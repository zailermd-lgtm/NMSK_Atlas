"""Q207 skin shrink-wrap (replaces the normal-based inflation, which spiked on the collapsed wrist skin): the minimal outward movement of the skin so that no structure of the hand / wrist / distal
forearm lies outside it.

  new envelope = old envelope  UNION  (the structures that poke out, dilated by the class margin)      -> its boundary is the target surface (bone-anchored: it follows the structures)
  every skin vertex of the outer sheet moves to the nearest point of the new boundary (x + depth * outward gradient of the signed distance of the new envelope: the minimal displacement);
  inner sheet / rim vertices take the Gaussian-weighted displacement of the outer-sheet vertices around them (position-based: both sheets of a slab move together = thickness kept, vertices
  shared by two patches get the same displacement = the welds stay).  Patches / vertices out of reach move by exactly 0.  Iterated until the check passes; the person's own CT / cryosection skin
  limits the outward movement (a vertex never leaves it)."""
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
from scripts.zanatomy.q198_core import Grid  # noqa: E402
from scripts.zanatomy.q207_inflate import POLICY, demands, OwnSkin  # noqa: E402,F401

OUTER_SD_MM = -1.2        # skin vertices with envelope depth above this are the outer sheet (the inner sheet lies one slab thickness, 3 mm, below)
KERNEL_SIGMA_MM = 3.0
NOISE_MM = 0.5            # extra margin over the class margin (grid resolution 1 mm)


def obstacle_mask(page, fine, dem, log=None):
    """voxels of the structures that violate (or are within the margin of) the envelope, dilated by margin + noise; points further out than the class cap are not followed"""
    g = Grid(fine.lo, fine.lo + (np.array(fine.shape) - 1) * fine.h, fine.h)
    ob = np.zeros(fine.shape, bool)
    by_margin = {}
    nviol = 0
    for i, (idx, mg, cp) in dem.items():
        v, f = page.v(i), page.f(i)
        s = fine.value(v[idx])
        need = s + mg
        keep = (need > 0.0) & (s <= cp)
        if not keep.any():
            continue
        nviol += int((need > 0.5).sum())
        sel = np.zeros(len(v), bool)
        sel[idx[keep]] = True
        fm = sel[f].any(1)
        if not fm.any():
            continue
        m = g.raster(v, f[fm], spacing=0.5)
        by_margin.setdefault(mg, np.zeros(fine.shape, bool))
        by_margin[mg] |= m
    for mg, m in by_margin.items():
        if not m.any():
            continue
        d = ndi.distance_transform_edt(~m, sampling=fine.h)
        ob |= d <= (mg + NOISE_MM)
    return ob, nviol


def wrap(page, V, side, wrist, coarse, own, zone=None, iters=4, log=print, snap=None):
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
        ob, nviol = obstacle_mask(page, fine, dem)
        if it == 0:
            inside0 = float(fine.inside_true.mean())
        elif float(fine.inside_true.mean()) < inside0 - 0.01:
            log(f"   LEAK: inside fraction {inside0:.4f} -> {float(fine.inside_true.mean()):.4f}; stopping and keeping the previous state")
            V = prev
            hist.append({"it": it, "leak": True})
            break
        prev = {k: x.copy() for k, x in V.items()}
        log(f"   it{it}: violating structure vertices (> 0.5 mm) {nviol}  [{time.time()-t0:.0f}s]")
        hist.append({"it": it, "violating_vertices": nviol})
        if nviol == 0:
            break
        new_in = ndi.binary_fill_holes(np.pad(fine.inside_true | ob, 1))[1:-1, 1:-1, 1:-1]
        d_in = ndi.distance_transform_edt(new_in, sampling=fine.h).astype(np.float32)
        d_out = ndi.distance_transform_edt(~new_in, sampling=fine.h).astype(np.float32)
        sdn = np.where(new_in, -(d_in - 0.5 * fine.h), d_out - 0.5 * fine.h)
        sm = ndi.gaussian_filter(sdn, 1.0)
        gr = [ndi.sobel(sm, axis=a, mode="nearest") / (8.0 * fine.h) for a in range(3)]
        # how far the new boundary lies beyond the OLD one at every voxel of the old boundary shell (same discretisation bias in both)
        shell = fine.inside_true & ~ndi.binary_erosion(fine.inside_true, iterations=2)
        mvf = np.where(shell, np.maximum(fine.sd - sdn, 0.0), 0.0).astype(np.float32)
        sh = np.argwhere(mvf > 0.25)
        shp = fine.lo + sh * fine.h
        shv = mvf[sh[:, 0], sh[:, 1], sh[:, 2]]
        shtree = cKDTree(shp) if len(sh) else None
        src_p, src_u = [], []
        for i in movable:
            v = V[i]
            m = ((v > lo + 2) & (v < hi - 2)).all(1)
            if not m.any() or shtree is None:
                continue
            sd_old = fine.value(v[m])
            outer = sd_old > OUTER_SD_MM
            if not outer.any():
                continue
            x = v[m][outer]
            # a vertex must clear what the faces around it span: dilate the movement of the boundary by the local mesh scale (mean incident edge length)
            f = page.f(i)
            e = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
            el = np.linalg.norm(v[e[:, 0]] - v[e[:, 1]], axis=1)
            ssum = np.zeros(len(v)); cnt = np.zeros(len(v))
            np.add.at(ssum, e[:, 0], el); np.add.at(cnt, e[:, 0], 1)
            rho = np.clip(ssum / np.maximum(cnt, 1), 3.0, 12.0)[m][outer]
            nb = shtree.query_ball_point(x, rho)
            mv = np.array([shv[l].max() if l else 0.0 for l in nb])
            c = ((x - fine.lo) / fine.h).T
            n = np.stack([ndi.map_coordinates(g_, c, order=1, mode="nearest") for g_ in gr], 1)
            n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-6)
            if it == 0:
                g0 = np.stack([ndi.map_coordinates(ndi.sobel(ndi.gaussian_filter(fine.sd, 1.5), axis=a, mode='nearest') / (8.0 * fine.h), c, order=1, mode='nearest') for a in range(3)], 1)
                g0 /= np.maximum(np.linalg.norm(g0, axis=1, keepdims=True), 1e-6)
                cosv = (n * g0).sum(1)
                sel = mv > 0.5
                log(f"      {i[9:40]}: outer {len(x)} moving {int(sel.sum())} cos(n, old outward) min {cosv[sel].min() if sel.any() else 1:.2f} frac<0.3: {(cosv[sel] < 0.3).mean() if sel.any() else 0:.2f}")
            src_p.append(x); src_u.append(n * mv[:, None])
        if not src_p:
            break
        SP, SU = np.vstack(src_p), np.vstack(src_u)
        mm = np.linalg.norm(SU, axis=1)
        log(f"      movement of outer vertices: n={len(mm)} >0.3mm: {(mm>0.3).sum()} p50/p90/max of those {np.percentile(mm[mm>0.3],50) if (mm>0.3).any() else 0:.1f}/{np.percentile(mm[mm>0.3],90) if (mm>0.3).any() else 0:.1f}/{mm.max():.1f}; shell voxels with mv>0.25: {len(sh)}, max mv {shv.max() if len(sh) else 0:.1f} at {shp[np.argmax(shv)].round(0) if len(sh) else None}")
        active = np.linalg.norm(SU, axis=1) > 0.02
        if not active.any():
            log("   nothing to move")
            break
        tree = cKDTree(SP)
        for i in movable:
            v = V[i]
            m = ((v > lo) & (v < hi)).all(1)
            if not m.any():
                continue
            dd, kk = tree.query(v[m])
            own_vertex = dd < 1e-6                       # an outer-sheet vertex keeps exactly its own projection
            nb = tree.query_ball_point(v[m], 3 * KERNEL_SIGMA_MM)
            u = np.zeros((m.sum(), 3))
            for k, lst in enumerate(nb):
                if own_vertex[k]:
                    u[k] = SU[kk[k]]
                    continue
                if not lst:
                    continue
                d = np.linalg.norm(SP[lst] - v[m][k], axis=1)
                w = np.exp(-(d ** 2) / (2 * KERNEL_SIGMA_MM ** 2))
                u[k] = (w[:, None] * SU[lst]).sum(0) / w.sum()
            if np.abs(u).max() < 1e-3:
                continue
            # own skin headroom
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
