"""Q205 (male): both HANDS of the Z-Anatomy model fitted to the VISIBLE HUMAN MALE re-fitted per bone chain on HIS evidence.

Why: Q204 measured the Q195 hand fit: the first metacarpal -> proximal phalanx gap is 81.8 (L) / 88.7 (R) mm (0.1 mm in the Z source), the thumb bones lie 20-50 mm outside his skin,
the 5th CMC joint is open 4.1 mm, the right first / fifth metacarpal sit 8-9 mm off his CT hand labels (Q191's per-piece fit onto his COMPOSITE meshes).
Evidence = his CT hand-bone labels (data/derived/Q205_his_hand_labels.npz: carpals / metacarpals / phalanges / radius / ulna label voxels of
vhm_arm_bones_cryo_completed.nii.gz in atlas mm; the carpal / metacarpal / phalanx split is a plane cut, so the labels are used as ONE bone mass) + his CT skin as the envelope.
Method = the Q192 stages (q192_left_hand: rigid hand body about the wrist, rays 2-5 MCP / PIP / DIP hinges, thumb CMC + MCP + IP, both signs, bone-bone collision, skin containment)
started from the Q201 state, aimed at his labels instead of her photographs.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
LABELS = REPO / "data" / "derived" / "Q205_his_hand_labels.npz"


def load_labels(side):
    z = np.load(LABELS)
    return {k: z[f"{k}_{side}"].astype(np.float64) for k in ("carp", "mc", "ph", "radius", "ulna")}


class HisEnvelope:
    """his CT skin as a signed-distance field (>0 inside) around one hand; same pen() as q192_left_hand.Envelope"""

    def __init__(self, skin, side, h=1.5, pad=45.0, log=print):
        from scripts.zanatomy.q191_left_trial import SkinSDF
        L = load_labels(side)
        P = np.vstack([L["carp"], L["mc"], L["ph"]])
        lo, hi = P.min(0) - pad, P.max(0) + pad
        self.sdf = SkinSDF(skin, cKDTree(np.asarray(skin.vertices, float)), lo, hi, h=h)
        self.lo, self.hi = lo, hi

    def __call__(self, P):
        return self.sdf(P)

    def pen(self, A, depth=2.5, w=0.35):
        return w * float(np.mean(np.maximum(0.0, depth - self.sdf(A)) ** 2))


# ------------------------------------------------------------------------------------------------ fit
def _setup():
    from scripts.zanatomy import body_ctx
    body_ctx.configure("vhm")
    from scripts.zanatomy import q192_left_hand as H
    return H


def fit_mc(H, M, S, o, ev, env, log=print):
    """metacarpal o (+ its phalanges, rigidly) turned about its carpal joint: <= 0.30 rad (17 deg), objective = trimmed two-way chamfer to the evidence not explained by the other bones
    + skin containment + collision with the other bones + a prior on the turn"""
    from scipy.optimize import minimize
    from scipy.spatial.transform import Rotation as Rot
    mc = M.mc(o)
    chain = [mc] + M.phal(o)
    Pm = S.pts[mc]
    cap = S.pts[f"zan_capitate_bone_{M.side}"].mean(0)
    dd = np.linalg.norm(Pm - cap, axis=1)
    cj = Pm[np.argsort(dd)[:max(8, int(0.12 * len(Pm)))]].mean(0)          # the carpal end of the metacarpal
    Ef = H._owner_free(S, M, set(chain), ev, Pm.mean(0), reach=60.0, thin=2)
    Et = cKDTree(Ef)
    others = np.vstack([S.pts[b] for b in M.hand_ids if b not in chain] + [S.pts[M.rad], S.pts[M.uln]])
    Ot = cKDTree(others[::2])
    rng = np.random.default_rng(3)
    Ps = M.sub(Pm, 500)

    def obj(x):
        A = Rot.from_rotvec(x).apply(Ps - cj) + cj
        f = H.trimmed(Et.query(A)[0], 0.85) if len(Ef) else 0.0
        tA = cKDTree(A)
        near = Ef[tA.query(Ef, distance_upper_bound=5.0)[0] < 5.0]
        g = H.trimmed(tA.query(near)[0], 0.5) if len(near) > 20 else 5.0
        coll = float(np.maximum(0.0, 2.0 - Ot.query(A)[0]).mean()) * 3.0
        return f + 0.5 * g + coll + env.pen(A) + 4.0 * float((x ** 2).sum())

    best = min(((obj(np.zeros(3)), np.zeros(3)),), key=lambda t: t[0])
    res = minimize(obj, np.zeros(3), method="Powell", bounds=[(-0.30, 0.30)] * 3, options={"xtol": 1e-3, "ftol": 1e-5, "maxiter": 800})
    if res.fun < best[0] - 0.05:
        R = Rot.from_rotvec(res.x)
        S.move(chain, lambda P: R.apply(P - cj) + cj)
        log(f"  Q205 MC {o}: J {best[0]:.2f} -> {res.fun:.2f}, turn {np.degrees(np.linalg.norm(res.x)):.1f} deg")
        return {"J_before": round(best[0], 3), "J_after": round(float(res.fun), 3), "turn_deg": round(float(np.degrees(np.linalg.norm(res.x))), 1), "rotvec": [float(a) for a in res.x]}
    return {"J_before": round(best[0], 3), "J_after": round(best[0], 3), "turn_deg": 0.0, "held": True}


def reseat_phalanges(H, M, S, o, log=print):
    """Q195 left the thumb phalanges 82-89 mm from their metacarpal (the Q168 placement of the composite phalanx piece).  Put the ray's phalanges back into the metacarpal's frame
    exactly as in the Z source: new pose = similarity(raw metacarpal -> current metacarpal) applied to the RAW phalanges (touching distance of the source, source posture), and the
    interior points follow the same motion.  Returns the gap before / after (mm)"""
    from scripts.zanatomy.q191_hand import kabsch, apply_T
    mc = M.mc(o)
    Tm = kabsch(M.r[mc], S.v[mc], scale=True)
    g0 = float(cKDTree(S.pts[mc][::2]).query(S.pts[M.phal(o)[0]][::2])[0].min())
    for b in M.phal(o):
        newv = apply_T(Tm, M.r[b])
        Tb = kabsch(S.v[b], newv, scale=True)
        S.pts[b] = apply_T(Tb, S.pts[b])
        S.v[b] = newv
    g1 = float(cKDTree(S.pts[mc][::2]).query(S.pts[M.phal(o)[0]][::2])[0].min())
    log(f"  Q205 reseat {o}: metacarpal -> proximal phalanx gap {g0:.1f} -> {g1:.2f} mm")
    return {"gap_before_mm": round(g0, 2), "gap_after_mm": round(g1, 2)}


def thumb_gap(S, M):
    from scripts.zanatomy.q191_hand import surf_pts
    a, b = M.mc("first"), M.phal("first")[0]
    return float(cKDTree(S.pts[a][::2]).query(S.pts[b][::2])[0].min())


def fit_thumb2(H, M, S, ev, env, log=print, n_random=80, n_refine=10):
    """thumb chain CMC (3 DOF, <= 0.5 rad) + MCP (3 DOF, <= 1.2 rad) + IP (3 DOF, <= 1.4 rad) about the Z joints, from many starts.  Objective: Q192 thumb terms (evidence the other bones do
    not explain, collision, skin containment) + CORE term: the thumb phalanges lie in the middle of his thumb soft tissue (his skin signed distance >= 6 mm, the thumb is ~20 mm thick) +
    tip term (the distal end 3-8 mm inside his skin) + joint continuity (MC1 head - proximal phalanx base touch as in the Z source) + priors on the turns"""
    from scipy.optimize import minimize
    from scipy.spatial.transform import Rotation as Rot
    import itertools
    sfx = "_" + M.side
    bs = [M.mc("first")] + M.phal("first")
    P = [S.pts[b] for b in bs]
    V = [S.v[b] for b in bs]
    trap = S.pts[f"zan_trapezium_bone{sfx}"].mean(0)
    cs, prev = [], trap
    for p in P:
        cs.append(H.joint_point(p, prev))
        prev = p.mean(0)
    Ef = H._owner_free(S, M, set(bs), ev, cs[0], reach=85.0)
    Et = cKDTree(Ef) if len(Ef) else None
    others = np.vstack([S.pts[b] for b in M.hand_ids if b not in bs])
    Ot = cKDTree(others[::2])
    Ps = [M.sub(p, 300) for p in P]
    # the Z-source continuity: nearest surface distance MC1 -> proximal phalanx in the CURRENT state (the Z source touches within ~0.1 mm; the chain keeps that by construction when only joint rotations are used)
    lim = np.array([0.5] * 3 + [1.2] * 3 + [1.4] * 3)

    def chain_pts(x):
        return H.chain_apply(x.reshape(3, 3), Ps, cs)

    def obj(x):
        Xs = chain_pts(x)
        A = np.vstack(Xs)
        tA = cKDTree(A)
        f = H.trimmed(Et.query(A)[0], 0.85) if Et is not None else 0.0
        near = Ef[tA.query(Ef, distance_upper_bound=6.0)[0] < 6.0] if Et is not None else np.zeros((0, 3))
        g = H.trimmed(tA.query(near)[0], 0.5) if len(near) > 20 else 6.0
        coll = float(np.maximum(0.0, 2.0 - Ot.query(A)[0]).mean()) * 3.0
        ph = np.vstack(Xs[1:])
        core = 0.12 * float(np.mean(np.maximum(0.0, 6.0 - env(ph)) ** 2))
        # tip: the 5 % of the distal phalanx farthest from the MC head
        d = Xs[2]
        tip = d[np.argsort(-np.linalg.norm(d - Xs[0].mean(0), axis=1))[:max(5, len(d) // 20)]]
        tip_pen = 0.3 * float(np.mean(np.maximum(0.0, 3.0 - env(tip)) ** 2 + np.maximum(0.0, env(tip) - 9.0) ** 2))
        return 0.5 * f + 0.25 * g + coll + env.pen(A) + core + tip_pen + 1.5 * float((x ** 2).sum()) * 0.1

    rr = np.random.default_rng(11)
    starts = [(obj(np.zeros(9)), np.zeros(9))]
    for _ in range(n_random):
        x0 = rr.uniform(-1, 1, 9) * lim * 0.6
        starts.append((obj(x0), x0))
    starts.sort(key=lambda s: s[0])
    res = []
    for f0, x0 in starts[:n_refine]:
        r = minimize(obj, x0, method="Powell", bounds=list(zip(-lim, lim)), options={"xtol": 1e-2, "ftol": 1e-5, "maxiter": 3000})
        res.append((float(r.fun), r.x))
    res.sort(key=lambda s: s[0])
    x = res[0][1]
    X = H.chain_apply(x.reshape(3, 3), P, cs)
    XV = H.chain_apply(x.reshape(3, 3), V, cs)
    alts = None
    for f2, x2 in res[1:]:
        sh = float(np.mean([np.linalg.norm(a - b, axis=1).mean() for a, b in zip(X, H.chain_apply(x2.reshape(3, 3), P, cs))]))
        if sh > 3.0:
            alts = (round(f2, 3), round(sh, 1))
            break
    for b, xx, xv in zip(bs, X, XV):
        S.pts[b], S.v[b] = xx, xv
    rep = {"J": round(res[0][0], 3), "J_start": round(starts[0][0] if starts[0][1].any() == 0 else obj(np.zeros(9)), 3), "joint_rotation_deg": [round(float(np.degrees(np.linalg.norm(x.reshape(3, 3)[i]))), 1) for i in range(3)],
           "next_distinct_optimum_J_and_shift_mm": alts, "evidence_voxels_in_reach": int(len(Ef))}
    log(f"  Q205 thumb: {rep}")
    return rep


def fit_side(by, side, skin, log=print, quick=False):
    """full per-bone chain fit of one hand on his evidence.  Returns (M, S, report, env)"""
    H = _setup()
    t0 = time.time()
    lab = load_labels(side)
    ev = np.vstack([lab["carp"], lab["mc"], lab["ph"]]).astype(np.float32)
    env = HisEnvelope(skin, side)
    M = H.HandModel(by, side)
    S = H.State(M)
    evh = H.clean_hand_evidence(M, S, ev, y_max=1e9)
    rep = {"labels_voxels": int(len(evh)), "evidence_before": H.evidence_fit(M, S, evh)}
    rep["reseat_thumb"] = reseat_phalanges(H, M, S, "first", log=log)
    rep["hand_rigid"] = H.fit_hand_rigid(M, S, evh, env, n_starts=5 if quick else 9, scale_rng=(0.96, 1.06), cone=0.5, log=log)
    rep["metacarpals"] = {o: fit_mc(H, M, S, o, evh, env, log=log) for o in ("fifth", "fourth", "third", "second")}
    cap, Hh, d, t = H.hand_frame(M, S)
    rep["chains"] = {}
    for ps in range(1 if quick else 2):
        for o in ("fifth", "fourth", "third", "second"):
            bs, X, XV, r = H.fit_ray(M, S, o, evh, env, t, Hh, log=log)
            for b, x, xv in zip(bs, X, XV):
                S.pts[b], S.v[b] = x, xv
            rep["chains"][o] = r
    evt = H.clean_hand_evidence(M, S, np.vstack([lab["mc"], lab["ph"]]).astype(np.float32), y_max=1e9)      # the carpal label block is NOT evidence for the thumb (it would attract the phalanges to the carpals)
    rep["chains"]["first"] = fit_thumb2(H, M, S, evt, env, log=log, n_random=30 if quick else 80)
    rep["nudged_inside_his_skin"] = H.nudge_inside(M, S, env, evh, log=log)
    rep["evidence_after"] = H.evidence_fit(M, S, evh)
    rep["thumb_gap_after_mm"] = round(thumb_gap(S, M), 3)
    rep["seconds"] = round(time.time() - t0)
    return M, S, rep, env
