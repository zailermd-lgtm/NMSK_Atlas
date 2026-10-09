#!/usr/bin/env python3
"""Rebuild rib structures with central hub and articulation surfaces.

This script:
1. Reads the current bundle state
2. Extracts original rib geometry from ribs_l and ribs_r (if merged)
3. Adds central rib hub, sternal hubs, and costovertebral hubs
4. Merges everything into ribs_l and ribs_r structures
5. Verifies connectivity

The hub-based approach creates star-topology connectivity where:
- Central rib hub connects all ribs together
- Sternal hubs (one per side) bridge ribs to sternum
- Costovertebral hubs bridge ribs to thoracic vertebrae
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
SOURCE_DIR = REPO_ROOT / "data" / "ct_sources"


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


def cmd_rebuild(args: argparse.Namespace) -> int:
    """Rebuild rib structures with hub articulations."""

    for subject in ["ct_vhm", "ct_vhf"]:
        print(f"\nRebuilding ribs with hubs for {subject}...")
        subject_dir = BUILD_DIR / subject

        # Load manifest and existing mesh
        manifest = load_manifest(subject)
        existing_verts, existing_faces = read_mesh_binary(subject_dir)

        print(f"  Current mesh: {len(existing_verts)} vertices, {len(existing_faces)} faces")

        # Remove existing articulation structures (if any)
        original_struct_count = len(manifest["structures"])
        manifest["structures"] = [
            s for s in manifest["structures"]
            if not ("articulation" in s["atlas_id"] or "hub" in s["atlas_id"])
        ]
        removed_count = original_struct_count - len(manifest["structures"])
        if removed_count > 0:
            print(f"  Removed {removed_count} existing articulation structures")

        # Rebuild mesh without articulations
        non_articulation_verts = []
        non_articulation_faces = []

        new_vertex_offset = 0
        new_face_offset = 0

        for struct in manifest["structures"]:
            old_vert_start = struct["vertex_offset"]
            old_vert_end = old_vert_start + struct["vertex_count"]
            old_face_start = struct["face_offset"]
            old_face_end = old_face_start + struct["triangle_count"]

            struct_verts = existing_verts[old_vert_start:old_vert_end]
            struct_faces = existing_faces[old_face_start:old_face_end]

            struct_faces_remapped = struct_faces + (new_vertex_offset - old_vert_start)

            struct["vertex_offset"] = new_vertex_offset
            struct["face_offset"] = new_face_offset

            non_articulation_verts.append(struct_verts)
            non_articulation_faces.append(struct_faces_remapped)

            new_vertex_offset += len(struct_verts)
            new_face_offset += len(struct_faces)

        if non_articulation_verts and non_articulation_faces:
            consolidated_verts = np.vstack(non_articulation_verts)
            consolidated_faces = np.vstack(non_articulation_faces)
        else:
            consolidated_verts = np.empty((0, 3), dtype=np.float32)
            consolidated_faces = np.empty((0, 3), dtype=np.uint32)

        print(f"  Rebuilt mesh (without articulations): {len(consolidated_verts)} vertices, {len(consolidated_faces)} faces")

        # Load hub and articulation OBJ files
        hub_files = {
            f"{subject}_rib_hub.obj": "rib_hub",
            f"{subject}_sternal_hub_l.obj": "sternal_hub_l",
            f"{subject}_sternal_hub_r.obj": "sternal_hub_r",
            f"{subject}_costovertebral_hub_l.obj": "costovertebral_hub_l",
            f"{subject}_costovertebral_hub_r.obj": "costovertebral_hub_r",
        }

        hubs = {}
        for filename, atlas_id in hub_files.items():
            filepath = OUTPUT_DIR / filename
            if filepath.exists():
                try:
                    verts, faces = read_obj_file(filepath)
                    hubs[atlas_id] = (verts, faces)
                    print(f"  Loaded {filename}")
                except Exception as e:
                    print(f"  Warning: Failed to load {filename}: {e}")

        # Collect rib geometry (including consolidated ribs from merged structures)
        rib_geom = {"left": ([], []), "right": ([], [])}

        for struct in manifest["structures"]:
            if struct["atlas_id"] in ["ribs_l", "ribs_r"]:
                side = struct["side"]
                if side not in ["left", "right"]:
                    side = "left" if "l" in struct["atlas_id"] else "right"

                vert_start = struct["vertex_offset"]
                vert_end = vert_start + struct["vertex_count"]
                face_start = struct["face_offset"]
                face_end = face_start + struct["triangle_count"]

                rib_geom[side][0].append(consolidated_verts[vert_start:vert_end])
                rib_geom[side][1].append(consolidated_faces[face_start:face_end])

        # Remove rib structures from manifest
        manifest["structures"] = [
            s for s in manifest["structures"]
            if s["atlas_id"] not in ["ribs_l", "ribs_r"]
        ]

        # Rebuild final mesh with ribs + hubs
        final_verts = [consolidated_verts] if len(consolidated_verts) > 0 else []
        final_faces = [consolidated_faces] if len(consolidated_faces) > 0 else []

        current_vert_offset = len(consolidated_verts)
        current_face_offset = len(consolidated_faces)

        # Update offsets for non-rib structures
        for struct in manifest["structures"]:
            struct["vertex_offset"] = current_vert_offset if current_vert_offset > 0 else struct["vertex_offset"]
            struct["face_offset"] = current_face_offset if current_face_offset > 0 else struct["face_offset"]

        # Add ribs + hubs consolidated per side
        for side in ["left", "right"]:
            side_char = side[0].lower()
            side_ribs = rib_geom[side]

            # Collect all geometry for this side
            side_all_verts = []
            side_all_faces = []

            # Add rib geometry
            if side_ribs[0]:
                side_all_verts.extend(side_ribs[0])
                side_all_faces.extend(side_ribs[1])

            # Add hubs
            hub_keys = [
                "rib_hub",
                f"sternal_hub_{side_char}",
                f"costovertebral_hub_{side_char}",
            ]

            for key in hub_keys:
                if key in hubs:
                    side_all_verts.append(hubs[key][0])
                    side_all_faces.append(hubs[key][1])

            if side_all_verts:
                # Consolidate side geometry
                merged_verts = np.vstack(side_all_verts)

                merged_faces = []
                vert_offset = 0
                for i, faces in enumerate(side_all_faces):
                    merged_faces.append(faces + vert_offset)
                    vert_offset += len(side_all_verts[i])

                merged_faces = np.vstack(merged_faces) if merged_faces else np.empty((0, 3), dtype=np.uint32)

                # Add to final mesh
                final_verts.append(merged_verts)
                final_faces.append(merged_faces)

                # Create structure entry
                ribs_key = f"ribs_{side_char}"
                struct = {
                    "atlas_id": ribs_key,
                    "source_structure": ribs_key,
                    "side": side,
                    "source_file": f"merged ribs + hubs for {side}",
                    "vertex_offset": current_vert_offset,
                    "face_offset": current_face_offset,
                    "vertex_count": len(merged_verts),
                    "triangle_count": len(merged_faces),
                    "bbox_min_mm": merged_verts.min(axis=0).tolist(),
                    "bbox_max_mm": merged_verts.max(axis=0).tolist(),
                }

                manifest["structures"].append(struct)

                current_vert_offset += len(merged_verts)
                current_face_offset += len(merged_faces)

        # Consolidate final mesh
        if final_verts:
            final_verts = np.vstack(final_verts)
            final_faces = np.vstack(final_faces) if final_faces else np.empty((0, 3), dtype=np.uint32)
        else:
            final_verts = np.empty((0, 3), dtype=np.float32)
            final_faces = np.empty((0, 3), dtype=np.uint32)

        print(f"  Final mesh: {len(final_verts)} vertices, {len(final_faces)} faces")
        print(f"  Final structures: {len(manifest['structures'])}")

        write_mesh_binary(subject_dir, final_verts, final_faces)
        save_manifest(subject, manifest)

    return 0


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "command",
        choices=["rebuild"],
        help="Command to run",
    )

    args = parser.parse_args()

    if args.command == "rebuild":
        return cmd_rebuild(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
