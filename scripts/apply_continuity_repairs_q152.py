#!/usr/bin/env python3
"""Q152 apply phase: turn data/derived/Q152_continuity_repair.json's diagnosis into
real, committed geometry fixes.

Three mechanisms, matched to the diagnosis's own causes:

  DROP_ISLAND (and the island half of MIXED_ISLAND_AND_ANATOMICAL) -- applied in
      MESH space, directly on the already-built, already atlas-frame
      build/vh/<subject> geometry (mesh_components/drop_mesh_islands in
      scripts/repair_continuity_q152.py). No affine/origin re-derivation needed
      at all -- this can only REMOVE already-correctly-placed triangles, never
      move anything, so it carries none of the placement risk a fresh voxel
      reconversion would.

  GAP_BRIDGE / PIPELINE_ARTIFACT -- applied in VOXEL space (shape-interpolation
      fill, or a --smooth 0.0 reconversion), which DOES need the rigid origin
      the original conversion used. That origin is derived per source subject
      (derive_origin in repair_continuity_q152.py) from every OTHER already-
      correctly-placed label the same volume already contributes -- never
      guessed. A subject is SKIPPED (recorded, not silently dropped) if that
      derivation's own per-label spread exceeds ORIGIN_SPREAD_LIMIT_MM: this
      project's standing rule is that a plausible fix is worth less than an
      honestly-declined one that would risk placing a muscle in the wrong
      place, which is worse than leaving it fragmented.

Every subject fix lands in a new small subject named
'<root_subject>_contfix' (this task's per-source variant of Q116's own
single-id '_fix' pattern -- one name per distinct source volume, not one
merged subject, because different sources need different label maps and
origins and there is no existing multi-source-into-one-subject merge tool to
invent one for). Male ids whose real source is a FEMALE subject (a
cross_subject_transfer) are fixed by fixing the female subject and
re-running the transfer, exactly Q113/Q114's own precedent -- never
duplicated as an independent male fix.
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from engine import volume_ingest as vol  # noqa: E402
from engine import vh_ingest as vh  # noqa: E402
import triage_continuity_q115 as triage  # noqa: E402
import repair_continuity_q152 as diag  # noqa: E402

AUDIT_JSON = REPO_ROOT / "data" / "derived" / "Q112_full_continuity_audit.json"
REPORT_JSON = REPO_ROOT / "data" / "derived" / "Q152_continuity_repair.json"
BUILD = REPO_ROOT / "build" / "vh"
ORIGIN_SPREAD_LIMIT_MM = 3.0

BADGE_BRIDGE = ("Slice gaps bridged by shape interpolation between real sections "
                "({gap_mm:.1f} mm, {pct:.1f}% of volume) -- Q152.")
BADGE_ISLAND = ("A stray, disconnected fragment ({pct:.1f}% of volume) was dropped as "
                "not real anatomy -- Q152 continuity repair.")
BADGE_PIPELINE = ("Re-surfaced at --smooth 0.0 to recover real continuity the "
                   "original smoothing/decimation pass severed -- Q152.")


def load_audit_subjects():
    audit = json.loads(AUDIT_JSON.read_text())
    out = {}
    for body in ("male", "female"):
        for key, rec in audit["bodies"][body]["structures"].items():
            out[(body, rec["id"], rec["side"])] = rec.get("subjects") or []
    return out


def new_manifest_skeleton(subject: str, source_volume: str, label_map: str,
                           smooth: float) -> dict:
    return {"subject": subject,
            "frame": "atlas: +X right, +Y superior, +Z anterior, millimetres",
            "source_volume": source_volume, "source_kind": "labelled volume (NIfTI)",
            "label_map": label_map, "marching_cubes_step": 1,
            "surface_smoothing_sigma_voxels": smooth,
            "attribution": ["Q152 continuity repair: geometry re-surfaced from the "
                            "same segmented source volume as its own original "
                            "subject; same licence/consent terms apply."],
            "structures": []}


def write_subject(out_dir: Path, manifest: dict, verts_blocks, faces_blocks):
    out_dir.mkdir(parents=True, exist_ok=True)
    all_v = np.concatenate(verts_blocks).astype(np.float32) if verts_blocks else np.zeros((0, 3), np.float32)
    all_f = np.concatenate(faces_blocks).astype(np.uint32) if faces_blocks else np.zeros((0, 3), np.uint32)
    (out_dir / "vertices.f32").write_bytes(all_v.tobytes())
    (out_dir / "faces.u32").write_bytes(all_f.tobytes())
    manifest["vertex_count"] = int(all_v.shape[0])
    manifest["triangle_count"] = int(all_f.shape[0])
    if len(all_v):
        manifest["bbox_min_mm"] = [round(float(x), 4) for x in all_v.min(axis=0)]
        manifest["bbox_max_mm"] = [round(float(x), 4) for x in all_v.max(axis=0)]
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))


def apply_islands(report: dict, audit_subjects: dict, log: list) -> dict:
    """Mesh-space island drop. Groups by the actual SHIPPED subject (from the
    live audit, not the diagnosis's own traced-back source subject -- for a
    transferred id these can differ, and it's the shipped mesh that needs
    fixing).  Returns {(body, shipped_subject): manifest-in-progress} plus
    fills verts/faces lists via closures held in `written`."""
    written: dict[tuple, dict] = {}   # (body, subject) -> dict(manifest=..., verts=[], faces=[])
    for key, r in report["results"].items():
        if r["cause"] not in ("DROP_ISLAND", "MIXED_ISLAND_AND_ANATOMICAL"):
            continue
        if not r.get("islands"):
            continue
        body, atlas_id, side = r["body"], r["id"], r["side"]
        subjects = audit_subjects.get((body, atlas_id, side)) or []
        if not subjects:
            log.append(f"SKIP island {body}/{atlas_id}: no shipped subject in audit")
            continue
        # Q152b fix: the diagnosis JSON's own 'side' can be the literal string
        # "none" (a midline structure, e.g. diaphragm) -- every OTHER manifest
        # in this build stores that as real JSON null (see e.g. ct_vhf_twall's
        # own diaphragm entry). Writing the raw string here (as this function
        # did before) broke resolve_source's own side_norm lookup against a
        # subject this function itself produces (side_norm=None != "none"),
        # silently making a later diagnosis pass unable to trace back through
        # its own output -- exactly what surfaced female diaphragm as
        # UNRESOLVED. Normalized the same way resolve_source itself does.
        side_manifest = None if side in (None, "none") else side
        subject = subjects[0]
        try:
            result = diag.drop_mesh_islands(subject, atlas_id, side)
        except (Exception, SystemExit) as exc:
            log.append(f"SKIP island {body}/{atlas_id}: {exc}")
            continue
        if not result["dropped"]:
            log.append(f"SKIP island {body}/{atlas_id}: {result['reason']}")
            continue
        # '_contfix_mesh' (not plain '_contfix'): a source subject can carry BOTH a
        # mesh-space island drop (this function) and a voxel-space gap-bridge/pipeline
        # fix (apply_voxel_fixes) for DIFFERENT ids at once -- ct_vhf_dneck is exactly
        # this case (island drops on semispinalis_capitis_l etc., a gap-bridge on
        # longus_capitis_l). Same subject name for both would let whichever phase
        # writes second silently overwrite the first's fixes.
        out_subject = f"{subject}_contfix_mesh"
        wkey = (body, out_subject)
        if wkey not in written:
            src_manifest = json.loads((BUILD / subject / "manifest.json").read_text())
            written[wkey] = {
                "manifest": {"subject": out_subject,
                             "frame": src_manifest["frame"],
                             "source_volume": src_manifest.get("source_volume"),
                             "source_kind": "mesh-space island drop of an already-built subject",
                             "attribution": src_manifest.get("attribution", []),
                             "structures": []},
                "verts": [], "faces": [], "voffset": 0, "foffset": 0,
            }
        w = written[wkey]
        pct = result["dropped_face_frac"] * 100
        w["manifest"]["structures"].append({
            "atlas_id": atlas_id, "side": side_manifest,
            "source_structure": atlas_id,
            "source_file": f"{subject}/manifest.json#mesh-island-drop",
            "vertex_offset": w["voffset"], "face_offset": w["foffset"],
            "vertex_count": int(len(result["kept_verts"])),
            "triangle_count": int(len(result["kept_faces"])),
            "bbox_min_mm": [round(float(x), 4) for x in result["kept_verts"].min(axis=0)],
            "bbox_max_mm": [round(float(x), 4) for x in result["kept_verts"].max(axis=0)],
            "procedural_badge": BADGE_ISLAND.format(pct=pct),
            "q152_island_drop": {"dropped_face_frac": result["dropped_face_frac"],
                                  "n_components_before": result["n_components"],
                                  "dropped_components": result["dropped_bbox"]},
        })
        w["verts"].append(result["kept_verts"].astype(np.float32))
        w["faces"].append((result["kept_faces"] + w["voffset"]).astype(np.uint32))
        w["voffset"] += len(result["kept_verts"])
        w["foffset"] += len(result["kept_faces"])
        log.append(f"ISLAND {body}/{atlas_id}: dropped {pct:.2f}% of faces "
                    f"({result['n_components']} components) -> {out_subject}")
    for (body, out_subject), w in written.items():
        write_subject(BUILD / out_subject, w["manifest"], w["verts"], w["faces"])
    return written


def apply_voxel_fixes(report: dict, audit_subjects: dict, log: list) -> dict:
    """GAP_BRIDGE + PIPELINE_ARTIFACT, grouped by the resolved ROOT source
    subject (recomputed here via resolve_source, not trusted from the
    diagnosis JSON's own mislabeled 'resolved_subject' field -- see
    scripts/repair_continuity_q152.py's diagnose_one, which stores the
    STARTING subject there, not the chased-through root)."""
    # Keyed (root_subject) -> {(atlas_id, side): (bodies, r, src)}: a male id
    # transferred from a female source (e.g. longus_capitis_l via
    # xfer_vhf2vhm_neck) and the female's OWN direct entry both resolve to
    # the SAME root_subject/label -- fixing it once there fixes both (exactly
    # Q113/Q114's own precedent), so this dedupes by (atlas_id, side) rather
    # than processing, and duplicating geometry for, every body that
    # happens to reference it.
    groups: dict[str, dict[tuple, tuple]] = {}
    for key, r in report["results"].items():
        if r["cause"] not in ("GAP_BRIDGE", "PIPELINE_ARTIFACT"):
            continue
        if r.get("source") == "Q113/Q114 (reused verbatim)":
            continue  # external_intercostals: already fixed, nothing to redo
        body, atlas_id, side = r["body"], r["id"], r["side"]
        subjects = audit_subjects.get((body, atlas_id, side)) or []
        side_norm = None if side in (None, "none") else side
        src = None
        for s in dict.fromkeys(subjects):
            resolved = triage.resolve_source(s, atlas_id, side_norm)
            if resolved["kind"] == "volume":
                src = resolved
                break
        if src is None:
            log.append(f"SKIP voxel-fix {body}/{atlas_id}: source no longer resolvable")
            continue
        root_subject = src["resolved_subject"]
        by_id = groups.setdefault(root_subject, {})
        # Q152b fix: normalized (side_norm, matching resolve_source's own
        # convention -- None, never the literal string "none") -- this key's
        # `side` also flows straight into the new subject's own manifest
        # entry below, and every other manifest in this build stores a
        # midline structure's side as real JSON null, not the string "none"
        # (see the apply_islands fix just above for the same bug and its
        # effect: female diaphragm's own later resolve_source lookup broke
        # on exactly this mismatch).
        idkey = (atlas_id, side_norm)
        if idkey in by_id:
            by_id[idkey][0].append(body)
        else:
            by_id[idkey] = ([body], r, src)

    written: dict[str, dict] = {}
    for root_subject, items in groups.items():
        if not (BUILD / root_subject / "manifest.json").exists():
            log.append(f"SKIP {root_subject}: not present in this build (recovered-bundle-only "
                       f"subject with no local raw manifest to align a reconversion against)")
            continue
        try:
            origin, spread = diag.derive_origin(root_subject)
        except (Exception, SystemExit) as exc:
            log.append(f"SKIP {root_subject}: origin derivation failed: {exc}")
            continue
        if spread > ORIGIN_SPREAD_LIMIT_MM:
            log.append(f"SKIP {root_subject}: origin estimate spread {spread:.2f}mm exceeds "
                       f"{ORIGIN_SPREAD_LIMIT_MM}mm safety limit -- declined rather than risk "
                       f"placing geometry wrong (all {len(items)} id(s) on this subject left "
                       f"fragmented, disclosed)")
            continue
        log.append(f"{root_subject}: derived origin {origin.round(3).tolist()} "
                   f"(spread {spread:.3f}mm across labels) -- OK, applying")

        mapping_path = BUILD / f"{root_subject}_volume_mapping.json"
        if not mapping_path.exists():
            mapping_path = REPO_ROOT / "mappings" / "subjects" / f"{root_subject}_volume_mapping.json"
        mapping = json.loads(mapping_path.read_text())
        src_manifest = json.loads((BUILD / root_subject / "manifest.json").read_text())
        # Prefer the per-subject manifest's OWN 'source_volume' (see derive_origin's
        # matching comment) -- the separate volume_mapping.json copy can be stale.
        source_volume = src_manifest.get("source_volume") or mapping["source_volume"]
        volume, affine, codes = vol.load_labels(Path(source_volume))
        z_ax = diag.zaxis_index(codes)
        spacing = np.array([np.linalg.norm(affine[:3, k]) for k in range(3)])
        orig_smooth = src_manifest.get("surface_smoothing_sigma_voxels", 1.0)

        out_subject = f"{root_subject}_contfix"
        man = new_manifest_skeleton(out_subject, source_volume, mapping["label_map"], None)
        verts_blocks, faces_blocks, voffset, foffset = [], [], 0, 0
        lo, hi = np.full(3, np.inf), np.full(3, -np.inf)

        for (atlas_id, side), (bodies, r, src) in items.items():
            label = src["label"]
            smooth_used = orig_smooth
            badge = None
            working_volume = volume
            if r["cause"] == "PIPELINE_ARTIFACT":
                smooth_used = 0.0
                badge = BADGE_PIPELINE
            else:  # GAP_BRIDGE
                # ALL approved gaps for this label in one call (interpolate_labels_z fills
                # a label's whole real-slice range at once) but restricted to exactly the
                # ranges the diagnosis approved -- never any other gap the same label might
                # have that exceeded the 10mm cap (see bridge_label_in_volume's own docstring).
                # int(): the diagnosis JSON's z-indices can come back as numpy
                # int64 (from np.argwhere/find_objects) rounded to plain str by
                # its own writer's `default=str` fallback -- normalize either
                # representation to a real Python int here.
                approved = [(int(br["gap_zmin"]), int(br["gap_zmax"])) for br in r["bridges"]]
                working_volume, total_added = diag.bridge_label_in_volume(
                    working_volume, label, z_ax, spacing[z_ax], approved_ranges=approved)
                voxel_vol_mm3 = np.prod(spacing)
                added_pct = 100 * total_added * voxel_vol_mm3 / (
                    (working_volume == label).sum() * voxel_vol_mm3) if (working_volume == label).any() else 0
                max_gap_mm = max((b["gap_mm"] for b in r["bridges"]), default=0)
                badge = BADGE_BRIDGE.format(gap_mm=max_gap_mm, pct=added_pct)

            v, f = vol.label_surface(working_volume, label, step=1, smooth=smooth_used)
            if len(v) == 0:
                log.append(f"SKIP {'/'.join(bodies)}/{atlas_id}: label empty after fix (unexpected)")
                continue
            world = vol.voxels_to_atlas(v, affine) - origin
            mn, mx = world.min(axis=0), world.max(axis=0)
            lo, hi = np.minimum(lo, mn), np.maximum(hi, mx)
            man["structures"].append({
                "atlas_id": atlas_id, "side": side, "source_structure": atlas_id,
                "source_file": f"{Path(mapping['source_volume']).name}#{label}",
                "vertex_offset": voffset, "face_offset": foffset,
                "vertex_count": int(v.shape[0]), "triangle_count": int(f.shape[0]),
                "bbox_min_mm": [round(float(x), 4) for x in mn],
                "bbox_max_mm": [round(float(x), 4) for x in mx],
                "procedural_badge": badge,
                "q152_cause": r["cause"],
            })
            verts_blocks.append(world.astype(np.float32))
            faces_blocks.append((f + voffset).astype(np.uint32))
            voffset += v.shape[0]
            foffset += f.shape[0]
            log.append(f"{r['cause']} {'/'.join(bodies)}/{atlas_id}: reconverted from "
                       f"{root_subject} (smooth={smooth_used}) -> {out_subject} "
                       f"(fixes it for every body listed, via a shared source or a "
                       f"regenerated transfer)")

        if man["structures"]:
            man["marching_cubes_step"] = 1
            write_subject(BUILD / out_subject, man, verts_blocks, faces_blocks)
            written[out_subject] = man

    return written


def main() -> int:
    if not REPORT_JSON.exists():
        raise SystemExit(f"Run scripts/repair_continuity_q152.py first -- {REPORT_JSON} missing")
    report = json.loads(REPORT_JSON.read_text())
    audit_subjects = load_audit_subjects()
    log: list[str] = []

    islands = apply_islands(report, audit_subjects, log)
    voxel = apply_voxel_fixes(report, audit_subjects, log)

    print("\n".join(log))
    print(f"\n{len(islands)} island-drop contfix subject(s), {len(voxel)} voxel-fix contfix subject(s)")
    out = REPO_ROOT / "data" / "derived" / "Q152_apply_log.json"
    out.write_text(json.dumps({
        "log": log,
        "island_subjects": {f"{b}|{s}": True for b, s in islands},
        "voxel_subjects": list(voxel),
    }, indent=2))
    print(f"Wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
