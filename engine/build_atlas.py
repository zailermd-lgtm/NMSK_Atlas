#!/usr/bin/env python3
"""CLI: build 1mm-resolution procedural geometry for a muscle (or all
muscles in a data file) and run the validation suite.

Usage:
    python -m engine.build_atlas --muscle deltoid_r
    python -m engine.build_atlas --validate-only
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from . import fiber_field
from . import validators

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_bones() -> dict:
    path = REPO_ROOT / "data" / "skeleton" / "bones.json"
    return {b["id"]: b for b in json.loads(path.read_text())} if path.exists() else {}


def _find_muscle(muscle_id: str) -> dict | None:
    for path in (REPO_ROOT / "data" / "muscles").rglob("*.json"):
        if path.name == "muscle_index.json":
            continue
        payload = json.loads(path.read_text())
        entities = payload if isinstance(payload, list) else [payload]
        for m in entities:
            if m.get("id") == muscle_id:
                return m
    return None


def build_muscle(muscle_id: str) -> dict:
    m = _find_muscle(muscle_id)
    if m is None:
        raise SystemExit(f"muscle '{muscle_id}' not found in data/muscles/")
    att = m["attachments"]
    origin_pt = np.zeros(3)  # placeholder: resolved via rig.py + bones' landmark table in a full run
    insertion_pt = np.array([0.0, -300.0, 0.0])  # illustrative offset; real run uses landmark coordinates
    report = {"muscle": muscle_id, "compartments": []}
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
            nmj_fraction=(comp.get("neuromuscular_junction_zone", {}) or {}).get("position_fraction_along_fascicle", 0.5),
            resolution_mm=1.0,
        )
        report["compartments"].append({
            "id": comp["id"],
            "n_fascicles": len(fascicles),
            "points_per_fascicle_mean": float(np.mean([len(f.points_mm) for f in fascicles])) if fascicles else 0,
        })
    return report


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--muscle", help="muscle id to generate fiber geometry for")
    ap.add_argument("--validate-only", action="store_true")
    args = ap.parse_args()

    if not args.validate_only and args.muscle:
        report = build_muscle(args.muscle)
        print(json.dumps(report, indent=2))

    print("\n--- Validation report ---")
    results = validators.run_all()
    total_problems = sum(len(v) for v in results.values())
    for check, problems in results.items():
        status = "PASS" if not problems else f"FAIL ({len(problems)})"
        print(f"[{status}] {check}")
        for p in problems[:20]:
            print(f"    - {p}")
    raise SystemExit(1 if total_problems else 0)


if __name__ == "__main__":
    main()
