#!/usr/bin/env python3
"""Q155: append one finalized refine_transfer_photo_watershed.py output directory's structures
into another, in place -- used to combine the female forearm and female hand photo-watershed
refinements (two separate --volume/--labels/--mapping runs, since the hand has no shared
two-bone anchor with the forearm) into the single shipped subject `xfer_zan2vhf_limb_photo` this
task's brief names. Refuses on any atlas_id collision between the two (the forearm/hand id sets
are disjoint by construction, so a collision would mean something is wrong, not something to
silently overwrite).

    python3 scripts/transfer/q155_merge_into.py build/vh/xfer_zan2vhf_limb_photo build/vh/_q155_vhf_hand_photo
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np


def main() -> int:
    dst_dir, src_dir = Path(sys.argv[1]), Path(sys.argv[2])
    dman = json.loads((dst_dir / "manifest.json").read_text())
    sman = json.loads((src_dir / "manifest.json").read_text())

    dst_ids = {s["atlas_id"] for s in dman["structures"]}
    src_ids = {s["atlas_id"] for s in sman["structures"]}
    collide = dst_ids & src_ids
    if collide:
        raise SystemExit(f"refusing to merge: atlas_id collision {sorted(collide)}")

    dV = np.fromfile(dst_dir / "vertices.f32", np.float32).reshape(-1, 3)
    dF = np.fromfile(dst_dir / "faces.u32", np.uint32).reshape(-1, 3)
    sV = np.fromfile(src_dir / "vertices.f32", np.float32).reshape(-1, 3)
    sF = np.fromfile(src_dir / "faces.u32", np.uint32).reshape(-1, 3)

    voff = len(dV)
    foff = len(dF)
    new_structs = []
    for s in sman["structures"]:
        s2 = dict(s)
        s2["vertex_offset"] = s["vertex_offset"] + voff
        s2["face_offset"] = s["face_offset"] + foff
        new_structs.append(s2)

    V = np.concatenate([dV, sV]) if len(sV) else dV
    F = np.concatenate([dF, sF + voff]) if len(sF) else dF
    V.astype(np.float32).tofile(dst_dir / "vertices.f32")
    F.astype(np.uint32).tofile(dst_dir / "faces.u32")

    dman["structures"] = dman["structures"] + new_structs
    dman["vertex_count"] = int(len(V))
    dman["triangle_count"] = int(len(F))
    dman["bbox_min_mm"] = [round(float(x), 4) for x in V.min(axis=0)] if len(V) else None
    dman["bbox_max_mm"] = [round(float(x), 4) for x in V.max(axis=0)] if len(V) else None
    d_attr = dman.get("attribution") or []
    if isinstance(d_attr, str):
        d_attr = [d_attr]
    s_attr = sman.get("attribution") or []
    if isinstance(s_attr, str):
        s_attr = [s_attr]
    dman["attribution"] = d_attr + [a for a in s_attr if a not in d_attr]
    (dst_dir / "manifest.json").write_text(json.dumps(dman, indent=1))
    print(f"merged {len(new_structs)} structures from {src_dir} into {dst_dir}: "
          f"{[s['atlas_id'] for s in new_structs]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
