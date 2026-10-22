#!/usr/bin/env python3
"""Post-process existing remeshed ribs to improve connectivity.

Instead of re-voxelizing from scratch (memory intensive), load the existing
remeshed OBJ files and apply connectivity improvements via mesh-based operations.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import trimesh
from scipy import ndimage
from skimage import measure

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = REPO_ROOT / "data" / "ct_sources" / "task_outputs"


def load_obj_mesh(filepath: Path) -> tuple[np.ndarray, np.ndarray]:
    """Load mesh from OBJ file."""
    print(f"  Loading {filepath.name}...")
    mesh = trimesh.load(filepath, process=False)
    return np.array(mesh.vertices), np.array(mesh.faces)


def save_obj_mesh(filepath: Path, vertices: np.ndarray, faces: np.ndarray) -> None:
    """Save mesh to OBJ file."""
    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    mesh.export(filepath)
    print(f"  Saved {filepath.name} ({len(vertices)} verts, {len(faces)} faces)")


def improve_connectivity(verts: np.ndarray, faces: np.ndarray, voxel_size: float = 2.0) -> tuple[np.ndarray, np.ndarray]:
    """Apply connectivity improvements via voxelization + aggressive dilation."""
    print(f"  Improving connectivity at {voxel_size}mm resolution...")

    # Create mesh for voxelization
    mesh = trimesh.Trimesh(vertices=verts, faces=faces, process=False)

    # Get bounds
    v_min = verts.min(axis=0)
    v_max = verts.max(axis=0)
    grid_dims = np.ceil((v_max - v_min) / voxel_size).astype(int) + 1

    print(f"    Grid dimensions: {grid_dims}")
    print(f"    Grid size: {np.prod(grid_dims):,.0f} voxels")

    # Create binary voxel grid by sampling at centers
    voxel_grid = np.zeros(grid_dims, dtype=bool)

    print("    Sampling voxels...")
    # Sample every voxel center
    for x in range(grid_dims[0]):
        if x % 30 == 0:
            print(f"      X: {x}/{grid_dims[0]}")
        for y in range(grid_dims[1]):
            for z in range(grid_dims[2]):
                # Voxel center in world coords
                pt = np.array([x, y, z]) * voxel_size + v_min
                # Check if inside mesh using ray casting
                if mesh.contains(pt.reshape(1, -1))[0]:
                    voxel_grid[x, y, z] = True

    # Apply aggressive dilation
    print("    Applying dilation...")
    struct = ndimage.generate_binary_structure(3, 26)
    dilated = ndimage.binary_dilation(voxel_grid, structure=struct, iterations=10)

    # Reconstruct mesh
    print("    Running marching cubes...")
    result = measure.marching_cubes(dilated, level=0.5)
    verts_new = result[0] * voxel_size + v_min
    faces_new = result[1]

    print(f"    New mesh: {len(verts_new)} vertices, {len(faces_new)} faces")

    return verts_new, faces_new


def cmd_process(args: argparse.Namespace) -> int:
    """Post-process existing remeshed ribs."""

    for subject in ["ct_vhm", "ct_vhf"]:
        for atlas_id in ["ribs_l", "ribs_r"]:
            print(f"\nProcessing {subject} {atlas_id}...")

            input_file = OUTPUT_DIR / f"{subject}_{atlas_id}_remeshed.obj"

            if not input_file.exists():
                print(f"  WARNING: {input_file.name} not found, skipping")
                continue

            try:
                verts, faces = load_obj_mesh(input_file)
                print(f"    Loaded: {len(verts)} vertices, {len(faces)} faces")

                verts_new, faces_new = improve_connectivity(verts, faces, voxel_size=2.0)

                # Overwrite with improved version
                save_obj_mesh(input_file, verts_new, faces_new)

            except Exception as e:
                print(f"  ERROR: {e}")
                import traceback
                traceback.print_exc()
                return 1

    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["process"], help="Command to run")

    args = parser.parse_args()

    if args.command == "process":
        return cmd_process(args)

    return 1


if __name__ == "__main__":
    sys.exit(main())
