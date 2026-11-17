#!/usr/bin/env python3
"""Q360: Base · Female anterior trunk skin -- one seamless surface, as the back is: the 18 chest skin regions rebuilt from their
Z-Anatomy source topology by ONE joint deformation onto the current (Q292-fitted) chest surface.

    python3 scripts/anatomy/q360/chest_skin_q360.py --page-dir DIR                       # dry run: build + measure, report only
    python3 scripts/anatomy/q360/chest_skin_q360.py --page-dir DIR --write               # and write DIR (+ the pose rig, see --rig-file)
    options: --source-dir DIR (Base · Male page, default <page-dir>/../viewer_zan_atlas), --rig-file FILE, --no-rig, --report FILE

Cause (measured, Q356 + this round): Q292 fitted the chest skin regions onto her CT skin from the Z-Anatomy patches merged with
`merge_vertices(digits_vertex=3)` -- but those patches were decoded from a page, where every mesh is quantised over its own box,
so the "same" border vertex of two regions differs by micrometres and was NOT merged; the regions were then subdivided and their
fit displacement smoothed each over its own mesh. Hence: borders that share 0-15 % of their vertices, rounded rims (no outer-to-wall
crease), slots up to ~5 mm, overlaps, serrated edges -- and the load-time weld (Q334) finds nothing to join. Every backup beside the
page files (`*.q318` .. `*.q358`) holds these 18 meshes byte-identical to the current ones: no pre-Q292 copy exists there.

The fix (route A, a joint refit; deterministic, nothing invented, every number into the report):
  1. SOURCE: the 18 regions' Z-Anatomy slabs as they are on the Base · Male page (the same Z body; every other Base · Female skin
     region still has their exact topology). Their outer sheets are merged into ONE surface (vertices within the engine's weld
     distance, 0.03 mm, are one vertex), region label per face. A vertex shared with an unchanged neighbouring region is LOCKED at
     that neighbour's Base · Female vertex (so those borders stay exact).
  2. FRAME: the rest is carried into the Base · Female frame by a thin-plate spline through the displacements of the unchanged skin
     regions and the trunk / shoulder bones (identical topology on both pages: the Q250 female-skeleton deformation, re-measured).
  3. DENSITY: subdivided as one mesh (conforming longest-edge bisection) to EDGE_MM edges, as Q292 did (borders with unchanged
     regions are not split, so they keep their exact shared vertices).
  4. FIT: one smooth displacement field over the whole merged surface (membrane-regularised non-rigid ICP, stiff to soft) onto the
     CURRENT outer sheets of the 18 regions (their rounded rims left out). Where the current pieces disagree: in a band around their
     borders the data weight fades, so the surface bridges their steps smoothly; where two pieces overlap (stacked) it follows the
     outermost (what is seen today); in a slot (no current piece) it is interpolated from both sides.
  5. SLABS: each region is cut back out of the merged surface by its label, with an inner sheet THICK mm under it (the Z slab
     thickness, measured) and a wall at every border, so neighbours share their border vertices (outer and inner) and the rim is a
     crease -- as the back regions are. Vertex counts change; the pose rig follows (weights transferred from the current meshes).
  6. TUCK: breast tissue (and any other structure that would end outside) is moved under the new skin by Q353's guarded tuck rule.
Guards: weld % per region (Python copy of the Q334 weld rules) >= WELD_MIN; front / lateral z-buffer holes (a deeper structure seen
where skin should be) = 0 px in the chest window; deviation from the current outer surface <= DEV_CAP (core) / DEV_CAP_BORDER (band
of the current borders); breast tissue, muscle and rib: 0 vertices outside the skin; no folded / flipped face; closed, consistently
wound slabs. Originals kept beside each changed file as `<name>.q360` (never overwritten). A page whose chest regions already carry
the Q360 sentence is refused (restore the `.q360` copies and the rig to re-apply). Report: data/derived/Q360_chest_skin_report.json.
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import shutil
import sys
import time
import zlib
from pathlib import Path

import numpy as np
import trimesh
from scipy import sparse
from scipy.interpolate import RBFInterpolator
from scipy.sparse.linalg import spsolve
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
for p in (REPO, REPO / "scripts" / "zanatomy", REPO / "scripts" / "anatomy" / "q340", REPO / "scripts" / "anatomy" / "q353",
          REPO / "scripts" / "anatomy" / "q241"):
    sys.path.insert(0, str(p))
import build_zan_atlas_viewer as B  # noqa: E402  pack_mesh / split_blob
import conform_palm_q340 as C340    # noqa: E402  page I/O
import conform_skin_q353 as Q       # noqa: E402  Geo / sheets / SkinSet / run_tuck / outside_count / Bones

STEM = "atlas_viewer_base_female"
SRC_STEM = "atlas_viewer_zan_atlas"
TAG = "Q360"
REPORT = REPO / "data/derived/Q360_chest_skin_report.json"
RIG = REPO / "data/anatomy/pose_rig_base_f.json"
LAST_IDS = ("skin_vulva_cvh", "skin_perineum_rule_q358")
CHEST_RE = re.compile(r"mammary|pectoral_region|presternal|lateral_region_of_thorax|epigastric|infraclavicular|deltopectoral|"
                      r"hypochondriac")       # the regions Q292 refitted (scripts/anatomy/q292/build_q292.py SKIN_PATCH_RE)
BREAST = Q.BREAST + ["breast_ct_r", "breast_ct_l", "breast_fgt_ct_r", "breast_fgt_ct_l"]

# ------------------------------------------------------------------ parameters
WELD_MM = 0.03       # the engine's weld distance (Q334 WELD)
CRACK_MM = 0.6       # mm: Z source border vertices of two regions this close are one vertex (the engine's rim join reaches 1 mm)
TJ_MM = 1.0          # mm: a border vertex this close to an unchanged neighbour's edge is a T-junction on that edge
EDGE_MM = 4.0        # target edge length after subdivision (Q292 SKIN_EDGE)
GRADE = 0.7          # near a long unsplit border edge the faces may keep edges up to GRADE x its length (graded away from it)
RIM_EXCL = 2.0       # mm: current outer-sheet faces this close to their region's rim are the rounded rim, not the surface
BAND_IN, BAND_OUT = 2.0, 8.0   # mm from a current border: data weight 0 inside BAND_IN, full from BAND_OUT (smoothstep)
STIFF = (0.01, 0.03, 0.1, 0.3, 1.0, 3.0, 10.0, 10.0)   # data weight (x vertex degree) per ICP round: stiff -> soft
SAMPLE_MM = 0.5      # target sampling (closest point = nearest sample + projection onto its face plane)
TANG_MAX = 1.5       # mm: a point farther than this sideways from a piece's surface lies beyond that piece (slot), not over it
OVL_MM = 8.0         # mm: stacked pieces within this height of the nearest one: the outermost is followed
PLAUS_MM = 25.0      # mm: in the soft rounds a target farther than this is not trusted
PRE_RELEASE = False  # True: release before the subdivision (that border is then refined freely); False: in the fit + neighbour follows
RIM_PULL = False     # a released border vertex is fitted like any free border vertex (True: pulled to the current pieces' rim)
FAR_ROUNDS = 3       # the first (stiff, far) rounds find the surface through Q353's outer-sheet classification
FACE_COS = 0.8       # a target sample whose face normal is more than ~37 degrees off the vertex normal is not followed
LOCK_GAP_MAX = 6.0   # mm: a neighbour's border vertex farther than this (a skin thickness) from the current chest surface is not
#                      joined: there the chest skin lies over the neighbour's edge (axilla: Q292 pushed it out over her breast)
LOCK_REACH, LOCK_REACH_MIN, LOCK_REACH_MAX = 4.0, 12.0, 40.0   # no data within 4 x the gap (12..40 mm) of a disagreeing locked vertex
DEV_CAP = 1.5        # mm: max deviation from the current outer surface away from the current borders (core)
DEV_CAP_BORDER = 6.0 # mm: max deviation within BAND_OUT of a current border (pieces disagree by up to ~10 mm there)
WELD_MIN = 80.0      # % of rim vertices that must weld (exact or rim-join), per changed region
FOLD_COS = -0.5      # neighbouring outer faces more than 120 degrees apart = folded
RBF_N = 6000         # thin-plate spline samples (deterministic stride)
TUCK_GUARD = ("muscle", "bone", "cartilage")
CHEST_BOX = (np.array([-220.0, 230.0, -160.0]), np.array([220.0, 700.0, 200.0]))
PX = 0.5             # mm per pixel of the hole raster
FOLD_MAX_PCT = 0.2   # % of the new outer faces that may be folded (> 120 degrees to a neighbour) or have a flipped inner face
HOLE_PIECE_MAX = 100 # px (25 mm2): no see-through piece larger than this, and no view with more hole pixels than before


# ------------------------------------------------------------------ small helpers
def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def st(x):
    x = np.asarray(x, float)
    if not len(x):
        return None
    return {"max": round(float(x.max()), 2), "mean": round(float(x.mean()), 2), "p95": round(float(np.percentile(x, 95)), 2),
            "n": int(len(x))}


def edges_of(f):
    e = np.sort(np.vstack([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]), axis=1)
    return e


def vnormals(v, f):
    """three.js computeVertexNormals: area-weighted sum of the face normals, normalised"""
    fn = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
    n = np.zeros_like(v)
    for k in range(3):
        np.add.at(n, f[:, k], fn)
    return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)


def fnormals(v, f):
    fn = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
    return fn / np.maximum(np.linalg.norm(fn, axis=1, keepdims=True), 1e-12)


def laplacian(n, f):
    e = np.unique(edges_of(f), axis=0)
    A = sparse.coo_matrix((np.ones(2 * len(e)), (np.r_[e[:, 0], e[:, 1]], np.r_[e[:, 1], e[:, 0]])), shape=(n, n)).tocsr()
    deg = np.asarray(A.sum(1)).ravel()
    return sparse.diags(deg) - A, deg


class UF:
    def __init__(self, n):
        self.p = np.arange(n)

    def find(self, a):
        p = self.p
        r = a
        while p[r] != r:
            r = p[r]
        while p[a] != r:
            p[a], a = r, p[a]
        return r

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[max(ra, rb)] = min(ra, rb)

    def roots(self):
        return np.array([self.find(i) for i in range(len(self.p))])


# ------------------------------------------------------------------ 1. the Z source surface
CREASE_COS = 0.5     # a Z slab's sheets meet its wall at a crease sharper than 60 degrees


def z_sheets(g, k):
    """face classes of a Z slab (+1 outer, -1 inner, 0 wall). A Z slab's outer and inner sheets have separate vertices, joined by a
    wall standing ~90 degrees off them. Per vertex: the area-weighted sign of (face normal . direction away from the nearest bones)
    over its sheet-like faces (|dot| > 0.5; the wall faces are ~0); a face is a sheet face when its three vertices agree."""
    v, f = g.V0[k]
    t = trimesh.Trimesh(v, f, process=False)
    c = t.triangles_center
    fn = t.face_normals
    # sheet face: the slab's other sheet right behind it (Q353's test); a wall face looks along the slab
    loc, ri, _ = trimesh.ray.ray_triangle.RayMeshIntersector(t).intersects_location(c - fn * 0.02, -fn, multiple_hits=False)
    hit = np.full(len(f), np.inf)
    hit[ri] = np.linalg.norm(loc - (c[ri] - fn[ri] * 0.02), axis=1)
    sheet = (hit > 0.8) & (hit < Q.SHEET_MAX)
    # outward: horizontally away from the trunk's bone axis at that height (the nearest bones mislead over the abdomen)
    ax = trunk_axis(g)
    yy = np.clip(np.round(c[:, 1] / 10.0).astype(int), min(ax), max(ax))
    a0 = np.array([ax[y] for y in yy])
    u = c - a0; u[:, 1] = 0
    u /= np.linalg.norm(u, axis=1, keepdims=True) + 1e-12
    dot = (fn * u).sum(1)
    w = t.area_faces * np.sign(dot) * sheet
    s = np.zeros(len(v))
    for j in range(3):
        np.add.at(s, f[:, j], w)
    vo = s > 0
    cls = np.where(vo[f].all(1), 1, np.where((~vo[f]).all(1), -1, 0))
    # the sheets are two connected discs once the wall is left out: each connected piece of sheet faces takes its area majority
    from scipy.sparse.csgraph import connected_components
    adj = t.face_adjacency
    m = (cls[adj[:, 0]] != 0) & (cls[adj[:, 1]] != 0)
    A = sparse.coo_matrix((np.ones(int(m.sum())), (adj[m, 0], adj[m, 1])), shape=(len(f), len(f)))
    _, lab = connected_components(A, directed=False)
    for c_ in np.unique(lab[cls != 0]):
        s_ = (lab == c_) & (cls != 0)
        cls[s_] = 1 if (t.area_faces[s_] * cls[s_]).sum() > 0 else -1
    return cls


_AXIS = {}


def trunk_axis(g):
    """per 10 mm of height: the centroid (x, z) of the trunk bones (|x| < 120 mm) -> {y/10: (x, y, z)}"""
    if id(g) not in _AXIS:
        P = g.interior[np.abs(g.interior[:, 0]) < 120]
        out = {}
        for y in range(int(P[:, 1].min() // 10), int(P[:, 1].max() // 10) + 1):
            s = np.abs(P[:, 1] - 10 * y) < 25
            if s.sum() > 50:
                out[y] = np.array([P[s, 0].mean(), 10.0 * y, P[s, 2].mean()])
        _AXIS[id(g)] = out
    return _AXIS[id(g)]


def source_surface(gm, gf, chest, log):
    """merge the outer sheets of the chest regions (Base · Male = Z topology) into one surface; lock the vertices shared with an
    unchanged region (same vertex count on both pages) at that region's Base · Female vertex"""
    V, F, L, own = [], [], [], []
    n0 = 0
    for i, k in enumerate(chest):
        cls = z_sheets(gm, k)
        v, f = gm.V0[k]
        fo = f[cls == 1]
        V.append(v); F.append(fo + n0); L.append(np.full(len(fo), i)); own += [i] * len(v); n0 += len(v)
    V = np.vstack(V); F = np.vstack(F); L = np.concatenate(L); own = np.array(own)
    uf = UF(len(V))
    for a, b in sorted(cKDTree(V).query_pairs(WELD_MM)):
        uf.union(a, b)
    # the Z source's own cracks: border vertices of two regions up to CRACK_MM apart (the engine's rim join / snap closes these on
    # the page) are one vertex here -- mutually nearest pairs only
    r = uf.roots()
    e0, c0 = np.unique(edges_of(r[F]), axis=0, return_counts=True)
    bv = np.unique(e0[c0 == 1])
    bv = bv[np.isin(bv, np.unique(r[F]))]
    cracks = 0
    if len(bv):
        tb = cKDTree(V[bv])
        d1, j1 = tb.query(V[bv], k=2)
        for x, (dd, jj) in enumerate(zip(d1[:, 1], j1[:, 1])):
            if dd <= CRACK_MM and own[bv[x]] != own[bv[jj]] and j1[jj, 1] == x and x < jj:
                uf.union(int(bv[x]), int(bv[jj])); cracks += 1
    r = uf.roots()
    used = np.unique(r[F])
    remap = -np.ones(len(V), int); remap[used] = np.arange(len(used))
    Fm = remap[r[F]]
    ok = (Fm[:, 0] != Fm[:, 1]) & (Fm[:, 1] != Fm[:, 2]) & (Fm[:, 0] != Fm[:, 2])
    Fm, L = Fm[ok], L[ok]
    Vm = np.zeros((len(used), 3))
    s_ = remap[r] >= 0
    np.add.at(Vm, remap[r][s_], V[s_]); cnt = np.bincount(remap[r][s_], minlength=len(used)); Vm /= cnt[:, None]
    e, c = np.unique(edges_of(Fm), axis=0, return_counts=True)
    assert (c <= 2).all(), f"merged Z outer surface is not manifold ({int((c > 2).sum())} edges)"
    # fixed neighbours: skin regions with identical vertex count on both pages (Z topology kept), not in the chest set
    fixed = [k for k in gf.M if gf.sys[k] == "skin" and k not in chest and k in gm.M and gm.M[k]["vc"] == gf.M[k]["vc"]]
    PV, PF, PO = [], [], []
    EM, EF, EO = [], [], []
    lo, hi = Vm.min(0) - 2, Vm.max(0) + 2
    for k in fixed:
        vm, fk = gm.V0[k]
        s = np.all((vm >= lo) & (vm <= hi), axis=1)
        if s.any():
            outer_v = np.zeros(len(vm), bool); outer_v[np.unique(fk[z_sheets(gm, k) == 1])] = True
            PV.append(vm[s]); PF.append(gf.V0[k][0][s]); PO += [k] * int(s.sum())
            ek = np.unique(edges_of(fk), axis=0)
            ek = ek[(s & outer_v)[ek].all(1)]          # an outer-sheet edge of the neighbour (T-junctions)
            EM.append(vm[ek]); EF.append(gf.V0[k][0][ek]); EO += [k] * len(ek)
    PV, PF = np.vstack(PV), np.vstack(PF); PO = np.array(PO)
    EM, EF, EO = np.vstack(EM), np.vstack(EF), np.array(EO)
    d, j = cKDTree(PV).query(Vm, distance_upper_bound=WELD_MM)
    bd = e[c == 1]
    onb = np.zeros(len(Vm), bool); onb[bd.ravel()] = True
    lock = np.isfinite(d) & onb          # only the border of the merged surface is shared with a neighbour (an interior vertex that
    #                                      happens to touch another region -- the arm skin in the axilla -- is not a border)
    tgt = np.full((len(Vm), 3), np.nan)
    tl = cKDTree(PV).query_ball_point(Vm[lock], WELD_MM)
    tgt[lock] = np.array([PF[x].mean(0) for x in tl])
    neigh = {k for x in tl for k in PO[x]}
    # a border vertex lying on a neighbour's edge (a T-junction of the Z source, within TJ_MM): locked at the same point of that
    # edge on the Base · Female page
    tj = 0
    for i in np.where(onb & ~lock)[0]:
        A_, B_ = EM[:, 0], EM[:, 1]
        ab = B_ - A_
        t_ = np.clip(((Vm[i] - A_) * ab).sum(1) / np.maximum((ab * ab).sum(1), 1e-12), 0, 1)
        dd = np.linalg.norm(A_ + t_[:, None] * ab - Vm[i], axis=1)
        m = int(np.argmin(dd))
        if dd[m] <= TJ_MM:
            lock[i] = True; tj += 1
            tgt[i] = EF[m, 0] + t_[m] * (EF[m, 1] - EF[m, 0]); neigh.add(EO[m])
    neigh = sorted(neigh)
    # what is left of the border is a small hole inside the chest set (a Z crack loop): filled with a fan of faces
    lock_edge = bd[lock[bd[:, 0]] & lock[bd[:, 1]]]
    free_b = bd[~(lock[bd[:, 0]] & lock[bd[:, 1]])]
    Fm, L, filled = fill_holes(Vm, Fm, L, free_b, lock)
    e, c = np.unique(edges_of(Fm), axis=0, return_counts=True)
    assert (c <= 2).all(), "hole filling made the surface non-manifold"
    bd2 = e[c == 1]
    open_free = bd2[~(lock[bd2[:, 0]] & lock[bd2[:, 1]])]
    log(f"  source: {len(chest)} Z regions -> merged outer surface {len(Vm)} vertices / {len(Fm)} faces ({cracks} Z cracks <= "
        f"{CRACK_MM} mm joined, {filled} hole faces added); {int(lock.sum())} border vertices locked ({tj} on a neighbour's edge; "
        f"{len(neigh)} unchanged regions); border {len(bd2)} edges, {len(open_free)} of them not on a neighbour")
    return dict(V=Vm, F=Fm, L=L, lock=lock, lock_tgt=tgt, lock_edges=lock_edge, fixed=fixed, neighbours=neigh,
                boundary_edges=int(len(bd2)), open_border_edges=int(len(open_free)), z_cracks_joined=cracks,
                hole_faces_added=filled, t_junction_locks=tj)


def fill_holes(V, F, L, bedges, lock, max_edges=8):
    """small closed border loops made only of free (not shared) edges: a fan from their centroid vertex-free (ear clipping on
    the loop itself, no vertex added); the label of the most common neighbouring face"""
    from collections import defaultdict
    nb = defaultdict(list)
    for a, b in bedges.tolist():
        nb[a].append(b); nb[b].append(a)
    seen, added = set(), 0
    Fn, Ln = [F], [L]
    vf = defaultdict(list)
    for fi, t in enumerate(F.tolist()):
        for v in t:
            vf[v].append(fi)
    for s in list(nb):
        if s in seen or len(nb[s]) != 2:
            continue
        loop, prev, cur = [s], None, s
        while True:
            nx = [x for x in nb[cur] if x != prev]
            if not nx or len(nb[cur]) != 2:
                loop = None; break
            prev, cur = cur, nx[0]
            if cur == s:
                break
            loop.append(cur)
            if len(loop) > max_edges:
                loop = None; break
        if not loop:
            continue
        seen.update(loop)
        if len(loop) < 3:
            continue
        # orientation: follow the winding of the face along the first loop edge (the new face runs the edge the other way)
        a, b = loop[0], loop[1]
        fa = [fi for fi in vf[a] if b in F[fi]]
        t = F[fa[0]].tolist(); ia = t.index(a)
        same = t[(ia + 1) % 3] == b
        lab = np.bincount(L[[fi for v in loop for fi in vf[v]]]).argmax()
        ring = loop if not same else loop[::-1]
        for k in range(1, len(ring) - 1):
            Fn.append(np.array([[ring[0], ring[k], ring[k + 1]]])); Ln.append(np.array([lab])); added += 1
    return np.vstack(Fn), np.concatenate(Ln), added


def frame_map(gm, gf, S, chest, log):
    """Base · Male -> Base · Female frame: thin-plate spline through the displacements of the unchanged skin regions and the trunk /
    shoulder bones (identical topology on both pages) near the chest; locked vertices exactly"""
    lo, hi = S["V"].min(0) - 120, S["V"].max(0) + 120
    P, Dd = [], []
    for k in sorted(gf.M):
        if k in chest or k not in gm.M or gm.M[k]["vc"] != gf.M[k]["vc"] or gf.sys[k] not in ("skin", "bone", "cartilage"):
            continue
        vm, vf = gm.V0[k][0], gf.V0[k][0]
        s = np.all((vm >= lo) & (vm <= hi), axis=1)
        if s.sum() < 3:
            continue
        P.append(vm[s]); Dd.append(vf[s] - vm[s])
    P, Dd = np.vstack(P), np.vstack(Dd)
    # one sample per 4 mm cell (deterministic), then a fixed stride down to RBF_N
    cell = np.floor(P / 4.0).astype(np.int64)
    _, first = np.unique(cell, axis=0, return_index=True)
    first = np.sort(first)
    if len(first) > RBF_N:
        first = first[np.linspace(0, len(first) - 1, RBF_N).astype(int)]
    lk = S["lock"]
    Ps = np.vstack([P[first], S["V"][lk]]); Ds = np.vstack([Dd[first], S["lock_tgt"][lk] - S["V"][lk]])
    Ps, ui = np.unique(np.round(Ps, 3), axis=0, return_index=True); Ds = Ds[ui]
    rbf = RBFInterpolator(Ps, Ds, kernel="thin_plate_spline", smoothing=1.0, degree=1)
    X = S["V"] + rbf(S["V"])
    # how well the spline reproduces the locked (exact) vertices; the rest of that residual is spread harmonically over the surface
    R = S["lock_tgt"][lk] - X[lk]
    res = np.linalg.norm(R, axis=1)
    Lp, _ = laplacian(len(X), S["F"])
    free = ~lk
    A = Lp.tocsr()
    Dh = np.zeros_like(X); Dh[lk] = R
    for c in range(3):
        Dh[free, c] = spsolve(A[free][:, free].tocsc(), -(A[free][:, lk] @ R[:, c]))
    X = X + Dh
    X[lk] = S["lock_tgt"][lk]
    log(f"  frame: spline through {len(Ps)} samples (of {len(P)} + {int(lk.sum())} locked); at the locked vertices residual median "
        f"{np.median(res):.2f} / max {res.max():.2f} mm, spread harmonically (max {np.linalg.norm(Dh[free], axis=1).max():.2f} mm)")
    return X, {"samples": int(len(Ps)), "of": int(len(P)), "locked_residual_mm": st(res)}


# ------------------------------------------------------------------ 3. conforming longest-edge bisection
def refine(V, F, L, lock_edges, hmax=EDGE_MM, iters=12):
    V = V.copy(); F = F.copy(); L = L.copy()
    locked = set(map(tuple, np.sort(lock_edges, axis=1).tolist()))
    for _ in range(iters):
        E, inv = np.unique(np.sort(np.stack([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]], 1), axis=2).reshape(-1, 2), axis=0,
                           return_inverse=True)
        FE = inv.reshape(-1, 3)
        ln = np.linalg.norm(V[E[:, 0]] - V[E[:, 1]], axis=1)
        lk = np.array([tuple(e) in locked for e in E.tolist()]) if locked else np.zeros(len(E), bool)
        # graded size near a long unsplit (locked) border edge: a face there may keep edges up to ~0.7 x that edge, shrinking by half
        # a millimetre per millimetre away from it -- else bisection leaves a fan of ever thinner slivers along the edge
        h = np.full(len(F), float(hmax))
        if len(lock_edges):
            Lk = np.linalg.norm(V[lock_edges[:, 0]] - V[lock_edges[:, 1]], axis=1)
            sel = Lk > hmax
            if sel.any():
                A_, B_ = V[lock_edges[sel, 0]], V[lock_edges[sel, 1]]
                c = V[F].mean(1)
                for a_, b_, l_ in zip(A_, B_, Lk[sel]):
                    ab = b_ - a_
                    t_ = np.clip(((c - a_) @ ab) / (ab @ ab), 0, 1)
                    dd = np.linalg.norm(a_ + t_[:, None] * ab - c, axis=1)
                    h = np.maximum(h, GRADE * l_ - 0.5 * dd)
        hreq = np.full(len(E), np.inf)
        np.minimum.at(hreq, FE.ravel(), np.repeat(h, 3))
        mark = (ln > hreq) & ~lk
        if not mark.any():
            break
        lnu = np.where(lk[FE], -1.0, ln[FE])
        lu = FE[np.arange(len(F)), lnu.argmax(1)]
        has_u = lnu.max(1) > 0
        while True:     # closure: a face with a marked edge has its longest unlocked edge marked
            need = mark[FE].any(1) & has_u & ~mark[lu]
            if not need.any():
                break
            mark[lu[need]] = True
        mid = -np.ones(len(E), int)
        mi = np.where(mark)[0]
        mid[mi] = len(V) + np.arange(len(mi))
        V = np.vstack([V, 0.5 * (V[E[mi, 0]] + V[E[mi, 1]])])
        newF, newL = [], []
        emid = {}
        for e_i in mi:
            emid[(int(E[e_i, 0]), int(E[e_i, 1]))] = int(mid[e_i])

        def m_of(a, b):
            return emid.get((a, b) if a < b else (b, a))

        def split(tri, lab):
            a, b, c = tri
            best, bl = None, -1.0
            for (x, y, z) in ((a, b, c), (b, c, a), (c, a, b)):
                m = m_of(x, y)
                if m is not None:
                    l2 = float(((V[x] - V[y]) ** 2).sum())
                    if l2 > bl:
                        best, bl = (x, y, z, m), l2
            if best is None:
                newF.append(tri); newL.append(lab)
                return
            x, y, z, m = best
            split((x, m, z), lab)
            split((m, y, z), lab)
        sel = mark[FE].any(1)
        for t, lab in zip(F[~sel].tolist(), L[~sel].tolist()):
            newF.append(tuple(t)); newL.append(lab)
        for t, lab in zip(F[sel].tolist(), L[sel].tolist()):
            split(tuple(t), lab)
        F = np.array(newF, int); L = np.array(newL, int)
    return V, F, L


def delaunay_flips(V, F, L, max_pass=60):
    """Lawson edge flips (an interior edge whose two opposite angles sum to more than 180 degrees is flipped), never across a region
    border (the labels keep their outline) and never into a fold: the fans of slivers that a long, unsplit border edge leaves in
    the bisection become well-shaped triangles (one triangle per such edge keeps it). Vertex positions and count unchanged."""
    F = F.copy()
    nflip = 0
    for _ in range(max_pass):
        t = trimesh.Trimesh(V, F, process=False)
        adj = t.face_adjacency
        if not len(adj):
            break
        f0, f1 = adj[:, 0], adj[:, 1]
        same = L[f0] == L[f1]
        # face0 written (a, b, o0) with a -> b the shared edge in its winding
        o0 = np.array([[x for x in F[i] if x not in e][0] if len(set(F[i]) - set(e)) == 1 else -1
                       for i, e in zip(f0.tolist(), t.face_adjacency_edges.tolist())])
        o1 = np.array([[x for x in F[i] if x not in e][0] if len(set(F[i]) - set(e)) == 1 else -1
                       for i, e in zip(f1.tolist(), t.face_adjacency_edges.tolist())])
        ia = np.argmax(F[f0] == o0[:, None], axis=1)
        a = F[f0, (ia + 1) % 3]; b = F[f0, (ia + 2) % 3]

        def ang(o, p_, q_):
            u = V[p_] - V[o]; w = V[q_] - V[o]
            c = (u * w).sum(1) / np.maximum(np.linalg.norm(u, axis=1) * np.linalg.norm(w, axis=1), 1e-12)
            return np.arccos(np.clip(c, -1, 1))
        exc = ang(o0, a, b) + ang(o1, a, b) - np.pi
        n0 = fnormals(V, np.stack([o0, a, o1], 1)); n1 = fnormals(V, np.stack([o0, o1, b], 1))
        cr = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])      # area-weighted: a degenerate face does not vote
        nold = cr[f0] + cr[f1]; nold /= np.maximum(np.linalg.norm(nold, axis=1, keepdims=True), 1e-12)
        ok = same & (exc > 1e-3) & ((n0 * nold).sum(1) > 0.5) & ((n1 * nold).sum(1) > 0.5) & (o0 >= 0) & (o1 >= 0)
        if not ok.any():
            break
        ex = set(map(tuple, np.sort(edges_of(F), axis=1).tolist()))
        used = np.zeros(len(F), bool)
        did = 0
        for i in np.where(ok)[0][np.argsort(-exc[ok])]:
            if used[f0[i]] or used[f1[i]] or tuple(sorted((int(o0[i]), int(o1[i])))) in ex:
                continue
            F[f0[i]] = [o0[i], a[i], o1[i]]; F[f1[i]] = [o0[i], o1[i], b[i]]
            used[f0[i]] = used[f1[i]] = True
            ex.add(tuple(sorted((int(o0[i]), int(o1[i])))))
            did += 1
        nflip += did
        if not did:
            break
    return F, nflip


# ------------------------------------------------------------------ 4. the target: the current outer sheets
class Target:
    """the current chest slabs (all their faces), sampled every SAMPLE_MM, with face normals. No sheet classification is trusted
    (on these refitted slabs the ray / bone classifiers disagree on thousands of faces): a point follows the nearest sample whose
    face normal agrees with its own (within FACE_COS) -- on a closed, outward-wound slab that is the outer sheet, never the inner
    sheet (normals opposite) nor the wall / rounded rim (normals turned away). Rim points: vertices where neighbouring faces of a
    current slab turn by more than 45 degrees (its rounded or creased border)."""

    def __init__(self, g, chest):
        P, N, O, OU = [], [], [], []
        rims = []
        self.tri = {}
        for i, k in enumerate(chest):
            v, f = g.V0[k]
            t = trimesh.Trimesh(v, f, process=False)
            self.tri[k] = t
            fn = fnormals(v, f)
            cls, _ = g.sheets(k)        # Q353's classification: only used to find the surface in the first, far rounds
            adj = t.face_adjacency
            dd = (fn[adj[:, 0]] * fn[adj[:, 1]]).sum(1)
            rv = np.unique(t.face_adjacency_edges[dd < np.cos(np.radians(45))])
            rims.append(v[rv])
            A, Bv, Cv = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
            lmax = np.max(np.stack([np.linalg.norm(A - Bv, axis=1), np.linalg.norm(Bv - Cv, axis=1),
                                    np.linalg.norm(Cv - A, axis=1)], 1), 1)
            nsub = np.clip(np.ceil(lmax / SAMPLE_MM).astype(int), 1, 40)
            for ns in np.unique(nsub):
                sel = np.where(nsub == ns)[0]
                uu, vv = np.meshgrid(np.arange(ns + 1), np.arange(ns + 1))
                m = (uu + vv) <= ns
                bu, bv = uu[m] / ns, vv[m] / ns
                pts = (A[sel, None] * (1 - bu - bv)[None, :, None] + Bv[sel, None] * bu[None, :, None]
                       + Cv[sel, None] * bv[None, :, None]).reshape(-1, 3)
                P.append(pts.astype(np.float32)); N.append(np.repeat(fn[sel], len(bu), 0).astype(np.float32))
                O.append(np.full(len(pts), i, np.int16)); OU.append(np.repeat(cls[sel] == 1, len(bu)))
        self.outer = np.concatenate(OU)
        self.P = np.vstack(P).astype(float); self.N = np.vstack(N).astype(float); self.O = np.concatenate(O)
        self.rimpts = rims
        allrim = np.vstack([r for r in rims if len(r)])
        self.drim = cKDTree(allrim).query(self.P)[0]            # distance from ANY current border (for the band weight)
        own_d = np.full(len(self.P), np.inf)
        for i, r in enumerate(rims):
            s_ = self.O == i
            if len(r):
                own_d[s_] = cKDTree(r).query(self.P[s_])[0]
        self.core = own_d > RIM_EXCL
        self.ci = np.where(self.core)[0]
        self.tree = cKDTree(self.P[self.core])
        self.per = {i: (cKDTree(self.P[self.core & (self.O == i)]), np.where(self.core & (self.O == i))[0])
                    for i in range(len(chest)) if (self.core & (self.O == i)).any()}
        self.all_tree = cKDTree(self.P)
        self.oi = np.where(self.core & self.outer)[0]
        self.otree = cKDTree(self.P[self.oi])
        self.folded = 0
        self.cos = FACE_COS

    def _agree(self, tree, idx, X, U, k=32, ub=np.inf):
        """per point: the nearest sample (of tree / idx) whose normal agrees with U; -1 if none among the k nearest"""
        d, j = tree.query(X, k=k, distance_upper_bound=ub)
        okd = np.isfinite(d)
        jj = np.where(okd, j, 0)
        g = idx[np.minimum(jj, len(idx) - 1)]
        agree = okd & ((self.N[g] * U[:, None, :]).sum(2) > self.cos)
        first = np.where(agree.any(1), agree.argmax(1), -1)
        out = np.where(first >= 0, g[np.arange(len(X)), np.maximum(first, 0)], -1)
        return out

    def closest(self, X, U, far=False):
        if far:          # first rounds: the nearest sample of the (classified) outer sheets, no normal test
            _, j = self.otree.query(X)
            j = self.oi[j]
            n = self.N[j]
            return X - ((X - self.P[j]) * n).sum(1)[:, None] * n, n, j, np.ones(len(X), bool)
        j = self._agree(self.tree, self.ci, X, U)
        ok = j >= 0
        jj = np.maximum(j, 0)
        n = self.N[jj]
        q = X - ((X - self.P[jj]) * n).sum(1)[:, None] * n
        q[~ok] = X[~ok]
        return q, n, jj, ok

    def stacked(self, X, U):
        """per point: the current pieces it lies over / under (sideways offset < TANG_MAX, normal agreeing), their heights along U;
        the outermost within OVL_MM of the nearest -> target, else nan"""
        cols = sorted(self.per)
        H = np.full((len(X), len(cols)), np.nan)
        J = np.full((len(X), len(cols)), -1)
        for c, i in enumerate(cols):
            tr, idx = self.per[i]
            jj = self._agree(tr, idx, X, U, k=16, ub=PLAUS_MM)
            o = np.where(jj >= 0)[0]
            jj = jj[o]
            n = self.N[jj]
            off = X[o] - self.P[jj]
            h = (off * n).sum(1)
            tang = np.linalg.norm(off - h[:, None] * n, axis=1)
            hh = -h / np.maximum((n * U[o]).sum(1), 0.3)
            good = (tang < TANG_MAX) & (np.abs(hh) <= OVL_MM + 2.0)
            H[o[good], c] = hh[good]; J[o[good], c] = jj[good]
        tgt = np.full((len(X), 3), np.nan)
        nn = np.full((len(X), 3), np.nan)
        stacked = np.zeros(len(X), bool)
        for i in np.where(np.isfinite(H).any(1))[0]:
            h = H[i]; c = np.where(np.isfinite(h))[0]
            h0 = h[c][np.argmin(np.abs(h[c]))]
            win = c[(h[c] >= h0 - 1e-9) & (h[c] <= h0 + OVL_MM)]
            cc = win[np.argmax(h[win])]
            stacked[i] = len(c) > 1
            tgt[i] = X[i] + h[cc] * U[i]
            nn[i] = self.N[J[i, cc]]
        return tgt, nn, stacked

    def dist(self, X, U=None):
        """distance to the current outer surface: the nearest sample (rims included) whose normal agrees with U (outer-facing), its
        sideways part, and that sample's distance from a current border"""
        if U is None:
            _, j = self.all_tree.query(X)
        else:
            j = self._agree(self.all_tree, np.arange(len(self.P)), X, U, k=48)
            bad = j < 0
            if bad.any():
                j[bad] = self.all_tree.query(X[bad])[1]
        n = self.N[j]
        off = X - self.P[j]
        h = (off * n).sum(1)
        tang = np.linalg.norm(off - h[:, None] * n, axis=1)
        return np.abs(h), tang, self.drim[j]


P2P = 0.05          # share of the point-to-point term next to the point-to-plane one (keeps the system well posed tangentially)


def solve_p2plane(Lp, deg, wl, Dt, nq, lock, Dlock, free):
    """min  sum_edges |D_i - D_j|^2 + sum_i wl_i deg_i [ ((D_i - Dt_i) . n_i)^2 + P2P |D_i - Dt_i|^2 ],  D = Dlock on the locked
    vertices (3n x 3n sparse system: the displacement is smooth; the data pulls along the target normal, so vertices are not dragged
    sideways into a concavity)"""
    n = len(Dt)
    I3 = sparse.identity(3, format="csr")
    K = sparse.kron(Lp, I3, format="csr")
    a = wl * deg
    rows = np.repeat(np.arange(n) * 3, 9) + np.tile(np.repeat(np.arange(3), 3), n)
    cols = np.repeat(np.arange(n) * 3, 9) + np.tile(np.tile(np.arange(3), 3), n)
    blk = a[:, None, None] * (nq[:, :, None] * nq[:, None, :] + P2P * np.eye(3)[None])
    Wm = sparse.coo_matrix((blk.ravel(), (rows, cols)), shape=(3 * n, 3 * n)).tocsr()
    rhs = np.einsum("nij,nj->ni", blk, Dt).ravel()
    A = (K + Wm).tocsr()
    fi = (np.where(free)[0][:, None] * 3 + np.arange(3)).ravel()
    li = (np.where(lock)[0][:, None] * 3 + np.arange(3)).ravel()
    D = np.zeros(3 * n)
    D[li] = Dlock[lock].ravel()
    D[fi] = spsolve(A[fi][:, fi].tocsc(), rhs[fi] - A[fi][:, li] @ D[li])
    return D.reshape(n, 3)


def fit(X0, F, lock, tgt_lock, T: Target, log):
    """membrane-regularised non-rigid ICP: displacement D smooth over the merged surface (graph Laplacian), data term = closest point
    on the current core sheets (weight faded near the current borders), locked vertices exact; stiff -> soft"""
    n = len(X0)
    Lp, deg = laplacian(n, F)
    X = X0.copy()
    free = ~lock
    hist = []
    snaps = []
    # where a locked border vertex (an unchanged neighbour's vertex) lies off the current surface, the pieces disagree there: no data
    # within LOCK_REACH x that gap of it, so the surface bridges from the neighbour to the current surface instead of folding back
    lock = lock.copy()
    li = np.where(lock)[0]
    U0 = vnormals(X0, F)
    gap = T.dist(tgt_lock[li], U0[li])[0] if len(li) else np.zeros(0)
    rel = li[gap > LOCK_GAP_MAX]           # the pieces disagree too much to join here (the right axilla); the neighbour follows
    lock[rel] = False                      # the chest skin there instead (neighbour_follow)
    free = ~lock
    fit.released = rel
    keep = gap <= LOCK_GAP_MAX
    li, gap = li[keep], gap[keep]
    dis = li[gap > 0.5]
    wl = np.ones(n)
    if len(dis):
        dd, jj = cKDTree(X0[dis]).query(X0, k=min(8, len(dis)))
        dd = dd.reshape(n, -1); jj = jj.reshape(n, -1)
        reach = np.clip(LOCK_REACH * gap[gap > 0.5][jj], LOCK_REACH_MIN, LOCK_REACH_MAX)
        wl = np.min(smoothstep(dd / reach), axis=1)
    fit.lock_gap = gap
    rim_all = np.vstack([r_ for r_ in T.rimpts if len(r_)])
    rim_tree = cKDTree(rim_all)
    for r, lam in enumerate(STIFF):
        U = vnormals(X, F)
        if r < len(STIFF) - 2:
            q, nq, j, okc = T.closest(X, U, far=r < FAR_ROUNDS)
            w = smoothstep((T.drim[j] - BAND_IN) / (BAND_OUT - BAND_IN)) * okc
            if r >= 3:
                w = w * (np.linalg.norm(q - X, axis=1) < PLAUS_MM)
            stacked = np.zeros(n, bool)
        else:
            q, nq, stacked = T.stacked(X, U)
            ok = np.isfinite(q[:, 0])
            q2, nq2, j, _ = T.closest(X, U)
            nq = np.where(ok[:, None], nq, nq2)
            _, j_all = T.all_tree.query(np.where(ok[:, None], q, q2))
            w = np.where(ok, smoothstep((T.drim[j_all] - BAND_IN) / (BAND_OUT - BAND_IN)), 0.0)
            q = np.where(ok[:, None], q, X)
        w = w * wl
        if RIM_PULL and len(rel) and r >= FAR_ROUNDS:
            # a released border vertex (its neighbour lies > LOCK_GAP_MAX off the current surface) goes to the current pieces'
            # own border there: the chest skin keeps covering what it covers today (it lies over the neighbour's edge)
            _, jr = rim_tree.query(X[rel])
            q[rel] = rim_all[jr]
            dv = q[rel] - X[rel]
            nq[rel] = dv / np.maximum(np.linalg.norm(dv, axis=1, keepdims=True), 1e-9)
            w[rel] = 1.0
        Dt = q - X
        D = solve_p2plane(Lp, deg, lam * w, Dt, nq, lock, tgt_lock - X, free)
        X = X + D
        snaps.append(X.copy())
        res = np.linalg.norm(q - X, axis=1)[w > 0.5]
        hist.append({"round": r, "data_weight": lam, "move_max_mm": round(float(np.linalg.norm(D, axis=1).max()), 2),
                     "residual_where_weighted_p95_mm": round(float(np.percentile(res, 95)), 3) if len(res) else None,
                     "weighted_vertices": int((w > 0.5).sum()), "stacked_vertices": int(stacked.sum())})
        log(f"    round {r}: weight {lam:g}  move max {hist[-1]['move_max_mm']} mm  residual p95 {hist[-1]['residual_where_weighted_p95_mm']}")
    fit.snaps = snaps
    T.cos = FACE_COS
    return X, hist, lock


# ------------------------------------------------------------------ 5. slabs
def slab(outer_v, inner_v, fo):
    """closed slab from an outer sheet (faces fo, outward) and per-vertex inner positions: inner sheet reversed + rim wall
    (as scripts/anatomy/q358/perineum_skin_q358.py slab)"""
    used = np.unique(fo)
    remap = -np.ones(len(outer_v), int); remap[used] = np.arange(len(used))
    po, pi = outer_v[used], inner_v[used]
    f = remap[fo]; nv = len(po)
    e = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
    key = np.sort(e, axis=1)
    _, inv, cnt = np.unique(key, axis=0, return_inverse=True, return_counts=True)
    bd = e[cnt[inv.ravel()] == 1]
    walls = []
    for a, b in bd:
        walls += [[b, a, a + nv], [b, a + nv, b + nv]]
    Fs = np.vstack([f, f[:, ::-1] + nv] + ([np.array(walls, int)] if walls else []))
    cls = np.r_[np.ones(len(f), int), -np.ones(len(f), int), np.zeros(len(walls), int)]
    return np.vstack([po, pi]), Fs, used, cls


def z_thickness(gm, chest):
    out = {}
    for k in chest:
        cls = z_sheets(gm, k)
        v, f = gm.V0[k]
        to = trimesh.Trimesh(v, f[cls == 1], process=False)
        vi = np.unique(f[cls == -1])
        _, d, _ = trimesh.proximity.closest_point(to, v[vi])
        out[k] = float(np.median(d))
    return out


def inner_of(X, F, lock, S, gf, gm, thick):
    """inner sheet: THICK under the merged outer surface along its normal; a locked vertex takes the inner border vertex of its
    unchanged neighbour (the exact partner of the Z slab)"""
    Nn = vnormals(X, F)
    Y = X - thick * Nn
    li = np.where(lock)[0]
    if len(li):
        # the unchanged neighbours' inner-sheet vertices near the locked ones
        PV = []
        for k in S["neighbours"]:
            cls, _ = gf.sheets(k)
            v, f = gf.V0[k]
            PV.append(v[np.unique(f[cls == -1])])
        PV = np.vstack(PV)
        d, j = cKDTree(PV).query(X[li] - thick * Nn[li], distance_upper_bound=thick)
        ok = np.isfinite(d)
        Y[li[ok]] = PV[j[ok]]
        return Y, {"locked": int(len(li)), "inner_partner_found": int(ok.sum()), "partner_offset_mm": st(d[ok])}
    return Y, {"locked": 0}


# ------------------------------------------------------------------ 6. measurements
def weld_stats(pieces, focus, others_box=None):
    """Python copy of the Q334 weld rules (viewer/zan_atlas.template.html, Q334 weld): per focus piece, its rim vertices (a vertex
    with an incident face more than ~45 degrees off its normal) and how many of them are joined to another skin piece -- exactly
    (within WELD 0.03 mm) or by the rim join (mutually nearest rim vertex of another piece within 1 mm and 0.67 x the shortest edge,
    normals not opposed)"""
    ids = list(pieces)
    P, OW, NR, RIM, ME = [], [], [], [], []
    for i, k in enumerate(ids):
        v, f = pieces[k]
        n = vnormals(v, f)
        fn = fnormals(v, f)
        rim = np.zeros(len(v), bool)
        for c in range(3):
            d = (fn * n[f[:, c]]).sum(1)
            rim[f[d < 0.7, c]] = True
        me = np.full(len(v), 1e9)
        for a, b in ((0, 1), (1, 2), (2, 0)):
            le = np.linalg.norm(v[f[:, a]] - v[f[:, b]], axis=1)
            np.minimum.at(me, f[:, a], le); np.minimum.at(me, f[:, b], le)
        P.append(v); OW.append(np.full(len(v), i)); NR.append(n); RIM.append(rim); ME.append(me)
    P = np.vstack(P); OW = np.concatenate(OW); NR = np.vstack(NR); RIM = np.concatenate(RIM); ME = np.concatenate(ME)
    tr = cKDTree(P)
    welded = np.zeros(len(P), bool)
    pr = tr.query_pairs(WELD_MM, output_type="ndarray")
    if len(pr):
        x = pr[OW[pr[:, 0]] != OW[pr[:, 1]]]
        welded[x[:, 0]] = welded[x[:, 1]] = True
    # rim join among rim vertices not yet welded
    RL = np.where(RIM & ~welded)[0]
    rj = np.zeros(len(P), bool)
    if len(RL):
        t2 = cKDTree(P[RL])
        pr = t2.query_pairs(1.0, output_type="ndarray")
        if len(pr):
            u, v = RL[pr[:, 0]], RL[pr[:, 1]]
            dd = ((P[u] - P[v]) ** 2).sum(1)
            ok = (OW[u] != OW[v]) & (dd < 1.0) & (dd <= 0.45 * ME[u] ** 2) & (dd <= 0.45 * ME[v] ** 2) & ((NR[u] * NR[v]).sum(1) >= 0)
            u, v, dd = u[ok], v[ok], dd[ok]
            best = {}
            for a, b, d_ in zip(u.tolist(), v.tolist(), dd.tolist()):
                for x, y in ((a, b), (b, a)):
                    if x not in best or d_ < best[x][1]:
                        best[x] = (y, d_)
            for x, (y, _) in best.items():
                if best.get(y, (None,))[0] == x:
                    rj[x] = True
    out = {}
    base = 0
    for i, k in enumerate(ids):
        n = len(pieces[k][0])
        s = slice(base, base + n); base += n
        if k in focus:
            r = RIM[s]
            out[k] = {"rim_vertices": int(r.sum()), "welded": int((r & welded[s]).sum()), "rim_joined": int((r & rj[s]).sum()),
                      "pct": round(100.0 * float((r & (welded[s] | rj[s])).sum()) / max(int(r.sum()), 1), 1)}
    return out


def raster(tris, owner, axis, sign, lo, hi, px=PX):
    """orthographic z-buffer along `axis` (looking from sign * axis): owner index of the frontmost face per pixel (-1 = none)"""
    a, b = [c for c in range(3) if c != axis]
    nx, ny = int((hi[a] - lo[a]) / px), int((hi[b] - lo[b]) / px)
    Zb = np.full((ny, nx), -1e18); O = np.full((ny, nx), -1, np.int32)
    x = (tris[:, :, a] - lo[a]) / px; y = (tris[:, :, b] - lo[b]) / px; z = sign * tris[:, :, axis]
    keep = (x.max(1) >= 0) & (x.min(1) < nx) & (y.max(1) >= 0) & (y.min(1) < ny)
    for fi in np.where(keep)[0]:
        x0, x1 = int(max(0, np.floor(x[fi].min()))), int(min(nx - 1, np.ceil(x[fi].max())))
        y0, y1 = int(max(0, np.floor(y[fi].min()))), int(min(ny - 1, np.ceil(y[fi].max())))
        if x0 > x1 or y0 > y1:
            continue
        gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
        (ax, bx, cx), (ay, by, cy) = x[fi], y[fi]
        den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
        if abs(den) < 1e-12:
            continue
        l1 = ((by - cy) * (gx - cx) + (cx - bx) * (gy - cy)) / den
        l2 = ((cy - ay) * (gx - cx) + (ax - cx) * (gy - cy)) / den
        l3 = 1 - l1 - l2
        m = (l1 >= -1e-9) & (l2 >= -1e-9) & (l3 >= -1e-9)
        if not m.any():
            continue
        zz = l1 * z[fi, 0] + l2 * z[fi, 1] + l3 * z[fi, 2]
        sub = Zb[y0:y1 + 1, x0:x1 + 1]; osub = O[y0:y1 + 1, x0:x1 + 1]
        w = m & (zz > sub)
        sub[w] = zz[w]; osub[w] = owner[fi]
    return O


def holes(g, chest, extra=None):
    """front and lateral views of the chest window: pixels where the frontmost structure is NOT skin, although skin lies all around
    (a deeper structure seen through a slot) -> count; per view"""
    lo, hi = CHEST_BOX
    ids = [k for k in g.in_box(lo, hi) if (g.sys[k] in ("skin", "muscle", "bone", "cartilage", "vessel", "nerve", "lymph") or k in BREAST)
           and not k.startswith(("fat_subcut", "soft_unlabelled"))]      # the subcutaneous fat / unlabelled soft-tissue layers lie
    #                                                                       in the skin by construction (hidden by default)
    T, O, isskin = [], [], []
    for i, k in enumerate(ids):
        v, f = (extra[k] if extra and k in extra else (g.cur[k], g.F[k]))
        c = v[f].mean(1)
        s = np.all((c >= lo) & (c <= hi), axis=1)
        T.append(v[f[s]]); O.append(np.full(int(s.sum()), i)); isskin.append(g.sys[k] == "skin")
    T = np.vstack(T); O = np.concatenate(O); isskin = np.array(isskin)
    from scipy import ndimage
    out = {}
    WIN = {0: (-200, 200), 1: (380, 640), 2: (-120, 180)}      # x, y (height: below the clavicles to the costal margin), z
    for name, axis, sign in (("front", 2, 1), ("lateral_r", 0, 1), ("lateral_l", 0, -1)):
        lo2, hi2 = lo.copy(), hi.copy()
        for c in range(3):
            if c != axis:
                lo2[c], hi2[c] = WIN[c]
        Ob = raster(T, O, axis, sign, lo2, hi2)
        sk = (Ob >= 0) & isskin[np.maximum(Ob, 0)]
        other = (Ob >= 0) & ~sk
        # a hole pixel: a non-skin structure is frontmost and skin surrounds it (enclosed in the skin mask)
        enclosed = ndimage.binary_fill_holes(sk) & ~sk
        hp = enclosed & other
        lab, nl = ndimage.label(hp)
        who = {}
        for kk in np.unique(Ob[hp]):
            who[ids[int(kk)]] = int((Ob[hp] == kk).sum())
        a_, b_ = [c for c in range(3) if c != axis]
        where = []
        for l_ in range(1, nl + 1):
            yy, xx = np.where(lab == l_)
            if len(yy) >= 20:
                c_ = np.zeros(3); c_[a_] = lo2[a_] + (xx.mean() + 0.5) * PX; c_[b_] = lo2[b_] + (yy.mean() + 0.5) * PX
                where.append({"px": int(len(yy)), "centre_mm": [round(float(x), 1) if i != axis else None for i, x in enumerate(c_)]})
        out[name] = {"hole_px": int(hp.sum()), "pieces": int(nl), "seen_through": dict(sorted(who.items(), key=lambda t: -t[1])[:8]),
                     "largest": sorted(where, key=lambda t: -t["px"])[:6], "px_mm": PX}
    return out


def outside(g, sk, keys):
    return {k: Q.outside_count(g, sk, k) for k in keys}


# ------------------------------------------------------------------ pose rig
def rig_decode(src, idx_of, nv_of, positions):
    """decoded per-vertex (segment idx (nv,3), weight (nv,3)) of skinned structures, as the viewer reconstructs them"""
    import make_pose_rig as MPR
    R = src["rig"]
    blob = zlib.decompress(base64.b64decode(src["weights_zlib_b64"]))
    ent = {e[0]: e for e in R["skin"]}
    out = {}
    for k, i in idx_of.items():
        if i not in ent:
            out[k] = None
            continue
        _, nv, K, pal, off, nc = ent[i]
        nb = (nv + 7) // 8
        ctrl = np.unpackbits(np.frombuffer(blob, np.uint8, nb, off))[:nv].astype(bool)
        assert int(ctrl.sum()) == nc
        o = off + nb
        pi = np.stack([np.frombuffer(blob, np.uint8, nc, o + kk * nc) for kk in range(K)], 1).astype(np.int64)
        o += K * nc
        qw = [np.frombuffer(blob, np.uint8, nc, o + kk * nc).astype(np.int64) for kk in range(K - 1)]
        w = np.zeros((nc, K))
        w[:, 1:] = np.stack(qw, 1) if qw else w[:, 1:]
        w[:, 0] = 255 - w[:, 1:].sum(1)
        out[k] = MPR.decode_weights(positions[k], ctrl, pal, pi, w)
    return out


def rig_transfer(src, man_old, man_new, chest, old_pos, new_geo, nseg, pool_extra=()):
    """the chest regions' weights carried from the current meshes (as the viewer reconstructs them, all 18 regions pooled) onto the
    new ones: inverse-square average of the 4 nearest old vertices, top 3; every border vertex stores its own weights (so a vertex
    shared by two regions gets the same weights in both and the border cannot open when posed); else the Q241/Q338 encoding"""
    import make_pose_rig as MPR
    R = json.loads(json.dumps(src["rig"]))
    ids_old = [m["id"] for m in man_old["meshes"]]; ids_new = [m["id"] for m in man_new["meshes"]]
    assert ids_old == ids_new, "mesh order must not change"
    assert R["count"] == len(ids_old) and R["nv"] == [int(m["vc"]) for m in man_old["meshes"]], "rig and page out of step"
    pool = list(chest) + [k for k in pool_extra if k not in chest]
    idx_of = {k: ids_old.index(k) for k in pool}
    dec = rig_decode(src, idx_of, None, old_pos)
    rigid_of = {}
    for s_, lst in R["rigid"]:
        for i in lst:
            rigid_of[i] = s_
    PX_, WX = [], []
    for k in pool:      # the old chest regions + the unchanged neighbours (a locked border vertex takes its neighbour's weights)
        v = old_pos[k]
        Wd = np.zeros((len(v), nseg), np.float32)
        if dec[k] is None:
            Wd[:, rigid_of[idx_of[k]]] = 1.0
        else:
            sg, w = dec[k]
            for c in range(sg.shape[1]):
                np.add.at(Wd, (np.arange(len(v)), sg[:, c]), w[:, c])
        PX_.append(v); WX.append(Wd)
    PX_ = np.vstack(PX_); WX = np.vstack(WX)
    tr = cKDTree(PX_)
    blob = zlib.decompress(base64.b64decode(src["weights_zlib_b64"]))
    ent = {e[0]: e for e in R["skin"]}
    span = {}
    offs = sorted(e[4] for e in R["skin"]) + [len(blob)]
    for e in R["skin"]:
        span[e[0]] = (e[4], offs[offs.index(e[4]) + 1])
    new_entries, chunks = {}, {}
    rep = {}
    for k in chest:
        i = idx_of[k]
        v, f, cls = new_geo[k]
        d, nn = tr.query(v, k=4)
        d = np.maximum(d, 1e-3); ww = 1.0 / (d * d); ww /= ww.sum(1, keepdims=True)
        W = (WX[nn] * ww[:, :, None]).sum(1)
        bvert = np.zeros(len(v), bool); bvert[np.unique(f[cls == 0])] = True
        ctrl = MPR.refine_controls(v, W, MPR.control_set(W) | bvert)
        cv = np.where(ctrl)[0]
        Wc = W[cv]
        top = np.argsort(-Wc, axis=1, kind="stable")[:, :3]
        tw = np.take_along_axis(Wc, top, 1); tw = tw / np.maximum(tw.sum(1, keepdims=True), 1e-9)
        q = np.round(tw * 255).astype(np.int32); q[:, 0] += 255 - q.sum(1); q = np.clip(q, 0, 255)
        pal = sorted(int(s_) for s_ in np.unique(top[q > 0]))
        if len(pal) == 1:      # one segment only: rigid in it
            new_entries[i] = ("rigid", pal[0])
            rep[k] = {"kind": "rigid", "segment": pal[0]}
            continue
        pm = {s_: n_ for n_, s_ in enumerate(pal)}
        K = max(1, int((q > 0).any(0).nonzero()[0].max() + 1))
        pi = np.zeros((len(cv), K), np.uint8)
        for kk in range(K):
            pi[:, kk] = [pm.get(int(s_), 0) for s_ in top[:, kk]]
            if kk:
                pi[q[:, kk] == 0, kk] = pi[q[:, kk] == 0, 0]
        b = np.packbits(ctrl).tobytes() + b"".join([pi[:, kk].tobytes() for kk in range(K)] + [q[:, kk].astype(np.uint8).tobytes()
                                                                                          for kk in range(1, K)])
        new_entries[i] = ("skin", [i, int(len(v)), K, pal, 0, int(len(cv))])
        chunks[i] = b
        sg, wq = MPR.decode_weights(v, ctrl, pal, pi.astype(np.int64), q[:, :K].astype(float))
        Wr = np.zeros_like(W)
        for c in range(sg.shape[1]):
            np.add.at(Wr, (np.arange(len(v)), sg[:, c]), wq[:, c])
        rep[k] = {"kind": "skin", "controls": int(len(cv)), "of": int(len(v)), "segments": pal,
                  "reconstruction_err_p95": round(float(np.percentile(0.5 * np.abs(Wr - MPR.top3(W)).sum(1), 95)), 3)}
    # rebuild skin list + blob (every other entry byte for byte)
    skin, packed = [], bytearray()
    for e in R["skin"]:
        if e[0] in new_entries:
            continue
        s, t = span[e[0]]
        e2 = list(e); e2[4] = len(packed); packed.extend(blob[s:t]); skin.append(e2)
    rigid = {s_: [i for i in lst if i not in new_entries] for s_, lst in R["rigid"]}
    for i, (kind, val) in sorted(new_entries.items()):
        if kind == "skin":
            val[4] = len(packed); packed.extend(chunks[i]); skin.append(val)
        else:
            rigid.setdefault(val, []).append(i)
    skin.sort(key=lambda e: e[0])
    R["skin"] = skin
    R["rigid"] = [[s_, sorted(v)] for s_, v in sorted(rigid.items())]
    R["nv"] = [int(m["vc"]) for m in man_new["meshes"]]
    R["notes"] = R["notes"] + (f"; {TAG}: the {len(chest)} anterior trunk skin regions rebuilt from their Z source topology (vertex "
                               "counts changed); their weights carried from the previous meshes (pooled, 4 nearest, top 3), border vertices "
                               "store their own weights")
    out = dict(src); out["rig"] = R
    out["weights_zlib_b64"] = base64.b64encode(zlib.compress(bytes(packed), 9)).decode("ascii")
    return out, rep


# ------------------------------------------------------------------ page I/O (the Q358 layout; originals kept as <name>.q360)
def repack(man, blob, replace):
    """replace = {id: (v, f, rec)}: geometry in place, mesh order and every other mesh byte for byte"""
    meshes, chunks, off = [], [], 0
    for m in man["meshes"]:
        n = dict(m)
        if m["id"] in replace:
            v, f, rec = replace[m["id"]]
            fields, packed = B.pack_mesh(np.asarray(v, float), np.asarray(f), off)
            n.update(fields); n["rec"] = rec
            chunks.append(packed); off += len(packed)
        else:
            pos = blob[m["vo"]: m["vo"] + m["vc"] * 6]; idx = blob[m["io"]: m["io"] + m["ic"] * 6]
            n["vo"], n["io"] = off, off + len(pos)
            chunks += [pos, idx]; off += len(pos) + len(idx)
        meshes.append(n)
    man2 = dict(man); man2["meshes"] = meshes
    return man2, b"".join(chunks)


def write_page(d: Path, man_old, man_new, blob_new, old_files):
    pages = C340.pages_of(d, STEM)
    texts = {p: p.read_text(encoding="utf-8") for p in pages}
    for p, t in texts.items():
        assert C340.LIT["manifest"].search(t).group(1) == C340.ser_manifest(man_old), f"{p}: manifest serialisation differs"
        assert C340.LIT["files"].search(t).group(1) == json.dumps(old_files), f"{p}: file list serialisation differs"
    chunks = B.split_blob(blob_new, STEM)
    assert [n for n, _ in chunks] == [f["path"] for f in old_files], "geo file set would change; not handled"
    files = [{"path": n, "bytes": len(c), "enc": "base64"} for n, c in chunks]
    changed = []
    for n, c in chunks:
        p = d / n; new = base64.b64encode(c)
        if p.read_bytes() != new:
            bk = p.with_name(p.name + ".q360")
            if not bk.exists():
                shutil.copy2(p, bk)
            p.write_bytes(new); changed.append(n)
    for p, t in texts.items():
        bk = p.with_name(p.name + ".q360")
        if not bk.exists():
            shutil.copy2(p, bk)
        t2 = C340.LIT["manifest"].sub(lambda _m: "window.__ANATOMY_MANIFEST__=" + C340.ser_manifest(man_new) + ";", t, count=1)
        t2 = C340.LIT["files"].sub(lambda _m: "window.__ANATOMY_BIN_FILES__=" + json.dumps(files) + ";", t2, count=1)
        p.write_text(t2, encoding="utf-8"); changed.append(p.name)
    return changed


def jsonable(o):
    if isinstance(o, dict):
        return {str(k): jsonable(v) for k, v in o.items() if not str(k).startswith("_")}
    if isinstance(o, (list, tuple)):
        return [jsonable(v) for v in o]
    if isinstance(o, np.generic):
        return o.item()
    if isinstance(o, np.ndarray):
        return o.tolist()
    return o


# ------------------------------------------------------------------ guards / measurements on a geometry
def folds(v, f):
    t = trimesh.Trimesh(v, f, process=False)
    fn = fnormals(v, f); adj = t.face_adjacency
    d = (fn[adj[:, 0]] * fn[adj[:, 1]]).sum(1)
    return int((d < FOLD_COS).sum()), int((d < 0).sum())


def mirror_med(a, b):
    """median distance between region a and region b mirrored in x (not a target: the body is not symmetric -- a sanity figure)"""
    if a is None or b is None:
        return None
    return round(float(np.median(cKDTree(b * np.array([-1, 1, 1])).query(a)[0])), 2)


def note_for(k, dv, wb, wa):
    return (f"{TAG}: rebuilt together with the other anterior trunk skin regions as ONE surface -- this region's Z-Anatomy source "
            f"(the same body as Base · Male) carried by one smooth deformation onto the previous Q292-fitted chest surface (deviation "
            f"from it mean {dv['mean']} / p95 {dv['p95']} / max {dv['max']} mm, the larger values only along the old borders where "
            f"the pieces did not meet), {EDGE_MM:g} mm edges, a {THICK_NOTE} slab with a creased rim; its border vertices are now "
            f"shared with its neighbours (weld {wb} -> {wa} % of rim vertices), so no seam is drawn between the regions.")


THICK_NOTE = "3 mm"


def build(d: Path, src: Path, log=print, bk_dir=None):
    rep = {}
    t0 = time.time()
    gf = Q.Geo(d); gm = Q.Geo(src)
    chest = sorted(k for k in gf.M if gf.sys[k] == "skin" and k.startswith("zan_skin") and CHEST_RE.search(k))
    assert len(chest) == 18, chest
    for k in chest:
        if f"{TAG}:" in ((gf.M[k].get("rec") or {}).get("procedural_badge") or ""):
            return None, f"{k} already carries the {TAG} sentence"
    ids = [m["id"] for m in gf.man["meshes"]]
    assert tuple(ids[-2:]) == LAST_IDS, f"last meshes {ids[-2:]} (expected {LAST_IDS})"
    rep["regions"] = chest
    # source checks: the backups beside the page files hold no other version of these meshes
    rep["originals_beside_page"] = backups_equal(bk_dir or d, chest, gf)
    S = source_surface(gm, gf, chest, log)
    rep["source"] = {k: S[k] for k in ("boundary_edges", "open_border_edges", "z_cracks_joined", "hole_faces_added", "t_junction_locks")}
    rep["source"].update(vertices=int(len(S["V"])), faces=int(len(S["F"])), locked=int(S["lock"].sum()), neighbours=S["neighbours"],
                         z_vertex_counts={k: int(gm.M[k]["vc"]) for k in chest})
    X0, rep["frame"] = frame_map(gm, gf, S, chest, log)
    T = Target(gf, chest)
    # a neighbour's border vertex lying more than LOCK_GAP_MAX off the current chest surface is not joined (decided before the
    # subdivision, so that border is subdivided and fitted like any free border)
    li = np.where(S["lock"])[0]
    g0 = T.dist(S["lock_tgt"][li], vnormals(X0, S["F"])[li])[0]
    rel = li[g0 > LOCK_GAP_MAX] if PRE_RELEASE else np.zeros(0, int)
    if len(rel):
        S["lock"] = S["lock"].copy(); S["lock"][rel] = False
        X0[rel] = X0[rel]          # (its position stays the frame-mapped one; the fit takes it from there)
        e_, c_ = np.unique(edges_of(S["F"]), axis=0, return_counts=True)
        bd_ = e_[c_ == 1]
        S["lock_edges"] = bd_[S["lock"][bd_[:, 0]] & S["lock"][bd_[:, 1]]]
    rep["locks_released"] = [{"at_mm": [round(float(x), 1) for x in S["lock_tgt"][i]], "gap_mm": round(float(gg), 2)}
                             for i, gg in zip(rel, g0[g0 > LOCK_GAP_MAX])]
    log(f"  locks: {int(S['lock'].sum())} kept, {len(rel)} released (neighbour > {LOCK_GAP_MAX} mm off the current chest surface)")
    V, F, L = refine(X0, S["F"], S["L"], S["lock_edges"])
    F, nfl = delaunay_flips(V, F, L)
    rep["edge_flips"] = nfl
    lock = np.zeros(len(V), bool); lock[:len(S["lock"])] = S["lock"]
    tl = np.full((len(V), 3), np.nan); tl[:len(S["lock"])] = S["lock_tgt"]
    log(f"  subdivided: {len(V)} vertices / {len(F)} faces")
    Xf, rep["fit_rounds"], lock = fit(V, F, lock, tl, T, log)
    gap = fit.lock_gap
    th = z_thickness(gm, chest)
    thick = float(np.median(list(th.values())))
    global THICK_NOTE
    THICK_NOTE = f"{thick:.1f} mm"
    Y, rep["inner"] = inner_of(Xf, F, lock, S, gf, gm, thick)
    rep["thickness_mm"] = {"used": round(thick, 3), "z_source_median_per_region": {k: round(v, 2) for k, v in th.items()}}
    # --- a released border vertex: the neighbour's own vertex there (and its inner partner, if it has one) follows the chest skin, so
    #     the border stays shared (the right axilla: the arm skin's border point lies 7.6 mm inside her breast, Q250 / Q292)
    follow, rep["neighbour_follows"] = neighbour_follow(gf, fit.released, tl, Xf, Y, S)
    # --- deviation from the current outer surface, per region
    Uf = vnormals(Xf, F)
    dist, tang, drim = T.dist(Xf, Uf)
    # the pieces' own disagreement at the current borders: a vertex near a locked neighbour vertex that lies off the current surface
    li = np.where(lock)[0]
    dis_tree = None
    if len(li):
        gl = T.dist(Xf[li], Uf[li])[0]
        m = gl > 0.5
        P_ = np.vstack([Xf[li[m]], tl[fit.released]]) if len(fit.released) else Xf[li[m]]
        G_ = np.r_[gl[m], np.linalg.norm(tl[fit.released] - Xf[fit.released], axis=1)] if len(fit.released) else gl[m]
        if len(P_):
            dis_tree = (cKDTree(P_), G_)
    allowed = np.where(drim > BAND_OUT, DEV_CAP, DEV_CAP_BORDER)
    if dis_tree is not None:
        dd, jj = dis_tree[0].query(Xf)
        reach = np.clip(LOCK_REACH * dis_tree[1][jj], LOCK_REACH_MIN, LOCK_REACH_MAX)
        allowed = np.maximum(allowed, np.where(dd < reach, dis_tree[1][jj] + DEV_CAP, 0))
    over = dist > allowed + 1e-6
    new, pieces_after = {}, {}
    per = {}
    for i, k in enumerate(chest):
        fo = F[L == i]
        v, f, used, cls = slab(Xf, Y, fo)
        new[k] = (v, f, cls)
        vi = used
        t = trimesh.Trimesh(v, f, process=False)
        fo_r = f[cls == 1]; fi_r = f[cls == -1]
        no = fnormals(v, fo_r); ni = fnormals(v, fi_r)
        per[k] = {"vertices": [int(gf.M[k]["vc"]), int(len(v))], "faces": [int(gf.M[k]["ic"]), int(len(f))],
                  "deviation_mm": st(dist[vi]), "deviation_core_mm": st(dist[vi][drim[vi] > BAND_OUT]),
                  "deviation_border_band_mm": st(dist[vi][drim[vi] <= BAND_OUT]),
                  "over_cap_vertices": int(over[vi].sum()), "over_slot_vertices": int((tang[vi] > TANG_MAX).sum()),
                  "watertight": bool(t.is_watertight), "winding_consistent": bool(t.is_winding_consistent),
                  "volume_cm3": round(float(t.volume) / 1000, 2),
                  "folded_outer_pairs": folds(v, fo_r)[0], "inner_flipped_faces": int(((no * ni).sum(1) > 0).sum()),
                  "edge_median_mm": round(float(np.median(np.linalg.norm(v[edges_of(fo_r)[:, 0]] - v[edges_of(fo_r)[:, 1]], axis=1))), 2)}
    rep["deviation_policy"] = {"core_cap_mm": DEV_CAP, "border_band_mm": BAND_OUT, "border_cap_mm": DEV_CAP_BORDER,
                               "near_a_neighbour_that_did_not_meet": "gap + core cap, within 4 x gap (12..40 mm)",
                               "over_cap_vertices": int(over.sum()), "of": int(len(Xf))}
    rep["deviation_all_mm"] = st(dist)
    rep["folded_pairs_merged_surface"] = folds(Xf, F)
    rep["locks_off_current_surface"] = {"n": int((gap > 0.5).sum()), "gap_mm": st(gap[gap > 0.5]) if (gap > 0.5).any() else None}
    rep["per_region"] = per
    rep["folded_before_pairs"] = int(sum(folds(gf.V0[k][0], gf.V0[k][1][gf.sheets(k)[0] == 1])[0] for k in chest))
    rep["mirror_median_mm"] = {}
    for k in chest:
        if k.endswith("_r"):
            o = k[:-2] + "_l"
            rep["mirror_median_mm"][k[9:-2]] = {"before": mirror_med(gf.V0[k][0], gf.V0[o][0]), "after": mirror_med(new[k][0], new[o][0])}
    log(f"  built {time.time() - t0:.0f} s")
    return dict(gf=gf, gm=gm, chest=chest, new=new, S=S, T=T, Xf=Xf, F=F, L=L, follow=follow), rep


def neighbour_follow(gf, released, tl, Xf, Y, S):
    """for each released border vertex: the unchanged neighbour's vertex at its lock position (outer) and that vertex's inner partner
    (the neighbour vertex joined to it by an edge, about a slab thickness away, nearest to it) are moved onto the chest skin's outer /
    inner vertex. Vertex and face counts of the neighbour unchanged. -> ({id: new positions}, report)"""
    out, rep = {}, []
    for vtx in released:
        p = tl[vtx]
        best = None
        for k in S["neighbours"]:
            v = out.get(k, gf.V0[k][0])
            d = np.linalg.norm(v - p, axis=1)
            i = int(np.argmin(d))
            if d[i] < 0.05:
                best = (k, i); break
        if best is None:
            rep.append({"vertex": int(vtx), "found": False}); continue
        k, i = best
        v = out.get(k, gf.V0[k][0]).copy(); f = gf.F[k]
        e = edges_of(f); nb = np.unique(np.r_[e[e[:, 0] == i, 1], e[e[:, 1] == i, 0]])
        dn = np.linalg.norm(v[nb] - v[i], axis=1)
        cand = nb[(dn > 1.5) & (dn < 4.5)]
        nrm = vnormals(v, f)[i]
        j = int(cand[np.argmin(np.linalg.norm(v[cand] - (v[i] - 3.0 * nrm), axis=1))]) if len(cand) else None
        v0 = v.copy()
        v[i] = Xf[vtx]
        if j is not None:
            v[j] = Y[vtx]
        fl = int((((fnormals(v0, f) * fnormals(v, f)).sum(1)) < 0).sum())
        out[k] = v
        rep.append({"vertex": int(vtx), "found": True, "neighbour": k, "outer_vertex": i, "inner_vertex": j,
                    "moved_mm": round(float(np.linalg.norm(Xf[vtx] - p)), 2), "neighbour_faces_flipped": fl})
    return out, rep


def backups_equal(d: Path, chest, gf):
    """the page's own backups (<file>.qNNN): do any hold another version of the chest regions?"""
    out = {}
    tags = sorted({p.suffix for p in d.glob("*.q[0-9][0-9][0-9]")})

    def pick(name, tg):      # the state before round tg: the earliest backup of this file from round tg on, else the file itself
        for t_ in tags:
            if t_ >= tg and (d / (name + t_)).exists():
                return d / (name + t_)
        return d / name
    for tg in tags:
        try:
            t = pick("index.html", tg).read_text(encoding="utf-8")
            man = json.loads(C340.LIT["manifest"].search(t).group(1)); files = json.loads(C340.LIT["files"].search(t).group(1))
            blob = b"".join(base64.b64decode(pick(f["path"], tg).read_bytes()) for f in files)
            M = {m["id"]: m for m in man["meshes"]}
            same = all(k in M and M[k]["vc"] == gf.M[k]["vc"] and np.abs(C340.dec(M[k], blob)[0] - gf.V0[k][0]).max() < 0.02 for k in chest)
            out[tg[1:]] = "identical" if same else "differs"
        except Exception as e:      # an incomplete backup set (only some files of a round were copied)
            out[tg[1:]] = f"not readable ({type(e).__name__})"
    return out


def skin_pieces(g, lo, hi, replace=None):
    out = {}
    for k in g.in_box(lo, hi, sys_=("skin",)):
        if replace and k in replace:
            out[k] = (replace[k][0], replace[k][1])
        else:
            out[k] = (g.cur[k], g.F[k])
    return out


def install(g, k, v, f, cls):
    """put a new mesh into a Q353 Geo (rest geometry, sheet classes known)"""
    g.V0[k] = (v, f); g.cur[k] = v.copy(); g.F[k] = f
    g._sheet[k] = (cls, np.zeros((0, 2), int))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--page-dir", required=True)
    ap.add_argument("--source-dir", help="the Base · Male page dir (Z topology); default <page-dir>/../viewer_zan_atlas")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--report", default=str(REPORT))
    ap.add_argument("--rig-file", default=str(RIG), help="pose rig read (default the shared data/anatomy/pose_rig_base_f.json)")
    ap.add_argument("--rig-out", help="where the spliced rig is written (default: --rig-file itself -- ONLY when applying to the "
                                      "build page it describes; for a copy pass a scratch path)")
    ap.add_argument("--no-rig", action="store_true")
    ap.add_argument("--backups-dir", help="where the <file>.qNNN backups are looked for (default --page-dir)")
    ap.add_argument("--debug-npz")
    a = ap.parse_args(argv)
    d = Path(a.page_dir)
    src = Path(a.source_dir) if a.source_dir else d.parent / "viewer_zan_atlas"
    assert C340.pages_of(d, STEM), f"{d}: no {STEM}.html (Base · Female only)"
    assert C340.pages_of(src, SRC_STEM), f"{src}: no {SRC_STEM}.html (the Base · Male page is the Z source)"
    t0 = time.time()
    print(f"{TAG} chest skin on {d} (Z source {src})")
    G, rep = build(d, src, bk_dir=Path(a.backups_dir) if a.backups_dir else None)
    if G is None:
        print(f"Q360_CHEST_SKIN_REFUSED {d}: {rep}. Re-apply only on the page before Q360: restore every '<file>.q360' beside its "
              f"file in {d} and the pose rig (git checkout data/anatomy/pose_rig_base_f.json), then run again.")
        return 3
    gf, chest, new = G["gf"], G["chest"], G["new"]
    lo, hi = CHEST_BOX
    # --- weld (Q334 rules), before / after, chest regions + the back regions as the reference
    back = [k for k in gf.M if gf.sys[k] == "skin" and re.search(r"scapular|vertebral|auscultation", k)]
    focus = set(chest) | set(back)
    wb = weld_stats(skin_pieces(gf, lo - 60, hi + 60), focus)
    follow = G["follow"]
    after_geo = {k: v for k, v in new.items()}
    after_geo.update({k: (v, gf.F[k]) for k, v in follow.items()})
    wa = weld_stats(skin_pieces(gf, lo - 60, hi + 60, after_geo), focus)
    rep["weld_pct"] = {k: {"before": wb[k]["pct"], "after": wa[k]["pct"], "rim_vertices": [wb[k]["rim_vertices"], wa[k]["rim_vertices"]],
                           "rim_joined_after": wa[k]["rim_joined"]} for k in sorted(focus) if k in wb and k in wa}
    for k in chest:
        print(f"  weld {k[9:]:32s} {wb[k]['pct']:5.1f} -> {wa[k]['pct']:5.1f} %  (rim {wa[k]['rim_vertices']})")
    # --- holes before (current pieces)
    rep["holes_before"] = holes(gf, chest)
    old_pos = {k: gf.V0[k][0].copy() for k in gf.M if gf.sys[k] == "skin" and gf.in_box(lo - 60, hi + 60) and k in gf.M}
    old_pos = {k: gf.V0[k][0].copy() for k in skin_pieces(gf, lo - 60, hi + 60)}
    old_geo = {k: (gf.V0[k][0].copy(), gf.F[k].copy()) for k in chest}
    sk_before = Q.SkinSet(gf, [k for k in gf.in_box(lo - 20, hi + 20, sys_=("skin",))])
    deep = [k for k in gf.in_box(np.array([-200.0, 280.0, -60.0]), np.array([200.0, 640.0, 200.0]))
            if gf.sys[k] in TUCK_GUARD or k in BREAST]
    deep = [k for k in deep if k in gf.M]
    out_b = outside(gf, sk_before, deep)
    # --- install the new chest skin, measure, tuck the breast tissue (Q353 rule)
    for k in chest:
        install(gf, k, *new[k])
    for k, v in follow.items():
        gf.cur[k] = v.copy()
    sk = Q.SkinSet(gf, [k for k in gf.in_box(lo - 20, hi + 20, sys_=("skin",))])
    out_a = outside(gf, sk, deep)
    bones = Q.Bones(gf, lo, hi)
    tuck = {}
    for k in [k for k in BREAST if k in gf.M]:
        if out_a[k]["outside"] > 0 or out_a[k]["in_slab"] > 0:
            tuck[k] = Q.run_tuck(gf, k, sk, bones, print)
    out_t = outside(gf, sk, deep)
    rep["outside_skin"] = {"before": {k: v for k, v in out_b.items() if v["outside"]},
                           "after_skin": {k: v for k, v in out_a.items() if v["outside"]},
                           "after_tuck": {k: v for k, v in out_t.items() if v["outside"]}}
    rep["tuck"] = tuck
    gained = {k: [out_b[k]["outside"], out_t[k]["outside"]] for k in deep if out_t[k]["outside"] > out_b[k]["outside"]}
    rep["outside_gained"] = gained
    rep["holes_after"] = holes(gf, chest)
    if a.debug_npz:
        np.savez_compressed(a.debug_npz, Xf=G["Xf"], F=G["F"], L=G["L"],
                            **{f"tuck__{k}": gf.cur[k] for k in tuck}, **{f"follow__{k}": v for k, v in follow.items()})
    for v_ in ("front", "lateral_r", "lateral_l"):
        print(f"  holes {v_}: {rep['holes_before'][v_]['hole_px']} -> {rep['holes_after'][v_]['hole_px']} px")
    # --- guards
    per = rep["per_region"]
    breast_out = {k: out_t[k]["outside"] for k in BREAST if k in out_t and out_t[k]["outside"]}
    guards = {
        "weld_min_pct": WELD_MIN,
        "weld_below_min": {k[9:]: wa[k]["pct"] for k in chest if wa[k]["pct"] < WELD_MIN},
        "holes_after_px": {v_: rep["holes_after"][v_]["hole_px"] for v_ in ("front", "lateral_r", "lateral_l")},
        "deviation_over_cap_vertices": rep["deviation_policy"]["over_cap_vertices"],
        "breast_tissue_outside": breast_out,
        "structures_gaining_outside": gained,
        "slabs_closed_and_consistent": all(per[k]["watertight"] and per[k]["winding_consistent"] and per[k]["volume_cm3"] > 0 for k in chest),
        "inner_flipped_faces": sum(per[k]["inner_flipped_faces"] for k in chest),
        "folded_outer_pairs": sum(per[k]["folded_outer_pairs"] for k in chest),
        "mesh_order_last_two": [m["id"] for m in gf.man["meshes"]][-2:],
    }
    hb = {v_: rep["holes_before"][v_]["hole_px"] for v_ in ("front", "lateral_r", "lateral_l")}
    big = {v_: [w_["px"] for w_ in rep["holes_after"][v_]["largest"] if w_["px"] > HOLE_PIECE_MAX] for v_ in hb}
    guards["holes_before_px"] = hb
    guards["hole_pieces_over_max"] = {v_: x for v_, x in big.items() if x}
    holes_ok = all(guards["holes_after_px"][v_] <= hb[v_] for v_ in hb) and not guards["hole_pieces_over_max"]
    guards["holes_ok"] = holes_ok
    nout = sum(int((new[k][2] == 1).sum()) for k in chest)
    guards["folded_or_flipped_pct_of_outer_faces"] = round(100.0 * (guards["folded_outer_pairs"] + guards["inner_flipped_faces"]) / nout, 3)
    guards["folded_before_pairs_current_outer"] = rep.get("folded_before_pairs")
    holes_ok = holes_ok and guards["folded_or_flipped_pct_of_outer_faces"] <= FOLD_MAX_PCT
    ok = (not guards["weld_below_min"] and holes_ok and not guards["deviation_over_cap_vertices"]
          and not breast_out and not gained and guards["slabs_closed_and_consistent"] and tuple(guards["mesh_order_last_two"]) == LAST_IDS)
    guards["pass"] = bool(ok)
    rep["guards"] = guards
    # --- page + rig
    replace = {}
    for k in chest:
        dv = per[k]["deviation_mm"]
        rec = C340.badge_add(gf.M[k].get("rec") or {}, note_for(k, dv, wb[k]["pct"], wa[k]["pct"]))
        replace[k] = (new[k][0], new[k][1], rec)
    for r_ in rep["neighbour_follows"]:
        if r_.get("found"):
            k = r_["neighbour"]
            rec = C340.badge_add(gf.M[k].get("rec") or {},
                                 f"{TAG}: one border point of this region (outer {r_['outer_vertex']} and inner {r_['inner_vertex']}: a spike "
                                 f"left by the Q250 skeleton deformation, lying inside the breast) moved {r_['moved_mm']} mm onto the "
                                 "rebuilt chest skin, so the two regions share it; nothing else changed.")
            replace[k] = (follow[k], gf.F[k], rec)
    for k, r in tuck.items():
        if r.get("ships"):
            rec = C340.badge_add(gf.M[k].get("rec") or {},
                                 f"{TAG} tuck: moved under the rebuilt chest skin by the Q353 rule (rule-based; max "
                                 f"{r['displacement']['max_mm']} mm, cap {Q.CAP_TUCK:g} mm; vertex and triangle counts unchanged).")
            replace[k] = (gf.cur[k], gf.F[k], rec)
    man_new, blob_new = repack(gf.man, gf.blob, replace)
    assert [m["id"] for m in man_new["meshes"]] == [m["id"] for m in gf.man["meshes"]]
    rig_src = json.loads(Path(a.rig_file).read_text(encoding="utf-8"))
    neigh = sorted(set(G["S"]["neighbours"]))
    rig_new, rep["rig_weights"] = rig_transfer(rig_src, gf.man, man_new, chest, old_pos,
                                               {k: new[k] for k in chest}, len(rig_src["rig"]["segs"]), pool_extra=neigh)
    rep.update({"schema": "nmsk.q360.chest_skin.v1", "round": TAG, "generated": time.strftime("%Y-%m-%d"), "page_dir": str(d),
                "source_dir": str(src),
                "parameters": dict(weld_mm=WELD_MM, crack_mm=CRACK_MM, tj_mm=TJ_MM, edge_mm=EDGE_MM, rim_excl_mm=RIM_EXCL,
                                   band_mm=[BAND_IN, BAND_OUT], stiffness=list(STIFF), p2p_share=P2P, tang_max_mm=TANG_MAX,
                                   ovl_mm=OVL_MM, face_cos=FACE_COS, lock_reach=[LOCK_REACH, LOCK_REACH_MIN, LOCK_REACH_MAX],
                                   dev_cap_mm=DEV_CAP, dev_cap_border_mm=DEV_CAP_BORDER, weld_min_pct=WELD_MIN)})
    if a.write and ok:
        rep["files_written"] = write_page(d, gf.man, man_new, blob_new, gf.files)
        if not a.no_rig:
            out = Path(a.rig_out or a.rig_file)
            out.write_text(json.dumps(rig_new, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
            rep["rig"] = {"written": str(out), "count": rig_new["rig"]["count"]}
    else:
        rep["files_written"] = []
        rep["rig"] = "dry run" if not a.write else "guards failed: nothing written"
    rep["seconds"] = round(time.time() - t0, 1)
    Path(a.report).write_text(json.dumps(jsonable(rep), indent=1), encoding="utf-8")
    print("  guards:", json.dumps(jsonable(guards))[:1500])
    print(f"Q360_CHEST_SKIN_{'WRITTEN' if (a.write and ok) else ('GUARD_FAIL' if not ok else 'DRY')} {d}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
