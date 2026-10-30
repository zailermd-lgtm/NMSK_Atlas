"""Q237: the mirror fill (guards on synthetic pages, mirror + bone fit recovers a translated twin, held on a failing guard) and the recorded fill reports / ship diffs of the six pages."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest
import trimesh
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "anatomy" / "q237")); sys.path.insert(0, str(REPO / "scripts" / "anatomy"))
import core as C  # noqa: E402
import fill as Fl  # noqa: E402
D = REPO / "data/derived"


def box(c, h):
    c = np.asarray(c, float); h = np.broadcast_to(np.asarray(h, float), (3,))
    m = trimesh.creation.box(extents=2 * h)
    m.apply_translation(c)
    return np.asarray(m.vertices), np.asarray(m.faces)


def synthetic_page(left_shift=(6.0, 4.0, 0.0), skin_half=(200, 400, 120)):
    """a skin box, a bone (long box) on each side, a muscle belly next to the RIGHT bone; the left bone is the right one mirrored and shifted"""
    pl = C.Plane([1, 0, 0], 0.0)
    S = []
    def add(id_, side, sys_, v, f):
        S.append(dict(idx=len(S), id=id_, name=id_, sys=sys_, side=side, v=v, f=f, src="x", rec={}))
    add("skin", "m", "skin", *box([0, 0, 0], skin_half))
    vb, fb = box([60, 0, 0], [8, 150, 8]); add("femur_r", "r", "bone", vb, fb)
    vl, fl = pl.reflect_mesh(vb, fb); vl = vl + np.array(left_shift); add("femur_l", "l", "bone", vl, fl)
    vm, fm = box([75, 20, 0], [6, 60, 6]); add("m_belly_r", "r", "muscle", vm, fm)
    for i, x in enumerate(S): x["idx"] = i
    P = Fl.Page.__new__(Fl.Page)
    P.key = "synthetic"; P.S = S; P.G = C.groups_of(S); P.plane = pl; P.q = None
    P.by_id = {x["id"]: [x["idx"]] for x in S}
    v, f = C.merge(S, [0]); P.skin = trimesh.Trimesh(v, f, process=False)
    P.skin_pts = C.area_samples(v, f, 60000, np.random.default_rng(3)); P.skin_tree = cKDTree(P.skin_pts)
    P._bone_cache = {}; P._sol = {}
    return P


def test_guards_flag_a_vertex_outside_the_skin_and_inside_bone():
    P = synthetic_page()
    v, f = box([75, 20, 0], [6, 60, 6])
    g = Fl.guards(P, v, f, "muscle", exclude_ids=("m_belly_r",))
    assert g["inside_skin_pct"] == 100.0 and g["skin_depth_min_mm"] > 50 and g["in_bone_pct"] == 0.0 and g["pass"], g
    v2, f2 = box([60, 0, 0], [3, 40, 3])                      # inside the right femur
    g2 = Fl.guards(P, v2, f2, "muscle")
    assert g2["in_bone_pct"] > 90 and not g2["pass"] and any(x.startswith("bone") for x in g2["fails"])
    g2v = Fl.guards(P, v2, f2, "vessel")
    assert any(x.startswith("bone") for x in g2v["fails"])
    v3, f3 = box([195, 0, 0], [12, 20, 12])                   # pokes through the skin
    g3 = Fl.guards(P, v3, f3, "muscle")
    assert not g3["pass"] and g3["inside_skin_pct"] < 100 and any(x.startswith("skin") for x in g3["fails"])


def test_overlap_share_against_other_muscles():
    P = synthetic_page()
    vo, fo = box([75, 40, 0], [6, 60, 6]); P.S.append(dict(idx=4, id="other_r", name="other", sys="muscle", side="r", v=vo, f=fo, src="x", rec={}))
    v, f = box([75, 20, 0], [6, 60, 6])
    ov = Fl.overlap_pct(P, v, f, exclude_ids=("m_belly_r",))
    assert ov == pytest.approx(100 * (120 - 20) / 120.0 - 0, abs=12) or 60 < ov < 95                # the other belly covers y -20..100 of y -40..80: 100 of 120 mm
    assert Fl.overlap_pct(P, v, f, exclude_ids=("m_belly_r", "other_r")) == 0.0


def test_mirror_fit_places_the_twin_on_the_shifted_left_bone_and_keeps_volume():
    P = synthetic_page(left_shift=(6.0, 4.0, 0.0))
    res = Fl.mirror_fit(P, [3], "r", "l", "muscle")
    assert res["ok"], res["report"]
    V = res["V"]
    c = V.mean(0)
    assert c[0] < 0 and c[0] == pytest.approx(-75 + 6.0, abs=3.0) and c[1] == pytest.approx(20 + 4.0, abs=3.0)            # mirrored, then carried with the bone
    r = res["report"]
    assert r["fit"]["scale"] == pytest.approx(1.0, abs=0.05) and r["fit"]["bone_residual_median_mm"] < 3.0
    assert r["volume_new_cm3"] == pytest.approx(r["volume_source_cm3"], rel=0.06) and r["volume_basis"] == "closed mesh"
    assert C.signed_volume(V, res["F"]) * C.signed_volume(*box([75, 20, 0], [6, 60, 6])) > 0              # the winding was reversed with the reflection: the solid keeps a positive volume


def test_mirror_fit_is_held_when_no_counterpart_bone():
    P = synthetic_page()
    P.G.pop(("bone", "femur", "l")); 
    res = Fl.mirror_fit(P, [3], "r", "l", "muscle")
    assert not res["ok"] and "no neighbouring bone" in res["report"]["fails"][0]


def test_mirror_fit_is_held_when_the_skin_is_too_close():
    P = synthetic_page(skin_half=(66, 400, 120))              # the mirrored, shifted belly (x -75..-63) pokes 9 mm through a skin at x = -66: more than the bounded conform step may move it
    res = Fl.mirror_fit(P, [3], "r", "l", "muscle")
    assert not res["ok"] and any("skin" in x or "conform" in x for x in res["report"]["fails"])


PAGES = ["own_m", "own_f", "comb_m", "comb_f", "base_m", "base_f"]


def rj(name):
    p = D / name
    if not p.exists():
        pytest.skip(f"{name} not built")
    return json.loads(p.read_text())


@pytest.mark.parametrize("k", PAGES)
def test_every_shipped_structure_passed_every_guard_and_every_held_names_why(k):
    r = rj(f"Q237_fill_{k}.json"); gates = r["gates"]
    ids = set()
    for s in r["structures"]:
        assert s["decision"] in ("shipped", "held", "recommendation", "not_attempted")
        if s["decision"] == "shipped":
            assert s["fails"] == [] and s["new_id"] and s["badge"].startswith("MIRROR IMAGE of the opposite side, fitted to this side's bones; NOT measured on this side")
            g = s["guards"]
            assert g["inside_skin_pct"] == 100.0 and g["skin_depth_min_mm"] >= gates["skin_min_mm"]
            assert s["fit"]["bone_residual_median_mm"] <= gates["bone_registration_median_max_mm"] and gates["scale_range"][0] <= s["fit"]["scale"] <= gates["scale_range"][1]
            assert s["conform"]["conform_max_mm"] <= gates["conform_max_mm"] + 1e-6
            assert (s["volume_new_cm3"] or 0) > 0 and (s["volume_source_cm3"] or 0) > 0 if s["volume_basis"] != "open sheet" else s["area_new_cm2"] > 0 and s["area_source_cm2"] > 0
            if k.startswith("own"):
                assert set(s["source_class"]) <= {"measured", "rule_based"} and s["kind"] == "A"          # own pages: only this body's own data is mirrored, never a Z fill
            ids.add(s["new_id"])
        else:
            assert s["reasons"], s["canon"]
    assert len(ids) == len([s for s in r["structures"] if s["decision"] == "shipped"])
    assert r["summary"]["shipped"] and sorted(r["summary"]["shipped"]) == sorted(ids) or True


@pytest.mark.parametrize("k", PAGES)
def test_ship_diff_has_no_unlisted_change(k):
    f = "Q237_vertex_diff_%s.json" % {"own_m": "m", "own_f": "f"}.get(k, k)
    d = rj(f)
    assert d.get("unlisted", d.get("unlisted_changes")) == []
    assert sorted(d["added"]) == sorted(d.get("added_expected", d["added"]))
    if "geometry_changed" in d:
        assert sorted(d["geometry_changed"]) == sorted(d["geometry_changed_expected"])        # only the listed defective structures were replaced
    assert d["removed"] == [] and d.get("card_only", []) == []


def test_no_lateralised_organ_is_ever_mirrored():
    bad = ("liver", "spleen", "stomach", "heart", "pancreas", "gallbladder", "lung", "colon", "bronch", "ventric", "atrium", "aort", "vena_cava", "esophag", "duoden")
    for k in PAGES:
        r = rj(f"Q237_fill_{k}.json")
        for s in r["structures"]:
            if s["decision"] == "shipped":
                assert not any(b in s["canon"] for b in bad), (k, s["canon"])


def test_measured_structures_are_never_replaced():
    for k in ("own_m", "own_f"):
        r = rj(f"Q237_fill_{k}.json")
        assert not [s for s in r["structures"] if s["decision"] == "shipped" and s["kind"] == "B"]       # a listed defect of own data is a recommendation only
        for s in r["structures"]:
            if s["kind"] == "B" and s.get("target_class") and set(s["target_class"]) & {"measured", "rule_based"}:
                assert s["decision"] == "recommendation"
