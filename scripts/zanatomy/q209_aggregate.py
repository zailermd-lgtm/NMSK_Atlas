#!/usr/bin/env python3
"""Q209: the UNCHANGED Q204 aggregator (scripts/zanatomy/q204_aggregate.py) over the Q209 raw runs (build/q209_raw[_merged]) -> data/derived/Q209_anatomy_audit.json
with the Q198 -> Q204 -> Q209 comparison added (compact)."""
import json, os, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
import scripts.zanatomy.q209_paths  # noqa: F401,E402
from scripts.zanatomy import q204_aggregate as A  # noqa: E402

TMP = REPO / "build" / "q209_agg"; TMP.mkdir(exist_ok=True)
for n in ("Q198_anatomy_audit.json",):
    t = TMP / n
    if not t.exists(): t.symlink_to(REPO / "data/derived" / n)
A.DER = TMP
A.RAW = REPO / "build" / "q209_raw"; A.RAWM = REPO / "build" / "q209_raw_merged"
A.PAGE_DIR.update({"z_male": "build/q197/viewer_zan_atlas", "z_base_f": "build/q202/viewer_base_female", "z_male_fit": "build/q208/viewer_zan_vhm", "z_female_fit": "build/q208/viewer_zan_female",
                   "own_m": "build/q203/viewer_m_hr (+build/viewer_m_hr_q203)", "own_f": "build/q203/viewer_f_hr (+build/viewer_f_hr_q203)"})
A.main()
raw = json.loads((TMP / "Q204_anatomy_audit.json").read_text())
q4 = json.loads((REPO / "data/derived/Q204_anatomy_audit.json").read_text())
raw["meta"]["task"] = "Q209 read-only re-run of the Q204 whole-body continuity / in-place audit on the six CURRENTLY PUBLISHED pages (Q198 + Q204 code and thresholds unchanged)"
raw["meta"]["q204_pages"] = q4["meta"]["pages"]
for k, p in raw["pages"].items():
    o = q4["pages"][k]
    p["q198_q204_q209"] = {"junction_major_moderate_minor": [p["q198_vs_now"]["severity_major_moderate_minor"][0], o["q198_vs_now"]["severity_major_moderate_minor"][1], p["q198_vs_now"]["severity_major_moderate_minor"][1]],
                           "verdict": [p["q198_vs_now"]["verdict"][0], o["q198_vs_now"]["verdict"][1], p["q198_vs_now"]["verdict"][1]],
                           "elbow_L_R": [p["q198_vs_now"]["elbow_L_R"][0], o["q198_vs_now"]["elbow_L_R"][1], p["q198_vs_now"]["elbow_L_R"][1]],
                           "whole_body_structures_major_moderate_minor": [None, [o["structure_severity_counts"][x] for x in ("major", "moderate", "minor")], [p["structure_severity_counts"][x] for x in ("major", "moderate", "minor")]],
                           "region_major_plus_moderate_q204_q209": {r: [o["regions"][r]["structures_major_moderate_minor"][0] + o["regions"][r]["structures_major_moderate_minor"][1],
                                                                     p["regions"][r]["structures_major_moderate_minor"][0] + p["regions"][r]["structures_major_moderate_minor"][1], p["regions"][r]["n_structures"]] for r in raw["meta"]["regions"]}}
    p["q204_page"] = q4["pages"][k]["page"]
(REPO / "data/derived/Q209_anatomy_audit.json").write_text(json.dumps(raw, separators=(",", ":")))
print("Q209 json bytes", (REPO / "data/derived/Q209_anatomy_audit.json").stat().st_size)
