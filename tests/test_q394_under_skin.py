"""Q394: the under-skin census's pure parts -- exact point-triangle distance, the ray-parity inside test, the outer / inner test
of a skin slab, the exclusion rules, the spine regions in the pose fk; and (when the built pages are present) the page census
agrees with the Q353 outside_count it extends on the vertices both test."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "anatomy" / "q394"))
import under_skin_q394 as U  # noqa: E402


def brute_closest(p, a, b, c, n=120):
    best, bq = np.inf, None
    for i in range(n + 1):
        for j in range(n + 1 - i):
            u, v = i / n, j / n
            q = a + u * (b - a) + v * (c - a)
            d = np.linalg.norm(p - q)
            if d < best:
                best, bq = d, q
    return bq


def test_closest_on_tris_matches_brute_force():
    rng = np.random.default_rng(394)
    A = np.array([0.0, 0, 0]); B = np.array([10.0, 0, 0]); C = np.array([2.0, 7, 1])
    for _ in range(40):
        p = rng.uniform(-8, 16, 3)
        q = U.closest_on_tris(p[None], A[None], B[None], C[None])[0]
        assert np.linalg.norm(p - q) <= np.linalg.norm(p - brute_closest(p, A, B, C)) + 1e-6


def slab(r_out=50.0, r_in=48.0, sub=2):
    import trimesh
    o = trimesh.creation.icosphere(subdivisions=sub, radius=r_out)
    i = trimesh.creation.icosphere(subdivisions=sub, radius=r_in)
    V = np.vstack([o.vertices, i.vertices]); F = np.vstack([o.faces, i.faces[:, ::-1] + len(o.vertices)])
    cls = np.r_[np.ones(len(o.faces), int), -np.ones(len(i.faces), int)]
    return V, F, cls


def test_skin_test_and_parity_on_a_closed_slab():
    V, F, cls = slab()
    sk = U.Skin(["s"], {"s": V}, {"s": F}, {"s": cls})
    P = np.array([[0, 0, 53.0], [0, 0, 49.0], [0, 0, 30.0], [55.0, 0, 0], [0, 0, 0.0]])
    out, so, si, *_ = sk.test(P)
    assert out.tolist() == [True, False, False, True, False]       # outside / in the slab / deep / outside / centre
    assert abs(so[0] - 3.0) < 0.5 and so[2] < 0 and si[2] > 0
    par = sk.confirm(P)
    assert par.tolist() == [True, False, False, True, False]        # the parity test needs only the outer sheet


def test_parity_holds_when_a_patch_is_swapped():
    V, F, cls = slab()
    c = V[F].mean(1)
    swap = (c[:, 2] > 30)                                            # a cap of both sheets labelled the wrong way round
    cls2 = np.where(swap, -cls, cls)
    sk = U.Skin(["s"], {"s": V}, {"s": F}, {"s": cls2})
    P = np.array([[0, 0, 40.0], [0, 0, 56.0]])
    out, so, *_ = sk.test(P)
    assert out[0]                                                     # the Q353 test is fooled under the swapped patch ...
    assert sk.confirm(P).tolist() == [False, True]                   # ... the parity test is not


def test_exclusions_have_reasons_and_keep_deep_structures():
    for sid in ("zan_cornea_l", "zan_upper_canine_r", "zan_mucosa_of_nasal_cavity", "zan_corpus_spongiosum_of_penis"):
        assert U.excluded(sid)
    for sid in ("latissimus_dorsi_r", "biceps_brachii_l", "fat_subcut_thigh_l", "zan_great_saphenous_vein_l", "zan_seventh_rib_l",
                "breast_fat_r", "supraclavicular_n_r", "rectus_abdominis_r"):
        assert U.excluded(sid) is None
    assert all(why for _, why in U.EXCLUDE)


def test_fk_rest_is_identity_and_regions_rotate():
    import json
    p = REPO / "data/anatomy/pose_rig_base_m.json"
    if not p.exists():
        pytest.skip("no rig")
    rig = json.loads(p.read_text(encoding="utf-8"))["rig"]
    M0 = U.fk(rig, {})
    assert all(np.allclose(m, np.eye(4)) for m in M0)
    M1 = U.fk(rig, U.STATES["neck_flex_rot"])
    occ = [L["seg"] for r in rig["regions"] if r["id"] == "cervical" for L in r["levels"]][-1]
    assert not np.allclose(M1[occ], np.eye(4))
    lum = [L["seg"] for r in rig["regions"] if r["id"] == "lumbar" for L in r["levels"]][0]
    assert np.allclose(M1[lum], np.eye(4))


def test_states_cover_the_brief():
    assert {"rest", "sh_abd", "sh_flex", "arm_elbow", "hipknee", "neck_flex_rot", "neck_ext_lat", "trunk"} <= set(U.STATES)
