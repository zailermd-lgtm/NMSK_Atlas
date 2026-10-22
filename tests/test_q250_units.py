"""Q250 units: similarity fit, coherent point drift, thin-plate field, limb segment map, bone-anchored warp guards (toy meshes), pelvis registration helpers."""
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "anatomy"))

from scripts.anatomy.q250 import lib as L  # noqa: E402
from scripts.anatomy.q250 import skel_target as ST  # noqa: E402
from scripts.anatomy.q250 import warp as W  # noqa: E402
from scripts.anatomy.q250 import pelvis_reg as PR  # noqa: E402

trimesh = pytest.importorskip("trimesh")


def _rot(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1.0]])


def test_umeyama_recovers_similarity():
    rng = np.random.default_rng(0)
    A = rng.normal(size=(200, 3)) * 30
    R = _rot(0.4); t = np.array([5.0, -3.0, 9.0])
    B = 1.3 * A @ R.T + t
    s, R2, t2 = L.umeyama(A, B)
    assert abs(s - 1.3) < 1e-9 and np.allclose(R2, R) and np.allclose(t2, t)


def test_icp_with_fixed_scale_keeps_the_scale():
    rng = np.random.default_rng(1)
    A = rng.normal(size=(400, 3)) * 20
    B = 0.9 * A @ _rot(0.1).T + np.array([2.0, 1.0, 0.0])
    s, R, t, d = L.icp_sim(A, B, iters=30, trim=1.0, scale=False, init=(0.9, np.eye(3), np.zeros(3)))
    assert s == 0.9 and np.median(d) < 1.5


def test_cpd_nonrigid_deforms_a_shape_onto_a_bent_copy():
    rng = np.random.default_rng(2)
    X = rng.uniform(-30, 30, size=(500, 3))
    Y = X.copy(); Y[:, 0] += 6.0 * np.sin(X[:, 1] / 20.0)            # smooth bend
    W_, beta = L.cpd_nonrigid(X, Y, beta=15.0, lam=1.0, iters=40, w=0.02)
    T = L.cpd_apply(X, W_, beta, X)
    assert np.linalg.norm(T - Y, axis=1).mean() < 1.5 < np.linalg.norm(X - Y, axis=1).mean()


def test_tps_field_is_exact_at_its_control_points_without_smoothing():
    rng = np.random.default_rng(3)
    P = rng.uniform(-50, 50, size=(60, 3)); U = rng.normal(size=(60, 3)) * 3
    f = L.TPS(P, U, smoothing=0.0)
    assert np.abs(f(P) - U).max() < 1e-6


def test_limb_segment_map_covers_the_limb_bones_and_leaves_the_axial_skeleton():
    assert ST.seg_of("femur_l") == ("leg", "l", "thigh") and ST.seg_of("patella_r") == ("leg", "r", "thigh")
    assert ST.seg_of("tibia_r") == ("leg", "r", "shank") and ST.seg_of("fibula_l") == ("leg", "l", "shank")
    assert ST.seg_of("calcaneus_l")[2] == "foot" and ST.seg_of("zan_first_metatarsal_bone_r")[2] == "foot"
    assert ST.seg_of("zan_proximal_phalanx_of_first_finger_of_foot_l")[2] == "foot"
    assert ST.seg_of("humerus_r") == ("arm", "r", "upper") and ST.seg_of("radius_l") == ("arm", "l", "fore")
    assert ST.seg_of("zan_scaphoid_bone_l") == ("arm", "l", "hand") and ST.seg_of("zan_second_metacarpal_bone_r")[2] == "hand"
    assert ST.seg_of("zan_distal_phalanx_of_third_finger_of_hand_r")[2] == "hand"
    for axial in ("sacrum", "sternum", "frontal", "clavicle_l", "scapula_r", "hip_bone_l", "zan_vertebra_l1", "zan_seventh_rib_l", "mandible"):
        assert ST.seg_of(axial) is None, axial


def _page(bone_v, soft_v):
    cube = trimesh.creation.box(extents=(10, 10, 10))
    b = trimesh.Trimesh(cube.vertices + bone_v, cube.faces, process=False)
    s = trimesh.creation.icosphere(subdivisions=2, radius=4.0)
    s = trimesh.Trimesh(s.vertices + soft_v, s.faces, process=False)
    sk = trimesh.creation.icosphere(subdivisions=2, radius=60.0)
    return {"bone": dict(m=dict(sys="bone", id="bone"), v=np.asarray(b.vertices), f=np.asarray(b.faces)),
            "muscle": dict(m=dict(sys="muscle", id="muscle"), v=np.asarray(s.vertices), f=np.asarray(s.faces)),
            "skin": dict(m=dict(sys="skin", id="skin"), v=np.asarray(sk.vertices), f=np.asarray(sk.faces))}


def test_warp_keeps_attachments_on_the_moved_bone_and_reports_guards():
    # a muscle touching the bone's +x face; the bone moves 12 mm along +y and is scaled by 1.1 about its centre: the muscle vertices within 1 mm of the bone must stay within 1 mm of it
    Z = _page(np.zeros(3), np.array([9.0, 0, 0]))
    bv = Z["bone"]["v"]
    tgt = {"bone": bv * 1.1 + np.array([0, 12.0, 0])}
    A = W.apply(Z, tgt, verbose=False)
    rep = A["report"]
    assert rep["attachment_distance_after_mm"]["max"] <= 1.0 + 1e-6 and rep["attachment_distance_after_mm"]["fraction_le_1mm"] == 1.0
    assert A["v"]["bone"] is tgt["bone"] or np.allclose(A["v"]["bone"], tgt["bone"])
    mv = rep["structures"]["muscle"]
    assert 5 < mv["mean_move_mm"] < 20 and mv["flipped_fraction"] < 0.05


def test_warp_exempt_structures_do_not_move():
    Z = _page(np.zeros(3), np.array([9.0, 0, 0]))
    tgt = {"bone": Z["bone"]["v"] + np.array([0, 20.0, 0])}
    A = W.apply(Z, tgt, verbose=False, exempt={"muscle"})
    assert np.allclose(A["v"]["muscle"], Z["muscle"]["v"]) or np.abs(A["v"]["muscle"] - Z["muscle"]["v"]).max() < 1.0   # only a guard push (0.4 mm) may touch it


def test_symphysis_closing_sets_the_gap_to_the_target():
    l = np.c_[np.linspace(-60, -8, 40), np.zeros(40), np.zeros(40)] + np.array([0, 0, 0.0])
    r = np.c_[np.linspace(8, 60, 40), np.zeros(40), np.zeros(40)]
    out, rep = PR.close_symphysis({"hip_bone_l": l, "hip_bone_r": r}, 2.0)
    assert rep["gap_before_mm"] == pytest.approx(16.0, abs=0.01) and rep["gap_after_mm"] == pytest.approx(2.0, abs=0.3)
    assert out["hip_bone_l"][:, 0].max() < out["hip_bone_r"][:, 0].min()


def test_mirror_and_tri_stats():
    p = np.array([[1.0, 2, 3]])
    assert np.allclose(L.mirror(p), [[-1.0, 2, 3]])
    v = np.array([[0, 0, 0], [1.0, 0, 0], [0, 1.0, 0]]); f = np.array([[0, 1, 2]])
    st = W.tri_stats(v, v * 2.0, f)
    assert st["area_ratio"] == pytest.approx(4.0) and st["flipped_fraction"] == 0.0
    st2 = W.tri_stats(v, v * np.array([1, -1, 1]), f)
    assert st2["flipped_fraction"] == 1.0


def test_symmetric_warp_gives_a_mirror_symmetric_field():
    """left / right bones that are mirror images moved by mirror-image targets: the soft-tissue field must be exactly mirror symmetric (control set and bone samples are mirror-closed)"""
    cube = trimesh.creation.box(extents=(10, 20, 10))
    def page():
        Z = {}
        for sd, sx in (("l", -30.0), ("r", 30.0)):
            Z[f"b_{sd}"] = dict(m=dict(sys="bone", id=f"b_{sd}"), v=cube.vertices + np.array([sx, 0, 0]), f=np.asarray(cube.faces))
        s = trimesh.creation.icosphere(subdivisions=2, radius=5.0)
        Z["soft"] = dict(m=dict(sys="muscle", id="soft"), v=np.asarray(s.vertices) + np.array([0, 15, 0]), f=np.asarray(s.faces))
        sk = trimesh.creation.icosphere(subdivisions=2, radius=90.0)
        Z["skin"] = dict(m=dict(sys="skin", id="skin"), v=np.asarray(sk.vertices), f=np.asarray(sk.faces))
        return Z
    Z = page()
    tgt = {"b_l": Z["b_l"]["v"] * 1.05 + np.array([-8.0, 6.0, 2.0]), "b_r": Z["b_r"]["v"] * 1.05 + np.array([8.0, 6.0, 2.0])}
    A = W.apply(Z, tgt, verbose=False, symmetric=True)
    V = np.array([[12.0, 18.0, 3.0], [-4.0, -9.0, 7.0], [25.0, 5.0, -6.0]])
    f = W.carry(V, A["control"], A["samples"]); g = W.carry(L.mirror(V), A["control"], A["samples"])
    assert np.abs(L.mirror(f) - g).max() < 1e-6
    assert np.abs(A["v"]["soft"][:, 1].mean() - Z["soft"]["v"][:, 1].mean()) > 3          # it did move
