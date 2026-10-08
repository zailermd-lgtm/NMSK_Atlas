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


def wrap(page, V, side, wrist, coarse, own, zone=None, iters=5, tol_mm=0.5, log=print, snap=None):
    zone = zone or page.zone_structs(side, wrist)
    dem = demands(page, zone, wrist)
    pts = np.vstack([page.v(i)[m] for i, m in zone.items()])
    lo, hi = pts.min(0) - 22, pts.max(0) + 22
    V = {i: v.copy() for i, v in V.items()}
    V0 = {i: v.copy() for i, v in V.items()}
    movable = sorted(i for i in V if i.endswith("_" + side) and C.LIMB_SKIN_RE.search(i))
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
        src_p, src_u = [], []
        for i in movable:
            v = V[i]
            m = ((v > lo + 2) & (v < hi - 2)).all(1)
            if not m.any():
                continue
            sd_old = fine.value(v[m])
            outer = sd_old > OUTER_SD_MM
            if not outer.any():
                continue
            x = v[m][outer]
            c = ((x - fine.lo) / fine.h).T
            n = np.stack([ndi.map_coordinates(g_, c, order=1, mode="nearest") for g_ in gr], 1)
            n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-6)
            nbr = rtree.query_ball_point(x, 8.0)
            rho = np.clip(np.array([RR[l].mean() for l in nbr]), RHO_MIN, RHO_MAX)
            cand = qtree.query_ball_point(x, np.sqrt(rho ** 2 + H_MAX ** 2))
            r = np.zeros(len(x))
            for k, lst in enumerate(cand):
                if not lst:
                    continue
                d = Q[lst] - x[k]
                h = d @ n[k]
                lat = np.linalg.norm(d - h[:, None] * n[k], axis=1)
                ok = (lat <= rho[k]) & (h > -3.0) & (h < H_MAX) & (h <= Xs[lst] + 0.7 * lat + 2.0)     # an obstacle counts only when its height above x is the height it has above the envelope
                if ok.any():
                    r[k] = max(0.0, float((h[ok] + Mg[lst][ok]).max()))
            uu = n * (RELAX * r)[:, None]
            mvd = r > 0.3
            if mvd.any():
                dsd = fine.value(x[mvd] + uu[mvd]) - fine.value(x[mvd])
                log(f"      {i[9:36]:27s} raised {int(mvd.sum()):4d}  median move {np.median(r[mvd]):.1f}  envelope sd change at the new position: median {np.median(dsd):.1f}, share < 0: {(dsd < -0.3).mean():.2f}")
            src_p.append(x); src_u.append(uu)
        SP, SU = np.vstack(src_p), np.vstack(src_u)
        mm = np.linalg.norm(SU, axis=1)
        log(f"      outer vertices {len(mm)}; raised > 0.3 mm: {int((mm > 0.3).sum())}; p50/p90/max of those {np.percentile(mm[mm > 0.3], 50) if (mm > 0.3).any() else 0:.1f}/{np.percentile(mm[mm > 0.3], 90) if (mm > 0.3).any() else 0:.1f}/{mm.max():.1f} mm")
        if not (mm > 0.02).any():
            break
        tree = cKDTree(SP)
        for i in movable:
            v = V[i]
            m = ((v > lo) & (v < hi)).all(1)
            if not m.any():
                continue
            dd, kk = tree.query(v[m])
            own_vertex = dd < 1e-6
            nb = tree.query_ball_point(v[m], 3 * KERNEL_SIGMA_MM)
            u = np.zeros((m.sum(), 3))
            for k, lst in enumerate(nb):
                if own_vertex[k]:
                    u[k] = SU[kk[k]]
                elif lst:
                    d = np.linalg.norm(SP[lst] - v[m][k], axis=1)
                    w = np.exp(-(d ** 2) / (2 * KERNEL_SIGMA_MM ** 2))
                    u[k] = (w[:, None] * SU[lst]).sum(0) / w.sum()
            if np.abs(u).max() < 1e-3:
                continue
            s0 = own.sd(v[m])
            s1 = own.sd(v[m] + u)
            room = np.maximum(s0, -0.5)
            sc = np.where(s1 > room, np.clip((room - s0) / np.maximum(s1 - s0, 1e-6), 0, 1), 1.0)
            w_ = v.copy()
            w_[m] = v[m] + u * sc[:, None]
            V[i] = w_
        if snap is not None:
            snap.append({k: x.copy() for k, x in V.items()})
    return V, hist
