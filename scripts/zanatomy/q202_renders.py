#!/usr/bin/env python3
"""Q202 renders: perineal region of the female pages, before / after (skin only, closure highlighted), plus escape-ray and section views.  -> build/q202_renders/ (git-ignored)"""
from __future__ import annotations

import sys
import zlib
from pathlib import Path

import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q202_pages as P  # noqa: E402
from scripts.zanatomy import q190_render as RR  # noqa: E402

OUT = REPO / "build" / "q202_renders"
CLOS = "zan_skin_perineal_closure"
VIEWS = (("front", 0, 0), ("below_front", 0, -40), ("below", 0, -80), ("side", 90, -10), ("back_low", 180, -30), ("oblique", 35, -30))


def scene(dir_, stem, hl=CLOS):
    man, blob = P.load_page(dir_, stem)
    S = P.decode(man, blob, only=lambda m: m["sys"] == "skin")
    sc = []
    for i, m in S.items():
        h = (zlib.crc32(i.encode()) % 1000) / 1000
        col = (0.30, 0.55, 0.95) if i == hl else (0.88, 0.72 + 0.16 * h, 0.60)
        sc.append({"v": m["v"], "f": m["f"], "color": col})
    return sc


def sheet(name, pages, target=(0, -70, 30), half=75):
    ims = []
    for label, (d, s) in pages:
        sc = scene(d, s)
        RR.render(sc, [dict(name=f"{v}", az=a, el=e, target=target, half=half) for v, a, e in VIEWS], OUT, prefix=f"_tmp_{label}_")
        ims.append([Image.open(OUT / f"_tmp_{label}_{v}.png") for v, _, _ in VIEWS])
    w, h = ims[0][0].size
    M = Image.new("RGB", (w * len(VIEWS), h * len(pages)), "white")
    for r, row in enumerate(ims):
        for c, im in enumerate(row):
            M.paste(im, (c * w, r * h))
    M.resize((M.width // 2, M.height // 2)).save(OUT / name)
    for f in OUT.glob("_tmp_*.png"):
        f.unlink()


if __name__ == "__main__":
    which = sys.argv[1]
    OUT.mkdir(parents=True, exist_ok=True)
    if which == "base_f":
        sheet("perineum_base_female_before_after.png", [("before", (REPO / "build/q197/viewer_base_female", "atlas_viewer_base_female")), ("after", (REPO / "build/q202/viewer_base_female", "atlas_viewer_base_female"))])
    elif which == "fit_f":
        sheet("perineum_zan_female_before_after.png", [("before", (REPO / "build/q199/viewer_zan_female", "atlas_viewer_zan_female")), ("after", (REPO / "build/q202/viewer_zan_female", "atlas_viewer_zan_female"))])
