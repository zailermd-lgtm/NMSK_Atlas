#!/usr/bin/env python3
"""Replace lumbar discs directly in the mesh with optimized larger discs.

This script:
1. Loads the mesh and manifest
2. Finds lumbar disc structures
3. Replaces their OBJ files with optimized versions
4. Rebuilds the mesh with new discs
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

BUILD_DIR = REPO_ROOT / "build" / "vh"
OUTPUT_DIR = REPO_ROOT / "data" / "ct_sources" / "task_outputs"


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


def save_manifest(subject: str, manifest: dict) -> None:
    manifest_path = BUILD_DIR / subject / "manifest.json"
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)


def read_obj_file(filepath: Path) -> tuple[np.ndarray, np.ndarray]:
    """Read OBJ file."""
    vertices = []
    faces = []
    
    with open(filepath, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            
            parts = line.split()
            if not parts:
                continue
            
            if parts[0] == 'v':
                v = [float(parts[1]), float(parts[2]), float(parts[3])]
                vertices.append(v)
            elif parts[0] == 'f':
                face_indices = []
                for part in parts[1:]:
                    v_idx = int(part.split('/')[0]) - 1
                    face_indices.append(v_idx)
                
                for i in range(1, len(face_indices) - 1):
                    faces.append([face_indices[0], face_indices[i], face_indices[i + 1]])
    
    return np.array(vertices), np.array(faces)


def cmd_replace(args: argparse.Namespace) -> int:
    """Replace lumbar discs with optimized versions."""
    print("Replacing lumbar discs with optimized larger discs\n")
    
    for subject in ["ct_vhm", "ct_vhf"]:
        print(f"{subject}:")
        subject_dir = BUILD_DIR / subject
        
        # Load mesh and manifest
        verts, faces = read_mesh_binary(subject_dir)
        manifest = load_manifest(subject)
        
        print(f"  Original mesh: {len(verts)} vertices, {len(faces)} faces")
        
        # Find lumbar disc structures
        lumbar_disc_ids = [f"intervertebral_disc_l{i}_l{i+1}" for i in range(1, 5)]
        lumbar_disc_structs = [s for s in manifest["structures"] if s["atlas_id"] in lumbar_disc_ids]
        
        if not lumbar_disc_structs:
            print("  No lumbar discs found in manifest")
            continue
        
        # Build index mapping: what vertices/faces belong to current discs
        disc_vertex_ranges = {}
        disc_face_ranges = {}
        
        for struct in lumbar_disc_structs:
            aid = struct["atlas_id"]
            vert_start = struct["vertex_offset"]
            vert_end = vert_start + struct["vertex_count"]
            face_start = struct["face_offset"]
            face_end = face_start + struct["triangle_count"]
            
            disc_vertex_ranges[aid] = (vert_start, vert_end)
            disc_face_ranges[aid] = (face_start, face_end)
        
        # Load new disc OBJ files
        new_discs = {}
        for disc_id in lumbar_disc_ids:
            obj_file = OUTPUT_DIR / f"{subject}_{disc_id}.obj"
            if obj_file.exists():
                new_verts, new_faces = read_obj_file(obj_file)
                new_discs[disc_id] = (new_verts, new_faces)
        
        print(f"  Found {len(new_discs)} new disc OBJ files")
        
        if len(new_discs) != len(lumbar_disc_ids):
            print(f"  ERROR: Expected {len(lumbar_disc_ids)} disc files, found {len(new_discs)}")
            continue
        
        # Check if vertices/faces match
        print(f"  Checking size compatibility...")
        size_ok = True
        for disc_id in lumbar_disc_ids:
            old_v_start, old_v_end = disc_vertex_ranges[disc_id]
            old_f_start, old_f_end = disc_face_ranges[disc_id]
            old_v_count = old_v_end - old_v_start
            old_f_count = old_f_end - old_f_start
            
            new_v_count, new_f_count = len(new_discs[disc_id][0]), len(new_discs[disc_id][1])
            
            if old_v_count != new_v_count or old_f_count != new_f_count:
                print(f"    {disc_id}: size mismatch (old {old_v_count}v/{old_f_count}f vs new {new_v_count}v/{new_f_count}f)")
                size_ok = False
        
        if not size_ok:
            print(f"  ERROR: New discs have different vertex/face counts. Cannot replace in-place.")
            print(f"  Would need to rebuild entire mesh, but keeping old discs for stability.")
            continue
        
        # Replace disc geometry in place
        print(f"  Replacing disc geometry in-place...")
        replace_count = 0
        
        for disc_id in lumbar_disc_ids:
            v_start, v_end = disc_vertex_ranges[disc_id]
            f_start, f_end = disc_face_ranges[disc_id]
            
            new_verts, new_faces = new_discs[disc_id]
            
            # Replace vertices
            verts[v_start:v_end] = new_verts
            
            # Replace faces (they need to be remapped relative to vertex offset)
            faces[f_start:f_end] = new_faces + v_start
            
            replace_count += 1
        
        print(f"  Replaced {replace_count} lumbar discs")
        
        # Write updated mesh and manifest
        write_mesh_binary(subject_dir, verts, faces)
        save_manifest(subject, manifest)
        
        print(f"  Wrote mesh: {len(verts)} vertices, {len(faces)} faces\n")
    
    print("Disc replacement complete. Now verify continuity:")
    print("  python3 scripts/verify_vertebral_continuity.py analyze")
    
    return 0


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("command", choices=["replace"], help="Command to run")
    
    args = parser.parse_args()
    
    if args.command == "replace":
        return cmd_replace(args)
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
