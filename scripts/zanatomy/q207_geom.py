"""Q207 skin geometry checks: triangle-triangle self / mutual intersections of skin slabs, slab thickness (ray along the inward normal), edge-length ratio vs the Z source."""
from __future__ import annotations

import numpy as np
from scipy.spatial import cKDTree


def _seg_tri(p0, p1, a, b, c, eps=1e-9, margin=1e-3):
    d = p1 - p0
    e1, e2 = b - a, c - a
    h = np.cross(d, e2)
    det = (e1 * h).sum(1)
    ok = np.abs(det) > eps
    f = np.where(ok, 1.0 / np.where(ok, det, 1.0), 0.0)
    s = p0 - a
    u = f * (s * h).sum(1)
    q = np.cross(s, e1)
    v = f * (d * q).sum(1)
    t = f * (e2 * q).sum(1)
    return ok & (u > margin) & (v > margin) & (u + v < 1 - margin) & (t > margin) & (t < 1 - margin)


def intersecting_pairs(V, F, owner, weld_tol=0.3, max_pairs=15_000_000):
    """V (n,3), F (m,3) of ALL meshes concatenated, owner (m,) patch index per face.  Returns the (k,2) array of intersecting face pairs.  Pairs that share a vertex index or have vertices closer than
    weld_tol (welded seams) are not counted."""
    T = V[F]
    lo, hi = T.min(1), T.max(1)
    cell = 5.0
    c0 = np.floor(lo / cell).astype(np.int64)
    c1 = np.floor(hi / cell).astype(np.int64)
    span = c1 - c0 + 1
    cnt = span.prod(1)
    fi = np.repeat(np.arange(len(F)), cnt)
    off = np.arange(cnt.sum()) - np.repeat(np.cumsum(cnt) - cnt, cnt)
    sx, sy = span[fi, 0], span[fi, 1]
    ix = off % sx
    iy = (off // sx) % sy
    iz = off // (sx * sy)
    cx = c0[fi] + np.stack([ix, iy, iz], 1)
    key = (cx[:, 0] + 100000) * 4_000_000_000 + (cx[:, 1] + 100000) * 20000 + (cx[:, 2] + 100000)
    o = np.argsort(key, kind="stable")
    key, fi = key[o], fi[o]
    starts = np.r_[0, np.flatnonzero(np.diff(key)) + 1, len(key)]
    pa, pb = [], []
    for s0, s1 in zip(starts[:-1], starts[1:]):
        n = s1 - s0
        if n < 2:
            continue
        g = fi[s0:s1]
        i, j = np.triu_indices(n, 1)
        pa.append(g[i]); pb.append(g[j])
    if not pa:
        return np.zeros((0, 2), int)
    pr = np.unique(np.stack([np.concatenate(pa), np.concatenate(pb)], 1), axis=0)
    if len(pr) > max_pairs:
        raise RuntimeError(f"too many candidate pairs {len(pr)}")
    a, b = pr[:, 0], pr[:, 1]
    m = (lo[a] <= hi[b] + 1e-9).all(1) & (lo[b] <= hi[a] + 1e-9).all(1)
    a, b = a[m], b[m]
    # vertex sharing / welded vertices
    vt = cKDTree(V)
    share = np.zeros(len(a), bool)
    Fa, Fb = F[a], F[b]
    for i in range(3):
        for j in range(3):
            share |= (V[Fa[:, i]] - V[Fb[:, j]]).__pow__(2).sum(1) < weld_tol ** 2
    a, b = a[~share], b[~share]
    hit = np.zeros(len(a), bool)
    TA, TB = T[a], T[b]
    for (X, Y) in ((TA, TB), (TB, TA)):
        for k in range(3):
            p0, p1 = X[:, k], X[:, (k + 1) % 3]
            hit |= _seg_tri(p0, p1, Y[:, 0], Y[:, 1], Y[:, 2])
    return np.stack([a[hit], b[hit]], 1)


def count_by_owner(pairs, owner, names):
    out = {}
    for x, y in pairs:
        k = tuple(sorted((names[owner[x]], names[owner[y]])))
        out[k] = out.get(k, 0) + 1
    return out


def concat(meshes):
    """{id: (v,f)} -> V, F, owner, ids"""
    ids = list(meshes)
    Vs, Fs, ow, off = [], [], [], 0
    for k, i in enumerate(ids):
        v, f = meshes[i]
        Vs.append(v)
        Fs.append(f + off)
        ow.append(np.full(len(f), k))
        off += len(v)
    return np.vstack(Vs), np.vstack(Fs), np.concatenate(ow), ids


def slab_thickness(v, f):
    """per-face thickness of a closed outward-wound slab: distance along the inward normal to the first hit on the same mesh (mm)"""
    import trimesh
    tm = trimesh.Trimesh(v, f, process=False)
    cen = tm.triangles_center
    n = tm.face_normals
    o = cen - n * 0.02
    loc, ray, tri = tm.ray.intersects_location(o, -n, multiple_hits=False)
    t = np.full(len(f), np.nan)
    t[ray] = np.linalg.norm(loc - o[ray], axis=1)
    return t


def edge_ratio(v, f, v0):
    """edge length ratio (current / Z source) over the unique edges of f"""
    e = np.unique(np.sort(np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]), axis=1), axis=0)
    l1 = np.linalg.norm(v[e[:, 0]] - v[e[:, 1]], axis=1)
    l0 = np.linalg.norm(v0[e[:, 0]] - v0[e[:, 1]], axis=1)
    ok = l0 > 0.3
    return l1[ok] / l0[ok]


def pair_depth(V, F, pairs):
    """approximate penetration depth (mm) of intersecting triangle pairs: how far the vertices of one triangle reach to the far side of the other's plane (min over the two directions, both ways)"""
    T = V[F]
    a, b = pairs[:, 0], pairs[:, 1]
    out = np.zeros(len(pairs))
    for (x, y) in ((a, b), (b, a)):
        P0, P1, P2 = T[y, 0], T[y, 1], T[y, 2]
        n = np.cross(P1 - P0, P2 - P0)
        n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
        d = np.einsum("kij,kj->ki", T[x] - P0[:, None, :], n)
        out = np.maximum(out, np.minimum(np.abs(np.where(d > 0, d, 0)).max(1), np.abs(np.where(d < 0, d, 0)).max(1)))
    return out


def new_pairs(pairs0, pairs1, owner0=None):
    """pairs that exist after but not before (face index pairs; the face numbering of the concatenation is the same)"""
    s0 = {(int(x), int(y)) for x, y in np.sort(pairs0, axis=1)}
    keep = [k for k, (x, y) in enumerate(np.sort(pairs1, axis=1)) if (int(x), int(y)) not in s0]
    return pairs1[keep]
