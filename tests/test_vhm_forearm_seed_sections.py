"""scripts/cryo/vhm_forearm_seed_sections.py (Q180-prep): pure helpers, and mapping.json round trips when the outputs
exist (VHM_SEED_SECTIONS_DIR, else the newest */scratchpad/q180 under /tmp/claude-*; skipped when absent)."""
import glob
import json
import os
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "cryo"))
import vhm_forearm_seed_sections as S  # noqa: E402


def test_image_axes_view_from_distal_puts_radial_left_for_flexor_sign_minus():
    e = np.array([0.6, 0.8]); n = -1.0 * np.array([-e[1], e[0]])        # Q164 rule with sign -1
    right, down = S.image_axes(n)
    assert np.isclose(right @ down, 0) and np.isclose(np.linalg.norm(right), 1)
    assert np.isclose(e @ right, -1.0)                                     # radial side on the image left
    assert np.allclose(down, -n)                                           # anterior up


def test_section_affines_round_trip():
    a = np.array([-0.448, 0.632, -0.632]); a /= np.linalg.norm(a); c = np.array([207.2, 28.6, -704.2])
    right, down = S.image_axes(np.array([0.3, -0.954]))
    M = S.section_affines(27.0, (-40.0, 35.0), right, down, 0.2, c, a, -60.0, -60.0, 0.5, -150.0, 1.0)
    px = np.array([[0, 0], [10.5, 3.25], [400, 300]])
    assert np.allclose(S.to2(M["atlas_to_pixel"], S.to2(M["pixel_to_atlas"], px)), px)
    assert np.allclose(S.to2(M["frame_st_to_pixel"], S.to2(M["pixel_to_frame_st"], px)), px)
    ijk = S.to2(M["pixel_to_frame_index"], px)
    assert np.allclose(ijk[:, 0], 177.0) and np.allclose(S.to2(M["frame_index_to_pixel"], ijk), px)
    A = S.to2(M["pixel_to_atlas"], px)                                     # rigid: 0.2 mm per pixel, on the plane
    assert np.isclose(np.linalg.norm(A[1] - A[0]), 0.2 * np.linalg.norm(px[1] - px[0]))
    nA = np.array(M["atlas_plane_normal_distal"])
    assert np.allclose(A @ nA - M["atlas_plane_offset"], 0, atol=1e-9)


def test_template_shift_finds_a_known_offset():
    ct = np.zeros((60, 60), bool); yy, xx = np.mgrid[0:60, 0:60]; ct[np.hypot(yy - 30, xx - 30) <= 6] = True
    photo = np.roll(ct, (3, -2), (0, 1))
    dy, dx, sc, sc0 = S.template_shift(photo, ct, max_px=6)
    assert (dy, dx) == (3, -2) and sc > sc0


def test_presence_bands():
    assert S.presence(0.75, 1.0, 1.0, 0.5) is None
    assert S.presence(0.75, 1.0, 1.0, 0.9) == "belly"
    assert S.presence(0.0, 1.0, 0.55, 0.8) == "tendon"
    assert S.presence(0.0, 0.33, 0.33, 0.32) == "edge"
    names = [m["atlas_id"] for m in S.expected_muscles(0.5)]
    assert "pronator_quadratus_r" not in names and "flexor_digitorum_profundus_r" in names


def _out_dir():
    d = os.environ.get("VHM_SEED_SECTIONS_DIR")
    if d:
        return Path(d)
    hits = sorted(glob.glob("/tmp/claude-*/*/*/scratchpad/q180/mapping.json"), key=os.path.getmtime)
    return Path(hits[-1]).parent if hits else None


def test_mapping_json_round_trips():
    d = _out_dir()
    if d is None or not (d / "mapping.json").exists():
        pytest.skip("Q180 seed-section outputs absent")
    m = json.load(open(d / "mapping.json"))
    assert len(m["sections"]) == 5
    rng = np.random.default_rng(0)
    for sec in m["sections"]:
        W, H = sec["image"]["width"], sec["image"]["height"]; M = sec["maps"]
        assert (d / sec["image"]["file"]).exists() and (d / sec["image"]["file_septa"]).exists()
        px = rng.uniform([0, 0], [W, H], (50, 2))
        assert np.allclose(S.to2(M["atlas_to_pixel"], S.to2(M["pixel_to_atlas"], px)), px, atol=1e-6)
        assert np.allclose(S.to2(M["frame_st_to_pixel"], S.to2(M["pixel_to_frame_st"], px)), px, atol=1e-6)
        ijk = S.to2(M["pixel_to_frame_index"], px)
        assert np.allclose(ijk[:, 0], sec["frame_index_i"]) and np.allclose(S.to2(M["frame_index_to_pixel"], ijk), px, atol=1e-6)
        A = S.to2(M["pixel_to_atlas"], px[:2])
        assert np.isclose(np.linalg.norm(A[1] - A[0]), sec["image"]["pixel_mm"] * np.linalg.norm(px[1] - px[0]))
        for b, r in sec["self_check"].items():
            assert r["mapping_error_mm"] is not None and r["mapping_error_mm"] <= 2.0, (sec["id"], b)
