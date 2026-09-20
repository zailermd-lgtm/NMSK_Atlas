#!/usr/bin/env python3
"""Ingest remeshed rib structures back into the bundles.

This script:
1. Reads the voxelized and reconstructed rib meshes from OBJ files
2. Replaces ribs_l and ribs_r in both ct_vhm and ct_vhf bundles
3. Updates the manifest with new vertex/triangle counts
4. Re-exports the bundles as binary files
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Tuple

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

BUILD_DIR = REPO_ROOT / "build" / "vh"
OUTPUT_DIR = REPO_ROOT / "data" / "ct_sources" / "task_outputs"


def read_mesh_binary(subject_dir: Path) -> Tuple[np.ndarray, np.ndarray]:
    """Read mesh from binary files."""
    verts_file = subject_dir / "vertices.f32"
    faces_file = subject_dir / "faces.u32"

    if not verts_file.exists() or not faces_file.exists():
        return np.empty((0, 3)), np.empty((0, 3), dtype=np.uint32)

    verts = np.fromfile(verts_file, dtype=np.float32).reshape(-1, 3)
    faces = np.fromfile(faces_file, dtype=np.uint32).reshape(-1, 3)

    return verts, faces


def write_mesh_binary(subject_dir: Path, vertices: np.ndarray, faces: np.ndarray) -> None:
    """Write mesh to binary files."""
    vertices.astype(np.float32).tofile(subject_dir / "vertices.f32")
    faces.astype(np.uint32).tofile(subject_dir / "faces.u32")


def load_manifest(subject: str) -> dict:
    """Load manifest for a subject."""
    manifest_path = BUILD_DIR / subject / "manifest.json"
    with open(manifest_path) as f:
        return json.load(f)


def save_manifest(subject: str, manifest: dict) -> None:
    """Save manifest for a subject."""
    manifest_path = BUILD_DIR / subject / "manifest.json"
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)


def read_obj_file(filepath: Path) -> Tuple[np.ndarray, np.ndarray]:
    """Read OBJ file and return vertices and faces."""
    vertices = []
    faces = []

    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue

            parts = line.split()
            if not parts:
                continue

            if parts[0] == 'v':  # Vertex
                v = [float(parts[1]), float(parts[2]), float(parts[3])]
                vertices.append(v)
            elif parts[0] == 'f':  # Face
                face_indices = []
                for part in parts[1:]:
                    v_idx = int(part.split('/')[0]) - 1  # OBJ uses 1-based indexing
                    face_indices.append(v_idx)

                # Triangulate face if needed
                for i in range(1, len(face_indices) - 1):
                    faces.append([face_indices[0], face_indices[i], face_indices[i + 1]])

    return np.array(vertices, dtype=np.float32), np.array(faces, dtype=np.uint32)


def cmd_ingest(args: argparse.Namespace) -> int:
    """Ingest remeshed ribs into bundles."""

    results = {}

    for subject in ["ct_vhm", "ct_vhf"]:
        print(f"\nProcessing {subject}...")

        subject_dir = BUILD_DIR / subject

        # Load current bundle
        all_verts, all_faces = read_mesh_binary(subject_dir)
        manifest = load_manifest(subject)

        print(f"  Current bundle: {len(all_verts)} vertices, {len(all_faces)} faces")

        # Load remeshed ribs
        remeshed_ribs = {}
        for atlas_id in ["ribs_l", "ribs_r"]:
            obj_path = OUTPUT_DIR / f"{subject}_{atlas_id}_remeshed.obj"
            if not obj_path.exists():
                print(f"  ERROR: {obj_path} not found")
                return 1

            verts, faces = read_obj_file(obj_path)
            remeshed_ribs[atlas_id] = (verts, faces)
            print(f"  Loaded {atlas_id}: {len(verts)} vertices, {len(faces)} faces")

        # Build new bundle
        # We need to:
        # 1. Keep all non-rib structures as-is
        # 2. Replace ribs_l and ribs_r with remeshed versions
        # 3. Adjust offsets for subsequent structures

        new_verts = []
        new_faces = []
        vert_offset = 0
        face_offset = 0

        new_structures = []

        for struct in manifest["structures"]:
            atlas_id = struct["atlas_id"]

            if atlas_id in ["ribs_l", "ribs_r"]:
                # Replace with remeshed version
                remeshed_verts, remeshed_faces = remeshed_ribs[atlas_id]

                new_verts.append(remeshed_verts)
                new_faces.append(remeshed_faces)

                # Update manifest entry
                new_struct = struct.copy()
                new_struct["vertex_offset"] = vert_offset
                new_struct["vertex_count"] = len(remeshed_verts)
                new_struct["face_offset"] = face_offset
                new_struct["triangle_count"] = len(remeshed_faces)

                new_structures.append(new_struct)

                vert_offset += len(remeshed_verts)
                face_offset += len(remeshed_faces)

                print(f"  Replaced {atlas_id}: {len(remeshed_verts)} vertices, {len(remeshed_faces)} faces")
            else:
                # Keep original structure but update offsets
                vert_start = struct["vertex_offset"]
                vert_end = vert_start + struct["vertex_count"]
                face_start = struct["face_offset"]
                face_end = face_start + struct["triangle_count"]

                struct_verts = all_verts[vert_start:vert_end].copy()
                struct_faces = all_faces[face_start:face_end].copy()

                # Remap face indices
                struct_faces_remapped = struct_faces.copy()
                for i in range(len(struct_faces_remapped)):
                    for j in range(3):
                        # Convert global index to local, then to new global
                        global_idx = struct_faces_remapped[i, j]
                        if global_idx >= vert_start and global_idx < vert_end:
                            # Local index in old bundle
                            local_idx = global_idx - vert_start
                            # New global index
                            struct_faces_remapped[i, j] = vert_offset + local_idx
                        # else: index is out of our structure, keep as-is (will be fixed if it's another structure)

                new_verts.append(struct_verts)
                new_faces.append(struct_faces_remapped)

                # Update manifest entry
                new_struct = struct.copy()
                new_struct["vertex_offset"] = vert_offset
                new_struct["vertex_count"] = len(struct_verts)
                new_struct["face_offset"] = face_offset
                new_struct["triangle_count"] = len(struct_faces_remapped)

                new_structures.append(new_struct)

                vert_offset += len(struct_verts)
                face_offset += len(struct_faces_remapped)

        # Consolidate new bundle
        consolidated_verts = np.vstack(new_verts)
        consolidated_faces = np.vstack(new_faces)

        print(f"  New bundle: {len(consolidated_verts)} vertices, {len(consolidated_faces)} faces")

        # Write new bundle
        write_mesh_binary(subject_dir, consolidated_verts, consolidated_faces)

        # Update and save manifest
        manifest["structures"] = new_structures
        save_manifest(subject, manifest)

        results[subject] = {
            "status": "SUCCESS",
            "vertices": len(consolidated_verts),
            "faces": len(consolidated_faces),
        }

        print(f"  Saved bundle")

    # Summary
    print("\n" + "="*70)
    print("INGESTION SUMMARY")
    print("="*70)

    for subject in ["ct_vhm", "ct_vhf"]:
        result = results.get(subject, {})
        if result.get("status") == "SUCCESS":
            print(f"{subject}: {result['vertices']} vertices, {result['faces']} faces")
        else:
            print(f"{subject}: ERROR")

    print("="*70)

    return 0


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "command",
        choices=["ingest"],
        help="Command to run",
    )

    args = parser.parse_args()

    if args.command == "ingest":
        return cmd_ingest(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
