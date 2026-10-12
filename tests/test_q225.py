"""Q225: Z-fitted pages -- left-elbow bones re-seated (ulna / radius on the humerus by joint congruency), patellae re-seated on the femoral trochlea, floating ribs on their vertebra, wrist / shoulder soft tissue
carried (tear relaxation), clinical files of the female page regenerated.  Synthetic tests of the helpers (signed-distance field, pair report, tapered rigid correction, re-seat of two toy bars, guards) and, when
the Q225 pages are built, the page-level guards: ship-diff scope (0 unlisted), exact bone-bone penetration <= 1 mm at the left elbow / patellae / floating ribs, joint space vs the base model, per-bone fit error in
the card badge, the wrist tears down, the cards, the final pages with parts_data.json, the female clinical files (and none for the male)."""
import json
import re
import sys
from pathlib import Path

import numpy as np
import pytest
import trimesh

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.zanatomy import q225_core as K5  # noqa: E402
from scripts.zanatomy import q225_elbow as EL  # noqa: E402
from scripts.zanatomy import q225_joint as J  # noqa: E402

DER = REPO / "data" / "derived"
FIT = {"male": REPO / "build" / "q225_fit" / "viewer_zan_vhm", "female": REPO / "build" / "q225_fit" / "viewer_zan_female"}
FINAL = {"male": REPO / "build" / "q225" / "viewer_zan_vhm", "female": REPO / "build" / "q225" / "viewer_zan_female"}
STEM = {"male": "atlas_viewer_zan_male_fitted", "female": "atlas_viewer_zan_female"}
SHIP = {w: DER / f"Q225_ship_diff_{w}.json" for w in FIT}
built = pytest.mark.skipif(not all((FIT[w] / f"{STEM[w]}.html").exists() and SHIP[w].exists() for w in FIT), reason="Q225 pages not built")
final = pytest.mark.skipif(not all((FINAL[w] / "index.html").exists() for w in FINAL), reason="Q225 final pages not built")


def box(c, size):
    m = trimesh.creation.box(extents=size)
    m.apply_translation(c)
    return np.asarray(m.vertices, float), np.asarray(m.faces, np.int64)


# ------------------------------------------------------------------------------------------------ synthetic
def test_sdf_is_negative_inside_positive_outside_and_measures_distance():
    v, f = box((0, 0, 0), (20, 20, 20))
    s = J.Sdf(v, f, pad=10.0, h=1.0)
    assert s(np.array([[0.0, 0, 0]]))[0] < -8.0            # deep inside
    assert abs(s(np.array([[14.0, 0, 0]]))[0] - 4.0) < 1.0       # 4 mm outside the face at x = 10
    assert s(np.array([[60.0, 0, 0]]))[0] > 40.0                   # far outside: keeps growing


def test_pair_report_overlap_and_gap():
    va, fa = box((0, 0, 0), (20, 20, 20))
    vb, fb = box((17, 0, 0), (20, 20, 20))               # overlaps by 3 mm
    r = J.pair_report(va, fa, vb, fb, sdf_a=J.Sdf(va, fa, h=0.5), sdf_b=J.Sdf(vb, fb, h=0.5))
    assert -4.0 <= r["min_clearance_mm"] < -1.5          # surface samples of b are up to 3 mm deep in a (a box has few vertices: the vertex rule sees only its corners)
    vc, fc = box((24, 0, 0), (20, 20, 20))               # 4 mm gap
    r2 = J.pair_report(va, fa, vc, fc, sdf_a=J.Sdf(va, fa, h=0.5), sdf_b=J.Sdf(vc, fc, h=0.5))
    assert r2["max_depth_mm"] == 0.0 and abs(r2["min_clearance_mm"] - 4.0) < 0.8 and abs(r2["patch_p05_mm"] - 4.0) < 0.8


def test_taper_correction_is_zero_beyond_its_length_and_full_at_the_joint_end():
    v, _ = box((0, 50, 0), (10, 100, 10))                # a bar along y, joint end at y = 0
    tp = EL.Taper(v, np.array([0.0, 0, 0]), taper=0.4)
    par = np.array([2.0, 3.0, 1.0, 0.02, -0.01, 0.03])
    d = tp.disp(v, par)
    t = (v[:, 1] - v[:, 1].min()) / 100.0
    assert np.allclose(d[t > 0.4], 0.0)                                   # the far end is not touched
    assert np.linalg.norm(d[t < 0.01] - par[:3], axis=1).max() < 1.0     # full correction at the joint end (rotation about its centre adds < 1 mm here)
    rigid = EL.Taper(v, np.array([0.0, 0, 0]), taper=0.4, rigid=True)
    assert np.allclose(rigid.weight(v), 1.0)


def test_reseat_separates_two_overlapping_toy_bones_and_keeps_the_far_end():
    # fixed 'humerus' block; moving 'ulna' bar whose joint end overlaps it by 6 mm; base joint space 1.5 mm
    hv, hf = box((0, 0, 0), (30, 30, 30))
    uv, uf = box((0, 15 + 70 - 6, 0), (14, 140, 14))     # joint end at y = 15 - 6 + ... overlaps the block top
    gaps = {("hum", "uln"): 1.5}
    bones = {"hum": (hv, hf), "uln": (uv, uf)}
    R = EL.reseat(bones, {}, gaps, np.array([0.0, 15.0, 0.0]), ["uln"], ["hum"], dict(taper=0.5, w_reg=0.05, w_pull=2.0, floor_frac=0.8), log=lambda *a: None)
    jb, ja = list(R["report"]["joint_before"].values())[0], list(R["report"]["joint_after"].values())[0]
    assert jb["max_penetration_mm"] >= 3.0
    assert ja["max_penetration_mm"] <= 1.0
    assert abs(ja["joint_space_p05_mm"] - 1.5) <= 1.5
    far = np.argmax(uv[:, 1])
    assert np.linalg.norm(R["W"]["uln"][uv[:, 1] > uv[:, 1].max() - 20] - uv[uv[:, 1] > uv[:, 1].max() - 20], axis=1).max() < 0.5      # wrist end untouched


def test_guard_helpers():
    from scripts.zanatomy import q225_build as B
    v, f = box((0, 0, 0), (10, 10, 10))
    assert abs(B.mesh_volume(v, f) - 1000.0) < 1e-6
    lo, hi = B.edge_stretch(v, v * 1.1, f)
    assert abs(lo - 1.1) < 1e-6 and abs(hi - 1.1) < 1e-6
    assert B.GUARDS["max_penetration_mm"] <= 1.0 and B.GUARDS["volume_ratio"][0] > 0.9 and B.GUARDS["volume_ratio"][1] < 1.12


def test_dense_own_tree_sees_triangle_interiors():
    v, f = box((0, 0, 0), (40, 40, 40))
    t = EL.own_tree(v, f, spacing=2.0)
    assert t.query(np.array([[0.0, 0.0, 20.0]]))[0][0] < 2.5          # centre of a 40 mm face: its vertices are 28 mm away
