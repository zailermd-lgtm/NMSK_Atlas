"""Validates the core animation-safety guarantee: an anchor stored in a
bone's local frame stays rigidly attached to that bone through arbitrary
posing, including compound/rotational end-of-range motion.

This is an engine-level test against a synthetic two-bone chain (a
shoulder-like ball-and-socket joint feeding a hinge elbow), which is the
right level to prove the *mechanism* is correct -- every anchor in
data/rig/anchors.json is resolved through this exact same
Rig.resolve_anchor() code path, so a mechanism proof here covers all of
them by construction (schema/rig.schema.json's design note). Data-level
checks (every anchor references a bone that exists, etc.) are covered
separately in test_attachment_existence.py.
"""
import numpy as np

from engine import geometry as geo
from engine.rig import Rig, BoneSpec, JointSpec, JointDOF, sample_full_rom_poses


def _build_test_rig():
    bones = {
        "torso": BoneSpec(id="torso", parent_in_kinematic_chain=None,
                           rest_transform=geo.Transform.identity()),
        "upper_arm": BoneSpec(id="upper_arm", parent_in_kinematic_chain="torso",
                               rest_transform=geo.Transform(np.eye(3), geo.vec3(200, 0, 0))),
        "forearm": BoneSpec(id="forearm", parent_in_kinematic_chain="upper_arm",
                             rest_transform=geo.Transform(np.eye(3), geo.vec3(0, -300, 0))),
    }
    shoulder = JointSpec(id="shoulder", parent_bone="torso", child_bone="upper_arm", dofs=[
        JointDOF("flexion_extension", geo.vec3(1, 0, 0), -60, 180),
        JointDOF("abduction_adduction", geo.vec3(0, 0, 1), 0, 180),
        JointDOF("internal_external_rotation", geo.vec3(0, 1, 0), -90, 90),
    ])
    elbow = JointSpec(id="elbow", parent_bone="upper_arm", child_bone="forearm", dofs=[
        JointDOF("flexion_extension", geo.vec3(1, 0, 0), 0, 150),
    ])
    return Rig(bones, {"shoulder": shoulder, "elbow": elbow}), shoulder, elbow


def test_anchor_stays_rigid_through_full_rom_including_compound_rotation():
    rig, shoulder, elbow = _build_test_rig()
    local_anchor = geo.vec3(10, -250, 5)  # e.g. a muscle insertion on the forearm
    shoulder_poses = sample_full_rom_poses(shoulder, n_per_axis=3)  # includes combined-axis end-of-range
    elbow_poses = sample_full_rom_poses(elbow, n_per_axis=3)
    combined_poses = []
    for sp in shoulder_poses:
        for ep in elbow_poses:
            combined_poses.append({**sp, **ep})
    assert rig.anchor_is_rigid_under_pose("forearm", local_anchor, combined_poses)


def test_rom_clamping_rejects_impossible_poses():
    rig, shoulder, elbow = _build_test_rig()
    impossible_pose = {"shoulder": {"abduction_adduction": 999.0}}
    clamped = rig.clamp_pose(impossible_pose)
    assert clamped["shoulder"]["abduction_adduction"] == 180.0  # clipped to documented max


def test_forward_kinematics_is_identity_at_neutral_pose_offsets():
    rig, shoulder, elbow = _build_test_rig()
    fk = rig.forward_kinematics({})
    # at neutral pose, upper_arm origin should sit exactly at its rest offset from torso
    np.testing.assert_allclose(fk["upper_arm"].apply(np.zeros(3)), geo.vec3(200, 0, 0))
    np.testing.assert_allclose(fk["forearm"].apply(np.zeros(3)), geo.vec3(200, -300, 0))
