"""Q343: the name card's group families (Myofascial lines, Innervation) and Parts chooser -- source-level assertions.
The browser run is scripts/anatomy/q343/verify_groups_q343.py."""
from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
D = REPO / "viewer" / "groups342"
JS = (D / "groups342.js").read_text(encoding="utf-8")
CSS = (D / "groups342.css").read_text(encoding="utf-8")
QC = (REPO / "viewer" / "quickcard" / "quickcard.js").read_text(encoding="utf-8")
ZAN = (REPO / "viewer" / "zan_atlas.template.html").read_text(encoding="utf-8")
OWN = (REPO / "viewer" / "atlas_viewer.template.html").read_text(encoding="utf-8")
BANNED = ["ultrasound", "hounsfield", "t1_se", "imaging_tissues", "tissue table", "nmskultrasound", "acoustic", "mrayl", "b-mode"]
SIDECAR = REPO / "scripts" / "anatomy" / "q342" / "build_sidecar_q342.py"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def test_templates_in_sync():
    for s in ("scripts/sync_groups342_q343.py", "scripts/sync_quickcard_q321.py"):
        r = subprocess.run([sys.executable, str(REPO / s), "--check"], capture_output=True, text=True)
        assert r.returncode == 0, s + ": " + r.stdout + r.stderr
    for t in (ZAN, OWN):
        assert t.count("<!-- Q343 html begin -->") == 1 and t.index("<!-- Q321 html end -->") < t.index("<!-- Q343 html begin -->")


def test_no_banned_words():
    for name, t in (("js", JS), ("css", CSS), ("qc", QC), ("zan", ZAN), ("own", OWN)):
        low = t.lower()
        for w in BANNED:
            assert w not in low, (name, w)


def test_families_registered_through_the_card_registry():
    assert 'Q.family({key:"mfl", label:"Myofascial lines", order:40' in JS
    assert 'Q.family({key:"inn", label:"Innervation", order:50' in JS
    assert 'Q.addon({key:"parts"' in JS
    assert "markIds(ids, true, true, true)" in JS and "NMSKHistory" in JS          # one undo step per choice, via the controller
    assert 'fetch(URL)' in JS and 'var URL = "groups_q342.json"' in JS             # lazy, from the page's sidecar


def test_honest_labels():
    js = JS.replace("\\u2014", "\u2014")
    for s in ("Rule-based from sourced posture + muscle actions", "No dissection evidence \u2014 contested",
              "Not examined by any review \u2014 contested", "Contested concept", "no separate mesh on this body"):
        assert s in js or s in SIDECAR.read_text(encoding="utf-8"), s
    assert "not delimitable from the sources" in SIDECAR.read_text(encoding="utf-8")


def test_card_registry_has_sheets_addons_and_scope():
    for k in ("qc-rback", "relBack", "function addon(a)", "setScope:setScope", "data-scope", "it.off", "qc-rwhy", "addon:addon"):
        assert k in QC, k
    assert "ArrowLeft" in QC and "Escape" in QC


def test_regen_builds_the_sidecar_for_the_base_pages():
    rg = (REPO / "scripts" / "regen_template_only.py").read_text(encoding="utf-8")
    assert '"scripts/anatomy/q342/build_sidecar_q342.py", p, str(dst)' in rg


@pytest.mark.parametrize("page,dirname", [("base_m", "viewer_zan_atlas"), ("base_f", "viewer_base_female")])
def test_sidecar_page_ids_only_and_clean(page, dirname):
    d = REPO / "build" / "q309" / dirname
    if not d.is_dir():
        pytest.skip("built page not present")
    sc = _load("sc342", SIDECAR)
    ids = sc.page_ids(d)
    res = sc.build(page, d)
    txt = json.dumps(res, ensure_ascii=False)
    for w in BANNED + ["scripts/"]:
        assert w not in txt.lower(), w
    got = set()

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                if k in ("r", "l", "mid") and isinstance(v, list):
                    got.update(v)
                else:
                    walk(v)
        elif isinstance(o, list):
            for x in o:
                walk(x)
    walk(res["m"]); walk(res["lines"]["items"]); walk(res["inn"]["nerves"]); walk(res["parts"])
    assert got and got <= ids, sorted(got - ids)[:5]
    cls = {c["k"]: c for c in res["lines"]["cls"]}
    assert cls["horizontal"].get("off") and cls["horizontal"]["why"]
    assert all(L["ev"] in ("strong", "moderate", "none", "not_examined") for L in res["lines"]["items"])
    assert len(res["lines"]["items"]) == 18 and len(res["inn"]["pats"]) == 22  # Q348: + 3 Tittel slings
    assert all(set(s) <= {"l", "doi", "pmid"} for s in res["src"].values())
    pm = {m["id"]: m for m in res["parts"]}
    assert [p["st"] for p in pm["pectoralis_major"]["p"]] == ["separate_mesh"] * 3
    assert all(p["st"] == "rule" and p["why"] == "no separate mesh on this body" for p in pm["trapezius"]["p"])
    assert "C6" in [L["lv"] for L in res["inn"]["levels"]]
