"""The pure shoulder-girdle split rule (scripts/cryo/split_shoulder_girdle.py) on a synthetic scapula whose answer is
known by construction: a thin blade with a lateral border, a humeral head touching it at the glenoid level, a dorsal
muscle slab and a belly lateral of the border."""
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from scripts.cryo import split_shoulder_girdle as sg  # noqa: E402

NZ, NR, NC = 120, 80, 120     # (z, row, col); lateral = smaller col (patient's right, lateral_sign -1)
Z_IA, Z_TOP, Z_HEAD = 10, 110, 85


def _synthetic():
    scap = np.zeros((NZ, NR, NC), bool); scap[Z_IA:Z_TOP + 1, 40:44, 30:91] = True        # blade, lateral border at col 30
    hum = np.zeros_like(scap); hum[Z_HEAD:Z_TOP + 1, 30:52, 22:29] = True                   # head within 6 mm of the border
    hum[Z_IA:Z_HEAD, 30:52, 5:12] = True                                                     # shaft, far from the blade
    merged = np.zeros_like(scap)
    merged[Z_IA:91, 44:55, 20:91] = True                                                     # dorsal slab
    merged[Z_IA:81, 30:55, 10:29] = True                                                     # belly lateral of the border
    return scap, hum, merged


def test_levels_come_from_the_blade_and_the_humeral_head():
    scap, hum, _ = _synthetic()
    lv = sg.side_levels(scap, hum)
    assert lv["z_ia"] == Z_IA and lv["z_top"] == Z_TOP
    assert lv["z_gl"] == Z_HEAD                                    # lowest level where the head touches the scapula
    assert abs(lv["z_tm"] - (Z_IA + (Z_HEAD - Z_IA) / 3)) < 1e-9   # top of the lower third of the lateral border
    assert abs(lv["z_spine"] - (Z_IA + 0.78 * (Z_TOP - Z_IA))) < 1e-9


def test_slice_frame_points_medially_and_dorsally():
    scap, _, _ = _synthetic()
    P, u, n = sg.slice_frame(scap[50], -1)
    assert abs(P[1] - 32) < 1.5 and abs(P[0] - 41.5) < 1e-9        # the lateral tip of the blade
    assert u[1] > 0.99 and n[0] > 0.99                             # medial = +col here, dorsal = +row


def test_split_puts_each_muscle_where_grays_says():
    scap, hum, merged = _synthetic()
    lv = sg.side_levels(scap, hum)
    mk = sg.teres_markers(merged, scap, -1, lv)
    lab = sg.assign_to_markers(merged, mk)
    assert ((lab > 0) == merged).all()                              # every merged voxel assigned, nothing outside
    assert lab[60, 48, 80] == 1                                     # fossa, far medial: infraspinatus
    assert lab[60, 48, 34] == 2                                     # dorsal lateral border, upper two thirds: teres minor
    assert lab[60, 40, 15] == 3                                     # belly lateral of the border: teres major
    assert lab[20, 48, 34] == 3                                     # lower third of the lateral border: teres major
    assert lab[20, 48, 85] == 3 or lab[20, 48, 85] == 1             # inferior-angle level, medial: not teres minor
    assert (lab[:int(lv["z_tm"])] != 2).all()                      # no teres minor below the inferior-angle third
    vols = {l: int((lab == l).sum()) for l in (1, 2, 3)}
    assert min(vols.values()) > 0 and vols[2] < vols[3]                # teres minor is the smallest of the pair


def test_rhomboid_cut_follows_the_oblique_line():
    mask = np.zeros((120, 10, 100), bool); mask[40:110, 3:7, 20:80] = True
    minor = sg.rhomboid_cut(mask, p_sp=(100.0, 70.0), p_root=(80.0, 30.0))   # T1 spinous process -> spine root
    assert minor[105, 5, 60] and not minor[60, 5, 40]
    assert minor[91, 5, 50] and not minor[89, 5, 50]                          # the line passes z = 90 at col 50
    assert (minor & ~mask).sum() == 0
