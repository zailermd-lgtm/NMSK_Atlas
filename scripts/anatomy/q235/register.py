"""Q235: rigid + uniform-scale registration of the CVH pelvic bones (atlas axes, side convention sx) onto a page's pelvic bones with a BIDIRECTIONAL (symmetric) trimmed closest-point iteration:
the CVH bone meshes are cropped (iliac wings, upper sacrum absent) so a one-way ICP of a partial surface onto the whole page bone biases the scale upward; here only the page bone points inside the
(expanded) bounding box of the moved CVH bones take part, and source->target and target->source pairs are both used."""
from __future__ import annotations
import numpy as np
from scipy.spatial import cKDTree


def umeyama(A, B, w=None, scale=True):
    w = np.ones(len(A)) if w is None else w
    w = w / w.sum()
    ca, cb = (A * w[:, None]).sum(0), (B * w[:, None]).sum(0)
    X, Y = A - ca, B - cb
    U, S, Vt = np.linalg.svd((Y * w[:, None]).T @ X)
    d = np.ones(3); d[-1] = np.sign(np.linalg.det(U) * np.linalg.det(Vt))
    R = U @ np.diag(d) @ Vt
    s = (S * d).sum() / ((X ** 2).sum(1) * w).sum() if scale else 1.0
    t = cb - s * R @ ca
    return s, R, t


def apply(T, V):
    s, R, t = T
    return s * V @ R.T + t


def sym_icp(src, dst, T0, iters=80, trim=0.85, margin=8.0, scale=True, fixed_scale=None):
    """src, dst: (n,3). T0 = (s,R,t) start. -> T, residual info"""
    tree_d = cKDTree(dst)
    T = T0
    for _ in range(iters):
        P = apply(T, src)
        lo, hi = P.min(0) - margin, P.max(0) + margin
        sel = np.all((dst >= lo) & (dst <= hi), axis=1)
        D = dst[sel]
        tree_s = cKDTree(P)
        d1, i1 = tree_d.query(P)
        d2, i2 = tree_s.query(D)
        k1 = d1 <= np.quantile(d1, trim); k2 = d2 <= np.quantile(d2, trim)
        A = np.vstack([src[k1], src[i2[k2]]]); B = np.vstack([dst[i1[k1]], D[k2]])
        if fixed_scale is None:
            T = umeyama(A, B, scale=scale)
        else:
            s, R, t = umeyama(A / 1.0, B, scale=False); T = (fixed_scale, R, t)
            # refit translation for the fixed scale
            T = (fixed_scale, R, B.mean(0) - fixed_scale * R @ A.mean(0))
    P = apply(T, src)
    d1 = tree_d.query(P)[0]
    return T, d1


def rot(pitch=0, yaw=0, roll=0):
    a, b, c = np.radians([pitch, yaw, roll])
    Rx = np.array([[1, 0, 0], [0, np.cos(a), -np.sin(a)], [0, np.sin(a), np.cos(a)]])
    Ry = np.array([[np.cos(b), 0, np.sin(b)], [0, 1, 0], [-np.sin(b), 0, np.cos(b)]])
    Rz = np.array([[np.cos(c), -np.sin(c), 0], [np.sin(c), np.cos(c), 0], [0, 0, 1]])
    return Rz @ Ry @ Rx
