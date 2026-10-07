"""Q199: the numbers of the PROJECT_STATE entry from the committed build report + audit (no recomputation).

    python3 scripts/zanatomy/q199_summary.py [--build data/derived/Q199_zan_female_q199_build.json] [--audit data/derived/Q199_elbow_audit.json]
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]


def distortion(structs: dict) -> dict:
    out = {}
    for cat in ("muscle", "vessel", "nerve", "all"):
        rows = [s for s in structs.values() if cat == "all" or s["cat"] == cat]
        if not rows:
            continue
        g = lambda key, w: [r[w].get(key) for r in rows if r[w].get(key) is not None]
        st_b, st_a = g("stretch_area_outside_0.67_1.5_pct", "before"), g("stretch_area_outside_0.67_1.5_pct", "after")
        fo_b, fo_a = g("folded_edges_pct", "before"), g("folded_edges_pct", "after")
        out[cat] = {"n": len(rows), "stretched_triangles_pct_mean": [round(float(np.mean(st_b)), 1), round(float(np.mean(st_a)), 1)],
                    "structures_gt_25pct_stretched": [int(sum(x > 25 for x in st_b)), int(sum(x > 25 for x in st_a))],
                    "folded_edges_pct_mean": [round(float(np.mean(fo_b)), 2), round(float(np.mean(fo_a)), 2)],
                    "outside_her_skin_pct_mean": [round(float(np.mean(g("outside_her_skin_pct", "before"))), 2), round(float(np.mean(g("outside_her_skin_pct", "after"))), 2)],
                    "inside_displayed_bones_pct_mean": [round(float(np.mean(g("inside_z_bone_pct", "before"))), 2), round(float(np.mean(g("inside_z_bone_pct", "after"))), 2)]}
        if cat == "muscle":
            vb, va = g("volume_ratio_vs_source", "before"), g("volume_ratio_vs_source", "after")
            out[cat]["volume_ratio_outside_0.65_1.5"] = [int(sum(not 0.65 <= x <= 1.5 for x in vb)), int(sum(not 0.65 <= x <= 1.5 for x in va))]
    return out


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--build", default=str(REPO / "data" / "derived" / "Q199_zan_female_q199_build.json"))
    ap.add_argument("--audit", default=str(REPO / "data" / "derived" / "Q199_elbow_audit.json"))
    a = ap.parse_args(argv)
    rep = json.loads(Path(a.build).read_text())["q199"]
    st = rep["structures"]
    print("moved structures:", len(st), dict(Counter(s["cat"] for s in st.values())), "| ladder:", dict(Counter(s["ladder"] for s in st.values())))
    print("moved ids (incl. bones, skin patches, shipped-mesh separation):", len(rep["moved_ids"]))
    for side in ("l", "r"):
        sub = {k: v for k, v in st.items() if k.endswith("_" + side) or "_" + side + "_" in k}
        print(f"distortion {side}:", json.dumps(distortion(sub)))
    big = sorted(((s["max_move_mm"], k) for k, s in st.items()), reverse=True)[:8]
    print("largest moves:", big)
    print("bones:", rep["bones"])
    for side in ("left", "right"):
        c = rep["chain"][side]
        print(side, "chain:", json.dumps({k: c[k] for k in c if k in ("params", "shaft_centre_residual_mm", "elbow_blob_evidence_mm", "label_recall_mm_mean", "joint_before", "joint_after")}))
    for side in ("l", "r"):
        print("continuity", side, rep["continuity"][side]["summary"])
        sep = rep.get("separation", {}).get(side)
        if sep:
            print("separation", side, {k: sep[k] for k in ("muscles", "with_overlap_gt_0.3pct_before", "mean_overlap_pct_before", "mean_overlap_pct_after")})
        ss = rep["skin_seams"][side]
        print("skin seams", side, ss["before"], "->", ss["after"])
    if Path(a.audit).exists():
        au = json.loads(Path(a.audit).read_text())
        for side in ("left", "right"):
            o = au[side]
            print(side, "audit joint", o["joint"]["before"]["nearest_surface_gap_mm_median"], "->", o["joint"]["after"]["nearest_surface_gap_mm_median"], "| attachments", o["attachments_summary"],
                  "| continuity", o["continuity_summary"], "| centrelines", o["centreline_pairs_summary"], "| containment", o["containment"],
                  "| overlap", {k: {kk: vv for kk, vv in v.items() if kk != "per_muscle"} for k, v in o["muscle_overlap"].items()})


if __name__ == "__main__":
    main()
