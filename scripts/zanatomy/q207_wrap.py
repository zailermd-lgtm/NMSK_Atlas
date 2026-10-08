"""Q207 skin clearing (replaces the normal-based inflation and the envelope-union shrink wrap, both of which spiked / leaked on the collapsed wrist skin): the MINIMAL outward movement of the skin so
that no structure of the hand / wrist / distal forearm lies outside it.

  * the structure vertices that are outside the skin (or closer than the class margin to its outer surface) are the obstacles (points q with margin m);
  * every outer-sheet skin vertex x with the outward normal n(x) (gradient of the smoothed signed distance of the CURRENT skin envelope) is raised along n(x) by
        r(x) = max over obstacles q within the lateral radius rho(x) of the normal line:  (q - x).n + m(q),   r >= 0
    -- the lowest position from which the faces around x clear every obstacle (rho = the local mesh scale, a field of POSITION: a vertex shared by two patches gets the same movement);
  * inner sheet / rim vertices take the Gaussian-weighted movement of the outer-sheet vertices around them (position-based: both sheets of a slab move together = thickness kept);
  * only outward movement along the old normal: monotone, no leak, vertices out of reach move by exactly 0; the person's own CT / cryosection skin limits the outward movement (a vertex never
    leaves it); iterated until the check passes."""
from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q207_core as C  # noqa: E402
from scripts.zanatomy.q207_inflate import POLICY, demands, OwnSkin  # noqa: E402,F401

OUTER_SD_MM = -1.2        # skin vertices with envelope depth above this are the outer sheet (the inner sheet lies one slab thickness, 3 mm, below)
KERNEL_SIGMA_MM = 3.0
SMOOTH_SIGMA_MM = 3.0
RHO_MIN, RHO_MAX = 3.0, 9.0
H_MAX = 16.0              # obstacles further than this above a vertex along its normal are not followed here
RELAX = 1.0


def obstacles(page, fine, dem, tol=0.0):
    """-> Q (n,3), margin (n,), excess (n,) of the structure vertices that violate their margin and lie within the class cap"""
    Q, M, X = [], [], []
    for i, (idx, mg, cp) in dem.items():
        v = page.v(i)[idx]
        s = fine.value(v)
        need = s + mg
        k = (need > tol) & (s <= cp)
        if k.any():
            Q.append(v[k]); M.append(np.full(k.sum(), mg)); X.append(s[k])
    if not Q:
        return np.zeros((0, 3)), np.zeros(0), np.zeros(0)
    return np.vstack(Q), np.concatenate(M), np.concatenate(X)


def local_scale(page, V, ids):
    RP, RR = [], []
    for i in ids:
        v, f = V[i], page.f(i)
        e = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
        el = np.linalg.norm(v[e[:, 0]] - v[e[:, 1]], axis=1)
        ssum = np.zeros(len(v)); cnt = np.zeros(len(v))
        np.add.at(ssum, e[:, 0], el); np.add.at(cnt, e[:, 0], 1)
        RP.append(v); RR.append(ssum / np.maximum(cnt, 1))
    RP, RR = np.vstack(RP), np.concatenate(RR)
    return cKDTree(RP), RR


class Ctx:
    def __init__(self, fine, gr, Q, Mg, Xs, qtree, rtree, RR, own):
        self.fine, self.gr, self.Q, self.Mg, self.Xs, self.qtree, self.rtree, self.RR, self.own = fine, gr, Q, Mg, Xs, qtree, rtree, RR, own


def displace(x, cx, dbg=None):
    """movement of skin points x (n,3) for the current envelope / obstacles: -> (selector of the points near the envelope boundary, u (k,3)).  A function of POSITION only."""
    fine, gr, Q, Mg, Xs, qtree, rtree, RR, own = cx.fine, cx.gr, cx.Q, cx.Mg, cx.Xs, cx.qtree, cx.rtree, cx.RR, cx.own
    sd = fine.value(x)
    near = (sd > -6.0) & (sd < 6.0)
    if not near.any():
        return near, np.zeros((0, 3))
    x, sd = x[near], sd[near]
    c = ((x - fine.lo) / fine.h).T
    n = np.stack([ndi.map_coordinates(g_, c, order=1, mode="nearest") for g_ in gr], 1)
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-6)
    o = x - sd[:, None] * n
    # the direction of a stack of sheets is the normal at the OUTER point o (not at each vertex): the two sheets of a slab / an overlay and its sheet move by the same vector, so their offset
    # (thickness 3 mm; 0.3 mm for a collapsed slab) is not turned by r * (angle between the two vertex normals)
    c2 = ((o - fine.lo) / fine.h).T
    n = np.stack([ndi.map_coordinates(g_, c2, order=1, mode="nearest") for g_ in gr], 1)
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-6)
    nbr = rtree.query_ball_point(o, 8.0)
    rho = np.clip(np.array([RR[l].mean() if l else RHO_MIN for l in nbr]), RHO_MIN, RHO_MAX)
    cand = qtree.query_ball_point(o, np.sqrt((1.6 * rho) ** 2 + H_MAX ** 2))
    r = np.zeros(len(x))
    for k, lst in enumerate(cand):
        if not lst:
            continue
        d = Q[lst] - o[k]
        h = d @ n[k]
        lat = np.linalg.norm(d - h[:, None] * n[k], axis=1)
        # smooth in position (a vertex shared by two patches / lying 1-2 mm from its partner must get the same movement): lateral taper 1 -> 0 between rho and 1.6 rho,
        # and the consistency filter (the obstacle's height above o is the height it has above the envelope) as a soft weight
        wl = np.where(lat <= rho[k], 1.0, np.where(lat >= 1.6 * rho[k], 0.0, 0.5 * (1 + np.cos(np.pi * (lat - rho[k]) / (0.6 * rho[k])))))
        wc = np.clip(1.0 - (h - (Xs[lst] + 0.7 * lat + 2.0)) / 2.0, 0.0, 1.0)
        wt = wl * wc * ((h > -3.0) & (h < H_MAX))
        if (wt > 0).any():
            r[k] = max(0.0, float((wt * (h + Mg[lst])).max()))
    r0 = r.copy()
    # a skin never moves into another part of the skin (the neighbouring finger, the thigh the hand lies on): march along the normal through the free space of the current envelope
    if (r > 0.3).any():
        kk = np.flatnonzero(r > 0.3)
        tt = np.arange(0.5, H_MAX + 1.0, 0.5)
        P3 = o[kk][:, None, :] + tt[None, :, None] * n[kk][:, None, :]
        cc = ((P3.reshape(-1, 3) - fine.lo) / fine.h).T
        ins = ndi.map_coordinates(fine.inside_true.astype(np.uint8), cc, order=0, mode="nearest").reshape(len(kk), len(tt)) > 0
        # free space: leave the envelope first (an overlapping slab of the neighbouring patch right above o does not count), then the next entry into the envelope is another part of the skin
        out_ix = np.where((~ins).any(1), (~ins).argmax(1), len(tt))
        after = ins & (np.arange(len(tt))[None, :] > out_ix[:, None])
        first = np.where(after.any(1), after.argmax(1), len(tt))
        tfree = np.where(first < len(tt), tt[np.minimum(first, len(tt) - 1)] - 1.0, 1e9)         # stay 0.5 mm clear of the other skin (+ the 0.5 mm voxel offset)
        tfree = np.maximum(tfree, 0.0)
        r[kk] = np.minimum(r[kk], tfree)
    u = n * (RELAX * r)[:, None]
    s0 = own.sd(x)
    s1 = own.sd(x + u)
    room = np.maximum(s0, -0.5)
    sc = np.where(s1 > room, np.clip((room - s0) / np.maximum(s1 - s0, 1e-6), 0, 1), 1.0)
    if dbg is not None:
        dbg.update({"sd": sd, "n": n, "o": o, "rho": rho, "r_obstacles": r0, "r_after_free_space": r.copy(), "own_scale": sc, "own_s0": s0})
    return near, u * sc[:, None]


def wrap(page, V, side, wrist, coarse, own, zone=None, iters=5, tol_mm=0.5, log=print, snap=None):
    zone = zone or page.zone_structs(side, wrist)
    dem = demands(page, zone, wrist)
    pts = np.vstack([page.v(i)[m] for i, m in zone.items()])
    lo, hi = pts.min(0) - 22, pts.max(0) + 22
    V = {i: v.copy() for i, v in V.items()}
    V0 = {i: v.copy() for i, v in V.items()}
    movable = sorted(i for i in V if i.endswith("_" + side) and C.LIMB_SKIN_RE.search(i))
    FOLLOW = {f"zan_skin_nail_plate_{side}": f"zan_skin_dorsal_surfaces_of_digits_of_hand_{side}", f"zan_skin_perionyx_{side}": f"zan_skin_dorsal_surfaces_of_digits_of_hand_{side}"}
    hist = []
    for it in range(iters):
        t0 = time.time()
        fine = C.Fine(page, V, coarse, lo, hi, h=1.0)
        if it == 0:
            inside0 = float(fine.inside_true.mean())
        elif float(fine.inside_true.mean()) < inside0 - 0.01:
            log(f"   LEAK: inside fraction {inside0:.4f} -> {float(fine.inside_true.mean()):.4f}; keeping the previous state")
            V = prev
            hist.append({"it": it, "leak": True})
            break
        prev = {k: x.copy() for k, x in V.items()}
        Q, Mg, Xs = obstacles(page, fine, dem)
        nviol = int(((Xs + Mg) > tol_mm).sum())
        log(f"   it{it}: obstacle vertices {len(Q)}, violating (> {tol_mm} mm) {nviol}, worst {(Xs + Mg).max() if len(Xs) else 0:.1f} mm  [{time.time()-t0:.0f}s]")
        hist.append({"it": it, "violating_vertices": nviol, "worst_mm": float((Xs + Mg).max()) if len(Xs) else 0.0})
        if nviol == 0:
            break
        qtree = cKDTree(Q)
        sm = ndi.gaussian_filter(fine.sd, 1.5)
        gr = [ndi.sobel(sm, axis=a, mode="nearest") / (8.0 * fine.h) for a in range(3)]
        rtree, RR = local_scale(page, V, movable)
        cx = Ctx(fine, gr, Q, Mg, Xs, qtree, rtree, RR, own)
        # every vertex (both sheets of a slab, overlays such as the nail plates, rim vertices) moves by the movement needed at the point of the OUTER boundary on its own normal line:
        # o(x) = x - sd(x) n(x); u(x) = r(o(x)) n(x)   -> a stack of sheets (slab, overlay on a slab) moves as one, vertices at the same position get the same movement
        tot_moved = 0
        mmax = []
        Ufull = {}
        pending = {}
        for i in movable:
            if i in FOLLOW:
                continue
            v = V[i]
            m = ((v > lo + 2) & (v < hi - 2)).all(1)
            if not m.any():
                continue
            idx = np.flatnonzero(m)
            x = v[idx]
            near, u = displace(v[idx], cx)
            if not near.any():
                continue
            idx, x = idx[near], v[idx][near]
            mv = np.linalg.norm(u, axis=1)
            Uf = np.zeros_like(v)
            Uf[idx] = u
            Ufull[i] = (v.copy(), Uf)
            pending[i] = (idx, x, u)
        # position-based smoothing of the displacement over ALL skin vertices around (both sheets, all patches): neighbouring layers of the (crumpled) skin move by the same vector, so they do not
        # cut through each other; vertices that share a position get the same movement
        if pending and SMOOTH_SIGMA_MM > 0:
            AP = np.vstack([p_[1] for p_ in pending.values()])
            AU = np.vstack([p_[2] for p_ in pending.values()])
            if (np.linalg.norm(AU, axis=1) > 1e-3).any():
                st = cKDTree(AP)
                for i, (idx, x, u) in pending.items():
                    nb = st.query_ball_point(x, 3 * SMOOTH_SIGMA_MM)
                    us = np.zeros_like(u)
                    for k, lst in enumerate(nb):
                        d = np.linalg.norm(AP[lst] - x[k], axis=1)
                        w = np.exp(-(d ** 2) / (2 * SMOOTH_SIGMA_MM ** 2))
                        us[k] = (w[:, None] * AU[lst]).sum(0) / w.sum()
                    pending[i] = (idx, x, us)
        for i, (idx, x, u) in pending.items():
            v = V[i]
            mv = np.linalg.norm(u, axis=1)
            if (mv > 1e-3).any():
                w_ = v.copy()
                w_[idx] = x + u
                V[i] = w_
                tot_moved += int((mv > 0.3).sum()); mmax.append(mv.max())
            Ufull[i] = (v.copy(), np.where(np.isin(np.arange(len(v)), idx)[:, None], np.zeros_like(v), 0.0))
            Uf = np.zeros_like(v); Uf[idx] = u; Ufull[i] = (v.copy(), Uf)
        # overlay patches (nail plate, perionyx) lie ON the dorsal digit sheet: they take exactly the movement of the nearest dorsal-sheet vertices (the offset between the sheets is kept)
        for i, lead in FOLLOW.items():
            if i in V and lead in Ufull:
                p0, uf = Ufull[lead]
                tr = cKDTree(p0)
                d, k = tr.query(V[i], k=3)
                w = 1.0 / np.maximum(d, 0.3) ** 2
                uu = (uf[k] * w[..., None]).sum(1) / w.sum(1, keepdims=True)
                far = d[:, 0] > 6.0
                uu[far] = 0.0
                V[i] = V[i] + uu
        log(f"      vertices moved > 0.3 mm: {tot_moved}; max {max(mmax) if mmax else 0:.1f} mm")
        if not tot_moved:
            break
        if snap is not None:
            snap.append({k: x.copy() for k, x in V.items()})
    return V, hist
