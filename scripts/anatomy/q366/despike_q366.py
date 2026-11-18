#!/usr/bin/env python3
"""Q366: Base·F -- body-wide guarded de-spike of the registration noise against the real Base·M (Z-Anatomy source) mesh.

    python3 scripts/anatomy/q366/despike_q366.py --page-dir DIR [--src-dir DIR]            # dry run: measure, write nothing
    python3 scripts/anatomy/q366/despike_q366.py --page-dir DIR --write                    # and write the page files + report
    options: --only REGEX (development; never with --write), --hist FILE (residual histogram, npz), --allow-build

Finding (Q364): the body registration that built Base·F from the Z-Anatomy source left SPIKES: single vertices or small patches
displaced 3-8.5 mm from where the rest of the structure's warp puts them (orbit muscles, lacrimal gland, optic nerve, temporal
vessels; Q364 refitted only the globes).

Every Base·F structure with a same-topology twin on Base·M (same id, same vertex count, same triangles) carries a per-vertex
correspondence x_M -> x_F.  Nothing is sculpted:
  map      per vertex i, a LOCAL smooth map is fitted from its K nearest Base·M neighbours (same structure, i itself and its coincident
           copies left out) to their Base·F positions: a similarity (Umeyama) plus an affine deviation ridge-regularised towards it
           (LAMBDA), robustly (iteratively reweighted, Cauchy weights at CAUCHY x the neighbourhood's robust residual scale, floor
           S_MIN).  Long structures bent by the warp are followed: each vertex has its own map.  The prediction p_i is x_M,i through
           its map; the residual r_i = |x_F,i - p_i|; the neighbourhood spread sigma_i = 1.4826 x median of the neighbours' r.
  flag     a spike seed is r_i > T_HI mm AND r_i > K_HI x sigma_i; it grows over mesh edges into neighbours with r > T_LO mm AND
           r > K_LO x sigma (hysteresis: the shoulders of a spike go with its tip).  Flagged vertices are left out of every
           neighbourhood and the maps refitted (PASSES), so a spike patch never steers its own correction.
  move     a flagged vertex goes to p_i: its own Base·M position through the measured local warp of its unflagged neighbours.
           Nothing else moves; no Laplacian smoothing, nothing invented.
  exclude  the skin layer (slabs welded at load on identical border vertices, Q334), every structure written by a geometry round
           since Q318 (found from the page's own *.q318 backups: any structure whose geometry differs from it, or that is new) and
           the bones (the reference layer of the Q357 in-bone test and of every contact round; measured, not moved).  Vertices
           within CONTACT mm of an excluded structure, or coincident with another structure's vertex (a shared border), are frozen.
  guards   per structure (a structure failing any is left exactly as it is and listed): (a) no moved vertex enters a bone or goes
           deeper into one (generalised winding number > 0.5 against the page's bones, depth by closest point; Q357's test);
           (b) surface area (and, for a closed mesh, enclosed volume) change within SIZE_FREE %, or else not further than SIZE_AWAY %
           points from the reference size (the Base·M mesh through the smooth local maps); (c) see exclude /
           frozen; (d) faces whose normal opposes the Base·M face normal through the local map ("flipped") may not increase; the
           per-vertex move is capped at CAP mm.
  write    vertex / triangle counts and order unchanged (pose rig contract); every replaced file is first copied beside itself as
           `<name>.q366` (never overwriting); each changed structure's card gets a "Q366: ..." note; a page that already carries a
           Q366 note is refused (idempotent).  Deterministic.  Report: data/derived/Q366_despike_report.json (written only with
           --write).
"""
from __future__ import annotations

import argparse, base64, json, re, shutil, sys, time
from pathlib import Path

import numpy as np
from scipy import sparse
from scipy.sparse import csgraph
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]

OUT = REPO / "data/derived/Q366_despike_report.json"
TAG = "Q366:"
SUFFIX = ".q366"
BASELINE = ".q318"   # the oldest per-round backup kept beside the page: every geometry round since writes its own suffix

K = 64               # neighbours of the local map (a 12-vertex spike patch is < 20 % of them)
LAMBDA = 0.1         # ridge of the affine part towards the local similarity (x trace of the neighbourhood covariance / 3)
CAUCHY = 2.385       # Cauchy weight scale, x the robust residual scale (95% efficiency), first two reweightings
TUKEY = 4.685        # Tukey biweight cut-off, x the robust residual scale (95% efficiency), the later ones
S_MIN = 0.15         # mm, floor of the robust residual scale of a neighbourhood
IRLS = 6             # reweighting iterations
PASSES = 3           # flag -> refit without the flagged -> flag again
T_HI, K_HI = 1.0, 10.0  # seed: residual > T_HI mm and > K_HI x neighbourhood spread (Q366 doc: histogram trough)
T_LO, K_LO = 0.5, 4.0  # grow: residual > T_LO mm and > K_LO x neighbourhood spread
SIG_MIN = 0.05       # mm, floor of sigma (quantisation of the page: span / 65535, ~0.01 mm)
CAP = 12.0           # mm, per-vertex move cap (worst Q364 spike 8.5 mm)
PATCH_MAX = 12       # vertices: a connected flagged patch larger than this is a region that moved, not a spike: left
MIN_SUPPORT = 32     # unflagged neighbours (of K) a corrected vertex's map must rest on
MOVE_RATIO, MOVE_ADD = 1.5, 1.0   # a correction may not exceed max(MOVE_RATIO x first-pass residual, residual + MOVE_ADD mm)
CONTACT = 1.0        # mm, a vertex this close to an excluded structure's vertex is frozen
COINCIDENT = 0.02    # mm, a vertex this close to another structure's vertex is a shared border: frozen
SIZE_FREE = 2.0      # %, area / volume change always accepted
SIZE_AWAY = 2.0      # %, beyond SIZE_FREE the change must not take the size further from the scaled source by more than this
FLIP_ADD = 0         # flipped faces after may not exceed before + FLIP_ADD
BONE_TOL = 0.1       # mm, deeper into a bone than before by more than this = fail
EXCLUDE_SYS = ("skin", "bone")


# ------------------------------------------------------------------ pure geometry (tested in tests/test_q366_despike.py)
def neighbours(XM, k=K):
    """K nearest neighbours of each vertex in the Base·M mesh, the vertex itself and its coincident copies left out.
    Returns (n, k') int array (k' = min(k, n - 1)), padded with -1 where fewer distinct neighbours exist."""
    n = len(XM)
    kk = int(min(k, n - 1))
    if kk < 1:
        return np.full((n, 0), -1, int)
    tree = cKDTree(XM)
    q = int(min(n, kk + 1 + 4))
    d, j = tree.query(XM, k=q)
    if q == 1:
        d, j = d[:, None], j[:, None]
    ok = d > 1e-6                     # drops self and coincident copies
    out = np.full((n, kk), -1, int)
    rank = np.cumsum(ok, axis=1)
    sel = ok & (rank <= kk)
    rows = np.repeat(np.arange(n), sel.sum(1))
    cols = (np.cumsum(sel, axis=1) - 1)[sel]
    out[rows, cols] = j[sel]
    return out


def _umeyama_batched(u, v, w):
    """per row: s R minimising sum_j w |s R u_j - v_j|^2 for centred u, v (n, k, 3) -> L (n, 3, 3)"""
    Svu = np.einsum("nk,nki,nkj->nij", w, v, u)
    U, S, Vt = np.linalg.svd(Svu)
    d = np.sign(np.linalg.det(U) * np.linalg.det(Vt))
    D = np.ones((len(u), 3)); D[:, 2] = d
    R = np.einsum("nij,nj,njk->nik", U, D, Vt)
    var = np.einsum("nk,nki,nki->n", w, u, u)
    s = (S * D).sum(1) / np.maximum(var, 1e-12)
    return s[:, None, None] * R, Svu, var


def local_predict(XM, XF, nb, mask=None, lam=LAMBDA, iters=IRLS, s_min=S_MIN):
    """Leave-one-out local map prediction.  For each vertex i: fit y = c_F + A (x - c_M) to its neighbours nb[i] (mask False = not
    used), A = similarity + ridge-regularised affine deviation, Cauchy-reweighted.  Returns p (n, 3) = the prediction of x_F,i from
    x_M,i, and ok (n,) = whether a map could be fitted (>= 4 usable neighbours)."""
    n = len(XM)
    p = XF.copy()
    if nb.shape[1] == 0:
        return p, np.zeros(n, bool)
    valid = nb >= 0
    if mask is not None:
        valid &= mask[np.where(nb >= 0, nb, 0)]
    ok = valid.sum(1) >= 4
    j = np.where(nb >= 0, nb, 0)
    Xj, Yj = XM[j], XF[j]                      # (n, k, 3)
    # robust start (breakdown 50 %): the neighbours' displacements x_F - x_M against their component-wise median, so a spike patch
    # inside the neighbourhood is down-weighted before the first fit can bend towards it
    dsp = np.where(valid[..., None], Yj - Xj, np.nan)
    with np.errstate(all="ignore"):
        e0 = np.linalg.norm(dsp - np.nanmedian(dsp, axis=1)[:, None], axis=2)
        s0 = np.maximum(1.4826 * np.nanmedian(e0, axis=1), s_min)
    w = np.where(valid, 1.0 / (1.0 + (np.nan_to_num(e0) / (CAUCHY * s0[:, None])) ** 2), 0.0)
    eye = np.eye(3)[None]
    for it in range(iters + 1):
        ws = np.maximum(w.sum(1), 1e-12)
        cM = np.einsum("nk,nki->ni", w, Xj) / ws[:, None]
        cF = np.einsum("nk,nki->ni", w, Yj) / ws[:, None]
        u = Xj - cM[:, None]; v = Yj - cF[:, None]
        L0, Svu, var = _umeyama_batched(u, v, w)
        Suu = np.einsum("nk,nki,nkj->nij", w, u, u)
        reg = (lam * var / 3.0 + 1e-9)[:, None, None]
        A = np.linalg.solve(Suu + reg * eye, np.transpose(Svu + reg * L0, (0, 2, 1)))
        A = np.transpose(A, (0, 2, 1))
        e = np.linalg.norm(np.einsum("nij,nkj->nki", A, u) - v, axis=2)
        if it == iters:
            break
        em = np.where(valid, e, np.nan)
        sr = np.maximum(1.4826 * np.nanmedian(np.where(ok[:, None], em, 0.0), axis=1), s_min)
        if it < 2:      # Cauchy first (convex start), then Tukey's biweight (redescending: a spike patch gets weight 0)
            w = valid / (1.0 + (e / (CAUCHY * sr[:, None])) ** 2)
        else:
            w = valid * np.clip(1.0 - (e / (TUKEY * sr[:, None])) ** 2, 0.0, None) ** 2
    pr = cF + np.einsum("nij,nj->ni", A, XM - cM)
    p[ok] = pr[ok]
    return p, ok


def spread(r, nb, mask=None):
    """robust spread of the neighbours' residuals: 1.4826 x median |r_j| over usable neighbours"""
    if nb.shape[1] == 0:
        return np.full(len(r), np.inf)
    valid = nb >= 0
    if mask is not None:
        valid &= mask[np.where(nb >= 0, nb, 0)]
    rj = np.where(valid, r[np.where(nb >= 0, nb, 0)], np.nan)
    with np.errstate(all="ignore"):
        s = 1.4826 * np.nanmedian(rj, axis=1)
    return np.where(np.isfinite(s), np.maximum(s, SIG_MIN), np.inf)


def edges_of(F):
    e = np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]])
    return np.unique(np.sort(e, axis=1), axis=0)


def flag(r, sig, F, n, frozen=None, t_hi=T_HI, k_hi=K_HI, t_lo=T_LO, k_lo=K_LO):
    """hysteresis: seeds r > t_hi & r > k_hi sigma; grown over mesh edges into r > t_lo & r > k_lo sigma"""
    seed = (r > t_hi) & (r > k_hi * sig)
    weak = (r > t_lo) & (r > k_lo * sig)
    if frozen is not None:
        seed &= ~frozen; weak &= ~frozen
    if not seed.any():
        return seed
    E = edges_of(F) if len(F) else np.zeros((0, 2), int)
    cand = weak | seed
    m = cand[E[:, 0]] & cand[E[:, 1]]
    G = sparse.coo_matrix((np.ones(m.sum()), (E[m, 0], E[m, 1])), shape=(n, n))
    _, lab = csgraph.connected_components(G, directed=False)
    keep = np.isin(lab, np.unique(lab[seed])) & cand
    return keep


def despike_structure(XM, XF, F, frozen=None, k=K, passes=PASSES):
    """-> (new XF, flagged mask, residual before (first pass), sigma, prediction).  Pure: XM, XF (n, 3), F (m, 3)."""
    n = len(XM)
    nb = neighbours(XM, k)
    mask = np.ones(n, bool)
    p, ok = local_predict(XM, XF, nb, mask)
    r0 = np.where(ok, np.linalg.norm(XF - p, axis=1), 0.0)
    sig0 = spread(r0, nb)
    fl = np.zeros(n, bool)
    r, sig = r0, sig0
    for _ in range(passes):
        f2 = flag(r, sig, F, n, frozen) & ok
        f2 |= fl
        if (f2 == fl).all() and _ > 0:
            break
        fl = f2
        if not fl.any():
            break
        p, ok2 = local_predict(XM, XF, nb, ~fl)
        ok = ok & ok2
        r = np.where(ok, np.linalg.norm(XF - p, axis=1), 0.0)
        sig = spread(r, nb, ~fl)
    info = dict(patches=0, rejected={})
    if frozen is not None:      # spike seeds the freeze holds (contact with an excluded structure / shared border): left, counted
        info["frozen_seeds"] = int((frozen & (r0 > T_HI) & (r0 > K_HI * sig0)).sum())
    if fl.any():
        # patch checks: a spike is small, its correction is supported by unflagged neighbours and agrees with the first-pass residual
        valid = nb >= 0
        support = (valid & ~fl[np.where(valid, nb, 0)]).sum(1)
        mv = np.linalg.norm(p - XF, axis=1)
        E = edges_of(F)
        m = fl[E[:, 0]] & fl[E[:, 1]]
        G = sparse.coo_matrix((np.ones(m.sum()), (E[m, 0], E[m, 1])), shape=(n, n))
        _, lab = csgraph.connected_components(G, directed=False)
        for L in np.unique(lab[fl]):
            vs = np.where(fl & (lab == L))[0]
            why = None
            if len(vs) > PATCH_MAX:
                why = "patch larger than %d vertices (a region, not a spike)" % PATCH_MAX
            elif not ok[vs].all() or (support[vs] < min(MIN_SUPPORT, nb.shape[1] // 2)).any():
                why = "too few unflagged neighbours to carry the map"
            elif (mv[vs] > np.maximum(MOVE_RATIO * r0[vs], r0[vs] + MOVE_ADD)).any() or (mv[vs] > CAP).any():
                why = "refitted map disagrees with the first-pass residual (unstable)"
            if why:
                fl[vs] = False
                info["rejected"][why] = info["rejected"].get(why, 0) + 1
            else:
                info["patches"] += 1
        info["label"] = np.where(fl, lab, -1)
    X1 = XF.copy()
    X1[fl] = p[fl]
    return X1, fl, r0, sig0, p, info


# ------------------------------------------------------------------ mesh measures
def area(V, F):
    return float(np.linalg.norm(np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]]), axis=1).sum() / 2)


def volume(V, F):
    return float(np.einsum("ij,ij->i", V[F[:, 0]], np.cross(V[F[:, 1]], V[F[:, 2]])).sum() / 6)


def closed(F):
    e = np.sort(np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]]), axis=1)
    _, c = np.unique(e, axis=0, return_counts=True)
    return bool((c == 2).all())


def face_normals(V, F):
    return np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])


def flipped_vs_source(XM, X, F, p_lin):
    """faces whose normal opposes the Base·M normal carried through the local map (approximated by the map of the face's vertices:
    the Base·F image of the Base·M face built from the predictions p_lin).  Counted over faces whose image is not degenerate."""
    n0 = face_normals(p_lin, F)
    n1 = face_normals(X, F)
    good = np.linalg.norm(n0, axis=1) > 1e-6
    return int(((np.einsum("ij,ij->i", n0, n1) < 0) & good).sum())


def stats(d):
    d = np.asarray(d, float)
    if not len(d):
        return dict(max_mm=0.0, p95_mm=0.0, mean_mm=0.0)
    return dict(max_mm=round(float(d.max()), 2), p95_mm=round(float(np.percentile(d, 95)), 2), mean_mm=round(float(d.mean()), 2))


# ------------------------------------------------------------------ page context
def _load():
    for p in (HERE.parent / "q340", HERE.parent / "q349"):
        if str(p) not in sys.path:
            sys.path.insert(0, str(p))
    import conform_palm_q340 as C340      # noqa: E402  page I/O, repack, badge_add
    import conform_fingers_q349 as C349   # noqa: E402  winding number
    return C340, C349


def baseline_changed(d: Path, stem, man, blob, C340):
    """ids whose geometry differs from the page's *.q318 backup (or that are new since): written by a later geometry round"""
    h = d / (stem + ".html" + BASELINE)
    if not h.exists():
        raise SystemExit(f"{h} missing: cannot tell which structures later rounds wrote (refusing)")
    t = h.read_text(encoding="utf-8")
    m0 = json.loads(C340.LIT["manifest"].search(t).group(1)); f0 = json.loads(C340.LIT["files"].search(t).group(1))
    b0 = b"".join(base64.b64decode((d / (f["path"] + BASELINE)).read_bytes()) for f in f0)
    M0 = {m["id"]: m for m in m0["meshes"]}
    out = {}
    for m in man["meshes"]:
        o = M0.get(m["id"])
        if o is None:
            out[m["id"]] = "new since Q318"; continue
        if (o["vc"], o["ic"]) != (m["vc"], m["ic"]):
            out[m["id"]] = "vertex / triangle count changed since Q318"; continue
        v1, f1 = C340.dec(m, blob); v0, ff0 = C340.dec(o, b0)
        dd = float(np.abs(v1 - v0).max())
        if dd > 1e-3 or not np.array_equal(f1, ff0):
            out[m["id"]] = "geometry changed since Q318 (max %.2f mm)" % dd
    return out


def round_tags(rec):
    b = ((rec or {}).get("procedural_badge")) or ""
    return sorted(set(re.findall(r"\b(Q3\d\d[a-z]?):", b)))


class BoneSet:
    """the page's bones (oriented outward by signed volume) for Q357's in-bone test: generalised winding number > 0.5, depth = distance
    to the closest surface point"""
    def __init__(self, bones, C349):
        import trimesh
        self.tm, self.C349, self.T = {}, C349, trimesh
        for k, (v, f) in bones.items():
            if not len(f):
                continue
            t = trimesh.Trimesh(v, f, process=False)
            if t.volume < 0:
                t = trimesh.Trimesh(v, f[:, ::-1], process=False)
            self.tm[k] = t

    def depth(self, P):
        """per point: (inside any bone, bone id, depth mm)"""
        P = np.atleast_2d(P)
        ins = np.zeros(len(P), bool); nm = np.array([""] * len(P), dtype=object); dep = np.zeros(len(P))
        for k, t in self.tm.items():
            lo, hi = t.bounds
            m = np.all((P > lo - 0.5) & (P < hi + 0.5), axis=1)
            if not m.any():
                continue
            idx = np.where(m)[0]
            w = np.abs(self.C349.winding(P[idx], t.vertices, t.faces))
            j = idx[w > 0.5]
            if not len(j):
                continue
            _, dd, _ = self.T.proximity.closest_point(t, P[j])
            better = dd > dep[j]
            ins[j] = True; nm[j[better]] = k; dep[j[better]] = dd[better]
        return ins, nm, dep


def guard_bone(bs, P0, P1):
    i0, n0, d0 = bs.depth(P0)
    i1, n1, d1 = bs.depth(P1)
    new = i1 & ~i0
    deeper = i1 & i0 & (d1 > d0 + BONE_TOL)
    return dict(inside_before=int(i0.sum()), inside_after=int(i1.sum()), new_inside=int(new.sum()), deeper=int(deeper.sum()),
                bones=sorted(set(n1[new | deeper])), ok=bool(not new.any() and not deeper.any()))


# ------------------------------------------------------------------ write (as eye_q364.write_page, originals kept as *.q366)
def write_page(d: Path, stem, man_old, man_new, blob_new, old_files, C340):
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
        p = d / n; new = base64.b64encode(c)
        if p.read_bytes() != new:
            bk = p.with_name(p.name + SUFFIX)
            if not bk.exists():
                shutil.copy2(p, bk)
            p.write_bytes(new); changed.append(n)
    for p, t in texts.items():
        bk = p.with_name(p.name + SUFFIX)
        if not bk.exists():
            shutil.copy2(p, bk)
        t2 = C340.LIT["manifest"].sub(lambda _m: "window.__ANATOMY_MANIFEST__=" + C340.ser_manifest(man_new) + ";", t, count=1)
        t2 = C340.LIT["files"].sub(lambda _m: "window.__ANATOMY_BIN_FILES__=" + json.dumps(files) + ";", t2, count=1)
        p.write_text(t2, encoding="utf-8"); changed.append(p.name)
    return changed


def note_for(r):
    return (f"{TAG} {r['moved']} of {r['verts']} vertices put back on this body's smooth warp of the Z-Anatomy source mesh: the body "
            f"registration that built this page had left them as spikes (residual up to {r['residual_max_mm']:.1f} mm against a local map "
            f"fitted to their neighbours); each went to its own source position through that local map (move max {r['move']['max_mm']:.1f} mm, "
            f"p95 {r['move']['p95_mm']:.1f} mm). Nothing else moved; placement, size and shape kept.")


def umeyama_scale(A, B):
    """uniform scale of the similarity fit Base·M -> Base·F of a whole structure (the structure's own size ratio)"""
    a, b = A - A.mean(0), B - B.mean(0)
    U, S, Vt = np.linalg.svd(b.T @ a / len(A))
    d = np.sign(np.linalg.det(U) * np.linalg.det(Vt))
    return float((S[0] + S[1] + d * S[2]) / max((a ** 2).sum(1).mean(), 1e-12))


def size_check(x0, x1, ref):
    """(b): change within SIZE_FREE %, or else toward the source's size (scaled by the structure's own fit) and never more than
    SIZE_AWAY % further from it than before"""
    ch = 100 * (x1 - x0) / max(abs(x0), 1e-9)
    e0 = 100 * abs(x0 / ref - 1) if ref else 0.0
    e1 = 100 * abs(x1 / ref - 1) if ref else 0.0
    ok = abs(ch) <= SIZE_FREE or e1 <= e0 + SIZE_AWAY
    return dict(change_pct=round(ch, 2), off_source_before_pct=round(e0, 2), off_source_after_pct=round(e1, 2), ok=bool(ok))


def histograms(R, Q):
    eb = [0, 0.05, 0.1, 0.2, 0.3, 0.5, 0.75, 1, 1.5, 2, 3, 4, 5, 6, 7, 8, 10, 15, 1e9]
    qb = [float(x) for x in np.round(np.geomspace(0.5, 200, 25), 2)]
    h = dict(residual_mm=dict(edges=eb[:-1] + ["inf"], counts=np.histogram(R, eb)[0].tolist()))
    for lo in (1.0, 1.5):
        h["ratio_residual_over_spread_r_gt_%g" % lo] = dict(edges=qb, counts=np.histogram(Q[R > lo], qb)[0].tolist())
    rb = [0.3, 0.6, 1, 1.5, 2, 3, 4, 6, 8, 12, 1e9]
    h["residual_mm_where_ratio_gt_%g" % K_HI] = dict(edges=rb[:-1] + ["inf"], counts=np.histogram(R[Q > K_HI], rb)[0].tolist())
    h["residual_mm_where_ratio_lt_3"] = dict(edges=rb[:-1] + ["inf"], counts=np.histogram(R[Q < 3], rb)[0].tolist())
    h["percentiles_residual_mm"] = {str(p): round(float(np.percentile(R, p)), 3) for p in (50, 90, 99, 99.9)}
    return h


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--page-dir", required=True, help="the Base·F page dir (written with --write)")
    ap.add_argument("--src-dir", default=None, help="the Base·M page dir (Z-Anatomy source geometry), read only; default <page-dir>/../viewer_zan_atlas")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--allow-build", action="store_true", help="permit --write into build/ (the main thread's apply step)")
    ap.add_argument("--only", default=None, help="regex on structure ids (development; never with --write)")
    ap.add_argument("--json", default=str(OUT))
    a = ap.parse_args(argv)
    d = Path(a.page_dir).resolve()
    sd = Path(a.src_dir).resolve() if a.src_dir else d.parent / "viewer_zan_atlas"
    if a.write and "/build/" in str(d) + "/" and not a.allow_build:
        print("refused: never write into build/ without --allow-build (apply on a copy; the main thread applies)")
        return 2
    if a.only and a.write:
        print("refused: --only is for development runs")
        return 2
    if d == sd:
        print("refused: page and source are the same dir")
        return 2
    C340, C349 = _load()
    stem = C340.stem_of(d)
    if "female" not in stem:
        print(f"refused: {stem} is not Base·F (only Base·F carries the registration)")
        return 2
    man, blob, files = C340.read_page(d, stem)
    done = [m["id"] for m in man["meshes"] if TAG in (((m.get("rec") or {}).get("procedural_badge")) or "")]
    if done:
        print(f"Q366 already applied to this page ({len(done)} structures carry the Q366 note, e.g. {done[0]}); nothing done")
        return 0
    sman, sblob, _ = C340.read_page(sd, C340.stem_of(sd))
    t0 = time.time()
    V = {m["id"]: C340.dec(m, blob) for m in man["meshes"]}
    SM = {m["id"]: m for m in sman["meshes"]}
    sysof = {m["id"]: m.get("sys") for m in man["meshes"]}
    recs = {m["id"]: m.get("rec") for m in man["meshes"]}
    # ---- exclusions
    written = baseline_changed(d, stem, man, blob, C340)
    for m in man["meshes"]:
        tg = round_tags(m.get("rec"))
        if tg and m["id"] not in written:
            written[m["id"]] = "card carries a later round's note (%s)" % ",".join(tg)
    skipped, excluded, twins = {}, {}, {}
    for m in man["meshes"]:
        i = m["id"]; s = SM.get(i)
        if s is None:
            skipped[i] = "no Base·M structure of this id (rule-based or female-only)"; continue
        if (s["vc"], s["ic"]) != (m["vc"], m["ic"]):
            skipped[i] = "Base·M twin has another vertex / triangle count"; continue
        xs, fs = C340.dec(s, sblob)
        if not np.array_equal(fs, V[i][1]):
            skipped[i] = "Base·M twin has other triangles"; continue
        if m.get("sys") in EXCLUDE_SYS:
            excluded[i] = {"skin": "skin layer (slabs welded at load on identical border vertices, Q334)",
                           "bone": "bone: the reference layer of the in-bone test and of every contact round (measured, not moved)"}[m["sys"]]
        elif i in written:
            excluded[i] = "written by a later round: " + written[i]
        twins[i] = xs
    # ---- trees for frozen vertices: contact with an excluded structure (not bones: the bone guard covers them), shared borders
    ids = [m["id"] for m in man["meshes"]]
    allP = np.concatenate([V[i][0] for i in ids]); own = np.concatenate([np.full(len(V[i][0]), k) for k, i in enumerate(ids)])
    tree_all = cKDTree(allP)
    exc_ids = [i for i in ids if (i in excluded and sysof[i] != "bone") or (i in written)]
    exP = np.concatenate([V[i][0] for i in exc_ids]) if exc_ids else np.zeros((0, 3))
    exO = np.concatenate([np.full(len(V[i][0]), ids.index(i)) for i in exc_ids]) if exc_ids else np.zeros(0, int)
    tree_ex = cKDTree(exP) if len(exP) else None
    bones = BoneSet({i: V[i] for i in ids if sysof[i] == "bone"}, C349)
    print("Q366 %s: %d structures, %d with a same-topology Base·M twin, %d skipped, %d excluded (%.0f s)" % (
        stem, len(ids), len(twins), len(skipped), len(excluded), time.time() - t0), flush=True)
    # ---- per structure
    rep_s, replace, notes = {}, {}, {}
    Rall, Qall = [], []
    held, totals = {}, dict(examined=0, corrected=0, held=0, vertices_moved=0, frozen_vertices=0, patches=0, patches_rejected={})
    allmv = []
    for k, i in enumerate(ids):
        if i not in twins or i in excluded:
            continue
        if a.only and not re.search(a.only, i):
            continue
        XM, (XF, F) = twins[i], V[i]
        n = len(XM)
        frozen = np.zeros(n, bool)
        if tree_ex is not None:
            dd, jj = tree_ex.query(XF, k=1, distance_upper_bound=CONTACT)
            frozen |= np.isfinite(dd)
        dd, jj = tree_all.query(XF, k=6, distance_upper_bound=COINCIDENT)
        jj = np.where(np.isfinite(dd), jj, 0)
        frozen |= (np.isfinite(dd) & (own[jj] != k)).any(1)
        X1, fl, r0, sig, p, info = despike_structure(XM, XF, F, frozen)
        totals["examined"] += 1
        Rall.append(r0); Qall.append(r0 / sig)
        for w, c in info["rejected"].items():
            totals["patches_rejected"][w] = totals["patches_rejected"].get(w, 0) + c
        e = dict(sys=sysof[i], verts=n, residual_max_mm=round(float(r0.max()), 2), frozen=int(frozen.sum()), moved=int(fl.sum()))
        if info.get("frozen_seeds"):
            e["frozen_spike_seeds"] = info["frozen_seeds"]; totals["frozen_spike_seeds"] = totals.get("frozen_spike_seeds", 0) + info["frozen_seeds"]
        if info["rejected"]:
            e["patches_rejected"] = info["rejected"]
        if fl.any():
            # method step (not a guard): a patch whose correction would put a vertex into a bone, or deeper into one, is not corrected
            i0, _, d0 = bones.depth(XF[fl]); i1, nm1, d1 = bones.depth(X1[fl])
            bad = (i1 & ~i0) | (i1 & i0 & (d1 > d0 + BONE_TOL))
            if bad.any():
                badl = np.unique(info["label"][np.where(fl)[0][bad]])
                drop = fl & np.isin(info["label"], badl)
                e["patches_into_bone"] = dict(patches=int(len(badl)), vertices=int(drop.sum()), bones=sorted(set(nm1[bad])))
                fl = fl & ~drop; info["patches"] -= int(len(badl))
                X1 = XF.copy(); X1[fl] = p[fl]
                e["moved"] = int(fl.sum())
        if fl.any():
            mv = np.linalg.norm(X1 - XF, axis=1)[fl]
            e["move"] = stats(mv); e["patches"] = info["patches"]
            g = {}
            g["bone"] = guard_bone(bones, XF[fl], X1[fl])
            # reference size: the Base·M mesh carried through the smooth local maps (p: every vertex's own leave-one-out prediction),
            # so the female anisotropic scaling is in the reference and only the spikes are not
            s_ = umeyama_scale(XM, XF)
            ga = dict(scale_vs_source=round(s_, 4))
            a0, a1, aref = area(XF, F), area(X1, F), area(p, F)
            ga["area"] = size_check(a0, a1, aref)
            ok = ga["area"]["ok"]
            if closed(F):
                v0, v1, vref = volume(XF, F), volume(X1, F), volume(p, F)
                ga["volume"] = size_check(v0, v1, vref)
                ok = ok and ga["volume"]["ok"]
            ga["ok"] = bool(ok)
            g["size"] = ga
            fb, fa = flipped_vs_source(XM, XF, F, p), flipped_vs_source(XM, X1, F, p)
            g["flipped"] = dict(before=fb, after=fa, ok=bool(fa <= fb + FLIP_ADD))
            g["cap"] = dict(max_mm=e["move"]["max_mm"], cap_mm=CAP, ok=bool(e["move"]["max_mm"] <= CAP))
            e["guards"] = g
            fails = [x for x, v in g.items() if not v["ok"]]
            if fails:
                e["decision"] = "held: " + ", ".join(fails); e["moved"] = 0
                held[i] = fails; totals["held"] += 1
            else:
                e["decision"] = "corrected"
                totals["corrected"] += 1; totals["vertices_moved"] += int(fl.sum()); totals["patches"] += info["patches"]
                allmv.append(mv)
                replace[i] = X1; notes[i] = note_for(e)
        totals["frozen_vertices"] += int(frozen.sum())
        rep_s[i] = e
        if totals["examined"] % 250 == 0:
            print("  %d examined, %d corrected, %d held (%.0f s)" % (totals["examined"], totals["corrected"], totals["held"], time.time() - t0), flush=True)
    R, Q = np.concatenate(Rall), np.concatenate(Qall)
    mvall = np.concatenate(allmv) if allmv else np.zeros(0)
    totals["move"] = stats(mvall)
    totals["skipped_no_twin"] = len(skipped); totals["excluded"] = len(excluded)
    exc_by = {}
    for i, w in excluded.items():
        kx = w.split(":")[0]; exc_by[kx] = exc_by.get(kx, 0) + 1
    totals["excluded_by_reason"] = exc_by
    rep = {"schema": "nmsk.q366.despike.v1", "round": "Q366", "generated": time.strftime("%Y-%m-%d"), "page": stem, "written": bool(a.write),
           "source_page": C340.stem_of(sd),
           "parameters": dict(k=K, lam=LAMBDA, cauchy=CAUCHY, tukey=TUKEY, s_min_mm=S_MIN, irls=IRLS, passes=PASSES, t_hi_mm=T_HI, k_hi=K_HI, t_lo_mm=T_LO,
                              k_lo=K_LO, sigma_floor_mm=SIG_MIN, cap_mm=CAP, patch_max=PATCH_MAX, min_support=MIN_SUPPORT,
                              move_ratio=MOVE_RATIO, move_add_mm=MOVE_ADD, contact_mm=CONTACT, coincident_mm=COINCIDENT,
                              size_free_pct=SIZE_FREE, size_away_pct=SIZE_AWAY, flip_add=FLIP_ADD, bone_tol_mm=BONE_TOL),
           "totals": totals, "histograms": histograms(R, Q), "held": held,
           "skipped": skipped, "excluded": excluded, "structures": rep_s}
    print("Q366 totals: examined %d, corrected %d (%d vertices, %d patches), held %d, skipped %d, excluded %d; move max %.2f p95 %.2f mm" % (
        totals["examined"], totals["corrected"], totals["vertices_moved"], totals["patches"], totals["held"], len(skipped), len(excluded),
        totals["move"]["max_mm"], totals["move"]["p95_mm"]), flush=True)
    if replace:
        man2, blob2 = C340.repack(man, blob, {kk: (v, V[kk][1], C340.badge_add(recs[kk], notes[kk])) for kk, v in replace.items()})
        for m0, m1 in zip(man["meshes"], man2["meshes"]):
            assert m0["id"] == m1["id"] and m0["vc"] == m1["vc"] and m0["ic"] == m1["ic"]
        assert len(blob2) == len(blob)
        if a.write:
            rep["files_changed"] = write_page(d, stem, man, man2, blob2, files, C340)
            print("  wrote: " + ", ".join(rep["files_changed"]) + " (originals kept as *%s)" % SUFFIX)
            rig = REPO / "data/anatomy/pose_rig_base_f.json"
            if rig.exists():
                R0 = json.loads(rig.read_text(encoding="utf-8"))["rig"]
                ok = R0["count"] == len(man2["meshes"]) and R0["nv"] == [int(m["vc"]) for m in man2["meshes"]]
                rep["pose_rig"] = ("vertex counts and order unchanged: the rig (%s) still matches; no re-encode" % rig.relative_to(REPO)) if ok \
                    else "RIG OUT OF STEP with the page (it was before Q366 too: Q366 changes no count)"
                print("  pose rig: " + rep["pose_rig"])
    if a.write:
        jp = Path(a.json)
        jp.parent.mkdir(parents=True, exist_ok=True)
        jp.write_text(json.dumps(rep, indent=1, default=lambda o: o.tolist() if isinstance(o, np.ndarray) else (
            float(o) if isinstance(o, np.floating) else (int(o) if isinstance(o, np.integer) else str(o)))) + "\n", encoding="utf-8")
        print(f"  report -> {jp}")
    print(f"Q366 {'WRITTEN' if a.write else 'DRY RUN'} {stem}: {len(replace)} structures changed")
    return rep


if __name__ == "__main__":
    r = main()
    sys.exit(r if isinstance(r, int) else 0)
