#!/usr/bin/env python3
"""Merge rib articulation surfaces into the ribs_l and ribs_r structures.

This script:
1. Reads generated articulation OBJ files
2. Merges them into the existing ribs_l and ribs_r structures
3. Updates manifests to reflect the merged geometry
4. Re-exports bundles with merged rib structures
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


def read_obj_file(filepath: Path) -> tuple[np.ndarray, np.ndarray]:
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
                    v_idx = int(part.split('/')[0]) - 1
                    face_indices.append(v_idx)

                for i in range(1, len(face_indices) - 1):
                    faces.append([face_indices[0], face_indices[i], face_indices[i + 1]])

    return np.array(vertices), np.array(faces)


def read_mesh_binary(subject_dir: Path) -> tuple[np.ndarray, np.ndarray]:
    """Read existing mesh from binary files."""
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


def cmd_merge(args: argparse.Namespace) -> int:
    """Merge articulation OBJ files into rib structures."""

    for subject in ["ct_vhm", "ct_vhf"]:
        print(f"\nMerging rib articulations for {subject}...")
        subject_dir = BUILD_DIR / subject

        # Load manifest and existing mesh
        manifest = load_manifest(subject)
        existing_verts, existing_faces = read_mesh_binary(subject_dir)

        print(f"  Current mesh: {len(existing_verts)} vertices, {len(existing_faces)} faces")

        # Find articulation structures to remove and their geometries to extract
        articulation_atlas_ids = [
            s["atlas_id"] for s in manifest["structures"]
            if "articulation" in s["atlas_id"]
        ]

        if not articulation_atlas_ids:
            print(f"  No articulation structures found")
            continue

        print(f"  Found {len(articulation_atlas_ids)} articulation structures to merge")

        # Extract articulation geometry
        articulation_geometry = {}
        for struct in manifest["structures"]:
            if struct["atlas_id"] in articulation_atlas_ids:
                vert_start = struct["vertex_offset"]
                vert_end = vert_start + struct["vertex_count"]
                face_start = struct["face_offset"]
                face_end = face_start + struct["triangle_count"]

                verts = existing_verts[vert_start:vert_end].copy()
                faces = existing_faces[face_start:face_end].copy()

                articulation_geometry[struct["atlas_id"]] = (verts, faces)

        # Remove articulation structures from manifest
        original_struct_count = len(manifest["structures"])
        manifest["structures"] = [
            s for s in manifest["structures"]
            if "articulation" not in s["atlas_id"]
        ]
        print(f"  Removed {original_struct_count - len(manifest['structures'])} articulation structures")

        # Rebuild mesh without articulations, update offsets
        non_articulation_verts = []
        non_articulation_faces = []

        new_vertex_offset = 0
        new_face_offset = 0

        for struct in manifest["structures"]:
            old_vert_start = struct["vertex_offset"]
            old_vert_end = old_vert_start + struct["vertex_count"]
            old_face_start = struct["face_offset"]
            old_face_end = old_face_start + struct["triangle_count"]

            # Extract this structure's geometry
            struct_verts = existing_verts[old_vert_start:old_vert_end]
            struct_faces = existing_faces[old_face_start:old_face_end]

            # Remap face indices
            struct_faces_remapped = struct_faces + (new_vertex_offset - old_vert_start)

            # Update structure offsets
            struct["vertex_offset"] = new_vertex_offset
            struct["face_offset"] = new_face_offset

            non_articulation_verts.append(struct_verts)
            non_articulation_faces.append(struct_faces_remapped)

            new_vertex_offset += len(struct_verts)
            new_face_offset += len(struct_faces)

        # Consolidate
        if non_articulation_verts and non_articulation_faces:
            consolidated_verts = np.vstack(non_articulation_verts)
            consolidated_faces = np.vstack(non_articulation_faces)
        else:
            consolidated_verts = np.empty((0, 3), dtype=np.float32)
            consolidated_faces = np.empty((0, 3), dtype=np.uint32)

        print(f"  Rebuilt mesh (without articulations): {len(consolidated_verts)} vertices, {len(consolidated_faces)} faces")

        # Now merge articulations into rib structures
        for side in ["left", "right"]:
            ribs_key = f"ribs_{side[0].lower()}"

            # Find rib structures
            rib_structs = [s for s in manifest["structures"] if s["atlas_id"] == ribs_key]

            if not rib_structs:
                print(f"  Warning: No {ribs_key} structures found")
                continue

            # Collect all rib geometry
            all_rib_verts = []
            all_rib_faces = []

            for struct in rib_structs:
                vert_start = struct["vertex_offset"]
                vert_end = vert_start + struct["vertex_count"]
                face_start = struct["face_offset"]
                face_end = face_start + struct["triangle_count"]

                all_rib_verts.append(consolidated_verts[vert_start:vert_end])
                all_rib_faces.append(consolidated_faces[face_start:face_end])

            # Collect articulation geometry for this side
            side_char = side[0].lower()
            side_articulations = [
                (atlas_id, geom) for atlas_id, geom in articulation_geometry.items()
                if f"_{side_char}" in atlas_id
            ]

            for _, (art_verts, art_faces) in side_articulations:
                all_rib_verts.append(art_verts)
                all_rib_faces.append(art_faces)

            print(f"  {ribs_key}: merging {len(rib_structs)} rib fragments + {len(side_articulations)} articulations")

            # Consolidate all rib geometry
            if all_rib_verts:
                merged_verts = np.vstack(all_rib_verts)

                # Remap faces to consolidated indices
                merged_faces = []
                vert_offset = 0
                for i, faces in enumerate(all_rib_faces):
                    merged_faces.append(faces + vert_offset)
                    vert_offset += len(all_rib_verts[i])

                merged_faces = np.vstack(merged_faces)

                # Replace all rib structures with single consolidated structure
                # Remove old rib structures
                manifest["structures"] = [s for s in manifest["structures"] if s["atlas_id"] != ribs_key]

                # Add consolidated structure
                consolidated_struct = {
                    "atlas_id": ribs_key,
                    "source_structure": ribs_key,
                    "side": side,
                    "source_file": f"merged from {len(rib_structs)} fragments + {len(side_articulations)} articulations",
                    "vertex_offset": len(consolidated_verts),
                    "face_offset": len(consolidated_faces),
                    "vertex_count": len(merged_verts),
                    "triangle_count": len(merged_faces),
                    "bbox_min_mm": merged_verts.min(axis=0).tolist(),
                    "bbox_max_mm": merged_verts.max(axis=0).tolist(),
                }

                manifest["structures"].append(consolidated_struct)

                # Add to consolidated mesh
                consolidated_verts = np.vstack([consolidated_verts, merged_verts])
                consolidated_faces = np.vstack([consolidated_faces, merged_faces + len(consolidated_verts) - len(merged_verts)])

        # Update remaining structures' offsets
        current_vert_offset = 0
        current_face_offset = 0

        for struct in manifest["structures"]:
            old_vert_offset = struct["vertex_offset"]
            old_face_offset = struct["face_offset"]
            struct["vertex_offset"] = current_vert_offset
            struct["face_offset"] = current_face_offset
            current_vert_offset += struct["vertex_count"]
            current_face_offset += struct["triangle_count"]

        # Rebuild final consolidated mesh with correct offsets
        final_verts = []
        final_faces = []

        for struct in manifest["structures"]:
            vert_start = struct["vertex_offset"]
            vert_end = vert_start + struct["vertex_count"]
            face_start = struct["face_offset"]
            face_end = face_start + struct["triangle_count"]

            final_verts.append(consolidated_verts[vert_start:vert_end])
            final_faces.append(consolidated_faces[face_start:face_end])

        if final_verts:
            final_verts = np.vstack(final_verts)
            final_faces = np.vstack(final_faces)
        else:
            final_verts = np.empty((0, 3), dtype=np.float32)
            final_faces = np.empty((0, 3), dtype=np.uint32)

        print(f"  Final mesh: {len(final_verts)} vertices, {len(final_faces)} faces")

        # Write mesh
        write_mesh_binary(subject_dir, final_verts, final_faces)

        # Save manifest
        save_manifest(subject, manifest)
        print(f"  Updated manifest: {len(manifest['structures'])} structures")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "command",
        choices=["merge"],
        help="Command to run",
    )

    args = parser.parse_args()

    if args.command == "merge":
        return cmd_merge(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
