"""Q217: put the carried Z-base muscle (the forearm part, A) and the page's own distal part (tendon into the hand, B) together as ONE structure.

A = the base mesh carried by the twisted-tube map (q217_twist.TwistMap), clipped to y >= y_m - OVER.  B = the page's mesh (his hand-side fit, untouched there), clipped to y <= y_m + OVER, warped so that its cross-section loops
at the plane y = y_m land on A's loops there (per-loop translation, inverse-distance blended, decaying to 0 over DECAY mm below the seam).  The two pieces overlap coaxially by 2 OVER mm: no gap, no flat cap."""
from __future__ import annotations

import numpy as np
import trimesh
from scipy.optimize import linear_sum_assignment
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

OVER = 4.0
DECAY = 45.0


def loops_at(v, f, y):
    """centroids (and vertex-free) of the cross-section components of a mesh at plane y -> (k, 3) array, areas-free"""
    tm = trimesh.Trimesh(np.asarray(v, float), np.asarray(f, np.int64), process=False)
    seg = trimesh.intersections.mesh_plane(tm, [0, 1, 0], [0, float(y), 0])
    if seg is None or len(seg) == 0:
        return np.zeros((0, 3))
    P = seg.reshape(-1, 3)
    key = np.round(P / 0.05).astype(np.int64)
    _, inv = np.unique(key, axis=0, return_inverse=True)
    inv = inv.reshape(-1, 2)
    n = inv.max() + 1
    A = coo_matrix((np.ones(len(inv)), (inv[:, 0], inv[:, 1])), shape=(n, n))
    nc, lab = connected_components(A, directed=False)
    mid = seg.mean(1)
    out = []
    for c in range(nc):
        m = lab[inv[:, 0]] == c
        if m.sum() >= 3:
            out.append(mid[m].mean(0))
    return np.array(out) if out else np.zeros((0, 3))


def clip(v, f, keep_face):
    f2 = f[keep_face]
    used = np.unique(f2)
    remap = -np.ones(len(v), np.int64)
    remap[used] = np.arange(len(used))
    return v[used], remap[f2], used


def join(a_v, a_f, b_v, b_f, y_m, log=None):
    """-> (v, f, info).  a_* = carried base mesh (whole), b_* = the page mesh (whole)"""
    info = {}
    cA = loops_at(a_v, a_f, y_m)
    cB = loops_at(b_v, b_f, y_m)
    info["loops_A"], info["loops_B"] = len(cA), len(cB)
    # A: keep faces with centroid y >= y_m - OVER
    ca = a_v[a_f].mean(1)[:, 1]
    av, af, _ = clip(a_v, a_f, ca >= y_m - OVER)
    if not len(cB) or not len(cA) or len(af) == 0:
        info["note"] = "no seam (A or B has no section at the seam plane)"
        if len(cA) == 0 and len(cB) == 0:
            return av, af, info
        # base ends above the seam: A is the whole muscle
        return av, af, info
    cb = b_v[b_f].mean(1)[:, 1]
    bv, bf, _ = clip(b_v, b_f, cb <= y_m + OVER)
    if len(bf) == 0:
        return av, af, info
    D = np.linalg.norm(cA[:, None, :] - cB[None, :, :], axis=2)
    ri, ci = linear_sum_assignment(D)
    pair = {int(j): int(i) for i, j in zip(ri, ci)}
    for j in range(len(cB)):
        if j not in pair:
            pair[j] = int(D[:, j].argmin())
    t = np.array([cA[pair[j]] - cB[j] for j in range(len(cB))])
    t[:, 1] = 0.0                                                   # slide within the plane only
    w = 1.0 / (np.linalg.norm(bv[:, None, :] - cB[None, :, :], axis=2) + 3.0) ** 2
    w /= w.sum(1, keepdims=True)
    u = w @ t
    dec = np.clip((bv[:, 1] - (y_m + OVER - DECAY)) / DECAY, 0.0, 1.0)
    dec = 3 * dec ** 2 - 2 * dec ** 3
    bv = bv + u * dec[:, None]
    info.update(seam_shift_mm=[round(float(np.linalg.norm(x)), 1) for x in t], b_faces=int(len(bf)), a_faces=int(len(af)))
    v = np.concatenate([av, bv])
    f = np.concatenate([af, bf + len(av)])
    return v, f, info
