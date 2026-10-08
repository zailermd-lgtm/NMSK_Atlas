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
CT_EVID = REPO / "data" / "derived" / "Q205_his_hand_ct_evidence.npz"
Y_BLOCK = 34.0                      # atlas y: above = the torso CT block (HU evidence), below = the legs-block fingers (label volume)


def load_labels(side):
    z = np.load(LABELS)
    return {k: z[f"{k}_{side}"].astype(np.float64) for k in ("carp", "mc", "ph", "radius", "ulna")}


def load_evidence(side):
    """his hand-bone evidence of one side (atlas mm): the frozen-CT HU >= 250 solids for atlas y >= 34 (scripts/cryo/q205_ct_hand_evidence.py; the label volume kept only the dorsal-ulnar bones there,
    the thumb and most metacarpals / phalanges of the torso block are NOT in it) plus the label volume's carpal / metacarpal / phalanx voxels below y = 34 (legs-block fingers)"""
    lab = load_labels(side)
    L = np.vstack([lab["carp"], lab["mc"], lab["ph"]])
    ct = np.load(CT_EVID)[f"ct_{side}"].astype(np.float64)
    return np.vstack([L[L[:, 1] < Y_BLOCK], ct]).astype(np.float32)


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
    lim = np.array([0.9] * 3 + [1.3] * 3 + [1.4] * 3)

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


def fit_side(by, side, skin, log=print):
    """per-bone chain fit of one hand on his evidence: (1) the Z-source hand on his forearm, (2) carpal + metacarpal block turned about the wrist (global rotation sampling), (3) each ray:
    metacarpal turn + hinge chain, kept only where the evidence score gains, (4) thumb: reseat on its metacarpal, CMC / MCP / IP articulated beam search, (5) bones > 2 % outside his skin nudged in.
    Returns (M, S, report)"""
    H = _setup()
    t0 = time.time()
    ev = load_evidence(side)
    env = HisEnvelope(skin, side)
    M = H.HandModel(by, side)
    S = H.State(M)
    evh = H.clean_hand_evidence(M, S, ev, y_max=1e9)
    Et = cKDTree(evh)
    rep = {"evidence_voxels": int(len(evh)), "evidence_before": H.evidence_fit(M, S, evh),
           "bone_evidence_score_before": {b[4:]: round(bone_score(S, b, Et), 2) for b in M.hand_ids}}
    rep["forearm_given"] = forearm_given_pose(H, M, S, log=log)
    rep["hand_block"] = fit_hand_global(H, M, S, evh, env, log=log)
    rep["reseat_thumb"] = reseat_phalanges(H, M, S, "first", log=log)
    rep["rays"] = refine_rays(H, M, S, evh, env, log=log)
    rep["thumb"] = thumb_beam(H, M, S, evh, env, log=log)
    rep["nudged_inside_his_skin"] = H.nudge_inside(M, S, env, evh, log=log)
    rep["evidence_after"] = H.evidence_fit(M, S, evh)
    rep["bone_evidence_score_after"] = {b[4:]: round(bone_score(S, b, Et), 2) for b in M.hand_ids}
    rep["thumb_gap_after_mm"] = round(thumb_gap(S, M), 3)
    rep["seconds"] = round(time.time() - t0)
    return M, S, rep


# ------------------------------------------------------------------------------------------------ evidence-scored articulated search (v2)
def _score(P, Et, cap=4.0):
    return float(np.minimum(Et.query(P)[0], cap).mean())


def bone_score(S, b, Et):
    return _score(S.pts[b], Et)


def so3_grid(n=1200, max_deg=100.0, seed=0):
    """rotation vectors: the identity + n quasi-random rotations with angle <= max_deg"""
    from scipy.spatial.transform import Rotation as Rot
    r = Rot.random(n * 3, random_state=seed)
    rv = r.as_rotvec()
    ang = np.linalg.norm(rv, axis=1)
    rv = rv[ang <= np.radians(max_deg)][:n]
    return np.vstack([np.zeros((1, 3)), rv])


def beam_chain(H, M, S, bs, joints, Et, others_tree, env, max_deg=(110.0, 100.0, 90.0), beam=6, n_rot=1500, log=print, w_env=1.0, label="chain"):
    """articulated chain bs = [b0, b1, ...] turned about joints[i] (points in the CURRENT frame): stage i samples rotations of bone i (and of everything distal of it, rigidly) about joints[i]
    (the joint centre moves with the proximal bones), scores bone i by the mean distance of its interior points to the evidence (capped), collision with the other bones and containment in his
    skin; a beam of the best partial chains is kept; the best full chain is polished by Powell.  Everything is a rotation about a joint: bone lengths and joint distances stay those of the Z source"""
    from scipy.spatial.transform import Rotation as Rot
    from scipy.optimize import minimize
    P = [S.pts[b] for b in bs]
    V = [S.v[b] for b in bs]
    k = len(bs)
    Ps = [M.sub(p, 400) for p in P]

    def pose(th):
        return H.chain_apply(th, Ps, joints)

    def cost_i(Xi):
        coll = float(np.maximum(0.0, 1.5 - others_tree.query(Xi)[0]).mean()) * 3.0
        return _score(Xi, Et) + coll + w_env * env.pen(Xi)

    states = [(0.0, np.zeros((k, 3)))]
    for i in range(k):
        cand = []
        grid = so3_grid(n_rot, max_deg[min(i, len(max_deg) - 1)], seed=i)
        for sc, th in states:
            Xs_prev = None
            for rv in grid:
                t2 = th.copy()
                t2[i] = rv
                Xi = pose(t2[:i + 1])[i] if False else H.chain_apply(t2[:i + 1], Ps[:i + 1], joints[:i + 1])[i]
                cand.append((sc + cost_i(Xi), t2))
        cand.sort(key=lambda t: t[0])
        # beam with diversity: skip candidates whose pose of bone i is within 2 mm (mean) of a kept one
        kept, keptX = [], []
        for c, t2 in cand:
            Xi = H.chain_apply(t2[:i + 1], Ps[:i + 1], joints[:i + 1])[i]
            if all(np.linalg.norm(Xi - x, axis=1).mean() > 2.0 for x in keptX):
                kept.append((c, t2))
                keptX.append(Xi)
            if len(kept) >= beam:
                break
        states = kept
        log(f"  Q205 {label}: stage {i + 1}/{k}: best cumulative cost {states[0][0]:.2f}")
    best = None
    for sc, th in states:
        def obj(x):
            Xs = pose(x.reshape(k, 3))
            return sum(cost_i(X) for X in Xs) + 0.5 * float((x ** 2).sum()) * 0.02
        lim = np.array([np.radians(m) for m in (list(max_deg) + [max_deg[-1]] * k)[:k] for _ in range(3)])
        r = minimize(obj, th.ravel(), method="Powell", bounds=list(zip(-lim, lim)), options={"xtol": 1e-3, "ftol": 1e-5, "maxiter": 2500})
        if best is None or r.fun < best[0]:
            best = (float(r.fun), r.x.reshape(k, 3))
    th = best[1]
    X = H.chain_apply(th, P, joints)
    XV = H.chain_apply(th, V, joints)
    return X, XV, {"cost": round(best[0], 3), "joint_rotation_deg": [round(float(np.degrees(np.linalg.norm(t))), 1) for t in th]}


def source_contacts(M, ids, touch_mm=3.0):
    """pairs of bones (from ids + forearm bones) that touch in the Z source (raw frame x body scale): {(a, b): source distance}"""
    from scripts.zanatomy import q190_metrics as Mx
    from scripts.zanatomy.q191_hand import surf_pts
    pts = {i: surf_pts(M.r[i], M.f[i], 1500) for i in ids}
    out = {}
    for a in ids:
        ta = cKDTree(pts[a])
        for b in ids:
            if a < b:
                d = float(ta.query(pts[b])[0].min()) * Mx.BODY_SCALE
                if d <= touch_mm:
                    out[(a, b)] = d
    return out


def fit_carpals(H, M, S, ev, Et, env, contacts, log=print, rounds=2, only=None):
    """each carpal: bounded similarity (<= 0.35 rad, <= 8 mm, scale 0.96-1.04) about its own centroid; objective = (a) distance of its interior points to the evidence (capped) + (b) COVERAGE of
    the carpal evidence (the evidence within 5 mm of the carpal group) by the union of the carpals, so a bone cannot shrink into the mass + collision with every other hand / forearm bone +
    the Z-source contacts (pairs that touch in the Z source keep touching: <= 1.5 mm) + skin; kept only if the objective gains.  Returns (report, {id: (s, R, t) net motion})"""
    from scipy.optimize import minimize
    from scipy.spatial.transform import Rotation as Rot
    from scripts.zanatomy.q191_hand import kabsch
    carp = list(M.ids["carpals"])
    v_start = {b: S.v[b].copy() for b in carp}
    E_g = None
    rep = {}
    order = ["capitate", "hamate", "lunate", "scaphoid", "triquetrum", "trapezium", "trapezoid", "pisiform"]
    for rd in range(rounds):
        U0 = np.vstack([S.pts[k] for k in carp])
        E_g = ev[cKDTree(U0).query(ev)[0] < 5.0]
        Eg_t = cKDTree(E_g)
        for nm in order:
            if only is not None and nm not in only:
                continue
            b = f"zan_{nm}_bone_{M.side}"
            P = S.pts[b]
            c = P.mean(0)
            Ps = M.sub(P, 500)
            oth = [k for k in M.all_ids if k != b]
            Ot = cKDTree(np.vstack([S.pts[k][::2] for k in oth]))
            other_carp = np.vstack([S.pts[k][::2] for k in carp if k != b])
            nb = [(a if a != b else bb, d) for (a, bb), d in contacts.items() if b in (a, bb)]
            nbt = {k: cKDTree(S.pts[k][::2]) for k, _ in nb if k in S.pts}

            def sim(x, Q):
                return x[6] * Rot.from_rotvec(x[:3]).apply(Q - c) + c + x[3:6]

            def obj(x, ret_parts=False):
                A = sim(x, Ps)
                coll = float(np.maximum(0.0, 1.5 - Ot.query(A)[0]).mean()) * 4.0
                cont = 0.0
                for k, d0 in nb:
                    if k in nbt:
                        cont += max(0.0, float(nbt[k].query(A)[0].min()) - max(1.5, d0 + 1.0)) ** 2
                U = np.vstack([other_carp, A])
                cov = float(np.minimum(cKDTree(U).query(E_g)[0], 3.0).mean())
                return _score(A, Et) + 0.8 * cov + coll + 0.6 * cont + env.pen(A) + 3.0 * float((x[:3] ** 2).sum()) + 15.0 * (x[6] - 1.0) ** 2

            x0 = np.r_[np.zeros(6), 1.0]
            f0 = obj(x0)
            r = minimize(obj, x0, method="Powell", bounds=[(-0.35, 0.35)] * 3 + [(-8, 8)] * 3 + [(0.96, 1.04)], options={"xtol": 1e-3, "ftol": 1e-6, "maxiter": 1500})
            if r.fun < f0 - 0.1:
                s0, s1 = _score(P, Et), _score(sim(r.x, P), Et)
                S.move([b], lambda Q, x=r.x, c=c: sim(x, Q))
                rep[b] = {"evidence_score_before": round(s0, 2), "evidence_score_after": round(s1, 2), "turn_deg": round(float(np.degrees(np.linalg.norm(r.x[:3]))), 1),
                          "shift_mm": round(float(np.linalg.norm(r.x[3:6])), 1), "scale": round(float(r.x[6]), 3), "objective": [round(f0, 2), round(float(r.fun), 2)]}
                log(f"  Q205 carpal {nm}: objective {f0:.2f} -> {r.fun:.2f}; evidence score {s0:.2f} -> {s1:.2f}, turn {rep[b]['turn_deg']} deg, shift {rep[b]['shift_mm']} mm, scale {rep[b]['scale']}")
    net = {b: kabsch(v_start[b], S.v[b], scale=False) for b in carp}
    return rep, net


def follow_rays(H, M, S, net, contacts, log=print):
    """every ray (metacarpal + phalanges) moves with the carpal it articulates with (the Z-source carpometacarpal contact with the smallest source distance): the CMC joints stay closed"""
    from scripts.zanatomy.q191_hand import apply_T
    rep = {}
    for o in ("first", "second", "third", "fourth", "fifth"):
        mc = M.mc(o)
        cand = [(d, (a if a != mc else b)) for (a, b), d in contacts.items() if mc in (a, b) and (a if a != mc else b) in net]
        if not cand:
            continue
        d, c = min(cand)
        T = net[c]
        for b in [mc] + M.phal(o):
            S.pts[b] = apply_T(T, S.pts[b])
            S.v[b] = apply_T(T, S.v[b])
        rep[o] = {"follows": c[4:], "source_distance_mm": round(d, 2)}
    return rep


def thumb_beam(H, M, S, ev, env, log=print):
    """thumb: reseat the phalanges on the metacarpal (Z-source posture), then the evidence-scored articulated search CMC -> MCP -> IP over the evidence that no other Z hand bone explains"""
    bs = [M.mc("first")] + M.phal("first")
    sfx = "_" + M.side
    trap = S.pts[f"zan_trapezium_bone{sfx}"].mean(0)
    P = [S.pts[b] for b in bs]
    cs, prev = [], trap
    for p in P:
        cs.append(H.joint_point(p, prev))
        prev = p.mean(0)
    others = np.vstack([S.pts[b][::2] for b in M.all_ids if b not in bs])
    Ot = cKDTree(others)
    free = ev[Ot.query(ev)[0] > 2.0]
    near = free[np.linalg.norm(free - cs[0], axis=1) < 140.0]
    Et = cKDTree(near)
    log(f"  Q205 thumb: {len(near)} evidence voxels of the {len(ev)} are not explained by another Z bone and lie within 140 mm of the CMC joint")
    X, XV, rep = beam_chain(H, M, S, bs, cs, Et, Ot, env, max_deg=(75.0, 100.0, 90.0), log=log, label="thumb")
    for b, x, xv in zip(bs, X, XV):
        S.pts[b], S.v[b] = x, xv
    rep["evidence_voxels_free"] = int(len(near))
    rep["thumb_bones_evidence_score"] = {b[4:-2]: round(_score(S.pts[b], Et), 2) for b in bs}
    return rep


def restore_state(H, M, S, V):
    for i, v in V.items():
        if i in S.v:
            S.v[i] = np.asarray(v, float)
            S.pts[i] = H.interior(S.v[i], M.f[i], 0.9)


def refine_rays(H, M, S, evh, env, log=print):
    """metacarpals 2-5 (turn about their carpal end, <= 0.3 rad) and phalanx chains 2-5 (Q192 hinges) on the evidence; a ray's new pose is kept only when the mean evidence score of its bones gains"""
    Et = cKDTree(evh)
    rep = {}
    cap, Hh, d, t = H.hand_frame(M, S)
    for o in ("fifth", "fourth", "third", "second"):
        chain = [M.mc(o)] + M.phal(o)
        sc0 = np.mean([bone_score(S, b, Et) for b in chain])
        snap = {b: (S.v[b].copy(), S.pts[b].copy()) for b in chain}
        r1 = fit_mc(H, M, S, o, evh, env, log=log)
        bs, X, XV, r2 = H.fit_ray(M, S, o, evh, env, t, Hh, log=log)
        for b, x, xv in zip(bs, X, XV):
            S.pts[b], S.v[b] = x, xv
        sc1 = np.mean([bone_score(S, b, Et) for b in chain])
        if sc1 > sc0 - 0.1:
            for b, (v, p) in snap.items():
                S.v[b], S.pts[b] = v, p
            rep[o] = {"kept": "current pose", "evidence_score": [round(float(sc0), 2), round(float(sc1), 2)]}
        else:
            rep[o] = {"kept": "refit", "evidence_score": [round(float(sc0), 2), round(float(sc1), 2)], "metacarpal": r1, "chain": r2}
        log(f"  Q205 ray {o}: evidence score {sc0:.2f} -> {sc1:.2f}: {rep[o]['kept']}")
    return rep


# ------------------------------------------------------------------------------------------------ v3: the hand as the Z-source arrangement on HIS forearm, turned about the wrist
def forearm_given_pose(H, M, S, log=print):
    """carpals / metacarpals / phalanges = the Z-SOURCE hand attached to his forearm: one similarity from the raw distal radius + ulna (distal 80 mm) to their current (Q201) positions, applied
    to every raw hand bone.  The wrist contacts (forearm bones -> carpals) and every joint of the Z source then hold exactly (source congruence); evidence moves the hand from there"""
    from scripts.zanatomy.q191_hand import kabsch, apply_T
    pts_r, pts_v = [], []
    for k in (M.rad, M.uln):
        r = M.r[k]
        # distal end = the end toward the hand: lowest along the forearm axis (the hand centroid side)
        hc = np.vstack([M.r[b] for b in M.hand_ids]).mean(0)
        d = np.linalg.norm(r - hc, axis=1)
        sel = d < np.sort(d)[int(0.35 * len(d))]
        pts_r.append(r[sel])
        pts_v.append(S.v[k][sel])
    T = kabsch(np.vstack(pts_r), np.vstack(pts_v), scale=True)
    for b in M.hand_ids:
        newv = apply_T(T, M.r[b])
        Tb = kabsch(S.v[b], newv, scale=True)
        S.pts[b] = apply_T(Tb, S.pts[b])
        S.v[b] = newv
    log(f"  Q205 hand = Z-source arrangement on his forearm (similarity scale {T[0]:.3f})")
    return {"forearm_similarity_scale": round(float(T[0]), 4)}


def fit_hand_global(H, M, S, evh, env, n_rot=2500, cone_deg=65.0, log=print):
    """the carpal + metacarpal 2-5 block turned about the wrist (lunate centroid): global sampling of rotations within the cone (no local optimum, no roll ambiguity beyond the cone), scored by the
    one-way evidence distance of the block + the coverage of the evidence near it + collision with radius / ulna + skin; top 8 polished by Powell with a bounded shift / scale"""
    from scipy.optimize import minimize
    from scipy.spatial.transform import Rotation as Rot
    ids = list(M.ids["carpals"]) + M.ids["mc"][1:]
    block = np.vstack([S.pts[k] for k in ids])
    c0 = S.pts[f"zan_lunate_bone_{M.side}"].mean(0)
    rng = np.random.default_rng(0)
    Zs = block[rng.choice(len(block), min(2000, len(block)), replace=False)]
    Ew = evh[np.linalg.norm(evh - block.mean(0), axis=1) < 75.0]
    Et = cKDTree(Ew)
    FA = cKDTree(np.vstack([S.pts[M.rad][::3], S.pts[M.uln][::3]]))

    def Jx(x, P=Zs):
        A = Rot.from_rotvec(x[:3]).apply(P - c0) * x[6] + c0 + x[3:6]
        cov = np.minimum(cKDTree(A).query(Ew)[0], 3.0).mean()
        coll = float(np.maximum(0.0, 1.5 - FA.query(A)[0]).mean()) * 4.0
        return float(np.minimum(Et.query(A)[0], 4.0).mean() + 0.8 * cov + coll + env.pen(A))

    J0 = Jx(np.r_[np.zeros(6), 1.0])
    rv = Rot.random(n_rot * 4, random_state=7).as_rotvec()
    rv = rv[np.linalg.norm(rv, axis=1) <= np.radians(cone_deg)][:n_rot]
    res = sorted(((Jx(np.r_[r, 0, 0, 0, 1.0]), r) for r in rv), key=lambda t: t[0])
    out = []
    for f, r in res[:8]:
        o = minimize(Jx, np.r_[r, 0, 0, 0, 1.0], method="Powell", bounds=[(-1.2, 1.2)] * 3 + [(-8, 8)] * 3 + [(0.96, 1.04)], options={"xtol": 1e-3, "ftol": 1e-6, "maxiter": 2000})
        out.append((float(o.fun), o.x))
    out.sort(key=lambda t: t[0])
    f, x = out[0]
    nxt = next(((round(f2, 2), round(float(np.degrees(np.linalg.norm(x2[:3] - x[:3]))), 0)) for f2, x2 in out[1:] if np.degrees(np.linalg.norm(x2[:3] - x[:3])) > 8.0), None)
    R = Rot.from_rotvec(x[:3])
    allhand = [k for k in M.hand_ids if "phalan" not in k and k != M.mc("first")] + [b for o in ("second", "third", "fourth", "fifth") for b in M.phal(o)] + M.phal("first") + [M.mc("first")]
    S.move(allhand, lambda P: R.apply(P - c0) * x[6] + c0 + x[3:6])
    log(f"  Q205 hand block: J {J0:.2f} -> {f:.2f}; turn {np.degrees(np.linalg.norm(x[:3])):.0f} deg about the wrist, shift {np.linalg.norm(x[3:6]):.1f} mm, scale {x[6]:.3f}; next distinct optimum {nxt}")
    return {"J_forearm_given": round(J0, 3), "J": round(f, 3), "turn_deg": round(float(np.degrees(np.linalg.norm(x[:3]))), 1), "shift_mm": [round(float(a), 1) for a in x[3:6]], "scale": round(float(x[6]), 4),
            "next_distinct_optimum_J_and_turn_difference_deg": nxt, "wrist_centre": [round(float(a), 1) for a in c0]}


def save_fit(M, S, rep, side, out_dir=None):
    out_dir = Path(out_dir or REPO / "data" / "derived")
    arrs = {f"v_{i}": S.v[i].astype(np.float32) for i in M.hand_ids}
    np.savez_compressed(out_dir / f"Q205_hand_bones_{side}.npz", **arrs)
    (out_dir / f"Q205_hand_fit_{side}.json").write_text(json.dumps(rep, indent=1, default=float))


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("side", choices=["r", "l"])
    ap.add_argument("--polish", action="store_true", help="second pass on the saved fit")
    ap.add_argument("--state", default=str(REPO / "build" / "q201" / "after_q201.npz"))
    a = ap.parse_args(argv)
    from scripts.zanatomy import body_ctx
    body_ctx.configure("vhm")
    from scripts.zanatomy import q190_metrics as Mx
    from scripts.ribs_from_ct_labels import load_skin
    by = {d["id"]: d for d in Mx.load_dump(a.state)}
    if a.polish:
        M, S, rep = polish(by, a.side, load_skin("vhm"))
        arrs = {f"v_{i}": S.v[i].astype(np.float32) for i in M.hand_ids}
        np.savez_compressed(REPO / "data" / "derived" / f"Q205_hand_bones_{a.side}.npz", **arrs)
        (REPO / "data" / "derived" / f"Q205_hand_polish_{a.side}.json").write_text(json.dumps(rep, indent=1, default=float))
        print("polished", a.side, rep["seconds"], "s")
        return
    M, S, rep = fit_side(by, a.side, load_skin("vhm"))
    save_fit(M, S, rep, a.side)
    print("done", a.side, rep["seconds"], "s")



# ------------------------------------------------------------------------------------------------ soft tissue
def refine_soft(by, raw, side, bone_v, skin, skin_tree, skin_vn, regions, his, log=print):
    """the Q191 / Q195 carry for one hand with the NEW bones: bone-anchored field from the Z source (per-bone similarity maps, forearm bones as anchors), up to four candidate placements per
    structure with his skin / bone / stretch / fold / volume guards, hand skin onto his CT skin, labelled intrinsics onto his labels.  `bone_v` = {id: new vertices}"""
    from scripts.zanatomy import q191_hand as H191
    raw = {k: np.asarray(v, float) for k, v in raw.items()}
    T = {i: H191.kabsch(raw[i], bone_v[i], scale=True) for i in bone_v}
    rep = H191.run_side(side, by, raw, regions, his, skin, skin_tree, skin_vn, {i: np.asarray(v, float) for i, v in bone_v.items()}, T, log=log)
    return rep


def hand_note(i, r):
    from scripts.zanatomy import q191_hand as H191
    t = H191._note(i, r).replace(" Q191 (hand/wrist refit onto her own CT hand)", " Q205 (hand soft tissue re-carried by the per-bone chain fit of his hand bones on his CT / photographs)", 1)
    for a, b in ((" outside her skin", " outside his skin"), ("inside her CT", "inside his CT"), ("onto her own", "onto his own"), (" her ", " his ")):
        t = t.replace(a, b)
    return t


def beam_ray(H, M, S, o, evh, env, log=print):
    """a ray whose hinge fit left the bones off the evidence (mean score > 1.5): its three phalanges re-searched as an articulated chain (MCP / PIP / DIP, 3 DOF each, <= 110 / 110 / 90 deg)
    about the joints of their CURRENT pose over the evidence no other Z hand bone explains; kept only if the mean score gains >= 0.3"""
    bs = M.phal(o)
    Et_all = cKDTree(evh)
    sc0 = np.mean([bone_score(S, b, Et_all) for b in bs])
    snap = {b: (S.v[b].copy(), S.pts[b].copy()) for b in bs}
    mc = S.pts[M.mc(o)]
    cs, prev = [], mc.mean(0)
    for b in bs:
        cs.append(H.joint_point(S.pts[b], prev))
        prev = S.pts[b].mean(0)
    others = np.vstack([S.pts[b][::2] for b in M.all_ids if b not in bs])
    Ot = cKDTree(others)
    free = evh[Ot.query(evh)[0] > 2.0]
    near = free[np.linalg.norm(free - cs[0], axis=1) < 120.0]
    Et = cKDTree(near)
    X, XV, r = beam_chain(H, M, S, bs, cs, Et, Ot, env, max_deg=(110.0, 110.0, 90.0), log=log, label=f"ray {o}")
    for b, x, xv in zip(bs, X, XV):
        S.pts[b], S.v[b] = x, xv
    sc1 = np.mean([bone_score(S, b, Et_all) for b in bs])
    if sc1 > sc0 - 0.3:
        for b, (v, p) in snap.items():
            S.v[b], S.pts[b] = v, p
        return {"kept": "current pose", "evidence_score": [round(float(sc0), 2), round(float(sc1), 2)]}
    return {"kept": "beam refit", "evidence_score": [round(float(sc0), 2), round(float(sc1), 2)], **r}


def polish(by, side, skin, log=print):
    """second pass on the saved fit (Q205_hand_bones_<side>.npz): the pisiform alone (the global block fit leaves it off; no joint with a metacarpal).  Tried and dropped: refitting every carpal with the rays following
    (evidence agreement 80.9 -> 70.7 %: the thumb chain, fitted on the block pose, lost its place) and an articulated re-search of the second ray (no gain)"""
    H = _setup()
    t0 = time.time()
    ev = load_evidence(side)
    env = HisEnvelope(skin, side)
    M = H.HandModel(by, side)
    S = H.State(M)
    z = np.load(REPO / "data" / "derived" / f"Q205_hand_bones_{side}.npz")
    restore_state(H, M, S, {k[2:]: z[k] for k in z.files})
    evh = H.clean_hand_evidence(M, S, ev, y_max=1e9)
    Et = cKDTree(evh)
    rep = {}
    contacts = source_contacts(M, M.hand_ids + [M.rad, M.uln])
    rep["carpals"], net = fit_carpals(H, M, S, evh, Et, env, contacts, log=log, rounds=1, only=("pisiform",))      # the pisiform has no joint with a metacarpal: refit alone (the other carpals keep the block fit, their rays follow them)
    rep["evidence_after"] = H.evidence_fit(M, S, evh)
    rep["bone_evidence_score_after"] = {b[4:]: round(bone_score(S, b, Et), 2) for b in M.hand_ids}
    rep["thumb_gap_after_mm"] = round(thumb_gap(S, M), 3)
    rep["seconds"] = round(time.time() - t0)
    return M, S, rep


if __name__ == "__main__":
    main()
