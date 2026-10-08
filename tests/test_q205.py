"""Q205: page I/O (metadata-only patch, card repair), articulated search, reseat of the phalanges on their metacarpal, shoulder field, the committed evidence / fit files, and (when the Q205 pages
are built) the final-page guards: no card name equals its raw id, scope = the listed structures only, thumb joints continuous."""
import json
import re
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.zanatomy import q205_pages as P  # noqa: E402

PAGES = {"male": (REPO / "build" / "q205" / "viewer_zan_vhm", "atlas_viewer_zan_male_fitted"), "female": (REPO / "build" / "q205" / "viewer_zan_female", "atlas_viewer_zan_female")}
BASES = {"male": (REPO / "build" / "q197" / "viewer_zan_atlas", "atlas_viewer_zan_atlas"), "female": (REPO / "build" / "q202" / "viewer_base_female", "atlas_viewer_base_female")}


def norm(s):
    return re.sub(r"[\s_]+", "_", s.strip().lower())


# ------------------------------------------------------------------------------------------------ page I/O
def fake_man(names, recs):
    return {"meshes": [{"id": i, "name": n, "rec": r} for (i, n), r in zip(names, recs)]}


def test_card_repairs_restore_base_name_and_facts_but_keep_the_fit_badge():
    base = fake_man([("pronator_teres_l", "Pronator teres")], [{"origin": "humerus", "nerve": "median", "procedural_badge": "base note"}])
    bad = fake_man([("pronator_teres_l", "pronator teres l")], [{"folder": "derived", "name": "pronator_teres_l", "procedural_badge": "Q201 moved it"}])
    r = P.card_repairs(bad, base)
    name, rec = r["pronator_teres_l"]
    assert name == "Pronator teres"
    assert rec["origin"] == "humerus" and rec["nerve"] == "median"
    assert rec["procedural_badge"] == "Q201 moved it"            # the fitted page's own badge, not the base page's


def test_card_repairs_empty_when_cards_agree():
    base = fake_man([("a", "A")], [{"origin": "x", "procedural_badge": "b1"}])
    fit = fake_man([("a", "A")], [{"origin": "x", "procedural_badge": "other"}])
    assert P.card_repairs(fit, base) == {}


def test_strip_badge():
    assert P.strip_badge({"a": 1, "procedural_badge": "x"}) == {"a": 1}
    assert P.strip_badge(None) == {}


@pytest.mark.skipif(not (REPO / "build" / "q202" / "viewer_zan_vhm").exists(), reason="Q202 page not built here")
def test_meta_only_save_keeps_geometry_bytes(tmp_path):
    d, stem = REPO / "build" / "q202" / "viewer_zan_vhm", "atlas_viewer_zan_male_fitted"
    man, blob = P.load_page(d, stem)
    i = man["meshes"][0]["id"]
    man2, blob2 = P.save_page(tmp_path, stem, man, blob, meta={i: ("Renamed", {"origin": "x"})})
    assert blob2 == blob
    e = {m["id"]: m for m in man2["meshes"]}
    assert e[i]["name"] == "Renamed" and e[i]["rec"] == {"origin": "x"}
    m3, b3 = P.load_page(tmp_path, stem)
    assert b3 == blob and {m["id"]: m for m in m3["meshes"]}[i]["name"] == "Renamed"


# ------------------------------------------------------------------------------------------------ geometry helpers
def test_so3_grid_bounds():
    from scripts.zanatomy import q205_hand as Q5
    g = Q5.so3_grid(300, 60.0, seed=1)
    assert g.shape[1] == 3 and np.linalg.norm(g[0]) == 0
    assert np.degrees(np.linalg.norm(g, axis=1)).max() <= 60.0 + 1e-9


def test_beam_chain_recovers_a_two_bone_pose():
    from scipy.spatial import cKDTree
    from scipy.spatial.transform import Rotation as Rot
    from scripts.zanatomy import q205_hand as Q5
    from scripts.zanatomy import q192_left_hand as H

    class Env:
        def pen(self, A, depth=2.5, w=0.35):
            return 0.0

        def __call__(self, P):
            return np.full(len(P), 20.0)

    rng = np.random.default_rng(0)
    b0 = np.c_[rng.uniform(-3, 3, 400), rng.uniform(0, 30, 400), rng.uniform(-3, 3, 400)]            # bone 0 along +y from the origin
    b1 = np.c_[rng.uniform(-3, 3, 400), rng.uniform(30, 55, 400), rng.uniform(-3, 3, 400)]
    joints = [np.array([0.0, 0.0, 0.0]), np.array([0.0, 30.0, 0.0])]
    th = np.array([[0.0, 0.0, 0.6], [0.0, 0.0, 0.5]])                                              # the true pose: both bones bent in the xy plane
    truth = H.chain_apply(th, [b0, b1], joints)
    Et = cKDTree(np.vstack(truth))
    Ot = cKDTree(np.array([[500.0, 500.0, 500.0]]))

    class M:
        def sub(self, P, n):
            return P[:n]

    class S:
        pts = {"a": b0, "b": b1}
        v = {"a": b0.copy(), "b": b1.copy()}

    X, XV, rep = Q5.beam_chain(H, M(), S(), ["a", "b"], joints, Et, Ot, Env(), max_deg=(60.0, 60.0), beam=4, n_rot=600, log=lambda *a: None)
    d = [cKDTree(t).query(x)[0].mean() for t, x in zip(truth, X)]
    assert max(d) < 1.0


def test_reseat_phalanges_restores_the_source_contact():
    from scripts.zanatomy import q205_hand as Q5
    from scripts.zanatomy.q191_hand import kabsch, apply_T
    rng = np.random.default_rng(1)
    mc_raw = np.c_[rng.uniform(-4, 4, 300), rng.uniform(0, 40, 300), rng.uniform(-4, 4, 300)]
    ph_raw = np.c_[rng.uniform(-3, 3, 300), rng.uniform(40.1, 70, 300), rng.uniform(-3, 3, 300)]
    R = np.array([[0.0, -1, 0], [1, 0, 0], [0, 0, 1]])
    mc_v = 1.05 * mc_raw @ R.T + [10, 20, 5]
    ph_far = ph_raw + [80, 0, 0]                                         # Q195: the phalanx 80 mm off its metacarpal

    class M:
        r = {"mc": mc_raw, "ph": ph_raw}

        def mc(self, o):
            return "mc"

        def phal(self, o):
            return ["ph"]

    class S:
        v = {"mc": mc_v, "ph": ph_far}
        pts = {"mc": mc_v.copy(), "ph": ph_far.copy()}

    rep = Q5.reseat_phalanges(None, M(), S(), "first", log=lambda *a: None)
    assert rep["gap_before_mm"] > 30 and rep["gap_after_mm"] < 3.0         # random point clouds: the nearest-sample distance is ~sampling pitch


def test_shoulder_field_follows_the_humerus_and_vanishes_far_away():
    from scripts.zanatomy import q205_shoulder as Sh
    h0 = np.c_[np.zeros(200), np.linspace(0, 100, 200), np.zeros(200)]
    h1 = h0 + np.array([10.0, 0, 0])
    far = np.c_[np.full(300, 300.0), np.linspace(0, 100, 300), np.zeros(300)]
    by = {"humerus_l": {"v": h1, "cat": "bone"}, "scapula_l": {"v": far, "cat": "bone"}}
    F = Sh.ShoulderField("l", by, h0, np.array([0.0, 100.0, 0.0]))
    assert abs(np.linalg.norm(F(np.array([[1.0, 50.0, 0.0]]))[0]) - 10.0) < 3.0      # next to the moved bone: most of its displacement
    assert np.linalg.norm(F(np.array([[300.0, 50.0, 0.0]]))[0]) < 1.0                # next to a fixed bone: ~0


# ------------------------------------------------------------------------------------------------ committed data
def test_hand_evidence_files_have_both_sides_in_atlas_mm():
    ct = np.load(REPO / "data" / "derived" / "Q205_his_hand_ct_evidence.npz")
    lab = np.load(REPO / "data" / "derived" / "Q205_his_hand_labels.npz")
    for s, sign in (("r", 1), ("l", -1)):
        P_ = ct[f"ct_{s}"]
        assert len(P_) > 20000 and sign * P_[:, 0].mean() > 0 and 30 <= P_[:, 1].min() and P_[:, 1].max() <= 120
        assert len(lab[f"mc_{s}"]) > 5000


@pytest.mark.skipif(not (REPO / "data" / "derived" / "Q205_hand_fit_r.json").exists(), reason="fit reports not committed")
def test_male_hand_fit_reports_improve_evidence_agreement_and_close_the_thumb():
    for s in "rl":
        f = json.loads((REPO / "data" / "derived" / f"Q205_hand_fit_{s}.json").read_text())
        pol = json.loads((REPO / "data" / "derived" / f"Q205_hand_polish_{s}.json").read_text())
        assert f["reseat_thumb"]["gap_after_mm"] < 1.0
        assert pol["evidence_after"]["hand"]["evidence_within_1.5mm_of_a_Z_bone_pct"] > f["evidence_before"]["hand"]["evidence_within_1.5mm_of_a_Z_bone_pct"] + 25
        assert pol["thumb_gap_after_mm"] < 1.0


# ------------------------------------------------------------------------------------------------ final pages
@pytest.mark.parametrize("which", ["male", "female"])
def test_no_card_name_equals_its_raw_id(which):
    d, stem = PAGES[which]
    if not (d / f"{stem}.html").exists():
        pytest.skip(f"{which} Q205 page not built here")
    man, _ = P.load_page(d, stem)
    # a raw-id card name = the id with its side suffix as the name ("pronator teres l"); single-word names equal to their id up to case ("Coccyx") are legitimate
    bad = [m["id"] for m in man["meshes"] if norm(m["name"]) == norm(m["id"]) and re.search(r"_[lr]$", m["id"]) and not m["id"].startswith("zan_")]
    assert not bad, bad[:10]
    # every card that exists in the clean base page carries the same name
    bd, bstem = BASES[which]
    bman, _ = P.load_page(bd, bstem)
    be = {m["id"]: m for m in bman["meshes"]}
    wrong = [m["id"] for m in man["meshes"] if m["id"] in be and m["name"] != be[m["id"]]["name"]]
    assert not wrong, wrong[:10]


@pytest.mark.parametrize("which", ["male", "female"])
def test_matched_cards_carry_atlas_facts(which):
    d, stem = PAGES[which]
    if not (d / f"{stem}.html").exists():
        pytest.skip(f"{which} Q205 page not built here")
    man, _ = P.load_page(d, stem)
    bd, bstem = BASES[which]
    bman, _ = P.load_page(bd, bstem)
    be = {m["id"]: m for m in bman["meshes"]}
    missing = [m["id"] for m in man["meshes"] if m["id"] in be and "origin" in (be[m["id"]].get("rec") or {}) and "origin" not in (m.get("rec") or {})]
    assert not missing, missing[:10]


@pytest.mark.parametrize("which", ["male", "female"])
def test_scope_only_listed_structures_changed(which):
    d, stem = PAGES[which]
    rep = REPO / "data" / "derived" / f"Q205_ship_diff_{which}.json"
    if not (d / f"{stem}.html").exists() or not rep.exists():
        pytest.skip("page / ship diff not built here")
    r = json.loads(rep.read_text())
    assert r["geometry_changed_but_not_listed"] == []
    assert r["added"] == [] and r["removed"] == []


@pytest.mark.parametrize("which", ["male", "female"])
def test_thumb_chain_is_continuous_on_the_page(which):
    from scipy.spatial import cKDTree
    d, stem = PAGES[which]
    if not (d / f"{stem}.html").exists():
        pytest.skip("page not built here")
    man, blob = P.load_page(d, stem)
    S = P.decode(man, blob, only=lambda m: m["sys"] == "bone" and "first" in m["id"] and "hand" in m["id"] or m["id"].startswith("zan_first_metacarpal"))
    for s in "lr":
        mc, ph = S.get(f"zan_first_metacarpal_bone_{s}"), S.get(f"zan_proximal_phalanx_of_first_finger_of_hand_{s}")
        if mc is None or ph is None:
            continue
        g = cKDTree(mc["v"]).query(ph["v"])[0].min()
        assert g < 3.0, (s, g)
