"""Landmarks scale with the measured bone length (Q43, 2026-09-14).

`position_local_mm` is the coordinate on the Visible Human MALE. A bone
record that carries `reference_length_mm` (his length along the frame's
long axis) has its along-axis coordinate stretched by the subject's
measured length over that reference; the across-axis coordinates stay in
millimetres; a record without a reference is used exactly as stored.
"""
import json
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from engine.geometry import (bone_length_along_axis, local_to_world,  # noqa: E402
                             scale_local_to_length)


def test_along_axis_scales_and_across_axes_do_not():
    # reference 400 mm, subject 340 mm -> factor 0.85 on Y only
    out = scale_local_to_length([30.0, -400.0, -12.0], 400.0, 340.0)
    assert np.allclose(out, [30.0, -340.0, -12.0]), out


def test_a_bone_without_a_reference_is_unchanged():
    p = [30.0, -400.0, -12.0]
    assert np.array_equal(scale_local_to_length(p, None, 340.0), p)
    assert np.array_equal(scale_local_to_length(p, 400.0, None), p)
    # and a nonsense length (a frame that failed) is no information either
    assert np.array_equal(scale_local_to_length(p, 400.0, float("nan")), p)
    assert np.array_equal(scale_local_to_length(p, 0.0, 340.0), p)


def test_the_same_body_gets_a_factor_of_exactly_one():
    p = np.array([30.0, -400.0, -12.0])
    assert np.array_equal(scale_local_to_length(p, 400.0, 400.0), p)


def test_local_to_world_applies_the_scaling_before_the_frame():
    origin = np.array([10.0, 20.0, 30.0])
    basis = np.eye(3)[[2, 0, 1]]          # local X->world Z, Y->world X, Z->world Y
    w = local_to_world([1.0, -400.0, 5.0], origin, basis, 400.0, 340.0)
    assert np.allclose(w, origin + np.array([-340.0, 5.0, 1.0])), w
    w0 = local_to_world([1.0, -400.0, 5.0], origin, basis)
    assert np.allclose(w0, origin + np.array([-400.0, 5.0, 1.0])), w0


def test_bone_length_is_the_1st_to_99th_percentile_extent():
    rng = np.random.default_rng(0)
    y = rng.uniform(-340.0, 0.0, size=20000)
    mesh = np.column_stack([rng.normal(size=y.size), y, rng.normal(size=y.size)])
    mesh = np.vstack([mesh, [[0.0, -900.0, 0.0]]])    # one stray vertex
    length = bone_length_along_axis(mesh, np.zeros(3), np.array([0.0, 1.0, 0.0]))
    assert abs(length - 340.0 * 0.98) < 2.0, length


def test_the_audit_frame_carries_the_length_and_the_male_reference_matches_it():
    """build_frames returns the measured length as the frame's 5th element,
    and on a synthetic bone of the reference length a landmark is placed
    where it was written."""
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import audit_landmarks_vs_geometry as audit
    def femur(sign):
        rng = np.random.default_rng(4)
        u = rng.normal(size=(1400, 3))
        u /= np.linalg.norm(u, axis=1)[:, None]
        head = u * 24.0 + np.array([90.0 * sign, 0.0, 0.0])
        t = np.linspace(0, 1, 900)[:, None]
        shaft = (np.array([114.0 * sign, -30.0, 0.0]) * (1 - t)
                 + np.array([95.0 * sign, -420.0, 0.0]) * t)
        return np.vstack([head, shaft + rng.normal(scale=1.2, size=shaft.shape)])
    # both femora, so the hip frames (which need both acetabula) exist too
    frames = audit.build_frames({"femur_r": femur(+1), "femur_l": femur(-1)}, {}, {})
    fr = frames["femur_r"]
    assert len(fr) == 5 and fr[4] is not None and 380 < fr[4] < 460, fr[4]
    # a bone with no fitted long axis gets None
    assert frames["hip_bone_r"][4] is None
    lm = [5.0, -400.0, 0.0]
    same = audit.place(lm, fr, {"reference_length_mm": fr[4]})
    stored = audit.place(lm, fr, {})
    assert np.allclose(same, stored)
    shorter = audit.place(lm, fr, {"reference_length_mm": fr[4] / 0.85})
    # 15 % shorter reference ratio -> the point moves 60 mm back up the shaft
    assert abs(np.linalg.norm(shorter - stored) - 60.0) < 1e-6


def test_every_reference_length_in_bones_json_is_on_a_bone_with_a_long_axis():
    bones = json.loads((REPO_ROOT / "data" / "skeleton" / "bones.json").read_text())
    with_ref = {b["id"] for b in bones if "reference_length_mm" in b}
    assert with_ref, "no bone carries reference_length_mm"
    stems = ("femur", "tibia", "fibula", "humerus", "radius", "ulna", "clavicle")
    # thoracic_vertebrae (Q131, 2026-09-22): the first vertebral-column entity
    # with a fitted long axis (its 12-vertebra column, T1 origin to T12/L1
    # end) rather than the "neither" convention cervical_vertebrae uses --
    # needed because its one shipped landmark (T11's spinous process) sits
    # ~250 mm from the T1 origin, far enough that the small male/female
    # column-length difference (305.8 vs 306.7 mm) would otherwise compound.
    exact_ids = ("thoracic_vertebrae",)
    for bid in with_ref:
        assert bid.startswith(stems) or bid in exact_ids, bid
        b = next(x for x in bones if x["id"] == bid)
        assert b["reference_length_mm"] > 100 and "reference_length_note" in b, bid


def test_truncated_bone_is_not_scaled():
    from engine.geometry import scale_local_to_length
    out = scale_local_to_length([10.0, -300.0, 5.0], 450.0, 150.0)      # measured 0.33 of the reference: cut by the field of view
    assert out.tolist() == [10.0, -300.0, 5.0]
    out = scale_local_to_length([10.0, -300.0, 5.0], 450.0, 400.0)
    assert abs(out[1] - (-300.0 * 400 / 450)) < 1e-9
