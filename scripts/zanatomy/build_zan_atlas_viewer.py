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
    DEFAULT_INVENTORY, DEFAULT_NAMEMAP, DEFAULT_ZAN_DIR, load_source,
    safe_filename, to_atlas_frame,
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


def decimate(v: np.ndarray, f: np.ndarray, mesh_id: str, cat: str, scale: float):
    budget = max(150, int(BUDGET_OVERRIDES.get(mesh_id, BUDGET.get(cat, DEFAULT_BUDGET)) * scale))
    if mesh_id in SHEET_IDS:
        q = decimate_quadric(v, f, budget)
        if q is not None:
            return q
    dv, df, _cell = decimate_to(v, f, budget)
    if len(df) == 0:
        dv, df = v, f
    if len(dv) > MAX_VERTS:
        dv, df, _cell = decimate_to(v, f, min(budget, MAX_VERTS - 1))
    return dv, df


def build(*, zan_dir: Path, inventory_path: Path, namemap_path: Path,
          corrections_dir: Path, budget_scale: float):
    inventory = json.loads(Path(inventory_path).read_text())
    namemap = json.loads(Path(namemap_path).read_text())

    matched = load_source(inventory_path=inventory_path, namemap_path=namemap_path, zan_dir=zan_dir)
    orphans, dropped_dupe, zero_face = build_orphan_pool(inventory, namemap)
    origin, origin_report = compute_origin(zan_dir)
    corrections = load_corrections(corrections_dir)
    atlas_records = load_atlas_records()
    id_to_cat = {e.entity_id: e.category for e in load_full_atlas()}

    meshes: list[dict] = []
    bin_chunks: list[bytes] = []
    byte_off = 0
    seen_ids: set[str] = set()
    counts_by_layer: Counter = Counter()
    counts_by_category: Counter = Counter()
    corrected_ids: list[str] = []
    matched_with_record = 0

    def emit(mesh_id: str, display_name: str, side_raw, cat: str, v_raw: np.ndarray, f: np.ndarray,
              rec_override=None, zanatomy_name: str | None = None):
        nonlocal byte_off, matched_with_record
        if mesh_id in seen_ids:
            raise ValueError(f"duplicate atlas id emitted twice: {mesh_id}")
        seen_ids.add(mesh_id)

        warped, note = apply_correction(mesh_id, v_raw, zan_dir, corrections)
        v = warped - origin
        dv, df = decimate(v, f, mesh_id, cat, budget_scale)

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
        emit(stable, meta["name"], meta["side"], meta["category"], v_raw, f, zanatomy_name=meta["name"])

    # sanity this build's own two invariants (also re-checked by
    # tests/test_build_zan_atlas_viewer.py against the real, committed output):
    ids = [m["id"] for m in meshes]
    assert len(ids) == len(set(ids)), "exporter produced a duplicate id"
    for m in meshes:
        assert "clinical" not in (m.get("rec") or {}), f"{m['id']} carries a clinical key"

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
            "corrected_ids": corrected_ids,
        },
        "meshes": meshes,
    }
    blob = b"".join(bin_chunks)
    return manifest, blob, origin_report


def render_html(manifest: dict, blob: bytes) -> str:
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    manifest_json = json.dumps(manifest, separators=(",", ":")).replace("</", "<\\/")
    b64 = base64.b64encode(blob).decode("ascii")
    if "</script" in b64.lower():
        raise SystemExit("base64 payload contains a script terminator")
    html = template.replace("__MANIFEST_JSON__", manifest_json, 1)
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
    ap.add_argument("-o", "--out", default="build/viewer_zan_atlas/atlas_viewer_zan_atlas.html")
    ap.add_argument("--report", default=str(REPO / "data" / "derived" / "Q157_zan_atlas_report.json"))
    args = ap.parse_args(argv)

    manifest, blob, origin_report = build(
        zan_dir=Path(args.zan_dir), inventory_path=Path(args.inventory), namemap_path=Path(args.namemap),
        corrections_dir=Path(args.corrections_dir), budget_scale=args.budget_scale)

    html = render_html(manifest, blob)
    out_path = REPO / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
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
        "binary_bytes": len(blob),
        "html_bytes": len(html),
        **manifest["totals"],
    }
    Path(args.report).write_text(json.dumps(report, indent=1))

    print(f"meshes: {manifest['totals']['meshes']}  "
          f"(matched {manifest['totals']['matched_entities']}, "
          f"orphan {manifest['totals']['orphan_structures']})")
    print("by layer:", manifest["totals"]["by_layer"])
    print("by category:", manifest["totals"]["by_category"])
    print(f"corrected ids: {manifest['totals']['corrected_ids']}")
    print(f"binary {len(blob)/1e6:.2f} MB -> html {len(html)/1e6:.2f} MB -> {out_path}")
    print(f"wrote {args.report}")
    if len(html) > 15_000_000:
        print(f"WARNING: {len(html)/1e6:.2f} MB exceeds the 15 MB page budget; "
              f"re-run with a smaller --budget-scale", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
