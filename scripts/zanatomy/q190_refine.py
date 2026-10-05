"""Q190: per-structure refinement of the fitted female Z-Anatomy muscles toward HER OWN CT labels.

Owner: "still distortion in the lumbar region and the gluteus muscles".  Root cause (data/derived/Q190_*.json): in v6 every Z muscle is
carried by ONE smooth global field (anchored on her bones + skin outline), so each muscle is sheared/stretched and sits ~9 mm
off her own muscle.  Here each muscle that has a counterpart among her own CT-derived meshes (TotalSegmentator `total` + her
erector / abdominal label meshes, build/viewer_f_hr) is re-placed on its OWN Z-Anatomy source mesh:

  1. start from the Z source shape (not the sheared v6 shape): similarity fit raw -> v6 (Umeyama);
  2. partial-aware two-way trimmed ICP onto her label surface: similarity, then affine with singular values bounded to
     0.85-1.18 of the similarity scale (so the muscle keeps its own proportions);
  3. regularised bounded residual: a smooth Gaussian-RBF displacement (control spacing RBF_SPACING mm, ridge), max MAX_RESID_MM
     (15 mm), fold-guarded (Jacobian), volume guard 0.65-1.5 x the source volume, pushed out of her bone labels;
  4. accepted only if her-label chamfer improves; else the muscle is held (v6 position) and the reason is reported.
Structures with no counterpart of hers (tendons, fascia, nerves, vessels, the muscles she has no label for) follow the refined
muscles through a smooth, distance-decaying displacement (propagation), nothing is invented: only Z meshes move, her CT is the reference.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

from scripts.zanatomy import q190_metrics as Mx

MAX_RESID_MM = 15.0
RBF_SPACING = 20.0
RBF_RIDGE = 1.0
VOLUME_RATIO = (0.65, 1.5)
AFFINE_SV = (0.85, 1.18)
SCALE_BOUNDS = (0.80, 1.25)          # similarity scale relative to the raw->v6 fit
TRIM = 0.75
BODY_SCALE = Mx.BODY_SCALE
HER_ALIAS = {"zan_psoas_major": "iliopsoas", "zan_iliacus_muscle": "iliopsoas"}
SKIP_RE = re.compile(r"forearm|wrist|hand|digit|palm|pollic|carpal|ulnar|antebrach|metacarp|interossei|lumbrical|finger|"
                     r"flexor_(carpi|digit)|extensor_(carpi|digit|indicis|pollicis)|supinator|pronator|brachioradialis|anconeus|"
                     r"masseter|temporalis|pterygoid|pharyng|glossus|rectus_(superior|inferior|medial|lateral)|oblique_(superior|inferior)|"
                     r"levator_palpebrae|digastric|hyoid|mylohyoid|thyro|platysma|capitis|colli|plantaris|_longus_(l|r)$")


def her_id_for(zid: str, her: dict):
    if zid in her and her[zid]["cat"] == "muscle":
        return zid
    m = re.match(r"(zan_psoas_major|zan_iliacus_muscle)_([lr])$", zid)
    if m:
        k = f"iliopsoas_{m.group(2)}"
        return k if k in her else None
    return None


def in_scope(d: dict) -> bool:
    c = d["v"].mean(0)
    return d["cat"] == "muscle" and -140 < c[1] < 650 and not SKIP_RE.search(d["id"])


# ------------------------------------------------------------------------------------------------ transforms
def umeyama(src, dst, w=None, with_scale=True):
    w = np.ones(len(src)) if w is None else w
    w = w / w.sum()
    ms, md = (src * w[:, None]).sum(0), (dst * w[:, None]).sum(0)
    X, Y = src - ms, dst - md
    C = (Y * w[:, None]).T @ X
    U, S, Vt = np.linalg.svd(C)
    D = np.diag([1, 1, np.sign(np.linalg.det(U @ Vt))])
    R = U @ D @ Vt
    s = (S * np.diag(D)).sum() / (w * (X ** 2).sum(1)).sum() if with_scale else 1.0
    return s, R, md - s * R @ ms


def apply_sim(p, T):
    s, R, t = T
    return s * p @ R.T + t


def fit_affine(src, dst, A0, t0, w=None):
    """weighted affine lstsq, singular values bounded to AFFINE_SV x the mean singular value of A0"""
    w = np.ones(len(src)) if w is None else w
    X = np.c_[src, np.ones(len(src))] * np.sqrt(w)[:, None]
    Y = dst * np.sqrt(w)[:, None]
    sol, *_ = np.linalg.lstsq(X, Y, rcond=None)
    A, t = sol[:3].T, sol[3]
    U, S, Vt = np.linalg.svd(A)
    s0 = np.linalg.svd(A0, compute_uv=False).mean()
    S = np.clip(S, AFFINE_SV[0] * s0, AFFINE_SV[1] * s0)
    A2 = U @ np.diag(S) @ Vt
    if np.linalg.det(A2) < 0:
        return None
    # refit translation for the bounded matrix
    t = (dst * w[:, None]).sum(0) / w.sum() - A2 @ ((src * w[:, None]).sum(0) / w.sum())
    return A2, t


class Ref:
    """her label surface: samples + normals + KD-tree"""

    def __init__(self, v, f, n=12000, seed=0):
        self.v, self.f = v.astype(np.float64), f
        rng = np.random.default_rng(seed)
        self.pts = Mx.surf_samples(self.v, f, n, rng)
        self.tree = cKDTree(self.pts)
        self.vol = abs(volume(self.v, f))


def volume(v, f):
    return float(np.einsum("ij,ij->i", v[f[:, 0]], np.cross(v[f[:, 1]], v[f[:, 2]])).sum() / 6.0)


PARTIAL_NEAR_MM = 25.0
PARTIAL_COVER = 0.6       # fraction of the Z vertices within PARTIAL_NEAR_MM of her label below which her label is a PARTIAL reference


def trimmed_pairs(P, ref: Ref, trim=TRIM, cap=45.0, partial=False):
    """two-way pairs: Z points -> her surface and her samples -> Z points, each trimmed to the best `trim` fraction.
    partial: her label covers only part of the Z muscle (e.g. her transversus label is the lateral third): only the Z points near
    her label are paired, the rest follows through the spring / the smooth residual"""
    d1, i1 = ref.tree.query(P)
    k1 = d1 <= (PARTIAL_NEAR_MM if partial else min(np.quantile(d1, trim), cap))
    zt = cKDTree(P)
    d2, i2 = zt.query(ref.pts)
    k2 = d2 <= min(np.quantile(d2, trim), cap)
    return (np.flatnonzero(k1), ref.pts[i1[k1]]), (i2[k2], ref.pts[k2])


MAX_ROT_DEG = 25.0      # the fitted pose may not turn the muscle further than this from its v6 orientation


def _limit_rotation(R, R0, max_deg):
    from scipy.spatial.transform import Rotation as Rot
    rel = Rot.from_matrix(R @ R0.T)
    rv = rel.as_rotvec()
    ang = np.linalg.norm(rv)
    lim = np.radians(max_deg)
    if ang > lim:
        rv = rv * lim / ang
    return Rot.from_rotvec(rv).as_matrix() @ R0


SPRING_PARTIAL = 0.35
SPRING = 0.1          # weight of the "stay near the v6 position" spring (per source point) against 1.0 per her-label pair


def icp(raw_s, T0, ref: Ref, iters=40, affine=False, A0=None, anchor=None, partial=False):
    """raw_s: source (raw) points; returns the transform (similarity T or affine (A,t)) on raw coordinates"""
    T = T0
    s0 = T0[0]
    for it in range(iters):
        P = apply_sim(raw_s, T) if not affine else raw_s @ T[0].T + T[1]
        (ia, qa), (ib, qb) = trimmed_pairs(P, ref, partial=partial)
        src = np.vstack([raw_s[ia], raw_s[ib]])
        dst = np.vstack([qa, qb])
        w = np.ones(len(src))
        if anchor is not None:                       # sliding along a sheet is invisible to her surface: keep v6 as the prior
            n_d = len(src)
            src = np.vstack([src, anchor[0]]); dst = np.vstack([dst, anchor[1]])
            w = np.concatenate([w, np.full(len(anchor[0]), (SPRING_PARTIAL if partial else SPRING) * n_d / len(anchor[0]))])
        if len(src) < 20:
            break
        if not affine:
            s, R, t = umeyama(src, dst, w)
            R = _limit_rotation(R, T0[1], MAX_ROT_DEG)
            s = float(np.clip(s, SCALE_BOUNDS[0] * s0, SCALE_BOUNDS[1] * s0))
            ws = w / w.sum()
            T = (s, R, (dst * ws[:, None]).sum(0) - s * R @ (src * ws[:, None]).sum(0))
        else:
            r = fit_affine(src, dst, A0, None, w)
            if r is None:
                break
            T = r
    return T


# ------------------------------------------------------------------------------------------------ residual
def fps(P, spacing, rng):
    """greedy spacing sample"""
    idx = rng.permutation(len(P))
    tree_pts = []
    chosen = []
    for i in idx:
        if not chosen or np.min(np.linalg.norm(np.asarray(tree_pts) - P[i], axis=1)) > spacing:
            chosen.append(i); tree_pts.append(P[i])
        if len(chosen) > 800:
            break
    return P[chosen]


def rbf_fit(C, sigma, X, D, w, ridge):
    Phi = np.exp(-((X[:, None, :] - C[None]) ** 2).sum(2) / (2 * sigma ** 2))
    Pw = Phi * w[:, None]
    G = Pw.T @ Phi + ridge * np.eye(len(C))
    return np.linalg.solve(G, Pw.T @ D)


def rbf_eval(C, sigma, W, X):
    out = np.empty((len(X), 3))
    for a in range(0, len(X), 20000):
        Xc = X[a:a + 20000]
        out[a:a + 20000] = np.exp(-((Xc[:, None, :] - C[None]) ** 2).sum(2) / (2 * sigma ** 2)) @ W
    return out


def jac_min(C, sigma, W, X, h=3.0):
    """smallest det(I + grad u) over the points (central differences of the RBF displacement)"""
    J = np.zeros((len(X), 3, 3))
    for k in range(3):
        e = np.zeros(3); e[k] = h
        J[:, :, k] = (rbf_eval(C, sigma, W, X + e) - rbf_eval(C, sigma, W, X - e)) / (2 * h)
    J += np.eye(3)
    return np.linalg.det(J)


def residual_fit(x1, ref: Ref, cap=MAX_RESID_MM, iters=4, rng=None, partial=False):
    """smooth bounded displacement u moving the (affinely fitted) points x1 toward her surface; returns x1 + u(x1), diagnostics"""
    rng = rng or np.random.default_rng(1)
    C = fps(x1, RBF_SPACING, rng)
    sigma = RBF_SPACING
    sub = rng.choice(len(x1), min(len(x1), 6000), replace=False)
    X = x1[sub]
    u_cur = np.zeros_like(X)
    W = np.zeros((len(C), 3))
    for it in range(iters):
        cur = X + u_cur
        d1, i1 = ref.tree.query(cur)
        D = ref.pts[i1] - X                        # total displacement wanted from x1
        thr = min(PARTIAL_NEAR_MM if partial else np.quantile(d1, 0.85), cap * 1.6)
        w = (d1 <= thr).astype(float)
        mag = np.linalg.norm(D, axis=1)
        D = D * np.minimum(1.0, cap / np.maximum(mag, 1e-9))[:, None]
        # her samples the muscle does not cover pull the nearest Z point toward them (bounded)
        zt = cKDTree(cur)
        d2, i2 = zt.query(ref.pts)
        k2 = d2 <= min(np.quantile(d2, 0.85), cap * 1.6)
        #
        Xb = np.vstack([X, X[i2[k2]]])
        Db = np.vstack([D, ref.pts[k2] - X[i2[k2]]])
        wb = np.concatenate([w, 0.5 * np.ones(k2.sum())])
        mb = np.linalg.norm(Db, axis=1)
        Db = Db * np.minimum(1.0, cap / np.maximum(mb, 1e-9))[:, None]
        W = rbf_fit(C, sigma, Xb, Db, wb, RBF_RIDGE * wb.sum() / len(C))
        u_cur = rbf_eval(C, sigma, W, X)
    # magnitude cap + fold guard: scale the amplitude down until the Jacobian is healthy
    amp = 1.0
    for _ in range(8):
        u = rbf_eval(C, sigma, W * amp, x1)
        m = np.linalg.norm(u, axis=1)
        sc = np.minimum(1.0, cap / np.maximum(m, 1e-9))
        det = jac_min(C, sigma, W * amp, x1[rng.choice(len(x1), min(len(x1), 3000), replace=False)])
        if det.min() > 0.45:
            break
        amp *= 0.8
    u = rbf_eval(C, sigma, W * amp, x1)
    u *= np.minimum(1.0, cap / np.maximum(np.linalg.norm(u, axis=1), 1e-9))[:, None]
    return x1 + u, {"amp": round(amp, 2), "jac_min": round(float(det.min()), 2), "resid_med_mm": round(float(np.median(np.linalg.norm(u, axis=1))), 2),
                    "resid_max_mm": round(float(np.linalg.norm(u, axis=1).max()), 2)}


def chamfer(v, f, ref: Ref, n=6000, partial=False):
    pz = Mx.surf_samples(v, f, n)
    da = ref.tree.query(pz)[0]
    a = float(np.median(da[da <= PARTIAL_NEAR_MM])) if partial and (da <= PARTIAL_NEAR_MM).any() else float(np.median(da))
    b = float(np.median(cKDTree(pz).query(ref.pts)[0]))
    return a, b, 0.5 * (a + b)


def refine_group(members, ref: Ref, log=print):
    """members: [{id, v (v6), r (raw), f}]; returns {id: v_new} + report"""
    R = np.vstack([m["r"] for m in members])
    V6 = np.vstack([m["v"] for m in members])
    F = []
    off = 0
    for m in members:
        F.append(m["f"] + off); off += len(m["r"])
    F = np.vstack(F)
    rng = np.random.default_rng(3)
    sub = rng.choice(len(R), min(len(R), 5000), replace=False)
    Rs = R[sub]
    T0 = umeyama(R, V6)
    partial = bool((ref.tree.query(V6[sub])[0] <= PARTIAL_NEAR_MM).mean() < PARTIAL_COVER)
    before = chamfer(V6, F, ref, partial=partial)
    # similarity ICP (start at the v6 pose of the source shape); a PARTIAL label (covers only part of the Z muscle) must not set
    # the muscle's length, so it gets a similarity with narrow scale bounds and no affine stage
    global SCALE_BOUNDS
    sb = SCALE_BOUNDS
    if partial:
        SCALE_BOUNDS = (0.92, 1.10)
    try:
        T1 = icp(Rs, T0, ref, affine=False, anchor=(Rs, V6[sub]), partial=partial)
    finally:
        SCALE_BOUNDS = sb
    A1 = T1[0] * T1[1]
    t1 = T1[2]
    cands = {"sim": R @ A1.T + t1}
    if not partial:
        TA = icp(Rs, (A1, t1), ref, iters=25, affine=True, A0=A1, anchor=(Rs, V6[sub]), partial=partial)
        cands["affine"] = R @ TA[0].T + TA[1]
    # position stability: the fitted pose may not move the muscle (mean vertex shift from v6) much beyond the error it corrects
    base = apply_sim(R, T0)
    cap_shift = (2.0 * before[2] + 8.0) if partial else (3.0 * before[2] + 10.0)
    for k in cands:
        sh = np.linalg.norm(cands[k] - V6, axis=1).mean()
        if sh > cap_shift:
            lo, hi = 0.0, 1.0
            for _ in range(12):
                mid = 0.5 * (lo + hi)
                if np.linalg.norm(base + mid * (cands[k] - base) - V6, axis=1).mean() > cap_shift:
                    hi = mid
                else:
                    lo = mid
            cands[k] = base + lo * (cands[k] - base)
    best = None
    for name, X1 in cands.items():
        c = chamfer(X1, F, ref, partial=partial)
        if best is None or c[2] < best[1][2]:
            best = (name, c, X1)
    name, c1, X1 = best
    TA = (A1, t1)
    X2, diag = residual_fit(X1, ref, partial=partial)
    c2 = chamfer(X2, F, ref, partial=partial)
    # volume guard (closed meshes)
    vol_src = abs(volume(R, F)) * BODY_SCALE ** 3
    vol2 = abs(volume(X2, F))
    ratio = vol2 / vol_src if vol_src > 1e-6 else 1.0
    rep = {"her_label_chamfer_before_mm": [round(x, 2) for x in before], "after_pose_mm": [round(x, 2) for x in c1], "after_mm": [round(x, 2) for x in c2],
           "pose": name, "partial_reference": partial, "affine_sv": [round(float(x), 3) for x in np.linalg.svd(np.linalg.lstsq(np.c_[R[::7], np.ones(len(R[::7]))], X1[::7], rcond=None)[0][:3].T / BODY_SCALE, compute_uv=False)],
           "volume_ratio_vs_source": round(ratio, 3), **diag}
    return X2, rep, off


def volume_guard(X, R, F, centroid_pull=True):
    """shrink/grow uniformly about the centroid so the volume stays within VOLUME_RATIO x source volume (x BODY_SCALE^3)"""
    vol_src = abs(volume(R, F)) * BODY_SCALE ** 3
    if vol_src < 1e-6:
        return X, 1.0
    ratio = abs(volume(X, F)) / vol_src
    lim = min(max(ratio, VOLUME_RATIO[0]), VOLUME_RATIO[1])
    if lim != ratio:
        c = X.mean(0)
        X = c + (X - c) * (lim / ratio) ** (1 / 3)
        ratio = lim
    return X, ratio


class Guards:
    """her bone labels (inside-depth map) -> push points out of bone"""

    def __init__(self, body):
        self.B = body

    def depth(self, P):
        import scripts.placement_sweep_q185 as P185
        return np.nan_to_num(P185.sample_depth(self.B.bone, self.B.A, self.B.O, P, self.B.shape))

    def push_out(self, P, f=None, tol=2.0, iters=4, max_move=12.0, smooth=30):
        """move vertices that lie > tol mm inside her bone labels out along the depth gradient; with the mesh faces `f` the push is
        spread over the neighbours (Laplacian passes, each vertex keeps at least its own push) so it makes no facets/pleats"""
        P0 = P.copy()
        P = P.copy()
        for _ in range(iters):
            d = self.depth(P)
            ins = d > tol
            if not ins.any():
                break
            Qp = P[ins]
            g = np.zeros_like(Qp)
            for k in range(3):
                e = np.zeros(3); e[k] = 1.5
                g[:, k] = (self.depth(Qp + e) - self.depth(Qp - e)) / 3.0
            n = np.linalg.norm(g, axis=1, keepdims=True)
            step = np.minimum(d[ins] - tol + 0.3, max_move)[:, None]
            P[ins] = Qp - np.where(n > 1e-6, g / np.maximum(n, 1e-9), 0.0) * step   # depth grows inward: step against its gradient
        if f is not None and smooth:
            from scipy import sparse
            D = P - P0
            moved = np.linalg.norm(D, axis=1) > 1e-6
            if moved.any():
                n_ = len(P)
                e = np.vstack([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
                A = sparse.coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(n_, n_)).tocsr()
                A = ((A + A.T) > 0).astype(float)
                deg = np.maximum(np.asarray(A.sum(1)).ravel(), 1)
                Ds = D.copy()
                for _ in range(smooth):
                    Ds = (A @ Ds) / deg[:, None]
                    Ds[moved] = np.where((np.linalg.norm(Ds[moved], axis=1) > np.linalg.norm(D[moved], axis=1))[:, None], Ds[moved], D[moved])
                cand = P0 + Ds
                still = self.depth(cand) > tol + 0.5
                cand[still] = P[still]
                P = cand
        return P


def split_back(X, members):
    out, o = {}, 0
    for m in members:
        out[m["id"]] = X[o:o + len(m["r"])]
        o += len(m["r"])
    return out


def dump_pending(pending, raw, path):
    meta = [{"id": p["mesh_id"], "cat": p["cat"], "zname": p.get("zanatomy_name"), "name": p.get("display_name"),
             "side": str(p.get("side_raw"))} for p in pending]
    arrs = {"meta": np.array(json.dumps(meta))}
    for i, p in enumerate(pending):
        arrs[f"v{i}"] = p["v"].astype(np.float32)
        arrs[f"r{i}"] = raw[p["mesh_id"]].astype(np.float32)
        arrs[f"f{i}"] = p["f"].astype(np.int32)
    np.savez(path, **arrs)
    print("q190 dump:", len(meta), "meshes ->", path)


# ------------------------------------------------------------------------------------------------ whole-body pass
def plan_groups(structs: list[dict], her: dict) -> dict:
    """{her_id: [Z structure dicts]} for every in-scope Z muscle that has a counterpart among her own meshes"""
    groups: dict = {}
    for d in structs:
        if not in_scope(d):
            continue
        hid = her_id_for(d["id"], her)
        if hid:
            groups.setdefault(hid, []).append(d)
    return groups


class HerObstacles:
    """her own muscle labels do not overlap each other: a refined Z muscle may not enter another label of hers.  Per label: closed mesh
    (ray containment), vertex KD-tree and outward vertex normals (orientation checked by probing)."""

    def __init__(self, her: dict):
        import trimesh
        self.d = {}
        for k, h in her.items():
            if h.get("cat") != "muscle" or len(h["v"]) < 50:
                continue
            v, f = h["v"].astype(np.float64), h["f"].astype(np.int64)
            n = _vertex_normals(v, f)
            m = trimesh.Trimesh(v, f, process=False)
            probe = np.arange(0, len(v), max(1, len(v) // 300))
            try:
                outside_frac = (~m.contains(v[probe] + 1.0 * n[probe])).mean()
            except Exception:
                continue
            if outside_frac < 0.5:
                n = -n
            self.d[k] = (v.min(0), v.max(0), cKDTree(v), n, v, m)

    def push(self, X, F, own_hids, iters=3, margin=0.3, max_move=10.0, smooth=6):
        X = X.copy()
        X0 = X.copy()
        for _ in range(iters):
            D = np.zeros_like(X)
            lo, hi = X.min(0), X.max(0)
            hit = 0
            for k, (l, h, tree, n, v, m) in self.d.items():
                if k in own_hids or np.any(h < lo - 1) or np.any(l > hi + 1):
                    continue
                sel = np.flatnonzero(np.all((X >= l - 1) & (X <= h + 1), 1))
                if not len(sel):
                    continue
                try:
                    ins = m.contains(X[sel])
                except Exception:
                    continue
                if not ins.any():
                    continue
                s2 = sel[ins]
                dd, q = tree.query(X[s2])
                depth = np.maximum(-np.einsum("ij,ij->i", X[s2] - v[q], n[q]), 0.0) + margin
                push = np.minimum(depth, max_move)[:, None] * n[q]
                big = np.linalg.norm(push, axis=1) > np.linalg.norm(D[s2], axis=1)
                D[s2[big]] = push[big]
                hit += int(ins.sum())
            if not hit:
                break
            D = _smooth_push(F, D, smooth)
            D *= np.minimum(1.0, max_move / np.maximum(np.linalg.norm(D, axis=1), 1e-9))[:, None]
            X = X + D
        return X, int((np.linalg.norm(X - X0, axis=1) > 0.2).sum())


def _closed(f):
    e = np.sort(np.vstack([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]), axis=1)
    return bool((np.unique(e, axis=0, return_counts=True)[1] == 2).all())


def refine_all(structs, her, guards=None, log=print, obstacles=None):
    """per-group refinement; returns ({id: new v}, {id: report}); a group is HELD (v6 kept) when her-label chamfer does not improve"""
    groups = plan_groups(structs, her)
    new, rep = {}, {}
    for hid, members in sorted(groups.items()):
        hv = her[hid]
        if len(hv["v"]) < 50:
            continue
        ref = Ref(hv["v"].astype(np.float64), hv["f"].astype(np.int64))
        X, r, _ = refine_group(members, ref)
        Rr = np.vstack([m["r"] for m in members])
        F = np.vstack([m["f"] + o for m, o in zip(members, np.cumsum([0] + [len(m["r"]) for m in members[:-1]]))])
        closed = _closed(F)
        if closed:
            X, ratio = volume_guard(X, Rr, F)
        else:                                  # open sheets (fasciae, wide flat muscles drawn as one shell): no volume to guard
            ratio = abs(volume(X, F)) / max(abs(volume(Rr, F)) * BODY_SCALE ** 3, 1e-6)
        r["volume_ratio_vs_source"] = round(ratio, 3)
        r["closed_mesh"] = bool(closed)
        if guards is not None:
            X = guards.push_out(X, F)
        if obstacles is not None:
            X, n_pushed = obstacles.push(X, F, {hid})
            r["pushed_out_of_her_other_labels_vertices"] = n_pushed
        c = chamfer(X, F, ref, partial=r["partial_reference"])
        r["after_mm"] = [round(x, 2) for x in c]
        if c[2] < 0.9 * r["her_label_chamfer_before_mm"][2]:
            r["status"] = "refined"
            for k, v in split_back(X, members).items():
                new[k] = v
        else:
            r["status"] = "held"
        r["her_id"] = hid
        r["members"] = [m["id"] for m in members]
        for m in members:
            rep[m["id"]] = r
        log(f"  {hid:28s} {r['status']:8s} her-label chamfer {r['her_label_chamfer_before_mm'][2]:.1f} -> {c[2]:.1f} mm  vol x{ratio:.2f}  {r['pose']}")
    return new, rep


PROP_CATS = ("muscle", "fascia", "tendon", "nerve", "vessel", "bursa")
PROP_SIGMA, PROP_GATE, PROP_K = 22.0, 35.0, 24


def propagate(structs, new, log=print):
    """structures without a counterpart of hers (tendons, fascia, nerves, vessels, the muscles she has no label for) follow the
    refined muscles: displacement = distance-weighted mean of the refined muscles' displacements (Gaussian, sigma PROP_SIGMA),
    gated to 0 beyond PROP_GATE of the nearest refined vertex.  Returns {id: new v}"""
    old, dlt = [], []
    for d in structs:
        if d["id"] in new:
            sel = np.arange(0, len(d["v"]), max(1, len(d["v"]) // 2500))
            old.append(d["v"][sel]); dlt.append(new[d["id"]][sel] - d["v"][sel])
    old, dlt = np.vstack(old), np.vstack(dlt)
    tree = cKDTree(old)
    out = {}
    for d in structs:
        if d["id"] in new or d["cat"] not in PROP_CATS or SKIP_RE.search(d["id"]) or CNS_STRUCT.search(d["id"]):
            continue
        c = d["v"].mean(0)
        if not (-200 < c[1] < 700):
            continue
        dist, idx = tree.query(d["v"], k=PROP_K, distance_upper_bound=PROP_GATE * 2.5)
        has = np.isfinite(dist[:, 0])
        if not has.any():
            continue
        dd = np.where(np.isfinite(dist), dist, 1e9)
        w = np.exp(-(dd / PROP_SIGMA) ** 2)
        ws = w.sum(1)
        D = np.zeros_like(d["v"])
        ok = has & (ws > 1e-9)
        ii = np.where(np.isfinite(dist), idx, 0)
        D[ok] = (w[ok][:, :, None] * dlt[ii[ok]]).sum(1) / ws[ok][:, None]
        g = np.exp(-(dd[:, 0] / PROP_GATE) ** 2) * has
        step = g[:, None] * D
        if np.linalg.norm(step, axis=1).max() < 0.3:
            continue
        # fold / stretch guard: a structure whose own shape would get MORE distorted vs its Z source is moved only part of the way
        base_s = Mx.distortion_score(Mx.stretch_stats(d["v"], d["r"], d["f"]))
        for amp in (1.0, 0.6, 0.3):
            cand = d["v"] + amp * step
            if Mx.distortion_score(Mx.stretch_stats(cand, d["r"], d["f"])) <= base_s + 3.0:
                out[d["id"]] = cand
                break
    log(f"  propagated onto {len(out)} structures without a counterpart of hers")
    return out


# ------------------------------------------------------------------------------------------------ skin
def skin_displacement_smoothing(structs, mask_fn, iters=12, log=print):
    """Skin patches: u = v6 - raw (displacement of every skin vertex from its Z source position) is smoothed over the WELDED skin
    graph (the patches tile one surface; seam vertices share their raw position), v' = v6 + m (u_smooth - u).  Smoothing the
    displacement, not the surface, keeps Z-Anatomy's own skin relief (gluteal fold, cleft, iliac crest) and removes the stretch/shear
    spikes the global field put in.  m = mask_fn(points) in [0, 1] (0 at the front: the v6 anterior result is kept).
    Returns {id: v}."""
    from scipy import sparse
    skin = [d for d in structs if d["cat"] == "skin"]
    allraw = np.vstack([d["r"] for d in skin]).astype(np.float64)
    key = np.round(allraw, 2)
    uniq, inv = np.unique(key, axis=0, return_inverse=True)
    inv = inv.reshape(-1)
    n = len(uniq)
    off = np.cumsum([0] + [len(d["r"]) for d in skin])
    e = []
    for d, o in zip(skin, off[:-1]):
        f = d["f"]
        e.append(inv[o + np.vstack([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])])
    e = np.vstack(e)
    A = sparse.coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(n, n)).tocsr()
    A = ((A + A.T) > 0).astype(float)
    deg = np.maximum(np.asarray(A.sum(1)).ravel(), 1)
    allv = np.vstack([d["v"] for d in skin]).astype(np.float64)
    U = np.zeros((n, 3)); cnt = np.zeros(n)
    np.add.at(U, inv, allv - allraw); np.add.at(cnt, inv, 1)
    U /= np.maximum(cnt, 1)[:, None]
    Us = U.copy()
    for _ in range(iters):
        Us = (A @ Us) / deg[:, None]
    keep = np.concatenate([np.full(len(d["v"]), (not LIMB_SKIN.search(d["id"])) and -150 < d["v"].mean(0)[1] < 640 and abs(d["v"].mean(0)[0]) < 260)
                           for d in skin])
    from scripts.zanatomy import trunk_refit_q186c as T
    wy = T.smoothstep((allv[:, 1] + 110.0) / 30.0) * (1.0 - T.smoothstep((allv[:, 1] - 290.0) / 40.0))   # lumbar/sacral/gluteal/hip/flank only
    m = mask_fn(allv) * keep * wy
    dlt = m[:, None] * (Us[inv] - U[inv])
    dlt *= np.minimum(1.0, 20.0 / np.maximum(np.linalg.norm(dlt, axis=1), 1e-9))[:, None]
    newv = allv + dlt
    out = {}
    for d, a, b in zip(skin, off[:-1], off[1:]):
        out[d["id"]] = newv[a:b]
    mv = np.linalg.norm(newv - allv, axis=1)
    log(f"  skin displacement smoothing: {len(skin)} patches, {n} welded vertices, moved median {np.median(mv[m > 0.01]):.1f} mm max {mv.max():.1f} mm")
    return out


def outline_chart(skin_mesh, axis, smooth_cells=2.5):
    """her CT back outline R(y, theta): first-exit radius of the horizontal ray from her trunk axis, TRUSTED cells only (front/back
    sectors, one crossing; the lateral band is fused with her arms), inpainted along theta (<= 130 deg gaps) and lightly Gaussian
    smoothed (her CT skin is stair-stepped).  Returns (ys, ths, Rsmooth, trusted_mask_dilated)"""
    from scipy import ndimage as ndi
    from scripts.zanatomy import trunk_refit_q186c as T
    ys = np.arange(-130.0, 640.0, 5.0)
    ths = np.radians(np.arange(-180.0, 180.0, 2.5))
    R, nh, trusted = T.her_outline_chart(skin_mesh, axis, ys, ths)
    G = np.where(trusted, R, np.nan)
    Gi, _ = T.inpaint_theta(G, ths)
    fill = np.where(np.isnan(Gi), np.nanmedian(Gi), Gi)
    Gs = ndi.gaussian_filter(np.pad(fill, ((0, 0), (8, 8)), mode="wrap"), sigma=smooth_cells, mode="nearest")[:, 8:-8]
    return ys, ths, np.where(np.isnan(Gi), np.nan, Gs), trusted


LIMB_SKIN = re.compile(r"arm|forearm|wrist|hand|digit|palm|nail|perionyx|elbow|cubital|bicipital|radial|thigh|knee|leg|calf|foot|neck|face|head|ear|cheek|nose|chin|scalp|axill|deltoid|supraclav|infraclav|deltopectoral|carotid|triangle_of_ausc|clavicular")


def outward_vertex_normals(v, f, axis_fn):
    """area-weighted vertex normals of an open skin patch with every FACE normal turned away from her trunk axis (the winding of
    an open Z-Anatomy patch is not consistent, the radial direction is a reliable outside for the trunk)"""
    fn = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
    cen = v[f].mean(1)
    xc, zc = axis_fn(cen[:, 1])
    rad = np.stack([cen[:, 0] - xc, np.zeros(len(f)), cen[:, 2] - zc], 1)
    fn = np.where((np.einsum("ij,ij->i", fn, rad) < 0)[:, None], -fn, fn)
    vn = np.zeros_like(v)
    for k in range(3):
        np.add.at(vn, f[:, k], fn)
    return vn / np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-9)


def _welded(skin):
    from scipy import sparse
    allraw = np.vstack([d["r"] for d in skin]).astype(np.float64)
    uniq, inv = np.unique(np.round(allraw, 2), axis=0, return_inverse=True)
    inv = inv.reshape(-1)
    n = len(uniq)
    off = np.cumsum([0] + [len(d["r"]) for d in skin])
    e = np.vstack([inv[o + np.vstack([d["f"][:, [0, 1]], d["f"][:, [1, 2]], d["f"][:, [2, 0]]])] for d, o in zip(skin, off[:-1])])
    A = sparse.coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(n, n)).tocsr()
    A = ((A + A.T) > 0).astype(float)
    return inv, A, np.maximum(np.asarray(A.sum(1)).ravel(), 1), n, off


def skin_outline_pull(structs, skin_mesh, axis, chart, inset=1.5, cap_out=25.0, cap_in=8.0, smooth_iters=10, log=print):
    """Posterior / lateral skin (lumbar, sacral, gluteal, hip, flank; NOT the front: weight 0 for |theta| < 70 deg): add a smooth radial
    offset so the Z skin sits on her measured CT back outline (inset mm inside it).  Only an offset is added, Z-Anatomy's own relief
    (gluteal cleft/fold, iliac crest) is kept; v6 stays where it already lies inside the outline by less than the cap."""
    from scripts.zanatomy import trunk_refit_q186c as T
    ys, ths, Rs, _ = chart
    skin = [d for d in structs if d["cat"] == "skin"]
    inv, A, deg, n, off_ = _welded(skin)
    allv = np.vstack([d["v"] for d in skin]).astype(np.float64)
    xc, zc = axis(allv[:, 1])
    dx, dz = allv[:, 0] - xc, allv[:, 2] - zc
    r = np.hypot(dx, dz)
    th = np.arctan2(dx, dz)
    wth = T.smoothstep((np.degrees(np.abs(th)) - 70.0) / 30.0)
    wy = T.smoothstep((allv[:, 1] + 110.0) / 30.0) * (1.0 - T.smoothstep((allv[:, 1] - 290.0) / 40.0))
    keep = np.concatenate([np.full(len(d["v"]), not LIMB_SKIN.search(d["id"]) and abs(d["v"].mean(0)[0]) < 260 and d["v"].mean(0)[1] < 640) for d in skin])
    w = wth * wy * keep
    Rh = T.bilinear(Rs, ys, ths, allv[:, 1], th)
    offv = np.clip(np.nan_to_num(Rh - inset - r, nan=0.0), -cap_in, cap_out) * w
    # welded-graph smoothing of the offset (seam vertices share it): small offset gradients -> no stretch
    O = np.zeros(n); cnt = np.zeros(n)
    np.add.at(O, inv, offv); np.add.at(cnt, inv, 1)
    O /= np.maximum(cnt, 1)
    for _ in range(smooth_iters):
        O = (A @ O) / deg
    offv = O[inv]
    u = np.stack([dx, np.zeros_like(dx), dz], 1) / np.maximum(r, 1e-6)[:, None]
    newv = allv + (np.where(w > 0, offv, 0.0))[:, None] * u
    out, moved_all = {}, []
    for d, a_, b_ in zip(skin, off_[:-1], off_[1:]):
        if (w[a_:b_] > 1e-3).any():
            out[d["id"]] = newv[a_:b_]
            moved_all.append(np.linalg.norm(newv[a_:b_] - allv[a_:b_], axis=1)[w[a_:b_] > 0.3])
    mv = np.concatenate(moved_all)
    log(f"  skin outline pull: {len(out)} patches, moved (posterior weight > 0.3) median {np.median(mv):.1f} mm p90 {np.percentile(mv, 90):.1f} mm max {mv.max():.1f}")
    return out


# ------------------------------------------------------------------------------------------------ skin envelope (nerves / vessels / fascia)
ARM_STRUCT = re.compile(r"brachial|axillary|cephalic|basilic|circumflex_humeral|humer|subscapular_(a|v|n)|thoracodorsal|lateral_thoracic|"
                        r"musculocutaneous|radial|ulnar|median|antebrach|forearm|hand|digit|deltoid|biceps|triceps|coracobrachialis|of_arm|arm_")


class SkinEnvelope:
    """the FITTED trunk skin as a signed envelope: nearest skin vertex + its outward normal (pseudo-normal side test)"""

    def __init__(self, skin_structs, axis):
        P, N = [], []
        for d in skin_structs:
            if LIMB_SKIN.search(d["id"]) or abs(d["v"].mean(0)[0]) > 260:
                continue
            v, f = d["v"].astype(np.float64), d["f"]
            vn = outward_vertex_normals(v, f, axis)
            P.append(v); N.append(vn)
        self.P, self.N = np.vstack(P), np.vstack(N)
        self.tree = cKDTree(self.P)

    def signed(self, X):
        d, j = self.tree.query(X)
        return np.einsum("ij,ij->i", X - self.P[j], self.N[j]), d, j


def envelope_clamp(structs_by_id, ids, env: SkinEnvelope, axis, margin=1.0, reach=40.0, max_move=14.0):
    """vertices of the listed structures that lie outside the fitted skin envelope (within `reach` mm of it) are moved inside it.
    Returns {id: (new v, n_moved, max_mm)}"""
    out = {}
    for k in ids:
        d = structs_by_id[k]
        v = d["v"]
        s, dist, j = env.signed(v)
        xc, zc = axis(v[:, 1])
        rho = np.hypot(v[:, 0] - xc, v[:, 2] - zc)
        bad = (s > -margin) & (dist < reach) & (rho < 260)
        if not bad.any():
            continue
        step = np.minimum(s[bad] + margin, max_move)[:, None] * env.N[j[bad]]
        D = np.zeros_like(v)
        D[bad] = -step
        if len(d["f"]):
            D = _smooth_push(d["f"], D, 6)           # spread over the mesh: no spikes / pleats where a structure crosses the skin
        nv = v + D
        out[k] = (nv, int(bad.sum()), float(np.linalg.norm(step, axis=1).max()))
    return out


def skin_cover_muscles(structs, skin_newv, muscle_v, env_axis, axis_fn, chart, margin=3.0, cap=25.0, smooth_iters=24, tol=2.0, log=print):
    """Where a (refined) trunk muscle reaches outside the fitted skin (flank: her outline is hidden by her arms, so the v6 skin sits
    ~20 mm inside), the skin patches are moved OUTWARD along their normals until they cover it by `margin` mm, never beyond her
    outline interpolated by the chart (+0.5 mm) and never more than `cap` mm.  Offsets are smoothed over the welded skin graph."""
    from scripts.zanatomy import trunk_refit_q186c as T
    ys, ths, Rs, _ = chart
    skin = [d for d in structs if d["cat"] == "skin"]
    inv, A, deg, n, off_ = _welded(skin)
    allv = np.vstack([skin_newv.get(d["id"], d["v"]) for d in skin]).astype(np.float64)
    names = np.concatenate([np.full(len(d["v"]), d["id"], object) for d in skin])
    keep = np.concatenate([np.full(len(d["v"]), not LIMB_SKIN.search(d["id"]) and abs(d["v"].mean(0)[0]) < 260) for d in skin])
    # normals of the skin vertices (outward)
    fn_v = np.zeros_like(allv)
    for d, a_, b_ in zip(skin, off_[:-1], off_[1:]):
        vn = outward_vertex_normals(allv[a_:b_], d["f"], axis_fn)
        fn_v[a_:b_] = vn
    # seam vertices (one copy per patch) must move in the SAME direction: welded mean normal
    Nw = np.zeros((n, 3)); np.add.at(Nw, inv, fn_v)
    fn_v = Nw[inv] / np.maximum(np.linalg.norm(Nw[inv], axis=1, keepdims=True), 1e-9)
    tree = cKDTree(allv[keep])
    kidx = np.flatnonzero(keep)
    need = np.zeros(len(allv))
    for k, v in muscle_v.items():
        if v is None or len(v) == 0:
            continue
        dist, j = tree.query(v)
        jj = kidx[j]
        s = np.einsum("ij,ij->i", v - allv[jj], fn_v[jj])
        sel = (s > -margin) & (dist < 45.0)
        if sel.any():
            np.maximum.at(need, jj[sel], s[sel] + margin)
    xc, zc = axis_fn(allv[:, 1])
    r = np.hypot(allv[:, 0] - xc, allv[:, 2] - zc)
    th = np.arctan2(allv[:, 0] - xc, allv[:, 2] - zc)
    Rh = T.bilinear(Rs, ys, ths, allv[:, 1], th)
    room = np.nan_to_num(Rh - 0.5 - r, nan=cap)
    wth = T.smoothstep((np.degrees(np.abs(th)) - 70.0) / 30.0)       # the anterior skin (|theta| < 70 deg) stays exactly as in v6
    need = np.minimum(np.minimum(need, cap), np.maximum(room, 0.0)) * keep * wth
    needw = np.zeros(n)
    np.maximum.at(needw, inv, need)               # seam vertices (one copy per patch) share the offset
    O = needw.copy()
    for _ in range(smooth_iters):
        O = (A @ O) / deg
    off = np.maximum(O, needw - tol)[inv]         # smooth offsets; a muscle may still reach `tol` mm into the skin margin (no bumps)
    newv = allv + off[:, None] * fn_v
    out = dict(skin_newv)
    moved = 0
    for d, a_, b_ in zip(skin, off_[:-1], off_[1:]):
        if (off[a_:b_] > 0.3).any():
            out[d["id"]] = newv[a_:b_]
            moved += 1
    log(f"  skin covers muscles: {moved} patches moved outward, max {off.max():.1f} mm, vertices > 1 mm {int((off > 1).sum())}")
    return out


def run_all(structs, her, guards, skin_mesh, axis, log=print):
    """the whole Q190 pass on {id, cat, v, r, f} structures (full resolution, v6 positions).  Returns (new v per id, report)."""
    from scripts.zanatomy import trunk_refit_q186c as T
    by_id = {d["id"]: d for d in structs}
    rep = {}
    obstacles = HerObstacles(her)
    new, mrep = refine_all(structs, her, guards, log=log, obstacles=obstacles)
    pr = propagate(structs, new, log=log)
    newv = {**new, **pr}
    rep["muscles"], rep["propagated"] = mrep, sorted(pr)
    rec, rrep = shape_recovery(structs, newv, skip_ids=set(new), log=log)
    newv.update(rec)
    rep["shape_recovery"] = rrep
    mus_ids = [k for k, d in by_id.items() if d["cat"] == "muscle" and in_scope(d) and not ARM_STRUCT.search(k)]
    # resolve_overlaps() exists but is NOT run: measured gain 16.8 % -> 16.2-16.6 % of trunk-muscle vertices inside another muscle, at a
    # distortion cost and a ray-tracer crash risk; the her-label exclusion in refine_all is what keeps the refined muscles out of each other
    rep["overlap_resolution"] = {"run": False}
    # skin: displacement smoothing (posterior/lateral only), then pull toward her measured back outline
    mask = lambda q: 1.0 - T.anterior_weight(q, axis)
    sm = skin_displacement_smoothing(structs, mask, iters=12, log=log)
    skin_after_sm = [{**d, "v": sm[d["id"]]} for d in structs if d["cat"] == "skin"]
    chart = outline_chart(skin_mesh, axis)
    pull = skin_outline_pull(skin_after_sm, skin_mesh, axis, chart, log=log)
    skin_v = {d["id"]: pull.get(d["id"], sm[d["id"]]) for d in skin_after_sm}
    rep["skin_ids"] = sorted(skin_v)
    # skin must cover the refined / propagated trunk muscles (flank)
    trunk_mus = {k: newv.get(k, d["v"]) for k, d in by_id.items() if d["cat"] == "muscle" and in_scope(d) and not ARM_STRUCT.search(k)}
    skin_v = skin_cover_muscles(skin_after_sm, skin_v, trunk_mus, axis, axis, chart, log=log)
    newv.update(skin_v)
    # envelope clamp: every other trunk structure inside the fitted skin
    cur = {d["id"]: {**d, "v": newv.get(d["id"], d["v"])} for d in structs}
    env = SkinEnvelope([cur[k] for k in skin_v], axis)
    ids = [k for k, d in cur.items() if d["cat"] in ("muscle", "fascia", "tendon", "nerve", "vessel", "bursa", "ligament") and not ARM_STRUCT.search(k)
           and not CNS_STRUCT.search(k)
           and -150 < d["v"].mean(0)[1] < 650 and abs(d["v"].mean(0)[0]) < 200]
    cl = envelope_clamp(cur, ids, env, axis)
    skipped = []
    for k, (v, nmv, mx) in list(cl.items()):
        d = by_id[k]
        # shape guard: a structure that the clamp would distort (> 6 points more triangles outside 0.67-1.5x) is left where it was
        if k not in set(new) and Mx.distortion_score(Mx.stretch_stats(v, d["r"], d["f"])) > Mx.distortion_score(Mx.stretch_stats(cur[k]["v"], d["r"], d["f"])) + 6.0:
            skipped.append(k)
            del cl[k]
            continue
        newv[k] = v
    rep["envelope_clamp_skipped_for_shape"] = skipped
    # thin structures must not end up deeper inside her bone labels than they were in v6 (nerves leaving foramina keep their v6 contact)
    bg = {}
    for k, d in cur.items():
        if d["cat"] not in ("nerve", "vessel", "fascia", "tendon") or k not in newv or ARM_STRUCT.search(k) or guards is None or CNS_STRUCT.search(k):
            continue
        v0, v1 = d["v"], newv[k]
        sel = slice(None, None, max(1, len(v1) // 600))
        f0, f1 = float((guards.depth(v0[sel]) > 1).mean()), float((guards.depth(v1[sel]) > 1).mean())
        if f1 > f0 + 0.01:
            v2 = guards.push_out(v1, d["f"], tol=1.0)
            f2 = float((guards.depth(v2[sel]) > 1).mean())
            if f2 < f1:
                newv[k] = v2
                bg[k] = {"in_bone_before": round(f0, 3), "after_recovery": round(f1, 3), "after_guard": round(f2, 3)}
    rep["bone_guard_thin"] = bg
    log(f"  bone guard (thin structures): {len(bg)} structures pushed out of her bone labels")
    rep["envelope_clamp"] = {k: {"vertices": c[1], "max_mm": round(c[2], 1)} for k, c in cl.items()}
    newv.update(reweld_skin(structs, {k: newv[k] for k in skin_v}))
    log(f"  envelope clamp: {len(cl)} structures, {sum(c[1] for c in cl.values())} vertices")
    return newv, rep


# ------------------------------------------------------------------------------------------------ shape recovery of the rest
RECOVER_CATS = ("muscle", "fascia", "tendon", "ligament", "nerve", "vessel", "bursa", "lymphatic", "organ")
RECOVER_SIGMAS = (25.0, 50.0, 90.0)
RECOVER_MAX_DEV_MM = 15.0


def smooth_displacement(d, v, sigma):
    """v' = S0(raw) + (I + lam L)^-1 (v - S0(raw)): the structure's displacement from its own Z source shape (best similarity S0) is
    low-pass filtered over its mesh graph (diffusion length sigma mm), so the shear/stretch the global field put into it goes while its
    large-scale position stays.  Returns v'."""
    from scipy import sparse
    from scipy.sparse.linalg import splu
    r = d["r"].astype(np.float64)
    f = d["f"]
    T0 = umeyama(r, v)
    base = apply_sim(r, T0)
    u = v - base
    e = np.unique(np.sort(np.vstack([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]), axis=1), axis=0)
    h = float(np.median(np.linalg.norm(r[e[:, 0]] - r[e[:, 1]], axis=1))) * max(T0[0], 1e-3)
    lam = max((sigma / max(h, 1e-3)) ** 2 / 2.0, 0.0)
    n = len(v)
    A = sparse.coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(n, n))
    A = (A + A.T).tocsr()
    L = sparse.diags(np.asarray(A.sum(1)).ravel()) - A
    lu = splu((sparse.identity(n) + lam * L).tocsc())
    us = np.column_stack([lu.solve(u[:, k]) for k in range(3)])
    return base + us


def shape_recovery(structs, newv, skip_ids, log=print):
    """for every trunk/pelvis/hip/shoulder structure that has NO label of hers (not in skip_ids): pick the diffusion length (or none) that
    lowers its distortion score the most, accepting only an improvement >= 2 points and a vertex deviation <= RECOVER_MAX_DEV_MM"""
    from scripts.zanatomy import q190_audit as Au
    out, rep = {}, {}
    for d in structs:
        k = d["id"]
        if k in skip_ids or d["cat"] not in RECOVER_CATS or Au.HAND.search(k) or CNS_STRUCT.search(k) or Au.region_of(d) is None or len(d["f"]) < 30:
            continue
        v = newv.get(k, d["v"])
        s0 = Mx.distortion_score(Mx.stretch_stats(v, d["r"], d["f"]))
        if s0 < 4.0:
            continue
        best = (s0, None, None)
        for sg in RECOVER_SIGMAS:
            try:
                v2 = smooth_displacement(d, v, sg)
            except Exception:
                continue
            dev = float(np.linalg.norm(v2 - v, axis=1).max())
            sc = Mx.distortion_score(Mx.stretch_stats(v2, d["r"], d["f"]))
            if dev <= RECOVER_MAX_DEV_MM and sc < best[0] - 2.0:
                best = (sc, sg, v2)
                if sc < 4.0:
                    break
        if best[1] is not None:
            out[k] = best[2]
            rep[k] = {"sigma_mm": best[1], "score_before": round(s0, 1), "score_after": round(best[0], 1),
                      "max_dev_mm": round(float(np.linalg.norm(best[2] - v, axis=1).max()), 1)}
    log(f"  shape recovery: {len(out)} structures, mean distortion score {np.mean([r['score_before'] for r in rep.values()]):.1f} -> {np.mean([r['score_after'] for r in rep.values()]):.1f}" if rep else "  shape recovery: none")
    return out, rep


# ------------------------------------------------------------------------------------------------ neighbour overlap
def _vertex_normals(v, f):
    fn = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
    vn = np.zeros_like(v)
    for k in range(3):
        np.add.at(vn, f[:, k], fn)
    return vn / np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-9)


def _smooth_push(f, D, passes):
    from scipy import sparse
    moved = np.linalg.norm(D, axis=1) > 1e-6
    if not moved.any() or not passes:
        return D
    n = len(D)
    e = np.vstack([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
    A = sparse.coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(n, n)).tocsr()
    A = ((A + A.T) > 0).astype(float)
    deg = np.maximum(np.asarray(A.sum(1)).ravel(), 1)
    Ds = D.copy()
    for _ in range(passes):
        Ds = (A @ Ds) / deg[:, None]
        Ds[moved] = np.where((np.linalg.norm(Ds[moved], axis=1) > np.linalg.norm(D[moved], axis=1))[:, None], Ds[moved], D[moved])
    return Ds


CNS_STRUCT = re.compile(r"(spinal|spino|cortico|rubro|olivo|tecto|reticulo|vestibulo|posterolateral|solitary|lissauer)[a-z_]*tract|fasciculus|horn_of|funiculus|root_of_spinal|spinal_ganglion|spinal_reticular|central_canal|commissure|substantia|"
                        r"spinal_cord|lemniscus|decussation|gracile|cuneate|nucleus|cerebr|brain|ventric")      # inside the vertebral canal: follows her vertebrae, never the muscles


NOT_A_MUSCLE_BODY = re.compile(r"bursa|septum|fascia|aponeurosis|tendon|sheath|ligament|membrane|retinaculum|capsule|raphe|linea|lamina")


def resolve_overlaps(by_id, newv, ids, movable, iters=6, margin=0.5, max_move=8.0, smooth=6, revert_pts=3.0, log=print):
    """closed trunk muscles that interpenetrate (Z muscles fitted one by one to her non-overlapping labels): each vertex lying inside
    another muscle is moved out along that muscle's outward normal by half the depth + margin (the other muscle's inside vertices
    do the other half); the push is spread over the mesh (smooth passes).  Several iterations."""
    import trimesh
    closed = [k for k in ids if _closed(by_id[k]["f"]) and not NOT_A_MUSCLE_BODY.search(k)]
    movable = set(movable) & set(closed)
    start = {k: newv.get(k, by_id[k]["v"]).copy() for k in movable}
    tot0 = None
    for it in range(iters):
        cur = {k: newv.get(k, by_id[k]["v"]) for k in closed}
        info = {k: (cur[k].min(0), cur[k].max(0), cKDTree(cur[k]), _vertex_normals(cur[k], by_id[k]["f"]),
                    trimesh.Trimesh(cur[k], by_id[k]["f"], process=False)) for k in closed}
        disp = {k: np.zeros_like(cur[k]) for k in closed}
        n_in = 0
        for k in closed:
            if k not in movable:                  # only the refined muscles move; every other muscle is an obstacle
                continue
            v = cur[k]
            lo, hi = info[k][0], info[k][1]
            for j in closed:
                if j == k:
                    continue
                lj, hj, tj, nj, mj = info[j]
                if np.any(hj < lo - 1) or np.any(lj > hi + 1):
                    continue
                sel = np.flatnonzero(np.all((v >= lj - 1) & (v <= hj + 1), 1))
                if not len(sel):
                    continue
                try:
                    ins = mj.contains(v[sel])
                except Exception:
                    continue
                if not ins.any():
                    continue
                s2 = sel[ins]
                d, q = tj.query(v[s2])
                depth = np.einsum("ij,ij->i", v[s2] - cur[j][q], -nj[q])
                depth = np.maximum(depth, 0.0) + margin
                push = (0.6 if j in movable else 1.0) * np.minimum(depth, 2 * max_move)[:, None] * nj[q]
                bigger = np.linalg.norm(push, axis=1) > np.linalg.norm(disp[k][s2], axis=1)
                disp[k][s2[bigger]] = push[bigger]
                n_in += int(ins.sum())
        if tot0 is None:
            tot0 = n_in
        for k in movable & set(closed):
            if np.linalg.norm(disp[k], axis=1).max() > 0:
                D = _smooth_push(by_id[k]["f"], disp[k], smooth)
                m = np.linalg.norm(D, axis=1)
                D *= np.minimum(1.0, max_move / np.maximum(m, 1e-9))[:, None]
                newv[k] = cur[k] + D
        log(f"  overlap resolution iteration {it + 1}: {n_in} muscle vertices inside another muscle")
    # a muscle whose own shape gets more distorted by the push is put back where it was before the resolution
    reverted = []
    for k in movable:
        if k not in newv or np.abs(newv[k] - start[k]).max() < 1e-9:
            continue
        d = by_id[k]
        if Mx.distortion_score(Mx.stretch_stats(newv[k], d["r"], d["f"])) > Mx.distortion_score(Mx.stretch_stats(start[k], d["r"], d["f"])) + revert_pts:
            newv[k] = start[k]
            reverted.append(k)
    log(f"  overlap resolution: {len(reverted)} muscles reverted (shape got worse)")
    return {"vertices_inside_first_pass": tot0, "vertices_inside_last_pass": n_in, "reverted_for_shape": sorted(reverted)}


def reweld_skin(structs, skin_v):
    """the skin patches tile one surface: every set of vertices that shared a Z source position is put back on their common mean
    (the global field and the clamps left tears of up to 6 mm)"""
    skin = [d for d in structs if d["cat"] == "skin" and d["id"] in skin_v]
    allr = np.vstack([d["r"] for d in skin]).astype(np.float64)
    allv = np.vstack([skin_v[d["id"]] for d in skin]).astype(np.float64)
    u, inv = np.unique(np.round(allr, 2), axis=0, return_inverse=True)
    inv = inv.reshape(-1)
    cnt = np.bincount(inv)
    mean = np.zeros((len(u), 3)); np.add.at(mean, inv, allv); mean /= cnt[:, None]
    allv = np.where((cnt[inv] > 1)[:, None], mean[inv], allv)
    off = np.cumsum([0] + [len(d["r"]) for d in skin])
    return {d["id"]: allv[a:b] for d, a, b in zip(skin, off[:-1], off[1:])}


# ------------------------------------------------------------------------------------------------ build hook
def _vol_cm3(v, f):
    return abs(volume(v, f)) / 1000.0


def refine_pending(pending: list[dict], raw: dict, log=print) -> dict:
    """build hook (build_zan_atlas_viewer.py --q190-refine): runs run_all on the fitted pending meshes, applies the result, clamps once more
    inside her CT skin, badges every moved structure (fit_note) and returns the report (written into the build report json)."""
    from scripts.transfer.zan_to_vhf_whole_body import load_her_meshes
    from scripts.placement_sweep_q185 import Body
    from scripts.ribs_from_ct_labels import load_skin
    from scripts.zanatomy import trunk_refit_q186c as T
    from scripts.zanatomy import q190_audit as Au
    structs = [{"id": p["mesh_id"], "cat": p["cat"], "v": p["v"], "r": raw[p["mesh_id"]].astype(np.float64), "f": p["f"]} for p in pending]
    by_p = {p["mesh_id"]: p for p in pending}
    her = load_her_meshes()
    skin = load_skin("vhf")
    axis = T.trunk_axis(np.asarray(skin.vertices, np.float64))
    guards = Guards(Body("vhf"))
    before = Au.table(structs)
    newv, rep = run_all(structs, her, guards, skin, axis, log=log)
    for k, v in newv.items():
        by_p[k]["v"] = v
    clamp = T.clamp_inside_skin(pending, skin_mesh=skin, log=log)
    sk_ids = [p["mesh_id"] for p in pending if p["cat"] == "skin"]
    rew = reweld_skin([{"id": p["mesh_id"], "cat": "skin", "r": raw[p["mesh_id"]]} for p in pending if p["cat"] == "skin"],
                      {i: by_p[i]["v"] for i in sk_ids})
    for i, v in rew.items():
        by_p[i]["v"] = v
    for p in pending:
        p.pop("v_unclamped", None)
    structs_after = [{"id": p["mesh_id"], "cat": p["cat"], "v": p["v"], "r": raw[p["mesh_id"]].astype(np.float64), "f": p["f"]} for p in pending]
    after = Au.table(structs_after)
    v6 = {d["id"]: d for d in structs}
    out_struct = {}
    for k, b in before.items():
        a = after.get(k)
        if a is None:
            continue
        d = v6[k]
        moved = float(np.linalg.norm(by_p[k]["v"] - d["v"], axis=1).mean()) if len(d["v"]) else 0.0
        e = {"cat": b["cat"], "region": b["region"], "distortion_score_before": round(b["score"], 2), "distortion_score_after": round(a["score"], 2),
             "flipped_before": round(b["stretch"]["flipped"], 4), "flipped_after": round(a["stretch"]["flipped"], 4),
             "edge_p95_before": round(b["stretch"]["edge_p95"], 3), "edge_p95_after": round(a["stretch"]["edge_p95"], 3),
             "area_outside_0.67_1.5_before": round(b["stretch"]["area_frac_gt1.5"] + b["stretch"]["area_frac_lt0.67"], 4),
             "area_outside_0.67_1.5_after": round(a["stretch"]["area_frac_gt1.5"] + a["stretch"]["area_frac_lt0.67"], 4),
             "mean_move_mm": round(moved, 2)}
        if _closed(d["f"]):
            e["volume_cm3_v6"] = round(_vol_cm3(d["v"], d["f"]), 2)
            e["volume_cm3_q190"] = round(_vol_cm3(by_p[k]["v"], d["f"]), 2)
            e["volume_cm3_source_x_body_scale3"] = round(_vol_cm3(d["r"], d["f"]) * BODY_SCALE ** 3, 2)
        if k in rep["muscles"]:
            m = rep["muscles"][k]
            e["her_label"] = m["her_id"]
            e["her_label_chamfer_mm_before_after"] = [m["her_label_chamfer_before_mm"][2], m["after_mm"][2]]
            e["her_label_partial"] = m["partial_reference"]
        out_struct[k] = e
        note = None
        if k in rep["muscles"]:
            m = rep["muscles"][k]
            note = (f" Q190: refined onto her own CT-derived {m['her_id'].replace('_', ' ')} (her TotalSegmentator/own mesh is only the reference, the shape is "
                    f"this Z-Anatomy mesh): two-way median distance to her label {m['her_label_chamfer_before_mm'][2]} -> {m['after_mm'][2]} mm"
                    f"{' (her label covers only part of this muscle)' if m['partial_reference'] else ''}; {m['pose']} fit + smooth residual "
                    f"<= {m['resid_max_mm']} mm; triangles stretched outside 0.67-1.5x of the Z source {100 * e['area_outside_0.67_1.5_before']:.0f} % -> "
                    f"{100 * e['area_outside_0.67_1.5_after']:.0f} %"
                    + (f"; volume {e['volume_cm3_v6']} -> {e['volume_cm3_q190']} cm3." if "volume_cm3_v6" in e else "."))
        elif k in rep["shape_recovery"]:
            sr = rep["shape_recovery"][k]
            note = (f" Q190: global-field shear removed (displacement low-passed over its own mesh, {sr['sigma_mm']:.0f} mm), position kept within "
                    f"{sr['max_dev_mm']} mm; triangles stretched outside 0.67-1.5x {100 * e['area_outside_0.67_1.5_before']:.0f} % -> "
                    f"{100 * e['area_outside_0.67_1.5_after']:.0f} %.")
        elif k in rep["propagated"]:
            note = f" Q190: moved with the neighbouring refined muscles (mean {moved:.1f} mm)."
        elif b["cat"] == "skin" and moved > 1.0:
            note = (f" Q190: back/flank skin: displacement smoothed, set on her measured CT back outline (1.5 mm inside it) and moved out over her refined "
                    f"muscles where they reached the old skin; mean move {moved:.1f} mm; front untouched.")
        if k in rep["envelope_clamp"] and rep["envelope_clamp"][k]["vertices"] >= 5:
            c = rep["envelope_clamp"][k]
            note = (note or "") + f" Q190: {c['vertices']} vertices outside the fitted skin were moved inside it (max {c['max_mm']} mm)."
        if note:
            by_p[k]["fit_note"] = (by_p[k].get("fit_note") or "") + note
    return {"rule": "scripts/zanatomy/q190_refine.py", "refine": {k: v for k, v in rep.items() if k not in ("muscles", "propagated", "shape_recovery", "envelope_clamp", "skin_ids")},
            "muscle_groups": {k: v for k, v in rep["muscles"].items()},
            "propagated": rep["propagated"], "shape_recovery": rep["shape_recovery"], "envelope_clamp": rep["envelope_clamp"],
            "clamp_inside_her_skin": {k: v for k, v in clamp.items() if k != "per_structure"}, "structures": out_struct}
