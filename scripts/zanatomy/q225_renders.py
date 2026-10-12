#!/usr/bin/env python3
"""Q225 renders: the LEFT ELBOW before (Q221 / Q222 page) | after (Q225 page), bones only and bones + the elbow soft tissue, both Z-fitted pages -> build/q225_renders/ (git-ignored) and, small,
data/derived/Q225_render_<name>.png.   python3 scripts/zanatomy/q225_renders.py [male female]"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q225_core as K5  # noqa: E402
from scripts.zanatomy import q190_render as R  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

OUT = REPO / "build" / "q225_renders"
DER = REPO / "data" / "derived"
CREAM, BLUE, MAG, RED, GREY = (0.93, 0.91, 0.80), (0.30, 0.50, 0.85), (0.95, 0.05, 0.75), (0.80, 0.25, 0.20), (0.62, 0.62, 0.66)


def scene(pg, soft, c, half):
    sc = []
    for i in K5.ELBOW_L:
        sc.append({"v": pg.v(i), "f": pg.f(i), "color": {"humerus_l": CREAM, "radius_l": BLUE, "ulna_l": MAG}[i]})
    if soft:
        for i in pg.ids:
            s = pg.sys(i)
            if s not in ("muscle", "vessel", "nerve") or not i.endswith("_l"):
                continue
            v = pg.v(i)
            if np.linalg.norm(v.mean(0) - c) > 110:
                continue
            f = pg.f(i)
            keep = np.linalg.norm(v[f].mean(1) - c, axis=1) < half
            if keep.sum() > 1:
                sc.append({"v": v, "f": f[keep], "color": RED if s == "muscle" else GREY})
    return sc


def montage(name, title, lines, rows, size=520):
    ims = []
    for sc, views, d in rows:
        R.render(sc, views, d, size=(size, size))
        ims.append([Image.open(d / f"{v['name']}.png").convert("RGB") for v in views])
    W = Image.new("RGB", (size * len(ims[0]), size * len(ims) + 70), (255, 255, 255))
    for r, row in enumerate(ims):
        for k, im in enumerate(row):
            W.paste(im, (size * k, 70 + size * r))
    dr = ImageDraw.Draw(W)
    dr.text((8, 6), title, fill=(0, 0, 0))
    for i, t in enumerate(lines):
        dr.text((8, 24 + 14 * i), t, fill=(120, 0, 0))
    W.save(OUT / f"{name}.png")
    W.resize((W.width * 2 // 3, W.height * 2 // 3), Image.LANCZOS).save(DER / f"Q225_render_{name}.png", optimize=True)
    print(name, "done", flush=True)


def run(which):
    cfg = K5.PAGES[which]
    before, after = K5.load(which), K5.load(which, src=cfg["out"])
    hv = before.v("humerus_l")
    c = hv[hv[:, 1] < hv[:, 1].min() + 25].mean(0)
    half = 95
    views = [dict(name="lateral", az=-90, el=0, target=c, half=half), dict(name="anterior", az=0, el=0, target=c, half=half), dict(name="posterior", az=180, el=15, target=c, half=half)]
    rows = []
    for tag, pg in (("before", before), ("after", after)):
        for soft in (False, True):
            d = OUT / f"{which}_{tag}_{'soft' if soft else 'bones'}"
            rows.append((scene(pg, soft, c, half + 15), [dict(v) for v in views], d))
    OUT.mkdir(parents=True, exist_ok=True)
    nm = {"male": "his", "female": "her"}[which]
    montage(f"{which}_left_elbow_before_after", f"Z fitted to {nm} reconstruction | LEFT elbow: rows = before (Q221/Q222 page) bones, before + soft tissue, AFTER (Q225) bones, after + soft tissue",
            ["cream = humerus, blue = radius, magenta = ulna; red = muscles, grey = vessels / nerves (left arm, within 110 mm of the joint)."], rows)


if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    for w in (sys.argv[1:] or ["male", "female"]):
        run(w)
