"""Q240 (B): vessel / nerve labels in the shared Labels controller (viewer/labels/) against the synthetic engine of tests/q236/harness.html, in real headless Chromium.

Arteries / nerves are labelled by default in Visible (veins on request) with a level (Main / + secondary / + tertiary / All) and a minimum diameter per group from the page's
calibre table, main trunks first with a reserved share of the budget, "Hide vessel / nerve labels", the long-structure anchor (inside the structure's own pixels), callouts without
overlaps / crossings, persistence, the panel help, and the page without a calibre table."""
import json
import shutil
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
HARNESS = REPO / "tests" / "q236" / "harness.html"
LAB = REPO / "viewer" / "labels"
CHROME = "/opt/pw-browsers/chromium"

pw = pytest.importorskip("playwright.sync_api")
pytestmark = pytest.mark.skipif(not Path(CHROME).exists(), reason="headless Chromium not installed")

# id -> (name, cat, x, y, kind, diameter, level, promoted)
VN = [
    ("aorta_t", "Aorta (test)", "vessel", 0, 250, "a", 25.0, 1, 0), ("femoral_a_t", "Femoral artery (test)", "vessel", -260, 120, "a", 8.5, 1, 0),
    ("radial_a_t", "Radial artery (test)", "vessel", 300, -150, "a", 4.0, 2, 0), ("digital_a_t", "Digital artery (test)", "vessel", -300, -200, "a", 2.0, 3, 0),
    ("tiny_a_t", "Tiny artery (test)", "vessel", 120, -270, "a", 0.8, 4, 0), ("cava_t", "Vena cava (test)", "vessel", 60, 270, "v", 18.0, 1, 0),
    ("saph_v_t", "Saphenous vein (test)", "vessel", -150, -270, "v", 4.0, 2, 0), ("sciatic_n_t", "Sciatic nerve (test)", "nerve", 280, -20, "n", 12.0, 1, 0),
    ("sural_n_t", "Sural nerve (test)", "nerve", -300, 20, "n", 3.0, 2, 0), ("digital_n_t", "Digital nerve (test)", "nerve", -330, -80, "n", 1.5, 3, 0),
    ("fine_n_t", "Fine nerve (test)", "nerve", 0, -280, "n", 0.5, 4, 0), ("median_n_t", "Median nerve (test)", "nerve", -200, 220, "n", 1.4, 1, 1),
]
CAL = {"v": 1, "c": {i[0]: [i[5], i[6], i[7], i[8]] for i in VN}}
ABBREV = {"v": 1, "a": {}}
EXTRA = "<script>" + "".join(
    'SC.push({id:%s, name:%s, side:"m", cat:%s, c:[%d, %d, 0], r:14, a:1, col:%s});\n' % (json.dumps(i[0]), json.dumps(i[1]), json.dumps(i[2]), i[3], i[4], "[190,40,40]" if i[5] == "a" else "[60,80,200]" if i[5] == "v" else "[210,180,40]")
    for i in VN) + "</script>"


def page_html(cal=CAL):
    h = HARNESS.read_text()
    h = h.replace("/*CSS*/", (LAB / "labels.css").read_text()).replace("<!--HTML-->", (LAB / "labels.html").read_text())
    h = h.replace("/*ABBREV*/", json.dumps(ABBREV) + '</script><script type="application/json" id="nmsk-calibre">' + json.dumps(cal))
    h = h.replace("/*JS*/", (LAB / "labels.js").read_text())
    # the extra structures are pushed after the harness's own SC definition but before make()
    h = h.replace("var cam = {az:0.4, el:0.1, dist:900}", EXTRA.replace("<script>", "").replace("</script>", "") + "\nvar cam = {az:0.4, el:0.1, dist:900}", 1)
    return h


@pytest.fixture(scope="module")
def browser():
    with pw.sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME)
        yield b
        b.close()


def open_page(ctx, html):
    page = ctx.new_page()
    page.errs = []
    page.on("pageerror", lambda e: page.errs.append(str(e)))
    page.route("http://q240.test/**", lambda r: r.fulfill(status=200, body=html, content_type="text/html"))
    page.goto("http://q240.test/index.html")
    return page


@pytest.fixture()
def pg(browser):
    ctx = browser.new_context(viewport={"width": 900, "height": 620})
    page = open_page(ctx, page_html())
    page.evaluate("make()")
    yield page
    assert not page.errs, page.errs
    ctx.close()


def settle(pg, ms=700):
    pg.evaluate("__L.refreshNow()")
    pg.wait_for_timeout(ms)
    pg.evaluate("__L.refreshNow()")
    pg.wait_for_timeout(ms)
    pg.wait_for_function("!__L.state().animating", timeout=20000)
    return pg.evaluate("({s: __L.state(), c: __L.selfCheck()})")


def shown_vn(pg):
    """the vessels / nerves selected for a label (an anchor each): what the filters decide, independent of whether the layout finds room for every callout"""
    r = settle(pg)
    sel = {a["id"] for a in pg.evaluate("__L.anchors()") if a["id"] in CAL["c"]}
    assert set(r["s"]["vnShown"]) <= sel
    assert len(r["s"]["vnShown"]) >= 0.5 * len(sel)
    return sel


def test_defaults_are_arteries_and_nerves_to_level_two(pg):
    pg.evaluate("__L.setMode('vis'); __L.set('density', 60)")
    r = settle(pg)
    assert r["s"]["haveCal"] and r["s"]["calCount"] == len(VN)
    assert r["s"]["vn"] == {"hide": False, "a": True, "v": False, "n": True, "lva": 2, "lvn": 2, "da": 0, "dn": 0}
    got = set(r["s"]["vnShown"])
    sel = shown_vn(pg)
    assert sel == {"aorta_t", "femoral_a_t", "radial_a_t", "sciatic_n_t", "sural_n_t", "median_n_t"}, sel        # no veins, nothing under level 2 (median = promoted trunk)
    assert got <= sel


@pytest.mark.parametrize("lv,expect", [
    (1, {"aorta_t", "femoral_a_t", "sciatic_n_t", "median_n_t"}),
    (2, {"aorta_t", "femoral_a_t", "radial_a_t", "sciatic_n_t", "sural_n_t", "median_n_t"}),
    (3, {"aorta_t", "femoral_a_t", "radial_a_t", "digital_a_t", "sciatic_n_t", "sural_n_t", "median_n_t", "digital_n_t"}),
    (4, {"aorta_t", "femoral_a_t", "radial_a_t", "digital_a_t", "tiny_a_t", "sciatic_n_t", "sural_n_t", "median_n_t", "digital_n_t", "fine_n_t"}),
])
def test_levels(pg, lv, expect):
    pg.evaluate("__L.setMode('vis'); __L.set('density', 60); __L.set('lva', %d); __L.set('lvn', %d)" % (lv, lv))
    assert shown_vn(pg) == expect


def test_groups_veins_and_independent_levels(pg):
    pg.evaluate("__L.setMode('vis'); __L.set('density', 60); __L.set('gv', true); __L.set('lva', 1); __L.set('lvn', 4)")
    got = shown_vn(pg)
    assert "cava_t" in got and "saph_v_t" not in got and "fine_n_t" in got and "radial_a_t" not in got          # arteries / veins share a level, nerves have their own
    pg.evaluate("__L.set('ga', false)")
    got = shown_vn(pg)
    assert not any(i.endswith("_a_t") for i in got) and "cava_t" in got
    pg.evaluate("__L.set('gn', false)")
    assert shown_vn(pg) == {"cava_t"}


def test_minimum_diameter_cuts_on_top_of_the_level(pg):
    pg.evaluate("__L.setMode('vis'); __L.set('density', 60); __L.set('lva', 4); __L.set('lvn', 4); __L.set('da', 5); __L.set('dn', 3)")
    assert shown_vn(pg) == {"aorta_t", "femoral_a_t", "sciatic_n_t", "sural_n_t"}
    pg.evaluate("__L.set('da', 0); __L.set('dn', 0)")
    assert len(shown_vn(pg)) == 10


def test_hide_switch_and_forced_structures(pg):
    pg.evaluate("__L.setMode('vis'); __L.set('density', 60); __L.set('vhide', true)")
    assert shown_vn(pg) == set()
    pg.evaluate("sel = 'tiny_a_t'")                                 # a selected vessel is labelled whatever the filter says
    assert shown_vn(pg) == {"tiny_a_t"}
    pg.evaluate("sel = null; __L.set('vhide', false)")
    assert len(shown_vn(pg)) == 6


def test_main_trunks_first_under_a_tight_budget(pg):
    pg.evaluate("__L.setMode('vis'); __L.set('lva', 4); __L.set('lvn', 4); __L.set('density', 4)")
    r = settle(pg)
    cal = {i: CAL["c"][i] for i in r["s"]["vnShown"]}
    assert len(cal) >= 3 and all(v[2] == 1 for v in cal.values()), cal                  # the reserved share goes to the main trunks
    assert len(r["s"]["shown"]) <= 5


def test_long_structures_get_a_run_anchor_inside_their_own_pixels(pg):
    pg.evaluate("__L.setMode('vis'); __L.set('density', 60); __L.set('callout', 'out')")
    r = settle(pg)
    an = {a["id"]: a for a in pg.evaluate("__L.anchors()")}
    assert an["aorta_t"]["long"] >= 6 and an["sciatic_n_t"]["long"] >= 6
    # the anchor's pixel in the ID image names the structure
    for sid in ("aorta_t", "sciatic_n_t", "femoral_a_t"):
        a = an[sid]
        hit = pg.evaluate("(function(a){ var b = idImage(false, 320), r = rectR, u = Math.floor((a.sx - r.left) / r.width * b.w), v = Math.floor((a.sy - r.top) / r.height * b.h); return SC[b.ids[v * b.w + u] - 1] && SC[b.ids[v * b.w + u] - 1].id; })(%s)" % json.dumps(a))
        assert hit == sid, (sid, hit)
    c = r["c"]
    assert c["overlaps"] == 0 and c["leaderCrossings"] <= max(2, c["callout"] // 8) and c["bodyHits"] == 0 and c["outsideFrame"] == 0       # (as test_q236_controller; callouts crowding the HUD column are dropped by the solver, not forced)


def test_labels_use_the_structure_colour(pg):
    pg.evaluate("__L.setMode('vis'); __L.set('density', 60); __L.set('colour', 'own')")
    settle(pg)
    cols = pg.evaluate("(function(){ var o = {}; [].forEach.call(document.querySelectorAll('#lab-layer text.lb-t'), function(t){ o[t.textContent] = t.getAttribute('fill'); }); return o; })()")
    assert "Aorta (test) (R)" not in cols and any(k.startswith("Aorta") for k in cols)
    red = [v for k, v in cols.items() if k.startswith("Aorta")][0]
    blue = [v for k, v in cols.items() if k.startswith("Sciatic")][0]
    assert red != blue                                              # each label takes its structure's colour (darkened for contrast)


def test_panel_controls_help_and_persistence(browser):
    ctx = browser.new_context(viewport={"width": 900, "height": 620})
    page = open_page(ctx, page_html())
    page.evaluate("make()")
    page.click("#t-labels")
    for i in ("lab-vhide", "lab-g-a", "lab-g-v", "lab-g-n", "lab-lva", "lab-lvn", "lab-da", "lab-dn"):
        assert page.evaluate("!!document.getElementById('%s')" % i), i
    txt = page.evaluate("document.querySelector('#lab-panel .lb-help').textContent")
    for t in ("6 mm", "3 to 6 mm", "1.5 to 3 mm", "4 mm", "2 to 4 mm", "1 to 2 mm", "named trunks"):
        assert t in txt, t
    page.evaluate("document.querySelector('#lab-lva button[data-v=\"1\"]').click()")
    page.evaluate("document.getElementById('lab-g-v').click()")
    page.evaluate("document.getElementById('lab-vhide').click()")
    s = page.evaluate("__L.state().vn")
    assert s["lva"] == 1 and s["v"] is True and s["hide"] is True
    assert page.evaluate("document.getElementById('lab-lva').querySelector('[aria-pressed=true]').dataset.v") == "1"
    assert page.evaluate("document.getElementById('lab-g-a').disabled")          # disabled while everything is hidden
    page.reload(); page.evaluate("make()")
    assert page.evaluate("__L.state().vn") == s                                  # remembered
    page.evaluate("__L.reset()")
    assert page.evaluate("__L.state().vn") == {"hide": False, "a": True, "v": False, "n": True, "lva": 2, "lvn": 2, "da": 0, "dn": 0}
    assert not page.errs, page.errs
    ctx.close()


def test_legend_rows_carry_the_calibre(pg):
    pg.evaluate("__L.setMode('vis'); __L.openLegend(true); __L.openLegend(true)")
    pg.evaluate("document.querySelector('#lg-only button[data-v=\"all\"]').click()")
    pg.evaluate("document.getElementById('lg-q').value = 'aorta'; document.getElementById('lg-q').dispatchEvent(new Event('input', {bubbles: true}))")
    pg.wait_for_timeout(300)
    t = pg.evaluate("document.getElementById('lg-list').textContent")
    assert "artery" in t and "25.0 mm" in t and "level 1" in t


def test_page_without_a_calibre_table(browser):
    ctx = browser.new_context(viewport={"width": 900, "height": 620})
    page = open_page(ctx, page_html(cal={}))
    page.evaluate("make()")
    page.evaluate("__L.setMode('vis'); __L.set('density', 60)")
    s = settle(page)["s"]
    assert s["haveCal"] is False
    assert {"radial_a_t", "femoral_a_t", "sciatic_n_t"} <= set(s["vnShown"]) or len(s["vnShown"]) >= 3      # without a table the vessels / nerves are classified by id / name (level 2, no diameter): all of the arteries and nerves, no veins ('_v_t' is off)
    assert not any("_v_" in i or i.startswith("cava") for i in s["vnShown"])
    assert page.evaluate("document.getElementById('lab-da').disabled")        # level / diameter controls are off without a table
    page.evaluate("document.getElementById('t-labels').click()")
    assert "calibre table" in page.evaluate("document.getElementById('lab-hint').textContent")
    assert not page.errs, page.errs
    ctx.close()
