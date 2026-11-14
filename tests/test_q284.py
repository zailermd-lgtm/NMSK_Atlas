"""Q284: moment arms from this body's geometry -- the maths against hand-computable cases, and the committed data / wiring."""
import json
import math
import re
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts/anatomy/q284"))
sys.path.insert(0, str(REPO / "scripts/anatomy/q241"))
import moments as MO  # noqa: E402

KEYS = ["own_m", "own_f", "comb_m", "comb_f", "base_m", "base_f"]


def hinge_rig(axis=(0.0, 0.0, 1.0)):
    return {"segments": [{"id": "root", "par": -1}, {"id": "child", "par": 0}],
            "joints": [{"id": "knee_r", "seg": 1, "par": 0, "ref": -1, "c": [0.0, 0.0, 0.0],
                        "dof": [{"k": "flex", "a": list(axis), "lo": -120.0, "hi": 120.0, "q0": 0.0}]}],
            "regions": []}


def test_straight_line_moment_arm_matches_the_analytic_value():
    """two points, one on each side of a hinge: r = -dL/dtheta = -z . (B x u), u = unit(B - A)"""
    rig = hinge_rig()
    A, B = np.array([30.0, 120.0, 5.0]), np.array([15.0, -80.0, -4.0])
    path = {"p": np.array([A, B]), "seg": np.array([0, 1]), "wraps": {}}
    got = MO.moment_arms(rig, path, "j", "knee_r", angles=[0.0])["r"]["flex"][0]
    u = (B - A) / np.linalg.norm(B - A)
    want = -np.array([0, 0, 1.0]) @ np.cross(B, u)
    assert got == pytest.approx(want, abs=0.02)


def test_moment_arm_follows_the_joint_angle():
    """the same two points, evaluated at 60 deg: the child point is rotated first"""
    rig = hinge_rig()
    A, B = np.array([30.0, 120.0, 0.0]), np.array([15.0, -80.0, 0.0])
    path = {"p": np.array([A, B]), "seg": np.array([0, 1]), "wraps": {}}
    got = MO.moment_arms(rig, path, "j", "knee_r", angles=[60.0])["r"]["flex"][0]
    t = math.radians(60.0)
    Rz = np.array([[math.cos(t), -math.sin(t), 0], [math.sin(t), math.cos(t), 0], [0, 0, 1]])
    Bt = Rz @ B
    u = (Bt - A) / np.linalg.norm(Bt - A)
    assert got == pytest.approx(-np.array([0, 0, 1.0]) @ np.cross(Bt, u), abs=0.02)


def test_points_on_one_segment_give_no_moment_arm():
    rig = hinge_rig()
    path = {"p": np.array([[0, -20.0, 0], [5, -90.0, 3]]), "seg": np.array([1, 1]), "wraps": {}}
    assert MO.crossed(rig, path["seg"]) == []
    assert MO.moment_arms(rig, path, "j", "knee_r", angles=[0.0])["r"]["flex"][0] == pytest.approx(0.0, abs=1e-6)


def test_sphere_wrap_length_is_tangents_plus_arc():
    R, d = 20.0, 50.0
    a, b, c = np.array([0.0, d, 0.0]), np.array([0.0, -d, 0.0]), np.zeros(3)
    want = 2 * math.sqrt(d * d - R * R) + R * (math.pi - 2 * math.acos(R / d))
    assert MO.wrapped(a, b, c, R) == pytest.approx(want, rel=1e-9)
    assert MO.wrapped(a, b + np.array([60.0, 0, 0]), c, 1.0) == pytest.approx(np.linalg.norm(b + np.array([60.0, 0, 0]) - a))   # clears it


def test_oriented_wrap_goes_round_the_muscle_side():
    """a and b 90 deg apart: the short way round (90 deg) or, when the muscle lies on the other side, the long way (270 deg)"""
    R, d = 10.0, 30.0
    a, b, c = np.array([d, 0.0, 0.0]), np.array([0.0, d, 0.0]), np.zeros(3)
    tang = 2 * math.sqrt(d * d - R * R)
    short = MO.wrapped(a, b, c, R, n0=[0, 0, 1.0])
    long_ = MO.wrapped(a, b, c, R, n0=[0, 0, -1.0])
    assert short == pytest.approx(np.linalg.norm(b - a))      # 90 deg is less than the two tangent angles: straight
    assert long_ == pytest.approx(tang + R * (1.5 * math.pi - 2 * math.acos(R / d)), rel=1e-9)


def test_cylinder_wrap_adds_the_axial_run():
    R, d, dz = 15.0, 40.0, 30.0
    a, b, c, u = np.array([0.0, d, 0.0]), np.array([0.0, -d, dz]), np.zeros(3), np.array([0, 0, 1.0])
    flat = 2 * math.sqrt(d * d - R * R) + R * (math.pi - 2 * math.acos(R / d))
    assert MO.wrapped_cyl(a, b, c, u, R) == pytest.approx(math.hypot(flat, dz), rel=1e-9)


def test_a_wrap_holds_the_moment_arm_at_its_radius():
    """a path held round a hinge by a cylinder of radius R: the moment arm is R while it wraps"""
    rig = hinge_rig()
    R = 25.0
    A, B = np.array([0.0, 120.0, 0.0]), np.array([0.0, -120.0, 0.0])      # the straight line passes through the axis
    path = {"p": np.array([A, B]), "seg": np.array([0, 1]),
            "wraps": {"knee_r": {"c": [0, 0, 0], "R": R, "par": 0, "u": [0, 0, 1.0], "n0": [0, 0, 1.0]}}}
    r = MO.moment_arms(rig, path, "j", "knee_r", angles=[0.0, 20.0])["r"]["flex"]
    assert abs(r[0]) == pytest.approx(R, rel=1e-3) and abs(r[1]) == pytest.approx(R, rel=1e-3)


def test_principal_curve_follows_a_bent_tube():
    t = np.linspace(0, math.pi / 2, 400)
    pts = np.c_[100 * np.cos(t), 100 * np.sin(t), np.zeros_like(t)]
    rng = np.random.default_rng(1)
    v = np.repeat(pts, 10, axis=0) + rng.normal(0, 3, (4000, 3))
    P = MO.principal_curve(v)
    rad = np.linalg.norm(P[:, :2], axis=1)
    assert np.abs(rad[2:-2] - 100).max() < 8          # it follows the arc, not the chord (whose midpoint is 70.7 from the centre)


@pytest.mark.parametrize("key", KEYS)
def test_committed_moment_data(key):
    f = REPO / "data/anatomy" / ("moment_arms_%s.json" % key)
    d = json.loads(f.read_text(encoding="utf-8"))
    assert d["key"] == key and d["round"] == "Q284" and d["s"]
    n = sum(1 for s in d["s"].values() if s["j"])
    assert n > 50
    for sid, s in d["s"].items():
        for jid, e in s["j"].items():
            dofs, sweep, angs, r = e
            assert all(len(r[k]) == len(angs) for k in dofs), (sid, jid)
            assert all(abs(x) <= 150 for k in dofs for x in r[k]), (sid, jid)
    lit = json.loads((REPO / "data/anatomy/moment_arm_literature_q284.json").read_text(encoding="utf-8"))
    for e in lit["entries"]:
        assert e["quote"] and e["pmid"].isdigit() and e["doi"].startswith("10.")


def test_iliopsoas_is_a_hip_flexor_on_every_page_that_has_it():
    """flexor at 45 deg on every structure; at 0 and 90 deg on at least 80 % of them. The known exceptions are documented in
    PROJECT_STATE Q284 (Combined F left psoas -3 mm at 0 deg; Base F psoas -10 mm at 90 deg, its mesh touching the pubic bone 14 mm
    below the hip centre, a fixed pulley in this model) -- kept as computed, not tuned away."""
    seen, pos = 0, {0.0: 0, 90.0: 0}
    for key in KEYS:
        d = json.loads((REPO / "data/anatomy" / ("moment_arms_%s.json" % key)).read_text(encoding="utf-8"))
        for sid, s in d["s"].items():
            if re.search(r"(psoas_major|iliacus_muscle|iliacus|iliopsoas)_(r|l)$", sid):
                hip = [e for j, e in s["j"].items() if j.startswith("hip_")]
                if hip:
                    seen += 1
                    angs, flex = hip[0][2], hip[0][3]["flex"]
                    assert flex[angs.index(45.0)] > 0, (key, sid, flex)
                    for a in pos:
                        pos[a] += flex[angs.index(a)] > 0
    assert seen >= 8 and all(v >= 0.8 * seen for v in pos.values()), (seen, pos)


def test_templates_and_regen_carry_the_moments_block():
    for t in ("viewer/atlas_viewer.template.html", "viewer/zan_atlas.template.html"):
        s = (REPO / t).read_text(encoding="utf-8")
        assert s.count("<!-- NMSK-MOMENTS begin -->") == 1 and s.count("<!-- NMSK-MOMENTS end -->") == 1
    assert "q284/build_moments.py" in (REPO / "scripts/regen_template_only.py").read_text(encoding="utf-8")
