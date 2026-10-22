"""Q243: a fast signed distance to a set of bone meshes. trimesh's exact closest-point query costs ~1 ms per point (hundreds of thousands of points for the 24 nuclei and 29 cord segments); here the
distance is taken to a dense surface sample (about 0.15 mm spacing) with the sign from the sampled face normal, and only the points within a thin band of the surface (|d| < band) are re-solved EXACTLY."""
from __future__ import annotations
import numpy as np, trimesh
from scipy.spatial import cKDTree

N_SAMPLES = 250000


class Bones:
    def __init__(self, meshes, n=N_SAMPLES, seed=0):
        np.random.seed(seed)
        self.meshes = list(meshes)
        self.kd, self.nrm = [], []
        for m in self.meshes:
            pts, fi = trimesh.sample.sample_surface(m, n)
            self.kd.append(cKDTree(pts)); self.nrm.append(np.asarray(m.face_normals)[fi]);
        self.pts = [k.data for k in self.kd]

    def signed(self, W, band=0.8, exact=True):
        """-> (signed distance (n,), outward bone normal (n,3)); negative = inside a bone"""
        W = np.asarray(W, float)
        best = np.full(len(W), np.inf); bn = np.zeros((len(W), 3))
        for k, m in enumerate(self.meshes):
            d, i = self.kd[k].query(W)
            n = self.nrm[k][i]
            s = np.where(((W - self.pts[k][i]) * n).sum(1) >= 0, 1.0, -1.0)
            sd = d * s
            upd = np.abs(sd) < np.abs(best)
            best[upd] = sd[upd]; bn[upd] = n[upd]
        if exact:
            idx = np.where(np.abs(best) < band)[0]
            for k, m in enumerate(self.meshes):
                if not len(idx):
                    break
                sel = idx[self.kd[k].query(W[idx])[0] < band + 0.3]
                if not len(sel):
                    continue
                c, d, tri = trimesh.proximity.closest_point(m, W[sel])
                nn = m.face_normals[tri]
                sd = d * np.where(((W[sel] - c) * nn).sum(1) >= 0, 1.0, -1.0)
                upd = np.abs(sd) < np.abs(best[sel]) + 1e-9
                best[sel[upd]] = sd[upd]; bn[sel[upd]] = nn[upd]
        return best, bn

    def rest_on(self, V, margin=1.2, iters=6):
        """vertices closer than `margin` to a bone (or inside it) are moved out along the bone normal to `margin`. -> V', n moved, max move (mm)"""
        V = np.array(V, float); V0 = V.copy()
        for _ in range(iters):
            sd, n = self.signed(V)
            v = sd < margin
            if not v.any():
                break
            V[v] += (margin - sd[v])[:, None] * n[v]
        d = np.linalg.norm(V - V0, axis=1)
        return V, int((d > 0.05).sum()), float(d.max())
