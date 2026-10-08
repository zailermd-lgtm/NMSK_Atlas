"""Q207: overlay patches (nail plate, perionyx) re-seated on the dorsal digit sheet: every vertex keeps its source place relative to the sheet (face, barycentric, offset along the face normal) and is
re-computed from the CURRENT sheet.  Used where the per-patch fits of an earlier task had collapsed the overlay (male right nail plates: 9 % of the edges < 0.05 mm, edge ratio p5 0.0)."""
from __future__ import annotations

import numpy as np
import trimesh


def transfer(raw_over_v, raw_base_v, base_f, cur_base_v, snap=0.7):
    tm = trimesh.Trimesh(raw_base_v, base_f, process=False)
    cl, dist, tid = trimesh.proximity.closest_point(tm, raw_over_v)
    bary = trimesh.triangles.points_to_barycentric(tm.triangles[tid], cl)
    bary = np.clip(bary, 0, 1)
    bary /= bary.sum(1, keepdims=True)
    # a vertex that lies (almost) on a vertex of the sheet sits exactly on that vertex again (the border pairs of the seam metric stay vertex to vertex)
    hot = bary.max(1) > snap
    oh = np.zeros_like(bary)
    oh[np.arange(len(bary)), bary.argmax(1)] = 1.0
    bary = np.where(hot[:, None], oh, bary)
    off = ((raw_over_v - cl) * tm.face_normals[tid]).sum(1)
    cur = trimesh.Trimesh(cur_base_v, base_f, process=False)
    P = (cur.triangles[tid] * bary[:, :, None]).sum(1) + off[:, None] * cur.face_normals[tid]
    return P


def degenerate_share(v, f, v_src, tol=0.05):
    e = np.unique(np.sort(np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]), axis=1), axis=0)
    l1 = np.linalg.norm(v[e[:, 0]] - v[e[:, 1]], axis=1)
    l0 = np.linalg.norm(v_src[e[:, 0]] - v_src[e[:, 1]], axis=1)
    return float(((l1 < tol) & (l0 > 0.3)).mean())
