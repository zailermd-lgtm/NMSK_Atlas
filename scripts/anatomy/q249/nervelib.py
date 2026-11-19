"""Q249: tools for rule-based nerve tubes: spline through waypoints, push out of bones / soft structures, round tube with taper + end caps, measurement and guards.
A nerve is a dict: id, name, latin, side ('l','r','m'), anchors (list of 3-vectors, atlas frame mm), d (diameter mm or (d_start, d_end)), plus the documentation fields (course / calibre / error); build_nerve() adds V, F, report, status, held."""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np, trimesh
from scipy.interpolate import splprep, splev
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent; REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "scripts/anatomy/q248"))
import lig_pages as PG, rulelig as RL, guards as GD  # noqa: E402

CLEAR_EXTRA = 0.3
MAX_BONE_FRAC = 0.20            # a nerve with more than 20 % of its (raw) length inside bone is held
MAX_MUSCLE_FRAC_OWN = 0.45      # report only for Z pages; own pages: held above this (nerves lie in fascial planes between muscles)
NSEG = 10


def spline(anchors, n=60, smooth=0.0):
    """cubic spline through the anchors (chord-length parametrised), sampled uniformly in arc length -> (n,3)"""
    A = np.asarray(anchors, float)
    keep = [0] + [i for i in range(1, len(A)) if np.linalg.norm(A[i] - A[i - 1]) > 0.25]
    A = A[keep]
    if len(A) == 2:
        P = A[0] + (A[1] - A[0]) * np.linspace(0, 1, n)[:, None]
        return P
    k = min(3, len(A) - 1)
    tck, u = splprep(A.T, k=k, s=smooth)
    uu = np.linspace(0, 1, 400)
    X = np.stack(splev(uu, tck), 1)
    s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(X, axis=0), axis=1))]
    t = np.linspace(0, s[-1], n)
    return np.stack([np.interp(t, s, X[:, i]) for i in range(3)], 1)


def path_len(P):
    return float(np.linalg.norm(np.diff(P, axis=0), axis=1).sum())


def smooth_ends_fixed(P, it=3):
    return RL.smooth_path(P, it)


def push_out_bones(ctx, P, rad, loops=6, keep=(0, -1)):
    """move interior points out of the bones to signed distance >= rad + 0.3, smooth, ends stay"""
    P = P.copy()
    ids = ctx.near_bones(P, 25.0)
    for _ in range(loops):
        sd, a, nr, pt = ctx.bf.signed(P, ids)
        need = rad + CLEAR_EXTRA
        bad = sd < need
        for k in keep:
            bad[k] = False
        if not bad.any():
            break
        P[bad] += nr[bad] * (need[bad] - sd[bad])[:, None] if np.ndim(need) else nr[bad] * (need - sd[bad])[:, None]
        P = RL.smooth_path(P, 2)
    return P


class Soft:
    """closed muscle / organ surfaces of the page as sample clouds with outward normals: push points outside (margin) or onto the surface"""
    def __init__(self, E, gd):
        self.E, self.gd = E, gd

    def field(self, i):
        return self.gd._field(i)

    def signed(self, i, P):
        kd, nn = self.field(i)
        d, k = kd.query(np.atleast_2d(P))
        s = ((np.atleast_2d(P) - kd.data[k]) * nn[k]).sum(1)
        return np.where(s < 0, -d, d), kd.data[k], nn[k]

    def outside(self, i, P, margin=0.3, loops=4):
        P = np.atleast_2d(P).copy()
        for _ in range(loops):
            sd, pt, n = self.signed(i, P)
            mg = np.broadcast_to(np.asarray(margin, float), (len(P),))
            bad = sd < mg
            if not bad.any():
                break
            P[bad] += n[bad] * (mg[bad] - sd[bad])[:, None]
        return P

    def surface_point(self, i, P, margin=0.0, direction=None, thr=0.2, maxdist=None):
        """nearest surface point of structure i to P, offset outward by margin; -> (point, outward normal).  direction: only surface samples whose outward normal . direction > thr (e.g. the medial surface of a muscle)"""
        kd, nn = self.field(i)
        if direction is not None:
            key = (i, tuple(np.round(direction, 3)), thr)
            if not hasattr(self, "_sub"): self._sub = {}
            if key not in self._sub:
                sel = (nn @ np.asarray(direction, float)) > thr
                self._sub[key] = (cKDTree(kd.data[sel]), nn[sel]) if sel.sum() > 20 else (kd, nn)
            kd, nn = self._sub[key]
        d, k = kd.query(np.atleast_2d(P)[0])
        if maxdist is not None and d > maxdist:
            return None, None
        return kd.data[k] + nn[k] * margin, nn[k]


def tube_round(P, d0, d1=None, nseg=NSEG):
    """closed round tube along the path (n,3): parallel-transport (Bishop) frame, diameter d0 (or d0 -> d1 linearly), nseg vertices per ring, end caps at the end points.  -> V, F, cap0 index, cap1 index, diameters (n,)"""
    P = np.asarray(P, float); n = len(P)
    d = np.full(n, float(d0)) if d1 is None else np.linspace(d0, d1, n)
    T = np.gradient(P, axis=0); T /= np.linalg.norm(T, axis=1, keepdims=True) + 1e-12
    a = np.eye(3)[np.argmin(np.abs(T[0]))]
    W = np.zeros((n, 3)); W[0] = a - (a @ T[0]) * T[0]; W[0] /= np.linalg.norm(W[0])
    for i in range(1, n):
        w = W[i - 1] - (W[i - 1] @ T[i]) * T[i]
        nw = np.linalg.norm(w)
        W[i] = w / nw if nw > 1e-9 else W[i - 1]
    N = np.cross(T, W)
    th = np.linspace(0, 2 * np.pi, nseg, endpoint=False)
    V = (P[:, None, :] + 0.5 * d[:, None, None] * (np.cos(th)[None, :, None] * W[:, None, :] + np.sin(th)[None, :, None] * N[:, None, :])).reshape(-1, 3)
    F = []
    for i in range(n - 1):
        for k in range(nseg):
            a_, b_ = i * nseg + k, i * nseg + (k + 1) % nseg
            c_, e_ = (i + 1) * nseg + k, (i + 1) * nseg + (k + 1) % nseg
            F += [[a_, b_, e_], [a_, e_, c_]]
    c0, c1 = len(V), len(V) + 1
    V = np.vstack([V, P[0], P[-1]])
    for k in range(nseg):
        F.append([c0, (k + 1) % nseg, k]); F.append([c1, (n - 1) * nseg + k, (n - 1) * nseg + (k + 1) % nseg])
    F = np.array(F)
    if trimesh.Trimesh(V, F, process=False).volume < 0:
        F = F[:, ::-1]
    return V, F, c0, c1, d


def measure_tube(ctx, gd, V, F, c0, c1, P, d, *, gate_soft, min_skin, extra_bone_ids=None):
    ids = ctx.near_bones(V, 4.0)
    sd = ctx.bf.signed(V, ids)[0] if ids else np.full(len(V), 9.0)
    m = trimesh.Trimesh(V, F, process=False)
    rep = dict(vertices=int(len(V)), triangles=int(len(F)), watertight=bool(m.is_watertight), volume_mm3=round(float(abs(m.volume)), 1), volume_cm3=round(float(abs(m.volume)) / 1000, 4),
               min_signed_distance_to_bone_mm=round(float(sd.min()), 2), vertices_deeper_1mm_in_bone=int((sd < -1.0).sum()))
    ov = gd.overlap(V)
    rep["soft_overlap"] = ov
    rep["skin_min_depth_mm"] = gd.skin_depth(V)
    return rep


class Overlap:
    """soft-tissue overlap by ray parity (trimesh.contains) on the closed muscles / organs of the page; depth from the sampled surface.  Thin open sheets are skipped (no inside)."""
    def __init__(self, E, gd):
        self.E, self.gd = E, gd; self._m = {}

    def mesh(self, i):
        if i not in self._m:
            m = PG.mesh(self.E[i]); self._m[i] = m if m.is_watertight else None
        return self._m[i]

    def __call__(self, V):
        lo, hi = V.min(0) - 8, V.max(0) + 8
        dm = np.zeros(len(V), bool); do = np.zeros(len(V), bool); who = {}
        for i, e in self.E.items():
            if e["sys"] not in ("muscle", "organ", "viscera") or len(e["f"]) <= 20 or "zfill" in i:
                continue
            a, b = e["v"].min(0), e["v"].max(0)
            if not ((a <= hi).all() and (b >= lo).all()):
                continue
            m = self.mesh(i)
            if m is None:
                continue
            cand = np.where(((V >= a - 1) & (V <= b + 1)).all(1))[0]
            if not len(cand):
                continue
            try:
                ins = m.contains(V[cand])
            except Exception:  # noqa: BLE001
                continue
            if not ins.any():
                continue
            kd, nn = self.gd._field(i)
            d, _ = kd.query(V[cand[ins]])
            org = e["sys"] != "muscle"
            deep = d > (GD.ORGAN_DEEP_MM if org else GD.MUSCLE_DEEP_MM)
            if deep.any():
                who[i] = int(deep.sum()); (do if org else dm)[cand[ins][deep]] = True
        return dict(muscle_fraction_deeper_6mm=round(float(dm.mean()), 3), organ_fraction_deeper_3mm=round(float(do.mean()), 3), top=dict(sorted(who.items(), key=lambda x: -x[1])[:4]))


def finish_bones(ctx, V, F, c0, c1, iters=5, tol=0.8):
    """push every tube vertex deeper than `tol` mm inside a bone back out (end-cap centres stay), repeat until none is left or iters used up"""
    V = V.copy(); ids = ctx.near_bones(V, 6.0); moved = 0
    for _ in range(iters):
        sd, a, nr, pt = ctx.bf.signed(V, ids) if ids else (np.full(len(V), 9.0), 0, np.zeros((len(V), 3)), 0)
        deep = sd < -tol; deep[[c0, c1]] = False
        if not deep.any():
            break
        moved += int(deep.sum())
        V[deep] += nr[deep] * (-sd[deep] + 0.3)[:, None]
    sd = ctx.bf.signed(V, ids)[0] if ids else np.full(len(V), 9.0)
    return V, dict(pushed_out_of_bone=moved, min_signed_distance_mm=round(float(sd.min()), 2), vertices_deeper_1mm=int((sd < -1.0).sum()))
