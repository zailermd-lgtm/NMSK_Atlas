#!/usr/bin/env python3
"""Q211 report: the state's reports (bones, follow, zones, inbone) -> data/derived/Q211_report_{male,female}.json.   python3 scripts/zanatomy/q211_report.py"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy.q211_build import State  # noqa: E402


def summarize(st):
    r = st.reports
    out = {"bones": r["bones"], "zones": {z: {k: v for k, v in rep.items() if k != "tear_gt5_by_structure"} for z, rep in r["zones"].items()}, "tear_by_structure": {z: rep["tear_gt5_by_structure"] for z, rep in r["zones"].items()}}
    f = r["follow"]
    out["follow"] = {"structures": len(f), "mean_move_mm_median": round(float(np.median([v["mean_move_mm"] for v in f.values()])), 2) if f else None, "max_move_mm": max([v["max_move_mm"] for v in f.values()], default=None)}
    ib = r["inbone"]
    rep = ib["repaired"]
    tb = lambda k, s: float(np.mean([v[s][k] for v in rep.values()])) if rep else None
    out["inbone"] = {"targets": len(ib["targets"]), "repaired": len(rep), "kept_unrepaired": sorted(ib["kept"]),
                     "inside_bone_pct_mean_before_after": [round(tb("inside_bone_pct", "before"), 2), round(tb("inside_bone_pct", "after"), 2)] if rep else None,
                     "outside_skin_pct_mean_before_after": [round(tb("outside_skin_pct", "before"), 2), round(tb("outside_skin_pct", "after"), 2)] if rep else None,
                     "max_move_mm": max([v["max_move_mm"] for v in rep.values()], default=None)}
    allv = {}
    for i, logs in st.log.items():
        allv[i] = [L["stage"] for L in logs]
    out["structures_changed"] = len(st.V)
    out["by_stage"] = {s: sum(1 for v in allv.values() if s in v) for s in ("bone", "follow", "zone", "inbone", "final")}
    out["final"] = r.get("final")
    out["guards_in_zones"] = {z: {"attach_guard": rep.get("attach_guard"), "overlap_guard": rep.get("overlap_guard"), "reanchored": rep.get("reanchored")} for z, rep in r["zones"].items()}
    return out


if __name__ == "__main__":
    for w in ("male", "female"):
        st = State.load(w, "final")
        (REPO / "data" / "derived" / f"Q211_report_{w}.json").write_text(json.dumps(summarize(st), indent=1, default=float))
        print(w, json.dumps({k: v for k, v in summarize(st).items() if k in ("follow", "inbone", "by_stage", "structures_changed")}, default=float)[:700])
