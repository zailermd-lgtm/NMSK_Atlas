#!/usr/bin/env python3
"""Q243: quick headless-Chromium (swiftshader) check of the Q243 page dirs: page / console errors, horizontal scroll, the new structures in the page's structure list, the parts sidecar (the 18 HRA organ
parts and their markers), the calibre table, desktop + phone.
    python3 scripts/anatomy/q243/page_check.py THREE_MIN_JS OUT.json [page_dir:html:name1|name2 ...]     (default: the three build/q243 pages)"""
import json, socket, subprocess, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[3]
three, outp = sys.argv[1:3]
specs = sys.argv[3:] or [
    "build/q243/viewer_f_hr:atlas_viewer_female.html:Uterine artery (left)|Median sacral vein|Nucleus pulposus, disc L2-L3|Spinal cord, C1 segment",
    "build/q243/viewer_zan_female:atlas_viewer_zan_female.html:Uterine artery (left)|Median sacral vein|Internal pudendal vein (right)",
    "build/q243/viewer_base_female:atlas_viewer_base_female.html:Uterine artery (left)|Median sacral vein|Superior rectal artery"]
res = {}
with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"], executable_path="/opt/pw-browsers/chromium")
    for spec in specs:
        d, rel, expect = spec.split(":"); expect = [e for e in expect.split("|") if e]
        s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
        srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "-d", str(REPO / d)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1)
        r = {}
        try:
            for vp, (w, h, mob) in {"desktop": (1400, 900, False), "phone": (390, 844, True)}.items():
                ctx = b.new_context(viewport=dict(width=w, height=h), is_mobile=mob, has_touch=mob)
                pg = ctx.new_page(); errs = []
                pg.on("pageerror", lambda e: errs.append(str(e)))
                pg.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" and "Failed to load resource" not in m.text and "ERR_FAILED" not in m.text else None)
                pg.route("**/fonts.g*.com/**", lambda r_: r_.abort())
                pg.route("**/three*.js", lambda r_: r_.fulfill(path=three, content_type="application/javascript"))
                pg.goto(f"http://127.0.0.1:{port}/{rel}", wait_until="load")
                pg.wait_for_function("window.__partsState && window.__selState && window.__labCtl", timeout=900000)
                pg.wait_for_timeout(2000)
                t0 = time.time(); st = pg.evaluate("window.__partsState()")
                while not st["loaded"] and time.time() - t0 < 120:                    # the parts sidecar is fetched asynchronously
                    pg.wait_for_timeout(2000); st = pg.evaluate("window.__partsState()")
                txt = pg.evaluate("document.body.innerText")
                html = pg.evaluate("document.documentElement.outerHTML")
                found = {e: (e in txt or e in html) for e in expect}
                markers = [m["part"] for m in st["markers"]]
                r[vp] = dict(page_errors=errs[:5], horizontal_scroll=bool(pg.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1")), title=pg.title(), found=found,
                             parts=st["parts"], placements=st["placements"], hra_markers=sum(1 for m in markers if m.startswith(("uterus.", "uterine_tube."))), hra_marker_classes=sorted({m["cls"] for m in st["markers"] if m["part"].startswith(("uterus.", "uterine_tube."))}),
                             calibre_in_page='id="nmsk-calibre"' in html)
                ctx.close()
        finally:
            srv.terminate()
        res[d] = r
        print(d, json.dumps({k: {kk: vv for kk, vv in v.items() if kk in ("page_errors", "horizontal_scroll", "parts", "placements", "hra_markers", "found")} for k, v in r.items()}), flush=True)
b.close() if False else None
Path(outp).write_text(json.dumps(res, indent=1) + "\n")
