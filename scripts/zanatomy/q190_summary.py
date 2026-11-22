"""Q190: compact numbers file data/derived/Q190_trunk_refine.json from the build report (full-resolution stretch/volume numbers) and the
shipped-geometry audit (data/derived/Q190_trunk_audit.json)."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
D = REPO / "data" / "derived"
KEY = ["gluteus_maximus", "gluteus_medius", "gluteus_minimus", "quadratus_lumborum", "multifidus", "longissimus", "iliocostalis", "spinalis",
       "iliopsoas", "rectus_abdominis", "external_oblique", "internal_oblique", "transversus_abdominis", "latissimus_dorsi", "trapezius"]


def main():
    b = json.loads((D / "Q190_zan_female_q190_build.json").read_text())["q190"]
    a = json.loads((D / "Q190_trunk_audit.json").read_text())
    st = b["structures"]
    regions = {}
    for rg in sorted({v["region"] for v in st.values()}):
        v = [x for x in st.values() if x["region"] == rg]
        regions[rg] = {"structures": len(v), "mean_distortion_score_before": round(float(np.mean([x["distortion_score_before"] for x in v])), 2),
                       "mean_distortion_score_after": round(float(np.mean([x["distortion_score_after"] for x in v])), 2),
                       "flipped_faces_pct_before": round(100 * float(np.mean([x["flipped_before"] for x in v])), 2),
                       "flipped_faces_pct_after": round(100 * float(np.mean([x["flipped_after"] for x in v])), 2)}
    rank = lambda sel, key: sorted(((k, v) for k, v in st.items() if sel(v)), key=lambda kv: -kv[1][key])
    row = lambda kv: {"id": kv[0], "cat": kv[1]["cat"], "region": kv[1]["region"], "score_before": kv[1]["distortion_score_before"], "score_after": kv[1]["distortion_score_after"],
                      "area_outside_0.67_1.5_before": kv[1]["area_outside_0.67_1.5_before"], "area_outside_0.67_1.5_after": kv[1]["area_outside_0.67_1.5_after"],
                      "flipped_before": kv[1]["flipped_before"], "flipped_after": kv[1]["flipped_after"], "refined": "her_label" in kv[1],
                      "recovered": kv[0] in b["shape_recovery"]}
    key_rows = {}
    ch = a["her_label_chamfer_mm"]
    for k in KEY:
        for side in ("_l", "_r"):
            g = ch.get(k + side)
            if g:
                mem = g["members"]
                vols = [(st[m].get("volume_cm3_v6"), st[m].get("volume_cm3_q190"), st[m].get("volume_cm3_source_x_body_scale3")) for m in mem if m in st]
                key_rows[k + side] = {"her_label_chamfer_mm_v6": g["mean_before"], "her_label_chamfer_mm_q190": g["mean_after"], "partial_label": g["partial_label"],
                                      "volume_cm3_v6_q190_source": [round(sum(x[i] or 0 for x in vols), 1) for i in range(3)] if vols else None}
    out = {"source": "Q190 (2026-10-05): per-structure refinement of the female Z-Anatomy muscles onto her own CT labels; scripts/zanatomy/q190_refine.py, q190_metrics.py, "
                     "q190_audit.py, q190_ship_audit.py. Distortion score = % of triangles whose area stretch vs the Z source (x body scale, divided by the "
                     "structure's own median so a uniform scale is not distortion) is outside 0.67-1.5, plus % flipped faces.",
           "regions": regions,
           "worst10_before_all_trunk_structures": [row(kv) for kv in rank(lambda v: True, "distortion_score_before")[:10]],
           "worst10_after_all_trunk_structures": [row(kv) for kv in rank(lambda v: True, "distortion_score_after")[:10]],
           "worst10_muscles_before": [row(kv) for kv in rank(lambda v: v["cat"] == "muscle", "distortion_score_before")[:10]],
           "worst10_muscles_after": [row(kv) for kv in rank(lambda v: v["cat"] == "muscle", "distortion_score_after")[:10]],
           "key_muscles_vs_her_ct_label": key_rows,
           "refined_muscles": {k: {kk: v[kk] for kk in ("her_label", "her_label_chamfer_mm_before_after", "her_label_partial", "volume_cm3_v6", "volume_cm3_q190",
                                                      "volume_cm3_source_x_body_scale3", "distortion_score_before", "distortion_score_after") if kk in v}
                               for k, v in st.items() if "her_label" in v},
           "counts": {"refined_muscles": sum(1 for v in st.values() if "her_label" in v), "shape_recovered": len(b["shape_recovery"]), "propagated": len(b["propagated"]),
                      "envelope_clamped": len(b["envelope_clamp"])},
           "shipped_geometry_audit": {k: a[k] for k in ("her_label_chamfer_median_mm", "containment", "lr_symmetry_mm", "front_crease", "back_skin")} | {
               "muscle_overlap": {k: v for k, v in a["muscle_overlap"].items() if k != "per_muscle"}},
           "all_structures": st}
    (D / "Q190_trunk_refine.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps({k: out[k] for k in ("regions", "counts")}, indent=1))
    for k in ("worst10_before_all_trunk_structures", "worst10_muscles_before"):
        print(k)
        for r in out[k]:
            print("  %-48s %-9s %5.1f -> %5.1f %s" % (r["id"][:48], r["cat"], r["score_before"], r["score_after"], "refined" if r["refined"] else ("recovered" if r["recovered"] else "")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
