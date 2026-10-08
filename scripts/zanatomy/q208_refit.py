"""Q208 slab refit: the Z source skin slabs of the forearm / wrist / elbow re-warped onto the person's own skin (q208_tube) and welded to the neighbours that stay where they are.

  Slabs      the topology of a set of source skin patches: twin vertex (inner <-> outer, 3.0 mm), merged nodes (vertices the patches share in the source), mesh graph
  tube_map   cylindrical re-warp of the forearm tube (bone-pair frames of the source and of the page, own skin radius)
  correct    boundary correction: vertices that coincide with a fixed neighbour in the source are pulled onto it, the correction decays harmonically (graph Laplacian) into the patch
"""
from __future__ import annotations

import numpy as np
from scipy.sparse import coo_matrix, csr_matrix, diags
from scipy.sparse.csgraph import connected_components
from scipy.sparse.linalg import spsolve
from scipy.spatial import cKDTree

from scripts.zanatomy import q208_tube as T


class Slabs:
    def __init__(self, raw_v, faces, ids, merge_tol=1.5):
        self.ids = list(ids)
        self.off = np.cumsum([0] + [len(raw_v[i]) for i in self.ids])
        self.V = np.vstack([raw_v[i] for i in self.ids])
        self.F = np.vstack([faces[i] + self.off[k] for k, i in enumerate(self.ids)])
        self.patch = np.concatenate([np.full(len(raw_v[i]), k) for k, i in enumerate(self.ids)])
        self.twin = np.zeros(len(self.V), int)
        for k, i in enumerate(self.ids):
            v = raw_v[i]
            d, kk = cKDTree(v).query(v, k=2)
            self.twin[self.off[k]:self.off[k + 1]] = kk[:, 1] + self.off[k]
        # merged nodes
        pr = cKDTree(self.V).query_pairs(merge_tol, output_type="ndarray")
        n = len(self.V)
        A = coo_matrix((np.ones(len(pr)), (pr[:, 0], pr[:, 1])), shape=(n, n))
        self.nnode, self.node = connected_components(A, directed=False)
        e = np.concatenate([self.F[:, [0, 1]], self.F[:, [1, 2]], self.F[:, [2, 0]]])
        e = np.unique(np.sort(self.node[e], axis=1), axis=0)
        self.edges = e[e[:, 0] != e[:, 1]]

    def split(self, arr):
        return {i: arr[self.off[k]:self.off[k + 1]] for k, i in enumerate(self.ids)}

    def outer_flags(self, rho=None, bone_pts=None):
        """outer sheet = the twin farther from the bones (bone_pts) or, without bones, from the centreline (rho); a vertex whose mesh neighbours are all of the other kind swaps with its twin (a twin pair that sits tangentially at a rim)"""
        if bone_pts is not None:
            d = cKDTree(bone_pts).query(self.V)[0]
            outer = d >= d[self.twin]
        else:
            outer = rho >= rho[self.twin]
        e = np.concatenate([self.F[:, [0, 1]], self.F[:, [1, 2]], self.F[:, [2, 0]]])
        for _ in range(3):
            n_out = np.bincount(e[:, 0], weights=outer[e[:, 1]], minlength=len(outer)) + np.bincount(e[:, 1], weights=outer[e[:, 0]], minlength=len(outer))
            n_all = np.bincount(e[:, 0], minlength=len(outer)) + np.bincount(e[:, 1], minlength=len(outer))
            frac = n_out / np.maximum(n_all, 1)
            flip = (outer & (frac == 0) & (n_all > 0)) | (~outer & (frac == 1) & (n_all > 0))
            if not flip.any():
                break
            new = outer.copy()
            new[flip] = ~outer[flip]
            lone = np.flatnonzero(flip & ~flip[self.twin])
            new[self.twin[lone]] = ~new[lone]
            outer = new
        return outer


def tube_positions(S, Fs, Fp, g, prof, margin=1.0, outer=None):
    """new positions of ALL vertices of Slabs S: outer vertices on the own skin (radius - margin), inner vertices = new outer twin - the source twin offset carried in the local cylindrical frame"""
    v = S.V
    sx, th, rho, _ = Fs.coords(v)
    if outer is None:
        outer = S.outer_flags(rho)
    sN = g(sx)
    org, e1, e2 = Fp.at(sN)
    rN = prof.at(sN, th) - margin
    ur = np.cos(th)[:, None] * e1 + np.sin(th)[:, None] * e2
    ut = -np.sin(th)[:, None] * e1 + np.cos(th)[:, None] * e2
    xo = org + rN[:, None] * ur
    off = v[S.twin] - v
    _, e1s, e2s = Fs.at(sx)
    urs = np.cos(th)[:, None] * e1s + np.sin(th)[:, None] * e2s
    uts = -np.sin(th)[:, None] * e1s + np.cos(th)[:, None] * e2s
    comp = np.stack([(off * urs).sum(1), (off * uts).sum(1), (off * Fs.a).sum(1)], 1)
    offp = comp[:, :1] * ur + comp[:, 1:2] * ut + comp[:, 2:3] * Fp.a
    new = np.where(outer[:, None], xo, xo[S.twin] - offp)
    return new, outer, dict(s=sx, theta=th, rho=rho, s_new=sN, rho_new=rN)


def laplacian(nnode, edges, w=None):
    w = np.ones(len(edges)) if w is None else w
    A = coo_matrix((np.r_[w, w], (np.r_[edges[:, 0], edges[:, 1]], np.r_[edges[:, 1], edges[:, 0]])), shape=(nnode, nnode)).tocsr()
    return diags(np.asarray(A.sum(1)).ravel()) - A, A


def correct(S, P, fixed_vertex_targets, mu=0.08, log=print):
    """P (n,3) positions of the vertices of S.  fixed_vertex_targets {vertex index: target xyz}: the correction d = target - P at those vertices (averaged per merged node) is extended harmonically
    into the patches: (L + mu I) d = 0 on the free nodes (the decay length ~ 1 / sqrt(mu) mesh edges).  Returns the corrected positions (every vertex of a node moves by the node's correction)."""
    n = S.nnode
    idx = np.array(sorted(fixed_vertex_targets))
    tgt = np.array([fixed_vertex_targets[i] for i in idx])
    d0 = tgt - P[idx]
    nodes = S.node[idx]
    D = np.zeros((n, 3))
    cnt = np.zeros(n)
    np.add.at(D, nodes, d0)
    np.add.at(cnt, nodes, 1)
    fixed = cnt > 0
    D[fixed] /= cnt[fixed][:, None]
    L, A = laplacian(n, S.edges)
    M = (L + mu * diags(np.ones(n))).tocsr()
    free = np.flatnonzero(~fixed)
    fx = np.flatnonzero(fixed)
    if len(free):
        rhs = -M[free][:, fx] @ D[fx]
        sol = spsolve(M[free][:, free].tocsc(), rhs)
        D[free] = sol
    return P + D[S.node], D


def twin_stray(raw_v, cur_v, ratio=2.0, min_mm=6.0):
    """vertices of a patch whose inner / outer twin pair (3.0 mm in the source) the earlier fits pulled apart (> ratio x and > min_mm): stray sheet vertices"""
    d, k = cKDTree(raw_v).query(raw_v, k=2)
    tw = k[:, 1]
    t0 = np.linalg.norm(raw_v - raw_v[tw], axis=1)
    t1 = np.linalg.norm(cur_v - cur_v[tw], axis=1)
    return (t1 > ratio * t0) & (t1 > min_mm)


def rim_targets(S, raw_v, neighbours_raw, neighbours_cur, tol=1.5):
    """vertices of S coinciding (source distance < tol) with a vertex of a fixed neighbour -> {vertex: (CURRENT position of that neighbour vertex, neighbour id, neighbour vertex index, stray flag)}"""
    nb_ids = list(neighbours_raw)
    pts = np.vstack([neighbours_raw[i] for i in nb_ids])
    cur = np.vstack([neighbours_cur[i] for i in nb_ids])
    own = np.concatenate([np.full(len(neighbours_raw[i]), k) for k, i in enumerate(nb_ids)])
    loc = np.concatenate([np.arange(len(neighbours_raw[i])) for i in nb_ids])
    stray = np.concatenate([twin_stray(neighbours_raw[i], neighbours_cur[i]) for i in nb_ids])
    d, k = cKDTree(pts).query(S.V)
    sel = np.flatnonzero(d < tol)
    return {int(i): (cur[k[i]], nb_ids[own[k[i]]], int(loc[k[i]]), bool(stray[k[i]])) for i in sel}


# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------
# as-similar-as-possible deformation of source slabs between fixed rims, pulled onto the person's own skin
# ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------
def node_graph(S, twin_weight=1.0):
    """edges of the node graph of Slabs S (mesh edges + inner / outer twin edges, so that the slab thickness is part of the shape) -> (edges, weights); node rest positions = mean source position"""
    e = [S.edges]
    w = [np.ones(len(S.edges))]
    tw = np.stack([S.node, S.node[S.twin]], 1)
    tw = np.unique(np.sort(tw, axis=1), axis=0)
    tw = tw[tw[:, 0] != tw[:, 1]]
    e.append(tw)
    w.append(np.full(len(tw), twin_weight))
    E = np.vstack(e)
    W = np.concatenate(w)
    key = E[:, 0].astype(np.int64) * S.nnode + E[:, 1]
    u, idx = np.unique(key, return_index=True)
    return E[idx], W[idx]


def node_values(S, arr):
    out = np.zeros((S.nnode, arr.shape[1]))
    cnt = np.zeros(S.nnode)
    np.add.at(out, S.node, arr)
    np.add.at(cnt, S.node, 1)
    return out / cnt[:, None]


def asap(S, X0, fixed, soft=None, iters=30, similarity=True, twin_weight=1.5, log=None, graph=None):
    """ASAP / ARAP: min sum_ij w_ij |(x_i - x_j) - s_i R_i (r_i - r_j)|^2 + sum_soft w_k |x_k - t_k|^2 with Dirichlet rows `fixed` {node: xyz}.
    r = node rest positions (Z source), X0 node starting positions (n,3).  soft: (nodes, targets (m,3), weights (m,)).  Returns node positions."""
    E, Wt = node_graph(S, twin_weight) if graph is None else graph
    n = S.nnode
    r = node_values(S, S.V)
    i, j = E[:, 0], E[:, 1]
    A = coo_matrix((np.r_[Wt, Wt], (np.r_[i, j], np.r_[j, i])), shape=(n, n)).tocsr()
    L = (diags(np.asarray(A.sum(1)).ravel()) - A).tocsr()
    nodes_f = np.array(sorted(fixed))
    isf = np.zeros(n, bool)
    isf[nodes_f] = True
    ingraph = np.zeros(n, bool)
    ingraph[E.ravel()] = True
    free = np.flatnonzero(~isf & ingraph)
    Df = diags(np.zeros(n))
    if soft is not None:
        sn, st, sw = soft
        d = np.zeros(n)
        np.add.at(d, sn, sw)
        Df = diags(d)
    M = (L + Df).tocsr()
    Mff = M[free][:, free].tocsc()
    from scipy.sparse.linalg import splu
    lu = splu(Mff)
    X = X0.copy()
    for k, p in fixed.items():
        X[k] = p
    nbr = [[] for _ in range(n)]
    for (a, b), w in zip(E, Wt):
        nbr[a].append((b, w))
        nbr[b].append((a, w))
    for it in range(iters):
        # local step
        Rm = np.zeros((n, 3, 3))
        sc = np.ones(n)
        for a in range(n):
            nb = nbr[a]
            if not nb:
                Rm[a] = np.eye(3)
                continue
            js = np.array([q for q, _ in nb])
            ww = np.array([w for _, w in nb])
            P = (r[a] - r[js]) * ww[:, None]
            Q = X[a] - X[js]
            C = P.T @ Q
            U, Sg, Vt = np.linalg.svd(C)
            R = Vt.T @ np.diag([1, 1, np.sign(np.linalg.det(Vt.T @ U.T))]) @ U.T
            Rm[a] = R
            if similarity:
                num = np.einsum("ij,ij->", (P @ R.T), Q) if False else (Q * ((r[a] - r[js]) @ R.T) * ww[:, None]).sum()
                den = (ww * ((r[a] - r[js]) ** 2).sum(1)).sum()
                sc[a] = np.clip(num / max(den, 1e-12), 0.5, 2.0)
        # global step: rhs_i = sum_j w_ij (s_i R_i + s_j R_j)/2 (r_i - r_j) + soft
        rhs = np.zeros((n, 3))
        ri = (sc[i, None] * np.einsum("kab,kb->ka", Rm[i], r[i] - r[j]))
        rj = (sc[j, None] * np.einsum("kab,kb->ka", Rm[j], r[i] - r[j]))
        t = 0.5 * Wt[:, None] * (ri + rj)
        np.add.at(rhs, i, t)
        np.add.at(rhs, j, -t)
        if soft is not None:
            np.add.at(rhs, sn, sw[:, None] * st)
        b = rhs[free] - M[free][:, nodes_f] @ np.array([fixed[k] for k in nodes_f])
        Xn = X.copy()
        Xn[free] = lu.solve(b)
        delta = np.abs(Xn - X).max()
        X = Xn
        if log and it % 5 == 0:
            log(f"      asap it {it}: max change {delta:.3f} mm")
        if delta < 0.01:
            break
    return X


def outer_graph(S, outer, spring="inv_len"):  # spring: "inv_len" (1 / source length) or "uniform"
    """edges between OUTER nodes (mesh edges whose both ends are outer vertices), weights = spring constants 1 / source length"""
    e = np.concatenate([S.F[:, [0, 1]], S.F[:, [1, 2]], S.F[:, [2, 0]]])
    m = outer[e[:, 0]] & outer[e[:, 1]]
    a, b = S.node[e[m, 0]], S.node[e[m, 1]]
    key = np.unique(np.sort(np.stack([a, b], 1), axis=1), axis=0)
    key = key[key[:, 0] != key[:, 1]]
    r = node_values(S, S.V)
    L = np.linalg.norm(r[key[:, 0]] - r[key[:, 1]], axis=1)
    w = 1.0 / np.maximum(L, 0.5) if spring == "inv_len" else np.ones(len(key))
    return key, w


def surface_harmonic(S, outer, fixed, own_tm, margin=1.0, iters=300, log=None, hint=None, spring="inv_len", start="harmonic", step=1.0, proj_every=5, centre=None):
    """outer sheet of Slabs S laid on the person's own skin between fixed rim nodes: graph-Laplacian (spring) positions with the rim nodes fixed, every free node re-projected onto the own skin (nearest point,
    moved `margin` inward) after each relaxation sweep.  Returns node positions (n, 3) of the outer nodes (others zero), the node normals (own skin normals, smoothed) and a mask of outer nodes."""
    import trimesh
    n = S.nnode
    onode = np.zeros(n, bool)
    onode[S.node[outer]] = True

    def project(P):
        """(point on own skin, own-skin normal): nearest point, or (centre given) the first exit of the ray from `centre` through the point (keeps every node on its own side of the limb)"""
        if centre is None:
            cp, dist, tri = trimesh.proximity.closest_point(own_tm, P)
            return cp, own_tm.face_normals[tri]
        if np.ndim(centre) == 3:           # centreline: list of segments (a, b); origin of the ray = closest point of the polyline
            org = np.zeros_like(P)
            bd = np.full(len(P), np.inf)
            for a_, b_ in centre:
                ab = b_ - a_
                t_ = np.clip(((P - a_) @ ab) / (ab @ ab), 0, 1)
                c_ = a_ + t_[:, None] * ab
                dd_ = np.linalg.norm(P - c_, axis=1)
                m_ = dd_ < bd
                org[m_], bd[m_] = c_[m_], dd_[m_]
        else:
            org = np.tile(centre, (len(P), 1))
        d = P - org
        d /= np.maximum(np.linalg.norm(d, axis=1, keepdims=True), 1e-9)
        O = org
        loc, ray, tri = own_tm.ray.intersects_location(O, d, multiple_hits=True)
        cp = P.copy()
        nf = np.zeros_like(P)
        best = np.full(len(P), np.inf)
        dist = np.linalg.norm(loc - O[ray], axis=1)
        for l, r_, t_, di in zip(loc, ray, tri, dist):
            if di < best[r_]:
                best[r_], cp[r_], nf[r_] = di, l, own_tm.face_normals[t_]
        miss = ~np.isfinite(best)
        if miss.any():
            c2, d2, t2 = trimesh.proximity.closest_point(own_tm, P[miss])
            cp[miss], nf[miss] = c2, own_tm.face_normals[t2]
        return cp, nf
    key, w = outer_graph(S, outer, spring)
    A = coo_matrix((np.r_[w, w], (np.r_[key[:, 0], key[:, 1]], np.r_[key[:, 1], key[:, 0]])), shape=(n, n)).tocsr()
    deg = np.asarray(A.sum(1)).ravel()
    lone = onode & (deg == 0)  # an outer vertex without an outer neighbour (a stray twin pair of a rim): placed from the outer twins of its neighbours below
    onode &= deg > 0
    isf = np.zeros(n, bool)
    for k in fixed:
        isf[k] = True
    free = onode & ~isf
    X = np.zeros((n, 3))
    for k, p in fixed.items():
        X[k] = p
    # outer components that touch no fixed node (islands: nothing to interpolate between) keep the hint positions (node mean of `hint`, the current page) and are only draped on the own skin
    nc, lab = connected_components(A, directed=False)
    has_fixed = np.zeros(nc, bool)
    has_fixed[lab[isf & onode]] = True
    island = free & ~has_fixed[lab]
    if island.any():
        X[island] = node_values(S, hint if hint is not None else S.V)[island]
        free = free & ~island
        isl_idx = np.flatnonzero(island)
    # harmonic start over the outer graph
    Lm = (diags(deg) - A).tocsr()
    fr = np.flatnonzero(free)
    fx = np.flatnonzero(isf & onode)
    D = X[fx]
    if start == "hint":
        X[fr] = node_values(S, hint if hint is not None else S.V)[fr]
        cp0, nf0 = project(X[fr])
        X[fr] = cp0 - margin * nf0
    else:
        X[fr] = spsolve(Lm[fr][:, fr].tocsc(), -Lm[fr][:, fx] @ D)
    nrm = np.zeros((n, 3))
    if island.any():
        cp, nf = project(X[island])
        X[island] = cp - margin * nf
        nrm[island] = nf
    for it in range(iters):
        Xn = X.copy()
        Xn[fr] = X[fr] + step * ((A[fr] @ X) / deg[fr][:, None] - X[fr])
        X = Xn
        if it % proj_every == proj_every - 1 or it == iters - 1:
            cp, nf = project(X[fr])
            X[fr] = cp - margin * nf
            nrm[fr] = nf
    if lone.any():
        e = np.concatenate([S.F[:, [0, 1]], S.F[:, [1, 2]], S.F[:, [2, 0]]])
        for nd in np.flatnonzero(lone):
            vs = np.flatnonzero(S.node == nd)
            nb = np.unique(e[np.isin(e[:, 0], vs), 1])
            nb = nb[~np.isin(nb, vs)]
            ref = S.node[S.twin[nb]]
            ref = ref[onode[ref]]
            if len(ref):
                p = X[ref].mean(0)
                cp, dist, tri = trimesh.proximity.closest_point(own_tm, p[None])
                X[nd] = cp[0] - margin * own_tm.face_normals[tri[0]]
                nrm[nd] = own_tm.face_normals[tri[0]]
                onode[nd] = True
    # normals at fixed outer nodes: from the own skin too
    if len(fx):
        cp, dist, tri = trimesh.proximity.closest_point(own_tm, X[fx])
        nrm[fx] = own_tm.face_normals[tri]
    # smooth the normals over the outer graph
    for _ in range(3):
        nn = (A @ nrm + nrm) / (deg + 1)[:, None]
        nrm = nn / np.maximum(np.linalg.norm(nn, axis=1, keepdims=True), 1e-9)
    return X, nrm, onode


def mesh_normals(S, outer, X, nrm_own):
    """outward vertex normals of the outer sheet from its own faces (area weighted), oriented like the own-skin normals; nodes without an outer face keep the own-skin normal"""
    Fn = S.node[S.F]
    fo = outer[S.F].all(1)
    t = X[Fn[fo]]
    fn = np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0])
    acc = np.zeros((S.nnode, 3))
    for k in range(3):
        np.add.at(acc, Fn[fo][:, k], fn)
    nl = np.linalg.norm(acc, axis=1)
    flip = (acc * nrm_own).sum(1) < 0
    acc[flip] *= -1
    out = nrm_own.copy()
    ok = nl > 1e-9
    out[ok] = acc[ok] / nl[ok][:, None]
    return out


def drape_asap(S, outer, X, fixed, own_tm, margin=1.0, w_pull=8.0, rounds=6, iters=20, free_mask=None):
    """as-similar-as-possible relaxation of the OUTER sheet (outer-outer edges only, rest = source) between the fixed rim nodes, every round pulled hard onto the own skin and finally projected onto it.
    X: start positions (node array); free_mask: nodes allowed to move (default: free outer nodes)"""
    import trimesh
    key, w = outer_graph(S, outer, "uniform")
    onode = np.zeros(S.nnode, bool)
    onode[S.node[outer]] = True
    isf = np.zeros(S.nnode, bool)
    for k in fixed:
        isf[k] = True
    free = onode & ~isf if free_mask is None else free_mask
    fr = np.flatnonzero(free)
    X = X.copy()
    for rd in range(rounds):
        cp, dist, tri = trimesh.proximity.closest_point(own_tm, X[fr])
        targ = cp - margin * own_tm.face_normals[tri]
        X = asap(S, X, fixed, soft=(fr, targ, np.full(len(fr), w_pull)), iters=iters, graph=(key, w))
    cp, dist, tri = trimesh.proximity.closest_point(own_tm, X[fr])
    X[fr] = cp - margin * own_tm.face_normals[tri]
    nrm = np.zeros((S.nnode, 3))
    nrm[fr] = own_tm.face_normals[tri]
    return X, nrm


def lbs_positions(S, raw, pg, side, s_arm=-290.0, s_fore=-220.0, Fs=None):
    """pose-driven starting positions of the source vertices of the elbow slabs: linear blend of the similarity transforms of the humerus and of the forearm bones (Z source -> fitted page), weights by the source
    coordinate s along the forearm axis (smoothstep between s_arm and s_fore).  Keeps the side (anterior / lateral / ...) of every vertex."""
    from scripts.zanatomy.q207_uro import kabsch
    s_ = "_" + side

    def sim(ids):
        X = np.vstack([raw.v(i) for i in ids])
        Y = np.vstack([pg.v(i) for i in ids])
        sc, R, mx, my = kabsch(X, Y, scale=True)
        return lambda P: sc * (P - mx) @ R.T + my
    Ta = sim(["humerus" + s_])
    Tf = sim(["radius" + s_, "ulna" + s_])
    sx = Fs.coords(S.V)[0]
    t = np.clip((sx - s_arm) / (s_fore - s_arm), 0, 1)
    w = (t * t * (3 - 2 * t))[:, None]
    return w * Tf(S.V) + (1 - w) * Ta(S.V)


def rim_ruled_positions(S, Fs, top, bottom):
    """starting positions of the source vertices of a ring-shaped band between two fixed rims: the band is unrolled with the source cylindrical coordinates (u = theta, v = s about the forearm frame Fs);
    top / bottom = {vertex: target xyz} of the vertices that coincide with the neighbour above / below.  A vertex at (u, v) is placed on the straight line between the rim points of the same u
    (rim curves interpolated periodically in u) at the fraction lam = (v - v_top(u)) / (v_bot(u) - v_top(u))."""
    s_, th, rho, _ = Fs.coords(S.V)

    def curve(rim):
        idx = np.array(sorted(rim))
        u = th[idx]
        o = np.argsort(u)
        idx, u = idx[o], u[o]
        pos = np.array([rim[i] for i in idx])
        return u, s_[idx], pos

    ut, vt, pt = curve(top)
    ub, vb, pb = curve(bottom)

    def interp(u, uk, arr):
        out = np.zeros((len(u), arr.shape[1]))
        for c in range(arr.shape[1]):
            out[:, c] = np.interp(u, uk, arr[:, c], period=2 * np.pi)
        return out
    Pt, Pb = interp(th, ut, pt), interp(th, ub, pb)
    Vt = np.interp(th, ut, vt, period=2 * np.pi)
    Vb = np.interp(th, ub, vb, period=2 * np.pi)
    lam = np.clip((s_ - Vt) / np.where(np.abs(Vb - Vt) < 1e-6, 1e-6, Vb - Vt), 0, 1)
    return (1 - lam)[:, None] * Pt + lam[:, None] * Pb
