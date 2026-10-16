#!/usr/bin/env python3
"""Generate rib-to-rib bridging cylinders to create connectivity within rib structures.

This script creates small cylindrical bridges connecting adjacent ribs together,
creating a chain of connectivity that makes the 12 ribs form a single connected component.

Bridging parameters:
  - One bridge per adjacent rib pair (11 bridges per side)
  - Small radius (3-4 mm) to minimize intersection with existing geometry
  - Positioned mid-way between rib Y-centers

Output: OBJ files in data/ct_sources/task_outputs/
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


def create_cylinder_mesh(
    center: np.ndarray,
    radius: float,
    height: float,
    n_segments: int = 16,
) -> tuple[np.ndarray, np.ndarray]:
    """Create a cylinder mesh."""
    vertices = []

    z_top = height / 2.0
    z_bot = -height / 2.0

    angles = np.linspace(0, 2 * np.pi, n_segments, endpoint=False)
    for angle in angles:
        x = radius * np.cos(angle)
        y = radius * np.sin(angle)
        vertices.append([x, y, z_top])

    for angle in angles:
        x = radius * np.cos(angle)
        y = radius * np.sin(angle)
        vertices.append([x, y, z_bot])

    vertices.append([0, 0, z_top])
    top_center_idx = len(vertices) - 1

    vertices.append([0, 0, z_bot])
    bot_center_idx = len(vertices) - 1

    vertices = np.array(vertices)
    vertices[:, :3] += center[np.newaxis, :]

    faces = []

    for i in range(n_segments):
        next_i = (i + 1) % n_segments
        faces.append([i, n_segments + i, n_segments + next_i])
        faces.append([i, n_segments + next_i, next_i])

    for i in range(n_segments):
        next_i = (i + 1) % n_segments
        faces.append([i, next_i, top_center_idx])

    for i in range(n_segments):
        next_i = (i + 1) % n_segments
        faces.append([n_segments + next_i, n_segments + i, bot_center_idx])

    return vertices, np.array(faces)


def load_manifest(subject: str) -> dict:
    """Load manifest for a subject."""
    manifest_path = REPO_ROOT / "build" / "vh" / subject / "manifest.json"
    with open(manifest_path) as f:
        return json.load(f)


def get_rib_structures(manifest: dict, side: str) -> list[dict]:
    """Get all rib structures for a given side."""
    ribs_key = f"ribs_{side[0].lower()}"
    return [s for s in manifest["structures"] if s["atlas_id"] == ribs_key]


def generate_rib_bridges(subject: str) -> dict:
    """Generate rib-to-rib bridging cylinders.

    Returns dict mapping:
      - f"rib_bridge_{side}_{i}_to_{i+1}" -> (vertices, faces)
    """
    manifest = load_manifest(subject)

    bridges = {}

    # Bridge parameters - small connectors between adjacent ribs
    bridge_radius = 4.0  # mm (small to avoid intersection with rib geometry)
    bridge_height = 80.0  # mm (tall to span across the rib structure)

    for side in ["left", "right"]:
        ribs = get_rib_structures(manifest, side)

        if not ribs:
            print(f"  Warning: No ribs found for {side} in {subject}")
            continue

        print(f"  Processing {len(ribs)} {side} ribs...")

        # Sort ribs by Y position (superior to inferior)
        ribs_sorted = sorted(
            ribs,
            key=lambda r: (r["bbox_max_mm"][1] + r["bbox_min_mm"][1]) / 2.0,
            reverse=True,
        )

        # Create bridges between adjacent ribs
        for i in range(len(ribs_sorted) - 1):
            rib1 = ribs_sorted[i]
            rib2 = ribs_sorted[i + 1]

            # Get rib centers
            rib1_center_y = (rib1["bbox_max_mm"][1] + rib1["bbox_min_mm"][1]) / 2.0
            rib2_center_y = (rib2["bbox_max_mm"][1] + rib2["bbox_min_mm"][1]) / 2.0

            # Bridge positioned mid-way between ribs
            bridge_y = (rib1_center_y + rib2_center_y) / 2.0

            # Bridge X position: at approximate rib center in X (mid-shaft)
            rib1_center_x = (rib1["bbox_max_mm"][0] + rib1["bbox_min_mm"][0]) / 2.0
            bridge_x = rib1_center_x

            # Bridge Z position: at approximate rib center in Z
            rib1_center_z = (rib1["bbox_max_mm"][2] + rib1["bbox_min_mm"][2]) / 2.0
            bridge_z = rib1_center_z

            bridge_center = np.array([bridge_x, bridge_y, bridge_z])
            bridge_verts, bridge_faces = create_cylinder_mesh(
                bridge_center, bridge_radius, bridge_height
            )

            side_char = side[0].lower()
            bridge_key = f"rib_bridge_{side_char}{i+1:02d}_to_{i+2:02d}"
            bridges[bridge_key] = (bridge_verts, bridge_faces)

    return bridges


def write_obj_file(filepath: Path, vertices: np.ndarray, faces: np.ndarray) -> None:
    """Write mesh to OBJ file."""
    with open(filepath, 'w') as f:
        f.write("# Rib-to-rib bridge\n")
        f.write("# Procedurally generated cylindrical connector\n\n")

        for v in vertices:
            f.write(f"v {v[0]:.4f} {v[1]:.4f} {v[2]:.4f}\n")

        f.write("\n")

        for face in faces:
            f.write(f"f {face[0]+1} {face[1]+1} {face[2]+1}\n")


def cmd_generate(args: argparse.Namespace) -> int:
    """Generate rib bridges for both male and female."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for subject in ["ct_vhm", "ct_vhf"]:
        print(f"\nGenerating rib bridges for {subject}...")
        bridges = generate_rib_bridges(subject)

        for atlas_id, (verts, faces) in bridges.items():
            filename = f"{subject}_{atlas_id}.obj"
            filepath = OUTPUT_DIR / filename
            write_obj_file(filepath, verts, faces)
            print(f"  {filename}: {len(verts)} vertices, {len(faces)} faces")

        print(f"Generated {len(bridges)} rib bridges for {subject}")

    print(f"\nAll rib bridge OBJ files written to {OUTPUT_DIR}")
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
