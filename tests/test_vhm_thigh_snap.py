"""Q173: his adductor magnus / biceps femoris long head / semitendinosus snapped onto the photographed fat plane, and his
Q57 sciatic nerve placed with the measured photograph-to-atlas registration -- the derived report's measured claims."""
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
REPORT = REPO / "data/derived/Q173_vhm_adductor_magnus.json"
BUNDLE = REPO / "build/viewer_m_hr/bundle.json"
IDS = ("adductor_magnus_r", "adductor_magnus_l", "biceps_femoris_r", "biceps_femoris_l", "semitendinosus_r", "semitendinosus_l")


@pytest.fixture(scope="module")
def report():
    if not REPORT.exists():
        pytest.skip("Q173 report absent")
    return json.loads(REPORT.read_text())


def test_report_cites_its_source(report):
    assert "Visible Human" in report["source"] and "Andreassen" in report["source"] and "vhm_nerves_cryo" in report["source"]
    assert report["subject"] == "ct_vhm_thigh_snap" and report["supplier"]["subject"] == "vhm_both"


def test_registration_consistent_between_muscles_and_femur(report):
    for side in ("right", "left"):
        f = report["registration"]["fit"][side]
        r, c = f["shift_px_rows_cols"]; fr, fc = f["femur_shift_px_median"]
        assert abs(r - fr) <= 1.5 and abs(c - fc) <= 1.5          # two independent fits agree within 0.5 mm
        assert f["muscle_iou_median_at_zero_vs_fit"][1] > f["muscle_iou_median_at_zero_vs_fit"][0]
        assert f["femur_iou_median_at_zero_vs_fit"][1] > f["femur_iou_median_at_zero_vs_fit"][0]


@pytest.mark.parametrize("sid", IDS)
def test_bounded_inward_move_and_small_volume_change(report, sid):
    s = report["structures"][sid]
    assert 0 < s["move"]["max_mm"] <= 8.0
    assert -6.0 <= s["volume_change_pct"] < 0                   # inward only; a large change would mean a wrong snap
    p = s["photo"]
    assert p["on_photographed_muscle_frac_after"] >= p["on_photographed_muscle_frac_before"]
    assert p["non_muscle_inside_cm3_after"] < p["non_muscle_inside_cm3_before"]


def test_nerve_overlap_reduced(report):
    if "verify" not in report:
        pytest.skip("verify not run")
    per = report["verify"]["per_structure"]
    for sid in ("adductor_magnus_r", "adductor_magnus_l"):
        a = per[sid]["q57_nerve_as_shipped_before_q173_vs_old_mesh"]; b = per[sid]["registered_nerve_vs_new_mesh"]
        assert b["beyond_1mm"] < 0.4 * a["beyond_1mm"] and b["max_depth_mm"] < a["max_depth_mm"]


def test_bundle_ships_snapped_muscles_and_badged_nerve():
    if not BUNDLE.exists():
        pytest.skip("male hi-res bundle absent")
    b = json.loads(BUNDLE.read_text()); by = {}
    for e in b["structures"]:
        by.setdefault(e["id"], []).append(e)
    if "sciatic_n" not in by:
        pytest.skip("bundle predates Q173")
    for sid in IDS:
        assert all(e["subject"] == "ct_vhm_thigh_snap" for e in by[sid])
        assert "fat plane" in by[sid][0]["rec"]["procedural_badge"]
    n = by["sciatic_n"][0]
    assert n["subject"] == "ct_vhm_sciatic" and "126" in n["rec"]["procedural_badge"] and "84" in n["rec"]["procedural_badge"]
