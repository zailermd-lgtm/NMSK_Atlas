#!/usr/bin/env python3
"""Q384: what "distorted" means, as numbers. Pure geometry (numpy / scipy), shared by the browser verifier
(verify_pose_q384.py reads the posed vertices back from the page) and by the offline rig work.

A long structure (vessel, nerve, muscle belly) is cut into SLABS of its own REST surface: vertices binned along its
long axis, bin width `h` mm (12-25), keeping in each bin the cluster that continues the trunk (side branches are left
out). The slabs are material: the same vertices are followed into the pose. Per pose:
  bend   largest angle (deg) between consecutive centreline segments (centreline = slab centroids; where the pose has
         compressed the centreline, a segment runs on to the next centroid at least 0.35 slab widths away); bend_rest is the
         same number in the rest pose (the meshes are coarse: a rest "bend" of 10-25 degrees is sampling noise) and
         bend_add the largest increase at one node
  xsec   the circumferential stretch of the surface, its 5th percentile by area over the structure's triangles (1 =
         unchanged, towards 0 = squeezed flat, which is what a linear blend does to a tube half way through a 180 degree
         twist or bend); bending and shortening along the centreline do not enter
  dlen   centreline length change, percent of the rest length
Skin: border vertices of DIFFERENT skin pieces that coincide at rest (<= `eps` mm) are pairs; the gap of a pair in a pose
is the distance between its two posed vertices. A tear is a gap. These are measures of the DISPLAY rule (the skinning),
not of anatomy: nothing here says where a vein really lies in a flexed limb."""
from __future__ import annotations

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree


def slabs(v, f=None, h=None, cluster=True):
    """-> (list of vertex index arrays along the trunk of the structure, slab width mm, length mm).
    The meshes are heavily decimated tubes (edges up to 50 mm, several pieces), so the surface graph is no guide to the
    axis; a limb structure at rest is monotone along its own long axis, and that is what is used: vertices are binned
    along the first principal axis, and in each bin the cluster that continues the previous slab is kept."""
    v = np.asarray(v, float)
    c = v.mean(0); u, s_, vt = np.linalg.svd(v - c, full_matrices=False)
    t = (v - c) @ vt[0]
    L = float(t.max() - t.min())
    if h is None:
        h = float(np.clip(L / 40.0, 12.0, 25.0))
    nb = max(3, int(round(L / h)))
    bins = np.minimum(((t - t.min()) / L * nb).astype(int), nb - 1)
    out, prev = [], None
    for k in range(nb):
        ids = np.where(bins == k)[0]
        if len(ids) < 3:
            continue
        if not cluster:                      # a muscle belly is one mass: its heads are not side branches
            out.append(ids); continue
        pr = cKDTree(v[ids]).query_pairs(max(10.0, 0.6 * h), output_type="ndarray")
        nc, lab = connected_components(coo_matrix((np.ones(len(pr)), (pr[:, 0], pr[:, 1])), shape=(len(ids), len(ids))), directed=False)
        if nc > 1:
            cs = [v[ids[lab == q]].mean(0) for q in range(nc)]; sz = np.bincount(lab)
            q = int(np.argmax(sz)) if prev is None else int(np.argmin([np.linalg.norm(x - prev) - 0.01 * n for x, n in zip(cs, sz)]))
            ids = ids[lab == q]
            if len(ids) < 3:
                continue
        prev = v[ids].mean(0)
        out.append(ids)
    return out, h, L


def _centres(p, sl):
    return np.array([p[s].mean(0) for s in sl])


def _nbrs(c, k, hmin):
    """the nodes before and after k that are at least hmin away (a compressed stretch of centreline is all noise node to node)"""
    j = k - 1
    while j > 0 and np.linalg.norm(c[k] - c[j]) < hmin:
        j -= 1
    l = k + 1
    while l < len(c) - 1 and np.linalg.norm(c[l] - c[k]) < hmin:
        l += 1
    return j, l


def _bends(c, hmin=0.0):
    out = np.zeros(max(0, len(c) - 2))
    for k in range(1, len(c) - 1):
        j, l = _nbrs(c, k, hmin)
        a, b = c[k] - c[j], c[l] - c[k]
        out[k - 1] = np.degrees(np.arccos(np.clip(a @ b / max(np.linalg.norm(a) * np.linalg.norm(b), 1e-12), -1, 1)))
    return out


def _xsec(rest, posed, f, c0):
    """the circumferential stretch of every triangle of the surface: the unit direction in the rest triangle's plane that is
    perpendicular to the centreline (taken at the nearest slab centre) is carried into the pose by the triangle's own
    deformation, and its new length is the stretch. Bending and shortening ALONG the centreline leave it at 1; a tube
    squeezed across (a linear blend half way through a bend or twist) brings it towards 0 on two sides of the ring.
    -> (stretch per triangle, rest area per triangle)"""
    f = np.asarray(f, int)
    a, b, c = rest[f[:, 0]], rest[f[:, 1]], rest[f[:, 2]]
    e1, e2 = b - a, c - a
    n = np.cross(e1, e2); ar = np.linalg.norm(n, axis=1)
    ok = ar > 1e-6
    cs = c0.copy()                               # the direction of the centreline, from a smoothed copy: node to node the coarse centroids wander
    if len(c0) >= 5:
        k = np.array([1.0, 2, 3, 2, 1]) / 9.0
        pad = np.vstack([c0[:1]] * 2 + [c0] + [c0[-1:]] * 2)
        cs = np.stack([np.convolve(pad[:, a], k, mode="valid") for a in range(3)], 1)
    tg = np.gradient(cs, axis=0); tg /= np.maximum(np.linalg.norm(tg, axis=1, keepdims=True), 1e-9)
    _, nn = cKDTree(c0).query((a + b + c) / 3.0)
    d = np.cross(n, tg[nn]); dl = np.linalg.norm(d, axis=1); ok &= dl > 1e-6 * np.maximum(ar, 1e-9)
    d = d / np.maximum(dl, 1e-12)[:, None]
    # d = al * e1 + be * e2 in the triangle's plane
    g11, g12, g22 = (e1 * e1).sum(1), (e1 * e2).sum(1), (e2 * e2).sum(1)
    det = np.maximum(g11 * g22 - g12 * g12, 1e-18)
    r1, r2 = (d * e1).sum(1), (d * e2).sum(1)
    al, be = (g22 * r1 - g12 * r2) / det, (g11 * r2 - g12 * r1) / det
    E1, E2 = posed[f[:, 1]] - posed[f[:, 0]], posed[f[:, 2]] - posed[f[:, 0]]
    lam = np.linalg.norm(al[:, None] * E1 + be[:, None] * E2, axis=1)
    return lam[ok], 0.5 * ar[ok]


def _wpct(x, w, q):
    o = np.argsort(x); cw = np.cumsum(w[o]); return float(x[o][np.searchsorted(cw, q * cw[-1])])


def tube(rest, posed, sl, h=None, f=None):
    """the three numbers of one structure in one pose (+ where along it the worst bend is, as a fraction of its length).
    A "segment" is at least 0.35 slab widths long in the pose it is measured in."""
    c0, c1 = _centres(rest, sl), _centres(posed, sl)
    if h is None:
        h = float(np.median(np.linalg.norm(np.diff(c0, axis=0), axis=1)))
    b0, b1 = _bends(c0, 0.35 * h), _bends(c1, 0.35 * h)
    lam, ar = _xsec(rest, posed, f, c0) if f is not None and len(f) else (np.array([1.0]), np.array([1.0]))
    r = np.array([_wpct(lam, ar, 0.05)]) if len(lam) else np.array([1.0])
    L0 = np.linalg.norm(np.diff(c0, axis=0), axis=1).sum(); L1 = np.linalg.norm(np.diff(c1, axis=0), axis=1).sum()
    kb = int(np.argmax(b1)) if len(b1) else 0
    return dict(bend=float(b1.max()) if len(b1) else 0.0, bend_rest=float(b0.max()) if len(b0) else 0.0, bend_add=float((b1 - b0).max()) if len(b1) else 0.0,
                bend_at=round((kb + 1) / max(1, len(sl) - 1), 2),
                xsec=float(r.min()), dlen=float(100.0 * (L1 / max(L0, 1e-9) - 1.0)), n=len(sl))


def border_pairs(parts, eps=0.05):
    """parts = [(structure index, rest vertices)] -> (ia, va, ib, vb) arrays: vertices of different pieces that coincide at rest"""
    off = np.cumsum([0] + [len(v) for _, v in parts])
    P = np.vstack([v for _, v in parts]); own = np.repeat(np.arange(len(parts)), [len(v) for _, v in parts])
    pr = cKDTree(P).query_pairs(eps, output_type="ndarray")
    pr = pr[own[pr[:, 0]] != own[pr[:, 1]]]
    return own[pr[:, 0]], pr[:, 0] - off[own[pr[:, 0]]], own[pr[:, 1]], pr[:, 1] - off[own[pr[:, 1]]], P[pr[:, 0]]


def gaps(posed_parts, pairs):
    ia, va, ib, vb, _ = pairs
    g = np.zeros(len(ia))
    for a in np.unique(ia):
        m = ia == a
        for b in np.unique(ib[m]):
            mm = m & (ib == b)
            g[mm] = np.linalg.norm(posed_parts[a][va[mm]] - posed_parts[b][vb[mm]], axis=1)
    return g
