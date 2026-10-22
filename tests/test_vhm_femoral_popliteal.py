"""Q174: his femoral/popliteal bundles (scripts/cryo/vhm_femoral_popliteal_track.py). Output checks skip when absent."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from scripts.cryo import vhm_femoral_popliteal_track as T  # noqa: E402
from scripts.cryo import vhf_nerve_track as nt  # noqa: E402

REPORT = REPO / "data/derived/Q174_vhm_femoral_popliteal.json"
BUNDLE = REPO / "build/viewer_m_hr/bundle.json"
IDS = ["femoral_a_r", "femoral_a_l", "femoral_v_r", "femoral_v_l", "popliteal_v_r", "popliteal_v_l", "tibial_n"]


def _disc(im, r0, c0, rad, col):
    yy, xx = np.ogrid[:im.shape[0], :im.shape[1]]
    im[(yy - r0) ** 2 + (xx - c0) ** 2 <= rad * rad] = col


def test_lumen_detector_black_and_blue_stay_separate():
    im = np.full((200, 200, 3), (210, 170, 110), np.uint8)             # fat
    _disc(im, 100, 80, 15, (25, 14, 11))                                # clotted vein (black)
    _disc(im, 100, 108, 10, (35, 90, 190))                              # gel-filled artery touching it (blue)
    lab, blue = T.lumina(im, with_blue=True, split_h=None)
    a, b = lab[100, 80], lab[100, 108]
    assert a > 0 and b > 0 and a != b
    assert blue[lab == b].mean() > 0.5 and blue[lab == a].mean() < 0.3


def test_dark_patch_inside_muscle_has_no_rim():
    im = np.full((200, 200, 3), (70, 30, 25), np.uint8)                # his muscle
    _disc(im, 100, 100, 12, (50, 22, 18))                               # a darker patch inside it
    lab = T.lumina(im, split_h=None)
    m = lab == lab[100, 100]
    assert T.ring_contrast(im[..., 0].astype(np.float32), m) < T.RING_MIN
    im2 = np.full((200, 200, 3), (210, 170, 110), np.uint8); _disc(im2, 100, 100, 12, (30, 15, 12))
    lab2 = T.lumina(im2, split_h=None)
    assert T.ring_contrast(im2[..., 0].astype(np.float32), lab2 == lab2[100, 100]) > T.RING_MIN


def test_small_lumen_survives_splitting():
    im = np.full((120, 120, 3), (210, 170, 110), np.uint8); _disc(im, 60, 60, 4, (25, 14, 11))   # ~1.6 mm radius
    assert T.lumina(im, split_h=6.0)[60, 60] > 0


def test_per_side_registration_in_crops(tmp_path):
    ys = [-100]
    b = {"y_atlas": ys, "levels": {"-100": {"RS": 4.0, "CS": -96.0, "windows": {"right": [0, 300, 0, 300], "left": [0, 300, 0, 300]}}},
         "origin": [-6.035, -895.476, 4.787], "H": 405, "sc": 0.99, "X0": 242.72, "Y0": 239.0475, "ap_row": -1, "CB": 0.0}
    for s in ("right", "left"):
        np.lib.format.open_memmap(tmp_path / f"c_{s}.npy", mode="w+", dtype=np.uint8, shape=(1, 300, 300, 3)).flush()
    json.dump(b, open(tmp_path / "c_bbox.json", "w"))
    raw = {s: nt.Crops(str(tmp_path / "c"), s) for s in ("right", "left")}

    class A:
        crops = str(tmp_path / "c"); out = str(tmp_path / "r")
    if not T.Q173.exists():
        pytest.skip("Q173 report absent")
    T.register(A)
    reg = json.loads(T.Q173.read_text())["registration"]["used_px"]
    for s in ("right", "left"):
        r = nt.Crops(str(tmp_path / "r"), s)
        d = np.array(r.atlas_to_px(-100, 40.0, 10.0)) - np.array(raw[s].atlas_to_px(-100, 40.0, 10.0))
        assert np.allclose(d, reg[s], atol=1e-6)
        x, z = r.px_to_atlas(-100, *r.atlas_to_px(-100, 40.0, 10.0))
        assert abs(x - 40.0) < 1e-6 and abs(z - 10.0) < 1e-6


@pytest.fixture
def report():
    if not REPORT.exists():
        pytest.skip("Q174 report absent")
    return json.loads(REPORT.read_text())


def test_report_numbers(report):
    assert report["source"] and "male cryosections" in report["source"]
    assert set(report["structures"]) == set(IDS)
    for aid, s in report["structures"].items():
        assert all(v["inside"] == 0 for v in s["vertices_inside_bone"].values()), aid
        assert s["tracked_levels"] >= 20 and s["longest_run_without_detection"] <= 12, aid
    for side in ("right", "left"):
        fv = report["femoral_artery_vs_vein"][side]
        assert fv["artery_lateral_of_vein_levels"] == fv["levels"] > 0
    d = report["popliteal_depth_order_left"]
    assert d["nerve_posterior_of_vein_levels"] == d["levels"] > 0
    assert {"popliteal_a_r", "popliteal_a_l"} <= set(report["nulled"])


def test_bundle_has_badged_ids():
    if not BUNDLE.exists():
        pytest.skip("male hi-res bundle absent")
    st = {s["id"]: s for s in json.loads(BUNDLE.read_text())["structures"] if s["subject"] in ("ct_vhm_femoral", "ct_vhm_popliteal")}
    if not st:
        pytest.skip("bundle built without Q174")
    assert set(st) == set(IDS)
    for s in st.values():
        assert "Q174" in (s.get("rec") or {}).get("procedural_badge", "")
