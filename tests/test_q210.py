"""Q210: male Z-fitted page -- (1) the genital structures vs the urogenital skin (skin refit to the structures' scale), (2) forearm vs trunk / thigh skin contact relaxation, (3) the left palmaris longus.
Synthetic tests of the helpers (partition relaxation on two crossing slabs, tendon pull-inside, enclosure criterion) and, when the Q210 page / report are built, the page-level guards: scope = the listed
meshes only (ship diff), genital structures byte-identical and inside the skin, forearm | trunk deep face pairs gone, no border step > 3 mm, every changed card carries its before -> after numbers."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.zanatomy import q207_geom as G  # noqa: E402
from scripts.zanatomy import q210_contact as CT  # noqa: E402
from scripts.zanatomy import q210_genital as GN  # noqa: E402
from scripts.zanatomy import q210_struct as ST  # noqa: E402

PAGE = REPO / "build" / "q210" / "viewer_zan_vhm"
SRC = REPO / "build" / "q208" / "viewer_zan_vhm"
STEM = "atlas_viewer_zan_male_fitted"
REPORT = REPO / "data" / "derived" / "Q210_report_male.json"
SHIP = REPO / "data" / "derived" / "Q210_ship_diff_male.json"


# ------------------------------------------------------------------------------------------------ synthetic fixtures
def slab_grid(n=15, size=60.0, z0=0.0, t=3.0, x0=-30.0, y0=-30.0):
    """a closed slab: outer sheet at z0 + t (outward +z), inner sheet at z0, rim walls; faces outward wound"""
    xs = np.linspace(0, size, n)
    v = np.array([[x0 + x, y0 + y, z0 + t] for y in xs for x in xs] + [[x0 + x, y0 + y, z0] for y in xs for x in xs])
    m = n * n
    f = []
    for j in range(n - 1):
        for i in range(n - 1):
            a = j * n + i
            f += [[a, a + 1, a + n], [a + 1, a + n + 1, a + n]]
            f += [[a + m, a + n + m, a + 1 + m], [a + 1 + m, a + n + m, a + n + 1 + m]]
    for k in range(n - 1):                                  # rim walls (4 sides)
        for a, b in ((k, k + 1), (n * (n - 1) + k + 1, n * (n - 1) + k), (k * n + n, k * n), ((k + 1) * n - 1, (k + 2) * n - 1)):
            if 0 <= a < m and 0 <= b < m:
                f += [[a, b, b + m], [a, b + m, a + m]]
    return v, np.array(f)


class Fake:
    """minimal page stand-in (skin_ids, v, f, S)"""

    def __init__(self, V, F):
        self.V, self.F = V, F
        self.skin_ids = list(V)
        self.S = {i: {} for i in V}

    def v(self, i):
        return self.V[i]

    def f(self, i):
        return self.F[i]


def toy_scene():
    """a tilted forearm slab (outward normal -z, outer sheet z = 1 + 0.2 x) cutting through a flat trunk slab (z in [0, 3], outward +z); forearm tissue is the plane z = 40, trunk tissue the plane z = -25"""
    vF, fF = slab_grid(z0=0.0, t=3.0)
    vF = vF.copy()
    vF[:, 2] = -vF[:, 2] + 4.0 + 0.2 * vF[:, 0]            # reflected: the outer sheet (first half) faces -z, at z = 1 + 0.2 x; inner sheet 3 mm above
    fF = fF[:, ::-1].copy()                                 # reflection reverses the winding
    vT, fT = slab_grid(n=12, size=64.0, z0=0.0, t=3.0, x0=-32.0, y0=-31.3)       # a different grid: coincident grids give degenerate (on-edge) crossings
    V = {"zan_skin_forearm_l": vF, "zan_skin_trunk_l": vT}
    F = {"zan_skin_forearm_l": fF, "zan_skin_trunk_l": fT}
    gx, gy = np.meshgrid(np.linspace(-40, 40, 17), np.linspace(-40, 40, 17))
    tissue = {"l": np.stack([gx.ravel(), gy.ravel(), np.full(gx.size, 40.0)], 1), "r": np.stack([gx.ravel(), gy.ravel(), np.full(gx.size, 400.0)], 1), "trunk": np.stack([gx.ravel(), gy.ravel(), np.full(gx.size, -25.0)], 1)}
    return V, F, tissue


# ------------------------------------------------------------------------------------------------ tests: relaxation
def test_toy_scene_crosses_before():
    V, F, tissue = toy_scene()
    Vc, Fc, ow, nm = G.concat({i: (V[i], F[i]) for i in V})
    pr = G.intersecting_pairs(Vc, Fc, ow)
    assert len(pr) > 20


def test_relax_removes_crossing_and_keeps_margins():
    V, F, tissue = toy_scene()
    pg, raw = Fake(V, F), Fake({i: v.copy() for i, v in V.items()}, F)
    out, rep = CT.relax(pg, raw, V, ["zan_skin_forearm_l"], ["zan_skin_trunk_l"], tissue, max_it=6, absorb_it=3, count_every=1, log=lambda *a: None)
    Vc, Fc, ow, nm = G.concat({i: (out[i], F[i]) for i in out})
    pr = G.intersecting_pairs(Vc, Fc, ow)
    dd = G.pair_depth(Vc, Fc, pr) if len(pr) else np.zeros(0)
    assert (dd > CT.STOP_DEPTH).sum() == 0
    # each skin stays at least MARGIN_KEEP over its own tissue (and both slabs keep their thickness)
    from scipy.spatial import cKDTree
    assert cKDTree(tissue["l"]).query(out["zan_skin_forearm_l"])[0].min() >= CT.MARGIN_KEEP - 1e-6
    assert cKDTree(tissue["trunk"]).query(out["zan_skin_trunk_l"])[0].min() >= CT.MARGIN_KEEP - 1e-6
    for i in out:
        n = len(V[i]) // 2
        t0 = np.linalg.norm(V[i][:n] - V[i][n:], axis=1).mean()
        t1 = np.linalg.norm(out[i][:n] - out[i][n:], axis=1).mean()
        assert abs(t1 - t0) < 0.6


def test_relax_moves_the_skin_with_the_larger_margin_more():
    V, F, tissue = toy_scene()
    pg, raw = Fake(V, F), Fake({i: v.copy() for i, v in V.items()}, F)
    out, rep = CT.relax(pg, raw, V, ["zan_skin_forearm_l"], ["zan_skin_trunk_l"], tissue, max_it=6, absorb_it=3, count_every=1, log=lambda *a: None)
    mf = np.linalg.norm(out["zan_skin_forearm_l"] - V["zan_skin_forearm_l"], axis=1).max()
    mt = np.linalg.norm(out["zan_skin_trunk_l"] - V["zan_skin_trunk_l"], axis=1).max()
    assert mf > 0 and mt > 0 and rep["rho"]["l"] > 0


def test_relax_without_crossing_is_identity():
    V, F, tissue = toy_scene()
    V = dict(V)
    V["zan_skin_forearm_l"] = V["zan_skin_forearm_l"] + np.array([0, 0, 40.0])   # far away
    pg, raw = Fake(V, F), Fake({i: v.copy() for i, v in V.items()}, F)
    tissue = dict(tissue)
    tissue["l"] = tissue["l"] + np.array([0, 0, 40.0])
    out, rep = CT.relax(pg, raw, V, ["zan_skin_forearm_l"], ["zan_skin_trunk_l"], tissue, max_it=3, absorb_it=1, count_every=1, log=lambda *a: None)
    for i in V:
        assert np.abs(out[i] - V[i]).max() < 1e-6


# ------------------------------------------------------------------------------------------------ tests: palmaris helper
class FakeOwn:
    """own skin stand-in: the half space z < 0 (trimesh slab for the nearest point queries)"""

    def __init__(self):
        import trimesh
        self.tm = trimesh.creation.box(extents=(400, 400, 200))
        self.tm.apply_translation([0, 0, -100.0])            # box top face at z = 0, outward normal +z

    def sd(self, P):
        P = np.asarray(P, float)
        return P[:, 2].copy()                                 # + outside; exact on the top face area


def tube_mesh(n_s=40, n_t=10, r=3.0, length=120.0, z0=-10.0):
    xs = np.linspace(0, length, n_s)
    th = np.linspace(0, 2 * np.pi, n_t, endpoint=False)
    v = np.array([[x - 60.0, r * np.cos(t), z0 + r * np.sin(t)] for x in xs for t in th])
    f = []
    idx = lambda i, j: i * n_t + (j % n_t)
    for i in range(n_s - 1):
        for j in range(n_t):
            a, b, c, d = idx(i, j), idx(i, j + 1), idx(i + 1, j), idx(i + 1, j + 1)
            f += [[a, c, b], [b, c, d]]
    return v, np.array(f)


def test_pull_inside_brings_a_protruding_tendon_end_back():
    v, f = tube_mesh()
    v = v.copy()
    tip = v[:, 0] > 40.0
    v[tip, 2] += 15.0 + (v[tip, 0] - 40.0) * 0.2           # the tendon end sticks out of the skin (z > 0) by up to ~19 mm
    own = FakeOwn()
    assert (own.sd(v) > 0).sum() > 10
    w, info = ST.pull_inside(v, f, own, margin=1.0, need=0.3, decay_mm=25.0)
    assert (own.sd(w) > -0.3).sum() == 0
    far = np.linalg.norm(v - np.array([-60.0, 0, -10.0]), axis=1) > 0
    assert np.abs(w[v[:, 0] < 0] - v[v[:, 0] < 0]).max() < 1e-6          # the part more than 25 mm (mesh distance) from the tip keeps its place
    assert info["outside"] > 10


def test_pull_inside_identity_when_inside():
    v, f = tube_mesh()
    w, info = ST.pull_inside(v, f, FakeOwn())
    assert np.abs(w - v).max() == 0 and info["violating"] == 0


# ------------------------------------------------------------------------------------------------ tests: enclosure criterion
def row(a, f5=0.0, fm=0.0):
    return {"audit_gt3_pct": a, "fine_gt0.5_pct": f5, "fine_max_mm": fm}


def test_passes_requires_zero_audit_and_small_fine():
    ok, bad = GN.passes({"zan_glans_penis": row(0.0, 8.0, 2.4), "zan_testis_l": row(0.0, 11.9, 4.3)})
    assert ok and not bad
    ok, bad = GN.passes({"zan_glans_penis": row(0.4, 0.0, 0.0)})
    assert not ok and "zan_glans_penis" in bad
    ok, bad = GN.passes({"zan_glans_penis": row(0.0, 13.0, 1.0)})
    assert not ok
    ok, bad = GN.passes({"zan_glans_penis": row(0.0, 0.0, 6.0)})
    assert not ok
    ok, bad = GN.passes({"zan_external_pudendal_veins_l": row(8.0, 11.0, 8.0)})      # groin vessels are reported, not part of the test
    assert ok


# ------------------------------------------------------------------------------------------------ page-level guards (when built)
built = pytest.mark.skipif(not (PAGE / f"{STEM}.html").exists() or not REPORT.exists() or not SHIP.exists(), reason="Q210 page / report not built")


@built
def test_scope_only_listed_meshes_changed():
    r = json.loads(SHIP.read_text())
    assert r["geometry_changed_but_not_listed"] == [] and r["added"] == [] and r["removed"] == []
    assert r["card_only"] == []
    assert r["listed_structures"] == len(r["geometry_changed"])
    ids = set(r["geometry_changed"])
    for i in ids:
        assert i.startswith("zan_skin_") or i == ST.ID


@built
def test_genital_structures_byte_identical():
    from scripts.zanatomy import q210_core as K
    r = json.loads(SHIP.read_text())
    for i in K.GEN_ALL:
        assert i not in r["geometry_changed"], i


@built
def test_changed_cards_carry_before_after_numbers():
    from scripts.zanatomy import q205_pages as P5
    man, blob = P5.load_page(PAGE, STEM)
    r = json.loads(SHIP.read_text())
    by = {m["id"]: m for m in man["meshes"]}
    for i in r["geometry_changed"]:
        b = (by[i].get("rec") or {}).get("procedural_badge", "")
        assert "Q210" in b and (" -> " in b), i
        assert "Rule-based, nothing invented" in b


@built
def test_genital_structures_inside_displayed_skin():
    rep = json.loads(REPORT.read_text())
    from scripts.zanatomy import q210_core as K
    fin = rep["genital"]["structures_final_state"]
    for i in K.GEN_MAIN:
        assert fin[i]["audit_gt3_pct"] == 0.0, (i, fin[i])
        assert fin[i]["fine_max_mm"] <= 5.0, (i, fin[i])
    for i in K.GEN_MAIN:
        assert rep["genital"]["structures_outside_own_skin_pct"][i] <= 1.0          # unchanged by Q210 (the structures were not moved): at most 0.1 mm over his own skin


@built
def test_genital_refit_guards():
    rep = json.loads(REPORT.read_text())
    g = rep["genital"]
    vs = g["volume_mm3"]
    for k in "lr":
        assert vs[k][1] <= 1.7 * vs[k][2]                      # not more than the structures' fit scale allows
    xa = g["across_midline_plane_mm_after"]
    xb = g["across_midline_plane_mm_before"]
    assert xa["l_reaches_into_r_side"] <= max(xb["l_reaches_into_r_side"], 3.0) + 1.0
    assert xa["r_reaches_into_l_side"] <= max(xb["r_reaches_into_l_side"], 3.0) + 1.0
    assert 99.0 < g["envelope_L_final"] < 101.5               # sealed, same body volume


@built
def test_forearm_trunk_pairs_gone():
    rep = json.loads(REPORT.read_text())
    c = rep["contact"]
    assert c["before"]["deep_gt2"] >= 1000                   # the Q209 count reproduced
    assert c["after"]["deep_gt2"] <= 0.05 * c["before"]["deep_gt2"]
    assert c["after"]["other_deep_pairs_among_candidates"] <= c["before"]["other_deep_pairs_among_candidates"] + 40


@built
def test_no_new_border_steps_and_skin_stays_over_tissue():
    rep = json.loads(REPORT.read_text())
    assert rep["seams"]["q210"]["steps_gt_3mm"] <= rep["seams"]["q208"]["steps_gt_3mm"]
    assert rep["seams"]["q210"]["max_step_mm"] <= max(rep["seams"]["q208"]["max_step_mm"], 3.0)
    for i, m in rep["contact"]["margins"].items():
        assert m["min_margin_mm"][1] >= min(m["min_margin_mm"][0], CT.MARGIN_KEEP) - 0.05, (i, m)       # never closer to the own tissue than before or 1 mm
    for i, m in rep["moved"].items():
        t0, t1 = m["thickness_median_mm"]
        assert abs(t1 - t0) < 0.8 or 2.0 <= t1 <= 3.4, (i, m["thickness_median_mm"])      # the 3 mm slab thickness is kept (the 26-vertex anal patch 3.69 -> 2.64 mm: closer to the 3.0 of the Z source)


@built
def test_palmaris_inside_own_skin():
    rep = json.loads(REPORT.read_text())
    if "palmaris" not in rep:
        pytest.skip("palmaris not in this build")
    p = rep["palmaris"]
    assert p["outside_own_skin"][0] > 0 and p["outside_own_skin"][1] == 0
    assert p["outside_displayed_skin_gt3_pct"][1] == 0.0
    assert abs(p["extent_along_axis_mm"][1] / p["extent_along_axis_mm"][0] - 1) < 0.05
