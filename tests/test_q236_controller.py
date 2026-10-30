"""Q236: the shared structure-label controller (viewer/labels/) against a tiny synthetic engine in real headless Chromium (no WebGL needed).

The synthetic engine (tests/q236/harness.html) is an orthographic camera orbiting a few spheres with a z-buffered ID image, a cut plane and a cut-face lookup, i.e. the same
adaptor contract the two real engines implement. Checks: modes (Off / Selected / Visible / All), occlusion (a structure fully inside another gets no label; a translucent one
in front does not hide what is behind it; ghost / hidden ones get none), the density cap, callouts (no overlaps, nothing touching the body silhouette, nothing inside a HUD
panel, no crossing leader lines, leader dot on the structure), inline mode, re-solving after an orbit, CUT mode (labels only for the kept side, anchors ON the cut face when
it is filled), abbreviation text, the legend window (size buttons, font, search, row click, drag, corner resize, bottom sheet on phones), persistence in localStorage and the
blocked-storage fallback."""
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

ABBREV = {"v": 1, "a": {"body": ["BT", 0, "Body trunk"], "heart": ["HRT", 1, "Heart"], "arm_l": ["AM-L", 1, "Arm muscle"], "arm_r": ["AM-R", 1, "Arm muscle"]}}


def page_html(abbrev=ABBREV):
    h = HARNESS.read_text()
    h = h.replace("/*CSS*/", (LAB / "labels.css").read_text()).replace("<!--HTML-->", (LAB / "labels.html").read_text())
    h = h.replace("/*ABBREV*/", json.dumps(abbrev)).replace("/*JS*/", (LAB / "labels.js").read_text())
    return h


@pytest.fixture(scope="module")
def browser():
    with pw.sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME)
        yield b
        b.close()


def open_page(ctx, html=None):
    """a real origin (localStorage works there; about:blank denies it)"""
    page = ctx.new_page()
    page.errs = []
    page.on("pageerror", lambda e: page.errs.append(str(e)))
    body = html or page_html()
    page.route("http://q236.test/**", lambda r: r.fulfill(status=200, body=body, content_type="text/html"))
    page.goto("http://q236.test/index.html")
    return page


@pytest.fixture()
def pg(browser):
    ctx = browser.new_context(viewport={"width": 900, "height": 620})
    page = open_page(ctx)
    page.evaluate("make()")
    yield page
    assert not page.errs, page.errs
    ctx.close()


def settle(pg, ms=900):
    pg.evaluate("__L.refreshNow()")
    pg.wait_for_timeout(ms)
    pg.evaluate("__L.refreshNow()")
    pg.wait_for_timeout(ms)
    pg.wait_for_function("!__L.state().animating", timeout=20000)
    return pg.evaluate("({s: __L.state(), c: __L.selfCheck()})")


def test_off_by_default_and_toolbar_button(pg):
    assert pg.evaluate("__L.state().mode") == "off"
    assert pg.evaluate("document.getElementById('lab-layer').style.display") in ("", "none")
    assert pg.evaluate("!!document.getElementById('t-labels')")
    pg.click("#t-labels")
    assert pg.evaluate("!document.getElementById('lab-panel').hidden")
    assert pg.evaluate("__L.state().mode") == "vis"          # opening the panel switches labels on


def test_visible_mode_occlusion_and_density(pg):
    pg.evaluate("__L.setMode('vis')")
    r = settle(pg)
    shown = set(r["s"]["shown"])
    assert "heart" not in shown                               # fully inside the opaque body
    assert "ghost" not in shown and "hid" not in shown        # 10 % opacity / not drawn
    assert "behind" in shown                                  # seen through the 40 % glass in front of it
    assert {"arm_l", "arm_r", "body"} <= shown
    pg.evaluate("__L.set('density', 5)")
    r = settle(pg)
    assert len(r["s"]["shown"]) <= 6
    assert r["s"]["visible"] >= 8


def test_hide_occluded_option_shows_the_hidden_one_dashed(pg):
    pg.evaluate("__L.setMode('sel'); document.defaultView.sel = 'heart'; sel = 'heart'")
    r = settle(pg)
    assert "heart" not in r["s"]["shown"]                     # occluded: no label even though it is selected
    pg.evaluate("__L.set('occl', false)")
    r = settle(pg)
    assert "heart" in r["s"]["shown"]
    assert pg.evaluate("!!document.querySelector('#lab-layer .lb-hid')")


def test_selected_hovered_and_marked_mode(pg):
    pg.evaluate("__L.setMode('sel')")
    assert settle(pg)["s"]["shown"] == []
    pg.evaluate("sel = 'arm_l'")
    assert settle(pg)["s"]["shown"] == ["arm_l"]
    pg.evaluate("marks = ['arm_r', 's3']; __L.dirty()")
    assert set(settle(pg)["s"]["shown"]) == {"arm_l", "arm_r", "s3"}
    pg.evaluate("__L.hover('s5')")
    assert "s5" in settle(pg)["s"]["shown"]


def test_all_mode_labels_every_visible_structure(pg):
    pg.evaluate("__L.setMode('all')")
    r = settle(pg)
    assert len(r["s"]["shown"]) >= 15 and "heart" not in r["s"]["shown"]
    assert r["c"]["overlaps"] == 0


def test_callouts_outside_the_body_without_overlaps_or_crossings(pg):
    pg.evaluate("__L.setMode('all'); __L.set('callout','out')")
    r = settle(pg, 1200)
    c = r["c"]
    assert c["callout"] >= 12 and c["inline"] == 0
    assert c["overlaps"] == 0 and c["bodyHits"] == 0 and c["outsideFrame"] == 0 and c["obstacleHits"] == 0
    assert c["leaderCrossings"] <= max(2, c["callout"] // 8)
    assert c["maxLeader"] < 420
    # every leader dot lies on the structure it belongs to (its pixel in the ID image names it)
    ok = pg.evaluate("""(function(){ var bad = 0, b = __L.boxes(); var id = idImage(false, 700);
      b.forEach(function(x){ if (!x.lead) return; var pts = x.lead.split(' ')[0].split(','); var u = Math.floor((+pts[0] - 100) / 700 * id.w), v = Math.floor(+pts[1] / 600 * id.h);
        var s = SC.map(function(q){return q.id;}).indexOf(x.id); var hit = false; for (var dy = -2; dy <= 2; dy++) for (var dx = -2; dx <= 2; dx++){ var n = id.ids[(v + dy) * id.w + u + dx]; if (n === s + 1) hit = true; }
        if (!hit && SC[s].a >= 0.6) bad++; }); return bad; })()""")
    assert ok == 0


def test_inline_mode_keeps_text_on_the_structure(pg):
    pg.evaluate("__L.setMode('vis'); __L.set('density', 30); __L.set('callout','in')")
    r = settle(pg)
    c = r["c"]
    assert c["callout"] == 0 and c["inline"] >= 3 and c["overlaps"] == 0


def test_auto_mixes_inline_and_callouts_and_respects_font_size(pg):
    pg.evaluate("__L.setMode('vis'); __L.set('density', 40); __L.set('font', 11)")
    small = settle(pg)["c"]
    pg.evaluate("__L.set('font', 20)")
    big = settle(pg)
    assert big["c"]["overlaps"] == 0 and big["c"]["bodyHits"] == 0
    assert big["c"]["inline"] <= small["inline"]         # larger text fits on fewer structures
    assert pg.evaluate("document.getElementById('lab-layer').getAttribute('font-size')") == "20"


def test_orbit_resolves_again_and_labels_follow_their_structures(pg):
    pg.evaluate("__L.setMode('all'); __L.set('callout','out')")
    a = settle(pg)
    before = {b["id"]: b for b in pg.evaluate("__L.boxes()")}
    pg.evaluate("cam.az = 2.1; frame()")
    b = settle(pg, 1400)
    assert b["c"]["overlaps"] == 0 and b["c"]["bodyHits"] == 0 and b["c"]["outsideFrame"] == 0
    after = {x["id"]: x for x in pg.evaluate("__L.boxes()")}
    moved = [i for i in before if i in after and abs(before[i]["x"] - after[i]["x"]) + abs(before[i]["y"] - after[i]["y"]) > 30]
    assert len(moved) >= 5                                    # the callouts really followed the rotation
    assert "heart" not in after


def test_cut_mode_only_kept_side_and_anchors_on_the_cut_face(pg):
    pg.evaluate("__L.setMode('all'); __L.set('callout','out')")
    full = settle(pg)["s"]["shown"]
    # remove x < 0 (kept side: x >= 0), fill the cut face, look from the removed side (camera on -x)
    pg.evaluate("cutS = {on:true, kn:[1,0,0], c:0, th:0}; capOn = true; cam.az = -Math.PI / 2; cam.el = 0.02; frame()")
    r = settle(pg, 1200)
    shown = set(r["s"]["shown"])
    clipped = pg.evaluate("SC.filter(function(s){ return s.c[0] + s.r < 0; }).map(function(s){ return s.id; })")
    assert "arm_l" in clipped and not (shown & set(clipped))   # structures wholly on the removed side get no label
    assert r["s"]["cutOn"] and r["s"]["capOn"]
    assert r["s"]["kinds"].get("cut", 0) >= 3                 # anchors ON the cut face
    assert r["c"]["overlaps"] == 0 and r["c"]["bodyHits"] == 0
    # the cut-face anchors really lie on the plane x = 0 and inside the structure's section
    bad = pg.evaluate("""(function(){ var bad = 0, st = __L.state(); (__L.anchors ? __L.anchors() : []).forEach(function(a){ if (a.kind !== 'cut') return;
        var s = SC.filter(function(q){ return q.id === a.id; })[0]; if (Math.abs(a.p3[0]) > 1e-3 || Math.hypot(a.p3[0] - s.c[0], a.p3[1] - s.c[1], a.p3[2] - s.c[2]) > s.r + 1e-3) bad++; }); return bad; })()""")
    assert bad == 0
    assert "heart" in shown                                   # the cut exposes the heart inside the body
    pg.evaluate("cutS = {on:false, kn:[1,0,0], c:0, th:0}; capOn = false; cam.az = 0.4; frame()")
    r = settle(pg)
    assert "heart" not in r["s"]["shown"] and "arm_l" in r["s"]["shown"] and set(full) >= set()


def test_abbreviation_text_and_side_marks(pg):
    pg.evaluate("__L.setMode('vis'); __L.set('density', 40); __L.set('callout','out'); __L.set('text','abbr')")
    r = settle(pg)
    texts = pg.evaluate("Array.prototype.map.call(document.querySelectorAll('#lab-layer .lb-t'), function(t){return t.textContent;})")
    assert "AM-L" in texts and "AM-R" in texts and "BT" in texts
    assert pg.evaluate("__L.abbr('heart')") == "HRT"
    pg.evaluate("__L.set('text','full')")
    texts = pg.evaluate("Array.prototype.map.call(document.querySelectorAll('#lab-layer .lb-t'), function(t){return t.textContent;})")
    assert "Arm muscle (L)" in texts and "Arm muscle (R)" in texts
    pg.evaluate("__L.set('side', false)")
    texts = pg.evaluate("Array.prototype.map.call(document.querySelectorAll('#lab-layer .lb-t'), function(t){return t.textContent;})")
    assert "Arm muscle" in texts and "Arm muscle (L)" not in texts


def test_legend_window_controls(pg):
    pg.evaluate("__L.setMode('vis'); __L.set('density', 40)")
    settle(pg)
    pg.click("#t-labels")
    pg.click("#lab-legend-btn")
    assert pg.evaluate("!document.getElementById('lab-legend').hidden")
    n_on = pg.evaluate("document.querySelectorAll('#lg-list .lg-row').length")
    assert n_on == len(pg.evaluate("__L.state().shown")) > 3
    sizes = {}
    for s in "SML":
        pg.click(f'#lab-legend [data-size="{s}"]')
        sizes[s] = pg.evaluate("(function(){var r=document.getElementById('lab-legend').getBoundingClientRect();return [r.width,r.height];})()")
    assert sizes["S"][0] < sizes["M"][0] < sizes["L"][0] and sizes["S"][1] < sizes["M"][1] < sizes["L"][1]
    f0 = pg.evaluate("parseFloat(getComputedStyle(document.querySelector('#lg-list .lg-row')).fontSize)")
    pg.click("#lg-fup"); pg.click("#lg-fup")
    assert pg.evaluate("parseFloat(getComputedStyle(document.querySelector('#lg-list .lg-row')).fontSize)") == f0 + 2
    pg.evaluate("(function(){var s=document.getElementById('lg-font'); s.value=11; s.dispatchEvent(new Event('input',{bubbles:true}));})()")
    assert pg.evaluate("parseFloat(getComputedStyle(document.querySelector('#lg-list .lg-row')).fontSize)") == 11
    pg.click('#lg-only [data-v="all"]')
    assert pg.evaluate("document.querySelectorAll('#lg-list .lg-row').length") == pg.evaluate("SC.length")
    pg.fill("#lg-q", "arm")
    assert pg.evaluate("document.querySelectorAll('#lg-list .lg-row').length") == 2
    pg.click("#lg-list .lg-row")
    assert pg.evaluate("calls.select") [-1] in ("arm_l", "arm_r")
    # drag the header, resize with the corner
    pg.click('#lab-legend [data-size="M"]')
    r0 = pg.evaluate("(function(){var r=document.getElementById('lab-legend').getBoundingClientRect();return [r.left,r.top,r.width,r.height];})()")
    hb = pg.locator("#lg-head").bounding_box()
    pg.mouse.move(hb["x"] + 20, hb["y"] + 10); pg.mouse.down(); pg.mouse.move(hb["x"] + 20 + 50, hb["y"] + 10 + 40, steps=5); pg.mouse.up()
    r1 = pg.evaluate("(function(){var r=document.getElementById('lab-legend').getBoundingClientRect();return [r.left,r.top,r.width,r.height];})()")
    assert r1[0] > r0[0] + 30 and r1[1] > r0[1] + 20 and abs(r1[2] - r0[2]) < 1
    gb = pg.locator("#lg-grip").bounding_box()
    pg.mouse.move(gb["x"] + 8, gb["y"] + 8); pg.mouse.down(); pg.mouse.move(gb["x"] + 8 - 60, gb["y"] + 8 - 50, steps=5); pg.mouse.up()
    r2 = pg.evaluate("(function(){var r=document.getElementById('lab-legend').getBoundingClientRect();return [r.left,r.top,r.width,r.height];})()")
    assert r2[2] < r1[2] - 20 and r2[3] < r1[3] - 20 and abs(r2[0] - r1[0]) < 1
    # the open legend is a HUD obstacle for the callouts
    pg.evaluate("__L.set('callout','out'); __L.setMode('all')")
    assert settle(pg)["c"]["obstacleHits"] == 0


def test_phone_panels_are_bottom_sheets(browser):
    ctx = browser.new_context(viewport={"width": 360, "height": 640}, is_mobile=True, has_touch=True)
    pg = open_page(ctx); errs = pg.errs
    pg.evaluate("phone = true; make()")
    pg.evaluate("__L.openPanel(true)")
    assert pg.evaluate("document.getElementById('lab-panel').classList.contains('lb-phone')")
    r = pg.evaluate("(function(){var r=document.getElementById('lab-panel').getBoundingClientRect();return [r.left,r.right,r.bottom,innerWidth,innerHeight];})()")
    assert r[0] >= 0 and r[1] <= r[3] and r[2] <= r[4]
    pg.evaluate("__L.openLegend(true)")
    l = pg.evaluate("(function(){var r=document.getElementById('lab-legend').getBoundingClientRect();return [r.left,r.right,r.bottom,innerWidth,innerHeight];})()")
    assert l[0] == 0 and l[1] == l[3] and abs(l[2] - l[4]) < 1
    assert pg.evaluate("document.getElementById('lab-panel').hidden")       # one sheet at a time
    heights = []
    for s in "SML":
        pg.click(f'#lab-legend [data-size="{s}"]'); heights.append(pg.evaluate("document.getElementById('lab-legend').getBoundingClientRect().height"))
    assert heights[0] < heights[1] < heights[2]
    assert pg.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert not errs
    ctx.close()


def test_settings_persist_in_localstorage_and_survive_blocked_storage(browser):
    ctx = browser.new_context(viewport={"width": 900, "height": 620})
    pg = open_page(ctx); errs = pg.errs
    pg.evaluate("make()")
    pg.evaluate("__L.setMode('all'); __L.set('text','abbr'); __L.set('font', 15); __L.set('callout','out'); __L.set('density', 33); __L.set('colour','neutral'); __L.openLegend(true)")
    s = json.loads(pg.evaluate("localStorage.getItem('nmsk.labels.v1')"))
    assert s["mode"] == "all" and s["text"] == "abbr" and s["font"] == 15 and s["callout"] == "out" and s["density"] == 33 and s["colour"] == "neutral" and s["lg"]["open"] is True
    pg.evaluate("make()")                                                    # a new controller restores them
    st = pg.evaluate("__L.settings()")
    assert (st["mode"], st["text"], st["font"], st["callout"], st["density"], st["colour"], st["lg"]["open"]) == ("all", "abbr", 15, "out", 33, "neutral", True)
    # hostile / out-of-range stored values are clamped or ignored
    pg.evaluate("localStorage.setItem('nmsk.labels.v1', JSON.stringify({mode:'nope', font:999, density:-4, text:5, lg:{w:1, font:'x'}})); make()")
    st = pg.evaluate("__L.settings()")
    assert st["mode"] == "off" and st["font"] == 22 and st["density"] == 3 and st["text"] == "full" and st["lg"]["w"] == 200
    # blocked storage: no exception, the settings still work in memory
    pg.evaluate("Object.defineProperty(window, 'localStorage', {get:function(){ throw new Error('blocked'); }}); make()")
    pg.evaluate("__L.setMode('vis'); __L.set('font', 14)")
    assert pg.evaluate("__L.state().storageOK") is False and pg.evaluate("__L.settings().font") == 14
    assert not errs
    ctx.close()


def test_reset_and_keyboard_cycle(pg):
    pg.keyboard.press("l"); assert pg.evaluate("__L.state().mode") == "sel"
    pg.keyboard.press("l"); assert pg.evaluate("__L.state().mode") == "vis"
    pg.keyboard.press("l"); assert pg.evaluate("__L.state().mode") == "all"
    pg.keyboard.press("l"); assert pg.evaluate("__L.state().mode") == "off"
    pg.evaluate("__L.set('font', 19); __L.reset()")
    st = pg.evaluate("__L.settings()")
    assert st["font"] == 12 and st["mode"] == "vis"
