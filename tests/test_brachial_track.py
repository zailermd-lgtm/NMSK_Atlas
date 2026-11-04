"""Upper-arm rules on synthetic sections (scripts/cryo/vhf_brachial_track.py, Q56 second half).

The rules that are specific to this tracker and that the Visible Human data cannot test on its own:
the FRAME (the deep-arm muscle hull that keeps the arm apart from the chest wall it touches, and the
humerus disc inside it), the arm's LOCAL-CONTRAST lumen rule and its not-muscle-red surround, the
medial-bicipital-groove seed rule, the plausibility gate, and the sign convention of the numeric
relation check that is run on the shipped label volume.
"""
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from scripts.cryo import vhf_brachial_track as bt  # noqa: E402
from scripts.cryo.vhf_nerve_track import Crops, PX  # noqa: E402

H = W = 300
FAT = (215, 185, 140)
MUSCLE = (78, 38, 32)
BONE = (205, 200, 190)
LUMEN = (30, 20, 16)
BONE_RC = (150, 80)                                          # row, col of the synthetic humerus


def _crops(tmp_path, ys):
    levels = {str(y): {"zi": 10, "dcm": "x", "RS": -7.0, "CS": -120.0, "z_ras": y - 885.229, "z_src": y - 800,
                       "windows": {"right": [60, 60 + H, 36, 36 + W]}} for y in ys}
    json.dump({"y_atlas": ys, "levels": levels, "box_atlas": {"right": [95, 240, -140, 30]},
               "origin": [7.769, -885.229, 14.137], "H": 405, "sc": 0.99, "note": ""},
              open(tmp_path / "t_bbox.json", "w"))
    a = np.lib.format.open_memmap(tmp_path / "t_right.npy", mode="w+", dtype=np.uint8,
                                  shape=(len(ys), H, W, 3))
    a.flush()
    return Crops(str(tmp_path / "t"), "right"), a


def _disk(img, r, c, rad_mm, rgb):
    yy, xx = np.ogrid[:img.shape[0], :img.shape[1]]
    m = (yy - r) ** 2 + (xx - c) ** 2 <= (rad_mm / PX) ** 2
    img[m] = rgb
    return m


def _arm_section(groove_rc=None, belly_lumen_rc=None, lateral_lumen_rc=None):
    """A cream (fat) field holding an ARM - a posterior and an anterior muscle lobe with a 12 mm band of
    intermuscular fat between them and a pale 8 mm bone in that band - and, 32 mm away across the fat, a
    third muscle mass standing for the CHEST WALL her arm rests against in these sections."""
    im = np.zeros((H, W, 3), np.uint8)
    im[:] = FAT
    im[40:132, 40:190] = MUSCLE                              # posterior lobe (triceps)
    im[168:260, 40:190] = MUSCLE                             # anterior lobe (biceps/brachialis)
    im[40:260, 285:300] = MUSCLE                             # the chest wall, across the fat
    _disk(im, BONE_RC[0], BONE_RC[1], 8, BONE)               # the humerus in the intermuscular band
    for rc in (groove_rc, belly_lumen_rc, lateral_lumen_rc):
        if rc:
            _disk(im, rc[0], rc[1], 1.8, LUMEN)
    return im


def _frame_rec(crops, y, im, bone_rc):
    hull, cl = bt.deep_arm(im, bone_rc)
    b, dist = bt.bone_disc(im, bone_rc, 12.0, hull, cl)
    rec = {"y": y, "hull": hull, "found": b is not None,
           "dist_mm": np.clip(dist * PX, 0, 255).astype(np.uint8),
           "bone": (b[0], b[1], b[2]) if b else (bone_rc[0], bone_rc[1], 0.0)}
    bx, bz = crops.px_to_atlas(y, rec["bone"][0], rec["bone"][1])
    rec["bone_xz"] = (float(bx), float(bz))
    rec["bone_r_mm"] = rec["bone"][2] * PX
    return rec


# ---------------------------------------------------------------- the frame
def test_deep_arm_hull_holds_the_arm_and_not_the_chest_wall_it_touches(tmp_path):
    """Her arm touches her chest in these sections, so a plain tissue island runs into the thorax. The
    hull is built from the MUSCLE class, whose two masses are 55 mm apart, well beyond the closing."""
    crops, _ = _crops(tmp_path, [440])
    im = _arm_section()
    hull, _ = bt.deep_arm(im, BONE_RC)
    assert hull is not None
    cc = np.nonzero(hull)[1]
    assert cc.max() < 240, "the hull reached the chest-wall muscle at column 285"
    assert hull[BONE_RC], "the hull does not contain the bone it was seeded at"


def test_bone_disc_is_the_largest_inscribed_circle_of_the_pale_class(tmp_path):
    crops, _ = _crops(tmp_path, [440])
    im = _arm_section()
    hull, cl = bt.deep_arm(im, BONE_RC)
    b, _ = bt.bone_disc(im, BONE_RC, 12.0, hull, cl)
    assert b is not None
    assert abs(b[0] - BONE_RC[0]) < 6 and abs(b[1] - BONE_RC[1]) < 6
    assert 6.0 < b[2] * PX < 10.0, f"bone radius {b[2] * PX:.1f} mm is not the 8 mm disc"


# ---------------------------------------------------------------- the arm's lumen rule
def test_lumen_rule_takes_a_dark_dot_in_fat_and_refuses_the_same_dot_inside_a_belly(tmp_path):
    """The rule is LOCAL CONTRAST plus a surround that is not muscle-red. Her arm muscle photographs as
    dark as a thigh lumen, so a dark dot inside a belly must be refused on its surround, not on its
    darkness."""
    crops, _ = _crops(tmp_path, [440])
    im = _arm_section(groove_rc=(150, 145), belly_lumen_rc=(80, 100))
    hull, cl = bt.deep_arm(im, BONE_RC)
    lab = bt.arm_lumina(im, hull, cl)
    got = {}
    for i in range(1, int(lab.max()) + 1):
        mm = lab == i
        if mm.sum() < 5:
            continue
        rc = tuple(int(round(v)) for v in np.array(np.nonzero(mm)).mean(1))
        got[rc] = bt.not_muscle_frac(im, mm, cl)
    groove = [f for rc, f in got.items() if abs(rc[1] - 145) < 6 and abs(rc[0] - 150) < 6]
    belly = [f for rc, f in got.items() if abs(rc[1] - 100) < 6 and abs(rc[0] - 80) < 6]
    assert groove and groove[0] > 0.9, "the lumen lying in fat was not found, or its surround read as muscle"
    assert belly and belly[0] < 0.35, "a dark dot inside a belly passed the not-muscle-red surround rule"


# ---------------------------------------------------------------- the seed rule
def test_groove_seed_is_medial_to_the_humerus_and_ignores_a_lateral_lumen(tmp_path):
    ys = [440]
    crops, arr = _crops(tmp_path, ys)
    #   +x is the subject's right and this is the RIGHT arm, so MEDIAL is the larger COLUMN in the crop
    im = _arm_section(groove_rc=(150, 145), lateral_lumen_rc=(150, 48))
    arr[0] = im
    arr.flush()
    rec = _frame_rec(crops, 440, im, BONE_RC)
    frame = {440: rec}
    c = bt.groove_lumen(crops, frame, "right", 440)
    assert c is not None, "the medial groove lumen was not seeded"
    assert c["medial_mm"] > 0, "the seed is not medial to the photographed humerus"
    assert bt.SEED_MED_MM[0] <= c["medial_mm"] <= bt.SEED_MED_MM[1]
    pr, pc = crops.atlas_to_px(440, c["x"], c["z"])
    assert pc > BONE_RC[1], "the lateral decoy was seeded instead of the medial groove lumen"


# ---------------------------------------------------------------- the plausibility gate
def test_gate_nulls_a_section_more_than_twice_off_and_a_fragment():
    assert bt.gate("artery", 4.2, 60, 60) is None
    assert "twice" in bt.gate("artery", 11.0, 60, 60)
    assert "far under" in bt.gate("median_n", 1.2, 60, 60)
    assert "too short" in bt.gate("ulnar_n", 4.0, 8, 60)
    assert "too short" in bt.gate("radial_n", 4.0, 60, 12)


# ---------------------------------------------------------------- the numeric relation check
def test_relation_signs_are_lateral_positive_and_anterior_positive_on_the_right():
    bands = {"440..460": {"brachial_a_r": {"x": 180.0, "z": -30.0},
                          "median_n": {"x": 186.0, "z": -28.0},
                          "ulnar_n": {"x": 172.0, "z": -36.0}},
             "340..360": {"brachial_a_r": {"x": 200.0, "z": -50.0},
                          "median_n": {"x": 194.0, "z": -48.0},
                          "ulnar_n": {"x": 188.0, "z": -60.0}}}
    rel = bt.relations_from_volume(bands, "brachial_a_r", "right")
    assert rel["440..460"]["median_n"]["lateral_mm"] == 6.0      # lateral high in the arm
    assert rel["340..360"]["median_n"]["lateral_mm"] == -6.0     # medial at the elbow
    assert rel["340..360"]["ulnar_n"]["lateral_mm"] < 0 and rel["340..360"]["ulnar_n"]["anterior_mm"] < 0


def test_merge_legs_keeps_the_tracked_level_when_the_two_legs_disagree():
    down = [{"y": 460, "gap": False, "x": 1.0, "z": 2.0}, {"y": 459, "gap": True, "x": 1.0, "z": 2.0}]
    up = [{"y": 460, "gap": True, "x": 9.0, "z": 9.0}, {"y": 461, "gap": False, "x": 3.0, "z": 4.0}]
    rows = bt.merge_legs([down, up])
    assert [r["y"] for r in rows] == [461, 460]
    assert not rows[1]["gap"] and rows[1]["x"] == 1.0
