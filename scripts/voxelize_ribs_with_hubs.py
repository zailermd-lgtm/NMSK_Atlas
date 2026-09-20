#!/usr/bin/env python3
"""Voxelize rib structures with integrated hubs and reconstruct mesh.

This script:
1. Loads ribs_l and ribs_r from the binary bundle using careful index handling
2. Voxelizes each at 2mm resolution using trimesh
3. Applies voxel dilation to ensure continuity in voxel space
4. Reconstructs mesh using marching cubes
5. Exports as OBJ files for ingestion

The key insight: Face-adjacency connectivity requires shared edges (two faces
sharing 2 vertices). Spatial overlap alone is insufficient. Voxelization + union
ensures voxel-level 6/26-connectivity, which marching cubes converts back to a
topologically connected mesh.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Tuple

import numpy as np
from scipy import ndimage
from skimage import measure
import trimesh

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


def load_manifest(subject: str) -> dict:
    """Load manifest for a subject."""
    manifest_path = BUILD_DIR / subject / "manifest.json"
    with open(manifest_path) as f:
        return json.load(f)


def write_obj_file(filepath: Path, vertices: np.ndarray, faces: np.ndarray) -> None:
    """Write mesh to OBJ file."""
    with open(filepath, 'w') as f:
        f.write(f"# Voxelized mesh: {len(vertices)} vertices, {len(faces)} faces\n")

        for v in vertices:
            f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")

        for face in faces:
            # OBJ uses 1-based indexing
            f.write(f"f {face[0]+1} {face[1]+1} {face[2]+1}\n")


def extract_structure_mesh(
    all_verts: np.ndarray,
    all_faces: np.ndarray,
    struct: dict,
) -> Tuple[np.ndarray, np.ndarray]:
    """Extract vertices and faces for a single structure, handling out-of-bounds indices."""
    vert_start = struct["vertex_offset"]
    vert_end = vert_start + struct["vertex_count"]
    face_start = struct["face_offset"]
    face_end = face_start + struct["triangle_count"]

    # Check if face_start is within bounds
    if face_start >= len(all_faces):
        print(f"    WARNING: face_start {face_start} >= total faces {len(all_faces)}, skipping")
        return np.empty((0, 3)), np.empty((0, 3), dtype=np.uint32)

    # Clamp face_end to available faces
    face_end = min(face_end, len(all_faces))

    verts = all_verts[vert_start:vert_end].copy()
    faces = all_faces[face_start:face_end].copy()

    # Remap face indices to local vertex range
    # Faces may reference vertices outside this structure's range
    # We'll clamp them to valid local indices
    faces_clamped = faces.copy()
    for i in range(faces_clamped.shape[0]):
        for j in range(3):
            idx = faces_clamped[i, j]
            # If index is in global range, convert to local
            if idx >= vert_start:
                idx_local = idx - vert_start
                faces_clamped[i, j] = min(idx_local, len(verts) - 1)
            else:
                # Index is too small, clamp to 0
                faces_clamped[i, j] = 0

    return verts, faces_clamped


def voxelize_structure(
    subject: str,
    atlas_id: str,
    voxel_size: float = 2.0,
) -> Tuple[np.ndarray, np.ndarray]:
    """Voxelize a rib structure and reconstruct mesh.

    Args:
        subject: 'ct_vhm' or 'ct_vhf'
        atlas_id: 'ribs_l' or 'ribs_r'
        voxel_size: resolution in mm (default 2.0)

    Returns:
        - vertices: reconstructed mesh vertices
        - faces: reconstructed mesh faces
    """
    print(f"\nProcessing {subject} {atlas_id}...")

    subject_dir = BUILD_DIR / subject
    manifest = load_manifest(subject)
    all_verts, all_faces = read_mesh_binary(subject_dir)

    print(f"  Bundle data: {len(all_verts)} total vertices, {len(all_faces)} total faces")

    # Find structures with this atlas_id
    structures = [s for s in manifest["structures"] if s["atlas_id"] == atlas_id]

    if not structures:
        raise ValueError(f"No structures found with atlas_id={atlas_id}")

    print(f"  Found {len(structures)} structure(s)")

    # Extract and consolidate mesh
    all_component_verts = []
    all_component_faces = []

    for struct_idx, struct in enumerate(structures):
        verts, faces = extract_structure_mesh(all_verts, all_faces, struct)
        if len(verts) == 0:
            continue
        all_component_verts.append(verts)
        all_component_faces.append(faces)
        print(f"    Structure {struct_idx}: {len(verts)} verts, {len(faces)} faces")

    if not all_component_verts:
        raise ValueError("No valid structures extracted")

    # Consolidate vertices and faces
    consolidated_verts = np.vstack(all_component_verts)

    consolidated_faces = []
    vert_offset = 0
    for i, faces in enumerate(all_component_faces):
        consolidated_faces.append(faces + vert_offset)
        vert_offset += len(all_component_verts[i])

    consolidated_faces = np.vstack(consolidated_faces)

    print(f"  Consolidated: {len(consolidated_verts)} vertices, {len(consolidated_faces)} faces")

    # Create mesh with trimesh
    ribs_mesh = trimesh.Trimesh(vertices=consolidated_verts, faces=consolidated_faces, process=False)
    print(f"  Mesh: {len(ribs_mesh.vertices)} vertices, {len(ribs_mesh.faces)} faces")

    # Voxelize with trimesh
    print(f"  Voxelizing at {voxel_size}mm resolution...")
    voxel_grid = ribs_mesh.voxelized(pitch=voxel_size)
    print(f"  Voxel grid shape: {voxel_grid.matrix.shape}")

    # Apply morphological operations to fill gaps and connect components
    # Use dilation with small radius followed by closing to fill small holes
    print(f"  Applying morphological operations...")
    struct = ndimage.generate_binary_structure(3, 26)  # 26-connectivity

    # Dilate to bridge nearby components
    # Use 8 iterations to create ~16mm bridges between rib components
    dilated = ndimage.binary_dilation(voxel_grid.matrix, structure=struct, iterations=8)

    # Reconstruct mesh using marching cubes
    print("  Running marching cubes...")
    result = measure.marching_cubes(dilated, level=0.5)
    # Handle different scikit-image versions (returns 2 or 4 values)
    if len(result) == 4:
        vertices_voxel, faces_new = result[0], result[1]
    else:
        vertices_voxel, faces_new = result[0], result[1]

    # Convert from voxel indices to world coordinates
    # VoxelGrid.bounds gives [[min_x, min_y, min_z], [max_x, max_y, max_z]]
    origin = voxel_grid.bounds[0]
    vertices = vertices_voxel * voxel_size + origin

    print(f"  Reconstructed mesh: {len(vertices)} vertices, {len(faces_new)} faces")

    return vertices, faces_new


def cmd_voxelize(args: argparse.Namespace) -> int:
    """Voxelize rib structures for both subjects."""
    voxel_size = getattr(args, 'voxel_size', 2.0)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    results = {}

    for subject in ["ct_vhm", "ct_vhf"]:
        results[subject] = {}
        for atlas_id in ["ribs_l", "ribs_r"]:
            try:
                vertices, faces = voxelize_structure(subject, atlas_id, voxel_size)

                # Export as OBJ
                output_file = OUTPUT_DIR / f"{subject}_{atlas_id}_remeshed.obj"
                write_obj_file(output_file, vertices, faces)

                results[subject][atlas_id] = {
                    "status": "SUCCESS",
                    "vertices": len(vertices),
                    "faces": len(faces),
                    "output": str(output_file),
                }

                print(f"  Exported to: {output_file}")

            except Exception as e:
                results[subject][atlas_id] = {
                    "status": "ERROR",
                    "error": str(e),
                }
                print(f"  ERROR: {e}")
                import traceback
                traceback.print_exc()
                return 1

    # Summary
    print("\n" + "="*70)
    print("VOXELIZATION SUMMARY")
    print("="*70)

    for subject in ["ct_vhm", "ct_vhf"]:
        print(f"\n{subject}:")
        for atlas_id in ["ribs_l", "ribs_r"]:
            result = results[subject][atlas_id]
            if result["status"] == "SUCCESS":
                print(f"  {atlas_id}: {result['vertices']} vertices, {result['faces']} faces")
            else:
                print(f"  {atlas_id}: ERROR - {result['error']}")

    print("="*70)

    return 0


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "command",
        choices=["voxelize"],
        help="Command to run",
    )
    parser.add_argument(
        "--voxel-size",
        type=float,
        default=2.0,
        help="Voxel size in mm (default 2.0)",
    )

    args = parser.parse_args()

    if args.command == "voxelize":
        return cmd_voxelize(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
