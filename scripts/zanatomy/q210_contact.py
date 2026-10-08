#!/usr/bin/env python3
"""Q210 (2): male forearm vs trunk / thigh / lateral-abdomen SKIN crossing (Q209: 1083 deep face pairs, median 5.0 mm, p90 9.6, max 17.2 mm; the arms rest on the body in the CT, the deep tissue is clear by 23-25 mm).
LOCAL SYMMETRIC CONTACT RELAXATION, skin only (no bone / muscle / vessel moves):
  * free patches: the 6 forearm / wrist slabs of each side and the trunk / thigh patches that cross them; every other skin patch is fixed (its shared border vertices are anchors);
  * the gap between the forearm deep tissue and the trunk deep tissue (nearest bone / muscle points) is SPLIT between the two skins in the ratio of their margins over their own tissue (forearm share rho = median forearm
    margin / (forearm + trunk margin) of the vertices in contact, 0.44 left / 0.38 right): w = d_forearm / (d_forearm + d_trunk); a forearm skin vertex must satisfy w <= rho - delta, a trunk skin vertex w >= rho + delta,
    so the two skins cannot cross.  A violating vertex moves toward its OWN tissue by the violation (mm), never closer than 1 mm to it;
  * both sheets of a slab take the movement of the sheet that violates (thickness kept), the movement is smoothed (3 mm, forearm and trunk separately: they move in opposite directions where they overlap), tapers
    to 0 over 8 mm of mesh distance from the vertices shared with fixed patches (welds / border steps kept), vertices shared by two free patches get the same movement;
  * face pairs that survive (thin corners, tapered rims) are removed by the trunk skin alone (absorb phase).
    python3 scripts/zanatomy/q210_build.py contact"""
from __future__ import annotations

import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q210_core as K  # noqa: E402
from scripts.zanatomy import q207_geom as G  # noqa: E402
from scripts.zanatomy import q207_weld as WD  # noqa: E402
from scripts.zanatomy import q208_core as K8  # noqa: E402
from scripts.zanatomy.q198_core import surf_points  # noqa: E402

BASE = lambda i: i[len("zan_skin_"):-2]
NB = ("palm", "dorsum_of_hand", "radial_foveola", "anterior_region_of_arm", "posterior_region_of_arm", "deltoid_region", "dorsal_surfaces_of_digits_of_hand", "palmar_surfaces_of_digits_of_hand",
      "nail_plate", "perionyx", "medial_bicipital_groove", "lateral_bicipital_groove", "lateral_region_of_arm", "medial_region_of_arm")
SIGMA, TAPER_MM, MARGIN_KEEP, STOP_DEPTH, OVERRELAX, DAMP = 3.0, 8.0, 1.0, 0.3, 1.3, 0.12
DELTA, MAX_IT, ABSORB_IT = 0.04, 8, 6       # partition half-gap (share of the tissue gap), iterations


def forearm_ids(pg, side=None):
    return sorted(i for i in pg.skin_ids if BASE(i) in K8.TUBE and (side is None or i.endswith("_" + side)))


def find_sets(pg, V, min_depth=0.3):
    """-> F ids, T ids (patches that cut a forearm slab deeper than min_depth), the F x T pairs"""
    fore = set(i for i in pg.skin_ids if BASE(i) in K8.TUBE + K8.ELBOW)
    allf = np.vstack([V[i] for i in fore])
    lo, hi = allf.min(0) - 20, allf.max(0) + 20
    cand = sorted({i for i in pg.skin_ids if "nail_plate" not in i and "perionyx" not in i and (V[i].max(0) >= lo).all() and (V[i].min(0) <= hi).all()} | fore)
    Vc, F, ow, nm = G.concat({i: (V[i], pg.f(i)) for i in cand})
    pr = G.intersecting_pairs(Vc, F, ow)
    dd = G.pair_depth(Vc, F, pr) if len(pr) else np.zeros(0)
    Ts, Fs = set(), set()
    for (x, y), d in zip(pr, dd):
        a, b = nm[ow[x]], nm[ow[y]]
        if (a in fore) != (b in fore) and BASE(b if a in fore else a) not in NB and d > min_depth:
            Ts.add(b if a in fore else a)
            Fs.add(a if a in fore else b)
    return sorted(Fs), sorted(Ts), cand


def tissue_points(pg, sf=None):
    """deep tissue sample points: forearm side {l, r} (arm + forearm + hand bones / muscles of that side) and trunk (all other bone / muscle structures)"""
    reg = K.C7.regions()
    P = {"l": [], "r": [], "trunk": []}
    for i in pg.ids:
        if pg.sys(i) not in ("bone", "muscle") or not len(pg.v(i)):
            continue
        pts = surf_points(pg.v(i), pg.f(i), 2.5, cap=20000)
        arm = reg.get(i) in K.C7.ARM_REGIONS
        if arm:
            side = pg.S[i]["m"]["side"]
            if side in P:
                P[side].append(pts)
        else:
            P["trunk"].append(pts)
    return {k: np.vstack(v) for k, v in P.items()}


def mesh_graph(V, faces, ids, anchors):
    """combined vertex graph of the free patches (edge length weights, shared vertices of two free patches joined by a 0.01 edge); geodesic distance from the anchor vertices"""
    off, o = {}, 0
    for i in ids:
        off[i] = o
        o += len(V[i])
    N = o
    r, c, w = [], [], []
    for i in ids:
        f = faces[i] + off[i]
        e = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
        v = np.vstack([V[j] for j in ids])
        l = np.linalg.norm(v[e[:, 0]] - v[e[:, 1]], axis=1)
        r.append(e[:, 0]); c.append(e[:, 1]); w.append(l)
    allv = np.vstack([V[j] for j in ids])
    t = cKDTree(allv)
    owner = np.concatenate([[k] * len(V[j]) for k, j in enumerate(ids)])
    pr = t.query_pairs(0.6, output_type="ndarray")
    pr = pr[owner[pr[:, 0]] != owner[pr[:, 1]]]
    r.append(pr[:, 0]); c.append(pr[:, 1]); w.append(np.full(len(pr), 0.01))
    A = coo_matrix((np.concatenate(w) + 1e-6, (np.concatenate(r), np.concatenate(c))), shape=(N, N)).tocsr()
    A = A.maximum(A.T)
    src = np.flatnonzero(anchors)
    g = dijkstra(A, indices=src, min_only=True) if len(src) else np.full(N, 1e9)
    return off, allv, owner, pr, g


def anchors_of(pg, raw, free, V):
    """free-patch vertices that are shared with a FIXED patch in the Z source (border pairs, raw distance < 1.5 mm) or sit on a patch border that is not shared with a free patch"""
    skin = [i for i in pg.skin_ids if i in raw.S]
    rawd = {i: raw.v(i) for i in skin}
    cons = WD.border_pairs(rawd, skin)
    anc = {i: np.zeros(len(V[i]), bool) for i in free}
    for (x, a, partners) in cons:
        A = skin[x]
        for (y, b, w) in partners:
            B = skin[y]
            if A in free and B not in free:
                anc[A][a] = True
            if B in free and A not in free:
                anc[B][b] = True
    return anc


def twins(raw, ids, V):
    """slab twin of every vertex (nearest other vertex of the same patch in the Z source, reciprocal pairs only; -1 otherwise)"""
    out = {}
    for i in ids:
        v0 = raw.v(i)
        d, k = cKDTree(v0).query(v0, k=2)
        tw = k[:, 1]
        recip = tw[tw] == np.arange(len(v0))
        out[i] = np.where(recip & (d[:, 1] < 6.0), tw, -1)
    return out


def relax(pg, raw, V0, F_ids, T_ids, tissue, rho=None, delta=0.02, max_it=25, absorb_it=12, count_every=3, log=print):
    """partition relaxation.  d_F(x), d_T(x) = distance of x to the forearm / trunk deep tissue, w = d_F / (d_F + d_T).  The gap between the two tissues is split in the ratio rho (the forearm share, from the margins):
    a forearm skin vertex must satisfy w <= rho - delta, a trunk skin vertex w >= rho + delta, so the two skins cannot cross.  A violating vertex moves toward its own tissue by the violation (mm); both sheets of a slab
    take the movement of the sheet that violates; Gaussian smoothing (4 mm), taper over 10 mm from the fixed neighbours, margin limit.  Pairs that survive (thin forearm corners, tapered rims) are removed by the
    trunk skin alone (absorb phase: the trunk vertices of a deep pair move toward their tissue by the pair depth)."""
    free = list(F_ids) + list(T_ids)
    isF = {i: (i in F_ids) for i in free}
    V = {i: V0[i].copy() for i in free}
    faces = {i: pg.f(i) for i in free}
    anc = anchors_of(pg, raw, set(free), V)
    anchors = np.concatenate([anc[i] for i in free])
    off, allv0, owner, shared, g = mesh_graph(V, faces, free, anchors)
    taper = np.clip(g / TAPER_MM, 0, 1)
    taper = taper * taper * (3 - 2 * taper)
    N = len(allv0)
    side_of = np.concatenate([[i[-1]] * len(V[i]) for i in free])
    isF_v = np.concatenate([[isF[i]] * len(V[i]) for i in free])
    tw = twins(raw, free, V)
    twg = np.full(N, -1)
    for i in free:
        t_ = tw[i]
        twg[off[i]: off[i] + len(t_)] = np.where(t_ >= 0, t_ + off[i], -1)
    tf = {s_: cKDTree(tissue[s_]) for s_ in "lr"}
    tt = cKDTree(tissue["trunk"])

    def geometry(cv):
        dF = np.zeros(N); dT = np.zeros(N); dirv = np.zeros((N, 3))
        for s_ in "lr":
            m = side_of == s_
            dF[m], kF = tf[s_].query(cv[m])
            dT[m], kT = tt.query(cv[m])
            mf = isF_v[m]
            pF = tissue[s_][kF] - cv[m]
            pT = tissue["trunk"][kT] - cv[m]
            pick = np.where(mf[:, None], pF, pT)                       # toward the OWN tissue
            dirv[m] = pick / np.maximum(np.linalg.norm(pick, axis=1, keepdims=True), 1e-9)
        return dF, dT, dirv
    cv = allv0.copy()
    dF, dT, dirv = geometry(cv)
    # the split ratio per side from the margins of the vertices that are in contact (initial F x T pairs)
    Vc, Fc, ow, nm = G.concat({i: (V[i], faces[i]) for i in free})
    pr = G.intersecting_pairs(Vc, Fc, ow)
    dd = G.pair_depth(Vc, Fc, pr) if len(pr) else np.zeros(0)
    loc0 = np.cumsum([0] + [len(faces[i]) for i in free])

    def gverts(fi):
        k = np.searchsorted(loc0, fi, side="right") - 1
        return off[free[k]] + faces[free[k]][fi - loc0[k]]
    inpair = np.zeros(N, bool)
    for (x, y), d in zip(pr, dd):
        if isF[nm[ow[x]]] != isF[nm[ow[y]]] and d > 0.3:
            inpair[gverts(x)] = True
            inpair[gverts(y)] = True
    rho_s = {}
    for s_ in "lr":
        mF_ = dF[inpair & isF_v & (side_of == s_)]
        mT_ = dT[inpair & ~isF_v & (side_of == s_)]
        rho_s[s_] = float(np.median(mF_) / (np.median(mF_) + np.median(mT_))) if rho is None else rho
        log(f"   side {s_}: contact vertices forearm {len(mF_)} (median margin {np.median(mF_):.1f} mm), trunk {len(mT_)} (median margin {np.median(mT_):.1f} mm) -> forearm share rho = {rho_s[s_]:.2f}")
    rho_v = np.where(side_of == "l", rho_s["l"], rho_s["r"])
    margin0 = np.where(isF_v, dF, dT)
    log(f"   free patches {len(free)} (forearm {len(F_ids)}, trunk / thigh {len(T_ids)}), {N} vertices, anchors {int(anchors.sum())}")
    hist = []
    tr0 = cKDTree(allv0)

    def count(Vd):
        Vc_, Fc_, ow_, nm_ = G.concat({i: (Vd[i], faces[i]) for i in free})
        pr_ = G.intersecting_pairs(Vc_, Fc_, ow_)
        dd_ = G.pair_depth(Vc_, Fc_, pr_) if len(pr_) else np.zeros(0)
        ft = [(x, y, d) for (x, y), d in zip(pr_, dd_) if isF[nm_[ow_[x]]] != isF[nm_[ow_[y]]]]
        return ft, nm_, ow_

    def smooth(u):
        """Gaussian smoothing of the movement over the ACTIVE neighbours of the same body (forearm or trunk, both sheets of the slabs): the two skins move in opposite directions where they overlap, so they must not be mixed"""
        cvv = np.vstack([V[i] for i in free])
        act = np.linalg.norm(u, axis=1) > 1e-6
        us = np.zeros_like(u)
        for grp in (isF_v, ~isF_v):
            gi = np.flatnonzero(grp)
            tr = cKDTree(cvv[gi])
            nb = tr.query_ball_point(cvv[gi], 3 * SIGMA)
            for kk, lst in enumerate(nb):
                lst = gi[np.asarray(lst)]
                a_ = lst[act[lst]]
                if len(a_) == 0:
                    continue
                k = gi[kk]
                w = np.exp(-np.linalg.norm(cvv[a_] - cvv[k], axis=1) ** 2 / (2 * SIGMA ** 2))
                wall = np.exp(-np.linalg.norm(cvv[lst] - cvv[k], axis=1) ** 2 / (2 * SIGMA ** 2))
                us[k] = (w[:, None] * u[a_]).sum(0) / w.sum() * min(1.0, w.sum() / (DAMP * wall.sum()))
        return us

    def finish(u):
        has = twg >= 0
        # both sheets of a slab take the movement of the sheet that violates (the larger one)
        a = np.flatnonzero(has)
        big = np.where((np.linalg.norm(u[a], axis=1) >= np.linalg.norm(u[twg[a]], axis=1))[:, None], u[a], u[twg[a]])
        u = u.copy()
        u[a] = big
        if len(shared):
            avg = 0.5 * (u[shared[:, 0]] + u[shared[:, 1]])
            u[shared[:, 0]] = avg
            u[shared[:, 1]] = avg
        return u

    def apply(u, cap_by_margin=True):
        nonlocal cv
        cvv = np.vstack([V[i] for i in free])
        dF_, dT_, dir_ = geometry(cvv)
        mg = np.where(isF_v, dF_, dT_)
        # margin limit for both sheets of a slab: the smaller margin of the two
        mg2 = np.where(twg >= 0, np.minimum(mg, mg[np.maximum(twg, 0)]), mg)
        nu = np.linalg.norm(u, axis=1)
        lim = np.maximum(mg2 - MARGIN_KEEP, 0.0)
        u = u * np.where(nu > lim, lim / np.maximum(nu, 1e-9), 1.0)[:, None]
        for i in free:
            V[i] = V[i] + u[off[i]: off[i] + len(V[i])]
        return u
    ft, nm_, ow_ = count(V)
    hist.append(dict(phase="start", ft_pairs=len(ft), gt0_3=sum(1 for r in ft if r[2] > STOP_DEPTH), deep_gt2=sum(1 for r in ft if r[2] > 2)))
    log(f"   start: forearm|trunk pairs {hist[-1]['ft_pairs']}, > 0.3 mm {hist[-1]['gt0_3']}, > 2 mm {hist[-1]['deep_gt2']}")
    for it in range(max_it):
        cvv = np.vstack([V[i] for i in free])
        dF, dT, dirv = geometry(cvv)
        eF = (1 - rho_v + delta) * dF - (rho_v - delta) * dT
        eT = (rho_v + delta) * dT - (1 - rho_v - delta) * dF
        e = np.where(isF_v, eF, eT)
        s = np.maximum(e, 0.0) * OVERRELAX
        if s.max() < 0.3:
            log(f"   partition it{it}: max violation {s.max():.2f} mm - done")
            break
        u = dirv * s[:, None]
        u = smooth(u) * taper[:, None]
        u = finish(u)
        u = apply(u)
        mv = np.linalg.norm(u, axis=1)
        if it % count_every == 0 or it == max_it - 1:
            ft, nm_, ow_ = count(V)
            hist.append(dict(phase="partition", it=it, max_violation_mm=round(float(s.max()), 2), moved_gt0_3=int((mv > 0.3).sum()), max_move_mm=round(float(mv.max()), 2), ft_pairs=len(ft), gt0_3=sum(1 for r in ft if r[2] > STOP_DEPTH), deep_gt2=sum(1 for r in ft if r[2] > 2)))
            log(f"   partition it{it}: violation max {s.max():.1f} mm, moved {int((mv > 0.3).sum())} (max {mv.max():.1f}); pairs {len(ft)}, > 0.3 mm {hist[-1]['gt0_3']}, > 2 mm {hist[-1]['deep_gt2']}")
        else:
            log(f"   partition it{it}: violation max {s.max():.1f} mm, moved {int((mv > 0.3).sum())} (max {mv.max():.1f})")
    Vp = {i: V[i].copy() for i in free}
    ft, nm_, ow_ = count(V)
    hist.append(dict(phase="after_partition", ft_pairs=len(ft), gt0_3=sum(1 for r in ft if r[2] > STOP_DEPTH), deep_gt2=sum(1 for r in ft if r[2] > 2), max_mm=round(float(max([r[2] for r in ft] or [0])), 2)))
    log(f"   after partition: forearm|trunk pairs {len(ft)}, > 0.3 mm {hist[-1]['gt0_3']}, > 2 mm {hist[-1]['deep_gt2']}, max {hist[-1]['max_mm']} mm")
    for it in range(absorb_it):
        if not ft or max(r[2] for r in ft) <= STOP_DEPTH:
            break
        pen = np.zeros(N)
        for x, y, d in ft:
            if d <= STOP_DEPTH:
                continue
            for fi, isf in ((x, isF[nm_[ow_[x]]]), (y, isF[nm_[ow_[y]]])):
                if not isf:
                    vv = gverts(fi)
                    pen[vv] = np.maximum(pen[vv], d * 1.3)
        cvv = np.vstack([V[i] for i in free])
        dF, dT, dirv = geometry(cvv)
        u = dirv * pen[:, None]
        u = smooth(u) * taper[:, None]
        u = finish(u)
        u = apply(u)
        mv = np.linalg.norm(u, axis=1)
        ft, nm_, ow_ = count(V)
        hist.append(dict(phase="absorb", it=it, moved_gt0_3=int((mv > 0.3).sum()), max_move_mm=round(float(mv.max()), 2), ft_pairs=len(ft), gt0_3=sum(1 for r in ft if r[2] > STOP_DEPTH), deep_gt2=sum(1 for r in ft if r[2] > 2)))
        log(f"   absorb it{it}: trunk moved {int((mv > 0.3).sum())} (max {mv.max():.1f}); pairs {len(ft)}, > 0.3 mm {hist[-1]['gt0_3']}, > 2 mm {hist[-1]['deep_gt2']}")
    return V, dict(hist=hist, free=free, F=list(F_ids), T=list(T_ids), rho=rho_s, V_partition=Vp, taper=taper, geodesic=g, off=off, anchors=anchors)


if __name__ == "__main__":
    from scripts.zanatomy import q210_build as B
    B.stage_contact()
