"""Q236: frame cost with and without labels, one page, one viewport, nothing else running (software GL: swiftshader, so absolute numbers are CPU rasterisation, not a GPU).

    python3 scripts/anatomy/q236/perf_check.py ROOT_DIR PAGE.html PAGE_NAME [--json out.json] [--steps 8] [--viewport 1366x768]

Orbit steps (mouse drag, each step waits two animation frames) with labels Off / Visible (vis, 24) / All, the same camera path each time; per mode: mean / median / max ms per step, plus the
controller's own numbers (ID pass, whole heavy refresh, per-frame layout) and how many heavy refreshes happened (the ID pass is throttled to about 1/7 of the time)."""
import json
import socket
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright

args = [a for a in sys.argv[1:] if not a.startswith("--")]
root, rel, page_name = args[:3]
opt = lambda k, d: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d
steps = int(opt("--steps", "8")); W, H = [int(x) for x in opt("--viewport", "1366x768").split("x")]; json_out = opt("--json", None)
args = [a for a in args if a not in (json_out, opt("--steps", "8"), opt("--viewport", "1366x768"))]
s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "-d", root], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
res = {"page": page_name, "viewport": f"{W}x{H}", "steps": steps, "renderer": "chromium swiftshader (software GL)", "modes": {}}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
    pg = b.new_context(viewport={"width": W, "height": H}).new_page(); pg.set_default_timeout(600000)
    pg.route("**/fonts.g*.com/**", lambda r: r.fulfill(status=200, body="", content_type="text/css"))
    pg.route("**/three*.js", lambda r: r.fulfill(path="/tmp/three_x/package/build/three.min.js", content_type="application/javascript"))
    pg.goto(f"http://127.0.0.1:{port}/{rel}")
    pg.wait_for_function("window.__labCtl", timeout=900000); pg.wait_for_timeout(2500)
    pg.evaluate("document.getElementById('btn-spin') && document.getElementById('btn-spin').classList.contains('on') && document.getElementById('btn-spin').click()")
    cx, cy = W // 2, H // 2 + 40

    def orbit():
        pg.mouse.move(cx, cy); pg.mouse.down(); ts = []
        for k in range(steps):
            t0 = time.time(); pg.mouse.move(cx + 12 * (k + 1), cy + 2 * (k % 3))
            pg.evaluate("new Promise(function(r){requestAnimationFrame(function(){requestAnimationFrame(r);});})")
            ts.append((time.time() - t0) * 1000)
        pg.mouse.up(); ts.sort()
        return {"mean_ms": round(sum(ts) / len(ts)), "median_ms": round(ts[len(ts) // 2]), "max_ms": round(ts[-1])}

    for mode, extra in (("off", ""), ("vis", "window.__labCtl.set('density', 24);"), ("all", "")):
        pg.evaluate("window.__labCtl.setMode('%s'); %s" % (mode, extra)); pg.wait_for_timeout(1500)
        h0 = pg.evaluate("window.__labState().heavyCount")
        r = orbit(); st = pg.evaluate("window.__labState()")
        r.update({"heavy_refreshes_during_orbit": st["heavyCount"] - h0, "id_pass_ms": st["idMs"], "refresh_ms": st["heavyMs"], "layout_ms": st["layoutMs"], "labelled": len(st["shown"])})
        res["modes"][mode] = r
        print(page_name, mode, json.dumps(r), flush=True)
    pg.evaluate("window.__labCtl.setMode('off')")
    b.close()
srv.terminate()
off = res["modes"]["off"]["mean_ms"]
res["overhead_pct"] = {m: round(100 * (res["modes"][m]["mean_ms"] - off) / off) for m in ("vis", "all")}
print(page_name, "overhead vs off (%):", res["overhead_pct"])
if json_out:
    json.dump(res, open(json_out, "w"), indent=1)
