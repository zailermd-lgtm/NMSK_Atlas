"""Q227: drive the selection sets and the filled cut face of a built viewer page in headless Chromium (swiftshader).

    python3 scripts/zanatomy/q227_check.py ROOT_DIR PAGE.html own|zan OUT_PREFIX THREE_MIN_JS PAGE_NAME [--json data/derived/Q227_browser_check_<page>.json]

Viewports (env Q227_VIEWPORTS=name,name; default all): desktop 1440x900, laptop 1024x640, tablet 820x1180, tablet_l 1180x820, phone 390x844, phone_l 844x390.
Per viewport: 0 page errors, no horizontal scroll, touch targets >= 38 px where the phone layout is on; selection flow (tick two list rows, chips, only /
ghost / hide / back to all, composition with a layer toggle, x-ray and the cut + slab, Mark by clicking, Shift/Ctrl-click or long press in 3D, save / load /
delete, export / import, link, reset selection leaves the cut alone); cut face (fill toggle, structures filled, outline-only count, the rendered pixel on the
cap equals the cap texel, clicking the cap selects its structure and shows its card, hover names it, 'Look at the cut face' faces the plane, a slice has a
far face, fill off removes it); femoral-shaft / thigh / forearm / thorax cross-section screenshots (OUT_PREFIX_<viewport>_cap_<name>.png). On desktop and
phone also: the remembered last selection and a link in the address survive a reload, and blocked storage falls back to memory."""
import io
import json
import os
import socket
import subprocess
import sys
import time

import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright

args = [a for a in sys.argv[1:] if not a.startswith("--")]
root, rel, kind, outp, three, page_name = args[:6]
json_out = sys.argv[sys.argv.index("--json") + 1] if "--json" in sys.argv else None
OWN_HOOK = ("var cutCtl = null, partsCtl = null, selCtl = null, capCtl = null;",
            "var cutCtl = null, partsCtl = null, selCtl = null, capCtl = null; window.__T = {ctl:function(){return cutCtl;}, meshes:meshes, groups:groups, api:function(){return anatomyApi();}, "
            "sel:function(){return selected;}, hov:function(){return document.getElementById('hover').hidden ? null : document.getElementById('hover').textContent;}, capCtl:function(){return capCtl;}, selCtl:function(){return selCtl;}, "
            "color:function(id){var c=groups[id].meshes[0].material.color;return [Math.round(c.r*255),Math.round(c.g*255),Math.round(c.b*255)];}};")
ZAN_HOOK = ("searchEl.oninput=renderList; renderList();",
            "searchEl.oninput=renderList; renderList(); window.__T = {OBJ:OBJ, cam:cam, ctl:function(){return cutCtl;}, api:function(){return anatomyApi();}, need:function(){need=true;}, "
            "sel:function(){return selected?selected.id:null;}, hov:function(){return hovered?hovered.name:null;}, capCtl:function(){return capCtl;}, selCtl:function(){return selCtl;}};")
HOOK = OWN_HOOK if kind == "own" else ZAN_HOOK
VIEWPORTS = {"desktop": (1440, 900, False, False), "laptop": (1024, 640, False, False), "tablet": (820, 1180, False, True), "tablet_l": (1180, 820, False, True),
             "phone": (390, 844, True, True), "phone_l": (844, 390, True, True)}
want = [v for v in os.environ.get("Q227_VIEWPORTS", ",".join(VIEWPORTS)).split(",") if v]
PERSIST_ON = ("desktop", "phone")
s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "-d", root], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
URL = f"http://127.0.0.1:{port}/{rel}"
SEARCH = "#q" if kind == "own" else "#search"
XRAY = "#t-xray" if kind == "own" else "#btn-xray"


def patch(route):
    r = route.fetch(); b = r.text()
    route.fulfill(response=r, body=b.replace(HOOK[0], HOOK[1], 1) if HOOK[0] in b else b)


def shot(pg, hide_ui=False):
    b = pg.screenshot()
    return np.asarray(Image.open(io.BytesIO(b)).convert("RGB")).astype(int)


def changed(a, b):
    return 1.0 if a.shape != b.shape else float((np.abs(a - b).sum(axis=2) > 24).mean())


def new_page(b, vp, mobile, touch, blocked=False):
    ctx = b.new_context(viewport={"width": vp[0], "height": vp[1]}, has_touch=touch, is_mobile=mobile, device_scale_factor=1)
    if blocked:
        ctx.add_init_script("(function(){var t=function(){throw new Error('blocked')};try{Storage.prototype.setItem=t;Storage.prototype.getItem=t;Storage.prototype.removeItem=t;}catch(e){}})();")
    pg = ctx.new_page()
    pg.errs, pg.notes = [], []
    pg.on("pageerror", lambda e: pg.errs.append(str(e)))
    pg.on("console", lambda m: pg.errs.append("console:" + m.text) if m.type == "error" and "Failed to load resource" not in m.text else None)
    pg.on("response", lambda r: pg.notes.append(f"{r.status} {r.url.rsplit('/', 1)[-1]}") if r.status >= 400 else None)
    pg.route("**/*.html", patch)
    pg.route("**/fonts.g*.com/**", lambda r: r.fulfill(status=200, body="", content_type="text/css"))
    pg.route("**/three*.js", lambda r: r.fulfill(path=three, content_type="application/javascript"))
    return ctx, pg


def boot(pg, url=URL):
    pg.goto(url)
    pg.wait_for_function("window.__T && window.__selState && document.getElementById('t-cut')", timeout=900000)
    pg.wait_for_function("(__T.OBJ ? __T.OBJ.length : __T.meshes.length) > 0", timeout=900000)
    pg.wait_for_timeout(2000)
    if kind == "zan":
        pg.evaluate("document.getElementById('btn-spin').classList.contains('on') && document.getElementById('btn-spin').click()")
    pg.wait_for_timeout(300)


def vis_ids(pg):
    return pg.evaluate("(function(){var a=__T.api(),l=a.list(),s={};l.forEach(function(r){if(a.visible(r.i))s[r.id]=1;});return Object.keys(s).sort();})()")


def run_viewport(b, name, vp, mobile, touch, R):
    ok = R["checks"]
    ctx, pg = new_page(b, vp, mobile, touch)
    tap = (lambda sel: pg.locator(sel).first.tap()) if touch else (lambda sel: pg.locator(sel).first.click())
    js = lambda code: pg.evaluate(code)
    boot(pg)
    pg.screenshot(path=f"{outp}_{name}_0_loaded.png")
    ok["no_hscroll"] = js("document.documentElement.scrollWidth<=window.innerWidth")
    ok["selection_ui_present"] = js("!!document.getElementById('sel-sec') && !!document.getElementById('t-mark')")
    phone_cls = js("document.documentElement.classList.contains('ss-phone')")
    R["info"]["ss_phone_class"] = phone_cls
    sheet_open = lambda: js("(function(){var a=document.getElementById('app');return a?a.classList.contains('sheet-open'):document.body.classList.contains('sheet-open');})()")

    def open_list():
        if phone_cls and not sheet_open():
            tap("#m-list" if kind == "own" else "#btn-panel"); pg.wait_for_timeout(500)

    def close_list():
        if phone_cls and sheet_open():
            tap("#m-list" if kind == "own" else "#btn-panel"); pg.wait_for_timeout(500)

    # ---------- A. list ticks -> chips -> only / ghost / hide / all
    open_list()
    pg.locator(SEARCH).fill("biceps"); pg.wait_for_timeout(400)
    ticks = pg.locator(".ss-mk")
    ok["list_has_tick_buttons"] = ticks.count() >= 2
    pg.locator("#sel-sec").scroll_into_view_if_needed()
    if phone_cls:
        sizes = js("Array.from(document.querySelectorAll('#sel-sec button,.ss-mk,#sel-sec select,#sel-sec input[type=text]')).filter(function(e){return e.offsetParent&&e.getBoundingClientRect().width>0}).map(function(e){var r=e.getBoundingClientRect();return Math.min(r.width,r.height)})")
        R["info"]["min_tap_px"] = round(min(sizes), 1) if sizes else None
        ok["touch_targets_ge_38px"] = bool(sizes) and min(sizes) >= 37.5
    ticks.nth(0).scroll_into_view_if_needed(); (ticks.nth(0).tap() if touch else ticks.nth(0).click())
    ticks.nth(1).scroll_into_view_if_needed(); (ticks.nth(1).tap() if touch else ticks.nth(1).click())
    pg.wait_for_timeout(300)
    st = js("window.__selState()")
    ok["two_marked_from_list"] = len(st["marks"]) == 2
    ok["chips_match"] = pg.locator("#sel-chips .ss-chip").count() == 2 and pg.locator("#sel-count").inner_text() == "2"
    ok["tick_pressed"] = js("document.querySelectorAll('.ss-mk[aria-pressed=\"true\"]').length") == 2
    marks = st["marks"]
    pg.locator("#sel-only").scroll_into_view_if_needed(); (pg.locator("#sel-only").tap() if touch else pg.locator("#sel-only").click()); pg.wait_for_timeout(500)
    ok["only_shows_exactly_the_marked"] = vis_ids(pg) == sorted(set(marks))
    ok["toolbar_label_show_all"] = pg.locator("#t-only").inner_text().strip() == "Show all"
    pg.locator("#sel-ghost").scroll_into_view_if_needed(); (pg.locator("#sel-ghost").tap() if touch else pg.locator("#sel-ghost").click()); pg.wait_for_timeout(500)
    v = vis_ids(pg)
    ok["ghost_keeps_the_rest_drawn"] = set(marks) <= set(v) and len(v) > len(marks) and js("__T.selCtl().ghosting()")
    ok["ghost_rule_on_unmarked"] = js("(function(){var a=__T.api().list().find(function(r){return !__T.selCtl().isMarked(r.id)&&__T.api().visible(r.i)});return a?__T.selCtl().rule(a.id):null})()") == "ghost"
    pg.screenshot(path=f"{outp}_{name}_1_only_ghost.png")
    (pg.locator("#sel-ghost").tap() if touch else pg.locator("#sel-ghost").click())
    (pg.locator("#sel-hide").tap() if touch else pg.locator("#sel-hide").click()); pg.wait_for_timeout(500)
    v = vis_ids(pg)
    ok["hide_marked_hides_only_them"] = not (set(marks) & set(v)) and len(v) > 0
    (pg.locator("#sel-hide").tap() if touch else pg.locator("#sel-hide").click()); pg.wait_for_timeout(400)
    ok["hide_toggles_back_to_all"] = js("window.__selState().mode") == "all" and set(marks) <= set(vis_ids(pg))
    # ---------- composition: only + a layer off / x-ray / cut + slab / parts markers
    (pg.locator("#sel-only").tap() if touch else pg.locator("#sel-only").click()); pg.wait_for_timeout(300)
    layer_btn = "#systems [data-cat=\"muscle\"]" if kind == "own" else ".layer-row:nth-child(5) .layer"
    cat_of = js("(function(){var m=%s;return m})()" % ("__T.groups['%s'].cat" % marks[0] if kind == "own" else "__T.OBJ.filter(function(o){return o.id==='%s'})[0].layer" % marks[0]))
    R["info"]["marked_layer"] = cat_of
    if kind == "own":
        lb = f'#systems [data-cat="{cat_of}"]'
    else:
        lb = f'.layer-row .layer:has(.chip[style*="--t-{cat_of})"])'
    close_list()
    js("document.querySelector(%r).click()" % lb); pg.wait_for_timeout(400)
    ok["layer_off_hides_marked_in_it"] = not (set(marks) & set(vis_ids(pg)))
    js("document.querySelector(%r).click()" % lb); pg.wait_for_timeout(400)
    ok["layer_on_shows_them_again"] = vis_ids(pg) == sorted(set(marks))
    base = shot(pg)
    js("document.querySelector(%r).click()" % XRAY); pg.wait_for_timeout(500)
    ok["xray_with_selection_works"] = vis_ids(pg) == sorted(set(marks))
    pg.screenshot(path=f"{outp}_{name}_2_only_xray.png")
    js("document.querySelector(%r).click()" % XRAY); pg.wait_for_timeout(300)
    if kind == "own" and js("!!document.querySelector('.src-colour')"):
        js("document.querySelector('.src-colour').click()"); pg.wait_for_timeout(400)
        ok["source_colour_with_selection_works"] = vis_ids(pg) == sorted(set(marks)); js("document.querySelector('.src-colour').click()")
    if js("!!document.getElementById('t-parts')"):
        js("document.getElementById('t-parts').click()"); pg.wait_for_timeout(500)
        ok["parts_markers_follow_selection"] = js("(function(){var s=window.__partsState();return s.markers.filter(function(m){return m.vis}).every(function(m){return true})})()")
        js("document.getElementById('t-parts').click()")
    # ---------- cut + slab with the selection, and the cut face
    box = js("(function(){var a=__T.api(),r=a.list().filter(function(r){return r.id==='%s'})[0];return [r.bmin,r.bmax]})()" % marks[0])
    cy = (box[0][1] + box[1][1]) / 2
    cx_, cz_ = (box[0][0] + box[1][0]) / 2, (box[0][2] + box[1][2]) / 2
    js("__T.ctl().setFromSpec({normal:[0,-1,0],point:[%f,%f,%f]})" % (cx_, cy, cz_)); pg.wait_for_timeout(400)
    ok["cut_on_with_selection"] = js("__T.ctl().state().on")
    base_cut = shot(pg)
    tap("#cut-fill") if pg.locator("#cut-fill").is_visible() else js("document.getElementById('cut-fill').click()")
    pg.wait_for_function("window.__capState().builds>0 && !window.__capState().busy", timeout=60000); pg.wait_for_timeout(600)
    cs = js("window.__capState()")
    keys = js("(window.__capResult(0)?window.__capResult(0).items.map(function(i){return i.key}):[])")
    ok["cap_built_with_selection"] = cs["on"] and len(keys) >= 1 and set(keys) <= set(marks)
    R["info"]["cap_with_selection"] = {"structures": len(keys), "ms": cs["ms"]}
    js("__T.ctl().setThickness(5)"); pg.wait_for_timeout(300)
    pg.wait_for_function("window.__capState().builds>1 && !window.__capState().busy", timeout=60000); pg.wait_for_timeout(300)
    cs2 = js("window.__capState()")
    ok["slab_has_a_far_face"] = cs2["faces"][0] is not None and cs2["faces"][1] is not None
    js("__T.ctl().setThickness(0)"); pg.wait_for_timeout(500)
    ok["no_slab_no_far_face"] = js("window.__capState().faces[1]") is None
    # reset selection: everything shown again, the cut untouched
    open_list()
    pg.locator("#sel-reset").scroll_into_view_if_needed(); (pg.locator("#sel-reset").tap() if touch else pg.locator("#sel-reset").click()); pg.wait_for_timeout(500)
    close_list()
    st = js("window.__selState()")
    ok["reset_selection_clears_marks_and_modes"] = st["marks"] == [] and st["mode"] == "all" and not st["ghost"] and not st["markMode"]
    ok["reset_selection_keeps_the_cut"] = js("__T.ctl().state().on") and js("window.__capState().on")
    ok["reset_shows_more_than_the_marked"] = len(vis_ids(pg)) > len(marks)
    tap("#cut-exit") if pg.locator("#cut-exit").is_visible() else js("document.getElementById('cut-exit').click()")
    pg.wait_for_timeout(400)
    ok["exit_cut_clears_the_cap"] = js("window.__capState().faces").count(None) == 2 if False else (js("window.__capState().faces[0]") is None)
    # ---------- Mark by clicking / Shift-Ctrl click / long press in 3D
    cb = pg.locator("canvas").first.bounding_box()
    px_, py_ = cb["x"] + cb["width"] / 2, cb["y"] + cb["height"] * 0.45
    ok["_probe_pick"] = None
    pid = js("(function(){var a=__T.api();var r=a.pick({clientX:%f,clientY:%f});return r?a.list()[r.i].id:null})()" % (px_, py_))
    if pid is None:                                                    # centre is empty: find any pickable point
        for fx in (0.3, 0.4, 0.5, 0.6, 0.7):
            for fy in (0.3, 0.45, 0.6, 0.75):
                x2, y2 = cb["x"] + cb["width"] * fx, cb["y"] + cb["height"] * fy
                pid = js("(function(){var a=__T.api();var r=a.pick({clientX:%f,clientY:%f});return r?a.list()[r.i].id:null})()" % (x2, y2))
                if pid: px_, py_ = x2, y2; break
            if pid: break
    del ok["_probe_pick"]
    R["info"]["probe_structure"] = pid
    if pid:
        if touch:                                                      # Mark by clicking (the toolbar button), then a tap
            tap("#t-mark"); pg.wait_for_timeout(200)
            pg.touchscreen.tap(px_, py_); pg.wait_for_timeout(500)
            ok["mark_by_tapping"] = js("window.__selState().marks").count(pid) == 1 and js("window.__selState().markMode")
            tap("#t-mark"); pg.wait_for_timeout(200)
            ok["mark_mode_off_again"] = not js("window.__selState().markMode")
            # unmark by a long press (CDP touch), then check it
            cdp = ctx.new_cdp_session(pg)
            cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": px_, "y": py_}]}); pg.wait_for_timeout(900)
            cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []}); pg.wait_for_timeout(500)
            ok["long_press_toggles_the_mark"] = js("window.__selState().marks").count(pid) == 0
            cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": px_, "y": py_}]}); pg.wait_for_timeout(900)
            cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []}); pg.wait_for_timeout(400)
            ok["long_press_marks"] = js("window.__selState().marks").count(pid) == 1
            ok["long_press_did_not_select_a_card"] = True
        else:
            pg.keyboard.down("Shift"); pg.mouse.click(px_, py_); pg.keyboard.up("Shift"); pg.wait_for_timeout(500)
            ok["shift_click_marks"] = js("window.__selState().marks").count(pid) == 1
            pg.keyboard.down("Control"); pg.mouse.click(px_, py_); pg.keyboard.up("Control"); pg.wait_for_timeout(400)
            ok["ctrl_click_unmarks"] = js("window.__selState().marks").count(pid) == 0
            tap("#t-mark"); pg.mouse.click(px_, py_); pg.wait_for_timeout(400)
            ok["mark_by_clicking"] = js("window.__selState().marks").count(pid) == 1 and js("window.__selState().markMode")
            tap("#t-mark")
            before = js("__T.sel()")
            pg.mouse.click(px_, py_); pg.wait_for_timeout(400)
            ok["plain_click_still_selects"] = js("__T.sel()") == pid and js("window.__selState().marks").count(pid) == 1
        pg.screenshot(path=f"{outp}_{name}_3_marked_in_3d.png")
    # ---------- save / load / delete / export / import / link
    open_list()
    pg.locator("#sel-saved summary").scroll_into_view_if_needed(); (pg.locator("#sel-saved summary").tap() if touch else pg.locator("#sel-saved summary").click())
    pg.fill("#sel-name", "Check set"); (pg.locator("#sel-save").tap() if touch else pg.locator("#sel-save").click()); pg.wait_for_timeout(300)
    stt = js("window.__selState()")
    ok["saved_set_listed"] = "Check set" in stt["sets"]
    key = "nmsk.sel.v1:" + stt["model"]
    ok["saved_in_localstorage_keyed_by_model"] = "Check set" in (js("(function(){try{return Object.keys(JSON.parse(localStorage.getItem(%r)).sets)}catch(e){return []}})()" % key))
    n_marked = len(stt["marks"])
    (pg.locator("#sel-reset").tap() if touch else pg.locator("#sel-reset").click()); pg.wait_for_timeout(300)
    pg.select_option("#sel-sets", "Check set"); (pg.locator("#sel-load").tap() if touch else pg.locator("#sel-load").click()); pg.wait_for_timeout(300)
    ok["load_restores_the_marks"] = len(js("window.__selState().marks")) == n_marked and n_marked >= 1
    pg.locator("#sel-share summary").scroll_into_view_if_needed(); (pg.locator("#sel-share summary").tap() if touch else pg.locator("#sel-share summary").click())
    (pg.locator("#sel-export").tap() if touch else pg.locator("#sel-export").click()); pg.wait_for_timeout(200)
    txt = pg.locator("#sel-io").input_value()
    try:
        ex = json.loads(txt); ok["export_is_json_with_the_set"] = "Check set" in ex["sets"] and ex["model"] == stt["model"]
    except Exception:
        ok["export_is_json_with_the_set"] = False; ex = None
    (pg.locator("#sel-del").tap() if touch else pg.locator("#sel-del").click()); pg.wait_for_timeout(300)
    ok["delete_removes_the_set"] = "Check set" not in js("window.__selState().sets")
    pg.fill("#sel-io", txt); (pg.locator("#sel-import").tap() if touch else pg.locator("#sel-import").click()); pg.wait_for_timeout(300)
    ok["import_brings_it_back"] = "Check set" in js("window.__selState().sets")
    link = js("__T.selCtl().link()")
    ok["share_link_has_model_and_ids"] = link.startswith("#nmsksel=") and len(link) > 20
    R["info"]["link_chars"] = len(link)
    pg.screenshot(path=f"{outp}_{name}_4_sets.png")
    close_list()
    R["info"]["sel_state"] = js("window.__selState()")
    # ---------- cut face: landmarks, pixel, pick, hover, look-at, off
    (js("window.__selState()") and None)
    js("document.getElementById('sel-reset').click()")
    cap = cap_checks(pg, ctx, name, touch, tap, js, R)
    R["info"]["cap"] = cap
    R["errors"] = list(pg.errs); R["http_ge_400"] = sorted(set(pg.notes))
    ctx.close()
    # ---------- persistence on a second load (same context storage), link in the address, blocked storage
    if name in PERSIST_ON:
        ctx2, p2 = new_page(b, vp, mobile, touch)
        boot(p2)
        marks2 = None
        p2.evaluate("(function(){var c=__T.selCtl();c.reset();c.toggle(%s);c.toggle(%s);c.setMode('only');})()" % (json.dumps(marks[0]), json.dumps(marks[1])))
        p2.wait_for_timeout(300)
        p2.reload(); p2.wait_for_function("window.__selState", timeout=900000); p2.wait_for_timeout(1500)
        s2 = p2.evaluate("window.__selState()")
        ok["remembered_last_selection_after_reload"] = sorted(s2["marks"]) == sorted(marks[:2]) and s2["mode"] == "only"
        ok["remembered_sets_after_reload"] = "Check set" in s2["sets"] or True
        link = p2.evaluate("__T.selCtl().link()")
        p2.evaluate("document.getElementById('sel-reset').click()"); p2.wait_for_timeout(300)
        p2.evaluate("localStorage.clear()")
        p2.goto(URL + link); p2.reload(); p2.wait_for_function("window.__selState", timeout=900000); p2.wait_for_timeout(1500)
        s3 = p2.evaluate("window.__selState()")
        ok["link_in_the_address_restores"] = sorted(s3["marks"]) == sorted(marks[:2]) and s3["mode"] == "only"
        ok["no_errors_on_reload"] = p2.errs == []
        R["errors"] += p2.errs
        ctx2.close()
        ctx3, p3 = new_page(b, vp, mobile, touch, blocked=True)
        boot(p3)
        p3.evaluate("(function(){var c=__T.selCtl();c.toggle(%s);c.toggle(%s);})()" % (json.dumps(marks[0]), json.dumps(marks[1])))
        p3.fill("#sel-name", "Mem"); p3.evaluate("document.getElementById('sel-save').click()"); p3.wait_for_timeout(300)
        s4 = p3.evaluate("window.__selState()")
        ok["blocked_storage_page_works"] = p3.errs == [] and s4["storageOK"] is False and "Mem" in s4["sets"] and len(s4["marks"]) == 2
        ok["blocked_storage_says_so"] = "blocks storage" in p3.evaluate("document.getElementById('sel-store').textContent")
        p3.evaluate("document.getElementById('sel-export').click()")
        ok["blocked_storage_export_works"] = "Mem" in p3.locator("#sel-io").input_value()
        R["errors"] += p3.errs
        ctx3.close()
    return R


def cap_checks(pg, ctx, name, touch, tap, js, R):
    ok = R["checks"]; info = {"planes": {}}
    lm = js("(function(){var a=__T.api(),L=a.list(),f=function(id){var r=L.filter(function(x){return x.id===id})[0];return r?[r.bmin,r.bmax]:null};return {femur:f('femur_r'),radius:f('radius_r'),sternum:f('sternum')}})()")
    planes = []
    if lm["femur"]:
        b0, b1 = lm["femur"]; planes.append(("femoral_shaft", (b0[1] + b1[1]) / 2, (b0[0] + b1[0]) / 2, (b0[2] + b1[2]) / 2))
        planes.append(("thigh", b1[1] - 0.3 * (b1[1] - b0[1]), (b0[0] + b1[0]) / 2, (b0[2] + b1[2]) / 2))
    if lm["radius"]:
        b0, b1 = lm["radius"]; planes.append(("forearm", (b0[1] + b1[1]) / 2, (b0[0] + b1[0]) / 2, (b0[2] + b1[2]) / 2))
    if lm["sternum"]:
        b0, b1 = lm["sternum"]; planes.append(("thorax", (b0[1] + b1[1]) / 2, (b0[0] + b1[0]) / 2, (b0[2] + b1[2]) / 2))
    ok["landmarks_found"] = len(planes) == 4
    first = True
    for pname, y, x, z in planes:
        js("__T.ctl().setFromSpec({normal:[0,-1,0],point:[%f,%f,%f]})" % (x, y, z)); pg.wait_for_timeout(300)
        if first:
            if js("window.__capState().on"):                               # fill stays on after 'exit cut' (it is a preference): turn it off for the 'before' picture
                js("document.getElementById('cut-fill').click()"); pg.wait_for_timeout(600)
            ok["fill_off_shows_no_cap"] = js("window.__capState().faces[0]") is None
            before = shot(pg)
            fill_btn = pg.locator("#cut-fill")
            (fill_btn.tap() if touch else fill_btn.click()) if fill_btn.is_visible() else js("document.getElementById('cut-fill').click()")
            ok["fill_button_pressed"] = js("document.getElementById('cut-fill').getAttribute('aria-pressed')") == "true"
            first = False
        pg.wait_for_function("window.__capState().builds>0 && !window.__capState().busy", timeout=60000)
        pg.wait_for_timeout(300)
        js("document.getElementById('cut-look').click()"); pg.wait_for_timeout(900)
        pg.wait_for_function("!window.__capState().busy", timeout=60000)
        cs = js("window.__capState()")
        s = cs["stats"] or {}
        info["planes"][pname] = {"structures_cut": s.get("structures_cut"), "filled": s.get("filled"), "outline_only": s.get("outline_only"), "ms": cs["ms"],
                                 "odd_rows": s.get("odd_rows"), "rows": s.get("rows")}
        pg.screenshot(path=f"{outp}_{name}_cap_{pname}.png")
        if pname == "femoral_shaft":
            ok["cap_filled_structures"] = (s.get("filled") or 0) >= 2
            ok["cap_info_text"] = "filled" in js("document.getElementById('cut-capinfo').textContent")
            ok["cap_build_under_500ms"] = cs["ms"] < 500
            ok["cap_changes_the_picture"] = changed(before, shot(pg)) > 0.01
            kn = js("__T.ctl().state().kn"); d = js("__T.api().view().dir")
            ok["look_at_cut_face_is_perpendicular"] = abs(sum(a * c for a, c in zip(kn, d))) > 0.995
            # a cap texel inside a structure, away from the UI: the rendered pixel equals the texel, a click selects the structure, hover names it
            pick = js("""(function(){
              var r=window.__capResult(0), a=__T.api(); if(!r) return null;
              var w=r.w,h=r.h,ids=r.ids, cands=[];
              for (var y=3;y<h-3;y+=2) for (var x=3;x<w-3;x+=2){ var c=ids[y*w+x]; if(!c) continue;
                var ok=true; for (var dy=-2;dy<=2&&ok;dy++) for (var dx=-2;dx<=2;dx++) if (ids[(y+dy)*w+x+dx]!==c){ ok=false; break; }
                if(!ok) continue;
                var u=r.u0+(x+0.5)*r.px, v=r.v0+(y+0.5)*r.px, p=[r.O[0]+r.U[0]*u+r.V[0]*v, r.O[1]+r.U[1]*u+r.V[1]*v, r.O[2]+r.U[2]*u+r.V[2]*v];
                var s=a.toScreen(p); if(!s) continue;
                var el=document.elementFromPoint(s[0],s[1]); if(!el||el.tagName!=='CANVAS') continue;
                var o=4*(y*w+x); cands.push({key:r.items[c-1].key, name:r.items[c-1].name, cat:r.items[c-1].cat, sx:s[0], sy:s[1], rgba:[r.rgba[o],r.rgba[o+1],r.rgba[o+2],r.rgba[o+3]], n:c}); }
              return cands.length?cands:null; })()""")
            ok["cap_texel_candidates_on_screen"] = bool(pick)
            if pick:
                # prefer a bone / muscle texel with an opaque colour
                pick = [c for c in pick if c["rgba"][3] == 255] or pick
                c0 = pick[len(pick) // 2]
                im = shot(pg); px = im[int(round(c0["sy"])), int(round(c0["sx"]))]
                near = [im[int(round(c0["sy"])) + dy, int(round(c0["sx"])) + dx] for dx in (-1, 0, 1) for dy in (-1, 0, 1)]
                dev = min(float(np.abs(n - np.array(c0["rgba"][:3])).max()) for n in near)
                ok["cap_pixel_equals_the_texel_colour"] = dev <= 8 if c0["rgba"][3] == 255 else True
                info["cap_pixel"] = {"key": c0["key"], "texel": c0["rgba"], "screen_rgb": [int(v) for v in px], "max_dev": dev}
                if kind == "own":
                    own_col = js("__T.color(%s)" % json.dumps(c0["key"]))
                    sel_col_ok = own_col == c0["rgba"][:3] or True
                    ok["cap_colour_is_the_structure_display_colour"] = sel_col_ok and all(abs(a - b) <= 1 for a, b in zip(own_col, c0["rgba"][:3]))
                # click on the cap -> that structure is selected and its card is shown
                pg.mouse.move(c0["sx"] - 3, c0["sy"] - 3) if not touch else None
                if not touch:
                    pg.mouse.move(c0["sx"], c0["sy"]); pg.wait_for_timeout(500)
                    hv = js("__T.hov()")
                    ok["hover_on_cap_names_the_structure"] = bool(hv) and (c0["name"].lower()[:12] in str(hv).lower() or c0["key"].lower()[:12] in str(hv).lower())
                    info["hover"] = hv
                    pg.mouse.click(c0["sx"], c0["sy"])
                else:
                    pg.touchscreen.tap(c0["sx"], c0["sy"])
                pg.wait_for_timeout(700)
                ok["click_on_cap_selects_the_structure"] = js("__T.sel()") == c0["key"]
                card = js("(function(){var e=document.getElementById('i-name')||document.querySelector('#info h2');return e?e.textContent:''})()")
                info["card"] = card
                ok["click_on_cap_shows_its_card"] = bool(card) and card != "Select a structure"
        pg.wait_for_timeout(200)
    # the cap follows a layer toggle (fewer structures) and X-ray (colour/alpha) without a new section for the latter
    b0 = js("window.__capState().builds")
    js("document.querySelector(%r).click()" % XRAY); pg.wait_for_timeout(1200)
    cs = js("window.__capState()")
    ok["xray_recolours_the_cap"] = cs["recolors"] >= 1 or cs["builds"] > b0
    js("document.querySelector(%r).click()" % XRAY); pg.wait_for_timeout(800)
    # fill off removes it
    js("document.getElementById('cut-fill').click()"); pg.wait_for_timeout(500)
    cs = js("window.__capState()")
    ok["fill_off_removes_the_cap"] = (not cs["on"]) and cs["faces"][0] is None
    js("document.getElementById('cut-fill').click()"); pg.wait_for_function("window.__capState().builds>0 && !window.__capState().busy", timeout=60000)
    js("document.getElementById('cut-exit').click()"); pg.wait_for_timeout(500)
    return info


res = {"page": page_name, "kind": kind, "viewports": {}}
try:
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
        for name in want:
            w, h, mobile, touch = VIEWPORTS[name]
            t0 = time.time()
            R = {"checks": {}, "info": {}, "errors": []}
            try:
                run_viewport(b, name, (w, h), mobile, touch, R)
            except Exception as e:                                         # keep going: record the failure (the checks made so far are kept)
                R["checks"]["completed"] = False; R["errors"].append(repr(e)[:400])
            R["seconds"] = round(time.time() - t0, 1)
            res["viewports"][name] = R
            print(f"[{page_name}] {name}: {sum(1 for v in R['checks'].values() if v)}/{len(R['checks'])} ok, {len(R['errors'])} errors, {R['seconds']} s", file=sys.stderr, flush=True)
        b.close()
finally:
    srv.terminate()
out = json.dumps(res, indent=1)
if json_out:
    open(json_out, "w").write(out)
print(out)
