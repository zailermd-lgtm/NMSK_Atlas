"""Q234: place the HRA VH_F mammary glands (CC BY 4.0, Visible Human female) against a page's own chest.
 1. thoracic registration: the HRA thoracic vertebrae onto the page's thoracic vertebrae (rigid + uniform scale ICP), the same donor, so the HRA chest wall lies on the page's chest wall;
 2. skin-envelope fit: the HRA breast projects farther forward than the page's (flat, supine) chest skin, so each anteroposterior column of the breast is compressed, only as much as needed, to lie between the page's
    chest wall (posterior limit) and the page's skin (anterior limit): z' = b' + (z - b) / (t - b) * (t' - b'), column (x, y) of the breast with HRA extent [b, t] and available extent [b', t'];
 3. gates: signed distances of every vertex to the page's skin interior, pectoralis major, bones, other muscles (1 mm voxel signed-distance fields).
Frames: atlas (mm, +X right, +Y superior, +Z anterior)."""
from __future__ import annotations
import numpy as np, trimesh
from scipy import ndimage as ndi
from scipy.interpolate import RegularGridInterpolator

P = 1.0


def _raster_local(v, f, lo, hi, dens):
    """boolean occupancy (local array, its origin) of the surface samples of the triangles inside [lo, hi]"""
    c = v[f].mean(1)
    k = np.all((c > lo - 4) & (c < hi + 4), axis=1)
    if not k.any():
        return None, None
    m = trimesh.Trimesh(v, f[k], process=False)
    pts = m.sample(int(m.area * dens) + 300)
    pts = pts[np.all((pts >= lo) & (pts < hi), axis=1)]
    if len(pts) == 0:
        return None, None
    o = np.floor(pts.min(0) / P) * P - 4 * P
    sh = tuple(np.ceil((pts.max(0) - o) / P).astype(int) + 5)
    g = np.zeros(sh, bool)
    idx = np.floor((pts - o) / P).astype(int)
    g[tuple(idx.T)] = True
    return g, o


def solid_mask(v, f, lo, hi, shape, dens=3.0):
    """filled solid of a (nearly) closed surface, within the box [lo, hi) of the grid (origin lo, pitch P)"""
    out = np.zeros(shape, bool)
    g, o = _raster_local(v, f, lo, hi, dens)
    if g is None:
        return out
    g = ndi.binary_dilation(g, structure=np.ones((3, 3, 3), bool), iterations=1)
    g = ndi.binary_closing(g, iterations=1)
    g = ndi.binary_fill_holes(g)
    g = ndi.binary_erosion(g, structure=np.ones((3, 3, 3), bool), iterations=1)
    i0 = np.round((o - lo) / P).astype(int)
    a0 = np.maximum(i0, 0)
    a1 = np.minimum(i0 + np.array(g.shape), np.array(shape))
    if (a1 <= a0).any():
        return out
    out[a0[0]:a1[0], a0[1]:a1[1], a0[2]:a1[2]] = g[a0[0] - i0[0]:a1[0] - i0[0], a0[1] - i0[1]:a1[1] - i0[1], a0[2] - i0[2]:a1[2] - i0[2]]
    return out


def skin_mask(v, f, lo, hi, shape):
    """body interior inside the box: dilate the surface samples, fill every y slice (the box holds the whole torso cross-section in x and z), erode"""
    g, o = _raster_local(v, f, lo, hi, 4.0)
    full = np.zeros(shape, bool)
    i0 = np.round((o - lo) / P).astype(int)
    a0 = np.maximum(i0, 0); a1 = np.minimum(i0 + np.array(g.shape), np.array(shape))
    full[a0[0]:a1[0], a0[1]:a1[1], a0[2]:a1[2]] = g[a0[0] - i0[0]:a1[0] - i0[0], a0[1] - i0[1]:a1[1] - i0[1], a0[2] - i0[2]:a1[2] - i0[2]]
    full = ndi.binary_dilation(full, structure=np.ones((3, 3, 3), bool), iterations=1)
    for j in range(shape[1]):
        full[:, j, :] = ndi.binary_fill_holes(full[:, j, :])
    return ndi.binary_erosion(full, structure=np.ones((3, 3, 3), bool), iterations=1)


def sdf(mask):
    return (ndi.distance_transform_edt(~mask, sampling=P) - ndi.distance_transform_edt(mask, sampling=P)).astype(np.float32)


class Fields:
    """signed distances (mm, negative inside) of the skin interior and of groups of chest-wall structures on a 1 mm grid cropped to one breast's region.
    groups: {name: [(id, v, f), ...]} (e.g. pec, bone, muscle); 'wall' is their union"""

    def __init__(self, skin, groups, crop_lo, crop_hi, pad=14.0):
        sv, sf = skin
        sk_lo = sv.min(0) - 4; sk_hi = sv.max(0) + 4
        lo = np.array([sk_lo[0], crop_lo[1] - pad, sk_lo[2]]); hi = np.array([sk_hi[0], crop_hi[1] + pad, sk_hi[2]])
        lo = np.floor(lo / P) * P; hi = np.ceil(hi / P) * P
        shape = tuple(np.ceil((hi - lo) / P).astype(int))
        sk = skin_mask(sv, sf, lo, hi, shape)
        masks = {}
        for gname, walls in groups.items():
            m = np.zeros(shape, bool)
            for i, v, f in walls:
                if len(f) < 6 or (v.max(0) < lo).any() or (v.min(0) > hi).any():
                    continue
                m |= solid_mask(v, f, lo, hi, shape, 3.0)
            masks[gname] = m
        masks["wall"] = np.any(list(masks.values()), axis=0)
        cl = np.maximum(np.floor((np.array(crop_lo) - pad - lo) / P).astype(int), 0)
        ch = np.minimum(np.ceil((np.array(crop_hi) + pad - lo) / P).astype(int), np.array(shape))
        sl = tuple(slice(a, b) for a, b in zip(cl, ch))
        self.lo = lo + cl * P
        self.skin_mask = sk[sl]
        self.masks = {k: v[sl] for k, v in masks.items()}
        self.sd = {"skin": sdf(self.skin_mask)}
        for k, m in self.masks.items():
            self.sd[k] = sdf(m) if m.any() else np.full(m.shape, 99.0, np.float32)

    def at(self, name, pts):
        c = ((np.asarray(pts) - self.lo) / P - 0.5).T
        return ndi.map_coordinates(self.sd[name], c, order=1, mode="nearest")

    def column_tops(self, xs, ys):
        """skin top z and chest-wall top z (the highest wall voxel below the skin top) of the columns (xs[i], ys[j]) -> two (len(xs), len(ys)) arrays (nan where absent)"""
        zs_t = np.full((len(xs), len(ys)), np.nan); zw_t = np.full_like(zs_t, np.nan)
        for a, x in enumerate(xs):
            for b, y in enumerate(ys):
                i = int(round(x - self.lo[0] - 0.5)); j = int(round(y - self.lo[1] - 0.5))
                if not (0 <= i < self.skin_mask.shape[0] and 0 <= j < self.skin_mask.shape[1]):
                    continue
                z = np.where(self.skin_mask[i, j])[0]
                if not len(z):
                    continue
                zt = z.max(); zs_t[a, b] = self.lo[2] + zt + 0.5
                w = np.where(self.masks["wall"][i, j, :zt + 1])[0]
                if len(w):
                    zw_t[a, b] = self.lo[2] + w.max() + 0.5
        return zs_t, zw_t


def xform(p, s, R, t):
    return s * np.asarray(p) @ R.T + t


def _fill_nearest(a):
    """replace nan by the value of the nearest finite cell"""
    bad = ~np.isfinite(a)
    if not bad.any():
        return a
    idx = ndi.distance_transform_edt(bad, return_distances=False, return_indices=True)
    return a[tuple(idx)]


class ColumnWarp:
    """anteroposterior column compression of a breast (all its structures with the same map) into the space between a page's chest wall and skin"""

    def __init__(self, F, ref_pts, m_wall=1.0, m_skin=1.5, step=2.0, sigma=1.5, rest_gap=25.0):
        lo = ref_pts.min(0)[:2] - 6; hi = ref_pts.max(0)[:2] + 6
        self.xs = np.arange(lo[0], hi[0] + step, step); self.ys = np.arange(lo[1], hi[1] + step, step)
        nx, ny = len(self.xs), len(self.ys)
        # HRA extent per column from the dense reference surface samples (fat + areola + nipple, already in the page frame after the thoracic registration)
        ix = np.clip(np.round((ref_pts[:, 0] - self.xs[0]) / step).astype(int), 0, nx - 1)
        iy = np.clip(np.round((ref_pts[:, 1] - self.ys[0]) / step).astype(int), 0, ny - 1)
        b = np.full((nx, ny), np.inf); t = np.full((nx, ny), -np.inf)
        np.minimum.at(b, (ix, iy), ref_pts[:, 2]); np.maximum.at(t, (ix, iy), ref_pts[:, 2])
        has = np.isfinite(b)
        b = _fill_nearest(np.where(has, b, np.nan)); t = _fill_nearest(np.where(has, t, np.nan))
        zs, zw = F.column_tops(self.xs, self.ys)
        zs = _fill_nearest(zs)
        wall_known = np.isfinite(zw)
        zw = np.where(wall_known, zw, -1e3)
        zw_s = ndi.gaussian_filter(np.where(wall_known, zw, np.nanmedian(zw[wall_known])), 3.0)
        zs_s = ndi.gaussian_filter(zs, sigma)
        rest = wall_known & ((b - zw_s) <= rest_gap)                                   # the HRA fat lies within rest_gap mm of the page's chest wall: its posterior surface rests on the wall (a breast lies on the pectoral fascia)
        bp = np.where(rest, zw_s + m_wall, np.where(wall_known, np.maximum(b, zw_s + m_wall), np.minimum(b, zs_s - m_skin - 3.0)))
        tp = np.minimum(t, zs_s - m_skin)                                   # anterior limit: inside the skin
        tp = np.maximum(tp, bp + 2.0)                                       # a sliver rather than inverted where the page has no room
        self.b, self.t, self.bp, self.tp = [ndi.gaussian_filter(a, sigma) for a in (b, t, bp, tp)]
        self.has = ndi.binary_dilation(has, iterations=2)
        self._ip = {k: RegularGridInterpolator((self.xs, self.ys), getattr(self, k), bounds_error=False, fill_value=None) for k in ("b", "t", "bp", "tp")}
        self.stats = dict(columns=int(has.sum()), ratio_median=float(np.median(((tp - bp) / np.maximum(t - b, 1e-3))[has])), ratio_min=float(((tp - bp) / np.maximum(t - b, 1e-3))[has].min()),
                          columns_compressed=int(((tp - bp) < (t - b) - 0.5)[has].sum()), room_min_mm=float((tp - bp)[has].min()))

    def __call__(self, V):
        V = np.asarray(V, float)
        xy = V[:, :2]
        b, t, bp, tp = [self._ip[k](xy) for k in ("b", "t", "bp", "tp")]
        u = np.clip((V[:, 2] - b) / np.maximum(t - b, 1.0), 0.0, 1.0)
        W = V.copy()
        W[:, 2] = bp + u * (tp - bp)
        return W


def grad_unit(F, name, pts):
    """unit gradient (outward = towards increasing signed distance) of a field at pts"""
    g = np.zeros((len(pts), 3))
    for a in range(3):
        d = np.zeros(3); d[a] = 1.0
        g[:, a] = F.at(name, pts + d) - F.at(name, pts - d)
    n = np.linalg.norm(g, axis=1, keepdims=True)
    return g / np.maximum(n, 1e-9)


def push_field(F, parts, rules, sigma=6.0, iters=14, damp=1.0):
    """Smooth rim correction. rules: [(field, margin, kind)]: kind 'inside' keeps sd <= -margin (skin interior), kind 'outside' keeps sd >= margin (chest wall groups).
    The displacement of the violating vertices of the `driver` parts (every part is checked, all parts receive the same smooth field, Gaussian kernel sigma) is repeated until no violation or `iters`.
    parts: {id: V} -> returns {id: V'}, history list of (iteration, n_violating, max_violation_mm)"""
    from scipy.spatial import cKDTree
    cur = {k: np.array(v, float) for k, v in parts.items()}
    hist = []
    for it in range(iters):
        P_, D_ = [], []
        worst = 0.0; nviol = 0
        for k, V in cur.items():
            for name, margin, kind in rules:
                sd = F.at(name, V)
                v = (sd > -margin) if kind == "inside" else (sd < margin)
                if not v.any():
                    continue
                gr = grad_unit(F, name, V[v])
                amt = (sd[v] + margin) if kind == "inside" else (sd[v] - margin)       # inside: positive = too far out -> move by -amt along +grad ; outside: negative = too far in -> move by -amt along +grad
                P_.append(V[v]); D_.append(-amt[:, None] * gr * damp)
                nviol += int(v.sum()); worst = max(worst, float(np.abs(amt).max()))
        hist.append((it, nviol, round(worst, 2)))
        if nviol == 0:
            break
        P_ = np.vstack(P_); D_ = np.vstack(D_)
        tree = cKDTree(P_)
        for k, V in cur.items():
            idx = tree.query_ball_point(V, 3 * sigma)
            dV = np.zeros_like(V)
            for i_, nb in enumerate(idx):
                if nb:
                    r2 = ((P_[nb] - V[i_]) ** 2).sum(1)
                    w = np.exp(-r2 / (2 * sigma ** 2))
                    dV[i_] = (w[:, None] * D_[nb]).sum(0) / max(w.sum(), 1.0)
            cur[k] = V + dV
    return cur, hist
