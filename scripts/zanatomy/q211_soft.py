"""Q211 soft-tissue repair of a junction zone: tear relaxation (q211_relax) + the Q206 guard ladder (displayed skin / displayed bones / volume / fold / stretch) per structure, accept-if-not-worse.
Works on the DECODED shipped meshes of a page (topology identical to the unfitted Z base page for the matched structures: the Z source IS the reference shape)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q211_core as K  # noqa: E402
from scripts.zanatomy import q211_relax as RX  # noqa: E402
from scripts.zanatomy import q206_carry as C6  # noqa: E402
from scripts.zanatomy import q199_elbow as E  # noqa: E402

CAT = {"joint": "ligament", "insertion": "ligament", "muscle": "muscle", "vessel": "vessel", "nerve": "nerve", "fascia": "fascia", "bursa": "bursa", "tendon": "tendon", "cartilage": "cartilage"}
SOFT_NOT = ("bone", "skin", "cartilage", "lymph", "viscera", "cns")


def zone_ids(pg, base, zone_ids_raw):
    m = set(K.matched(pg, base))
    return [i for i in zone_ids_raw if i in m and pg.sys(i) not in SOFT_NOT]


def zone_ids_fitseams(pg, base, centre, R):
    """the structures of the Q198 fit-seam zone: matched (same topology as the unfitted base), not bone / skin / cartilage, with a base vertex within R of the base joint centre"""
    m = K.matched(pg, base)
    return [i for i in m if pg.sys(i) not in ("bone", "skin", "cartilage") and (np.linalg.norm(base.v(i) - centre, axis=1) < R).any()]


def cstay_vector(env, zone, Z, pg, att_coeff=20.0, att_mm=6.0):
    """stay-put coefficient per vertex: 1, and for muscle / tendon / ligament / bursa vertices 1 + (att_coeff - 1) * exp(-(d / att_mm)^2) with d = distance to the nearest displayed bone surface (attachment footprints
    and structures lying on bone are held; the belly away from the bones is free)"""
    c = np.ones(Z.n)
    sd = np.abs(env.bone[zone].value(Z.X, outside=50.0))
    att = np.zeros(Z.n, bool)
    for k, i in enumerate(Z.ids):
        if pg.sys(i) in ("muscle", "joint", "insertion", "tendon", "bursa"):
            att[Z.lab == k] = True
    c[att] = 1.0 + (att_coeff - 1.0) * np.exp(-(sd[att] / att_mm) ** 2)
    return c


def constraints(env, zone, Z, X, rcat, bone_tol=None, skin_tol=2.0):
    """vertices more than `tol` mm inside a displayed bone -> target displacement out along the bone's signed-field gradient; vertices more than skin_tol outside the displayed skin -> back to 0.5 mm inside"""
    idx, tgt = [], []
    dep = env.depth(X, zone)
    tol = np.array([C6.PUSH_TOL.get(CAT.get(rcat[Z.ids[k]], rcat[Z.ids[k]]), 1.0) for k in Z.lab])
    m = dep > tol
    if m.any():
        g = env.bone[zone].gradient(X[m])
        idx.append(np.flatnonzero(m))
        tgt.append(g * (dep[m] - tol[m] + 0.6)[:, None])
    sd = env.skin_sd(X)
    m = sd > skin_tol
    if m.any():
        g = -env.skin.gradient(X[m])
        idx.append(np.flatnonzero(m))
        tgt.append(g * (sd[m] + 0.5)[:, None])
    if not idx:
        return None
    ii = np.concatenate(idx)
    tt = np.concatenate(tgt)
    # a vertex in both lists: the sum (rare)
    u, inv = np.unique(ii, return_inverse=True)
    T = np.zeros((len(u), 3))
    np.add.at(T, inv, tt)
    return u, T


def accept(mm, m00, cat, f):
    """a repaired structure is kept only if it is not worse on the audit's own measures: outside the displayed skin / inside the displayed bones (+1 point, floor 3 %), stretched triangles (+8, tubes +14),
    folded edges (+3, tubes +8; floor 4 %), median edge scale (+-25 % for open meshes)"""
    tube = cat in ("vessel", "nerve")
    gain = (m00["inside_bone_pct"] - mm["inside_bone_pct"]) + (m00["outside_skin_pct"] - mm["outside_skin_pct"])
    if gain >= 10.0:                                  # a structure that leaves a bone / comes back inside the skin may stretch / fold more for it (a large gain: much more)
        big = gain >= 30.0
        ok = (mm["outside_skin_pct"] <= max(m00["outside_skin_pct"], 3.0) + 1.0 and mm["inside_bone_pct"] <= max(m00["inside_bone_pct"], 3.0) + 1.0
              and mm["stretched_pct"] <= m00["stretched_pct"] + ((45.0 if big else 25.0) if tube else (40.0 if big else 20.0)) and mm["folded_pct"] <= max(m00["folded_pct"] + ((12.0 if big else 10.0) if tube else (8.0 if big else 5.0)), 6.0))
        if ok and (E._closed(f) or abs(mm["edge_scale"] / max(m00["edge_scale"], 1e-6) - 1.0) <= C6.EDGE_SCALE_TOL):
            return True, None
    onbone = cat in ("ligament", "bursa", "cartilage", "tendon")           # lie ON the bone by design: more inside-bone slack
    ok = (mm["outside_skin_pct"] <= max(m00["outside_skin_pct"], 3.0) + 1.0 and mm["inside_bone_pct"] <= max(m00["inside_bone_pct"], 3.0) + (10.0 if onbone else 1.0)
          and mm["stretched_pct"] <= m00["stretched_pct"] + (30.0 if tube else 12.0) and mm["folded_pct"] <= max(m00["folded_pct"] + (10.0 if tube else 4.0), 5.0))
    if not E._closed(f) and abs(mm["edge_scale"] / max(m00["edge_scale"], 1e-6) - 1.0) > C6.EDGE_SCALE_TOL:
        ok = False
    return ok, None


def island_gap(v, f):
    """the Q198 `tube_gap` measure: largest distance (mm) from any other face-connected island of the (welded) mesh to its MAIN (largest-area) island; 0 for one piece"""
    from scipy.spatial import cKDTree
    from scripts.zanatomy.q198_core import weld, islands
    w, g = weld(np.asarray(v, float), f)
    isl = islands(w, g)
    if len(isl) < 2:
        return 0.0
    mt = cKDTree(w[isl[0]["vidx"]])
    return max(float(mt.query(w[b["vidx"]])[0].min()) for b in isl[1:])


def gap_ok(cat, v_new, v_old, f, slack=3.0):
    """a vessel / nerve must not be torn apart by a move: its island gap may not grow by more than `slack` mm"""
    if cat not in ("vessel", "nerve"):
        return True
    return island_gap(v_new, f) <= island_gap(v_old, f) + slack


def ladder(env, zone, v, f, r, cat, i, vr0):
    return C6.guard(env, zone, v, f, r, CAT.get(cat, "vessel") if cat in CAT else cat, i, v, vr0)


def relax_zone(env, zone, st, ids, centre, R, rounds=10, w_p=1.0, w_s=8.0, w_0=0.05, tol=2.0, cap=24.0, att_coeff=20.0, log=print, w_c=10.0, reanchor_share=0.5, rounds2=5, frame_bones=None):
    """returns (V_new {id: vertices} for the structures that moved > 0.3 mm, report)"""
    pg, base = st.pg, st.base
    cur = {i: st.v(i).astype(float) for i in ids}
    Z = RX.Zone(ids, {i: base.v(i) for i in ids}, cur, {i: pg.f(i) for i in ids}, centre, R)
    cst = cstay_vector(env, zone, Z, pg, att_coeff)
    t0 = Z.tears()
    rep = {"structures": len(ids), "vertices": Z.n, "pairs": int(len(Z.P)), "tear_gt5_before": round(float((t0 > 5).mean()), 4), "tear_gt2_before": round(float((t0 > 2).mean()), 4),
           "tear_median_before_mm": round(float(np.median(t0)), 2)}
    log(f"  {zone}: {len(ids)} structures, {Z.n} vertices, {len(Z.P)} base-adjacent pairs; tear > 5 mm {rep['tear_gt5_before']}")
    rcat = {i: pg.sys(i) for i in ids}
    r_ = {i: base.v(i).astype(float) for i in ids}
    f_ = {i: pg.f(i) for i in ids}
    X = Z.X.copy()
    m0 = {i: C6.metrics(env, zone, cur[i], r_[i], f_[i]) for i in ids}
    c0 = {i: C6.cost(m0[i], CAT.get(rcat[i], rcat[i]), m0[i]) for i in ids}
    best = {i: cur[i] for i in ids}                    # accepted state
    X0 = Z.X
    reanchored = {}
    for rd in range(rounds + rounds2):
        if rd == rounds and reanchor_share is not None:
            reanchored = reanchor(env, zone, st, Z, X, ids, rcat, r_, f_, m0, reanchor_share, log, frame_bones=frame_bones, centre=centre, R=R)
            for i, vv in reanchored.items():
                X[Z.off[i]:Z.off[i] + len(vv)] = vv
            X0 = np.where(np.isin(np.arange(Z.n), np.concatenate([np.arange(Z.off[i], Z.off[i] + len(v)) for i, v in reanchored.items()] or [np.zeros(0, int)]))[:, None], X, Z.X)
        con = constraints(env, zone, Z, X, rcat)
        u, na = RX.solve(Z, X, cst, w_p=w_p, w_s=w_s, w_0=w_0, tol=tol, con=con, w_c=w_c)
        Xn = X + u
        # cap the total movement from the page
        d = Xn - X0
        n = np.linalg.norm(d, axis=1)
        Xn = X0 + d * np.minimum(1.0, cap / np.maximum(n, 1e-9))[:, None]
        acc = rej = 0
        reasons = {}
        Xa = X.copy()
        for k, i in enumerate(ids):
            a, b = Z.off[i], Z.off[i] + len(cur[i])
            vn = Xn[a:b]
            if np.linalg.norm(vn - X[a:b], axis=1).max() < 0.05:
                continue
            vg = ladder(env, zone, vn, f_[i], r_[i], rcat[i], i, m0[i]["volume_ratio"])
            vg = E.cap_to(vg, X0[a:b], cap + 6.0)
            mm = C6.metrics(env, zone, vg, r_[i], f_[i])
            cat = CAT.get(rcat[i], rcat[i])
            ok, why = accept(mm, m0[i], cat, f_[i])
            ok = ok and gap_ok(cat, vg, X[a:b], f_[i])
            if not ok:
                reasons[i] = (mm["outside_skin_pct"], mm["inside_bone_pct"], mm["stretched_pct"], mm["folded_pct"])
            if ok:
                Xa[a:b] = vg
                acc += 1
            else:
                rej += 1
        X = Xa
        rep.setdefault("last_rejects", {})
        rep["last_rejects"] = {i: dict(zip(("outside_skin", "inside_bone", "stretched", "folded"), v)) for i, v in reasons.items()}
        t = Z.tears(X)
        log(f"    round {rd}: active pairs {na}, accepted {acc} rejected {rej} structures; tear > 5 mm {float((t > 5).mean()):.3f}, > 2 mm {float((t > 2).mean()):.3f}, median {float(np.median(t)):.2f}")
    t1 = Z.tears(X)
    out, srep = {}, {}
    for i in ids:
        a, b = Z.off[i], Z.off[i] + len(cur[i])
        mv = np.linalg.norm(X[a:b] - cur[i], axis=1)
        if mv.max() < 0.3:
            continue
        out[i] = X[a:b].copy()
        m1 = C6.metrics(env, zone, X[a:b], r_[i], f_[i])
        srep[i] = {"cat": rcat[i], "mean_move_mm": round(float(mv.mean()), 2), "max_move_mm": round(float(mv.max()), 2), "before": m0[i], "after": m1}
    rep["reanchored"] = {i: round(float(np.linalg.norm(X[Z.off[i]:Z.off[i] + len(cur[i])] - cur[i], axis=1).mean()), 1) for i in reanchored}
    rep.update({"tear_gt5_after": round(float((t1 > 5).mean()), 4), "tear_gt2_after": round(float((t1 > 2).mean()), 4), "tear_median_after_mm": round(float(np.median(t1)), 2), "moved": len(out), "structures_report": srep})
    # per-structure pair tear before / after (own pairs)
    pb, pa = {}, {}
    for k, i in enumerate(ids):
        sel = (Z.lab[Z.P[:, 0]] == k) | (Z.lab[Z.P[:, 1]] == k)
        if sel.sum():
            pb[i] = round(float((t0[sel] > 5).mean()), 3)
            pa[i] = round(float((t1[sel] > 5).mean()), 3)
    rep["tear_gt5_by_structure"] = {"before": pb, "after": pa}
    return out, rep, Z, X


def muscle_overlap(pg, V, ids, lo, hi, h=1.5):
    """the Q198 elbow muscle-in-muscle measure on the shipped meshes: share of each closed muscle's voxel solid (h = 1.5 mm, closing 1) that lies inside another muscle's solid; muscles > 3 cm3 only.
    V = {id: vertices} overrides of the page's own vertices"""
    from scripts.zanatomy.q198_core import Grid
    g = Grid(np.asarray(lo, float), np.asarray(hi, float), h)
    cnt = np.zeros(g.shape, np.int8)
    sol = {}
    for i in ids:
        if pg.sys(i) != "muscle":
            continue
        v = np.asarray(V.get(i, pg.v(i)), float)
        sv = g.solid(v, pg.f(i), close=1)
        sol[i] = sv
        cnt += sv
    out = {}
    for i, sv in sol.items():
        n = int(sv.sum())
        if n > 200:
            out[i] = {"vol_cm3": round(n * g.h ** 3 / 1000, 1), "overlap_pct": round(100 * float(((cnt > 1) & sv).sum()) / n, 1)}
    return out


def follow(env, zone, st, moved, radius=35.0, min_move=1.5, log=print):
    """soft structures near the moved bones `moved` ({id: new vertices}) follow them: candidate = current vertices + the gated bone-anchored field of the bone displacement (Q199 / Q206 field), then the guard ladder;
    kept if not worse (accept()).  -> {id: (new vertices, report)}"""
    pg = st.pg
    bones = [i for i in pg.ids if pg.sys(i) == "bone"]
    v0 = {i: pg.v(i) for i in bones}
    v1 = {i: moved.get(i, pg.v(i)) for i in bones}
    c = np.mean([v0[i].mean(0) for i in moved], axis=0)
    F = K.ChainField(v0, v1, c, bones)
    log(f"  follow {zone}: moving bones {{{', '.join(f'{k}: {v:.1f}' for k, v in F.bone_dv.items())}}} mm")
    from scipy.spatial import cKDTree
    mt = cKDTree(np.vstack([v0[i] for i in moved] + [v1[i] for i in moved]))
    out = {}
    for i in pg.ids:
        cat = pg.sys(i)
        if cat in ("bone", "skin", "lymph", "viscera", "cns"):
            continue
        v = st.v(i).astype(float)
        if mt.query(v)[0].min() > radius:
            continue
        D = E.gated(F(v))
        dmax = float(np.linalg.norm(D, axis=1).max())
        if dmax < min_move:
            continue
        f = pg.f(i)
        r = (st.base.v(i) if (i in st.base.S and len(st.base.v(i)) == len(v)) else v).astype(float)
        m00 = C6.metrics(env, zone, v, r, f)
        cand = v + D
        ccat = CAT.get(cat, cat)
        vg = C6.guard(env, zone, cand, f, r, ccat, i, cand, m00["volume_ratio"])
        mm = C6.metrics(env, zone, vg, r, f)
        ok, _ = accept(mm, m00, ccat, f)
        ok = ok and gap_ok(ccat, vg, v, f)
        if not ok:
            vg2 = C6.guard(env, zone, v + E.lowpass(D, f, 10.0), f, r, ccat, i, v + D, m00["volume_ratio"])
            mm2 = C6.metrics(env, zone, vg2, r, f)
            ok2, _ = accept(mm2, m00, ccat, f)
            ok2 = ok2 and gap_ok(ccat, vg2, v, f)
            if ok2:
                vg, mm, ok = vg2, mm2, True
        if not ok and ccat in ("ligament", "bursa", "cartilage", "tendon"):          # lie ON the bone by design: the raw field result (a smooth carried copy) is accepted if skin / stretch / folds are not worse
            mr = C6.metrics(env, zone, cand, r, f)
            okr = (mr["outside_skin_pct"] <= max(m00["outside_skin_pct"], 3.0) + 1.0 and mr["inside_bone_pct"] <= m00["inside_bone_pct"] + 10.0
                   and mr["stretched_pct"] <= m00["stretched_pct"] + 30.0 and mr["folded_pct"] <= max(m00["folded_pct"] + 3.0, 4.0))
            if okr:
                vg, mm, ok = cand, mr, True
        mv = np.linalg.norm(vg - v, axis=1)
        if ok and mv.max() > 0.3:
            out[i] = (vg, {"cat": cat, "field_max_mm": round(dmax, 2), "mean_move_mm": round(float(mv.mean()), 2), "max_move_mm": round(float(mv.max()), 2), "before": m00, "after": mm})
        elif not ok:
            log(f"    {i}: follow rejected (field {dmax:.1f} mm): {m00} -> {mm}")
    log(f"  follow {zone}: {len(out)} structures moved")
    return out


def reanchor(env, zone, st, Z, X, ids, rcat, r_, f_, m0, share_min, log, frame_bones=None, centre=None, R=None):
    """structures that are still mostly torn from their Z-source neighbours after the relaxation (> share_min of their pairs > 5 mm: a structure left on an old frame, a gross misplacement beyond the relaxation cap)
    are re-anchored: candidate = the Z source (base) vertices carried by the bone-anchored field of the base -> fitted bones (the Q168 / Q199 field), then the guard ladder; adopted if it is accepted by the
    containment guards and its own pair tears fall by at least 0.25"""
    pg, base = st.pg, st.base
    bones = [i for i in K.bone_ids(pg) if i in set(K.matched(pg, base))]
    F = K.ChainField({b: base.v(b) for b in bones}, {b: pg.v(b) for b in bones}, np.mean([base.v(i).mean(0) for i in ids], axis=0), bones)
    t = Z.tears(X)
    out = {}
    pairs_dummy = None
    # frame offsets of the zone structures on the CURRENT state vs their bone-chain image (the Q198 fit-seam measure): a structure with a REAL offset (> 10 mm and more than 8 mm above its image) is re-anchored too
    real_frame = {}
    if frame_bones:
        bv = {i: base.v(i) for i in ids}
        cv = {i: X[Z.off[i]:Z.off[i] + len(bv[i])] for i in ids}
        for b in frame_bones:
            bv[b], cv[b] = base.v(b), pg.v(b)
        img = {i: bv[i] + F(bv[i]) for i in ids}
        for b in frame_bones:
            img[b] = pg.v(b)
        sysf = lambda i: pg.sys(i)
        allids = list(ids) + list(frame_bones)
        V, W, L, keep = K.zone_arrays(bv, cv, sysf, allids, centre, R)
        V2, W2, L2, keep2 = K.zone_arrays(bv, img, sysf, allids, centre, R)
        fo, fo2 = K.frame_offsets(V, W, L, keep, sysf, list(frame_bones), centre, bv), K.frame_offsets(V2, W2, L2, keep2, sysf, list(frame_bones), centre, bv)
        real_frame = {i: (v["frame_offset_mm"], fo2.get(i, {}).get("frame_offset_mm", 0.0)) for i, v in fo.items() if v["frame_offset_mm"] > 10.0 and v["frame_offset_mm"] > fo2.get(i, {}).get("frame_offset_mm", 0.0) + 8.0}
        if real_frame:
            log(f"    real frame offsets (page vs bone-chain image, mm): " + ", ".join(f"{i[:30]} {a:.1f} / {b:.1f}" for i, (a, b) in real_frame.items()))
    for k, i in enumerate(ids):
        sel = (Z.lab[Z.P[:, 0]] == k) | (Z.lab[Z.P[:, 1]] == k)
        by_tear = sel.sum() >= 20 and (t[sel] > 5).mean() > share_min
        if not by_tear and i not in real_frame:         # (a REAL frame offset is only logged and tried: adopted only if its pair tears fall)
            continue
        a, b = Z.off[i], Z.off[i] + len(r_[i])
        cat = CAT.get(rcat[i], rcat[i])
        cand = base.v(i) + F(base.v(i))
        m_cur = C6.metrics(env, zone, X[a:b], r_[i], f_[i])
        vg = C6.guard(env, zone, cand, f_[i], r_[i], cat, i, cand, m_cur["volume_ratio"])
        mm = C6.metrics(env, zone, vg, r_[i], f_[i])
        onbone = cat in ("ligament", "bursa", "cartilage", "tendon")
        ok = (mm["outside_skin_pct"] <= max(m_cur["outside_skin_pct"], 3.0) + 1.0 and mm["inside_bone_pct"] <= max(m_cur["inside_bone_pct"], 3.0) + (10.0 if onbone else 1.0)
              and mm["folded_pct"] <= max(m_cur["folded_pct"] + 6.0, 6.0))
        Xt = X.copy()
        Xt[a:b] = vg
        t2 = Z.tears(Xt)
        share_after = float((t2[sel] > 5).mean())
        share_before = float((t[sel] > 5).mean())
        if ok and share_after < share_before - 0.25:
            out[i] = vg
            log(f"    re-anchored {i}: pair tear share {share_before:.2f} -> {share_after:.2f}, mean move {np.linalg.norm(vg - X[a:b], axis=1).mean():.1f} mm" + (f", frame offset {real_frame[i][0]:.1f} mm (image {real_frame[i][1]:.1f})" if i in real_frame else ""))
        else:
            log(f"    not re-anchored {i}: {'guards' if not ok else 'no tear gain'} (share {share_before:.2f} -> {share_after:.2f})")
    return out


def push_group(env, zone, st, ids, log=print, cap=12.0):
    """structures that the fit left inside a displayed bone: the guard ladder only (skin clamp, push out of the displayed bones, volume guard), kept if not worse (accept()).  -> {id: (vertices, report)}"""
    pg = st.pg
    out = {}
    for i in ids:
        v = st.v(i).astype(float)
        f = pg.f(i)
        r = (st.base.v(i) if (i in st.base.S and len(st.base.v(i)) == len(v)) else v).astype(float)
        cat = CAT.get(pg.sys(i), pg.sys(i))
        m00 = C6.metrics(env, zone, v, r, f)
        if m00["inside_bone_pct"] <= 3.0 and m00["outside_skin_pct"] <= 3.0:
            continue
        vg = C6.guard(env, zone, v, f, r, cat, i, v, m00["volume_ratio"])
        vg = E.cap_to(vg, v, cap)
        mm = C6.metrics(env, zone, vg, r, f)
        ok, _ = accept(mm, m00, cat, f)
        ok = ok and gap_ok(cat, vg, v, f)
        mv = np.linalg.norm(vg - v, axis=1)
        if ok and mv.max() > 0.3 and (mm["inside_bone_pct"] < m00["inside_bone_pct"] - 1.0 or mm["outside_skin_pct"] < m00["outside_skin_pct"] - 1.0):
            out[i] = (vg, {"cat": pg.sys(i), "mean_move_mm": round(float(mv.mean()), 2), "max_move_mm": round(float(mv.max()), 2), "before": m00, "after": mm})
        else:
            log(f"    {i}: not repaired (kept): {'rejected' if not ok else 'no gain'}  in-bone {m00['inside_bone_pct']}->{mm['inside_bone_pct']} stretched {m00['stretched_pct']}->{mm['stretched_pct']}")
    return out


def end_distances(v, bone_tree, frac=0.1):
    """distance (mm) of the two ends of a long structure (the 10 % of its vertices at either end of its first principal axis) to the nearest bone"""
    c = v.mean(0)
    u, s_, vt = np.linalg.svd(v - c, full_matrices=False)
    t = (v - c) @ vt[0]
    lo, hi = t.min(), t.max()
    return [float(bone_tree.query(v[sel].mean(0))[0]) for sel in (t < lo + frac * (hi - lo), t > hi - frac * (hi - lo))]


def attach_guard(st, out, bone_ids, log=print, rise=3.0, floor=6.0):
    """muscles / tendons whose end moved away from the nearest bone (> `floor` mm and more than `rise` mm further than where it started: an origin / insertion torn off) go back part of the way (move x 0.66, 0.33, 0)"""
    from scipy.spatial import cKDTree
    pg = st.pg
    tree = cKDTree(np.vstack([st.v(b) for b in bone_ids]))
    info = {}
    for i in list(out):
        if pg.sys(i) not in ("muscle", "tendon"):
            continue
        v0 = st.v(i)
        d0 = end_distances(v0, tree)
        for fct in (1.0, 0.66, 0.33, 0.0):
            v = v0 + fct * (out[i] - v0)
            d1 = end_distances(v, tree)
            if all(a <= max(b + rise, floor) for a, b in zip(d1, d0)):
                break
        if fct < 1.0:
            info[i] = (d0, end_distances(out[i], tree), fct)
            if fct == 0.0:
                out.pop(i)
            else:
                out[i] = v0 + fct * (out[i] - v0)
    if info:
        log("    attachment guard: " + ", ".join(f"{i[:24]} ends {[round(x, 1) for x in a]}->{[round(x, 1) for x in b]} x{f}" for i, (a, b, f) in info.items()))
    return out, info


def overlap_guard(st, muscle_ids, out, limit=55.0, max_rise=6.0, log=print):
    """the Q198 muscle-in-muscle measure (share of a muscle's voxel solid inside the other zone muscles, `muscle_overlap`) is checked for the zone muscles the relaxation moved: a muscle that ends above `limit` %
    AND more than `max_rise` points above where it started goes back part of the way (move x 0.66, 0.33, 0) until it does not.  -> (out', {id: (before, after, factor)})"""
    pg = st.pg
    mus = [i for i in muscle_ids if pg.sys(i) == "muscle"]
    if not mus:
        return out, {}
    pts = np.vstack([np.vstack([st.v(i), out[i]]) if i in out else st.v(i) for i in mus])
    lo, hi = pts.min(0) - 5.0, pts.max(0) + 5.0
    V0 = {i: st.v(i) for i in mus}
    cur = {i: out.get(i, st.v(i)) for i in mus}
    o0 = muscle_overlap(pg, V0, mus, lo, hi)
    o1 = muscle_overlap(pg, cur, mus, lo, hi)
    info = {}
    bad = [i for i in out if i in o1 and i in o0 and o1[i]["overlap_pct"] > limit and o1[i]["overlap_pct"] - o0[i]["overlap_pct"] > max_rise]
    log(f"    overlap guard: {len(bad)} moved muscles end > {limit} % and > {max_rise} points higher: " + ", ".join(f"{i[:24]} {o0[i]['overlap_pct']}->{o1[i]['overlap_pct']}" for i in bad))
    for fct in (0.66, 0.33, 0.0):
        if not bad:
            break
        for i in bad:
            cur[i] = V0[i] + fct * (out[i] - V0[i])
        o2 = muscle_overlap(pg, cur, mus, lo, hi)
        nxt = []
        for i in bad:
            if i in o2 and o2[i]["overlap_pct"] > max(o0[i]["overlap_pct"] + max_rise, limit) and fct > 0.0:
                nxt.append(i)
            else:
                info[i] = (o0[i]["overlap_pct"], o2.get(i, {"overlap_pct": None})["overlap_pct"], fct)
        bad = nxt
    out2 = dict(out)
    for i, (b, a, fct) in info.items():
        if fct == 0.0:
            out2.pop(i, None)
        else:
            out2[i] = cur[i]
    return out2, info
