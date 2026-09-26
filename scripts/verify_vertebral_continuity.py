#!/usr/bin/env python3
"""Verify vertebral column continuity using vertex-based metrics (matching Q103).

Uses face-adjacency connected components, but measures continuity via
VERTICES like Q103 does (main_frac = largest_component_vertices / total_vertices).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from collections import defaultdict

import numpy as np
from scipy import sparse
from scipy.sparse.csgraph import connected_components

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

BUILD_DIR = REPO_ROOT / "build" / "vh"


def read_mesh_binary(subject_dir: Path) -> tuple[np.ndarray, np.ndarray]:
    """Read mesh from binary files."""
    verts_file = subject_dir / "vertices.f32"
    faces_file = subject_dir / "faces.u32"

    verts = np.fromfile(verts_file, dtype=np.float32).reshape(-1, 3)
    faces = np.fromfile(faces_file, dtype=np.uint32).reshape(-1, 3)

    return verts, faces


def load_manifest(subject: str) -> dict:
    """Load manifest for a subject."""
    manifest_path = BUILD_DIR / subject / "manifest.json"
    with open(manifest_path) as f:
        return json.load(f)


def build_face_adjacency_graph(
    faces: np.ndarray,
    include_structures: list[str],
    manifest: dict,
) -> tuple[sparse.csr_matrix, np.ndarray, dict]:
    """Build face adjacency graph for selected structures.

    Returns:
        (adjacency_matrix, selected_face_indices, face_to_struct_dict)
    """
    # Get face ranges for selected structures.
    # BUG FIX (Q111, was open since Q104/Q107/Q110 documented it): several
    # manifest structures can share one atlas_id -- e.g. lumbar_vertebrae has
    # 5 (L1-L5), cervical_vertebrae 7, thoracic_vertebrae 12 -- so keying this
    # dict by atlas_id and assigning with `=` silently overwrote every
    # fragment but the last one seen. That meant this function only ever
    # scored ONE vertebra piece per region against its discs; see Q110's
    # PROJECT_STATE.md entry for the full trace and re-measured numbers.
    face_ranges: dict[str, list[tuple[int, int]]] = defaultdict(list)
    for struct in manifest["structures"]:
        if struct["atlas_id"] in include_structures:
            face_ranges[struct["atlas_id"]].append((
                struct["face_offset"],
                struct["face_offset"] + struct["triangle_count"],
            ))

    # Collect faces to include
    selected_faces = []
    face_to_struct = {}

    for atlas_id, ranges in sorted(face_ranges.items()):
        for start, end in ranges:
            for i in range(start, end):
                selected_faces.append(i)
                face_to_struct[i] = atlas_id

    if not selected_faces:
        raise ValueError(f"No faces found for structures: {include_structures}")

    selected_faces = np.array(selected_faces)
    n_faces = len(selected_faces)

    # Build edge adjacency: which faces share an edge
    edge_to_faces: dict[tuple, list[int]] = {}

    for local_idx, face_idx in enumerate(selected_faces):
        face = faces[face_idx]
        v0, v1, v2 = face

        # Create edges as sorted tuples
        edges = [
            tuple(sorted([v0, v1])),
            tuple(sorted([v1, v2])),
            tuple(sorted([v2, v0])),
        ]

        for edge in edges:
            if edge not in edge_to_faces:
                edge_to_faces[edge] = []
            edge_to_faces[edge].append(local_idx)

    # Build sparse adjacency matrix
    row = []
    col = []

    for face_list in edge_to_faces.values():
        # All pairs of faces sharing this edge are adjacent
        for i in range(len(face_list)):
            for j in range(i + 1, len(face_list)):
                row.extend([face_list[i], face_list[j]])
                col.extend([face_list[j], face_list[i]])

    # Create symmetric sparse matrix
    adj = sparse.csr_matrix(
        (np.ones(len(row), dtype=bool), (row, col)),
        shape=(n_faces, n_faces),
    )

    return adj, selected_faces, face_to_struct


def analyze_continuity(subject: str, faces: np.ndarray, manifest: dict) -> dict:
    """Analyze continuity for all vertebral regions using VERTEX metrics."""
    results = {
        "subject": subject,
        "audit_timestamp": "2026-09-20",
        "source": "Q104: Intervertebral Disc Integration Task",
        "methodology": "Face-adjacency connected components with vertex-based main_frac metric (matching Q103 methodology)",
        "regions": {},
    }

    for region_name, atlas_ids in [
        ("cervical", ["cervical_vertebrae"] + [f"intervertebral_disc_c{i}_c{i+1}" for i in range(1, 7)]),
        ("thoracic", ["thoracic_vertebrae"] + [f"intervertebral_disc_t{i}_t{i+1}" for i in range(1, 12)]),
        ("lumbar", ["lumbar_vertebrae"] + [f"intervertebral_disc_l{i}_l{i+1}" for i in range(1, 5)]),
    ]:
        # Filter atlas_ids that actually exist
        available_ids = [aid for aid in atlas_ids if any(s["atlas_id"] == aid for s in manifest["structures"])]

        if not available_ids:
            print(f"  {region_name}: SKIPPED (no structures found)")
            results["regions"][region_name] = {"status": "SKIPPED", "reason": "no structures"}
            continue

        try:
            adj, selected_faces, face_to_struct = build_face_adjacency_graph(
                faces, available_ids, manifest
            )

            # Run connected components
            n_components, labels = connected_components(adj, directed=False)

            # Compute main_frac using VERTICES (matching Q103 methodology)
            # Each face has 3 vertices; map faces to their vertices and components
            component_vertices = defaultdict(set)
            for face_idx, component_id in enumerate(labels):
                face_global_idx = selected_faces[face_idx]
                face = faces[face_global_idx]
                for v in face:
                    component_vertices[component_id].add(int(v))

            # Compute component sizes in vertices
            vertex_component_sizes = {k: len(v) for k, v in component_vertices.items()}
            largest_vertex_count = max(vertex_component_sizes.values())
            total_vertices = sum(len(v) for v in component_vertices.values())
            main_frac = largest_vertex_count / total_vertices if total_vertices > 0 else 0.0

            # Determine status
            if main_frac >= 0.99:
                status = "CONTINUOUS"
            elif main_frac >= 0.5:
                status = "FRAGMENTED"
            else:
                status = "SEVERE_BREAK"

            results["regions"][region_name] = {
                "status": status,
                "main_frac": float(main_frac),
                "n_components": int(n_components),
                "total_vertices": int(total_vertices),
                "largest_component_vertices": int(largest_vertex_count),
                "included_structures": available_ids,
            }

            print(f"  {region_name:10s} {status:15s} main_frac={main_frac:.3f} components={n_components:2d}")

        except Exception as e:
            print(f"  {region_name}: ERROR - {e}")
            results["regions"][region_name] = {"status": "ERROR", "error": str(e)}

    return results


def cmd_analyze(args: argparse.Namespace) -> int:
    """Run continuity analysis."""
    print("Vertebral column continuity analysis with intervertebral discs (VERTEX-based):\n")

    for subject in ["ct_vhm", "ct_vhf"]:
        print(f"{subject}:")
        subject_dir = BUILD_DIR / subject
        verts, faces = read_mesh_binary(subject_dir)
        manifest = load_manifest(subject)

        results = analyze_continuity(subject, faces, manifest)

        # Save results
        output_file = REPO_ROOT / "data" / "derived" / f"Q104_continuity_{subject}.json"
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"  Results saved to {output_file.name}\n")

    return 0


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "command",
        choices=["analyze"],
        help="Command to run",
    )

    args = parser.parse_args()

    if args.command == "analyze":
        return cmd_analyze(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
