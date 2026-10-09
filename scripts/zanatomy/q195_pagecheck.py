"""Q195: headless (Chromium, swiftshader, three.js routed from a local copy) load of a built Z-Anatomy page, desktop + phone:
page errors, console errors, horizontal scroll, structures visible at load; screenshots.

    python3 scripts/zanatomy/q195_pagecheck.py ROOT_DIR PAGE.html OUT_PREFIX THREE_MIN_JS"""
import json, socket, subprocess, sys, time
from playwright.sync_api import sync_playwright

root, rel, outp, three = sys.argv[1:5]
HOOK = ('searchEl.oninput=renderList; renderList();',
        'searchEl.oninput=renderList; renderList(); window.__T = {OBJ: OBJ, cam: cam, need: function(){ need = true; }};')
s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "-d", root], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)


def patch(route):
    r = route.fetch(); b = r.text()
    route.fulfill(response=r, body=b.replace(HOOK[0], HOOK[1], 1) if HOOK[0] in b else b)


res = {}
try:
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader"])
        for name, vp in (("desktop", {"width": 1400, "height": 900}), ("phone", {"width": 390, "height": 844})):
            pg = b.new_page(viewport=vp)
            errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" else None)
            pg.route("**/*.html", patch)
            pg.route("**/three*.js", lambda r: r.fulfill(path=three, content_type="application/javascript"))
            pg.goto(f"http://127.0.0.1:{port}/{rel}")
            pg.wait_for_function("window.__T && __T.OBJ.length>0", timeout=600000)
            pg.wait_for_timeout(3000)
            res[name] = {"errors": errs, "structures": pg.evaluate("__T.OBJ.length"), "search_placeholder": pg.evaluate("document.getElementById('search').placeholder"),
                         "no_hscroll": pg.evaluate("document.documentElement.scrollWidth<=window.innerWidth"), "title": pg.title()}
            pg.screenshot(path=f"{outp}_{name}.png")
            if name == "desktop":
                pg.evaluate("__T.cam.az=0;__T.cam.el=0;__T.need()"); pg.wait_for_timeout(500); pg.screenshot(path=f"{outp}_front.png")
                pg.evaluate("__T.cam.az=1.5708;__T.cam.el=0;__T.need()"); pg.wait_for_timeout(500); pg.screenshot(path=f"{outp}_side.png")
        b.close()
finally:
    srv.terminate()
print(json.dumps(res, indent=1))
