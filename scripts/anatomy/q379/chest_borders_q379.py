#!/usr/bin/env python3
"""Q379: Base·F rebuilt chest skin (Q360) -- its free border vertices put ON the unchanged neighbour's border, so the load-time weld
joins them (weld, or the Q375 T-junction attach), without re-fitting the chest surface.

    python3 scripts/anatomy/q379/chest_borders_q379.py --page-dir DIR                 # dry run: plan + guards, writes nothing
    python3 scripts/anatomy/q379/chest_borders_q379.py --page-dir DIR --write         # and write the page files + report
    options: --cap MM (per-vertex move cap, default 4), --json FILE (report; default data/derived/Q379_chest_borders_report.json,
             written with --write or when given), --allow-build (permit --write into build/: the main thread's apply step),
             --no-under (skip the under-skin guard; development only, never with --write)

Cause (measured on the page): Q360 locked the chest's border vertices shared with an unchanged neighbour at that neighbour's
vertices, then subdivided the chest -- the vertices added between two locked ones lie near, not on, the neighbour's straight
border edge (0.04-1 mm off), so the engine (scripts/anatomy/q334/seams_weld_q334.js, steps 1 / 1b / 1c) joins nothing there:
in the axilla (lateral thorax | posterior and anterior arm, deltoid) the outer AND inner sheet run free between the locks, the
chest's wall there finds no twin and is drawn.
  sheets   a Q360 slab is [outer vertices | inner vertices] with inner = outer + nv; outer faces use only the first half, inner faces
           only the second, walls both (checked per slab; another layout is refused).
  runs     per chest slab and sheet: the sheet's border loops; a vertex is LOCKED when an unchanged (non-chest) skin vertex lies
           within the weld distance; a RUN is a maximal stretch of free vertices between two locked ones.
  target   the neighbours' border on the same sheet: the graph of every unchanged skin piece's rim edges (the engine's rim rule and its
           "along the border" test, vertices of different pieces within the weld distance merged); the shortest path between the run's
           two lock vertices is the neighbour's border polyline there.  Each interior polyline vertex takes ONE run vertex (an order-
           keeping assignment of least squared distance: those are welded); every other run vertex goes to its closest point on the
           polyline, kept in order and inside its edge (0.03 < t < 0.97: attached by step 1c).  Nothing else moves; no smoothing.
  quantise the page stores each mesh as 16-bit codes over its own box (manifest min / span, unchanged here): the moved vertex's code
           is the one of the 27 around the target whose decoded point lies nearest the target edge (or vertex), and the residual is
           measured after that round trip; unmoved vertices keep their bytes.
  guards   per run (a failing run keeps every vertex where it is, and is listed): no vertex moved > cap; path no longer than 1.6 x
           the run and every run vertex within cap of it; after the round trip every target <= 0.01 mm off its edge / vertex.
           Per slab: area change <= 1 %; no outer / inner face flipped or turned > 60 degrees.  Whole page (on the round-trip
           positions, through the engine in node): no border of a touched slab, or of a neighbour, loses joined vertices; no
           structure under the skin gains vertices outside it (Q353 outside_count, the Q353 / Q360 / Q377 test), breast tissue none.
  write    vertex / triangle counts and order unchanged (the pose rig still matches: no re-encode); originals copied beside as
           `<name>.q379` (never overwriting); each changed slab's card gets a "Q379: ..." note; a page with a Q379 note is refused.
"""
from __future__ import annotations

import argparse, json, re, subprocess, sys, time
from pathlib import Path

import numpy as np
from scipy import sparse
from scipy.sparse import csgraph
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
for _p in ("q340", "q375", "q377", "q366", "q353"):
    if str(HERE.parent / _p) not in sys.path:
        sys.path.insert(0, str(HERE.parent / _p))
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

OUT = REPO / "data/derived/Q379_chest_borders_report.json"
TAG = "Q379:"
SUFFIX = ".q379"
WELD_MM = 0.03        # the engine's weld / T-junction distance (Q334_WELD)
CAP = 4.0             # mm, per-vertex move cap (default)
T_MIN = 0.03          # a T-junction target stays this far (fraction of its edge) inside the edge; the engine wants 0.02 < t < 0.98
RESID_MAX = 0.01      # mm, after the 16-bit round trip
PATH_RATIO = 1.6      # neighbour polyline length / run length (a longer path is the wrong way round)
FACE_MM = 3.5         # a chest border vertex this close to an unchanged neighbour's border edge faces that neighbour (census)
BRIDGE_MM = 1.5       # rim vertices of two different neighbour pieces this close are bridged in the border graph (corners)
AREA_MAX = 1.0        # %, slab area change
TURN_COS = 0.5        # a face of a moved vertex may turn by up to 60 degrees
THICK_MIN = 0.5       # a moved vertex keeps at least this share of its distance to its partner on the other sheet
CHEST_RE = re.compile(r"mammary|pectoral_region|presternal|lateral_region_of_thorax|epigastric|infraclavicular|deltopectoral|"
                      r"hypochondriac")      # the Q360 regions (scripts/anatomy/q360/chest_skin_q360.py CHEST_RE)
SKIP = re.compile(r"^nail plate", re.I)
BREAST_EXTRA = ["breast_ct_r", "breast_ct_l", "breast_fgt_ct_r", "breast_fgt_ct_l"]


# ------------------------------------------------------------------ pure functions (tests/test_q379_chest_borders.py)
def seg_point(p, a, b):
    """closest point of segment a-b to p -> (t unclamped, t clamped, distance to the clamped point)"""
    ab = b - a
    ll = float(ab @ ab)
    if not ll > 0:
        return 0.0, 0.0, float(np.linalg.norm(p - a))
    t = float((p - a) @ ab / ll)
    tc = min(max(t, 0.0), 1.0)
    return t, tc, float(np.linalg.norm(p - (a + tc * ab)))


def polyline_project(p, Q):
    """closest point of polyline Q (m+1, 3) to p -> (arc length along Q, distance, segment index, t in segment)"""
    S = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(Q, axis=0), axis=1))]
    best = (np.inf, 0.0, 0, 0.0)
    for k in range(len(Q) - 1):
        _, tc, d = seg_point(p, Q[k], Q[k + 1])
        if d < best[0] - 1e-12:
            best = (d, S[k] + tc * (S[k + 1] - S[k]), k, tc)
    return best[1], best[0], best[2], best[3]


def at_arc(Q, s):
    """point of polyline Q at arc length s -> (point, segment, t)"""
    S = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(Q, axis=0), axis=1))]
    k = int(np.clip(np.searchsorted(S, s, side="right") - 1, 0, len(Q) - 2))
    ln = S[k + 1] - S[k]
    t = 0.0 if ln <= 0 else (s - S[k]) / ln
    return Q[k] + t * (Q[k + 1] - Q[k]), k, float(t)


def match_nodes(Pr, Q):
    """order-keeping assignment of the polyline's interior vertices Q[1:-1] to run points Pr (n, 3), each to a different point, least
    total squared distance; a node may stay unmatched (cost: 100 mm^2) when there are too few points -> {node k: point i}"""
    n, m = len(Pr), len(Q) - 2
    if m <= 0 or n == 0:
        return {}
    C = ((Pr[:, None, :] - Q[None, 1:-1, :]) ** 2).sum(-1)         # (n, m)
    SKIPC = 100.0
    D = np.full((n + 1, m + 1), np.inf)
    D[:, 0] = 0.0
    for j in range(1, m + 1):
        D[0, j] = D[0, j - 1] + SKIPC
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            D[i, j] = min(D[i - 1, j], D[i, j - 1] + SKIPC, D[i - 1, j - 1] + C[i - 1, j - 1])
    out, i, j = {}, n, m
    while j > 0:
        if i > 0 and np.isclose(D[i, j], D[i - 1, j - 1] + C[i - 1, j - 1]):
            out[j] = i - 1; i -= 1; j -= 1
        elif i > 0 and np.isclose(D[i, j], D[i - 1, j]):
            i -= 1
        else:
            j -= 1
    return out


def plan_run(Pr, Q, cap=CAP, tmin=T_MIN, attach=None, snap=True):
    """targets for an ordered run of free border points Pr (n, 3) between the two lock vertices Q[0], Q[-1] of the neighbour's border
    polyline Q.  attach: per segment of Q, True where it is a real edge of one piece (False: a bridge between two pieces' corner
    vertices -- nothing can attach there, a point is moved to a real edge when there is room, else lies on the bridge).  snap:
    interior vertices of Q each take one run point.  -> (list of dicts {target, kind: 'vertex' (onto Q[node]) | 'edge' (onto
    segment seg at t, tmin < t < 1-tmin) | 'bridge', move}, status 'ok' or the reason the whole run stays)"""
    n = len(Pr)
    if n == 0:
        return [], "ok"
    S = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(Q, axis=0), axis=1))]
    L = float(S[-1])
    if not L > 0:
        return [None] * n, "degenerate polyline"
    att = np.ones(len(Q) - 1, bool) if attach is None else np.asarray(attach, bool)
    arc = np.full(n, np.nan)
    kind = [None] * n
    for j, i in (match_nodes(Pr, Q) if snap else {}).items():      # node j (1..m) -> point i
        arc[i] = S[j]; kind[i] = ("vertex", j)
    sproj = np.array([polyline_project(p, Q)[0] for p in Pr])
    # the places a free point may go: the inside of every real edge, as arc intervals
    ok_iv = [(S[k] + tmin * (S[k + 1] - S[k]), S[k + 1] - tmin * (S[k + 1] - S[k])) for k in range(len(Q) - 1) if att[k] and S[k + 1] > S[k]]

    def nearest_ok(x, lo, hi):
        best = None
        for a_, b_ in ok_iv:
            a2, b2 = max(a_, lo), min(b_, hi)
            if a2 >= b2:
                continue
            y = min(max(x, a2), b2)
            if best is None or abs(y - x) < abs(best - x):
                best = y
        return best
    fixed = [(-1, 0.0)] + [(i, arc[i]) for i in range(n) if kind[i]] + [(n, L)]
    for (i0, s0), (i1, s1) in zip(fixed[:-1], fixed[1:]):
        free = list(range(i0 + 1, i1))
        if not free:
            continue
        if s1 <= s0:
            return [None] * n, "order"
        prev, gap = s0, 1e-3 * (s1 - s0)
        for c, i in enumerate(free):
            rest = len(free) - c - 1
            lo, hi = prev + gap, s1 - (rest + 1) * gap
            if lo >= hi:
                return [None] * n, "crowded"
            want = min(max(sproj[i], lo), hi)
            y = nearest_ok(want, lo, hi)
            if y is None:
                kind[i] = ("bridge", None)
            else:
                want = y; kind[i] = ("edge", None)
            arc[i] = want; prev = want
    out = []
    for i in range(n):
        if kind[i][0] == "vertex":
            j = kind[i][1]
            tgt = Q[j].copy(); rec = dict(kind="vertex", node=int(j))
        else:
            tgt, k, t = at_arc(Q, arc[i]); rec = dict(kind=kind[i][0], seg=int(k), t=float(t))
        rec.update(target=tgt, move=float(np.linalg.norm(tgt - Pr[i])))
        out.append(rec)
    if any(r["move"] > cap for r in out):
        return [None] * n, "cap"
    return out, "ok"


def encode(x, mn, span):
    """the page's 16-bit code of a position over its mesh box (scripts/zanatomy/build_zan_atlas_viewer.py pack_mesh)"""
    sp = np.where(np.asarray(span) <= 1e-9, 1.0, np.asarray(span, float))
    return np.clip(np.rint((np.asarray(x, float) - mn) / sp * 65535.0), 0, 65535).astype(np.int64)


def decode(q, mn, span):
    """as conform_palm_q340.dec / the viewer: min + q / 65535 * span"""
    return np.asarray(mn, float) + np.asarray(q, float) / 65535.0 * np.asarray(span, float)


def best_code(target, mn, span, a=None, b=None, tmin=0.02):
    """the code (of the 27 around the target's own) whose decoded point lies nearest the segment a-b, inside it (tmin < t < 1-tmin)
    -- or nearest the target point when no segment is given.  -> (code (3,), decoded point, residual mm); code None when the
    target lies outside the mesh box (the box would change: refused)"""
    mn = np.asarray(mn, float); span = np.asarray(span, float)
    sp = np.where(span <= 1e-9, 1.0, span)
    raw = (np.asarray(target, float) - mn) / sp * 65535.0
    if (raw < -0.5).any() or (raw > 65535.5).any():
        return None, None, np.inf
    q0 = np.rint(raw).astype(np.int64)
    best = (np.inf, None, None)
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for dz in (-1, 0, 1):
                q = q0 + (dx, dy, dz)
                if (q < 0).any() or (q > 65535).any():
                    continue
                p = decode(q, mn, span)
                if a is None:
                    d = float(np.linalg.norm(p - target))
                else:
                    t, _, d = seg_point(p, a, b)
                    if not (tmin < t < 1 - tmin):
                        continue
                if d < best[0]:
                    best = (d, q, p)
    return best[1], best[2], best[0]


# ------------------------------------------------------------------ mesh helpers
def q360_layout(P, F):
    """a Q360 slab: [outer | inner], inner = outer + nv, inner faces = outer faces reversed + nv -> (nv, outer mask, inner mask) or None"""
    n = len(P)
    if n % 2:
        return None
    nv = n // 2
    o = (F < nv).all(1); i = (F >= nv).all(1)
    if o.sum() != i.sum() or o.sum() == 0:
        return None
    a = {tuple(sorted(t)) for t in F[o].tolist()}
    b = {tuple(sorted(t)) for t in (F[i] - nv).tolist()}
    return (nv, o, i) if a == b else None


def border_loops(F):
    """ordered border loops (vertex lists) of a face set (edges used once)"""
    E = np.sort(np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]]), 1)
    u, c = np.unique(E, axis=0, return_counts=True)
    adj = {}
    for a, b in u[c == 1]:
        adj.setdefault(int(a), []).append(int(b)); adj.setdefault(int(b), []).append(int(a))
    seen, loops = set(), []
    for s in sorted(adj):
        if s in seen:
            continue
        ch, prev, cur = [s], None, s
        seen.add(s)
        while True:
            nx = [x for x in adj[cur] if x != prev and x not in seen]
            if not nx:
                break
            prev, cur = cur, nx[0]
            ch.append(cur); seen.add(cur)
        loops.append(ch)
    return loops


def runs_of(loop, locked):
    """maximal stretches of unlocked vertices between two locked ones in a closed loop -> [(lock a, [free...], lock b)]"""
    n = len(loop)
    li = [k for k in range(n) if locked[loop[k]]]
    if not li:
        return []
    out = []
    for c, k in enumerate(li):
        k2 = li[(c + 1) % len(li)]
        span = (k2 - k) % n if len(li) > 1 else n
        free = [loop[(k + j) % n] for j in range(1, span)]
        if free:
            out.append((loop[k], free, loop[k2]))
    return out


def area(P, F):
    return float(np.linalg.norm(np.cross(P[F[:, 1]] - P[F[:, 0]], P[F[:, 2]] - P[F[:, 0]]), axis=1).sum() / 2)


def fnormals(P, F):
    n = np.cross(P[F[:, 1]] - P[F[:, 0]], P[F[:, 2]] - P[F[:, 0]])
    return n / np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)


# ------------------------------------------------------------------ engine (node) census
def engine(SK, tmp, names):
    """the engine's weld on all skin pieces -> {id: (roots, seam)} (scripts/anatomy/q377/weld_roots_q377.js)"""
    import skin_q377 as S7
    return S7.weld_roots([(i, names.get(i, i), SK[i][0], SK[i][1]) for i in SK], tmp)


def border_census(SK, W, chest, BC):
    """per (chest slab, neighbour) and (neighbour, chest slab): border vertices (the Q375 rule: rim vertices within 1.5 mm of the
    other's surface) and how many the engine joined to that piece (same weld root, or attached to its edge: a seam root no other
    piece shares) -> {"A|B": [joined, border]}"""
    from collections import Counter
    ids = list(SK)
    roots = {i: set(W[i][0].tolist()) for i in ids}
    RC = Counter()
    for i in ids:
        RC.update(roots[i])
    lo = {i: SK[i][0].min(0) - 3 for i in ids}; hi = {i: SK[i][0].max(0) + 3 for i in ids}
    out = {}
    for A in chest:
        for B in ids:
            if B == A or (lo[B] > hi[A]).any() or (hi[B] < lo[A]).any():
                continue
            for K, Lp in ((A, B), (B, A)):
                key = f"{K}|{Lp}"
                if key in out:
                    continue
                ia = BC.classify(*SK[K], *SK[Lp])["border"]
                if len(ia) < 2:
                    continue
                r, s = W[K]
                j = sum(1 for v in ia if r[v] in roots[Lp] or (s[v] and RC[r[v]] == 1))
                out[key] = [int(j), int(len(ia))]
    return out


# ------------------------------------------------------------------ main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--page-dir", required=True, help="the Base·F page dir (written with --write)")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--allow-build", action="store_true", help="permit --write into build/ (the main thread's apply step)")
    ap.add_argument("--cap", type=float, default=CAP)
    ap.add_argument("--json", default=None)
    ap.add_argument("--no-under", action="store_true", help="skip the under-skin guard (development only; never with --write)")
    ap.add_argument("--tmp", default=None, help="scratch dir for the engine run (default: <page-dir>/../.q379_tmp, removed)")
    a = ap.parse_args(argv)
    d = Path(a.page_dir).resolve()
    if a.write and "/build/" in str(d) + "/" and not a.allow_build:
        print("refused: never write into build/ without --allow-build (apply on a copy; the main thread applies)")
        return 2
    if a.write and a.no_under:
        print("refused: --no-under is for development runs")
        return 2
    import conform_palm_q340 as C340
    import border_census_q375 as BC
    stem = C340.stem_of(d)
    if "female" not in stem:
        print(f"refused: {stem} is not Base·F")
        return 2
    man, blob, files = C340.read_page(d, stem)
    MM = {m["id"]: m for m in man["meshes"]}
    done = [k for k, m in MM.items() if TAG in (((m.get("rec") or {}).get("procedural_badge")) or "")]
    if done:
        print(f"Q379 already applied to this page ({len(done)} slabs carry the Q379 note, e.g. {done[0]}); nothing done")
        return 0
    t0 = time.time()
    SK = {k: C340.dec(m, blob) for k, m in MM.items() if m.get("sys") == "skin" and not SKIP.match(m.get("name", ""))}
    names = {k: m.get("name", k) for k, m in MM.items()}
    chest = sorted(k for k in SK if k.startswith("zan_skin") and CHEST_RE.search(k))
    if len(chest) != 18:
        print(f"refused: expected the 18 Q360 chest slabs, found {len(chest)}")
        return 2
    lay = {k: q360_layout(*SK[k]) for k in chest}
    bad = [k for k, v in lay.items() if v is None]
    if bad:
        print(f"refused: not the Q360 slab layout: {bad}")
        return 2
    others = [k for k in SK if k not in chest]
    # ---- the neighbours' border graph: rim edges along the border, vertices of different pieces within WELD_MM merged
    offs, PP, EE, OWN = {}, [], [], []
    n0 = 0
    for k in others:
        P, F = SK[k]
        r, vn = BC.rim_vertices(P, F)
        E = BC.rim_edges(P, F, r, vn)
        offs[k] = n0; PP.append(P); EE.append(E + n0); OWN.append(np.full(len(P), len(OWN)))
        n0 += len(P)
    GP = np.concatenate(PP); GE = np.concatenate(EE)
    gpairs = cKDTree(GP).query_pairs(WELD_MM, output_type="ndarray")
    _, lab = csgraph.connected_components(sparse.coo_matrix((np.ones(len(gpairs)), (gpairs[:, 0], gpairs[:, 1])), shape=(n0, n0)),
                                          directed=False)
    nodeP = np.zeros((lab.max() + 1, 3)); np.add.at(nodeP, lab, GP); nodeP /= np.bincount(lab)[:, None]
    ew = np.linalg.norm(GP[GE[:, 0]] - GP[GE[:, 1]], axis=1)
    NN = lab.max() + 1
    # bridges: the inner border of two neighbouring Z pieces is cut at different vertices (up to ~1.2 mm apart at a corner): rim
    # nodes of different pieces within BRIDGE_MM are joined by a bridge segment (on the path, but nothing attaches to it)
    nown = np.full(NN, -1); nown[lab] = np.concatenate(OWN)
    rimnode = np.zeros(NN, bool); rimnode[lab[GE.ravel()]] = True
    rn = np.where(rimnode)[0]
    bp = cKDTree(nodeP[rn]).query_pairs(BRIDGE_MM, output_type="ndarray")
    bp = rn[bp] if len(bp) else np.zeros((0, 2), int)
    bp = bp[nown[bp[:, 0]] != nown[bp[:, 1]]] if len(bp) else bp
    bw = np.linalg.norm(nodeP[bp[:, 0]] - nodeP[bp[:, 1]], axis=1) if len(bp) else np.zeros(0)
    ri = np.r_[lab[GE[:, 0]], lab[GE[:, 1]], bp[:, 0], bp[:, 1]]; ci = np.r_[lab[GE[:, 1]], lab[GE[:, 0]], bp[:, 1], bp[:, 0]]
    G = sparse.coo_matrix((np.r_[ew, ew, bw, bw], (ri, ci)), shape=(NN, NN)).tocsr()
    gtree = cKDTree(GP)
    # an edge of the graph -> one real piece edge (the engine attaches a vertex to a piece's own edge)
    edge_of = {}
    for (u, v) in GE:
        edge_of.setdefault((int(lab[u]), int(lab[v])), (int(u), int(v))); edge_of.setdefault((int(lab[v]), int(lab[u])), (int(v), int(u)))
    piece_of = np.concatenate(OWN); oname = others

    ctree = {k: cKDTree(np.concatenate([SK[c][0] for c in chest if c != k])) for k in chest}
    plan, refused, X1, runs_all = {}, [], {k: SK[k][0].copy() for k in chest}, []
    codes = {}
    for sheet in ("outer", "inner"):
        # the merged chest sheet: every chest slab's faces of this sheet, its vertices shared by two slabs (within WELD_MM) one node
        cop, FF = [], []
        for k in chest:
            nv, om, im = lay[k]
            vs = np.arange(nv) if sheet == "outer" else np.arange(nv, 2 * nv)
            base = len(cop); cop += [(k, int(v)) for v in vs]
            FF.append(SK[k][1][om if sheet == "outer" else im] - vs[0] + base)
        CP = np.array([SK[k][0][v] for k, v in cop])
        pr = cKDTree(CP).query_pairs(WELD_MM, output_type="ndarray")
        _, cl = csgraph.connected_components(sparse.coo_matrix((np.ones(len(pr)), (pr[:, 0], pr[:, 1])), shape=(len(CP), len(CP))),
                                             directed=False)
        copies = {}
        for g_, cl_ in enumerate(cl):
            copies.setdefault(int(cl_), []).append(cop[g_])
        MF = cl[np.concatenate(FF)]
        MF = MF[(MF[:, 0] != MF[:, 1]) & (MF[:, 1] != MF[:, 2]) & (MF[:, 0] != MF[:, 2])]
        NP = np.zeros((cl.max() + 1, 3)); NP[cl] = CP
        for loop in border_loops(MF):
            dl, jl = gtree.query(NP[loop], distance_upper_bound=WELD_MM)
            locked = {v: (int(lab[j]) if np.isfinite(dd) else None) for v, dd, j in zip(loop, dl, jl)}
            for va, free, vb in runs_of(loop, {v: locked[v] is not None for v in loop}):
                na, nb = locked[va], locked[vb]
                slabs_r = sorted({k for v in free for k, _ in copies[v]})
                rec = dict(sheet=sheet, slabs=slabs_r, n=len(free), corner_vertices=int(sum(len(copies[v]) > 1 for v in free)),
                           free=[[list(c_) for c_ in copies[v]] for v in free])
                run_len = float(np.linalg.norm(np.diff(NP[[va] + free + [vb]], axis=0), axis=1).sum())
                rec["lock_pieces"] = [oname[piece_of[np.where(lab == na)[0][0]]], oname[piece_of[np.where(lab == nb)[0][0]]]]
                dist, pred = csgraph.dijkstra(G, indices=na, return_predecessors=True)
                if na == nb or not np.isfinite(dist[nb]):
                    ca_, cb_ = (np.isfinite(csgraph.dijkstra(G, indices=x_, limit=60.0)) for x_ in (na, nb))
                    rec["gap_mm"] = round(float(cKDTree(nodeP[ca_]).query(nodeP[cb_])[0].min()), 2)
                    rec["status"] = "no neighbour path"; refused.append(rec); continue
                path = [nb]
                while path[-1] != na:
                    path.append(int(pred[path[-1]]))
                path = path[::-1]
                Q = nodeP[path]
                Q[0], Q[-1] = NP[va], NP[vb]          # the lock vertices themselves (within the weld distance of the nodes)
                rec["path_len_mm"] = round(float(dist[nb]), 2); rec["run_len_mm"] = round(run_len, 2)
                rec["neighbours"] = sorted({oname[piece_of[edge_of[(path[q], path[q + 1])][0]]] for q in range(len(path) - 1)
                                            if (path[q], path[q + 1]) in edge_of})
                if dist[nb] > PATH_RATIO * run_len + 1.0:
                    rec["status"] = "path too long"; refused.append(rec); continue
                attach = [(path[q], path[q + 1]) in edge_of for q in range(len(path) - 1)]
                rec["off_mm"] = [round(polyline_project(p, Q)[1], 3) for p in NP[free]]
                fis = {}
                for k in slabs_r:
                    nv, om, im = lay[k]
                    vk = [v for f_ in free for kk, v in copies[f_] if kk == k]
                    fis[k] = (vk, np.where(np.isin(SK[k][1], vk).any(1) & (om | im))[0])      # sheet faces (a wall turns with its border)
                st, mv = "no plan", []
                for snap in (True, False):
                    tg, st = plan_run(NP[free], Q, cap=a.cap, attach=attach, snap=snap)
                    if st != "ok":
                        continue
                    mv = []
                    for f_, t in zip(free, tg):
                        for k, v in copies[f_]:
                            m = MM[k]
                            if t["kind"] == "edge":
                                ga, gb = edge_of[(path[t["seg"]], path[t["seg"] + 1])]
                                code, dec_p, res = best_code(t["target"], m["min"], m["span"], GP[ga], GP[gb])
                            else:
                                code, dec_p, res = best_code(t["target"], m["min"], m["span"])
                            if code is None or (t["kind"] != "bridge" and res > RESID_MAX):
                                st = "outside the mesh box" if code is None else f"round trip {res:.4f} mm"
                                break
                            mv.append((k, v, code, dec_p, res, t))
                        if st != "ok":
                            break
                    if st != "ok":
                        continue
                    Xt = {k: X1[k].copy() for k in slabs_r}
                    for k, v, code, dec_p, res, t in mv:
                        Xt[k][v] = dec_p
                    worst_c, worst_t = 1.0, 1.0
                    for k in slabs_r:
                        nv = lay[k][0]; vk, fi = fis[k]
                        if len(fi):
                            worst_c = min(worst_c, float((fnormals(X1[k], SK[k][1][fi]) * fnormals(Xt[k], SK[k][1][fi])).sum(1).min()))
                        fv = np.array(vk); pv = np.where(fv < nv, fv + nv, fv - nv)      # each vertex's partner on the other sheet
                        th0 = np.linalg.norm(X1[k][fv] - X1[k][pv], axis=1); th1 = np.linalg.norm(Xt[k][fv] - Xt[k][pv], axis=1)
                        worst_t = min(worst_t, float((th1 / np.maximum(th0, 1e-9)).min()))
                    rec["min_face_cos"], rec["min_thickness_share"] = round(worst_c, 3), round(worst_t, 3)
                    if worst_c < TURN_COS:
                        st = f"face turned (cos {worst_c:.2f})"; continue
                    if worst_t < THICK_MIN:
                        st = f"sheets closer (thickness share {worst_t:.2f})"; continue
                    rec["snapped"] = snap
                    break
                if st != "ok":
                    rec["status"] = st; rec["max_off_mm"] = max(rec["off_mm"]); refused.append(rec); continue
                for k, v, code, dec_p, res, t in mv:
                    X1[k][v] = dec_p; codes.setdefault(k, {})[v] = code
                tg_by = [t for t in tg]
                rec.update(status="ok", moves_mm=[round(t["move"], 3) for t in tg_by], kinds=[t["kind"] for t in tg_by],
                           residual_mm=[round(r_, 4) for *_, r_, t in mv if t["kind"] != "bridge"])
                runs_all.append(rec)
                for k in slabs_r:
                    plan.setdefault(k, []).append(rec)
    mvall = np.array([x for r in runs_all for x in r["moves_mm"]])
    resall = np.array([x for r in runs_all for x in r["residual_mm"]])
    print(f"Q379 {stem}: {len(runs_all)} runs planned on {len(plan)} slabs, {len(mvall)} vertices "
          f"(move max {mvall.max() if len(mvall) else 0:.2f} p95 {np.percentile(mvall, 95) if len(mvall) else 0:.2f} mm, "
          f"residual after round trip max {resall.max() if len(resall) else 0:.4f} mm); refused runs {len(refused)} ({time.time() - t0:.0f} s)",
          flush=True)
    for r in refused:
        print(f"   refused {[x[9:] for x in r['slabs']]} {r['sheet']} {r['n']} vertices: {r['status']} {r.get('lock_pieces', '')} "
              f"off max {r.get('max_off_mm', '')} gap {r.get('gap_mm', '')}")

    # ---- per slab guards: area, faces turned
    slabs = {}
    for k in plan:
        P0, F = SK[k]
        a0, a1 = area(P0, F), area(X1[k], F)
        mv = np.array(sorted(codes[k]))
        nv_, om_, im_ = lay[k]
        fi = np.where(np.isin(F, mv).any(1) & (om_ | im_))[0]
        cs = (fnormals(P0, F[fi]) * fnormals(X1[k], F[fi])).sum(1)
        slabs[k] = dict(moved=int(len(mv)), area_change_pct=round(100 * (a1 - a0) / a0, 4), faces_touched=int(len(fi)),
                        min_face_cos=round(float(cs.min()), 3) if len(cs) else 1.0,
                        ok=bool(abs(100 * (a1 - a0) / a0) <= AREA_MAX and (not len(cs) or cs.min() >= TURN_COS)))
    bad_slabs = [k for k, s in slabs.items() if not s["ok"]]

    # ---- engine census before / after (node)
    import shutil, tempfile
    tmp = Path(a.tmp) if a.tmp else Path(tempfile.mkdtemp(prefix="q379_"))
    tmp.mkdir(parents=True, exist_ok=True)
    SK1 = dict(SK); SK1.update({k: (X1[k], SK[k][1]) for k in plan})
    W0 = engine(SK, tmp, names); W1 = engine(SK1, tmp, names)
    cen0 = border_census(SK, W0, chest, BC); cen1 = border_census(SK1, W1, chest, BC)
    borders, lost = {}, []
    for key in sorted(set(cen0) | set(cen1)):
        b0, b1 = cen0.get(key, [0, 0]), cen1.get(key, [0, 0])
        borders[key.replace("zan_skin_", "")] = dict(before=b0, after=b1)
        A_, B_ = key.split("|")
        if (A_ in chest) != (B_ in chest) or A_ in plan or B_ in plan:
            if b1[0] < b0[0]:
                lost.append(key.replace("zan_skin_", ""))

    def open_free(SKx, Wx):
        """chest border-loop vertices (both sheets) facing an unchanged neighbour that the engine left open"""
        from collections import Counter
        RC = Counter()
        for i in SKx:
            RC.update(Wx[i][0].tolist())
        rootsN = set().union(*[set(Wx[i][0].tolist()) for i in others])
        per = {}
        for k in chest:
            P, F = SKx[k]; nv, om, im = lay[k]
            for fm in (om, im):
                for loop in border_loops(F[fm]):
                    dn = etree.query(P[loop])[0]
                    dc = ctree[k].query(SK[k][0][loop])[0]
                    for v, dd, d2 in zip(loop, dn, dc):
                        if dd > FACE_MM or d2 <= WELD_MM:
                            continue      # faces another chest slab (shared with it) or nothing: not a border with an unchanged one
                        r, s = Wx[k][0][v], Wx[k][1][v]
                        if not (r in rootsN or (s and RC[r] == 1)):
                            nb = oname[piece_of[gtree.query(P[v])[1]]]
                            per.setdefault(f"{k[9:]}|{nb[9:]}", 0)
                            per[f"{k[9:]}|{nb[9:]}"] += 1
        return per
    # the neighbours' border edges, sampled every 0.25 mm (distance of a chest border vertex to an unchanged neighbour's border)
    sm = [GP[GE[:, 0]] + t_ * (GP[GE[:, 1]] - GP[GE[:, 0]]) for t_ in np.linspace(0, 1, 1 + int(np.ceil(ew.max() / 0.25)))]
    etree = cKDTree(np.concatenate(sm))
    of0, of1 = open_free(SK, W0), open_free(SK1, W1)
    print(f"  engine: chest border vertices facing an unchanged neighbour left open {sum(of0.values())} -> {sum(of1.values())}")
    for kk in sorted(set(of0) | set(of1)):
        print(f"     {kk:60s} {of0.get(kk, 0):3d} -> {of1.get(kk, 0):3d}")
    if lost:
        print("  BORDER SHARE LOST: " + ", ".join(lost))

    # ---- under-skin guard (Q353 outside_count) on the chest box
    under = None
    if not a.no_under and plan:
        import conform_skin_q353 as Q
        g = Q.Geo(d)
        lo = np.min([X1[k].min(0) for k in plan], 0) - 20; hi = np.max([X1[k].max(0) for k in plan], 0) + 20
        skin_ids = [kk for kk in g.in_box(lo, hi, sys_=("skin",)) if not SKIP.match(names.get(kk, ""))]
        und = [kk for kk in g.in_box(lo, hi, sys_=Q.VISIBLE_SYS)] + [kk for kk in Q.BREAST + BREAST_EXTRA if kk in g.M]
        und = sorted(set(und))
        sk0 = Q.SkinSet(g, skin_ids)
        o0 = {kk: Q.outside_count(g, sk0, kk)["outside"] for kk in und}
        for k in plan:
            g.cur[k] = X1[k]
        sk1 = Q.SkinSet(g, skin_ids)
        o1 = {kk: Q.outside_count(g, sk1, kk)["outside"] for kk in und}
        gained = {kk: [o0[kk], o1[kk]] for kk in und if o1[kk] > o0[kk]}
        breast = {kk: o1[kk] for kk in Q.BREAST + BREAST_EXTRA if kk in o1 and o1[kk] > 0}
        under = dict(structures=len(und), outside_before=int(sum(o0.values())), outside_after=int(sum(o1.values())), gained=gained,
                     breast_outside_after=breast, ok=not gained and not breast)
        print(f"  under the skin: {len(und)} structures, outside {under['outside_before']} -> {under['outside_after']}; gained {gained}; "
              f"breast tissue outside after {breast}")
    if not a.tmp:
        shutil.rmtree(tmp, ignore_errors=True)

    ok = not bad_slabs and not lost and (under is None or under["ok"])
    rep = {"schema": "nmsk.q379.chest_borders.v1", "round": "Q379", "generated": time.strftime("%Y-%m-%d"), "page": stem,
           "written": False,
           "parameters": dict(weld_mm=WELD_MM, cap_mm=a.cap, t_min=T_MIN, residual_max_mm=RESID_MAX, path_ratio=PATH_RATIO,
                              area_max_pct=AREA_MAX, turn_cos=TURN_COS),
           "totals": dict(runs=sum(len(v) for v in plan.values()), slabs=len(plan), vertices_moved=int(len(mvall)),
                          to_vertex=int(sum(r["kinds"].count("vertex") for k in plan for r in plan[k])),
                          to_edge=int(sum(r["kinds"].count("edge") for k in plan for r in plan[k])),
                          move=dict(max_mm=round(float(mvall.max()), 3) if len(mvall) else 0.0,
                                    p95_mm=round(float(np.percentile(mvall, 95)), 3) if len(mvall) else 0.0,
                                    p50_mm=round(float(np.median(mvall)), 3) if len(mvall) else 0.0),
                          residual_after_round_trip=dict(max_mm=round(float(resall.max()), 5) if len(resall) else 0.0,
                                                         p95_mm=round(float(np.percentile(resall, 95)), 5) if len(resall) else 0.0,
                                                         p50_mm=round(float(np.median(resall)), 5) if len(resall) else 0.0),
                          open_facing_neighbour=dict(before=int(sum(of0.values())), after=int(sum(of1.values())))),
           "open_facing_neighbour": dict(before=of0, after=of1), "refused_runs": refused, "slabs": slabs,
           "runs": {k: v for k, v in plan.items()}, "borders": borders, "border_share_lost": lost, "under_skin": under,
           "guards_ok": bool(ok)}
    if a.write and ok and plan:
        blob2 = bytearray(blob)
        for k, cv in codes.items():
            m = MM[k]
            for v, code in cv.items():
                blob2[m["vo"] + 6 * v: m["vo"] + 6 * v + 6] = np.asarray(code, "<u2").tobytes()
        man2 = json.loads(json.dumps(man))
        for m in man2["meshes"]:
            if m["id"] in plan:
                s = slabs[m["id"]]
                mv = [x for r in plan[m["id"]] for x in r["moves_mm"]]
                nb = sorted({n_[9:].replace("_", " ") for r in plan[m["id"]] for n_ in r["neighbours"]})
                m["rec"] = C340.badge_add(m.get("rec") or {}, (
                    f"{TAG} {s['moved']} border vertices of this rebuilt region (Q360) moved onto the unchanged neighbouring region's own "
                    f"border ({', '.join(nb)}), so the two regions join there (move max {max(mv):.2f} mm); nothing else moved, "
                    f"the surface was not re-fitted."))
        import despike_q366 as D
        old = D.SUFFIX
        try:
            D.SUFFIX = SUFFIX
            rep["files_changed"] = D.write_page(d, stem, man, man2, bytes(blob2), files, C340)
        finally:
            D.SUFFIX = old
        rep["written"] = True
        # check: what the page now holds is what was planned
        man3, blob3, _ = C340.read_page(d, stem)
        for m in man3["meshes"]:
            if m["id"] in plan:
                assert np.abs(C340.dec(m, blob3)[0] - X1[m["id"]]).max() < 1e-9
        rig = REPO / "data/anatomy/pose_rig_base_f.json"
        if rig.exists():
            R0 = json.loads(rig.read_text(encoding="utf-8"))["rig"]
            okr = R0["count"] == len(man3["meshes"]) and R0["nv"] == [int(m["vc"]) for m in man3["meshes"]]
            rep["pose_rig"] = ("vertex counts and order unchanged: the rig still matches; no re-encode" if okr
                               else "RIG OUT OF STEP with the page (Q379 changes no count)")
            print("  pose rig: " + rep["pose_rig"])
        print("  wrote: " + ", ".join(rep["files_changed"]) + f" (originals kept as *{SUFFIX})")
    if a.write or a.json:
        jp = Path(a.json or OUT)
        jp.parent.mkdir(parents=True, exist_ok=True)
        jp.write_text(json.dumps(rep, indent=1, default=lambda o: o.tolist() if isinstance(o, np.ndarray) else (
            float(o) if isinstance(o, np.floating) else (int(o) if isinstance(o, np.integer) else str(o)))) + "\n", encoding="utf-8")
        print(f"  report -> {jp}")
    print(f"Q379 {'WRITTEN' if rep['written'] else ('GUARD_FAIL' if not ok else 'DRY RUN')} {stem}: {len(plan)} slabs, "
          f"{len(mvall)} vertices")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
