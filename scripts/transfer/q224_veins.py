#!/usr/bin/env python3
"""Q224 (1): the BROKEN VEINS of the two OWN pages (Q223 top defect 1): femoral v. r 62 mm / l 35 mm gaps and internal jugular v. 44-52 mm (his) / 36-43 mm (hers).

A vein of the own bundles is a set of closed pieces (the label / tracked outline stopped where the evidence stopped).  Method, per vein:
  1. pieces = connected surface pieces; pieces below SPECK_NV vertices are label specks (4-17 vertices, a few mm3) and are not evidence of a lumen.
  2. each piece's centreline (3 mm geodesic levels) gives the two STUMPS: outward tangent and the cross-section ellipse (semi-axes a >= b, orientation) at STUMP_DEPTH mm inside the end -- the person's own
     evidence at both ends (his tracked cryosection outline, her CT label, his transferred label for the IJV).
  3. pieces are chained greedily (nearest free ends, outward tangents must point at each other); each link is a BRIDGE = a cubic Hermite centreline from stump A to stump B (end tangents = the stumps' own
     tangents, so the vessel leaves each stump in the direction it was going), bone-repelled where it would touch a bone, with an elliptical section that morphs from A's ellipse to B's (smoothstep: the
     calibre is the stump's at both ends, no step) and a section orientation that twists from A's to B's.  Embedded EMBED_MM into each stump.
  4. the pieces' exact 0.5 mm voxel solids + the bridge solids are united, smoothed (sigma 0.4 mm), marching cubes, one connected piece, quadric decimation to the old triangle budget.
  Guards (a failed one keeps the old vein and records why): one piece afterwards; volume of the result = pieces + bridge solid within 0.95-1.05; the old pieces move <= 1.0 mm (p95: voxel re-mesh + smoothing) outside the bridge zone;
  every bridge-zone vertex inside the skin >= 1 mm and in no bone; calibre at both junctions within 0.8-1.25 of the stump's, bridge calibre inside [0.9 min, 1.1 max] of the stump radii; no sharp bend
  (turning angle <= 60 deg per 3 mm); bridge no longer than MAX_BRIDGE_MM.
The bridge is RULE-BASED (a smooth curve between two measured stumps), never measured: the card says so with its length and radii."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import trimesh
from scipy import ndimage as ndi
from scipy.spatial import ConvexHull, cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.transfer import q216_common as C216  # noqa: E402

SPECK_NV = 30
STUMP_DEPTH = 3.0          # mm inside the end where the stump section is measured
EMBED_MM = 2.5
H = 0.5
MAX_BRIDGE_MM = 90.0
SECTION_STEP = 0.25


# ------------------------------------------------------------------------------------------ stumps
def polygon_ellipse(P2):
    """convex hull of 2D points -> (area, centre, a, b, major axis angle); a, b = semi-axes of the ellipse with the hull's second moments (uniform polygon: var = a^2 / 4)"""
    P2 = np.asarray(P2, float)
    if len(P2) < 4:
        return None
    try:
        h = ConvexHull(P2)
    except Exception:
        return None
    poly = P2[h.vertices]
    x, y = poly[:, 0], poly[:, 1]
    x1, y1 = np.roll(x, -1), np.roll(y, -1)
    cr = x * y1 - x1 * y
    A = 0.5 * cr.sum()
    if abs(A) < 1e-9:
        return None
    cx = ((x + x1) * cr).sum() / (6 * A)
    cy = ((y + y1) * cr).sum() / (6 * A)
    Ixx = ((y ** 2 + y * y1 + y1 ** 2) * cr).sum() / 12.0 - A * cy ** 2
    Iyy = ((x ** 2 + x * x1 + x1 ** 2) * cr).sum() / 12.0 - A * cx ** 2
    Ixy = ((x * y1 + 2 * x * y + 2 * x1 * y1 + x1 * y) * cr).sum() / 24.0 - A * cx * cy
    cov = np.array([[Iyy, -Ixy], [-Ixy, Ixx]]) / A
    cov = np.array([[cov[0, 0], cov[0, 1]], [cov[1, 0], cov[1, 1]]])
    w, V = np.linalg.eigh(cov)
    w = np.maximum(w, 1e-6)
    a, b = 2 * np.sqrt(w[1]), 2 * np.sqrt(w[0])
    return dict(area=abs(float(A)), centre=np.array([cx, cy]), a=float(a), b=float(b), major=V[:, 1])


def plane_basis(t):
    t = np.asarray(t, float) / np.linalg.norm(t)
    h = np.array([1.0, 0, 0]) if abs(t[0]) < 0.9 else np.array([0, 1.0, 0])
    u = np.cross(t, h)
    u /= np.linalg.norm(u)
    return u, np.cross(t, u)


def centreline(v, f, step=3.0):
    from scripts.zanatomy.q198_soft import graph_levels
    cen, cnt, _nc, L = graph_levels(np.asarray(v, float), np.asarray(f, np.int64), step)
    return np.asarray(cen), float(L)


def section_at(v, centre, t, half=1.0, rmax=14.0):
    """vertices in the slab |(x - centre) . t| <= half and within rmax of the axis -> (ellipse dict, 3D centre)"""
    u, w = plane_basis(t)
    d = v - centre
    along = d @ t
    lat = d - np.outer(along, t)
    sel = (np.abs(along) <= half) & (np.linalg.norm(lat, axis=1) <= rmax)
    if sel.sum() < 5:
        return None
    P2 = np.column_stack([lat[sel] @ u, lat[sel] @ w])
    e = polygon_ellipse(P2)
    if e is None:
        return None
    c3 = centre + e["centre"][0] * u + e["centre"][1] * w
    e["major3"] = e["major"][0] * u + e["major"][1] * w
    e["centre3"] = c3
    return e


def exact_section(tm, origin, t):
    """exact cross-section of the closed piece by the plane (origin, normal t): the loop with the largest area -> ellipse dict (area, a, b, major3, centre3) or None"""
    try:
        sec = tm.section(plane_origin=origin, plane_normal=t)
    except Exception:
        return None
    if sec is None:
        return None
    u, w = plane_basis(t)
    best = None
    for pl in sec.discrete:
        P = np.asarray(pl) - origin
        P2 = np.column_stack([P @ u, P @ w])
        if len(P2) < 4:
            continue
        e = polygon_ellipse(P2)
        if e is None:
            continue
        e["dist0"] = float(np.linalg.norm(e["centre"]))              # the loop that belongs to the tube here: the one centred nearest to the centreline point (a bent tube meets the plane again elsewhere)
        if best is None or e["dist0"] < best["dist0"]:
            best = e
    if best is None or best["dist0"] > 6.0:
        return None
    best["major3"] = best["major"][0] * u + best["major"][1] * w
    best["centre3"] = origin + best["centre"][0] * u + best["centre"][1] * w
    return best


def centreline_at(cen, arc, d):
    return np.array([np.interp(d, arc, cen[:, k]) for k in range(3)])


def smooth_centre(cen, sigma=1.2):
    from scipy.ndimage import gaussian_filter1d
    if len(cen) < 6:
        return cen
    pad = 4
    ext = np.vstack([cen[0] + (cen[0] - cen[1:pad + 1][::-1].mean(0)) * 0, cen])
    return gaussian_filter1d(cen, sigma, axis=0, mode="nearest")


def analyse_piece(v, f):
    """-> dict(vol, length, cen, ends=[stump 0, stump 1]).  A stump = the BODY of the tube just inside the end.  The tracked outline / label of an own vein tapers to a rounded tip and sometimes hooks sideways over its
    last mm (the tracker lost the lumen: a 'hook' of the right femoral vein, a narrowing tail of the IJV pieces), so the stump is the outermost depth from which the centreline keeps within 40 deg of the baseline direction
    (20-46 mm in) and the exact section stays >= 85 % of the body calibre (median of the sections on the baseline); the tip beyond it is replaced by the bridge.
    stump = dict(p, t (outward), a, b, major3, r_eq, cut_depth_mm, tip_r_eq, body_r_eq, profile)"""
    cen0, L = centreline(v, f, 2.0)
    cen = smooth_centre(cen0)
    out = dict(v=v, f=f, length=L, cen=cen)
    tm = trimesh.Trimesh(v, f, process=False)
    out["vol"] = abs(float(tm.volume)) if tm.is_watertight else float(tm.convex_hull.volume) * 0.6
    out["tm"] = tm
    arc0 = np.r_[0, np.cumsum(np.linalg.norm(np.diff(cen, axis=0), axis=1))]
    ends = []
    for which in (0, 1):
        c = cen if which == 0 else cen[::-1]
        arc = arc0 if which == 0 else (arc0[-1] - arc0[::-1])
        top = float(arc[-1])
        if top < 8.0:
            ends.append(None)
            continue

        def tl(d, h=2.5):
            t = centreline_at(c, arc, max(d - h, 0.0)) - centreline_at(c, arc, min(d + h, top))
            return t / max(np.linalg.norm(t), 1e-9)
        d_b0, d_b1 = min(20.0, 0.3 * top), min(46.0, 0.85 * top)
        tb = centreline_at(c, arc, d_b0) - centreline_at(c, arc, d_b1)
        tb /= max(np.linalg.norm(tb), 1e-9)
        ds = np.arange(0.5, min(d_b1 + 2.0, 0.95 * top), 0.5)
        sec = {}
        for d in ds:
            e = exact_section(tm, centreline_at(c, arc, d), tl(d, 3.0))
            if e is not None:
                sec[round(float(d), 2)] = e
        base = [np.sqrt(e["a"] * e["b"]) for d, e in sec.items() if d_b0 <= d <= d_b1]
        if len(base) < 3:
            ends.append(None)
            continue
        rb = float(np.median(base))
        good = {}
        for d, e in sec.items():
            ang = float(np.degrees(np.arccos(np.clip(tl(d) @ tb, -1, 1))))
            good[d] = (ang <= 40.0) and (np.sqrt(e["a"] * e["b"]) >= 0.85 * rb)
        keys = sorted(sec)
        cut = None
        run = 0
        for d in [k for k in reversed(keys) if k <= d_b1 + 1e-9]:           # from the deep end of the baseline outwards to the tip
            if good[d]:
                cut, run = d, 0
            elif cut is not None:
                run += 1
                if run >= 3:                                                 # three consecutive bad samples (1.5 mm) end the usable stump
                    break
        if cut is not None and cut > 0.3 * top:                              # a short piece keeps >= 40 % of its length as the body (both ends are cut)
            ok = [k for k in keys if k <= 0.3 * top]
            cut = ok[-1] if ok else None
        if cut is None or cut > 26.0:
            ends.append(None)
            continue
        win = [sec[d] for d in keys if cut <= d <= cut + 4.0]
        ref = win[0]["major3"]
        for e in win:
            if e["major3"] @ ref < 0:
                e["major3"] = -e["major3"]
        a_m, b_m = float(np.median([e["a"] for e in win])), float(np.median([e["b"] for e in win]))
        tt = centreline_at(c, arc, cut) - centreline_at(c, arc, min(cut + 10.0, top))
        tt /= max(np.linalg.norm(tt), 1e-9)
        e_cut = sec[cut]
        st = dict(p=e_cut["centre3"], t=tt, a=a_m, b=b_m, major3=win[len(win) // 2]["major3"], r_eq=float(np.sqrt(a_m * b_m)), cut_depth_mm=round(float(cut), 1), body_r_eq=round(rb, 2),
                  tip_r_eq=round(float(np.sqrt(sec[keys[0]]["a"] * sec[keys[0]]["b"])), 2), end_point=c[0], tip_to_cut_mm=round(float(np.linalg.norm(c[0] - e_cut["centre3"])), 1),
                  hook_deg=round(float(np.degrees(np.arccos(np.clip(tl(keys[0]) @ tb, -1, 1)))), 0), profile=[(round(d, 1), round(float(np.sqrt(sec[d]['a'] * sec[d]['b'])), 2)) for d in keys[:12:2]])
        ends.append(st)
    out["ends"] = ends
    return out


def split_vein(v, f):
    tm = trimesh.Trimesh(np.asarray(v, float), np.asarray(f, np.int64), process=False)
    parts = tm.split(only_watertight=False)
    big, specks = [], []
    for p in parts:
        (big if len(p.vertices) >= SPECK_NV else specks).append(p)
    pieces = [analyse_piece(np.asarray(p.vertices), np.asarray(p.faces)) for p in big]
    pieces.sort(key=lambda d: -d["vol"])
    return pieces, [dict(nv=int(len(p.vertices)), centroid=np.round(p.centroid, 1).tolist(), bbox=np.round(p.bounds, 1).tolist(), vol_mm3=round(abs(float(p.volume)), 2)) for p in specks]


# ------------------------------------------------------------------------------------------ chain
def plan_chain(pieces, max_bridge=MAX_BRIDGE_MM):
    """greedy chain from the largest piece: repeatedly join the nearest pair (free end of the group, free end of an unattached piece) whose outward tangents point at each other -> (links, unattached, notes)"""
    n = len(pieces)
    free = {(i, e): pieces[i]["ends"][e] for i in range(n) for e in (0, 1) if pieces[i]["ends"][e] is not None}
    group = {0}
    links, notes = [], []
    while len(group) < n:
        best = None
        for (i, ei), A in free.items():
            if i not in group:
                continue
            for (j, ej), Bn in free.items():
                if j in group:
                    continue
                d = Bn["p"] - A["p"]
                dist = float(np.linalg.norm(d))
                if dist < 1e-6:
                    continue
                dn = d / dist
                ca, cb = float(A["t"] @ dn), float(-Bn["t"] @ dn)
                score = dist * (1.0 + max(0.0, 0.5 - ca) + max(0.0, 0.5 - cb))
                if best is None or score < best[0]:
                    best = (score, i, ei, j, ej, dist, ca, cb)
        if best is None:
            break
        _s, i, ei, j, ej, dist, ca, cb = best
        if dist > max_bridge:
            notes.append(f"nearest free ends are {dist:.1f} mm apart (> {max_bridge:g}): not bridged")
            break
        links.append(dict(a=(i, ei), b=(j, ej), end_gap_mm=dist, cos_a=ca, cos_b=cb))
        group.add(j)
        free.pop((i, ei))
        free.pop((j, ej))
    return links, [i for i in range(n) if i not in group], notes


# ------------------------------------------------------------------------------------------ the bridge
def hermite(pA, tA, pB, tB, step=SECTION_STEP, kA=1.0, kB=1.0):
    L = float(np.linalg.norm(pB - pA))
    m0, m1 = tA * L * kA, -tB * L * kB                      # leave A along its outward tangent, arrive at B against B's outward tangent
    t = np.linspace(0, 1, 400)[:, None]
    P = (2 * t ** 3 - 3 * t ** 2 + 1) * pA + (t ** 3 - 2 * t ** 2 + t) * m0 + (-2 * t ** 3 + 3 * t ** 2) * pB + (t ** 3 - t ** 2) * m1
    return resample(P, step)


def resample(P, step):
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    s = np.r_[0, np.cumsum(seg)]
    n = max(int(round(s[-1] / step)), 2)
    q = np.linspace(0, s[-1], n + 1)
    return np.column_stack([np.interp(q, s, P[:, k]) for k in range(3)])


def tangents(P):
    T = np.gradient(P, axis=0)
    return T / np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-9)


def repel_from_bones(P, amax, bone_tree, margin=0.6, iters=40, fixed=3):
    """push centreline samples that come closer than amax + margin to a bone surface sample away from it (Laplacian-smoothed), end samples held -> (P, moved_max_mm)"""
    P0 = P.copy()
    need = amax + margin
    for _ in range(iters):
        d, i = bone_tree.query(P)
        bad = d < need
        if not bad.any():
            break
        away = P - bone_tree.data[i]
        away /= np.maximum(np.linalg.norm(away, axis=1, keepdims=True), 1e-9)
        P = P + np.where(bad[:, None], away * (need - d)[:, None] * 0.8, 0.0)
        for _s in range(3):                                          # smooth, keep the ends
            Q = P.copy()
            Q[1:-1] = 0.25 * P[:-2] + 0.5 * P[1:-1] + 0.25 * P[2:]
            P = Q
        P[:fixed], P[-fixed:] = P0[:fixed], P0[-fixed:]
    return P, float(np.linalg.norm(P - P0, axis=1).max())


def route_around_bones(P, A, Bn, need, bone_tree, ctx, h=0.75, dev_w=0.03, pad=22.0):
    """the centreline P (Hermite) comes closer than `need` mm to a bone: find a minimum-cost path on a 0.75 mm lattice from stump A to stump B that keeps `need` mm from every bone (cost = 1 + 0.03 deviation^2 from P
    + a steep penalty inside the clearance, infinite inside bone), smooth it (Gaussian 2.5 mm, ends pinned) and leave each stump along its own tangent -> (new centreline, info)"""
    from skimage.graph import route_through_array
    from scipy.ndimage import gaussian_filter1d
    lo, hi = P.min(0) - pad, P.max(0) + pad
    shape = tuple(np.ceil((hi - lo) / h).astype(int) + 1)
    ii = np.argwhere(np.ones(shape, bool))
    X = lo + ii * h
    db = bone_tree.query(X)[0]
    inside = np.zeros(len(X), bool)
    near = np.flatnonzero(db < 7.0)
    if len(near):
        ins, _cp, _d = ctx.bone_field.inside(X[near])
        inside[near[ins]] = True
    dev = cKDTree(P).query(X)[0]
    cost = 1.0 + dev_w * dev ** 2 + np.where(db < need, 40.0 * (need - db) / need, 0.0)
    cost[inside] = 1e4
    cost = cost.reshape(shape)
    lead = 6.0
    s0 = tuple(np.clip(np.rint((A["p"] + lead * A["t"] - lo) / h).astype(int), 0, np.asarray(shape) - 1))
    s1 = tuple(np.clip(np.rint((Bn["p"] + lead * Bn["t"] - lo) / h).astype(int), 0, np.asarray(shape) - 1))
    path, tot = route_through_array(cost, s0, s1, fully_connected=True, geometric=True)
    Q = resample(lo + np.asarray(path, float) * h, 1.0)
    # waypoints every ~6 mm of the lattice path, clamped cubic spline from A (leaving along A's tangent) to B (arriving against B's tangent)
    k = max(int(round(6.0 / 1.0)), 1)
    wp = np.vstack([A["p"], Q[::k][1:-1] if len(Q[::k]) > 2 else Q[len(Q) // 2:len(Q) // 2 + 1], Bn["p"]])
    seg = np.linalg.norm(np.diff(wp, axis=0), axis=1)
    u = np.r_[0, np.cumsum(seg)]
    from scipy.interpolate import CubicSpline
    cs = CubicSpline(u, wp, bc_type=((1, A["t"]), (1, -Bn["t"])))
    Q2 = cs(np.linspace(0, u[-1], int(u[-1] / 0.5) + 1))
    d_after = bone_tree.query(Q2)[0]
    return Q2, dict(route_cost=round(float(tot), 1), min_clearance_mm=round(float(d_after.min()), 2), path_len_mm=round(float(np.linalg.norm(np.diff(Q2, axis=0), axis=1).sum()), 1), waypoints=int(len(wp)))


def bishop_frames(P, u0):
    T = tangents(P)
    U = np.zeros_like(P)
    u = u0 - (u0 @ T[0]) * T[0]
    U[0] = u / np.linalg.norm(u)
    for i in range(1, len(P)):
        u = U[i - 1] - (U[i - 1] @ T[i]) * T[i]
        U[i] = u / max(np.linalg.norm(u), 1e-9)
    return T, U


def smoothstep(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def bridge_profile(P, A, Bn, bone_tree=None):
    """semi-axes and section orientation along the centreline P (stump A -> stump B): calibre morphs smoothly, the orientation twists by the (wrapped) difference of the major axes"""
    T, U = bishop_frames(P, A["major3"])
    s = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
    x = s / s[-1]
    sm = smoothstep(x)
    a = A["a"] + (Bn["a"] - A["a"]) * sm
    b = A["b"] + (Bn["b"] - A["b"]) * sm
    # twist: angle of B's major axis against the transported frame at the end, wrapped to (-90, 90]
    ub = Bn["major3"] - (Bn["major3"] @ T[-1]) * T[-1]
    ub /= max(np.linalg.norm(ub), 1e-9)
    wb = np.cross(T[-1], U[-1])
    ang = np.arctan2(ub @ wb, ub @ U[-1])
    ang = (ang + np.pi / 2) % np.pi - np.pi / 2
    phi = ang * sm
    W = np.cross(T, U)
    n_flat = 0
    if bone_tree is not None:
        # where a bone is closer than the long axis, lay the slit flat against it: the major axis perpendicular to the direction of the nearest bone point (blend over the distance, ends pinned)
        d, ib = bone_tree.query(P)
        to_b = bone_tree.data[ib] - P
        to_b = to_b - np.einsum("ij,ij->i", to_b, T)[:, None] * T
        nb = np.linalg.norm(to_b, axis=1)
        m = np.cross(T, to_b / np.maximum(nb[:, None], 1e-9))
        ang_t = np.arctan2(np.einsum("ij,ij->i", m, W), np.einsum("ij,ij->i", m, U))
        w = np.clip((a + 1.0 - d) / np.maximum(a - b + 1.0, 0.5), 0.0, 1.0)
        step = SECTION_STEP
        w[: int(2.0 / step)] = 0.0
        w[-int(2.0 / step):] = 0.0
        dphi = (ang_t - phi + np.pi / 2) % np.pi - np.pi / 2
        phi2 = phi + w * dphi
        un = np.unwrap(2 * phi2) / 2
        k = int(1.5 / step)
        ker = np.ones(2 * k + 1) / (2 * k + 1)
        un_s = np.convolve(np.pad(un, k, mode="edge"), ker, mode="valid")
        un_s[: int(1.0 / step)] = phi[: int(1.0 / step)]
        un_s[-int(1.0 / step):] = phi[-int(1.0 / step):]
        n_flat = int((w > 0.05).sum())
        phi = un_s
    Ur = np.cos(phi)[:, None] * U + np.sin(phi)[:, None] * W
    Wr = np.cross(T, Ur)
    return dict(T=T, U=Ur, W=Wr, a=a, b=b, s=s, twist_deg=float(np.degrees(ang)), flattened_samples=n_flat)


def bridge_mask(grid, P, prof, embed_a, embed_b, pad=0.8):
    """voxels inside the elliptical-section tube around P; the tube is prolonged EMBED_MM straight into both stumps with the stump's own section"""
    Tt = prof["T"]
    n_e = int(round(EMBED_MM / SECTION_STEP))
    ext0 = np.array([P[0] - Tt[0] * SECTION_STEP * (k + 1) for k in range(n_e)])[::-1]
    ext1 = np.array([P[-1] + Tt[-1] * SECTION_STEP * (k + 1) for k in range(n_e)])
    PP = np.vstack([ext0, P, ext1])
    TT = np.vstack([np.repeat(Tt[:1], n_e, 0), Tt, np.repeat(Tt[-1:], n_e, 0)])
    UU = np.vstack([np.repeat(prof["U"][:1], n_e, 0), prof["U"], np.repeat(prof["U"][-1:], n_e, 0)])
    WW = np.vstack([np.repeat(prof["W"][:1], n_e, 0), prof["W"], np.repeat(prof["W"][-1:], n_e, 0)])
    aa = np.r_[np.full(n_e, prof["a"][0]), prof["a"], np.full(n_e, prof["a"][-1])]
    bb = np.r_[np.full(n_e, prof["b"][0]), prof["b"], np.full(n_e, prof["b"][-1])]
    R = float(aa.max()) + pad
    lo = np.maximum(grid.idx(PP.min(0) - R), 0)
    hi = np.minimum(grid.idx(PP.max(0) + R) + 1, np.asarray(grid.shape))
    out = np.zeros(grid.shape, bool)
    ii = np.argwhere(np.ones(tuple(hi - lo), bool)) + lo
    X = grid.pos(ii)
    tree = cKDTree(PP)
    d, k = tree.query(X, distance_upper_bound=R)
    ok = np.isfinite(d)
    X, ii, k = X[ok], ii[ok], k[ok]
    rel = X - PP[k]
    along = np.einsum("ij,ij->i", rel, TT[k])
    xu, xw = np.einsum("ij,ij->i", rel, UU[k]), np.einsum("ij,ij->i", rel, WW[k])
    inside = (np.abs(along) <= SECTION_STEP * 1.01 + 0.05) & ((xu / aa[k]) ** 2 + (xw / bb[k]) ** 2 <= 1.0)
    ii = ii[inside]
    out[tuple(ii.T)] = True
    return out


def bend_max_deg(P, span=3.0):
    k = max(int(round(span / SECTION_STEP)), 1)
    T = tangents(P)
    c = np.clip((T[:-k] * T[k:]).sum(1), -1, 1)
    return float(np.degrees(np.arccos(c)).max()) if len(c) else 0.0


# ------------------------------------------------------------------------------------------ whole vein
def tail_mask(grid, st, radius=45.0):
    """voxels of the stump's tip beyond its cut plane (within `radius` mm of the cut point)"""
    lo = np.maximum(grid.idx(st["p"] - radius), 0)
    hi = np.minimum(grid.idx(st["p"] + radius) + 1, np.asarray(grid.shape))
    m = np.zeros(grid.shape, bool)
    ii = np.argwhere(np.ones(tuple(hi - lo), bool)) + lo
    X = grid.pos(ii)
    sel = ((X - st["p"]) @ st["t"] > 0.0) & (np.linalg.norm(X - st["p"], axis=1) <= radius)
    m[tuple(ii[sel].T)] = True
    return m


def bridge_vein(sid, v0, f0, ctx, bone_tree, log=print, budget=None, max_bend_deg=45.0, h=H, move_p95_max=0.6):
    """-> (v, f, info); v is None when no bridge was built / a guard failed (info['why'])"""
    pieces, specks = split_vein(v0, f0)
    info = dict(id=sid, pieces=[dict(nv=int(len(p["v"])), length_mm=round(p["length"], 1), vol_mm3=round(p["vol"], 1),
                                     ends=[(None if e is None else {k: (round(e[k], 2) if isinstance(e[k], float) else e[k]) for k in ("r_eq", "a", "b", "cut_depth_mm", "body_r_eq", "tip_r_eq", "hook_deg", "tip_to_cut_mm")} | dict(p=np.round(e["p"], 1).tolist()))
                                           for e in p["ends"]]) for p in pieces], specks=specks, links=[], why=[])
    if len(pieces) < 2:
        info["why"].append("one usable piece, nothing to bridge")
        return None, None, info
    links, unattached, notes = plan_chain(pieces)
    info["notes"] = notes
    info["unattached_pieces"] = unattached
    if not links or unattached:
        info["why"].append(("no link could be planned" if not links else f"pieces {unattached} cannot be attached") + (": " + "; ".join(notes) if notes else ""))
        return None, None, info
    allv = np.vstack([p["v"] for p in pieces])
    grid = C216.VoxGrid(allv.min(0) - 8.0, allv.max(0) + 8.0, h)
    solids = [grid.solid(p["v"], p["f"]) for p in pieces]
    cut_ends = {(lk[k][0], lk[k][1]) for lk in links for k in ("a", "b")}
    tails = {}
    for (i, e) in cut_ends:
        tm_ = tail_mask(grid, pieces[i]["ends"][e])
        tails[(i, e)] = float((solids[i] & tm_).sum()) * grid.h ** 3
        solids[i] = solids[i] & ~tm_
    union = np.zeros(grid.shape, bool)
    for sl in solids:
        union |= sl
    brmask = np.zeros(grid.shape, bool)
    bridges = []
    for lk in links:
        (i, ei), (j, ej) = lk["a"], lk["b"]
        A, Bn = pieces[i]["ends"][ei], pieces[j]["ends"][ej]
        P = hermite(A["p"], A["t"], Bn["p"], Bn["t"], kA=0.75 * float(np.clip(lk["cos_a"], 0.15, 1.0)), kB=0.75 * float(np.clip(lk["cos_b"], 0.15, 1.0)))
        need = max(np.sqrt(A["a"] * A["b"]), np.sqrt(Bn["a"] * Bn["b"])) + 1.0
        clear0 = float(bone_tree.query(P)[0].min())
        route = None
        if clear0 < need:
            P, route = route_around_bones(P, A, Bn, need, bone_tree, ctx)
        moved = 0.0 if route is None else route["path_len_mm"] - float(np.linalg.norm(np.diff(hermite(A["p"], A["t"], Bn["p"], Bn["t"]), axis=0), axis=1).sum())
        P = resample(P, SECTION_STEP)
        prof = bridge_profile(P, A, Bn, bone_tree)
        m = bridge_mask(grid, P, prof, A, Bn)
        brmask |= m
        ij = np.clip(grid.idx(P), 0, np.asarray(grid.shape) - 1)
        out_of = ~union[tuple(ij.T)]
        arc = np.r_[0, np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))]
        new_len = float(np.diff(arc)[out_of[1:] & out_of[:-1]].sum()) if len(arc) > 1 else 0.0
        rr = np.sqrt(prof["a"] * prof["b"])
        rec = dict(link=[[i, ei], [j, ej]], end_gap_mm=round(lk["end_gap_mm"], 2), nearest_vertex_gap_mm=round(float(cKDTree(pieces[i]["v"]).query(pieces[j]["v"])[0].min()), 2),
                   stump_a=dict(p=np.round(A["p"], 1).tolist(), r_eq=round(A["r_eq"], 2), a=round(A["a"], 2), b=round(A["b"], 2), cut_depth_mm=A["cut_depth_mm"]),
                   stump_b=dict(p=np.round(Bn["p"], 1).tolist(), r_eq=round(Bn["r_eq"], 2), a=round(Bn["a"], 2), b=round(Bn["b"], 2), cut_depth_mm=Bn["cut_depth_mm"]),
                   centreline_mm=round(float(arc[-1]), 1), chord_mm=round(float(np.linalg.norm(Bn["p"] - A["p"])), 1), new_part_mm=round(new_len, 1),
                   radius_mm=dict(start=round(float(rr[0]), 2), end=round(float(rr[-1]), 2), min=round(float(rr.min()), 2), max=round(float(rr.max()), 2)),
                   twist_deg=round(prof["twist_deg"], 1), bend_max_deg_per_3mm=round(bend_max_deg(P), 1), bone_route=route, hermite_clearance_mm=round(clear0, 2), route_extra_length_mm=round(moved, 1), cos_tangents=[round(lk["cos_a"], 2), round(lk["cos_b"], 2)],
                   centreline=np.round(P[:: max(1, len(P) // 24)], 1).tolist())
        why = []
        if bend_max_deg(P) > max_bend_deg:
            why.append(f"bend {bend_max_deg(P):.0f} deg per 3 mm (gate {max_bend_deg:g})")
        lo_r, hi_r = min(A["r_eq"], Bn["r_eq"]), max(A["r_eq"], Bn["r_eq"])
        if rr.min() < 0.9 * lo_r - 1e-6 or rr.max() > 1.1 * hi_r + 1e-6:
            why.append(f"bridge radius {rr.min():.2f}-{rr.max():.2f} outside the stump radii {lo_r:.2f}-{hi_r:.2f}")
        rec["why"] = why
        bridges.append((rec, P, prof))
        info["links"].append(rec)
    info["tails_removed_mm3"] = {f"{i}.{e}": round(v_, 0) for (i, e), v_ in tails.items()}
    full = union | brmask
    full = ndi.binary_closing(full, structure=ndi.generate_binary_structure(3, 1), iterations=1) | full
    lab, nlab = ndi.label(full, structure=np.ones((3, 3, 3)))
    cnt = np.bincount(lab.ravel())[1:]
    main = lab == (int(np.argmax(cnt)) + 1)
    dropped = float(1.0 - cnt.max() / cnt.sum())
    info["dropped_volume_share"] = round(dropped, 4)
    nf0 = len(f0)
    new_len_total = sum(r_["new_part_mm"] for r_, _P, _p in bridges)
    kept_len = sum(p["length"] for p in pieces)
    v1, f1 = C216.mask_to_mesh(main, grid, sigma_vox=0.8, budget=int(budget or nf0 * (1.0 + new_len_total / max(kept_len, 1.0)) * 1.1))       # the same triangle density as the old vein (+10 %: the loft is smoother than the old decimation)
    n_isl, isl, vw, fw = _islands(v1, f1)
    info["pieces_after"] = n_isl
    vol_old = abs(float(trimesh.Trimesh(v0, f0, process=False).volume))
    vol0 = float(union.sum()) * grid.h ** 3
    vol1 = abs(float(trimesh.Trimesh(v1, f1, process=False).volume))
    bnew = float((brmask & ~union).sum()) * grid.h ** 3
    info["volume_mm3"] = dict(old_mesh=round(vol_old, 0), old_pieces_kept=round(vol0, 0), tails_removed=round(sum(tails.values()), 0), bridge_new=round(bnew, 0), result=round(vol1, 0))
    why = [w for r_, _P, _p in bridges for w in r_["why"]]
    if n_isl != 1:
        why.append(f"{n_isl} pieces after the loft")
    if dropped > 0.01:
        why.append(f"{dropped:.1%} of the volume not connected to the main piece")
    ratio = vol1 / max(vol0 + bnew, 1.0)
    info["volume_ratio_vs_kept_plus_bridge"] = round(ratio, 3)
    if not (0.93 <= ratio <= 1.07):
        why.append(f"volume x{ratio:.3f} of the kept pieces + bridge")
    from scripts.transfer.q216_fix import surf_pts
    old_pts = np.vstack([surf_pts(p["v"], p["f"], 0.8) for p in pieces])
    d_old = trimesh.proximity.closest_point(trimesh.Trimesh(v1, f1, process=False), old_pts)[1]
    zone = np.zeros(len(old_pts), bool)
    for (i, e) in cut_ends:
        st = pieces[i]["ends"][e]
        zone |= (((old_pts - st["p"]) @ st["t"]) > -3.0) & (np.linalg.norm(old_pts - st["p"], axis=1) <= 45.0)           # the removed tip and 3 mm of the body that the loft smooths into the bridge
    info["old_to_new_mm"] = dict(p95_outside_bridge=round(float(np.percentile(d_old[~zone], 95)), 2), max_outside_bridge=round(float(d_old[~zone].max()), 2), points_in_zone=int(zone.sum()))
    if info["old_to_new_mm"]["p95_outside_bridge"] > move_p95_max:
        why.append(f"old pieces move {info['old_to_new_mm']['p95_outside_bridge']} mm (p95)")
    allP = np.vstack([P for _r, P, _p in bridges])
    rmaxb = max(r_["radius_mm"]["max"] for r_, _P, _p in bridges)
    zv = cKDTree(allP).query(v1)[0] < (rmaxb * 2.5 + 2.0)
    kept_pts = np.vstack([surf_pts(p["v"], p["f"], 0.8) for p in pieces])
    new_only = zv & (cKDTree(kept_pts).query(v1)[0] > 1.0)                   # vertices that are NOT on the person's kept surface: the bridge's own skin
    sk_in, sk_d = ctx.skin_state(v1[zv])
    ins, _cp, _d = ctx.bone_field.inside(v1[zv])
    ins_new, _cp2, _d2 = ctx.bone_field.inside(v1[new_only]) if new_only.any() else (np.zeros(0, bool), None, None)
    ins_old, _cp3, _d3 = ctx.bone_field.inside(kept_pts[:: max(1, len(kept_pts) // 20000)])
    info["bridge_zone"] = dict(vertices=int(zv.sum()), bridge_only_vertices=int(new_only.sum()), inside_skin_pct=round(sk_in, 2), min_skin_depth_mm=round(sk_d, 1), vertices_in_bone_zone=int(ins.sum()),
                               bridge_only_in_bone=int(ins_new.sum()), kept_surface_points_in_bone_pct=round(100.0 * float(ins_old.mean()), 2),
                               min_bone_dist_bridge_only_mm=round(float(bone_tree.query(v1[new_only])[0].min()), 2) if new_only.any() else None)
    if sk_in < 100.0 or sk_d < 1.0:
        why.append(f"skin: {sk_in:.1f} % inside, closest {sk_d:.1f} mm")
    if ins_new.any():
        why.append(f"{int(ins_new.sum())} vertices of the bridge's own surface inside a bone")
    cont = []
    tmr = trimesh.Trimesh(v1, f1, process=False)
    for rec, P, prof in bridges:
        for tag, k, st in (("a", 0, rec["stump_a"]), ("b", -1, rec["stump_b"])):
            kk = k if k == 0 else len(P) - 1
            kin = min(kk + 8, len(P) - 1) if kk == 0 else max(kk - 8, 0)           # 2 mm on the bridge side of the junction
            T = prof["T"][kin]
            e = exact_section(tmr, P[kin], T)
            if e is not None:
                r_res = float(np.sqrt(e["a"] * e["b"]))
                cont.append(dict(end=tag, result_r_eq=round(r_res, 2), stump_r_eq=st["r_eq"], ratio=round(r_res / st["r_eq"], 3)))
                if not (0.8 <= r_res / st["r_eq"] <= 1.25):
                    why.append(f"calibre at junction {tag}: x{r_res / st['r_eq']:.2f} of the stump")
    info["calibre_continuity"] = cont
    info["why"] = why
    info["triangles"] = [int(nf0), int(len(f1))]
    info["_bridges"] = [(r_["centreline"], r_["radius_mm"]) for r_, _P, _p in bridges]
    if why:
        return None, None, info
    return v1, f1, info


def _islands(v, f):
    from scripts.zanatomy.q198_core import weld, islands
    vw, fw = weld(np.asarray(v, float), np.asarray(f, np.int64), 0.02)
    isl = islands(vw, fw)
    return len(isl), isl, vw, fw
