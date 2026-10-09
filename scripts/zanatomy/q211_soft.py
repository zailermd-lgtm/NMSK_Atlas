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


def cstay_vector(env, zone, Z, pg, att_coeff=5.0, att_mm=3.0):
    """stay-put coefficient per vertex: 1, and `att_coeff` for muscle / tendon / ligament vertices within att_mm of a displayed bone (attachment footprints)"""
    c = np.ones(Z.n)
    sd = env.bone[zone].value(Z.X, outside=50.0)
    att = np.zeros(Z.n, bool)
    for k, i in enumerate(Z.ids):
        if pg.sys(i) in ("muscle", "joint", "insertion", "tendon", "bursa"):
            att[Z.lab == k] = True
    c[att & (np.abs(sd) < att_mm)] = att_coeff
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


def ladder(env, zone, v, f, r, cat, i, vr0):
    return C6.guard(env, zone, v, f, r, CAT.get(cat, "vessel") if cat in CAT else cat, i, v, vr0)


def relax_zone(env, zone, st, ids, centre, R, rounds=10, w_p=1.0, w_s=8.0, w_0=0.05, tol=2.0, cap=24.0, att_coeff=5.0, log=print, w_c=10.0):
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
    for rd in range(rounds):
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
            vg = E.cap_to(vg, cur[i], cap + 6.0)
            mm = C6.metrics(env, zone, vg, r_[i], f_[i])
            cat = CAT.get(rcat[i], rcat[i])
            ok, why = accept(mm, m0[i], cat, f_[i])
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
        if not ok:
            vg2 = C6.guard(env, zone, v + E.lowpass(D, f, 10.0), f, r, ccat, i, v + D, m00["volume_ratio"])
            mm2 = C6.metrics(env, zone, vg2, r, f)
            ok2, _ = accept(mm2, m00, ccat, f)
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
        mv = np.linalg.norm(vg - v, axis=1)
        if ok and mv.max() > 0.3 and (mm["inside_bone_pct"] < m00["inside_bone_pct"] - 1.0 or mm["outside_skin_pct"] < m00["outside_skin_pct"] - 1.0):
            out[i] = (vg, {"cat": pg.sys(i), "mean_move_mm": round(float(mv.mean()), 2), "max_move_mm": round(float(mv.max()), 2), "before": m00, "after": mm})
        else:
            log(f"    {i}: not repaired (kept): {'rejected' if not ok else 'no gain'}  in-bone {m00['inside_bone_pct']}->{mm['inside_bone_pct']} stretched {m00['stretched_pct']}->{mm['stretched_pct']}")
    return out
