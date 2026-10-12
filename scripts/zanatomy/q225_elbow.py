"""Q225 left-elbow bone re-seat of the two Z-fitted pages.

The fits put the three left-arm bones on the person's evidence ONE BONE AT A TIME (similarity + bend per bone, Q168 / Q199 / Q201), so the joint surfaces are not congruent: ulna 9.4 mm into the humerus (his),
humerus / radius 7.7 mm (hers); the unfitted Z bases have joint spaces (0.7 / 4.7 / 2.2 mm) and no contact.  Fix = a LOCAL rigid correction of the elbow end of the radius and the ulna
    d(v) = s(t) * (tau + theta x (v - c)),   t = position along the bone from its elbow end (0) to the wrist end (1),   s = 1 - smoothstep(t / TAPER)
(tau, theta per bone: 6 parameters; the humerus is the fixed frame, the wrist ends are not touched, so the Q201 / Q205 wrist chain stays), found by a damped least squares of
  (1) joint-space residuals  max(0, g_pair - clearance) over the surface samples of each of the 3 pairs (g_pair = the joint space MEASURED ON THE UNFITTED BASE model, 5th percentile of the contact patch),
  (2) a pull of the patch 5th percentile clearance toward the base value (no wider joint than the base),
  (3) the person's OWN bones (evidence) : capped chamfer of the bone surface to the person's own bone mesh both ways,
  (4) a small regulariser on the move.
Clearances come from signed-distance fields of the bone solids (q225_joint.Sdf); the inverse of the (smooth) deformation is approximated by p - d(p) for the cross terms."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q225_joint as J  # noqa: E402

TAPER = 0.55           # fraction of the bone length over which the correction fades to zero


def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


class Taper:
    """local rigid correction of the elbow end of a bone"""

    def __init__(self, v, elbow_pt, taper=TAPER):
        v = np.asarray(v, float)
        # elbow end = the end of the long axis nearest to `elbow_pt`
        c = v.mean(0)
        u, s, vt = np.linalg.svd(v - c, full_matrices=False)
        ax = vt[0]
        pr = (v - c) @ ax
        lo, hi = pr.min(), pr.max()
        if abs((c + ax * lo - elbow_pt) @ ax) > abs((c + ax * hi - elbow_pt) @ ax):
            ax, pr = -ax, -pr
            lo, hi = pr.min(), pr.max()
        self.ax, self.c0, self.lo, self.L, self.taper = ax, c, lo, hi - lo, taper
        # centre of rotation = centroid of the elbow-end 15 % of the bone
        near = v[pr < lo + 0.15 * self.L]
        self.cen = near.mean(0)

    def weight(self, p):
        t = ((np.asarray(p, float) - self.c0) @ self.ax - self.lo) / self.L
        return 1.0 - smoothstep(t / self.taper)

    def disp(self, p, par):
        p = np.asarray(p, float)
        tau, th = par[:3], par[3:6]
        return self.weight(p)[:, None] * (tau[None, :] + np.cross(th[None, :], p - self.cen))

    def apply(self, p, par):
        return np.asarray(p, float) + self.disp(p, par)


def percentile_patch(c, patch_mm=6.0, q=5.0):
    c = np.asarray(c)
    c = c[c < patch_mm]
    return float(np.percentile(c, q)) if len(c) else float("nan")


class Fit:
    """bones: dict name -> (v, f) of the FITTED page; fixed = ('humerus_l',); moving = ('ulna_l', 'radius_l'); gaps = {(a, b): joint space on the base (mm)}; own = {name: (v, f)} evidence"""

    def __init__(self, bones, own, gaps, elbow_pt, moving=("ulna_l", "radius_l"), fixed=("humerus_l",), h=1.0, log=print, w_ev=0.6, w_reg=0.02, w_pull=4.0, w_gap=6.0, ev_cap=8.0, taper=TAPER, floor_frac=0.5):
        self.bones, self.own, self.gaps, self.moving, self.fixed, self.log = bones, own, gaps, list(moving), list(fixed), log
        self.names = list(fixed) + list(moving)
        self.w_ev, self.w_reg, self.w_pull, self.w_gap, self.ev_cap, self.floor_frac = w_ev, w_reg, w_pull, w_gap, ev_cap, floor_frac
        self.sdf = {n: J.Sdf(*bones[n], h=h) for n in self.names}
        self.tp = {n: Taper(bones[n][0], elbow_pt, taper) for n in self.moving}
        self.samp = {}
        for n in self.names:
            idx, w = J.surf_samples(*bones[n], spacing=1.6, cap=4000)
            self.samp[n] = (idx, w, J.sample_pts(bones[n][0], idx, w))
        self.pairs = [(a, b) for k, a in enumerate(self.names) for b in self.names[k + 1:] if (a, b) in gaps or (b, a) in gaps]
        # evidence (own bones, vertices; only the part near the elbow zone matters: the taper region of the bone)
        self.ev = {}
        for n in self.moving:
            if n in own:
                self.ev[n] = (own_tree(*own[n]),)
        self.ev_n = {}
        self.par = {n: np.zeros(6) for n in self.moving}

    # ---- geometry under parameters -----------------------------------------------------------
    def pos(self, n, P, par):
        """sample positions of bone n under the parameter dict `par`"""
        return self.tp[n].apply(P, par[n]) if n in self.moving else P

    def inv_pos(self, n, Q, par):
        """approximate pre-image of points Q under bone n's deformation (so the bone's ORIGINAL sdf can be used)"""
        if n not in self.moving:
            return Q
        x = Q.copy()
        for _ in range(2):
            x = Q - self.tp[n].disp(x, par[n])
        return x

    def clearances(self, par):
        out = {}
        for a, b in self.pairs:
            pa = self.pos(a, self.samp[a][2], par)
            pb = self.pos(b, self.samp[b][2], par)
            ca = self.sdf[b](self.inv_pos(b, pa, par))
            cb = self.sdf[a](self.inv_pos(a, pb, par))
            out[(a, b)] = (ca, cb)
        return out

    def residuals(self, x):
        par = {n: x[6 * k:6 * k + 6] for k, n in enumerate(self.moving)}
        res = []
        for (a, b), (ca, cb) in self.clearances(par).items():
            g = self.gaps.get((a, b), self.gaps.get((b, a)))
            c = np.concatenate([ca, cb])
            res.append(self.w_gap * np.maximum(self.floor_frac * g - c, 0.0) / np.sqrt(len(c)) * 6.0)
            m = percentile_patch(c)
            if np.isfinite(m):
                res.append(np.array([self.w_pull * (m - g)]))
        for n in self.moving:
            if n in self.ev:
                tr_own = self.ev[n][0]
                P = self.pos(n, self.samp[n][2], par)
                d1 = np.minimum(tr_own.query(P)[0], self.ev_cap)
                res.append(self.w_ev * d1 / np.sqrt(len(d1)) * 3.0)
        for n in self.moving:
            p = par[n]
            res.append(np.array([self.w_reg * np.linalg.norm(p[:3]), self.w_reg * np.linalg.norm(p[3:]) * self.tp[n].L * self.tp[n].taper * 0.5]))
        return np.concatenate(res)

    def solve(self, x0=None, max_nfev=80):
        x0 = np.zeros(6 * len(self.moving)) if x0 is None else x0
        r = least_squares(self.residuals, x0, method="trf", x_scale=np.tile([2, 2, 2, 0.02, 0.02, 0.02], len(self.moving)), diff_step=1e-3, max_nfev=max_nfev)
        return r

    def params(self, x):
        return {n: x[6 * k:6 * k + 6] for k, n in enumerate(self.moving)}

    def deformed(self, x):
        par = self.params(x)
        return {n: self.tp[n].apply(self.bones[n][0], par[n]) for n in self.moving}


def own_tree(v, f, spacing=1.5):
    """KD-tree of dense surface samples of the person's own bone mesh (vertex-only distances overestimate on coarse triangles)"""
    idx, w = J.surf_samples(v, f, spacing=spacing, cap=200000)
    return cKDTree(np.vstack([np.asarray(v, float), J.sample_pts(v, idx, w)]))


def evidence_error(v, f, own_vf, zone_frac=None, taper=None, cap=25.0):
    """per-bone fit error against the person's own bone mesh: (fit -> own mean, own -> fit mean [own samples within `cap` mm of the fit], both mm).  zone_frac: only the part of the bone
    with Taper weight > 0.05 (the elbow end) is counted."""
    v = np.asarray(v, float)
    idx, w = J.surf_samples(v, f, spacing=1.5, cap=60000)
    P = np.vstack([v, J.sample_pts(v, idx, w)])
    to = own_tree(*own_vf)
    tf = cKDTree(P)
    if taper is not None:
        m = taper.weight(P) > 0.05
        P = P[m]
        a = to.query(P)[0]
        oi, ow = J.surf_samples(*own_vf, spacing=1.5, cap=100000)
        O = J.sample_pts(own_vf[0], oi, ow)
        mo = taper.weight(O) > 0.05
        d = tf.query(O[mo])[0]
    else:
        a = to.query(P)[0]
        oi, ow = J.surf_samples(*own_vf, spacing=1.5, cap=100000)
        O = J.sample_pts(own_vf[0], oi, ow)
        d = tf.query(O)[0]
    b = d[d < cap]
    return round(float(a.mean()), 2), round(float(b.mean()), 2) if len(b) else None
