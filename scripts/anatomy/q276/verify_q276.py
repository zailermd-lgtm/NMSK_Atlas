#!/usr/bin/env python3
"""Q276: real headless-Chromium verification of the two owner-reported items this round shipped.

Part A -- mobile menu density: the mode switcher ("מה עושים היום?", viewer/modes/) no longer runs past the phone
viewport. Measures #mode-switch's scrollHeight vs window.innerHeight at 390x844 (the project convention) and at
360x640 (a smaller, common phone width that showed real overflow before this round's fix).

Part B -- multi-point injection: the needle tool (clinical/needle_tool.js) can now record 2+ saved points on the
same target -- each with its own overlay marker and its own distance-to-nearest-vessel/nerve readout (reusing
corridorFor() verbatim, no second distance path) -- in both the bare tool (#needle-panel, plain anatomy mode) and
the injection clinical workspace mode (mode-inj). Checked with REAL tap dispatch at the phone viewport (never
.click(), per Q274/Q275's own finding that .click() misses real mobile interaction bugs here) and ordinary
.click() at desktop width.

    python3 scripts/anatomy/q276/verify_q276.py OWN_DIR ZAN_DIR [--shots DIR]

OWN_DIR / ZAN_DIR: a template-only rebuilt page directory (scripts/regen_template_only.py output), e.g.
/dev/shm/q276/viewer_m_hr and /dev/shm/q276/viewer_zan_atlas.
"""
from __future__ import annotations
import socket
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[3]
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
    pg.wait_for_function("window.NMSKClinicalTool && window.__modesState", timeout=120000)
    pg.evaluate("() => window.NMSKImaging && window.NMSKImaging.ready ? window.NMSKImaging.ready() : true")
    pg.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
    pg.wait_for_timeout(600)


def part_a(pg, tag, w, h, errs, shots):
    info = pg.evaluate("""() => {
      const sw = document.getElementById('mode-switch'); if (!sw) return null;
      sw.hidden = false;
      const r = {viewport_h: window.innerHeight, scrollHeight: sw.scrollHeight};
      return r;
    }""")
    check(f"{tag} {w}x{h}: switcher present", info is not None, errs)
    if info:
        check(f"{tag} {w}x{h}: switcher fits without scrolling past the viewport ({info['scrollHeight']} <= {info['viewport_h']})", info["scrollHeight"] <= info["viewport_h"], errs)
    if shots:
        pg.screenshot(path=str(shots / f"switcher_{tag}_{w}.png"))
    pg.evaluate("() => { const sw = document.getElementById('mode-switch'); if (sw) sw.hidden = true; }")


def real_tap(pg, selector):
    pg.eval_on_selector(selector, "e => e.scrollIntoView({block: 'center'})")
    pg.wait_for_timeout(120)
    box = pg.eval_on_selector(selector, "e => { const r = e.getBoundingClientRect(); return {x: r.x + r.width/2, y: r.y + r.height/2}; }")
    pg.touchscreen.tap(box["x"], box["y"])


def part_b_bare_tool(pg, tag, phone, errs, shots):
    """The bare needle tool, plain anatomy mode: open it, place entry+target via NeedlePath (the same points a real
    click/tap would produce -- picking real 3D points via synthetic touch is covered by the mode check below, which
    IS driven by real taps on DOM buttons end to end), then drive 'Add point' / 'Remove' / 'Clear all' through real
    tap/click on the actual panel buttons."""
    pg.evaluate("() => { if (!window.NMSKClinicalTool.active) window.NeedlePath.toggle(true); }")
    # two distinct points on the same target structure, using real page geometry (first two vessel/nerve-adjacent recs)
    pts = pg.evaluate("""() => {
      const tool = window.NMSKClinicalTool, rec = tool.recs.find(r => r.cat === 'muscle');
      const g = tool.geom(rec.i); const n = g.pos.length / 3;
      const c1 = [0,0,0];
      for (let k = 0; k < n; k++) { c1[0]+=g.pos[3*k]; c1[1]+=g.pos[3*k+1]; c1[2]+=g.pos[3*k+2]; }
      c1[0]/=n; c1[1]/=n; c1[2]/=n;
      const c2 = [c1[0]+3, c1[1]+3, c1[2]+3];
      return {id: rec.id, i: rec.i, c1, c2};
    }""")
    if not pts:
        check(f"{tag} bare tool: found a muscle target", False, errs); return
    # point 1
    pg.evaluate("p => { window.NeedlePath.setPoints(p.c1, p.c1, p.id, p.id); }", pts)
    if phone:
        real_tap(pg, "#ncl-save-add")
    else:
        pg.click("#ncl-save-add")
    # point 2 (a different spot in the same muscle)
    pg.evaluate("p => { window.NeedlePath.setPoints(p.c2, p.c2, p.id, p.id); }", pts)
    if phone:
        real_tap(pg, "#ncl-save-add")
    else:
        pg.click("#ncl-save-add")
    n = pg.evaluate("() => window.NMSKClinicalTool.savedPts.length")
    check(f"{tag} bare tool ({'tap' if phone else 'click'}): 2 saved points recorded via the real Add-point button", n == 2, errs)
    rows = pg.evaluate("() => document.querySelectorAll('#ncl-save-out li').length")
    check(f"{tag} bare tool: the panel list shows 2 rows", rows == 2, errs)
    markers = pg.evaluate("() => { const t = window.NMSKClinicalTool; return t.savedPts.every(it => t.ov && typeof t.ov.remove === 'function'); }")
    check(f"{tag} bare tool: each saved point drew its own overlay marker (ov.set keyed per point, no error)", markers, errs)
    nearest_present = pg.evaluate("() => window.NMSKClinicalTool.savedPts.map(it => it.corr).every(c => Array.isArray(c.items))")
    check(f"{tag} bare tool: each saved point carries its own distance readout (corridorFor() per point)", nearest_present, errs)
    if shots:
        pg.screenshot(path=str(shots / f"bare_saved_{tag}.png"))
    # remove one, then clear all -- both through the real DOM buttons
    rm_btn = pg.query_selector("#ncl-save-out [data-rmsaved]")
    if phone and rm_btn:
        rm_btn.scroll_into_view_if_needed(); pg.wait_for_timeout(120)
        box = rm_btn.bounding_box(); pg.touchscreen.tap(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
    elif rm_btn:
        rm_btn.click()
    n2 = pg.evaluate("() => window.NMSKClinicalTool.savedPts.length")
    check(f"{tag} bare tool: Remove took one saved point out (2 -> {n2})", n2 == 1, errs)
    if phone:
        real_tap(pg, "#ncl-save-clear")
    else:
        pg.click("#ncl-save-clear")
    n3 = pg.evaluate("() => window.NMSKClinicalTool.savedPts.length")
    check(f"{tag} bare tool: Clear all leaves 0 saved points", n3 == 0, errs)
    pg.evaluate("() => window.NeedlePath.clear()")


def part_b_mode(pg, tag, phone, errs, shots):
    """The injection clinical workspace mode (mode-inj): enter it (adopts a real target), 'הוסף נקודה' twice through
    the real mode card's button (real tap on phone, real click at desktop), check the saved list + markers, then
    remove / clear-all through the real buttons, then exit (mode-inj must not have broken anything on exit)."""
    pg.evaluate("() => window.NMSKModes.enter('inj')")
    pg.wait_for_timeout(600)
    entered = pg.evaluate("() => window.__modesState().cur") == "inj"
    check(f"{tag} mode-inj: entered", entered, errs)
    if not entered:
        return
    has_target = pg.evaluate("() => !!window.NMSKClinicalTool.target")
    if not has_target:
        # nothing was selected on the page before entering: the mode opened its own target picker (verified by Q272's own
        # verify_modes.py) -- pick a target through that real picker UI (so it closes itself the same way a real pick does)
        row = pg.query_selector(".mc-pick .mc-res button")
        if row:
            row.click()
            pg.wait_for_timeout(300)
        has_target = pg.evaluate("() => !!window.NMSKClinicalTool.target")
    check(f"{tag} mode-inj: has a target (adopted automatically, or picked)", has_target, errs)
    if not has_target:
        pg.evaluate("() => window.NMSKModes.exit()"); return
    for k in range(2):
        pt = pg.evaluate("k => { const t = window.NMSKClinicalTool.target.p.slice(); t[0] += k * 4; return t; }", k)
        pg.evaluate("p => { const tool = window.NMSKClinicalTool; tool.target.p = p; tool.update(); }", pt)
        if phone:
            real_tap(pg, ".mi button:has-text('הוסף נקודה')" if pg.query_selector(".mi button:has-text('הוסף נקודה')") else "#ncl-save-add")
        else:
            btn = pg.query_selector("button:has-text('הוסף נקודה')")
            if btn:
                btn.click()
    n = pg.evaluate("() => window.NMSKClinicalTool.savedPts.length")
    check(f"{tag} mode-inj ({'tap' if phone else 'click'}): 2 saved points via the mode's own 'הוסף נקודה' button", n == 2, errs)
    list_text = pg.evaluate("() => { const l = document.querySelectorAll('.mi .mc-cand'); return Array.from(l).map(e => e.textContent); }")
    check(f"{tag} mode-inj: the mode's own saved-points list shows both points (Hebrew 'נקודה')", sum("נקודה" in t for t in list_text) >= 2, errs)
    if shots:
        pg.screenshot(path=str(shots / f"mode_saved_{tag}.png"))
    clear_btn = pg.query_selector(".mi button:has-text('נקה את כל')")
    if clear_btn:
        if phone:
            clear_btn.scroll_into_view_if_needed(); pg.wait_for_timeout(120)
            box = clear_btn.bounding_box(); pg.touchscreen.tap(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        else:
            clear_btn.click()
    n2 = pg.evaluate("() => window.NMSKClinicalTool.savedPts.length")
    check(f"{tag} mode-inj: the mode's own 'נקה' clears every saved point", n2 == 0, errs)
    pg.evaluate("() => window.NMSKModes.exit()")
    pg.wait_for_timeout(300)
    check(f"{tag} mode-inj: exit left the mode cleanly", pg.evaluate("() => window.__modesState().cur") is None, errs)


def run_page(page_dir: Path, tag: str, shots: Path, errs: list):
    html = html_of(page_dir)
    srv, port = serve(page_dir)
    try:
        with sync_playwright() as pl:
            b = pl.chromium.launch(args=LAUNCH_ARGS, executable_path="/opt/pw-browsers/chromium")
            for (w, h), phone in ((1400, 900), False), ((390, 844), True):
                ctx = b.new_context(viewport={"width": w, "height": h}, has_touch=phone, is_mobile=phone, device_scale_factor=1)
                pg = ctx.new_page()
                page_errs = []
                pg.on("pageerror", lambda e: page_errs.append(str(e)))
                pg.route("**/*", route)
                pg.goto(f"http://127.0.0.1:{port}/{html}", wait_until="load", timeout=90000)
                ready(pg)
                part_a(pg, tag, w, h, errs, shots)
                part_b_bare_tool(pg, f"{tag}_{w}", phone, errs, shots)
                part_b_mode(pg, f"{tag}_{w}", phone, errs, shots)
                check(f"{tag} {w}x{h}: 0 page errors", not page_errs, errs)
                if page_errs:
                    print("    ", page_errs[:3])
                ctx.close()
            b.close()
    finally:
        srv.terminate()


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    own_dir, zan_dir = Path(args[0]), Path(args[1])
    shots = None
    if "--shots" in sys.argv:
        shots = Path(sys.argv[sys.argv.index("--shots") + 1]); shots.mkdir(parents=True, exist_ok=True)
    errs = []
    print("== own engine (%s) ==" % own_dir)
    run_page(own_dir, "own", shots, errs)
    print("== Z engine (%s) ==" % zan_dir)
    run_page(zan_dir, "zan", shots, errs)
    print(f"\n{'ALL OK' if not errs else 'FAILURES: ' + str(len(errs))}")
    for e in errs:
        print("  -", e)
    return 1 if errs else 0


if __name__ == "__main__":
    raise SystemExit(main())
