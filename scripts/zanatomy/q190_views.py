"""Q190 audit renders: close-ups of the lumbar / sacral / gluteal / hip / flank region, her own model vs a Z-Anatomy female build."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q190_render as R  # noqa: E402

COL = {"skin": (0.90, 0.74, 0.64), "muscle": (0.78, 0.22, 0.20), "her_muscle": (0.80, 0.45, 0.15), "bone": (0.92, 0.9, 0.80),
       "fascia": (0.55, 0.65, 0.80), "nerve": (0.95, 0.85, 0.2), "vessel": (0.2, 0.35, 0.85), "her_bone": (0.8, 0.85, 0.7)}
VIEWS = {   # name: (az, el, target, half)
    "back": (180, 0, (0, 70, -60), 230),
    "back_obl": (210, 15, (0, 70, -60), 230),
    "side_R": (90, 0, (0, 70, -60), 230),
    "above": (180, 60, (0, 70, -60), 230),
    "below": (180, -50, (0, 20, -60), 230),
    "sacrum": (180, 0, (0, 20, -80), 120),
    "lumbar": (180, 0, (0, 190, -80), 130),
    "glut_obl": (150, 10, (80, 30, -60), 140),
    "flank": (120, 5, (110, 130, -40), 160),
}


def render_set(scene, tag, out, names=None, size=(640, 640)):
    names = names or list(VIEWS)
    views = [{"name": n, "az": VIEWS[n][0], "el": VIEWS[n][1], "target": VIEWS[n][2], "half": VIEWS[n][3]} for n in names]
    R.render(scene, views, out, size=size, prefix=tag + "_")


def montage(files, labels, dest, w=640):
    from PIL import Image, ImageDraw
    ims = [Image.open(f).convert("RGB") for f in files]
    W = sum(i.width for i in ims); H = max(i.height for i in ims) + 22
    M = Image.new("RGB", (W, H), "white"); d = ImageDraw.Draw(M); x = 0
    for im, lb in zip(ims, labels):
        M.paste(im, (x, 22)); d.text((x + 6, 5), lb, fill=(0, 0, 0)); x += im.width
    M.save(dest)
