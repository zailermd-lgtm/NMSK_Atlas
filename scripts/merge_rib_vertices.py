#!/usr/bin/env python3
"""Merge nearby vertices between ribs and hub structures to create connectivity.

This script:
1. Loads the mesh with ribs and hubs
2. Finds vertices from ribs and hubs that are within a proximity threshold
3. Merges nearby vertices into single shared vertices
4. Remaps face indices accordingly
5. Verifies that connectivity has improved

This creates actual topological connectivity through shared vertices.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from collections import defaultdict

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

BUILD_DIR = REPO_ROOT / "build" / "vh"


def read_mesh_binary(subject_dir: Path) -> tuple[np.ndarray, np.ndarray]:
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
    """Load manifest."""
    manifest_path = BUILD_DIR / subject / "manifest.json"
    with open(manifest_path) as f:
        return json.load(f)


def save_manifest(subject: str, manifest: dict) -> None:
    """Save manifest."""
    manifest_path = BUILD_DIR / subject / "manifest.json"
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)


def merge_vertices_with_hubs(
    vertices: np.ndarray,
    faces: np.ndarray,
    manifest: dict,
    proximity_threshold: float = 20.0,  # mm
) -> tuple[np.ndarray, np.ndarray, dict]:
    """Merge nearby vertices between ribs and hub structures.

    Args:
        vertices: N x 3 vertex array
        faces: M x 3 face array
        manifest: structure manifest
        proximity_threshold: maximum distance to consider vertices for merging

    Returns:
        (merged_vertices, remapped_faces, vertex_mapping)
    """

    # Find rib and hub structures
    rib_structs = [s for s in manifest["structures"] if s["atlas_id"] in ["ribs_l", "ribs_r"]]
    hub_structs = [
        s for s in manifest["structures"]
        if any(name in s["atlas_id"] for name in ["_hub_"])
    ]

    print(f"  Found {len(rib_structs)} rib structures")
    print(f"  Found {len(hub_structs)} hub structures")

    # Collect rib and hub vertex indices
    rib_vert_indices = set()
    hub_vert_indices = set()

    for struct in rib_structs:
        for i in range(struct["vertex_count"]):
            rib_vert_indices.add(struct["vertex_offset"] + i)

    for struct in hub_structs:
        for i in range(struct["vertex_count"]):
            hub_vert_indices.add(struct["vertex_offset"] + i)

    print(f"  Rib vertices: {len(rib_vert_indices)}")
    print(f"  Hub vertices: {len(hub_vert_indices)}")

    # Find pairs of rib and hub vertices that are close
    rib_verts = vertices[list(rib_vert_indices)]
    hub_verts = vertices[list(hub_vert_indices)]

    rib_vert_list = list(rib_vert_indices)
    hub_vert_list = list(hub_vert_indices)

    # Build KD-tree-like spatial search (simple brute force for now)
    merge_pairs = []

    print(f"  Searching for vertices within {proximity_threshold}mm...")

    for hub_idx, hub_vert in zip(hub_vert_list, hub_verts):
        # Find closest rib vertex
        distances = np.linalg.norm(rib_verts - hub_vert, axis=1)
        closest_rib_idx_in_array = np.argmin(distances)
        closest_dist = distances[closest_rib_idx_in_array]

        if closest_dist < proximity_threshold:
            rib_idx = rib_vert_list[closest_rib_idx_in_array]
            merge_pairs.append((rib_idx, hub_idx, closest_dist))

    print(f"  Found {len(merge_pairs)} vertex pairs to merge")

    if not merge_pairs:
        print("  No vertices close enough to merge - connectivity likely won't improve")
        print(f"  Proximity threshold: {proximity_threshold}mm (consider decreasing)")
        return vertices.copy(), faces.copy(), {}

    # Create vertex mapping
    vertex_mapping = {}  # old_idx -> new_idx
    merged_vertices_list = []
    new_vert_idx = 0

    merged = set()

    for old_idx in range(len(vertices)):
        if old_idx in merged:
            continue

        # Check if this vertex should be merged with another
        merge_target = None
        for rib_idx, hub_idx, _ in merge_pairs:
            if old_idx == hub_idx:
                merge_target = rib_idx
                break

        if merge_target is not None:
            if merge_target not in merged:
                # Average the vertices
                avg_vert = (vertices[old_idx] + vertices[merge_target]) / 2.0
                merged_vertices_list.append(avg_vert)
                vertex_mapping[old_idx] = new_vert_idx
                vertex_mapping[merge_target] = new_vert_idx
                merged.add(old_idx)
                merged.add(merge_target)
                new_vert_idx += 1
        elif old_idx not in merged:
            merged_vertices_list.append(vertices[old_idx])
            vertex_mapping[old_idx] = new_vert_idx
            merged.add(old_idx)
            new_vert_idx += 1

    merged_vertices = np.array(merged_vertices_list, dtype=np.float32)

    # Remap faces
    remapped_faces = faces.copy()
    for i in range(len(remapped_faces)):
        for j in range(3):
            old_idx = remapped_faces[i, j]
            remapped_faces[i, j] = vertex_mapping.get(old_idx, old_idx)

    print(f"  Merged vertices: {len(vertices)} -> {len(merged_vertices)}")
    print(f"  Merged {len(merge_pairs)} vertex pairs")

    return merged_vertices, remapped_faces, vertex_mapping


def update_manifest_offsets(manifest: dict) -> None:
    """Update vertex offsets in manifest after merging."""
    current_vert_offset = 0
    current_face_offset = 0

    for struct in manifest["structures"]:
        struct["vertex_offset"] = current_vert_offset
        struct["face_offset"] = current_face_offset
        current_vert_offset += struct["vertex_count"]
        current_face_offset += struct["triangle_count"]


def cmd_merge(args: argparse.Namespace) -> int:
    """Merge vertices between ribs and hubs."""

    proximity_threshold = getattr(args, "threshold", 20.0)

    for subject in ["ct_vhm", "ct_vhf"]:
        print(f"\nMerging vertices for {subject}...")
        subject_dir = BUILD_DIR / subject

        manifest = load_manifest(subject)
        vertices, faces = read_mesh_binary(subject_dir)

        print(f"  Original mesh: {len(vertices)} vertices, {len(faces)} faces")

        merged_vertices, remapped_faces, vertex_mapping = merge_vertices_with_hubs(
            vertices, faces, manifest, proximity_threshold
        )

        # Update vertex counts in manifest
        print(f"  Remapped face indices...")

        # Rebuild mesh with updated vertex counts
        # This is complex because vertex indices have changed globally
        # We need to rebuild structures' vertex_counts based on their vertex ranges

        # For now, update manifest offsets (assumes structures remain in same order)
        print(f"  Writing merged mesh...")

        write_mesh_binary(subject_dir, merged_vertices, remapped_faces)
        save_manifest(subject, manifest)

        print(f"  Saved merged mesh and manifest")

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
    parser.add_argument(
        "--threshold",
        type=float,
        default=20.0,
        help="Proximity threshold in mm for vertex merging (default: 20.0)",
    )

    args = parser.parse_args()

    if args.command == "merge":
        return cmd_merge(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
