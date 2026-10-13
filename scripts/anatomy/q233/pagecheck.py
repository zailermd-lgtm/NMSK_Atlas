#!/usr/bin/env python3
"""Q233: headless Chromium (swiftshader) load of the six Q233 pages (or any page dirs): page / console errors, horizontal scroll, structure list text contains the new organs, title, desktop + phone.
    python3 scripts/anatomy/q233/pagecheck.py THREE_MIN_JS OUT.json [page_dir:html:expect1,expect2 ...]   (default: the six build/q233 pages)"""
import json, socket, subprocess, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright
REPO = Path(__file__).resolve().parents[3]
three, outp = sys.argv[1:3]
specs = sys.argv[3:] or [
    "build/q233/viewer_m_hr:atlas_viewer_male.html:Testis,Prostate,Glans penis,Seminal vesicle",
    "build/q233/viewer_f_hr:atlas_viewer_female.html:Uterus,Ovary,Uterine tube",
    "build/q233/viewer_zan_atlas:atlas_viewer_zan_atlas.html:Testis,Penis,Prostate",
    "build/q233/viewer_base_female:atlas_viewer_base_female.html:Uterus,Ovary,Uterine tube",
    "build/q233/viewer_zan_vhm:atlas_viewer_zan_male_fitted.html:Testis,Penis,Prostate",
    "build/q233/viewer_zan_female:atlas_viewer_zan_female.html:Uterus,Ovary,Uterine tube"]
res = {}
with sync_playwright() as p:
    b = p.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"], executable_path="/opt/pw-browsers/chromium")
    for spec in specs:
        d, rel, expect = spec.split(":"); expect = [e for e in expect.split(",") if e]
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
                    if "three" in u and ("cdnjs" in u or "jsdelivr" in u or "unpkg" in u):
                        rq.fulfill(body=open(three, "rb").read(), content_type="application/javascript")
                    elif "fonts.g" in u:
                        rq.abort()
                    else:
                        rq.continue_()
                HOOKS = [("var cutCtl = null, partsCtl = null;", "var cutCtl = null, partsCtl = null; window.__T = {meshes:meshes, groups:groups, order:order};"),
                         ("searchEl.oninput=renderList; renderList();", "searchEl.oninput=renderList; renderList(); window.__T = {OBJ: OBJ};")]
                def patch(rq):
                    resp = rq.fetch(); t = resp.text()
                    for a_, b_ in HOOKS:
                        if a_ in t: t = t.replace(a_, b_, 1)
                    rq.fulfill(response=resp, body=t)
                pg.route("**/*", route)
                pg.route("**/*.html", patch)
                pg.goto(f"http://127.0.0.1:{port}/{rel}", wait_until="load")
                try:
                    pg.wait_for_function("window.__T && ((window.__T.OBJ && window.__T.OBJ.length > 0) || (window.__T.meshes && window.__T.meshes.length > 50))", timeout=240000)
                except Exception:
                    pass
                time.sleep(3)
                present = {}
                names = pg.evaluate("""() => { var T = window.__T || {}, out = [];
                    if (T.OBJ) T.OBJ.forEach(function(o){ out.push((o.name || o.id || "") + "|" + (o.id || "") + "|" + (o.sys || "")); });
                    if (T.meshes) T.meshes.forEach(function(m){ var u = m.userData || {}; out.push((u.name || u.id || m.name || "") + "|" + (u.id || m.name || "") + "|" + (u.cat || u.sys || "")); });
                    return out; }""")
                for e in expect:
                    present[e] = any(e.lower() in n.lower() for n in names)
                present["_structures_seen"] = len(names)
                txt = pg.evaluate("() => document.body.innerText")
                info = dict(title=pg.title(), scrollW=pg.evaluate("document.documentElement.scrollWidth"), innerW=pg.evaluate("window.innerWidth"), text_len=len(txt),
                            expected_present=present, errors=[e for e in errs if "clinical_" not in e and "404" not in e and "ERR_CERT" not in e and "fonts" not in e.lower()], errors_all=errs[:6])
                r[name] = info; ctx.close()
        finally:
            srv.terminate()
        res[d] = r
        print(d, {k: (v["title"], v["expected_present"], v["errors"][:2], (v["scrollW"], v["innerW"])) for k, v in r.items()}, flush=True)
    b.close()
Path(outp).write_text(json.dumps(res, indent=1))
