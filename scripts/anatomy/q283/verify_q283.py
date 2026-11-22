#!/usr/bin/env python3
"""Q283: real headless-Chromium verification of the Learn panel (viewer/learn/).

Owner's request: a learn / explain button for a structure, a muscle or a muscle group, chosen by text or on the model;
the choice highlighted and everything else semi-transparent (adjustable); a button to rotate the figure a half or full
turn in a chosen direction; a button to simulate the structure's action by moving the model (example: iliopsoas --
psoas: hip flexion; iliacus: "adduction + flexion"). Checked on both engines, desktop click and phone touch:

A  toolbar button opens the panel; text search finds the muscle, its parts, named groups and motions
B  picking highlights exactly the page's own structures of that muscle (Q227 marks + Q232 hl/fade states) at the
   panel's opacity, and the opacity slider drives the selection controller's fade value
C  the parts row: psoas major offers hip flexion + lumbar lateral flexion; iliacus offers hip flexion only and the card
   says plainly that adduction is not animated for lack of a citation
D  simulate drives the Q241 pose rig (hip_r flexion rises during the run) and returns it exactly to the start pose
E  half / full turn rotate the camera (view direction reversed / restored)
F  a click on the model hands the clicked muscle to the panel (follow mode)
G  Quick view's new "Learn" button hands its pick over in one click
H  a named group (quadriceps) and a motion search (hip flexion) highlight every member and offer aggregated motions;
   a muscle with no rig joint for its cited actions says why instead of offering a button
I  0 page errors

    python3 scripts/anatomy/q283/verify_q283.py OWN_DIR ZAN_DIR
"""
from __future__ import annotations
import socket
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

THREE = "/tmp/three_x/package/build/three.min.js"
LAUNCH_ARGS = ["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]


def serve(page_dir):
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "-d", str(page_dir)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    return srv, port


def route(rq):
    u = rq.request.url
    if "three" in u and u.endswith(".js") and ("cdnjs" in u or "jsdelivr" in u or "unpkg" in u):
        rq.fulfill(body=open(THREE, "rb").read(), content_type="application/javascript")
    elif "fonts.g" in u:
        rq.abort()
    else:
        rq.continue_()


def html_of(d: Path) -> str:
    c = sorted(Path(d).glob("atlas_viewer*.html"))
    return c[0].name if c else "index.html"


def check(label, cond, errs):
    ok = bool(cond)
    print(("  OK  " if ok else "  FAIL") + " " + label)
    if not ok:
        errs.append(label)
    return ok


def ready(pg):
    pg.wait_for_function("document.readyState === 'complete'", timeout=60000)
    pg.wait_for_function("window.learnCtl && window.learnCtl.state().ready", timeout=120000)
    pg.wait_for_function("window.NMSKClinicalTool && window.NMSKClinicalTool.api && window.NMSKClinicalTool.api.pose() && window.NMSKClinicalTool.api.pose().ready()", timeout=180000)
    pg.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
    pg.wait_for_timeout(600)
    b = pg.query_selector("#mw-close")
    if b and b.is_visible():
        b.click(); pg.wait_for_timeout(200)


def tap(pg, selector, phone):
    pg.eval_on_selector(selector, "e => e.scrollIntoView({block: 'center'})")
    pg.wait_for_timeout(100)
    if phone:
        box = pg.eval_on_selector(selector, "e => { const r = e.getBoundingClientRect(); return {x: r.x + r.width/2, y: r.y + r.height/2}; }")
        pg.touchscreen.tap(box["x"], box["y"])
    else:
        pg.click(selector)


def tap_text(pg, container, text, phone):
    """tap the first button inside `container` whose text contains `text` (real click / touch, not a JS .click())"""
    idx = pg.evaluate("([c, t]) => Array.from(document.querySelectorAll(c + ' button')).findIndex(b => b.textContent.indexOf(t) >= 0)", [container, text])
    if idx < 0:
        return False
    tap(pg, f"{container} button >> nth={idx}", phone)
    return True


def sample_during(pg, expr, start_selector, phone, busy_flag, timeout=400000):
    """start an in-page sampler of `expr` every 40 ms, trigger the action, wait until `busy_flag` clears; return the samples
    (software rendering makes single fixed-time samples meaningless: a frame can take seconds)"""
    pg.evaluate("(e) => { window.__smp = []; window.__smpT = setInterval(() => { try { window.__smp.push((new Function('api', 'return ' + e))(window.NMSKClinicalTool.api)); } catch (x) {} }, 40); }", expr)
    start_selector()
    pg.wait_for_function(f"window.learnCtl.state().{busy_flag}", timeout=10000)
    pg.wait_for_function(f"!window.learnCtl.state().{busy_flag}", timeout=timeout)
    pg.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
    return pg.evaluate("() => { clearInterval(window.__smpT); return window.__smp; }")


def api(pg, expr):
    return pg.evaluate("() => { const api = window.NMSKClinicalTool.api; return " + expr + "; }")


def run_page(page_dir: Path, tag: str, errs: list):
    html = html_of(page_dir)
    srv, port = serve(page_dir)
    try:
        with sync_playwright() as pl:
            b = pl.chromium.launch(args=LAUNCH_ARGS, executable_path="/opt/pw-browsers/chromium")
            for (w, h), phone in ((1400, 900), False), ((390, 844), True):
                T = f"{tag}_{w}"
                ctx = b.new_context(viewport={"width": w, "height": h}, has_touch=phone, is_mobile=phone, device_scale_factor=1)
                pg = ctx.new_page()
                page_errs = []
                pg.on("pageerror", lambda e: page_errs.append(str(e)))
                pg.route("**/*", route)
                pg.goto(f"http://127.0.0.1:{port}/{html}", wait_until="load", timeout=90000)
                ready(pg)
                il = pg.evaluate("() => window.learnCtl.recsFor('iliopsoas', 'r', null)")
                check(f"{T}: page has right iliopsoas structures ({il})", il, errs)
                # A
                tap(pg, "#t-learn", phone); pg.wait_for_timeout(200)
                check(f"{T}: A toolbar button opens the Learn panel", pg.evaluate("() => !document.getElementById('ln-panel').hidden"), errs)
                pg.fill("#ln-q", "iliopsoas"); pg.wait_for_timeout(250)
                res = pg.evaluate("() => Array.from(document.querySelectorAll('#ln-res button')).map(b => b.textContent)")
                check(f"{T}: A search lists the muscle ({res[:3]})", any("Iliopsoas" in r and "(r)" in r for r in res), errs)
                tap_text(pg, "#ln-res", "(r)", phone); pg.wait_for_timeout(400)
                st = pg.evaluate("() => window.learnCtl.state()")
                check(f"{T}: A picked iliopsoas (r)", st["cur"] and st["cur"]["b"] == "iliopsoas" and st["cur"]["side"] == "r", errs)
                # B
                sel = api(pg, "api.selection().state()")
                check(f"{T}: B marks = exactly the page's iliopsoas_r structures", sorted(set(sel["marks"])) == sorted(set(il)), errs)
                check(f"{T}: B selected highlighted, others faded at 25%", sel["sel"] == "hl" and sel["oth"] == "fade" and abs(sel["fade"] - 0.25) < 1e-6, errs)
                pg.eval_on_selector("#ln-op", "e => { e.value = 40; e.dispatchEvent(new Event('input', {bubbles: true})); }"); pg.wait_for_timeout(100)
                check(f"{T}: B opacity slider -> fade 40%", abs(api(pg, "api.selection().state().fade") - 0.40) < 1e-6, errs)
                # C
                tap_text(pg, "#ln-parts", "Psoas major", phone); pg.wait_for_timeout(300)
                acts = [a["label"] for a in pg.evaluate("() => window.learnCtl.state().acts")]
                check(f"{T}: C psoas major offers hip flexion + lumbar lateral flexion ({acts})", any("Hip flexion" in a for a in acts) and any("Lumbar spine lateral flexion" in a for a in acts), errs)
                tap_text(pg, "#ln-parts", "Iliacus", phone); pg.wait_for_timeout(300)
                acts = [a["label"] for a in pg.evaluate("() => window.learnCtl.state().acts")]
                na = pg.evaluate("() => Array.from(document.querySelectorAll('#ln-acts .ln-na')).map(p => p.textContent).join(' ')")
                check(f"{T}: C iliacus offers hip flexion, no adduction ({acts})", any("Hip flexion" in a for a in acts) and not any("adduction" in a.lower() for a in acts), errs)
                check(f"{T}: C card says adduction is not animated for iliacus, and why", "Not animated for Iliacus: hip adduction" in na and "No citation" in na, errs)
                # D
                p0 = api(pg, "api.pose().pose().j.hip_r")
                smp = sample_during(pg, "api.pose().pose().j.hip_r[0]", lambda: tap_text(pg, "#ln-acts", "Hip flexion", phone), phone, "animating")
                check(f"{T}: D simulate raises right hip flexion through the pose rig ({p0[0]:.1f} -> max {max(smp or [p0[0]]):.1f}, {len(smp)} samples)", smp and max(smp) > p0[0] + 15, errs)
                end = api(pg, "api.pose().pose().j.hip_r")
                check(f"{T}: D pose returns exactly to the start ({end[0]:.2f} vs {p0[0]:.2f})", all(abs(a - c) < 0.01 for a, c in zip(end, p0)), errs)
                tap_text(pg, "#ln-parts", "Psoas major", phone); pg.wait_for_timeout(300)
                l0 = api(pg, "api.pose().pose().r.lumbar[1]")
                smp = sample_during(pg, "api.pose().pose().r.lumbar[1]", lambda: tap_text(pg, "#ln-acts", "Lumbar spine lateral flexion", phone), phone, "animating")
                check(f"{T}: D right psoas bends the lumbar spine to the right ({l0:.1f} -> max {max(smp or [l0]):.1f})", smp and max(smp) > l0 + 5, errs)
                check(f"{T}: D lumbar spine back to the start", abs(api(pg, "api.pose().pose().r.lumbar[1]") - l0) < 0.01, errs)
                # E
                d0 = api(pg, "api.view().dir")
                turn = '[data-turn="180"][data-dir="1"]' if phone else '[data-turn="360"][data-dir="-1"]'
                smp = sample_during(pg, "api.view().dir", lambda: tap(pg, turn, phone), phone, "rotating")
                pg.wait_for_timeout(400)
                d1 = api(pg, "api.view().dir")
                def cosxz(a, c): return (a[0] * c[0] + a[2] * c[2]) / max(1e-9, (a[0] ** 2 + a[2] ** 2) ** .5 * (c[0] ** 2 + c[2] ** 2) ** .5)
                dot = cosxz(d0, d1); mn = min([cosxz(d0, x) for x in smp] or [1])
                if phone:
                    check(f"{T}: E half turn reverses the horizontal view direction (cos {dot:.3f})", dot < -0.99, errs)
                else:
                    check(f"{T}: E full turn comes back to the start direction (cos {dot:.3f}) after facing the other way (min cos {mn:.2f})", dot > 0.99 and mn < -0.5, errs)
                # G (Quick view hand-over), then H
                tap(pg, "#ln-close", phone); pg.wait_for_timeout(100)
                tap(pg, "#t-quick", phone); pg.wait_for_timeout(150)
                pg.fill("#qv-q", "rectus femoris"); pg.wait_for_timeout(250)
                pg.evaluate("() => { const b = Array.from(document.querySelectorAll('#qv-res button')).find(x => x.textContent.indexOf('rectus_femoris_r') >= 0); if (b) b.click(); }")
                pg.wait_for_timeout(150)
                tap(pg, "#qv-learn", phone); pg.wait_for_timeout(400)
                st = pg.evaluate("() => window.learnCtl.state()")
                check(f"{T}: G Quick view 'Learn' opens the Learn panel on its pick in one click", st["open"] and st["cur"] and st["cur"]["b"] == "rectus_femoris", errs)
                pg.fill("#ln-q", "quadriceps"); pg.wait_for_timeout(250)
                tap_text(pg, "#ln-res", "Quadriceps femoris", phone); pg.wait_for_timeout(400)
                acts = [a["label"] for a in pg.evaluate("() => window.learnCtl.state().acts")]
                marks = api(pg, "api.selection().state().marks.length")
                check(f"{T}: H quadriceps group: knee extension aggregated over its members ({acts[:2]}), {marks} structures marked", any(a.startswith("▶ Knee extension") for a in acts) and marks >= 4, errs)
                pg.fill("#ln-q", "hip flexion"); pg.wait_for_timeout(250)
                tap_text(pg, "#ln-res", "Hip flexion", phone); pg.wait_for_timeout(400)
                st = pg.evaluate("() => window.learnCtl.state()")
                check(f"{T}: H motion search 'hip flexion' highlights every muscle citing it ({api(pg, 'api.selection().state().marks.length')} structures)", st["cur"]["k"] == "f" and api(pg, "api.selection().state().marks.length") >= 6, errs)
                ok = pg.evaluate("() => window.learnCtl.pickMuscle('trapezius', 'r') || window.learnCtl.pickMuscle('trapezius', null)")
                if ok:
                    txt = pg.evaluate("() => document.getElementById('ln-acts').textContent")
                    check(f"{T}: H trapezius says why nothing is simulated", "No motion to simulate" in txt and "scapula" in txt, errs)
                # F: a real click on the model hands the clicked muscle over (camera at the right thigh, front view)
                pg.evaluate("() => window.learnCtl.pickGroup('hamstrings')"); pg.wait_for_timeout(200)
                xy = pg.evaluate("""() => { const api = window.NMSKClinicalTool.api; const r = api.list().filter(x => x.id === 'rectus_femoris_r')[0]; if (!r) return null;
                    const p = [(r.bmin[0]+r.bmax[0])/2, (r.bmin[1]+r.bmax[1])/2, r.bmax[2] - 6]; api.focus(p, 260); return api.toScreen(p); }""")
                pg.wait_for_timeout(500)
                if xy and phone:
                    top = pg.evaluate("() => document.getElementById('ln-panel').getBoundingClientRect().top")
                    check(f"{T}: F the focused structure stays visible above the phone panel (y {xy[1]:.0f} < panel top {top:.0f})", xy[1] < top - 10, errs)
                if xy:
                    if phone: pg.touchscreen.tap(xy[0], xy[1])
                    else: pg.mouse.click(xy[0], xy[1])
                    try:
                        pg.wait_for_function("() => { const s = window.learnCtl.state(); return s.cur && s.cur.k === 'm'; }", timeout=20000)
                    except Exception:
                        pass
                    st = pg.evaluate("() => window.learnCtl.state()")
                    sid = api(pg, "api.selectedId()")
                    check(f"{T}: F click on the model (selected {sid}) hands that muscle to the panel ({st['cur']})", st["cur"] and st["cur"]["k"] == "m" and sid and st["cur"]["b"] in sid, errs)
                check(f"{T}: I 0 page errors", not page_errs, errs)
                if page_errs:
                    print("    ", page_errs[:5])
                ctx.close()
            b.close()
    finally:
        srv.terminate()


def main():
    own, zan = Path(sys.argv[1]), Path(sys.argv[2])
    errs = []
    run_page(own, "own", errs)
    run_page(zan, "zan", errs)
    print("\nALL OK" if not errs else f"\n{len(errs)} FAILED: " + "; ".join(errs))
    return 0 if not errs else 1


if __name__ == "__main__":
    raise SystemExit(main())
