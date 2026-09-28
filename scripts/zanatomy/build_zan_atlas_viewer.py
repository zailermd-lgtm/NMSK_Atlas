#!/usr/bin/env python3
"""Q157: build ONE self-contained, full-body Z-Anatomy reference viewer, fed by this
project's OWN Z-Anatomy pipeline (so it carries this project's own corrections and
atlas records), reproducing the UI of the owner's preferred August viewer (built in
another session, not this repo -- see PROJECT_STATE.md Q157) instead of this
project's own existing `viewer/atlas_viewer.template.html`.

Reuses, unchanged:
  - `scripts/zanatomy/zan_source.load_source()` for every MATCHED entity (this
    project's own atlas id, geometry from Z-Anatomy) -- the same pool
    `scripts/zanatomy/build_zan_reference.py` uses, side-split-nerve fix and all.
  - `scripts/zanatomy/build_zan_reference.build_orphan_pool()`/`compute_origin()`/
    `classify_orphan_category()` for every ORPHAN (a real Z-Anatomy structure with
    no confident/exact match to one of this project's own entities) -- kept under
    a stable `zan_<slug>[_r|_l]` id, same as that module.
  - `scripts/zanatomy/apply_corrections.apply_correction()` for the declarative,
    cited Q144/Q145 posterior-interosseous-nerve correction (and any future one
    under `data/corrections/zanatomy/`), applied on the same raw, pre-origin atlas-
    frame mesh that module expects, exactly as `build_zan_reference.py` does.
  - `scripts/export_viewer_bundle.summarise()` for every matched entity's atlas
    facts (name, TA, origin/insertion, innervation, functional-compartment PCSA/
    fascicle/pennation/force, actions, notes, targets/supplies) -- this function
    has NO `clinical` key in its own output shape (that block is built entirely
    separately, in `export_viewer_bundle.main()`'s own `compact_clinical()`/
    `bundle["clinical"]`, never called here), so this build cannot leak the
    owner's private clinical layer even by omission-bug: there is nothing to omit.
  - `scripts/export_viewer_bundle.decimate_to`/`decimate_quadric`/`BUDGET`/
    `BUDGET_OVERRIDES`/`SHEET_IDS`/`MAX_VERTS` for decimation, at a global
    `--budget-scale` tuned so the whole page stays under 15 MB (this build ships
    every category in ONE page, unlike `build_zan_reference.py`'s own
    zan_ref_msk/zan_ref_nv split -- see PROJECT_STATE.md Q157).

NEW here (this file's only real logic):
  - ONE binary layout instead of `export_viewer_bundle.py`'s own global-quantum
    int16 format: viewer/zan_atlas.template.html's loader (adapted from the
    owner's preferred build) expects each mesh's positions quantised to uint16
    over that MESH's OWN local bounding box (`min`+`span`, per-mesh, not one
    quantum for the whole page) followed immediately by that mesh's own uint16
    triangle indices, offset from a shared manifest (`vo`/`vc`/`io`/`ic`) -- see
    that template's own `main()` for the exact read-back. Encoded here by
    `pack_mesh()`.
  - LAYER CLASSIFICATION: this project's own 9 atlas categories (bone, muscle,
    tendon, ligament, fascia, bursa, cartilage, nerve, vessel) plus the Z-Anatomy-
    orphan-only categories (organ, lymphatic) map onto the template's fixed
    11-key tissue-layer taxonomy (`classify_layer()`). Tendon is folded into the
    template's own "insertion" layer/preset (relabelled "Tendons" in the
    template) rather than left empty: this project never ships Z-Anatomy's own
    origin/insertion DECAL meshes that layer originally held (they are dropped
    as UI-highlight duplicates by `zan_source.py`/`build_zan_reference.py`, the
    same as every other bundle this project ships), so the slot would otherwise
    carry nothing. A peripheral "nerve" object is further split into the
    template's own "nerve" (peripheral) vs. "cns" (brain/cord/special-sense)
    layers by a small name-substring check (`CNS_NAME_HINTS`) -- this project's
    own atlas has no CNS entities at all (Q141: 9 categories, no organ/CNS/
    lymphatic), so this split only ever affects Z-Anatomy ORPHAN nerve-system
    objects, never a matched entity.
  - PROCEDURAL BADGE: only a structure `apply_correction()` actually warped gets
    `rec.procedural_badge` set here (to that correction's own cited note) --
    unlike `build_zan_reference.py`'s own `--force-badge`, this build never
    stamps a blanket "generic reference model" disclosure onto every one of
    ~2500 structures; that whole-body provenance lives in the sources modal
    (viewer/zan_atlas.template.html's own static text) instead, per Q157's own
    instruction to keep the badge convention scoped to corrected structures.

Usage (the exact Q157 build):
    python3 scripts/zanatomy/build_zan_atlas_viewer.py \\
        --out build/viewer_zan_atlas/atlas_viewer_zan_atlas.html
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from scripts.zanatomy.map_names import load_full_atlas, strip_suffix  # noqa: E402
from scripts.zanatomy import muscle_gap_closure as gap_closure  # noqa: E402
from scripts.zanatomy.zan_source import (  # noqa: E402
    DEFAULT_INVENTORY, DEFAULT_NAMEMAP, DEFAULT_ZAN_DIR, load_extra_links,
    load_source, safe_filename, to_atlas_frame,
)
from scripts.zanatomy.build_zan_reference import (  # noqa: E402
    build_orphan_pool, classify_orphan_category, compute_origin,
)
from scripts.zanatomy.apply_corrections import (  # noqa: E402
    DEFAULT_CORRECTIONS_DIR, apply_correction, load_corrections,
)
from scripts.export_viewer_bundle import (  # noqa: E402
    BUDGET, BUDGET_OVERRIDES, DEFAULT_BUDGET, MAX_VERTS, SHEET_IDS,
    decimate_quadric, decimate_to, load_atlas_records, summarise,
)

TEMPLATE_PATH = REPO / "viewer" / "zan_atlas.template.html"
PINNED_COMMIT = "6c7f9016bd5899ac8edafd31b9900c151df42ed6"
ATTRIBUTION = (
    "Z-Anatomy (CC BY-SA 4.0; github.com/LluisV/Z-Anatomy), derived from "
    "BodyParts3D (CC BY-SA 2.1 Japan, Database Center for Life Science). Pinned "
    f"clone commit {PINNED_COMMIT}. A generic reference body, not segmented from "
    "any specimen and not registered to either of this project's own Visible "
    "Human subjects -- see PROJECT_STATE.md Q142/Q143/Q157."
)

# This project's own 9 atlas categories -> the template's 11-key tissue layer.
# "insertion" is repurposed to carry tendons (see module docstring); every
# other category keeps the template's own original slot. A category this
# project's own atlas never uses (organ, lymphatic -- orphan-only, see
# build_zan_reference.classify_orphan_category) still needs an entry here.
CAT_TO_LAYER = {
    "bone": "bone", "cartilage": "cartilage",
    "ligament": "joint", "bursa": "bursa",
    "muscle": "muscle", "tendon": "insertion", "fascia": "fascia",
    "vessel": "vessel", "organ": "viscera", "lymphatic": "lymph",
}

# A "nerve"-category object (this project's own category, or
# build_zan_reference.classify_orphan_category's Nervous-system default) is
# further split into the template's own "nerve" (peripheral) vs. "cns" (brain,
# spinal cord, special senses) layers by name -- see module docstring. Matched
# only against Z-Anatomy's OWN name (never this project's atlas id), since a
# matched entity's atlas id is always a peripheral-nerve id in this project's
# registry (Q141: no CNS entities exist here at all).
CNS_NAME_HINTS = (
    "brain", "cerebr", "cerebell", "medulla oblongata", "pons", "midbrain",
    "thalamus", "hypothalamus", "spinal cord", "ventricle", "pituitary",
    "hippocamp", "amygdala", "corpus callosum", "basal gangli", "pineal",
    "olfactory bulb", "optic chiasm", "optic nerve", "retina", "cornea",
    "lens", "eyeball", "dorsal root", "rootlet", "dura mater", "arachnoid",
    "pia mater", "meninge", "cauda equina", "choroid plexus",
)


BURSA_HINTS = ("bursa", "tendon sheath", "synovial sheath", "vagina tendinis")
LIGAMENT_HINTS = ("retinacul", "ligament", "interosseous membrane", "joint capsule", "articular capsule")
BRAIN_SURFACE_HINTS = ("gyrus", "gyri", "sulcus", "lobule", "occipital pole", "temporal pole",
                       "frontal pole", "temporal plane", "nucleus of", "horn of spinal")
FASCIA_RE = __import__("re").compile(
    r"\bfascia\b|\bseptum\b|aponeuros|iliotibial tract|linea alba|\bgalea\b|epicranial aponeurosis")
VEIN_HINTS = (" vein", "vein ", "veins", "vena ", "venous", "sinus")


def is_vein(name: str, mesh_id: str) -> bool:
    """Q161: veins draw blue. Name hints, plus this atlas's own `_v` id convention
    (e.g. brachiocephalic_v_r). Dural venous sinuses count as veins."""
    low = " " + name.lower() + " "
    return any(h in low for h in VEIN_HINTS) or mesh_id.endswith("_v") or "_v_" in mesh_id


def classify_layer(cat: str, zanatomy_name: str) -> str:
    low = zanatomy_name.lower()
    # Q161: owner asked for bursae in their own colour, and ligaments/retinacula together in
    # an off-white layer distinct from cartilage -- Z-Anatomy files many bursae and all
    # retinacula under its Muscular system, so name hints decide before the category does.
    if cat not in ("vessel", "nerve", "bone") and any(h in low for h in BURSA_HINTS):
        return "bursa"
    if cat not in ("vessel", "nerve", "bone", "cartilage") and any(h in low for h in LIGAMENT_HINTS):
        return "joint"
    # fascial sheets filed as "muscle" (atlas category or Z-Anatomy's Muscular system) drew as
    # opaque muscle-coloured shells over the real muscles; whole-word so "Tensor fasciae latae"
    # stays a muscle
    if cat in ("muscle", "fascia", "tendon", "ligament") and FASCIA_RE.search(low):
        return "fascia"
    if cat == "nerve" and "lacrimal" in low:
        return "viscera"
    if cat == "nerve" and any(h in low for h in BRAIN_SURFACE_HINTS):
        return "cns"
    if cat == "nerve":
        low = zanatomy_name.lower()
        if any(h in low for h in CNS_NAME_HINTS):
            return "cns"
        return "nerve"
    return CAT_TO_LAYER.get(cat, "viscera")


def side_code(raw) -> str:
    return {"right": "r", "left": "l"}.get(raw, "m")


def _load_raw_mesh(zan_dir: Path, system: str, name: str):
    """This build's own Z-Anatomy npz -> (vertices, faces) in this project's
    atlas frame (mm), WITHOUT the hip-origin shift build_zan_reference.py
    applies -- apply_correction()'s own lateral_epicondyle_y() measurement
    needs the same pre-shift frame it is always called in, and this function
    is the single place both the matched and the orphan path get their raw
    mesh from, so that rule cannot be accidentally violated by one path but
    not the other."""
    path = Path(zan_dir) / system / f"{safe_filename(name)}.npz"
    d = np.load(path)
    return to_atlas_frame(d["vertices_mm"]).astype(np.float64), d["faces"].astype(np.int64)


def pack_mesh(v: np.ndarray, f: np.ndarray, byte_offset: int):
    """This template's own per-mesh binary layout: `vc` positions quantised to
    uint16 over this mesh's OWN local bbox (`min`+`span`), then `ic` triangles
    as uint16 indices -- see module docstring. Returns
    (manifest_fields, packed_bytes)."""
    vmin = v.min(axis=0)
    vmax = v.max(axis=0)
    span = vmax - vmin
    span_safe = np.where(span <= 1e-9, 1.0, span)  # a degenerate (near-planar) axis must not divide by ~0
    q = np.clip(np.rint((v - vmin) / span_safe * 65535.0), 0, 65535).astype("<u2")
    idx = f.astype("<u2")
    pos_bytes = q.tobytes()
    idx_bytes = idx.tobytes()
    fields = {
        "vo": byte_offset, "vc": int(len(v)),
        "io": byte_offset + len(pos_bytes), "ic": int(len(f)),
        "min": [round(float(x), 3) for x in vmin],
        "span": [round(float(x), 3) for x in span],
    }
    return fields, pos_bytes + idx_bytes


def weld(v: np.ndarray, f: np.ndarray):
    """Merge coincident vertices (Z-Anatomy exports split vertices at UV/normal seams), so
    quadric decimation sees one connected surface instead of seam-separated patches."""
    u, inv = np.unique(np.round(v, 4), axis=0, return_inverse=True)
    return u, inv.reshape(-1)[f]


def orient_outward(v: np.ndarray, f: np.ndarray):
    """Q160: make every piece's triangle winding consistent and, where the piece is closed,
    outward-facing. Measured on the Q159 build: 1,046 of 1,930 bone/muscle/tendon/nerve/vessel
    source meshes had a negative signed volume (inside-out), 557/826 of them on the right side
    (mirrored copies in the Z-Anatomy file). The viewer derives normals from the winding, so an
    inside-out muscle was drawn as its own far inner wall: muscles looked thin with gaps between
    them and deeper vessels showed through. After this: 461/471 muscles, 300/304 bones outward;
    the rest are open sheets/tubes the viewer's two-sided lighting handles."""
    import trimesh
    tm = trimesh.Trimesh(v, f, process=False)
    trimesh.repair.fix_normals(tm, multibody=True)
    return np.asarray(tm.vertices, np.float64), np.asarray(tm.faces, np.int64)


def n_pieces(f: np.ndarray, nv: int) -> int:
    """Connected surface pieces (triangles sharing a vertex)."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    f = np.asarray(f, np.int64)
    e = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
    _n, lab = connected_components(coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(nv, nv)),
                                   directed=False)
    return len(np.unique(lab[f[:, 0]]))


def decimate(v: np.ndarray, f: np.ndarray, mesh_id: str, cat: str, scale: float, prepped: bool = False):
    """Q159: quadric edge-collapse first for EVERY mesh (it never splits a surface), vertex
    clustering only as a fallback. Measured on the full Q157 build at the same budgets:
    clustering added components to 340/2570 structures (123 nerves, 79 vessels, 6 muscles
    split into pieces), quadric to 32 (0 muscles) -- data/derived/Q159_decimation_continuity.json."""
    budget = max(150, int(BUDGET_OVERRIDES.get(mesh_id, BUDGET.get(cat, DEFAULT_BUDGET)) * scale))
    wv, wf = (v, f) if prepped else orient_outward(*weld(v, f))
    src_pieces = n_pieces(wf, len(wv))
    for attempt in range(4):  # continuity guard: never ship more pieces than the source has
        q = decimate_quadric(wv, wf, budget * 2 ** attempt)
        if q is None or not len(q[1]) or len(q[0]) > MAX_VERTS:
            break
        if n_pieces(q[1], len(q[0])) <= src_pieces or attempt == 3:
            return q
    dv, df, _cell = decimate_to(wv, wf, budget)
    if len(df) == 0:
        dv, df = v, f
    if len(dv) > MAX_VERTS:
        dv, df, _cell = decimate_to(v, f, min(budget, MAX_VERTS - 1))
    return dv, df


DECAL_SUFFIXES = ("ol", "or", "el", "er")  # Z-Anatomy origin/insertion highlight decals


def rescue_unshipped(inventory: dict, namemap: dict, matched: dict, orphans: dict) -> dict:
    """Q161: every Z-Anatomy object the name map matched (exact/confident) but that
    load_source() then rejected -- wrong-system or wrong-side candidate, tiny sub-part
    of a multi-part id, a cross-category name filter hit -- was shipped by NOBODY:
    build_orphan_pool() only takes ambiguous/unmatched/grouped entries. That silently
    dropped e.g. the medial/lateral patellar retinacula, lumbricals of the hand, dorsal
    fascia of the hand. Ship each such object as its own mesh (largest copy per
    system/side/base name, decals skipped, never a second copy of anything shipped)."""
    objs_by_name = {o["name"]: o for o in inventory["objects"]}
    consumed = set()
    for rec in matched.values():
        consumed.update(rec.get("zanatomy_parts") or [])
    consumed.update(meta["mesh_name"] for meta in orphans.values())
    consumed_keys = set()
    for name in consumed:
        o = objs_by_name.get(name)
        if o:
            consumed_keys.add((o.get("side"), strip_suffix(name)))
    muscular_bases = {strip_suffix(o["name"]) for o in inventory["objects"] if o["system"] == "Muscular"}
    groups: dict = {}
    for e in namemap["entries"]:
        if e["status"] not in ("exact", "confident") or e["zanatomy_name"] in consumed:
            continue
        o = objs_by_name.get(e["zanatomy_name"])
        if o is None or o["face_count"] == 0 or o.get("suffix") in DECAL_SUFFIXES:
            continue
        base = strip_suffix(e["zanatomy_name"])
        if (o.get("side"), base) in consumed_keys:
            continue  # a UI-highlight / other-system copy of something already shipped
        if o["system"] == "Skeletal" and (base in muscular_bases or not any(
                w in base.lower() for w in ("cartilage", "sinus", "bone"))):
            continue  # a muscle's attachment footprint drawn on the bone, not the muscle
        key = (o["system"], o.get("side"), base)
        groups.setdefault(key, []).append((o, e.get("atlas_id")))
    used = set(orphans)
    out = {}
    for (system, side, base), cands in sorted(groups.items(), key=lambda kv: str(kv[0])):
        o, aid = max(cands, key=lambda c: c[0]["vertex_count"])
        slug = "".join(ch if ch.isalnum() else "_" for ch in base.lower()).strip("_")
        while "__" in slug:
            slug = slug.replace("__", "_")
        stable = "zan_" + slug + {"right": "_r", "left": "_l"}.get(side, "")
        n = 2
        while stable in used:
            stable = f"zan_{slug}{ {'right': '_r', 'left': '_l'}.get(side, '') }_{n}".replace(" ", "")
            n += 1
        used.add(stable)
        cat = "cartilage" if "cartilage" in base.lower() else classify_orphan_category(base, system)
        out[stable] = {"name": base, "system": system, "side": side, "atlas_id": aid,
                       "category": cat, "mesh_name": o["name"]}
    return out


# Q162: left-side Z-Anatomy objects the contralateral (mirror) audit found broken, replaced by the
# mirror image (x -> -x about the measured mirror plane x = 0) of their right-side counterpart.
# Measured on the source (scratch audit of 823 L/R pairs, 2026-09-28): the left iliopsoas fascia lies
# a median 17.2 mm from the left psoas major (right side: 2.8 mm) -- displaced ~16 mm medially and
# ~10 mm up; the left iliopectineal arch is a 23-vertex stub (right: 142); the left zonular fibres
# span 0.3 mm (right: a 15 mm ring of 97 fibres).
CONTRA_REPAIRS = {
    "zan_iliopsoas_fascia_l": ("zan_iliopsoas_fascia_r", "left source object displaced ~19 mm off the psoas"),
    "zan_iliopectineal_arch_l": ("zan_iliopectineal_arch_r", "left source object is a 23-vertex stub"),
    "zan_zonular_fibres_l": ("zan_zonular_fibres_r", "left source object is a 0.3 mm stub"),
}


LAST_REPORTS: dict = {}


def _mirror_pairs(pending: list[dict]):
    by_id = {p["mesh_id"]: p for p in pending}
    return [(by_id[k], by_id[k[:-2] + "_r"]) for k in sorted(by_id)
            if k.endswith("_l") and k[:-2] + "_r" in by_id]


def repair_contralateral(pending: list[dict]) -> dict:
    """Mirror audit of every L/R pair (chamfer of left vs mirrored right, pieces, volume), then the
    CONTRA_REPAIRS replacements, each measured and badged."""
    from scipy.spatial import cKDTree
    flagged, repaired, missing = [], [], []
    pairs = _mirror_pairs(pending)
    for L, R in pairs:
        rv = R["v"] * np.array([-1.0, 1.0, 1.0])
        dl, _ = cKDTree(rv).query(L["v"])
        dr, _ = cKDTree(L["v"]).query(rv)
        ch = float((dl.mean() + dr.mean()) / 2)
        pl, pr = n_pieces(L["f"], len(L["v"])), n_pieces(R["f"], len(R["v"]))
        if ch > 2.0 or pl != pr:
            flagged.append({"id": L["mesh_id"][:-2], "cat": L["cat"], "chamfer_mm": round(ch, 2),
                            "pieces_l": pl, "pieces_r": pr, "verts_l": len(L["v"]), "verts_r": len(R["v"])})
    by_id = {p["mesh_id"]: p for p in pending}
    for tgt, (src, why) in CONTRA_REPAIRS.items():
        if tgt not in by_id or src not in by_id:
            missing.append(tgt)
            continue
        T, S = by_id[tgt], by_id[src]
        mv = S["v"] * np.array([-1.0, 1.0, 1.0])
        d, _ = cKDTree(mv).query(T["v"])
        T["v"], T["f"] = mv.copy(), S["f"][:, ::-1].copy()
        T["notes"].append(
            f"Q162 contralateral repair: {why}; replaced by the mirror image of the right-side Z-Anatomy "
            f"object (mirror plane x = 0, measured on 111 bone pairs); the replaced geometry differed by "
            f"a median {float(np.median(d)):.1f} mm.")
        repaired.append({"id": tgt, "from": src, "reason": why, "median_change_mm": round(float(np.median(d)), 1)})
    return {"pairs_audited": len(pairs), "flagged": flagged, "repaired": repaired, "repair_targets_missing": missing}


# objects Z-Anatomy files under its Muscular system that are not muscle bellies (eyelid tarsal
# plates, the orbit's tendinous ring and trochlea, digital fibrous sheaths, the iliopectineal arch,
# zonular fibres): obstacles for the gap closure, never moved themselves
NOT_MUSCLE_HINTS = ("tarsus", "tendinous ring", "trochlea", "fibrous sheath", "iliopectineal arch", "zonular")


def close_muscle_gaps(pending: list[dict]) -> dict:
    """Q162: gap closure over every muscle-layer mesh (see muscle_gap_closure.py for the rule and
    its citations); tendons are closed onto, everything else is an obstacle."""
    movable, tendons, obstacles = {}, {}, {}
    for p in pending:
        layer = classify_layer(p["cat"], p["zanatomy_name"] or p["display_name"])
        key = p["mesh_id"]
        low = (p["zanatomy_name"] or p["display_name"]).lower()
        if p["cat"] == "muscle" and layer == "muscle" and not any(h in low for h in NOT_MUSCLE_HINTS):
            movable[key] = (p["v"], p["f"])
        elif p["cat"] == "tendon" and layer == "insertion":
            tendons[key] = (p["v"], p["f"])
        else:
            obstacles[key] = (p["v"], p["f"])

    def summary(a):
        g = np.concatenate([x["gaps"] for x in a.values()]) if a else np.zeros(0)
        nv = sum(x["n"] for x in a.values())
        return {"vertices": nv, "median_gap_mm": round(float(np.median(g)), 2) if len(g) else None,
                "frac_vertices_gap_gt_1_25mm": round(float((g > 1.25).sum() / nv), 4),
                "frac_vertices_inside_other_muscle": round(float(sum(x["inside"] for x in a.values()) / nv), 4)}

    before = summary(gap_closure.audit(movable, tendons, obstacles))
    out = gap_closure.close_gaps(movable, tendons, obstacles, log=print)
    after_meshes = {k: (out[k][0], movable[k][1]) for k in movable}
    after = summary(gap_closure.audit(after_meshes, tendons, obstacles))
    by_id = {p["mesh_id"]: p for p in pending}
    changed = 0
    per_mesh = {}
    for k, (v_new, st) in out.items():
        per_mesh[k] = st
        if st["moved_frac"] < 0.01 and st["shift_max_mm"] < 0.2:
            continue
        changed += 1
        by_id[k]["v"] = v_new
        by_id[k]["notes"].append(
            f"Q162 gap closure: surface moved outward along its normals toward neighbouring muscles, "
            f"down to a {gap_closure.TARGET_GAP_MM:.1f} mm interface ({gap_closure.CITATIONS}); never toward "
            f"bone, nerves, vessels or fascia. {st['moved_frac']:.0%} of vertices moved, median "
            f"{st['shift_median_mm']} mm, max {st['shift_max_mm']} mm; volume {st['volume_cm3_before']} -> "
            f"{st['volume_cm3_after']} cm3. Z-Anatomy source geometry otherwise unchanged.")
    return {"rule": "muscle_gap_closure.py", "target_gap_mm": gap_closure.TARGET_GAP_MM,
            "max_shift_mm": gap_closure.MAX_SHIFT_MM, "citations": gap_closure.CITATIONS,
            "movable_muscles": len(movable), "changed_muscles": changed,
            "before": before, "after": after, "per_mesh": per_mesh}


def build(*, zan_dir: Path, inventory_path: Path, namemap_path: Path,
          corrections_dir: Path, budget_scale: float, category_scale: dict | None = None,
          close_gaps: bool = True):
    inventory = json.loads(Path(inventory_path).read_text())
    namemap = json.loads(Path(namemap_path).read_text())

    matched = load_source(inventory_path=inventory_path, namemap_path=namemap_path, zan_dir=zan_dir)

    # Q158b (lead review of Q158's first cut): `matched` is exactly
    # `map_names.py`'s own exact/confident matches (plus `_ATLAS_ID_OVERRIDE`)
    # again, untouched by Q158's curated links -- so it can never overlap with
    # `build_orphan_pool`'s own ambiguous/unmatched/grouped selection below (a
    # namemap entry has exactly one status), and no double-count filtering is
    # needed here any more. `build_orphan_pool` runs unfiltered, exactly as
    # before Q157/Q158 -- see the module docstring for why Q158's links are
    # metadata-only now (a `part_of` reference on the object's OWN orphan mesh,
    # attached just below), never a second, merged copy of anything.
    orphans, dropped_dupe, zero_face = build_orphan_pool(inventory, namemap)
    rescued = rescue_unshipped(inventory, namemap, matched, orphans)
    origin, origin_report = compute_origin(zan_dir)
    corrections = load_corrections(corrections_dir)
    atlas_records = load_atlas_records()
    id_to_cat = {e.entity_id: e.category for e in load_full_atlas()}

    # Q158b: parent links (Z-Anatomy name -> the coarser/parent atlas entity
    # this project's own registry files it under) -- read-only metadata, never
    # used to merge geometry (see zan_source.load_extra_links()'s own
    # docstring). Keyed by the exact raw Z-Anatomy name, which is also what
    # `build_orphan_pool` stores as that orphan's own `mesh_name`.
    parent_links_by_zname = {l["zanatomy_name"]: l for l in load_extra_links()}
    parent_linked_count = 0
    unresolved_parent_links: list[str] = []

    meshes: list[dict] = []
    bin_chunks: list[bytes] = []
    byte_off = 0
    seen_ids: set[str] = set()
    counts_by_layer: Counter = Counter()
    counts_by_category: Counter = Counter()
    corrected_ids: list[str] = []
    matched_with_record = 0

    pending: list[dict] = []

    def emit(mesh_id: str, display_name: str, side_raw, cat: str, v_raw: np.ndarray, f: np.ndarray,
              rec_override=None, zanatomy_name: str | None = None, parent_link=None):
        """Q162: collect first (corrected, origin-shifted, welded, outward-oriented), so the
        whole-body steps below (contralateral repair, muscle gap closure) see every structure."""
        if mesh_id in seen_ids:
            raise ValueError(f"duplicate atlas id emitted twice: {mesh_id}")
        seen_ids.add(mesh_id)
        warped, note = apply_correction(mesh_id, v_raw, zan_dir, corrections)
        v, fw = orient_outward(*weld(warped - origin, f))
        pending.append(dict(mesh_id=mesh_id, display_name=display_name, side_raw=side_raw, cat=cat, v=v, f=fw,
                            rec_override=rec_override, zanatomy_name=zanatomy_name, parent_link=parent_link,
                            notes=[note] if note else []))

    def finish(mesh_id: str, display_name: str, side_raw, cat: str, v: np.ndarray, f: np.ndarray,
               rec_override=None, zanatomy_name: str | None = None, parent_link=None, notes=()):
        nonlocal byte_off, matched_with_record, parent_linked_count
        note = " ".join(notes)
        dv, df = decimate(v, f, mesh_id, cat, (category_scale or {}).get(cat, budget_scale), prepped=True)

        fields, packed = pack_mesh(dv, df, byte_off)
        byte_off += len(packed)
        bin_chunks.append(packed)

        layer = classify_layer(cat, zanatomy_name or display_name)
        counts_by_layer[layer] += 1
        counts_by_category[cat] += 1

        entry = {"name": display_name, "id": mesh_id, "side": side_code(side_raw), "sys": layer, **fields}
        if layer == "vessel" and is_vein(zanatomy_name or display_name, mesh_id):
            entry["vt"] = "v"
        rec_out = {}
        if rec_override is not None:
            folder, real_rec = rec_override
            rec_out = summarise(folder, real_rec, {})
        elif parent_link is not None:
            # Q158b: this object stays its OWN separate mesh (never merged into
            # the parent's geometry) -- it just borrows the parent atlas
            # entity's own cited facts for display, clearly labelled as the
            # parent's via `part_of`/`part_of_id`, never presented as this
            # specific piece's own independently-verified record.
            parent_id, parent_folder, parent_real_rec = parent_link
            parent_facts = summarise(parent_folder, parent_real_rec, {})
            rec_out = dict(parent_facts)
            rec_out["part_of_id"] = parent_id
            rec_out["part_of"] = parent_facts.get("name") or parent_id.replace("_", " ")
            parent_linked_count += 1
        if note:
            rec_out = dict(rec_out)
            rec_out["procedural_badge"] = note
            corrected_ids.append(mesh_id)
        if rec_out:
            entry["rec"] = rec_out
        if rec_override is not None:
            matched_with_record += 1
        meshes.append(entry)

    for aid, rec in sorted(matched.items()):
        cat = rec["cat"]
        base_atlas_id = rec.get("base_atlas_id")
        if base_atlas_id:
            rec_override = atlas_records.get(base_atlas_id)
            base_name = rec.get("base_name") or base_atlas_id
            side_word = {"_r": "right", "_l": "left"}.get(aid[-2:])
            display_name = f"{base_name} ({side_word})" if side_word else base_name
        else:
            rec_override = atlas_records.get(aid)
            real_rec = rec_override[1] if rec_override else None
            display_name = (real_rec or {}).get("name_common") or (real_rec or {}).get("name") \
                or aid.replace("_", " ")
        zanatomy_names = rec.get("zanatomy_parts") or []
        emit(aid, display_name, rec.get("side"), cat, rec["v"].astype(np.float64), rec["f"].astype(np.int64),
             rec_override=rec_override, zanatomy_name=zanatomy_names[0] if zanatomy_names else display_name)

    for stable, meta in sorted(orphans.items()):
        v_raw, f = _load_raw_mesh(zan_dir, meta["system"], meta["mesh_name"])
        parent_link = None
        link = parent_links_by_zname.get(meta["mesh_name"])
        if link:
            parent_pair = atlas_records.get(link["atlas_id"])
            if parent_pair:
                parent_link = (link["atlas_id"], parent_pair[0], parent_pair[1])
            else:
                unresolved_parent_links.append(meta["mesh_name"])
        emit(stable, meta["name"], meta["side"], meta["category"], v_raw, f,
             zanatomy_name=meta["name"], parent_link=parent_link)

    # Q161: matched-but-rejected objects (see rescue_unshipped) -- own geometry, own id,
    # linked to the atlas entity the name map matched them to (as "part of").
    for stable, meta in sorted(rescued.items()):
        if stable in seen_ids:
            continue
        v_raw, f = _load_raw_mesh(zan_dir, meta["system"], meta["mesh_name"])
        parent_pair = atlas_records.get(meta["atlas_id"]) if meta["atlas_id"] else None
        parent_link = (meta["atlas_id"], parent_pair[0], parent_pair[1]) if parent_pair else None
        emit(stable, meta["name"], meta["side"], meta["category"], v_raw, f,
             zanatomy_name=meta["name"], parent_link=parent_link)

    # Q162 (owner: "look on the contralateral side and other accurate models and medical articles"):
    # (1) replace the few left-side source objects the mirror audit found broken by the mirrored
    # right side; (2) close the artificial gaps between neighbouring muscles to a cited 1 mm interface.
    contra_report = repair_contralateral(pending)
    gap_report = close_muscle_gaps(pending) if close_gaps else {"skipped": True}
    LAST_REPORTS["contralateral"] = contra_report
    LAST_REPORTS["gap_closure"] = gap_report
    for item in pending:
        finish(**item)

    # a Q158 link whose own zanatomy_name never turned up as any orphan's
    # `mesh_name` (build_orphan_pool's own highlight-duplicate dedup picked a
    # DIFFERENT representative for that name's (system, side, base) group, or
    # the object was itself dropped as a zero-face annotation curve) -- never
    # a fatal error, just means that one link finds nothing to attach to.
    used_link_names = {meta["mesh_name"] for meta in orphans.values()} & set(parent_links_by_zname)
    unmatched_parent_links = sorted(set(parent_links_by_zname) - used_link_names)

    # sanity this build's own invariants (also re-checked by
    # tests/test_build_zan_atlas_viewer.py against the real, committed output):
    ids = [m["id"] for m in meshes]
    assert len(ids) == len(set(ids)), "exporter produced a duplicate id"
    for m in meshes:
        assert "clinical" not in (m.get("rec") or {}), f"{m['id']} carries a clinical key"
    # Q158b: never merge -- every shipped mesh's own geometry must come from
    # exactly the ONE Z-Anatomy object it is named for, so a parent-linked
    # structure carries no `zanatomy_parts` list of its own (that concept only
    # exists for `matched`, where several real sub-parts are deliberately
    # concatenated) and every orphan mesh_name is used by at most one shipped id.
    mesh_names_seen = Counter(meta["mesh_name"] for meta in orphans.values())
    dup_mesh_names = [n for n, c in mesh_names_seen.items() if c > 1]
    assert not dup_mesh_names, f"two shipped structures share one Z-Anatomy source object: {dup_mesh_names}"

    manifest = {
        "attribution": ATTRIBUTION,
        "totals": {
            "meshes": len(meshes),
            "by_layer": dict(counts_by_layer),
            "by_category": dict(counts_by_category),
            "matched_entities": len(matched),
            "matched_with_atlas_record": matched_with_record,
            "orphan_structures": len(orphans),
            "rescued_matched_but_unshipped": sorted(rescued),
            "orphan_dropped_as_ui_highlight_duplicate": dropped_dupe,
            "orphan_dropped_as_zero_face_annotation_curve": zero_face,
            # Q158b: reported SEPARATELY from matched_entities, per lead review --
            # a "direct" link (matched_entities, this project's own entity id IS
            # the shipped mesh) is a different, stronger claim than a "parent"
            # link (this Z-Anatomy object stays its own separate, unmatched mesh
            # and only borrows its parent atlas entity's cited facts for display).
            "direct_atlas_links": len(matched),
            "parent_linked_structures": parent_linked_count,
            "parent_links_with_no_orphan_mesh": unmatched_parent_links,
            "parent_links_with_no_atlas_record": unresolved_parent_links,
            "corrected_ids": corrected_ids,
            "contralateral_repairs": contra_report,
            "muscle_gap_closure": {k: v for k, v in gap_report.items() if k != "per_mesh"},
        },
        "meshes": meshes,
    }
    blob = b"".join(bin_chunks)
    return manifest, blob, origin_report


# Q159: the published hi-res build (with --external-bin): full musculoskeletal budgets, then
# nerves > vessels > organs/lymph, ~2.9M triangles / ~26 MB geometry (vs 1.1M in one 15 MB page).
HIRES_CATEGORY_SCALE = {"muscle": 1.0, "bone": 1.0, "tendon": 1.0, "ligament": 1.0, "cartilage": 1.0,
                        "fascia": 1.0, "bursa": 1.0, "nerve": 0.8, "vessel": 0.5, "organ": 0.3,
                        "lymphatic": 0.3}
# The artifact host serves no raw .bin type, so geometry ships as base64 .txt (16 MB text-file cap):
# 11 MB of binary -> ~14.7 MB of base64 per file.
BIN_FILE_MAX = 11_000_000


def split_blob(blob: bytes, stem: str, max_bytes: int = BIN_FILE_MAX):
    """Q159: cut the geometry into sibling files (even-length, so uint16 views stay aligned
    across the loader's concatenation). Returns [(published_path, bytes)]."""
    step = max_bytes - (max_bytes % 2)
    return [(f"{stem}_geo_{i:02d}.txt", blob[o:o + step]) for i, o in enumerate(range(0, len(blob), step))]


def render_html(manifest: dict, blob: bytes, bin_files: list | None = None) -> str:
    """Self-contained page (geometry inlined as base64) unless `bin_files` names the sibling
    binary files the loader should fetch instead ([{path, bytes}], in blob order)."""
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    manifest_json = json.dumps(manifest, separators=(",", ":")).replace("</", "<\\/")
    b64 = "" if bin_files else base64.b64encode(blob).decode("ascii")
    if "</script" in b64.lower():
        raise SystemExit("base64 payload contains a script terminator")
    html = template.replace("__MANIFEST_JSON__", manifest_json, 1)
    html = html.replace("__BIN_FILES_JSON__", json.dumps(bin_files or []), 1)
    html = html.replace("__BIN_B64__", b64, 1)
    return html


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--inventory", default=str(DEFAULT_INVENTORY))
    ap.add_argument("--namemap", default=str(DEFAULT_NAMEMAP))
    ap.add_argument("--zan-dir", default=str(DEFAULT_ZAN_DIR))
    ap.add_argument("--corrections-dir", default=str(DEFAULT_CORRECTIONS_DIR))
    ap.add_argument("--budget-scale", type=float, default=0.22,
                    help="multiplies every category triangle budget; tuned so the WHOLE body "
                         "(every category in one page, unlike build_zan_reference.py's own "
                         "msk/nv split) stays under the 15 MB page cap -- see PROJECT_STATE.md Q157.")
    ap.add_argument("--category-scale", action="append", default=[], metavar="CAT=SCALE",
                    help="per-category override of --budget-scale (repeatable), e.g. muscle=1.0")
    ap.add_argument("--external-bin", action="store_true",
                    help="Q159: write geometry as sibling base64 <out-stem>_geo_NN.txt files (each under the "
                         "artifact host's 16 MB text-file cap) instead of inlining it, so the page is "
                         "no longer the resolution ceiling; publish them with the page.")
    ap.add_argument("--no-gap-closure", action="store_true", help="skip the Q162 muscle gap closure")
    ap.add_argument("--q162-report", default=str(REPO / "data" / "derived" / "Q162_gap_closure_contralateral.json"))
    ap.add_argument("-o", "--out", default="build/viewer_zan_atlas/atlas_viewer_zan_atlas.html")
    ap.add_argument("--report", default=str(REPO / "data" / "derived" / "Q157_zan_atlas_report.json"))
    args = ap.parse_args(argv)

    category_scale = dict(HIRES_CATEGORY_SCALE) if args.external_bin and not args.category_scale else {}
    for item in args.category_scale:
        cat, _, val = item.partition("=")
        category_scale[cat.strip()] = float(val)

    manifest, blob, origin_report = build(
        zan_dir=Path(args.zan_dir), inventory_path=Path(args.inventory), namemap_path=Path(args.namemap),
        corrections_dir=Path(args.corrections_dir), budget_scale=args.budget_scale,
        category_scale=category_scale, close_gaps=not args.no_gap_closure)
    Path(args.q162_report).write_text(json.dumps(LAST_REPORTS, indent=1, default=float))

    out_path = REPO / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    bin_files = None
    if args.external_bin:
        bin_files = []
        for name, chunk in split_blob(blob, out_path.stem):
            (out_path.parent / name).write_text(base64.b64encode(chunk).decode("ascii"), encoding="ascii")
            bin_files.append({"path": name, "bytes": len(chunk), "enc": "base64"})
    html = render_html(manifest, blob, bin_files)
    out_path.write_text(html, encoding="utf-8")

    report = {
        "source": (
            "Q157 (2026-09-25): builds ONE self-contained, full-body Z-Anatomy reference "
            "viewer (every non-excluded category in one page) reproducing the owner's "
            "preferred August viewer's UI, fed by this project's own Z-Anatomy pipeline "
            "(corrections + atlas records included, clinical excluded by construction -- "
            "see scripts/zanatomy/build_zan_atlas_viewer.py). "
        ),
        "origin": origin_report,
        "budget_scale": args.budget_scale,
        "category_scale": category_scale,
        "decimation": "Q159: quadric edge-collapse on welded meshes, vertex clustering fallback",
        "bin_files": bin_files or "inline base64",
        "binary_bytes": len(blob),
        "html_bytes": len(html),
        **manifest["totals"],
    }
    Path(args.report).write_text(json.dumps(report, indent=1))

    print(f"meshes: {manifest['totals']['meshes']}  "
          f"(direct-linked {manifest['totals']['direct_atlas_links']}, "
          f"orphan {manifest['totals']['orphan_structures']} "
          f"[{manifest['totals']['parent_linked_structures']} parent-linked])")
    print("by layer:", manifest["totals"]["by_layer"])
    print("by category:", manifest["totals"]["by_category"])
    print(f"corrected ids: {manifest['totals']['corrected_ids']}")
    print(f"binary {len(blob)/1e6:.2f} MB -> html {len(html)/1e6:.2f} MB -> {out_path}")
    print(f"wrote {args.report}")
    if bin_files:
        print(f"external geometry: {[(b['path'], round(b['bytes']/1e6, 2)) for b in bin_files]}")
    if len(html) > 15_000_000:
        print(f"WARNING: {len(html)/1e6:.2f} MB exceeds the 15 MB page budget; "
              f"re-run with a smaller --budget-scale", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
