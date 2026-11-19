#!/usr/bin/env python3
"""Q205: before -> after numbers of one Z page (Q204 hands audit, Q204 regional pass, Q198 junction counts, skin metrics) -> data/derived/Q205_summary_<male|female>.json
    python3 scripts/zanatomy/q205_summary.py male|female    (needs build/q204_raw/Q204_hands_<key>.json, Q204_regions_<key>.json, Q198_model_<key>_<joints>.json, fitseams for the after key)"""
import json
import sys
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
RAW = REPO / "build" / "q204_raw"
KEYS = {"male": ("z_male_fit", "q205_m", "z_male", "z_male_fit"), "female": ("z_female_fit", "q205_f", "z_base_f", "z_female_fit")}


def hands(key):
    d = json.loads((RAW / f"Q204_hands_{key}.json").read_text())
    out = {}
    for sd, r in d["sides"].items():
        out[sd] = {"links_mm": {l["link"]: l["gap_mm"] for l in r["links"]},
                   "finger_link_gaps_gt3mm": [[o, x["gap_mm"]] for o, f in r["fingers"].items() for x in f["links"] if x["gap_mm"] > 3],
                   "bend_deg": {o: f["bend_deg"] for o, f in r["fingers"].items()},
                   "bones_outside_skin_gt1pct": [[b["id"], b["outside_skin_pct"], b["outside_skin_max_mm"]] for f in r["fingers"].values() for b in f["bones"] if b["outside_skin_pct"] > 1]}
    return out


def regions(key):
    d = json.loads((RAW / f"Q204_regions_{key}.json").read_text())
    sv = lambda r: max([x["severity"] for x in r["defects"]] or [0])
    out = {}
    for reg in ("wrist_hand", "shoulder", "arm_elbow_forearm"):
        c = Counter(sv(r) for r in d["rows"] if r["region"] == reg)
        out[reg] = {"major": c[3], "moderate": c[2], "minor": c[1], "n": sum(c.values())}
    out["skin_seam_totals"] = d["skin_seam_totals"]
    return out


def junctions(key, fitkey, basekey, files, fs):
    from scripts.zanatomy import q205_paths  # noqa: F401
    from scripts.zanatomy import q198_rank as R
    base = json.loads((RAW / f"Q198_model_{basekey}.json").read_text())
    res = json.loads((RAW / files).read_text())
    D, _ = R.build_model(fitkey, "zan", res, json.loads(fs.read_text()), base)
    out = {}
    for reg in ("shoulder", "wrist", "elbow"):
        for sd in "lr":
            c = Counter(d["severity"] for d in D if d["region"] == reg and d.get("side") == sd)
            out[f"{reg}_{sd}"] = [c[3], c[2], c[1]]
    return out


if __name__ == "__main__":
    which = sys.argv[1]
    kb, ka, base, fitkey = KEYS[which]
    out = {"before_key": kb, "after_key": ka, "hands": {"before": hands(kb), "after": hands(ka)}, "regions": {"before": regions(kb), "after": regions(ka)}}
    jb = RAW / f"Q198_model_{kb}.json"
    ja = sorted(RAW.glob(f"Q198_model_{ka}_*.json"), key=lambda p: p.stat().st_size)
    if ja:
        out["junctions_major_moderate_minor"] = {"before": junctions(kb, fitkey, base, jb.name, RAW / "fake" / "data" / "derived" / f"Q198_fitseams_{kb}.json"),
                                                 "after": junctions(ka, fitkey, base, ja[-1].name, RAW / "fake" / "data" / "derived" / f"Q198_fitseams_{ka}.json")}
    (REPO / "data" / "derived" / f"Q205_summary_{which}.json").write_text(json.dumps(out, indent=1))
    print(json.dumps(out["regions"]), json.dumps(out.get("junctions_major_moderate_minor")))
