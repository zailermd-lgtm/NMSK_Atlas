#!/usr/bin/env python3
"""Generate region-optimized intervertebral discs with larger lumbar discs.

This script regenerates discs with optimized parameters per region:
- Cervical & Thoracic: radius 40mm, thickness 20mm (working well)
- Lumbar: radius 50mm, thickness 24mm (larger to span fragmented topology)
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
    name: str
    atlas_id: str
    region: str


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


def compute_region_bbox(manifest: dict, atlas_id: str) -> tuple[np.ndarray, np.ndarray] | None:
    """Compute bounding box encompassing all fragments of a vertebra region."""
    frags = [s for s in manifest["structures"] if s["atlas_id"] == atlas_id]

    if not frags:
        return None

    z_mins = [f["bbox_min_mm"][2] for f in frags]
    z_maxs = [f["bbox_max_mm"][2] for f in frags]
    x_mins = [f["bbox_min_mm"][0] for f in frags]
    x_maxs = [f["bbox_max_mm"][0] for f in frags]
    y_mins = [f["bbox_min_mm"][1] for f in frags]
    y_maxs = [f["bbox_max_mm"][1] for f in frags]

    return (
        np.array([min(x_mins), min(y_mins), min(z_mins)]),
        np.array([max(x_maxs), max(y_maxs), max(z_maxs)]),
    )


def generate_disc_meshes(subject: str) -> dict:
    """Generate all intervertebral disc meshes with region-optimized parameters."""
    manifest = load_manifest(subject)

    cervical_bbox = compute_region_bbox(manifest, "cervical_vertebrae")
    thoracic_bbox = compute_region_bbox(manifest, "thoracic_vertebrae")
    lumbar_bbox = compute_region_bbox(manifest, "lumbar_vertebrae")

    if not all([cervical_bbox, thoracic_bbox, lumbar_bbox]):
        raise SystemExit(f"Missing vertebra regions in {subject} manifest")

    discs = {}

    # CERVICAL: Original size (radius 40mm, thickness 20mm) - working well
    for level in CERVICAL_LEVELS:
        bbox_min, bbox_max = cervical_bbox
        parts = level.name.split('-')
        lower_idx = int(parts[0][1:])
        frac = (lower_idx - 0.5) / 6.0
        z_disc = bbox_min[2] + frac * (bbox_max[2] - bbox_min[2])
        x_center = (bbox_min[0] + bbox_max[0]) / 2.0
        y_center = (bbox_min[1] + bbox_max[1]) / 2.0
        center = np.array([x_center, y_center, z_disc])
        verts, faces = create_cylinder_mesh(center, radius=40.0, height=20.0)
        discs[level.atlas_id] = (verts, faces)

    # THORACIC: Original size (radius 40mm, thickness 20mm) - working well
    for level in THORACIC_LEVELS:
        bbox_min, bbox_max = thoracic_bbox
        parts = level.name.split('-')
        lower_idx = int(parts[0][1:])
        frac = (lower_idx - 0.5) / 11.0
        z_disc = bbox_min[2] + frac * (bbox_max[2] - bbox_min[2])
        x_center = (bbox_min[0] + bbox_max[0]) / 2.0
        y_center = (bbox_min[1] + bbox_max[1]) / 2.0
        center = np.array([x_center, y_center, z_disc])
        verts, faces = create_cylinder_mesh(center, radius=40.0, height=20.0)
        discs[level.atlas_id] = (verts, faces)

    # LUMBAR: OPTIMIZED LARGER SIZE (radius 50mm, thickness 24mm)
    # to bridge the highly fragmented lumbar topology
    for level in LUMBAR_LEVELS:
        bbox_min, bbox_max = lumbar_bbox
        parts = level.name.split('-')
        lower_idx = int(parts[0][1:])
        frac = (lower_idx - 0.5) / 4.0
        z_disc = bbox_min[2] + frac * (bbox_max[2] - bbox_min[2])
        x_center = (bbox_min[0] + bbox_max[0]) / 2.0
        y_center = (bbox_min[1] + bbox_max[1]) / 2.0
        center = np.array([x_center, y_center, z_disc])
        # OPTIMIZED FOR LUMBAR: 50mm radius, 24mm thickness
        verts, faces = create_cylinder_mesh(center, radius=50.0, height=24.0)
        discs[level.atlas_id] = (verts, faces)

    return discs


def write_obj_file(filepath: Path, vertices: np.ndarray, faces: np.ndarray) -> None:
    """Write mesh to OBJ file."""
    with open(filepath, 'w') as f:
        f.write("# Intervertebral disc\n")
        f.write("# Procedurally generated cylindrical geometry\n\n")

        for v in vertices:
            f.write(f"v {v[0]:.4f} {v[1]:.4f} {v[2]:.4f}\n")

        f.write("\n")

        for face in faces:
            f.write(f"f {face[0]+1} {face[1]+1} {face[2]+1}\n")


def cmd_generate(args: argparse.Namespace) -> int:
    """Generate optimized disc meshes for both male and female."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    for subject in ["ct_vhm", "ct_vhf"]:
        print(f"\nGenerating optimized discs for {subject}...")
        discs = generate_disc_meshes(subject)

        # Write OBJ files
        for atlas_id, (verts, faces) in discs.items():
            filename = f"{subject}_{atlas_id}.obj"
            filepath = OUTPUT_DIR / filename
            write_obj_file(filepath, verts, faces)
            vertex_count = len(verts)
            face_count = len(faces)
            
            # Show lumbar discs with their new size
            if "disc_l" in atlas_id:
                print(f"  {filename}: {vertex_count} vertices, {face_count} faces (OPTIMIZED: r=50mm h=24mm)")
            else:
                print(f"  {filename}: {vertex_count} vertices, {face_count} faces")

        print(f"Generated {len(discs)} discs for {subject}")

    print(f"\nAll disc OBJ files written to {OUTPUT_DIR}")
    print("\nNext steps:")
    print("  python3 scripts/ingest_intervertebral_discs.py ingest")
    print("  python3 scripts/merge_disc_vertices.py merge")
    print("  python3 scripts/export_viewer_bundle.py --subject ct_vhm -o build/viewer_male --budget-scale 0.85")
    print("  python3 scripts/export_viewer_bundle.py --subject ct_vhf -o build/viewer_female --budget-scale 0.85")
    print("  python3 scripts/verify_vertebral_continuity.py analyze")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("command", choices=["generate"], help="Command to run")

    args = parser.parse_args()

    if args.command == "generate":
        return cmd_generate(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
