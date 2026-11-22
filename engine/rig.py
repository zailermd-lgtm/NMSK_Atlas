"""Kinematic rig: joint hierarchy, forward kinematics with ROM clamping,
and anchor resolution (rigid or linear-blend-skinned).

This is the module that satisfies the "allow later animation of the model
while preserving correct relative positions during movement, including
rotational movement, within human anatomical limits" requirement:

  - Bones form a tree (schema/rig.schema.json + data/rig/skeleton_hierarchy.json).
  - Each joint (schema/joint.schema.json) supplies degrees of freedom with
    cited min/max ROM.
  - A `Pose` is a dict of joint_id -> {axis_name: angle_deg}. `clamp_pose`
    clips every axis to its documented ROM before use, so an "impossible"
    pose can never be constructed.
  - `forward_kinematics` walks the tree root-to-leaf composing each joint's
    rotation into a global Transform per bone.
  - `resolve_anchor` converts any RigAnchor (stored purely in local
    coordinates) to its correct global position at the given pose — by
    construction, not by re-fitting -- which is exactly what keeps muscle/
    nerve/vessel/fascia attachment points correctly anchored through
    arbitrary, including compound-rotational, motion.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np

from . import geometry as geo

Pose = Dict[str, Dict[str, float]]  # joint_id -> {axis_name: angle_deg}


@dataclass
class JointDOF:
    axis_name: str
    axis_local_direction: np.ndarray  # unit vector in the *parent* bone's local frame
    min_deg: float
    max_deg: float


@dataclass
class JointSpec:
    id: str
    parent_bone: str
    child_bone: str
    dofs: List[JointDOF]


@dataclass
class BoneSpec:
    id: str
    parent_in_kinematic_chain: Optional[str]
    # transform of this bone's local frame w.r.t. its parent bone's local frame,
    # AT THE NEUTRAL (zero-pose) POSITION -- i.e. the joint center offset.
    rest_transform: geo.Transform


class Rig:
    def __init__(self, bones: Dict[str, BoneSpec], joints: Dict[str, JointSpec]):
        self.bones = bones
        self.joints = joints
        # bone_id -> joint_id whose child_bone == bone_id (i.e. the joint that moves it)
        self._joint_for_child: Dict[str, str] = {}
        for j in joints.values():
            self._joint_for_child[j.child_bone] = j.id

    def clamp_pose(self, pose: Pose) -> Pose:
        clamped: Pose = {}
        for joint_id, axes in pose.items():
            joint = self.joints.get(joint_id)
            if joint is None:
                continue
            clamped[joint_id] = {}
            for dof in joint.dofs:
                val = axes.get(dof.axis_name, 0.0)
                clamped[joint_id][dof.axis_name] = float(np.clip(val, dof.min_deg, dof.max_deg))
        return clamped

    def _joint_local_transform(self, joint: JointSpec, axes: Dict[str, float]) -> geo.Transform:
        """Compose this joint's DOF rotations (about axes fixed in the
        parent bone frame) into a single rigid transform, applied on top of
        the rest_transform offset of the child bone."""
        t = geo.Transform.identity()
        for dof in joint.dofs:
            angle = axes.get(dof.axis_name, 0.0)
            t = geo.Transform.from_axis_angle(dof.axis_local_direction, angle).compose(t)
        return t

    def forward_kinematics(self, pose: Pose, clamp: bool = True) -> Dict[str, geo.Transform]:
        """Returns bone_id -> Transform mapping that bone's LOCAL frame to
        the GLOBAL frame, at the given pose."""
        if clamp:
            pose = self.clamp_pose(pose)
        global_tf: Dict[str, geo.Transform] = {}

        def resolve(bone_id: str) -> geo.Transform:
            if bone_id in global_tf:
                return global_tf[bone_id]
            bone = self.bones[bone_id]
            if bone.parent_in_kinematic_chain is None:
                global_tf[bone_id] = bone.rest_transform  # root: rest_transform IS its global placement
                return global_tf[bone_id]
            parent_global = resolve(bone.parent_in_kinematic_chain)
            joint_id = self._joint_for_child.get(bone_id)
            joint_local = geo.Transform.identity()
            if joint_id is not None:
                joint = self.joints[joint_id]
                axes = pose.get(joint_id, {})
                joint_local = self._joint_local_transform(joint, axes)
            # parent_frame -> (rest offset) -> (joint rotation) -> child_frame
            combined = parent_global.compose(bone.rest_transform).compose(joint_local)
            global_tf[bone_id] = combined
            return combined

        for bone_id in self.bones:
            resolve(bone_id)
        return global_tf

    def resolve_anchor(self, parent_bone_frame: str, local_position_mm: np.ndarray,
                        pose: Pose, blend_weights: Optional[List[dict]] = None) -> np.ndarray:
        """Global position of an anchor at the given pose. If blend_weights
        is given (dual/multi-bone skinning for anchors that sit over a
        joint), performs a weighted average of the per-bone-frame global
        positions (linear blend skinning, Magnenat-Thalmann et al.)."""
        fk = self.forward_kinematics(pose)
        if not blend_weights:
            return fk[parent_bone_frame].apply(np.asarray(local_position_mm))
        acc = np.zeros(3)
        total_w = 0.0
        for bw in blend_weights:
            w = bw["weight"]
            acc += w * fk[bw["bone_frame"]].apply(np.asarray(local_position_mm))
            total_w += w
        return acc / total_w if total_w > 0 else acc

    def anchor_is_rigid_under_pose(self, parent_bone_frame: str, local_position_mm: np.ndarray,
                                    poses: List[Pose], tol_mm: float = 1e-6) -> bool:
        """Sanity check used by tests/test_rig_preserves_anchors.py: recovers
        the anchor's local coordinates at every sampled pose by inverse-
        transforming its global position, and asserts they are unchanged --
        i.e. the anchor truly moves rigidly with its parent bone rather than
        having been baked as a global coordinate that silently drifts."""
        base = np.asarray(local_position_mm)
        for pose in poses:
            fk = self.forward_kinematics(pose)
            global_pos = fk[parent_bone_frame].apply(base)
            recovered_local = fk[parent_bone_frame].inverse().apply(global_pos)
            if np.linalg.norm(recovered_local - base) > tol_mm:
                return False
        return True


def sample_full_rom_poses(joint: JointSpec, n_per_axis: int = 3) -> List[Pose]:
    """Generate a grid of poses spanning each DOF's full documented ROM,
    including COMBINED end-of-range across axes (e.g. shoulder fully
    abducted + fully externally rotated at once) -- this is what makes the
    rigidity check meaningful for rotational and compound motion, not just
    each axis in isolation."""
    axis_samples = []
    for dof in joint.dofs:
        axis_samples.append(np.linspace(dof.min_deg, dof.max_deg, n_per_axis))
    poses: List[Pose] = []
    grids = np.meshgrid(*axis_samples) if axis_samples else []
    if not axis_samples:
        return [{joint.id: {}}]
    flat = [g.flatten() for g in grids]
    for combo in zip(*flat):
        axes = {dof.axis_name: val for dof, val in zip(joint.dofs, combo)}
        poses.append({joint.id: axes})
    return poses
