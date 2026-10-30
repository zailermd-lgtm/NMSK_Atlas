#!/usr/bin/env python3
"""Q203: montage of before / after renders.  q203_montage.py OUT.png TITLE ROW1_PREFIX_GLOB ... (each row = one png list sorted by name)"""
import sys
from pathlib import Path
from PIL import Image, ImageDraw
out, title = sys.argv[1], sys.argv[2]
rows = [sorted(Path().glob(g)) for g in sys.argv[3:]]
ims = [[Image.open(p).convert("RGB") for p in r] for r in rows]
w = max(i.width for r in ims for i in r); h = max(i.height for r in ims for i in r)
cols = max(len(r) for r in ims)
M = Image.new("RGB", (w * cols, h * len(ims) + 24), "white")
ImageDraw.Draw(M).text((6, 6), title, fill="black")
for r, row in enumerate(ims):
    for c, im in enumerate(row):
        M.paste(im, (c * w, 24 + r * h))
M.save(out); print(out, M.size)
