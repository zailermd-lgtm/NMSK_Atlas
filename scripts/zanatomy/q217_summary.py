#!/usr/bin/env python3
"""Q217: elbow numbers of the UNCHANGED Q198 junction audit (elbow only) before / after, per page and side, from build/q217_raw/Q198_model_<key>_elbow.json  ->  data/derived/Q217_elbow_before_after.json
    python3 scripts/zanatomy/q217_summary.py own_m:own_m_a zan_m:zan_m_a own_f zan_f
muscle set = the arm / forearm muscles of that side in the audit zone (trunk muscles excluded).  Columns: n, mean / max share of the volume inside other muscles (Q198 lattice measure), muscles > 40 / > 60 %,
detached ends (end zone > 5 mm from its expected bone, min distance), flat cut faces on muscles, muscles with islands (> 1 piece, gap > 2 mm), muscles > 5 % of vertices inside bone, > 1 % outside skin, the skin / bone numbers of the junction."""
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
RAW = REPO / "build/q217_raw"
TRUNK = ("oblique", "transversus", "serratus", "latissimus", "iliocostalis", "rectus_abdominis", "pectoralis", "deltoid", "trapezius", "teres", "infraspinatus", "subscapularis", "supraspinatus", "gluteus", "iliopsoas")


def one(key):
    d = json.loads((RAW / f"Q198_model_{key}_elbow.json").read_text())
    out = {}
    for j in d["junctions"]:
        s = j["side"]
        soft = [x for x in j["soft"] if x["sys"] == "muscle" and x["id"].endswith("_" + s) and not any(t in x["id"] for t in TRUNK)]
        ov = {i: v["overlap_pct"] for i, v in j["muscle_overlap"].items() if i.endswith("_" + s) and not any(t in i for t in TRUNK)}
        det = []
        for x in soft:
            for end, e in (x.get("attach_ends_in_zone") or {}).items():
                if e.get("min_expected_bone_mm", 0) > 5.0:
                    det.append((x["id"], end, e["min_expected_bone_mm"]))
        out[s] = dict(n_muscles=len(soft), overlap_mean_pct=round(float(np.mean(list(ov.values()))), 1) if ov else None, overlap_max_pct=max(ov.values()) if ov else None,
                      muscles_over_40=sum(1 for v in ov.values() if v > 40), muscles_over_60=sum(1 for v in ov.values() if v > 60), detached_ends_over_5mm=len(det), detached=det,
                      flat_cut_muscles=sum(1 for x in soft if x.get("flat_caps")), muscles_with_islands=sum(1 for x in soft if x.get("islands", 1) > 1 and x.get("max_island_gap_mm", 0) > 2.0),
                      muscles_in_bone_over_5pct=sum(1 for x in soft if x.get("inside_bone_pct", 0) > 5), muscles_outside_skin_over_1pct=sum(1 for x in soft if x.get("outside_skin_pct", 0) > 1),
                      tubes=len([x for x in j['tubes'] if x['id'].endswith('_l' if s == 'l' else '_r')]), tubes_gap_over_5mm=sum(1 for x in j['tubes'] if x['id'].endswith('_' + s) and x.get('max_island_gap_mm', 0) > 5),
                      tubes_level_jump_over_25mm=sum(1 for x in j['tubes'] if x['id'].endswith('_' + s) and x.get('max_level_jump_mm', 0) > 25),
                      bone_surface_gap_mm=j["bones"].get("surface_gap_mm"), bone_max_penetration_mm=j["bones"].get("max_penetration_mm"))
    return out


if __name__ == "__main__":
    res = {}
    for a in sys.argv[1:]:
        b, _, af = a.partition(":")
        res[b] = {"before": one(b), "after": one(af) if af else None}
    p = REPO / "data/derived/Q217_elbow_before_after.json"
    p.write_text(json.dumps(res, indent=1, default=str))
    for k, v in res.items():
        for s in ("l", "r"):
            b = v["before"][s]
            a = v["after"][s] if v["after"] else None
            f = lambda x: f"n {x['n_muscles']}, overlap mean {x['overlap_mean_pct']} max {x['overlap_max_pct']}, >40: {x['muscles_over_40']}, >60: {x['muscles_over_60']}, detached ends {x['detached_ends_over_5mm']}, flat {x['flat_cut_muscles']}, islands {x['muscles_with_islands']}, in bone {x['muscles_in_bone_over_5pct']}, outside skin {x['muscles_outside_skin_over_1pct']}, tubes {x['tubes']} (gap>5mm {x['tubes_gap_over_5mm']}, jump>25mm {x['tubes_level_jump_over_25mm']})"
            print(k, s, "before:", f(b))
            if a:
                print(k, s, " after:", f(a))
