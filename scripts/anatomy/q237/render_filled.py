#!/usr/bin/env python3
"""Q237: screenshots of filled structures in the real pages (headless Chromium, swiftshader): the mirrored structure selected, 'Colour by source' on (class 'Mirrored from the opposite side'), the muscle layer off (own pages)
or the layers that hide it faded (Z pages). Writes data/derived/Q237_render_<key>_filled_<id>.png
    python3 scripts/anatomy/q237/render_filled.py THREE_MIN_JS"""
import socket, subprocess, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright
REPO = Path(__file__).resolve().parents[3]
three = sys.argv[1]
JOBS = [("own_f", "build/q237/viewer_f_hr", "atlas_viewer_female.html", "femoral artery", "femoral_a_l", "own"), ("own_f", "build/q237/viewer_f_hr", "atlas_viewer_female.html", "popliteal vein", "popliteal_v_l", "own"),
        ("own_m", "build/q237/viewer_m_hr", "atlas_viewer_male.html", "tibial nerve", "tibial_n_r", "own")]      # own pages: the structure list is clickable by id; the Z pages' mirrored structures are seen through the Symmetric view
with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"], executable_path="/opt/pw-browsers/chromium")
    for key, d, html, q, sid, kind in JOBS:
        s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
        srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "-d", str(REPO / d)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); time.sleep(1)
        try:
            ctx = b.new_context(viewport=dict(width=1400, height=900)); pg = ctx.new_page()
            def route(rq):
                u = rq.request.url
                if "three" in u and ("cdnjs" in u or "jsdelivr" in u or "unpkg" in u): rq.fulfill(body=open(three, "rb").read(), content_type="application/javascript")
                elif "fonts.g" in u: rq.abort()
                else: rq.continue_()
            pg.route("**/*", route)
            pg.goto(f"http://127.0.0.1:{port}/{html}", wait_until="load"); time.sleep(10)
            if kind == "own":
                pg.wait_for_selector("#src-colour", state="visible", timeout=90000)
                pg.click("#src-colour"); time.sleep(0.5)
                pg.click("[data-cat='muscle']"); time.sleep(0.5)
                pg.fill("#q", q); time.sleep(1.2)
                pg.click(f"#list [data-id='{sid}'] + button.row"); time.sleep(3.0)
            else:
                pg.evaluate("() => { var a = document.querySelector('[data-view=front]'); if (a) a.click(); }")
                pg.fill("#search", q); time.sleep(1.5)
                pg.evaluate("(sid) => { var els = document.querySelectorAll('#list .item'); for (var i = 0; i < els.length; i++){ if ((els[i].dataset.id || '') === sid || els[i].textContent.toLowerCase().indexOf('(l)') >= 0){ els[i].click(); break; } } }", sid)
                time.sleep(3.0)
            out = REPO / f"data/derived/Q237_render_{key}_filled_{sid[:40]}.png"
            pg.screenshot(path=str(out)); print("wrote", out)
        except Exception as ex:
            print("FAILED", key, sid, str(ex)[:200])
        finally:
            srv.terminate()
