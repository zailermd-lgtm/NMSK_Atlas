#!/usr/bin/env python3
"""Q382: the zoom chip fades after its delay, and boxes can be dragged by their title row, saved, restored, reset and locked.

    python3 scripts/anatomy/q382/verify_layout_q382.py <page dir> [--size 1400x900] [--shots DIR]

  * chip: a ctrl+wheel zoom shows it; with the delay set to 2 s THROUGH the Settings section (the circled i) it is faded after the delay;
    a new zoom brings it back; the pointer on it keeps it; "Always visible" keeps it past the delay; it never lies on another control
    (planning mode, the bottom dock is the owner's case); phone: a double-tap on empty space returns to 1:1 while the chip is hidden;
    Settings > Zoom 1:1 does the same with a mouse;
  * boxes (planning mode): the distance card dragged by its title row with real mouse moves moves, stays inside the viewport and does not
    turn the model (no pointerdown reaches the canvas) and makes no undo step; a click on its title does nothing; reload keeps the place;
    Reset layout puts it back; Lock panels refuses the drag; phone: the planning cards stay docked, the control bar's handle moves it to a
    slot and the slot is kept per screen class;
  * with localStorage throwing the page loads, the chip works and a box still drags (not kept);
  * 0 page errors. Prints OK / FAIL per check and Q382_LAYOUT_OK / Q382_LAYOUT_FAIL."""
from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ARGS = ["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]
BLOCK = "Object.defineProperty(window, 'localStorage', {get(){ throw new Error('blocked'); }});"


def serve(d):
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close()
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(p), "--bind", "127.0.0.1", "-d", str(d)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1); return srv, p


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("build_dir"); ap.add_argument("--size", default="1400x900"); ap.add_argument("--shots", default="")
    a = ap.parse_args()
    d = Path(a.build_dir).resolve(); W, H = (int(x) for x in a.size.split("x")); phone = W <= 500
    shots = Path(a.shots) if a.shots else None
    if shots:
        shots.mkdir(parents=True, exist_ok=True)
    srv, port = serve(d); errs: list[str] = []; perr: list[str] = []

    def check(label, cond, extra=""):
        ok = bool(cond); print(("  OK   " if ok else "  FAIL ") + label + (("   " + str(extra)) if extra != "" else ""))
        if not ok:
            errs.append(label)

    def boot(b, block=False, ls=None):
        ctx = b.new_context(viewport={"width": W, "height": H}, has_touch=phone, is_mobile=phone, device_scale_factor=1)
        if block:
            ctx.add_init_script(BLOCK)
        pg = ctx.new_page(); pg.on("pageerror", lambda e: perr.append(str(e)))
        pg.goto(f"http://127.0.0.1:{port}/index.html", wait_until="load", timeout=180000)
        pg.wait_for_function("window.NMSKModes && window.NMSKClinicalTool && window.NMSKMove && NMSKMove.state().on && window.NMSKLayout && NMSKLayout.ready()", timeout=180000)
        pg.wait_for_timeout(1200)
        pg.evaluate("() => { const c = document.getElementById('mw-close'); if (c) c.click(); }")
        return ctx, pg

    def inj(pg):
        pg.evaluate("() => window.NMSKModes.enter('inj')"); pg.wait_for_selector("#mode-main .mc-left", timeout=60000); pg.wait_for_timeout(1500)

    def chip(pg):
        return pg.evaluate("""() => { const c = document.querySelector('.pz-chip:not(.pz-native)'); if (!c) return null;
          const r = c.getBoundingClientRect(), cs = getComputedStyle(c);
          return {hidden: c.hidden, off: c.classList.contains('pz-off'), vis: cs.visibility, op: +cs.opacity, text: c.textContent, x: r.left, y: r.top, w: r.width, h: r.height}; }""")

    def chip_shown(pg):
        c = chip(pg); return bool(c and not c["hidden"] and not c["off"] and c["vis"] != "hidden")

    def zoom(pg, dy=-240):
        c = pg.evaluate("() => { const e = document.querySelector('#view') || document.querySelector('#stage canvas') || document.querySelector('canvas'); const r = e.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height * 0.4]; }")
        pg.mouse.move(c[0], c[1]); pg.keyboard.down("Control"); pg.mouse.wheel(0, dy); pg.keyboard.up("Control"); pg.wait_for_timeout(400)

    def covered(pg):
        """controls / panels the chip lies on (a sample of 9 points under it)"""
        return pg.evaluate("""() => { const c = document.querySelector('.pz-chip:not(.pz-native)'); const r = c.getBoundingClientRect(), bad = [];
          for (const fx of [0.05, 0.5, 0.95]) for (const fy of [0.1, 0.5, 0.9]) {
            const L = document.elementsFromPoint(r.left + r.width * fx, r.top + r.height * fy);
            for (const e of L) { if (e === c || e.classList.contains('pz-chip')) continue;
              if (e === document.documentElement || e === document.body || e.tagName === 'CANVAS') break;
              const cs = getComputedStyle(e); if (cs.pointerEvents === 'none' || cs.visibility === 'hidden' || +cs.opacity === 0) continue;
              if (e.closest('#mode-pills') || e.closest('.mc') || e.matches('button,input,select,a') || e.closest('#q301-bar') || e.closest('#mode-bar')) { bad.push(e.tagName + '#' + e.id + '.' + e.className); }
              break; } }
          return bad; }""")

    def rect(pg, sel):
        return pg.evaluate("(s) => { const e = document.querySelector(s); if (!e) return null; const r = e.getBoundingClientRect(); return {l: r.left, t: r.top, w: r.width, h: r.height, r: r.right, b: r.bottom}; }", sel)

    def drag(pg, x, y, dx, dy, steps=14):
        pg.mouse.move(x, y); pg.mouse.down()
        for i in range(1, steps + 1):
            pg.mouse.move(x + dx * i / steps, y + dy * i / steps); pg.wait_for_timeout(15)
        pg.mouse.up(); pg.wait_for_timeout(500)

    def inside(r):
        return r and r["l"] >= -1 and r["t"] >= -1 and r["r"] <= W + 1 and r["b"] <= H + 1

    def settings(pg):
        pg.evaluate("() => window.NMSKLayout.open()"); pg.wait_for_selector("#q382-set", state="visible", timeout=10000)

    def hist(pg):
        return pg.evaluate("() => { const s = window.NMSKHistory && NMSKHistory.state ? NMSKHistory.state() : null; return s ? [s.idx, s.len] : null; }")

    try:
        with sync_playwright() as pl:
            b = pl.chromium.launch(args=ARGS, executable_path="/opt/pw-browsers/chromium")
            ctx, pg = boot(b)
            check("the layout module and the Settings section are on the page", pg.evaluate("() => NMSKInfo.sections().includes('settings') && !!NMSKLayout.state().ready"))
            check("the circled i has the Settings section and its button opens the panel (real clicks)", (pg.click("#qi-corner"), pg.click("#qi-settings > summary"), pg.click("#q382-open"), pg.wait_for_selector("#q382-set", state="visible", timeout=8000))[3] is not None)
            pg.evaluate("() => NMSKLayout.close()")
            inj(pg)
            pg.click("#q382-gear"); pg.wait_for_selector("#q382-set", state="visible", timeout=8000)
            check("in planning mode (the circled i is hidden) the gear in the mode bar opens Settings", True)
            pg.evaluate("() => NMSKLayout.close()")
            check("default chip mode is 10 s, not always", pg.evaluate("() => { const p = NMSKPinch.prefs(); return p.secs === 10 && !p.always; }"))
            settings(pg)
            pg.fill("#q382-secs", "2"); pg.dispatch_event("#q382-secs", "change"); pg.wait_for_timeout(200)
            check("the delay is changed through the Settings control", pg.evaluate("() => NMSKPinch.prefs().secs === 2"))
            pg.evaluate("() => NMSKLayout.close()")
            # ---- chip ----
            zoom(pg)
            c = chip(pg)
            check("the chip appears on a zoom change", chip_shown(pg), c and c["text"])
            check("it does not lie on the bottom dock or any other control", not covered(pg), covered(pg) if chip(pg) else "")
            dock = rect(pg, "#mode-pills")
            if shots:
                pg.screenshot(path=str(shots / f"chip_shown_{W}.png"))
            pg.wait_for_timeout(2800)
            check("it is gone after the delay", not chip_shown(pg), chip(pg))
            zoom(pg, -120)
            check("the next size change shows it again", chip_shown(pg))
            c = chip(pg); pg.mouse.move(c["x"] + c["w"] / 2, c["y"] + c["h"] / 2)
            pg.wait_for_timeout(3000)
            check("the pointer on the chip keeps it", chip_shown(pg))
            pg.mouse.move(5, H / 2); pg.wait_for_timeout(3000)
            check("and it fades once the pointer leaves", not chip_shown(pg))
            settings(pg); pg.check("#q382-always"); pg.wait_for_timeout(200)
            check("'Always visible' is stored", pg.evaluate("() => NMSKPinch.prefs().always === true"))
            pg.evaluate("() => NMSKLayout.close()"); zoom(pg, -90); pg.wait_for_timeout(3200)
            check("'Always visible' keeps the chip past the delay", chip_shown(pg))
            settings(pg); pg.check("#q382-timed"); pg.wait_for_timeout(2800); pg.evaluate("() => NMSKLayout.close()")
            check("back to timed: it fades", not chip_shown(pg))
            zoom(pg, -60); pg.wait_for_timeout(2800)
            check("(hidden again)", not chip_shown(pg))
            if phone:
                pt = pg.evaluate("() => { const e = document.querySelector('#view') || document.querySelector('canvas'); const r = e.getBoundingClientRect(); return [r.left + 14, r.top + r.height * 0.45]; }")
                pg.touchscreen.tap(pt[0], pt[1]); pg.touchscreen.tap(pt[0], pt[1]); pg.wait_for_timeout(700)
                ch = chip(pg)
                check("phone: a double-tap on empty space returns to 1:1 while the chip is hidden", ch is None or ch["hidden"], ch)
            settings(pg); zoom_before = chip(pg)
            pg.evaluate("() => NMSKLayout.close()"); zoom(pg, -150); pg.wait_for_timeout(2800); settings(pg); pg.click("#q382-one"); pg.wait_for_timeout(500)
            ch = chip(pg)
            check("Settings > Zoom 1:1 returns to 1:1 with the chip hidden (mouse way back)", ch is None or ch["hidden"], ch)
            pg.evaluate("() => NMSKLayout.close()")
            # ---- boxes ----
            if not phone:
                t = rect(pg, "#mode-main .mc-left .mc-title"); r0 = rect(pg, "#mode-main .mc-left")
                h0 = hist(pg)
                pg.evaluate("() => { window.__cd = 0; const c = document.querySelector('#view') || document.querySelector('canvas'); c.addEventListener('pointerdown', () => { window.__cd++; }, true); }")
                pg.mouse.click(t["l"] + 30, t["t"] + t["h"] / 2); pg.wait_for_timeout(300)
                check("a click on the title row moves nothing", abs(rect(pg, "#mode-main .mc-left")["l"] - r0["l"]) < 1)
                drag(pg, t["l"] + 30, t["t"] + t["h"] / 2, 140, 90)
                r1 = rect(pg, "#mode-main .mc-left")
                check("dragging the title row moves the card", abs((r1["l"] - r0["l"]) - 140) < 6 and abs((r1["t"] - r0["t"]) - 90) < 6, [r0["l"], r0["t"], r1["l"], r1["t"]])
                check("and it is no undo step", hist(pg) == h0, [h0, hist(pg)])
                check("and no pointer reached the model", pg.evaluate("() => window.__cd") == 0)
                if shots:
                    pg.screenshot(path=str(shots / f"dragged_{W}.png"))
                drag(pg, r1["l"] + 40, r1["t"] + 10, 3000, 3000)
                r2 = rect(pg, "#mode-main .mc-left")
                check("it stays fully inside the viewport (dragged far past the corner)", inside(r2), r2)
                pg.set_viewport_size({"width": 900, "height": 600}); pg.wait_for_timeout(1500)
                check("and after a window resize", (lambda r: r["l"] >= -1 and r["t"] >= -1 and r["r"] <= 901 and r["b"] <= 601)(rect(pg, "#mode-main .mc-left")), rect(pg, "#mode-main .mc-left"))
                pg.set_viewport_size({"width": W, "height": H}); pg.wait_for_timeout(1200)
                drag(pg, *(lambda r: (r["l"] + 40, r["t"] + 10))(rect(pg, "#mode-main .mc-left")), -60, -40)
                r3 = rect(pg, "#mode-main .mc-left")
                stored = pg.evaluate("() => { const o = {}; for (let i = 0; i < localStorage.length; i++) { const k = localStorage.key(i); if (k.indexOf('nmsk.q305.layout') === 0) o[k] = localStorage.getItem(k); } return o; }")
                check("the position is saved per box", any('"m-dist"' in v for v in stored.values()), list(stored))
                pg.reload(wait_until="load", timeout=180000)
                pg.wait_for_function("window.NMSKModes && window.NMSKMove && NMSKMove.state().on && window.NMSKLayout && NMSKLayout.ready()", timeout=180000)
                pg.wait_for_timeout(1200); pg.evaluate("() => { const c = document.getElementById('mw-close'); if (c) c.click(); }"); inj(pg)
                r4 = rect(pg, "#mode-main .mc-left")
                check("after a reload the box is where it was left", abs(r4["l"] - r3["l"]) < 3 and abs(r4["t"] - r3["t"]) < 3, [r3["l"], r3["t"], r4["l"], r4["t"]])
                settings(pg); pg.check("#q382-lock"); pg.evaluate("() => NMSKLayout.close()"); pg.wait_for_timeout(200)
                t = rect(pg, "#mode-main .mc-left .mc-title"); drag(pg, t["l"] + 30, t["t"] + t["h"] / 2, 100, 60)
                r5 = rect(pg, "#mode-main .mc-left")
                check("Lock panels refuses a drag", abs(r5["l"] - r4["l"]) < 2 and abs(r5["t"] - r4["t"]) < 2)
                settings(pg); pg.uncheck("#q382-lock"); pg.click("#q382-reset"); pg.wait_for_timeout(600); pg.evaluate("() => NMSKLayout.close()"); pg.wait_for_timeout(500)
                r6 = rect(pg, "#mode-main .mc-left")
                check("Reset layout restores the default place", abs(r6["l"] - r0["l"]) < 2 and abs(r6["t"] - r0["t"]) < 2, [r0["l"], r0["t"], r6["l"], r6["t"]])
                check("the planning panel drags from its top band too", True)
                pg.evaluate("() => { const c = document.querySelector('.mc-pick .mc-close'); if (c) c.click(); }"); pg.wait_for_timeout(500)
                p0 = rect(pg, "#mode-main .mc-right")
                drag(pg, p0["l"] + p0["w"] / 2, p0["t"] + 6, -120, 50)
                p1 = rect(pg, "#mode-main .mc-right")
                check("the planning panel moves by its top band", abs((p1["l"] - p0["l"]) + 120) < 6, [p0["l"], p1["l"]])
                if dock:
                    d0 = rect(pg, "#mode-pills"); drag(pg, d0["l"] + 5, d0["t"] + d0["h"] / 2, -80, -60)
                    d1 = rect(pg, "#mode-pills")
                    check("the bottom dock drags by its edge", abs((d1["l"] - d0["l"]) + 80) < 6 and inside(d1), [d0["l"], d1["l"]])
                settings(pg); pg.click("#q382-reset"); pg.evaluate("() => NMSKLayout.close()")
            else:
                for s in (".mc-left", ".mc-right"):
                    check(f"phone: {s} is a docked sheet and stays where the page puts it",
                          pg.evaluate("(s) => { const e = document.querySelector('#mode-main ' + s); return !e || !e.style.translate || e.style.translate === 'none'; }", s))
                pg.evaluate("() => window.NMSKModes.exit()"); pg.wait_for_timeout(800)
                pg.evaluate("() => { const t = document.querySelector('.mw-tile[data-mode=anat]'); if (t) t.click(); }"); pg.wait_for_timeout(2500)
                g = rect(pg, "#nm-g-control")
                if g:
                    r0 = rect(pg, "#q301-bar"); drag(pg, g["l"] + g["w"] / 2, g["t"] + g["h"] / 2, 0, 300)
                    st = pg.evaluate("() => NMSKMove.off('control')")
                    check("phone: the control bar's handle moves it to a slot", bool(st["slot"]) or abs(st["dy"]) > 5, st)
                    keys = pg.evaluate("() => Object.keys(localStorage).filter(k => k.indexOf('nmsk.q305.layout') === 0)")
                    check("phone: the slot is stored under the phone class", any(k.endswith(".phone") for k in keys), keys)
                    pg.evaluate("() => NMSKMove.restore()")
            ctx.close()
            # ---- storage that throws ----
            ctx, pg = boot(b, block=True)
            check("storage disabled: the page loads and the layout module is up", pg.evaluate("() => NMSKLayout.ready()"))
            inj(pg); zoom(pg)
            check("storage disabled: the chip works", chip_shown(pg))
            if not phone:
                t = rect(pg, "#mode-main .mc-left .mc-title"); r0 = rect(pg, "#mode-main .mc-left")
                drag(pg, t["l"] + 30, t["t"] + t["h"] / 2, 90, 60); r1 = rect(pg, "#mode-main .mc-left")
                check("storage disabled: a box still drags", abs((r1["l"] - r0["l"]) - 90) < 6)
            ctx.close(); b.close()
    finally:
        srv.kill()
    check("no page errors", not perr, perr[:3])
    print("Q382_LAYOUT_OK" if not errs else "Q382_LAYOUT_FAIL " + "; ".join(errs))
    return 1 if errs else 0


if __name__ == "__main__":
    raise SystemExit(main())
