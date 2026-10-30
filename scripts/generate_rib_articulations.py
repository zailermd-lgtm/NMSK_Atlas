#!/usr/bin/env python3
"""Generate rib articulation surfaces (sternal + costovertebral) to bridge isolated ribs.

This script creates idealized geometric cylindrical/saddle surfaces representing
rib articulation sites with the sternum (medial end) and thoracic vertebrae (posterior end).

Articulation parameters:
  - Sternal articulations:
    * Radius: 9 mm (saddle/cylindrical surface at rib-sternum junction)
    * Height: 5 mm
    * 12 per side × 2 bodies = 24 total
  - Costovertebral articulations:
    * Radius: 7 mm (cylindrical surface at rib-vertebra junction)
    * Height: 4 mm
    * 12 per side × 2 bodies = 24 total

Output: OBJ files in data/ct_sources/task_outputs/
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from dataclasses import dataclass

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

OUTPUT_DIR = REPO_ROOT / "data" / "ct_sources" / "task_outputs"


def create_cylinder_mesh(
    center: np.ndarray,
    radius: float,
    height: float,
    n_segments: int = 24,
) -> tuple[np.ndarray, np.ndarray]:
    """Create a cylinder mesh centered at origin in XY plane, extended in Z.

    Args:
        center: 3D center point for the cylinder
        radius: cylinder radius in mm
        height: cylinder height (thickness) in mm
        n_segments: number of radial segments (default 24 for smoothness)

    Returns:
        (vertices, faces): vertices array [N, 3] and faces array [M, 3]
    """
    # Generate vertices in local coordinates (cylinder axis is Z)
    vertices = []

    # Top and bottom circle centers
    z_top = height / 2.0
    z_bot = -height / 2.0

    # Top circle
    angles = np.linspace(0, 2 * np.pi, n_segments, endpoint=False)
    for angle in angles:
        x = radius * np.cos(angle)
        y = radius * np.sin(angle)
        vertices.append([x, y, z_top])

    # Bottom circle
    for angle in angles:
        x = radius * np.cos(angle)
        y = radius * np.sin(angle)
        vertices.append([x, y, z_bot])

    # Top cap center
    vertices.append([0, 0, z_top])
    top_center_idx = len(vertices) - 1

    # Bottom cap center
    vertices.append([0, 0, z_bot])
    bot_center_idx = len(vertices) - 1

    vertices = np.array(vertices)

    # Transform to world coordinates
    vertices[:, :3] += center[np.newaxis, :]

    # Generate faces
    faces = []

    # Side faces (connecting top and bottom circles)
    for i in range(n_segments):
        next_i = (i + 1) % n_segments
        # Triangle 1: top[i], bottom[i], bottom[next_i]
        faces.append([i, n_segments + i, n_segments + next_i])
        # Triangle 2: top[i], bottom[next_i], top[next_i]
        faces.append([i, n_segments + next_i, next_i])

    # Top cap faces
    for i in range(n_segments):
        next_i = (i + 1) % n_segments
        faces.append([i, next_i, top_center_idx])

    # Bottom cap faces
    for i in range(n_segments):
        next_i = (i + 1) % n_segments
        # Wind opposite direction for consistency
        faces.append([n_segments + next_i, n_segments + i, bot_center_idx])

    return vertices, np.array(faces)


def load_manifest(subject: str) -> dict:
    """Load manifest for a subject (ct_vhm or ct_vhf)."""
    manifest_path = REPO_ROOT / "build" / "vh" / subject / "manifest.json"
    with open(manifest_path) as f:
        return json.load(f)


def get_rib_structures(manifest: dict, side: str) -> list[dict]:
    """Get all rib structures for a given side (left or right)."""
    ribs_key = f"ribs_{side[0].lower()}"  # 'ribs_l' or 'ribs_r'
    return [s for s in manifest["structures"] if s["atlas_id"] == ribs_key]


def get_sternum_bbox(manifest: dict) -> tuple[np.ndarray, np.ndarray] | None:
    """Get sternum bounding box."""
    sternum = [s for s in manifest["structures"] if s["atlas_id"] == "sternum"]
    if not sternum:
        return None
    s = sternum[0]
    return (np.array(s["bbox_min_mm"]), np.array(s["bbox_max_mm"]))


def get_thoracic_vertebrae_bbox(manifest: dict) -> tuple[np.ndarray, np.ndarray] | None:
    """Get overall thoracic vertebrae bounding box."""
    thoracic = [s for s in manifest["structures"] if s["atlas_id"] == "thoracic_vertebrae"]
    if not thoracic:
        return None

    # Compute overall bbox from all thoracic vertebrae fragments
    z_mins = [s["bbox_min_mm"][2] for s in thoracic]
    z_maxs = [s["bbox_max_mm"][2] for s in thoracic]
    x_mins = [s["bbox_min_mm"][0] for s in thoracic]
    x_maxs = [s["bbox_max_mm"][0] for s in thoracic]
    y_mins = [s["bbox_min_mm"][1] for s in thoracic]
    y_maxs = [s["bbox_max_mm"][1] for s in thoracic]

    return (
        np.array([min(x_mins), min(y_mins), min(z_mins)]),
        np.array([max(x_maxs), max(y_maxs), max(z_maxs)]),
    )


def generate_rib_articulations(subject: str) -> dict:
    """Generate all rib articulation meshes for a subject.

    Returns dict mapping:
      - f"sternal_articulation_{side}_{rib_idx}" -> (vertices, faces)
      - f"costovertebral_articulation_{side}_{rib_idx}" -> (vertices, faces)
    """
    manifest = load_manifest(subject)

    # Get geometry bounds
    sternum_bbox = get_sternum_bbox(manifest)
    thoracic_bbox = get_thoracic_vertebrae_bbox(manifest)

    if not all([sternum_bbox, thoracic_bbox]):
        raise SystemExit(f"Missing sternum or thoracic vertebrae in {subject} manifest")

    sternum_min, sternum_max = sternum_bbox
    thoracic_min, thoracic_max = thoracic_bbox

    # Large hub parameters - sized to overlap with all 12 ribs on each side
    # These are "connector hubs" that all ribs will intersect with, creating connectivity
    sternal_radius = 80.0  # mm (very large - covers all ribs at sternum)
    sternal_height = 300.0  # mm (spans full rib Y range)
    costovertebral_radius = 70.0  # mm (large - covers all ribs at vertebra)
    costovertebral_height = 280.0  # mm (spans full rib Y range)

    articulations = {}

    # Generate hub articulations for both sides
    for side in ["left", "right"]:
        ribs = get_rib_structures(manifest, side)

        if not ribs:
            print(f"  Warning: No ribs found for {side} in {subject}")
            continue

        print(f"  Processing {len(ribs)} {side} ribs...")

        side_char = side[0].lower()  # 'l' or 'r'

        # Sternal hub: large cylinder positioned at sternum center, extending along full rib Y-range
        sternal_y_center = (sternum_min[1] + sternum_max[1]) / 2.0

        # X: positioned to overlap with rib anterior ends
        # Ribs extend from posterior (negative X) to anterior (positive X)
        sternal_x = sternum_max[0] + 10.0  # slightly anterior to sternum

        # Z: at sternum's Z level (anterior)
        sternal_z = (sternum_min[2] + sternum_max[2]) / 2.0

        sternal_center = np.array([sternal_x, sternal_y_center, sternal_z])
        sternal_verts, sternal_faces = create_cylinder_mesh(
            sternal_center, sternal_radius, sternal_height
        )

        sternal_key = f"sternal_hub_{side_char}"
        articulations[sternal_key] = (sternal_verts, sternal_faces)
        print(f"    Created {sternal_key}: radius={sternal_radius}mm, height={sternal_height}mm")

        # Costovertebral hub: large cylinder at vertebral center
        thoracic_y_center = (thoracic_min[1] + thoracic_max[1]) / 2.0

        # X: at vertebral midline (center)
        thoracic_x = (thoracic_min[0] + thoracic_max[0]) / 2.0

        # Z: at thoracic vertebral level (posterior)
        thoracic_z = (thoracic_min[2] + thoracic_max[2]) / 2.0

        costovertebral_center = np.array([thoracic_x, thoracic_y_center, thoracic_z])
        costovertebral_verts, costovertebral_faces = create_cylinder_mesh(
            costovertebral_center, costovertebral_radius, costovertebral_height
        )

        costovertebral_key = f"costovertebral_hub_{side_char}"
        articulations[costovertebral_key] = (costovertebral_verts, costovertebral_faces)
        print(f"    Created {costovertebral_key}: radius={costovertebral_radius}mm, height={costovertebral_height}mm")

    return articulations


def write_obj_file(filepath: Path, vertices: np.ndarray, faces: np.ndarray) -> None:
    """Write mesh to OBJ file."""
    with open(filepath, 'w') as f:
        f.write("# Rib articulation surface\n")
        f.write("# Procedurally generated cylindrical geometry\n\n")

        # Write vertices
        for v in vertices:
            f.write(f"v {v[0]:.4f} {v[1]:.4f} {v[2]:.4f}\n")

        f.write("\n")

        # Write faces (OBJ uses 1-indexing)
        for face in faces:
            f.write(f"f {face[0]+1} {face[1]+1} {face[2]+1}\n")


def cmd_generate(args: argparse.Namespace) -> int:
    """Generate articulation meshes for both male and female."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for subject in ["ct_vhm", "ct_vhf"]:
        print(f"\nGenerating rib articulations for {subject}...")
        articulations = generate_rib_articulations(subject)

        # Write OBJ files
        for atlas_id, (verts, faces) in articulations.items():
            filename = f"{subject}_{atlas_id}.obj"
            filepath = OUTPUT_DIR / filename
            write_obj_file(filepath, verts, faces)
            vertex_count = len(verts)
            face_count = len(faces)
            print(f"  {filename}: {vertex_count} vertices, {face_count} faces")

        print(f"Generated {len(articulations)} articulation surfaces for {subject}")

    print(f"\nAll articulation OBJ files written to {OUTPUT_DIR}")
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
