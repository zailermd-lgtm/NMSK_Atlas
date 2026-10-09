#!/usr/bin/env python3
"""Q212: wrist bones of HIS two hands before (Q203 bundle) / after (Q212 bundle): radius, ulna, carpals, metacarpals, phalanges; the CT re-segmented pieces green, the Z-Anatomy pieces blue.
    python3 scripts/transfer/q212_render_wrist.py OUT_DIR"""
import re, sys
from pathlib import Path
import numpy as np
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "zanatomy"))
from scripts.transfer.q200_bundle import Bundle
from scripts.zanatomy import q190_render as R
out = Path(sys.argv[1])
for tag, d in (("before", "build/viewer_m_hr_q203"), ("after", "build/viewer_m_hr_q212")):
    B = Bundle(REPO / d)
    for sd, ctr in (("r", np.array([140.0, 100.0, 115.0])), ("l", np.array([-160.0, 105.0, 105.0]))):
        scene = []
        for it in B.items:
            e = it["e"]
            if e["cat"] != "bone" or not re.search(rf"(radius|ulna|carpals|metacarpals|phalanges_hand)_{sd}", e["id"]) or e.get("hidden_default"):
                continue
            v, f = B.mesh(it)
            col = (0.93, 0.91, 0.80)
            if e.get("subject", "").endswith("wrist_q212"):
                col = (0.15, 0.70, 0.35)
            elif "_zfill" in e["id"]:
                col = (0.10, 0.40, 0.95)
            scene.append({"v": v, "f": f, "color": col})
        views = [dict(name=f"wrist_{sd}_{tag}_{n}", az=az, el=el, target=ctr, half=70) for n, az, el in (("ant", 0, 15), ("post", 180, 15), ("lat", 90 if sd == "r" else 270, 10), ("sup", 0, 75))]
        R.render(scene, views, out, size=(520, 520))
print("done")
