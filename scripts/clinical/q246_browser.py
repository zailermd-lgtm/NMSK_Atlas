#!/usr/bin/env python3
"""Q246 -- real-page check of the imaging + ultrasound continuity changes: headless Chromium (swiftshader) on a BUILT page.

    python3 scripts/clinical/q246_browser.py PAGE_DIR PAGE.html TAG --vp 1366x768 [--shots-dir data/derived/q246] [--json out.json]

Per run (same script on the old page, build/q244/*, and the new one, build/q246/*): CT / MRI come up; timing per view from NMSKImaging.perf() for the first full images, for a plane DRAG
(shift-drag pan = the quick tier-0 preview path, the cost that matters while dragging) and for the pass after release (tier 1), for a 10 mm slab, single view; ultrasound star + sweep timing;
small screenshots (palette PNG, <= 640 px wide) of the panels; page errors = 0."""
from __future__ import annotations

import io
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from q239_host import serve  # noqa: E402
from q239_check import save_small  # noqa: E402

THREE = "/tmp/three_x/package/build/three.min.js"


def run(page_dir, page, tag, vp, shots_dir=None):
    from playwright.sync_api import sync_playwright
    srv, port = serve(page_dir, page=page)
    w, h = map(int, vp.split("x")); mobile = min(w, h) < 520
    R = {"page": page, "tag": tag, "vp": vp, "errors": [], "perf": {}, "us": {}}
    shots = Path(shots_dir) if shots_dir else None
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
            ctx = b.new_context(viewport={"width": w, "height": h}, has_touch=mobile, is_mobile=mobile, device_scale_factor=1)
            pg = ctx.new_page(); pg.set_default_timeout(600000)
            pg.on("pageerror", lambda e: R["errors"].append("pageerror:" + str(e)[:200]))
            pg.on("console", lambda m: R["errors"].append("console:" + m.text[:200]) if m.type == "error" and "GPU stall" not in m.text else None)
            pg.route("**/fonts.g*.com/**", lambda r: r.fulfill(status=200, body="", content_type="text/css"))
            pg.route("**/three*.js", lambda r: r.fulfill(path=THREE, content_type="application/javascript"))
            pg.goto(f"http://127.0.0.1:{port}/{page}")
            pg.wait_for_function("window.NMSKImaging", timeout=600000); pg.wait_for_timeout(2500)
            if pg.evaluate("document.getElementById('btn-spin') && document.getElementById('btn-spin').classList.contains('on')"):
                pg.evaluate("document.getElementById('btn-spin').click()")
            pg.wait_for_function("document.getElementById('t-imaging').title.indexOf('ready (v')>0", timeout=60000)
            R["version"] = pg.evaluate("NMSKImaging.version")

            def shot(name, sel):
                png = pg.screenshot()
                try:
                    bx = pg.locator(sel).first.bounding_box()
                    png = pg.screenshot(clip={"x": max(0, bx["x"]), "y": max(0, bx["y"]), "width": min(w - max(0, bx["x"]), bx["width"]), "height": min(h - max(0, bx["y"]), bx["height"])})
                except Exception as e:                                          # noqa: BLE001
                    R["errors"].append("shot-clip:" + str(e)[:100])
                if shots is not None:
                    save_small(png, shots / f"{tag}_{vp}_{name}.png")

            def idle(extra=500):
                pg.evaluate("NMSKImaging.idle()"); pg.wait_for_timeout(extra)

            def hist_since(n0):
                return pg.evaluate("(n)=>NMSKImaging.perf().history.slice(n).map(function(x){return {view:x.view,ms:x.ms,sub:x.sub,W:x.W,tier:x.tier,ss:x.ss||1}})", n0)

            def nhist():
                return pg.evaluate("NMSKImaging.perf().history.length")

            btn = pg.locator("#t-imaging").first
            (btn.tap() if mobile else btn.click())
            pg.wait_for_function("NMSKImaging.geo() !== null", timeout=900000)
            pg.wait_for_function("(function(){var v=NMSKImaging.views();return Object.keys(v).some(function(k){return v[k].stats&&v[k].stats.tier===1;});})()", timeout=900000)
            pg.evaluate("NMSKImaging.set({modality:'ct',ctWindow:'soft',layout:'mpr',thick:0,slab:'avg'})"); idle(1500)
            n0 = nhist(); pg.evaluate("NMSKImaging.set({P: NMSKImaging.state().P.map(function(x,i){return i===1? x+3 : x})})"); idle(1200)
            R["perf"]["mpr_full_4views_thick0"] = hist_since(n0)
            shot("ct_mpr_thin", "#img-root")
            # ---- drag: shift-drag (pan) over the axial view = quick tier-0 passes, then release = tier 1
            views = pg.locator("#img-root .img-view")
            bx = views.nth(1).bounding_box(); cx, cy = bx["x"] + bx["width"] / 2, bx["y"] + bx["height"] / 2
            n0 = nhist(); t0 = time.time()
            pg.keyboard.down("Shift"); pg.mouse.move(cx, cy); pg.mouse.down()
            for i in range(18):
                pg.mouse.move(cx + 3 * i, cy + 2 * i); pg.wait_for_timeout(60)
            pg.mouse.up(); pg.keyboard.up("Shift")
            R["drag_wall_s"] = round(time.time() - t0, 2)
            pg.wait_for_timeout(200); mid = hist_since(n0); idle(1500); R["perf"]["drag_then_release"] = hist_since(n0)
            R["perf"]["drag_tier0_ms"] = [x["ms"] for x in R["perf"]["drag_then_release"] if x["tier"] == 0]
            R["perf"]["release_tier1_ms"] = [x["ms"] for x in R["perf"]["drag_then_release"] if x["tier"] == 1]
            # ---- slab, single view, MRI, MIP
            for name, patch in (("ct_slab10_avg", {"modality": "ct", "layout": "mpr", "thick": 10, "slab": "avg"}), ("ct_single_slab5", {"layout": "single", "active": "ax", "thick": 5, "slab": "avg"}),
                                ("mri_t1_single", {"modality": "mr", "seq": "t1_se", "layout": "single", "active": "co", "thick": 0}), ("mri_t2_mpr", {"seq": "t2_se", "layout": "mpr", "thick": 0}),
                                ("ct_mip25", {"modality": "ct", "ctWindow": "bone", "layout": "mpr", "thick": 25, "slab": "mip"})):
                n0 = nhist(); pg.evaluate("NMSKImaging.set(%s)" % json.dumps(patch)); idle(1200)
                R["perf"][name] = hist_since(n0); shot(name, "#img-root")
            R["status_line"] = pg.evaluate("(document.querySelector('#img-root .img-status')||{}).textContent")
            pg.evaluate("NMSKImaging.close()"); pg.wait_for_timeout(700)
            # ---- ultrasound
            btn = pg.locator("#t-ultrasound").first
            (btn.tap() if mobile else btn.click())
            pg.evaluate("NMSKUltrasound.ready()"); pg.evaluate("NMSKUltrasound.idle()"); pg.wait_for_timeout(1500)
            for name, patch in (("star_tilt15", {"mode": "star", "probe": "linear", "tilt": 15, "depthCm": 5}), ("sweep9_3mm", {"mode": "sweep", "n": 9, "spacing": 3}), ("sweep5_10mm", {"mode": "sweep", "n": 5, "spacing": 10}),
                                ("star_convex", {"mode": "star", "probe": "convex", "tilt": 10})):
                pg.evaluate("NMSKUltrasound.set(%s)" % json.dumps(patch)); pg.evaluate("NMSKUltrasound.idle()"); pg.wait_for_timeout(900)
                R["us"][name] = pg.evaluate("(function(){var p=NMSKUltrasound.perf().last; return {n:p.n, ms:p.ms, per:p.per};})()"); shot("us_" + name, "#us-root")
            R["us_status"] = pg.evaluate("(document.querySelector('#us-root .us-status')||{}).textContent")
            pg.evaluate("NMSKUltrasound.close()"); pg.wait_for_timeout(400)
            b.close()
    except Exception as e:                                                          # noqa: BLE001
        R["errors"].append("harness:" + str(e)[:300])
    finally:
        srv.shutdown()
    R["ok"] = not R["errors"]
    return R


def main():
    a = list(sys.argv[1:])
    def opt(name, default=None):
        if name in a:
            i = a.index(name); v = a[i + 1]; del a[i:i + 2]; return v
        return default
    vp = opt("--vp", "1366x768"); shots = opt("--shots-dir"); out = opt("--json")
    page_dir, page, tag = a[:3]
    t0 = time.time(); R = run(page_dir, page, tag, vp, shots); R["seconds"] = round(time.time() - t0)
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True); Path(out).write_text(json.dumps(R, indent=1) + "\n")
    print(json.dumps({k: R[k] for k in ("page", "tag", "vp", "ok", "seconds", "errors")}))
    return 0 if R["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
