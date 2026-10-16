#!/usr/bin/env python3
"""Q213 renders (build/q213_renders, git-ignored): BEFORE (blue dashed) over AFTER (red) axial sections of corrected muscles with the bones (black) of the page, one panel per level.

    python3 scripts/clinical/q213_render_overlay.py --a zan_f --b zan_f_q213 --ids adductor_magnus_r,adductor_brevis_r --out PATH [--levels auto|y1,y2,...] [--pad 25]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import q213_render as R  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True)
    ap.add_argument("--b", required=True)
    ap.add_argument("--ids", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--levels", default="auto")
    ap.add_argument("--pad", type=float, default=25.0)
    ap.add_argument("--n", type=int, default=3)
    a = ap.parse_args()
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    A, B = R.get(a.a), R.get(a.b)
    ids = a.ids.split(",")
    ids = [i for i in ids if i in A and i in B and len(A[i]["v"]) == len(B[i]["v"])]
    if a.levels == "auto":
        lv = []
        for i in ids:
            d = np.linalg.norm(A[i]["v"] - B[i]["v"], axis=1)
            top = A[i]["v"][np.argsort(-d)[: max(5, len(d) // 20)]]
            lv.append(float(np.median(top[:, 1])))
        lv = sorted(set(round(x / 10) * 10 for x in lv))[: a.n]
    else:
        lv = [float(x) for x in a.levels.split(",")]
    fig, axs = plt.subplots(1, len(lv), figsize=(6.2 * len(lv), 6.4), squeeze=False)
    for ax, y in zip(axs[0], lv):
        allp = []
        for i in ids:
            for M_, col, ls, lw in ((A, "tab:blue", "--", 1.0), (B, "red", "-", 1.3)):
                segs = R.section(M_[i]["v"], M_[i]["f"], y)
                for p, q in segs:
                    ax.plot([p[0], q[0]], [p[2], q[2]], ls, color=col, lw=lw)
                    allp += [p, q]
        if not allp:
            continue
        P = np.array(allp)
        x0, x1 = P[:, 0].min() - a.pad, P[:, 0].max() + a.pad
        z0, z1 = P[:, 2].min() - a.pad, P[:, 2].max() + a.pad
        for sid, d in B.items():
            if d["cat"] != "bone":
                continue
            v = d["v"]
            if v[:, 1].min() > y or v[:, 1].max() < y or v[:, 0].max() < x0 or v[:, 0].min() > x1:
                continue
            for p, q in R.section(v, d["f"], y):
                ax.plot([p[0], q[0]], [p[2], q[2]], "-", color="k", lw=1.4)
        ax.set_xlim(x0, x1); ax.set_ylim(z0, z1); ax.set_aspect("equal")
        ax.set_title(f"y = {y:g}   blue dashed = {a.a}, red = {a.b}   ({', '.join(ids)[:60]})", fontsize=7)
    fig.tight_layout()
    fig.savefig(a.out, dpi=105)
    print(a.out, lv)


if __name__ == "__main__":
    main()
