#!/usr/bin/env python3
"""Q200: montage of the elbow renders of one model (rows = left/right arm, columns = views).  q200_montage.py DIR/MODEL OUT.png [TITLE]"""
import sys
from pathlib import Path
from PIL import Image, ImageDraw
d = Path(sys.argv[1]); out = sys.argv[2]
views = ["anterior", "posterior", "medial", "lateral", "sagittal", "coronal"]
rows = [s for s in "lr" if (d / f"elbow_{s}_anterior.png").exists()]
ims = [[Image.open(d / f"elbow_{s}_{v}.png").convert("RGB") for v in views] for s in rows]
w = max(i.width for r in ims for i in r); h = max(i.height for r in ims for i in r)
M = Image.new("RGB", (w * len(views), h * len(rows) + 24), "white")
dr = ImageDraw.Draw(M)
dr.text((6, 6), (sys.argv[3] if len(sys.argv) > 3 else d.name) + "   columns: " + " | ".join(views) + "   rows: " + " / ".join("left" if s == "l" else "right" for s in rows), fill="black")
for r, row in enumerate(ims):
    for c, im in enumerate(row):
        M.paste(im, (c * w, 24 + r * h))
M.save(out)
print(out, M.size)
