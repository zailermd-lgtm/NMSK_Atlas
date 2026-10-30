"""Q200: articulate the Z-Anatomy forearm bones with the Z-Anatomy distal humerus in the body's frame.

The per-bone Q168/Q195 similarities fit each bone to the surviving measured piece independently; a truncated bone (her ulna: 117 mm of
a 250 mm bone, the proximal 87 mm outside the CT block) can slide along its shaft by a centimetre or more without changing its
fit, so the joint ends up open (her right humerus-ulna gap 11 mm). Here the Z bone gets a bounded correction (scale 0.92-1.15,
rotation <= 10 deg, translation <= 20 mm about the articular end) that keeps the one-sided chamfer to the measured piece and closes
the joint to a 1.5-2 mm contact patch with the Z humerus."""
from __future__ import annotations
import numpy as np
from scipy.optimize import minimize
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation

from scripts.transfer.q200_geom import sample_surface


def _apply(P, pivot, x):
    s = np.exp(x[0]); R = Rotation.from_rotvec(x[1:4]).as_matrix()
    return (P - pivot) @ (s * R).T + pivot + x[4:7]


def contact(A, B_tree, k=30):
    d = B_tree.query(A)[0]
    return float(np.sort(d)[:k].mean()), float(d.min())


def refine_to_joint(zv, zf, own_v, own_f, hum_pts_tree, prox_sign, partner=None, target=1.8, max_rot_deg=10.0, max_trans=20.0,
                    scale_rng=(0.92, 1.15), w_art=6.0, art_len=40.0):
    """Correction of the Z bone (vertices zv in the body frame; the Q168/Q195 placement) so that its articular end touches the
    humerus samples. prox_sign +1: the articular end is the end with the largest y. Returns (zv', info, fn) where fn applies the same correction to any points."""
    zs = sample_surface(zv, zf, 5000, 1)
    os_ = sample_surface(own_v, own_f, 4000, 2)
    yv = prox_sign * zs[:, 1]
    top = zs[yv >= yv.max() - art_len]
    pivot = top.mean(0)
    otree_zs = None

    def cost(x):
        Z = _apply(zs, pivot, x)
        d = cKDTree(Z).query(os_)[0]
        ch = np.mean(np.sort(d)[: int(0.9 * len(d))])
        T = _apply(top, pivot, x)
        cm, _ = contact(T, hum_pts_tree)
        c = ch + w_art * (cm - target) ** 2
        if partner is not None:
            cp, dm = partner(T)
            c += w_art * 0.5 * (cp - 1.5) ** 2 * 0 + (0 if dm >= 0.5 else 5 * (0.5 - dm))
        reg = 0.02 * (np.degrees(np.linalg.norm(x[1:4])) ** 2) + 0.01 * np.sum(x[4:7] ** 2)
        # soft bounds inside the search, so the clipped result is the optimum and not a clipped excursion
        pen = 50.0 * max(0.0, np.degrees(np.linalg.norm(x[1:4])) - max_rot_deg) ** 2 + 5.0 * max(0.0, np.linalg.norm(x[4:7]) - max_trans) ** 2
        pen += 2000.0 * (max(0.0, np.log(scale_rng[0]) - x[0]) ** 2 + max(0.0, x[0] - np.log(scale_rng[1])) ** 2)
        return c + reg + pen

    x0 = np.zeros(7)
    d0 = cKDTree(zs).query(os_)[0]
    c0 = contact(top, hum_pts_tree)
    best = None
    for start in (x0,):
        r = minimize(cost, start, method="Powell", options=dict(maxiter=4000, xtol=1e-2, ftol=1e-4))
        if best is None or r.fun < best.fun:
            best = r
    x = best.x.copy()
    x[0] = np.clip(x[0], np.log(scale_rng[0]), np.log(scale_rng[1]))
    rv = x[1:4]; ang = np.degrees(np.linalg.norm(rv))
    if ang > max_rot_deg:
        x[1:4] = rv * (max_rot_deg / ang)
    tn = np.linalg.norm(x[4:7])
    if tn > max_trans:
        x[4:7] *= max_trans / tn
    Z = _apply(zs, pivot, x)
    d1 = cKDTree(Z).query(os_)[0]
    T = _apply(top, pivot, x)
    c1 = contact(T, hum_pts_tree)
    info = dict(scale=float(np.exp(x[0])), rot_deg=float(np.degrees(np.linalg.norm(x[1:4]))), trans_mm=float(np.linalg.norm(x[4:7])),
                chamfer_before=float(np.median(d0)), chamfer_after=float(np.median(d1)), chamfer_p90_before=float(np.quantile(d0, .9)),
                chamfer_p90_after=float(np.quantile(d1, .9)),
                contact_before_mm=c0[0], gap_before_mm=c0[1], contact_after_mm=c1[0], gap_after_mm=c1[1])
    xx = x.copy()
    return _apply(zv, pivot, x), info, (lambda P, _x=xx, _p=pivot: _apply(np.asarray(P, float), _p, _x))
