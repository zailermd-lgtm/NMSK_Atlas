"""Q179: her photo-tracked thigh/knee structures -- audit tools (output checks skip when the outputs are absent)."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from scripts.cryo import vhm_stream_leg_crops as STREAM  # noqa: E402
from scripts.cryo import vhf_tracked_q179 as Q  # noqa: E402
from scripts.cryo.vhf_nerve_track import Crops  # noqa: E402

REPORT = REPO / "data/derived/Q179_vhf_tracked_audit.json"


def test_z_offset_spec():
    assert STREAM.z_offset_at("-17", -100) == -17.0
    spec = "0:-20,-375:-14"
    assert STREAM.z_offset_at(spec, 0) == pytest.approx(-20.0)
    assert STREAM.z_offset_at(spec, -375) == pytest.approx(-14.0)
    assert STREAM.z_offset_at(spec, -187.5) == pytest.approx(-17.0)
    assert STREAM.z_offset_at(spec, 30) == pytest.approx(-20.0)          # constant beyond


def test_streamer_male_constants_unchanged():
    assert STREAM.ORIGIN == "-6.035,-895.476,4.787"
    assert (STREAM.X0, STREAM.Y0, STREAM.RS, STREAM.CS, STREAM.CB) == (240.0 + 2.72, (-239.0625 + 479.0) - 0.89, 4.0, -96.0, 0.0)


def test_crops_per_side_shift(tmp_path):
    lv = {"RS": -2.0, "CS": -108.0, "windows": {"right": [0, 300, 0, 300]}, "RS_by_side": {"right": 1.5}, "CS_by_side": {"right": -110.0}}
    b = {"y_atlas": [-100], "levels": {"-100": lv}, "origin": [7.769, -885.229, 14.137], "H": 405, "sc": 0.99,
         "X0": 350.0, "Y0": 240.0, "ap_row": -1, "CB": 110.0}
    (tmp_path / "t_bbox.json").write_text(json.dumps(b)); np.save(tmp_path / "t_right.npy", np.zeros((1, 300, 300, 3), np.uint8))
    c = Crops(str(tmp_path / "t"), "right"); L, _ = c.level(-100)
    assert (L["RS"], L["CS"]) == (1.5, -110.0)
    pr, pc = c.atlas_to_px(-100, np.array([100.0]), np.array([-10.0])); x, z = c.px_to_atlas(-100, pr, pc)
    assert x[0] == pytest.approx(100.0) and z[0] == pytest.approx(-10.0)
    del lv["RS_by_side"], lv["CS_by_side"]; (tmp_path / "t_bbox.json").write_text(json.dumps(b))
    assert Crops(str(tmp_path / "t"), "right").level(-100)[0]["RS"] == -2.0       # male / old bbox files unchanged


def test_shift_volume_counts_and_sides():
    A = np.diag([0.5, 0.5, 1.0, 1.0]); A[:3, 3] = [Q.ORIGIN[0] - 10.0, Q.ORIGIN[2] - 10.0, Q.ORIGIN[1] - 5.0]
    L = np.zeros((40, 40, 10), np.uint8); L[5:8, 5:8, 3] = 1; L[30:33, 5:8, 3] = 2        # x < 0 (left) / x > 0 (right)
    tab = {"right": {y: [1.0, -0.5] for y in range(-20, 20)}, "left": {y: [-2.0, 0.0] for y in range(-20, 20)}}
    L2, A2, applied = Q.shift_volume(L, A, tab)
    for lab in (1, 2):
        assert (L == lab).sum() == (L2 == lab).sum()
    ii, jj, _ = np.nonzero(L2 == 2); x = A2[0, 3] + 0.5 * ii - Q.ORIGIN[0]; z = A2[1, 3] + 0.5 * jj - Q.ORIGIN[2]
    i0, j0, _ = np.nonzero(L == 2); x0 = A[0, 3] + 0.5 * i0 - Q.ORIGIN[0]; z0 = A[1, 3] + 0.5 * j0 - Q.ORIGIN[2]
    assert x.mean() - x0.mean() == pytest.approx(1.0) and z.mean() - z0.mean() == pytest.approx(-0.5)
    ii, _, _ = np.nonzero(L2 == 1); i0, _, _ = np.nonzero(L == 1)
    assert (A2[0, 3] + 0.5 * ii).mean() - (A[0, 3] + 0.5 * i0).mean() == pytest.approx(-2.0)


def test_her_muscle_colour_rule():
    px = np.array([[[70, 39, 30], [65, 45, 34], [140, 101, 70], [34, 25, 20], [202, 182, 121]]], np.uint8)   # muscle x2, nerve, clot, fat
    assert Q.muscle_f(px, lumen=False)[0].tolist() == [True, True, False, False, False]


def _report():
    if not REPORT.exists():
        pytest.skip("Q179 report absent")
    return json.loads(REPORT.read_text())


def test_report_top_level():
    r = _report()
    assert r["source"].startswith("U.S. National Library of Medicine")
    assert "decision" in r and r["status"].startswith("STOPPED")


def test_report_registration_and_share():
    r = _report(); a = r["audit"]
    for s in ("right", "left"):
        fi = a["registration"]["femur_in_plane"][s]
        assert fi["residual_mm_median"] < 1.0 and fi["levels_used"] > 250
    sh = a["photo_share"]
    for k in ("sciatic_n:right", "sciatic_n:left", "femoral_n:right"):
        assert sh[k]["registered"]["on_photographed_muscle"] < sh[k]["as_placed"]["on_photographed_muscle"]
    assert sh["femoral_a_r:right"]["registered"]["on_photographed_lumen"] > sh["femoral_a_r:right"]["as_placed"]["on_photographed_lumen"]
    assert set(a["unusable_photographs"]["right"]["unusable"]) >= {-128, -129, -130, -131}


def test_reg_table_bounded():
    if not Q.REG_JSON.exists():
        pytest.skip("Q179 registration table absent")
    for key in Q.VOLS:
        tab = Q.reg_table(key)
        for side, rows in tab.items():
            assert max(np.hypot(*v) for v in rows.values()) < 20.0
