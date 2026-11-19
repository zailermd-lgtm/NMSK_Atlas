#!/usr/bin/env python3
"""Q237: headless Chromium (swiftshader) check of the six Q237 pages: desktop 1400x900 + phone 390x844: page / console errors, horizontal scroll, the Symmetric-view control (ready, three choices, banner,
counts), CUT mode + Symmetric view in BOTH engines (the mirrored copy is clipped like everything else: with the default sagittal cut removing the right half, 'mirror left onto right' must look like 'off'),
and screenshots (symmetric view; a filled structure).
    python3 scripts/anatomy/q237/pagecheck.py THREE_MIN_JS OUT.json [OUT_PNG_DIR] [page_dir:html:KEY ...]   (default: the six build/q237 pages)"""
import json, socket, subprocess, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright
REPO = Path(__file__).resolve().parents[3]
three, outp = sys.argv[1:3]
png = Path(sys.argv[3]) if len(sys.argv) > 3 else REPO / "data/derived"
specs = [x for x in sys.argv[4:] if x != "--fresh"] or ["build/q237/viewer_m_hr:atlas_viewer_male.html:own_m", "build/q237/viewer_f_hr:atlas_viewer_female.html:own_f", "build/q237/viewer_zan_atlas:atlas_viewer_zan_atlas.html:base_m",
                         "build/q237/viewer_base_female:atlas_viewer_base_female.html:base_f", "build/q237/viewer_zan_vhm:atlas_viewer_zan_male_fitted.html:comb_m", "build/q237/viewer_zan_female:atlas_viewer_zan_female.html:comb_f"]
NAMES = {"own_m": "Imaging-based male", "own_f": "Imaging-based female", "base_m": "Base male", "base_f": "Base female", "comb_m": "Combined male", "comb_f": "Combined female"}


def diff_frac(a, b):
    from PIL import Image, ImageChops
    import io
    A = Image.open(io.BytesIO(a)).convert("L"); B = Image.open(io.BytesIO(b)).convert("L")
    d = ImageChops.difference(A, B)
    h = d.histogram()
    n = sum(h[24:])
    return n / (A.size[0] * A.size[1])


res = json.loads(Path(outp).read_text()) if Path(outp).exists() and "--fresh" not in sys.argv else {}
with sync_playwright() as p:
    for spec in specs:
        b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"], executable_path="/opt/pw-browsers/chromium")       # one browser per page (the big Z pages exhaust a long-lived swiftshader process)
        d, rel, key = spec.split(":")
        s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
        srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "-d", str(REPO / d)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1)
        r = {}
        try:
            for name, vp, touch in (("desktop", dict(width=1400, height=900), False), ("phone", dict(width=390, height=844), True)):
                ctx = b.new_context(viewport=vp, has_touch=touch, is_mobile=touch)
                pg = ctx.new_page(); errs = []
                pg.on("pageerror", lambda e: errs.append("pageerror:" + str(e)))
                pg.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" else None)
                def route(rq):
                    u = rq.request.url
                    if "three" in u and ("cdnjs" in u or "jsdelivr" in u or "unpkg" in u): rq.fulfill(body=open(three, "rb").read(), content_type="application/javascript")
                    elif "fonts.g" in u: rq.abort()
                    else: rq.continue_()
                pg.route("**/*", route)
                pg.goto(f"http://127.0.0.1:{port}/{rel}", wait_until="load")
                try: pg.wait_for_selector("#sym-select", timeout=60000)
                except Exception: pass
                time.sleep(3)
                info = dict(title=pg.title(), scrollW=pg.evaluate("document.documentElement.scrollWidth"), innerW=pg.evaluate("window.innerWidth"),
                            sym_select=bool(pg.evaluate("!!document.getElementById('sym-select')")), state=pg.evaluate("window.__symState ? window.__symState() : null"))
                if info["sym_select"]:
                    info["options"] = pg.evaluate("Array.from(document.getElementById('sym-select').options).map(o => o.textContent)")
                    box = pg.evaluate("(function(){var r=document.getElementById('sym-select').getBoundingClientRect();return [r.left,r.top,r.right,r.bottom];})()")
                    info["select_in_viewport"] = bool(box[0] >= -1 and box[2] <= vp["width"] + 1 and box[1] >= -1 and box[3] <= vp["height"] + 1)
                    modes = {}
                    for m in ("r", "l"):
                        pg.select_option("#sym-select", m); time.sleep(2.0)
                        modes[m] = dict(state=pg.evaluate("window.__symState()"), banner=bool(pg.evaluate("!document.getElementById('sym-banner').hidden")), banner_text=pg.evaluate("document.getElementById('sym-banner').innerText")[:160], debug=pg.evaluate("window.__symDebug()"))
                        if name == "desktop":
                            pg.screenshot(path=str(png / f"Q237_render_{key}_symmetric_mirror_{'right_onto_left' if m == 'r' else 'left_onto_right'}.png"))
                    pg.select_option("#sym-select", "off"); time.sleep(1.0)
                    modes["off"] = dict(state=pg.evaluate("window.__symState()"), banner=bool(pg.evaluate("!document.getElementById('sym-banner').hidden")))
                    info["modes"] = modes
                    pg.evaluate("() => { var bs = document.querySelectorAll('button.pill'); for (var i = 0; i < bs.length; i++){ if (bs[i].textContent.trim() === 'spin' && bs[i].classList.contains('on')) bs[i].click(); } }")      # Z pages turn by themselves: stop it for the pixel comparison
                    time.sleep(1.0)
                    if name == "desktop":
                        # CUT mode + Symmetric view: default sagittal cut removes the +X (right) half
                        pg.click("#t-cut"); time.sleep(2.5)
                        clip = dict(x=430, y=200, width=370, height=500)          # the model, without the toolbar, the banner and the side panels (they differ between the states by design)
                        a_off = pg.screenshot(clip=clip)
                        pg.select_option("#sym-select", "l"); time.sleep(2.5)
                        a_l = pg.screenshot(clip=clip); dbg_l = pg.evaluate("window.__symDebug()")
                        pg.select_option("#sym-select", "r"); time.sleep(2.5)
                        a_r = pg.screenshot(clip=clip); dbg_r = pg.evaluate("window.__symDebug()")
                        pg.screenshot(path=str(png / f"Q237_render_{key}_symmetric_cut_mirror_right_onto_left.png"))
                        info["cut"] = dict(left_onto_right_vs_off_diff_frac=round(diff_frac(a_off, a_l), 4), right_onto_left_vs_off_diff_frac=round(diff_frac(a_off, a_r), 4), debug_l=dbg_l, debug_r=dbg_r)
                info["errors"] = [e for e in errs if "clinical_" not in e and "404" not in e and "ERR_CERT" not in e and "fonts" not in e.lower() and "ERR_FAILED" not in e]
                info["errors_all"] = errs[:6]
                r[name] = info; ctx.close()
        finally:
            srv.terminate(); b.close()
        res[d] = r
        Path(outp).write_text(json.dumps(res, indent=1))
        print(d, {k: (v["title"], v["sym_select"], v.get("modes", {}).get("r", {}).get("state"), v.get("cut", {}).get("left_onto_right_vs_off_diff_frac"), v["errors"][:2], (v["scrollW"], v["innerW"])) for k, v in r.items()}, flush=True)
Path(outp).write_text(json.dumps(res, indent=1))
