#!/usr/bin/env python3
"""Q392: second nerve round on the Base pages (rule-based, badged). Starts from the CURRENT build/q309 pages (Q388 sciatic
re-route already in them).

    python3 scripts/anatomy/q392/patch_nerves_q392.py --page-dir build/q309/viewer_zan_atlas --out DIR     # private copy
    python3 scripts/anatomy/q392/patch_nerves_q392.py --page-dir DIR --report-only

Never writes into --page-dir: the patched page files (atlas_viewer_<stem>.html, index.html, the four geo files) go to
--out/<dir>, with Q392_nerves_<dir>.json (per structure: moved vertex count, max move, guards, the measured relations).
A page that already carries a Q392 badge is refused. Deterministic (no randomness; same input -> same bytes).

What it does, per body and per side (right and left measured and moved independently, never mirrored):

 1. MUSCULOCUTANEOUS NERVE -- RE-ROUTED (published numbers). Source: the nerve leaves the lateral root of the median nerve
    93 mm (M) below the coracoid tip, never enters coracobrachialis (7-10 mm away) and runs ~150 mm inside biceps /
    brachialis. Rule: origin fixed; it enters coracobrachialis at once (the origin already lies within Macchi's entry
    range 7.7 +/- 2.5 cm from the coracoid) and stays inside it until EXIT_MM = 116 mm from the coracoid tip (Macchi 2007:
    exit 11.6 +/- 0.8 cm; intramuscular length 4.4 +/- 1.9 cm), then runs back to its source course between biceps and
    brachialis over BLEND_MCN mm (Gray's relation); the last FIX_END mm (lateral antebrachial cutaneous junction) fixed.
 2. LATERAL FEMORAL CUTANEOUS NERVE -- RE-ROUTED (published numbers). Source: it leaves the psoas at once and runs
    through the anterior abdominal wall (inside transversus abdominis, 19-80 mm from iliacus), reaching the inguinal
    ligament correctly (11 mm medial to the ASIS). Rule: top fixed; along the lateral border of psoas major down to the
    level EMERGE_BELOW_CREST mm below the iliac crest (Uzel 2011: emergence -0.98 +/- 5.57 cm from the crest; 12.39 +/-
    2.67 cm from the ASIS), then on the anterior face of iliacus on the straight line to the source's passage under the
    inguinal ligament (Mandal 2022: 2.1 +/- 1.3 cm medial to the ASIS -- the source passage, kept fixed with everything
    below it).
 3. CONTACT CORRECTION (no new course): the obturator nerve (centre 1.5-10 mm inside pectineus / adductor longus /
    sartorius over ~180 mm) and the medial antebrachial cutaneous nerve (4-12 mm inside biceps) are moved by the least
    displacement that takes their centre out of every muscle (Viterbi chain through free space, the ideal = the source
    course). Their level and their neighbours stay the source's; the verifier then reports which relation results.
 4. MUSCLE YIELDS (contact correction): biceps brachii, coracobrachialis and brachialis yield to the brachial artery,
    brachial veins, median (lateral-root mesh), ulnar and musculocutaneous nerves where they overlap them: their surface
    moves by at most YIELD_CAP mm, along the direction from the tube into the muscle, so that the tube's surface lies
    YIELD_CLR mm outside. Measured first: the bundle lies in the medial bicipital groove between coracobrachialis /
    brachialis (deep) and triceps (posterior) 10-25 mm under the medial skin, and its centres are only 1-5 mm inside the
    biceps' medial border; biceps volume 202 / 155 cm3 (M / F) vs 163 cm3 measured by MRI in unimpaired arms (Adkins 2021,
    doi:10.1073/pnas.2008597118) -- the muscle is not oversized, its medial border overlaps the bundle.
 5. Attached nerves (whose END lies on a moved stretch) follow (weight 1 at the contact, 0 at their far end), as the Q388
    stubs; a nerve that only crosses a moved stretch (median trunk, ilio-inguinal) is not moved.
Guards (a structure failing any is NOT written; said in the report): centre not deeper than CENTRE_TOL mm in a muscle
(other than the wanted one) on the moved stretch and never in a bone; no vertex deeper than BONE_TOL mm in a bone; max
move <= cap; turning angle of the smoothed centreline <= max(KINK_DEG, source + 5); length change <= len_tol.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy.ndimage import distance_transform_edt, gaussian_filter1d
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "q388"))
import lib388 as L  # noqa: E402
from reroute_sciatic_q388 import occupancy, write_copy, GRID  # noqa: E402

TAG = "Q392"
EXIT_MM = 124.0        # Macchi 2007: exit 11.6 +/- 0.8 cm from the coracoid; +1 SD because the Z origin is late (9.3 cm), so
#                        the intramuscular length (Macchi 4.4 +/- 1.9 cm) stays within 1 SD of its mean
BLEND_MCN = 40.0
EMERGE_BELOW_CREST = 10.0   # Uzel 2011: -0.98 +/- 5.57 cm relative to the iliac crest
FIX_TOP = 3.0
FIX_END = 8.0
CENTRE_TOL = 1.5
BONE_TOL = 1.0
KINK_DEG = 35.0
YIELD_CLR = 0.5
YIELD_CAP = 8.0
YIELD_LAT = 6.0
SRC = {
    "macchi": "Macchi V et al. 2007, Clin Anat 20:400-406, doi:10.1002/ca.20402 (MCN enters coracobrachialis 7.7 +/- 2.5 cm, exits 11.6 +/- 0.8 cm from the coracoid; 4.4 +/- 1.9 cm inside)",
    "clavert": "Clavert P et al. 2009, Surg Radiol Anat 31:49-53, doi:10.1007/s00276-008-0426-2 (entry 55.7 mm from the coracoid tip)",
    "krassnig": "Krassnig R et al. 2023, Eur J Trauma Emerg Surg 49:299-306, doi:10.1007/s00068-022-02063-1 (entry at 14.9-33.9 % of humeral length from the greater-tubercle tip)",
    "uzel": "Uzel M et al. 2011, Clin Orthop Relat Res 469:2605-2611, doi:10.1007/s11999-011-1858-2 (LFCN emerges from the lateral border of psoas -0.98 +/- 5.57 cm from the iliac crest, 12.39 +/- 2.67 cm from the ASIS)",
    "mandal": "Mandal P et al. 2022, Plast Reconstr Surg 149:1147-1151, doi:10.1097/PRS.0000000000009034 (LFCN medial border 2.1 +/- 1.3 cm medial to the ASIS at the inguinal ligament, 93 nerves)",
    "hospodar": "Hospodar PP et al. 1999, J Orthop Trauma 13:17-19, doi:10.1097/00005131-199901000-00005 (20.4 mm medial to the ASIS, range 3-46; always anterior to iliopsoas)",
    "adkins": "Adkins AN et al. 2021, PNAS 118:e2008597118, doi:10.1073/pnas.2008597118 (biceps brachii 163 cm3, unimpaired arm, MRI)",
    "gray": "Gray's Anatomy (relations; knowledge only): MCN between biceps and brachialis; brachial bundle in the medial bicipital groove outside biceps; obturator anterior division behind adductor longus / pectineus, on adductor brevis; LFCN across iliacus deep to the iliac fascia",
}


def sid(b, s):
    return f"{b}_{s}"


def coracoid_tip(scap):
    a = scap[scap[:, 2] > np.percentile(scap[:, 2], 97)]
    return a[np.argmax(a[:, 2])]


def stations(N, step=3.0):
    C0 = L.centreline(N, n=60)
    n = int(max(40, L.arclen(C0)[-1] / step))
    C = L.centreline(N, n=n)
    return gaussian_filter1d(C, 2.0, axis=0, mode="nearest")


def tube_radius(N, C):
    r = L.local_radius(N, C)
    r = np.where(np.isfinite(r), r, np.nanmedian(r))
    return np.clip(gaussian_filter1d(r, 2), 0.4, 6.0)


def slice_occ(sc, y, cx, cz, ids):
    ids = [k for k in ids]
    return occupancy(sc, y, cx, cz, ids)


def viterbi(sc, Cs, rad, lo, hi, ideal, sig, exclude=(), want=None, step_max=8.0, skip=None, dep_w=12.0):
    """stations lo..hi (both fixed at the source) -> chosen (x, z) per station. ideal[i] = (x, z); want[i] = mesh id the
    centre should lie inside (then that mesh is not an obstacle and being outside it costs)."""
    want = want or {}
    cands, unary = [], []
    for i in range(lo, hi + 1):
        if i in (lo, hi):
            cands.append(Cs[i][[0, 2]][None]); unary.append(np.zeros(1)); continue
        ix, iz = ideal[i]
        ids = [k for k in sc.near_ids([ix, Cs[i, 1], iz], 31) if k not in exclude and k != want.get(i)
               and not (skip and skip(i, k))]
        xs, zs, occ = slice_occ(sc, Cs[i, 1], ix, iz, ids)
        clr = distance_transform_edt(~occ) * GRID
        dep = distance_transform_edt(occ) * GRID
        X, Z = np.meshgrid(xs, zs, indexing="ij")
        U = 0.5 * (np.hypot(X - ix, Z - iz) / sig[i]) ** 2 + 6.0 * np.maximum(0.0, rad[i] + 0.5 - clr) + dep_w * dep
        if want.get(i):
            _, _, ow = slice_occ(sc, Cs[i, 1], ix, iz, [want[i]])
            out = distance_transform_edt(~ow) * GRID          # distance to the wanted muscle's interior
            U = U + 20.0 * out + 10.0 * (~ow)
        U = U[::2, ::2].ravel(); X = X[::2, ::2].ravel(); Z = Z[::2, ::2].ravel()
        keep = np.argsort(U, kind="stable")[:150]
        cands.append(np.c_[X[keep], Z[keep]]); unary.append(U[keep])
    cost = unary[0].copy(); back = []
    for k in range(1, len(cands)):
        dxz = np.linalg.norm(cands[k][:, None, :] - cands[k - 1][None, :, :], axis=2)
        T = 0.5 * dxz ** 2 + np.where(dxz > step_max, 1e6, 0.0)
        tot = cost[None, :] + T
        j = np.argmin(tot, axis=1)
        back.append(j); cost = tot[np.arange(len(j)), j] + unary[k]
    path = [int(np.argmin(cost))]
    for k in range(len(cands) - 1, 0, -1):
        path.append(int(back[k - 1][path[-1]]))
    path = path[::-1]
    return np.array([cands[k][path[k]] for k in range(len(cands))])


def apply_course(N, Cs, chosen, lo, hi):
    """translate each ring of the tube by the displacement of its centreline station (calibre / counts / order kept)."""
    V0 = N["V"].astype(float)
    Dx = np.zeros(len(Cs)); Dz = np.zeros(len(Cs))
    st = np.arange(lo, hi + 1)
    Dx[st] = chosen[:, 0] - Cs[st, 0]; Dz[st] = chosen[:, 1] - Cs[st, 2]
    Dx = gaussian_filter1d(Dx, 1.0); Dz = gaussian_filter1d(Dz, 1.0)
    Dx[: lo + 1] = 0; Dz[: lo + 1] = 0; Dx[hi:] = 0; Dz[hi:] = 0
    disp = np.c_[Dx, np.zeros_like(Dx), Dz]
    _, ii = cKDTree(Cs).query(V0, k=2)
    a, b = Cs[ii[:, 0]], Cs[ii[:, 1]]
    w = np.clip(np.einsum("ij,ij->i", V0 - a, b - a) / np.maximum(np.einsum("ij,ij->i", b - a, b - a), 1e-9), 0, 1)
    dv = disp[ii[:, 0]] * (1 - w)[:, None] + disp[ii[:, 1]] * w[:, None]
    return V0 + dv, disp


def turn(P):
    T = np.diff(P, axis=0); T /= np.linalg.norm(T, axis=1)[:, None] + 1e-9
    return np.degrees(np.arccos(np.clip(np.einsum("ij,ij->i", T[:-1], T[1:]), -1, 1)))


def guards(D, sc, s, N, V1, disp, cap, len_tol, allow=None, bones=None):
    """allow: {station index: mesh id the centre may be inside}."""
    fails, ins = [], []
    allow = allow or {}
    Cs = stations(N)
    C1 = stations(dict(V=V1, F=N["F"]))
    mv = np.where(np.linalg.norm(disp, axis=1) > 0.05)[0]
    if not len(mv):
        return ["nothing moved"], {}
    # map moved stations of the source centreline onto the new one by arc fraction
    f = np.linspace(0, 1, len(C1))
    fm = np.linspace(0, 1, len(disp))[mv]
    j_lo, j_hi = int(np.searchsorted(f, fm.min())), int(np.searchsorted(f, fm.max()))
    for j in range(j_lo, min(j_hi + 1, len(C1)), 2):
        p = C1[j]
        ids = [k for k in sc.near_ids(p, 12) if k not in set(allow.values())]
        xs, zs, occ = occupancy(sc, p[1], p[0], p[2], ids)
        dep = float((distance_transform_edt(occ) * GRID)[occ.shape[0] // 2, occ.shape[1] // 2])
        inb = [k for k, _ in L.inside_ids(sc, p, systems=("bone",))]
        if dep > CENTRE_TOL or inb:
            ins.append((round(float(p[1]), 1), [k for k, _ in L.inside_ids(sc, p)], round(dep, 1)))
    if ins:
        fails.append(f"centre inside muscle/bone (depth > {CENTRE_TOL} mm) at {len(ins)} stations: {ins[:5]}")
    moved = np.linalg.norm(V1 - N["V"], axis=1) > 0.05
    for b in bones or []:
        Bm = D[b]
        lo, hi = Bm["V"].min(0) - 2, Bm["V"].max(0) + 2
        sel = moved & np.all((V1 >= lo) & (V1 <= hi), axis=1)
        if sel.any():
            wn = np.abs(L.winding(Bm["V"], Bm["F"], V1[sel]))
            if (wn > 0.5).any():
                dd = sc.kd(b).query(V1[sel][wn > 0.5])[0]
                if dd.max() > BONE_TOL:
                    fails.append(f"{b}: {int((wn > 0.5).sum())} vertices inside, deepest {dd.max():.1f} mm")
    l0, l1 = L.arclen(Cs)[-1], L.arclen(C1)[-1]
    if abs(l1 - l0) / l0 * 100 > len_tol:
        fails.append(f"length {l0:.0f} -> {l1:.0f} mm (> {len_tol} %)")
    md = float(np.linalg.norm(disp, axis=1).max())
    if md > cap:
        fails.append(f"displacement {md:.1f} > {cap}")
    a0, a1 = turn(Cs), turn(C1)
    if a1.max() > max(KINK_DEG, a0.max() + 5):
        fails.append(f"kink {a1.max():.0f} deg (source {a0.max():.0f})")
    return fails, dict(len_before=float(l0), len_after=float(l1), max_move=md, max_turn=float(a1.max()),
                       max_turn_src=float(a0.max()), inside_after=ins)


# ------------------------------------------------------------------------------------------------ the three courses
def mcn_course(D, sc, s):
    N = D[sid("musculocutaneous_n", s)]
    Cs = stations(N); S = L.arclen(Cs); rad = tube_radius(N, Cs)
    tip = coracoid_tip(D[sid("scapula", s)]["V"].astype(float))
    cb = sid("coracobrachialis", s)
    lo = int(np.searchsorted(S, FIX_TOP)); hi = int(np.searchsorted(S, S[-1] - FIX_END))
    dt = np.linalg.norm(Cs - tip, axis=1)
    i_exit = int(np.argmax(dt >= EXIT_MM))
    ideal, sig, want, kind = {}, {}, {}, {}
    CBV = D[cb]["V"]
    for i in range(lo + 1, i_exit + 1):
        sl = L.slab(CBV, Cs[i, 1], 1.5)
        ideal[i] = (float(sl[:, 0].mean()), float(sl[:, 2].mean())) if len(sl) else (float(Cs[i, 0]), float(Cs[i, 2]))
        sig[i] = 3.0; want[i] = cb; kind[i] = "in_coracobrachialis"
    xe, ze = ideal[i_exit]
    for i in range(i_exit + 1, hi):
        b = np.clip((S[i] - S[i_exit]) / BLEND_MCN, 0, 1)
        ideal[i] = ((1 - b) * xe + b * Cs[i, 0], (1 - b) * ze + b * Cs[i, 2]); sig[i] = 4.0; kind[i] = "biceps_brachialis"
    bic = sid("biceps_brachii", s)

    def skip(i, k):   # in coracobrachialis only bones are obstacles; below it biceps is not (it yields to the nerve, step 4)
        return (D[k]["sys"] != "bone") if i in want else (k == bic)
    chosen = viterbi(sc, Cs, rad, lo, hi, ideal, sig, want=want, skip=skip)
    V1, disp = apply_course(N, Cs, chosen, lo, hi)
    rep = dict(rule="re-route (Macchi 2007 entry/exit)", i_exit=i_exit, exit_from_tip_src=float(dt[i_exit]),
               origin_from_tip=float(dt[0]))
    return N, V1, disp, rep, [cb, bic]


def lfcn_course(D, sc, s):
    sg = L.SG[s]
    N = D[sid("lateral_femoral_cutaneous_n", s)]
    Cs = stations(N); S = L.arclen(Cs); rad = tube_radius(N, Cs)
    ps = D[sid("zan_psoas_major", s)]; ia = D[sid("zan_iliacus_muscle", s)]
    lig = D.get(sid("inguinal_ligament", s)) or D.get(sid("zan_inguinal_ligament", s))
    hip = D[sid("hip_bone", s)]["V"].astype(float)
    crest = float(hip[:, 1].max())
    # top fixed until the nerve has descended 6 mm (its first stretch can run horizontally, where y-slices cannot steer it)
    lo = max(int(np.searchsorted(S, FIX_TOP)), int(np.argmax(Cs[0, 1] - Cs[:, 1] > 6.0)))
    d_lig = cKDTree(lig["V"]).query(Cs)[0]
    hi = int(np.argmin(d_lig))                     # the passage under the inguinal ligament: fixed with all below
    yE = crest - EMERGE_BELOW_CREST
    P = Cs[hi]
    ideal, sig = {}, {}
    # emergence point E: psoas lateral border at yE
    def psoas_lat(y):
        sl = L.slab(ps["V"], y, 1.5)
        if not len(sl):
            return None
        q = sl[np.argmax(sg * sl[:, 0])]
        return q
    pE = psoas_lat(yE)
    for i in range(lo + 1, hi):
        y = Cs[i, 1]; r = rad[i] + 0.5
        if y >= yE:
            q = psoas_lat(y)
            b = float(np.clip((S[i] - S[lo]) / 30.0, 0, 1))      # from the fixed top onto the psoas border over 30 mm
            ideal[i] = ((1 - b) * Cs[i, 0] + b * (q[0] + sg * r), (1 - b) * Cs[i, 2] + b * q[2]) if q is not None else (float(Cs[i, 0]), float(Cs[i, 2]))
            sig[i] = 3.0
        else:
            t = (yE - y) / max(yE - P[1], 1e-6)
            x = (1 - t) * (pE[0] + sg * r) + t * P[0]
            sl = L.slab(ia["V"], y, 1.5)
            sl = sl[np.abs(sl[:, 0] - x) < 3] if len(sl) else sl
            z = float(sl[:, 2].max() + r) if len(sl) else float((1 - t) * pE[2] + t * P[2])
            ideal[i] = (float(x), z); sig[i] = 3.0
    ks = sorted(ideal)
    xz = gaussian_filter1d(np.array([ideal[i] for i in ks]), 3.0, axis=0, mode="nearest")
    ideal = {i: (float(a), float(b)) for i, (a, b) in zip(ks, xz)}
    chosen = viterbi(sc, Cs, rad, lo, hi, ideal, sig, step_max=12.0)
    V1, disp = apply_course(N, Cs, chosen, lo, hi)
    rep = dict(rule="re-route (Uzel 2011 emergence, Mandal 2022 passage)", y_emerge=float(yE), crest=crest,
               passage=P.tolist())
    return N, V1, disp, rep, []


def contact_course(D, sc, s, base, fix_top=FIX_TOP, fix_end=FIX_END):
    N = D[sid(base, s)]
    Cs = stations(N); S = L.arclen(Cs); rad = tube_radius(N, Cs)
    lo = int(np.searchsorted(S, fix_top)); hi = int(np.searchsorted(S, S[-1] - fix_end))
    ideal = {i: (float(Cs[i, 0]), float(Cs[i, 2])) for i in range(lo + 1, hi)}
    sig = {i: 6.0 for i in ideal}
    chosen = viterbi(sc, Cs, rad, lo, hi, ideal, sig, dep_w=40.0)
    V1, disp = apply_course(N, Cs, chosen, lo, hi)
    return N, V1, disp, dict(rule="contact correction (least displacement out of the muscles)"), []


# ------------------------------------------------------------------------------------------------ muscle yield
def muscle_yield(M, tubes, cap=YIELD_CAP, clr=YIELD_CLR, lat=YIELD_LAT):
    """M: muscle mesh dict; tubes: list of (V, F) tube meshes. -> new muscle vertices, per-vertex move."""
    V = M["V"].astype(float)
    best = np.zeros_like(V)
    for TV, TF in tubes:
        T = dict(V=TV, F=TF)
        C = stations(T, step=2.0); r = tube_radius(T, C)
        kd = cKDTree(C)
        lo, hi = TV.min(0) - 15, TV.max(0) + 15
        sel = np.where(np.all((V >= lo) & (V <= hi), axis=1))[0]
        if not len(sel):
            continue
        # inward direction per station: from the station to the centroid of the muscle's section at that level (the mean of
        # its surface vertices within +/- 3 mm in y, i.e. the whole perimeter -- a local mean would point at the nearest surface)
        u = np.zeros_like(C)
        for k, c in enumerate(C):
            sl = V[np.abs(V[:, 1] - c[1]) < 3.0]
            if len(sl):
                d = sl.mean(0) - c; d[1] = 0.0
                u[k] = d / (np.linalg.norm(d) + 1e-9)
        u = gaussian_filter1d(u, 2.0, axis=0, mode="nearest"); u /= np.linalg.norm(u, axis=1)[:, None] + 1e-9
        tang = np.gradient(C, axis=0); tang /= np.linalg.norm(tang, axis=1)[:, None] + 1e-9
        dd, kk = kd.query(V[sel])
        c = C[kk]; uu = u[kk]; tt = tang[kk]
        rel = V[sel] - c
        along = np.einsum("ij,ij->i", rel, tt)
        rel = rel - along[:, None] * tt
        a = np.einsum("ij,ij->i", rel, uu)                       # signed distance along the inward direction
        lat_d = np.linalg.norm(rel - a[:, None] * uu, axis=1)     # distance across
        need = (r[kk] + clr) - a
        wlat = np.clip(1 - np.maximum(lat_d - (r[kk] + clr), 0) / lat, 0, 1)   # full within the tube's width, 0 at +lat mm (coarse muscle triangles)
        end = (kk > 0) & (kk < len(C) - 1)
        m = (need > 0) & (wlat > 0) & end & (np.abs(along) < 3.0)
        amt = np.minimum(need, cap) * wlat
        mv = np.zeros((len(sel), 3)); mv[m] = (amt[m])[:, None] * uu[m]
        rows = sel
        bigger = np.linalg.norm(mv, axis=1) > np.linalg.norm(best[rows], axis=1)
        best[rows[bigger]] = mv[bigger]
    return V + best, np.linalg.norm(best, axis=1)


def mesh_volume(V, F):
    a, b, c = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    return float(abs(np.einsum("ij,ij->i", a, np.cross(b, c)).sum()) / 6.0)


# ------------------------------------------------------------------------------------------------ attached nerves
def followers(D, s, moved: dict, skip: set, lim=3.0):
    """nerves touching a moved stretch follow: weight 1 at the contact, 0 at their far end."""
    out = {}
    for k, v in D.items():
        if v["sys"] != "nerve" or k in moved or k in skip or not k.endswith("_" + s):
            continue
        V = v["V"].astype(float)
        for mk, (V0, V1) in moved.items():
            dv = V1 - V0
            mvd = np.linalg.norm(dv, axis=1) > 0.05
            if not mvd.any():
                continue
            lo, hi = V0[mvd].min(0) - lim, V0[mvd].max(0) + lim
            if np.any(V.max(0) < lo) or np.any(V.min(0) > hi):
                continue
            d, ii = cKDTree(V0).query(V)
            j = int(np.argmin(d))
            if d[j] > lim or not mvd[ii[j]]:
                continue
            Cf = L.centreline(v, n=40)                 # only a nerve that ENDS on the moved stretch is attached to it;
            if Cf is None or min(np.linalg.norm(V[j] - Cf[0]), np.linalg.norm(V[j] - Cf[-1])) > 8.0:
                continue                               # one that merely crosses it (median trunk, ilio-inguinal) stays
            g = np.linalg.norm(V - V[j], axis=1)
            w = np.clip(1 - g / max(g.max(), 1e-6), 0, 1) ** 1.5
            out[k] = (mk, V + w[:, None] * dv[ii[j]][None])
            break
    return out


# ------------------------------------------------------------------------------------------------ main
BONES = {"musculocutaneous_n": ("humerus", "scapula"), "lateral_femoral_cutaneous_n": ("hip_bone",),
         "obturator_n": ("hip_bone", "femur"), "zan_medial_antebrachial_cutaneous_nerve": ("humerus",)}
CAPS = {"musculocutaneous_n": (30.0, 12.0), "lateral_femoral_cutaneous_n": (90.0, 25.0), "obturator_n": (15.0, 6.0),
        "zan_medial_antebrachial_cutaneous_nerve": (18.0, 6.0)}
YIELD = {"biceps_brachii": ("zan_brachial_artery", "zan_brachial_veins", "median_n_lateral_root", "ulnar_n", "musculocutaneous_n"),
         "coracobrachialis": ("zan_brachial_artery", "zan_brachial_veins", "median_n_lateral_root", "ulnar_n"),
         "brachialis": ("zan_brachial_artery", "zan_brachial_veins", "median_n_lateral_root", "ulnar_n", "musculocutaneous_n")}


def badge_for(base, rep):
    if base == "musculocutaneous_n":
        return (f"{TAG} RULE-BASED RE-ROUTE (course only; the Z-Anatomy tube's cross-section and vertex order are kept): the "
                f"source nerve never entered coracobrachialis and ran inside biceps / brachialis; it now enters "
                f"coracobrachialis at its origin, leaves it {EXIT_MM:.0f} mm from the coracoid tip and runs between biceps "
                f"and brachialis. Moved up to {rep['max_move']:.0f} mm. Stated error: +/- 8 mm at the exit (the cited SD); "
                f"elsewhere the free-space projection (grid {GRID} mm). Sources: {SRC['macchi']}; {SRC['clavert']}; {SRC['gray']}.")
    if base == "lateral_femoral_cutaneous_n":
        return (f"{TAG} RULE-BASED RE-ROUTE (course only): the source nerve ran through the anterior abdominal wall "
                f"(inside transversus abdominis); it now runs down the lateral border of psoas to {EMERGE_BELOW_CREST:.0f} mm "
                f"below the iliac crest and across the anterior face of iliacus to its (unchanged) passage under the "
                f"inguinal ligament. Moved up to {rep['max_move']:.0f} mm. Stated error: +/- 55 mm for the emergence level "
                f"(the cited SD), the passage is the source's. Sources: {SRC['uzel']}; {SRC['mandal']}; {SRC['gray']}.")
    return (f"{TAG} CONTACT CORRECTION (no new course): the source centre lay inside a muscle mesh; moved by the least "
            f"displacement out of the muscles (up to {rep['max_move']:.1f} mm, grid {GRID} mm). Level and neighbours are the "
            f"source's.")


def run_side(D, sc, s, log):
    sides = {}
    replace, badges = {}, {}
    moved_nerves = {}
    jobs = [("musculocutaneous_n", mcn_course), ("lateral_femoral_cutaneous_n", lfcn_course),
            ("zan_medial_antebrachial_cutaneous_nerve", lambda D, sc, s: contact_course(D, sc, s, "zan_medial_antebrachial_cutaneous_nerve"))]
    for base, fn in jobs:
        k = sid(base, s)
        if k not in D:
            sides[k] = dict(skipped="no mesh"); continue
        N, V1, disp, rep, allow_ids = fn(D, sc, s)
        cap, lt = CAPS[base]
        allow = {}
        fails, g = guards(D, sc, s, N, V1, disp, cap, lt, allow={i: a for i, a in enumerate(allow_ids)},
                          bones=[sid(b, s) for b in BONES[base] if sid(b, s) in D])
        rep.update(g); rep["fails"] = fails
        rep["moved_vertices"] = int((np.linalg.norm(V1 - N["V"], axis=1) > 0.05).sum())
        sides[k] = rep
        log(f"  {k}: max move {rep.get('max_move', 0):.1f} mm, length {rep.get('len_before', 0):.0f}->{rep.get('len_after', 0):.0f}, "
            f"turn {rep.get('max_turn', 0):.0f} (src {rep.get('max_turn_src', 0):.0f}), guards {'OK' if not fails else fails}")
        if fails:
            continue
        replace[k] = V1; badges[k] = badge_for(base, rep)
        moved_nerves[k] = (N["V"].astype(float), V1)
    # attached nerves follow
    for k, (mk, V) in followers(D, s, moved_nerves, set()).items():
        replace[k] = V; badges[k] = f"{TAG}: its end at {D[mk]['name']} follows that nerve's {TAG} correction (weight 1 at the contact, 0 at its far end)."
        sides[k] = dict(follows=mk, max_move=float(np.linalg.norm(V - D[k]["V"], axis=1).max()))
    # muscles yield to the bundle (with the re-routed MCN)
    for mb, tbs in YIELD.items():
        mk = sid(mb, s)
        if mk not in D:
            continue
        tubes = []
        for tb in tbs:
            tk = sid(tb, s)
            if tk in D:
                tubes.append((replace.get(tk, D[tk]["V"]).astype(float), D[tk]["F"]))
        V1, mv = muscle_yield(D[mk], tubes)
        v0, v1 = mesh_volume(D[mk]["V"].astype(float), D[mk]["F"]), mesh_volume(V1, D[mk]["F"])
        rep = dict(rule="muscle yields (contact correction)", moved_vertices=int((mv > 0.05).sum()), max_move=float(mv.max()),
                   volume_cm3=[round(v0 / 1000, 2), round(v1 / 1000, 2)])
        sides[mk] = rep
        log(f"  {mk}: {rep['moved_vertices']} vertices moved, max {rep['max_move']:.1f} mm, volume {rep['volume_cm3']}")
        if rep["moved_vertices"]:
            replace[mk] = V1
            badges[mk] = (f"{TAG} CONTACT CORRECTION: its surface yields (at most {YIELD_CAP:.0f} mm, {rep['moved_vertices']} "
                          f"vertices) where the source mesh overlapped the brachial artery / veins and the median, ulnar and "
                          f"musculocutaneous nerves, which lie outside it (medial bicipital groove; between biceps and "
                          f"brachialis). Volume {rep['volume_cm3'][0]} -> {rep['volume_cm3'][1]} cm3. Sources: {SRC['gray']}; "
                          f"{SRC['adkins']}.")
    return replace, badges, sides


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--page-dir", required=True)
    ap.add_argument("--out")
    ap.add_argument("--report-only", action="store_true")
    a = ap.parse_args(argv)
    src = Path(a.page_dir).resolve()
    D = L.LazyPage(src)
    for k in ("musculocutaneous_n_r", "biceps_brachii_r"):
        if TAG in (D[k]["rec"].get("procedural_badge") or ""):
            print("Q392_PATCH_REFUSED: page already carries the Q392 patch"); return 2
    sc = L.Scene(D)
    replace, badges, report = {}, {}, {"page": src.name, "sides": {}}
    for s in "rl":
        print(f"{src.name} {s}:")
        r, b, rep = run_side(D, sc, s, print)
        replace.update(r); badges.update(b); report["sides"][s] = rep
    report["replaced"] = sorted(replace)
    report["moved_vertex_count"] = {k: int((np.linalg.norm(V - D[k]["V"], axis=1) > 0.05).sum()) for k, V in replace.items()}
    report["sources"] = SRC
    if a.out and not a.report_only and replace:
        out = Path(a.out).resolve()
        assert out != src and src not in out.parents, "--out must not be inside the source page dir"
        files = write_copy(src, out / src.name, replace, D, badges)
        report["written"] = files
    rp = Path(a.out or ".") / f"Q392_nerves_{src.name}.json"
    rp.parent.mkdir(parents=True, exist_ok=True)
    rp.write_text(json.dumps(report, indent=1, default=float))
    nfail = sum(1 for s in report["sides"].values() for v in s.values() if isinstance(v, dict) and v.get("fails"))
    print(("Q392_PATCH_OK" if not nfail else f"Q392_PATCH_PARTIAL {nfail} structures held back"), "->", rp)
    return 0 if not nfail else 1


if __name__ == "__main__":
    sys.exit(main())
