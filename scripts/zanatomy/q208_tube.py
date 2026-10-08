"""Q208 forearm tube: bone-pair frames + own-skin radial profile.

The Z skin of the forearm is a tube of thin slabs around the radius / ulna pair.  Every structure of the page has the vertex order of the Z source (the fits only move vertices), so the radius / ulna
of the Z source and of the fitted page correspond vertex by vertex.  From them:
  * a FRAME along the forearm axis at coordinate s (mm from the wrist joint centre along the bone axis): origin o(s) = midpoint of the radius and ulna section centroids, e1(s) = direction radius -> ulna
    (in the plane normal to the axis), e2 = a x e1.  The frame of the source and of the page differ by the translation, bend and ROLL (pronation) of the fit;
  * s_page = g(s_source) from the corresponding bone vertices (monotone, linear extrapolation).
A source skin vertex has cylindrical coordinates (s, theta, rho) in the source frame; its new place is the point of the page frame at (g(s), theta) whose radius is the person's OWN skin radius there
(ray from the page axis through the watertight CT / cryosection skin, smoothed) minus a margin: the outer sheet follows the person's own skin, the inner sheet keeps the source twin offset in the
local cylindrical frame (thickness preserved).  A function of POSITION, so vertices that two patches share in the source stay shared.
"""
from __future__ import annotations

import numpy as np
from scipy import ndimage as ndi


def unit(v, axis=-1):
    return v / np.maximum(np.linalg.norm(v, axis=axis, keepdims=True), 1e-12)


class Frames:
    def __init__(self, bones_r, bones_u, wrist, sigma_mm=12.0, ds=2.0, slab=6.0):
        self.W = np.asarray(wrist, float)
        self.roll = None
        both = np.vstack([bones_r, bones_u])
        c = both.mean(0)
        a = np.linalg.svd(both - c, full_matrices=False)[2][0]
        if (self.W - c) @ a < 0:
            a = -a
        self.a = a
        sR, sU = (bones_r - self.W) @ a, (bones_u - self.W) @ a
        lo, hi = max(sR.min(), sU.min()) + 4.0, min(sR.max(), sU.max()) - 4.0
        self.grid = np.arange(lo, hi + 1e-6, ds)
        cR, cU, ok = [], [], []
        for s in self.grid:
            mr, mu = np.abs(sR - s) < slab, np.abs(sU - s) < slab
            ok.append(mr.sum() >= 6 and mu.sum() >= 6)
            cR.append(self._inplane(bones_r[mr], s).mean(0) if mr.sum() >= 6 else np.zeros(3))
            cU.append(self._inplane(bones_u[mu], s).mean(0) if mu.sum() >= 6 else np.zeros(3))
        ok = np.array(ok)
        cR, cU = np.array(cR), np.array(cU)
        g = self.grid
        if not ok.all():
            for arr in (cR, cU):
                for k in range(3):
                    arr[:, k] = np.interp(g, g[ok], arr[ok, k])
        o = 0.5 * (cR + cU)
        e1 = unit(cU - cR - ((cU - cR) @ a)[:, None] * a)
        sg = sigma_mm / ds
        o = np.stack([ndi.gaussian_filter1d(o[:, k], sg, mode="nearest") for k in range(3)], 1)
        e1 = unit(np.stack([ndi.gaussian_filter1d(e1[:, k], sg, mode="nearest") for k in range(3)], 1))
        e1 = unit(e1 - (e1 @ a)[:, None] * a)
        self.o, self.e1 = o, e1          # o: in-plane offset (3D, normal to a) of the centreline at s
        self.ds = ds
        n = max(int(30 / ds), 3)
        self.slope_lo = (o[n] - o[0]) / (g[n] - g[0])
        self.slope_hi = (o[-1] - o[-1 - n]) / (g[-1] - g[-1 - n])

    def _inplane(self, P, s):
        d = P - self.W - ((P - self.W) @ self.a)[:, None] * self.a
        return d

    def at(self, s):
        """frame at coordinates s (n,): origin (3D point), e1, e2 (extrapolated beyond the bone range: constant e1, linear centreline)"""
        s = np.asarray(s, float)
        g = self.grid
        sc = np.clip(s, g[0], g[-1])
        o = np.stack([np.interp(sc, g, self.o[:, k]) for k in range(3)], 1)
        o = o + np.where((s < g[0])[:, None], (s - g[0])[:, None] * self.slope_lo, 0.0) + np.where((s > g[-1])[:, None], (s - g[-1])[:, None] * self.slope_hi, 0.0)
        e1 = unit(np.stack([np.interp(sc, g, self.e1[:, k]) for k in range(3)], 1))
        e1 = unit(e1 - (e1 @ self.a)[:, None] * self.a)
        e2 = np.cross(self.a, e1)
        if self.roll is not None:           # roll correction about the axis (radians, function of s): the skin frame turned against the bone pair frame
            d = np.asarray(self.roll(s), float)
            e1, e2 = np.cos(d)[:, None] * e1 + np.sin(d)[:, None] * e2, -np.sin(d)[:, None] * e1 + np.cos(d)[:, None] * e2
        origin = self.W + s[:, None] * self.a + o
        return origin, e1, e2

    def coords(self, P):
        """cylindrical coordinates of points: s, theta, rho (+ unit vectors are recomputed by .at)"""
        s = (P - self.W) @ self.a
        origin, e1, e2 = self.at(s)
        q = P - origin
        c1, c2 = (q * e1).sum(1), (q * e2).sum(1)
        return s, np.arctan2(c2, c1), np.hypot(c1, c2), q @ self.a


def monotone_map(s_src, s_page, ds=10.0):
    """s_page = g(s_src) from corresponding bone vertices: binned medians, monotone, linear extrapolation with the end slopes (returned as a function)"""
    lo, hi = np.percentile(s_src, [1, 99])
    edges = np.arange(lo, hi + ds, ds)
    xs, ys = [], []
    for a, b in zip(edges[:-1], edges[1:]):
        m = (s_src >= a) & (s_src < b)
        if m.sum() >= 5:
            xs.append(np.median(s_src[m])); ys.append(np.median(s_page[m]))
    xs, ys = np.array(xs), np.maximum.accumulate(np.array(ys))
    # smooth with a cubic fit of the binned values (robust to the flared ends)
    k = min(3, len(xs) - 1)
    p = np.polyfit(xs, ys, k)
    x0, x1 = xs[0], xs[-1]
    y0, y1 = np.polyval(p, x0), np.polyval(p, x1)
    d0, d1 = np.polyval(np.polyder(p), x0), np.polyval(np.polyder(p), x1)
    d0, d1 = max(d0, 0.5), max(d1, 0.5)

    def g(s):
        s = np.asarray(s, float)
        out = np.polyval(p, np.clip(s, x0, x1))
        out = np.where(s < x0, y0 + (s - x0) * d0, out)
        out = np.where(s > x1, y1 + (s - x1) * d1, out)
        return out
    return g


class OwnProfile:
    """radius of the person's own skin along rays from the page centreline: grid over (s, theta), first exit, smoothed (Gaussian), minus a margin"""

    def __init__(self, tm, frames, s_lo, s_hi, ds=2.0, ntheta=96, rmax=130.0, sigma_s=3.0, sigma_t=2.0, bone_rho=None):
        self.f = frames
        self.s = np.arange(s_lo, s_hi + 1e-6, ds)
        self.th = np.linspace(-np.pi, np.pi, ntheta, endpoint=False)
        origin, e1, e2 = frames.at(self.s)
        S, T = np.meshgrid(np.arange(len(self.s)), np.arange(ntheta), indexing="ij")
        D = np.cos(self.th)[None, :, None] * e1[:, None, :] + np.sin(self.th)[None, :, None] * e2[:, None, :]
        O = np.repeat(origin[:, None, :], ntheta, 1)
        loc, ray, tri = tm.ray.intersects_location(O.reshape(-1, 3), D.reshape(-1, 3), multiple_hits=True)
        rho = np.full(len(O.reshape(-1, 3)), np.nan)
        if len(ray):
            d = np.linalg.norm(loc - O.reshape(-1, 3)[ray], axis=1)
            order = np.lexsort((d, ray))
            ray_s, d_s = ray[order], d[order]
            first = np.r_[True, ray_s[1:] != ray_s[:-1]]
            ok = d_s[first] < rmax
            rho[ray_s[first][ok]] = d_s[first][ok]
        rho = rho.reshape(len(self.s), ntheta)
        self.raw = rho.copy()
        # fill gaps (rays that left the body far away or hit nothing: the limb touches the trunk, the voxel skin is fused there): per row a low-order Fourier fit of the valid samples, the residual
        # interpolated across the gap, so the profile continues smoothly over the contact
        for i in range(len(self.s)):
            m = np.isnan(rho[i])
            if m.all() or not m.any():
                continue
            ok = ~m
            if ok.sum() >= 24:
                A = np.stack([np.ones(ntheta)] + [f(k * self.th) for k in (1, 2, 3) for f in (np.cos, np.sin)], 1)
                c = np.linalg.lstsq(A[ok], rho[i, ok], rcond=None)[0]
                fit = A @ c
                res = np.interp(self.th, self.th[ok], (rho[i] - fit)[ok], period=2 * np.pi)
                rho[i, m] = (fit + res)[m]
            else:
                rho[i, m] = np.interp(self.th[m], self.th[ok], rho[i, ok], period=2 * np.pi)
        m = np.isnan(rho).all(1)
        if m.any():
            for k in range(ntheta):
                rho[m, k] = np.interp(self.s[m], self.s[~m], rho[~m, k])
        # robust outlier clamp against the median of the neighbours (a ray that slipped between facets / hit the other limb)
        med = ndi.median_filter(rho, size=(5, 5), mode="wrap")
        bad = np.abs(rho - med) > 12.0
        rho[bad] = med[bad]
        self.nbad = int(bad.sum())
        rho = ndi.gaussian_filter(rho, (sigma_s / ds, sigma_t), mode=("nearest", "wrap"))
        self.rho = rho

    def at(self, s, th):
        """smoothed own-skin radius at (s, theta) arrays, bilinear (periodic in theta)"""
        fs = np.clip((np.asarray(s, float) - self.s[0]) / (self.s[1] - self.s[0]), 0, len(self.s) - 1)
        ft = ((np.asarray(th, float) - self.th[0]) / (self.th[1] - self.th[0])) % len(self.th)
        i0 = np.floor(fs).astype(int)
        i1 = np.minimum(i0 + 1, len(self.s) - 1)
        j0 = np.floor(ft).astype(int) % len(self.th)
        j1 = (j0 + 1) % len(self.th)
        a, b = fs - i0, ft - np.floor(ft)
        R = self.rho
        return (1 - a) * (1 - b) * R[i0, j0] + (1 - a) * b * R[i0, j1] + a * (1 - b) * R[i1, j0] + a * b * R[i1, j1]


class AxisFrame:
    """straight axis frame (the humerus): origin = point on the axis, a = unit direction, e1 / e2 fixed;  same interface as Frames (.at, .coords, .a, .W)"""

    def __init__(self, point, axis, e1):
        self.W = np.asarray(point, float)
        self.a = unit(np.asarray(axis, float))
        e1 = np.asarray(e1, float)
        self.e1 = unit(e1 - (e1 @ self.a) * self.a)
        self.e2 = np.cross(self.a, self.e1)

    def at(self, s):
        s = np.asarray(s, float)
        n = len(s)
        return self.W + s[:, None] * self.a, np.tile(self.e1, (n, 1)), np.tile(self.e2, (n, 1))

    def coords(self, P):
        s = (P - self.W) @ self.a
        q = P - self.W - s[:, None] * self.a
        c1, c2 = q @ self.e1, q @ self.e2
        return s, np.arctan2(c2, c1), np.hypot(c1, c2), np.zeros(len(P))


def humerus_frames(raw, pg, side, sim):
    """source / page straight frames of the humerus related by the similarity transform `sim` (scale, R, mx, my of kabsch: page = scale (x - mx) R^T + my)"""
    s_ = "_" + side
    Hs = raw.v("humerus" + s_)
    c = Hs.mean(0)
    a = np.linalg.svd(Hs - c, full_matrices=False)[2][0]
    forearm_dir = raw.wrist()[side] - c
    if a @ forearm_dir < 0:
        a = -a
    e1 = np.cross(a, [0, 0, 1.0])
    sc, R, mx, my = sim
    Fs = AxisFrame(c, a, e1)
    cp = sc * (c - mx) @ R.T + my
    ap = R @ a
    ep = R @ Fs.e1
    Fp = AxisFrame(cp, ap, ep)
    return Fs, Fp, sc
