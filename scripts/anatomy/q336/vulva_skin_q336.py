#!/usr/bin/env python3
"""Q336: Base · Female -- cover the open urogenital triangle with the REAL vulvar / perineal skin surface of the Chinese
Visible Human female (Wu et al. 2015, CC BY 4.0; third_party/cvh_wu2015 mesh 46 "Skin"), registered onto this body.

    python3 scripts/anatomy/q336/vulva_skin_q336.py --page-dir DIR            # dry run: build + measure, write the report only
    python3 scripts/anatomy/q336/vulva_skin_q336.py --page-dir DIR --write    # and write the page files in DIR + the pose rig

What was wrong: Z-Anatomy has no female perineal skin. Its male urogenital patches (penile / scrotal / urogenital-triangle
skin) were removed for the female body (Q196) and the generated closure that replaced them was removed as invented geometry
(Q297), so the page shows a 36-vertex opening from the mons to the anal region (data/derived/Q202_perineal_loop.json).
Q235 / Q297 recorded "no source holds female perineal skin" -- that was wrong: the CVH skin block of the same CVH set
(a cropped block from the iliac crests to the upper thighs, 8,985 vertices) carries the real external surface of the mons
pubis, labia majora, labia minora and vestibule of that woman (renders in docs/Q336_genital_region.md).

Method (every step measured into the report; nothing is drawn by hand, no vertex of the CVH surface is moved relative to another):
  1. bone registration: the CVH pelvic bone + sacrum/coccyx onto this page's hip bones, sacrum and coccyx, rigid + uniform
     scale, bidirectional trimmed closest point (scripts/anatomy/q235/register.sym_icp, the Q235 method), CVH side convention
     sx = -1 (Q235) -- the transform the CVH perineal structures on this page follow;
  2. the CVH block's crop faces (flat caps where the block was cut) are dropped;
  3. ONE similarity transform (rotation + translation + uniform scale: shape unchanged) refits that bone-registered surface onto
     this page's own Z skin in a 70 mm band around the opening (opening dilated 15 mm left out), trimmed closest point;
  4. the piece over the opening is cut out: CVH faces whose centroid projects inside the opening dilated by 25 mm (in the
     opening's own plane) and lies within 60 mm of its fan membrane, largest connected piece, minus the faces that would stand
     in FRONT of a neighbouring patch outside the opening (so the border tucks UNDER the neighbours, never over them);
     interior holes closed with their own CVH faces where the source has them (the introitus / meatus holes of the source stay);
  5. a 3.0 mm closed slab like every Z skin patch (inner sheet 3.0 mm behind along the vertex normals, own rim wall).
The seam is NOT welded: the patch border lies under the neighbouring Z patches (the vulva is another person's real surface and
this body's crotch is Z-Anatomy's male-derived shape; welding it would need the deformation Q186b already rejected).
Measured: see-through rays through the opening before / after, border depth under the neighbours, shift of the surface against the
organ-consistent (bone-only) placement, left / right mirror distance.
The patch is appended as `skin_vulva_cvh` (sys skin), rigid in the pelvis segment of the pose rig (as the removed closure
was); the ten neighbouring Z skin cards get a Q336 sentence in place of the Q297 "open perineum" note. Nothing else moves.
Every file replaced is copied beside itself as `<name>.q336` first (never overwriting an existing copy).
"""
from __future__ import annotations

import argparse
import base64
import json
import re
import shutil
import sys
import time
from pathlib import Path

import numpy as np
import scipy.sparse as sp
from scipy.sparse.csgraph import connected_components
import trimesh
from matplotlib.path import Path as MPath
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
for p in (REPO, REPO / "scripts" / "zanatomy", REPO / "scripts" / "anatomy" / "q235", HERE):
    sys.path.insert(0, str(p))
import build_zan_atlas_viewer as B  # noqa: E402  pack_mesh / split_blob (the builder's own layout)
import cvh as CV                    # noqa: E402  CVH loader + atlas axes (Q235)
import register as RG               # noqa: E402  sym_icp / rot / apply (Q235)
import q202_geom as GG              # noqa: E402  split_slab (outer / inner sheet of a Z skin patch)

STEM = "atlas_viewer_base_female"
NEW_ID = "skin_vulva_cvh"
LOOP = REPO / "data/derived/Q202_perineal_loop.json"
REPORT = REPO / "data/derived/Q336_vulva_skin_report.json"
RIG = REPO / "data/anatomy/pose_rig_base_f.json"
SX = -1                     # Q235: CVH file +x is the patient's LEFT
THICK = 3.0                 # Z skin slab thickness (Q202)
CAP_TOL = 2.0               # mm from a crop plane of the CVH block
MEMBRANE_MM = 60.0          # piece faces within this distance of the opening's fan membrane
BAND_MM = 70.0              # CVH skin within this distance of the rim drives the similarity refit
FLAP_MM = 3.0               # a border vertex this far in front of a neighbour's outer sheet is cut off (no shards through it)
DIL_MM = 25.0               # the piece reaches this far past the rim, under the neighbouring patches
DEBUG = {}
LIT = {"files": re.compile(r"^window\.__ANATOMY_BIN_FILES__=(.*);$", re.M),
       "manifest": re.compile(r"^window\.__ANATOMY_MANIFEST__=(.*);$", re.M)}
ORGANS = ["clitoris_cavernous_body", "vestibular_bulb_l", "vestibular_bulb_r", "bartholin_gland_l", "bartholin_gland_r",
          "vagina", "urethra_female_submucous_layer", "urethra_female_lumen", "perineal_body", "bulbospongiosus_cvh",
          "ischiocavernosus_cvh_l", "ischiocavernosus_cvh_r", "urethrovaginal_sphincter_cvh", "urethral_compressor_cvh",
          "superficial_transverse_perineal_cvh", "deep_perineal_muscle_cvh", "external_anal_sphincter_ct_vhf",
          "zan_external_pudendal_veins_l", "zan_external_pudendal_veins_r", "zan_superficial_external_pudendal_artery_l",
          "zan_superficial_external_pudendal_artery_r", "round_ligament_uterus_l", "round_ligament_uterus_r",
          "adductor_longus_l", "adductor_longus_r", "gracilis_l", "gracilis_r", "pubic_symphysis_disc", "hip_bone_l", "hip_bone_r"]


# ------------------------------------------------------------------ page I/O (q333 / ship_q319 layout)
def pages_of(d: Path):
    return [p for p in (d / f"{STEM}.html", d / "index.html") if p.exists()]


def ser_manifest(man):
    return json.dumps(man, separators=(",", ":")).replace("</", "<\\/")


def read_page(d: Path):
    t = pages_of(d)[0].read_text(encoding="utf-8")
    man = json.loads(LIT["manifest"].search(t).group(1))
    files = json.loads(LIT["files"].search(t).group(1))
    blob = b"".join(base64.b64decode((d / f["path"]).read_bytes()) for f in files)
    return man, blob, files


def dec(m, blob):
    q = np.frombuffer(blob, np.uint16, m["vc"] * 3, m["vo"]).reshape(-1, 3).astype(np.float64)
    f = np.frombuffer(blob, np.uint16, m["ic"] * 3, m["io"]).reshape(-1, 3).astype(np.int64)
    return np.asarray(m["min"]) + q / 65535.0 * np.asarray(m["span"]), f


def repack(man, blob, replace_rec, add, drop):
    """untouched meshes keep their own bytes; `replace_rec` only swaps card records; `add` = [(entry, v, f)]"""
    meshes, chunks, off = [], [], 0
    for m in man["meshes"]:
        if m["id"] in drop:
            continue
        n = dict(m)
        if m["id"] in replace_rec:
            n["rec"] = replace_rec[m["id"]]
        pos = blob[m["vo"]: m["vo"] + m["vc"] * 6]; idx = blob[m["io"]: m["io"] + m["ic"] * 6]
        n["vo"], n["io"] = off, off + len(pos)
        chunks += [pos, idx]; off += len(pos) + len(idx)
        meshes.append(n)
    for entry, v, f in add:
        fields, packed = B.pack_mesh(np.asarray(v, float), np.asarray(f), off)
        n = dict(entry); n.update(fields)
        meshes.append(n); chunks.append(packed); off += len(packed)
    man2 = dict(man); man2["meshes"] = meshes
    t = json.loads(json.dumps(man.get("totals") or {}))
    if t:
        t["meshes"] = len(meshes)
        bl = t.setdefault("by_layer", {})
        for _id in drop:
            bl["skin"] = bl.get("skin", 0) - 1
        for entry, _, _ in add:
            bl[entry["sys"]] = bl.get(entry["sys"], 0) + 1
        man2["totals"] = t
    return man2, b"".join(chunks)


def write_page(d: Path, man_old, man_new, blob_new, old_files):
    pages = pages_of(d)
    texts = {p: p.read_text(encoding="utf-8") for p in pages}
    for p, t in texts.items():
        assert LIT["manifest"].search(t).group(1) == ser_manifest(man_old), f"{p}: manifest serialisation differs"
        assert LIT["files"].search(t).group(1) == json.dumps(old_files), f"{p}: file list serialisation differs"
    chunks = B.split_blob(blob_new, STEM)
    assert [n for n, _ in chunks] == [f["path"] for f in old_files], "geo file set would change; not handled"
    files = [{"path": n, "bytes": len(c), "enc": "base64"} for n, c in chunks]
    changed = []
    for n, c in chunks:
        p = d / n; new = base64.b64encode(c)
        if p.read_bytes() != new:
            bk = p.with_name(p.name + ".q336")
            if not bk.exists():
                shutil.copy2(p, bk)
            p.write_bytes(new); changed.append(n)
    for p, t in texts.items():
        bk = p.with_name(p.name + ".q336")
        if not bk.exists():
            shutil.copy2(p, bk)
        t2 = LIT["manifest"].sub(lambda _m: "window.__ANATOMY_MANIFEST__=" + ser_manifest(man_new) + ";", t, count=1)
        t2 = LIT["files"].sub(lambda _m: "window.__ANATOMY_BIN_FILES__=" + json.dumps(files) + ";", t2, count=1)
        p.write_text(t2, encoding="utf-8"); changed.append(p.name)
    return changed


# ------------------------------------------------------------------ geometry helpers
def loop_rails(V):
    L = json.loads(LOOP.read_text())["loop"]
    P = np.array([V(e["members"][0][0])[e["members"][0][1]] for e in L])
    Q = np.array([V(e["partner_members"][0][0])[e["partner_members"][0][1]] for e in L])
    return P, Q


def loop_frame(P):
    c0 = P.mean(0); _, _, vt = np.linalg.svd(P - c0)
    e1, e2, nrm = vt
    # the opening faces anterior-inferior on these pages
    if nrm @ np.array([0.0, -0.55, 0.83]) < 0:
        nrm = -nrm
    poly = MPath(np.c_[(P - c0) @ e1, (P - c0) @ e2])
    return c0, e1, e2, nrm, poly


def in_loop(X, fr, radius=0.0):
    c0, e1, e2, _, poly = fr
    q = np.c_[(X - c0) @ e1, (X - c0) @ e2]
    if radius == 0.0:
        return poly.contains_points(q)
    return poly.contains_points(q, radius=radius) | poly.contains_points(q, radius=-radius)


def fan_points(P):
    c0 = P.mean(0); out = []
    for i in range(len(P)):
        a, b = P[i], P[(i + 1) % len(P)]
        for s in np.linspace(0, 1, 15):
            for t in np.linspace(0, 1 - s, max(2, int(15 * (1 - s)) + 1)):
                out.append(c0 + s * (a - c0) + t * (b - c0))
    return np.array(out)


def seg_dist(Qs, P):
    best = np.full(len(Qs), 1e9)
    for a, b in zip(P, np.roll(P, -1, 0)):
        ab = b - a; t = np.clip(((Qs - a) @ ab) / (ab @ ab), 0, 1)
        best = np.minimum(best, np.linalg.norm(Qs - (a + t[:, None] * ab), axis=1))
    return best


def boundary_loops(f):
    e = np.sort(np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]), axis=1)
    u, c = np.unique(e, axis=0, return_counts=True)
    be = u[c == 1]
    adj = {}
    for a, b in be:
        adj.setdefault(a, []).append(b); adj.setdefault(b, []).append(a)
    seen, loops = set(), []
    for s in adj:
        if s in seen:
            continue
        lp = [s]; seen.add(s); prev, cur = None, s
        while True:
            nx = [x for x in adj[cur] if x != prev and (x not in seen or (x == s and len(lp) > 2))]
            if not nx:
                break
            n = nx[0]
            if n == s:
                break
            lp.append(n); seen.add(n); prev, cur = cur, n
        loops.append(np.array(lp))
    return sorted(loops, key=len, reverse=True), be


def largest_component(F, mask):
    idx = np.flatnonzero(mask)
    sub = F[idx]
    e = np.concatenate([sub[:, [0, 1]], sub[:, [1, 2]], sub[:, [2, 0]]]); fi = np.tile(np.arange(len(sub)), 3)
    key = np.sort(e, axis=1); o = np.lexsort((key[:, 1], key[:, 0])); key, fi = key[o], fi[o]
    same = np.all(key[1:] == key[:-1], axis=1)
    A = sp.coo_matrix((np.ones(same.sum()), (fi[:-1][same], fi[1:][same])), shape=(len(sub), len(sub)))
    nc, lab = connected_components(A, directed=False)
    keep = lab == np.argmax(np.bincount(lab))
    out = np.zeros(len(F), bool); out[idx[keep]] = True
    return out


def fill_holes_from_source(F, sel, holes, outer):
    """unselected source faces in edge-connected groups that touch only interior hole borders (never the outer border)"""
    hole_v = set(int(x) for h in holes for x in h); outer_v = set(int(x) for x in outer)
    rest = np.flatnonzero(~sel)
    sub = F[rest]
    e = np.concatenate([sub[:, [0, 1]], sub[:, [1, 2]], sub[:, [2, 0]]]); fi = np.tile(np.arange(len(sub)), 3)
    key = np.sort(e, axis=1); o = np.lexsort((key[:, 1], key[:, 0])); key, fi = key[o], fi[o]
    same = np.all(key[1:] == key[:-1], axis=1)
    A = sp.coo_matrix((np.ones(same.sum()), (fi[:-1][same], fi[1:][same])), shape=(len(sub), len(sub)))
    nc, lab = connected_components(A, directed=False)
    selv = set(np.unique(F[sel]).tolist())
    out = np.zeros(len(F), bool)
    for c in range(nc):
        fc = np.flatnonzero(lab == c)
        if len(fc) > 600:
            continue
        vs = set(np.unique(sub[fc]).tolist()) & selv
        if vs and vs <= hole_v and not (vs & outer_v):
            out[rest[fc]] = True
    return out


def stats(x):
    x = np.asarray(x, float)
    return {"median": round(float(np.median(x)), 2), "p90": round(float(np.percentile(x, 90)), 2),
            "max": round(float(x.max()), 2)}


# ------------------------------------------------------------------ the build
def build(man, blob, log=print, placement="surface"):
    ids = {m["id"]: m for m in man["meshes"]}
    cache = {}

    def V(i):
        if i not in cache:
            cache[i] = dec(ids[i], blob)
        return cache[i][0]

    P, Q = loop_rails(V)
    fr = loop_frame(P)
    rep = {"loop": {"n": int(len(P)), "perimeter_mm": round(float(np.linalg.norm(P - np.roll(P, -1, 0), axis=1).sum()), 1),
                    "rail_gap_mm": stats(np.linalg.norm(P - Q, axis=1))}}

    # 1. bones
    src = np.vstack([CV.to_atlas(CV.load_raw(44)[0], SX), CV.to_atlas(CV.load_raw(45)[0], SX)])
    dst = np.vstack([V(k) for k in ("hip_bone_l", "hip_bone_r", "sacrum", "coccyx")])
    best = None
    for pitch in (-0.3, -0.15, 0.0, 0.15, 0.3):
        R0 = RG.rot(pitch=pitch)
        T0 = (1.0, R0, dst[dst[:, 1] < 40].mean(0) - src.mean(0) @ R0.T)
        T, d = RG.sym_icp(src, dst, T0)
        if best is None or np.median(d) < best[2]:
            best = (T, d, float(np.median(d)))
    T, d, _ = best
    rep["bone_registration"] = {"method": "rigid + uniform scale, bidirectional trimmed closest point (Q235 sym_icp), "
                                          "CVH pelvic bone + sacrum/coccyx -> hip bones, sacrum, coccyx; sx = -1",
                                "scale": round(float(T[0]), 4), "residual_mm": stats(d)}
    log(f"  bones: scale {T[0]:.4f}, residual median {np.median(d):.2f} / p90 {np.percentile(d, 90):.2f} mm")

    # 2. CVH skin, crop caps off, bone-registered
    Vr, Fr = CV.load_raw(46)
    Va, Fa = CV.to_atlas(Vr, SX, Fr)
    Vb = RG.apply(T, Va)
    lo, hi = Vr.min(0), Vr.max(0)
    cap = np.zeros(len(Fr), bool)
    for ax in range(3):
        for val in (lo[ax], hi[ax]):
            cap |= np.all(np.abs(Vr[Fr][:, :, ax] - val) < CAP_TOL, axis=1)
    F = Fa[~cap]
    rep["cvh_skin"] = {"vertices": int(len(Vr)), "triangles": int(len(Fr)), "crop_cap_triangles_dropped": int(cap.sum())}

    # target: outer sheets of this page's Z skin around the opening (the patches whose outer sheet comes within 80 mm of the rim)
    bones = np.vstack([V(k) for k in ("hip_bone_l", "hip_bone_r", "sacrum", "coccyx", "femur_l", "femur_r")])
    bt = cKDTree(bones)
    TV, TN, tids, zmesh = [], [], [], []
    for m in man["meshes"]:
        if m["sys"] != "skin" or m["id"] == NEW_ID:
            continue
        v, f = dec(m, blob)
        if seg_dist(v, P).min() > 80:
            continue
        mo, _, _, _ = GG.split_slab(v, f, bt)
        fo = f[mo]
        c = v[fo].mean(1); n = GG.face_normals(v, fo)
        TV.append(c); TN.append(n); tids.append(m["id"]); zmesh.append((v, f))
    TV = np.vstack(TV); TN = np.vstack(TN); tr = cKDTree(TV)
    zall = _crop(trimesh.util.concatenate([trimesh.Trimesh(v, f, process=False) for v, f in zmesh]), P)
    zouter = _crop(trimesh.Trimesh(*_outer_only(zmesh, bt), process=False), P)

    # 3. one similarity transform (rotation, translation, uniform scale -- no shape change) of the bone-registered CVH skin onto
    #    this page's skin in a band around the opening (CVH vertices within BAND_MM of the rim, the opening dilated by 15 mm left out)
    used = np.unique(F)
    S0 = Vb[used]
    band = (seg_dist(S0, P) < BAND_MM) & ~in_loop(S0, fr, 15.0)
    src = S0[band]
    Ts = (1.0, np.eye(3), np.zeros(3))
    for _ in range(40 if placement == "surface" else 0):
        Y = RG.apply(Ts, src); dd, ii = tr.query(Y)
        k = dd < np.quantile(dd, 0.8)
        Ts = RG.umeyama(src[k], TV[ii[k]], scale=True)
    Y = RG.apply(Ts, src); dd, ii = tr.query(Y)
    X = RG.apply(Ts, Vb)
    sc_total = float(T[0] * Ts[0])
    rep["surface_fit"] = {"method": "similarity (rotation + translation + uniform scale), trimmed closest point (80 %), 40 rounds, "
                                    f"CVH skin within {BAND_MM:.0f} mm of the rim (opening dilated 15 mm excluded) onto the outer "
                                    "sheets of this page's Z skin patches",
                          "target_patches": tids, "band_points": int(band.sum()), "scale_after_bones": round(float(Ts[0]), 4),
                          "total_scale_cvh_to_page": round(sc_total, 4),
                          "rotation_deg_after_bones": round(float(np.degrees(np.arccos(np.clip((np.trace(Ts[1]) - 1) / 2, -1, 1)))), 2),
                          "translation_mm_after_bones": round(float(np.linalg.norm(X[used].mean(0) - Vb[used].mean(0))), 1),
                          "band_distance_to_page_skin_mm": stats(dd)}
    log(f"  similarity refit: scale x{Ts[0]:.3f} (total x{sc_total:.3f}), band distance median {np.median(dd):.2f} mm")

    # 4. the piece: CVH faces over the opening dilated by DIL_MM (so the border tucks under the neighbours) and within 35 mm of the
    #    opening's fan membrane, largest connected piece; minus the flaps that would stand in FRONT of a neighbour outside the
    #    opening; interior holes (deep labial folds) closed with their own CVH faces
    ft = cKDTree(fan_points(P))
    cen = X[F].mean(1)
    sel = in_loop(cen, fr, DIL_MM) & (ft.query(cen)[0] < MEMBRANE_MM)
    sel = largest_component(F, sel)
    # a face goes when ANY of its vertices outside the opening stands more than FLAP_MM in front of a neighbour's outer sheet
    vs = np.unique(F[sel])
    vout = vs[~in_loop(X[vs], fr)]
    cpz, dz, tz = trimesh.proximity.closest_point(zouter, X[vout])
    proud = np.zeros(len(X), bool)
    proud[vout] = np.einsum("ij,ij->i", X[vout] - cpz, zouter.face_normals[tz]) > FLAP_MM
    front = sel & proud[F].any(1)
    sel &= ~front
    sel = largest_component(F, sel)
    added = 0
    for _ in range(4):
        loops, _ = boundary_loops(F[sel])
        extra = fill_holes_from_source(F, sel, loops[1:], loops[0]) & ~proud[F].any(1)
        if not extra.any():
            break
        sel |= extra; added += int(extra.sum())
    used_v = np.unique(F[sel]); remap = -np.ones(len(X), int); remap[used_v] = np.arange(len(used_v))
    po = X[used_v].copy(); pf = remap[F[sel]]
    if (trimesh.Trimesh(po, pf, process=False).face_normals.mean(0) @ fr[3]) < 0:
        pf = pf[:, ::-1]
    loops, _ = boundary_loops(pf)
    om = trimesh.Trimesh(po, pf, process=False)
    # border: how deep under the neighbours (positive = behind their outer sheet)
    bv = loops[0]
    cpb, db, tb = trimesh.proximity.closest_point(zouter, po[bv])
    depth = -np.einsum("ij,ij->i", po[bv] - cpb, zouter.face_normals[tb])
    inside_open_b = in_loop(po[bv], fr)
    rep["piece"] = {"triangles": int(len(pf)), "vertices": int(len(po)), "hole_faces_added_from_source": added,
                    "flap_faces_removed": int(front.sum()), "boundary_loops": [int(len(lp)) for lp in loops],
                    "outer_area_mm2": round(float(om.area), 1),
                    "border_depth_under_neighbour_skin_mm": stats(depth[~inside_open_b]) if (~inside_open_b).any() else None,
                    "border_vertices_inside_opening": int(inside_open_b.sum()), "border_vertices": int(len(bv)),
                    "rim_to_piece_mm": stats(trimesh.proximity.closest_point(om, P)[1])}
    DEBUG.update(X=X, F=F, sel=sel, po=po, pf=pf, P=P, Q=Q, Vb=Vb)

    # 5. see-through test of the opening, before and after: rays from outside onto points of the fan membrane, in a cone of
    #    directions around the opening's outward normal; a ray that reaches 15 mm beyond its membrane point without hitting any
    #    skin is a hole you can see through
    caps = []                                    # metric only: the source's own interior openings (introitus / meatus) capped
    for lp in loops[1:]:
        caps.append(po[lp].mean(0))
    capv = np.vstack([po] + ([np.array(caps)] if caps else []))
    capf = [pf] + [np.array([[lp[k], lp[(k + 1) % len(lp)], len(po) + j] for k in range(len(lp))]) for j, lp in enumerate(loops[1:])]
    om_c = trimesh.Trimesh(capv, np.vstack(capf), process=False)
    rep["see_through"] = {"before": see_through(zall, P, fr), "after": see_through(trimesh.util.concatenate([zall, om]), P, fr),
                          "after_source_openings_capped": see_through(trimesh.util.concatenate([zall, om_c]), P, fr),
                          "source_interior_openings": [int(len(lp)) for lp in loops[1:]]}
    log(f"  see-through rays: before {rep['see_through']['before']['open_share']:.3f}, after {rep['see_through']['after']['open_share']:.3f}")

    # 6. slab like every Z skin patch: inner sheet THICK mm behind along the vertex normals, closed by its own rim wall
    nrm = om.vertex_normals
    pi = po - THICK * nrm
    nv = len(po)
    Fo = pf; Fi = pf[:, ::-1] + nv
    fdir = set()
    for f_ in Fo:
        fdir |= {(int(f_[0]), int(f_[1])), (int(f_[1]), int(f_[2])), (int(f_[2]), int(f_[0]))}
    walls = []
    _, bedges = boundary_loops(pf)
    for a, b in bedges:
        a, b = int(a), int(b)
        if (a, b) not in fdir:
            a, b = b, a
        walls += [[b, a, a + nv], [b, a + nv, b + nv]]
    Vs = np.vstack([po, pi]); Fs = np.vstack([Fo, Fi, np.array(walls, int).reshape(-1, 3)])
    slab = trimesh.Trimesh(Vs, Fs, process=False)
    rep["slab"] = {"thickness_mm": THICK, "vertices": int(len(Vs)), "triangles": int(len(Fs)),
                   "watertight": bool(slab.is_watertight), "winding_consistent": bool(slab.is_winding_consistent),
                   "volume_cm3": round(float(abs(slab.volume)) / 1000.0, 3), "outer_area_mm2": round(float(om.area), 1)}
    log(f"  piece {len(pf)} triangles, slab {abs(slab.volume) / 1000:.2f} cm3, watertight {slab.is_watertight}")

    # checks: left / right symmetry of the outer sheet, against the neighbouring Z skin's own
    mir = po * np.array([-1, 1, 1])
    d1 = cKDTree(po).query(mir)[0]
    zl = np.vstack([V(i) for i in ("zan_skin_anterior_region_of_thigh_l", "zan_skin_anal_region_l")])
    zr = np.vstack([V(i) for i in ("zan_skin_anterior_region_of_thigh_r", "zan_skin_anal_region_r")])
    d2 = cKDTree(zr).query(zl * np.array([-1, 1, 1]))[0]
    rep["symmetry"] = {"outer_sheet_mirror_nn_mm": stats(d1), "neighbour_z_skin_mirror_nn_mm": stats(d2),
                       "centroid_x_mm": round(float(po[:, 0].mean()), 2),
                       "note": "the CVH woman's own vulva is not mirror-exact; the Z neighbours are exact mirrors by construction"}
    # organs vs the new skin: nearest distance only (the vestibule is a deep concave cleft, so a nearest-face sign cannot tell
    # inside from outside there); and how far the surface sits from its organ-consistent (bone-only) placement
    org = {}
    om_b = trimesh.Trimesh(Vb[used_v], pf, process=False)
    for i in ORGANS:
        if i not in ids:
            continue
        v = V(i)
        org[i] = {"nearest_mm": round(float(trimesh.proximity.closest_point(om, v)[1].min()), 1),
                  "nearest_if_bone_only_mm": round(float(trimesh.proximity.closest_point(om_b, v)[1].min()), 1)}
    rep["shift_vs_bone_only_mm"] = stats(np.linalg.norm(X[used_v] - Vb[used_v], axis=1))
    rep["organs_vs_new_skin"] = org
    return Vs, Fs, rep


def _outer_only(zmesh, bt):
    vs, fs, off = [], [], 0
    for v, f in zmesh:
        mo, _, _, _ = GG.split_slab(v, f, bt)
        vs.append(v); fs.append(f[mo] + off); off += len(v)
    return np.vstack(vs), np.vstack(fs)


def _crop(m, P, r=110.0):
    c = m.triangles_center
    k = np.linalg.norm(c - P.mean(0), axis=1) < r
    return trimesh.Trimesh(m.vertices, m.faces[k], process=False)


def see_through(mesh, P, fr, n_dirs=7, reach=15.0):
    c0, e1, e2, nrm, _ = fr
    pts = fan_points(P)[::6]
    dirs = [nrm]
    for k in range(n_dirs - 1):
        a = 2 * np.pi * k / (n_dirs - 1)
        d = nrm + 0.5 * (np.cos(a) * e1 + np.sin(a) * e2); dirs.append(d / np.linalg.norm(d))
    origins, vecs = [], []
    for d in dirs:
        origins.append(pts + 150.0 * d); vecs.append(np.repeat(-d[None], len(pts), 0))
    O = np.vstack(origins); D = np.vstack(vecs)
    locs, ri, _ = mesh.ray.intersects_location(O, D, multiple_hits=False)
    hit = np.full(len(O), np.inf)
    hit[ri] = np.linalg.norm(locs - O[ri], axis=1)
    open_ = hit > 150.0 + reach
    none = ~np.isfinite(hit) | (hit > 150.0 + 120.0)
    return {"rays": int(len(O)), "open": int(open_.sum()), "open_share": round(float(open_.mean()), 4),
            "reach_mm": reach, "no_skin_within_120mm": int(none.sum()), "no_skin_share": round(float(none.mean()), 4)}


# ------------------------------------------------------------------ cards
CITE = ("Chinese Visible Human young adult female: Wu Y, Dabhoiwala NF, Hagoort J, Shan JL, Tan LW, Fang BJ, Zhang SX, Lamers WH. "
        "3D topography of the young adult anal sphincter complex reconstructed from undeformed serial anatomical sections. "
        "PLoS ONE 2015;10(8):e0132226, doi:10.1371/journal.pone.0132226, S3 Fig (CC BY 4.0; third_party/cvh_wu2015, mesh 46 'Skin')")


def new_entry(rep):
    b = rep["bone_registration"]; s = rep["surface_fit"]; pc = rep["piece"]; st = rep["see_through"]
    sl = rep["slab"]; sh = rep["shift_vs_bone_only_mm"]; sy = rep["symmetry"]
    bd = pc["border_depth_under_neighbour_skin_mm"] or {"median": 0, "p90": 0, "max": 0}
    badge = (
        "REAL SURFACE OF ANOTHER PERSON, REGISTERED onto this body -- not this body's skin, not drawn by hand, not deformed. "
        f"Source: {CITE}. The CVH skin block (cropped from the iliac crests to the upper thighs) carries the external surface of the "
        "mons pubis, labia majora, labia minora and vestibule at the resolution of that segmentation (2-4 mm triangles); the source "
        "has no separate labium, prepuce, glans or hymen object, so none is named separately here, and its two small openings in "
        "the vestibule (introitus / urethral meatus region) are kept as the source has them. "
        f"Placement (Q336, scripts/anatomy/q336/vulva_skin_q336.py): (1) CVH pelvic bones onto this page's hip bones, sacrum and coccyx, "
        f"rigid + uniform scale x{b['scale']} (residual median {b['residual_mm']['median']} / p90 {b['residual_mm']['p90']} mm) -- the "
        "transform the CVH perineal structures on this page follow; (2) one similarity transform (shape unchanged) onto this page's "
        f"own skin in a 70 mm band around the opening: scale x{s['scale_after_bones']} (x{s['total_scale_cvh_to_page']} in all), "
        f"rotation {s['rotation_deg_after_bones']} deg, band distance median {s['band_distance_to_page_skin_mm']['median']} / p90 "
        f"{s['band_distance_to_page_skin_mm']['p90']} mm; the surface therefore sits median {sh['median']} / max {sh['max']} mm away "
        "from the placement that would keep the CVH woman's own skin-to-organ relation exactly; (3) cut to the opening, its border "
        f"tucked UNDER the neighbouring Z patches (median {bd['median']} / p90 {bd['p90']} mm behind their outer surface; not welded); "
        f"(4) a {sl['thickness_mm']} mm closed slab like every Z skin patch, {sl['volume_cm3']} cm3, outer area {sl['outer_area_mm2']} mm2. "
        f"Cover: rays through the opening that meet no skin within {st['after']['reach_mm']:.0f} mm of it {st['before']['open_share'] * 100:.0f} % "
        f"before -> {st['after']['open_share'] * 100:.0f} % after; meeting no skin at all {st['before']['no_skin_share'] * 100:.0f} % -> "
        f"{st['after']['no_skin_share'] * 100:.0f} %. Known limits: between the posterior commissure and the anal region the CVH perineum "
        "lies 20-30 mm deeper than this body's Z thigh and anal skin, so that strip is a recessed crevice; the Base body's crotch is "
        "Z-Anatomy's male-derived shape, so the vulva is narrower than the space the CVH woman's thighs leave it; left / right mirror "
        f"distance of the surface median {sy['outer_sheet_mirror_nn_mm']['median']} / p90 {sy['outer_sheet_mirror_nn_mm']['p90']} mm "
        "(a real, not mirror-exact vulva). Pubic hair, the prepuce and frenulum of the clitoris, the hymen and the paraurethral "
        "(Skene) glands are not modelled.")
    rec = {"name": "Vulva and perineal skin (CVH, registered)", "latin": "Pudendum femininum (vulva), cutis",
           "folder": "skin", "region": "perineum",
           "source": CITE + "; placement Q336 (this card). Anatomy: Gray's Anatomy (20th ed. 1918, public domain), 'The External "
                     "Organs' of the female genital organs (pudendum: mons pubis, labia majora, labia minora, clitoris, vestibule); "
                     "Lloyd J et al. BJOG 2005;112:643-6, doi:10.1111/j.1471-0528.2004.00517.x (normal variation of vulval dimensions)",
           "geom_src": "Chinese Visible Human female skin (Wu et al. 2015, CC BY 4.0), registered by bones and one similarity fit to this "
                       "page's skin (Q336) -- NOT Z-Anatomy geometry",
           "method": "registered other person's real surface (rigid + uniform scale), not deformed",
           "procedural_badge": badge,
           "notes": "Covers the opening left in the female Base body where Z-Anatomy's male urogenital skin was removed (Q196) and the "
                    "generated closure was removed (Q297). Visible on it: mons pubis, labia majora, labia minora, vestibule, anterior "
                    "perineum."}
    return {"name": rec["name"], "id": NEW_ID, "side": "m", "sys": "skin", "rec": rec}


NEIGH_NOTE = ("Q336: the opening between the thighs is now covered by `skin_vulva_cvh` -- the REAL vulvar / perineal skin surface of "
              "the Chinese Visible Human female (Wu et al. 2015, CC BY 4.0; the 'Skin' mesh of the same CVH set as the perineal "
              "muscles), registered onto this body, its border tucked under this patch (its own card gives the method and the numbers). "
              "Q297 had removed a generated closure there and recorded that no source held female perineal skin; that record was "
              "wrong -- the CVH skin block carries it.")


def neighbour_recs(man):
    out = {}
    for m in man["meshes"]:
        if m["sys"] != "skin":
            continue
        r = m.get("rec") or {}
        b = r.get("procedural_badge", "")
        if "|| Q297:" not in b or "perineum of this page is deliberately shown OPEN" not in b:
            continue
        r2 = dict(r)
        r2["procedural_badge"] = b[: b.index("|| Q297:")] + "|| " + NEIGH_NOTE
        out[m["id"]] = r2
    return out


CVH_NOTE = ("|| Q336 correction: the CVH set DOES contain the vulvar skin surface (its 'Skin' mesh, 46 of 47); it now ships on this "
            "page as `skin_vulva_cvh` ('Vulva and perineal skin (CVH, registered)'). Where this card says that no labia, mons pubis, "
            "vulva or vulvar / perineal skin exists, it describes the page before Q336.")


def cvh_recs(man, already):
    """the CVH perineal cards that still say the vulvar skin does not exist get the Q336 correction appended (idempotent)"""
    out = {}
    for m in man["meshes"]:
        r = already.get(m["id"]) or m.get("rec") or {}
        b = r.get("procedural_badge", "")
        if "Q336 correction" in b:
            continue
        if "vulvar skin surface are not in the CVH set" in b or "has no vulvar, labial or perineal surface" in b:
            r2 = dict(r); r2["procedural_badge"] = b + " " + CVH_NOTE
            out[m["id"]] = r2
    return out


# ------------------------------------------------------------------ pose rig
def splice_rig(man_old, man_new, write, rig_path=RIG):
    """man_old = the page as it was before this write (with or without an earlier skin_vulva_cvh as its last mesh)"""
    src = json.loads(rig_path.read_text(encoding="utf-8"))
    R = src["rig"]
    ids_old = [m["id"] for m in man_old["meshes"]]
    ids_new = [m["id"] for m in man_new["meshes"]]
    assert R["count"] == len(ids_old), f"rig count {R['count']} != page {len(ids_old)} (rig and page out of step)"
    assert ids_new[-1] == NEW_ID
    nv_new = [int(m["vc"]) for m in man_new["meshes"]]
    assert nv_new[:len(ids_old) - (1 if ids_old[-1] == NEW_ID else 0)] == R["nv"][:len(ids_old) - (1 if ids_old[-1] == NEW_ID else 0)], \
        "the rig's vertex counts differ from the page: rig and page out of step"
    R2 = dict(R)            # every other entry (segments, joints, skin entries, weights blob) kept byte for byte
    R2["nv"] = nv_new
    if ids_old[-1] == NEW_ID:                       # re-run: same index, only its vertex count may change
        assert len(ids_new) == len(ids_old)
        change = "re-run: vertex count of the existing entry updated"
    else:
        assert len(ids_new) == len(ids_old) + 1 and ids_new[:-1] == ids_old, "existing indices must not move"
        seg = next(i for i, s_ in enumerate(R["segs"]) if s_[0] == "pelvis")
        rigid = {g[0]: list(g[1]) for g in R["rigid"]}
        rigid.setdefault(seg, []).append(len(ids_old))
        R2["count"] = len(ids_new)
        R2["rigid"] = [[s_, sorted(v)] for s_, v in sorted(rigid.items())]
        R2["notes"] = R["notes"] + ("; Q336: +1 structure (skin_vulva_cvh, the CVH vulvar / perineal skin registered onto the "
                                    "opening, appended so no index moved), rigid in the pelvis segment as the removed Q202 closure "
                                    "was; weights blob unchanged")
        change = "appended, rigid in the pelvis segment"
    out = dict(src); out["rig"] = R2
    if write:
        rig_path.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    return {"rig": str(rig_path), "count_before": R["count"], "count_after": R2["count"],
            "change": change, "written": bool(write)}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--page-dir", required=True)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--report", default=str(REPORT))
    ap.add_argument("--rig-file", default=str(RIG),
                    help="the pose rig to splice (default data/anatomy/pose_rig_base_f.json -- use the default ONLY when applying to "
                         "the build page the shared rig describes; for a private copy pass a copy of the rig)")
    ap.add_argument("--no-rig", action="store_true", help="do not touch any pose rig")
    a = ap.parse_args(argv)
    d = Path(a.page_dir)
    assert pages_of(d), f"{d}: no {STEM}.html (this script is for Base · Female only)"
    t0 = time.time()
    man, blob, files = read_page(d)
    drop = set()
    if any(m["id"] == NEW_ID for m in man["meshes"]):
        assert man["meshes"][-1]["id"] == NEW_ID, "existing skin_vulva_cvh is not the last mesh"
        drop = {NEW_ID}
    man_base = dict(man); man_base["meshes"] = [m for m in man["meshes"] if m["id"] not in drop]
    print(f"Q336 vulva skin on {d}")
    Vs, Fs, rep = build(man_base, blob)
    entry = new_entry(rep)
    recs = neighbour_recs(man)
    recs.update(cvh_recs(man, recs))
    man_new, blob_new = repack(man, blob, recs, [(entry, Vs, Fs)], drop)
    rep.update({"page_dir": str(d), "new_id": NEW_ID, "neighbour_cards_updated": sorted(recs),
                "meshes_before": len(man["meshes"]), "meshes_after": len(man_new["meshes"]), "seconds": round(time.time() - t0, 1)})
    if a.write:
        rep["files_written"] = write_page(d, man, man_new, blob_new, files)
        if not a.no_rig:
            rep["rig"] = splice_rig(man, man_new, True, Path(a.rig_file).resolve())
    else:
        rep["files_written"] = []
        rep["rig"] = "dry run"
    Path(a.report).write_text(json.dumps(rep, indent=1), encoding="utf-8")
    print(json.dumps({k: rep[k] for k in ("see_through", "slab", "shift_vs_bone_only_mm")}, indent=None))
    print(f"Q336_VULVA_SKIN_{'WRITTEN' if a.write else 'DRY'} {d}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
