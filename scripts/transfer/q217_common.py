"""Q217 shared: page loaders for the elbow / forearm work (own male bundle = Bundle, Z male page = Q198 loader), muscle sets, window, overlap measures."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

# left forearm muscles (Z-Anatomy / own ids); the arm muscles are fixed neighbours
FOREARM = ["abductor_pollicis_longus", "anconeus", "brachioradialis", "extensor_carpi_radialis_brevis", "extensor_carpi_radialis_longus", "extensor_carpi_ulnaris", "extensor_digiti_minimi",
           "extensor_digitorum", "extensor_indicis", "extensor_pollicis_brevis", "zan_extensor_pollicis_longus", "flexor_carpi_radialis", "flexor_carpi_ulnaris", "flexor_digitorum_profundus",
           "flexor_digitorum_superficialis", "zan_humero_ulnar_head_of_flexor_digitorum_superficialis", "flexor_pollicis_longus", "pronator_quadratus", "pronator_teres", "supinator",
           "zan_palmaris_longus_muscle"]
ARM = ["biceps_brachii", "brachialis", "coracobrachialis", "zan_lateral_head_of_triceps_brachii", "zan_long_head_of_triceps_brachii", "zan_medial_head_of_triceps_brachii", "triceps_brachii"]
BONES_L = ["humerus_l", "radius_l", "ulna_l"]
Y_WIN = (100.0, 305.0)             # working window along atlas y (wrist .. elbow); outside it nothing moves


def side_ids(names, side="l"):
    return [f"{n}_{side}" for n in names]


def mesh_volume(v, f):
    t = np.asarray(v)[f]
    return abs(float(np.einsum("ij,ij->", t[:, 0], np.cross(t[:, 1], t[:, 2])) / 6.0)) / 1000.0


def zan_left(key="zan_m"):
    """Q198 loader dict {id: dict(v, f, sys)} of the structures of the page"""
    from scripts.zanatomy import q217_paths  # noqa: F401
    from scripts.zanatomy import q198_load as L
    S = L.load(key)
    return {s["id"]: s for s in S}


class SkinGuard:
    """signed distance of points to the page's skin (mm, negative = inside): sign from the Q198 voxel envelope (3 mm, closed by 2), magnitude from a KD-tree of 1 mm surface samples of the skin patches / mesh near the zone"""

    def __init__(self, skin_structs, zone_lo=(-330.0, 40.0, -160.0), zone_hi=(-60.0, 360.0, 200.0), close=2):
        from scipy.spatial import cKDTree
        from scripts.zanatomy.q198_core import SkinField, surf_points
        self.field = SkinField(skin_structs, 3.0, close=close)
        pts = []
        lo, hi = np.asarray(zone_lo), np.asarray(zone_hi)
        for s in skin_structs:
            v = s["v"]
            if (v.max(0) < lo).any() or (v.min(0) > hi).any():
                continue
            P = surf_points(np.asarray(v, float), np.asarray(s["f"], np.int64), 1.0, cap=200000)
            pts.append(P[((P >= lo) & (P <= hi)).all(1)])
        self.tree = cKDTree(np.concatenate(pts))

    def signed(self, p):
        d = self.tree.query(p)[0]
        sd = self.field.signed(p)
        return np.where(sd <= 0, -d, d).astype(np.float32)


def overlap_voxels(meshes, lo=(-280.0, 94.0, -90.0), hi=(-130.0, 308.0, 150.0), h=0.5, ids=None):
    """exact-solid overlap of closed meshes on a 0.5 mm grid: {id: dict(vol_cm3, shared_pct, with={other id: shared cm3})}, total shared volume (cm3).  meshes = {id: (v, f)}"""
    from scripts.transfer.q216_common import VoxGrid
    g = VoxGrid(lo, hi, h)
    ids = list(meshes) if ids is None else ids
    cnt = np.zeros(g.shape, np.uint8)
    sol = {}
    for i in ids:
        v, f = meshes[i]
        v = np.asarray(v, float)
        a = np.maximum(g.idx(v.min(0) - 2.0), 0)
        b = np.minimum(g.idx(v.max(0) + 2.0) + 1, np.asarray(g.shape))
        if (b <= a).any():
            continue
        sub = VoxGrid(g.pos(a), g.pos(b - 1), h)
        s = sub.solid(v, np.asarray(f, np.int64))
        sl = tuple(slice(int(a[k]), int(a[k]) + s.shape[k]) for k in range(3))
        sl = tuple(slice(sl[k].start, min(sl[k].stop, g.shape[k])) for k in range(3))
        s = s[tuple(slice(0, sl[k].stop - sl[k].start) for k in range(3))]
        sol[i] = (sl, s)
        cnt[sl] += s.astype(np.uint8)
    rows = {}
    for i, (sl, s) in sol.items():
        n = int(s.sum())
        c = cnt[sl]
        sh = int((s & (c > 1)).sum())
        w = {}
        for j, (sl2, s2) in sol.items():
            if j == i:
                continue
            lo2 = [max(sl[k].start, sl2[k].start) for k in range(3)]
            hi2 = [min(sl[k].stop, sl2[k].stop) for k in range(3)]
            if any(hi2[k] <= lo2[k] for k in range(3)):
                continue
            a_ = s[tuple(slice(lo2[k] - sl[k].start, hi2[k] - sl[k].start) for k in range(3))]
            b_ = s2[tuple(slice(lo2[k] - sl2[k].start, hi2[k] - sl2[k].start) for k in range(3))]
            x = int((a_ & b_).sum())
            if x:
                w[j] = round(x * h ** 3 / 1000.0, 2)
        rows[i] = dict(vol_cm3=round(n * h ** 3 / 1000.0, 2), shared_pct=round(100.0 * sh / max(n, 1), 1), with_=w)
    return rows, round(float((cnt > 1).sum()) * h ** 3 / 1000.0, 2)


def min_dist(a, b, spacing=1.0):
    """minimum surface-sample distance between two meshes (v, f)"""
    from scipy.spatial import cKDTree
    from scripts.transfer.q217_slide import surface_samples
    pa, pb = surface_samples(*a, spacing), surface_samples(*b, spacing)
    return float(cKDTree(pb).query(pa)[0].min())


def adjacency_pairs(base, names, near_mm=2.0, spacing=1.0):
    """pairs of structures of `names` (dict id -> (v, f), the unfitted Z base) whose surfaces are <= near_mm apart"""
    from scipy.spatial import cKDTree
    from scripts.transfer.q217_slide import surface_samples
    P = {i: surface_samples(*base[i], spacing) for i in names}
    T = {i: cKDTree(p) for i, p in P.items()}
    out = []
    ids = list(names)
    for a in range(len(ids)):
        for b in range(a + 1, len(ids)):
            i, j = ids[a], ids[b]
            if (P[i].max(0) < P[j].min(0) - near_mm).any() or (P[i].min(0) > P[j].max(0) + near_mm).any():
                continue
            d = T[j].query(P[i])[0].min()
            if d <= near_mm:
                out.append((i, j, float(d)))
    return out


class BoneVox:
    """his bones as filled voxel solids (0.5 mm, open CT shells closed) with the depth (mm) of a point inside them (1 mm lattice)"""

    def __init__(self, bones, lo=(-285.0, 90.0, -95.0), hi=(-125.0, 350.0, 150.0)):
        from scipy import ndimage as ndi
        from scripts.transfer import q217_domain as D
        from scripts.transfer.q216_common import VoxGrid
        g = VoxGrid(lo, hi, 0.5)
        occ = np.zeros(g.shape, bool)
        for k, (v, f) in bones.items():
            v = np.asarray(v, float)
            if (v.max(0) < np.asarray(lo)).any() or (v.min(0) > np.asarray(hi)).any():
                continue
            occ |= D.bone_solid(g, v, np.asarray(f, np.int64))
        m = occ[::2, ::2, ::2]
        self.lo, self.h = g.lo, 1.0
        self.depth_vol = ndi.distance_transform_edt(m, sampling=1.0).astype(np.float32)
        self.shape = m.shape

    def depth(self, p):
        i = np.floor((np.asarray(p) - self.lo) / self.h + 0.5).astype(np.int64)
        ok = ((i >= 0) & (i < np.asarray(self.shape))).all(1)
        out = np.zeros(len(p), np.float32)
        out[ok] = self.depth_vol[i[ok, 0], i[ok, 1], i[ok, 2]]
        return out


def muscle_metrics(meshes, fixed, skin, bonevox, ids=None):
    """per muscle: voxel volume, shared %, with-others, % vertices outside the skin (window y 100-320), skin depth min, % vertices > 1 mm inside a bone, deepest, mesh volume"""
    ids = list(meshes) if ids is None else ids
    M = dict(meshes)
    M.update(fixed)
    rows, tot = overlap_voxels(M, ids=list(M))
    out = {}
    for i in ids:
        v, f = meshes[i]
        win = (v[:, 1] > 100) & (v[:, 1] < 320)
        sg = skin.signed(v[win]) if win.any() else np.zeros(1)
        bd = bonevox.depth(v)
        out[i] = dict(vol_cm3=rows[i]["vol_cm3"], shared_pct=rows[i]["shared_pct"], with_=rows[i]["with_"], outside_skin_pct=round(100.0 * float((sg > 0).mean()), 2),
                      skin_depth_min_mm=round(float(-sg.max()), 2), in_bone_pct=round(100.0 * float((bd > 1.0).mean()), 2), bone_depth_max_mm=round(float(bd.max()), 1),
                      mesh_cm3=round(mesh_volume(v, f), 1))
    return out, tot
