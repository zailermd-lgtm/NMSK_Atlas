#!/usr/bin/env python3
"""Q398: finish Q394 -- refit what still lies outside the skin at rest (Base · Male / Base · Female).

    python3 scripts/anatomy/q398/refit_q398.py --page-dir DIR [--json REP] [--cache DIR]             # dry run
    python3 scripts/anatomy/q398/refit_q398.py --page-dir DIR --write [--allow-build]                # write DIR (originals *.q398)

The test is Q394's (scripts/anatomy/q394/under_skin_q394.py: Q353 outside test, every vertex, ray-parity confirmed). Three steps,
in this order, each rule-based and deterministic:

 1. STRUCTURE REFIT, depth remap (replaces Q394's envelope tuck where that failed). A structure's vertex x has a depth d(x) under
    the skin's inner sheet (signed, along the inner sheet's normal, + = deeper). Every vertex that is outside, or inside the skin
    slab, needs e = GAP - d (GAP 0.3 mm, Q353). E(x) = max_j (e_j - K |x - x_j|)+ (Lipschitz envelope, no kink) and the
    Gaussian-weighted mean of the inner normals of the requirements give amplitude and direction. The column of the structure
    under x is remapped monotonically: depths [L, D] -> [GAP, D] with L = GAP - E, i.e. a vertex moves by
        u = E * clamp((D - d) / (D - L), 0, 1)        (du/dd > -1: no two vertices of a column change order: no fold)
    D is where the remap stops:
      shell     (fat / unlabelled soft-tissue compartments, Q295: a shell between the skin and the muscle layer) D = the
                compartment's own deepest depth within R_SHELL mm -- its deep face stays where it is, the compartment is rebuilt
                between the skin's inner sheet and that face, i.e. made THINNER there (local thickness ratio reported);
      solid     (everything else: muscle, nerve, vessel, ligament, capsule, fascia...) D = own deepest depth + 2E + 2 mm -- close to
                a translation inward, the shape kept.
    Bones are never moved; a vertex the move would put into a bone keeps its place, the move fading in over 3 mm (Q394
    bone_yield). Guards per structure (else NOT FIXED, bytes kept): move <= CAP (solid) / CAP_SHELL (shell); 0 outside after;
    flipped <= FLIP_MAX % of moved faces; no vertex newly in bone; solid: volume (closed) / area (open) change <= VOL_MAX %;
    shell: volume / area change recorded, <= VOL_MAX_SHELL %.
 2. SKIN OFFSET (owner's delegate, 2026-11-25: only where the page skin is demonstrably thinner / closer than what it must cover
    because of the source fit -- toes, fingers / finger tips, lips / philtrum, perineal patch borders: Q394 cause class (d)).
    What step 1 could not fix and lies under one of SKIN_REGIONS, or anywhere under skin thinner than THIN_MM (Q394's class (d)
    rule, per vertex), needs the skin's inner sheet GAP mm above it: r = GAP - d,
    capped at SKIN_MAX (4 mm). Every skin vertex (both sheets and the walls) is moved OUTWARD along the skin's own smoothed outer
    normal n(q) at its closest outer-sheet point q by A(q) = max_j (r_j - K_SKIN |q - q_j|)+ over requirements whose outer normal
    agrees with n(q) (cos > COS_SKIN); evaluating at q moves a slab's two sheets together (the thickness is kept) and coincident
    border vertices of neighbouring pieces together (the load-time weld is kept). Never inward. The nail plates follow.
    Recorded per skin piece: vertices moved, max move, added volume (silhouette change), thickness min before / after.
 3. STRUCTURE REFIT again (step 1) for what the moved skin now has room for.

Vertex / triangle counts and order unchanged. Each changed structure's card gets a "Q398:" badge with what was done and the
volume / area change. Deterministic.
"""
from __future__ import annotations

import argparse, json, re, sys, time
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
for _p in ("q394", "q353", "q340", "q366"):
    if str(HERE.parent / _p) not in sys.path:
        sys.path.insert(0, str(HERE.parent / _p))
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

import under_skin_q394 as U  # noqa: E402
import tuck_under_skin_q394 as T  # noqa: E402

TAG = "Q398:"
SUFFIX = ".q398"
GAP = 0.3
KS = ((0.5, "remap"), (0.3, "remap"), (0.15, "remap"), (0.1, "translate"), (0.05, "translate"))
# (envelope slope, kind) tried in order, most local first; 'translate' (solid structures only): the column moves as a whole (w = 1),
# a smooth bend of a longer stretch -- for coarse thin tubes, where a local remap shears the few long faces
SIG = 4.0                        # mm, direction smoothing
ROUNDS = 6
CAP, CAP_SHELL = 12.0, 25.0      # mm per vertex
VOL_MAX, VOL_MAX_SHELL = 2.0, 30.0
FLIP_MAX = 0.5
R_SHELL = 8.0                    # mm: the shell's local deepest depth is taken over this radius
DMIN = 1.0                       # mm: the remap's floor D >= GAP + DMIN
SHELL_SYS = ("fat",)
SHELL_RE = re.compile(r"^(fat_|soft_unlabelled_)")
SKIN_REGIONS = re.compile(r"digits_of_(hand|foot)|perionyx|distal_transverse_arch_of_foot|philtrum|tubercle_of_upper_lip|"
                          r"oral_region|angle_of_mouth|labial_commissure|mentolabial_sulcus|perineum_rule_q358|urogenital_region|"
                          r"anal_region|skin_vulva")
SKIN_MAX = 4.0
K_SKIN = 0.2
COS_SKIN = 0.3
FADE_R = 3.0                     # mm: the skin move fades to 0 towards a skin piece outside SKIN_REGIONS
SKIN_ROUNDS = 5
FOLD_COS, FOLD_AREA = 0.5, 0.3   # a skin face turned by > 60 deg or shrunk below 30 % by the offset = a fold: held
TOL_N, TOL_MM = 2, 0.75          # a skin-offset group is kept when the total outside (count and depth, complete test) falls and no
                                 # structure gets more than TOL_N vertices / TOL_MM mm worse (listed: the digits' parity is ambiguous)
THIN_MM = 0.5                    # Q394 cause class (d): the slab under the closest outer point is thinner than this -> skin offset allowed
SKIN_MARGIN = 0.3                # mm added to each skin requirement (the offset is along the skin normal, not the inner normal)
IN_SLAB = False                  # in-slab vertices (not outside) are not requirements: tested, a snug shell would be crushed
NAIL_RE = re.compile(r"nail_plate")


def is_shell(pg, k):
    return pg.sys.get(k) in SHELL_SYS or bool(SHELL_RE.match(k))


def need_of(sk, v):
    """-> (need mask, depth d, inner normals at the closest inner point, confirmed-outside mask): a vertex needs to move when it is
    outside (Q394 test, parity-confirmed); its neighbours follow by the envelope"""
    out, so, si, own, tang, q = sk.test(v)
    c = np.where(out)[0]
    if len(c):
        conf = sk.confirm(v[c]); out[c[~conf]] = False
    _, _, ti, _ = sk.inner.query(v)
    slab = (so <= 0) & (si < GAP) & (tang < U.TANG_MAX) & (si > -6.0)
    # si along the inner normal: + = deeper.  In Skin.test `out` needs si < 0; here d = si
    need = out | (slab & IN_SLAB)
    return need, si, sk.inner.N[ti], out


def outside_complete(sk, v):
    """outside by the ray-parity test and over the skin (s_out > 0, tangential < TANG_MAX), whatever the closest inner sheet says
    (the Q394 test also needs s_in < 0 and so misses a vertex whose closest inner sheet belongs to the next digit: the census's
    `__hidden__`). Used to judge the skin offset fairly: moving the skin out uncovers such vertices to the Q394 test."""
    out, so, si, own, tang, q = sk.test(v)
    c = np.where((so > 0) & (tang < U.TANG_MAX))[0]
    m = np.zeros(len(v), bool)
    if len(c):
        m[c[sk.confirm(v[c])]] = True
    return m, so


def env_field(X, pts, amp, dirs, K, sig=SIG):
    """amplitude max_j (amp_j - K|x - x_j|)+ and Gaussian-mean direction (unit), separately"""
    a = np.zeros(len(X)); D = np.zeros((len(X), 3))
    if not len(pts):
        return a, D
    r = float(amp.max()) / K + 1e-6
    tx, tn = cKDTree(X), cKDTree(pts)
    S = tx.sparse_distance_matrix(tn, max(r, 3 * sig), output_type="coo_matrix")
    i, j, d = S.row, S.col, S.data
    d0, j0 = tn.query(X, distance_upper_bound=1e-9)
    z = np.where(np.isfinite(d0))[0]
    i = np.r_[i, z]; j = np.r_[j, j0[z]]; d = np.r_[d, np.zeros(len(z))]
    np.maximum.at(a, i, amp[j] - K * d)
    w = np.exp(-0.5 * (d / sig) ** 2) + 1e-12 * (d < r)
    np.add.at(D, i, w[:, None] * dirs[j])
    n = np.linalg.norm(D, axis=1, keepdims=True)
    D = np.where(n > 1e-9, D / np.maximum(n, 1e-12), 0.0)
    return np.clip(a, 0, None), D


def local_max(X, val, r):
    """max of val over the points within r of each point"""
    t = cKDTree(X)
    S = t.sparse_distance_matrix(t, r, output_type="coo_matrix")
    m = val.copy()
    np.maximum.at(m, S.row, val[S.col])
    return m


def remap_step(v, sk, shell, K, kind="remap"):
    need, d, nrm, _ = need_of(sk, v)
    if not need.any():
        return None
    e = GAP - d[need]
    keep = e > 1e-4
    if not keep.any():
        return None
    E, Dir = env_field(v, v[need][keep], e[keep], nrm[need][keep], K)
    act = E > 1e-6
    dloc = local_max(v, d, R_SHELL)
    if shell:
        Dd = np.maximum(dloc, GAP + DMIN)
    else:
        Dd = np.maximum(dloc, GAP + DMIN) + 2 * E + 2.0
    L = GAP - E
    w = np.clip((Dd - d) / np.maximum(Dd - L, 1e-9), 0.0, 1.0) if kind == "remap" else np.ones(len(v))
    u = np.where(act, E * w, 0.0)
    return v + Dir * u[:, None]


def thickness_ratio(v0, v1, f):
    """local shell thickness after / before over the moved region, via the mesh's own depth extent is not available
    cheaply; report the ratio of the volume of the moved faces' prisms instead (volume change of the whole mesh is reported)"""
    return None


def refit_one(pg, sk, k, bones, Q):
    v0 = pg.V[k].copy(); f = pg.F[k]
    shell = is_shell(pg, k)
    need0, d0, _, out0 = need_of(sk, v0)
    n0 = int(out0.sum())
    res = dict(sys=pg.sys[k], mode="shell" if shell else "solid", nv=len(v0),
               before=dict(n=n0, max_mm=round(float(sk.test(v0)[1][out0].max()), 3) if n0 else 0.0, in_slab=int((need0 & ~out0).sum())))
    if n0 == 0:
        res.update(status="clean"); return res, None
    if pg.sys[k] in T.NO_MOVE_SYS:
        res.update(status="NOT FIXED", reason="a bone is not moved (skin defect over the bone)"); return res, None
    cap = CAP_SHELL if shell else CAP
    vmax = VOL_MAX_SHELL if shell else VOL_MAX
    tries = []
    for K, kind in KS:
        if shell and kind != "remap":
            continue
        v = v0.copy()
        for _ in range(ROUNDS):
            v2 = remap_step(v, sk, shell, K, kind)
            if v2 is None:
                break
            v = v2
        v = T.bone_yield(v0, v, bones)
        o = T.outside_of(sk, v)[0]
        D = v - v0; dn = np.linalg.norm(D, axis=1); mv = dn > 1e-6
        fg = Q.face_guards(v0, v, f)
        dv = Q.vol_change(fg)
        da = abs(T.area(v, f) - T.area(v0, f)) / max(T.area(v0, f), 1e-9) * 100
        b0 = int(bones.inside(v0[mv]).sum()); b1 = int(bones.inside(v[mv]).sum())
        fails = []
        if dn.max() > cap:
            fails.append(f"move {dn.max():.2f} mm > cap {cap:g}")
        if o.any():
            fails.append(f"{int(o.sum())} vertices still outside")
        if fg["flipped_pct_moved_faces"] > FLIP_MAX:
            fails.append(f"flipped {fg['flipped_pct_moved_faces']} % of moved faces")
        if b1 > b0:
            fails.append(f"moved vertices inside bone {b0} -> {b1}")
        if dv is not None and dv > vmax:
            fails.append(f"volume change {dv:.2f} %")
        if dv is None and da > vmax:
            fails.append(f"area change {da:.2f} % (open mesh)")
        vol0, vol1 = fg["volume_before_mm3"], fg["volume_after_mm3"]
        t = dict(slope=K, kind=kind, moved=int(mv.sum()), max_mm=round(float(dn.max()), 3),
                 p95_mm=round(float(np.percentile(dn[mv], 95)), 3) if mv.any() else 0.0,
                 volume_change_pct=None if dv is None else round(dv, 3),
                 volume_signed_pct=None if dv is None else round((vol1 - vol0) / max(abs(vol0), 1e-9) * 100, 3),
                 area_change_pct=round(da, 3), closed_manifold=fg["closed_manifold"], flipped_pct=fg["flipped_pct_moved_faces"],
                 inside_bone=[b0, b1], after_outside=int(o.sum()), fails=fails, _v=v)
        tries.append(t)
        if not fails:
            break
    best = min(tries, key=lambda t: (len(t["fails"]) > 0, t["after_outside"], t["max_mm"]))
    v = best.pop("_v")
    for t in tries:
        t.pop("_v", None)
    res["tries"] = tries
    for x in ("slope", "kind", "moved", "max_mm", "p95_mm", "volume_change_pct", "volume_signed_pct", "area_change_pct", "closed_manifold",
              "after_outside", "flipped_pct"):
        res[x] = best[x]
    if not best["fails"]:
        res["status"] = "FIXED"; return res, v
    # partial: accept when it only fails on "still outside" and reduces the outside count / depth without breaking other guards
    other = [x for x in best["fails"] if "still outside" not in x]
    if not other and best["after_outside"] < n0:
        res.update(status="PARTIAL", reason="; ".join(best["fails"])); return res, v
    res.update(status="NOT FIXED", reason="; ".join(best["fails"]))
    return res, None


# ------------------------------------------------------------------ skin offset
def outer_normals_at(sk, Qp, r=2.0):
    """smoothed outer normal at points Qp: area-weighted mean of the outer-sheet face normals within r (a function of position)"""
    O = sk.outer
    C = (O.A + O.B + O.C) / 3.0
    ar = np.linalg.norm(np.cross(O.B - O.A, O.C - O.A), axis=1) / 2
    t = cKDTree(C)
    tq = cKDTree(Qp)
    S = tq.sparse_distance_matrix(t, r, output_type="coo_matrix")
    N = np.zeros((len(Qp), 3))
    w = ar[S.col] * np.exp(-0.5 * (S.data / (r / 2)) ** 2)
    np.add.at(N, S.row, w[:, None] * O.N[S.col])
    miss = np.linalg.norm(N, axis=1) < 1e-12
    if miss.any():
        _, j = t.query(Qp[miss]); N[miss] = O.N[j]
    return N / np.linalg.norm(N, axis=1, keepdims=True)


def orient(sk, q, n, h=0.4):
    """the outer normal pointing out of the body, checked by the ray-parity test (a swapped outer / inner patch has its 'outer'
    normal pointing in): -> n, -n, or 0 where neither side is clearly outside"""
    po = sk.confirm(q + h * n); ne = sk.confirm(q - h * n)
    s = np.where(po & ~ne, 1.0, np.where(ne & ~po, -1.0, 0.0))
    return n * s[:, None]


def skin_offset(pg, sk, req_pts, req_r, cum=None, allowed=None, cls=None):
    """-> {skin id: new vertices}, per-piece report. req_pts: requirement points (structure vertices), req_r: outward amount.
    cum: {id: per-vertex outward move so far} (the cap SKIN_MAX is on the total); allowed: skin ids that may move (the move fades
    to 0 over FADE_R mm towards any other skin piece, so the border to a piece that does not move stays closed)"""
    so, q, ti, _ = sk.outer.query(req_pts)
    qj = q
    nj = orient(sk, qj, outer_normals_at(sk, qj))
    ok = np.linalg.norm(nj, axis=1) > 0.5
    qj, nj, r = qj[ok], nj[ok], np.minimum(req_r[ok], SKIN_MAX)
    new, rep = {}, {}
    if not len(qj):
        return new, rep
    ids = [k for k in pg.skin_ids if allowed is None or k in allowed] + [k for k in pg.ids if NAIL_RE.search(k)]
    lo, hi = qj.min(0) - SKIN_MAX / K_SKIN - 3, qj.max(0) + SKIN_MAX / K_SKIN + 3
    fixed = [pg.V[k] for k in pg.skin_ids if allowed is not None and k not in allowed]
    ftree = cKDTree(np.vstack(fixed)) if fixed else None
    tn = cKDTree(qj)
    cand = {}
    for k in ids:
        v = pg.V[k]
        sel = np.where((v >= lo).all(1) & (v <= hi).all(1))[0]
        if not len(sel):
            continue
        _, qk, _, _ = sk.outer.query(v[sel])
        S = cKDTree(qk).sparse_distance_matrix(tn, float(r.max()) / K_SKIN, output_type="coo_matrix")
        if not S.nnz:
            continue
        rows = np.unique(S.row)
        sel, qk = sel[rows], qk[rows]
        S = cKDTree(qk).sparse_distance_matrix(tn, float(r.max()) / K_SKIN, output_type="coo_matrix")
        n0 = outer_normals_at(sk, qk)
        nk = orient(sk, qk, n0)
        nn = np.where((np.linalg.norm(nk, axis=1) > 0.5)[:, None], nk, n0)
        agree = (nn[S.row] * nj[S.col]).sum(1) > COS_SKIN
        val = np.where(agree, r[S.col] - K_SKIN * S.data, 0.0)
        A = np.zeros(len(sel)); np.maximum.at(A, S.row, val)
        A = np.clip(A, 0, None)
        if ftree is not None:
            dfix, _ = ftree.query(qk)
            A *= np.clip(dfix / FADE_R, 0, 1)
        if cum is not None and k in cum:
            A = np.minimum(A, np.clip(SKIN_MAX - cum[k][sel], 0, None))
        cand[k] = [sel, qk, nk, A]
    # hold: a vertex in the move's support whose outward side is not clearly outside (a fold: two toes / fingers touching,
    # orient 0), and an outer-sheet vertex whose moved position would not lie outside the skin as it was (it would enter the
    # neighbouring digit) -- the move fades to 0 over FADE_R mm around every held point (Lipschitz, as Q394's bone_yield)
    outer_v = {k: set(np.unique(pg.F[k][cls[k] == 1]).tolist()) if cls is not None and k in cls else set() for k in cand}
    for _ in range(5):
        held = []
        for k, (sel, qk, nk, A) in cand.items():
            act = A > 1e-6
            z = act & (np.linalg.norm(nk, axis=1) < 0.5)
            held.append(qk[z])
            ov = np.array([i in outer_v[k] for i in sel]) & act & ~z
            if ov.any():
                p = pg.V[k][sel[ov]] + nk[ov] * A[ov, None]
                bad = ~sk.confirm(p)
                held.append(qk[ov][bad])
            # a fold: the outward offset of a concave surface (the cleft between two digits, the web) turns or crushes faces
            if act.any():
                v = pg.V[k]; v2 = v.copy(); v2[sel] = v[sel] + nk * A[:, None]
                f = pg.F[k]
                mvf = np.isin(f, sel[act]).any(1)
                if mvf.any():
                    ff = f[mvf]
                    n0_ = np.cross(v[ff[:, 1]] - v[ff[:, 0]], v[ff[:, 2]] - v[ff[:, 0]])
                    n1_ = np.cross(v2[ff[:, 1]] - v2[ff[:, 0]], v2[ff[:, 2]] - v2[ff[:, 0]])
                    a0_, a1_ = np.linalg.norm(n0_, axis=1), np.linalg.norm(n1_, axis=1)
                    ok_ = a0_ > 1e-9
                    cosr = (n0_ * n1_).sum(1) / np.maximum(a0_ * a1_, 1e-18)
                    badf = ok_ & ((cosr < FOLD_COS) | (a1_ < FOLD_AREA * a0_))
                    if badf.any():
                        held.append(v[np.unique(ff[badf])])
        held = np.vstack(held) if held else np.zeros((0, 3))
        if not len(held):
            break
        ht = cKDTree(held)
        for k, c in cand.items():
            dh, _ = ht.query(c[1])
            c[3] = c[3] * np.clip(dh / FADE_R, 0, 1)
    new, rep = {}, {}
    for k, (sel, qk, nk, A) in cand.items():
        if not (A > 1e-6).any():
            continue
        v = pg.V[k]
        v2 = v.copy(); v2[sel] = v[sel] + nk * A[:, None]
        new[k] = v2
        if cum is not None:
            c = cum.setdefault(k, np.zeros(len(v))); c[sel] += A
        rep[k] = dict(moved=int((A > 1e-6).sum()), max_mm=round(float(A.max()), 3))
    return new, rep


def skin_stats(pg, cls, k, v0, v1, sk0, sk1):
    """added volume (outer sheet sweep, mm3) and slab thickness (depth of the moved outer vertices under the inner sheet of the
    whole skin) min / p5 before / after"""
    f = pg.F[k]; c = cls[k]
    fo = f[c == 1]
    D = v1 - v0
    mv = np.linalg.norm(D, axis=1) > 1e-6
    A, B, C = v0[fo[:, 0]], v0[fo[:, 1]], v0[fo[:, 2]]
    n = np.cross(B - A, C - A) / 2
    du = (D[fo[:, 0]] + D[fo[:, 1]] + D[fo[:, 2]]) / 3
    addv = float((n * du).sum(1).sum())
    out = dict(added_volume_mm3=round(addv, 1), moved=int(mv.sum()), max_mm=round(float(np.linalg.norm(D, axis=1).max()), 3))
    mf = mv[fo].any(1) if len(fo) else np.zeros(0, bool)
    if mf.any():
        c0 = v0[fo[mf]].mean(1); c1 = v1[fo[mf]].mean(1)
        th0 = np.abs(sk0.inner.query(c0)[0]); th1 = np.abs(sk1.inner.query(c1)[0])
        out["thickness_moved_mm"] = dict(p5_before=round(float(np.percentile(th0, 5)), 3), p5_after=round(float(np.percentile(th1, 5)), 3),
                                         median_before=round(float(np.median(th0)), 3), median_after=round(float(np.median(th1)), 3))
    return out


# ------------------------------------------------------------------ driver
def note(r):
    vc = (f"volume change {r['volume_signed_pct']:+.2f} %" if r.get("volume_signed_pct") is not None
          else f"open surface, area change {r['area_change_pct']:.2f} %")
    if r["mode"] == "shell":
        what = ("it was refitted between the skin's inner sheet and its own deep face (rule-based depth remap: the part under the "
                "skin was made thinner there, its deep face kept)")
    else:
        what = "it was moved inward along the skin's inner normal by a rule-based depth remap that keeps its shape"
    st = "" if r["status"] == "FIXED" else f" Still outside after this: {r['after_outside']} vertices (open defect)."
    return (f"{TAG} {r['before']['n']} of its {r['nv']} vertices lay outside the skin surface (up to {r['before']['max_mm']:.1f} mm); "
            f"{what} to {GAP:g} mm under the skin's inner sheet ({r['moved']} vertices moved, max {r['max_mm']:.1f} mm, p95 "
            f"{r['p95_mm']:.1f} mm; {vc}).{st} Rule-based correction, not measured.")


def skin_note(s):
    th = s.get("thickness_moved_mm")
    tt = (f"; skin thickness there (median / 5th percentile) {th['median_before']:.2f} / {th['p5_before']:.2f} -> "
          f"{th['median_after']:.2f} / {th['p5_after']:.2f} mm" if th else "")
    return (f"{TAG} rule-based local skin offset OUTWARD (Q398; the source-fitted skin here was thinner / closer than the structures "
            f"it must cover): {s['moved']} vertices moved outward along the skin normal, max {s['max_mm']:.2f} mm (cap {SKIN_MAX:g}), "
            f"smooth falloff; added volume {s['added_volume_mm3'] / 1000:.2f} cm3 (silhouette change){tt}. Not measured.")


def run(pg, sk_factory, todo, bones, Q, log):
    out, newv = {}, {}
    sk = sk_factory()
    for k in todo:
        r, v = refit_one(pg, sk, k, bones, Q)
        out[k] = r
        if v is not None:
            newv[k] = v
        log(f"   {k:60s} {r['before']['n']:5d} max {r['before']['max_mm']:6.2f} {r['mode']:5s} -> {r['status']}"
            + (f" (move {r.get('max_mm', 0):.2f}, vol {r.get('volume_signed_pct')}, area {r.get('area_change_pct', 0):.2f} %, out {r.get('after_outside')})"
               if r["status"] in ("FIXED", "PARTIAL") else f" ({r.get('reason', '')})"))
    return out, newv


def main(argv=None):
    import conform_skin_q353 as Q
    import conform_palm_q340 as C340
    ap = argparse.ArgumentParser()
    ap.add_argument("--page-dir", required=True)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--allow-build", action="store_true")
    ap.add_argument("--json")
    ap.add_argument("--cache")
    ap.add_argument("--only")
    ap.add_argument("--no-skin", action="store_true")
    ap.add_argument("--step1", help="pickle: reuse / store the step-1 result (development; same page and code only)")
    a = ap.parse_args(argv)
    d = Path(a.page_dir).resolve()
    if a.write and "/build/" in str(d) and not a.allow_build:
        raise SystemExit("refusing to write into build/ without --allow-build")
    pg = U.Page(d, cache_dir=a.cache)
    for m in pg.g.man["meshes"]:
        if TAG in json.dumps(m.get("rec") or {}):
            raise SystemExit(f"{m['id']}: already carries a {TAG} note (refused: run on the original page)")
    log = lambda s: print(s, flush=True)  # noqa: E731
    cls = pg.cls()
    V0 = {k: pg.V[k].copy() for k in pg.ids}
    inc, _ = pg.tested()
    t0 = time.time()
    c = U.census(pg, "rest", ids=inc); c.pop("__suspect__", None); c.pop("__hidden__", None)
    todo = sorted(c) if not a.only else a.only.split(",")
    log(f"{pg.d.name}: {len(c)} structures outside at rest ({time.time() - t0:.0f}s)")
    lo = np.min([pg.V[k].min(0) for k in pg.ids if pg.sys[k] != "skin"], 0) - 20
    hi = np.max([pg.V[k].max(0) for k in pg.ids if pg.sys[k] != "skin"], 0) + 20
    bones = Q.Bones(pg.g, lo, hi)
    mk = lambda: U.Skin(pg.skin_ids, pg.V, pg.F, cls)  # noqa: E731
    log("step 1: structure refit")
    if a.step1 and Path(a.step1).exists():
        import pickle
        r1, nv1 = pickle.load(open(a.step1, "rb")); log(f"   (step 1 from {a.step1})")
    else:
        r1, nv1 = run(pg, mk, todo, bones, Q, log)
        if a.step1:
            import pickle
            pickle.dump((r1, nv1), open(a.step1, "wb"))
    for k, v in nv1.items():
        pg.V[k] = v
    skin_rep, skin_new = {}, {}
    r3 = {}
    if not a.no_skin:
        allowed = {k for k in pg.skin_ids if SKIN_REGIONS.search(k)}
        cum, who_all = {}, []
        sk_b = mk()
        before1 = {}
        for k in todo:
            o, so_, si_ = T.outside_of(sk_b, pg.V[k])
            if o.any():
                before1[k] = (int(o.sum()), float(so_[o].max()))
        skin_ids_all = list(pg.skin_ids) + [k for k in pg.ids if NAIL_RE.search(k)]
        best = (np.inf, None, -1)
        for rnd in range(SKIN_ROUNDS + 1):
            sk = mk()
            P, R, who = [], [], []
            metric = 0.0                                   # over every structure left: sum of (GAP - depth) of its outside vertices
            for k in todo:
                if r1[k]["status"] in ("FIXED", "clean"):
                    continue
                v = pg.V[k]
                out, so, si, own, tang, q = sk.test(v)
                cc = np.where(out)[0]
                if len(cc):
                    conf = sk.confirm(v[cc]); out[cc[~conf]] = False
                metric += float((GAP - si[out]).sum())
                reg = np.array([sk.ids[o] in allowed for o in own])
                th = np.full(len(v), np.inf)
                if out.any():
                    th[out] = np.abs(sk.inner.query(q[out])[0])          # slab thickness under the closest outer point
                thin = out & (th < THIN_MM)
                for o in np.unique(own[thin]):
                    allowed.add(sk.ids[o])
                m = out & (reg | thin)
                if m.any():
                    P.append(v[m]); R.append(GAP + SKIN_MARGIN - si[m]); who.append((k, int(m.sum())))
            log(f"step 2 round {rnd + 1}: skin offset requirements: {sum(n for _, n in who)} vertices of {len(who)} structures; "
                f"outside sum {metric:.1f} mm")
            if metric < best[0] - 1e-6:
                best = (metric, {k: pg.V[k].copy() for k in skin_ids_all}, rnd)
            if not P or rnd == SKIN_ROUNDS:
                break
            who_all.append(who)
            P = np.vstack(P); R = np.concatenate(R)
            new, srep = skin_offset(pg, sk, P, R, cum=cum, allowed=allowed, cls=cls)
            if not new:
                break
            for k, v in new.items():
                pg.V[k] = v
        # keep the best round (a later round can make it worse: digits that touch)
        for k, v in best[1].items():
            pg.V[k] = v
        log(f"step 2: kept the skin after round {best[2]} (outside sum {best[0]:.1f} mm)")
        # no structure may end up (much) worse than without the offset (digits that touch: a moved digit's skin can cross its
        # neighbour's, and the outside test then reads a fold). Per group of skin pieces (one hand's digits, one foot's toes, the
        # mouth, each other piece alone), in a fixed order: the group's move is tried at scale 1, 1/2, 1/4 with every other group as
        # already decided; the first scale at which the complete outside test (parity, every inner sheet) gives a smaller total
        # count and depth and no structure more than TOL_N vertices / TOL_MM mm worse is kept (the small worsenings are listed);
        # else the group does not move.
        D = {k: pg.V[k] - V0[k] for k in skin_ids_all if not np.array_equal(pg.V[k], V0[k])}
        for k in D:
            pg.V[k] = V0[k].copy()
        groups = {}
        for k in sorted(D):
            m_ = re.search(r"(digits_of_hand|perionyx(?!_foot)|nail_plate(?!_foot)).*_([lr])$", k)
            m2 = re.search(r"(digits_of_foot|perionyx_foot|nail_plate_foot|distal_transverse_arch_of_foot).*_([lr])$", k)
            m3 = re.search(r"philtrum|tubercle_of_upper_lip|oral_region|angle_of_mouth|labial_commissure|mentolabial_sulcus", k)
            g = f"hand_{m_.group(2)}" if m_ else f"foot_{m2.group(2)}" if m2 else "mouth" if m3 else k
            groups.setdefault(g, []).append(k)
        held_log = {}

        def state_of(near):
            sk = mk(); res = {}
            for k in near:
                o, so_ = outside_complete(sk, pg.V[k])
                res[k] = (int(o.sum()), float(so_[o].max()) if o.any() else 0.0, float(so_[o].sum()))
            return res
        for g in sorted(groups):
            ks = groups[g]
            lo_ = np.min([V0[k].min(0) for k in ks], 0) - 15; hi_ = np.max([V0[k].max(0) for k in ks], 0) + 15
            near = [k for k in inc if (pg.V[k].max(0) >= lo_).all() and (pg.V[k].min(0) <= hi_).all()]
            base = state_of(near)
            done = 0.0
            for sc in (1.0, 0.5, 0.25):
                for k in ks:
                    pg.V[k] = V0[k] + sc * D[k]
                now = state_of(near)
                worse = [k for k in near if now[k][0] > base[k][0] + TOL_N or now[k][1] > base[k][1] + TOL_MM]
                gain = sum(v[2] for v in base.values()) - sum(v[2] for v in now.values())
                gain_n = sum(v[0] for v in base.values()) - sum(v[0] for v in now.values())
                if not worse and gain > 0 and gain_n > 0:
                    held_log.setdefault(g, []).append(dict(scale=sc, gain_mm=round(gain, 2), gain_n=gain_n, within_tolerance=[
                        (k, base[k][:2], now[k][:2]) for k in near if now[k][0] > base[k][0] or now[k][1] > base[k][1] + 0.05]))
                    done = sc
                    break
                held_log.setdefault(g, []).append(dict(scale=sc, worse=worse[:20], gain_mm=round(gain, 2)))
            if done == 0.0:
                for k in ks:
                    pg.V[k] = V0[k].copy()
            held_log.setdefault(g, []).append(dict(kept_scale=done))
            log(f"step 2 group {g}: {len(ks)} pieces, kept scale {done:g}" + (f" (tried: {held_log[g][:-1]})" if held_log[g][:-1] else ""))
        skin_new = {k: pg.V[k] for k in skin_ids_all if not np.array_equal(pg.V[k], V0[k])}
        if skin_new:
            sk0 = U.Skin(pg.skin_ids, {k: V0[k] for k in pg.ids}, pg.F, cls)
            sk1 = mk()
            for k, v in skin_new.items():
                s = skin_stats(pg, cls, k, V0[k], v, sk0, sk1) if k in cls else dict(
                    moved=int((np.linalg.norm(v - V0[k], axis=1) > 1e-6).sum()),
                    max_mm=round(float(np.linalg.norm(v - V0[k], axis=1).max()), 3), added_volume_mm3=0.0)
                skin_rep[k] = s
                log(f"   skin {k:50s} moved {s['moved']:5d} max {s['max_mm']:.2f} mm, +{s['added_volume_mm3'] / 1000:.2f} cm3 {s.get('thickness_moved_mm', '')}")
            skin_rep["__requirements__"] = dict(rounds=who_all, kept_round=best[2], outside_sum_mm=round(best[0], 2), held=held_log)
            log("step 3: structure refit again")
            todo3 = [k for k in todo if r1[k]["status"] != "FIXED" and pg.sys[k] not in T.NO_MOVE_SYS] + \
                    [k for k in todo if pg.sys[k] in T.NO_MOVE_SYS]
            # step 3 starts from the step-1 result (a PARTIAL is kept and continued from)
            r3, nv3 = run(pg, mk, todo3, bones, Q, log)
            for k, v in nv3.items():
                pg.V[k] = v
    # final structure set to write
    changed = {k: pg.V[k] for k in pg.ids if not np.array_equal(pg.V[k], V0[k])}
    rep = dict(schema="nmsk.q398.refit.v1", page=pg.d.name, generated=time.strftime("%Y-%m-%d"),
               parameters=dict(gap_mm=GAP, slopes=KS, rounds=ROUNDS, cap_mm=CAP, cap_shell_mm=CAP_SHELL, vol_max_pct=VOL_MAX,
                               vol_max_shell_pct=VOL_MAX_SHELL, flip_max_pct=FLIP_MAX, r_shell_mm=R_SHELL, skin_max_mm=SKIN_MAX,
                               k_skin=K_SKIN, cos_skin=COS_SKIN, skin_regions=SKIN_REGIONS.pattern),
               step1=r1, skin=skin_rep, step3=r3, changed=sorted(changed), written=False)
    # final per-structure verdict
    final = {}
    for k in todo:
        rr = r3.get(k) or r1[k]
        final[k] = dict(status=rr["status"], step=3 if k in r3 else 1)
    rep["final"] = final
    if a.write and changed:
        import despike_q366 as D
        man, blob, files = pg.g.man, pg.g.blob, pg.g.files
        repl = {}
        for k, v in changed.items():
            rec = pg.g.M[k].get("rec") or {}
            if k in skin_rep:
                rec = C340.badge_add(rec, skin_note(skin_rep[k]))
            for rr in (r1.get(k), r3.get(k)):
                if rr and rr["status"] in ("FIXED", "PARTIAL"):
                    rec = C340.badge_add(rec, note(rr))
            repl[k] = (v, pg.F[k], rec)
        man2, blob2 = C340.repack(man, blob, repl)
        old = D.SUFFIX
        try:
            D.SUFFIX = SUFFIX
            rep["files_changed"] = D.write_page(d, pg.g.stem, man, man2, blob2, files, C340)
        finally:
            D.SUFFIX = old
        rep["written"] = True
        man3, blob3, _ = C340.read_page(d, pg.g.stem)
        qr = {}
        for m in man3["meshes"]:
            if m["id"] in changed:
                P3, F3 = C340.dec(m, blob3)
                qr[m["id"]] = round(float(np.abs(P3 - changed[m["id"]]).max()), 5)
                assert np.array_equal(F3, pg.F[m["id"]])
        rep["quantisation_residual_mm"] = qr
        assert [m["vc"] for m in man3["meshes"]] == [m["vc"] for m in man["meshes"]]
        assert [m["id"] for m in man3["meshes"]] == [m["id"] for m in man["meshes"]]
        log("  wrote: " + ", ".join(rep["files_changed"]) + f" (originals kept as *{SUFFIX})")
    if a.json:
        Path(a.json).write_text(json.dumps(rep, indent=1, default=lambda o: o.tolist() if isinstance(o, np.ndarray) else (
            float(o) if isinstance(o, np.floating) else int(o) if isinstance(o, np.integer) else str(o))) + "\n", encoding="utf-8")
    nf = sum(1 for x in final.values() if x["status"] == "FIXED")
    npart = sum(1 for x in final.values() if x["status"] == "PARTIAL")
    log(f"Q398 REFIT {'WRITTEN' if rep['written'] else 'DRY RUN'} {pg.d.name}: {len(todo)} outside at rest, fixed {nf}, partial {npart}, "
        f"not fixed {len(todo) - nf - npart}; skin pieces moved {len([k for k in skin_rep if not k.startswith('__')])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
