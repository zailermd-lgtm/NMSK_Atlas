#!/usr/bin/env python3
"""Mirror an ingested subject's meshes about the sagittal plane x = c / 2 (x' = c - x).

Q149: build/vh/ct_vhm_abw came from data/ct_sources/task_outputs/vhm_abdominal_wall_cryo.nii.gz,
whose voxels are in cryosection column order (column index increases toward subject right)
but whose affine carries the CT's x direction (-1 mm/col). The surfaced meshes were therefore
mirrored and offset: the linea alba sat at x ~ +105 mm instead of on the spine. The volume's
left/right LABELS are right (scripts/cryo/abdominal_wall_from_cryo.py assigns them in cryo
orientation), so the fix is a pure geometric mirror, not a label swap. c is chosen so the
rule's own midline (the vertebral-body column, x ~ 105.4 in the bad frame) lands on the male's
lumbar spine (mean x -5.0 mm over y 110-300 in the shipped bundle): c = 105.4 - 5.0 = 100.4.

Idempotent: the manifest records `mirror_x_fix`; a second run is a no-op.
Mirroring reverses triangle orientation, so each face's winding is flipped too.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


def mirror(subject_dir: Path, c: float, note: str) -> bool:
    man_p = subject_dir / "manifest.json"
    man = json.loads(man_p.read_text())
    if man.get("mirror_x_fix"):
        return False
    V = np.fromfile(subject_dir / "vertices.f32", np.float32).reshape(-1, 3)
    F = np.fromfile(subject_dir / "faces.u32", np.uint32).reshape(-1, 3)
    V[:, 0] = c - V[:, 0]
    F = F[:, [0, 2, 1]]
    V.astype(np.float32).tofile(subject_dir / "vertices.f32")
    np.ascontiguousarray(F, dtype=np.uint32).tofile(subject_dir / "faces.u32")
    for st in man["structures"]:
        v = V[st["vertex_offset"]:st["vertex_offset"] + st["vertex_count"]]
        st["bbox_min_mm"] = [round(float(x), 4) for x in v.min(0)]
        st["bbox_max_mm"] = [round(float(x), 4) for x in v.max(0)]
    man["bbox_min_mm"] = [round(float(x), 4) for x in V.min(0)]
    man["bbox_max_mm"] = [round(float(x), 4) for x in V.max(0)]
    man["mirror_x_fix"] = {"x_new": f"{c} - x", "note": note}
    man_p.write_text(json.dumps(man, indent=1))
    return True


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("subject_dir", type=Path)
    ap.add_argument("--c", type=float, required=True)
    ap.add_argument("--note", default="")
    a = ap.parse_args()
    print("mirrored" if mirror(a.subject_dir, a.c, a.note) else "already fixed, no-op", a.subject_dir)


if __name__ == "__main__":
    main()
