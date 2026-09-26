#!/usr/bin/env python3
"""Ingest the voxelized+remeshed female (ct_vhf) lumbar column back into its bundle.

Mirrors `ingest_remeshed_ribs.py`'s structure and its Q107 vertex_offset fix
(faces read from the remeshed OBJ are 0-based LOCAL indices and must be shifted
by the running `vert_offset` before being appended to the shared global face
array -- the exact bug Q107 found and fixed for discs/ribs is NOT reintroduced
here).

SCOPE (Q110, 2026-09-22): `ct_vhf` ONLY. Unlike `ingest_remeshed_ribs.py`
(which loops `["ct_vhm", "ct_vhf"]`), this script never touches `ct_vhm` --
the task this script was written for is explicitly scoped to the female
lumbar column, and the male has no analogous shipped lumbar-disc feature to
fix.

This script replaces the 5 `lumbar_vertebrae` pieces (L1-L5) AND the 4
`intervertebral_disc_l{1,2,3,4}_l{2,3,4,5}` pieces with ONE consolidated
`lumbar_vertebrae` manifest entry -- exactly analogous to how
`ingest_remeshed_ribs.py` consolidates N per-rib pieces sharing one atlas_id
into a single `ribs_l`/`ribs_r` entry. The 4 lumbar disc atlas_ids are REMOVED
(their geometry is fused into the single reconstructed mesh, no longer
independently selectable) -- this is a real, disclosed trade-off; see
`--dry-run` and PROJECT_STATE.md's Q110 entry for why, as measured by this
project's own tooling (`voxelize_lumbar_column.py`), this trade was ultimately
DECLINED for shipping (severe real-bone volume distortion), even though this
ingestion script itself works correctly end-to-end (validated on a scratch
copy of `ct_vhf`, see Q110 entry).
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Tuple

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

BUILD_DIR = REPO_ROOT / "build" / "vh"
OUTPUT_DIR = REPO_ROOT / "data" / "ct_sources" / "task_outputs"

SUBJECT = "ct_vhf"
LUMBAR_ATLAS_ID = "lumbar_vertebrae"
DISC_ATLAS_IDS = [
    "intervertebral_disc_l1_l2",
    "intervertebral_disc_l2_l3",
    "intervertebral_disc_l3_l4",
    "intervertebral_disc_l4_l5",
]
REPLACED_ATLAS_IDS = {LUMBAR_ATLAS_ID, *DISC_ATLAS_IDS}


def read_mesh_binary(subject_dir: Path) -> Tuple[np.ndarray, np.ndarray]:
    verts = np.fromfile(subject_dir / "vertices.f32", dtype=np.float32).reshape(-1, 3)
    faces = np.fromfile(subject_dir / "faces.u32", dtype=np.uint32).reshape(-1, 3)
    return verts, faces


def write_mesh_binary(subject_dir: Path, vertices: np.ndarray, faces: np.ndarray) -> None:
    vertices.astype(np.float32).tofile(subject_dir / "vertices.f32")
    faces.astype(np.uint32).tofile(subject_dir / "faces.u32")


def load_manifest(subject_dir: Path) -> dict:
    with open(subject_dir / "manifest.json") as f:
        return json.load(f)


def save_manifest(subject_dir: Path, manifest: dict) -> None:
    with open(subject_dir / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)


def read_obj_file(filepath: Path) -> Tuple[np.ndarray, np.ndarray]:
    vertices, faces = [], []
    with open(filepath) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if parts[0] == "v":
                vertices.append([float(parts[1]), float(parts[2]), float(parts[3])])
            elif parts[0] == "f":
                idx = [int(p.split("/")[0]) - 1 for p in parts[1:]]
                for i in range(1, len(idx) - 1):
                    faces.append([idx[0], idx[i], idx[i + 1]])
    return np.array(vertices, dtype=np.float32), np.array(faces, dtype=np.uint32)


def cmd_ingest(args: argparse.Namespace) -> int:
    subject_dir = BUILD_DIR / SUBJECT if args.build_dir is None else Path(args.build_dir) / SUBJECT

    print(f"Processing {SUBJECT} (build dir: {subject_dir})...")

    all_verts, all_faces = read_mesh_binary(subject_dir)
    manifest = load_manifest(subject_dir)
    print(f"  Current bundle: {len(all_verts)} vertices, {len(all_faces)} faces, "
          f"{len(manifest['structures'])} structures")

    obj_path = Path(args.remeshed_obj)
    if not obj_path.exists():
        print(f"  ERROR: {obj_path} not found")
        return 1
    remeshed_verts, remeshed_faces = read_obj_file(obj_path)
    print(f"  Loaded remeshed lumbar column: {len(remeshed_verts)} vertices, {len(remeshed_faces)} faces")

    new_verts, new_faces = [], []
    vert_offset = 0
    face_offset = 0
    new_structures = []
    already_spliced = False

    for struct in manifest["structures"]:
        atlas_id = struct["atlas_id"]

        if atlas_id in REPLACED_ATLAS_IDS:
            # Splice the single consolidated remeshed mesh in exactly once,
            # at the position of the FIRST replaced piece encountered (should
            # be the first lumbar_vertebrae piece, since discs/vertebrae are
            # ingested together in this manifest's structure order); every
            # other replaced piece (the remaining 4 lumbar_vertebrae pieces
            # and the 4 disc pieces) is dropped, not re-spliced.
            if already_spliced:
                continue
            already_spliced = True

            new_verts.append(remeshed_verts)
            # Q107 FIX (do not reintroduce): OBJ face indices are 0-based
            # LOCAL indices; they must be shifted by vert_offset before being
            # appended to the shared global face array.
            new_faces.append(remeshed_faces.astype(np.int64) + vert_offset)

            new_struct = struct.copy()
            new_struct["atlas_id"] = LUMBAR_ATLAS_ID
            new_struct["source_structure"] = "lumbar_vertebrae_L1-L5_remeshed"
            new_struct["vertex_offset"] = vert_offset
            new_struct["vertex_count"] = len(remeshed_verts)
            new_struct["face_offset"] = face_offset
            new_struct["triangle_count"] = len(remeshed_faces)
            new_struct["bbox_min_mm"] = remeshed_verts.min(axis=0).tolist()
            new_struct["bbox_max_mm"] = remeshed_verts.max(axis=0).tolist()

            new_structures.append(new_struct)
            vert_offset += len(remeshed_verts)
            face_offset += len(remeshed_faces)
            print(f"  Spliced consolidated lumbar_vertebrae: {len(remeshed_verts)} vertices, "
                  f"{len(remeshed_faces)} faces (replacing 5 vertebrae + 4 disc pieces)")
        else:
            vert_start = struct["vertex_offset"]
            vert_end = vert_start + struct["vertex_count"]
            face_start = struct["face_offset"]
            face_end = face_start + struct["triangle_count"]

            struct_verts = all_verts[vert_start:vert_end].copy()
            struct_faces = all_faces[face_start:face_end].copy()

            # Q108 FIX (do not reintroduce): do the offset-shift arithmetic in
            # a signed int64 buffer before casting back to uint32, since a
            # negative shift on a uint32 array raises OverflowError under
            # numpy>=2.
            shift = vert_offset - vert_start
            struct_faces_remapped = (struct_faces.astype(np.int64) + shift).astype(np.uint32)

            new_verts.append(struct_verts)
            new_faces.append(struct_faces_remapped)

            new_struct = struct.copy()
            new_struct["vertex_offset"] = vert_offset
            new_struct["vertex_count"] = len(struct_verts)
            new_struct["face_offset"] = face_offset
            new_struct["triangle_count"] = len(struct_faces_remapped)
            new_structures.append(new_struct)

            vert_offset += len(struct_verts)
            face_offset += len(struct_faces_remapped)

    consolidated_verts = np.vstack(new_verts)
    consolidated_faces = np.vstack(new_faces)
    print(f"  New bundle: {len(consolidated_verts)} vertices, {len(consolidated_faces)} faces, "
          f"{len(new_structures)} structures (was {len(manifest['structures'])})")

    if args.dry_run:
        print("  DRY RUN: not writing.")
        return 0

    write_mesh_binary(subject_dir, consolidated_verts, consolidated_faces)
    manifest["structures"] = new_structures
    save_manifest(subject_dir, manifest)
    print("  Saved bundle.")
    return 0


def verify_offsets(subject_dir: Path) -> int:
    """Count structures whose face indices fall outside their own vertex range."""
    verts, faces = read_mesh_binary(subject_dir)
    manifest = load_manifest(subject_dir)
    bad = 0
    for s in manifest["structures"]:
        vo, vc = s["vertex_offset"], s["vertex_count"]
        fo, fc = s["face_offset"], s["triangle_count"]
        f = faces[fo : fo + fc]
        if len(f) == 0:
            continue
        if f.min() < vo or f.max() >= vo + vc:
            bad += 1
            print(f"    OFFSET-INCONSISTENT: {s['atlas_id']} ({s.get('source_structure')}) "
                  f"face range [{f.min()},{f.max()}] outside vertex range [{vo},{vo+vc})")
    print(f"  {bad}/{len(manifest['structures'])} offset-inconsistent structures")
    return bad


def cmd_verify(args: argparse.Namespace) -> int:
    subject_dir = BUILD_DIR / SUBJECT if args.build_dir is None else Path(args.build_dir) / SUBJECT
    bad = verify_offsets(subject_dir)
    return 1 if bad else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["ingest", "verify"])
    parser.add_argument("--remeshed-obj", default=str(OUTPUT_DIR / "ct_vhf_lumbar_column_remeshed_d6.obj"))
    parser.add_argument("--build-dir", default=None, help="Override build/vh dir (for testing on a scratch copy)")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if args.command == "ingest":
        return cmd_ingest(args)
    elif args.command == "verify":
        return cmd_verify(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
