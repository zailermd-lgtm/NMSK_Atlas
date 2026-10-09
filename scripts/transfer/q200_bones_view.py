#!/usr/bin/env python3
"""Q200: bones-only close-ups of one elbow (measured bones cream, Z-filled bone pieces blue).  q200_bones_view.py BUNDLE OUT_DIR own_m|own_f l|r"""
import sys
from pathlib import Path
import numpy as np
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "zanatomy"))
from scripts.transfer.q200_bundle import Bundle
from scripts.zanatomy import q190_render as R
from scripts.zanatomy import q198_renders as R8

B = Bundle(sys.argv[1]); out = Path(sys.argv[2]); model = sys.argv[3]; side = sys.argv[4]
j = R8.elbow_json(model, side) if model == "own_m" or side == "r" else None
sc = []
cen = None
for it in B.items:
    e = it["e"]
    if e["cat"] != "bone":
        continue
    if not (e["id"].startswith(("humerus", "radius", "ulna", "carpals", "metacarpal", "phalanges_hand")) and (e["side"] or "")[:1] == ("l" if side == "l" else "r")):
        continue
    v, f = B.mesh(it)
    z = e["subject"].endswith("_q200")
    sc.append(dict(v=v, f=f, color=(0.15, 0.45, 0.95) if z else (0.93, 0.91, 0.80)))
h = B.get("humerus_" + side)["v"]
c = np.asarray(j["centre_mm"]) if j else h[h[:, 1] < h[:, 1].min() + 8].mean(0) + np.array([0, -10, 0])
lat = 90 if side == "r" else 270
views = [dict(name=f"bones_{side}_anterior", az=0, el=0, target=c, half=85), dict(name=f"bones_{side}_posterior", az=180, el=0, target=c, half=85),
         dict(name=f"bones_{side}_lateral", az=lat, el=0, target=c, half=85), dict(name=f"bones_{side}_medial", az=(lat + 180) % 360, el=0, target=c, half=85)]
out.mkdir(parents=True, exist_ok=True)
R.render(sc, views, out, size=(480, 480))
from PIL import Image
ims = [Image.open(out / f"{v['name']}.png").convert("RGB") for v in views]
M = Image.new("RGB", (sum(i.width for i in ims), ims[0].height), "white"); x = 0
for i in ims:
    M.paste(i, (x, 0)); x += i.width
M.save(out / f"bones_{side}.png"); print(out / f"bones_{side}.png")
