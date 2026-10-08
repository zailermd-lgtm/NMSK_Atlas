#!/usr/bin/env python3
"""Q210 (2): male forearm vs trunk / thigh / lateral-abdomen SKIN crossing (Q209: 1083 deep face pairs, median 5.0 mm, p90 9.6, max 17.2 mm; the arms rest on the body in the CT, the deep tissue is clear by 23-25 mm).
LOCAL SYMMETRIC CONTACT RELAXATION, skin only (no bone / muscle / vessel moves):
  * free patches: the 6 forearm / wrist slabs of each side and the trunk / thigh patches that cross them; every other skin patch is fixed (its shared border vertices are anchors);
  * each iteration: the face pairs forearm | trunk that cut through each other (q207_geom) give every vertex of the pair the penetration depth; the depth is SPLIT between the two skins in proportion to
    their margins over their own deep tissue (trunk skin stands 12-60 mm over trunk tissue, forearm skin 2.7-26 mm over forearm tissue): the share of the trunk skin is margin_trunk / (margin_trunk + margin_forearm);
    a vertex moves toward its OWN deep tissue (nearest bone / muscle point) by share x depth x relax, never further than margin - 1 mm (the thin forearm corners);
  * the movement is a function of POSITION (Gaussian smoothing over both sheets of the slabs, 4 mm: thickness kept), tapers to 0 over 10 mm of mesh distance from the anchors (welds / border steps kept), vertices
    shared by two free patches get the same movement;
  * stops when no forearm | trunk face pair is left deeper than 0.3 mm.
    python3 scripts/zanatomy/q210_contact.py"""
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
SIGMA, TAPER_MM, RELAX, MARGIN_KEEP, STOP_DEPTH = 4.0, 10.0, 1.4, 1.0, 0.3


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


def relax(pg, raw, V0, F_ids, T_ids, tissue, max_it=40, log=print):
    free = list(F_ids) + list(T_ids)
    isF = {i: (i in F_ids) for i in free}
    V = {i: V0[i].copy() for i in free}
    faces = {i: pg.f(i) for i in free}
    anc = anchors_of(pg, raw, set(free), V)
    anchors = np.concatenate([anc[i] for i in free])
    off, allv0, owner, shared, g = mesh_graph(V, faces, free, anchors)
    taper = np.clip(g / TAPER_MM, 0, 1)
    taper = taper * taper * (3 - 2 * taper)
    side_of = np.concatenate([[i[-1]] * len(V[i]) for i in free])
    isF_v = np.concatenate([[isF[i]] * len(V[i]) for i in free])
    # margins over the own deep tissue and the direction toward it
    tf = {s: cKDTree(tissue[s]) for s in "lr"}
    tt = cKDTree(tissue["trunk"])
    N = len(allv0)
    margin = np.zeros(N)
    towards = np.zeros((N, 3))
    for s in "lr":
        for isf in (True, False):
            m = (side_of == s) & (isF_v == isf)
            if not m.any():
                continue
            tr, P = (tf[s], tissue[s]) if isf else (tt, tissue["trunk"])
            d, k = tr.query(allv0[m])
            margin[m] = d
            tw = P[k] - allv0[m]
            towards[m] = tw / np.maximum(np.linalg.norm(tw, axis=1, keepdims=True), 1e-9)
    log(f"   free patches {len(free)} (forearm {len(F_ids)}, trunk / thigh {len(T_ids)}), {N} vertices, anchors {int(anchors.sum())}; margin over own tissue: forearm min {margin[isF_v].min():.1f} median {np.median(margin[isF_v]):.1f}, trunk min {margin[~isF_v].min():.1f} median {np.median(margin[~isF_v]):.1f}")
    total = np.zeros((N, 3))
    hist = []
    for it in range(max_it):
        cur = np.vstack([V[i] for i in free]) if it else allv0.copy()
        Vc, Fc, ow, nm = G.concat({i: (V[i], faces[i]) for i in free})
        pr = G.intersecting_pairs(Vc, Fc, ow)
        dd = G.pair_depth(Vc, Fc, pr) if len(pr) else np.zeros(0)
        # F x T pairs
        ft = [(x, y, d) for (x, y), d in zip(pr, dd) if isF[nm[ow[x]]] != isF[nm[ow[y]]]]
        deep = [r for r in ft if r[2] > 2.0]
        mx = max([r[2] for r in ft] or [0])
        n03 = sum(1 for r in ft if r[2] > STOP_DEPTH)
        hist.append(dict(it=it, ft_pairs=len(ft), gt0_3=n03, deep_gt2=len(deep), max_mm=round(float(mx), 2)))
        log(f"   it{it}: forearm|trunk pairs {len(ft)}, > {STOP_DEPTH} mm {n03}, > 2 mm {len(deep)}, max {mx:.2f} mm")
        if n03 == 0:
            break
        # vertex penetration: both skins; global vertex index = off[patch] + local
        pen = np.zeros(N)
        # local face -> global vertex ids
        loc0 = np.cumsum([0] + [len(f) for f in (faces[i] for i in free)])
        def gverts(fi):
            k = np.searchsorted(loc0, fi, side="right") - 1
            i = free[k]
            return off[i] + faces[i][fi - loc0[k]]
        for x, y, d in ft:
            va, vb = gverts(x), gverts(y)
            f_va, t_vb = (va, vb) if isF[nm[ow[x]]] else (vb, va)
            mF, mT = margin[f_va].mean(), margin[t_vb].mean()
            sF = mF / max(mF + mT, 1e-6)
            sF = np.clip(sF, 0.05, 0.95)
            pen[f_va] = np.maximum(pen[f_va], sF * d * RELAX)
            pen[t_vb] = np.maximum(pen[t_vb], (1 - sF) * d * RELAX)
        u = towards * pen[:, None]
        # position-based smoothing over both sheets (and the shared vertices of free patches)
        cv = np.vstack([V[i] for i in free])
        tr = cKDTree(cv)
        nb = tr.query_ball_point(cv, 3 * SIGMA)
        act = np.linalg.norm(u, axis=1) > 1e-6
        # Gaussian average over the ACTIVE neighbours; the share of active weight (x 1 / 0.35, capped at 1) lets the movement decay away from the contact
        us2 = np.zeros_like(u)
        for k, lst in enumerate(nb):
            lst = np.asarray(lst)
            a = lst[act[lst]]
            if len(a) == 0:
                continue
            w = np.exp(-np.linalg.norm(cv[a] - cv[k], axis=1) ** 2 / (2 * SIGMA ** 2))
            wall = np.exp(-np.linalg.norm(cv[lst] - cv[k], axis=1) ** 2 / (2 * SIGMA ** 2))
            us2[k] = (w[:, None] * u[a]).sum(0) / w.sum() * min(1.0, w.sum() / (0.35 * wall.sum()))
        u = us2 * taper[:, None]
        # shared vertices of two free patches: the same movement
        if len(shared):
            avg = 0.5 * (u[shared[:, 0]] + u[shared[:, 1]])
            u[shared[:, 0]] = avg
            u[shared[:, 1]] = avg
        # margin limit: never further than margin - MARGIN_KEEP toward the own tissue
        nu = np.linalg.norm(u, axis=1)
        lim = np.maximum(margin - MARGIN_KEEP, 0.0)
        sc = np.where(nu > lim, lim / np.maximum(nu, 1e-9), 1.0)
        u = u * sc[:, None]
        total += u
        for i in free:
            V[i] = V[i] + u[off[i]: off[i] + len(V[i])]
        mv = np.linalg.norm(u, axis=1)
        log(f"      moved: vertices > 0.3 mm {int((mv > 0.3).sum())}, max {mv.max():.2f} mm, forearm max {mv[isF_v].max():.2f}, trunk max {mv[~isF_v].max():.2f}")
        # recompute the margin along the way (distance to the own tissue at the new place)
        cv2 = np.vstack([V[i] for i in free])
        for s in "lr":
            for isf in (True, False):
                m = (side_of == s) & (isF_v == isf)
                if m.any():
                    margin[m] = (tf[s] if isf else tt).query(cv2[m])[0]
    return V, dict(hist=hist, free=free, F=list(F_ids), T=list(T_ids), total_move_max=float(np.linalg.norm(total, axis=1).max()))


if __name__ == "__main__":
    pg, raw = K.load(REPO / "build/q210/_after_genital" if (REPO / "build/q210/_after_genital").exists() else None)
    V0 = {i: pg.v(i) for i in pg.skin_ids}
    Fs, Ts, cand = find_sets(pg, V0)
    print("F", [i[9:] for i in Fs], "T", [i[9:] for i in Ts])
    tis = tissue_points(pg)
    t = time.time()
    V, rep = relax(pg, raw, V0, forearm_ids(pg), Ts, tis)
    print(rep["hist"][-1], time.time() - t)
    pickle.dump((V, rep), open(K.state_path("contact"), "wb"))
