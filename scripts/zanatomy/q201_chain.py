"""Q201: the kinematic chain humerus -> radius / ulna (-> wrist) of the Z-Anatomy model fitted to the VISIBLE HUMAN MALE, from HIS evidence (his CT labels completed through his colour
cryosection photographs: scripts/cryo/q201_arm_evidence.py).  Counterpart of q199_elbow.fit_left / fit_right (her photographs / labels).

Why (measured on the Q195 state): the Q168 per-bone similarity fit treats his radius / ulna / humerus as FOV-cut (the completed labels end in a flat plane at the joint line, 5-8 cm of the
real bones are in the "wrong" label) and lets the Z bone run on beyond the cut: the left Z ulna's olecranon stands at y = 348 in the air outside the arm (his bone mass at the elbow ends at 287),
the right Z radius / ulna were shrunk to scale 0.84 / 0.87 (wrist 28 mm off the carpals).  The labels are right where they are bone-specific (humerus y > 335, radius / ulna y < 236) and
right as ONE union where the completion split one cream bone mass by a plane (y 236 .. 335).  So:
  * each of the three Z bones gets its own similarity transform (rotation about its centroid, translation, uniform scale within +-8 % of its Q195 scale),
  * fitted to (a) its own label surface outside the elbow zone (two-way capped chamfer, the Z samples only inside the label's y range), (b) the union solid of the zone: the Z samples of the
    three bones inside the zone must lie in the solid (distance 0 inside) and the boundary of the solid must be covered by the Z union surface, (c) the Z-source joint (surface pairs that touch
    in the Z source keep their source distance), (d) small priors on the scale and the motion.
The soft tissue then follows through the same bone-anchored field as Q199 (q199_elbow.Field), the wrist (carpals, hand: fixed bones of the field) stays.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from scipy import ndimage as ndi
from scipy.optimize import least_squares
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation as Rot

from scripts.zanatomy import q190_metrics as Mx
from scripts.zanatomy import q199_elbow as E

REPO = Path(__file__).resolve().parents[2]
EVID = REPO / "data" / "derived" / "Q201_vhm_arm_evidence.npz"
ZONE = (236.0, 335.0)
CAP_FAR_MM = 60.0
SCALE_ABS = {"humerus": (1.0, 1.15), "radius": (0.95, 1.12), "ulna": (0.95, 1.12)}      # absolute scale of the Z source bone (his humerus label is 1.11 x the Z source)
ROT_MAX_DEG = 75.0
W_PAIR = 2.0
BOX = (5.0, 8.0, 0.03)              # stage B may move a bone at most 5 deg / 8 mm / 3 % scale from its label-only fit (+ the bend)
BONES = ("humerus", "radius", "ulna")


def _sstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


BEND_FROM = 0.45           # the bend (shape difference between his bone and the Z bone) grows from 45 % of the bone length towards the elbow end to the full amount at the end
BEND_MAX_MM = 15.0


class ChainM:
    """per-bone transform (same interface as q199_elbow.Chain for the Field / refine_side: hum, rad, uln, hc, P): a smooth bend at the elbow end (3 mm parameters, shape difference between his
    bone and the Z bone, <= BEND_MAX_MM) in the bone's Q195 frame, then similarity (rotation about the bone's Q195 centroid, scale, translation).  p = [rotvec(3), translation(3), scale, bend(3)]"""

    def __init__(self, side, by, params=None):
        s = "_" + side
        self.side = side
        self.c, self.ax, self.tr = {}, {}, {}
        for b in BONES:
            v = by[b + s]["v"]
            c = v.mean(0)
            a = np.linalg.eigh((v - c).T @ (v - c))[1][:, -1]
            if (a[1] < 0) != (b == "humerus"):         # axis points to the elbow end: down for the humerus, up for the forearm bones
                a = -a
            t = (v - c) @ a
            self.c[b], self.ax[b], self.tr[b] = c, a, (float(t.min()), float(t.max()))
        v = by["humerus" + s]["v"]
        self.hc = E.sphere_centre(v[v[:, 1] > v[:, 1].max() - 30.0])
        self.p = {b: np.r_[np.zeros(6), 1.0, np.zeros(3)] for b in BONES}
        if params is not None:
            for b in BONES:
                self.p[b] = np.r_[np.asarray(params[b], float), np.zeros(10 - len(params[b]))]

    @property
    def P(self):                                    # humerus rotation + translation first (refine_side asks whether the humerus moved)
        return np.r_[self.p["humerus"][:6], self.p["humerus"][6], self.p["radius"][:6], self.p["ulna"][:6]]

    def apply(self, b, X, p=None):
        p = self.p[b] if p is None else p
        X = np.asarray(X, float)
        t0, t1 = self.tr[b]
        w = _sstep((((X - self.c[b]) @ self.ax[b] - t0) / (t1 - t0) - BEND_FROM) / (1.0 - BEND_FROM))
        Xb = X + w[:, None] * p[7:10][None, :]
        R = Rot.from_rotvec(p[:3]).as_matrix()
        return ((Xb - self.c[b]) * p[6]) @ R.T + self.c[b] + p[3:6]

    def hum(self, X, P=None):
        return self.apply("humerus", X)

    def rad(self, X, P=None):
        return self.apply("radius", X)

    def uln(self, X, P=None):
        return self.apply("ulna", X)


def load_evidence(path=EVID):
    z = np.load(path)
    return {k: z[k].astype(float) for k in z.files if k != "note"}


def _union_field(P, pad=25.0):
    """EDT of the union solid (1 mm grid) around the zone: distance to the solid, 0 inside; lookup by trilinear interpolation"""
    lo = np.floor(P.min(0) - pad).astype(int)
    hi = np.ceil(P.max(0) + pad).astype(int)
    shape = tuple(hi - lo + 1)
    g = np.zeros(shape, bool)
    ij = np.round(P - lo).astype(int)
    g[ij[:, 0], ij[:, 1], ij[:, 2]] = True
    g = ndi.binary_closing(g, iterations=1)
    d = ndi.distance_transform_edt(~g).astype(np.float32)
    bound = g & ~ndi.binary_erosion(g)
    B = np.argwhere(bound) + lo
    return lo, d, B.astype(float)


def _lookup(lo, d, X):
    return ndi.map_coordinates(d, (X - lo).T, order=1, mode="nearest")


def _procrustes_scale(r, v):
    a, b = np.asarray(r, float), np.asarray(v, float)
    return float(np.sqrt(((b - b.mean(0)) ** 2).sum() / ((a - a.mean(0)) ** 2).sum()))


class Fit:
    def __init__(self, side, by, raw, ev, n=3000):
        s = "_" + side
        self.side, self.by, self.raw = side, by, raw
        self.smp = {b: E.bary_samples(raw[b + s], by[b + s]["f"], n, seed=21) for b in BONES}
        self.v0 = {b: by[b + s]["v"] for b in BONES}
        self.S0 = {b: E.at(self.v0[b], self.smp[b]) for b in BONES}
        self.c0 = {b: self.v0[b].mean(0) for b in BONES}
        rng = np.random.default_rng(5)
        self.lab = {}
        for b in BONES:
            P = ev[f"shaft_{b}_{side}"]
            self.lab[b] = (cKDTree(P[rng.permutation(len(P))[:6000]]), P[rng.permutation(len(P))[:2500]], (P[:, 1].min(), P[:, 1].max()))
        U = ev[f"union_{side}"]
        self.lo, self.edt, self.bound = _union_field(U)
        self.bound_s = self.bound[rng.permutation(len(self.bound))[:3000]]
        self.jsmp, self.jsel, self.jj, self.jd0 = E.joint_pairs(raw, side, by)
        self.cur = {b: np.r_[np.zeros(6), 1.0, np.zeros(3)] for b in BONES}
        self.abs0 = {b: _procrustes_scale(raw[b + s], by[b + s]["v"]) for b in BONES}

    def chain(self, cur=None):
        ch = ChainM(self.side, self.by, cur or self.cur)
        return ch

    def surfaces(self, cur):
        ch = self.chain(cur)
        return ch, {b: ch.apply(b, self.S0[b]) for b in BONES}

    def parts(self, cur, active=BONES, w_joint=True):
        ch, S = self.surfaces(cur)
        sh, sr = [], []
        for b in active:
            tree, Pl, (y0, y1) = self.lab[b]
            inr = (S[b][:, 1] >= y0 - 5) & (S[b][:, 1] <= y1 + 5) & ((S[b][:, 1] > ZONE[1]) if b == "humerus" else (S[b][:, 1] < ZONE[0] + 8))
            sh.append(np.where(inr, np.minimum(tree.query(S[b])[0], CAP_FAR_MM), 0.0))
            sr.append(np.minimum(cKDTree(S[b]).query(Pl)[0], CAP_FAR_MM))
        Zall = np.vstack([S[b] for b in BONES])
        inz = (Zall[:, 1] >= ZONE[0]) & (Zall[:, 1] <= ZONE[1])
        up = np.where(inz, np.minimum(_lookup(self.lo, self.edt, Zall), CAP_FAR_MM), 0.0)
        ur = np.minimum(cKDTree(Zall).query(self.bound_s)[0], CAP_FAR_MM)
        h = E.at(ch.hum(self.v0["humerus"]), self.jsmp["humerus"])
        f = np.vstack([E.at(ch.rad(self.v0["radius"]), self.jsmp["radius"]), E.at(ch.uln(self.v0["ulna"]), self.jsmp["ulna"])])
        pair = np.linalg.norm(h[self.jsel] - f[self.jj], axis=1) - self.jd0
        return np.concatenate(sh), np.concatenate(sr), up, ur, pair

    def reg(self, cur, active):
        r = []
        for b in active:
            p = cur[b]
            r += [20.0 * (p[6] * self.abs0[b] - Mx.BODY_SCALE) if b != "humerus" else 0.0, 0.01 * np.degrees(np.linalg.norm(p[:3])), 0.01 * np.linalg.norm(p[3:6]), 0.15 * np.linalg.norm(p[7:10])]
        return np.array(r)

    def stats(self, cur):
        sh, sr, up, ur, pair = self.parts(cur)
        ch, S = self.surfaces(cur)
        jt = E.joint_stat(self.jsmp, self.jsel, self.jj, self.jd0, ch.hum(self.v0["humerus"]), ch.rad(self.v0["radius"]), ch.uln(self.v0["ulna"]))
        return {"label_surface_to_Z_mm_median": round(float(np.median(sr)), 2), "Z_to_label_mm_median": round(float(np.median(sh[sh > 0])) if (sh > 0).any() else 0.0, 2),
                "union_Z_outside_solid_mm_mean": round(float(up[up > 0].mean()) if (up > 0).any() else 0.0, 2), "union_Z_outside_solid_pct": round(100 * float((up > 0.5).mean()), 1),
                "union_boundary_to_Z_mm_median": round(float(np.median(ur)), 2), "union_boundary_to_Z_mm_p90": round(float(np.percentile(ur, 90)), 2), "joint": jt}

    def axis(self, b):
        v = self.v0[b]
        c = v - v.mean(0)
        return np.linalg.eigh(c.T @ c)[1][:, -1]

    def stage(self, active, w_pair, cur0=None, rot_max_deg=ROT_MAX_DEG, w_union=1.0, box=None, labels_only=False, trans_max=60.0):
        """least squares over the similarity parameters of `active`; box = (rot_deg, trans_mm, scale_rel) around cur0 (the later stage may only refine)"""
        cur = dict(self.cur if cur0 is None else cur0)
        base = {b: cur[b].copy() for b in active}

        def unpack(x):
            c = dict(cur)
            for k, b in enumerate(active):
                c[b] = x[10 * k:10 * k + 10]
            return c

        def resid(x):
            c = unpack(x)
            sh, sr, up, ur, pair = self.parts(c, active)
            if labels_only:
                return np.r_[sh, sr, self.reg(c, active)]
            return np.r_[sh, sr, w_union * up, w_union * ur, w_pair * pair, self.reg(c, active)]
        x0 = np.concatenate([cur[b] for b in active])
        lo, hi = [], []
        bm = 1e-6 if labels_only else BEND_MAX_MM
        for b in active:
            smin, smax = SCALE_ABS[b][0] / self.abs0[b], SCALE_ABS[b][1] / self.abs0[b]
            if box is None:
                r = np.radians(rot_max_deg)
                lo.append(np.r_[-r * np.ones(3), -trans_max * np.ones(3), smin, -bm * np.ones(3)])
                hi.append(np.r_[r * np.ones(3), trans_max * np.ones(3), smax, bm * np.ones(3)])
            else:
                dr, dt, ds = np.radians(box[0]), box[1], box[2]
                p0 = base[b]
                lo.append(np.r_[p0[:3] - dr, p0[3:6] - dt, max(smin, p0[6] - ds), -bm * np.ones(3)])
                hi.append(np.r_[p0[:3] + dr, p0[3:6] + dt, min(smax, p0[6] + ds), bm * np.ones(3)])
        lo, hi = np.concatenate(lo), np.concatenate(hi)
        xs = np.tile(np.r_[0.05 * np.ones(3), 5 * np.ones(3), 0.02, 3 * np.ones(3)], len(active))
        s = least_squares(resid, np.clip(x0, lo + 1e-9, hi - 1e-9), bounds=(lo, hi), x_scale=xs, loss="soft_l1", f_scale=3.0, max_nfev=60)
        return unpack(s.x), float(s.cost)

    def label_fit(self, b):
        """one bone against its own label (the wrist / shaft / head: CT), multi-start over the roll about its long axis (the roll is the weakly constrained DOF of a long bone)"""
        ax = self.axis(b)
        best = None
        for roll in (0, 45, -45, 90, -90, 135, 180):
            cur = dict(self.cur)
            p = np.r_[np.radians(roll) * ax, np.zeros(3), 1.0, np.zeros(3)]
            p[6] = float(np.clip(Mx.BODY_SCALE / self.abs0[b], SCALE_ABS[b][0] / self.abs0[b], SCALE_ABS[b][1] / self.abs0[b])) if b != "humerus" else 1.0
            cur[b] = p
            c, cost = self.stage((b,), 0.0, cur, labels_only=True)
            if best is None or cost < best[0]:
                best = (cost, c[b], roll)
        return best

    def run(self, log=print):
        before = self.stats(self.cur)
        cur = dict(self.cur)
        starts = {}
        for b in BONES:                                          # A. every bone against its own label (humerus: head + shaft, radius / ulna: shaft + wrist)
            cost, p, roll = self.label_fit(b)
            cur[b] = p
            starts[b] = roll
        self.stage_a = {b: cur[b].copy() for b in BONES}
        self.stage_a_stats = self.stats(cur)
        cur, _ = self.stage(BONES, W_PAIR, cur, box=BOX)         # B. all three: the union of the elbow zone and the Z-source joint, within a small box around A
        self.cur = cur
        self.starts = starts
        return cur, before, self.stats(cur)


def fit_male(side, by, raw, ev=None, log=print):
    """returns (ChainM, report)"""
    ev = ev if ev is not None else load_evidence()
    F = Fit(side, by, raw, ev)
    cur, before, after = F.run(log)
    ch = F.chain(cur)
    rep = {"frame": "his CT labels completed through his cryosection photographs (atlas = world + (6.0, 895.4 z, -4.8 y))", "before": before, "after": after,
           "stage_a": {"stats": F.stage_a_stats, "start_roll_deg": F.starts, "params": {b: F.stage_a[b].round(4).tolist() for b in BONES}},
           "params": {b: {"rot_deg": round(float(np.degrees(np.linalg.norm(ch.p[b][:3]))), 2), "translation_mm": ch.p[b][3:6].round(2).tolist(), "scale_vs_q195": round(float(ch.p[b][6]), 4), "bend_mm": ch.p[b][7:10].round(1).tolist()} for b in BONES},
           "bone_move_mm": {b: {"max": round(float(np.linalg.norm(ch.apply(b, F.v0[b]) - F.v0[b], axis=1).max()), 1), "mean": round(float(np.linalg.norm(ch.apply(b, F.v0[b]) - F.v0[b], axis=1).mean()), 1)} for b in BONES}}
    log(f"  Q201 {side} chain: {rep['params']}")
    log(f"  Q201 {side} before {before}\n         after  {after}")
    return ch, rep
