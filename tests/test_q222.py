"""Q222: systematic extension of the sourced parts table (data/anatomy/structure_parts.json) + geometry re-run on the Q217-era bodies."""
import json
import re
from collections import Counter
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
TABLE = REPO / "data/anatomy/structure_parts.json"
COV = REPO / "data/derived/Q219_parts_coverage.json"
IDX = REPO / "data/derived/Q219_structure_ids.json"
DER = REPO / "data/derived"
BODIES = ["vhm", "vhf", "zan_m", "zan_f"]
CLINICAL = re.compile(r"motor point|needle|trigger point|nerve block|injection technique|dangerous|hazard", re.I)


@pytest.fixture(scope="module")
def table():
    return json.loads(TABLE.read_text())


@pytest.fixture(scope="module")
def q222(table):
    return [p for p in table["parts"] if p["added_in"] == "Q222"]


def _by_struct(table):
    d = {}
    for p in table["parts"]:
        d.setdefault(p["structure_id"], []).append(p)
    return d


def test_every_row_tagged_and_ids_unique(table):
    assert all(re.match(r"^Q\d+$", p["added_in"]) for p in table["parts"])      # Q219 / Q222 / a later round's own rows_q<N>_*.py module
    ids = [p["id"] for p in table["parts"]]
    assert len(ids) == len(set(ids))
    c = Counter(p["added_in"] for p in table["parts"])
    assert c["Q219"] == 347, "Q219 rows must be untouched"
    assert c["Q222"] >= 150


def test_at_least_80_new_structures(table):
    old = {p["structure_id"] for p in table["parts"] if p["added_in"] == "Q219"}
    new = {p["structure_id"] for p in table["parts"]} - old
    assert len(old) == 101
    assert len(new) >= 80, len(new)


def test_all_q222_rows_are_journal_verified(table, q222):
    refs = table["references"]
    for p in q222:
        assert p["verification"] == "verified", p["id"]
        assert p["refs"] and all(r in refs for r in p["refs"]), p["id"]
        assert any(refs[r]["kind"] == "journal" for r in p["refs"]), p["id"]
        assert p["citation"].strip() and "PMID" in p["citation"], p["id"]
        assert p["part_type"] in table["part_types"]


def test_q222_references_are_pubmed_checked(table, q222):
    used = {r for p in q222 for r in p["refs"]}
    new_refs = {k: v for k, v in table["references"].items() if v.get("verified") == "pubmed-2026-10-12"}
    assert len(new_refs) >= 60
    for k, v in new_refs.items():
        assert v["kind"] == "journal" and re.fullmatch(r"\d{4,9}", str(v["pmid"])), k
        assert v["basis"].startswith("abstract:"), k
        assert v["citation"].strip(), k
        assert v["doi"] is None or v["doi"].startswith("10."), k
    pm = [v["pmid"] for v in table["references"].values() if v["kind"] == "journal"]
    assert len(pm) == len(set(pm)), "one registry entry per PubMed record"
    assert set(table["references"]) >= used


def test_no_unused_references(table):
    used = {r for p in table["parts"] for r in p["refs"]} | {c["ref"] for s in table["part_sets"] for c in s["reported_counts"]}
    assert set(table["references"]) == used


def test_no_clinical_content_in_new_rows(q222):
    for p in q222:
        txt = " ".join(str(p.get(k) or "") for k in ("name", "description", "note", "evidence", "variability"))
        assert not CLINICAL.search(txt), (p["id"], CLINICAL.search(txt).group(0))


def test_case_reports_are_flagged_as_such(q222, table):
    for p in q222:
        if any("case report" in (table["references"][r]["basis"].lower()) for r in p["refs"]) and len(p["refs"]) == 1:
            assert "case report" in ((p.get("variability") or "") + (p.get("evidence") or "")).lower(), p["id"]


def test_structure_ids_resolve(table):
    ids = json.loads(IDX.read_text())
    base = lambda i: re.sub(r"_(r|l)$", "", re.sub(r"_zfill.*$", "", i))
    own = {b: {base(i) for i in ids[b]["ids"]} for b in BODIES}
    for p in table["parts"]:
        assert p["resolved_in"], p["id"]
        # maps_to points at ids that exist in the snapshot of that body
        for b in BODIES:
            for i in p["maps_to"]["structure_ids"][b] + p["maps_to"]["part_ids"][b]:
                assert i in ids[b]["ids"], (p["id"], b, i)


def test_snapshot_is_the_q217_era_bodies():
    ids = json.loads(IDX.read_text())
    assert ids["vhm"]["source"].endswith("viewer_m_hr_q217/bundle.json")
    assert ids["zan_m"]["source"].startswith("build/q221/")
    assert ids["zan_f"]["source"].startswith("build/q220/")
    assert "anconeus_l" in ids["vhm"]["ids"], "Q217 own male carries the added left forearm muscles"


def test_disputed_counts_recorded(table):
    sets = {s["id"]: s for s in table["part_sets"]}
    assert len({c["n"] for c in sets["iliolumbar_ligament.bands"]["reported_counts"]}) >= 4       # 1 / 2 / 3 / 5
    assert {c["n"] for c in sets["coracoacromial_ligament.bands"]["reported_counts"]} == {1, 2, 3}
    assert {c["n"] for c in sets["adductor_magnus.parts"]["reported_counts"]} == {2, 4}
    assert {c["n"] for c in sets["supinator.layers"]["reported_counts"]} == {1, 2}
    assert {c["n"] for c in sets["temporalis.parts"]["reported_counts"]} == {1, 3}
    assert {c["n"] for c in sets["articularis_genus.layers"]["reported_counts"]} == {3, 7}
    assert {c["n"] for c in sets["flexor_digiti_minimi_hand.bellies"]["reported_counts"]} == {0, 1, 2}
    for s in table["part_sets"]:
        for c in s["reported_counts"]:
            assert c["ref"] in table["references"]
        assert s["member_part_ids"] or s["id"] in ("biceps_long_head.attachment_types", "fibularis_tendon.variants"), s["id"]


def test_priority_regions_covered(table):
    d = _by_struct(table)
    must = ["pectoralis_minor", "latissimus_dorsi", "adductor_magnus", "tibialis_anterior", "flexor_pollicis_brevis", "abductor_pollicis_brevis", "opponens_pollicis",
            "flexor_digiti_minimi_brevis_hand", "diaphragm", "transversus_abdominis", "obturator_internus", "temporalis", "supinator",
            "coracoacromial_ligament", "iliolumbar_ligament", "popliteofibular_ligament", "annular_ligament", "ligamentum_nuchae", "transverse_ligament_of_knee",
            "palmar_aponeurosis", "guyons_canal", "bicipital_aponeurosis", "peroneal_retinaculum", "colles_fascia", "transversalis_fascia", "extensor_retinaculum_ankle",
            "glenoid_labrum", "tfcc_disc", "tmj_disc", "biceps_brachii_tendon_complex", "fibularis_tendon_complex"]
    for m in must:
        assert m in d, m
    assert len(d["adductor_magnus"]) >= 5 and len({p["part_type"] for p in d["adductor_magnus"]}) >= 2
    assert len([p for p in d["iliolumbar_ligament"] if p["added_in"] == "Q222"]) >= 3


def test_coverage_file_consistent(table):
    cov = json.loads(COV.read_text())
    assert cov["parts_total"] == len(table["parts"]) == cov["by_verification"]["verified"] + cov["by_verification"]["unverified"]
    assert cov["structures_with_parts"] == len({p["structure_id"] for p in table["parts"]})
    q = cov["q222"]
    assert q["structures_before"] == 101 and q["structures_after"] == cov["structures_with_parts"]
    assert len(q["structures_added"]) == q["structures_after"] - q["structures_before"] >= 80
    assert q["parts_added"] == sum(1 for p in table["parts"] if p["added_in"] == "Q222")
    assert cov["entity_classes"]["muscles"]["with_parts"] >= 80          # was 42 of 220
    assert cov["entity_classes"]["ligaments"]["with_parts"] >= 30        # was 21 of 51
    assert cov["entity_classes"]["fascia"]["with_parts"] >= 28           # was 18 of 95
    assert cov["entity_classes"]["tendons"]["with_parts"] >= 13          # was 11 of 26
    assert cov["entity_classes"]["cartilage"]["with_parts"] >= 6         # was 3 of 46
    assert cov["entity_classes"]["bursae"]["with_parts"] == 0            # skipped on purpose (see PROJECT_STATE Q222)
    # sub-lists agree with the counts
    for k, v in cov["entity_classes"].items():
        assert len(v["with_parts_ids"]) == v["with_parts"] and v["with_parts"] + v["without_parts"] == v["entities"]


# ---------------------------------------------------------------- geometry re-run
@pytest.mark.parametrize("key,fname,src", [("vhm", "Q219_parts_vhm.json", "viewer_m_hr_q217"), ("vhf", "Q219_parts_vhf.json", "viewer_f_hr_q216"),
                                           ("zan_m", "Q219_parts_zan_m.json", "q221/viewer_zan_vhm"), ("zan_f", "Q219_parts_zan_f.json", "q220/viewer_zan_female"),
                                           ("zbase_m", "Q220_parts_zbase_m.json", "viewer_zan_atlas"), ("zbase_f", "Q220_parts_zbase_f.json", "viewer_base_female")])
def test_geometry_files_cover_every_part_and_never_claim_measured(table, key, fname, src):
    g = json.loads((DER / fname).read_text())
    assert src in json.dumps(g.get("source"))
    all_ids = {p["id"] for p in table["parts"]}
    placed = {x["part_id"] for x in g["placed"]}
    text_only = {x["part_id"] for x in g["text_only"]}
    # a part can be placed on one side only (then it is also listed as text_only with partial=True)
    assert all_ids <= placed | text_only, sorted(all_ids - placed - text_only)[:5]
    assert placed <= all_ids
    for x in g["placed"]:
        assert x["source_class"] in ("rule_based", "z_fill"), x["part_id"]
        assert x["source_class"] != "measured"
        if key.startswith("zbase") and x["rule"] == "z_part_mesh":
            # unfitted reference body: no fit badge -> the error is "not stated" and the extent of the part mesh is given instead
            assert x["error_bound_mm"] is None and x["bbox_mm"] and x["error_basis"].strip(), x["part_id"]
        else:
            assert x.get("error_bound_mm") is not None and x["error_bound_mm"] >= 0, x["part_id"]
        assert len(x["position_mm"]) == 3
    for x in g["text_only"]:
        assert x["reason"].strip()


def test_q222_end_snap_requests_obey_the_guard(table):
    """Q222 rows asked for end_snap_bone placements only where the origin / insertion is the muscle's single bony end; where the mesh end is not within
    the tolerance of the bone the part must stay text-only with the stated distance."""
    req = [p["id"] for p in table["parts"] if p["added_in"] == "Q222" and (p.get("geometry") or {}).get("rule") == "end_snap_bone"]
    assert len(req) >= 3
    for key, fname in (("vhm", "Q219_parts_vhm.json"), ("zan_m", "Q219_parts_zan_m.json"), ("zbase_m", "Q220_parts_zbase_m.json")):
        g = json.loads((DER / fname).read_text())
        placed = {(x["part_id"], x["side"]): x for x in g["placed"]}
        for pid in req:
            for (p2, side), x in placed.items():
                if p2 == pid:
                    assert x["rule"] == "end_snap_bone" and x["gap_mm"] <= 10.0 + 1e-6, (key, pid)
            if not any(p2 == pid for p2, _ in placed):
                why = [t for t in g["text_only"] if t["part_id"] == pid]
                assert why and why[0]["reason"], (key, pid)


def test_q222_new_placements_are_few_and_labelled(table):
    """The point of Q222 is sourced text; placements only where a Q219 rule applies. Count and classes are reported, not hidden."""
    g = {k: json.loads((DER / f).read_text()) for k, f in (("vhm", "Q219_parts_vhm.json"), ("zan_m", "Q219_parts_zan_m.json"))}
    for k, v in g.items():
        assert v["counts"]["placed"] == len(v["placed"])
        assert set(v["counts"]["placed_by_class"]) <= {"rule_based", "z_fill"}
    assert g["vhm"]["counts"]["placed_by_class"].keys() == {"rule_based"}   # own bodies never carry Z-fill positions
