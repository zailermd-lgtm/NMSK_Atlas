#!/usr/bin/env python3
"""Generate a larger central rib hub for improved connectivity.

Increases hub radius to better bridge rib gaps.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage
from skimage import measure
import trimesh

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

BUILD_DIR = REPO_ROOT / "build" / "vh"
OUTPUT_DIR = REPO_ROOT / "data" / "ct_sources" / "task_outputs"


def read_mesh_binary(subject_dir: Path) -> tuple[np.ndarray, np.ndarray]:
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


def extract_structure_mesh(all_verts: np.ndarray, all_faces: np.ndarray, struct: dict) -> tuple[np.ndarray, np.ndarray]:
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


def create_icosphere(radius: float, subdivisions: int = 3) -> tuple[np.ndarray, np.ndarray]:
    """Create an icosphere."""
    phi = (1.0 + np.sqrt(5.0)) / 2.0

    vertices = np.array([
        [-1, phi, 0], [1, phi, 0], [-1, -phi, 0], [1, -phi, 0],
        [0, -1, phi], [0, 1, phi], [0, -1, -phi], [0, 1, -phi],
        [phi, 0, -1], [phi, 0, 1], [-phi, 0, -1], [-phi, 0, 1],
    ], dtype=np.float32)

    vertices = vertices / np.linalg.norm(vertices[0]) * radius

    faces = np.array([
        [0, 11, 5], [0, 5, 1], [0, 1, 7], [0, 7, 10], [0, 10, 11],
        [1, 5, 9], [5, 11, 4], [11, 10, 2], [10, 7, 6], [7, 1, 8],
        [3, 9, 4], [3, 4, 2], [3, 2, 6], [3, 6, 8], [3, 8, 9],
        [4, 9, 5], [2, 4, 11], [6, 2, 10], [8, 6, 7], [9, 8, 1],
    ], dtype=np.uint32)

    for _ in range(subdivisions):
        faces_new = []
        for face in faces:
            v0, v1, v2 = vertices[face[0]], vertices[face[1]], vertices[face[2]]
            m0 = (v0 + v1) / 2.0
            m1 = (v1 + v2) / 2.0
            m2 = (v2 + v0) / 2.0
            m0 = m0 / np.linalg.norm(m0) * radius
            m1 = m1 / np.linalg.norm(m1) * radius
            m2 = m2 / np.linalg.norm(m2) * radius

            m0_idx = len(vertices)
            m1_idx = len(vertices) + 1
            m2_idx = len(vertices) + 2
            vertices = np.vstack([vertices, [m0, m1, m2]])

            faces_new.append([face[0], m0_idx, m2_idx])
            faces_new.append([face[1], m1_idx, m0_idx])
            faces_new.append([face[2], m2_idx, m1_idx])
            faces_new.append([m0_idx, m1_idx, m2_idx])
        faces = np.array(faces_new, dtype=np.uint32)

    return vertices, faces


def voxelize_and_merge_ribs_with_hub(subject: str, hub_radius_factor: float = 0.5) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """Voxelize ribs with larger hub, then merge."""
    print(f"\nProcessing {subject}...")

    subject_dir = BUILD_DIR / subject
    manifest = load_manifest(subject)
    all_verts, all_faces = read_mesh_binary(subject_dir)

    # Extract ribs
    all_rib_verts = []
    all_rib_faces = []
    for atlas_id in ["ribs_l", "ribs_r"]:
        structures = [s for s in manifest["structures"] if s["atlas_id"] == atlas_id]
        for struct in structures:
            verts, faces = extract_structure_mesh(all_verts, all_faces, struct)
            if len(verts) > 0:
                all_rib_verts.append(verts)
                all_rib_faces.append(faces)

    # Consolidate ribs
    consolidated_verts = np.vstack(all_rib_verts)
    consolidated_faces = []
    vert_offset = 0
    for i, faces in enumerate(all_rib_faces):
        consolidated_faces.append(faces + vert_offset)
        vert_offset += len(all_rib_verts[i])
    consolidated_faces = np.vstack(consolidated_faces)

    print(f"  Ribs: {len(consolidated_verts)} vertices, {len(consolidated_faces)} faces")

    # Create larger hub
    ribs_bbox_min = consolidated_verts.min(axis=0)
    ribs_bbox_max = consolidated_verts.max(axis=0)
    hub_center = (ribs_bbox_min + ribs_bbox_max) / 2.0
    hub_radius = (ribs_bbox_max[0] - ribs_bbox_min[0]) * hub_radius_factor

    print(f"  Hub: center={hub_center}, radius={hub_radius}mm (factor={hub_radius_factor})")

    hub_verts, hub_faces = create_icosphere(hub_radius, subdivisions=3)
    hub_verts = hub_verts + hub_center

    # Merge ribs and hub
    vert_offset = len(consolidated_verts)
    merged_verts = np.vstack([consolidated_verts, hub_verts])
    merged_faces_l = [consolidated_faces, hub_faces + vert_offset]
    merged_faces = np.vstack(merged_faces_l)

    print(f"  Merged (ribs+hub): {len(merged_verts)} vertices, {len(merged_faces)} faces")

    # Voxelize merged geometry at 2mm
    print("  Voxelizing at 2mm...")
    mesh = trimesh.Trimesh(vertices=merged_verts, faces=merged_faces, process=False)

    v_min = merged_verts.min(axis=0)
    v_max = merged_verts.max(axis=0)
    grid_dims = np.ceil((v_max - v_min) / 2.0).astype(int) + 1
    print(f"    Grid: {grid_dims}, {np.prod(grid_dims):,.0f} voxels")

    # Simple but slow voxelization: sample at voxel centers
    voxel_grid = np.zeros(grid_dims, dtype=bool)
    print("    Sampling voxels...")
    sample_step = 5  # Sample every 5th voxel for speed
    for x in range(0, grid_dims[0], sample_step):
        print(f"      X: {x}/{grid_dims[0]}", end='\r')
        for y in range(0, grid_dims[1], sample_step):
            for z in range(0, grid_dims[2], sample_step):
                pt = np.array([x, y, z]) * 2.0 + v_min
                try:
                    if mesh.contains(pt.reshape(1, -1))[0]:
                        voxel_grid[x, y, z] = True
                except:
                    pass
    print()

    # Fill missing voxels with dilation
    print("  Applying strong dilation...")
    struct = ndimage.generate_binary_structure(3, 26)
    dilated = ndimage.binary_dilation(voxel_grid, structure=struct, iterations=20)

    # Marching cubes
    print("  Marching cubes...")
    result = measure.marching_cubes(dilated, level=0.5)
    verts_new = result[0] * 2.0 + v_min
    faces_new = result[1]

    # Extract just the ribs part (split by hub)
    # This is approximate - we'll just return the whole merged mesh
    # In practice, we'd need to re-ingest into the bundle and separate components

    return verts_new, faces_new, hub_verts, hub_faces


def write_obj_file(filepath: Path, vertices: np.ndarray, faces: np.ndarray) -> None:
    """Write mesh to OBJ file."""
    with open(filepath, 'w') as f:
        for v in vertices:
            f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
        for face in faces:
            f.write(f"f {face[0]+1} {face[1]+1} {face[2]+1}\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["voxelize"], help="Command to run")
    parser.add_argument("--hub-factor", type=float, default=0.5, help="Hub radius factor (default 0.5)")

    args = parser.parse_args()

    if args.command != "voxelize":
        return 1

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for subject in ["ct_vhm", "ct_vhf"]:
        try:
            verts_new, faces_new, hub_verts, hub_faces = voxelize_and_merge_ribs_with_hub(subject, args.hub_factor)

            # Save merged output
            output_file = OUTPUT_DIR / f"{subject}_ribs_merged_with_large_hub.obj"
            write_obj_file(output_file, verts_new, faces_new)
            print(f"  Saved: {output_file} ({len(verts_new)} verts, {len(faces_new)} faces)")

        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
