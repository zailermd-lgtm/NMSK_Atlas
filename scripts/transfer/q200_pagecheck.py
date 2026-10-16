#!/usr/bin/env python3
"""Q200: headless Chromium (swiftshader) page check of a built own-model page: page errors, Source-facet class counts read from the page vs the
Q200 audit, structures drawn at load, no horizontal scroll (desktop 1400x900 + phone 390x844).
    q200_pagecheck.py ROOT PAGE.html THREE_MIN_JS AUDIT.json male|female"""
import json, socket, subprocess, sys, time
from playwright.sync_api import sync_playwright

root, rel, three, audit, which = sys.argv[1:6]
s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "-d", root], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
HOOK = ("var cutCtl = null;", "var cutCtl = null; window.__T = {meshes:meshes, groups:groups, order:order};")
res = {}
try:
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"], executable_path="/opt/pw-browsers/chromium")
        for name, vp, touch in (("desktop", dict(width=1400, height=900), False), ("phone", dict(width=390, height=844), True)):
            ctx = b.new_context(viewport=vp, has_touch=touch, is_mobile=touch)
            pg = ctx.new_page(); errs = []
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" else None)
            def route(r):
                u = r.request.url
                if "three" in u and "cdnjs" in u:
                    r.fulfill(body=open(three, "rb").read(), content_type="application/javascript")
                elif u.endswith(rel):
                    resp = r.fetch(); t = resp.text(); r.fulfill(response=resp, body=t.replace(HOOK[0], HOOK[1], 1) if HOOK[0] in t else t)
                else:
                    r.continue_()
            pg.route("**/*", route)
            pg.goto(f"http://127.0.0.1:{port}/{rel}", wait_until="load")
            pg.wait_for_function("window.__T && window.__T.meshes && window.__T.meshes.length > 100", timeout=180000)
            time.sleep(2)
            info = pg.evaluate("""() => { var T = window.__T, cls = {}, ids = {}, vis = 0;
              T.meshes.forEach(function(m){ var s = m.userData; cls[s.src] = (cls[s.src]||0) + 1; if (m.visible) vis++; });
              var gc = {}; T.order.forEach(function(g){ gc[g.src] = (gc[g.src]||0) + 1; });
              return {entries: T.meshes.length, entry_classes: cls, group_classes: gc, groups: T.order.length, visible_entries: vis,
                      scrollW: document.documentElement.scrollWidth, innerW: window.innerWidth}; }""")
            info["errors"] = [e for e in errs if "clinical_" not in e and "404" not in e]
            info["errors_all"] = errs
            res[name] = info
            ctx.close()
        b.close()
finally:
    srv.terminate()
a = json.load(open(audit))["own_" + which]
res["audit_entries"] = {c: v["entries"] for c, v in a["by_class"].items()}
res["audit_ids"] = {c: v["ids"] for c, v in a["by_class"].items()}
res["audit_visible_default"] = a.get("visible_default_by_class")
res["match"] = {n: (res[n]["entry_classes"] == {k: v for k, v in res["audit_entries"].items() if v} and res[n]["group_classes"] == {k: v for k, v in res["audit_ids"].items() if v}) for n in ("desktop", "phone")}
print(json.dumps(res, indent=1)[:5000])
