#!/usr/bin/env python3
"""Turn a segmented CT or MRI into atlas-frame geometry.

Same three steps as the STL ingest, and the same manifest out the other end,
so every audit already written runs on the result unchanged:

    python3 scripts/ingest_volume_geometry.py inspect  SEG.nii.gz --labels totalsegmentator
    python3 scripts/ingest_volume_geometry.py propose  SEG.nii.gz --labels totalsegmentator --subject ct01
    python3 scripts/ingest_volume_geometry.py convert  SEG.nii.gz --labels totalsegmentator --subject ct01 --origin ...

`inspect` reads the volume's own affine, reports its orientation, spacing and
extent, lists what is actually present, and tries to recover the atlas origin
by fitting both femoral heads. It changes nothing. `propose` writes an
editable mapping of structure names onto atlas entities. `convert` writes the
meshes.

The origin is not applied unless you pass it. Geometry converted without one
keeps the scanner's own origin, which is a corner of the imaged volume and
lines up with nothing in this atlas.
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

from engine import vh_ingest as vh                       # noqa: E402
from engine import volume_ingest as vol                  # noqa: E402

BUILD_DIR = REPO_ROOT / "build" / "vh"

# Names in a scan label map that no atlas entity should ever absorb. Viscera
# and the brain are real structures and correctly segmented; this atlas is
# musculoskeletal and neurovascular and has nowhere to put a spleen.
NOT_MUSCULOSKELETAL = (
    "spleen", "kidney", "gallbladder", "liver", "stomach", "pancreas",
    "adrenal", "lung", "esophagus", "trachea", "thyroid", "bowel", "duodenum",
    "colon", "bladder", "prostate", "heart", "atrial", "brain", "cyst",
)


def surfaces_for(volume, affine, names, wanted=None, step=1):
    """{name: atlas-frame vertices} for every label present."""
    out = {}
    present = set(np.unique(volume).tolist()) - {0}
    for label in sorted(present):
        name = names.get(label)
        if name is None or (wanted and name not in wanted):
            continue
        verts, faces = vol.label_surface(volume, label, step=step)
        if len(verts) == 0:
            continue
        out[name] = (vol.voxels_to_atlas(verts, affine), faces)
    return out


# --------------------------------------------------------------------------
# 1. inspect
# --------------------------------------------------------------------------

def cmd_inspect(args) -> int:
    path = Path(args.volume).expanduser().resolve()
    volume, affine, codes = vol.load_labels(path)
    names = vol.load_label_names(args.labels)

    spacing = np.linalg.norm(affine[:3, :3], axis=0)
    print(f"file       {path.name}")
    print(f"shape      {volume.shape}")
    print(f"spacing    {np.array2string(spacing, precision=3)} mm")
    print(f"axis codes {codes}  (NIfTI world frame)")
    if not vol.is_right_handed(affine):
        print("handedness ok -- left and right are as the file says")
    else:
        print("handedness WRONG: this volume's affine has positive determinant,\n"
              "           which means the scan is stored MIRRORED. Left and right\n"
              "           are swapped. Fix the source; nothing here will silently\n"
              "           correct a patient's laterality.")

    present = sorted(set(np.unique(volume).tolist()) - {0})
    known = [names[i] for i in present if i in names]
    unknown = [i for i in present if i not in names]
    print(f"\n{len(present)} labels present, {len(known)} named by "
          f"{args.labels}, {len(unknown)} unnamed")
    if unknown:
        print(f"  unnamed ids: {unknown[:20]}")

    skeletal = [n for n in known
                if not any(k in n for k in NOT_MUSCULOSKELETAL)]
    print(f"{len(skeletal)} of them are musculoskeletal or vascular:")
    for name in skeletal:
        print(f"    {name}")

    print("\nfitting the atlas origin from the femoral heads")
    femurs = surfaces_for(volume, affine, names,
                          wanted={"femur_left", "femur_right"}, step=args.step)
    report = vol.hip_joint_origin({k: v[0] for k, v in femurs.items()})
    for side, fit in report["sides"].items():
        flag = "" if fit["plausible"] else "   <-- NOT a femoral head"
        print(f"  {side:5} centre {fit['centre_mm']}  r={fit['radius_mm']} mm  "
              f"rms={fit['rms_mm']} mm{flag}")
    if report["origin_mm"]:
        o = report["origin_mm"]
        print(f"\n  atlas origin ({report['from']}):")
        print(f"    --origin '{o[0]:.3f},{o[1]:.3f},{o[2]:.3f}'")
        print("  Those are ATLAS-frame millimetres, already converted, so pass\n"
              "  them to convert exactly as printed.")
    else:
        print(f"\n  origin NOT recovered: {report['from']}")
        print("  Without it the geometry keeps the scanner's own origin and\n"
              "  will not line up with data/rig/anchors.json.")
    return 0


# --------------------------------------------------------------------------
# 2. propose
# --------------------------------------------------------------------------

def cmd_propose(args) -> int:
    path = Path(args.volume).expanduser().resolve()
    volume, _affine, _codes = vol.load_labels(path)
    names = vol.load_label_names(args.labels)
    atlas = vh.load_atlas_index()
    reviewed = vol.load_atlas_mapping(args.labels)
    known_ids = {e.entity_id for e in atlas}
    bad = {n: m["atlas_id"] for n, m in reviewed.items()
           if m.get("atlas_id") and m["atlas_id"] not in known_ids}
    for n, m in reviewed.items():
        for part, target in (m.get("split_parts") or {}).items():
            if target and target not in known_ids:
                bad[f"{n}[{part}]"] = target
        if m.get("splitter") and m["splitter"] not in vol.LABEL_SPLITTERS:
            bad[n] = f"splitter {m['splitter']!r} (not in engine/volume_ingest.py)"
    if bad:
        raise SystemExit(
            f"{args.labels}: {len(bad)} reviewed mapping(s) name an atlas "
            f"entity that does not exist, so they would silently do nothing:\n"
            + "\n".join(f"  {n} -> {i}" for n, i in list(bad.items())[:10]))

    present = sorted(set(np.unique(volume).tolist()) - {0})
    entries, counts = [], Counter()
    for label in present:
        raw = names.get(label)
        if raw is None:
            entries.append({"label": label, "source_structure": None,
                            "status": "unnamed", "atlas_id": None,
                            "note": f"id {label} is not in the {args.labels} map"})
            counts["unnamed"] += 1
            continue
        pretty = raw.replace("_", " ")
        _base, side = vh.split_side(pretty)
        decision = reviewed.get(raw)
        if decision is not None:
            # A reviewed decision outranks any score, including a decision
            # NOT to map -- which is why atlas_id may be null here. A split
            # has no atlas_id either: its entities are named per part.
            split = decision.get("relationship") == "split"
            status = ("curated" if decision["atlas_id"] or split
                      else "no_atlas_entity")
            entry = {"label": label, "source_structure": raw,
                     "side": side, "status": status,
                     "atlas_id": decision["atlas_id"],
                     "relationship": decision.get("relationship"),
                     "note": decision.get("note") or None,
                     "candidates": []}
            if split:
                entry["splitter"] = decision["splitter"]
                entry["split_parts"] = decision["split_parts"]
            entries.append(entry)
            counts[status] += 1
            continue
        if any(k in raw for k in NOT_MUSCULOSKELETAL):
            status, chosen, note = "no_atlas_category", None, (
                "Correctly segmented, but this atlas is musculoskeletal and "
                "neurovascular and has no entity for it.")
            cands = []
        else:
            cands = vh.propose_matches(pretty, atlas, side=side, top_n=3)
            best = cands[0] if cands else None
            runner = cands[1] if len(cands) > 1 else None
            note = None
            # The STL ingest's override table is not consulted here. It keys
            # on a tissue-class token ('bone|talus') that CT structure names
            # never carry, so every lookup missed; the reviewed decisions for
            # this label map live in the label map itself and were applied
            # above.
            if best is not None and best.score >= vh.EXACT and (
                    runner is None or runner.score < vh.EXACT):
                status, chosen = "confident", best.entity_id
            elif best is None or best.score < args.min_score:
                status, chosen = "unmatched", None
            elif runner and (best.score - runner.score) < args.margin:
                status, chosen = "ambiguous", None
            else:
                status, chosen = "confident", best.entity_id
        counts[status] += 1
        entry = {"label": label, "source_structure": raw, "side": side,
                 "status": status, "atlas_id": chosen,
                 "candidates": [{"atlas_id": c.entity_id, "category": c.category,
                                 "score": c.score, "matched_name": c.matched_name}
                                for c in cands]}
        if note:
            entry["note"] = note
        entries.append(entry)

    for status, n in counts.most_common():
        print(f"  {status:20} {n}")

    BUILD_DIR.mkdir(parents=True, exist_ok=True)
    out = BUILD_DIR / f"{args.subject}_volume_mapping.json"
    if out.exists() and not args.force:
        raise SystemExit(f"\n{out.relative_to(REPO_ROOT)} exists and may hold "
                         f"your edits. Pass --force to overwrite.")
    out.write_text(json.dumps({
        "_README": [
            "Review every entry before running convert.",
            "Set 'atlas_id' to the correct entity, or null to skip the label.",
            "'status' is advisory; convert reads 'atlas_id' only.",
        ],
        "subject": args.subject,
        "source_volume": str(path),
        "label_map": args.labels,
        "entries": entries,
    }, indent=2))
    print(f"\nwrote {out.relative_to(REPO_ROOT)}")
    print(f"      {sum(1 for e in entries if e['atlas_id'] or e.get('split_parts'))} "
          f"of {len(entries)} labels currently have an atlas_id or a split")
    return 0


# --------------------------------------------------------------------------
# 3. convert
# --------------------------------------------------------------------------

def cmd_convert(args) -> int:
    path = Path(args.volume).expanduser().resolve()
    mapping_file = BUILD_DIR / f"{args.subject}_volume_mapping.json"
    if not mapping_file.exists():
        raise SystemExit(f"No mapping at {mapping_file}. Run 'propose' first.")
    mapping = json.loads(mapping_file.read_text())
    entries = [e for e in mapping["entries"]
               if e.get("atlas_id") or e.get("split_parts")]
    if not entries:
        raise SystemExit(f"{mapping_file.name} has no entry with an atlas_id.")

    known = {e.entity_id for e in vh.load_atlas_index()}
    claimed = {e["atlas_id"] for e in entries if e.get("atlas_id")}
    for e in entries:
        # A part mapped to null is a decision not to ingest it (the
        # ascending aorta has no atlas entity); only named parts are checked.
        claimed.update(t for t in (e.get("split_parts") or {}).values() if t)
    unknown = sorted(claimed - known)
    if unknown:
        raise SystemExit("atlas_id values that do not exist in data/:\n"
                         + "\n".join(f"  {i}" for i in unknown[:12]))

    volume, affine, _codes = vol.load_labels(path)
    names = vol.load_label_names(mapping.get("label_map", args.labels))
    label_ids = {n: i for i, n in names.items()}
    origin = np.zeros(3)
    if args.origin:
        origin = vh.parse_origin(args.origin)
        print(f"origin {args.origin} (atlas mm) -> (0,0,0)")
    else:
        print("origin: NOT SET. The geometry will keep the scanner's own "
              "origin and will not line up with data/rig/anchors.json. Run "
              "inspect to recover it.")

    out_dir = (Path(args.out).expanduser().resolve() if args.out
               else BUILD_DIR / args.subject)
    out_dir.mkdir(parents=True, exist_ok=True)

    verts_blocks, faces_blocks, manifest = [], [], []
    vertex_base = face_base = 0
    lo, hi = np.full(3, np.inf), np.full(3, -np.inf)
    for entry in entries:
        # Most labels are one atlas entity. Two hold several -- see the
        # 'split' relationship in mappings/<labels>_labels.json -- and are
        # cut geometrically, at levels measured from the scan itself.
        if entry.get("split_parts"):
            splitter = vol.LABEL_SPLITTERS.get(entry.get("splitter"))
            if splitter is None:
                raise SystemExit(
                    f"{entry['source_structure']}: no splitter named "
                    f"{entry.get('splitter')!r} in engine/volume_ingest.py")
            if not (volume == entry["label"]).any():
                print(f"  {entry['source_structure']}: label absent, skipped")
                continue
            try:
                produced, notes = splitter(volume, entry["label"], affine, label_ids)
            except ValueError as exc:
                raise SystemExit(f"{entry['source_structure']}: {exc}") from None
            missing = set(entry["split_parts"]) - set(produced)
            if missing:
                raise SystemExit(
                    f"{entry['source_structure']}: splitter {entry['splitter']!r} "
                    f"returned no part named {', '.join(sorted(missing))}")
            print(f"  split {entry['source_structure']}:")
            for line in notes:
                print(f"      {line}")
            parts = []
            for part, target in entry["split_parts"].items():
                if not target:
                    print(f"      {part}: no atlas entity, not ingested")
                    continue
                if not produced[part].any():
                    print(f"      {part}: empty in this scan")
                    continue
                v, f = vol.mask_surface(produced[part], step=args.step)
                parts.append((target, v, f))
        else:
            v, f = vol.label_surface(volume, entry["label"], step=args.step)
            if len(v) == 0:
                print(f"  {entry['source_structure']}: label absent, skipped")
                continue
            parts = [(entry["atlas_id"], v, f)]

        for atlas_id, v, f in parts:
            v = vol.voxels_to_atlas(v, affine) - origin
            mn, mx = v.min(axis=0), v.max(axis=0)
            lo, hi = np.minimum(lo, mn), np.maximum(hi, mx)
            record = {
                "atlas_id": atlas_id,
                "source_structure": entry["source_structure"],
                "side": entry.get("side"),
                "source_file": f"{path.name}#{entry['label']}",
                "vertex_offset": vertex_base, "face_offset": face_base,
                "vertex_count": int(v.shape[0]),
                "triangle_count": int(f.shape[0]),
                "bbox_min_mm": [round(float(x), 4) for x in mn],
                "bbox_max_mm": [round(float(x), 4) for x in mx],
            }
            if entry.get("split_parts"):
                record["split_from"] = entry["source_structure"]
                record["splitter"] = entry["splitter"]
            manifest.append(record)
            verts_blocks.append(v.astype(np.float32))
            faces_blocks.append((f + vertex_base).astype(np.uint32))
            vertex_base += v.shape[0]
            face_base += f.shape[0]

    if not verts_blocks:
        raise SystemExit("no mapped label is present in this volume")

    all_verts = np.concatenate(verts_blocks)
    all_faces = np.concatenate(faces_blocks)
    (out_dir / "vertices.f32").write_bytes(all_verts.tobytes())
    (out_dir / "faces.u32").write_bytes(all_faces.tobytes())
    (out_dir / "manifest.json").write_text(json.dumps({
        "subject": args.subject,
        "frame": "atlas: +X right, +Y superior, +Z anterior, millimetres",
        "source_volume": str(path),
        "source_kind": "labelled volume (NIfTI)",
        "label_map": mapping.get("label_map", args.labels),
        "marching_cubes_step": args.step,
        "vertex_count": int(all_verts.shape[0]),
        "triangle_count": int(all_faces.shape[0]),
        "bbox_min_mm": [round(float(v), 4) for v in lo],
        "bbox_max_mm": [round(float(v), 4) for v in hi],
        "attribution": [
            "Geometry surfaced from a segmented volume supplied by the "
            "operator. Whatever licence and consent govern that scan and its "
            "segmentation travel with everything derived from it, and are NOT "
            "asserted here.",
        ],
        "structures": manifest,
    }, indent=2))

    extent = hi - lo
    print(f"\nvertices   {all_verts.shape[0]:,}")
    print(f"triangles  {all_faces.shape[0]:,}")
    print(f"bbox (mm)  {np.array2string(lo, precision=1)} .. "
          f"{np.array2string(hi, precision=1)}")
    print(f"extent(mm) {np.array2string(extent, precision=1)}")
    print(f"\nwrote {out_dir}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name, fn in (("inspect", cmd_inspect), ("propose", cmd_propose),
                     ("convert", cmd_convert)):
        p = sub.add_parser(name)
        p.add_argument("volume")
        p.add_argument("--labels", default="totalsegmentator")
        p.add_argument("--step", type=int, default=1,
                       help="marching-cubes step; >1 decimates and is faster")
        p.set_defaults(fn=fn)
        if name != "inspect":
            p.add_argument("--subject", required=True)
        if name == "propose":
            p.add_argument("--min-score", type=float, default=0.55)
            p.add_argument("--margin", type=float, default=0.08)
            p.add_argument("--force", action="store_true")
        if name == "convert":
            p.add_argument("--origin")
            p.add_argument("--out")
    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
