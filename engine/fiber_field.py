"""Procedural muscle-fiber field generator.

Given one `functional_compartments[i]` entry from a muscle's data (an
architecture type, a pennation angle, an origin seed region, and an
insertion anchor), generates a set of 1mm-resolution fascicle centerlines —
the actual per-fiber-bundle direction data the task asked for — without
hand-authoring individual fiber curves.

Each output fascicle carries:
  - its compartment_id (so "the posterior third of deltoid" is a queryable
    subset of one muscle's geometry — the functional-grouping requirement),
  - its polyline (1mm-spaced points, in the *origin bone's* local frame so
    it can be re-posed by the rig),
  - its NMJ marker position.

Architecture types implemented per the classic muscle-architecture
classification (Lieber & Fridén 2000; also see docs/SOURCES.md):
  parallel_strap / fusiform  -> fibers run origin->insertion directly
                                 (fusiform bulges at the belly midpoint)
  unipennate / bipennate /
  multipennate                -> fibers attach to an internal aponeurosis at
                                 `pennation_deg` from the muscle's long axis
  circular                    -> fibers form concentric loops (sphincters)
  convergent_triangular       -> broad origin fan converging to a point/
                                 narrow tendon insertion (e.g. pectoralis)
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import List

import numpy as np

from . import geometry as geo


@dataclass
class Fascicle:
    compartment_id: str
    points_mm: np.ndarray  # (N,3) local frame of the origin bone, 1mm spacing
    nmj_position_mm: np.ndarray  # (3,)
    pennation_deg: float


def _long_axis(origin_pt: np.ndarray, insertion_pt: np.ndarray) -> np.ndarray:
    d = insertion_pt - origin_pt
    n = np.linalg.norm(d)
    return d / n if n > 1e-9 else np.array([0.0, 0.0, 1.0])


def _pennate_path(seed: np.ndarray, insertion_pt: np.ndarray, pennation_deg: float,
                   long_axis: np.ndarray) -> List[np.ndarray]:
    """Route a fiber from `seed` onto a virtual internal aponeurosis running
    toward `insertion_pt`, meeting the long axis at `pennation_deg`."""
    to_insertion = insertion_pt - seed
    length = np.linalg.norm(to_insertion)
    if length < 1e-9:
        return [seed, insertion_pt]
    # Aponeurosis point: travel along the long axis, then fiber cuts in at the
    # pennation angle to reach it -- classic pennate geometry construction.
    theta = np.radians(pennation_deg)
    apo_len = length * np.cos(theta) if theta > 1e-6 else length
    apo_point = seed + long_axis * apo_len
    return [seed, apo_point, insertion_pt]


def generate_compartment_fibers(
    compartment_id: str,
    architecture_type: str,
    pennation_deg: float,
    seed_region_local_mm: np.ndarray,
    origin_anchor_local_mm: np.ndarray,
    insertion_anchor_local_mm: np.ndarray,
    nmj_fraction: float = 0.5,
    resolution_mm: float = 1.0,
) -> List[Fascicle]:
    """Generate the compartment's fascicle field. Coordinates are all in the
    same (origin-bone) local frame; `rig.py` is responsible for reposing
    them via forward kinematics when a global pose is needed.
    """
    seeds = geo.polygon_seed_points(seed_region_local_mm, spacing_mm=resolution_mm) \
        if len(seed_region_local_mm) >= 3 else np.atleast_2d(origin_anchor_local_mm)

    long_axis = _long_axis(origin_anchor_local_mm, insertion_anchor_local_mm)
    fascicles: List[Fascicle] = []

    for seed in seeds:
        if architecture_type in ("parallel_strap",):
            control = [seed, insertion_anchor_local_mm]
        elif architecture_type == "fusiform":
            mid = (seed + insertion_anchor_local_mm) / 2.0
            # belly bulge perpendicular to the long axis
            perp = np.cross(long_axis, np.array([0.0, 0.0, 1.0]))
            if np.linalg.norm(perp) < 1e-6:
                perp = np.cross(long_axis, np.array([1.0, 0.0, 0.0]))
            perp /= (np.linalg.norm(perp) + 1e-12)
            bulge = mid + perp * (0.06 * np.linalg.norm(insertion_anchor_local_mm - seed))
            control = [seed, bulge, insertion_anchor_local_mm]
        elif architecture_type in ("unipennate", "bipennate", "multipennate"):
            control = _pennate_path(seed, insertion_anchor_local_mm, pennation_deg, long_axis)
        elif architecture_type == "convergent_triangular":
            control = [seed, insertion_anchor_local_mm]
        elif architecture_type == "circular":
            # loop around the centroid of the seed region at this seed's radius
            centroid = seed_region_local_mm.mean(axis=0) if len(seed_region_local_mm) else seed
            radius_vec = seed - centroid
            radius = np.linalg.norm(radius_vec)
            control = []
            for a in np.linspace(0, 2 * np.pi, 24):
                axis_hint = np.array([0.0, 0.0, 1.0])
                u = radius_vec / (radius + 1e-9)
                v = np.cross(axis_hint, u)
                control.append(centroid + radius * (np.cos(a) * u + np.sin(a) * v))
            control.append(control[0])
        else:
            control = [seed, insertion_anchor_local_mm]

        path = geo.catmull_rom_spline(control, samples_per_segment=8) if len(control) >= 3 else np.array(control)
        resampled = geo.resample_polyline(path, spacing_mm=resolution_mm)
        idx = int(round(nmj_fraction * (len(resampled) - 1))) if len(resampled) > 1 else 0
        fascicles.append(Fascicle(
            compartment_id=compartment_id,
            points_mm=resampled,
            nmj_position_mm=resampled[idx] if len(resampled) else seed,
            pennation_deg=pennation_deg,
        ))
    return fascicles


def compartment_fascicle_count_from_pcsa(pcsa_mm2: float, mean_fiber_cross_section_mm2: float = 0.005) -> int:
    """Estimate a physiologically-plausible fascicle sampling count from
    physiological cross-sectional area, purely for density/consistency
    checks (tests/test_fiber_field_coverage.py) -- NOT a claim that this
    equals the true individual-fiber count (a real muscle has on the order
    of 10^4-10^6 individual fibers per PCSA cm^2; we sample representative
    fascicle bundles at 1mm seed spacing instead)."""
    if pcsa_mm2 <= 0:
        return 0
    return max(1, int(pcsa_mm2 / (mean_fiber_cross_section_mm2 * 200)))
