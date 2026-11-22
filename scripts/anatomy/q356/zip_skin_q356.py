#!/usr/bin/env python3
"""Q356: Base · Female anterior chest skin -- the slots and grooves between the refitted skin regions closed by laying each region's
border under its neighbour's (a shingle), so the breast tissue no longer shows through and no region ends in an open slot.

    python3 scripts/anatomy/q356/zip_skin_q356.py --page-dir DIR [--steps chest]            # dry run
    python3 scripts/anatomy/q356/zip_skin_q356.py --page-dir DIR [--steps chest] --write    # and write DIR

Cause (measured on the regenerated page, Q356). The Q334 load-time weld removes a border only where two skin slabs share their
border: vertices within 0.03 mm (or a rim vertex with a mutually nearest rim vertex within 1 mm and a third of its shortest edge),
and a sharp rim (the wall stands ~90 degrees off the surface: that is how it finds the wall and leaves it out). The back regions
(Z-Anatomy, ~3 mm edges) are built that way: 43-64 of their outer-to-wall edges are creases, and 83-99 % of their rim vertices weld
or rim-join. This body's anterior trunk regions were refitted one by one (~0.7-1.1 mm edges, closed slabs ~2.7 mm thick):
  * their borders share no vertices -- 0-15 % of their rim vertices weld, 65-95 % stay unjoined;
  * their rims are rounded, not creased -- e.g. inframammary / mammary / pectoral: outer and inner sheet joined without a single
    edge sharper than 60 degrees, so there is no wall for the weld to find and the rounded rim itself is drawn;
  * they do not meet -- slots up to ~5 mm (the breast tissue shows through, e.g. lateral and inferior to the mammary region),
    overlaps of up to ~10 mm (presternal / pectoral), serrated borders.
Q353 chest_seams measured its gaps from the ray-classified "outer rim", which on these rounded slabs is where the rounding starts,
not the border (87 of 124 such edges on the right inframammary region are flat continuations of the surface): it moved an inner row
and left the rounded border where it was -- hence "gaps closed, outlines unchanged". Q353 back moved border vertices the weld had
joined: unjoined rim vertices vertebral 26 -> 60, infrascapular 10 -> 38 -- the new lines.

The step (existing real meshes only, nothing added or deleted; vertex and triangle counts and order unchanged): the chest regions are
ordered coarse to fine (median outer-border edge; ties by name); regions outside the set lead. Every outer-border vertex of a region
whose nearest outer border of another region lies within MATCH mm, and belongs to a region that leads, goes to the closest point of
that border, then PAST mm further under the leader (along the leader's surface, into it) and UNDER mm below its outer surface. The
region's rounded rim then lies under the leader and the leader's rim rests on it: no slot, no groove. A border vertex facing a later
region follows the region (that region comes under it); a border vertex already shared with its neighbour (within WELD_EPS: the
weld joins it), and every other vertex the weld joins to another region, is held where it is. The border move is carried into the region harmonically over its own mesh
(zero beyond FALL mm), cap CAP mm; a held border vertex that folds an outer face is let go.
Guards (Q353's runner, reused: a region failing any is kept as it is and leads; the others are redone): folded faces <= 0.5 % of the
moved outer faces (a face flattened onto the border line is counted apart); stretched faces <= before + 12 points; slab volume change
<= 20 %; no border opening grows by > 0.2 mm (a border vertex counts as open only when no other region's outer surface passes within
COVER mm of it -- an overlap is not an opening); no structure under the skin gains vertices outside it (the breast tissue must stay
fully under the skin; Q353's tuck rule may tuck it); exact L/R mirror pairs stay mirrors. Originals kept beside each replaced file as
`<name>.q356`; a step whose tag a structure already carries is skipped (idempotent). Report: data/derived/Q356_skin_zip_report.json.
"""
from __future__ import annotations

import argparse
import base64
import json
import shutil
import sys
import time
from pathlib import Path

import numpy as np
import trimesh
from scipy import sparse
from scipy.sparse.linalg import splu
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "anatomy" / "q353"))
import conform_skin_q353 as Q  # noqa: E402  Geo / sheets / guards / run_step1 / tuck
C340 = Q.C340

OUT = REPO / "data/derived/Q356_skin_zip_report.json"
MATCH, CAP, FALL, WELD_EPS = 6.0, 8.0, 20.0, 0.03
PAST, UNDER = 1.5, 0.3          # mm: the follower's border this far past the leader's border, this far under its outer surface
COVER, FLAT = 1.0, 0.1

FRONT = ["pectoral_region", "mammary_region", "presternal_region", "inframammary_region",
         "epigastric_region", "hypochondriac_region", "infraclavicular_fossa", "deltopectoral_triangle"]
STEPS = {"chest": dict(seam=[f"zan_skin_{c}_{s}" for c in FRONT for s in "rl"], tuck=[], strict=Q.BREAST)}


def tag(step):
    return f"Q356 {step}:"


def rim_out(g, k):
    return g.sheets(k)[1]


def coarse(g, k):
    e = rim_out(g, k)
    if not len(e):
        return 0.0
    v = g.V0[k][0]
    return float(np.median(np.linalg.norm(v[e[:, 0]] - v[e[:, 1]], axis=1)))


def outer_core(g, k):
    """vertices whose every face is on the outer sheet (the surface itself, not its rounded rim)"""
    cls, _ = g.sheets(k)
    f = g.F[k]
    n = len(g.cur[k])
    on = {c: np.zeros(n, bool) for c in (1, -1, 0)}
    for c in on:
        on[c][f[cls == c].ravel()] = True
    return on[1] & ~on[0] & ~on[-1]


def vnormals(g, k):
    """outward vertex normals of slab k's outer sheet (area-weighted over its outer faces, current positions)"""
    cls, _ = g.sheets(k)
    v, f = g.cur[k], g.F[k]
    fo = f[cls == 1]
    fa = np.cross(v[fo[:, 1]] - v[fo[:, 0]], v[fo[:, 2]] - v[fo[:, 0]])
    vn = np.zeros_like(v)
    for j in range(3):
        np.add.at(vn, fo[:, j], fa)
    return vn / np.maximum(np.linalg.norm(vn, axis=1, keepdims=True), 1e-12)


def spread(v, f, u, du):
    """the border move carried into the region: harmonic (uniform Laplacian) over the slab's own mesh, the held border vertices at
    their move, every vertex farther than FALL mm from a moved one at zero"""
    n = len(v)
    D = np.zeros((n, 3))
    mv = np.linalg.norm(du, axis=1) > 1e-9
    if not mv.any():
        return D
    dist, _ = cKDTree(v[u[mv]]).query(v)
    fixed = dist > FALL
    fixed[u] = True
    D[u] = du
    e = np.unique(np.sort(f[:, [0, 1, 1, 2, 2, 0]].reshape(-1, 2), axis=1), axis=0)
    A = sparse.coo_matrix((np.ones(2 * len(e)), (np.r_[e[:, 0], e[:, 1]], np.r_[e[:, 1], e[:, 0]])), shape=(n, n)).tocsr()
    A.data[:] = 1.0
    L = sparse.diags(np.asarray(A.sum(1)).ravel()) - A
    fr = np.where(~fixed)[0]; fx = np.where(fixed)[0]
    if len(fr):
        solve = splu(L[fr][:, fr].tocsc())
        rhs = -(L[fr][:, fx] @ D[fx])
        for c in range(3):
            D[fr, c] = solve.solve(np.ascontiguousarray(rhs[:, c]))
    nn = np.linalg.norm(D, axis=1)
    over = nn > CAP
    D[over] *= (CAP / nn[over])[:, None]
    D[u] = du
    return D


def _fn(v, f):
    return np.cross(v[f[:, 1]] - v[f[:, 0]], v[f[:, 2]] - v[f[:, 0]])


def flattened(v0, v1, f):
    """faces left with < FLAT of their area: a thin face along the border whose corners all went onto one line (not drawn)"""
    return np.linalg.norm(_fn(v1, f), axis=1) < FLAT * np.maximum(np.linalg.norm(_fn(v0, f), axis=1), 1e-12)


def real_flips(v0, v1, f):
    return ((_fn(v0, f) * _fn(v1, f)).sum(1) < 0) & ~flattened(v0, v1, f)


def flipped_pct(v0, v1, f):
    """Q213's measure without the faces flattened onto a line (reported apart)"""
    if not len(f):
        return 0.0
    keep = ~flattened(v0, v1, f) & (np.linalg.norm(_fn(v0, f), axis=1) > 1e-9)
    return float(100.0 * real_flips(v0, v1, f)[keep].mean()) if keep.any() else 0.0


_G = {}


def _moved_near(o, p, r=3.0):
    g, st = _G.get("g"), _G.get("start", {})
    if g is None or o not in st:
        return False
    near = np.linalg.norm(g.cur[o] - p, axis=1) < r
    return bool((np.linalg.norm(g.cur[o] - st[o], axis=1)[near] > 0.05).any())


def _covered(g, P, others):
    """per point: another region's outer surface passes within COVER mm of it (the border is closed there, if by an overlap)"""
    out = np.zeros(len(P), bool)
    for o in others:
        cls, _ = g.sheets(o)
        fo = g.F[o][cls == 1]
        if not len(fo):
            continue
        t = trimesh.Trimesh(g.cur[o], fo, process=False)
        _, d, _ = trimesh.proximity.closest_point(t, P)
        out |= d < COVER
    return out


def border_growth(before, after, movable, pos):
    """Q353's guard: a border vertex whose gap to the nearest neighbouring border grew by more than GROW_MAX -- unless another region's
    outer surface now passes within COVER mm of it (an overlap, not an opening); charged to the region that moved there"""
    g = _G.get("g")
    mv = set(movable); blame = {}
    for k, (b0, o0) in before.items():
        b1, o1 = after[k]
        grew = np.where((b0 < Q.MATCH) & np.isfinite(b1) & (b1 - b0 > Q.GROW_MAX))[0]
        if not len(grew):
            continue
        others = sorted({o for o in list(o0[grew]) + list(o1[grew]) if o and o != k})
        if g is not None and others:
            grew = grew[~_covered(g, pos[k][grew], others)]
        for i in grew:
            p = pos[k][i]
            cand = [k] + [o for o in (o1[i], o0[i]) if o]
            who = next((o for o in cand if o in mv and _moved_near(o, p)), None)
            if who is None:
                who = k if k in mv else next((o for o in cand if o in mv), None)
            if who:
                x = blame.setdefault(who, dict(vertices=0, max_growth_mm=0.0, at=[], points=[]))
                x["points"].append(p)
                x["vertices"] += 1; x["max_growth_mm"] = round(max(x["max_growth_mm"], float(b1[i] - b0[i])), 2)
                if len(x["at"]) < 3:
                    x["at"].append(f"{k[9:]}->{o1[i][9:]}")
    return blame


def openings(g, pieces):
    """border vertices of the set (outer border) not covered by another region's outer surface, and their gap to the nearest
    neighbouring border (the measure the growth guard uses)"""
    gaps = Q.border_gaps(g, pieces)
    pos = Q.border_pos(g, pieces)
    res = {}
    for k in pieces:
        b, o = gaps[k]
        m = np.where(b < Q.MATCH)[0]
        others = sorted({x for x in o[m] if x and x != k})
        cov = _covered(g, pos[k][m], others) if len(m) and others else np.zeros(len(m), bool)
        res[k] = (b[m][~cov], int(len(m)))
    return res


def shared_tree(g, k, pieces):
    return cKDTree(np.vstack([g.cur[o] for o in pieces if o != k]))


def shingle_seams(g, movable, log):
    """run_seams replacement for Q353's run_step1 (see the module doc)"""
    movable = [k for k in movable if k in g.M]
    lo = np.min([g.box(k)[0] for k in movable], 0) - MATCH
    hi = np.max([g.box(k)[1] for k in movable], 0) + MATCH
    anchors = [k for k in g.in_box(lo, hi, sys_=("skin",), exclude=set(movable)) if "nail_plate" not in k]
    order = sorted(movable, key=lambda k: (-round(coarse(g, k), 2), k))
    rank = {k: i for i, k in enumerate(order)}
    start = {k: g.cur[k].copy() for k in movable}
    _G.update(g=g, start=start)
    op0 = openings(g, movable + anchors)
    rep = {}
    for k in order:
        v = g.cur[k]
        segs, own = [], []
        for o in movable + anchors:
            e = rim_out(g, o)
            if o != k and len(e):
                segs.append(np.stack([g.cur[o][e[:, 0]], g.cur[o][e[:, 1]]], 1)); own += [o] * len(e)
        S = np.vstack(segs); own = np.array(own)
        tree = cKDTree(S.mean(1))
        rv = np.unique(rim_out(g, k))
        P = v[rv]
        _, J = tree.query(P, k=min(32, len(S)))
        best = np.full(len(P), np.inf); bj = np.zeros(len(P), int); bt = np.zeros(len(P))
        for col in range(J.shape[1]):
            j = J[:, col]
            A, B = S[j, 0], S[j, 1]
            t = np.clip(((P - A) * (B - A)).sum(1) / np.maximum(((B - A) ** 2).sum(1), 1e-12), 0, 1)
            d = np.linalg.norm(P - (A + t[:, None] * (B - A)), axis=1)
            m = d < best
            best[m] = d[m]; bj[m] = j[m]; bt[m] = t[m]
        lead = np.array([(own[j] not in rank) or rank[own[j]] < rank[k] for j in bj])
        dsh, _ = shared_tree(g, k, movable + anchors).query(v, distance_upper_bound=WELD_EPS)
        shared = np.isfinite(dsh)                # every vertex the weld already joins to another region stays where it is
        joined = (best < WELD_EPS) | shared[rv]
        go = (best < MATCH) & lead & ~joined
        proj = S[bj, 0] + bt[:, None] * (S[bj, 1] - S[bj, 0])
        tgt = P.copy()
        for o in sorted(set(own[bj[go]])):
            sel = np.where(go & (own[bj] == o))[0]
            cv = np.where(outer_core(g, o))[0]
            if len(cv) < 6:
                go[sel] = False
                continue
            vn = vnormals(g, o)
            _, jq = cKDTree(g.cur[o][cv]).query(proj[sel], k=6)
            c0 = g.cur[o][cv[jq]].mean(1)
            nL = vn[cv[jq]].sum(1); nL /= np.maximum(np.linalg.norm(nL, axis=1, keepdims=True), 1e-12)
            ti = c0 - proj[sel]; ti -= (ti * nL).sum(1, keepdims=True) * nL
            ti /= np.maximum(np.linalg.norm(ti, axis=1, keepdims=True), 1e-12)
            tgt[sel] = proj[sel] + PAST * ti - UNDER * nL
        dd = tgt - P
        over = np.linalg.norm(dd, axis=1) > CAP
        hold = (go & ~over) | joined
        dd[joined] = 0.0
        u, du = rv[hold], dd[hold]
        sh = np.setdiff1d(np.where(shared)[0], u)      # the shared ones off the outer border (inner border, wall) too
        nh = len(u)
        u = np.r_[u, sh]; du = np.vstack([du, np.zeros((len(sh), 3))])
        movable_u = np.arange(len(u)) < nh       # only a vertex this step moves can be let go
        fo = g.F[k][g.sheets(k)[0] == 1]
        keep = np.ones(len(u), bool); released = 0
        D = np.zeros_like(v)
        for _ in range(6):
            D = spread(v, g.F[k], u[keep], du[keep]) if keep.any() else np.zeros_like(v)
            bad = real_flips(v, v + D, fo)
            if not bad.any():
                break
            cv2 = np.isin(u, fo[bad].ravel()) & keep & movable_u & ~np.isin(u, rv[joined])
            if not cv2.any():
                break
            keep &= ~cv2; released += int(cv2.sum())
        g.cur[k] = v + D
        rep[k] = dict(rank=rank[k], border_edge_median_mm=round(coarse(g, k), 2), border_vertices=int(len(rv)),
                      under_leader=int((keep[:nh] & go[hold]).sum()), already_joined=int(joined.sum()), shared_vertices_held=int(len(sh)), facing_later_region=int(((best < MATCH) & ~lead).sum()),
                      no_neighbour=int((best >= MATCH).sum()), over_cap=int((go & over).sum()), released_folding=released,
                      flattened_faces=int(flattened(v, v + D, fo).sum()))
    op1 = openings(g, movable + anchors)
    for k in movable:
        b0, n0 = op0[k]; b1, n1 = op1[k]
        rep[k].update(border_gap_before_mm=dict(median=round(float(np.median(b0)), 2) if len(b0) else 0.0,
                                                over_1_5mm=int((b0 > 1.5).sum()), open_vertices=int(len(b0)), of=n0),
                      border_gap_after_mm=dict(median=round(float(np.median(b1)), 2) if len(b1) else 0.0,
                                               over_1_5mm=int((b1 > 1.5).sum()), open_vertices=int(len(b1)), of=n1))
    log(f"    order (coarse leads): {', '.join(x[9:] for x in order)}")
    return rep, anchors, start


def note_for(step, k, srep):
    s = srep["seam_guards"][k]["displacement"]
    z = srep["seams"][k]
    return (f"{tag(step)} border laid under the neighbouring skin region (this body's trunk regions were refitted one by one: they met "
            f"with slots, overlaps and rounded rims -- an outline, and tissue showing through); {z['under_leader']} border vertices "
            f"{PAST:g} mm past the neighbour's border and {UNDER:g} mm under its surface, the move carried {FALL:g} mm into the region, "
            f"max {s['max_mm']} mm (cap {CAP:g}); mesh, vertex and triangle counts unchanged.")


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
        p = d / n
        new = base64.b64encode(c)
        if p.read_bytes() != new:
            bk = p.with_name(p.name + ".q356")
            if not bk.exists():
                shutil.copy2(p, bk)
            p.write_bytes(new); changed.append(n)
    for p, t in texts.items():
        bk = p.with_name(p.name + ".q356")
        if not bk.exists():
            shutil.copy2(p, bk)
        t2 = C340.LIT["manifest"].sub(lambda _m: "window.__ANATOMY_MANIFEST__=" + C340.ser_manifest(man_new) + ";", t, count=1)
        t2 = C340.LIT["files"].sub(lambda _m: "window.__ANATOMY_BIN_FILES__=" + json.dumps(files) + ";", t2, count=1)
        p.write_text(t2, encoding="utf-8"); changed.append(p.name)
    return changed


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--page-dir", required=True)
    ap.add_argument("--steps", default="chest")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--json", default=str(OUT))
    a = ap.parse_args(argv)
    d = Path(a.page_dir).resolve()
    Q.STEPS.update(STEPS)
    Q.run_seams = shingle_seams              # Q353's guarded step runner, with this border rule,
    Q.border_growth = border_growth          # its border guard counting only openings and charged to the region that moved,
    Q.flipped_pct = flipped_pct              # and a face flattened onto a line counted apart from a fold
    g = Q.Geo(d)
    if g.stem not in Q.STEMS:
        print(f"Q356 is for Base · Female only ({g.stem}); nothing done")
        return 2
    t0 = time.time()
    rep = dict(schema="nmsk.q356.skin_zip.v1", round="Q356", generated=time.strftime("%Y-%m-%d"), page_dir=str(d), page=g.stem,
               written=bool(a.write), rule_based=True,
               parameters=dict(match_mm=MATCH, past_mm=PAST, under_mm=UNDER, cap_mm=CAP, fall_mm=FALL, cover_mm=COVER,
                               grow_max_mm=Q.GROW_MAX, flip_max_pct=Q.FLIP_MAX, stretch_add_pts=Q.STRETCH_ADD,
                               slab_vol_max_pct=Q.SLAB_VOL_MAX, mirror_max_mm=Q.MIRROR_MAX, steps=STEPS),
               steps={})
    recs = {m["id"]: m.get("rec") for m in g.man["meshes"]}
    owner = {}
    for st in [s.strip() for s in a.steps.split(",") if s.strip()]:
        if st not in STEPS:
            raise SystemExit(f"unknown step {st}")
        done = [k for k, r in recs.items() if tag(st) in ((r or {}).get("procedural_badge") or "")]
        if done:
            print(f"-- {st}: already applied ({len(done)} structures carry '{tag(st)}'); skipped")
            rep["steps"][st] = dict(skipped="already applied", structures=done)
            continue
        print(f"-- {st}")
        before = {k: v.copy() for k, v in g.cur.items()}
        r = Q.run_step(g, st, print)
        r.pop("_snap", None)
        rep["steps"][st] = r
        for k in g.cur:
            if np.abs(g.cur[k] - before[k]).max() > 1e-6:
                owner.setdefault(k, []).append(st)
    replace, rep["structures"] = {}, {}
    for k, sts in sorted(owner.items()):
        v0, f = g.V0[k]
        v1 = g.cur[k]
        rec = recs[k]
        for st in sts:
            sr = rep["steps"][st]
            if k in sr.get("seams", {}):
                rec = C340.badge_add(rec, note_for(st, k, sr))
            else:
                rec = C340.badge_add(rec, Q.note_for("chest_tuck", k, sr).replace("Q353 chest_tuck:", tag(st)))
        replace[k] = (v1, f, rec)
        rep["structures"][k] = dict(steps=sts, sys=g.sys[k], vertices=len(v0), faces=len(f), displacement=Q.stats(v1 - v0),
                                    **Q.face_guards(v0, v1, f), card=rec["procedural_badge"])
    rep["geometry_changed"] = sorted(replace)
    if replace:
        man2, blob2 = C340.repack(g.man, g.blob, replace)
        for m0, m1 in zip(g.man["meshes"], man2["meshes"]):
            assert m0["id"] == m1["id"] and m0["vc"] == m1["vc"] and m0["ic"] == m1["ic"]
        assert len(blob2) == len(g.blob)
        if a.write:
            rep["files_changed"] = write_page(d, g.stem, g.man, man2, blob2, g.files)
            print("  wrote: " + ", ".join(rep["files_changed"]) + " (originals kept as *.q356)")
    rep["seconds"] = round(time.time() - t0, 1)
    jp = Path(a.json)
    allr = json.loads(jp.read_text(encoding="utf-8")) if jp.exists() else {}
    if allr.get("schema") != "nmsk.q356.skin_zip_report.v1":
        allr = {"schema": "nmsk.q356.skin_zip_report.v1", "pages": {}}
    allr["pages"][g.stem] = rep
    jp.parent.mkdir(parents=True, exist_ok=True)
    jp.write_text(json.dumps(allr, indent=1, default=Q.jsonable), encoding="utf-8")
    print(f"Q356 {'WRITTEN' if a.write else 'DRY RUN'}: {len(replace)} structures changed -> {jp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
