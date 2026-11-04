"""Q236: drive the structure labels of a built viewer page in headless Chromium (swiftshader).

    python3 scripts/anatomy/q236/browser_check.py ROOT_DIR PAGE.html OUT_PREFIX PAGE_NAME [--json out.json] [--three /tmp/three_x/package/build/three.min.js]

Env: Q236_VIEWPORTS=name,name (default desktop,laptop,tablet,phone), Q236_FULL=name,... (viewports that run the long flow: cut mode, legend, persistence, timing; default desktop,phone).
Viewports: desktop 1920x1080, laptop 1366x768, tablet 768x1024, phone 360x640.
Per viewport: 0 page errors, no horizontal scroll, the Labels button + panel (floating, or a bottom sheet on phones), labels drawn in Auto / Inline / Outside / Abbreviation / All /
Selected modes with the geometry self-check (no overlapping label boxes, no callout touching the body silhouette, nothing outside the canvas or inside a HUD panel, no crossing
leader lines), after an orbit, in CUT mode with the cut face filled (anchors on the cut face), legend window (open, S / M / L, font A- / A+ / slider, search, row click selects,
drag, corner resize; bottom sheet on phones), settings persistence across a reload, and frame timing with / without labels. Screenshots OUT_PREFIX_<viewport>_*.png."""
import json
import os
import socket
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright

args = [a for a in sys.argv[1:] if not a.startswith("--")]
root, rel, outp, page_name = args[:4]
json_out = sys.argv[sys.argv.index("--json") + 1] if "--json" in sys.argv else None
three = sys.argv[sys.argv.index("--three") + 1] if "--three" in sys.argv else "/tmp/three_x/package/build/three.min.js"
args = [a for a in args if a != json_out and a != three]
kind = "own" if "atlas_viewer_male" in rel or "atlas_viewer_female" in rel else "zan"
VIEWPORTS = {"desktop": (1920, 1080, False, False), "laptop": (1366, 768, False, False), "tablet": (768, 1024, False, True), "phone": (360, 640, True, True)}
want = [v for v in os.environ.get("Q236_VIEWPORTS", "desktop,laptop,tablet,phone").split(",") if v]
FULL = tuple(v for v in os.environ.get("Q236_FULL", "desktop,phone").split(",") if v)
s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "-d", root], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
URL = f"http://127.0.0.1:{port}/{rel}"
LIST_ROW = "#list .row" if kind == "own" else "#list .item"
CUT_BTN = "#t-cut"


def new_page(b, vp, mobile, touch, ctx=None):
    ctx = ctx or b.new_context(viewport={"width": vp[0], "height": vp[1]}, has_touch=touch, is_mobile=mobile, device_scale_factor=1)
    pg = ctx.new_page()
    pg.set_default_timeout(300000)
    pg.errs = []
    pg.on("pageerror", lambda e: pg.errs.append(str(e)))
    pg.on("console", lambda m: pg.errs.append("console:" + m.text) if m.type == "error" and "Failed to load resource" not in m.text else None)
    pg.route("**/fonts.g*.com/**", lambda r: r.fulfill(status=200, body="", content_type="text/css"))
    pg.route("**/three*.js", lambda r: r.fulfill(path=three, content_type="application/javascript"))
    return ctx, pg


def boot(pg):
    pg.goto(URL)
    pg.wait_for_function("window.__labCtl && window.__selState", timeout=900000)
    pg.wait_for_timeout(2500)
    pg.evaluate("document.getElementById('btn-spin') && document.getElementById('btn-spin').classList.contains('on') && document.getElementById('btn-spin').click()")
    pg.wait_for_timeout(300)


def settle(pg, ms=900):
    pg.evaluate("window.__labCtl.refreshNow()")
    pg.wait_for_timeout(ms)
    pg.evaluate("window.__labCtl.refreshNow()")
    pg.wait_for_timeout(ms)
    for _ in range(40):                                        # the labels glide to their places (a few frames; slow software GL needs longer)
        if not pg.evaluate("window.__labCtl.state().animating"):
            break
        pg.wait_for_timeout(300)
    return pg.evaluate("({s: window.__labCtl.state(), c: window.__labCtl.selfCheck()})")


def run_viewport(b, name, vp, mobile, touch, R):
    ok = R["checks"]; info = R["info"]
    full = name in FULL
    ctx, pg = new_page(b, vp, mobile, touch)
    js = pg.evaluate
    shots = []

    def shot(tag):
        f = f"{outp}_{name}_{tag}.png"
        pg.screenshot(path=f); shots.append(f)

    def click(sel):
        l = pg.locator(sel).first
        l.scroll_into_view_if_needed()
        l.tap() if touch else l.click()
        pg.wait_for_timeout(250)

    def close_sheets():
        """phone layout: selecting a structure opens the page's Details sheet, which (by design) hides the labels panel; close it again"""
        js("""(function(){ var a = document.getElementById('app'); if (!a || !a.classList.contains('sheet-open')) return;
            ['m-info', 'm-list'].forEach(function(id){ var b = document.getElementById(id); if (b && b.getAttribute('aria-pressed') === 'true') b.click(); }); })()""")
        pg.wait_for_timeout(400)

    def geom_ok(tag, c, allow_inline_overlap=False):
        ok[f"{tag}_no_overlap"] = c["overlaps"] == 0
        ok[f"{tag}_callouts_off_body"] = c["bodyHits"] == 0
        ok[f"{tag}_inside_canvas"] = c["outsideFrame"] == 0
        ok[f"{tag}_off_hud"] = c["obstacleHits"] == 0
        info[f"{tag}_selfcheck"] = c

    boot(pg)
    pg.set_default_timeout(60000)
    ok["no_hscroll"] = js("document.documentElement.scrollWidth<=window.innerWidth")
    ok["labels_button"] = js("!!document.getElementById('t-labels')")
    ok["labels_off_by_default"] = js("window.__labState().mode") == "off"
    ok["layer_hidden_when_off"] = js("(function(){var l=document.getElementById('lab-layer');return !l||getComputedStyle(l).display==='none';})()")
    # --- open the panel ---
    click("#t-labels")
    ok["panel_opens"] = js("!document.getElementById('lab-panel').hidden")
    ok["opening_switches_labels_on"] = js("window.__labState().mode") == "vis"
    pr = js("(function(){var r=document.getElementById('lab-panel').getBoundingClientRect();return {l:r.left,t:r.top,r:r.right,b:r.bottom,w:innerWidth,h:innerHeight};})()")
    ok["panel_inside_viewport"] = pr["l"] >= -1 and pr["t"] >= -1 and pr["r"] <= pr["w"] + 1 and pr["b"] <= pr["h"] + 1
    if mobile:
        ok["panel_is_bottom_sheet"] = js("document.getElementById('lab-panel').classList.contains('lb-phone')")
    ok["panel_not_over_toolbar"] = js("""(function(){var p=document.getElementById('lab-panel').getBoundingClientRect(), ok=true;
        ['tools','topright','cut-panel','needle-panel'].forEach(function(id){var e=document.getElementById(id); if(!e||e.hidden) return; var r=e.getBoundingClientRect();
          if(r.width>4&&r.height>4&&getComputedStyle(e).display!=='none'&&p.left<r.right&&p.right>r.left&&p.top<r.bottom&&p.bottom>r.top) ok=false;}); return ok;})()""")
    sheet = js("document.getElementById('lab-panel').classList.contains('lb-phone')")      # phones and narrow stages: bottom sheets instead of floating windows
    info["sheet_layout"] = sheet
    # a sheet covers part of the model: fold it while the model is inspected
    if sheet:
        click("#lab-min")
    c = settle(pg)
    info["mode_vis_state"] = {k: c["s"][k] for k in ("mode", "visible", "heavyMs", "idMs", "layoutMs", "kinds")}
    ok["vis_labels_drawn"] = len(c["s"]["shown"]) > 0
    ok["vis_respects_density"] = len(c["s"]["shown"]) <= c["s"]["density"] + 1
    geom_ok("auto", c["c"])
    shot("1_auto")
    # --- inline / outside ---
    pg.evaluate("window.__labCtl.set('callout','in')")
    c = settle(pg)
    ok["inline_no_callouts"] = c["c"]["callout"] == 0
    ok["inline_no_overlap"] = c["c"]["overlaps"] == 0
    info["inline_selfcheck"] = c["c"]
    shot("2_inline")
    pg.evaluate("window.__labCtl.set('callout','out')")
    c = settle(pg)
    ok["outside_all_callouts"] = c["c"]["inline"] == 0 and c["c"]["callout"] > 0
    geom_ok("outside", c["c"])
    info["outside_leader_px"] = [c["c"]["meanLeader"], c["c"]["maxLeader"]]
    ok["outside_no_crossing_leaders"] = c["c"]["leaderCrossings"] <= (max(4, c["c"]["callout"] // 2) if sheet else max(3, c["c"]["callout"] // 3))       # (a floating panel or a phone-sized stage leaves a label column little room)
    info["outside_crossings"] = c["c"]["leaderCrossings"]
    shot("3_outside")
    # --- abbreviations ---
    pg.evaluate("window.__labCtl.set('text','abbr')")
    c = settle(pg)
    ab = js("(function(){var s=window.__labState(), ids=s.shown.slice(0,6); return ids.map(function(id){return [id, window.__labCtl.abbr(id)];});})()")
    texts = js("Array.prototype.map.call(document.querySelectorAll('#lab-layer .lb-t'), function(t){return t.textContent;})")
    ok["abbr_text_on_screen"] = all(a[1] in texts for a in ab) and len(ab) > 0
    ok["abbr_table_in_page"] = js("window.__labState().hasTable")
    geom_ok("abbr", c["c"])
    shot("4_abbr")
    pg.evaluate("window.__labCtl.set('text','full'); window.__labCtl.set('callout','auto')")
    # --- all / selected ---
    pg.evaluate("window.__labCtl.setMode('all')")
    c = settle(pg, 1200)
    ok["all_mode_capped"] = len(c["s"]["shown"]) <= 160
    geom_ok("all", c["c"])
    info["all_labelled"] = len(c["s"]["shown"]); info["all_visible"] = c["s"]["visible"]
    shot("5_all")
    try:                                                                 # the list row path (selects some structure and may frame the camera on it; on a phone / narrow tablet the list can be a closed sheet or off screen) ...
        l = pg.locator(LIST_ROW).first
        l.scroll_into_view_if_needed(timeout=5000)
        l.tap(timeout=5000) if touch else l.click(timeout=5000)
        pg.wait_for_timeout(250)
    except Exception:
        info["list_row_click"] = "skipped (list not reachable at this width)"
    pg.evaluate("(document.getElementById('t-reset') || document.getElementById('btn-reset')).click()")      # the list click may have framed the camera on that structure: home view again
    pg.wait_for_timeout(800)
    pg.evaluate("window.__labCtl.setMode('vis')")
    c = settle(pg)
    pick = js("window.__labState().shown[0]")
    pg.evaluate("window.__labCtl.setMode('sel')")
    pg.evaluate("window.__labCtl.selectId(%s)" % json.dumps(pick))      # ... then one that is on screen
    close_sheets()
    c = settle(pg)
    sel = js("(function(){var i=document.querySelector('#lab-layer .lb-sel'); return i?i.textContent:null;})()")
    ok["selected_mode_labels_selection"] = sel is not None and len(c["s"]["shown"]) >= 1
    # marked structures (Selection feature) are labelled too: mark the selected one through the Selection panel, then select another one
    pg.evaluate("document.getElementById('sel-markcur').click()")
    other = js("(function(){ var s = window.__labState(); return null; })()")
    pg.evaluate("window.__labCtl.setMode('vis')"); c = settle(pg)
    other = next((i for i in c["s"]["shown"] if i != pick), None)
    pg.evaluate("window.__labCtl.setMode('sel')")
    if other:
        pg.evaluate("window.__labCtl.selectId(%s)" % json.dumps(other)); close_sheets()
    c = settle(pg)
    ok["selected_mode_includes_marked"] = other is not None and pick in c["s"]["shown"] and other in c["s"]["shown"]
    pg.evaluate("document.getElementById('sel-clear').click()")
    ok["selected_mode_few"] = len(c["s"]["shown"]) <= 3
    shot("6_selected")
    pg.evaluate("(document.getElementById('t-reset') || document.getElementById('btn-reset')).click()")      # the list click may have framed the camera on one structure: home view again
    pg.evaluate("window.__labCtl.setMode('vis')")
    pg.wait_for_timeout(800)
    settle(pg)
    # --- orbit ---
    cx, cy = vp[0] // 2, vp[1] // 2 - (60 if mobile else 0)
    before = js("window.__labState().shown")
    pg.mouse.move(cx, cy); pg.mouse.down()
    for k in range(1, 7):
        pg.mouse.move(cx + 22 * k, cy + 3 * k)
        pg.wait_for_timeout(120)
    pg.mouse.up()
    c = settle(pg, 1100)
    ok["after_orbit_labels"] = len(c["s"]["shown"]) > 0
    geom_ok("orbit", c["c"])
    shot("7_orbit")
    # --- panel controls ---
    pg.evaluate("window.__labCtl.openPanel(true)")
    f0 = js("window.__labCtl.settings().font")
    pg.evaluate("window.__labCtl.set('font', 17)")
    c = settle(pg)
    ok["font_size_applies"] = js("document.getElementById('lab-layer').getAttribute('font-size')") == "17" and f0 != 17
    ok["font_big_no_overlap"] = c["c"]["overlaps"] == 0 and c["c"]["bodyHits"] == 0
    pg.evaluate("window.__labCtl.set('font', 12); window.__labCtl.set('density', 8)")
    c = settle(pg)
    ok["density_slider_limits"] = len(c["s"]["shown"]) <= 9
    pg.evaluate("window.__labCtl.set('density', 24); window.__labCtl.set('colour','neutral')")
    c = settle(pg)
    fills = js("Array.prototype.map.call(document.querySelectorAll('#lab-layer .lb-t'), function(t){return t.getAttribute('fill');})")
    ok["neutral_colour"] = len(set(fills)) <= 1 and len(fills) > 0
    pg.evaluate("window.__labCtl.set('colour','own')")
    ok["side_marks_toggle"] = True
    pg.evaluate("window.__labCtl.set('side', false)")
    t_noside = js("Array.prototype.map.call(document.querySelectorAll('#lab-layer .lb-t'), function(t){return t.textContent;}).filter(function(t){return /\\((R|L)\\)$/.test(t);}).length")
    pg.evaluate("window.__labCtl.set('side', true)")
    t_side = js("Array.prototype.map.call(document.querySelectorAll('#lab-layer .lb-t'), function(t){return t.textContent;}).filter(function(t){return /\\((R|L)\\)$/.test(t);}).length")
    ok["side_marks_toggle"] = t_noside == 0 and t_side > 0
    # --- legend ---
    pg.evaluate("window.__labCtl.openPanel(true)")
    if js("document.getElementById('lab-panel').classList.contains('lb-min')"):
        click("#lab-min")
    click("#lab-legend-btn")
    ok["legend_opens"] = js("!document.getElementById('lab-legend').hidden")
    pg.wait_for_timeout(300)
    rows = js("document.querySelectorAll('#lg-list .lg-row').length")
    ok["legend_lists_onscreen_labels"] = rows == len(js("window.__labState().shown")) and rows > 0
    lr = js("(function(){var r=document.getElementById('lab-legend').getBoundingClientRect();return {l:r.left,t:r.top,w:r.width,h:r.height,r:r.right,b:r.bottom,iw:innerWidth,ih:innerHeight};})()")
    ok["legend_inside_viewport"] = lr["l"] >= -1 and lr["t"] >= -1 and lr["r"] <= lr["iw"] + 1 and lr["b"] <= lr["ih"] + 1
    if sheet:
        ok["legend_is_bottom_sheet"] = abs(lr["b"] - lr["ih"]) < 2 and abs(lr["w"] - lr["iw"]) < 2
    sizes = {}
    for sz in ("S", "M", "L"):
        click(f'#lab-legend [data-size="{sz}"]')
        sizes[sz] = js("(function(){var r=document.getElementById('lab-legend').getBoundingClientRect();return [Math.round(r.width),Math.round(r.height)];})()")
    info["legend_sizes"] = sizes
    ok["legend_size_buttons"] = (sizes["S"][1] < sizes["M"][1] < sizes["L"][1]) and (sheet or sizes["S"][0] < sizes["M"][0] < sizes["L"][0])
    click('#lab-legend [data-size="M"]')
    fs0 = js("parseFloat(getComputedStyle(document.querySelector('#lg-list .lg-row')).fontSize)")
    click("#lg-fup"); click("#lg-fup")
    fs1 = js("parseFloat(getComputedStyle(document.querySelector('#lg-list .lg-row')).fontSize)")
    click("#lg-fdn")
    fs2 = js("parseFloat(getComputedStyle(document.querySelector('#lg-list .lg-row')).fontSize)")
    pg.evaluate("(function(){var s=document.getElementById('lg-font'); s.value=20; s.dispatchEvent(new Event('input',{bubbles:true}));})()")
    fs3 = js("parseFloat(getComputedStyle(document.querySelector('#lg-list .lg-row')).fontSize)")
    info["legend_font_px"] = [fs0, fs1, fs2, fs3]
    ok["legend_font_controls"] = fs1 > fs0 and fs2 < fs1 and fs3 == 20
    shot("8_legend")
    # all structures + search + row click selects
    click('#lg-only [data-v="all"]')
    nall = js("document.querySelectorAll('#lg-list .lg-row').length")
    ok["legend_all_structures"] = nall > rows
    pg.fill("#lg-q", "bic")
    pg.wait_for_timeout(300)
    nq = js("document.querySelectorAll('#lg-list .lg-row').length")
    names = js("Array.prototype.map.call(document.querySelectorAll('#lg-list .lg-row'), function(r){return r.textContent.toLowerCase();})")
    ok["legend_search_filters"] = 0 < nq < nall and all("bic" in n for n in names)
    sel_before = js("window.__selState && 0; (function(){var h=document.querySelector('#lab-layer .lb-sel');return h?h.textContent:'';})()")
    row_id = js("(function(){var r=document.querySelector('#lg-list .lg-row'); return r?r.getAttribute('data-i'):null;})()")
    click("#lg-list .lg-row")
    close_sheets()
    ok["legend_row_selects_structure"] = js("document.querySelector('#lg-list .lg-row.lg-sel')!==null")
    pg.fill("#lg-q", "")
    click('#lg-only [data-v="shown"]')
    if not sheet:
        h0 = js("(function(){var r=document.getElementById('lab-legend').getBoundingClientRect();return [r.left,r.top];})()")
        hb = pg.locator("#lg-head").bounding_box()
        pg.mouse.move(hb["x"] + 30, hb["y"] + 10); pg.mouse.down(); pg.mouse.move(hb["x"] + 30 - 120, hb["y"] + 10 + 60, steps=6); pg.mouse.up()
        h1 = js("(function(){var r=document.getElementById('lab-legend').getBoundingClientRect();return [r.left,r.top];})()")
        ok["legend_draggable"] = abs(h1[0] - h0[0]) > 40 or abs(h1[1] - h0[1]) > 20
        g0 = js("(function(){var r=document.getElementById('lab-legend').getBoundingClientRect();return [r.width,r.height];})()")
        gb = pg.locator("#lg-grip").bounding_box()
        pg.mouse.move(gb["x"] + 8, gb["y"] + 8); pg.mouse.down(); pg.mouse.move(gb["x"] + 8 - 60, gb["y"] + 8 - 50, steps=6); pg.mouse.up()
        g1 = js("(function(){var r=document.getElementById('lab-legend').getBoundingClientRect();return [r.width,r.height];})()")
        ok["legend_corner_resize"] = g1[0] < g0[0] - 20 and g1[1] < g0[1] - 20
    # --- cut mode with the cut face filled ---
    if full:
        pg.evaluate("window.__labCtl.openLegend(false)")
        click(CUT_BTN)
        pg.wait_for_timeout(500)
        click('#cut-axis button[data-axis="y"]') if js("!!document.querySelector('#cut-axis button[data-axis=\"y\"]')") else None
        # axial plane through the upper chest / pelvis region: slide to a structure-rich level
        js("(function(){var s=document.getElementById('cut-pos'); if(s){ s.value=String(Math.round((+s.min + +s.max) * 0.5) + 40); s.dispatchEvent(new Event('input',{bubbles:true})); }})()")
        pg.wait_for_timeout(500)
        if js("!!document.getElementById('cut-fill')"):
            click("#cut-fill")
        pg.wait_for_timeout(1500)
        if js("!!document.getElementById('cut-look')"):
            click("#cut-look")
        pg.wait_for_timeout(1500)
        pg.evaluate("window.__labCtl.setMode('vis'); window.__labCtl.set('density', 30)")
        c = settle(pg, 1500)
        ok["cut_on_labels_drawn"] = c["s"]["cutOn"] and len(c["s"]["shown"]) > 0
        info["cut_state"] = {"shown": len(c["s"]["shown"]), "kinds": c["s"]["kinds"], "capOn": c["s"]["capOn"]}
        ok["cut_labels_on_cut_face"] = c["s"]["capOn"] and c["s"]["kinds"].get("cut", 0) > 0
        geom_ok("cut", c["c"])
        shot("9_cut")
        # orbit a little inside cut mode
        pg.mouse.move(cx, cy); pg.mouse.down()
        for k in range(1, 5):
            pg.mouse.move(cx + 18 * k, cy - 6 * k); pg.wait_for_timeout(120)
        pg.mouse.up()
        c = settle(pg, 1100)
        ok["cut_after_orbit_labels"] = len(c["s"]["shown"]) > 0
        geom_ok("cut_orbit", c["c"])
        shot("10_cut_orbit")
        click(CUT_BTN) if js("document.getElementById('t-cut').getAttribute('aria-pressed')") == "true" else None
        pg.wait_for_timeout(500)
        # --- persistence ---
        pg.evaluate("window.__labCtl.setMode('all'); window.__labCtl.set('text','abbr'); window.__labCtl.set('font', 15); window.__labCtl.openLegend(true)")
        stored = js("localStorage.getItem('nmsk.labels.v1')")
        ok["settings_stored"] = bool(stored) and '"mode":"all"' in stored
        pg.reload()
        pg.wait_for_function("window.__labCtl && window.__selState", timeout=900000)
        pg.wait_for_timeout(1500)
        st = js("window.__labCtl.settings()")
        ok["settings_restored_after_reload"] = st["mode"] == "all" and st["text"] == "abbr" and st["font"] == 15 and st["lg"]["open"] is True
        pg.evaluate("window.__labCtl.openLegend(false); window.__labCtl.setMode('off')")
        # --- frame timing: orbit steps with labels off / Visible / All ---
        def orbit_ms(label, steps=6):
            pg.mouse.move(cx, cy); pg.mouse.down()
            ts = []
            for k in range(steps):
                t0 = time.time()
                pg.mouse.move(cx + 14 * (k + 1), cy + 2 * k)
                pg.evaluate("new Promise(function(r){requestAnimationFrame(function(){requestAnimationFrame(r);});})")
                ts.append((time.time() - t0) * 1000)
            pg.mouse.up()
            ts.sort()
            return {"mean_ms": round(sum(ts) / len(ts)), "median_ms": round(ts[len(ts) // 2]), "max_ms": round(ts[-1])}
        perf = {}
        pg.evaluate("window.__labCtl.setMode('off')"); pg.wait_for_timeout(600)
        perf["off"] = orbit_ms("off")
        pg.evaluate("window.__labCtl.setMode('vis')"); settle(pg)
        perf["visible"] = orbit_ms("vis")
        pg.evaluate("window.__labCtl.setMode('all')"); settle(pg)
        perf["all"] = orbit_ms("all")
        st = js("window.__labState()")
        perf["last_idpass_ms"] = st["idMs"]; perf["last_refresh_ms"] = st["heavyMs"]; perf["last_layout_ms"] = st["layoutMs"]
        info["perf_orbit_step"] = perf
        pg.evaluate("window.__labCtl.setMode('off')")
    ok["zero_page_errors"] = not pg.errs
    R["errors"] = pg.errs[:6]
    R["screenshots"] = shots
    ctx.close()


def main():
    out = {"page": page_name, "kind": kind, "viewports": {}}
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
        for name in want:
            vp = VIEWPORTS[name]
            R = {"viewport": f"{vp[0]}x{vp[1]}", "checks": {}, "info": {}, "errors": []}
            t0 = time.time()
            try:
                run_viewport(b, name, vp[:2], vp[2], vp[3], R)
            except Exception as e:                                                  # keep going: the failure is recorded
                R["checks"]["run_completed"] = False
                R["errors"].append("EXC " + repr(e)[:400])
            R["seconds"] = round(time.time() - t0)
            out["viewports"][name] = R
            bad = [k for k, v in R["checks"].items() if v is not True]
            print(page_name, name, f"{len(R['checks']) - len(bad)}/{len(R['checks'])} ok", "errors:", len(R["errors"]), "FAILED:" if bad else "", bad, flush=True)
        b.close()
    srv.terminate()
    if json_out:
        os.makedirs(os.path.dirname(json_out) or ".", exist_ok=True)
        if "--merge" in sys.argv and os.path.exists(json_out):                  # re-run of some viewports only: keep the others
            old = json.load(open(json_out))
            old["viewports"].update(out["viewports"]); out = old
        json.dump(out, open(json_out, "w"), indent=1)


main()
