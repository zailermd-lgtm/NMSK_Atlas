#!/usr/bin/env python3
"""Q205: the UNCHANGED Q198 ranking (q198_rank.build_model) on one junction-audit JSON; the fitted pages are compared with their unfitted base exactly as in Q204.
    python3 scripts/zanatomy/q205_rank.py JSON KEY(z_male_fit|z_female_fit) [--sides shoulder,wrist]  -> counts per junction / side (major, moderate, minor) + the major list"""
import json
import sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
import scripts.zanatomy.q205_paths  # noqa: F401,E402
from scripts.zanatomy import q198_rank as R  # noqa: E402

BASE_JSON = {"z_male_fit": "Q198_model_z_male.json", "z_female_fit": "Q198_model_z_base_f.json"}
FS = {"z_male_fit": "Q198_fitseams_z_male_fit.json", "z_female_fit": "Q198_fitseams_z_female_fit.json"}


def rank(res, key, junctions=None):
    raw = REPO / "build" / "q204_raw"
    base = json.loads((raw / BASE_JSON[key]).read_text())
    fit = json.loads((REPO / "data" / "derived" / FS[key]).read_text())
    D, absent = R.build_model(key, "zan", res, fit, base)
    out = {}
    for d in D:
        if junctions and d["region"] not in junctions:
            continue
        k = (d["region"], d.get("side"))
        out.setdefault(k, [0, 0, 0])
        if d["severity"] >= 1:
            out[k][3 - d["severity"]] += 1
    return D, out


if __name__ == "__main__":
    res = json.loads(Path(sys.argv[1]).read_text())
    key = sys.argv[2]
    js = sys.argv[3].split(",") if len(sys.argv) > 3 else None
    D, out = rank(res, key, js)
    for k, v in sorted(out.items()):
        print(k, "major/moderate/minor", v)
