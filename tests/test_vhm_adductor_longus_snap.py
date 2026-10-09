"""Q175: his adductor longus (anterolateral face, under the femoral vessels) snapped onto the photographed fat plane --
the derived report's measured claims, the stored moves and the shipped bundle. Skips when the outputs are absent."""
import json
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
REPORT = REPO / "data/derived/Q175_vhm_adductor_longus.json"
STORE = REPO / "data/ct_sources/task_outputs/vhm_thigh_snap_q175.npz"
BUNDLE = REPO / "build/viewer_m_hr/bundle.json"
IDS = ("adductor_longus_r", "adductor_longus_l")


@pytest.fixture(scope="module")
def report():
    if not REPORT.exists():
        pytest.skip("Q175 report absent")
    return json.loads(REPORT.read_text())


def test_report_cites_its_source(report):
    s = report["source"]
    assert "Visible Human" in s and "Andreassen" in s and "vhm_femoral_cryo" in s and "vhm_thigh_snap_q173" in s
    assert report["subject"] == "ct_vhm_thigh_snap" and report["supplier"]["subject"] == "vhm_both" and report["status"] == "ok"


def test_registration_rechecked_on_femur(report):
    r = report["registration"]
    for side in ("right", "left"):
        fr, fc = r["recheck_summary"][side]["femur"]; ur, uc = r["used_px"][side]
        assert abs(fr - ur) <= 1.5 and abs(fc - uc) <= 1.5          # femur on these crops agrees with Q173 within 0.5 mm


@pytest.mark.parametrize("sid", IDS)
def test_bounded_inward_move_and_small_volume_change(report, sid):
    s = report["structures"][sid]
    assert 0 < s["move"]["max_mm"] <= 8.0
    assert -5.0 <= s["volume_change_pct"] < 0                   # inward only; > 5 % was the stop rule
    p = s["photo"]
    assert p["on_photographed_muscle_frac_after"] > p["on_photographed_muscle_frac_before"]
    assert p["non_muscle_inside_cm3_after"] < p["non_muscle_inside_cm3_before"]


@pytest.mark.parametrize("sid", IDS)
def test_femoral_vein_overlap_reduced(report, sid):
    v = report["structures"][sid]["femoral_vein_full_res"]
    assert v["vs_new_mesh"]["beyond_1mm"] < 0.5 * v["vs_old_mesh"]["beyond_1mm"]
    assert v["vs_new_mesh"]["max_depth_mm"] < v["vs_old_mesh"]["max_depth_mm"]


def test_no_new_overlap_with_neighbours(report):
    if "verify" not in report:
        pytest.skip("verify-al not run")
    for sid in IDS:
        o = report["verify"]["per_structure"][sid]
        assert o["new_overlap"] == []
        for k in ("femur", "pectineus", "adductor_brevis", "adductor_magnus", "sartorius", "vastus_medialis"):
            assert k + sid[-2:] in o["neighbours_old_vs_new_bundle"]


def test_stored_moves_bounded():
    if not STORE.exists():
        pytest.skip("Q175 store absent")
    z = np.load(STORE)
    keys = [k for k in z.files if k not in ("reg", "params")]
    assert sorted(keys) == ["adductor_longus_l__0", "adductor_longus_r__0"]
    for k in keys:
        assert z[k].min() >= 0 and z[k].max() <= 8.0


def test_bundle_ships_snapped_adductor_longus():
    if not BUNDLE.exists():
        pytest.skip("male hi-res bundle absent")
    by = {}
    for e in json.loads(BUNDLE.read_text())["structures"]:
        by.setdefault(e["id"], []).append(e)
    if not any(e["subject"] == "ct_vhm_thigh_snap" for e in by.get("adductor_longus_r", [])):
        pytest.skip("bundle predates Q175")
    for sid in IDS:
        assert all(e["subject"] == "ct_vhm_thigh_snap" for e in by[sid])
        assert "Q175" in by[sid][0]["rec"]["procedural_badge"] and "fat plane" in by[sid][0]["rec"]["procedural_badge"]
