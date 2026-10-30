"""Q250: the FEMALE target skeleton for the Base page, in the Z-Anatomy page frame, from
  (1) Combined · Female (the 250 Z-Anatomy bones similarity-fitted, bone by bone, to the Visible Human female's own CT skeleton; her frame),
  (2) a female pelvic ring (her own CT pelvis, or a mean of adult women: see pelvis_reg.py),
and the rule "shape and proportion from the woman, pose from Z-Anatomy":
  * trunk / head / girdle bones: Z bone -> her bone (similarity), expressed in the Z frame by one rigid transform G (her frame -> Z frame, no scale);
  * limb bones: Z ORIENTATION kept (standard anatomical pose, not her supine cadaver pose), each limb segment scaled by HER bone-length ratio and chained joint to joint
    (hip / shoulder anchored at HER joint centre): F_seg(x) = Q_parent' + s_seg (x - Q_joint);
  * pelvis (hip bones, sacrum, coccyx): non-rigid registration onto the female ring (pelvis_reg);
  * left / right symmetrised (the Z-Anatomy skeleton is exactly mirror-symmetric, hers is not: pose and asymmetry are not wanted in a generic base).
Output: per-bone target vertices (same vertex order as the Z bones) + report."""
from __future__ import annotations
import re
import numpy as np
from scipy.spatial import cKDTree
from scripts.anatomy.q250 import lib as L
from scripts.anatomy.q233 import dimorphism as D

CARPAL = ("capitate", "hamate", "lunate", "pisiform", "scaphoid", "trapezium", "trapezoid", "triquetrum")


def seg_of(i):
    """-> (limb, side, segment) or None for the axial skeleton"""
    m = re.search(r"_([lr])$", i)
    if not m:
        return None
    sd = m.group(1); b = i[:-2]
    if b in ("femur", "patella"):
        return ("leg", sd, "thigh")
    if b in ("tibia", "fibula"):
        return ("leg", sd, "shank")
    if b in ("calcaneus", "talus", "navicular", "cuboid") or b.startswith("cuneiform") or b.endswith("_of_foot") or "metatarsal" in b:
        return ("leg", sd, "foot")
    if b == "humerus":
        return ("arm", sd, "upper")
    if b in ("radius", "ulna"):
        return ("arm", sd, "fore")
    if b.endswith("_of_hand") or "metacarpal" in b or any(b == f"zan_{c}_bone" for c in CARPAL):
        return ("arm", sd, "hand")
    return None


def sim_homologous(Zv, Cv, tol=0.6):
    if len(Zv) != len(Cv):
        return None
    s, R, t = L.umeyama(Zv, Cv)
    res = np.linalg.norm(s * Zv @ R.T + t - Cv, axis=1)
    return (s, R, t, float(res.mean())) if res.mean() < tol else None


def end_centroid(v, ax, frac, top):
    """centroid of the `frac` fraction of vertices at one end along unit axis ax"""
    tt = v @ ax
    k = max(8, int(len(v) * frac))
    idx = np.argsort(tt)[-k:] if top else np.argsort(tt)[:k]
    return v[idx].mean(0)


def long_axis(v):
    ax = np.linalg.svd(v - v.mean(0), full_matrices=False)[2][0]
    return ax if ax[1] > 0 else -ax          # +Y = superior = proximal for the legs and (in the Z pose) the arms


def joint_points(Z):
    """Z-frame joint points (dict[(limb, side)] -> dict) from the Z bones themselves"""
    out = {}
    Sl = [dict(id=i, sys="bone", v=e["v"], f=e["f"]) for i, e in Z.items() if i in ("femur_l", "femur_r")]
    for sd in "lr":
        fe, ti, fi, ta = (Z[f"{n}_{sd}"]["v"] for n in ("femur", "tibia", "fibula", "talus"))
        hip = np.array(D.femur_metrics(Sl, sd)["head_centre"])
        axf, axt = long_axis(fe), long_axis(ti)
        knee = 0.5 * (end_centroid(fe, axf, 0.05, False) + end_centroid(ti, axt, 0.05, True))
        ankle = 0.5 * (end_centroid(ti, axt, 0.04, False) + ta.mean(0))
        hu, ra, ul = Z[f"humerus_{sd}"]["v"], Z[f"radius_{sd}"]["v"], Z[f"ulna_{sd}"]["v"]
        axh = long_axis(hu)
        top = hu[hu @ axh > (hu @ axh).max() - 30]
        med = top[top[:, 0] < np.median(hu[:, 0])] if sd == "r" else top[top[:, 0] > np.median(hu[:, 0])]
        c, r, _ = D.fit_sphere(med[np.abs(med[:, 0] - (med[:, 0].min() if sd == "r" else med[:, 0].max())) < 22])
        sh = np.array(c)
        elbow = 0.5 * (end_centroid(hu, axh, 0.05, False) + end_centroid(ul, long_axis(ul), 0.06, True))
        car = np.mean([Z[f"zan_{c_}_bone_{sd}"]["v"].mean(0) for c_ in ("scaphoid", "lunate", "triquetrum")], 0)
        wrist = 0.5 * (end_centroid(ra, long_axis(ra), 0.05, False) + car)
        out[sd] = dict(hip=hip, knee=knee, ankle=ankle, shoulder=sh, elbow=elbow, wrist=wrist)
    return out


def rigid_g(Z, C, ids):
    A = np.array([C[i]["v"].mean(0) for i in ids]); B = np.array([Z[i]["v"].mean(0) for i in ids])
    s, R, t = L.umeyama(A, B, scale=False)
    res = np.linalg.norm(A @ R.T + t - B, axis=1)
    return R, t, res


def build(Z, C, ring_target_fn=None, trunk_smoothing=1.0e4, ring_ids=("hip_bone_l", "hip_bone_r", "sacrum", "coccyx")):
    """Z, C: decoded pages (id -> dict(v, f, m)). ring_target_fn(G) -> {id: target vertices} in the Z frame for the pelvic ring (None: ring kept as the
    similarity fit to hers). Returns dict(target={id: V'}, report=...)"""
    axial = [i for i in Z if Z[i]["m"]["sys"] == "bone" and i in C and (i.startswith(("zan_vertebra", "zan_atlas", "zan_axis")) or i.endswith("_rib_l") or i.endswith("_rib_r")
                                                                          or i in ("sternum", "frontal", "occipital", "clavicle_l", "clavicle_r", "hip_bone_l", "hip_bone_r", "sacrum"))]
    R0, t0, res0 = rigid_g(Z, C, axial)
    # her frame -> Z frame, no scale:  x_Z = R0 x_her + t0 ;  trimmed re-fit
    keep = res0 < np.quantile(res0, 0.85)
    R0, t0, res1 = rigid_g(Z, C, [a for a, k in zip(axial, keep) if k])
    G = lambda p: p @ R0.T + t0  # noqa: E731
    rep = dict(G_rotation_deg=round(float(np.degrees(np.arccos(np.clip((np.trace(R0) - 1) / 2, -1, 1)))), 2), G_translation_mm=t0.round(1).tolist(),
               G_fit_axial_bone_centroids_median_mm=round(float(np.median(res1)), 1), per_bone={})
    T0, sc, kind = {}, {}, {}
    for i, e in Z.items():
        if e["m"]["sys"] != "bone" or i not in C:
            continue
        h = sim_homologous(e["v"], C[i]["v"])
        if h is not None:
            s, R, t, r = h
            kind[i] = "similarity"
        else:
            s, R, t, d = L.icp_sim(e["v"][::max(1, len(e["v"]) // 1500)], C[i]["v"], iters=80, trim=0.9)
            kind[i] = "icp_similarity"
        T0[i] = (s, R, t); sc[i] = s
    # target 0 (her pose, Z frame): trunk, head, girdle bones (limb bones are rebuilt below in the Z pose)
    tgt = {i: G(s * Z[i]["v"] @ R.T + t) for i, (s, R, t) in T0.items() if seg_of(i) is None}
    if ring_target_fn is not None:
        for i, v in ring_target_fn(G).items():
            tgt[i] = v; kind[i] = "nonrigid_ring"
    # --- left / right symmetrisation of the displacement field (Z is mirror-symmetric)
    ids = list(tgt)
    allZ = np.vstack([Z[i]["v"] for i in ids]); allU = np.vstack([tgt[i] - Z[i]["v"] for i in ids])
    tree = cKDTree(allZ)
    d, j = tree.query(L.mirror(allZ))
    Us = 0.5 * (allU + allU[j] * np.array([-1, 1, 1]))
    rep["mirror_nn_median_mm"] = round(float(np.median(d)), 3)
    Usd, off = {}, 0
    for i in ids:
        n = len(Z[i]["v"]); Usd[i] = Us[off:off + n]; off += n
    # --- trunk / head / girdle: one SMOOTH field through the per-bone targets (her per-bone fits jitter: a vertebra-by-vertebra similarity of a woman's CT has +-10 deg ICP rotations and
    #     6-10 % scale steps between neighbours, which would tear the discs / intercostal tissue); each bone is then the similarity image of its Z bone under the smooth field
    trunk = [i for i in ids if kind[i] != "nonrigid_ring"]
    rng = np.random.default_rng(0)
    P, U = [], []
    for i in trunk:
        n = len(Z[i]["v"]); k = min(n, max(10, n // 25)); idx = rng.choice(n, k, replace=False)
        P.append(Z[i]["v"][idx]); U.append(Usd[i][idx])
    P = np.vstack(P); U = np.vstack(U)
    ftrunk = L.TPS(P, U, smoothing=trunk_smoothing)
    res = np.linalg.norm(ftrunk(P) - U, axis=1)
    rep["trunk_field"] = dict(smoothing=trunk_smoothing, control_points=int(len(P)), residual_to_her_per_bone_fit_median_mm=round(float(np.median(res)), 2), p95_mm=round(float(np.quantile(res, .95)), 1))
    out = {}
    for i in trunk:
        V0 = Z[i]["v"]; s_, R_, t_ = L.umeyama(V0, V0 + ftrunk(V0)); V = s_ * V0 @ R_.T + t_
        out[i] = V
        s2, R2, t2 = L.umeyama(V0, V)
        rep["per_bone"][i] = dict(kind=kind[i], scale=round(float(s2), 4), rot_deg=round(float(np.degrees(np.arccos(np.clip((np.trace(R2) - 1) / 2, -1, 1)))), 1),
                                  shift_mm=round(float(np.linalg.norm(V.mean(0) - V0.mean(0))), 1))
    ringV = {i: Z[i]["v"] + Usd[i] for i in ids if kind[i] == "nonrigid_ring"}
    out.update(ringV)
    # --- limbs: Z orientation, her segment scales, joint-to-joint chain; anchored where the bone they articulate with has gone: shoulder = Z joint + smooth trunk field (the scapula / clavicle follow it),
    #     hip = Z joint + displacement of the registered pelvis around the acetabulum (the femoral head stays in the deformed acetabulum)
    JP = joint_points(Z)
    seg_scale = {}
    MAIN = {("leg", "thigh"): ("femur",), ("leg", "shank"): ("tibia", "fibula"), ("leg", "foot"): ("calcaneus", "talus"), ("arm", "upper"): ("humerus",),
            ("arm", "fore"): ("radius", "ulna"), ("arm", "hand"): ("zan_second_metacarpal_bone", "zan_third_metacarpal_bone", "zan_capitate_bone")}
    for (lb, sg), names in MAIN.items():
        vals = [sc[f"{n}_{sd}"] for n in names for sd in "lr" if f"{n}_{sd}" in sc]
        seg_scale[(lb, sg)] = float(np.median(vals))
    rep["segment_scale_from_her"] = {f"{a}_{b}": round(v, 4) for (a, b), v in seg_scale.items()}
    rv = np.vstack([Z[i]["v"] for i in ringV]); ru = np.vstack([Usd[i] for i in ringV])
    anchors = {}
    for sd in "lr":
        j_ = JP[sd]
        w = np.exp(-((rv - j_["hip"]) ** 2).sum(1) / (2 * 15.0 ** 2)); anchors[("leg", sd)] = j_["hip"] + (w[:, None] * ru).sum(0) / w.sum()
        anchors[("arm", sd)] = j_["shoulder"] + ftrunk(j_["shoulder"][None])[0]
    F = {}
    for sd in "lr":
        j_ = JP[sd]
        s1, s2, s3 = (seg_scale[("leg", k)] for k in ("thigh", "shank", "foot"))
        Hp = anchors[("leg", sd)]; Kp = Hp + s1 * (j_["knee"] - j_["hip"]); Ap = Kp + s2 * (j_["ankle"] - j_["knee"])
        F[("leg", sd, "thigh")] = (s1, j_["hip"], Hp); F[("leg", sd, "shank")] = (s2, j_["knee"], Kp); F[("leg", sd, "foot")] = (s3, j_["ankle"], Ap)
        s1, s2, s3 = (seg_scale[("arm", k)] for k in ("upper", "fore", "hand"))
        Sp = anchors[("arm", sd)]; Ep = Sp + s1 * (j_["elbow"] - j_["shoulder"]); Wp = Ep + s2 * (j_["wrist"] - j_["elbow"])
        F[("arm", sd, "upper")] = (s1, j_["shoulder"], Sp); F[("arm", sd, "fore")] = (s2, j_["elbow"], Ep); F[("arm", sd, "hand")] = (s3, j_["wrist"], Wp)
    for i, e in Z.items():
        sg = seg_of(i) if e["m"]["sys"] == "bone" else None
        if sg and i in C:
            s_, Q, Qp = F[sg]
            out[i] = Qp + s_ * (e["v"] - Q)
            rep["per_bone"][i] = dict(kind="limb_chain", scale=round(float(s_), 4), rot_deg=0.0, shift_mm=round(float(np.linalg.norm(out[i].mean(0) - e["v"].mean(0))), 1))
    rep["joint_points_Z_mm"] = {sd: {k: v.round(1).tolist() for k, v in JP[sd].items()} for sd in JP}
    rep["joint_targets_mm"] = {f"{k[0]}_{k[1]}_{k[2]}": dict(scale=round(v[0], 4), anchor_Z=v[1].round(1).tolist(), anchor_target=v[2].round(1).tolist()) for k, v in F.items()}
    kind.update({i: "limb_chain" for i in out if seg_of(i) and i not in ringV})
    # --- final exact left / right symmetry of every bone target (the smooth field was fitted on random control samples, which are not mirror pairs): average each vertex with the mirror of its
    #     mirror-partner vertex, then re-fit the similarity of the rigid bones (pelvic ring stays non-rigid)
    bid = list(out)
    allZ = np.vstack([Z[i]["v"] for i in bid]); allT = np.vstack([out[i] for i in bid])
    d, j = cKDTree(allZ).query(L.mirror(allZ))
    Ts = 0.5 * (allT + L.mirror(allT[j])); off = 0
    asym0 = np.linalg.norm(allT - L.mirror(allT[j]), axis=1)
    for i in bid:
        n = len(Z[i]["v"]); V = Ts[off:off + n]; off += n
        if kind.get(i) != "nonrigid_ring":
            s_, R_, t_ = L.umeyama(Z[i]["v"], V); V = s_ * Z[i]["v"] @ R_.T + t_
        out[i] = V
    allT2 = np.vstack([out[i] for i in bid])
    rep["left_right_symmetry_mm"] = dict(before_median=round(float(np.median(asym0)), 2), before_max=round(float(asym0.max()), 1), after_median=round(float(np.median(np.linalg.norm(allT2 - L.mirror(allT2[j]), axis=1))), 3),
                                         after_max=round(float(np.linalg.norm(allT2 - L.mirror(allT2[j]), axis=1).max()), 2))
    return dict(target=out, report=rep, G=(R0, t0), kind=kind)
