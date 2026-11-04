"""Q240: calibre (mean tube diameter) of a vessel / nerve mesh, estimated from the geometry itself.

Method (deterministic, numpy only): the vertices are ordered along the principal axis of the structure and cut into slabs about one tube diameter thick; each slab gives a
centre (mean of its vertices) and, relative to the LOCAL axis (from the neighbouring slab centres, so a curved vessel is handled), the perpendicular distances of its vertices;
diameter = 2 x the median over slabs of the per-slab median distance (a tube's ring of vertices lies at the radius; a branch stub or a cap vertex is an outlier the medians
ignore). Second estimate (cross-check, reported): lateral area / (pi x centreline length) = diameter of the equivalent cylinder. The primary value is the slab estimate when the
two agree within a factor 2, else the smaller one (a mesh whose area includes branches or thick caps overestimates by area; one whose slabs mix a branch underestimates by slab,
but a branch only ever adds to the area estimate, so the smaller of two disagreeing estimates is the safer bound for the trunk).
"""
from __future__ import annotations

import numpy as np


def _clean(V: np.ndarray, F: np.ndarray):
    used = np.unique(F.reshape(-1))
    remap = -np.ones(len(V), np.int64)
    remap[used] = np.arange(len(used))
    return V[used], remap[F]


def tube_diameter(V: np.ndarray, F: np.ndarray) -> dict:
    """V (n,3) mm, F (m,3) -> {diameter_mm, length_mm, area_diameter_mm, slabs}"""
    V, F = _clean(np.asarray(V, np.float64), np.asarray(F, np.int64))
    if len(V) < 6 or len(F) < 4:
        return {"diameter_mm": None, "length_mm": 0.0, "area_diameter_mm": None, "slabs": 0}
    c0 = V.mean(0)
    u, s, vt = np.linalg.svd(V - c0, full_matrices=False)
    e = vt[0]
    t = (V - c0) @ e
    L0 = float(t.max() - t.min())
    A = V[F]
    area = float(0.5 * np.linalg.norm(np.cross(A[:, 1] - A[:, 0], A[:, 2] - A[:, 0]), axis=1).sum())
    d_guess = max(0.5, area / (np.pi * max(L0, 1e-6)))               # equivalent-cylinder diameter on the straight length
    nb = int(min(160, max(3, round(L0 / max(1.0 * d_guess, 2.0)))))
    edges = np.linspace(t.min(), t.max() + 1e-9, nb + 1)
    which = np.clip(np.searchsorted(edges, t, side="right") - 1, 0, nb - 1)
    cen, ok = np.zeros((nb, 3)), np.zeros(nb, bool)
    for k in range(nb):
        m = which == k
        if m.sum() >= 3:
            cen[k] = V[m].mean(0); ok[k] = True
    idx = np.nonzero(ok)[0]
    if len(idx) < 2:
        return {"diameter_mm": None, "length_mm": L0, "area_diameter_mm": d_guess, "slabs": int(len(idx))}
    C = cen[idx]
    clen = float(np.linalg.norm(np.diff(C, axis=0), axis=1).sum()) + (edges[1] - edges[0])
    meds = []
    for a, k in enumerate(idx):
        lo, hi = max(0, a - 1), min(len(idx) - 1, a + 1)
        ax = C[hi] - C[lo]
        n = np.linalg.norm(ax)
        ax = ax / n if n > 1e-9 else e
        d = V[which == k] - cen[k]
        perp = d - np.outer(d @ ax, ax)
        meds.append(float(np.median(np.linalg.norm(perp, axis=1))))
    d_slab = 2.0 * float(np.median(meds))
    d_area = area / (np.pi * max(clen, 1e-6))
    d = d_slab if d_slab <= 2 * d_area and d_area <= 2 * d_slab else min(d_slab, d_area)
    return {"diameter_mm": round(d, 2), "length_mm": round(clen, 1), "area_diameter_mm": round(d_area, 2), "slab_diameter_mm": round(d_slab, 2), "slabs": int(len(idx))}
