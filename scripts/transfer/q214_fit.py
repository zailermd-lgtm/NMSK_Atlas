#!/usr/bin/env python3
"""Q214: transfer-fit of a Z-Anatomy muscle that an OWN page does not carry (splenius capitis / cervicis, fibularis brevis, flexor pollicis brevis) onto the person's own skeleton.

Source of the starting geometry = the Z-Anatomy page FITTED to this body (per-bone chain fits Q168 / Q195 / Q200 / Q211 onto the person's own bones; build/q211/viewer_zan_vhm for him, build/q213/viewer_zan_female for her).
Fit = bounded steps, each reported:
  1. ATTACHMENTS: the two end zones (extreme 12 % along the principal axis) are pulled onto the person's OWN bone landmark / bone set that the muscle's card names as origin / insertion (the closest 10 % of the
     zone's vertices land on the bone surface; capped at ATTACH_CAP_MM, farther = the fitted Z muscle does not reach the person's bone = refused); smooth displacement field, ends weighted.
  2. BONES + NEIGHBOURS: pushed out of the person's own bone meshes (margin 1.5 mm) and, by the Q200 bounded separation, out of the neighbouring muscle meshes; end zones held; a shallow clamp brings an end
     zone that the pull buried more than BONE_CLAMP_MM in its bone back; vertices near / outside the skin go inside it.  Variants (pull stiffness, bone chain, separation extent, displacement smoothing) are
     tried; the first that passes every guard wins, otherwise the best one is reported with its reasons.
  3. GUARDS (all must hold, else the muscle is NOT added and the reasons are recorded): every vertex inside the skin and >= SKIN_DEPTH_MIN_MM below it; belly <= BELLY_IN_BONE_MAX % and all vertices <=
     ALL_IN_BONE_MAX % inside bone, deepest embedding <= BONE_DEPTH_MAX_MM on the Q204 bone-depth lattice; <= OVERLAP_MAX % of the VOLUME inside other muscles measured exactly as the Q204 audit does (the
     rise it causes in each neighbour's overlap is reported with the card, not gated: the neighbours overlap their own neighbours already); volume ratio to the fitted Z muscle within VOL_LO..VOL_HI; end-to-end length ratio within LEN_LO..LEN_HI; folded faces <= FLIP_MAX_PCT, stretched
     triangles not up > 12 points; both ends within END_DIST_MAX_MM of their bone after the fit; mean / max move within MEAN_MOVE_MAX / MAX_MOVE_MAX.
Nothing is invented: the mesh is the Z-Anatomy structure, displaced inside bounds; the card states the numbers."""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import trimesh
from scipy.sparse import diags, identity
from scipy.sparse.linalg import spsolve
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "clinical"))
from scripts.transfer import q213_inbone as IB  # noqa: E402

ATTACH_CAP_MM = 25.0        # an end zone farther than this from its bone: the fitted Z muscle does not reach the person's bone
END_DIST_MAX_MM = 3.5       # after the fit: contact distance (5th percentile of the vertices) of each end zone to its bone (~2 x the 1.3-2.2 mm median distance of the fitted Z bones to the person's own bones)
BONE_MARGIN, MUSCLE_MARGIN = 1.5, 0.4
MEAN_MOVE_MAX, MAX_MOVE_MAX = 6.0, 20.0
BELLY_IN_BONE_MAX, ALL_IN_BONE_MAX = 5.0, 25.0
OVERLAP_MAX = 60.0          # gate on the VOLUME share inside other muscles (2 mm voxel field, as the Q204 audit measures it): above the Q198 / Q204 severity-2 line a new muscle would add a finding
OVERLAP_NOTE_MAX = 40.0     # the Q198 / Q204 severity-1 line: the card says so when the share is above it
VOL_LO, VOL_HI = 0.75, 1.30
LEN_LO, LEN_HI = 0.85, 1.20
SKIN_DEPTH_MIN_MM = 1.0
BONE_DEPTH_MAX_MM = 5.0     # deepest vertex inside a bone mesh (the Q204 regional pass counts an embedding > 5 mm as a defect: attachments embed 3-5 mm by design)
BONE_CLAMP_MM = 3.5         # vertices deeper than this inside a bone (Q204 lattice depth) are brought back to it
ZONE_FRAC = 0.12
FLIP_MAX_PCT = 1.0          # faces folded against the Z start mesh (the Z sources have 0 %; pressing a thin end sheet onto a curved bone surface folds ~0.5 % of its faces, the audit does not count it)
PULL_LAMS = (40.0, 8.0, 3.0)
LAMS = ((160.0, 40.0, 10.0), (40.0, 10.0, 3.0))
SEPARATION = ((6, 10.0), (12, 16.0), (16, 22.0))      # (rounds, total mm) of the Q200 bounded separation from the neighbouring muscles


# ----------------------------------------------------------------------------- context
class Context:
    """everything of one person that the fit measures against: bone meshes (displayed ones), muscle meshes, skin"""

    def __init__(self, bundle):
        self.B = bundle
        self.bones = {}
        self.muscles = {}
        lo, hi = np.full(3, np.inf), np.full(3, -np.inf)
        for k, it in enumerate(bundle.items):
            e = it["e"]
            v, f = bundle.mesh(it)
            if not e.get("hidden_default") and len(v):
                lo, hi = np.minimum(lo, v.min(0)), np.maximum(hi, v.max(0))
            if e["cat"] == "bone" and not e.get("hidden_default"):
                self.bones[f"{e['id']}#{k}"] = (v, f)
            elif e["cat"] == "muscle" and not e.get("hidden_default"):
                self.muscles[f"{e['id']}#{k}"] = (v, f)
        self.all_min, self.all_max = lo, hi
        self.bone_field = IB.BoneField(self.bones)
        sk = bundle.get("skin")
        self.skin = trimesh.Trimesh(sk["v"], sk["f"], process=False)
        from scripts.transfer.q200_geom import sample_surface
        self.skin_tree = cKDTree(sample_surface(sk["v"], sk["f"], 120000, 3))
        self.muscle_overlap = IB.MuscleOverlap(self.muscles)

    def bone_depth(self):
        if getattr(self, "q204_bone_depth", None) is None:
            self.q204_bone_depth = BoneDepth(self)
        return self.q204_bone_depth

    def overlap_field(self):
        """the Q204 lattice measure of this body's muscles (built once, kept up to date by add_muscle)"""
        if getattr(self, "q204_overlap", None) is None:
            self.q204_overlap = OverlapField(self)
        return self.q204_overlap

    def add_muscle(self, sid, v, f):
        """a muscle accepted in this run becomes a neighbour of the ones fitted after it"""
        k = f"{sid}#new"
        tm = trimesh.Trimesh(v, f, process=False)
        self.muscles[k] = (v, f)
        self.muscle_overlap.tm[k] = tm
        self.muscle_overlap.box[k] = (tm.bounds[0] - 1.0, tm.bounds[1] + 1.0)
        if getattr(self, "q204_overlap", None) is not None:
            self.q204_overlap.add(v, f, sid)

    def bone_ids(self, pattern):
        rx = re.compile(pattern)
        return [k for k in self.bones if rx.match(k.split("#")[0])]

    def bone_pts(self, pattern):
        ks = self.bone_ids(pattern)
        if not ks:
            return np.zeros((0, 3))
        return np.vstack([self.bones[k][0] for k in ks])

    def neighbour_field(self, skip_ids=()):
        """BoneField of every muscle mesh except the ones whose id is in skip_ids"""
        return IB.BoneField({k: v for k, v in self.muscles.items() if k.split("#")[0] not in set(skip_ids)})

    def skin_inset(self, V, min_depth=SKIN_DEPTH_MIN_MM + 0.3, inset=1.6):
        """vertices outside the skin or closer to it than `min_depth` mm go to the nearest skin-surface point, inset by `inset` mm towards the inside (q200_geom.clip_skin_nearest rule, local move)"""
        out = V.copy()
        ins = self.skin.contains(out)
        d = self.skin_tree.query(out)[0]
        bad = np.flatnonzero((~ins) | (d < min_depth))
        if not len(bad):
            return out
        cl, _d, tri = self.skin.nearest.on_surface(out[bad])
        nrm = self.skin.face_normals[tri]
        a, b = cl - nrm * inset, cl + nrm * inset
        out[bad] = np.where(self.skin.contains(a)[:, None], a, b)
        return out

    def skin_state(self, V):
        inside = self.skin.contains(V)
        d = self.skin_tree.query(V)[0]
        return float(inside.mean() * 100.0), float(np.where(inside, d, -d).min())


class BoneDepth:
    """depth (mm) of a point inside the person's bones on the SAME 2 mm lattice and with the same per-bone rasterisation as the Q204 audit (scripts/zanatomy/q204_regions.py BoneVox: every displayed bone
    rasterised on its own local grid, surface closed by one dilation, filled, Euclidean depth; union depth = the deepest of the bones).  The audit counts an embedding > 5 mm of >= 8 % of a muscle's
    vertices (> 1.5 mm deep) as a finding; ray parity on the open CT bone meshes under-reads it (the mastoid end of the Z splenius reads 3 mm by ray parity, 8 mm on the lattice)."""
    H = 2.0

    def __init__(self, ctx):
        from scipy import ndimage as ndi
        from scripts.zanatomy.q198_core import Grid
        lo = getattr(ctx, "all_min", None)
        hi = getattr(ctx, "all_max", None)
        if lo is None or not np.isfinite(lo).all():
            vs = [np.asarray(ctx.skin.vertices)] + [v for v, f in ctx.bones.values()]
            lo, hi = np.min([x.min(0) for x in vs], axis=0), np.max([x.max(0) for x in vs], axis=0)
        self.lo = np.asarray(lo, float) - 8.0
        hi = np.asarray(hi, float) + 8.0
        self.shape = tuple(np.ceil((hi - self.lo) / self.H).astype(int) + 1)
        self.d1 = np.zeros(self.shape, np.float16)
        for k, (v, f) in ctx.bones.items():
            if len(f) < 4:
                continue
            i0 = np.maximum(np.floor((v.min(0) - 6.0 - self.lo) / self.H).astype(int), 0)
            gl = Grid(self.lo + i0 * self.H, v.max(0) + 6.0, self.H)
            try:
                sol = gl.solid(np.asarray(v, float), np.asarray(f, np.int64), close=1)
            except Exception:  # noqa
                continue
            if not sol.any():
                continue
            dep = ndi.distance_transform_edt(sol, sampling=self.H).astype(np.float16)
            sl = tuple(slice(int(i0[a]), min(int(i0[a]) + sol.shape[a], self.shape[a])) for a in range(3))
            sub = tuple(slice(0, sl[a].stop - sl[a].start) for a in range(3))
            self.d1[sl] = np.maximum(self.d1[sl], np.where(sol[sub], dep[sub], 0))

    def depth(self, P):
        i = np.floor((np.asarray(P) - self.lo) / self.H + 0.5).astype(np.int64)
        ok = ((i >= 0) & (i < np.asarray(self.shape))).all(1)
        out = np.zeros(len(P), np.float32)
        out[ok] = self.d1[i[ok, 0], i[ok, 1], i[ok, 2]]
        return out

    def outward(self, P):
        """unit vector of steepest decrease of the depth at P (central differences over one voxel)"""
        h = self.H
        g = np.column_stack([self.depth(P + np.eye(3)[k] * h) - self.depth(P - np.eye(3)[k] * h) for k in range(3)])
        n = np.linalg.norm(g, axis=1, keepdims=True)
        return -g / np.maximum(n, 1e-6)


class OverlapField:
    """% of the volume of a mesh that lies inside other muscles, measured EXACTLY the way scripts/zanatomy/q204_regions.py measures `overlap_pct`: every muscle is rasterised on its own local grid
    (surface closed by one dilation, filled) aligned to ONE global 2 mm lattice (origin = min of all structures - 8 mm), the muscles' voxels are counted, and a muscle's overlap is the share of its voxels
    that another muscle also covers.  (A local grid per muscle is essential: filling the interior of a big neighbour on a small box would leave it hollow and under-read the overlap 3-5 times.)  The
    Z-fill continuation pieces `<id>_zfill*` of a muscle count with that muscle (the Q204 audit merges them first).  `ctx` supplies the muscle meshes (neighbours); muscles accepted in this run are added
    with `add`.  `harm` = how much a candidate muscle raises the overlap of each neighbour (reported with the card; a neighbour that crosses the Q198 / Q204 40 / 60 % line gets a new audit finding)."""
    H = 2.0

    def __init__(self, ctx, skip_ids=()):
        from scripts.zanatomy.q198_core import Grid
        self.Grid = Grid
        lo = getattr(ctx, "all_min", None)
        hi = getattr(ctx, "all_max", None)
        if lo is None or not np.isfinite(lo).all():
            vs = [np.asarray(ctx.skin.vertices)] + [v for v, f in ctx.muscles.values()]
            lo, hi = np.min([x.min(0) for x in vs], axis=0), np.max([x.max(0) for x in vs], axis=0)
        self.lo = np.asarray(lo, float) - 8.0
        hi = np.asarray(hi, float) + 8.0
        self.shape = tuple(np.ceil((hi - self.lo) / self.H).astype(int) + 1)
        self.cnt = np.zeros(self.shape, np.int8)
        self.groups, self.gbox = {}, {}
        skip = set(skip_ids)
        # the audit merges the Z-fill continuation pieces `<id>_zfill*` into their muscle BEFORE it rasterises (scripts/zanatomy/q204_paths.merge_zfill: concatenation, the flat cut faces of the base under the
        # continuation dropped); the same function is used here so that a neighbour's voxels are the audit's
        from scripts.zanatomy.q204_paths import merge_zfill
        S = [{"id": k.split("#")[0], "v": v, "f": f, "sys": "muscle"} for k, (v, f) in ctx.muscles.items() if k.split("#")[0] not in skip and len(f) > 4]
        for st in merge_zfill(S):
            self._put(st["id"], self.voxels(st["v"], st["f"]))

    def _put(self, mid, w):
        w = w.astype(np.int32)
        self.groups[mid] = w
        self.gbox[mid] = (w.min(0), w.max(0))
        self.cnt[tuple(w.T)] += 1

    def voxels(self, v, f):
        i0 = np.maximum(np.floor((v.min(0) - 6.0 - self.lo) / self.H).astype(int), 0)
        gl = self.Grid(self.lo + i0 * self.H, v.max(0) + 6.0, self.H)
        w = np.argwhere(gl.solid(np.asarray(v, float), np.asarray(f, np.int64), close=1)) + i0
        return w[(w < np.asarray(self.shape)).all(1)]

    def add(self, v, f, mid=None):
        w = self.voxels(v, f)
        if len(w):
            self._put(mid or f"new{len(self.groups)}", w)

    def pct(self, v, f):
        w = self.voxels(v, f)
        return 100.0 * float((self.cnt[tuple(w.T)] > 0).mean()) if len(w) else 0.0

    def harm(self, v, f):
        """[(neighbour id, overlap % before, overlap % after)] for every neighbour whose overlap rises when the mesh (v, f) is added, largest rise first"""
        w = self.voxels(v, f)
        if not len(w):
            return []
        mask = np.zeros(self.shape, bool)
        mask[tuple(w.T)] = True
        lo, hi = w.min(0), w.max(0)
        out = []
        for mid, g in self.groups.items():
            b0, b1 = self.gbox[mid]
            if (b1 < lo).any() or (b0 > hi).any():
                continue
            inter = mask[tuple(g.T)]
            if not inter.any():
                continue
            c = self.cnt[tuple(g.T)].astype(np.int16)
            out.append((mid, round(100.0 * float((c > 1).mean()), 1), round(100.0 * float(((c + inter) > 1).mean()), 1)))
        return sorted([x for x in out if x[2] > x[1]], key=lambda x: x[1] - x[2])


def vertebra_pieces(ctx, prefix):
    """[(level, V)] of the vertebra pieces `prefix` (cervical_vertebrae / thoracic_vertebrae), level 1 = topmost"""
    ks = ctx.bone_ids(rf"^{prefix}$")
    ks = sorted(ks, key=lambda k: -ctx.bones[k][0][:, 1].mean())
    return [(i + 1, ctx.bones[k][0]) for i, k in enumerate(ks)]


def spinous_pts(ctx, prefix, lv0, lv1, band=18.0):
    """posterior-most part (z within `band` mm of the vertebra's most posterior vertex, near the midline) of vertebrae lv0..lv1 of that series"""
    out = []
    for lv, V in vertebra_pieces(ctx, prefix):
        if lv0 <= lv <= lv1:
            xm = np.median(V[:, 0])
            sel = V[(np.abs(V[:, 0] - xm) < 10) & (V[:, 2] <= V[:, 2].min() + band)]
            out.append(sel)
    return np.vstack(out) if out else np.zeros((0, 3))


def transverse_pts(ctx, prefix, lv0, lv1, side):
    out = []
    sx = 1 if side == "r" else -1
    for lv, V in vertebra_pieces(ctx, prefix):
        if lv0 <= lv <= lv1:
            xm = np.median(V[:, 0])
            half = 0.5 * (V[:, 0].max() - V[:, 0].min())
            sel = V[(sx * (V[:, 0] - xm) > 0.35 * half)]
            out.append(sel)
    return np.vstack(out) if out else np.zeros((0, 3))


# ----------------------------------------------------------------------------- end zones
def axis_and_zones(v, frac=ZONE_FRAC):
    c = v.mean(0)
    u = np.linalg.svd(v - c, full_matrices=False)[2][0]
    t = (v - c) @ u
    lo, hi = np.percentile(t, [100 * frac, 100 * (1 - frac)])
    return u, t, (t <= lo), (t >= hi)


def length_mm(v, z_lo, z_hi):
    return float(np.linalg.norm(v[z_hi].mean(0) - v[z_lo].mean(0)))


def assign_targets(v, z_lo, z_hi, tgt_a, tgt_b):
    """which end zone goes to target A (origin) and which to B (insertion): the assignment with the smaller total distance"""
    ta, tb = cKDTree(tgt_a), cKDTree(tgt_b)
    d = lambda tree, z: float(np.percentile(tree.query(v[z])[0], 5))
    s1 = d(ta, z_lo) + d(tb, z_hi)
    s2 = d(ta, z_hi) + d(tb, z_lo)
    return (z_lo, z_hi) if s1 <= s2 else (z_hi, z_lo)


def pull_ends(v, f, zones_targets, lam=40.0, w=30.0):
    """zones_targets = [(zone mask, target point cloud)]; each zone is translated so that its centroid lands on the nearest target point (cap ATTACH_CAP_MM); smooth field over the mesh.
    -> (new v, per-zone info) or (None, info) when a zone is farther than the cap"""
    n = len(v)
    Lap = IB.laplacian(n, f)
    W = np.zeros(n)
    P = np.zeros((n, 3))
    info = []
    for zone, tgt in zones_targets:
        tree = cKDTree(tgt)
        cen = v[zone].mean(0)
        d0 = tree.query(v[zone])[0]
        dc, i = tree.query(cen)
        # the zone is translated so that its closest 10 % of vertices land on the bone surface (mean vector to the nearest bone point); a broad origin touches along a line, not with every vertex
        idx = np.argsort(d0)[: max(3, int(0.10 * len(d0)))]
        vz = v[zone]
        step = (tgt[tree.query(vz[idx])[1]] - vz[idx]).mean(axis=0)
        info.append(dict(dist_before_p5=float(np.percentile(d0, 5)), dist_before_min=float(d0.min()), step_mm=float(np.linalg.norm(step))))
        if np.linalg.norm(step) > ATTACH_CAP_MM:
            info[-1]["refused"] = True
            return None, info
        if float(np.percentile(d0, 5)) <= 1.5:
            step = np.zeros(3)                  # already touching its bone
        W[zone] = w
        P[zone] = step
    if not W.any():
        return v.copy(), info
    M = (diags(W) + lam * Lap + 1e-3 * identity(n)).tocsc()
    D = np.column_stack([spsolve(M, W * P[:, k]) for k in range(3)])
    return v + D, info


# ----------------------------------------------------------------------------- fit
def zone_dist(v, zone, tgt):
    """contact distance of an end zone to its bone: 5th percentile of the vertex distances (a broad origin touches its bone along a line, not with every vertex)"""
    return float(np.percentile(cKDTree(tgt).query(v[zone])[0], 5))


def bone_push(v0, f, ctx, start, ends, lams):
    cur = start
    for lam in lams:
        cur, _r = IB.push_out(v0, f, ctx.bone_field, lam=lam, start=cur, ends=ends, margin=BONE_MARGIN)
    return cur


def shallow_bone_clamp(v0, f, ctx, start, lam=1.0, passes=20):
    """the pull of an attachment (and the Z source itself) may bury an end zone in its bone: vertices deeper than BONE_CLAMP_MM on the Q204 bone-depth lattice are brought back to BONE_CLAMP_MM - 0.5
    (smooth, local field: the correction decays within ~10 mm of the embedded vertices)"""
    from scipy.sparse import diags, identity
    from scipy.sparse.linalg import spsolve
    bd = ctx.bone_depth()
    n = len(v0)
    Lap = IB.laplacian(n, f)
    cur = start.copy()
    for _ in range(passes):
        d = bd.depth(cur)
        deep = d > BONE_CLAMP_MM
        if not deep.any():
            break
        P = np.where(deep[:, None], bd.outward(cur) * (d - BONE_CLAMP_MM + 0.5)[:, None], 0.0)
        w = deep.astype(float)
        M = (diags(w) + lam * Lap + 0.05 * identity(n)).tocsc()
        cur = cur + np.column_stack([spsolve(M, w * P[:, k]) for k in range(3)])
    return cur


def smooth_displacement(v0, v1, f, iters):
    """Laplacian smoothing of the DISPLACEMENT field (not of the surface): removes the folds a local push leaves, keeps the shape of the muscle"""
    from scripts.transfer.q200_overlap import _lap
    return v0 + _lap(v0, f, v1 - v0, iters=iters)


def inner_fit(v0, f, ctx, tgt_a, tgt_b, skip_ids=(), log=lambda *a: None):
    """-> (vertices or None, report).  v0 = the Z muscle fitted to the body.  tgt_a / tgt_b = point clouds of the origin / insertion bone landmark sets.
    Variants tried (first one that passes every guard wins, else the best one is reported with its reasons): pull stiffness x bone-push chain x separation extent x displacement smoothing."""
    from scripts.transfer.q200_overlap import separate
    rep = dict(guards={}, why_not=[])
    u, t, z_lo, z_hi = axis_and_zones(v0)
    za, zb = assign_targets(v0, z_lo, z_hi, tgt_a, tgt_b)
    L0 = length_mm(v0, z_lo, z_hi)
    vol0 = IB.volume(v0, f)
    rep["length_z_mm"], rep["volume_z_cm3"] = round(L0, 1), round(vol0 / 1000.0, 2)
    rep["end_dist_z_mm"] = [round(zone_dist(v0, za, tgt_a), 1), round(zone_dist(v0, zb, tgt_b), 1)]
    pull0, info = pull_ends(v0, f, [(za, tgt_a), (zb, tgt_b)])
    rep["attach_pull"] = info
    if pull0 is None:
        rep["why_not"].append("the fitted Z muscle's end lies %.0f mm from the person's bone named as origin / insertion (cap %.0f mm)" % (max(i["step_mm"] for i in info), ATTACH_CAP_MM))
        return None, rep
    ends = za | zb
    lo, hi = v0.min(0) - 12.0, v0.max(0) + 12.0
    others = [m for k, m in ctx.muscle_overlap.tm.items() if k.split("#")[0] not in set(skip_ids) and not ((m.bounds[1] < lo).any() or (m.bounds[0] > hi).any())]
    best = None
    ofield = ctx.overlap_field()
    big_pull = max(i["step_mm"] for i in info) > 8.0
    for pull_lam in (PULL_LAMS if big_pull else PULL_LAMS[:1]):          # the stiffer / softer pull fields only matter when an end has to travel far
        pv, _ = pull_ends(v0, f, [(za, tgt_a), (zb, tgt_b)], lam=pull_lam)
        for lams in LAMS:
            stage1 = bone_push(v0, f, ctx, pv, ends, lams)
            constrain = lambda x, lams=lams: bone_push(v0, f, ctx, x, ends, lams)
            for rounds, total in SEPARATION:
                sep, sinfo = separate(stage1, f, others, constrain=constrain, pin=ends, rounds=rounds, step=0.7, per_round=3.0, total=total, vol=(0.75, 1.3))
                for sm in (8, 16, 30, 60):
                    base = smooth_displacement(v0, sep, f, sm)
                    base = ctx.skin_inset(base)
                    base = bone_push(v0, f, ctx, base, ends, lams)
                    base = shallow_bone_clamp(v0, f, ctx, base)
                    for post in (0,):
                        cur = base
                        cand = evaluate(v0, cur, f, ctx, za, zb, tgt_a, tgt_b, L0, vol0, skip_ids, ofield)
                        gg = cand["guards"]
                        log("   pull", pull_lam, "chain", lams, "sep", rounds, total, "smooth", sm, post, "| overlap", gg["overlap_pct"], "vol", gg["overlap_vol_pct"], "zfit-vol", gg["overlap_vol_z_fit_pct"], "belly-bone", gg["belly_in_bone_pct"],
                            "depth", gg["bone_depth_max_mm"], "flip", gg["flipped_pct"], "stretch", gg["stretched_after"], "move", gg["mean_move_mm"], gg["max_move_mm"], "vol", gg["volume_ratio"], "ends", gg["end_dist_mm"], cand["why_not"])
                        ok = not cand["why_not"]
                        key = (not ok, len(cand["why_not"]), gg["overlap_vol_pct"] + 3 * gg["belly_in_bone_pct"] + 10 * gg["flipped_pct"] + gg["mean_move_mm"])
                        if best is None or key < best[0]:
                            best = (key, cur, cand, (pull_lam, lams, rounds, total, (sm, post)), sinfo)
                        if ok:
                            break
                    if best[0][0] is False:
                        break
                if best[0][0] is False:
                    break
            if best[0][0] is False:
                break
        if best[0][0] is False:
            break
    _, cur, cand, par, sinfo = best
    cand["variant"] = dict(pull_lam=par[0], bone_chain=list(par[1]), separation_rounds=par[2], separation_total_mm=par[3], displacement_smoothing=par[4][0])
    cand["separation"] = {k: round(float(x), 3) for k, x in sinfo.items()}
    cand.update({k: rep[k] for k in ("length_z_mm", "volume_z_cm3", "end_dist_z_mm", "attach_pull")})
    return (cur if not cand["why_not"] else None), cand


def evaluate(v0, v1, f, ctx, za, zb, tgt_a, tgt_b, L0, vol0, skip_ids=(), ofield=None):
    g, why = {}, []
    ins, _, dist = ctx.bone_field.inside(v1)
    belly = ~(za | zb)
    g["in_bone_pct"] = round(100.0 * float(ins.mean()), 1)
    g["belly_in_bone_pct"] = round(100.0 * float(ins[belly].mean()), 1)
    g["deep_in_bone_pct"] = round(100.0 * float((np.isfinite(dist) & (dist > 1.5)).mean()), 1)
    bdp = ctx.bone_depth().depth(v1)
    g["bone_depth_max_mm"] = round(float(bdp.max()), 1)
    g["bone_deep_pct"] = round(100.0 * float((bdp > 1.5).mean()), 1)
    ov = ctx.muscle_overlap.pct(v1, skip=_skip_keys(ctx, skip_ids))
    g["overlap_pct"] = round(ov, 1)
    g["overlap_z_fit_pct"] = round(ctx.muscle_overlap.pct(v0, skip=_skip_keys(ctx, skip_ids)), 1)
    ofield = ofield or ctx.overlap_field()
    g["overlap_vol_pct"] = round(ofield.pct(v1, f), 1)
    hm = ofield.harm(v1, f)
    g["neighbour_overlap_rise"] = [list(x) for x in hm[:8]]
    g["neighbours_over_the_line"] = [list(x) for x in hm if (x[1] <= OVERLAP_NOTE_MAX < x[2]) or (x[1] <= OVERLAP_MAX < x[2])]
    g["overlap_vol_z_fit_pct"] = round(ofield.pct(v0, f), 1)
    sk_in, sk_depth = ctx.skin_state(v1)
    g["inside_skin_pct"], g["min_skin_depth_mm"] = round(sk_in, 2), round(sk_depth, 1)
    mv = np.linalg.norm(v1 - v0, axis=1)
    g["mean_move_mm"], g["max_move_mm"] = round(float(mv.mean()), 2), round(float(mv.max()), 2)
    vol1 = IB.volume(v1, f)
    g["volume_cm3"] = round(vol1 / 1000.0, 2)
    g["volume_ratio"] = round(vol1 / max(vol0, 1e-9), 3)
    g["length_mm"] = round(length_mm(v1, za, zb), 1)
    g["length_ratio"] = round(g["length_mm"] / max(L0, 1e-9), 3)
    g["flipped_pct"] = round(IB.flipped_pct(v0, v1, f), 2)
    g["stretched_before"], g["stretched_after"] = round(IB.stretched_pct(v0, v0, f), 1), round(IB.stretched_pct(v0, v1, f), 1)
    g["end_dist_mm"] = [round(zone_dist(v1, za, tgt_a), 1), round(zone_dist(v1, zb, tgt_b), 1)]
    if g["belly_in_bone_pct"] > BELLY_IN_BONE_MAX:
        why.append(f"{g['belly_in_bone_pct']} % of the belly still inside her bones (gate {BELLY_IN_BONE_MAX:g})")
    if g["in_bone_pct"] > ALL_IN_BONE_MAX:
        why.append(f"{g['in_bone_pct']} % of the vertices inside bone (gate {ALL_IN_BONE_MAX:g})")
    if g["bone_depth_max_mm"] > BONE_DEPTH_MAX_MM:
        why.append(f"embedded {g['bone_depth_max_mm']} mm in a bone mesh (gate {BONE_DEPTH_MAX_MM:g} mm)")
    if g["overlap_vol_pct"] > OVERLAP_MAX:
        why.append(f"{g['overlap_vol_pct']} % of its volume inside the neighbouring muscles (gate {OVERLAP_MAX:g}; fitted Z muscle {g['overlap_vol_z_fit_pct']} %; {g['overlap_pct']} % of the vertices)")
    if g["inside_skin_pct"] < 100.0 or g["min_skin_depth_mm"] < SKIN_DEPTH_MIN_MM:
        why.append(f"skin: {g['inside_skin_pct']} % inside, closest {g['min_skin_depth_mm']} mm to the surface (gate 100 %, >= {SKIN_DEPTH_MIN_MM:g} mm)")
    if g["mean_move_mm"] > MEAN_MOVE_MAX or g["max_move_mm"] > MAX_MOVE_MAX:
        why.append(f"move mean {g['mean_move_mm']} / max {g['max_move_mm']} mm (gate {MEAN_MOVE_MAX:g} / {MAX_MOVE_MAX:g})")
    if not (VOL_LO <= g["volume_ratio"] <= VOL_HI):
        why.append(f"volume x{g['volume_ratio']} of the fitted Z muscle (gate {VOL_LO}-{VOL_HI})")
    if not (LEN_LO <= g["length_ratio"] <= LEN_HI):
        why.append(f"length x{g['length_ratio']} (gate {LEN_LO}-{LEN_HI})")
    if g["flipped_pct"] > FLIP_MAX_PCT:
        why.append(f"{g['flipped_pct']} % faces flipped")
    if g["stretched_after"] > g["stretched_before"] + 12.0:
        why.append(f"stretched triangles {g['stretched_before']} -> {g['stretched_after']} %")
    if max(g["end_dist_mm"]) > END_DIST_MAX_MM:
        why.append(f"an end lies {max(g['end_dist_mm'])} mm from its bone (gate {END_DIST_MAX_MM:g})")
    return dict(guards=g, why_not=why)


def _skip_keys(ctx, ids):
    ids = set(ids)
    return [k for k in ctx.muscles if k.split("#")[0] in ids]


def neighbour_table(v, ctx, skip_ids=(), top=8):
    """share (%) of the vertices of v inside each neighbouring muscle (by id, pieces summed), largest first"""
    out = {}
    skip = set(skip_ids)
    inm_any = np.zeros(len(v), bool)
    for k, m in ctx.muscle_overlap.tm.items():
        sid = k.split("#")[0]
        if sid in skip:
            continue
        lo, hi = ctx.muscle_overlap.box[k]
        sel = np.flatnonzero(np.all((v >= lo) & (v <= hi), axis=1))
        if len(sel):
            c = m.contains(v[sel])
            if c.any():
                out[sid] = out.get(sid, 0) + int(c.sum())
                inm_any[sel[c]] = True
    rows = sorted(((s, round(100.0 * c / len(v), 1)) for s, c in out.items()), key=lambda x: -x[1])[:top]
    return rows
