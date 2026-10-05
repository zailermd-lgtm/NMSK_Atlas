"""Q192: pure parts of scripts/zanatomy/q192_left_hand.py (synthetic data) + the stored evidence / fit / build output when present."""
import json
from pathlib import Path

import numpy as np
import pytest
from scipy.spatial.transform import Rotation as Rot

from scripts.zanatomy import q192_left_hand as Q

REPO = Path(__file__).resolve().parents[1]


def test_sim_apply_pivot_is_fixed_and_scale_is_about_it():
    c = np.array([5.0, -3.0, 2.0])
    x = np.r_[0.3, -0.2, 0.5, 0, 0, 0, 1.05]
    assert np.allclose(Q.sim_apply(x, c[None], c), c)
    P = np.random.default_rng(0).normal(size=(50, 3)) * 10 + c
    Y = Q.sim_apply(x, P, c)
    assert np.allclose(np.linalg.norm(Y - c, axis=1), 1.05 * np.linalg.norm(P - c, axis=1))


def test_chain_apply_joint_stays_and_distal_bone_follows_proximal():
    cs = [np.array([0.0, 0, 0]), np.array([0.0, 10, 0])]
    P = [np.array([[0.0, 5, 0], [0.0, 10, 0]]), np.array([[0.0, 15, 0], [0.0, 20, 0]])]
    th = np.array([[0.0, 0, np.pi / 2], [0.0, 0, 0]])                 # joint 0 turns 90 deg about z: the whole chain swings, joint 1 unbent
    X = Q.chain_apply(th, P, cs)
    assert np.allclose(X[0][1], [-10, 0, 0], atol=1e-9) and np.allclose(X[1][1], [-20, 0, 0], atol=1e-9)
    th2 = np.array([[0.0, 0, 0], [0.0, 0, np.pi / 2]])               # joint 1 only: the distal bone turns about its own joint, the proximal one stays
    X2 = Q.chain_apply(th2, P, cs)
    assert np.allclose(X2[0], P[0]) and np.allclose(X2[1][0], [-5, 10, 0], atol=1e-9)


def test_trimmed_ignores_outliers():
    a = np.r_[np.ones(90), 100.0 * np.ones(10)]
    assert Q.trimmed(a, 0.9) == 1.0


def test_joint_point_is_near_the_previous_segment():
    seg = np.c_[np.zeros(100), np.linspace(0, 30, 100), np.zeros(100)]
    j = Q.joint_point(seg, np.array([0.0, -5.0, 0.0]))
    assert j[1] < 5.0


def test_apply_transforms_roundtrip():
    from scripts.zanatomy.q191_hand import kabsch
    rng = np.random.default_rng(1)
    r = rng.normal(size=(40, 3)) * 10
    R = Rot.from_rotvec([0.4, -0.2, 0.9]).as_matrix()
    v = 1.03 * r @ R.T + np.array([3.0, 4.0, -5.0])
    s, R2, t = kabsch(r, v, scale=True)
    out = Q.apply_transforms({"a": r}, {"a": {"s": s, "R": R2.tolist(), "t": t.tolist()}})["a"]
    assert np.abs(out - v).max() < 1e-9


def test_frame_calibration_matches_module_constants():
    cal = json.loads((REPO / "data" / "derived" / "Q192_frame_calibration.json").read_text())["adopted"]
    assert cal["y_offset"] == Q.CAL["y_offset"] and cal["AZ"] == Q.CAL["az"] and cal["AX_left"] == Q.CAL["ax"]["l"] and cal["px_mm"] == Q.CAL["px_mm"]


def test_evidence_file_is_real_left_hand_data():
    ev = Q.load_evidence()
    h, fa = ev["hand"], ev["forearm"]
    assert len(h) > 200000 and len(fa) > 50000
    assert h[:, 0].max() < -60 and fa[:, 0].max() < -120                 # her LEFT side is -x in the atlas
    assert 30 <= h[:, 1].min() and h[:, 1].max() <= 215 and fa[:, 1].min() >= 150     # hand levels / wrist-forearm levels in atlas y
    roi = np.unpackbits(ev["hand_roi"], axis=None)[:int(np.prod(ev["hand_roi_shape"]))].reshape(ev["hand_roi_shape"]).astype(bool)
    assert roi.sum() > 1e6                                              # the hand silhouettes (no area limit) are stored


def _fit():
    p = REPO / "data" / "derived" / "Q192_left_hand_fit.json"
    if not p.exists():
        pytest.skip("Q192 fit not stored")
    return json.loads(p.read_text())


def test_stored_fit_is_a_set_of_proper_similarities_with_a_unique_answer():
    fit = _fit()
    T = fit["transforms_from_Z_source_frame"]
    assert len(T) == 29                                                    # 8 carpals + 5 metacarpals + 14 phalanges + radius + ulna
    for i, t in T.items():
        R = np.asarray(t["R"])
        assert np.allclose(R @ R.T, np.eye(3), atol=1e-6) and np.linalg.det(R) > 0.999, i   # no reflection: it is a left hand
        assert 0.9 <= t["s"] <= 1.1, i
        assert t["max_residual_mm"] < 0.05, i                              # rigid per bone: one similarity reproduces the articulated mesh
    rep = fit["report"]
    assert rep["hand_rigid"]["starts_in_best_basin"] >= 0.6 * rep["hand_rigid"]["n_starts"]
    nxt = rep["hand_rigid"]["next_distinct_optimum_J_and_shift_mm"]
    assert nxt is None or nxt[0] > rep["hand_rigid"]["J"]


def test_q192_build_leaves_everything_but_the_left_hand_unchanged_if_present():
    after, before = REPO / "build" / "viewer_zan_female_q192", REPO / "build" / "viewer_zan_female_q191"
    d = REPO / "data" / "derived" / "Q192_ship_diff.json"
    if not (after / "manifest.json").exists() or not before.exists() or not d.exists():
        pytest.skip("Q192 build / diff not present")
    diff = json.loads(d.read_text())
    assert diff["right_hand_changed"] == 0 and diff["outside_left_hand_scope_changed"] == []
