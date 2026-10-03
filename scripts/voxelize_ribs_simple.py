#!/usr/bin/env python3
"""Lightweight rib voxelization without trimesh.voxelized().

Uses direct numpy/scipy voxel sampling from mesh triangles.
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
    """Extract vertices and faces for a single structure."""
    vert_start = struct["vertex_offset"]
    vert_end = vert_start + struct["vertex_count"]
    face_start = struct["face_offset"]
    face_end = face_start + struct["triangle_count"]

    if face_start >= len(all_faces):
        return np.empty((0, 3)), np.empty((0, 3), dtype=np.uint32)

    face_end = min(face_end, len(all_faces))

    verts = all_verts[vert_start:vert_end].copy()
    faces = all_faces[face_start:face_end].copy()

    # Remap face indices
    faces_clamped = faces.copy()
    for i in range(faces_clamped.shape[0]):
        for j in range(3):
            idx = faces_clamped[i, j]
            if idx >= vert_start:
                idx_local = idx - vert_start
                faces_clamped[i, j] = min(idx_local, len(verts) - 1)
            else:
                faces_clamped[i, j] = 0

    return verts, faces_clamped


def voxelize_mesh_simple(
    vertices: np.ndarray,
    faces: np.ndarray,
    voxel_size: float = 2.0,
) -> np.ndarray:
    """Simple numpy-based voxelization by sampling at voxel centers.

    Args:
        vertices: mesh vertices [N, 3]
        faces: mesh faces [M, 3]
        voxel_size: voxel resolution in mm

    Returns:
        Binary voxel grid
    """
    # Get bounds
    v_min = vertices.min(axis=0)
    v_max = vertices.max(axis=0)

    # Create voxel grid
    dims = np.ceil((v_max - v_min) / voxel_size).astype(int) + 1
    voxel_grid = np.zeros(dims, dtype=bool)

    print(f"  Voxel grid shape: {voxel_grid.shape}")
    print(f"  Voxel grid size: {dims[0] * dims[1] * dims[2] / 1e6:.1f}M voxels")

    # Voxelize by iterating over faces and rasterizing
    print("  Rasterizing triangles into voxels...")
    for face_idx, face in enumerate(faces):
        if face_idx % 50000 == 0:
            print(f"    Face {face_idx}/{len(faces)}")

        # Get triangle vertices
        v0 = vertices[face[0]]
        v1 = vertices[face[1]]
        v2 = vertices[face[2]]

        # Get bounding box of triangle
        bbox_min = np.floor((np.minimum(v0, np.minimum(v1, v2)) - v_min) / voxel_size).astype(int)
        bbox_max = np.ceil((np.maximum(v0, np.maximum(v1, v2)) - v_min) / voxel_size).astype(int)

        # Clamp to grid
        bbox_min = np.maximum(bbox_min, 0)
        bbox_max = np.minimum(bbox_max, dims - 1)

        # Simple approach: check voxel centers against triangle
        for x in range(bbox_min[0], bbox_max[0] + 1):
            for y in range(bbox_min[1], bbox_max[1] + 1):
                for z in range(bbox_min[2], bbox_max[2] + 1):
                    voxel_grid[x, y, z] = True

    return voxel_grid, v_min, voxel_size


def voxelize_structure(
    subject: str,
    atlas_id: str,
    voxel_size: float = 2.0,
    dilation_iterations: int = 3,
) -> Tuple[np.ndarray, np.ndarray]:
    """Voxelize and reconstruct mesh.

    Args:
        subject: 'ct_vhm' or 'ct_vhf'
        atlas_id: 'ribs_l' or 'ribs_r'
        voxel_size: resolution in mm
        dilation_iterations: morphological dilation iterations

    Returns:
        - vertices: reconstructed mesh vertices
        - faces: reconstructed mesh faces
    """
    print(f"\nProcessing {subject} {atlas_id}...")

    subject_dir = BUILD_DIR / subject
    manifest = load_manifest(subject)
    all_verts, all_faces = read_mesh_binary(subject_dir)

    # Find and extract structure
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

    # Voxelize
    print(f"  Voxelizing at {voxel_size}mm resolution...")
    voxel_grid, v_min, vs = voxelize_mesh_simple(
        consolidated_verts, consolidated_faces, voxel_size
    )

    # Apply dilation
    print(f"  Applying dilation ({dilation_iterations} iterations)...")
    struct = ndimage.generate_binary_structure(3, 26)
    dilated = ndimage.binary_dilation(voxel_grid, structure=struct, iterations=dilation_iterations)

    # Marching cubes
    print("  Running marching cubes...")
    result = measure.marching_cubes(dilated, level=0.5)
    if len(result) == 4:
        vertices_voxel, faces_new = result[0], result[1]
    else:
        vertices_voxel, faces_new = result[0], result[1]

    # Convert to world coordinates
    vertices = vertices_voxel * voxel_size + v_min

    print(f"  Reconstructed mesh: {len(vertices)} vertices, {len(faces_new)} faces")

    return vertices, faces_new


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["voxelize"], help="Command to run")
    parser.add_argument("--voxel-size", type=float, default=2.0, help="Voxel size in mm")
    parser.add_argument("--dilation-iterations", type=int, default=3, help="Dilation iterations")

    args = parser.parse_args()

    if args.command != "voxelize":
        return 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    results = {}

    for subject in ["ct_vhm", "ct_vhf"]:
        results[subject] = {}
        for atlas_id in ["ribs_l", "ribs_r"]:
            try:
                print(f"\n{'='*70}")
                vertices, faces = voxelize_structure(
                    subject, atlas_id, args.voxel_size, args.dilation_iterations
                )

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


if __name__ == "__main__":
    sys.exit(main())
