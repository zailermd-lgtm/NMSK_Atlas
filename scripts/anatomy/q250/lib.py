"""Q250 shared helpers: page I/O, similarity fits, coherent point drift (non-rigid), Gaussian-RBF / thin-plate warp fields.
Frames: atlas frame (mm, +X right, +Y superior, +Z anterior) everywhere."""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np, trimesh
from scipy.spatial import cKDTree
from scipy.interpolate import RBFInterpolator

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "anatomy"))
from scripts.zanatomy import q205_pages as P5  # noqa: E402


def load_page(d, stem):
    man, blob = P5.load_page(d, stem)
    return man, blob, P5.decode(man, blob)


def umeyama(A, B, scale=True):
    """s, R, t minimising |s R a + t - b|"""
    ca, cb = A.mean(0), B.mean(0)
    X, Y = A - ca, B - cb
    U, S, Vt = np.linalg.svd(Y.T @ X / len(A))
    d = np.ones(3); d[-1] = np.sign(np.linalg.det(U) * np.linalg.det(Vt))
    R = U @ np.diag(d) @ Vt
    s = (S * d).sum() / ((X ** 2).sum() / len(A)) if scale else 1.0
    return s, R, cb - s * R @ ca


def icp_sim(src, dst, iters=60, trim=0.9, scale=True, init=None):
    tree = cKDTree(dst)
    s, R, t = (1.0, np.eye(3), dst.mean(0) - src.mean(0)) if init is None else init
    for _ in range(iters):
        P = s * src @ R.T + t
        d, i = tree.query(P)
        k = d <= np.quantile(d, trim)
        s_new, R, t = umeyama(src[k], dst[i[k]], scale)
        if scale:
            s = s_new
        else:                                   # scale held at its initial value: translation re-solved for it
            t = dst[i[k]].mean(0) - s * R @ src[k].mean(0)
    P = s * src @ R.T + t
    return s, R, t, tree.query(P)[0]


def sample(v, f, n, seed=0):
    m = trimesh.Trimesh(v, f, process=False)
    rng = np.random.default_rng(seed)
    try:
        p, fi = trimesh.sample.sample_surface(m, n, seed=seed)
        return np.asarray(p), np.asarray(m.face_normals[fi])
    except Exception:  # noqa: BLE001
        i = rng.choice(len(v), n); return v[i], np.zeros((n, 3))


def cpd_nonrigid(X, Y, beta=25.0, lam=3.0, iters=80, w=0.05, sigma2=None, verbose=False):
    """Coherent Point Drift, non-rigid (Myronenko & Song 2010). X source (M,3), Y target (N,3). Returns W, G-kernel params so that T(x) = x + G(x, X) @ W."""
    M, N, D = len(X), len(Y), 3
    G = np.exp(-((X[:, None, :] - X[None, :, :]) ** 2).sum(-1) / (2 * beta ** 2))
    W = np.zeros((M, D))
    if sigma2 is None:
        sigma2 = (((X[:, None, :] - Y[None, ::7, :]) ** 2).sum() / (D * M * len(Y[::7])))
    for it in range(iters):
        T = X + G @ W
        d2 = ((T[:, None, :] - Y[None, :, :]) ** 2).sum(-1)
        c = (2 * np.pi * sigma2) ** (D / 2) * w / (1 - w) * M / N
        K = np.exp(-d2 / (2 * sigma2))
        P = K / (K.sum(0, keepdims=True) + c)
        P1 = P.sum(1); Pt1 = P.sum(0); Np = P1.sum()
        PY = P @ Y
        W = np.linalg.solve(np.diag(P1) @ G + lam * sigma2 * np.eye(M), PY - P1[:, None] * X)
        T = X + G @ W
        s2 = ((Y ** 2).sum(1) @ Pt1 - 2 * (PY * T).sum() + (T ** 2).sum(1) @ P1) / (Np * D)
        sigma2 = max(float(s2), 1e-6)
        if verbose and it % 10 == 0:
            print(it, round(float(np.sqrt(sigma2)), 3), flush=True)
    return W, beta


def cpd_apply(Xc, W, beta, pts, chunk=20000):
    out = np.empty_like(pts)
    for i in range(0, len(pts), chunk):
        p = pts[i:i + chunk]
        K = np.exp(-((p[:, None, :] - Xc[None, :, :]) ** 2).sum(-1) / (2 * beta ** 2))
        out[i:i + chunk] = p + K @ W
    return out


class TPS:
    """thin-plate-spline (3-D kernel r) displacement field through control points (exact or smoothed) + polynomial degree 1"""

    def __init__(self, P, U, smoothing=0.0, neighbors=None):
        self.f = RBFInterpolator(P, U, kernel="thin_plate_spline", smoothing=smoothing, degree=1, neighbors=neighbors)

    def __call__(self, pts, chunk=8000):
        out = np.empty((len(pts), 3))
        for i in range(0, len(pts), chunk):
            out[i:i + chunk] = self.f(pts[i:i + chunk])
        return out


def mirror(p):
    q = np.array(p, float, copy=True)
    q[..., 0] *= -1
    return q


def mesh_volume(v, f):
    m = trimesh.Trimesh(v, f, process=False)
    return float(m.volume) if m.is_watertight else float("nan")
