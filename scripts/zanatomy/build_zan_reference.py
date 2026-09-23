"""Q143: build the "Z-Anatomy reference model" -- a standalone, UNREGISTERED generic
body (a third viewer bundle, not a transfer onto either Visible Human specimen). Q142
found that registering Z-Anatomy onto our real subjects is too inaccurate to ship
(centroid error 18-83mm, dice < 0.5 on every one of 14 tested structures); this instead
ships Z-Anatomy's own internally-consistent geometry, in this project's atlas frame, as
its own body, badged everywhere as a generic CC BY-SA 4.0 reference rather than as
either specimen.

Writes two `build/vh/<subject>/{manifest.json,vertices.f32,faces.u32}` subject folders
in exactly the layout `scripts/export_viewer_bundle.py` already reads (see that
module's `main()`), split by system per the task's size-budget escape hatch:

  - zan_ref_msk: Skeletal + Muscular + Joints (bone/muscle/tendon/ligament/fascia/
    bursa/cartilage) -- the musculoskeletal half.
  - zan_ref_nv:  Nervous + CardioVascular + Visceral + Lymphoid (nerve/vessel/organ/
    lymphatic) -- the neurovascular/visceral half.

Every structure in both is one of:

  1. A MATCHED entity: this project's own entity id (so its real record's TA name/
     region attach in the exporter automatically), geometry via
     `scripts/zanatomy/zan_source.py.load_source()` unchanged -- reusing Q142's own
     loader fixes (drop UI-highlight duplicate objects, drop skeletal "decal"
     objects filed under the wrong system, pick the right sub-part per entity,
     union genuinely distinct sub-parts like the two ECU heads into one mesh).
  2. An ORPHAN: no confident/exact match to any of our entities (name_map status
     ambiguous/unmatched/grouped) -- kept anyway (never dropped just for being
     unmapped) under a STABLE id derived from the Z-Anatomy name (`zan_<slug>[_r|_l]`),
     with that Z-Anatomy name displayed verbatim as the record's `name` -- never a
     guessed mapping to one of our entities. The same highlight-duplicate dedup rule
     Q142 used (objects sharing a stripped base name are the same real structure;
     keep only the largest) is reapplied here, independently, since these never
     entered `zan_source`'s own per-atlas-id grouping.

The 30 objects `extract_fbx.py` flagged non-commercial (inner ear, kidney -- both
under a licence separate from and incompatible with the rest of the CC BY-SA 4.0
release) are excluded outright in both paths: they never carry a confident/exact
match (their own name_map status is `excluded_nc_licensed`, never a candidate for
either MATCHED or ORPHAN), so no extra filter is needed here beyond selecting the
statuses this script actually reads.

ORIGIN: the midpoint of the two hip joint centres, this project's own atlas-frame
convention (see docs/ARCHITECTURE.md and `scripts/ingest_vh_geometry.py`'s own
`--origin` measurement, which does the same thing off a femoral head CARTILAGE
mesh). Z-Anatomy ships no separate femoral head cartilage object, so this uses a
cheap proxy instead: a least-squares sphere fit (`engine.vh_ingest.fit_sphere`) to
each Femur.l/.r mesh's own proximal-most 15mm-by-atlas-Y cap. Measured directly
(not assumed): that cap fits a sphere to RMS 0.36mm (82 vertices/side, radius
~23.2mm, a physiologically plausible femoral head); the fit degrades sharply past
about 25mm as the neck and greater trochanter start contributing non-spherical
vertices (RMS 8+mm at 30mm). The two sides mirror exactly in X (83.7 / -83.7mm), the
usual check that side and axis are both right. All geometry (matched AND orphan) is
shifted by this one origin so the bundle sits in the same frame convention as the two
specimen bundles, even though it registers to neither.

Usage (the exact Q143 build -- see PROJECT_STATE.md for why these two budget scales):
    python3 scripts/zanatomy/build_zan_reference.py
    BADGE="Z-Anatomy (CC BY-SA 4.0) generic reference model -- not segmented from a specimen"
    python3 scripts/export_viewer_bundle.py --subject zan_ref_msk -o build/viewer_zan_msk \\
        --budget-scale 0.35 --force-badge "$BADGE" --strip-clinical \\
        --subject-label "Z-Anatomy reference model (musculoskeletal)"
    python3 scripts/export_viewer_bundle.py --subject zan_ref_nv -o build/viewer_zan_nv \\
        --budget-scale 0.5 --sheet-categories nerve,vessel --force-badge "$BADGE" --strip-clinical \\
        --subject-label "Z-Anatomy reference model (neurovascular / visceral)"
    python3 scripts/build_viewer_html.py --bundle build/viewer_zan_msk \\
        -o build/viewer_zan/atlas_viewer_zanatomy_msk.html --title "Z-Anatomy Reference (MSK)"
    python3 scripts/build_viewer_html.py --bundle build/viewer_zan_nv \\
        -o build/viewer_zan/atlas_viewer_zanatomy_nv.html --title "Z-Anatomy Reference (Neurovascular)"
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from engine.vh_ingest import fit_sphere  # noqa: E402
from scripts.zanatomy.map_names import strip_suffix  # noqa: E402
from scripts.zanatomy.zan_source import (  # noqa: E402
    DEFAULT_INVENTORY, DEFAULT_NAMEMAP, DEFAULT_ZAN_DIR, load_source,
    safe_filename, to_atlas_frame,
)
from scripts.zanatomy.apply_corrections import (  # noqa: E402
    DEFAULT_CORRECTIONS_DIR, apply_correction, load_corrections,
)

BUILD_VH = REPO / "build" / "vh"

FRAME = "atlas: +X right, +Y superior, +Z anterior, millimetres"

PINNED_COMMIT = "6c7f9016bd5899ac8edafd31b9900c151df42ed6"

ATTRIBUTION = [
    "Z-Anatomy (CC BY-SA 4.0; app and rig by Lluis Vinent Juanico, "
    "https://www.z-anatomy.com), whose models derive from BodyParts3D "
    "(CC BY-SA 2.1 Japan, Database Center for Life Science, Japan) -- both credits "
    "required together, see third_party/z-anatomy/NOTICE. Pinned clone commit "
    f"{PINNED_COMMIT}. A generic reference body, not segmented from any specimen, and "
    "NOT registered to either of this project's own Visible Human subjects -- Q142 "
    "found registration too inaccurate to ship (centroid error 18-83mm, dice < 0.5 on "
    "every tested structure); see PROJECT_STATE.md Q142/Q143. 30 objects the release's "
    "own licence file marks non-commercial (inner ear, kidney) are excluded outright, "
    "independent of this CC BY-SA layer.",
]

BADGE = (
    "Z-Anatomy (CC BY-SA 4.0) generic reference model — not segmented from a "
    "specimen, and not registered to this project's own Visible Human subjects "
    f"(pinned clone commit {PINNED_COMMIT}; see PROJECT_STATE.md Q143)."
)

# Q143's own coarse category for a Z-Anatomy system, used only for the ORPHAN pool
# (a matched entity already carries this project's own category via its real entity
# record). Joints is a mix of ligament/capsule/cartilage/bursa/tendon; refined by a
# name-substring check below rather than lumped as one category, since the exporter's
# triangle budget (scripts/export_viewer_bundle.py BUDGET) differs sharply between them.
_SYSTEM_CATEGORY = {
    "Muscular": "muscle", "Skeletal": "bone", "Nervous": "nerve",
    "CardioVascular": "vessel", "Visceral": "organ", "Lymphoid": "lymphatic",
}
_JOINTS_HINTS = (
    ("cartilage", "cartilage"), ("meniscus", "cartilage"), ("labrum", "cartilage"),
    ("intervertebral disc", "cartilage"), ("bursa", "bursa"), ("tendon", "tendon"),
)


def classify_orphan_category(name: str, system: str) -> str:
    if system == "Muscular":
        return "tendon" if "tendon" in name.lower() else "muscle"
    if system == "Joints":
        low = name.lower()
        for needle, cat in _JOINTS_HINTS:
            if needle in low:
                return cat
        return "ligament"  # Joints is predominantly capsules/ligaments
    return _SYSTEM_CATEGORY.get(system, "other")


# musculoskeletal vs neurovascular/visceral split, task's own size-budget escape
# hatch (point 4): applied by CATEGORY, not by Z-Anatomy system, so a matched
# entity (whose category is OUR atlas's, e.g. "cartilage") and an orphan (whose
# category came from classify_orphan_category above) land the same way.
_MSK_CATS = {"bone", "muscle", "tendon", "ligament", "fascia", "bursa", "cartilage"}


def bundle_of(cat: str) -> str:
    return "zan_ref_msk" if cat in _MSK_CATS else "zan_ref_nv"


_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    s = _SLUG_RE.sub("_", name.lower()).strip("_")
    return s or "unnamed"


def compute_origin(zan_dir: Path) -> tuple[np.ndarray, dict]:
    """Hip joint centre midpoint -- see module docstring for the method and the
    measured numbers that justify the 15mm cap."""
    report = {}
    centres = []
    for side in ("r", "l"):
        path = Path(zan_dir) / "Skeletal" / f"{safe_filename(f'Femur.{side}')}.npz"
        d = np.load(path)
        v = to_atlas_frame(d["vertices_mm"])
        ymax = float(v[:, 1].max())
        cap = v[v[:, 1] > ymax - 15.0]
        centre, radius, rms = fit_sphere(cap)
        centres.append(centre)
        report[side] = {
            "centre_mm": [round(float(x), 2) for x in centre],
            "radius_mm": round(float(radius), 2), "rms_mm": round(float(rms), 3),
            "n_points": int(len(cap)),
        }
    origin = (centres[0] + centres[1]) / 2.0
    mirror_x_mm = abs(report["r"]["centre_mm"][0] + report["l"]["centre_mm"][0])
    report["origin_mm"] = [round(float(x), 2) for x in origin]
    report["mirror_x_check_mm"] = round(mirror_x_mm, 3)
    report["method"] = (
        "least-squares sphere fit (engine.vh_ingest.fit_sphere) to each Femur.l/.r "
        "mesh's own proximal-most 15mm-by-atlas-Y cap -- a cheap proxy for the "
        "femoral head ball (Z-Anatomy ships no separate femoral head cartilage "
        "object); see module docstring for the RMS-vs-cap-size measurement that "
        "picked 15mm."
    )
    return origin, report


def build_orphan_pool(inventory: dict, namemap: dict):
    """{stable_id: {'name','system','side','category','mesh_names'[one]}} for every
    Z-Anatomy object the name_map could not confidently/exactly match to one of this
    project's own entities (and that is not the 30 non-commercial-licensed ones,
    which never carry these statuses) -- deduplicated of Z-Anatomy's own UI-highlight
    copies exactly like `zan_source.load_source()` dedupes them for the matched pool,
    just independently, since these never entered that function's per-atlas-id
    grouping."""
    objs_by_name = {o["name"]: o for o in inventory["objects"]}
    groups: dict[tuple, list] = {}
    zero_face = 0
    for e in namemap["entries"]:
        if e["status"] not in ("ambiguous", "unmatched", "grouped"):
            continue
        obj = objs_by_name[e["zanatomy_name"]]
        if obj["face_count"] == 0:
            # 6 objects release-wide (eyeball equator/meridian curves, a ciliary-body
            # and zonular-fibre curve, an oesophagus profile line, a medulla path) are
            # wireframe annotation curves with vertices but NO triangles at all -- not
            # tissue surface geometry, the same kind of diagram overlay extract_fbx.py
            # already excludes whole-file for "Regions of human body"/"References".
            zero_face += 1
            continue
        base = strip_suffix(e["zanatomy_name"])
        groups.setdefault((obj["system"], obj.get("side"), base), []).append(obj)

    out = {}
    used_ids: set[str] = set()
    dropped_as_dupe = 0
    for (system, side, base), cands in groups.items():
        # Every candidate here already shares one (system, side, stripped-base-name)
        # key, so -- unlike zan_source's per-atlas-id grouping, which can combine
        # candidates with genuinely DIFFERENT stripped names as distinct real
        # sub-parts -- these are always Z-Anatomy's own UI-highlight copies of the
        # SAME real object (module docstring). Keep only the largest.
        dropped_as_dupe += len(cands) - 1
        rep = max(cands, key=lambda c: c["vertex_count"])
        stable = "zan_" + slugify(base) + ({"right": "_r", "left": "_l"}.get(side, ""))
        if stable in used_ids:
            n = 2
            while f"{stable}_{n}" in used_ids:
                n += 1
            stable = f"{stable}_{n}"
        used_ids.add(stable)
        out[stable] = {
            "name": base, "system": system, "side": side,
            "category": classify_orphan_category(base, system),
            "mesh_name": rep["name"], "vertex_count": rep["vertex_count"],
        }
    return out, dropped_as_dupe, zero_face


def load_mesh(zan_dir: Path, system: str, name: str, origin: np.ndarray):
    path = Path(zan_dir) / system / f"{safe_filename(name)}.npz"
    d = np.load(path)
    v = to_atlas_frame(d["vertices_mm"]) - origin
    return v.astype(np.float64), d["faces"].astype(np.int64)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--inventory", default=str(DEFAULT_INVENTORY))
    ap.add_argument("--namemap", default=str(DEFAULT_NAMEMAP))
    ap.add_argument("--zan-dir", default=str(DEFAULT_ZAN_DIR))
    ap.add_argument("--report", default=str(REPO / "data" / "derived" / "Q143_zan_reference_report.json"))
    args = ap.parse_args(argv)

    zan_dir = Path(args.zan_dir)
    inventory = json.loads(Path(args.inventory).read_text())
    namemap = json.loads(Path(args.namemap).read_text())

    origin, origin_report = compute_origin(zan_dir)
    print("hip joint centre origin (mm):", origin_report["origin_mm"],
          "mirror-x check:", origin_report["mirror_x_check_mm"])

    matched = load_source(inventory_path=args.inventory, namemap_path=args.namemap, zan_dir=zan_dir)
    orphans, dropped_dupe, zero_face = build_orphan_pool(inventory, namemap)
    print(f"matched (our entity ids): {len(matched)}   "
          f"orphans (stable zan_ ids): {len(orphans)}   "
          f"(dropped {dropped_dupe} orphan UI-highlight duplicates, "
          f"{zero_face} zero-face annotation curves)")

    buckets: dict[str, dict] = {"zan_ref_msk": {"verts": [], "faces": [], "structures": []},
                                 "zan_ref_nv": {"verts": [], "faces": [], "structures": []}}
    counts_by_cat: Counter = Counter()
    matched_ids_shipped = []

    corrections = load_corrections()
    for aid, rec in matched.items():
        raw_v = rec["v"].astype(np.float64)
        # Q144: any declarative correction (data/corrections/zanatomy/*.json)
        # applies here, on the RAW atlas-frame mesh before the hip-origin
        # subtraction below (the same frame `apply_correction` fits the lateral
        # epicondyle in) -- a no-op (v unchanged, note=None) for every id that
        # carries no correction, i.e. every bundle before this one is unaffected.
        raw_v, correction_note = apply_correction(aid, raw_v, DEFAULT_ZAN_DIR, corrections)
        v = raw_v - origin
        f = rec["f"].astype(np.int64)
        cat = rec["cat"]
        bkey = bundle_of(cat)
        b = buckets[bkey]
        voff = sum(len(x) for x in b["verts"])
        foff = sum(len(x) for x in b["faces"])
        b["verts"].append(v)
        b["faces"].append(f)
        structure = {
            "atlas_id": aid, "side": rec.get("side"),
            "vertex_offset": voff, "face_offset": foff,
            "vertex_count": len(v), "triangle_count": len(f),
            "bbox_min_mm": [round(float(x), 2) for x in v.min(axis=0)],
            "bbox_max_mm": [round(float(x), 2) for x in v.max(axis=0)],
            "source_structure": "+".join(rec.get("zanatomy_parts") or []),
        }
        if rec.get("base_atlas_id"):
            # Q144: a nerve id this build split by side (zan_source.py) has no
            # entity record of its own under the SUFFIXED id (this project's own
            # nerve registry is not split by side) -- export_viewer_bundle.py's
            # own atlas.get(aid) will miss, so give it the same explicit
            # name/region/category fallback an orphan (no entity record at all)
            # already gets, sourced from the real (base, unsuffixed) record.
            structure["category"] = cat
            structure["region"] = rec["rec"].get("region")
            side_word = {"_r": "right", "_l": "left"}.get(aid[-2:], "")
            base_name = rec.get("base_name") or rec["base_atlas_id"]
            structure["name"] = f"{base_name} ({side_word})" if side_word else base_name
        if correction_note:
            structure["correction_note"] = correction_note
        b["structures"].append(structure)
        counts_by_cat[cat] += 1
        matched_ids_shipped.append(aid)

    orphan_examples: dict[str, str] = {}
    for stable, meta in orphans.items():
        v, f = load_mesh(zan_dir, meta["system"], meta["mesh_name"], origin)
        cat = meta["category"]
        bkey = bundle_of(cat)
        b = buckets[bkey]
        voff = sum(len(x) for x in b["verts"])
        foff = sum(len(x) for x in b["faces"])
        b["verts"].append(v)
        b["faces"].append(f)
        b["structures"].append({
            "atlas_id": stable, "side": meta["side"],
            "vertex_offset": voff, "face_offset": foff,
            "vertex_count": len(v), "triangle_count": len(f),
            "bbox_min_mm": [round(float(x), 2) for x in v.min(axis=0)],
            "bbox_max_mm": [round(float(x), 2) for x in v.max(axis=0)],
            "source_structure": meta["mesh_name"],
            "category": cat,           # Q143: read by export_viewer_bundle.py's fallback
            "name": meta["name"],      # -- an orphan has no entity record to pull these from
        })
        counts_by_cat[cat] += 1
        if cat not in orphan_examples:
            orphan_examples[cat] = meta["name"]

    for subject, b in buckets.items():
        out_dir = BUILD_VH / subject
        out_dir.mkdir(parents=True, exist_ok=True)
        verts = np.concatenate(b["verts"]).astype(np.float32) if b["verts"] else np.zeros((0, 3), np.float32)
        # faces are per-structure LOCAL indices (0-based within that structure's own
        # vertex block) -- exactly what scripts/export_viewer_bundle.py's own loop
        # expects (it subtracts vertex_offset right back off before use), so no
        # global re-basing is done here.
        faces_local = [f for f in b["faces"]]
        faces_global = []
        voff = 0
        for f, s in zip(faces_local, b["structures"]):
            faces_global.append(f + voff)
            voff += s["vertex_count"]
        faces = np.concatenate(faces_global).astype(np.uint32) if faces_global else np.zeros((0, 3), np.uint32)
        # face_offset must be in units of TRIANGLES into this concatenated array
        foff = 0
        for s, f in zip(b["structures"], faces_local):
            s["face_offset"] = foff
            foff += len(f)

        (out_dir / "vertices.f32").write_bytes(verts.tobytes())
        (out_dir / "faces.u32").write_bytes(faces.tobytes())
        manifest = {
            "subject": subject,
            "frame": FRAME,
            "source_volume": "Z-Anatomy FBX release (see scripts/zanatomy/extract_fbx.py)",
            "source_kind": "Z-Anatomy (CC BY-SA 4.0) generic reference model, unregistered",
            "vertex_count": int(len(verts)),
            "triangle_count": int(len(faces)),
            "bbox_min_mm": [round(float(x), 2) for x in verts.min(axis=0)] if len(verts) else None,
            "bbox_max_mm": [round(float(x), 2) for x in verts.max(axis=0)] if len(verts) else None,
            "attribution": ATTRIBUTION,
            "structures": b["structures"],
        }
        (out_dir / "manifest.json").write_text(json.dumps(manifest))
        print(f"{subject}: {len(b['structures'])} structures, {len(faces):,} triangles -> {out_dir}")

    split_ids = sorted(aid for aid, rec in matched.items() if rec.get("base_atlas_id"))
    corrected_ids = sorted(
        s["atlas_id"] for b in buckets.values() for s in b["structures"] if s.get("correction_note"))
    report = {
        "source": (
            "Q143 (2026-09-23): builds the Z-Anatomy reference model bundle -- a standalone, "
            "unregistered generic body, badged everywhere as Z-Anatomy CC BY-SA 4.0, not "
            "registered to either Visible Human specimen (Q142 found registration too "
            "inaccurate to ship). Q144 (2026-09-23) added the side-split fix for sideless "
            "nerve ids (zan_source.py) and the radial-nerve-pathway correction "
            "(data/corrections/zanatomy/radial_n.json) applied here. See "
            "scripts/zanatomy/build_zan_reference.py."
        ),
        "origin": origin_report,
        "counts_by_category": dict(counts_by_cat),
        "matched_entities": len(matched),
        "q144_side_split_ids": split_ids,
        "q144_side_split_count": len(split_ids),
        "q144_corrected_ids": corrected_ids,
        "orphan_structures": len(orphans),
        "orphan_dropped_as_ui_highlight_duplicate": dropped_dupe,
        "orphan_dropped_as_zero_face_annotation_curve": zero_face,
        "orphan_example_name_by_category": orphan_examples,
        "subjects": {s: {"structures": len(b["structures"]),
                          "triangles": int(sum(len(f) for f in b["faces"]))}
                     for s, b in buckets.items()},
    }
    Path(args.report).write_text(json.dumps(report, indent=1))
    print(f"wrote {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
