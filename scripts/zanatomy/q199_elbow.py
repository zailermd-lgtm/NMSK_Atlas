"""Q199: the ELBOW of the female Z-Anatomy viewer, both arms.  humerus - radius - ulna as ONE kinematic chain, the soft tissue carried by a bone-anchored smooth field.

Why (measured on v12 = Q194 state): the left upper arm (humerus, biceps / triceps / brachialis, brachial vessels ...) is in the CT frame, the left forearm (bones Q192, soft tissue
Q194) and her skin are in the cryosection-photograph frame; her left humerus lies 16-20 mm (z) from the same humerus in the photographs (30 mm at the elbow, 7 deg of tilt) and
the Z ulna / radius do not articulate with the Z humerus (nearest-surface gap at the contact patch 27.4 mm, the Z source 5.4 mm; right elbow 9.8 mm).  Q194 bridged this with a 100 mm
blend.  Here:
  1. CHAIN (per side).  Humerus: ONE rigid motion + scale about her CT humeral-head centre (the shoulder stays in the glenoid within 4 mm) from (a) the centres of the humerus
     disc in her photographs at y = 380, 430 ... 500 (left; data/derived/Q199_left_arm_evidence.npz, scripts/cryo/q199_arm_evidence.py) and (b) the bone blobs of the elbow levels y = 312 ..
     354 (trimmed two-way chamfer to the Z bones).  Forearm: radius and ulna each swing (2 DOF, no twist: the pronation is Q192's) about the wrist centre, so the wrist and the hand stay.  The
     Z-source joint (surface pairs that touch in the Z source) must stay a joint.  RIGHT arm: her own CT labels are the frame of the whole chain (shoulder to hand), so the humerus stays on her
     humerus label and only the two forearm bones swing (bounded) until the joint closes.
  2. FIELD.  Every soft structure of the arm moves by  D(x) = sum_b w_b(x) D_b(x)  over the moving bones (humerus: its rigid motion, radius / ulna: their swings) and the fixed bones
     (shoulder girdle, ribs, carpals, hand: D = 0) plus a null anchor 40 mm out (so tissue far from every bone moves less, and skin does not move);  w_b = 1 / (d_b + 6 mm)^2 with d_b the
     distance to the bone as it was.  No axial blend length: the elbow transition is where the nearest bone changes.
  3. PER STRUCTURE.  candidates (field, field low-passed 10 / 25 mm, mean translation) pushed out of the displayed bones, inside her skin, volume 0.65-1.5x the Z source (other closed
     meshes +-10 %), the cheapest by a cost (skin + bone + stretch + 6 x folds + attachment excess + her-label excess, the field is kept unless another is better by > 2); then the origin /
     insertion footprints (Z-source vertices < 8 mm from the humerus / radius / ulna / scapula / clavicle) that sit > 3 mm further from their bone than in the Z source are brought back by a
     smooth end translation (<= 10 mm; the part of a right-arm muscle that lies on her own label is not moved); pairs that touch in the Z source and are > 5 mm apart (vessel / nerve pairs > 3 mm)
     close up; the neighbour-muscle overlap is reduced by the Q194 bounded separation on the shipped meshes (<= 5 mm).  Everything after the field stays within 10 mm of the field result.
Everything else is untouched (bit-identical vertices).
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
from scipy.optimize import least_squares
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation as Rot

REPO = Path(__file__).resolve().parents[2]
EVID = REPO / "data" / "derived" / "Q199_left_arm_evidence.npz"

W_SOFT_MM, W_POWER, W_NULL_MM = 6.0, 2.0, 90.0
HEAD_SHIFT_MM = 4.0
SWING_DEG_W = 0.15
CAP_MM = 7.0


# ------------------------------------------------------------------------------------------------ helpers
def bary_samples(v, f, n=3000, seed=1):
    """n barycentric surface samples of the mesh (f, bary) -> positions on ANY vertex array with the same topology"""
    v = np.asarray(v, float)
    t = v[f]
    area = 0.5 * np.linalg.norm(np.cross(t[:, 1] - t[:, 0], t[:, 2] - t[:, 0]), axis=1)
    rng = np.random.default_rng(seed)
    fi = rng.choice(len(f), n, p=area / area.sum())
    u = rng.random((n, 2))
    m = u.sum(1) > 1
    u[m] = 1 - u[m]
    return f[fi], np.c_[1 - u.sum(1), u[:, 0], u[:, 1]]


def at(v, smp):
    f, b = smp
    return (v[f] * b[:, :, None]).sum(1)


def sphere_centre(P):
    sol = np.linalg.lstsq(np.c_[2 * P, np.ones(len(P))], (P ** 2).sum(1), rcond=None)[0]
    return sol[:3]


def distal_end(raw, v, k=25, proximal=False):
    o = np.argsort(-raw[:, 1] if proximal else raw[:, 1])[:k]
    return v[o].mean(0)


class Chain:
    """parameters P = [hum rotvec(3) about the head centre, hum translation(3), hum scale, radius swing(2), ulna swing(2)]; swings are rotation vectors in the plane normal to the
    forearm axis (no twist) about the wrist centre"""

    def __init__(self, side, by, raw):
        s = "_" + side
        self.side = side
        v = by["humerus" + s]["v"]
        self.hc = sphere_centre(v[v[:, 1] > v[:, 1].max() - 30.0])            # humeral head (top 30 mm of the bone)
        self.u = v[v[:, 1] >= np.percentile(v[:, 1], 70)].mean(0) - v[v[:, 1] <= np.percentile(v[:, 1], 30)].mean(0)
        self.u /= np.linalg.norm(self.u)
        self.cw = (distal_end(raw["radius" + s], by["radius" + s]["v"]) + distal_end(raw["ulna" + s], by["ulna" + s]["v"])) / 2
        ce = (distal_end(raw["radius" + s], by["radius" + s]["v"], proximal=True) + distal_end(raw["ulna" + s], by["ulna" + s]["v"], proximal=True)) / 2
        af = (ce - self.cw) / np.linalg.norm(ce - self.cw)
        ref = np.array([0, 1.0, 0]) if abs(af[1]) < 0.95 else np.array([0, 0, 1.0])
        self.e1 = np.cross(af, ref)
        self.e1 /= np.linalg.norm(self.e1)
        self.e2 = np.cross(af, self.e1)
        self.ce = ce
        self.P = np.r_[np.zeros(6), 1.0, np.zeros(4)]

    def hum(self, X, P=None):
        P = self.P if P is None else P
        R = Rot.from_rotvec(P[:3]).as_matrix()
        return ((X - self.hc) * P[6]) @ R.T + self.hc + P[3:6]

    def fore(self, X, q):
        R = Rot.from_rotvec(q[0] * self.e1 + q[1] * self.e2).as_matrix()
        return (X - self.cw) @ R.T + self.cw

    def rad(self, X, P=None):
        return self.fore(X, (self.P if P is None else P)[7:9])

    def uln(self, X, P=None):
        return self.fore(X, (self.P if P is None else P)[9:11])


def joint_pairs(raw, side, by, d_cut=8.0):
    """samples of the Z-source humerus that touch the radius / ulna (< d_cut mm), their partner sample on the forearm bones and the source gap"""
    s = "_" + side
    smp = {n: bary_samples(raw[n + s], by[n + s]["f"], 3000) for n in ("humerus", "radius", "ulna")}
    h0 = at(raw["humerus" + s], smp["humerus"])
    f0 = np.vstack([at(raw["radius" + s], smp["radius"]), at(raw["ulna" + s], smp["ulna"])])
    d0, j = cKDTree(f0).query(h0)
    sel = np.where(d0 < d_cut)[0]
    return smp, sel, j[sel], d0[sel]


def joint_stat(smp, sel, jj, d0, vh, vr, vu):
    h = at(vh, smp["humerus"])
    f = np.vstack([at(vr, smp["radius"]), at(vu, smp["ulna"])])
    pair = np.linalg.norm(h[sel] - f[jj], axis=1)
    gap = cKDTree(f).query(h[sel])[0]
    return {"contact_samples": int(len(sel)), "source_gap_mm_median": round(float(np.median(d0)), 2), "nearest_surface_gap_mm_median": round(float(np.median(gap)), 2),
            "nearest_surface_gap_mm_p90": round(float(np.percentile(gap, 90)), 2), "pair_distance_change_mm_mean": round(float(np.abs(pair - d0).mean()), 2)}


# ------------------------------------------------------------------------------------------------ chain fits
def fit_left(by, raw, evid=None, log=print):
    """left chain from her photograph evidence (see the module docstring); returns the Chain and a report"""
    z = np.load(EVID if evid is None else evid)
    E = z["elbow_pts_mm10"].astype(float) / 10.0
    shaft = z["shaft_y_x_z"].astype(float)
    ch = Chain("l", by, raw)
    tE = cKDTree(E)
    names = ("humerus_l", "radius_l", "ulna_l")
    smp = {n: bary_samples(raw[n], by[n]["f"], 3000) for n in names}
    ax_levels = np.arange(330, 601, 5)
    vh = by["humerus_l"]["v"]
    ax = np.array([vh[np.abs(vh[:, 1] - y) < 3].mean(0) for y in ax_levels if (np.abs(vh[:, 1] - y) < 3).sum() >= 3])
    jsmp, jsel, jj, jd0 = joint_pairs(raw, "l", by)

    def place(P):
        return {"humerus_l": ch.hum(by["humerus_l"]["v"], P), "radius_l": ch.rad(by["radius_l"]["v"], P), "ulna_l": ch.uln(by["ulna_l"]["v"], P)}

    def parts(P):
        pl = place(P)
        A = ch.hum(ax, P)
        o = np.argsort(A[:, 1])
        sh = []
        for y, x, zz in shaft:
            sh += [np.interp(y, A[o, 1], A[o, 0]) - x, np.interp(y, A[o, 1], A[o, 2]) - zz]
        S = np.vstack([at(pl[n], smp[n]) for n in names])
        w = (S[:, 1] >= 312) & (S[:, 1] <= 354)
        prec = np.where(w, np.minimum(tE.query(S)[0], CAP_MM), 0.0)
        rec = np.minimum(cKDTree(S).query(E)[0], CAP_MM)
        reg = np.r_[5.0 * max(np.linalg.norm(P[3:6]) - HEAD_SHIFT_MM, 0), 2.0 * (P[:3] @ ch.u) * 100, 60 * (P[6] - 1.0), SWING_DEG_W * np.degrees(P[7:11])]
        return np.array(sh), prec, rec, reg

    def resid(P):
        sh, prec, rec, reg = parts(P)
        return np.r_[sh, 0.12 * prec, 0.05 * rec, reg]

    P0 = ch.P.copy()
    # start: the shaft-only solution (head fixed to 4 mm), then the full objective
    def r_shaft(p6):
        P = np.r_[p6, 1.0, np.zeros(4)]
        sh, _, _, reg = parts(P)
        return np.r_[sh, reg[:2]]
    s0 = least_squares(r_shaft, np.zeros(6), x_scale=np.r_[0.05 * np.ones(3), 5 * np.ones(3)])
    P1 = np.r_[s0.x, 1.0, np.zeros(4)]
    s = least_squares(resid, P1, x_scale=np.r_[0.05 * np.ones(3), 5 * np.ones(3), 0.02, 0.05 * np.ones(4)])
    ch.P = s.x
    sh, prec, rec, reg = parts(ch.P)
    sh0, prec0, rec0, _ = parts(P0)
    pl0, pl1 = place(P0), place(ch.P)
    rep = {"frame": "photograph (her skin, left forearm and hand are in it); head centre = her CT humerus head",
           "params": {"humerus_rot_deg": round(float(np.degrees(np.linalg.norm(ch.P[:3]))), 2), "humerus_translation_mm": ch.P[3:6].round(2).tolist(), "humerus_scale": round(float(ch.P[6]), 4),
                      "head_shift_mm": round(float(np.linalg.norm(ch.P[3:6])), 2), "radius_swing_deg": np.degrees(ch.P[7:9]).round(2).tolist(), "ulna_swing_deg": np.degrees(ch.P[9:11]).round(2).tolist(),
                      "elbow_end_move_mm": {"radius": round(float(np.linalg.norm(ch.rad(ch.ce[None])[0] - ch.ce)), 1), "ulna": round(float(np.linalg.norm(ch.uln(ch.ce[None])[0] - ch.ce)), 1)}},
           "shaft_centre_residual_mm": {"before_mean": round(float(np.hypot(sh0[0::2], sh0[1::2]).mean()), 1), "after_mean": round(float(np.hypot(sh[0::2], sh[1::2]).mean()), 1),
                                        "after_max": round(float(np.hypot(sh[0::2], sh[1::2]).max()), 1)},
           "elbow_blob_evidence_mm": {"bone_to_evidence_mean_before": round(float(prec0[prec0 > 0].mean()), 2), "bone_to_evidence_mean_after": round(float(prec[prec > 0].mean()), 2),
                                      "evidence_covered_mean_before": round(float(rec0.mean()), 2), "evidence_covered_mean_after": round(float(rec.mean()), 2), "cap_mm": CAP_MM},
           "joint_before": joint_stat(jsmp, jsel, jj, jd0, by["humerus_l"]["v"], by["radius_l"]["v"], by["ulna_l"]["v"]),
           "joint_after": joint_stat(jsmp, jsel, jj, jd0, pl1["humerus_l"], pl1["radius_l"], pl1["ulna_l"])}
    log(f"  Q199 left chain: {rep['params']}")
    return ch, rep


def fit_right(by, raw, her, log=print):
    """right chain: her CT labels carry the whole chain, the humerus stays on its label; the radius / ulna swing (bounded) so the Z-source joint closes while they stay on their labels"""
    ch = Chain("r", by, raw)
    names = ("humerus_r", "radius_r", "ulna_r")
    smp = {n: bary_samples(raw[n], by[n]["f"], 3000) for n in names}
    lab, labtree, laby = {}, {}, {}
    for n in names:
        lab[n] = at(np.asarray(her[n]["v"], float), bary_samples(her[n]["v"], np.asarray(her[n]["f"]), 6000, seed=7))      # seeded: the fit is reproducible
        labtree[n] = cKDTree(lab[n])
        laby[n] = (lab[n][:, 1].min(), lab[n][:, 1].max())
    jsmp, jsel, jj, jd0 = joint_pairs(raw, "r", by)

    def parts(q):
        P = np.r_[np.zeros(6), 1.0, q]
        vr, vu = ch.rad(by["radius_r"]["v"], P), ch.uln(by["ulna_r"]["v"], P)
        h = at(by["humerus_r"]["v"], smp["humerus_r"])
        f = np.vstack([at(vr, smp["radius_r"]), at(vu, smp["ulna_r"])])
        pair = np.linalg.norm(h[jsel] - f[jj], axis=1) - jd0
        rec, prec = [], []
        for n, vv in (("radius_r", vr), ("ulna_r", vu)):
            Z = at(vv, smp[n])
            rec.append(np.minimum(cKDTree(Z).query(lab[n])[0], CAP_MM))
            m = (Z[:, 1] >= laby[n][0]) & (Z[:, 1] <= laby[n][1])
            prec.append(np.where(m, np.minimum(labtree[n].query(Z)[0], CAP_MM), 0.0))
        return pair, np.concatenate(rec), np.concatenate(prec)

    def resid(q):
        pair, rec, prec = parts(q)
        return np.r_[0.5 * pair, 0.1 * rec, 0.1 * prec, SWING_DEG_W * np.degrees(q)]
    s = least_squares(resid, np.zeros(4), x_scale=0.05 * np.ones(4))
    ch.P = np.r_[np.zeros(6), 1.0, s.x]
    p0, r0, c0 = parts(np.zeros(4))
    p1, r1, c1 = parts(s.x)
    nr = len(her["radius_r"]["v"]) and 6000
    rep = {"frame": "her CT labels (humerus on its label; forearm bones swing about the wrist)",
           "params": {"radius_swing_deg": np.degrees(s.x[:2]).round(2).tolist(), "ulna_swing_deg": np.degrees(s.x[2:]).round(2).tolist(),
                      "elbow_end_move_mm": {"radius": round(float(np.linalg.norm(ch.rad(ch.ce[None])[0] - ch.ce)), 1), "ulna": round(float(np.linalg.norm(ch.uln(ch.ce[None])[0] - ch.ce)), 1)}},
           "label_recall_mm_mean": {"radius_before": round(float(r0[:nr].mean()), 2), "radius_after": round(float(r1[:nr].mean()), 2), "ulna_before": round(float(r0[nr:].mean()), 2), "ulna_after": round(float(r1[nr:].mean()), 2)},
           "joint_before": joint_stat(jsmp, jsel, jj, jd0, by["humerus_r"]["v"], by["radius_r"]["v"], by["ulna_r"]["v"]),
           "joint_after": joint_stat(jsmp, jsel, jj, jd0, by["humerus_r"]["v"], ch.rad(by["radius_r"]["v"]), ch.uln(by["ulna_r"]["v"]))}
    log(f"  Q199 right chain: {rep['params']}")
    return ch, rep


# ------------------------------------------------------------------------------------------------ field
class Field:
    """D(x) = sum_b w_b(x) D_b(x) / sum_b w_b(x), over the moving bones (their displacement functions) and the fixed bones + a null anchor (D = 0)"""

    def __init__(self, side, by, raw, ch: Chain):
        s = "_" + side
        self.ch = ch
        moving = {"humerus" + s: lambda X: ch.hum(X) - X, "radius" + s: lambda X: ch.rad(X) - X, "ulna" + s: lambda X: ch.uln(X) - X}
        self.moving = moving
        self.trees = {}
        for n in moving:
            v, f = by[n]["v"], by[n]["f"]
            self.trees[n] = cKDTree(at(v, bary_samples(v, f, 6000, seed=3)))
        pts = []
        c = ch.hc
        for i, d in by.items():
            if d["cat"] != "bone" or i in moving:
                continue
            v = d["v"]
            if np.linalg.norm(v.mean(0) - c) < 450.0:
                pts.append(v)
        self.fixed = cKDTree(np.vstack(pts)) if pts else None

    def weights(self, X):
        W, D = [], []
        for n, fn in self.moving.items():
            d = self.trees[n].query(X)[0]
            W.append(1.0 / (d + W_SOFT_MM) ** W_POWER)
            D.append(fn(X))
        if self.fixed is not None:
            W.append(1.0 / (self.fixed.query(X)[0] + W_SOFT_MM) ** W_POWER)
            D.append(np.zeros_like(X))
        W.append(np.full(len(X), 1.0 / (W_NULL_MM + W_SOFT_MM) ** W_POWER))
        D.append(np.zeros_like(X))
        W = np.array(W)
        W /= W.sum(0)
        return W, np.array(D)

    def __call__(self, X):
        W, D = self.weights(X)
        return (W[:, :, None] * D).sum(0)


# ------------------------------------------------------------------------------------------------ per structure
GATE_MM = (0.8, 3.0)           # |D| below 0.8 mm: untouched, above 3 mm: full, smooth between (tissue far from the arm stays bit-identical)
SKIP_CATS = ("skin", "bone")
ARM_RADIUS_MM = 420.0
PUSH_CATS = ("muscle", "vessel", "nerve", "fascia", "lymphatic")
BONE_OK_CATS = ("ligament", "bursa", "cartilage", "tendon")      # attach to / lie on bone by design: no inside-bone cost
ATTACH_CATS = ("muscle", "tendon", "ligament", "bursa")
ATTACH_ZONE_MM, ATTACH_TOL_MM, ATTACH_CAP_MM = 8.0, 3.0, 10.0
PULL_SIGMA_MM = 25.0
CONT_CATS = ("muscle", "tendon", "ligament", "fascia", "vessel", "nerve", "bursa", "cartilage")
GAP_TOL_MM, GAP_TOL_VESSEL_MM, GAP_CAP_MM = 5.0, 3.0, 12.0
CLOSE_SIGMA_MM = 15.0
CLOSE_TARGET_MM, CLOSE_TARGET_MUSCLE_MM = 1.5, 3.0
PREFER_FIELD_MARGIN = 2.0
STEPS = {"attach", "close"}          # diagnostic switches (the build uses both)
ADJUST_CAP_MM = 10.0          # push-out / skin clamp / volume / attachment / closure adjustments may not move a vertex further than this from the field's own result (+ <= SEPARATE_MAX_MM on the shipped mesh = 15 mm)
SEPARATE_MAX_MM = 5.0
SEPARATE_FOLD_TOL = 0.01      # share of edges newly folded per mesh (Q194: 0.003 rejected 80 % of the moves at the crowded right elbow)
ELBOW_ZONE_MM = 100.0         # continuity is judged where the contact lies within this distance of the Z-source elbow joint
ARM_REGIONS = ("upper_limb", "forearm_hand")


def _sstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


def gated(D):
    n = np.linalg.norm(D, axis=1)
    return D * _sstep((n - GATE_MM[0]) / (GATE_MM[1] - GATE_MM[0]))[:, None]


def side_ids(by, side):
    s = "_" + side
    return [i for i, d in by.items() if (i.endswith(s) or (s + "_") in i) and d["cat"] not in SKIP_CATS]


def lowpass(D, f, sigma_mm=10.0, edge_mm=4.0):
    """diffusion of the displacement over the mesh graph (the shear the field puts into a structure that spans the elbow goes, its mean motion stays)"""
    from scipy import sparse
    from scipy.sparse.linalg import splu
    n = len(D)
    e = np.unique(np.sort(np.vstack([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]), axis=1), axis=0)
    A = sparse.coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(n, n))
    A = (A + A.T).tocsr()
    L = sparse.diags(np.asarray(A.sum(1)).ravel()) - A
    lam = max((sigma_mm / edge_mm) ** 2 / 2.0, 0.0)
    lu = splu((sparse.identity(n) + lam * L).tocsc())
    return np.column_stack([lu.solve(D[:, k]) for k in range(3)])


def _closed(f):
    from scripts.zanatomy import q190_refine as Q
    return Q._closed(f)


def _metrics(v, r, f, skin, zb):
    from scripts.zanatomy import q191_hand as H
    return H.struct_metrics(v, r, f, H.Ctx(skin, None, (), zb), None)


def _vol_out(vr):
    return 0.0 if vr is None else max(0.65 - vr, vr - 1.5, 0.0)


ATTACH_W = 1.5


LABEL_W, LABEL_TOL_MM = 2.0, 1.5
HER_ALIAS_R = {"zan_extensor_pollicis_longus_r": "extensor_pollicis_longus_r"}


def cost(m, m0, cat, att_excess=0.0, lab_excess=0.0):
    c = 2.0 * m.get("outside_her_skin_pct", 0) + 1.0 * (m.get("stretch_area_outside_0.67_1.5_pct", 0) or 0) + 6.0 * m.get("folded_edges_pct", 0)
    if cat not in BONE_OK_CATS:
        c += 2.0 * m.get("inside_z_bone_pct", 0)
    if cat == "muscle":
        c += 60.0 * max(0.0, _vol_out(m.get("volume_ratio_vs_source")) - _vol_out(m0.get("volume_ratio_vs_source")))
    return c + ATTACH_W * att_excess + LABEL_W * lab_excess


def at_nearest(Dfull, vfull, P, k=3):
    """displacement of the full-resolution mesh interpolated (inverse distance, k nearest vertices) to the points P (the shipped, pre-decimated mesh)"""
    d, j = cKDTree(vfull).query(P, k=k)
    w = 1.0 / (d + 0.5)
    w /= w.sum(1, keepdims=True)
    return (Dfull[j] * w[:, :, None]).sum(1)


def vol_clamp(v, r, f, lo, hi):
    from scripts.zanatomy import q190_refine as Q
    vs = abs(Q.volume(r, f)) * Q.BODY_SCALE ** 3
    if vs < 1e-6:
        return v
    ratio = abs(Q.volume(v, f)) / vs
    lim = min(max(ratio, lo), hi)
    if lim == ratio:
        return v
    c = v.mean(0)
    return c + (v - c) * (lim / ratio) ** (1 / 3)


def cap_to(v1, ref, cap=ADJUST_CAP_MM):
    """no vertex further than `cap` from `ref` (the field's own result)"""
    d = v1 - ref
    n = np.linalg.norm(d, axis=1)
    k = np.minimum(1.0, cap / np.maximum(n, 1e-9))
    return ref + d * k[:, None]


def make_candidate(v0, f, r, cat, i, Dc, skin, skin_tree, zb, vr0=None):
    from scripts.zanatomy import q190_refine as Q
    from scripts.zanatomy import q191_hand as H
    ref = v0 + Dc
    v1 = ref.copy()
    ones = np.ones(len(v1), bool)
    if cat in PUSH_CATS:
        v1 = H.push_out_of_bones(v1, f, zb, ones, tol=1.5, max_move=7.0)
    if cat not in ("ligament", "bursa", "cartilage"):
        v1 = H.clamp_inside_skin(v1, f, ones, skin, skin_tree)
    v1 = cap_to(v1, ref)
    if _closed(f) and not H.NOT_BODY.search(i):
        if cat == "muscle":
            v1, _ = Q.volume_guard(v1, r, f)
        elif vr0 is not None:
            v1 = vol_clamp(v1, r, f, vr0 * 0.9, vr0 * 1.1)
    return v1


class Labels:
    """her own-model labels (CT frame, the RIGHT arm: her real measurement) of the right muscles that have one: median distance label -> Z surface (the coverage of her label).  A move that
    takes a labelled muscle more than LABEL_TOL_MM further from its label costs; the Z-source attachment footprint is not allowed to override her label"""

    def __init__(self, by, raw, her, ids):
        self.items = {}
        for i in ids:
            hid = HER_ALIAS_R.get(i, i)
            if by[i]["cat"] != "muscle" or hid not in her or her[hid]["cat"] != "muscle" or not _closed(by[i]["f"]):
                continue
            lab = at(np.asarray(her[hid]["v"], float), bary_samples(her[hid]["v"], np.asarray(her[hid]["f"]), 3000, seed=11))
            self.items[i] = (cKDTree(lab), lab, bary_samples(raw[i], by[i]["f"], 2500, seed=12))

    def gate(self, i, v):
        """0 on her label (< 3 mm), 1 beyond 9 mm from it"""
        return _sstep((self.items[i][0].query(v)[0] - 3.0) / 6.0)

    def med(self, i, v):
        t, lab, smp = self.items[i]
        return float(np.median(cKDTree(at(v, smp)).query(lab)[0]))

    def excess(self, i, v, base):
        return 0.0 if i not in self.items else max(0.0, self.med(i, v) - base - LABEL_TOL_MM)


class Attach:
    """origin / insertion footprints from the Z source: the vertices of a structure within ATTACH_ZONE_MM of the humerus / radius / ulna (x body scale) and their source distance"""

    def __init__(self, side, by, raw):
        from scripts.zanatomy import q190_metrics as Mx
        s = "_" + side
        self.bones = [n + s for n in ("humerus", "radius", "ulna", "scapula", "clavicle") if n + s in by]
        self.scale = Mx.BODY_SCALE
        self.smp = {b: bary_samples(raw[b], by[b]["f"], 6000, seed=5) for b in self.bones}
        src = {b: cKDTree(at(raw[b], self.smp[b])) for b in self.bones}
        self.zone = {}
        for i, d in by.items():
            if d["cat"] not in ATTACH_CATS or not (i.endswith(s) or s + "_" in i):
                continue
            z = {}
            for b in self.bones:
                d0 = src[b].query(raw[i])[0] * self.scale
                idx = np.where(d0 < ATTACH_ZONE_MM)[0]
                if len(idx) >= 6:
                    z[b] = (idx, d0[idx])
            if z:
                self.zone[i] = z

    def trees(self, by):
        return {b: cKDTree(at(by[b]["v"], self.smp[b])) for b in self.bones}

    def stat(self, i, v, trees):
        out = {}
        for b, (idx, d0) in self.zone.get(i, {}).items():
            d1 = trees[b].query(v[idx])[0]
            out[b] = {"source_mm": round(float(np.median(d0)), 1), "now_mm": round(float(np.median(d1)), 1), "vertices": int(len(idx))}
        return out

    def excess(self, i, v, trees):
        """sum over the footprint bones of how much the median footprint distance exceeds the Z-source one (+ATTACH_TOL_MM), mm"""
        tot = 0.0
        for b, (idx, d0) in self.zone.get(i, {}).items():
            tot += max(0.0, float(np.median(trees[b].query(v[idx])[0])) - float(np.median(d0)) - ATTACH_TOL_MM)
        return tot

    def pull(self, i, v, f, trees, cap=ATTACH_CAP_MM, sigma=PULL_SIGMA_MM, gate=None):
        """footprint vertices that sit further from their bone than in the Z source (+ATTACH_TOL_MM): the structure end moves by the MEAN pull vector of those vertices (<= cap), the motion
        fading with the distance from them (Gaussian, sigma mm), so the structure keeps its shape instead of being sheared vertex by vertex"""
        D = np.zeros_like(v)
        n_pull = 0
        for b, (idx, d0) in self.zone.get(i, {}).items():
            dist, j = trees[b].query(v[idx])
            P = trees[b].data[j]
            too = dist > d0 + ATTACH_TOL_MM
            if too.sum() < 3:
                continue
            k = idx[too]
            vec = (P[too] - v[k]) / np.maximum(dist[too], 1e-6)[:, None] * (dist[too] - d0[too])[:, None]
            T = vec.mean(0)
            n = np.linalg.norm(T)
            if n < 1.0:
                continue
            T *= min(1.0, cap / n)
            dz = cKDTree(v[k]).query(v)[0]
            Db = T[None, :] * np.exp(-((dz / sigma) ** 2))[:, None]
            D = np.where(np.linalg.norm(Db, axis=1)[:, None] > np.linalg.norm(D, axis=1)[:, None], Db, D)
            n_pull += int(too.sum())
        if not n_pull:
            return v, 0
        if gate is not None:                      # the part of the structure that lies on her own label stays: only the end beyond the label (the extrapolated part) is brought to the bone
            D = D * gate[:, None]
        return v + D, n_pull


def in_scope(side, i, raw_i, region, jc, hum_tree=None, humerus_moved=True):
    """the Q199 scope (also what the post-build trim keeps): ARM structures (Q168 region upper_limb / forearm_hand) -- on the right side only where they reach the elbow zone (the right
    humerus does not move: its shoulder is not touched); trunk-region muscles that insert on the humerus (LEFT only, the humerus moved: shoulder blend zone); merged Z meshes (non-trunk,
    non-head) that hold an arm part in the elbow zone (the field is zero on their other parts)"""
    arm = region in ARM_REGIONS
    n_near = int((np.linalg.norm(raw_i - jc, axis=1) < ELBOW_ZONE_MM + 40.0).sum())
    merged = region not in ("trunk", "head_neck") and n_near >= 100
    if side == "r":
        return (arm and n_near > 0) or merged
    if arm or merged:
        return True
    return bool(humerus_moved and hum_tree is not None and int((hum_tree.query(raw_i)[0] < ATTACH_ZONE_MM).sum()) >= 6)


def refine_side(side, by, raw, ch: Chain, skin, skin_tree, regions=None, log=print, only=None, her=None, label_sides=("r",), scope=None, extra_centres=(), allow_unchanged=False, note_fn=None, field_fn=None):
    """new bones, field-carried soft tissue with the guard ladder, attachments, continuity; mutates by[i]["v"] (and ["pre_decimated"]), returns the per-structure report"""
    from scripts.zanatomy import q191_hand as H
    s = "_" + side
    F = Field(side, by, raw, ch)
    old = {n: by[n]["v"].copy() for n in ("humerus" + s, "radius" + s, "ulna" + s)}
    att = Attach(side, by, raw)
    jsmp, jsel, _, _ = joint_pairs(raw, side, by)
    jc = at(raw["humerus" + s], jsmp["humerus"])[jsel].mean(0)          # the Z-source elbow joint (raw frame): where continuity is judged
    att_before_trees = att.trees(by)
    for n, fn in (("humerus", ch.hum), ("radius", ch.rad), ("ulna", ch.uln)):
        by[n + s]["v"] = fn(old[n + s])
    att_trees = att.trees(by)
    zb = [H.Inside(by[n + s]["v"], by[n + s]["f"]) for n in ("humerus", "radius", "ulna")]
    rep = {"bones": {n + s: {"max_move_mm": round(float(np.linalg.norm(by[n + s]["v"] - old[n + s], axis=1).max()), 1),
                              "mean_move_mm": round(float(np.linalg.norm(by[n + s]["v"] - old[n + s], axis=1).mean()), 1)} for n in ("humerus", "radius", "ulna")},
           "structures": {}}
    hum_tree = cKDTree(at(raw["humerus" + s], bary_samples(raw["humerus" + s], by["humerus" + s]["f"], 6000, seed=5)))
    ids = [i for i in side_ids(by, side) if np.linalg.norm(by[i]["v"].mean(0) - ch.hc) < ARM_RADIUS_MM and (only is None or i in only)
           and (regions is None or (scope or in_scope)(side, i, raw[i], regions.get(i), jc, hum_tree, humerus_moved=bool(np.abs(ch.P[:6]).max() > 1e-9)))]
    # = see in_scope: arm structures, the shoulder muscles that insert on a MOVED humerus, merged Z meshes that hold an arm part (the field is zero on their other parts)
    v_before = {i: by[i]["v"].copy() for i in ids}
    lab = Labels(by, raw, her, ids) if (her is not None and side in label_sides) else None
    lab_base = {i: lab.med(i, v_before[i]) for i in lab.items} if lab else {}
    lex = (lambda i, v: lab.excess(i, v, lab_base[i]) if lab and i in lab_base else 0.0)
    v_field = {i: by[i]["v"].copy() for i in ids}            # after the field step: the attachment and closure steps stay within ADJUST_CAP_MM of it
    ctx = {}

    def record(i, name, v1, m0, m1, a0, a1, n_pull):
        d = by[i]
        d["v"] = v1
        mv = np.linalg.norm(v1 - v_before[i], axis=1)
        ctx[i] = {"name": name, "m0": m0, "m1": m1, "att0": a0, "att1": a1, "pulled": n_pull}
        rep["structures"][i] = {"cat": d["cat"], "ladder": name, "mean_move_mm": round(float(mv.mean()), 2), "max_move_mm": round(float(mv.max()), 2), "before": m0, "after": m1,
                                "attachment_before": a0, "attachment_after": a1, "attachment_pull_vertices": n_pull}

    for i in ids:
        d = by[i]
        v0, f, r, cat = v_before[i].astype(float), d["f"], raw[i].astype(float), d["cat"]
        D = gated(field_fn(i, v0) if field_fn is not None else F(v0))
        dmax = float(np.linalg.norm(D, axis=1).max())
        has_zone = "attach" in STEPS and cat in ATTACH_CATS and i in att.zone
        if dmax < 0.05 and not (has_zone and att.excess(i, v0, att_trees) > 0):
            continue
        m0 = _metrics(v0, r, f, skin, zb)
        name, v1, m1 = "not moved by the field", v0, m0
        if dmax >= 0.05:
            cands = [("field", D)]
            if len(v0) > 30:
                cands.append(("field, low-passed 10 mm", lowpass(D, f, 10.0)))
                cands.append(("field, low-passed 25 mm", lowpass(D, f, 25.0)))
            cands.append(("mean translation of the field", np.tile(D.mean(0), (len(v0), 1))))
            if allow_unchanged:
                cands.append(("kept where it was (the field would take it off its own measured mesh / the bones it was fitted to)", np.zeros_like(D)))
            res = []
            for nm, Dc in cands:
                vv = make_candidate(v0, f, r, cat, i, Dc, skin, skin_tree, zb, m0.get("volume_ratio_vs_source"))
                mm = _metrics(vv, r, f, skin, zb)
                c1 = cost(mm, m0, cat, att.excess(i, vv, att_trees), lex(i, vv))
                res.append((c1, nm, vv, mm))
                if nm == "field" and c1 <= cost(m0, m0, cat, att.excess(i, v0, att_before_trees)) + 1.0:
                    break                                   # the field is not worse than before: no need to try the others
            best = min(res, key=lambda t: t[0])
            pick = res[0] if res[0][0] <= best[0] + PREFER_FIELD_MARGIN else best
            _, name, v1, m1 = pick
        a_before = att.stat(i, v0, att_before_trees)
        v_field[i] = v1.copy()
        n_pull = 0
        if has_zone:
            v2, n_pull = att.pull(i, v1, f, att_trees, gate=(lab.gate(i, v1) if lab and i in lab.items else None))
            if n_pull:
                v2 = make_candidate(v1, f, r, cat, i, v2 - v1, skin, skin_tree, zb, m0.get("volume_ratio_vs_source"))
                m2 = _metrics(v2, r, f, skin, zb)
                v2 = cap_to(v2, v_field[i])
                if cost(m2, m0, cat, att.excess(i, v2, att_trees), lex(i, v2)) <= cost(m1, m0, cat, att.excess(i, v1, att_trees), lex(i, v1)) + 3.0:
                    v1, m1 = v2, m2
                else:
                    n_pull = 0
        if np.array_equal(v1, v0):
            continue
        record(i, name, v1, m0, m1, a_before, att.stat(i, v1, att_trees), n_pull)
    before_closure = {i: by[i]["v"].copy() for i in ids}
    centres = np.vstack([jc[None]] + [np.asarray(c, float)[None] for c in extra_centres])
    rep["continuity"] = close_gaps(side, by, raw, set(ids), skin, skin_tree, zb, centres, v_field, log=log, rounds=6 if "close" in STEPS else 0, veto=(lambda k, vk: lex(k, vk) > 0.5) if lab else None)
    for i in ids:                                    # structures the gap closure moved that the field / attachment step had left alone
        if i not in rep["structures"] and not np.array_equal(by[i]["v"], before_closure[i]):
            r = raw[i].astype(float)
            m0 = _metrics(before_closure[i], r, by[i]["f"], skin, zb)
            record(i, "gap closure only", by[i]["v"], m0, _metrics(by[i]["v"], r, by[i]["f"], skin, zb), att.stat(i, v_before[i], att_before_trees), att.stat(i, by[i]["v"], att_trees), 0)
    for i, c in rep["structures"].items():
        d = by[i]
        q = ctx[i]
        mv = np.linalg.norm(d["v"] - v_before[i], axis=1)
        c["mean_move_mm"], c["max_move_mm"] = round(float(mv.mean()), 2), round(float(mv.max()), 2)
        if not np.array_equal(d["v"], before_closure[i]) and q["name"] != "gap closure only":
            q["m1"] = _metrics(d["v"], raw[i].astype(float), d["f"], skin, zb)
            q["att1"] = att.stat(i, d["v"], att_trees)
            c["after"], c["attachment_after"] = q["m1"], q["att1"]
        d["fit_note"] = (d.get("fit_note") or "") + (note_fn or _note)(side, i, d["cat"], q, q["m1"], mv, rep["continuity"]["per_structure"].get(i))
    # the shipped (pre-decimated) meshes of the Q194 neighbour separation follow with the displacement of their full-resolution mesh
    n_pre = 0
    for i in rep["structures"]:
        pre = by[i].get("pre_decimated")
        if pre is not None:
            pv, pf = pre
            by[i]["pre_decimated"] = (np.asarray(pv, float) + at_nearest(by[i]["v"] - v_before[i], v_before[i], np.asarray(pv, float)), pf)
            n_pre += 1
    rep["shipped_meshes_carried"] = n_pre
    return rep


def _fmt_m(m):
    keys = (("outside_her_skin_pct", "outside her skin %"), ("inside_z_bone_pct", "inside the displayed bones %"), ("stretch_area_outside_0.67_1.5_pct", "stretched triangles %"),
            ("folded_edges_pct", "folded edges %"), ("volume_ratio_vs_source", "volume vs source"))
    return ", ".join(f"{lb} {m[k]}" for k, lb in keys if m.get(k) is not None)


def _note(side, i, cat, q, m1, mv, cont):
    how = {"not moved by the field": "its origin / insertion footprint brought back to the bone", "gap closure only": "closed up against the structures it touches in the Z source"}.get(q["name"])
    txt = (f" Q199: {'adjusted' if how else 'moved'} at the {'left' if side == 'l' else 'right'} elbow ("
           + (how if how else f"humerus - radius - ulna fitted as one kinematic chain, tissue carried by the bone-anchored field: {q['name']}")
           + f"; mean {mv.mean():.1f} mm, max {mv.max():.1f} mm). Before -> after: " + _fmt_m(q["m0"]) + " -> " + _fmt_m(m1) + ".")
    a0, a1 = q["att0"], q["att1"]
    if a0 and a1:
        txt += " Origin / insertion footprint to the bone (source / before / after, mm): " + "; ".join(f"{b.rsplit('_', 1)[0]} {a1[b]['source_mm']} / {a0[b]['now_mm']} / {a1[b]['now_mm']}" for b in a1 if b in a0) + "."
    if cont:
        txt += f" Gap to {cont['neighbours']} neighbour structure(s) it touches in the Z source: {cont['before_mm']} -> {cont['after_mm']} mm."
    return txt


def contact_pairs(side, by, raw, ids, movable, centre, touch_mm=3.0):
    """pairs of arm structures that touch in the Z source (vertex sets < touch_mm apart, x body scale), at least one of them moved: (a, b, d0)"""
    from scripts.zanatomy import q190_metrics as Mx
    sub = {i: raw[i][::max(1, len(raw[i]) // 1200)].astype(float) for i in ids if by[i]["cat"] in CONT_CATS and len(raw[i]) > 3}
    tr = {i: cKDTree(p) for i, p in sub.items()}
    keys = list(sub)
    cen = {i: sub[i].mean(0) for i in keys}
    ext = {i: float(np.linalg.norm(sub[i] - cen[i], axis=1).max()) for i in keys}
    out = []
    for x in range(len(keys)):
        for y in range(x + 1, len(keys)):
            a, b = keys[x], keys[y]
            if a not in movable and b not in movable:
                continue
            if np.linalg.norm(cen[a] - cen[b]) > ext[a] + ext[b] + touch_mm + 5:
                continue
            dd, jj = tr[b].query(sub[a])
            k = int(np.argmin(dd))
            d0 = float(dd[k]) * Mx.BODY_SCALE
            if d0 <= touch_mm and np.linalg.norm(sub[a][k] - np.atleast_2d(centre), axis=1).min() < ELBOW_ZONE_MM:
                out.append((a, b, d0))
    return out


def _gap(by, a, b):
    from scripts.zanatomy import q191_hand as H
    pa, pb = H.surf_pts(by[a]["v"], by[a]["f"], 1500, 1), H.surf_pts(by[b]["v"], by[b]["f"], 1500, 2)
    return float(cKDTree(pb).query(pa)[0].min())


def close_gaps(side, by, raw, movable, skin, skin_tree, zb, centre, v_field, log=print, rounds=6, veto=None):
    """pairs that touch in the Z source and are further apart now (> GAP_TOL_MM; vessel / nerve pairs GAP_TOL_VESSEL_MM): both structures (only the moved one if the other did not
    move) go half way to each other over the footprint that touches in the source (<= GAP_CAP_MM each, spread over the mesh, volume / fold guarded)"""
    from scripts.zanatomy import q190_refine as Q
    from scripts.zanatomy import q191_hand as H
    from scripts.zanatomy import q190_metrics as Mx
    allids = [i for i in side_ids(by, side) if i in movable or np.linalg.norm(by[i]["v"].mean(0) - by["humerus_" + side]["v"].mean(0)) < 330.0]
    movable = set(movable)
    pairs = contact_pairs(side, by, raw, allids, movable, centre)
    g_field = {(a, b): _gap(by, a, b) for a, b, _ in pairs}
    tolof = lambda a, b: GAP_TOL_VESSEL_MM if (by[a]["cat"] in ("vessel", "nerve") and by[b]["cat"] in ("vessel", "nerve")) else GAP_TOL_MM
    v_start = {i: by[i]["v"].copy() for i in allids}
    for rnd in range(rounds):
        for a, b, d0 in sorted(pairs, key=lambda t: -g_field[(t[0], t[1])]):
            if _gap(by, a, b) <= max(tolof(a, b), d0 + 2.0):
                continue
            ra, rb = raw[a].astype(float), raw[b].astype(float)
            va, vb = by[a]["v"], by[b]["v"]
            fa = np.where(cKDTree(rb).query(ra)[0] * Mx.BODY_SCALE < ATTACH_ZONE_MM)[0]
            fb = np.where(cKDTree(ra).query(rb)[0] * Mx.BODY_SCALE < ATTACH_ZONE_MM)[0]
            if len(fa) < 3 or len(fb) < 3:
                continue
            da, ja = cKDTree(vb).query(va[fa])
            db_, jb = cKDTree(va).query(vb[fb])
            share_a, share_b = (0.5, 0.5) if (a in movable and b in movable) else ((1.0, 0.0) if a in movable else (0.0, 1.0))
            d0 = max(d0, CLOSE_TARGET_MUSCLE_MM if (by[a]["cat"] == "muscle" and by[b]["cat"] == "muscle") else CLOSE_TARGET_MM)      # vertex-vertex distance: the surfaces then stay apart
            new = {}
            for k, fk, dk, tgt, share, vk0 in ((a, fa, da, vb[ja], share_a, va), (b, fb, db_, va[jb], share_b, vb)):
                if share == 0.0:
                    continue
                step = np.clip(share * (dk - d0), 0, GAP_CAP_MM)
                vec = (tgt - vk0[fk]) / np.maximum(dk, 1e-6)[:, None] * step[:, None]
                near = step > 0.5
                if near.sum() < 3:
                    continue
                T = vec[near].mean(0)
                dz = cKDTree(vk0[fk][near]).query(vk0)[0]
                vk = vk0 + T[None, :] * np.exp(-((dz / CLOSE_SIGMA_MM) ** 2))[:, None]
                if by[k]["cat"] in PUSH_CATS:
                    vk = H.push_out_of_bones(vk, by[k]["f"], zb, np.ones(len(vk), bool), tol=1.5, max_move=7.0)
                rk = raw[k].astype(float)
                if by[k]["cat"] == "muscle" and _closed(by[k]["f"]) and not H.NOT_BODY.search(k):
                    vk, _ = Q.volume_guard(vk, rk, by[k]["f"])
                f0, f1 = H.fold_stats(vk0, rk, by[k]["f"]), H.fold_stats(vk, rk, by[k]["f"])
                vk = cap_to(vk, v_field[k]) if k in v_field else vk
                f1 = H.fold_stats(vk, rk, by[k]["f"])
                if f1 > max(f0 + 0.01, 0.02) or (veto is not None and veto(k, vk)):
                    new = None
                    break
                new[k] = vk
            if new:
                for k, vk in new.items():
                    by[k]["v"] = vk
    rows, per = [], {}
    for a, b, d0 in pairs:
        gn = _gap(by, a, b)
        t = tolof(a, b)
        rows.append({"a": a, "b": b, "source_mm": round(d0, 2), "after_field_mm": round(g_field[(a, b)], 2), "after_closure_mm": round(gn, 2), "tol_mm": t})
        for k in (a, b):
            c = per.setdefault(k, {"neighbours": 0, "before_mm": 0.0, "after_mm": 0.0})
            c["neighbours"] += 1
            c["before_mm"] = max(c["before_mm"], round(g_field[(a, b)], 1))
            c["after_mm"] = max(c["after_mm"], round(gn, 1))
    changed = {k for k in allids if not np.array_equal(by[k]["v"], v_start[k])}
    summ = {"pairs": len(rows), "gap_gt_tol_after_field": int(sum(r["after_field_mm"] > max(r["tol_mm"], r["source_mm"] + 2) for r in rows)),
            "gap_gt_tol_after_closure": int(sum(r["after_closure_mm"] > max(r["tol_mm"], r["source_mm"] + 2) for r in rows)), "structures_moved_by_closure": len(changed)}
    log(f"  Q199 continuity {side}: {summ}")
    return {"summary": summ, "rows": rows, "per_structure": {k: v for k, v in per.items() if k in movable}, "closure_moved": sorted(changed)}


# ------------------------------------------------------------------------------------------------ skin seams
SKIN_ELBOW_RE = re.compile(r"skin_(anterior|posterior)_region_of_(arm|elbow|forearm)|skin_cubital_fossa|skin_(medial|lateral)_(border_of_forearm|bicipital_groove)")


def skin_seam_rows(by, raw, side, ids):
    """adjacent skin patches (their borders share Z-source vertices, < 1.5 mm): the step between the shared border vertices now"""
    rows = []
    for x in range(len(ids)):
        for y in range(x + 1, len(ids)):
            i, j = ids[x], ids[y]
            d, k = cKDTree(raw[j]).query(raw[i])
            sel = d < 1.5
            if sel.sum() < 3:
                continue
            step = np.linalg.norm(by[i]["v"][sel] - by[j]["v"][k[sel]], axis=1)
            rows.append({"a": i, "b": j, "border_vertices": int(sel.sum()), "step_mm_p95": round(float(np.percentile(step, 95)), 2), "step_mm_max": round(float(step.max()), 2)})
    return rows


def weld_borders(by, raw, patches, movable, rounds=4, passes=24, cap=8.0):
    """borders of adjacent skin patches (vertices < 1.5 mm apart in the Z source, nearest partner): the two border vertices go to their common mean when both patches may move, a
    movable patch goes all the way to a fixed neighbour; the correction is spread over the movable patch (no pleat)"""
    from scripts.zanatomy import q190_refine as Q
    pairs = []
    for x in range(len(patches)):
        for y in range(x + 1, len(patches)):
            a, b = patches[x], patches[y]
            if a not in movable and b not in movable:
                continue
            d, k = cKDTree(raw[b]).query(raw[a])
            sel = np.where(d < 1.5)[0]
            if len(sel) >= 3:
                pairs.append((a, b, sel, k[sel]))
    moved = {}
    for _ in range(rounds):
        corr = {i: np.zeros_like(by[i]["v"]) for i in movable}
        cnt = {i: np.zeros(len(by[i]["v"])) for i in movable}
        for a, b, ia, ib in pairs:
            vec = by[b]["v"][ib] - by[a]["v"][ia]
            sa, sb = (0.5, 0.5) if (a in movable and b in movable) else ((1.0, 0.0) if a in movable else (0.0, 1.0))
            if sa:
                corr[a][ia] += sa * vec
                cnt[a][ia] += 1
            if sb:
                corr[b][ib] -= sb * vec
                cnt[b][ib] += 1
        for i in movable:
            m = cnt[i] > 0
            if not m.any():
                continue
            c = np.zeros_like(corr[i])
            c[m] = corr[i][m] / cnt[i][m][:, None]
            n = np.linalg.norm(c, axis=1)
            c *= np.minimum(1.0, cap / np.maximum(n, 1e-9))[:, None]
            c2 = Q._smooth_push(by[i]["f"], c, passes)
            c2 = np.where((n > 1e-6)[:, None], c, c2)
            by[i]["v"] = by[i]["v"] + c2
            moved[i] = moved.get(i, 0.0) + float(np.linalg.norm(c2, axis=1).max())
    return moved


def weld_elbow_skin(side, by, raw, log=print):
    """the skin patches of the arm / elbow / forearm tile ONE surface but were fitted to her skin one by one (Q186 / Q190 / Q194): the border vertices are welded (weld_borders), the
    patches around the set (wrist, thorax) stay where they are; seam steps > 3 mm are the defect"""
    s = "_" + side
    ids = [i for i, d in by.items() if d["cat"] == "skin" and i.endswith(s) and SKIN_ELBOW_RE.search(i)]
    around = [i for i, d in by.items() if d["cat"] == "skin" and i.endswith(s)]
    elbow_set = set(ids)
    before = skin_seam_rows(by, raw, side, around)
    v0 = {i: by[i]["v"].copy() for i in ids}
    moved = weld_borders(by, raw, around, elbow_set)
    after = skin_seam_rows(by, raw, side, around)
    pick = lambda rows: [r for r in rows if r["a"] in elbow_set or r["b"] in elbow_set]
    rep = {}
    for i in ids:
        mv = np.linalg.norm(by[i]["v"] - v0[i], axis=1)
        if mv.max() < 0.05:
            continue
        sb = max([r["step_mm_max"] for r in before if i in (r["a"], r["b"])] or [0])
        sa = max([r["step_mm_max"] for r in after if i in (r["a"], r["b"])] or [0])
        rep[i] = {"max_correction_mm": round(float(mv.max()), 2), "mean_correction_mm": round(float(mv.mean()), 2), "seam_step_max_before_mm": sb, "seam_step_max_after_mm": sa}
        by[i]["fit_note"] = (by[i].get("fit_note") or "") + (
            f" Q199: skin patch welded to its neighbours across the arm / elbow / forearm seams (largest seam step {sb} -> {sa} mm; mean move {mv.mean():.1f} mm, max {mv.max():.1f} mm).")
    summ = lambda rows: {"seams": len(rows), "steps_gt_3mm": int(sum(r["step_mm_max"] > 3 for r in rows)), "max_step_mm": round(max([r["step_mm_max"] for r in rows] or [0]), 2)}
    out = {"patches": ids, "moved": rep, "before": summ(pick(before)), "after": summ(pick(after)), "seams_before": pick(before), "seams_after": pick(after)}
    log(f"  Q199 skin seams {side}: {out['before']} -> {out['after']}")
    return out


# ------------------------------------------------------------------------------------------------ neighbour-muscle separation on the shipped meshes
def separate_elbow(side, by, raw, skin, skin_tree, decimate_fn, log=print, radius=140.0):
    """the field / attachment / closure steps pack muscles against each other (neighbour overlap rose 14.6 -> 19.8 % left, 16.5 -> 22.7 % right at full resolution): the Q194 bounded per-vertex
    separation along the contact normal (q194_separate.separate: <= 4 mm per round, 6 mm in all, volume 0.65-1.5x, no new folds, containment) on the SHIPPED (decimated) meshes of the closed
    muscles of the elbow zone; a mesh that cannot move without breaking a guard stays"""
    from scripts.zanatomy import q190_metrics as Mx
    from scripts.zanatomy import q190_refine as Q
    from scripts.zanatomy import q194_hand_trunk as HT
    from scripts.zanatomy import q194_separate as Sp
    s = "_" + side
    jsmp, jsel, _, _ = joint_pairs(raw, side, by)
    jc = at(raw["humerus" + s], jsmp["humerus"])[jsel].mean(0)
    ids = [i for i in side_ids(by, side) if by[i]["cat"] == "muscle" and _closed(by[i]["f"]) and not Q.NOT_A_MUSCLE_BODY.search(i)
           and np.any(np.linalg.norm(raw[i] - jc, axis=1) < radius)]
    meshes = {i: by[i].get("pre_decimated") or decimate_fn(by[i]["v"].astype(float), by[i]["f"], i, "muscle") for i in ids}
    meshes = {i: (np.asarray(v, float), f) for i, (v, f) in meshes.items()}
    vol_ref = {i: abs(Q.volume(raw[i].astype(float), by[i]["f"])) * Mx.BODY_SCALE ** 3 for i in ids}
    G = HT.Gates(by, skin, skin_tree)
    Sp.MAX_TOTAL_MM = SEPARATE_MAX_MM
    Sp.FOLD_TOL = SEPARATE_FOLD_TOL
    ov0 = Sp.overlap_pct(meshes)
    movable = {i for i in ids if ov0[i] > 0.3}
    base = {i: meshes[i][0] for i in movable}
    out, mrep = Sp.separate(meshes, vol_ref, movable, keep=lambda i, v2: G.accept(i, base[i], v2), log=log)
    ov1 = Sp.overlap_pct({i: (out[i], meshes[i][1]) for i in ids})
    rep = {"muscles": len(ids), "with_overlap_gt_0.3pct_before": len(movable), "mean_overlap_pct_before": round(float(np.mean([ov0[i] for i in ids])), 2),
           "mean_overlap_pct_after": round(float(np.mean([ov1[i] for i in ids])), 2), "moved": mrep, "overlap_pct": {i: [round(ov0[i], 1), round(ov1[i], 1)] for i in ids}}
    for i, m in mrep.items():
        if m["max_move_mm"] < 0.3:
            continue
        by[i]["pre_decimated"] = (out[i], meshes[i][1])
        vr = abs(Q.volume(out[i], meshes[i][1])) / vol_ref[i]
        by[i]["fit_note"] = (by[i].get("fit_note") or "") + (
            f" Q199: overlap with neighbouring muscles reduced by the Q194 bounded per-vertex separation on the shipped mesh (vertices inside a neighbour {ov0[i]:.1f} -> {ov1[i]:.1f} %, "
            f"mean move {m['mean_move_mm']} mm, max {m['max_move_mm']}, volume {vr:.2f}x the Z source).")
    log(f"  Q199 separation {side}: {len(ids)} muscles, overlap {rep['mean_overlap_pct_before']} -> {rep['mean_overlap_pct_after']} % (shipped meshes)")
    return rep
