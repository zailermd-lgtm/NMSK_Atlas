"""Q211: Z-fitted pages -- junction repair (elbow + shoulder tear relaxation), evidence-bounded bone re-seats (male left tibia / fibula distal ends, female L1), fit-made inside-bone / outside-skin structures pushed out.
Synthetic tests of the helpers (axial bone field, sparse tear relaxation on two toy sheets, bone-chain field, acceptance rule, badge text) and, when the Q211 pages are built, the page-level guards:
scope = the listed meshes only (ship diff), skin / unlisted bones byte-identical, the female clinical files are the Q208 ones (only clinical_needle_tool.js is compared byte for byte), every changed card carries
its before -> after numbers, the bone gaps closed, the tears down."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.zanatomy import q211_bones as B  # noqa: E402
from scripts.zanatomy import q211_core as K  # noqa: E402
from scripts.zanatomy import q211_relax as RX  # noqa: E402
from scripts.zanatomy import q211_soft as SF  # noqa: E402

PAGES = {"male": REPO / "build" / "q211" / "viewer_zan_vhm", "female": REPO / "build" / "q211" / "viewer_zan_female"}
SRC = {"male": REPO / "build" / "q210" / "viewer_zan_vhm", "female": REPO / "build" / "q208" / "viewer_zan_female"}
STEM = {"male": "atlas_viewer_zan_male_fitted", "female": "atlas_viewer_zan_female"}
SHIP = {w: REPO / "data" / "derived" / f"Q211_ship_diff_{w}.json" for w in PAGES}
built = pytest.mark.skipif(not all((PAGES[w] / f"{STEM[w]}.html").exists() and SHIP[w].exists() for w in PAGES), reason="Q211 pages not built")


# ------------------------------------------------------------------------------------------------ synthetic
def test_axial_field_is_zero_at_the_fixed_end_and_delta_at_the_moving_end():
    v = np.column_stack([np.zeros(11), np.linspace(0, 100, 11), np.zeros(11)])
    d = B.axial_field(v, np.array([0.0, 0, 0]), np.array([0.0, 100, 0]), 6.0, t0=0.3)
    assert np.allclose(d[:4], 0.0)                                 # t <= 0.3: untouched
    assert np.isclose(d[-1][1], 6.0)                               # moving end: full delta along the axis
    assert (np.diff(d[:, 1]) >= -1e-12).all()                      # monotone
    dl = B.axial_field(v, np.array([0.0, 0, 0]), np.array([0.0, 100, 0]), 6.0, linear=True)
    assert np.allclose(dl[:, 1], 6.0 * v[:, 1] / 100.0)


def sheet(n=12, size=30.0, z=0.0):
    xs = np.linspace(0, size, n)
    v = np.array([[x, y, z] for y in xs for x in xs])
    f = []
    for j in range(n - 1):
        for i in range(n - 1):
            a = j * n + i
            f += [[a, a + 1, a + n], [a + 1, a + n + 1, a + n]]
    return v, np.array(f)


def test_tear_relaxation_closes_a_gap_and_keeps_the_shape():
    va, f = sheet()
    vb, _ = sheet(z=1.0)                                           # touching in the Z source (1 mm)
    base = {"a": va, "b": vb}
    cur = {"a": va.copy(), "b": vb + np.array([0.0, 0.0, 12.0])}   # on the fitted page b has drifted 11 mm away
    Z = RX.Zone(["a", "b"], base, cur, {"a": f, "b": f}, np.array([15.0, 15.0, 0.0]), 100.0)
    assert len(Z.P) > 100 and (Z.tears() > 5).all()
    u, active = RX.solve(Z, Z.X, np.ones(Z.n), w_p=1.0, w_s=8.0, w_0=0.05, tol=2.0)
    X = Z.X + u
    assert (Z.tears(X) > 5).mean() < 0.02
    e = RX.edges_of(f)
    l0 = np.linalg.norm(va[e[:, 0]] - va[e[:, 1]], axis=1)
    la = np.linalg.norm(X[:len(va)][e[:, 0]] - X[:len(va)][e[:, 1]], axis=1)
    assert np.abs(la / l0 - 1).max() < 0.05                        # the sheet moved as a piece (smoothness term)


def test_chain_field_follows_the_moving_bone_and_decays():
    bone_a = np.column_stack([np.zeros(50), np.linspace(0, 50, 50), np.zeros(50)])
    bone_b = bone_a + np.array([100.0, 0, 0])
    v0 = {"a": bone_a, "b": bone_b}
    v1 = {"a": bone_a + np.array([0.0, 8.0, 0]), "b": bone_b}
    F = K.ChainField(v0, v1, np.array([0.0, 25.0, 0.0]), ["a", "b"])
    assert set(F.moving) == {"a"}
    near_ = F(np.array([[1.0, 25.0, 0.0]]))[0]
    far = F(np.array([[300.0, 25.0, 0.0]]))[0]
    assert near_[1] > 6.0 and np.linalg.norm(far) < 1.0 and np.linalg.norm(far) < 0.15 * near_[1]


def test_accept_rule():
    m0 = {"outside_skin_pct": 0.0, "inside_bone_pct": 20.0, "stretched_pct": 10.0, "folded_pct": 0.0, "edge_scale": 1.0}
    ok = dict(m0, inside_bone_pct=2.0, stretched_pct=25.0)         # leaves the bone (gain 18) for a stretch of +15: accepted
    assert SF.accept(ok, m0, "muscle", np.array([[0, 1, 2]]))[0]
    bad = dict(m0, outside_skin_pct=12.0)
    assert not SF.accept(bad, m0, "muscle", np.array([[0, 1, 2]]))[0]
    worse = dict(m0, inside_bone_pct=40.0)
    assert not SF.accept(worse, m0, "muscle", np.array([[0, 1, 2]]))[0]


def test_badge_notes_carry_before_after_numbers():
    from scripts.zanatomy import q211_pack as PK
    m = {"outside_skin_pct": 1.0, "outside_skin_max_mm": 2.0, "inside_bone_pct": 30.0, "inside_bone_max_mm": 7.0, "stretched_pct": 5.0, "folded_pct": 0.0}
    a = dict(m, inside_bone_pct=0.0, inside_bone_max_mm=0.4)
    L = {"mean_move_mm": 3.1, "max_move_mm": 9.0, "before": m, "after": a, "zone": "elbow_l"}
    rep = {"tear_gt5_by_structure": {"before": {"x": 0.8}, "after": {"x": 0.1}}, "tear_gt5_before": 0.8, "tear_gt5_after": 0.2, "pairs": 100, "moved": 20}
    t = PK.note_zone(L, rep, "x")
    assert "30.0 %" in t and "0.0 %" in t and "->" in t and "0.8 -> 0.1" in t
    assert "->" in PK.note_inbone(L)


# ------------------------------------------------------------------------------------------------ page level
@built
@pytest.mark.parametrize("which", ["male", "female"])
def test_scope_only_listed_meshes_change(which):
    r = json.loads(SHIP[which].read_text())
    assert r["geometry_changed_but_not_listed"] == [] and r["added"] == [] and r["removed"] == []
    assert r["card_only"] == [] and r["unchanged"] > 2500
    assert set(r["geometry_changed"]) == set(r["stages"])


@built
@pytest.mark.parametrize("which", ["male", "female"])
def test_skin_and_unlisted_bones_byte_identical(which):
    r = json.loads(SHIP[which].read_text())
    pg = K.load(which, src=SRC[which])
    changed = set(r["geometry_changed"])
    assert not [i for i in changed if pg.sys(i) == "skin"]
    bones = sorted(i for i in changed if pg.sys(i) == "bone")
    assert bones == (["fibula_l", "tibia_l"] if which == "male" else ["zan_vertebra_l1"])


@built
@pytest.mark.parametrize("which", ["male", "female"])
def test_changed_cards_carry_before_after_numbers(which):
    r = json.loads(SHIP[which].read_text())
    pg = K.load(which, src=PAGES[which])
    for i in r["geometry_changed"]:
        b = (pg.S[i]["m"].get("rec") or {}).get("procedural_badge", "")
        assert "Q211" in b, i
        assert "->" in b.split("Q211")[-1], i


@built
def test_female_clinical_files_present_needle_tool_unchanged():
    old, new = SRC["female"], PAGES["female"]
    names = sorted(f.name for f in old.glob("clinical_*"))
    assert names and names == sorted(f.name for f in new.glob("clinical_*"))
    assert (old / "clinical_needle_tool.js").read_bytes() == (new / "clinical_needle_tool.js").read_bytes()    # motor points / risk are regenerated by the main session


@built
def test_bone_gaps_closed():
    from scripts.zanatomy.q211_bones import min_gap
    pm, pf = K.load("male", src=PAGES["male"]), K.load("female", src=PAGES["female"])
    pm0, pf0 = K.load("male", src=SRC["male"]), K.load("female", src=SRC["female"])
    g = lambda pg: min_gap(np.vstack([pg.v("tibia_l"), pg.v("fibula_l")]), pg.v("talus_l"))
    assert g(pm0) > 5.0 and g(pm) < 3.0                            # his own ankle gap 2.4 mm
    h = lambda pg: min_gap(pg.v("zan_vertebra_t12"), pg.v("zan_vertebra_l1"))
    assert h(pf0) > 9.0 and h(pf) < 3.0                            # her own meshes 0.25 mm
    assert min_gap(pf.v("zan_vertebra_l1"), pf.v("zan_vertebra_l2")) < 3.5   # the level below did not open


@built
def test_tear_reduced_in_every_repaired_zone():
    for which in ("male", "female"):
        p = REPO / "data" / "derived" / f"Q211_report_{which}.json"
        if not p.exists():
            pytest.skip("report not written")
        z = json.loads(p.read_text())["zones"]
        assert set(z) == {"shoulder_l", "elbow_l", "shoulder_r", "elbow_r"}
        for name, rep in z.items():
            assert rep["tear_gt5_after"] < 0.6 * rep["tear_gt5_before"], (which, name)
