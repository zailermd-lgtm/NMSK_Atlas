"""Per-bone frames and the affine that carries one body's bone onto another's.

A bone frame is its principal axes (signs fixed to the atlas axes so the
same bone on two bodies gets the same axis order and direction), the
1st/99th-percentile extents along them, and the centre of that box. The
map from the male's femur to the female's femur is then the affine that
takes his box onto hers: rotate into his frame, scale each axis by the
extent ratio, rotate out into hers. Nothing is fitted to soft tissue; the
bones are the only measured correspondence between the two bodies.

Truncated bones (the female humeri, radius and ulna end at the CT field of
view) get a *similarity* from their proximal part instead: uniform scale
from the transverse extents, so a missing distal end does not shrink the
whole arm.
"""
from __future__ import annotations

import numpy as np

LONG_RATIO = 1.6   # ext0/ext1 above this: use principal axes; below: atlas axes


def bone_frame(v: np.ndarray, clip_top_mm: float | None = None) -> dict:
    v = np.asarray(v, np.float64)
    if clip_top_mm is not None:
        top = v[:, 1].max()
        v = v[v[:, 1] >= top - clip_top_mm]
    c = v.mean(axis=0)
    X = v - c
    w, R = np.linalg.eigh(X.T @ X / len(X))
    R = R[:, ::-1]
    proj = X @ R
    lo, hi = np.percentile(proj, 1, axis=0), np.percentile(proj, 99, axis=0)
    ext = hi - lo
    if ext[0] / max(ext[1], 1e-6) < LONG_RATIO:
        R = np.eye(3)
    else:
        # sign convention: each axis points along the atlas axis it is closest to,
        # and the three are assigned to distinct atlas axes in order (long axis first)
        taken = []
        for k in range(3):
            comp = np.abs(R[:, k]).copy(); comp[taken] = -1
            j = int(np.argmax(comp)); taken.append(j)
            if R[j, k] < 0:
                R[:, k] *= -1
        if np.linalg.det(R) < 0:
            R[:, 2] *= -1
    proj = X @ R
    lo, hi = np.percentile(proj, 1, axis=0), np.percentile(proj, 99, axis=0)
    centre = c + R @ ((lo + hi) / 2)
    return {"R": R, "ext": hi - lo, "centre": centre, "n": int(len(v))}


def bone_affine(src: dict, dst: dict, uniform: bool = False) -> tuple[np.ndarray, np.ndarray]:
    """Return (A, t) with x_dst = A @ x_src + t mapping the src bone box onto dst's."""
    s = dst["ext"] / np.maximum(src["ext"], 1e-6)
    if uniform:
        s = np.full(3, float(np.sqrt(s[1] * s[2])))
    A = dst["R"] @ np.diag(s) @ src["R"].T
    t = dst["centre"] - A @ src["centre"]
    return A, t


def apply(A: np.ndarray, t: np.ndarray, v: np.ndarray) -> np.ndarray:
    return v @ A.T + t
