"""Q170: his own pelvic viscera (scripts/vhf_pelvic_viscera.py --body vhm) and the rectum / anal sphincter check
for both bodies -- the derived report's measured claims."""
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
REPORT = REPO / "data/derived/Q170_vhm_pelvic_viscera.json"
BUNDLE = REPO / "build/viewer_m_hr/bundle.json"
IDS = ("urinary_bladder", "rectum", "sigmoid_colon", "prostate")


@pytest.fixture(scope="module")
def report():
    if not REPORT.exists():
        pytest.skip("Q170 report absent")
    return json.loads(REPORT.read_text())


def test_report_cites_its_source(report):
    assert report["source"] and "vhm_total" in report["source"] and "vhm_legs_total" in report["source"]
    assert report["subject"] == "ct_vhm_pelvis" and report["origin_atlas_mm"] == [-6.035, -895.476, 4.787]


def test_blocks_joined_by_the_documented_offset(report):
    a = report["volume_assembly"]
    assert a["legs_to_torso_ras_mm"] == [2.72, -0.89, -693.0]
    assert a["in_plane_nearest_voxel_residual_mm"] <= 0.1


@pytest.mark.parametrize("sid", IDS)
def test_volume_in_reference_range(report, sid):
    s = report["structures"][sid]
    lo, hi = s["reference_volume_cm3"]
    assert lo <= s["voxel_volume_cm3"] <= hi
    assert abs(s["mesh_volume_cm3"] - s["voxel_volume_cm3"]) / s["voxel_volume_cm3"] < 0.05
    if "reference_length_mm" in s:
        lo, hi = s["reference_length_mm"]
        assert lo <= s["centreline_length_mm"] <= hi


@pytest.mark.parametrize("sid", IDS)
def test_single_component(report, sid):
    s = report["structures"][sid]
    assert s["voxel_components"] == 1 and s["mesh_components"] == 1 and s["watertight"]
    assert all(x < 0.01 * s["voxel_volume_cm3"] for x in s.get("mesh_specks_dropped_cm3", []))


def test_dropped_pieces_are_specks_or_listed(report):
    pelvic = report["colon"]["pelvic_colon_cm3"]
    assert all(x < 0.01 * pelvic for x in report["colon"]["pelvic_colon_specks_dropped_cm3"])
    for p in report["colon"].get("non_speck_pieces_dropped", []):        # reviewed, detached pieces
        assert p["cm3"] < 0.02 * pelvic and p["gap_to_kept_mm"] > 3
    for sid in ("urinary_bladder", "prostate"):
        s = report["structures"][sid]
        assert all(x < 0.01 * s["voxel_volume_cm3"] for x in s["specks_dropped_cm3"])
        for p in s.get("non_speck_pieces_dropped", []):
            assert p["cm3"] < 0.02 * s["voxel_volume_cm3"] and p["gap_to_kept_mm"] > 3


@pytest.mark.parametrize("sid", IDS)
def test_inside_his_pelvis(report, sid):
    p = report["structures"][sid]["position"]
    assert p["inside_pelvic_box"]
    assert p["vertices_inside_ct_bone_surface_hip_sacrum"] == 0
    assert p["fraction_of_vertices_below_inlet"] >= (0.5 if sid == "urinary_bladder" else 0.95)


def test_prostate_below_bladder_and_in_front_of_rectum(report):
    s = report["structures"]
    assert s["prostate"]["bbox_max_mm"][1] < s["urinary_bladder"]["bbox_max_mm"][1]
    pz = (s["prostate"]["bbox_min_mm"][2] + s["prostate"]["bbox_max_mm"][2]) / 2
    assert pz > s["rectum"]["bbox_min_mm"][2]


def test_rectum_ends_near_s3(report):
    L = report["landmarks_atlas_mm"]
    f = L.get("rectum_upper_end_fraction_of_sacral_height_from_promontory",
              L["take_off_fraction_of_sacral_height_from_promontory"])
    assert 0.35 <= f <= 0.70


def test_anal_canal_check_both_bodies(report):
    c = report.get("anal_canal_check")
    if c is None:
        pytest.skip("--anal-check not run")
    for body in ("vhf", "vhm"):
        r = c[body]
        if "skipped" in r:
            continue
        # measured only: both rectum meshes end at the level of their sphincter's lower edge, never inside it
        assert abs(r["gap_rectum_lowest_to_sphincter_bottom_mm"]) < 3
        assert r["rectum_vertices_inside_sphincter"] in (0, None)


def test_shipped_in_male_bundle():
    if not BUNDLE.exists():
        pytest.skip("build/viewer_m_hr absent (build/ is not in git)")
    rows = {e["id"]: e for e in json.loads(BUNDLE.read_text())["structures"] if e["id"] in IDS}
    if not rows:
        pytest.skip("male bundle not rebuilt with ct_vhm_pelvis")
    assert set(rows) == set(IDS)
    for e in rows.values():
        assert e["cat"] == "organ" and e["subject"] == "ct_vhm_pelvis" and e["rec"]["name"]
