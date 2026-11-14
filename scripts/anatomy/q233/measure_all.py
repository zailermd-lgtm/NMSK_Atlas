#!/usr/bin/env python3
"""Q233: run every dimorphism measurement on the six CURRENT pages -> data/derived/Q233_measures.json.    python3 scripts/anatomy/q233/measure_all.py"""
import json, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "anatomy"))
import q233_load as Q  # noqa: E402
from scripts.anatomy.q233 import dimorphism as D  # noqa: E402

out = {}
for k in Q.PAGES:
    S = Q.load(k)
    r = {}
    for f in (D.pelvis_size, D.outlet_and_subpubic, D.sacrum_metrics, D.ischiopubic, D.sciatic_notch, D.sternum_metrics, D.shoulder_hip, D.breast_projection):
        try:
            r.update(f(S))
        except Exception as e:  # noqa: BLE001
            r[f.__name__ + "_error"] = str(e)
    for sd in "rl":
        fm = D.femur_metrics(S, sd)
        r[f"femoral_head_diameter_{sd}_mm"] = fm.get("femoral_head_diameter_mm"); r[f"bicondylar_breadth_{sd}_mm"] = fm.get("bicondylar_breadth_mm"); r[f"femur_length_{sd}_mm"] = fm.get("femur_length_mm")
        r[f"q_angle_{sd}_deg"] = D.q_angle(S, sd).get("q_angle_deg")
    r["bi_acetabular_distance_mm"] = None
    try:
        a, b = D.femur_metrics(S, "r")["head_centre"], D.femur_metrics(S, "l")["head_centre"]
        r["bi_acetabular_distance_mm"] = round(abs(a[0] - b[0]), 1)
    except Exception:
        pass
    r = {a: b for a, b in r.items() if not a.startswith("tuber_")}
    ids = {x["id"] for x in S}
    r["skull_meshes_present"] = sorted(i for i in ids if i.split("#")[0] in ("cranium", "mandible", "frontal", "occipital", "temporal_l", "temporal_r", "maxilla_l", "maxilla_r", "zygomatic_l", "zygomatic_r"))
    out[k] = r
    print(k, flush=True)
(REPO / "data/derived/Q233_measures.json").write_text(json.dumps(out, indent=1, default=float) + "\n")
