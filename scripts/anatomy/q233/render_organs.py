#!/usr/bin/env python3
"""Q233: point-cloud render (front / side / top) of the added female organs inside her pelvis from a built page -> PNG.   python3 scripts/anatomy/q233/render_organs.py PAGE_KEY OUT.png [PAGE_DIR]"""
import os, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "anatomy"))
import numpy as np, matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
import q233_load as Q
key, out = sys.argv[1:3]
if len(sys.argv) > 3: os.environ["Q233_SRC_" + key] = sys.argv[3]
S = Q.load(key); by = {}
for x in S: by.setdefault(x["id"], x)
cols = {"uterus": "m", "ovary_l": "r", "ovary_r": "r", "uterine_tube_l": "orange", "uterine_tube_r": "orange"}
fig, ax = plt.subplots(1, 3, figsize=(24, 9))
for i, (ix, iy, t) in enumerate(((0, 1, "front (x, y)"), (2, 1, "side (z, y)"), (0, 2, "top (x, z)"))):
    for k in ("hip_bone_l", "hip_bone_r", "sacrum#1", "sacrum", "urinary_bladder", "zan_urinary_bladder", "rectum"):
        if k in by:
            v = by[k]["v"][::3]; ax[i].scatter(v[:, ix], v[:, iy], s=0.3, c="lightgray" if ("bone" in k or "sacrum" in k) else ("c" if "blad" in k else "g"))
    for k, c in cols.items():
        if k in by:
            v = by[k]["v"][::2]; ax[i].scatter(v[:, ix], v[:, iy], s=1.2, c=c)
    ax[i].set_aspect("equal"); ax[i].set_title(f"{key}: {t}")
    ax[i].set_xlim(-130, 130) if ix == 0 else ax[i].set_xlim(-130, 80)
    if iy == 1: ax[i].set_ylim(-70, 100)
plt.savefig(out, dpi=50)
