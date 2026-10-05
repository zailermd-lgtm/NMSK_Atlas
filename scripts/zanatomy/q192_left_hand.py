"""Q192: the LEFT hand / wrist of the female Z-Anatomy viewer, placed on her OWN left-hand bones as seen in her full-resolution cryosection photographs.

Her CT has no left hand (the 480 mm field of view clips the arms; Q191 held the left hand).  Her left-hand cryosection photographs DO show the carpals,
metacarpals and phalanges as cream blocks (scripts/cryo/q192_hand_evidence.py -> data/derived/Q192_left_hand_evidence.npz: real pixels, no template).  This module
fits the Z-Anatomy left forearm bones and hand bones onto that evidence:

  F  radius_l / ulna_l   one similarity of the pair (multi-start; the Z forearm is a Q168 proxy, 25-30 mm and a pronation twist off), then one bounded
                         similarity per bone onto the evidence assigned to it
  H  hand (carpals + metacarpals) rigid body about the wrist: multi-start inside a +-63 deg cone around the pose the forearm gives it, scale <= 1.04
                         (her right hand: Z hand = her CT hand at scale 1.00), objective = trimmed two-way chamfer to the evidence + a containment term
                         (bones inside her left-hand skin, which is the same photographs)
  C  finger rays 2-5     MCP (flexion + abduction), PIP, DIP hinges about the hand's transverse axis, both flexion signs, sequential, two passes, evidence
                         already explained by other bones removed, bone-bone collision and skin containment terms; thumb: CMC (3 DOF) + MCP + IP

Every stage reports its objective and the NEXT-BEST distinct optimum (the Q191 left-hand trial's problem was a competing optimum 46 mm away).  The result is stored
as one similarity per Z bone FROM THE Z SOURCE FRAME (data/derived/Q192_left_hand_fit.json), so the build only applies it (deterministic, independent of
upstream changes); `fit` recomputes it:

    python3 scripts/zanatomy/build_zan_atlas_viewer.py ... --q191-dump DUMP.npz        # the Q190 state (Z meshes with their source frame)
    python3 scripts/zanatomy/q192_left_hand.py fit --npz DUMP.npz [--validate-right]

The same code runs on the RIGHT hand (side='r') where her CT bones exist: `--validate-right` fits the right Z hand onto the right-hand photographs from a start
turned 25 deg away and measures the result against her CT hand bones (`validate_right`).
"""
from __future__ import annotations

import argparse
import itertools
import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np
from scipy.optimize import minimize
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation as Rot

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from scripts.zanatomy.q191_hand import ORD, bone_ids, kabsch  # noqa: E402

EVIDENCE = REPO / "data" / "derived" / "Q192_left_hand_evidence.npz"
FIT = REPO / "data" / "derived" / "Q192_left_hand_fit.json"
SIDE_SUFFIX = {"l": "_l", "r": "_r"}


# ------------------------------------------------------------------------------------------------ small helpers
def load_evidence(path=EVIDENCE) -> dict:
    z = np.load(path)
    u = float(z["unit_mm"])
    return {k: z[k].astype(np.float32) * u for k in ("hand", "forearm", "right_hand")}


def trimmed(a, f):
    a = np.sort(np.asarray(a))
    return float(a[:max(1, int(f * len(a)))].mean())


def sim_apply(x, P, c):
    """x = [rotvec(3), shift(3), scale]; rotation + scale about the pivot c"""
    R = Rot.from_rotvec(x[:3]).as_matrix()
    return x[6] * (P - c) @ R.T + c + x[3:6]


def interior(v, f, pitch=0.9):
    import trimesh
    return np.asarray(trimesh.Trimesh(v, f, process=False).voxelized(pitch).fill().points, np.float64)


def rot_about(rv, c, P):
    return Rot.from_rotvec(rv).apply(P - c) + c


def joint_point(seg_pts, prev_centroid, frac=0.12):
    d = np.linalg.norm(seg_pts - prev_centroid, axis=1)
    return seg_pts[np.argsort(d)[:max(8, int(frac * len(seg_pts)))]].mean(0)


def chain_apply(th, P, cs):
    """forward kinematics: th[i] rotvec of joint i about centre cs[i] (original frame); bone i is moved by joints i..0"""
    Rm = [Rot.from_rotvec(th[i]) for i in range(len(P))]
    out = []
    for i in range(len(P)):
        X = P[i]
        for j in range(i, -1, -1):
            X = Rm[j].apply(X - cs[j]) + cs[j]
        out.append(X)
    return out


class Skin:
    """her skin as a signed-distance field around the hand (>0 inside); built once from the skin mesh (q191_left_trial.SkinSDF), cached"""

    def __init__(self, cache: Path | None = None, lo=(-250, 0, 10), hi=(-30, 230, 190)):
        if cache is not None and cache.exists():
            self.sdf = pickle.loads(cache.read_bytes())
            return
        from scipy.spatial import cKDTree as KD
        from scripts.ribs_from_ct_labels import load_skin
        from scripts.zanatomy.q191_left_trial import SkinSDF
        skin = load_skin("vhf")
        self.sdf = SkinSDF(skin, KD(np.asarray(skin.vertices, float)), lo, hi, h=1.5)
        if cache is not None:
            cache.write_bytes(pickle.dumps(self.sdf))

    def pen(self, A, depth=2.5, w=0.35):
        return w * float(np.mean(np.maximum(0.0, depth - self.sdf(A)) ** 2))


# ------------------------------------------------------------------------------------------------ model
class HandModel:
    """Z bones of one side at their current (Q190-state) pose: vertices v, faces f, raw Z source frame r, interior points"""

    def __init__(self, by: dict, side="l", pitch=0.9, rng=None):
        self.side = side
        sfx = SIDE_SUFFIX[side]
        self.ids = bone_ids(side)
        self.hand_ids = sum(self.ids.values(), [])
        self.rad, self.uln = "radius" + sfx, "ulna" + sfx
        self.all_ids = self.hand_ids + [self.rad, self.uln]
        self.v = {i: np.asarray(by[i]["v"], float).copy() for i in self.all_ids}
        self.f = {i: np.asarray(by[i]["f"], int) for i in self.all_ids}
        self.r = {i: np.asarray(by[i]["r"], float) for i in self.all_ids} if "r" in by[self.all_ids[0]] else None
        self.pts = {i: interior(self.v[i], self.f[i], pitch) for i in self.all_ids}
        self.rng = rng if rng is not None else np.random.default_rng(0)

    def sub(self, P, n):
        return P[self.rng.choice(len(P), min(n, len(P)), replace=False)]

    def mc(self, o):
        return self.ids["mc"][ORD.index(o)]

    def phal(self, o):
        return [i for i in self.ids["phal"] if f"_of_{o}_finger" in i]


class State:
    """current vertices / interior points of every bone while the stages move them"""

    def __init__(self, M: HandModel):
        self.M = M
        self.pts = {i: M.pts[i].copy() for i in M.all_ids}
        self.v = {i: M.v[i].copy() for i in M.all_ids}

    def move(self, ids, fn):
        for i in ids:
            self.pts[i] = fn(self.pts[i])
            self.v[i] = fn(self.v[i])


# ------------------------------------------------------------------------------------------------ stage F: forearm bones
def fit_forearm(M: HandModel, S: State, ev: np.ndarray, n_starts=11, log=print):
    rng = np.random.default_rng(2)
    Et = cKDTree(ev[rng.choice(len(ev), min(len(ev), 15000), replace=False)])
    Es = ev[rng.choice(len(ev), min(len(ev), 3000), replace=False)]
    both = np.vstack([M.sub(S.pts[M.rad], 1200), M.sub(S.pts[M.uln], 1200)])
    c0 = both.mean(0)

    def J(x, P):
        Q = sim_apply(x, P, c0)
        return trimmed(Et.query(Q)[0], 0.85) + 0.5 * trimmed(cKDTree(Q).query(Es)[0], 0.7)

    res = []
    rs = Rot.random(n_starts, random_state=5)
    for i in range(n_starts):
        rv = np.zeros(3) if i == 0 else rs[i - 1].as_rotvec() * np.radians(25) / np.linalg.norm(rs[i - 1].as_rotvec())
        tr = np.zeros(3) if i == 0 else rng.normal(size=3) * 20
        r = minimize(J, np.r_[rv, tr, 1.0], args=(both,), method="Powell", bounds=[(-0.8, 0.8)] * 3 + [(-90, 90)] * 3 + [(0.9, 1.1)],
                     options={"xtol": 1e-2, "ftol": 1e-5, "maxiter": 1200})
        res.append((float(r.fun), r.x))
    res.sort(key=lambda t: t[0])
    xp = res[0][1]
    # distinct next best: first start whose pose differs by > 5 mm mean point shift
    Pbest = sim_apply(xp, both, c0)
    nxt = next(((f, float(np.linalg.norm(sim_apply(x, both, c0) - Pbest, axis=1).mean())) for f, x in res[1:]
                if np.linalg.norm(sim_apply(x, both, c0) - Pbest, axis=1).mean() > 5.0), None)
    log(f"  Q192 forearm pair: J {res[0][0]:.2f} (J of the Q168 pose {J(np.r_[0, 0, 0, 0, 0, 0, 1.0], both):.1f}); rot {np.degrees(np.linalg.norm(xp[:3])):.0f} deg, shift {xp[3:6].round(1)}, "
        f"scale {xp[6]:.3f}; next distinct optimum {nxt}; starts within 0.05 of best {sum(1 for f, _ in res if f < res[0][0] + 0.05)}/{n_starts}")
    S.move(M.all_ids, lambda P: sim_apply(xp, P, c0))          # the hand follows the forearm pair (the wrist of the Z model is neutral), stage H turns it about the wrist
    # assignment and per-bone refinement
    tR, tU = cKDTree(S.pts[M.rad]), cKDTree(S.pts[M.uln])
    dR, dU = tR.query(ev)[0], tU.query(ev)[0]
    asg, near = np.where(dR < dU, 0, 1), np.minimum(dR, dU) < 10
    per = {}
    for ni, k in enumerate((M.rad, M.uln)):
        E_ = ev[(asg == ni) & near]
        Et2 = cKDTree(E_[rng.choice(len(E_), min(len(E_), 15000), replace=False)])
        Es2 = E_[rng.choice(len(E_), min(len(E_), 3000), replace=False)]
        P = M.sub(S.pts[k], 1500)
        c = P.mean(0)

        def J2(x, P=P, c=c, Et2=Et2, Es2=Es2):
            Q = sim_apply(x, P, c)
            return trimmed(Et2.query(Q)[0], 0.9) + 0.5 * trimmed(cKDTree(Q).query(Es2)[0], 0.8)

        r = minimize(J2, np.r_[0, 0, 0, 0, 0, 0, 1.0], method="Powell", bounds=[(-0.9, 0.9)] * 3 + [(-20, 20)] * 3 + [(0.95, 1.05)],
                     options={"xtol": 1e-2, "ftol": 1e-5, "maxiter": 2000})
        log(f"  Q192 {k}: J {J2(np.r_[0, 0, 0, 0, 0, 0, 1.0]):.2f} -> {r.fun:.2f}; extra rot {np.degrees(np.linalg.norm(r.x[:3])):.0f} deg, shift {r.x[3:6].round(1)}, scale {r.x[6]:.3f}")
        S.move([k], lambda Q, x=r.x, c=c: sim_apply(x, Q, c))
        per[k] = {"J_before": round(float(J2(np.r_[0, 0, 0, 0, 0, 0, 1.0])), 3), "J_after": round(float(r.fun), 3), "evidence_voxels": int(len(E_))}
    return {"pair": {"J": round(res[0][0], 3), "rot_deg": round(float(np.degrees(np.linalg.norm(xp[:3]))), 1), "scale": round(float(xp[6]), 4),
                     "next_distinct_optimum_J_and_shift_mm": nxt, "starts_in_best_basin": int(sum(1 for f, _ in res if f < res[0][0] + 0.05)), "n_starts": n_starts},
            "per_bone": per}


# ------------------------------------------------------------------------------------------------ stage H: the hand as a rigid body
def clean_hand_evidence(M, S, ev_hand, y_max=172.0):
    fa = np.vstack([S.pts[M.rad], S.pts[M.uln]])
    d = cKDTree(fa).query(ev_hand)[0]
    return ev_hand[(d > 4.0) & (ev_hand[:, 1] < y_max)]


def fit_hand_rigid(M: HandModel, S: State, ev: np.ndarray, skin: Skin, n_starts=15, scale_rng=(0.96, 1.04), cone=1.1, log=print):
    rng = np.random.default_rng(4)
    core_ids = [i for i in M.hand_ids if "phalanx" not in i]
    core = np.vstack([S.pts[i] for i in core_ids])
    core = core[rng.choice(len(core), 1500, replace=False)]
    Et = cKDTree(ev[rng.choice(len(ev), 25000, replace=False)])
    Es = ev[rng.choice(len(ev), 5000, replace=False)]
    c0 = S.pts[f"zan_capitate_bone{SIDE_SUFFIX[M.side]}"].mean(0)

    def J(x, Q=core):
        A = sim_apply(x, Q, c0)
        return trimmed(Et.query(A)[0], 0.9) + 0.5 * trimmed(cKDTree(A).query(Es)[0], 0.5) + skin.pen(A)

    rs = Rot.random(n_starts - 1, random_state=9)
    out = []
    for i in range(n_starts):
        rv = np.zeros(3) if i == 0 else rs[i - 1].as_rotvec() * np.radians(30) / np.linalg.norm(rs[i - 1].as_rotvec())
        tr = np.zeros(3) if i == 0 else rng.normal(size=3) * 8
        r = minimize(J, np.r_[rv, tr, 1.0], method="Powell", bounds=[(-cone, cone)] * 3 + [(-30, 30)] * 3 + [tuple(scale_rng)],
                     options={"xtol": 1e-2, "ftol": 1e-5, "maxiter": 1500})
        out.append((float(r.fun), r.x))
    out.sort(key=lambda t: t[0])
    x = out[0][1]
    Pb = sim_apply(x, core, c0)
    nxt = next(((f, float(np.linalg.norm(sim_apply(xx, core, c0) - Pb, axis=1).mean())) for f, xx in out[1:]
                if np.linalg.norm(sim_apply(xx, core, c0) - Pb, axis=1).mean() > 5.0), None)
    inb = sum(1 for f, xx in out if f < out[0][0] + 0.15 and np.linalg.norm(sim_apply(xx, core, c0) - Pb, axis=1).mean() < 4.0)
    log(f"  Q192 hand rigid: J {out[0][0]:.2f}; rot {np.degrees(np.linalg.norm(x[:3])):.0f} deg from the forearm-given pose, shift {x[3:6].round(1)}, scale {x[6]:.3f}; "
        f"{inb}/{n_starts} starts in the best basin (<= 4 mm); next distinct optimum (J, mean shift mm) {nxt}")
    S.move(M.hand_ids, lambda P: sim_apply(x, P, c0))
    return {"J": round(out[0][0], 3), "rot_deg_from_forearm_pose": round(float(np.degrees(np.linalg.norm(x[:3]))), 1), "shift_mm": [round(float(a), 1) for a in x[3:6]],
            "scale": round(float(x[6]), 4), "starts_in_best_basin": int(inb), "n_starts": n_starts, "next_distinct_optimum_J_and_shift_mm": nxt,
            "scale_bound": list(scale_rng)}


# ------------------------------------------------------------------------------------------------ stage C: finger chains
def hand_frame(M: HandModel, S: State):
    sfx = SIDE_SUFFIX[M.side]
    cap = S.pts[f"zan_capitate_bone{sfx}"].mean(0)

    def head(o):
        m = S.pts[M.mc(o)]
        dd = np.linalg.norm(m - cap, axis=1)
        return m[np.argsort(-dd)[:max(8, int(0.12 * len(m)))]].mean(0)

    H = {o: head(o) for o in ORD}
    d = H["third"] - cap
    d /= np.linalg.norm(d)
    t = H["second"] - H["fifth"]
    t -= d * (t @ d)
    t /= np.linalg.norm(t)
    return cap, H, d, t


def _owner_free(S, M, skip, ev, ctr, reach=75.0, thin=3):
    pts = np.vstack([S.pts[k] for k in M.hand_ids if k not in skip] + [S.pts[M.rad], S.pts[M.uln]])
    m = cKDTree(pts).query(ev, distance_upper_bound=2.2)[0] > 2.2
    E = ev[m]
    return E[np.linalg.norm(E - ctr, axis=1) < reach][::thin]


def fit_ray(M, S, o, ev, skin, tt0, H, signs=(1, -1), log=print):
    bs = M.phal(o)
    k = len(bs)
    P = [S.pts[b] for b in bs]
    V = [S.v[b] for b in bs]
    mcc = S.pts[M.mc(o)].mean(0)
    cs, prev = [], mcc
    for p in P:
        cs.append(joint_point(p, prev))
        prev = p.mean(0)
    dist = P[-1].mean(0)
    dk = dist - mcc
    dk /= np.linalg.norm(dk)
    Ef = _owner_free(S, M, set(bs), ev, H[o])
    Et = cKDTree(Ef)
    others = np.vstack([S.pts[b] for b in M.hand_ids if b not in bs])
    Ot = cKDTree(others[::2])
    Ps = [M.sub(p, 300) for p in P]
    best_all = []
    for sg in signs:
        a = tt0 - dk * (tt0 @ dk)
        a = sg * a / np.linalg.norm(a)
        n_ = np.cross(dk, a)
        n_ /= np.linalg.norm(n_)

        def rots(x):
            th = np.zeros((k, 3))
            th[0] = x[0] * a + x[1] * n_
            for i in range(1, k):
                th[i] = x[i + 1] * a
            return th

        def obj(x, reg=3e-3):
            A = np.vstack(chain_apply(rots(x), Ps, cs))
            f = trimmed(Et.query(A)[0], 0.85)
            tA = cKDTree(A)
            near = Ef[tA.query(Ef, distance_upper_bound=6.0)[0] < 6.0]
            g = trimmed(tA.query(near)[0], 0.5) if len(near) > 20 else 6.0
            coll = float(np.maximum(0.0, 2.0 - Ot.query(A)[0]).mean()) * 3.0
            return f + 0.5 * g + coll + skin.pen(A) + reg * 100 * float((x ** 2).sum())

        lo = [-0.3, -0.45] + [-0.1] * (k - 1)
        hi = [1.75, 0.45] + [1.95] * (k - 2) + [1.4]
        grid = itertools.product((0, 0.5, 1.0, 1.5), (0,), (0, 0.8, 1.6), (0, 0.6, 1.2)) if k == 3 else itertools.product((0, 0.5, 1.0, 1.5), (0,), (0, 0.8, 1.6))
        starts = sorted(((obj(np.array(g)), np.array(g)) for g in grid), key=lambda t: t[0])
        for f0, x0 in starts[:5]:
            r = minimize(obj, x0, method="Powell", bounds=list(zip(lo, hi)), options={"xtol": 1e-3, "ftol": 1e-5, "maxiter": 2500})
            best_all.append((float(r.fun), r.x, sg, rots(r.x)))
    best_all.sort(key=lambda t: t[0])
    f, x, sg, th = best_all[0]
    X = chain_apply(th, P, cs)
    XV = chain_apply(th, V, cs)
    alts = []
    for f2, x2, sg2, th2 in best_all[1:]:
        sh = float(np.mean([np.linalg.norm(a - b, axis=1).mean() for a, b in zip(X, chain_apply(th2, P, cs))]))
        if sh > 3.0:
            alts.append((round(f2, 3), round(sh, 1)))
            break
    rep = {"J": round(f, 3), "flexion_sign": sg, "angles_deg": {"mcp_flex": round(float(np.degrees(x[0])), 1), "mcp_abd": round(float(np.degrees(x[1])), 1),
                                                                "pip": round(float(np.degrees(x[2])), 1), **({"dip": round(float(np.degrees(x[3])), 1)} if k == 3 else {})},
           "next_distinct_optimum_J_and_shift_mm": alts[0] if alts else None, "evidence_voxels_in_reach": int(len(Ef))}
    log(f"  Q192 ray {o}: J {f:.2f}; {rep['angles_deg']}; next distinct optimum {rep['next_distinct_optimum_J_and_shift_mm']}")
    return bs, X, XV, rep


def fit_thumb(M, S, ev, skin, log=print):
    sfx = SIDE_SUFFIX[M.side]
    bs = [M.mc("first")] + M.phal("first")
    P = [S.pts[b] for b in bs]
    V = [S.v[b] for b in bs]
    trap = S.pts[f"zan_trapezium_bone{sfx}"].mean(0)
    cs, prev = [], trap
    for p in P:
        cs.append(joint_point(p, prev))
        prev = p.mean(0)
    Ef = _owner_free(S, M, set(bs), ev, cs[0], reach=85.0)
    Et = cKDTree(Ef)
    others = np.vstack([S.pts[b] for b in M.hand_ids if b not in bs])
    Ot = cKDTree(others[::2])
    Ps = [M.sub(p, 300) for p in P]
    cap, H, d, t = hand_frame(M, S)
    n_ = np.cross(d, t)

    def obj(x, reg=2e-3):
        A = np.vstack(chain_apply(x.reshape(3, 3), Ps, cs))
        f = trimmed(Et.query(A)[0], 0.85)
        tA = cKDTree(A)
        near = Ef[tA.query(Ef, distance_upper_bound=6.0)[0] < 6.0]
        g = trimmed(tA.query(near)[0], 0.5) if len(near) > 20 else 6.0
        coll = float(np.maximum(0.0, 2.0 - Ot.query(A)[0]).mean()) * 3.0
        return f + 0.5 * g + coll + skin.pen(A) + reg * 100 * float((x ** 2).sum())

    A_ = [np.radians(a) for a in (-40, 0, 40)]
    B_ = [np.radians(a) for a in (-45, 0, 45)]
    starts = []
    for a1, a2 in itertools.product(A_, A_):
        for a3, a4 in itertools.product(B_, B_):
            th = np.zeros((3, 3))
            th[0], th[1], th[2] = a1 * t + a2 * n_, a3 * t, a4 * t
            starts.append((obj(th.ravel()), th.ravel()))
    starts.sort(key=lambda s: s[0])
    res = []
    for f0, x0 in starts[:5]:
        r = minimize(obj, x0, method="Powell", bounds=[(-1.8, 1.8)] * 9, options={"xtol": 1e-2, "ftol": 1e-5, "maxiter": 3000})
        res.append((float(r.fun), r.x))
    res.sort(key=lambda s: s[0])
    th = res[0][1].reshape(3, 3)
    X = chain_apply(th, P, cs)
    XV = chain_apply(th, V, cs)
    alts = None
    for f2, x2 in res[1:]:
        sh = float(np.mean([np.linalg.norm(a - b, axis=1).mean() for a, b in zip(X, chain_apply(x2.reshape(3, 3), P, cs))]))
        if sh > 3.0:
            alts = (round(f2, 3), round(sh, 1))
            break
    rep = {"J": round(res[0][0], 3), "joint_rotation_deg": [round(float(np.degrees(np.linalg.norm(th[i]))), 1) for i in range(3)], "next_distinct_optimum_J_and_shift_mm": alts}
    log(f"  Q192 thumb: {rep}")
    return bs, X, XV, rep


def fit_chains(M, S, ev, skin, passes=2, log=print):
    cap, H, d, t = hand_frame(M, S)
    rep = {}
    for ps in range(passes):
        for o in ("fifth", "fourth", "third", "second"):
            bs, X, XV, r = fit_ray(M, S, o, ev, skin, t, H, log=log)
            for b, x, xv in zip(bs, X, XV):
                S.pts[b], S.v[b] = x, xv
            rep[o] = r
    bs, X, XV, r = fit_thumb(M, S, ev, skin, log=log)
    for b, x, xv in zip(bs, X, XV):
        S.pts[b], S.v[b] = x, xv
    rep["first"] = r
    return rep


# ------------------------------------------------------------------------------------------------ evaluation against the evidence
def evidence_fit(M, S, ev_hand, ev_fa=None):
    """how well the fitted Z bones explain the photographs: share of evidence voxels within 1.5 / 3 mm of a bone and share of bone volume on evidence"""
    out = {}
    for name, ids_, ev in (("hand", M.hand_ids, ev_hand), ("forearm", [M.rad, M.uln], ev_fa)):
        if ev is None:
            continue
        B = np.vstack([S.pts[i] for i in ids_])
        d = cKDTree(B).query(ev)[0]
        e = cKDTree(ev).query(B)[0]
        out[name] = {"evidence_within_1.5mm_of_a_Z_bone_pct": round(100 * float((d < 1.5).mean()), 1), "evidence_within_3mm_pct": round(100 * float((d < 3.0).mean()), 1),
                     "Z_bone_volume_within_1.5mm_of_evidence_pct": round(100 * float((e < 1.5).mean()), 1),
                     "median_Z_to_evidence_mm": round(float(np.median(e)), 2), "median_evidence_to_Z_mm": round(float(np.median(d)), 2)}
    return out


def to_transforms(M: HandModel, S: State, ids_=None):
    """one similarity per bone from the Z source frame (s, R, t) with the residual of the vertices"""
    out = {}
    for i in (ids_ or M.all_ids):
        s, R, t = kabsch(M.r[i], S.v[i], scale=True)
        resid = float(np.abs((s * M.r[i] @ R.T + t) - S.v[i]).max())
        out[i] = {"s": float(s), "R": R.tolist(), "t": t.tolist(), "max_residual_mm": round(resid, 4)}
    return out


def apply_transforms(raw: dict, T: dict) -> dict:
    return {i: float(t["s"]) * np.asarray(raw[i], float) @ np.asarray(t["R"]).T + np.asarray(t["t"]) for i, t in T.items()}


# ------------------------------------------------------------------------------------------------ drivers
def fit_left(by: dict, ev: dict, skin_cache: Path | None = None, log=print):
    t0 = time.time()
    M = HandModel(by, "l")
    S = State(M)
    skin = Skin(skin_cache)
    rep = {"forearm": fit_forearm(M, S, ev["forearm"], log=log)}
    evh = clean_hand_evidence(M, S, ev["hand"])
    log(f"  Q192 hand evidence after removing her radius/ulna: {len(evh)} voxels")
    rep["hand_rigid"] = fit_hand_rigid(M, S, evh, skin, log=log)
    rep["chains"] = fit_chains(M, S, evh, skin, log=log)
    rep["evidence_fit"] = evidence_fit(M, S, evh, ev["forearm"])
    rep["seconds"] = round(time.time() - t0)
    return M, S, rep


def validate_right(by: dict, ev: dict, her_ct: dict, shift=(-1.0, -2.0, 13.0), start_turn_deg=25.0, skin=None, log=print):
    """the same pipeline on the RIGHT hand, where her CT bones exist.  Start: the Z right hand (Q168/Q191 pose = her CT) moved by the photograph-vs-CT shift of her right arm
    and turned `start_turn_deg` about the wrist (the left hand starts ~25 deg from its answer); result vs her CT bones (moved by the same shift)."""
    from scripts.zanatomy.q191_hand import chamfer2, surf_pts
    M = HandModel(by, "r")
    S = State(M)
    sh = np.asarray(shift, float)
    cap = S.pts["zan_capitate_bone_r"].mean(0) + sh
    R0 = Rot.from_rotvec(np.radians(start_turn_deg) * np.array([0.3, 0.8, 0.5]) / np.linalg.norm([0.3, 0.8, 0.5]))
    S.move(M.all_ids, lambda P: R0.apply(P + sh - cap) + cap)
    evh = ev["right_hand"][ev["right_hand"][:, 1] < 172.0]
    skin = skin or Skin(None, lo=(30, 0, 10), hi=(250, 230, 190))
    rep = {"rigid": fit_hand_rigid(M, S, evh, skin, log=log)}
    rep["chains"] = fit_chains(M, S, evh, skin, log=log)
    groups = {"carpals": (M.ids["carpals"], "carpals_r"), "phalanges": (M.ids["phal"], "phalanges_hand_r"), **{f"mc{k + 1}": ([M.ids["mc"][k]], f"metacarpal_{k + 1}_r") for k in range(5)}}
    err = {}
    for g, (zids, her_id) in groups.items():
        ref = surf_pts(her_ct[her_id]["v"].astype(float) + sh, her_ct[her_id]["f"], 6000)
        A = np.vstack([surf_pts(S.v[i], M.f[i], 800, ) for i in zids])
        B = np.vstack([surf_pts(M.v[i] + sh, M.f[i], 800) for i in zids])           # the start without any fitting (Q168 pose moved by the shift)
        a = chamfer2(A, ref)
        b = chamfer2(B, ref)
        err[g] = {"two_way_median_mm_fitted_from_photographs": round(a[2], 2), "Q168_pose_shifted_by_the_arm_offset_mm": round(b[2], 2)}
    rep["vs_her_CT_bones"] = err
    return rep


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["fit"])
    ap.add_argument("--npz", required=True)
    ap.add_argument("--evidence", default=str(EVIDENCE))
    ap.add_argument("--out", default=str(FIT))
    ap.add_argument("--skin-cache", default=None)
    ap.add_argument("--validate-right", action="store_true")
    a = ap.parse_args(argv)
    from scripts.zanatomy import q190_metrics as Mx
    L = {d["id"]: d for d in Mx.load_dump(a.npz)}
    ev = load_evidence(Path(a.evidence))
    M, S, rep = fit_left(L, ev, Path(a.skin_cache) if a.skin_cache else None)
    T = to_transforms(M, S)
    out = {"source": "Q192: scripts/zanatomy/q192_left_hand.py on data/derived/Q192_left_hand_evidence.npz (her left-hand cryosection photographs, scripts/cryo/q192_hand_evidence.py)",
           "report": rep, "transforms_from_Z_source_frame": T}
    if a.validate_right:
        from scripts.transfer.zan_to_vhf_whole_body import load_her_meshes
        out["validation_right_hand"] = validate_right(L, ev, load_her_meshes())
    Path(a.out).write_text(json.dumps(out, indent=1))
    print("wrote", a.out)


if __name__ == "__main__":
    main()
