"""Q226 probe: open a staged page in headless Chromium (swiftshader), open Imaging, report errors/timings, save screenshots.
    python3 scripts/clinical/q226_probe.py ROOT_DIR PAGE.html OUT_PREFIX THREE_JS [WxH] [js-to-eval-after-ready]"""
import json, socket, subprocess, sys, time
from playwright.sync_api import sync_playwright
root, rel, outp, three = sys.argv[1:5]
vp = sys.argv[5] if len(sys.argv) > 5 else "1440x900"
extra = sys.argv[6] if len(sys.argv) > 6 else ""
w, h = map(int, vp.split("x"))
s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "-d", root], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
try:
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
        mobile = min(w, h) < 520
        ctx = b.new_context(viewport={"width": w, "height": h}, has_touch=mobile, is_mobile=mobile, device_scale_factor=1)
        pg = ctx.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append("pageerror:" + str(e)))
        pg.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" else None)
        pg.route("**/fonts.g*.com/**", lambda r: r.fulfill(status=200, body="", content_type="text/css"))
        pg.route("**/three*.js", lambda r: r.fulfill(path=three, content_type="application/javascript"))
        pg.goto(f"http://127.0.0.1:{port}/{rel}")
        pg.wait_for_function("window.NMSKImaging", timeout=900000)
        pg.wait_for_timeout(3000)
        pg.screenshot(path=f"{outp}_0.png")
        t0 = time.time()
        pg.evaluate("NMSKImaging.open()")
        pg.wait_for_function("NMSKImaging.geo() !== null", timeout=300000)
        print("geometry ready s", round(time.time() - t0, 1))
        pg.evaluate("NMSKImaging.idle()")
        pg.wait_for_timeout(2500)
        print(json.dumps(pg.evaluate("NMSKImaging.perf().history")[-6:]))
        pg.screenshot(path=f"{outp}_1.png")
        if extra:
            print(json.dumps(pg.evaluate(extra)))
            pg.wait_for_timeout(3000); pg.screenshot(path=f"{outp}_2.png")
        print("errors", errs[:10])
        b.close()
finally:
    srv.terminate()
