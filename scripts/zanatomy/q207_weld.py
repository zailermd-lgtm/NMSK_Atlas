"""Q207 seam repair by ONE sparse least-squares solve (replaces the iterative half-way pull of Q199 / Q202, which oscillates where a vertex touches several patches):
   minimise   sum_c w_c |(x_a + u_a) - sum_j b_j (x_bj + u_bj)|^2        constraints c: shared border vertex pairs and source contacts (a vertex of one slab on the face of another, < 1 mm in the Z source)
            + lam_s sum_(i,j in near) |u_i - u_j|^2                        smoothness over mesh edges AND 3D neighbours of the same patch (both sheets of a slab move as one: thickness kept)
            + lam_0 sum |u|^2                                              minimal movement
   over the displacements of the 'free' patches (the others are fixed, u = 0); gate: only constraints whose gap is above `gate` pull with full weight, the others hold (weight w_hold)."""
from __future__ import annotations

import numpy as np
from scipy.sparse import coo_matrix, csr_matrix, identity, vstack
from scipy.sparse.linalg import cg
from scipy.spatial import cKDTree


def border_pairs(raw, ids, tol=1.5):
    """[(pa, a, [(pb, b, w)])] shared border vertices of adjacent patches (source distance < tol): vertex a of ids[pa] with its nearest partner vertex b of ids[pb]"""
    cons = []
    trees = {i: cKDTree(raw[i]) for i in ids}
    for x in range(len(ids)):
        for y in range(x + 1, len(ids)):
            d, k = trees[ids[y]].query(raw[ids[x]])
            sel = np.flatnonzero(d < tol)
            if len(sel) < 3:
                continue
            for a in sel:
                cons.append((x, int(a), [(y, int(k[a]), 1.0)]))
    return cons


def contact_cons(contacts, ids):
    """contacts of q202_contact.contacts -> same format (partner = barycentric points of a face / edge of the other patch)"""
    out = []
    for (pi, a, pj, vi, w, d0) in contacts:
        out.append((pi, int(a), [(pj, int(q), float(wq)) for q, wq in zip(vi, w) if wq > 0]))
    return out


def solve(V, faces, ids, cons, free, gate_gap=1.0, w_pull=1.0, w_hold=0.2, lam_s=2.0, lam_0=0.01, knn=6, near_mm=6.0, log=print):
    """V {id: (n,3)} current; returns {id: new V} for the free patches"""
    off = {}
    o = 0
    for i in ids:
        if i in free:
            off[i] = o
            o += len(V[i])
    N = o
    if N == 0:
        return {}
    rows, cols, vals = [], [], []
    rhs = []
    r = 0

    def pos(pidx, vidx):
        return V[ids[pidx]][vidx]
    for (pa, a, partners) in cons:
        A, Bs = ids[pa], [ids[p] for p, _, _ in partners]
        pt = sum(w * V[ids[p]][q] for p, q, w in partners)
        gap = V[A][a] - pt
        g = float(np.linalg.norm(gap))
        wt = w_pull if g > gate_gap else w_hold
        if A not in free and all(b not in free for b in Bs):
            continue
        # residual = (x_a + u_a) - sum_j b_j (x_bj + u_bj) = gap + u_a - sum b_j u_bj  -> want 0
        coef = []
        if A in free:
            coef.append((off[A] + a, 1.0))
        for p, q, w in partners:
            if ids[p] in free:
                coef.append((off[ids[p]] + q, -w))
        for c, v in coef:
            rows.append(r); cols.append(c); vals.append(v * np.sqrt(wt))
        rhs.append(-gap * np.sqrt(wt))
        r += 1
    C = coo_matrix((vals, (rows, cols)), shape=(r, N)).tocsr()
    R = np.array(rhs).reshape(-1, 3)
    # smoothness
    srows, scols, svals = [], [], []
    k = 0
    for i in ids:
        if i not in free:
            continue
        v, f = V[i], faces[i]
        e = np.unique(np.sort(np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]), axis=1), axis=0)
        d, nb = cKDTree(v).query(v, k=knn + 1)
        pairs = [e]
        a = np.repeat(np.arange(len(v)), knn)
        b = nb[:, 1:].ravel()
        dd = d[:, 1:].ravel()
        m = dd < near_mm
        pairs.append(np.sort(np.stack([a[m], b[m]], 1), axis=1))
        P = np.unique(np.vstack(pairs), axis=0)
        for s_, (x, y) in enumerate(P):
            pass
        n = len(P)
        idx = np.arange(n) + k
        srows += [idx, idx]
        scols += [off[i] + P[:, 0], off[i] + P[:, 1]]
        svals += [np.full(n, np.sqrt(lam_s)), np.full(n, -np.sqrt(lam_s))]
        k += n
    S = coo_matrix((np.concatenate(svals), (np.concatenate(srows), np.concatenate(scols))), shape=(k, N)).tocsr()
    M = (C.T @ C + S.T @ S + lam_0 * identity(N)).tocsr()
    U = np.zeros((N, 3))
    for c in range(3):
        b = C.T @ R[:, c]
        U[:, c], info = cg(M, b, x0=np.zeros(N), rtol=1e-8, maxiter=4000)
    out = {i: V[i] + U[off[i]: off[i] + len(V[i])] for i in free}
    return out
