"""Q350: three muscle-record contradictions found by the Q348 book pass (docs/Q348_reference_pass.md §2.7 items 1-3) are corrected
in the records, wired both ways in the nerve tree, consistent with the innervation groups, and carried to built pages by the
manifest patch (scripts/zanatomy/patch_manifest_nerves_q350.py)."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
MUS = REPO / "data/muscles"
SIDES = ("r", "l")
SPS = ["intercostal_n_t2_muscular", "intercostal_n_t3_muscular", "intercostal_n_t4_muscular", "intercostal_n_t5_muscular"]
LPD, LPS = "lateral_plantar_n_deep_branch", "lateral_plantar_n_superficial_branch"
FORBIDDEN = ("ultrasound", "hounsfield", "t1_se", "imaging_tissues", "tissue table", "nmskultrasound", "acoustic", "mrayl", "b-mode")
PAGES = {"base_m": REPO / "build/q309/viewer_zan_atlas/atlas_viewer_zan_atlas.html",
         "base_f": REPO / "build/q309/viewer_base_female/atlas_viewer_base_female.html"}
# record -> (nerve list, root_levels, Mannan 2017 page)
EXPECT = {
    "serratus_posterior_superior": (SPS, "T2-T5", 407),
    "pectoralis_minor": (["medial_pectoral_n", "lateral_pectoral_n"], "C8-T1", 106),   # reviewed range kept; book C6-C8 divergent
    "plantar_interossei": ([LPD, LPS], "S1-S3", 291),
    "dorsal_interossei_foot": ([LPD, LPS], "S1-S3", 295),
}


def rec(mid, s):
    (p,) = MUS.rglob(f"{mid}_{s}.json")
    return json.loads(p.read_text(encoding="utf-8"))


def tree():
    out = {}
    for p in sorted((REPO / "data/nerves").glob("*.json")):
        for e in json.loads(p.read_text(encoding="utf-8")):
            if isinstance(e, dict) and "id" in e:
                out[e["id"]] = e
    return out


@pytest.mark.parametrize("mid", sorted(EXPECT))
def test_record_nerve_roots_and_citation(mid):
    nerves, roots, page = EXPECT[mid]
    for s in SIDES:
        r = rec(mid, s)
        inn = r["innervation"]
        assert inn["nerve"] == nerves and inn["root_levels"] == roots, (mid, s)
        assert "Mannan" in inn["source"] and f"p. {page}" in inn["source"] and inn["note"].startswith("Q350")
        assert f"p. {page}" in r["source"] and "Mannan" in r["source"]           # the record's own citation list
        for c in r["functional_compartments"]:
            assert c["innervation_branch_ids"] == nerves, (mid, s)
        txt = json.dumps(inn).lower()
        assert not any(w in txt for w in FORBIDDEN)


def test_interossei_exception_names_the_book_muscle():
    assert "3rd plantar interosseous" in rec("plantar_interossei", "r")["innervation"]["note"]
    assert "4th dorsal interosseous" in rec("dorsal_interossei_foot", "r")["innervation"]["note"]


def test_pectoralis_minor_keeps_the_medial_pectoral_first_and_the_reviewed_range():
    inn = rec("pectoralis_minor", "r")["innervation"]
    assert inn["nerve"][0] == "medial_pectoral_n" and inn["root_levels"] == "C8-T1"
    assert "C6-C8" in inn["note"] and "not adopted" in inn["note"] and "communicating loop" in inn["note"]


def test_nerve_tree_lists_the_compartments_back():
    t = tree()
    for s in SIDES:
        assert f"pectoralis_minor_{s}_main" in t["lateral_pectoral_n"]["targets"]
        assert f"pectoralis_minor_{s}_main" in t["medial_pectoral_n"]["targets"]
        for m in ("plantar_interossei", "dorsal_interossei_foot"):
            assert f"{m}_{s}_main" in t[LPS]["targets"] and f"{m}_{s}_main" in t[LPD]["targets"]
        sps = f"serratus_posterior_superior_{s}_main"
        supplying = sorted(k for k, e in t.items() if sps in (e.get("targets") or []))
        assert supplying == sorted(SPS), supplying


def test_innervation_groups_agree_with_the_records():
    g = json.loads((REPO / "data/anatomy/innervation_groups_q342.json").read_text(encoding="utf-8"))["muscles"]
    for mid, (nerves, roots, _page) in EXPECT.items():
        assert g[mid]["nerves"] == nerves, mid
    assert g["serratus_posterior_superior"]["roots_text"].startswith("T2-T5")
    assert g["serratus_posterior_superior"]["corrected_q348"]["was"] == "T1-T4"
    pm = g["pectoralis_minor"]
    assert pm["roots_text"] == "C8-T1" and pm["motor_levels"] == ["C8", "T1"] and pm["book_check_q348"]["status"] == "differs"
    q = json.loads((REPO / "data/anatomy/innervation_q322.json").read_text(encoding="utf-8"))["muscles"]["pectoralis_minor"]
    assert [n["id"] for n in q["nerve"]] == ["medial_pectoral_n", "lateral_pectoral_n"] and q["roots"]["adopted_text"] == "C8-T1"


def _patch():
    p = REPO / "scripts/zanatomy/patch_manifest_nerves_q350.py"
    spec = importlib.util.spec_from_file_location("p350", p)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def test_manifest_patch_replaces_only_the_nerve_keys():
    m = _patch()
    recs = m._records()
    man = {"meshes": [
        {"id": "pectoralis_minor_r", "rec": {"folder": "trunk", "name": "x", "nerve": ["medial_pectoral_n"], "source": "old",
                                             "compartments": [{"id": "pectoralis_minor_r_main", "nerves": ["medial_pectoral_n"], "pcsa": 1}]}},
        {"id": "lateral_pectoral_n_l", "rec": {"folder": "nerves", "targets": ["a"]}},
        {"id": "deltoid_r", "rec": {"folder": "upper_limb", "nerve": ["axillary_n"]}},
    ]}
    html = "<script>" + m.KEY + json.dumps(man, separators=(",", ":")) + ";</script>"
    new, ids = m.patch_text(html, recs)
    assert ids == ["pectoralis_minor_r", "lateral_pectoral_n_l"]
    out = json.loads(new[new.index(m.KEY) + len(m.KEY):-len(";</script>")])["meshes"]
    assert out[0]["rec"]["nerve"] == ["medial_pectoral_n", "lateral_pectoral_n"] and "Mannan" in out[0]["rec"]["source"]
    assert out[0]["rec"]["compartments"][0] == {"id": "pectoralis_minor_r_main", "nerves": ["medial_pectoral_n", "lateral_pectoral_n"], "pcsa": 1}
    assert "pectoralis_minor_l_main" in out[1]["rec"]["targets"] and out[2] == man["meshes"][2]
    assert m.patch_text(new, recs) == (new, [])                                   # idempotent


@pytest.mark.parametrize("page", sorted(PAGES))
def test_built_base_pages_need_exactly_these_patches(page):
    """build/ is read only here: the patch is computed in memory. Until the next regen runs the patch, the built page still shows the
    old records; afterwards this list is empty."""
    if not PAGES[page].exists():
        pytest.skip("build/ not restored")
    m = _patch()
    _new, ids = m.patch_text(PAGES[page].read_text(encoding="utf-8"), m._records())
    want = {f"{x}_{s}" for x in (*EXPECT, "lateral_pectoral_n") for s in SIDES}
    assert set(ids) in (want, set())
