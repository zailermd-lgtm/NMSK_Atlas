"""Q205 (male): both HANDS of the Z-Anatomy model fitted to the VISIBLE HUMAN MALE re-fitted per bone chain on HIS evidence.

Why: Q204 measured the Q195 hand fit: the first metacarpal -> proximal phalanx gap is 81.8 (L) / 88.7 (R) mm (0.1 mm in the Z source), the thumb bones lie 20-50 mm outside his skin,
the 5th CMC joint is open 4.1 mm, the right first / fifth metacarpal sit 8-9 mm off his CT hand labels (Q191's per-piece fit onto his COMPOSITE meshes).
Evidence = his CT hand-bone labels (data/derived/Q205_his_hand_labels.npz: carpals / metacarpals / phalanges / radius / ulna label voxels of
vhm_arm_bones_cryo_completed.nii.gz in atlas mm; the carpal / metacarpal / phalanx split is a plane cut, so the labels are used as ONE bone mass) + his CT skin as the envelope.
Method = the Q192 stages (q192_left_hand: rigid hand body about the wrist, rays 2-5 MCP / PIP / DIP hinges, thumb CMC + MCP + IP, both signs, bone-bone collision, skin containment)
started from the Q201 state, aimed at his labels instead of her photographs.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
LABELS = REPO / "data" / "derived" / "Q205_his_hand_labels.npz"


def load_labels(side):
    z = np.load(LABELS)
    return {k: z[f"{k}_{side}"].astype(np.float64) for k in ("carp", "mc", "ph", "radius", "ulna")}


class HisEnvelope:
    """his CT skin as a signed-distance field (>0 inside) around one hand; same pen() as q192_left_hand.Envelope"""

    def __init__(self, skin, side, h=1.5, pad=45.0, log=print):
        from scripts.zanatomy.q191_left_trial import SkinSDF
        L = load_labels(side)
        P = np.vstack([L["carp"], L["mc"], L["ph"]])
        lo, hi = P.min(0) - pad, P.max(0) + pad
        self.sdf = SkinSDF(skin, cKDTree(np.asarray(skin.vertices, float)), lo, hi, h=h)
        self.lo, self.hi = lo, hi

    def __call__(self, P):
        return self.sdf(P)

    def pen(self, A, depth=2.5, w=0.35):
        return w * float(np.mean(np.maximum(0.0, depth - self.sdf(A)) ** 2))
