#!/usr/bin/env python3
"""Q208 report stage: before (Q207 page) -> after (Q208 state) numbers of the skin of one page; written to data/derived/Q208_report_<which>.json and build/q208/<which>_report.pkl (card badges use it).
    python3 scripts/zanatomy/q208_report.py male|female [--zone]      (--zone: structure containment over the whole forearm + hand, slow)"""
from __future__ import annotations

import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q207_core as C7  # noqa: E402
from scripts.zanatomy import q208_core as K  # noqa: E402
from scripts.zanatomy import q208_eval as E  # noqa: E402
from scripts.zanatomy import q208_refit as RF  # noqa: E402

ELBOW_FOREARM = K.TUBE + K.ELBOW


def final_state(which):
    return pickle.load(open(K.state_path(which, "uro"), "rb"))[0]


def group_of(i):
    n = i[len("zan_skin_"):-2]
    if n in K.TUBE:
        return "forearm / wrist (re-warped)"
    if n in K.ELBOW:
        return "elbow / cubital (refit)"
    if n in ("urogenital_region", ):
        return "urogenital (rim weld)"
    return "neighbour (weld / re-seat)"


def forearm_sections(pg, V, side, step=3.0):
    """sections of the displayed limb skin normal to the forearm axis, from 25 mm below the elbow joint line to the wrist: the outline must be closed around the axis point and cut itself nowhere;
    -> dict(slices, closed, crossings (total segment crossings of the section polylines, adjacent segments excluded), radius_step_max)"""
    import trimesh
    import shapely
    from shapely.geometry import LineString, Point
    from shapely.ops import polygonize, unary_union
    s = "_" + side
    W = pg.wrist()[side]
    rad, ulna = pg.v("radius" + s), pg.v("ulna" + s)
    a = np.linalg.svd(np.vstack([rad, ulna]) - np.vstack([rad, ulna]).mean(0), full_matrices=False)[2][0]
    if (W - rad.mean(0)) @ a < 0:
        a = -a
    elb = ulna[np.argmax((ulna - W) @ (-a))]
    ids = [i for i in pg.skin_ids if i.endswith(s) and any(k in i for k in K.TUBE + K.ELBOW)]
    Vs, Fs, off = [], [], 0
    for i in ids:
        Vs.append(V[i])
        Fs.append(pg.f(i) + off)
        off += len(V[i])
    mesh = trimesh.Trimesh(np.vstack(Vs), np.vstack(Fs), process=False)
    L = np.linalg.norm(W - elb)
    u = np.cross(a, [1, 0, 0])
    u /= np.linalg.norm(u)
    w = np.cross(a, u)
    rows = []
    for t in np.arange(0.1 * L, L, step):
        o = elb + (W - elb) / L * t
        seg = trimesh.intersections.mesh_plane(mesh, a, o)
        if len(seg) == 0:
            rows.append((t, 0, 0, np.nan))
            continue
        s2 = np.stack([((seg - o) @ u), ((seg - o) @ w)], -1)
        # centre of the section = the forearm bone centre: the axis point o; crossings among the polylines
        lines = [LineString(x) for x in s2 if np.linalg.norm(x[0] - x[1]) > 1e-6]
        union = unary_union([shapely.set_precision(x, 0.05) for x in lines])
        polys = [p for p in polygonize(union) if p.contains(Point(0, 0))]
        # crossing count: pairs of non-touching segments that properly cross
        cr = 0
        arr = s2
        lo, hi = arr.min(1), arr.max(1)
        for i in range(len(arr)):
            m = (lo[:, 0] <= hi[i, 0]) & (hi[:, 0] >= lo[i, 0]) & (lo[:, 1] <= hi[i, 1]) & (hi[:, 1] >= lo[i, 1])
            for j in np.flatnonzero(m):
                if j <= i:
                    continue
                if np.linalg.norm(arr[i][:, None] - arr[j][None], axis=2).min() < 0.05:
                    continue                    # shares a vertex (adjacent)
                if lines[i].crosses(lines[j]):
                    cr += 1
        r = float(np.sqrt(max(p.area for p in polys) / np.pi)) if polys else np.nan
        rows.append((t, 1 if polys else 0, cr, r))
    r = np.array(rows)
    rr = r[~np.isnan(r[:, 3]), 3]
    return dict(slices=int(len(r)), closed=int(r[:, 1].sum()), segment_crossings=int(r[:, 2].sum()), slices_with_crossings=int((r[:, 2] > 0).sum()), radius_step_max_mm_per_3mm=round(float(np.abs(np.diff(rr)).max()), 2) if len(rr) > 1 else None)


def run(which, zone=False, log=print):
    pg, raw = K.load(which)
    V0 = {i: pg.v(i) for i in pg.skin_ids}
    V1 = final_state(which)
    moved = sorted(i for i in V1 if np.linalg.norm(V1[i] - V0[i], axis=1).max() > 0.05)
    log(f"[{which}] {len(moved)} skin patches changed")
    rep = {"page": which, "moved": {}, "groups": {}}
    q = E.quality(pg, V1, V0, raw, moved)
    own = None
    from scripts.zanatomy.q207_inflate import OwnSkin
    own = OwnSkin(which)
    for i in moved:
        d = np.linalg.norm(V1[i] - V0[i], axis=1)
        s0, s1 = own.sd(V0[i]), own.sd(V1[i])
        rep["moved"][i] = dict(group=group_of(i), max_move_mm=round(float(d.max()), 2), mean_move_mm=round(float(d.mean()), 2), vertices=len(d), vertices_moved_gt0_3mm=int((d > 0.3).sum()), **q[i],
                               outside_own_skin_gt2mm_pct=[round(float((s0 > 2).mean() * 100), 2), round(float((s1 > 2).mean() * 100), 2)])
    # slab twin distance (3.0 mm in the source): median / p95 before -> after
    from scipy.spatial import cKDTree
    for i in moved:
        v0r = raw.v(i)
        d, k = cKDTree(v0r).query(v0r, k=2)
        tw = k[:, 1]
        t0 = np.linalg.norm(V0[i] - V0[i][tw], axis=1)
        t1 = np.linalg.norm(V1[i] - V1[i][tw], axis=1)
        rep["moved"][i]["twin_distance_mm"] = {"median": [round(float(np.median(t0)), 2), round(float(np.median(t1)), 2)], "p95": [round(float(np.percentile(t0, 95)), 2), round(float(np.percentile(t1, 95)), 2)]}
    # skin sheet crossings (the Q207 id set + moved)
    ids = E.crossing_ids(pg, extra=moved)
    rep["crossings"] = {"patches_checked": len(ids)}
    pairs = {}
    for tag, VV in (("z_source", {i: raw.v(i) for i in ids}), ("q207", V0), ("q208", V1)):
        r, deep = E.crossings(pg, VV, ids)
        rep["crossings"][tag] = r
        pairs[tag] = deep
    inner_names = K.TUBE + K.ELBOW

    def cat(k):
        a, b = (x[len("zan_skin_"):-2] for x in k)
        ia, ib = a in inner_names, b in inner_names
        if ia and ib:
            return "forearm_wrist_elbow_internal"
        if ia or ib:
            o = b if ia else a
            return "forearm_wrist_elbow_vs_arm_hand" if o in K.ARM_NB + K.WRIST_NB + ("deltoid_region", "radial_foveola", "dorsal_surfaces_of_digits_of_hand", "palmar_surfaces_of_digits_of_hand", "nail_plate", "perionyx", "medial_bicipital_groove") else "forearm_wrist_elbow_vs_trunk_thigh"
        return "other_pairs"
    for tag in pairs:
        cc = {}
        for k, c in pairs[tag].items():
            cc[cat(k)] = cc.get(cat(k), 0) + c
        rep["crossings"][tag]["deep_pairs_by_category"] = cc
    rep["crossings"]["top_pairs_q208"] = [[a[9:], b[9:], c] for (a, b), c in sorted(pairs["q208"].items(), key=lambda kv: -kv[1])[:12]]
    rep["crossings"]["top_pairs_q207"] = [[a[9:], b[9:], c] for (a, b), c in sorted(pairs["q207"].items(), key=lambda kv: -kv[1])[:12]]
    log(f"   crossings {rep['crossings']['z_source']['depth_gt_2mm']} (Z) / {rep['crossings']['q207']['depth_gt_2mm']} (Q207) -> {rep['crossings']['q208']['depth_gt_2mm']} (Q208)")
    # forearm sections normal to the forearm axis
    rep["forearm_sections"] = {}
    for side in "lr":
        a = forearm_sections(pg, V0, side)
        b = forearm_sections(pg, V1, side)
        z = forearm_sections(raw, {i: raw.v(i) for i in raw.skin_ids}, side)
        rep["forearm_sections"][side] = {"z_source": z, "q207": a, "q208": b}
        log(f"   forearm sections {side}: {a} -> {b}")
    from scripts.zanatomy import q208_build as B
    rep["bones_not_enclosed_elbow_region"] = {}
    for side in "lr":
        a, n0 = B.bones_poking(pg, raw, V0, side)
        b, n1 = B.bones_poking(pg, raw, V1, side)
        rep["bones_not_enclosed_elbow_region"][side] = {"q207": a, "q208": b, "bone_vertices": n0}
    log(f"   bones not enclosed at the elbow {rep['bones_not_enclosed_elbow_region']}")
    # seams (border steps) before / after for all patches
    from scripts.zanatomy import q199_elbow as EL
    sids = sorted(i for i in pg.skin_ids if i in raw.S)
    rawd = {i: raw.v(i) for i in sids}
    rows = {}
    for tag, VV in (("q207", V0), ("q208", V1)):
        by = {i: {"v": VV[i], "f": pg.f(i), "cat": "skin"} for i in sids}
        rows[tag] = EL.skin_seam_rows(by, rawd, None, sids)
    for i in moved:
        sb = max([r["step_mm_max"] for r in rows["q207"] if i in (r["a"], r["b"])] or [0])
        sa = max([r["step_mm_max"] for r in rows["q208"] if i in (r["a"], r["b"])] or [0])
        rep["moved"][i]["seam_step_max_mm"] = [round(sb, 2), round(sa, 2)]
    rep["seams"] = {t: {"steps_gt_2mm": int(sum(r["step_mm_max"] > 2 for r in rr)), "steps_gt_3mm": int(sum(r["step_mm_max"] > 3 for r in rr)), "max_step_mm": round(max(r["step_mm_max"] for r in rr), 2),
                        "worst": [[r["a"][9:], r["b"][9:], r["step_mm_max"]] for r in sorted(rr, key=lambda r: -r["step_mm_max"])[:5]]} for t, rr in rows.items()}
    log(f"   seams {rep['seams']['q207']['steps_gt_3mm']} -> {rep['seams']['q208']['steps_gt_3mm']} steps > 3 mm; max {rep['seams']['q207']['max_step_mm']} -> {rep['seams']['q208']['max_step_mm']}")
    # outward displacement of the outer sheet along the skin normal (what the needle tool's skin depth sees)
    out = {}
    bones = {s: K.side_bones(raw, s) for s in "lr"}
    for i in moved:
        side = i[-1]
        S = RF.Slabs({i: raw.v(i)}, {i: pg.f(i)}, [i])
        o = S.outer_flags(bone_pts=bones[side]) if side in "lr" else np.ones(len(S.V), bool)
        d = V1[i][o] - V0[i][o]
        out[i] = dict(outer_vertices=int(o.sum()), mean_move_mm=round(float(np.linalg.norm(d, axis=1).mean()), 2), max_move_mm=round(float(np.linalg.norm(d, axis=1).max()), 2))
    rep["outer_sheet_move"] = out
    # urogenital numbers (male)
    if which == "male":
        from scripts.zanatomy import q207_uro as U7
        ids_u = list(U7.IDS)
        vol = lambda VV, i: round(U7.volume(VV[i], pg.f(i)))
        rep["urogenital"] = {"volume_mm3": {i[-1]: [vol(V0, i), vol(V1, i), vol({k: raw.v(k) for k in ids_u}, i)] for i in ids_u}}
    pickle.dump(rep, open(K.state_path(which, "report"), "wb"))
    (REPO / "data" / "derived" / f"Q208_report_{which}.json").write_text(json.dumps(rep, indent=1, default=float))
    return rep


if __name__ == "__main__":
    run(sys.argv[1])
