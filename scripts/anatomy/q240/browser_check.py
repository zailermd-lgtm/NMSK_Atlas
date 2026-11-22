"""Q240: drive the view-dependent part markers and the vessel / nerve labels of a built viewer page in headless Chromium (swiftshader).

    python3 scripts/anatomy/q240/browser_check.py ROOT_DIR PAGE.html OUT_PREFIX PAGE_NAME [--json out.json] [--three /tmp/three_x/package/build/three.min.js]

Env: Q240_VIEWPORTS=name,name (default desktop,phone). Viewports: desktop 1600x900, phone 390x780 (touch).
A) part markers: default mode Visible + near with the culling engine running (depth image taken, markers hidden behind tissue / beyond the band left out, none of the shown ones
   is culled), All >= Visible + near >= Selected only, depth band monotonic (25 % <= 55 % <= all), a selected muscle whose marker is behind tissue is drawn see-through (dashed ring
   + halo) and is left out when "Show hidden ones of selected muscles" is off, hover / marking also exempt, Cut mode hides the removed side, the panel (controls, hint, phone
   layout), recompute on camera settle (throttled), depth values sane (viewer-space millimetres), 0 page errors.
B) vessel / nerve labels (callout mode): arteries + nerves labelled by default in Visible, level Main <= + secondary <= All (counts, every label's level within the chosen one),
   minimum diameter, Veins group, "Hide vessel / nerve labels", main trunks first under a tight budget, long structures anchored on the structure's own pixels (not the
   centroid), no overlapping boxes / none on the body, in the frame, off the HUD (crossing leaders are reported), legend rows carry the calibre. Screenshots OUT_PREFIX_<viewport>_*.png."""
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
kind = "own" if "atlas_viewer_male" in rel or "atlas_viewer_female" in rel else "zan"
VIEWPORTS = {"desktop": (1600, 900, False, False), "phone": (390, 780, True, True)}
want = [v for v in os.environ.get("Q240_VIEWPORTS", "desktop,phone").split(",") if v]
s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "-d", root], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
URL = f"http://127.0.0.1:{port}/{rel}"
LAYER_JS = {
    "own": "function(cat, on){ var b = document.querySelector('[data-cat=\"' + cat + '\"]'); if (b && (b.getAttribute('aria-pressed') === 'true') !== on) b.click(); }",
    "zan": "function(cat, on){ var names = {vessel:'Cardiovascular', nerve:'Nerve structures', muscle:'Muscles', skin:'Skin', bone:'Bones'}; var rows = document.querySelectorAll('#layers .layer');"
           " for (var i = 0; i < rows.length; i++){ var nm = rows[i].querySelector('.nm'); if (nm && nm.textContent.indexOf(names[cat]) === 0){ if ((rows[i].getAttribute('aria-pressed') === 'true') !== on) rows[i].click(); } } }",
}[kind]


def run_viewport(b, name, vp, mobile, touch, R):
    ok = R["checks"]; info = R["info"]
    ctx = b.new_context(viewport={"width": vp[0], "height": vp[1]}, has_touch=touch, is_mobile=mobile, device_scale_factor=1)
    pg = ctx.new_page(); pg.set_default_timeout(300000); pg.errs = []
    pg.on("pageerror", lambda e: pg.errs.append(str(e)))
    pg.on("console", lambda m: pg.errs.append("console:" + m.text) if m.type == "error" and "Failed to load resource" not in m.text else None)
    pg.route("**/fonts.g*.com/**", lambda r: r.fulfill(status=200, body="", content_type="text/css"))
    pg.route("**/three*.js", lambda r: r.fulfill(path=three, content_type="application/javascript"))
    js = pg.evaluate
    shots = []

    def shot(tag):
        f = f"{outp}_{name}_{tag}.png"
        pg.screenshot(path=f); shots.append(f)

    def close_sheets():
        js("""(function(){ var a = document.getElementById('app'); if (!a || !a.classList.contains('sheet-open')) return;
            ['m-info', 'm-list'].forEach(function(id){ var b = document.getElementById(id); if (b && b.getAttribute('aria-pressed') === 'true') b.click(); }); })()""")
        pg.wait_for_timeout(300)

    def pst():
        return js("window.__partsState()")

    def cull_now():
        js("window.__partsCtl.cullNow()"); pg.wait_for_timeout(250)
        return pst()

    def shown(st):
        return [m for m in st["markers"] if m["vis"]]

    pg.goto(URL)
    pg.wait_for_function("window.__labCtl && window.__partsState && window.__partsState().loaded", timeout=900000)
    pg.wait_for_timeout(2500)
    js("document.getElementById('btn-spin') && document.getElementById('btn-spin').classList.contains('on') && document.getElementById('btn-spin').click()")
    pg.set_default_timeout(60000)
    ok["no_hscroll"] = js("document.documentElement.scrollWidth<=window.innerWidth")

    # ------------------------------------------------------------------ A) part markers
    st = pst()
    ok["A_default_mode_near"] = st["mode"] == "near" and st["canCull"] is True and st["band"] == 55 and st["hid"] is True
    ok["A_parts_button"] = js("!!document.getElementById('t-parts')")
    js("window.__partsCtl.select(null)")
    js("window.__partsCtl.setMode('near')"); js("window.__partsCtl.setBand(55)")
    st = cull_now()
    info["A_cull"] = st["cull"]
    ok["A_depth_image_taken"] = st["cull"]["n"] >= 1 and bool(st["cull"]["img"]) and st["cull"]["far"] > st["cull"]["near"] > 0
    vis0 = shown(st)
    ok["A_near_culls_something"] = st["cull"]["cnt"]["occ"] + st["cull"]["cnt"]["far"] > 0
    ok["A_near_shown_are_visible_and_near"] = all(m["cull"] == 0 or m["forced"] for m in vis0)
    dd = [abs(m["dm"] - m["z"]) for m in st["markers"] if m["dm"] is not None and m["z"] is not None and m["cull"] == 0]
    dd.sort()
    info["A_dm_minus_z_median_mm"] = dd[len(dd) // 2] if dd else None
    ok["A_depth_values_sane"] = bool(dd) and dd[len(dd) // 2] < 60 and st["cull"]["near"] > 100        # view-space millimetres, not packed junk
    n_near = len(vis0)
    shot("A1_near_nothing_selected")
    js("window.__partsCtl.setMode('all')"); st_all = cull_now(); n_all = len(shown(st_all))
    shot("A2_all")
    js("window.__partsCtl.setMode('sel')"); st_sel = cull_now(); n_sel = len(shown(st_sel))
    ok["A_all_ge_near_ge_selected_only"] = n_all >= n_near >= n_sel and n_all > n_near
    info["A_counts"] = {"all": n_all, "near_band55": n_near, "selected_only_nothing_selected": n_sel, "placed": st["placements"]}
    js("window.__partsCtl.setMode('near')")
    counts = {}
    for band in (25, 55, 100):
        js(f"window.__partsCtl.setBand({band})"); counts[band] = len(shown(cull_now()))
        if band == 25:
            shot("A3_near_band25")
        if band == 100:
            shot("A4_near_band_all")
    info["A_band_counts"] = counts
    ok["A_band_monotonic"] = counts[25] <= counts[55] <= counts[100]
    ok["A_band_changes_the_set"] = counts[25] < counts[100]
    js("window.__partsCtl.setBand(55)"); cull_now()
    # a muscle whose marker is behind tissue: selected -> drawn see-through; box off -> culled like the rest
    st = pst()
    cand = [m for m in st["markers"] if (m["cull"] & 1) and not m["forced"]]
    info["A_occluded_markers"] = len(cand)
    ok["A_some_marker_is_hidden_behind_tissue"] = len(cand) > 0
    mesh = js("""(async function(){ var d = await (await fetch('parts_data.json')).json(); var want = %s, out = null;
        want.forEach(function(pid){ if (out) return; Object.keys(d.mesh_parts).forEach(function(k){ if (out) return; var e = d.mesh_parts[k]; var pi = d.parts.findIndex(function(p){ return p.id === pid; });
          if (e.p.indexOf(pi) >= 0 && d.placed.some(function(g){ return g.p === pi && g.car.indexOf(k) >= 0; })) out = k; }); }); return out; })()""" % json.dumps([m["part"] for m in cand[:40]]))
    info["A_selected_mesh"] = mesh
    if mesh:
        js(f"window.__labCtl.selectId({json.dumps(mesh)})"); pg.wait_for_timeout(600); close_sheets()
        st = cull_now()
        mine = [m for m in st["markers"] if m["forced"] and m["vis"]]
        ok["A_selected_markers_shown"] = len(mine) > 0
        hid = [m for m in st["markers"] if m["forced"] and m["vis"] and m["behind"]]
        info["A_selected_behind"] = len(hid)
        ok["A_selected_hidden_marker_is_see_through"] = len(hid) > 0 and js("document.querySelectorAll('#pm-layer .pm.pm-behind:not([hidden])').length") > 0
        shot("A5_selected_behind_tissue")
        js("document.getElementById('t-parts').click()"); pg.wait_for_timeout(300)
        ok["A_panel_opens"] = js("!document.getElementById('pm-panel').hidden")
        pr = js("(function(){var r=document.getElementById('pm-panel').getBoundingClientRect();return {l:r.left,t:r.top,r:r.right,b:r.bottom,w:innerWidth,h:innerHeight};})()")
        ok["A_panel_inside_viewport"] = pr["l"] >= -1 and pr["t"] >= -1 and pr["r"] <= pr["w"] + 1 and pr["b"] <= pr["h"] + 1
        ok["A_panel_controls"] = js("document.querySelectorAll('#pm-panel .pp-seg button:not([hidden])').length") == 4 and js("!!document.querySelector('#pm-panel .pp-band') && !!document.querySelector('#pm-panel .pp-hid')")
        ok["A_panel_hint_counts"] = len(js("document.querySelector('#pm-panel .pp-hint').textContent")) > 3
        shot("A6_panel")
        js("document.querySelector('#pm-panel .pp-hid').click()"); pg.wait_for_timeout(300); st = cull_now()
        ok["A_box_off_culls_selected_hidden"] = st["hid"] is False and len([m for m in st["markers"] if m["forced"] and m["vis"] and m["behind"]]) == 0
        shot("A7_hidden_of_selected_off")
        js("document.querySelector('#pm-panel .pp-hid').click()"); pg.wait_for_timeout(200)
        # panel buttons drive the mode
        js("document.querySelector('#pm-panel .pp-seg button[data-v=\"off\"]').click()"); st = cull_now()
        ok["A_off_hides_all_but_nothing_selected_forced"] = st["mode"] == "off" and len([m for m in st["markers"] if m["vis"]]) == 0
        js("document.querySelector('#pm-panel .pp-seg button[data-v=\"sel\"]').click()"); st = cull_now()
        ok["A_selected_only_shows_only_selected"] = st["mode"] == "sel" and all(m["forced"] for m in st["markers"] if m["vis"]) and len(shown(st)) > 0
        js("document.querySelector('#pm-panel .pp-seg button[data-v=\"near\"]').click()"); st = cull_now()
        js("document.getElementById('t-parts').click()"); pg.wait_for_timeout(200)
        # hover exemption
        js("window.__partsCtl.select(null)")
        js(f"window.__partsCtl.hover({json.dumps(mesh)})"); st = cull_now()
        ok["A_hover_shows_its_markers"] = len([m for m in st["markers"] if m["forced"] and m["vis"]]) > 0
        js("window.__partsCtl.hover(null)"); cull_now()
    # throttled recompute on camera settle: an orbit changes the view, a depth image follows without any call
    n0 = pst()["cull"]["n"]
    cx, cy = vp[0] // 2, vp[1] // 2 + 40
    pg.mouse.move(cx, cy); pg.mouse.down()
    for k in range(6):
        pg.mouse.move(cx + 14 * (k + 1), cy + 3 * (k % 3)); pg.wait_for_timeout(60)
    pg.mouse.up(); pg.wait_for_timeout(3500)
    n1 = pst()["cull"]["n"]
    info["A_recompute_during_orbit_and_settle"] = n1 - n0
    ok["A_recompute_on_settle_throttled"] = 1 <= n1 - n0 <= 10
    shot("A8_after_orbit")
    # CUT mode: a marker on the removed side is hidden, the kept side stays
    if not mobile:
        js("document.getElementById('t-cut').click()"); pg.wait_for_timeout(400)
        js("(function(){var s=document.getElementById('cut-pos'); if(s){ s.value=String(Math.round((+s.min + +s.max) * 0.5)); s.dispatchEvent(new Event('input',{bubbles:true})); }})()")
        pg.wait_for_timeout(800)
        st = cull_now()
        why = {}
        for m in st["markers"]:
            why[m["why"]] = why.get(m["why"], 0) + 1
        info["A_cut_reasons"] = why
        ok["A_cut_hides_removed_side"] = why.get("cut", 0) > 0 and all(m["why"] != "cut" for m in shown(st))
        shot("A9_cut")
        js("document.getElementById('t-cut').click()"); pg.wait_for_timeout(300)
    # frame cost of the culling pass
    st = pst()
    info["A_cull_ms"] = {"last": st["cull"]["ms"], "avg": st["cull"]["avgMs"], "image": st["cull"]["img"]}

    # ------------------------------------------------------------------ B) vessel / nerve labels
    close_sheets()
    js(f"({LAYER_JS})('muscle', false)"); js(f"({LAYER_JS})('vessel', true)"); js(f"({LAYER_JS})('nerve', true)")
    if kind == "zan":
        js(f"({LAYER_JS})('skin', false)")
    js("window.__partsCtl.setMode('off')")
    pg.wait_for_timeout(800)
    js("window.__labCtl.setMode('vis'); window.__labCtl.set('callout', 'out'); window.__labCtl.set('density', 60)")

    def settle(ms=1000):
        for _ in range(2):
            js("window.__labCtl.refreshNow()"); pg.wait_for_timeout(ms)
        for _ in range(40):
            if not js("window.__labCtl.state().animating"):
                break
            pg.wait_for_timeout(300)
        return js("({s: window.__labCtl.state(), c: window.__labCtl.selfCheck()})")

    c = settle()
    S0 = c["s"]
    ok["B_calibre_table_loaded"] = S0["haveCal"] is True and S0["calCount"] > 20
    ok["B_defaults"] = S0["vn"] == {"hide": False, "a": True, "v": False, "n": True, "lva": 2, "lvn": 2, "da": 0, "dn": 0}
    info["B_vn_visible_default"] = {"vnVisible": S0["vnVisible"], "vnShown": len(S0["vnShown"]), "labelled": len(S0["shown"])}
    ok["B_vessels_and_nerves_labelled_by_default"] = len(S0["vnShown"]) > 0
    res = {}
    js("window.__labCtl.set('density', 120)")          # the budget: levels add labels only while Max labels has room (main trunks first)
    for lv, tag in ((1, "main"), (2, "secondary"), (4, "all")):
        js(f"window.__labCtl.set('lva', {lv}); window.__labCtl.set('lvn', {lv})")
        if lv == 4:
            js("window.__labCtl.set('gv', true)")
        c = settle()
        ids = c["s"]["vnShown"]
        cal = js("(function(ids){ return ids.map(function(i){ return window.__labCtl.calibre(i); }); })(%s)" % json.dumps(ids))
        selected = js("window.__labCtl.anchors().filter(function(a){ var c = window.__labCtl.calibre(a.id); return c && c.kind; }).length")
        res[tag] = {"n_selected": selected, "n": len(ids), "levels": sorted({x["level"] for x in cal}), "kinds": sorted({x["kind"] for x in cal}), "self": c["c"], "labelled": len(c["s"]["shown"])}
        ok[f"B_level_{tag}_respected"] = all(x["level"] <= lv for x in cal)
        ok[f"B_level_{tag}_no_overlap_off_body_in_frame"] = c["c"]["overlaps"] == 0 and c["c"]["bodyHits"] == 0 and c["c"]["outsideFrame"] == 0 and c["c"]["obstacleHits"] == 0
        # crossing leaders are reported, not asserted: with ~60 callouts on a whole-body view the Q236 solver leaves some (PROJECT_STATE Q236 limits); sparse views are asserted in tests/test_q240_labels_vn.py
        shot(f"B_{tag}")
        if lv == 4:
            ok["B_veins_group_adds_veins"] = "v" in res[tag]["kinds"]
            js("window.__labCtl.set('gv', false)")
    info["B_levels"] = res
    ok["B_levels_monotonic"] = res["main"]["n_selected"] <= res["secondary"]["n_selected"] <= res["all"]["n_selected"] and res["main"]["n_selected"] < res["all"]["n_selected"]      # what is selected for a label (a callout may still be dropped for lack of room on a phone)
    # minimum diameter on top of the level
    js("window.__labCtl.set('lva', 4); window.__labCtl.set('lvn', 4); window.__labCtl.set('gv', false)")
    base = len(settle()["s"]["vnShown"])
    js("window.__labCtl.set('da', 5); window.__labCtl.set('dn', 3)")
    c = settle(); lim = c["s"]["vnShown"]
    cal = js("(function(ids){ return ids.map(function(i){ return window.__labCtl.calibre(i); }); })(%s)" % json.dumps(lim))
    ok["B_min_diameter_cuts"] = len(lim) < base and all((x["diameter"] is None) or (x["diameter"] >= (3 if x["kind"] == "n" else 5)) for x in cal)
    info["B_min_diameter"] = {"all_levels": base, "da5_dn3": len(lim)}
    js("window.__labCtl.set('da', 0); window.__labCtl.set('dn', 0); window.__labCtl.set('lva', 2); window.__labCtl.set('lvn', 2)")
    # main trunks first under a tight budget
    js("window.__labCtl.set('density', 6)")
    c = settle(); few = c["s"]["vnShown"]
    cal = js("(function(ids){ return ids.map(function(i){ return window.__labCtl.calibre(i); }); })(%s)" % json.dumps(few))
    ok["B_main_trunks_first_under_budget"] = len(few) > 0 and sum(1 for x in cal if x["level"] == 1) >= max(1, len(cal) // 2)
    info["B_budget6"] = {"vn": len(few), "levels": [x["level"] for x in cal]}
    js("window.__labCtl.set('density', 60)")
    # long structures anchored on their own pixels
    c = settle()
    anc = js("window.__labCtl.anchors().filter(function(a){ return a.long > 0; }).length")
    info["B_long_anchors"] = anc
    ok["B_long_structures_use_run_anchor"] = anc > 0
    # hide switch
    js("window.__labCtl.set('vhide', true)")
    c = settle()
    ok["B_hide_switch_removes_all"] = len(c["s"]["vnShown"]) == 0
    shot("B_hidden")
    js("window.__labCtl.set('vhide', false)")
    # the panel carries the controls and the help
    js("document.getElementById('t-labels').click()") if not js("!document.getElementById('lab-panel').hidden") else None
    pg.wait_for_timeout(300)
    ok["B_panel_controls"] = js("['lab-vhide','lab-g-a','lab-g-v','lab-g-n','lab-lva','lab-lvn','lab-da','lab-dn'].every(function(i){ return !!document.getElementById(i); })") and \
        js("document.querySelector('#lab-panel .lb-help').textContent.indexOf('6 mm') > 0")
    shot("B_panel")
    # legend rows carry the calibre
    js("window.__labCtl.openLegend(true)"); pg.wait_for_timeout(500)
    js("document.getElementById('lg-q').value = 'artery'; document.getElementById('lg-q').dispatchEvent(new Event('input', {bubbles: true}))"); pg.wait_for_timeout(300)
    ok["B_legend_rows_carry_calibre"] = js("document.querySelectorAll('#lg-list .lg-d').length") > 0 or js("document.querySelectorAll('#lg-list .lg-row').length") == 0
    js("window.__labCtl.openLegend(false)")
    ok["B_no_page_errors"] = True
    R["errors"] = list(pg.errs)
    ok["no_page_errors"] = not pg.errs
    R["shots"] = shots
    ctx.close()


results = {"page": page_name, "kind": kind, "viewports": {}}
with sync_playwright() as p:
    for name in want:
        vp = VIEWPORTS[name]
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])      # one browser per viewport (a second page of 3 M triangles in the same software-GL process can run it out of memory)
        R = {"checks": {}, "info": {}, "errors": [], "shots": []}
        try:
            run_viewport(b, name, vp[:2], vp[2], vp[3], R)
        except Exception as e:      # keep what was collected
            R["errors"].append("EXC " + repr(e)[:600]); R["checks"]["completed"] = False
        results["viewports"][name] = R
        bad = [k for k, v in R["checks"].items() if v is not True]
        print(page_name, name, "FAIL " + ",".join(bad) if bad or R["errors"] else "ok", R["errors"][:3], flush=True)
        try:
            b.close()
        except Exception:
            pass
srv.terminate()
if json_out:
    json.dump(results, open(json_out, "w"), indent=1)
