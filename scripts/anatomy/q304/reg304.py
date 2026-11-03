"""Q304 registration: the Combined page of a body -> the Imaging page of the SAME body, from bone points only.

WHY A CORRECTION FIELD AND NOT A FREE SIMILARITY, measured rather than assumed.
The Combined pages ARE Z-Anatomy fitted onto that Visible Human's own skeleton (Q195: per-bone similarity fits,
soft tissue blended from the nearest bones), and the Imaging page of the same body carries that body's own
segmented bones. `xfer304.py probe` measures the consequence: over 22-23 lower-limb and lumbar bone groups the
Combined page's bone surfaces already lie 0.8-2.8 mm (median) from the Imaging page's own bone surfaces. So the
two pages share the body frame and the registration is a REFINEMENT.

A first version used the Q292 recipe literally -- per-bone nearest-point similarity ICP for the correspondences,
then one global similarity plus a thin-plate spline (lib292.Map). It was discarded by its own numbers: a
nearest-point correspondence on a long bone slides freely ALONG the shaft, so the pair displacements carried a
large tangential component, the global similarity absorbed it, and structures were moved up to 22.7 mm median
(zan_sural_communicating_branch_of_common_fibular_nerve_r) although the bone surfaces either side of them agreed
to 1.3 mm. A 2 cm axial slide of a nerve down the leg is not a refinement.

What is used instead is the same mathematics with the degeneracy removed: the map is the IDENTITY plus a
thin-plate-spline correction field fitted to CLOSEST-POINT displacements (scipy RBFInterpolator,
kernel='thin_plate_spline', degree=1, smoothing=10, a spatially uniform control-point subsample -- exactly
Q292's lib292.Map machinery, with its similarity term fixed at the identity because the probe says the frames
already agree). A closest-point displacement is normal to the target surface, so it cannot slide; the field is
re-queried for three passes so a point that started on the wrong side of a thin bone converges.

The residual is then the honest quantity: the point-to-surface distance from the MAPPED Combined bone surface to
the Imaging page's own bone surface, reported overall, per bone group, and -- because a nerve can be no better
placed than the bones beside it -- per nerve, as the residual of the correspondences within a stated radius of
that nerve's own vertices.

Nothing here invents geometry: every transferred vertex is a Combined-page vertex moved by this one field.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy.interpolate import RBFInterpolator
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[3]
for p in (REPO, REPO / "scripts/anatomy/q292", REPO / "scripts/anatomy/q241", REPO / "scripts/anatomy/q237"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

# the bones that carry the lower limb and the lumbosacral trunk: every nerve to transfer runs beside one of them
LOWER = ("femur", "tibia", "fibula", "patella", "hip_bone", "sacrum", "coccyx",
         "talus", "calcaneus", "tarsal", "metatarsal", "mt_", "ph_foot", "phalanges_foot", "lumbar_spine", "vert_l")


def is_lower(k: str) -> bool:
    return any(k.startswith(p) for p in LOWER)


def tri_samples(v, f, per_mm2=0.25, rng=None, cap=60000):
    """area-weighted surface samples + every vertex (a decimated Z bone has a quarter of the own-page bone's
    vertices, so a vertex-to-vertex distance would report the decimation and not the fit)."""
    rng = rng or np.random.default_rng(0)
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    ar = 0.5 * np.linalg.norm(np.cross(b - a, c - a), axis=1)
    tot = float(ar.sum())
    n = int(min(cap, max(0, np.ceil(tot * per_mm2))))
    if n <= 0 or tot <= 0:
        return v
    k = rng.choice(len(f), size=n, p=ar / tot)
    u, w = rng.random(n), rng.random(n)
    m = u + w > 1.0
    u[m], w[m] = 1.0 - u[m], 1.0 - w[m]
    return np.vstack([v, a[k] + u[:, None] * (b[k] - a[k]) + w[:, None] * (c[k] - a[k])])


class Field:
    """identity + a thin-plate-spline correction fitted to closest-point displacements on shared bones.

    groups: {name: (src_points (N,3), dst_tree cKDTree of dense target-surface samples)}
    """

    def __init__(self, groups, iters=3, trim_mm=8.0, smoothing=10.0, ncp=3500, cp_vox=8.0, seed=0):
        self.groups = list(groups)
        X = np.vstack([groups[g][0] for g in self.groups])
        self.gidx = np.concatenate([np.full(len(groups[g][0]), i) for i, g in enumerate(self.groups)])
        self.X = X
        self.trim_mm = float(trim_mm)
        rng = np.random.default_rng(seed)
        D = np.zeros_like(X)
        self.rbf = None
        for it in range(iters):
            Y = np.empty_like(X); d = np.empty(len(X))
            for i, g in enumerate(self.groups):
                m = self.gidx == i
                dd, jj = groups[g][1].query(X[m] + D[m], workers=-1)
                Y[m] = groups[g][2][jj]; d[m] = dd
            keep = d <= trim_mm
            if keep.sum() < 500:
                keep = d <= np.quantile(d, 0.95)
            T = Y - X                                           # total displacement wanted at X
            key = np.floor(X[keep] / cp_vox).astype(np.int64)
            _, first = np.unique(key, axis=0, return_index=True)
            idx = np.nonzero(keep)[0][first if len(first) <= ncp else rng.choice(first, ncp, replace=False)]
            self.rbf = RBFInterpolator(X[idx], T[idx], kernel="thin_plate_spline", smoothing=smoothing, degree=1)
            D = self(X) - X                                  # the DISPLACEMENT field, not the mapped points
            self.kept = int(keep.sum()); self.iters = it + 1
        # the honest residual: where the mapped source surface lands relative to the target surface
        res = np.empty(len(X))
        for i, g in enumerate(self.groups):
            m = self.gidx == i
            res[m] = groups[g][1].query(X[m] + D[m], workers=-1)[0]
        self.resid = res
        self.before = np.empty(len(X))
        for i, g in enumerate(self.groups):
            m = self.gidx == i
            self.before[m] = groups[g][1].query(X[m], workers=-1)[0]
        self.D = D
        self.tree = cKDTree(X)
        self.control_points = int(len(idx))

    def __call__(self, P):
        P = np.asarray(P, float)
        out = np.empty_like(P)
        for a in range(0, len(P), 20000):
            out[a:a + 20000] = P[a:a + 20000] + self.rbf(P[a:a + 20000])
        return out

    @staticmethod
    def _st(r):
        return dict(n=int(len(r)), median_mm=round(float(np.median(r)), 2),
                    p95_mm=round(float(np.quantile(r, 0.95)), 2), max_mm=round(float(r.max()), 2),
                    rms_mm=round(float(np.sqrt((r ** 2).mean())), 2))

    def stats(self):
        s = self._st(self.resid)
        s.update(before=self._st(self.before), kept_pairs=self.kept, iters=self.iters,
                 control_points=self.control_points, trim_mm=self.trim_mm,
                 displacement_median_mm=round(float(np.median(np.linalg.norm(self.D, axis=1))), 2),
                 displacement_p95_mm=round(float(np.quantile(np.linalg.norm(self.D, axis=1), 0.95)), 2),
                 displacement_max_mm=round(float(np.linalg.norm(self.D, axis=1).max()), 2))
        return s

    def per_group(self):
        out = {}
        for i, g in enumerate(self.groups):
            m = self.gidx == i
            out[g] = dict(after=self._st(self.resid[m]), before=self._st(self.before[m]))
        return out

    def local(self, P, radius=40.0):
        """the residual of the bone correspondences within `radius` of this structure's own vertices."""
        P = np.asarray(P, float)
        idx = set()
        for lst in self.tree.query_ball_point(P[:: max(1, len(P) // 400)], radius):
            idx.update(lst)
        if len(idx) < 20:
            _, i = self.tree.query(P, k=min(60, len(self.X)))
            idx = set(np.asarray(i).ravel().tolist())
        r = self.resid[sorted(idx)]
        s = self._st(r); s["radius_mm"] = radius
        return s
