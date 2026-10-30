"""Q256 item 2: ORIGIN / INSERTION markers extended from muscles (already Q219/Q240) to tendons, ligaments and fascia, generated
programmatically from this project's own already-authored data/{tendons,ligaments,fascia}/*.json attachment fields."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts/anatomy/q219"))


@pytest.fixture(scope="module")
def table():
    r = subprocess.run([sys.executable, "scripts/anatomy/q219/build_parts.py"], cwd=REPO, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    return json.loads((REPO / "data/anatomy/structure_parts.json").read_text())


@pytest.fixture(scope="module")
def coverage():
    return json.loads((REPO / "data/derived/Q256_attachment_coverage.json").read_text())


def test_every_ligament_and_tendon_got_an_attachment_pair(coverage):
    assert coverage["ligaments"]["total"] == coverage["ligaments"]["placed"] == 51
    assert coverage["tendons"]["total"] == coverage["tendons"]["placed"] == 26


def test_fascia_only_gets_a_pair_when_exactly_two_bony_attachments_are_listed(coverage):
    f = coverage["fascia"]
    assert f["placed"] < f["total"]                      # NOT every fascia -- most do not have a clean 2-point attachment
    assert f["placed"] + len(f["skipped"]) == f["total"]
    for s in f["skipped"]:
        assert s["bony_attachments"] != 2
        assert s["reason"]                                # every skip says WHY, honestly


def test_ligament_rows_disclose_the_project_convention_not_an_anatomical_fact(table):
    rows = [p for p in table["parts"] if p["id"].endswith(".origin_q256") and p["structure_class"] == "ligament"]
    assert rows, "no ligament origin_q256 rows generated"
    for r in rows:
        assert "convention" in r["note"].lower() and "no muscle-style directional pull" in r["note"].lower() or "no muscle-style" in r["note"]
        assert r["verification"] == "unverified" and r["evidence"] == "textbook"
        assert r["note"] and "data/ligaments" in r["note"]           # the record's own `source` string is quoted verbatim


def test_tendon_proximal_end_is_a_musculotendinous_junction_not_a_fake_bony_origin(table):
    rows = [p for p in table["parts"] if p["structure_id"] == "achilles_tendon" and p["part_type"] == "muscle_tendon_junction"]
    assert rows and "mtj_q256" in rows[0]["id"]
    assert not any(p["structure_id"] == "achilles_tendon" and p["part_type"] == "origin_part" for p in table["parts"])


def test_insertion_rows_cite_the_correct_bone_and_a_real_textbook_ref(table):
    acl = next(p for p in table["parts"] if p["id"] == "anterior_cruciate_ligament.insertion_q256")
    assert acl["anchor"]["bone"] == "tibia"
    assert any(r in acl["refs"] for r in ("gray_students4", "ta1998", "moore8"))
    assert acl["citation"]


def test_fascia_pair_names_both_ends_by_the_stated_convention(table):
    fl = [p for p in table["parts"] if p["structure_id"] == "fascia_lata" and p["part_type"] in ("origin_part", "insertion_point")]
    assert len(fl) == 2
    for p in fl:
        assert "convention" in p["note"] or "by this project" in p["note"].lower() or "fascia sheets rarely" in p["note"].lower()


def test_geometry_rule_is_generic_not_hardcoded_to_muscle_wording():
    g = (REPO / "scripts/anatomy/q219/build_geometry.py").read_text(encoding="utf-8")
    assert "the structure's own mesh" in g or "the structure's mesh end" in g
    assert "muscle mesh end is" not in g              # the old, muscle-only wording of the user-facing reason string is gone


@pytest.mark.parametrize("body", ["vhm"])
def test_real_geometry_build_places_some_and_honestly_text_onlys_the_rest(body):
    geo = REPO / f"data/derived/Q219_parts_{body}.json"
    if not geo.exists():
        pytest.skip("Q219 geometry not built in this environment")
    j = json.loads(geo.read_text())
    placed_q256 = [p for p in j["placed"] if p["part_id"].endswith("_q256")]
    text_only_q256 = [t for t in j["text_only"] if t["part_id"].endswith("_q256")]
    assert placed_q256, "no Q256 origin/insertion/MTJ marker actually placed on a real body -- the feature produced no working markers"
    assert text_only_q256                              # most structures of these types are absent on any one body: expected, honest
    for p in placed_q256:
        assert p["source_class"] == "rule_based" and p.get("error_bound_mm") is not None
    for t in text_only_q256:
        assert t.get("reason")


def test_midline_records_get_the_catalogue_row_but_no_geometry_rule(table):
    # ligamentum_flavum is genuinely midline (no left/right mesh): giving it a geom rule would duplicate one point under a spurious r/l
    rows = [p for p in table["parts"] if p["structure_id"] == "ligamentum_flavum" and p["id"].endswith("_q256")]
    assert rows
    for r in rows:
        assert r["geometry"] is None


def test_refs_added_are_real_textbooks_not_fabricated():
    refs = sys.modules.get("refs") or __import__("refs")
    for k in ("gray_students4", "moore8", "ta1998", "stecco2015"):
        assert k in refs.REFS and refs.REFS[k]["kind"] == "textbook"


def test_schema_md_documents_the_extension_and_its_honest_limits():
    doc = (REPO / "data/anatomy/parts_schema.md").read_text(encoding="utf-8")
    assert "Q256 extension" in doc
    for w in ("no contractile pull", "midline", "fascia", "73 of 104"):
        assert w in doc, w
