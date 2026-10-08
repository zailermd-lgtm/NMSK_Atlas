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


def build_nodes(raw, ids, tol=1.5, seam_mm=4.5, comp_mm=14.0, faces=None):
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
    # the seam slit between the two halves (up to ~6 mm in the source itself, wider than the closing radius of the audit's envelope): vertices of one half within seam_mm of the other half at the midline are one node too
    if len(ids) == 2 and seam_mm:
        l0, r0 = off[0], off[1]
        xl, xr = X[off[0]:off[1]], X[off[1]:off[2]]
        tr = cKDTree(xr)
        d, k = tr.query(xl)
        for a in np.flatnonzero((d < seam_mm) & (np.abs(xl[:, 0]) < 8.0)):
            ra, rb = find(off[0] + a), find(off[1] + int(k[a]))
            if ra != rb:
                par[rb] = ra
        d2, k2 = cKDTree(xl).query(xr)
        for b in np.flatnonzero((d2 < seam_mm) & (np.abs(xr[:, 0]) < 8.0)):
            ra, rb = find(off[0] + int(k2[b])), find(off[1] + b)
            if ra != rb:
                par[rb] = ra
    # the strip of each half hangs from the bag along a top edge that lies within a few mm of the bag in the source (1.3 / 2.1 / 2.1 / 4.2 / 4.9 / 4.9 mm): those vertex pairs (different components of the same half) are one node
    if faces is not None and comp_mm:
        for k, i in enumerate(ids):
            nc, lab = components(faces[i], off[k + 1] - off[k])
            sz = np.bincount(lab)
            big = np.isin(lab, np.flatnonzero(sz >= 100))
            vb = np.flatnonzero(big); vs = np.flatnonzero(~big)
            if len(vs) and len(vb):
                d, kk = cKDTree(X[off[k] + vb]).query(X[off[k] + vs])
                for a in np.flatnonzero(d < comp_mm):
                    ra, rb = find(off[k] + vs[a]), find(off[k] + vb[int(kk[a])])
                    if ra != rb:
                        par[rb] = ra
    node = np.array([find(a) for a in range(n)])
    return X, node, off


def components(f, n):
    from scipy.sparse.csgraph import connected_components
    A = coo_matrix((np.ones(len(f) * 3), (np.r_[f[:, 0], f[:, 1], f[:, 2]], np.r_[f[:, 1], f[:, 2], f[:, 0]])), shape=(n, n))
    return connected_components(A, directed=False)


def refit(raw, cur, faces, others_raw, others_cur, others_faces=None, vol_target=None, tol_border=1.5, near_mm=140.0, w_c=1000.0, tie_mm=6.5, w_tie=20.0, strip_max_vertices=100, keep_strips=False, split=(), conflict_mm=3.0, log=print):
    """raw / cur: {id: vertices} of the two patches (Z source, current page); faces {id: f}; others_*: {id: vertices} of all other skin patches (source / current state).
    The two small components of each half (the perineal strips) are NOT refit: they stay where the Q202 weld put them and act as neighbours (the bag / strip contact vertices of the source are tied to them).
    Constraints for the bag components = every place where they touch a neighbour in the SOURCE: (a) vertices within tol of a neighbour's vertex or ON a neighbour's face -> pulled onto that point of the
    neighbour's current surface; (b) vertices of a neighbour lying on a face of the bag -> the face (barycentric) is pulled through that vertex; (c) soft ties (weight w_tie) of every bag vertex within
    tie_mm of a neighbour surface to that surface with the source offset.  The neighbours do not move.  -> {id: new vertices}, report"""
    import trimesh
    from scripts.zanatomy import q202_contact as K
    ids = list(IDS)
    # components: the strips stay, the bags are refit
    isbag = {}
    for i in ids:
        nc, lab = components(faces[i], len(raw[i]))
        sz = np.bincount(lab)
        isbag[i] = np.isin(lab, np.flatnonzero(sz >= strip_max_vertices)) if keep_strips else np.ones(len(raw[i]), bool)
    # pseudo patches for the strips (fixed)
    oraw, ocur, ofac = dict(others_raw), dict(others_cur), dict(others_faces or {})
    for i in ids:
        sv = np.flatnonzero(~isbag[i])
        if len(sv):
            remap = -np.ones(len(raw[i]), int); remap[sv] = np.arange(len(sv))
            fm = (~isbag[i][faces[i]]).all(1)
            oraw["strip_" + i] = raw[i][sv]; ocur["strip_" + i] = cur[i][sv]; ofac["strip_" + i] = remap[faces[i][fm]]
    X, node, off = build_nodes({i: raw[i] for i in ids}, ids, faces=faces)
    node = node.copy()
    for root in split:                       # nodes whose hard targets of the two halves disagree: the right half gets its own node again (the seam stays open there as in the current page)
        sel = (node == root) & (np.arange(len(node)) >= off[1])
        node[sel] = 10_000_000 + root
    # drop the strip vertices from the node set: each strip vertex is its own (fixed) vertex
    F_all = np.vstack([faces[i] + off[k] for k, i in enumerate(ids)])
    bagmask = np.concatenate([isbag[i] for i in ids])
    uniq, inv = np.unique(node, return_inverse=True)
    m = len(uniq)
    Xn = np.zeros((m, 3)); cnt = np.zeros(m)
    np.add.at(Xn, inv, X); np.add.at(cnt, inv, 1)
    Xn /= cnt[:, None]
    nodes_bag = np.zeros(m, bool); nodes_bag[inv[bagmask]] = True
    # the bag faces
    Fb = F_all[bagmask[F_all].all(1)]
    c0 = X.mean(0)
    oids = [i for i in oraw if np.linalg.norm(oraw[i] - c0, axis=1).min() < near_mm]
    allids = ids + oids
    fall = dict(faces); fall.update(ofac)
    rawd = {i: {"v": (raw[i] if i in raw else oraw[i]), "f": fall[i]} for i in allids}
    cons = K.contacts(rawd, allids, tol=1.0)
    curd = dict(cur); curd.update(ocur)
    rows, wts, dirichlet = [], [], []
    for (pi, a, pj, vi, w, d0) in cons:
        A_, B_ = allids[pi], allids[pj]
        a_uro, b_uro = A_ in ids, B_ in ids
        if a_uro and b_uro:
            continue
        if a_uro and not b_uro:
            nd = inv[off[ids.index(A_)] + a]
            if not bagmask[off[ids.index(A_)] + a]:
                continue
            tgt = (curd[B_][vi] * w[:, None]).sum(0)
            rows.append(([(nd, 1.0)], tgt)); wts.append(1.0); dirichlet.append((nd, tgt))
        elif b_uro and not a_uro:
            offB = off[ids.index(B_)]
            if not all(bagmask[offB + int(q)] for q, wq in zip(vi, w) if wq > 0):
                continue
            rows.append(([(inv[offB + int(q)], float(wq)) for q, wq in zip(vi, w) if wq > 0], curd[A_][a])); wts.append(1.0)
    ov = np.vstack([oraw[i] for i in oids]); oc = np.vstack([ocur[i] for i in oids])
    d, k = cKDTree(ov).query(X)
    for a in np.flatnonzero((d < tol_border) & bagmask):
        rows.append(([(inv[a], 1.0)], oc[k[a]])); wts.append(1.0); dirichlet.append((inv[a], oc[k[a]]))
    n_hard = len(rows)
    Vo, Fo, off2 = [], [], 0
    for i in oids:
        Vo.append(oraw[i]); Fo.append(fall[i] + off2); off2 += len(oraw[i])
    Vo, Fo = np.vstack(Vo), np.vstack(Fo)
    Vc = np.vstack([ocur[i] for i in oids])
    tmo = trimesh.Trimesh(Vo, Fo, process=False)
    cl, dist, tid = trimesh.proximity.closest_point(tmo, X)
    bcs = trimesh.triangles.points_to_barycentric(Vo[Fo[tid]], cl)
    bcs = np.clip(bcs, 0, 1); bcs /= bcs.sum(1, keepdims=True)
    for a in np.flatnonzero((dist >= 0.05) & (dist < tie_mm) & (d >= tol_border) & bagmask):
        tgt = (Vc[Fo[tid[a]]] * bcs[a][:, None]).sum(0) + (X[a] - cl[a])
        rows.append(([(inv[a], 1.0)], tgt)); wts.append(w_tie / w_c)
    # diagnostics: nodes whose hard targets (from different neighbour vertices) disagree
    from collections import defaultdict
    tg = defaultdict(list)
    for (lst, tgt) in rows[:n_hard]:
        if len(lst) == 1:
            tg[lst[0][0]].append(tgt)
    conflicts = []
    for nd, lst in tg.items():
        if len(lst) > 1:
            a = np.array(lst)
            sp = float(np.linalg.norm(a[:, None] - a[None], axis=2).max())
            if sp > conflict_mm:
                conflicts.append((round(sp, 1), np.round(a.mean(0), 0).tolist(), int(uniq[nd])))
    log(f"   hard-target conflicts > {conflict_mm} mm at {len(conflicts)} nodes: {sorted(conflicts, reverse=True)[:8]}")
    log(f"   uro refit (bags; strips kept): {n_hard} hard constraints + {len(rows) - n_hard} soft ties, {int(nodes_bag.sum())} bag nodes")
    e = np.concatenate([Fb[:, [0, 1]], Fb[:, [1, 2]], Fb[:, [2, 0]]])
    e = np.unique(np.sort(inv[e], axis=1), axis=0)
    e = e[e[:, 0] != e[:, 1]]
    W = coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(m, m))
    W = (W + W.T).tocsr()
    L = (diags(np.asarray(W.sum(1)).ravel()) - W).tocsc()
    ri, ci, vv = [], [], []
    T = np.zeros((len(rows), 3))
    for r_, (lst, tgt) in enumerate(rows):
        T[r_] = tgt
        for nd, w in lst:
            ri.append(r_); ci.append(nd); vv.append(w)
    Cm = coo_matrix((vv, (ri, ci)), shape=(len(rows), m)).tocsr()
    Wd = diags(np.array(wts))
    free = np.flatnonzero(nodes_bag)
    A = (L + w_c * (Cm.T @ Wd @ Cm)).tocsc()
    dn = np.array([d_[0] for d_ in dirichlet]); dt = np.array([d_[1] for d_ in dirichlet])
    un, ui = np.unique(dn, return_index=True)
    strip_cur = {i: cur[i] for i in ids}

    def place(s):
        _, R, mx, my = kabsch(Xn[un], dt[ui], scale=False)
        P = s * (Xn - Xn[un].mean(0)) @ R.T + dt[ui].mean(0)
        res = np.zeros((m, 3))
        rhs = w_c * (Cm.T @ (Wd @ (T - Cm @ P)))
        Af = A[free][:, free].tocsc()
        for c in range(3):
            res[free, c] = spsolve(Af, rhs[free, c])
        Z = P + res
        out = {}
        for k_, i in enumerate(ids):
            v = Z[inv[off[k_]: off[k_ + 1]]].copy()
            v[~isbag[i]] = cur[i][~isbag[i]]
            out[i] = v
        return out, Z
    vt = vol_target or volume(raw[ids[0]], faces[ids[0]])
    best = None
    for s in np.linspace(0.30, 1.12, 83):
        o, Z = place(s)
        vv_ = [volume(o[i], faces[i]) for i in ids]
        err = max(abs(v / vt - 1) for v in vv_)
        if best is None or err < best[0]:
            best = (err, s, o, vv_, Z)
    err, s, out, vv_, Z = best
    for s2 in np.linspace(s - 0.01, s + 0.01, 21):
        o, Z2 = place(s2)
        v2 = [volume(o[i], faces[i]) for i in ids]
        e2 = max(abs(v / vt - 1) for v in v2)
        if e2 < err:
            err, s, out, vv_, Z = e2, s2, o, v2, Z2
    resid = np.linalg.norm(Cm @ Z - T, axis=1)[:n_hard]
    big = np.argsort(-resid)[:8]
    log("   largest hard-constraint residuals (mm, target xyz, nodes): " + str([(round(float(resid[b]), 1), np.round(T[b], 0).tolist(), [n_ for n_, w_ in rows[b][0]][:3]) for b in big]))
    rep = {"scale": round(float(s), 4), "volume_target": round(vt), "volumes": [round(v) for v in vv_], "hard_constraints": n_hard, "soft_ties": len(rows) - n_hard,
           "constraint_residual_mm_mean_max": [round(float(resid.mean()), 2), round(float(resid.max()), 2)], "bag_nodes": int(nodes_bag.sum()), "strip_vertices_kept": int((~np.concatenate([isbag[i] for i in ids])).sum()), "conflict_roots": [c[2] for c in conflicts], "split_nodes": len(split)}
    log(f"   uro refit: {rep}")
    return out, rep


def refit_split(raw, cur, faces, others_raw, others_cur, others_faces=None, log=print, **kw):
    """refit, then split the l / r seam nodes whose hard targets (the neighbours of the two halves) disagree by more than conflict_mm and refit again"""
    out, rep = refit(raw, cur, faces, others_raw, others_cur, others_faces, log=log, **kw)
    roots = rep.get("conflict_roots", [])
    if roots:
        log(f"   splitting {len(roots)} seam nodes whose neighbours disagree and refitting")
        out, rep = refit(raw, cur, faces, others_raw, others_cur, others_faces, split=tuple(roots), log=log, **kw)
        rep["split_nodes"] = len(roots)
    return out, rep
