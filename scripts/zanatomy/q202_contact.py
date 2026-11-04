"""Q202: contact seams of the skin slabs.  Two skin patches touch in the Z source not only at shared vertices (q199_elbow.skin_seam_rows) but wherever a vertex of one lies on an edge / face of the
other (the rim of one slab is a different polyline than the rim of its neighbour).  After the per-patch fits (Q168 / Q190 / Q195) those contacts open.  Here:
  contacts(raw)            vertex a of patch A that lies < 1.0 mm from the surface of another patch B in the SOURCE -> (A, a, B, barycentric partner point as (vertices of B, weights))
  gaps(by, contacts)       the same contacts in the fitted state: distance vertex -> partner point
  contact_weld(...)        both patches move half way (capped, spread over the patch by the mesh smoother, rounds), the same rule as the Q199 / Q201 border weld, for every contact
"""
from __future__ import annotations

import numpy as np
from scipy.spatial import cKDTree


def _samples(raw, ids):
    """source surface samples: vertices, edge midpoints, face centroids -> (points, patch label, vertex ids (k,3), weights (k,3))"""
    P, L, VI, W = [], [], [], []
    for pi, i in enumerate(ids):
        v, f = raw[i]["v"], raw[i]["f"]
        n = len(v)
        P.append(v); L.append(np.full(n, pi)); VI.append(np.stack([np.arange(n)] * 3, 1)); W.append(np.tile([1.0, 0, 0], (n, 1)))
        e = np.unique(np.sort(np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]), axis=1), axis=0)
        P.append(0.5 * (v[e[:, 0]] + v[e[:, 1]])); L.append(np.full(len(e), pi)); VI.append(np.stack([e[:, 0], e[:, 1], e[:, 1]], 1)); W.append(np.tile([0.5, 0.5, 0], (len(e), 1)))
        P.append(v[f].mean(1)); L.append(np.full(len(f), pi)); VI.append(f.copy()); W.append(np.full((len(f), 3), 1 / 3))
    return np.vstack(P), np.concatenate(L), np.vstack(VI), np.vstack(W)


def contacts(raw, ids, tol=1.0):
    P, L, VI, W = _samples(raw, ids)
    tree = cKDTree(P)
    out = []
    for pi, i in enumerate(ids):
        v = raw[i]["v"]
        # k nearest samples, take the first that belongs to another patch
        d, k = tree.query(v, k=12, distance_upper_bound=tol)
        for a in range(len(v)):
            for dd, kk in zip(d[a], k[a]):
                if kk >= len(P) or not np.isfinite(dd):
                    break
                if L[kk] != pi:
                    out.append((pi, a, int(L[kk]), VI[kk].copy(), W[kk].copy(), float(dd)))
                    break
    return out


def partner_point(by, ids, c):
    pi, a, pj, vi, w, d0 = c
    return (by[ids[pj]]["v"][vi] * w[:, None]).sum(0)


def gaps(by, ids, cons):
    g = np.array([np.linalg.norm(partner_point(by, ids, c) - by[ids[c[0]]]["v"][c[1]]) for c in cons])
    return g


def contact_weld(by, ids, cons, movable, rounds=10, cap=14.0, passes=24, gate=0.0):
    from scripts.zanatomy import q190_refine as Q
    for _ in range(rounds):
        corr = {i: np.zeros_like(by[i]["v"]) for i in movable}
        cnt = {i: np.zeros(len(by[i]["v"])) for i in movable}
        for c in cons:
            pi, a, pj, vi, w, d0 = c
            A, B = ids[pi], ids[pj]
            vec = partner_point(by, ids, c) - by[A]["v"][a]
            if np.linalg.norm(vec) <= gate:
                continue
            if A not in movable and B not in movable:
                continue
            sa, sb = (0.5, 0.5) if (A in movable and B in movable) else ((1.0, 0.0) if A in movable else (0.0, 1.0))
            if sa:
                corr[A][a] += sa * vec; cnt[A][a] += 1
            if sb:
                for q, wq in zip(vi, w):
                    if wq > 0:
                        corr[B][q] -= sb * vec * wq; cnt[B][q] += wq
        for i in movable:
            m = cnt[i] > 0
            if not m.any():
                continue
            cc = np.zeros_like(corr[i]); cc[m] = corr[i][m] / cnt[i][m][:, None]
            n = np.linalg.norm(cc, axis=1)
            cc *= np.minimum(1.0, cap / np.maximum(n, 1e-9))[:, None]
            c2 = Q._smooth_push(by[i]["f"], cc, passes)
            c2 = np.where((n > 1e-6)[:, None], cc, c2)
            by[i]["v"] = by[i]["v"] + c2
