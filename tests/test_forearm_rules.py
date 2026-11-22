"""The pure rule functions of scripts/cryo/vhf_forearm_muscles_from_cryo.py on synthetic bone discs whose answer is
known by construction: the ulna-radius frame (flexor side away from the ulna's subcutaneous border), the marker
positions (mm from the disc surface, seeded only inside their f-window), the compartment map, the seed snap, the
level fraction and the frame-height fixed point."""
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from scripts.cryo import vhf_forearm_muscles_from_cryo as fm  # noqa: E402

U, R = np.array([100.0, 100.0]), np.array([100.0, 190.0])         # ulna left, radius right (rows, cols), 30 mm apart
RU, RR = 15.0, 15.0                                                # 5 mm disc radii (px)


def test_bone_frame_points_away_from_the_ulnar_skin():
    e, n, d = fm.bone_frame(U, R, skin_dir_at_ulna=(-30.0, 0.0))    # skin above the ulna -> flexor side is below
    assert np.allclose(e, (0, 1)) and abs(d - 90) < 1e-9
    assert np.allclose(n, (1, 0))
    e2, n2, _ = fm.bone_frame(U, R, skin_dir_at_ulna=(+30.0, 0.0))
    assert np.allclose(n2, (-1, 0)) and np.allclose(e2, e)


def test_marker_positions_offsets_add_the_disc_radius_and_respect_the_f_window():
    e, n = np.array([0.0, 1.0]), np.array([1.0, 0.0])
    pos = fm.marker_positions(U, R, RU, RR, e, n, f=0.10, active_only=True)
    assert "pronator_quadratus" not in pos and "flexor_carpi_ulnaris" in pos         # PQ starts at f 0.82
    anc, em, nm, *_ = fm.MARKER_RULES["flexor_carpi_ulnaris"]
    assert anc == "U"
    exp = U + e * (em / fm.PX + np.sign(em) * RU) + n * (nm / fm.PX + np.sign(nm) * RU)
    assert np.allclose(pos["flexor_carpi_ulnaris"], exp)
    assert np.dot(np.array(pos["flexor_carpi_ulnaris"]) - U, n) > 0                 # on the flexor side
    assert np.dot(np.array(pos["extensor_carpi_ulnaris"]) - U, n) < 0               # on the extensor side
    allp = fm.marker_positions(U, R, RU, RR, e, n, f=0.10, active_only=False)
    assert set(allp) == set(fm.MARKER_RULES)


def test_compartments_flexor_lateral_extensor():
    e, n = np.array([0.0, 1.0]), np.array([1.0, 0.0])
    comp = fm.compartments((200, 300), U, R, RU, RR, e, n)
    assert comp[150, 145] == fm.GROUP_ID["flexor"]        # flexor side, between the bones
    assert comp[50, 145] == fm.GROUP_ID["extensor"]       # extensor side, between the bones
    assert comp[100, 250] == fm.GROUP_ID["lateral"]       # beyond the radius: the mobile wad
    assert comp[100, 40] == fm.GROUP_ID["flexor"]         # the ulna's medial face (s < 0, |t| < ulna radius)
    assert comp[30, 250] == fm.GROUP_ID["extensor"]       # beyond the radius but > 14 mm behind it
    assert set(np.unique(comp)) == set(fm.GROUP_ID.values())


def test_snap_and_level_fraction_and_corrected_y():
    reg = np.zeros((50, 50), bool); reg[20:30, 20:30] = True
    assert fm.snap((25, 25), reg) == (25, 25)
    assert fm.snap((25, 33), reg) == (25, 29)
    assert fm.snap((25, 48), reg) is None                 # farther than 15 px
    assert fm.level_fraction(17, 17, 177) == 0.0 and abs(fm.level_fraction(97, 17, 177) - 0.5) < 1e-9
    assert fm.level_fraction(3, 3, 3) == 0.0
    assert fm.corrected_y(-600.0, np.array([]), np.array([])) == -600.0 + 885.229
    cy = np.array([100.0, 300.0]); co = np.array([70.0, 70.0])
    assert abs(fm.corrected_y(-600.0, cy, co) - (-600.0 - 70.0 + 885.229)) < 1e-6
