#!/usr/bin/env python3
"""Ingest the Visible Human lower-extremity geometry into the atlas.

Source: Andreassen TE, Hume DR, Hamilton LD, Walker KE, Higinbotham SE,
Shelburne KB. "Three Dimensional Lower Extremity Musculoskeletal Geometry of
the Visible Human Female and Male." Sci Data 10:34 (2023).
doi:10.1038/s41597-022-01905-2 -- reported CC BY 4.0, CONFIRM AT SOURCE.
Underlying imagery courtesy of the U.S. National Library of Medicine.

Download the data yourself and point this script at the folder. Nothing here
reaches the network.

    Digital Commons @ DU   https://digitalcommons.du.edu/visiblehuman/
                           doi:10.56902/COB.vh.2022.0
    SimTK mirror           https://simtk.org/projects/3d-vh-geometry

Take the **"Final 3D STL models"** folder -- 87.8 MB zipped, 117 MB extracted,
split into a Right and a Left download. Those meshes are already smoothed,
overlap-free and corrected to a uniform 0.05 mm gap, so they need no further
processing. Start with Right: the atlas names motor targets on the right side.

Note what "final" costs. Those models were remeshed to target edge lengths of
1.5 mm (muscle), 1.0 mm (bone) and 0.75 mm (cartilage, ligament) -- coarser
than this project's sub-millimetre goal. For true sub-millimetre surface
detail use the **raw** STL models instead, written at ScanIP's ~0.33 mm
default, at the cost of the segmentation artefacts the smoothing removed.
This script reads either; see docs/GEOMETRY_SOURCES.md.

Run the three steps in order. Each one stops and shows you its work before
anything is written to data/.

  1.  inspect   What is actually in the folder: files, structure names,
                triangle counts, bounding box, and a guess at units and
                up-axis. Writes a report; changes nothing.

  2.  propose   Match those structure names against the atlas's own entity
                IDs and write an editable mapping file. Every match carries
                a score and its runners-up. REVIEW THIS FILE BY HAND -- the
                matcher is string similarity, not anatomy.

  3.  convert   Apply the reviewed mapping, transform into the atlas frame,
                and emit indexed geometry plus a manifest.

Step 3 refuses to guess the coordinate frame. Pass --axes and --units
explicitly, using what step 1 reported.

Examples
--------
    python3 scripts/ingest_vh_geometry.py inspect ~/vh/VHM
    python3 scripts/ingest_vh_geometry.py propose ~/vh/VHM --subject vhm
    $EDITOR build/vh/vhm_mapping.json
    python3 scripts/ingest_vh_geometry.py convert ~/vh/VHM --subject vhm \\
        --axes '+x,+z,-y' --units mm
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from engine import vh_ingest as vh  # noqa: E402

MESH_SUFFIXES = {".stl", ".obj", ".ply"}
BUILD_DIR = REPO_ROOT / "build" / "vh"

# Structures the DU release ships that this atlas has no category for. Not
# errors -- just noted, so they do not sit in the unmatched list forever.
KNOWN_UNMAPPABLE = ("fat", "dermis", "epidermis", "skin", "fascia_outer")


# --------------------------------------------------------------------------
# shared helpers
# --------------------------------------------------------------------------

def find_meshes(root: Path) -> list[Path]:
    if not root.is_dir():
        raise SystemExit(f"Not a directory: {root}")
    found = sorted(p for p in root.rglob("*") if p.suffix.lower() in MESH_SUFFIXES)
    if not found:
        raise SystemExit(
            f"No mesh files under {root}.\n"
            f"Looked for: {', '.join(sorted(MESH_SUFFIXES))}\n"
            f"The DU release ships STL alongside 3D Slicer masks and image "
            f"stacks -- point this at the folder holding the STL geometry."
        )
    return found


def structure_name(path: Path, root: Path) -> str:
    """Best available name for a mesh: its filename, and its parent folder
    when that folder is not just a bulk container."""
    stem = path.stem
    parent = path.parent.name
    if path.parent != root and parent.lower() not in {"stl", "meshes", "geometry", "processed", "raw"}:
        return f"{parent} {stem}"
    return stem


def load_mesh(path: Path) -> np.ndarray:
    if path.suffix.lower() == ".stl":
        return vh.read_stl(path)
    raise SystemExit(
        f"{path.name}: only STL is implemented. The DU release provides STL; "
        f"convert other formats first (e.g. with meshio) or extend engine/vh_ingest.py."
    )


# --------------------------------------------------------------------------
# 1. inspect
# --------------------------------------------------------------------------

def cmd_inspect(args: argparse.Namespace) -> int:
    root = Path(args.directory).expanduser().resolve()
    meshes = find_meshes(root)
    print(f"{len(meshes)} mesh file(s) under {root}\n")

    records = []
    lo = np.full(3, np.inf)
    hi = np.full(3, -np.inf)
    failed = []

    for path in meshes:
        try:
            tris = load_mesh(path)
        except Exception as exc:                                  # noqa: BLE001
            failed.append((path.relative_to(root).as_posix(), str(exc)))
            continue
        pts = tris.reshape(-1, 3)
        mn, mx = pts.min(axis=0), pts.max(axis=0)
        lo = np.minimum(lo, mn)
        hi = np.maximum(hi, mx)
        raw = structure_name(path, root)
        base, side = vh.split_side(raw)
        records.append({
            "file": path.relative_to(root).as_posix(),
            "raw_name": raw,
            "structure": base,
            "side": side,
            "normalised": vh.normalise(base),
            "triangles": int(tris.shape[0]),
            "bbox_min": [float(v) for v in mn],
            "bbox_max": [float(v) for v in mx],
        })

    if not records:
        raise SystemExit("Every mesh failed to read. See the errors above.")

    sides = Counter(r["side"] or "none" for r in records)
    total_tris = sum(r["triangles"] for r in records)
    print(f"triangles      {total_tris:,} across {len(records)} structures")
    print(f"side markers   " + ", ".join(f"{k}={v}" for k, v in sorted(sides.items())))
    if sides.get("none"):
        print(f"               {sides['none']} file(s) carry no side marker -- "
              f"midline structures, or a naming convention split_side() misses.")

    frame = vh.infer_frame(lo, hi)
    print("\ncoordinate frame")
    print(f"  bbox min     {np.array2string(np.array(frame.bbox_min), precision=3)}")
    print(f"  bbox max     {np.array2string(np.array(frame.bbox_max), precision=3)}")
    print(f"  extent       {np.array2string(np.array(frame.extent), precision=3)}")
    print(f"  units guess  {frame.guessed_units or 'UNRECOGNISED'}")
    for note in frame.notes:
        print(f"  - {note}")

    # The atlas puts its origin at the midpoint of the hip joint centres
    # (docs/ARCHITECTURE.md). Converted geometry otherwise sits wherever the
    # scanner's volume corner happened to be, which is nowhere in particular,
    # and would miss every anchor in data/rig/anchors.json. Report the
    # measurement; let the human pass it back in via --origin.
    head = next((p for p in meshes
                 if "cartilage" in p.name.lower() and "femurhead" in
                 p.name.lower().replace("_", "")), None)
    if head is not None:
        centre, radius, rms = vh.fit_sphere(load_mesh(head).reshape(-1, 3))
        print("\nhip joint centre (from the femoral head cartilage)")
        print(f"  source mesh  {head.name}")
        print(f"  centre       {np.array2string(centre, precision=2)}  (source units)")
        print(f"  radius       {radius:.2f}   rms residual {rms:.3f}")
        if rms > 1.5:
            print("  - POOR FIT. A femoral head fits a sphere to well under a "
                  "millimetre; this does not, so do not use this centre.")
        else:
            print("  - Good fit. This is one hip centre. The atlas origin is the "
                  "MIDPOINT OF BOTH, so it lies on the sagittal midline at this "
                  "height and depth -- take the midline coordinate from the "
                  "medial face of the pubic symphysis, and pass the result to "
                  "convert as --origin.")
    else:
        print("\nhip joint centre: no femoral head cartilage mesh found, so the "
              "atlas origin cannot be measured from this folder. convert will "
              "leave the geometry in the source's own origin unless you pass "
              "--origin explicitly.")

    print("\nlargest structures")
    for rec in sorted(records, key=lambda r: -r["triangles"])[:12]:
        side = f" [{rec['side']}]" if rec["side"] else ""
        print(f"  {rec['triangles']:>9,}  {rec['structure']}{side}")

    if failed:
        print(f"\n{len(failed)} file(s) could not be read")
        for name, err in failed[:10]:
            print(f"  {name}: {err}")

    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    out = BUILD_DIR / f"{args.subject}_inspect.json"
    out.write_text(json.dumps({
        "source_directory": str(root),
        "structures": records,
        "failed": [{"file": f, "error": e} for f, e in failed],
        "frame": {
            "bbox_min": frame.bbox_min,
            "bbox_max": frame.bbox_max,
            "extent": frame.extent,
            "longest_axis": frame.longest_axis,
            "guessed_units": frame.guessed_units,
            "notes": frame.notes,
        },
    }, indent=2))
    print(f"\nwrote {out.relative_to(REPO_ROOT)}")
    print("next: propose")
    return 0


# --------------------------------------------------------------------------
# 2. propose
# --------------------------------------------------------------------------

def cmd_propose(args: argparse.Namespace) -> int:
    root = Path(args.directory).expanduser().resolve()
    inspect_file = BUILD_DIR / f"{args.subject}_inspect.json"
    if inspect_file.exists():
        records = json.loads(inspect_file.read_text())["structures"]
        print(f"using {inspect_file.relative_to(REPO_ROOT)} ({len(records)} structures)")
    else:
        print("no inspect report found; scanning filenames only (no geometry read)")
        records = []
        for path in find_meshes(root):
            raw = structure_name(path, root)
            base, side = vh.split_side(raw)
            records.append({
                "file": path.relative_to(root).as_posix(),
                "raw_name": raw, "structure": base, "side": side,
                "normalised": vh.normalise(base), "triangles": None,
            })

    atlas = vh.load_atlas_index()
    print(f"atlas index: {len(atlas)} entities across "
          f"{len(set(e.category for e in atlas))} categories")
    overrides = vh.load_overrides()
    print(f"curated overrides: {len(overrides)}\n")

    entries = []
    counts = Counter()
    for rec in records:
        cands = vh.propose_matches(rec["structure"], atlas, side=rec["side"], top_n=3)
        best = cands[0] if cands else None
        runner = cands[1] if len(cands) > 1 else None
        note = None

        override = overrides.get(vh.override_key(rec["structure"]) or "")
        if override is not None:
            # A reviewed decision outranks any score. These are the cases the
            # matcher cannot settle -- the release names cartilage by bone
            # surface where the atlas names it by joint, and ships seven
            # tarsals where the atlas carries one entity.
            resolved = vh.apply_override(override, rec["side"])
            status, chosen = "curated", resolved["atlas_id"]
            note = f"{resolved['relationship']}: {resolved['note']}"
        elif any(k in rec["normalised"] for k in KNOWN_UNMAPPABLE):
            status, chosen = "no_atlas_category", None
            note = "This tissue class has no counterpart in the atlas schema."
        elif best is not None and best.score >= vh.EXACT and (
                runner is None or runner.score < vh.EXACT):
            # An exact normalised match beats the ambiguity margin outright.
            status, chosen = "confident", best.entity_id
        elif best is None or best.score < args.min_score:
            grouped = vh.find_grouping_entity(rec["structure"], atlas, side=rec["side"])
            if grouped:
                status, chosen = "grouped", None
                cands = grouped
                note = (f"No 1:1 entity. The atlas carries this inside the coarser "
                        f"'{grouped[0].entity_id}'. Several source meshes will map "
                        f"onto that one ID -- decide whether to merge them or to "
                        f"split the atlas entity first.")
            else:
                status, chosen = "unmatched", None
        elif runner and (best.score - runner.score) < args.margin:
            status, chosen = "ambiguous", None
        else:
            status, chosen = "confident", best.entity_id

        counts[status] += 1
        entry = {
            "file": rec["file"],
            "source_structure": rec["structure"],
            "side": rec["side"],
            "status": status,
            "atlas_id": chosen,
            "candidates": [
                {"atlas_id": c.entity_id, "category": c.category,
                 "score": c.score, "matched_name": c.matched_name}
                for c in cands
            ],
        }
        if note:
            entry["note"] = note
        if override is not None:
            entry["relationship"] = resolved["relationship"]
            if resolved.get("compartment_id"):
                entry["compartment_id"] = resolved["compartment_id"]
        entries.append(entry)

    # Two meshes landing on one atlas entity is a real relationship -- the DU
    # release ships the two gastrocnemius heads separately where the atlas
    # carries one entity with fibre compartments -- but it must be a decision,
    # not a silent collapse. Downgrade those out of "confident".
    claim_counts = Counter(e["atlas_id"] for e in entries if e["atlas_id"])
    for entry in entries:
        entity_id = entry["atlas_id"]
        if entry["status"] == "curated":
            # Several meshes sharing one atlas_id is exactly what a reviewed
            # 'part_of' says should happen. Downgrading it would undo the
            # decision the override exists to record.
            continue
        if entity_id and claim_counts[entity_id] > 1:
            counts[entry["status"]] -= 1
            counts["grouped"] += 1
            entry["status"] = "grouped"
            entry["atlas_id"] = None
            entry["note"] = (
                f"{claim_counts[entity_id]} source meshes matched '{entity_id}'. "
                f"The atlas holds one entity where this dataset segments several "
                f"parts. Either set atlas_id on all of them to merge, or split "
                f"the atlas entity first."
            )

    mapped_ids = {e["atlas_id"] for e in entries if e["atlas_id"]}
    # A curated entry's atlas_id need not appear among its scored candidates
    # -- that is the point of curating it -- so fall back to the entity's own
    # category rather than reporting it as unknown.
    category_of = {e.entity_id: e.category for e in atlas}
    by_cat = Counter(
        next((c["category"] for c in e["candidates"] if c["atlas_id"] == e["atlas_id"]),
             category_of.get(e["atlas_id"], "?"))
        for e in entries if e["atlas_id"]
    )

    print(f"  curated             {counts['curated']}   (reviewed in mappings/du_vh_overrides.json)")
    print(f"  confident           {counts['confident']}")
    print(f"  ambiguous           {counts['ambiguous']}   (top two within {args.margin} -- pick one by hand)")
    print(f"  grouped             {counts['grouped']}   (atlas has a coarser entity covering this)")
    print(f"  unmatched           {counts['unmatched']}   (below --min-score {args.min_score})")
    print(f"  no atlas category   {counts['no_atlas_category']}")
    print(f"\n  auto-mapped by category: " + (", ".join(f"{k}={v}" for k, v in sorted(by_cat.items())) or "none"))

    for category, expected in vh.DU_EXPECTED_COUNTS.items():
        got = by_cat.get(category)
        if got is not None and got < expected:
            print(f"  note: {got}/{expected} expected {category} structures mapped automatically")

    # Several meshes on one atlas ID is only a problem when nobody decided it
    # should happen. A curated 'part_of' says exactly that it should -- seven
    # tarsal meshes onto one tarsals entity -- so those are reported as the
    # merges they are, and only the unreviewed collisions are warnings.
    claimed = Counter(e["atlas_id"] for e in entries if e["atlas_id"])
    curated_ids = {e["atlas_id"] for e in entries if e["status"] == "curated"}
    merges = sorted(i for i, n in claimed.items() if n > 1 and i in curated_ids)
    dupes = sorted(i for i, n in claimed.items() if n > 1 and i not in curated_ids)
    if merges:
        print(f"\n  {len(merges)} curated merge(s) -- several meshes to one entity, "
              f"as reviewed:")
        for entity_id in merges:
            print(f"    {entity_id}  <- {claimed[entity_id]} meshes")
    if dupes:
        print(f"\n  WARNING: {len(dupes)} atlas ID(s) claimed by more than one mesh "
              f"with no reviewed decision behind it:")
        for entity_id in dupes[:10]:
            print(f"    {entity_id}")

    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    out = BUILD_DIR / f"{args.subject}_mapping.json"
    if out.exists() and not args.force:
        raise SystemExit(
            f"\n{out.relative_to(REPO_ROOT)} already exists and may contain your edits.\n"
            f"Pass --force to overwrite it."
        )
    out.write_text(json.dumps({
        "_README": [
            "Review every entry before running convert.",
            "Set 'atlas_id' to the correct atlas entity, or null to skip this mesh.",
            "'status' is advisory; convert reads 'atlas_id' only.",
            "'candidates' are string-similarity suggestions, not anatomical judgements.",
        ],
        "subject": args.subject,
        "source_directory": str(root),
        "entries": entries,
    }, indent=2))
    print(f"\nwrote {out.relative_to(REPO_ROOT)}")
    print(f"next: review that file by hand, then convert")
    # mapped_ids is a set of entity IDs, so using it here undercounted every
    # curated merge: seven tarsal meshes share one ID and were reported as one.
    resolved_meshes = sum(1 for e in entries if e["atlas_id"])
    print(f"      {resolved_meshes} of {len(entries)} meshes currently have an "
          f"atlas_id, across {len(mapped_ids)} atlas entities")
    return 0


# --------------------------------------------------------------------------
# 3. convert
# --------------------------------------------------------------------------

def cmd_convert(args: argparse.Namespace) -> int:
    root = Path(args.directory).expanduser().resolve()
    mapping_file = BUILD_DIR / f"{args.subject}_mapping.json"
    if not mapping_file.exists():
        raise SystemExit(f"No mapping at {mapping_file}. Run 'propose' first.")

    mapping = json.loads(mapping_file.read_text())
    entries = [e for e in mapping["entries"] if e.get("atlas_id")]
    if not entries:
        raise SystemExit(
            f"{mapping_file.name} has no entry with an atlas_id set.\n"
            f"Review the file and assign IDs before converting."
        )

    still_open = [e for e in mapping["entries"]
                  if e["status"] in ("ambiguous", "unmatched") and not e.get("atlas_id")]
    if still_open and not args.allow_unreviewed:
        raise SystemExit(
            f"{len(still_open)} mesh(es) are still ambiguous or unmatched with no "
            f"atlas_id assigned, e.g.:\n"
            + "\n".join(f"  {e['source_structure']}" for e in still_open[:8])
            + f"\n\nResolve them in {mapping_file.name}, or pass --allow-unreviewed "
              f"to convert only what is mapped and drop the rest."
        )

    try:
        axes = vh.parse_axes(args.axes)
    except ValueError as exc:
        raise SystemExit(str(exc)) from None
    scale = vh.UNIT_SCALE_TO_MM[args.units]
    origin = np.zeros(3)
    if args.origin:
        try:
            origin = vh.parse_origin(args.origin)
        except ValueError as exc:
            raise SystemExit(str(exc)) from None
    print(f"axes {args.axes}  units {args.units} (x{scale})  {len(entries)} mesh(es)")
    if args.origin:
        print(f"origin {args.origin} (source units) -> atlas (0,0,0)")
    else:
        print("origin: NOT SET. Geometry keeps the source's own origin, which is "
              "the scanner volume corner, not the atlas's midpoint of the hip "
              "joint centres. It will not line up with data/rig/anchors.json. "
              "Run inspect to measure the hip centre, then pass --origin.")
    print()

    known = {e.entity_id for e in vh.load_atlas_index()}
    unknown = sorted({e["atlas_id"] for e in entries} - known)
    if unknown:
        raise SystemExit(
            f"{len(unknown)} atlas_id value(s) in the mapping do not exist in data/:\n"
            + "\n".join(f"  {i}" for i in unknown[:12])
            + "\n\nFix the mapping, or add those entities to the atlas first."
        )

    out_dir = Path(args.out).expanduser().resolve() if args.out else BUILD_DIR / args.subject
    out_dir.mkdir(parents=True, exist_ok=True)

    verts_blocks, faces_blocks, manifest = [], [], []
    vertex_base = 0
    lo = np.full(3, np.inf)
    hi = np.full(3, -np.inf)

    for entry in entries:
        path = root / entry["file"]
        if not path.exists():
            raise SystemExit(f"Missing mesh referenced by the mapping: {path}")
        tris = load_mesh(path)
        verts, faces = vh.weld(tris, tol_mm=args.weld_tol)
        # Translate in SOURCE units before rotating, so --origin is the
        # number inspect printed rather than something the caller has to
        # transform by hand first.
        verts = vh.to_atlas_frame(verts - origin, axes, scale)

        mn, mx = verts.min(axis=0), verts.max(axis=0)
        lo, hi = np.minimum(lo, mn), np.maximum(hi, mx)

        manifest.append({
            "atlas_id": entry["atlas_id"],
            "source_structure": entry["source_structure"],
            "side": entry["side"],
            "source_file": entry["file"],
            "vertex_offset": vertex_base,
            "vertex_count": int(verts.shape[0]),
            "triangle_count": int(faces.shape[0]),
            "bbox_min_mm": [round(float(v), 4) for v in mn],
            "bbox_max_mm": [round(float(v), 4) for v in mx],
        })
        verts_blocks.append(verts.astype(np.float32))
        faces_blocks.append((faces + vertex_base).astype(np.uint32))
        vertex_base += verts.shape[0]

    all_verts = np.concatenate(verts_blocks)
    all_faces = np.concatenate(faces_blocks)

    (out_dir / "vertices.f32").write_bytes(all_verts.tobytes())
    (out_dir / "faces.u32").write_bytes(all_faces.tobytes())
    (out_dir / "manifest.json").write_text(json.dumps({
        "subject": args.subject,
        "frame": "atlas: +X right, +Y superior, +Z anterior, millimetres",
        "source_axes": args.axes,
        "source_units": args.units,
        "weld_tolerance_mm": args.weld_tol,
        "vertex_count": int(all_verts.shape[0]),
        "triangle_count": int(all_faces.shape[0]),
        "bbox_min_mm": [round(float(v), 4) for v in lo],
        "bbox_max_mm": [round(float(v), 4) for v in hi],
        "attribution": [
            "Anatomical imagery courtesy of the U.S. National Library of "
            "Medicine (Visible Human Project).",
            "Lower-extremity musculoskeletal geometry derived from Andreassen TE, "
            "Hume DR, Hamilton LD, Walker KE, Higinbotham SE, Shelburne KB, "
            "'Three Dimensional Lower Extremity Musculoskeletal Geometry of the "
            "Visible Human Female and Male', Scientific Data 10:34 (2023), "
            "doi:10.1038/s41597-022-01905-2, used under CC BY 4.0.",
        ],
        "structures": manifest,
    }, indent=2))

    extent = hi - lo
    print(f"vertices   {all_verts.shape[0]:,}")
    print(f"triangles  {all_faces.shape[0]:,}")
    print(f"bbox (mm)  {np.array2string(lo, precision=1)} .. {np.array2string(hi, precision=1)}")
    print(f"extent(mm) {np.array2string(extent, precision=1)}")
    if not (200.0 <= extent.max() <= 2500.0):
        print(f"\nWARNING: largest extent is {extent.max():.1f} mm, which is not a "
              f"plausible lower-limb length. Check --units.")
    if extent[1] < extent.max() * 0.8:
        print(f"\nWARNING: the atlas Y (superior) axis is not the longest one. "
              f"For a pelvis-to-foot scan it normally should be. Check --axes.")

    print(f"\nwrote {out_dir}")
    print("  vertices.f32  faces.u32  manifest.json")
    print("\nAttribution is embedded in the manifest and MUST ship with anything "
          "built from it. See docs/GEOMETRY_SOURCES.md.")
    return 0


# --------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    def common(p):
        p.add_argument("directory", help="folder holding the downloaded STL geometry")
        p.add_argument("--subject", default="vhm",
                       help="label for output files, e.g. vhm or vhf (default: vhm)")
        return p

    p_inspect = common(sub.add_parser("inspect", help="report what is in the folder"))
    p_inspect.set_defaults(func=cmd_inspect)

    p_propose = common(sub.add_parser("propose", help="draft a name -> atlas ID mapping"))
    p_propose.add_argument("--min-score", type=float, default=0.55,
                           help="below this similarity a match is 'unmatched' (default: 0.55)")
    p_propose.add_argument("--margin", type=float, default=0.08,
                           help="if the top two are closer than this, flag 'ambiguous' (default: 0.08)")
    p_propose.add_argument("--force", action="store_true",
                           help="overwrite an existing mapping file, discarding hand edits")
    p_propose.set_defaults(func=cmd_propose)

    p_convert = common(sub.add_parser("convert", help="apply the mapping and emit geometry"))
    p_convert.add_argument("--axes", required=True,
                           help="source->atlas axis spec, e.g. '+x,+z,-y'. See 'inspect' output.")
    p_convert.add_argument("--origin", default=None,
                           help="source-unit coordinates to move to the atlas origin, "
                                "'x,y,z'. The atlas origin is the midpoint of the hip "
                                "joint centres; inspect measures one of them for you. "
                                "Omit and the source origin is kept, which will not "
                                "line up with the atlas rig.")
    p_convert.add_argument("--units", required=True, choices=sorted(vh.UNIT_SCALE_TO_MM),
                           help="units of the source coordinates")
    p_convert.add_argument("--weld-tol", type=float, default=1e-4,
                           help="vertex merge tolerance in source units (default: 1e-4)")
    p_convert.add_argument("--out", default=None, help="output directory (default: build/vh/<subject>)")
    p_convert.add_argument("--allow-unreviewed", action="store_true",
                           help="convert what is mapped and silently drop unresolved meshes")
    p_convert.set_defaults(func=cmd_convert)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
