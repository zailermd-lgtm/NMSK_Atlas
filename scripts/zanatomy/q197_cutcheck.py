"""Q197: drive the shared Cut mode of a built viewer page in headless Chromium (swiftshader), desktop + phone.

    python3 scripts/zanatomy/q197_cutcheck.py ROOT_DIR PAGE.html own|zan OUT_PREFIX THREE_MIN_JS

Per viewport: cut on, place on model (click/tap), the plane passes through the clicked point (the overlay ring sits on the
click), flip / choose side, step buttons, arrow keys, PageUp, wheel over the slider (desktop), presets, selection with the cut
on, add-on hook (api.cut/setCut and, if clinical_needle_tool.js is staged next to the page, its 'Cut through target'),
x-ray / source facet with the cut on, reset, exit. Prints JSON; screenshots OUT_PREFIX_<viewport>_<step>.png."""
import io
import json
import socket
import subprocess
import sys
import time

import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright

root, rel, kind, outp, three = sys.argv[1:6]
OWN_HOOK = ("var cutCtl = null;", "var cutCtl = null; window.__T = {ctl:function(){return cutCtl;}, meshes:meshes, api:function(){return anatomyApi();}};")
ZAN_HOOK = ("searchEl.oninput=renderList; renderList();",
            "searchEl.oninput=renderList; renderList(); window.__T = {OBJ:OBJ, cam:cam, ctl:function(){return cutCtl;}, api:function(){return anatomyApi();}, need:function(){need=true;}};")
HOOK = OWN_HOOK if kind == "own" else ZAN_HOOK
s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "-d", root], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)


def patch(route):
    r = route.fetch(); b = r.text()
    route.fulfill(response=r, body=b.replace(HOOK[0], HOOK[1], 1) if HOOK[0] in b else b)


def img(pg, sel="canvas"):
    pg.add_style_tag(content="#cut-svg,#cut-panel{visibility:hidden!important}")
    b = pg.locator(sel).first.screenshot()
    pg.evaluate("document.querySelectorAll('style').forEach(function(s){ if(s.textContent.indexOf('#cut-svg,#cut-panel{visibility:hidden!important}')===0) s.remove(); })")
    return np.asarray(Image.open(io.BytesIO(b)).convert("RGB")).astype(int)


def changed(a, b):
    if a.shape != b.shape: return 1.0
    return float((np.abs(a - b).sum(axis=2) > 24).mean())


def st(pg): return pg.evaluate("__T.ctl().state()")


res = {}
try:
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
        for name, vp, mobile in (("desktop", {"width": 1400, "height": 900}, False), ("phone", {"width": 390, "height": 844}, True)):
            ctx = b.new_context(viewport=vp, has_touch=mobile, is_mobile=mobile, device_scale_factor=1)
            pg = ctx.new_page()
            errs, notes = [], []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" else None)
            pg.on("response", lambda r: notes.append(f"{r.status} {r.url.rsplit('/', 1)[-1]}") if r.status >= 400 else None)
            pg.route("**/*.html", patch)
            pg.route("**/fonts.g*.com/**", lambda r: r.fulfill(status=200, body="", content_type="text/css"))
            pg.route("**/three*.js", lambda r: r.fulfill(path=three, content_type="application/javascript"))
            pg.goto(f"http://127.0.0.1:{port}/{rel}")
            pg.wait_for_function("window.__T && document.getElementById('t-cut')", timeout=900000)
            pg.wait_for_function("(__T.OBJ ? __T.OBJ.length : __T.meshes.length) > 0", timeout=900000)
            pg.wait_for_timeout(2500)
            R = {"checks": {}}
            ok = R["checks"]
            tap = (lambda sel: pg.locator(sel).tap()) if mobile else (lambda sel: pg.locator(sel).click())
            if kind == "zan":                                            # stop the auto-spin so the view is stable
                pg.evaluate("document.getElementById('btn-spin').classList.contains('on') && document.getElementById('btn-spin').click()")
            pg.wait_for_timeout(500)
            base = img(pg)
            pg.screenshot(path=f"{outp}_{name}_0_before.png")
            ok["button_visible"] = pg.locator("#t-cut").is_visible()
            tap("#t-cut"); pg.wait_for_timeout(400)
            s0 = st(pg)
            ok["panel_visible"] = pg.locator("#cut-panel").is_visible() and s0["on"]
            box = pg.locator("#cut-panel").bounding_box()
            ok["panel_in_viewport"] = bool(box and box["x"] >= -0.5 and box["y"] >= -0.5 and box["x"] + box["width"] <= vp["width"] + 0.5 and box["y"] + box["height"] <= vp["height"] + 0.5)
            ok["no_hscroll"] = pg.evaluate("document.documentElement.scrollWidth<=window.innerWidth")
            ok["min_button_height"] = pg.evaluate("Math.min.apply(null,Array.from(document.querySelectorAll('#cut-panel button')).filter(function(b){return b.offsetParent}).map(function(b){return b.getBoundingClientRect().height}))")
            ok["default_removes_+axis_side"] = (s0["ori"] == "x" and s0["rs"] == 1)
            pg.screenshot(path=f"{outp}_{name}_1_cut_on_sagittal.png")
            ok["cut_changes_picture"] = changed(base, img(pg))
            # --- place on model
            cb = pg.locator("canvas").first.bounding_box()
            top = cb["y"]; bottom = min(cb["y"] + cb["height"], box["y"] if mobile else 1e9)
            cx = cb["x"] + cb["width"] / 2 if not mobile else vp["width"] / 2
            cy = (top + bottom) / 2 if mobile else cb["y"] + cb["height"] * 0.45
            tap("#cut-place")
            ok["armed"] = st(pg)["armed"] and pg.evaluate("document.body.classList.contains('cut-armed')")
            if mobile: pg.touchscreen.tap(cx, cy)
            else: pg.mouse.click(cx, cy)
            pg.wait_for_timeout(500)
            s1 = st(pg)
            ok["placed"] = s1["placed"] and not s1["armed"]
            ring = pg.evaluate("(function(){var c=document.querySelector('#cut-svg circle.cut-pt[r=\"5\"]');return c?[+c.getAttribute('cx'),+c.getAttribute('cy')]:null})()")
            ok["plane_through_click_px_error"] = None if not ring else float(np.hypot(ring[0] - cx, ring[1] - cy))
            ok["plane_through_click"] = bool(ring) and ok["plane_through_click_px_error"] < 3.0
            ok["anchor"] = [round(v, 1) for v in s1["anchor"]]
            ok["offset_after_place"] = s1["offset"]
            pg.screenshot(path=f"{outp}_{name}_2_placed.png")
            # --- side
            a_before = pg.evaluate("document.getElementById('cut-pos').value")
            tap("#cut-flip"); s2 = st(pg)
            ok["flip_changes_side"] = s2["rs"] == -s1["rs"] and s2["ori"] == s1["ori"] and abs(s2["offset"] - s1["offset"]) < 1e-9
            ok["flip_changes_picture"] = changed(img(pg), base)
            pg.screenshot(path=f"{outp}_{name}_3_flipped.png")
            tap("#cut-side-a"); s2b = st(pg); ok["side_buttons"] = s2b["rs"] == 1
            tap("#cut-side-b"); ok["side_buttons"] = ok["side_buttons"] and st(pg)["rs"] == -1
            tap("#cut-side-a")
            # --- move along the normal
            tap('#cut-steps [data-step="10"]'); tap('#cut-steps [data-step="10"]')
            s3 = st(pg)
            ok["steps_move_20mm"] = abs(s3["offset"] - 20) < 1e-6 and s3["ori"] == s1["ori"] and s3["rs"] == 1 and s3["n0"] == s1["n0"]
            tap('#cut-steps [data-step="-1"]'); tap('#cut-steps [data-step="1"]'); tap('#cut-steps [data-step="-10"]')
            ok["steps_pm1_pm10"] = abs(st(pg)["offset"] - 10) < 1e-6
            tap('#cut-steps [data-step="10"]')                            # back to 20
            if not mobile:
                pg.keyboard.press("ArrowUp"); pg.keyboard.press("Shift+ArrowDown"); pg.keyboard.press("PageUp"); pg.keyboard.press("PageDown"); pg.keyboard.press("ArrowRight")
                ok["keys"] = abs(st(pg)["offset"] - (20 + 1 - 10 + 10 - 10 + 1)) < 1e-6
                pg.locator("#cut-pos").hover(); pg.mouse.wheel(0, -120)
                ok["wheel_over_slider"] = abs(st(pg)["offset"] - 13) < 1e-6
            mm_text = pg.locator("#cut-mm").inner_text()
            ok["readout_text"] = mm_text
            ok["readout_matches"] = abs(float(mm_text.lower().replace("−", "-").replace("mm", "").replace("+", "")) - st(pg)["offset"]) < 0.06
            sl = pg.evaluate("(function(){var e=document.getElementById('cut-pos');return [+e.min,+e.max,+e.value]})()")
            ok["slider_range"] = sl
            pg.evaluate("(function(){var e=document.getElementById('cut-pos');e.value=String(+e.min+0.5*(+e.max-+e.min));e.dispatchEvent(new Event('input',{bubbles:true}))})()")
            ok["slider_input"] = abs(st(pg)["offset"] - (sl[0] + 0.5 * (sl[1] - sl[0]))) < 1.0
            pg.screenshot(path=f"{outp}_{name}_4_moved.png")
            # --- presets
            for ax, nm in (("y", "axial"), ("z", "coronal"), ("x", "sagittal"), ("view", "view")):
                tap(f'#cut-axis [data-axis="{ax}"]'); sx = st(pg)
                ok[f"preset_{nm}"] = sx["ori"] == ax and abs(sx["offset"]) < 1e-6 and sx["rs"] == (-1 if ax == "view" else 1)
                if ax in ("y", "view"): pg.screenshot(path=f"{outp}_{name}_5_{nm}.png")
            # --- selection and picking with the cut on
            tap("#cut-axis [data-axis=\"x\"]")
            sel_before = pg.evaluate("document.querySelector('#insp-head h2') ? document.querySelector('#insp-head h2').textContent : (document.getElementById('info')||{}).className")
            if mobile: pg.touchscreen.tap(cx, cy)
            else: pg.mouse.click(cx, cy)
            pg.wait_for_timeout(500)
            sel_after = pg.evaluate("document.querySelector('#insp-head h2') ? document.querySelector('#insp-head h2').textContent : (document.getElementById('info')||{}).className")
            ok["selection_works_with_cut_on"] = sel_after != sel_before and st(pg)["on"] and not st(pg)["armed"]
            pg.screenshot(path=f"{outp}_{name}_6_selected.png")
            if pg.evaluate("document.getElementById('app') && document.getElementById('app').classList.contains('sheet-open')"):
                ok["panel_steps_aside_while_sheet_open"] = pg.locator("#cut-panel").is_hidden()
                tap("#m-info")                                            # close the phone sheet to get the panel back
                ok["panel_returns_after_sheet_closed"] = pg.locator("#cut-panel").is_visible()
            # --- layers / x-ray / source facet with the cut on
            xr = "#t-xray" if kind == "own" else "#btn-xray"
            jsclick = lambda sel: pg.evaluate("document.querySelector(%r).click()" % sel)
            jsclick(xr); pg.wait_for_timeout(400); pg.screenshot(path=f"{outp}_{name}_7_xray_cut.png"); jsclick(xr)
            if kind == "own" and pg.locator(".src-colour").count():
                pg.locator(".src-colour").first.scroll_into_view_if_needed()
                pg.locator(".src-colour").first.click(force=True) if not mobile else pg.evaluate("document.querySelector('.src-colour').click()")
                pg.wait_for_timeout(400); ok["source_facet_clicked"] = True
                pg.evaluate("document.querySelector('.src-colour[aria-pressed=\"true\"]') && document.querySelector('.src-colour[aria-pressed=\"true\"]').click()")
            # --- add-on API contract
            api = pg.evaluate("(function(){var a=__T.api();var s=__T.ctl().state();var c=a.cut();return {cut:c,kn:s.kn,cc:s.c}})()")
            ok["api_cut_matches_plane"] = bool(api["cut"]) and all(abs(api["cut"][i] - api["kn"][i]) < 1e-6 for i in range(3)) and abs(api["cut"][3] - api["cc"]) < 1e-3
            api2 = pg.evaluate("(function(){var a=__T.api();a.setCut({normal:[0,0,-1],point:[0,5,7]});var s=__T.ctl().state();var c=a.cut();a.setCut(null);return {s:s,c:c,after:__T.ctl().state().on}})()")
            ok["api_setCut_view_plane"] = api2["s"]["on"] and api2["s"]["ori"] == "view" and abs(api2["c"][2] + 1) < 1e-9 and abs(api2["c"][3] - 7) < 1e-6 and api2["after"] is False
            # --- needle add-on, when staged next to the page
            if pg.locator("#t-needle").count():
                pg.evaluate("document.getElementById('t-needle').click()"); pg.wait_for_timeout(500)
                if pg.locator("#ncl-cuthere").count():
                    pg.evaluate("document.getElementById('ncl-cuthere').click()"); pg.wait_for_timeout(500)
                    sn = st(pg)
                    ok["needle_cut_through_target"] = sn["on"] and sn["ori"] == "view" and pg.locator("#cut-panel").is_visible()
                    pg.screenshot(path=f"{outp}_{name}_8_needle_cut.png")
                ok["needle_panel_present"] = True
            else:
                ok["needle_panel_present"] = False
            # --- reset / exit
            if not st(pg)["on"]: tap("#t-cut")
            tap("#cut-reset"); sr = st(pg)
            ok["reset_cut"] = sr["ori"] == "x" and sr["rs"] == 1 and abs(sr["offset"]) < 1e-9 and not sr["placed"] and sr["on"]
            tap("#cut-exit"); sx = st(pg)
            ok["exit_cut"] = (not sx["on"]) and pg.locator("#cut-panel").is_hidden() and pg.evaluate("document.getElementById('cut-svg').style.display==='none'")
            pg.wait_for_timeout(300)
            ok["exit_clears_api_cut"] = pg.evaluate("__T.api().cut()") is None
            pg.screenshot(path=f"{outp}_{name}_9_after_exit.png")
            R["errors"] = errs; R["http_ge_400"] = sorted(set(notes))
            res[name] = R
            ctx.close()
        b.close()
finally:
    srv.terminate()
print(json.dumps(res, indent=1))
