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

# ---------------------------------------------------------------------------------------------------------------------------
# Q322 step 3: the mode itself (viewer/innervation/) and the rule-based IZ band placement (scripts/anatomy/q322/place_iz_q322.py).
# The browser run is scripts/anatomy/q322/verify_innervation_q322.py.
import importlib.util  # noqa: E402
import subprocess  # noqa: E402
import sys  # noqa: E402

D = REPO / "viewer" / "innervation"
JS = (D / "innervation.js").read_text(encoding="utf-8")
CSS = (D / "innervation.css").read_text(encoding="utf-8")
ZAN = (REPO / "viewer" / "zan_atlas.template.html").read_text(encoding="utf-8")
OWN = (REPO / "viewer" / "atlas_viewer.template.html").read_text(encoding="utf-8")
MODES_JS = (REPO / "viewer" / "modes" / "modes.js").read_text(encoding="utf-8")
MODES_HTML = (REPO / "viewer" / "modes" / "modes.html").read_text(encoding="utf-8")
PLACE = REPO / "scripts" / "anatomy" / "q322" / "place_iz_q322.py"
SIDECAR = REPO / "scripts" / "anatomy" / "q322" / "build_sidecar_q322.py"
DATA_PUB = json.loads((REPO / "data" / "anatomy" / "innervation_q322.json").read_text(encoding="utf-8"))
INJ = re.compile(r"inject|needle|botul|toxin|\bdose|motor.point", re.I)
MODE_PAGES = ("base_m", "base_f")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def iz_bands(page):
    return json.loads((REPO / "data" / "derived" / f"Q322_iz_bands_{page}.json").read_text(encoding="utf-8"))


def test_mode_registered_through_the_shared_controller():
    assert 'NMSKModes.register("inn", provider)' in JS
    assert '"inj", "us", "cmp", "inn"' in MODES_JS and "inj|us|cmp|inn|anat" in MODES_JS
    assert 'data-mode="inn"' in MODES_HTML
    # marking and colour go through the selection controller's public API, never a parallel state
    for call in ("markIds(", 'setGroup("oth", "fade", true)', ".snapshot()", ".restore("):
        assert call in JS, call
    assert "NMSKQuickCard" not in JS and "NMSKQuick." not in JS           # the quick card is not touched; the panel follows the selection
    assert "onAfterDraw" in JS and "toScreen" in JS                        # markers through the engine's public add-on hooks


def test_templates_in_sync():
    for s in ("scripts/sync_innervation_q322.py", "scripts/sync_modes_q272.py"):
        r = subprocess.run([sys.executable, str(REPO / s), "--check"], capture_output=True, text=True)
        assert r.returncode == 0, s + ": " + r.stdout + r.stderr
    for t in (ZAN, OWN):
        assert t.count("<!-- Q322 html begin -->") == 1 and t.index("<!-- Q321 html end -->") < t.index("<!-- Q322 html begin -->")


def test_public_text_is_clean():
    for name, t in (("js", JS), ("css", CSS), ("zan", ZAN), ("own", OWN)):
        low = t.lower()
        for w in FORBIDDEN:
            assert w not in low, (name, w)
    for name, t in (("js", JS), ("css", CSS)):
        assert not INJ.search(t), (name, INJ.search(t).group(0))
    for f in (PLACE, SIDECAR, D / "innervation.js"):
        src = f.read_text(encoding="utf-8")
        assert "clinical/data" not in src and 'REPO / "clinical"' not in src, f      # never reads the private layer
        assert not re.search(r"opus|sonnet|haiku|claude-", src, re.I), f


@pytest.mark.parametrize("page", MODE_PAGES)
def test_sidecar_is_public_and_complete(page):
    sc = _load("sc322", SIDECAR)
    res = sc.build(page)                       # raises on a banned or injection term
    txt = json.dumps(res, ensure_ascii=False)
    assert not INJ.search(txt) and not any(w in txt.lower() for w in FORBIDDEN)
    assert all("citation" not in s for s in res["sources"].values())          # titles are not shipped
    assert set(res["muscles"]) == set(DATA_PUB["muscles"])
    for k, m in res["muscles"].items():
        assert m["nerve"] and m["trunks"], k                                   # every record has a nerve and a colour key
        assert m["roots"]["adopted"] == DATA_PUB["muscles"][k]["roots"]["adopted"]
        assert len(m["iz"]) == len(DATA_PUB["muscles"][k]["iz"])


@pytest.mark.parametrize("page", MODE_PAGES)
def test_band_placement_rules(page):
    b = iz_bands(page)
    assert b["page"] == page and b["fail_mm"] == 5.0
    assert not b["landmark_failures"]
    lines = DATA_PUB["lines"]
    placed = [x for x in b["bands"] if x["status"] == "placed"]
    assert len(placed) >= 150
    for x in placed:
        assert x["dot_inside"], (x["muscle"], x["part"], x["side"])           # every dot inside its muscle mesh
        assert x["rings"] and all(len(r) >= 3 for r in x["rings"])
        if lines[x["line"]]["mode"] == "level" and "shifted_mm" not in x:
            pct = sum(x["pct"]) / 2 if isinstance(x["pct"], list) else x["pct"]
            assert abs(x["level_pct"] - pct) / 100 * x["line_len_mm"] <= 1.0, (x["muscle"], x["part"])   # band level within 1 mm
    # both sides placed (or both not): the rule does not depend on the side
    st = {}
    for x in b["bands"]:
        st.setdefault((x["muscle"], x["iz"]), {})[x["side"]] = x["status"]
    for k, v in st.items():
        assert v.get("l") == v.get("r"), k
    for x in b["bands"]:
        if x["status"] == "failed":
            assert x["reason"]
    # every band of the json appears once per side
    assert len(b["bands"]) == 2 * sum(len(m["iz"]) for m in DATA_PUB["muscles"].values())


@pytest.mark.parametrize("page", MODE_PAGES)
def test_dots_inside_by_winding_number(page):
    html = _load("piz", PLACE).PAGES[page]
    if not html.exists():
        pytest.skip("build page not present (build/ is not in git)")
    sys.path.insert(0, str(REPO / "scripts" / "anatomy" / "q219"))
    import numpy as np
    import geomlib as G
    body = G.load_zan(html)
    for x in iz_bands(page)["bands"]:
        if x["status"] != "placed":
            continue
        vs, fs, o = [], [], 0
        for i in x["structures"]:
            vs.append(body[i]["v"]); fs.append(body[i]["f"] + o); o += len(body[i]["v"])
        V, F = np.vstack(vs), np.vstack(fs)
        assert G.inside(np.array([x["dot"]]), V, F)[0], (x["muscle"], x["part"], x["side"])


def test_regen_ships_the_sidecar_on_base_pages_only():
    src = (REPO / "scripts" / "regen_template_only.py").read_text(encoding="utf-8")
    assert 'if p in ("base_m", "base_f"):' in src and "scripts/anatomy/q322/build_sidecar_q322.py" in src
