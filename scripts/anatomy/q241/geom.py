"""Q241 geometry helpers (numpy only): rotations, rigid fits, sphere fit, PCA, mesh components, skinning in numpy."""
from __future__ import annotations
import numpy as np


def unit(a, eps=1e-12):
    a = np.asarray(a, float)
    n = np.linalg.norm(a)
    return a / n if n > eps else a * 0.0


def rot(axis, deg):
    """rotation matrix about `axis` by deg (Rodrigues, math convention: v -> v cos + (a x v) sin + a (a.v)(1-cos))"""
    a = unit(axis); t = np.radians(deg); c, s = np.cos(t), np.sin(t)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    return np.eye(3) * c + s * K + (1 - c) * np.outer(a, a)


def rot_angle(R):
    return float(np.degrees(np.arccos(np.clip((np.trace(R) - 1) / 2, -1, 1))))


def rotvec(R):
    """rotation vector (axis * angle in degrees) of a proper rotation"""
    ang = np.arccos(np.clip((np.trace(R) - 1) / 2, -1, 1))
    if ang < 1e-9:
        return np.zeros(3)
    if abs(ang - np.pi) < 1e-6:
        w, V = np.linalg.eigh((R + R.T) / 2); ax = V[:, -1]
    else:
        ax = np.array([R[2, 1] - R[1, 2], R[0, 2] - R[2, 0], R[1, 0] - R[0, 1]]) / (2 * np.sin(ang))
    return unit(ax) * np.degrees(ang)


def kabsch(P, Q, w=None):
    """R, t minimising |R P + t - Q| (proper rotation)"""
    if w is None:
        pc, qc = P.mean(0), Q.mean(0); H = (P - pc).T @ (Q - qc)
    else:
        w = w / w.sum(); pc, qc = (P * w[:, None]).sum(0), (Q * w[:, None]).sum(0); H = ((P - pc) * w[:, None]).T @ (Q - qc)
    U, S, Vt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    R = Vt.T @ np.diag([1, 1, d]) @ U.T
    return R, qc - R @ pc


def pca(P):
    """(centre, eigenvalues desc, axes columns desc)"""
    c = P.mean(0); w, V = np.linalg.eigh(np.cov((P - c).T)); o = np.argsort(w)[::-1]
    return c, w[o], V[:, o]


def sphere_fit(P, r0=None):
    """algebraic least-squares sphere -> (centre, radius, rms residual)"""
    A = np.c_[2 * P, np.ones(len(P))]; b = (P ** 2).sum(1)
    x = np.linalg.lstsq(A, b, rcond=None)[0]
    c = x[:3]; r = np.sqrt(max(x[3] + c @ c, 0))
    return c, float(r), float(np.sqrt(np.mean((np.linalg.norm(P - c, axis=1) - r) ** 2)))


def sphere_ransac(P, rmin, rmax, tol=1.2, iters=1500, seed=0):
    """largest near-spherical patch of P with radius in [rmin, rmax]: RANSAC on 4-point spheres, then least squares on the inliers (re-selected twice)"""
    rng = np.random.default_rng(seed)
    n = len(P)
    if n < 8:
        return None
    best = (-1, None)
    for _ in range(iters):
        i = rng.choice(n, 4, replace=False); Q = P[i]
        A = np.c_[2 * Q, np.ones(4)]; b = (Q ** 2).sum(1)
        try:
            x = np.linalg.solve(A, b)
        except np.linalg.LinAlgError:
            continue
        c = x[:3]; r2 = x[3] + c @ c
        if r2 <= 0:
            continue
        r = np.sqrt(r2)
        if r < rmin or r > rmax:
            continue
        k = int((np.abs(np.linalg.norm(P - c, axis=1) - r) < tol).sum())
        if k > best[0]:
            best = (k, (c, r))
    if best[1] is None:
        return None
    c, r = best[1]
    for _ in range(3):
        m = np.abs(np.linalg.norm(P - c, axis=1) - r) < tol * 1.5
        if m.sum() < 8:
            break
        c, r, rms = sphere_fit(P[m])
    m = np.abs(np.linalg.norm(P - c, axis=1) - r) < tol * 1.5
    c, r, rms = sphere_fit(P[m])
    return c, r, rms, int(m.sum())


def components(f, nv):
    """connected components of a triangle mesh -> label per vertex"""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    e = np.r_[f[:, [0, 1]], f[:, [1, 2]]]
    g = coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(nv, nv))
    return connected_components(g, directed=False)[1]


def trimmed_extreme(P, d, frac=0.03):
    """mean of the `frac` most extreme points of P along direction d (a landmark that tolerates a single stray vertex)"""
    t = P @ d; k = max(3, int(len(P) * frac)); o = np.argsort(t)[-k:]
    return P[o].mean(0)


def angle_between(a, b):
    return float(np.degrees(np.arccos(np.clip(unit(a) @ unit(b), -1, 1))))


def signed_angle(a, b, axis):
    """signed angle (deg) from a to b about `axis`, both projected onto the plane perpendicular to the axis (math right-hand convention)"""
    ax = unit(axis); a = a - (a @ ax) * ax; b = b - (b @ ax) * ax
    a, b = unit(a), unit(b)
    return float(np.degrees(np.arctan2(ax @ np.cross(a, b), a @ b)))


def solve_euler(axes, D, x0=None):
    """angles (deg) q with Rot(a1,q1)Rot(a2,q2)Rot(a3,q3) ~ D (axes = list of 1..3 unit vectors, fixed in the parent frame); least squares on the rotation difference"""
    from scipy.optimize import least_squares
    k = len(axes)

    def mk(q):
        R = np.eye(3)
        for a, t in zip(axes, q):
            R = R @ rot(a, t)
        return R

    def res(q):
        return (mk(q) - D).ravel()
    best = None
    for st in ([0.0] * k, [30.0] * k, [-30.0] * k, [90.0] + [0.0] * (k - 1)):
        r = least_squares(res, np.array(st, float), method="lm")
        if best is None or r.cost < best.cost:
            best = r
    return best.x, float(np.sqrt(2 * best.cost / 9))


def skin_apply(v, parts):
    """linear blend skinning: parts = [(weights (n,), 4x4 matrix), ...] -> (n,3)"""
    out = np.zeros_like(v)
    for w, M in parts:
        out += w[:, None] * (v @ M[:3, :3].T + M[:3, 3])
    return out


def T4(R=None, t=None):
    M = np.eye(4)
    if R is not None: M[:3, :3] = R
    if t is not None: M[:3, 3] = t
    return M


def about(R, c):
    """4x4: rotation R about the point c"""
    M = np.eye(4); M[:3, :3] = R; M[:3, 3] = c - R @ c
    return M
