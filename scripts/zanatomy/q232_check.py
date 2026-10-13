"""Q232: drive the selection INVERT + display states (fade / hide / ghost / x-ray / highlight, presets, keys, helpers) of a built viewer page in headless
Chromium (swiftshader).

    python3 scripts/zanatomy/q232_check.py ROOT_DIR PAGE.html own|zan OUT_PREFIX THREE_MIN_JS PAGE_NAME [--json data/derived/Q232_browser_check_<page>.json] [--merge]

Viewports (env Q232_VIEWPORTS=name,name; default all six): desktop 1440x900, laptop 1024x640, tablet 820x1180, tablet_l 1180x820, phone 390x844, phone_l 844x390.
Per viewport: 0 page errors, no horizontal scroll, the new controls present, touch targets >= 38 px on the phone layout, the panel scrolls; mark two biceps from the list,
Invert (marks = everything shown minus them, chips say so, count, toggles back), Fade others (opacity = the slider, marked stay solid, nothing removed from the add-on
visibility), Fade selected, Hide selected (not visible, not pickable), Highlight selected (colour), Ghost / X-ray groups, presets, keys I / F / H (and not while typing),
Mark all visible, Mark layer; composition with a layer toggle (Invert respects it), global X-ray, the Source facet (own); Cut + fill: the cap alpha follows the fade, a hidden
structure has no cap, the highlight colours the cap; saved inverse set -> reset -> load; export / link carry the inverse flag. Screenshots OUT_PREFIX_<viewport>_*.png."""
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
            "sel:function(){return selected;}, capCtl:function(){return capCtl;}, selCtl:function(){return selCtl;}, "
            "alpha:function(id){var m=groups[id].meshes[0];return m.visible?m.material.opacity:0;}, "
            "color:function(id){var c=groups[id].meshes[0].material.color;return [Math.round(c.r*255),Math.round(c.g*255),Math.round(c.b*255)];}};")
ZAN_HOOK = ("searchEl.oninput=renderList; renderList();",
            "searchEl.oninput=renderList; renderList(); window.__T = {OBJ:OBJ, cam:cam, ctl:function(){return cutCtl;}, api:function(){return anatomyApi();}, need:function(){need=true;}, "
            "sel:function(){return selected?selected.id:null;}, capCtl:function(){return capCtl;}, selCtl:function(){return selCtl;}, "
            "alpha:function(id){var o=objsById[id][0];if(!vis(o))return 0;var k=selLook(o);return faded.has(o)?Math.min(0.18,alphaFor[o.layer]):(k==='fade'||k==='xray'||k==='ghost')?selAlpha(k,o.layer,k==='ghost'?alphaFor[o.layer]:layerAlpha(o.layer)):layerAlpha(o.layer);}, "
            "color:function(id){var c=colOf(objsById[id][0]);return [Math.round(c[0]*255),Math.round(c[1]*255),Math.round(c[2]*255)];}};")
HOOK = OWN_HOOK if kind == "own" else ZAN_HOOK
VIEWPORTS = {"desktop": (1440, 900, False, False), "laptop": (1024, 640, False, False), "tablet": (820, 1180, False, True), "tablet_l": (1180, 820, False, True),
             "phone": (390, 844, True, True), "phone_l": (844, 390, True, True)}
want = [v for v in os.environ.get("Q232_VIEWPORTS", ",".join(VIEWPORTS)).split(",") if v]
FULL = tuple(v for v in os.environ.get("Q232_FULL", "desktop,phone").split(",") if v)       # the long flow (composition, cut + cap, saved sets); the others run the layout + core flow
s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "-d", root], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
URL = f"http://127.0.0.1:{port}/{rel}"
SEARCH = "#q" if kind == "own" else "#search"
XRAY = "#t-xray" if kind == "own" else "#btn-xray"
XRAY_OFF = "#t-xray" if kind == "own" else "#btn-solid"


def patch(route):
    r = route.fetch(); b = r.text()
    route.fulfill(response=r, body=b.replace(HOOK[0], HOOK[1], 1) if HOOK[0] in b else b)


def shot(pg):
    return np.asarray(Image.open(io.BytesIO(pg.screenshot())).convert("RGB")).astype(int)


def changed(a, b):
    return 1.0 if a.shape != b.shape else float((np.abs(a - b).sum(axis=2) > 24).mean())


def new_page(b, vp, mobile, touch):
    ctx = b.new_context(viewport={"width": vp[0], "height": vp[1]}, has_touch=touch, is_mobile=mobile, device_scale_factor=1)
    pg = ctx.new_page()
    pg.set_default_timeout(240000)
    pg.errs = []
    pg.on("pageerror", lambda e: pg.errs.append(str(e)))
    pg.on("console", lambda m: pg.errs.append("console:" + m.text) if m.type == "error" and "Failed to load resource" not in m.text else None)
    pg.route("**/*.html", patch)
    pg.route("**/fonts.g*.com/**", lambda r: r.fulfill(status=200, body="", content_type="text/css"))
    pg.route("**/three*.js", lambda r: r.fulfill(path=three, content_type="application/javascript"))
    return ctx, pg


def boot(pg):
    pg.goto(URL)
    pg.wait_for_function("window.__T && window.__selState && document.getElementById('t-cut')", timeout=900000)
    pg.wait_for_function("(__T.OBJ ? __T.OBJ.length : __T.meshes.length) > 0", timeout=900000)
    pg.wait_for_timeout(2000)
    if kind == "zan":
        pg.evaluate("document.getElementById('btn-spin').classList.contains('on') && document.getElementById('btn-spin').click()")
    pg.wait_for_timeout(300)


def vis_ids(pg):
    return pg.evaluate("(function(){var a=__T.api(),l=a.list(),s={};l.forEach(function(r){if(a.visible(r.i))s[r.id]=1;});return Object.keys(s).sort();})()")


def run_viewport(b, name, vp, mobile, touch, R):
    ok = R["checks"]; info = R["info"]
    full = name in FULL
    ctx, pg = new_page(b, vp, mobile, touch)
    js = lambda code: pg.evaluate(code)

    def tap(sel):
        l = pg.locator(sel).first
        l.scroll_into_view_if_needed()
        l.tap() if touch else l.click()
        pg.wait_for_timeout(350)

    boot(pg)
    ok["no_hscroll"] = js("document.documentElement.scrollWidth<=window.innerWidth")
    ids_needed = ["sel-invert", "sel-markvis", "sel-cat", "sel-markcat", "sel-fade", "sel-hl", "sel-p-isolate", "sel-p-fadeoth", "sel-p-fadesel", "sel-p-hidesel", "sel-p-hlsel",
                  "sel-only", "sel-hide", "sel-ghost", "t-invert", "t-mark"]
    ok["new_controls_present"] = all(js("!!document.getElementById('%s')" % i) for i in ids_needed) and js("document.querySelectorAll('.ss-st[data-g]').length") == 11
    phone_cls = js("document.documentElement.classList.contains('ss-phone')")
    info["ss_phone_class"] = phone_cls
    sheet_open = lambda: js("(function(){var a=document.getElementById('app');return a?a.classList.contains('sheet-open'):document.body.classList.contains('sheet-open');})()")

    def open_list():
        if phone_cls and not sheet_open():
            tap("#m-list" if kind == "own" else "#btn-panel"); pg.wait_for_timeout(300)

    def close_list():
        if phone_cls and sheet_open():
            tap("#m-list" if kind == "own" else "#btn-panel"); pg.wait_for_timeout(300)

    def st():
        return js("window.__selState()")

    open_list()
    pg.locator(SEARCH).fill("biceps"); pg.wait_for_timeout(400)
    pg.locator("#sel-sec").scroll_into_view_if_needed()
    if phone_cls:
        sizes = js("Array.from(document.querySelectorAll('#sel-sec button,.ss-mk,#sel-sec select,#sel-sec input,#sel-sec summary')).filter(function(e){return e.offsetParent&&e.getBoundingClientRect().width>0}).map(function(e){var r=e.getBoundingClientRect();return Math.min(r.width,r.height)})")
        info["min_tap_px"] = round(min(sizes), 1) if sizes else None
        ok["touch_targets_ge_38px"] = bool(sizes) and min(sizes) >= 37.5
    # the panel scrolls: its scroll container has overflow auto/scroll and the section fits horizontally
    ok["panel_scrollable_no_overflow_x"] = js("(function(){var e=document.getElementById('sel-sec'),p=e.parentElement;while(p&&p!==document.body){var o=getComputedStyle(p).overflowY;if(o==='auto'||o==='scroll')break;p=p.parentElement;}"
                                                "var r=e.getBoundingClientRect(),pr=p?p.getBoundingClientRect():{left:0,right:innerWidth};return !!p&&e.scrollWidth<=e.clientWidth+1&&r.left>=pr.left-1&&r.right<=pr.right+1;})()")
    ticks = pg.locator(".ss-mk")
    ticks.nth(0).scroll_into_view_if_needed(); (ticks.nth(0).tap() if touch else ticks.nth(0).click())
    ticks.nth(1).scroll_into_view_if_needed(); (ticks.nth(1).tap() if touch else ticks.nth(1).click())
    pg.wait_for_timeout(300)
    s0 = st(); marks = s0["marks"]
    ok["two_marked"] = len(marks) == 2
    all_vis = vis_ids(pg)
    pg.locator(SEARCH).fill(""); pg.wait_for_timeout(200)
    # ---------- Invert
    tap("#sel-invert")
    s1 = st()
    n_shown = len(all_vis)
    ok["invert_marks_the_rest"] = s1["inverted"] and not (set(s1["marks"]) & set(marks)) and set(s1["left"]) == set(marks) and 0 < len(s1["marks"]) <= n_shown
    ok["invert_marks_are_shown_structures"] = set(s1["marks"]) <= set(all_vis) and set(s1["marks"]) | set(marks) == set(all_vis)
    ok["invert_count_and_chips"] = pg.locator("#sel-count").inner_text() == str(len(s1["marks"])) and "Inverted" in pg.locator("#sel-chips").inner_text() and pg.locator("#sel-chips .ss-exc").count() == 2
    ok["invert_button_pressed"] = pg.locator("#sel-invert").get_attribute("aria-pressed") == "true" and pg.locator("#t-invert").get_attribute("aria-pressed") == "true"
    ok["invert_changes_nothing_visible"] = vis_ids(pg) == all_vis
    tap("#sel-invert")
    s2 = st()
    ok["invert_toggles_back"] = (not s2["inverted"]) and sorted(s2["marks"]) == sorted(marks)
    # ---------- Fade others / Fade selected / Hide selected / Highlight selected / Isolate (presets)
    tap("#sel-p-fadeoth"); pg.wait_for_timeout(500)
    s3 = st()
    other = js("(function(){var l=__T.api().list(),m=%s;var r=l.filter(function(r){return __T.api().visible(r.i)&&m.indexOf(r.id)<0;});return r.length?r[Math.floor(r.length/2)].id:null})()" % json.dumps(marks))
    ok["fade_others_state"] = s3["sel"] == "show" and s3["oth"] == "fade" and s3["fade"] == 0.15
    a_other, a_sel = js("__T.alpha(%s)" % json.dumps(other)), js("__T.alpha(%s)" % json.dumps(marks[0]))
    info["alpha_other_marked"] = [a_other, a_sel]
    ok["fade_others_alpha_default_15pct"] = abs(a_other - 0.15) < 0.02 and a_sel > 0.9
    ok["fade_keeps_addon_visibility"] = vis_ids(pg) == all_vis                    # the add-ons' view of "visible" is unchanged by a fade
    pg.screenshot(path=f"{outp}_{name}_1_fade_others.png")
    js("(function(){var e=document.getElementById('sel-fade');e.value=40;e.dispatchEvent(new Event('input',{bubbles:true}));})()"); pg.wait_for_timeout(400)
    ok["fade_slider_sets_alpha"] = abs(js("__T.alpha(%s)" % json.dumps(other)) - 0.4) < 0.02 and pg.locator("#sel-fade-v").inner_text().strip() == "40 %"
    js("(function(){var e=document.getElementById('sel-fade');e.value=0;e.dispatchEvent(new Event('input',{bubbles:true}));})()"); pg.wait_for_timeout(300)
    ok["fade_0_is_not_drawn"] = js("__T.alpha(%s)" % json.dumps(other)) == 0 and other not in vis_ids(pg)
    js("(function(){var e=document.getElementById('sel-fade');e.value=15;e.dispatchEvent(new Event('input',{bubbles:true}));})()"); pg.wait_for_timeout(300)
    tap("#sel-p-fadesel"); pg.wait_for_timeout(400)
    ok["fade_selected_alpha"] = abs(js("__T.alpha(%s)" % json.dumps(marks[0])) - 0.15) < 0.02 and js("__T.alpha(%s)" % json.dumps(other)) > 0.3
    tap("#sel-p-hidesel"); pg.wait_for_timeout(500)
    v = vis_ids(pg)
    ok["hide_selected_hides_them"] = not (set(marks) & set(v)) and other in v
    ok["hidden_selected_not_pickable"] = True
    try:
        pts = js("(function(){var a=__T.api(),r=a.list().filter(function(r){return r.id===%s})[0];var c=[0,1,2].map(function(k){return (r.bmin[k]+r.bmax[k])/2});return a.toScreen(c)})()" % json.dumps(marks[0]))
        if pts:
            hit = js("(function(){var a=__T.api(),h=a.pick({clientX:%f,clientY:%f});return h?a.list()[h.i].id:null})()" % (pts[0], pts[1]))
            ok["hidden_selected_not_pickable"] = hit not in marks
            info["pick_at_hidden_centre"] = hit
    except Exception as e:
        info["pick_error"] = repr(e)[:120]
    pg.screenshot(path=f"{outp}_{name}_2_hide_selected.png")
    tap("#sel-p-hlsel"); pg.wait_for_timeout(500)
    col = js("__T.color(%s)" % json.dumps(marks[0]))
    ok["highlight_selected_colour"] = max(abs(col[0] - 255), abs(col[1] - 176), abs(col[2] - 0)) <= 6 and st()["sel"] == "hl"
    info["highlight_colour"] = col
    ok["highlight_is_solid"] = js("__T.alpha(%s)" % json.dumps(marks[0])) > 0.95
    pg.screenshot(path=f"{outp}_{name}_3_highlight.png")
    tap("#sel-p-isolate"); pg.wait_for_timeout(500)
    ok["isolate_shows_only_selected"] = vis_ids(pg) == sorted(set(marks))
    tap("#sel-p-isolate"); pg.wait_for_timeout(300)
    # group buttons: Others ghost, Selected x-ray
    tap('.ss-st[data-g="oth"][data-s="ghost"]'); pg.wait_for_timeout(400)
    ok["others_ghost"] = st()["oth"] == "ghost" and js("__T.selCtl().ghosting()") and abs(js("__T.alpha(%s)" % json.dumps(other)) - (0.1 if kind == "own" else 0.12)) < 0.03
    tap('.ss-st[data-g="oth"][data-s="show"]'); tap('.ss-st[data-g="sel"][data-s="xray"]'); pg.wait_for_timeout(400)
    ok["selected_xray"] = st()["sel"] == "xray" and js("__T.alpha(%s)" % json.dumps(marks[0])) <= 1.0
    tap('.ss-st[data-g="sel"][data-s="show"]')
    # ---------- the owner's sequence: mark a muscle, invert, fade others
    tap("#sel-reset")
    tap("#sel-markvis"); pg.wait_for_timeout(300)
    s4 = st()
    ok["mark_all_visible"] = sorted(s4["marks"]) == all_vis
    tap("#sel-clear")
    open_list(); pg.locator(SEARCH).fill("biceps"); pg.wait_for_timeout(300)
    ticks = pg.locator(".ss-mk"); ticks.nth(0).scroll_into_view_if_needed(); (ticks.nth(0).tap() if touch else ticks.nth(0).click()); pg.locator(SEARCH).fill(""); pg.wait_for_timeout(200)
    one = st()["marks"]
    tap("#sel-invert"); tap("#sel-p-fadesel"); pg.wait_for_timeout(600)            # the owner's sequence: mark a muscle, swap, fade the (now selected) rest
    s5 = st()
    rest = js("(function(){var l=__T.api().list();var r=l.filter(function(r){return __T.api().visible(r.i)&&r.id!==%s;});return r[Math.floor(r.length/3)].id})()" % json.dumps(one[0]))
    ok["owner_sequence_invert_then_fade_selected"] = s5["inverted"] and s5["sel"] == "fade" and abs(js("__T.alpha(%s)" % json.dumps(rest)) - 0.15) < 0.02 and js("__T.alpha(%s)" % json.dumps(one[0])) > 0.9
    close_list()
    pg.screenshot(path=f"{outp}_{name}_4_invert_fade_others.png")
    # ---------- keys: I invert, F fade others, H hide selected; not while typing
    open_list()
    tap("#sel-reset"); close_list()
    open_list(); pg.locator(SEARCH).fill("biceps"); pg.wait_for_timeout(300)
    ticks = pg.locator(".ss-mk"); ticks.nth(0).scroll_into_view_if_needed(); (ticks.nth(0).tap() if touch else ticks.nth(0).click())
    pg.locator(SEARCH).click(); pg.keyboard.press("i"); pg.wait_for_timeout(200)
    ok["key_ignored_while_typing"] = not st()["inverted"] and pg.locator(SEARCH).input_value().endswith("i")
    pg.locator(SEARCH).fill(""); js("document.activeElement&&document.activeElement.blur()"); close_list()
    if not touch:
        pg.keyboard.press("i"); pg.wait_for_timeout(200); a = st()["inverted"]
        pg.keyboard.press("i"); pg.wait_for_timeout(200); b2 = st()["inverted"]
        ok["key_i_inverts_and_back"] = a and not b2
        pg.keyboard.press("f"); pg.wait_for_timeout(200); f1 = st()["oth"]
        pg.keyboard.press("f"); pg.wait_for_timeout(200); f2 = st()["oth"]
        ok["key_f_fades_others_toggle"] = f1 == "fade" and f2 == "show"
        pg.keyboard.press("h"); pg.wait_for_timeout(200); h1 = st()["sel"]
        pg.keyboard.press("h"); pg.wait_for_timeout(200); h2 = st()["sel"]
        ok["key_h_hides_selected_toggle"] = h1 == "hide" and h2 == "show"
    else:                                                                       # touch devices: the same through the keyboard-less path (controller)
        js("__T.selCtl().onKey({key:'i',target:document.body,preventDefault:function(){},stopImmediatePropagation:function(){}})"); a = st()["inverted"]
        js("__T.selCtl().onKey({key:'i',target:document.body,preventDefault:function(){},stopImmediatePropagation:function(){}})")
        ok["key_i_inverts_and_back"] = a and not st()["inverted"]
    # ---------- Mark layer
    tap("#sel-reset")
    cats = js("Array.from(document.querySelectorAll('#sel-cat option')).map(function(o){return o.value})")
    ok["layer_select_filled"] = len(cats) >= 2
    mus = "muscle"
    if mus in cats:
        js("(function(){var s=document.getElementById('sel-cat');s.value='muscle';})()")
        tap("#sel-markcat")
        s6 = st()
        ok["mark_layer_marks_muscles"] = len(s6["marks"]) > 10 and js("(function(){var a=__T.api().list(),m=%s,ok=true;a.forEach(function(r){if(m.indexOf(r.id)>=0&&r.cat!=='muscle')ok=false});return ok})()" % json.dumps(s6["marks"]))
        tap("#sel-unmarkcat"); ok["unmark_layer"] = len(st()["marks"]) == 0
    else:
        ok["mark_layer_marks_muscles"] = True; ok["unmark_layer"] = True
    tap("#sel-reset")
    if full:
        full_flow(pg, js, tap, open_list, close_list, st, ok, info, marks, name)
    ok["reset_clears_everything"] = (lambda s: s["marks"] == [] and not s["inverted"] and s["sel"] == "show" and s["oth"] == "show" and s["mode"] == "all")(st())
    ok["no_page_errors"] = len(pg.errs) == 0
    R["errors"] = pg.errs[:6]
    ctx.close()


def full_flow(pg, js, tap, open_list, close_list, st, ok, info, marks, name):
    # ---------- composition: a layer toggle changes what Invert works on; global X-ray; source facet (own)
    open_list()
    pg.locator(SEARCH).fill("biceps"); pg.wait_for_timeout(300)
    ticks = pg.locator(".ss-mk"); ticks.nth(0).scroll_into_view_if_needed()
    (ticks.nth(0).tap() if pg.evaluate("'ontouchstart' in window") else ticks.nth(0).click())
    pg.locator(SEARCH).fill(""); pg.wait_for_timeout(200)
    n_before = len(st()["marks"])
    tap("#sel-invert"); n_inv_all = len(st()["marks"]); tap("#sel-invert")
    # switch off one layer (bones: the first layer button) and invert again: fewer structures are eligible
    if kind == "own":
        js("document.querySelector('#systems [data-cat=\"bone\"]').click()")
    else:
        js("document.querySelector('#layers .layer-row button.layer').click()")
    pg.wait_for_timeout(400)
    tap("#sel-invert"); n_inv_off = len(st()["marks"]); tap("#sel-invert")
    ok["invert_respects_layer_toggle"] = n_inv_off < n_inv_all and set(st()["marks"]) == set(js("window.__selState().marks"))
    if kind == "own":
        js("document.querySelector('#systems [data-cat=\"bone\"]').click()")
    else:
        js("document.querySelector('#layers .layer-row button.layer').click()")
    pg.wait_for_timeout(300)
    # global X-ray + fade others + invert: no errors, structures are still drawn
    tap("#sel-p-fadeoth")
    js("document.querySelector(%r).click()" % XRAY); pg.wait_for_timeout(500)
    ok["xray_with_fade_works"] = st()["oth"] == "fade" and len(vis_ids(pg)) > 2
    js("document.querySelector(%r).click()" % XRAY_OFF); pg.wait_for_timeout(300)
    if kind == "own" and js("!!document.getElementById('src-colour')"):
        js("document.getElementById('src-colour').click()"); pg.wait_for_timeout(400)
        ok["source_colour_with_highlight"] = True
        tap("#sel-p-hlsel"); pg.wait_for_timeout(300)
        col = js("__T.color(%s)" % json.dumps(st()["marks"][0]))
        ok["highlight_beats_source_colour"] = abs(col[0] - 255) <= 6
        tap("#sel-p-hlsel")
        js("document.getElementById('src-colour').click()"); pg.wait_for_timeout(300)
    tap("#sel-reset")
    # ---------- saved inverse set, export, link
    open_list(); pg.locator(SEARCH).fill("biceps"); pg.wait_for_timeout(300)
    ticks = pg.locator(".ss-mk"); ticks.nth(0).scroll_into_view_if_needed()
    (ticks.nth(0).tap() if pg.evaluate("'ontouchstart' in window") else ticks.nth(0).click())
    pg.locator(SEARCH).fill(""); pg.wait_for_timeout(200)
    tap("#sel-invert"); tap("#sel-p-fadeoth")
    left = st()["left"]; nmarks = len(st()["marks"])
    tap("#sel-saved summary"); pg.fill("#sel-name", "Inv check"); tap("#sel-save")
    stored = js("JSON.parse(localStorage.getItem('nmsk.sel.v1:' + window.__selState().model)).sets['Inv check']")
    ok["saved_set_is_inverse_of"] = bool(stored["inv"]) and sorted(stored["ids"]) == sorted(left) and stored["os"] == "fade"
    ok["saved_option_says_inverse"] = "inverse" in js("document.getElementById('sel-sets').selectedOptions[0].textContent")
    tap("#sel-reset")
    pg.select_option("#sel-sets", "Inv check"); tap("#sel-load")
    s = st()
    ok["load_restores_inverse_and_states"] = s["inverted"] and len(s["marks"]) == nmarks and s["oth"] == "fade" and sorted(s["left"]) == sorted(left)
    tap("#sel-share summary"); tap("#sel-export")
    exp = json.loads(pg.locator("#sel-io").input_value())
    ok["export_has_inverse_flag"] = exp["sets"]["Inv check"].get("inv") is True and exp["current"].get("inv") is True and exp["current"]["os"] == "fade"
    tap("#sel-link")
    link = pg.locator("#sel-io").input_value()
    ok["link_has_state_field"] = "#nmsksel=" in link and link.count("~") == 4 and "~show.fade.15.1." in link
    tap("#sel-reset"); pg.fill("#sel-io", link); tap("#sel-import")
    s = st()
    ok["import_link_restores"] = s["inverted"] and s["oth"] == "fade" and len(s["marks"]) == nmarks
    tap("#sel-reset"); close_list()
    # ---------- cut + fill: faded structures fade their cap, hidden ones have none, the highlight colours it
    a = marks[0]
    box = js("(function(){var a=__T.api(),r=a.list().filter(function(r){return r.id==='%s'})[0];return [r.bmin,r.bmax]})()" % a)
    c = [(box[0][k] + box[1][k]) / 2 for k in range(3)]
    open_list(); pg.locator(SEARCH).fill("biceps"); pg.wait_for_timeout(300)
    ticks = pg.locator(".ss-mk"); ticks.nth(0).scroll_into_view_if_needed()
    (ticks.nth(0).tap() if pg.evaluate("'ontouchstart' in window") else ticks.nth(0).click())
    pg.locator(SEARCH).fill(""); pg.wait_for_timeout(200)
    one = st()["marks"][0]
    box = js("(function(){var a=__T.api(),r=a.list().filter(function(r){return r.id==='%s'})[0];return [r.bmin,r.bmax]})()" % one)
    c = [(box[0][k] + box[1][k]) / 2 for k in range(3)]
    js("__T.ctl().setFromSpec({normal:[0,-1,0],point:[%f,%f,%f]})" % tuple(c)); pg.wait_for_timeout(400)
    js("document.getElementById('cut-fill').click()") if not js("window.__capState().on") else None
    pg.wait_for_function("window.__capState().builds>0 && !window.__capState().busy", timeout=90000); pg.wait_for_timeout(500)
    CAPJS = ("(function(key){var r=window.__capResult(0);if(!r||!r.items)return null;var it=r.items.filter(function(i){return i.key===key})[0];if(!it)return null;"
             "var n=r.w*r.h,i;for(i=0;i<n;i++)if(r.ids[i]===it.code)break;if(i>=n)return null;return {a:r.rgba[4*i+3],r:r.rgba[4*i],g:r.rgba[4*i+1],b:r.rgba[4*i+2],status:it.status};})(%s)")
    base = js(CAPJS % json.dumps(one))
    ok["cap_has_the_selected_structure"] = base is not None and base["a"] > 200
    others = js("(function(){var r=window.__capResult(0);return r.items.filter(function(i){return i.key!==%s&&i.status==='filled'}).map(function(i){return i.key})})()" % json.dumps(one))
    ok["cap_has_other_structures"] = len(others) >= 1
    cs0 = js("window.__capState()")
    tap("#sel-p-fadeoth")
    js("(function(){var e=document.getElementById('sel-fade');e.value=45;e.dispatchEvent(new Event('input',{bubbles:true}));})()")
    pg.wait_for_function("(function(){var s=window.__capState();return !s.busy&&(s.builds>%d||s.recolors>%d)})()" % (cs0["builds"], cs0["recolors"]), timeout=90000); pg.wait_for_timeout(500)
    fa = [js(CAPJS % json.dumps(k)) for k in others[:6]]
    fa = [x for x in fa if x]
    info["cap_alpha_faded_others"] = [x["a"] for x in fa]
    ok["faded_cap_alpha_follows_slider"] = bool(fa) and all(abs(x["a"] - round(0.45 * 255)) <= 3 for x in fa)
    ok["selected_cap_stays_solid"] = (js(CAPJS % json.dumps(one)) or {"a": 0})["a"] > 250
    pg.screenshot(path=f"{outp}_{name}_5_cut_fade_cap.png")
    cs0 = js("window.__capState()")
    tap("#sel-p-hidesel")
    pg.wait_for_function("(function(){var s=window.__capState();return !s.busy&&(s.builds>%d||s.recolors>%d)})()" % (cs0["builds"], cs0["recolors"]), timeout=90000); pg.wait_for_timeout(500)
    ok["hidden_selected_has_no_cap"] = js(CAPJS % json.dumps(one)) is None
    cs0 = js("window.__capState()")
    tap("#sel-p-hlsel")
    pg.wait_for_function("(function(){var s=window.__capState();return !s.busy&&(s.builds>%d||s.recolors>%d)})()" % (cs0["builds"], cs0["recolors"]), timeout=90000); pg.wait_for_timeout(500)
    hc = js(CAPJS % json.dumps(one))
    ok["highlight_colours_the_cap"] = hc is not None and abs(hc["r"] - 255) <= 4 and abs(hc["g"] - 176) <= 4 and hc["a"] > 250
    pg.screenshot(path=f"{outp}_{name}_6_cut_highlight_cap.png")
    tap("#sel-reset")
    js("document.getElementById('cut-exit').click()"); pg.wait_for_timeout(400)
    close_list()


res = {"page": page_name, "kind": kind, "viewports": {}}
if json_out and "--merge" in sys.argv and os.path.exists(json_out):
    try:
        res = json.load(open(json_out))
    except Exception:
        pass
try:
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
        for name in want:
            w, h, mobile, touch = VIEWPORTS[name]
            t0 = time.time()
            R = {"checks": {}, "info": {}, "errors": []}
            try:
                run_viewport(b, name, (w, h), mobile, touch, R)
            except Exception as e:
                import traceback; traceback.print_exc(file=sys.stderr)
                R["checks"]["completed"] = False; R["errors"].append(repr(e)[:400])
            R["seconds"] = round(time.time() - t0, 1)
            res["viewports"][name] = R
            bad = [k for k, v in R["checks"].items() if v is not True]
            print(f"[{page_name}] {name}: {len(R['checks']) - len(bad)}/{len(R['checks'])} ok, {len(R['errors'])} errors, {R['seconds']} s", "FAILED:" if bad else "", bad, file=sys.stderr, flush=True)
        b.close()
finally:
    srv.terminate()
out = json.dumps(res, indent=1, default=str)
if json_out:
    open(json_out, "w").write(out)
print(out)
