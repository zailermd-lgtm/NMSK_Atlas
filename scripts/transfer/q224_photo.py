"""Q224: his cryosection photographs (1 mm stack SCRATCH/vh_cryo/cryo_1mm.npy) sampled at atlas points, with the Q174 / Q173 mapping of scripts/cryo/vhm_stream_leg_crops.py + vhm_femoral_popliteal_track.py register().

    photo index zi = round(-16 - (y + oy));  RASx = x + ox, RASy = z + oz;  frame col c = X0s - RASx, row r = Y0s - RASy  (row 0 anterior)
    1 mm photo row = (H - 1) - (r - RS) / SC,  col = (c - CB - CS) / SC;  X0s = X0 + dc * SC / 3, Y0s = Y0 - dr * SC / 3  with the Q173 per-side registration (right 7.23 / 0.03, left 7.01 / -7.17 crop px).
It is an EVIDENCE CHECK at 1 mm (a vein is 8-16 mm wide), not the 0.33 mm tracker of Q174."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
H, SC = 405, 0.99
RS, CS, CB = 4.0, -96.0, 0.0
X0 = 240.0 + 2.72
Y0 = (-239.0625 + 479.0) - 0.89
ORIGIN = (-6.035, -895.476, 4.787)
REG = {"right": (7.23, 0.03), "left": (7.01, -7.17)}


class Photos:
    def __init__(self, stack=REPO / "SCRATCH/vh_cryo/cryo_1mm.npy"):
        self.a = np.load(stack, mmap_mode="r")

    @staticmethod
    def index(y):
        return int(round(-16 - (y + ORIGIN[1])))

    @staticmethod
    def to_px(P, side):
        """atlas points (n, 3) -> (row, col) in the 1 mm photograph of their own level"""
        dr, dc = REG[side]
        X0s, Y0s = X0 + dc * SC / 3.0, Y0 - dr * SC / 3.0
        rasx, rasy = P[:, 0] + ORIGIN[0], P[:, 2] + ORIGIN[2]
        c, r = X0s - rasx, Y0s - rasy
        return (H - 1) - (r - RS) / SC, (c - CB - CS) / SC

    def slice(self, y):
        zi = self.index(y)
        return np.asarray(self.a[zi])

    def crop(self, y, side, centre_xz, half=40.0):
        """RGB crop around an atlas (x, z) at level y -> (image, function atlas (x, z) -> crop px (row, col))"""
        im = self.slice(y)
        P = np.array([[centre_xz[0], y, centre_xz[1]]])
        r0, c0 = self.to_px(P, side)
        r0, c0, h = int(round(float(r0[0]))), int(round(float(c0[0]))), int(round(half / SC))
        sub = im[max(r0 - h, 0): r0 + h, max(c0 - h, 0): c0 + h]
        off = (max(r0 - h, 0), max(c0 - h, 0))
        return sub, off
