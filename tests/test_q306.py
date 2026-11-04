"""Q306: data-level assertions for the search COVERAGE layer -- the group names, the concepts, the new
synonyms and the reference list the audit measured.

The headline assertion is the one the brief asked for: EVERY term in the new data resolves to a structure
that really exists on at least one of the six pages, OR to an honest explanation -- never to silence and
never to a different structure presented as the answer. The owner's three cases are pinned individually
(psoas minor, pelvic tilt, a functional group name), and so is the defect class that produced the two
wrong answers Q306 found, so a later round cannot quietly undo any of it.

Measured in docs/research/Q306_search_coverage_audit.md: 115 of the 342 reference terms reached something
before this round, 342 of 342 after.
"""
from __future__ import annotations
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
Q298 = REPO / "scripts/anatomy/q298"
sys.path.insert(0, str(Q298))

DATA = REPO / "data/anatomy"
DERIVED = REPO / "data/derived"
KEYS = ["own_m", "own_f", "base_m", "base_f", "comb_m", "comb_f"]
# Q308: ASK for the baseline instead of listing it. This literal said `build/q306`, a directory that was
# never persisted, so the fallback list silently chose `build/q305` -- and every page assertion in this file
# has been measuring a build three rounds old while reporting success. `scripts/anatomy/q241/model.SRC` is
# the one place that declares the current baseline; the list stays only as a backstop.
def _baseline_build():
    import sys as _s
    _p = str(REPO / "scripts/anatomy/q241")
    if _p not in _s.path:
        _s.path.insert(0, _p)
    import model as _m
    r = REPO / _m.build_root()
    if r.is_dir():
        return r
    for alt in ("q308", "q307", "q306", "q305", "q304", "q303"):
        if (REPO / "build" / alt).is_dir():
            return REPO / "build" / alt
    return r


BUILD = _baseline_build()
pytestmark = pytest.mark.skipif(not BUILD.is_dir(), reason="no viewer build on disk")


# ---------------------------------------------------------------- fixtures
@pytest.fixture(scope="module")
def syn():
    return json.loads((DATA / "synonyms_q306.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def gnames():
    return json.loads((DATA / "groups_q306.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def concepts():
    return json.loads((DATA / "concepts_q306.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def newgroups():
    return json.loads((DATA / "muscle_groups_q306.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def reference():
    return json.loads((DATA / "search_reference_q306.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def pages():
    import pagedata as P
    return {k: P.structures(k, BUILD) for k in KEYS}


@pytest.fixture(scope="module")
def index(pages):
    import pagedata as P
    out = {}
    for k, ss in pages.items():
        ix = {}
        for i, s in enumerate(ss):
            for key in P.keys_of(s["name"]):
                ix.setdefault(key, []).append(i)
        out[k] = ix
    return out


@pytest.fixture(scope="module")
def compiled():
    return {k: json.loads((DERIVED / f"Q306_search_{k}.json").read_text(encoding="utf-8")) for k in KEYS}


def _resolves(index, target):
    import pagedata as P
    t = P.fold(target)
    got = []
    for k, ix in index.items():
        c = list(ix.get(t, [])) + list(ix.get(t + " muscle", []))
        if t.endswith(" muscle"):
            c += list(ix.get(t[:-7], []))
        rx = re.compile(r"(^|\b)(head|part) of " + re.escape(t) + r"( muscle)?$")
        for key, v in ix.items():
            if rx.search(key):
                c += v
        if c:
            got.append(k)
    return got


# ---------------------------------------------------------------- THE HEADLINE
def test_every_new_term_resolves_to_a_structure_or_to_an_explanation(syn, index):
    """Q298's rule, carried forward: nothing in the data may point at nothing."""
    dead = []
    for e in syn["entries"]:
        if not any(_resolves(index, t) for t in e["targets"]):
            dead.append(("entry", e["canon"], e["targets"]))
    for f in syn["families"]:
        hit = any(re.search(f["re"], n) for k in index for n in index[k])
        if not hit:
            dead.append(("family", f["canon"], f["re"]))
    assert not dead, dead


def test_every_new_abbreviation_reaches_a_real_structure(syn, index):
    orphan = []
    for e in syn["entries"]:
        if not e["abbr"]:
            continue
        if not any(_resolves(index, t) for t in e["targets"]):
            orphan += [(a, e["canon"]) for a in e["abbr"]]
    assert not orphan, orphan


def test_cited_but_not_shipped_names_really_are_absent(syn, index):
    """An explanation may only be offered for something that genuinely does not ship -- otherwise the page
    would tell the user a structure is missing while it is right there. This is the check that caught four
    of Q302's gap entries being out of date (nipple, areola, Cooper's ligaments, nail plate).

    Q308: this assertion is kept, but it is NOT the guard. It tests whether the query RESOLVES through the
    alias table, and a structure that ships under a name no alias connects to the query resolves to nothing
    while sitting on the screen -- which is how the pubic symphysis, the retrocalcaneal bursa and the TFCC
    came to be DENIED on three cards. The real guard is the PRESENCE check in
    tests/test_q308.py::test_no_absence_entry_denies_a_structure_that_is_on_the_page, which reads the six
    pages' own structure lists (name, Latin and id). Do not treat this test's passing as evidence again."""
    wrong = []
    for n in syn["cited_but_not_shipped"]:
        if n.get("corrected_by") == "Q308":
            continue          # now an alias onto the shipping mesh; the builder's per-page guard handles it
        for t in [n["name"]] + n["syn"]:
            got = _resolves(index, t)
            if got:
                wrong.append((n["name"], t, got))
    assert not wrong, wrong


def test_every_explanation_offers_structures_that_do_exist(syn, index):
    bad = []
    for n in syn["cited_but_not_shipped"]:
        assert n["offer"], n["name"]
        for o in n["offer"]:
            if not _resolves(index, o):
                bad.append((n["name"], o))
    assert not bad, bad


# ---------------------------------------------------------------- the owner's three cases
def test_psoas_minor_is_recorded_as_a_real_absence_with_its_sources(syn, index, pages):
    """Q308 CHANGED WHAT IS TRUE HERE, and this test says so rather than being deleted.

    Q306 recorded the psoas minor as an absence in every source we hold, and that was correct. Q308 then BUILT
    it, rule-based, on each page's own T12 and L1 bodies and its own pecten pubis -- so it now SHIPS on the
    four Z pages (hidden by default, labelled "not demonstrated on this body") and is still genuinely absent
    on the two Imaging pages, whose engine has no hidden-by-default flag. What has NOT changed, and is still
    pinned below, is that no SOURCE holds it -- the upstream catalogue still has none, which is exactly why it
    had to be built rather than imported -- and that the prevalence claim is cited rather than asserted."""
    rows = [n for n in syn["cited_but_not_shipped"] if n["name"] == "Psoas minor"]
    assert len(rows) == 1, "psoas minor must be declared exactly once"
    r = rows[0]
    assert r.get("built_by") == "Q308", "the entry must say that Q308 built it"
    # it is absent exactly where it is not shipped, and present exactly where it is
    for k, ss in pages.items():
        hits = [s["name"] for s in ss
                if "psoas minor" in (s["name"] + " " + (s["latin"] or "")).lower()]
        if k.startswith("own"):
            assert not hits, (k, hits)          # the Imaging pages: still genuinely absent
        else:
            assert hits, (k, "Q308 ships the psoas minor on the four Z pages")
    # NO SOURCE holds it: still true, and still the reason it had to be built rather than imported
    inv = json.loads((DERIVED / "zanatomy_inventory.json").read_text(encoding="utf-8"))
    assert not [o for o in inv["objects"] if "psoas minor" in o["name"].lower()]
    # the prevalence claim is cited, not asserted
    assert "raja2026" in r["src"] and "patra2024" in r["src"]
    assert "40-50" in r["why"] and "%" in r["why"]
    assert "10.7759/cureus.111450" in syn["sources"]["raja2026"]
    assert "10.5603/fm.99128" in syn["sources"]["patra2024"]
    # and it offers the muscles that DO ship instead of returning nothing
    for o in ("psoas major", "iliacus", "iliopsoas"):
        assert o in r["offer"], o
    assert any("פסואס" in h for h in r["he"]), "the owner works in Hebrew"


def test_pelvic_tilt_is_answered_as_a_concept_with_cited_biomechanics(concepts):
    by = {c["id"]: c for c in concepts["concepts"]}
    for cid in ("pelvic_tilt", "anterior_pelvic_tilt", "posterior_pelvic_tilt", "lateral_pelvic_tilt"):
        assert cid in by, cid
        c = by[cid]
        assert c["he_label"], cid
        assert c["offer_structures"] or c["offer_groups"], cid
    # anterior tilt: the hip flexors and the lumbar extensors, each cited
    a = by["anterior_pelvic_tilt"]
    assert "act_hip_flex_p" in a["offer_groups"]
    assert "erector_spinae" in a["offer_groups"]
    assert any("preece2021" == cl["src"] for cl in a["claims"])
    # posterior tilt: gluteus maximus, hamstrings, abdominals, each cited
    p = by["posterior_pelvic_tilt"]
    for g in ("gluteal", "hamstrings", "anterolateral_abdominal_wall"):
        assert g in p["offer_groups"], g
    assert {cl["src"] for cl in p["claims"]} >= {"jang2024", "haddas2016"}
    # lateral tilt: the hip abductors and quadratus lumborum, each cited
    l = by["lateral_pelvic_tilt"]
    assert "act_hip_abd_p" in l["offer_groups"] and "act_lumbar_lat_p" in l["offer_groups"]
    assert {cl["src"] for cl in l["claims"]} >= {"becker2018", "willy2013"}
    # every claim on every concept names a source that the file defines
    for c in concepts["concepts"]:
        for cl in c["claims"]:
            assert cl["src"] in concepts["sources"], (c["id"], cl["src"])
    # the five PubMed sources carry their DOIs
    for s, doi in (("preece2021", "10.1016/j.jmpt.2020.09.006"),
                   ("jang2024", "10.1080/09593985.2023.2297001"),
                   ("haddas2016", "10.1007/s00586-016-4586-1"),
                   ("becker2018", "10.1249/MSS.0000000000001674"),
                   ("willy2013", "10.2519/jospt.2013.4516")):
        assert doi in concepts["sources"][s], s
    # and each links the Q283 simulation where the rig has a matching degree of freedom
    assert ["hip", "flex"] in a["sim"] and ["hip", "abd"] in l["sim"]


def test_every_functional_group_has_a_name_a_user_could_type(gnames, compiled):
    """The defect: Q298 shipped 108-110 groups per page but only the 17 named textbook ones had
    searchable names, so "hip flexors" returned nothing on every page."""
    rows = gnames["action_groups"] + gnames["extra_groups"]
    assert len(gnames["action_groups"]) == 87, len(gnames["action_groups"])
    assert len(gnames["extra_groups"]) == 6, len(gnames["extra_groups"])
    for r in rows:
        assert r["syn"], r["id"]
        assert r["he"], r["id"]
        assert r["name_rule"], r["id"]
    # the clinical names a clinician actually types
    want = {"hip flexors": "act_hip_flex_p", "hip extensors": "act_hip_flex_n",
            "knee extensors": "act_knee_flex_n", "knee flexors": "act_knee_flex_p",
            "hip abductors": "act_hip_abd_p", "hip adductors": "act_hip_abd_n",
            "ankle dorsiflexors": "act_ankle_dp_p", "ankle plantarflexors": "act_ankle_dp_n",
            "shoulder abductors": "act_shoulder_abd_p", "elbow flexors": "act_elbow_flex_p",
            "wrist extensors": "act_wrist_flex_n", "wrist flexors": "act_wrist_flex_p",
            "trunk flexors": "act_lumbar_flex_p", "neck flexors": "act_cervical_flex_p",
            "hip external rotators": "act_hip_rot_n", "pes anserinus": "pes_anserinus",
            "carpal tunnel contents": "carpal_tunnel_contents"}
    by = {r["id"]: r for r in rows}
    for term, gid in want.items():
        assert gid in by, gid
        assert term in by[gid]["syn"], (term, gid, by[gid]["syn"])
    # every group the page carries is in the search table, not only in the relations block
    for k in KEYS:
        ids = {g["id"] for g in compiled[k]["groups"]}
        assert len(ids) >= 100, (k, len(ids))
        assert "act_hip_flex_p" in ids, k


def test_the_broken_group_labels_were_corrected(gnames):
    """The generated labels used the pose rig's own words: nobody searches "The opposite of rotation at
    the hip joint", "Radial at the radiocarpal (wrist) joint" or "Flexion at the f2 dip"."""
    by = {r["id"]: r for r in gnames["action_groups"]}
    assert by["act_hip_rot_n"]["label"] == "External (lateral) rotation at the hip joint"
    assert by["act_wrist_dev_p"]["label"].startswith("Radial deviation at the")
    assert "index finger distal interphalangeal (DIP) joint" in by["act_f2_dip_flex_p"]["label"]
    # no corrected label may still carry a rig word
    for r in gnames["action_groups"]:
        assert "The opposite of" not in r["label"], r["id"]
        assert not re.search(r"\b(f[2-5]|t[1-5])\s+(mcp|pip|dip|mtp|ip)\b", r["label"]), r["id"]
    # label_was keeps the old text so the change is auditable
    changed = [r for r in gnames["action_groups"] if r["label"] != r["label_was"]]
    assert len(changed) == 62, len(changed)


def test_the_spine_rotation_direction_comes_from_the_cited_quotes(gnames):
    """Not guessed: the quoted actions themselves say which way the rig's sign goes."""
    acts = json.loads((DATA / "muscle_actions_q283.json").read_text(encoding="utf-8"))
    pos, neg = [], []
    for r in acts["rows"]:
        for mv in r["mv"]:
            if mv[0] in ("cervical", "thoracic", "lumbar") and mv[1] == "rot":
                (pos if mv[2] > 0 else neg).append(r["q"].lower())
    assert pos and neg
    assert any("ipsilateral" in q or "same side" in q for q in pos), pos
    assert any("contralateral" in q or "opposite side" in q for q in neg), neg
    by = {r["id"]: r for r in gnames["action_groups"]}
    assert "Ipsilateral" in by["act_cervical_rot_p"]["label"]
    assert "Contralateral" in by["act_cervical_rot_n"]["label"]
    assert by["act_cervical_rot_p"]["note"], "the convention must be stated on the row"


# ---------------------------------------------------------------- item 12: the new cited groups
def test_the_new_groups_have_cited_membership_and_nothing_inferred(newgroups, index):
    gs = newgroups["groups"]
    assert len(gs) == 18, len(gs)
    for g in gs:
        assert g["members"], g["id"]
        assert g["src"], g["id"]
        for part in g["src"].split(","):
            assert part in newgroups["sources"], (g["id"], part)
        assert g["syn"] and g["he"], g["id"]
        for m in g["members"]:
            assert _resolves(index, m), (g["id"], m)
        # a member the source names but no page ships is RECORDED, never silently dropped
        for m in g["not_on_any_page"]:
            assert not _resolves(index, m), (g["id"], m)
    # the groups the owner's report and the audit named
    ids = {g["id"] for g in gs}
    for gid in ("pelvic_floor", "scapular_stabilisers", "mastication", "intrinsic_foot",
                "intrinsic_hand", "forearm_anterior", "forearm_posterior", "thigh_anterior",
                "thigh_posterior", "thigh_medial", "leg_posterior_deep",
                "leg_posterior_superficial", "transversospinalis"):
        assert gid in ids, gid


def test_a_contested_group_says_what_is_contested(newgroups):
    con = [g for g in newgroups["groups"] if g["contested"]]
    assert len(con) == 7, [g["id"] for g in con]
    for g in con:
        assert len(g["contested_why"]) > 60, g["id"]
    # the compartments and every "stabiliser" group are where the literature disagrees
    ids = {g["id"] for g in con}
    assert "scapular_stabilisers" in ids
    assert {"forearm_anterior", "forearm_posterior", "thigh_anterior", "thigh_posterior",
            "leg_posterior_deep"} <= ids
    # the scapular-stabiliser row cites a real paper for the narrow clinical reading
    sc = [g for g in newgroups["groups"] if g["id"] == "scapular_stabilisers"][0]
    assert "karagiannakis2017" in sc["src"]
    assert "10.1016/j.jbmt.2017.09.018" in newgroups["sources"]["karagiannakis2017"]


# ---------------------------------------------------------------- the two wrong answers
def test_the_matcher_says_when_a_match_is_only_approximate(pages, compiled):
    """The defect class Q306 found: "psoas minor" returned Psoas major at rank 1 and "long head of biceps
    brachii" returned the long head of TRICEPS brachii, both with no sign that nothing had matched. The
    page stated something false with confidence, which is what Q297 refused to allow for geometry."""
    node = subprocess.run(["node", "--version"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    if node.returncode != 0:
        pytest.skip("node not available")
    k = "base_f"
    items = [{"id": s["id"], "name": s["name"], "latin": s["latin"], "cat": s["cat"],
              "part": s["part_of"], "group": s["cat"], "note": ""} for s in pages[k]]
    c = compiled[k]
    payload = {"items": items,
               "data": {"ids": c["ids"], "sub": c["sub"], "alias": c["alias"],
                        "groups": c["groups"], "ns": c["not_shipped"]},
               "queries": ["psoas minor", "long head of biceps brachii", "hamstrings", "semitendinosus",
                           "gastrocnemus", "iliotibal band", "hip flexors", "zzzzqqqq"]}
    tmp = DERIVED / ".q306_js_probe.json"
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    prog = ("const fs=require('fs');eval(fs.readFileSync(process.argv[1],'utf8'));"
            "const p=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));"
            "const ix=NMSKSearchCore.build({items:p.items,data:p.data});const o={};"
            "for(const q of p.queries){const r=ix.run(q);"
            "o[q]={n:r.ids.length,top:r.ids.slice(0,2),approx:r.approx,note_first:r.note_first,"
            "notes:r.notes.map(x=>x.name),groups:r.groups.map(g=>g.id)};}"
            "console.log(JSON.stringify(o));")
    try:
        r = subprocess.run(["node", "-e", prog, "--", str(REPO / "viewer/q298/search.js"), str(tmp)],
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=REPO)
        assert r.returncode == 0, r.stdout
        o = json.loads(r.stdout)
    finally:
        tmp.unlink(missing_ok=True)
    # Q311: psoas minor ships on Z pages (Q308 built it) — alias match, not an explanation
    assert o["psoas minor"]["n"] >= 1
    assert o["psoas minor"]["approx"] == 0
    assert o["psoas minor"]["note_first"] == 0
    # the biceps query now reaches the BICEPS
    assert all("biceps_brachii" in t for t in o["long head of biceps brachii"]["top"]), \
        o["long head of biceps brachii"]
    assert o["long head of biceps brachii"]["approx"] == 0
    # a real match is never labelled approximate
    for q in ("hamstrings", "semitendinosus", "hip flexors"):
        assert o[q]["approx"] == 0, (q, o[q])
    # a typo still finds the structure, and says it is approximate
    for q in ("gastrocnemus", "iliotibal band"):
        assert o[q]["n"] >= 1 and o[q]["approx"] == 1, (q, o[q])
    # nothing at all stays nothing, and is not called approximate
    assert o["zzzzqqqq"]["n"] == 0 and o["zzzzqqqq"]["approx"] == 0
    # the group query reaches the group
    assert "act_hip_flex_p" in o["hip flexors"]["groups"]


# ---------------------------------------------------------------- the reference list
def test_the_reference_list_is_fully_reachable(reference, compiled, pages, index):
    """The audit's own measurement, pinned: every term in data/anatomy/search_reference_q306.json reaches
    a structure, a group, a concept or an explanation on at least one page."""
    node = subprocess.run(["node", "--version"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    if node.returncode != 0:
        pytest.skip("node not available")
    import pagedata as P
    terms = [t["term"] for t in reference["terms"]]
    assert len(terms) == len(set(terms)), "one row per term"
    assert len(terms) >= 340, len(terms)
    prog = ("const fs=require('fs');eval(fs.readFileSync(process.argv[1],'utf8'));"
            "const p=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));"
            "const ix=NMSKSearchCore.build({items:p.items,data:p.data});const o={};"
            "for(const q of p.queries){const r=ix.run(q);"
            "o[q]={ids:r.ids.slice(0,3),groups:r.groups.map(g=>g.id),notes:r.notes.length};}"
            "console.log(JSON.stringify(o));")
    reached = {t: False for t in terms}
    for k in KEYS:
        c = compiled[k]
        items = [{"id": s["id"], "name": s["name"], "latin": s["latin"], "cat": s["cat"],
                  "part": s["part_of"], "group": s["cat"], "note": ""} for s in pages[k]]
        cmap = {}
        for row in c.get("concepts", []):
            for a in row.get("al", []):
                cmap.setdefault(P.fold(a), []).append(row["id"])
        tmp = DERIVED / f".q306_ref_{k}.json"
        tmp.write_text(json.dumps({"items": items,
                                   "data": {"ids": c["ids"], "sub": c["sub"], "alias": c["alias"],
                                            "groups": c["groups"], "ns": c["not_shipped"]},
                                   "queries": terms}, ensure_ascii=False), encoding="utf-8")
        try:
            r = subprocess.run(["node", "-e", prog, "--", str(REPO / "viewer/q298/search.js"), str(tmp)],
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=REPO)
            assert r.returncode == 0, r.stdout[:3000]
            o = json.loads(r.stdout)
        finally:
            tmp.unlink(missing_ok=True)
        names = {s["id"]: s["name"] + " " + (s["latin"] or "") for s in pages[k]}
        for row in reference["terms"]:
            t, exp = row["term"], row["expect"]
            d = o[t]
            ok = False
            if exp.startswith("G:"):
                ok = exp[2:] in d["groups"]
            elif exp in ("", "?"):
                ok = bool(d["notes"] or cmap.get(P.fold(t)) or d["groups"])
            else:
                rx = re.compile(exp, re.I)
                ok = any(rx.search(names.get(i, "")) for i in d["ids"])
                if not ok:
                    ok = bool(cmap.get(P.fold(t)) or d["notes"])
            if ok:
                reached[t] = True
    dead = sorted(t for t, v in reached.items() if not v)
    assert not dead, f"{len(dead)} reference terms reach nothing on any page: {dead}"


# ---------------------------------------------------------------- housekeeping
def test_hebrew_is_declared_a_project_translation_everywhere(syn, gnames, concepts, newgroups):
    """Terminologia Anatomica has no Hebrew edition; Q298 declared this and Q306 must not quietly drop it."""
    for f, key in ((syn, "sources"), (gnames, "he_note"), (concepts, "he_note"), (newgroups, "he_note")):
        blob = json.dumps(f.get(key), ensure_ascii=False)
        assert "PROJECT-SUPPLIED TRANSLATION" in blob.upper() or "project-supplied" in blob.lower(), key


def test_every_new_concept_declares_what_kind_of_thing_it_is(concepts):
    for c in concepts["concepts"]:
        assert c["kind"] in concepts["kinds"], (c["id"], c["kind"])
        assert c["body"], c["id"]
        # a diagnosis must say it is one and must not assert a mechanism
        if c["kind"] == "diagnosis":
            assert "DIAGNOSIS" in c["note"], c["id"]
        # a measure must say whether this project computes it
        if c["kind"] == "measure":
            assert c["claims"], c["id"]


def test_no_model_identifier_leaks_into_the_new_data(syn, gnames, concepts, newgroups, reference):
    blob = json.dumps([syn, gnames, concepts, newgroups, reference], ensure_ascii=False).lower()
    for bad in ("claude", "anthropic", "opus", "sonnet", "haiku", "gpt-", "llm"):
        assert bad not in blob, bad

# ---------------------------------------------------------------- Q304's nerves: the owner's own case
def test_every_q304_nerve_is_reachable_by_every_name_a_clinician_uses(syn, index):
    """The owner's ORIGINAL complaint was that he could not find the peroneal nerve, so this is the one
    case that must be flawless: all 39 nerves Q304 carries onto the Imaging pages, trunks AND the 27
    named branches, by TA name, clinical name, abbreviation and Hebrew."""
    xfer = json.loads((DERIVED / "Q304_nerve_transfer.json").read_text(encoding="utf-8"))
    ids = set()
    for k in ("own_m", "own_f"):
        ids |= set(xfer[k]["ids"])
    distinct = {re.sub(r"_(l|r)$", "", i) for i in ids}
    assert len(distinct) == 39, len(distinct)
    # every nerve the transfer names has an entry, and every entry resolves
    nerves = [e for e in syn["entries"] if "nerve" in e["canon"].lower() or "branch" in e["canon"].lower()]
    assert len(nerves) >= 39, len(nerves)
    for e in nerves:
        assert any(_resolves(index, t) for t in e["targets"]), e["canon"]
        assert e["he"], f"{e['canon']} has no Hebrew name"
    # peroneal must reach fibular, for all three, and in Hebrew
    forms = {}
    for e in syn["entries"]:
        for f in e["abbr"] + e["syn"] + e["he"]:
            forms.setdefault(f.lower(), set()).add(e["canon"])
    for term, canon in (("peroneal nerve", "Common fibular nerve"),
                        ("common peroneal nerve", "Common fibular nerve"),
                        ("deep peroneal nerve", "Deep fibular nerve"),
                        ("superficial peroneal nerve", "Superficial fibular nerve"),
                        ("cpn", "Common fibular nerve"),
                        ("dpn", "Deep fibular nerve"),
                        ("spn", "Superficial fibular nerve"),
                        ("העצב הפרונאלי", "Common fibular nerve"),
                        ("העצב הפיבולרי העמוק", "Deep fibular nerve")):
        assert canon in forms.get(term, set()), (term, canon, forms.get(term))
    # the named branches, by the name a clinician says rather than the page's wording
    for term in ("nerve to iliacus", "nerve to sartorius", "nerve to rectus femoris",
                 "nerve to pectineus", "nerve to vastus lateralis", "nerve to semitendinosus",
                 "nerve to semimembranosus", "nerve to adductor magnus", "nerve to gastrocnemius",
                 "nerve to soleus", "nerve to popliteus", "infrapatellar branch",
                 "medial sural cutaneous nerve", "sural communicating branch",
                 "lateral sural cutaneous nerve", "lumboinguinal nerve"):
        assert forms.get(term), term


def test_the_four_overturned_gaps_stay_overturned(index, pages):
    """Q302's gap list said the nipple, the areola, Cooper's ligaments and the nails were not shipped.
    They are. This test exists so a later round cannot "close" a gap that does not exist -- and so the
    day one of them really is removed, this fails loudly instead of the claim quietly becoming true."""
    for t, where in (("nipple", {"own_f", "base_f", "comb_f"}),
                     ("areola", {"own_f", "base_f", "comb_f"}),
                     ("suspensory ligaments of the breast", {"own_f", "base_f", "comb_f"}),
                     ("nail plate", {"base_m", "base_f", "comb_m", "comb_f"}),
                     ("ligamenta flava", {"base_m", "base_f", "comb_m", "comb_f"})):
        got = set(_resolves(index, t))
        assert got >= where, (t, "expected at least", where, "got", got)
    # and the male pages really do carry no nipple, which is why the search must say so there
    for k in ("own_m", "base_m", "comb_m"):
        hits = [s["name"] for s in pages[k]
                if re.search(r"nipple|areola", s["name"], re.I)]
        assert not hits, (k, hits)


def test_the_seven_new_absences_are_recorded_not_silent(syn):
    names = {n["name"].lower() for n in syn["cited_but_not_shipped"]}
    for want in ("pubic symphysis", "coracoacromial ligament", "retrocalcaneal bursa",
                 "anterolateral ligament of the knee", "triangular fibrocartilage complex",
                 "zygapophysial (facet) joint", "anterior superior iliac spine",
                 "posterior superior iliac spine"):
        assert want in names, (want, sorted(names))

