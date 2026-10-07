"""Q200: geometry helpers for the elbow-continuity repair of the two OWN reconstructed models
(similarity ICP onto partial bones, hinge refinement, plane clipping, loop welding)."""
from __future__ import annotations
import numpy as np
from scipy.spatial import cKDTree


def umeyama(P, Q, with_scale=True):
    mp, mq = P.mean(0), Q.mean(0)
    X, Y = P - mp, Q - mq
    U, S, Vt = np.linalg.svd(Y.T @ X / len(P))
    D = np.eye(3)
    if np.linalg.det(U) * np.linalg.det(Vt) < 0:
        D[2, 2] = -1
    R = U @ D @ Vt
    s = (S * np.diag(D)).sum() / (X ** 2).sum(1).mean() if with_scale else 1.0
    A = s * R
    return A, mq - A @ mp


def sample_surface(v, f, n, seed=0):
    rng = np.random.default_rng(seed)
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    ar = np.linalg.norm(np.cross(b - a, c - a), axis=1) / 2
    idx = rng.choice(len(f), n, p=ar / ar.sum())
    r1, r2 = rng.random(n), rng.random(n)
    m = r1 + r2 > 1
    r1[m], r2[m] = 1 - r1[m], 1 - r2[m]
    return a[idx] + r1[:, None] * (b - a)[idx] + r2[:, None] * (c - a)[idx]


def pca_axes(P):
    c = P.mean(0)
    w, V = np.linalg.eigh(np.cov((P - c).T))
    return c, V[:, ::-1]


def icp_partial(zv, zf, ov, of, A0, t0, scale=(0.85, 1.25), fixed_scale=None, iters=60, trim=0.85, n=6000, w_pts=None,
                two_way=False, trim_z=0.8):
    """Z (src, complete) -> own (dst, possibly partial). One-sided: every own point is pulled to its nearest Z surface
    point (so the Z part with no own counterpart is free); trimmed; similarity (scale clamped / fixed)."""
    zs = sample_surface(zv, zf, n, 1)
    os_ = sample_surface(ov, of, n, 2) if w_pts is None else w_pts
    A, t = A0.copy(), t0.copy()
    for k in range(iters):
        zt = zs @ A.T + t
        tree = cKDTree(zt)
        d, j = tree.query(os_)
        keep = d <= np.quantile(d, trim)
        # own points -> matching un-transformed Z points
        S, T = zs[j[keep]], os_[keep]
        if two_way:
            otree = cKDTree(os_)
            d2, j2 = otree.query(zt)
            k2 = d2 <= np.quantile(d2, trim_z)
            S = np.concatenate([S, zs[k2]]); T = np.concatenate([T, os_[j2[k2]]])
        An, tn = umeyama(S, T, with_scale=fixed_scale is None)
        if fixed_scale is not None:
            An = An / max(np.cbrt(abs(np.linalg.det(An))), 1e-9) * fixed_scale
            tn = T.mean(0) - An @ S.mean(0)
        else:
            s = np.cbrt(abs(np.linalg.det(An)))
            sc = np.clip(s, *scale)
            An = An / s * sc
            tn = T.mean(0) - An @ S.mean(0)
        A, t = An, tn
    zt = zs @ A.T + t
    d, _ = cKDTree(zt).query(os_)
    return A, t, dict(median=float(np.median(d)), p90=float(np.quantile(d, .9)), max=float(d.max()),
                      scale=float(np.cbrt(abs(np.linalg.det(A)))))


def rot_angle_deg(R):
    return float(np.degrees(np.arccos(np.clip((np.trace(R) - 1) / 2, -1, 1))))


def pca_rh(P):
    c, V = pca_axes(P)
    if np.linalg.det(V) < 0:
        V[:, 2] = -V[:, 2]
    return c, V


def fit_bone(zv, zf, ov, of, scale0=1.05, **kw):
    """Best of the 4 proper axis flips of the PCA frames as the ICP start."""
    cz, Vz = pca_rh(zv)
    co, Vo = pca_rh(ov)
    best = None
    for fl in ((1, 1, 1), (-1, -1, 1), (-1, 1, -1), (1, -1, -1)):
        R = (Vo * np.array(fl)) @ Vz.T
        A0 = R * scale0
        t0 = co - A0 @ cz
        A, t, st = icp_partial(zv, zf, ov, of, A0, t0, **kw)
        if best is None or st["median"] < best[2]["median"]:
            best = (A, t, st)
    return best


def blend_transform(zv, bone_clouds, bone_AT, soften=8.0, power=2.0, cutoff=40.0):
    """Q147/Q168 soft-tissue rule: inverse-square blend of the nearby bones' similarities.
    bone_clouds {b: (n,3) Z-frame points}; bone_AT {b: (A,t)} Z frame -> own frame."""
    names = list(bone_clouds)
    D = np.stack([cKDTree(bone_clouds[b]).query(zv)[0] for b in names], 1)
    W = 1.0 / (D + soften) ** power
    taper = np.clip(1.0 - np.maximum(D - D.min(1, keepdims=True), 0) / cutoff, 0, 1)
    W = W * taper
    W /= W.sum(1, keepdims=True)
    out = np.zeros_like(zv)
    for k, b in enumerate(names):
        A, t = bone_AT[b]
        out += W[:, [k]] * (zv @ A.T + t)
    return out


def align_rigid_local(zv, zf, mv, mf, axis_k, pos, sign, window=45.0, iters=25, max_t=30.0, max_deg=20.0, trim=0.8):
    """Rigid (no scale) alignment of the Z counterpart to the measured structure M using only the stretch of Z that lies
    within `window` mm on M's side of the seam plane (the part both describe). Bounded; returns (zv_aligned, info)."""
    s = sign * (zv[:, axis_k] - pos)
    sel_f = (s[zf].min(1) > -window) & (s[zf].max(1) < 6.0)
    if sel_f.sum() < 20:
        return zv, dict(applied=False, reason="no overlap window")
    zs_all = sample_surface(zv, zf[sel_f], 3000, 4)
    ms_all = sample_surface(mv, mf, 8000, 5)
    mt = cKDTree(ms_all)
    d0 = mt.query(zs_all)[0]
    R, t = np.eye(3), np.zeros(3)
    cur = zs_all.copy()
    for _ in range(iters):
        d, j = mt.query(cur)
        keep = d <= np.quantile(d, trim)
        A, tt = umeyama(cur[keep], ms_all[j[keep]], with_scale=False)
        cur = cur @ A.T + tt
        R, t = A @ R, A @ t + tt
    ang = rot_angle_deg(R)
    cen = zs_all.mean(0)
    move = float(np.linalg.norm(R @ cen + t - cen))
    d1 = mt.query(cur)[0]
    mode = "rigid"
    axial = float(abs((R @ cen + t - cen)[axis_k]))
    if ang > 12.0 or move > max_t or axial > 5.0:
        # a limb muscle is a near-cylinder: its roll / tilt in a 45 mm window is poorly determined -> translation only
        R, t = np.eye(3), np.zeros(3)
        cur = zs_all.copy()
        for _ in range(iters):
            d, j = mt.query(cur)
            keep = d <= np.quantile(d, trim)
            dt = (ms_all[j[keep]] - cur[keep]).mean(0)
            dt[axis_k] = 0.0                       # the position along the limb comes from the bones, not from a 45 mm window
            cur = cur + dt; t = t + dt
        ang, move, mode = 0.0, float(np.linalg.norm(t)), "translation"
        d1 = mt.query(cur)[0]
    info = dict(before_median=float(np.median(d0)), after_median=float(np.median(d1)), rot_deg=ang, move_mm=move, mode=mode)
    if move > max_t * 1.5 or np.median(d1) >= np.median(d0):
        info.update(applied=False, reason="bounds / no gain")
        return zv, info
    info["applied"] = True
    return zv @ R.T + t, info
