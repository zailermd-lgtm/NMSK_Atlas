"""The pure rule functions of scripts/cryo/vhm_forearm_muscles_from_cryo.py on synthetic input whose answer is known
by construction: the level -> torso z mapping, the photo <-> RAS translation (with the bone correction), the scaled
marker table and marker positions, the thumb-side check, the ship-or-merge rule and the bone correction smoothing."""
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from scripts.cryo import vhm_forearm_muscles_from_cryo as fm  # noqa: E402

U, R = np.array([100.0, 100.0]), np.array([100.0, 190.0])
RU, RR = 15.0, 15.0
T = (180.0, 340.0, -5.0, 8.0)                     # (rowB, colB) 1 mm-frame px, (xB, yB) RAS mm
BOX = [180, 1050, 90, 990]


def test_instance_to_torso_z_and_atlas_y():
    assert fm.inst_to_z(1613) == -628.0                                  # top of his CT radius label
    assert abs((fm.inst_to_z(1613) - fm.ORIGIN[1]) - 267.476) < 1e-9     # atlas y = z + 895.476


def test_photo_ras_round_trip_and_handedness():
    pr, pc = np.array([300.0, 500.0]), np.array([200.0, 700.0])
    x, y = fm.photo_to_ras(T, BOX, pr, pc)
    r2, c2 = fm.ras_to_photo(T, BOX, x, y)
    assert np.allclose(r2, pr) and np.allclose(c2, pc)
    assert x[1] < x[0] and y[1] > y[0]          # image right = patient's left (-x), image down = anterior (+y)
    xc, yc = fm.photo_to_ras(T, BOX, pr, pc, corr=(30.0, 0.0))            # a 30 px (10 mm) row correction moves y by -9.9
    assert np.allclose(yc - y, -30.0 / 3.0 * fm.PX1) and np.allclose(xc, x)
    r3, c3 = fm.ras_to_photo(T, BOX, xc, yc, corr=(30.0, 0.0))
    assert np.allclose(r3, pr) and np.allclose(c3, pc)


def test_scaled_rules_and_marker_positions():
    rules = fm.scaled_rules(1.15)
    assert set(rules) == set(fm.HER_RULES)
    anc, em, nm, f0, f1, grp = rules["flexor_carpi_ulnaris"]; anc0, em0, nm0, f00, f10, grp0 = fm.HER_RULES["flexor_carpi_ulnaris"]
    assert anc == anc0 and grp == grp0 and (f0, f1) == (f00, f10) and abs(em - 1.15 * em0) < 1e-9 and abs(nm - 1.15 * nm0) < 1e-9
    e, n = np.array([0.0, 1.0]), np.array([1.0, 0.0])
    pos = fm.marker_positions(U, R, RU, RR, e, n, f=0.10, rules=rules)
    assert "pronator_quadratus" not in pos and "flexor_carpi_ulnaris" in pos
    exp = U + e * (em / fm.PX + np.sign(em) * RU) + n * (nm / fm.PX + np.sign(nm) * RU)
    assert np.allclose(pos["flexor_carpi_ulnaris"], exp)
    assert np.dot(np.array(pos["extensor_carpi_ulnaris"]) - U, n) < 0
    assert set(fm.marker_positions(U, R, RU, RR, e, n, f=0.1, rules=rules, active_only=False)) == set(rules)


def test_thumb_side():
    P = np.array([[0.0, 0.0], [10.0, 0.5], [20.0, -0.5], [30.0, 0.0], [-8.0, 25.0]])   # four in a line, the thumb 25 mm off it
    off, i = fm.thumb_side(P, n_ras=(0.0, 1.0))
    assert i == 4 and abs(off - 25.0) < 1.0
    off2, i2 = fm.thumb_side(P, n_ras=(0.0, -1.0))
    assert i2 == 4 and abs(off2 + 25.0) < 1.0


def test_ship_or_merge():
    groups = {"a": "flexor", "b": "flexor", "c": "flexor", "x": "extensor"}
    supp = {"a|b": {"levels": 50, "frac_levels_ratio_ge_1.8": 0.9}, "b|c": {"levels": 50, "frac_levels_ratio_ge_1.8": 0.4},
            "a|x": {"levels": 50, "frac_levels_ratio_ge_1.8": 0.1},          # a rule line between compartments: ignored
            "a|c": {"levels": 3, "frac_levels_ratio_ge_1.8": 0.0}}           # too few shared levels: ignored
    ship, weak = fm.ship_or_merge(supp, groups)
    assert ship == {"a", "x"} and weak == [("b", "c", 0.4)]


def test_bone_correction_smooths_and_holds():
    track = {j: {} for j in range(10)}
    residual = {"radius": {j: [3.0, 0.0] for j in range(2, 8)}, "ulna": {j: [1.0, 0.0] for j in range(2, 8)}}
    residual["radius"][5] = [30.0, 0.0]                                    # one outlier level
    corr = fm.bone_correction(track, residual, size=5)
    assert abs(corr[4][0] - 2.0 / fm.PX) < 1e-6 and abs(corr[5][0] - 2.0 / fm.PX) < 1e-6   # mean of both bones, outlier removed
    assert abs(corr[0][0] - corr[2][0]) < 1e-6 and abs(corr[9][0] - corr[7][0]) < 1e-6      # held beyond the ends
