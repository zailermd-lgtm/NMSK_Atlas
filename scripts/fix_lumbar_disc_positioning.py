#!/usr/bin/env python3
"""Fix lumbar disc positioning to be centered on actual vertebra centers.

The discs were positioned using the region's bounding box center, which doesn't
work well for fragmented vertebrae. This script repositions them to match the
actual vertebral body centers."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from collections import defaultdict

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

BUILD_DIR = REPO_ROOT / "build" / "vh"


def read_mesh_binary(subject_dir: Path) -> tuple[np.ndarray, np.ndarray]:
    verts = np.fromfile(subject_dir / "vertices.f32", dtype=np.float32).reshape(-1, 3)
    faces = np.fromfile(subject_dir / "faces.u32", dtype=np.uint32).reshape(-1, 3)
    return verts, faces


def write_mesh_binary(subject_dir: Path, vertices: np.ndarray, faces: np.ndarray) -> None:
    vertices.astype(np.float32).tofile(subject_dir / "vertices.f32")
    faces.astype(np.uint32).tofile(subject_dir / "faces.u32")


def load_manifest(subject: str) -> dict:
    manifest_path = BUILD_DIR / subject / "manifest.json"
    with open(manifest_path) as f:
        return json.load(f)


def fix_lumbar_disc_positions(verts: np.ndarray, manifest: dict) -> np.ndarray:
    """Reposition lumbar discs to actual vertebra centers."""
    
    # Get lumbar vertebrae vertices
    lumbar_struct = next((s for s in manifest["structures"] if s["atlas_id"] == "lumbar_vertebrae"), None)
    if not lumbar_struct:
        print("  No lumbar_vertebrae found")
        return verts
    
    v_start = lumbar_struct["vertex_offset"]
    v_end = v_start + lumbar_struct["vertex_count"]
    lumbar_verts = verts[v_start:v_end]
    
    # Compute actual lumbar vertebrae center in XY (not using bounding box)
    lumbar_center_x = lumbar_verts[:, 0].mean()
    lumbar_center_y = lumbar_verts[:, 1].mean()
    
    print(f"  Lumbar vertebrae XY center: ({lumbar_center_x:.1f}, {lumbar_center_y:.1f})")
    print(f"  Lumbar vertebrae Z range: {lumbar_verts[:, 2].min():.1f} to {lumbar_verts[:, 2].max():.1f}")
    
    # For each disc, reposition its XY coordinates to lumbar center
    disc_ids = [f"intervertebral_disc_l{i}_l{i+1}" for i in range(1, 5)]
    
    repositioned_count = 0
    for disc_id in disc_ids:
        disc_struct = next((s for s in manifest["structures"] if s["atlas_id"] == disc_id), None)
        if not disc_struct:
            continue
        
        d_start = disc_struct["vertex_offset"]
        d_end = d_start + disc_struct["vertex_count"]
        disc_verts = verts[d_start:d_end]
        
        # Get disc's current center
        old_center_x = disc_verts[:, 0].mean()
        old_center_y = disc_verts[:, 1].mean()
        
        # Compute offset to lumbar center
        dx = lumbar_center_x - old_center_x
        dy = lumbar_center_y - old_center_y
        
        # Apply offset
        verts[d_start:d_end, 0] += dx
        verts[d_start:d_end, 1] += dy
        
        print(f"  {disc_id}: shifted ({dx:+.1f}, {dy:+.1f})")
        repositioned_count += 1
    
    print(f"  Repositioned {repositioned_count} discs")
    return verts


def cmd_fix(args: argparse.Namespace) -> int:
    """Fix disc positioning."""
    print("Fixing lumbar disc positioning (centering on actual vertebra centers)\n")
    
    for subject in ["ct_vhm", "ct_vhf"]:
        print(f"{subject}:")
        subject_dir = BUILD_DIR / subject
        
        # Read mesh and manifest
        verts, faces = read_mesh_binary(subject_dir)
        manifest = load_manifest(subject)
        
        print(f"  Current mesh: {len(verts)} vertices, {len(faces)} faces")
        
        # Fix disc positioning
        verts = fix_lumbar_disc_positions(verts, manifest)
        
        # Write mesh
        write_mesh_binary(subject_dir, verts, faces)
        print(f"  Wrote mesh: {len(verts)} vertices, {len(faces)} faces\n")
    
    print("Disc positioning fixed. Now verify continuity:")
    print("  python3 scripts/verify_vertebral_continuity.py analyze")
    
    return 0


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("command", choices=["fix"], help="Command to run")
    
    args = parser.parse_args()
    
    if args.command == "fix":
        return cmd_fix(args)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
