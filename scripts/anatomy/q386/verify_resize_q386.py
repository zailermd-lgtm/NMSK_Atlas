#!/usr/bin/env python3
"""Q386: every box can be resized (grip, lower-right), scrolls inside, and has a text size (all boxes in Settings, one box by A- / A+).

    python3 scripts/anatomy/q386/verify_resize_q386.py <page dir> [--size 1400x900] [--shots DIR]

  desktop (1400x900): real mouse drags on the grips of the Pose panel, Labels, the name card, the cut panel, the measure bar, the needle panel
    and (planning mode) the distance card and the planning panel: shrinks to the minimum and not under it, content then scrolls, grows to the
    viewport and not past it, the top-left corner stays, a mid size is kept after a reload; double-click on the grip = the box's own size;
    Lock panels refuses a resize; Reset layout puts the sizes (and the per-box text sizes) back;
    text size: all boxes 150 % through the Settings select, one box by its A+ button (own size wins over the all-boxes one), saved and
    restored after a reload, the text really is larger, never under the 10 px floor (80 %), no box reaches past the screen at 160 %;
  phone (390x844): no resize grips; the text size reaches the docked sheets through Navigate > Settings (the gear is hidden there), the Pose
    panel, Labels, the name card and the open group sheet take it, stay on the screen and scroll; saved after a reload;
  localStorage throwing: a box still resizes and the text size still applies (not kept); 0 page errors.
Prints OK / FAIL per check and Q386_RESIZE_OK / Q386_RESIZE_FAIL."""
from __future__ import annotations

import argparse
import socket
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ARGS = ["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]
BLOCK = "Object.defineProperty(window, 'localStorage', {get(){ throw new Error('blocked'); }});"
MINW, MINH = 150, 90

TEXT_JS = """(k) => { const b = NMSKMove.box(k); const e = b ? (typeof b.el === 'function' ? b.el() : document.getElementById(b.el)) : document.querySelector(k);
  if (!e) return null; const z = parseFloat(e.style.getPropertyValue('--q386-z')) || 1; let m = 99, first = 0; const all = e.querySelectorAll('*');
  for (const x of all) { if (x.children.length > 0 && !x.firstChild) continue; if (!/\\S/.test(x.textContent || '') || /^(SCRIPT|STYLE|SVG|PATH|CANVAS)$/i.test(x.tagName)) continue;
    const f = parseFloat(getComputedStyle(x).fontSize); if (f && f < m) m = f;
    if (!first) { const tn = [...x.childNodes].find(n => n.nodeType === 3 && /\\S/.test(n.textContent)); if (tn) { const r = document.createRange(); r.selectNodeContents(tn); const q = r.getClientRects()[0]; if (q && q.height) first = q.height; } } }
  const r = e.getBoundingClientRect(); const cs = getComputedStyle(e);
  return {z, min: m, eff: m * z, first, cls: e.className, l: r.left, t: r.top, r: r.right, b: r.bottom, w: r.width, h: r.height, ov: cs.overflow, sh: e.scrollHeight, ch: e.clientHeight, sw: e.scrollWidth, cw: e.clientWidth, st: e.scrollTop}; }"""


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
        ok = bool(cond); print(("  OK   " if ok else "  FAIL ") + label + (("   " + str(extra)) if extra != "" else ""), flush=True)
        if not ok:
            errs.append(label)

    def boot(b, ctx=None, block=False):
        if ctx is None:
            ctx = b.new_context(viewport={"width": W, "height": H}, has_touch=phone, is_mobile=phone, device_scale_factor=1)
            if block:
                ctx.add_init_script(BLOCK)
        pg = ctx.new_page(); pg.on("pageerror", lambda e: perr.append(str(e)))
        pg.goto(f"http://127.0.0.1:{port}/index.html", wait_until="load", timeout=180000)
        pg.wait_for_function("window.NMSKModes && window.NMSKMove && NMSKMove.state().on && window.NMSKLayout && NMSKLayout.ready() && window.NMSKResize && NMSKResize.ready()", timeout=180000)
        for _ in range(12):                      # the welcome window can come up late; it lies over every box until closed
            pg.wait_for_timeout(500)
            if pg.evaluate("() => { const c = document.getElementById('mw-close'); if (c && c.offsetParent !== null) { c.click(); return true; } return false; }"):
                pg.wait_for_timeout(600); break
        return ctx, pg

    def js(pg, code, *args, wait=700):
        r = pg.evaluate(code, *args) if args else pg.evaluate(code)
        pg.wait_for_timeout(wait); return r

    def text(pg, k):
        return pg.evaluate(TEXT_JS, k)

    def shot(pg, name):
        if shots:
            pg.screenshot(path=str(shots / f"{name}.png"))

    # ---- how each box is opened / closed (by id) ----
    def hide_sheet(pg):
        pg.evaluate("() => { const s = document.getElementById('q301-sheet'); const g = document.querySelector('#q301-groups .qg-g.qg-on, #q301-groups .qg-g[aria-expanded=true]'); if (s && !s.hidden && g) g.click(); }")

    def open_qcard(pg):
        pts = ((195, 200), (190, 300), (150, 250), (230, 350)) if phone else ((700, 300), (690, 420), (660, 250), (720, 360), (700, 520))
        # Q393: with panels open the figure is drawn in the free part of the screen, so aim at the figure itself when it is offset
        bx = pg.evaluate("() => { try { return document.querySelector('canvas[data-q393]') ? NMSKQuick.box() : null; } catch (e) { return null; } }")
        if bx:
            cx = (bx["l"] + bx["r"]) / 2; h = bx["b"] - bx["t"]
            pts = tuple((cx + dx, bx["t"] + h * f) for dx, f in ((0, 0.25), (-10, 0.38), (10, 0.18), (0, 0.5), (-20, 0.6)))
        for x, y in pts:
            pg.mouse.click(x, y); pg.wait_for_timeout(1100)
            if pg.evaluate("() => NMSKMove.present().includes('qcard')"):
                return True
        return False

    OPEN = {
        "pose": lambda pg: js(pg, "document.getElementById('qg-pose').click()", wait=1000),
        "labels": lambda pg: js(pg, "document.getElementById('t-labels').click()", wait=1000),
        "qcard": lambda pg: open_qcard(pg),
        "cut": lambda pg: (js(pg, "document.getElementById('qg-cut').click()"), js(pg, "document.getElementById('t-cut').click()", wait=1000)),
        "measure": lambda pg: js(pg, "document.getElementById('qg-measure').click()", wait=1000),
        "x-needle-panel": lambda pg: js(pg, "document.getElementById('qg-needle').click()", wait=1200),
    }
    CLOSE = {
        "pose": "document.querySelector('#pose-panel .pz-head button:last-child').click()",
        "labels": "document.getElementById('lab-close').click()",
        "qcard": "NMSKQuick.close()",
        "cut": "document.getElementById('cut-exit').click()",
        "measure": "document.getElementById('ms-close').click()",
        "x-needle-panel": "document.getElementById('ncl-close').click()",
    }

    def ensure_open(pg, k):
        if present(pg, k):
            return True
        OPEN[k](pg); hide_sheet(pg); pg.wait_for_timeout(500)
        if not present(pg, k):
            OPEN[k](pg); hide_sheet(pg); pg.wait_for_timeout(500)
        return present(pg, k)

    def close_box(pg, k):
        try:
            js(pg, CLOSE[k], wait=600)
        except Exception:
            pass
        hide_sheet(pg)

    def present(pg, k):
        return pg.evaluate("(k) => NMSKMove.present().includes(k)", k)

    def why(pg, k):
        return pg.evaluate("""(k) => { const o = document.querySelector('.q386-ov[data-q386="' + k + '"]'); if (!o) return 'no overlay'; const b = NMSKMove.box(k); const e = typeof b.el === 'function' ? b.el() : document.getElementById(b.el); const r = e.getBoundingClientRect();
          const l = document.elementsFromPoint(Math.min(innerWidth - 4, r.right - 8), Math.min(innerHeight - 4, r.bottom - 8)).slice(0, 4).map(n => (n.id || String(n.className)).slice(0, 30));
          return [o.hidden, o.style.cssText, NMSKMove.locked(), l, Math.round(r.right), Math.round(r.bottom)]; }""", k)

    def grip(pg, k):
        return pg.evaluate("""(k) => { const o = document.querySelector('.q386-ov[data-q386="' + k + '"]'); if (!o || o.hidden) return null;
          const g = o.querySelector('.q386-rz'); if (!g || getComputedStyle(g).display === 'none') return null; const r = g.getBoundingClientRect();
          return [r.left + r.width / 2, r.top + r.height / 2]; }""", k)

    def rect(pg, k):
        return pg.evaluate("(k) => NMSKMove.rect(k)", k)

    def drag_to(pg, k, dx, dy):
        g = grip(pg, k)
        if not g:
            return None
        pg.mouse.move(*g); pg.mouse.down(); pg.mouse.move(g[0] + dx / 2, g[1] + dy / 2, steps=5); pg.mouse.move(g[0] + dx, g[1] + dy, steps=6); pg.mouse.up()
        pg.wait_for_timeout(650)
        return rect(pg, k)

    def inside(r, slack=1):
        return r and r["left"] >= -slack and r["top"] >= -slack and r["left"] + r["width"] <= W + slack and r["top"] + r["height"] <= H + slack

    def hover(pg, k):
        r = rect(pg, k); pg.mouse.move(r["left"] + r["width"] / 2, r["top"] + r["height"] / 2); pg.wait_for_timeout(700)

    def settings_open(pg):
        pg.evaluate("() => NMSKLayout.open()"); pg.wait_for_timeout(500)

    def settings_close(pg):
        pg.evaluate("() => NMSKLayout.close()"); pg.wait_for_timeout(200)

    def all_boxes_in_view(pg):
        bad = []
        for k in pg.evaluate("() => NMSKResize.boxes().filter(b => b.present).map(b => b.key)"):
            t = text(pg, k)
            if t and not (t["l"] >= -1 and t["t"] >= -1 and t["r"] <= W + 1 and t["b"] <= H + 1):
                bad.append((k, round(t["l"]), round(t["t"]), round(t["r"]), round(t["b"])))
        return bad

    with sync_playwright() as pw:
        br = pw.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=ARGS)
        MID = {}
        if not phone:
            ctx, pg = boot(br)
            check("module present, boxes listed", pg.evaluate("() => NMSKResize.boxes().length >= 8"))
            base = {}
            # ---- A. resize each box ----
            for k in ("pose", "labels", "qcard", "cut", "measure", "x-needle-panel"):
                if not ensure_open(pg, k):
                    check(f"{k}: opened", False); continue
                r0 = rect(pg, k); base[k] = r0
                hover(pg, k)
                g = grip(pg, k)
                check(f"{k}: a resize grip lies on the box's lower-right corner", g and abs(g[0] - min(r0["left"] + r0["width"], W)) < 24 and abs(g[1] - min(r0["top"] + r0["height"], H)) < 24, g or why(pg, k))
                if k == "pose":
                    shot(pg, "pose_before")
                r1 = drag_to(pg, k, -3000, -3000)
                if not r1:
                    check(f"{k}: shrink drag", False); close_box(pg, k); continue
                check(f"{k}: shrinks to the minimum and not under it", MINW - 1 <= r1["width"] <= max(MINW + 2, 0) + 1 and MINH - 1 <= r1["height"] <= MINH + 3, (r1["width"], r1["height"]))
                check(f"{k}: the top-left corner stays", abs(r1["left"] - r0["left"]) <= 6 and abs(r1["top"] - r0["top"]) <= 6, (r0["left"], r0["top"], r1["left"], r1["top"]))
                t = text(pg, k)
                check(f"{k}: smaller than its content it scrolls inside", t and t["ov"] in ("auto", "scroll") and (t["sh"] > t["ch"] + 1 or t["sw"] > t["cw"] + 1), t and (t["ov"], t["sh"], t["ch"]))
                if t and t["sh"] > t["ch"] + 1:
                    pg.evaluate("(k) => { const b = NMSKMove.box(k); const e = typeof b.el === 'function' ? b.el() : document.getElementById(b.el); e.scrollTop = 1e6; }", k)
                    check(f"{k}: scrolling reaches the end", text(pg, k)["st"] > 0)
                if k == "pose":
                    shot(pg, "pose_min")
                r2 = drag_to(pg, k, 4000, 4000)
                check(f"{k}: grows to the viewport and not past it", r2 and inside(r2) and r2["width"] > r1["width"] + 20 and r2["width"] <= W - 14 and r2["height"] <= H - 14, r2)
                if k == "pose":
                    shot(pg, "pose_max")
                # a mid size, kept for the reload
                tw, th = 330, 300
                g = grip(pg, k); r2 = rect(pg, k)
                r3 = drag_to(pg, k, (r2["left"] + tw) - (r2["left"] + r2["width"]), (r2["top"] + th) - (r2["top"] + r2["height"]))
                check(f"{k}: a mid size is reached", r3 and abs(r3["width"] - tw) <= 6 and abs(r3["height"] - th) <= 6, r3)
                MID[k] = (r3["width"], r3["height"]) if r3 else None
                # double-click on the grip: the box's own size; then back to the mid size for the reload
                g = grip(pg, k)
                if g:
                    pg.mouse.dblclick(*g); pg.wait_for_timeout(700)
                    rd = rect(pg, k)
                    # (the labels panel is moved down and shortened by the page's own bar-avoidance when it was grown under the control bar)
                    check(f"{k}: double-click on the grip gives the box its own size", rd and abs(rd["width"] - r0["width"]) <= 4 and (k == "labels" or abs(rd["height"] - r0["height"]) <= 4), (rd, r0))
                    r2 = rd; r3 = drag_to(pg, k, (r2["left"] + tw) - (r2["left"] + r2["width"]), (r2["top"] + th) - (r2["top"] + r2["height"]))
                    MID[k] = (r3["width"], r3["height"]) if r3 else None
                close_box(pg, k); pg.wait_for_timeout(300)
            # ---- B. planning boxes ----
            pg.evaluate("() => NMSKModes.enter('inj')"); pg.wait_for_selector("#mode-main .mc-left", timeout=60000); pg.wait_for_timeout(1800)
            pg.evaluate("() => { const c = document.querySelector('.mc-pick .mc-close'); if (c) c.click(); }"); pg.wait_for_timeout(700)
            for k in ("m-dist", "m-plan"):
                if not present(pg, k):
                    check(f"{k}: present in planning mode", False); continue
                r0 = rect(pg, k); base[k] = r0; hover(pg, k)
                r1 = drag_to(pg, k, -3000, -3000)
                check(f"{k}: shrinks to the minimum and not under it", r1 and MINW - 1 <= r1["width"] <= MINW + 3 and MINH - 1 <= r1["height"] <= MINH + 3, r1 and (r1["width"], r1["height"]))
                t = text(pg, k)
                check(f"{k}: smaller than its content it scrolls inside", t and t["ov"] in ("auto", "scroll") and (t["sh"] > t["ch"] + 1 or t["sw"] > t["cw"] + 1), t and (t["ov"], t["sh"], t["ch"]))
                r2 = drag_to(pg, k, 4000, 4000)
                check(f"{k}: grows to the viewport and not past it", r2 and inside(r2), r2)
                r2 = rect(pg, k)
                r3 = drag_to(pg, k, 340 - r2["width"], 320 - r2["height"])
                check(f"{k}: a mid size is reached", r3 and abs(r3["width"] - 340) <= 6 and abs(r3["height"] - 320) <= 6, r3)
                MID[k] = (r3["width"], r3["height"]) if r3 else None
                shot(pg, "plan_" + k)
            pg.evaluate("() => NMSKModes.exit()"); pg.wait_for_timeout(900)

            # ---- C. text size, before the reload ----
            ensure_open(pg, "pose"); ensure_open(pg, "labels")
            for k in ("pose", "labels"):
                t = text(pg, k); base[k + "_t"] = t
            hover(pg, "pose")
            ob = pg.evaluate("""() => { const b = document.querySelector('.q386-ov[data-q386="pose"] .q386-fb'); if (!b || b.offsetParent === null) return null; const r = b.getBoundingClientRect(); return [r.left + r.width / 2, r.top + r.height / 2]; }""")
            check("pose: A+ shows while the pointer is over the box", ob)
            if ob:
                pg.mouse.click(*ob); pg.wait_for_timeout(700)
            tp, tl = text(pg, "pose"), text(pg, "labels")
            check("pose: A+ gives its own text size (110 %), another box keeps 100 %", abs(tp["z"] - 1.1) < 0.02 and abs(tl["z"] - 1.0) < 0.02, (tp["z"], tl["z"]))
            check("pose: the text really is larger", tp["first"] > base["pose_t"]["first"] * 1.05, (base["pose_t"]["first"], tp["first"]))
            settings_open(pg)
            check("settings: the all-boxes text size select and a row for the pose box exist", pg.evaluate("() => !!document.getElementById('q386-g') && !!document.querySelector('#q386-rows select[data-k=pose]')"))
            pg.select_option("#q386-g", "150"); pg.wait_for_timeout(1000)
            settings_close(pg)
            tp, tl = text(pg, "pose"), text(pg, "labels")
            check("all boxes 150 %: Labels takes it, Pose keeps its own 110 %", abs(tl["z"] - 1.5) < 0.02 and abs(tp["z"] - 1.1) < 0.02, (tl["z"], tp["z"]))
            check("all boxes 150 %: the Labels text really is larger", tl["first"] > base["labels_t"]["first"] * 1.3, (base["labels_t"]["first"], tl["first"]))
            settings_open(pg); pg.select_option("#q386-g", "160"); pg.wait_for_timeout(1000); settings_close(pg)
            check("160 %: no box reaches past the screen", not all_boxes_in_view(pg), all_boxes_in_view(pg))
            tl = text(pg, "labels")
            check("160 %: Labels scrolls inside", tl["ov"] in ("auto", "scroll"), tl["ov"])
            shot(pg, "font160")
            settings_open(pg); pg.select_option("#q386-g", "80"); pg.wait_for_timeout(1000); settings_close(pg)
            tl = text(pg, "labels")
            check("80 %: nothing under the 10 px floor", tl["eff"] >= min(base["labels_t"]["min"], 10) - 0.06, (tl["min"], tl["z"], tl["eff"]))
            settings_open(pg); pg.select_option("#q386-g", "150"); pg.wait_for_timeout(900); settings_close(pg)
            close_box(pg, "labels"); close_box(pg, "pose")

            # ---- reload: everything comes back ----
            pg.close(); ctx, pg = boot(br, ctx)
            check("reload: the all-boxes text size is 150 %, the pose box has its own", pg.evaluate("() => NMSKResize.global() === 150 && NMSKResize.own('pose') && NMSKResize.box('pose') === 110"))
            for k in ("pose", "labels", "qcard", "cut", "measure", "x-needle-panel"):
                ensure_open(pg, k); pg.wait_for_timeout(300)
                r = rect(pg, k)
                check(f"reload: {k} comes back at its saved size", r and MID.get(k) and abs(r["width"] - MID[k][0]) <= 6 and abs(r["height"] - MID[k][1]) <= 6, (r and (r["width"], r["height"]), MID.get(k)))
                if k in ("pose", "labels"):
                    t = text(pg, k)
                    check(f"reload: {k} has its text size", abs(t["z"] - (1.1 if k == "pose" else 1.5)) < 0.02, t["z"])
                if k != "pose" and k != "labels":
                    close_box(pg, k)
            pg.evaluate("() => NMSKModes.enter('inj')"); pg.wait_for_selector("#mode-main .mc-left", timeout=60000); pg.wait_for_timeout(1800)
            pg.evaluate("() => { const c = document.querySelector('.mc-pick .mc-close'); if (c) c.click(); }"); pg.wait_for_timeout(700)
            for k in ("m-dist", "m-plan"):
                r = rect(pg, k)
                check(f"reload: {k} comes back at its saved size", r and MID.get(k) and abs(r["width"] - MID[k][0]) <= 6 and abs(r["height"] - MID[k][1]) <= 6, (r and (r["width"], r["height"]), MID.get(k)))
            pg.evaluate("() => NMSKModes.exit()"); pg.wait_for_timeout(900)
            hide_sheet(pg)

            # ---- E. lock ----
            settings_open(pg); pg.check("#q382-lock"); settings_close(pg); pg.wait_for_timeout(600)
            before = rect(pg, "pose"); hover(pg, "pose")
            check("lock: the resize grip is gone", grip(pg, "pose") is None)
            g = pg.evaluate("""() => { const r = document.getElementById('pose-panel').getBoundingClientRect(); return [r.right - 5, r.bottom - 5]; }""")
            pg.mouse.move(*g); pg.mouse.down(); pg.mouse.move(g[0] - 80, g[1] - 80, steps=6); pg.mouse.up(); pg.wait_for_timeout(500)
            after = rect(pg, "pose")
            check("lock: a drag at the corner does not resize", after and abs(after["width"] - before["width"]) <= 1 and abs(after["height"] - before["height"]) <= 1, (before, after))
            settings_open(pg); pg.uncheck("#q382-lock"); settings_close(pg); pg.wait_for_timeout(600)
            hover(pg, "pose")
            check("lock off: the grip is back", grip(pg, "pose") is not None)

            # ---- F. Reset layout ----
            settings_open(pg); pg.click("#q382-reset"); pg.wait_for_timeout(900); settings_close(pg)
            tp = text(pg, "pose"); tl = text(pg, "labels")
            check("reset: the pose and labels boxes lose their resize (no size, no class)", "q386-s" not in tp["cls"] and "q386-s" not in tl["cls"]
                  and pg.evaluate("() => !NMSKResize.size('pose') && !NMSKResize.size('labels') && !NMSKResize.size('qcard')"), (tp["cls"], tl["cls"]))
            check("reset: the per-box text size is gone, the all-boxes one stays", abs(tp["z"] - 1.5) < 0.02 and pg.evaluate("() => NMSKResize.global() === 150 && !NMSKResize.own('pose')"), tp["z"])
            settings_open(pg); pg.select_option("#q386-g", "100"); pg.wait_for_timeout(900); settings_close(pg)
            t = text(pg, "pose"); rp, rl = rect(pg, "pose"), rect(pg, "labels")
            check("all boxes 100 %: nothing is left on the box (no class, no zoom)", t["z"] == 1 and "q386" not in t["cls"], t["cls"])
            check("reset: the pose and labels boxes are at their own size again", rp and rl and abs(rp["width"] - base["pose"]["width"]) <= 4 and abs(rp["height"] - base["pose"]["height"]) <= 4
                  and abs(rl["width"] - base["labels"]["width"]) <= 6, (rp, base["pose"], rl, base["labels"]))
            pg.close(); ctx.close()
        else:
            ctx, pg = boot(br)
            check("phone: the gear is hidden, Settings is reached by Navigate > Settings", pg.evaluate("() => !document.getElementById('q382-gear')"))
            js(pg, "document.getElementById('qg-view').click()", wait=800)
            check("phone: the Navigate group has a Settings button", pg.evaluate("() => !!document.getElementById('q382-settings')"))
            js(pg, "document.getElementById('q382-settings').click()", wait=700)
            sp = pg.evaluate("""() => { const p = document.getElementById('q382-panel'); const r = p.getBoundingClientRect(); const s = document.getElementById('q386-g'); return {vis: !p.hidden, l: r.left, t: r.top, r: r.right, b: r.bottom, sel: !!s && s.offsetParent !== null, ov: getComputedStyle(p).overflowY, sh: p.scrollHeight, ch: p.clientHeight}; }""")
            check("phone: Settings opens on the screen with the text size select", sp["vis"] and sp["sel"] and sp["l"] >= -1 and sp["r"] <= W + 1 and sp["b"] <= H + 1, sp)
            check("phone: the Settings panel scrolls", sp["ov"] in ("auto", "scroll"), sp["ov"])
            shot(pg, "phone_settings")
            pg.select_option("#q386-g", "150"); pg.wait_for_timeout(900); settings_close(pg)
            check("phone: no resize grip", pg.evaluate("() => [...document.querySelectorAll('.q386-ov')].every(o => o.hidden)"))
            base0 = {}
            ensure_open(pg, "pose"); ensure_open(pg, "labels"); open_qcard(pg)
            for k in ("pose", "labels", "qcard"):
                t = text(pg, k)
                if not t:
                    check(f"phone: {k} opened", False); continue
                check(f"phone: {k} takes the 150 % text size", abs(t["z"] - 1.5) < 0.02 or (t["z"] > 1.0 and k == "pose"), t["z"])
                check(f"phone: {k} stays on the screen", t["l"] >= -1 and t["t"] >= -1 and t["r"] <= W + 1 and t["b"] <= H + 1, (round(t["l"]), round(t["t"]), round(t["r"]), round(t["b"])))
                check(f"phone: {k} scrolls inside", t["ov"] in ("auto", "scroll"), t["ov"])
            shot(pg, "phone_150")
            # per-box override from Settings
            settings_open(pg)
            has = pg.evaluate("() => !!document.querySelector('#q386-rows select[data-k=labels]')")
            check("phone: Settings has a row for the Labels box", has)
            if has:
                pg.select_option("#q386-rows select[data-k=labels]", "120"); pg.wait_for_timeout(800)
                check("phone: the Labels row sets its own text size", abs(text(pg, "labels")["z"] - 1.2) < 0.02, text(pg, "labels")["z"])
                pg.select_option("#q386-rows select[data-k=labels]", ""); pg.wait_for_timeout(600)
            settings_close(pg)
            # floor at 80 %
            t0 = text(pg, "labels")
            settings_open(pg); pg.select_option("#q386-g", "80"); pg.wait_for_timeout(900); settings_close(pg)
            t1 = text(pg, "labels")
            check("phone: 80 % never goes under the 10 px floor", t1["eff"] >= min(t0["min"], 10) - 0.06, (t1["min"], t1["z"], t1["eff"]))
            settings_open(pg); pg.select_option("#q386-g", "160"); pg.wait_for_timeout(900); settings_close(pg)
            # the open group sheet
            js(pg, "document.getElementById('qg-view').click()", wait=900)
            ts = text(pg, "#q301-sheet")
            check("phone: the open group sheet takes the text size and stays on the screen", ts and ts["z"] > 1.4 and ts["t"] >= -1 and ts["b"] <= H + 1 and ts["r"] <= W + 1, ts and (ts["z"], round(ts["t"]), round(ts["b"])))
            check("phone: the open group sheet scrolls", ts and ts["ov"] in ("auto", "scroll"), ts and ts["ov"])
            shot(pg, "phone_160_sheet")
            pg.close(); ctx, pg = boot(br, ctx)
            check("phone: the text size survives a reload", pg.evaluate("() => NMSKResize.global() === 160"))
            settings_open(pg); pg.select_option("#q386-g", "100"); pg.wait_for_timeout(500); settings_close(pg)
            pg.close(); ctx.close()

        # ---- storage disabled ----
        ctx, pg = boot(br, block=True)
        if not phone:
            ensure_open(pg, "pose")
            r0 = rect(pg, "pose"); hover(pg, "pose")
            r1 = drag_to(pg, "pose", -120, -150)
            check("storage disabled: a box still resizes", r0 and r1 and r1["width"] < r0["width"] - 60, (r0 and r0["width"], r1 and r1["width"]))
        settings_open(pg)
        pg.select_option("#q386-g", "130"); pg.wait_for_timeout(700); settings_close(pg)
        if not phone:
            check("storage disabled: the text size still applies", abs(text(pg, "pose")["z"] - 1.3) < 0.02, text(pg, "pose")["z"])
        else:
            check("storage disabled: the text size still applies", pg.evaluate("() => NMSKResize.global() === 130"))
        ctx.close(); br.close()
    srv.terminate()
    check("0 page errors", not perr, perr[:3])
    print("Q386_RESIZE_OK" if not errs else "Q386_RESIZE_FAIL " + "; ".join(errs[:6]))
    return 0 if not errs else 1


if __name__ == "__main__":
    raise SystemExit(main())
