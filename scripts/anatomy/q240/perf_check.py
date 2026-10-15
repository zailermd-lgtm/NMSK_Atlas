"""Q240: frame cost of the view-dependent part markers and the vessel / nerve labels, one page, one viewport (software GL: swiftshader, i.e. CPU rasterisation, not a GPU).

    python3 scripts/anatomy/q240/perf_check.py ROOT_DIR PAGE.html PAGE_NAME [--json out.json] [--steps 6] [--viewport 1366x768]

Orbit steps (mouse drag, each step waits two animation frames) with Parts markers Off / Visible + near / All and with Labels Off / Visible (arteries + nerves to level 2), the same
camera path each time; per mode: mean / median / max ms per step, the number of depth passes taken during the orbit (throttled: camera settle + a low rate while orbiting), and the
cost of one forced depth + ID capture (the unit the throttle works in)."""
import json
import socket
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright

args = [a for a in sys.argv[1:] if not a.startswith("--")]
root, rel, page_name = args[:3]
opt = lambda k, d: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d
steps = int(opt("--steps", "6")); W, H = [int(x) for x in opt("--viewport", "1366x768").split("x")]; json_out = opt("--json", None)
s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "-d", root], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
res = {"page": page_name, "viewport": f"{W}x{H}", "steps": steps, "renderer": "chromium swiftshader (software GL)", "modes": {}}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
    pg = b.new_context(viewport={"width": W, "height": H}).new_page(); pg.set_default_timeout(900000)
    pg.route("**/fonts.g*.com/**", lambda r: r.fulfill(status=200, body="", content_type="text/css"))
    pg.route("**/three*.js", lambda r: r.fulfill(path="/tmp/three_x/package/build/three.min.js", content_type="application/javascript"))
    pg.goto(f"http://127.0.0.1:{port}/{rel}")
    pg.wait_for_function("window.__labCtl && window.__partsState && window.__partsState().loaded", timeout=900000); pg.wait_for_timeout(2500)
    pg.evaluate("document.getElementById('btn-spin') && document.getElementById('btn-spin').classList.contains('on') && document.getElementById('btn-spin').click()")
    res["structures"] = pg.evaluate("window.__labCtl.state().calCount") and pg.evaluate("(function(){ return document.getElementById('s-str') ? document.getElementById('s-str').textContent : null; })()")
    cx, cy = W // 2, H // 2 + 40

    def orbit():
        pg.mouse.move(cx, cy); pg.mouse.down(); ts = []
        for k in range(steps):
            t0 = time.time(); pg.mouse.move(cx + 12 * (k + 1), cy + 2 * (k % 3))
            pg.evaluate("new Promise(function(r){requestAnimationFrame(function(){requestAnimationFrame(r);});})")
            ts.append((time.time() - t0) * 1000)
        pg.mouse.up(); ts.sort()
        return {"mean_ms": round(sum(ts) / len(ts)), "median_ms": round(ts[len(ts) // 2]), "max_ms": round(ts[-1])}

    def run(tag, pjs, ljs):
        pg.evaluate(pjs + ";" + ljs); pg.wait_for_timeout(2500)
        n0 = pg.evaluate("window.__partsState().cull.n")
        r = orbit(); pg.wait_for_timeout(2500)
        st = pg.evaluate("window.__partsState()")
        r.update({"depth_passes_during_orbit_and_settle": st["cull"]["n"] - n0, "avg_capture_ms": st["cull"]["avgMs"], "image": st["cull"]["img"], "shown": st["cull"]["cnt"]["shown"], "placed": st["placements"]})
        res["modes"][tag] = r
        print(page_name, tag, json.dumps(r), flush=True)

    run("baseline (markers off, labels off)", "window.__partsCtl.setMode('off')", "window.__labCtl.setMode('off')")
    run("markers: Visible + near", "window.__partsCtl.setMode('near')", "window.__labCtl.setMode('off')")
    run("markers: All", "window.__partsCtl.setMode('all')", "window.__labCtl.setMode('off')")
    run("markers off, labels: Visible (arteries + nerves)", "window.__partsCtl.setMode('off')", "window.__labCtl.setMode('vis'); window.__labCtl.set('density', 40)")
    run("markers near + labels Visible", "window.__partsCtl.setMode('near')", "window.__labCtl.setMode('vis')")
    pg.evaluate("window.__partsCtl.setMode('near'); window.__labCtl.setMode('off')"); pg.wait_for_timeout(1500)
    cap = []
    for _ in range(3):
        pg.evaluate("window.__partsCtl.cullNow()"); cap.append(pg.evaluate("window.__partsState().cull.ms"))
    res["forced_capture_ms"] = cap
    print(page_name, "forced capture ms (depth + ID pass, then decisions)", cap)
    b.close()
srv.terminate()
base = res["modes"]["baseline (markers off, labels off)"]["mean_ms"]
res["overhead_pct"] = {k: round(100 * (v["mean_ms"] - base) / base) for k, v in res["modes"].items() if not k.startswith("baseline")}
print(page_name, "overhead vs baseline (%):", res["overhead_pct"])
if json_out:
    json.dump(res, open(json_out, "w"), indent=1)
