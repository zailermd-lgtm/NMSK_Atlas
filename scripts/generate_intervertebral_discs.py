#!/usr/bin/env python3
"""Generate cylindrical intervertebral disc meshes to bridge vertebral fragmentation.

This script creates idealized geometric cylinder meshes representing
intervertebral discs between adjacent vertebrae. The discs are positioned
at the midpoint between vertebra bounding box Z-extents.

Disc parameters (anatomically reasonable):
  - Radius: 10-12 mm (typical IVD outer diameter ~20-24 mm)
  - Thickness: 7-8 mm (typical IVD height)

Vertebral levels:
  - Cervical: C1-C2 through C6-C7 (6 discs)
  - Thoracic: T1-T2 through T11-T12 (11 discs)
  - Lumbar: L1-L2 through L4-L5 (4 discs)
  Total: 21 discs per body

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


@dataclass
class VertebralLevel:
    """Definition of a vertebral level."""
    name: str
    atlas_id: str
    region: str  # 'cervical', 'thoracic', or 'lumbar'


# Vertebral level definitions
CERVICAL_LEVELS = [
    VertebralLevel("C1-C2", "intervertebral_disc_c1_c2", "cervical"),
    VertebralLevel("C2-C3", "intervertebral_disc_c2_c3", "cervical"),
    VertebralLevel("C3-C4", "intervertebral_disc_c3_c4", "cervical"),
    VertebralLevel("C4-C5", "intervertebral_disc_c4_c5", "cervical"),
    VertebralLevel("C5-C6", "intervertebral_disc_c5_c6", "cervical"),
    VertebralLevel("C6-C7", "intervertebral_disc_c6_c7", "cervical"),
]

THORACIC_LEVELS = [
    VertebralLevel("T1-T2", "intervertebral_disc_t1_t2", "thoracic"),
    VertebralLevel("T2-T3", "intervertebral_disc_t2_t3", "thoracic"),
    VertebralLevel("T3-T4", "intervertebral_disc_t3_t4", "thoracic"),
    VertebralLevel("T4-T5", "intervertebral_disc_t4_t5", "thoracic"),
    VertebralLevel("T5-T6", "intervertebral_disc_t5_t6", "thoracic"),
    VertebralLevel("T6-T7", "intervertebral_disc_t6_t7", "thoracic"),
    VertebralLevel("T7-T8", "intervertebral_disc_t7_t8", "thoracic"),
    VertebralLevel("T8-T9", "intervertebral_disc_t8_t9", "thoracic"),
    VertebralLevel("T9-T10", "intervertebral_disc_t9_t10", "thoracic"),
    VertebralLevel("T10-T11", "intervertebral_disc_t10_t11", "thoracic"),
    VertebralLevel("T11-T12", "intervertebral_disc_t11_t12", "thoracic"),
]

LUMBAR_LEVELS = [
    VertebralLevel("L1-L2", "intervertebral_disc_l1_l2", "lumbar"),
    VertebralLevel("L2-L3", "intervertebral_disc_l2_l3", "lumbar"),
    VertebralLevel("L3-L4", "intervertebral_disc_l3_l4", "lumbar"),
    VertebralLevel("L4-L5", "intervertebral_disc_l4_l5", "lumbar"),
]

ALL_LEVELS = CERVICAL_LEVELS + THORACIC_LEVELS + LUMBAR_LEVELS


def create_cylinder_mesh(
    center: np.ndarray,
    radius: float,
    height: float,
    n_segments: int = 32,
) -> tuple[np.ndarray, np.ndarray]:
    """Create a cylinder mesh centered at origin in XY plane, extended in Z.

    Args:
        center: 3D center point for the cylinder
        radius: cylinder radius in mm
        height: cylinder height (thickness) in mm
        n_segments: number of radial segments (default 32 for smoothness)

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


def get_vertebra_bbox(manifest: dict, atlas_id: str) -> tuple[np.ndarray, np.ndarray] | None:
    """Get bounding box for a vertebra group from manifest."""
    for struct in manifest["structures"]:
        if struct["atlas_id"] == atlas_id:
            bbox_min = np.array(struct["bbox_min_mm"])
            bbox_max = np.array(struct["bbox_max_mm"])
            return bbox_min, bbox_max
    return None


def generate_disc_meshes(subject: str) -> dict:
    """Generate all intervertebral disc meshes for a subject.

    Returns dict mapping level.atlas_id -> (vertices, faces)
    """
    manifest = load_manifest(subject)

    # Get bounding boxes for vertebra regions
    cervical_bbox = get_vertebra_bbox(manifest, "cervical_vertebrae")
    thoracic_bbox = get_vertebra_bbox(manifest, "thoracic_vertebrae")
    lumbar_bbox = get_vertebra_bbox(manifest, "lumbar_vertebrae")

    if not all([cervical_bbox, thoracic_bbox, lumbar_bbox]):
        raise SystemExit(f"Missing vertebra regions in {subject} manifest")

    # Disc parameters (anatomically reasonable)
    disc_radius = 11.0  # mm (10-12 mm typical)
    disc_thickness = 7.5  # mm (7-8 mm typical)

    discs = {}

    # For each level, compute disc position at midpoint between adjacent vertebra Z-extents
    # We'll estimate disc positions assuming relatively uniform spacing within each region

    for level in CERVICAL_LEVELS:
        if level.region == "cervical":
            bbox_min, bbox_max = cervical_bbox
            # Extract the level index from the name (C1-C2 -> 1, C2-C3 -> 2, etc.)
            parts = level.name.split('-')
            lower_idx = int(parts[0][1:])  # Get number from C1, C2, etc.
            upper_idx = lower_idx + 1

            # Estimate disc Z position as a fraction through the cervical region
            # 6 discs over the cervical range
            frac_start = (lower_idx - 1) / 6.0
            frac_end = lower_idx / 6.0
            frac_mid = (frac_start + frac_end) / 2.0

            z_disc = bbox_min[2] + frac_mid * (bbox_max[2] - bbox_min[2])
            x_center = (bbox_min[0] + bbox_max[0]) / 2.0
            y_center = (bbox_min[1] + bbox_max[1]) / 2.0

            center = np.array([x_center, y_center, z_disc])
            verts, faces = create_cylinder_mesh(center, disc_radius, disc_thickness)
            discs[level.atlas_id] = (verts, faces)

    for level in THORACIC_LEVELS:
        if level.region == "thoracic":
            bbox_min, bbox_max = thoracic_bbox
            # Extract the level index from the name (T1-T2 -> 1, etc.)
            parts = level.name.split('-')
            lower_idx = int(parts[0][1:])

            # 11 discs over the thoracic range
            frac_start = (lower_idx - 1) / 11.0
            frac_end = lower_idx / 11.0
            frac_mid = (frac_start + frac_end) / 2.0

            z_disc = bbox_min[2] + frac_mid * (bbox_max[2] - bbox_min[2])
            x_center = (bbox_min[0] + bbox_max[0]) / 2.0
            y_center = (bbox_min[1] + bbox_max[1]) / 2.0

            center = np.array([x_center, y_center, z_disc])
            verts, faces = create_cylinder_mesh(center, disc_radius, disc_thickness)
            discs[level.atlas_id] = (verts, faces)

    for level in LUMBAR_LEVELS:
        if level.region == "lumbar":
            bbox_min, bbox_max = lumbar_bbox
            # Extract the level index from the name (L1-L2 -> 1, etc.)
            parts = level.name.split('-')
            lower_idx = int(parts[0][1:])

            # 4 discs over the lumbar range
            frac_start = (lower_idx - 1) / 4.0
            frac_end = lower_idx / 4.0
            frac_mid = (frac_start + frac_end) / 2.0

            z_disc = bbox_min[2] + frac_mid * (bbox_max[2] - bbox_min[2])
            x_center = (bbox_min[0] + bbox_max[0]) / 2.0
            y_center = (bbox_min[1] + bbox_max[1]) / 2.0

            center = np.array([x_center, y_center, z_disc])
            verts, faces = create_cylinder_mesh(center, disc_radius, disc_thickness)
            discs[level.atlas_id] = (verts, faces)

    return discs


def write_obj_file(filepath: Path, vertices: np.ndarray, faces: np.ndarray) -> None:
    """Write mesh to OBJ file."""
    with open(filepath, 'w') as f:
        f.write("# Intervertebral disc\n")
        f.write("# Procedurally generated cylindrical geometry\n\n")

        # Write vertices
        for v in vertices:
            f.write(f"v {v[0]:.4f} {v[1]:.4f} {v[2]:.4f}\n")

        f.write("\n")

        # Write faces (OBJ uses 1-indexing)
        for face in faces:
            f.write(f"f {face[0]+1} {face[1]+1} {face[2]+1}\n")


def cmd_generate(args: argparse.Namespace) -> int:
    """Generate disc meshes for both male and female."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for subject in ["ct_vhm", "ct_vhf"]:
        print(f"\nGenerating discs for {subject}...")
        discs = generate_disc_meshes(subject)

        # Write OBJ files
        for atlas_id, (verts, faces) in discs.items():
            filename = f"{subject}_{atlas_id}.obj"
            filepath = OUTPUT_DIR / filename
            write_obj_file(filepath, verts, faces)
            vertex_count = len(verts)
            face_count = len(faces)
            print(f"  {filename}: {vertex_count} vertices, {face_count} faces")

        print(f"Generated {len(discs)} discs for {subject}")

    print(f"\nAll disc OBJ files written to {OUTPUT_DIR}")
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
