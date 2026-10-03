#!/usr/bin/env python3
"""Generate cylindrical intervertebral disc meshes to bridge vertebral fragmentation.

This script creates idealized geometric cylinder meshes representing
intervertebral discs between adjacent vertebrae. Each disc is centered
per adjacent PAIR of vertebrae (compute_region_vertebra_pieces +
compute_level_disc_centers), with its thickness axis along Y -- this
atlas's craniocaudal axis (+Y superior, +Z anterior; see
build/vh/*/manifest.json's "frame" field) -- so it actually sits between
its two neighbours instead of stacked front-to-back at one fixed height.

Q148 FIX: until this fix, only the lumbar region got per-pair placement
(Q111); cervical/thoracic used a single region-wide bbox center with the
disc's position varied only along Z (this atlas's ANTERIOR axis, not
craniocaudal) by fraction of index -- so every cervical disc shared one
X/Y and every thoracic disc shared another, both spread front-to-back
instead of stacked top-to-bottom (the owner-reported bug). The cylinder
mesh itself also had its axis on Z (radius spanning XY) instead of Y
(radius spanning XZ), which affected lumbar too even after Q111's center
fix -- see create_cylinder_mesh's docstring.

Disc parameters (as actually used below; this docstring previously said
14mm/8mm, stale since before this script's own disc_radius/disc_thickness
constants were set to 40/20 -- see Q104's PROJECT_STATE.md entry):
  - Radius: 40 mm (XZ plane; super-sized to absolutely ensure overlap)
  - Thickness: 20 mm (Y axis, craniocaudal)

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

# Reuse the validated face-adjacency / per-piece-cleaning primitives Q110
# already built and cross-checked (see PROJECT_STATE.md's Q110 entry) instead
# of re-implementing them here.
from scripts.voxelize_lumbar_column import (  # noqa: E402
    face_adjacency_components,
    clean_vertebra_piece,
)

OUTPUT_DIR = REPO_ROOT / "data" / "ct_sources" / "task_outputs"
BUILD_DIR = REPO_ROOT / "build" / "vh"


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
    """Create a disc-shaped cylinder mesh: axis (thickness direction) along Y,
    radius spanning the XZ plane.

    Q148 FIX: this used to build the cylinder with its axis along Z and its
    radius spanning XY ("centered at origin in XY plane, extended in Z"), i.e.
    it assumed Z was the craniocaudal axis. This atlas's frame is +X right,
    +Y superior, +Z anterior (see build/vh/*/manifest.json's "frame" field) --
    Y is craniocaudal, not Z. With the old axis choice every disc's `radius`
    (40mm) extent landed in Y, so a disc was ~80mm tall regardless of the
    actual ~10-40mm gap between its two vertebrae, while its `height`
    (thickness, the dimension that should separate one level from the next)
    sat in Z and did no such separating. Swapping the local Y and Z axes here
    makes the disc's thickness span the real superior-inferior gap and its
    radius span the (mostly small) left-right/anterior-posterior footprint,
    matching this frame.

    Args:
        center: 3D center point for the cylinder
        radius: cylinder radius in mm (XZ plane)
        height: cylinder height (thickness) in mm (Y axis, craniocaudal)
        n_segments: number of radial segments (default 32 for smoothness)

    Returns:
        (vertices, faces): vertices array [N, 3] and faces array [M, 3]
    """
    # Generate vertices in local coordinates (cylinder axis is Y)
    vertices = []

    # Top and bottom circle centers
    y_top = height / 2.0
    y_bot = -height / 2.0

    # Top circle
    angles = np.linspace(0, 2 * np.pi, n_segments, endpoint=False)
    for angle in angles:
        x = radius * np.cos(angle)
        z = radius * np.sin(angle)
        vertices.append([x, y_top, z])

    # Bottom circle
    for angle in angles:
        x = radius * np.cos(angle)
        z = radius * np.sin(angle)
        vertices.append([x, y_bot, z])

    # Top cap center
    vertices.append([0, y_top, 0])
    top_center_idx = len(vertices) - 1

    # Bottom cap center
    vertices.append([0, y_bot, 0])
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


def read_mesh_binary(subject: str) -> tuple[np.ndarray, np.ndarray]:
    """Read a subject's shipped mesh from its binary vertex/face files."""
    subject_dir = BUILD_DIR / subject
    verts = np.fromfile(subject_dir / "vertices.f32", dtype=np.float32).reshape(-1, 3)
    faces = np.fromfile(subject_dir / "faces.u32", dtype=np.uint32).reshape(-1, 3)
    return verts, faces


def compute_region_vertebra_pieces(
    manifest: dict, all_verts: np.ndarray, all_faces: np.ndarray, atlas_id: str
) -> list[np.ndarray]:
    """Each individual vertebra's own cleaned vertex array for `atlas_id`,
    ordered craniocaudally (most superior first).

    Q148 FIX (was Q111, lumbar-only): `cervical_vertebrae`/`thoracic_vertebrae`/
    `lumbar_vertebrae` are each one atlas_id shared by several manifest
    `structures` records -- one per REAL, separate vertebra (confirmed: 7/12/5
    records respectively, on both ct_vhm and ct_vhf) -- but neither ct_vhm's
    manifest (recovered from the published bundle) nor ct_vhf's cervical/
    thoracic records carry a name or label id that says which record is C1 vs
    C2 etc (only ct_vhf's lumbar records happen to carry it, as
    `source_structure: "vertebrae_L1"` etc, which the old lumbar-only version
    of this function keyed on and which silently did nothing useful for
    ct_vhm, whose lumbar records are all just `"lumbar_vertebrae"`). Ordering
    by mean Y instead -- this atlas's craniocaudal axis (`+Y superior`, see
    manifest["frame"]) -- needs no name at all and is verified monotonic on
    every region/subject checked for Q148 (e.g. ct_vhm cervical mean Y: 714.6,
    704.1, 678.6, 661.6, 644.5, 627.8, 610.1 -- strictly decreasing, C1..C7).

    Each fragment is first reduced to its own largest face-adjacency
    component (+ any large, real secondary component) via
    `clean_vertebra_piece`, same as Q111's `compute_region_bbox` did, so a
    disjoint segmentation-noise island (e.g. ct_vhf's vertebrae_L2, see
    PROJECT_STATE.md's Q111 entry) can't pull a centroid off.
    """
    frags = [s for s in manifest["structures"] if s["atlas_id"] == atlas_id]
    pieces = []
    for frag in frags:
        vo, vc = frag["vertex_offset"], frag["vertex_count"]
        fo, fc = frag["face_offset"], frag["triangle_count"]
        verts = all_verts[vo : vo + vc]
        faces_local = all_faces[fo : fo + fc].astype(np.int64) - vo
        cv, _cf, _dropped = clean_vertebra_piece(
            frag.get("source_structure", atlas_id), verts, faces_local
        )
        pieces.append(cv)
    pieces.sort(key=lambda v: -v[:, 1].mean())
    return pieces


def compute_level_disc_centers(pieces: list[np.ndarray]) -> list[np.ndarray]:
    """Per-level (adjacent-pair) disc centers, one per consecutive pair in
    `pieces` (already ordered craniocaudally by
    `compute_region_vertebra_pieces`).

    Generalizes Q111's lumbar-only per-pair placement to cervical/thoracic
    too (Q148): X and Y (this atlas's craniocaudal axis) are centered on the
    mean of the two adjacent vertebrae's own vertices -- tracking each
    level's real position along the spine's curve instead of a single
    region-wide average, which is what left every cervical disc at the same
    fixed X/Y and every thoracic disc at another single fixed X/Y (Q148 bug).
    Z (this atlas's anterior axis) is placed at whichever pair of the two
    vertebrae's Z-extents faces each other most closely, following the
    spine's own anteroposterior curve (lordosis/kyphosis) rather than a
    plain Z-centroid average.
    """
    centroids = [p.mean(axis=0) for p in pieces]
    z_ranges = [(p[:, 2].min(), p[:, 2].max()) for p in pieces]

    centers = []
    for i in range(len(pieces) - 1):
        cu, cl = centroids[i], centroids[i + 1]
        x_center = (cu[0] + cl[0]) / 2.0
        y_center = (cu[1] + cl[1]) / 2.0
        zu_min, zu_max = z_ranges[i]
        zl_min, zl_max = z_ranges[i + 1]
        candidates = [
            (abs(zu_min - zl_max), (zu_min + zl_max) / 2.0),
            (abs(zu_max - zl_min), (zu_max + zl_min) / 2.0),
        ]
        candidates.sort(key=lambda c: c[0])
        z_center = candidates[0][1]
        centers.append(np.array([x_center, y_center, z_center]))

    return centers


# Expected vertebra fragment count per region -- see
# compute_region_vertebra_pieces's docstring for why fragment COUNT (not a
# name/label) is what identifies them here.
_REGION_VERTEBRA_COUNTS = {
    "cervical_vertebrae": 7,
    "thoracic_vertebrae": 12,
    "lumbar_vertebrae": 5,
}


def generate_disc_meshes(subject: str) -> dict:
    """Generate all intervertebral disc meshes for a subject.

    Returns dict mapping level.atlas_id -> (vertices, faces)
    """
    manifest = load_manifest(subject)
    all_verts, all_faces = read_mesh_binary(subject)

    # Q148 FIX: every region (not just lumbar, per Q111) now gets its own
    # per-level (adjacent-vertebra-pair) disc center -- see
    # compute_region_vertebra_pieces/compute_level_disc_centers's docstrings.
    # The old cervical/thoracic path centered every disc in a region on that
    # region's single bbox-wide X/Y and only varied Z by fraction of the
    # region's Z-extent: since Z is this atlas's ANTERIOR axis, not the
    # craniocaudal one, that produced discs stacked front-to-back at one
    # fixed height instead of stacked superior-to-inferior between their
    # actual vertebrae (the owner-reported bug).
    region_centers = {}
    for atlas_id, expected_count in _REGION_VERTEBRA_COUNTS.items():
        pieces = compute_region_vertebra_pieces(manifest, all_verts, all_faces, atlas_id)
        if len(pieces) != expected_count:
            raise SystemExit(
                f"{subject}: expected {expected_count} {atlas_id} fragments, found {len(pieces)}"
            )
        region_centers[atlas_id] = compute_level_disc_centers(pieces)

    # Disc parameters - SUPER-SIZED to absolutely ensure connectivity
    # These are procedural/synthetic geometry, not anatomically extracted, so size
    # is purely determined by the connectivity goal (main_frac ≥ 0.99).
    disc_radius = 40.0  # mm (super-large to absolutely ensure XZ-plane overlap)
    disc_thickness = 20.0  # mm (Y axis; spans the real inter-vertebral gap with margin)

    discs = {}

    for level, center in zip(CERVICAL_LEVELS, region_centers["cervical_vertebrae"]):
        verts, faces = create_cylinder_mesh(center, disc_radius, disc_thickness)
        discs[level.atlas_id] = (verts, faces)

    for level, center in zip(THORACIC_LEVELS, region_centers["thoracic_vertebrae"]):
        verts, faces = create_cylinder_mesh(center, disc_radius, disc_thickness)
        discs[level.atlas_id] = (verts, faces)

    for level, center in zip(LUMBAR_LEVELS, region_centers["lumbar_vertebrae"]):
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
    """Generate disc meshes for the requested subject(s)/level(s)."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    subjects = [args.subject] if args.subject else ["ct_vhm", "ct_vhf"]
    lumbar_ids = {lvl.atlas_id for lvl in LUMBAR_LEVELS}

    for subject in subjects:
        print(f"\nGenerating discs for {subject}...")
        discs = generate_disc_meshes(subject)

        if args.only_lumbar:
            discs = {aid: v for aid, v in discs.items() if aid in lumbar_ids}

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
    parser.add_argument(
        "--subject",
        choices=["ct_vhm", "ct_vhf"],
        default=None,
        help="Limit to one subject (default: both, matching original behavior).",
    )
    parser.add_argument(
        "--only-lumbar",
        action="store_true",
        help="Only write the 4 lumbar disc OBJ files (still computes all region "
             "bboxes/centers first, since generate_disc_meshes needs them, but "
             "skips writing cervical/thoracic files so they're never touched).",
    )

    args = parser.parse_args()

    if args.command == "generate":
        return cmd_generate(args)

    return 0


if __name__ == "__main__":
    sys.exit(main())
