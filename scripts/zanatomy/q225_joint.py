"""Q225 joint measures: signed-distance fields of bone solids (0.5 mm voxel solid of the Q223 / Q217 code, `q217_domain.bone_solid`), exact penetration depth of vertices (Q223 `pairs_exact` rule),
joint-space (surface-to-surface clearance of surface samples), the patch statistics used as 'joint space' of a pair."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.transfer import q217_domain as D  # noqa: E402
from scripts.transfer.q216_common import VoxGrid  # noqa: E402

H = 0.5


class Sdf:
    """signed distance (mm; > 0 outside, < 0 inside) of the closed solid of (v, f) on a 0.5 mm grid around the bbox + pad (outside the box: distance to the box)"""

    def __init__(self, v, f, pad=14.0, h=H):
        v = np.asarray(v, float)
        self.g = VoxGrid(v.min(0) - pad, v.max(0) + pad, h)
        occ = D.bone_solid(self.g, v, np.asarray(f, np.int64))
        self.occ = occ
        din = ndi.distance_transform_edt(occ, sampling=h)
        dout = ndi.distance_transform_edt(~occ, sampling=h)
        self.sd = (dout - din).astype(np.float32)
        self.h = h

    def __call__(self, p):
        p = np.asarray(p, float)
        c = (p - self.g.lo) / self.h
        out = ndi.map_coordinates(self.sd, c.T, order=1, mode="nearest")
        # outside the grid: add the distance to the box so the field keeps growing
        lo, hi = np.zeros(3), np.asarray(self.sd.shape, float) - 1
        ex = np.maximum(np.maximum(lo - c, c - hi), 0.0)
        return out + np.linalg.norm(ex, axis=1) * self.h


def surf_samples(v, f, spacing=1.2, cap=12000):
    """points on the surface (vertices + barycentric triangle samples) with the vertex index triple + weights so they can follow a vertex displacement"""
    v = np.asarray(v, float)
    f = np.asarray(f, np.int64)
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    area = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
    n = np.maximum(1, np.round(area / (spacing * spacing)).astype(int))
    rng = np.random.default_rng(0)
    tri = np.repeat(np.arange(len(f)), n)
    r1, r2 = rng.random(len(tri)), rng.random(len(tri))
    flip = r1 + r2 > 1
    r1[flip], r2[flip] = 1 - r1[flip], 1 - r2[flip]
    w = np.stack([1 - r1 - r2, r1, r2], 1)
    if len(tri) > cap:
        k = rng.choice(len(tri), cap, replace=False)
        tri, w = tri[k], w[k]
    idx = f[tri]
    return idx, w


def sample_pts(v, idx, w):
    return (np.asarray(v, float)[idx] * w[:, :, None]).sum(1)


def vertex_depth(sdf, v):
    """Q223 rule: depth (mm, >= 0) of the vertices inside the solid of the other bone"""
    return np.maximum(-sdf(v), 0.0)


def pair_report(va, fa, vb, fb, sdf_a=None, sdf_b=None, patch_mm=6.0):
    """exact penetration of the surfaces into each other (vertex rule of Q223) + joint-space of the pair (surface-sample clearance): min, 5th percentile of the patch (samples of either bone within `patch_mm`
    of the other), median of the patch."""
    sdf_a = sdf_a or Sdf(va, fa)
    sdf_b = sdf_b or Sdf(vb, fb)
    ia, wa = surf_samples(va, fa)
    ib, wb = surf_samples(vb, fb)
    pa, pb = sample_pts(va, ia, wa), sample_pts(vb, ib, wb)
    ca, cb = sdf_b(pa), sdf_a(pb)            # clearance of a's samples to b and vice versa
    da, db = np.maximum(-sdf_b(va), 0), np.maximum(-sdf_a(vb), 0)
    allc = np.concatenate([ca, cb])
    patch = allc[allc < patch_mm]
    out = dict(
        a_in_b=dict(max_mm=round(float(da.max()), 2), pct_over_1mm=round(100 * float((da > 1).mean()), 1)),
        b_in_a=dict(max_mm=round(float(db.max()), 2), pct_over_1mm=round(100 * float((db > 1).mean()), 1)),
        min_clearance_mm=round(float(allc.min()), 2),                       # < 0: interpenetration (depth)
        patch_p05_mm=round(float(np.percentile(patch, 5)), 2) if len(patch) else None,
        patch_median_mm=round(float(np.median(patch)), 2) if len(patch) else None,
        patch_n=int(len(patch)))
    out["max_depth_mm"] = max(out["a_in_b"]["max_mm"], out["b_in_a"]["max_mm"])
    return out
