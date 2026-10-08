#!/usr/bin/env python3
"""Q205: the Z-Anatomy model fitted to the VISIBLE HUMAN FEMALE -- wrist chain (forearm bones refit on her evidence so that radius / ulna meet her carpals), hand joint closure (carpometacarpal /
metacarpophalangeal gaps), the soft tissue carried by the bone-anchored field (Q199 machinery), metadata (card names / atlas facts), skin welds.  In-process patch of the published Q202 page:
the Q199 full-resolution state (a dump of the Q199 build: build/q205/after_q199.npz) is the start of the structures that move, every other structure is copied byte for byte.

    python3 scripts/zanatomy/q205_female.py [--state build/q205/after_q199.npz] [--dump build/q205/female_state.npz]
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
TUBE_CLOSE = (25.0, 25.0, 35.0)
HAND_RE = r"metacarpal|finger_of_hand|scaphoid|lunate|triquetrum|pisiform|trapezi|capitate|hamate"


def load_all(state):
    from scripts.zanatomy import q190_metrics as Mx
    L = Mx.load_dump(state)
    by = {d["id"]: {"v": d["v"].copy(), "f": d["f"], "cat": d["cat"], "r": d["r"]} for d in L}
    return by, {i: d["r"] for i, d in by.items()}


def evidence(side, by, her):
    """her radius / ulna evidence (atlas mm): right = her CT meshes' surfaces, left = her left-forearm cryosection voxels (Q192) assigned to the nearest Z forearm bone"""
    from scripts.zanatomy.q191_hand import surf_pts
    out = {}
    if side == "r":
        for b in ("radius", "ulna"):
            out[b] = surf_pts(her[b + "_r"]["v"].astype(float), her[b + "_r"]["f"], 6000)
        return out
    from scripts.zanatomy import q192_left_hand as H
    fa = H.load_evidence()["forearm"].astype(float)
    tr = {b: cKDTree(by[b + "_l"]["v"][::2]) for b in ("radius", "ulna")}
    dR, dU = tr["radius"].query(fa)[0], tr["ulna"].query(fa)[0]
    near = np.minimum(dR, dU) < 12.0
    out["radius"] = fa[near & (dR <= dU)]
    out["ulna"] = fa[near & (dR > dU)]
    return out


class FieldX:
    """q199_elbow.Field extended by extra MOVING bones with a constant displacement (the metacarpal / phalanx rays closed onto their joints): D = sum_b w_b D_b / sum w_b"""

    def __init__(self, base, side, by, extra):
        from scripts.zanatomy import q199_elbow as E
        self.E = E
        self.base = base
        self.extra = extra
        self.trees = {i: cKDTree(E.at(by[i]["v"], E.bary_samples(by[i]["v"], by[i]["f"], 1500, seed=3))) for i in extra}
        hc = base.ch.hc
        pts = [d["v"] for i, d in by.items() if d["cat"] == "bone" and i not in base.moving and i not in extra and np.linalg.norm(d["v"].mean(0) - hc) < 450.0]
        self.fixed = cKDTree(np.vstack(pts))

    def __call__(self, X):
        E = self.E
        W, D = [], []
        for n, fn in self.base.moving.items():
            W.append(1.0 / (self.base.trees[n].query(X)[0] + E.W_SOFT_MM) ** E.W_POWER)
            D.append(fn(X))
        for i, t in self.extra.items():
            W.append(1.0 / (self.trees[i].query(X)[0] + E.W_SOFT_MM) ** E.W_POWER)
            D.append(np.tile(t, (len(X), 1)))
        W.append(1.0 / (self.fixed.query(X)[0] + E.W_SOFT_MM) ** E.W_POWER)
        D.append(np.zeros_like(X))
        W.append(np.full(len(X), 1.0 / (E.W_NULL_MM + E.W_SOFT_MM) ** E.W_POWER))
        D.append(np.zeros_like(X))
        W = np.array(W)
        W /= W.sum(0)
        return (W[:, :, None] * np.array(D)).sum(0)


def surface_gap(by, a, b, n=2500):
    from scripts.zanatomy.q191_hand import surf_pts
    ta = cKDTree(surf_pts(by[a]["v"], by[a]["f"], n, 1))
    d, j = ta.query(surf_pts(by[b]["v"], by[b]["f"], n, 2))
    k = int(np.argmin(d))
    return float(d[k]), ta.data[j[k]], surf_pts(by[b]["v"], by[b]["f"], n, 2)[k]


def close_rays(by, raw, side, max_mm=8.0, tol_mm=2.0, log=print):
    """metacarpal -> carpals and phalanx -> metacarpal joints that are open (gap > tol_mm; the Z-source contact is < 1 mm): the ray (metacarpal + phalanges, rigid) / the phalanges chain is translated toward the
    joint by (gap - 0.5 mm) <= max_mm.  Returns {bone id: translation}"""
    from scripts.zanatomy.q191_hand import bone_ids, ORD
    ids = bone_ids(side)
    moves = {}
    s = "_" + side
    for o in ORD:
        mc = f"zan_{o}_metacarpal_bone{s}"
        phs = [i for i in ids["phal"] if f"_of_{o}_finger" in i]
        # CMC: nearest carpal
        best = min((surface_gap(by, c, mc) + (c,) for c in ids["carpals"]), key=lambda t: t[0])
        g, pc, pm, c = best
        if g > tol_mm:
            t = (pc - pm) / max(g, 1e-6) * min(max_mm, g - 0.5)
            for b in [mc] + phs:
                moves[b] = moves.get(b, np.zeros(3)) + t
            log(f"  Q205 {side} {o}: CMC gap to {c[4:-2]} {g:.1f} mm -> ray moved {np.linalg.norm(t):.1f} mm")
            for b in [mc] + phs:
                by[b]["v"] = by[b]["v"] + t
        g2, pc2, pm2 = surface_gap(by, mc, phs[0])
        if g2 > tol_mm:
            t = (pc2 - pm2) / max(g2, 1e-6) * min(max_mm, g2 - 0.3)
            for b in phs:
                moves[b] = moves.get(b, np.zeros(3)) + t
                by[b]["v"] = by[b]["v"] + t
            log(f"  Q205 {side} {o}: MCP gap {g2:.1f} mm -> phalanges moved {np.linalg.norm(t):.1f} mm")
        for a, b_ in zip(phs[:-1], phs[1:]):
            g3, pc3, pm3 = surface_gap(by, a, b_)
            if g3 > tol_mm:
                t = (pc3 - pm3) / max(g3, 1e-6) * min(max_mm, g3 - 0.3)
                for b in phs[phs.index(b_):]:
                    moves[b] = moves.get(b, np.zeros(3)) + t
                    by[b]["v"] = by[b]["v"] + t
                log(f"  Q205 {side} {o}: interphalangeal gap {g3:.1f} mm -> distal part moved {np.linalg.norm(t):.1f} mm")
    return moves


def forearm_and_hand(by, raw, side, her, skin, skin_tree, regions, moved_prev, log=print):
    from scripts.zanatomy import q199_elbow as E
    from scripts.zanatomy import q205_forearm_f as FF
    ev = evidence(side, by, her)
    ch, frep = FF.fit_forearm_f(side, by, raw, ev, log=log)
    s = "_" + side
    v_old = {n: by[n + s]["v"].copy() for n in ("humerus", "radius", "ulna")}
    # the ray closure uses the CURRENT hand bones (they were fitted to her CT / photographs: kept) -- measured after the forearm bones moved? the wrist gap is between forearm bones and carpals only, so independent
    base = E.Field(side, by, raw, ch)
    from scripts.zanatomy.q191_hand import bone_ids
    hb_before = {b: by[b]["v"].copy() for b in sum(bone_ids(side).values(), [])}
    moves = close_rays(by, raw, side, log=log)
    for b, t in moves.items():
        by[b]["v"] = hb_before[b].copy()            # refine_side measures with the bones where the field was built; the ray bones are set after it
    FX = FieldX(base, side, by, moves) if moves else base
    zone = {}
    for i, d in by.items():
        if d["cat"] in ("skin", "bone") or not (i.endswith(s) or s + "_" in i) or i in moved_prev:
            continue
        if np.linalg.norm(d["v"].mean(0) - ch.hc) > 700.0:
            continue
        if float(np.linalg.norm(FX(d["v"]), axis=1).max()) >= 1.5:
            zone[i] = True
    log(f"  Q205 {side}: {len(zone)} forearm / wrist / hand structures follow the refit bones")

    def scope(side_, i, raw_i, region, jc, hum_tree, humerus_moved=True):
        return i in zone

    E.SKIN_W, E.ATTACH_W, E.ATTACH_CAP_RUN, E.SEPARATE_MAX_MM, E.SKIN_CAP_MM = 6.0, 3.0, 20.0, 8.0, 20.0
    wc = np.asarray(frep["wrist_centre_raw"], float)
    r = E.refine_side(side, by, raw, ch, skin, skin_tree, regions=regions, log=log, her=her, label_sides=("r",), scope=scope, extra_centres=[wc], allow_unchanged=True, note_fn=note,
                      tube_close=TUBE_CLOSE, close_rounds=10, arm_radius_mm=800.0, final_skin_clamp=12.0, revert_outside_pp=8.0, field_fn=lambda i, v0: FX(v0))
    for b, t in moves.items():
        by[b]["v"] = by[b]["v"] + t
    return {"forearm": frep, "ray_moves_mm": {b: round(float(np.linalg.norm(t)), 2) for b, t in moves.items()}, "structures": r["structures"], "bones": r["bones"], "continuity": {k: v for k, v in r["continuity"].items() if k != "rows"},
            "reverted_outside_skin": r.get("reverted_outside_skin", {})}


def note(side, i, cat, q, m1, mv, cont):
    from scripts.zanatomy import q199_elbow as E
    how = {"not moved by the field": "its origin / insertion footprint brought back to the bone", "gap closure only": "closed up against the structures it touches in the Z source"}.get(q["name"])
    s = "left" if side == "l" else "right"
    txt = (f" Q205: {'adjusted' if how else 'moved'} with the {s} forearm bones refit at the wrist ("
           + (how if how else f"radius / ulna refit on her own evidence so that they meet her carpals (Q204: forearm -> carpal gaps up to 20 mm); tissue carried by the bone-anchored field: {q['name']}")
           + f"; mean {mv.mean():.1f} mm, max {mv.max():.1f} mm). Before -> after: " + E._fmt_m(q["m0"]) + " -> " + E._fmt_m(m1) + ".")
    a0, a1 = q["att0"], q["att1"]
    if a0 and a1:
        txt += " Origin / insertion footprint to the bone (source / before / after, mm): " + "; ".join(f"{b.rsplit('_', 1)[0]} {a1[b]['source_mm']} / {a0[b]['now_mm']} / {a1[b]['now_mm']}" for b in a1 if b in a0) + "."
    if cont:
        txt += f" Gap to {cont['neighbours']} neighbour structure(s) it touches in the Z source: {cont['before_mm']} -> {cont['after_mm']} mm."
    return txt


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--state", default=str(REPO / "build" / "q205" / "after_q199.npz"))
    ap.add_argument("--dump", default=str(REPO / "build" / "q205" / "female_state.npz"))
    ap.add_argument("--sides", default="r,l")
    a = ap.parse_args(argv)
    t0 = time.time()
    from scripts.zanatomy import body_ctx
    from scripts.transfer.zan_to_vhf_whole_body import load_her_meshes
    from scripts.ribs_from_ct_labels import load_skin
    by, raw = load_all(a.state)
    her = load_her_meshes()
    skin = load_skin("vhf")
    skin_tree = cKDTree(np.asarray(skin.vertices, float))
    regions = json.loads(body_ctx.REGION_REPORT.read_text())["region_of_structure"]
    v0 = {i: d["v"].copy() for i, d in by.items()}
    moved_q199 = set(json.loads((REPO / "data" / "derived" / "Q199_zan_female_q199_build.json").read_text())["q199"]["moved_ids"]) if False else set()
    rep = {}
    for side in a.sides.split(","):
        rep[side] = forearm_and_hand(by, raw, side, her, skin, skin_tree, regions, moved_q199)
        print(side, "done", round(time.time() - t0), flush=True)
    changed = [i for i in by if not np.array_equal(by[i]["v"], v0[i]) or by[i].get("fit_note")]
    arrs = {"ids": np.array(json.dumps(changed)), "notes": np.array(json.dumps({i: by[i].get("fit_note", "") for i in changed})), "report": np.array(json.dumps(rep, default=float)),
            "cats": np.array(json.dumps({i: by[i]["cat"] for i in changed}))}
    for k, i in enumerate(changed):
        arrs[f"v{k}"] = by[i]["v"].astype(np.float64)
    np.savez(a.dump, **arrs)
    print("changed", len(changed), "->", a.dump, round(time.time() - t0), "s")


if __name__ == "__main__":
    main()
