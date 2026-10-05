"""Q191: hand / wrist of the female Z-Anatomy viewer, fitted onto HER own hand (build hook --q191-hand).

Order (all on the full-resolution `pending` meshes, after the Q190 refinement, before the Q162 gap closure and the decimation):
 1. bones: every Z carpal / metacarpal / phalanx is fitted (similarity, bounded, then a small bounded smooth residual) onto her own
    CT hand bone meshes (carpals_r, metacarpal_1..5_r, phalanges_hand_r; her composites are split by nearest fitted Z piece).
 2. soft tissue: one bone-anchored smooth field (inverse-distance blend of the per-bone similarity maps, computed from the Z SOURCE
    shape, forearm bones as identity anchors) x an axial taper that is 0 well up the forearm: no seam.
 3. per structure: muscles she has a CT label of (hand intrinsics) are refined onto it (scripts/zanatomy/q190_refine.refine_group);
    all others stay on the field and are only constrained (out of bone, inside her skin).
 4. hand skin patches are set onto her CT hand skin where it lies within reach; welded seams.
 5. guards: volume 0.65-1.5x of source, fold (Jacobian / flipped faces), out of bone, inside her skin.
Left hand: her CT has no left hand bones (see PROJECT_STATE Q191); it is placed from her right hand only when `LEFT_MIRROR` validated it.
"""
from __future__ import annotations

import re

import numpy as np
from scipy.spatial import cKDTree

from scripts.zanatomy import q190_metrics as Mx
from scripts.zanatomy import q190_refine as Q

CARPALS = ("scaphoid", "lunate", "triquetrum", "pisiform", "trapezium", "trapezoid", "capitate", "hamate")
ORD = ("first", "second", "third", "fourth", "fifth")
BODY_SCALE = Mx.BODY_SCALE


def bone_ids(s: str) -> dict:
    """{'carpals': [...], 'mc': [...], 'phal': [...]} Z mesh ids of one hand (s = 'r'|'l')"""
    ph = [f"zan_{p}_phalanx_of_{o}_finger_of_hand_{s}" for o in ORD for p in ("proximal", "middle", "distal") if not (p == "middle" and o == "first")]
    return {"carpals": [f"zan_{c}_bone_{s}" for c in CARPALS], "mc": [f"zan_{o}_metacarpal_bone_{s}" for o in ORD], "phal": ph}


# her CT bone mesh each Z hand bone group is fitted to (right hand only: she has no left hand bones)
HER_BONES = {"carpals": "carpals_r", "phal": "phalanges_hand_r", **{f"mc{k}": f"metacarpal_{k}_r" for k in range(1, 6)}}
HER_FOREARM_BONES = ("radius_r", "ulna_r")


# ------------------------------------------------------------------------------------------------ geometry helpers
def kabsch(src, dst, w=None, scale=False):
    """similarity (s,R,t) with dst ~ s R src + t (weighted)"""
    w = np.ones(len(src)) if w is None else np.asarray(w, float)
    w = w / w.sum()
    cs, cd = (src * w[:, None]).sum(0), (dst * w[:, None]).sum(0)
    A, B = src - cs, dst - cd
    H = (A * w[:, None]).T @ B
    U, S, Vt = np.linalg.svd(H)
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    D = np.diag([1, 1, d])
    R = Vt.T @ D @ U.T
    s = float((S * np.diag(D)).sum() / (w * (A ** 2).sum(1)).sum()) if scale else 1.0
    return s, R, cd - s * R @ cs


def apply_T(T, P):
    s, R, t = T
    return s * P @ R.T + t


def rot_deg(R):
    return float(np.degrees(np.arccos(np.clip((np.trace(R) - 1) / 2, -1, 1))))


def limit_T(T, T0, max_rot=20.0, scale_rng=(0.85, 1.2), P=None, max_shift=7.0):
    """clip a similarity T to within `max_rot` deg of T0, scale within `scale_rng` x T0's, mean point shift <= max_shift (interpolated back)"""
    from scipy.spatial.transform import Rotation as Rot
    s, R, t = T
    s0, R0, t0 = T0
    rv = Rot.from_matrix(R @ R0.T).as_rotvec()
    a = np.linalg.norm(rv)
    lim = np.radians(max_rot)
    if a > lim:
        rv *= lim / a
    R = Rot.from_rotvec(rv).as_matrix() @ R0
    s = float(np.clip(s, scale_rng[0] * s0, scale_rng[1] * s0))
    if P is not None:
        c = P.mean(0)
        # keep the centroid motion bounded (translation is free of the others)
        base = apply_T(T0, c)
        cur = s * R @ c + t
        sh = np.linalg.norm(cur - base)
        if sh > max_shift:
            t = t - (cur - base) * (1 - max_shift / sh)
    return s, R, t


class Inside:
    """approximate signed inside test of a (closed or nearly closed) mesh: nearest surface sample + its outward face normal.
    Samples are dense (about one per mm), so the sign is right to ~the sample spacing; used for her bone meshes and the fitted Z bones."""

    def __init__(self, v, f, spacing=0.8):
        v = np.asarray(v, float)
        fn = np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])
        area = 0.5 * np.linalg.norm(fn, axis=1)
        sgn = 1.0 if Q.volume(v, f) >= 0 else -1.0
        fn = sgn * fn / np.maximum(2 * area, 1e-12)[:, None]
        n = int(min(60000, max(2000, area.sum() / spacing ** 2)))
        rng = np.random.default_rng(0)
        idx = rng.choice(len(f), n, p=area / area.sum())
        u = rng.random((n, 2)); m = u.sum(1) > 1; u[m] = 1 - u[m]
        t = v[f[idx]]
        self.pts = t[:, 0] + u[:, :1] * (t[:, 1] - t[:, 0]) + u[:, 1:] * (t[:, 2] - t[:, 0])
        self.n = fn[idx]
        self.tree = cKDTree(self.pts)

    def depth(self, P):
        """>0 inside (mm below the surface), <0 outside"""
        d, j = self.tree.query(P)
        s = np.einsum("ij,ij->i", P - self.pts[j], self.n[j])
        return np.where(s < 0, d, -d)

    def push_dir(self, P):
        d, j = self.tree.query(P)
        return self.n[j]


def surf_pts(v, f, n=4000, seed=0):
    return Mx.surf_samples(v, f, n, np.random.default_rng(seed))


def chamfer2(A, B):
    """two-way median of the nearest distances between two point sets (mm): (A->B, B->A, mean)"""
    a = float(np.median(cKDTree(B).query(A)[0]))
    b = float(np.median(cKDTree(A).query(B)[0]))
    return a, b, 0.5 * (a + b)


# ------------------------------------------------------------------------------------------------ bones
def fit_pieces(pieces: dict, ref_pts: np.ndarray, composite: bool, iters=10, max_rot=20.0, max_shift=7.0, scale_rng=(0.85, 1.2), spring=0.15,
               cap=14.0, trim=0.85):
    """pieces {id: {"r": raw verts, "v": current verts, "f": faces}}  ->  {id: (s,R,t)} raw -> her frame.
    composite: her mesh holds several of the pieces (carpals, phalanges): its samples are split between the pieces by the nearest fitted piece
    surface at every iteration (so one carpal can not take its neighbour's surface)."""
    ids = list(pieces)
    T0 = {k: kabsch(pieces[k]["r"], pieces[k]["v"], scale=True) for k in ids}
    T = dict(T0)
    samp = {k: surf_pts(pieces[k]["r"], pieces[k]["f"], 1500, seed=i) for i, k in enumerate(ids)}   # raw-frame samples
    for it in range(iters):
        cur = {k: apply_T(T[k], samp[k]) for k in ids}
        if composite:
            allp = np.vstack([cur[k] for k in ids])
            lab = np.concatenate([np.full(len(cur[k]), i) for i, k in enumerate(ids)])
            d, j = cKDTree(allp).query(ref_pts)
            owner = lab[j]
            own_ok = d <= cap
        newT = {}
        for i, k in enumerate(ids):
            S = ref_pts[(owner == i) & own_ok] if composite else ref_pts
            if len(S) < 30:
                newT[k] = T[k]
                continue
            tr = cKDTree(S)
            d1, i1 = tr.query(cur[k])
            keep1 = d1 <= min(np.quantile(d1, trim), cap)
            d2, i2 = cKDTree(cur[k]).query(S)
            keep2 = d2 <= min(np.quantile(d2, trim), cap)
            src = np.vstack([samp[k][keep1], samp[k][i2[keep2]]])
            dst = np.vstack([S[i1[keep1]], S[keep2]])
            w = np.ones(len(src))
            # spring to the Q168 pose (carries the slide along the shaft that her surface can not see)
            src = np.vstack([src, samp[k]]); dst = np.vstack([dst, apply_T(T0[k], samp[k])])
            w = np.concatenate([w, np.full(len(samp[k]), spring * len(w) / len(samp[k]))])
            Tn = kabsch(src, dst, w, scale=True)
            newT[k] = limit_T(Tn, T0[k], max_rot, scale_rng, P=samp[k], max_shift=max_shift)
        T = newT
    cur = {k: apply_T(T[k], samp[k]) for k in ids}
    if composite:
        allp = np.vstack([cur[k] for k in ids])
        lab = np.concatenate([np.full(len(cur[k]), i) for i, k in enumerate(ids)])
        d, j = cKDTree(allp).query(ref_pts)
        owner = np.where(d <= cap, lab[j], -1)
        assigned = {k: ref_pts[owner == i] for i, k in enumerate(ids)}
    else:
        assigned = {k: ref_pts for k in ids}
    return T, T0, assigned


def bone_residual(raw_new, f, ref_pts, cap=3.5):
    """small bounded smooth residual of one fitted bone toward her samples (Q190 residual_fit, fold guard inside)"""
    class _R:
        pass
    r = _R()
    r.pts = ref_pts
    r.tree = cKDTree(ref_pts)
    X, diag = Q.residual_fit(raw_new, r, cap=cap, iters=3)
    return X, diag


# ------------------------------------------------------------------------------------------------ soft-tissue field
def smoothstep(x):
    x = np.clip(x, 0.0, 1.0)
    return x * x * (3 - 2 * x)


class HandMap:
    """raw (Z source) points -> her frame by an inverse-distance blend of the per-bone similarity maps (hand bones: the Q191 fits; the distal
    radius / ulna: their Q168 maps, as identity-like anchors).  Distances are measured to the Z SOURCE bone surfaces, so the field is built
    from the source shape (no stacking on the Q168 / Q190 result)."""

    def __init__(self, bone_raw: dict, T: dict, soft=2.5, power=2.5, k=6):
        self.ids = list(bone_raw)
        self.T = [T[b] for b in self.ids]
        self.trees = [cKDTree(bone_raw[b]) for b in self.ids]
        self.soft, self.power, self.k = soft, power, k

    def map(self, X):
        X = np.asarray(X, float)
        D = np.stack([t.query(X)[0] for t in self.trees], 1)
        W = (D + self.soft) ** -self.power
        if self.k < W.shape[1]:
            thr = np.sort(W, 1)[:, -self.k][:, None]
            W = np.where(W >= thr, W, 0.0)
        W /= W.sum(1, keepdims=True)
        out = np.zeros_like(X)
        for j, T in enumerate(self.T):
            sel = W[:, j] > 0
            if sel.any():
                out[sel] += W[sel, j][:, None] * apply_T(T, X[sel])
        return out


def wrist_frame(raw_radius: np.ndarray):
    """(c_w, u): Z-source wrist point (distal end of the radius) and the unit forearm axis pointing toward the hand"""
    c = raw_radius.mean(0)
    X = raw_radius - c
    u = np.linalg.svd(X, full_matrices=False)[2][0]
    s = X @ u
    if s[X[:, 1] < np.percentile(X[:, 1], 10)].mean() < 0:      # the hand is toward lower y in the Z frame
        u = -u
    if u[1] > 0:
        u = -u
    s = X @ u
    return c + u * np.percentile(s, 98), u


TAPER_PROX_MM, TAPER_FULL_MM = 62.0, 12.0      # axial taper: 0 this far up the forearm from the wrist, 1 this far before it
GATE_NEAR_MM, GATE_FAR_MM = 85.0, 125.0        # a vertex further than this from the Z hand/forearm bones of its side is not a hand vertex


def field_weight(Xraw, c_w, u, near_tree):
    s = (Xraw - c_w) @ u
    tau = smoothstep((s + TAPER_PROX_MM) / (TAPER_PROX_MM - TAPER_FULL_MM))
    d = near_tree.query(Xraw)[0]
    gate = 1.0 - smoothstep((d - GATE_NEAR_MM) / (GATE_FAR_MM - GATE_NEAR_MM))
    return tau * gate


BONE_VOLUME = (0.80, 1.25)


def fit_hand_bones(by_id: dict, raw: dict, her: dict, side="r", log=print, skin=None):
    """Z hand bones of `side` -> her CT hand bones.  Returns (new_v {id: verts}, T {id: (s,R,t) raw->her frame, before the residual}, report)"""
    ids = bone_ids(side)
    new_v, Tout, rep = {}, {}, {}

    def piece(i):
        return {"r": raw[i].astype(float), "v": by_id[i]["v"].astype(float), "f": by_id[i]["f"]}

    groups = [("carpals", ids["carpals"], her[HER_BONES["carpals"]], True, dict(max_rot=14.0, max_shift=6.0, scale_rng=(0.93, 1.08))),
              ("phalanges", ids["phal"], her[HER_BONES["phal"]], True, dict(max_rot=18.0, max_shift=8.0, scale_rng=(0.93, 1.08)))]
    groups += [(f"mc{k + 1}", [ids["mc"][k]], her[HER_BONES[f"mc{k + 1}"]], False, dict(max_rot=15.0, max_shift=8.0, scale_rng=(0.93, 1.08))) for k in range(5)]
    for name, zids, hm, comp, kw in groups:
        ref_pts = surf_pts(hm["v"].astype(float), hm["f"], 7000 if comp else 3500)
        pcs = {i: piece(i) for i in zids}
        T, T0, assigned = fit_pieces(pcs, ref_pts, comp, **kw)
        cur_all, new_all = [], []
        for i in zids:
            P = pcs[i]
            X1 = apply_T(T[i], P["r"])
            S = assigned[i]
            before = chamfer2(surf_pts(P["v"], P["f"], 2500), S) if len(S) > 30 else (np.nan,) * 3
            X2, diag = (X1, {"amp": 0.0, "resid_max_mm": 0.0}) if len(S) <= 60 else bone_residual(X1, P["f"], S, cap=3.0)
            vol_src = abs(Q.volume(P["r"], P["f"])) * BODY_SCALE ** 3
            vr = abs(Q.volume(X2, P["f"])) / vol_src if vol_src > 1e-6 else 1.0
            if not (BONE_VOLUME[0] <= vr <= BONE_VOLUME[1]):
                T[i] = T0[i]; X2 = apply_T(T0[i], P["r"])
                vr = abs(Q.volume(X2, P["f"])) / vol_src
            after = chamfer2(surf_pts(X2, P["f"], 2500), S) if len(S) > 30 else (np.nan,) * 3
            ref_tree = cKDTree(ref_pts)
            z0 = float(np.median(ref_tree.query(surf_pts(P["v"], P["f"], 1500))[0]))
            z1 = float(np.median(ref_tree.query(surf_pts(X2, P["f"], 1500))[0]))
            if len(S) < 150 or z1 > z0 - 0.1 or after[2] > before[2] - 0.15:      # keep the Q168 placement unless the fit gains (assigned samples AND her whole mesh)
                T[i] = T0[i]; X2 = apply_T(T0[i], P["r"]); after = before
                vr = abs(Q.volume(X2, P["f"])) / vol_src
                diag = {"amp": 0.0, "resid_max_mm": 0.0, "held": "no gain over the Q168 placement on her mesh"}
            new_v[i] = X2
            Tout[i] = T[i]
            rep[i] = {"her_ref": HER_BONES["carpals" if name == "carpals" else "phal" if name == "phalanges" else name],
                      "assigned_samples": int(len(S)), "chamfer_mm_before": [round(x, 2) for x in before], "chamfer_mm_after": [round(x, 2) for x in after],
                      "scale_vs_q168": round(T[i][0] / T0[i][0], 3), "rot_deg_vs_q168": round(rot_deg(T[i][1] @ T0[i][1].T), 1),
                      "volume_ratio_vs_source": round(vr, 3), "resid_max_mm": diag.get("resid_max_mm"), **({"note": diag["held"]} if "held" in diag else {})}
            cur_all.append(surf_pts(P["v"], P["f"], 800)); new_all.append(surf_pts(X2, P["f"], 800))
        a0, a1 = chamfer2(np.vstack(cur_all), ref_pts), chamfer2(np.vstack(new_all), ref_pts)
        log(f"  Q191 bones {name}: two-way median to her mesh {a0[2]:.2f} -> {a1[2]:.2f} mm")
        rep[f"_group_{name}"] = {"before_mm": [round(x, 2) for x in a0], "after_mm": [round(x, 2) for x in a1]}
    # her CT skin is the envelope: a bone more than 2 % outside it is translated (bounded) toward the inside, if that does not move it off her bone mesh
    if skin is not None:
        from trimesh.proximity import closest_point
        allref = {k: cKDTree(surf_pts(her[HER_BONES[("carpals" if k in ids["carpals"] else "phal" if k in ids["phal"] else f"mc{ids['mc'].index(k) + 1}")]]["v"].astype(float),
                                      her[HER_BONES[("carpals" if k in ids["carpals"] else "phal" if k in ids["phal"] else f"mc{ids['mc'].index(k) + 1}")]]["f"], 5000)) for k in new_v}
        for k, X in list(new_v.items()):
            for _ in range(3):
                out = ~skin.contains(X)
                if out.mean() <= 0.02:
                    break
                cp, _, tri = closest_point(skin, X[out])
                push = (cp - 1.0 * skin.face_normals[tri]) - X[out]
                t = np.clip(0.8 * push.mean(0), -4.0, 4.0)
                X2 = X + t
                if np.median(allref[k].query(X2[::2])[0]) > np.median(allref[k].query(X[::2])[0]) + 1.5 or (~skin.contains(X2)).mean() >= out.mean():
                    break
                X = X2
            if X is not new_v[k]:
                shift = float(np.linalg.norm(X.mean(0) - new_v[k].mean(0)))
                if shift > 0.05:
                    rep[k]["skin_nudge_mm"] = round(shift, 2)
                    rep[k]["outside_her_skin_pct_after_nudge"] = round(100 * float((~skin.contains(X)).mean()), 1)
                new_v[k] = X
    for k in new_v:
        Tout[k] = kabsch(raw[k], new_v[k], scale=True)
    return new_v, Tout, rep


# ------------------------------------------------------------------------------------------------ scope
HAND_NAME = re.compile(r"hand|manus|digit|palm|pollic|carpal|carpi|metacarp|lumbric|interossei|thenar|retinac|wrist|radiocarp|scaphoid|lunate|triquetr|"
                       r"trapez|capitate|hamate|pisif|pisot|opponens|flexor_|extensor_|palmaris|antebrach|forearm|radial|ulnar|median_|interosseous|"
                       r"pronator|brachioradialis|cruciform|synovial|perionyx|foveola|nail|ulnolunate|ulnocapitate|ulnotriquetral|scapho|"
                       r"radioscapho|triquetro|articular_disc_of_distal_radio|common_flexor|tendon_sheath|abd_pollicis|supinator|anconeus|annular")
SIDE_RE = re.compile(r"_([rl])(_\d+)?$")
SKIN_HAND = re.compile(r"^zan_skin_.*(forearm|wrist|hand|digits_of_hand|palm|perionyx|radial_foveola)")
SOFT_PUSH_CATS = ("muscle", "nerve", "vessel", "lymphatic", "tendon", "fascia")      # pushed out of bone; ligaments/capsules/sheaths attach to it
NOT_BODY = Q.NOT_A_MUSCLE_BODY
FOOT_NAME = re.compile(r"foot|plantar|hallucis|digitorum_(brevis|longus)|fibular|peroneal|tibial|calcaneo|talo|cune|cuboid|navicular|metatars|tarsal|toe")


def side_of(i: str):
    m = SIDE_RE.search(i)
    return m.group(1) if m else None


def scope(pending: list[dict], regions: dict, side: str) -> list[str]:
    """ids of the non-bone structures of one side that may sit in the wrist / hand (the field and the gate decide where they move)"""
    out = []
    for p in pending:
        i = p["mesh_id"]
        if side_of(i) != side or p["cat"] == "bone" or FOOT_NAME.search(i):
            continue
        if regions.get(i) == "forearm_hand" or HAND_NAME.search(i) or SKIN_HAND.search(i):
            out.append(i)
    return out


def hand_component_mask(raw_v: np.ndarray, near_tree, thr=GATE_NEAR_MM):
    """vertices within `thr` mm (Z source frame) of the Z hand/forearm bones of the side: the hand part of a mesh that also holds a foot part"""
    return near_tree.query(raw_v)[0] < thr


def submesh(v, f, mask):
    keep = mask[f].all(1)
    idx = -np.ones(len(v), int)
    idx[np.flatnonzero(mask)] = np.arange(mask.sum())
    return v[mask], idx[f[keep]], np.flatnonzero(mask)


# ------------------------------------------------------------------------------------------------ guards
def _adj(f, n):
    from scipy import sparse
    e = np.vstack([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
    A = sparse.coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(n, n)).tocsr()
    return ((A + A.T) > 0).astype(float)


def fold_stats(v, r, f):
    """rotation-free fold measure (the Q190 'flipped' fraction compares normals in the global frame, which is meaningless for a hand whose
    pose differs from the Z source by tens of degrees): share of INTERIOR EDGES whose dihedral angle turned from < 60 deg (smooth in the Z
    source) to > 100 deg (folded over) in the fitted mesh"""
    if len(f) == 0:
        return 0.0

    def fnorm(x):
        n = np.cross(x[f[:, 1]] - x[f[:, 0]], x[f[:, 2]] - x[f[:, 0]])
        return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)

    ns, nn = fnorm(r), fnorm(v)
    e = np.vstack([np.c_[f[:, 0], f[:, 1], np.arange(len(f))], np.c_[f[:, 1], f[:, 2], np.arange(len(f))], np.c_[f[:, 2], f[:, 0], np.arange(len(f))]])
    key = np.sort(e[:, :2], 1)
    order = np.lexsort((key[:, 1], key[:, 0]))
    k, fi = key[order], e[order, 2]
    same = (k[1:] == k[:-1]).all(1)
    a, b = fi[:-1][same], fi[1:][same]
    if not len(a):
        return 0.0
    cs, cn = (ns[a] * ns[b]).sum(1), (nn[a] * nn[b]).sum(1)
    sel = cs > 0.5
    return float((cn[sel] < -0.17).mean()) if sel.any() else 0.0


def vol_ratio(v, r, f):
    if not Q._closed(f):
        return None
    vs = abs(Q.volume(r, f)) * BODY_SCALE ** 3
    return abs(Q.volume(v, f)) / vs if vs > 1e-6 else None


def struct_metrics(v, r, f, ctx, active=None):
    """the numbers a hand structure's badge states: share of its (active) vertices outside her skin / inside her CT bone meshes / inside the
    displayed Z hand bones, stretch vs the Z source, folded edges, volume ratio"""
    a = np.ones(len(v), bool) if active is None else active
    if not a.any():
        a = np.ones(len(v), bool)
    P = v[a]
    out = {"outside_her_skin_pct": round(100 * float((~ctx.skin_contains(P)).mean()), 2)}
    if ctx.her_bones:
        out["inside_her_bone_pct"] = round(100 * float((np.max([b.depth(P) for b in ctx.her_bones], 0) > 1.5).mean()), 2)
    if ctx.z_bones:
        out["inside_z_bone_pct"] = round(100 * float((np.max([b.depth(P) for b in ctx.z_bones], 0) > 1.5).mean()), 2)
    st = Mx.stretch_stats(v, r, f)
    if st:
        out["stretch_area_outside_0.67_1.5_pct"] = round(100 * (st["area_frac_gt1.5"] + st["area_frac_lt0.67"]), 1)
        out["edge_outside_0.67_1.5_pct"] = round(100 * (st["edge_frac_gt1.5"] + st["edge_frac_lt0.67"]), 1)
    out["folded_edges_pct"] = round(100 * fold_stats(v, r, f), 2)
    vr_ = vol_ratio(v, r, f)
    if vr_ is not None:
        out["volume_ratio_vs_source"] = round(vr_, 3)
    return out


def push_out_of_bones(v, f, bones, active, tol=1.5, max_move=7.0, iters=3, passes=8):
    """vertices > tol mm inside a bone are moved out along that bone's surface normal, the push is spread over the mesh"""
    P0 = v.copy()
    P = v.copy()
    for _ in range(iters):
        dep = np.full(len(P), -1e9)
        dirn = np.zeros_like(P)
        for b in bones:
            d = b.depth(P)
            better = d > dep
            dep = np.where(better, d, dep)
            if better.any():
                dirn[better] = b.push_dir(P[better])
        ins = active & (dep > tol)
        if not ins.any():
            break
        step = np.minimum(dep[ins] - tol + 0.4, max_move)[:, None]
        P[ins] = P[ins] + dirn[ins] * step
    D = Q._smooth_push(f, P - P0, passes)
    return P0 + D


def clamp_inside_skin(v, f, active, skin, tree, margin=1.0, max_move=14.0):
    from trimesh.proximity import closest_point
    from scripts.zanatomy import trunk_refit_q186c as T186
    idx = np.flatnonzero(active & (tree.query(v)[0] < 45.0))
    if not len(idx):
        return v
    out = idx[~skin.contains(v[idx])]
    if not len(out):
        return v
    cp, _, tri = closest_point(skin, v[out])
    tgt = cp - margin * skin.face_normals[tri]
    mv = np.linalg.norm(tgt - v[out], axis=1)
    ok = mv <= max_move
    new = v.copy()
    new[out[ok]] = tgt[ok]
    return T186._smooth_clamp(v, new, f, skin)


class Ctx:
    def __init__(self, skin, skin_tree, her_bones=(), z_bones=()):
        self.skin, self.skin_tree = skin, skin_tree
        self.her_bones, self.z_bones = list(her_bones), list(z_bones)
        self._sc_cache = {}

    def skin_contains(self, P):
        return self.skin.contains(P)


# ------------------------------------------------------------------------------------------------ skin
SKIN_METHOD = "rbf"
SKIN_DATA_W = 0.5
SKIN_CAP = 14.0
SKIN_SMOOTH = 30


def set_skin_onto_her(patches, skin, skin_vn, skin_tree, bone_pts, cap=None, inset=0.8, cos_min=0.5, smooth=None):
    """hand skin patches (tile one surface; seam vertices share their Z source position) -> her CT skin.  A vertex follows her surface only
    where her surface is within `cap` mm AND faces the same way (normal agreement; the palm against her thigh finds the thigh's far side
    otherwise); every other vertex takes the smoothed displacement of the welded graph.  Returns {id: new v}, stats"""
    cap = SKIN_CAP if cap is None else cap
    smooth = SKIN_SMOOTH if smooth is None else smooth
    inv, A, deg, n, off = Q._welded(patches)
    allv = np.vstack([p["v"] for p in patches]).astype(float)
    N = np.zeros_like(allv)
    for p, a, b in zip(patches, off[:-1], off[1:]):
        N[a:b] = Q._vertex_normals(p["v"].astype(float), p["f"])
    bt = cKDTree(bone_pts)
    d_b, j_b = bt.query(allv)
    N *= np.where(np.einsum("ij,ij->i", allv - bone_pts[j_b], N) < 0, -1.0, 1.0)[:, None]      # outward = away from the hand bones
    d, j = skin_tree.query(allv)
    nh = skin_vn[j]
    p_h = np.asarray(skin.vertices)[j]
    s = np.einsum("ij,ij->i", allv - p_h, nh)
    gate = (d <= cap * 1.2) & (np.abs(s) <= cap) & (np.einsum("ij,ij->i", N, nh) > cos_min)
    step = -(s + inset)[:, None] * nh
    # a vertex OUTSIDE her skin is wrong whichever way her surface faces: it goes to the closest point of her surface (inset mm inside)
    from trimesh.proximity import closest_point
    near = d <= 40.0
    out = np.zeros(len(allv), bool)
    out[near] = ~skin.contains(allv[near])
    oi = np.flatnonzero(out)
    if len(oi):
        cp, _, tri = closest_point(skin, allv[oi])
        tgt = cp - inset * skin.face_normals[tri]
        mv = np.linalg.norm(tgt - allv[oi], axis=1)
        ok = mv <= cap * 1.2
        gate[oi[ok]] = True
        gate[oi[~ok]] = False
        step[oi[ok]] = (tgt - allv[oi])[ok]
    U = np.zeros((n, 3)); G = np.zeros(n); cnt = np.zeros(n)
    np.add.at(U, inv, np.where(gate[:, None], step, 0.0))
    np.add.at(G, inv, gate.astype(float)); np.add.at(cnt, inv, 1.0)
    fixed = G > 0.5 * cnt
    U = np.where(fixed[:, None], U / np.maximum(G, 1)[:, None], 0.0)
    Us = U.copy()
    for _ in range(smooth):        # data term 0.5 on the vertices that found her surface: the displacement stays smooth (no crumpling)
        Us = np.where(fixed[:, None], SKIN_DATA_W * U + (1 - SKIN_DATA_W) * (A @ Us) / deg[:, None], (A @ Us) / deg[:, None])
    dlt = Us[inv]
    dlt *= np.minimum(1.0, cap / np.maximum(np.linalg.norm(dlt, axis=1), 1e-9))[:, None]
    new = allv + dlt
    out = {p["id"]: new[a:b] for p, a, b in zip(patches, off[:-1], off[1:])}
    return out, {"gated_vertex_share": round(float(gate.mean()), 3), "moved_mean_mm": round(float(np.linalg.norm(dlt, axis=1).mean()), 2),
                 "moved_max_mm": round(float(np.linalg.norm(dlt, axis=1).max()), 2)}


def skin_normals(skin):
    return np.asarray(skin.vertex_normals, float)


# ------------------------------------------------------------------------------------------------ labelled muscles
def refine_small(members, ref, cap=6.0, spacing=9.0):
    """Q190 refine_group with the residual cap and RBF spacing of a hand muscle (the Q190 values are for trunk muscles)"""
    orig, old_sp = Q.residual_fit, Q.RBF_SPACING
    Q.residual_fit = lambda x1, ref_, **kw: orig(x1, ref_, **{"cap": cap, **kw})
    Q.RBF_SPACING = spacing
    try:
        return Q.refine_group(members, ref)
    finally:
        Q.residual_fit, Q.RBF_SPACING = orig, old_sp


# right hand: Z structure id -> her own CT/cryo label id (hand intrinsics she has a label of)
HAND_LABEL_GROUPS = {"hypothenar": ["abductor_digiti_minimi_hand_r", "flexor_digiti_minimi_brevis_hand_r", "opponens_digiti_minimi_r"],
                     "interossei": ["dorsal_interossei_hand_r", "palmar_interossei_r"], "adductor_pollicis": ["adductor_pollicis_r"]}
HAND_LABELS = {"abductor_digiti_minimi_hand_r": "abductor_digiti_minimi_hand_r", "adductor_pollicis_r": "adductor_pollicis_r",
               "dorsal_interossei_hand_r": "dorsal_interossei_hand_r", "palmar_interossei_r": "palmar_interossei_r",
               "flexor_digiti_minimi_brevis_hand_r": "flexor_digiti_minimi_brevis_hand_r", "opponens_digiti_minimi_r": "opponens_digiti_minimi_r"}


def merge_inside(objs):
    m = Inside.__new__(Inside)
    m.pts = np.vstack([o.pts for o in objs])
    m.n = np.vstack([o.n for o in objs])
    m.tree = cKDTree(m.pts)
    return m


def merged_bones(meshes):
    return merge_inside([Inside(v, f) for v, f in meshes])


def _fmt(x, nd=1):
    return "n/a" if x is None else f"{x:.{nd}f}"


def _guard_volume(v, r, f, active):
    """volume guard 0.65-1.5x of the Z source (x body scale^3) on the closed part of the structure that sits in the hand (the opponens mesh also
    holds a foot part: it is scaled about its own hand centroid, not the global one)"""
    if active.all():
        return Q.volume_guard(v, r, f)[0] if Q._closed(f) else v
    vs, fs, idx = submesh(v, f, active)
    if len(fs) < 20 or not Q._closed(fs):
        return v
    X, _ = Q.volume_guard(vs, r[idx], fs)
    out = v.copy()
    out[idx] = X
    return out


CAND_W = {"outside_her_skin_pct": 2.0, "inside_her_bone_pct": 2.0, "inside_z_bone_pct": 1.0, "stretch_area_outside_0.67_1.5_pct": 0.5, "folded_edges_pct": 3.0}


def cand_score(m, cat):
    """one number to choose between the candidate placements of a structure: containment first (outside her skin, inside bone), then distortion.
    Ligaments / capsules / sheaths attach to bone by design: their inside-bone share does not count."""
    s_ = 0.0
    for k, w in CAND_W.items():
        if k.startswith("inside") and cat in ("ligament", "joint", "bursa", "tendon"):
            continue
        s_ += w * m.get(k, 0.0)
    return s_


def run_side(side, by, raw, regions, her, skin, skin_tree, skin_vn, bone_new_v, bone_T, relax_sigma=8.0, log=print, label_refine=True, trace=None):
    """moves the hand/wrist structures of one side (bones already fitted: bone_new_v / bone_T); returns the per-structure report.
    Every structure gets up to four candidate placements (field only / field + shape relaxation, each with and without the bone / skin
    constraints) and keeps the one with the best containment-first score (see cand_score); the unmoved Q168 placement competes too."""
    ids_b = bone_ids(side)
    hb_ids = sum(ids_b.values(), [])
    rad, uln = f"radius_{side}", f"ulna_{side}"
    c_w, u = wrist_frame(raw[rad])
    bone_raw, T = {}, {}
    for i in hb_ids:
        bone_raw[i], T[i] = raw[i], bone_T[i]
    for i in (rad, uln):
        m = (raw[i] - c_w) @ u > -90.0
        bone_raw[i], T[i] = raw[i][m], kabsch(raw[i][m], by[i]["v"][m], scale=True)
    HM = HandMap(bone_raw, T)
    near_tree = cKDTree(np.vstack(list(bone_raw.values())))
    ids = scope([{"mesh_id": k, "cat": by[k]["cat"]} for k in by], regions, side)
    weights = {i: field_weight(raw[i].astype(float), c_w, u, near_tree) for i in ids}
    ids = [i for i in ids if weights[i].max() > 0.02]
    act = {i: weights[i] > 0.02 for i in ids}
    her_b = []
    if side == "r":
        her_b = [merged_bones([(her[k]["v"].astype(float), her[k]["f"].astype(int)) for k in list(HER_BONES.values()) + list(HER_FOREARM_BONES)])]
    zb_old = [merged_bones([(by[i]["v"].astype(float), by[i]["f"]) for i in hb_ids + [rad, uln]])]
    ctx0 = Ctx(skin, skin_tree, her_b, zb_old)
    before = {i: struct_metrics(by[i]["v"].astype(float), raw[i].astype(float), by[i]["f"], ctx0, act[i]) for i in ids}
    v0 = {i: by[i]["v"].astype(float).copy() for i in ids}
    # 1. bones
    for i in hb_ids:
        by[i]["v"] = bone_new_v[i]
    z_bones_new = merged_bones([(by[i]["v"].astype(float), by[i]["f"]) for i in hb_ids + [rad, uln]])
    ctx1 = Ctx(skin, skin_tree, her_b, [z_bones_new])
    # 2. field, and its shape-relaxed version (Q190 idea at hand scale; weighted by the field weight: forearm part and seam unchanged)
    cand = {i: {"field": None, "relax": None} for i in ids}
    for i in ids:
        Xn = HM.map(raw[i].astype(float))
        cand[i]["field"] = v0[i] + weights[i][:, None] * (Xn - v0[i])
        if relax_sigma and i not in HAND_LABELS:
            vs = Q.smooth_displacement({"r": raw[i].astype(float), "f": by[i]["f"]}, cand[i]["field"], relax_sigma)
            cand[i]["relax"] = cand[i]["field"] + weights[i][:, None] * (vs - cand[i]["field"])
    log(f"  Q191 {side}: field carried {len(ids)} structures")
    # 3. skin onto her skin (per variant; welded patches are processed together)
    sk_ids = [i for i in ids if by[i]["cat"] == "skin"]
    skin_rep = {}
    for var in ("field", "relax"):
        if not sk_ids or cand[sk_ids[0]][var] is None:
            continue
        patches = [{"id": i, "v": cand[i][var], "r": raw[i], "f": by[i]["f"]} for i in sk_ids]
        bone_pts = np.vstack([by[i]["v"][::2] for i in hb_ids + [rad, uln]])
        if SKIN_METHOD == "rbf":
            new, skin_rep[var] = set_skin_rbf(patches, skin, skin_tree)
        else:
            new, skin_rep[var] = set_skin_onto_her(patches, skin, skin_vn, skin_tree, bone_pts)
        for i in sk_ids:
            cand[i][var] = cand[i][var] + weights[i][:, None] * (new[i] - cand[i][var])
        rew = Q.reweld_skin([{"id": i, "cat": "skin", "r": raw[i]} for i in sk_ids], {i: cand[i][var] for i in sk_ids})
        for rnd in range(2):
            for i in sk_ids:
                cand[i][var] = clamp_inside_skin(rew[i], by[i]["f"], act[i], skin, skin_tree, margin=0.8, max_move=6.0)
            rew = Q.reweld_skin([{"id": i, "cat": "skin", "r": raw[i]} for i in sk_ids], {i: cand[i][var] for i in sk_ids})
        for i in sk_ids:
            cand[i][var] = rew[i]
    log(f"  Q191 {side}: hand skin onto her skin: {skin_rep}")
    # 4. muscles she has a label of: refined from the field placement, neighbours TOGETHER (one fit of the group onto the union of her labels keeps their
    # arrangement: fitting each onto its own abutting compartment inflates them into one another)
    lab_rep = {}
    if label_refine and side == "r":
        for gname, zids in HAND_LABEL_GROUPS.items():
            members, parts = [], []
            for zid in zids:
                hid = HAND_LABELS[zid]
                if zid not in cand or hid not in her:
                    continue
                m = weights[zid] > 0.5
                if m.sum() < 30:
                    continue
                vsub, fsub, idx = submesh(cand[zid]["field"], by[zid]["f"], m)
                members.append({"id": zid, "v": vsub, "r": raw[zid].astype(float)[idx], "f": fsub})
                parts.append((zid, idx, hid))
            if not members:
                continue
            hv, hf, off = [], [], 0
            for _, _, hid in parts:
                hv.append(her[hid]["v"].astype(float)); hf.append(her[hid]["f"].astype(int) + off); off += len(hv[-1])
            ref = Q.Ref(np.vstack(hv), np.vstack(hf))
            X2, rep, _ = refine_small(members, ref)
            o = 0
            for (zid, idx, hid), mem in zip(parts, members):
                n = len(mem["r"])
                cand[zid]["field"] = cand[zid]["field"].copy()
                cand[zid]["field"][idx] = X2[o:o + n]
                o += n
                own = Q.Ref(her[hid]["v"].astype(float), her[hid]["f"].astype(int))
                if len(parts) > 1:               # then each member alone, a small bounded smooth residual (<= 3 mm) onto its own label
                    orig_sp = Q.RBF_SPACING
                    Q.RBF_SPACING = 9.0
                    try:
                        X3, _ = Q.residual_fit(X2[o - n:o], own, cap=3.0, iters=3)
                        X2[o - n:o] = X3
                        cand[zid]["field"][idx] = X3
                    except np.linalg.LinAlgError:       # a very small mesh: keep the group fit
                        pass
                    finally:
                        Q.RBF_SPACING = orig_sp
                lab_rep[zid] = {**rep, "group": gname, "her_id": hid, "vertices_refined": int(n),
                                "her_label_chamfer_before_mm": [None, None, round(Q.chamfer(mem["v"], mem["f"], own)[2], 2)],
                                "after_mm": [None, None, round(Q.chamfer(X2[o - n:o], mem["f"], own)[2], 2)]}
            log(f"  Q191 {side}: group {gname} {[z for z, _, _ in parts]} onto the union of her labels: {rep['her_label_chamfer_before_mm'][2]} -> {rep['after_mm'][2]} mm")

    # 5. constraints (out of the displayed + her CT bones, inside her skin; two rounds) and the volume guard of closed muscles
    def constrain(i, v):
        for _ in range(2):
            if by[i]["cat"] in SOFT_PUSH_CATS:
                v = push_out_of_bones(v, by[i]["f"], [z_bones_new] + her_b, act[i])
            v = clamp_inside_skin(v, by[i]["f"], act[i], skin, skin_tree, **({"margin": 0.8, "max_move": 6.0} if by[i]["cat"] == "skin" else {}))
        if by[i]["cat"] == "muscle" and Q._closed(by[i]["f"]) and not NOT_BODY.search(i):
            v, _ = Q.volume_guard(v, raw[i].astype(float), by[i]["f"])
        return v

    per = {}
    for i in ids:
        r_ = raw[i].astype(float)
        f_ = by[i]["f"]
        opts = {"q168": v0[i]}
        for var in ("field", "relax"):
            if cand[i][var] is None:
                continue
            opts[var] = cand[i][var]
            if by[i]["cat"] != "skin":
                opts[var + "+constraints"] = constrain(i, cand[i][var])
        mets = {k: struct_metrics(v, r_, f_, ctx1, act[i]) for k, v in opts.items()}
        sc = {k: cand_score(m, by[i]["cat"]) for k, m in mets.items()}
        if i in lab_rep:                        # a labelled muscle follows her label (never the Q168 placement) and respects bone and skin
            sc = {k: v for k, v in sc.items() if k.endswith("+constraints")}
        best = min(sc, key=sc.get)
        by[i]["v"] = opts[best]
        per[i] = {"before": before[i], "after": mets[best], "chosen": best, "scores": {k: round(v, 1) for k, v in sc.items()},
                  "mean_move_mm": round(float(np.linalg.norm(opts[best] - v0[i], axis=1)[act[i]].mean()), 2),
                  "max_move_mm": round(float(np.linalg.norm(opts[best] - v0[i], axis=1).max()), 2)}
        if i in lab_rep:
            per[i]["label"] = {**lab_rep[i], "volume_ratio_after": mets[best].get("volume_ratio_vs_source")}
    # 6. volume guard 0.65-1.5x of the Z source for the muscles (after every other step)
    for i in ids:
        if by[i]["cat"] == "muscle" and not NOT_BODY.search(i):
            by[i]["v"] = _guard_volume(by[i]["v"].astype(float), raw[i].astype(float), by[i]["f"], act[i])
            per[i]["after"] = struct_metrics(by[i]["v"].astype(float), raw[i].astype(float), by[i]["f"], ctx1, act[i])
    return {"structures": per, "bones_moved": hb_ids, "skin": skin_rep, "labels": lab_rep, "wrist_point_z_source": [round(float(x), 1) for x in c_w],
            "chosen_counts": {k: sum(1 for r in per.values() if r["chosen"] == k) for k in ("q168", "field", "relax", "field+constraints", "relax+constraints")}}


def smooth_for_guard(d, v, sigma=10.0):
    return Q.smooth_displacement(d, v, sigma)


def set_skin_rbf(patches, skin, skin_tree, cap=12.0, near_mm=9.0, spacing=9.0, inset=0.8):
    """alternative to set_skin_onto_her: ONE smooth fold-guarded RBF displacement (Q190 residual_fit) of the welded hand skin vertices toward
    the part of her CT skin that lies within `near_mm` of them -- a smooth map keeps the Z skin's own shape (the point-wise pull crumples it)"""
    inv, A, deg, n, off = Q._welded(patches)
    allv = np.vstack([p["v"] for p in patches]).astype(float)
    W = np.zeros((n, 3)); cnt = np.zeros(n)
    np.add.at(W, inv, allv); np.add.at(cnt, inv, 1)
    X = W / cnt[:, None]
    sv = np.asarray(skin.vertices)
    cand = np.unique(np.concatenate([np.asarray(c, int) for c in skin_tree.query_ball_point(X[::3], near_mm)]))
    if len(cand) < 50:
        return {p["id"]: p["v"] for p in patches}, {"note": "no her skin within reach"}

    class _R:
        pass
    ref = _R()
    ref.pts = sv[cand] - inset * np.asarray(skin.vertex_normals)[cand]
    ref.tree = cKDTree(ref.pts)
    orig = Q.RBF_SPACING
    Q.RBF_SPACING = spacing
    try:
        X2, diag = Q.residual_fit(X, ref, cap=cap, iters=4)
    finally:
        Q.RBF_SPACING = orig
    new = X2[inv]
    out = {p["id"]: new[a:b] for p, a, b in zip(patches, off[:-1], off[1:])}
    dl = np.linalg.norm(X2 - X, axis=1)
    return out, {"method": "rbf", **diag, "moved_mean_mm": round(float(dl.mean()), 2), "moved_max_mm": round(float(dl.max()), 2), "her_skin_points": int(len(cand))}


def _note(i, r, bone=False):
    b, a = r["before"], r["after"]
    t = (f" Q191 (hand/wrist refit onto her own CT hand): moved {r['mean_move_mm']} mm on average (max {r['max_move_mm']} mm). Before -> after: "
         f"outside her skin {b['outside_her_skin_pct']} -> {a['outside_her_skin_pct']} %")
    if "inside_her_bone_pct" in b:
        t += f"; inside her CT hand/forearm bone meshes {b['inside_her_bone_pct']} -> {a['inside_her_bone_pct']} %"
    t += (f"; triangles stretched outside 0.67-1.5x of the Z source {b.get('stretch_area_outside_0.67_1.5_pct')} -> {a.get('stretch_area_outside_0.67_1.5_pct')} %; "
          f"folded edges {b['folded_edges_pct']} -> {a['folded_edges_pct']} %.")
    if "label" in r:
        lb = r["label"]
        t += (f" Refined onto her own {lb['her_id'].replace('_', ' ')} (CT/cryosection label, rule-based compartment): two-way median distance "
              f"{lb['her_label_chamfer_before_mm'][2]} -> {lb['after_mm'][2]} mm; volume {lb.get('volume_ratio_after')}x of the Z source.")
    t += f" Placement chosen among {len(r['scores'])} candidates: {r['chosen']}."
    return t


def refine_hand(pending: list[dict], raw: dict, log=print) -> dict:
    """build hook (--q191-hand): right hand fitted onto her CT hand bones, soft tissue carried / refined / constrained; the left hand is held
    (she has no left hand bones and the skin-envelope trial found no unique pose: scripts/zanatomy/q191_left_trial.py)"""
    import json
    from scripts.transfer.zan_to_vhf_whole_body import load_her_meshes
    from scripts.ribs_from_ct_labels import load_skin
    from scripts.transfer.zan_to_vhf_whole_body import DEFAULT_REPORT
    by = {p["mesh_id"]: p for p in pending}
    her = load_her_meshes()
    skin = load_skin("vhf")
    skin_tree = cKDTree(np.asarray(skin.vertices, float))
    skin_vn = skin_normals(skin)
    regions = json.loads(DEFAULT_REPORT.read_text())["region_of_structure"]
    raw = {k: np.asarray(v, float) for k, v in raw.items()}
    # right hand
    new_v, T, brep = fit_hand_bones(by, raw, her, "r", log=log, skin=skin)
    rep = run_side("r", by, raw, regions, her, skin, skin_tree, skin_vn, new_v, T, log=log)
    ids = bone_ids("r")
    for i, r in brep.items():
        if i.startswith("_"):
            continue
        txt = (f" Q191: fitted onto her own CT {r['her_ref'].replace('_', ' ')} (similarity, bounded refinement): two-way median distance {r['chamfer_mm_before'][2]} -> "
               f"{r['chamfer_mm_after'][2]} mm; scale {r['scale_vs_q168']}x, turned {r['rot_deg_vs_q168']} deg vs the Q168 fit; volume {r['volume_ratio_vs_source']}x of the Z source."
               + (f" Kept at the Q168 placement ({r['note']})." if "note" in r else ""))
        by[i]["fit_note"] = (by[i].get("fit_note") or "") + txt
    for i, r in rep["structures"].items():
        if by[i]["cat"] != "bone":
            by[i]["fit_note"] = (by[i].get("fit_note") or "") + _note(i, r)
    # left hand: held; measure and say so
    lids = sum(bone_ids("l").values(), [])
    inside = float(skin.contains(np.vstack([by[i]["v"] for i in lids])).mean())
    for i in lids:
        by[i]["fit_note"] = (by[i].get("fit_note") or "") + (
            f" Q191: NOT moved. Her CT has no left hand bones; {100 * (1 - inside):.0f} % of the Z left hand bone vertices lie outside her CT skin "
            f"(right hand after Q191: 0 %), so this placement is an unchecked estimate.")
    return {"rule": "scripts/zanatomy/q191_hand.py", "right": {k: v for k, v in rep.items() if k != "structures"}, "bones": brep, "structures": rep["structures"],
            "left_hand": {"held": True, "bone_vertices_outside_her_skin_pct": round(100 * (1 - inside), 1),
                          "reason": "no left hand bones in her CT; skin-envelope trial ambiguous (data/derived/Q191_left_hand_trial.json)"}}
