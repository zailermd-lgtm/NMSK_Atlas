#!/usr/bin/env python3
"""Q243 (3): is the Z-derived spine of Combined female good enough to carry the HRA nucleus pulposus / spinal cord? Fits every HRA vertebra to the Z vertebra of the same name / rank (rigid + uniform scale,
as for the own page) and reports the residuals; the lumbar column is tried with both rank mappings because the Z-Anatomy spine has FIVE lumbar vertebrae and the HRA / the Visible Human female SIX.
    python3 scripts/anatomy/q243/zspine_eval.py PAGE_DIR STEM -o data/derived/Q243_spine_comb_f.json"""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np, trimesh
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "anatomy"))
from scripts.anatomy.q243 import spine as SP  # noqa: E402
from scripts.zanatomy import q205_pages as P5  # noqa: E402


def main(page_dir, stem, out):
    np.random.seed(0)
    man, blob = P5.load_page(Path(page_dir), stem)
    S = P5.decode(man, blob)
    zid = {"C1": "zan_atlas_c1", "C2": "zan_axis_c2", **{f"C{i}": f"zan_vertebra_c{i}" for i in range(3, 8)}, **{f"T{i}": f"zan_vertebra_t{i}" for i in range(1, 13)}, **{f"L{i}": f"zan_vertebra_l{i}" for i in range(1, 6)}}
    zm = {lv: trimesh.Trimesh(S[i]["v"], S[i]["f"], process=False) for lv, i in zid.items() if i in S and len(S[i]["f"])}
    hv = SP.hra_vertebrae()
    hs = {lv: trimesh.Trimesh(v, f, process=False).sample(5000) for lv, (v, f) in hv.items()}
    ps = {lv: m.sample(20000) for lv, m in zm.items()}
    res = {}
    for variant, lummap in (("HRA L1-L5 <-> Z l1-l5", {f"L{i}": f"L{i}" for i in range(1, 6)}), ("HRA L2-L6 <-> Z l1-l5", {f"L{i + 1}": f"L{i}" for i in range(1, 6)})):
        pairs = [(lv, lv) for lv in zm if lv[0] in "CT"] + [(h, z) for h, z in lummap.items()]
        allh = np.vstack([hs[h] for h, _ in pairs]); allp = np.vstack([ps[z] for _, z in pairs])
        tree = cKDTree(allp)
        best = None
        for dy in (-20, 0, 20):
            s, R, t, d = SP._icp(allh, tree, allp, s0=0.95, t0=allp.mean(0) - 0.95 * allh.mean(0) + np.array([0, dy, 0.]), iters=60, trim=0.7)
            if best is None or np.median(d) < best[0]:
                best = (float(np.median(d)), s, R, t)
        _, sG, RG, tG = best
        rows = {}
        for h, z in pairs:
            tr = cKDTree(ps[z])
            s, R, t, d = SP._icp(hs[h], tr, ps[z], s0=sG, R0=RG, t0=tG, iters=50, trim=0.85)
            dd = tr.query(s * hs[h] @ R.T + t)[0]
            rows[f"{h}->{z}"] = dict(scale=round(float(s), 3), median_mm=round(float(np.median(dd)), 2), p90_mm=round(float(np.quantile(dd, .9)), 2),
                                     centroid_offset_mm=round(float(np.linalg.norm((s * hs[h].mean(0) @ R.T + t) - ps[z].mean(0))), 1))
        med = [r["median_mm"] for r in rows.values()]
        lum = [r for k, r in rows.items() if k.startswith("L")]
        res[variant] = dict(global_scale=round(float(sG), 3), n_levels=len(rows), median_of_level_medians_mm=round(float(np.median(med)), 2), max_level_median_mm=round(float(max(med)), 2),
                            lumbar_median_of_medians_mm=round(float(np.median([r["median_mm"] for r in lum])), 2), lumbar_max_centroid_offset_mm=round(float(max(r["centroid_offset_mm"] for r in lum)), 1), levels=rows)
        print(variant, res[variant]["median_of_level_medians_mm"], res[variant]["max_level_median_mm"], res[variant]["lumbar_median_of_medians_mm"], flush=True)
    own = [k for k in ("zan_nucleus_pulposus_c2_c3", "zan_spinal_cord", "zan_white_matter_of_spinal_cord") if k in S]
    doc = dict(page=str(page_dir), z_lumbar_vertebrae=sum(1 for lv in zm if lv[0] == "L"), hra_lumbar_vertebrae=6, variants=res,
               z_page_already_has=dict(nucleus_pulposus=sorted(i for i in S if i.startswith("zan_nucleus_pulposus_")), spinal_cord_parts=sorted(i for i in S if "spinal_cord" in i)))
    Path(out).write_text(json.dumps(doc, indent=1) + "\n")


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0], a[1], a[a.index("-o") + 1])
