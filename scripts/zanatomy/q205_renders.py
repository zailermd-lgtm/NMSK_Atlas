"""Q205 renders: sections of Z structures over HIS full-resolution cryosection photographs (hand levels) -- before | after.
    photo_sections(crops_npz, side, models={'label': {id: (v, f, kind)}}, levels, out)   kind in bone / thumb / muscle / vessel / nerve / skin
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
COL = {"bone": ("#111111", 1.2), "thumb": ("#e00000", 1.6), "muscle": ("#b05028", 0.5), "vessel": ("#d01010", 0.8), "nerve": ("#d8b000", 0.8), "skin": ("#00c0ff", 1.0), "other": ("#7070b0", 0.5)}


def photo_sections(crops, side, models, levels, out, xwin=None, zwin=(95, 200), dpi=45):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    from scripts.zanatomy.q190_render import section_lines
    z = np.load(crops)
    si = 0 if side == "r" else 1
    X0, Y0 = z["reg"][si]
    r0, r1, c0, c1 = z[f"box_px_{side}"]
    ys = list(z["ys"])
    xwin = xwin or ((-15, 175) if side == "r" else (-175, 15))
    names = list(models)
    fig, ax = plt.subplots(len(levels), len(names), figsize=(8 * len(names), 5.4 * len(levels)), squeeze=False)
    for r, y in enumerate(levels):
        im = z[f"crop_{side}"][ys.index(int(y))]
        ext = [X0 + 6 - c0 * .33, X0 + 6 - c1 * .33, Y0 - 4.8 + r1 * .33, Y0 - 4.8 + r0 * .33]
        for c, nm in enumerate(names):
            a = ax[r, c]
            a.imshow(im, extent=ext, interpolation="nearest")
            for i, (v, f, kind) in models[nm].items():
                if v[:, 1].min() > y or v[:, 1].max() < y:
                    continue
                L = section_lines(v, f, y)
                if len(L):
                    col, w = COL.get(kind, COL["other"])
                    a.add_collection(LineCollection(L, colors=col, linewidths=w))
            a.set_xlim(*xwin)
            a.set_ylim(zwin[1], zwin[0])
            a.set_title(f"{nm}  {side.upper()} hand y={y} (his photograph; black bone, red thumb)", fontsize=9)
    plt.tight_layout()
    plt.savefig(out, dpi=dpi)
    plt.close(fig)
