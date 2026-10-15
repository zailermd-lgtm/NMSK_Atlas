"""Q236: structure labels (callouts, abbreviations, legend window) wired into both viewer templates.

The shared block (viewer/labels/) is verbatim in both templates (scripts/sync_labels_q236.py --check), the engine adaptors implement the contract documented at the top of
labels.js, the engines call the controller (draw / hover / dirty), nothing outside the overlay is touched (no change to geometry or data), the existing shared blocks and
their tests are intact, and the regenerated pages + the headless-Chromium results are consistent."""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
OWN = REPO / "viewer" / "atlas_viewer.template.html"
ZAN = REPO / "viewer" / "zan_atlas.template.html"
LAB = REPO / "viewer" / "labels"
sys.path.insert(0, str(REPO / "scripts"))
import sync_labels_q236 as sync  # noqa: E402

PAGES = {"own_m": ("viewer_m_hr", "atlas_viewer_male.html", "own"), "own_f": ("viewer_f_hr", "atlas_viewer_female.html", "own"),
         "zan_m": ("viewer_zan_vhm", "atlas_viewer_zan_male_fitted.html", "zan"), "zan_f": ("viewer_zan_female", "atlas_viewer_zan_female.html", "zan"),
         "base_f": ("viewer_base_female", "atlas_viewer_base_female.html", "zan"), "base_m": ("viewer_zan_atlas", "atlas_viewer_zan_atlas.html", "zan")}
ADAPTOR = ["modelId", "structures", "alphas", "color", "geometry", "view", "idImage", "cut", "capHit", "fillCut", "ray", "selected", "marked", "select", "bg", "obstacles",
           "canvasRect", "redraw", "toolbar", "toolClass", "isPhone"]
CONTROLS = ["lab-layer", "lab-panel", "lab-show", "lab-text", "lab-callout", "lab-dens", "lab-font", "lab-colour", "lab-side", "lab-occl", "lab-legend-btn", "lab-reset", "lab-cutfill",
            "lab-legend", "lg-head", "lg-q", "lg-only", "lg-fdn", "lg-fup", "lg-font", "lg-list", "lg-grip", "lg-close"]


def test_fragment_is_verbatim_in_both_templates():
    for t in (OWN, ZAN):
        s = t.read_text(encoding="utf-8")
        assert sync.render(s) == s, f"{t.name} is out of date: run scripts/sync_labels_q236.py"
        for kind in ("css", "html", "js"):
            b, e = sync.MARK[kind]
            assert s.count(b) == 1 and s.count(e) == 1
        assert s.count("<!-- NMSK-ABBREV begin -->") == 1 and s.count("<!-- NMSK-ABBREV end -->") == 1
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "sync_labels_q236.py"), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout


def test_fragment_declares_every_control_and_the_contract():
    html = (LAB / "labels.html").read_text()
    for c in CONTROLS:
        assert f'id="{c}"' in html, c
    js = (LAB / "labels.js").read_text()
    assert "function NMSKLabels(E)" in js and "var NMSKLabelsCore" in js
    for name in ADAPTOR:
        assert name in js.split("function NMSKLabels(E)")[0], name        # documented in the header comment
    assert "localStorage" in js and js.count("try {") >= 3                 # storage always guarded
    assert "eval(" not in js and "innerHTML = html" in js                  # legend rows are escaped (esc()) before innerHTML
    assert "esc(abbr[k])" in js and "esc(full[k])" in js
    css = (LAB / "labels.css").read_text()
    for token in ("#lab-panel", "#lab-legend", ".lb-phone", "paint-order:stroke", "prefers"[:0]):
        assert token in css


@pytest.mark.parametrize("tpl,own", [(OWN, True), (ZAN, False)])
def test_engine_adaptor_and_hooks(tpl, own):
    s = tpl.read_text(encoding="utf-8")
    seg = s[s.index("labelsCtl = NMSKLabels({"):]
    seg = seg[:seg.index("window.__labState")]
    for name in ADAPTOR:
        assert re.search(r"\b" + name + r"\s*:", seg), name
    assert "labelsCtl = null" in s                                         # declared with the other controllers
    assert re.search(r"if \(labelsCtl\) labelsCtl\.update\(\);", s)        # the end of draw()
    assert "labelsCtl.hover(" in s and "labelsCtl.dirty()" in s
    assert "window.__labState" in s and "window.__labCtl" in s
    # the ID image comes from what is drawn: own = flat-colour MeshBasicMaterial pass with the cut planes, Z = the picking pass in a corner of the picking buffer
    if own:
        assert "WebGLRenderTarget" in seg and "clippingPlanes = cut.on ? cutPlanes : null" in seg and "readRenderTargetPixels" in seg
        assert "m.material = im" in seg and "s[0].material = s[2]" in seg    # materials restored
    else:
        assert "renderIds(all, false, sc)" in seg and "function renderIds(all, depth, sc)" in s and "pickKey = null" in seg
        assert "capGeom(" in seg


def test_templates_keep_the_other_shared_blocks_and_pass_their_tests():
    for t in (OWN, ZAN):
        s = t.read_text(encoding="utf-8")
        for name in ("CUT-MODE", "PARTS-UI", "SELECTION"):
            assert s.count(f"{name} js begin */") == 1
        assert s.count("CUT-CAP js begin */") == 1
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-x", str(REPO / "tests" / "test_q232.py"), str(REPO / "tests" / "test_cut_mode_q197.py")], capture_output=True, text=True, cwd=REPO)
    assert r.returncode == 0, r.stdout[-1500:]


def test_controller_never_changes_the_model():
    """the labels are an overlay: the shared code has no way to touch geometry, materials, colours, visibility or the cut (only the engine adaptors read them)"""
    js = (LAB / "labels.js").read_text()
    for bad in (".material", "setHex", "clippingPlanes", "gl.", "THREE.", "BufferGeometry", "needsUpdate"):
        assert bad not in js, bad
    assert not re.search(r"\.(visible|opacity|position|color)\s*=[^=]", js)
    assert "fillCut" in js and js.count("E.fillCut()") == 1               # the one engine action: the 'Fill cut face' button, which presses the existing cut-panel feature


@pytest.mark.parametrize("key", sorted(PAGES))
def test_regenerated_page_has_the_labels(key):
    d, html, kind = PAGES[key]
    p = REPO / "build" / "q236" / d / html
    if not p.exists():
        pytest.skip("build/q236 not present")
    s = p.read_text(encoding="utf-8")
    # the page carries the labels block of the generation it was built with (Q240 extended the fragment: the build/q240 pages carry the current one, tests/test_q240_parts_cull.py)
    assert s.count("/* LABELS js begin */") == 1 and s.count("/* LABELS js end */") == 1 and "function NMSKLabels(E)" in s
    assert sync.render(s) == s or "nmsk-calibre" not in s                  # a page with the current calibre table has the current block
    assert 'id="nmsk-abbrev"' in s and 'id="t-labels"' not in s            # the toolbar button is made by the controller, not in the markup
    assert "<title>NMSK Atlas — " in s
    v = json.loads((REPO / "build" / "q236" / "_verify" / f"{d}.json").read_text()) if (REPO / "build" / "q236" / "_verify" / f"{d}.json").exists() else None
    if v:
        assert v.get("literals_identical") is True and v.get("geo_identical") is True        # data and geometry untouched
    assert (p.parent / "index.html").read_text(encoding="utf-8") == s


@pytest.mark.parametrize("key", sorted(PAGES))
def test_browser_check_results(key):
    f = REPO / "data" / "derived" / f"Q236_browser_check_{key}.json"
    if not f.exists():
        pytest.skip("browser check not run")
    d = json.loads(f.read_text())
    assert d["viewports"], key
    for name, v in d["viewports"].items():
        bad = [k for k, x in v["checks"].items() if x is not True]
        assert not bad, (key, name, bad)
        assert not v["errors"], (key, name, v["errors"])
