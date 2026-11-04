#!/usr/bin/env python3
"""Q211: the UNCHANGED Q198 aggregator (q198_rank: thresholds, severity, verdict, elbow rule) over the junction audit of one Z-fitted page, each with its unfitted Z base as baseline.
    python3 scripts/zanatomy/q211_rank.py KEY [KEY ...]     KEY = q210_m q208_f q211_m q211_f   (raw junction audit build/q211_raw/Q198_model_<KEY>.json, fitseams build/q204_raw/fake/data/derived/Q198_fitseams_<KEY>.json)
-> build/q211_rank/<KEY>.json  (full model block incl. every defect with its metrics) and data/derived/Q211_junction_rank.json (compact table, appended per key)"""
import json
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "zanatomy"))
from scripts.zanatomy import q198_rank as R  # noqa: E402

FIT = {"q210_m": ("z_male_fit", "z_male"), "q211_m": ("z_male_fit", "z_male"), "q208_f": ("z_female_fit", "z_base_f"), "q211_f": ("z_female_fit", "z_base_f")}
SEAMS = REPO / "build/q204_raw/fake/data/derived"


def run(tag):
    fk, bk = FIT[tag]
    d = REPO / "build" / "q211_rank" / tag
    d.mkdir(parents=True, exist_ok=True)
    for f in d.glob("*.json"):
        f.unlink()
    shutil.copy(REPO / f"build/q209_raw/Q198_model_{bk}.json", d / f"Q198_model_{bk}.json")
    shutil.copy(REPO / f"build/q211_raw/Q198_model_{tag}.json", d / f"Q198_model_{fk}.json")
    sp = SEAMS / f"Q198_fitseams_{tag}.json"
    if sp.exists():
        shutil.copy(sp, d / f"Q198_fitseams_{fk}.json")
    R.DER = d
    R.FIT_SEAMS = {fk: f"Q198_fitseams_{fk}.json"}
    R.main()
    a = json.loads((d / "Q198_anatomy_audit.json").read_text())["models"][fk]
    (REPO / "build" / "q211_rank" / f"{tag}.json").write_text(json.dumps(a))
    return {"verdict": a["verdict_continuous_and_in_place"], "major_moderate_minor": [a["severity_counts"][x] for x in ("major", "moderate", "minor")],
            "elbow": {s: [a["elbow"][s]["verdict"], a["elbow"][s]["n_major"], a["elbow"][s]["n_moderate"]] for s in "lr"},
            "junction_table": {f"{j['junction']}_{j['side']}": [j["n_major"], j["n_moderate"], j["n_minor"], j["bone_gap_mm"], j["bone_penetration_mm"]] for j in a["junction_table"]}}


if __name__ == "__main__":
    out = {}
    p = REPO / "data" / "derived" / "Q211_junction_rank.json"
    if p.exists():
        out = json.loads(p.read_text())
    for t in sys.argv[1:]:
        out[t] = run(t)
        print(t, json.dumps({k: v for k, v in out[t].items() if k != "junction_table"}))
    p.write_text(json.dumps(out, indent=1))
