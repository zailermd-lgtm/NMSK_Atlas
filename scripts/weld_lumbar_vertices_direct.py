#!/usr/bin/env python3
"""Direct vertex welding for lumbar region to improve disc-vertebra connectivity.

This script:
1. Loads the current mesh
2. Identifies lumbar disc and vertebrae vertices (by spatial proximity and z-range)
3. Welds vertices that are close together
4. Writes the improved mesh
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from collections import defaultdict

import numpy as np
from scipy.spatial import cKDTree

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

BUILD_DIR = REPO_ROOT / "build" / "vh"


def read_mesh_binary(subject_dir: Path) -> tuple[np.ndarray, np.ndarray]:
    verts = np.fromfile(subject_dir / "vertices.f32", dtype=np.float32).reshape(-1, 3)
    faces = np.fromfile(subject_dir / "faces.u32", dtype=np.uint32).reshape(-1, 3)
    return verts, faces


def write_mesh_binary(subject_dir: Path, vertices: np.ndarray, faces: np.ndarray) -> None:
    vertices.astype(np.float32).tofile(subject_dir / "vertices.f32")
    faces.astype(np.uint32).tofile(subject_dir / "faces.u32")


def load_manifest(subject: str) -> dict:
    manifest_path = BUILD_DIR / subject / "manifest.json"
    with open(manifest_path) as f:
        return json.load(f)


def get_lumbar_vertex_indices(manifest: dict, verts: np.ndarray) -> tuple[set, set]:
    """Identify lumbar vertebrae and disc vertices by looking at manifest."""
    lumbar_vert_indices = set()
    disc_vert_indices = set()
    
    for struct in manifest["structures"]:
        if "lumbar" in struct["atlas_id"] or "disc_l" in struct["atlas_id"]:
            start = struct["vertex_offset"]
            end = start + struct["vertex_count"]
            
            # Filter by what actually exists in the mesh
            if end <= len(verts):
                indices = set(range(start, end))
                if "disc" in struct["atlas_id"]:
                    disc_vert_indices.update(indices)
                else:
                    lumbar_vert_indices.update(indices)
    
    return lumbar_vert_indices, disc_vert_indices


def weld_lumbar_vertices(
    vertices: np.ndarray,
    faces: np.ndarray,
    lumbar_indices: set,
    disc_indices: set,
    distance_threshold: float = 5.0,
) -> tuple[np.ndarray, np.ndarray]:
    """Weld disc vertices close to lumbar vertebrae."""
    
    if not lumbar_indices or not disc_indices:
        print("  No lumbar or disc vertices found")
        return vertices, faces
    
    # Extract lumbar vertebrae vertices
    lumbar_verts = vertices[list(lumbar_indices)]
    lumbar_indices_list = list(lumbar_indices)
    
    # Build KDTree for lumbar vertices
    tree = cKDTree(lumbar_verts)
    
    # Find disc vertices that should be merged with lumbar
    merge_map = {}  # old_index -> new_index
    merge_count = 0
    
    for disc_idx in disc_indices:
        disc_vert = vertices[disc_idx:disc_idx+1]

        # Find nearest lumbar vertex
        dist, neighbor_idx = tree.query(disc_vert, k=1)

        if dist.item() < distance_threshold:
            # Merge: map this disc vertex to the nearest lumbar vertex
            merge_map[disc_idx] = lumbar_indices_list[neighbor_idx.item()]
            merge_count += 1
    
    print(f"  Merged {merge_count} disc vertices with lumbar vertices")
    
    if not merge_map:
        print("  No vertices matched for merging")
        return vertices, faces
    
    # Remap faces to use merged vertices
    remapped_faces = faces.copy()
    for i, face in enumerate(faces):
        for j in range(3):
            if face[j] in merge_map:
                remapped_faces[i, j] = merge_map[face[j]]
    
    print(f"  Remapped {len(set(remapped_faces.flat) & set(merge_map.values()))} face references")
    
    return vertices, remapped_faces.astype(np.uint32)


def cmd_weld(args: argparse.Namespace) -> int:
    """Weld lumbar vertebrae and disc vertices."""
    print("Direct lumbar vertex welding (topology optimization)\n")
    
    for subject in ["ct_vhm", "ct_vhf"]:
        print(f"{subject}:")
        subject_dir = BUILD_DIR / subject
        
        # Read mesh and manifest
        verts, faces = read_mesh_binary(subject_dir)
        manifest = load_manifest(subject)
        
        print(f"  Current mesh: {len(verts)} vertices, {len(faces)} faces")
        
        # Get lumbar vertex indices
        lumbar_indices, disc_indices = get_lumbar_vertex_indices(manifest, verts)
        
        print(f"  Lumbar vertices: {len(lumbar_indices)}")
        print(f"  Lumbar disc vertices: {len(disc_indices)}")
        
        # Weld vertices
        verts, faces = weld_lumbar_vertices(
            verts, faces,
            lumbar_indices, disc_indices,
            distance_threshold=5.0,
        )
        
        # Write mesh
        write_mesh_binary(subject_dir, verts, faces)
        print(f"  Wrote mesh: {len(verts)} vertices, {len(faces)} faces\n")
    
    print("Vertex welding complete. Now re-export bundles and verify continuity:")
    print("  python3 scripts/export_viewer_bundle.py --subject ct_vhm -o build/viewer_male --budget-scale 0.85")
    print("  python3 scripts/export_viewer_bundle.py --subject ct_vhf -o build/viewer_female --budget-scale 0.85")
    print("  python3 scripts/verify_vertebral_continuity.py analyze")
    
    return 0


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("command", choices=["weld"], help="Command to run")
    
    args = parser.parse_args()
    
    if args.command == "weld":
        return cmd_weld(args)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
