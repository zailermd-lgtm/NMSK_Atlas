"""Q340 palm helpers: the palm frame of a Base page side (metacarpal plane + palmar normal) and the layer heights in it.

Palm frame of side s (model space, mm):
  d_h  the hand axis: wrist joint centre (pose rig) -> centroid of metacarpals 2-5;
  n    the palmar normal of the METACARPAL PLANE: the least-squares plane through the palmar-most 15 % of the
       middle-60 % shaft vertices of metacarpals 2-5 (the palmar sense taken from the rig's finger-3 flexion direction,
       hand_frame.Hand: "flexion moves the distal segment toward the palm");
  t    along the hand in that plane (d_h minus its n part), r = n x t turned toward the thumb.
  h    = height above the metacarpal plane along n (> 0 palmar).
Reads the page through the Q338 Page (scripts/anatomy/q338/hand_audit_q338.py); never writes."""
from __future__ import annotations
import sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "q338"))
import hand_audit_q338 as A  # noqa: E402,F401  (re-exported as lib340.A: the Q338 Page)
import hand_frame as HF      # noqa: E402



class Palm:
    def __init__(self, pg, s):
        self.s = s
        B = pg.M.bones(); J = {j["id"]: j for j in pg.rig["joints"]}
        w = np.array(J["wrist_" + s]["c"], float)
        mcs = [B["mc_%d_%s" % (f, s)]["v"] for f in range(2, 6)]
        d_h = HF.unit(np.vstack(mcs).mean(0) - w)
        p0 = pg.H[s].fingers[3][0]["p"]; p0 = HF.unit(p0 - (p0 @ d_h) * d_h)
        top = []
        for v in mcs:
            a = (v - w) @ d_h; lo, hi = np.percentile(a, [20, 80])
            m = (a > lo) & (a < hi); q = v[m]; pp = q @ p0
            top.append(q[pp >= np.percentile(pp, 85)])
        T = np.vstack(top); c = T.mean(0)
        n = np.linalg.svd(T - c)[2][2]
        if n @ p0 < 0:
            n = -n
        t = HF.unit(d_h - (d_h @ n) * n)
        r = HF.unit(np.cross(n, t))
        th = B["mc_1_" + s]["v"].mean(0)
        if (th - c) @ r < 0:
            r = -r
        self.w, self.c, self.n, self.t, self.r = w, c, n, t, r
        self.mc_t = [float(((v - c) @ t).min()) for v in mcs] + [float(((v - c) @ t).max()) for v in mcs]
        self.plane_rms = float(np.sqrt((((T - c) @ n) ** 2).mean()))

    def trh(self, P):
        D = np.asarray(P, float) - self.c
        return np.c_[D @ self.t, D @ self.r, D @ self.n]


def sid(pg, base, s):
    """structure id on the page for a base name and side (the left aponeurosis carries a zan_ prefix on these pages)"""
    for k in (base + "_" + s, "zan_" + base + "_" + s, base.replace("zan_", "") + "_" + s):
        if k in pg.byid:
            return k
    return None


# ---------------------------------------------------------------------------------------------------- height maps (1 mm columns along n)
HCELL = 1.0


def surface_samples(v, f, spacing=0.35):
    """points on every triangle at about `spacing` mm (barycentric lattice), plus the vertices -- deterministic"""
    T = v[f]
    e = np.maximum(np.linalg.norm(T[:, 1] - T[:, 0], axis=1), np.linalg.norm(T[:, 2] - T[:, 0], axis=1))
    out = [v]
    for k in np.unique(np.clip(np.ceil(e / spacing).astype(int), 1, 12)):
        sel = T[np.clip(np.ceil(e / spacing).astype(int), 1, 12) == k]
        ab = np.array([(i / k, j / k) for i in range(k + 1) for j in range(k + 1 - i)])
        out.append((sel[:, None, 0] * (1 - ab[:, 0] - ab[:, 1])[None, :, None] + sel[:, None, 1] * ab[None, :, 0, None]
                    + sel[:, None, 2] * ab[None, :, 1, None]).reshape(-1, 3))
    return np.vstack(out)


class HMap:
    """top (max h) and bottom (min h) of a set of surfaces per 1 mm (t, r) column"""

    def __init__(self, palm, meshes, cell=HCELL):
        self.cell = cell
        X = palm.trh(np.vstack([surface_samples(v, f) for v, f in meshes])) if meshes else np.zeros((0, 3))
        I = np.floor(X[:, :2] / cell).astype(np.int64)
        self.o = I.min(0) - 2 if len(I) else np.zeros(2, int)
        sh = (I.max(0) - self.o + 3) if len(I) else np.ones(2, int)
        self.top = np.full(sh, -np.inf); self.bot = np.full(sh, np.inf)
        J = I - self.o
        np.maximum.at(self.top, (J[:, 0], J[:, 1]), X[:, 2])
        np.minimum.at(self.bot, (J[:, 0], J[:, 1]), X[:, 2])

    def at(self, TR):
        J = np.floor(np.asarray(TR)[:, :2] / self.cell).astype(np.int64) - self.o
        ok = (J >= 0).all(1) & (J[:, 0] < self.top.shape[0]) & (J[:, 1] < self.top.shape[1])
        top = np.full(len(J), -np.inf); bot = np.full(len(J), np.inf)
        top[ok] = self.top[J[ok, 0], J[ok, 1]]; bot[ok] = self.bot[J[ok, 0], J[ok, 1]]
        return top, bot

    def inside(self, TRH, tol=0.3):
        """points lying within the column extent of the surfaces (bottom + tol < h < top - tol): inside a tendon / nerve / sheet cross-section"""
        top, bot = self.at(TRH)
        return (TRH[:, 2] > bot + tol) & (TRH[:, 2] < top - tol)
