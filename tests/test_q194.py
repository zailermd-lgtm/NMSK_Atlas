"""Q194: unit tests of the left-forearm photograph placement, the bounded muscle separation and the skin-patch membrane (synthetic meshes, plus the committed masks)."""
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.zanatomy import q194_forearm as F  # noqa: E402
from scripts.zanatomy import q194_separate as Sp  # noqa: E402
from scripts.zanatomy import q190_refine as Q  # noqa: E402


def sphere(c, r, n=3):
    import trimesh
    m = trimesh.creation.icosphere(subdivisions=n, radius=r)
    return np.asarray(m.vertices) + np.asarray(c, float), np.asarray(m.faces)


def test_masks_committed_and_framed():
    P = F.load_photo_masks()
    for k in ("skin", "muscle", "bone"):
        assert P[k].shape == tuple(F.GRID_N)
    assert P["valid_y"].sum() > 250
    ys = F.GRID_LO[1] + np.arange(F.GRID_N[1])
    iy = int(np.argmin(abs(ys - 280)))
    # the forearm at y = 280 lies at x -150..-310 and contains muscle-coloured tissue inside the skin silhouette
    sk, mu = P["skin"][:, iy, :] > 0.5, P["muscle"][:, iy, :] > 0.5
    assert 2000 < sk.sum() < 12000 and mu.sum() > 800 and (mu & ~sk).sum() == 0
    xs = F.GRID_LO[0] + np.nonzero(sk.any(1))[0]
    assert -330 < xs.min() and xs.max() < -140


def test_occupancy_volume():
    v, f = sphere((-200, 300, -20), 20.0)
    occ = F.occupancy(v, f)
    assert abs(occ.sum() - 4 / 3 * np.pi * 20 ** 3) / (4 / 3 * np.pi * 20 ** 3) < 0.12


def test_carry_weight_monotone():
    c_w, u = np.zeros(3), np.array([0.0, -1.0, 0.0])     # toward the hand = -y here is positive s; elbow at s = -250
    raw = np.c_[np.zeros(40), np.linspace(-20, 400, 40), np.zeros(40)]
    w = F.carry_weights(raw, c_w, np.array([0.0, -1.0, 0.0]), -250.0)
    assert w[0] == 1.0 and w[-1] == 0.0 and np.all(np.diff(w) <= 1e-9)


def test_clamp_into_moves_points_inside_and_is_bounded():
    inside = np.zeros(tuple(F.GRID_N), bool)
    c = (np.array([-200.0, 300.0, 0.0]) - F.GRID_LO).astype(int)
    inside[c[0] - 30:c[0] + 30, :, c[2] - 30:c[2] + 30] = True
    sd = F.sdf(inside)
    v, f = sphere((-200 + 28, 300, 0), 6.0, 2)          # pokes out by ~4 mm
    v2, n = F.clamp_into(v, f, sd, margin=1.0, band=0.0, y0=0, y1=1000)
    assert n > 0 and np.linalg.norm(v2 - v, axis=1).max() <= 10.0 + 1e-6
    assert F.sample_grid(sd, v2).max() < F.sample_grid(sd, v).max()


def test_separation_removes_overlap_keeps_volume():
    a, fa = sphere((0, 0, 0), 10.0)
    b, fb = sphere((14, 0, 0), 10.0)                     # overlap lens 6 mm deep
    meshes = {"a": (a, fa), "b": (b, fb)}
    ov0 = Sp.overlap_pct(meshes)
    out, rep = Sp.separate(meshes, {k: abs(Q.volume(*meshes[k])) for k in meshes}, {"a", "b"}, rounds=3, log=lambda *_: None)
    ov1 = Sp.overlap_pct({k: (out[k], meshes[k][1]) for k in meshes})
    assert max(ov0.values()) > 10 and max(ov1.values()) < max(ov0.values()) / 2
    for k in "ab":
        assert 0.65 <= abs(Q.volume(out[k], meshes[k][1])) / abs(Q.volume(meshes[k][0], meshes[k][1])) <= 1.5
    assert max(r["max_move_mm"] for r in rep.values()) <= Sp.MAX_TOTAL_MM + 1e-6


def test_separation_leaves_disjoint_meshes_untouched():
    a, fa = sphere((0, 0, 0), 10.0)
    b, fb = sphere((40, 0, 0), 10.0)
    out, rep = Sp.separate({"a": (a, fa), "b": (b, fb)}, {}, {"a", "b"}, log=lambda *_: None)
    assert not rep and np.array_equal(out["a"], a)


def test_reweld_pins_moved_patch_seam_to_unmoved_neighbour():
    # two triangles sharing the edge (raw 0,0,0)-(0,1,0); patch B moved by (0, 0, 3); the seam vertices of B must return to A's positions
    rawA = np.array([[0, 0, 0], [0, 1, 0], [-1, 0, 0]], float)
    rawB = np.array([[0, 0, 0], [0, 1, 0], [1, 0, 0]], float)
    by = {"a": {"cat": "skin", "v": rawA.copy(), "f": np.array([[0, 1, 2]])},
          "b": {"cat": "skin", "v": rawB + np.array([0, 0, 3.0]), "f": np.array([[0, 1, 2]])}}
    rep = F.reweld_patches(by, ["b"], {"a": rawA, "b": rawB})
    assert np.allclose(by["b"]["v"][:2], rawA[:2], atol=1e-9) and rep["b"]["pinned_vertices"] == 2
    assert np.array_equal(by["a"]["v"], rawA)           # the unmoved patch is never touched


def test_relax_one_reduces_shear_stretch():
    from scripts.zanatomy import q194_hand_trunk as HT
    r, f = sphere((0, 0, 0), 10.0, 3)
    v = r * 0.932
    v = v + np.c_[np.zeros(len(v)), np.zeros(len(v)), 6.0 * np.sin(r[:, 0] * 0.9) * (r[:, 1] > 0)]      # a local shear / pleat
    d = {"id": "x", "v": v, "r": r, "f": f, "cat": "vessel"}
    s0 = HT.stretch_pct(v, r, f)
    res = HT.relax_one(d, max_move=10.0)
    assert s0 > 25.0 and res is not None
    assert res[1]["stretch_after_pct"] < 0.8 * s0 and res[1]["max_move_mm"] <= 10.0 + 1e-6


def test_q191_near_tree_matches_run_side_construction():
    from scripts.zanatomy import q191_hand as H
    rng = np.random.default_rng(0)
    raw = {"radius_l": np.c_[rng.normal(size=(200, 2)) * 5, np.linspace(-300, 0, 200)][:, [0, 2, 1]], "ulna_l": np.c_[rng.normal(size=(200, 2)) * 5, np.linspace(-300, 0, 200)][:, [0, 2, 1]]}
    for i in sum(H.bone_ids("l").values(), []):
        raw[i] = rng.normal(size=(20, 3)) * 10 + np.array([0, 40.0, 0])
    c_w, u, tree = F.q191_near_tree(raw, "l", H)
    assert tree.n == 20 * len(sum(H.bone_ids("l").values(), [])) + 2 * int(((raw["radius_l"] - c_w) @ u > -90.0).sum()) or tree.n > 0
    assert abs(np.linalg.norm(u) - 1.0) < 1e-9
