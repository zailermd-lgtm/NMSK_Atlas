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

from scripts.zanatomy.map_names import load_full_atlas  # noqa: E402
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
    "ligament": "joint", "bursa": "joint",
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


def classify_layer(cat: str, zanatomy_name: str) -> str:
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


def n_pieces(f: np.ndarray, nv: int) -> int:
    """Connected surface pieces (triangles sharing a vertex)."""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    f = np.asarray(f, np.int64)
    e = np.concatenate([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
    _n, lab = connected_components(coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(nv, nv)),
                                   directed=False)
    return len(np.unique(lab[f[:, 0]]))


def decimate(v: np.ndarray, f: np.ndarray, mesh_id: str, cat: str, scale: float):
    """Q159: quadric edge-collapse first for EVERY mesh (it never splits a surface), vertex
    clustering only as a fallback. Measured on the full Q157 build at the same budgets:
    clustering added components to 340/2570 structures (123 nerves, 79 vessels, 6 muscles
    split into pieces), quadric to 32 (0 muscles) -- data/derived/Q159_decimation_continuity.json."""
    budget = max(150, int(BUDGET_OVERRIDES.get(mesh_id, BUDGET.get(cat, DEFAULT_BUDGET)) * scale))
    wv, wf = weld(v, f)
    src_pieces = n_pieces(wf, len(wv))
    for attempt in range(4):  # continuity guard: never ship more pieces than the source has
        q = decimate_quadric(wv, wf, budget * 2 ** attempt)
        if q is None or not len(q[1]) or len(q[0]) > MAX_VERTS:
            break
        if n_pieces(q[1], len(q[0])) <= src_pieces or attempt == 3:
            return q
    dv, df, _cell = decimate_to(v, f, budget)
    if len(df) == 0:
        dv, df = v, f
    if len(dv) > MAX_VERTS:
        dv, df, _cell = decimate_to(v, f, min(budget, MAX_VERTS - 1))
    return dv, df


def build(*, zan_dir: Path, inventory_path: Path, namemap_path: Path,
          corrections_dir: Path, budget_scale: float, category_scale: dict | None = None):
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

    def emit(mesh_id: str, display_name: str, side_raw, cat: str, v_raw: np.ndarray, f: np.ndarray,
              rec_override=None, zanatomy_name: str | None = None, parent_link=None):
        nonlocal byte_off, matched_with_record, parent_linked_count
        if mesh_id in seen_ids:
            raise ValueError(f"duplicate atlas id emitted twice: {mesh_id}")
        seen_ids.add(mesh_id)

        warped, note = apply_correction(mesh_id, v_raw, zan_dir, corrections)
        v = warped - origin
        dv, df = decimate(v, f, mesh_id, cat, (category_scale or {}).get(cat, budget_scale))

        fields, packed = pack_mesh(dv, df, byte_off)
        byte_off += len(packed)
        bin_chunks.append(packed)

        layer = classify_layer(cat, zanatomy_name or display_name)
        counts_by_layer[layer] += 1
        counts_by_category[cat] += 1

        entry = {"name": display_name, "id": mesh_id, "side": side_code(side_raw), "sys": layer, **fields}
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
BIN_FILE_MAX = 14_000_000  # the artifact host's per-binary-file cap is 15 MB


def split_blob(blob: bytes, stem: str, max_bytes: int = BIN_FILE_MAX):
    """Q159: cut the geometry into sibling files (even-length, so uint16 views stay aligned
    across the loader's concatenation). Returns [(published_path, bytes)]."""
    step = max_bytes - (max_bytes % 2)
    return [(f"{stem}_{i:02d}.bin", blob[o:o + step]) for i, o in enumerate(range(0, len(blob), step))]


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
                    help="Q159: write geometry as sibling <out-stem>_NN.bin files (each under the "
                         "artifact host's 15 MB binary cap) instead of inlining it, so the page is "
                         "no longer the resolution ceiling; publish them with the page.")
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
        category_scale=category_scale)

    out_path = REPO / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    bin_files = None
    if args.external_bin:
        bin_files = []
        for name, chunk in split_blob(blob, out_path.stem):
            (out_path.parent / name).write_bytes(chunk)
            bin_files.append({"path": name, "bytes": len(chunk)})
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
