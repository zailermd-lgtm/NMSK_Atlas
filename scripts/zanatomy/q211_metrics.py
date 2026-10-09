#!/usr/bin/env python3
"""Q211 before / after metrics of the two Z-fitted pages with the UNCHANGED Q198 (junction audit + rank), Q204 (whole-body regional pass) code.
    python3 scripts/zanatomy/q211_metrics.py   -> data/derived/Q211_metrics.json (+ a table on stdout)    needs build/q211_rank/<tag>.json (q211_rank.py) and build/q211_raw/Q204_regions_<tag>.json (q211_audit.py regions)"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
import scripts.zanatomy.q211_paths  # noqa: F401,E402
from scripts.zanatomy.q204_regions import structure_defects  # noqa: E402

REGIONS = ["head_neck", "shoulder", "arm_elbow_forearm", "wrist_hand", "thorax", "abdomen_pelvis", "hip", "thigh", "knee", "leg", "ankle", "foot"]
TAGS = {"male": ("q210_m", "q211_m"), "female": ("q208_f", "q211_f")}


def regional(tag):
    d = json.loads((REPO / f"build/q211_raw/Q204_regions_{tag}.json").read_text())
    reg = defaultdict(lambda: [0, 0, 0, 0])
    tot = Counter()
    inb = outs = 0
    for r in d["rows"]:
        r["defects"] = structure_defects(r)
        ms = max([x["severity"] for x in r["defects"]], default=0)
        reg[r["region"]][3] += 1
        if ms:
            reg[r["region"]][3 - ms] += 1
            tot[ms] += 1
        if any(x["check"] == "inside_bone" and x["severity"] >= 2 for x in r["defects"]):
            inb += 1
        if any(x["check"] == "outside_skin" and x["severity"] >= 2 for x in r["defects"]):
            outs += 1
    return {"whole_body_major_moderate_minor": [tot[3], tot[2], tot[1]], "regions_major_moderate_minor_n": {k: reg[k] for k in REGIONS}, "inside_bone_sev_ge2": inb, "outside_skin_sev_ge2": outs,
            "n_rows": len(d["rows"]), "skin_seam_totals": d.get("skin_seam_totals")}


def junction(tag):
    a = json.loads((REPO / f"build/q211_rank/{tag}.json").read_text())
    return {"verdict": a["verdict_continuous_and_in_place"], "major_moderate_minor": [a["severity_counts"][x] for x in ("major", "moderate", "minor")],
            "elbow": {s: [a["elbow"][s]["verdict"], a["elbow"][s]["n_major"], a["elbow"][s]["n_moderate"], a["elbow"][s]["n_minor"]] for s in "lr"},
            "junction": {f"{j['junction']}_{j['side']}": {"mmm": [j["n_major"], j["n_moderate"], j["n_minor"]], "bone_gap_mm": j["bone_gap_mm"], "bone_penetration_mm": j["bone_penetration_mm"]} for j in a["junction_table"]},
            "cause_groups_sev_ge2": a["cause_groups_sev_ge2"]}


if __name__ == "__main__":
    out = {}
    for which, (t0, t1) in TAGS.items():
        out[which] = {"before": {"page": t0, "q198": junction(t0), "q204": regional(t0)}, "after": {"page": t1, "q198": junction(t1), "q204": regional(t1)}}
        b, a = out[which]["before"], out[which]["after"]
        print(f"== {which}: Q198 verdict {b['q198']['verdict']} -> {a['q198']['verdict']}, junction major/mod/minor {b['q198']['major_moderate_minor']} -> {a['q198']['major_moderate_minor']}; "
              f"elbows {b['q198']['elbow']} -> {a['q198']['elbow']}")
        print(f"   Q204 whole body {b['q204']['whole_body_major_moderate_minor']} -> {a['q204']['whole_body_major_moderate_minor']}; inside-bone sev>=2 structures {b['q204']['inside_bone_sev_ge2']} -> {a['q204']['inside_bone_sev_ge2']}; "
              f"outside-skin {b['q204']['outside_skin_sev_ge2']} -> {a['q204']['outside_skin_sev_ge2']}")
        for jn in ("shoulder_l", "shoulder_r", "elbow_l", "elbow_r", "ankle_l", "ankle_r", "knee_l", "knee_r", "thoraco_lumbar_m"):
            print(f"   {jn:18s} {b['q198']['junction'][jn]['mmm']} gap {b['q198']['junction'][jn]['bone_gap_mm']} -> {a['q198']['junction'][jn]['mmm']} gap {a['q198']['junction'][jn]['bone_gap_mm']}")
    (REPO / "data" / "derived" / "Q211_metrics.json").write_text(json.dumps(out, indent=1))
