"""Pure functions of scripts/cryo/vhm_forearm_muscles_v3.py (Q165)."""
import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "cryo"))
import vhm_forearm_muscles_v3 as V  # noqa: E402

T = V.TISSUE


def test_tissue_map_only_colour_muscle_is_muscle_and_bone_wins():
    cls = np.array([[3, 2, 4, 1], [3, 5, 3, 0]])
    isl = np.array([[1, 1, 1, 1], [1, 1, 1, 0]], bool)
    bone = np.array([[0, 0, 0, 0], [0, 0, 1, 0]], bool)
    t = V.tissue_map(cls, isl, bone)
    assert t.tolist() == [[T["muscle"], T["fat"], T["pale"], T["other"]], [T["muscle"], T["bone"], T["bone"], T["outside"]]]


def test_muscle_fraction_excludes_bone_and_outside():
    t = np.array([T["muscle"], T["muscle"], T["fat"], T["bone"], T["bone"], T["outside"]])
    assert math.isclose(V.muscle_fraction_nonbone(t), 2 / 3)


def test_separability():
    f, ov = V.separability(np.full(100, 80.0) + np.arange(100) % 5, np.full(100, 170.0) + np.arange(100) % 5)
    assert f > 100 and ov == 0.0
    f2, ov2 = V.separability(np.arange(100.0), np.arange(50.0, 150.0))
    assert f2 < 2 and ov2 > 0.3


def test_paleness_residual_marks_a_thin_pale_line():
    im = np.zeros((40, 40, 3), np.uint8); im[..., 0] = 90; im[..., 1] = 45; im[..., 2] = 38      # red belly, g/r 0.5
    im[:, 20] = (160, 150, 120)                                                                   # 1 px pale septum
    d = V.paleness_residual(im, np.ones((40, 40), bool), sigma_px=0)
    assert d[:, 20].min() > 0.3 and abs(d[:, 5]).max() < 1e-6


def test_elevation_high_at_edge_and_ridge_low_in_belly():
    m = np.zeros((31, 31), bool); m[5:26, 5:26] = True
    r = np.zeros((31, 31), np.float32); r[15, 5:26] = 1.0
    E = V.elevation(m, r, ds=0.5, dmax_mm=3.0, w_ridge=0.5)
    assert E[5, 10] > E[10, 10] and E[15, 15] > E[10, 15]
    assert math.isclose(float(E[10, 12]), 0.5 * (1 - min(6 * 0.5, 3.0) / 3.0))


def test_boundary_septum_fractions():
    L = np.zeros((12, 12), int); L[2:10, 2:6] = 1; L[2:10, 6:10] = 2
    onsep = np.zeros((12, 12), bool); onsep[:, 5:7] = True          # the septum between the two
    out = V.boundary_septum_fractions(L, onsep, min_px=1)
    f_all, f_ct, n = out[1]
    assert f_ct == 1.0 and 0 < f_all < 1 and n == 8 * 2 + 2 * 2      # left+right columns, top/bottom middle


def test_scale_factor_and_mismatch():
    assert math.isclose(V.scale_factor({"a": 300.0, "b": 100.0}, {"a": 100.0, "b": 100.0}), 2.0)
    with pytest.raises(ValueError):
        V.scale_factor({"a": 1.0}, {"b": 1.0})


def test_gate_v3():
    assert V.gate_v3(10, 10, 1.0, 0.6)[0]
    assert not V.gate_v3(10, 10, 1.0, 0.4)[0]
    assert not V.gate_v3(30, 10, 1.0, 0.9)[0]
    assert not V.gate_v3(10, 10, 0.9, 0.9)[0]
    ok, why = V.gate_v3(10, 10, 1.0, 0.9, out_of_range=True)
    assert not ok and "OUT OF RANGE" in why


def test_move_to_basin():
    E = np.ones((20, 20)); E[12, 13] = 0.0; allowed = np.ones((20, 20), bool)
    assert V.move_to_basin((10, 10), E, allowed, 4) == (12, 13)
    assert V.move_to_basin((10, 10), E, np.zeros((20, 20), bool), 4) is None


def test_mesh_volume_unit_cube():
    v = np.array([[0, 0, 0], [10, 0, 0], [10, 10, 0], [0, 10, 0], [0, 0, 10], [10, 0, 10], [10, 10, 10], [0, 10, 10]], float)
    f = np.array([[0, 2, 1], [0, 3, 2], [4, 5, 6], [4, 6, 7], [0, 1, 5], [0, 5, 4], [1, 2, 6], [1, 6, 5], [2, 3, 7], [2, 7, 6], [3, 0, 4], [3, 4, 7]])
    assert math.isclose(V.mesh_volume_cm3(v, f), 1.0)
