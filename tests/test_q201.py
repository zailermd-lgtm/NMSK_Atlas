"""Q201: unit tests of the male elbow chain (his evidence), the blend-delta field, the skin welds, the scope; plus the committed evidence / report / audit when present."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.zanatomy import q199_elbow as E  # noqa: E402
from scripts.zanatomy import q201_chain as C  # noqa: E402


def lumpy(c, h, r, n=24, lump=0.0):
    """a cylinder along y with an asymmetric lump (so its roll about the axis is visible)"""
    import trimesh
    m = trimesh.creation.cylinder(radius=r, height=h, sections=n)
    v = np.asarray(m.vertices, float)[:, [0, 2, 1]]
    if lump:
        ang = np.arctan2(v[:, 2], v[:, 0])
        v[:, [0, 2]] *= (1.0 + lump * np.exp(-(ang ** 2) / 0.3))[:, None]
    return v + np.asarray(c, float), np.asarray(m.faces)


def toy(side="l"):
    s = "_" + side
    by, raw = {}, {}
    for n, (c, h, r) in {"humerus": ((-200, 450, 0), 300, 10), "radius": ((-195, 225, 0), 150, 6), "ulna": ((-205, 225, 0), 150, 6)}.items():
        v, f = lumpy(c, h, r, lump=0.4)
        by[n + s] = {"v": v, "f": f, "cat": "bone"}
        raw[n + s] = v.copy()
    return by, raw


def evidence_from(by, side="l", shift=np.zeros(3)):
    """evidence arrays (atlas mm) made from bone surfaces: shafts outside the zone, solid union inside"""
    s = "_" + side
    ev = {}
    uni = []
    for b in C.BONES:
        P = E.at(by[b + s]["v"], E.bary_samples(by[b + s]["v"], by[b + s]["f"], 6000, seed=2)) + shift
        ok = P[:, 1] > C.ZONE[1] if b == "humerus" else P[:, 1] < C.ZONE[0]
        ev[f"shaft_{b}_{side}"] = P[ok]
    g = np.mgrid[-215:-185:1.0, C.ZONE[0]:C.ZONE[1]:1.0, -15:15:1.0].reshape(3, -1).T
    ev[f"union_{side}"] = g + shift
    return ev


def test_evidence_committed_and_framed():
    ev = C.load_evidence()
    for s, sign in (("l", -1), ("r", 1)):
        U = ev[f"union_{s}"]
        assert len(U) > 20000 and U[:, 1].min() >= C.ZONE[0] - 1 and U[:, 1].max() <= C.ZONE[1] + 1
        assert np.all(sign * U[:, 0] > 120) and np.all(sign * U[:, 0] < 320)             # his arm lateral of the trunk, on the side
        for b in C.BONES:
            P = ev[f"shaft_{b}_{s}"]
            assert len(P) > 5000
            assert (P[:, 1].min() > C.ZONE[1] - 1) if b == "humerus" else (P[:, 1].max() < C.ZONE[0] + 1)
    assert ev["shaft_humerus_l"][:, 1].max() > 590 and ev["shaft_ulna_r"][:, 1].min() < 100          # head and wrist are in the CT labels


def test_chain_identity_and_bend_only_at_the_elbow_end():
    by, raw = toy()
    ch = C.ChainM("l", by)
    X = by["humerus_l"]["v"]
    assert np.allclose(ch.hum(X), X) and np.allclose(ch.rad(by["radius_l"]["v"]), by["radius_l"]["v"])
    ch.p["humerus"][7:10] = [0, 0, 10.0]
    d = np.linalg.norm(ch.hum(X) - X, axis=1)
    assert d[X[:, 1] > 540].max() < 1e-6 and d[X[:, 1] < 310].min() > 9.0          # the head half does not bend, the elbow end moves the full amount
    ch.p["ulna"][7:10] = [0, 5.0, 0]
    Y = by["ulna_l"]["v"]
    dy = np.linalg.norm(ch.uln(Y) - Y, axis=1)
    assert dy[Y[:, 1] < 190].max() < 1e-6 and dy[Y[:, 1] > 290].min() > 4.5       # the forearm bones bend at their PROXIMAL (elbow) end


def test_similarity_rotates_about_the_bone_centroid_and_scales():
    by, raw = toy()
    ch = C.ChainM("l", by)
    ch.p["radius"][:3] = np.radians(30) * np.array([0, 1.0, 0])
    Y = by["radius_l"]["v"]
    Z = ch.rad(Y)
    c = Y.mean(0)
    assert np.allclose(np.linalg.norm(Z - c, axis=1), np.linalg.norm(Y - c, axis=1), atol=1e-6)         # rotation about its own centroid
    ch.p["radius"][6] = 1.1
    assert np.allclose(np.linalg.norm(ch.rad(Y) - c, axis=1), 1.1 * np.linalg.norm(Y - c, axis=1), atol=1e-6)


def test_label_fit_recovers_a_translation_and_a_roll_of_a_lumpy_bone():
    by, raw = toy()
    shift = np.array([0.0, -12.0, 9.0])
    ev = evidence_from(by, shift=shift)
    F = C.Fit("l", by, raw, ev, n=1500)
    cands = F.label_fit("radius")
    cost, p, roll = cands[0]
    assert len(cands) == 7 and cands[0][0] <= cands[-1][0]            # all roll starts are returned, best first
    ch = F.chain({**F.cur, "radius": p})
    moved = ch.rad(by["radius_l"]["v"]) - by["radius_l"]["v"]
    # only the part of the radius below the zone is evidence; the fit puts it onto the shifted label
    low = by["radius_l"]["v"][:, 1] < 200
    assert np.linalg.norm(moved[low].mean(0) - shift) < 4.0


def test_fit_stats_report_the_union_and_the_joint_keys():
    by, raw = toy()
    ev = evidence_from(by)
    F = C.Fit("l", by, raw, ev, n=800)
    st = F.stats(F.cur)
    for k in ("label_surface_to_Z_mm_median", "Z_to_label_mm_median", "union_Z_outside_solid_pct", "union_boundary_to_Z_mm_median", "joint", "wrist_gap_change_mm_mean_abs"):
        assert k in st
    assert st["label_surface_to_Z_mm_median"] < 3.0          # the toy evidence is the toy bones


def test_bounds_keep_scale_and_bend_inside_the_documented_limits():
    assert C.SCALE_ABS["radius"][0] >= 0.9 and C.SCALE_ABS["humerus"][1] <= 1.2 and max(C.BEND_MAX_MM.values()) <= 15.0 and C.ROT_MAX_DEG <= 75.0


class StubXf:
    """the pieces of ZanToVhf the delta field uses: two unit bone clouds (a moving 'radius_l' and a fixed 'carpals_l/x'), identity transforms"""

    def __init__(self):
        def cloud(c, h, r):
            v, f = lumpy(c, h, r)
            return E.at(v, E.bary_samples(v, f, 4000, seed=1))
        r = cloud((0, 100, 0), 200, 6)
        k = cloud((0, -30, 0), 60, 8)
        from scipy.spatial import cKDTree
        self.unit_names = ["radius_l", "carpals_l/x"]
        self.unit_A = [np.eye(3), np.eye(3)]
        self.unit_t = [np.zeros(3), np.zeros(3)]
        pts = [r, k]
        self.trees = [cKDTree(p) for p in pts]
        self.lo = np.array([p.min(0) for p in pts])
        self.hi = np.array([p.max(0) for p in pts])
        self.piece_map = {}
        self._tree = cKDTree(np.vstack(pts))

    def _allowed(self, cls):
        return np.array([0, 1]), self._tree

    def limb_class(self, v):
        return "arm"


def test_delta_field_is_the_weighted_bone_displacement_and_zero_beside_fixed_bones(monkeypatch):
    from scripts.zanatomy import q201_field as FLD
    by, raw = toy()
    ch = C.ChainM("l", by)
    ch.p["radius"][3:6] = [0, 0, 10.0]                                   # the radius moves 10 mm anterior
    DF = FLD.DeltaField(StubXf(), {"l": ch})
    near_r = np.array([[0.0, 150.0, 8.0]])                               # beside the moving bone
    near_c = np.array([[0.0, -30.0, 10.0]])                              # beside the fixed one
    monkeypatch.setattr(FLD.Q, "spatial_clusters", lambda v, *a, **k: (np.zeros(len(v), int), 1))
    d1 = DF.delta("some_muscle_l", near_r)
    d2 = DF.delta("some_muscle_l", near_c)
    assert d1[0, 2] > 8.0 and abs(d2[0, 2]) < 1.0
    assert np.allclose(DF.delta("some_muscle_l", np.array([[0.0, -200.0, 0.0]])), 0.0, atol=1e-6)         # beyond the fixed carpal the nearest unit is the fixed one: the blend follows it (D = 0)
    assert abs(DF.delta("a_rigid_follower", near_r)[0, 2]) < 10.1


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


def test_weld_all_skin_closes_seams_of_both_sides_without_touching_the_midline():
    from scripts.zanatomy import q201_refine as R
    by, raw = {}, {}
    for s in ("l", "r"):
        va, fa = grid_patch(0, 50)
        vb, fb = grid_patch(50, 100)
        by[f"skin_a_{s}"], by[f"skin_b_{s}"] = {"v": va.copy(), "f": fa, "cat": "skin"}, {"v": vb + [0, 0, 12.0], "f": fb, "cat": "skin"}
        raw[f"skin_a_{s}"], raw[f"skin_b_{s}"] = va.copy(), vb.copy()
    by["skin_mid"], raw["skin_mid"] = {"v": va.copy(), "f": fa, "cat": "skin"}, va.copy()
    mid0 = by["skin_mid"]["v"].copy()
    rep = R.weld_all_skin(by, raw, log=lambda *a: None)
    for s in ("l", "r"):
        assert rep[s]["before"]["steps_gt_3mm"] >= 1 and rep[s]["after"]["steps_gt_3mm"] == 0
        assert rep[s]["after"]["max_step_mm"] < 1.5
    assert np.array_equal(by["skin_mid"]["v"], mid0)


def test_scope_takes_forearm_and_wrist_structures_not_the_trunk_or_the_shoulder():
    from scripts.zanatomy import q201_refine as R
    jc, wc = np.array([-240.0, 270.0, -50.0]), np.array([-150.0, 110.0, 100.0])
    sc = R.make_scope({"l": jc}, {"l": wc})
    far = np.array([[-100.0, 560.0, 0.0]] * 200)
    assert sc("l", "x_l", jc + np.random.default_rng(0).normal(0, 20, (200, 3)), "forearm_hand", jc, None)
    assert sc("l", "y_l", wc + np.random.default_rng(1).normal(0, 20, (200, 3)), "forearm_hand", jc, None)          # wrist-only structure
    assert not sc("l", "z_l", far, "upper_limb", jc, None)                                                           # shoulder-level arm structure
    assert not sc("l", "t_l", jc + np.random.default_rng(2).normal(0, 20, (200, 3)), "trunk", jc, None)             # trunk muscle near the elbow in the source: out
    assert R.WRIST_ZONE_MM == 90.0


def test_hook_is_wired_into_the_builder_and_asserts_the_male_context():
    src = (REPO / "scripts" / "zanatomy" / "build_zan_atlas_viewer.py").read_text()
    assert "--q201-refine" in src and "q201_refine" in src and "--q201-dump-after" in src
    from scripts.zanatomy import q201_refine as R
    import inspect
    assert "body_ctx.BODY == \"vhm\"" in inspect.getsource(R.refine_core)
