"""Q348 reference pass: every fact taken from the owner's books carries book + page, and the public data files this round
touched carry none of the banned words."""
import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
DA = REPO / "data/anatomy"
sys.path.insert(0, str(REPO / "scripts/anatomy/q342"))
import books_q348 as B  # noqa: E402

BANNED = ["ultrasound", "hounsfield", "t1_se", "imaging_tissues", "tissue table", "nmskultrasound", "acoustic", "mrayl", "b-mode"]
TOUCHED = ["myofascial_lines_q342.json", "innervation_groups_q342.json", "muscle_parts_q342.json", "synonyms_q306.json"]
BOOK_KEYS = {"mannan2017", "sontakke2023", "haviarova2024", "carp2015", "myers2015", "richter2015", "grays_atlas"}


def load(name):
    return json.loads((DA / name).read_text(encoding="utf-8"))


def is_page(p):
    return isinstance(p, int) and p > 0


@pytest.mark.parametrize("name", TOUCHED)
def test_no_banned_words(name):
    s = (DA / name).read_text(encoding="utf-8").lower()
    assert not [w for w in BANNED if w in s], name


def test_books_module_clean_and_cited():
    s = (REPO / "scripts/anatomy/q342/books_q348.py").read_text(encoding="utf-8").lower()
    assert not [w for w in BANNED if w in s]
    for k, b in B.BOOKS.items():
        assert re.search(r"(19|20)\d\d", b["citation"]), k          # year
        assert b["short"] and b["opened"], k
    for mid, entries in B.ROOTS.items():
        for e in entries:
            assert e["ref"] in B.BOOKS and is_page(e["page"]) and e["nerve"], mid
    for v in B.VARIATIONS:
        assert v["ref"] in B.BOOKS and v["pages"] and all(is_page(p) for p in v["pages"]) and v["fact"], v["id"]
    for (mid, pid), b in B.BOOK_PARTS.items():
        assert b["ref"] in B.BOOKS and is_page(b["page"]) and b["fact"], (mid, pid)
    for mid, a in B.ADOPT.items():
        assert a["ref"] in B.BOOKS and is_page(a["page"]) and a["was"] and a["roots_text"], mid


def test_innervation_book_checks():
    d = load("innervation_groups_q342.json")
    refs = d["references"]
    n = 0
    for mid, m in d["muscles"].items():
        b = m.get("book_check_q348")
        if not b:
            continue
        n += 1
        assert b["status"] in ("agrees", "differs", "nerve_only"), mid
        for e in b["entries"]:
            assert e["ref"] in refs and e["ref"] in BOOK_KEYS and is_page(e["page"]), mid
            assert e["ref"] in m["sources"], mid
        if b["status"] == "differs" and b.get("books_levels"):
            assert m["roots_range_across_sources"] and "p. " in m["roots_range_across_sources"], mid
    assert n >= 140
    for mid in d["counts"]["corrected_q348"]:
        c = d["muscles"][mid]["corrected_q348"]
        assert c["ref"] in refs and is_page(c["page"]) and c["was"] != c["now"], mid
    # the one correction: serratus posterior superior is T2-T5 (Mannan p. 407)
    sps = d["muscles"]["serratus_posterior_superior"]
    assert sps["motor_levels"] == ["T2", "T3", "T4", "T5"] and "mannan2017" in sps["sources"]
    t1 = [e["muscle_id"] for e in d["families"]["root"]["levels"]["T1"]["members"]]
    assert "serratus_posterior_superior" not in t1
    for v in d["variations_q348"]:
        assert v["ref"] in refs and all(is_page(p) for p in v["pages"]), v["id"]
        for mid in v["muscles"]:
            assert v["id"] in d["muscles"][mid]["variation_notes_q348"]


def test_lines_book_checks():
    d = load("myofascial_lines_q342.json")
    refs = d["references"]
    assert {"myers2015", "richter2015"} <= set(refs)
    for ln in d["lines"]:
        bc = ln.get("book_check")
        if ln["author_family"] == "myers":
            assert bc and bc["ref"] == "myers2015" and bc["pages"].startswith("PDF p") and bc["confirmed"], ln["id"]
            assert bc["status"] in ("partly_confirmed", "course_only")
            assert ln["verify_against_book"] is True       # the chapter lists no stations: the flag stays
        if ln["author_family"] == "tittel":
            assert ln["composition_refs"] == ["richter2015"] and ln["evidence"]["label"] == "not_examined"
    lat = next(l for l in d["lines"] if l["id"] == "lateral_line")
    assert any("gluteus_medius" in s["page_bases"] for s in lat["stations"])
    hz = d["sub_choices"]["horizontal"]
    assert hz["status"] == "not_offered" and not hz["members"] and "myers2015" in hz["refs"]


def test_parts_book_facts():
    d = load("muscle_parts_q342.json")
    refs = d["references"]
    n = 0
    for m in d["muscles"]:
        for p in m["parts"]:
            b = p.get("book_q348")
            if b:
                n += 1
                assert b["ref"] in refs and is_page(b["page"]) and b["ref"] in p["refs"], (m["muscle_id"], p["id"])
            if p["verification"] == "verified_book":
                assert b, (m["muscle_id"], p["id"])
    assert n == len(B.BOOK_PARTS)


def test_q336_records_cite_pages():
    syn = load("synonyms_q306.json")
    for k in ("mannan2017", "grays_atlas"):
        assert re.search(r"\bpp?\. \d+", syn["sources"][k]), k
    rows = {r["name"]: r for r in syn["cited_but_not_shipped"]}
    pm = rows["Perineal membrane"]
    assert "mannan2017" in pm["src"] and "INFERIOR FASCIA" in pm["why"]
    assert "superficial branches" in rows["Perineal nerve"]["why"]
