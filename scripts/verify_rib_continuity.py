#!/usr/bin/env python3
"""Verify rib continuity after articulation surface integration.

This script:
1. Extracts ribs_l and ribs_r from both male and female bundles
2. Performs face-adjacency connected-components analysis
3. Calculates main_frac = largest_component_vertices / total_vertices
4. Reports continuity metrics; target >= 0.99
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from collections import deque

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


def load_manifest(subject: str) -> dict:
    """Load manifest for a subject."""
    manifest_path = BUILD_DIR / subject / "manifest.json"
    with open(manifest_path) as f:
        return json.load(f)


def extract_structure_mesh(
    all_verts: np.ndarray,
    all_faces: np.ndarray,
    struct: dict,
) -> tuple[np.ndarray, np.ndarray]:
    """Extract vertices and faces for a single structure."""
    vert_start = struct["vertex_offset"]
    vert_end = vert_start + struct["vertex_count"]
    face_start = struct["face_offset"]
    face_end = face_start + struct["triangle_count"]

    verts = all_verts[vert_start:vert_end].copy()
    faces = all_faces[face_start:face_end].copy()

    # Remap face indices to be relative to extracted vertices
    faces -= vert_start

    return verts, faces


def build_adjacency_graph(faces: np.ndarray) -> dict[int, set[int]]:
    """Build face adjacency graph from faces.

    Two faces are adjacent if they share an edge (2 common vertices).
    Returns dict mapping face_idx -> set of adjacent face indices.
    """
    # Build edge -> faces mapping
    edge_to_faces = {}

    for face_idx, face in enumerate(faces):
        # Extract edges
        edges = [
            tuple(sorted([face[0], face[1]])),
            tuple(sorted([face[1], face[2]])),
            tuple(sorted([face[2], face[0]])),
        ]

        for edge in edges:
            if edge not in edge_to_faces:
                edge_to_faces[edge] = []
            edge_to_faces[edge].append(face_idx)

    # Build adjacency from edges
    adjacency = {}
    for face_idx in range(len(faces)):
        adjacency[face_idx] = set()

    for edge, face_list in edge_to_faces.items():
        if len(face_list) >= 2:
            for i in range(len(face_list)):
                for j in range(i + 1, len(face_list)):
                    adjacency[face_list[i]].add(face_list[j])
                    adjacency[face_list[j]].add(face_list[i])

    return adjacency


def find_connected_components(
    n_faces: int,
    adjacency: dict[int, set[int]],
    faces: np.ndarray,
) -> list[set[int]]:
    """Find connected components of faces using BFS.

    Returns list of sets, where each set contains face indices in a component.
    """
    visited = set()
    components = []

    for start_face in range(n_faces):
        if start_face in visited:
            continue

        # BFS to find all faces in this component
        component = set()
        queue = deque([start_face])
        visited.add(start_face)

        while queue:
            face_idx = queue.popleft()
            component.add(face_idx)

            for neighbor in adjacency[face_idx]:
                if neighbor not in visited:
                    visited.add(neighbor)
                    queue.append(neighbor)

        components.append(component)

    return components


def count_component_vertices(component: set[int], faces: np.ndarray) -> int:
    """Count unique vertices in a face component."""
    vertices = set()
    for face_idx in component:
        face = faces[face_idx]
        vertices.add(face[0])
        vertices.add(face[1])
        vertices.add(face[2])
    return len(vertices)


def verify_structure_continuity(
    subject: str,
    atlas_id: str,
) -> dict:
    """Verify continuity for a specific structure."""
    subject_dir = BUILD_DIR / subject
    manifest = load_manifest(subject)
    all_verts, all_faces = read_mesh_binary(subject_dir)

    # Find all structures with this atlas_id
    structures = [s for s in manifest["structures"] if s["atlas_id"] == atlas_id]

    if not structures:
        return {
            "subject": subject,
            "atlas_id": atlas_id,
            "status": "NOT_FOUND",
            "error": f"No structures found with atlas_id={atlas_id}",
        }

    # Consolidate all faces and vertices from all structures with this atlas_id
    all_component_verts = []
    all_component_faces = []

    for struct in structures:
        verts, faces = extract_structure_mesh(all_verts, all_faces, struct)
        all_component_verts.append(verts)
        all_component_faces.append(faces)

    # Need to consolidate faces with remapped indices
    consolidated_verts = np.vstack(all_component_verts)

    # Remap faces
    consolidated_faces = []
    vert_offset = 0
    for faces in all_component_faces:
        consolidated_faces.append(faces + vert_offset)
        vert_offset += len(all_component_verts[len(consolidated_faces) - 1])

    consolidated_faces = np.vstack(consolidated_faces)

    total_verts = len(consolidated_verts)
    total_faces = len(consolidated_faces)

    # Build adjacency and find components
    adjacency = build_adjacency_graph(consolidated_faces)
    components = find_connected_components(total_faces, adjacency, consolidated_faces)

    # Sort components by size (vertices)
    component_sizes = []
    for component in components:
        vertex_count = count_component_vertices(component, consolidated_faces)
        component_sizes.append((vertex_count, len(component), component))

    component_sizes.sort(reverse=True)

    # Calculate metrics
    largest_component_verts = component_sizes[0][0] if component_sizes else 0
    main_frac = largest_component_verts / total_verts if total_verts > 0 else 0.0

    status = "CONNECTED" if main_frac >= 0.99 else "FRAGMENTED"

    return {
        "subject": subject,
        "atlas_id": atlas_id,
        "status": status,
        "total_vertices": total_verts,
        "total_faces": total_faces,
        "n_components": len(components),
        "largest_component_vertices": largest_component_verts,
        "main_frac": main_frac,
        "component_breakdown": [
            {
                "vertices": sz[0],
                "faces": sz[1],
            }
            for sz in component_sizes[:5]  # Top 5 components
        ],
    }


def cmd_verify(args: argparse.Namespace) -> int:
    """Verify continuity for all rib structures."""

    results = []

    for subject in ["ct_vhm", "ct_vhf"]:
        for atlas_id in ["ribs_l", "ribs_r"]:
            print(f"\nVerifying {subject} {atlas_id}...")
            result = verify_structure_continuity(subject, atlas_id)
            results.append(result)

            # Print summary
            print(f"  Status: {result.get('status', 'ERROR')}")
            if "total_vertices" in result:
                print(f"  Total vertices: {result['total_vertices']}")
                print(f"  Components: {result['n_components']}")
                print(f"  Main component: {result['largest_component_vertices']} vertices")
                print(f"  Main frac: {result['main_frac']:.4f}")

    # Summary table
    print("\n" + "="*70)
    print("CONTINUITY VERIFICATION SUMMARY")
    print("="*70)
    print(f"{'Subject':<12} {'Structure':<10} {'Status':<12} {'Main Frac':<10}")
    print("-"*70)

    for result in results:
        subject = result["subject"]
        atlas_id = result["atlas_id"]
        status = result.get("status", "ERROR")
        main_frac = result.get("main_frac", 0.0)
        print(f"{subject:<12} {atlas_id:<10} {status:<12} {main_frac:>8.4f}")

    print("="*70)

    # Check if all targets met
    all_connected = all(r.get("main_frac", 0.0) >= 0.99 for r in results)

    if all_connected:
        print("\nSUCCESS: All rib structures have main_frac >= 0.99")
        return 0
    else:
        print("\nWARNING: Some rib structures have main_frac < 0.99")
        print("May need to adjust articulation positioning or sizing.")
        return 1


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "command",
        choices=["verify"],
        help="Command to run",
    )

    args = parser.parse_args()

    if args.command == "verify":
        return cmd_verify(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
