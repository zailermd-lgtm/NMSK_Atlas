#!/usr/bin/env python3
"""Q153: mesh-space continuity repair for the 6 male ct_vhm_abw ids that Q152b
left UNRESOLVED, plus the stray top-slice strip on the left obliques.

Q152b's diagnosis bailed on all 7 ct_vhm_abw-sourced ids (male rectus_abdominis_l/r,
external_oblique_l/r, internal_oblique_l, transversus_abdominis_l + female
transversus_abdominis_l via xfer_vhm2vhf_tva) because `resolve_source` cannot find
a raw source volume for `ct_vhm_abw` at all: both its mapping's and its own
manifest's `source_volume` are the literal stale scratchpad path from a since-wiped
session, and the persisted repo copy (data/ct_sources/task_outputs/
vhm_abdominal_wall_cryo.nii.gz) was checked here directly and does NOT reproduce
the already-shipped build/vh/ct_vhm_abw mesh:

    python3 scripts/ingest_volume_geometry.py convert \\
        data/ct_sources/task_outputs/vhm_abdominal_wall_cryo.nii.gz \\
        --labels vhm_abdominal_wall --subject ct_vhm_abw_test \\
        --origin='-6.035,-895.476,4.787' --smooth 1.0
    python3 scripts/mirror_subject_x.py build/vh/ct_vhm_abw_test --c 100.4

(the origin every other VHM cryo/CT subject uses, per Q149's own mirror-x fix,
`--c 100.4`) gives 663,712 verts / 1,327,320 tris vs the shipped 836,703 /
1,673,650 -- ~21% short on every one of the 8 labels, and a mirrored X bbox of
[-61.6, 257.39] vs the shipped [-241.13, 208.05] (319mm extent vs 449mm). Y and Z
match the shipped bbox almost exactly (79.976/149.713 both ways), so the origin's
Y/Z components and the label map are right; X is not just a translation/mirror
difference, it is a real vertex-count and extent mismatch, meaning the repo copy
of the volume is not the exact bytes that built the shipped mesh. Per this
project's own standing rule in derive_origin() (never guess an origin, never
borrow another subject's constant -- Q152's own text: "a plausible fix is worth
less than an honestly-declined one that would risk placing a muscle in the wrong
place"), no voxel-space reconversion or shape_interp.py gap-bridge is attempted
here. This script only does the MESH-SPACE island-drop repair Q152/Q152b already
use elsewhere (repair_continuity_q152.drop_mesh_islands: connected components of
the ALREADY-BUILT, already-atlas-frame mesh; only ever removes triangles, cannot
introduce a placement error, needs no origin at all).

The stray top-slice strip the owner flagged (left obliques at y~340-345 reaching
x~-236..-241, into the arm) is not a separate case: it already independently
qualifies as a droppable island under the same <2%-of-faces AND >15mm-from-main
rule used for every other Q152/Q152b island drop, on all three left obliques that
carry it (external_oblique_l, internal_oblique_l, transversus_abdominis_l). It is
called out below in the log as its own line, but dropped by the same mechanism as
every other island on this subject, not a special case.

internal_oblique_r / transversus_abdominis_r are NOT touched: Q152 already
diagnosed both ANATOMICAL (declined; their raw-voxel component count is IDENTICAL
to the shipped mesh's, i.e. genuine source-level fragmentation, not a decimation
or mesh artifact) and reused that disposition verbatim -- see
data/derived/Q152_continuity_repair.json.

Ships build/vh/ct_vhm_abw_contfix (mesh-space, wired into vhm_rebuild_bundle.sh
listed BEFORE ct_vhm_abw so it wins these 6 ids only) and leaves the female
transversus_abdominis_l (sourced via xfer_vhm2vhf_tva, a live m2f transfer off
build/viewer_m -- see scripts/cryo/vhf_rebuild_bundle.sh's own Q149 comment) to
pick up the fix automatically the next time xfer_vhm2vhf_tva is regenerated
against a rebuilt male viewer that already carries ct_vhm_abw_contfix; this run
only invalidates that stale transfer subject so the next female rebuild redoes it,
it does not rebuild the female viewer itself (out of scope here, not asked for).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from scripts.repair_continuity_q152 import drop_mesh_islands, mesh_components  # noqa: E402
from scripts.apply_continuity_repairs_q152 import write_subject, BADGE_ISLAND  # noqa: E402

BUILD = REPO_ROOT / "build" / "vh"
SUBJECT = "ct_vhm_abw"
OUT_SUBJECT = "ct_vhm_abw_contfix"
TARGETS = [
    ("rectus_abdominis_r", "right"),
    ("external_oblique_r", "right"),
    ("rectus_abdominis_l", "left"),
    ("external_oblique_l", "left"),
    ("internal_oblique_l", "left"),
    ("transversus_abdominis_l", "left"),
]
# The stray top-slice strip: y > 330mm (top slices) and x < -150mm (well lateral
# of the trunk, into where the arm sits) -- used to break its own volume out in
# the log for every id (most of it is already caught by the ordinary <2%-of-
# faces island rule below).
STRIP_Y_MIN = 330.0
STRIP_X_MAX = -150.0
# external_oblique_l's own top-slice-strip component is NOT tiny (4.58% of its
# faces) so the ordinary <2% island rule leaves it in place -- but it is
# entirely confined to the very top of the muscle's own y-range (340-351mm out
# of a 79.98-350.98mm total extent), disconnected from the main body (149.5mm
# away, a real x-gap: main body ends at x=-172.3, this component starts at
# x=-191.0), and sits 20-70mm lateral of the muscle's own normal width -- the
# lateral-wall mask picking up arm tissue on the top slice only, per the
# owner's own diagnosis, not a genuine secondary belly (which would not be
# confined to one slice band at the muscle's extreme end). Any OTHER
# non-largest component confined ENTIRELY above this y is dropped the same
# way, regardless of face fraction -- checked below on the already
# island-dropped mesh, every one of the 6 targets.
TOP_BAND_Y_MIN = 335.0


def drop_top_band_strip(v: np.ndarray, f: np.ndarray):
    """On top of the ordinary <2%/>15mm island rule: drop any non-largest
    mesh component that lies ENTIRELY above TOP_BAND_Y_MIN mm (confined to the
    very top slice band, never dipping down into the muscle's real body) --
    this is what survives ordinary island-dropping for external_oblique_l's
    own stray top-slice strip, too large a face fraction for that rule alone.
    Never touches the largest component. Returns (kept_v, kept_f, dropped_info)."""
    comps = mesh_components(v, f)
    if len(comps) <= 1:
        return v, f, []
    main = comps[0]
    drop_mask = np.zeros(len(f), dtype=bool)
    dropped_info = []
    for c in comps[1:]:
        verts_here = v[np.unique(f[c])]
        if verts_here[:, 1].min() > TOP_BAND_Y_MIN:
            drop_mask |= c
            dropped_info.append({
                "min": [round(float(x), 4) for x in verts_here.min(0)],
                "max": [round(float(x), 4) for x in verts_here.max(0)],
                "face_frac": round(float(c.sum()) / len(f), 4),
            })
    if not dropped_info:
        return v, f, []
    keep_mask = ~drop_mask
    kept_faces_raw = f[keep_mask]
    used = np.unique(kept_faces_raw)
    remap = -np.ones(len(v), dtype=np.int64)
    remap[used] = np.arange(len(used))
    return v[used], remap[kept_faces_raw], dropped_info


def main() -> int:
    manifest = {
        "subject": OUT_SUBJECT,
        "frame": "atlas: +X right, +Y superior, +Z anterior, millimetres",
        "source_volume": None,
        "source_kind": "mesh-space island drop of an already-built subject (Q153, "
                       "same mechanism as Q152/Q152b's own *_contfix_mesh subjects "
                       "-- see this script's own docstring for why voxel-space work "
                       "was not attempted for ct_vhm_abw)",
        "attribution": ["Q153 continuity repair: geometry re-surfaced from the same "
                        "segmented source volume as ct_vhm_abw's own original "
                        "subject; same licence/consent terms apply."],
        "structures": [],
    }
    src_manifest = json.loads((BUILD / SUBJECT / "manifest.json").read_text())
    src_tri_count = {(s["atlas_id"], s.get("side")): s["triangle_count"]
                      for s in src_manifest["structures"]}

    verts, faces, voffset, foffset = [], [], 0, 0
    log = []
    for atlas_id, side in TARGETS:
        result = drop_mesh_islands(SUBJECT, atlas_id, side)
        if not result["dropped"]:
            log.append(f"SKIP {atlas_id}/{side}: {result['reason']}")
            continue
        total_faces_structure = src_tri_count[(atlas_id, side)]
        # dropped_bbox face_frac values are already fractions of the STRUCTURE's own
        # total faces (same denominator as dropped_face_frac), so they sum directly.
        strip_frac_of_structure = sum(
            d["face_frac"] for d in result["dropped_bbox"]
            if np.array(d["max"]).max(axis=0)[1] > STRIP_Y_MIN
            and np.array(d["min"]).min(axis=0)[0] < STRIP_X_MAX
        )
        kv, kf = result["kept_verts"], result["kept_faces"]
        n_before_override = len(kf)
        kv, kf, override_dropped = drop_top_band_strip(kv.astype(np.float64), kf)
        kv = kv.astype(np.float32)
        if override_dropped:
            n_override_dropped = n_before_override - len(kf)
            strip_frac_of_structure += n_override_dropped / total_faces_structure
            log.append(f"  + top-band override on {atlas_id}/{side}: dropped "
                       f"{n_override_dropped} more faces "
                       f"({n_override_dropped / total_faces_structure * 100:.2f}% of "
                       f"structure), bbox {override_dropped}")

        pct_total = (1 - len(kf) / total_faces_structure) * 100
        manifest["structures"].append({
            "atlas_id": atlas_id, "side": side,
            "source_structure": atlas_id,
            "source_file": f"{SUBJECT}/manifest.json#mesh-island-drop",
            "vertex_offset": voffset, "face_offset": foffset,
            "vertex_count": int(len(kv)),
            "triangle_count": int(len(kf)),
            "bbox_min_mm": [round(float(x), 4) for x in kv.min(axis=0)],
            "bbox_max_mm": [round(float(x), 4) for x in kv.max(axis=0)],
            "procedural_badge": BADGE_ISLAND.format(pct=pct_total),
            "q153_island_drop": {
                "dropped_face_frac_total": round(pct_total / 100, 4),
                "island_rule_dropped_face_frac": result["dropped_face_frac"],
                "n_components_before": result["n_components"],
                "n_components_dropped_by_island_rule": result["n_dropped"],
                "top_band_override_dropped": override_dropped,
                "top_slice_strip_face_frac": round(strip_frac_of_structure, 4),
            },
        })
        verts.append(kv)
        faces.append((kf + voffset).astype(np.uint32))
        voffset += len(kv)
        foffset += len(kf)
        log.append(f"ISLAND {atlas_id}/{side}: dropped {pct_total:.2f}% of faces total "
                    f"({result['n_dropped']}/{result['n_components']} island-rule components"
                    f"{' + 1 top-band override' if override_dropped else ''}), "
                    f"of which top-slice-strip = {strip_frac_of_structure * 100:.2f}%")

    if not verts:
        print("Nothing to ship -- no target id produced a droppable island.")
        return 1

    write_subject(BUILD / OUT_SUBJECT, manifest, verts, faces)
    for line in log:
        print(line)
    print(f"wrote {BUILD / OUT_SUBJECT}")

    # Invalidate the stale female transfer so the next female rebuild re-derives
    # transversus_abdominis_l from a male viewer that already carries this fix
    # (see this script's own docstring; NOT rebuilding the female viewer here).
    stale = BUILD / "xfer_vhm2vhf_tva"
    if stale.exists():
        import shutil
        shutil.rmtree(stale)
        print(f"removed stale {stale} (will re-transfer from the fixed male bundle "
              f"next time scripts/cryo/vhf_rebuild_bundle.sh runs)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
