#!/usr/bin/env python3
"""Q209 READ-ONLY: measure the male Z-fitted page's (build/q208/viewer_zan_vhm) forearm skin vs trunk / thigh skin crossing (Q208: 472 deep face pairs).
Reads the geometry the page embeds. Output data/derived/Q209_forearm_trunk.json.   python3 scripts/zanatomy/q209_forearm_trunk.py"""
import json, sys
from pathlib import Path
import numpy as np
from scipy.spatial import cKDTree
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
import scripts.zanatomy.q209_paths  # noqa: F401,E402
from scripts.zanatomy.q198_load import load  # noqa: E402
from scripts.zanatomy.q198_core import Grid, surf_points, tri_area  # noqa: E402
from scripts.zanatomy import q207_geom as G  # noqa: E402

TUBE = ("anterior_region_of_forearm", "posterior_region_of_forearm", "lateral_border_of_forearm", "medial_border_of_forearm", "anterior_region_of_wrist", "posterior_region_of_wrist")
ELBOW = ("anterior_region_of_elbow", "posterior_region_of_elbow", "cubital_fossa")
NB = ("palm", "dorsum_of_hand", "radial_foveola", "anterior_region_of_arm", "posterior_region_of_arm", "deltoid_region", "dorsal_surfaces_of_digits_of_hand", "palmar_surfaces_of_digits_of_hand",
      "nail_plate", "perionyx", "medial_bicipital_groove", "lateral_bicipital_groove", "lateral_region_of_arm", "medial_region_of_arm")
Q = lambda x: round(float(x), 2)


def pct(a, q):
    return Q(np.percentile(a, q)) if len(a) else None


def main():
    S = load("z_male_fit")
    by = {s["id"]: s for s in S}
    skin = {s["id"]: s for s in S if s["sys"] == "skin"}
    base = lambda i: i[len("zan_skin_"):-2]
    fore = {i for i in skin if base(i) in TUBE + ELBOW}
    out = {"page": "build/q208/viewer_zan_vhm", "n_skin_patches": len(skin), "n_forearm_elbow_patches": len(fore)}
    # --- candidate patches: forearm + every other patch whose bbox meets a forearm bbox (+20 mm); nail/perionyx excluded as in Q208
    fv = np.concatenate([skin[i]["v"] for i in fore]); lo, hi = fv.min(0) - 20, fv.max(0) + 20
    cand = {i for i, s in skin.items() if "nail_plate" not in i and "perionyx" not in i and (s["v"].max(0) >= lo).all() and (s["v"].min(0) <= hi).all()} | fore
    ids = sorted(cand)
    Vc, F, ow, nm = G.concat({i: (skin[i]["v"], skin[i]["f"]) for i in ids})
    pr = G.intersecting_pairs(Vc, F, ow)
    dd = G.pair_depth(Vc, F, pr) if len(pr) else np.zeros(0)
    cat = lambda a, b: ("fore_fore" if (a in fore and b in fore) else "fore_vs_arm_hand" if ((a in fore) != (b in fore) and base(b if a in fore else a) in NB) else "fore_vs_trunk_thigh" if (a in fore) != (b in fore) else "other")
    rows = []
    for (x, y), d in zip(pr, dd):
        a, b = nm[ow[x]], nm[ow[y]]
        rows.append((a, b, float(d), x, y, cat(a, b)))
    deep = [r for r in rows if r[2] > 2]
    out["crossings_page_decode"] = {"candidates": len(ids), "face_pairs": len(rows), "deep_gt2": len(deep), "deep_gt4": sum(r[2] > 4 for r in rows),
                                    "by_category_deep_gt2": {c: sum(1 for r in deep if r[5] == c) for c in ("fore_fore", "fore_vs_arm_hand", "fore_vs_trunk_thigh", "other")}}
    ft = [r for r in deep if r[5] == "fore_vs_trunk_thigh"]
    d_ft = np.array([r[2] for r in ft])
    pairs = {}
    for a, b, d, x, y, c in ft:
        k = tuple(sorted((a[9:], b[9:]))); pairs.setdefault(k, []).append(d)
    out["forearm_vs_trunk"] = {"deep_pairs_gt2": len(ft), "depth_mm": {"median": pct(d_ft, 50), "p90": pct(d_ft, 90), "max": Q(d_ft.max()) if len(d_ft) else None},
                               "deep_gt4": int((d_ft > 4).sum()), "deep_gt8": int((d_ft > 8).sum()), "deep_gt12": int((d_ft > 12).sum()),
                               "patch_pairs": [{"pair": list(k), "n": len(v), "max_mm": Q(max(v)), "median_mm": Q(np.median(v))} for k, v in sorted(pairs.items(), key=lambda kv: -len(kv[1]))[:14]]}
    # unique faces involved + their area
    area = tri_area(Vc, F)
    fa = {r[3] for r in ft} | {r[4] for r in ft}
    tr_faces = [f_ for f_ in fa if nm[ow[f_]] not in fore]; fo_faces = [f_ for f_ in fa if nm[ow[f_]] in fore]
    out["forearm_vs_trunk"]["footprint_mm2"] = {"trunk_thigh_faces": len(tr_faces), "trunk_thigh_area": Q(area[tr_faces].sum()), "forearm_faces": len(fo_faces), "forearm_area": Q(area[fo_faces].sum())}
    cen = np.array([Vc[F[f_]].mean(0) for f_ in fa])
    out["forearm_vs_trunk"]["centroid_of_contact_mm"] = [Q(c) for c in cen.mean(0)] if len(cen) else None
    # --- per forearm axis: tube-radius model from the forearm patches
    res = {}
    for sd in ("l", "r"):
        rb = np.concatenate([by[f"radius_{sd}"]["v"], by[f"ulna_{sd}"]["v"]])
        c0 = rb.mean(0); u, s, vt = np.linalg.svd(rb - c0, full_matrices=False); ax = vt[0]
        t_ = (rb - c0) @ ax
        # orient: distal = hand side (palm patch centroid)
        palm = skin[f"zan_skin_palm_{sd}"]["v"].mean(0)
        if (palm - c0) @ ax < 0: ax = -ax; t_ = -t_
        tmin, tmax = float(t_.min()), float(t_.max())
        ref = np.cross(ax, [0, 0, 1.0]); ref /= np.linalg.norm(ref); ref2 = np.cross(ax, ref)
        cyl = lambda P: (((P - c0) @ ax), np.arctan2((P - c0) @ ref2, (P - c0) @ ref), np.linalg.norm((P - c0) - np.outer((P - c0) @ ax, ax), axis=1))
        fv_ = np.concatenate([skin[i]["v"] for i in fore if i.endswith("_" + sd) and base(i) in TUBE])
        t, th, r = cyl(fv_)
        nb_t, nb_a = 28, 24
        edges = np.linspace(tmin - 10, tmax + 10, nb_t + 1)
        R_out = np.full((nb_t, nb_a), np.nan)
        for i in range(nb_t):
            m = (t >= edges[i]) & (t < edges[i + 1])
            ab = np.minimum(((th[m] + np.pi) / (2 * np.pi) * nb_a).astype(int), nb_a - 1)
            for j in range(nb_a):
                if (ab == j).any(): R_out[i, j] = r[m][ab == j].max()
        # trunk / thigh skin vertices (patches that cross, plus every non-arm patch near the forearm)
        trunk_ids = [i for i in ids if i not in fore and base(i) not in NB]
        tv = np.concatenate([skin[i]["v"] for i in trunk_ids]); tid = np.concatenate([[i] * len(skin[i]["v"]) for i in trunk_ids])
        tt, tth, tr_ = cyl(tv)
        ti = np.clip(np.floor((tt - (tmin - 10)) / (tmax + 20 - tmin) * nb_t).astype(int), 0, nb_t - 1)
        ta = np.minimum(((tth + np.pi) / (2 * np.pi) * nb_a).astype(int), nb_a - 1)
        ok = (tt > tmin) & (tt < tmax) & (tr_ < 120)
        Ro = R_out[ti, ta]
        depth = np.where(ok & np.isfinite(Ro), Ro - tr_, -1e9)
        sel = depth > 0
        res[sd] = {"axis_len_mm": Q(tmax - tmin), "forearm_outer_radius_median_mm": Q(np.nanmedian(R_out)),
                   "trunk_skin_vertices_inside_forearm_tube": int((depth > 2).sum()), "gt5mm": int((depth > 5).sum()), "gt10mm": int((depth > 10).sum()), "gt15mm": int((depth > 15).sum()),
                   "depth_mm": {"median": pct(depth[depth > 2], 50), "p90": pct(depth[depth > 2], 90), "max": Q(depth[depth > 2].max()) if (depth > 2).any() else None},
                   "by_patch": {k: int(((tid == k) & (depth > 2)).sum()) for k in sorted(set(tid[depth > 2]))}}
        res[sd]["_sel"] = (tid[depth > 2], tv[depth > 2], depth[depth > 2])
        res[sd]["_ax"] = (c0, ax, tmin, tmax)
    # --- deep tissue: forearm bones / muscles vs trunk / thigh muscles+bones (solid overlap, 2 mm), and margins under each skin
    reg_path = REPO / "build/q209_raw/Q204_regions_z_male_fit.json"
    reg = {r["id"]: r["region"] for r in json.loads(reg_path.read_text())["rows"]} if reg_path.exists() else {}
    deep_res = {}
    for sd in ("l", "r"):
        c0, ax, tmin, tmax = res[sd]["_ax"]
        rel = [s for s in S if s["sys"] in ("bone", "muscle") and s["side"] in (sd, "m") and len(s["v"])]
        near = lambda s: bool(((s["v"] - c0) @ ax).min() > tmin - 60 and ((s["v"] - c0) @ ax).max() < tmax + 60 and np.linalg.norm((s["v"].mean(0) - c0) - ((s["v"].mean(0) - c0) @ ax) * ax) < 90)
        fa_ = [s for s in rel if near(s) and reg.get(s["id"]) in ("arm_elbow_forearm", "wrist_hand")]
        tr_ = [s for s in S if s["sys"] in ("bone", "muscle") and reg.get(s["id"]) in ("thorax", "abdomen_pelvis", "hip", "thigh") and s["side"] in (sd, "m") and len(s["v"])]
        allv = np.concatenate([s["v"] for s in fa_ + tr_]); g = Grid(allv.min(0) - 4, allv.max(0) + 4, 2.0)
        Fo = np.zeros(g.shape, bool); Tr = np.zeros(g.shape, bool)
        for s in fa_: Fo |= g.solid(s["v"], s["f"])
        for s in tr_: Tr |= g.solid(s["v"], s["f"])
        ov = Fo & Tr
        # offenders
        offs = {}
        for s in fa_:
            m = g.solid(s["v"], s["f"]) & Tr
            if m.any(): offs[s["id"]] = int(m.sum())
        offt = {}
        for s in tr_:
            m = g.solid(s["v"], s["f"]) & Fo
            if m.any(): offt[s["id"]] = int(m.sum())
        # nearest surface distance between the two sets
        P1 = np.concatenate([surf_points(s["v"], s["f"], 2.5, cap=20000) for s in fa_]); P2 = np.concatenate([surf_points(s["v"], s["f"], 2.5, cap=20000) for s in tr_])
        dmin, _ = cKDTree(P2).query(P1); 
        deep_res[sd] = {"n_forearm_structures": len(fa_), "n_trunk_thigh_structures": len(tr_), "deep_overlap_mm3": int(ov.sum() * 8), "forearm_structures_in_trunk_tissue": dict(sorted(offs.items(), key=lambda kv: -kv[1])[:6]),
                        "trunk_structures_in_forearm_tissue": dict(sorted(offt.items(), key=lambda kv: -kv[1])[:6]), "min_surface_gap_forearm_to_trunk_tissue_mm": Q(dmin.min()),
                        "forearm_deep_points_within_5mm_of_trunk_tissue": int((dmin < 5).sum()), "of": len(P1)}
        # skin margins: depth of the crossing trunk-skin vertices over trunk tissue, and forearm outer skin over forearm tissue
        tid, tv, dep = res[sd]["_sel"]
        if len(tv):
            tree = cKDTree(P2)
            dm, _ = tree.query(tv)
            deep_res[sd]["trunk_skin_over_tissue_margin_mm"] = {"median": pct(dm, 50), "p10": pct(dm, 10), "min": Q(dm.min()), "needed_median_to_clear": pct(dep, 50), "needed_p90": pct(dep, 90)}
            fo_skin = np.concatenate([skin[i]["v"] for i in fore if i.endswith("_" + sd)])
            P1t = cKDTree(P1)
            # forearm skin vertices near the contact (within 25 mm of the offending trunk vertices)
            near_fs = fo_skin[cKDTree(tv).query(fo_skin)[0] < 25]
            if len(near_fs):
                d1, _ = P1t.query(near_fs)
                deep_res[sd]["forearm_skin_over_tissue_margin_mm"] = {"n": len(near_fs), "median": pct(d1, 50), "p10": pct(d1, 10), "min": Q(d1.min())}
    for sd in res:
        res[sd].pop("_sel"); res[sd].pop("_ax")
    out["tube_depth_of_trunk_skin_by_side"] = res
    out["deep_tissue_by_side"] = deep_res
    (REPO / "data/derived/Q209_forearm_trunk.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out, indent=1)[:6000])


if __name__ == "__main__":
    main()
