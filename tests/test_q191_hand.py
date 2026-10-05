"""Q191: pure parts of scripts/zanatomy/q191_hand.py (synthetic meshes, no CT data needed) + the q191 build output when present."""
import numpy as np
import trimesh

from scripts.zanatomy import q191_hand as H


def _box(a=(10.0, 4.0, 3.0)):
    m = trimesh.creation.icosphere(subdivisions=3)
    return (m.vertices * np.asarray(a)).astype(float), m.faces.astype(np.int64)


def _rot(deg, axis=(0, 0, 1)):
    from scipy.spatial.transform import Rotation as Rot
    return Rot.from_rotvec(np.radians(deg) * np.asarray(axis, float)).as_matrix()


def test_kabsch_recovers_similarity():
    v, _ = _box()
    R = _rot(25, (1, 2, 0.5)); t = np.array([5.0, -3.0, 8.0])
    s, R2, t2 = H.kabsch(v, 1.1 * v @ R.T + t, scale=True)
    assert abs(s - 1.1) < 1e-6 and np.allclose(R2, R, atol=1e-6) and np.allclose(t2, t, atol=1e-5)


def test_inside_depth_sign():
    v, f = _box((10, 10, 10))
    ins = H.Inside(v, f)
    d = ins.depth(np.array([[0, 0, 0.0], [0, 0, 5.0], [0, 0, 20.0]]))
    assert d[0] > 8 and d[1] > 3 and d[2] < -5


def test_fold_stats_is_rotation_free_and_sees_a_fold():
    v, f = _box()
    assert H.fold_stats(v @ _rot(90).T + 3, v, f) == 0.0          # a rigid turn of 90 deg is not a fold
    w = v.copy(); w[v[:, 0] > 0, 0] *= -1.0                         # one half turned inside out
    assert H.fold_stats(w, v, f) > 0.0


def test_hand_map_identity_and_blend():
    a = np.random.default_rng(0).normal(size=(200, 3)) * 5
    b = a + np.array([40.0, 0, 0])
    I = (1.0, np.eye(3), np.zeros(3))
    HM = H.HandMap({"a": a, "b": b}, {"a": I, "b": I})
    x = np.random.default_rng(1).normal(size=(50, 3)) * 20
    assert np.allclose(HM.map(x), x, atol=1e-6)                     # all identity -> identity
    Tb = (1.0, np.eye(3), np.array([0.0, 10.0, 0.0]))
    HM = H.HandMap({"a": a, "b": b}, {"a": I, "b": Tb})
    mid = HM.map(np.array([[20.0, 0, 0]]))[0, 1]
    assert 0.0 < mid < 10.0 and HM.map(a[:1])[0, 1] < 1.0 and HM.map(b[:1])[0, 1] > 8.0   # follows the nearest bone, blends between


def test_field_weight_taper():
    from scipy.spatial import cKDTree
    c, u = np.zeros(3), np.array([0, -1.0, 0])
    near = cKDTree(np.array([[0, 0, 0.0], [0, -30, 0.0]]))
    w = H.field_weight(np.array([[0, 100.0, 0], [0, 40.0, 0], [0, 0, 0], [0, -20.0, 0], [0, -300.0, 0]]), c, u, near)
    assert w[0] == 0 and 0 < w[1] < 1 and w[2] == 1 and w[3] == 1 and w[4] == 0     # 100 mm up the forearm: 0; at the wrist / hand: 1; far from the hand bones: 0


def test_fit_pieces_recovers_a_displaced_piece_without_leaving_bounds():
    v, f = _box()
    her = v @ _rot(8).T + np.array([2.0, 1.0, 0.0])
    pts = H.surf_pts(her, f, 4000)
    T, T0, assigned = H.fit_pieces({"p": {"r": v, "v": v + np.array([5.0, 0, 0]), "f": f}}, pts, False, max_rot=15.0, max_shift=8.0, scale_rng=(0.93, 1.08))
    err0 = np.linalg.norm(H.apply_T(T0["p"], v).mean(0) - her.mean(0))        # centroid error (the ellipsoid is nearly symmetric: vertex errors are slide-ambiguous)
    err1 = np.linalg.norm(H.apply_T(T["p"], v).mean(0) - her.mean(0))
    assert err1 < 0.9 * err0 and 0.93 <= T["p"][0] / T0["p"][0] <= 1.08 + 1e-9 and H.rot_deg(T["p"][1] @ T0["p"][1].T) <= 15.0 + 1e-6


def test_scope_and_ids():
    ids = H.bone_ids("r")
    assert len(ids["carpals"]) == 8 and len(ids["mc"]) == 5 and len(ids["phal"]) == 14
    pend = [{"mesh_id": "adductor_pollicis_r", "cat": "muscle"}, {"mesh_id": "adductor_pollicis_l", "cat": "muscle"}, {"mesh_id": "gluteus_medius_r", "cat": "muscle"},
            {"mesh_id": "zan_skin_palm_r", "cat": "skin"}, {"mesh_id": "zan_capitate_bone_r", "cat": "bone"}, {"mesh_id": "extensor_digitorum_brevis_r", "cat": "muscle"}]
    assert sorted(H.scope(pend, {}, "r")) == ["adductor_pollicis_r", "zan_skin_palm_r"]       # no bones, no foot, no trunk


def test_q191_build_output_if_present():
    """the q191 build keeps the v7 structure set, finite geometry, the Q191 badges, and leaves the trunk / pelvis / shoulder vertices of v7 untouched"""
    from pathlib import Path
    import pytest
    root = Path(__file__).resolve().parents[1]
    after, before = root / "build" / "viewer_zan_female_q191", root / "build" / "viewer_zan_female"
    if not (after / "atlas_viewer_zan_female.html").exists() or not (before / "atlas_viewer_zan_female.html").exists():
        pytest.skip("q191 build not present")
    from scripts.zanatomy import trunk_refit_q186c_audit as A186
    Ma, Mb = A186.load_viewer(after), A186.load_viewer(before)
    assert set(Ma) == set(Mb)
    assert all(np.isfinite(m["v"]).all() for m in Ma.values())
    far = [k for k, m in Mb.items() if m["v"].mean(0)[1] > 250 and k in Ma and len(Ma[k]["v"]) == len(m["v"])]
    assert far and max(float(np.abs(Mb[k]["v"] - Ma[k]["v"]).max()) for k in far if "radius" not in k and "forearm" not in k) < 60.0
    html = (after / "atlas_viewer_zan_female.html").read_text()
    assert "Q191 (hand/wrist refit onto her own CT hand)" in html
