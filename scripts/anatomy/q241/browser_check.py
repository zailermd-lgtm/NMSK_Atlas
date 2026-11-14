"""Q241: headless-Chromium check of the Pose feature on one page (software GL: swiftshader, so frame times are CPU rasterisation, not a GPU).

    python3 scripts/anatomy/q241/browser_check.py ROOT_DIR REL_HTML PAGE_NAME [--out DIR] [--json out.json] [--viewport 1366x768] [--shots] [--sweep]

--shots   screenshots: neutral, elbow flexed 90, shoulder abducted 90, hip flexed 90, knee flexed 90 (+ panel open)
--sweep   every joint DOF to both ends of its normal range (others at the model pose): update ms, structures moved, console / page errors; then back to the model pose (must restore the rest geometry)
Always: pose rig loads, API present, 0 page errors."""
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

args = [a for a in sys.argv[1:] if not a.startswith("--")]
opt = lambda k, d=None: sys.argv[sys.argv.index(k) + 1] if k in sys.argv else d
root, rel, name = args[0], args[1], args[2]
W, H = [int(x) for x in (opt("--viewport", "1366x768")).split("x")]
out_dir = opt("--out"); json_out = opt("--json")
s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "-d", root], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(1)
res = {"page": name, "viewport": "%dx%d" % (W, H), "renderer": "chromium swiftshader (software GL)", "errors": [], "shots": [], "sweep": []}
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
    pg = b.new_context(viewport={"width": W, "height": H}).new_page(); pg.set_default_timeout(900000)
    pg.on("pageerror", lambda e: res["errors"].append("pageerror: " + str(e)[:300]))
    pg.on("console", lambda m: res["errors"].append("console.error: " + m.text[:300]) if m.type == "error" else None)
    pg.route("**/fonts.g*.com/**", lambda r: r.fulfill(status=200, body="", content_type="text/css"))
    pg.route("**/three*.js", lambda r: r.fulfill(path="/tmp/three_x/package/build/three.min.js", content_type="application/javascript"))
    t0 = time.time()
    pg.goto("http://127.0.0.1:%d/%s" % (port, rel))
    pg.wait_for_function("window.__poseApi && window.__poseApi.ready()", timeout=900000)
    res["load_s"] = round(time.time() - t0, 1)
    pg.evaluate("document.getElementById('btn-spin') && document.getElementById('btn-spin').classList.contains('on') && document.getElementById('btn-spin').click()")
    pg.wait_for_timeout(1500)
    res["stats0"] = pg.evaluate("window.__poseApi.stats()")
    res["rig"] = pg.evaluate("(function(){var r=window.__poseApi.rig(); return {segments:r.segs.length, joints:r.joints.length, regions:r.regions.length, count:r.count}})()")

    def frame(n=2):
        pg.evaluate("new Promise(function(r){var k=0;function f(){if(++k>=%d)r();else requestAnimationFrame(f);}requestAnimationFrame(f);})" % n)

    def setp(sets, wait=True):
        t = time.time()
        for (jid, k, v) in sets:
            ok = pg.evaluate("window.__poseApi.%s(%s,%s,%s)" % ("set" if not jid.startswith("region:") else "setRegion", json.dumps(jid.replace("region:", "")), json.dumps(k), v))
        st = pg.evaluate("window.__poseApi.stats()")
        if wait:
            frame(2)
        return round((time.time() - t) * 1000), st

    def shot(label, sets):
        pg.evaluate("window.__poseApi.reset()"); pg.evaluate("window.__poseApi.update()")
        ms, st = setp(sets)
        pg.wait_for_timeout(400)
        f = None
        if out_dir:
            Path(out_dir).mkdir(parents=True, exist_ok=True)
            f = str(Path(out_dir) / ("%s_%s.png" % (name, label)))
            pg.screenshot(path=f)
        res["shots"].append({"label": label, "ms_total": ms, "update_ms": round(st["ms"], 1), "moved": st["changed"], "file": f})
        print(name, label, "update %.1f ms, %d structures moved, +render %d ms" % (st["ms"], st["changed"], ms), flush=True)

    if "--shots" in sys.argv:
        pg.evaluate("window.__poseApi.reset()"); pg.evaluate("window.__poseApi.update()"); pg.wait_for_timeout(500)
        if out_dir:
            Path(out_dir).mkdir(parents=True, exist_ok=True); pg.screenshot(path=str(Path(out_dir) / ("%s_neutral.png" % name)))
        shot("elbow_flexed_90", [("elbow_r", "flex", 90), ("elbow_l", "flex", 90)])
        shot("shoulder_abducted_90", [("shoulder_r", "abd", 90), ("shoulder_l", "abd", 90)])
        shot("hip_flexed_90", [("hip_r", "flex", 90), ("hip_l", "flex", 90)])
        shot("knee_flexed_90", [("knee_r", "flex", 90), ("knee_l", "flex", 90)])
        pg.evaluate("window.__poseApi.reset()"); pg.evaluate("window.__poseApi.open(true)"); pg.wait_for_timeout(600)
        if out_dir:
            pg.screenshot(path=str(Path(out_dir) / ("%s_panel.png" % name)))
        pg.evaluate("window.__poseApi.open(false)")
    if "--sweep" in sys.argv:
        rig = pg.evaluate("window.__poseApi.rig()")
        todo = []
        for j in rig["joints"]:
            if j.get("driven"):
                continue
            for d in j["dof"]:
                todo.append((j["id"], d["k"], d["lo"], d["hi"]))
        for r in rig["regions"]:
            for d in r["dof"]:
                todo.append(("region:" + r["id"], d["k"], d["lo"], d["hi"]))
        for (jid, k, lo, hi) in todo:
            row = {"joint": jid, "dof": k}
            for tag, v in (("lo", lo), ("hi", hi)):
                pg.evaluate("window.__poseApi.reset()"); pg.evaluate("window.__poseApi.update()")
                ms, st = setp([(jid, k, v)], wait=False)
                row[tag] = {"value": v, "update_ms": round(st["ms"], 1), "moved": st["changed"]}
            res["sweep"].append(row)
        pg.evaluate("window.__poseApi.reset()"); pg.evaluate("window.__poseApi.update()"); frame(2)
        res["sweep_summary"] = {"dofs": len(todo), "max_update_ms": max(max(r["lo"]["update_ms"], r["hi"]["update_ms"]) for r in res["sweep"]),
                                "mean_update_ms": round(sum(r[t]["update_ms"] for r in res["sweep"] for t in ("lo", "hi")) / (2 * len(res["sweep"])), 1)}
        print(name, "sweep", res["sweep_summary"], flush=True)
    # frame cost: time of 3 rendered frames at the model pose and with a posed update in front of each (software GL: dominated by rasterisation)
    if "--frames" in sys.argv:
        pg.evaluate("window.__poseApi.reset()"); pg.evaluate("window.__poseApi.update()"); frame(2)
        def burst(posed):
            ts = []
            for k in range(4):
                t = time.time()
                if posed:
                    pg.evaluate("window.__poseApi.set('elbow_r','flex',%d); window.__poseApi.set('knee_l','flex',%d)" % (30 + 20 * k, 20 + 20 * k))
                frame(2); ts.append((time.time() - t) * 1000)
            return round(sum(ts) / len(ts))
        res["frame_ms"] = {"rest": burst(False), "posed_update_each_frame": burst(True)}
        print(name, "frame ms", res["frame_ms"], flush=True)
    res["errors_n"] = len(res["errors"])
    b.close()
srv.terminate()
print(name, "errors:", len(res["errors"]), res["errors"][:3])
if json_out:
    json.dump(res, open(json_out, "w"), indent=1)
