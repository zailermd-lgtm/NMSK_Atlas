"""Q186c: pure parts of scripts/zanatomy/trunk_refit_q186c.py (no CT data needed)."""
import numpy as np

from scripts.zanatomy import trunk_refit_q186c as T


def test_smoothstep_bounds():
    x = np.array([-1.0, 0.0, 0.5, 1.0, 2.0])
    y = T.smoothstep(x)
    assert y[0] == 0 and y[1] == 0 and y[3] == 1 and y[4] == 1 and abs(y[2] - 0.5) < 1e-12


def test_trunk_weight_is_one_inside_zero_far_and_continuous():
    axis = lambda y: (np.zeros_like(y), np.zeros_like(y))
    q = np.array([[0, 300, 0], [100, 300, 0], [165, 300, 0], [215, 300, 0], [400, 300, 0], [0, 900, 0], [0, -400, 0]], float)
    w = T.trunk_weight(q, axis)
    assert w[0] == 1 and w[1] == 1 and w[2] == 1 and w[3] == 0 and w[4] == 0 and w[5] == 0 and w[6] == 0
    r = np.linspace(150, 230, 400)
    ww = T.trunk_weight(np.stack([r, np.full_like(r, 300), np.zeros_like(r)], 1), axis)
    assert np.all(np.diff(ww) <= 1e-12) and np.max(np.abs(np.diff(ww))) < 0.02      # monotone, no step


def test_bilinear_wraps_theta():
    ys = np.arange(0.0, 50.0, 5.0)
    ths = np.radians(np.arange(-180.0, 180.0, 2.0))
    grid = np.tile(np.cos(ths), (len(ys), 1))
    a = T.bilinear(grid, ys, ths, np.array([12.0]), np.array([np.radians(179.5)]))
    b = T.bilinear(grid, ys, ths, np.array([12.0]), np.array([np.radians(-180.5)]))
    assert abs(a[0] - b[0]) < 1e-3 and a[0] < -0.99


def test_rbf_reproduces_anchors_and_jacobian_of_translation_is_identity():
    rng = np.random.default_rng(0)
    src = rng.uniform(-50, 50, (200, 3))
    dst = src + np.array([3.0, -2.0, 5.0])
    f = T.rbf(src, dst, smoothing=0.0)
    assert np.abs(T.apply_rbf(f, src) - dst).max() < 1e-6
    st = T.jacobian_stats(f, rng.uniform(-30, 30, (50, 3)))
    assert abs(st["min"] - 1.0) < 1e-3 and abs(st["max"] - 1.0) < 1e-3


def test_bone_targets_cover_ribs_and_vertebrae():
    t = T.bone_targets()
    assert len(t) == 24 + 17
    assert t["zan_first_rib_l"] == 92 and t["zan_twelfth_rib_r"] == 115
    assert t["zan_vertebra_t1"] == 43 and t["zan_vertebra_l5"] == 27


def test_grid_field_matches_direct_evaluation_and_clamp_helper_is_pure():
    rng = np.random.default_rng(1)
    src = rng.uniform(-60, 60, (300, 3))
    dst = src + 8 * np.sin(src / 40.0)                 # smooth field
    f = T.rbf(src, dst, smoothing=10.0)
    pts = rng.uniform(-40, 40, (400, 3))
    g = T.GridField(f, pts, step=6.0)
    assert np.abs(g(pts) - f(pts)).max() < 0.5


def test_shoulder_girdle_is_inside_the_reach_at_shoulder_height_only():
    axis = lambda y: (np.zeros_like(y), np.zeros_like(y))
    lo = T.trunk_weight(np.array([[250.0, 300.0, 0.0]]), axis)[0]
    hi = T.trunk_weight(np.array([[250.0, 540.0, 0.0]]), axis)[0]
    assert lo == 0.0 and hi > 0.9


def test_flip_fraction_detects_a_mirrored_triangle():
    v0 = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0]], float)
    f = np.array([[0, 1, 2]])
    assert T._flip_frac(v0, v0, f) == 0.0
    v1 = v0.copy(); v1[:, 2] = 0; v1[[1, 2]] = v1[[2, 1]]
    assert T._flip_frac(v0, v1, f) == 1.0
