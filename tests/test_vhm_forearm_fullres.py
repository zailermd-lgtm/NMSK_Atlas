"""Pure functions of scripts/cryo/vhm_forearm_muscles_fullres.py (Q164)."""
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "cryo"))
import vhm_forearm_muscles_fullres as V  # noqa: E402


def test_photo_ras_roundtrip():
    x, y = V.photo_to_ras(np.array([100.0, 250.5]), np.array([40.0, 700.0]), 330.0, -167.0)
    r, c = V.ras_to_photo(x, y, 330.0, -167.0)
    assert np.allclose(r, [100.0, 250.5]) and np.allclose(c, [40.0, 700.0])
    # column to the right = RAS x decreasing, row down = RAS y increasing
    assert x[1] < x[0] and y[1] > y[0]


def test_translation_from_bones_recovers_shift():
    X0, Y0 = 331.0, -168.0
    ct = {}; ph = {}
    for b, (r, c) in {"radius": (300.0, 420.0), "ulna": (380.0, 510.0)}.items():
        ph[b] = (r, c); x, y = V.photo_to_ras(r, c, X0, Y0); ct[b] = (float(x), float(y))
    T = V.translation_from_bones(ph, ct)
    assert abs(T[0] - X0) < 1e-9 and abs(T[1] - Y0) < 1e-9
    assert V.translation_from_bones({}, ct) is None


def test_architecture_volume():
    comps = [{"fiber_architecture": {"physiological_cross_section_area_mm2": 150, "optimal_fascicle_length_mm": 160, "pennation_deg": 0}},
             {"fiber_architecture": {"physiological_cross_section_area_mm2": 100, "optimal_fascicle_length_mm": 50, "pennation_deg": 60}},
             {"fiber_architecture": {"physiological_cross_section_area_mm2": None}}]
    assert math.isclose(V.architecture_volume_cm3(comps), 24.0 + 10.0, rel_tol=1e-9)


def test_normalised_expectations_sum_to_total():
    e = V.normalised_expectations({"a": 1.0, "b": 3.0}, 200.0)
    assert math.isclose(e["a"], 50.0) and math.isclose(e["b"], 150.0)


def test_main_component_fraction_drops_small_islands():
    m = np.zeros((30, 30, 30), bool); m[2:22, 2:22, 2:22] = True            # 8000
    m[25:27, 25:27, 25:27] = True                                            # 8 voxels = 0.1 % -> dropped
    f, n = V.main_component_fraction(m)
    assert n == 2 and f == 1.0
    m[24:29, 24:29, 24:29] = True                                            # 125 voxels (> 1 %) -> kept
    f, _ = V.main_component_fraction(m)
    assert math.isclose(f, 8000 / 8125)


def test_gate():
    assert V.gate(10.0, 10.0, 1.0)[0]
    assert not V.gate(25.0, 10.0, 1.0)[0]
    assert not V.gate(4.0, 10.0, 1.0)[0]
    assert not V.gate(10.0, 10.0, 0.95)[0]
    assert not V.gate(10.0, 0.0, 1.0)[0]


def test_bone_frame_points_away_from_ulna_skin():
    e, n, d = V.bone_frame((10.0, 10.0), (10.0, 40.0), skin_dir_at_ulna=(5.0, 0.0))
    assert np.allclose(e, [0, 1]) and d == 30.0 and n[0] < 0


def test_ring_positions_depth_and_window():
    rules = {"flexor_carpi_ulnaris": ("U", -8, 4, 0.0, 0.85, "flexor")}
    out = V.ring_positions((0.0, 0.0), np.array([0.0, 1.0]), np.array([1.0, 0.0]), lambda ang: 40.0, 0.5, rules,
                           ring={"flexor_carpi_ulnaris": (90.0, 0.25)})
    assert np.allclose(out["flexor_carpi_ulnaris"], (30.0, 0.0))
    assert V.ring_positions((0.0, 0.0), np.array([0.0, 1.0]), np.array([1.0, 0.0]), lambda ang: 40.0, 0.9, rules,
                            ring={"flexor_carpi_ulnaris": (90.0, 0.25)}) == {}
