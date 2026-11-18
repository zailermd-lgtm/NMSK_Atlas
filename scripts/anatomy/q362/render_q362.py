#!/usr/bin/env python3
"""Q362: offline renders of the transferred organs in context (no browser): bones + neighbours + the new meshes, front / lateral / inferior,
before (page without them) and after (the page after the apply).  Flat-shaded matplotlib, orthographic.

    python3 scripts/anatomy/q362/render_q362.py --page-dir DIR --out OUTDIR [--ids a,b] [--tag after]"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt                      # noqa: E402
import numpy as np                                    # noqa: E402
from mpl_toolkits.mplot3d.art3d import Poly3DCollection  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import transfer_organs_q362 as T                     # noqa: E402

COL = {"bone": "#d9d2c0", "viscera": "#c98a7a", "muscle": "#b5474a", "vessel": "#a33", "new": "#2a7fd4", "new_m": "#1f9e5a"}
VIEWS = {"front": (0, -90), "lateral_right": (0, 0), "inferior": (-90, -90)}


def shade(v, f, rgb):
    n = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
    n /= np.linalg.norm(n, axis=1, keepdims=True) + 1e-12
    lam = 0.45 + 0.55 * np.abs(n @ np.array([0.3, 0.5, 0.8]) / np.linalg.norm([0.3, 0.5, 0.8]))
    c = np.clip(np.array(matplotlib.colors.to_rgb(rgb))[None] * lam[:, None], 0, 1)
    return c


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--page-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--ids", default=None, help="the new ids to show (default: every Q362 id on the page)")
    ap.add_argument("--context", default=None, help="extra context ids (comma)")
    ap.add_argument("--box", default=None, help="xmin,xmax,ymin,ymax,zmin,zmax (default: around the new meshes + 60 mm)")
    ap.add_argument("--tag", default="after")
    ap.add_argument("--name", default=None)
    ap.add_argument("--npz", default=None, help="dir of <id>.npz meshes (a dry run's --dump-dir) shown as the new meshes")
    a = ap.parse_args(argv)
    d = Path(a.page_dir).resolve(); key = T.DIRKEY[d.name]
    man, blob, files, E = T.read_page(d, T.STEM[key])
    allnew = [o["id"] for o in T.ORGANS if o["key"] == key]
    if a.npz:
        sysof = {o["id"]: o["sys"] for o in T.ORGANS}
        for i in (a.ids.split(",") if a.ids else allnew):
            f_ = Path(a.npz) / f"{i}.npz"
            if f_.exists() and i not in E:
                z = np.load(f_)
                E[i] = dict(v=_swap(z["v"]), f=z["f"], sys=sysof[i], name=i)
    new = [i for i in (a.ids.split(",") if a.ids else allnew) if i in E]
    ref = new or [i for i in (a.ids or "").split(",") if i]
    if a.box:
        b = np.array([float(x) for x in a.box.split(",")]).reshape(3, 2)
        lo, hi = b[[0, 2, 1], 0], b[[0, 2, 1], 1]          # atlas (x, y, z) -> plotted (x, z, y)
    else:
        P = np.vstack([E[i]["v"] for i in new]) if new else np.zeros((1, 3))
        lo, hi = P.min(0) - 60, P.max(0) + 60
    ctx = set((a.context or "").split(",")) - {""}
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    for vname, (el, az) in VIEWS.items():
        fig = plt.figure(figsize=(7, 7), dpi=110)
        ax = fig.add_subplot(111, projection="3d"); ax.set_proj_type("ortho")
        for k, e in E.items():
            sys_ = e["sys"]
            isnew = k in new
            if not isnew and not (sys_ == "bone" or k in ctx):
                continue
            v, f = e["v"], e["f"]
            c = v[f].mean(1)
            keep = np.all((c > lo) & (c < hi), axis=1)
            if vname.startswith("lateral") and not isnew:      # a mid-sagittal cut: the near (right) half of the context is left out
                keep &= c[:, 0] < 2.0
            if not keep.any():
                continue
            f = f[keep]
            col = COL["new"] if isnew and e["sys"] == "viscera" else COL["new_m"] if isnew else COL.get(sys_, "#999")
            pc = Poly3DCollection(v[f], facecolors=shade(v, f, col), edgecolors="none", alpha=1.0 if isnew or sys_ == "bone" else 0.55)
            ax.add_collection3d(pc)
        # plotted frame (x right, y anterior, z up): the atlas (+X right, +Y up, +Z anterior) swapped on read
        ax.set_xlim(lo[0], hi[0]); ax.set_ylim(lo[1], hi[1]); ax.set_zlim(lo[2], hi[2])
        ax.set_box_aspect(tuple(hi - lo))
        ax.view_init(elev=el, azim=az)
        ax.set_axis_off()
        ax.set_title(f"{a.name or d.name} {a.tag} {vname}: {', '.join(new) if new else '(none)'}"[:110], fontsize=7)
        fn = out / f"{a.name or key}_{a.tag}_{vname}.png"
        fig.savefig(fn, bbox_inches="tight"); plt.close(fig)
        print(fn)
    return 0


def _swap(v):
    return v[:, [0, 2, 1]]


if __name__ == "__main__":
    # matplotlib's z is up: feed (x, z, y)
    _orig = T.read_page

    def _rp(d, stem):
        man, blob, files, E = _orig(d, stem)
        for e in E.values():
            e["v"] = _swap(e["v"])
        return man, blob, files, E
    T.read_page = _rp
    sys.exit(main())
