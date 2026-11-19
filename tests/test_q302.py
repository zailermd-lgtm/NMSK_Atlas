"""Q302: assertions for the eight-source survey.

Nothing was imported this round, so there is no geometry and no page change to check: these
assertions pin the *findings* instead, so that a later round cannot quietly contradict them.
Every number comes from data/derived/Q302_source_survey.json, which was written from direct
HTTP / git / S3 reads of the sources themselves; the prose lives in
docs/research/Q302_source_survey.md and is asserted to agree with the JSON.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
EVIDENCE = REPO / "data/derived/Q302_source_survey.json"
SURVEY = REPO / "docs/research/Q302_source_survey.md"


@pytest.fixture(scope="module")
def ev():
    assert EVIDENCE.is_file(), f"missing {EVIDENCE}"
    return json.loads(EVIDENCE.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def doc():
    assert SURVEY.is_file(), f"missing {SURVEY}"
    return SURVEY.read_text(encoding="utf-8")


# ------------------------------------------------------------------ the round shipped no geometry


def test_nothing_was_imported(ev):
    assert ev["verdict"]["imported"] == "nothing"
    assert ev["verdict"]["gaps_closed"] == []
    assert ev["verdict"]["published"] == "nothing"


# ------------------------------------------------------------------ BodyParts3D


def test_bodyparts3d_is_now_cc_by_4(ev, doc):
    """The finding that matters most: DBCLS relicensed BodyParts3D on 2025-02-27."""
    bp = ev["bodyparts3d"]
    assert bp["license"] == "CC BY 4.0 International"
    assert bp["license_page_last_updated"] == "2025-02-27"
    assert "CC Attribution 4.0 International" in bp["required_attribution"]
    assert "2025-02-27" in doc
    assert "CC BY 4.0" in doc


def test_bodyparts3d_has_no_peripheral_limb_nerve(ev):
    """55 'nerve' entries, every one of them cranial or orbital -- so BodyParts3D cannot close gap 1."""
    bp = ev["bodyparts3d"]
    assert bp["nerve_entries_peripheral_limb"] == []
    assert bp["nerve_entries_total"] > 0


def test_bodyparts3d_has_no_nails_and_no_breast(ev):
    bp = ev["bodyparts3d"]
    assert bp["nail_entries"] == []
    assert bp["breast_entries"] == []


def test_bodyparts3d_perineum_is_a_region_marker_not_a_surface(ev):
    """Measured, not assumed: four ~2 cm blobs of 368 faces each. Gap 2 is not closed by this."""
    per = ev["bodyparts3d"]["measured_obj_download"]["perineum"]
    assert per["faces_each"] == 368
    assert max(per["bbox_mm"]) < 25.0, per["bbox_mm"]
    assert len(per["elements"]) == 4


def test_bodyparts3d_pelvic_floor_was_already_held(ev):
    """The apparent levator-ani delta was a naming artefact, and the survey says so."""
    got = {s.lower() for s in ev["bodyparts3d"]["already_in_zanatomy_despite_name_difference"]}
    for n in ("levator ani", "pubococcygeus", "iliococcygeus", "coccygeus"):
        assert n in got


# ------------------------------------------------------------------ Z-Anatomy upstream


def test_zanatomy_head_adds_nothing_in_any_gap_category(ev):
    new = ev["zanatomy_head"]["new_vs_pin_in_gap_categories"]
    assert set(new) == {"nerve", "female_perineum", "nail_pulp", "breast", "bursa"}
    assert all(v == 0 for v in new.values()), new


def test_zanatomy_female_terms_are_text_only(ev):
    """Mons pubis / Nipple / Areola / Nail bed / Clitoris / Vagina / Uterus / Ovary / Cooper appear in
    Startup.blend only as terminology text -- no OB or ME datablock. This is the trap that
    a name-grep alone would fall into."""
    terms = ev["zanatomy_head"]["text_only_terms_no_OB_or_ME_datablock"]
    for t in ("Mons pubis", "Nipple", "Areola", "Nail bed", "Clitoris", "Vagina", "Uterus", "Ovary"):
        assert t in terms, t


def test_zanatomy_pin_is_unchanged_and_named(ev, doc):
    assert ev["zanatomy_head"]["our_pin"].startswith("6c7f9016")
    assert "6c7f9016" in doc
    assert ev["zanatomy_head"]["license"] == "CC BY-SA 4.0"


def test_zanatomy_nail_geometry_is_four_merged_plates(ev):
    """Gap 3 is precise: Z-Anatomy ships Nail plate, and nothing ships a nail bed or digital pulp."""
    nails = ev["zanatomy_head"]["nail_objects"]
    assert all(n.startswith("Nail plate") for n in nails), nails
    assert len(nails) == 4, nails
    assert not any("bed" in n.lower() or "pulp" in n.lower() for n in nails)


# ------------------------------------------------------------------ SPARC


def test_sparc_catalogue_was_surveyed_whole(ev):
    sp = ev["sparc"]
    assert sp["published_datasets_total"] >= 600
    # not just the SPARC org: the rodent-heavy consortia and IT'IS were counted too
    assert len(sp["organizations"]) > 5
    assert "RE-JOIN" in sp["organizations"]


def test_sparc_692_is_human_and_cc_by(ev):
    d = ev["sparc_692"]
    assert d["subject"]["species"] == "Homo sapiens"
    assert d["license_spdx"] == "CC-BY-4.0"
    assert d["doi"] == "10.26275/1jdc-qiiv"


def test_sparc_692_carries_no_in_body_trajectory(ev):
    """The decisive measurement: an 85 mm excised segment laid straight in the scanner. Lateral
    wander of 1 mm over 85 mm is a straight line in scan space, not a nerve course in a body."""
    c = ev["sparc_692"]["scl2_centerline"]
    assert ev["sparc_692"]["excised_and_straightened"] is True
    assert c["arc_length_mm"] == pytest.approx(c["axial_span_mm"], abs=1.0)
    assert max(c["lateral_span_axis1_mm"], c["lateral_span_axis2_mm"]) < 3.0


def test_sparc_692_has_no_common_fibular_nerve(ev):
    """Gap 1 names the whole fibular system; 692's five annotated branches are all tibial-division
    hamstring branches."""
    d = ev["sparc_692"]
    assert d["common_fibular_branch_present"] is False
    joined = " ".join(d["branches_annotated"]).lower()
    assert "fibular" not in joined and "peroneal" not in joined


def test_sparc_scaffolds_are_self_declared_generic(ev):
    """445 and 307 are rejected on their own curators' words, not on our opinion."""
    s = ev["scaffolds"]
    assert "not subject/sample specific" in s["sparc_445"]["provenance_quote"]
    assert "best guess" in s["sparc_307"]["provenance_quote"]
    assert "Anatomography" in s["sparc_307"]["vasculature_source"]


def test_physiome_d71_is_the_same_artefact_as_sparc_445(ev):
    assert "models.physiomeproject.org/e/d71" in ev["scaffolds"]["sparc_445"]["physiome_mirror"]


# ------------------------------------------------------------------ Zygote / BioDigital


def test_zygote_provenance_fails_the_realness_rule(ev):
    """Two of the three relevant products are not derived from imaging at all, in Zygote's own words."""
    p = ev["zygote"]["products"]
    assert "photographic and illustrative atlases" in p["3D Female Reproductive System"]["provenance_quote"]
    assert "digitized from physical models" in p["3D Female Nervous System"]["provenance_quote"]
    assert "laser scans of live models" in p["3D Female Integumentary System"]["provenance_quote"]
    assert all(v["price_usd"] > 0 for v in p.values())


def test_biodigital_still_delivers_no_mesh(ev):
    assert ev["biodigital"]["mesh_files_delivered"] is False


# ------------------------------------------------------------------ bioRxiv


def test_biorxiv_is_recorded_as_unverified_with_no_citation(ev, doc):
    """The DOI prefix turned out to be genuine; the article id still could not be resolved. The
    survey must say so and must not carry an invented citation."""
    b = ev["biorxiv"]
    assert b["prefix_10_64898_is_real_biorxiv_prefix"] is True
    assert b["this_article_id_found"] is False
    assert b["http_status_every_attempt"] == 429
    assert "429" in doc


# ------------------------------------------------------------------ the document itself


def test_survey_is_hebrew_with_english_anatomy_terms(doc):
    assert sum(1 for ch in doc if "֐" <= ch <= "׿") > 2000
    for term in ("fibular", "sciatic nerve", "levator ani", "mons pubis", "perineum", "Cooper"):
        assert term in doc, term


def test_survey_has_a_row_for_every_one_of_the_eight_sources(doc):
    for key in ("BodyParts3D", "Z-Anatomy", "sparc.science", "Pennsieve", "physiomeproject",
                "bioRxiv", "Zygote", "BioDigital"):
        assert key in doc, key


def test_survey_states_plainly_that_nothing_qualified(doc):
    assert "לא יובא דבר" in doc


def test_gap1_uses_q303s_reverified_count_not_the_brief_s(ev, doc):
    """The round brief said 18 fibular/peroneal meshes per Z page; Q303 re-measured the pages'
    own calibre table and got 24 against 0 on both Imaging pages. The survey uses 24."""
    g = ev["gap1_reverified_by_q303"]
    assert g["fibular_peroneal_mesh_ids_imaging_pages"] == 0
    assert g["fibular_peroneal_mesh_ids_each_z_page"] == 24
    assert g["lower_limb_nerves_missing_total"] == 71
    assert "24" in doc
