#!/usr/bin/env python3
"""Generate cylindrical intervertebral disc meshes to bridge vertebral fragmentation.

This script creates idealized geometric cylinder meshes representing
intervertebral discs between adjacent vertebrae. The discs are positioned
at regular intervals within each vertebral region's Z-extent.

Disc parameters (as actually used below; this docstring previously said
14mm/8mm, stale since before this script's own disc_radius/disc_thickness
constants were set to 40/20 -- see Q104's PROJECT_STATE.md entry):
  - Radius: 40 mm (super-sized to absolutely ensure XY overlap)
  - Thickness: 20 mm

Vertebral levels:
  - Cervical: C1-C2 through C6-C7 (6 discs)
  - Thoracic: T1-T2 through T11-T12 (11 discs)
  - Lumbar: L1-L2 through L4-L5 (4 discs)
  Total: 21 discs per body

Cervical/thoracic discs are centered on a single region-wide vertebra bbox
per region. Lumbar discs (Q111 fix) are instead centered per adjacent pair
of vertebrae -- see compute_lumbar_disc_centers's own docstring for why the
lumbar region needs that and the other two don't.

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


def read_mesh_binary(subject: str) -> tuple[np.ndarray, np.ndarray]:
    """Read a subject's shipped mesh from its binary vertex/face files."""
    subject_dir = BUILD_DIR / subject
    verts = np.fromfile(subject_dir / "vertices.f32", dtype=np.float32).reshape(-1, 3)
    faces = np.fromfile(subject_dir / "faces.u32", dtype=np.uint32).reshape(-1, 3)
    return verts, faces


def compute_region_bbox(
    manifest: dict,
    atlas_id: str,
    all_verts: np.ndarray | None = None,
    all_faces: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray] | None:
    """Compute bounding box encompassing all fragments of a vertebra region.

    Q111 FIX: when mesh data is supplied, each fragment is first reduced to
    its own largest face-adjacency component (+ any large, real secondary
    component -- see clean_vertebra_piece's own NOISE_FRAGMENT_MAX_FRACTION
    threshold) before its bbox is folded into the region bbox. This matters
    because a manifest fragment's own bbox_min/max_mm is the RAW extent of
    every vertex in that fragment, including any small disjoint island that
    doesn't belong to it. Q110 found exactly this for ct_vhf's vertebrae_L2:
    a ~1.8%-of-vertices fragment (454/24996 verts) that is a genuinely
    separate mesh island (zero shared vertices with the rest of L2) sitting
    entirely inside the real `sacrum` structure's own bbox. Traced to the
    RAW source label volume itself (see PROJECT_STATE.md's Q111 entry): the
    same disjoint voxel cluster (502 raw voxels, 1.77% of L2's raw voxel
    count) already exists in vhf_total.nii.gz's own label==30 mask, at the
    exact same location -- a TotalSegmentator source-label artifact, not
    something this project's ingestion pipeline introduced. Excluding it here
    (rather than trusting the raw label mask's full extent) is a generally
    more robust way to compute a region's bbox regardless of which vertebra
    happens to carry the mislabeled voxels.

    Falls back to the raw manifest bboxes when no mesh data is given (keeps
    every existing caller working unchanged).
    """
    frags = [s for s in manifest["structures"] if s["atlas_id"] == atlas_id]

    if not frags:
        return None

    if all_verts is None or all_faces is None:
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

    mins, maxs = [], []
    for frag in frags:
        vo, vc = frag["vertex_offset"], frag["vertex_count"]
        fo, fc = frag["face_offset"], frag["triangle_count"]
        verts = all_verts[vo : vo + vc]
        faces_local = all_faces[fo : fo + fc].astype(np.int64) - vo
        clean_verts, _clean_faces, _dropped = clean_vertebra_piece(
            frag.get("source_structure", atlas_id), verts, faces_local
        )
        mins.append(clean_verts.min(axis=0))
        maxs.append(clean_verts.max(axis=0))

    return (
        np.stack(mins).min(axis=0),
        np.stack(maxs).max(axis=0),
    )


def compute_lumbar_disc_centers(
    manifest: dict, all_verts: np.ndarray, all_faces: np.ndarray
) -> dict[str, np.ndarray]:
    """Per-level (adjacent-pair) disc centers for the lumbar column.

    Q111 FIX: `compute_region_bbox` alone is not enough for the lumbar
    region even once the mislabeled L2 fragment is excluded, because this
    atlas's frame has +Y as the craniocaudal (superior-inferior) axis (see
    manifest["frame"]), and the 5 lumbar vertebrae's own X/Y centroids shift
    by tens of mm level to level (measured: L1 (-4.0, 273.8) -> L5 (0.2,
    126.6), a 147mm swing in Y alone) -- a single region-wide XY center
    cannot track that curve. This reproduces Q110's own validated
    per-level approach (`voxelize_lumbar_column.py`'s build_corrected_discs`,
    prototyped there but never shipped): each disc is centered on the mean
    XY of its two adjacent (cleaned) vertebrae's own vertices, at whichever
    pair of the two vertebrae's Z-extents faces each other most closely.
    """
    order = ["L1", "L2", "L3", "L4", "L5"]
    pieces = {
        s["source_structure"]: s
        for s in manifest["structures"]
        if s["atlas_id"] == "lumbar_vertebrae"
    }
    missing = [n for n in order if f"vertebrae_{n}" not in pieces]
    if missing:
        raise SystemExit(f"Missing lumbar vertebra pieces: {missing}")

    clean_verts = {}
    for name in order:
        frag = pieces[f"vertebrae_{name}"]
        vo, vc = frag["vertex_offset"], frag["vertex_count"]
        fo, fc = frag["face_offset"], frag["triangle_count"]
        verts = all_verts[vo : vo + vc]
        faces_local = all_faces[fo : fo + fc].astype(np.int64) - vo
        cv, _cf, _dropped = clean_vertebra_piece(f"vertebrae_{name}", verts, faces_local)
        clean_verts[name] = cv

    centroids = {n: clean_verts[n].mean(axis=0) for n in order}
    z_ranges = {n: (clean_verts[n][:, 2].min(), clean_verts[n][:, 2].max()) for n in order}

    centers = {}
    for i in range(4):
        upper, lower = order[i], order[i + 1]
        level_key = f"l{i+1}_l{i+2}"
        cu, cl = centroids[upper], centroids[lower]
        x_center = (cu[0] + cl[0]) / 2.0
        y_center = (cu[1] + cl[1]) / 2.0
        zu_min, zu_max = z_ranges[upper]
        zl_min, zl_max = z_ranges[lower]
        candidates = [
            (abs(zu_min - zl_max), (zu_min + zl_max) / 2.0),
            (abs(zu_max - zl_min), (zu_max + zl_min) / 2.0),
        ]
        candidates.sort(key=lambda c: c[0])
        z_center = candidates[0][1]
        centers[level_key] = np.array([x_center, y_center, z_center])

    return centers


def generate_disc_meshes(subject: str) -> dict:
    """Generate all intervertebral disc meshes for a subject.

    Returns dict mapping level.atlas_id -> (vertices, faces)
    """
    manifest = load_manifest(subject)
    all_verts, all_faces = read_mesh_binary(subject)

    # Get bounding boxes for vertebra regions (encompassing all fragments).
    # Q111: cleaned via compute_region_bbox's largest-component filtering --
    # verified a no-op for cervical/thoracic on both subjects (<=2.25mm
    # shift, see PROJECT_STATE.md's Q111 entry) so this is safe to always use.
    cervical_bbox = compute_region_bbox(manifest, "cervical_vertebrae", all_verts, all_faces)
    thoracic_bbox = compute_region_bbox(manifest, "thoracic_vertebrae", all_verts, all_faces)

    if not all([cervical_bbox, thoracic_bbox]):
        raise SystemExit(f"Missing vertebra regions in {subject} manifest")

    # Q111: lumbar no longer uses a single region-wide bbox center at all --
    # see compute_lumbar_disc_centers's own docstring for why that was never
    # going to work in this atlas frame, mislabeled fragment or not.
    lumbar_centers = compute_lumbar_disc_centers(manifest, all_verts, all_faces)

    # Disc parameters - SUPER-SIZED to absolutely ensure connectivity
    # These are procedural/synthetic geometry, not anatomically extracted, so size
    # is purely determined by the connectivity goal (main_frac ≥ 0.99).
    disc_radius = 40.0  # mm (super-large to absolutely ensure XY overlap)
    disc_thickness = 20.0  # mm (very thick to span all Z gaps and have margin)

    discs = {}

    # Position discs evenly through each region's Z range

    for level in CERVICAL_LEVELS:
        bbox_min, bbox_max = cervical_bbox
        parts = level.name.split('-')
        lower_idx = int(parts[0][1:])  # Get number from C1, C2, etc.

        # 6 discs for C1-C7, place them at proportional positions
        frac = (lower_idx - 0.5) / 6.0
        z_disc = bbox_min[2] + frac * (bbox_max[2] - bbox_min[2])
        x_center = (bbox_min[0] + bbox_max[0]) / 2.0
        y_center = (bbox_min[1] + bbox_max[1]) / 2.0

        center = np.array([x_center, y_center, z_disc])
        verts, faces = create_cylinder_mesh(center, disc_radius, disc_thickness)
        discs[level.atlas_id] = (verts, faces)

    for level in THORACIC_LEVELS:
        bbox_min, bbox_max = thoracic_bbox
        parts = level.name.split('-')
        lower_idx = int(parts[0][1:])

        # 11 discs for T1-T12
        frac = (lower_idx - 0.5) / 11.0
        z_disc = bbox_min[2] + frac * (bbox_max[2] - bbox_min[2])
        x_center = (bbox_min[0] + bbox_max[0]) / 2.0
        y_center = (bbox_min[1] + bbox_max[1]) / 2.0

        center = np.array([x_center, y_center, z_disc])
        verts, faces = create_cylinder_mesh(center, disc_radius, disc_thickness)
        discs[level.atlas_id] = (verts, faces)

    for level in LUMBAR_LEVELS:
        # Q111: per-level (adjacent-pair) center, not the region-wide bbox
        # center used above for cervical/thoracic -- see
        # compute_lumbar_disc_centers's docstring for why the lumbar region
        # needs this and the other two regions don't (empirically, no-op
        # there; see PROJECT_STATE.md's Q111 entry).
        level_key = level.atlas_id.replace("intervertebral_disc_", "")
        center = lumbar_centers[level_key]
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
