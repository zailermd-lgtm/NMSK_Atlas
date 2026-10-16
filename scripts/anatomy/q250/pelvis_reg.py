"""Q250: non-rigid registration of the Z-Anatomy pelvic ring (hip bones, sacrum, coccyx; male-derived shape) onto a FEMALE target pelvic ring (point cloud), so that the Z bones keep their
anatomy / vertex topology (muscle attachments) but take the female shape. Similarity ICP, then coherent point drift (non-rigid, smooth), then a residual report.

    ring = {'hip_bone_l': (v, f), 'hip_bone_r': ..., 'sacrum': ..., 'coccyx': ...}   (Z page frame)
    target = (N,3) points on the female pelvis (same frame)
    res = register(ring, target) -> dict(v={id: warped vertices}, field=(Xc, W, beta, sim), report=...)
"""
from __future__ import annotations
import numpy as np
from scipy.spatial import cKDTree
from scripts.anatomy.q250 import lib as L


def ring_points(ring, n_per=1500, seed=0, skip=()):
    P, owner = [], []
    for k, (v, f) in ring.items():
        if k in skip:
            continue
        p, _ = L.sample(v, f, n_per if len(v) < 6000 else 2 * n_per, seed)
        P.append(p); owner += [k] * len(p)
    return np.vstack(P), np.array(owner)


def landmarks(ring):
    """21 geometric landmarks of a pelvic ring {hip_bone_l, hip_bone_r, sacrum, coccyx: (v, f)} (atlas frame, +X right): found by the same simple extreme-point rules on the Z ring and on
    the female target ring, so they are homologous by rule (not hand-placed): per hip bone ischial tuberosity (lowest), iliac crest top (highest), iliac wing lateral extreme, ASIS-like
    (most anterior point of the upper 45 %), PSIS-like (most posterior of the upper 45 %), pubic symphysis upper / lower (medial extremes of the anterior-inferior part), acetabular
    rim point (most lateral point of the middle third); sacrum promontory, apex and the two lateral ala extremes; coccyx tip."""
    out = {}
    for k, sg in (("hip_bone_l", -1), ("hip_bone_r", 1)):
        v = ring[k][0]; sd = "l" if sg < 0 else "r"
        out["tub_" + sd] = v[np.argmin(v[:, 1])]
        out["crest_" + sd] = v[np.argmax(v[:, 1])]
        out["wing_" + sd] = v[np.argmax(sg * v[:, 0])]
        up = v[v[:, 1] > v[:, 1].min() + 0.55 * np.ptp(v[:, 1])]
        out["asis_" + sd] = up[np.argmax(up[:, 2])]
        out["psis_" + sd] = up[np.argmin(up[:, 2])]
        z_lim = v[:, 2].min() + 0.62 * np.ptp(v[:, 2])
        ant = v[(v[:, 2] > z_lim) & (v[:, 1] < v[:, 1].min() + 0.55 * np.ptp(v[:, 1]))]
        xmed = ant[np.argmin(sg * ant[:, 0])] if False else ant[np.argmin(np.abs(ant[:, 0]))]
        face = ant[np.abs(ant[:, 0] - xmed[0]) < 6.0]
        out["symU_" + sd] = face[np.argmax(face[:, 1])]
        out["symL_" + sd] = face[np.argmin(face[:, 1])]
        mid = v[(v[:, 1] > v[:, 1].min() + 0.33 * np.ptp(v[:, 1])) & (v[:, 1] < v[:, 1].min() + 0.66 * np.ptp(v[:, 1]))]
        out["acet_" + sd] = mid[np.argmax(sg * mid[:, 0])]
    if "sacrum" not in ring:
        return out
    sa = ring["sacrum"][0]
    mid = np.median(sa[:, 0])
    top = sa[sa[:, 1] > sa[:, 1].max() - 0.28 * np.ptp(sa[:, 1])]
    cen = top[np.abs(top[:, 0] - mid) < 14]
    out["promontory"] = cen[np.argmax(cen[:, 2])]
    out["apex"] = sa[np.abs(sa[:, 0] - mid) < 14][np.argmin(sa[np.abs(sa[:, 0] - mid) < 14][:, 1])]
    out["ala_l"] = top[np.argmin(top[:, 0])]; out["ala_r"] = top[np.argmax(top[:, 0])]
    if "coccyx" in ring:
        cc = ring["coccyx"][0]; out["coccyx_tip"] = cc[np.argmin(cc[:, 1])]
    return out


def landmark_prewarp(ring, target_ring):
    """thin-plate warp (exact at the landmarks, affine elsewhere) of the Z ring onto the female ring landmarks"""
    a, b = landmarks(ring), landmarks(target_ring)
    keys = sorted(set(a) & set(b))
    A = np.array([a[k] for k in keys]); B = np.array([b[k] for k in keys])
    f = L.TPS(A, B - A, smoothing=5.0)
    return f, dict(keys=keys, residual_before_mm=round(float(np.linalg.norm(A - B, axis=1).mean()), 1))


STABLE = ("symU_l", "symU_r", "symL_l", "symL_r", "tub_l", "tub_r")      # the extreme-point landmarks that stay well defined on a registered mesh (crest / wing / promontory picks jump by 20 mm)


def damp_sacrum(out, src, f=0.5, keys=("sacrum", "coccyx")):
    """sacrum / coccyx: the non-rigid fit of the sacrum is noisy (its surface is the least constrained of the ring): keep only a fraction f of the non-rigid part of the displacement on top of the best
    similarity fit of the starting bone to its registered positions (clean anatomy, still follows the target)"""
    res = dict(out)
    for k in keys:
        if k in out and k in src:
            s_, R_, t_ = L.umeyama(src[k], out[k])
            sim = s_ * src[k] @ R_.T + t_
            res[k] = sim + f * (out[k] - sim)
    return res


def landmark_snap(out, ring_faces, target_ring, smoothing=1.0, keys=None):
    """final correction: thin-plate warp (small smoothing) between the landmarks of the REGISTERED ring and the target landmarks, so that small but important contact surfaces (pubic symphysis faces,
    ischial tuberosities, ASIS) land on the target even though a coherent-point-drift fit averages them out. Returns the new vertices and the landmark residuals before / after."""
    ring = {k: (v, ring_faces[k]) for k, v in out.items() if k in ring_faces}
    a, b = landmarks(ring), landmarks(target_ring)
    keys = keys or STABLE
    ks = [k for k in sorted(set(a) & set(b)) if k in keys]
    A = np.array([a[k] for k in ks]); B = np.array([b[k] for k in ks])
    # anchors: ring vertices farther than 45 mm from every landmark stay where they are (a thin-plate warp through a few clustered landmarks would otherwise extrapolate wildly)
    allv = np.vstack(list(out.values())); rng = np.random.default_rng(0)
    far = allv[cKDTree(A).query(allv)[0] > 45.0]
    anc = far[rng.choice(len(far), min(500, len(far)), replace=False)] if len(far) else np.zeros((0, 3))
    f = L.TPS(np.vstack([A, anc]), np.vstack([B - A, np.zeros((len(anc), 3))]), smoothing=smoothing)
    new = {k: v + f(v) for k, v in out.items()}
    ring2 = {k: (new[k], ring_faces[k]) for k in new if k in ring_faces}
    a2 = landmarks(ring2)
    A2 = np.array([a2[k] for k in ks])
    return new, dict(landmarks=ks, residual_before_mm=round(float(np.linalg.norm(A - B, axis=1).mean()), 2), residual_after_mm=round(float(np.linalg.norm(A2 - B, axis=1).mean()), 2),
                     per_landmark_after_mm={k: round(float(np.linalg.norm(x - y)), 1) for k, x, y in zip(ks, A2, B)})


def close_symphysis(out, gap_target, sigma=30.0):
    """a non-rigid fit averages the small pubic symphysis faces: move the two pubic faces toward each other (smooth Gaussian falloff, sigma 30 mm) until their closest distance equals the target ring's
    (her symphyseal gap)."""
    l, r = out["hip_bone_l"], out["hip_bone_r"]
    d, j = cKDTree(r).query(l); i = int(np.argmin(d)); pl, pr = l[i], r[j[i]]
    gap = float(d[i]); u = (pr - pl) / max(gap, 1e-6)
    shift = max(gap - gap_target, 0.0) / 2.0
    res = dict(out)
    res["hip_bone_l"] = l + u * shift * np.exp(-((l - pl) ** 2).sum(1) / (2 * sigma ** 2))[:, None]
    res["hip_bone_r"] = r - u * shift * np.exp(-((r - pr) ** 2).sum(1) / (2 * sigma ** 2))[:, None]
    d2 = cKDTree(res["hip_bone_r"]).query(res["hip_bone_l"])[0].min()
    return res, dict(gap_before_mm=round(gap, 1), gap_target_mm=round(gap_target, 1), gap_after_mm=round(float(d2), 1), shift_each_mm=round(shift, 1))


def register(ring, target, beta=9.0, lam=0.4, iters=60, w=0.02, n_ctrl=2600, n_tgt=3400, seed=0, verbose=False, target_ring=None, refine=True, skip=(), init=None, placed=None, local_mm=75.0, snap=True, sacrum_damp=0.5):
    rng = np.random.default_rng(seed)
    allv = np.vstack([v for v, f in ring.values()])
    src_pts, _ = ring_points(ring, 1400, seed, skip)
    tgt = target[rng.choice(len(target), min(n_tgt, len(target)), replace=False)]
    if placed is not None:                       # every bone already placed on the target (piece-wise similarity): identity start, no ICP
        ring = {k: (placed[k], f) for k, (v, f) in ring.items()}
        src_pts, _ = ring_points(ring, 1400, seed, skip)
        s, R, t = 1.0, np.eye(3), np.zeros(3)
        d0 = cKDTree(target).query(src_pts)[0]
    elif init is not None:                         # coarse alignment given (e.g. from the homologous hip bones): similarity, then a short ICP polish with the scale fixed
        s, R, t = init
        s, R, t, d0 = L.icp_sim(src_pts, target, iters=15, trim=0.85, scale=False, init=(s, R, t))
    else:
        s, R, t, d0 = L.icp_sim(src_pts, target, iters=60, trim=0.85)
    sim = (s, R, t)
    X0 = s * src_pts @ R.T + t
    pre, pre_rep = None, None
    ring1 = {k: (s * v @ R.T + t, f) for k, (v, f) in ring.items()}
    if target_ring is not None:
        pre, pre_rep = landmark_prewarp(ring1, target_ring)
        X0 = X0 + pre(X0)
    stages = []                                   # [(Xc, W, beta)] applied in sequence
    cur = X0
    for (bt, lm, it_, nc) in ((beta, lam, iters, n_ctrl), (beta / 2.2, lam / 2.5, max(30, iters // 2), int(n_ctrl * 1.25))):
        if bt < 5.5 and not refine:
            break
        sel = rng.choice(len(cur), min(nc, len(cur)), replace=False)
        Xc = cur[sel]
        W, b = L.cpd_nonrigid(Xc, tgt, beta=bt, lam=lm, iters=it_, w=w, verbose=verbose)
        stages.append((Xc, W, b))
        cur = L.cpd_apply(Xc, W, b, cur)
        if not refine:
            break
    if local_mm:                                  # last stage: the inferior pelvis (ischiopubic rami, tuberosities, pubic arch) alone, narrow kernel, so the subpubic arch is not smoothed away
        ymin = float(target[:, 1].min())
        mc = cur[:, 1] < ymin + local_mm; mt = target[:, 1] < ymin + local_mm
        if mc.sum() > 200 and mt.sum() > 200:
            tl = target[mt]; tl = tl[rng.choice(len(tl), min(2400, len(tl)), replace=False)]
            Xc = cur[mc]; Xc = Xc[rng.choice(len(Xc), min(900, len(Xc)), replace=False)]
            W, b = L.cpd_nonrigid(Xc, tl, beta=5.0, lam=0.25, iters=40, w=w, verbose=verbose)
            stages.append((Xc, W, b)); cur = L.cpd_apply(Xc, W, b, cur)
    out, rep = {}, {}
    ttree = cKDTree(target)
    for k, (v, f) in ring.items():
        v1 = s * v @ R.T + t
        if pre is not None:
            v1 = v1 + pre(v1)
        v2 = v1
        for Xc, W, b in stages:
            v2 = L.cpd_apply(Xc, W, b, v2)
        out[k] = v2
        d = ttree.query(v2)[0]
        rep[k] = dict(median_mm=round(float(np.median(d)), 2), p90_mm=round(float(np.quantile(d, .9)), 2), max_mm=round(float(d.max()), 1))
    out = damp_sacrum(out, {k: (s * v @ R.T + t) if pre is None else (s * v @ R.T + t) + pre(s * v @ R.T + t) for k, (v, f) in ring.items()}, sacrum_damp)
    if target_ring is not None and snap:
        out, snap_rep = landmark_snap(out, {k: f for k, (v, f) in ring.items()}, target_ring)
        rep["_landmark_snap"] = snap_rep
        gt = float(cKDTree(L.sample(*target_ring["hip_bone_r"], 25000)[0]).query(L.sample(*target_ring["hip_bone_l"], 25000)[0])[0].min())
        out, sym_rep = close_symphysis(out, max(gt, 2.0))
        rep["_symphysis"] = sym_rep
        for k, (v, f) in ring.items():
            d = ttree.query(out[k])[0]
            rep[k] = dict(median_mm=round(float(np.median(d)), 2), p90_mm=round(float(np.quantile(d, .9)), 2), max_mm=round(float(d.max()), 1))
    # reverse residual: target -> registered ring (coverage)
    rv = np.vstack(list(out.values())); rtree = cKDTree(rv)
    dr = rtree.query(target[::5])[0]
    rep["_target_to_ring"] = dict(median_mm=round(float(np.median(dr)), 2), p90_mm=round(float(np.quantile(dr, .9)), 2))
    rep["_similarity_scale"] = round(float(s), 4)
    rep["_icp_median_mm"] = round(float(np.median(d0)), 2)
    if pre_rep:
        rep["_landmarks"] = pre_rep
    return dict(v=out, sim=sim, stages=stages, report=rep)
