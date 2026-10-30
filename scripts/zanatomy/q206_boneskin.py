#!/usr/bin/env python3
"""Q206: how much of each DISPLAYED wrist / hand / forearm bone lies outside the DISPLAYED skin (Q198 SkinField, > 3 mm) -- the limit of what the soft tissue can do (a vessel cannot be between a bone
and a skin that the bone pierces).   python3 scripts/zanatomy/q206_boneskin.py -> data/derived/Q206_bones_vs_skin.json"""
import json
import re
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q206_env as EN  # noqa: E402

BONE = re.compile(r"radius|ulna|scaphoid|lunate|triquetrum|pisiform|trapezium|trapezoid|capitate|hamate|metacarpal|finger_of_hand")


def main():
    out = {}
    for which, key in (("male", "q206_m"), ("female", "q206_f")):
        env = EN.Env(key)
        res = {}
        for side in "lr":
            rows = []
            for i, e in env.by.items():
                if e["sys"] == "bone" and i.endswith("_" + side) and BONE.search(i) and "foot" not in i:
                    sd = env.skin_sd(e["v"])
                    rows.append({"id": i, "outside_skin_gt3mm_pct": round(100 * float((sd > 3).mean()), 1), "max_outside_mm": round(float(max(sd.max(), 0)), 1)})
            rows.sort(key=lambda r: -r["outside_skin_gt3mm_pct"])
            res[side] = {"bones_with_gt1pct_outside": [r for r in rows if r["outside_skin_gt3mm_pct"] > 1.0], "n_bones": len(rows)}
        out[which] = res
        print(which, {s: [(r["id"], r["outside_skin_gt3mm_pct"], r["max_outside_mm"]) for r in v["bones_with_gt1pct_outside"][:5]] for s, v in res.items()})
    (REPO / "data" / "derived" / "Q206_bones_vs_skin.json").write_text(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
