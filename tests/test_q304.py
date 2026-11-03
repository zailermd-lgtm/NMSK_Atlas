"""Q304: the lower-limb nerve meshes carried onto the two Imaging pages from the Combined page of the SAME body by
the documented bone-point registration, and the calibre of our sciatic nerve validated against SPARC dataset 692.

These are the static checks; the browser ones are scripts/anatomy/q304/verify_q304.py.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
D = REPO / "data" / "derived"
Q304 = REPO / "scripts" / "anatomy" / "q304"
THIRD = REPO / "third_party" / "sparc_692_sciatic"
DOI = "10.26275/1jdc-qiiv"
CVH = (31.7, 27.6, 29.5)
OWN = ("own_m", "own_f")


def j(p):
    if not p.is_file():
        pytest.skip(f"{p.name} not built")
    return json.loads(p.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def xfer():
    return j(D / "Q304_nerve_transfer.json")


@pytest.fixture(scope="module")
def val():
    return j(D / "Q304_nerve_validation.json")


@pytest.fixture(scope="module")
def probe():
    return j(D / "Q304_frame_probe.json")


@pytest.fixture(scope="module")
def sparc():
    return j(D / "Q304_sparc692_calibre.json")


@pytest.fixture(scope="module")
def cmp_():
    return j(D / "Q304_sparc692_comparison.json")


# ---------------------------------------------------------------- the premise, measured and not assumed
def test_the_combined_page_is_already_fitted_to_the_imaging_page_s_own_skeleton(probe):
    """The round's whole shortcut rests on this. It is measured point-to-surface on 22-23 shared bone groups, and
    the only group above 3 mm median is the coccyx, which is named."""
    for k in OWN:
        rows = probe[k]["bones"]
        assert len(rows) >= 22, (k, len(rows))
        # the only groups above 3 mm median are the two small bones whose Z mesh is worst fitted -- the coccyx
        # (9.4 mm on Imaging M) and the patellae (3.3-4.5 mm) -- and they are named so a new offender cannot hide
        bad = {g: v["median_mm"] for g, v in rows.items() if v["median_mm"] > 3.0}
        assert set(bad) <= {"coccyx", "patella_l", "patella_r"}, (k, bad)
        assert probe[k]["median_of_bone_medians_mm"] <= 2.5, (k, probe[k]["median_of_bone_medians_mm"])


def test_the_bundle_of_a_shipped_imaging_page_round_trips_byte_for_byte():
    """Q299 recorded that the Imaging pages could not be touched because the matching bundle was not on disk. It is
    recoverable from the page itself, and the recovery is proved by re-rendering, not asserted."""
    r = j(D / "Q304_bundle_recovery.json")
    for k in OWN:
        assert r["pages"][k]["ok"] is True, (k, r["pages"][k])
        assert r["pages"][k]["structures"] > 900
        assert r["pages"][k]["bytes"] > 20_000_000


# ---------------------------------------------------------------- the registration
def test_the_registration_residual_is_reported_and_small(xfer):
    for k in OWN:
        r = xfer[k]["registration"]
        assert r["median_mm"] <= 1.2, (k, r["median_mm"])
        assert r["p95_mm"] <= 4.0, (k, r["p95_mm"])
        assert r["max_mm"] <= 25.0, (k, r["max_mm"])
        # it must be an IMPROVEMENT on the untransformed frame, in both median and p95
        assert r["median_mm"] < r["before"]["median_mm"], (k, r)
        assert r["p95_mm"] < r["before"]["p95_mm"], (k, r)
        assert r["kept_pairs"] > 50_000, (k, r["kept_pairs"])


def test_the_map_is_the_identity_plus_a_correction_field_and_says_why():
    """The first version used a free global similarity and slid a nerve 22.7 mm down the leg; the module records
    that rejection beside the method so it cannot come back silently."""
    s = (Q304 / "reg304.py").read_text(encoding="utf-8")
    assert "22.7 mm" in s and "slides freely ALONG the shaft" in s
    assert "thin_plate_spline" in s and "IDENTITY plus" in s
    assert "closest-point displacement is normal to the target surface" in s


def test_every_transferred_vertex_is_a_combined_page_vertex_moved_by_one_field(xfer):
    """No sculpting: the displacement of each mesh is bounded by the field's own displacement, which is bounded by
    the bone correspondences."""
    for k in OWN:
        r = xfer[k]["registration"]
        assert r["displacement_median_mm"] <= 3.0, (k, r)
        assert r["displacement_max_mm"] <= 30.0, (k, r)


# ---------------------------------------------------------------- what landed
def test_the_fibular_system_landed_on_both_imaging_pages(xfer):
    """The owner's own defect. 0 fibular / peroneal meshes on either Imaging page before this round."""
    for k in OWN:
        fib = [i for i in xfer[k]["ids"] if "fibular" in i or "peroneal" in i]
        assert len(fib) == 18, (k, len(fib))
        for want in ("common_fibular_n_l", "common_fibular_n_r", "deep_fibular_n_l", "deep_fibular_n_r",
                     "superficial_fibular_n_l", "superficial_fibular_n_r"):
            assert want in xfer[k]["ids"], (k, want)


def test_the_counts_are_what_the_round_reports(xfer):
    assert xfer["own_m"]["n_transferred"] == 71
    assert xfer["own_f"]["n_transferred"] == 64
    assert 60_000 < xfer["own_m"]["triangles"] < 70_000
    assert 55_000 < xfer["own_f"]["triangles"] < 65_000


def test_the_calibre_table_records_the_new_nerves():
    """Q240's table is keyed by id and `--inject` only copies it, so without rows of their own the Labels panel,
    the nerve-level filter and Q303's emphasis would all skip them."""
    cal = json.loads((REPO / "data/anatomy/calibre.json").read_text(encoding="utf-8"))
    xf = j(D / "Q304_nerve_transfer.json")
    for key, page in (("own_m", "viewer_m_hr"), ("own_f", "viewer_f_hr")):
        c = cal["pages"][page]["c"]
        for sid in xf[key]["ids"]:
            assert sid in c, (page, sid)
            assert c[sid][0] == "n", (page, sid, c[sid])
            assert c[sid][1] > 0, (page, sid, c[sid])
        assert cal["pages"][page]["q304_added"] == sorted(xf[key]["ids"])


def test_the_pose_rig_grew_by_exactly_the_new_structures():
    rep = j(D / "Q304_page_report.json")
    for key in OWN:
        rig = json.loads((REPO / f"data/anatomy/pose_rig_{key}.json").read_text(encoding="utf-8"))["rig"]
        # Q307 spliced 57 / 60 more after Q304's, so the rig is longer than Q304's own end: what Q304 pinned is
        # that ITS entries sit immediately after the committed ones, which is still exactly true.
        assert rig["count"] >= len(rep[key]["new_indices"]) + min(rep[key]["new_indices"]), (key, rig["count"])
        assert "Q304" in rig["notes"]


# ---------------------------------------------------------------- provenance, the point of the round
def test_no_transferred_structure_can_print_measured_on_this_body():
    """The subject id is what decides the class the card prints and what Q297's audit reads. `xfer_zan2*` is the
    Z-Anatomy fill class and a label containing "rule" is the rule-based class; neither is "measured"."""
    rep = j(D / "Q304_page_report.json")
    tpl = (REPO / "viewer/atlas_viewer.template.html").read_text(encoding="utf-8")
    for key in OWN:
        subs = rep[key]["subjects"]
        assert subs, key
        for s in subs:
            assert s.startswith("xfer_zan2") or "rule_nerve" in s, (key, s)
            assert s + ":" in tpl, f"{s} has no SUBJECT_LABELS entry (scripts/sync_subjects_q304.py)"
    assert 'if (b.indexOf("xfer_zan2") === 0) return "filled_zan";' in tpl


def test_the_provenance_audit_still_has_nothing_unaccounted_for():
    a = j(D / "Q304_provenance_audit.json")
    assert a["class_totals"]["d_unaccounted" if "d_unaccounted" in a["class_totals"] else "a_measured"] is not None
    assert a["class_totals"].get("d_unaccounted", 0) == 0
    assert len(a["unaccounted"]) == 0
    assert len(a["mislabelled"]) == 0, a["mislabelled"][:3]
    assert len(a["rule_without_visible_badge"]) == 0
    # the transferred meshes are counted as real third-party geometry or as documented rules, never as measured
    assert a["class_totals"]["a_measured"] == 803
    assert a["class_totals"]["b_real_third_party"] == 13004
    assert a["class_totals"]["c_rule_based"] == 1481
    assert a["pages"]["own_m"]["meshes"] == 1022
    assert a["pages"]["own_f"]["meshes"] == 1168


def test_every_card_states_a_method_and_an_error_band():
    """Q300 made both templates render `method` and `error_band_mm`; Q297 found 68 cards that printed nothing.
    Every structure this round adds must carry both."""
    import sys
    sys.path.insert(0, str(Q304))
    import cards304 as CD  # noqa: E402
    nerves = Path("/dev/shm/q304/nerves")
    xf = j(D / "Q304_nerve_transfer.json")
    va = j(D / "Q304_nerve_validation.json")
    if not (nerves / "own_m_nerves.json").is_file():
        pytest.skip("the Q304 nerve build is not in /dev/shm (it is wiped on a container restart)")
    for key in OWN:
        items = json.loads((nerves / f"{key}_nerves.json").read_text(encoding="utf-8"))
        reg = dict(xf[key]["registration"]); reg["bone_groups"] = xf[key]["bone_groups"]
        for sid, d in items.items():
            rec = CD.transferred_rec(key, d, reg, va[key], "Combined")
            assert rec["method"], sid
            assert isinstance(rec["error_band_mm"], float) and rec["error_band_mm"] > 0, sid
            assert rec["procedural_badge"].startswith("Q304 NOT SEGMENTED FROM THIS SUBJECT'S OWN IMAGING"), sid
            assert "Measured on this body" not in rec["procedural_badge"], sid
            assert "bone-point" in rec["procedural_badge"], sid
            assert "Z-Anatomy" in rec["source"], sid


# ---------------------------------------------------------------- validation against the page's own geometry
def test_no_transferred_nerve_penetrates_skin_or_sits_mostly_inside_a_bone(val):
    for k in OWN:
        assert val[k]["mask_validation"]["ok"] is True, (k, val[k]["mask_validation"]["reasons"])
        assert val[k]["bone"]["n_mostly_inside"] == 0, (k, val[k]["bone"])
        assert val[k]["bone"]["worst_depth_mm"] <= 8.0, (k, val[k]["bone"])
    assert val["own_m"]["skin"]["n_with_any_outside"] == 0, val["own_m"]["skin"]
    # Imaging Female keeps ONE offender, in her toes, because the mesh guard refused the pull-in rather than
    # flipping 5.17 % of its triangles. It is pinned by name so it cannot be forgotten.
    out = [i for i, v in val["own_f"]["structures"].items() if v["out_beyond_5mm"]]
    assert out == ["zan_dorsal_digital_branches_of_deep_fibular_nerve_r"], out
    assert val["own_f"]["skin"]["worst_mm"] < 10.0


def test_the_course_past_the_fibular_neck_is_plausible(val):
    for k in OWN:
        f = val[k]["fibular_neck"]
        assert set(f) == {"l", "r"}, (k, list(f))
        for side, v in f.items():
            assert v["crosses_head_level"] is True, (k, side)
            assert v["min_dist_to_fibular_neck_mm"] <= 5.0, (k, side, v["min_dist_to_fibular_neck_mm"])
            for br, b in v["branches"].items():
                assert b["gap_mm"] <= 1.0, (k, side, br, b)


def test_left_right_is_judged_against_the_page_s_own_skeleton_and_not_mirror_symmetry(val):
    """On these pages the man's own FIBULA has a mirror median of 76.7 mm, because his legs were scanned in
    different positions. Mirror symmetry is therefore the wrong criterion (Q296 learned it on Combined M)."""
    bm = val["own_m"]["bone_mirror"]
    assert bm["fibula"]["median_mm"] > 50.0, bm["fibula"]
    for k in OWN:
        rat = [v["ratio_to_bone"] for v in val[k]["mirror"].values() if v["ratio_to_bone"]]
        assert len(rat) >= 25, (k, len(rat))
        rat.sort()
        assert rat[len(rat) // 2] <= 2.0, (k, rat[len(rat) // 2])


def test_the_realness_of_every_transferred_mesh_is_recorded_against_the_cvh_references(val):
    for k in OWN:
        d = val[k]["dihedral"]
        assert tuple(d["cvh_reference_deg"]) == CVH
        assert 5.0 <= d["min"] <= 60.0 and 5.0 <= d["max"] <= 60.0, (k, d)
        for sid, v in val[k]["structures"].items():
            assert v["defect_edges_pct"] <= 10.0, (k, sid, v["defect_edges_pct"])
            assert v["cm3_abs"] > 0, (k, sid)


def test_the_sided_sciatic_is_not_a_duplicate_of_the_body_s_own_traced_one(val):
    """Measured rather than assumed: the Imaging pages carry their own `sciatic_n`, traced over about a third of
    the course, and the transferred sided pair is a different statement about the same nerve."""
    for k in OWN:
        dup = [v for v in val[k]["structures"].values() if v.get("duplicates")]
        assert dup, k
        for v in dup:
            for o in v["duplicates"]:
                # the worst overlap anywhere is her left sided sciatic against her own traced `sciatic_n`:
                # 10.7 % of its surface within 3 mm, median separation 34.8 mm. The rest are 0.0-0.4 %.
                assert o["within_3mm_pct"] <= 12.0, (k, o)


# ---------------------------------------------------------------- Part B
def test_the_sparc_dataset_is_identified_with_its_doi_licence_and_subject(sparc):
    d = sparc["dataset"]
    assert d["doi"] == DOI
    assert d["license"] == "CC BY 4.0"
    assert d["voxel_um"] == 11.4
    assert "sub-SC001" in d["subject"] and "embalmed cadaver" in d["subject"]
    assert len(sparc["files"]) == 23
    assert sum(f["bytes"] for f in sparc["files"]) < 20_000_000, "only the calibre products may be downloaded"
    for f in sparc["files"]:
        assert len(f["sha256"]) == 64


def test_the_morphology_columns_were_converted_from_voxels(sparc):
    """The one trap in this dataset: `eq_diameter` is in VOXELS of the 11.4 um scan, not millimetres."""
    for s, v in sparc["samples"].items():
        assert "VOXELS" in v["note"]
        e = v["eq_diameter_mm"]
        assert 4.0 <= e["mean"] <= 9.0, (s, e)
        assert v["n_slices"] > 5000, (s, v["n_slices"])
    assert 6.0 <= sparc["pooled"]["mean_of_sample_means_mm"] <= 7.5


def test_the_five_named_levels_are_read_from_the_dataset_s_own_annotations(sparc):
    for side in ("left", "right"):
        lv = sparc["levels"][side]
        assert set(lv) == {"formation", "lesser_trochanter", "lt+7cm", "lt+14cm", "lt+21cm"}, (side, list(lv))
        for name, v in lv.items():
            assert 4.0 <= v["eq_diameter_window_mean_mm"] <= 9.0, (side, name, v)
            assert v["window_slices"] >= 100, (side, name, v)
            assert side in v["annotation"]


def test_only_calibre_was_taken_and_never_shape():
    s = (Q304 / "sparc304.py").read_text(encoding="utf-8")
    assert "CALIBRE ONLY, NEVER SHAPE" in s
    assert "excised" in s and "laid straight" in s
    n = (THIRD / "NOTICE").read_text(encoding="utf-8")
    assert "NOT USED: no geometry, no image, no mask, no mesh and no centreline shape" in n


def test_the_comparison_is_apples_to_apples(cmp_):
    """SPARC's slices are perpendicular to the nerve's own axis because the segment was laid straight, so ours are
    cut perpendicular to our nerve's own local axis too; the oblique section is kept beside it."""
    s = (Q304 / "sparc304.py").read_text(encoding="utf-8")
    assert "PERPENDICULAR TO THE NERVE'S OWN LOCAL AXIS" in s
    assert "oblique_eq_diameter_mm" in s
    assert cmp_["doi"] == DOI and cmp_["license"] == "CC BY 4.0"
    assert cmp_["n_comparisons"] >= 40
    rows = [r for r in cmp_["rows"] if r.get("ratio")]
    assert {r["page"] for r in rows} == {"own_m", "own_f", "base_m", "base_f", "comb_m", "comb_f"}
    # the oblique (femoral-axis) section is recorded beside the perpendicular one wherever the plane meets the mesh;
    # on two of the 50 rows it misses entirely, which is stated rather than hidden
    assert sum(1 for r in rows if r["oblique_mm"] is None) <= 3, [r for r in rows if r["oblique_mm"] is None]


def test_the_discrepancy_is_the_one_the_round_reports(cmp_):
    by = cmp_["by_level_ratio_median"]
    # proximal: ours is too thick; mid / distal thigh: within about a quarter
    assert by["lesser_trochanter"] >= 1.4, by
    assert by["formation"] >= 1.4, by
    for lv in ("lt+14cm", "lt+21cm"):
        assert 0.75 <= by[lv] <= 1.25, (lv, by[lv])
    assert 0.9 <= by["lt+7cm"] <= 1.3, by


def test_no_mesh_calibre_was_changed_and_the_reason_is_on_the_card():
    """The brief allowed a change only if it could be made from the real measurement. It cannot: the specimen is
    embalmed, PTA-stained and excised (a lower bound), and n = 1."""
    import sys
    sys.path.insert(0, str(Q304))
    import cards304 as CD  # noqa: E402
    cmp_ = j(D / "Q304_sparc692_comparison.json")
    lev = j(D / "Q304_sparc692_calibre.json")["levels"]
    rows = [r for r in cmp_["rows"] if r["page"] == "base_m" and r["id"] == "sciatic_n_r"]
    note = CD.sciatic_note("base_m", rows, lev)
    assert DOI in note and "CC BY 4.0" in note
    assert "THE GEOMETRY WAS DELIBERATELY NOT CHANGED" in note
    assert "lower bound" in note and "n=1" in note.replace("(n = 1)", "n=1")
    assert "never the shape" in note
    rep = j(D / "Q304_page_report.json")
    for k in ("own_m", "own_f", "base_m", "base_f", "comb_m", "comb_f"):
        assert rep[k]["sciatic_cards"], k
    assert rep["own_m"]["replaced"] == [] and rep["base_m"]["added"] == []


def test_the_licence_obligations_are_shipped_the_way_q296_shipped_the_slicer_licence():
    assert (THIRD / "LICENSE").is_file() and (THIRD / "NOTICE").is_file() and (THIRD / "README.md").is_file()
    lic = (THIRD / "LICENSE").read_text(encoding="utf-8")
    assert lic.startswith("Creative Commons Attribution 4.0 International")
    for needle in ("Section 1 – Definitions", "Section 3 – License Conditions", "Attribution"):
        assert needle in lic or needle.replace("–", "-") in lic, needle
    n = (THIRD / "NOTICE").read_text(encoding="utf-8")
    low = n.lower()
    for needle in (DOI, "sub-SC001", "41 years", "embalmed cadaver", "11.4 um", "CC-BY-4.0",
                   "doi:10.1088/1741-2552/ae33f6", "Pelot", "OT2OD025349", "NOT ENDORSED"):
        assert needle.lower() in low, needle


# ---------------------------------------------------------------- the on-screen missing list
def test_q303_s_missing_nerve_probe_matches_the_way_the_page_names_things():
    """Q304's finding: the engine's list does not always carry a display name, so a MAJOR pattern ending in a word
    boundary could never match an id like `tibial_n` -- "_" is a word character. The screen said an Imaging page
    carried no tibial and no sural nerve while it carried both."""
    src = (REPO / "viewer/q303/nerves.js").read_text(encoding="utf-8")
    assert 'var idn = String(r.id || "").replace(/_/g, " ");' in src
    assert "p[1].test(r.id) || p[1].test(idn) || p[1].test(r.name)" in src
    assert "conventional list" in src, "a rule-based list must still say so"
    assert "Q304 carried those nerves across by bone-point" in src
    for t in TEMPLATES_TEXT():
        assert 'var idn = String(r.id || "").replace(/_/g, " ");' in t


def TEMPLATES_TEXT():
    return [(REPO / "viewer/atlas_viewer.template.html").read_text(encoding="utf-8"),
            (REPO / "viewer/zan_atlas.template.html").read_text(encoding="utf-8")]


def test_the_research_doc_exists_and_carries_the_numbers():
    p = REPO / "docs/research/Q304_nerve_transfer_and_calibre.md"
    s = p.read_text(encoding="utf-8")
    assert len(s) > 12000
    for needle in (DOI, "sub-SC001", "common fibular", "thin_plate_spline", "Q297", "22.7",
                   "lesser trochanter", "CC BY 4.0", "fibular neck"):
        assert needle in s, needle
    assert "|" in s, "the round asked for tables"


def test_the_sources_doc_and_the_viewer_readme_record_the_round():
    g = (REPO / "docs/GEOMETRY_SOURCES.md").read_text(encoding="utf-8")
    assert "## Q304" in g and DOI in g and "third_party/sparc_692_sciatic" in g
    v = (REPO / "docs/VIEWER_README.md").read_text(encoding="utf-8")
    assert "Q304" in v and "fibular" in v


def test_the_open_items_page_marks_the_two_decisions_as_taken():
    t = (REPO / "docs/OPEN_ITEMS_FOR_OWNER.md").read_text(encoding="utf-8")
    assert "## Q304" in t
    assert DOI in t
    assert "fit from Z" in t and "validate and cite" in t
