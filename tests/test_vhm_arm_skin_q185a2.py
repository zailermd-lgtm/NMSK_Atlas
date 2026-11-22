"""Q185a2: his arm skin beyond the CT field of view from his cryosection photographs -- join, registration, sweep rule."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "cryo"))
import vhm_arm_skin_from_cryo_q185a2 as Q  # noqa: E402
from scripts.placement_sweep_q185 import skin_unknown  # noqa: E402


def _ball(n, r=20.0, c=(0.0, 0.0, 0.0), cut=None):
    from skimage.measure import marching_cubes
    g = np.linspace(-30, 30, n); X, Y, Z = np.meshgrid(g, g, g, indexing="ij")
    occ = (X - c[0]) ** 2 + (Y - c[1]) ** 2 + (Z - c[2]) ** 2 <= r * r
    if cut is not None:
        occ &= X >= cut                       # a flat "FOV cap" at x = cut
    v, f, _, _ = marching_cubes(np.pad(occ, 1).astype(float), 0.5)
    v = (v - 1) * (g[1] - g[0]) + g[0]
    return v, Q.oriented_outward(v, f.astype(np.int64))


def test_join_at_wall_is_closed_and_consistent():
    import trimesh
    va, fa = _ball(41, cut=-12.0)            # "CT" skin, cut flat
    vb, fb = _ball(57, c=(0.4, 0.0, 0.0))    # "photo" surface: other sampling, slightly offset, complete
    plane = float(va[:, 0].min()); xw = plane + 6.0
    V, F, arm = Q.split_ct_at_wall(va, fa, xw, plane, ct_keep_ge=True)
    assert len(arm) == 1
    V, F, st = Q.join_at_wall(V, F, vb, fb, xw, ct_keep_ge=True)
    m = trimesh.Trimesh(V, F, process=False)
    assert st["loops_ct"] == st["loops_photo"] == 1 and st["open_edges_ct"] == st["open_edges_photo"] == 0
    assert m.is_watertight and m.is_winding_consistent and m.volume > 0
    assert abs(m.volume - 4 / 3 * np.pi * 20 ** 3) / (4 / 3 * np.pi * 20 ** 3) < 0.05
    assert st["wall_gap_mm_max"] < 2.0


def test_translation_round_trip_and_reliability():
    T = (331.0, -162.5)
    ct = {"radius": (250.0, -10.0, 300), "ulna": (262.0, -30.0, 350)}
    m = {}
    for b, (x, y, a) in ct.items():
        r, c = Q.to_px(x, y, T); m[b] = (float(r), float(c), a)
    X0, Y0 = Q.level_translation(m, ct)
    assert abs(X0 - T[0]) < 1e-6 and abs(Y0 - T[1]) < 1e-6
    assert Q.reliable(m, ct)
    bad = dict(m); bad["ulna"] = (m["ulna"][0] + 6, m["ulna"][1], 350)     # 6 px = 5.9 mm off the CT pair distance
    assert not Q.reliable(bad, ct)
    assert not Q.reliable({"radius": m["radius"]}, ct)                        # one of two bones: not reliable
    assert Q.reliable({"humerus": m["radius"]}, {"humerus": ct["radius"]})    # the only bone in the section


def test_skin_unknown_only_in_open_intervals():
    p = np.array([[-240.0, 300, 0], [-240.0, 500, 0], [250.0, 300, 0], [0.0, 300, 0]])
    planes = (-232.4, 245.6)
    assert skin_unknown(p, (planes, None)).tolist() == [True, True, True, False]          # Q185a: whole cut
    assert skin_unknown(p, (planes, [])).tolist() == [False] * 4                          # Q185a2: rebuilt, nothing open
    op = [{"side": "lo", "y_mm": [450.0, 550.0]}]
    assert skin_unknown(p, (planes, op)).tolist() == [False, True, False, False]
    assert not skin_unknown(p, None).any()


def test_built_skin_report():
    rep = REPO / "data/derived/Q185a2_arm_skin_vhm.json"
    if not rep.exists():
        pytest.skip("Q185a2 report not built")
    r = json.loads(rep.read_text())
    assert r["watertight"] and r["merge"]["watertight"]
    assert r["enclosure_summary"]["bone"]["beyond_inside_new_frac"] >= 0.99
    assert r["seam_step_mm"]["zip_strip_gap_max"] <= 2.0
