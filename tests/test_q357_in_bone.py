"""Q357: vessels / nerves inside bone on the Base pages -- allow-list, report and (when applied) page checks. Fast; page checks skip
when the page or the Q357 application is absent."""
import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "anatomy" / "q357"))
ALLOW = REPO / "data/anatomy/q357_in_bone_allow.json"
REPORT = REPO / "data/derived/Q357_in_bone_report.json"
SCRIPT = REPO / "scripts/anatomy/q357/conform_in_bone_q357.py"
PAGES = {"atlas_viewer_zan_atlas": REPO / "build/q309/viewer_zan_atlas", "atlas_viewer_base_female": REPO / "build/q309/viewer_base_female"}


@pytest.fixture(scope="module")
def Q():
    pytest.importorskip("trimesh")
    import conform_in_bone_q357 as q
    return q


def test_allow_list_entries_are_cited_and_compile():
    d = json.loads(ALLOW.read_text(encoding="utf-8"))
    assert set(d["sources"]) == {"Y", "M", "G"}
    keys = set()
    for e in d["allow"]:
        re.compile(e["ids"]); re.compile(e["bones"])
        assert e["passage"] and e["cite"], e["key"]
        for b, p in e["cite"]:
            assert b in d["sources"] and re.fullmatch(r"\d{1,3}", p), (e["key"], b, p)
        assert e["key"] not in keys
        keys.add(e["key"])
    for e in d["unsure"]:
        re.compile(e["ids"]); re.compile(e["bones"])
        assert e["reason"], e["key"]
    re.compile(d["out_of_scope"]["ids"])


@pytest.mark.parametrize("sid,bone,want", [
    ("zan_internal_carotid_artery_l", "temporal_l", "allow"),
    ("zan_internal_carotid_artery_r", "sphenoid", "allow"),
    ("zan_facial_nerve_vii_r", "temporal_r", "allow"),
    ("zan_hypoglossal_n_l", "occipital", "allow"),
    ("zan_vagus_nerve_x_l", "occipital", "allow"),
    ("zan_vagus_nerve_x_l", "vert_t5", "conform"),
    ("zan_inferior_alveolar_artery_r", "mandible", "allow"),
    ("zan_obturator_n_l", "hip_bone_l", "allow"),
    ("zan_pudendal_n_r", "hip_bone_r", "allow"),
    ("zan_sigmoid_sinus_l", "temporal_l", "allow"),
    ("zan_vertebral_artery_r", "vert_c4", "allow"),
    ("zan_right_testicular_vein", "hip_bone_r", "conform"),
    ("zan_posterior_circumflex_humeral_artery_l", "humerus_l", "conform"),
    ("zan_calcaneal_branches_of_fibular_artery_r", "calcaneus_r", "conform"),
    ("zan_internal_thoracic_veins_l", "sternum", "conform"),
    ("zan_maxillary_artery_l", "maxilla_l", "unsure"),
    ("zan_trigeminal_n_v3_inferior_alveolar_branch_l", "head_misc_lower_lateral_incisor_l", "unsure"),
])
def test_classification(Q, sid, bone, want):
    assert Q.Allow().classify(sid, bone)[0] == want


def test_brain_and_ear_parts_out_of_scope(Q):
    a = Q.Allow()
    assert a.out_of_scope("zan_tuber_of_vermis", "nerve") and a.out_of_scope("zan_tympanic_membrane_l", "nerve")
    assert not a.out_of_scope("zan_superior_cerebellar_artery_l", "vessel")
    assert not a.out_of_scope("zan_facial_nerve_vii_l", "nerve")


def test_bone_labels(Q):
    assert Q.bone_label("vert_t5") == "T5 vertebra"
    assert Q.bone_label("rib_2_l") == "left 2nd rib"
    assert Q.bone_label("hip_bone_r") == "right hip bone"
    assert Q.bone_label("ph_foot_3_prox_r") == "right proximal phalanx of the 3rd toe"


def test_parameters_within_brief():
    s = SCRIPT.read_text(encoding="utf-8")
    cap = float(re.search(r"^CAP = ([\d.]+)", s, re.M).group(1))
    assert 0 < cap <= 10.0
    for t in (s, ALLOW.read_text(encoding="utf-8")):
        assert not re.search(r"claude|opus|sonnet|haiku|\bgpt", t, re.I)


def test_report_consistent():
    if not REPORT.exists():
        pytest.skip("no Q357 report yet")
    r = json.loads(REPORT.read_text(encoding="utf-8"))
    assert r["allow_list"]["allow"], "the report carries the allow-list with its citations"
    for stem, p in r["pages"].items():
        cap = p["parameters"]["cap_mm"]
        assert cap <= 10.0
        for k in p["geometry_changed"]:
            s = p["structures"][k]
            assert s["decision"].startswith("conformed"), k
            assert s["displacement"]["max_mm"] <= cap, k
            assert all(v["ok"] for v in s["guards"].values() if isinstance(v, dict)), k
            assert s["card"].startswith("Q357:"), k
        for k, why in p["left_as_is"].items():
            assert why.startswith("left:"), k
        assert p["screen_after"]["vertices"] <= p["screen_before"]["vertices"]


@pytest.mark.parametrize("stem", sorted(PAGES))
def test_applied_page_keeps_counts(stem):
    d = PAGES[stem]
    html = d / f"{stem}.html"
    bak = d / f"{stem}.html.q357"
    if not html.exists() or not bak.exists():
        pytest.skip("page absent or Q357 not applied")
    lit = re.compile(r"^window\.__ANATOMY_MANIFEST__=(.*);$", re.M)
    m1 = json.loads(lit.search(html.read_text(encoding="utf-8")).group(1))
    m0 = json.loads(lit.search(bak.read_text(encoding="utf-8")).group(1))
    a = {m["id"]: (m["vc"], m["ic"]) for m in m0["meshes"]}
    b = {m["id"]: (m["vc"], m["ic"]) for m in m1["meshes"]}
    # Q357's promise: the structures IT moved keep their vertex / triangle counts, and it removed nothing. Later rounds may add
    # structures (Q358 the rule-based perineal skin, Q365 nerves) or re-cut one they own (Q358 skin_vulva_cvh, Q365 the maxillary
    # nerve's split): those are not Q357's and are not compared.
    assert set(a) <= set(b), sorted(set(a) - set(b))[:5]
    moved = set(a)
    if REPORT.exists():
        rep0 = json.loads(REPORT.read_text(encoding="utf-8"))["pages"].get(stem)
        if rep0 and rep0.get("written"):
            moved = set(rep0["geometry_changed"])
    assert {i: a[i] for i in moved} == {i: b[i] for i in moved}
    noted = {m["id"] for m in m1["meshes"] if "Q357:" in ((m.get("rec") or {}).get("procedural_badge") or "")}
    if REPORT.exists():
        rep = json.loads(REPORT.read_text(encoding="utf-8"))["pages"].get(stem)
        if rep and rep.get("written"):
            assert noted == set(rep["geometry_changed"])
