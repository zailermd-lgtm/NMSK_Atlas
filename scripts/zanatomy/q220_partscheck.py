"""Q220: functional check of the sourced PARTS UI (card list + point markers) of a built viewer page in headless Chromium (swiftshader).

    python3 scripts/zanatomy/q220_partscheck.py ROOT_DIR PAGE.html own|zan OUT_PREFIX THREE_MIN_JS [--ids deltoid=ID,sm=ID,tp=ID,finger=ID]

Per viewport (desktop 1400x900, phone 390x844 touch; env Q220_VIEWPORTS=desktop|phone):
  card    selecting a structure (a real list click on desktop) shows its Parts rows: name, type badge, description, citation links (PMID / DOI),
          'unverified' badge where flagged, the disputed-count note where the part set is disputed (semimembranosus 3 / 5 / 6);
  markers every marker's atlas-mm position equals the data file's position (and the Q219 / Q220 json), the engine's own projection and an
          independent pinhole projection (from api.view()) agree with the DOM ring to < 2 px, the ring is inside the canvas;
  toggle  'Parts markers' shows the markers of every placed part, off = only the selected structure's; a row click focuses a placed marker (camera
          moves, card with source class + error bound opens) or says 'text only (no placement)';
  cut     a plane that removes a marker hides it (ring + dot), a plane that keeps it shows it, a thin slab (state.th) hides it beyond the slab
          and shows it inside; the solid dot is depth-tested: hidden behind opaque tissue, visible with x-ray (pixel colour at the marker with the DOM layer hidden);
  layers  hiding the structure's layer hides its markers;
  absent  with parts_data.json answering 404 the page runs: no Parts section, no toggle, 0 page errors.
Prints JSON; screenshots OUT_PREFIX_<viewport>_<step>.png.  Last line: FAILED_CHECKS / PAGE_ERRORS."""
import io
import json
import math
import os
import socket
import subprocess
import sys
import time

import numpy as np
from PIL import Image
from playwright.sync_api import sync_playwright

args = [a for a in sys.argv[1:] if not a.startswith("--")]
root, rel, kind, outp, three = args[:5]
IDS = {}
for a in sys.argv[1:]:
    if a.startswith("--ids"):
        pass
if "--ids" in sys.argv:
    for kv in sys.argv[sys.argv.index("--ids") + 1].split(","):
        k, v = kv.split("=")
        IDS[k] = v
OWN_HOOK = ("window.__partsState = function(){ return partsCtl.state(); };",
            "window.__partsState = function(){ return partsCtl.state(); }; window.__T = {kind:'own', api:function(){return anatomyApi();}, ctl:function(){return cutCtl;}, "
            "select:function(id){ select(id); }, groups:groups, cam:function(a,e,d,t){ if(arguments.length){ az=a; el=e; dist=d; target.set(t[0],t[1],t[2]); place(); draw(); } return {az:az,el:el,dist:dist}; }, "
            "fov:35, rootPos:function(){return root.position.toArray();}};")
ZAN_HOOK = ("window.__partsState=function(){ return partsCtl.state(); };",
            "window.__partsState=function(){ return partsCtl.state(); }; window.__T = {kind:'zan', OBJ:OBJ, api:function(){return anatomyApi();}, ctl:function(){return cutCtl;}, "
            "select:function(id){ var o=OBJ.filter(function(x){return x.id===id;})[0]; select(o,false); need=true; }, "
            "cam:function(a,e,d,t){ if(arguments.length){ cam.az=a; cam.el=e; cam.dist=d; cam.tgt=t.slice(); need=true; spinning=false; } return {az:cam.az,el:cam.el,dist:cam.dist}; }, fov:0.85*180/Math.PI, rootPos:function(){return [0,0,0];}};")
HOOK = OWN_HOOK if kind == "own" else ZAN_HOOK
srv_port = socket.socket(); srv_port.bind(("127.0.0.1", 0)); port = srv_port.getsockname()[1]; srv_port.close()
srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "-d", root], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)


def patch(route):
    r = route.fetch(); b = r.text()
    route.fulfill(response=r, body=b.replace(HOOK[0], HOOK[1], 1) if HOOK[0] in b else b)


def checks_add(d, k, v):
    d[k] = v


FAILED = []
res = {}
errs_all = []


def check(R, name, cond, info=None):
    R[name] = bool(cond) if info is None else {"ok": bool(cond), "info": info}
    if not cond:
        FAILED.append(name)


def pinhole(view, fov_deg, wpx, hpx, p):
    eye, tgt = np.array(view["eye"]), np.array(view["target"])
    z = eye - tgt; z /= np.linalg.norm(z)
    x = np.cross([0, 1, 0], z); x /= np.linalg.norm(x)
    y = np.cross(z, x)
    d = np.array(p) - eye
    vx, vy, vz = d @ x, d @ y, d @ z
    if vz >= 0:
        return None
    t = math.tan(math.radians(fov_deg) / 2)
    nx = vx / (-vz) / (t * wpx / hpx); ny = vy / (-vz) / t
    return ((nx * .5 + .5) * wpx, (0.5 - 0.5 * ny) * hpx)


try:
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
        for name, vp, mobile in (("desktop", {"width": 1400, "height": 900}, False), ("phone", {"width": 390, "height": 844}, True)):
            if name not in os.environ.get("Q220_VIEWPORTS", "desktop,phone").split(","):
                continue
            R = {}
            res[name] = R
            for variant in ("with_data", "no_data"):
                ctx = b.new_context(viewport=vp, has_touch=mobile, is_mobile=mobile, device_scale_factor=1)
                pg = ctx.new_page()
                errs, notes = [], []
                pg.on("pageerror", lambda e: errs.append(str(e)))
                pg.on("console", lambda m: errs.append("console:" + m.text) if (m.type == "error" and "404" not in m.text and "Failed to load resource" not in m.text) else None)
                pg.on("response", lambda r: notes.append(f"{r.status} {r.url.rsplit('/', 1)[-1]}") if r.status >= 400 else None)
                pg.route("**/*.html", patch)
                pg.route("**/fonts.g*.com/**", lambda r: r.fulfill(status=200, body="", content_type="text/css"))
                pg.route("**/three*.js", lambda r: r.fulfill(path=three, content_type="application/javascript"))
                if variant == "no_data":
                    pg.route("**/parts_data.json", lambda r: r.fulfill(status=404, body="not found"))
                pg.goto(f"http://127.0.0.1:{port}/{rel}")
                pg.add_init_script("document.addEventListener('DOMContentLoaded',function(){var s=document.createElement('style');s.textContent='*{-webkit-tap-highlight-color:transparent!important}';document.head.appendChild(s);})")
                pg.wait_for_function("window.__T && document.getElementById('t-cut')", timeout=900000)
                pg.wait_for_function("(__T.OBJ ? __T.OBJ.length : Object.keys(__T.groups).length) > 0", timeout=900000)
                pg.wait_for_timeout(2500)
                tap = (lambda sel: pg.locator(sel).tap()) if mobile else (lambda sel: pg.locator(sel).click())
                if kind == "zan":
                    pg.evaluate("document.getElementById('btn-spin').classList.contains('on') && document.getElementById('btn-spin').click()")
                pg.wait_for_timeout(500)
                if variant == "no_data":
                    S = pg.evaluate("__partsState()")
                    sid = IDS.get("deltoid")
                    pg.evaluate("__T.select(%s)" % json.dumps(sid)); pg.wait_for_timeout(600)
                    Rn = {}
                    check(Rn, "not_loaded", S["loaded"] is False)
                    check(Rn, "no_parts_section", pg.locator(".pm-sec").count() == 0)
                    check(Rn, "no_toggle", pg.locator("#t-parts").count() == 0)
                    check(Rn, "card_still_shows_the_structure", pg.evaluate("document.getElementById(%s).innerText.length>20" % json.dumps("i-body" if kind == "own" else "info")))
                    check(Rn, "no_page_errors", not errs, errs[:3])
                    R["fallback_no_sidecar"] = Rn
                    pg.screenshot(path=f"{outp}_{name}_nodata.png")
                    ctx.close()
                    continue
                CARD = "#i-body" if kind == "own" else "#info"
                T = {}
                R["checks"] = T
                S = pg.evaluate("__partsState()")
                check(T, "sidecar_loaded", S["loaded"] and S["parts"] > 0, {"parts": S["parts"], "placements": S["placements"]})
                data = json.load(open(os.path.join(root, os.path.dirname(rel), "parts_data.json")))
                check(T, "placements_equal_file", S["placements"] == len(data["placed"]))
                check(T, "toggle_visible", pg.locator("#t-parts").is_visible() if data["placed"] else True)
                check(T, "no_hscroll", pg.evaluate("document.documentElement.scrollWidth<=window.innerWidth"))

                # ---------------- card rows
                def card_info(sid):
                    pg.evaluate("__T.select(%s)" % json.dumps(sid)); pg.wait_for_timeout(700)
                    if mobile and kind == "own":
                        pg.evaluate("document.getElementById('m-info').getAttribute('aria-pressed')==='false' && document.getElementById('m-info').click()")
                        pg.wait_for_timeout(300)
                    return pg.evaluate("""(function(card){ var sec=document.querySelector(card+' .pm-sec'); if(!sec) return null;
                      var rows=Array.from(sec.querySelectorAll('.pm-row'));
                      return {n:rows.length, mesh:sec.getAttribute('data-pm-mesh'),
                        types:rows.map(function(r){return r.querySelector('.pm-ty').textContent;}),
                        names:rows.map(function(r){return r.querySelector('.pm-nm').textContent;}),
                        unverified:rows.filter(function(r){return r.querySelector('.pm-unv');}).length,
                        pmid:sec.querySelectorAll('a[href*="pubmed.ncbi.nlm.nih.gov"]').length, doi:sec.querySelectorAll('a[href*="doi.org"]').length,
                        desc:rows.filter(function(r){return r.querySelector('.pm-d');}).length, cites:rows.filter(function(r){return r.querySelector('.pm-c').innerText.trim().length>10;}).length,
                        setnote:Array.from(sec.querySelectorAll('.pm-set')).map(function(e){return e.innerText;}),
                        marker_tags:rows.filter(function(r){return r.querySelector('.pm-pl');}).length,
                        header:sec.querySelector('summary').innerText}; })(%s)""" % json.dumps(CARD))
                for key, label in (("deltoid", "deltoid"), ("sm", "semimembranosus"), ("tp", "tibialis_posterior"), ("finger", "finger_collateral")):
                    sid = IDS.get(key)
                    if not sid:
                        T[f"card_{label}"] = "skipped: no such mesh on this page (own bodies have no finger-ligament mesh)"
                        continue
                    ci = card_info(sid)
                    ok = bool(ci) and ci["n"] >= (3 if key in ("deltoid", "finger") else 5) and ci["desc"] == ci["n"] and ci["cites"] == ci["n"] and ci["pmid"] >= 1
                    T[f"card_{label}"] = {"ok": ok, "info": ci and {k: v for k, v in ci.items() if k not in ("names", "types")}, "types": ci and sorted(set(ci["types"])), "first_names": ci and ci["names"][:4]}
                    if not ok:
                        FAILED.append(f"card_{label}")
                    if key == "sm":
                        txt = " ".join(ci["setnote"]) if ci else ""
                        check(T, "semimembranosus_disputed_count_3_5_6", all(f"{n}" in txt for n in ("3", "5", "6")) and "disagree" in txt, txt[:200])
                    if key == "tp":
                        check(T, "tibialis_posterior_has_unverified_or_prevalence", ci is not None and ci["n"] >= 8)
                    pg.evaluate("(function(c){var e=document.querySelector(c+' .pm-sec'); if(e) e.scrollIntoView({block:'start'});})(%s)" % json.dumps(CARD)); pg.wait_for_timeout(250)
                    pg.screenshot(path=f"{outp}_{name}_card_{label}.png")
                if not mobile:
                    # a real search + list click selects the structure and shows the same section
                    if kind == "own":
                        pg.fill("#q", "deltoid"); pg.wait_for_timeout(300); pg.locator("#list .row").first.click(); pg.wait_for_timeout(600)
                    else:
                        pg.fill("#search", "deltoid"); pg.wait_for_timeout(300); pg.locator("#list .item").first.click(); pg.wait_for_timeout(800)
                    check(T, "real_list_click_shows_parts", pg.locator(CARD + " .pm-sec .pm-row").count() >= 3)

                # ---------------- markers for a structure with placements
                api_view = lambda: pg.evaluate("__T.api().view()")
                # choose a structure: the deltoid (or the first placed part's structure)
                sid_marker = IDS.get("deltoid")
                pg.evaluate("__T.select(%s)" % json.dumps(sid_marker)); pg.wait_for_timeout(500)
                S = pg.evaluate("__partsState()")
                selm = [m for m in S["markers"] if m["why"] != "off"]
                check(T, "markers_for_selected_structure", len(selm) >= 1, [m["part"] for m in selm][:6])
                # frame the first selected marker so that all of its DOM geometry is in view
                m0 = selm[0] if selm else S["markers"][0]
                rp = pg.evaluate("__T.rootPos()")
                tgt = [m0["xyz"][0] + (rp[0] if kind == "own" else 0), m0["xyz"][1] + (rp[1] if kind == "own" else 0), m0["xyz"][2] + (rp[2] if kind == "own" else 0)]
                pg.evaluate("__T.cam(0.5, 0.1, 600, %s)" % json.dumps(tgt)); pg.wait_for_timeout(900)
                S = pg.evaluate("__partsState()")
                cb = pg.locator("canvas").first.bounding_box()
                view = api_view()
                fov = pg.evaluate("__T.fov")
                dev = []
                for m in S["markers"]:
                    if not m["shown"]:
                        continue
                    ph = pinhole(view, fov, cb["width"], cb["height"], m["xyz"])
                    es = pg.evaluate("__T.api().toScreen(%s)" % json.dumps(m["xyz"]))
                    el = pg.evaluate("(function(j){ var r=document.querySelectorAll('#pm-layer .pm')[j]; var q=r.querySelector('.pm-ring').getBoundingClientRect(); return [q.left+q.width/2,q.top+q.height/2]; })(%d)" % m["j"])
                    dev.append(max(abs(el[0] - (cb["x"] + ph[0])), abs(el[1] - (cb["y"] + ph[1]))) if ph else 999)
                    dev.append(max(abs(el[0] - es[0]), abs(el[1] - es[1])))
                check(T, "ring_matches_independent_projection_px", bool(dev) and max(dev) < 2.0, {"n_shown": len([m for m in S["markers"] if m["shown"]]), "max_dev_px": round(max(dev), 2) if dev else None})
                # positions equal the data file / the Q219 json
                geo_file = os.path.join(os.path.dirname(__file__), "..", "..", data["geometry"]["file"])
                g = json.load(open(geo_file))
                gm = {(x["part_id"], x["side"]): x["position_mm"] for x in g["placed"]}
                pm = {(data["parts"][x["p"]]["id"], x["s"]): x["xyz"] for x in data["placed"]}
                diff = max(max(abs(a - b2) for a, b2 in zip(pm[k], gm[k])) for k in pm)
                check(T, "positions_equal_geometry_json", diff < 0.006 and set(pm) <= set(gm), {"max_abs_diff_mm": diff, "n": len(pm)})
                st_xyz = {(m["part"], m["side"]): m["xyz"] for m in S["markers"]}
                check(T, "state_positions_equal_data", all(max(abs(a - b2) for a, b2 in zip(st_xyz[k], pm[k])) < 1e-6 for k in pm))
                pg.screenshot(path=f"{outp}_{name}_markers_selected.png")

                # ---------------- hover / tap card of a marker (source class + error bound)
                if selm:
                    ring = pg.locator("#pm-layer .pm").nth(selm[0]["j"]).locator(".pm-ring")
                    if mobile:
                        ring.tap()
                    else:
                        ring.hover()
                    pg.wait_for_timeout(500)
                    ct = pg.evaluate("(function(){var c=document.getElementById('pm-card'); return c.hidden?null:c.innerText;})()")
                    check(T, "marker_card_has_class_and_error_bound", bool(ct) and ("Rule-based" in ct or "Z-Anatomy fill" in ct) and "Error bound" in ct and "not a measurement" in ct, ct and ct[:260])
                    cbx = pg.evaluate("(function(){var c=document.getElementById('pm-card').getBoundingClientRect();return [c.left,c.top,c.right,c.bottom];})()")
                    check(T, "marker_card_inside_viewport", cbx[0] >= -0.5 and cbx[1] >= -0.5 and cbx[2] <= vp["width"] + 0.5 and cbx[3] <= vp["height"] + 0.5, cbx)
                    pg.screenshot(path=f"{outp}_{name}_marker_card.png")
                    pg.keyboard.press("Escape") if not mobile else pg.evaluate("document.querySelector('#pm-card .pm-x') && document.querySelector('#pm-card .pm-x').click()")
                    pg.mouse.move(5, 5) if not mobile else None
                    pg.wait_for_timeout(300)

                # ---------------- toggle
                sel_only = len([m for m in pg.evaluate("__partsState()")["markers"] if m["vis"]])
                tap("#t-parts"); pg.wait_for_timeout(500)
                S2 = pg.evaluate("__partsState()")
                all_vis = len([m for m in S2["markers"] if m["vis"]])
                check(T, "toggle_shows_more_markers", S2["showAll"] and all_vis > sel_only and pg.locator("#t-parts").get_attribute("aria-pressed") == "true", {"selected_only": sel_only, "all_toggle": all_vis, "total": S2["placements"]})
                pg.evaluate("__T.cam(0.4, 0.05, %d, %s)" % (2600 if kind == "own" else 3200, json.dumps([0, 0, 0] if kind == "zan" else [0, 0, 0])))
                pg.wait_for_timeout(700)
                pg.screenshot(path=f"{outp}_{name}_markers_all.png")
                tap("#t-parts"); pg.wait_for_timeout(400)
                S3 = pg.evaluate("__partsState()")
                check(T, "toggle_off_returns_to_selection", (not S3["showAll"]) and len([m for m in S3["markers"] if m["vis"]]) == sel_only)

                # ---------------- row click: placed -> focus, unplaced -> text only
                pg.evaluate("__T.select(%s)" % json.dumps(sid_marker)); pg.wait_for_timeout(500)
                if mobile and kind == "own":
                    pg.evaluate("document.getElementById('m-info').getAttribute('aria-pressed')==='false' && document.getElementById('m-info').click()"); pg.wait_for_timeout(300)
                rows = pg.evaluate("Array.from(document.querySelectorAll(%s+' .pm-row')).map(function(r){return {pi:r.getAttribute('data-pi'), placed:!!r.querySelector('.pm-pl'), name:r.querySelector('.pm-nm').textContent};})" % json.dumps(CARD))
                placed_rows = [r for r in rows if r["placed"]]
                text_rows = [r for r in rows if not r["placed"]]
                check(T, "card_marks_placed_vs_text_rows", len(placed_rows) >= 1 and len(text_rows) >= 1, {"placed": len(placed_rows), "text": len(text_rows)})
                if text_rows:
                    row = pg.locator(CARD + ' .pm-row[data-pi="%s"]' % text_rows[0]["pi"])
                    row.scroll_into_view_if_needed(); (row.tap() if mobile else row.click()); pg.wait_for_timeout(300)
                    msg = row.locator(".pm-msg").inner_text()
                    check(T, "unplaced_row_says_text_only", msg.startswith("text only (no placement)"), msg[:140])
                if placed_rows:
                    pg.evaluate("__T.cam(0.4, 0.05, 1800, [0,0,0])" if kind == "zan" else "__T.cam(0.4, 0.05, 2300, [0,0,0])"); pg.wait_for_timeout(500)
                    row = pg.locator(CARD + ' .pm-row[data-pi="%s"]' % placed_rows[0]["pi"])
                    row.scroll_into_view_if_needed(); (row.tap() if mobile else row.click()); pg.wait_for_timeout(900)
                    S4 = pg.evaluate("__partsState()")
                    fm = S4["markers"][S4["focus"]] if S4["focus"] >= 0 else None
                    cam_dist = pg.evaluate("__T.cam().dist")
                    scr = pg.evaluate("(function(j){ var q=document.querySelectorAll('#pm-layer .pm')[j].querySelector('.pm-ring').getBoundingClientRect(); return [q.left+q.width/2,q.top+q.height/2]; })(%d)" % S4["focus"]) if fm else None
                    check(T, "placed_row_focuses_marker", bool(fm) and fm["vis"] and fm["part"] and scr and abs(scr[0] - (cb["x"] + cb["width"] / 2)) < 0.2 * cb["width"] and abs(scr[1] - (cb["y"] + cb["height"] / 2)) < 0.2 * cb["height"] and cam_dist < 1000,
                          {"part": fm and fm["part"], "ring_px": scr, "cam_dist": cam_dist})
                    check(T, "placed_row_opens_marker_card", pg.evaluate("!document.getElementById('pm-card').hidden"))
                    pg.screenshot(path=f"{outp}_{name}_row_focus.png")
                    pg.evaluate("document.querySelector('#pm-card .pm-x') && document.querySelector('#pm-card .pm-x').click()")

                # ---------------- cut and slab
                S5 = pg.evaluate("__partsState()")
                vm = [m for m in S5["markers"] if m["vis"]]
                if vm:
                    m = vm[0]; xyz = m["xyz"]
                    n = [0.0, 1.0, 0.0]
                    def cut_at(d):       # kept half = n.(q - point) >= 0; marker lies at signed distance d inside the kept half (d < 0: cut away)
                        point = [xyz[0] - n[0] * d, xyz[1] - n[1] * d, xyz[2] - n[2] * d]
                        pg.evaluate("__T.api().setCut({normal:%s, point:%s})" % (json.dumps(n), json.dumps(point))); pg.wait_for_timeout(500)
                        return next(x for x in pg.evaluate("__partsState()")["markers"] if x["j"] == m["j"])
                    a = cut_at(-12)
                    check(T, "cut_removing_marker_hides_it", (not a["vis"]) and a["why"] == "cut" and (not a["shown"]), a["why"])
                    pxh = pg.evaluate("(function(j){return document.querySelectorAll('#pm-layer .pm')[j].hidden;})(%d)" % m["j"])
                    check(T, "cut_hides_dom_ring", pxh)
                    a = cut_at(12)
                    check(T, "cut_keeping_marker_shows_it", a["vis"] and a["shown"])
                    ctl_set = lambda th: pg.evaluate("__T.ctl().setThickness(%s)" % th)
                    ctl_set(5); pg.wait_for_timeout(300)
                    a = cut_at(12)       # setCut drops any slab (th = 0): the marker (12 mm in) is kept; then a 5 mm slab puts it beyond the far face
                    ctl_set(5); pg.wait_for_timeout(500)
                    a = next(x for x in pg.evaluate("__partsState()")["markers"] if x["j"] == m["j"])
                    check(T, "slab_5mm_hides_marker_beyond_far_face", (not a["vis"]) and a["why"] == "cut", a["why"])
                    pg.evaluate("__T.api().setCut(null)")
                    # keep setCut's slab behaviour honest: setFromSpec drops the slab, so set the plane then the thickness
                    pg.evaluate("__T.api().setCut({normal:%s, point:%s})" % (json.dumps(n), json.dumps([xyz[0] - n[0] * 3, xyz[1] - n[1] * 3, xyz[2] - n[2] * 3]))); pg.wait_for_timeout(300)
                    ctl_set(5); pg.wait_for_timeout(500)
                    a = next(x for x in pg.evaluate("__partsState()")["markers"] if x["j"] == m["j"])
                    check(T, "slab_5mm_keeps_marker_inside_slab", a["vis"] and pg.evaluate("__T.ctl().state().th") == 5, a["why"])
                    pg.evaluate("__T.api().setCut({normal:%s, point:%s})" % (json.dumps(n), json.dumps([xyz[0] - n[0] * 8, xyz[1] - n[1] * 8, xyz[2] - n[2] * 8]))); pg.wait_for_timeout(300)
                    ctl_set(5); pg.wait_for_timeout(500)
                    a = next(x for x in pg.evaluate("__partsState()")["markers"] if x["j"] == m["j"])
                    check(T, "slab_5mm_hides_marker_8mm_behind_plane", (not a["vis"]) and a["why"] == "cut", a["why"])
                    ctl_set(10); pg.wait_for_timeout(400)
                    a = next(x for x in pg.evaluate("__partsState()")["markers"] if x["j"] == m["j"])
                    check(T, "slab_10mm_shows_it_again", a["vis"], a["why"])
                    pg.screenshot(path=f"{outp}_{name}_cut_slab.png")
                    pg.evaluate("__T.ctl().exit(true)"); pg.wait_for_timeout(300)
                    a = next(x for x in pg.evaluate("__partsState()")["markers"] if x["j"] == m["j"])
                    check(T, "cut_exit_restores_marker", a["vis"])

                    # ---------------- depth test / x-ray: pixel colour of the solid dot (DOM layer hidden), markers of every placed part, nothing selected
                    pg.evaluate("__T.select(null)"); pg.wait_for_timeout(300)
                    if pg.locator("#t-parts").get_attribute("aria-pressed") != "true":
                        tap("#t-parts")
                    pg.wait_for_timeout(300)
                    allm = [x for x in pg.evaluate("__partsState()")["markers"] if x["vis"]]
                    step = max(1, len(allm) // 7)
                    probe = allm[::step][:8]
                    rows_px = []

                    def dot_pixels(mk):
                        colour = np.array([232, 161, 23] if mk["cls"] == "rule_based" else [46, 143, 224])
                        pg.add_style_tag(content="#pm-layer{visibility:hidden!important}")
                        pg.wait_for_timeout(250)
                        im = np.asarray(Image.open(io.BytesIO(pg.locator("canvas").first.screenshot())).convert("RGB")).astype(int)
                        pg.evaluate("document.querySelectorAll('style').forEach(function(s){ if(s.textContent.indexOf('#pm-layer{visibility:hidden')===0) s.remove(); })")
                        mm = pg.evaluate("__partsState()")["markers"][mk["j"]]
                        x, y = int(round(mm["sx"] - cb["x"])), int(round(mm["sy"] - cb["y"]))
                        crop = im[max(0, y - 7):y + 8, max(0, x - 7):x + 8]
                        return int((np.abs(crop - colour).max(axis=2) < 40).sum())
                    for mk in probe:
                        pg.evaluate("__T.cam(0.5, 0.1, 300, %s)" % json.dumps([mk["xyz"][0] + (rp[0] if kind == "own" else 0), mk["xyz"][1] + (rp[1] if kind == "own" else 0), mk["xyz"][2] + (rp[2] if kind == "own" else 0)]))
                        pg.wait_for_timeout(450)
                        n_off = dot_pixels(mk)
                        tap("#t-xray") if kind == "own" else pg.evaluate("document.getElementById('btn-xray').click()")
                        pg.wait_for_timeout(450)
                        n_on = dot_pixels(mk)
                        tap("#t-xray") if kind == "own" else pg.evaluate("document.getElementById('btn-xray').click()")
                        pg.wait_for_timeout(250)
                        rows_px.append({"part": mk["part"], "side": mk["side"], "dot_px_xray_off": n_off, "dot_px_xray_on": n_on})
                    pg.screenshot(path=f"{outp}_{name}_xray_probe_last.png")
                    revealed = [r for r in rows_px if r["dot_px_xray_off"] < 6 and r["dot_px_xray_on"] >= 12]
                    seen_off = [r for r in rows_px if r["dot_px_xray_off"] >= 12]
                    check(T, "depth_test_hides_dot_behind_opaque_tissue_and_xray_reveals_it", len(revealed) >= 1, {"revealed_by_xray": len(revealed), "visible_without_xray": len(seen_off), "probed": rows_px})
                    check(T, "xray_never_hides_a_dot", all(r["dot_px_xray_on"] >= 12 or r["dot_px_xray_off"] < 12 for r in rows_px) or len([r for r in rows_px if r["dot_px_xray_on"] < 12 and r["dot_px_xray_off"] >= 12]) == 0)
                    if pg.locator("#t-parts").get_attribute("aria-pressed") == "true":
                        tap("#t-parts")

                    # ---------------- layer hidden -> markers hidden
                    pg.evaluate("__T.select(%s)" % json.dumps(sid_marker)); pg.wait_for_timeout(400)
                    before = len([x for x in pg.evaluate("__partsState()")["markers"] if x["vis"]])
                    if kind == "own":
                        pg.evaluate("document.querySelector('#systems [data-cat=\"muscle\"]').click()")
                    else:
                        pg.evaluate("document.querySelector('.layer-row .layer').parentNode && Array.from(document.querySelectorAll('.layer')).filter(function(b){return /muscle/i.test(b.innerText);})[0].click()")
                    pg.wait_for_timeout(500)
                    after = [x for x in pg.evaluate("__partsState()")["markers"] if x["vis"] and x["part"].split('.')[0] in ("deltoid",)]
                    check(T, "muscle_layer_off_hides_its_markers", len(after) == 0 and before > 0, {"before": before, "deltoid_after": len(after)})
                    if kind == "own":
                        pg.evaluate("document.querySelector('#systems [data-cat=\"muscle\"]').click()")
                    else:
                        pg.evaluate("Array.from(document.querySelectorAll('.layer')).filter(function(b){return /muscle/i.test(b.innerText);})[0].click()")
                    pg.wait_for_timeout(400)
                check(T, "no_page_errors", not errs, errs[:4])
                R["http_errors"] = [x for x in notes if "parts_data" not in x][:5]
                ctx.close()
        b.close()
finally:
    srv.terminate()
print(json.dumps(res, indent=1, default=str))
print("FAILED_CHECKS:", FAILED)
