#!/usr/bin/env python3
"""Q200: close-up of chosen structures (measured red, continuation blue, bones cream).  q200_pairview.py BUNDLE OUT.png cx cy cz half id1,id2,... [az1,az2,...]"""
import sys
from pathlib import Path
import numpy as np
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "zanatomy"))
from scripts.transfer.q200_bundle import Bundle
from scripts.zanatomy import q190_render as R
from PIL import Image
B = Bundle(sys.argv[1]); out = Path(sys.argv[2]); c = np.array([float(x) for x in sys.argv[3:6]]); half = float(sys.argv[6])
ids = sys.argv[7].split(","); azs = [float(a) for a in (sys.argv[8].split(",") if len(sys.argv) > 8 else ["0", "90", "180", "270"])]
sc = []
for it in B.items:
    e = it["e"]
    keep = e["id"] in ids or any(e["id"] == i + "_zfill" for i in ids)
    bone = e["cat"] == "bone" and e["id"].split("_zfill")[0].startswith(("humerus", "radius", "ulna"))
    if not (keep or bone):
        continue
    v, f = B.mesh(it)
    z = e["subject"].endswith("_q200")
    col = (0.15, 0.45, 0.95) if z else ((0.93, 0.91, 0.80) if e["cat"] == "bone" else (0.75, 0.2, 0.15))
    sc.append(dict(v=v, f=f, color=col))
views = [dict(name=f"v{int(a)}", az=a, el=0, target=c, half=half) for a in azs]
tmp = out.parent / "_pv"; tmp.mkdir(parents=True, exist_ok=True)
R.render(sc, views, tmp, size=(520, 520))
ims = [Image.open(tmp / f"{v['name']}.png").convert("RGB") for v in views]
M = Image.new("RGB", (sum(i.width for i in ims), ims[0].height), "white"); x = 0
for i in ims:
    M.paste(i, (x, 0)); x += i.width
M.save(out); print(out)
