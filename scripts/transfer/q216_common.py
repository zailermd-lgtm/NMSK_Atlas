"""Q216 shared helpers (own female page): exact voxel solids of closed muscle meshes, nerve / vessel exclusion corridors, channel carving with a retract-to-the-nearest-surface rule, marching-cubes
re-meshing to the page's triangle budget, the audit-equivalent end / flat-cap / island measures, and the page context (bones, skin, muscles) of the Q215 bundle."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import trimesh
from scipy import ndimage as ndi
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "clinical"))

SRC_BUNDLE = REPO / "build/viewer_f_hr_q215"
SRC_PAGE = REPO / "build/q215/viewer_f_hr"
OUT_BUNDLE = REPO / "build/viewer_f_hr_q216"
OUT_PAGE = REPO / "build/q216/viewer_f_hr"
SUBJECT = "xfer_vhm2vhf_sep_q216"          # the 27 Q215 muscles keep the Source class (TRANSFERRED); the subject key marks the Q216 clean-up (template SUBJECT_LABELS)
TRACED = ("sciatic_n", "femoral_a_r", "femoral_v_r", "femoral_n", "popliteal_a_r", "popliteal_v_r", "tibial_n")
H = 0.5                                     # mm, voxel size of the carve / re-mesh grid


# ------------------------------------------------------------------------------------------ voxel solids
class VoxGrid:
    """isotropic grid [lo, lo + shape * h); voxel (i, j, k) has its centre at lo + (i, j, k) * h"""

    def __init__(self, lo, hi, h=H):
        self.h = float(h)
        self.lo = np.asarray(lo, float)
        self.shape = tuple(np.ceil((np.asarray(hi, float) - self.lo) / self.h).astype(int) + 1)

    def idx(self, p):
        return np.floor((np.asarray(p) - self.lo) / self.h + 0.5).astype(np.int64)

    def pos(self, ijk):
        return self.lo + np.asarray(ijk, float) * self.h

    def inb(self, i):
        return ((i >= 0) & (i < np.asarray(self.shape))).all(1)

    def shell(self, v, f):
        from scripts.zanatomy.q198_core import surf_points
        occ = np.zeros(self.shape, bool)
        if not len(f):
            return occ
        p = surf_points(np.asarray(v, float), np.asarray(f, np.int64), self.h * 0.35, cap=8000000)
        i = self.idx(p)
        i = i[self.inb(i)]
        occ[i[:, 0], i[:, 1], i[:, 2]] = True
        return occ

    def solid(self, v, f):
        """exact solid of a closed (or nearly closed) mesh: the shell raster is filled; only the 1.5 mm band around the surface is decided by ray parity (trimesh.contains), the deep interior is the fill"""
        s = self.shell(v, f)
        d = ndi.binary_dilation(s, iterations=1)
        filled = ndi.binary_fill_holes(np.pad(d, 1))[1:-1, 1:-1, 1:-1]
        core = ndi.binary_erosion(filled, iterations=4)
        outside = ~ndi.binary_dilation(filled, iterations=1)
        band = ~core & ~outside
        out = core.copy()
        ij = np.argwhere(band)
        if len(ij):
            tm = trimesh.Trimesh(np.asarray(v, float), np.asarray(f, np.int64), process=False)
            out[tuple(ij.T)] = tm.contains(self.pos(ij))
        return out


def mask_volume_cm3(mask, h=H):
    return float(mask.sum()) * h ** 3 / 1000.0


def largest_components(mask, keep_frac=0.0):
    """-> (mask of the largest 26-connected component, dropped volume fraction)"""
    lab, n = ndi.label(mask, structure=np.ones((3, 3, 3)))
    if n <= 1:
        return mask, 0.0
    cnt = np.bincount(lab.ravel())[1:]
    k = int(np.argmax(cnt)) + 1
    return lab == k, float(1.0 - cnt.max() / cnt.sum())


def mask_to_mesh(mask, grid, sigma_vox=0.8, budget=9000):
    """marching cubes of the Gaussian-smoothed mask (iso 0.5), largest connected surface piece, quadric decimation to `budget` triangles -> (v, f) in atlas mm"""
    from skimage import measure
    from scripts.export_viewer_bundle import decimate_quadric
    pad = int(np.ceil(3 * sigma_vox)) + 1
    m = np.pad(mask.astype(np.float32), pad)
    fld = ndi.gaussian_filter(m, sigma_vox) if sigma_vox > 0 else m
    v, f, _n, _val = measure.marching_cubes(fld, 0.5, spacing=(grid.h,) * 3)
    v = v + (grid.lo - pad * grid.h)
    tm = trimesh.Trimesh(v, f, process=False)
    parts = tm.split(only_watertight=False)
    if len(parts) > 1:
        tm = max(parts, key=lambda p: len(p.faces))
        v, f = np.asarray(tm.vertices), np.asarray(tm.faces)
    out = decimate_quadric(np.asarray(v, float), np.asarray(f, np.int64), budget)
    if out is not None:
        v, f = out
    return np.asarray(v, float), np.asarray(f, np.int64)


# ------------------------------------------------------------------------------------------ nerve corridor
def corridor_mask(grid, nerve_meshes, clearance, rmax=9.0):
    """voxels inside a nerve / vessel or within `clearance` mm of its surface.  nerve_meshes = [(v, f)]; the tubes are open at their ends, so the inside test is ray parity on the voxels within `rmax` mm of the surface only"""
    from scripts.zanatomy.q198_core import surf_points
    out = np.zeros(grid.shape, bool)
    for v, f in nerve_meshes:
        v = np.asarray(v, float)
        if (v.max(0) < grid.lo - rmax).any() or (v.min(0) > grid.lo + np.asarray(grid.shape) * grid.h + rmax).any():
            continue
        P = surf_points(v, np.asarray(f, np.int64), 0.4, cap=2000000)
        tree = cKDTree(P)
        lo = np.maximum(grid.idx(v.min(0) - rmax), 0)
        hi = np.minimum(grid.idx(v.max(0) + rmax) + 1, np.asarray(grid.shape))
        if (hi <= lo).any():
            continue
        sl = tuple(slice(int(a), int(b)) for a, b in zip(lo, hi))
        ii = np.argwhere(np.ones(tuple(hi - lo), bool)) + lo
        # only the voxels of the box that are within rmax of the surface
        d, _ = tree.query(grid.pos(ii), distance_upper_bound=rmax)
        near = np.isfinite(d)
        ii, d = ii[near], d[near]
        sel = d <= clearance
        tm = trimesh.Trimesh(v, np.asarray(f, np.int64), process=False)
        cand = ~sel
        if cand.any():
            ins = tm.contains(grid.pos(ii[cand]))
            sel[np.flatnonzero(cand)[ins]] = True
        out[tuple(ii[sel].T)] = True
    return out


def descent_channel(mask, h, seeds, max_mm=24.0, sigma_mm=1.2, stop_depth_mm=0.4):
    """voxels on the steepest-descent paths of the depth field of `mask` (EDT to the outside) from every seed voxel to the surface: the straight way out for a structure that lies inside a muscle"""
    depth = ndi.distance_transform_edt(mask, sampling=h).astype(np.float32)
    phi = ndi.gaussian_filter(depth, sigma_mm / h)
    gx, gy, gz = np.gradient(phi, h)
    pos = np.argwhere(seeds).astype(np.float32)
    path = np.zeros(mask.shape, bool)
    if not len(pos):
        return path
    path[tuple(pos.astype(int).T)] = True
    alive = np.ones(len(pos), bool)
    for _ in range(int(max_mm / h)):
        idx = np.flatnonzero(alive)
        if not len(idx):
            break
        p = pos[idx]
        coords = p.T
        g = np.stack([ndi.map_coordinates(c, coords, order=1, mode="nearest") for c in (gx, gy, gz)], 1)
        n = np.linalg.norm(g, axis=1, keepdims=True)
        step = -g / np.maximum(n, 1e-6)
        ph = ndi.map_coordinates(phi, coords, order=1, mode="nearest")
        stop = (ph <= stop_depth_mm) | (n[:, 0] < 1e-4)
        p2 = p + step
        ok = ~stop
        pos[idx[ok]] = p2[ok]
        alive[idx[stop]] = False
        ij = np.clip(np.rint(pos[idx[ok]]).astype(int), 0, np.asarray(mask.shape) - 1)
        path[tuple(ij.T)] = True
    return path


def carve_channel(mask, grid, corridor, slot_extra_mm=0.8):
    """the muscle minus the nerve corridor and the way out of it: -> (new mask, channel mask, dropped-fragment volume fraction)"""
    seeds = corridor & mask
    ch = descent_channel(mask, grid.h, seeds)
    ch |= corridor
    if slot_extra_mm > 0:
        dist = ndi.distance_transform_edt(~ch, sampling=grid.h)
        ch = dist <= slot_extra_mm
    new = mask & ~ch
    new, dropped = largest_components(new)
    new = ndi.binary_opening(new, structure=ndi.generate_binary_structure(3, 1), iterations=1) | (new & ~ndi.binary_dilation(ch, iterations=2))
    new, dropped2 = largest_components(new)
    return new, ch, dropped + dropped2


# ------------------------------------------------------------------------------------------ audit-equivalent measures
def weld_mesh(v, f, tol=0.02):
    from scripts.zanatomy.q198_core import weld
    return weld(v, f, tol)


def volume_cm3(v, f):
    tm = trimesh.Trimesh(np.asarray(v, float), np.asarray(f, np.int64), process=False)
    return abs(float(tm.volume)) / 1000.0


def audit_ends(v, f, bone_tree, frac=0.08, minv=6):
    """the Q204 / Q198 end test on a (merged) muscle mesh: PCA axis of the main connected component (oriented like the audit's pseudo joint axis = principal axis of all vertices), the extreme 8 % along it at
    each end, distance of those vertices to the nearest bone surface sample -> ({'prox': {...}, 'dist': {...}}, axis, centre); 'prox' = the low end along the axis (the audit's name)"""
    from scripts.zanatomy.q198_core import islands, pca
    from scripts.zanatomy.q198_soft import end_region
    v = np.asarray(v, float)
    p = v if len(v) < 20000 else v[:: len(v) // 20000 + 1]
    a = np.linalg.svd(p - p.mean(0), full_matrices=False)[2][0]            # q204_regions.pseudo_J
    vw, fw = weld_mesh(v, f)
    isl = islands(vw, fw)
    vm = vw[isl[0]["vidx"]]
    cc, vt, _sv = pca(vm)
    ax = vt[0]
    if np.dot(ax, a) < 0:
        ax = -ax
    vv = vw[np.unique(fw)]
    ends, _t = end_region(vv, ax, cc, frac, minv)
    out = {}
    for nm, e in zip(("prox", "dist"), ends):
        d = bone_tree.query(vv[e])[0]
        out[nm] = dict(min_any_bone_mm=round(float(d.min()), 2), median_any_bone_mm=round(float(np.median(d)), 2), centre=np.round(vv[e].mean(0), 1).tolist())
    return out, ax, cc


def flat_cap_rows(v, f, minarea=40.0):
    from scripts.zanatomy.q198_core import flat_caps
    return flat_caps(np.asarray(v, float), np.asarray(f, np.int64), minarea=minarea)


def island_rows(v, f):
    from scripts.zanatomy.q198_core import islands
    vw, fw = weld_mesh(v, f)
    isl = islands(vw, fw)
    tot = sum(i["area"] for i in isl)
    mt = cKDTree(vw[isl[0]["vidx"]])
    return [dict(area_share=round(i["area"] / tot, 4), faces=i["faces"], gap_mm=round(float(mt.query(vw[i["vidx"]])[0].min()), 2)) for i in isl[1:]]


def bone_surface_tree(B, side=None):
    """KD-tree of 1 mm surface samples of every displayed bone of the bundle (the Q204 BoneField 'any bone' distance)"""
    from scripts.zanatomy.q198_core import surf_points
    pts, names = [], []
    for it in B.items:
        e = it["e"]
        if e["cat"] == "bone" and not e.get("hidden_default"):
            v, f = B.mesh(it)
            if len(f):
                P = surf_points(v, f, 1.0, cap=50000)
                pts.append(P)
                names += [e["id"]] * len(P)
    return cKDTree(np.concatenate(pts)), np.asarray(names)
