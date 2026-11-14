#!/usr/bin/env python3
"""Q208 check of the female right 4th / 5th fingertip skin (Q207: 9.6-10.2 mm of skin beyond the distal phalanx against 2.8-3.7 mm in the Z source) against HER OWN evidence:
for every distal phalanx of both hands of a page: how far the displayed digit skin reaches beyond the bone tip along the finger axis (page and Z source), whether those skin vertices lie inside her own
cryosection skin, and how far her own skin envelope still encloses the finger axis beyond the tip.  Verdict: the skin is shortened only if it leaves her own skin (it does not).
    python3 scripts/zanatomy/q208_fingertip.py female|male"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q208_core as K  # noqa: E402
from scripts.zanatomy.q207_inflate import OwnSkin  # noqa: E402

FING = ("first", "second", "third", "fourth", "fifth")


def run(which):
    pg, raw = K.load(which)
    own = OwnSkin(which)
    out = {"page": which, "fingers": {}}
    for side in "lr":
        dig = [i for i in pg.skin_ids if i.endswith("_" + side) and any(k in i for k in ("digits_of_hand", "nail_plate_" + side, "perionyx_" + side))]
        rdig = [i for i in raw.skin_ids if i in dig]
        allv = np.vstack([pg.v(i) for i in dig])
        rallv = np.vstack([raw.v(i) for i in rdig])
        for f in FING:
            b = f"zan_distal_phalanx_of_{f}_finger_of_hand_{side}"
            pr = f"zan_proximal_phalanx_of_{f}_finger_of_hand_{side}"
            row = {}
            for tag, P, vv in (("page", pg, allv), ("z_source", raw, rallv)):
                v = P.v(b)
                c = v.mean(0)
                a = np.linalg.svd(v - c, full_matrices=False)[2][0]
                if (c - P.v(pr).mean(0)) @ a < 0:
                    a = -a
                tip = ((v - c) @ a).max()
                t = (vv - c) @ a
                perp = np.linalg.norm((vv - c) - t[:, None] * a, axis=1)
                m = (perp < 9) & (t > tip - 2)
                row[tag + "_skin_beyond_bone_tip_mm"] = round(float(max(t[m].max() - tip, 0)), 1) if m.any() else 0.0
                if tag == "page":
                    sd = own.sd(vv[m]) if m.any() else np.array([0.0])
                    row["skin_vertices_beyond_tip_max_signed_dist_to_own_skin_mm"] = round(float(sd.max()), 1)
                    ext = 0.0
                    for d in np.arange(0, 30.5, 0.5):
                        if own.sd((c + a * (tip + d))[None])[0] < 0:
                            ext = d
                    row["own_skin_encloses_finger_axis_beyond_tip_mm"] = float(ext)
            row["verdict"] = "no change: skin inside her own skin" if row["skin_vertices_beyond_tip_max_signed_dist_to_own_skin_mm"] <= 0.5 else "skin leaves the own skin"
            out["fingers"][f"{f}_{side}"] = row
    Path(REPO / "data" / "derived" / f"Q208_fingertip_{which}.json").write_text(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    r = run(sys.argv[1])
    for k, v in r["fingers"].items():
        print(k, v)
