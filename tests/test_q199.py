"""Q199: unit tests of the elbow chain / bone-anchored field / gates (synthetic meshes, plus the committed photograph evidence and, when present, the committed build report)."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.zanatomy import q199_elbow as E  # noqa: E402


def cyl(c, h, r, n=24, axis=1):
    import trimesh
    m = trimesh.creation.cylinder(radius=r, height=h, sections=n)
    v = np.asarray(m.vertices, float)
    if axis == 1:
        v = v[:, [0, 2, 1]]
    return v + np.asarray(c, float), np.asarray(m.faces)


def toy(side="l"):
    """a straight toy arm: humerus y 300..600, radius / ulna y 150..300, at x = -200; plus a fixed 'scapula'"""
    s = "_" + side
    by, raw = {}, {}
    for n, (c, h, r) in {"humerus": ((-200, 450, 0), 300, 10), "radius": ((-195, 225, 0), 150, 6), "ulna": ((-205, 225, 0), 150, 6)}.items():
        v, f = cyl(c, h, r)
        by[n + s] = {"v": v, "f": f, "cat": "bone"}
        raw[n + s] = v.copy()
    v, f = cyl((-150, 640, 0), 60, 20)
    by["scapula" + s] = {"v": v, "f": f, "cat": "bone"}
    raw["scapula" + s] = v.copy()
    return by, raw


def test_evidence_committed_and_framed():
    z = np.load(E.EVID)
    P = z["elbow_pts_mm10"].astype(float) / 10
    assert len(P) > 20000 and P[:, 1].min() >= 311 and P[:, 1].max() <= 355
    assert P[:, 0].max() < -150 and P[:, 0].min() > -300           # her left arm
    sh = z["shaft_y_x_z"]
    assert len(sh) >= 8 and np.all(np.diff(sh[:, 0]) > 0) and sh[:, 1].max() < -150


def test_bary_samples_follow_the_mesh():
    v, f = cyl((0, 0, 0), 40, 5)
    smp = E.bary_samples(v, f, 500)
    p0 = E.at(v, smp)
    p1 = E.at(v + np.array([3.0, -2.0, 1.0]), smp)
    assert np.allclose(p1 - p0, [3.0, -2.0, 1.0])


def test_chain_identity_and_head_pivot():
    by, raw = toy()
    ch = E.Chain("l", by, raw)
    ch.hc = np.array([-200.0, 600.0, 0.0])                          # the toy humerus has no spherical head
    X = by["humerus_l"]["v"]
    assert np.allclose(ch.hum(X), X) and np.allclose(ch.rad(by["radius_l"]["v"]), by["radius_l"]["v"])
    ch.P[:3] = np.radians(5) * np.array([0, 0, 1.0])
    # the head centre does not move under the rotation, the distal end does
    assert np.allclose(ch.hum(ch.hc[None])[0], ch.hc, atol=1e-6)
    d = np.linalg.norm(ch.hum(X) - X, axis=1)
    assert d[X[:, 1].argmin()] > 15.0 and d[X[:, 1].argmax()] < 4.0
    # the forearm swing leaves the wrist centre where it is and has no twist about the forearm axis
    ch.P[7:9] = [0.05, 0.0]
    assert np.allclose(ch.rad(ch.cw[None])[0], ch.cw, atol=1e-6)


def test_field_follows_the_nearest_moving_bone_and_fades_far_away():
    by, raw = toy()
    ch = E.Chain("l", by, raw)
    ch.P[3:6] = [0.0, 0.0, 12.0]                                     # humerus 12 mm anterior
    F = E.Field("l", by, raw, ch)
    near_h = np.array([[-200.0, 420.0, 14.0]])                       # 4 mm off the humerus surface
    near_r = np.array([[-195.0, 200.0, 8.0]])                        # beside the (unmoved) radius
    far = np.array([[-200.0, 420.0, 200.0]])
    assert F(near_h)[0, 2] > 7.0 and abs(F(near_r)[0, 2]) < 3.0 and abs(F(far)[0, 2]) < 3.0
    W, D = F.weights(near_h)
    assert np.allclose(W.sum(0), 1.0)


def test_gate_is_zero_below_and_one_above():
    D = np.array([[0.0, 0.0, 0.5], [0.0, 0.0, 1.5], [0.0, 0.0, 4.0]])
    G = E.gated(D)
    assert np.allclose(G[0], 0) and 0 < G[1, 2] < 1.5 and np.allclose(G[2], D[2])


def test_joint_stat_detects_an_open_joint():
    by, raw = toy()
    # make the Z-source humerus touch the forearm bones: move the raw humerus down 140 mm so it overlaps the proximal ends
    raw2 = {k: v.copy() for k, v in raw.items()}
    raw2["humerus_l"] = raw["humerus_l"] + np.array([0, -150.0, 0])
    by2 = {k: dict(v) for k, v in by.items()}
    by2["humerus_l"] = dict(by["humerus_l"], v=raw2["humerus_l"].copy())
    smp, sel, jj, d0 = E.joint_pairs(raw2, "l", by2)
    assert len(sel) > 20
    closed = E.joint_stat(smp, sel, jj, d0, by2["humerus_l"]["v"], by["radius_l"]["v"], by["ulna_l"]["v"])
    opened = E.joint_stat(smp, sel, jj, d0, by2["humerus_l"]["v"] + np.array([0, 0, 25.0]), by["radius_l"]["v"], by["ulna_l"]["v"])
    assert opened["nearest_surface_gap_mm_median"] > closed["nearest_surface_gap_mm_median"] + 10


def test_attachment_pull_brings_a_detached_end_back():
    by, raw = toy()
    s = "_l"
    v, f = cyl((-205, 230, 0), 60, 3, n=16)                          # a tendon-like tube lying on the ulna in the source
    by["tendon" + s], raw["tendon" + s] = {"v": v.copy() + np.array([0, 0, 0]), "f": f, "cat": "tendon"}, v.copy()
    A = E.Attach("l", by, raw)
    assert "tendon_l" in A.zone
    moved = v + np.array([0, 0, 20.0])                               # the chain left it 20 mm away
    trees = A.trees(by)
    v2, n = A.pull("tendon_l", moved, f, trees)
    assert n > 0
    d_before = np.median(trees["ulna_l"].query(moved)[0])
    d_after = np.median(trees["ulna_l"].query(v2)[0])
    assert d_after < d_before - 5.0 and np.linalg.norm(v2 - moved, axis=1).max() <= E.ATTACH_CAP_MM + 1e-6


def test_lowpass_keeps_mean_motion():
    v, f = cyl((0, 0, 0), 60, 5)
    D = np.zeros_like(v)
    D[v[:, 1] > 0] = [0, 0, 10.0]
    L = E.lowpass(D, f, 10.0)
    assert abs(L.mean(0)[2] - D.mean(0)[2]) < 0.5 and L[:, 2].max() < 10.0 and L[:, 2].min() > 0.0



def grid_patch(x0, x1, ny=8, nx=8, z=0.0):
    xs, ys = np.linspace(x0, x1, nx), np.linspace(0, 70, ny)
    X, Y = np.meshgrid(xs, ys)
    v = np.c_[X.ravel(), Y.ravel(), np.full(X.size, z)]
    f = []
    for j in range(ny - 1):
        for i in range(nx - 1):
            a = j * nx + i
            f += [[a, a + 1, a + nx], [a + 1, a + nx + 1, a + nx]]
    return v, np.array(f)


def test_weld_borders_closes_a_seam_step_and_pins_to_the_fixed_neighbour():
    va, fa = grid_patch(0, 50)
    vb, fb = grid_patch(50, 100)
    vc, fc = grid_patch(100, 150)
    raw = {"a": va.copy(), "b": vb.copy(), "c": vc.copy()}
    by = {"a": {"v": va.copy(), "f": fa}, "b": {"v": vb + [0, 0, 6.0], "f": fb}, "c": {"v": vc.copy(), "f": fc}}
    moved = E.weld_borders(by, raw, ["a", "b", "c"], {"a", "b"})
    step_ab = np.linalg.norm(by["a"]["v"][7::8] - by["b"]["v"][0::8], axis=1)
    step_bc = np.linalg.norm(by["b"]["v"][7::8] - by["c"]["v"][0::8], axis=1)
    assert step_ab.max() < 0.8 and step_bc.max() < 0.8          # both seams closed
    assert np.allclose(by["c"]["v"], vc)                          # the fixed neighbour did not move
    assert set(moved) == {"a", "b"}


def test_close_sigma_and_caps_are_the_documented_ones():
    assert E.GAP_TOL_MM == 5.0 and E.GAP_TOL_VESSEL_MM == 3.0 and E.ATTACH_CAP_MM == 12.0 and E.ADJUST_CAP_MM == 12.0 and E.SEPARATE_MAX_MM == 3.0
    v1 = np.zeros((3, 3)); ref = np.array([[20.0, 0, 0], [0, 5.0, 0], [0, 0, 0]])
    assert np.linalg.norm(E.cap_to(ref, v1) - v1, axis=1).max() <= 12.0 + 1e-9


REPORT = REPO / "data" / "derived" / "Q199_zan_female_q199_build.json"


@pytest.mark.skipif(not REPORT.exists(), reason="Q199 build report not committed yet")
def test_committed_report_states_the_numbers():
    rep = json.loads(REPORT.read_text())["q199"]
    for side in ("left", "right"):
        j = rep["chain"][side]
        assert j["joint_after"]["nearest_surface_gap_mm_median"] < j["joint_before"]["nearest_surface_gap_mm_median"]
        assert j["joint_after"]["nearest_surface_gap_mm_median"] <= 8.0
    assert len(rep["moved_ids"]) > 50
