"""Q207 skin inflation: move the displayed skin patches OUTWARD, locally, so that every structure of the hand / wrist / distal forearm lies inside the skin again.

Bone-anchored displacement field: every structure vertex that lies outside (or less than the margin inside) the FINE skin envelope is a demand (amount = how far the skin must move outward there, capped per
structure class).  The skin displacement is u(x) = A(x) N(x): A = the greyscale dilation of the demands by a radial plateau + cosine taper kernel (exact via one distance transform per amount level),
N = outward normal field of the envelope (gradient of the smoothed signed distance).  u is a function of POSITION, so (1) both sheets of a slab and the vertices two patches share move together
(slab thickness and welds are kept), (2) it is zero outside the kernel support (patches out of reach stay byte for byte), (3) the movement is the demand and no more.  Iterated (the envelope is rebuilt
from the moved skin) until the demands are met; the person's own CT / cryosection skin limits the outward movement.
"""
from __future__ import annotations

import re
import sys
import time
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q207_core as C  # noqa: E402

# class policy: margin (mm the structure must lie inside the envelope) and cap (largest single demand the skin follows, mm)
POLICY = {"bone": (0.5, 14.0), "vessel": (0.3, 12.0), "nerve": (0.3, 12.0), "joint": (0.3, 12.0), "bursa": (0.3, 12.0), "cartilage": (0.3, 12.0), "lymph": (0.3, 12.0),
          "fascia": (0.0, 5.0), "muscle": (0.0, 5.0), "viscera": (0.0, 0.0), "cns": (0.0, 0.0), "insertion": (0.0, 0.0)}
R0_MM = 3.5            # plateau radius around a demand point
TAPER_MIN, TAPER_MAX, TAPER_PER_MM = 8.0, 28.0, 2.0
MAX_TOTAL_MM = 16.0


MUSCLE_ZONE_MM = 45.0     # muscles / fascia only count where they are tendons: within this distance of the wrist joint centre or of a hand bone (the bellies are out of scope)


def demands(page, zone, wrist=None):
    """-> dict(id -> (vertex indices, margin, cap)) of the structures of the zone"""
    out = {}
    hand = None
    for i, m in zone.items():
        mg, cp = POLICY.get(page.sys(i), (0.5, 0.0))
        if cp <= 0:
            continue
        m = m.copy()
        if page.sys(i) in ("muscle", "fascia") and wrist is not None:
            if hand is None:
                from scipy.spatial import cKDTree
                side = "r" if "_r" in i[-3:] or i.endswith("_r") else "l"
                hand = None
            m &= np.linalg.norm(page.v(i) - wrist, axis=1) < MUSCLE_ZONE_MM
        if not m.any():
            continue
        out[i] = (np.where(m)[0], mg, cp)
    return out


def level_field(fine, Q, need, quant=None):
    """A(x) on the fine grid: max over demand points of need * kernel(|x - q|); exact per amount level by a distance transform"""
    shape, h, lo = fine.shape, fine.h, fine.lo
    A = np.zeros(shape, np.float32)
    ok = need > 0.05
    Q, need = Q[ok], need[ok]
    if not len(Q):
        return A
    lev = np.where(need <= 3.0, np.ceil(need / 0.25) * 0.25, 3.0 + np.ceil((need - 3.0) / 0.5) * 0.5)
    ix = np.floor((Q - lo) / h + 0.5).astype(int)
    inb = ((ix >= 0) & (ix < np.array(shape))).all(1)
    ix, lev = ix[inb], lev[inb]
    for L in np.unique(lev):
        sel = ix[lev >= L - 1e-6]
        R = float(np.clip(TAPER_PER_MM * L, TAPER_MIN, TAPER_MAX))
        pad = int(np.ceil((R0_MM + R) / h)) + 2
        a0 = np.maximum(sel.min(0) - pad, 0)
        a1 = np.minimum(sel.max(0) + pad + 1, np.array(shape))
        sub = np.ones(tuple(a1 - a0), bool)
        ss = sel - a0
        sub[ss[:, 0], ss[:, 1], ss[:, 2]] = False
        d = ndi.distance_transform_edt(sub, sampling=h).astype(np.float32)
        t = np.clip((d - R0_MM) / R, 0, 1)
        k = 0.5 * (1 + np.cos(np.pi * t))
        k[t >= 1] = 0
        sl = tuple(slice(a, b) for a, b in zip(a0, a1))
        A[sl] = np.maximum(A[sl], L * k)
    return A


def sample(grid, lo, h, P, order=1):
    c = ((np.asarray(P, float) - lo) / h).T
    return ndi.map_coordinates(grid, c, order=order, mode="nearest")


def bone_direction(fine, page, side, sigma_mm=12.0):
    """outward direction from the local bone mass: x - (gaussian-weighted centre of the arm / hand bone voxels around x); 'bone-anchored'"""
    from scripts.zanatomy.q198_core import Grid
    g = Grid(fine.lo, fine.lo + (np.array(fine.shape) - 1) * fine.h, fine.h)
    occ = np.zeros(fine.shape, bool)
    for i in page.ids:
        if page.sys(i) == "bone" and i.endswith("_" + side) and (C.HAND_RE.search(i) or re.search(r"radius|ulna|humerus", i)):
            v = page.v(i)
            if ((v > fine.lo - 40) & (v < fine.lo + np.array(fine.shape) * fine.h + 40)).all(1).any():
                occ |= g.raster(v, page.f(i), spacing=fine.h * 0.5)
    sg = sigma_mm / fine.h
    S0 = ndi.gaussian_filter(occ.astype(np.float32), sg)
    ix = np.stack(np.meshgrid(*[np.arange(n) for n in fine.shape], indexing="ij"), 0).astype(np.float32)
    cen = [ndi.gaussian_filter(occ * ix[a], sg) / np.maximum(S0, 1e-6) for a in range(3)]
    d = [ix[a] - cen[a] for a in range(3)]
    n = np.sqrt(d[0] ** 2 + d[1] ** 2 + d[2] ** 2) + 1e-6
    return [x / n for x in d], S0


def normal_field(fine, O=None, sigma_mm=3.0, bonedir=None):
    """outward direction field: the smoothed normals of the OUTER sheet samples (faces of the limb patches whose normal points away from the nearest bone); where no sample is near, the gradient of the envelope"""
    sm = ndi.gaussian_filter(fine.sd, 2.5 / fine.h)
    g = [ndi.sobel(sm, axis=a, mode="nearest") / (8.0 * fine.h) for a in range(3)]
    n = np.sqrt(g[0] ** 2 + g[1] ** 2 + g[2] ** 2) + 1e-6
    g = [x / n for x in g]
    if O is None:
        return g
    ix = np.floor((O.P - fine.lo) / fine.h + 0.5).astype(int)
    ok = ((ix >= 0) & (ix < np.array(fine.shape))).all(1)
    ix, Nn = ix[ok], O.N[ok]
    acc = [np.zeros(fine.shape, np.float32) for _ in range(3)]
    for a in range(3):
        np.add.at(acc[a], (ix[:, 0], ix[:, 1], ix[:, 2]), Nn[:, a])
    acc = [ndi.gaussian_filter(x, sigma_mm / fine.h) for x in acc]
    m = np.sqrt(acc[0] ** 2 + acc[1] ** 2 + acc[2] ** 2)
    w = np.clip(m / 0.02, 0, 1)
    out = []
    for a in range(3):
        out.append((w * acc[a] / np.maximum(m, 1e-9) + (1 - w) * g[a]).astype(np.float32))
    if bonedir is not None:
        bd, S0 = bonedir
        wb = np.clip(S0 / 0.02, 0, 1) * 0.7
        out = [(1 - wb) * out[a] + wb * bd[a] for a in range(3)]
    nn = np.sqrt(out[0] ** 2 + out[1] ** 2 + out[2] ** 2) + 1e-9
    return [x / nn for x in out]


class OwnSkin:
    def __init__(self, which):
        import trimesh
        from scripts.zanatomy import q198_load as L
        S = [s for s in L.load(C.PAGES[which]["own"]) if s["id"] == "skin"][0]
        self.tm = trimesh.Trimesh(S["v"], S["f"], process=False)

    def sd(self, P):
        import trimesh
        return -trimesh.proximity.signed_distance(self.tm, np.asarray(P, float))        # + outside


def measure(page, fine, dem):
    """per-class measure of the demand structures against the fine envelope: share > 0.5 mm / > 3 mm outside, max"""
    rows = {}
    for i, (idx, mg, cp) in dem.items():
        s = fine.value(page.v(i)[idx])
        rows[i] = (float((s > 0.5).mean() * 100), float((s > 3).mean() * 100), float(s.max()))
    return rows


def inflate(page, V, side, wrist, coarse, own, zone=None, iters=10, tol_mm=0.5, log=print, only_ids=None, gain=1.2, snap=None):
    """V: {skin id: (n,3)} current skin (modified copy returned).  Returns (V2, report)"""
    zone = zone or page.zone_structs(side, wrist)
    dem = demands(page, zone, wrist)
    pts = np.vstack([page.v(i)[m] for i, m in zone.items()])
    lo, hi = pts.min(0) - 22, pts.max(0) + 22
    V = {i: v.copy() for i, v in V.items()}
    V0 = {i: v.copy() for i, v in V.items()}
    bone_pts = np.vstack([page.v(i) for i in page.ids if page.sys(i) == "bone"])
    movable = {i for i in V if i.endswith("_" + side) and C.LIMB_SKIN_RE.search(i)}
    s_init = {}
    hist = []
    N = None
    for it in range(iters):
        t0 = time.time()
        fine = C.Fine(page, V, coarse, lo, hi, h=1.0)
        Q, need = [], []
        per = {}
        for i, (idx, mg, cp) in dem.items():
            p = page.v(i)[idx]
            s = fine.value(p)
            if i not in s_init:
                s_init[i] = s.copy()
            remaining = cp - np.maximum(s_init[i] - s, 0.0)           # a capped class may follow the skin only up to `cap` in total
            nd = np.minimum(s + mg, np.maximum(remaining, 0.0))
            m = nd > 0.05
            per[i] = (int((nd > tol_mm).sum()), float(nd.max()) if len(nd) else 0.0)
            Q.append(p[m]); need.append(nd[m])
        Q, need = (np.vstack(Q), np.concatenate(need)) if Q else (np.zeros((0, 3)), np.zeros(0))
        viol = int((need > tol_mm).sum())
        log(f"   it{it}: demand vertices > {tol_mm} mm: {viol}, max demand {need.max() if len(need) else 0:.2f} mm [{time.time()-t0:.0f}s]")
        top = sorted(per.items(), key=lambda kv: -kv[1][0])[:5]
        log("      top: " + "; ".join(f"{k[:28]} {v[0]} ({v[1]:.1f})" for k, v in top))
        hist.append({"it": it, "demand_vertices": viol, "max_demand_mm": float(need.max()) if len(need) else 0.0})
        if viol == 0:
            break
        if N is None:
            # outward direction = gradient of the signed distance of the envelope of the LIMB patches alone (a hand lying on the thigh keeps its own outside), fixed at the start
            fineN = C.Fine(page, V0, coarse, lo, hi, h=1.0, patches=sorted(movable), deep_mm=1e9)
            N = normal_field(fineN)
            del fineN
        A = level_field(fine, Q, np.minimum(need * gain, MAX_TOTAL_MM))
        for i, v in V.items():
            if i not in movable:
                continue
            m = ((v > lo) & (v < hi)).all(1)
            if not m.any():
                continue
            a = sample(A, fine.lo, fine.h, v[m])
            if a.max() < 0.02:
                continue
            n = np.stack([sample(g, fine.lo, fine.h, v[m]) for g in N], 1)
            n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-6)
            u = a[:, None] * n
            # own skin headroom: the outer sheet may not leave the person's own skin (unless it already is outside there)
            s0 = own.sd(v[m])
            s1 = own.sd(v[m] + u)
            room = np.maximum(s0, -0.5)
            over = s1 - room
            sc = np.where(over > 0, np.clip((room - s0) / np.maximum(s1 - s0, 1e-6), 0, 1), 1.0)
            u = u * sc[:, None]
            w = v.copy()
            w[m] = v[m] + u
            tot = np.linalg.norm(w - V0[i], axis=1)
            k = tot > MAX_TOTAL_MM
            if k.any():
                w[k] = V0[i][k] + (w[k] - V0[i][k]) * (MAX_TOTAL_MM / tot[k])[:, None]
            V[i] = w
        if snap is not None:
            snap.append({k: x.copy() for k, x in V.items()})
    return V, hist
