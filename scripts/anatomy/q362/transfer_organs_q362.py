#!/usr/bin/env python3
"""Q362: real organ geometry of the frozen Imaging pages, registered onto the two Base pages by the bones both bodies have.

    python3 scripts/anatomy/q362/transfer_organs_q362.py --page-dir DIR [--steps a,b] [--write] [--rig-file F] [--rig-out F]
        DIR = a copy of build/q309/viewer_zan_atlas (Base · Male) or build/q309/viewer_base_female (Base · Female)
        default steps: Base·M rectum,anal,perineal,ileum ; Base·F ileum,kidneys.  NOT default: kidneys_m (Base·M kidneys taken from the
        Visible Human FEMALE -- only on the owner's say-so).

Owner (2026-11-17, Q362): "interesting solution, may be synergistic with the atlases". The Q363 audit found these organs absent on the Base
pages with a real source only on the frozen own-engine Imaging pages (read here, never written: build/q309/viewer_m_hr, viewer_f_hr).

Sources and licences (repo provenance: docs/GEOMETRY_SOURCES.md, data/derived/Q170_vhm_pelvic_viscera.json, Q193_viscera_v?m.json,
Q172_vhm_pfloor_rebuild.json, mappings/subjects/ct_vhm_pfloor_volume_mapping.json):
  * rectum (ct_vhm_pelvis), small bowel (ct_vhm_viscera / ct_vhf_viscera), kidneys (ct_vhf_viscera): the Visible Human male / female
    frozen CT (U.S. National Library of Medicine, public domain; "Courtesy of the U.S. National Library of Medicine"), segmented by the
    TotalSegmentator v2 `total` task (Apache-2.0 software; an open task, its output ours to derive) -- shown on the Base pages freely.
  * perineal muscles + external anal sphincter (ct_vhm_pfloor): his cryosection photographs (NLM, public domain) segmented by THIS
    project's position rules + marker watershed, bounded by his CT bone / organ labels (Q172, badged RULE-BASED there): licence-free, but
    the outline is rule-based on a real image -- the card says so.  Bulbospongiosus / ischiocavernosus include the erectile tissue they
    cover (no septum at 1 mm, Q172 note).  He has no superficial transverse perineal muscle (< 1 cm3 per side, not shipped by Q172) and no
    separate internal sphincter / anal canal (inside the CT colon label = this rectum's lowest part).
  * the Z-Anatomy kidney (CC-BY-NC) stays excluded (data/derived/zanatomy_inventory.json nc_licensing_note).

Registration (scripts/anatomy/q362/register_q362.py): a SIMILARITY transform per (source body, region, page) by trimmed symmetric ICP on
paired bones -- pelvis: hip bones, sacrum, coccyx (his only), proximal femora; kidney: T11-L4 + ribs 11-12; abdomen (small bowel): L1-L5,
hip bones, sacrum, ribs 10-12.  No warp: a bone-driven thin-plate spline was tried (40/80 control points, smoothing 10/100) and lowers
the bone residual by only 0.4-1.7 mm median while it moves the organs by a median 4-21 mm (max 50 mm, extrapolating far from the
bones) -- more than the residual it would remove; the organ keeps the subject's shape exactly (uniform scale only).
Guards per organ (an organ failing one is held, the others ship): no vertex > BONE_MM inside a bone of the page; no vertex outside the
skin (Q357 voxel body, Q365 ray fallback); closed mesh.  A violation may be fixed only by a rigid nudge of the whole organ of at most
NUDGE_CAP mm (smallest translation that clears bone and skin), never by reshaping.  Soft-tissue overlaps are measured and listed
(neighbour, vertices, depth) both ways; none is resolved by reshaping the organ.
Checks against the owner's books (knowledge only, facts + page): see BOOK / book_checks(); a placement that contradicts them is held.
Write: new meshes before the trailing block (Base·F: skin_vulva_cvh, skin_perineum_rule_q358 stay last), every other mesh keeps its
order; the Z structure a transfer replaces is hidden by default (`hd`, as Base·F's Q292 rectum hid the Z sigmoid); originals copied
beside each changed file as `<name>.q362` (never overwritten); the pose rig is spliced (each new mesh rigid in its stated segment) and
written to --rig-out; a page that already carries a requested step's ids is refused.  Deterministic.
Report: data/derived/Q362_transfer_report.json (per page)."""
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
for p in ("", "scripts", "scripts/zanatomy", "scripts/anatomy/q340", "scripts/anatomy/q349", "scripts/anatomy/q357",
          "scripts/anatomy/q241", "scripts/anatomy/q362"):
    sys.path.insert(0, str(REPO / p))
import build_zan_atlas_viewer as BZ      # noqa: E402  pack_mesh / split_blob
import conform_palm_q340 as C340         # noqa: E402  page I/O
import conform_fingers_q349 as C349      # noqa: E402  winding number
import srcpage_q362 as SP                # noqa: E402  frozen own-engine pages (read only)
import register_q362 as RG               # noqa: E402  bone registration

TAG = "Q362"
SUFFIX = ".q362"
REPORT = REPO / "data/derived/Q362_transfer_report.json"
DIRKEY = {"viewer_zan_atlas": "base_m", "viewer_base_female": "base_f"}
STEM = {"base_m": "atlas_viewer_zan_atlas", "base_f": "atlas_viewer_base_female"}
TRAIL = ("skin_vulva_cvh", "skin_perineum_rule_q358")
SRC = {"m": REPO / "build/q309/viewer_m_hr", "f": REPO / "build/q309/viewer_f_hr"}
BONE_MM = 1.0
NUDGE_CAP = 5.0
SOLID = ("viscera", "muscle", "cns")   # solid neighbours (fat volumes, open fascial sheets, vessel / nerve / lymph tubes: listed only)
SOFT_DEPTH = 3.0     # mm: an organ vertex deeper than this inside a solid neighbour counts as a real overlap
SOFT_FRAC = 0.03
NONBLOCKING = ("length",)   # a book check that differs holds the organ, except these (a size is the subject's own)     # held when more than this share of the organ's vertices is deeper than SOFT_DEPTH in one solid neighbour
DEFAULT_STEPS = {"base_m": ["rectum", "anal", "perineal", "ileum"], "base_f": ["ileum", "kidneys"]}
ALL_STEPS = {"base_m": ["rectum", "anal", "perineal", "ileum", "kidneys_m"], "base_f": ["ileum", "kidneys"]}

M17 = "Noor MA. Mannan's Regional Dissection and Surface Anatomy, 14th ed. Jaypee, New Delhi 2017"
GA = "Drake RL, Vogl AW, Mitchell AWM et al. Gray's Atlas of Anatomy, Churchill Livingstone / Elsevier (edition not in the owner's scan)"
NLM = "U.S. National Library of Medicine, The Visible Human Project (public domain; courtesy of the U.S. National Library of Medicine)"
TS = "TotalSegmentator v2 `total` task (Apache-2.0 software, an openly available task)"
WHO = {"m": ("Visible Human male", "his"), "f": ("Visible Human female", "her")}

# step, page key, source body, source id, new id, side, sys, region, name, kind, latin, rig segment ("vert" = nearest vertebra / pelvis)
ORGANS = [
    dict(step="rectum", key="base_m", src="m", sid="rectum", id="rectum_vhm", side="m", sys="viscera", region="pelvis", kind="ct",
         name="Rectum (Visible Human male CT, registered)", latin="Rectum", folder="viscera", seg="pelvis", subject="ct_vhm_pelvis",
         hide=["zan_sigmoid_colon"]),
    dict(step="anal", key="base_m", src="m", sid="external_anal_sphincter", id="external_anal_sphincter_vhm", side="m", sys="muscle",
         region="pelvis", kind="q172", name="External anal sphincter (Visible Human male, registered)", latin="Musculus sphincter ani externus",
         folder="trunk", seg="pelvis", hide=["external_anal_sphincter"], subject="ct_vhm_pfloor"),
    *[dict(step="perineal", key="base_m", src="m", sid=f"{b}_{s}", id=f"{b}_vhm_{s}", side=s, sys="muscle", region="pelvis", kind="q172",
           name=f"{n} (Visible Human male, registered)", latin=lat, folder="trunk", seg="pelvis", subject="ct_vhm_pfloor",
           allow=(["zan_corpus_spongiosum_of_penis", "zan_corpus_cavernosum_of_penis"] if b != "deep_transverse_perineal" else []))
      for b, n, lat in (("bulbospongiosus", "Bulbospongiosus", "Musculus bulbospongiosus"),
                        ("ischiocavernosus", "Ischiocavernosus", "Musculus ischiocavernosus"),
                        ("deep_transverse_perineal", "Deep transverse perineal muscle", "Musculus transversus perinei profundus"))
      for s in "lr"],
    dict(step="ileum", key="base_m", src="m", sid="small_bowel", id="small_bowel_vhm", side="m", sys="viscera", region="abdomen", kind="ct", hide=["zan_jejunum"],
         name="Small bowel: jejunum and ileum (Visible Human male CT, registered)", latin="Intestinum tenue (jejunum et ileum)",
         folder="viscera", seg="vert", subject="ct_vhm_viscera"),
    dict(step="ileum", key="base_f", src="f", sid="small_bowel", id="small_bowel_vhf", side="m", sys="viscera", region="abdomen", kind="ct", hide=["zan_jejunum"],
         name="Small bowel: jejunum and ileum (Visible Human female CT, registered)", latin="Intestinum tenue (jejunum et ileum)",
         folder="viscera", seg="vert", subject="ct_vhf_viscera"),
    *[dict(step="kidneys", key="base_f", src="f", sid=f"kidney_{s}", id=f"kidney_vhf_{s}", side=s, sys="viscera", region="kidney", kind="ct",
           name=f"Kidney, {'left' if s == 'l' else 'right'} (Visible Human female CT, registered)", latin=f"Ren {'sinister' if s == 'l' else 'dexter'}",
           folder="viscera", seg="vert", subject="ct_vhf_viscera") for s in "lr"],
    *[dict(step="kidneys_m", key="base_m", src="f", sid=f"kidney_{s}", id=f"kidney_vhf_{s}", side=s, sys="viscera", region="kidney", kind="ct",
           name=f"Kidney, {'left' if s == 'l' else 'right'} (from the Visible Human FEMALE CT, registered onto this male body)",
           latin=f"Ren {'sinister' if s == 'l' else 'dexter'}", folder="viscera", seg="vert", subject="ct_vhf_viscera", cross_sex=True)
      for s in "lr"],
]


# ------------------------------------------------------------------ page I/O
def read_page(d: Path, stem):
    man, blob, files = C340.read_page(d, stem)
    E = {}
    for m in man["meshes"]:
        v, f = C340.dec(m, blob)
        E[m["id"]] = dict(v=v, f=f, sys=m["sys"], name=m["name"])
    return man, blob, files, E


def repack(man, blob, insert, before, hide):
    """insert = [(entry, v, f)] placed before the first id of `before` present (else at the end); hide = ids that get hd:1."""
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
            if m["id"] in hide:
                n["hd"] = 1
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
        bc = t.get("by_category")
        if isinstance(bc, dict):
            for entry, _, _ in insert:
                c = {"viscera": "organ", "muscle": "muscle"}[entry["sys"]]
                bc[c] = bc.get(c, 0) + 1
        man2["totals"] = t
    return man2, b"".join(chunks), cut


def write_page(d: Path, stem, man_old, man_new, blob_new, old_files):
    pages = C340.pages_of(d, stem)
    texts = {p: p.read_text(encoding="utf-8") for p in pages}
    for p, t in texts.items():
        assert C340.LIT["manifest"].search(t).group(1) == C340.ser_manifest(man_old), f"{p}: manifest serialisation differs"
        assert C340.LIT["files"].search(t).group(1) == json.dumps(old_files), f"{p}: file list serialisation differs"
    chunks = BZ.split_blob(blob_new, stem)
    names_old = [f["path"] for f in old_files]
    names_new = [n for n, _ in chunks]
    assert names_new[:len(names_old)] == names_old, "geo file names would change; not handled"
    files = [{"path": n, "bytes": len(c), "enc": "base64"} for n, c in chunks]
    changed = []
    for n, c in chunks:
        p = d / n; new = base64.b64encode(c)
        if not p.exists():
            p.write_bytes(new); changed.append(n + " (new)")
        elif p.read_bytes() != new:
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


# ------------------------------------------------------------------ measures
def mstats(v, f):
    t = trimesh.Trimesh(v, f, process=False)
    ext = np.ptp(v, 0)
    return dict(vertices=int(len(v)), triangles=int(len(f)), closed=bool(t.is_watertight),
                volume_cm3=round(abs(float(t.volume)) / 1000.0, 2), area_cm2=round(float(t.area) / 100.0, 1),
                bbox_mm=[round(float(x), 1) for x in ext])


def winding_in(P, v, f):
    return np.abs(C349.winding(P, v, f)) > 0.5


class Fit:
    """bones (Q357 Bones: winding inside + fast signed view), the skin body (Q357 Context), the soft neighbours of the page."""

    def __init__(self, d: Path, key, E):
        import conform_in_bone_q357 as Q357
        self.Q = Q357
        os.environ["Q241_SRC_" + key] = str(d)
        M = Q357.load_model(d)
        self.ctx = Q357.Context(M, Q357.Allow())
        self.B = Q357.Bones(M)
        self.E = E
        self._tm = {}

    def tm(self, i):
        if i not in self._tm:
            self._tm[i] = trimesh.Trimesh(self.E[i]["v"], self.E[i]["f"], process=False)
        return self._tm[i]

    def in_bone(self, V):
        lo, hi = V.min(0) - 2, V.max(0) + 2
        keys = [k for k in self.B.names if not (np.any(self.B.T[k].bounds[0] > hi) or np.any(self.B.T[k].bounds[1] < lo))]
        ins, name, dep = self.B.inside(V, keys, tol=BONE_MM)
        out = {}
        for k in set(name[ins]):
            m = name == k
            out[k] = dict(vertices=int(m.sum()), max_mm=round(float(dep[m].max()), 2))
        return out, ins

    def outside_skin(self, V):
        o = self.ctx.outside_skin(V) > 0
        if not o.any():
            return 0, o
        # an axial slice whose 2-D fill failed reads 'outside' for every point: there a ray from the body axis out through the vertex must
        # still cross the skin beyond it (as Q365 Guarder.outside_skin)
        sk = self.skin_near(V)
        if not hasattr(self, "_axis"):
            allv = np.vstack([self.E[i]["v"] for i in self.E if re.match(r"zan_vertebra_[tl]\d+$|sacrum$", i)])
            self._axis = (float(np.median(allv[:, 0])), float(np.median(allv[:, 2])))
        xm, zc = self._axis
        res = np.zeros(len(V), bool)
        J = np.where(o)[0]
        A = np.column_stack([np.full(len(J), xm), V[J, 1], np.full(len(J), zc)])
        filled = self.ctx.outside_skin(A) == 0
        res[J[filled]] = True                                   # the slice is filled: the voxel verdict stands
        K = J[~filled]
        if len(K):
            Dv = V[K] - A[~filled]; Dv[:, 1] = 0.0
            L = np.linalg.norm(Dv, axis=1)
            ok = L > 1e-6
            hit = np.zeros(len(K), bool)
            if sk is not None and ok.any():
                hit[ok] = sk.ray.intersects_any(V[K][ok], Dv[ok] / L[ok][:, None])
            res[K[~hit]] = True
        return int(res.sum()), res

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
        return trimesh.Trimesh(np.vstack(vs), np.vstack(fs), process=False) if vs else None

    def solid_grid(self, V, allowed):
        """depth (mm) inside any SOLID neighbour (viscera / muscle / cns, not `allowed`) on a 1 mm grid around the organ (+ NUDGE_CAP):
        winding inside mask per neighbour, depth = Euclidean distance transform of the mask.  Used to score nudge candidates."""
        from scipy import ndimage
        lo = V.min(0) - NUDGE_CAP - 3; hi = V.max(0) + NUDGE_CAP + 3
        shp = np.ceil(hi - lo).astype(int) + 1
        g = np.stack(np.meshgrid(*[lo[i] + np.arange(shp[i]) for i in range(3)], indexing="ij"), -1).reshape(-1, 3)
        dep = np.zeros(len(g))
        for k, e in self.E.items():
            if e["sys"] not in SOLID or k in allowed:
                continue
            v = e["v"]
            if (v.min(0) > hi).any() or (v.max(0) < lo).any():
                continue
            m = np.all((g > v.min(0) - 0.5) & (g < v.max(0) + 0.5), axis=1)
            if not m.any():
                continue
            idx = np.where(m)[0]
            ins = np.zeros(len(g), bool); ins[idx[winding_in(g[idx], v, e["f"])]] = True
            if ins.any():
                dep = np.maximum(dep, ndimage.distance_transform_edt(ins.reshape(shp)).ravel())
        D = dep.reshape(shp)
        return lambda P: D[tuple(np.clip(np.rint(P - lo).astype(int), 0, shp - 1).T)]

    def nudge(self, V, allowed=()):
        """smallest-cost rigid translation (<= NUDGE_CAP mm) that leaves no vertex > BONE_MM in bone and none outside the skin, and puts
        as few organ vertices as possible deeper than SOFT_DEPTH in a solid neighbour (ties: the smaller move)."""
        b0, _ = self.in_bone(V); s0, _ = self.outside_skin(V)
        depth = self.solid_grid(V, set(allowed))
        c0 = int((depth(V) > SOFT_DEPTH).sum())
        if not b0 and not s0 and c0 <= SOFT_FRAC * len(V):
            return np.zeros(3), dict(needed=False, deep_solid_vertices=c0)
        dirs = [np.array((x, y, z), float) for x in (-1, 0, 1) for y in (-1, 0, 1) for z in (-1, 0, 1) if (x, y, z) != (0, 0, 0)]
        dirs = [u / np.linalg.norm(u) for u in dirs]
        if b0:                                       # the bones' outward normal at the offending vertices
            _, ins = self.in_bone(V)
            d, i = cKDTree(self.B.P).query(V[ins])
            n = self.B.N[i].mean(0)
            if np.linalg.norm(n) > 1e-6:
                dirs.insert(0, n / np.linalg.norm(n))
        s0v = int((self.ctx.outside_skin(V) > 0).sum())
        lo, hi = V.min(0) - NUDGE_CAP - 2, V.max(0) + NUDGE_CAP + 2
        bv = self.B.subset([k for k in self.B.names if not (np.any(self.B.T[k].bounds[0] > hi) or np.any(self.B.T[k].bounds[1] < lo))], lo, hi)
        cands = []
        for step in np.arange(0.5, NUDGE_CAP + 1e-9, 0.5):
            for u in dirs:
                W = V + step * u
                if (bv.signed(W)[0] > BONE_MM).any():            # fast screens; the exact tests below confirm
                    continue
                if (self.ctx.outside_skin(W) > 0).sum() > s0v:
                    continue
                cands.append((int((depth(W) > SOFT_DEPTH).sum()), float(step), u))
        cands.sort(key=lambda c: (c[0], c[1]))
        for c, step, u in cands[:40]:
            if c >= c0 and not b0 and not s0:
                break
            W = V + step * u
            b, _ = self.in_bone(W); s, _ = self.outside_skin(W)
            if not b and not s:
                return step * u, dict(needed=True, mm=round(step, 2), direction=[round(float(x), 3) for x in u],
                                      before=dict(in_bone=b0, outside_skin=s0, deep_solid_vertices=c0), deep_solid_vertices=c)
        return None if (b0 or s0) else np.zeros(3), dict(needed=True, failed=True, before=dict(in_bone=b0, outside_skin=s0, deep_solid_vertices=c0))

    def overlaps(self, sid, V, F, others=(), skip=()):
        """soft neighbours: (a) the organ's vertices inside a neighbour (winding > 0.5), depth = distance to that neighbour's surface;
        (b) the neighbour's vertices inside the (closed) organ, depth = distance to the organ's surface."""
        lo, hi = V.min(0) - 1, V.max(0) + 1
        org = trimesh.Trimesh(V, F, process=False)
        rows = []
        pool = [(k, e["v"], e["f"], e["sys"]) for k, e in self.E.items() if e["sys"] not in ("bone", "skin", "fat", "fascia", "insertion")
                and k not in skip]
        pool += [(k, v, f, s) for k, v, f, s in others if k != sid]
        for k, v, f, s in pool:
            if (v.min(0) > hi).any() or (v.max(0) < lo).any():
                continue
            m = np.all((V > v.min(0) - 0.5) & (V < v.max(0) + 0.5), axis=1)
            a = np.zeros(len(V), bool)
            if m.any():
                idx = np.where(m)[0]
                a[idx[winding_in(V[idx], v, f)]] = True
            mb = np.all((v > lo) & (v < hi), axis=1)
            b = np.zeros(len(v), bool)
            if mb.any():
                idx = np.where(mb)[0]
                b[idx[winding_in(v[idx], V, F)]] = True
            if not a.any() and not b.any():
                continue
            da = trimesh.proximity.closest_point(trimesh.Trimesh(v, f, process=False), V[a])[1] if a.any() else np.zeros(0)
            db = trimesh.proximity.closest_point(org, v[b])[1] if b.any() else np.zeros(0)
            rows.append(dict(neighbour=k, sys=s, cls="solid" if s in SOLID else "minor",
                             organ_vertices_inside=int(a.sum()), organ_vertices_deeper_than_soft_mm=int((da > SOFT_DEPTH).sum()),
                             organ_depth_max_mm=round(float(da.max()), 1) if len(da) else 0.0,
                             neighbour_vertices_inside=int(b.sum()), neighbour_vertices=int(len(v)),
                             neighbour_depth_max_mm=round(float(db.max()), 1) if len(db) else 0.0))
        rows.sort(key=lambda r: -(r["organ_vertices_inside"] + r["neighbour_vertices_inside"]))
        return rows


# ------------------------------------------------------------------ the owner's books (knowledge only: facts + page)
BOOK = {
    "kidney_levels": (f"{M17}, p. 333 (PDF p. 351)", "each kidney extends from T11 to L3"),
    "kidney_size": (f"{M17}, p. 333 (PDF p. 351)", "about 10 cm long, 6 cm broad, 3 cm thick"),
    "kidney_hilum": (f"{M17}, pp. 528-529 (PDF pp. 546-547)",
                     "hilum about 2 in (51 mm) from the median plane, opposite L1 (back); right a little lower than left"),
    "kidney_rib12": (f"{GA}, p. 177", "ribs XI-XII lie on the posterior surface of the kidneys (with diaphragm, psoas, quadratus lumborum)"),
    "rectum_s3": (f"{M17}, p. 385 (PDF p. 403) and p. 563 'Levels' (PDF p. 581)", "the rectum begins at the third sacral vertebra"),
    "rectum_curve": (f"{M17}, p. 385 (PDF p. 403)", "it passes down in the concavity of the sacrum; dilated (ampulla) at the level of the coccyx"),
    "rectum_bend": (f"{M17}, p. 385 (PDF p. 403)", "about 3 cm in front of the coccyx it bends sharply backwards to become the anal canal"),
    "rectum_bladder": (f"{M17}, p. 351 (PDF p. 369); {GA}, p. 216", "in the male the rectum lies behind the bladder and prostate"),
    "anal_canal": (f"{M17}, p. 385 (PDF p. 403)", "anal canal: below the pelvic diaphragm, 3.8 cm long"),
    "eas_parts": (f"{GA}, p. 216", "external anal sphincter: subcutaneous, superficial and deep parts, around the anal canal"),
    "perineal_body": (f"{M17}, p. 354 (PDF p. 372)", "perineal body about 1/2 in in front of the anus, between the anus and the bulb; "
                      "sphincter ani externus meets it from behind, bulbospongiosus from the front"),
    "ischiocavernosus": (f"{M17}, p. 355 (PDF p. 373)", "from the ramus of the ischium close to its tuberosity, onto the crus penis"),
    "bulbospongiosus": (f"{M17}, p. 355 (PDF p. 373)", "from the median raphe and the perineal body; embraces the bulb and corpus spongiosum"),
    "deep_transverse": (f"{M17}, p. 359 (PDF p. 377)", "from the ramus of the ischium, medially to the median raphe and the perineal body"),
    "ileum": (f"{M17}, p. 380 (PDF p. 398)", "the ileum (distal 3/5 of the small intestine) lies between the outline of the large gut and the pelvis"),
    "ileocaecal": (f"{GA}, pp. 155, 158", "the ileum ends at the ileocaecal junction on the caecum (right iliac fossa)"),
}


def vlevels(E):
    lv = {}
    for k in E:
        m = re.match(r"zan_vertebra_([tl]\d+)$", k)
        if m:
            v = E[k]["v"]
            lv[m.group(1).upper()] = dict(y=float(v[:, 1].mean()), top=float(v[:, 1].max()), bot=float(v[:, 1].min()),
                                         body=float(np.median(v[v[:, 2] > np.median(v[:, 2]), 1])))
    return lv


def level_of(y, lv):
    """the vertebra whose body-height band holds y (bands split half-way between neighbouring body centres)"""
    order = ["T10", "T11", "T12", "L1", "L2", "L3", "L4", "L5"]
    c = [(n, lv[n]["body"]) for n in order if n in lv]
    best = min(c, key=lambda t: abs(t[1] - y))
    i = [n for n, _ in c].index(best[0])
    frac = (y - best[1]) / ((c[i - 1][1] - best[1]) if y > best[1] and i > 0 else (best[1] - c[i + 1][1]) if i + 1 < len(c) else 30.0)
    return best[0] + ("" if abs(frac) < 0.25 else (" (upper part)" if y > best[1] else " (lower part)"))


def chk(name, ok, measured, expected, cite, differs=None):
    return dict(check=name, verdict="pass" if ok else "differs", measured=measured, books=expected, citation=cite,
                **({"by": differs} if differs and not ok else {}))


def book_checks(o, V, F, E, placed):
    s = o["step"]
    out = []
    if s in ("kidneys", "kidneys_m"):
        lv = vlevels(E)
        top, bot = float(V[:, 1].max()), float(V[:, 1].min())
        lt, lb = level_of(top, lv), level_of(bot, lv)
        okl = lt.split()[0] in ("T11", "T12", "T10") and lb.split()[0] in ("L2", "L3", "L4")
        out.append(chk("vertebral levels (poles)", okl, f"upper pole {lt}, lower pole {lb}", BOOK["kidney_levels"][1], BOOK["kidney_levels"][0],
                       f"upper pole at {lt}, lower at {lb}"))
        ax = np.linalg.svd(V - V.mean(0), full_matrices=False)[2][0]
        L = float(np.ptp((V - V.mean(0)) @ ax))
        out.append(chk("length", 80 <= L <= 140, f"{L:.0f} mm", BOOK["kidney_size"][1], BOOK["kidney_size"][0], f"{L - 100:+.0f} mm vs 10 cm"))
        xm = float(np.median(np.vstack([E[k]["v"] for k in E if re.match(r"zan_vertebra_[tl]\d+$", k)])[:, 0]))
        c = V.mean(0)
        band = V[np.abs(V[:, 1] - c[1]) < 10]
        med = band[np.argmin(np.abs(band[:, 0] - xm))]
        dx = abs(float(med[0]) - xm)
        hl = level_of(float(c[1]), lv)
        okh = hl.split()[0] in ("T12", "L1", "L2")
        out.append(chk("hilum (centre of the medial border) level", okh, f"{hl}; medial border {dx:.0f} mm from the median plane",
                       BOOK["kidney_hilum"][1], BOOK["kidney_hilum"][0], f"hilum at {hl}"))
        r12 = E.get(f"zan_twelfth_rib_{o['side']}")
        if r12 is not None:
            R = r12["v"]
            inx = (R[:, 0] > V[:, 0].min()) & (R[:, 0] < V[:, 0].max()) & (R[:, 1] > V[:, 1].min()) & (R[:, 1] < V[:, 1].max())
            behind = inx & (R[:, 2] < c[2])
            d = float(cKDTree(V).query(R[inx])[0].min()) if inx.any() else None
            ok12 = bool(behind.sum() >= 5)
            out.append(chk("12th rib on its posterior surface", ok12,
                           f"{int(behind.sum())} rib-12 vertices overlap the kidney's coronal outline behind it" + (f", nearest {d:.0f} mm" if d is not None else ""),
                           BOOK["kidney_rib12"][1], BOOK["kidney_rib12"][0], "rib 12 not behind the kidney"))
        u = E.get(f"zan_ureter_{o['side']}")
        if u is not None:
            top_u = u["v"][np.argmax(u["v"][:, 1])]
            du = float(cKDTree(V).query(top_u)[0])
            out.append(dict(check="ureter continuity (measured only)", verdict="info", measured=f"upper end of the Z-Anatomy ureter {du:.0f} mm from the kidney"))
    elif s == "rectum":
        sac = E["sacrum"]["v"]; cx = E["coccyx"]["v"]
        mid = sac[np.abs(sac[:, 0] - np.median(sac[:, 0])) < 15]
        prom = mid[np.argmax(mid[:, 1] + 0.3 * mid[:, 2])]
        apex_y = float(sac[:, 1].min())
        top = float(V[:, 1].max())
        fr = (float(prom[1]) - top) / (float(prom[1]) - apex_y)
        ok = 0.30 <= fr <= 0.70
        out.append(chk("upper end at the 3rd sacral vertebra", ok,
                       f"upper end at {fr:.2f} of the sacral height below the promontory (S3 ~ 0.40-0.60 by equal segments)",
                       BOOK["rectum_s3"][1], BOOK["rectum_s3"][0], f"{fr:.2f} of the sacral height"))
        # posterior wall in the sacral hollow: distance from the rectum's posterior surface to sacrum + coccyx along its height
        bone = np.vstack([sac, cx]); bt = cKDTree(bone)
        ys = np.arange(V[:, 1].min() + 10, top - 5, 5.0)
        gaps = []
        for y in ys:
            sl = V[np.abs(V[:, 1] - y) < 2.5]
            if len(sl):
                p = sl[np.argmin(sl[:, 2])]
                b = bone[np.abs(bone[:, 1] - y) < 4]
                if len(b):
                    gaps.append(float(p[2] - b[:, 2].max()))
        g = np.array(gaps) if gaps else np.array([np.nan])
        okc = bool(np.nanmedian(g) > -2 and np.nanmedian(g) < 40)
        out.append(chk("in the concavity of the sacrum", okc,
                       f"posterior wall {np.nanmedian(g):.0f} mm (median; range {np.nanmin(g):.0f}..{np.nanmax(g):.0f}) in front of the sacrum/coccyx at the same height",
                       BOOK["rectum_curve"][1], BOOK["rectum_curve"][0], f"median {np.nanmedian(g):.0f} mm"))
        tip = cx[np.argmin(cx[:, 1])]
        sl = V[np.abs(V[:, 1] - tip[1]) < 4]
        if len(sl):
            dz = float(sl[:, 2].mean() - tip[2])
            out.append(chk("bend ~3 cm in front of the coccyx", 15 <= dz <= 50, f"rectum centre {dz:.0f} mm in front of the coccyx tip at its height",
                           BOOK["rectum_bend"][1], BOOK["rectum_bend"][0], f"{dz - 30:+.0f} mm vs 30 mm"))
        for nb in ("zan_prostate", "zan_urinary_bladder"):
            if nb in E:
                P = E[nb]["v"]
                ylo, yhi = P[:, 1].min(), P[:, 1].max()
                sl = V[(V[:, 1] > ylo) & (V[:, 1] < yhi)]
                if len(sl):
                    gap = float(np.percentile(P[:, 2], 2) - sl[:, 2].max())
                    out.append(chk(f"behind the {E[nb]['name'].lower()}", gap > -8.0,
                                   f"rectum front {gap:+.0f} mm behind the {E[nb]['name'].lower()}'s back (2nd percentile) at its height",
                                   BOOK["rectum_bladder"][1], BOOK["rectum_bladder"][0], f"overlaps by {-gap:.0f} mm"))
        dco = E.get("zan_descending_colon")
        if dco is not None:
            lowp = dco["v"][np.argmin(dco["v"][:, 1])]
            out.append(dict(check="continuity with the colon above (measured only)", verdict="info",
                            measured=f"lowest point of the Z-Anatomy descending colon {float(cKDTree(V).query(lowp)[0]):.0f} mm from this rectum"))
        la = [E[k]["v"] for k in ("levator_ani_l", "levator_ani_r") if k in E]
        if la:
            Lv = np.vstack(la); low = V[V[:, 1] < V[:, 1].min() + 40]
            below = float(np.median(Lv[:, 1]) - V[:, 1].min())
            out.append(dict(check="anal part below the pelvic diaphragm (measured only)", verdict="info",
                            measured=f"the mesh's lowest point is {below:.0f} mm below the median height of the levator ani",
                            books=BOOK["anal_canal"][1], citation=BOOK["anal_canal"][0]))
    elif s == "anal":
        rect = placed.get("rectum_vhm")
        if rect is not None:
            R = rect[0]; d = float(np.linalg.norm(V.mean(0)[[0, 2]] - R[R[:, 1] < R[:, 1].min() + 15].mean(0)[[0, 2]]))
            dy = float(V.mean(0)[1] - R[:, 1].min())
            out.append(chk("around the anal canal (the rectum's lowest part)", d < 12 and -5 < dy < 35,
                           f"ring axis {d:.0f} mm from the canal axis; ring centre {dy:.0f} mm above the canal's lowest point",
                           BOOK["eas_parts"][1], BOOK["eas_parts"][0], f"axis off by {d:.0f} mm"))
        sk = [E[k]["v"] for k in ("zan_skin_anal_region_l", "zan_skin_anal_region_r") if k in E]
        if sk:
            S = np.vstack(sk)
            dsk = float(cKDTree(S).query(V)[0].min())
            out.append(dict(check="gap to the anal skin (measured only: the source holds the deep part only)", verdict="info",
                            measured=f"nearest anal-region skin {dsk:.0f} mm; the subcutaneous and superficial parts and the lower anal canal are not "
                                     f"in the source segmentation (the ring is 10 mm tall at the anorectal junction)",
                            books=BOOK["eas_parts"][1], citation=BOOK["eas_parts"][0]))
        if "external_anal_sphincter" in E:
            z = E["external_anal_sphincter"]["v"]
            out.append(dict(check="Z-Anatomy sphincter it replaces (measured only)", verdict="info",
                            measured=f"Z-Anatomy external anal sphincter lowest point {float(z[:, 1].min()):.0f} mm vs this one {float(V[:, 1].min()):.0f} mm"))
    elif s == "perineal":
        hip = E[f"hip_bone_{o['side']}"]
        ht = trimesh.Trimesh(hip["v"], hip["f"], process=False)
        dmin = float(np.abs(trimesh.proximity.signed_distance(ht, V[::max(1, len(V) // 800)])).min())
        xm = float(np.median(E["sacrum"]["v"][:, 0]))
        medial = float(np.abs(V[:, 0] - xm).min())
        if o["sid"].startswith("ischiocavernosus"):
            out.append(chk("on the ischiopubic ramus", dmin < 6.0, f"{dmin:.1f} mm from the hip bone", BOOK["ischiocavernosus"][1],
                           BOOK["ischiocavernosus"][0], f"{dmin:.0f} mm from the bone"))
            cc = E.get("zan_corpus_cavernosum_of_penis")
            if cc is not None:
                dc = float(cKDTree(cc["v"]).query(V)[0].min())
                out.append(chk("covers the crus penis", dc < 6.0, f"{dc:.1f} mm from the corpus cavernosum", BOOK["ischiocavernosus"][1],
                               BOOK["ischiocavernosus"][0], f"{dc:.0f} mm away"))
        elif o["sid"].startswith("bulbospongiosus"):
            out.append(chk("in the midline (median raphe)", medial < 6.0, f"medial edge {medial:.1f} mm from the median plane",
                           BOOK["bulbospongiosus"][1], BOOK["bulbospongiosus"][0], f"{medial:.0f} mm off the midline"))
            cs = E.get("zan_corpus_spongiosum_of_penis")
            if cs is not None:
                dc = float(cKDTree(cs["v"]).query(V)[0].min())
                out.append(chk("embraces the bulb (corpus spongiosum)", dc < 6.0, f"{dc:.1f} mm from the corpus spongiosum", BOOK["bulbospongiosus"][1],
                               BOOK["bulbospongiosus"][0], f"{dc:.0f} mm away"))
        else:
            out.append(chk("from the ischial ramus", dmin < 6.0, f"{dmin:.1f} mm from the hip bone", BOOK["deep_transverse"][1],
                           BOOK["deep_transverse"][0], f"{dmin:.0f} mm from the bone"))
            out.append(chk("to the median raphe", medial < 10.0, f"medial end {medial:.1f} mm from the median plane", BOOK["deep_transverse"][1],
                           BOOK["deep_transverse"][0], f"{medial:.0f} mm off the midline"))
        eas = placed.get("external_anal_sphincter_vhm")
        if eas is not None and not o["sid"].startswith("ischio"):
            de = float(cKDTree(eas[0]).query(V)[0].min())
            out.append(chk("meets the external sphincter at the perineal body", de < 12.0, f"{de:.1f} mm from the external anal sphincter",
                           BOOK["perineal_body"][1], BOOK["perineal_body"][0], f"{de:.0f} mm apart"))
    elif s == "ileum":
        tc = E.get("zan_transverse_colon"); ac = E.get("zan_ascending_colon"); dc = E.get("zan_descending_colon")
        if tc is not None:
            above = float((V[:, 1] > np.median(tc["v"][:, 1])).mean())
            out.append(chk("infracolic (below the transverse colon)", above < 0.15, f"{above * 100:.0f} % of its vertices above the transverse colon's median height",
                           BOOK["ileum"][1], BOOK["ileum"][0], f"{above * 100:.0f} % above"))
        if ac is not None and dc is not None:
            xa, xd = float(np.median(ac["v"][:, 0])), float(np.median(dc["v"][:, 0]))
            lo_, hi_ = min(xa, xd), max(xa, xd)
            inside = float(((V[:, 0] > lo_ - 15) & (V[:, 0] < hi_ + 15)).mean())
            out.append(chk("within the frame of the large gut", inside > 0.85, f"{inside * 100:.0f} % of its vertices between the ascending and descending colon (+-15 mm)",
                           BOOK["ileum"][1], BOOK["ileum"][0], f"{(1 - inside) * 100:.0f} % outside"))
            A = ac["v"]; base = A[A[:, 1] < A[:, 1].min() + 25]
            app = E.get("zan_vermiform_appendix")
            tgt = np.vstack([base] + ([app["v"]] if app is not None else []))
            dj = float(cKDTree(V).query(tgt)[0].min())
            out.append(chk("reaches the caecal end of the ascending colon (ileocaecal junction)", dj < 20.0,
                           f"{dj:.0f} mm from the lowest 25 mm of the Z-Anatomy ascending colon / the appendix (the Base pages have no caecum mesh)",
                           BOOK["ileocaecal"][1], BOOK["ileocaecal"][0], f"{dj:.0f} mm away"))
        hips = [E[k]["v"] for k in ("hip_bone_l", "hip_bone_r")]
        crest = float(np.mean([h[:, 1].max() for h in hips]))
        pel = float((V[:, 1] < crest - 60).mean())
        out.append(dict(check="share in the pelvis (measured only)", verdict="info", measured=f"{pel * 100:.0f} % of its vertices more than 60 mm below the iliac crests"))
    return out


# ------------------------------------------------------------------ records
def record(o, R, T, before, after, fitrep, checks, nudge):
    who, his = WHO[o["src"]]
    s, Rm, t = T
    deg = RG.rotation_deg(Rm)
    res = R["_all"]
    per = "; ".join(f"{k} {v['median']:.1f}" for k, v in sorted(R.items()) if k != "_all")
    if o["kind"] == "ct":
        src = (f"{who} ({NLM}), frozen CT; automatic segmentation: {TS}; subject {o['subject']} of the Imaging-based "
               f"{'Male' if o['src'] == 'm' else 'Female'} page. Registered onto this body in {TAG}.")
        lead = (f"Real organ of another body, registered: the {who}'s own CT {o['sid'].replace('_l', '').replace('_r', '').replace('_', ' ')}, "
                f"carried onto this body by the bones both have.")
        if o.get("cross_sex"):
            lead = (f"Real organ of ANOTHER body of the other sex, registered: the {who}'s own CT kidney, carried onto this male body by shared bones.")
        how = "segmented automatically from the CT (not hand-drawn)"
    else:
        src = (f"{who} ({NLM}), {his} 1 mm cryosection photographs; outlined by this project's own position rules + marker watershed, "
               f"bounded by {his} CT bone and organ labels (subject {o['subject']} of the Imaging-based Male page). Registered onto this body in {TAG}.")
        lead = (f"Rule-based outline on a real scan, registered: the {who}'s own cryosection photographs, outlined by stated position rules.")
        how = "outlined on the photographs by stated position rules and a watershed (rule-based segmentation, not a dissection)"
    nud = (f" Rigid nudge {nudge['mm']} mm (to clear bone / skin)." if nudge.get("needed") and not nudge.get("failed") else "")
    badge = (f"{lead} {how.capitalize()}. Registration: similarity fitted on {o['region']} bones ({', '.join(k for k in sorted(R) if k != '_all')}): "
             f"uniform scale x{s:.3f}, rotation {deg:.1f} deg; bone residual median {res['median']:.1f} / p90 {res['p90']:.1f} mm "
             f"(per bone median: {per}). No warp: the shape is the source's, only scaled. Volume {before['volume_cm3']} cm3 on the source, "
             f"{after['volume_cm3']} cm3 here.{nud} Not this body's own organ, not Z-Anatomy geometry, not drawn by hand.")
    if o["kind"] == "q172" and o["sid"].startswith(("bulbospongiosus", "ischiocavernosus")):
        badge += (" It includes the erectile tissue it covers (" + ("bulb of the penis" if o["sid"].startswith("bulbo") else "crus of the penis") +
                  "): erectile tissue photographs as dark as muscle and no septum separates them at 1 mm, so the mass is larger than the muscle alone.")
    if o["step"] == "rectum":
        badge += (" Its lowest part is the upper anal canal (the CT label does not separate them; the internal sphincter is inside this wall;"
                  " the lower anal canal is not in the source). The Z-Anatomy 'sigmoid colon' of this page, which runs down the sacral hollow"
                  " where this rectum lies, is hidden by default ('unhide' on its card).")
    if o["step"] == "anal":
        badge += (" Only the deep part: a 10 mm ring at the anorectal junction (the source outlined the sphincter only where the CT colon label"
                  " reaches); the superficial and subcutaneous parts are not in the source. The Z-Anatomy external anal sphincter of this page"
                  " is hidden by default ('unhide' on its card).")
    if o["step"] == "ileum":
        badge += (" One CT label holds jejunum and ileum (no boundary between them is visible on CT; the change is gradual); "
                  "the Z-Anatomy jejunum of this page is hidden by default ('unhide' on its card).")
    if o.get("cross_sex"):
        badge += (" PROVISIONAL: no real male kidney exists in any source this project may use (the Z-Anatomy kidney is CC-BY-NC; his own CT "
                  "kidney label is empty / under-segmented); this is HER kidney, scaled to his skeleton.")
    facts = {"rectum": [BOOK["rectum_s3"], BOOK["rectum_curve"], BOOK["rectum_bend"], BOOK["rectum_bladder"], BOOK["anal_canal"]],
             "anal": [BOOK["eas_parts"], BOOK["perineal_body"]],
             "ileum": [BOOK["ileum"], BOOK["ileocaecal"]],
             "kidneys": [BOOK["kidney_levels"], BOOK["kidney_size"], BOOK["kidney_hilum"], BOOK["kidney_rib12"]]}
    facts["kidneys_m"] = facts["kidneys"]
    if o["step"] == "perineal":
        facts["perineal"] = [BOOK[{"b": "bulbospongiosus", "i": "ischiocavernosus", "d": "deep_transverse"}[o["sid"][0]]], BOOK["perineal_body"]]
    fl = facts[o["step"]]
    short = {M17: "Mannan 14th ed.", GA: "Gray's Atlas"}

    def cshort(c):
        for k_, v_ in short.items():
            c = c.replace(k_, v_)
        return c
    notes = " ".join(f"{t[1][0].upper()}{t[1][1:]} ({cshort(t[0])})." for t in fl)
    cites = sorted({t[0].split(",")[0] for t in fl})
    rec = {"name": o["name"], "latin": o["latin"], "folder": o["folder"], "region": {"pelvis": "pelvis", "abdomen": "abdomen", "kidney": "abdomen"}[o["region"]]
           if o["step"] != "perineal" else "perineum",
           "source": src + " Anatomy: " + "; ".join(sorted({t[0] for t in fl})) + ".",
           "geom_src": f"{who} {'CT' if o['kind'] == 'ct' else 'cryosection photographs (rule-based outline)'} (NLM, public domain), registered "
                       f"onto this body by its bones ({TAG}) -- NOT Z-Anatomy geometry",
           "method": "registered another person's real " + ("organ" if o["kind"] == "ct" else "rule-based segmentation") +
                     " (similarity on shared bones: rotation + translation + one uniform scale), not deformed",
           "notes": notes,
           "procedural_badge": badge}
    return rec


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
    added = []
    for nid, sname in seg_of_new.items():
        si = segn.index(sname)
        rigid.setdefault(si, []).append(pos[nid]); added.append([nid, sname])
    R2 = dict(R)
    R2["nv"] = [int(m["vc"]) for m in man_new["meshes"]]; R2["count"] = len(ids_new)
    R2["rigid"] = [[s_, sorted(v)] for s_, v in sorted(rigid.items())]
    R2["skin"] = [[o2n[e[0]], *e[1:]] for e in R["skin"]]
    R2["notes"] = R["notes"] + (f"; {TAG}: +{len(added)} registered organ / muscle meshes from the Imaging pages inserted before the trailing "
                                "block (indices after it shifted), each rigid in its stated segment (pelvis, or the vertebra nearest its centre); "
                                "weights blob unchanged")
    out = dict(src); out["rig"] = R2
    if rig_out is not None:
        rig_out.parent.mkdir(parents=True, exist_ok=True)
        rig_out.write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False), encoding="utf-8")
    return {"rig_in": rel(rig_src), "rig_out": rel(rig_out) if rig_out else None, "count_before": R["count"], "count_after": R2["count"],
            "added": added}


def seg_for(o, V, E, rig):
    if o["seg"] != "vert":
        return o["seg"]
    segn = [s_[0] for s_ in rig["segs"]]
    c = V.mean(0); best = (1e9, "pelvis")
    for k, e in E.items():
        m = re.match(r"zan_vertebra_([tl]\d+)$", k)
        name = ("v" + m.group(1).upper()) if m else ("pelvis" if k == "sacrum" else None)
        if name is None or name not in segn:
            continue
        d = float(np.linalg.norm(e["v"].mean(0) - c))
        if d < best[0]:
            best = (d, name)
    return best[1]


def rel(p) -> str:
    p = Path(p).resolve()
    try:
        return str(p.relative_to(REPO))
    except ValueError:
        return "/".join(p.parts[-2:])


# ------------------------------------------------------------------ main
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--page-dir", required=True)
    ap.add_argument("--steps", default=None, help="comma list (default per page: " + "; ".join(f"{k}: {','.join(v)}" for k, v in DEFAULT_STEPS.items()) + ")")
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--allow-build", action="store_true", help="permit --write into build/q309 (the main thread's apply step)")
    ap.add_argument("--rig-file", default=None, help="pose rig to splice (default data/anatomy/pose_rig_<key>.json)")
    ap.add_argument("--rig-out", default=None, help="where the spliced rig goes (default <page-dir>/../pose_rig_<key>.q362.json)")
    ap.add_argument("--src-root", default=None, help="dir holding viewer_m_hr / viewer_f_hr (read only; default build/q309)")
    ap.add_argument("--report", default=str(REPORT))
    ap.add_argument("--dump-dir", default=None, help="also save each placed mesh as <id>.npz here (renders, inspection)")
    a = ap.parse_args(argv)
    d = Path(a.page_dir).resolve()
    key = DIRKEY.get(d.name)
    assert key, f"{d}: a Base page dir is expected ({sorted(DIRKEY)})"
    if "/build/q309/" in str(d) + "/" and a.write and not a.allow_build:
        print("refused: never write into build/q309 without --allow-build (apply on a copy; the main thread applies)")
        return 2
    steps = a.steps.split(",") if a.steps else DEFAULT_STEPS[key]
    bad = [s for s in steps if s not in ALL_STEPS[key]]
    assert not bad, f"steps {bad} are not offered on {key} ({ALL_STEPS[key]})"
    src_root = Path(a.src_root).resolve() if a.src_root else None
    srcdir = {k: (src_root / v.name if src_root else v) for k, v in SRC.items()}
    stem = STEM[key]
    t0 = time.time()
    man, blob, files, E = read_page(d, stem)
    ids = [m["id"] for m in man["meshes"]]
    todo = [o for o in ORGANS if o["key"] == key and o["step"] in steps]
    have = [o["id"] for o in todo if o["id"] in ids]
    if have:
        print(f"Q362_TRANSFER_REFUSED {d}: the page already carries {have} (steps {steps}). Re-apply only on the page before Q362: restore "
              f"every '<file>{SUFFIX}' beside its file in {d} and the pose rig, then run again.")
        return 3
    print(f"Q362 transfer on {d} ({key}), steps {steps}, {len(ids)} meshes", flush=True)
    rig_src = Path(a.rig_file).resolve() if a.rig_file else REPO / f"data/anatomy/pose_rig_{key}.json"
    rig = json.loads(rig_src.read_text(encoding="utf-8"))["rig"]
    fit = Fit(d, key, E)
    print(f"  fit context ready ({time.time() - t0:.0f} s)", flush=True)
    regs, srcs = {}, {}
    placed, items = {}, []
    for o in todo:
        if o["src"] not in srcs:
            srcs[o["src"]], _ = SP.read_own(srcdir[o["src"]])
        O = srcs[o["src"]]
        rk = (o["src"], o["region"])
        if rk not in regs:
            sb = RG.src_bones(O, o["region"]); db = RG.dst_bones(E, list(sb))
            pr = RG.Pairs(sb, db); T = pr.fit()
            regs[rk] = dict(T=T, residual=pr.residual(lambda X, T=T: RG.apply(T, X)), bones=pr.names)
            print(f"  registration {rk}: scale {T[0]:.4f} rot {RG.rotation_deg(T[1]):.2f} deg residual {regs[rk]['residual']['_all']}", flush=True)
        T = regs[rk]["T"]
        S = O[o["sid"]]
        v0, f0 = S["v"], S["f"]
        V = RG.apply(T, v0)
        before = mstats(v0, f0)
        if np.linalg.det(T[1]) < 0:
            f0 = f0[:, ::-1]
        t1 = time.time()
        allowed = set(o.get("hide", [])) | set(o.get("allow", []))
        shift, nud = fit.nudge(V, allowed)
        print(f"    {o['id']}: nudge {nud} ({time.time() - t1:.0f} s)", flush=True)
        it = dict(id=o["id"], step=o["step"], source=dict(page=srcdir[o["src"]].name, id=o["sid"], subject=S["subject"],
                                                           record_name=(S["rec"] or {}).get("name")),
                  registration=dict(region=o["region"], bones=regs[rk]["bones"], scale=round(float(T[0]), 4),
                                    rotation_deg=round(RG.rotation_deg(T[1]), 2), translation_mm=[round(float(x), 1) for x in T[2]],
                                    residual_mm=regs[rk]["residual"], warp="none"),
                  nudge=nud, status="ship", held=[])
        if shift is None:
            it["status"] = "held"; it["held"].append(f"cannot clear bone / skin with a rigid nudge <= {NUDGE_CAP} mm: {nud['before']}")
            shift = np.zeros(3)
        V = V + shift
        after = mstats(V, f0)
        sim = RG.apply(T, v0)
        it["shape"] = dict(before=before, after=after, volume_ratio=round(after["volume_cm3"] / max(before["volume_cm3"], 1e-9), 4),
                           volume_ratio_expected_scale3=round(float(T[0]) ** 3, 4),
                           deviation_from_similarity_mm=round(float(np.linalg.norm(V - sim, axis=1).max()), 2))
        ib, _ = fit.in_bone(V); osk, _ = fit.outside_skin(V)
        it["guards"] = dict(in_bone=ib, outside_skin_vertices=osk, closed=after["closed"])
        if ib:
            it["status"] = "held"; it["held"].append(f"inside bone: {ib}")
        if osk:
            it["status"] = "held"; it["held"].append(f"{osk} vertices outside the skin")
        it["V"], it["F"], it["o"] = V, f0, o
        placed[o["id"]] = (V, f0)
        items.append(it)
    # overlaps (after all are placed, so new-vs-new pairs are measured too) and book checks
    others = [(it["id"], it["V"], it["F"], it["o"]["sys"]) for it in items]
    for it in items:
        o = it["o"]
        allowed = set(o.get("hide", [])) | set(o.get("allow", []))
        it["overlaps"] = fit.overlaps(o["id"], it["V"], it["F"], others=others, skip=())
        it["overlaps_allowed"] = {"hidden_by_this_step": sorted(o.get("hide", [])), "by_design": sorted(o.get("allow", []))}
        lim = SOFT_FRAC * len(it["V"])
        for r in it["overlaps"]:
            if r["cls"] == "solid" and r["neighbour"] in E and r["neighbour"] not in allowed and r["organ_vertices_deeper_than_soft_mm"] > lim:
                it["status"] = "held"
                it["held"].append(f"overlaps {r['neighbour']}: {r['organ_vertices_deeper_than_soft_mm']} of {len(it['V'])} vertices deeper than "
                                  f"{SOFT_DEPTH} mm (max {r['organ_depth_max_mm']} mm)")
        it["book_checks"] = book_checks(o, it["V"], it["F"], E, placed)
        dif = [c for c in it["book_checks"] if c["verdict"] == "differs"]
        it["book_differs"] = [c["check"] for c in dif]
        block = [c["check"] for c in dif if c["check"] not in NONBLOCKING]
        if block:
            it["status"] = "held"; it["held"].append(f"contradicts the books: {block}")
        print(f"  {it['id']:34s} {it['status']:5s} vol {it['shape']['before']['volume_cm3']}->{it['shape']['after']['volume_cm3']} "
              f"nudge {it['nudge'].get('mm', 0)} inbone {it['guards']['in_bone']} out {it['guards']['outside_skin_vertices']} "
              f"overlaps {[(r['neighbour'], r['organ_vertices_inside'], r['organ_depth_max_mm'], r['neighbour_vertices_inside']) for r in it['overlaps'][:5]]} "
              f"books-differ {it['book_differs']} {'; '.join(it['held'])[:200]}", flush=True)
        if a.dump_dir:
            Path(a.dump_dir).mkdir(parents=True, exist_ok=True)
            np.savez(Path(a.dump_dir) / f"{it['id']}.npz", v=it["V"], f=it["F"])
    rep = {"schema": "nmsk.q362.transfer.v1", "round": TAG, "generated": time.strftime("%Y-%m-%d"), "page_dir": rel(d), "key": key,
           "steps": steps, "parameters": dict(bone_mm=BONE_MM, nudge_cap_mm=NUDGE_CAP, trim=RG.TRIM, iters=RG.ITERS,
                                              femur_top_mm=RG.FEMUR_TOP_MM, warp="none (see the module docstring)"),
           "sources": {k: rel(v) for k, v in srcdir.items()}}
    ship = [it for it in items if it["status"] == "ship"]
    insert, hide = [], set()
    seg = {}
    for it in ship:
        o = it["o"]
        rec = record(o, regs[(o["src"], o["region"])]["residual"], regs[(o["src"], o["region"])]["T"], it["shape"]["before"],
                     it["shape"]["after"], None, it["book_checks"], it["nudge"])
        it["rec"] = rec
        entry = {"name": o["name"], "id": o["id"], "side": o["side"], "sys": o["sys"], "rec": rec}
        insert.append((entry, it["V"], it["F"]))
        hide |= set(o.get("hide", []))
        seg[o["id"]] = seg_for(o, it["V"], E, rig)
    hide &= set(ids)
    rep["hidden_by_default"] = sorted(hide)
    rep["structures"] = {it["id"]: {k: v for k, v in it.items() if k not in ("V", "F", "o")} for it in items}
    rep["meshes_before"] = len(ids)
    man_new, blob_new, cut = repack(man, blob, insert, TRAIL, hide)
    ids_new = [m["id"] for m in man_new["meshes"]]
    rep["meshes_after"] = len(ids_new); rep["inserted_at"] = cut
    present = [t for t in TRAIL if t in ids]
    if present:
        assert ids_new[-len(present):] == present, f"{present} must stay at the end, in this order"
    assert [i for i in ids_new if i in set(ids)] == ids, "existing meshes must keep their order"
    rig_out = Path(a.rig_out).resolve() if a.rig_out else d.parent / f"pose_rig_{key}{SUFFIX}.json"
    rep["rig"] = splice_rig(rig_src, man, man_new, seg, rig_out if (a.write and ship) else None)
    if a.write and ship:
        rep["files_written"] = write_page(d, stem, man, man_new, blob_new, files)
    else:
        rep["files_written"] = []
    rep["seconds"] = round(time.time() - t0, 1)
    rp = Path(a.report)
    allr = json.loads(rp.read_text(encoding="utf-8")) if rp.exists() else {}
    if allr.get("schema") != "nmsk.q362.transfer_report.v1":
        allr = {"schema": "nmsk.q362.transfer_report.v1", "pages": {}}
    allr["pages"][stem + ("" if steps == DEFAULT_STEPS[key] else "+" + "+".join(steps))] = json.loads(json.dumps(rep, default=lambda x: x.tolist() if hasattr(x, "tolist") else str(x)))
    rp.parent.mkdir(parents=True, exist_ok=True)
    rp.write_text(json.dumps(allr, indent=1), encoding="utf-8")
    print(f"Q362_TRANSFER_{'WRITTEN' if (a.write and ship) else 'DRY'} {d}: {len(ship)} placed, {len(items) - len(ship)} held, "
          f"hidden {sorted(hide)} -> {rel(rp)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
