#!/usr/bin/env python3
"""Q115 follow-up: for the UNCLEAR-because-no-voxel-source male structures
(geometry "recovered from the published male viewer (Version 25)" -- the DU
lower-limb STLs this project cannot re-download, per PROJECT_STATE), there is
still something to measure even without a label volume: whether each STORED
PIECE is itself a single connected component in the recovered mesh (before
export_viewer_bundle.py's own second decimation pass), and whether that
second decimation makes things meaningfully worse.

This tells apart two different situations this triage's volume-only method
cannot see:
  - MULTI_PIECE_INHERENT: every stored piece is already ~1 connected
    component on its own; the group's main_frac is capped below 1.0 purely
    by (id,side) bundling >1 legitimate anatomical piece under one id --
    the same modeling ceiling Q113 documented for sciatic_n, not a defect
    this session's own pipeline introduced or can fix.
  - SECOND_DECIMATION_ARTIFACT: pieces are NOT individually continuous
    even in the recovered pre-second-decimation mesh, or the shipped
    (post-export_viewer_bundle.py) main_frac is markedly worse than the
    recovered mesh's own -- i.e. THIS project's re-decimation step is an
    additional, potentially fixable, destroyer on top of whatever the
    original published bundle already was.

Read-only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

sys.path.insert(0, str(REPO_ROOT / "scripts"))
from audit_full_continuity_q112 import analyze_group  # noqa: E402

VHM_BOTH = REPO_ROOT / "build" / "vh" / "vhm_both"


def load_vhm_both():
    manifest = json.loads((VHM_BOTH / "manifest.json").read_text())
    faces_all = np.fromfile(VHM_BOTH / "faces.u32", dtype="<u4").reshape(-1, 3)
    return manifest, faces_all


def piece_faces_local(struct_rec, faces_all):
    fo, tc, vo = struct_rec["face_offset"], struct_rec["triangle_count"], struct_rec["vertex_offset"]
    faces_global = faces_all[fo:fo + tc]
    return (faces_global - vo).astype(np.uint32)


def main() -> int:
    triage = json.loads((REPO_ROOT / "data" / "derived" / "Q115_triage.json").read_text())
    audit = json.loads((REPO_ROOT / "data" / "derived" / "Q112_full_continuity_audit.json").read_text())
    manifest, faces_all = load_vhm_both()

    recovered_targets = []
    for key, r in triage["results"].items():
        if r["classification"] != "UNCLEAR":
            continue
        reason = r.get("reason", "")
        if "recovered from the published" not in reason:
            continue
        recovered_targets.append((key, r))

    print(f"{len(recovered_targets)} UNCLEAR/recovered-geometry targets to re-check at the mesh level")

    out = {}
    for key, r in recovered_targets:
        atlas_id, side = r["id"], r["side"]
        side_norm = None if side in (None, "none") else side
        recs = [s for s in manifest["structures"]
                if s["atlas_id"] == atlas_id and s.get("side") == side_norm]
        if not recs:
            out[key] = {"status": "no_match_in_vhm_both"}
            continue

        per_piece = []
        for rec in recs:
            faces_local = piece_faces_local(rec, faces_all)
            group_result = analyze_group([(rec, faces_local, rec["vertex_count"])])
            per_piece.append({
                "vertex_count": rec["vertex_count"],
                "triangle_count": rec["triangle_count"],
                "tris_full_at_source": rec.get("tris_full_at_source"),
                "piece_main_frac": group_result["main_frac"],
                "piece_n_components": group_result["n_components"],
            })

        combined = analyze_group([
            (rec, piece_faces_local(rec, faces_all), rec["vertex_count"]) for rec in recs
        ])

        body, group_key = key.split("|", 1)
        shipped_main_frac = audit["bodies"][body]["structures"][group_key]["main_frac"]

        all_pieces_solid = all(p["piece_main_frac"] >= 0.99 for p in per_piece)
        classification = ("MULTI_PIECE_INHERENT" if (len(recs) > 1 and all_pieces_solid)
                          else "SECOND_DECIMATION_OR_SOURCE_ISSUE")
        out[key] = {
            "n_pieces_in_recovered_mesh": len(recs),
            "per_piece": per_piece,
            "recovered_mesh_combined_main_frac": combined["main_frac"],
            "shipped_main_frac": shipped_main_frac,
            "classification": classification,
        }
        print(f"{key}: n_pieces={len(recs)} piece_main_fracs="
              f"{[round(p['piece_main_frac'],3) for p in per_piece]} "
              f"recovered_combined={combined['main_frac']:.3f} "
              f"shipped={shipped_main_frac:.3f} -> {classification}")

    out_path = REPO_ROOT / "data" / "derived" / "Q115_recovered_pieces_check.json"
    out = {"source": "Q115 follow-up: mesh-level re-check of the UNCLEAR (no-voxel-source) male "
                      "structures recovered from the published viewer bundle -- distinguishes "
                      "genuinely multi-piece anatomy (each stored piece already main_frac 1.0) from "
                      "a real defect (scripts/triage_recovered_pieces_q115.py)",
           **out}
    out_path.write_text(json.dumps(out, indent=2))
    print(f"\nWrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
