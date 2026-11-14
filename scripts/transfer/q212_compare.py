#!/usr/bin/env python3
"""Q212: Q198 metrics per junction, Q203 pages (data/derived/Q203_model_<key>_after.json) vs Q212 pages (Q212_model_<key>_after212.json), same code as q203_compare.metrics.
    python3 scripts/transfer/q212_compare.py  ->  data/derived/Q212_before_after.json"""
import json, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.transfer.q203_compare import metrics
D = REPO / "data/derived"
out = {}
sumk = ["structs_with_flat_cap", "flat_caps", "flat_cap_area_mm2", "bone_flat_caps", "bone_flat_cap_area_mm2", "muscle_ends_gt5mm_from_bone", "islands_gt5mm", "open_loops_in_zone"]
for key in ("own_m", "own_f"):
    A = json.loads((D / f"Q203_model_{key}_after.json").read_text()); B = json.loads((D / f"Q212_model_{key}_after212.json").read_text())
    ja = {(j["name"], j["side"]): j for j in A["junctions"]}; jb = {(j["name"], j["side"]): j for j in B["junctions"]}
    out[key] = {}
    for k in sorted(set(ja) & set(jb)):
        ma, mb = metrics(ja[k]), metrics(jb[k])
        out[key][f"{k[0]}_{k[1]}"] = dict(before=ma, after=mb)
        ch = {m: (ma[m], mb[m]) for m in ma if ma[m] != mb[m]}
        if ch:
            print(key, k, ch)
    out[key]["total"] = {w: {m: sum((v[w][m] or 0) for kk, v in out[key].items() if kk != "total") for m in sumk} for w in ("before", "after")}
    print(key, "TOTAL", {m: (out[key]["total"]["before"][m], out[key]["total"]["after"][m]) for m in sumk})
(D / "Q212_before_after.json").write_text(json.dumps(out, indent=1))
