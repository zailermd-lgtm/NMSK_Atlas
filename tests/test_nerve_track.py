"""Nerve tracking through full-resolution cryosection crops (scripts/cryo/vhf_nerve_track.py)."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from scripts.cryo import vhf_nerve_track as nt  # noqa: E402


def _crops(tmp_path):
    ys = [-100, -101, -102]
    levels = {str(y): {"zi": 10, "dcm": "x", "RS": -7.0 + 0.1 * i, "CS": -120.0, "z_ras": y - 885.229, "z_src": y - 800,
                       "windows": {"right": [60, 660, 36, 636]}} for i, y in enumerate(ys)}
    b = {"y_atlas": ys, "levels": levels, "box_atlas": {"right": [0, 200, -150, 60]}, "origin": [7.769, -885.229, 14.137],
         "H": 405, "sc": 0.99, "note": ""}
    json.dump(b, open(tmp_path / "t_bbox.json", "w"))
    a = np.lib.format.open_memmap(tmp_path / "t_right.npy", mode="w+", dtype=np.uint8, shape=(3, 600, 600, 3)); a[:] = 200; a.flush()
    return nt.Crops(str(tmp_path / "t"), "right")


def test_crop_mapping_round_trip(tmp_path):
    c = _crops(tmp_path)
    for x, z in ((100.0, -40.0), (12.5, 55.0), (180.0, -140.0)):
        pr, pc = c.atlas_to_px(-101, x, z); x2, z2 = c.px_to_atlas(-101, pr, pc)
        assert abs(x2 - x) < 1e-6 and abs(z2 - z) < 1e-6
    # subject's right is the low-column side of the photograph and posterior is the top
    pr1, pc1 = c.atlas_to_px(-101, 150.0, 0.0); pr2, pc2 = c.atlas_to_px(-101, 50.0, -100.0)
    assert pc1 < pc2 and pr2 < pr1


def test_fascicle_texture_detector_finds_the_honeycomb_only():
    rng = np.random.default_rng(0)
    im = np.full((300, 300, 3), 200, np.uint8)                      # fat
    yy, xx = np.ogrid[:300, :300]
    im[(yy - 220) ** 2 + (xx - 150) ** 2 < 60 ** 2] = 60             # a muscle belly (its edge with the fat must not fire)
    for r in range(90, 130, 7):                                       # honeycomb 40 x 40 px: pale cells with dark walls
        for cc in range(90, 130, 7):
            im[r:r + 7, cc:cc + 7] = 80; im[r + 1:r + 6, cc + 1:cc + 6] = 135
    im[..., 1] = (im[..., 0] * 0.7).astype(np.uint8); im[..., 2] = (im[..., 0] * 0.5).astype(np.uint8)
    im = np.clip(im.astype(int) + rng.integers(-3, 4, im.shape), 0, 255).astype(np.uint8)
    lab, n = nt.nerve_blobs(im)
    assert n == 1
    cy, cx = [float(v) for v in np.argwhere(lab == 1).mean(0)]
    assert abs(cy - 110) < 6 and abs(cx - 110) < 6


def test_viterbi_follows_the_smooth_chain_through_a_gap():
    ys = list(range(-100, -121, -1)); per = {}
    for i, y in enumerate(ys):
        cands = [{"x": 100.0 + 0.3 * i, "z": -40.0, "area_mm2": 30.0, "inside": 1.0, "lab": 1},   # the nerve, drifting 0.3 mm / level
                 {"x": 100.0 + 0.3 * i + 25.0, "z": -40.0, "area_mm2": 30.0, "inside": 1.0, "lab": 2}]   # a distractor 25 mm away
        if 8 <= i <= 10:
            cands = [cands[1]]                                        # three levels where only the distractor is detected
        per[y] = cands
    chain = nt.viterbi(ys, per, {"x": 100.0, "z": -40.0})
    assert [c[0] for c in chain] == ys
    xs = [c[1] for c in chain]; idx = [c[3] for c in chain]
    assert idx[8] is None and idx[9] is None and idx[10] is None      # gaps, not the distractor
    assert idx[11] == 0 and abs(xs[-1] - (100.0 + 0.3 * 20)) < 1e-6


def test_seed_rule_uses_the_bony_landmarks():
    meshes = {"hip_bone_r": {"v": np.array([[60.0, -60.0, -30.0], [80.0, 0.0, 0.0], [50.0, 40.0, -10.0]])},
              "femur_r": {"v": np.array([[160.0, -30.0, -20.0], [110.0, 0.0, -10.0], [100.0, -400.0, 0.0], [120.0, -50.0, 0.0]])}}
    s = nt.seed_rule("sciatic", meshes, "right")
    assert s["y"] == pytest.approx(-80.0) and s["x"] == pytest.approx(110.0) and s["z"] == pytest.approx(-35.0)


def test_scorer_features_and_augmentation_shapes():
    from scripts.cryo import vhf_nerve_scorer as sc
    rng = np.random.default_rng(1)
    X = rng.integers(0, 255, (5, 48, 48, 3), dtype=np.uint8); Y = np.array([1, 0, 1, 0, 0], np.uint8)
    F = sc.features(X)
    assert F.shape == (5, 144 + 3 + 3 + 1 + 4) and np.isfinite(F).all()
    Xa, Ya = sc.augment(X, Y)
    assert Xa.shape == (40, 48, 48, 3) and Ya.sum() == 8 * Y.sum()
    # a rotation of a patch gives the same pooled energy features (rotation-invariant parts)
    F2 = sc.features(np.rot90(X, 1, axes=(1, 2)))
    assert np.allclose(F[:, 147:151], F2[:, 147:151], atol=1e-4)
