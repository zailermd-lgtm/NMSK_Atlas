#!/usr/bin/env python3
"""Q210 (1): the male genital structures lie OUTSIDE the Q207 / Q208 urogenital skin.  Decision (numbers in Q210_genital_male.json): the SKIN follows the structures.
Q207 refit the two urogenital skin halves to the Z-SOURCE volume (37.1 k mm3 each) while the fitted structures kept the fit scale of the person (testes +30 % volume, spongiosum +22 %, penis length +20 %, all of them inside
his own CT skin); moving the structures with the Q207 skin warp would shorten the penis by 8-37 % (glans 45 -> 28 mm) and shrink the testes by 20 %.  Here the Q207 refit (q207_uro.refit_split: ONE similarity +
harmonic residual onto the fixed neighbours, nodes at the seam) is re-run with the volume target of the person's own genital scale: the smallest target (2 k mm3 grid) at which every listed structure is enclosed
(audit measure: no vertex > 3 mm outside the Q198 envelope; 1 mm envelope: <= 12 % of the vertices > 0.5 mm, none > 5 mm outside), then the Q208 rim weld (q208_uro.weld) closes the border steps again (l | r seam nodes merged within 12 mm of the Z source, SEAM_MM).  The refit shape is looser than the structures (its outer sheet lies up to 19 mm outside his own CT skin, which the structures touch from
inside), so the outer sheet is finally CLAMPED onto his own skin (own_clamp: 0.3 mm inside it, both sheets of a slab together, welds kept): the skin encloses the structures and stays inside his own skin.
    python3 scripts/zanatomy/q210_genital.py [T_mm3 ...]        (no argument: search the target)"""
from __future__ import annotations

import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q210_core as K  # noqa: E402
from scripts.zanatomy import q207_uro as U7  # noqa: E402
from scripts.zanatomy import q208_uro as U8  # noqa: E402


SEAM_MM = 12.0      # l | r seam nodes: vertices of one half within 12 mm of the other half at the midline in the Z source are one node (Q207: 4.5 mm; at the larger volume the perineal slit of the source,
#                     up to ~11 mm at its anal end, stayed open and 7 of 4000 rays from the perineal probe point escaped through it)


def refit(pg, raw, V0, T, own=None, seam_mm=SEAM_MM, log=lambda *a: None):
    ids = list(K.UROS)
    oth = [i for i in pg.skin_ids if i not in ids and i in raw.S]
    orig = U7.build_nodes
    U7.build_nodes = lambda *a, **k: orig(*a, **{**k, "seam_mm": seam_mm})
    try:
        out, rep = _refit_split(pg, raw, V0, T, ids, oth, log)
    finally:
        U7.build_nodes = orig
    rep["seam_mm"] = seam_mm
    return _finish(pg, raw, V0, out, rep, own, log)


def _refit_split(pg, raw, V0, T, ids, oth, log):
    return U7.refit_split({i: raw.v(i) for i in ids}, {i: pg.v(i) for i in ids}, {i: pg.f(i) for i in ids}, {i: raw.v(i) for i in oth}, {i: V0[i] for i in oth},
                          others_faces={i: pg.f(i) for i in oth}, vol_target=T, log=log)


def _finish(pg, raw, V0, out, rep, own, log):
    V = dict(V0)
    V.update(out)
    rawv = {i: raw.v(i) for i in pg.skin_ids if i in raw.S}
    faces = {i: pg.f(i) for i in pg.skin_ids}
    V2, info = U8.weld(faces, rawv, V, list(rawv), w_pull=20.0, lam_s=0.3, log=lambda *a: None)
    rep["weld"] = {i: [round(float(np.linalg.norm(V2[i] - V[i], axis=1).max()), 2), round(float(np.linalg.norm(V2[i] - V[i], axis=1).mean()), 2)] for i in info["free"]}
    if own is not None:
        V2, rep["own_clamp"] = own_clamp(pg, raw, V2, own, log=log)
    return V2, rep


def own_clamp(pg, raw, V, own, margin=0.3, sigma=3.0, taper_mm=10.0, ids=K.UROS, log=lambda *a: None):
    """The refit (Z-source shape at the structures' scale) is looser than the structures: its outer sheet lies up to 19 mm OUTSIDE his own CT skin, which the Q206 skin the structures were fitted to never did
    (structures touch his own skin from inside: 0 % outside, closest 0.1 mm).  The outer sheet is clamped onto his own skin: a vertex that is outside it (or closer than `margin` to its surface) moves inward along the own-skin
    normal to `margin` inside; both sheets of a slab take the movement of the sheet that moves most (thickness kept); Gaussian smoothing (sigma) over the two halves; the movement tapers to 0 over `taper_mm` of mesh
    distance from the vertices shared with the fixed neighbours (welds kept).  A vertex never moves further than its structure allows: the structure vertices stay enclosed (checked by the caller)."""
    import trimesh
    from scipy.spatial import cKDTree
    from scripts.zanatomy import q210_contact as CT
    free = list(ids)
    Vf = {i: V[i].copy() for i in free}
    faces = {i: pg.f(i) for i in free}
    anc = CT.anchors_of(pg, raw, set(free), Vf)
    anchors = np.concatenate([anc[i] for i in free])
    off, allv, owner, shared, g = CT.mesh_graph(Vf, faces, free, anchors)
    taper = np.clip(g / taper_mm, 0, 1)
    taper = taper * taper * (3 - 2 * taper)
    tw = CT.twins(raw, free, Vf)
    twg = np.full(len(allv), -1)
    for i in free:
        t_ = tw[i]
        twg[off[i]: off[i] + len(t_)] = np.where(t_ >= 0, t_ + off[i], -1)
    s = own.sd(allv)
    cp, dist, tri = trimesh.proximity.closest_point(own.tm, allv)
    nrm = own.tm.face_normals[tri]
    move = np.maximum(s + margin, 0.0)                               # inward distance needed (mm)
    u = -nrm * move[:, None]
    # both sheets of a slab: the larger movement
    a_ = np.flatnonzero(twg >= 0)
    big = np.where((np.linalg.norm(u[a_], axis=1) >= np.linalg.norm(u[twg[a_]], axis=1))[:, None], u[a_], u[twg[a_]])
    u[a_] = big
    # smoothing (Gaussian over active neighbours, both halves)
    act = np.linalg.norm(u, axis=1) > 1e-6
    tr = cKDTree(allv)
    nb = tr.query_ball_point(allv, 3 * sigma)
    us = np.zeros_like(u)
    for k, lst in enumerate(nb):
        lst = np.asarray(lst)
        a2 = lst[act[lst]]
        if len(a2) == 0:
            continue
        w = np.exp(-np.linalg.norm(allv[a2] - allv[k], axis=1) ** 2 / (2 * sigma ** 2))
        wall = np.exp(-np.linalg.norm(allv[lst] - allv[k], axis=1) ** 2 / (2 * sigma ** 2))
        us[k] = (w[:, None] * u[a2]).sum(0) / w.sum() * min(1.0, w.sum() / (0.12 * wall.sum()))
    us = us * taper[:, None]
    if len(shared):
        avg = 0.5 * (us[shared[:, 0]] + us[shared[:, 1]])
        us[shared[:, 0]] = avg
        us[shared[:, 1]] = avg
    out = dict(V)
    for i in free:
        out[i] = V[i] + us[off[i]: off[i] + len(V[i])]
    nu = np.linalg.norm(us, axis=1)
    s1 = own.sd(np.vstack([out[i] for i in free]))
    info = {"vertices_moved_gt0_3": int((nu > 0.3).sum()), "max_move_mm": round(float(nu.max()), 1), "outside_own_skin_gt2mm_pct": [round(float((s > 2).mean() * 100), 1), round(float((s1 > 2).mean() * 100), 1)],
            "outside_own_skin_max_mm": [round(float(s.max()), 1), round(float(s1.max()), 1)]}
    return out, info


def passes(rows, main_ids=K.GEN_MAIN, fine_tol=12.0, fine_max=5.0):
    """enclosed: no vertex > 3 mm outside the Q198 envelope (audit measure) and, on the 1 mm envelope, <= 12 % of the vertices > 0.5 mm / none > 5 mm outside (the Q206 skin the structures were fitted to: 0-17 % / 4 mm).
    The external pudendal vessels (groin, drawn from the fixed inguinal / thigh patches) are outside the urogenital patch domain: reported, not part of the test."""
    bad = {i: r for i, r in rows.items() if i in main_ids and (r["audit_gt3_pct"] > 0.0 or r.get("fine_gt0.5_pct", 0) > fine_tol or r.get("fine_max_mm", 0) > fine_max)}
    return not bad, bad


def evaluate(pg, V, with_fine=True):
    sf = K.coarse(pg, V)
    fine = K.fine_box(pg, V, sf) if with_fine else None
    return sf, K.outside_rows(pg, sf, fine=fine)


def search(pg, raw, V0, grid=(48000, 50000, 52000, 54000, 56000, 58000, 60000), log=print):
    from scripts.zanatomy.q207_inflate import OwnSkin
    own = OwnSkin("male")
    trials = {}
    lo, hi = 0, len(grid) - 1
    best = None
    # bisection over the (monotone) target: the smallest passing one
    while lo <= hi:
        mid = (lo + hi) // 2
        T = grid[mid]
        t = time.time()
        V, rep = refit(pg, raw, V0, T, own=own)
        sf, rows = evaluate(pg, V)
        ok, bad = passes(rows)
        trials[T] = dict(ok=ok, volumes=rep["volumes"], scale=rep["scale"], own_clamp=rep.get("own_clamp"), bad={i[4:]: [r["audit_gt3_pct"], r["audit_max_mm"], r.get("fine_gt0.5_pct")] for i, r in bad.items()})
        log(f"T={T}: volumes (before the own-skin clamp) {rep['volumes']} pass={ok} bad={list(trials[T]['bad'])}  [{time.time() - t:.0f}s]")
        if ok:
            best = (T, V, rep)
            hi = mid - 1
        else:
            lo = mid + 1
    return best, trials


if __name__ == "__main__":
    pg, raw = K.load()
    V0 = {i: pg.v(i) for i in pg.skin_ids}
    if len(sys.argv) > 1:
        T = int(sys.argv[1])
        from scripts.zanatomy.q207_inflate import OwnSkin
        V, rep = refit(pg, raw, V0, T, own=OwnSkin("male"))
        sf, rows = evaluate(pg, V)
        print(T, rep["volumes"], rep["weld"], passes(rows)[0], {i[4:20]: (r["audit_gt3_pct"], r["audit_max_mm"], r["fine_gt0.5_pct"]) for i, r in rows.items()})
    else:
        best, trials = search(pg, raw, V0)
        T, V, rep = best
        pickle.dump((V, dict(T=T, rep=rep, trials=trials)), open(K.state_path("genital"), "wb"))
        print("chosen T", T)
