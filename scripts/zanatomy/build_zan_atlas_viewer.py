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

# Q186 (owner: "zanatomy models being missing few things as penile skin, face skin, etc."): the
# Z-Anatomy SKIN is "Regions of human body100.fbx" -- region surface patches (face, scalp, trunk,
# limbs, perineum incl. the penile/scrotal skin inside "Urogenital region"), nails and hair. Q141's
# extractor had dropped the whole file as a "diagram overlay"; it is now extracted as the Integument
# system into its own inventory (see scripts/zanatomy/extract_fbx.py). The template has no skin layer
# yet: until it lists one (k:"skin"), skin draws in the fascia layer (translucent, tan, 15 % default).
DEFAULT_INTEG_INVENTORY = REPO / "data" / "derived" / "zanatomy_integument_inventory.json"
SKIN_LAYER = "skin" if 'k:"skin"' in TEMPLATE_PATH.read_text(encoding="utf-8") else "fascia"
CAT_TO_LAYER["skin"] = SKIN_LAYER
# hair is extracted and inventoried but not shipped by default: the template colours by layer, so it
# would draw as a lumpy skin-coloured cap over the scalp patches (--with-hair ships it)
HAIR_NAMES = ("Hairs of head", "Hairs of eyebrow", "Eyelashes", "Pubic hairs")
# male external genitalia skin (penis + scrotum are part of the Urogenital region patches) and the
# pubic hair wrapped round the penile root: never on the female variant (Z-Anatomy has no vulva)
MALE_ONLY_SKIN = frozenset({"zan_skin_urogenital_region_l", "zan_skin_urogenital_region_r",
                            "zan_skin_pubic_hairs"})


def skin_pool(integ_inventory: dict, with_hair: bool = False) -> dict:
    """{zan_skin_<slug>[_r|_l]: meta} for every extracted Integument object (one object -> one id)."""
    out = {}
    for o in integ_inventory["objects"]:
        base = strip_suffix(o["name"])
        if base in HAIR_NAMES and not with_hair:
            continue
        slug = "".join(ch if ch.isalnum() else "_" for ch in base.lower()).strip("_")
        while "__" in slug:
            slug = slug.replace("__", "_")
        sid = "zan_skin_" + slug + {"right": "_r", "left": "_l"}.get(o.get("side"), "")
        if sid in out:
            raise ValueError(f"two Integument objects map to {sid}")
        is_region = not any(k in base for k in ("Nail", "Perionyx")) and base not in HAIR_NAMES
        out[sid] = {"name": f"{base} (skin)" if is_region else base, "system": "Integument",
                    "side": o.get("side"), "category": "skin", "mesh_name": o["name"]}
    return out

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
    if cat == "skin":
        return SKIN_LAYER
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


def outward_if_closed(v: np.ndarray, f: np.ndarray) -> np.ndarray:
    """Q186: the audit found 6-9 CLOSED shipped meshes (liver, lung lobes, gyri) still inside-out after
    orient_outward + decimation; flip a closed mesh whose signed volume is negative."""
    f = np.asarray(f, np.int64)
    if not len(f):
        return f
    e = np.sort(np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]]), axis=1)
    _, c = np.unique(e, axis=0, return_counts=True)
    if not (c == 2).all():
        return f
    a, b, cc = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    return f[:, ::-1].copy() if np.einsum("ij,ij->i", a, np.cross(b, cc)).sum() < 0 else f


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
# Q186: the full decal family (.ol/.el/.o1l/.e2r/... -- attachment footprints on the bone and highlight copies)
DECAL_RE = __import__("re").compile(r"\.[oe]\d*[lr]$")
_VEIN_WORD = __import__("re").compile(r"\bveins?\b", __import__("re").I)
_ARTERY_WORD = __import__("re").compile(r"\barter", __import__("re").I)


def _is_artery_id(aid: str) -> bool:
    return bool(__import__("re").search(r"(_a|_aa)(_[lr])?$|_a_", aid))


def _is_vein_id(aid: str) -> bool:
    return bool(__import__("re").search(r"_v(_[lr])?$|_v_", aid))


def _slug(base: str) -> str:
    slug = "".join(ch if ch.isalnum() else "_" for ch in base.lower()).strip("_")
    while "__" in slug:
        slug = slug.replace("__", "_")
    return slug


def split_vessel_mismatches(matched: dict, orphans: dict) -> list[dict]:
    """Q186: a matched artery id built only from objects Z-Anatomy names as veins (or the reverse) is a
    name-map error (measured: `superior_phrenic_a_r` <- "Right superior phrenic vein"). Ship the object
    as its own orphan under its own Z-Anatomy name instead, with no atlas link."""
    moved = []
    for aid in sorted(matched):
        parts = matched[aid].get("zanatomy_parts") or []
        if not parts:
            continue
        wrong = ((_is_artery_id(aid) and all(_VEIN_WORD.search(n) for n in parts)) or
                 (_is_vein_id(aid) and all(_ARTERY_WORD.search(n) and not _VEIN_WORD.search(n) for n in parts)))
        if not wrong or len(parts) != 1:
            continue
        rec = matched.pop(aid)
        name = parts[0]
        base = strip_suffix(name)
        side = rec.get("side") if rec.get("side") in ("left", "right") else None
        stable = "zan_" + _slug(base) + {"right": "_r", "left": "_l"}.get(side, "")
        while stable in orphans:
            stable += "_b"
        orphans[stable] = {"name": base, "system": "CardioVascular", "side": side, "category": "vessel",
                           "mesh_name": name}
        moved.append({"was": aid, "now": stable, "source": name})
    return moved


def curate_orphans(orphans: dict, inventory: dict) -> tuple[dict, dict]:
    """Q186 build defects found by scripts/zanatomy/zan_inventory_audit.py, fixed here (one rule each):
    (a) an orphan whose only source is an origin/insertion DECAL (e.g. "Temporalis muscle.o2l", a bone
        footprint) shipped as a second "Temporalis muscle" -- decals never ship (same rule as everywhere);
    (b) an unplaced prototype (Z-Anatomy's "Lymph node", a 2 mm sphere at the scene origin, 0.9 m below
        the pelvis) is dropped;
    (c) exact duplicates (same system, vertex/face counts and bbox) ship once (a guard: none in this release);
    (d) a left/right object Z-Anatomy left unsuffixed (e.g. "Iliocostalis colli muscle" = the left one,
        next to "Iliocostalis colli muscle.r") gets its side from its position and a _l/_r id;
    (e) a pair whose .l/.r labels are swapped in the source (both lie wholly on the other side; measured:
        "Lateral temporomandibular ligament") is swapped back.
    Raw Z-Anatomy x: +x is the subject's LEFT (zan_source.to_atlas_frame)."""
    objs = {o["name"]: o for o in inventory["objects"]}
    fixes: dict = {"decal_dropped": [], "unplaced_prototype_dropped": [], "duplicate_dropped": [],
                   "side_inferred": [], "side_swapped": []}
    out = {}
    seen_geo = {}
    for sid in sorted(orphans):
        meta = orphans[sid]
        o = objs.get(meta["mesh_name"])
        if DECAL_RE.search(meta["mesh_name"]):
            fixes["decal_dropped"].append({"id": sid, "source": meta["mesh_name"]})
            continue
        if o is not None:
            lo, hi = np.asarray(o["bbox_min_mm"]), np.asarray(o["bbox_max_mm"])
            if np.linalg.norm((lo + hi) / 2) < 5.0 and (hi - lo).max() < 5.0:
                fixes["unplaced_prototype_dropped"].append({"id": sid, "source": meta["mesh_name"]})
                continue
            key = (o["system"], o["vertex_count"], o["face_count"], tuple(o["bbox_min_mm"]), tuple(o["bbox_max_mm"]))
            if key in seen_geo:
                fixes["duplicate_dropped"].append({"id": sid, "source": meta["mesh_name"], "same_as": seen_geo[key]})
                continue
            seen_geo[key] = sid
        out[sid] = meta

    def geo_side(o):
        lo, hi = o["bbox_min_mm"][0], o["bbox_max_mm"][0]
        return "left" if lo > 5.0 else ("right" if hi < -5.0 else None)

    by_base: dict = {}
    for o in inventory["objects"]:
        if o.get("side") in ("left", "right") and not DECAL_RE.search(o["name"]):
            by_base.setdefault((o["system"], strip_suffix(o["name"])), {})[o["side"]] = o
    final = {}
    for sid in sorted(out):
        meta = out[sid]
        o = objs.get(meta["mesh_name"])
        if o is None:
            final[sid] = meta
            continue
        gs, pair = geo_side(o), by_base.get((o["system"], strip_suffix(meta["mesh_name"])), {})
        other = {"left": "right", "right": "left"}
        if meta["side"] is None and gs and other[gs] in pair and gs not in pair:
            new = "zan_" + _slug(meta["name"]) + {"left": "_l", "right": "_r"}[gs]
            if new not in out and new not in final:
                fixes["side_inferred"].append({"was": sid, "now": new, "source": meta["mesh_name"], "side": gs})
                final[new] = dict(meta, side=gs, note=(f"Q186: Z-Anatomy names this object without a side "
                                                       f"suffix; it lies wholly on the {gs} and its "
                                                       f"{other[gs]} counterpart is suffixed, so it ships as {gs}."))
                continue
        if meta["side"] in ("left", "right") and gs and gs != meta["side"]:
            twin = pair.get(other[meta["side"]])
            if twin is not None and geo_side(twin) == meta["side"]:
                new = sid[:-2] + {"left": "_l", "right": "_r"}[gs]
                fixes["side_swapped"].append({"was": sid, "now": new, "source": meta["mesh_name"]})
                final[new] = dict(meta, side=gs, note=(f"Q186: the Z-Anatomy source labels this object "
                                                       f"'{meta['side']}' but it lies wholly on the {gs} (as its "
                                                       f"twin lies on the other side): labels swapped back."))
                continue
        final[sid] = meta
    return final, fixes


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
        if o is None or o["face_count"] == 0 or DECAL_RE.search(e["zanatomy_name"]):
            continue
        base = strip_suffix(e["zanatomy_name"])
        if (o.get("side"), base) in consumed_keys:
            continue  # a UI-highlight / other-system copy of something already shipped
        if o["system"] == "Skeletal" and (base in muscular_bases or not any(
                w in base.lower() for w in ("cartilage", "sinus", "bone"))):
            continue  # a muscle's attachment footprint drawn on the bone, not the muscle
        key = (o["system"], o.get("side"), base)
        aid = e.get("atlas_id")
        if aid and aid[-2:] in ("_l", "_r") and o.get("side") in ("left", "right") and \
                aid[-2:] != {"left": "_l", "right": "_r"}[o["side"]]:
            aid = None  # Q186: a left object name-matched to a RIGHT atlas id must not claim "part of" it
        groups.setdefault(key, []).append((o, aid))
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
Q162_REPORT_SOURCE = ("Q162 (2026-09-28): measured by scripts/zanatomy/build_zan_atlas_viewer.py on the Z-Anatomy "
                      "source meshes (contralateral mirror audit; ray-cast muscle gap closure, "
                      "scripts/zanatomy/muscle_gap_closure.py). Interface target from Stecco et al. 2008 "
                      "doi:10.1016/j.jbmt.2008.04.041, Stecco et al. 2009 doi:10.1007/s00276-008-0395-5, "
                      "Pirri et al. 2021 doi:10.1111/joa.13360.")


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


def _fmt_mm(x) -> str:
    return f"{x:.1f}" if isinstance(x, (int, float)) else "n/a"


def fit_badge(mesh_id: str, rep: dict, left_forearm_proxy: bool, region: str | None = None, body: str = "vhf") -> str:
    """Q168: one structure's badge text -- its own measured error where her CT mesh exists,
    otherwise its region's median/max, labelled as an estimate.  Q195: body="vhm" = the same for the VH male (his)."""
    if body == "vhm":
        return fit_badge_vhm(mesh_id, rep, region)
    head = ("Q168: Z-Anatomy geometry fitted onto the Visible Human female's own skeleton "
            "(per-bone similarity fits, soft tissue blended from the nearest bones). ")
    ps = rep["per_structure"].get(mesh_id)
    if ps is not None:
        txt = (f"Measured on her own CT mesh ({ps['her_subject']}): centroid {_fmt_mm(ps['centroid_mm'])} mm, "
               f"surface {_fmt_mm(ps['surface_mm'])} mm (before fitting {_fmt_mm(ps['raw_centroid_mm'])} / "
               f"{_fmt_mm(ps['raw_surface_mm'])} mm).")
        if (ps.get("her_extent_ratio") or 1.0) < 0.7:
            txt += " Her mesh is cut off by the scan field, so the centroid error is overstated."
        if ps.get("fit_target"):
            txt += " This muscle was used to place her left forearm, so it is not an independent check."
        return head + txt
    region = rep["region_of_structure"].get(mesh_id) or region or "whole_body"
    re_ = rep["region_errors"].get(region) or rep["region_errors"]["whole_body"]
    s = re_["surface_mm"]
    txt = (f"Not measured on this structure (she has no mesh of it). Estimate from her {region.replace('_', '/')} "
           f"region: surface error median {_fmt_mm(s['median'])} mm, max {_fmt_mm(s['max'])} mm "
           f"(n={re_['n']}).")
    if left_forearm_proxy:
        txt += (" Her left forearm and hand have no CT bones; they are placed from her own left forearm "
                "extensor muscles, so this placement cannot be checked.")
    return head + txt


def fit_badge_vhm(mesh_id: str, rep: dict, region: str | None = None) -> str:
    """Q195: the badge of a structure fitted onto the VH MALE's own skeleton: measured error against his own mesh where one
    exists (before -> after), otherwise the median/max of his body region, labelled as an estimate."""
    head = ("Q195: Z-Anatomy geometry fitted onto the Visible Human male's own skeleton (his CT / DU release bones; per-bone "
            "similarity fits, soft tissue blended from the nearest bones). ")
    ps = rep["per_structure"].get(mesh_id)
    if ps is not None:
        txt = (f"Measured against his own mesh ({ps['her_subject']}): centroid {_fmt_mm(ps['centroid_mm'])} mm, "
               f"surface {_fmt_mm(ps['surface_mm'])} mm (Z-Anatomy unfitted: {_fmt_mm(ps['raw_centroid_mm'])} / "
               f"{_fmt_mm(ps['raw_surface_mm'])} mm).")
        if (ps.get("her_extent_ratio") or 1.0) < 0.7:
            txt += " His mesh is cut off by the scan field or only partly segmented, so the centroid error is overstated."
        return head + txt
    region = rep["region_of_structure"].get(mesh_id) or region or "whole_body"
    re_ = rep["region_errors"].get(region) or rep["region_errors"]["whole_body"]
    s = re_["surface_mm"]
    return head + (f"Not measured on this structure (he has no mesh of it). Estimate from his {region.replace('_', '/')} "
                   f"region: surface error median {_fmt_mm(s['median'])} mm, max {_fmt_mm(s['max'])} mm (n={re_['n']}).")


TARGET = {"body": "vhf"}          # Q195: which body this build fits onto (set in build())


def load_her_skin():
    """Her own CT body-surface mesh (atlas id `skin`, first of her subjects carrying it), or None."""
    from scripts.transfer import zan_to_vhf_whole_body as Q168
    try:
        order = Q168.her_subject_order()      # Q195: the configured body's bundle (female unless body_ctx.configure("vhm"))
    except (OSError, ValueError, KeyError):
        return None
    for sub in order:
        mf = Q168.VH_DIR / sub / "manifest.json"
        if not mf.exists():
            continue
        st = [s for s in json.loads(mf.read_text())["structures"] if s["atlas_id"] == "skin"]
        if not st:
            continue
        V = np.fromfile(Q168.VH_DIR / sub / "vertices.f32", dtype="<f4").reshape(-1, 3)
        return sub, np.vstack([V[s["vertex_offset"]:s["vertex_offset"] + s["vertex_count"]] for s in st]).astype(np.float64)
    return None


def skin_vs_her_skin(pending: list[dict]) -> dict:
    """Q186: each fitted Z-Anatomy skin patch vs HER OWN CT skin surface (nearest-vertex distance), so
    the badge states how far the generic male skin sits from her real body surface. Her CT skin is cut
    by the scan field in places, so the median (not the max) is the meaningful figure."""
    from scipy.spatial import cKDTree
    skin = [p for p in pending if p["cat"] == "skin"]
    her = load_her_skin() if skin else None
    if her is None:
        for p in skin:
            p["fit_note"] += " Not compared with " + ("his" if TARGET["body"] == "vhm" else "her") + " own skin (the CT skin mesh is not available in this build)."
        return {"compared": False}
    sub, hv = her
    tree = cKDTree(hv)
    allv = []
    for p in skin:
        d = tree.query(p["v"])[0]
        allv.append(d)
        if TARGET["body"] == "vhm":
            p["fit_note"] += (f" Skin: compared with his own CT skin surface ({sub}), this patch lies a median "
                              f"{np.median(d):.1f} mm (90th percentile {np.percentile(d, 90):.1f} mm) from it; the "
                              f"shape is still Z-Anatomy's body, so fat and contour are not his.")
            continue
        p["fit_note"] += (f" Skin: compared with her own CT skin surface ({sub}), this patch lies a median "
                          f"{np.median(d):.1f} mm (90th percentile {np.percentile(d, 90):.1f} mm) from it; the "
                          f"shape is Z-Anatomy's male body, so breasts, fat and contour are not hers.")
    d = np.concatenate(allv)
    return {"compared": True, "her_subject": sub, "patches": len(skin),
            "median_mm": round(float(np.median(d)), 1), "p90_mm": round(float(np.percentile(d, 90)), 1),
            "frac_within_10mm": round(float((d <= 10).mean()), 3)}


def fit_to_vhf(pending: list[dict], body: str = "vhf") -> dict:
    """Q168 (owner: 'Z-Anatomy female -- fit it to her skeleton'): drop the male-only objects, move
    every structure into the VH female's frame with the committed per-bone fits, badge each one.
    Q195: body="vhm" fits onto the VH male (his own bones, Q195 report), keeping the male-only structures."""
    from scripts.transfer import zan_to_vhf_whole_body as Q168  # lazy: that module imports this one
    report_path = Q168.DEFAULT_REPORT
    if body == "vhm":
        from scripts.transfer import zan_to_vhm_whole_body as Q195
        Q195.apply_male_units()
        report_path = Q195.REPORT
    rep = json.loads(Path(report_path).read_text())
    male = (Q168.MALE_ONLY_IDS | MALE_ONLY_SKIN) if body == "vhf" else frozenset()
    dropped = [p["mesh_id"] for p in pending if p["mesh_id"] in male]
    pending[:] = [p for p in pending if p["mesh_id"] not in male]
    xf = Q168.load_zan_to_vhf(zan_meshes={p["mesh_id"]: p["v"] for p in pending}, report_path=report_path)
    # Q186: ids Q168's report does not list (skin, renamed orphans) get their region the way Q168 assigned
    # every other structure's (nearest Z-Anatomy bones, in the source frame, before the fit)
    new_ids = [p for p in pending if p["mesh_id"] not in rep["region_of_structure"]]
    rtree = Q168.region_tree({p["mesh_id"]: p for p in pending}) if new_ids else None
    new_region = {p["mesh_id"]: Q168.structure_region(p["v"], rtree) for p in new_ids}
    proxy_ids = set(Q168.PROXY_FOLLOWERS)
    measured = 0
    seam_before = {}  # Q186: skin vertices shared by two patches -> their copies, to measure tearing
    for i, p in enumerate(pending):
        if p["cat"] == "skin":
            for j, key in enumerate(map(tuple, np.round(p["v"], 2))):
                seam_before.setdefault(key, []).append((i, j))
    for p in pending:
        if p["cat"] == "skin":
            # Q186: one limb class per skin patch (patches ARE body regions); per-cluster classes flung
            # her left thumb's nail fold ~290 mm away (it sits against the thigh in the source pose)
            p["v"] = np.asarray(xf.blend(p["v"], xf.limb_class(p["v"])), dtype=np.float64)
        else:
            p["v"] = np.asarray(xf(p["mesh_id"], p["cat"], p["v"]), dtype=np.float64)
        region = rep["region_of_structure"].get(p["mesh_id"]) or new_region.get(p["mesh_id"], "whole_body")
        left_proxy = p["mesh_id"] in proxy_ids or (region == "forearm_hand" and side_code(p["side_raw"]) == "l")
        p["fit_note"] = fit_badge(p["mesh_id"], rep, left_proxy, region, body)
        measured += p["mesh_id"] in rep["per_structure"]
    skin_fit = skin_vs_her_skin(pending)
    tears = [max(np.linalg.norm(pending[a][ "v"][b] - pending[c]["v"][d]) for (a, b) in cp for (c, d) in cp)
             for cp in seam_before.values() if len({a for a, _ in cp}) > 1]
    if tears:
        t = np.asarray(tears)
        skin_fit["seam_tear_mm"] = {"shared_vertices": len(t), "median": round(float(np.median(t)), 2),
                                    "p99": round(float(np.percentile(t, 99)), 2), "max": round(float(t.max()), 2)}
    return {"skin_vs_her_ct_skin": skin_fit,"rule": "scripts/transfer/zan_to_vhf_whole_body.py (Q168)" + (" via zan_to_vhm_whole_body.py (Q195)" if body == "vhm" else ""), "fits": str(Path(report_path).relative_to(REPO)),
            "male_only_dropped": sorted(dropped), "structures": len(pending),
            "measured_on_her_mesh": measured, "region_errors": rep["region_errors"],
            "female_pelvic_organs": rep.get("female_pelvic_organs")}


def refit_trunk_q186c(pending: list[dict], raw: dict, anterior_v5: bool = False) -> dict:
    """Q186c (owner: error in the female chest/abdomen): per-bone refit of her ribs + vertebrae onto her CT labels, then
    one smooth displacement field for the soft tissue (scripts/zanatomy/trunk_refit_q186c.py); badges every moved
    structure and re-measures the skin patches against her CT skin."""
    import re
    from scripts.zanatomy import trunk_refit_q186c as Q186c
    before_refit = {p["mesh_id"]: p["v"].copy() for p in pending}
    bones = Q186c.refit_bones(pending)
    legacy_v = None
    if anterior_v5:
        # Q186c3: the v5 field (cubic RBF on all bones + skin anchors; scripts/zanatomy/trunk_refit_q186c_v5.py) run on a copy
        # of the bone-refit state; its result decides the front, the new field the back / flanks / shoulders / buttocks
        from scripts.zanatomy import trunk_refit_q186c_v5 as V5
        copy5 = [{"mesh_id": p["mesh_id"], "cat": p["cat"], "v": p["v"].copy(), "f": p["f"], "anchor_mask": p.get("anchor_mask")} for p in pending]
        V5.refit_trunk(copy5, raw)
        legacy_v = {p["mesh_id"]: p["v"] for p in copy5}
        del copy5
    cart = Q186c.refit_cartilage(pending)
    rep = Q186c.refit_trunk(pending, raw)
    blend = Q186c.blend_anterior(pending, legacy_v) if legacy_v is not None else None
    clamp = Q186c.clamp_inside_skin(pending)
    flips = Q186c.mesh_flip_stats(pending, raw, before_refit)
    del before_refit
    for p in pending:
        p.pop("anchor_mask", None)
        p.pop("anchor_target", None)
        p.pop("v_unclamped", None)
    by_id = {p["mesh_id"]: p for p in pending}
    for mid, b in bones.items():
        if b.get("status") == "refit":
            by_id[mid]["fit_note"] += (f" Q186c: refit onto her own CT label of this bone (TotalSegmentator, her scan): her label to this "
                                       f"mesh {b['her_label_to_Z_mm_before']} -> {b['her_label_to_Z_mm_after']} mm median, this mesh to her "
                                       f"label {b['Z_to_her_label_mm_before']} -> {b['Z_to_her_label_mm_after']} mm (similarity, scale {b['scale']}).")
    for mid, c in clamp["per_structure"].items():
        if c["fraction"] >= 0.01 and mid in by_id:
            by_id[mid]["fit_note"] += (f" Q186c: {c['fraction']:.0%} of its vertices lay outside her CT skin and were moved inside it (median {c['median_mm']} mm, max {c['max_mm']} mm).")
    for mid, c in cart.items():
        if c.get("status") == "anchors":
            by_id[mid]["fit_note"] += (f" Q186c: anchored on her own CT costal-cartilage mesh (rigid ICP, {c['supported_vertex_fraction']:.0%} of its vertices within "
                                       f"{Q186c.SUPPORT_MM:.0f} mm of it): {c['to_her_mesh_mm_before']} -> {c['after']} mm median to her mesh.")
    for k, st in rep["_per_structure_shift"].items():
        if st["shift_max"] > 1.0:
            by_id[k]["fit_note"] += (f" Q186c trunk refit: carried by one smooth field anchored on her own CT ribs, vertebrae, pelvis "
                                     f"and CT skin outline (not the per-bone blend); moved a median {st['shift_med']:.0f} mm "
                                     f"(max {st['shift_max']:.0f} mm) from the Q168 position. An estimate: Z-Anatomy's arrangement, her frame.")
    for p in pending:
        if p["cat"] == "skin":
            p["fit_note"] = re.sub(r" Skin: compared with (?:her|his) own CT skin surface.*$", "", p["fit_note"], flags=re.S)
    skin_fit = skin_vs_her_skin(pending)
    LAST_REPORTS["fit_to_vhf"]["skin_vs_her_ct_skin_after_q186c"] = skin_fit
    out = {k: v for k, v in rep.items() if not k.startswith("_")}
    out["bones"] = bones
    out["cartilage"] = cart
    out["anterior_v5_blend"] = blend
    out["mesh_flips_vs_source"] = flips
    out["clamp_inside_her_skin"] = {k: v for k, v in clamp.items() if k != "per_structure"}
    out["skin_vs_her_ct_skin"] = skin_fit
    return out


def _vhm_text(s: str) -> str:
    import re
    s = re.sub(r"\bhers\b", "his", s)
    s = re.sub(r"\b(her)\b", "his", s)
    s = re.sub(r"\bHer\b", "His", s)
    return re.sub(r"\bshe\b", "he", re.sub(r"\bShe\b", "He", s))


def _body_words(pending: list[dict], fn):
    """Q195: the female refit hooks write her-wording badges; for the male build the text they ADD is rewritten to his (pronoun swap only)."""
    n0 = {p["mesh_id"]: len(p.get("fit_note") or "") for p in pending}
    out = fn()
    if TARGET["body"] == "vhm":
        for p in pending:
            n = n0.get(p["mesh_id"], 0)
            note = p.get("fit_note") or ""
            if len(note) > n:
                p["fit_note"] = note[:n] + _vhm_text(note[n:])
    return out


def clamp_to_skin_q195(pending: list[dict]) -> dict:
    """Q195 stage 1 (his body, no trunk refit): every non-bone vertex that the Q168 per-bone blend left outside HIS CT skin is moved to just inside it
    (scripts/zanatomy/trunk_refit_q186c.clamp_inside_skin, body-aware via body_ctx); badges the structures it touched and re-measures the skin patches."""
    import re
    from scripts.zanatomy import trunk_refit_q186c as T
    clamp = T.clamp_inside_skin(pending)
    by_id = {p["mesh_id"]: p for p in pending}
    for mid, c in clamp["per_structure"].items():
        if c["fraction"] >= 0.01 and mid in by_id:
            by_id[mid]["fit_note"] += (f" Q195: {c['fraction']:.0%} of its vertices lay outside his CT skin and were moved inside it (median {c['median_mm']} mm, max {c['max_mm']} mm).")
    for p in pending:
        p.pop("v_unclamped", None)
        if p["cat"] == "skin":
            p["fit_note"] = re.sub(r" Skin: compared with his own CT skin surface.*$", "", p["fit_note"], flags=re.S)
    skin_fit = skin_vs_her_skin(pending)
    LAST_REPORTS["fit_to_vhf"]["skin_vs_his_ct_skin_after_clamp"] = skin_fit
    return {"clamp_inside_his_skin": {k: v for k, v in clamp.items() if k != "per_structure"}, "skin_vs_his_ct_skin": skin_fit}


def close_muscle_gaps(pending: list[dict]) -> dict:
    """Q162: gap closure over every muscle-layer mesh (see muscle_gap_closure.py for the rule and
    its citations); tendons are closed onto, everything else is an obstacle."""
    movable, tendons, obstacles = {}, {}, {}
    for p in pending:
        if p["cat"] == "skin":
            continue  # Q186: outside every muscle; leaving it out keeps the Q162 closure unchanged
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
          close_gaps: bool = True, target_body: str | None = None,
          integ_inventory_path: Path | None = DEFAULT_INTEG_INVENTORY, with_hair: bool = False,
          trunk_refit: bool = False, anterior_v5: bool = False, q190: dict | None = None, q191: dict | None = None,
          q194: dict | None = None, pure_source: bool = False, q195_refine: bool = False):
    TARGET["body"] = target_body or "vhf"
    if target_body == "vhm":                  # Q195: aim the Q168/Q186c/Q190/Q191 fitting code at the VH male BEFORE it is imported
        from scripts.zanatomy import body_ctx
        body_ctx.configure("vhm")
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
    # Q186: build defects found by the inventory audit (see curate_orphans / split_vessel_mismatches)
    q186_fixes = {"vessel_name_map_errors_split": split_vessel_mismatches(matched, orphans)}
    orphans, orphan_fixes = curate_orphans(orphans, inventory)
    q186_fixes.update(orphan_fixes)
    rescued = rescue_unshipped(inventory, namemap, matched, orphans)
    for sid in [k for k, m in rescued.items() if DECAL_RE.search(m["mesh_name"])]:
        q186_fixes["decal_dropped"].append({"id": sid, "source": rescued.pop(sid)["mesh_name"]})
    skins = (skin_pool(json.loads(Path(integ_inventory_path).read_text()), with_hair)
             if integ_inventory_path and Path(integ_inventory_path).exists() else {})
    # Q186: which Z-Anatomy source object(s) each shipped id is made of (route: matched = this
    # project's own atlas id, several sub-parts possibly concatenated; orphan; rescued; skin)
    provenance: dict = {}
    origin, origin_report = compute_origin(zan_dir)
    corrections = {} if pure_source else load_corrections(corrections_dir)  # Q196: pure_source = no declarative correction
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
               rec_override=None, zanatomy_name: str | None = None, parent_link=None, notes=(),
               fit_note: str | None = None, pre_decimated=None):
        nonlocal byte_off, matched_with_record, parent_linked_count
        note = " ".join(notes)
        if pre_decimated is not None:        # Q194: the shipped (decimated) mesh was moved by the bounded neighbour separation
            dv, df = pre_decimated
        elif cat == "skin":
            dv, df = v, f  # Q186: patches tile one surface; decimating each alone would open the seams
        else:
            dv, df = decimate(v, f, mesh_id, cat, (category_scale or {}).get(cat, budget_scale), prepped=True)
        df = outward_if_closed(dv, df)

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
            corrected_ids.append(mesh_id)
        if note or fit_note:
            rec_out = dict(rec_out)
            rec_out["procedural_badge"] = " ".join(x for x in (fit_note, note) if x)
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
        provenance[aid] = {"route": "matched", "sources": list(zanatomy_names)}
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
        provenance[stable] = {"route": "orphan", "sources": [meta["mesh_name"]]}
        emit(stable, meta["name"], meta["side"], meta["category"], v_raw, f,
             zanatomy_name=meta["name"], parent_link=parent_link)
        if meta.get("note"):
            pending[-1]["notes"].append(meta["note"])

    # Q161: matched-but-rejected objects (see rescue_unshipped) -- own geometry, own id,
    # linked to the atlas entity the name map matched them to (as "part of").
    for stable, meta in sorted(rescued.items()):
        if stable in seen_ids:
            continue
        v_raw, f = _load_raw_mesh(zan_dir, meta["system"], meta["mesh_name"])
        parent_pair = atlas_records.get(meta["atlas_id"]) if meta["atlas_id"] else None
        parent_link = (meta["atlas_id"], parent_pair[0], parent_pair[1]) if parent_pair else None
        provenance[stable] = {"route": "rescued", "sources": [meta["mesh_name"]]}
        emit(stable, meta["name"], meta["side"], meta["category"], v_raw, f,
             zanatomy_name=meta["name"], parent_link=parent_link)

    # Q186: the skin (Integument system), one shipped id per source object
    for sid, meta in sorted(skins.items()):
        v_raw, f = _load_raw_mesh(zan_dir, meta["system"], meta["mesh_name"])
        provenance[sid] = {"route": "skin", "sources": [meta["mesh_name"]]}
        emit(sid, meta["name"], meta["side"], meta["category"], v_raw, f, zanatomy_name=meta["name"])

    # Q162 (owner: "look on the contralateral side and other accurate models and medical articles"):
    # (1) replace the few left-side source objects the mirror audit found broken by the mirrored
    # right side; (2) close the artificial gaps between neighbouring muscles to a cited 1 mm interface.
    contra_report = {"skipped": "pure_source"} if pure_source else repair_contralateral(pending)
    # Q168: the female variant is moved onto her skeleton BEFORE gap closure, so the 1 mm interface
    # is restored in her frame (the per-bone fits stretch neighbouring muscles differently).
    LAST_REPORTS.pop("fit_to_vhf", None)
    LAST_REPORTS.pop("trunk_refit", None)
    if target_body in ("vhf", "vhm"):
        raw_before_fit = {p["mesh_id"]: p["v"].copy() for p in pending} if (trunk_refit or q191 or q190 or q194) else None
        LAST_REPORTS["fit_to_vhf"] = fit_to_vhf(pending, body=target_body)
        if target_body == "vhm" and not trunk_refit:
            LAST_REPORTS["clamp_q195"] = clamp_to_skin_q195(pending)
        if trunk_refit:
            LAST_REPORTS["trunk_refit"] = _body_words(pending, lambda: refit_trunk_q186c(pending, raw_before_fit, anterior_v5=anterior_v5))
            if q190 and q190.get("dump"):
                from scripts.zanatomy import q190_refine as Q190
                Q190.dump_pending(pending, raw_before_fit, q190["dump"])
                raise SystemExit(0)
            if q190 and q190.get("refine"):
                # Q190: per-structure refinement of each fitted Z muscle/fascia/nerve/skin toward her own CT label (after the
                # global field + clamp, before the Q162 gap closure and the decimation)
                from scripts.zanatomy import q190_refine as Q190
                LAST_REPORTS["q190"] = _body_words(pending, lambda: Q190.refine_pending(pending, raw_before_fit))
        if q191 and (q191.get("dump") or q191.get("hand")):
            from scripts.zanatomy import q190_refine as Q190
            if q191.get("dump"):
                Q190.dump_pending(pending, raw_before_fit, q191["dump"])
                raise SystemExit(0)
            # Q191: hand/wrist bones onto her own hand bones, soft tissue carried by a bone-anchored field, intrinsic muscles refined
            from scripts.zanatomy import q191_hand as Q191
            left_fit = None
            if q191.get("left_fit"):          # Q192: the left hand placed on her left-hand cryosection photographs
                left_fit = json.loads(Path(q191["left_fit"]).read_text())
            LAST_REPORTS["q191"] = _body_words(pending, lambda: Q191.refine_hand(pending, raw_before_fit, left_fit=left_fit))
            if q191.get("dump_after"):
                Q190.dump_pending(pending, raw_before_fit, q191["dump_after"])
        if target_body == "vhm" and q195_refine:
            # Q195: organs and lower-limb muscles refined onto HIS measured meshes, limb skin onto his CT skin (scripts/zanatomy/q195_refine.py)
            from scripts.zanatomy import q195_refine as Q195R
            LAST_REPORTS["q195_refine"] = _body_words(pending, lambda: Q195R.refine_pending(pending, raw_before_fit))
    elif target_body == "native_female":
        # Q196: the generic Z-Anatomy body in its OWN frame, male-only objects removed, nothing fitted to any specimen
        from scripts.transfer import zan_to_vhf_whole_body as Q168
        male = Q168.MALE_ONLY_IDS | MALE_ONLY_SKIN
        dropped = sorted(p["mesh_id"] for p in pending if p["mesh_id"] in male)
        pending[:] = [p for p in pending if p["mesh_id"] not in male]
        LAST_REPORTS["native_female"] = {"male_only_dropped": dropped, "structures": len(pending),
                                         "fitted_to_any_specimen": False}
    elif target_body is not None:
        raise ValueError(f"unknown target body {target_body!r}")
    pend_held = None
    close_gaps = close_gaps and not pure_source
    if close_gaps and q191 and q191.get("left_fit"):
        # Q192: the gap closure is ONE global ray scene (deterministic, but every mesh that moves perturbs the rays of the others by a hair; measured: the left hand
        # alone changed 110 right-side and 227 left muscles by 0.01-1 mm and decimation then re-samples them).  So it is run twice, on the Q191 state (left hand held)
        # and on the Q192 state, and every structure that is neither moved by the left-hand refit nor within 10 mm of one that is keeps its Q191 result bit for bit.
        from scripts.zanatomy import q191_hand as Q191H
        snap = Q191H.LEFT_HELD_SNAPSHOT
        pend_held = [{**p, "v": snap.get(p["mesh_id"], p["v"]), "notes": list(p["notes"])} for p in pending]
        moved = [p["v"] for p in pending if p["mesh_id"] in snap and (len(snap[p["mesh_id"]]) != len(p["v"]) or not np.array_equal(snap[p["mesh_id"]], p["v"]))]
        moved += [snap[p["mesh_id"]] for p in pending if p["mesh_id"] in snap and not np.array_equal(snap[p["mesh_id"]], p["v"])]
        from scipy.spatial import cKDTree as _KD
        mtree = _KD(np.vstack([m[::3] for m in moved]))
        coupled = {p["mesh_id"] for p in pending if mtree.query(p["v"][::4], distance_upper_bound=10.0)[0].min() < 10.0}
    gap_report = close_muscle_gaps(pending) if close_gaps else {"skipped": True}
    if pend_held is not None:
        close_muscle_gaps(pend_held)
        kept = 0
        for p, ph in zip(pending, pend_held):
            if p["mesh_id"] not in coupled:
                kept += int(not np.array_equal(p["v"], ph["v"]))
                p["v"], p["notes"] = ph["v"], ph["notes"]
        gap_report["q192_isolation"] = {"coupled_structures_keep_the_Q192_closure": len(coupled), "structures_restored_to_their_Q191_closure": kept,
                                        "why": "the global closure scene couples distant meshes at the 0.01-1 mm level; outside the left-hand refit (and its 10 mm neighbourhood) the Q191 result is kept"}
    LAST_REPORTS["contralateral"] = contra_report
    LAST_REPORTS["gap_closure"] = gap_report
    if target_body == "vhm" and q195_refine:
        from scripts.zanatomy import q195_refine as Q195R
        LAST_REPORTS["q195_final_volume_guard"] = _body_words(pending, lambda: Q195R.final_volume_guard(pending, raw_before_fit))
    if q194 and q194.get("dump"):         # Q194: the exact full-resolution state right before the decimation / export (= v9 without --q194-refine)
        from scripts.zanatomy import q190_refine as Q190
        Q190.dump_pending(pending, raw_before_fit, q194["dump"])
        if q194.get("dump_only"):
            raise SystemExit(0)
    if q194 and q194.get("refine"):
        # Q194: bounded post-closure refinements (left forearm on her photographs, overlap / distortion leftovers); everything not listed in the report stays bit-identical
        from scripts.zanatomy import q194_refine as Q194
        LAST_REPORTS["q194"] = Q194.refine_pending(pending, raw_before_fit, budget_scale=budget_scale, category_scale=category_scale)
        if q194.get("dump_after"):
            from scripts.zanatomy import q190_refine as Q190
            Q190.dump_pending(pending, raw_before_fit, q194["dump_after"])
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
            "skin_structures": len([m for m in meshes if m["id"] in skins]),
            "q186_fixes": q186_fixes,
            "skin_layer": SKIN_LAYER,
            "contralateral_repairs": contra_report,
            "muscle_gap_closure": {k: v for k, v in gap_report.items() if k != "per_mesh"},
            **({"fit_to_vhf": {k: v for k, v in LAST_REPORTS["fit_to_vhf"].items() if k != "region_errors"}}
               if target_body in ("vhf", "vhm") else {}),
            **({"native_female": LAST_REPORTS["native_female"]} if target_body == "native_female" else {}),
        },
        **({"variant": target_body} if target_body in ("vhf", "vhm") else {}),
        **({"variant": "native_female"} if target_body == "native_female" else {}),
        **({"pure_source": True} if pure_source else {}),
        "meshes": meshes,
    }
    blob = b"".join(bin_chunks)
    shipped = {m["id"] for m in meshes}
    LAST_REPORTS["provenance"] = {k: v for k, v in sorted(provenance.items()) if k in shipped}
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


# Q168 female variant: page wording only (the template itself stays the reference viewer's).
VHF_WORDING = [
    ("<title>NMSK Atlas — Z-Anatomy reference body</title>", "<title>NMSK Atlas — Z-Anatomy fitted to the female</title>"),
    ("<h1>NMSK Atlas — Z-Anatomy</h1>", "<h1>NMSK Atlas — Z-Anatomy, fitted</h1>"),
    ("    <div class=\"licence\">",
     "    <p><strong>Fitted to a real body (Q168).</strong> In this female variant every Z-Anatomy structure has been "
     "moved onto the skeleton of the Visible Human female (U.S. National Library of Medicine), bone by bone; soft "
     "tissue follows the nearest bones. Male-only structures are removed. No female reproductive organs are shown: "
     "Z-Anatomy's reproductive organs are male and her own scans carry no uterus or ovary label, so nothing was "
     "invented. Every structure's card states its fit error, measured against her own CT mesh where one exists "
     "and otherwise estimated from its body region. Fits and errors: <code>data/derived/Q168_zan_to_vhf.json</code>.</p>\n"
     "    <div class=\"licence\">"),
]


# Q195 male variant: Z-Anatomy male fitted to the Visible Human male (his body does have the male-only structures, so they stay, fitted)
VHM_WORDING = [
    ("<title>NMSK Atlas — Z-Anatomy reference body</title>", "<title>NMSK Atlas — Z-Anatomy male, fitted to the Visible Human male</title>"),
    ("<h1>NMSK Atlas — Z-Anatomy</h1>", "<h1>NMSK Atlas — Z-Anatomy male, fitted to the Visible Human male</h1>"),
    ("    <div class=\"licence\">",
     "    <p><strong>Fitted to a real body (Q195).</strong> Z-Anatomy male, fitted to the Visible Human male: every Z-Anatomy structure "
     "has been moved onto the skeleton of the Visible Human male (U.S. National Library of Medicine), bone by bone; soft tissue "
     "follows the nearest bones. His body has the male-only structures, so they are kept and fitted. Every structure's card states "
     "its fit error, measured against his own CT-derived mesh where one exists and otherwise estimated from its body region; the "
     "shapes and the arrangement of the soft tissue are Z-Anatomy's, not his. Fits and errors: "
     "<code>data/derived/Q195_zan_to_vhm.json</code>.</p>\n"
     "    <div class=\"licence\">"),
]


def apply_vhf_wording(template: str, wording=None) -> str:
    for old, new in (wording or VHF_WORDING):
        if template.count(old) != 1:
            raise SystemExit(f"female wording: template anchor not found once: {old[:50]!r}")
        template = template.replace(old, new, 1)
    return template


# Q196 native female variant: page wording only (no body is fitted, nothing is invented)
NATIVE_FEMALE_WORDING = [
    ("<title>NMSK Atlas — Z-Anatomy reference body</title>", "<title>NMSK Atlas — Female base model</title>"),
    ("<h2>NMSK Atlas — Z-Anatomy</h2>", "<h2>NMSK Atlas — Female base model (unadapted)</h2>"),
    ("<h1>NMSK Atlas — Z-Anatomy</h1>", "<h1>NMSK Atlas — Female base</h1>"),
    ('matched+" atlas-linked · "+partOf+" part-of-linked";',
     'matched+" atlas-linked · "+partOf+" part-of-linked · generic Z-Anatomy body, male-only organs removed, not fitted to any specimen";'),
    ("    <div class=\"licence\">",
     "    <p><strong>Source limitation (Q196).</strong> The source has no female body: Z-Anatomy (and BodyParts3D "
     "under it) ships ONE male-derived body. This page is the generic Z-Anatomy body in its own frame with the "
     "male-only organs removed (penis, scrotum and male external skin, testes, epididymides, seminal glands, "
     "prostate and their vessels). No female reproductive organs are shown and none were invented. Nothing is "
     "fitted to any specimen, scan or Visible Human; body proportions, breasts and pelvis are the source's. "
     "Same repairs as the male base page (a few mirrored left-side objects, muscle gaps closed to a 1 mm "
     "interface). A genuinely female open atlas was searched for and not found: "
     "<code>data/derived/Q196_female_base_sources.json</code>.</p>\n"
     "    <div class=\"licence\">"),
]


def render_html(manifest: dict, blob: bytes, bin_files: list | None = None) -> str:
    """Self-contained page (geometry inlined as base64) unless `bin_files` names the sibling
    binary files the loader should fetch instead ([{path, bytes}], in blob order)."""
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    manifest_json = json.dumps(manifest, separators=(",", ":")).replace("</", "<\\/")
    b64 = "" if bin_files else base64.b64encode(blob).decode("ascii")
    if "</script" in b64.lower():
        raise SystemExit("base64 payload contains a script terminator")
    if manifest.get("variant") == "vhf":
        template = apply_vhf_wording(template)
    elif manifest.get("variant") == "vhm":
        template = apply_vhf_wording(template, VHM_WORDING)
    elif manifest.get("variant") == "native_female":
        template = apply_vhf_wording(template, NATIVE_FEMALE_WORDING)
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
    ap.add_argument("--integ-inventory", default=str(DEFAULT_INTEG_INVENTORY),
                    help="Q186: Integument (skin) inventory; '' to build without skin")
    ap.add_argument("--with-hair", action="store_true", help="Q186: also ship the Z-Anatomy hair objects")
    ap.add_argument("--anterior-v5", action="store_true",
                    help="Q186c3 (with --trunk-refit): blend the v5 field into the anterior sector (front, groin to shoulders)")
    ap.add_argument("--q190-dump", default=None, help="Q190: write the fitted pending meshes (npz) after the trunk refit and exit")
    ap.add_argument("--q190-refine", action="store_true",
                    help="Q190 (with --trunk-refit): per-structure refinement of the fitted muscles toward her own CT label surfaces")
    ap.add_argument("--q191-dump", default=None, help="Q191: write the fitted pending meshes (npz) after the Q190 refinement and exit")
    ap.add_argument("--q191-dump-after", default=None, help="Q191: also write the pending meshes (npz) right after the hand refit (audit input)")
    ap.add_argument("--q191-hand", action="store_true",
                    help="Q191 (with --trunk-refit --q190-refine): fit the hand/wrist bones onto her own hand bones and carry/refine the hand soft tissue")
    ap.add_argument("--q192-left-fit", default=None,
                    help="Q192 (with --q191-hand): data/derived/Q192_left_hand_fit.json -- place the LEFT hand/wrist bones on her left-hand cryosection photographs and run "
                         "the Q191 carry / candidates / gates for the left side (without it the left hand is held exactly as in Q191)")
    ap.add_argument("--q194-dump", default=None, help="Q194: write the final pre-export pending meshes (npz, after gap closure)")
    ap.add_argument("--q194-dump-after", default=None, help="Q194: also write the full-resolution pending meshes (npz) after the Q194 refinement (audit input)")
    ap.add_argument("--q194-dump-only", action="store_true", help="Q194: exit right after --q194-dump")
    ap.add_argument("--q194-refine", action="store_true", help="Q194 (with the Q192 flags): bounded post-closure refinement (scripts/zanatomy/q194_refine.py)")
    ap.add_argument("--q195-refine", action="store_true",
                    help="Q195 (with --target-body vhm): organs + lower-limb muscles refined onto his measured meshes, limb skin onto his CT skin")
    ap.add_argument("--trunk-refit", action="store_true",
                    help="Q186c (female only): refit her ribs/vertebrae onto her CT labels and carry the trunk soft tissue by one "
                         "smooth field anchored on her bones + CT skin outline (scripts/zanatomy/trunk_refit_q186c.py)")
    ap.add_argument("--target-body", choices=["vhf", "vhm", "native_female"], default=None,
                    help="vhf (Q168): fit the whole model onto the VH female's skeleton; vhm (Q195): onto the VH male's; native_female (Q196): the unfitted Z-Anatomy body "
                         "in its own frame without the male-only objects")
    ap.add_argument("--pure-source", action="store_true",
                    help="Q196: no declarative corrections, no contralateral repair, no muscle gap closure (decimation + skin only)")
    ap.add_argument("--q162-report", default=None,
                    help="default data/derived/Q162_gap_closure_contralateral.json (Q168_zan_female_build.json with --target-body vhf)")
    ap.add_argument("-o", "--out", default=None,
                    help="default build/viewer_zan_atlas/atlas_viewer_zan_atlas.html (build/viewer_zan_female/"
                         "atlas_viewer_zan_female.html with --target-body vhf)")
    ap.add_argument("--report", default=None,
                    help="default data/derived/Q157_zan_atlas_report.json (Q168_zan_female_report.json with --target-body vhf)")
    args = ap.parse_args(argv)
    derived = REPO / "data" / "derived"
    female = args.target_body == "vhf"
    native = args.target_body == "native_female"
    male_fit = args.target_body == "vhm"
    args.q162_report = args.q162_report or str(derived / ("Q195_zan_male_fitted_build.json" if male_fit
                                                         else "Q168_zan_female_build.json" if female
                                                         else "Q196_zan_female_native_build.json" if native
                                                         else "Q162_gap_closure_contralateral.json"))
    args.report = args.report or str(derived / ("Q195_zan_male_fitted_report.json" if male_fit
                                                     else "Q168_zan_female_report.json" if female
                                                     else "Q196_zan_female_native_report.json" if native
                                                     else "Q157_zan_atlas_report.json"))
    args.out = args.out or ("build/viewer_zan_male_fitted_q195/atlas_viewer_zan_male_fitted.html" if male_fit
                            else "build/viewer_zan_female/atlas_viewer_zan_female.html" if female
                            else "build/viewer_base_female_q196/atlas_viewer_base_female.html" if native
                            else "build/viewer_zan_atlas/atlas_viewer_zan_atlas.html")

    category_scale = dict(HIRES_CATEGORY_SCALE) if args.external_bin and not args.category_scale else {}
    for item in args.category_scale:
        cat, _, val = item.partition("=")
        category_scale[cat.strip()] = float(val)

    manifest, blob, origin_report = build(
        zan_dir=Path(args.zan_dir), inventory_path=Path(args.inventory), namemap_path=Path(args.namemap),
        corrections_dir=Path(args.corrections_dir), budget_scale=args.budget_scale,
        category_scale=category_scale, close_gaps=not args.no_gap_closure, target_body=args.target_body,
        integ_inventory_path=Path(args.integ_inventory) if args.integ_inventory else None, with_hair=args.with_hair,
        trunk_refit=args.trunk_refit, anterior_v5=args.anterior_v5, pure_source=args.pure_source, q195_refine=args.q195_refine,
        q190={"dump": args.q190_dump, "refine": args.q190_refine},
        q191={"dump": args.q191_dump, "hand": args.q191_hand, "dump_after": args.q191_dump_after, "left_fit": args.q192_left_fit},
        q194={"dump": args.q194_dump, "dump_only": args.q194_dump_only, "refine": args.q194_refine, "dump_after": args.q194_dump_after})
    src = Q162_REPORT_SOURCE + (" Q168 female variant: every structure first moved onto the VH female's skeleton "
                                "(scripts/transfer/zan_to_vhf_whole_body.py), then gap-closed in her frame." if female else "")
    Path(args.q162_report).write_text(json.dumps(
        {"source": src, **{k: v for k, v in LAST_REPORTS.items() if k != "provenance"}}, indent=1, default=float))

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
        "provenance": LAST_REPORTS.get("provenance", {}),
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
