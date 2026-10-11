"""Q217: non-rigid fit of an existing muscle mesh to its new voxel territory (q217_tile.py label volume).

The mesh keeps its vertices, faces and tendons.  Only the vertices near the voxels where the territory differs from the prior solid (cut at an interface, released from bone / fat / skin, regrown) are driven:
per round the vertex goes to the nearest point of the new territory's surface (p - phi(p) grad phi(p), phi = signed distance of the territory, 0.5 mm EDT), capped per round, and the displacement field of the
whole mesh is solved with a graph-Laplacian smoothness term (q217_slide.solve_disp: stiff first, local last) so the surface is carried, not crumpled; vertices outside the working window are held."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi
from scipy.ndimage import map_coordinates

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.transfer.q213_inbone import laplacian  # noqa: E402
from scripts.transfer.q217_slide import solve_disp, smooth_ramp  # noqa: E402

LAMS = (20.0, 8.0, 4.0, 2.0, 1.0, 1.0, 0.5, 0.5)


class Territory:
    """signed distance (mm, + outside) of one muscle's voxel territory on a 1 mm lattice (every 2nd voxel of the 0.5 mm grid) + the distance to the voxels where it differs from the prior solid"""

    def __init__(self, g, lab_mask, prior_mask, pad_mm=12.0):
        h = g.h
        idx = np.argwhere(lab_mask | prior_mask)
        lo = np.maximum(idx.min(0) - int(pad_mm / h), 0)
        hi = np.minimum(idx.max(0) + int(pad_mm / h) + 1, np.asarray(g.shape))
        sl = tuple(slice(int(lo[a]), int(hi[a])) for a in range(3))
        self.lo = g.lo + lo * h
        self.h = 2 * h
        m = lab_mask[sl][::2, ::2, ::2]
        din = ndi.distance_transform_edt(m, sampling=self.h)
        dout = ndi.distance_transform_edt(~m, sampling=self.h)
        self.phi = np.where(m, -(din - self.h / 2), dout - self.h / 2).astype(np.float32)
        diff = (lab_mask[sl] ^ prior_mask[sl])[::2, ::2, ::2]
        self.near_change = ndi.distance_transform_edt(~diff, sampling=self.h).astype(np.float32) if diff.any() else np.full(m.shape, 99.0, np.float32)
        self.vol_cm3 = float(lab_mask[sl].sum()) * h ** 3 / 1000.0
        self.shape = m.shape

    def _s(self, arr, p, big):
        i = (np.asarray(p) - self.lo) / self.h
        inb = ((i >= 0) & (i <= np.asarray(self.shape) - 1)).all(1)
        out = np.full(len(p), big, np.float32)
        if inb.any():
            out[inb] = map_coordinates(arr, i[inb].T, order=1, mode="nearest")
        return out

    def phi_at(self, p):
        return self._s(self.phi, p, 30.0)

    def change_dist(self, p):
        return self._s(self.near_change, p, 99.0)

    def project(self, p, e=0.6):
        """vector from p to the nearest point of the territory surface (one Newton step)"""
        ph = self.phi_at(p)
        g = np.zeros_like(p)
        for k in range(3):
            d = np.zeros(3)
            d[k] = e
            g[:, k] = (self.phi_at(p + d) - self.phi_at(p - d)) / (2 * e)
        n = np.linalg.norm(g, axis=1, keepdims=True)
        return -ph[:, None] * g / np.maximum(n, 1e-6), ph


def fit_mesh(v0, f, terr, y_win=(100.0, 342.0), ramp=20.0, change_reach=2.5, rounds=len(LAMS), cap=3.0, alpha=0.8, wdata=30.0, extra_anchor=None, log=None):
    """-> (new vertices, report).  The driven vertices = those within `change_reach` mm of a changed voxel and inside the window."""
    n = len(v0)
    Lap = laplacian(n, f)
    x = np.asarray(v0, float).copy()
    cd = terr.change_dist(v0)
    drive = cd <= change_reach
    y = v0[:, 1]
    inside_win = (y >= y_win[0]) & (y <= y_win[1])
    drive &= inside_win
    anch = 60.0 * np.maximum(smooth_ramp(y, y_win[0], ramp), 1.0 - smooth_ramp(y, y_win[1] - ramp, ramp))
    if extra_anchor is not None:
        anch = np.maximum(anch, extra_anchor)
    hist = []
    for r in range(rounds):
        t, ph = terr.project(x)
        nrm = np.linalg.norm(t, axis=1, keepdims=True)
        t = np.where(nrm > cap, t * cap / np.maximum(nrm, 1e-9), t)
        w = drive.astype(float) * wdata
        d = solve_disp(Lap, w, t, LAMS[r % len(LAMS)], anch)
        x = x + alpha * d
        hist.append(float(np.abs(terr.phi_at(x[drive])).mean()) if drive.any() else 0.0)
    rep = dict(driven_vertices=int(drive.sum()), driven_pct=round(100.0 * float(drive.mean()), 1), mean_abs_phi_mm=[round(h, 3) for h in hist[:1] + hist[-1:]])
    return x, rep
