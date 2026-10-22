"""Q211 tear relaxation: the structures of a junction zone that TOUCH in the unfitted Z source (vertex pairs <= 2 mm apart, different soft structures) but are > tol apart on the fitted page are drawn back together by ONE
sparse least-squares displacement field over all vertices of the zone structures:
   minimise   w_p * sum_pairs |(x_a + u_a) - (x_b + u_b)|^2   +   w_s * sum_edges |u_v - u_w|^2   +   w_0 * sum_v c_v |u_v|^2
pair term = the pairs that are further apart than `tol` (re-weighted each round), smoothness over each structure's own mesh edges (a structure moves as a coherent piece, its shape is kept), stay-put term with a per-vertex
coefficient c_v (vertices at a bone attachment footprint, structures carrying the person's own measured geometry: large).  After each solve the movement is capped, each structure goes through the guard ladder
(inside the displayed skin, out of the displayed bones, volume / fold / stretch guards: q206_carry) and the result is kept only if the structure is not worse than before (cost), then the pairs are re-evaluated."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy.sparse import coo_matrix, csr_matrix, diags
from scipy.sparse.linalg import splu
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))


def edges_of(f):
    e = np.unique(np.sort(np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]), axis=1), axis=0)
    return e


class Zone:
    """ids: soft structures; base / cur: {id: vertices}; offsets for the stacked vertex vector"""

    def __init__(self, ids, base, cur, faces, centre, R):
        self.ids = list(ids)
        self.off, n = {}, 0
        for i in self.ids:
            self.off[i] = n
            n += len(cur[i])
        self.n = n
        self.X = np.concatenate([cur[i] for i in self.ids]).astype(float)
        self.B = np.concatenate([base[i] for i in self.ids]).astype(float)
        self.lab = np.concatenate([np.full(len(cur[i]), k) for k, i in enumerate(self.ids)])
        E = []
        for i in self.ids:
            e = edges_of(faces[i]) + self.off[i]
            E.append(e)
        self.E = np.concatenate(E)
        # base adjacency: vertex pairs <= 2 mm apart in the Z source from different structures, near the joint
        near = np.linalg.norm(self.B - centre, axis=1) < R
        idx = np.flatnonzero(near)
        tr = cKDTree(self.B[idx])
        pr = tr.query_pairs(2.0, output_type="ndarray")
        pr = idx[pr]
        self.P = pr[self.lab[pr[:, 0]] != self.lab[pr[:, 1]]]
        self.d0 = np.linalg.norm(self.B[self.P[:, 0]] - self.B[self.P[:, 1]], axis=1)

    def tears(self, X=None):
        X = self.X if X is None else X
        return np.linalg.norm(X[self.P[:, 0]] - X[self.P[:, 1]], axis=1)


def solve(Z, X, cstay, w_p=1.0, w_s=8.0, w_0=0.05, tol=2.0, pair_mask=None, con=None, w_c=4.0):
    """-> u (n, 3).  Pair term only for pairs with separation > tol (target separation 0.5 * tol)."""
    n = Z.n
    P = Z.P if pair_mask is None else Z.P[pair_mask]
    d = X[P[:, 0]] - X[P[:, 1]]
    dist = np.linalg.norm(d, axis=1)
    act = dist > tol
    P, d, dist = P[act], d[act], dist[act]
    # target for (x_a + u_a) - (x_b + u_b) = d * (0.5 tol / dist)  ->  residual rows
    tgt = d * (0.5 * tol / np.maximum(dist, 1e-9))[:, None]
    rows, cols, vals = [], [], []
    r = 0
    m = len(P)
    sw_p = np.sqrt(w_p)
    ri = np.arange(m)
    rows += [ri, ri]
    cols += [P[:, 0], P[:, 1]]
    vals += [np.full(m, sw_p), np.full(m, -sw_p)]
    rhs_p = sw_p * (tgt - d)                    # (u_a - u_b) = tgt - d
    r = m
    e = Z.E
    k = len(e)
    ri = r + np.arange(k)
    sw_s = np.sqrt(w_s)
    rows += [ri, ri]
    cols += [e[:, 0], e[:, 1]]
    vals += [np.full(k, sw_s), np.full(k, -sw_s)]
    r += k
    ri = r + np.arange(n)
    rows += [ri]
    cols += [np.arange(n)]
    vals += [np.sqrt(w_0 * cstay)]
    r += n
    nc = 0
    if con is not None and len(con[0]):
        ci, ct = con                              # constraint vertices (pushed out of a bone / back inside the skin): u_v = ct_v
        nc = len(ci)
        ri = r + np.arange(nc)
        rows += [ri]
        cols += [ci]
        vals += [np.full(nc, np.sqrt(w_c))]
        r += nc
    A = coo_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))), shape=(r, n)).tocsr()
    AtA = (A.T @ A).tocsc()
    lu = splu(AtA)
    u = np.zeros((n, 3))
    for c in range(3):
        b = np.zeros(r)
        b[:m] = rhs_p[:, c]
        if nc:
            b[r - nc:r] = np.sqrt(w_c) * ct[:, c]
        u[:, c] = lu.solve(A.T @ b)
    return u, int(act.sum())
