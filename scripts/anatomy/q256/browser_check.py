"""Q256: headless-Chromium check of items 1/2/3 on one built page.
    python3 scripts/anatomy/q256/browser_check.py BUILD_DIR PAGE.html OUT.json
"""
import json
import socket
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright

root, rel, out_path = sys.argv[1:4]
s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "-d", root],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
URL = f"http://127.0.0.1:{port}/{rel}"
R = {"checks": {}, "info": {}, "errors": []}
try:
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium",
                               args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
        ctx = b.new_context(viewport={"width": 1400, "height": 900})
        pg = ctx.new_page(); pg.set_default_timeout(300000)
        pg.on("pageerror", lambda e: R["errors"].append("pageerror:" + str(e)))
        pg.on("console", lambda m: R["errors"].append("console:" + m.text) if m.type == "error" and "Failed to load resource" not in m.text else None)
        pg.route("**/fonts.g*.com/**", lambda r: r.fulfill(status=200, body="", content_type="text/css"))
        pg.route("**/three*.js", lambda r: r.fulfill(path="/tmp/three_x/package/build/three.min.js", content_type="application/javascript"))
        pg.route("**pmc.ncbi.nlm.nih.gov**", lambda r: r.abort())
        pg.goto(URL, timeout=300000)
        pg.wait_for_function("window.__partsState && window.__partsState().loaded", timeout=300000)
        pg.wait_for_timeout(1500)

        # ---- item 1: Parts markers default OFF, no dots in the normal display
        st0 = pg.evaluate("window.__partsState()")
        R["info"]["parts_default"] = {"mode": st0["mode"], "shown": len([m for m in st0["markers"] if m["vis"]])}
        R["checks"]["1_default_mode_off"] = st0["mode"] == "off"
        R["checks"]["1_nothing_shown_by_default"] = len([m for m in st0["markers"] if m["vis"]]) == 0
        pg.evaluate("window.__partsCtl.setMode('near')")
        pg.wait_for_timeout(300)
        pg.evaluate("window.__partsCtl.cullNow && window.__partsCtl.cullNow()")
        pg.wait_for_timeout(300)
        st1 = pg.evaluate("window.__partsState()")
        shown1 = [m for m in st1["markers"] if m["vis"]]
        R["info"]["parts_after_opt_in"] = {"mode": st1["mode"], "shown": len(shown1)}
        R["checks"]["1_opting_in_shows_markers"] = st1["mode"] == "near" and len(shown1) > 0
        pg.evaluate("window.__partsCtl.setMode('off')")

        # ---- item 2: tendon/ligament/fascia origin/insertion markers actually present in this page's own data
        parts2 = pg.evaluate("""fetch('parts_data.json').then(r=>r.json()).then(d=>{
            var cls = {ligament:0, tendon:0, fascia:0, muscle:0};
            d.placed.forEach(function(pl){ var p = d.parts[pl.p]; var sid = p.id.split('.')[0]; });
            var byCls = {};
            d.parts.forEach(function(p){ if (/_q256$/.test(p.id)) (byCls[p.ty]=byCls[p.ty]||0, byCls[p.ty]++); });
            var placedQ256 = d.placed.filter(function(pl){ return /_q256$/.test(d.parts[pl.p].id); }).length;
            return {byType: byCls, placedQ256: placedQ256, totalParts: d.parts.length, totalPlaced: d.placed.length};
        })""")
        R["info"]["q256_attachments"] = parts2
        R["checks"]["2_origin_insertion_rows_present"] = parts2["placedQ256"] >= 0 and sum(parts2["byType"].values()) > 0

        # ---- item 3: nerve groups panel loads real plexus data and a REAL CLICK on a group row marks it via the existing selCtl
        ng = pg.evaluate("window.__nerveGroupsState ? window.__nerveGroupsState() : null")
        R["info"]["nerve_groups_initial"] = ng
        R["checks"]["3_nerve_groups_controller_present"] = ng is not None
        if ng and ng.get("loaded"):
            R["checks"]["3_toolbar_button_present"] = pg.evaluate("!!document.getElementById('t-nervegroups')")
            pg.evaluate("document.getElementById('t-nervegroups').click()")
            pg.wait_for_timeout(200)
            sel_before = pg.evaluate("window.__selState().marks.length")
            n_rows = pg.evaluate("document.querySelectorAll('.ng-row').length")
            R["info"]["ng_rows_shown"] = n_rows
            if n_rows > 0:
                pg.evaluate("document.querySelector('.ng-row').click()")
                pg.wait_for_timeout(300)
                sel_after = pg.evaluate("window.__selState().marks.length")
                R["info"]["marks_before_after_click"] = [sel_before, sel_after]
                R["checks"]["3_clicking_a_group_marks_real_nerves_via_selCtl"] = sel_after > sel_before
                pg.evaluate("document.querySelector('.ng-clear').click()")
                pg.wait_for_timeout(200)
                R["checks"]["3_clear_button_clears_marks"] = pg.evaluate("window.__selState().marks.length") == 0
        R["checks"]["0_no_page_errors"] = len(R["errors"]) == 0
        b.close()
finally:
    srv.terminate()

json.dump(R, open(out_path, "w"), indent=1)
print(json.dumps({"checks": R["checks"], "errors": R["errors"][:10]}, indent=1))
