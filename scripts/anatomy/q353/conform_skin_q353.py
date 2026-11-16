#!/usr/bin/env python3
"""Q353: Base · Female skin defects -- seams between the trunk skin regions, breast tissue / facial muscle through the skin,
and the border of the vulvar skin patch.

    python3 scripts/anatomy/q353/conform_skin_q353.py --page-dir DIR [--steps chest,back,head,perineum]          # dry run
    python3 scripts/anatomy/q353/conform_skin_q353.py --page-dir DIR [--steps ...] --write                       # and write DIR

What is wrong (measured on the page, data/derived/Q353_skin_report.json):
  chest / back  the trunk skin regions of this body were refitted one by one (the deformed female trunk), so neighbouring regions
                no longer meet: their outer borders miss each other by a median ~1 mm and up to ~8 mm, with steps of +-2..5 mm
                across the border. The engine's load-time weld (Q334) only joins borders within 1.5 mm (T-junctions 0.8 mm), so the
                rest stays a crease and the shading breaks along it (geometry, not normals). The same at the scapular /
                interscapular / auscultation junction leaves a small triangular hole on each side.
  breast        breast fat pads / lactiferous ducts lie partly outside the (refitted) chest skin.
  head          frontalis, temporoparietalis, orbicularis oris and platysma lie partly in / outside the scalp and face skin.
  perineum      the Q336 vulvar patch (real CVH surface, tucked under the Z neighbours) crosses the neighbours' outer surface in
                many places (islands, a flap) and lies too deep under their border elsewhere (gaps where muscle shows).

The conform (owner-approved pattern of Q333 / Q336 / Q340 / Q349: existing real meshes only, nothing added, nothing deleted):
  seams   per step a set of movable skin regions; every outer-border vertex is matched to the nearest outer border of another skin
          region within MATCH mm; movable-movable pairs meet at the midpoint (SEAM_ROUNDS rounds, then the later region in a fixed
          order snaps onto the earlier one's border), a fixed neighbour is the target itself. The border displacement is spread over
          the region (Gaussian-weighted, SIG mm, faded to zero over FALL mm from the border), so each slab cross-section moves as a
          whole. Per-vertex move capped at CAP_SEAM.
  tuck    a deeper structure that lies in / outside the skin moves inward along the skin's inner-sheet normal until it is GAP mm
          under the inner sheet (fallback: HIDE mm under the outer surface), by a Lipschitz envelope (slope K) of the requirement,
          capped at CAP_TUCK mm.
  vulva   every vertex of `skin_vulva_cvh` that lies under a Z neighbour (projects onto a neighbour face) is held between VU_HI mm and
          (neighbour thickness + VU_LO) mm under the neighbour's outer surface (pushed down where it stands through it, lifted where
          it lies deeper than the neighbour's inner sheet); the move is spread over the patch as for the seams; cap CAP_VULVA.
Guards (a structure / region failing any keeps its bytes and is listed): vertex / triangle counts and order unchanged (pose rig and
symmetry sidecar untouched); flipped faces <= FLIP_MAX % of the moved faces; stretched (area x0.5 / x2) <= before + STRETCH_ADD
points; move <= cap; no moved vertex newly inside a bone; volume change <= VOL_MAX %; no structure gains vertices outside the skin
(tucked structures: none left outside); L/R pairs that were exact mirrors stay within MIRROR_MAX mm median.
Every replaced file is first copied beside itself as `<name>.q353` (never overwriting); a step whose tag a structure already
carries is skipped (idempotent). Deterministic.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

import numpy as np
import trimesh
from scipy import sparse
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "scripts" / "anatomy" / "q340"))
import conform_palm_q340 as C340  # noqa: E402  page I/O (read_page, dec, repack, badge_add, LIT, ser_manifest)
from scripts.transfer.q213_inbone import flipped_pct, stretched_pct  # noqa: E402

OUT = REPO / "data/derived/Q353_skin_report.json"
STEMS = ("atlas_viewer_base_female",)

MATCH, CAP_SEAM, SIG, FALL, SEAM_ROUNDS, RIM_SIG = 8.0, 8.0, 3.0, 25.0, 4, 2.0
PIN_R = 4.0
WELD_EPS = 0.03     # mm: the engine's load-time weld (Q334); border vertices this close are already one vertex
GAP, HIDE, K_ENV, CAP_TUCK, TUCK_ROUNDS = 0.3, 0.5, 0.15, 8.0, 4
TUCK_TRIES = [("under_inner_sheet", 4.0), ("under_inner_sheet", 10.0), ("under_inner_sheet", 1e6), ("under_outer_surface", 4.0),
              ("under_outer_surface", 10.0), ("under_outer_surface", 1e6)]     # direction smoothing sigma; 1e6 = one direction (a translation)
VU_HI, VU_LO, CAP_VULVA, VU_FALL, VU_ROUNDS = 0.4, 0.6, 10.0, 12.0, 5
VULVA_VARIANTS = ("both", "push", "lift")
FLIP_MAX, STRETCH_ADD, VOL_MAX, MIRROR_MAX, SLAB_VOL_MAX = 0.5, 12.0, 5.0, 0.5, 20.0
TANG_MAX = 2.0      # mm: farther from the skin surface sideways than this = beyond its border (an opening), not under it
SHEET_MAX = 6.0     # mm: the slab's other sheet lies within this distance behind a sheet face
GAIN_TOL = 2
NEAR = 12.0          # mm: a vertex farther than this from every skin vertex is not tested against the skin

CHEST = ["pectoral_region", "mammary_region", "presternal_region", "inframammary_region", "infraclavicular_fossa",
         "deltopectoral_triangle", "lateral_region_of_thorax", "epigastric_region", "hypochondriac_region"]
BACK = ["scapular_region", "interscapular_region", "triangle_of_auscultation", "infrascapular_region", "vertebral_region"]
STEPS = {
    "chest": dict(seam=[f"zan_skin_{c}_{s}" for c in CHEST for s in "rl"],
                  tuck=["breast_fat_r", "breast_fat_l", "lactiferous_ducts_r", "lactiferous_ducts_l"]),
    "back": dict(seam=[f"zan_skin_{c}_{s}" for c in BACK for s in "rl"], tuck=[]),
    "head": dict(seam=[], tuck=[f"{m}_{s}" for m in ("frontalis", "zan_temporoparietalis_muscle", "orbicularis_oris", "platysma")
                                for s in "rl"]),
    "perineum": dict(seam=[], tuck=[], vulva="skin_vulva_cvh"),
}
INTERIOR_SYS = ("bone",)       # the skeleton is under every skin region (muscle may itself be what pokes through)
VISIBLE_SYS = ("muscle", "vessel", "nerve", "viscera", "bone", "joint", "cartilage", "lymph", "bursa", "insertion")


def tag(step):
    return f"Q353 {step}:"


def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def stats(D):
    n = np.linalg.norm(D, axis=1) if D.ndim == 2 else np.abs(D)
    mv = n > 1e-6
    return dict(vertices_moved=int(mv.sum()), max_mm=round(float(n.max()) if len(n) else 0.0, 2),
                mean_moved_mm=round(float(n[mv].mean()) if mv.any() else 0.0, 2))


def vol(v, f):
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    return float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6.0)


def closed_manifold(f):
    e = np.sort(f[:, [0, 1, 1, 2, 2, 0]].reshape(-1, 2), axis=1)
    _, c = np.unique(e, axis=0, return_counts=True)
    return bool((c == 2).all())


def vol_change(fg):
    """% volume change; only a closed manifold mesh has a volume (project rule), else None"""
    if not fg["closed_manifold"]:
        return None
    return abs(fg["volume_after_mm3"] - fg["volume_before_mm3"]) / max(abs(fg["volume_before_mm3"]), 1e-9) * 100


def moved_faces(f, mv):
    return mv[f].any(1)


def face_guards(v0, v1, f, sel=None):
    """flipped % of the moved faces and stretched % (of `sel` faces when given: the outer sheet of a skin slab, the surface that
    is seen; its narrow border wall is reported separately), volume of the whole mesh"""
    mv = np.linalg.norm(v1 - v0, axis=1) > 1e-6
    fs = f if sel is None else f[sel]
    mf = moved_faces(fs, mv)
    fl = flipped_pct(v0, v1, fs[mf]) if mf.any() else 0.0
    o = v0.mean(0)
    closed = closed_manifold(f)
    out = dict(flipped_pct_moved_faces=round(fl, 3), stretched_pct=[round(stretched_pct(v0, v0, fs), 2), round(stretched_pct(v0, v1, fs), 2)],
               closed_manifold=closed, volume_before_mm3=round(vol(v0 - o, f), 1), volume_after_mm3=round(vol(v1 - o, f), 1))
    if sel is not None:
        fw = f[~sel]; mw = moved_faces(fw, mv)
        out["border_wall_and_inner"] = dict(flipped_pct_moved_faces=round(flipped_pct(v0, v1, fw[mw]) if mw.any() else 0.0, 3),
                                            stretched_pct=[round(stretched_pct(v0, v0, fw), 2), round(stretched_pct(v0, v1, fw), 2)])
    return out


# ------------------------------------------------------------------ page geometry
class Geo:
    def __init__(self, d: Path):
        self.d = d
        self.stem = C340.stem_of(d)
        self.man, self.blob, self.files = C340.read_page(d, self.stem)
        self.M = {m["id"]: m for m in self.man["meshes"]}
        self.V0 = {k: C340.dec(m, self.blob) for k, m in self.M.items()}
        self.cur = {k: v.copy() for k, (v, _) in self.V0.items()}
        self.F = {k: f for k, (_, f) in self.V0.items()}
        self.sys = {k: m.get("sys") for k, m in self.M.items()}
        P = [self.cur[k] for k in self.M if self.sys[k] in INTERIOR_SYS]
        self.interior = np.vstack(P)
        self.itree = cKDTree(self.interior)
        self._sheet = {}

    def box(self, k, pad=0.0):
        v = self.cur[k]
        return v.min(0) - pad, v.max(0) + pad

    def in_box(self, lo, hi, sys_=None, exclude=()):
        out = []
        for k in self.M:
            if k in exclude or (sys_ and self.sys[k] not in sys_):
                continue
            v = self.cur[k]
            if np.all(v.max(0) >= lo) and np.all(v.min(0) <= hi):
                out.append(k)
        return out

    def sheets(self, k):
        """per face of a skin slab: +1 outer sheet, -1 inner sheet, 0 wall. A sheet face has the slab's other sheet right behind it
        (ray along -normal, 0.8..SHEET_MAX mm); a sheet face is outer / inner by its normal against the direction from the nearest
        bone vertices (the body is under the outer sheet), smoothed over its neighbours three times; enclosed islands join
        the sheet around them. Cached (rest geometry)."""
        if k in self._sheet:
            return self._sheet[k]
        v, f = self.V0[k]
        t = trimesh.Trimesh(v, f, process=False)
        fn = t.face_normals
        c = t.triangles_center
        area = t.area_faces
        adj = t.face_adjacency
        _, idx = self.itree.query(c, k=24)
        u = c - self.interior[idx].mean(1)
        u /= np.linalg.norm(u, axis=1, keepdims=True) + 1e-12
        dot = (fn * u).sum(1)
        # a sheet face sees the slab's other sheet right behind it (1..SHEET_MAX mm along -normal); a wall face looks along the slab
        loc, ri, _ = trimesh.ray.ray_triangle.RayMeshIntersector(t).intersects_location(c - fn * 0.02, -fn, multiple_hits=False)
        hit = np.full(len(f), np.inf)
        hit[ri] = np.linalg.norm(loc - (c[ri] - fn[ri] * 0.02), axis=1)
        sheet = (hit > 0.8) & (hit < SHEET_MAX)
        a_, b_ = adj[:, 0], adj[:, 1]
        A = sparse.coo_matrix((np.ones(2 * len(adj)), (np.r_[a_, b_], np.r_[b_, a_])), shape=(len(f), len(f))).tocsr()
        deg = np.asarray(A.sum(1)).ravel()
        for _ in range(3):
            dot = (dot + A @ dot) / (1.0 + deg)
        cls = np.where(sheet, np.where(dot > 0, 1, -1), 0)
        # islands: a wall-like patch enclosed by one sheet belongs to that sheet; a small patch of one sheet enclosed by the other
        # sheet belongs to the other (a true wall touches both sheets)
        for c0 in (0, 1, -1):
            m = cls == c0
            e = m[a_] & m[b_]
            Gc = sparse.coo_matrix((np.ones(int(e.sum())), (a_[e], b_[e])), shape=(len(f), len(f)))
            ncc, lab = connected_components(Gc, directed=False)
            lab = np.where(m, lab, -1)
            touch = {}
            for x, y in ((a_, b_), (b_, a_)):
                s = (lab[x] >= 0) & (cls[y] != c0)
                for l_, cy in zip(lab[x][s], cls[y][s]):
                    touch.setdefault(int(l_), set()).add(int(cy))
            if c0 == 0:
                for l_, ts in touch.items():
                    if len(ts) == 1:
                        cls[lab == l_] = ts.pop()
            else:
                tot = area[cls == c0].sum()
                for l_, ts in touch.items():
                    if ts == {-c0} and area[lab == l_].sum() < 0.05 * tot:
                        cls[lab == l_] = -c0
        # rim edges of the outer sheet: an outer face next to a non-outer face, or a free edge of an outer face
        a, b = adj[:, 0], adj[:, 1]
        e = t.face_adjacency_edges[((cls[a] == 1) & (cls[b] == 0)) | ((cls[a] == 0) & (cls[b] == 1))]
        es = np.sort(f[cls == 1][:, [0, 1, 1, 2, 2, 0]].reshape(-1, 2), axis=1)
        u_, cnt = np.unique(es, axis=0, return_counts=True)
        rim_e = np.unique(np.sort(np.vstack([e, u_[cnt == 1]]), axis=1), axis=0) if len(e) or (cnt == 1).any() else np.zeros((0, 2), int)
        self._sheet[k] = (cls, rim_e)
        return self._sheet[k]


class SkinSet:
    """the outer and inner sheets of a set of skin pieces at their CURRENT positions"""

    def __init__(self, g: Geo, ids):
        self.ids = list(ids)
        Vo, Fo, Vi, Fi, Oo, Oi = [], [], [], [], [], []
        no = ni = 0
        for k in self.ids:
            cls, _ = g.sheets(k)
            v, f = g.cur[k], g.F[k]
            fo, fi = f[cls == 1], f[cls == -1]
            Vo.append(v); Fo.append(fo + no); Oo += [k] * len(fo); no += len(v)
            Vi.append(v); Fi.append(fi + ni); Oi += [k] * len(fi); ni += len(v)
        self.outer = trimesh.Trimesh(np.vstack(Vo), np.vstack(Fo), process=False)
        self.inner = trimesh.Trimesh(np.vstack(Vi), np.vstack(Fi), process=False)
        self.oown, self.iown = np.array(Oo), np.array(Oi)
        self.tree = cKDTree(np.vstack(Vo))

    def near(self, P, r=NEAR):
        d, _ = self.tree.query(P, distance_upper_bound=r)
        return np.where(np.isfinite(d))[0]

    def s_out(self, P):
        q, _, tri = trimesh.proximity.closest_point(self.outer, P)
        n = self.outer.face_normals[tri]
        return ((P - q) * n).sum(1), n, q, tri

    def s_in(self, P):
        q, _, tri = trimesh.proximity.closest_point(self.inner, P)
        n = self.inner.face_normals[tri]          # into the body
        return ((P - q) * n).sum(1), n


def outside_count(g: Geo, sk: SkinSet, k):
    """vertices of structure k outside the outer skin surface (s_out > 0) and inside the skin slab (s_in < 0)"""
    v = g.cur[k]
    c = sk.near(v)
    if not len(c):
        return dict(outside=0, in_slab=0, max_out_mm=0.0, beyond_border=0)
    so, n, q, _ = sk.s_out(v[c])
    si, _ = sk.s_in(v[c])
    cov = covered(v[c], so, n, q)
    o = (so > 0) & (si < 0) & cov          # deeper than the inner sheet is under the skin whatever the outer sheet says
    return dict(outside=int(o.sum()), in_slab=int(((so <= 0) & (si < 0) & cov).sum()),
                max_out_mm=round(float(so[o].max()) if o.any() else 0.0, 2), beyond_border=int(((so > 0) & (si < 0) & ~cov).sum()))


def covered(P, so, n, q):
    """the point lies over / under the skin surface or in a seam gap narrower than TANG_MAX (not beyond a real opening: eye,
    mouth, nostril, the perineal opening)"""
    return np.linalg.norm((P - q) - so[:, None] * n, axis=1) < TANG_MAX


# ------------------------------------------------------------------ bones
class Bones:
    def __init__(self, g: Geo, lo, hi):
        ids = g.in_box(lo, hi, sys_=("bone",))
        if not ids:
            self.t = None
            return
        V, Fs, n = [], [], 0
        for k in ids:
            V.append(g.cur[k]); Fs.append(g.F[k] + n); n += len(g.cur[k])
        self.t = trimesh.Trimesh(np.vstack(V), np.vstack(Fs), process=False)
        self.tree = cKDTree(self.t.vertices)

    def inside(self, P):
        if self.t is None or not len(P):
            return np.zeros(len(P), bool)
        d, _ = self.tree.query(P, distance_upper_bound=15.0)
        out = np.zeros(len(P), bool)
        c = np.where(np.isfinite(d))[0]
        if len(c):
            q, _, tri = trimesh.proximity.closest_point(self.t, P[c])
            out[c] = ((P[c] - q) * self.t.face_normals[tri]).sum(1) < -0.05
        return out


# ------------------------------------------------------------------ fields
def envelope(X, need_pts, amp, dirs, K=K_ENV, sig=4.0):
    """amplitude a(x) = max_j (amp_j - K |x - x_j|)+ and the Gaussian-weighted mean direction of the requirements around x"""
    a = np.zeros(len(X)); D = np.zeros((len(X), 3))
    if not len(need_pts):
        return D
    r = float(amp.max()) / K + 1e-6
    tx, tn = cKDTree(X), cKDTree(need_pts)
    S = tx.sparse_distance_matrix(tn, max(r, 3 * sig), output_type="coo_matrix")
    i, j, d = S.row, S.col, S.data
    # exact coincidences are dropped by the sparse matrix; add them
    d0, j0 = tn.query(X, distance_upper_bound=1e-9)
    z = np.where(np.isfinite(d0))[0]
    i = np.r_[i, z]; j = np.r_[j, j0[z]]; d = np.r_[d, np.zeros(len(z))]
    val = amp[j] - K * d
    np.maximum.at(a, i, val)
    w = np.exp(-0.5 * (d / sig) ** 2)
    np.add.at(D, i, w[:, None] * dirs[j])
    nrm = np.linalg.norm(D, axis=1, keepdims=True)
    D = np.where(nrm > 1e-9, D / np.maximum(nrm, 1e-12), 0.0)
    return D * np.clip(a, 0, None)[:, None]


def shepard(X, pts, vecs, sig=SIG, fall=FALL):
    """Gaussian-weighted mean of the border vectors, faded to zero over `fall` mm from the nearest border point"""
    if not len(pts):
        return np.zeros((len(X), 3))
    tn = cKDTree(pts)
    kk = min(16, len(pts))
    d, j = tn.query(X, k=kk)
    if kk == 1:
        d, j = d[:, None], j[:, None]
    w = np.exp(-0.5 * (d / sig) ** 2) + 1e-12
    D = (w[:, :, None] * vecs[j]).sum(1) / w.sum(1)[:, None]
    return D * smoothstep(1.0 - d[:, 0] / fall)[:, None]


# ------------------------------------------------------------------ seams
def seg_closest(P, A, B):
    AB = B - A
    t = np.clip(((P - A) * AB).sum(1) / np.maximum((AB * AB).sum(1), 1e-12), 0, 1)
    Q = A + t[:, None] * AB
    return Q, np.linalg.norm(P - Q, axis=1)


def rim_targets(g: Geo, movable, anchors, full_snap):
    """per movable piece: its outer-border vertices, their partner piece and the target point on the partner's outer border"""
    order = {k: i for i, k in enumerate(movable)}
    segs, own = [], []
    for k in list(movable) + list(anchors):
        _, rim_e = g.sheets(k)
        if len(rim_e):
            v = g.cur[k]
            segs.append(np.stack([v[rim_e[:, 0]], v[rim_e[:, 1]]], 1)); own += [k] * len(rim_e)
    S = np.vstack(segs); own = np.array(own)
    mid = S.mean(1)
    tree = cKDTree(mid)
    out = {}
    for k in movable:
        _, rim_e = g.sheets(k)
        rv = np.unique(rim_e)
        P = g.cur[k][rv]
        _, J = tree.query(P, k=min(48, len(mid)))
        best_d = np.full(len(P), np.inf); best_q = P.copy(); best_o = np.array([""] * len(P), dtype=object)
        for c in range(J.shape[1]):
            j = J[:, c]
            ok = own[j] != k
            Q, d = seg_closest(P, S[j, 0], S[j, 1])
            b = ok & (d < best_d)
            best_d[b] = d[b]; best_q[b] = Q[b]; best_o[b] = own[j][b]
        T = P.copy(); hit = best_d < MATCH
        for i in np.where(hit)[0]:
            o = best_o[i]
            if o in order and not full_snap:
                T[i] = 0.5 * (P[i] + best_q[i])
            elif o in order and order[o] > order[k]:
                T[i] = P[i]              # the later piece snaps onto this one
            else:
                T[i] = best_q[i]
        out[k] = dict(rv=rv, target=T, gap=best_d, partner=best_o, matched=hit)
    return out


def run_seams(g: Geo, movable, log):
    movable = [k for k in movable if k in g.M]
    lo = np.min([g.box(k)[0] for k in movable], 0) - MATCH
    hi = np.max([g.box(k)[1] for k in movable], 0) + MATCH
    anchors = [k for k in g.in_box(lo, hi, sys_=("skin",), exclude=set(movable)) if "nail_plate" not in k]
    start = {k: g.cur[k].copy() for k in movable}
    gap0 = None
    for rnd in range(SEAM_ROUNDS + 1):
        full = rnd == SEAM_ROUNDS
        R = rim_targets(g, movable, anchors, full)
        if gap0 is None:
            gap0 = {k: r["gap"].copy() for k, r in R.items()}
            # a stretch of border already shared vertex for vertex (welded at load) stays where it is: a border vertex is pinned
            # when it and every border vertex of its piece within PIN_R mm are within WELD_EPS of the neighbour
            pins = {}
            for k, r in R.items():
                P0 = g.cur[k][r["rv"]]
                bad = gap0[k] >= WELD_EPS
                if bad.any():
                    db, _ = cKDTree(P0[bad]).query(P0)
                    pins[k] = (~bad) & (db > PIN_R)
                else:
                    pins[k] = np.ones(len(P0), bool)
        for k, r in R.items():
            v = g.cur[k]
            d = r["target"] - v[r["rv"]]
            dn = np.linalg.norm(d, axis=1)
            d[dn > CAP_SEAM] = 0.0
            pin = pins[k]
            # matching noise along the border is smoothed out before it is spread (no kinks at the border); lighter in the last round
            d = shepard(v[r["rv"]], v[r["rv"]], d, sig=RIM_SIG if not full else RIM_SIG / 2, fall=1e9)
            d[pin | ~(gap0[k] < MATCH)] = 0.0    # nor a border with no neighbour within MATCH (it is not dragged off its own border)
            D = shepard(v, v[r["rv"]], d)
            if full:
                D[r["rv"]] = d
            g.cur[k] = v + D
    R = rim_targets(g, movable, anchors, True)
    rep = {}
    for k in movable:
        D = g.cur[k] - start[k]
        n = np.linalg.norm(D, axis=1)
        over = n > CAP_SEAM
        if over.any():           # the spread of several rounds may add up beyond the cap: scale those back
            g.cur[k][over] = start[k][over] + D[over] * (CAP_SEAM / n[over])[:, None]
        g0, g1 = gap0[k], R[k]["gap"]
        m0 = g0 < MATCH
        rep[k] = dict(border_vertices=int(len(g0)), matched=int(m0.sum()),
                      border_gap_before_mm=dict(median=round(float(np.median(g0[m0])), 2) if m0.any() else None,
                                                p90=round(float(np.percentile(g0[m0], 90)), 2) if m0.any() else None,
                                                over_1_5mm=int((g0[m0] > 1.5).sum())),
                      border_gap_after_mm=dict(median=round(float(np.median(g1[m0])), 2) if m0.any() else None,
                                               p90=round(float(np.percentile(g1[m0], 90)), 2) if m0.any() else None,
                                               max=round(float(g1[m0].max()), 2) if m0.any() else None,
                                               over_1_5mm=int((g1[m0] > 1.5).sum())),
                      unmatched_over_match=int((g0 >= MATCH).sum()),
                      partners=sorted(set(x for x in R[k]["partner"][m0] if x)))
    return rep, anchors, start


# ------------------------------------------------------------------ tuck
def run_tuck(g: Geo, k, sk: SkinSet, bones: Bones, log, tries=None):
    v0 = g.cur[k].copy(); f = g.F[k]
    before = outside_count(g, sk, k)
    res = dict(before=before)
    if before["outside"] == 0 and before["in_slab"] == 0:
        res.update(ships=False, reason="nothing in or outside the skin")
        return res
    for mode, sig in (tries or TUCK_TRIES):
        v = v0.copy()
        for _ in range(TUCK_ROUNDS):
            c = sk.near(v)
            if not len(c):
                break
            so, no, qo, _ = sk.s_out(v[c])
            cov = covered(v[c], so, no, qo)
            si, ni = sk.s_in(v[c])
            if mode == "under_inner_sheet":
                req = GAP - si; dirn = ni
            else:
                req = np.where(si < 0, so + HIDE, 0.0); dirn = -no
            need = (req > 1e-3) & cov
            if not need.any():
                break
            v = v + envelope(v, v[c][need], req[need], dirn[need], sig=sig)
        D = v - v0
        dn = np.linalg.norm(D, axis=1)
        g.cur[k] = v
        after = outside_count(g, sk, k)
        g.cur[k] = v0
        fg = face_guards(v0, v, f)
        mv = dn > 1e-6
        b0 = int(bones.inside(v0[mv]).sum()); b1 = int(bones.inside(v[mv]).sum())
        fails = []
        if dn.max() > CAP_TUCK:
            fails.append(f"move {dn.max():.2f} mm > cap {CAP_TUCK:g}")
        if after["outside"] > 0:
            fails.append(f"{after['outside']} vertices still outside the skin")
        if mode == "under_inner_sheet" and after["in_slab"] > 0:
            fails.append(f"{after['in_slab']} vertices still in the skin slab")
        if fg["flipped_pct_moved_faces"] > FLIP_MAX:
            fails.append(f"flipped {fg['flipped_pct_moved_faces']} % of moved faces")
        if fg["stretched_pct"][1] > fg["stretched_pct"][0] + STRETCH_ADD:
            fails.append(f"stretched {fg['stretched_pct']}")
        if b1 > b0:
            fails.append(f"moved vertices inside bone {b0} -> {b1}")
        dv = vol_change(fg)
        if dv is not None and dv > VOL_MAX:
            fails.append(f"volume change {dv:.1f} %")
        res.setdefault("tries", []).append(dict(mode=mode, direction_sigma_mm=sig, displacement=stats(D), after=after, guards=fg, inside_bone=[b0, b1],
                                                volume_change_pct=(None if dv is None else round(dv, 2)), fails=fails))
        if not fails:
            res.update(ships=True, mode=mode, displacement=stats(D), after=after, guards=fg, inside_bone=[b0, b1],
                       volume_change_pct=(None if dv is None else round(dv, 2)))
            g.cur[k] = v
            break
    else:
        res.update(ships=False, reason="; ".join(res["tries"][-1]["fails"]))
    log(f"    tuck {k}: outside {before['outside']} / in slab {before['in_slab']} (max {before['max_out_mm']} mm) -> "
        + (f"SHIPS ({res['mode']}, max {res['displacement']['max_mm']} mm)" if res["ships"] else f"KEPT ({res.get('reason')})"))
    return res


# ------------------------------------------------------------------ vulva
def run_vulva(g: Geo, k, log, variant="both"):
    v0 = g.cur[k].copy(); f = g.F[k]
    lo, hi = g.box(k, 20.0)
    neigh = [n for n in g.in_box(lo, hi, sys_=("skin",), exclude={k}) if "nail_plate" not in n]
    sk = SkinSet(g, neigh)
    cls, _ = g.sheets(k)
    outer_v = np.unique(f[cls == 1])
    # neighbour thickness at each neighbour outer face: distance to its inner sheet
    v = v0.copy()
    hist = []
    for rnd in range(VU_ROUNDS):
        P = v[outer_v]
        s, n, q, tri = sk.s_out(P)
        tang = np.linalg.norm((P - q) - s[:, None] * n, axis=1)
        cov = tang < 0.6
        si, _ = sk.s_in(P)
        thick = s - si                       # outer-to-inner sheet distance of the neighbour along its normal
        lo_t = -(np.clip(thick, 1.5, 4.0) + VU_LO)
        tgt = np.clip(s, lo_t, -VU_HI)
        dl = np.where(cov, tgt - s, 0.0)
        if variant == "push":
            dl = np.minimum(dl, 0.0)
        elif variant == "lift":
            dl = np.maximum(dl, 0.0)
        dl = np.clip(dl, -CAP_VULVA, CAP_VULVA)
        if rnd == 0:
            hist.append(dict(covered=int(cov.sum()), outer_vertices=int(len(P)),
                             in_front_of_neighbour=int((cov & (s > 0)).sum()), max_in_front_mm=round(float(s[cov].max()), 2),
                             deeper_than_neighbour_inner=int((cov & (s < lo_t)).sum()), max_deep_mm=round(float(-s[cov].min()), 2),
                             need_over_cap=int((cov & (np.abs(tgt - s) > CAP_VULVA)).sum())))
        dvec = dl[:, None] * n
        act = cov
        D = shepard(v, P[act], dvec[act], sig=SIG, fall=VU_FALL)
        D[outer_v[act]] = dvec[act]
        v = v + D
    D = v - v0
    n_ = np.linalg.norm(D, axis=1)
    over = n_ > CAP_VULVA
    v[over] = v0[over] + D[over] * (CAP_VULVA / n_[over])[:, None]
    P = v[outer_v]
    s, n, q, tri = sk.s_out(P)
    tang = np.linalg.norm((P - q) - s[:, None] * n, axis=1)
    cov = tang < 0.6
    si, _ = sk.s_in(P)
    lo_t = -(np.clip(s - si, 1.5, 4.0) + VU_LO)
    after = dict(covered=int(cov.sum()), in_front_of_neighbour=int((cov & (s > 0)).sum()),
                 max_in_front_mm=round(float(max(s[cov].max(), 0)), 2), deeper_than_neighbour_inner=int((cov & (s < lo_t - 0.05)).sum()),
                 max_deep_mm=round(float(-s[cov].min()), 2))
    fg = face_guards(v0, v, f, sel=cls == 1)
    fails = []
    if fg["flipped_pct_moved_faces"] > FLIP_MAX:
        fails.append(f"flipped {fg['flipped_pct_moved_faces']} % of moved faces")
    if fg["stretched_pct"][1] > fg["stretched_pct"][0] + STRETCH_ADD:
        fails.append(f"stretched {fg['stretched_pct']}")
    dv = vol_change(fg)
    if dv is not None and dv > VOL_MAX:
        fails.append(f"volume change {dv:.1f} %")
    res = dict(variant=variant, neighbours=neigh, before=hist[0], after=after, displacement=stats(v - v0), guards=fg, volume_change_pct=(None if dv is None else round(dv, 2)),
               fails=fails, ships=not fails)
    if not fails:
        g.cur[k] = v
    log(f"    vulva {k}: in front of a neighbour {hist[0]['in_front_of_neighbour']} -> {after['in_front_of_neighbour']} vertices, "
        f"deeper than its inner sheet {hist[0]['deeper_than_neighbour_inner']} -> {after['deeper_than_neighbour_inner']}, "
        f"max move {res['displacement']['max_mm']} mm -> {'SHIPS' if not fails else 'KEPT (' + '; '.join(fails) + ')'}")
    return res, neigh


# ------------------------------------------------------------------ metrics
def ring_open(g: Geo, ylo=-140.0, yhi=-40.0, P=1.5, K=2):
    """the Q337 sweep's ring test on the skin (axial slices whose skin outline does not close), in [ylo, yhi]"""
    from scipy import ndimage
    ids = [k for k in g.M if g.sys[k] == "skin"]
    V, Fs, n = [], [], 0
    for k in ids:
        v = g.cur[k]
        if v[:, 1].max() < ylo - 5 or v[:, 1].min() > yhi + 5:
            continue
        V.append(v); Fs.append(g.F[k] + n); n += len(v)
    tm = trimesh.Trimesh(np.vstack(V), np.vstack(Fs), process=False)
    sp, _ = trimesh.sample.sample_surface(tm, int(tm.area * 4), seed=2)
    sp = sp[(sp[:, 1] >= ylo) & (sp[:, 1] <= yhi)]
    lo = sp.min(0) - 12; hi = sp.max(0) + 12
    shp = np.ceil((hi - lo) / P).astype(int) + 1
    occ = np.zeros(shp, bool)
    ijk = np.floor((sp - lo) / P).astype(int); occ[ijk[:, 0], ijk[:, 1], ijk[:, 2]] = True
    st = ndimage.generate_binary_structure(3, 1)
    d = ndimage.binary_dilation(occ, st, iterations=K)
    lev = []
    for j in range(shp[1]):
        sl = d[:, j, :]
        if not sl.any():
            continue
        fl = ndimage.binary_fill_holes(sl)
        if fl.sum() < sl.sum() * 1.15 and sl.sum() > 200:
            lev.append(round(float(lo[1] + j * P)))
    return lev


def mirror_err(g: Geo, k):
    o = k[:-2] + ("_l" if k.endswith("_r") else "_r")
    if not (k.endswith(("_r", "_l")) and o in g.M) or len(g.cur[o]) != len(g.cur[k]):
        return None, None
    m = g.cur[o] * np.array([-1, 1, 1])
    d, _ = cKDTree(m).query(g.cur[k])
    m0 = g.V0[o][0] * np.array([-1, 1, 1])
    d0, _ = cKDTree(m0).query(g.V0[k][0])
    return float(np.median(d0)), float(np.median(d))


def worse_than(b, a):
    """a structure is made worse when it gains more than GAIN_TOL vertices outside the skin; one already far outside (a known,
    separate defect, >= 100 vertices) only when it gains more than 2 % of them"""
    g_ = a["outside"] - b["outside"]
    return g_ > GAIN_TOL and (b["outside"] < 100 or g_ > 0.02 * b["outside"])


# ------------------------------------------------------------------ steps
def run_step(g: Geo, step, log):
    """the perineum step tries the vulva rule in full, then its two halves (push down only / lift only); the first variant whose
    step passes every guard ships"""
    if not STEPS[step].get("vulva"):
        return run_step1(g, step, log)
    tried = []
    for variant in VULVA_VARIANTS:
        r = run_step1(g, step, log, variant)
        tried.append(dict(variant=variant, ships=r["ships"], vulva_fails=r.get("vulva", {}).get("fails"),
                          outside_skin_gained=r.get("outside_skin_gained")))
        if r["ships"] and r["vulva"]["ships"]:
            break
        sn = r.pop("_snap", None)            # this variant leaves nothing behind (a failed step has restored itself)
        if sn is not None:
            g.cur.update(sn)
    r["variants_tried"] = tried
    return r


def run_step1(g: Geo, step, log, variant="both"):
    cfg = STEPS[step]
    rep = dict(step=step)
    snap = {k: v.copy() for k, v in g.cur.items()}
    touched = set(cfg["seam"]) | set(cfg["tuck"]) | ({cfg["vulva"]} if cfg.get("vulva") else set())
    # region box and the structures checked against the skin there
    ids = [k for k in touched if k in g.M]
    lo = np.min([g.box(k)[0] for k in ids], 0) - 15
    hi = np.max([g.box(k)[1] for k in ids], 0) + 15
    skin_ids = [k for k in g.in_box(lo, hi, sys_=("skin",)) if "nail_plate" not in k]
    under = [k for k in g.in_box(lo, hi, sys_=VISIBLE_SYS) if k not in touched]     # the fat layer is off by default; its own defects are not this round's
    sk0 = SkinSet(g, skin_ids)
    pokes0 = {k: outside_count(g, sk0, k) for k in under}
    if cfg["seam"]:
        # a region failing its guards is kept as it is and becomes a fixed neighbour; the others are redone against it (a half-way
        # move toward a region that then stays put would open a new gap)
        movable = [k for k in cfg["seam"] if k in g.M]
        kept = {}
        for it in range(6):
            log(f"  [{step}] seams over {len(movable)} regions (pass {it + 1})")
            seams, anchors, start = run_seams(g, movable, log if it == 0 else (lambda *_: None))
            guards, fails_now = {}, {}
            for k in movable:
                fg = face_guards(start[k], g.cur[k], g.F[k], sel=g.sheets(k)[0] == 1)
                fails = []
                if fg["flipped_pct_moved_faces"] > FLIP_MAX:
                    fails.append(f"flipped {fg['flipped_pct_moved_faces']} %")
                if fg["stretched_pct"][1] > fg["stretched_pct"][0] + STRETCH_ADD:
                    fails.append(f"stretched {fg['stretched_pct']}")
                dv = vol_change(fg)
                if dv is not None and dv > SLAB_VOL_MAX:
                    fails.append(f"slab volume change {dv:.1f} %")
                guards[k] = dict(fg, displacement=stats(g.cur[k] - start[k]), volume_change_pct=(None if dv is None else round(dv, 2)), fails=fails)
                if fails:
                    fails_now[k] = fails
            if not fails_now:
                break
            for k in movable:
                g.cur[k] = start[k].copy()
            for k, fl in fails_now.items():
                kept[k] = dict(fails=fl, guards=guards[k], pass_=it + 1)
                log(f"    seam {k} KEPT: {'; '.join(fl)}")
            movable = [k for k in movable if k not in fails_now]
            if not movable:
                seams, guards = {}, {}
                break
        rep["seams"], rep["seam_anchors"], rep["seam_guards"], rep["seam_kept"] = seams, anchors, guards, kept
        for k, s in seams.items():
            log(f"    seam {k}: gap median {s['border_gap_before_mm']['median']} -> {s['border_gap_after_mm']['median']} mm, "
                f">1.5 mm {s['border_gap_before_mm']['over_1_5mm']} -> {s['border_gap_after_mm']['over_1_5mm']}, "
                f"max move {guards[k]['displacement']['max_mm']} mm")
    if cfg.get("vulva"):
        log(f"  [{step}] vulvar patch")
        rep["vulva"], _ = run_vulva(g, cfg["vulva"], log, variant)
    sk = SkinSet(g, skin_ids)
    bones = Bones(g, lo, hi)
    # structures that gained vertices outside the moved skin are tucked as well (the same guarded rule)
    gained = [k for k in under if worse_than(pokes0[k], outside_count(g, sk, k))]
    tl = [k for k in cfg["tuck"] if k in g.M] + [k for k in gained if k not in cfg["tuck"]]
    rep["tuck"] = {}
    if tl:
        log(f"  [{step}] tuck {len(tl)} structures ({len(gained)} gained vertices outside the moved skin)")
    done = set()
    for k in tl:
        if k in done:
            continue
        o = k[:-2] + ("_l" if k.endswith("_r") else "_r")
        a0, _ = mirror_err(g, k)
        if o in tl and a0 is not None and a0 < 0.1:
            # exact mirror twins (Z-Anatomy): the same rule must pass on both sides, else both stay (as Q349)
            v0k, v0o = g.cur[k].copy(), g.cur[o].copy()
            for tr in TUCK_TRIES:
                rk = run_tuck(g, k, sk, bones, lambda *_: None, tries=[tr])
                ro = run_tuck(g, o, sk, bones, lambda *_: None, tries=[tr])
                if rk["ships"] and ro["ships"]:
                    break
                g.cur[k], g.cur[o] = v0k.copy(), v0o.copy()
            else:
                rk = run_tuck(g, k, sk, bones, lambda *_: None)
                ro = run_tuck(g, o, sk, bones, lambda *_: None)
                if rk["ships"] != ro["ships"] or (rk["ships"] and rk["mode"] != ro["mode"]):
                    for x, r in ((k, rk), (o, ro)):
                        if r["ships"]:
                            r.update(ships=False, reason="its mirror twin fails every try (left and right are kept mirror images)")
                g.cur[k], g.cur[o] = v0k.copy(), v0o.copy()
                if rk["ships"] and ro["ships"]:     # both pass but by different tries: keep both as they are (not mirror images)
                    rk.update(ships=False, reason="the twins pass only by different tries; kept as mirror images")
                    ro.update(ships=False, reason=rk["reason"])
            for x, r in ((k, rk), (o, ro)):
                rep["tuck"][x] = dict(r, listed=x in cfg["tuck"], mirror_pair=[k, o])
                b = r["before"]
                log(f"    tuck {x}: outside {b['outside']} / in slab {b['in_slab']} (max {b['max_out_mm']} mm) -> "
                    + (f"SHIPS ({r['mode']}, max {r['displacement']['max_mm']} mm)" if r["ships"] else
                       f"KEPT ({r.get('reason') or '; '.join(r['tries'][-1]['fails'])})"))
            done |= {k, o}
            continue
        rep["tuck"][k] = run_tuck(g, k, sk, bones, log)
        rep["tuck"][k]["listed"] = k in cfg["tuck"]
        done.add(k)
    # region guard: nothing gains vertices outside the skin
    worse = {}
    for k in under:
        a = outside_count(g, sk, k)
        if worse_than(pokes0[k], a):
            worse[k] = [pokes0[k]["outside"], a["outside"]]
        elif a["outside"] > pokes0[k]["outside"]:
            rep.setdefault("outside_skin_gained_within_tolerance", {})[k] = [pokes0[k]["outside"], a["outside"]]
    rep["outside_skin_gained"] = worse
    rep["outside_skin_region"] = {k: [pokes0[k], outside_count(g, sk, k)] for k in under if pokes0[k]["outside"]}
    if worse:
        log(f"  [{step}] GUARD: {len(worse)} structures gain vertices outside the skin: {sorted(worse)[:8]} -> step kept")
        g.cur.update({k: snap[k] for k in g.cur})
        rep["ships"] = False
        return rep
    # mirror sanity for L/R pairs that were exact mirrors
    rep["mirror"] = {}
    for k in sorted(touched):
        if k not in g.M or np.abs(g.cur[k] - snap[k]).max() < 1e-6:
            continue
        a, b = mirror_err(g, k)
        if a is not None:
            rep["mirror"][k] = [round(a, 3), round(b, 3)]
            if a < 0.1 and b > MIRROR_MAX:
                log(f"    mirror guard: {k} median mirror distance {a:.2f} -> {b:.2f} mm (kept)")
                g.cur[k] = snap[k]
    rep["ships"] = True
    rep["_snap"] = snap
    return rep


def note_for(step, k, srep):
    if step in ("chest", "back") and k in srep.get("seams", {}):
        s = srep["seam_guards"][k]["displacement"]
        return (f"{tag(step)} border joined to the neighbouring skin regions (this body's regions were refitted one by one and no longer "
                f"met: a crease and gaps along the border); outer border matched to the neighbours' border, the move spread over "
                f"{FALL:g} mm from the border, max {s['max_mm']} mm (cap {CAP_SEAM:g}); mesh, vertex and triangle counts unchanged.")
    if step == "perineum" and k == STEPS["perineum"]["vulva"]:
        s = srep["vulva"]["displacement"]
        return (f"{tag(step)} the patch border is held just under the neighbouring skin regions (it crossed their surface in places and "
                f"lay deeper than their inner surface elsewhere); rule-based, max {s['max_mm']} mm (cap {CAP_VULVA:g}); the CVH surface "
                f"shape, vertex and triangle counts are unchanged elsewhere.")
    t = srep["tuck"][k]
    return (f"{tag(step)} the part lying in or outside the skin moved inward along the skin's normal until it lies under the skin "
            f"({t['mode'].replace('_', ' ')}); rule-based, max {t['displacement']['max_mm']} mm (cap {CAP_TUCK:g}), volume change "
            f"{t['volume_change_pct']} %; mesh, vertex and triangle counts unchanged.")


def write_page(d: Path, stem, man_old, man_new, blob_new, old_files):
    B = C340.B
    pages = C340.pages_of(d, stem)
    texts = {p: p.read_text(encoding="utf-8") for p in pages}
    for p, t in texts.items():
        assert C340.LIT["manifest"].search(t).group(1) == C340.ser_manifest(man_old), f"{p}: manifest serialisation differs"
        assert C340.LIT["files"].search(t).group(1) == json.dumps(old_files), f"{p}: file list serialisation differs"
    chunks = B.split_blob(blob_new, stem)
    assert [n for n, _ in chunks] == [f["path"] for f in old_files], "geo file set would change; not handled"
    files = [{"path": n, "bytes": len(c), "enc": "base64"} for n, c in chunks]
    import base64
    changed = []
    for n, c in chunks:
        p = d / n
        new = base64.b64encode(c)
        if p.read_bytes() != new:
            bk = p.with_name(p.name + ".q353")
            if not bk.exists():
                shutil.copy2(p, bk)
            p.write_bytes(new); changed.append(n)
    for p, t in texts.items():
        bk = p.with_name(p.name + ".q353")
        if not bk.exists():
            shutil.copy2(p, bk)
        t2 = C340.LIT["manifest"].sub(lambda _m: "window.__ANATOMY_MANIFEST__=" + C340.ser_manifest(man_new) + ";", t, count=1)
        t2 = C340.LIT["files"].sub(lambda _m: "window.__ANATOMY_BIN_FILES__=" + json.dumps(files) + ";", t2, count=1)
        p.write_text(t2, encoding="utf-8"); changed.append(p.name)
    return changed


def jsonable(o):
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, (np.floating, np.integer)):
        return o.item()
    return str(o)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--page-dir", required=True)
    ap.add_argument("--steps", default="chest,back,head,perineum")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--json", default=str(OUT))
    a = ap.parse_args(argv)
    d = Path(a.page_dir).resolve()
    g = Geo(d)
    if g.stem not in STEMS:
        print(f"Q353 is for Base · Female only ({g.stem}); nothing done")
        return 2
    t0 = time.time()
    rep = dict(schema="nmsk.q353.skin.v1", round="Q353", generated=time.strftime("%Y-%m-%d"), page_dir=str(d), page=g.stem,
               written=bool(a.write), rule_based=True,
               parameters=dict(match_mm=MATCH, cap_seam_mm=CAP_SEAM, sigma_mm=SIG, fall_mm=FALL, seam_rounds=SEAM_ROUNDS, gap_mm=GAP,
                               hide_mm=HIDE, envelope_slope=K_ENV, cap_tuck_mm=CAP_TUCK, vulva_hi_mm=VU_HI, vulva_lo_mm=VU_LO,
                               cap_vulva_mm=CAP_VULVA, flip_max_pct=FLIP_MAX, stretch_add_pts=STRETCH_ADD, vol_max_pct=VOL_MAX,
                               mirror_max_mm=MIRROR_MAX, steps=STEPS),
               steps={})
    recs = {m["id"]: m.get("rec") for m in g.man["meshes"]}
    steps = [s.strip() for s in a.steps.split(",") if s.strip()]
    owner = {}
    if "perineum" in steps:
        rep["ring_open_before"] = ring_open(g)
    for st in steps:
        done = [k for k, r in recs.items() if tag(st) in ((r or {}).get("procedural_badge") or "")]
        if done:
            print(f"-- {st}: already applied ({len(done)} structures carry '{tag(st)}', e.g. {done[0]}); skipped")
            rep["steps"][st] = dict(skipped="already applied", structures=done)
            continue
        print(f"-- {st}")
        before = {k: v.copy() for k, v in g.cur.items()}
        rep["steps"][st] = run_step(g, st, print)
        rep["steps"][st].pop("_snap", None)
        for k in g.cur:
            if np.abs(g.cur[k] - before[k]).max() > 1e-6:
                owner.setdefault(k, []).append(st)
    if "perineum" in steps:
        rep["ring_open_after"] = ring_open(g)
    replace, rep["structures"] = {}, {}
    for k, sts in sorted(owner.items()):
        v0, f = g.V0[k]
        v1 = g.cur[k]
        rec = recs[k]
        for st in sts:
            rec = C340.badge_add(rec, note_for(st, k, rep["steps"][st]))
        replace[k] = (v1, f, rec)
        rep["structures"][k] = dict(steps=sts, sys=g.sys[k], vertices=len(v0), faces=len(f), displacement=stats(v1 - v0),
                                    **face_guards(v0, v1, f), card=rec["procedural_badge"])
    rep["geometry_changed"] = sorted(replace)
    if replace:
        man2, blob2 = C340.repack(g.man, g.blob, replace)
        for m0, m1 in zip(g.man["meshes"], man2["meshes"]):
            assert m0["id"] == m1["id"] and m0["vc"] == m1["vc"] and m0["ic"] == m1["ic"]
        assert len(blob2) == len(g.blob)
        if a.write:
            rep["files_changed"] = write_page(d, g.stem, g.man, man2, blob2, g.files)
            print("  wrote: " + ", ".join(rep["files_changed"]) + " (originals kept as *.q353)")
    rep["seconds"] = round(time.time() - t0, 1)
    jp = Path(a.json)
    allr = json.loads(jp.read_text(encoding="utf-8")) if jp.exists() else {}
    if allr.get("schema") != "nmsk.q353.skin_report.v1":
        allr = {"schema": "nmsk.q353.skin_report.v1", "pages": {}}
    allr["pages"][g.stem] = rep
    jp.parent.mkdir(parents=True, exist_ok=True)
    jp.write_text(json.dumps(allr, indent=1, default=jsonable), encoding="utf-8")
    print(f"Q353 {'WRITTEN' if a.write else 'DRY RUN'}: {len(replace)} structures changed -> {jp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
