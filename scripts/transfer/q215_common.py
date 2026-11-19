"""Q215 shared helpers: her Q48 septa label volume (her own thigh / hip compartments) addressed in atlas coordinates, bundle / Z page loaders, the target list."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import nibabel as nib

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "clinical"))

SRC_BUNDLE = REPO / "build/viewer_f_hr_q214"
SRC_PAGE = REPO / "build/q214/viewer_f_hr"
Z_PAGE = REPO / "build/q213/viewer_zan_female/atlas_viewer_zan_female.html"
OUT_BUNDLE = REPO / "build/viewer_f_hr_q215"
OUT_PAGE = REPO / "build/q215/viewer_f_hr"
SEPTA = REPO / "data/ct_sources/task_outputs/vhf_xfer_lowerlimb_septa.nii.gz"
SEPTA_LABELS = REPO / "mappings/vhf_xfer_septa_labels.json"
ORIGIN = (7.769, -885.229, 14.137)          # atlas frame -> her torso RAS (see refine_transfer_to_septa.py)

# hip / thigh / gluteal / pelvic-floor-adjacent muscles of the 52 male-carried target sides (Q213_target_muscle_audit.json own_cls == transferred)
HIP_THIGH = ["obturator_internus", "piriformis", "adductor_brevis", "adductor_longus", "adductor_magnus", "gracilis", "sartorius", "tensor_fasciae_latae",
             "rectus_femoris", "vastus_lateralis", "vastus_medialis", "vastus_intermedius", "biceps_femoris", "semitendinosus", "semimembranosus"]


class Septa:
    """her Q48 label volume (1 mm, her own septa-refined thigh / hip muscle regions) addressed by atlas coordinates"""

    def __init__(self):
        im = nib.load(SEPTA)
        self.D = np.asanyarray(im.dataobj)
        self.A = im.affine
        self.labels = {int(k): v for k, v in json.loads(SEPTA_LABELS.read_text())["labels"].items()}
        self.id2lab = {v: k for k, v in self.labels.items()}

    def index(self, P):
        ox, oy, oz = ORIGIN
        P = np.asarray(P, float)
        i = np.rint(self.A[0, 3] - ox - P[:, 0]).astype(np.int64)
        j = np.rint(self.A[1, 3] - oz - P[:, 2]).astype(np.int64)
        k = np.rint(P[:, 1] + oy - self.A[2, 3]).astype(np.int64)
        return i, j, k

    def lookup(self, P):
        """label id (0 = none / outside the volume) at atlas points"""
        i, j, k = self.index(P)
        ok = (i >= 0) & (i < self.D.shape[0]) & (j >= 0) & (j < self.D.shape[1]) & (k >= 0) & (k < self.D.shape[2])
        out = np.zeros(len(P), np.int32)
        out[ok] = self.D[i[ok], j[ok], k[ok]]
        return out

    def points(self, sid):
        """atlas coordinates of the voxel centres of one muscle's label"""
        ox, oy, oz = ORIGIN
        if sid not in self.id2lab:
            return np.zeros((0, 3))
        ijk = np.argwhere(self.D == self.id2lab[sid])
        return np.column_stack([self.A[0, 3] - ox - ijk[:, 0], ijk[:, 2] + self.A[2, 3] - oy, self.A[1, 3] - oz - ijk[:, 1]])


def load_z():
    import motor_points_q187 as MP
    MP.VIEWERS["_q215z"] = {"kind": "zan", "html": Z_PAGE, "label": "z"}
    return MP.load_viewer("_q215z")
