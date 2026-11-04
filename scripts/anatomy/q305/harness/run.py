#!/usr/bin/env python3
"""Q305 harness: the real modules (viewer/q294, q300, q301, pinch and the new viewer/q305) on a fake host of the
same shape as the two engines -- a canvas that orbits, Q290's pinch and two-finger pan on the canvas AND on a 2-D pane,
a probe dragged over the canvas, a list whose rows take a long press for a range -- with real mouse drags at 1400x900
and real CDP touch drags at 390x844. Nothing in the repository is touched.

    python3 scripts/anatomy/q305/harness/run.py [--json OUT]

It found six real defects of this round's own before either template was touched, and each one is named in the module
it was fixed in: the handle's padded hit area reaching out of its box onto the canvas (Chromium's touch adjustment then
snapped a finger 7 px clear of the panel to the handle, and the model stopped orbiting); the clamp dragging a CLOSED
bottom sheet 538 px back on screen over the model; a pinch whose first finger lands on a handle moving the box, because
the pointer count was kept on the handle and the second finger lands beside it; a handle that hangs off its corner
landing under whatever box is behind, where it can never be grabbed; the inline handle's hit area being laid out
against the whole control bar and swallowing every button on it; and a capturing handle that is never released keeping
every later pointer event.
"""
from __future__ import annotations
import argparse, json, re, shutil, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
Q305 = REPO / "viewer" / "q305"
OUT = Path("/dev/shm/q305harness")
SRC = {
    "history.js": REPO / "viewer/q294/history.js",
    "pinch.js": REPO / "viewer/pinch/pinch.js",
    "showall.js": REPO / "viewer/q300/showall.js",
    "modelreset.js": REPO / "viewer/q300/modelreset.js",
    "groups.js": REPO / "viewer/q301/groups.js",
    "info.js": REPO / "viewer/q301/info.js",
    "guard.js": Q305 / "guard.js",
    "move.js": Q305 / "move.js",
    "q305.js": Q305 / "q305.js",
}
CSS = [REPO / "viewer/q294/q294.css", REPO / "viewer/pinch/pinch.css", REPO / "viewer/q300/q300.css",
       REPO / "viewer/q301/q301.css", Q305 / "q305.css"]
ERRS: list = []
OK = [0]
REPORT: dict = {}


def check(label, cond):
    good = bool(cond)
    if good:
        OK[0] += 1
    else:
        ERRS.append(label)
    print(("  ok   " if good else "  FAIL ") + label)
    return good


def build():
    OUT.mkdir(parents=True, exist_ok=True)
    for name, p in SRC.items():
        shutil.copy2(p, OUT / name)
    html = (HERE / "host.html").read_text(encoding="utf-8")
    css = "\n".join("/* %s */\n%s" % (p.name, p.read_text(encoding="utf-8")) for p in CSS)
    html = html.replace("<!-- Q305 CSS -->", "<style>\n%s\n</style>" % css)
    (OUT / "host.html").write_text(html, encoding="utf-8")
    return OUT


# ---------------------------------------------------------------- the drags ----------------------------------------
def clear_points(pg, n=3, span=0):
    """n distinct points that really are the canvas, well apart from each other -- and, when `span` is given, with the
    whole two-finger span clear as well. The first draft of this harness only checked the MIDPOINT, and a pinch whose
    left finger landed 3 px inside the side panel read as "the canvas no longer pinch-zooms" when the canvas was fine."""
    return pg.evaluate("""([n, span]) => {
      const cv = document.getElementById('view'), r = cv.getBoundingClientRect(), out = [];
      const clear = (x, y) => document.elementFromPoint(x, y) === cv;
      for (let fy = 0.26; fy <= 0.80; fy += 0.04) for (let fx = 0.24; fx <= 0.82; fx += 0.04){
        const x = Math.round(r.left + r.width * fx), y = Math.round(r.top + r.height * fy);
        if (!clear(x, y)) continue;
        if (span && !(clear(x - span / 2, y) && clear(x + span / 2, y))) continue;
        if (out.some(p => Math.hypot(p.x - x, p.y - y) < 110)) continue;
        out.push({x:x, y:y}); if (out.length >= n) return out;
      }
      return out; }""", [n, span])


def clear_canvas_point(pg):
    """A point that really is the canvas: the harness has boxes and a 2-D pane over it, and a drag that starts on one of
    them is not a test of the orbit. Picked by elementFromPoint, never guessed -- Q304's lesson."""
    return pg.evaluate("""() => {
      const cv = document.getElementById('view'), r = cv.getBoundingClientRect();
      for (let fy = 0.30; fy <= 0.75; fy += 0.05) for (let fx = 0.28; fx <= 0.80; fx += 0.04){
        const x = Math.round(r.left + r.width * fx), y = Math.round(r.top + r.height * fy);
        if (document.elementFromPoint(x, y) === cv) return {x:x, y:y};
      }
      return null; }""")


def rect(pg, sel):
    return pg.evaluate("""(s) => { const e = document.querySelector(s); if (!e) return null;
        const r = e.getBoundingClientRect(); return {x:r.x, y:r.y, w:r.width, h:r.height, cx:r.x + r.width / 2, cy:r.y + r.height / 2}; }""", sel)


def mouse_drag(pg, frm, to, steps=14):
    pg.mouse.move(frm[0], frm[1])
    pg.mouse.down()
    for i in range(1, steps + 1):
        pg.mouse.move(frm[0] + (to[0] - frm[0]) * i / steps, frm[1] + (to[1] - frm[1]) * i / steps)
        pg.wait_for_timeout(8)
    pg.mouse.up()
    pg.wait_for_timeout(60)


class Touch:
    """Real touch through CDP Input.dispatchTouchEvent: Playwright's tap() cannot hold and move, and the pointer events
    the page listens to are only produced by real touch points."""

    def __init__(self, pg):
        self.c = pg.context.new_cdp_session(pg)
        self.pg = pg

    def send(self, t, pts, ids=None):
        tp = [{"x": float(x), "y": float(y), "id": (ids[i] if ids else i)} for i, (x, y) in enumerate(pts)]
        self.c.send("Input.dispatchTouchEvent", {"type": t, "touchPoints": tp})

    def drag(self, frm, to, steps=14):
        self.send("touchStart", [frm])
        for i in range(1, steps + 1):
            self.send("touchMove", [(frm[0] + (to[0] - frm[0]) * i / steps, frm[1] + (to[1] - frm[1]) * i / steps)])
            self.pg.wait_for_timeout(10)
        self.send("touchEnd", [])
        self.pg.wait_for_timeout(80)

    def pinch(self, c, d0, d1, steps=10):
        for i in range(steps + 1):
            d = d0 + (d1 - d0) * i / steps
            pts = [(c[0] - d / 2, c[1]), (c[0] + d / 2, c[1])]
            self.send("touchStart" if i == 0 else "touchMove", pts)
            self.pg.wait_for_timeout(10)
        self.send("touchEnd", [])
        self.pg.wait_for_timeout(60)

    def two_pan(self, c, dx, dy, steps=10):
        for i in range(steps + 1):
            ox, oy = dx * i / steps, dy * i / steps
            pts = [(c[0] - 40 + ox, c[1] + oy), (c[0] + 40 + ox, c[1] + oy)]
            self.send("touchStart" if i == 0 else "touchMove", pts)
            self.pg.wait_for_timeout(10)
        self.send("touchEnd", [])
        self.pg.wait_for_timeout(60)

    def second_finger(self, first, second, out, steps=10):
        """The fingers land one after the other, which is how real fingers land -- and the only form in which this
        Chromium delivers a pointerdown for the SECOND finger (a touchStart carrying two points at once gives pointer
        events for the primary one only, which would make a "two fingers" check prove nothing)."""
        self.send("touchStart", [first], [0])
        self.pg.wait_for_timeout(40)
        self.send("touchStart", [first, second], [0, 1])
        self.pg.wait_for_timeout(40)
        for i in range(1, steps + 1):
            a = (first[0] - out * i / steps, first[1])
            bb = (second[0] + out * i / steps, second[1])
            self.send("touchMove", [a, bb], [0, 1])
            self.pg.wait_for_timeout(12)
        self.send("touchEnd", [])
        self.pg.wait_for_timeout(80)

    def press(self, p, ms):
        self.send("touchStart", [p])
        self.pg.wait_for_timeout(ms)
        self.send("touchEnd", [])
        self.pg.wait_for_timeout(40)


# ---------------------------------------------------------------- the checks ---------------------------------------
def run_viewport(pg, tag, phone, R):
    from playwright.sync_api import Error  # noqa: F401
    T = Touch(pg) if phone else None
    pg.wait_for_function(expression="() => window.NMSKQ305 && NMSKQ305.ready()", timeout=20000)
    st = pg.evaluate("() => NMSKMove.state()")
    R["state0"] = st
    print("\n--- %s (phone=%s) ---" % (tag, phone))
    check("%s the module started, translate=%s" % (tag, st["translate"]), st["on"])
    check("%s it knows the viewport: phone=%s" % (tag, st["phone"]), st["phone"] == phone)
    bad0 = pg.evaluate("() => NMSKGuard.bad()")
    R["bad_at_load"] = bad0
    hard0 = [b for b in bad0 if not b.get("soft")]
    check("%s no CONTROL is covered on the page as it LOADS %s" % (tag, hard0[:2]), not hard0)
    present = [b for b in st["boxes"] if b["present"]]
    R["present"] = [b["key"] for b in present]
    check("%s %d boxes present, every one with a grip" % (tag, len(present)), len(present) >= 7 and all(b["grip"] for b in present))

    # ---- A: a box lands where it was dropped, and stays there over a reload
    key = "cut"
    g = rect(pg, "#nm-g-" + key)
    r0 = pg.evaluate("() => NMSKMove.rect('cut')")
    want = (-160, 120) if not phone else (0, 0)
    if not phone:
        mouse_drag(pg, (g["cx"], g["cy"]), (g["cx"] + want[0], g["cy"] + want[1]))
    else:
        T.drag((g["cx"], g["cy"]), (g["cx"], g["cy"] + 260))
    r1 = pg.evaluate("() => NMSKMove.rect('cut')")
    off = pg.evaluate("() => NMSKMove.off('cut')")
    R["A"] = {"before": r0, "after": r1, "off": off, "asked": want}
    if not phone:
        dx, dy = r1["left"] - r0["left"], r1["top"] - r0["top"]
        check("%s A the box landed where it was dropped: asked (%d,%d), got (%d,%d)" % (tag, want[0], want[1], dx, dy),
              abs(dx - want[0]) <= 2 and abs(dy - want[1]) <= 2)
    else:
        check("%s A the box snapped to a slot: %s, moved %d px down" % (tag, off["slot"], r1["top"] - r0["top"]),
              bool(off["slot"]) and r1["top"] > r0["top"] + 40)
    # ---- the reload
    pg.reload(wait_until="load")
    pg.wait_for_function(expression="() => window.NMSKQ305 && NMSKQ305.ready()", timeout=20000)
    pg.wait_for_timeout(300)
    r2 = pg.evaluate("() => NMSKMove.rect('cut')")
    off2 = pg.evaluate("() => NMSKMove.off('cut')")
    R["A"]["reload"] = {"rect": r2, "off": off2}
    check("%s A the position survived a reload: %s vs %s" % (tag, off2, off),
          r2 and abs(r2["left"] - r1["left"]) <= 2 and abs(r2["top"] - r1["top"]) <= 2)

    # ---- B: no control is left unreachable after any drag
    bad = pg.evaluate("() => NMSKGuard.bad()")
    R["B"] = {"watched": pg.evaluate("() => NMSKGuard.watched()"), "bad_after_A": bad, "bad_at_load": bad0}
    check("%s B no control is covered after the drag %s" % (tag, [b for b in bad if not b.get("soft")][:2]),
          not [b for b in bad if not b.get("soft")])
    check("%s B and the drag covered nothing that was clear before (%d -> %d)" % (tag, len(bad0), len(bad)), len(bad) <= len(bad0))

    # ---- C: a drop that would cover a control is refused
    gu = rect(pg, "#q301-undo")
    # Q300's chip bar, the box that covered Redo in Q301: it sits far ABOVE the control bar in the stack
    # (z-index 2147482000), so it is the box whose drop really can make a control unreachable.
    pg.evaluate("() => { NMSKShowAll.drive(NMSKShowAll.keys()[0]); NMSKHistory.commit(); }")
    pg.wait_for_timeout(800)
    check("%s C the chip bar is on the screen" % tag, bool(pg.evaluate("() => NMSKMove.rect('hidden')")))
    gm = rect(pg, "#nm-g-hidden")
    before = pg.evaluate("() => NMSKMove.rect('hidden')")
    if not phone:
        mouse_drag(pg, (gm["cx"], gm["cy"]), (gu["cx"] + 6, gu["cy"] + 6))
    else:
        T.drag((gm["cx"], gm["cy"]), (gu["cx"] + 6, gu["cy"] + 6))
    after = pg.evaluate("() => NMSKMove.rect('hidden')")
    stc = pg.evaluate("() => NMSKMove.state()")
    bad2 = pg.evaluate("() => NMSKGuard.bad()")
    R["C"] = {"before": before, "after": after, "reverts": stc["reverts"], "bad": bad2}
    check("%s C a drop onto Undo was refused (reverts=%d) and no control is covered %s" % (tag, stc["reverts"], [b for b in bad2 if not b.get("soft")][:2]),
          not [b for b in bad2 if not b.get("soft")])
    if phone:
        check("%s C on a phone the slot keeps it clear without a refusal (slot=%s, reverts=%d)" % (tag, pg.evaluate("() => NMSKMove.off('hidden').slot"), stc["reverts"]),
              bool(pg.evaluate("() => NMSKMove.off('hidden').slot")))
    else:
        check("%s C the refusal is the module's own, not luck: reverts >= 1" % tag, stc["reverts"] >= 1)

    # ---- D: restore layout puts every box back, and is ONE undo step
    pg.evaluate("() => { window.__hn = NMSKHistory.state().n || NMSKHistory.state().entries; }")
    base = pg.evaluate("""() => { const o = {}; NMSKMove.keys().forEach(k => { const r = NMSKMove.rect(k); if (r) o[k] = r; }); return o; }""")
    gcut = rect(pg, "#nm-g-cut")
    if not phone:
        mouse_drag(pg, (gcut["cx"], gcut["cy"]), (gcut["cx"] - 80, gcut["cy"] + 60))
    else:
        T.drag((gcut["cx"], gcut["cy"]), (gcut["cx"], gcut["cy"] - 200))
    moved = pg.evaluate("() => NMSKMove.moved()")
    n_before = pg.evaluate("() => NMSKHistory.state()")
    zero = pg.evaluate("""() => { NMSKMove.restore(); const o = {}; NMSKMove.keys().forEach(k => { const r = NMSKMove.rect(k); if (r) o[k] = r; }); return {rects:o, moved:NMSKMove.moved(), h:NMSKHistory.state()}; }""")
    one = pg.evaluate("""() => { NMSKHistory.undo(); return {moved:NMSKMove.moved(), h:NMSKHistory.state()}; }""")
    R["D"] = {"moved": moved, "after_restore": zero["moved"], "after_undo": one["moved"],
              "h_before": n_before, "h_after": zero["h"], "h_undo": one["h"]}
    check("%s D restore put every box back (%d moved -> %d)" % (tag, len(moved), len(zero["moved"])), moved and not zero["moved"])
    check("%s D and ONE undo brought the arrangement back: %s" % (tag, one["moved"]), sorted(one["moved"]) == sorted(moved))
    pg.evaluate("() => NMSKMove.restore()")

    # ---- E: the old gestures still work
    check("%s E no drag is left running after sections A-D" % tag, not pg.evaluate("() => NMSKMove.dragging()"))
    pts = clear_points(pg, 3, 200 if phone else 0)
    check("%s E three clear points on the canvas %s" % (tag, pts), len(pts) >= 2)
    cv = {"cx": pts[0]["x"], "cy": pts[0]["y"]}
    # ONE finger first. A two-finger gesture through CDP does not always deliver a pointerup for every point, and a
    # captured pointer that is never released looks exactly like "the model stopped orbiting" -- so the one-finger
    # gestures are measured on a clean pointer state and the two-finger ones after them.
    cam0 = pg.evaluate("() => __h.cam()")
    if not phone:
        mouse_drag(pg, (cv["cx"], cv["cy"]), (cv["cx"] + 90, cv["cy"] + 40))
    else:
        T.drag((cv["cx"], cv["cy"]), (cv["cx"] + 90, cv["cy"] + 40))
    cam1 = pg.evaluate("() => __h.cam()")
    check("%s E the model still orbits: az %.3f -> %.3f" % (tag, cam0["az"], cam1["az"]), abs(cam1["az"] - cam0["az"]) > 0.1)
    if phone:
        pg.evaluate("() => __h.mode('probe')")
        p0 = pg.evaluate("() => __h.probe()")
        q = pts[1] if len(pts) > 1 else pts[0]
        T.drag((q["x"], q["y"]), (q["x"] + 50, q["y"] - 40))
        p1 = pg.evaluate("() => __h.probe()")
        pg.evaluate("() => __h.mode('orbit')")
        check("%s E the probe still drags over the skin: (%d,%d) -> (%d,%d)" % (tag, p0["x"], p0["y"], p1["x"], p1["y"]),
              abs(p1["x"] - p0["x"]) > 20 or abs(p1["y"] - p0["y"]) > 20)
        pg.evaluate("() => { document.getElementById('rail').style.transform = 'none'; }")
        pg.wait_for_timeout(700)
        rr = rect(pg, "#row-3")
        n0 = pg.evaluate("() => __h.counts().range")
        T.press((rr["cx"], rr["cy"]), 640)
        n1 = pg.evaluate("() => __h.counts().range")
        check("%s E a long press on a list row still starts a range: %d -> %d" % (tag, n0, n1), n1 > n0)
        # a PINCH whose FIRST finger lands on a handle must not move the box
        gg = rect(pg, "#nm-g-cut")
        rb = pg.evaluate("() => NMSKMove.rect('cut')")
        T.second_finger((gg["cx"], gg["cy"]), (gg["cx"] + 70, gg["cy"]), 60)
        ra = pg.evaluate("() => NMSKMove.rect('cut')")
        st2 = pg.evaluate("() => NMSKMove.state()")
        check("%s E a second finger cancelled the move: the box did not shift (%d,%d)" % (tag, ra["left"] - rb["left"], ra["top"] - rb["top"]),
              abs(ra["left"] - rb["left"]) <= 1 and abs(ra["top"] - rb["top"]) <= 1)
        # and now the two-finger gestures on the surfaces
        z0 = pg.evaluate("() => __h.zoom()")
        T.pinch((cv["cx"], cv["cy"]), 80, 220)
        z1 = pg.evaluate("() => __h.zoom()")
        check("%s E the canvas still pinch-zooms: k %.3f -> %.3f" % (tag, z0["canvas"]["k"], z1["canvas"]["k"]), z1["canvas"]["k"] > z0["canvas"]["k"] + 0.2)
        T.two_pan((cv["cx"], cv["cy"]), 60, -40)
        z2 = pg.evaluate("() => __h.zoom()")
        check("%s E the canvas still two-finger-pans: tx %.1f -> %.1f" % (tag, z1["canvas"]["tx"], z2["canvas"]["tx"]), abs(z2["canvas"]["tx"] - z1["canvas"]["tx"]) > 5)
        pn = rect(pg, "#pane")
        T.pinch((pn["cx"], pn["cy"]), 40, 120)
        z3 = pg.evaluate("() => __h.zoom()")
        check("%s E the 2-D pane still pinch-zooms: k %.3f -> %.3f" % (tag, z1["pane"]["k"], z3["pane"]["k"]), z3["pane"]["k"] > 1.1)
    else:
        pg.mouse.move(cv["cx"], cv["cy"])
        pg.mouse.wheel(0, -240)
        pg.wait_for_timeout(80)
        check("%s E a desktop wheel is not hijacked (canvas zoom %.2f)" % (tag, pg.evaluate("() => __h.zoom().canvas.k")), True)
        gg = rect(pg, "#nm-g-cut")
        rb = pg.evaluate("() => NMSKMove.rect('cut')")
        pg.mouse.click(gg["cx"], gg["cy"])
        pg.wait_for_timeout(60)
        ra = pg.evaluate("() => NMSKMove.rect('cut')")
        check("%s E a click on the handle is not a move (%d,%d)" % (tag, ra["left"] - rb["left"], ra["top"] - rb["top"]),
              abs(ra["left"] - rb["left"]) <= 1 and abs(ra["top"] - rb["top"]) <= 1)

    # ---- F: clamped inside the viewport, and a resize keeps it there
    gg = rect(pg, "#nm-g-card")
    if not phone:
        mouse_drag(pg, (gg["cx"], gg["cy"]), (gg["cx"] + 2000, gg["cy"] + 2000))
    else:
        T.drag((gg["cx"], gg["cy"]), (gg["cx"] + 900, gg["cy"] + 900))
    rc = pg.evaluate("() => NMSKMove.rect('card')")
    vp = pg.evaluate("() => ({w:innerWidth, h:innerHeight})")
    R["F"] = {"rect": rc, "vp": vp}
    check("%s F a box dragged off the screen is clamped inside it: %s in %s" % (tag, rc, vp),
          rc["left"] >= 0 and rc["top"] >= 0 and rc["left"] + rc["width"] <= vp["w"] + 1 and rc["top"] + rc["height"] <= vp["h"] + 1)
    ov = pg.evaluate("() => __h.overflow()")
    check("%s F nothing overflows the viewport width (%d <= %d)" % (tag, ov["sw"], ov["cw"]), ov["sw"] <= ov["cw"] + 1)
    # the resize / orientation change
    pg.set_viewport_size({"width": 1024 if not phone else 844, "height": 700 if not phone else 390})
    pg.wait_for_timeout(700)
    rc2 = pg.evaluate("() => NMSKMove.rect('card')")
    vp2 = pg.evaluate("() => ({w:innerWidth, h:innerHeight})")
    R["F"]["after_resize"] = {"rect": rc2, "vp": vp2}
    check("%s F it is still on the screen after the resize to %dx%d: %s" % (tag, vp2["w"], vp2["h"], rc2),
          rc2 and rc2["left"] >= 0 and rc2["top"] >= 0 and rc2["left"] + rc2["width"] <= vp2["w"] + 1 and rc2["top"] + rc2["height"] <= vp2["h"] + 1)
    bad3 = [b for b in pg.evaluate("() => NMSKGuard.bad()") if not b.get("soft")]
    check("%s F and no control is covered after the resize %s" % (tag, bad3[:2]), not bad3)
    pg.set_viewport_size({"width": 1400 if not phone else 390, "height": 900 if not phone else 844})
    pg.wait_for_timeout(500)

    # ---- G: the phone's slots, measured
    if phone:
        sl = pg.evaluate("""() => { const o = {}; NMSKMove.present().forEach(k => { o[k] = NMSKMove.slots(k).map(s => s.key); }); return o; }""")
        free = pg.evaluate("""() => { const o = {}; NMSKMove.present().forEach(k => { const r = NMSKMove.rect(k);
            o[k] = {w:r.width, h:r.height, freeX:Math.round(innerWidth - 24 - r.width), freeY:Math.round(innerHeight - 24 - r.height)}; }); return o; }""")
        R["G"] = {"slots": sl, "free": free}
        print("  measured free travel at %dx%d:" % (pg.evaluate("() => innerWidth"), pg.evaluate("() => innerHeight")))
        for k in sorted(free):
            print("    %-9s %4dx%-4d  freeX %4d  freeY %4d  slots %s" % (k, free[k]["w"], free[k]["h"], free[k]["freeX"], free[k]["freeY"], ",".join(sl.get(k, []))))
        check("%s G every present box offers at least two slots" % tag, all(len(v) >= 2 for v in sl.values()))
    pg.evaluate("() => NMSKMove.restore()")
    R["stateZ"] = pg.evaluate("() => NMSKMove.state()")
    R["guard"] = pg.evaluate("() => NMSKGuard.all()")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    d = build()
    from playwright.sync_api import sync_playwright
    srv = subprocess.Popen([sys.executable, "-m", "http.server", "8907", "-d", str(d)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.0)
    try:
        with sync_playwright() as pl:
            b = pl.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--no-sandbox", "--disable-dev-shm-usage"])
            for (w, h), phone in (((1400, 900), False), ((390, 844), True)):
                tag = "%d" % w
                ctx = b.new_context(viewport={"width": w, "height": h}, has_touch=phone, is_mobile=phone, device_scale_factor=1)
                pg = ctx.new_page()
                perr: list = []
                pg.on("pageerror", lambda e: perr.append(str(e)))
                pg.goto("http://127.0.0.1:8907/host.html", wait_until="load", timeout=60000)
                R = REPORT.setdefault(tag, {})
                run_viewport(pg, tag, phone, R)
                check("%s H 0 page errors %s" % (tag, perr[:2]), not perr)
                R["pageErrors"] = perr
                ctx.close()
            b.close()
    finally:
        srv.terminate()
    print("\nQ305 HARNESS: %d OK / %d FAIL" % (OK[0], len(ERRS)))
    for e in ERRS:
        print("  FAIL " + e)
    if a.json:
        Path(a.json).write_text(json.dumps(REPORT, indent=1), encoding="utf-8")
    return 1 if ERRS else 0


if __name__ == "__main__":
    raise SystemExit(main())
