"""Q211 bones: small evidence-bounded re-seats of Z bones whose Q198 junction gap is larger than the person's OWN measured bones show (own CT / cryosection meshes of the Q203 own-model pages are the evidence).
Every move is a smooth axial displacement field of the Z bone (the Z mesh is bent / stretched, never replaced):
    d(v) = delta * axis * smoothstep((t - t0) / (1 - t0)),   t = position along the bone's long axis from the fixed end (0) to the moving end (1)
 (a) male LEFT tibia + fibula: the Z fit is 5.9 mm SHORTER than his own tibia (proximal ends equal, distal ends 5.8 mm apart) and the ankle joint space is 5.8 mm (his own 2.4, the Z source 0.8):
     distal ends extended by delta = min(own length - Z length, gap - 1 mm) along the shaft;
 (b) female zan_vertebra_l1 stands for her TWO rib-free bodies L1 + L1B (Q185k: she has six lumbar vertebrae, Z five): its top stopped 6-8 mm below her L1 / T12 disc space (T12 | L1 gap 10.1 mm,
     her own meshes 0.25, the Z source 1.1): top end extended upward until the T12 | L1 gap equals her other lumbar levels' gap (L1 | L2 2.24 mm);
 (c) C7 and T2 (both people): Z C7 stands 2.2-2.7 mm higher than the person's own C7 (C7 | T1 gap 3.2 / 4.5 mm, own 0.25 / 0.0): translated along y onto the own vertebra's centroid (bounded 4 mm)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))


def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def axial_field(v, fixed_end, moving_end, delta, t0=0.3, linear=False):
    """displacement (n, 3) of the vertices v: 0 up to fraction t0 of the fixed -> moving axis, smoothstep up to `delta` mm along the axis at the moving end"""
    a = np.asarray(moving_end, float) - np.asarray(fixed_end, float)
    L = np.linalg.norm(a)
    ax = a / L
    t = ((v - fixed_end) @ ax) / L
    s = np.clip(t, 0.0, 1.0) if linear else smoothstep((t - t0) / (1.0 - t0))
    return np.outer(s * delta, ax)


def min_gap(A, B):
    return float(cKDTree(A).query(B)[0].min())


def chamfer(A, B, n=3000):
    sa, sb = A[::max(1, len(A) // n)], B[::max(1, len(B) // n)]
    return float(cKDTree(B).query(sa)[0].mean()), float(cKDTree(A).query(sb)[0].mean())
