"""Q297: data-level assertions for the provenance audit and for the three things this round changed.

The headline assertions are the two the brief asked for: no shipped structure is in class (d), and every rule-based
structure both carries a visible rule badge and has a volume recorded. The rest pin the perineum, breast and fingertip
findings so a later round cannot silently undo them."""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
Q297 = REPO / "scripts/anatomy/q297"
sys.path.insert(0, str(Q297))

# Q308: the baseline is resolved from scripts/anatomy/q241/model.SRC, the one place that declares it, instead
# of a literal here. A hardcoded `build/q297` in a test keeps asserting about a build that landed rounds ago
# and reports success while doing it -- which is how 31 rule-tracked nerves added by Q304 and Q307 came to have
# no recorded volume with these very tests passing.
def _baseline_root():
    import sys as _s
    _p = str(REPO / "scripts/anatomy/q241")
    if _p not in _s.path:
        _s.path.insert(0, _p)
    import model as _m
    return _m.build_root()


_BASELINE = _baseline_root()

BUILD = REPO / _BASELINE
pytestmark = pytest.mark.skipif(not BUILD.is_dir(), reason=f"{_BASELINE} not on disk")


@pytest.fixture(scope="module")


def audit():
    import audit297
    return audit297.run(_BASELINE)


@pytest.fixture(scope="module")
def prov():
    import prov297
    return prov297


# ---------------------------------------------------------------- the two assertions the round is about
def test_no_structure_is_unaccounted(audit):
    """class (d): geometry whose shape cannot be traced to a real source or to a cited rule."""
    bad = [(r["page"], r["id"], r["why"]) for r in audit["unaccounted"]]
    assert bad == [], f"{len(bad)} shipped structures are unaccounted for: {bad[:10]}"


def test_every_rule_based_structure_shows_a_rule_badge(audit):
    bad = [(r["page"], r["id"]) for r in audit["rule_without_visible_badge"]]
    assert bad == [], f"{len(bad)} rule-based structures show no rule wording on their card: {bad[:10]}"


def test_no_card_claims_measured_for_generated_geometry(audit):
    bad = [(r["page"], r["id"], r["cls"]) for r in audit["mislabelled"]]
    assert bad == [], f"{len(bad)} cards print 'Measured on this body' for geometry that is not measured: {bad[:10]}"


def test_every_rule_based_structure_records_a_volume(prov):
    """Every class (c) structure has a volume on file. Most state one in their own badge; the generated connectors and
    the rule-tracked vessels / nerves state the calibre and length that define the solid instead, so Q297 measured the
    enclosed volume of all of them off the shipped geometry into data/derived/Q297_rule_based_volumes.json."""
    import audit297
    rec = json.loads((REPO / "data/derived/Q297_rule_based_volumes.json").read_text())["pages"]
    missing = []
    for key in prov.KEYS:
        h, d, kind = prov.page_html(key, _BASELINE)
        L = prov.subject_labels(h) if kind == "own" else {}
        have = rec.get(key, {})
        for st in prov.structures(key, _BASELINE):
            cls, _, _ = audit297.classify(st, kind, L)
            if cls != "c_rule_based":
                continue
            if have.get(st["id"]) is None:
                missing.append((key, st["id"]))
    assert missing == [], f"{len(missing)} rule-based structures have no recorded volume: {missing[:10]}"


def test_the_recorded_volumes_cover_exactly_the_rule_based_set(prov):
    import audit297
    rec = json.loads((REPO / "data/derived/Q297_rule_based_volumes.json").read_text())["pages"]
    for key in prov.KEYS:
        h, d, kind = prov.page_html(key, _BASELINE)
        L = prov.subject_labels(h) if kind == "own" else {}
        want = {st["id"] for st in prov.structures(key, _BASELINE)
                if audit297.classify(st, kind, L)[0] == "c_rule_based"}
        assert set(rec[key]) == want, f"{key}: volume file covers {len(rec[key])} ids, class (c) has {len(want)}"
        assert all(v is not None and v >= 0 for v in rec[key].values())


# ---------------------------------------------------------------- the perineum
def test_generated_perineal_closure_is_gone_from_both_female_pages(prov):
    for key in ("base_f", "comb_f"):
        ids = {s["id"] for s in prov.structures(key, _BASELINE)}
        assert "zan_skin_perineal_closure" not in ids, f"{key} still ships the generated perineal surface closure"


def test_the_real_perineal_structures_are_still_shipped(prov):
    real = ["perineal_body", "deep_perineal_muscle_cvh", "superficial_transverse_perineal_cvh",
            "bulbospongiosus_cvh", "ischiocavernosus_cvh_l", "ischiocavernosus_cvh_r",
            "urethrovaginal_sphincter_cvh", "vagina", "clitoris_cavernous_body"]
    for key in ("own_f", "base_f", "comb_f"):
        ids = {s["id"] for s in prov.structures(key, _BASELINE)}
        miss = [r for r in real if r not in ids]
        assert miss == [], f"{key} lost real perineal structures: {miss}"


def test_the_real_perineal_structures_still_name_their_source(prov):
    for key in ("base_f", "comb_f"):
        by = {s["id"]: s for s in prov.structures(key, _BASELINE)}
        for sid in ("perineal_body", "deep_perineal_muscle_cvh", "bulbospongiosus_cvh"):
            b = by[sid]["rec"].get("procedural_badge") or ""
            assert "REAL SEGMENTATION OF ANOTHER PERSON" in b, f"{key}/{sid} lost its CVH badge"
            assert "Wu" in b and "0132226" in b, f"{key}/{sid} lost its citation"


def test_the_neighbouring_skin_says_the_perineum_is_shown_open(prov):
    for key in ("base_f", "comb_f"):
        notes = [s for s in prov.structures(key, _BASELINE)
                 if "Q297: the perineum of this page is deliberately shown OPEN" in (s["rec"].get("procedural_badge") or "")]
        assert len(notes) >= 8, f"{key}: only {len(notes)} neighbouring skin patches carry the open-perineum note"


# ---------------------------------------------------------------- the rule-based cords
def test_brachial_cords_are_badged_rule_based_with_a_volume(prov):
    for key in ("base_m", "base_f", "comb_m", "comb_f"):
        by = {s["id"]: s for s in prov.structures(key, _BASELINE)}
        for w in ("lateral", "medial"):
            for s in "lr":
                sid = f"brachial_cord_{w}_{s}"
                assert sid in by, f"{key} lost {sid}"
                r = by[sid]["rec"]
                b = r.get("procedural_badge") or ""
                assert b.startswith("RULE-BASED"), f"{key}/{sid} carries no rule-based badge"
                assert re.search(r"Volume on this page \d+\.\d+ cm3", b), f"{key}/{sid} records no volume"
                assert "NOT Z-Anatomy geometry" in (r.get("geom_src") or ""), f"{key}/{sid} still claims Z-Anatomy geometry"


def test_the_rule_built_brachial_plexus_is_no_longer_called_measured(prov):
    for key in ("own_m", "own_f"):
        h, d, kind = prov.page_html(key, _BASELINE)
        L = prov.subject_labels(h)
        shown = set()
        for st in prov.structures(key, _BASELINE):
            if "rule_nerve_q258" in (st["subject"] or ""):
                shown.add(prov.classify_source(st["subject"], st["rec"].get("procedural_badge"), L))
        assert shown == {"rule_based"}, f"{key}: the Q258 rule-built plexus is shown as {shown}"


def test_the_two_missing_subject_labels_are_in_the_template():
    import subprocess
    r = subprocess.run([sys.executable, str(REPO / "scripts/sync_subjects_q297.py"), "--check"],
                       capture_output=True, text=True, cwd=str(REPO))
    assert r.returncode == 0, r.stdout + r.stderr


# ---------------------------------------------------------------- the breasts and the fingertips
def test_the_breast_cards_carry_this_pages_own_numbers(prov):
    for key in ("base_f", "comb_f"):
        by = {s["id"]: s for s in prov.structures(key, _BASELINE)}
        for sid in ("breast_ct_l", "breast_ct_r"):
            b = by[sid]["rec"].get("procedural_badge") or ""
            assert "Q297 re-measured this page's own breast meshes" in b, f"{key}/{sid} has no Q297 re-measurement"
            assert re.search(r"left/right difference of \d+\.\d+ %", b), f"{key}/{sid} states no per-page asymmetry"
            assert "supine" in b.lower() and "will not sculpt" in b, f"{key}/{sid} does not state the supine limitation"
        for sid in ("nipple_l", "areola_l"):
            b = by[sid]["rec"].get("procedural_badge") or ""
            assert "Q297 re-measured this mesh on THIS page" in b, f"{key}/{sid} has no Q297 volume"


def test_base_f_breast_asymmetry_is_recorded_as_worse_than_her_ct(prov):
    by = {s["id"]: s for s in prov.structures("base_f", _BASELINE)}
    b = by["breast_ct_l"]["rec"]["procedural_badge"]
    m = re.search(r"left/right difference of (\d+\.\d+) %", b)
    assert m and float(m.group(1)) > 20.0, "Base F should record a left/right difference well above her CT's 13.6 %"


def test_every_hand_distal_phalanx_carries_the_fingertip_measurement(prov):
    for key in ("base_m", "base_f", "comb_m", "comb_f"):
        by = {s["id"]: s for s in prov.structures(key, _BASELINE)}
        got = [sid for sid in by if re.match(r"zan_distal_phalanx_of_\w+_finger_of_hand_[lr]$", sid)]
        assert len(got) == 10, f"{key} has {len(got)} hand distal phalanges"
        for sid in got:
            b = by[sid]["rec"].get("procedural_badge") or ""
            assert "Q297 FINGERTIP MEASUREMENT" in b, f"{key}/{sid} has no fingertip measurement"
            assert "models NO nail" in b, f"{key}/{sid} does not state the Z-Anatomy source limitation"


def test_the_page_report_records_what_was_removed():
    rep = json.loads((REPO / "data/derived/Q297_page_report.json").read_text())
    for key in ("base_f", "comb_f"):
        assert rep["pages"][key]["dropped"] == ["zan_skin_perineal_closure"]
        assert rep["pages"][key]["meshes_after"] == rep["pages"][key]["meshes_before"] - 1
    for key in ("base_m", "comb_m"):
        assert rep["pages"][key]["dropped"] == []


def test_the_pose_rigs_match_the_page_mesh_counts(prov):
    for key in prov.KEYS:
        rig = json.loads((REPO / f"data/anatomy/pose_rig_{key}.json").read_text())["rig"]
        # Q308: the rig must match the CURRENT baseline's own mesh count, full stop. This assertion used to
        # read the Q297-era page and then ADD what Q304 and Q307 spliced on -- a correction that was only
        # needed because the baseline here was pinned to `build/q297` while the rigs had moved on. Now that
        # the baseline is resolved from model.SRC it already contains those nerves, and adding them again
        # double-counted: own_m came out as 1,207 against a rig of 1,079. The per-round adjustment is gone,
        # which also means this test will not need another one each time a round adds structures.
        n = len(prov.structures(key, _BASELINE))
        assert rig["count"] == n, f"{key}: rig count {rig['count']} but the baseline page has {n} meshes"
        assert len(rig["nv"]) == rig["count"]
        assert all(0 <= e[0] < rig["count"] for e in rig["skin"]), f"{key}: a skin rig entry is out of range"
        assert all(0 <= i < rig["count"] for g in rig["rigid"] for i in g[1]), f"{key}: a rigid rig index is out of range"
