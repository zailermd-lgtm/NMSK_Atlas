#!/usr/bin/env python3
"""Sample a region's generated geometry (muscle fiber fields today; nerve/
vessel centerlines follow the same resample_polyline() primitive) at the
atlas's 1mm target resolution and write a flat point cloud.

Usage:
    python scripts/generate_point_cloud.py --muscles deltoid_r,biceps_brachii_r --out out.npy
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from engine import fiber_field  # noqa: E402


def _find_muscle(muscle_id: str) -> dict | None:
    for path in (REPO_ROOT / "data" / "muscles").rglob("*.json"):
        if path.name == "muscle_index.json":
            continue
        payload = json.loads(path.read_text())
        for m in (payload if isinstance(payload, list) else [payload]):
            if m.get("id") == muscle_id:
                return m
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--muscles", required=True, help="comma-separated muscle ids")
    ap.add_argument("--out", required=True)
    ap.add_argument("--resolution-mm", type=float, default=1.0)
    args = ap.parse_args()

    all_points = []
    all_tags = []  # (muscle_id, compartment_id) per point, for downstream filtering
    for mid in args.muscles.split(","):
        m = _find_muscle(mid.strip())
        if m is None:
            print(f"warning: muscle '{mid}' not found in data/muscles/, skipping", file=sys.stderr)
            continue
        att = m["attachments"]
        # NOTE: this CLI illustrates the sampling primitive using a
        # placeholder straight-line origin/insertion offset; a full run
        # resolves real anchor coordinates via engine/rig.py against a
        # populated data/rig/anchors.json for this muscle.
        origin_pt = np.zeros(3)
        insertion_pt = np.array([0.0, -200.0, 0.0])
        for comp in m.get("functional_compartments", []):
            arch = comp["fiber_architecture"]
            seed_region = np.array(comp.get("fiber_field_seed_region_local_mm") or [origin_pt])
            fascicles = fiber_field.generate_compartment_fibers(
                compartment_id=comp["id"],
                architecture_type=arch["architecture_type"],
                pennation_deg=arch.get("pennation_deg", 0.0),
                seed_region_local_mm=seed_region,
                origin_anchor_local_mm=origin_pt,
                insertion_anchor_local_mm=insertion_pt,
                resolution_mm=args.resolution_mm,
            )
            for fsc in fascicles:
                all_points.append(fsc.points_mm)
                all_tags.extend([(mid, comp["id"])] * len(fsc.points_mm))

    if not all_points:
        print("no points generated", file=sys.stderr)
        sys.exit(1)

    cloud = np.concatenate(all_points, axis=0)
    np.save(args.out, cloud)
    tags_path = str(args.out).rsplit(".", 1)[0] + "_tags.json"
    with open(tags_path, "w") as f:
        json.dump(all_tags, f)
    print(f"wrote {len(cloud)} points ({args.resolution_mm}mm resolution) to {args.out}")
    print(f"wrote per-point (muscle_id, compartment_id) tags to {tags_path}")


if __name__ == "__main__":
    main()
