"""Q168: pure-function tests for scripts/transfer/zan_to_vhf_whole_body.py (no build data needed)."""
import numpy as np
import pytest

from scripts.transfer import zan_to_vhf_whole_body as Q


def _rot(axis, deg):
    a = np.asarray(axis, float) / np.linalg.norm(axis)
    K = np.array([[0, -a[2], a[1]], [a[2], 0, -a[0]], [-a[1], a[0], 0]])
    th = np.radians(deg)
    return np.eye(3) + np.sin(th) * K + (1 - np.cos(th)) * K @ K


def test_umeyama_recovers_similarity():
    rng = np.random.default_rng(0)
    P = rng.normal(size=(200, 3)) * 30
    R, s, t = _rot((1, 2, 3), 37), 0.91, np.array([5.0, -12.0, 40.0])
    s2, R2, t2 = Q.umeyama(P, s * P @ R.T + t)
    assert s2 == pytest.approx(s, abs=1e-9)
    assert np.allclose(R2, R, atol=1e-9) and np.allclose(t2, t, atol=1e-7)
    _, R3, _ = Q.umeyama(P, P @ R.T, with_scale=False)
    assert np.linalg.det(R3) == pytest.approx(1.0)


def test_trimmed_icp_recovers_small_motion_and_keeps_fixed_scale():
    rng = np.random.default_rng(1)
    src = rng.normal(size=(1500, 3)) * np.array([40, 15, 8])
    R, t = _rot((0, 0, 1), 6), np.array([3.0, -2.0, 1.0])
    dst = 0.9 * src @ R.T + t
    A0 = np.eye(3) * 0.9
    A, tt = Q.trimmed_icp(src, dst, A0, np.zeros(3), scale=False, corr="sym", trim=1.0)
    assert Q.sim_scale(A) == pytest.approx(0.9, abs=1e-6)
    assert np.abs(Q.apply_sim(A, tt, src) - dst).max() < 0.5


def test_smooth_idw_weights_normalised_tapered_and_continuous():
    D = np.array([[1.0, 5.0, 100.0], [0.0, np.inf, 3.0]])
    W = Q.smooth_idw_weights(D)
    assert np.allclose(W.sum(1), 1.0)
    assert W[0, 2] == 0.0                     # beyond dmin + cutoff: exactly zero
    assert W[1, 1] == 0.0                     # not a candidate
    assert W[0, 0] > W[0, 1] > 0
    # continuity: a bone crossing the cutoff boundary changes the weights only a little
    a = Q.smooth_idw_weights(np.array([[10.0, 10.0 + Q.BLEND_CUTOFF_MM - 1e-3]]))
    b = Q.smooth_idw_weights(np.array([[10.0, 10.0 + Q.BLEND_CUTOFF_MM + 1e-3]]))
    assert np.abs(a - b).max() < 1e-6


def test_sample_surface_on_triangles():
    v = np.array([[0, 0, 0], [10, 0, 0], [0, 10, 0], [0, 0, 10.0]])
    f = np.array([[0, 1, 2], [0, 1, 3]])
    pts = Q.sample_surface(v, f, 500)
    assert len(pts) == 500
    on_z0 = np.isclose(pts[:, 2], 0)
    on_y0 = np.isclose(pts[:, 1], 0)
    assert np.all(on_z0 | on_y0)
    assert np.all(pts.sum(1) <= 10 + 1e-9) and np.all(pts >= -1e-9)


def test_surface_distance_and_edge_stretch():
    rng = np.random.default_rng(2)
    A = rng.normal(size=(300, 3))
    assert Q.surface_distance(A, A)["sym"] == 0.0
    d = Q.surface_distance(A, A + np.array([0, 0, 2.0]))
    assert d["a_to_b"] <= 2.0 + 1e-9
    v = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0.0]])
    f = np.array([[0, 1, 2]])
    assert np.allclose(Q.edge_stretch(v, 3 * v, f), 1.0)     # uniform scale is not stretch
    v2 = v.copy(); v2[1, 0] = 4.0
    r = Q.edge_stretch(v, v2, f)
    assert r.max() / r.min() > 3.5              # one edge 4x, one unchanged


def test_units_pairing_and_groups():
    U = Q.UNITS
    assert len(U["ribs_r"]) == 12 and len(U["thoracic_vertebrae"]) == 12
    assert len(U["phalanges_hand_r"]) == 14 and len(U["phalanges_foot_l"]) == 14
    assert U["cranium"] and "mandible" not in U["cranium"]
    assert Q.unit_group("femur_r") == "lower_r" and Q.unit_group("carpals_l") == "upper_l"
    assert Q.unit_group("metacarpal_3_r") == "upper_r" and Q.unit_group("scapula_l") == "axial"
    assert Q.unit_group("forearm_l_proxy") == "upper_l"
    units = ["femur_r", "humerus_r", "radius_r", "ribs_r", "tibia_l"]
    assert "femur_r" not in Q.allowed_units("upper_r", units)
    assert "humerus_r" not in Q.allowed_units("lower_l", units)
    ax = Q.allowed_units("axial", units)
    assert "radius_r" not in ax and "humerus_r" in ax and "femur_r" in ax
    assert Q.region_of_unit("talus_l") == "foot" and Q.region_of_unit("hyoid") == "head_neck"
    assert Q.region_of_unit("forearm_l_proxy") == "forearm_hand"


def test_chains_are_proximal_to_distal():
    seen = set()
    fitted_directly = {p for zids in Q.UNITS.values() for p in zids if len(zids) == 1} | {
        p for u in ("thoracic_vertebrae",) for p in Q.UNITS[u]} | {
        p for s in "rl" for p in Q.UNITS[f"metatarsals_{s}"]}
    for child, parents, unit in Q.CHAINS:
        assert child in Q.UNITS[unit]
        for p in parents:
            assert p in seen or p in fitted_directly, (child, p)
        seen.add(child)


def test_male_only_ids():
    m = Q.MALE_ONLY_IDS
    for i in ("zan_prostate", "zan_testis_l", "zan_glans_penis", "gonadal_a_r", "zan_ductus_deferens_r"):
        assert i in m
    for keep in ("pudendal_n_l", "zan_urinary_bladder", "zan_superficial_external_pudendal_artery_l",
                 "zan_juxta_intestinal_mesenteric_nodes"):
        assert keep not in m
    assert "none found" in Q.FEMALE_PELVIC_ORGANS["uterus_ovary_tube_vagina"]


def test_spatial_clusters_split_far_pieces():
    rng = np.random.default_rng(3)
    a = rng.normal(size=(400, 3)) * 5
    b = rng.normal(size=(400, 3)) * 5 + np.array([0, -900.0, 0])
    lab, n = Q.spatial_clusters(np.vstack([a, b]))
    assert n == 2 and len(set(lab[:400])) == 1 and lab[0] != lab[-1]
    lab1, n1 = Q.spatial_clusters(a)
    assert n1 == 1


def test_fits_json_roundtrip():
    fits = {"femur_r": {"status": "fitted", "A": np.eye(3) * 0.9, "t": np.array([1.0, 2, 3]), "pieces": ["femur_r"],
                        "piece_fits": {}, "scale": 0.9},
            "radius_l": {"status": "unpaired", "her": False, "zan_pieces": 1}}
    back = Q.fits_from_json(Q.fits_to_json(fits))
    assert np.allclose(back["femur_r"]["A"], fits["femur_r"]["A"]) and back["radius_l"]["status"] == "unpaired"
