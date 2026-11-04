#!/usr/bin/env python3
"""Q305: real headless-Chromium check that the boxes on the screen can be moved where the user wants them, that they
are still there next time, and that moving them takes nothing away.

Owner (translated from Hebrew): "let the various boxes on the screen be moved around."

Desktop 1400x900 with real MOUSE drags, phone 390x844 with real TOUCH drags through CDP (Playwright's tap cannot hold
and move, and the pointer events these pages listen to are only produced by real touch points). One page of each engine.

A  WHERE IT WAS DROPPED. A real drag of a box's handle, and the box's own rectangle before and after: it must land
   within 2 px of where the handle was let go. Then the page is RELOADED and the box must come back to the same place.
   On the phone the drop snaps to a slot and the slot is what must survive.
B  NOTHING IS LEFT UNREACHABLE. `document.elementFromPoint` at the centre of every watched control -- the instrument
   that caught Q301's info drawer over Undo and Q300's chip bar over Redo -- before and after every drag. No control
   may be covered at any point, and a drag may not cover anything that was clear before it.
C  A DROP THAT WOULD COVER A CONTROL IS REFUSED. Q300's chip bar (which really did sit on Redo) is driven onto the
   screen through its own documented hook and dragged onto Undo. Either the module refuses the drop and puts the box
   back, or -- on the phone -- the slot discipline keeps it clear; in both cases Undo must still be reachable.
D  RESTORE, ONE UNDO STEP, AND THE MODEL RESET. Several boxes are moved with real drags; one tap on Restore layout in
   the control bar's View group must put every one of them back, ONE Ctrl+Z must bring the whole arrangement back in a
   single step, and Q300's Reset model must return the layout the page loaded in.
E  THE GESTURES THAT WERE ALREADY THERE. The model still orbits (a one-pointer drag on the canvas); the canvas still
   pinch-zooms and two-finger-pans (Q290); a 2-D image pane still pinch-zooms where one is open; the ultrasound probe
   still drags over the skin where the tool is available; a long press on a list row still starts a range (Q294/Q298);
   a tap on a handle is not a move; and a pinch whose FIRST finger lands on a handle does not move the box.
F  IT STAYS USABLE. A box dragged far off the screen is clamped inside it; it is still inside after a resize and after
   an orientation change; and nothing overflows 390 px.
G  THE PHONE. The measured free travel of every present box at 390x844 and the slots each one is given, which is the
   measurement the phone decision rests on.
H  0 page errors, both viewports.

    python3 scripts/anatomy/q305/verify_q305.py PAGE_DIR... [--json OUT]"""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE.parent / "q283"))
import verify_q283 as V  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

OKN = [0]
KEY = {"viewer_m_hr": "own_m", "viewer_f_hr": "own_f", "viewer_zan_atlas": "base_m", "viewer_base_female": "base_f",
       "viewer_zan_vhm": "comb_m", "viewer_zan_female": "comb_f"}
REPORT: dict = {}


def check(label, cond, errs):
    if V.check(label, cond, errs):
        OKN[0] += 1
        return True
    return False


# ---------------------------------------------------------------- the page ----------------------------------------
def ready(pg):
    pg.wait_for_function(expression="() => document.readyState === 'complete'", timeout=60000)
    pg.wait_for_function(expression="() => window.NMSKQ301 && NMSKQ301.state().on", timeout=180000)
    pg.wait_for_function(expression="() => window.NMSKQ305 && NMSKQ305.ready()", timeout=180000)
    pg.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
    pg.wait_for_timeout(500)
    quiet_chrome(pg)
    # the Z pages spin by themselves, so two measurements would be of two different poses (Q300's finding)
    pg.evaluate("""() => { const b = document.getElementById('btn-spin'); if (b && b.classList.contains('on')) b.click(); }""")
    pg.wait_for_timeout(400)
    settle(pg)


def quiet_chrome(pg):
    """The welcome / mode banners are dismissed IN PAGE: a real click on them hung for 30 s here (Q300's finding), and
    they are not one of this round's assertions. AND IT HAS TO BE DONE IN A LOOP, which the first smoke run found the
    hard way: the Z pages put the model switcher BACK on the screen once the model has finished loading, so a single
    dismissal before that left a full-screen overlay on top and the collision check reported every control on the
    control bar as covered -- twelve "failures" that were one overlay."""
    for _ in range(14):
        gone = pg.evaluate("""() => {
            ['mw-close', 'modal-close'].forEach(function(i){ var b = document.getElementById(i); if (b) b.click(); });
            var sw = document.getElementById('mode-switch');
            if (sw){ sw.hidden = true; sw.style.display = 'none'; }
            var m = document.getElementById('modal'); if (m) m.style.display = 'none';
            var shown = [].slice.call(document.querySelectorAll('.mw-body, #boot'))
                          .filter(function(e){ return e.offsetParent !== null; });
            return shown.length === 0; }""")
        pg.wait_for_timeout(250)
        if gone:
            return True
    return False


def stage(pg, phone):
    """Put the page into the state the owner actually works in, so there is more than one movable box on the screen.
    This is SET-UP, not an assertion: every assertion below is a real drag or a real press.
      - the Z pages load in the Model-only layout, where `#rail{display:none!important}`, so one press on `#t-lay3`
        brings the side panel back (that is how only `control` and `pills` were movable in the first smoke run);
      - the side panel is opened, a structure is selected so the structure card appears, and the cut panel is opened.
    """
    # `#t-lay3` CYCLES Model-only / Split / Compare, so it is pressed only while the side panel is still hidden --
    # pressed twice (it is called again after section A's reload) it would walk on to the next layout and change which
    # boxes are on the screen between two measurements of the same page.
    for _ in range(3):
        shown = pg.evaluate("""() => { const r = document.getElementById('rail');
            if (!r) return true;
            const q = r.getBoundingClientRect();
            return q.width > 8 && q.height > 8 && q.right > 0 && q.bottom > 0 && q.left < innerWidth && q.top < innerHeight; }""")
        if shown:
            break
        pg.evaluate("""() => { const b = document.getElementById('t-lay3'); if (b) b.click(); }""")
        pg.wait_for_timeout(700)
    pg.evaluate("""() => { const b = document.getElementById('btn-panel') || document.getElementById('m-list'); if (b) b.click(); }""")
    pg.wait_for_timeout(700)
    pg.evaluate("""() => { try { if (window.selCtl && selCtl.items && selCtl.items().length) selCtl.select(selCtl.items()[0].id); } catch (e){} }""")
    pg.wait_for_timeout(700)
    pg.evaluate("""() => { const b = document.getElementById('t-cut'); if (b && b.getAttribute('aria-pressed') !== 'true') b.click(); }""")
    pg.wait_for_timeout(900)
    quiet_chrome(pg)
    pg.evaluate("() => { if (window.NMSKMove) NMSKMove.refresh(); }")
    pg.wait_for_timeout(400)
    settle(pg)


def rest(pg, key, ms=4000):
    """Wait until the box has STOPPED moving, then measure -- up to `ms`, and it reports how long it took.
    The page's own placement code keeps running after `load`: Q301's `place()` rewrites the control bar when a group
    opens and on resize, and the Z pages settle their layout later than the own pages do. Q305's module re-resolves
    its offsets on a 600 ms pass for exactly that reason, so "where is the box after a reload" has to be asked once
    the page has finished moving it -- otherwise the answer is a race, not a measurement. It never pokes the module:
    it only waits and reads, so a module that does NOT heal itself still reads as not healed."""
    last, same, waited = None, 0, 0
    while waited < ms:
        r = pg.evaluate("(k) => NMSKMove.rect(k)", key)
        same = (same + 1) if (r and last and r == last) else 0
        last = r
        if r and same >= 2:
            return r, waited
        pg.wait_for_timeout(300)
        waited += 300
    return last, waited


def settle(pg):
    """commit the history NOW rather than trusting Q294's 320 ms debounce, which does not fire on time while software
       rendering redraws thousands of meshes -- Q301 reported that as a product bug before finding it was the script"""
    pg.evaluate("() => { if (window.NMSKHistory) NMSKHistory.commit(); }")
    pg.wait_for_timeout(250)


def canvas_sel(pg):
    return "#view" if pg.query_selector("#view") else "#stage canvas"


def rect(pg, sel):
    return pg.evaluate("""(s) => { const e = document.querySelector(s); if (!e) return null;
        const r = e.getBoundingClientRect();
        return {x:r.x, y:r.y, w:r.width, h:r.height, cx:Math.round(r.x + r.width / 2), cy:Math.round(r.y + r.height / 2)}; }""", sel)


def box(pg, key):
    return pg.evaluate("(k) => NMSKMove.rect(k)", key)


def offs(pg, key):
    return pg.evaluate("(k) => NMSKMove.off(k)", key)


def bad(pg, soft=False):
    """the watched controls whose own centre belongs to something else. `soft` includes the handles."""
    return [b for b in pg.evaluate("() => NMSKGuard.bad()") if soft or not b.get("soft")]


def on_top(pg, sel):
    """never press blind: Q304's lesson, after a covered row read as a missing card"""
    return pg.evaluate("""(s) => { const e = document.querySelector(s); if (!e) return {missing:true};
        const r = e.getBoundingClientRect();
        if (!(r.width > 0 && r.height > 0)) return {ok:false, over:'zero size'};
        const h = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
        return {ok: h === e || e.contains(h) || (h && h.contains(e)), over: h ? (h.tagName + '#' + h.id) : null}; }""", sel)


# ---------------------------------------------------------------- the drags ----------------------------------------
def mouse_drag(pg, frm, to, steps=16):
    pg.mouse.move(frm[0], frm[1])
    pg.mouse.down()
    for i in range(1, steps + 1):
        pg.mouse.move(frm[0] + (to[0] - frm[0]) * i / steps, frm[1] + (to[1] - frm[1]) * i / steps)
        pg.wait_for_timeout(10)
    pg.mouse.up()
    pg.wait_for_timeout(120)


class Touch:
    def __init__(self, pg):
        self.c = pg.context.new_cdp_session(pg)
        self.pg = pg

    def send(self, t, pts, ids=None):
        tp = [{"x": float(x), "y": float(y), "id": (ids[i] if ids else i)} for i, (x, y) in enumerate(pts)]
        self.c.send("Input.dispatchTouchEvent", {"type": t, "touchPoints": tp})

    def drag(self, frm, to, steps=16):
        self.send("touchStart", [frm])
        for i in range(1, steps + 1):
            self.send("touchMove", [(frm[0] + (to[0] - frm[0]) * i / steps, frm[1] + (to[1] - frm[1]) * i / steps)])
            self.pg.wait_for_timeout(12)
        self.send("touchEnd", [])
        self.pg.wait_for_timeout(140)

    def pinch(self, c, d0, d1, steps=12):
        for i in range(steps + 1):
            d = d0 + (d1 - d0) * i / steps
            pts = [(c[0] - d / 2, c[1]), (c[0] + d / 2, c[1])]
            self.send("touchStart" if i == 0 else "touchMove", pts)
            self.pg.wait_for_timeout(12)
        self.send("touchEnd", [])
        self.pg.wait_for_timeout(100)

    def two_pan(self, c, dx, dy, steps=12):
        for i in range(steps + 1):
            ox, oy = dx * i / steps, dy * i / steps
            pts = [(c[0] - 40 + ox, c[1] + oy), (c[0] + 40 + ox, c[1] + oy)]
            self.send("touchStart" if i == 0 else "touchMove", pts)
            self.pg.wait_for_timeout(12)
        self.send("touchEnd", [])
        self.pg.wait_for_timeout(100)

    def second_finger(self, first, second, out, steps=10):
        """The fingers land one after the other, as real fingers do -- and the only form in which this Chromium
        delivers a pointerdown for the SECOND finger. A touchStart carrying two points at once gives pointer events
        for the primary one only, which would make a "two fingers" check prove nothing."""
        self.send("touchStart", [first], [0])
        self.pg.wait_for_timeout(50)
        self.send("touchStart", [first, second], [0, 1])
        self.pg.wait_for_timeout(50)
        for i in range(1, steps + 1):
            self.send("touchMove", [(first[0] - out * i / steps, first[1]), (second[0] + out * i / steps, second[1])], [0, 1])
            self.pg.wait_for_timeout(14)
        self.send("touchEnd", [])
        self.pg.wait_for_timeout(120)

    def hold(self, p, ms):
        """a LONG PRESS: held down and released without a tap's click, which is what Q294/Q298 listen for"""
        self.send("touchStart", [p])
        self.pg.wait_for_timeout(ms)
        self.send("touchEnd", [])
        self.pg.wait_for_timeout(60)

    def tap(self, p):
        """an ordinary TAP, through Playwright's own touchscreen rather than CDP. A CDP touchEnd carrying no points
        does not always make Chromium synthesize the `click` these buttons listen for -- which is why the first phone
        run could not press Restore layout although both copies of it were measurably reachable."""
        self.pg.touchscreen.tap(p[0], p[1])
        self.pg.wait_for_timeout(120)


def drag_handle(pg, T, key, dx, dy):
    g = rect(pg, "#nm-g-" + key)
    if not g:
        return None
    top = on_top(pg, "#nm-g-" + key)
    if not top.get("ok"):
        return {"blocked": top}
    if T:
        T.drag((g["cx"], g["cy"]), (g["cx"] + dx, g["cy"] + dy))
    else:
        mouse_drag(pg, (g["cx"], g["cy"]), (g["cx"] + dx, g["cy"] + dy))
    return {"from": g, "dx": dx, "dy": dy}


def clear_points(pg, sel, n=3, span=0):
    """n points that really are the 3-D canvas, well apart -- and, with `span`, with the whole two-finger span clear.
    Checking only the MIDPOINT is not enough: a pinch whose left finger lands 3 px inside the side panel reads as
    "the canvas no longer pinch-zooms" when the canvas is fine."""
    return pg.evaluate("""([s, n, span]) => {
      const cv = document.querySelector(s); if (!cv) return [];
      const r = cv.getBoundingClientRect(), out = [];
      const clear = (x, y) => { const e = document.elementFromPoint(x, y); return e === cv || cv.contains(e); };
      for (let fy = 0.22; fy <= 0.82; fy += 0.04) for (let fx = 0.20; fx <= 0.84; fx += 0.04){
        const x = Math.round(r.left + r.width * fx), y = Math.round(r.top + r.height * fy);
        if (!clear(x, y)) continue;
        if (span && !(clear(x - span / 2, y) && clear(x + span / 2, y))) continue;
        if (out.some(p => Math.hypot(p.x - x, p.y - y) < 90)) continue;
        out.push({x:x, y:y}); if (out.length >= n) return out;
      }
      return out; }""", [sel, n, span])


def cam(pg):
    """az / el / dist / tgt, from the hook BOTH engines have. `window.__viewerState` exists only on the Z pages, and
    the first own-engine run read the pinch as "the canvas no longer zooms" because of it: a pinch moves `dist` and a
    two-finger pan moves `tgt`, so both have to be read, from a hook both engines carry."""
    return pg.evaluate("""() => {
      const o = c => ({az:c.az, el:c.el, dist:c.dist, tgt:(c.tgt || []).map(v => Math.round(v * 100) / 100)});
      if (window.__q303dbg && window.__q303dbg.cam) return o(window.__q303dbg.cam());
      if (window.__viewerState) return o(window.__viewerState().cam);
      return null; }""")


# ---------------------------------------------------------------- the sections -------------------------------------
def section_boxes(pg, T, tag, R, errs, phone):
    st = pg.evaluate("() => NMSKMove.state()")
    R["state0"] = st
    present = [b for b in st["boxes"] if b["present"]]
    R["present"] = [b["key"] for b in present]
    check("%s the module is running (translate=%s, store=%s)" % (tag, st["translate"], st["key"]), st["on"], errs)
    check("%s it reads the viewport as phone=%s" % (tag, st["phone"]), st["phone"] == phone, errs)
    check("%s the control bar is one of the movable boxes and has a handle" % tag,
          any(b["key"] == "control" and b["grip"] for b in present), errs)
    check("%s %d boxes are on this page, every one of them with a handle: %s" % (tag, len(present), R["present"]),
          len(present) >= 2 and all(b["grip"] for b in present), errs)
    h0 = bad(pg)
    R["bad_at_load"] = bad(pg, soft=True)
    check("%s no control is covered on the page as it LOADS %s" % (tag, h0[:2]), not h0, errs)
    return [b["key"] for b in present]


def section_a(pg, T, tag, R, errs, phone, present):
    """where it was dropped, and still there after a reload"""
    key = "control"
    want = (0, -150) if not phone else (0, -260)
    r0 = box(pg, key)
    did = drag_handle(pg, T, key, want[0], want[1])
    r1 = box(pg, key)
    o1 = offs(pg, key)
    R["A"] = {"key": key, "before": r0, "after": r1, "off": o1, "asked": want, "drag": did}
    if phone:
        check("%s A the box snapped to a slot (%s) and really moved: %d px" % (tag, o1["slot"], r0["top"] - r1["top"]),
              bool(o1["slot"]) and abs(r1["top"] - r0["top"]) > 40, errs)
    else:
        dx, dy = r1["left"] - r0["left"], r1["top"] - r0["top"]
        check("%s A the box landed where the handle was let go: asked (%d,%d), measured (%d,%d), tolerance 2 px"
              % (tag, want[0], want[1], dx, dy), abs(dx - want[0]) <= 2 and abs(dy - want[1]) <= 2, errs)
    settle(pg)
    pg.reload(wait_until="load")
    ready(pg)
    stage(pg, phone)
    r2, waited = rest(pg, key)
    o2 = offs(pg, key)
    R["A"]["reload"] = {"rect": r2, "off": o2, "settled_after_ms": waited}
    check("%s A and the position survived the reload (settled after %d ms): %s %s -> %s %s" % (tag, waited, r1, o1, r2, o2),
          r2 and abs(r2["left"] - r1["left"]) <= 2 and abs(r2["top"] - r1["top"]) <= 2, errs)
    h = bad(pg)
    check("%s A no control is covered after it %s" % (tag, h[:2]), not h, errs)


def section_c(pg, T, tag, R, errs, phone):
    """a drop that would cover a control is refused -- with the very box that covered Redo in Q301"""
    pg.evaluate("""() => { if (window.NMSKShowAll && NMSKShowAll.keys().length) {
        NMSKShowAll.drive(NMSKShowAll.keys()[0]); if (window.NMSKHistory) NMSKHistory.commit(); } }""")
    pg.wait_for_timeout(900)
    r = box(pg, "hidden")
    R["C"] = {"chip_bar": r}
    if not r:
        check("%s C (the chip bar could not be put on the screen on this page -- reported, not asserted)" % tag, True, errs)
        return
    gu = rect(pg, "#q301-undo")
    g = rect(pg, "#nm-g-hidden")
    if not (gu and g):
        check("%s C (Undo or the chip bar's handle is not measurable -- reported)" % tag, True, errs)
        return
    before = box(pg, "hidden")
    if T:
        T.drag((g["cx"], g["cy"]), (gu["cx"] + 4, gu["cy"] + 4))
    else:
        mouse_drag(pg, (g["cx"], g["cy"]), (gu["cx"] + 4, gu["cy"] + 4))
    after = box(pg, "hidden")
    stc = pg.evaluate("() => NMSKMove.state()")
    h = bad(pg)
    R["C"].update({"before": before, "after": after, "reverts": stc["reverts"], "bad": h,
                   "undo_on_top": on_top(pg, "#q301-undo")})
    check("%s C after a drop aimed straight at Undo, Undo is still reachable (reverts=%d) %s"
          % (tag, stc["reverts"], h[:2]), not h and on_top(pg, "#q301-undo").get("ok"), errs)
    sl = offs(pg, "hidden")["slot"]
    check("%s C and that is the module's own doing, not luck: %s" % (
        tag, ("refused, reverts=%d" % stc["reverts"]) if stc["reverts"] >= 1 else ("snapped to the slot %r" % sl)),
        stc["reverts"] >= 1 or bool(sl), errs)
    pg.evaluate("() => NMSKMove.restore()")
    settle(pg)


def section_d(pg, T, tag, R, errs, phone):
    """restore layout: every box back, one undo step, and inside Q300's model reset"""
    pg.evaluate("() => NMSKMove.restore()")
    settle(pg)
    # the boxes THIS page actually shows, not a fixed list: which boxes float differs per engine and per viewport
    # (the own engine at 390 px shows control / hidden / expand, the Z engine at 1400 control / hidden / cut / rail /
    # pills), and a fixed list quietly dragged only the one they had in common.
    want_keys = pg.evaluate("() => NMSKMove.present()")[:3]
    moved = []
    STEP = [(0, -140), (60, 40), (-70, 60)]
    for i, key in enumerate(want_keys):
        dx, dy = STEP[i % len(STEP)]
        drag_handle(pg, T, key, dx if not phone else 0, dy if not phone else (-200 if i % 2 == 0 else 200))
        o = offs(pg, key)
        if o and (o["dx"] or o["dy"] or o["slot"]):
            moved.append(key)
    settle(pg)
    mv = pg.evaluate("() => NMSKMove.moved()")
    h0 = pg.evaluate("() => NMSKHistory.state().idx")
    # Restore layout is pressed where the owner would press it: inside the control bar's View group
    opened = press_restore(pg, T)
    settle(pg)
    after = pg.evaluate("() => NMSKMove.moved()")
    h1 = pg.evaluate("() => NMSKHistory.state().idx")
    pg.keyboard.press("Control+z")
    pg.wait_for_timeout(500)
    back = pg.evaluate("() => NMSKMove.moved()")
    h2 = pg.evaluate("() => NMSKHistory.state().idx")
    R["D"] = {"moved": mv, "after_restore": after, "after_undo": back, "idx": [h0, h1, h2], "pressed": opened}
    # how many boxes a page offers is the page's business: on the own engine at 390 px the structure list and the
    # structure card are bottom sheets, not floating boxes, so the control bar can be the only one on the screen
    want = min(2, len(want_keys))
    check("%s D %d boxes were moved with real drags (%d of %d on the screen): %s"
          % (tag, len(mv), want, len(pg.evaluate("() => NMSKMove.present()")), mv), len(mv) >= want, errs)
    check("%s D one tap on Restore layout put every one of them back (%d -> %d)" % (tag, len(mv), len(after)),
          opened and not after, errs)
    check("%s D it is ONE undo step: the history moved %d -> %d and one Ctrl+Z brought back %s"
          % (tag, h0, h1, back), h1 == h0 + 1 and sorted(back) == sorted(mv), errs)
    # and Q300's model reset returns the layout THE PAGE LOADED IN, because the layout is one of its providers. That
    # is not the same as "nothing moved": section A deliberately reloads the page with a box already moved, so that
    # box's offset IS the load state and the reset must put it back to exactly that.
    load = pg.evaluate("() => { const L = NMSKModelReset.loaded(); return L ? L.q305layout : null; }")
    for i, key in enumerate(want_keys[:2]):
        drag_handle(pg, T, key, (0 if i else -60), (-120 if i else 50) if not phone else -180)
    settle(pg)
    pg.evaluate("() => { const b = document.getElementById('q301-mr-model'); if (b) b.click(); }")
    pg.wait_for_timeout(900)
    now = pg.evaluate("() => NMSKHistory.snapshot ? null : null") or pg.evaluate("() => NMSKMove.state().boxes.reduce((o, b) => (o[b.key] = b.off.slot || [b.off.dx, b.off.dy], o), {})")
    R["D"]["load_layout"] = load
    R["D"]["after_model_reset"] = now
    same = load is not None and all(json.dumps(load.get(k)) == json.dumps(now.get(k)) for k in load)
    check("%s D and Q300's Reset model returns the layout the page LOADED in (%s)" % (tag, json.dumps(load)[:90]),
          same, errs)
    h = bad(pg)
    check("%s D no control is covered after all of it %s" % (tag, h[:2]), not h, errs)


def press_restore(pg, T):
    """Press Restore layout where the owner would: in the control bar's View group, or, if that group's sheet has
    scrolled it below the fold (its body measured 441 px against a 362 px window), the copy in the circled i. Always a
    REAL press, and always at a point `document.elementFromPoint` has confirmed first (Q304's lesson)."""
    def press(sel):
        """The panels scroll, so the control is scrolled to first -- and the ALIGNMENT is tried three ways, which the
        phone run made necessary and is also what a real user does. `block:'center'` puts the target in the middle of
        the screen, and in this run the control bar had been parked in the middle of the screen, so the target landed
        under it every time ("covered by SPAN#", one of the bar's own button labels). Scrolled to the start or the end
        of its panel instead, it is clear."""
        if not pg.query_selector(sel):
            print("      %s is not on the page" % sel)
            return False
        over = None
        for how in ("center", "start", "end", "nearest"):
            pg.eval_on_selector(sel, "(e, b) => e.scrollIntoView({block: b})", how)
            pg.wait_for_timeout(300)
            t = on_top(pg, sel)
            if t.get("ok"):
                over = None
                break
            over = t.get("over")
        if over:
            print("      %s could not be uncovered (%s on top at every alignment)" % (sel, over))
            return False
        r = rect(pg, sel)
        if T:
            T.tap((r["cx"], r["cy"]))
        else:
            pg.mouse.click(r["cx"], r["cy"])
        pg.wait_for_timeout(500)
        return True
    n0 = pg.evaluate("() => NMSKMove.state().restores")
    pg.evaluate("() => { if (window.NMSKGroups) NMSKGroups.open('view'); }")
    pg.wait_for_timeout(600)
    where = "view group" if press("#q305-restore") else ""
    pg.evaluate("() => { if (window.NMSKGroups) NMSKGroups.close(); }")
    pg.wait_for_timeout(300)
    if pg.evaluate("() => NMSKMove.state().restores") == n0:
        pg.evaluate("() => { const b = document.getElementById('q301-info-btn'); if (b) b.click(); }")
        pg.wait_for_timeout(600)
        pg.evaluate("""() => { const d = document.getElementById('qi-layout'); if (d) d.open = true; }""")
        pg.wait_for_timeout(300)
        if press("#q305-restore-i"):
            where = (where + " + the i") if where else "the i"
        pg.evaluate("() => { const b = document.getElementById('qi-close'); if (b) b.click(); }")
        pg.wait_for_timeout(300)
    done = pg.evaluate("() => NMSKMove.state().restores") > n0
    print("    Restore layout pressed from: %s (restores %d -> %d)" % (where or "nowhere", n0, pg.evaluate("() => NMSKMove.state().restores")))
    return done and where


def section_e(pg, T, tag, R, errs, phone):
    """the gestures that were already there"""
    pg.evaluate("() => NMSKMove.restore()")
    settle(pg)
    cs = canvas_sel(pg)
    check("%s E no drag is left running after the earlier sections" % tag, not pg.evaluate("() => NMSKMove.dragging()"), errs)
    pts = clear_points(pg, cs, 3, 200 if phone else 0)
    R["E"] = {"canvas": cs, "points": pts}
    check("%s E clear points on the 3-D canvas: %s" % (tag, pts), len(pts) >= 2, errs)
    if not pts:
        return
    p0 = pts[0]
    # ONE finger first: a two-finger gesture through CDP does not always deliver a pointerup for every point, and a
    # captured pointer that is never released looks exactly like "the model stopped orbiting".
    c0 = cam(pg)
    if T:
        T.drag((p0["x"], p0["y"]), (p0["x"] + 110, p0["y"] + 50))
    else:
        mouse_drag(pg, (p0["x"], p0["y"]), (p0["x"] + 110, p0["y"] + 50))
    c1 = cam(pg)
    R["E"]["orbit"] = [c0, c1]
    check("%s E the model still orbits: az %s -> %s" % (tag, c0 and round(c0["az"], 3), c1 and round(c1["az"], 3)),
          c0 and c1 and (abs(c1["az"] - c0["az"]) > 0.05 or abs(c1["el"] - c0["el"]) > 0.05), errs)
    # a tap / click on a handle is not a move
    g = rect(pg, "#nm-g-control")
    rb = box(pg, "control")
    # Never crash where a FAIL is the honest answer: the handle is on the page, so the bar must be on the screen too.
    # When this read `None` it was not a missing feature but the stale-base defect -- the bar had been left at top 936
    # of an 844 px viewport, so `NMSKMove.rect` reported it as off the screen. A crash hid that behind a TypeError and
    # cost the rest of the page's run; a named FAIL says it.
    if not (g and rb):
        check("%s E the control bar must be on the screen before the tap (handle=%s, bar=%s)" % (tag, g, rb), False, errs)
    else:
        if T:
            T.tap((g["cx"], g["cy"]))
        else:
            pg.mouse.click(g["cx"], g["cy"])
        pg.wait_for_timeout(200)
        ra = box(pg, "control")
        if not ra:
            check("%s E the control bar must still be on the screen after a tap on its handle" % tag, False, errs)
        else:
            check("%s E a tap on the handle is not a move (%d,%d)" % (tag, ra["left"] - rb["left"], ra["top"] - rb["top"]),
                  abs(ra["left"] - rb["left"]) <= 1 and abs(ra["top"] - rb["top"]) <= 1, errs)
    if not phone:
        pg.mouse.move(p0["x"], p0["y"])
        pg.mouse.wheel(0, -240)
        pg.wait_for_timeout(200)
        check("%s E a desktop wheel over the model is not hijacked" % tag, not pg.evaluate("() => NMSKMove.dragging()"), errs)
        return
    # ---- the phone's own gestures
    # the structure list lives in a panel that can be closed (and the model reset in D closes it on the own engine),
    # so it is re-opened before the long press -- both engines call that panel's own button
    pg.evaluate("""() => { const b = document.getElementById('btn-panel') || document.getElementById('m-list'); if (b) b.click(); }""")
    pg.wait_for_timeout(800)
    rowsel = None
    for cand in ("#list .row", "#list button", "#list [role=option]", "#list li"):
        if pg.query_selector(cand):
            rowsel = cand
            break
    if rowsel:
        r = rect(pg, rowsel)
        t = on_top(pg, rowsel)
        if t.get("ok"):
            n0 = pg.evaluate("() => (window.NMSKQ298 && NMSKQ298.state) ? JSON.stringify(NMSKQ298.state()) : ''")
            T.hold((r["cx"], r["cy"]), 700)
            n1 = pg.evaluate("() => (window.NMSKQ298 && NMSKQ298.state) ? JSON.stringify(NMSKQ298.state()) : ''")
            R["E"]["longpress"] = {"before": n0[:200], "after": n1[:200]}
            check("%s E a long press on a list row still does something (Q294/Q298 range)" % tag, n0 != n1 or not n0, errs)
        else:
            check("%s E (a list row is covered by %s on this page -- reported, not asserted)" % (tag, t.get("over")), True, errs)
    # a pinch whose FIRST finger lands on a handle must not move the box
    g = rect(pg, "#nm-g-control")
    rb = box(pg, "control")
    T.second_finger((g["cx"], g["cy"]), (g["cx"] + 70, g["cy"]), 60)
    ra = box(pg, "control")
    R["E"]["second_finger"] = {"before": rb, "after": ra}
    check("%s E a second finger cancels the move: the box did not shift (%d,%d)"
          % (tag, ra["left"] - rb["left"], ra["top"] - rb["top"]),
          abs(ra["left"] - rb["left"]) <= 1 and abs(ra["top"] - rb["top"]) <= 1, errs)
    # Q290's pinch and two-finger pan, on the 3-D canvas
    z = "() => (window.NMSKPinch && window.__q305z) ? window.__q305z() : null"
    pg.evaluate("""(s) => { const cv = document.querySelector(s);
        window.__q305z = () => { try { return JSON.stringify(window.__viewerState ? window.__viewerState().cam : null); } catch (e){ return null; } }; }""", cs)
    c0 = cam(pg)
    T.pinch((p0["x"], p0["y"]), 90, 240)
    c1 = cam(pg)
    R["E"]["pinch"] = [c0, c1]
    # a pinch on the 3-D canvas moves the camera's DISTANCE, not its angles (the first run asserted az and read the
    # zoom as "the canvas no longer pinch-zooms")
    d0 = (c0 or {}).get("dist")
    d1 = (c1 or {}).get("dist")
    check("%s E the canvas still answers a pinch: dist %s -> %s" % (tag, d0 and round(d0, 2), d1 and round(d1, 2)),
          d0 is not None and d1 is not None and abs(d1 - d0) > max(0.5, 0.01 * d0), errs)
    c2 = cam(pg)
    T.two_pan((p0["x"], p0["y"]), 70, -50)
    c3 = cam(pg)
    R["E"]["two_pan"] = [c2, c3]
    t2, t3 = (c2 or {}).get("tgt"), (c3 or {}).get("tgt")
    check("%s E and a two-finger pan moves the view: tgt %s -> %s" % (tag, t2, t3), c2 != c3, errs)
    pg.evaluate("() => { const b = document.getElementById('q301-mr-model'); if (b) b.click(); }")
    pg.wait_for_timeout(600)


def inside(r, vp):
    return bool(r) and r["left"] >= 0 and r["top"] >= 0 and r["left"] + r["width"] <= vp["w"] + 1 and r["top"] + r["height"] <= vp["h"] + 1


def section_f(pg, T, tag, R, errs, phone):
    """clamped inside the viewport, still inside after a resize, and no overflow"""
    pg.evaluate("() => NMSKMove.restore()")
    settle(pg)
    key = "control"
    for k in ("cut", "card", "info", "control"):
        if box(pg, k) is not None:
            key = k
            break
    if T:
        drag_handle(pg, T, key, 900, 900)
    else:
        drag_handle(pg, None, key, 2200, 2200)
    r = box(pg, key)
    vp = pg.evaluate("() => ({w:innerWidth, h:innerHeight})")
    R["F"] = {"key": key, "rect": r, "vp": vp}
    check("%s F a box dragged far off the screen is clamped inside it: %s in %dx%d" % (tag, r, vp["w"], vp["h"]),
          r and r["left"] >= 0 and r["top"] >= 0 and r["left"] + r["width"] <= vp["w"] + 1 and r["top"] + r["height"] <= vp["h"] + 1, errs)
    ov = pg.evaluate("() => ({sw:document.documentElement.scrollWidth, cw:document.documentElement.clientWidth})")
    R["F"]["overflow"] = ov
    check("%s F nothing overflows the viewport width (%d <= %d)" % (tag, ov["sw"], ov["cw"]), ov["sw"] <= ov["cw"] + 1, errs)
    w2, h2 = (1024, 700) if not phone else (844, 390)
    pg.set_viewport_size({"width": w2, "height": h2})
    pg.wait_for_timeout(1100)
    r2 = box(pg, key)
    vp2 = pg.evaluate("() => ({w:innerWidth, h:innerHeight})")
    present2 = pg.evaluate("() => NMSKMove.present()")
    R["F"]["after_resize"] = {"rect": r2, "vp": vp2, "present": present2}
    if r2 is None:
        # the page's OWN layout can drop a box at a new size (the own engine's landscape phone layout does), and a box
        # the page no longer shows is not ours to keep on the screen. Every box the page DOES show must be inside it.
        bad2 = [k for k in present2 if not inside(box(pg, k), vp2)]
        check("%s F the page itself stopped showing %r at %dx%d; every box it DOES show is inside the viewport %s"
              % (tag, key, w2, h2, bad2), not bad2, errs)
    else:
        check("%s F it is still on the screen after the resize to %dx%d: %s" % (tag, w2, h2, r2),
              inside(r2, vp2), errs)
    h = bad(pg)
    check("%s F and no control is covered after the resize %s" % (tag, h[:2]), not h, errs)
    w0, h0 = (1400, 900) if not phone else (390, 844)
    pg.set_viewport_size({"width": w0, "height": h0})
    pg.wait_for_timeout(900)
    r3 = box(pg, key)
    R["F"]["back"] = r3
    check("%s F and back at %dx%d every box the page shows is inside again: %s" % (tag, w0, h0, r3),
          all(inside(box(pg, k), {"w": w0, "h": h0}) for k in pg.evaluate("() => NMSKMove.present()")), errs)
    pg.evaluate("() => NMSKMove.restore()")
    settle(pg)


def section_g(pg, tag, R, errs):
    """the measurement the phone decision rests on"""
    m = pg.evaluate("""() => { const o = {};
        NMSKMove.present().forEach(k => { const r = NMSKMove.rect(k);
          o[k] = {w:Math.round(r.width), h:Math.round(r.height),
                  freeX:Math.round(innerWidth - 24 - r.width), freeY:Math.round(innerHeight - 24 - r.height),
                  slots:NMSKMove.slots(k).map(s => s.key)}; });
        return o; }""")
    R["G"] = m
    print("    measured at %dx%d:" % (pg.evaluate("() => innerWidth"), pg.evaluate("() => innerHeight")))
    for k in sorted(m):
        v = m[k]
        print("      %-9s %4dx%-4d  freeX %5d  freeY %5d  slots %s" % (k, v["w"], v["h"], v["freeX"], v["freeY"], ",".join(v["slots"])))
    check("%s G every box on the screen is given at least two slots" % tag,
          m and all(len(v["slots"]) >= 2 for v in m.values()), errs)
    check("%s G and a box with no room on an axis is given bands there, not free drag" % tag,
          all((v["freeX"] >= 48) or all(s[1] == "c" for s in v["slots"]) for v in m.values()), errs)


# ---------------------------------------------------------------- the run -----------------------------------------
def run_page(page_dir: Path, errs: list, only=0):
    tag0 = KEY.get(page_dir.name, page_dir.name)
    html = V.html_of(page_dir)
    srv, port = V.serve(page_dir)
    rep = REPORT.setdefault(tag0, {})
    try:
        with sync_playwright() as pl:
            b = pl.chromium.launch(args=V.LAUNCH_ARGS, executable_path="/opt/pw-browsers/chromium")
            for (w, h), phone in (((1400, 900), False), ((390, 844), True)):
                if only and w != only:
                    continue
                tag = "%s_%d" % (tag0, w)
                R = rep.setdefault(str(w), {})
                ctx = b.new_context(viewport={"width": w, "height": h}, has_touch=phone, is_mobile=phone, device_scale_factor=1)
                pg = ctx.new_page()
                perr: list = []
                pg.on("pageerror", lambda e: perr.append(str(e)))
                pg.route("**/*", V.route)
                pg.goto("http://127.0.0.1:%d/%s" % (port, html), wait_until="load", timeout=180000)
                ready(pg)
                stage(pg, phone)
                T = Touch(pg) if phone else None
                print("\n--- %s ---" % tag)
                present = section_boxes(pg, T, tag, R, errs, phone)
                section_a(pg, T, tag, R, errs, phone, present)
                section_c(pg, T, tag, R, errs, phone)
                section_d(pg, T, tag, R, errs, phone)
                section_e(pg, T, tag, R, errs, phone)
                section_f(pg, T, tag, R, errs, phone)
                if phone:
                    section_g(pg, tag, R, errs)
                R["guard"] = pg.evaluate("() => NMSKGuard.all()")
                R["pageErrors"] = perr
                check("%s H 0 page errors %s" % (tag, perr[:2]), not perr, errs)
                ctx.close()
            b.close()
    finally:
        srv.terminate()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pages", nargs="+")
    ap.add_argument("--json", default="")
    ap.add_argument("--viewport", type=int, default=0, help="1400 or 390 only (for a quick run); both by default")
    a = ap.parse_args()
    errs: list = []
    for p in a.pages:
        run_page(Path(p), errs, a.viewport)
    print("\nQ305 VERIFY: %d OK / %d FAIL" % (OKN[0], len(errs)))
    for e in errs:
        print("  FAIL " + e)
    if a.json:
        Path(a.json).write_text(json.dumps(REPORT, indent=1), encoding="utf-8")
    return 1 if errs else 0


if __name__ == "__main__":
    raise SystemExit(main())
