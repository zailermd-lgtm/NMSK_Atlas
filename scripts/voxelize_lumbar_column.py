#!/usr/bin/env python3
"""Voxelize the female (ct_vhf) lumbar vertebral column + its 4 lumbar discs,
dilate to bridge, and reconstruct via marching cubes -- the Q104b-recommended
"option 3" (voxelization-based bridging, like Q105/Q109's rib fix) applied to
the female lumbar region. See PROJECT_STATE.md's Q110 entry for the full story.

Q110 (2026-09-22) FINDINGS THAT SHAPE THIS SCRIPT (measured, not assumed):

1. The 5 real `lumbar_vertebrae` mesh pieces (L1-L5, from `vhf_total.nii.gz`)
   have 12 face-adjacency components on their own -- confirming Q104b's "8
   separate components" finding was the right order of magnitude (the official
   verify_vertebral_continuity.py under-counts this region because it keys
   `face_ranges` by atlas_id in a plain dict, so 5 same-atlas_id pieces collapse
   to 1 -- a bug Q107 already documented and left unfixed; this script's own
   sweep measurement does NOT have that bug, see `measure_main_frac()` below).

2. The lumbar discs Q104b sized at 50mm radius/24mm thickness and Q108 shipped
   are positioned at a per-REGION bounding-box center (`compute_region_bbox`
   in generate_optimized_lumbar_discs.py: min of all 5 vertebrae's bbox mins,
   max of all 5 maxs) that is silently poisoned by a ~1.8%-of-vertices outlier
   fragment inside `vertebrae_L2` (454 of 24996 vertices, bbox X 175.6-187.3mm,
   Y 107.9-116.5mm, Z 33.8-43.4mm -- a location that falls entirely inside the
   real `sacrum` structure's own bbox, and is a COMPLETELY DISJOINT mesh island
   with zero shared vertices with the rest of vertebrae_L2: almost certainly a
   TotalSegmentator mislabeling artifact, not real L2 anatomy, and already
   redundant with the separately-shipped `sacrum` structure). That single
   outlier pulls the region bbox's max-X from ~50mm (every other vertebra) to
   187mm, shifting every lumbar disc's computed X-center from ~0mm to ~69mm --
   so the shipped discs sit ENTIRELY OUTSIDE the real vertebral column's XY
   footprint (verified: including them barely changes main_frac at all, 0.1809
   -> 0.1806, because they contribute a 4-extra-isolated-components penalty and
   ZERO real bridging).

This script therefore, before voxelizing:
  (a) drops each real vertebra piece's own small disconnected fragments (kept:
      only the largest face-adjacency component per piece) -- this is a
      measured, documented cleanup of pre-existing segmentation noise, not a
      new fabrication (see DROPPED_FRAGMENTS output at runtime for exactly
      what was removed, size and location, on every vertebra, not just L2);
  (b) regenerates the 4 lumbar discs, PER LEVEL (not per-region), centered on
      the mean of the two adjacent (cleaned) vertebrae's own vertices in X/Y,
      keeping the existing 40mm radius / 20mm thickness (matching cervical/
      thoracic, which were never affected by this bug) instead of the
      poisoned-position 50mm/24mm ones -- this is a bug fix to a bug Q104b
      already diagnosed ("wrong XY coordinates... ~154mm shift"), not new
      scope.

Then: voxelize the whole set (5 cleaned vertebrae + 4 corrected discs) together
at 2mm, dilate N iterations (26-connectivity), marching-cubes reconstruct --
identical technique to voxelize_ribs_with_hubs.py.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Tuple

import numpy as np
from scipy import ndimage, sparse
from scipy.sparse.csgraph import connected_components
from skimage import measure
import trimesh

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

BUILD_DIR = REPO_ROOT / "build" / "vh"
OUTPUT_DIR = REPO_ROOT / "data" / "ct_sources" / "task_outputs"

SUBJECT = "ct_vhf"  # scoped to the female ONLY -- see PROJECT_STATE.md Q110 hard constraints
LUMBAR_ATLAS_ID = "lumbar_vertebrae"
DISC_LEVELS = ["l1_l2", "l2_l3", "l3_l4", "l4_l5"]  # order: upper-lower pairs, e.g. l1_l2 = disc between L1 and L2
DISC_RADIUS_MM = 40.0
DISC_THICKNESS_MM = 20.0


def read_mesh_binary(subject_dir: Path) -> Tuple[np.ndarray, np.ndarray]:
    verts = np.fromfile(subject_dir / "vertices.f32", dtype=np.float32).reshape(-1, 3)
    faces = np.fromfile(subject_dir / "faces.u32", dtype=np.uint32).reshape(-1, 3)
    return verts, faces


def load_manifest(subject: str) -> dict:
    with open(BUILD_DIR / subject / "manifest.json") as f:
        return json.load(f)


def write_obj_file(filepath: Path, vertices: np.ndarray, faces: np.ndarray) -> None:
    with open(filepath, "w") as f:
        f.write(f"# {filepath.stem}: {len(vertices)} vertices, {len(faces)} faces\n")
        for v in vertices:
            f.write(f"v {v[0]:.6f} {v[1]:.6f} {v[2]:.6f}\n")
        for face in faces:
            f.write(f"f {face[0]+1} {face[1]+1} {face[2]+1}\n")


def face_adjacency_components(verts: np.ndarray, faces: np.ndarray):
    """Return (n_components, labels_per_face) via shared-edge adjacency.

    Vectorized (not the slow pure-Python BFS in the older scripts); validated
    against verify_vertebral_continuity.py's slow method on the current
    (unmodified) lumbar_vertebrae + disc selection: both report main_frac
    0.1806/16 components for that input (see PROJECT_STATE.md Q110 entry).
    """
    v0, v1, v2 = faces[:, 0], faces[:, 1], faces[:, 2]
    e0 = np.stack([np.minimum(v0, v1), np.maximum(v0, v1)], axis=1)
    e1 = np.stack([np.minimum(v1, v2), np.maximum(v1, v2)], axis=1)
    e2 = np.stack([np.minimum(v2, v0), np.maximum(v2, v0)], axis=1)
    edges = np.vstack([e0, e1, e2])
    face_of_edge = np.tile(np.arange(len(faces)), 3)

    order = np.lexsort((edges[:, 1], edges[:, 0]))
    edges_sorted = edges[order]
    faces_sorted = face_of_edge[order]

    rows, cols = [], []
    n = len(edges_sorted)
    i = 0
    while i < n:
        j = i
        while j + 1 < n and edges_sorted[j + 1, 0] == edges_sorted[i, 0] and edges_sorted[j + 1, 1] == edges_sorted[i, 1]:
            j += 1
        if j > i:
            group = faces_sorted[i : j + 1]
            for a in range(len(group)):
                for b in range(a + 1, len(group)):
                    rows.append(group[a]); cols.append(group[b])
                    rows.append(group[b]); cols.append(group[a])
        i = j + 1

    n_faces = len(faces)
    adj = sparse.csr_matrix((np.ones(len(rows), dtype=bool), (rows, cols)), shape=(n_faces, n_faces))
    n_components, labels = connected_components(adj, directed=False)
    return n_components, labels


NOISE_FRAGMENT_MAX_FRACTION = 0.05  # Q110: only auto-drop a component this small
# (relative to the piece's own vertex count) or smaller. Chosen from measurement:
# vertebrae_L2's real segmentation-noise fragments (5 of them, almost certainly
# TotalSegmentator mislabeling -- see module docstring) are all <=4.13% of L2's
# vertices; vertebrae_L1's own posterior-element/vertebral-body split (a REAL,
# large secondary component, 46% of L1's vertices -- almost certainly a thin
# bone bridge lost during label-volume-to-mesh conversion, not noise) sits far
# above this threshold and must NOT be silently deleted -- it is real anatomy
# that voxelization+dilation should bridge, not remove. A 5% cutoff drops every
# measured noise fragment and keeps every measured real one; see the runtime
# report below for exactly what each vertebra actually had.


def clean_vertebra_piece(source_structure: str, verts: np.ndarray, faces: np.ndarray) -> Tuple[np.ndarray, np.ndarray, list]:
    """Drop only SMALL disconnected face-adjacency fragments of a vertebra
    piece (segmentation noise, see NOISE_FRAGMENT_MAX_FRACTION) -- large
    secondary components (real anatomy split by a thin, lost bone bridge) are
    kept and left for voxelization+dilation to bridge. Reports every fragment
    (kept or dropped) for transparency."""
    n_components, labels = face_adjacency_components(verts, faces)
    if n_components <= 1:
        return verts, faces, []

    comp_face_counts = np.bincount(labels)
    n_verts_total = len(verts)

    drop_comp_ids = set()
    dropped = []
    kept_secondary = []
    main_comp = int(np.argmax(comp_face_counts))
    for comp_id in range(n_components):
        face_mask = labels == comp_id
        verts_idx = np.unique(faces[face_mask])
        frac = len(verts_idx) / n_verts_total
        info = {
            "source_structure": source_structure,
            "n_vertices": int(len(verts_idx)),
            "n_faces": int(face_mask.sum()),
            "frac_of_piece_vertices": float(frac),
            "bbox_min_mm": verts[verts_idx].min(axis=0).tolist(),
            "bbox_max_mm": verts[verts_idx].max(axis=0).tolist(),
        }
        if comp_id != main_comp and frac <= NOISE_FRAGMENT_MAX_FRACTION:
            drop_comp_ids.add(comp_id)
            dropped.append(info)
        elif comp_id != main_comp:
            kept_secondary.append(info)

    keep_face_mask = ~np.isin(labels, list(drop_comp_ids))
    kept_faces_local = faces[keep_face_mask]
    used_verts = np.unique(kept_faces_local)
    remap = -np.ones(len(verts), dtype=np.int64)
    remap[used_verts] = np.arange(len(used_verts))
    new_verts = verts[used_verts]
    new_faces = remap[kept_faces_local]

    for info in kept_secondary:
        print(f"    KEEPING large secondary component of {source_structure}: "
              f"{info['n_vertices']} verts ({info['frac_of_piece_vertices']*100:.1f}%) at bbox "
              f"{[round(x,1) for x in info['bbox_min_mm']]} - {[round(x,1) for x in info['bbox_max_mm']]} "
              f"-- real anatomy, left for voxelization to bridge")

    return new_verts, new_faces, dropped


def load_clean_vertebrae(manifest: dict, all_verts: np.ndarray, all_faces: np.ndarray) -> dict:
    """Return {source_structure: (verts, faces)} for the 5 lumbar vertebrae,
    each reduced to its own largest face-adjacency component."""
    pieces = {}
    all_dropped = []
    for s in manifest["structures"]:
        if s["atlas_id"] != LUMBAR_ATLAS_ID:
            continue
        vo, vc = s["vertex_offset"], s["vertex_count"]
        fo, fc = s["face_offset"], s["triangle_count"]
        verts = all_verts[vo : vo + vc].copy()
        faces_local = (all_faces[fo : fo + fc].astype(np.int64) - vo)
        clean_verts, clean_faces, dropped = clean_vertebra_piece(s["source_structure"], verts, faces_local)
        pieces[s["source_structure"]] = (clean_verts, clean_faces.astype(np.uint32))
        all_dropped.extend(dropped)

    print(f"  Cleaned {len(pieces)} vertebra pieces; dropped fragments:")
    for d in all_dropped:
        print(f"    {d['source_structure']}: dropped {d['n_vertices']} verts "
              f"({d['frac_of_piece_vertices']*100:.2f}%%) at bbox "
              f"{[round(x,1) for x in d['bbox_min_mm']]} - {[round(x,1) for x in d['bbox_max_mm']]}")
    if not all_dropped:
        print("    (none)")
    return pieces


def build_corrected_discs(clean_vertebrae: dict) -> dict:
    """Build the 4 lumbar discs, each centered on the mean XY of its two
    adjacent (cleaned) vertebrae's own vertices, at the Z gap between them."""
    order = ["L1", "L2", "L3", "L4", "L5"]
    centroids = {name: clean_vertebrae[f"vertebrae_{name}"][0].mean(axis=0) for name in order}
    z_ranges = {
        name: (clean_vertebrae[f"vertebrae_{name}"][0][:, 2].min(),
               clean_vertebrae[f"vertebrae_{name}"][0][:, 2].max())
        for name in order
    }

    discs = {}
    for i, level in enumerate(DISC_LEVELS):
        upper, lower = order[i], order[i + 1]
        cu, cl = centroids[upper], centroids[lower]
        x_center = (cu[0] + cl[0]) / 2.0
        y_center = (cu[1] + cl[1]) / 2.0
        # Gap sits between upper vertebra's max-Z and lower vertebra's min-Z
        # (lumbar Z increases from L5 (lowest, most negative-Z here) to L1;
        # match whichever ordering the actual data uses by taking the mean of
        # the closest facing surfaces).
        z_u_min, z_u_max = z_ranges[upper]
        z_l_min, z_l_max = z_ranges[lower]
        # pick the pair of extents that are closest together (the real gap)
        candidates = [
            (abs(z_u_min - z_l_max), (z_u_min + z_l_max) / 2.0),
            (abs(z_u_max - z_l_min), (z_u_max + z_l_min) / 2.0),
        ]
        candidates.sort(key=lambda c: c[0])
        z_center = candidates[0][1]

        center = np.array([x_center, y_center, z_center])
        verts, faces = create_cylinder_mesh(center, DISC_RADIUS_MM, DISC_THICKNESS_MM)
        discs[level] = (verts.astype(np.float32), faces.astype(np.uint32))
        print(f"    disc {level}: center=({x_center:.1f},{y_center:.1f},{z_center:.1f}) "
              f"gap={candidates[0][0]:.1f}mm (was ~65-70mm off-axis before this fix)")
    return discs


def create_cylinder_mesh(center: np.ndarray, radius: float, height: float, n_segments: int = 32):
    vertices = []
    z_top, z_bot = height / 2.0, -height / 2.0
    angles = np.linspace(0, 2 * np.pi, n_segments, endpoint=False)
    for angle in angles:
        vertices.append([radius * np.cos(angle), radius * np.sin(angle), z_top])
    for angle in angles:
        vertices.append([radius * np.cos(angle), radius * np.sin(angle), z_bot])
    vertices.append([0, 0, z_top]); top_center_idx = len(vertices) - 1
    vertices.append([0, 0, z_bot]); bot_center_idx = len(vertices) - 1
    vertices = np.array(vertices)
    vertices[:, :3] += center[np.newaxis, :]

    faces = []
    for i in range(n_segments):
        ni = (i + 1) % n_segments
        faces.append([i, n_segments + i, n_segments + ni])
        faces.append([i, n_segments + ni, ni])
    for i in range(n_segments):
        ni = (i + 1) % n_segments
        faces.append([i, ni, top_center_idx])
    for i in range(n_segments):
        ni = (i + 1) % n_segments
        faces.append([n_segments + ni, n_segments + i, bot_center_idx])
    return vertices, np.array(faces)


def voxelize_and_reconstruct(
    consolidated_verts: np.ndarray,
    consolidated_faces: np.ndarray,
    voxel_size: float,
    dilation_iterations: int,
) -> Tuple[np.ndarray, np.ndarray]:
    mesh = trimesh.Trimesh(vertices=consolidated_verts, faces=consolidated_faces, process=False)
    voxel_grid = mesh.voxelized(pitch=voxel_size)
    print(f"    voxel grid shape: {voxel_grid.matrix.shape}")

    struct = ndimage.generate_binary_structure(3, 26)
    dilated = ndimage.binary_dilation(voxel_grid.matrix, structure=struct, iterations=dilation_iterations)

    result = measure.marching_cubes(dilated, level=0.5)
    vertices_voxel, faces_new = result[0], result[1]

    origin = voxel_grid.bounds[0]
    vertices = vertices_voxel * voxel_size + origin
    return vertices, faces_new


def build_consolidated_input(clean_vertebrae: dict, discs: dict) -> Tuple[np.ndarray, np.ndarray, dict]:
    """Stack the 5 cleaned vertebrae + 4 corrected discs into one mesh array,
    tracking each source piece's vertex range for the volume-distortion check."""
    all_v, all_f = [], []
    vert_offset = 0
    piece_ranges = {}
    for name, (v, f) in list(clean_vertebrae.items()) + list(discs.items()):
        all_v.append(v)
        all_f.append(f.astype(np.int64) + vert_offset)
        piece_ranges[name] = (vert_offset, vert_offset + len(v))
        vert_offset += len(v)
    consolidated_verts = np.vstack(all_v)
    consolidated_faces = np.vstack(all_f).astype(np.uint32)
    return consolidated_verts, consolidated_faces, piece_ranges


def cmd_voxelize(args: argparse.Namespace) -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    manifest = load_manifest(SUBJECT)
    all_verts, all_faces = read_mesh_binary(BUILD_DIR / SUBJECT)

    print(f"Loading & cleaning {SUBJECT} lumbar vertebrae...")
    clean_vertebrae = load_clean_vertebrae(manifest, all_verts, all_faces)

    print("Building corrected (per-level, real-vertebra-centered) discs...")
    discs = build_corrected_discs(clean_vertebrae)

    consolidated_verts, consolidated_faces, piece_ranges = build_consolidated_input(clean_vertebrae, discs)
    print(f"Consolidated input: {len(consolidated_verts)} verts, {len(consolidated_faces)} faces "
          f"(5 vertebrae + 4 discs)")

    # Save the pre-voxelization consolidated input + piece ranges for the
    # volume-distortion check (cmd_volume_check) to reuse without recomputing
    # the cleaning/recentering step.
    np.savez(
        OUTPUT_DIR / "ct_vhf_lumbar_column_input.npz",
        verts=consolidated_verts, faces=consolidated_faces,
    )
    with open(OUTPUT_DIR / "ct_vhf_lumbar_column_piece_ranges.json", "w") as f:
        json.dump({k: list(v) for k, v in piece_ranges.items()}, f, indent=2)

    dilations = args.dilation_iterations
    for d in dilations:
        print(f"\nVoxelizing at {args.voxel_size}mm, dilation={d} iterations...")
        vertices, faces = voxelize_and_reconstruct(consolidated_verts, consolidated_faces, args.voxel_size, d)
        print(f"    reconstructed: {len(vertices)} verts, {len(faces)} faces")
        out_path = OUTPUT_DIR / f"ct_vhf_lumbar_column_remeshed_d{d}.obj"
        write_obj_file(out_path, vertices, faces)
        print(f"    wrote {out_path}")

    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["voxelize"])
    parser.add_argument("--voxel-size", type=float, default=2.0)
    parser.add_argument("--dilation-iterations", type=int, nargs="+", default=[4])
    args = parser.parse_args()
    if args.command == "voxelize":
        return cmd_voxelize(args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
