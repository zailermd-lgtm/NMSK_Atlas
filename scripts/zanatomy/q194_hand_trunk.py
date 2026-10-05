"""Q194: leftovers of Q190 (trunk) and Q191 (right hand): shape relaxation of the still-distorted structures, skin patches onto her CT outline, bounded
muscle-muscle separation (scripts/zanatomy/q194_separate.py).  Real sources only: the reference is her CT skin / bones / her own labels, the shape is the Z source."""
from __future__ import annotations

import re

import numpy as np
from scipy.spatial import cKDTree

from scripts.zanatomy import q190_metrics as Mx
from scripts.zanatomy import q190_refine as Q
from scripts.zanatomy import q191_hand as H

RELAX_SIGMAS = (8.0, 14.0, 24.0)


def stretch_pct(v, r, f):
    st = Mx.stretch_stats(v, r, f)
    return None if st is None else 100.0 * (st["area_frac_gt1.5"] + st["area_frac_lt0.67"])


def relax_one(d, sigmas=RELAX_SIGMAS, max_move=10.0, accept=None):
    """smallest low-pass sigma (Q190 shape relaxation) that brings the area-stretch score under max(25 %, half of before); returns (v_new, info) or None"""
    v0, r, f = d["v"].astype(float), d["r"].astype(float), d["f"]
    s0 = stretch_pct(v0, r, f)
    if s0 is None or s0 < 25.0:
        return None
    best = None
    for sg in sigmas:
        v1 = Q.smooth_displacement({"r": r, "f": f}, v0, sg)
        mv = np.linalg.norm(v1 - v0, axis=1)
        if mv.max() > max_move:
            v1 = v0 + (v1 - v0) * np.minimum(1.0, max_move / np.maximum(mv, 1e-9))[:, None]
        s1 = stretch_pct(v1, r, f)
        if d["cat"] == "muscle" and Q._closed(f):
            v1, _ = Q.volume_guard(v1, r, f)
        if accept is not None and not accept(d["id"], v0, v1):
            continue
        if H.fold_stats(v1, r, f) > H.fold_stats(v0, r, f) + 0.003:
            continue
        info = {"sigma_mm": sg, "stretch_before_pct": round(s0, 1), "stretch_after_pct": round(s1, 1), "max_move_mm": round(float(np.linalg.norm(v1 - v0, axis=1).max()), 2),
                "mean_move_mm": round(float(np.linalg.norm(v1 - v0, axis=1).mean()), 2)}
        if best is None or s1 < best[1]["stretch_after_pct"]:
            best = (v1, info)
        if s1 <= max(25.0, 0.5 * s0):
            break
    if best is None or best[1]["stretch_after_pct"] >= 0.8 * s0:
        return None
    return best


# ------------------------------------------------------------------------------------------------ skin patches onto her CT outline
def skin_dist(skin_pts_tree, v):
    return skin_pts_tree.query(v)[0]


def patch_membrane(by: dict, group: list[str], skin, skin_tree, inset=0.8, max_move=45.0, iters=400):
    """Z skin patches of `group` that lie far off her CT outline (Q190: gluteal fold, anal region 17-42 mm): the patches tile one surface, so their SEAM vertices (shared with
    patches outside the group) keep the neighbours' positions (which are on her skin), the interior vertices become the harmonic (membrane) interpolation of the seam, and then
    every vertex goes onto her CT skin, `inset` mm inside it.  Returns {id: v_new}"""
    from trimesh.proximity import closest_point
    other = [i for i, d in by.items() if d["cat"] == "skin" and i not in group]
    ro = np.vstack([by[i]["r"] for i in other])
    keyo = {tuple(x) for x in np.round(ro, 2)}
    # unique vertex ids over the group
    allr = np.vstack([by[i]["r"] for i in group]).astype(float)
    u, inv = np.unique(np.round(allr, 2), axis=0, return_inverse=True)
    inv = inv.reshape(-1)
    n = len(u)
    off = np.cumsum([0] + [len(by[i]["r"]) for i in group])
    pos = np.zeros((n, 3)); cnt = np.zeros(n)
    for k, i in enumerate(group):
        np.add.at(pos, inv[off[k]:off[k + 1]], by[i]["v"]); np.add.at(cnt, inv[off[k]:off[k + 1]], 1)
    pos /= cnt[:, None]
    fixed = np.array([tuple(x) in keyo for x in u])
    if fixed.all() or not fixed.any():
        return None
    # fixed positions = the neighbour patch's current vertex at that raw position
    nb = {}
    for i in other:
        for x, p in zip(np.round(by[i]["r"], 2), by[i]["v"]):
            nb.setdefault(tuple(x), p)
    for j in np.flatnonzero(fixed):
        pos[j] = nb[tuple(u[j])]
    e = []
    for k, i in enumerate(group):
        f = inv[off[k]:off[k + 1]][by[i]["f"]]
        e += [f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]
    e = np.unique(np.sort(np.vstack(e), 1), axis=0)
    nbr = [[] for _ in range(n)]
    for a, b in e:
        nbr[a].append(b); nbr[b].append(a)
    x = pos.copy()
    free = np.flatnonzero(~fixed)
    for _ in range(iters):                                  # Gauss-Seidel membrane
        for j in free:
            x[j] = x[nbr[j]].mean(0)
    cp, _, tri = closest_point(skin, x)
    tgt = cp - inset * skin.face_normals[tri]
    d = tgt - x
    mv = np.linalg.norm(d, axis=1)
    sc = np.minimum(1.0, max_move / np.maximum(mv, 1e-9))
    x = np.where(fixed[:, None], x, x + d * sc[:, None])
    return {i: x[inv[off[k]:off[k + 1]]] for k, i in enumerate(group)}


# ------------------------------------------------------------------------------------------------ acceptance gates
class Gates:
    """containment tests shared by every Q194 move: inside her CT skin, out of the displayed bones (ray parity), skin patches stay on her outline"""

    def __init__(self, by: dict, skin, skin_tree):
        from scripts.zanatomy.q194_separate import Skel
        self.by, self.skin, self.tree = by, skin, skin_tree
        self.bones = {i: Skel(d["v"].astype(float), d["f"]) for i, d in by.items() if d["cat"] == "bone" and Q._closed(d["f"])}
        self._cache = {}

    def outside_skin_pct(self, v):
        return 100.0 * float((~self.skin.contains(v)).mean())

    def inside_bone_pct(self, v, tol=1.5):
        lo, hi = v.min(0), v.max(0)
        worst = np.zeros(len(v), bool)
        for i, s in self.bones.items():
            if np.any(s.hi < lo - 2) or np.any(s.lo > hi + 2):
                continue
            worst |= s.depth(v) > tol
        return 100.0 * float(worst.mean())

    def accept(self, i, v0, v1, skin_tol=0.5, bone_tol=1.0, gap_tol=1.5):
        """a move v0 -> v1 of structure i is acceptable if it does not worsen containment (skin / bones) and, for skin patches, the gap to her skin"""
        d = self.by[i]
        if self.outside_skin_pct(v1) > self.outside_skin_pct(v0) + skin_tol:
            return False
        if d["cat"] == "skin":
            return float(np.median(self.tree.query(v1)[0])) <= float(np.median(self.tree.query(v0)[0])) + gap_tol
        if d["cat"] != "bone" and self.inside_bone_pct(v1) > self.inside_bone_pct(v0) + bone_tol:
            return False
        return True
