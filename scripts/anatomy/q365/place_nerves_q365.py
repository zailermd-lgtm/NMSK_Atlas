#!/usr/bin/env python3
"""Q365: head nerves missing on the Base pages -- placed from the existing rules and the source geometry.

    python3 scripts/anatomy/q365/place_nerves_q365.py --page-dir DIR                 # dry run: build, guard, report
    python3 scripts/anatomy/q365/place_nerves_q365.py --page-dir DIR --write         # and write the page files in DIR
        [--rig-file data/anatomy/pose_rig_<key>.json] [--rig-out PATH] [--calibre] [--scan-held] [--allow-build]

Owner (2026-11-17): "head nerves are missing". Q363 found that none were lost; these were never on the Base pages:

 1. INFRA-ORBITAL NERVE -- not a rule tube. The Z-Anatomy "Maxillary nerve" object of both bodies already runs on through the
    infra-orbital groove and canal to the face (2/3 of its vertices lie anterior to the orbital floor, within 1-2 mm of the
    real infra-orbital artery; Q357 already allows it in the maxilla). Q261's rule held it because the trunk point nearest
    the artery is ON the artery (< 2 mm, "no real length for a separate branch") -- the branch is the trunk's own end.
    So the infra-orbital nerve is SPLIT OFF that real geometry: the maxillary nerve's centreline is followed from its
    proximal end; the infra-orbital nerve begins where the centreline enters the infra-orbital groove of the maxilla (first
    centreline point within GROOVE_MM of the maxilla surface after which it stays near the bone or the infra-orbital artery
    to its end) -- Sontakke vol. 5 p. 255 (groove and canal from the inferior orbital fissure to the foramen), p. 337
    (runs forward in the floor of the orbit in the groove then the canal, appears on the face through the foramen);
    Mannan p. 23 (continuation of the maxillary nerve; appears on the face under cover of levator labii superioris).
    Faces are cut by the plane normal to the centreline there, both open ends capped (fan), vertex positions untouched.
    The maxillary nerve keeps its id and its proximal geometry. Badge: Z-Anatomy geometry split by a stated rule.
 2. Q261 rule branches (scripts/anatomy/q261/rule_cranial.py, run as is on the page): any of WANT_RC that the page lacks
    and that the rule now ships (Base·F facial temporal branches: held in Q261 by a 30-46 mm bone push-out -- the
    pre-Q353 frontalis lay where the straight path from the facial trunk crossed the skull; after Q353 tucked frontalis
    under the skin the same rule passes with 1-2 mm. Base·F facial cervical branch R: Q353 moved platysma, the branch
    now has 2.4 mm).
 3. Occipital nerves (data/nerves/dorsal_rami.json records, never built): the greater occipital (C2 dorsal ramus, medial
    branch), third occipital (C3, medial branch) and suboccipital (C1 dorsal ramus) nerves, by a NEW rule in this file
    with the Q259 tube builder (scripts/anatomy/q259/rulenerve.py Builder.mk: same badge, push-out, caps, checks), on
    waypoints measured on each body's own atlas / axis / C3, obliquus capitis inferior, rectus capitis posterior major,
    occipital bone, trapezius, occipital artery and occipital-region skin. Courses: Mannan p. 14, 88-90; Sontakke vol. 5
    p. 215-216, 225-227 (see OCC_* below; knowledge only, no prose copied).
 Not placed (reported with the rule's own reason, --scan-held): XI branch to SCM R, XII lingual branches L (Base·M), the
 femoral / tibial muscular branches, anococcygeal and dorsal nerve of the clitoris -- see the JSON report.

Q365 guards per new structure (a structure failing any is not written; the others are): no vertex > 1 mm inside a bone
other than an allowed passage (data/anatomy/q357_in_bone_allow.json); no vertex outside the skin (the Q357 voxel skin
body); length within LR_MAX of the same nerve on the other side (placed now or already on the page); its end within
REACH_MM of its target structure; no kink (turning angle of the centreline > KINK_DEG); closed mesh.
Write: new meshes go BEFORE the trailing block of the page (Base·F: skin_vulva_cvh, skin_perineum_rule_q358 stay last),
every other mesh keeps its order; originals copied beside each changed file as `<name>.q365` (never overwritten); the
pose rig is spliced (new meshes rigid in the segment of their nearest bone, the maxillary nerve stays rigid in its own;
indices after the insertion point shifted; weights blob unchanged) and written to --rig-out. A page that already carries
the Q365 structures is refused.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import re
import shutil
import sys
import time
from pathlib import Path

import numpy as np
import trimesh
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
for p in ("", "scripts", "scripts/zanatomy", "scripts/anatomy/q340", "scripts/anatomy/q248", "scripts/anatomy/q249",
          "scripts/anatomy/q259", "scripts/anatomy/q261", "scripts/anatomy/q357", "scripts/anatomy/q240", "scripts/anatomy/q349"):
    sys.path.insert(0, str(REPO / p))
import build_zan_atlas_viewer as BZ   # noqa: E402  pack_mesh / split_blob
import conform_palm_q340 as C340      # noqa: E402  page I/O
import nervelib as NL                 # noqa: E402  spline / path_len
import lm as LM249                    # noqa: E402  centerline
import lmk                            # noqa: E402  q259 page / landmark wrapper
import rule_cranial as RC             # noqa: E402  the Q261 cranial-branch rule
from rulenerve import Builder         # noqa: E402  the Q259 rule-based tube builder

TAG = "Q365"
SUFFIX = ".q365"
REPORT = REPO / "data/derived/Q365_nerves_report.json"
DIRKEY = {"viewer_zan_atlas": "base_m", "viewer_base_female": "base_f"}
STEM = {"base_m": "atlas_viewer_zan_atlas", "base_f": "atlas_viewer_base_female"}
TRAIL = ("skin_vulva_cvh", "skin_perineum_rule_q358")
WANT_RC = tuple(f"{n}_{s}" for n in ("facial_n_temporal_branch", "facial_n_cervical_branch", "accessory_n_scm_branch") for s in "lr")
GROOVE_MM = 3.0      # mm: centreline this close to the maxilla = in the infra-orbital groove
ACCOMP_MM = 6.0      # mm: from there to its end the nerve stays this close to the maxilla or the infra-orbital artery
LR_MAX = 1.6         # length ratio to the other side
REACH_MM = 2.0       # mm: end to target surface (rule tubes); split nerve: to levator labii superioris / infra-orbital skin
REACH_SPLIT_MM = 8.0
KINK_DEG = 75.0      # degrees between successive centreline segments
BONE_MM = 1.0
SUBCUT_MM = 1.8     # mm: a cutaneous nerve's subcutaneous waypoints / end lie this far under the outer skin surface (Z skin slabs are 3 mm)

M17 = "Noor MA. Mannan's Regional Dissection and Surface Anatomy, 14th ed., Jaypee, New Delhi 2017"
Y23 = "Sontakke YA. Textbook of Human Anatomy, Vol. 5 Head, Neck and Face, 1st e-book ed., CBS Publishers, New Delhi 2023"
SRC_IO = f"{Y23}, printed pp. 255, 337, 401; {M17}, p. 23"
SRC_OCC = f"{M17}, pp. 14, 88-90; {Y23}, printed pp. 215-216, 225-227"
OCC_ERR = 10.0
OCC_ERR_TEXT = ("landmark-rule allowance for a dorsal-ramus branch of the suboccipital region (waypoints on this page's own bones and "
                "muscles; no page-specific dissection): +-10 mm")


# ------------------------------------------------------------------ page I/O
def read(d: Path, stem):
    return C340.read_page(d, stem)


def dec(m, blob):
    return C340.dec(m, blob)


def repack(man, blob, replace, insert, before):
    """replace = {id: (v, f, rec|None)}; insert = [(entry, v, f)] placed before the first id of `before` present (else at the end)."""
    old = man["meshes"]
    ids = [m["id"] for m in old]
    cut = next((ids.index(t) for t in before if t in ids), len(ids))
    order = [("old", m) for m in old[:cut]] + [("new", e) for e in insert] + [("old", m) for m in old[cut:]]
    meshes, chunks, off = [], [], 0
    for kind, x in order:
        if kind == "new":
            entry, v, f = x
            fields, packed = BZ.pack_mesh(np.asarray(v, float), np.asarray(f), off)
            n = dict(entry); n.update(fields)
            chunks.append(packed); off += len(packed)
        else:
            m = x
            n = dict(m)
            if m["id"] in replace:
                v, f, rec = replace[m["id"]]
                fields, packed = BZ.pack_mesh(np.asarray(v, float), np.asarray(f), off)
                n.update(fields)
                if rec is not None:
                    n["rec"] = rec
                chunks.append(packed); off += len(packed)
            else:
                pos = blob[m["vo"]: m["vo"] + m["vc"] * 6]; idx = blob[m["io"]: m["io"] + m["ic"] * 6]
                n["vo"], n["io"] = off, off + len(pos)
                chunks += [pos, idx]; off += len(pos) + len(idx)
        meshes.append(n)
    man2 = dict(man); man2["meshes"] = meshes
    t = json.loads(json.dumps(man.get("totals") or {}))
    if t:
        t["meshes"] = len(meshes)
        bl = t.setdefault("by_layer", {})
        for entry, _, _ in insert:
            bl[entry["sys"]] = bl.get(entry["sys"], 0) + 1
        man2["totals"] = t
    return man2, b"".join(chunks), cut


def write_page(d: Path, stem, man_old, man_new, blob_new, old_files):
    pages = C340.pages_of(d, stem)
    texts = {p: p.read_text(encoding="utf-8") for p in pages}
    for p, t in texts.items():
        assert C340.LIT["manifest"].search(t).group(1) == C340.ser_manifest(man_old), f"{p}: manifest serialisation differs"
        assert C340.LIT["files"].search(t).group(1) == json.dumps(old_files), f"{p}: file list serialisation differs"
    chunks = BZ.split_blob(blob_new, stem)
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


# ------------------------------------------------------------------ geometry helpers
def cap_loops(v, f):
    """close every boundary loop with a fan about its centroid, winding consistent with the mesh."""
    e = np.vstack([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
    key = {}
    for a, b in e:
        key[(a, b)] = key.get((a, b), 0) + 1
    bnd = [(a, b) for (a, b) in key if (b, a) not in key]
    nxt = {}
    for a, b in bnd:
        nxt[b] = a                      # reversed direction: the cap runs opposite to the faces' own edge
    V = [*v]; F = [*map(tuple, f)]
    seen = set(); loops = 0
    for start in list(nxt):
        if start in seen:
            continue
        loop = [start]; seen.add(start); cur = nxt[start]
        while cur != start and cur not in seen and cur in nxt:
            loop.append(cur); seen.add(cur); cur = nxt[cur]
        if len(loop) < 3:
            continue
        c = np.mean([v[i] for i in loop], 0)
        ci = len(V); V.append(c)
        for i in range(len(loop)):
            F.append((loop[i], loop[(i + 1) % len(loop)], ci))
        loops += 1
    return np.asarray(V, float), np.asarray(F, np.int64), loops


def submesh(v, f, keep_faces):
    ff = f[keep_faces]
    used = np.unique(ff)
    remap = -np.ones(len(v), np.int64); remap[used] = np.arange(len(used))
    return v[used], remap[ff]


def geodesic(v, f, a, b):
    import scipy.sparse as sp
    from scipy.sparse.csgraph import dijkstra
    e = np.unique(np.sort(np.vstack([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]), axis=1), axis=0)
    w = np.linalg.norm(v[e[:, 0]] - v[e[:, 1]], axis=1)
    G = sp.coo_matrix((np.r_[w, w], (np.r_[e[:, 0], e[:, 1]], np.r_[e[:, 1], e[:, 0]])), shape=(len(v), len(v))).tocsr()
    _, pred = dijkstra(G, indices=a, directed=False, return_predecessors=True)
    seq = [b]
    while seq[-1] != a and pred[seq[-1]] >= 0:
        seq.append(pred[seq[-1]])
    return v[seq[::-1]]


def path_of(v, f, n=40):
    return LM249.centerline(v, f, n)


def kink_deg(P):
    P = np.asarray(P, float)
    if len(P) < 3:
        return 0.0
    a = P[1:-1] - P[:-2]; b = P[2:] - P[1:-1]
    na = np.linalg.norm(a, axis=1); nb = np.linalg.norm(b, axis=1)
    ok = (na > 1e-6) & (nb > 1e-6)
    if not ok.any():
        return 0.0
    c = np.clip((a[ok] * b[ok]).sum(1) / (na[ok] * nb[ok]), -1, 1)
    return float(np.degrees(np.arccos(c)).max())


# ------------------------------------------------------------------ 1. infra-orbital nerve split off the real maxillary nerve
def infraorbital(E, s):
    sw = "left" if s == "l" else "right"
    tid, aid, bid = f"zan_maxillary_nerve_{s}", f"zan_infra_orbital_artery_{s}", f"maxilla_{s}"
    nid = f"trigeminal_n_v2_infraorbital_branch_{s}"
    for k in (tid, aid, bid):
        if k not in E:
            return dict(id=nid, side=s, status="held", held=[f"no {k} on this page"])
    v, f = E[tid]["v"], E[tid]["f"]
    C = path_of(v, f, 60)
    if C[0][2] > C[-1][2]:                    # proximal end first (posterior, toward the foramen rotundum)
        C = C[::-1]
    mx = trimesh.Trimesh(E[bid]["v"], E[bid]["f"], process=False)
    dm = np.abs(trimesh.proximity.signed_distance(mx, C)) if len(C) else np.zeros(0)
    da = cKDTree(E[aid]["v"]).query(C)[0]
    near = np.minimum(dm, da)
    j0 = None
    for j in range(1, len(C) - 2):
        if dm[j] <= GROOVE_MM and (near[j:] <= ACCOMP_MM).all():
            j0 = j; break
    if j0 is None:
        return dict(id=nid, side=s, status="held", held=["the maxillary nerve's centreline never enters the infra-orbital groove "
                                                            f"(within {GROOVE_MM:g} mm of the maxilla and staying with the bone / artery)"])
    p = C[j0]; t = C[j0 + 1] - C[j0 - 1]; t /= np.linalg.norm(t)
    cen = v[f].mean(1)
    dist = (cen - p) @ t > 0
    # what is the infra-orbital nerve: the piece of the main source tube beyond the cut that continues the canal course, plus the
    # source's own separate small tubes on the face in front of the foramen (its palpebral / nasal / labial branches). A piece of the
    # main tube beyond the plane that is NOT connected to the canal course (a branch given off proximal to the cut) stays with V2.
    import scipy.sparse as sp
    from scipy.sparse.csgraph import connected_components

    def comps(ff_):
        ee = np.vstack([ff_[:, [0, 1]], ff_[:, [1, 2]]])
        G = sp.coo_matrix((np.ones(len(ee)), (ee[:, 0], ee[:, 1])), shape=(len(v), len(v)))
        return connected_components(G, directed=False)[1]
    lab0 = comps(f)
    main = np.argmax(np.bincount(lab0[f[:, 0]]))
    fi = np.where(dist)[0]
    on_main = lab0[f[fi, 0]] == main
    keep = np.zeros(len(f), bool)
    keep[fi[~on_main]] = True
    fm = fi[on_main]
    rep_pieces = 0
    if len(fm):
        lab1 = comps(f[fm])
        pcs = np.unique(lab1[f[fm, 0]]); rep_pieces = int(len(pcs))
        anchor = C[min(j0 + 2, len(C) - 1)]
        best = min(pcs, key=lambda c: np.linalg.norm(v[np.unique(f[fm][lab1[f[fm, 0]] == c])] - anchor, axis=1).min())
        keep[fm[lab1[f[fm, 0]] == best]] = True
    face_pieces = int(len(np.unique(lab0[f[fi[~on_main], 0]]))) if (~on_main).any() else 0
    dist = keep
    vd, fd = submesh(v, f, dist); vp, fp = submesh(v, f, ~dist)
    Vd, Fd, ld = cap_loops(vd, fd); Vp, Fp, lp = cap_loops(vp, fp)
    md, mp = trimesh.Trimesh(Vd, Fd, process=False), trimesh.Trimesh(Vp, Fp, process=False)
    # its course to the face: the geodesic on the distal mesh from the cut to its most anterior vertex (the foramen end; the source
    # object also carries the alveolar twigs given off in the canal, which the source centreline would otherwise follow)
    lab_d = None
    st = int(np.argmin(np.linalg.norm(vd - p, axis=1)))
    import scipy.sparse as sp2
    from scipy.sparse.csgraph import connected_components as cc2
    ee = np.vstack([fd[:, [0, 1]], fd[:, [1, 2]]])
    lab_d = cc2(sp2.coo_matrix((np.ones(len(ee)), (ee[:, 0], ee[:, 1])), shape=(len(vd), len(vd))), directed=False)[1]
    same = np.where(lab_d == lab_d[st])[0]
    fora = int(same[np.argmax(vd[same, 2])])                          # the canal course's own most anterior vertex: the foramen
    Pth = geodesic(vd, fd, st, fora)
    face_end = vd[int(np.argmax(vd[:, 2]))]
    Ld = float(NL.path_len(Pth)); Lp = float(NL.path_len(C[:j0 + 1]))
    rep = dict(split_point=np.round(p, 1).tolist(), split_index=j0, centreline_points=len(C), main_tube_pieces_beyond_plane=rep_pieces, face_branch_tubes=face_pieces,
               maxilla_distance_at_split_mm=round(float(dm[j0]), 2), artery_distance_at_split_mm=round(float(da[j0]), 2),
               infraorbital=dict(vertices=int(len(Vd)), triangles=int(len(Fd)), caps=ld, watertight=bool(md.is_watertight),
                                 winding_consistent=bool(md.is_winding_consistent), length_mm=round(Ld, 1),
                                 volume_mm3=round(float(abs(md.volume)), 1)),
               maxillary_rest=dict(vertices=int(len(Vp)), triangles=int(len(Fp)), caps=lp, watertight=bool(mp.is_watertight),
                                   winding_consistent=bool(mp.is_winding_consistent), length_mm=round(Lp, 1)),
               source_vertices=int(len(v)), source_triangles=int(len(f)))
    course = (f"The maxillary nerve's continuation through the floor of the orbit: it runs forward in the infra-orbital groove, then the "
              f"infra-orbital canal of the maxilla, and appears on the face at the infra-orbital foramen under cover of levator labii "
              f"superioris, where it divides into palpebral, nasal and superior labial branches (Sontakke vol. 5 pp. 255, 337; Mannan p. 23). "
              f"It travels in the groove and canal with the infra-orbital artery (Sontakke vol. 5 p. 131).")
    badge = (f"Q365: Z-ANATOMY GEOMETRY, NOT RULE-BASED -- the distal {Ld:.0f} mm of the source's own 'Maxillary nerve' object, which already runs "
             f"through the infra-orbital groove and canal to the foramen, together with the source's {face_pieces} small separate tubes on the "
             f"face in front of the foramen (its terminal palpebral / nasal / labial branches, not named separately). Only its BEGINNING is set "
             f"by a stated rule: the point where the maxillary nerve's centreline enters the groove on the maxilla ({dm[j0]:.1f} mm from the "
             f"bone; from there to its end it stays within {ACCOMP_MM:g} mm of the maxilla or the real infra-orbital artery). The source mesh "
             f"was cut there by the plane across the nerve and both cut ends capped; no vertex moved. {len(Vd)} vertices, closed meshes.")
    rec = {"name": f"Infra-orbital nerve ({sw})", "latin": f"Nervus infraorbitalis {'sinister' if s == 'l' else 'dexter'}",
           "folder": "nerves", "region": "head", "source": SRC_IO + "; geometry: Z-Anatomy (CC BY-SA 4.0), split from its 'Maxillary nerve' object",
           "notes": course, "procedural_badge": badge,
           "geom_src": "Z-Anatomy geometry (part of the source's 'Maxillary nerve' object), split off by the Q365 rule above"}
    entry = {"name": rec["name"], "id": nid, "side": s, "sys": "nerve", "rec": rec}
    return dict(id=nid, side=s, status="ship", held=[], kind="split", V=Vd, F=Fd, entry=entry, trunk=tid,
                trunk_geo=(Vp, Fp), report=rep, length_mm=Ld, path=np.vstack([Pth, face_end[None]]), target=[f"levator_labii_superioris_{s}", f"zan_skin_infra_orbital_region_{s}"])


# ------------------------------------------------------------------ 2b. facial temporal branch: the Q261 rule with its documented course
def temporal_branch(S, B, s):
    """Q261's rule (origin = the facial trunk's centreline point nearest frontalis, end = frontalis' own surface) with the two
    waypoints its straight spline leaves out: it emerges at the UPPER border of the parotid gland and crosses the ZYGOMATIC ARCH,
    in the soft tissue between the arch and the skin (Mannan p. 13; Sontakke vol. 5 p. 141: lateral to the TMJ under skin and
    fascia). On Base·F the straight spline crossed the arch outside the skin; nothing else of the rule changes."""
    E = S.E; sw = "left" if s == "l" else "right"; lat = "sinister" if s == "l" else "dexter"
    nid = f"facial_n_temporal_branch_{s}"
    tr, fr, par, zy = f"zan_facial_nerve_vii_{s}", f"frontalis_{s}", f"zan_parotid_gland_{s}", f"zygomatic_{s}"
    miss = [k for k in (tr, fr, par, zy) if k not in E]
    if miss:
        B.hold(nid, f"Facial n., temporal branch ({sw})", f"meshes missing on this page: {miss}", side=s); return None
    C = S.centerline(tr, n=40)
    cen = E[fr]["v"].mean(0)
    # the branch leaves the trunk in the parotid, i.e. AFTER the stylomastoid foramen: only trunk points outside the temporal bone count
    import conform_fingers_q349 as C349
    tb = f"temporal_{s}"
    if tb in E:
        if abs(C[0][0] - S.xm) > abs(C[-1][0] - S.xm):
            C = C[::-1]                                                  # medial (brainstem) end first
        w = np.abs(C349.winding(C, E[tb]["v"], E[tb]["f"]))
        ins = np.where(w >= 0.5)[0]
        if len(ins) and ins[-1] + 1 < len(C):
            C = C[ins[-1] + 1:]                                         # the extracranial run, after its last point in the bone
    origin = C[int(np.argmin(np.linalg.norm(C - cen, axis=1)))]
    pv = E[par]["v"]
    top = pv[pv[:, 1] >= np.percentile(pv[:, 1], 95)]
    w1 = top[np.argmin(np.linalg.norm(top - origin, axis=1))]           # upper border of the parotid gland, nearest the trunk
    end, _ = B.soft.surface_point(fr, w1, margin=0.35, maxdist=140.0)
    if end is None:
        B.hold(nid, f"Facial n., temporal branch ({sw})", "frontalis farther than 140 mm from the parotid's upper border", side=s); return None
    zv = E[zy]["v"]; xm = S.xm; sg = -1.0 if s == "l" else 1.0
    arch = zv[zv[:, 2] <= np.percentile(zv[:, 2], 35)]                 # the zygomatic bone's posterior (temporal) process
    arch = arch[np.argsort(-sg * (arch[:, 0] - xm))[: max(5, len(arch) // 10)]]
    ap = arch[np.argmin(np.abs(arch[:, 1] - 0.5 * (w1[1] + end[1])))]
    skins = [k for k in E if E[k]["sys"] == "skin"]
    sk_v = np.vstack([E[k]["v"] for k in skins if np.linalg.norm(E[k]["v"].mean(0) - ap) < 120])
    from scipy.spatial import cKDTree as KD
    ds, k = KD(sk_v).query(ap)
    w2 = ap + (sk_v[k] - ap) * 0.5                                      # half way between the arch and the skin
    face_bones = tuple(b for b in (f"temporal_{s}", zy, "mandible", "zan_mandible") if b in E)
    m1 = subcut_mid(E, w1, w2, bones=face_bones)                        # parotid border -> arch: in the subcutaneous plane
    e = B.mk(nid, f"Facial n., temporal branch ({sw})", f"Ramus temporalis nervi facialis {lat}", s, [origin, w1, m1, w2, end], 1.0,
             region="head",
             course=(f"Q365 rule (extends Q261's): branch of {tr}; leaves at the point of its own real centreline closest to {fr}, emerges at "
                     f"the upper border of the parotid gland (it leaves the trunk outside the temporal bone, after the stylomastoid foramen), passes upward and forward across the zygomatic arch to the side of the head and "
                     f"the forehead (Mannan p. 13; Sontakke vol. 5 p. 141) and ends on frontalis' own surface. Waypoints on this page: the trunk "
                     f"point; the parotid gland's upper border nearest it; a point in the subcutaneous plane on the way to the arch; half way between the zygomatic arch and the skin ({ds:.1f} mm apart "
                     f"there); frontalis."),
             calibre=RC.CAL, calibre_kind="assumption", source=RC.SOURCE + f" Course: {M17}, p. 13; {Y23}, p. 141.", err_mm=RC.ERR,
             err_text=RC.ERR_TEXT, len_range=(30.0, 165.0))
    e["q365_target"] = fr
    return e


# ------------------------------------------------------------------ 3. occipital nerves (new rule, Q259 builder)
def _surface_band(v, x, y, win=6.0):
    m = (np.abs(v[:, 0] - x) <= win) & (np.abs(v[:, 1] - y) <= win)
    return v[m]


def under_skin(B, E, skin, near, bone, maxdist=40.0):
    """a point in the subcutaneous plane: the skin surface point nearest `near`, moved toward the nearest surface of `bone` by half the
    skin-bone gap (at most SUBCUT_MM + 1.2 mm) -- independent of which face of the skin slab is nearest."""
    q, _ = B.soft.surface_point(skin, near, margin=0.0, maxdist=maxdist)
    if q is None:
        return None
    bv = E[bone]["v"]
    b = bv[int(np.argmin(np.linalg.norm(bv - q, axis=1)))]
    gap = float(np.linalg.norm(b - q))
    if gap < 1e-6:
        return q
    return q + (b - q) / gap * min(0.5 * gap, SUBCUT_MM + 1.2)


def subcut_mid(E, a, b, bones=("occipital", "zan_atlas_c1", "zan_axis_c2", "zan_vertebra_c3"), frac=0.5):
    """the subcutaneous point between waypoints a and b: the skin vertex nearest their midpoint (any skin region), moved toward the
    nearest of `bones` by half the gap (at most SUBCUT_MM + 1.2 mm) -- keeps a nerve that runs under the skin of the concave nape
    inside it instead of bridging the hollow."""
    m = (1.0 - frac) * np.asarray(a, float) + frac * np.asarray(b, float)
    best = None
    for k, e in E.items():
        if e["sys"] != "skin":
            continue
        v = e["v"]
        if (v.min(0) - 30 > m).any() or (v.max(0) + 30 < m).any():
            continue
        i = int(np.argmin(np.linalg.norm(v - m, axis=1)))
        d = float(np.linalg.norm(v[i] - m))
        if best is None or d < best[0]:
            best = (d, v[i])
    if best is None:
        return m
    q = best[1]
    bb = min((E[x]["v"][int(np.argmin(np.linalg.norm(E[x]["v"] - q, axis=1)))] for x in bones if x in E),
             key=lambda p_: float(np.linalg.norm(p_ - q)))
    gap = float(np.linalg.norm(bb - q))
    return q + (bb - q) / max(gap, 1e-6) * min(0.5 * gap, SUBCUT_MM + 1.2)


def occipital(S, B, s):
    E = S.E; xm = S.xm; sg = -1.0 if s == "l" else 1.0
    sw = "left" if s == "l" else "right"; lat = "sinister" if s == "l" else "dexter"
    need = ["occipital", "zan_atlas_c1", "zan_axis_c2", "zan_vertebra_c3", f"obliquus_capitis_inferior_{s}", f"obliquus_capitis_superior_{s}",
            f"rectus_capitis_posterior_major_{s}", f"trapezius_{s}", f"zan_skin_occipital_region_{s}", f"zan_occipital_artery_{s}",
            f"zan_vertebral_artery_{s}"]
    miss = [k for k in need if k not in E]
    out = []
    if miss:
        for nid, nm in ((f"greater_occipital_n_{s}", "Greater occipital nerve"), (f"third_occipital_n_{s}", "Third occipital nerve"),
                        (f"suboccipital_n_{s}", "Suboccipital nerve")):
            B.hold(nid, f"{nm} ({sw})", f"landmark meshes missing on this page: {miss}", side=s)
        return out
    occ = E["occipital"]["v"]
    mid = occ[np.abs(occ[:, 0] - xm) < 5.0]
    eop = mid[np.argmin(mid[:, 2])]                                   # external occipital protuberance: most posterior midline point
    oci = E[f"obliquus_capitis_inferior_{s}"]["v"]
    rel = sg * (oci[:, 0] - xm)
    lo_, hi_ = np.percentile(rel, 5), np.percentile(rel, 95)
    band = oci[(rel > lo_ + 0.4 * (hi_ - lo_)) & (rel < lo_ + 0.6 * (hi_ - lo_))]
    low = band[np.argmin(band[:, 1])]                                  # lower border of obliquus capitis inferior, mid-length
    bandm = oci[(rel > lo_ + 0.2 * (hi_ - lo_)) & (rel < lo_ + 0.45 * (hi_ - lo_))]
    post = bandm[np.argmin(bandm[:, 2])]                              # its posterior surface, medial part
    rcp = E[f"rectus_capitis_posterior_major_{s}"]["v"]
    ym = np.median(rcp[:, 1]); rb = rcp[np.abs(rcp[:, 1] - ym) < 4.0]
    rcp_post = rb[np.argmin(rb[:, 2])]
    trap = E[f"trapezius_{s}"]["v"]
    x25 = xm + sg * 25.0                                               # ~1 inch lateral to the protuberance (Mannan p. 14)
    ytop = float(trap[:, 1].max())                                     # this atlas' trapezius stops below the superior nuchal line:
    yp = min(eop[1] - 5.0, ytop - 3.0)                                 # it is pierced at its own upper part, 25 mm from the midline
    tb = trap[(np.abs(trap[:, 0] - x25) <= 6.0) & (np.abs(trap[:, 1] - yp) <= 6.0)]
    pierce = tb[np.argmin(tb[:, 2])] + np.array([0.0, 0.0, -1.5]) if len(tb) else None
    oa = E[f"zan_occipital_artery_{s}"]["v"]
    oab = oa[(np.abs(oa[:, 1] - (eop[1] + 10.0)) < 6.0) & (sg * (oa[:, 0] - xm) > 5.0)]
    skin = f"zan_skin_occipital_region_{s}"
    # ---- greater occipital: below obliquus capitis inferior, round its lower border, up and medially across the suboccipital
    # triangle, pierces semispinalis capitis and trapezius ~2.5 cm from the midline near the superior nuchal line, then up the
    # back of the scalp with the occipital artery toward the vertex (Mannan pp. 14, 88-89; Sontakke vol. 5 pp. 215, 227)
    if pierce is None or not len(oab):
        B.hold(f"greater_occipital_n_{s}", f"Greater occipital nerve ({sw})", "no trapezius surface 25 mm lateral at the protuberance's level, "
               "or no occipital artery 30 mm above it, on this page", side=s)
    else:
        a1 = low + np.array([0.0, -3.0, 0.0])
        a2 = post + np.array([0.0, 0.0, -3.0])
        a3 = rcp_post + np.array([0.0, 0.0, -4.0])
        snl = under_skin(B, E, skin, np.array([x25, eop[1], eop[2]]), "occipital")
        oam = oab[np.argmin(sg * (oab[:, 0] - xm))]                    # the occipital artery's most medial point 10 mm above the protuberance
        end = under_skin(B, E, skin, oam + np.array([-sg * 3.0, 0.0, 0.0]), "occipital")
        if end is None or snl is None:
            B.hold(f"greater_occipital_n_{s}", f"Greater occipital nerve ({sw})", "occipital-region skin farther than 40 mm from the protuberance's level / the occipital artery", side=s)
        else:
            e = B.mk(f"greater_occipital_n_{s}", f"Greater occipital nerve ({sw})", f"Nervus occipitalis major {lat}", s,
                     [a1, a2, a3, pierce, subcut_mid(E, pierce, snl, frac=1 / 3), subcut_mid(E, pierce, snl, frac=2 / 3), snl, end], 1.5, region="neck",
                     course=("Q365 rule. Medial branch of the dorsal ramus of C2: appears below obliquus capitis inferior, winds round its lower "
                             "border, runs upward and medially across the suboccipital triangle, pierces semispinalis capitis and trapezius about "
                             "2.5 cm lateral to the external occipital protuberance and ascends on the back of the scalp with the occipital artery "
                             "(Mannan pp. 14, 88-89; Sontakke vol. 5 pp. 215, 227). Waypoints on this page: 3 mm below the lower border of "
                             "obliquus capitis inferior at mid-length; 3 mm behind its medial part; 4 mm behind rectus capitis posterior major at "
                             "mid-height (this atlas ships no semispinalis capitis mesh); the posterior surface of trapezius 25 mm from the midline "
                             "at its own upper part (this atlas' trapezius stops below the superior nuchal line); two points in the subcutaneous plane of "
                             "the nape on the way up; under the occipital-region skin 25 mm from the midline at the protuberance's level; under the "
                             "skin just medial to the occipital artery 10 mm higher."),
                     calibre="no diameter in the owner's books; 1.5 mm = ASSUMPTION (described as the larger medial branch of the C2 dorsal ramus)",
                     calibre_kind="assumption", source=SRC_OCC, err_mm=OCC_ERR, err_text=OCC_ERR_TEXT, len_range=(50.0, 200.0))
            e["q365_target"] = skin
            out.append(e)
    # ---- third occipital: medial branch of the C3 dorsal ramus; pierces semispinalis capitis and trapezius, ascends medial to the
    # greater occipital to the skin of the lower back of the head up to the superior nuchal line (Mannan p. 14; Sontakke vol. 5 p. 216)
    c3 = E["zan_vertebra_c3"]["v"]
    relc = sg * (c3[:, 0] - xm)
    lam = c3[(relc > 6.0) & (relc < 14.0)]
    if len(lam) < 5:
        B.hold(f"third_occipital_n_{s}", f"Third occipital nerve ({sw})", "no lamina of C3 6-14 mm from the midline on this page", side=s)
    else:
        back = lam[lam[:, 2] <= np.percentile(lam[:, 2], 20)]          # the lamina (posterior fifth of the vertebra at this distance)
        t0 = back[np.argmax(back[:, 1])] + np.array([0.0, 0.0, -3.0])   # its upper edge, where the C3 dorsal ramus turns back
        x12 = xm + sg * 12.0
        tb3 = _surface_band(trap, x12, 0.5 * (t0[1] + eop[1]), 8.0)
        tgt_y = eop[1] - 8.0
        sk_pt = np.array([xm + sg * 14.0, tgt_y, eop[2]])
        end3 = under_skin(B, E, skin, sk_pt, "occipital")
        if not len(tb3) or end3 is None:
            B.hold(f"third_occipital_n_{s}", f"Third occipital nerve ({sw})", "no trapezius surface 12 mm from the midline between C3 and the "
                   "protuberance, or no occipital-region skin within 40 mm, on this page", side=s)
        else:
            t1 = tb3[np.argmin(tb3[:, 2])] + np.array([0.0, 0.0, -1.5])
            e = B.mk(f"third_occipital_n_{s}", f"Third occipital nerve ({sw})", f"Nervus occipitalis tertius {lat}", s,
                     [t0, t1, subcut_mid(E, t1, end3), end3], 1.0, region="neck",
                     course=("Q365 rule. Medial branch of the dorsal ramus of C3: pierces semispinalis capitis and trapezius close to the midline "
                             "and ascends medial to the greater occipital nerve to the skin of the lower back of the head, up to the superior "
                             "nuchal line (Mannan p. 14; Sontakke vol. 5 p. 216). Waypoints on this page: 3 mm behind the upper edge of the C3 "
                             "lamina 6-14 mm from the midline; the posterior surface of trapezius 12 mm from the midline half way up to the "
                             "protuberance; a point in the subcutaneous plane of the nape; under the occipital-region skin 14 mm from the midline, "
                             "8 mm below the protuberance."),
                     calibre="no diameter in the owner's books; 1.0 mm = ASSUMPTION (same as this atlas' lesser occipital nerve)",
                     calibre_kind="assumption", source=SRC_OCC, err_mm=OCC_ERR, err_text=OCC_ERR_TEXT, len_range=(25.0, 170.0))
            e["q365_target"] = skin
            out.append(e)
    # ---- suboccipital: dorsal ramus of C1, emerges between the vertebral artery and the posterior arch of the atlas into the
    # suboccipital triangle and supplies the suboccipital muscles (Mannan p. 90; Sontakke vol. 5 pp. 225, 227)
    atl = E["zan_atlas_c1"]["v"]
    va = E[f"zan_vertebral_artery_{s}"]["v"]
    kd = cKDTree(atl)
    dva = kd.query(va)[0]
    rva = sg * (va[:, 0] - xm)
    cand = va[(dva < 5.0) & (va[:, 2] < np.median(atl[:, 2])) & (rva > 10.0) & (rva < 35.0)]
    if len(cand) < 3:
        B.hold(f"suboccipital_n_{s}", f"Suboccipital nerve ({sw})", "no vertebral artery on the posterior arch of the atlas on this page", side=s)
    else:
        cva = cand.mean(0)
        _, k = kd.query(cva)
        s0 = 0.5 * (cva + atl[k])
        tri = np.mean([E[f"rectus_capitis_posterior_major_{s}"]["v"].mean(0), E[f"obliquus_capitis_superior_{s}"]["v"].mean(0),
                       oci.mean(0)], 0)
        tgt = f"rectus_capitis_posterior_major_{s}"
        end_s, _ = B.soft.surface_point(tgt, tri, margin=0.35, maxdist=40.0)
        if end_s is None:
            B.hold(f"suboccipital_n_{s}", f"Suboccipital nerve ({sw})", "rectus capitis posterior major farther than 40 mm from the suboccipital triangle", side=s)
        else:
            e = B.mk(f"suboccipital_n_{s}", f"Suboccipital nerve ({sw})", f"Nervus suboccipitalis {lat}", s,
                     [s0, 0.5 * (s0 + tri), tri, end_s], 1.0, region="neck",
                     course=("Q365 rule. Dorsal ramus of C1: emerges backward between the vertebral artery and the posterior arch of the atlas "
                             "into the suboccipital triangle and supplies rectus capitis posterior major and minor, obliquus capitis superior "
                             "and inferior and semispinalis capitis (Mannan p. 90; Sontakke vol. 5 pp. 225, 227). Waypoints on this page: midway "
                             "between this page's vertebral artery where it lies on the posterior arch and the arch itself; the centre of the "
                             "triangle formed by rectus capitis posterior major, obliquus capitis superior and inferior; the surface of rectus "
                             "capitis posterior major (its muscular branches to the other muscles are not modelled separately)."),
                     calibre="no diameter in the owner's books; 1.0 mm = ASSUMPTION (comparable small motor ramus)",
                     calibre_kind="assumption", source=SRC_OCC, err_mm=OCC_ERR, err_text=OCC_ERR_TEXT, len_range=(8.0, 70.0))
            e["q365_target"] = tgt
            out.append(e)
    return out


# ------------------------------------------------------------------ guards
class Guarder:
    def __init__(self, d: Path, key, E):
        import conform_in_bone_q357 as Q357
        self.Q = Q357
        self.allow = Q357.Allow()
        M = Q357.load_model(d)
        self.ctx = Q357.Context(M, self.allow)
        self.E = E
        self.bones = [i for i, e in E.items() if e["sys"] == "bone" and len(e["f"]) > 20]
        sp_ = [E[i]["v"] for i in E if re.match(r"zan_(atlas_c1|axis_c2|vertebra_[ctl]\d+)$", i)]
        allv = np.vstack(sp_) if sp_ else np.vstack([E[i]["v"] for i in self.bones])
        self.xm, self.zc = float(np.median(allv[:, 0])), float(np.median(allv[:, 2]))
        self._t = {}

    def tm(self, i):
        if i not in self._t:
            self._t[i] = trimesh.Trimesh(self.E[i]["v"], self.E[i]["f"], process=False)
        return self._t[i]

    def in_bone(self, sid, V):
        lo, hi = V.min(0) - 2, V.max(0) + 2
        bad = {}
        for b in self.bones:
            v = self.E[b]["v"]
            if (v.min(0) > hi).any() or (v.max(0) < lo).any():
                continue
            kind, _ = self.allow.classify(sid, re.sub(r"^zan_", "", b))
            if kind == "allow" and not (sid.startswith("facial_n_") and b.startswith("temporal")):
                continue                     # (the facial canal holds the facial trunk, not its terminal branches)
            w = np.abs(self.Q.C349.winding(V, v, self.E[b]["f"]))
            idx = np.where(w > 0.5)[0]
            if not len(idx):
                continue
            _, dd, _ = trimesh.proximity.closest_point(self.tm(b), V[idx])
            n = int((dd > BONE_MM).sum())
            if n:
                bad[b] = dict(vertices=n, max_mm=round(float(dd.max()), 2))
        return bad

    def outside_skin(self, V):
        """vertices outside the skin: the Q357 voxel body, except in an axial slice whose 2-D fill failed (the skin ring is open there:
        a point on the body's own axis reads 'outside' too) -- there a ray from the axis out through the vertex must still cross the
        skin beyond the vertex (open skin slabs: >= 1 hit beyond it = under the skin)."""
        V = np.asarray(V, float)
        o = self.ctx.outside_skin(V) > 0
        if not o.any():
            return 0
        ax = np.array([self.xm, 0.0, self.zc])
        sk = self.skin_near(V)
        n = 0
        for P in V[o]:
            a = ax.copy(); a[1] = P[1]
            if self.ctx.outside_skin(a[None])[0] == 0:
                n += 1; continue                                   # the slice is filled: the voxel verdict stands
            dvec = P - a; dvec[1] = 0.0; L = np.linalg.norm(dvec)
            if L < 1e-6 or sk is None:
                n += 1; continue
            hits = sk.ray.intersects_location([P], [dvec / L])[0]
            if not len(hits):
                n += 1
        return n

    def skin_near(self, V):
        lo, hi = V.min(0) - 60, V.max(0) + 60
        vs, fs, off = [], [], 0
        for k, e in self.E.items():
            if e["sys"] != "skin":
                continue
            v = e["v"]
            if (v.min(0) > hi).any() or (v.max(0) < lo).any():
                continue
            vs.append(v); fs.append(e["f"] + off); off += len(v)
        if not vs:
            return None
        return trimesh.Trimesh(np.vstack(vs), np.vstack(fs), process=False)

    def reach(self, P_end, targets):
        best = None
        for t in targets:
            if t in self.E:
                d = float(abs(trimesh.proximity.signed_distance(self.tm(t), P_end[None])[0]))
                best = d if best is None else min(best, d)
        return best


def existing_length(E, i):
    if i not in E:
        return None
    C = path_of(E[i]["v"], E[i]["f"], 40)
    if C is None or np.ndim(C) < 2:                 # too short for a centreline (< 10 mm): its extent
        v = E[i]["v"]
        return float(np.linalg.norm(v.max(0) - v.min(0)))
    return float(NL.path_len(C))


def guard_all(G, E, items):
    by = {it["id"]: it for it in items if it["status"] == "ship"}
    for it in by.values():
        V = it["V"]; g = {}
        g["in_bone"] = G.in_bone(it["id"], V)
        g["outside_skin_vertices"] = G.outside_skin(V)
        opp = re.sub(r"_l$", "_r", it["id"]) if it["id"].endswith("_l") else re.sub(r"_r$", "_l", it["id"])
        Lo = by[opp]["length_mm"] if opp in by else existing_length(E, opp)
        g["length_mm"] = round(it["length_mm"], 1); g["other_side_length_mm"] = None if Lo is None else round(Lo, 1)
        g["length_ratio"] = None if not Lo else round(max(it["length_mm"], Lo) / min(it["length_mm"], Lo), 2)
        end = it["path"][-1]
        g["end_to_target_mm"] = G.reach(np.asarray(end, float), it["target"])
        g["kink_deg"] = round(kink_deg(it["path"]), 1)
        mm = trimesh.Trimesh(V, it["F"], process=False)
        g["closed"] = bool(mm.is_watertight)
        reach_lim = REACH_SPLIT_MM if it.get("kind") == "split" else REACH_MM
        fails = []
        if g["in_bone"]:
            fails.append(f"inside a bone (not an allowed passage): {g['in_bone']}")
        if g["outside_skin_vertices"]:
            fails.append(f"{g['outside_skin_vertices']} vertices outside the skin")
        if g["length_ratio"] and g["length_ratio"] > LR_MAX:
            fails.append(f"length {g['length_mm']} mm vs {g['other_side_length_mm']} mm on the other side (ratio > {LR_MAX})")
        if g["end_to_target_mm"] is None or g["end_to_target_mm"] > reach_lim:
            fails.append(f"end {g['end_to_target_mm']} mm from its target (> {reach_lim} mm)")
        if it.get("kind") != "split" and g["kink_deg"] > KINK_DEG:
            fails.append(f"kink {g['kink_deg']} deg (> {KINK_DEG})")
        if not g["closed"]:
            fails.append("mesh not closed")
        g["pass"] = not fails
        it["q365_guards"] = g
        if fails:
            it["status"] = "held"; it["held"] = it.get("held", []) + ["Q365 guard: " + f for f in fails]
    return by


# ------------------------------------------------------------------ rule outputs -> items
def from_rule(e, target=None):
    if e.get("status") != "ship":
        return dict(id=e["id"], side=e.get("side"), status="held", held=e.get("held", []), kind="rule")
    rec = dict(e["rec"])
    rec["notes"] = (rec.get("notes", "") + f" Placed on this page in {TAG} (scripts/anatomy/q365/place_nerves_q365.py).").strip()
    entry = {"name": e["name"], "id": e["id"], "side": e["side"], "sys": "nerve", "rec": rec}
    wp = [np.asarray(w, float) for w in e["report"]["waypoints"]]
    P = NL.spline(wp, max(10, int(len(wp) * 12)))
    if target is None:
        m = re.search(r"closest to (\S+?),", rec.get("notes", ""))
        target = m.group(1) if m else None
    return dict(id=e["id"], side=e["side"], status="ship", held=[], kind="rule", V=np.asarray(e["V"], float), F=np.asarray(e["F"], np.int64),
                entry=entry, report=e["report"], length_mm=float(e["report"]["length_mm"]), path=P, target=[target] if target else [])


# ------------------------------------------------------------------ pose rig splice
def splice_rig(rig_src: Path, man_old, man_new, seg_of_new: dict, rig_out: Path | None):
    src = json.loads(rig_src.read_text(encoding="utf-8"))
    R = src["rig"]
    ids_old = [m["id"] for m in man_old["meshes"]]; ids_new = [m["id"] for m in man_new["meshes"]]
    assert R["count"] == len(ids_old), f"rig count {R['count']} != page {len(ids_old)} (rig and page out of step)"
    assert R["nv"] == [int(m["vc"]) for m in man_old["meshes"]], "the rig's vertex counts differ from the page: rig and page out of step"
    pos = {i: k for k, i in enumerate(ids_new)}
    o2n = [pos[i] for i in ids_old]
    segn = [s_[0] for s_ in R["segs"]]
    rigid = {g[0]: [o2n[i] for i in g[1]] for g in R["rigid"]}
    rigid_of = {i: s_ for s_, l in rigid.items() for i in l}
    nv_new = [int(m["vc"]) for m in man_new["meshes"]]
    for i, (a, b) in enumerate(zip(R["nv"], [nv_new[o2n[k]] for k in range(len(ids_old))])):
        if a != b:
            assert o2n[i] in rigid_of, f"{ids_old[i]} changes vertex count but is not rigid in the rig: weights would shift"
    added = []
    for nid, sname in seg_of_new.items():
        si = segn.index(sname)
        rigid.setdefault(si, []).append(pos[nid]); added.append([nid, sname])
    R2 = dict(R)
    R2["nv"] = nv_new; R2["count"] = len(ids_new)
    R2["rigid"] = [[s_, sorted(v)] for s_, v in sorted(rigid.items())]
    R2["skin"] = [[o2n[e[0]], *e[1:]] for e in R["skin"]]
    R2["notes"] = R["notes"] + (f"; {TAG}: +{len(added)} nerve structures inserted before the trailing block (indices after it shifted), "
                                "each rigid in the segment of its nearest bone; the maxillary nerves split (rigid, vertex counts changed); "
                                "weights blob unchanged")
    out = dict(src); out["rig"] = R2
    if rig_out is not None:
        rig_out.parent.mkdir(parents=True, exist_ok=True)
        rig_out.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    return {"rig_in": rel(rig_src), "rig_out": rel(rig_out) if rig_out else None, "count_before": R["count"], "count_after": R2["count"],
            "added": added}


def nearest_bone_seg(rig_src: Path, man, E, V):
    R = json.loads(rig_src.read_text(encoding="utf-8"))["rig"]
    segn = [s_[0] for s_ in R["segs"]]
    ids = [m["id"] for m in man["meshes"]]
    rig_of = {i: segn[s_] for s_, l in R["rigid"] for i in l}
    c = V.mean(0); best = (1e9, None)
    for k, i in enumerate(ids):
        if k not in rig_of or i not in E or E[i]["sys"] != "bone":
            continue
        d = float(cKDTree(E[i]["v"]).query(c)[0])
        if d < best[0]:
            best = (d, rig_of[k])
    return best[1]


def rel(p) -> str:
    """a path as the report keeps it: repo-relative, else only its last two parts (no scratch paths in committed data)"""
    p = Path(p).resolve()
    try:
        return str(p.relative_to(REPO))
    except ValueError:
        return "/".join(p.parts[-2:])


def jsonable(o):
    if isinstance(o, dict):
        return {k: jsonable(v) for k, v in o.items() if k not in ("V", "F", "path", "entry", "trunk_geo", "d", "rec")}
    if isinstance(o, (list, tuple)):
        return [jsonable(v) for v in o]
    if isinstance(o, np.ndarray):
        return o.tolist()
    if isinstance(o, np.generic):
        return o.item()
    return o


def scan_held(key, root):
    """the other sided branches Q363 listed, through the rules that made the existing side (report only)."""
    os.environ.setdefault("Q249_SRC_" + key, os.environ.get("Q248_SRC_" + key, ""))
    out = {}
    for p in ("q260", "q265"):
        sys.path.insert(0, str(REPO / f"scripts/anatomy/{p}"))
    import rule_limb_fill as LF
    import rule_q265 as R65
    want = ("femoral_n_branch_to_sartorius", "femoral_n_branch_to_iliacus", "femoral_n_branch_to_pectineus", "tibial_n_branch_to_popliteus",
            "hypoglossal_n_lingual_branches", "anococcygeal_n", "dorsal_n_clitoris")
    for e in LF.build(key, root=root)[0] + R65.build_hypoglossal_lingual_z(key, root)[0]:
        if e["id"].rsplit("_", 1)[0] in want:
            out[e["id"]] = dict(status=e["status"], held=e.get("held", []), length_mm=(e.get("report") or {}).get("length_mm"))
    import lm as LMP
    import rule_nerves as RN
    P = LMP.Pel(key)
    Bp = RN.build(P)
    for e in Bp.out:
        if e["id"].rsplit("_", 1)[0] in want:
            out[e["id"]] = dict(status=e["status"], held=e.get("held", []), length_mm=(e.get("report") or {}).get("length_mm"))
    return out


def update_calibre(d: Path, stem, ids):
    import make_calibre as MC
    doc = json.loads(MC.OUT.read_text(encoding="utf-8"))
    tab = MC.table_for(d / f"{stem}.html")
    pg = doc["pages"][d.name]
    n = 0
    for i in ids:
        if i in tab:
            pg["c"][i] = tab[i]; n += 1
    pg["c"] = dict(sorted(pg["c"].items())); pg["count"] = len(pg["c"])
    MC.OUT.write_text(json.dumps(doc, separators=(",", ":")) + "\n", encoding="utf-8")
    return n


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--page-dir", required=True)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--allow-build", action="store_true", help="permit --write into build/q309 (the main thread's apply step)")
    ap.add_argument("--rig-file", default=None, help="pose rig to splice (default data/anatomy/pose_rig_<key>.json)")
    ap.add_argument("--rig-out", default=None, help="where the spliced rig goes (default <page-dir>/../pose_rig_<key>.q365.json)")
    ap.add_argument("--calibre", action="store_true", help="add the new / changed nerves' rows to data/anatomy/calibre.json (this page)")
    ap.add_argument("--scan-held", action="store_true", help="also run the limb / XII / pelvic rules for the report (slow)")
    ap.add_argument("--report", default=str(REPORT))
    a = ap.parse_args(argv)
    d = Path(a.page_dir).resolve()
    key = DIRKEY.get(d.name)
    assert key, f"{d}: a Base page dir is expected ({sorted(DIRKEY)})"
    if "/build/q309/" in str(d) + "/" and a.write and not a.allow_build:
        print("refused: never write into build/q309 without --allow-build (apply on a copy; the main thread applies)")
        return 2
    stem = STEM[key]
    t0 = time.time()
    man, blob, files = read(d, stem)
    ids = [m["id"] for m in man["meshes"]]
    if any(i.startswith("trigeminal_n_v2_infraorbital_branch") or i.startswith("greater_occipital_n") for i in ids):
        print(f"Q365_NERVES_REFUSED {d}: the page already carries the Q365 structures. Re-apply only on the page before Q365: restore every "
              f"'<file>{SUFFIX}' beside its file in {d} and the pose rig, then run again.")
        return 3
    os.environ["Q248_SRC_" + key] = str(d)
    S = lmk.Spine(key, root=str(d.parent))
    E = S.E
    print(f"Q365 nerves on {d} ({key}), {len(ids)} meshes", flush=True)
    items = []
    for s in "lr":
        items.append(infraorbital(E, s))
    rc, _ = RC.build(key, root=str(d.parent))
    for e in rc:
        if e["id"] in WANT_RC and e["id"] not in ids and not e["id"].startswith("facial_n_temporal_branch"):
            items.append(from_rule(e))
    B = Builder(S)
    for s in "lr":
        if f"facial_n_temporal_branch_{s}" not in ids:
            temporal_branch(S, B, s)
        occipital(S, B, s)
    for e in B.out:
        items.append(from_rule(e, target=e.get("q365_target")))
    G = Guarder(d, key, E)
    guard_all(G, E, items)
    rep = {"schema": "nmsk.q365.nerves.v1", "round": TAG, "generated": time.strftime("%Y-%m-%d"), "page_dir": rel(d), "key": key,
           "parameters": dict(groove_mm=GROOVE_MM, accomp_mm=ACCOMP_MM, lr_max=LR_MAX, reach_mm=REACH_MM, reach_split_mm=REACH_SPLIT_MM,
                              kink_deg=KINK_DEG, bone_mm=BONE_MM),
           "structures": {it["id"]: jsonable(it) for it in items}}
    if a.scan_held:
        rep["other_sided_branches"] = scan_held(key, str(d.parent))
    ship = [it for it in items if it["status"] == "ship"]
    for it in items:
        g = it.get("q365_guards") or {}
        print(f"  {it['id']:45s} {it['status']:5s} len={g.get('length_mm')} other={g.get('other_side_length_mm')} end={g.get('end_to_target_mm')} "
              f"kink={g.get('kink_deg')} {'; '.join(it.get('held', []))[:220]}", flush=True)
    replace, insert = {}, []
    for it in ship:
        if it.get("kind") == "split":
            Vp, Fp = it["trunk_geo"]
            replace[it["trunk"]] = (Vp, Fp, None)
        insert.append((it["entry"], it["V"], it["F"]))
    rep["meshes_before"] = len(ids)
    man_new, blob_new, cut = repack(man, blob, replace, insert, TRAIL)
    rep["meshes_after"] = len(man_new["meshes"]); rep["inserted_at"] = cut
    ids_new = [m["id"] for m in man_new["meshes"]]
    present = [t for t in TRAIL if t in ids]
    if present:
        assert ids_new[-len(present):] == present, f"{present} must stay at the end, in this order"
    assert [i for i in ids_new if i in set(ids)] == ids, "existing meshes must keep their order"
    rig_src = Path(a.rig_file).resolve() if a.rig_file else REPO / f"data/anatomy/pose_rig_{key}.json"
    seg = {}
    for it in ship:
        if it.get("kind") == "split":
            R = json.loads(rig_src.read_text(encoding="utf-8"))["rig"]
            segn = [s_[0] for s_ in R["segs"]]; k = ids.index(it["trunk"])
            seg[it["id"]] = next(segn[s_] for s_, l in R["rigid"] if k in l)
        else:
            seg[it["id"]] = nearest_bone_seg(rig_src, man, E, it["V"])
    rig_out = Path(a.rig_out).resolve() if a.rig_out else d.parent / f"pose_rig_{key}{SUFFIX}.json"
    rep["rig"] = splice_rig(rig_src, man, man_new, seg, rig_out if a.write else None)
    if a.write and ship:
        rep["files_written"] = write_page(d, stem, man, man_new, blob_new, files)
        if a.calibre:
            rep["calibre_rows"] = update_calibre(d, stem, [it["id"] for it in ship] + list(replace))
    else:
        rep["files_written"] = []
    rep["seconds"] = round(time.time() - t0, 1)
    rp = Path(a.report)
    allr = json.loads(rp.read_text(encoding="utf-8")) if rp.exists() else {}
    if allr.get("schema") != "nmsk.q365.nerves_report.v1":
        allr = {"schema": "nmsk.q365.nerves_report.v1", "pages": {}}
    allr["pages"][stem] = rep
    rp.parent.mkdir(parents=True, exist_ok=True)
    rp.write_text(json.dumps(allr, indent=1), encoding="utf-8")
    print(f"Q365_NERVES_{'WRITTEN' if (a.write and ship) else 'DRY'} {d}: {len(ship)} placed, {len(items) - len(ship)} held -> {rel(rp)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
