#!/usr/bin/env python3
"""Q377: Base·F skin -- census of the Z skin slabs against the real Base·M mesh, and a guarded de-spike / border rejoin.

    python3 scripts/anatomy/q377/skin_q377.py --page-dir DIR [--src-dir DIR]            # dry run: census + plan, writes nothing
    python3 scripts/anatomy/q377/skin_q377.py --page-dir DIR --write                    # and write the page files + report
    options: --json FILE (report; default data/derived/Q377_skin_report.json, written with --write or when given),
             --allow-build (permit --write into build/: the main thread's apply step), --no-under (skip the under-skin guard; dev)

Every Base·F skin slab (`zan_skin_*`, nail plates out) with a same-topology twin on Base·M carries a per-vertex correspondence x_M -> x_F.
Q366 excluded the skin (shared borders must stay shared); Q377 measures it as ONE surface:
  map      Q366's robust leave-one-out local map (imported, not copied), fitted over ALL twin skin slabs together: a slab is a
           2.7 mm thick closed shell of a few hundred vertices, so a map over its own vertices alone is not local (its K=64
           neighbours span the whole slab); over the whole skin the 64 neighbours lie within a few cm and cross the borders.
  spikes   Q366's hysteresis flag (seed r > 1 mm and > 10 sigma) and patch checks (<= 12 vertices, supported, stable).
  borders  (a) every pair of vertices of two slabs within WELD_MM on Base·M (the engine welds them at load): still within WELD_MM on
           Base·F?  (b) every mutually nearest pair of RIM vertices of two slabs 0.03..RIM_MM apart on Base·M (the engine's rim join,
           Q334 1b): still within RIM_MM on Base·F?  (c) the Q360 chest slabs (no twin) against their twin neighbours: the Q375 border
           classes (shared / T-junction / offset / other).
  move     a spike vertex goes to its own Base·M position through the local warp of its unflagged neighbours (Q366).  Vertices
           coincident on Base·M (a shared border) move as ONE: to the mean of their new positions when all are spikes; when only some
           are, the group stays where it is if it is still joined on Base·F, else the spikes go to the unspiked member.  A separated
           coincident pair with no spike goes to the mean of the two local-map predictions (both sides move).  A vertex coincident with a
           slab that has no twin (the Q360 chest, Q358 perineum) is frozen.  Nothing else moves; no smoothing; nothing invented.
  guards   per slab (a failing slab is left exactly as it is, with every vertex tied to it across a border, and listed): no vertex
           moved > CAP mm; slab area change <= AREA_MAX %; the sheets keep their thickness (a moved vertex's distance to the other sheet
           ends within THICK_TOL of Base·M's, scaled, or nearer to it than before); every border of the slab keeps its joined share
           (weld + rim join + T-junction, the engine's rules) or gains; no structure under the skin gains vertices outside it (Q353's
           outside_count, the same test as its tuck guard).
  write    vertex / triangle counts and order unchanged (pose rig contract); originals copied beside as `<name>.q377` (never
           overwriting); each changed slab's card gets a "Q377: ..." note; a page with a Q377 note is refused.  Deterministic.
"""
from __future__ import annotations

import argparse, json, re, sys, time
from pathlib import Path

import numpy as np
from scipy import sparse
from scipy.sparse import csgraph
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
for _p in ("q366", "q375", "q340", "q353"):
    if str(HERE.parent / _p) not in sys.path:
        sys.path.insert(0, str(HERE.parent / _p))
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))
import despike_q366 as D           # noqa: E402  local map, flag, despike_structure, area, write_page, stats
import border_census_q375 as BC    # noqa: E402  rim rule, classify

OUT = REPO / "data/derived/Q377_skin_report.json"
TAG = "Q377:"
SUFFIX = ".q377"
WELD_MM = 0.03       # the engine's weld distance (Q334_WELD)
RIM_MM = 1.0         # the engine's rim-join distance (Q334_RIM)
CAP = 12.0           # mm, per-vertex move cap
AREA_MAX = 2.0       # %, slab area change
THICK_TOL = 0.5      # mm
GAIN_TOL = 0         # vertices a structure under the skin may newly have outside it
SKIP = re.compile(r"^nail plate", re.I)


# ------------------------------------------------------------------ pure functions (tests/test_q377_skin.py)
def coincident_groups(P_list, tol=WELD_MM):
    """vertices of different meshes within tol of each other (chained): -> (pairs (m, 4) [mesh a, vert a, mesh b, vert b], groups:
    list of arrays of (mesh, vert))"""
    P = np.concatenate(P_list)
    O = np.concatenate([np.full(len(p), k) for k, p in enumerate(P_list)])
    L = np.concatenate([np.arange(len(p)) for p in P_list])
    pr = cKDTree(P).query_pairs(tol, output_type="ndarray")
    pr = pr[O[pr[:, 0]] != O[pr[:, 1]]] if len(pr) else np.zeros((0, 2), int)
    n = len(P)
    _, lab = csgraph.connected_components(sparse.coo_matrix((np.ones(len(pr)), (pr[:, 0], pr[:, 1])), shape=(n, n)), directed=False)
    inpair = np.zeros(n, bool); inpair[pr.ravel()] = True
    groups = {}
    for g in np.where(inpair)[0]:
        groups.setdefault(lab[g], []).append((O[g], L[g]))
    pairs = np.stack([O[pr[:, 0]], L[pr[:, 0]], O[pr[:, 1]], L[pr[:, 1]]], 1) if len(pr) else np.zeros((0, 4), int)
    return pairs, [np.array(v) for v in groups.values()]


def rim_pairs(P_list, rim_list, lo=WELD_MM, hi=RIM_MM):
    """mutually nearest rim vertices of two different meshes lo < d <= hi apart -> (m, 5) [mesh a, vert a, mesh b, vert b, d]"""
    P = np.concatenate([p[r] for p, r in zip(P_list, rim_list)])
    O = np.concatenate([np.full(int(r.sum()), k) for k, r in enumerate(rim_list)])
    L = np.concatenate([np.where(r)[0] for r in rim_list])
    if len(P) < 2:
        return np.zeros((0, 5))
    t = cKDTree(P)
    d, j = t.query(P, k=min(12, len(P)))
    best = np.full(len(P), -1); bd = np.full(len(P), np.inf)
    for c in range(1, d.shape[1]):
        ok = (O[j[:, c]] != O) & (d[:, c] < bd) & (best < 0)
        best[ok] = j[ok, c]; bd[ok] = d[ok, c]
    out = []
    for a in range(len(P)):
        b = best[a]
        if b > a and best[b] == a and lo < bd[a] <= hi:
            out.append((O[a], L[a], O[b], L[b], bd[a]))
    return np.array(out) if out else np.zeros((0, 5))


def group_targets(groups, X0, X1, moved, tol=WELD_MM, pred=None):
    """one common position per coincident group (see the module doc, 'move').  X0 / X1 / moved / pred: lists per mesh (before, proposed,
    mask of proposed moves, local-map prediction).  -> X1 (copies, adjusted), moved (adjusted), list of (group index, rule)"""
    X1 = [x.copy() for x in X1]; moved = [m.copy() for m in moved]
    rules = []
    for gi, g in enumerate(groups):
        mv = np.array([moved[m][v] for m, v in g])
        p0 = np.array([X0[m][v] for m, v in g])
        sep = float(np.linalg.norm(p0 - p0.mean(0), axis=1).max() * 2)
        if mv.all():
            t = np.mean([X1[m][v] for m, v in g], 0); rule = "all spikes: mean"
        elif mv.any():
            if sep <= tol:
                t = None; rule = "joined, not all spikes: frozen"
            else:
                t = np.mean([X0[m][v] for (m, v), k in zip(g, mv) if not k], 0); rule = "separated: spikes to the unspiked"
        elif sep > tol and pred is not None:
            t = np.mean([pred[m][v] for m, v in g], 0); rule = "separated, no spike: mean of predictions"
        else:
            continue
        for k, (m, v) in enumerate(g):
            if t is None:
                X1[m][v] = X0[m][v]; moved[m][v] = False
            else:
                X1[m][v] = t; moved[m][v] = bool(np.linalg.norm(t - X0[m][v]) > 1e-9)
        rules.append((gi, rule))
    return X1, moved, rules


def sheet_partner(XM, F, cos=-0.5, k=24):
    """per vertex: the nearest vertex of the slab's other sheet on Base·M (vertex normal opposed) -> (partner index, has partner)"""
    vn, _ = BC.vertex_normals(XM, F)
    kk = int(min(k, len(XM)))
    d, j = cKDTree(XM).query(XM, k=kk)
    opp = (np.einsum("ij,ikj->ik", vn, vn[j]) < cos) & (d > 1e-6)
    has = opp.any(1)
    pj = j[np.arange(len(XM)), np.argmax(opp, 1)]
    return np.where(has, pj, -1), has


def thickness(X, pj):
    """distance of each vertex to its other-sheet partner (nan without one)"""
    ok = pj >= 0
    t = np.full(len(X), np.nan)
    t[ok] = np.linalg.norm(X[ok] - X[pj[ok]], axis=1)
    return t


def joined_share(Pa, Fa, Pb, Fb):
    """border vertices of A that face B and that the engine joins to B: shared (weld), on B's border edge (T-junction, 1c) or an
    offset pair within the rim join (1b) -> (joined, border)"""
    c = BC.classify(Pa, Fa, Pb, Fb, offset=RIM_MM)
    return int(len(c["shared"]) + len(c["tjunction"]) + len(c["offset"])), int(len(c["border"]))


# ------------------------------------------------------------------ page
def skin_of(man, blob, C340):
    out = {}
    for m in man["meshes"]:
        if m.get("sys") == "skin" and not SKIP.match(m.get("name", "")):
            out[m["id"]] = C340.dec(m, blob)
    return out


def neighbours_of(pairs, rp, ids):
    nb = {i: set() for i in ids}
    for a, _, b, _ in pairs:
        nb[ids[int(a)]].add(ids[int(b)]); nb[ids[int(b)]].add(ids[int(a)])
    for a, _, b, _, _ in rp:
        nb[ids[int(a)]].add(ids[int(b)]); nb[ids[int(b)]].add(ids[int(a)])
    return nb


def where(p):
    x, y, z = p
    side = "midline" if abs(x) < 3 else ("right (+x)" if x > 0 else "left (-x)")
    return f"{side}, height {y:.0f} mm, {'front' if z > 0 else 'back'} {abs(z):.0f} mm"


def note_for(e):
    return (f"{TAG} {e['moved']} of {e['verts']} vertices put back on this body's smooth warp of the Z-Anatomy source skin: the body "
            f"registration that built this page had left them as spikes or as a border no longer shared with the neighbouring region "
            f"(residual up to {e['residual_moved_max_mm']:.1f} mm against a local map fitted to the surrounding skin); each went to its own "
            f"source position through that map (move max {e['move']['max_mm']:.1f} mm, p95 {e['move']['p95_mm']:.1f} mm), a shared border "
            f"vertex to one common position. Nothing else moved; region borders, thickness and size kept.")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--page-dir", required=True, help="the Base·F page dir (written with --write)")
    ap.add_argument("--src-dir", default=None, help="the Base·M page dir, read only; default <page-dir>/../viewer_zan_atlas")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--allow-build", action="store_true", help="permit --write into build/ (the main thread's apply step)")
    ap.add_argument("--json", default=None)
    ap.add_argument("--no-under", action="store_true", help="skip the under-skin guard (development only; never with --write)")
    a = ap.parse_args(argv)
    d = Path(a.page_dir).resolve()
    sd = Path(a.src_dir).resolve() if a.src_dir else d.parent / "viewer_zan_atlas"
    if a.write and "/build/" in str(d) + "/" and not a.allow_build:
        print("refused: never write into build/ without --allow-build (apply on a copy; the main thread applies)")
        return 2
    if a.write and a.no_under:
        print("refused: --no-under is for development runs")
        return 2
    if d == sd:
        print("refused: page and source are the same dir")
        return 2
    C340, _ = D._load()
    stem = C340.stem_of(d)
    if "female" not in stem:
        print(f"refused: {stem} is not Base·F")
        return 2
    man, blob, files = C340.read_page(d, stem)
    done = [m["id"] for m in man["meshes"] if TAG in (((m.get("rec") or {}).get("procedural_badge")) or "")]
    if done:
        print(f"Q377 already applied to this page ({len(done)} slabs carry the Q377 note, e.g. {done[0]}); nothing done")
        return 0
    sman, sblob, _ = C340.read_page(sd, C340.stem_of(sd))
    t0 = time.time()
    SF, SM = skin_of(man, blob, C340), skin_of(sman, sblob, C340)
    names = {m["id"]: m["name"] for m in man["meshes"]}
    recs = {m["id"]: m.get("rec") for m in man["meshes"]}
    ids = sorted(SF)
    twin = [i for i in ids if i in SM and SM[i][0].shape == SF[i][0].shape and np.array_equal(SM[i][1], SF[i][1])]
    other = [i for i in ids if i not in twin]
    tw = {i: k for k, i in enumerate(twin)}
    print(f"Q377 {stem}: {len(ids)} skin slabs, {len(twin)} with a same-topology Base·M twin, {len(other)} without", flush=True)

    # ---- (a) the local map over the whole twin skin
    XM = [SM[i][0] for i in twin]; XF = [SF[i][0] for i in twin]; FF = [SF[i][1] for i in twin]
    off = np.cumsum([0] + [len(x) for x in XM])
    UM, UF = np.concatenate(XM), np.concatenate(XF)
    UFc = np.concatenate([f + off[k] for k, f in enumerate(FF)])
    # frozen: a twin vertex coincident (Base·F) with a vertex of a slab that has no twin -- its partner cannot be predicted
    frozen = np.zeros(len(UF), bool)
    if other:
        oP = np.concatenate([SF[i][0] for i in other])
        dd, _ = cKDTree(oP).query(UF, distance_upper_bound=WELD_MM)
        frozen |= np.isfinite(dd)
    X1u, flu, r0u, sigu, pu, info = D.despike_structure(UM, UF, UFc, frozen)
    split = lambda u: [u[off[k]:off[k + 1]] for k in range(len(twin))]
    r0, sig, fl, P1, PR = split(r0u), split(sigu), split(flu), split(X1u), split(pu)
    lab = split(info.get("label", np.full(len(UF), -1)))
    rim = [BC.rim_vertices(XM[k], FF[k])[0] for k in range(len(twin))]
    print("  local map: %d vertices, residual p50 %.2f p90 %.2f p99 %.2f max %.2f mm; %d spike vertices in %d patches; rejected %s (%.0f s)" % (
        (len(UF),) + tuple(np.percentile(r0u, [50, 90, 99, 100])) + (int(flu.sum()), info["patches"], info["rejected"], time.time() - t0)), flush=True)

    # ---- (b) borders between twin slabs: coincident on Base·M, rim-joined on Base·M
    pairs, groups = coincident_groups(XM)
    sepF = np.linalg.norm(np.array([XF[int(p[0])][int(p[1])] - XF[int(p[2])][int(p[3])] for p in pairs]), axis=1) if len(pairs) else np.zeros(0)
    rp = rim_pairs(XM, rim)
    rdF = np.array([np.linalg.norm(XF[int(p[0])][int(p[1])] - XF[int(p[2])][int(p[3])]) for p in rp]) if len(rp) else np.zeros(0)
    bord = {}
    for p, s in zip(pairs, sepF):
        k = tuple(sorted((twin[int(p[0])], twin[int(p[2])])))
        b = bord.setdefault(k, dict(coincident=0, separated=0, sep_max_mm=0.0, rim_pairs=0, rim_broken=0, rim_max_mm=0.0))
        b["coincident"] += 1; b["separated"] += int(s > WELD_MM); b["sep_max_mm"] = max(b["sep_max_mm"], round(float(s), 3))
    for p, s in zip(rp, rdF):
        k = tuple(sorted((twin[int(p[0])], twin[int(p[2])])))
        b = bord.setdefault(k, dict(coincident=0, separated=0, sep_max_mm=0.0, rim_pairs=0, rim_broken=0, rim_max_mm=0.0))
        b["rim_pairs"] += 1; b["rim_broken"] += int(s > RIM_MM); b["rim_max_mm"] = max(b["rim_max_mm"], round(float(s), 3))
    # ---- (c) slabs without a twin against their twin neighbours (the Q360 chest; Q358 perineum)
    nontwin = {}
    for i in other:
        if i not in SM and not i.startswith("zan_skin_"):
            continue       # rule-based / female-only pieces (Q358): not Z slabs, left alone
        Pi, Fi = SF[i]
        lo, hi = Pi.min(0) - 3, Pi.max(0) + 3
        for j in ids:
            if j == i:
                continue
            Pj, Fj = SF[j]
            if (Pj.min(0) > hi).any() or (Pj.max(0) < lo).any():
                continue
            for A, B in ((i, j), (j, i)):
                c = BC.classify(*SF[A], *SF[B], offset=RIM_MM)
                if len(c["border"]) < 2:
                    continue
                nontwin[f"{A}|{B}"] = dict(border=int(len(c["border"])), shared=int(len(c["shared"])), tjunction=int(len(c["tjunction"])),
                                          rim_join=int(len(c["offset"])), unjoined=int(len(c["other"])),
                                          offset_max_mm=round(float(c["offset_mm"].max()), 3) if len(c["offset_mm"]) else 0.0)
    print(f"  borders: {len(pairs)} coincident pairs ({int((sepF > WELD_MM).sum())} separated on Base·F, max {sepF.max() if len(sepF) else 0:.2f} mm); "
          f"{len(rp)} rim-join pairs ({int((rdF > RIM_MM).sum())} beyond the rim join on Base·F, max {rdF.max() if len(rdF) else 0:.2f} mm); "
          f"{len(nontwin)} slab-without-twin border sides measured", flush=True)

    # ---- the plan: spikes -> prediction; coincident groups -> one position
    X0 = [x.copy() for x in XF]
    moved = [f.copy() for f in fl]
    X1, moved, rules = group_targets(groups, X0, P1, moved, pred=PR)
    rule_n = {}
    for _, r in rules:
        rule_n[r] = rule_n.get(r, 0) + 1
    # vertices tied across borders: a held slab holds its group partners too
    gidx = {}
    for gi, g in enumerate(groups):
        for m, v in g:
            gidx.setdefault(int(m), {})[int(v)] = gi
    PJ = [sheet_partner(XM[k], FF[k])[0] for k in range(len(twin))]
    under = None
    if not a.no_under:
        import conform_skin_q353 as Q353      # noqa: E402  Geo / SkinSet / outside_count (the tuck guard's test)
        under = Q353
    held, rep_s = {}, {}
    for it in range(6):
        touched = [k for k in range(len(twin)) if moved[k].any()]
        fails = {}
        for k in touched:
            i = twin[k]
            mv = np.linalg.norm(X1[k] - X0[k], axis=1)
            g = {}
            g["cap"] = dict(max_mm=round(float(mv.max()), 2), ok=bool(mv.max() <= CAP))
            a0, a1 = D.area(X0[k], FF[k]), D.area(X1[k], FF[k])
            g["area"] = dict(change_pct=round(100 * (a1 - a0) / a0, 3), ok=bool(abs(100 * (a1 - a0) / a0) <= AREA_MAX))
            sm = D.umeyama_scale(XM[k], X0[k])
            tm = thickness(XM[k], PJ[k]) * sm; tb = thickness(X0[k], PJ[k]); ta = thickness(X1[k], PJ[k])
            sel = moved[k].copy()
            pj = PJ[k]
            sel[pj[(pj >= 0) & moved[k]]] = True          # the moved vertices' partners: their thickness changed too
            sel &= pj >= 0
            bad = sel & (np.abs(ta - tm) > THICK_TOL) & (np.abs(ta - tm) > np.abs(tb - tm) + 1e-6)
            g["thickness"] = dict(checked=int(sel.sum()), before_err_max_mm=round(float(np.nanmax(np.abs(tb - tm)[sel])), 2) if sel.any() else 0.0,
                                  after_err_max_mm=round(float(np.nanmax(np.abs(ta - tm)[sel])), 2) if sel.any() else 0.0,
                                  worse=int(bad.sum()), ok=bool(not bad.any()))
            fails[k] = [n for n, v in g.items() if not v["ok"]]
            rep_s[i] = dict(guards=g)
        # border share (python port of the engine's join rules) for every border of a touched slab
        for k in touched:
            i = twin[k]
            nbk = set()
            for b in bord:
                if i in b:
                    nbk.add(b[0] if b[1] == i else b[1])
            res = {}
            okb = True
            lo, hi = X0[k].min(0) - 3, X0[k].max(0) + 3
            for j in sorted(nbk | set(o for o in other if (SF[o][0].min(0) <= hi).all() and (SF[o][0].max(0) >= lo).all())):
                kj = tw.get(j)
                Pj0, Fj = SF[j]
                Pj1 = X1[kj] if kj is not None else Pj0
                s0 = joined_share(X0[k], FF[k], Pj0, Fj); s1 = joined_share(X1[k], FF[k], Pj1, Fj)
                t0_ = joined_share(Pj0, Fj, X0[k], FF[k]); t1_ = joined_share(Pj1, Fj, X1[k], FF[k])
                if s0[1] + t0_[1] == 0:
                    continue
                ok = s1[0] >= s0[0] and t1_[0] >= t0_[0]
                res[j] = dict(before=[s0[0], t0_[0]], after=[s1[0], t1_[0]], border=[s0[1], t0_[1]], ok=bool(ok))
                okb &= ok
            rep_s[i]["guards"]["border_share"] = dict(borders=res, ok=bool(okb))
            if not okb:
                fails[k].append("border_share")
        if under is not None and touched:
            g = under.Geo(d)
            ids_t = [twin[k] for k in touched]
            lo = np.min([X0[k].min(0) for k in touched], 0) - 15; hi = np.max([X0[k].max(0) for k in touched], 0) + 15
            skin_ids = [kk for kk in g.in_box(lo, hi, sys_=("skin",)) if "nail_plate" not in kk]
            und = [kk for kk in g.in_box(lo, hi, sys_=under.VISIBLE_SYS)]
            sk0 = under.SkinSet(g, skin_ids)
            o0 = {kk: under.outside_count(g, sk0, kk)["outside"] for kk in und}
            for k in touched:
                g.cur[twin[k]] = X1[k]
            sk1 = under.SkinSet(g, skin_ids)
            o1 = {kk: under.outside_count(g, sk1, kk)["outside"] for kk in und}
            gained = {kk: (o0[kk], o1[kk]) for kk in und if o1[kk] > o0[kk] + GAIN_TOL}
            # blame: a slab whose own vertices moved within 15 mm of a structure that gained
            for k in touched:
                i = twin[k]
                mvP = X0[k][moved[k]]
                near = []
                for kk, (b0, b1) in gained.items():
                    if len(mvP) and cKDTree(g.cur[kk]).query(mvP, distance_upper_bound=15.0)[0].min() < 15.0:
                        near.append(f"{kk} {b0}->{b1}")
                rep_s[i]["guards"]["under_skin"] = dict(structures=len(und), gained=near, ok=not near)
                if near:
                    fails[k].append("under_skin")
            rep_s["_under_totals"] = dict(structures=len(und), outside_before=int(sum(o0.values())), outside_after=int(sum(o1.values())),
                                          gained={kk: list(v) for kk, v in gained.items()})
        newly = [k for k in touched if fails[k]]
        if not newly:
            break
        for k in newly:
            held[twin[k]] = fails[k]
            hold = np.where(moved[k])[0]
            moved[k][:] = False; X1[k] = X0[k].copy()
            for v in hold:      # the group partners in other slabs stay too
                gi = gidx.get(k, {}).get(int(v))
                if gi is None:
                    continue
                for m, w in groups[gi]:
                    X1[m][w] = X0[m][w]; moved[m][w] = False
        print(f"  guard pass {it + 1}: held {[twin[k] for k in newly]} ({[fails[k] for k in newly]})", flush=True)

    # ---- report
    slabs, replace, notes, allmv = {}, {}, {}, []
    for k, i in enumerate(twin):
        mv = np.linalg.norm(X1[k] - X0[k], axis=1)
        m = moved[k] & (mv > 1e-9)
        spk = np.where(fl[k])[0]
        pts = []
        for L in np.unique(lab[k][fl[k]]) if len(spk) else []:
            vs = np.where(fl[k] & (lab[k] == L))[0]
            pts.append(dict(verts=int(len(vs)), residual_max_mm=round(float(r0[k][vs].max()), 2), on_rim=int(rim[k][vs].sum()),
                            where=where(X0[k][vs].mean(0))))
        e = dict(name=names[i], verts=int(len(X0[k])), residual=D.stats(r0[k]), spikes=dict(vertices=int(len(spk)), patches=pts),
                 moved=int(m.sum()))
        if m.any():
            e["move"] = D.stats(mv[m]); e["residual_moved_max_mm"] = round(float(r0[k][m].max()), 2)
            e["decision"] = "corrected"
            replace[i] = X1[k]; notes[i] = note_for(e); allmv.append(mv[m])
        elif i in held:
            e["decision"] = "held: " + ", ".join(held[i])
        if i in rep_s:
            e.update(rep_s[i])
        slabs[i] = e
    mvall = np.concatenate(allmv) if allmv else np.zeros(0)
    seps = sorted(({"a": a_, "b": b_, **v} for (a_, b_), v in bord.items() if v["separated"] or v["rim_broken"]),
                  key=lambda r: -max(r["sep_max_mm"], r["rim_max_mm"]))
    totals = dict(slabs=len(ids), twins=len(twin), without_twin=other, vertices=int(len(UF)),
                  residual=D.stats(r0u), slabs_with_spikes=int(sum(1 for k in range(len(twin)) if fl[k].any())),
                  spike_vertices=int(flu.sum()), spike_patches=int(info["patches"]), patches_rejected=info["rejected"],
                  frozen_vertices=int(frozen.sum()), borders=len(bord), coincident_pairs=int(len(pairs)),
                  coincident_separated=int((sepF > WELD_MM).sum()), rim_pairs=int(len(rp)), rim_broken=int((rdF > RIM_MM).sum()),
                  borders_separated=len(seps), group_rules=rule_n, corrected=len(replace), held=held,
                  vertices_moved=int(len(mvall)), move=D.stats(mvall))
    rep = {"schema": "nmsk.q377.skin.v1", "round": "Q377", "generated": time.strftime("%Y-%m-%d"), "page": stem, "written": bool(a.write),
           "source_page": C340.stem_of(sd),
           "parameters": dict(weld_mm=WELD_MM, rim_mm=RIM_MM, cap_mm=CAP, area_max_pct=AREA_MAX, thick_tol_mm=THICK_TOL, gain_tol=GAIN_TOL,
                              local_map="Q366 (k=%d, t_hi=%g, k_hi=%g, patch_max=%d) over all twin skin slabs together" % (D.K, D.T_HI, D.K_HI, D.PATCH_MAX)),
           "totals": totals, "borders_separated": seps, "without_twin_borders": nontwin,
           "under_skin": rep_s.get("_under_totals"), "slabs": slabs}
    print("Q377 totals: %d twin slabs, %d with spikes (%d vertices); %d borders separated; corrected %d slabs (%d vertices, move max %.2f p95 %.2f mm), held %d" % (
        len(twin), totals["slabs_with_spikes"], totals["spike_vertices"], len(seps), len(replace), len(mvall), totals["move"]["max_mm"],
        totals["move"]["p95_mm"], len(held)), flush=True)
    if replace and a.write:
        man2, blob2 = C340.repack(man, blob, {kk: (v, SF[kk][1], C340.badge_add(recs[kk], notes[kk])) for kk, v in replace.items()})
        for m0, m1 in zip(man["meshes"], man2["meshes"]):
            assert m0["id"] == m1["id"] and m0["vc"] == m1["vc"] and m0["ic"] == m1["ic"]
        assert len(blob2) == len(blob)
        old = D.SUFFIX
        try:
            D.SUFFIX = SUFFIX
            rep["files_changed"] = D.write_page(d, stem, man, man2, blob2, files, C340)
        finally:
            D.SUFFIX = old
        print("  wrote: " + ", ".join(rep["files_changed"]) + f" (originals kept as *{SUFFIX})")
        rig = REPO / "data/anatomy/pose_rig_base_f.json"
        if rig.exists():
            R0 = json.loads(rig.read_text(encoding="utf-8"))["rig"]
            ok = R0["count"] == len(man2["meshes"]) and R0["nv"] == [int(m["vc"]) for m in man2["meshes"]]
            rep["pose_rig"] = ("vertex counts and order unchanged: the rig (%s) still matches; no re-encode" % rig.relative_to(REPO)) if ok \
                else "RIG OUT OF STEP with the page (Q377 changes no count)"
            print("  pose rig: " + rep["pose_rig"])
    if a.write or a.json:
        jp = Path(a.json or OUT)
        jp.parent.mkdir(parents=True, exist_ok=True)
        jp.write_text(json.dumps(rep, indent=1, default=lambda o: o.tolist() if isinstance(o, np.ndarray) else (
            float(o) if isinstance(o, np.floating) else (int(o) if isinstance(o, np.integer) else str(o)))) + "\n", encoding="utf-8")
        print(f"  report -> {jp}")
    print(f"Q377 {'WRITTEN' if a.write else 'DRY RUN'} {stem}: {len(replace)} slabs changed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
