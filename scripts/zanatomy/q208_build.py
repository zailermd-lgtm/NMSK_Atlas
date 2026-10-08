#!/usr/bin/env python3
"""Q208 build of the two Z-fitted pages (in-process patch of the Q207 pages, no Z build):
   stage tube   : forearm / wrist skin slabs re-warped from the Z source onto the person's own skin (bone-pair frames), welded to the fixed hand neighbours     (q208_refit)
   stage elbow  : elbow / cubital slabs re-warped between the fixed arm skin and the new forearm skin                                                          (q208_elbow)
   stage uro    : male urogenital rims welded to the anal / thigh patches (neighbours move slightly)                                                            (q208_uro)
   stage pack   : changed skin patches re-packed with before -> after badges, all other structures byte for byte                                                 (q208_pack)
    python3 scripts/zanatomy/q208_build.py male|female tube|elbow|uro|pack|all"""
from __future__ import annotations

import pickle
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q208_core as K  # noqa: E402
from scripts.zanatomy import q208_refit as RF  # noqa: E402
from scripts.zanatomy import q208_tube as T  # noqa: E402

MARGIN = 1.0


def stage_tube(which, log=print, margin=MARGIN, sides="lr"):
    from scripts.zanatomy.q207_inflate import OwnSkin
    pg, raw = K.load(which)
    own = OwnSkin(which)
    V = {i: pg.v(i) for i in pg.skin_ids}
    info = {}
    for side in sides:
        s = "_" + side
        Wr, Wp = raw.wrist()[side], pg.wrist()[side]
        Fs = T.Frames(raw.v("radius" + s), raw.v("ulna" + s), Wr)
        Fp = T.Frames(pg.v("radius" + s), pg.v("ulna" + s), Wp)
        ss = np.concatenate([(raw.v(b + s) - Wr) @ Fs.a for b in ("radius", "ulna")])
        sp = np.concatenate([(pg.v(b + s) - Wp) @ Fp.a for b in ("radius", "ulna")])
        g = T.monotone_map(ss, sp)
        ids = [K.pid(n, side) for n in K.TUBE]
        S = RF.Slabs({i: raw.v(i) for i in ids}, {i: pg.f(i) for i in ids}, ids)
        prof = T.OwnProfile(own.tm, Fp, g(-262.0), g(45.0))
        P, outer, co = RF.tube_positions(S, Fs, Fp, g, prof, margin=margin, outer=S.outer_flags(bone_pts=K.side_bones(raw, side)))
        nb = [K.pid(n, side) for n in K.WRIST_NB]
        tgf = RF.rim_targets(S, None, {i: raw.v(i) for i in nb}, {i: V[i] for i in nb})
        tg = {vi: t[0] for vi, t in tgf.items() if not t[3]}
        P2, D = RF.correct(S, P, tg)
        log(f"[{which} {side}] profile bad {prof.nbad}, wrist rim vertices fixed {len(tg)} (stray neighbour vertices re-seated {len(tgf) - len(tg)}), correction max {np.linalg.norm(D, axis=1).max():.1f} mm")
        for i, v in S.split(P2).items():
            V[i] = v
        reseat = reseat_neighbours(V, tgf, P2)
        info[side] = dict(outer=S.split(outer), nfix=len(tg), reseated=reseat)
    pickle.dump((V, info), open(K.state_path(which, "tube"), "wb"))
    return V, info


def reseat_neighbours(V, tgf, P):
    """a neighbour vertex whose inner / outer twin the earlier fits pulled apart (stray sheet vertex) is not used as a weld target: it is re-seated on the refitted patch's vertex (V is modified); -> {neighbour id: count}"""
    out = {}
    for vi, (pos, nb_id, nb_idx, stray) in tgf.items():
        if stray:
            v = V[nb_id].copy()
            v[nb_idx] = P[vi]
            V[nb_id] = v
            out[nb_id] = out.get(nb_id, 0) + 1
    return out


def own_targets(own_tm, X, S, outer_nodes, margin=MARGIN, min_cos=0.5):
    """soft targets of the OUTER nodes on the person's own skin (nearest point moved inward by `margin`), only where the own skin faces the same way as the slab (outward normal = twin direction)"""
    import trimesh
    nodes = np.flatnonzero(outer_nodes)
    pts = X[nodes]
    cp, dist, tri = trimesh.proximity.closest_point(own_tm, pts)
    nf = own_tm.face_normals[tri]
    # outward direction of the slab at a node: outer node - its inner twin
    inner_of = {}
    tw = S.twin
    node_inner = np.zeros((S.nnode, 3))
    cnt = np.zeros(S.nnode)
    d = X[S.node] - X[S.node[tw]]
    np.add.at(node_inner, S.node, d)
    np.add.at(cnt, S.node, 1)
    u = node_inner[nodes] / np.maximum(np.linalg.norm(node_inner[nodes], axis=1, keepdims=True), 1e-9)
    ok = ((nf * u).sum(1) > min_cos) & (dist < 40.0)
    return nodes[ok], (cp - margin * nf)[ok], ok


def harmonic_start(S, fixed):
    """starting positions of all nodes: the graph-Laplacian (harmonic) interpolation of the fixed rim nodes (chords between the rims; the own-skin pull then drapes them)"""
    from scipy.sparse.linalg import spsolve
    L, A = RF.laplacian(S.nnode, RF.node_graph(S)[0])
    fk = np.array(sorted(fixed))
    free = np.setdiff1d(np.arange(S.nnode), fk)
    D = np.array([fixed[k] for k in fk])
    X = np.zeros((S.nnode, 3))
    X[fk] = D
    L = L.tocsr()
    X[free] = spsolve(L[free][:, free].tocsc(), -L[free][:, fk] @ D)
    return X


def fill_unset(S, P):
    """vertices that no rule placed (a stray twin pair of a rim: both flagged inner) take the mean of their mesh neighbours' positions"""
    P = P.copy()
    unset = np.linalg.norm(P, axis=1) < 1e-9
    if not unset.any():
        return P
    e = np.concatenate([S.F[:, [0, 1]], S.F[:, [1, 2]], S.F[:, [2, 0]]])
    e = np.vstack([e, e[:, ::-1]])
    for _ in range(10):
        if not unset.any():
            break
        ok = ~unset
        m = unset[e[:, 0]] & ok[e[:, 1]]
        acc = np.zeros_like(P)
        cnt = np.zeros(len(P))
        np.add.at(acc, e[m, 0], P[e[m, 1]])
        np.add.at(cnt, e[m, 0], 1)
        got = cnt > 0
        P[got] = acc[got] / cnt[got][:, None]
        unset = unset & ~got
    return P


def relieve(pg, V, S, ids, P, outer, neighbours, rounds=8, factor=0.8, min_frac=0.4, depth_mm=1.5, log=None):
    """thin the inner sheet (inner = outer + f (inner - outer), f >= min_frac) of the slab vertices that take part in a deep skin crossing (> depth_mm) with the neighbouring slabs, until no deep crossing is left"""
    from scripts.zanatomy import q207_geom as G
    P = P.copy()
    inner = ~outer
    frac = np.ones(len(P))
    base = P.copy()
    ck = list(ids) + [i for i in neighbours if i not in ids]
    offs = {i: o for i, o in zip(ids, S.off[:-1])}
    n_hit = 0
    for rd in range(rounds):
        Vc = dict(V)
        for i, v in S.split(P).items():
            Vc[i] = v
        M, Fc, ow, nm = G.concat({i: (Vc[i], pg.f(i)) for i in ck})
        pr = G.intersecting_pairs(M, Fc, ow)
        if not len(pr):
            break
        dd = G.pair_depth(M, Fc, pr)
        pr = pr[dd > depth_mm]
        if not len(pr):
            break
        starts = np.cumsum([0] + [len(V[i]) for i in ck])
        hit = []
        for f_ in np.unique(pr):
            i = ck[ow[f_]]
            if i in offs:
                hit.extend((Fc[f_] - starts[ow[f_]] + offs[i]).tolist())
        hit = np.unique(hit).astype(int)
        sel = np.unique(np.r_[hit[inner[hit]], S.twin[hit[~inner[hit]]]]).astype(int)
        sel = sel[inner[sel]]
        if not len(sel):
            break
        frac[sel] = np.maximum(frac[sel] * factor, min_frac)
        tw = S.twin
        P = np.where(inner[:, None], P[tw] + frac[:, None] * (base - base[tw]), P) if False else np.where(inner[:, None], base[tw] + frac[:, None] * (base - base[tw]), base)
        n_hit = int((frac < 1 - 1e-9).sum())
        if log:
            log(f"      relief round {rd}: {len(pr)} deep pairs, {n_hit} inner vertices thinned")
    return P, dict(thinned=n_hit, min_fraction=float(frac.min()))


def elbow_side_e1(pg, raw, own, V, side, mu=0.05, relief=True, log=None):
    """elbow slabs keep their Q207 shape; the rims that touch the refitted forearm skin follow it (harmonic displacement, decays into the patch), the rims at the arm skin stay.
    Where the slabs of the crease still cut through each other deeper than 1.5 mm the inner sheet is thinned there (down to 40 % of its thickness)."""
    ids = [K.pid(n, side) for n in K.ELBOW]
    S = RF.Slabs({i: raw.v(i) for i in ids}, {i: pg.f(i) for i in ids}, ids)
    outer = S.outer_flags(bone_pts=K.side_bones(raw, side))
    nb = [K.pid(n, side) for n in K.TUBE + K.ARM_NB]
    tgf = RF.rim_targets(S, None, {i: raw.v(i) for i in nb}, {i: V[i] for i in nb}, tol=1.5)
    tg = {vi: t[0] for vi, t in tgf.items() if not t[3]}
    P0 = np.vstack([pg.v(i) for i in ids])
    P2, D = RF.correct(S, P0, tg, mu=mu)
    info = dict(tgf=tgf, nfixed=len(tg), outer=outer, relief=None)
    if relief:
        P2, info["relief"] = relieve(pg, V, S, ids, P2, outer, nb, log=log)
        for vi, p in tg.items():          # welded vertices stay exactly on the neighbour
            P2[vi] = p
    return S, P2, info


def elbow_side(pg, raw, own, V, side, margin=MARGIN, thickness=3.0, mu_in=0.05, spring="inv_len", normals="own", drape=False, w_pull=8.0, relief=True, nsmooth=3, start="harmonic", step=1.0, proj_every=5, iters=300, radial=False, e1_hint=False, ruled=False):
    """elbow / cubital slabs of one side between the fixed arm skin and the refitted forearm skin (V: current skin).  -> (S, P2 vertex positions, info dict)"""
    s = "_" + side
    Fs = T.Frames(raw.v("radius" + s), raw.v("ulna" + s), raw.wrist()[side])
    ids = [K.pid(n, side) for n in K.ELBOW]
    S = RF.Slabs({i: raw.v(i) for i in ids}, {i: pg.f(i) for i in ids}, ids)
    outer = S.outer_flags(bone_pts=K.side_bones(raw, side))
    nb = [K.pid(n, side) for n in K.TUBE + K.ARM_NB]
    tgf = RF.rim_targets(S, None, {i: raw.v(i) for i in nb}, {i: V[i] for i in nb}, tol=1.5)
    tg = {vi: t[0] for vi, t in tgf.items() if not t[3]}
    fixed_v = {}
    for vi, p in tg.items():
        fixed_v.setdefault(int(S.node[vi]), []).append(p)
    fixed = {k: np.mean(v, 0) for k, v in fixed_v.items()}
    outer_nodes = set(S.node[outer].tolist())
    outer_fixed = {k: p for k, p in fixed.items() if k in outer_nodes}
    hint = np.vstack([V[i] for i in ids])
    if ruled:
        arm_n = {K.pid(x, side) for x in K.ARM_NB}
        top = {vi: t[0] for vi, t in tgf.items() if not t[3] and t[1] in arm_n and outer[vi]}
        bot = {vi: t[0] for vi, t in tgf.items() if not t[3] and t[1] not in arm_n and outer[vi]}
        hint = RF.rim_ruled_positions(S, Fs, top, bot)
        start = "hint"
    if e1_hint:
        hint, _ = RF.correct(S, np.vstack([pg.v(i) for i in ids]), {vi: t[0] for vi, t in tgf.items() if not t[3]}, mu=0.2)
        start = "hint"
    centre = None
    if radial:
        ul, hu = raw.v("ulna" + s), raw.v("humerus" + s)
        pu, ph = pg.v("ulna" + s), pg.v("humerus" + s)
        wr = pg.wrist()[side]
        a = pu.mean(0) - wr
        a /= np.linalg.norm(a)
        O_ = 0.5 * (pu[np.argmax((pu - wr) @ a)] + ph[np.argmin((ph - wr) @ a)])
        ha_ = np.linalg.svd(ph - ph.mean(0), full_matrices=False)[2][0]
        if ha_ @ a > 0:
            ha_ = -ha_                    # toward the shoulder
        centre = np.array([[O_, O_ + 160 * ha_], [O_, O_ + 160 * a]])
    if start == "lbs":
        hint, start = RF.lbs_positions(S, raw, pg, side, Fs=Fs), "hint"
    Xo, nrm, onode = RF.surface_harmonic(S, outer, outer_fixed, own.tm, margin=margin, hint=hint, spring=spring, start=start, step=step, proj_every=proj_every, iters=iters, centre=centre)
    if drape:
        free_mask = onode & ~np.isin(np.arange(S.nnode), list(outer_fixed))
        Xo2, nrm2 = RF.drape_asap(S, outer, Xo, outer_fixed, own.tm, margin=margin, w_pull=w_pull, free_mask=free_mask)
        Xo = np.where(free_mask[:, None], Xo2, Xo)
        nrm = np.where(free_mask[:, None], nrm2, nrm)
    if normals == "mesh":
        nrm = RF.mesh_normals(S, outer, Xo, nrm)
    P = np.zeros((len(S.V), 3))
    P[outer] = Xo[S.node[outer]]
    inner = ~outer
    P_outer = P.copy()
    tvec = np.full(len(S.V), thickness)
    inner_targets = {vi: p for vi, p in tg.items() if inner[vi]}
    nb_all = [K.pid(n, side) for n in K.TUBE + K.ARM_NB]

    def build_inner(tvec):
        Q = P_outer.copy()
        Q[inner] = Q[S.twin[inner]] - tvec[inner][:, None] * nrm[S.node[S.twin[inner]]]
        Q = fill_unset(S, Q)
        Q2, D = RF.correct(S, Q, inner_targets, mu=mu_in)
        for vi, p in tg.items():
            if outer[vi]:
                Q2[vi] = p
        return Q2, D
    P2, D = build_inner(tvec)
    relief_info = {"rounds": 0, "vertices_thinned": 0, "min_mm": thickness}
    if relief:
        from scripts.zanatomy import q207_geom as G
        ck = [i for i in ids] + nb_all
        for rd in range(8):
            Vc = dict(V)
            for i, v in S.split(P2).items():
                Vc[i] = v
            M, Fc, ow, nm = G.concat({i: (Vc[i], pg.f(i)) for i in ck})
            pr = G.intersecting_pairs(M, Fc, ow)
            if not len(pr):
                break
            dd = G.pair_depth(M, Fc, pr)
            pr = pr[dd > 1.5]
            if not len(pr):
                break
            offs = np.cumsum([0] + [len(V[i]) for i in ck])
            hit = set()
            for f_ in np.unique(pr):
                pi = ow[f_]
                if ck[pi] in ids:
                    base = offs[pi]
                    local = S.off[ids.index(ck[pi])]
                    hit.update((Fc[f_] - base + local).tolist())
            hit = np.array(sorted(hit), int)
            hit_in = hit[inner[hit]] if len(hit) else hit
            hit_tw = S.twin[hit[~inner[hit]]] if len(hit) else hit
            sel = np.unique(np.r_[hit_in, hit_tw]).astype(int)
            sel = sel[inner[sel]]
            if not len(sel):
                break
            tvec[sel] = np.maximum(tvec[sel] * 0.8, 1.2)
            P2, D = build_inner(tvec)
            relief_info = {"rounds": rd + 1, "vertices_thinned": int((tvec < thickness - 1e-6).sum()), "min_mm": float(tvec.min())}
    return S, P2, dict(outer=outer, tgf=tgf, nfixed=len(fixed), inner_corr_max=float(np.linalg.norm(D, axis=1).max()), Xo=Xo, onode=onode, relief=relief_info)


def stage_elbow(which, log=print, margin=MARGIN, sides="lr", **kw):
    from scripts.zanatomy.q207_inflate import OwnSkin
    pg, raw = K.load(which)
    own = OwnSkin(which)
    V, info = pickle.load(open(K.state_path(which, "tube"), "rb"))
    V = dict(V)
    rep = {}
    for side in sides:
        S, P2, d = elbow_side(pg, raw, own, V, side, margin=margin, **kw)
        sd = own.sd(P2[d["outer"]])
        log(f"[{which} {side}] elbow: {d['nfixed']} fixed nodes of {S.nnode}; outer own-skin dist med {np.median(sd):.2f} p5 {np.percentile(sd,5):.2f} p95 {np.percentile(sd,95):.2f}; inner correction max {d['inner_corr_max']:.1f}")
        for i, v in S.split(P2).items():
            V[i] = v
        rep[side] = dict(fixed=d["nfixed"], reseated=reseat_neighbours(V, d["tgf"], P2))
    pickle.dump((V, rep), open(K.state_path(which, "elbow"), "wb"))
    return V, rep

if __name__ == "__main__":
    which, stage = sys.argv[1], sys.argv[2]
    stages = ["tube", "elbow", "uro"] if stage == "all" else [stage]
    for s_ in stages:
        globals()["stage_" + s_](which)
