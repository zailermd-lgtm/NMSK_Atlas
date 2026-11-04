"""Q217: volume-conserving mutual separation of neighbouring muscle meshes (the 'slide apart' solver), inside his skin and off his bones.

Every muscle mesh (v, f) gets a signed distance field (0.5 mm voxels of its filled solid, negative inside).  Per round each vertex that is closer than the gap to another muscle (or inside it), to a bone, or
outside the skin gets a target displacement along the gradient of that field (exactly the amount that clears it); the displacement field of the WHOLE muscle is then solved with a graph-Laplacian smoothness
term (stiff first: nearly a translation of the whole belly, then more local), so a muscle is carried away from its neighbour instead of being dented (a dent = shrinking).  Vertices at anchors (the part of
the muscle outside the working window, the attachment zones that must stay on their bone) are held.  Muscle | muscle gap = FASCIA_MM (1.0 mm, the Q162 interface rule: each takes half)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi
from scipy.ndimage import map_coordinates
from scipy.sparse import diags, identity
from scipy.sparse.linalg import spsolve

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.transfer.q216_common import VoxGrid  # noqa: E402
from scripts.transfer.q213_inbone import laplacian  # noqa: E402

FASCIA_MM = 1.0
H = 0.5


class SDF:
    """signed distance (mm, + outside) of a filled mesh on a local 0.5 mm grid; sample(p) trilinear; outside the grid = +big"""

    def __init__(self, v, f, h=H, pad=6.0, clip=None, solid=None, lo=None):
        v = np.asarray(v, float)
        lo_ = v.min(0) - pad if lo is None else lo
        hi_ = v.max(0) + pad
        if clip is not None:
            lo_, hi_ = np.maximum(lo_, clip[0]), np.minimum(hi_, clip[1])
        self.h = h
        g = VoxGrid(lo_, hi_, h)
        self.lo = g.lo
        s = g.solid(v, np.asarray(f, np.int64)) if solid is None else solid
        self.shape = s.shape
        din = ndi.distance_transform_edt(s, sampling=h)
        dout = ndi.distance_transform_edt(~s, sampling=h)
        self.phi = np.where(s, -(din - h / 2), dout - h / 2).astype(np.float32)
        self.solid = s

    @classmethod
    def from_solid(cls, solid, lo, h=H):
        o = cls.__new__(cls)
        o.h, o.lo, o.shape, o.solid = h, np.asarray(lo, float), solid.shape, solid
        din = ndi.distance_transform_edt(solid, sampling=h)
        dout = ndi.distance_transform_edt(~solid, sampling=h)
        o.phi = np.where(solid, -(din - h / 2), dout - h / 2).astype(np.float32)
        return o

    def contains_box(self, p, margin=0.0):
        i = (np.asarray(p) - self.lo) / self.h
        return ((i >= -margin) & (i <= np.asarray(self.shape) - 1 + margin)).all(1)

    def sample(self, p, big=30.0):
        p = np.atleast_2d(p)
        i = (p - self.lo) / self.h
        inb = ((i >= 0) & (i <= np.asarray(self.shape) - 1)).all(1)
        out = np.full(len(p), big, np.float32)
        if inb.any():
            out[inb] = map_coordinates(self.phi, i[inb].T, order=1, mode="nearest")
        return out

    def grad(self, p, e=0.6):
        g = np.zeros((len(p), 3), np.float32)
        for k in range(3):
            d = np.zeros(3)
            d[k] = e
            g[:, k] = (self.sample(p + d) - self.sample(p - d)) / (2 * e)
        n = np.linalg.norm(g, axis=1, keepdims=True)
        return g / np.maximum(n, 1e-6)


def solve_disp(Lap, w, T, lam, anchor_w, tether=1e-3):
    """displacement field d minimising sum w |d - T|^2 + sum anchor |d|^2 + lam sum_edges |d_i - d_j|^2 + tether |d|^2"""
    n = Lap.shape[0]
    M = (diags(w + anchor_w) + lam * Lap + tether * identity(n)).tocsc()
    return np.column_stack([spsolve(M, w * T[:, k]) for k in range(3)])


def volume(v, f):
    t = v[f]
    return abs(float(np.einsum("ij,ij->", t[:, 0], np.cross(t[:, 1], t[:, 2])) / 6.0)) / 1000.0


# ------------------------------------------------------------------------------------------------ the solver
BOX_LO = np.array([-280.0, 94.0, -90.0])
BOX_HI = np.array([-130.0, 308.0, 150.0])


def smooth_ramp(y, y0, width):
    """1 at y <= y0, 0 at y >= y0 + width (smoothstep)"""
    t = np.clip((np.asarray(y) - y0) / width, 0.0, 1.0)
    return 1.0 - (3 * t * t - 2 * t ** 3)


def overlap_report(solids, ids):
    """per muscle: share (%) of its voxels inside another muscle of `solids` (dict id -> (lo_idx, bool array) as global-grid bool volumes)"""
    cnt = None
    for i in ids:
        s = solids[i].astype(np.uint8)
        cnt = s if cnt is None else cnt + s
    rows = {}
    for i in ids:
        n = int(solids[i].sum())
        rows[i] = dict(vol_cm3=round(n * H ** 3 / 1000.0, 2), shared_pct=round(100.0 * float((solids[i] & (cnt > 1)).sum()) / max(n, 1), 1))
    return rows, float((cnt > 1).sum()) * H ** 3 / 1000.0


def surface_samples(v, f, spacing=0.5, cap=400000):
    """dense surface samples of a triangle mesh (barycentric lattices, ~spacing apart)"""
    v = np.asarray(v, float)
    f = np.asarray(f, np.int64)
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    area = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
    k = np.clip(np.ceil(np.sqrt(area) / spacing).astype(int), 1, 40)
    out = [v]
    for kk in np.unique(k):
        sel = np.flatnonzero(k == kk)
        if kk == 1:
            out.append((a[sel] + b[sel] + c[sel]) / 3.0)
            continue
        ii, jj = np.meshgrid(np.arange(kk + 1), np.arange(kk + 1), indexing="ij")
        m = ii + jj <= kk
        u, w = ii[m] / kk, jj[m] / kk
        P = a[sel, None, :] * (1 - u - w)[None, :, None] + b[sel, None, :] * u[None, :, None] + c[sel, None, :] * w[None, :, None]
        out.append(P.reshape(-1, 3))
    P = np.concatenate(out)
    if len(P) > cap:
        P = P[np.random.default_rng(0).choice(len(P), cap, replace=False)]
    return P


class MeshField:
    """signed distance field of a closed mesh from surface samples (KD-tree) + ray parity: phi(p) < 0 inside; direction(p) = unit vector pointing OUT of the mesh at the nearest surface point"""

    def __init__(self, v, f, spacing=0.5):
        import trimesh
        from scipy.spatial import cKDTree
        self.tm = trimesh.Trimesh(np.asarray(v, float), np.asarray(f, np.int64), process=False)
        self.pts = surface_samples(v, f, spacing)
        self.tree = cKDTree(self.pts)
        self.lo, self.hi = self.tm.bounds[0] - 1.0, self.tm.bounds[1] + 1.0

    def near(self, p, margin):
        return np.flatnonzero(((p >= self.lo - margin) & (p <= self.hi + margin)).all(1))

    def query(self, p):
        """-> (signed distance, unit outward direction) for points p"""
        d, i = self.tree.query(p)
        q = self.pts[i]
        ins = self.tm.contains(p)
        dirn = np.where(ins[:, None], q - p, p - q)
        n = np.linalg.norm(dirn, axis=1, keepdims=True)
        dirn = dirn / np.maximum(n, 1e-9)
        return np.where(ins, -d, d), dirn



def surface_samples_faces(v, f, spacing=0.5, cap=400000):
    """like surface_samples but also returns the face index of every sample"""
    v = np.asarray(v, float)
    f = np.asarray(f, np.int64)
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    area = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
    k = np.clip(np.ceil(np.sqrt(area) / spacing).astype(int), 1, 40)
    P, F = [], []
    for kk in np.unique(k):
        sel = np.flatnonzero(k == kk)
        if kk == 1:
            P.append((a[sel] + b[sel] + c[sel]) / 3.0)
            F.append(sel)
            continue
        ii, jj = np.meshgrid(np.arange(kk + 1), np.arange(kk + 1), indexing="ij")
        m = ii + jj <= kk
        u, w = ii[m] / kk, jj[m] / kk
        Q = a[sel, None, :] * (1 - u - w)[None, :, None] + b[sel, None, :] * u[None, :, None] + c[sel, None, :] * w[None, :, None]
        P.append(Q.reshape(-1, 3))
        F.append(np.repeat(sel, Q.shape[1]))
    P, F = np.concatenate(P), np.concatenate(F)
    if len(P) > cap:
        ii = np.random.default_rng(0).choice(len(P), cap, replace=False)
        P, F = P[ii], F[ii]
    return P, F


class NormalField:
    """signed distance of a (possibly open) triangle mesh from its nearest surface sample and the side of that sample's face normal (orientation made outward by the sign of n . (q - centroid) summed over the samples):
    no ray parity, so open meshes do not flip the sign; phi < 0 inside; direction = unit vector out of the mesh at the nearest sample"""

    def __init__(self, v, f, spacing=0.5):
        from scipy.spatial import cKDTree
        v = np.asarray(v, float)
        f = np.asarray(f, np.int64)
        self.pts, fi = surface_samples_faces(v, f, spacing)
        n = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
        n = n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
        cen = v.mean(0)
        area = 0.5 * np.linalg.norm(np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]]), axis=1)
        mid = v[f].mean(1)
        sgn = float(np.sum(area * np.einsum("ij,ij->i", n, mid - cen)))
        if sgn < 0:
            n = -n
        self.nrm = n[fi]
        self.tree = cKDTree(self.pts)
        self.lo, self.hi = v.min(0) - 1.0, v.max(0) + 1.0

    def near(self, p, margin):
        return np.flatnonzero(((p >= self.lo - margin) & (p <= self.hi + margin)).all(1))

    def query(self, p):
        d, i = self.tree.query(p)
        q, n = self.pts[i], self.nrm[i]
        side = np.einsum("ij,ij->i", p - q, n)
        ins = side < 0
        dirn = np.where(ins[:, None], n, (p - q) / np.maximum(d, 1e-9)[:, None])
        return np.where(ins, -d, d), dirn



class VoxSDF:
    """signed distance (mm, phi < 0 inside) of the filled solid of a mesh (union over its connected components, so overlapping pieces of one muscle are fine) on a 1 mm lattice (every 2nd voxel of a 0.5 mm grid
    cropped to the working box); same query / near API as MeshField"""

    def __init__(self, v, f, h=H, pad=6.0):
        import trimesh
        from scripts.transfer.q217_tile import local_solid
        v = np.asarray(v, float)
        f = np.asarray(f, np.int64)
        lo = np.maximum(v.min(0) - pad, BOX_LO - 4.0)
        hi = np.minimum(v.max(0) + pad, BOX_HI + 4.0)
        self.valid = (hi > lo).all()
        self.lo_b, self.hi_b = v.min(0) - 1.0, v.max(0) + 1.0
        if not self.valid:
            return
        g = VoxGrid(lo, hi, h)
        tm = trimesh.Trimesh(v, f, process=False)
        occ = np.zeros(g.shape, bool)
        for comp in tm.split(only_watertight=False):
            if len(comp.faces) < 8:
                continue
            r = local_solid(g, comp.vertices, comp.faces, pad=1.0)
            if r is not None:
                occ[r[0]] |= r[1]
        m = occ[::2, ::2, ::2]
        self.h = 2 * h
        self.lo = g.lo
        din = ndi.distance_transform_edt(m, sampling=self.h)
        dout = ndi.distance_transform_edt(~m, sampling=self.h)
        self.phi = np.where(m, -(din - self.h / 2), dout - self.h / 2).astype(np.float32)
        self.shape = m.shape

    def near(self, p, margin):
        if not self.valid:
            return np.zeros(0, np.int64)
        return np.flatnonzero(((p >= self.lo_b - margin) & (p <= self.hi_b + margin)).all(1))

    def _s(self, p):
        i = (np.asarray(p) - self.lo) / self.h
        inb = ((i >= 0) & (i <= np.asarray(self.shape) - 1)).all(1)
        out = np.full(len(p), 30.0, np.float32)
        if inb.any():
            out[inb] = map_coordinates(self.phi, i[inb].T, order=1, mode="nearest")
        return out

    def query(self, p):
        ph = self._s(p)
        e = 0.8
        g = np.zeros_like(p)
        for k in range(3):
            d = np.zeros(3)
            d[k] = e
            g[:, k] = (self._s(p + d) - self._s(p - d)) / (2 * e)
        n = np.linalg.norm(g, axis=1, keepdims=True)
        return ph, g / np.maximum(n, 1e-6)


class Separator:
    """moving muscles {id: (v, f)}, fixed muscles {id: (v, f)}, bones {id: (v, f)}, skin guard (signed(p) <= 0 inside)"""

    def __init__(self, moving, fixed, bones, skin, y_win=(100.0, 305.0), ramp_mm=25.0, anchor_end=None, log=print):
        self.f = {k: np.asarray(f, np.int64) for k, (v, f) in moving.items()}
        self.x0 = {k: np.asarray(v, float).copy() for k, (v, f) in moving.items()}
        self.x = {k: v.copy() for k, v in self.x0.items()}
        self.ids = list(moving)
        self.skin = skin
        self.log = log
        self.Lap = {k: laplacian(len(self.x0[k]), self.f[k]) for k in self.ids}
        self.y_win = y_win
        self.ramp = ramp_mm
        lo, hi = BOX_LO, BOX_HI
        self.clip = (lo, hi)
        log("static fields ...")
        self.bone = self._union_sdf(bones)
        self.fixed = self._union_sdf(fixed)
        self.anchor_end = anchor_end or {}
        # anchors: outside the window the muscle is held; a ramp inside
        self.anch = {}
        for k in self.ids:
            y = self.x0[k][:, 1]
            a = np.maximum(smooth_ramp(y, y_win[0], ramp_mm), 1.0 - smooth_ramp(y, y_win[1] - ramp_mm, ramp_mm))
            self.anch[k] = 60.0 * a
            if k in self.anchor_end:
                self.anch[k] = np.maximum(self.anch[k], self.anchor_end[k])

    def _union_sdf(self, items):
        g = VoxGrid(BOX_LO, BOX_HI, H)
        from scripts.transfer.q217_domain import bone_solid
        occ = np.zeros(g.shape, bool)
        for k, (v, f) in items.items():
            v = np.asarray(v, float)
            if (v.max(0) < BOX_LO).any() or (v.min(0) > BOX_HI).any():
                continue
            occ |= bone_solid(g, v, np.asarray(f, np.int64))
        return SDF.from_solid(occ, g.lo)

    def muscle_sdfs(self):
        return {k: VoxSDF(self.x[k], self.f[k]) for k in self.ids}

    def targets(self, sd, gap_pair=FASCIA_MM / 2, gap_fixed=FASCIA_MM, gap_bone=0.3, skin_depth=1.0, share=0.6):
        T, W, why = {}, {}, {}
        for k in self.ids:
            x = self.x[k]
            t = np.zeros_like(x)
            inbox = ((x >= BOX_LO) & (x <= BOX_HI)).all(1)
            parts = {"muscle": np.zeros(len(x)), "fixed": np.zeros(len(x)), "bone": np.zeros(len(x)), "skin": np.zeros(len(x))}
            for j in self.ids:
                if j == k:
                    continue
                cand = sd[j].near(x, gap_pair + 0.1)
                if not len(cand):
                    continue
                phi, dirn = sd[j].query(x[cand])
                need = np.where(inbox[cand], np.maximum(gap_pair - phi, 0.0), 0.0)
                sel = need > 0
                if sel.any():
                    ci = cand[sel]
                    t[ci] += share * need[sel, None] * dirn[sel]
                    parts["muscle"][ci] = np.maximum(parts["muscle"][ci], need[sel])
            for nm, F, gap in (("fixed", self.fixed, gap_fixed), ("bone", self.bone, gap_bone)):
                phi = F.sample(x)
                need = np.where(inbox, np.maximum(gap - phi, 0.0), 0.0)
                sel = need > 0
                if sel.any():
                    t[sel] += need[sel, None] * F.grad(x[sel])
                    parts[nm][sel] = need[sel]
            if self.skin is not None:
                s = self.skin.signed(x)
                need = np.where(inbox, np.maximum(s + skin_depth, 0.0), 0.0)
                sel = need > 0
                if sel.any():
                    d, ii = self.skin.tree.query(x[sel])
                    near = self.skin.tree.data[ii]
                    inside = s[sel] <= 0
                    dirn = np.where(inside[:, None], x[sel] - near, near - x[sel])
                    nrm = np.linalg.norm(dirn, axis=1, keepdims=True)
                    t[sel] += need[sel, None] * dirn / np.maximum(nrm, 1e-6)
                    parts["skin"][sel] = need[sel]
            T[k] = t
            W[k] = (np.stack(list(parts.values())).max(0) > 0).astype(float)
            why[k] = {n: (int((p > 0).sum()), float(p[p > 0].sum()), float(p.max())) for n, p in parts.items()}
        return T, W, why

    def step(self, lam, alpha=0.8, cap=6.0, wdata=30.0):
        sd = self.muscle_sdfs()
        T, W, why = self.targets(sd, gap_pair=getattr(self, 'gap_pair', FASCIA_MM / 2))
        tot = {n: [0, 0.0, 0.0] for n in ("muscle", "fixed", "bone", "skin")}
        for k in self.ids:
            t = T[k]
            n = np.linalg.norm(t, axis=1, keepdims=True)
            t = np.where(n > cap, t * cap / np.maximum(n, 1e-9), t)
            d = solve_disp(self.Lap[k], W[k] * wdata, t, lam, self.anch[k])
            self.x[k] = self.x[k] + alpha * d
            for nm, (c, sm, mx) in why[k].items():
                tot[nm][0] += c
                tot[nm][1] += sm
                tot[nm][2] = max(tot[nm][2], mx)
        return tot
