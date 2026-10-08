"""Q206: the non-bone, non-muscle structures of the WRIST / HAND / DISTAL FOREARM (vessels, nerves, retinacula, ligaments, capsules, tendon sheaths, fascia) carried onto the Q205 bones.

Why: Q205 refit the bones (and muscles) of the two Z-fitted pages to his / her evidence, but the soft tissue of the hand was judged against his CT meshes / CT skin (male) or only against the
humerus-radius-ulna of the elbow chain (female), not against the DISPLAYED Z bones and the DISPLAYED Z skin that the Q198 audit uses.  Q198 wrist junction counts rose (female left 0/4/9 -> 2/8/18,
right 1/13/17 -> 2/10/25; male right majors 6 -> 10: palmar vessels / nerves inside bone, retinaculum / FCR sheath up to 10.8 mm outside the carried Z skin).

Method (per side; the same bone-anchored field the Q205 bones were moved by):
  1. FIELD  D(x) = sum_b w_b(x) D_b(x) / sum_b w_b(x) over every bone (D_b = the vertex displacement of the bone from its pre-Q205 pose to its Q205 pose, nearest vertices; fixed bones and a null anchor D = 0),
     w_b = 1 / (d_b + 6 mm)^2 with d_b the distance to the bone as it was (Q199 constants, q199_elbow.Field), gated 0.8-3 mm.
  2. CANDIDATES per structure: (A) where the Q205 page has it, (B) its pre-Q205 position + the field, (B10) the field low-passed 10 mm, (Bm) the mean translation of the field.  Each goes through the
     same guard ladder: pushed out of the displayed bones (voxel depth field of the Q198 bone fill; vessels / nerves / fascia 1 mm, ligaments / capsules / sheaths / tendons 2 mm, push <= 8 mm),
     back inside the displayed skin (Q198 SkinField; target 1 mm inside, clamp <= 14 mm), no vertex > 12 mm from the field result, closed bodies: volume +-10 % of the Z source, folds (share of edges
     newly folded) not larger than the structure had; the cheapest by cost = 6 x outside skin % + 2 x inside bone % + stretched triangles % + 6 x folded edges %; the field result B is kept unless another is cheaper by > 2.
  3. CONTINUITY: pairs that touch in the Z source and are further apart now close up (q199_elbow.close_gaps, vessel / nerve pairs > 3 mm, tube closure 25 / 25 / 35 mm) -- the tube continuity with the
     proximal parts; then one more skin / bone guard and a revert if the structure ended worse than before the closure.
Everything else is untouched.
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q199_elbow as E  # noqa: E402
from scripts.zanatomy import q190_refine as Q  # noqa: E402
from scripts.zanatomy import q190_metrics as Mx  # noqa: E402
from scripts.zanatomy import q191_hand as H  # noqa: E402

SOFT = ("vessel", "nerve", "ligament", "tendon", "fascia", "bursa", "cartilage")
BONE_OK = ("ligament", "bursa", "cartilage", "tendon")
HAND_RE = re.compile(r"metacarpal|finger_of_hand|scaphoid|lunate|triquetrum|pisiform|trapezi|capitate|hamate")
PUSH_TOL = {"vessel": 1.0, "nerve": 1.0, "fascia": 1.0, "lymphatic": 1.0, "ligament": 3.0, "tendon": 3.0, "bursa": 3.0, "cartilage": 3.0}
SKIN_TARGET_MM = 2.0           # a vertex more than this outside the displayed skin is brought back to 0.5 mm inside (the Q198 audit counts > 3 mm)
SKIN_COUNT_MM = 3.0            # the Q198 audit counts > 3 mm
BONE_COUNT_MM = 1.5
PUSH_MAX = 8.0
SKIN_MAX = 14.0
CAP_MM = 12.0
A_CAP_MM = 20.0            # no vertex further than this from where the Q205 page has the structure
REG_W = 0.3                # cost per mm of mean move away from the Q205 page
ARM_REGIONS = ("upper_limb", "forearm_hand")
FOLD_SLACK, FOLD_SLACK_TUBE = 2.5, 6.0      # share of edges newly folded a candidate may add (tubes: 1-2 mm radius, a 2-5 mm push folds a few of their sliver triangles)
EDGE_SCALE_TOL = 0.25      # length guard: median edge ratio vs the Z source may not change by more than this from the Q205 page
ZONE_HAND_MM, ZONE_WRIST_MM = 30.0, 120.0


class WristField:
    """the Q199 field with the Q205 bone displacement: D_b(x) = displacement of the nearest vertices (k = 3, inverse distance) of bone b between its pre-Q205 and its Q205 pose"""

    def __init__(self, side, by_cur, v_pre, centre, moved_mm=0.3):
        s = "_" + side
        self.moving, self.fixed_pts = {}, []
        for i, d in by_cur.items():
            if d["cat"] != "bone" or not (i.endswith(s)):
                continue
            if np.linalg.norm(v_pre[i].mean(0) - centre) > 450.0:
                continue
            dv = d["v"] - v_pre[i]
            if np.linalg.norm(dv, axis=1).max() > moved_mm:
                self.moving[i] = (cKDTree(v_pre[i]), dv)
            else:
                self.fixed_pts.append(v_pre[i])
        for i, d in by_cur.items():          # bones of the other side / trunk / skull within reach are fixed anchors too
            if d["cat"] == "bone" and not i.endswith(s) and np.linalg.norm(v_pre[i].mean(0) - centre) < 450.0:
                self.fixed_pts.append(v_pre[i])
        self.fixed = cKDTree(np.vstack(self.fixed_pts))
        self.bone_dv = {i: float(np.linalg.norm(m[1], axis=1).max()) for i, m in self.moving.items()}

    def __call__(self, X):
        X = np.asarray(X, float)
        W, D = [], []
        for i, (tree, dv) in self.moving.items():
            d, j = tree.query(X, k=3)
            w = 1.0 / (d + 0.5)
            w /= w.sum(1, keepdims=True)
            D.append((dv[j] * w[:, :, None]).sum(1))
            W.append(1.0 / (d[:, 0] + E.W_SOFT_MM) ** E.W_POWER)
        W.append(1.0 / (self.fixed.query(X)[0] + E.W_SOFT_MM) ** E.W_POWER)
        D.append(np.zeros_like(X))
        W.append(np.full(len(X), 1.0 / (E.W_NULL_MM + E.W_SOFT_MM) ** E.W_POWER))
        D.append(np.zeros_like(X))
        W = np.array(W)
        W /= W.sum(0)
        return (W[:, :, None] * np.array(D)).sum(0)


# ------------------------------------------------------------------------------------------------ guards
def _coherent(f, need, mask, sigma, edge):
    """normalized convolution of the push vectors of the violating vertices over the mesh graph: the neighbourhood of a violator moves with it (a vessel / nerve ring or a sheet patch translates as a unit, no pleats)"""
    m = mask.astype(float)
    edge = max(float(edge), 0.3)
    num = E.lowpass(need * m[:, None], f, sigma, edge)
    den = E.lowpass(np.repeat(m[:, None], 3, axis=1), f, sigma, edge)[:, 0]
    out = num / np.maximum(den, 1e-3)[:, None]
    return out * np.clip(den / 0.5, 0.0, 1.0)[:, None]


def _iterate(f, v, vec_fn, sigma, max_move, iters=6):
    P = v.copy()
    e = np.vstack([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
    edge = float(np.linalg.norm(v[e[:, 0]] - v[e[:, 1]], axis=1).mean())
    for _ in range(iters):
        need, mask = vec_fn(P)
        if not mask.any():
            break
        P = E.cap_to(P + _coherent(f, need, mask, sigma, edge), v, max_move)
    return P


def push_out(env, side, v, f, tol, sigma, max_move=PUSH_MAX):
    """vertices more than `tol` mm inside a displayed bone move out along the gradient of the bone's signed field; the push is spread coherently over the mesh"""
    def fn(P):
        dep = env.depth(P, side)
        mask = dep > tol
        need = np.zeros_like(P)
        if mask.any():
            need[mask] = env.bone[side].gradient(P[mask]) * (dep[mask] - tol + 0.6)[:, None]
        return need, mask
    return _iterate(f, v, fn, sigma, max_move)


def clamp_skin(env, v, f, sigma, target=SKIN_TARGET_MM, max_move=SKIN_MAX):
    """vertices more than `target` mm outside the displayed skin go back to 0.5 mm inside it along the skin gradient; spread coherently over the mesh"""
    def fn(P):
        sd = env.skin_sd(P)
        mask = sd > target
        need = np.zeros_like(P)
        if mask.any():
            need[mask] = -env.skin.gradient(P[mask]) * (sd[mask] + 0.5)[:, None]
        return need, mask
    return _iterate(f, v, fn, sigma, max_move)


def guard(env, side, v, f, r, cat, i, ref, vr0):
    v1 = np.asarray(v, float).copy()
    tol = PUSH_TOL.get(cat, 1.0)
    sigma = 5.0 if cat in ("vessel", "nerve") else 8.0
    for _ in range(3):                      # the last step is the bone push: a structure never ends inside a bone because the (thin) displayed skin squeezed it
        v1 = clamp_skin(env, v1, f, sigma)
        v1 = push_out(env, side, v1, f, tol, sigma)
    v1 = E.cap_to(v1, ref, CAP_MM)
    if E._closed(f) and not H.NOT_BODY.search(i) and cat != "bone" and vr0 is not None:
        v1 = E.vol_clamp(v1, r, f, vr0 * 0.9, vr0 * 1.1)
    return v1


def metrics(env, side, v, r, f):
    m = env.measure(v, side)
    st = Mx.stretch_stats(v, r, f)
    m["stretched_pct"] = round(100 * (st["area_frac_gt1.5"] + st["area_frac_lt0.67"]), 1) if st else 0.0
    m["folded_pct"] = round(100 * H.fold_stats(v, r, f), 2)
    m["volume_ratio"] = H.vol_ratio(v, r, f)
    m["edge_scale"] = round(float(st["scale_edge_med"]), 4) if st else 1.0
    return m


def cost(m, cat, m0):
    c = 6.0 * m["outside_skin_pct"] + 1.0 * m["stretched_pct"] + (3.0 if cat in ("vessel", "nerve") else 6.0) * m["folded_pct"]
    c += (0.5 if cat in BONE_OK else 3.0) * m["inside_bone_pct"]
    return c


def fmt(m):
    s = f"outside the displayed skin {m['outside_skin_pct']} % (max {m['outside_skin_max_mm']} mm), inside the displayed bones {m['inside_bone_pct']} % (max {m['inside_bone_max_mm']} mm), stretched triangles {m['stretched_pct']} %, folded edges {m['folded_pct']} %"
    return s


def in_zone(side, i, d, v_cur, v_pre, hand_tree, wrist, regions):
    s = "_" + side
    if d["cat"] not in SOFT or not (i.endswith(s) or s + "_" in i) or regions.get(i) not in ARM_REGIONS:
        return False
    for v in (v_cur, v_pre):
        if (hand_tree.query(v[::2])[0] < ZONE_HAND_MM).any() or (np.linalg.norm(v - wrist, axis=1) < ZONE_WRIST_MM).any():
            return True
    return False


def carry_side(env, side, by, v_pre, raw, centre_raw, regions, log=print):
    """by: Q205 state (mutated); returns the report"""
    s = "_" + side
    wrist = env.wrist[side]
    F = WristField(side, by, v_pre, wrist)
    log(f"  Q206 {side}: field from {len(F.moving)} moving bones (max bone move {max(F.bone_dv.values()):.1f} mm)")
    hand_ids = [i for i, d in by.items() if d["cat"] == "bone" and i.endswith(s) and (HAND_RE.search(i))]
    hand_pts = np.vstack([by[i]["v"][::3] for i in hand_ids] + [v_pre[i][::3] for i in hand_ids])
    hand_tree = cKDTree(hand_pts)
    ids = [i for i, d in by.items() if in_zone(side, i, d, d["v"], v_pre[i], hand_tree, wrist, regions)]
    log(f"  Q206 {side}: {len(ids)} structures in the wrist / hand / distal forearm zone")
    v_cur = {i: by[i]["v"].copy() for i in ids}
    rep, ctx = {}, {}
    for n, i in enumerate(ids):
        d = by[i]
        f, r, cat = d["f"], raw[i].astype(float), d["cat"]
        vA, vP = v_cur[i], v_pre[i].astype(float)
        mA = metrics(env, side, vA, r, f)
        D = E.gated(F(vP))
        dmax = float(np.linalg.norm(D, axis=1).max())
        # structures that are fine and that the field does not move are left alone (bit-identical)
        if dmax < 0.05 and mA["outside_skin_pct"] <= 3.0 and mA["inside_bone_pct"] <= 3.0:
            continue
        vr0 = mA["volume_ratio"]
        cands = []
        for nm, vv in (("kept where the Q205 page has it", vA), ("field from its pre-Q205 pose", vP + D)):
            if nm.startswith("field") and dmax < 0.05:
                continue
            cands.append((nm, vv))
        if dmax >= 0.05:
            if len(vP) > 30:
                cands.append(("field low-passed 10 mm", vP + E.lowpass(D, f, 10.0)))
            if float(np.linalg.norm(vP - vP.mean(0), axis=1).max()) < 30.0:      # a mean translation only for compact structures
                cands.append(("mean translation of the field", vP + np.tile(D.mean(0), (len(vP), 1))))
        res = []
        for nm, vv in cands:
            g = E.cap_to(guard(env, side, vv, f, r, cat, i, vv, vr0), vA, A_CAP_MM)
            mm = metrics(env, side, g, r, f)
            if mm["folded_pct"] > (max(mA["folded_pct"] + FOLD_SLACK_TUBE, 10.0) if cat in ("vessel", "nerve") else max(mA["folded_pct"] + FOLD_SLACK, 4.0)):          # fold guard
                continue
            if not E._closed(f) and abs(mm["edge_scale"] / max(mA["edge_scale"], 1e-6) - 1.0) > EDGE_SCALE_TOL:      # length guard (tubes, sheets)
                continue
            res.append((cost(mm, cat, mA) + REG_W * float(np.linalg.norm(g - vA, axis=1).mean()), nm, g, mm))
        if not res:
            continue
        best = min(res, key=lambda t: t[0])
        field_c = [t for t in res if t[1].startswith("field from")]
        pick = field_c[0] if field_c and field_c[0][0] <= best[0] + 2.0 else best
        c1, nm, v1, m1 = pick
        if nm.startswith("kept") and cost(mA, cat, mA) <= c1 + 0.5:
            continue
        mv = np.linalg.norm(v1 - vA, axis=1)
        if mv.max() < 0.3:
            continue
        by[i]["v"] = v1
        rep[i] = {"cat": cat, "ladder": nm, "mean_move_mm": round(float(mv.mean()), 2), "max_move_mm": round(float(mv.max()), 2), "field_max_mm": round(dmax, 2), "before": mA, "after": m1}
        ctx[i] = nm
    log(f"  Q206 {side}: {len(rep)} structures moved by the ladder")
    # continuity with the structures they touch in the Z source (tube closure for vessels / nerves)
    zb = [H.Inside(env.by[b]["v"], env.by[b]["f"]) for b in env.bone_ids[side] if b.endswith(s) and (HAND_RE.search(b) or b in ("radius" + s, "ulna" + s))]
    v_field = {i: by[i]["v"].copy() for i in ids}
    moved = set(rep)
    before_cl = {i: by[i]["v"].copy() for i in ids}
    cont = E.close_gaps(side, by, raw, moved, None, None, zb, np.atleast_2d(centre_raw), v_field, log=log, rounds=8, tube_close=(25.0, 25.0, 35.0))
    # one more guard after the closure and a revert of anything that ended worse
    for i in ids:
        if np.array_equal(by[i]["v"], before_cl[i]):
            continue
        d = by[i]
        f, r, cat = d["f"], raw[i].astype(float), d["cat"]
        vb = before_cl[i]
        mb = metrics(env, side, vb, r, f)
        vc = guard(env, side, by[i]["v"], f, r, cat, i, by[i]["v"], mb["volume_ratio"])
        mc = metrics(env, side, vc, r, f)
        if cost(mc, cat, mb) > cost(mb, cat, mb) + 1.0:
            by[i]["v"] = vb
            cont.setdefault("reverted_after_closure", []).append(i)
        else:
            by[i]["v"] = vc
    chain = chain_closure(env, side, by, raw, ids, log=log)
    for i in ids:
        if i in rep or np.array_equal(by[i]["v"], v_cur[i]):
            continue
        r, f = raw[i].astype(float), by[i]["f"]
        mv = np.linalg.norm(by[i]["v"] - v_cur[i], axis=1)
        if mv.max() < 0.3:
            by[i]["v"] = v_cur[i]
            continue
        rep[i] = {"cat": by[i]["cat"], "ladder": "gap closure only", "before": metrics(env, side, v_cur[i], r, f)}
        ctx[i] = "gap closure only"
    for i in list(rep):
        r, f = raw[i].astype(float), by[i]["f"]
        mv = np.linalg.norm(by[i]["v"] - v_cur[i], axis=1)
        if mv.max() < 0.3:
            by[i]["v"] = v_cur[i]
            rep.pop(i)
            continue
        rep[i]["after"] = metrics(env, side, by[i]["v"], r, f)
        rep[i]["mean_move_mm"], rep[i]["max_move_mm"] = round(float(mv.mean()), 2), round(float(mv.max()), 2)
        rep[i]["closure"] = cont["per_structure"].get(i)
    for k, v in chain.items():
        for i in k.split(" -> "):
            if i in rep:
                rep[i].setdefault("chain", []).append({"pair": k, **v})
    return {"structures": rep, "continuity": {k: v for k, v in cont.items() if k != "rows"}, "chain_closure": chain, "n_zone": len(ids), "moving_bones": F.bone_dv}


def _end_gap(va, vb):
    d, j = cKDTree(vb).query(va)
    k = int(np.argmin(d))
    return float(d[k]), k, int(j[k])


def _move_end(v, k, target, sigma):
    dz = np.linalg.norm(v - v[k], axis=1)
    return v + (target - v[k])[None, :] * np.exp(-((dz / sigma) ** 2))[:, None]


def chain_closure(env, side, by, raw, ids, log=print, rounds=3, tol=3.0, w_gap=4.0, sigma=25.0):
    """the wrist chains of q206_continuity (radial / ulnar artery -> palmar arches -> digital arteries, median / ulnar nerve -> digital branches ...): a pair that is continuous in the Z source (<= 3 mm) and is
    now further apart than `tol` is closed by moving the end of the parent, of the child or of both (<= 35 mm, Gaussian over `sigma` mm of the tube), each through the full guard ladder; the cheapest
    by  cost(parent) + cost(child) + w_gap * (gap - tol)  wins, and only if it beats the present pair."""
    from scripts.zanatomy import q206_continuity as CT
    from scripts.zanatomy import q190_metrics as Mx
    s_ = "_" + side
    idset = set(ids)
    rows = {}
    for rnd in range(rounds):
        n_closed = 0
        for p_, c_ in CT.CHAINS:
            a, b = f"{p_}{s_}", f"{c_}{s_}"
            if a not in idset or b not in idset:
                continue
            ra, rb = raw[a].astype(float), raw[b].astype(float)
            src = float(cKDTree(rb).query(ra)[0].min()) * Mx.BODY_SCALE
            if src > 3.0:
                continue                                   # not continuous in the Z source either
            va, vb = by[a]["v"], by[b]["v"]
            g0, ka, jb = _end_gap(va, vb)
            if g0 <= max(tol, src + 2.0):
                continue
            ma, mb = metrics(env, side, va, ra, by[a]["f"]), metrics(env, side, vb, rb, by[b]["f"])
            j0 = cost(ma, by[a]["cat"], ma) + cost(mb, by[b]["cat"], mb) + w_gap * (g0 - tol)
            best = None
            ta, tb = vb[jb], va[ka]
            toward = lambda x, y: x + (y - x) / max(np.linalg.norm(y - x), 1e-6) * min(max(np.linalg.norm(y - x) - 1.0, 0.0), 35.0)
            for nm, na, nb in (("parent", _move_end(va, ka, toward(va[ka], ta), sigma), vb), ("child", va, _move_end(vb, jb, toward(vb[jb], tb), sigma)),
                               ("both", _move_end(va, ka, va[ka] + 0.5 * (toward(va[ka], ta) - va[ka]), sigma), _move_end(vb, jb, vb[jb] + 0.5 * (toward(vb[jb], tb) - vb[jb]), sigma))):
                ga = guard(env, side, na, by[a]["f"], ra, by[a]["cat"], a, na, None) if na is not va else va
                gb = guard(env, side, nb, by[b]["f"], rb, by[b]["cat"], b, nb, None) if nb is not vb else vb
                g1 = _end_gap(ga, gb)[0]
                ma1, mb1 = metrics(env, side, ga, ra, by[a]["f"]), metrics(env, side, gb, rb, by[b]["f"])
                if ma1["folded_pct"] > max(ma["folded_pct"] + FOLD_SLACK_TUBE, 10.0) or mb1["folded_pct"] > max(mb["folded_pct"] + FOLD_SLACK_TUBE, 10.0):
                    continue
                j1 = cost(ma1, by[a]["cat"], ma) + cost(mb1, by[b]["cat"], mb) + w_gap * max(g1 - tol, 0.0)
                if best is None or j1 < best[0]:
                    best = (j1, nm, ga, gb, g1)
            if best is not None and best[0] < j0 - 1.0 and best[4] < g0:
                by[a]["v"], by[b]["v"] = best[2], best[3]
                rows[f"{a} -> {b}"] = {"mover": best[1], "gap_before_mm": round(g0, 2), "gap_after_mm": round(best[4], 2), "source_mm": round(src, 2)}
                n_closed += 1
        if not n_closed:
            break
    log(f"  Q206 {side}: chain closure {len(rows)} pairs, " + ", ".join(f"{k.split(' -> ')[1][:22]} {v['gap_before_mm']}->{v['gap_after_mm']}" for k, v in list(rows.items())[:6]))
    return rows


def note(side, i, r):
    s = "left" if side == "l" else "right"
    b, a = r["before"], r.get("after", r["before"])
    how = {"kept where the Q205 page has it": "kept where the Q205 page has it and pushed off the displayed bones / back inside the displayed skin",
           "gap closure only": "closed up against the structures it touches in the Z source"}.get(r["ladder"], f"carried by the bone-anchored field of the Q205 bones ({r['ladder']})")
    t = (f" Q206: wrist / hand soft tissue refit against the DISPLAYED {s} hand bones and skin ({how}; mean {r.get('mean_move_mm', 0):.1f} mm, max {r.get('max_move_mm', 0):.1f} mm from the Q205 page). "
         f"Before -> after: {fmt(b)} -> {fmt(a)}.")
    for ch in r.get("chain", []):
        t += f" Wrist chain {ch['pair'].replace(' -> ', ' to ')}: gap {ch['gap_before_mm']} -> {ch['gap_after_mm']} mm (Z source {ch['source_mm']} mm; moved: {ch['mover']})."
    c = r.get("closure")
    if c:
        t += f" Gap to {c['neighbours']} neighbour structure(s) it touches in the Z source: {c['before_mm']} -> {c['after_mm']} mm."
    return t


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("which", choices=["male", "female"])
    ap.add_argument("--sides", default="r,l")
    ap.add_argument("--dump")
    a = ap.parse_args(argv)
    from scripts.zanatomy import q206_state as ST
    from scripts.zanatomy import q206_env as EN
    t0 = time.time()
    cfg = ST.CFG[a.which]
    by, v_pre, raw = ST.load(a.which)
    env = EN.Env(cfg["key"])
    print("env", round(time.time() - t0), "s", flush=True)
    from scripts.zanatomy import body_ctx
    regions = json.loads(body_ctx.REGION_REPORT.read_text())["region_of_structure"]
    v0 = {i: d["v"].copy() for i, d in by.items()}
    rep = {}
    for side in a.sides.split(","):
        s = "_" + side
        cr = np.vstack([raw[b] for b in by if re.search(r"capitate|lunate", b) and b.endswith(s)]).mean(0)
        rep[side] = carry_side(env, side, by, v_pre, raw, cr, regions)
        print(side, "done", round(time.time() - t0), "s", flush=True)
    changed = [i for i in by if not np.array_equal(by[i]["v"], v0[i])]
    notes = {}
    for side in rep:
        for i, r in rep[side]["structures"].items():
            notes[i] = note(side, i, r)
    out = Path(a.dump or REPO / "build" / "q206" / f"{a.which}_state.npz")
    arrs = {"ids": np.array(json.dumps(changed)), "notes": np.array(json.dumps({i: notes.get(i, "") for i in changed})), "report": np.array(json.dumps(rep, default=float)),
            "cats": np.array(json.dumps({i: by[i]["cat"] for i in changed}))}
    for k, i in enumerate(changed):
        arrs[f"v{k}"] = by[i]["v"].astype(np.float64)
    np.savez(out, **arrs)
    print("changed", len(changed), "->", out, round(time.time() - t0), "s")


if __name__ == "__main__":
    main()
