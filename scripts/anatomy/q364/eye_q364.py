#!/usr/bin/env python3
"""Q364: Base pages -- the eyeballs: registration spikes on Base·F and the inside-out sclera.

    python3 scripts/anatomy/q364/eye_q364.py --page-dir DIR             # dry run: measure, report, write nothing
    python3 scripts/anatomy/q364/eye_q364.py --page-dir DIR --write     # and write the page files in DIR

Finding (owner, "eyes are not intact"; Q363 audit): Base·F globes carry spikes up to ~7 mm (sclera, retina, posterior segment,
cornea, iris, anterior chamber) at the posterior pole and the lateral limbus, left by the body registration that built Base·F from
the Z-Anatomy source; one sclera per body is drawn inside-out.

The eye is a rigid organ and the same ids with the same vertex counts and order exist clean on Base·M (the Z-Anatomy source
geometry, read-only from --src-dir). So nothing is sculpted:
  place   per eye (left and right separately, never mirrored) ONE similarity transform (rotation + translation + uniform scale)
          is fitted from the Base·M globe parts to the current Base·F positions of the same vertices (Umeyama, trimmed: vertices
          whose residual exceeds max(TRIM_MIN, TRIM_K x median) are dropped and the fit repeated, so the spikes do not steer it), and
          every globe part's vertices are replaced by the Base·M vertices through that transform. The suspensory ligament of the
          eyeball is placed with its eye only when it carries registration spikes on this page (its long lateral / medial horns
          are the source's own shape: the ligament reaches the check ligaments on the orbital walls).
  winding the sclera is open (corneal aperture in front, optic-nerve aperture behind), so the builder's normal fix could not tell
          inside from outside; a sclera whose faces point mostly into the globe (area-weighted, about the vitreous centre) gets
          its triangle winding reversed (vertex positions and triangle order unchanged). Applied on both pages.
  guards  (per eye; an eye failing any is left as it is and listed) fit residual median <= RES_MED mm on the kept vertices and
          >= KEEP_MIN of the vertices kept; scale within SCALE_RANGE of Base·M and the placed globe's sclera diameter within
          DIAM_RANGE mm (adult eye about 25 mm across: Yogesh, Textbook of Human Anatomy vol. 5, ch. 37, p. 374); no globe vertex
          inside a bone (generalised winding number > 0.5 against every bone near the orbit) unless it was so before; the extra-
          ocular muscles' and the lids' gaps to the globe reported before / after and none may open by more than GAP_ADD mm.
  write   vertex / triangle counts and order unchanged (pose rig contract); every replaced file is first copied beside itself as
          `<name>.q364` (never overwriting); each changed structure's card gets a "Q364: ..." note; a page that already carries a
          Q364 note is refused (idempotent).  Deterministic.  Report: data/derived/Q364_eye_report.json (one entry per page).
"""
from __future__ import annotations

import argparse, base64, json, shutil, sys, time
from pathlib import Path

import numpy as np
import trimesh
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
for p in (HERE.parent / "q340", HERE.parent / "q349"):
    sys.path.insert(0, str(p))
import conform_palm_q340 as C340      # noqa: E402  page I/O, repack, badge_add
import conform_fingers_q349 as C349   # noqa: E402  winding number

OUT = REPO / "data/derived/Q364_eye_report.json"
SRC_DEFAULT = REPO / "build/q309/viewer_zan_atlas"
TAG = "Q364:"
SUFFIX = ".q364"

GLOBE = ["zan_sclera", "zan_cornea", "zan_iris", "zan_lens", "zan_retina", "zan_vitreous_body", "zan_zonular_fibres",
         "zan_anterior_chamber_of_eyeball", "zan_anterior_segment_of_eyeball", "zan_posterior_segment_of_eyeball"]
LIG = "zan_suspensory_ligament_of_eyeball"
MUSCLES = ["superior_rectus", "inferior_rectus", "medial_rectus", "lateral_rectus", "superior_oblique", "inferior_oblique",
           "levator_palpebrae_superioris"]
LIDS = ["zan_superior_tarsus", "zan_inferior_tarsus", "orbicularis_oculi"]
SURFACE = ["zan_sclera", "zan_cornea"]          # the globe's outer surface, for gaps
TRIM_K, TRIM_MIN, TRIM_ITERS = 3.0, 0.5, 8      # trimmed fit: keep residual <= max(TRIM_MIN, TRIM_K x median)
RES_MED = 0.6        # mm, median residual of the kept vertices
KEEP_MIN = 0.85      # share of the globe vertices kept by the trimmed fit
SCALE_RANGE = (0.85, 1.10)   # x Base·M
DIAM_RANGE = (21.0, 27.0)    # mm, sclera extent across its two short axes (25 mm, Yogesh vol. 5 p. 374)
GAP_ADD = 1.0        # mm, a muscle / lid gap may not open by more than this
SPIKE = 1.5          # mm, a ligament vertex farther than this from the transformed source = registration spike
BONE_NEAR = 15.0     # mm, bones whose box comes this close to the globe box are tested
YOGESH_SIZE = "Yogesh, Textbook of Human Anatomy vol. 5 (Head, Neck and Face), ch. 37 Eyeball, p. 374 (eye about 25 mm in diameter)"
YOGESH_LIG = "Yogesh vol. 5, ch. 25, p. 257 (suspensory ligament of Lockwood: a hammock below the eyeball attached laterally and medially to the check ligaments)"


# ------------------------------------------------------------------ geometry
def umeyama(A, B):
    """s, R, t minimising |s R A + t - B| (rows are points)"""
    ma, mb = A.mean(0), B.mean(0)
    a, b = A - ma, B - mb
    U, S, Vt = np.linalg.svd(b.T @ a / len(A))
    D = np.eye(3)
    if np.linalg.det(U) * np.linalg.det(Vt) < 0:
        D[2, 2] = -1
    R = U @ D @ Vt
    s = float(np.trace(np.diag(S) @ D) / (a ** 2).sum(1).mean())
    return s, R, mb - s * R @ ma


def fit(A, B):
    keep = np.ones(len(A), bool)
    for _ in range(TRIM_ITERS):
        s, R, t = umeyama(A[keep], B[keep])
        r = np.linalg.norm(A @ R.T * s + t - B, axis=1)
        k2 = r <= max(TRIM_MIN, TRIM_K * np.median(r[keep]))
        if (k2 == keep).all():
            break
        keep = k2
    return s, R, t, r, keep


def apply(T, V):
    s, R, t = T
    return V @ R.T * s + t


def outward_share(V, F, c):
    """area-weighted share of faces whose normal points away from c"""
    tri = V[F]
    n = np.cross(tri[:, 1] - tri[:, 0], tri[:, 2] - tri[:, 0])
    d = np.einsum("ij,ij->i", n, tri.mean(1) - c)
    a = np.linalg.norm(n, axis=1)
    return float(a[d > 0].sum() / max(a.sum(), 1e-12))


def boundary_loops(V, F, c, axis):
    """open borders of a mesh: per loop its edge count, mean radius about its own centre, and where it sits on the axis"""
    e = np.sort(np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]]), axis=1)
    u, cnt = np.unique(e, axis=0, return_counts=True)
    b = u[cnt == 1]
    nm = int((cnt > 2).sum())
    if not len(b):
        return [], nm
    import scipy.sparse as sp
    from scipy.sparse.csgraph import connected_components
    n = len(V)
    g = sp.coo_matrix((np.ones(len(b)), (b[:, 0], b[:, 1])), shape=(n, n))
    k, lab = connected_components(g, directed=False)
    out = []
    used = np.unique(b)
    for L in np.unique(lab[used]):
        vs = used[lab[used] == L]
        ne = int(np.isin(b[:, 0], vs).sum())
        cc = V[vs].mean(0)
        out.append(dict(edges=ne, radius_mm=round(float(np.linalg.norm(V[vs] - cc, axis=1).mean()), 2),
                        pole=("anterior" if float((cc - c) @ axis) > 0 else "posterior"),
                        offset_mm=round(float((cc - c) @ axis), 1)))
    out.sort(key=lambda x: -x["edges"])
    return out, nm


def surface_tree(parts):
    pts = []
    for V, F in parts:
        tm = trimesh.Trimesh(V, F, process=False)
        p, _ = trimesh.sample.sample_surface(tm, max(4000, int(tm.area * 20)), seed=364)
        pts += [p, V]
    return cKDTree(np.concatenate(pts))


def gap(tree, V):
    return float(tree.query(V)[0].min())


def principal_extent(V):
    c = V.mean(0)
    w, U = np.linalg.eigh(np.cov((V - c).T))
    proj = (V - c) @ U
    return (proj.max(0) - proj.min(0))[::-1], U[:, ::-1]


def stats(d):
    return dict(max_mm=round(float(d.max()), 2), mean_mm=round(float(d.mean()), 2), p95_mm=round(float(np.percentile(d, 95)), 2))


# ------------------------------------------------------------------ write (as conform_in_bone_q357.write_page, originals kept as *.q364)
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


# ------------------------------------------------------------------ per eye
def do_eye(side, V, Vs, byid, bones, is_src):
    ids = [g + "_" + side for g in GLOBE]
    rep = dict(side=side, parts={}, decision=None)
    for i in ids + [LIG + "_" + side]:
        assert i in V and i in Vs, f"{i} missing"
        assert len(V[i][0]) == len(Vs[i][0]), f"{i}: vertex count {len(V[i][0])} vs source {len(Vs[i][0])}"
        rep.setdefault("faces_equal_source", {})[i] = bool(np.array_equal(V[i][1], Vs[i][1]))
    A = np.concatenate([Vs[i][0] for i in ids]); Bc = np.concatenate([V[i][0] for i in ids])
    if is_src:
        T = (1.0, np.eye(3), np.zeros(3)); r = np.linalg.norm(A - Bc, axis=1); keep = np.ones(len(A), bool)
    else:
        s, R, t, r, keep = fit(A, Bc); T = (s, R, t)
    s, R, t = T
    ang = float(np.degrees(np.arccos(np.clip((np.trace(R) - 1) / 2, -1, 1))))
    rep["transform"] = dict(scale=round(s, 4), rotation_deg=round(ang, 2), translation_mm=[round(float(x), 2) for x in t],
                            residual_median_mm=round(float(np.median(r[keep])), 3), residual_p95_kept_mm=round(float(np.percentile(r[keep], 95)), 3),
                            kept_share=round(float(keep.mean()), 4), vertices=int(len(A)),
                            spike_vertices_over_1_5mm=int((r > 1.5).sum()), worst_spike_mm=round(float(r.max()), 2))
    new = {i: apply(T, Vs[i][0]) for i in ids}
    # ligament: spikes on this page?
    li = LIG + "_" + side
    dl = np.linalg.norm(apply(T, Vs[li][0]) - V[li][0], axis=1)
    lig_move = (not is_src) and dl.max() > SPIKE
    if lig_move:
        new[li] = apply(T, Vs[li][0])
    rep["ligament"] = dict(vs_transformed_source=stats(dl), moved=bool(lig_move))
    for i, v1 in new.items():
        d = np.linalg.norm(v1 - V[i][0], axis=1)
        rep["parts"][i] = dict(vertices=len(v1), **stats(d))
    # size
    sc0, sc1 = V["zan_sclera_" + side][0], new["zan_sclera_" + side]
    ext1, U = principal_extent(sc1)
    ext0, _ = principal_extent(sc0)
    rep["sclera_extent_mm"] = dict(before=[round(float(x), 1) for x in ext0], after=[round(float(x), 1) for x in ext1],
                                  source=[round(float(x), 1) for x in principal_extent(Vs["zan_sclera_" + side][0])[0]])
    diam = float(np.mean(ext1[1:]))
    # bone guard: the globe parts (none may be inside a bone) and the ligament (its horns end on the lacrimal and zygomatic bones
    # through the check ligaments, in the source too: they may not go deeper than before)
    def in_bone(P0, P1):
        lo, hi = np.minimum(P0.min(0), P1.min(0)) - BONE_NEAR, np.maximum(P0.max(0), P1.max(0)) + BONE_NEAR
        n0 = n1 = 0; per = []
        for bid, (bv, bf) in bones.items():
            if (bv.max(0) < lo).any() or (bv.min(0) > hi).any():
                continue
            w0 = np.abs(C349.winding(P0, bv, bf)) > 0.5; w1 = np.abs(C349.winding(P1, bv, bf)) > 0.5
            n0 += int(w0.sum()); n1 += int(w1.sum())
            if w0.any() or w1.any():
                per.append(dict(bone=bid, before=int(w0.sum()), after=int(w1.sum())))
        return dict(inside_before=n0, inside_after=n1, bones=per)
    gp = [i for i in ids]
    rep["bone"] = in_bone(np.concatenate([V[i][0] for i in gp]), np.concatenate([new[i] for i in gp]))
    rep["bone_ligament"] = in_bone(V[li][0], new.get(li, V[li][0]))
    inb0, inb1 = rep["bone"]["inside_before"], rep["bone"]["inside_after"]
    # gaps
    t0 = surface_tree([V[i] for i in (x + "_" + side for x in SURFACE)])
    t1 = surface_tree([(new[i], V[i][1]) for i in (x + "_" + side for x in SURFACE)])
    gaps = {}
    for m in [x + "_" + side for x in MUSCLES + LIDS]:
        if m in V:
            gaps[m] = dict(before_mm=round(gap(t0, V[m][0]), 2), after_mm=round(gap(t1, V[m][0]), 2))
    rep["gaps"] = gaps
    # guards
    fails = []
    if not is_src:
        if rep["transform"]["residual_median_mm"] > RES_MED: fails.append("fit residual")
        if keep.mean() < KEEP_MIN: fails.append("too many vertices trimmed")
        if not (SCALE_RANGE[0] <= s <= SCALE_RANGE[1]): fails.append("scale %.3f" % s)
        if not (DIAM_RANGE[0] <= diam <= DIAM_RANGE[1]): fails.append("diameter %.1f mm" % diam)
        if inb1 > 0: fails.append("globe inside a bone (%d -> %d vertices)" % (inb0, inb1))
        bl = rep["bone_ligament"]
        if bl["inside_after"] > bl["inside_before"]: fails.append("ligament deeper into bone (%d -> %d vertices)" % (bl["inside_before"], bl["inside_after"]))
        for m, g in gaps.items():
            if g["after_mm"] > g["before_mm"] + GAP_ADD: fails.append("gap %s %.1f -> %.1f mm" % (m, g["before_mm"], g["after_mm"]))
    rep["sclera_diameter_mm"] = round(diam, 2)
    rep["guards_failed"] = fails
    rep["decision"] = ("source page: no placement" if is_src else ("left as is: " + "; ".join(fails) if fails else "placed"))
    return rep, ({} if (is_src or fails) else new)


def winding_fix(side, V):
    sid = "zan_sclera_" + side
    v, f = V[sid]
    c = V["zan_vitreous_body_" + side][0].mean(0)
    axis = V["zan_cornea_" + side][0].mean(0) - c; axis /= np.linalg.norm(axis)
    sh = outward_share(v, f, c)
    loops, nm = boundary_loops(v, f, c, axis)
    flip = sh < 0.5
    r = dict(outward_share_before=round(sh, 3), flipped=bool(flip), outward_share_after=round(outward_share(v, f[:, ::-1], c), 3) if flip else round(sh, 3),
             open_borders=loops, non_manifold_edges=nm)
    return r, (f[:, ::-1].copy() if flip else None)


def note_place(side_word, part, p, T, lig=False):
    return (f"{TAG} placed whole with its eye: the body registration that built this page from the Z-Anatomy source had left "
            f"spikes on the eyeball (up to {T['worst_spike_mm']:.1f} mm); the source eye (same mesh, same vertices) was put back through ONE "
            f"rigid placement of the {side_word} eye (rotation, shift and uniform scale {T['scale']:.3f}, fitted to this body's eye with the "
            f"spikes left out; residual median {T['residual_median_mm']:.2f} mm); this part moved max {p['max_mm']:.1f} mm, mean {p['mean_mm']:.1f} mm; "
            f"nothing was reshaped." + (" Its long lateral and medial ends are the source's own shape (the ligament reaches the check "
            f"ligaments on the lacrimal and zygomatic bones) and were kept." if lig else ""))


def note_wind(r):
    return (f"{TAG} triangle winding reversed so the outside of the sclera faces outward (it was drawn inside-out: "
            f"{100 * r['outward_share_before']:.0f}% of its surface faced out); positions unchanged. Its openings are anatomical "
            f"(the corneal aperture in front, the optic-nerve aperture behind).")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--page-dir", required=True)
    ap.add_argument("--src-dir", default=str(SRC_DEFAULT), help="the Base·M page dir (Z-Anatomy source geometry), read only")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--allow-build", action="store_true", help="permit --write into build/q309 (the main thread's apply step)")
    ap.add_argument("--json", default=str(OUT))
    a = ap.parse_args(argv)
    d = Path(a.page_dir).resolve(); sd = Path(a.src_dir).resolve()
    if "/build/q309/" in str(d) + "/" and a.write and not a.allow_build:
        print("refused: never write into build/q309 without --allow-build (the main thread's apply step)")
        return 2
    stem = C340.stem_of(d)
    man, blob, files = C340.read_page(d, stem)
    done = [m["id"] for m in man["meshes"] if TAG in (((m.get("rec") or {}).get("procedural_badge")) or "")]
    if done:
        print(f"Q364 already applied to this page ({len(done)} structures carry the Q364 note, e.g. {done[0]}); nothing done")
        return 0
    is_src = d == sd or "female" not in stem
    sman, sblob, _ = C340.read_page(sd, C340.stem_of(sd)) if not is_src else (man, blob, None)
    V = {m["id"]: C340.dec(m, blob) for m in man["meshes"]}
    Vs = {m["id"]: C340.dec(m, sblob) for m in sman["meshes"]}
    if not is_src:   # the source must carry no Q364 placement of its own (its winding fix is harmless: positions are what is used)
        pass
    bones = {m["id"]: V[m["id"]] for m in man["meshes"] if m.get("sys") == "bone"}
    recs = {m["id"]: m.get("rec") for m in man["meshes"]}
    rep = {"schema": "nmsk.q364.eye.v1", "round": "Q364", "generated": time.strftime("%Y-%m-%d"), "page": stem, "written": bool(a.write),
           "source_page": C340.stem_of(sd), "page_is_source": bool(is_src),
           "parameters": dict(trim_k=TRIM_K, trim_min_mm=TRIM_MIN, residual_median_max_mm=RES_MED, keep_min=KEEP_MIN, scale_range=SCALE_RANGE,
                              diameter_range_mm=DIAM_RANGE, gap_add_mm=GAP_ADD, ligament_spike_mm=SPIKE, bone_near_mm=BONE_NEAR),
           "citations": {"size": YOGESH_SIZE, "suspensory_ligament": YOGESH_LIG}, "eyes": {}, "sclera_winding": {}}
    replace, notes = {}, {}
    newV = {}
    for side, word in (("r", "right"), ("l", "left")):
        er, new = do_eye(side, V, Vs, None, bones, is_src)
        rep["eyes"][side] = er
        for i, v1 in new.items():
            newV[i] = v1
            notes[i] = note_place(word, i, er["parts"][i], er["transform"], lig=i.startswith(LIG))
        print("  %s eye: %s  scale %.4f rot %.2f deg  residual med %.3f mm  kept %.3f  worst spike %.1f mm  diam %.1f mm  globe in bone %d->%d  ligament ends in bone %d->%d" % (
        word, er["decision"], er["transform"]["scale"], er["transform"]["rotation_deg"], er["transform"]["residual_median_mm"],
        er["transform"]["kept_share"], er["transform"]["worst_spike_mm"], er["sclera_diameter_mm"], er["bone"]["inside_before"], er["bone"]["inside_after"],
        er["bone_ligament"]["inside_before"], er["bone_ligament"]["inside_after"]), flush=True)
    for side in ("r", "l"):
        Vw = dict(V)
        sid = "zan_sclera_" + side
        if sid in newV:
            Vw[sid] = (newV[sid], V[sid][1])
        wr, f2 = winding_fix(side, Vw)
        rep["sclera_winding"][sid] = wr
        print("  %s: outward share %.2f -> %s; open borders %s" % (sid, wr["outward_share_before"], "flipped" if f2 is not None else "kept",
              [(x["edges"], x["radius_mm"], x["pole"]) for x in wr["open_borders"]]), flush=True)
        if f2 is not None:
            replace[sid] = (newV.get(sid, V[sid][0]), f2)
            notes[sid] = (notes[sid] + " " if sid in notes else "") + note_wind(wr)
    for i, v1 in newV.items():
        if i not in replace:
            replace[i] = (v1, V[i][1])
    rep["geometry_changed"] = sorted(replace)
    rep["cards"] = notes
    if replace:
        man2, blob2 = C340.repack(man, blob, {k: (v, f, C340.badge_add(recs[k], notes[k])) for k, (v, f) in replace.items()})
        for m0, m1 in zip(man["meshes"], man2["meshes"]):
            assert m0["id"] == m1["id"] and m0["vc"] == m1["vc"] and m0["ic"] == m1["ic"]
        assert len(blob2) == len(blob)
        if a.write:
            rep["files_changed"] = write_page(d, stem, man, man2, blob2, files)
            print("  wrote: " + ", ".join(rep["files_changed"]) + " (originals kept as *%s)" % SUFFIX)
    jp = Path(a.json)
    allr = json.loads(jp.read_text(encoding="utf-8")) if jp.exists() else {}
    if allr.get("schema") != "nmsk.q364.eye_report.v1":
        allr = {"schema": "nmsk.q364.eye_report.v1", "pages": {}}
    allr["pages"][stem] = rep
    jp.parent.mkdir(parents=True, exist_ok=True)
    jp.write_text(json.dumps(allr, indent=1, default=lambda o: o.tolist() if isinstance(o, np.ndarray) else (float(o) if isinstance(o, np.floating) else (int(o) if isinstance(o, np.integer) else str(o)))) + "\n",
                  encoding="utf-8")
    print(f"Q364 {'WRITTEN' if a.write else 'DRY RUN'} {stem}: {len(replace)} structures changed -> {jp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
