#!/usr/bin/env python3
"""Q215 renders (build/q215_renders, git-ignored): before / after of replaced muscles.

    python3 scripts/transfer/q215_render.py --ids vastus_intermedius_r,adductor_brevis_r,obturator_internus_r --work SCRATCH/q215/work [--old build/viewer_f_hr_q214 --new build/viewer_f_hr_q215]

Per muscle  * <id>_photo.png : three axial levels of HER registered cryosection photograph (the evidence) with the section of the OLD mesh (red dashed) and the NEW mesh (yellow), every other replaced
                               muscle thin cyan;
            * <id>_3d.png    : the muscle old | new from the front and from the side (shaded, orthographic) with her femur / hip bone as grey context.
Needs the registered photograph stack (q215_refit.py docstring)."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import trimesh
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.transfer.q200_bundle import Bundle  # noqa: E402
from scripts.cryo import vhf_thigh_refit_q181 as R  # noqa: E402


def sections(v, f, y):
    s = trimesh.Trimesh(v, f, process=False).section(plane_origin=[0, y, 0], plane_normal=[0, 1, 0])
    if s is None:
        return []
    return [s.vertices[e.points] for e in s.entities]


def to_idx(p, A):
    return (p[:, 0] + R.ORIGIN[0] - A[0, 3]) / A[0, 0], (p[:, 2] + R.ORIGIN[2] - A[1, 3]) / A[1, 1]


def photo(aid, Bo, Bn, work, replaced, out, A, nlev=3):
    side = "right" if aid.endswith("_r") else "left"
    i0, i1 = R.SIDE_I[side]
    meta = json.loads((Path(work) / f"p1_{side}.json").read_text())
    rgb = np.load(Path(work) / f"p1_{side}_rgb.npy", mmap_mode="r")
    ks = meta["ks"]
    vo, fo = Bo.mesh(Bo.items[Bo.find(aid)[0]])
    vn, fn = Bn.mesh(Bn.items[Bn.find(aid)[0]])
    lo, hi = max(vo[:, 1].min(), vn[:, 1].min(), -400), min(vo[:, 1].max(), vn[:, 1].max(), 38)
    levels = [int(round(lo + (hi - lo) * t)) for t in np.linspace(0.2, 0.8, nlev)]
    fig, axs = plt.subplots(1, nlev, figsize=(9 * nlev, 9))
    for ax, y in zip(np.atleast_1d(axs), levels):
        k = min(ks, key=lambda kk: abs(R.y_of_k(A, kk) - y))
        t = ks.index(k)
        img = np.asarray(rgb[t])
        ax.imshow(np.swapaxes(img, 0, 1), origin="upper")
        for oid in replaced:
            if oid == aid or oid[-1] != aid[-1]:
                continue
            v, f = Bn.mesh(Bn.items[Bn.find(oid)[0]])
            for loop in sections(v, f, y):
                ii, jj = to_idx(loop, A)
                ax.plot(ii - i0, jj, color="cyan", lw=0.6, alpha=0.8)
        for loop in sections(vo, fo, y):
            ii, jj = to_idx(loop, A)
            ax.plot(ii - i0, jj, color="red", lw=1.6, ls="--")
        for loop in sections(vn, fn, y):
            ii, jj = to_idx(loop, A)
            ax.plot(ii - i0, jj, color="yellow", lw=1.8)
        pts = np.vstack([np.column_stack(to_idx(l, A)) for l in sections(vo, fo, y) + sections(vn, fn, y)] or [np.zeros((1, 2))])
        ax.set_xlim(pts[:, 0].min() - i0 - 45, pts[:, 0].max() - i0 + 45)
        ax.set_ylim(pts[:, 1].max() + 45, pts[:, 1].min() - 45)
        ax.set_title(f"{aid}  y = {y} mm   red dashed = before (Q214)   yellow = after (Q215)", fontsize=11)
    plt.tight_layout()
    plt.savefig(Path(out) / f"{aid}_photo.png", dpi=55)
    plt.close(fig)


def shade(v, f, view):
    tri = v[f]
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-9)
    ax_ = {"front": 2, "side": 0}[view]
    d = n[:, ax_]
    d = np.abs(d)                       # two-sided (the winding of the pages is not uniform)
    return 0.35 + 0.65 * d


def draw(ax, v, f, view, color, alpha=1.0, flat=None):
    cols = {"front": (0, 1, 2), "side": (2, 1, 0)}[view]
    sx = -1.0 if view == "front" else 1.0
    P = np.column_stack([sx * v[:, cols[0]], v[:, cols[1]]])
    depth = v[f][:, :, cols[2]].mean(1)
    order = np.argsort(depth if view == "front" else -depth)
    sh = shade(v, f, view) if flat is None else np.full(len(f), flat)
    base = np.array(matplotlib.colors.to_rgb(color))
    fc = np.clip(base[None, :] * sh[:, None], 0, 1)
    pc = PolyCollection(P[f][order], facecolors=fc[order], edgecolors="none", alpha=alpha)
    ax.add_collection(pc)
    return P


def three_d(aid, Bo, Bn, out):
    vo, fo = Bo.mesh(Bo.items[Bo.find(aid)[0]])
    vn, fn = Bn.mesh(Bn.items[Bn.find(aid)[0]])
    side = "r" if aid.endswith("_r") else "l"
    ctx = []
    for sid in (f"femur_{side}", f"hip_bone_{side}"):
        if Bo.find(sid):
            ctx.append(Bo.mesh(Bo.items[Bo.find(sid)[0]]))
    fig, axs = plt.subplots(2, 2, figsize=(13, 14))
    for r, view in enumerate(("front", "side")):
        for c, (v, f, col, ttl) in enumerate(((vo, fo, "#d9534f", "before (Q214)"), (vn, fn, "#f0c040", "after (Q215)"))):
            ax = axs[r, c]
            for cv, cf in ctx:
                draw(ax, cv, cf, view, "#9a9a9a", alpha=0.55, flat=0.8)
            P = draw(ax, v, f, view, col)
            ax.set_aspect("equal")
            allp = np.vstack([P] + [np.column_stack([(-1.0 if view == "front" else 1.0) * cv[:, {"front": 0, "side": 2}[view]], cv[:, 1]]) for cv, _ in ctx])
            ax.set_xlim(allp[:, 0].min() - 15, allp[:, 0].max() + 15)
            ax.set_ylim(allp[:, 1].min() - 15, allp[:, 1].max() + 15)
            ax.set_title(f"{aid} {view} {ttl}  {abs(trimesh.Trimesh(v, f, process=False).volume) / 1000:.0f} cm3")
            ax.set_xticks([]); ax.set_yticks([])
    plt.tight_layout()
    plt.savefig(Path(out) / f"{aid}_3d.png", dpi=50)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ids", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--old", default=str(REPO / "build/viewer_f_hr_q214"))
    ap.add_argument("--new", default=str(REPO / "build/viewer_f_hr_q215"))
    ap.add_argument("--report", default=str(REPO / "data/derived/Q215_report.json"))
    ap.add_argument("--out", default=str(REPO / "build/q215_renders"))
    a = ap.parse_args()
    Path(a.out).mkdir(parents=True, exist_ok=True)
    Bo, Bn = Bundle(a.old), Bundle(a.new)
    import nibabel as nib
    A = nib.load(str(R.Q48_VOL)).affine
    replaced = list(json.loads(Path(a.report).read_text())["replaced"])
    for aid in a.ids.split(","):
        photo(aid, Bo, Bn, a.work, replaced, a.out, A)
        three_d(aid, Bo, Bn, a.out)
        print("rendered", aid)


if __name__ == "__main__":
    main()
