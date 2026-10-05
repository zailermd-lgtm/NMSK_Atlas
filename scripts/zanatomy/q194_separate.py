"""Q194: bounded per-vertex separation of overlapping neighbour muscles along the contact normal.

Q190 resolved muscle-muscle overlap with a push-apart that collapsed the muscles (volume lost, folds); the neighbour overlap then rose 8.0 -> 9.7 % of the vertices.
Here each round: for every pair of (closed) neighbour meshes A, B, a vertex of A that lies > 0.3 mm inside B is moved along B's outward surface normal by HALF its
depth (+ 0.4 mm margin, the other half is B's own move), capped at MAX_MOVE_MM; every mesh's displacement is smoothed over its own surface (so no spikes) and the
result per mesh is accepted only if (i) volume stays in 0.65-1.5 x the Z source, (ii) the share of folded edges does not grow, (iii) it stays out of the displayed
bones and inside her skin where the caller says so (`keep`), else that mesh keeps its previous round.  Nothing moves that does not overlap.
"""
from __future__ import annotations

import numpy as np
from scipy.spatial import cKDTree

from scripts.zanatomy import q190_refine as Q
from scripts.zanatomy import q191_hand as H

MAX_MOVE_MM = 4.0
MARGIN_MM = 0.4
MIN_DEPTH_MM = 0.3


class Skel:
    """closed mesh: depth(P) > 0 for points inside (ray parity), depth = distance to the surface; dirn = outward face normal of the nearest triangle.
    (The Q191 `Inside` sampled-normal test misreads meshes with a few flipped / folded triangles; the ray parity does not.)"""

    def __init__(self, v, f, spacing=0.8):
        import trimesh
        self.m = trimesh.Trimesh(v, f, process=False)
        if self.m.volume < 0:
            self.m.invert()
        self.lo, self.hi = v.min(0), v.max(0)

    def depth(self, P):
        out = np.full(len(P), -1e9)
        sel = np.flatnonzero(np.all((P >= self.lo - 1.0) & (P <= self.hi + 1.0), axis=1))
        if not len(sel):
            return out
        try:
            c = self.m.contains(P[sel])
        except Exception:
            return out
        out[sel] = -1.0
        ins = sel[c]
        if len(ins):
            from trimesh.proximity import closest_point
            _, d, _ = closest_point(self.m, P[ins])
            out[ins] = d
        return out

    def dirn(self, P):
        from trimesh.proximity import closest_point
        _, _, tri = closest_point(self.m, P)
        return self.m.face_normals[tri]


def overlap_pct(meshes: dict, ids=None, nmax=3000, seed=0):
    """{id: % of its vertices (sampled) lying > MIN_DEPTH_MM inside another mesh of the set}"""
    rng = np.random.default_rng(seed)
    sk = {i: Skel(v, f) for i, (v, f) in meshes.items()}
    out = {}
    for i, (v, f) in meshes.items():
        if ids is not None and i not in ids:
            continue
        P = v[rng.choice(len(v), min(len(v), nmax), replace=False)]
        inside = np.zeros(len(P), bool)
        for j, s in sk.items():
            if j != i:
                inside |= s.depth(P) > MIN_DEPTH_MM
        out[i] = 100.0 * float(inside.mean())
    return out


def separate(meshes: dict, raw: dict, movable: set, rounds=3, max_move=MAX_MOVE_MM, smooth=8, keep=None, log=print):
    """meshes: {id: (v, f)} (all closed neighbour muscles in the area); movable: ids that may move.  keep(id, v) -> bool: extra acceptance test.  Returns ({id: v_new}, report)"""
    cur = {i: v.copy() for i, (v, f) in meshes.items()}
    rep = {}
    for rd in range(rounds):
        sk = {i: Skel(cur[i], meshes[i][1]) for i in meshes}
        new = {}
        for i in movable:
            v, f = cur[i], meshes[i][1]
            D = np.zeros_like(v)
            hit = np.zeros(len(v), bool)
            for j, s in sk.items():
                if j == i:
                    continue
                d = s.depth(v)
                m = d > MIN_DEPTH_MM
                if m.any():
                    n = s.dirn(v[m])
                    step = np.minimum(0.5 * (d[m] + MARGIN_MM), max_move)
                    cand = n * step[:, None]
                    idx = np.flatnonzero(m)
                    bigger = np.linalg.norm(cand, axis=1) > np.linalg.norm(D[idx], axis=1)
                    D[idx[bigger]] = cand[bigger]
                    hit[idx] = True
            if not hit.any():
                continue
            D = Q._smooth_push(f, D, smooth)
            cap = np.minimum(1.0, max_move / np.maximum(np.linalg.norm(D, axis=1), 1e-9))
            D *= cap[:, None]
            v2 = v + D
            vr = H.vol_ratio(v2, raw[i], f)
            fold0, fold1 = H.fold_stats(v, raw[i], f), H.fold_stats(v2, raw[i], f)
            ok = (vr is None or 0.65 <= vr <= 1.5) and fold1 <= fold0 + 0.003 and (keep is None or keep(i, v2))
            if ok:
                new[i] = v2
        for i, v2 in new.items():
            cur[i] = v2
        log(f"    separation round {rd}: {len(new)} of {len(movable)} meshes moved")
    for i in movable:
        d = np.linalg.norm(cur[i] - meshes[i][0], axis=1)
        if d.max() > 1e-6:
            rep[i] = {"max_move_mm": round(float(d.max()), 2), "mean_move_mm": round(float(d.mean()), 2)}
    return cur, rep
