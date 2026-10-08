"""Q207: refit of the two male urogenital skin patches (scrotal bag + perineal strip, left and right half) to their Z SOURCE volume.
The Q195 per-patch fit stretched them (59.9 k / 42.6 k mm3 against 37.1 k in the source, halves overlapping the midline).  Here: the source shape is placed by ONE similarity transform
(rotation + translation, scale chosen so that each half has the source volume) for both halves together, the seam vertices of the two halves and the bag / strip contact vertices of the source (< 1.5 mm
apart) are one node each, and the residual to the neighbours' border vertices (the welded positions of the current page, which stay exactly where they are) is extended into the patch by a harmonic
(graph Laplacian) interpolation.  Nothing is invented: every vertex is the source vertex, rigidly placed, plus a smooth residual."""
from __future__ import annotations

import numpy as np
from scipy.sparse import coo_matrix, csr_matrix, diags
from scipy.sparse.linalg import spsolve
from scipy.spatial import cKDTree

IDS = ("zan_skin_urogenital_region_l", "zan_skin_urogenital_region_r")


def kabsch(X, Y, scale=False):
    mx, my = X.mean(0), Y.mean(0)
    A, B = X - mx, Y - my
    U, S, Vt = np.linalg.svd(A.T @ B)
    d = np.sign(np.linalg.det(U @ Vt)) or 1.0
    D = np.diag([1, 1, d])
    R = Vt.T @ D @ U.T
    s = float((S * np.array([1, 1, d])).sum() / (A ** 2).sum()) if scale else 1.0
    return s, R, mx, my


def volume(v, f):
    t = v[f]
    return float(np.einsum("ij,ij->i", t[:, 0], np.cross(t[:, 1], t[:, 2])).sum() / 6.0)


def build_nodes(raw, ids, tol=1.5):
    """union-find of vertices (patch, index) -> node: l / r seam pairs and bag / strip contacts (< tol in the source)"""
    off = np.cumsum([0] + [len(raw[i]) for i in ids])
    X = np.vstack([raw[i] for i in ids])
    n = len(X)
    par = np.arange(n)

    def find(a):
        while par[a] != a:
            par[a] = par[par[a]]
            a = par[a]
        return a
    tree = cKDTree(X)
    for a, b in tree.query_pairs(tol):
        ra, rb = find(a), find(b)
        if ra != rb:
            par[rb] = ra
    node = np.array([find(a) for a in range(n)])
    return X, node, off


def refit(raw, cur, faces, others_raw, others_cur, vol_target=None, tol_border=1.5, log=print):
    """raw / cur: {id: vertices} of the two patches (Z source, current page); faces {id: f}; others_*: {id: vertices} of all other skin patches (source / current).
    -> {id: new vertices}, report"""
    ids = list(IDS)
    X, node, off = build_nodes({i: raw[i] for i in ids}, ids)
    Y = np.vstack([cur[i] for i in ids])
    F = np.vstack([faces[i] + off[k] for k, i in enumerate(ids)])
    nn = len(X)
    # border vertices: within tol of another patch in the source
    ov = np.vstack([others_raw[i] for i in others_raw])
    oc = np.vstack([others_cur[i] for i in others_raw])
    d, k = cKDTree(ov).query(X)
    border = d < tol_border
    target = oc[k]                                          # the neighbour's current (welded) position of that border vertex
    # nodes
    uniq, inv = np.unique(node, return_inverse=True)
    m = len(uniq)
    Xn = np.zeros((m, 3)); cnt = np.zeros(m)
    np.add.at(Xn, inv, X); np.add.at(cnt, inv, 1)
    Xn /= cnt[:, None]
    Bn = np.zeros(m, bool); Tn = np.zeros((m, 3)); tc = np.zeros(m)
    for a in np.flatnonzero(border):
        Bn[inv[a]] = True
        Tn[inv[a]] += Y[a] * 0 + target[a]                  # average of the targets of the merged vertices
        tc[inv[a]] += 1
    Tn[Bn] /= tc[Bn][:, None]
    # graph Laplacian on the merged nodes
    e = np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]])
    e = np.unique(np.sort(inv[e], axis=1), axis=0)
    e = e[e[:, 0] != e[:, 1]]
    W = coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(m, m))
    W = (W + W.T).tocsr()
    L = diags(np.asarray(W.sum(1)).ravel()) - W
    free = np.flatnonzero(~Bn)
    bnd = np.flatnonzero(Bn)

    def place(s):
        s_, R, mx, my = kabsch(Xn[bnd], Tn[bnd], scale=False)
        P = s * (Xn - Xn[bnd].mean(0)) @ R.T + Tn[bnd].mean(0)
        res = np.zeros((m, 3))
        res[bnd] = Tn[bnd] - P[bnd]
        if len(free):
            A = L[free][:, free].tocsc()
            for c in range(3):
                b = -(L[free][:, bnd] @ res[bnd, c])
                res[free, c] = spsolve(A, b)
        Z = P + res
        out = {}
        for k_, i in enumerate(ids):
            out[i] = Z[inv[off[k_]: off[k_ + 1]]]
        return out
    vt = vol_target or volume(raw[ids[0]], faces[ids[0]])
    best = None
    for s in np.linspace(0.90, 1.12, 23):
        o = place(s)
        vv = [volume(o[i], faces[i]) for i in ids]
        err = max(abs(v / vt - 1) for v in vv)
        if best is None or err < best[0]:
            best = (err, s, o, vv)
    err, s, out, vv = best
    # refine
    for s2 in np.linspace(s - 0.01, s + 0.01, 21):
        o = place(s2)
        vv2 = [volume(o[i], faces[i]) for i in ids]
        e2 = max(abs(v / vt - 1) for v in vv2)
        if e2 < err:
            err, s, out, vv = e2, s2, o, vv2
    rep = {"scale": round(float(s), 4), "volume_target": round(vt), "volumes": [round(v) for v in vv], "border_vertices": int(border.sum()), "nodes": int(m), "merged_vertices": int(nn - m),
           "border_residual_mm_mean": round(float(np.linalg.norm(Tn[bnd] - (s * (Xn[bnd] - Xn[bnd].mean(0)) @ kabsch(Xn[bnd], Tn[bnd])[1].T + Tn[bnd].mean(0)), axis=1).mean()), 2)}
    log(f"   uro refit: {rep}")
    return out, rep
