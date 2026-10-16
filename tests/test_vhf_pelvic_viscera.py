"""Q169: her own pelvic viscera (scripts/vhf_pelvic_viscera.py) -- the derived report's measured claims."""
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
REPORT = REPO / "data/derived/Q169_vhf_pelvic_viscera.json"
BUNDLE = REPO / "build/viewer_f_hr/bundle.json"
IDS = ("urinary_bladder", "rectum", "sigmoid_colon")


@pytest.fixture(scope="module")
def report():
    if not REPORT.exists():
        pytest.skip("Q169 report absent")
    return json.loads(REPORT.read_text())


def test_report_cites_its_source(report):
    assert report["source"] and "vhf_total" in report["source"]


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


def test_dropped_pieces_are_specks(report):
    pelvic = report["colon"]["pelvic_colon_cm3"]
    assert all(x < 0.01 * pelvic for x in report["colon"]["pelvic_colon_specks_dropped_cm3"])
    b = report["structures"]["urinary_bladder"]
    assert all(x < 0.01 * b["voxel_volume_cm3"] for x in b["specks_dropped_cm3"])


@pytest.mark.parametrize("sid", IDS)
def test_inside_her_pelvis(report, sid):
    p = report["structures"][sid]["position"]
    assert p["inside_pelvic_box"]
    for bone in ("hip_bone_l", "hip_bone_r", "sacrum"):
        assert p[f"sampled_vertices_inside_{bone}"] in (0, None)
    # the colon parts were cut at the inlet; an empty bladder lies mostly below it
    assert p["fraction_of_vertices_below_inlet"] >= (0.5 if sid == "urinary_bladder" else 0.98)


def test_take_off_near_s3(report):
    # rectosigmoid junction at about the third sacral segment: 35-70 % of her sacral height below the promontory
    assert 0.35 <= report["landmarks_atlas_mm"]["take_off_fraction_of_sacral_height_from_promontory"] <= 0.70


def test_shipped_in_female_bundle():
    if not BUNDLE.exists():
        pytest.skip("build/viewer_f_hr absent (build/ is not in git)")
    rows = {e["id"]: e for e in json.loads(BUNDLE.read_text())["structures"] if e["id"] in IDS}
    assert set(rows) == set(IDS)
    for e in rows.values():
        assert e["cat"] == "organ" and e["subject"] == "ct_vhf_pelvis" and e["rec"]["name"]
