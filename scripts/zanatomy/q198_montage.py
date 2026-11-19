#!/usr/bin/env python3
"""Q198 montages of the elbow close-ups: per side across the six models, and per model with both arms. python3 scripts/zanatomy/q198_montage.py [--hl]"""
import sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "build" / "q198_renders"
MODELS = [("own_m", "Own male"), ("own_f", "Own female"), ("z_male", "Z male base"), ("z_base_f", "Z generic (female variant)"), ("z_male_fit", "Z fitted to his reconstruction"), ("z_female_fit", "Z fitted to her reconstruction")]
VIEWS = ["anterior", "posterior", "medial", "lateral", "sagittal", "coronal"]
hl = "--hl" in sys.argv
tag = "_hl" if hl else ""
try:
    F = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 15); FB = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16)
except Exception:
    F = FB = ImageFont.load_default()
W = H = 400


def tile(model, side, view):
    p = OUT / model / f"elbow_{side}_{view}{tag}.png"
    if not p.exists():
        im = Image.new("RGB", (W, H), (235, 235, 235)); d = ImageDraw.Draw(im)
        d.text((12, H // 2 - 10), "no elbow bones in this model" if view == "anterior" else "n/a", fill=(120, 0, 0), font=F)
        return im
    im = Image.open(p).convert("RGB"); im.thumbnail((W, H)); bg = Image.new("RGB", (W, H), (255, 255, 255)); bg.paste(im, ((W - im.width) // 2, (H - im.height) // 2)); return bg


def sheet(rows, title, fname):
    LW, TH = 190, 54
    img = Image.new("RGB", (LW + W * len(VIEWS), TH + H * len(rows)), (255, 255, 255)); d = ImageDraw.Draw(img)
    d.text((8, 6), title, fill=(0, 0, 0), font=FB)
    for ci, v in enumerate(VIEWS):
        d.text((LW + ci * W + 8, TH - 22), v, fill=(40, 40, 40), font=F)
    for ri, (label, model, side) in enumerate(rows):
        d.text((6, TH + ri * H + 8), label, fill=(0, 0, 0), font=FB)
        d.text((6, TH + ri * H + 30), f"{'left' if side=='l' else 'right'} arm", fill=(60, 60, 60), font=F)
        for ci, v in enumerate(VIEWS):
            img.paste(tile(model, side, v), (LW + ci * W, TH + ri * H))
    img.thumbnail((3000, 3000)); img.save(OUT / fname, optimize=True)
    print("wrote", fname, img.size)


leg = " (orange = moderate, magenta = major defect structures)" if hl else ""
for side in ("l", "r"):
    sheet([(lab, m, side) for m, lab in MODELS], f"ELBOW, {'LEFT' if side=='l' else 'RIGHT'} arm, six models{leg}", f"elbow_{side}_all_models{tag}.png")
for m, lab in MODELS:
    sheet([(lab, m, "l"), (lab, m, "r")], f"{lab}: elbow, both arms{leg}", f"model_{m}_elbow{tag}.png")
