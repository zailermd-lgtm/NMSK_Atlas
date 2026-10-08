"""Q208: forearm / wrist / elbow skin slabs re-warped onto the person's own skin, male urogenital rim weld -- synthetic tests of the tube map (bone-pair frames, own-skin radius, slab twin offset, welds),
the slab topology helpers and the rim solve, and (when the Q208 pages / reports are built) the page-level guards: scope = the listed skin patches only, every changed card carries its before -> after numbers,
forearm sections closed and free of radius steps, slab thickness preserved, border steps closed, female clinical files present (only clinical_needle_tool.js is compared byte for byte)."""
import json
import re
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.zanatomy import q208_refit as RF  # noqa: E402
from scripts.zanatomy import q208_tube as T  # noqa: E402
from scripts.zanatomy import q207_geom as G  # noqa: E402
from scripts.zanatomy import q207_weld as WD  # noqa: E402

PAGES = {"male": (REPO / "build" / "q208" / "viewer_zan_vhm", "atlas_viewer_zan_male_fitted", REPO / "build" / "q207" / "viewer_zan_vhm"),
         "female": (REPO / "build" / "q208" / "viewer_zan_female", "atlas_viewer_zan_female", REPO / "build" / "q207" / "viewer_zan_female")}


# ------------------------------------------------------------------------------------------------ synthetic fixtures
def cylinder_bone(centre, radius, length, n_s=30, n_t=16, x0=0.0):
    """vertices of a cylinder along +x (a stand-in for a bone): (n_s * n_t, 3)"""
    xs = np.linspace(x0, x0 + length, n_s)
    th = np.linspace(0, 2 * np.pi, n_t, endpoint=False)
    return np.array([[x, centre[0] + radius * np.cos(t), centre[1] + radius * np.sin(t)] for x in xs for t in th])


def tube_slab(r_out=30.0, length=200.0, n_s=21, n_t=24, thick=3.0):
    """a closed slab around the x axis: outer sheet radius r_out, inner sheet r_out - thick, rim walls at both ends; faces outward wound"""
    xs = np.linspace(0, length, n_s)
    th = np.linspace(0, 2 * np.pi, n_t, endpoint=False)
    vo = np.array([[x, r_out * np.cos(t), r_out * np.sin(t)] for x in xs for t in th])
    vi = np.array([[x, (r_out - thick) * np.cos(t), (r_out - thick) * np.sin(t)] for x in xs for t in th])
    m = len(vo)
    f = []
    idx = lambda i, j: i * n_t + (j % n_t)
    for i in range(n_s - 1):
        for j in range(n_t):
            a, b, c, d = idx(i, j), idx(i, j + 1), idx(i + 1, j), idx(i + 1, j + 1)
            f += [[a, c, b], [b, c, d]]
            f += [[a + m, b + m, c + m], [b + m, d + m, c + m]]
    for i in (0, n_s - 1):                      # end walls
        for j in range(n_t):
            a, b = idx(i, j), idx(i, j + 1)
            f += [[a, b, b + m], [a, b + m, a + m]] if i == n_s - 1 else [[a, b + m, b], [a, a + m, b + m]]
    return np.vstack([vo, vi]), np.array(f)


class FakeSkin:
    """own skin stand-in: a watertight cylinder of radius R around the x axis (trimesh)"""

    def __init__(self, R=40.0, length=300.0):
        import trimesh
        self.tm = trimesh.creation.cylinder(radius=R, height=length, sections=64)
        self.tm.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0]))
        self.tm.apply_translation([length / 2 - 20, 0, 0])


def bone_pair(offset=(0.0, 0.0), roll=0.0, scale=1.0):
    """radius / ulna stand-ins: two thin cylinders at +-8 mm about the axis, rotated by `roll` about x"""
    c, s = np.cos(roll), np.sin(roll)
    R = np.array([[c, -s], [s, c]])
    a = (R @ np.array([-8.0 * scale, 0.0])) + np.array(offset)
    b = (R @ np.array([8.0 * scale, 0.0])) + np.array(offset)
    return cylinder_bone(a, 4.0, 180.0, x0=10.0), cylinder_bone(b, 4.0, 180.0, x0=10.0)


# ------------------------------------------------------------------------------------------------ tube map
def test_frames_follow_the_bone_pair_and_the_roll_is_recovered():
    r, u = bone_pair()
    F = T.Frames(r, u, wrist=[200.0, 0, 0])
    o, e1, e2 = F.at(np.array([-100.0]))
    assert abs(abs(F.a @ [1, 0, 0]) - 1) < 1e-3 and np.allclose(o[0, 1:], 0, atol=0.5)
    r2, u2 = bone_pair(roll=np.radians(40))
    F2 = T.Frames(r2, u2, wrist=[200.0, 0, 0])
    _, e1b, _ = F2.at(np.array([-100.0]))
    ang = np.degrees(np.arccos(np.clip(e1[0] @ e1b[0], -1, 1)))
    assert abs(ang - 40) < 1.5


def test_monotone_map_is_monotone_and_extrapolates_linearly():
    s = np.random.default_rng(0).uniform(-200, 0, 400)
    g = T.monotone_map(s, 1.1 * s + 5 + np.random.default_rng(1).normal(0, 0.3, 400))
    x = np.linspace(-260, 40, 60)
    y = g(x)
    assert np.all(np.diff(y) > 0) and abs(g(-100.0) - (1.1 * -100 + 5)) < 1.0


def test_tube_map_puts_the_outer_sheet_on_the_own_skin_and_keeps_the_twin_offset():
    v, f = tube_slab(r_out=30.0)
    rs, us = bone_pair()
    Fs = T.Frames(rs, us, wrist=[200.0, 0, 0])
    rp, up = bone_pair(offset=(0.0, 0.0), roll=np.radians(30))
    Fp = T.Frames(rp, up, wrist=[200.0, 0, 0])
    g = lambda s: np.asarray(s, float)
    own = FakeSkin(R=40.0)
    prof = T.OwnProfile(own.tm, Fp, -190.0, 10.0)
    S = RF.Slabs({"a": v}, {"a": f}, ["a"])
    outer = S.outer_flags(rho=Fs.coords(S.V)[2])
    P, outer2, co = RF.tube_positions(S, Fs, Fp, g, prof, margin=1.0, outer=outer)
    # outer sheet: 1 mm inside the 40 mm cylinder (profile smoothing tolerance 1 mm); inner sheet: the twin 3 mm further in
    r_out = np.hypot(P[outer][:, 1], P[outer][:, 2])
    inb = (P[outer][:, 0] > 10) & (P[outer][:, 0] < 190)
    assert np.all(np.abs(r_out[inb] - 39.0) < 1.2)
    tw = np.linalg.norm(P - P[S.twin], axis=1)
    assert np.all(np.abs(tw - 3.0) < 0.6)                                   # the source twin offset is carried in the local frame


def test_tube_map_is_a_function_of_position_so_shared_vertices_stay_shared():
    v, f = tube_slab()
    v2 = v.copy()
    S1 = RF.Slabs({"a": v, "b": v2}, {"a": f, "b": f}, ["a", "b"])           # two copies of the same patch = every vertex shared
    rs, us = bone_pair()
    Fs = T.Frames(rs, us, wrist=[200.0, 0, 0])
    rp, up = bone_pair(roll=np.radians(20))
    Fp = T.Frames(rp, up, wrist=[200.0, 0, 0])
    prof = T.OwnProfile(FakeSkin(35.0).tm, Fp, -190.0, 10.0)
    P, _, _ = RF.tube_positions(S1, Fs, Fp, lambda s: np.asarray(s, float), prof)
    n = len(v)
    assert np.allclose(P[:n], P[n:], atol=1e-6)
    assert S1.nnode == n                                                    # merged nodes


def test_slab_twin_and_outer_flags_on_a_closed_slab():
    v, f = tube_slab(r_out=30.0, thick=3.0)
    S = RF.Slabs({"a": v}, {"a": f}, ["a"])
    assert np.allclose(np.linalg.norm(v - v[S.twin], axis=1), 3.0, atol=1e-6)
    o = S.outer_flags(bone_pts=cylinder_bone((0, 0), 5.0, 200.0))
    assert o.sum() == len(v) // 2 and np.hypot(v[o][:, 1], v[o][:, 2]).min() > 29.9


def test_boundary_correction_decays_into_the_patch():
    v, f = tube_slab()
    S = RF.Slabs({"a": v}, {"a": f}, ["a"])
    x = v[:, 0]
    fixed = {int(i): v[i] + np.array([0, 0, 5.0]) for i in np.flatnonzero(x < 1.0)}          # the rim at x = 0 must move 5 mm
    P2, D = RF.correct(S, v.copy(), fixed, mu=0.08)
    d = np.abs(P2[:, 2] - v[:, 2])
    assert d[x < 1.0].min() > 4.9 and d[x > 150].max() < 0.5 and np.all(np.diff([d[(x > a) & (x < a + 20)].mean() for a in range(0, 180, 20)]) < 0.01)


def test_stray_neighbour_vertex_is_flagged_and_not_used_as_a_weld_target():
    v, f = tube_slab()
    S = RF.Slabs({"a": v}, {"a": f}, ["a"])
    cur = v.copy()
    k = int(np.flatnonzero(np.abs(v[:, 0] - 100) < 1)[0])
    cur[k] += np.array([0, 40.0, 0])                                         # a vertex the earlier fits pulled away from its twin
    st = RF.twin_stray(v, cur)
    assert st[k] and st.sum() <= 2


def test_least_squares_rim_weld_closes_a_step_between_two_patches():
    xs = np.array([0.0, 10.0, 20.0])
    a = np.array([[x, y, 0.0] for y in xs for x in xs])
    fa = []
    for j in range(2):
        for i in range(2):
            k = j * 3 + i
            fa += [[k, k + 1, k + 3], [k + 1, k + 4, k + 3]]
    fa = np.array(fa)
    b = a + np.array([20.0, 0, 0])
    V = {"A": a.copy(), "B": b + np.array([0, 0, 3.0])}                     # B sits 3 mm too high along the shared border (x = 20)
    raw = {"A": a, "B": b}
    ids = ["A", "B"]
    cons = WD.border_pairs(raw, ids)
    assert len(cons) >= 3
    new = WD.solve(V, {"A": fa, "B": fa}, ids, cons, {"A", "B"}, gate_gap=0.5, w_pull=20.0, lam_s=0.3, log=lambda *x: None)
    gap = np.linalg.norm(new["A"][[2, 5, 8]] - new["B"][[0, 3, 6]], axis=1)
    assert gap.max() < 0.6


# ------------------------------------------------------------------------------------------------ page-level guards
def _page(which):
    d, stem, old = PAGES[which]
    if not (d / f"{stem}.html").exists():
        pytest.skip("not built")
    from scripts.zanatomy import q205_pages as P
    man, blob = P.load_page(d, stem)
    return man, blob, P


def _report(which):
    p = REPO / "data" / "derived" / f"Q208_report_{which}.json"
    if not p.exists():
        pytest.skip("no report")
    return json.loads(p.read_text())


@pytest.mark.parametrize("which", ["male", "female"])
def test_scope_only_skin_patches_changed_and_all_listed(which):
    d, stem, old = PAGES[which]
    p = REPO / "data" / "derived" / f"Q208_ship_diff_{which}.json"
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
    r = json.loads((REPO / "data" / "derived" / f"Q208_ship_diff_{which}.json").read_text())
    E = {m["id"]: m for m in man["meshes"]}
    for i in r["geometry_changed"]:
        b = (E[i].get("rec") or {}).get("procedural_badge") or ""
        assert "Q208" in b and "->" in b and re.search(r"\d", b), i


@pytest.mark.parametrize("which", ["male", "female"])
def test_forearm_slabs_are_clean_and_not_stretched(which):
    rep = _report(which)
    tube = {i: m for i, m in rep["moved"].items() if m["group"].startswith("forearm")}
    assert len(tube) == 12
    for i, m in tube.items():
        (p5b, p95b), (p5a, p95a) = m["edge_ratio_p5_p95"]
        assert p5a >= 0.6 and p95a <= 1.9, (i, m["edge_ratio_p5_p95"])             # before: p5 down to 0.37, p95 up to 3.1
        assert m["twin_distance_mm"]["median"][1] > 2.5 and abs(m["twin_distance_mm"]["median"][1] - 3.0) < 0.5, i
        assert m["outside_own_skin_gt2mm_pct"][1] < 5.0, i


@pytest.mark.parametrize("which", ["male", "female"])
def test_forearm_sections_closed_and_without_radius_steps(which):
    rep = _report(which)
    for side in "lr":
        a, b = rep["forearm_sections"][side]["q207"], rep["forearm_sections"][side]["q208"]
        assert b["closed"] >= 0.9 * b["slices"] and b["closed"] >= a["closed"]
        assert b["radius_step_max_mm_per_3mm"] <= 3.0
        assert b["segment_crossings"] <= a["segment_crossings"]


@pytest.mark.parametrize("which", ["male", "female"])
def test_deep_skin_sheet_crossings_of_the_forearm_slabs_drop(which):
    rep = _report(which)
    c = rep["crossings"]
    a = c["q207"]["deep_pairs_by_category"].get("forearm_wrist_elbow_internal", 0)
    b = c["q208"]["deep_pairs_by_category"].get("forearm_wrist_elbow_internal", 0)
    assert b <= 0.35 * a + 40, (a, b)
    assert c["q208"]["depth_gt_2mm"] <= c["q207"]["depth_gt_2mm"]
    assert c["q208"]["depth_gt_4mm"] <= c["q207"]["depth_gt_4mm"]


def test_male_urogenital_rims_welded_to_anal_and_thigh_patches():
    rep = _report("male")
    assert rep["seams"]["q207"]["max_step_mm"] > 7.0
    for i in ("zan_skin_urogenital_region_l", "zan_skin_urogenital_region_r"):
        m = rep["moved"][i]
        assert m["seam_step_max_mm"][0] > 4.0 and m["seam_step_max_mm"][1] <= 2.0, i
        assert m["max_move_mm"] < 6.0
    for n in ("anal_region", "anterior_region_of_thigh"):
        for s in "lr":
            assert rep["moved"][f"zan_skin_{n}_{s}"]["max_move_mm"] < 3.0                     # neighbours move only slightly
    u = rep["urogenital"]["volume_mm3"]
    for k in "lr":
        v0, v1, vs = u[k]
        assert abs(v1 / vs - 1) < 0.10


@pytest.mark.parametrize("which", ["male", "female"])
def test_envelope_sealed_and_no_new_open_edges(which):
    p = REPO / "data" / "derived" / f"Q208_metrics_after_{which}.json"
    q = REPO / "data" / "derived" / f"Q207_metrics_after_{which}.json"
    if not p.exists():
        pytest.skip("no metrics")
    a, b = json.loads(q.read_text()), json.loads(p.read_text())
    assert b["envelope"]["envelope_L_close2"] > 0.97 * a["envelope"]["envelope_L_close2"]
    assert b["open"]["open_boundary_edges_total"] == a["open"]["open_boundary_edges_total"]
    assert all(x["escape_fraction"] <= 0.01 for x in b["escape"].values())


def test_female_clinical_files_present_needle_tool_unchanged():
    d, stem, old = PAGES["female"]
    if not d.exists():
        pytest.skip("not built")
    names = sorted(f.name for f in old.glob("clinical_*"))
    assert names and names == sorted(f.name for f in d.glob("clinical_*"))
    for f in old.glob("clinical_needle_tool.js"):
        assert (d / f.name).read_bytes() == f.read_bytes(), f.name
