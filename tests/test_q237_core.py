"""Q237: pairing core (names -> side / canonical key, lateralised list), the midsagittal plane (reflection, robust fit, fit to a synthetic skeleton) and the asymmetry metrics on synthetic meshes."""
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "anatomy" / "q237")); sys.path.insert(0, str(REPO / "scripts" / "anatomy"))
import core as C  # noqa: E402
import pairing as P  # noqa: E402


def S1(i, id_, side="m", sys_="muscle", name=None, v=None, f=None):
    v = np.zeros((3, 3)) if v is None else v
    f = np.array([[0, 1, 2]]) if f is None else f
    return dict(idx=i, id=id_, name=name or id_, sys=sys_, side=side, v=v, f=f, src="x", rec={})


def box(c, h=1.0):
    c = np.asarray(c, float)
    v = np.array([[x, y, z] for x in (-h, h) for y in (-h, h) for z in (-h, h)], float) + c
    f = np.array([[0, 1, 3], [0, 3, 2], [4, 6, 7], [4, 7, 5], [0, 4, 5], [0, 5, 1], [2, 3, 7], [2, 7, 6], [0, 2, 6], [0, 6, 4], [1, 5, 7], [1, 7, 3]])
    return v, f


def test_side_and_canon_conventions():
    for ident, field, exp in [("biceps_brachii_l", "l", ("l", "biceps_brachii")), ("zan_biceps_brachii_r", "r", ("r", "biceps_brachii")), ("radius_l_zfill", "l", ("l", "radius")),
                              ("thoracic_vertebrae#3", "m", ("m", "thoracic_vertebrae")), ("tibial_n", "l", ("l", "tibial_n")), ("zan_left_main_bronchus", "m", ("l", "main_bronchus")),
                              ("humerus_r_zfill203s", "r", ("r", "humerus")), ("intervertebral_disc_l1_l2", "m", ("m", "intervertebral_disc_l1_l2")), ("zan_vertebra_l1", "m", ("m", "vertebra_l1"))]:
        sd, cn, _ = C.side_and_canon(S1(0, ident, field))
        assert (sd, cn) == exp, ident


def test_twins_group_and_pieces_merge():
    S = [S1(0, "radius_l", "l", "bone"), S1(1, "radius_l_zfill", "l", "bone"), S1(2, "radius_r", "r", "bone"), S1(3, "zan_antebrachial_fascia_l", "l", "fascia"), S1(4, "antebrachial_fascia_r", "r", "fascia")]
    G = C.groups_of(S)
    assert G[("bone", "radius", "l")] == [0, 1] and G[("bone", "radius", "r")] == [2]
    assert G[("fascia", "antebrachial_fascia", "l")] == [3] and G[("fascia", "antebrachial_fascia", "r")] == [4]


@pytest.mark.parametrize("ident,expect", [("liver", True), ("spleen", True), ("zan_left_ventricle", True), ("zan_right_main_bronchus", True), ("zan_left_common_carotid_artery", True), ("gastrocnemius_l", False),
                                          ("digastric_l", False), ("iliohypogastric_n_r", False), ("inferior_epigastric_artery_l", False), ("sigmoid_sinus_l", False), ("brachialis_r", False), ("zan_gastro_omental_vein_l", True)])
def test_lateralised_by_nature(ident, expect):
    assert (C.lateral_reason(S1(0, ident)) is not None) == expect


def test_plane_reflection_and_matrix():
    pl = C.Plane([1, 0.05, -0.02], 7.0)
    p = np.array([[30.0, 10, 5], [-20, 4, 0]])
    q = pl.reflect(p)
    assert np.allclose(pl.reflect(q), p) and np.allclose(pl.signed(q), -pl.signed(p))
    M = pl.matrix()
    qq = (M[:3, :3] @ p.T).T + M[:3, 3]
    assert np.allclose(qq, q) and np.isclose(np.linalg.det(M[:3, :3]), -1)
    v, f = box([20, 0, 0])
    vm, fm = pl.reflect_mesh(v, f)
    assert np.isclose(C.signed_volume(vm, fm), C.signed_volume(v, f))


def test_robust_plane_recovers_a_tilted_plane_and_ignores_a_posed_limb():
    rng = np.random.default_rng(3)
    n = np.array([0.998, -0.04, 0.03]); n /= np.linalg.norm(n); d = 12.0
    pl = C.Plane(n, d)
    R = rng.normal(size=(40, 3)) * [60, 200, 60] + [90, 300, 0]
    R = R + (d - R @ n)[:, None] * 0 + 0                      # right landmarks
    L = pl.reflect(R) + rng.normal(size=(40, 3)) * 1.0
    L[0] += [0, 0, 60]                                            # one badly posed pair
    est, keep, res, ang = C.robust_plane(np.stack([R, L], 1))
    assert est.tilt_deg()["total_deg"] == pytest.approx(pl.tilt_deg()["total_deg"], abs=0.8)
    assert abs(est.d - d) < 2.0 and not keep[0]


def test_midsagittal_fit_on_a_synthetic_skeleton():
    """vertebrae on a leaning line + paired ribs/hip bones: the fitted plane leans like the spine, residual small"""
    pl = C.Plane([0.9990, -0.03, 0.02], -6.0)
    S = []
    for i in range(12):
        c = np.array([0.0, 100.0 + 40 * i, -20.0]); c[0] = (pl.d - pl.n[1] * c[1] - pl.n[2] * c[2]) / pl.n[0]
        S.append(S1(len(S), f"thoracic_vertebrae#{i + 1}", "m", "bone", v=box(c, 12)[0], f=box(c, 12)[1]))
    for i in range(10):
        c = np.array([90.0, 150.0 + 30 * i, 10.0 * (i % 3)])
        v, f = box(c, 8); vm, fm = pl.reflect_mesh(v, f)
        S.append(S1(len(S), f"rib_{i}_r", "r", "bone", v=v, f=f)); S.append(S1(len(S), f"rib_{i}_l", "l", "bone", v=vm, f=fm))
    C.groups_of(S)
    est, q = C.fit_midsagittal(S)
    assert est.tilt_deg()["roll_deg"] == pytest.approx(pl.tilt_deg()["roll_deg"], abs=0.7)
    assert abs(float(est.signed(np.array([pl.d / pl.n[0], 0, 0])))) < 3.0
    assert q["refl_median_mm"] < 3.5


def test_pair_metrics_on_mirrored_and_scaled_meshes():
    from multiprocessing import Pool  # noqa: F401
    pl = C.Plane([1, 0, 0], 0.0)
    vr, fr = box([40, 5, 3], 10.0)
    vl, fl = box([-40, 5, 3], 10.0)                         # exact mirror
    vl2, fl2 = box([-43, 5, 3], 12.0)                       # 20 % larger linear size, shifted
    S = [S1(0, "m_r", "r", "muscle", v=vr, f=fr), S1(1, "m_l", "l", "muscle", v=vl, f=fl), S1(2, "n_r", "r", "muscle", v=vr, f=fr), S1(3, "n_l", "l", "muscle", v=vl2, f=fl2)]
    P.init_worker(S, pl)
    a = P.pair_metrics(([0], [1]))
    assert a["ratio_r_over_l"] == pytest.approx(1.0, abs=0.02) and a["iou_mirror"] > 0.9 and a["centroid_offset_mm"] < 1.0 and a["msd_mm"] < 1.5
    b = P.pair_metrics(([2], [3]))
    assert b["ratio_r_over_l"] == pytest.approx((10 / 12) ** 3, abs=0.04) and b["centroid_offset_mm"] == pytest.approx(3.0, abs=0.8)
    assert P.flags_of(a, "muscle") == [] and any("ratio" in x for x in P.flags_of(b, "muscle"))
    assert P.tier_of(b) in ("flag", "major")


def test_classification_of_a_small_model():
    pl = C.Plane([1, 0, 0], 0.0)
    S = []
    def add(i, ident, side, sys_, c, h=6.0):
        v, f = box(c, h); S.append(S1(len(S), ident, side, sys_, v=v, f=f))
    add(0, "biceps_r", "r", "muscle", [50, 0, 0]); add(1, "biceps_l", "l", "muscle", [-50, 0, 0])              # paired
    add(2, "sternum", "m", "bone", [0, 0, 0], 20.0)                                                            # midline
    add(3, "liver", "m", "organ", [70, 0, 0]); add(4, "spleen", "m", "organ", [-70, 0, 0])                    # lateralised
    add(5, "triceps_r", "r", "muscle", [50, 30, 0])                                                            # missing left
    add(6, "zan_lung_l", "l", "viscera", [-40, 40, 0]); add(7, "zan_lung_r", "r", "viscera", [40, 40, 0])     # paired organ, sides differ by design
    C.groups_of(S)
    units, _ = P.classify(S, pl)
    got = {u["canon"]: (u["cls"], u.get("kind")) for u in units}
    assert got["biceps"][0] == "paired" and got["sternum"][0] == "midline" and got["liver"][0] == "lateralised" and got["spleen"][0] == "lateralised"
    assert got["triceps"] == ("unmatched", "missing_side") and got["lung"][0] == "lateralised"
