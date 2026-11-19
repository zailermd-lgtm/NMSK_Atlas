#!/usr/bin/env python3
"""Q210: the UNCHANGED Q198 aggregator (q198_rank: thresholds, severity, verdict) over the junction audit of the male Z-fitted page, Q208 (before; the Q209 raw files) and Q210 (after; build/q210_raw), each with the
unfitted Z male base as baseline -> data/derived/Q210_junction_rank.json (major / moderate / minor junction findings, verdict, elbow verdicts).   python3 scripts/zanatomy/q210_junction_rank.py"""
import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "zanatomy"))
from scripts.zanatomy import q198_rank as R  # noqa: E402

SRC = {"q208": (REPO / "build/q209_raw/Q198_model_z_male_fit.json", REPO / "build/q204_raw/fake/data/derived/Q198_fitseams_z_male_fit.json"),
       "q210": (REPO / "build/q210_raw/Q198_model_q210_m.json", REPO / "build/q204_raw/fake/data/derived/Q198_fitseams_q210_m.json")}


def run(tag):
    d = REPO / "build" / f"q210_rank_{tag}"
    d.mkdir(parents=True, exist_ok=True)
    shutil.copy(REPO / "build/q209_raw/Q198_model_z_male.json", d / "Q198_model_z_male.json")
    model, seams = SRC[tag]
    shutil.copy(model, d / "Q198_model_z_male_fit.json")
    if seams.exists():
        shutil.copy(seams, d / "Q198_fitseams_z_male_fit.json")
    R.DER = d
    R.FIT_SEAMS = {"z_male_fit": "Q198_fitseams_z_male_fit.json"}
    R.main()
    a = json.loads((d / "Q198_anatomy_audit.json").read_text())["models"]["z_male_fit"]
    return {"verdict": a["verdict_continuous_and_in_place"], "severity_major_moderate_minor": [a["severity_counts"][x] for x in ("major", "moderate", "minor")], "elbow_L_R": [a["elbow"]["l"]["verdict"], a["elbow"]["r"]["verdict"]],
            "junction_table": {f"{j['junction']}_{j['side']}": [j["n_major"], j["n_moderate"], j["n_minor"]] for j in a["junction_table"]}}


if __name__ == "__main__":
    out = {t: run(t) for t in ("q208", "q210")}
    (REPO / "data" / "derived" / "Q210_junction_rank.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({t: {k: v for k, v in o.items() if k != "junction_table"} for t, o in out.items()}))
