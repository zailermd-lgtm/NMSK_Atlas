#!/usr/bin/env python3
"""Q248: quick matplotlib preview of the pelvis bones + the new ligaments of one page (inferior and sagittal projections).   python3 preview.py KEY out.png [--lig npz ...]"""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lig_pages as PG  # noqa: E402


def main(key, out, npzs, root=None):
    E = PG.load(key, root)
    bones = [i for i, e in E.items() if e["sys"] == "bone" and (i.startswith(("hip_bone", "sacrum", "coccyx")) or i in ("femur_l", "femur_r"))]
    fig, ax = plt.subplots(1, 3, figsize=(18, 6))
    views = [("inferior (looking up)", 0, 2, False), ("sagittal (right side, anterior to the right)", 2, 1, True), ("frontal", 0, 1, True)]
    lig = {}
    for n in npzs:
        z = np.load(n)
        for k in z.files:
            if k.endswith("__v"):
                lig[k[:-3]] = z[k]
    for a, (title, i, j, _) in zip(ax, views):
        for b in bones:
            v = E[b]["v"]; a.scatter(v[:, i], v[:, j], s=0.3, c="#c9bfa6", alpha=0.5)
        for k, v in lig.items():
            c = "#d33" if k.endswith("_l") or "_l_" in k else "#2a7de1"
            a.scatter(v[:, i], v[:, j], s=1.2, c=c)
        a.set_aspect("equal"); a.set_title(f"{key}: {title}")
        if i == 0 and j == 2:
            a.invert_yaxis() if False else None
    lo = np.vstack([E[b]["v"] for b in bones if b.startswith("hip")]); 
    for a in ax:
        pass
    fig.savefig(out, dpi=90, bbox_inches="tight")


if __name__ == "__main__":
    a = sys.argv[1:]
    main(a[0], a[1], a[2:])
