"""Q176: his tracked outlines (sciatic, femoral/popliteal veins, tibial nerve) clipped to photographed non-muscle --
the clip rule on a synthetic section, the derived report's measured claims, the clipped volumes and the shipped bundle.
Output checks skip when the outputs are absent."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
REPORT = REPO / "data/derived/Q176_vhm_tracked_clip.json"
T = REPO / "data/ct_sources/task_outputs"
BUNDLE = REPO / "build/viewer_m_hr/bundle.json"
CLIPPED = ("sciatic_n", "femoral_v_l", "femoral_v_r", "popliteal_v_l", "popliteal_v_r", "tibial_n")


def test_clip_rule_peels_rim_muscle_only():
    from scripts.cryo.vhm_tracked_clip import clip_section
    M = np.zeros((40, 40), bool); M[5:35, 5:35] = True
    fr = np.zeros(M.shape); fr[5:35, 5:9] = 1.0          # 2 mm of muscle along one edge
    fr[18:22, 18:22] = 1.0                               # muscle-looking patch deep inside: never touched
    new, n, st = clip_section(M, fr)
    assert st == "clipped" and n == 30 * 4
    assert not new[5:35, 5:9].any() and new[18:22, 18:22].all()


def test_clip_rule_keeps_level_that_would_split():
    from scripts.cryo.vhm_tracked_clip import clip_section
    M = np.zeros((30, 60), bool); M[5:25, 5:25] = True; M[5:25, 35:55] = True; M[14:16, 25:35] = True   # two lobes + a 1 mm neck
    fr = np.zeros(M.shape); fr[14:16, 25:35] = 1.0        # the neck lies on photographed muscle: peeling it would split
    new, n, st = clip_section(M, fr)
    assert st in ("kept_split", "unchanged") and (new == M).all()


@pytest.fixture(scope="module")
def report():
    if not REPORT.exists():
        pytest.skip("Q176 report absent")
    return json.loads(REPORT.read_text())


def test_report_source_and_status(report):
    s = report["source"]
    assert "Visible Human" in s and "vhm_nerves_cryo" in s and "vhm_femoral_cryo" in s and "Q173" in s
    assert report["status"] == "ok"


@pytest.mark.parametrize("sid", CLIPPED)
def test_bounded_clip(report, sid):
    s = report["structures"][sid]
    assert s["volume_cm3"][1] <= s["volume_cm3"][0]
    assert s["diameter_change_pct"] > -20.0                     # stop rule
    assert s["components_3d_26conn"][1] <= s["components_3d_26conn"][0]
    assert s["components_3d_6conn"][1] <= s["components_3d_6conn"][0]
    assert s["on_photographed_muscle_frac"][1] <= s["on_photographed_muscle_frac"][0]
    assert s["bone_inside"]["bundle"] == 0 and s["bone_inside"]["fullres_subject"] == 0
    mc = s["mesh_components"]; assert mc["subject_after"] <= mc["subject_before"] and mc["bundle_after"] <= mc["bundle_before"]
    ob = s["muscle_overlap_bundle"]; assert ob["after"]["beyond_1mm_any"] <= ob["before"]["beyond_1mm_any"]


def test_arteries_not_clipped(report):
    for aid in ("femoral_a_l", "femoral_a_r"):
        assert report["structures"][aid]["clipped"] is False


def test_only_tracked_ids_changed(report):
    b = report["bundle"]
    assert not b["ids_added"] and not b["ids_removed"] and set(b["geometry_changed"]) <= set(CLIPPED)


def test_clipped_volumes_are_subsets():
    nib = pytest.importorskip("nibabel")
    pairs = [("vhm_nerves_cryo", "vhm_nerves_cryo_clip"), ("vhm_femoral_cryo", "vhm_femoral_cryo_clip"),
             ("vhm_popliteal_cryo", "vhm_popliteal_cryo_clip")]
    for a, b in pairs:
        if not (T / f"{b}.nii.gz").exists():
            pytest.skip("clipped volumes absent")
        i0, i1 = nib.load(str(T / f"{a}.nii.gz")), nib.load(str(T / f"{b}.nii.gz"))
        L0, L1 = np.asarray(i0.dataobj), np.asarray(i1.dataobj)
        assert np.allclose(i0.affine, i1.affine) and L0.shape == L1.shape
        assert ((L1 == 0) | (L1 == L0)).all()                   # only removals, never a new or relabelled voxel


def test_bundle_badges():
    if not BUNDLE.exists():
        pytest.skip("male hi-res bundle absent")
    b = json.loads(BUNDLE.read_text()); ids = {s["id"]: s for s in b["structures"]}
    if "sciatic_n" not in ids:
        pytest.skip("tracked ids not in this bundle")
    for aid in CLIPPED:
        assert "Q176" in json.dumps(ids[aid].get("rec", {}))
