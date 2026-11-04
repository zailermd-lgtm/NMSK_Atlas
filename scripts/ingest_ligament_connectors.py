#!/usr/bin/env python3
"""Ingest the procedural ligament OBJ meshes from generate_ligament_connectors.py into the
ct_vhm / ct_vhf raw-geometry subjects, exactly the way ingest_tendon_connectors.py (Q118)
added the tendons: append new structures/vertices/faces to that subject's own manifest +
vertices.f32/faces.u32, idempotently (existing ligament structures with the same id are
replaced, not duplicated, so this can be re-run safely).

Q122 ships these on WHICHEVER body's own generation report marks them "generated" -- unlike
Q118's tendons, several of these bone-to-bone connectors pass on only ONE of the two
bodies (the straight-chord-through-bone containment check and, on the female, a known CT
field-of-view fragment on her ulna_r, are real per-body geometric facts, not something to
force into agreement -- see PROJECT_STATE.md's Q122 entry). Running this with --body male
only ingests the ids `ligament_generation_report_male.json` marks generated; likewise for
--body female.

Every appended structure's own `source_file` carries the PROCEDURAL/RULE-BASED badge
in-line, so it survives into every downstream manifest/bundle without extra plumbing:
"PROCEDURAL/RULE-BASED (Q122): generate_ligament_connectors.py#<id>, NOT segmented from
imaging -- see PROJECT_STATE.md Q122".

    python3 scripts/ingest_ligament_connectors.py --body male
    python3 scripts/ingest_ligament_connectors.py --body female
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

OUTPUT_DIR = REPO_ROOT / "data" / "ct_sources" / "task_outputs"
BUILD_DIR = REPO_ROOT / "build" / "vh"

BADGE = ("PROCEDURAL/RULE-BASED (Q122): generate_ligament_connectors.py#{aid}, NOT "
         "segmented from imaging -- a geometrically-derived bone-to-bone connector "
         "between this body's own already-shipped bone landmarks, real measured length, "
         "disclosed arbitrary cross-section -- see PROJECT_STATE.md Q122")


def read_obj(path: Path):
    verts, faces = [], []
    for line in path.read_text().splitlines():
        if line.startswith("v "):
            verts.append([float(x) for x in line.split()[1:4]])
        elif line.startswith("f "):
            faces.append([int(p.split("/")[0]) - 1 for p in line.split()[1:4]])
    return np.array(verts, dtype=np.float64), np.array(faces, dtype=np.int64)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--body", choices=["male", "female"], required=True)
    args = ap.parse_args()

    report_path = OUTPUT_DIR / f"ligament_generation_report_{args.body}.json"
    report = json.loads(report_path.read_text())
    generated_ids = {k for k, v in report.items()
                      if isinstance(v, dict) and v.get("status") == "generated"}
    if not generated_ids:
        print(f"no generated ligament ids in {report_path} for body={args.body}")
        return 1

    subject = "ct_vhm" if args.body == "male" else "ct_vhf"
    subject_dir = BUILD_DIR / subject
    manifest = json.loads((subject_dir / "manifest.json").read_text())
    verts = np.fromfile(subject_dir / "vertices.f32", dtype=np.float32).reshape(-1, 3).astype(np.float64)
    faces = np.fromfile(subject_dir / "faces.u32", dtype=np.uint32).reshape(-1, 3).astype(np.int64)

    obj_files = [OUTPUT_DIR / f"ligament_{args.body}_{aid}.obj" for aid in sorted(generated_ids)]
    missing = [p for p in obj_files if not p.exists()]
    if missing:
        print(f"missing OBJ file(s) for ids marked generated: {missing}")
        return 1
    new_ids = {p.stem.replace(f"ligament_{args.body}_", "") for p in obj_files}

    # Drop any prior instance of these ids (idempotent re-run), keeping everything else.
    keep = [s for s in manifest["structures"] if s["atlas_id"] not in new_ids]
    removed = len(manifest["structures"]) - len(keep)
    if removed:
        print(f"  removing {removed} pre-existing structure(s) with the same id(s) (idempotent re-run)")

    # Rebuild the consolidated mesh from the kept structures only, remapping offsets --
    # identical approach to ingest_tendon_connectors.py's own consolidation step.
    non_v, non_f = [], []
    v_off = f_off = 0
    for s in keep:
        v0, vn = s["vertex_offset"], s["vertex_count"]
        f0, fn = s["face_offset"], s["triangle_count"]
        chunk_v = verts[v0:v0 + vn]
        chunk_f = (faces[f0:f0 + fn].astype(np.int64) + (v_off - v0)).astype(np.int64)
        s["vertex_offset"], s["face_offset"] = v_off, f_off
        non_v.append(chunk_v); non_f.append(chunk_f)
        v_off += vn; f_off += fn

    all_v = list(non_v)
    all_f = list(non_f)
    new_structs = []
    for p in obj_files:
        aid = p.stem.replace(f"ligament_{args.body}_", "")
        v, f = read_obj(p)
        all_v.append(v)
        all_f.append(f + v_off)
        new_structs.append({
            "atlas_id": aid,
            "source_structure": aid,
            "side": "right" if aid.endswith("_r") else ("left" if aid.endswith("_l") else None),
            "source_file": BADGE.format(aid=aid),
            "vertex_offset": v_off,
            "face_offset": f_off,
            "vertex_count": len(v),
            "triangle_count": len(f),
            "bbox_min_mm": v.min(axis=0).tolist(),
            "bbox_max_mm": v.max(axis=0).tolist(),
            "tris_full_at_source": len(f),
        })
        v_off += len(v); f_off += len(f)

    consolidated_v = np.vstack(all_v) if all_v else np.empty((0, 3))
    consolidated_f = np.vstack(all_f) if all_f else np.empty((0, 3), dtype=np.int64)

    consolidated_v.astype(np.float32).tofile(subject_dir / "vertices.f32")
    consolidated_f.astype(np.uint32).tofile(subject_dir / "faces.u32")

    manifest["structures"] = keep + new_structs
    manifest["vertex_count"] = int(len(consolidated_v))
    manifest["triangle_count"] = int(len(consolidated_f))
    manifest["bbox_min_mm"] = consolidated_v.min(axis=0).tolist()
    manifest["bbox_max_mm"] = consolidated_v.max(axis=0).tolist()
    (subject_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))

    print(f"{subject}: ingested {len(new_structs)} ligament structures "
          f"({int(len(consolidated_v))} verts, {int(len(consolidated_f))} faces total)")
    for s in new_structs:
        print(f"  + {s['atlas_id']:36} {s['vertex_count']:5} verts {s['triangle_count']:5} faces")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
