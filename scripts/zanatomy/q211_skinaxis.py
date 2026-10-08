#!/usr/bin/env python3
"""Q211: pose-aware elbow skin sections.  The Q198 elbow skin profile cuts planes perpendicular to ONE axis (humerus-COM -> forearm-COM) through the whole +-90 mm zone; with a flexed elbow the planes at the
crease cut the upper arm and the forearm obliquely.  Here the planes are perpendicular to the UPPER-ARM axis (shoulder -> elbow) on the proximal side and to the FOREARM axis (elbow -> wrist) on the distal side
(Q198's own skin_profile function, same closing / radius / step rules; sections within 12 mm of the joint centre skipped: there the two limb segments touch).
    python3 scripts/zanatomy/q211_skinaxis.py KEY   (KEY q210_m q208_f q211_m q211_f z_male z_base_f)"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.zanatomy import q211_paths  # noqa: F401,E402
from scripts.zanatomy import q198_audit as A  # noqa: E402
from scripts.zanatomy.q198_load import load
from scripts.zanatomy.q198_joints import find_joints
from scripts.zanatomy.q198_audit import elbow_angles

REPO = A.REPO


def run(key, log=print):
    S = load(key)
    J, B, lev = find_joints(S)
    skin = [s for s in S if s["sys"] == "skin" or s["id"] == "skin"]
    out = {}
    for j in J:
        if j["name"] != "elbow":
            continue
        ea = elbow_angles(j, B, j["side"])
        c = np.asarray(j["centre"], float)
        hax, fax = np.asarray(ea["humerus_axis"], float), np.asarray(ea["forearm_axis"], float)
        res = {"flexion_deg": ea["flexion_deg"]}
        for nm, ax, sgn in (("upper_arm", hax, -1.0), ("forearm", fax, 1.0)):
            cc = c + sgn * 51.0 * ax
            p = A.skin_profile(skin, dict(centre=cc, axis=ax), half=39.0, dt=3.0)        # t = -39 .. 39 around cc  = 12 .. 90 mm from the joint centre
            res[nm] = p
        out[j["side"]] = res
        log(key, j["side"], {k: {x: y for x, y in v.items() if x in ("slices", "valid", "open_or_missing_sections", "max_radius_step_mm_per_3mm", "steps_gt3mm", "at_t_mm")} if isinstance(v, dict) else v for k, v in res.items()})
    return out


if __name__ == "__main__":
    o = {k: run(k) for k in sys.argv[1:]}
    p = REPO / "data" / "derived" / "Q211_skin_pose_aware.json"
    old = json.loads(p.read_text()) if p.exists() else {}
    old.update(o)
    p.write_text(json.dumps(old, indent=1))
