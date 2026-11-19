#!/usr/bin/env python3
"""Q210 (3): the male LEFT palmaris longus has 21 vertices (1.2 %), 217-255 mm along its axis (the distal tendon end), up to 21 mm OUTSIDE his own CT skin (a fit defect of that muscle; Q208 Open item).
Cheap, in the same patch path: the vertices that are outside (or within 1 mm of the surface of) his own skin are moved to the nearest point of his own skin, 1 mm inside, the displacement is extended into the mesh as a harmonic
(graph Laplacian) field that decays to 0 at 25 mm of mesh distance (the other vertices keep their place), so nothing is invented and the belly is untouched.  Guards: stays inside his own skin and the displayed skin,
no new vertex inside a bone, edge lengths within the old range, extent along the axis within 5 %."""
from __future__ import annotations

import numpy as np
from scipy.sparse import coo_matrix, diags
from scipy.sparse.csgraph import dijkstra
from scipy.sparse.linalg import spsolve

ID = "zan_palmaris_longus_muscle_l"


def graph(v, f):
    e = np.unique(np.sort(np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]), axis=1), axis=0)
    w = np.linalg.norm(v[e[:, 0]] - v[e[:, 1]], axis=1)
    A = coo_matrix((w + 1e-6, (e[:, 0], e[:, 1])), shape=(len(v),) * 2).tocsr()
    return e, A.maximum(A.T)


def pull_inside(v, f, own, margin=1.0, need=0.3, decay_mm=25.0, rounds=6):
    """-> new vertices, info.  Constraint vertices = outside his own skin (further rounds: any vertex that the harmonic field leaves within `need` mm of the surface); they go to the nearest point of his own skin,
    `margin` inside; the displacement of every other vertex within `decay_mm` of mesh distance is the harmonic (graph Laplacian) extension."""
    import trimesh
    n = len(v)
    e, A = graph(v, f)
    W = coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(n, n))
    W = (W + W.T).tocsr()
    L = (diags(np.asarray(W.sum(1)).ravel()) - W).tocsr()
    s0 = own.sd(v)
    cons = np.zeros(n, bool)
    cons[s0 > 0] = True
    if not cons.any():
        return v.copy(), {"violating": 0}
    out = v.copy()
    for r in range(rounds):
        idx = np.flatnonzero(cons)
        cp, dist, tri = trimesh.proximity.closest_point(own.tm, v[idx])
        nrm = own.tm.face_normals[tri]
        U = np.zeros((n, 3))
        U[idx] = cp - margin * nrm - v[idx]
        g = dijkstra(A, indices=idx, min_only=True)
        free = np.flatnonzero((g < decay_mm) & ~cons)
        fixed = np.setdiff1d(np.arange(n), free)
        if len(free):
            Aff = L[free][:, free].tocsc()
            Afx = L[free][:, fixed]
            for c in range(3):
                U[free, c] = spsolve(Aff, -(Afx @ U[fixed, c]))
        out = v + U
        s1 = own.sd(out)
        bad = (s1 > -need) & ~cons
        if not bad.any():
            break
        cons |= bad
    nu = np.linalg.norm(out - v, axis=1)
    return out, {"violating": int(s0.size and (s0 > 0).sum()), "outside": int((s0 > 0).sum()), "constraint_vertices": int(cons.sum()), "rounds": r + 1, "moved_gt0_3": int((nu > 0.3).sum()), "max_move_mm": round(float(nu.max()), 1),
                 "mean_move_mm_of_moved": round(float(nu[nu > 0.3].mean()), 1)}


def extent_along(v, axis):
    t = (v - v.mean(0)) @ axis
    return float(t.max() - t.min())


def edge_ratio(v0, v1, f):
    e = np.unique(np.sort(np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]), axis=1), axis=0)
    a = np.linalg.norm(v0[e[:, 0]] - v0[e[:, 1]], axis=1)
    b = np.linalg.norm(v1[e[:, 0]] - v1[e[:, 1]], axis=1)
    ok = a > 0.3
    return b[ok] / a[ok]
