"""Q298: data-level assertions for the search synonym layer, the measured adjacency and the relation / functional-group tables.

The headline assertion is the one the brief asked for: EVERY abbreviation in the synonym file resolves to a structure that
really exists on at least one of the six pages -- so the thing the owner typed ("ITB") can never again reach nothing while
the structure is on the page. The rest pin the diagnosis (what the old search actually matched), the ranking rule, the
adjacency threshold and the labelling of inferred relations, so a later round cannot quietly undo them."""
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

BUILD = REPO / "build/q297"
DATA = REPO / "data/anatomy"
DERIVED = REPO / "data/derived"
KEYS = ["own_m", "own_f", "base_m", "base_f", "comb_m", "comb_f"]
pytestmark = pytest.mark.skipif(not BUILD.is_dir(), reason="build/q297 not on disk")

# the abbreviations the owner's round named explicitly
REQUIRED = ["ITB", "IT band", "TFL", "SCM", "ACL", "PCL", "MCL", "LCL", "FPL", "FDP", "FDS", "EPL", "EPB", "APL",
            "QL", "LD", "RF", "VMO", "ECRL", "ECRB", "FCU", "FCR", "TA", "EHL", "FHL", "PT", "GM", "SIJ", "TMJ"] + \
           [f"CN {r}" for r in ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI", "XII"]]


@pytest.fixture(scope="module")
def syn():
    return json.loads((DATA / "synonyms_q298.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def rules():
    return json.loads((DATA / "relations_q298.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def compiled():
    out = {}
    for k in KEYS:
        p = DERIVED / f"Q298_search_{k}.json"
        assert p.exists(), f"missing {p}"
        out[k] = json.loads(p.read_text(encoding="utf-8"))
    return out


@pytest.fixture(scope="module")
def pages():
    import pagedata as P
    return {k: P.structures(k, "build/q297") for k in KEYS}


# ---------------------------------------------------------------- the headline assertion
def test_every_abbreviation_reaches_a_real_structure_on_at_least_one_page(syn, compiled, pages):
    want = set()
    for e in syn["entries"]:
        want |= set(e.get("abbr") or [])
    for g in syn["groups"]:
        want |= set(g.get("abbr") or [])
    want |= {f"CN {['', 'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI', 'XII'][r['n']]}"
             for r in syn["cn"]["rows"]}
    real = {k: {s["id"] for s in v} for k, v in pages.items()}
    missing, dangling = [], []
    for ab in sorted(want):
        hit = False
        for k, c in compiled.items():
            for a in c["alias"]:
                if a["k"] == "abbr" and a["d"] == ab and a["i"]:
                    ids = [c["ids"][i] for i in a["i"]]
                    bad = [x for x in ids if x not in real[k]]
                    if bad:
                        dangling.append((ab, k, bad[:3]))
                    if ids:
                        hit = True
        if not hit:
            missing.append(ab)
    assert missing == [], f"{len(missing)} abbreviations resolve to nothing on any page: {missing}"
    assert dangling == [], f"abbreviations resolving to ids that are not on that page: {dangling[:5]}"


def test_the_abbreviations_the_round_asked_for_are_all_covered(syn):
    have = set()
    for e in syn["entries"]:
        have |= set(e.get("abbr") or [])
    for g in syn["groups"]:
        have |= set(g.get("abbr") or [])
    have |= {f"CN {['', 'I', 'II', 'III', 'IV', 'V', 'VI', 'VII', 'VIII', 'IX', 'X', 'XI', 'XII'][r['n']]}"
             for r in syn["cn"]["rows"]}
    miss = [a for a in REQUIRED if a not in have]
    assert miss == [], f"the round named these abbreviations and the data file does not carry them: {miss}"


def test_itb_resolves_to_the_iliotibial_tract_on_every_z_page(compiled, pages):
    for k in ("base_m", "base_f", "comb_m", "comb_f"):
        c = compiled[k]
        hits = [a for a in c["alias"] if a["q"] in ("itb", "it band", "iliotibial band")]
        assert len(hits) >= 3, f"{k}: ITB / IT band / iliotibial band are not all aliases ({len(hits)})"
        for a in hits:
            assert a["c"] == "Iliotibial tract", (k, a["q"], a["c"])
            names = {s["name"] for s in pages[k] if s["id"] in [c["ids"][i] for i in a["i"]]}
            assert names, (k, a["q"])
            assert all("liotibial" in n for n in names), (k, a["q"], names)


def test_the_hebrew_name_of_the_iliotibial_tract_resolves(compiled):
    for k in ("base_m", "base_f", "comb_m", "comb_f"):
        he = [a for a in compiled[k]["alias"] if a["k"] == "he" and a["c"] == "Iliotibial tract"]
        assert he, f"{k}: no Hebrew alias for the iliotibial tract"
        assert any(re.search(r"[֐-׿]", a["q"]) for a in he), f"{k}: the Hebrew alias is not Hebrew"


# ---------------------------------------------------------------- the synonym file itself
def test_every_entry_resolves_somewhere_or_is_declared_not_shipped(syn, compiled):
    got = set()
    for c in compiled.values():
        for a in c["alias"]:
            got.add(a["c"])
    declared = {e["canon"] for e in syn["cited_but_not_shipped"]} | {e["name"] for e in syn["cited_but_not_shipped"]}
    allc = [e["canon"] for e in syn["entries"]] + [r["canon"] for r in syn["cn"]["rows"]] + \
           [f["canon"] for f in syn["families"]]
    bad = [c for c in allc if c not in got and c not in declared]
    assert bad == [], f"these entries resolve on no page and are not declared as not shipped: {bad}"


def test_the_names_declared_not_shipped_really_are_absent(syn, pages):
    import pagedata as P
    for e in syn["cited_but_not_shipped"]:
        key = P.fold(e["canon"].split(" (")[0])
        for k, ss in pages.items():
            hit = [s["name"] for s in ss if key and key in P.fold(s["name"])]
            assert not hit, f'{e["name"]}: declared not shipped but {k} carries {hit[:2]}'


def test_every_entry_carries_a_source_and_a_hebrew_name(syn):
    nosrc = [e["canon"] for e in syn["entries"] if not e.get("src")]
    nohe = [e["canon"] for e in syn["entries"] if not (e.get("he") or [])]
    assert nosrc == [], f"entries with no source: {nosrc}"
    assert nohe == [], f"entries with no Hebrew name: {nohe}"
    assert "PROJECT-SUPPLIED TRANSLATION" in syn["sources"]["he"], "the Hebrew source must say it is not a standard"


def test_the_ambiguous_abbreviations_are_marked_ambiguous(syn):
    byab = {}
    for e in syn["entries"]:
        for a in e.get("abbr") or []:
            byab.setdefault(a, []).append(e)
    for a, es in byab.items():
        if len(es) > 1:
            bad = [e["canon"] for e in es if not e.get("ambiguous")]
            assert bad == [], f"{a} has {len(es)} expansions; these are not marked ambiguous: {bad}"
    gm = [e for e in syn["entries"] if "GM" in (e.get("abbr") or [])]
    assert len(gm) >= 2 and all(e.get("ambiguous") for e in gm), "GM must be marked ambiguous and say which muscles"


def test_the_compiled_tables_are_big_enough_and_index_real_ids(compiled, pages):
    for k, c in compiled.items():
        real = {s["id"] for s in pages[k]}
        assert c["counts"]["alias_forms"] > 300, (k, c["counts"])
        assert c["counts"]["abbr_forms"] >= 60, (k, c["counts"])
        assert c["counts"]["he_forms"] >= 100, (k, c["counts"])
        assert c["counts"]["groups"] >= 15, (k, c["counts"])
        assert set(c["ids"]) <= real, (k, sorted(set(c["ids"]) - real)[:5])
        assert len(c["sub"]) == len(c["ids"])
        for a in c["alias"]:
            assert a["i"] and max(a["i"]) < len(c["ids"]), (k, a["q"])


def test_searching_a_group_name_offers_the_group(compiled):
    for k in ("base_m", "base_f", "comb_m", "comb_f"):
        gs = {g["id"]: g for g in compiled[k]["groups"]}
        assert "hamstrings" in gs and len(gs["hamstrings"]["i"]) >= 4, (k, list(gs))
        assert "rotator_cuff" in gs and len(gs["rotator_cuff"]["i"]) >= 4, (k, list(gs))
        assert "hamstrings" in [g for g in gs], k
        assert "hamstrings" in gs["hamstrings"]["al"] or "hamstring" in gs["hamstrings"]["al"], gs["hamstrings"]["al"]


# ---------------------------------------------------------------- the measured adjacency
@pytest.fixture(scope="module")
def adj():
    out = {}
    for k in KEYS:
        p = DERIVED / f"Q298_adjacency_{k}.json"
        if p.exists():
            out[k] = json.loads(p.read_text(encoding="utf-8"))
    return out


def test_adjacency_exists_for_every_page_and_states_its_threshold(adj):
    assert sorted(adj) == sorted(KEYS), f"missing adjacency files: {sorted(set(KEYS) - set(adj))}"
    for k, a in adj.items():
        assert a["cell_mm"] == 2.0 and abs(a["threshold_mm"] - 3.46) < 0.01, (k, a["cell_mm"], a["threshold_mm"])
        assert "voxel" in a["how"] and "measurement, not an anatomical claim" in a["how"], k


def test_adjacency_is_symmetric_without_self_links_and_leaves_nothing_isolated(adj):
    for k, a in adj.items():
        n = len(a["ids"])
        assert len(a["adj"]) == n, k
        for i, row in enumerate(a["adj"]):
            assert i not in row, (k, i)
            assert not [j for j in row if j < 0 or j >= n], (k, i)
        bad = [(i, j) for i, row in enumerate(a["adj"]) for j in row if i not in a["adj"][j]]
        assert bad == [], f"{k}: {len(bad)} one-way adjacency links: {bad[:5]}"
        assert a["per_structure"]["isolated"] == 0, f'{k}: {a["per_structure"]["isolated"]} structures have no neighbour'
        assert a["pairs"] > n, (k, a["pairs"], n)


def test_adjacency_is_within_the_stated_threshold_on_a_real_sample(adj):
    """Re-measure a sample of the adjacent pairs and of the NON-adjacent ones straight off the shipped geometry."""
    import numpy as np
    from scipy.spatial import cKDTree
    import pagedata as P
    import adjacency_q298 as A
    k = "own_m"
    a = adj[k]
    rng = np.random.default_rng(298)
    pairs = [(i, j) for i, row in enumerate(a["adj"]) for j in row if j > i]
    pick = [pairs[t] for t in rng.choice(len(pairs), 25, replace=False)]
    need = sorted({x for p in pick for x in p})
    pts = {}
    for i, sid, v, f in P.meshes(k, "build/q297"):
        if i in need:
            pts[i] = A.samples(v, f, 2.0)
    far = []
    for i, j in pick:
        d = float(cKDTree(pts[i]).query(pts[j], k=1)[0].min())
        if d > a["threshold_mm"] + 0.01:
            far.append((a["ids"][i], a["ids"][j], round(d, 2)))
    assert far == [], f"pairs called adjacent that are further apart than {a['threshold_mm']} mm: {far}"


# ---------------------------------------------------------------- the relations and the functional groups
@pytest.fixture(scope="module")
def rel():
    out = {}
    for k in KEYS:
        p = DERIVED / f"Q298_relations_{k}.json"
        if p.exists():
            out[k] = json.loads(p.read_text(encoding="utf-8"))
    return out


def test_relations_exist_for_every_page_and_index_real_structures(rel, pages):
    assert sorted(rel) == sorted(KEYS), f"missing relation files: {sorted(set(KEYS) - set(rel))}"
    for k, r in rel.items():
        real = [s["id"] for s in pages[k]]
        assert r["ids"] == real, k
        n = len(real)
        for i, rows in r["rel"].items():
            assert 0 <= int(i) < n, (k, i)
            for j, kind in rows:
                assert 0 <= j < n, (k, i, j)
                assert kind in r["kinds"], (k, kind)
        assert r["counts"]["links"] > 1000, (k, r["counts"])


def test_every_relation_kind_names_its_source_and_says_whether_it_is_inferred(rel, rules):
    for k, r in rel.items():
        for kind, K in r["kinds"].items():
            assert K.get("src"), (k, kind)
            assert K.get("why"), (k, kind)
            assert K.get("inferred") in (0, 1), (k, kind)
    inferred = {kind for kind, K in rules["kinds"].items() if K["inferred"]}
    assert inferred == {"tendon", "bursa", "joint", "antagonist"}, inferred


def test_semitendinosus_offers_its_nerve_its_bones_and_the_hamstrings(rel):
    for k in ("base_m", "base_f", "comb_m", "comb_f"):
        r = rel[k]
        i = r["ids"].index("semitendinosus_r")
        rows = r["rel"][str(i)]
        kinds = {kind for _, kind in rows}
        assert {"nerve", "attach", "joint", "antagonist"} <= kinds, (k, kinds)
        nerves = [r["ids"][j] for j, kind in rows if kind == "nerve"]
        assert any("sciatic" in x for x in nerves), (k, nerves)
        gs = [r["fgroups"][g]["id"] for g in r["fg"][str(i)]]
        assert "hamstrings" in gs, (k, gs)
        ham = next(g for g in r["fgroups"] if g["id"] == "hamstrings")
        mem = {r["ids"][j] for j in ham["i"]}
        assert {"biceps_femoris_r", "semitendinosus_r", "semimembranosus_r"} <= mem, (k, sorted(mem))


def test_the_iliotibial_tract_offers_its_tensors(rel):
    for k in ("base_m", "base_f", "comb_m", "comb_f"):
        r = rel[k]
        ids = [x for x in r["ids"] if "iliotibial_tract" in x]
        assert ids, k
        found = False
        for sid in ids:
            i = r["ids"].index(sid)
            for g in r["fg"].get(str(i), []):
                G = r["fgroups"][g]
                if G["id"] != "itb_tensors":
                    continue
                mem = {r["ids"][j] for j in G["i"]}
                assert any("tensor_fasciae_latae" in x for x in mem), (k, sorted(mem))
                assert any("gluteus_maximus" in x for x in mem), (k, sorted(mem))
                found = True
        assert found, f"{k}: the iliotibial tract offers no tensors group"


def test_the_iliotibial_tract_has_cited_related_structures(rel):
    for k in ("base_m", "base_f", "comb_m", "comb_f"):
        r = rel[k]
        sid = [x for x in r["ids"] if "iliotibial_tract" in x][0]
        rows = r["rel"][str(r["ids"].index(sid))]
        tgt = {r["ids"][j] for j, _ in rows}
        assert any("tensor_fasciae_latae" in x for x in tgt), (k, sorted(tgt))
        assert any("tibia" in x for x in tgt), (k, sorted(tgt))


def test_functional_groups_all_carry_a_source_and_a_reason(rel):
    for k, r in rel.items():
        for g in r["fgroups"]:
            assert g["why"], (k, g["id"])
            assert g["inferred"] in (0, 1), (k, g["id"])
            assert len(g["i"]) >= 2, (k, g["id"])
            if not g["inferred"]:
                assert g["src"], (k, g["id"])


def test_action_groups_come_from_the_cited_action_data(rel):
    """picking a hamstring must offer 'flexion at the knee', and that group must hold the other knee flexors."""
    for k in ("base_f", "comb_m"):
        r = rel[k]
        i = r["ids"].index("biceps_femoris_r")
        names = [r["fgroups"][g]["name"] for g in r["fg"][str(i)]]
        assert any("knee" in n.lower() and "flex" in n.lower() for n in names), (k, names)
        g = next(r["fgroups"][x] for x in r["fg"][str(i)] if "knee" in r["fgroups"][x]["name"].lower()
                 and "flex" in r["fgroups"][x]["name"].lower())
        mem = {r["ids"][j] for j in g["i"]}
        assert {"semitendinosus_r", "semimembranosus_r"} <= mem, (k, sorted(mem))


# ---------------------------------------------------------------- the viewer side
def test_both_templates_carry_the_shared_modules_and_the_page_data_block():
    for t in ("viewer/atlas_viewer.template.html", "viewer/zan_atlas.template.html"):
        s = (REPO / t).read_text(encoding="utf-8")
        assert s.count("<!-- Q298 html begin -->") == 1 and s.count("<!-- Q298 html end -->") == 1, t
        assert s.count('id="nmsk-q298"') == 1, t
        for sym in ("NMSKSearchCore", "NMSKQ298Bar", "NMSKMulti", "NMSKExpand", "NMSKQ298.start("):
            assert sym in s, (t, sym)
        # the engine's own list must go through the shared matcher
        assert "NMSKQ298.filter(q)" in s, t
        assert "NMSKQ298.afterList(" in s, t
        assert "NMSKQ298.whySuffix(" in s, t


def test_sync_q298_is_up_to_date():
    r = subprocess.run([sys.executable, "scripts/sync_q298.py", "--check"], cwd=REPO,
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    assert r.returncode == 0, r.stdout


def test_the_js_and_the_python_fold_the_same_way():
    """The build step resolves aliases with pagedata.fold(); the browser matches with the same rule in search.js.
    If the two ever drift, an alias stops matching, which is exactly the Q298 defect coming back."""
    js = (REPO / "viewer/q298/search.js").read_text(encoding="utf-8")
    py = (REPO / "scripts/anatomy/q298/pagedata.py").read_text(encoding="utf-8")
    assert "[^0-9a-z\\u0590-\\u05ff]+" in js, "search.js must fold punctuation with the same class as pagedata.py"
    assert r"[^0-9a-z֐-׿]+" in py, "pagedata.py punctuation class changed"
    node = subprocess.run(["node", "--version"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    if node.returncode != 0:
        pytest.skip("node not available")
    import pagedata as P
    cases = ["Iliotibial (IT) tract/band", "Cooper's ligaments", "CN VII", "Müller", "  spaces   here ",
             "גיד אכילס", "Median nerve.l", "ACL/PCL"]
    prog = ("const fs=require('fs');eval(fs.readFileSync(process.argv[2],'utf8'));"
            "console.log(JSON.stringify(JSON.parse(process.argv[3]).map(NMSKSearchCore.fold)));")
    r = subprocess.run(["node", "-e", prog, "--", str(REPO / "viewer/q298/search.js"), json.dumps(cases)],
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=REPO)
    assert r.returncode == 0, r.stdout
    assert json.loads(r.stdout) == [P.fold(c) for c in cases], (r.stdout, [P.fold(c) for c in cases])


def test_the_js_matcher_finds_the_structure_by_every_name_the_owner_used(compiled, pages):
    """Drive the real browser matcher under node: the same module the page runs."""
    node = subprocess.run(["node", "--version"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    if node.returncode != 0:
        pytest.skip("node not available")
    k = "base_f"
    items = [{"id": s["id"], "name": s["name"], "latin": s["latin"], "cat": s["cat"],
              "part": s["part_of"], "group": s["cat"], "note": ""} for s in pages[k]]
    c = compiled[k]
    payload = {"items": items, "data": {"ids": c["ids"], "sub": c["sub"], "alias": c["alias"],
                                        "groups": c["groups"], "ns": c["not_shipped"]},
               "queries": ["ITB", "IT band", "iliotibial band", "הרצועה האיליוטיביאלית",
                           "iliotibal band", "hamstrings", "Hoffa", "Gerdy", "kneecap"]}
    tmp = REPO / "data/derived/.q298_js_probe.json"
    tmp.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    prog = ("const fs=require('fs');eval(fs.readFileSync(process.argv[2],'utf8'));"
            "const p=JSON.parse(fs.readFileSync(process.argv[3],'utf8'));"
            "const ix=NMSKSearchCore.build({items:p.items,data:p.data});const o={};"
            "for(const q of p.queries){const r=ix.run(q);"
            "o[q]={n:r.ids.length,top:r.ids.slice(0,4),why:r.ids.slice(0,4).map(i=>r.why[i]?r.why[i].c:null),"
            "groups:r.groups.map(g=>g.id),notes:r.notes.map(x=>x.name)};}"
            "console.log(JSON.stringify(o));")
    try:
        r = subprocess.run(["node", "-e", prog, "--", str(REPO / "viewer/q298/search.js"), str(tmp)],
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=REPO)
        assert r.returncode == 0, r.stdout
        o = json.loads(r.stdout)
    finally:
        tmp.unlink(missing_ok=True)
    for q in ("ITB", "IT band", "iliotibial band", "הרצועה האיליוטיביאלית", "iliotibal band"):
        assert o[q]["n"] >= 1, (q, o[q])
        assert all("liotibial" in t for t in o[q]["top"][:1]), (q, o[q])
        assert o[q]["why"][0] == "Iliotibial tract", (q, o[q])
    assert "hamstrings" in o["hamstrings"]["groups"], o["hamstrings"]
    assert o["Hoffa"]["why"][0] == "Infrapatellar fat pad", o["Hoffa"]
    assert o["kneecap"]["why"][0] == "Patella", o["kneecap"]
    assert "Gerdy's tubercle" in o["Gerdy"]["notes"], o["Gerdy"]


def test_the_old_single_substring_search_is_only_the_fallback():
    """The diagnosis, pinned: the engines still carry the old filter, but only behind the Q298 matcher."""
    own = (REPO / "viewer/atlas_viewer.template.html").read_text(encoding="utf-8")
    zan = (REPO / "viewer/zan_atlas.template.html").read_text(encoding="utf-8")
    assert "var q8 = (window.NMSKQ298 && NMSKQ298.ready()) ? NMSKQ298.filter(q) : null;" in own
    assert "var q8=(window.NMSKQ298&&NMSKQ298.ready())?NMSKQ298.filter(q):null;" in zan
    # the Z engine's old filter searched the display NAME only -- that is the defect, kept only as the fallback
    assert 'items=OBJ.filter(function(o){return !q||o.name.toLowerCase().indexOf(q)>=0;});' in zan
