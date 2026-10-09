"""Q190: pure parts of scripts/zanatomy/q190_refine.py + q190_metrics.py (synthetic meshes, no CT data needed)."""
import numpy as np
import trimesh

from scripts.zanatomy import q190_metrics as Mx
from scripts.zanatomy import q190_refine as Q


def _ellipsoid(a=(30.0, 12.0, 8.0), sub=3):
    m = trimesh.creation.icosphere(subdivisions=sub)
    v = m.vertices * np.asarray(a)
    return v.astype(float), m.faces.astype(np.int64)


def _rot(deg, axis=(0, 0, 1)):
    from scipy.spatial.transform import Rotation as Rot
    return Rot.from_rotvec(np.radians(deg) * np.asarray(axis, float)).as_matrix()


def test_stretch_identity_and_uniform_scale_are_not_distortion():
    v, f = _ellipsoid()
    s = Mx.stretch_stats(v * Mx.BODY_SCALE, v, f)
    assert abs(s["scale_edge_med"] - 1.0) < 1e-6 and s["flipped"] == 0 and s["area_frac_gt1.5"] == 0
    s2 = Mx.stretch_stats(v * 1.4, v, f)               # a uniform 1.4x is a scale, not a distortion
    assert s2["area_frac_gt1.5"] == 0 and s2["area_frac_lt0.67"] == 0
    w = v.copy(); w[v[:, 0] > 0, 0] *= 3.0                # one half stretched threefold along x IS distortion
    s3 = Mx.stretch_stats(w, v, f)
    assert s3["edge_p95"] > 1.3 and Mx.distortion_score(s3) > 5


def test_rotation_limit():
    R0 = _rot(10)
    R = _rot(70)
    out = Q._limit_rotation(R, R0, 25.0)
    ang = np.degrees(np.arccos(np.clip((np.trace(out @ R0.T) - 1) / 2, -1, 1)))
    assert abs(ang - 25.0) < 1e-6


def test_volume_guard_bounds():
    v, f = _ellipsoid()
    big, r = Q.volume_guard(v * 1.6, v, f)               # 1.6^3 = 4.1 x the source volume x BODY_SCALE^3 -> pulled back to 1.5
    assert abs(Q.volume(big, f) / (Q.volume(v, f) * Mx.BODY_SCALE ** 3) - Q.VOLUME_RATIO[1]) < 1e-6
    small, r = Q.volume_guard(v * 0.5, v, f)
    assert abs(Q.volume(small, f) / (Q.volume(v, f) * Mx.BODY_SCALE ** 3) - Q.VOLUME_RATIO[0]) < 1e-6


def test_refine_group_moves_a_sheared_muscle_onto_her_label_without_distortion():
    raw, f = _ellipsoid()
    t_true = np.array([9.0, -6.0, 5.0])
    her_v = raw @ _rot(7).T + t_true                       # her label: the same shape, moved/turned (she is the reference)
    ref = Q.Ref(her_v, f, n=6000)
    shear = np.eye(3); shear[0, 1] = 0.25                   # v6: the global field sheared the muscle and left it 12 mm off
    v6 = raw @ shear.T + t_true + np.array([-10.0, 6.0, -4.0])
    m = {"id": "x", "v": v6, "r": raw, "f": f}
    X, rep, _ = Q.refine_group([m], ref)
    assert rep["her_label_chamfer_before_mm"][2] > 4.0
    assert rep["after_mm"][2] < 1.5
    st = Mx.stretch_stats(X, raw, f)
    assert st["flipped"] == 0 and st["area_frac_gt1.5"] + st["area_frac_lt0.67"] < 0.02       # the Z shape is kept, v6's shear is gone
    assert rep["resid_max_mm"] <= Q.MAX_RESID_MM


def test_refine_group_partial_reference_keeps_length():
    raw, f = _ellipsoid((90.0, 10.0, 10.0), sub=4)
    keep = np.abs(raw[:, 0]) < 8                          # her label covers only the middle third of the Z muscle
    fm = np.all(keep[f], axis=1)
    her_v = raw + np.array([0.0, 7.0, 0.0])
    ref = Q.Ref(her_v, f[fm], n=4000)
    v6 = raw.copy()
    X, rep, _ = Q.refine_group([{"id": "y", "v": v6, "r": raw, "f": f}], ref)
    assert rep["partial_reference"] is True
    assert (X[:, 0].max() - X[:, 0].min()) > 0.9 * (raw[:, 0].max() - raw[:, 0].min())      # not squashed onto the fragment
    assert 3.0 < np.median(X[:, 1] - raw[:, 1]) < 10.0


def test_skin_envelope_clamp_moves_a_point_inside():
    sph = trimesh.creation.icosphere(subdivisions=3, radius=100.0)
    d = {"id": "zan_skin_test", "v": np.asarray(sph.vertices), "f": np.asarray(sph.faces), "cat": "skin"}
    axis = lambda y: (np.zeros_like(y), np.zeros_like(y))
    env = Q.SkinEnvelope([d], axis)
    nerve = {"id": "n", "v": np.array([[0.0, 0.0, 104.0], [0.0, 0.0, 50.0]]), "f": np.zeros((0, 3), int), "cat": "nerve"}
    out = Q.envelope_clamp({"n": nerve}, ["n"], env, axis)
    v = out["n"][0]
    assert np.linalg.norm(v[0]) < 100.0 and np.allclose(v[1], nerve["v"][1])


def test_q190_build_output_if_present():
    """the committed q190 build keeps the v6 structure set, finite geometry, its badges, and the v6 front skin"""
    from pathlib import Path
    import pytest
    root = Path(__file__).resolve().parents[1]
    after, before = root / "build" / "viewer_zan_female_q190", root / "build" / "viewer_zan_female"
    if not (after / "atlas_viewer_zan_female.html").exists() or not (before / "atlas_viewer_zan_female.html").exists():
        pytest.skip("q190 build not present")
    from scripts.zanatomy import trunk_refit_q186c_audit as A186
    Ma, Mb = A186.load_viewer(after), A186.load_viewer(before)
    assert set(Ma) <= set(Mb) and set(Mb) - set(Ma) <= {"zan_skin_perineal_closure"}  # Q202 added the closure patch to the installed page
    assert all(np.isfinite(m["v"]).all() for m in Ma.values())
    moved_front = 0
    for k, m in Mb.items():
        if m["sys"] == "skin" and "chest" not in k and "pectoral" in k and len(m["v"]) == len(Ma[k]["v"]):
            moved_front = max(moved_front, float(np.abs(m["v"] - Ma[k]["v"]).max()))
    assert moved_front < 3.0               # the anterior chest skin of v6 is kept (quantisation + seam re-weld only)
    html = (after / "atlas_viewer_zan_female.html").read_text()
    assert "Q190: refined onto her own CT-derived gluteus maximus" in html
