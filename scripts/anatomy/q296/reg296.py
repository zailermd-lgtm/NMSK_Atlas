"""Q296 registration: the SPL Inner Ear Atlas (one right ear, flat-panel CT) onto a page's own ear ossicles.

Bone-point registration, exactly the Q292 / Q295 method (lib292.sim / icp_pairs) narrowed to the three ossicles:
the atlas ships malleus, incus and stapes in the same frame as the structures we want, and every page already has
`malleus_{l,r}`, `incus_{l,r}`, `stapes_{l,r}` as bones. So the three ossicles are the registration landmarks and the
imported structures ride along -- no free parameters per imported structure.

Similarity only (scale + rotation + translation), no warp: the atlas is a single specimen and the three ossicles
span ~9 mm, so a thin-plate spline on this landmark set would be unconstrained. The atlas's own model coordinates are
uniformly ~3.15x life size (its label maps were meshed with the scanner's nominal spacing, not the 140 um flat-panel
voxel), which the similarity's scale term recovers: the fitted scale is the same to 5 decimals on every page and side.

The atlas ear is a RIGHT ear: the proper-rotation fit wins on a page's right side and the reflected fit on its left.
"""
from __future__ import annotations

import numpy as np
from scipy.spatial import cKDTree

OSSICLES = ("malleus", "incus", "stapes")


def sim(X, Y):
    """Umeyama similarity (proper rotation) X -> Y; returns (s, R, t) with p -> s*R@p + t."""
    mx, my = X.mean(0), Y.mean(0); A = X - mx; B = Y - my
    U, S, Vt = np.linalg.svd(A.T @ B); d = np.sign(np.linalg.det(U @ Vt)); D = np.diag([1, 1, d])
    R = (U @ D @ Vt).T; s = (S * np.diag(D)).sum() / (A ** 2).sum(); t = my - s * R @ mx
    return s, R, t


def sim_reflect(X, Y):
    """the same fit through a reflection of X in its own third principal plane (the mirrored ear)."""
    mx = X.mean(0); _, _, Vt = np.linalg.svd(X - mx, full_matrices=False)
    M = np.eye(3) - 2 * np.outer(Vt[2], Vt[2])
    s, R, t = sim((X - mx) @ M.T + mx, Y)
    return s, R @ M, t + s * R @ (mx - M @ mx)


def _refit(X, Y, reflected):
    """similarity fit that keeps the reflection state (det R < 0 stays < 0)."""
    if not reflected:
        return sim(X, Y)
    Mref = np.diag([-1.0, 1.0, 1.0])
    s, R, t = sim(X @ Mref.T, Y)
    return s, R @ Mref, t


def icp(src, dst, s, R, t, iters=60, trim=85.0):
    """per-structure nearest-point similarity ICP. src / dst: {name: points}; only like matches like."""
    trees = {k: cKDTree(v) for k, v in dst.items()}
    reflected = np.linalg.det(R) < 0
    for _ in range(iters):
        Xs, Ys = [], []
        for k, Xv in src.items():
            Z = s * Xv @ R.T + t; d, i = trees[k].query(Z)
            m = d <= np.percentile(d, trim) + 1e-9
            Xs.append(Xv[m]); Ys.append(dst[k][i[m]])
        s, R, t = _refit(np.vstack(Xs), np.vstack(Ys), reflected)
    res = np.concatenate([trees[k].query(s * Xv @ R.T + t)[0] for k, Xv in src.items()])
    return s, R, t, res


def fit(src, dst):
    """both handedness hypotheses, the better residual wins. -> dict with s / R / t / residuals / handedness."""
    Xc = np.array([src[k].mean(0) for k in src]); Yc = np.array([dst[k].mean(0) for k in src])
    best = None
    for lab, fn in (("proper", sim), ("reflect", sim_reflect)):
        s0, R0, t0 = fn(Xc, Yc)
        s, R, t, res = icp(src, dst, s0, R0, t0)
        rms = float(np.sqrt((res ** 2).mean()))
        if best is None or rms < best["rms"]:
            best = {"mode": lab, "s": float(s), "R": R, "t": t, "rms": rms, "n": int(len(res)),
                    "median_mm": float(np.median(res)), "p95_mm": float(np.percentile(res, 95)),
                    "max_mm": float(res.max())}
    return best


def apply(M, V):
    return M["s"] * np.asarray(V, float) @ M["R"].T + M["t"]
