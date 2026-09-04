#!/usr/bin/env python3
"""Cross-check muscle moment arms computed from the ingested geometry against
published values (OpenSim's lower-limb model and the biomechanics literature
it was validated against).

METHOD. For a muscle modelled as a straight line from its origin anchor A to
its insertion anchor B (both resolved to world coordinates through the same
bone frames scripts/audit_landmarks_vs_geometry.py fits from real geometry),
and a hinge joint with rotation axis (point C, unit direction u), the moment
arm about that axis is the classic rigid-body result for the moment of a
line-of-action force about an axis:

    r = (A - C) x normalize(B - A)  .  u

This is exact for a straight-line path -- it is what a point-to-point muscle
(no wrap surface) reduces to in OpenSim's own moment-arm solver -- and it is
evaluated at whatever joint angle the cadaver was captured in, which is close
to anatomical neutral for the hip, knee and ankle in the DU Visible Human Male.

WHAT THIS DELIBERATELY DOES NOT MODEL. Real gastrocnemius and soleus tendons
wrap the posterior calcaneus and (for gastrocnemius) the femoral condyles;
real hamstring tendons flatten against the tibial condyles at high flexion.
A straight chord underestimates a wrapped tendon's moment arm, more so as
flexion increases -- which is exactly why OpenSim gives wrapped muscles wrap
surfaces or via points instead of a bare two-point path, and exactly why this
script is a coarse cross-check at (roughly) one pose, not a replacement for
that machinery. The tolerance below is set accordingly generous.

JOINT AXES. Hip and ankle flexion/extension axes are taken as the atlas's own
mediolateral convention (+X), matching how this atlas already treats the
pelvis's superior axis and the tarsal/patellar frames as convention rather
than a fit, where no cartilage mesh gives a transverse axis to measure. The
knee axis is NOT convention -- it is the tibial plateau frame's fitted
transverse axis (lateral-minus-medial plateau cartilage), the one axis in
this script that comes from real geometry rather than an assumption.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.audit_landmarks_vs_geometry import load_geometry, build_frames  # noqa: E402

DATA_DIR = REPO_ROOT / "data"


def resolve_anchor(anchors_by_id: dict, muscle_id: str, role: str, frames: dict):
    a = anchors_by_id.get((muscle_id, role))
    if a is None:
        return None
    frame = frames.get(a["parent_bone_frame"])
    if frame is None:
        return None
    origin, basis = frame[:2]
    return origin + np.array(a["local_position_mm"], float) @ basis


def moment_arm(a: np.ndarray, b: np.ndarray, axis_point: np.ndarray, axis_dir: np.ndarray) -> float:
    axis_dir = axis_dir / np.linalg.norm(axis_dir)
    line = b - a
    line = line / np.linalg.norm(line)
    return float(np.cross(a - axis_point, line) @ axis_dir)


# (muscle_id, origin-side joint definition function key, published range in mm,
#  citation, one-line note on the comparison's honesty)
X_AXIS = np.array([1.0, 0.0, 0.0])  # mediolateral, atlas convention


def main() -> int:
    import json
    anchors = json.loads((DATA_DIR / "rig" / "anchors.json").read_text())
    anchors_by_id = {}
    for a in anchors:
        anchors_by_id[(a["owner_entity"], a["anchor_type"])] = a

    manifest, blocks, by_atlas_id, faces_by_atlas_id = load_geometry("vhm_both")
    frames = build_frames(by_atlas_id, blocks, faces_by_atlas_id)

    print(f"{'muscle':<24}{'joint':<10}{'computed mm':>12}  reference (source)")
    print("-" * 100)

    cases = []
    for side in ("r", "l"):
        hip_c = frames.get(f"femur_{side}")
        knee_f = frames.get(f"tibia_{side}")
        ankle_f = frames.get(f"tarsals_{side}")
        if hip_c is None or knee_f is None or ankle_f is None:
            print(f"[{side}] missing a required frame -- skipping this side "
                  f"(femur={hip_c is not None}, tibia={knee_f is not None}, "
                  f"tarsals={ankle_f is not None})")
            continue
        hip_centre = hip_c[0]
        knee_axis_point, knee_basis = knee_f[0], knee_f[1]
        knee_axis_dir = knee_basis[0]  # fitted transverse (epicondylar) axis
        ankle_centre = ankle_f[0]

        cases += [
            (f"gluteus_maximus_{side}", "hip_extension", hip_centre, X_AXIS,
             (35, 65), "Delp SL, PhD dissertation (1990); Arnold EM et al., "
             "Ann Biomed Eng 38:269 (2010) -- OpenSim gait2392 lower-limb model, "
             "gluteus maximus moment arm near hip-neutral"),
            (f"biceps_femoris_{side}", "knee_flexion", knee_axis_point, knee_axis_dir,
             (15, 35), "Herzog W, Read LJ, J Anat 182:213 (1993); Arnold EM et al., "
             "Ann Biomed Eng 38:269 (2010) -- knee flexor moment arm near full extension"),
            (f"semitendinosus_{side}", "knee_flexion", knee_axis_point, knee_axis_dir,
             (15, 35), "Herzog W, Read LJ, J Anat 182:213 (1993) -- semitendinosus "
             "moment arm near full extension"),
            (f"semimembranosus_{side}", "knee_flexion", knee_axis_point, knee_axis_dir,
             (15, 35), "Herzog W, Read LJ, J Anat 182:213 (1993) -- semimembranosus "
             "moment arm near full extension"),
            (f"gastrocnemius_{side}", "ankle_plantarflexion", ankle_centre, X_AXIS,
             (30, 60), "Maganaris CN et al., J Physiol 510:977 (1998); Rugg SG et al., "
             "J Biomech 23:495 (1990) -- Achilles tendon moment arm near ankle-neutral"),
            (f"soleus_{side}", "ankle_plantarflexion", ankle_centre, X_AXIS,
             (30, 60), "Maganaris CN et al., J Physiol 510:977 (1998) -- soleus shares "
             "gastrocnemius's Achilles insertion, so its ankle moment arm is near-identical"),
        ]

    out_of_range = []
    for muscle_id, joint, axis_point, axis_dir, ref_range, source in cases:
        a = resolve_anchor(anchors_by_id, muscle_id, "muscle_origin", frames)
        b = resolve_anchor(anchors_by_id, muscle_id, "muscle_insertion", frames)
        if a is None or b is None:
            print(f"{muscle_id:<24}{joint:<10}{'(no anchor)':>12}  {source}")
            continue
        r = moment_arm(a, b, axis_point, axis_dir)
        lo, hi = ref_range
        flag = "" if lo <= abs(r) <= hi else "  <-- OUTSIDE reference range"
        if flag:
            out_of_range.append((muscle_id, joint, r, ref_range))
        print(f"{muscle_id:<24}{joint:<10}{r:>12.1f}  [{lo}-{hi}] {source}{flag}")

    print(f"\n{len(cases) - len(out_of_range)}/{len(cases)} within their published range "
          f"(straight-line-path, single-pose approximation -- see module docstring).")
    if out_of_range:
        print("\nOut of range:")
        for muscle_id, joint, r, ref_range in out_of_range:
            print(f"  {muscle_id} ({joint}): computed {r:.1f} mm, expected {ref_range}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
