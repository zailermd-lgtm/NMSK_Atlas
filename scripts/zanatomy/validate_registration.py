"""Q142 phase 2 VALIDATION GATE: measure a Z-Anatomy registration against this project's
own real-data mesh for the same atlas_id, before any Z-Anatomy structure ships.

For every id present in both a cross_subject_transfer.py --direction zan2f/zan2m output
(the registered Z-Anatomy geometry) and the target body's own PUBLISHED bundle (its real,
non-transferred mesh for that id), reports:

  - centroid_dist_mm: distance between the two centroids
  - real_vol_cm3 / zan_vol_cm3 / vol_ratio: signed-volume comparison (scripts/transfer/
    bundle_io.py's own mesh_volume_cm3, unchanged)
  - dice / iou: voxel overlap at a 2 mm grid (trimesh's own fill-the-surface voxeliser,
    not a per-point ray cast -- ~1000x faster and exact at this resolution for a closed
    mesh; the same metric a segmentation-vs-ground-truth comparison would use)

This is read-only diagnostics: it does not touch any bundle, entity record or the
transfer's own output. See PROJECT_STATE.md's Q142 entry for the resulting table, the
acceptance bar it was measured against, and the shipping decision.

    python3 scripts/zanatomy/validate_registration.py --target build/viewer_f \\
        --registered build/vh/zan_vhf_val --out data/derived/Q142_validation_x.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import trimesh

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.transfer.bundle_io import read_bundle_dir, meshes_by_id, mesh_volume_cm3  # noqa: E402

PITCH_MM = 2.0


def load_transfer_manifest(d: Path):
    d = Path(d)
    man = json.loads((d / "manifest.json").read_text())
    verts = np.fromfile(d / "vertices.f32", dtype=np.float32).reshape(-1, 3)
    faces = np.fromfile(d / "faces.u32", dtype=np.uint32).reshape(-1, 3)
    out = {}
    for s in man["structures"]:
        v = verts[s["vertex_offset"]:s["vertex_offset"] + s["vertex_count"]]
        f = faces[s["face_offset"]:s["face_offset"] + s["triangle_count"]] - s["vertex_offset"]
        out[s["atlas_id"]] = (v.astype(np.float64), f)
    return out


def voxel_set(v, f, pitch=PITCH_MM):
    m = trimesh.Trimesh(v, f, process=False)
    vox = m.voxelized(pitch=pitch).fill()
    idx = np.round(vox.points / pitch).astype(np.int64)
    return set(map(tuple, idx))


def compare(v1, f1, v2, f2):
    c1, c2 = v1.mean(0), v2.mean(0)
    vol1, vol2 = mesh_volume_cm3(v1, f1), mesh_volume_cm3(v2, f2)
    s1, s2 = voxel_set(v1, f1), voxel_set(v2, f2)
    inter, union = len(s1 & s2), len(s1 | s2)
    return {
        "centroid_dist_mm": round(float(np.linalg.norm(c1 - c2)), 1),
        "real_vol_cm3": round(vol1, 1), "zan_vol_cm3": round(vol2, 1),
        "vol_ratio_zan_over_real": round(vol2 / vol1, 3) if vol1 else None,
        "dice": round(2 * inter / max(len(s1) + len(s2), 1), 3),
        "iou": round(inter / max(union, 1), 3),
        "real_extent_mm": round(float(np.linalg.norm(v1.max(0) - v1.min(0))), 1),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--target", required=True, help="the body's own published bundle dir (build/viewer_f etc.)")
    ap.add_argument("--registered", required=True, help="cross_subject_transfer.py zan2f/zan2m output dir")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()

    bt, blobt = read_bundle_dir(a.target)
    target = meshes_by_id(bt, blobt)  # NOT own_only: real subjects only are selected explicitly below
    registered = load_transfer_manifest(a.registered)

    rows = []
    for aid, (v2, f2) in sorted(registered.items()):
        real = target.get(aid)
        if real is None or str(real["subject"]).startswith(("xfer_", "zanatomy", "zan_")):
            rows.append({"id": aid, "skipped": "no real (non-transferred) mesh for this id on the target"})
            continue
        row = {"id": aid, "real_subject": real["subject"]}
        row.update(compare(real["v"].astype(np.float64), real["f"], v2, f2))
        rows.append(row)
        print(row)

    out = {"source": ("Q142 (2026-09-23) validation gate: centroid distance, signed-volume ratio and 2 mm-voxel "
                       "Dice/IoU between a scripts/transfer/cross_subject_transfer.py --direction zan2f/zan2m "
                       "registration of Z-Anatomy (CC BY-SA 4.0) geometry and this project's own real (non-"
                       "transferred) mesh for the same atlas_id, via scripts/zanatomy/validate_registration.py. "
                       "Diagnostics only -- read-only, no bundle/entity record touched. See PROJECT_STATE.md's "
                       "Q142 entry for the acceptance bar and shipping decision this table was measured against."),
           "target": a.target, "registered": a.registered, "pitch_mm": PITCH_MM, "rows": rows}
    if a.out:
        Path(a.out).write_text(json.dumps(out, indent=1))
        print(f"wrote {a.out}")


if __name__ == "__main__":
    main()
