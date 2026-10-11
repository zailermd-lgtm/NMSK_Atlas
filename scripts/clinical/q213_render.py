#!/usr/bin/env python3
"""Q213 renders (build/q213_renders, git-ignored): axial sections of two female pages side by side
(own female | Z fitted to her), muscles coloured and labelled, bones black, skin grey, motor points as stars.

    python3 scripts/clinical/q213_render.py --y -200 --x0 20 --x1 190 [--a vhf --b zan_f] [--out PATH]
"""
from __future__ import annotations

import argparse
import json
import pickle
import re
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import q213_audit as Q  # noqa: E402
import motor_points_q187 as M  # noqa: E402

REPO = M.REPO
CACHE = {}


def get(key):
    if key not in CACHE:
        CACHE[key] = Q.load(key)[0]
    return CACHE[key]


def section(v, f, y):
    d = v[:, 1] - y
    fd = d[f]
    sel = (fd.min(1) <= 0) & (fd.max(1) > 0)
    if not sel.any():
        return []
    F = f[sel]
    out = []
    for a, b, c in F:
        pts = []
        for p, q in ((a, b), (b, c), (c, a)):
            dp, dq = d[p], d[q]
            if (dp <= 0) != (dq <= 0):
                t = dp / (dp - dq)
                pts.append(v[p] + t * (v[q] - v[p]))
        if len(pts) == 2:
            out.append(pts)
    return out


def panel(ax, key, y, x0, x1, mpkey, label_muscles=True, hl=()):
    me = get(key)
    import matplotlib.pyplot as plt
    cm = plt.get_cmap("tab20")
    k = 0
    for sid, d in me.items():
        cat = "skin" if sid == "skin" else d["cat"]
        if cat not in ("muscle", "bone", "skin"):
            continue
        v = d["v"]
        if v[:, 1].min() > y or v[:, 1].max() < y or v[:, 0].max() < x0 - 20 or v[:, 0].min() > x1 + 20:
            continue
        segs = section(v, d["f"], y)
        if not segs:
            continue
        col = "k" if cat == "bone" else ("0.65" if cat == "skin" else cm(abs(hash(re.sub(r"_(r|l)(_zfill\w*)?$", "", sid))) % 20))
        lw = 1.6 if cat == "bone" else (1.0 if cat == "skin" else 0.9)
        if sid in hl:
            col, lw = "red", 1.8
        for p, q in segs:
            ax.plot([p[0], q[0]], [p[2], q[2]], "-", color=col, lw=lw)
        if cat == "muscle" and label_muscles and x0 <= np.array([p for s_ in segs for p in s_])[:, 0].mean() <= x1:
            P = np.array([p for s in segs for p in s])
            ax.text(P[:, 0].mean(), P[:, 2].mean(), re.sub(r"^zan_|_muscle|_(r|l)(_zfill\w*)?$", "", sid)[:14], fontsize=5, ha="center", color="0.15")
    mp = json.loads((REPO / "clinical/data/motor_points.json").read_text())["viewers"].get(mpkey, {"points": []})
    for p in mp["points"]:
        if abs(p["pos"][1] - y) < 8 and x0 <= p["pos"][0] <= x1:
            ax.plot(p["pos"][0], p["pos"][2], "*", color="magenta", ms=7)
    ax.set_xlim(x0, x1)
    ax.set_aspect("equal")
    ax.invert_xaxis() if False else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--y", type=float, required=True)
    ap.add_argument("--x0", type=float, default=-190)
    ap.add_argument("--x1", type=float, default=190)
    ap.add_argument("--a", default="vhf")
    ap.add_argument("--b", default="zan_f")
    ap.add_argument("--out", default=None)
    ap.add_argument("--hl", default="")
    a = ap.parse_args()
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axs = plt.subplots(1, 2, figsize=(14, 7))
    hl = tuple(a.hl.split(",")) if a.hl else ()
    for ax, k, t in ((axs[0], a.a, f"{a.a}"), (axs[1], a.b, f"{a.b}")):
        panel(ax, k, a.y, a.x0, a.x1, k if k in ("vhf", "zan_f") else "vhf", hl=hl)
        ax.set_title(f"{t}  y={a.y:g} (x right +, z up = anterior)", fontsize=8)
    out = a.out or str(REPO / f"build/q213_renders/sec_{a.a}_{a.b}_y{int(a.y)}.png")
    fig.tight_layout()
    fig.savefig(out, dpi=110)
    print(out)


if __name__ == "__main__":
    main()
