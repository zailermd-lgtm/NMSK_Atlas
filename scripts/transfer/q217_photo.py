"""Q217: HIS cryosection photographs of the left (or right) arm as a registered 3-D tissue-class volume in the atlas frame.

Photographs = `SCRATCH/vh_cryo/cryo_1mm.npy` (1878 axial RGB slices, 1 mm apart, 0.99 mm pixels), colour classes = `cryo_classes.classify` (1 tissue, 2 fat, 3 muscle, 4 pale connective, 5 white).
Registration = `data/derived/Q185a2_arm_skin_registration_vhm.json` (per slice and per side a translation T = (X0, Y0)):
    atlas x = X0 - col * 0.99 + 6.0     atlas z = Y0 + row * 0.99 - 4.8     atlas y = 1880.4 - instance      (the same mapping as q201_renders.photo_sections)
The volume is resampled to a 1 mm atlas grid (nearest neighbour in-plane, one photograph per integer y)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
CRYO = REPO / "SCRATCH" / "vh_cryo"
REG = REPO / "data" / "derived" / "Q185a2_arm_skin_registration_vhm.json"
PX = 0.99
Y_OFF = 1880.4

TISSUE, FAT, MUSCLE, PALE, WHITE = 1, 2, 3, 4, 5


def classify(im):
    sys.path.insert(0, str(CRYO))
    from cryo_classes import classify as c
    return c(im)


class Photos:
    """class volume of one side: cls[i, j, k] at atlas (x0 + i, y0 + j, z0 + k) mm, 0 = no photograph / gelatin"""

    def __init__(self, side="l", x=(-300.0, -100.0), y=(90.0, 372.0), z=(-130.0, 200.0)):
        self.side = side
        self.lo = np.array([np.floor(x[0]), np.floor(y[0]), np.floor(z[0])])
        self.shape = (int(x[1] - x[0]) + 1, int(y[1] - y[0]) + 1, int(z[1] - z[0]) + 1)
        reg = json.loads(REG.read_text())["sides"]["left" if side == "l" else "right"]["levels"]
        vol = np.load(CRYO / "cryo_1mm.npy", mmap_mode="r")
        idx = json.loads((CRYO / "cryo_index.json").read_text())
        inst = {r[1]: i for i, r in enumerate(idx)}
        self.cls = np.zeros(self.shape, np.uint8)
        self.reliable = np.zeros(self.shape[1], bool)
        xs = self.lo[0] + np.arange(self.shape[0])
        zs = self.lo[2] + np.arange(self.shape[2])
        for j in range(self.shape[1]):
            y_ = self.lo[1] + j
            k = int(round(Y_OFF - y_))
            if str(k) not in reg or k not in inst:
                continue
            X0, Y0 = reg[str(k)]["T"]
            self.reliable[j] = bool(reg[str(k)].get("reliable"))
            im = np.asarray(vol[inst[k]])
            c = classify(im)
            col = np.rint((X0 + 6.0 - xs) / PX).astype(int)
            row = np.rint((zs + 4.8 - Y0) / PX).astype(int)
            okc = (col >= 0) & (col < c.shape[1])
            okr = (row >= 0) & (row < c.shape[0])
            sub = c[np.ix_(np.clip(row, 0, c.shape[0] - 1), np.clip(col, 0, c.shape[1] - 1))]       # [z, x]
            sub = sub * (okr[:, None] & okc[None, :])
            self.cls[:, j, :] = sub.T

    def at(self, P):
        """class at atlas points (0 outside)"""
        i = np.rint(np.asarray(P, float) - self.lo).astype(np.int64)
        ok = ((i >= 0) & (i < np.asarray(self.shape))).all(1)
        out = np.zeros(len(P), np.uint8)
        out[ok] = self.cls[i[ok, 0], i[ok, 1], i[ok, 2]]
        return out
