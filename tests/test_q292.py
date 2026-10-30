"""Q292: Base · Female -- her own breasts, chest skin contour and pelvic organs (scripts/anatomy/q292/)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest
import trimesh

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts/anatomy/q292"))
import lib292 as L  # noqa: E402

REPORT = REPO / "data/derived/Q292_base_f_report.json"
VALID = REPO / "data/derived/Q292_validation.json"
PAGE_REPORT = REPO / "data/derived/Q292_page_report.json"
PAGE = REPO / "build/q292/viewer_base_female/atlas_viewer_base_female.html"


def test_occupancy_volume_of_a_sphere():
    s = trimesh.creation.icosphere(subdivisions=4, radius=20.0)
    i0, occ = L.occ_scan(np.asarray(s.vertices), np.asarray(s.faces))
    assert abs(occ.sum() / 1000.0 - s.volume / 1000.0) / (s.volume / 1000.0) < 0.03


def test_sdf_sign_and_push_out():
    s = trimesh.creation.icosphere(subdivisions=3, radius=15.0)
    sdf = L.SDF([(np.asarray(s.vertices), np.asarray(s.faces))], [-30, -30, -30], [30, 30, 30])
    assert sdf.at(np.array([[0.0, 0, 0]]))[0] > 10 and sdf.at(np.array([[25.0, 0, 0]]))[0] < -5
    p = trimesh.creation.icosphere(subdivisions=2, radius=3.0); V = np.asarray(p.vertices) + [12.0, 0, 0]
    V2, info = L.push_out(V, np.asarray(p.faces), sdf, margin=0.5, max_disp=20)
    assert (sdf.at(V2) <= -0.2).all() and info["still_violating"] == 0


def test_thin_plate_map_is_exact_for_a_similarity():
    rng = np.random.default_rng(0); X = rng.uniform(-100, 100, (600, 3))
    R = trimesh.transformations.rotation_matrix(0.1, [0, 1, 0])[:3, :3]; Y = 1.02 * X @ R.T + [3, -2, 5]
    M = L.Map(X, Y, smoothing=0.0, ncp=400)
    assert np.median(M.resid) < 1e-3 and abs(M.s - 1.02) < 1e-6


@pytest.mark.skipif(not REPORT.exists(), reason="Q292 report not built")
def test_report_breasts_and_pelvis():
    r = json.loads(REPORT.read_text())
    for s in "lr":
        b = r["breasts"][s]
        assert b["volume_kept_pct"] >= 60, b["volume_kept_pct"]
        assert b["vertices_outside_skin_gt0_5mm_pct"] < 3.0 and b["vertices_in_rib_cage_gt0_5mm_pct"] < 3.0
        assert b["fgt_vertices_outside_breast_pct"] < 1.0
    assert set(r["organs"]) == {"urinary_bladder", "rectum", "sigmoid_colon", "uterus_cryo_vhf"}
    assert r["map"]["tps_resid_med_mm"] < 2.0
    assert 0 < r["urethral_group_anterior_shift_mm"] <= 14


@pytest.mark.skipif(not VALID.exists(), reason="Q292 validation not built")
def test_validation_against_literature():
    v = json.loads(VALID.read_text())
    p = v["pelvis"]
    assert p["subpubic_angle_deg"] >= 78.6                                            # female side of the cut-off (PMID 32274246)
    for s in "lr":
        b = v["breast"][s]
        assert 300 <= b["volume_cm3"] <= 1100
        assert "fifth" in b["imf_level"] or "sixth" in b["imf_level"] or "seventh" in b["imf_level"]
    ref = [x["mean_deg"] for x in v["realness_dihedral"]["cvh_reference"].values()]
    assert 20 < min(ref) and max(ref) < 40


@pytest.mark.skipif(not (PAGE_REPORT.exists() and PAGE.exists()), reason="Q292 page not built")
def test_page_flags_and_cards():
    rep = json.loads(PAGE_REPORT.read_text())
    h = PAGE.read_text(encoding="utf-8")
    i = h.find("window.__ANATOMY_MANIFEST__=") + len("window.__ANATOMY_MANIFEST__=")
    man = json.JSONDecoder().raw_decode(h[i:])[0]
    E = {m["id"]: m for m in man["meshes"]}
    for k in ["breast_ct_l", "breast_ct_r", "breast_fgt_ct_l", "breast_fgt_ct_r", "urinary_bladder", "rectum", "sigmoid_colon", "uterus_cryo_vhf",
              "external_anal_sphincter_ct_vhf"]:
        assert k in E, k
    for k in ["breast_fat_l", "nipple_r", "mammary_gland_l", "zan_urinary_bladder", "zan_sigmoid_colon", "uterus", "external_anal_sphincter"]:
        assert E[k].get("hd") == 1, k
    assert E["breast_ct_r"].get("fd") == 1 and E["breast_ct_l"].get("fd") == 1
    assert "RULE-BASED" in E["breast_ct_r"]["rec"]["procedural_badge"] and "her own CT" in E["breast_ct_r"]["rec"]["geom_src"]
    assert E["breast_fgt_ct_r"]["rec"]["geom_src"].startswith("RULE-BASED")
    assert E["external_anal_sphincter_ct_vhf"]["rec"]["procedural_badge"].startswith("RULE-BASED")
    assert sorted(k for k, m in E.items() if m.get("hd")) == sorted(rep["hidden_default"])
    assert len(man["meshes"]) == rep["meshes"]


def test_template_card_names_the_geometry_source():
    t = (REPO / "viewer/zan_atlas.template.html").read_text(encoding="utf-8")
    assert "a.geom_src?'Geometry: '+esc(a.geom_src)" in t
