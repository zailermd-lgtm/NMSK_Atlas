"""Q202: perineal surface closure (minimal-surface hole fill), the loop extraction, page patching (byte-identical scope), the contact metric; plus the committed reports and the built pages when present."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.zanatomy import q202_closure as CL  # noqa: E402
from scripts.zanatomy import q202_contact as K  # noqa: E402
from scripts.zanatomy import q202_pages as P  # noqa: E402
from scripts.zanatomy import q198_core as C  # noqa: E402


def ring(n=24, a=40.0, b=25.0):
    t = np.linspace(0, 2 * np.pi, n, endpoint=False)
    # a saddle-ish closed loop: ellipse with a wave in z
    return np.stack([a * np.cos(t), 5.0 * np.sin(2 * t), b * np.sin(t)], 1)


def test_slab_is_closed_manifold_and_welded_to_loop():
    L1 = ring()
    L2 = L1 + np.array([0.0, 2.0, 0.0])
    r = CL.build_slab(L1, L2, n_ext_hint=(0, 1, 0), target_edge=5.0)
    u, c = C.edge_counts(r["f"])
    assert (c == 2).all()                                         # closed 2-manifold
    assert CL.tri_area(r["v"], r["f"]).min() > 1e-3               # no degenerate triangle
    X = r["outer"]
    # every loop vertex is a vertex of the outer sheet (shared position = welded seam)
    for p in L1:
        assert np.linalg.norm(X - p, axis=1).min() < 1e-6
    assert r["info"]["thickness_mm"]["min"] >= 0.29


def test_minimal_surface_is_flat_for_a_planar_loop():
    t = np.linspace(0, 2 * np.pi, 20, endpoint=False)
    L = np.stack([30 * np.cos(t), 0 * t, 20 * np.sin(t)], 1)
    r = CL.build_slab(L, L + [0, 3.0, 0], n_ext_hint=(0, -1, 0), target_edge=5.0)
    assert np.abs(r["outer"][:, 1]).max() < 1e-6                  # a planar loop spans a plane
    assert r["info"]["max_displacement_from_harmonic_mm"] < 1.0       # in-plane drift of the cotangent relaxation only


def test_minimal_surface_area_below_ruled_start():
    L1 = ring()
    r = CL.build_slab(L1, L1 + [0, 2.0, 0], n_ext_hint=(0, 1, 0), target_edge=5.0)
    v0, f0, rg, _, _ = CL.triangulate_loop(L1, 5.0)
    X0, _, _ = CL.minimal_surface(v0.copy(), f0, rg, iters=0)     # harmonic start only
    assert CL.tri_area(r["outer"], r["f_out"]).sum() <= CL.tri_area(X0, f0).sum() + 1e-6


def test_contacts_and_gaps_detect_a_torn_seam():
    # two quads sharing an edge in the source; the second one moves away by 3 mm in the fitted state
    v = np.array([[0, 0, 0], [10, 0, 0], [10, 10, 0], [0, 10, 0], [10, 0, 0.], [20, 0, 0], [20, 10, 0], [10, 10, 0.]], float)
    f1 = np.array([[0, 1, 2], [0, 2, 3]]); f2 = np.array([[0, 1, 2], [0, 2, 3]])
    raw = {"a": {"v": v[:4], "f": f1}, "b": {"v": v[4:], "f": f2}}
    ids = ["a", "b"]
    cons = K.contacts(raw, ids)
    assert len(cons) >= 4
    by = {"a": {"v": v[:4].copy(), "f": f1}, "b": {"v": v[4:] + [3.0, 0, 0], "f": f2}}
    g = K.gaps(by, ids, cons)
    assert g.max() == pytest.approx(3.0, abs=0.2)
    by0 = {"a": {"v": v[:4].copy(), "f": f1}, "b": {"v": v[4:].copy(), "f": f2}}
    assert K.gaps(by0, ids, cons).max() < 1e-9


def test_save_page_roundtrip_is_byte_identical(tmp_path):
    d = REPO / "build/q197/viewer_base_female"
    if not d.exists():
        pytest.skip("page not built here")
    man, blob = P.load_page(d, "atlas_viewer_base_female")
    P.save_page(tmp_path, "atlas_viewer_base_female", man, blob)
    assert (tmp_path / "atlas_viewer_base_female.html").read_bytes() == (d / "atlas_viewer_base_female.html").read_bytes()
    for g in d.glob("atlas_viewer_base_female_geo_*.txt"):
        assert (tmp_path / g.name).read_bytes() == g.read_bytes()


def test_loop_spec_is_closed_ring():
    f = REPO / "data" / "derived" / "Q202_perineal_loop.json"
    if not f.exists():
        pytest.skip("loop not extracted")
    d = json.loads(f.read_text())
    L = np.array([n["pos"] for n in d["loop"]])
    assert len(L) == 36
    seg = np.linalg.norm(np.diff(np.vstack([L, L[:1]]), axis=0), axis=1)
    assert 380 < seg.sum() < 440 and seg.max() < 30
    assert all(n["partner_pos"] is not None for n in d["loop"])
    # the rim offset of the Z skin slabs is 3.0 mm
    off = np.linalg.norm(np.array([n["partner_pos"] for n in d["loop"]]) - L, axis=1)
    assert 2.0 < off.mean() < 3.2


@pytest.mark.parametrize("key,old,new,stem", [
    ("base_f", "build/q197/viewer_base_female", "build/q202/viewer_base_female", "atlas_viewer_base_female"),
    ("fit_f", "build/q199/viewer_zan_female", "build/q202/viewer_zan_female", "atlas_viewer_zan_female"),
    ("fit_m", "build/q201/viewer_zan_vhm", "build/q202/viewer_zan_vhm", "atlas_viewer_zan_male_fitted"),
])
def test_built_page_scope_and_closure(key, old, new, stem):
    if not (REPO / new).exists() or not (REPO / old).exists():
        pytest.skip("pages not built here")
    m0, b0 = P.load_page(REPO / old, stem)
    m1, b1 = P.load_page(REPO / new, stem)
    e0 = {m["id"]: m for m in m0["meshes"]}
    changed = []
    for m in m1["meshes"]:
        o = e0.get(m["id"])
        if o is None:
            assert m["id"] == "zan_skin_perineal_closure"
            continue
        same = b1[m["vo"]: m["vo"] + m["vc"] * 6] == b0[o["vo"]: o["vo"] + o["vc"] * 6] and b1[m["io"]: m["io"] + m["ic"] * 6] == b0[o["io"]: o["io"] + o["ic"] * 6]
        if not same:
            changed.append(m["id"])
    assert all(i.startswith("zan_skin_") for i in changed)                   # nothing but skin differs
    assert len(m1["meshes"]) == len(m0["meshes"]) + (0 if key == "fit_m" else 1)
    if key != "fit_m":
        ent = [m for m in m1["meshes"] if m["id"] == "zan_skin_perineal_closure"][0]
        assert "NOT ANATOMY" in ent["rec"]["procedural_badge"] and "No vulva" in ent["rec"]["procedural_badge"]
        assert m1["totals"]["meshes"] == m0["totals"]["meshes"] + 1
        v, f = P.decode_one(ent, b1)
        u, c = C.edge_counts(f)
        assert (c == 2).all()


def test_committed_after_metrics_better_than_before():
    for p in ("fit_f", "fit_m", "base_f"):
        fb, fa = (REPO / "data" / "derived" / f"Q202_metrics_{w}_{p}.json" for w in ("before", "after"))
        if not (fb.exists() and fa.exists()):
            pytest.skip("metrics not committed")
        b, a = json.loads(fb.read_text()), json.loads(fa.read_text())
        assert a["seams"]["steps_gt_3mm"] <= b["seams"]["steps_gt_3mm"]
        assert a["seams"]["surface_gap_max_mm"] <= b["seams"]["surface_gap_max_mm"] + 1e-6
        for k in ("pelvis_floor", "pelvis_centre"):
            if p != "fit_m":
                assert a["escape"][k]["escape_fraction"] < b["escape"][k]["escape_fraction"]
