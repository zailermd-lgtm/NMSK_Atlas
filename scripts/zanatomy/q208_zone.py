#!/usr/bin/env python3
"""Q208 containment of the whole forearm + hand (not only the wrist zone of Q207) against the displayed skin, before (Q207 page) and after (Q208 state), and against the person's own CT / cryosection skin:
the classes (bone, vessel, nerve, joint, bursa, muscle, fascia ...) with > 5 % of their zone vertices more than 3 mm outside the displayed skin (Q198 audit field) and on the 1 mm envelope, and the per-muscle
numbers: share outside the displayed skin and outside the OWN skin (a muscle belly outside the own skin is the outlier, not the skin).
    python3 scripts/zanatomy/q208_zone.py male|female"""
from __future__ import annotations

import json
import pickle
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q207_core as C7  # noqa: E402
from scripts.zanatomy import q207_eval as EV  # noqa: E402
from scripts.zanatomy import q208_core as K  # noqa: E402
from scripts.zanatomy.q207_inflate import OwnSkin  # noqa: E402


def run(which, log=print):
    C7.ZONE_WRIST_MM = 300.0                       # whole forearm (elbow -> wrist is ~280 mm) + the hand bones' 35 mm
    pg, raw = K.load(which)
    V0 = {i: pg.v(i) for i in pg.skin_ids}
    V1 = pickle.load(open(K.state_path(which, "uro"), "rb"))[0]
    own = OwnSkin(which)
    W = pg.wrist()
    seal = EV.sealers(which, pg)
    cf0 = EV.coarse_field(which, pg, V0, seal)
    cf1 = EV.coarse_field(which, pg, V1, seal)
    log(f"[{which}] envelope {cf0.vol_L:.1f} -> {cf1.vol_L:.1f} L")
    out = {"page": which, "envelope_L": [round(float(cf0.vol_L), 1), round(float(cf1.vol_L), 1)], "sides": {}}
    for side in "lr":
        zone = pg.zone_structs(side, W[side])
        a = EV.zone_measure(pg, V0, which, side, W[side], cf0, own, zone)
        b = EV.zone_measure(pg, V1, which, side, W[side], cf1, own, zone)
        muscles = {}
        for i, m in zone.items():
            if pg.sys(i) != "muscle":
                continue
            so = own.sd(pg.v(i)[m])
            muscles[i] = {"vertices": int(m.sum()), "before": a["structures"][i], "after": b["structures"][i],
                          "outside_own_skin_gt3mm_pct": round(float((so > 3).mean() * 100), 1), "outside_own_skin_max_mm": round(float(max(so.max(), 0)), 1)}
        out["sides"][side] = {"before": a["classes"], "after": b["classes"], "structures": len(zone),
                              "muscles": muscles,
                              "muscles_gt5pct_outside_displayed_skin_audit": [sum(x["before"]["audit_gt3_pct"] > 5 for x in muscles.values()), sum(x["after"]["audit_gt3_pct"] > 5 for x in muscles.values())],
                              "muscles_gt5pct_outside_own_skin": sum(x["outside_own_skin_gt3mm_pct"] > 5 for x in muscles.values()),
                              "worst_muscle_outside_displayed_skin_mm": [max(x["before"]["audit_max_mm"] for x in muscles.values()), max(x["after"]["audit_max_mm"] for x in muscles.values())]}
        for c in ("bone", "vessel", "nerve", "joint", "bursa", "muscle", "fascia"):
            if c in a["classes"]:
                log(f"   {side} {c:7s} audit>5%: {a['classes'][c]['audit_gt5pct']} -> {b['classes'][c]['audit_gt5pct']} of {a['classes'][c]['structures']}; fine>5%: {a['classes'][c]['fine_gt5pct']} -> {b['classes'][c]['fine_gt5pct']}; fine mean >0.5 mm {a['classes'][c]['fine_mean_gt0.5_pct']} -> {b['classes'][c]['fine_mean_gt0.5_pct']} %; worst fine {a['classes'][c]['fine_worst_mm']} -> {b['classes'][c]['fine_worst_mm']} mm")
    (REPO / "data" / "derived" / f"Q208_zone_{which}.json").write_text(json.dumps(out, indent=1, default=float))
    return out


if __name__ == "__main__":
    run(sys.argv[1])
