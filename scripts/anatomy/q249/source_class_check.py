#!/usr/bin/env python3
"""Q249: the Source class the Imaging-based pages assign to structures whose badge starts 'PROCEDURAL/RULE-BASED' (the acromioclavicular / coracoclavicular ligaments, ...) and to the Q249 nerves, read from the running page
(headless Chromium, swiftshader).   python3 scripts/anatomy/q249/source_class_check.py PAGE_DIR HTML [--three PATH] [--json OUT]"""
import json, socket, subprocess, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright
REPO = Path(__file__).resolve().parents[3]
a = [x for x in sys.argv[1:] if not x.startswith("--")]
page_dir, html = a[:2]
three = sys.argv[sys.argv.index("--three") + 1] if "--three" in sys.argv else "/tmp/three_x/package/build/three.min.js"
jout = sys.argv[sys.argv.index("--json") + 1] if "--json" in sys.argv else None
if jout: a = [x for x in a if x != jout]
if "--three" in sys.argv: a = [x for x in a if x != three]
HOOK = ("var cutCtl = null, partsCtl = null, selCtl = null, capCtl = null, labelsCtl = null;",
        "var cutCtl = null, partsCtl = null, selCtl = null, capCtl = null, labelsCtl = null; window.__T = {meshes:meshes};")
JS = """() => { var out = {}, seen = {};
  window.__T.meshes.forEach(function(m){ var u = m.userData || {}; if (seen[u.id]) return; seen[u.id] = 1;
    var b = (u.rec && u.rec.procedural_badge) || "";
    var proc = /^\\s*procedural\\/rule-based/i.test(b), q249 = /^RULE-BASED \\(Q249\\)/.test(b);
    if (proc || q249) { var k = proc ? "procedural_rule_based" : "q249_nerves"; (out[k] = out[k] || []).push([u.id, u.subject || "", u.src]); } });
  return out; }"""
s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "-d", str(REPO / page_dir)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1); errs = []
try:
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"], executable_path="/opt/pw-browsers/chromium")
        pg = b.new_context(viewport=dict(width=1100, height=900)).new_page()
        pg.on("pageerror", lambda e: errs.append(str(e)))
        def route(rq):
            u = rq.request.url
            if "three" in u and u.endswith(".js") and ("cdnjs" in u or "jsdelivr" in u or "unpkg" in u): rq.fulfill(body=open(three, "rb").read(), content_type="application/javascript")
            elif "fonts.g" in u: rq.abort()
            else: rq.continue_()
        pg.route("**/*", route)
        def patch(rq):
            resp = rq.fetch(); t = resp.text()
            if HOOK[0] in t: t = t.replace(HOOK[0], HOOK[1], 1)
            rq.fulfill(response=resp, body=t)
        pg.route("**/*.html", patch)
        pg.goto(f"http://127.0.0.1:{port}/{html}", wait_until="load")
        pg.wait_for_function("window.__T && window.__T.meshes && window.__T.meshes.length > 50", timeout=300000)
        time.sleep(2)
        r = pg.evaluate(JS)
        b.close()
finally:
    srv.terminate()
from collections import Counter
summ = {k: dict(Counter(x[2] for x in v)) for k, v in r.items()}
print("page errors:", errs[:3]); print(json.dumps(summ))
ac = [x for x in r.get("procedural_rule_based", []) if re.search(r"acromioclav|coracoclav", x[0])] if (re := __import__("re")) else []
print("AC / CC ligaments:", ac[:8])
if jout: Path(jout).write_text(json.dumps(dict(summary=summ, ac_cc=ac, errors=errs, all=r), indent=1))
