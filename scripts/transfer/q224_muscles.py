#!/usr/bin/env python3
"""Q224 (3): muscles sawn flat at CT block edges / in several pieces on the two OWN pages (Q223 top defect 3 + 7).

    python3 scripts/transfer/q224_muscles.py --body m|f [--shard i/n] [--only id,id] [--cache DIR] [--list]

Per muscle (candidates = Q204 / Q223 findings: flat cut face > 100 mm2, detached piece > 2 % of the surface 5-60 mm from the main belly; read from the Q223 raw audit rows), three steps, each with the Q216 guards
(`q216_fix.Env.guards`: inside skin >= 1 mm, in-bone <= 8 % / <= 5 mm, volume / length bounds, one piece, <= 60 % inside other muscles and no neighbour newly across 40 / 60 %, NO operation brings the muscle back over a
traced nerve / vessel (the nerve clearance rule), the Z-fill continuation seam <= 2.5 mm or re-welded); a step that fails its guards is skipped and the reason recorded:
  1 RECONNECT  a detached piece (> 2 % of the area, > 5 mm away) is joined to the belly by a convex-hull loft of the two facing 3 mm sections (Q216 op_bridge, generalised to several pieces), re-meshed;
  2 EXTEND     the end that carries the flat cut face is pulled along the muscle's course onto the bone its card names (the Q214 / Q216 attachment pull, other end anchored, <= 25 mm; the nearest bone of any kind within
               16 mm when the named one is out of reach) = the muscle is extended through the missing block up to its attachment; only when the end is > 6 mm (the Q204 gate) from every bone;
  3 DOME       the planar facets that remain (the cut face itself) are replaced by a shallow dome (<= 3 mm, Q216 op_flat).
Class (subject) stays; volumes / lengths before -> after are recorded for every muscle; muscles whose steps all fail keep their mesh."""
from __future__ import annotations

import argparse
import json
import pickle
import re
import sys
import time
from pathlib import Path

import numpy as np
import trimesh
from scipy import ndimage as ndi
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "clinical"))
from scripts.transfer.q200_bundle import Bundle  # noqa: E402
from scripts.transfer import q216_common as C  # noqa: E402
from scripts.transfer import q216_fix as X  # noqa: E402
from scripts.transfer import q215_fill as Q15  # noqa: E402
from scripts.transfer.q224_common import BODIES, SCRATCH  # noqa: E402

CAP_MIN_MM2 = 100.0           # the audit's flat-cut finding starts here
ISLAND_SHARE_MIN = 0.02
ISLAND_GAP_MIN = 5.0
ISLAND_GAP_MAX = 60.0
BRIDGE_VOL = (1.0, 1.40)
CUM_VOL = (0.84, 1.40)
CUM_LEN = (0.88, 1.35)
CAP_END_RADIUS_MM = 30.0      # a cap belongs to an audit end when the cap centre is this close to the end's centre


def merged_rows(body):
    rows = json.loads((REPO / f"build/q223_raw_merged/Q204_regions_{BODIES[body]['pagekey']}.json").read_text())["rows"]
    return rows


def candidates(body):
    out = []
    for r in merged_rows(body):
        if r["sys"] not in ("muscle", "tendon"):
            continue
        caps = [c for c in (r.get("flat_caps") or []) if c["area_mm2"] > CAP_MIN_MM2]
        isl = ISLAND_GAP_MIN < r.get("max_island_gap_mm", 0) <= ISLAND_GAP_MAX and r.get("max_island_share_gt5mm", 0) > ISLAND_SHARE_MIN
        if caps or isl:
            out.append(dict(id=r["id"], caps=[(c["axis"], c["plane_mm"], c["area_mm2"]) for c in caps], island=(r.get("max_island_gap_mm"), r.get("max_island_share_gt5mm")) if isl else None,
                            side=r.get("side"), region=r.get("region")))
    out.sort(key=lambda c: -(max([a for _x, _p, a in c["caps"]] or [0]) + (300.0 if c["island"] else 0.0)))
    return out


# ------------------------------------------------------------------------------------------ step 1
def weld_pieces(v, f):
    from scripts.zanatomy.q198_core import weld, islands
    vw, fw = weld(np.asarray(v, float), np.asarray(f, np.int64), 0.02)
    return vw, fw, islands(vw, fw)


def op_bridge_islands(env, sid, v0, f0, log=print, max_rounds=4):
    """join every detached piece (> 2 % of the area, > 5 mm from the rest) to the belly by a loft of the two facing sections -> (v, f, info)"""
    v, f = v0, f0
    info = dict(op="bridge", rounds=[])
    for _ in range(max_rounds):
        vw, fw, isl = weld_pieces(v, f)
        if len(isl) < 2:
            break
        tot = sum(i["area"] for i in isl)
        big_idx = isl[0]["vidx"]
        cand = []
        for k in range(1, len(isl)):
            d = cKDTree(vw[isl[0]["vidx"]]).query(vw[isl[k]["vidx"]])[0].min()
            if isl[k]["area"] / tot > ISLAND_SHARE_MIN and d > ISLAND_GAP_MIN:
                cand.append((isl[k]["area"], k, float(d)))
        if not cand:
            break
        cand.sort(reverse=True)
        _a, k, gap = cand[0]
        # the facing ends: the small piece's vertices nearest to the belly (+ everything else that is not the small piece counts as 'belly')
        small_v = vw[isl[k]["vidx"]]
        rest = np.setdiff1d(np.arange(len(vw)), isl[k]["vidx"])
        rest = np.intersect1d(rest, np.unique(fw))
        d, i = cKDTree(vw[rest]).query(small_v)
        j = int(np.argmin(d))
        a_pt, b_pt = small_v[j], vw[rest][i[j]]
        ax = (b_pt - a_pt) / np.linalg.norm(b_pt - a_pt)
        sec_a = small_v[(small_v - a_pt) @ ax >= -3.0]
        vr = vw[rest]
        sec_b = vr[(vr - b_pt) @ ax <= 3.0]
        sec_b = sec_b[np.linalg.norm(sec_b - b_pt, axis=1) <= 40.0]
        hull = trimesh.convex.convex_hull(np.vstack([sec_a, sec_b]))
        grid = C.VoxGrid(vw.min(0) - 4.0, vw.max(0) + 4.0, C.H)
        m = C.VoxGrid.solid(grid, v, f)
        lo, hi = np.maximum(grid.idx(hull.bounds[0] - 1), 0), np.minimum(grid.idx(hull.bounds[1] + 1) + 1, grid.shape)
        ii = np.argwhere(np.ones(tuple(hi - lo), bool)) + lo
        hm = np.zeros(grid.shape, bool)
        hm[tuple(ii[hull.contains(grid.pos(ii))].T)] = True
        new = m | hm
        new = ndi.binary_closing(new, iterations=1) | new
        lab, n = ndi.label(new, structure=np.ones((3, 3, 3)))
        v1, f1 = C.mask_to_mesh(new, grid, sigma_vox=0.8, budget=Q15.BUDGET)
        info["rounds"].append(dict(gap_mm=round(gap, 2), small_part_area_share=round(isl[k]["area"] / tot, 3), bridge_added_cm3=round(C.mask_volume_cm3(new) - C.mask_volume_cm3(m), 2), components=int(n)))
        v, f = v1, f1
    if not info["rounds"]:
        return None, None, dict(info, why=["no detached piece above the thresholds in the base mesh (the finding is in a Z-fill continuation or is the merged view)"])
    return v, f, info


# ------------------------------------------------------------------------------------------ step 3 (large cut faces): refined dome
def conforming_split(v, f, split_edges):
    """split the given edges {(i, j) sorted} at their midpoints and re-triangulate every triangle that has 1, 2 or 3 split edges (a conforming mesh: no T-junction) -> (v, f)"""
    v = np.asarray(v, float)
    nv = len(v)
    mid = {}
    newv = []
    for e in sorted(split_edges):
        mid[e] = nv + len(newv)
        newv.append(0.5 * (v[e[0]] + v[e[1]]))
    V = np.vstack([v, np.array(newv)]) if newv else v
    out = []
    for a, b, c in f:
        e_ab, e_bc, e_ca = tuple(sorted((a, b))), tuple(sorted((b, c))), tuple(sorted((c, a)))
        m_ab, m_bc, m_ca = mid.get(e_ab), mid.get(e_bc), mid.get(e_ca)
        k = (m_ab is not None) + (m_bc is not None) + (m_ca is not None)
        if k == 0:
            out.append((a, b, c))
        elif k == 3:
            out += [(a, m_ab, m_ca), (m_ab, b, m_bc), (m_ca, m_bc, c), (m_ab, m_bc, m_ca)]
        elif k == 1:
            if m_ab is not None:
                out += [(a, m_ab, c), (m_ab, b, c)]
            elif m_bc is not None:
                out += [(b, m_bc, a), (m_bc, c, a)]
            else:
                out += [(c, m_ca, b), (m_ca, a, b)]
        else:                                    # two split edges: the corner they share is cut off, the quad left is split on its shorter diagonal
            if m_ab is None:                     # split bc, ca: shared corner c
                p, q, r, mp, mq = a, b, c, m_ca, m_bc          # corner r = c, edges r-p (ca) and r-q (bc)
            elif m_bc is None:                   # split ab, ca: shared corner a
                p, q, r, mp, mq = b, c, a, m_ab, m_ca
            else:                                # split ab, bc: shared corner b
                p, q, r, mp, mq = c, a, b, m_bc, m_ab
            # corner triangle (r, mq?, mp?) -- keep the original winding of (a, b, c)
            if m_ab is None:
                out.append((c, m_ca, m_bc))
                quad = [(a, b, m_bc, m_ca)]
            elif m_bc is None:
                out.append((a, m_ab, m_ca))
                quad = [(b, c, m_ca, m_ab)]
            else:
                out.append((b, m_bc, m_ab))
                quad = [(c, a, m_ab, m_bc)]
            for (p0, p1, p2, p3) in quad:
                d1 = np.linalg.norm(V[p0] - V[p2])
                d2 = np.linalg.norm(V[p1] - V[p3])
                if d1 <= d2:
                    out += [(p0, p1, p2), (p0, p2, p3)]
                else:
                    out += [(p0, p1, p3), (p1, p2, p3)]
    return V, np.asarray(out, np.int64)


def facet_edges_longer(v, f, tri_idx, max_edge):
    e = set()
    for t in tri_idx:
        a, b, c = f[t]
        for i, j in ((a, b), (b, c), (c, a)):
            if np.linalg.norm(v[i] - v[j]) > max_edge:
                e.add((int(min(i, j)), int(max(i, j))))
    return e


def op_flat_refined(env, sid, v0, f0, log=print, edges=(3.6, 2.4)):
    """Q216 op_flat for LARGE cut faces: the planar facet (a few big triangles) is first subdivided (conforming edge splits, no T-junction) to edges <= max_edge, then replaced by a cone dome whose height is the
    geodesic distance to the facet's rim (rim vertices do not move) x amp / max; amp 1.5 .. 5 mm; direction outward where the skin leaves >= 1.4 mm, else inward"""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import dijkstra
    ctx = env.ctx
    st = env.audit_state(sid, v0, f0)
    caps = [c for c in st["flat_caps"] if c["area_mm2"] > X.FLAT_AREA_MAX]
    info = dict(op="flat_cut", before=st["flat_caps"], dome=[], refined=True)
    if not caps:
        return None, None, dict(info, why=["no cap above the threshold"])
    best = None
    ext = (v0.min(0), v0.max(0))
    for max_edge, amp in [(me, am) for me in edges for am in (1.5, 2.0, 3.0, 4.0, 5.0)]:
        if best is not None and not best[3]:
            break
        v, f = np.asarray(v0, float).copy(), np.asarray(f0, np.int64).copy()
        dome = []
        groups = X.cap_triangles(v, f)
        todo = []
        for (k, kk), (tri, pos, sgn, area) in groups.items():
            if area <= 40.0 or not (abs(pos - ext[0][k]) < 1.5 or abs(pos - ext[1][k]) < 1.5) or ("xyz"[k] == "x" and abs(pos) < 15.0):
                continue
            todo.append((k, pos, sgn, area))
        for (k, pos, sgn, area) in todo:
            for _ in range(5):                                           # refine the facet (re-found by plane after every pass: the indices change)
                grp = [g for (kk_, _), g in X.cap_triangles(v, f).items() if kk_ == k and abs(g[1] - pos) < 0.3]
                tri = np.concatenate([g[0] for g in grp]) if grp else np.zeros(0, int)
                es = facet_edges_longer(v, f, tri, max_edge)
                if not es:
                    break
                v, f = conforming_split(v, f, es)
            grp = [g for (kk_, _), g in X.cap_triangles(v, f).items() if kk_ == k and abs(g[1] - pos) < 0.3]
            tri = np.concatenate([g[0] for g in grp])
            vi = np.unique(f[tri])
            # rim = facet vertices that also belong to a triangle outside the facet
            outside = np.ones(len(f), bool)
            outside[tri] = False
            rim = np.intersect1d(vi, np.unique(f[outside]))
            if not len(rim):
                continue
            idx = {int(x): n for n, x in enumerate(vi)}
            a = np.array([idx[int(x)] for x in f[tri][:, [0, 1, 2]].ravel()]).reshape(-1, 3)
            ee = np.vstack([a[:, [0, 1]], a[:, [1, 2]], a[:, [2, 0]]])
            w = np.linalg.norm(v[vi][ee[:, 0]] - v[vi][ee[:, 1]], axis=1)
            G = coo_matrix((np.r_[w, w], (np.r_[ee[:, 0], ee[:, 1]], np.r_[ee[:, 1], ee[:, 0]])), shape=(len(vi), len(vi))).tocsr()
            src = np.array([idx[int(x)] for x in rim])
            dist = dijkstra(G, indices=src, min_only=True)
            dist[~np.isfinite(dist)] = 0.0
            h = dist / max(float(dist.max()), 1e-9)
            trial = v[vi].copy()
            trial[:, k] += sgn * amp * h
            sk_in, sk_d = ctx.skin_state(trial)
            direction = sgn if (sk_in >= 100.0 and sk_d >= 1.4) else -sgn
            v[vi, k] += direction * amp * h
            dome.append(dict(axis="xyz"[k], plane_mm=round(pos, 1), area_mm2=round(area, 1), amplitude_mm=amp, outward=bool(direction == sgn), vertices=int(len(vi)), rim_vertices=int(len(rim)), radius_mm=round(float(dist.max()), 1)))
        if not dome:
            continue
        v = ctx.skin_inset(v)
        g, why = env.guards(sid, v, f, v0, f0, X.FLAT_VOL)
        st1 = env.audit_state(sid, v, f)
        left = [c for c in st1["flat_caps"] if c["area_mm2"] > X.FLAT_AREA_MAX]
        if left:
            why = why + [f"{len(left)} flat cap(s) still above {X.FLAT_AREA_MAX:g} mm2 at amplitude {amp}: {[c['area_mm2'] for c in left]}"]
        log(f"      refined dome edge {max_edge} amp {amp}: caps left {[c['area_mm2'] for c in st1['flat_caps']]}, vol x{g['volume_ratio']}, triangles {len(f0)} -> {len(f)}, {why or 'ok'}")
        if best is None or (len(why), len(f)) < (len(best[3]), len(best[1])):
            best = (v, f, dome, why, amp, st1, g)
    if best is None:
        return None, None, dict(info, why=["no facet could be refined"])
    v, f, dome, why, amp, st1, g = best
    return v, f, dict(info, dome=dome, after=st1["flat_caps"], amplitude_mm=amp, guards=g, why=why, triangles=[int(len(f0)), int(len(f))])


# ------------------------------------------------------------------------------------------ the muscle
def process(env, B, sid, cand, log=print):
    it = B.items[B.find(sid)[0]]
    v0, f0 = B.mesh(it)
    res = dict(id=sid, candidate=cand, steps=[], skipped=[], why=[], accepted=False)
    st0 = env.audit_state(sid, v0, f0)
    mv0, mf0 = env.merged(sid, v0, f0)
    caps0 = [c for c in C.flat_cap_rows(mv0, mf0) if c["area_mm2"] > CAP_MIN_MM2]
    res["before"] = dict(volume_cm3=round(C.volume_cm3(v0, f0), 2), flat_caps=[(c["axis"], c["plane_mm"], c["area_mm2"]) for c in caps0], islands=st0["islands"], ends=st0["ends"],
                         length_mm=round(float(env.page.metrics(v0, f0, v0)["length_mm"]), 1))
    v, f = v0, f0
    zfill_new = {}
    # ---- 1 reconnect
    if cand["island"] or st0["islands"]:
        v1, f1, inf = op_bridge_islands(env, sid, v, f, log)
        if v1 is None:
            res["skipped"].append(dict(step="reconnect", why=inf["why"]))
        else:
            g, why = env.guards(sid, v1, f1, v0, f0, BRIDGE_VOL)
            st1 = env.audit_state(sid, v1, f1)
            if st1["islands"] and max(i["gap_mm"] for i in st1["islands"]) > ISLAND_GAP_MIN and max(i["area_share"] for i in st1["islands"]) > ISLAND_SHARE_MIN:
                why.append(f"still an island {max(i['gap_mm'] for i in st1['islands'])} mm away")
            if len(trimesh.Trimesh(v1, f1, process=False).split(only_watertight=False)) != 1:
                why.append("more than one surface piece")
            log(f"  reconnect: vol {g['before']['volume_cm3']} -> {g['after']['volume_cm3']}, islands {len(st0['islands'])} -> {len(st1['islands'])}, {why or 'ok'}")
            if why:
                res["skipped"].append(dict(step="reconnect", why=why, info=inf))
            else:
                v, f = v1, f1
                res["steps"].append(dict(kind="reconnect", info=inf, guards=g))
    # ---- 2 extend (pull the cap's end onto its bone) + 3 dome
    mv, mf = env.merged(sid, v, f)
    caps = [c for c in C.flat_cap_rows(mv, mf) if c["area_mm2"] > CAP_MIN_MM2]
    if caps:
        st = env.audit_state(sid, v, f)
        which = []
        for c in caps:
            en = min(st["ends"], key=lambda e: np.linalg.norm(np.asarray(st["ends"][e]["centre"]) - np.asarray(c["centre"])))
            dist = float(np.linalg.norm(np.asarray(st["ends"][en]["centre"]) - np.asarray(c["centre"])))
            if dist <= CAP_END_RADIUS_MM and st["ends"][en]["min_any_bone_mm"] > X.END_GOAL_MM and en not in which:
                which.append(en)
        res["cap_ends"] = dict(ends_to_pull=which, caps=[(c["axis"], c["plane_mm"], c["area_mm2"]) for c in caps])
        if which:
            v1, f1, inf = X.op_ends(env, sid, which, v, f, log)
            if v1 is None or inf.get("why"):
                res["skipped"].append(dict(step="extend", why=(inf or {}).get("why") or (inf or {}).get("skipped"), pulled=(inf or {}).get("pulled"), skipped_ends=(inf or {}).get("skipped")))
            else:
                zfn = inf.pop("zfill_new", {})
                inf.pop("why", None)
                v, f = v1, f1
                zfill_new.update(zfn)
                res["steps"].append(dict(kind="extend", info=inf))
        v1, f1, inf = op_flat_refined(env, sid, v, f, log)
        if v1 is None or inf.get("why"):
            tried = (inf or {}).get("why")
            v2, f2, inf2 = X.op_flat(env, sid, v, f, log)                 # the Q216 shallow dome on the existing triangles (small facets)
            if v2 is not None and not inf2.get("why"):
                v1, f1, inf = v2, f2, inf2
                inf["refined_attempt_failed"] = tried
            elif v1 is not None or v2 is not None:
                inf = inf if v1 is not None else inf2
        if v1 is None:
            res["skipped"].append(dict(step="dome", why=(inf or {}).get("why")))
        elif inf.get("why"):
            res["skipped"].append(dict(step="dome", why=inf["why"], attempted=inf.get("amplitude_mm")))
        else:
            inf.pop("why", None)
            v, f = v1, f1
            res["steps"].append(dict(kind="dome", info=inf))
    if not res["steps"]:
        res["why"] = [s["why"] for s in res["skipped"]]
        return res
    # ---- cumulative guards against the base mesh
    g, why = env.guards(sid, v, f, v0, f0, CUM_VOL, CUM_LEN, seam=False)
    res["cumulative_guards"] = g
    if why:
        res["why"] = why
        res["steps_discarded"] = [s["kind"] for s in res["steps"]]
        res["steps"] = []
        return res
    mv1, mf1 = env.merged(sid, v, f)
    st1 = env.audit_state(sid, v, f)
    caps1 = [c for c in C.flat_cap_rows(mv1, mf1) if c["area_mm2"] > CAP_MIN_MM2]
    res["after"] = dict(volume_cm3=round(C.volume_cm3(v, f), 2), flat_caps=[(c["axis"], c["plane_mm"], c["area_mm2"]) for c in caps1], islands=st1["islands"], ends=st1["ends"],
                        length_mm=round(float(env.page.metrics(v, f, v0)["length_mm"]), 1))
    res["accepted"] = True
    res["v"], res["f"], res["zfill_new"] = v, f, zfill_new
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--body", required=True, choices=["m", "f"])
    ap.add_argument("--shard", default="0/1")
    ap.add_argument("--only", default="")
    ap.add_argument("--cache", default="")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--src", default="", help="bundle dir (default: the Q217 / Q216 source; the veins / duplicates stage output when given)")
    a = ap.parse_args()
    body = BODIES[a.body]
    cl = candidates(a.body)
    if a.list:
        for c in cl:
            print(c["id"], c["caps"], c["island"])
        print(len(cl))
        return
    si, sn = [int(x) for x in a.shard.split("/")]
    only = [x for x in a.only.split(",") if x]
    cache = Path(a.cache) if a.cache else SCRATCH / f"muscles_{a.body}"
    cache.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    B = Bundle(a.src or str(body["src_bundle"]))
    env = X.Env(B)
    log = lambda *x: print(*x, flush=True)
    log(f"{a.body}: context ready [{time.time() - t0:.0f} s], {len(cl)} candidates, shard {si}/{sn}")
    for n, c in enumerate(cl):
        sid = c["id"]
        if n % sn != si or (only and sid not in only):
            continue
        out = cache / f"{sid}.pkl"
        if out.exists():
            continue
        if len(B.find(sid)) != 1:
            why = "not an entry of the bundle (merged view of a Z-fill piece?)" if not B.find(sid) else f"the id occurs {len(B.find(sid))} times in the bundle (ambiguous: not touched)"
            out.write_bytes(pickle.dumps(dict(id=sid, candidate=c, accepted=False, why=[why], steps=[], skipped=[])))
            continue
        t1 = time.time()
        log(f"[{n}/{len(cl)}] {sid} caps {c['caps']} island {c['island']}")
        try:
            r = process(env, B, sid, c, log)
        except Exception as e:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            r = dict(id=sid, candidate=c, accepted=False, why=[f"exception: {type(e).__name__}: {e}"], steps=[], skipped=[])
        out.write_bytes(pickle.dumps(r))
        log(f"   -> {'ACCEPTED ' + str([s['kind'] for s in r['steps']]) if r['accepted'] else 'kept: ' + str(r['why'])[:300]}  [{time.time() - t1:.0f} s]")
    log(f"done [{time.time() - t0:.0f} s]")


if __name__ == "__main__":
    main()
