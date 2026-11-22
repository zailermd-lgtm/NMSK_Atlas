"""Q342: data for the "Related structures" families -- muscle parts, myofascial lines, innervation groups.

Schema, every entry sourced, every myofascial line carries its evidence label, every structure id present on the
Base page it is listed for (when the pages are built), rules never presented as validated, and no term the public
pages must not carry (including treatment vocabulary)."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PARTS = REPO / "data/anatomy/muscle_parts_q342.json"
LINES = REPO / "data/anatomy/myofascial_lines_q342.json"
INNERV = REPO / "data/anatomy/innervation_groups_q342.json"
DOC = REPO / "docs/Q342_groups_sources.md"
PAGE_DIRS = {"base_m": REPO / "build/q309/viewer_zan_atlas", "base_f": REPO / "build/q309/viewer_base_female"}
FORBIDDEN = ("ultrasound", "hounsfield", "t1_se", "imaging_tissues", "tissue table", "nmskultrasound", "acoustic", "mrayl", "b-mode",
             "inject", "needle", "botulinum", "toxin", "dosage")
REC = re.compile(r'\{"name":"[^"]*","id":"([^"]+)","side":"\w*","sys":"[a-z_]+"')
BODIES = ("base_m", "base_f")
SIDES = ("r", "l", "mid")


def _load(p):
    return json.loads(p.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def parts():
    return _load(PARTS)


@pytest.fixture(scope="module")
def lines():
    return _load(LINES)


@pytest.fixture(scope="module")
def inn():
    return _load(INNERV)


@pytest.fixture(scope="module")
def page_ids():
    out = {}
    for b, d in PAGE_DIRS.items():
        cand = [d / "index.html"] + sorted(d.glob("atlas_viewer_*.html"))
        f = next((c for c in cand if c.exists()), None)
        if f is None:
            pytest.skip("Base pages not built (build/ is gitignored)")
        out[b] = set(REC.findall(f.read_text(encoding="utf-8", errors="replace")))
        assert len(out[b]) > 3000, (b, len(out[b]))
    return out


def _structs(obj):
    """Yield every {base_m: {r,l,mid}, base_f: ...} dict found anywhere in obj."""
    if isinstance(obj, dict):
        if set(obj) == set(BODIES) and all(isinstance(v, dict) and set(v) == set(SIDES) for v in obj.values()):
            yield obj
        else:
            for v in obj.values():
                yield from _structs(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _structs(v)


# ---------------------------------------------------------------- schema
def test_schemas(parts, lines, inn):
    assert parts["schema"] == "nmsk.muscle_parts.v1"
    assert lines["schema"] == "nmsk.myofascial_lines.v1"
    assert inn["schema"] == "nmsk.innervation_groups.v1"
    for d in (parts, lines, inn):
        assert d["round"] == "Q342" and d["doc"] and d["references"]


def test_parts_schema_and_sources(parts):
    statuses = {"separate_mesh", "separate_mesh_rule_based", "rule", "not_delimitable", "missing_on_page"}
    seen = set()
    for m in parts["muscles"]:
        for p in m["parts"]:
            pid = f"{m['muscle_id']}.{p['id']}"
            assert pid not in seen, pid
            seen.add(pid)
            assert p["refs"], pid
            assert all(r in parts["references"] for r in p["refs"] + (p.get("nerve_source") or [])), pid
            assert p["verification"] in ("verified", "verified_book", "unverified_textbook"), pid
            body = p["body"]
            assert body["status"] in statuses, pid
            if body["status"] == "rule":
                assert body["rule"]["name"] in parts["rules"], pid
                assert parts["rules"][body["rule"]["name"]]["validated"] is False, pid  # never shown as anatomy
            if body["status"] == "not_delimitable":
                assert body.get("reason"), pid
    must = {"pectoralis_major", "deltoid", "trapezius", "latissimus_dorsi", "triceps_brachii", "biceps_brachii", "rectus_femoris",
            "vastus_medialis", "biceps_femoris", "gluteus_maximus", "gluteus_medius", "gluteus_minimus", "adductor_magnus", "gastrocnemius",
            "soleus", "serratus_anterior", "rectus_abdominis", "external_oblique", "internal_oblique", "erector_spinae",
            "sternocleidomastoid", "masseter", "temporalis", "subscapularis", "supinator", "flexor_digitorum_superficialis",
            "flexor_digitorum_profundus", "pronator_teres", "iliopsoas"}
    assert must <= {m["muscle_id"] for m in parts["muscles"]}


def test_parts_counts_consistent(parts):
    c = parts["counts"]
    assert c["parts"] == sum(len(m["parts"]) for m in parts["muscles"])
    for b in BODIES:
        assert sum(c["per_body"][b].values()) == c["parts"]


def test_lines_evidence_and_sources(lines):
    labels = {"strong", "moderate", "none", "not_examined"}
    for ln in lines["lines"]:
        ev = ln["evidence"]
        assert ev["label"] in labels and ev["label_text"] and ev["refs"], ln["id"]
        assert "wilke2016" in ev, ln["id"]
        assert ln["composition_refs"], ln["id"]
        assert all(r in lines["references"] for r in ln["composition_refs"] + ev["refs"]), ln["id"]
        assert ln["stations"] and all(s["side"] in ("S", "O", "mid", "B") for s in ln["stations"]), ln["id"]
        if "myers_at" in ln["composition_refs"]:
            assert ln["verify_against_book"] is True, ln["id"]  # the book was not opened
    by = {ln["id"]: ln["evidence"]["label"] for ln in lines["lines"]}
    assert by["superficial_back_line"] == "strong" and by["superficial_front_line"] == "none"
    assert by["spiral_line"] == "moderate" and by["lateral_line"] == "moderate"
    assert by["deep_front_line"] == "not_examined"
    hz = lines["sub_choices"]["horizontal"]
    assert hz["members"] == [] and hz["status"] == "not_offered" and hz["why"]  # no invented horizontal line
    for k, sc in lines["sub_choices"].items():
        assert all(m in by for m in sc["members"]), k


def test_innervation_sources(inn):
    refs = inn["references"]
    for k, m in inn["muscles"].items():
        assert m["sources"] and all(s in refs for s in m["sources"]), k
    fam = inn["families"]
    for lv, v in fam["root"]["levels"].items():
        assert re.match(r"^(C[1-8]|T(1[0-2]|[1-9])|L[1-5]|S[1-5])$", lv)
        assert all(e["muscle_id"] in inn["muscles"] for e in v["members"]), lv
    flagged = {m for v in fam["root"]["levels"].values() if v.get("isncsci_key_muscles") for m in v["isncsci_key_muscles"]["members"]}
    assert flagged <= set(inn["muscles"])
    for n, v in fam["peripheral"]["nerves"].items():
        assert all(e["muscle_id"] in inn["muscles"] for e in v["all_members"]), n
    for p in fam["central"]["patterns"]:
        assert p["refs"] and all(r in refs for r in p["refs"]), p["id"]
        assert p["rule_based_membership"] is True, p["id"]
        if p["status"] == "ok":
            assert p["members"] and p["components"], p["id"]
            assert all(c["source"] in refs for c in p["components"]), p["id"]
        else:
            assert not p["members"], p["id"]
        for e in p["members"]:
            assert e["tier"] in ("named_in_guide", "guide_section_and_action", "action_only", "guide_section_only"), p["id"]


# ---------------------------------------------------------------- page ids
@pytest.mark.parametrize("name", ["parts", "lines", "inn"])
def test_ids_on_their_page(name, parts, lines, inn, page_ids):
    data = {"parts": parts, "lines": lines, "inn": inn}[name]
    missing = []
    n = 0
    for s in _structs(data):
        for b in BODIES:
            for side in SIDES:
                for i in s[b][side]:
                    n += 1
                    if i not in page_ids[b]:
                        missing.append((b, i))
    assert n > 0
    assert not missing, missing[:20]


def test_body_specific_ids_are_listed_per_body(parts, lines, inn, page_ids):
    """An id listed for one body only must be absent from the other page (i.e. genuinely body-specific)."""
    wrong = []
    for d in (parts, lines, inn):
        for s in _structs(d):
            m = {i for side in SIDES for i in s["base_m"][side]}
            f = {i for side in SIDES for i in s["base_f"][side]}
            wrong += [("base_f", i) for i in m - f if i in page_ids["base_f"]]
            wrong += [("base_m", i) for i in f - m if i in page_ids["base_m"]]
    assert not wrong, wrong[:20]


# ---------------------------------------------------------------- public vocabulary
@pytest.mark.parametrize("path", [PARTS, LINES, INNERV, DOC])
def test_no_forbidden_terms(path):
    text = path.read_text(encoding="utf-8").lower()
    hits = [w for w in FORBIDDEN if w in text]
    assert not hits, (path.name, hits)


def test_q348_lines_and_horizontal():
    d = json.loads(LINES.read_text(encoding="utf-8"))
    fam = {l["id"]: l["author_family"] for l in d["lines"]}
    assert sum(1 for v in fam.values() if v == "myers") == 12 and sum(1 for v in fam.values() if v == "tittel") == 3
    assert d["sub_choices"]["horizontal"]["status"] == "not_offered"
    for l in d["lines"]:
        if l["author_family"] == "tittel":
            assert "diagonal_spiral" in l["sub_choices"] and l["crosses_midline"]
            assert {s["side"] for s in l["stations"]} >= {"S", "O"}
