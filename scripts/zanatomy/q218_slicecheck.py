"""Q218: functional check of the Cut-mode SLICE THICKNESS of a built viewer page in headless Chromium (swiftshader), desktop + phone.

    python3 scripts/zanatomy/q218_slicecheck.py ROOT_DIR PAGE.html own|zan OUT_PREFIX THREE_MIN_JS

Axial (Y) plane through the model centre, camera level with the plane (front view, zoomed on the torso) so the slab 0 <= a - y <= th is a
horizontal band on the screen. Per viewport it checks, with the cut on:
  (a) RENDERED geometry: the canvas with the slab differs from an empty-scene reference only inside the projected band of the slab
      (+- 4 px), never beyond it; there is something inside the band; a thicker slab widens it; moving the plane moves it; flipping
      the side puts the slab on the other side; the picture with thickness "all" equals the picture before any slab (the previous
      state is restored, < 0.2 % of the pixels); engine-side tests: own = every mesh carries the 2-plane array and a vertex test with
      the engine's own planes keeps exactly the slab; Z = the AABB cull passes exactly the objects whose box meets the slab.
  (b) PICKING: api.pick() over a grid outside the band hits nothing with the slab (and does hit with thickness "all"); looking
      straight down onto the plane, every picked structure's box meets the slab; a real mouse click / tap outside the band selects nothing.
  (c) UI: preset buttons / slider / readout / aria-pressed / far-face outline in the overlay, reset and exit, the add-on's "Cut through
      target" (when staged next to the page) drops the slab, the panel stays inside the viewport, and no page error.
Prints JSON; screenshots OUT_PREFIX_<viewport>_<step>.png. Last line: FAILED_CHECKS / PAGE_ERRORS."""
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
OWN_HOOK = ("var cutCtl = null;", "var cutCtl = null; window.__T = {ctl:function(){return cutCtl;}, meshes:meshes, api:function(){return anatomyApi();}, "
            "planes:function(){return [cutWorld, cutWorld2];}, rootPos:function(){return root.position.toArray();}, "
            "cam:function(a,e,d,t){ if(arguments.length){ az=a; el=e; dist=d; target.set(t[0],t[1],t[2]); place(); draw(); } return {az:az,el:el,dist:dist}; }, "
            "project:function(p){ var v=new THREE.Vector3(p[0]+root.position.x,p[1]+root.position.y,p[2]+root.position.z).project(camera); var r=renderer.domElement.getBoundingClientRect(); return [(v.x+1)/2*r.width,(1-v.y)/2*r.height]; }, "
            "hideAll:function(h){ meshes.forEach(function(m){ if(h){ m.userData.__v=m.visible; m.visible=false; } else m.visible=m.userData.__v!==false; }); draw(); }};")
ZAN_HOOK = ("searchEl.oninput=renderList; renderList();",
            "searchEl.oninput=renderList; renderList(); window.__T = {OBJ:OBJ, cam:function(a,e,d,t){ if(arguments.length){ cam.az=a; cam.el=e; cam.dist=d; cam.tgt=t.slice(); need=true; } return {az:cam.az,el:cam.el,dist:cam.dist}; }, "
            "ctl:function(){return cutCtl;}, api:function(){return anatomyApi();}, need:function(){need=true;}, clip:clip, passClip:passClip, "
            "project:function(p){ var s=proj(p); return s?[s.x/dpr, s.y/dpr]:null; }, "
            "hideAll:function(h){ if(h) clip.P2 = [0,0,0,1]; else cutCtl.setThickness(cutCtl.state().th); need=true; }};")
HOOK = OWN_HOOK if kind == "own" else ZAN_HOOK
s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "-d", root], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)


def patch(route):
    r = route.fetch(); b = r.text()
    route.fulfill(response=r, body=b.replace(HOOK[0], HOOK[1], 1) if HOOK[0] in b else b)


HIDE = "#cut-svg,#cut-panel{visibility:hidden!important}"


def img(pg, sel="canvas"):
    pg.add_style_tag(content=HIDE)
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
            if kind == "zan":
                pg.evaluate("document.getElementById('btn-spin').classList.contains('on') && document.getElementById('btn-spin').click()")
            pg.wait_for_timeout(400)
            tap("#t-cut"); pg.wait_for_timeout(300)
            tap('#cut-axis [data-axis="y"]'); pg.wait_for_timeout(300)
            s0 = st(pg)
            ok["panel_visible"] = pg.locator("#cut-panel").is_visible() and s0["on"] and s0["ori"] == "y" and s0["th"] == 0
            box = pg.locator("#cut-panel").bounding_box()
            ok["panel_in_viewport"] = bool(box and box["x"] >= -0.5 and box["y"] >= -0.5 and box["x"] + box["width"] <= vp["width"] + 0.5 and box["y"] + box["height"] <= vp["height"] + 0.5)
            ok["panel_height_px"] = round(box["height"]) if box else None
            ok["thickness_controls_visible"] = all(pg.locator(sel).is_visible() for sel in ("#cut-thsl", "#cut-thick", "#cut-th"))
            ok["no_hscroll"] = pg.evaluate("document.documentElement.scrollWidth<=window.innerWidth")
            ok["min_thick_button_height"] = pg.evaluate("Math.min.apply(null,Array.from(document.querySelectorAll('#cut-thick button')).filter(function(b){return b.offsetParent}).map(function(b){return b.getBoundingClientRect().height}))")
            ok["default_readout"] = pg.locator("#cut-th").inner_text()
            ok["default_slider_at_far_end"] = pg.evaluate("(function(){var e=document.getElementById('cut-thsl');return +e.value===+e.max})()")
            ok["no_far_face_outline_by_default"] = pg.locator("#cut-svg .cut-back").count() == 0
            ok["all_button_pressed_by_default"] = pg.locator('#cut-thick [data-th="0"]').get_attribute("aria-pressed") == "true"

            # ---- camera: level with the plane, front view, zoomed on the torso
            a = s0["a"]; anc = s0["anchor"]
            rp = pg.evaluate("__T.rootPos ? __T.rootPos() : [0,0,0]")
            tgt = [anc[0] + rp[0], a + rp[1], anc[2] + rp[2]] if kind == "own" else [anc[0], a, anc[2]]
            D = 520
            pg.evaluate("(function(t){ __T.cam(0, 0, %d, t); })(%s)" % (D, json.dumps(tgt)))
            pg.wait_for_timeout(500)
            cb = pg.locator("canvas").first.bounding_box()
            H = int(cb["height"]); W = int(cb["width"])

            def band(th, aa):
                """screen rows (canvas-relative) spanned by the slab 0 <= aa - y <= th over a body-sized footprint"""
                rows = []
                for y in (aa, aa - th):
                    for x in (-260, 260):
                        for z in (-220, 220):
                            q = pg.evaluate("__T.project(%s)" % json.dumps([anc[0] + x, y, anc[2] + z]))
                            if q: rows.append(q[1])
                return min(rows), max(rows)

            def empty_ref():
                pg.evaluate("__T.hideAll(true)"); pg.wait_for_timeout(400)
                e = img(pg)
                pg.evaluate("__T.hideAll(false)"); pg.wait_for_timeout(400)
                return e

            base_cut = img(pg)                                   # cut on (plane only, thickness all): the "previous state"
            pg.screenshot(path=f"{outp}_{name}_0_cut_all.png")
            ref = empty_ref()
            ok["scene_content_frac"] = round(changed(base_cut, ref), 4)
            ok["scene_has_content"] = ok["scene_content_frac"] > 0.01

            def outside_rows(im, lo, hi, margin=4):
                d = (np.abs(im - ref).sum(axis=2) > 24)
                rows = d.sum(axis=1)
                inside = int(rows[max(0, int(lo) - margin):min(H, int(hi) + margin + 1)].sum())
                return inside, int(rows.sum()) - inside

            # ---- 5 mm preset
            tap('#cut-thick [data-th="5"]'); pg.wait_for_timeout(500)
            s5 = st(pg)
            ok["preset_5_state"] = s5["th"] == 5 and abs(s5["a"] - a) < 1e-9
            ok["readout_5"] = pg.locator("#cut-th").inner_text()
            ok["preset_5_pressed"] = pg.locator('#cut-thick [data-th="5"]').get_attribute("aria-pressed") == "true" and pg.locator('#cut-thick [data-th="0"]').get_attribute("aria-pressed") == "false"
            ok["far_face_outline_drawn"] = pg.locator("#cut-svg .cut-back").count() == 1
            ok["slider_value_5"] = abs(float(pg.evaluate("document.getElementById('cut-thsl').value")) - 5) < 1e-6
            pg.screenshot(path=f"{outp}_{name}_1_slice5.png")
            im5 = img(pg)
            lo, hi = band(5, a)
            ins, out = outside_rows(im5, lo, hi)
            ok["band5_rows"] = [round(lo, 1), round(hi, 1)]
            ok["slice5_changed_px_inside_band"] = ins
            ok["slice5_changed_px_outside_band"] = out
            ok["slice5_renders_only_the_slab"] = ins > 0 and out == 0
            ok["slice5_clearly_smaller_than_all"] = changed(im5, base_cut) > 0.02

            # engine-side evidence
            if kind == "own":
                e5 = pg.evaluate("""(function(){ var P=__T.planes(), rp=__T.rootPos(), n=0, keep=0, inSlab=0, bad=0, ok2=true;
                  __T.meshes.forEach(function(m){ var cp=m.material.clippingPlanes; if(!cp || cp.length!==2 || cp[0]!==P[0] || cp[1]!==P[1]) ok2=false;
                    var pos=m.geometry.attributes.position.array; for(var i=0;i<pos.length;i+=3*7){ n++;
                      var v=new THREE.Vector3(pos[i]+rp[0], pos[i+1]+rp[1], pos[i+2]+rp[2]);
                      var k=P[0].distanceToPoint(v)>=0 && P[1].distanceToPoint(v)>=0; var d=%f-pos[i+1]; var slab=d>=0 && d<=5;
                      if(k) keep++; if(k!==slab) bad++; if(slab) inSlab++; } });
                  return {all_meshes_two_planes:ok2, sampled:n, kept:keep, expected_in_slab:inSlab, mismatches:bad}; })()""" % a)
                ok["engine_vertex_test_own"] = e5
                ok["engine_vertex_test_ok"] = e5["all_meshes_two_planes"] and e5["mismatches"] == 0 and e5["kept"] > 0
            else:
                e5 = pg.evaluate("""(function(){ var n=0, pass=0, exp=0, bad=0; __T.OBJ.forEach(function(o){ n++; var p=__T.passClip(o);
                    var inter = o.bmax[1] >= %f-5 && o.bmin[1] <= %f; if(p) pass++; if(inter) exp++; if(p!==inter) bad++; });
                  return {objects:n, pass_clip:pass, expected_box_meets_slab:exp, mismatches:bad}; })()""" % (a, a))
                ok["engine_cull_test_zan"] = e5
                ok["engine_cull_test_ok"] = e5["mismatches"] == 0 and 0 < e5["pass_clip"] < e5["objects"]

            # ---- (b) picking
            def grid_hits(lo_, hi_, margin=8):
                pts = [(x, y) for y in range(20, H - 20, 38) for x in range(20, W - 20, 38)]
                outs = [(x, y) for (x, y) in pts if y < lo_ - margin or y > hi_ + margin]
                ins_ = [(x, y) for (x, y) in pts if lo_ <= y <= hi_]
                f = "(function(P){ var a=__T.api(), r=[]; P.forEach(function(q){ var h=a.pick({clientX:%f+q[0], clientY:%f+q[1]}); r.push(h?1:0); }); return r; })" % (cb["x"], cb["y"])
                ho = sum(pg.evaluate(f + "(%s)" % json.dumps(outs)))
                hn = sum(pg.evaluate(f + "(%s)" % json.dumps(ins_))) if ins_ else 0
                return len(outs), ho, len(ins_), hn

            pg.wait_for_timeout(300)
            n_out, h_out, n_in, h_in = grid_hits(lo, hi)
            ok["pick_slice5_outside_band"] = {"points": n_out, "hits": h_out}
            ok["pick_slice5_beyond_slab_picks_nothing"] = h_out == 0
            ok["pick_slice5_inside_band"] = {"points": n_in, "hits": h_in}
            sel = "document.querySelector('#insp-head h2') ? document.querySelector('#insp-head h2').textContent : (document.getElementById('info')||{}).className"
            sel0 = pg.evaluate(sel)
            cx_ = cb["x"] + W / 2; cy_ = cb["y"] + (hi + 60 if hi + 60 < H - 5 else lo - 60)
            if mobile: pg.touchscreen.tap(cx_, cy_)
            else: pg.mouse.click(cx_, cy_)
            pg.wait_for_timeout(500)
            ok["click_beyond_slab_selects_nothing"] = pg.evaluate(sel) == sel0 and st(pg)["on"]

            # thicker slab -> wider band, still contained
            pg.evaluate("(function(){var e=document.getElementById('cut-thsl');e.value='25';e.dispatchEvent(new Event('input',{bubbles:true}))})()")
            pg.wait_for_timeout(500)
            s25 = st(pg)
            ok["slider_25"] = s25["th"] == 25 and pg.locator("#cut-th").inner_text() == "25.0 mm slice"
            lo25, hi25 = band(25, a)
            im25 = img(pg)
            ins25, out25 = outside_rows(im25, lo25, hi25)
            ok["slice25_renders_only_the_slab"] = ins25 > ins and out25 == 0
            n_out25, h_out25, n_in25, h_in25 = grid_hits(lo25, hi25)
            ok["pick_slice25"] = {"outside_hits": h_out25, "inside_hits": h_in25, "inside_points": n_in25}
            ok["pick_slice25_ok"] = h_out25 == 0 and h_in25 > 0
            pg.screenshot(path=f"{outp}_{name}_2_slice25.png")

            # move the plane 40 mm down with the slab on: the band moves with it
            tap('#cut-thick [data-th="10"]')
            for _ in range(4): tap('#cut-steps [data-step="-10"]')
            pg.wait_for_timeout(500)
            sm = st(pg)
            lom, him = band(10, sm["a"])
            insm, outm = outside_rows(img(pg), lom, him)
            ok["moved_plane_band_follows"] = abs(sm["a"] - (a - 40)) < 1e-6 and insm > 0 and outm == 0 and abs(lom - lo) > 5
            pg.screenshot(path=f"{outp}_{name}_3_moved.png")
            for _ in range(4): tap('#cut-steps [data-step="10"]')

            # flip the side: the slab goes to the other side of the plane (kept 0 <= y - a <= th)
            tap("#cut-flip"); pg.wait_for_timeout(500)
            sf = st(pg)
            lof, hif = band(10, a + 10)
            insf, outf = outside_rows(img(pg), lof, hif)
            ok["flipped_slab_other_side"] = sf["rs"] == -1 and sf["th"] == 10 and insf > 0 and outf == 0
            tap("#cut-flip"); pg.wait_for_timeout(300)

            # ---- 'all' restores the previous picture
            tap('#cut-thick [data-th="0"]'); pg.wait_for_timeout(600)
            sa = st(pg)
            im_all = img(pg)
            ok["all_state"] = sa["th"] == 0 and pg.locator("#cut-th").inner_text() == "whole rest of body"
            ok["all_restores_previous_picture_changed_frac"] = round(changed(im_all, base_cut), 5)
            ok["all_restores_previous_picture"] = changed(im_all, base_cut) < 0.002
            ok["all_removes_far_face_outline"] = pg.locator("#cut-svg .cut-back").count() == 0
            ok["slider_back_at_far_end"] = pg.evaluate("(function(){var e=document.getElementById('cut-thsl');return +e.value===+e.max})()")
            n_o2, h_o2, _, _ = grid_hits(lo, hi)
            ok["pick_all_outside_band"] = {"points": n_o2, "hits": h_o2}
            ok["pick_all_hits_beyond_the_old_slab"] = h_o2 > 0
            pg.screenshot(path=f"{outp}_{name}_4_all.png")

            # ---- looking straight down onto the plane: every picked structure meets the slab
            tap('#cut-thick [data-th="5"]'); pg.wait_for_timeout(300)
            pg.evaluate("(function(t){ __T.cam(0, 1.5, %d, t); })(%s)" % (D, json.dumps(tgt)))
            pg.wait_for_timeout(600)
            picks = pg.evaluate("""(function(){ var a=__T.api(), L=a.list(), r=[]; var c=document.querySelector('canvas').getBoundingClientRect();
               for (var i=0;i<9;i++) for (var j=0;j<9;j++){ var h=a.pick({clientX:c.left+c.width*(0.2+0.075*i), clientY:c.top+c.height*(0.2+0.075*j)}); if(h && h.i>=0) r.push(h.i); }
               var bad=0; r.forEach(function(i){ var q=L[i]; if (!(q.bmax[1] >= %f-5 && q.bmin[1] <= %f)) bad++; }); return {n:r.length, bad:bad}; })()""" % (a, a))
            ok["top_down_picks"] = picks
            ok["top_down_picks_only_in_slab"] = picks["n"] > 0 and picks["bad"] == 0
            pg.screenshot(path=f"{outp}_{name}_5_top_down_slice5.png")
            pg.evaluate("(function(t){ __T.cam(0, 0, %d, t); })(%s)" % (D, json.dumps(tgt)))
            pg.wait_for_timeout(400)

            # ---- place-on-model with a slab: the slab is kept
            tap("#cut-place"); pg.wait_for_timeout(200)
            px, py = cb["x"] + W / 2, cb["y"] + (lo + hi) / 2
            if mobile: pg.touchscreen.tap(px, py)
            else: pg.mouse.click(px, py)
            pg.wait_for_timeout(600)
            sp_ = st(pg)
            ok["place_with_slab_keeps_slab"] = sp_["th"] == 5
            ok["place_with_slab_placed_or_armed"] = bool(sp_["placed"] or sp_["armed"])

            # ---- add-on contract with a slab
            api = pg.evaluate("(function(){var a=__T.api(),s=__T.ctl().state();return {cut:a.cut(),kn:s.kn,cc:s.c,slab:a.cutSlab?a.cutSlab():null,th:s.th}})()")
            ok["api_cut_is_still_the_kept_half"] = bool(api["cut"]) and all(abs(api["cut"][i] - api["kn"][i]) < 1e-6 for i in range(3)) and abs(api["cut"][3] - api["cc"]) < 1e-3
            ok["api_cutSlab"] = api["slab"] == api["th"] == 5
            if pg.locator("#t-needle").count():
                pg.evaluate("document.getElementById('t-needle').click()"); pg.wait_for_timeout(500)
                ok["needle_panel_present"] = True
                if pg.locator("#ncl-cuthere").count():
                    pg.evaluate("document.getElementById('ncl-cuthere').click()"); pg.wait_for_timeout(500)
                    sn = st(pg)
                    ok["needle_cut_through_target_drops_slab"] = bool(sn["on"] and sn["ori"] == "view" and sn["th"] == 0 and pg.evaluate("__T.api().cutSlab()") == 0)
                    pg.screenshot(path=f"{outp}_{name}_6_needle_cut.png")
            else:
                ok["needle_panel_present"] = False
            if not st(pg)["on"]: tap("#t-cut")

            # ---- reset / exit
            tap('#cut-thick [data-th="5"]'); tap("#cut-reset"); sr = st(pg)
            ok["reset_clears_slab"] = sr["th"] == 0 and sr["on"] and pg.locator("#cut-svg .cut-back").count() == 0
            tap('#cut-thick [data-th="2"]'); tap("#cut-exit"); sx = st(pg)
            ok["exit_cut"] = bool(not sx["on"] and pg.evaluate("__T.api().cut()") is None and pg.evaluate("__T.api().cutSlab()") == 0)
            pg.wait_for_timeout(500)
            ok["exit_with_slab_set_shows_whole_scene"] = changed(img(pg), ref) > 0.01
            tap("#t-cut"); pg.wait_for_timeout(400)
            ok["re_enter_keeps_value"] = st(pg)["th"] == 2 and pg.locator("#cut-th").inner_text() == "2.0 mm slice"
            pg.screenshot(path=f"{outp}_{name}_7_reenter.png")
            R["errors"] = errs; R["http_ge_400"] = sorted(set(notes))
            res[name] = R
            ctx.close()
        b.close()
finally:
    srv.terminate()
print(json.dumps(res, indent=1))
fails = [f"{v}:{k}" for v, R in res.items() for k, x in R["checks"].items() if x is False]
print("FAILED_CHECKS:", fails, "PAGE_ERRORS:", sum(len(R["errors"]) for R in res.values()))
