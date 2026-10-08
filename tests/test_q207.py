"""Q207: skin of the two Z-fitted pages -- synthetic tests of the clearing (wrap), the triangle intersection check, the seam solve, the overlay re-seating and the urogenital refit helpers, and
(when the Q207 pages / reports are built) the page-level guards: scope = the listed skin patches only, structures of the wrist / hand inside the skin, urogenital volume near the Z source and no
overlap across the midline, envelope sealed, every changed card carries its before -> after numbers, female clinical files unchanged (clinical_risk.json absent)."""
import json
import re
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.zanatomy import q207_geom as G  # noqa: E402
from scripts.zanatomy import q207_nails as N  # noqa: E402
from scripts.zanatomy import q207_uro as U  # noqa: E402
from scripts.zanatomy import q207_weld as WD  # noqa: E402

PAGES = {"male": (REPO / "build" / "q207" / "viewer_zan_vhm", "atlas_viewer_zan_male_fitted", REPO / "build" / "q206" / "viewer_zan_vhm"),
         "female": (REPO / "build" / "q207" / "viewer_zan_female", "atlas_viewer_zan_female", REPO / "build" / "q206" / "viewer_zan_female")}


def grid_sheet(n=7, size=30.0, z=0.0):
    xs = np.linspace(0, size, n)
    v = np.array([[x, y, z] for y in xs for x in xs])
    f = []
    for j in range(n - 1):
        for i in range(n - 1):
            a = j * n + i
            f += [[a, a + 1, a + n], [a + 1, a + n + 1, a + n]]
    return v, np.array(f)


def closed_slab(n=7, size=30.0, t=3.0):
    v, f = grid_sheet(n, size, 0.0)
    v2 = v.copy(); v2[:, 2] -= t
    m = len(v)
    f2 = f[:, ::-1] + m
    # rim wall
    rim = []
    idx = np.arange(n * n).reshape(n, n)
    ring = list(idx[0, :]) + list(idx[1:, -1]) + list(idx[-1, -2::-1]) + list(idx[-2:0:-1, 0])
    for a, b in zip(ring, ring[1:] + ring[:1]):
        rim += [[a, b, b + m], [a, b + m, a + m]]
    return np.vstack([v, v2]), np.vstack([f, f2, np.array(rim)])


# ------------------------------------------------------------------------------------------------ geometry checks
def test_intersection_check_finds_crossing_triangles_and_ignores_shared_vertices():
    v = np.array([[0, 0, 0], [10, 0, 0], [0, 10, 0], [2, 2, -3], [2, 2, 3], [8, 2, 0.5], [0, 0, 0.0]], float)
    f = np.array([[0, 1, 2], [3, 4, 5]])
    p = G.intersecting_pairs(v, f, np.array([0, 1]))
    assert len(p) == 1
    f2 = np.array([[0, 1, 2], [0, 1, 6]])                   # share vertices 0 and 1 (a hinge): not an intersection
    assert len(G.intersecting_pairs(v, f2, np.array([0, 0]))) == 0


def test_slab_thickness_and_edge_ratio():
    v, f = closed_slab(7, 30.0, 3.0)
    t = G.slab_thickness(v, f)
    assert abs(np.nanmedian(t) - 3.0) < 0.2
    er = G.edge_ratio(v * 1.2, f, v)
    assert abs(np.median(er) - 1.2) < 1e-6


def test_pair_depth_grows_with_penetration():
    v = np.array([[0, 0, 0], [10, 0, 0], [0, 10, 0], [2, 2, -1], [2, 2, 5], [8, 2, 2]], float)
    f = np.array([[0, 1, 2], [3, 4, 5]])
    p = G.intersecting_pairs(v, f, np.array([0, 1]))
    d1 = G.pair_depth(v, f, p)[0]
    v2 = v.copy(); v2[3, 2] = -4
    d2 = G.pair_depth(v2, f, G.intersecting_pairs(v2, f, np.array([0, 1])))[0]
    assert d2 > d1 > 0


# ------------------------------------------------------------------------------------------------ seam solve
def test_least_squares_weld_closes_a_gap_and_leaves_the_far_end_alone():
    va, fa = grid_sheet(9, 40.0, 0.0)
    vb, fb = grid_sheet(9, 40.0, 4.0)                       # 4 mm above
    V = {"a": va, "b": vb}
    faces = {"a": fa, "b": fb}
    ids = ["a", "b"]
    # constraints: the first row of a (y = 0) with the first row of b
    cons = [(0, i, [(1, i, 1.0)]) for i in range(9)]
    new = WD.solve(V, faces, ids, cons, {"a", "b"}, gate_gap=0.5, w_pull=1.0, w_hold=1.0, lam_s=2.0)
    gap = np.linalg.norm(new["a"][:9] - new["b"][:9], axis=1)
    assert gap.max() < 1.0 and gap.max() < 0.3 * 4.0
    far = np.linalg.norm(new["a"][-9:] - va[-9:], axis=1).max() + np.linalg.norm(new["b"][-9:] - vb[-9:], axis=1).max()
    assert far < 2 * 2.0 + 0.5         # at most the half-way pull at the far end, spread by the smoothness


# ------------------------------------------------------------------------------------------------ overlay re-seating
def test_overlay_follows_its_sheet_and_keeps_its_offset():
    base_v, base_f = grid_sheet(9, 40.0, 0.0)
    over = np.array([[10.0, 10.0, 0.2], [20.0, 12.0, 0.3], [30.0, 25.0, 0.2]])
    cur = base_v.copy(); cur[:, 2] += 5.0 + 0.05 * cur[:, 0]       # the sheet is lifted and tilted
    P = N.transfer(over, base_v, base_f, cur)
    sheet_z = 5.0 + 0.05 * P[:, 0]
    assert np.allclose(P[:, 2] - sheet_z, over[:, 2], atol=0.2)
    assert np.allclose(P[:, :2], over[:, :2], atol=0.5)


def test_degenerate_share_counts_collapsed_edges_only_where_the_source_has_length():
    v0, f = grid_sheet(5, 20.0, 0.0)
    v1 = v0.copy(); v1[1] = v1[0]
    assert N.degenerate_share(v1, f, v0) > 0
    assert N.degenerate_share(v0, f, v0) == 0


# ------------------------------------------------------------------------------------------------ urogenital helpers
def test_volume_of_a_closed_mesh_and_kabsch():
    import trimesh
    b = trimesh.creation.box(extents=(10.0, 20.0, 3.0))
    assert abs(U.volume(np.asarray(b.vertices), np.asarray(b.faces)) - 600.0) < 1e-6
    rng = np.random.default_rng(0)
    X = rng.normal(size=(30, 3)) * 10
    a = 0.3
    R = np.array([[np.cos(a), -np.sin(a), 0], [np.sin(a), np.cos(a), 0], [0, 0, 1.0]])
    Y = X @ R.T + np.array([5.0, -3.0, 2.0])
    s, R2, mx, my = U.kabsch(X, Y, scale=True)
    assert abs(s - 1.0) < 1e-6 and np.allclose((X - mx) @ R2.T + my, Y, atol=1e-6)


def test_node_merging_joins_seam_pairs_across_the_two_halves_only():
    l = np.array([[-1.0, 0, 0], [-1.0, 10, 0], [-20.0, 0, 0]])
    r = np.array([[1.0, 0, 0], [1.0, 10, 0], [20.0, 0, 0]])
    f = np.array([[0, 1, 2]])
    X, node, off = U.build_nodes({"l": l, "r": r}, ["l", "r"], tol=1.5, seam_mm=3.0, comp_mm=0, faces=None)
    assert node[0] == node[3] and node[1] == node[4]          # seam pairs: one node
    assert node[2] != node[5]                                  # the lateral vertices stay apart


# ------------------------------------------------------------------------------------------------ page level
def _page(which):
    d, stem, old = PAGES[which]
    if not (d / f"{stem}.html").exists():
        pytest.skip(f"{d} not built")
    from scripts.zanatomy import q205_pages as P
    man, blob = P.load_page(d, stem)
    return man, blob, P


@pytest.mark.parametrize("which", ["male", "female"])
def test_scope_only_skin_patches_changed_and_all_listed(which):
    d, stem, old = PAGES[which]
    p = REPO / "data" / "derived" / f"Q207_ship_diff_{which}.json"
    if not p.exists() or not (d / f"{stem}.html").exists():
        pytest.skip("not built")
    r = json.loads(p.read_text())
    assert r["geometry_changed_but_not_listed"] == [] and r["added"] == [] and r["removed"] == []
    assert all(i.startswith("zan_skin_") for i in r["geometry_changed"])
    assert len(r["geometry_changed"]) == r["listed_structures"]
    from scripts.zanatomy import q205_shipdiff as SD
    r2 = SD.diff(old, d, stem, sorted(r["geometry_changed"]))
    assert r2["geometry_changed_but_not_listed"] == [] and set(r2["geometry_changed"]) == set(r["geometry_changed"])


@pytest.mark.parametrize("which", ["male", "female"])
def test_moved_cards_carry_before_after_numbers(which):
    man, blob, P = _page(which)
    d, stem, old = PAGES[which]
    r = json.loads((REPO / "data" / "derived" / f"Q207_ship_diff_{which}.json").read_text())
    E = {m["id"]: m for m in man["meshes"]}
    for i in r["geometry_changed"]:
        b = (E[i].get("rec") or {}).get("procedural_badge") or ""
        assert "Q207" in b and "->" in b and re.search(r"\d", b), i


@pytest.mark.parametrize("which", ["male", "female"])
def test_wrist_hand_structures_inside_the_skin_after(which):
    p = REPO / "data" / "derived" / f"Q207_report_{which}.json"
    if not p.exists():
        pytest.skip("no report")
    rep = json.loads(p.read_text())
    for side in "lr":
        a, b = rep["zone"][side]["before"]["classes"], rep["zone"][side]["after"]["classes"]
        assert b["bone"]["audit_gt5pct"] == 0 and b["bone"]["fine_gt5pct"] == 0
        assert b["bone"]["fine_mean_gt0.5_pct"] <= a["bone"]["fine_mean_gt0.5_pct"]
        for c in ("vessel", "nerve", "joint", "bursa"):
            if c in b:
                assert b[c]["audit_gt5pct"] <= a[c]["audit_gt5pct"] and b[c]["fine_gt5pct"] == 0, (side, c)


def test_male_right_wrist_bones_no_longer_poke_through():
    p = REPO / "data" / "derived" / "Q207_report_male.json"
    if not p.exists():
        pytest.skip("no report")
    rep = json.loads(p.read_text())
    bn = rep["zone"]["r"]["after"]["bones"]
    for k in ("zan_triquetrum_bone_r", "zan_lunate_bone_r", "radius_r"):
        assert bn[k]["audit_gt3_pct"] < 5.0 and bn[k]["audit_max_mm"] < 3.0, k


def test_urogenital_patch_refit_to_the_source_volume_without_midline_overlap_and_sealed():
    p = REPO / "data" / "derived" / "Q207_report_male.json"
    if not p.exists():
        pytest.skip("no report")
    rep = json.loads(p.read_text())
    u = rep["urogenital"]
    for k in "lr":
        v0, v1, vs = u["volume_mm3"][k]
        assert abs(v1 / vs - 1) < 0.08 and abs(v0 / vs - 1) > 0.10, (k, v0, v1, vs)
    a, b = u["across_midline_plane_mm_before"], u["across_midline_plane_mm_after"]
    assert max(b.values()) < 3.0 and max(a.values()) > 10.0         # the r half reached 20+ mm into the l side before
    assert rep["envelope_L"]["after"] > 95.0


def test_nail_plates_have_no_collapsed_edges_after():
    for which in ("male", "female"):
        d, stem, old = PAGES[which]
        if not (d / f"{stem}.html").exists():
            pytest.skip("not built")
        from scripts.zanatomy import q205_pages as P
        man, blob = P.load_page(d, stem)
        S = P.decode(man, blob, only=lambda m: m["id"].startswith("zan_skin_nail_plate_") and m["id"][-2:] in ("_l", "_r") and "foot" not in m["id"])
        mo, bo = P.load_page(REPO / "build" / "q197" / ("viewer_zan_atlas" if which == "male" else "viewer_base_female"), "atlas_viewer_zan_atlas" if which == "male" else "atlas_viewer_base_female")
        So = P.decode(mo, bo)
        for i, e in S.items():
            assert N.degenerate_share(e["v"], e["f"], So[i]["v"]) < 0.01, (which, i)


def test_female_clinical_files_unchanged_and_risk_absent():
    d, stem, old = PAGES["female"]
    if not d.exists():
        pytest.skip("not built")
    assert not (d / "clinical_risk.json").exists()
    for f in old.glob("clinical_*"):
        if f.name == "clinical_risk.json":
            continue
        assert (d / f.name).read_bytes() == f.read_bytes(), f.name
