"""Q217: carry an existing muscle mesh onto its new voxel territory by SDF demons registration (replaces the vertex-ICP of q217_fit for the big moves).

phi_S = signed distance (mm) of the prior solid, phi_T = of the new territory, both on a 1 mm lattice (every 2nd voxel of the 0.5 mm grid, cropped around both).  A smooth displacement field u
(multi-resolution 4 / 2 / 1 mm, Gaussian-regularised, symmetric demons force on the distance fields) is found with phi_T(x + u(x)) = phi_S(x): every point of the prior surface lands on the territory
surface, interior points follow smoothly, so the mesh is carried (translated / bent), not crumpled.  The vertices move by u (weighted to 0 outside the working window); topology, tendons and vertex count stay."""
from __future__ import annotations

import numpy as np
from scipy import ndimage as ndi
from scipy.ndimage import map_coordinates


def sdf(mask, h):
    din = ndi.distance_transform_edt(mask, sampling=h)
    dout = ndi.distance_transform_edt(~mask, sampling=h)
    return np.where(mask, -(din - h / 2), dout - h / 2).astype(np.float32)


class Warp:
    def __init__(self, g, prior_mask, terr_mask, pad_mm=14.0):
        h = g.h
        idx = np.argwhere(prior_mask | terr_mask)
        lo = np.maximum(idx.min(0) - int(pad_mm / h), 0)
        hi = np.minimum(idx.max(0) + int(pad_mm / h) + 1, np.asarray(g.shape))
        sl = tuple(slice(int(lo[a]), int(hi[a])) for a in range(3))
        self.h = 2 * h
        self.lo = g.lo + lo * h
        self.pS = sdf(prior_mask[sl][::2, ::2, ::2], self.h)
        self.pT = sdf(terr_mask[sl][::2, ::2, ::2], self.h)
        self.shape = self.pS.shape
        self.u = None
        self.vol_prior = float(prior_mask[sl].sum()) * h ** 3 / 1000.0
        self.vol_terr = float(terr_mask[sl].sum()) * h ** 3 / 1000.0

    def run(self, levels=((4, 40), (2, 40), (1, 25)), sigma=1.2, clamp=1.5):
        h0 = self.h
        u = None
        for fac, iters in levels:
            if fac == 1:
                S, T = self.pS, self.pT
            else:
                S = ndi.zoom(ndi.gaussian_filter(self.pS, fac / 2.0), 1.0 / fac, order=1)
                T = ndi.zoom(ndi.gaussian_filter(self.pT, fac / 2.0), 1.0 / fac, order=1)
            hh = h0 * fac
            sh = S.shape
            if u is None:
                u = np.zeros((3,) + sh, np.float32)
            else:
                u = np.stack([ndi.zoom(u[k], np.asarray(sh) / np.asarray(u.shape[1:]), order=1) for k in range(3)])
            grid = np.stack(np.meshgrid(*[np.arange(n, dtype=np.float32) for n in sh], indexing="ij"))
            gT = np.stack(np.gradient(T, hh)).astype(np.float32)
            gS = np.stack(np.gradient(S, hh)).astype(np.float32)
            for _ in range(iters):
                co = grid + u / hh
                Tw = map_coordinates(T, co, order=1, mode="nearest")
                diff = Tw - S
                gTw = np.stack([map_coordinates(gT[k], co, order=1, mode="nearest") for k in range(3)])
                gg = 0.5 * (gTw + gS)
                n2 = (gg ** 2).sum(0)
                upd = -diff[None] * gg / (n2[None] + 1e-2)
                m = np.sqrt((upd ** 2).sum(0))
                upd = np.where(m > clamp, upd * clamp / np.maximum(m, 1e-9), upd)
                u = u + upd
                u = np.stack([ndi.gaussian_filter(u[k], sigma) for k in range(3)])
            self.last_resid = float(np.abs(diff[np.abs(S) < 4]).mean()) if (np.abs(S) < 4).any() else 0.0
        # to the 1 mm lattice
        if u.shape[1:] != self.shape:
            u = np.stack([ndi.zoom(u[k], np.asarray(self.shape) / np.asarray(u.shape[1:]), order=1) for k in range(3)])
        self.u = u
        return self

    def disp(self, p):
        i = (np.asarray(p) - self.lo) / self.h
        inb = ((i >= 0) & (i <= np.asarray(self.shape) - 1)).all(1)
        out = np.zeros((len(p), 3))
        if inb.any():
            for k in range(3):
                out[inb, k] = map_coordinates(self.u[k], i[inb].T, order=1, mode="nearest")
        return out


def carry_mesh(v0, warp, y_win=(100.0, 342.0), ramp=20.0, w=None):
    from scripts.transfer.q217_slide import smooth_ramp
    d = warp.disp(v0)
    y = v0[:, 1]
    wgt = 1.0 - np.maximum(smooth_ramp(y, y_win[0], ramp), 1.0 - smooth_ramp(y, y_win[1] - ramp, ramp))
    return v0 + d * (wgt if w is None else w)[:, None]
