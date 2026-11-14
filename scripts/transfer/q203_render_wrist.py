#!/usr/bin/env python3
"""Q203: wrist close-ups of an own-model bundle (bones; Z-filled in blue / cyan).  q203_render_wrist.py BUNDLE OUT own_m|own_f"""
import sys
from pathlib import Path
import numpy as np
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "zanatomy"))
from scripts.transfer.q200_bundle import Bundle
from scripts.zanatomy import q190_render as R
B = Bundle(sys.argv[1]); out = sys.argv[2]; model = sys.argv[3]
cent = {"own_m": {"r": [140, 100, 112.], "l": [-168, 108, 100.]}, "own_f": {"r": [150, 100, 100.], "l": [-150, 100, 100.]}}[model]
for sd, c in cent.items():
    c = np.asarray(c, float); sc = []
    for it in B.items:
        e = it["e"]
        if e["cat"] != "bone":
            continue
        v, f = B.mesh(it)
        if np.linalg.norm(v - c, axis=1).min() > 70 or not re.search(r"(_%s)(_zfill\d*s?)?$|^(carpals|metacarpals|phalanges)" % sd, e["id"]) if False else False:
            continue
        if np.linalg.norm(v - c, axis=1).min() > 70:
            continue
        sub = e.get("subject", "")
        col = (0.1, 0.4, 0.95) if sub.endswith("_q203") else (0.3, 0.8, 0.85) if sub.endswith("_q200") else (0.93, 0.91, 0.80)
        sc.append(dict(v=v, f=f, color=col))
    lat = 90 if sd == "r" else 270
    R.render(sc, [dict(name=f"wrist_{sd}_ant", az=0, el=0, target=c, half=85), dict(name=f"wrist_{sd}_lat", az=lat, el=0, target=c, half=85), dict(name=f"wrist_{sd}_post", az=180, el=0, target=c, half=85)], Path(out) / model, size=(520, 520))
print("ok")
