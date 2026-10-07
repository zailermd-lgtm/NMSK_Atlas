"""Q202: perineal SURFACE CLOSURE for the two female variants (rule-based hole fill, not anatomy).

The Z-Anatomy base has no female perineal skin: the two male-only urogenital patches are deleted (Q196) and the neighbouring skin slabs (anal, hypogastric, inguinal, femoral triangle,
thigh) are left with a closed loop of free rim vertices (36 vertices, q202_loop.py).  The closure is a closed thin slab like every Z skin patch: its OUTER sheet is the discrete minimal
surface (Pinkall-Polthier iteration of the cotangent Laplacian, Dirichlet boundary = the loop, start = the harmonic map) spanning that loop, its INNER sheet is the same sheet moved by the
3.0 mm rim offset of the neighbouring slabs (boundary = their inner rim vertices, harmonic in between) and a rim wall joins the two.  Boundary vertices are the neighbours' own
vertices (shared positions = welded seam); nothing is added that has a shape of its own: no labia, no clitoris, no vaginal opening.
"""
from __future__ import annotations

import numpy as np
import scipy.sparse as sp
import scipy.sparse.linalg as spl


def _edges(f):
    e = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
    return np.sort(e, axis=1)


def subdivide(v, f):
    """1-to-4 midpoint subdivision"""
    e = _edges(f)
    u, inv = np.unique(e, axis=0, return_inverse=True)
    mid = 0.5 * (v[u[:, 0]] + v[u[:, 1]])
    nv = np.vstack([v, mid])
    m = len(v) + inv.reshape(-1)
    nf = len(f)
    m01, m12, m20 = m[:nf], m[nf:2 * nf], m[2 * nf:]
    a, b, c = f[:, 0], f[:, 1], f[:, 2]
    F = np.concatenate([np.stack([a, m01, m20], 1), np.stack([b, m12, m01], 1), np.stack([c, m20, m12], 1), np.stack([m01, m12, m20], 1)])
    return nv, F


def laplacian(v, f, kind="uniform"):
    n = len(v)
    i = np.concatenate([f[:, 0], f[:, 1], f[:, 2]])
    j = np.concatenate([f[:, 1], f[:, 2], f[:, 0]])
    if kind == "uniform":
        w = np.ones(len(i))
        Wm = sp.coo_matrix((np.r_[w, w], (np.r_[i, j], np.r_[j, i])), shape=(n, n)).tocsr()
        Wm.data[:] = 1.0
    else:
        wl = []
        for k in range(3):
            a, b, c = f[:, k], f[:, (k + 1) % 3], f[:, (k + 2) % 3]      # angle at c opposite edge (a,b)
            u, w_ = v[a] - v[c], v[b] - v[c]
            cot = np.einsum("ij,ij->i", u, w_) / np.maximum(np.linalg.norm(np.cross(u, w_), axis=1), 1e-12)
            wl.append((a, b, 0.5 * cot))
        I = np.concatenate([np.r_[x[0], x[1]] for x in wl]); J = np.concatenate([np.r_[x[1], x[0]] for x in wl]); W = np.concatenate([np.r_[x[2], x[2]] for x in wl])
        Wm = sp.coo_matrix((W, (I, J)), shape=(n, n)).tocsr()
        Wm.data = np.maximum(Wm.data, 1e-4)         # keep the system positive (obtuse triangles)
    d = np.asarray(Wm.sum(1)).ravel()
    return sp.diags(d) - Wm


def solve_dirichlet(Lm, X, fixed):
    n = len(X)
    free = np.setdiff1d(np.arange(n), fixed)
    Lff = Lm[free][:, free].tocsc()
    Lfb = Lm[free][:, fixed]
    Y = X.copy()
    for k in range(X.shape[1]):
        Y[free, k] = spl.spsolve(Lff, -(Lfb @ X[fixed, k]))
    return Y


def triangulate_loop(L, target_edge=6.0):
    """closed 3D loop (n,3) -> (v, f, ring): the polygon is projected on the best-fit plane (the one in which it is simple), its boundary is densified to `target_edge` ON the straight
    loop segments (= on the neighbours' rim edges), interior points on a hexagonal grid, Delaunay, triangles outside the polygon dropped; every boundary edge must be present"""
    from scipy.spatial import Delaunay
    from shapely.geometry import Polygon, Point
    from shapely.prepared import prep
    c = L.mean(0)
    u, s, vt = np.linalg.svd(L - c)
    cands = [vt[:2]]
    a = np.array([1.0, 0, 0]); b = vt[0] - a * (vt[0] @ a); b /= np.linalg.norm(b); cands.append(np.stack([a, b]))
    for B2 in cands:
        P2 = (L - c) @ B2.T
        poly = Polygon(P2)
        if poly.is_valid:
            break
    else:
        raise RuntimeError("no plane in which the loop projects to a simple polygon")
    n0 = len(L)
    bpts, bidx = [], []
    for i in range(n0):
        a_, b_ = L[i], L[(i + 1) % n0]
        k = max(1, int(np.ceil(np.linalg.norm(b_ - a_) / target_edge)))
        for t in range(k):
            bpts.append(a_ + (b_ - a_) * (t / k))
    bpts = np.array(bpts)
    nb = len(bpts)
    B2p = (bpts - c) @ B2.T
    # interior hex grid
    minx, miny, maxx, maxy = poly.bounds
    h = target_edge
    pp = prep(poly)
    inner = []
    for r_, y in enumerate(np.arange(miny, maxy + h, h * np.sqrt(3) / 2)):
        for x in np.arange(minx + (h / 2 if r_ % 2 else 0), maxx + h, h):
            pt = Point(x, y)
            if pp.contains(pt) and poly.exterior.distance(pt) > 0.55 * h:
                inner.append((x, y))
    inner = np.array(inner).reshape(-1, 2)
    P_all = np.vstack([B2p, inner])
    tri = Delaunay(P_all).simplices
    cen = P_all[tri].mean(1)
    keep = np.array([pp.contains(Point(*q)) for q in cen])
    tri = tri[keep]
    # boundary edges present?
    es = {tuple(sorted(e)) for e in _edges(tri).tolist()}
    missing = [(i, (i + 1) % nb) for i in range(nb) if tuple(sorted((i, (i + 1) % nb))) not in es]
    if missing:
        raise RuntimeError(f"{len(missing)} boundary edges missing from the Delaunay triangulation")
    # 3D start: boundary exact, interior on the loop's best-fit plane (the minimal-surface solve moves it)
    v = np.vstack([bpts, c + np.hstack([inner, np.zeros((len(inner), 1))]) @ np.vstack([B2, vt[2]]) if len(inner) else np.zeros((0, 3))])
    return v, tri.astype(np.int64), np.arange(nb), c, (vt[0], vt[1], vt[2])


def orient_to(v, f, n_ext):
    n = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
    if (n @ n_ext).sum() < 0:
        f = f[:, ::-1].copy()
    return f


def minimal_surface(v, f, ring, iters=40):
    """Pinkall-Polthier: minimise the Dirichlet energy with the cotangent weights of the previous surface; start = the harmonic (uniform) map"""
    V = v.copy()
    fixed = ring
    V = solve_dirichlet(laplacian(V, f, "uniform"), V, fixed)
    V_harm = V.copy()
    hist = []
    for k in range(iters):
        Vn = solve_dirichlet(laplacian(V, f, "cot"), V, fixed)
        hist.append(float(np.abs(Vn - V).max()))
        V = Vn
        if hist[-1] < 1e-3:
            break
    return V, hist, V_harm


def tri_area(v, f):
    return 0.5 * np.linalg.norm(np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]]), axis=1)


def build_slab(L1, L2, n_ext_hint=(0.0, -1.0, 0.3), target_edge=6.0):
    """outer loop L1 (n,3) ordered, inner loop L2 (n,3) (rim partners) -> dict(v, f, info) of a closed thin slab"""
    v0, f0, ring, c, basis = triangulate_loop(np.asarray(L1, float), target_edge)
    n0 = len(L1)
    L1 = np.asarray(L1, float); L2 = np.asarray(L2, float)
    L1r, L2r = [], []
    for i in range(n0):
        a_, b_, pa, pb = L1[i], L1[(i + 1) % n0], L2[i], L2[(i + 1) % n0]
        k = max(1, int(np.ceil(np.linalg.norm(b_ - a_) / target_edge)))
        for t in range(k):
            L1r.append(a_ + (b_ - a_) * (t / k)); L2r.append(pa + (pb - pa) * (t / k))
    L1r, L2r = np.array(L1r), np.array(L2r)
    assert len(L1r) == len(ring)
    X = v0.copy(); X[ring] = L1r
    X, hist, X_harm = minimal_surface(X, f0, ring)
    # outward side: the web separates the pelvic hollow (above / behind) from the air (below / in front)
    n = np.cross(X[f0[:, 1]] - X[f0[:, 0]], X[f0[:, 2]] - X[f0[:, 0]]); a = tri_area(X, f0)
    nm = (n / np.maximum(np.linalg.norm(n, axis=1), 1e-12)[:, None] * a[:, None]).sum(0); nm /= np.linalg.norm(nm)
    n_ext = nm if nm @ np.asarray(n_ext_hint) > 0 else -nm
    f_out = orient_to(X, f0, n_ext)
    # inner sheet: displacement field = harmonic extension of the rim offsets
    D = np.zeros_like(X); D[ring] = L2r - L1r
    Dn = solve_dirichlet(laplacian(X, f0, "uniform"), D, ring)
    Y = X + Dn
    thick = (X - Y) @ n_ext                      # > 0 where the inner sheet lies behind the outer one
    N = len(X)
    # rim wall (quads between consecutive ring vertices), inner sheet reversed
    rim = []
    R = list(ring)
    for a_, b_ in zip(R, R[1:] + R[:1]):
        # outward orientation: the rim wall faces away from the web centre
        rim.append([a_, b_ + N, a_ + N]); rim.append([b_, b_ + N, a_])
    rim = np.array(rim)
    V = np.vstack([X, Y])
    F = np.vstack([f_out, f_out[:, ::-1] + N, rim])
    info = {"outer_vertices": int(N), "triangles": int(len(F)), "ring_vertices": int(len(ring)), "outer_area_mm2": round(float(tri_area(X, f_out).sum()), 1),
            "inner_area_mm2": round(float(tri_area(Y, f_out).sum()), 1), "thickness_mm": {"min": round(float(thick.min()), 2), "median": round(float(np.median(thick)), 2), "max": round(float(thick.max()), 2)},
            "relaxation_max_move_last_iter_mm": round(hist[-1], 4), "iterations": len(hist), "n_ext": n_ext.round(3).tolist(),
            "max_displacement_from_harmonic_mm": round(float(np.linalg.norm(X - X_harm, axis=1).max()), 2)}
    return {"v": V, "f": F, "outer": X, "inner": Y, "f_out": f_out, "ring": ring, "info": info, "n_ext": n_ext}
