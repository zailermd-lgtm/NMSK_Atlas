#!/usr/bin/env python3
"""Q349: Base pages, both hands -- the palmar-dorsal order of the proper palmar digital nerves and arteries in the fingers, and the
depth of the superficial palmar venous arch.

    python3 scripts/anatomy/q349/conform_fingers_q349.py --page-dir DIR             # dry run: measure, report, write nothing
    python3 scripts/anatomy/q349/conform_fingers_q349.py --page-dir DIR --write     # and write the page files in DIR

Facts (owner's books, docs/Q348_reference_pass.md §2.3 / §3; knowledge only, no prose copied):
  F1  in the palm the common palmar digital nerve lies dorsal (deep) to the common palmar digital artery; on the sides of the fingers the
      proper palmar digital nerve lies palmar (superficial) to the proper palmar digital artery; they cross at the finger root
      (Mannan's Regional Dissection and Surface Anatomy, 14th ed. 2017, pp. 166, 168).
  F2  the superficial palmar venous arch is the venae comitantes of the superficial palmar arterial arch, i.e. it lies at the arterial
      arch's depth, superficial to the median-nerve branches and the flexor tendons (Mannan pp. 137, 166, 182).

Measured on the Z-Anatomy source (both Base bodies, both hands; data/derived/Q349_fingers_report.json): in the palm the common
digital nerves already lie 1.5-11 mm deep to the common digital arteries (Q340 lifted the arteries) -- kept; in the fingers the proper
nerves lie up to ~9 mm DORSAL to the arteries -- the wrong order; the venous arch lies ~9 mm deep to the arterial arch, on the carpus.

The conform (a documented, rule-driven move of the real source meshes; their shape is the source's):
  fingers  per hand, finger f (1-5) and side (radial / ulnar): finger coordinates of hand_frame.Hand (s = mm along the bone chain from
           the MCP joint, palmar / radial offsets in each phalanx's frame).  Centrelines of the nerve strand (median + ulnar proper digital
           branches) and the artery strand (proper palmar digital arteries) by a Gaussian kernel over s (SIGMA mm); tube radii = 90th-percentile
           vertex distance to the centreline.  Root = where the strand meets its unmoved parent (common digital vessel), never proximal
           to the hand's measured common-artery bifurcation level (thumb: its MCP joint).  Requirement, from root + ZONE mm distally:
           nerve centreline palmar to the artery centreline by m = max(M_MIN, the tube clearance sqrt((rn + ra + GAP)^2 - dr^2)).
           Move = the shortfall, split nerve palmar (share lam) / artery dorsal (1 - lam), each a smooth function of s (Lipschitz upper
           envelope K_ENV, times smoothstep from the strand's own root over ZONE mm, so it is zero at the junction with the unmoved
           parent) along the phalanx's palmar direction p (blended across joints): every cross-section moves rigidly.  Shares tried in
           order LAMS; the first that passes every guard ships, else the pair is left.  Per-vertex move capped at CAP mm.
  venous   superficial venous palmar arch: per vertex (its cross-section centroid, ball XS mm), the lift along the palm normal n
           (lib340.Palm) that puts it at the depth of the nearest arterial-arch cross-section (in the palm plane), or, where the two
           overlap in plan, just under it in contact (h_a - sqrt((ra + rv + GAP)^2 - D^2)); lifts only.  Field = Lipschitz upper
           envelope (slope tan BEND_MAX along the mesh) held at zero at the junctions with the unmoved ulnar veins / median antebrachial
           vein and at the in-finger part of the palmar digital veins (whose palm part follows, tapered), averaged per cross-section.
           Capped at CAP_V mm (the arterial arch's own Q340 lift on these pages was up to 9.9 mm).
Guards (a pair / the arch failing any is left untouched and listed, never forced): vertex / triangle counts unchanged (pose rig contract);
flipped triangles <= 0.5 % of the moved faces, stretched (area x0.5 / x2) <= before + 12 %; no group holds MORE of the structure's
vertices after than before with a new entrant that moved > 0.25 mm -- hand bones, flexor tendons, extensor tendons, tendon sheaths,
outside the skin, the Q340 arterial arch / common digital arteries, nerve inside artery / artery inside nerve (venous: also lumbricals,
digital nerves, above the palmar aponeurosis); max rotation of any moved edge <= BEND_MAX deg (no kinks); move <= CAP; the Q338 R1 rule
(proper artery strand median palmar offset >= -1.0 mm).  A pair / the arch ships only if it passes on BOTH hands (mirror images).
Every replaced file is first copied beside itself as `<name>.q349` (never overwriting); a page already carrying a Q349 note is refused.
Vertex counts unchanged, so the page's pose rig stays consistent (make_pose_rig --inject checks counts only): no rig splice.
Deterministic (no random state).
"""
from __future__ import annotations

import argparse, json, shutil, sys, time
from pathlib import Path

import numpy as np
from scipy import sparse
from scipy.sparse import csgraph
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE.parent / "q340"))
import conform_palm_q340 as C340   # noqa: E402  page I/O, BoneSet, stats, palm_depth, Side
from scripts.transfer.q213_inbone import flipped_pct, stretched_pct, volume as vol_q213  # noqa: E402
L = C340.L
A = L.A
HF = L.HF

OUT = REPO / "data/derived/Q349_fingers_report.json"
TAG = "Q349:"
SIGMA, ZONE, M_MIN, GAP, K_ENV, CAP, BEND_MAX, LAMS, W_MIN = 2.5, 15.0, 0.5, 0.3, 0.2, 4.0, 30.0, (0.5, 0.65, 0.35, 0.8, 0.2), 8.0
CAP_V, XS, JOIN, DMAX = 10.0, 2.5, 1.5, 15.0
NERVES = ["zan_proper_palmar_digital_branches_of_median_nerve", "zan_proper_palmar_digital_branches_of_ulnar_nerve"]
ARTERY = "zan_proper_palmar_digital_arteries"
COMMON_N = ["zan_common_palmar_digital_branches_of_median_nerve", "zan_common_palmar_digital_branches_of_ulnar_nerve"]
COMMON_A = "zan_common_palmar_digital_arteries"
ARCH, VARCH, DVEINS = "zan_superficial_palmar_arch", "zan_superficial_venous_palmar_arch", "zan_palmar_digital_veins"
VPARTNERS = ["zan_ulnar_veins", "zan_median_antebrachial_vein"]          # unmoved junctions of the venous arch (measured: both at the wrist)
GROUPS = {   # structure groups a moved vertex must not newly enter (generalised winding number > 0.5; bones: watertight inside test)
    "flexor tendons": ["zan_humero_ulnar_head_of_flexor_digitorum_superficialis", "flexor_digitorum_superficialis", "flexor_digitorum_profundus",
                       "flexor_pollicis_longus"],
    "extensor tendons": ["extensor_digitorum", "extensor_indicis", "extensor_digiti_minimi", "zan_extensor_pollicis_longus", "extensor_pollicis_brevis"],
    "tendon sheaths": ["zan_synovial_sheaths_of_digits_of_hand", "zan_cruciform_part_of_fibrous_sheath_of_digit_of_hand",
                       "zan_tendon_sheath_of_flexor_pollicis_longus"],
    "Q340 arterial arch": [ARCH, COMMON_A],
}
GROUPS_V = dict(GROUPS, **{
    "lumbricals": ["zan_lumbrical_muscles_of_hand"],
    "digital nerves": COMMON_N + NERVES + ["ulnar_n_superficial_branch", "ulnar_n_deep_branch", "recurrent_branch_of_median_n"],
})
MANNAN = ("Mannan's Regional Dissection and Surface Anatomy (Noor MA), 14th ed., Jaypee 2017, ISBN 978-93-86322-11-1 "
          "(owner's copy; docs/Q348_reference_pass.md §1)")
SRC_F1 = "Mannan pp. 166, 168"
SRC_F2 = "Mannan pp. 137, 166, 182"


# ------------------------------------------------------------------ small geometry helpers
def smoothstep(x):
    x = np.clip(x, 0, 1)
    return x * x * (3 - 2 * x)


def winding(P, V, F, chunk=96):
    """generalised winding number of points P w.r.t. a (possibly open) triangle mesh (as scripts/anatomy/q219/geomlib.winding);
    triangles farther than 30 mm from every point are dropped first (their contribution is the solid angle of a far patch: ~0 for a
    closed mesh, small for these open tubes)"""
    P = np.atleast_2d(P)
    out = np.zeros(len(P))
    if not len(P) or not len(F):
        return out
    lo, hi = P.min(0) - 30, P.max(0) + 30
    C = V[F].mean(1)
    F = F[np.all((C > lo) & (C < hi), axis=1)]
    if not len(F):
        return out
    Aa, Bb, Cc = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    for s in range(0, len(P), chunk):
        p = P[s:s + chunk, None, :]
        a, b, c = Aa[None] - p, Bb[None] - p, Cc[None] - p
        la, lb, lc = (np.linalg.norm(x, axis=2) for x in (a, b, c))
        det = np.einsum("ijk,ijk->ij", a, np.cross(b, c))
        den = la * lb * lc + np.einsum("ijk,ijk->ij", a, b) * lc + np.einsum("ijk,ijk->ij", a, c) * lb + np.einsum("ijk,ijk->ij", b, c) * la
        out[s:s + chunk] = np.arctan2(det, den).sum(axis=1) / (2 * np.pi)
    return out


def ball_centroids(v, R=XS):
    """per vertex: centroid of the vertices within R mm (the tube's cross-section centre) and the vertex's distance to it"""
    nb = cKDTree(v).query_ball_point(v, R)
    c = np.array([v[n].mean(0) for n in nb])
    return c, np.linalg.norm(v - c, axis=1), nb


def edges_of(f):
    e = np.vstack([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
    return np.unique(np.sort(e, axis=1), axis=0)


def edge_rotation(v0, v1, f, moved):
    """max angle (deg) between an edge before and after, over edges >= 1 mm with a moved vertex"""
    e = edges_of(f)
    e = e[moved[e[:, 0]] | moved[e[:, 1]]]
    if not len(e):
        return 0.0
    a, b = v0[e[:, 1]] - v0[e[:, 0]], v1[e[:, 1]] - v1[e[:, 0]]
    na, nb = np.linalg.norm(a, axis=1), np.linalg.norm(b, axis=1)
    ok = (na >= 1.0) & (nb > 1e-9)
    if not ok.any():
        return 0.0
    cs = np.clip((a[ok] * b[ok]).sum(1) / (na[ok] * nb[ok]), -1, 1)
    return float(np.degrees(np.arccos(cs)).max())


def faces_flipped_pct(v0, v1, f, moved):
    fm = f[moved[f].any(1)]
    return round(flipped_pct(v0, v1, fm), 2) if len(fm) else 0.0


def vol(v, f):
    """closed-surface (divergence) volume about the structure's original centroid -- open tubes: indicative only"""
    return round(vol_q213(v, f), 1)


def stats(d):
    n = np.linalg.norm(d, axis=1) if d.ndim == 2 else np.abs(d)
    m = n > 1e-6
    return dict(max_mm=round(float(n.max()), 2) if len(n) else 0.0, mean_moved_mm=round(float(n[m].mean()), 2) if m.any() else 0.0,
                moved_gt0_25mm=int((n > 0.25).sum()))


# ------------------------------------------------------------------ per side
class Side:
    def __init__(self, pg, s, V):
        self.pg, self.s, self.V = pg, s, V
        self.H = pg.H[s]
        self.P = L.Palm(pg, s)
        self.bones = C340.BoneSet(A.bones_of_hand(pg, s))
        self.shell, _ = A.skin_shell(pg, s)
        self.shell_v, self.shell_f = np.asarray(self.shell.vertices), np.asarray(self.shell.faces)
        # the Z hand skin meshes are closed solids (palmar / dorsal halves of the digits, palm, dorsum) that leave a seam at the mid-lateral
        # line, so neither a winding test nor the nearest-face normal says "inside" there.  The test is the skin's OUTER envelope per finger:
        # a point (s, angle, radius in its finger's cross-section) is outside when its radius exceeds the largest skin radius within 3 mm
        # along the finger and 20 deg around it, less 0.3 mm (Side.outside_skin)
        self.Ls = {f: [float(np.linalg.norm(g["b"] - g["a"])) for g in segs] for f, segs in self.H.fingers.items()}
        # palmar direction per finger on a 0.5 mm grid of s, blended across the joints (Gaussian, 3 mm)
        self.pgrid = {}
        for f, segs in self.H.fingers.items():
            Ls = self.Ls[f]
            lo = -Ls[0] - 5 if f == 1 else -60.0
            hi = (sum(Ls[1:]) if f == 1 else sum(Ls)) + 10
            g = np.arange(lo, hi, 0.5)
            k = np.array([self._seg_at(f, x) for x in g])
            p = np.array([segs[i]["p"] for i in k])
            from scipy.ndimage import gaussian_filter1d
            p = gaussian_filter1d(p, 6.0, axis=0, mode="nearest")
            self.pgrid[f] = (g, p / np.linalg.norm(p, axis=1)[:, None])

    def k(self, base):
        return L.sid(self.pg, base, self.s)

    def outside_skin(self, P):
        if not hasattr(self, "_skin"):
            Lk = self.coords(self.shell_v)
            self._skin = {f: (Lk["s"][Lk["finger"] == f], np.arctan2(Lk["radial"], Lk["palmar"])[Lk["finger"] == f],
                              np.hypot(Lk["radial"], Lk["palmar"])[Lk["finger"] == f]) for f in self.H.fingers}
        Lp = self.coords(P)
        th = np.arctan2(Lp["radial"], Lp["palmar"]); rho = np.hypot(Lp["radial"], Lp["palmar"])
        out = np.zeros(len(P), bool)
        for i in range(len(P)):
            s_, t_, r_ = self._skin[int(Lp["finger"][i])]
            dth = np.abs((t_ - th[i] + np.pi) % (2 * np.pi) - np.pi)
            m = (np.abs(s_ - Lp["s"][i]) < 3.0) & (dth < np.radians(20))
            out[i] = bool(m.any() and rho[i] > r_[m].max() - 0.3)
        return out

    def _seg_at(self, f, x):
        Ls = self.Ls[f]
        if f == 1:
            if x < 0:
                return 0
            acc = 0.0
            for i in (1, 2):
                acc += Ls[i]
                if x < acc:
                    return i
            return 2
        acc = 0.0
        for i in range(3):
            acc += Ls[i]
            if x < acc:
                return i
        return 2

    def coords(self, v, fingers=None):
        """finger coordinates: finger, seg, s (mm from the MCP joint along the chain; thumb: from its MCP, the metacarpal negative), palmar,
        radial, dist (Hand.locate; `fingers` restricts it to those fingers' frames)"""
        Lc = self.H.locate(v, fingers)
        S = np.zeros(len(v))
        for i, (f, k, t) in enumerate(zip(Lc["finger"], Lc["seg"], Lc["t"])):
            Ls = self.Ls[f]
            if f == 1:
                S[i] = -(1 - t) * Ls[0] if k == 0 else sum(Ls[1:k]) + t * Ls[k]
            else:
                S[i] = sum(Ls[:k]) + t * Ls[k]
                if k == 0 and t <= 0:
                    S[i] = (v[i] - self.H.fingers[f][0]["a"]) @ self.H.fingers[f][0]["u"]
        Lc["s"] = S
        Lc["side"] = np.where(Lc["radial"] > 0, 1, -1)
        return Lc

    def pdir(self, f, s):
        g, p = self.pgrid[f]
        i = np.clip(np.round((np.asarray(s) - g[0]) / 0.5).astype(int), 0, len(g) - 1)
        return p[i]


# ------------------------------------------------------------------ fingers: measure
def strand_mask(Lc, f, side):
    """every vertex of the mesh components labelled (finger f, side) -- the strand that moves"""
    return (Lc["finger"] == f) & (Lc["side"] == side)


def label_strands(sd: Side, V, F):
    """per connected component of a digital nerve / artery mesh: its finger side = the majority (finger, side) of its in-finger vertices
    (within DMAX mm of the bone axis, distal to the MCP joint); then every vertex of the component is located in THAT finger's frames
    (so a strand never mixes two fingers' fields).  Unlabelled components (fewer than 5 in-finger vertices): finger 0, never moved."""
    n = len(V)
    out = dict(finger=np.zeros(n, int), side=np.zeros(n, int), s=np.zeros(n), palmar=np.zeros(n), radial=np.zeros(n), dist=np.full(n, np.inf),
               seg=np.zeros(n, int), t=np.zeros(n), s_ring=np.zeros(n))
    for comp in HF.mesh_parts(dict(v=V, f=F), 1):
        Lc = sd.coords(V[comp])
        m = (Lc["dist"] < DMAX) & (((Lc["finger"] > 1) & (Lc["s"] > 3)) | ((Lc["finger"] == 1) & (Lc["s"] > 0)))
        if m.sum() < 5:
            continue
        lab, cnt = np.unique(Lc["finger"][m] * 10 + (Lc["side"][m] > 0), return_counts=True)
        f, rad = divmod(int(lab[cnt.argmax()]), 10)
        Lf = sd.coords(V[comp], fingers=[f])
        for k in ("s", "palmar", "radial", "dist", "seg", "t"):
            out[k][comp] = Lf[k]
        c, _, _ = ball_centroids(V[comp], 1.5)
        out["s_ring"][comp] = sd.coords(c, fingers=[f])["s"]
        out["finger"][comp] = f
        out["side"][comp] = 1 if rad else -1
    return out


def centreline(s, pal, rad, grid):
    w = np.exp(-0.5 * ((grid[:, None] - s[None]) / SIGMA) ** 2)
    W = w.sum(1)
    with np.errstate(invalid="ignore", divide="ignore"):
        pc, rc = (w @ pal) / W, (w @ rad) / W
    return pc, rc, W >= 0.3


def hand_root(sd: Side, cur):
    """the hand's common-artery bifurcation level along the fingers: median s of the proper-artery vertices within JOIN of the common
    palmar digital arteries (Z's own division points)"""
    va = cur[sd.k(ARTERY)][0]
    d, _ = cKDTree(cur[sd.k(COMMON_A)][0]).query(va)
    Lc = sd.coords(va)
    m = (d < JOIN) & (Lc["finger"] > 1)
    return float(np.median(Lc["s"][m])) if m.any() else 0.0


def junction_station(sd: Side, cur, keys_self, keys_parent, Lc, mask):
    """max s of a strand's vertices within JOIN of its parent meshes (the unmoved common vessel); None if it touches none"""
    if not mask.any():
        return None
    P = np.vstack([cur[k][0] for k in keys_self])[mask]
    par = [cur[k][0] for k in keys_parent if k]
    if not par:
        return None
    d, _ = cKDTree(np.vstack(par)).query(P)
    j = d < JOIN
    return float(Lc["s"][mask][j].max()) if j.any() else None


def collect(sd: Side, cur, keys):
    V = np.vstack([cur[k][0] for k in keys])
    offs = np.cumsum([0] + [len(cur[k][0]) for k in keys])
    labs = [label_strands(sd, *cur[k]) for k in keys]
    return V, offs, {k: np.concatenate([l[k] for l in labs]) for k in labs[0]}


def measure_pairs(sd: Side, cur):
    kn = [sd.k(b) for b in NERVES]; ka = [sd.k(ARTERY)]
    Vn, on, Ln = collect(sd, cur, kn)
    Va, oa, La = collect(sd, cur, ka)
    s_hand = hand_root(sd, cur)
    out = {}
    for f in range(1, 6):
        for side in (1, -1):
            name = "f%d_%s" % (f, "radial" if side > 0 else "ulnar")
            mn, ma = strand_mask(Ln, f, side), strand_mask(La, f, side)
            if mn.sum() < 6 or ma.sum() < 6:
                out[name] = dict(f=f, side=side, present=False, nerve_vertices=int(mn.sum()), artery_vertices=int(ma.sum()))
                continue
            base = 0.0 if f == 1 else s_hand
            jn = junction_station(sd, cur, kn, [sd.k(b) for b in COMMON_N], Ln, mn)
            ja = junction_station(sd, cur, ka, [sd.k(COMMON_A)], La, ma)
            st_n = max(base, jn) if jn is not None else base
            st_a = max(base, ja) if ja is not None else base
            lo = max(min(Ln["s"][mn].min(), La["s"][ma].min()), -60.0) - 1
            hi = max(Ln["s"][mn].max(), La["s"][ma].max()) + 1
            g = np.arange(np.floor(lo), hi + 0.5, 0.5)
            cn, ca = mn & (Ln["dist"] < DMAX), ma & (La["dist"] < DMAX)      # centreline: the in-hand part of the strand
            pn, rn_, okn = centreline(Ln["s"][cn], Ln["palmar"][cn], Ln["radial"][cn], g)
            pa, ra_, oka = centreline(La["s"][ca], La["palmar"][ca], La["radial"][ca], g)
            ii = lambda s_: np.clip(np.round((s_ - g[0]) / 0.5).astype(int), 0, len(g) - 1)
            Rn = float(np.percentile(np.hypot(Ln["palmar"][cn] - pn[ii(Ln["s"][cn])], Ln["radial"][cn] - rn_[ii(Ln["s"][cn])]), 90))
            Ra = float(np.percentile(np.hypot(La["palmar"][ca] - pa[ii(La["s"][ca])], La["radial"][ca] - ra_[ii(La["s"][ca])]), 90))
            both = okn & oka
            delta = pn - pa
            dr = rn_ - ra_
            mreq = np.maximum(M_MIN, np.sqrt(np.maximum(0, (Rn + Ra + GAP) ** 2 - dr ** 2)))
            s_req = max(st_n, st_a) + ZONE
            reg = both & (g >= s_req)
            prox = both & (g < min(st_n, st_a))
            out[name] = dict(f=f, side=side, present=True, nerve_vertices=int(mn.sum()), artery_vertices=int(ma.sum()),
                             root_nerve_s=round(st_n, 1), root_artery_s=round(st_a, 1), hand_root_s=round(s_hand, 1), requirement_from_s=round(s_req, 1),
                             radius_nerve=round(Rn, 2), radius_artery=round(Ra, 2),
                             grid=g, delta=delta, dr=dr, mreq=mreq, reg=reg, both=both, prox=prox, mn=mn, ma=ma)
            out[name].update(order_numbers(out[name], delta))
    return out, (kn, ka, on, oa)


def order_numbers(p, delta):
    """signed nerve - artery palmar offsets (mm, + = nerve palmar): distal of the root zone (rule: >= 0) and proximal of the root"""
    g, reg, prox, both = p["grid"], p["reg"], p["prox"], p["both"]
    r = {}
    if reg.any():
        d = delta[reg]
        r["distal_delta_min_med_max"] = [round(float(d.min()), 1), round(float(np.median(d)), 1), round(float(d.max()), 1)]
        r["distal_order_right_pct"] = round(100 * float((d >= 0).mean()), 1)
        r["distal_order_with_clearance_pct"] = round(100 * float((d >= p["mreq"][reg] - 1e-6).mean()), 1)
        r["distal_s_range"] = [round(float(g[reg].min()), 1), round(float(g[reg].max()), 1)]
    else:
        r["distal_order_right_pct"] = None
    if prox.any():
        d = delta[prox]
        r["proximal_delta_min_med_max"] = [round(float(d.min()), 1), round(float(np.median(d)), 1), round(float(d.max()), 1)]
    zone = both & (g >= min(p["root_nerve_s"], p["root_artery_s"])) & (g < p["requirement_from_s"])
    sgn = np.sign(delta)
    cr = [float(g[i + 1]) for i in range(len(g) - 1) if both[i] and both[i + 1] and sgn[i] < 0 <= sgn[i + 1]]
    r["crossings_s"] = [round(c, 1) for c in cr]
    r["delta_profile_5mm"] = {str(int(x)): round(float(delta[i]), 1) for i, x in enumerate(g) if both[i] and abs(x / 5 - round(x / 5)) < 1e-6}
    return r


def palm_webs(sd: Side, cur):
    """in the palm (proximal to the MCP line): common digital nerve height minus common digital artery height above the metacarpal plane,
    per web (nerves + arteries within 5 mm of the web line in r), 5 mm bins along the hand -- rule: < 0 (nerve deep)"""
    P, H = sd.P, sd.H
    mcp = {f: P.trh(H.fingers[f][0]["a"][None])[0] for f in range(2, 6)}
    rw = {"1-2": mcp[2][1] + (mcp[2][1] - mcp[3][1]) / 2, "2-3": (mcp[2][1] + mcp[3][1]) / 2, "3-4": (mcp[3][1] + mcp[4][1]) / 2,
          "4-5": (mcp[4][1] + mcp[5][1]) / 2}
    tmcp = max(m[0] for m in mcp.values())
    Xn = P.trh(np.vstack([cur[sd.k(b)][0] for b in COMMON_N]))
    Xa = P.trh(cur[sd.k(COMMON_A)][0])
    out = {}
    for k, r0 in rw.items():
        vals = []
        for t0 in np.arange(-50, tmcp, 5):
            a = (np.abs(Xn[:, 1] - r0) < 5) & (Xn[:, 0] >= t0) & (Xn[:, 0] < t0 + 5)
            b = (np.abs(Xa[:, 1] - r0) < 5) & (Xa[:, 0] >= t0) & (Xa[:, 0] < t0 + 5)
            if a.sum() >= 2 and b.sum() >= 2:
                vals.append((float(t0), float(Xn[a, 2].mean() - Xa[b, 2].mean())))
        if vals:
            d = np.array([v for _, v in vals])
            out[k] = dict(bins=len(vals), nerve_minus_artery_min_med_max=[round(float(d.min()), 1), round(float(np.median(d)), 1), round(float(d.max()), 1)],
                          nerve_deep_pct=round(100 * float((d < 0).mean()), 1))
    return out


# ------------------------------------------------------------------ fingers: plan + apply
def envelope(T, g, k):
    """smallest function >= T with slope <= k (upper Lipschitz envelope on the grid)"""
    E = T.copy()
    for i in range(1, len(E)):
        E[i] = max(E[i], E[i - 1] - k * (g[i] - g[i - 1]))
    for i in range(len(E) - 2, -1, -1):
        E[i] = max(E[i], E[i + 1] - k * (g[i + 1] - g[i]))
    return E


_SX = np.linspace(0, 1, 2001)


def plan_pair(p, lam):
    """the relative move c(s) = D(s) * smoothstep((s - a) / W): D = upper envelope (slope K_ENV) of the shortfall distal of the root zone;
    the ramp (a, W) lies inside the root zone [root, root + ZONE] and is placed so the nerve passes the artery (c = -delta) at the station
    of the zone where the two strands are farthest apart radially (they pass side by side there, not through each other)."""
    g = p["grid"]
    root, s_req = max(p["root_nerve_s"], p["root_artery_s"]), p["requirement_from_s"]
    T = np.where(p["reg"], np.maximum(0, p["mreq"] - p["delta"]), 0.0)
    D = envelope(T, g, K_ENV)
    z = p["both"] & (g >= root) & (g <= s_req)
    a, W, s_x, i = root, s_req - root, None, 0
    if z.any() and T.max() > 0:
        best = None
        for i in np.where(z)[0]:                 # candidate crossing stations whose ramp fits the zone with at least W_MIN mm
            q = float(np.clip(-p["delta"][i] / max(D[i], 1e-6), 0.02, 0.98))
            u = float(np.interp(q, smoothstep(_SX), _SX))
            Wi = min((g[i] - root) / u, (s_req - g[i]) / (1 - u))
            if Wi >= W_MIN and (best is None or abs(p["dr"][i]) > abs(p["dr"][best[0]])):
                best = (i, u, Wi)
        if best is not None:
            i, u, W = best; s_x = float(g[i])
            a = s_x - u * W
    c = D * smoothstep((g - a) / max(W, 1e-3))
    return dict(lam=lam, need_max_mm=round(float(T.max()), 2), dn=lam * c, da=(1 - lam) * c, delta_after=p["delta"] + c,
                ramp_mm=[round(float(a), 1), round(float(a + W), 1)], crossing_planned_s=None if s_x is None else round(s_x, 1),
                radial_separation_at_crossing_mm=None if s_x is None else round(float(abs(p["dr"][i])), 2),
                tube_contact_mm=round(p["radius_nerve"] + p["radius_artery"], 2))


def pair_displacements(sd: Side, p, plan, Ln, La):
    """per-vertex displacement of the pair's nerve and artery vertices (along the blended palmar direction at each vertex's s)"""
    g = p["grid"]
    ii = lambda s_: np.clip(np.round((s_ - g[0]) / 0.5).astype(int), 0, len(g) - 1)
    Dn = np.zeros((len(Ln["s"]), 3)); Da = np.zeros((len(La["s"]), 3))
    mn, ma = p["mn"], p["ma"]
    # evaluated at each vertex's cross-section centre (s_ring), so a ring moves as one
    Dn[mn] = plan["dn"][ii(Ln["s_ring"][mn])][:, None] * sd.pdir(p["f"], Ln["s_ring"][mn])
    Da[ma] = -plan["da"][ii(La["s_ring"][ma])][:, None] * sd.pdir(p["f"], La["s_ring"][ma])
    return Dn, Da


def centre_bend(s, V0, V1):
    """max angle (deg) between the strand's centreline tangent before and after (kernel centreline over s, tangent over +-1 mm)"""
    if len(s) < 6:
        return 0.0
    g = np.arange(s.min(), s.max() + 0.5, 0.5)
    w = np.exp(-0.5 * ((g[:, None] - s[None]) / SIGMA) ** 2); W = w.sum(1); ok = W >= 0.3
    C0, C1 = (w @ V0) / W[:, None], (w @ V1) / W[:, None]
    T0, T1 = C0[4:] - C0[:-4], C1[4:] - C1[:-4]
    ok = ok[4:] & ok[:-4] & (np.linalg.norm(T0, axis=1) > 0.2)
    if not ok.any():
        return 0.0
    cs = np.clip((T0[ok] * T1[ok]).sum(1) / (np.linalg.norm(T0[ok], axis=1) * np.linalg.norm(T1[ok], axis=1)), -1, 1)
    return float(np.degrees(np.arccos(cs)).max())


def group_inside(sd: Side, cur, P, groups, skip=()):
    """per group: boolean inside mask of points P"""
    out = {}
    for g, bases in groups.items():
        m = np.zeros(len(P), bool)
        for b in bases:
            k = sd.k(b)
            if k and k in cur and k not in skip:
                m |= np.abs(winding(P, *cur[k])) > 0.5
        out[g] = m
    s, _, _ = sd.bones.signed(P)
    out["hand bones"] = s > 0.0
    out["outside the skin"] = sd.outside_skin(P)
    return out


def guard_counts(m0, m1, moved):
    """[before, after, new entrants that moved > 0.25 mm]; fails when after > before with a new entrant"""
    res, fails = {}, []
    for g in m0:
        new = int((m1[g] & ~m0[g] & moved).sum())
        b, a = int(m0[g].sum()), int(m1[g].sum())
        if b or a or new:
            res[g] = [b, a, new]
        if a > b and new > 0:
            fails.append(g)
    return res, fails


def r1_palmar(sd: Side, v, mask):
    """median palmar offset of the in-finger part of a strand (the Q338 R1 statistic, its own finger frames)"""
    Lc = sd.coords(v[mask])
    m = (Lc["t"] > 0.02) & (Lc["t"] < 0.98) & ((Lc["finger"] > 1) | (Lc["seg"] > 0))
    return float(np.median(Lc["palmar"][m])) if m.any() else None


def try_pair(sd: Side, cur, p, ctx):
    kn, ka, on, oa = ctx
    Vn, _, Ln = collect(sd, cur, kn)
    Va, _, La = collect(sd, cur, ka)
    tries = []
    for lam in LAMS:
        plan = plan_pair(p, lam)
        if plan["need_max_mm"] <= 1e-6:
            return dict(ships=False, reason="order already right distal of the root zone", tries=[]), None
        Dn, Da = pair_displacements(sd, p, plan, Ln, La)
        dmax = max(np.linalg.norm(Dn, axis=1).max(), np.linalg.norm(Da, axis=1).max())
        t = dict(lam=lam, need_max_mm=plan["need_max_mm"], move_max_mm=round(float(dmax), 2), fails=[])
        if dmax > CAP + 1e-6:
            t["fails"].append("move %.2f mm > cap %.1f mm" % (dmax, CAP))
            tries.append(t); continue
        new = dict(cur)
        for i, k in enumerate(kn):
            new[k] = (cur[k][0] + Dn[on[i]:on[i + 1]], cur[k][1])
        new[ka[0]] = (Va + Da, cur[ka[0]][1])
        # penetration: the pair's moved vertices, before / after
        Pn0, Pa0 = Vn[p["mn"]], Va[p["ma"]]
        Pn1, Pa1 = Pn0 + Dn[p["mn"]], Pa0 + Da[p["ma"]]
        mvn = np.linalg.norm(Dn[p["mn"]], axis=1) > 0.25; mva = np.linalg.norm(Da[p["ma"]], axis=1) > 0.25
        g0n = group_inside(sd, cur, Pn0, GROUPS); g1n = group_inside(sd, new, Pn1, GROUPS)
        g0a = group_inside(sd, cur, Pa0, GROUPS, skip=(ka[0],)); g1a = group_inside(sd, new, Pa1, GROUPS, skip=(ka[0],))
        g0n["nerve inside artery"] = np.abs(winding(Pn0, *cur[ka[0]])) > 0.5
        g1n["nerve inside artery"] = np.abs(winding(Pn1, *new[ka[0]])) > 0.5
        g0a["artery inside nerve"] = np.zeros(len(Pa0), bool); g1a["artery inside nerve"] = np.zeros(len(Pa1), bool)
        for k in kn:
            g0a["artery inside nerve"] |= np.abs(winding(Pa0, *cur[k])) > 0.5
            g1a["artery inside nerve"] |= np.abs(winding(Pa1, *new[k])) > 0.5
        rn, fn = guard_counts(g0n, g1n, mvn); ra, fa = guard_counts(g0a, g1a, mva)
        t["penetration_nerve"] = rn; t["penetration_artery"] = ra
        t["fails"] += ["nerve: " + x for x in fn] + ["artery: " + x for x in fa]
        # triangles + bends
        tri = {}
        for i, k in enumerate(kn + ka):
            v0, f = cur[k]; v1 = new[k][0]
            mv = np.linalg.norm(v1 - v0, axis=1) > 1e-6
            if not mv.any():
                continue
            fp = faces_flipped_pct(v0, v1, f, mv)
            st = [round(stretched_pct(v0, v0, f), 1), round(stretched_pct(v0, v1, f), 1)]
            rot = edge_rotation(v0, v1, f, mv)
            tri[k] = dict(flipped_pct=fp, stretched_pct=st, max_edge_rotation_deg=round(rot, 1))
            if fp > 0.5:
                t["fails"].append("%s: flipped %.2f %%" % (k, fp))
            if st[1] > st[0] + 12.0:
                t["fails"].append("%s: stretched %s" % (k, st))
        t["triangles"] = tri
        cn, ca = p["mn"] & (Ln["dist"] < DMAX), p["ma"] & (La["dist"] < DMAX)
        t["bend_deg"] = dict(nerve=round(centre_bend(Ln["s"][cn], Vn[cn], Vn[cn] + Dn[cn]), 1), artery=round(centre_bend(La["s"][ca], Va[ca], Va[ca] + Da[ca]), 1))
        for w_, b_ in t["bend_deg"].items():
            if b_ > BEND_MAX:
                t["fails"].append("%s centreline bend %.1f deg > %.0f" % (w_, b_, BEND_MAX))
        t.update({k_: plan[k_] for k_ in ("ramp_mm", "crossing_planned_s", "radial_separation_at_crossing_mm", "tube_contact_mm")})
        r1 = r1_palmar(sd, Va + Da, p["ma"])
        t["artery_R1_palmar_after_mm"] = None if r1 is None else round(r1, 2)
        if r1 is not None and r1 < -1.0:
            t["fails"].append("artery strand median palmar offset %.2f < -1.0 mm (Q338 R1)" % r1)
        tries.append(t)
        if not t["fails"]:
            after = plan["delta_after"]
            res = dict(ships=True, lam=lam, tries=tries, need_max_mm=plan["need_max_mm"],
                       nerve_move=stats(Dn[p["mn"]]), artery_move=stats(Da[p["ma"]]))
            res["meshes_moved"] = [k for k in kn + ka if np.abs(new[k][0] - cur[k][0]).max() > 1e-6]
            res.update({"planned_after_" + k: v for k, v in order_numbers(p, after).items() if k != "delta_profile_5mm"})
            return res, new
    return dict(ships=False, reason="no share passes every guard", tries=tries), None


# ------------------------------------------------------------------ venous arch
def venous_layers(sd: Side, cur):
    """centroid heights (palm frame): venous minus nearest-arterial-arch centroid; in-plane separation"""
    P = sd.P
    cv, rv, _ = ball_centroids(cur[sd.k(VARCH)][0]); ca, ra, _ = ball_centroids(cur[sd.k(ARCH)][0])
    Cv, Ca = P.trh(cv), P.trh(ca)
    D, i = cKDTree(Ca[:, :2]).query(Cv[:, :2])
    dh = Cv[:, 2] - Ca[i, 2]
    return dict(venous_minus_arterial_h_p5_p50_p95=[round(float(x), 1) for x in np.percentile(dh, [5, 50, 95])],
                in_plane_separation_p5_p50_p95=[round(float(x), 1) for x in np.percentile(D, [5, 50, 95])],
                radius_arterial=round(float(np.median(ra)), 2), radius_venous=round(float(np.median(rv)), 2))


def plan_venous(sd: Side, cur):
    P = sd.P
    kv, kd, ka = sd.k(VARCH), sd.k(DVEINS), sd.k(ARCH)
    vv, fv = cur[kv]; vd, fd = cur[kd]
    cv, rv, nbv = ball_centroids(vv); ca, ra, _ = ball_centroids(cur[ka][0])
    Rv, Ra = float(np.median(rv)), float(np.median(ra))
    Cv, Ca = P.trh(cv), P.trh(ca)
    D, i = cKDTree(Ca[:, :2]).query(Cv[:, :2])
    target = Ca[i, 2] - np.sqrt(np.maximum(0, (Ra + Rv + GAP) ** 2 - D ** 2))
    req_v = np.maximum(0, target - Cv[:, 2])
    nv = len(vv)
    # the palmar digital veins: their palm part follows (tapered), their in-finger part is held (as Q340 HOLD_IN_FINGERS)
    Lc = sd.H.locate(vd)
    hold_d = (Lc["finger"] == 1) | ((Lc["dist"] < 15) & ((Lc["seg"] > 0) | (Lc["t"] > 0.0)))
    Vall = np.vstack([vv, vd]); n = len(Vall)
    E = np.vstack([edges_of(fv), edges_of(fd) + nv])
    link = cKDTree(vv).query_ball_tree(cKDTree(vd), JOIN)
    LE = np.array([(a, nv + b) for a, bs in enumerate(link) for b in bs], int).reshape(-1, 2)
    E = np.vstack([E, LE]) if len(LE) else E
    w = np.linalg.norm(Vall[E[:, 0]] - Vall[E[:, 1]], axis=1) + 1e-6
    G = sparse.coo_matrix((w, (E[:, 0], E[:, 1])), shape=(n, n)).tocsr()
    G = G.maximum(G.T)
    anchors = np.zeros(n, bool); anchors[nv:][hold_d] = True
    anchor_rep = {}
    for pb in VPARTNERS:
        pk = sd.k(pb)
        if pk and pk in cur:
            d, _ = cKDTree(cur[pk][0]).query(vv)
            a = d < JOIN
            anchors[:nv] |= a
            anchor_rep[pk] = int(a.sum())
    req = np.zeros(n); req[:nv] = req_v
    k = np.tan(np.radians(BEND_MAX)) * 0.9
    src = np.where(req > 0.05)[0]
    Lf = np.zeros(n)
    if len(src):
        Dg = csgraph.dijkstra(G, indices=src)
        Lf = np.maximum(0, (req[src][:, None] - k * Dg).max(0))
    if anchors.any():
        da = csgraph.dijkstra(G, indices=np.where(anchors)[0], min_only=True)
        Lf = np.minimum(Lf, k * np.where(np.isfinite(da), da, 1e9))
    # per cross-section: the mean over the ball (the ring moves together)
    Lv = np.array([Lf[:nv][nb].mean() for nb in nbv])
    nbd = cKDTree(vd).query_ball_point(vd, XS)
    Ld = np.array([Lf[nv:][nb].mean() for nb in nbd])
    Ld[hold_d] = 0.0
    shortfall = req_v - Lv
    return dict(Lv=Lv, Ld=Ld, req=req_v, anchors=anchor_rep, held_digital_vein_vertices=int(hold_d.sum()),
                slope=round(k, 3), Rv=Rv, Ra=Ra, shortfall=shortfall, D=D)


def try_venous(sd: Side, cur):
    kv, kd = sd.k(VARCH), sd.k(DVEINS)
    pl = plan_venous(sd, cur)
    n = sd.P.n
    vv, fv = cur[kv]; vd, fd = cur[kd]
    Dv = np.outer(pl["Lv"], n); Dd = np.outer(pl["Ld"], n)
    rep = dict(required_lift=stats(pl["req"]), lift_venous_arch=stats(Dv), lift_digital_veins=stats(Dd), anchors=pl["anchors"],
               held_digital_vein_vertices=pl["held_digital_vein_vertices"], slope_mm_per_mm=pl["slope"],
               shortfall_gt0_5mm_vertices=int((pl["shortfall"] > 0.5).sum()), shortfall_max_mm=round(float(pl["shortfall"].max()), 2), fails=[])
    mx = max(np.abs(pl["Lv"]).max(), np.abs(pl["Ld"]).max())
    if mx > CAP_V + 1e-6:
        rep["fails"].append("lift %.2f mm > cap %.1f mm" % (mx, CAP_V))
    new = dict(cur); new[kv] = (vv + Dv, fv); new[kd] = (vd + Dd, fd)
    pen = {}
    for k, V0, Dk in ((kv, vv, Dv), (kd, vd, Dd)):
        mv = np.linalg.norm(Dk, axis=1) > 0.25
        if not mv.any():
            continue
        m0 = group_inside(sd, cur, V0, GROUPS_V); m1 = group_inside(sd, new, V0 + Dk, GROUPS_V)
        X0, X1 = sd.P.trh(V0), sd.P.trh(V0 + Dk)
        Hr = C340.Side(sd.pg, sd.s, cur).hmap(["palmar_aponeurosis"], cur)
        if Hr is not None:
            for X, mm in ((X0, m0), (X1, m1)):
                _, bot = Hr.at(X)
                mm["above the palmar aponeurosis"] = np.isfinite(bot) & (X[:, 2] > bot + 0.3) & (X[:, 0] <= max(sd.P.mc_t[4:]) + 5.0)
        r, fails = guard_counts(m0, m1, mv)
        pen[k] = r
        rep["fails"] += ["%s: %s" % (k, x) for x in fails]
    rep["penetration_before_after_new"] = pen
    tri = {}
    for k in (kv, kd):
        v0, f = cur[k]; v1 = new[k][0]
        mv = np.linalg.norm(v1 - v0, axis=1) > 1e-6
        if not mv.any():
            continue
        fp = faces_flipped_pct(v0, v1, f, mv); st = [round(stretched_pct(v0, v0, f), 1), round(stretched_pct(v0, v1, f), 1)]
        rot = edge_rotation(v0, v1, f, mv)
        tri[k] = dict(flipped_pct=fp, stretched_pct=st, max_edge_rotation_deg=round(rot, 1))
        if fp > 0.5:
            rep["fails"].append("%s: flipped %.2f %%" % (k, fp))
        if st[1] > st[0] + 12.0:
            rep["fails"].append("%s: stretched %s" % (k, st))
        if rot > BEND_MAX:
            rep["fails"].append("%s: bend %.1f deg > %.0f" % (k, rot, BEND_MAX))
    rep["triangles"] = tri
    rep["layers_after_if_shipped"] = venous_layers(sd, new)
    rep["ships"] = not rep["fails"]
    return rep, new


# ------------------------------------------------------------------ side driver
def strip(p):
    return {k: v for k, v in p.items() if not isinstance(v, np.ndarray)}


def run_side(pg, s, V, log, deny=frozenset()):
    sd = Side(pg, s, V)
    cur0 = dict(V); cur = dict(V)
    rep = {"side": s}
    pairs, ctx = measure_pairs(sd, cur0)
    rep["pairs_before"] = {n: strip(p) for n, p in pairs.items()}
    rep["palm_webs_before"] = palm_webs(sd, cur0)
    c3 = C340.Side(pg, s, cur0)
    rep["venous_before"] = dict(venous_layers(sd, cur0), palm_depth=C340.palm_depth(c3, cur0))
    rep["pairs"] = {}
    for name, p in pairs.items():
        if not p["present"]:
            rep["pairs"][name] = dict(ships=False, reason="no nerve / artery pair on this finger side (%d / %d vertices)" % (p["nerve_vertices"], p["artery_vertices"]))
            continue
        # re-measure on the current geometry (earlier pairs may have moved shared meshes; their vertex sets are disjoint)
        pp, _ = measure_pairs(sd, cur)
        r, new = try_pair(sd, cur, pp[name], ctx)
        if r["ships"] and name in deny:
            r["ships"] = False; r["denied"] = "the other hand fails its guards (left and right are kept mirror images)"
        rep["pairs"][name] = r
        if r["ships"]:
            cur = new
        last = r["tries"][-1] if r.get("tries") else {}
        log("  %s %s: need %s mm -> %s%s" % (s, name, r.get("need_max_mm", last.get("need_max_mm", 0)),
                                            ("SHIPS lam %.2f, nerve max %.2f / artery max %.2f mm" % (r["lam"], r["nerve_move"]["max_mm"], r["artery_move"]["max_mm"]))
                                            if r["ships"] else "KEPT (%s)" % (r.get("denied") or r.get("reason")),
                                            "" if r["ships"] or not last else "; last try: " + "; ".join(last.get("fails", []))))
    # venous arch
    vr, vnew = try_venous(sd, cur)
    if vr["ships"] and "venous" in deny:
        vr["ships"] = False; vr["denied"] = "the other hand fails its guards (left and right are kept mirror images)"
    rep["venous"] = vr
    if vr["ships"]:
        cur = vnew
    log("  %s venous arch: required lift max %s mm, lift max %s mm, shortfall max %s mm -> %s%s" % (
        s, vr["required_lift"]["max_mm"], vr["lift_venous_arch"]["max_mm"], vr["shortfall_max_mm"], "SHIPS" if vr["ships"] else "KEPT",
        "" if vr["ships"] else " (" + (vr.get("denied") or "; ".join(vr["fails"])) + ")"))
    # after
    pa, _ = measure_pairs(sd, cur)
    rep["pairs_after"] = {n: strip(p) for n, p in pa.items()}
    rep["palm_webs_after"] = palm_webs(sd, cur)
    rep["venous_after"] = dict(venous_layers(sd, cur), palm_depth=C340.palm_depth(C340.Side(pg, s, cur), cur))
    rep["structures"] = {}
    changed = {}
    for k in sorted(set(cur) | set(cur0)):
        v0, f = cur0[k]; v1 = cur[k][0]
        if np.abs(v1 - v0).max() < 1e-6:
            continue
        mv = np.linalg.norm(v1 - v0, axis=1) > 1e-6
        rep["structures"][k] = dict(displacement=stats(v1 - v0), volume_before=vol(v0 - v0.mean(0), f), volume_after=vol(v1 - v0.mean(0), f),
                                    flipped_pct_moved_faces=faces_flipped_pct(v0, v1, f, mv),
                                    stretched_pct=[round(stretched_pct(v0, v0, f), 1), round(stretched_pct(v0, v1, f), 1)],
                                    max_edge_rotation_deg=round(edge_rotation(v0, v1, f, mv), 1), vertices=len(v0), faces=len(f))
        changed[k] = v1
    return rep, changed


def note_for(k, rep_side):
    st = rep_side["structures"][k]["displacement"]
    if VARCH in k or DVEINS in k:
        vr = rep_side["venous"]
        what = ("moved palmarward along the normal of the metacarpal plane to the depth of the superficial palmar arterial arch (in contact "
                "under it where the two overlap in plan), held at zero at its junctions with the ulnar veins and the median antebrachial vein"
                if VARCH in k else "its palm segments follow the superficial venous arch they open into, tapered to zero toward the in-finger part")
        return (f"{TAG} {what}, because the Z-Anatomy source put the venous arch about 9 mm deep to the arterial arch, on the carpus and deep "
                f"to the flexor tendons, and the superficial palmar venous arch is the venae comitantes of the superficial palmar arterial arch "
                f"({SRC_F2}); rule-based lift, max {st['max_mm']} mm (cap {CAP_V:g} mm), shortfall max {vr['shortfall_max_mm']} mm; the shape and "
                f"mesh are the source's (vertex / triangle counts unchanged).")
    moved = [n for n, r in rep_side["pairs"].items() if r.get("ships") and k in r.get("meshes_moved", [])]
    who = "nerve" if "nerve" in k else "artery"
    dirn = "palmarward" if who == "nerve" else "dorsalward"
    return (f"{TAG} in the fingers ({', '.join(moved)}) moved {dirn} along each phalanx's palmar direction so that the proper palmar digital "
            f"nerve lies palmar to the proper palmar digital artery distal to the finger root, crossing in the first {ZONE:g} mm distal to "
            f"the root (the source had the nerve dorsal to the artery there); in the palm the nerve stays deep to the artery ({SRC_F1}); "
            f"rule-based, each cross-section moved rigidly, zero at the finger root (the junction with the common digital {who}; thumb: its MCP "
            f"joint), max {st['max_mm']} mm "
            f"(cap {CAP:g} mm); the shape and mesh are the source's (vertex / triangle counts unchanged).")


# ------------------------------------------------------------------ write (as conform_palm_q340.write_page, originals kept as *.q349)
def write_page(d: Path, stem, man_old, man_new, blob_new, old_files):
    B = C340.B
    pages = C340.pages_of(d, stem)
    texts = {p: p.read_text(encoding="utf-8") for p in pages}
    for p, t in texts.items():
        assert C340.LIT["manifest"].search(t).group(1) == C340.ser_manifest(man_old), f"{p}: manifest serialisation differs"
        assert C340.LIT["files"].search(t).group(1) == json.dumps(old_files), f"{p}: file list serialisation differs"
    chunks = B.split_blob(blob_new, stem)
    assert [n for n, _ in chunks] == [f["path"] for f in old_files], "geo file set would change; not handled"
    files = [{"path": n, "bytes": len(c), "enc": "base64"} for n, c in chunks]
    changed = []
    for n, c in chunks:
        p = d / n; new = base64_b(c)
        if p.read_bytes() != new:
            bk = p.with_name(p.name + ".q349")
            if not bk.exists():
                shutil.copy2(p, bk)
            p.write_bytes(new); changed.append(n)
    for p, t in texts.items():
        bk = p.with_name(p.name + ".q349")
        if not bk.exists():
            shutil.copy2(p, bk)
        t2 = C340.LIT["manifest"].sub(lambda _m: "window.__ANATOMY_MANIFEST__=" + C340.ser_manifest(man_new) + ";", t, count=1)
        t2 = C340.LIT["files"].sub(lambda _m: "window.__ANATOMY_BIN_FILES__=" + json.dumps(files) + ";", t2, count=1)
        p.write_text(t2, encoding="utf-8"); changed.append(p.name)
    return changed


def base64_b(c):
    import base64
    return base64.b64encode(c)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--page-dir", required=True)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--json", default=str(OUT))
    a = ap.parse_args(argv)
    d = Path(a.page_dir).resolve()
    stem = C340.stem_of(d)
    man, blob, files = C340.read_page(d, stem)
    done = [m["id"] for m in man["meshes"] if TAG in ((m.get("rec") or {}).get("procedural_badge") or "")]
    if done:
        print(f"Q349 already applied to this page ({len(done)} structures carry the Q349 note, e.g. {done[0]}); nothing done")
        return 0
    pg = A.Page(str(d))
    V = {m["id"]: C340.dec(m, blob) for m in man["meshes"]}
    for x in pg.M.S:
        if x["id"] in V and len(x["v"]) == len(V[x["id"]][0]):
            assert np.abs(x["v"] - V[x["id"]][0]).max() < 1e-3, x["id"]
    rep = {"schema": "nmsk.q349.fingers.v1", "round": "Q349", "generated": time.strftime("%Y-%m-%d"), "page_dir": str(d), "page": stem,
           "written": bool(a.write),
           "parameters": dict(sigma_mm=SIGMA, root_zone_mm=ZONE, min_order_mm=M_MIN, tube_gap_mm=GAP, envelope_slope=K_ENV, cap_mm=CAP,
                              venous_cap_mm=CAP_V, bend_max_deg=BEND_MAX, shares_tried=list(LAMS), cross_section_ball_mm=XS, junction_mm=JOIN,
                              nerves=NERVES, artery=ARTERY, guard_groups=GROUPS, venous_guard_groups=GROUPS_V, venous_partners=VPARTNERS),
           "sources": [MANNAN + ": " + SRC_F1 + " (F1 finger nerve / artery order)", MANNAN + ": " + SRC_F2 + " (F2 venous arch = venae comitantes)"],
           "rule_based": True, "sides": {}}
    recs = {m["id"]: m.get("rec") for m in man["meshes"]}
    # a pair / the venous arch ships only if it passes on BOTH hands; repeated until the set is stable (a pair left on one hand changes
    # the geometry the next pairs of that hand are guarded against)
    deny = set()
    for _ in range(4):
        ships = {}
        for s in ("r", "l"):
            r, _ = run_side(pg, s, V, lambda *_: None, frozenset(deny))
            ships[s] = {n for n, x in r["pairs"].items() if x.get("ships")} | ({"venous"} if r["venous"]["ships"] else set())
        names = set(r["pairs"]) | {"venous"}
        new = deny | (names - (ships["r"] & ships["l"]))
        if new == deny and ships["r"] == ships["l"]:
            break
        deny = new
    rep["denied_both_sides"] = sorted(deny)
    replace = {}
    for s in ("r", "l"):
        print(f"-- side {s}")
        r, out = run_side(pg, s, V, print, frozenset(deny))
        rep["sides"][s] = r
        for k, v in out.items():
            replace[k] = (v, V[k][1], C340.badge_add(recs[k], note_for(k, r)))
            r["structures"][k]["card"] = replace[k][2]["procedural_badge"]
    rep["geometry_changed"] = sorted(replace)
    man2, blob2 = C340.repack(man, blob, replace)
    for m0, m1 in zip(man["meshes"], man2["meshes"]):
        assert m0["id"] == m1["id"] and m0["vc"] == m1["vc"] and m0["ic"] == m1["ic"]
    assert len(blob2) == len(blob)
    if a.write and replace:
        rep["files_changed"] = write_page(d, stem, man, man2, blob2, files)
        print("  wrote: " + ", ".join(rep["files_changed"]) + " (originals kept as *.q349)")
    jp = Path(a.json)
    allr = json.loads(jp.read_text(encoding="utf-8")) if jp.exists() else {}
    if allr.get("schema") != "nmsk.q349.fingers_report.v1":
        allr = {"schema": "nmsk.q349.fingers_report.v1", "pages": {}}
    allr["pages"][stem] = rep
    jp.parent.mkdir(parents=True, exist_ok=True)
    jp.write_text(json.dumps(allr, indent=1, default=lambda o: o.tolist() if isinstance(o, np.ndarray) else (float(o) if isinstance(o, np.floating) else str(o))),
                  encoding="utf-8")
    print(f"Q349 {'WRITTEN' if a.write else 'DRY RUN'}: {len(replace)} structures changed -> {jp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
