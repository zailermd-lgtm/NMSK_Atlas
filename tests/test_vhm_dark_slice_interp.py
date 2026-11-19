"""Q178: his tracked outlines on his unusable photographs (y -136..-141) replaced by shape interpolation between the
traced, clipped levels -- the interpolation rule on synthetic sections, the report's measured claims, the interpolated
volumes and the shipped bundle. Output checks skip when the outputs are absent."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
REPORT = REPO / "data/derived/Q178_vhm_sciatic_interp.json"
T = REPO / "data/ct_sources/task_outputs"
BUNDLE = REPO / "build/viewer_m_hr/bundle.json"
IDS = ("sciatic_n", "femoral_v_l", "femoral_v_r")


def test_interp_endpoints_and_midpoint():
    from scripts.cryo.vhm_dark_slice_interp import interp_section
    A = np.zeros((60, 60), bool); A[10:20, 10:20] = True          # 10 x 10 square
    B = np.zeros((60, 60), bool); B[30:50, 30:50] = True          # 20 x 20 square, elsewhere
    assert (interp_section(A, B, 0.0)[0] == A).all() and (interp_section(A, B, 1.0)[0] == B).all()
    M, n = interp_section(A, B, 0.5)
    ys, xs = np.nonzero(M)
    assert n == 1 and 12 <= ys.max() - ys.min() + 1 <= 18            # size in between
    assert abs(ys.mean() - 27.0) < 1.5 and abs(xs.mean() - 27.0) < 1.5   # centroid half way


@pytest.fixture(scope="module")
def report():
    if not REPORT.exists():
        pytest.skip("Q178 report absent")
    return json.loads(REPORT.read_text())


def test_report_source_and_span(report):
    assert "Visible Human" in report["source"] and "Q176" in report["source"]
    assert report["unusable_span"] == [-136, -141]
    lv = report["photographs"]["pooled"]["levels"]
    assert all(lv[str(y)]["unusable"] for y in range(-136, -142, -1))
    assert not lv["-135"]["unusable"] and not lv["-142"]["unusable"]
    assert lv["-137"]["muscle_frac"] < 0.01 and lv["-138"]["V_rel"] < -0.3          # black


def test_structures_interpolated_or_kept(report):
    s = report["structures"]
    for k in ("sciatic_n:right", "femoral_v_l:left", "femoral_v_r:right"):
        assert s[k]["status"] == "interpolated" and s[k]["bounds"] == [-135, -142]
        assert s[k]["components_3d_26_6conn"]["after"][0] <= s[k]["components_3d_26_6conn"]["before"][0]
        a = [s[k]["area_mm2_after"][str(y)] for y in range(-135, -143, -1)]
        lo, hi = min(a[0], a[-1]), max(a[0], a[-1])
        assert all(0.8 * lo <= x <= 1.1 * hi for x in a[1:-1])                      # continuous across the span
        for y in (-133, -134, -135, -142, -143):
            assert s[k]["area_mm2_after"][str(y)] == s[k]["area_mm2_before"][str(y)]
    assert s["sciatic_n:left"]["status"] == "kept_as_traced"
    assert s["femoral_a_l"]["voxels_in_span"] == 0 and s["femoral_a_r"]["voxels_in_span"] == 0


def test_verify_numbers(report):
    v = report.get("verify")
    if not v:
        pytest.skip("not verified yet")
    for aid in IDS:
        assert v[aid]["bone_inside"] == {"bundle": 0, "fullres_subject": 0}
        mc = v[aid]["mesh_components"]; assert mc["subject_after"] <= mc["subject_before"] and mc["bundle_after"] <= mc["bundle_before"]
        for tag in ("bundle", "fullres_subject"):
            m = v[aid][f"muscle_beyond_1mm_{tag}"]; assert m["after"] <= m["before"]
    b = report["bundle"]
    assert not b["ids_added"] and not b["ids_removed"] and sorted(b["geometry_changed"]) == sorted(IDS)


def test_volumes_change_only_the_span():
    nib = pytest.importorskip("nibabel")
    from scripts.cryo.vhm_dark_slice_interp import ORIGIN
    pairs = [("vhm_nerves_cryo_reg_clip", "vhm_nerves_cryo_reg_clip_interp"), ("vhm_femoral_cryo_clip", "vhm_femoral_cryo_clip_interp"),
             ("vhm_nerves_cryo_clip", "vhm_nerves_cryo_clip_interp")]
    for a, b in pairs:
        if not (T / f"{b}.nii.gz").exists():
            pytest.skip("interpolated volumes absent")
        i0, i1 = nib.load(str(T / f"{a}.nii.gz")), nib.load(str(T / f"{b}.nii.gz"))
        L0, L1 = np.asarray(i0.dataobj), np.asarray(i1.dataobj)
        assert np.allclose(i0.affine, i1.affine) and L0.shape == L1.shape
        ys = np.rint(i0.affine[2, 3] + i0.affine[2, 2] * np.arange(L0.shape[2]) - ORIGIN[1]).astype(int)
        diff = np.nonzero((L0 != L1).any((0, 1)))[0]
        assert len(diff) and set(ys[diff]) <= set(range(-141, -135))


def test_bundle_badges():
    if not BUNDLE.exists():
        pytest.skip("male hi-res bundle absent")
    b = json.loads(BUNDLE.read_text()); ids = {s["id"]: s for s in b["structures"]}
    if "sciatic_n" not in ids or "Q178" not in json.dumps(ids["sciatic_n"].get("rec", {})):
        pytest.skip("bundle predates Q178")
    for aid in IDS:
        badge = ids[aid]["rec"]["procedural_badge"]
        assert "Q176" in badge and "Q177" in badge and "Q178 RULE-BASED" in badge and "INTERPOLATED" in badge and "-136..-141" in badge
