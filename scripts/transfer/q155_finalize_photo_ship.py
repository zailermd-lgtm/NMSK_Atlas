#!/usr/bin/env python3
"""Q155: finalize a refine_transfer_photo_watershed.py shipping-mode output directory before it
is wired into a viewer rebuild.

Two things the raw shipping-mode `--out` does NOT do on its own (by design -- that script's own
badge text only fires under `--holdout`, and it never checks continuity at all):

1. DROP any refined structure whose main_frac (Q112's own face-adjacency, vertex-based metric --
   see scripts/clean_stray_mesh_islands.py's `analyze_piece`) is below --min-main-frac (default
   0.98, this task's own ship gate). Dropped ids are removed from this subject entirely (vertices/
   faces/manifest rewritten with consistent offsets) so a later, lower-priority subject in the
   bundle's --subject list (here: the Q147 whole-limb transfer itself) supplies them unrefined
   instead of a fragmented refined mesh silently shipping.

2. STAMP every structure that survives with the owner-approved (2026-09-25) ship badge, carrying
   this segment's own honest leave-one-out validation numbers (median/max mm), read directly from
   the caller's --median/--max args -- never invented here.

    python3 scripts/transfer/q155_finalize_photo_ship.py build/vh/xfer_zan2vhm_limb_photo \
        --median 19.9 --max 25.8 --report data/derived/Q155_finalize_male_forearm.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.clean_stray_mesh_islands import analyze_piece  # noqa: E402

MIN_MAIN_FRAC = 0.98
BADGE_METHOD = ("Z-Anatomy (CC BY-SA 4.0; Z-Anatomy / BodyParts3D) shape refined to this "
                "specimen's cryosection photographs (watershed on tissue boundaries)")


def badge(median_mm: float, max_mm: float) -> str:
    return (f"{BADGE_METHOD}; leave-one-out validation median {median_mm} mm, max {max_mm} mm "
            f"— below atlas target accuracy")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("subject_dir")
    ap.add_argument("--median", type=float, required=True, help="this segment's leave-one-out median centroid error, mm")
    ap.add_argument("--max", type=float, required=True, dest="max_mm", help="this segment's leave-one-out max centroid error, mm")
    ap.add_argument("--min-main-frac", type=float, default=MIN_MAIN_FRAC)
    ap.add_argument("--report", default=None)
    a = ap.parse_args()

    d = Path(a.subject_dir)
    man = json.loads((d / "manifest.json").read_text())
    V = np.fromfile(d / "vertices.f32", np.float32).reshape(-1, 3)
    F = np.fromfile(d / "faces.u32", np.uint32).reshape(-1, 3)

    kept, dropped = [], {}
    new_V, new_F = [], []
    voff = 0
    badge_text = badge(a.median, a.max_mm)
    for s in man["structures"]:
        v = V[s["vertex_offset"]:s["vertex_offset"] + s["vertex_count"]]
        f = F[s["face_offset"]:s["face_offset"] + s["triangle_count"]].astype(np.int64) - s["vertex_offset"]
        info = analyze_piece(v, f)
        main_frac = float(info["main_frac"]) if info is not None else 1.0
        if main_frac < a.min_main_frac:
            dropped[s["atlas_id"]] = round(main_frac, 4)
            continue
        s2 = dict(s)
        s2["vertex_offset"] = voff
        s2["face_offset"] = sum(len(x) for x in new_F)
        s2["procedural_badge"] = badge_text
        s2["main_frac_q112"] = round(main_frac, 4)
        new_V.append(v.astype(np.float32))
        new_F.append((f + voff).astype(np.uint32))
        voff += len(v)
        kept.append(s2)

    Vc = np.concatenate(new_V) if new_V else np.zeros((0, 3), np.float32)
    Fc = np.concatenate(new_F) if new_F else np.zeros((0, 3), np.uint32)
    Vc.tofile(d / "vertices.f32")
    Fc.tofile(d / "faces.u32")
    man["structures"] = kept
    man["vertex_count"] = int(len(Vc))
    man["triangle_count"] = int(len(Fc))
    man["bbox_min_mm"] = [round(float(x), 4) for x in Vc.min(axis=0)] if len(Vc) else None
    man["bbox_max_mm"] = [round(float(x), 4) for x in Vc.max(axis=0)] if len(Vc) else None
    man["attribution"] = [badge_text]
    (d / "manifest.json").write_text(json.dumps(man, indent=1))

    result = {"source": ("Q155 finalize log: scripts/transfer/q155_finalize_photo_ship.py, "
                          "applying the Q112 main_frac ship gate and the owner-approved "
                          "2026-09-25 ship badge to a refine_transfer_photo_watershed.py "
                          "shipping-mode output directory."),
              "subject": d.name, "shipped": [s["atlas_id"] for s in kept],
              "dropped_low_main_frac": dropped, "badge": badge_text,
              "min_main_frac": a.min_main_frac}
    print(json.dumps(result, indent=1))
    if a.report:
        Path(a.report).write_text(json.dumps(result, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
