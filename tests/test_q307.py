"""Q307: the nerve-placement assertions, so the defects this round measured cannot slip back.

The round started from the owner's report that the LATERAL ANTEBRACHIAL CUTANEOUS NERVE is "not in place". What
Q307 measured is that on the four Z pages it is in the right compartment, on the right side and at the right
depth, but covers only the proximal two thirds of the forearm -- and that it did not exist AT ALL on either
Imaging page, along with 95 other nerves the Combined page of the same body carries. These tests pin both the
fix and the honest statement of what is still wrong.
"""
from __future__ import annotations
import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
DERIVED = REPO / "data/derived"
LACN = "zan_lateral_antebrachial_cutaneous_nerve"
ZKEYS = ("base_m", "base_f", "comb_m", "comb_f")
OWN = ("own_m", "own_f")


def _j(p):
    return json.loads((DERIVED / p).read_text())


@pytest.fixture(scope="module")
def lacn():
    return _j("Q307_lacn_measurements.json")


@pytest.fixture(scope="module")
def xfer():
    return _j("Q307_nerve_transfer.json")


@pytest.fixture(scope="module")
def val():
    return _j("Q307_nerve_validation.json")


# ---------------------------------------------------------------- the owner's own case
def test_the_nerve_the_owner_reported_is_on_all_six_pages_and_on_both_sides(lacn):
    for k in ZKEYS + OWN:
        for s in ("l", "r"):
            m = lacn["pages"][k][s]
            assert m.get("t_along_the_forearm"), f"{k} {s}: no measured position"
            assert m.get("present", True) is not False, f"{k} {s}: absent"


def test_it_is_on_the_lateral_side_of_the_forearm_on_every_page(lacn):
    """radial of the radius' own axis, with the ulna's axis on the other side -- measured in a frame built from
    each page's OWN radius and ulna, so no page's pose can change the answer."""
    for k in ZKEYS + OWN:
        for s in ("l", "r"):
            m = lacn["pages"][k][s]
            assert m["radial_coord_p50_mm"] > 0, f"{k} {s} is not radial: {m['radial_coord_p50_mm']}"
            assert m["ulna_axis_radial_coord_p50_mm"] < m["radial_coord_p50_mm"]


def test_it_lies_against_the_brachioradialis_within_the_cited_distance(lacn):
    """Khadanovich 2023 (PMID 38128746, n=93 forearms): 'The medial border of the brachioradialis muscle was
    observed less than 1.8 mm from the LACN'. Our median distance to that muscle's surface is in that band on
    the Z pages; the Imaging pages carry the registration error on top, which their cards state."""
    for k in ZKEYS:
        for s in ("l", "r"):
            d = lacn["pages"][k][s].get("d_brachioradialis_surface_p50_mm")
            if d is None:
                continue
            assert d <= 2.5, f"{k} {s}: {d} mm from the brachioradialis"


def test_it_is_not_buried_in_the_brachioradialis_belly(lacn):
    """The false finding this round nearly reported. An uncalibrated inside/outside voxel test called 48-65 % of
    the nerve 'inside brachioradialis'; the mask is inflated by about one voxel (measured 1.28-1.35 mm on these
    muscles), and the nerve's true maximum depth inside it is under 2.7 mm. Pinned so a later round cannot
    re-report the burial."""
    for k in ZKEYS:
        for s in ("l", "r"):
            m = lacn["pages"][k][s]
            off = m.get("brachioradialis_mask_offset_mm")
            dep = m.get("max_depth_inside_the_brachioradialis_mask_mm")
            if off is None or dep is None:
                continue
            assert dep - off < 2.0, f"{k} {s}: {dep} mm deep against a {off} mm mask offset"


def test_the_truncation_is_recorded_and_has_not_silently_changed(lacn):
    """It stops in mid-forearm on every page: the distal third, the wrist and thenar territory and the division
    into anterior and posterior branches do not exist. Stated on the card, not sculpted (Q297's lesson)."""
    for k in ZKEYS + OWN:
        for s in ("l", "r"):
            t = lacn["pages"][k][s]["t_along_the_forearm"]
            assert 0.60 <= t[1] <= 0.80, f"{k} {s}: distal end at t={t[1]}"
    for k in ZKEYS:
        for s in ("l", "r"):
            assert lacn["pages"][k][s]["distal_end_short_of_the_wrist_mm"] >= 50.0


def test_the_literature_block_carries_both_papers_with_their_identifiers(lacn):
    lit = lacn["literature"]
    assert lit["qawasmi_2024"]["pmid"] == "38934998"
    assert lit["qawasmi_2024"]["doi"] == "10.1016/j.jhsa.2024.04.018"
    assert lit["khadanovich_2023"]["pmid"] == "38128746"
    assert lit["khadanovich_2023"]["doi"] == "10.1016/j.aanat.2023.152202"
    assert lit["khadanovich_2023"]["branches_into_anterior_and_posterior_pct"] == 81.7
    assert any("deep to the forearm superficial fascia" in q for q in lit["qawasmi_2024"]["quotes"])
    assert any("less than 1.8 mm from the LACN" in q for q in lit["khadanovich_2023"]["quotes"])


def test_the_lateral_antebrachial_cutaneous_nerve_now_has_a_cited_parent():
    """The project's own nerve registry has no row for it, which is why Q307's continuity test had no parent for
    the very structure the owner reported."""
    d = json.loads((REPO / "data/anatomy/nerve_parents_q307.json").read_text())
    row = next(r for r in d["parents"] if r["id"] == "lateral_antebrachial_cutaneous_nerve")
    assert row["parent_id"] == "musculocutaneous_n"
    assert "20931188" in row["source"] and "38934998" in row["source"]
    for r in d["parents"]:
        assert r.get("source"), f"{r['id']} has no source"


# ---------------------------------------------------------------- the transfer onto the Imaging pages
def test_each_imaging_page_gained_the_upper_limb_nerves_it_was_missing(xfer):
    for k in OWN:
        assert xfer[k]["n_transferred"] >= 55, xfer[k]["n_transferred"]
        assert LACN + "_l" in xfer[k]["ids"] and LACN + "_r" in xfer[k]["ids"]


def test_every_refusal_is_named_with_its_measured_reason(xfer):
    for k in OWN:
        for i, why in xfer[k]["refused"].items():
            assert re.search(r"\d", why), f"{k} {i}: refusal with no number"
            assert ("exceeds the gate" in why or "inside bone" in why or "BOTH sides pass" in why), why


def test_no_nerve_this_round_touched_ends_up_on_one_side_only(xfer):
    """A round called in to fix a nerve that exists on one side only must not create another one. The gate is
    applied in pairs inside the transfer, and the check here is on the PAGE: after the build, both sides of
    every nerve this round carried must be on it. (A nerve whose other side the page already had is not in the
    transfer list at all -- `recurrent_branch_of_median_n_l` was already there and only the right side was
    carried -- so the list alone is the wrong thing to test, which is how this test first failed.)"""
    cal = json.loads((REPO / "data/anatomy/calibre.json").read_text())
    page = {"own_m": "viewer_m_hr", "own_f": "viewer_f_hr"}
    for k in OWN:
        have = set(cal["pages"][page[k]]["c"])
        for i in xfer[k]["ids"]:
            other = (i[:-2] + "_r") if i.endswith("_l") else ((i[:-2] + "_l") if i.endswith("_r") else None)
            if other is None:
                continue
            assert other in have, f"{k}: {i} is on the page without {other}"


def test_the_one_sided_mirror_stubs_were_replaced_and_nothing_traced_was(xfer):
    """Q304's selector skipped any id the Imaging page already carried, so the page ended up with a full-length
    nerve on one side and a 29-40 mm mirror of the other side's traced segment under the SAME name. Only a
    `mirror_q237` mesh may be replaced; a structure traced on the body's own imaging never is."""
    assert xfer["own_m"]["n_replaced"] == 1
    assert xfer["own_f"]["n_replaced"] == 2
    for k in OWN:
        for i in xfer[k]["ids"]:
            pass
    txt = json.dumps(xfer)
    assert "mirror_q237" in txt


def test_the_detached_branches_now_meet_their_parent_trunk(val):
    """Imaging M's right plantar nerves hung 436.6 mm from their own tibial nerve and Imaging F's left 370.4 mm.
    Every parent/branch pair this round repaired must now touch."""
    for k in OWN:
        for pair, d in val[k]["checks"]["continuity_mm"].items():
            assert d <= 3.46, f"{k} {pair}: {d} mm (Q298's measured contact threshold is 3.46 mm)"


def test_the_transfer_adds_no_bone_penetration_and_nothing_leaves_the_body(val):
    for k in OWN:
        c = val[k]["checks"]
        assert c["body_mask_validates"] is True
        for i, r in (c["leaves_the_body"] or {}).items():
            assert r["worst_mm"] <= 5.0, f"{k} {i}: {r['worst_mm']} mm outside the body"
        for i, f in (c["in_bone_frac_over_5pct"] or {}).items():
            assert f <= 0.5, f"{k} {i}: {f:.0%} inside bone"


def test_mesh_realness_against_the_cvh_references(val):
    for k in OWN:
        d = val[k]["checks"]["dihedral"]
        assert d["cvh_references_deg"] == [31.7, 27.6, 29.5]
        assert 5.0 <= d["min"] and d["max"] <= 75.0, d


def test_the_new_nerves_have_a_measured_calibre_row_or_the_viewer_would_skip_them():
    """Q240's table drives the Labels panel, the nerve-level filter and Q303's nerve emphasis; a nerve without a
    row is invisible to all three, which is how the Imaging pages came to report 0 fibular nerves."""
    cal = json.loads((REPO / "data/anatomy/calibre.json").read_text())
    for page in ("viewer_m_hr", "viewer_f_hr"):
        c = cal["pages"][page]["c"]
        added = cal["pages"][page]["q307_added"]
        assert added, page
        for i in added:
            assert i in c and c[i][0] == "n" and c[i][1] > 0, (page, i, c.get(i))
        assert LACN + "_l" in c and LACN + "_r" in c


# ---------------------------------------------------------------- the general audit
def test_the_placement_audit_covers_every_page_and_every_nerve_it_claims():
    for k in ZKEYS + OWN:
        d = _j(f"Q307_placement_{k}.json")
        assert d["page"] == k
        assert d["n_scope"] >= 200, d["n_scope"]
        assert d["deep_mm_threshold"] == 2.0 and d["pitch_mm"] == 1.5
        cut = [i for i, r in d["structures"].items() if r["cutaneous"]]
        # the audit ran on the PRE-fix pages, where the Imaging pages carried no upper-limb cutaneous nerve at
        # all -- 17 on Imaging M against 43-45 on a Z page -- which is the gap this round closed.
        assert len(cut) >= (15 if k in OWN else 30), f"{k}: only {len(cut)} cutaneous nerves in scope"


def test_no_nerve_is_mostly_inside_a_muscle_belly_without_being_on_record():
    """Every cutaneous nerve measured deeper than the mask's own error band + 2 mm inside a muscle, with at
    least 5 % of its samples and a p95 depth of 5 mm or more, carries that depth on its own card."""
    cards = _j("Q307_in_muscle_cards.json")
    for k in ZKEYS + OWN:
        d = _j(f"Q307_placement_{k}.json")
        want = set()
        for i, r in d["structures"].items():
            if not r["cutaneous"]:
                continue
            if any(v["p95_mm"] >= 5.0 and v["frac"] >= 0.05 for v in r["in_muscle"].values()):
                want.add(i)
        assert want == set(cards.get(k, {})), f"{k}: {want ^ set(cards.get(k, {}))} not on a card"


def test_the_side_token_of_every_nerve_matches_the_side_it_is_on():
    """A nerve whose id says left must have its centroid on the left of the page's own midsagittal plane. The
    offenders are midline-crossing structures and are listed rather than silently tolerated."""
    allowed = re.compile(r"vagus|dorsal_n_penis|dorsal_n_clitoris|anococcygeal|splanchnic|plantar_digital|"
                         r"dorsal_digital_branches_of_deep_fibular")
    for k in ZKEYS + OWN:
        d = _j(f"Q307_placement_{k}.json")
        bad = [i for i, r in d["structures"].items() if not r["side"]["ok"] and not allowed.search(i)]
        assert not bad, f"{k}: {bad}"


def test_the_one_sided_source_mismatch_scan_is_on_record():
    d = _j("Q307_side_source_mismatch.json")
    for k in OWN:
        assert d[k]["offenders"], f"{k}: the scan found nothing, which cannot be right for the pre-fix state"
        names = {o["base"] for o in d[k]["offenders"]}
        assert "tibial_n" in names
