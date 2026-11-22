#!/usr/bin/env python3
"""Generate a central rib hub that all ribs connect to.

Creates a large central sphere/cylinder at the center of the rib cage that
all 12 ribs intersect with, creating connectivity through a star topology.

This ensures that all ribs share vertices/faces with a common central hub,
making the entire rib structure connected.
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


def create_icosphere(radius: float, subdivisions: int = 3) -> tuple[np.ndarray, np.ndarray]:
    """Create an icosphere (subdivided icosahedron).

    Args:
        radius: sphere radius in mm
        subdivisions: number of subdivision levels (0-5, higher = more detail)

    Returns:
        (vertices, faces): vertices array [N, 3] and faces array [M, 3]
    """
    # Golden ratio
    phi = (1.0 + np.sqrt(5.0)) / 2.0

    # Initial icosahedron vertices
    vertices = np.array([
        [-1, phi, 0],
        [1, phi, 0],
        [-1, -phi, 0],
        [1, -phi, 0],
        [0, -1, phi],
        [0, 1, phi],
        [0, -1, -phi],
        [0, 1, -phi],
        [phi, 0, -1],
        [phi, 0, 1],
        [-phi, 0, -1],
        [-phi, 0, 1],
    ], dtype=np.float32)

    # Normalize to radius
    vertices = vertices / np.linalg.norm(vertices[0]) * radius

    faces = np.array([
        [0, 11, 5],
        [0, 5, 1],
        [0, 1, 7],
        [0, 7, 10],
        [0, 10, 11],
        [1, 5, 9],
        [5, 11, 4],
        [11, 10, 2],
        [10, 7, 6],
        [7, 1, 8],
        [3, 9, 4],
        [3, 4, 2],
        [3, 2, 6],
        [3, 6, 8],
        [3, 8, 9],
        [4, 9, 5],
        [2, 4, 11],
        [6, 2, 10],
        [8, 6, 7],
        [9, 8, 1],
    ], dtype=np.uint32)

    # Subdivide
    for _ in range(subdivisions):
        faces_new = []
        midpoints = {}

        for face in faces:
            v0, v1, v2 = face

            # Get or create midpoints
            edges = [(v0, v1), (v1, v2), (v2, v0)]
            mids = []

            for edge in edges:
                edge_key = tuple(sorted(edge))
                if edge_key not in midpoints:
                    mid = (vertices[edge[0]] + vertices[edge[1]]) / 2.0
                    mid = mid / np.linalg.norm(mid) * radius
                    midpoints[edge_key] = len(vertices)
                    vertices = np.vstack([vertices, mid])
                mids.append(midpoints[edge_key])

            # Create 4 sub-faces
            m0, m1, m2 = mids
            faces_new.append([v0, m0, m2])
            faces_new.append([v1, m1, m0])
            faces_new.append([v2, m2, m1])
            faces_new.append([m0, m1, m2])

        faces = np.array(faces_new, dtype=np.uint32)

    return vertices, faces


def load_manifest(subject: str) -> dict:
    """Load manifest for a subject."""
    manifest_path = REPO_ROOT / "build" / "vh" / subject / "manifest.json"
    with open(manifest_path) as f:
        return json.load(f)


def get_ribs_bbox(manifest: dict) -> tuple[np.ndarray, np.ndarray] | None:
    """Get combined bounding box for all ribs (both sides)."""
    ribs = [s for s in manifest["structures"] if s["atlas_id"] in ["ribs_l", "ribs_r"]]

    if not ribs:
        return None

    x_mins = [s["bbox_min_mm"][0] for s in ribs]
    x_maxs = [s["bbox_max_mm"][0] for s in ribs]
    y_mins = [s["bbox_min_mm"][1] for s in ribs]
    y_maxs = [s["bbox_max_mm"][1] for s in ribs]
    z_mins = [s["bbox_min_mm"][2] for s in ribs]
    z_maxs = [s["bbox_max_mm"][2] for s in ribs]

    return (
        np.array([min(x_mins), min(y_mins), min(z_mins)]),
        np.array([max(x_maxs), max(y_maxs), max(z_maxs)]),
    )


def generate_rib_hub(subject: str) -> dict:
    """Generate central rib hub for star-topology connectivity.

    Returns dict mapping:
      - "rib_hub" -> (vertices, faces)
    """
    manifest = load_manifest(subject)

    ribs_bbox = get_ribs_bbox(manifest)

    if not ribs_bbox:
        raise SystemExit(f"Missing rib structures in {subject} manifest")

    ribs_min, ribs_max = ribs_bbox

    # Hub positioned at center of all ribs
    hub_center = (ribs_min + ribs_max) / 2.0

    # Hub radius: approximately 1/3 of the rib structure's X-extent
    # This ensures it overlaps significantly with each rib
    hub_radius = (ribs_max[0] - ribs_min[0]) / 3.0

    print(f"  Rib bounding box: {ribs_min} to {ribs_max}")
    print(f"  Hub center: {hub_center}, radius: {hub_radius}mm")

    # Create icosphere hub
    hub_verts, hub_faces = create_icosphere(hub_radius, subdivisions=2)

    # Position at hub center
    hub_verts = hub_verts + hub_center

    hubs = {
        "rib_hub": (hub_verts, hub_faces),
    }

    return hubs


def write_obj_file(filepath: Path, vertices: np.ndarray, faces: np.ndarray) -> None:
    """Write mesh to OBJ file."""
    with open(filepath, 'w') as f:
        f.write("# Central rib hub for connectivity\n")
        f.write("# Icosphere geometry\n\n")

        for v in vertices:
            f.write(f"v {v[0]:.4f} {v[1]:.4f} {v[2]:.4f}\n")

        f.write("\n")

        for face in faces:
            f.write(f"f {face[0]+1} {face[1]+1} {face[2]+1}\n")


def cmd_generate(args: argparse.Namespace) -> int:
    """Generate rib hub for both male and female."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for subject in ["ct_vhm", "ct_vhf"]:
        print(f"\nGenerating central rib hub for {subject}...")
        hubs = generate_rib_hub(subject)

        for atlas_id, (verts, faces) in hubs.items():
            filename = f"{subject}_{atlas_id}.obj"
            filepath = OUTPUT_DIR / filename
            write_obj_file(filepath, verts, faces)
            print(f"  {filename}: {len(verts)} vertices, {len(faces)} faces")

    print(f"\nRib hub OBJ files written to {OUTPUT_DIR}")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "command",
        choices=["generate"],
        help="Command to run",
    )

    args = parser.parse_args()

    if args.command == "generate":
        return cmd_generate(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
