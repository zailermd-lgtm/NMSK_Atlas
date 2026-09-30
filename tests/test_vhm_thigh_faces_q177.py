"""Q177: the faces his tracked sciatic nerve / femoral veins still entered (biceps femoris, adductor magnus, pectineus,
vastus medialis) snapped onto the photographed fat plane -- the derived report's measured claims, the stored moves, the
byte-identical rebuild and the shipped bundle. Skips when the outputs are absent."""
import hashlib
import json
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
REPORT = REPO / "data/derived/Q177_vhm_thigh_faces.json"
STORE = REPO / "data/ct_sources/task_outputs/vhm_thigh_snap_q177.npz"
SUBJ = REPO / "build/vh/ct_vhm_thigh_snap"
BUNDLE = REPO / "build/viewer_m_hr/bundle.json"
IDS = ("biceps_femoris_r", "biceps_femoris_l", "adductor_magnus_r", "adductor_magnus_l",
       "pectineus_r", "pectineus_l", "vastus_medialis_r", "vastus_medialis_l")


@pytest.fixture(scope="module")
def report():
    if not REPORT.exists():
        pytest.skip("Q177 report absent")
    return json.loads(REPORT.read_text())


def test_report_cites_its_source(report):
    s = report["source"]
    assert "Visible Human" in s and "Andreassen" in s and "vhm_thigh_snap_q173" in s and "ct_vhm_sciatic" in s and "ct_vhm_femoral" in s
    assert report["task"] == "Q177" and report["subject"] == "ct_vhm_thigh_snap" and report["stopped"] == []


def test_registration_rechecked_on_femur(report):
    rc = report["registration"]["recheck_on_these_crops"]["regcheck_fem"]; used = report["registration"]["used_px"]
    for side in ("right", "left"):
        fr, fc = rc[side]["femur"]["median_rows_cols"]; ur, uc = used[side]
        assert abs(fr - ur) <= 1.5 and abs(fc - uc) <= 1.5          # the femur on these crops agrees with Q173 within 0.5 mm


@pytest.mark.parametrize("sid", IDS)
def test_entry_direction_measured_and_bounded_move(report, sid):
    s = report["structures"][sid]
    assert s["status"] == "ok" and s["entry"]["n_vertices"] > 0
    assert abs(np.linalg.norm(s["entry"]["facing_atlas_xyz"]) - 1) < 1e-3
    assert 0 < s["move"]["max_mm"] <= 8.0
    assert -5.0 <= s["volume_change_pct"] < 0                   # inward only; > 5 % is the stop rule
    p = s["photo"]
    assert p["on_photographed_muscle_frac_after"] >= p["on_photographed_muscle_frac_before"]
    assert p["non_muscle_inside_cm3_after"] < p["non_muscle_inside_cm3_before"]
    t = s["tracked_fullres"]
    assert t["vs_after"]["beyond_1mm"] <= t["vs_before"]["beyond_1mm"] and t["vs_after"]["max_depth_mm"] <= t["vs_before"]["max_depth_mm"]


def test_measured_entry_faces(report):
    d = {k: report["structures"][k]["entry"]["direction"] for k in IDS}
    assert d["adductor_magnus_r"] == d["adductor_magnus_l"] == "posterior"
    assert d["biceps_femoris_r"] == d["biceps_femoris_l"] == "anteromedial"
    assert d["pectineus_r"] == d["pectineus_l"] == "anterolateral"
    assert d["vastus_medialis_r"] == d["vastus_medialis_l"] == "posteromedial"


def test_verify_no_new_overlap_and_less_tracked_overlap(report):
    if "verify" not in report:
        pytest.skip("verify-q177 not run")
    v = report["verify"]
    b = v["bundle"]; assert sorted(b["geometry_changed"]) == sorted(IDS) and b["ids_added"] == [] and b["ids_removed"] == []
    for sid in IDS:
        o = v["per_structure"][sid]
        assert o["new_overlap"] == [] and "femur" + sid[-2:] in o["neighbours_old_vs_new_bundle"]
        assert o["tracked_bundle_vs_new_bundle_mesh"]["beyond_1mm"] <= o["tracked_bundle_vs_old_bundle_mesh"]["beyond_1mm"]
    t = v["tracked_totals"]
    for tid in ("sciatic_n", "femoral_v_r", "femoral_v_l"):
        assert t[tid]["new_bundle"]["beyond_1mm_any"] <= t[tid]["old_bundle"]["beyond_1mm_any"]
    assert t["sciatic_n"]["new_bundle"]["beyond_1mm_any"] < 0.8 * t["sciatic_n"]["old_bundle"]["beyond_1mm_any"]


def test_stored_moves_bounded():
    if not STORE.exists():
        pytest.skip("Q177 store absent")
    z = np.load(STORE)
    keys = sorted(k for k in z.files if k != "params")
    assert keys == sorted(k + "__0" for k in IDS)
    for k in keys:
        assert z[k].min() >= 0 and z[k].max() <= 8.0


def test_apply_rebuilds_subject_byte_identically(tmp_path):
    if not (STORE.exists() and REPORT.exists() and (SUBJ / "manifest.json").exists()):
        pytest.skip("Q177 outputs absent")
    import sys
    sys.path.insert(0, str(REPO))
    import scripts.cryo.vhm_thigh_fat_plane_snap as Q
    before = {p.name: hashlib.md5(p.read_bytes()).hexdigest() for p in SUBJ.iterdir() if p.is_file()}
    import argparse
    Q.apply(argparse.Namespace(force_nerve=False))
    after = {p.name: hashlib.md5(p.read_bytes()).hexdigest() for p in SUBJ.iterdir() if p.is_file()}
    assert before == after


def test_bundle_ships_q177_faces_and_badges():
    if not BUNDLE.exists():
        pytest.skip("male hi-res bundle absent")
    by = {}
    for e in json.loads(BUNDLE.read_text())["structures"]:
        by.setdefault(e["id"], []).append(e)
    if not any(e["subject"] == "ct_vhm_thigh_snap" for e in by.get("pectineus_r", [])):
        pytest.skip("bundle predates Q177")
    for sid in IDS:
        assert all(e["subject"] == "ct_vhm_thigh_snap" for e in by[sid])
        assert "Q177" in by[sid][0]["rec"]["procedural_badge"]
    for sid in ("biceps_femoris_r", "adductor_magnus_l"):
        assert "Q173" in by[sid][0]["rec"]["procedural_badge"]              # Q173 sentence kept, Q177 appended
    for tid in ("sciatic_n", "femoral_v_l", "femoral_v_r"):
        b = by[tid][0]["rec"]["procedural_badge"]
        assert "Q176" in b and "Q177" in b and "The rest is the muscle" not in b
