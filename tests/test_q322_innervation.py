"""Q322: data/anatomy/innervation_q322.json (MUSCLE INNERVATION mode data) stays well-formed and honest.

Schema, every muscle sourced, percentages in 0-100, landmarks/lines declared, sources resolvable, no
term the public pages must not carry, and every structure id present on the Base pages (when built)."""
from __future__ import annotations
import json
import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
PUB = REPO / "data/anatomy/innervation_q322.json"
PRIV = REPO / "clinical/data/innervation_injection_q322.json"
PAGES = {"base_m": REPO / "build/q309/viewer_zan_atlas/atlas_viewer_zan_atlas.html",
         "base_f": REPO / "build/q309/viewer_base_female/atlas_viewer_base_female.html"}
FORBIDDEN = ("ultrasound", "hounsfield", "t1_se", "imaging_tissues", "tissue table", "nmskultrasound", "acoustic", "mrayl", "b-mode")
LM_KINDS = {"bony_point", "derived", "soft_tissue", "muscle_derived"}
VERDICTS = {"relevant", "partly", "not relevant", "not used"}
ROOT = re.compile(r"^(C[1-8]|T(1[0-2]|[1-9])|L[1-5]|S[1-5])$")
REC = re.compile(r'\{"name":"[^"]*","id":"([^"]+)","side":"\w*","sys":"[a-z_]+"')


@pytest.fixture(scope="module")
def d():
    return json.loads(PUB.read_text(encoding="utf-8"))


def _pcts(p):
    return [] if p is None else (p if isinstance(p, list) else [p])


def test_schema(d):
    assert d["schema"] == "nmsk.innervation.v1"
    for k in ("doc", "landmarks", "lines", "muscles", "sources", "coverage"):
        assert k in d
    assert set(d["scope"]) == {"base_m", "base_f"}
    for k, m in d["muscles"].items():
        for f in ("name", "region", "structures", "nerve", "roots", "iz", "iz_other_sources", "sources", "conflicts"):
            assert f in m, (k, f)
        assert m["region"] in ("upper_limb", "lower_limb")
        assert m["nerve"], k


def test_no_public_page_forbidden_terms():
    txt = PUB.read_text(encoding="utf-8").lower()
    assert not [w for w in FORBIDDEN if w in txt]


def test_landmarks_and_lines_declared(d):
    L, LN = d["landmarks"], d["lines"]
    for n, lm in L.items():
        assert lm["kind"] in LM_KINDS, n
        for o in lm.get("of", []):
            assert o in L, (n, o)
        if lm["kind"] == "derived":
            assert len(lm["of"]) == 2, n
    for i, ln in LN.items():
        assert ln["from"] in L and ln["to"] in L and ln["from"] != ln["to"], i
        assert ln["mode"] in ("level", "point"), i
    for n in d["landmarks_needed_for_guide_iz"]:
        assert n in L, n


def test_every_muscle_sourced_and_sources_resolve(d):
    S = d["sources"]
    for sid, s in S.items():
        assert s["citation"] and s["verdict"] in VERDICTS, sid
    for k, m in d["muscles"].items():
        allsrc = [s for v in m["sources"].values() for s in v]
        assert allsrc, k
        assert m["sources"]["nerve"] and m["sources"]["roots"], k
        for s in allsrc:
            assert s in S, (k, s)
        for z in m["iz"]:
            assert z["src"] and all(s in S for s in z["src"]) and z["cite"], (k, z)
        for o in m["iz_other_sources"]:
            assert o["src"] in S, (k, o)


def test_percentages_and_lines(d):
    for k, m in d["muscles"].items():
        for z in m["iz"]:
            assert z["line"] in d["lines"], (k, z)
            ps = _pcts(z["pct"])
            if not ps:
                assert z.get("note"), (k, z)        # a qualitative site must say so
            for p in ps:
                assert isinstance(p, (int, float)) and 0 <= p <= 100, (k, z)
            if isinstance(z["pct"], list):
                assert len(z["pct"]) == 2 and z["pct"][0] <= z["pct"][1], (k, z)
        for o in m["iz_other_sources"]:
            if o.get("line"):
                assert o["line"] in d["lines"], (k, o)
            for p in _pcts(o.get("pct")):
                assert 0 <= p <= 100, (k, o)


def test_roots(d):
    for k, m in d["muscles"].items():
        r = m["roots"]
        assert r["adopted"] and all(ROOT.match(x) for x in r["adopted"]), k
        for p in r["per_source"]:
            assert all(ROOT.match(x) for x in p["levels"]), (k, p)


def test_no_injection_technique_in_public(d):
    txt = json.dumps(d["muscles"]).lower()
    for w in ("injection_points", "needle", "probe", "transducer", "dose"):
        assert w not in txt, w


def test_private_layer_matches():
    if not PRIV.exists():
        pytest.skip("private clinical layer not present")
    p = json.loads(PRIV.read_text(encoding="utf-8"))
    assert p["schema"] == "nmsk.innervation_injection.v1" and "Private" in p["licence"]
    d = json.loads(PUB.read_text(encoding="utf-8"))
    assert set(p["muscles"]) == set(d["muscles"])


@pytest.mark.parametrize("page", sorted(PAGES))
def test_ids_exist_on_base_pages(d, page):
    if not PAGES[page].exists():
        pytest.skip("build/ not restored")
    ids = set(REC.findall(PAGES[page].read_text(encoding="utf-8")))
    for k, m in d["muscles"].items():
        assert m["structures"][page], (k, page)
        for s in m["structures"][page]:
            assert s in ids, (k, s)
        for p in m["parts"]:
            for s in p.get("structures", []):
                assert s + "_l" in ids and s + "_r" in ids, (k, s)
        for s in m["nerve_structures_on_page"][page]:
            assert s in ids, (k, s)
