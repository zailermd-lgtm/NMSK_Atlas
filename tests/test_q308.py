"""Q308: the structures this round BUILT, and the guard Q306's own guard could not be.

Two jobs:
  (1) every structure Q308 ships is badged rule-based, has a recorded volume and at least one citation;
  (2) no `cited_but_not_shipped` entry on any page denies a structure that is PRESENT on that page -- checked
      against the six pages' own structure lists (name, Latin AND id), not through the alias table. Q306's
      guard asked the alias table, so it could not see three structures that shipped under their TA names
      while their cards said they were missing.
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
for p in (REPO / "scripts/anatomy/q308", REPO / "scripts/anatomy/q298", REPO / "scripts/anatomy/q241"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import model as _M  # noqa: E402

# Asked for, not hardcoded: a literal baseline in a test goes stale the moment a round lands, and the test
# then keeps asserting about an old build while reporting success.
SRC = _M.build_root()
REPORT = REPO / "data/derived/Q308_built_structures.json"
PAGES = ["own_m", "own_f", "base_m", "base_f", "comb_m", "comb_f"]


@pytest.fixture(scope="module")
def built():
    assert REPORT.exists(), f"{REPORT} is missing -- run scripts/anatomy/q308/build308.py build"
    return json.loads(REPORT.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def lit():
    import lit308
    return lit308


def shipped(built, key):
    """{id: stats} for the structures Q308 actually ships on this page (refusals excluded)."""
    return {k: v for k, v in built[key].items()
            if not k.startswith("_") and k != "frame" and isinstance(v, dict) and not v.get("refused")}


# ------------------------------------------------------------------ (1) every built structure is accountable
def test_every_built_structure_has_a_recorded_volume(built):
    bad = []
    for key in PAGES:
        for sid, st in shipped(built, key).items():
            v = st.get("volume_cm3")
            if not isinstance(v, (int, float)) or not (v > 0):
                bad.append((key, sid, v))
    assert not bad, bad


def test_every_built_structure_volume_matches_its_analytic_volume(built):
    """A reported volume must be trustworthy. The mesh volume is checked against the independent analytic
    (frustum / elliptical-band) volume; per-vertex pushing once halved one psoas minor's volume and this is
    the check that refused it."""
    bad = []
    for key in PAGES:
        for sid, st in shipped(built, key).items():
            rel, tol = st.get("volume_mesh_vs_analytic_rel"), st.get("volume_check_tol")
            if rel is None or tol is None or rel > tol:
                bad.append((key, sid, rel, tol))
    assert not bad, bad


def test_every_built_structure_has_at_least_one_citation(built, lit):
    """Every family Q308 builds must name at least one source that carries a PMID or a DOI."""
    fam = {"coracoacromial_ligament": ["vonschroeder2001", "hu2009"],
           "lacn_anterior_branch": ["khadanovich2023", "qawasmi2024"],
           "lacn_posterior_branch": ["khadanovich2023", "qawasmi2024"],
           "psoas_minor": ["raja2026", "patra2024"],
           "anterolateral_ligament": ["kosy2016", "rustagi2019"]}
    bad = []
    for key in PAGES:
        for sid in shipped(built, key):
            base = sid.rsplit("_", 1)[0]
            keys = fam.get(base)
            if not keys:
                bad.append((key, sid, "no citation list for this family"))
                continue
            for ck in keys:
                c = lit.CITE.get(ck)
                if not c or not (c.get("pmid") or c.get("doi")):
                    bad.append((key, sid, ck, "source carries neither a PMID nor a DOI"))
    assert not bad, bad


def test_every_citation_in_lit308_carries_an_identifier_and_a_quote(lit):
    bad = [k for k, c in lit.CITE.items()
           if not (c.get("pmid") or c.get("doi")) or not c.get("quotes")]
    assert not bad, bad


def test_a_source_without_a_doi_says_so(lit):
    """Hu 2009 has no DOI assigned. A missing identifier must be stated, not left to look like an omission."""
    for k, c in lit.CITE.items():
        if c.get("doi") is None:
            assert c.get("doi_note"), f"{k} has no DOI and no doi_note saying why"


def test_every_refusal_is_recorded_with_a_reason(built):
    bad = []
    for key in PAGES:
        for sid, st in built[key].items():
            if sid.startswith("_") or sid == "frame" or not isinstance(st, dict):
                continue
            if st.get("refused") and not st.get("reason"):
                bad.append((key, sid))
    assert not bad, bad


def test_nothing_built_claims_to_be_measured_on_this_body(built):
    """Q297's rule: a rule-based structure may never carry the 'Measured on this body' claim."""
    blob = json.dumps(built, ensure_ascii=False).lower()
    assert "measured on this body" not in blob


def test_psoas_minor_is_hidden_by_default_everywhere_it_ships(built):
    """It is absent in roughly half of people, so the page must not assert it is present in THESE bodies."""
    for key in PAGES:
        for sid, st in shipped(built, key).items():
            if sid.startswith("psoas_minor"):
                assert st.get("hidden_by_default") is True, (key, sid)


def test_the_anterolateral_ligament_is_marked_contested(built, lit):
    for key in PAGES:
        for sid, st in shipped(built, key).items():
            if sid.startswith("anterolateral_ligament"):
                assert st.get("contested") is True, (key, sid)
    for k in ("all_femoral_origin", "all_width", "all_existence"):
        d = lit.DISAGREE[k]
        assert d["shipped"] and d["against"] and len(d["sources"]) >= 2, k


def test_the_lacn_branches_reach_the_wrist(built):
    """Q307's finding was that the trunk stops 53.8-73.5 mm short of the distal radius. Whatever Q308 ships
    must actually close that, or it has not done its job."""
    for key in PAGES:
        for sid, st in shipped(built, key).items():
            if sid.startswith("lacn_"):
                assert st["short_of_distal_radius_mm"] <= 20.0, (key, sid, st["short_of_distal_radius_mm"])


def test_the_lacn_branches_are_not_buried_in_the_brachioradialis(built, lit):
    """Khadanovich 2023: 'less than 1.8 mm from the LACN'. A cutaneous nerve hugs that border; it is not
    inside the belly (Q307 section 5)."""
    cap = lit.LIT["lacn_br_medial_border_max_mm"][0]
    for key in PAGES:
        for sid, st in shipped(built, key).items():
            if sid.startswith("lacn_"):
                assert st["max_depth_in_brachioradialis_mm"] <= cap, (key, sid)


def test_both_sides_or_neither(built):
    """Q307's gate 3, widened: a one-sided bilateral structure tells the reader the other side has none."""
    bad = []
    for key in PAGES:
        sh = shipped(built, key)
        for sid in sh:
            if sid.endswith("_l") and sid[:-2] + "_r" not in sh:
                bad.append((key, sid))
            if sid.endswith("_r") and sid[:-2] + "_l" not in sh:
                bad.append((key, sid))
    assert not bad, bad


def test_nothing_built_penetrates_bone(built):
    """After the centreline is cleared and the rings lifted, no shipped structure may be inside a bone."""
    bad = []
    for key in PAGES:
        for sid, st in shipped(built, key).items():
            for k, v in st.items():
                if k.startswith("min_signed_dist_to_") and k.endswith("_after_mm") and v < -0.01:
                    bad.append((key, sid, k, v))
    assert not bad, bad


def test_every_built_mesh_is_watertight(built):
    bad = [(k, sid) for k in PAGES for sid, st in shipped(built, k).items() if not st.get("watertight")]
    assert not bad, bad


def test_the_declared_modelling_choices_are_declared(lit):
    """Where no caliper was found, the number is a MODELLING CHOICE and must say so (Q248's precedent)."""
    for k in ("cal_cross_section", "all_cross_section", "lacn_branch_calibre", "psoas_minor_section"):
        t = lit.MODELLING_CHOICES[k].lower()
        assert "modelling choice" in t, k


def test_what_was_not_built_says_why_and_names_its_evidence(lit):
    for k, v in lit.NOT_BUILT.items():
        assert v["what"] and len(v["why"]) > 80, k
    assert "zygote" in lit.LICENCE_BLOCKED.lower() and "biodigital" in lit.LICENCE_BLOCKED.lower()


# --------------------------------- (2) THE GUARD: presence on the page, not searchability through the aliases
def test_no_absence_entry_denies_a_structure_that_is_on_the_page():
    """THE guard. Q306's version asked the alias table whether the query resolved; this one reads the page's own
    structure list -- name, Latin and id. It is what found the pubic symphysis, the retrocalcaneal bursa and the
    TFCC being denied on three cards while their meshes were on screen. It must never be weakened back."""
    import absence308 as A
    a = A.audit(SRC)
    offenders = {r["name"]: r["present_on"] for r in a["rows"] if not r["really_absent"]}
    allowed = {"Pubic symphysis", "Retrocalcaneal bursa", "Triangular fibrocartilage complex"}
    assert set(offenders) <= allowed, offenders
    syn = json.loads((REPO / "data/anatomy/synonyms_q306.json").read_text(encoding="utf-8"))
    for e in syn["cited_but_not_shipped"]:
        if e["name"] in offenders:
            assert e.get("corrected_by") == "Q308", (
                f"{e['name']} is present on {sorted(offenders[e['name']])} and its entry is NOT corrected")
            assert "CORRECTED" in e["why"], e["name"]


def test_the_three_corrected_names_now_reach_their_shipping_meshes():
    """The clinical name a clinician types must land on the mesh that really ships."""
    import absence308 as A
    want = {"pubic symphysis": "pubic_symphysis_disc",
            "retrocalcaneal bursa": "zan_subtendinous_calcaneal_bursa_l",
            "TFCC": "zan_articular_disc_of_distal_radio_ulnar_joint_l"}
    syn = json.loads((REPO / "data/anatomy/synonyms_q306.json").read_text(encoding="utf-8"))
    forms = {s.lower() for e in syn["entries"] for s in (e.get("syn") or [])}
    for term in want:
        assert term.lower() in forms, f"no alias entry carries the clinical form {term!r}"
    idx = A.page_name_index("base_m", SRC)
    for term, sid in want.items():
        hits = A.present(term, idx) or A.present(
            {"pubic symphysis": "interpubic fibrocartilaginous disc",
             "retrocalcaneal bursa": "subtendinous calcaneal bursa",
             "TFCC": "articular disc of distal radio-ulnar joint"}[term], idx)
        assert sid in hits, (term, sid, hits[:4])


def test_the_other_absence_entries_are_still_genuinely_absent():
    """16 of the 19 are real. If one of them ever starts shipping, this fails loudly instead of the page
    quietly lying the other way."""
    import absence308 as A
    a = A.audit(SRC)
    real = [r["name"] for r in a["rows"] if r["really_absent"]]
    for n in ("Psoas minor", "Coracoacromial ligament", "Anterolateral ligament of the knee",
              "Nail bed", "Digital pulp", "Female perineal skin"):
        assert n in real, n
