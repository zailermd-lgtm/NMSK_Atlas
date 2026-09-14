"""Coordinate frames, rigid transforms, and 1mm-resolution curve/surface
sampling utilities.

Conventions (see schema/common.schema.json and docs/ARCHITECTURE.md):
  - Units: millimetres throughout.
  - Global frame: subject in standard anatomical position, origin at the
    midpoint of the hip joint centers, +X = right, +Y = superior,
    +Z = anterior (right-handed).
  - Every bone owns a rigid local frame; all attachment points are stored
    in their parent bone's local frame and only ever converted to global
    coordinates on demand, at a specific pose.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

import numpy as np

Vec3 = np.ndarray  # shape (3,)


def vec3(x: float, y: float, z: float) -> Vec3:
    return np.array([x, y, z], dtype=float)


@dataclass(frozen=True)
class Transform:
    """A rigid transform (rotation + translation), row-vector convention:
    global_point = local_point @ R.T + t
    """
    R: np.ndarray  # (3,3) rotation matrix
    t: np.ndarray  # (3,) translation, mm

    @staticmethod
    def identity() -> "Transform":
        return Transform(np.eye(3), np.zeros(3))

    def apply(self, points: np.ndarray) -> np.ndarray:
        """points: (...,3) local -> (...,3) global"""
        points = np.asarray(points, dtype=float)
        return points @ self.R.T + self.t

    def inverse(self) -> "Transform":
        Rt = self.R.T
        return Transform(Rt, -Rt @ self.t)

    def compose(self, other: "Transform") -> "Transform":
        """self ∘ other: apply `other` first, then `self` (parent.compose(child))."""
        return Transform(self.R @ other.R, self.R @ other.t + self.t)

    @staticmethod
    def from_axis_angle(axis: Vec3, angle_deg: float, t: Vec3 = None) -> "Transform":
        axis = axis / (np.linalg.norm(axis) + 1e-12)
        theta = np.radians(angle_deg)
        K = np.array([
            [0, -axis[2], axis[1]],
            [axis[2], 0, -axis[0]],
            [-axis[1], axis[0], 0],
        ])
        R = np.eye(3) + np.sin(theta) * K + (1 - np.cos(theta)) * (K @ K)
        return Transform(R, np.zeros(3) if t is None else np.asarray(t, dtype=float))


# ---------------------------------------------------------------------------
# Landmarks scale with the bone they sit on (Q43, 2026-09-14).
#
# `data/skeleton/bones.json` stores every landmark as position_local_mm in
# the bone's local frame: origin at a joint centre, +Y the long axis. Those
# millimetres were measured on the Visible Human MALE, so on a subject whose
# femur is 0.88 of his every distal landmark lands 50-70 mm past the end of
# the bone. The record therefore also carries the male's bone length along
# that same axis (`reference_length_mm`), and a consumer that has MEASURED
# the subject's own length stretches or shrinks the along-axis coordinate by
# the ratio. The across-axis coordinates stay in millimetres: bone widths do
# not scale with length between these two bodies (her pelvis is as large as
# his), and the frame's transverse axes are fitted, not assumed.
# ---------------------------------------------------------------------------

LONG_AXIS = 1   # +Y of every ISB-style bone frame in bones.json is the long axis


def bone_length_along_axis(mesh: np.ndarray, origin: Vec3, axis: Vec3,
                           lo_pct: float = 1.0, hi_pct: float = 99.0) -> float:
    """Extent of a bone mesh along a unit axis, 1st to 99th percentile of its
    vertices. That is the definition `reference_length_mm` was measured with,
    so the same function must measure the subject; the percentiles keep one
    stray vertex from stretching every landmark on the bone."""
    proj = (np.asarray(mesh, float) - np.asarray(origin, float)) @ np.asarray(axis, float)
    return float(np.percentile(proj, hi_pct) - np.percentile(proj, lo_pct))


TRUNCATION_GUARD = (0.6, 1.5)   # measured/reference outside this band = a truncated or mis-fitted bone: factor 1


def scale_local_to_length(local_mm, reference_length_mm, measured_length_mm,
                          axis: int = LONG_AXIS) -> np.ndarray:
    """A landmark's local coordinates on a subject whose bone measures
    `measured_length_mm` where the record's were written for
    `reference_length_mm`: the along-axis component is multiplied by
    measured/reference, the other two are returned unchanged. Either length
    missing, non-finite or non-positive means no information, and the
    coordinates come back exactly as stored (factor 1); so does a ratio
    outside TRUNCATION_GUARD (a femur that leaves the scan at mid-thigh
    measures 0.34 of a femur and must not squash its landmarks)."""
    local = np.array(local_mm, dtype=float)
    if reference_length_mm is None or measured_length_mm is None:
        return local
    ref, meas = float(reference_length_mm), float(measured_length_mm)
    if not (np.isfinite(ref) and np.isfinite(meas)) or ref <= 0 or meas <= 0:
        return local
    if not (TRUNCATION_GUARD[0] <= meas / ref <= TRUNCATION_GUARD[1]):
        return local          # a bone cut by the scan's field of view measures its truncation, not its length
    local[..., axis] *= meas / ref
    return local


def local_to_world(local_mm, origin: Vec3, basis: np.ndarray,
                   reference_length_mm=None, measured_length_mm=None) -> np.ndarray:
    """origin + local @ basis, with the along-axis scaling above applied
    first. `basis` rows are the frame's X, Y, Z in world coordinates, as
    scripts/audit_landmarks_vs_geometry.py:build_frames returns them."""
    local = scale_local_to_length(local_mm, reference_length_mm, measured_length_mm)
    return np.asarray(origin, float) + local @ np.asarray(basis, float)


def resample_polyline(points: Sequence[Vec3], spacing_mm: float = 1.0) -> np.ndarray:
    """Arc-length resample a polyline (list of 3D points) to a uniform
    `spacing_mm` step. This is the core '1mm resolution' primitive: every
    generated centerline (fiber, nerve, vessel) is produced by defining a
    small number of anatomically meaningful control points and resampling
    through this function, rather than hand-authoring dense point data.
    """
    pts = np.asarray(points, dtype=float)
    if len(pts) < 2:
        return pts
    seg = np.diff(pts, axis=0)
    seg_len = np.linalg.norm(seg, axis=1)
    total = seg_len.sum()
    if total <= 0:
        return pts[:1]
    n_samples = max(2, int(round(total / spacing_mm)) + 1)
    cum = np.concatenate([[0.0], np.cumsum(seg_len)])
    targets = np.linspace(0.0, total, n_samples)
    out = np.zeros((n_samples, 3))
    for i, s in enumerate(targets):
        idx = np.searchsorted(cum, s, side="right") - 1
        idx = min(idx, len(seg_len) - 1)
        local = 0.0 if seg_len[idx] == 0 else (s - cum[idx]) / seg_len[idx]
        out[i] = pts[idx] + local * seg[idx]
    return out


def catmull_rom_spline(control_points: Sequence[Vec3], samples_per_segment: int = 12) -> np.ndarray:
    """Smooth interpolating spline through control points (used for nerve/
    vessel/muscle-tendon paths that pass through documented via-points)."""
    pts = np.asarray(control_points, dtype=float)
    if len(pts) < 3:
        return pts
    # duplicate endpoints so the curve passes through the first/last control points
    padded = np.vstack([pts[0], pts, pts[-1]])
    out = []
    for i in range(1, len(padded) - 2):
        p0, p1, p2, p3 = padded[i - 1], padded[i], padded[i + 1], padded[i + 2]
        for s in np.linspace(0, 1, samples_per_segment, endpoint=False):
            s2, s3 = s * s, s * s * s
            pt = 0.5 * (
                (2 * p1)
                + (-p0 + p2) * s
                + (2 * p0 - 5 * p1 + 4 * p2 - p3) * s2
                + (-p0 + 3 * p1 - 3 * p2 + p3) * s3
            )
            out.append(pt)
    out.append(pts[-1])
    return np.array(out)


def polygon_seed_points(polygon: Sequence[Vec3], spacing_mm: float = 1.0) -> np.ndarray:
    """1mm-spaced seed points filling a (roughly planar) polygon footprint —
    used to seed one fascicle centerline per point along a muscle
    compartment's origin surface."""
    poly = np.asarray(polygon, dtype=float)
    if len(poly) < 3:
        return poly
    centroid = poly.mean(axis=0)
    normal = np.cross(poly[1] - poly[0], poly[2] - poly[0])
    n = np.linalg.norm(normal)
    normal = normal / n if n > 1e-9 else np.array([0.0, 0.0, 1.0])
    ref = np.array([1.0, 0.0, 0.0]) if abs(normal[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    u = np.cross(normal, ref)
    u /= np.linalg.norm(u)
    v = np.cross(normal, u)
    poly2d = np.stack([(p - centroid) @ u for p in poly]), np.stack([(p - centroid) @ v for p in poly])
    us, vs = poly2d
    umin, umax, vmin, vmax = us.min(), us.max(), vs.min(), vs.max()
    n_u = max(1, int((umax - umin) / spacing_mm) + 1)
    n_v = max(1, int((vmax - vmin) / spacing_mm) + 1)
    seeds = []
    for i in range(n_u):
        for j in range(n_v):
            uu = umin + i * spacing_mm
            vv = vmin + j * spacing_mm
            if _point_in_poly2d(uu, vv, us, vs):
                seeds.append(centroid + uu * u + vv * v)
    if not seeds:
        seeds = [centroid]
    return np.array(seeds)


def _point_in_poly2d(x: float, y: float, xs: np.ndarray, ys: np.ndarray) -> bool:
    n = len(xs)
    inside = False
    j = n - 1
    for i in range(n):
        if ((ys[i] > y) != (ys[j] > y)) and (
            x < (xs[j] - xs[i]) * (y - ys[i]) / (ys[j] - ys[i] + 1e-12) + xs[i]
        ):
            inside = not inside
        j = i
    return inside
