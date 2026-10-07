"""Q198 geometry utilities (read-only audit): welding, boundary loops, islands, PCA ends, surface samples, voxel fills, skin field."""
from __future__ import annotations
import numpy as np
from scipy import ndimage as ndi
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components
from scipy.spatial import cKDTree


def tri_area(v, f):
    return 0.5 * np.linalg.norm(np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]]), axis=1)


def weld(v, f, tol=0.02):
    """merge coincident vertices (quantised positions) -> (v2, f2); drops degenerate faces"""
    key = np.round(v / tol).astype(np.int64)
    _, first, inv = np.unique(key, axis=0, return_index=True, return_inverse=True)
    v2 = v[first]; f2 = inv.reshape(-1)[f]
    ok = (f2[:, 0] != f2[:, 1]) & (f2[:, 1] != f2[:, 2]) & (f2[:, 0] != f2[:, 2])
    return v2, f2[ok]


def edge_counts(f):
    e = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]); e.sort(1)
    u, c = np.unique(e, axis=0, return_counts=True)
    return u, c


def boundary_loops(v, f):
    """open (count==1) edges -> list of loops (each: vertex-index array, chained greedily); nonmanifold edge count"""
    u, c = edge_counts(f)
    be = u[c == 1]
    nm = int((c > 2).sum())
    if len(be) == 0:
        return [], 0, nm
    n = len(v)
    A = coo_matrix((np.ones(len(be)), (be[:, 0], be[:, 1])), shape=(n, n))
    nc, lab = connected_components(A, directed=False)
    used = np.unique(be)
    loops = []
    for l in np.unique(lab[used]):
        idx = used[lab[used] == l]
        loops.append(idx)
    return loops, len(be), nm


def loop_stats(v, idx):
    p = v[idx]
    c = p.mean(0)
    u, s, vt = np.linalg.svd(p - c, full_matrices=False) if len(p) >= 3 else (None, np.zeros(3), np.eye(3))
    ext = float(s[0] / np.sqrt(max(len(p), 1))) * 2.0
    return {"n": int(len(idx)), "centre": c.tolist(), "extent_mm": round(ext * 1.0, 2), "planarity_mm": round(float(s[-1] / np.sqrt(max(len(p), 1))), 3),
            "normal": vt[-1].tolist()}


def islands(v, f):
    """face-connected components (after welding done by caller): list of dict(size_faces, area, centroid, vertex idx)"""
    n = len(v)
    A = coo_matrix((np.ones(len(f) * 3), (np.r_[f[:, 0], f[:, 1], f[:, 2]], np.r_[f[:, 1], f[:, 2], f[:, 0]])), shape=(n, n))
    nc, lab = connected_components(A, directed=False)
    a = tri_area(v, f)
    out = []
    flab = lab[f[:, 0]]
    for l in range(nc):
        m = flab == l
        if not m.any():
            continue
        out.append({"lab": l, "faces": int(m.sum()), "area": float(a[m].sum()), "vidx": np.unique(f[m])})
    out.sort(key=lambda d: -d["area"])
    return out


def pca(v):
    c = v.mean(0)
    u, s, vt = np.linalg.svd(v - c, full_matrices=False)
    return c, vt, s


def surf_points(v, f, spacing=1.2, cap=60000, rng=None):
    rng = rng or np.random.default_rng(0)
    a = tri_area(v, f)
    if len(a) == 0 or a.sum() <= 0:
        return v.copy()
    n = int(min(cap, max(len(v), a.sum() / spacing ** 2)))
    idx = rng.choice(len(f), n, p=a / a.sum())
    u = rng.random((n, 2)); m = u.sum(1) > 1; u[m] = 1 - u[m]
    t = v[f[idx]]
    return np.concatenate([v, t[:, 0] + u[:, :1] * (t[:, 1] - t[:, 0]) + u[:, 1:] * (t[:, 2] - t[:, 0])])


class Grid:
    """isotropic voxel grid over [lo, hi] (mm)"""
    def __init__(self, lo, hi, h):
        self.lo = np.asarray(lo, float); self.h = float(h)
        self.shape = tuple(np.ceil((np.asarray(hi, float) - self.lo) / h).astype(int) + 1)

    def idx(self, p):
        return np.floor((np.asarray(p) - self.lo) / self.h + 0.5).astype(np.int64)

    def inb(self, i):
        return ((i >= 0) & (i < np.asarray(self.shape))).all(1)

    def raster(self, v, f, spacing=None):
        occ = np.zeros(self.shape, bool)
        if len(f) == 0:
            return occ
        p = surf_points(v, f, spacing or self.h * 0.35, cap=8000000)
        i = self.idx(p); i = i[self.inb(i)]
        occ[i[:, 0], i[:, 1], i[:, 2]] = True
        return occ

    def solid(self, v, f, close=1):
        """rasterised surface -> filled solid (surface closed by `close` dilations first); returns bool volume"""
        s = self.raster(v, f)
        if close:
            s = ndi.binary_dilation(s, iterations=close)
        pad = np.pad(s, 1)
        out = ndi.binary_fill_holes(pad)[1:-1, 1:-1, 1:-1]
        if close:
            out = ndi.binary_erosion(out, iterations=close) | self.raster(v, f)
        return out

    def lookup(self, vol, p):
        i = self.idx(p); ok = self.inb(i)
        r = np.zeros(len(p), vol.dtype)
        r[ok] = vol[i[ok, 0], i[ok, 1], i[ok, 2]]
        return r, ok


class SkinField:
    """whole-body skin envelope on a voxel grid (h mm): inside volume (surface closed by 1-voxel dilation, then filled), signed distance (mm, + outside)."""
    def __init__(self, skin_structs, h=3.0, close=1):
        V = np.concatenate([s["v"] for s in skin_structs]); lo = V.min(0) - 12; hi = V.max(0) + 12
        self.g = Grid(lo, hi, h)
        surf = np.zeros(self.g.shape, bool)
        for s in skin_structs:
            surf |= self.g.raster(s["v"], s["f"])
        cl = ndi.binary_dilation(surf, iterations=close)
        pad = np.pad(cl, 1)
        filled = ndi.binary_fill_holes(pad)[1:-1, 1:-1, 1:-1]
        self.inside = ndi.binary_erosion(filled, iterations=close) | surf
        self.vol_L = float(self.inside.sum() * h ** 3 / 1e6)
        d_out = ndi.distance_transform_edt(~self.inside, sampling=h).astype(np.float32)
        d_in = ndi.distance_transform_edt(self.inside, sampling=h).astype(np.float32)
        self.sd = np.where(self.inside, -d_in, d_out)
        del d_out, d_in

    def signed(self, p):
        """signed distance to the skin (mm, + = outside); points outside the grid -> +50"""
        i = self.g.idx(p); ok = self.g.inb(i)
        r = np.full(len(p), 50.0, np.float32)
        r[ok] = self.sd[i[ok, 0], i[ok, 1], i[ok, 2]]
        return r


class SkinSurf:
    """skin as a surface: the OUTER shell only (a face is outer when a ray cast away from the nearest bone hits no other skin face), outward normals
    (away from the bones), dense samples -> signed distance by nearest outer sample and its normal (+ outside). Robust to gaps between patches."""
    def __init__(self, skin_structs, bone_points, spacing=2.0):
        import trimesh
        Vs, Fs, off = [], [], 0
        for s in skin_structs:
            Vs.append(s["v"]); Fs.append(s["f"] + off); off += len(s["v"])
        V = np.concatenate(Vs); F = np.concatenate(Fs)
        tm = trimesh.Trimesh(V, F, process=False)
        cent = tm.triangles_center; n = tm.face_normals
        bt = cKDTree(bone_points)
        d, i = bt.query(cent)
        dirv = cent - bone_points[i]; dirv /= np.maximum(np.linalg.norm(dirv, axis=1, keepdims=True), 1e-9)
        hit = tm.ray.intersects_any(cent + dirv * 0.05, dirv)
        outer = ~hit
        nout = np.where(((n * dirv).sum(1) >= 0)[:, None], n, -n)
        self.outer_frac = float(outer.mean())
        Fo = F[outer]; self.V, self.Fo = V, Fo; self.nf = nout[outer]
        a = tri_area(V, Fo)
        k = int(min(1500000, max(len(Fo), a.sum() / spacing ** 2)))
        rng = np.random.default_rng(1)
        idx = rng.choice(len(Fo), k, p=a / a.sum())
        u = rng.random((k, 2)); m = u.sum(1) > 1; u[m] = 1 - u[m]
        t = V[Fo[idx]]
        self.P = t[:, 0] + u[:, :1] * (t[:, 1] - t[:, 0]) + u[:, 1:] * (t[:, 2] - t[:, 0])
        self.N = self.nf[idx]
        self.tree = cKDTree(self.P)
        self.area_cm2 = float(a.sum() / 100)

    def signed(self, p, chunk=200000):
        p = np.asarray(p, float)
        out = np.empty(len(p), np.float32)
        for s0 in range(0, len(p), chunk):
            q = p[s0:s0 + chunk]
            d, i = self.tree.query(q)
            sgn = (((q - self.P[i]) * self.N[i]).sum(1) > 0)
            out[s0:s0 + chunk] = np.where(sgn, d, -d)
        return out

    def section_polygons(self, origin, normal):
        """outline polygons (shapely) of the outer skin shell in the plane (origin, normal) -> (polys, to2d basis)"""
        import trimesh
        from shapely.geometry import LineString
        from shapely.ops import unary_union, polygonize
        seg = trimesh.intersections.mesh_plane(trimesh.Trimesh(self.V, self.Fo, process=False), normal, origin, return_faces=False)
        nrm = np.asarray(normal, float); nrm /= np.linalg.norm(nrm)
        u = np.cross(nrm, [1, 0, 0]);
        if np.linalg.norm(u) < 1e-3:
            u = np.cross(nrm, [0, 1, 0])
        u /= np.linalg.norm(u); w = np.cross(nrm, u)
        if len(seg) == 0:
            return [], (u, w)
        s2 = np.stack([((seg - origin) @ u), ((seg - origin) @ w)], axis=-1)   # (k,2,2)
        lines = unary_union([LineString(x) for x in s2 if np.linalg.norm(x[0] - x[1]) > 1e-6])
        polys = list(polygonize(lines))
        return polys, (u, w)


def flat_caps(v, f, minarea=40.0, tol=0.3, at_end=1.5):
    """axis-aligned flat cut faces on a closed/open mesh: faces with normal along an axis, all vertices within `tol` mm of one plane, whose plane lies at an
    extreme (within `at_end` mm) of the structure along that axis -> list of {axis, plane_mm, area_mm2, centre}"""
    vf = v[f]
    nrm = np.cross(vf[:, 1] - vf[:, 0], vf[:, 2] - vf[:, 0]); ar = 0.5 * np.linalg.norm(nrm, axis=1); nrm /= np.maximum(2 * ar[:, None], 1e-9)
    caps = []
    for k, kn in enumerate("xyz"):
        fk = (np.abs(nrm[:, k]) > 0.95) & ((vf[:, :, k].max(1) - vf[:, :, k].min(1)) < tol)
        if not fk.any():
            continue
        pc = vf[fk][:, :, k].mean(1); a2 = ar[fk]; vk = vf[fk]
        key = np.round(pc / 0.5).astype(int)
        ext = (v[:, k].min(), v[:, k].max())
        for kk in np.unique(key):
            m = key == kk
            area = float(a2[m].sum()); pos = float(pc[m].mean())
            if area > minarea and (abs(pos - ext[0]) < at_end or abs(pos - ext[1]) < at_end):
                caps.append({"axis": kn, "plane_mm": round(pos, 1), "area_mm2": round(area, 1), "centre": vk[m].reshape(-1, 3).mean(0).tolist()})
    return sorted(caps, key=lambda x: -x["area_mm2"])
