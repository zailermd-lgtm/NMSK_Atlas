#!/usr/bin/env python3
"""Generate PROCEDURAL/RULE-BASED ligament connector meshes bridging two already-shipped
BONE landmarks (never a muscle mesh -- that is generate_tendon_connectors.py's job, Q118).

Q121's own feasibility investigation (see PROJECT_STATE.md) checked all 83 unshipped
`data/ligaments/**/*.json` records against this project's OWN existing landmark/anchor
system -- `scripts/audit_landmarks_vs_geometry.py:build_frames()` for turning a bone-local
landmark into a world coordinate, `data/skeleton/bones.json`'s own numbered landmarks for
the coordinate itself -- and found only ONE fully qualifies: `transverse_humeral_ligament_
{r,l}`. Every other candidate failed one of two independent, real blockers (see the
docstring's WHY section below and the Q121 PROJECT_STATE entry for the full per-ligament
accounting).

IMPORTANT CORRECTION TO Q118'S OWN CLAIM: Q118's PROJECT_STATE entry says build_frames()
"constructs a MEASURED frame for only 8 bones" (femur/fibula/hip_bone/patella, r/l). That
was true of the RESTRICTED subject list Q118's own `male_order()`/`female_order()` loaded
(lower-limb subjects only, sufficient for ITS OWN lower-limb tendon set) -- it was never a
claim about build_frames() itself, which (re-read in full for this item) also has
non-cartilage-dependent fallback paths for humerus, radius, ulna, clavicle, scapula,
mandible, hyoid and sternum (see its own "the upper body" section, using by_atlas_id
directly, no cartilage mesh needed). Verified directly this item by decoding the ACTUAL
published (pending) bundles (`build/viewer_{m,f}/atlas_viewer_*.html`'s own embedded
bundle-json/bundle-b64 payloads, dequantized at the export pipeline's own 0.25 mm/int16
scheme) AND by loading the real, full per-subject order each rebuild script actually uses
(reproduced below, correcting Q118's own truncated `male_order()`/`female_order()`, which
omit most upper-body/head/neck subjects because they were never needed for lower-limb
tendons): build_frames() resolves 19 bones on the male, 17 on the female (missing radius_l/
ulna_l on her -- her left forearm is documented elsewhere as incomplete, Q12/Q71/Q97).

Even so, MOST of the 83 ligaments still fail, on a SEPARATE, independent blocker never
before documented in this project: even where BOTH of a ligament's attachment bones ARE in
the resolvable set, that ligament's own authored landmark TEXT (eponymous/descriptive
phrases like "Schottle's point", "intertrochanteric line", "musculotendinous junction",
"superior pubic ramus") essentially never matches, as a literal substring, any landmark
NAME already authored in that bone's own `data/skeleton/bones.json` entry -- the same
single-exact-match rule `generate_tendon_connectors.py` already uses for its own
bone_landmark lookups. This item does NOT relax that rule or invent a new resolution
method (e.g. interpolating between two named landmarks to approximate an unauthored one)
-- per this item's own hard constraint, an unresolvable landmark is declined, not
approximated. See PROJECT_STATE.md's Q121 entry for the full per-ligament table.

GEOMETRY METHOD (bone-to-bone, NOT muscle-to-bone -- the real adaptation this item makes
to Q118's tendon method):
  1. Both endpoints are the bone's own already-authored `position_local_mm` landmark
     (never a nearest-mesh-vertex search -- there is no muscle mesh in this method at
     all), placed in world coordinates via the SAME `build_frames()`/`place()` machinery
     Q118 used, on THIS body's own real geometry.
  2. LENGTH = the real, measured straight-line distance between those two points on this
     body's own geometry -- never invented, never copied between bodies (see the Q121
     per-body numbers in PROJECT_STATE.md, which differ slightly by body as expected).
  3. CROSS-SECTION is the one genuinely arbitrary modeling choice, disclosed exactly like
     Q104's disc radius and Q118's tendon taper: since BOTH endpoints are bone landmarks
     (no muscle belly to measure a real spread from, unlike a tendon), there is nothing in
     this project's geometry to measure a caliper from at all. A uniform-radius tube is
     used, radius = a fixed disclosed fraction of the real measured gap (0.30x, clamped to
     [2, 6] mm) -- proportioned to look like a short, relatively stout band rather than a
     thin cord, honestly matching this ligament's own record, which (already, before this
     item touched it) cites a source questioning whether it is even a discrete ligament
     structure or a tendinous sling (Gleason et al. 2005) -- the SAME class of disclosed
     simplification as Q118's quadriceps tendon (4 round cords standing in for a real
     trilaminar sheet). This is NOT a measured ligament caliper; this project has no
     soft-tissue-thickness imaging of any kind.

Usage:
    python3 scripts/generate_ligament_connectors.py --body male
    python3 scripts/generate_ligament_connectors.py --body female
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.audit_landmarks_vs_geometry import build_frames, place  # noqa: E402
from scripts.generate_tendon_connectors import ring, tapered_tube, weld, mesh_components  # noqa: E402
from engine.vh_ingest import points_inside_mesh  # noqa: E402

DATA_DIR = REPO_ROOT / "data"
BUILD_DIR = REPO_ROOT / "build" / "vh"


def male_order() -> list[str]:
    """The REAL, full subject order scripts/vhm_rebuild_bundle.sh feeds
    scripts/export_viewer_bundle.py (read directly from that script's own `SUBJ` build-up,
    not reconstructed) -- unlike generate_tendon_connectors.py's own `male_order()`, which
    is deliberately restricted to the lower-limb subjects its own tendon set needed and is
    NOT a complete order (see this script's own docstring correction above)."""
    order = []
    if (BUILD_DIR / "ct_vhm_pfloor_fix" / "manifest.json").exists():
        order.append("ct_vhm_pfloor_fix")
    order += ["ct_vhm_foot", "vhm_both", "ct_vhm_arm", "ct_vhm_armm", "ct_vhm_forearm",
              "ct_vhm_shsp", "ct_vhm_delt", "ct_vhm_cuff", "ct_vhm_pmr", "ct_vhm_es",
              "ct_vhm_head", "ct_vhm", "ct_vhm_headm", "ct_vhm_neck", "ct_vhm_neckbv",
              "xfer_vhf2vhm", "xfer_vhf2vhm_neck", "ct_vhm_ggl", "ct_vhm_sgl",
              "ct_vhm_pfloor", "ct_vhm_orbit", "ct_vhm_abd", "ct_vhm_abw", "ct_vhm_twall",
              "ct_s1159_abd", "ct_s1159", "ct_vhm_skin"]
    return order


def female_order() -> list[str]:
    """The REAL, full subject order scripts/cryo/vhf_rebuild_bundle.sh feeds
    scripts/export_viewer_bundle.py, same correction as male_order() above."""
    order = ["ct_vhf_head", "ct_vhf_legs", "ct_vhf_tarsal", "ct_vhf_armb"]
    if (BUILD_DIR / "ct_vhf_descaorta" / "manifest.json").exists():
        order.append("ct_vhf_descaorta")
    if (BUILD_DIR / "ct_vhf_hyoid_fix" / "manifest.json").exists():
        order.append("ct_vhf_hyoid_fix")
    order += ["ct_vhf", "ct_vhf_headm", "ct_vhf_neck", "ct_vhf_neckbv", "ct_vhf_orbit",
              "ct_vhf_abd", "ct_vhf_shsp", "ct_vhf_delt", "ct_vhf_cuff", "ct_vhf_es",
              "ct_vhf_armm", "ct_vhf_forearm", "ct_vhf_left_forearm", "ct_vhf_dneck",
              "ct_vhf_hyoid", "ct_vhf_hand", "ct_vhf_femoral", "ct_vhf_popliteal",
              "ct_vhf_pfloor", "ct_vhf_twall", "ct_vhf_pmr", "xfer_vhm2vhf_rhom"]
    if (BUILD_DIR / "ct_vhf_nerve" / "manifest.json").exists():
        order.append("ct_vhf_nerve")
    if (BUILD_DIR / "ct_vhf_skin" / "manifest.json").exists():
        order.append("ct_vhf_skin")
    if (BUILD_DIR / "ct_vhf_xfersepta_fix" / "manifest.json").exists():
        order.append("ct_vhf_xfersepta_fix")
    if (BUILD_DIR / "xfer_vhm2vhf_sep" / "manifest.json").exists():
        order.append("xfer_vhm2vhf_sep")
    if (BUILD_DIR / "xfer_vhm2vhf" / "manifest.json").exists():
        order.append("xfer_vhm2vhf")
    return order


# The ligament ids this script attempts -- the single id Q121's investigation confirmed
# fully qualifies (both landmark names resolve, both bones frame-resolvable on both
# bodies). Structured as a dict so a future session can add another qualifying id without
# restructuring the script.
LIGAMENT_PLAN = {
    "transverse_humeral_ligament": {
        "bone": "humerus",
        "landmark_a": "greater tubercle",
        "landmark_b": "lesser tubercle",
    },
}

RADIUS_FRACTION = 0.30
MIN_RADIUS_MM = 2.0
MAX_RADIUS_MM = 6.0


def load_geometry_merged(order: list[str], needed_ids: set[str]):
    """Identical method to generate_tendon_connectors.py's own loader: first
    subject-in-`order`-wins, reproducing exactly what export_viewer_bundle.py's own
    claimed_by_prior_subjects logic would ship for that id."""
    out: dict[str, np.ndarray] = {}
    claimed: set[str] = set()
    for sub in order:
        mf = BUILD_DIR / sub / "manifest.json"
        if not mf.exists():
            continue
        man = json.loads(mf.read_text())
        verts = np.fromfile(BUILD_DIR / sub / "vertices.f32", dtype="<f4").reshape(-1, 3).astype(np.float64)
        this_subject: dict[str, list] = {}
        for s in man["structures"]:
            aid = s["atlas_id"]
            if aid not in needed_ids or aid in claimed:
                continue
            v0, vn = s["vertex_offset"], s["vertex_count"]
            this_subject.setdefault(aid, []).append(verts[v0:v0 + vn])
        for aid, chunks in this_subject.items():
            out[aid] = chunks
            claimed.add(aid)
    return {k: np.vstack(v) for k, v in out.items()}


def load_faces_merged(order: list[str], needed_ids: set[str]):
    """Same first-subject-wins method as load_geometry_merged(), but keeping each
    winning subject's own FACES too (locally re-indexed), needed for the
    inside-the-bone-mesh containment check build_ligament() runs on its own output."""
    out: dict[str, tuple[np.ndarray, np.ndarray]] = {}
    claimed: set[str] = set()
    for sub in order:
        mf = BUILD_DIR / sub / "manifest.json"
        if not mf.exists():
            continue
        man = json.loads(mf.read_text())
        verts = np.fromfile(BUILD_DIR / sub / "vertices.f32", dtype="<f4").reshape(-1, 3).astype(np.float64)
        faces = np.fromfile(BUILD_DIR / sub / "faces.u32", dtype="<u4").reshape(-1, 3).astype(np.int64)
        this_subject: dict[str, list] = {}
        for s in man["structures"]:
            aid = s["atlas_id"]
            if aid not in needed_ids or aid in claimed:
                continue
            v0, vn = s["vertex_offset"], s["vertex_count"]
            f0, fn = s["face_offset"], s["triangle_count"]
            this_subject.setdefault(aid, []).append((verts[v0:v0 + vn], faces[f0:f0 + fn] - v0))
        for aid, chunks in this_subject.items():
            all_v, all_f, off = [], [], 0
            for v, f in chunks:
                all_v.append(v)
                all_f.append(f + off)
                off += len(v)
            out[aid] = (np.vstack(all_v), np.vstack(all_f))
            claimed.add(aid)
    return out


def build_ligament(lig_id: str, plan: dict, by_atlas_id: dict, frames: dict, bones: dict,
                    bone_meshes_with_faces: dict):
    side = lig_id[-2:]  # "_r" or "_l"
    bone_id = plan["bone"] + side
    frame = frames.get(bone_id)
    if frame is None:
        return None, f"no measured frame for {bone_id}"
    bone_record = bones.get(bone_id)
    mesh = by_atlas_id.get(bone_id)
    if mesh is None:
        return None, f"no shipped geometry for {bone_id} on this body"

    def find_landmark(needle: str):
        needle = needle.lower()
        hits = [lm for lm in bone_record.get("landmarks", []) if needle in lm["name"].lower()]
        if len(hits) != 1:
            return None, f"expected exactly one bone landmark containing {needle!r}, found {len(hits)}"
        return hits[0]["position_local_mm"], None

    a_local, a_err = find_landmark(plan["landmark_a"])
    if a_err:
        return None, a_err
    b_local, b_err = find_landmark(plan["landmark_b"])
    if b_err:
        return None, b_err

    p0 = place(a_local, frame, bone_record)
    p1 = place(b_local, frame, bone_record)
    gap = float(np.linalg.norm(p1 - p0))
    if gap < 1e-3:
        return None, f"the two landmarks coincide (gap {gap:.2f} mm) -- no ligament to model"

    radius = float(np.clip(RADIUS_FRACTION * gap, MIN_RADIUS_MM, MAX_RADIUS_MM))
    verts, faces = tapered_tube(p0, p1, radius, radius)
    verts, faces = weld(verts, faces)
    n_comp = mesh_components(faces, len(verts))

    d0 = float(np.linalg.norm(mesh - p0, axis=1).min())
    d1 = float(np.linalg.norm(mesh - p1, axis=1).min())

    # POST-GENERATION VERIFICATION (the check a straight muscle-to-bone tendon never
    # needed): both endpoints of a bone-to-bone connector sit on the SAME (or an
    # adjoining) bone's own surface, so unlike a tendon -- whose muscle end is clearly
    # outside the bone -- there is no guarantee the straight chord between them stays
    # outside that bone at all. Checked directly against this body's own segmented
    # humerus mesh (ray-crossing containment, engine.vh_ingest.points_inside_mesh, the
    # SAME test Q118 used for skin containment): if a large fraction of the generated
    # tube's own vertices are INSIDE its own target bone, the straight-line method is
    # wrong for this attachment pair (the two points flank a locally convex/grooved
    # bone surface, so the chord cuts inward), and the connector is honestly declined
    # here rather than shipped half-buried in bone.
    own_mesh = bone_meshes_with_faces.get(bone_id)
    frac_inside_own_bone = None
    if own_mesh is not None:
        bv, bf = own_mesh
        inside = points_inside_mesh(verts, bv, bf)
        frac_inside_own_bone = float(inside.sum()) / float(len(verts))

    meta = {
        "bone": bone_id,
        "p0_world_mm": [round(float(x), 2) for x in p0],
        "p1_world_mm": [round(float(x), 2) for x in p1],
        "gap_mm": round(gap, 2),
        "radius_mm": round(radius, 2),
        "d_landmark_a_to_bone_mm": round(d0, 2),
        "d_landmark_b_to_bone_mm": round(d1, 2),
        "n_components": n_comp,
        "n_vertices": int(len(verts)),
        "n_faces": int(len(faces)),
        "frac_vertices_inside_own_bone": (round(frac_inside_own_bone, 3)
                                           if frac_inside_own_bone is not None else None),
    }
    if frac_inside_own_bone is not None and frac_inside_own_bone > 0.10:
        return None, (
            f"generated, but {frac_inside_own_bone*100:.0f}% of the connector's own "
            f"vertices lie INSIDE {bone_id}'s own mesh (straight-chord-in-convex-bone "
            f"failure, verified by ray-crossing containment) -- the straight-cord method "
            f"that works for a muscle-to-bone tendon does not safely generalize to this "
            f"bone-to-bone attachment pair; declined rather than shipped half-buried in "
            f"bone. meta={meta}"
        )
    return (verts, faces, meta), None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--body", choices=["male", "female"], required=True)
    ap.add_argument("-o", "--out-dir", default=str(DATA_DIR / "ct_sources" / "task_outputs"))
    args = ap.parse_args()

    order = male_order() if args.body == "male" else female_order()
    suffix_ids = set()
    for lid, plan in LIGAMENT_PLAN.items():
        for side in ("r", "l"):
            suffix_ids.add(plan["bone"] + "_" + side)
    by_atlas_id = load_geometry_merged(order, suffix_ids)
    bone_meshes_with_faces = load_faces_merged(order, suffix_ids)
    frames = build_frames(by_atlas_id, {}, {})
    bones = {b["id"]: b for b in json.loads((DATA_DIR / "skeleton" / "bones.json").read_text())}

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    report = {"source": "scripts/generate_ligament_connectors.py, Q121 (2026-09-22)"}
    for lid, plan in LIGAMENT_PLAN.items():
        for side in ("r", "l"):
            full_id = f"{lid}_{side}"
            result, err = build_ligament(full_id, plan, by_atlas_id, frames, bones, bone_meshes_with_faces)
            if err:
                print(f"[{args.body}] {full_id}: DECLINED -- {err}")
                report[full_id] = {"status": "declined", "reason": err}
                continue
            verts, faces, meta = result
            obj_path = out_dir / f"ligament_{args.body}_{full_id}.obj"
            with open(obj_path, "w") as f:
                f.write(f"# procedural ligament connector, Q121, body={args.body}, id={full_id}\n")
                for x, y, z in verts:
                    f.write(f"v {x:.4f} {y:.4f} {z:.4f}\n")
                for a, b, c in faces:
                    f.write(f"f {a+1} {b+1} {c+1}\n")
            print(f"[{args.body}] {full_id}: OK, {meta['n_vertices']} verts, "
                  f"{meta['n_faces']} faces, {meta['n_components']} component(s) -> {obj_path}")
            report[full_id] = {"status": "generated", **meta, "obj_path": str(obj_path)}

    report_path = out_dir / f"ligament_generation_report_{args.body}.json"
    report_path.write_text(json.dumps(report, indent=2))
    print(f"wrote {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
