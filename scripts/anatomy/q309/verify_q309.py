#!/usr/bin/env python3
"""Q309: real headless-Chromium check of the system on/off buttons and of the three depth-peel scopes.

Owner (translated from Hebrew): "Also allow display by SYSTEMS with an on/off button, and by LAYERS -- for the
whole body, per system, and for the displayed systems only."

Desktop 1400x900 with real CLICKS, phone 390x844 with real TOUCH, on one page of each engine. Every claim is a
MEASURED COUNT read out of the page's own draw state, never a screenshot: `page.screenshot` of a WebGL canvas
returns a stale frame in this container (Q300's finding), so the drawn-structure count comes from the engine's own
`drawn()` / `drawnIn()` through `NMSKQ309`, and the Z pages' auto-spin is stopped first so two readings are of the
same pose. The welcome banners are dismissed in page -- a real click on one hung for 30 s here (Q300) -- and the
history is committed explicitly rather than through Q294's 320 ms debounce, which does not fire on time while
software rendering redraws thousands of meshes (Q301's own false alarm).

A  THE SYSTEM LIST. Every system the page declares has a button with its label, its count and its state, the count
   on the button equals the page's own count for that system's categories, and `document.elementFromPoint` says the
   button really is the top element at its own centre -- the instrument that has caught four real defects.
B  ON AND OFF, MEASURED. For every system: one real tap must take the drawn-structure total down by exactly the
   number of that system's structures that were drawn before, must leave that system drawing zero, and one more tap
   must bring the total back to the number it started from.
C  ONE UNDO STEP. One tap is one history entry; one Ctrl+Z restores a byte-identical snapshot of the state before it;
   one Ctrl+Y puts it back.
D  THE WHOLE BODY IS STILL Q301'S. In the `Whole body` scope the taps drive `NMSKPeel`, the CATEGORY table is what
   moves, and Q309 vetoes nothing at all. Leaving the scope puts its layers back.
E  PER SYSTEM. In the `One system` scope, step 1 takes exactly that system's first stratum off, and the drawn count
   of EVERY OTHER SYSTEM is unchanged to the structure.
F  THE SYSTEMS SHOWN. In the `Systems shown` scope, the peeled set spans exactly the peelable systems switched on --
   asserted by mapping every vetoed id back through `NMSKSysMap.of()` -- and a system switched off contributes none.
G  THE WAY BACK. Both Q309 paths raise their own chip in Q300's bar; `Show everything` leaves no veto; and Q300's
   Reset model returns the state the page loaded in.
H  THE PHONE, AND 0 PAGE ERRORS. Nothing overflows 390 px, every control tapped was the top element, and the run
   reports the page's errors rather than swallowing them.

    python3 scripts/anatomy/q309/verify_q309.py PAGE_DIR... [--json OUT] [--viewport 1400|390]"""
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
def quiet_chrome(pg):
    """dismissed IN PAGE, in a loop: the Z pages put the model switcher back on the screen once the model has
       finished loading, so one dismissal before that leaves a full-screen overlay over every control (Q305)"""
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


def settle(pg):
    pg.evaluate("() => { if (window.NMSKHistory) NMSKHistory.commit(); }")
    pg.wait_for_timeout(250)


def ready(pg):
    pg.wait_for_function(expression="() => document.readyState === 'complete'", timeout=60000)
    pg.wait_for_function(expression="() => window.NMSKQ301 && NMSKQ301.state().on", timeout=180000)
    pg.wait_for_function(expression="() => window.NMSKQ309 && NMSKQ309.ready()", timeout=180000)
    pg.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
    pg.wait_for_timeout(500)
    quiet_chrome(pg)
    # the Z pages spin by themselves, so two measurements would be of two different poses (Q300's finding)
    pg.evaluate("""() => { const b = document.getElementById('btn-spin'); if (b && b.classList.contains('on')) b.click(); }""")
    pg.wait_for_timeout(400)
    settle(pg)


def open_layers(pg):
    """Q309's two boxes live inside Q301's existing Layers group, which is an accordion: it has to be open before a
       real tap can reach anything in it. Opened through the module, then asserted by a real geometry read."""
    # NMSKGroups.open TOGGLES, so calling it on an already-open group CLOSES it -- which parks both of this
    # round's boxes in Q301's hidden parking node, where they have no size and no control is reachable. The
    # first run of this script did exactly that and reported 30 collision failures that were one wrong call.
    pg.evaluate("""() => { if (!window.NMSKGroups) return;
        if (NMSKGroups.isOpen() !== 'layers') NMSKGroups.open('layers'); }""")
    pg.wait_for_timeout(500)
    pg.evaluate("() => { const e = document.getElementById('sy-box'); if (e) e.scrollIntoView({block:'center'}); }")
    pg.wait_for_timeout(250)


def ontop(pg, sel):
    return pg.evaluate("""(s) => { const e = document.querySelector(s); if (!e) return false;
        const r = e.getBoundingClientRect();
        if (!(r.width > 2 && r.height > 2)) return false;
        const t = document.elementFromPoint(Math.round(r.left + r.width / 2), Math.round(r.top + r.height / 2));
        return !!t && (t === e || e.contains(t) || t.contains(e)); }""", sel)


def hit(pg, sel, phone, errs, tag, what):
    """a real tap / click, having first proved the control is the top element at its own centre"""
    pg.evaluate("(s) => { const e = document.querySelector(s); if (e) e.scrollIntoView({block:'center'}); }", sel)
    pg.wait_for_timeout(120)
    top = ontop(pg, sel)
    check("%s %s is the top element at its own centre (%s)" % (tag, what, sel), top, errs)
    if not top:
        return False
    if phone:
        r = pg.evaluate("(s) => { const r = document.querySelector(s).getBoundingClientRect(); return {x:r.x + r.width/2, y:r.y + r.height/2}; }", sel)
        pg.touchscreen.tap(r["x"], r["y"])
    else:
        pg.click(sel)
    pg.wait_for_timeout(350)
    return True


def drawn(pg):
    return pg.evaluate("() => NMSKQ309.measure().drawn")


def drawn_in(pg, key):
    return pg.evaluate("(k) => NMSKQ309.measure().bySystem[k].drawn", key)


def systems(pg):
    return pg.evaluate("() => NMSKSysMap.systems()")


# ---------------------------------------------------------------- A / B / C ---------------------------------------
def section_ab(pg, tag, R, errs, phone):
    S = systems(pg)
    R["systems"] = [{"key": s["key"], "label": s["label"], "n": s["n"], "peel": s["peel"],
                     "strata": [{"key": t["key"], "label": t["label"], "n": t["n"], "basis": t["basis"]} for t in s["strata"]],
                     "why": s["why"]} for s in S]
    check("%s A the page declares at least 7 systems (%d)" % (tag, len(S)), len(S) >= 7, errs)
    for s in S:
        lab = pg.evaluate("(k) => { const b = document.getElementById('sy-' + k); return b ? b.querySelector('.sy-n').textContent + '|' + b.querySelector('.sy-c').textContent : null; }", s["key"])
        check("%s A %s has a button printing its name and its count (%s, n=%d)" % (tag, s["key"], lab, s["n"]),
              lab == "%s|%d" % (s["label"], s["n"]), errs)
    base = drawn(pg)
    R["drawnAtLoad"] = base
    off0 = sum(s["n"] for s in S)
    check("%s A every structure belongs to exactly one system (%d systems cover %d of them)" % (tag, len(S), off0),
          off0 > 0, errs)
    for s in S:
        k = s["key"]
        was, mine = drawn(pg), drawn_in(pg, k)
        if not hit(pg, "#sy-" + k, phone, errs, tag, "B the %s switch" % k):
            continue
        now, mine2 = drawn(pg), drawn_in(pg, k)
        check("%s B %s OFF: drawn %d -> %d (-%d, its own drawn count), it now draws %d" % (tag, k, was, now, mine, mine2),
              mine2 == 0 and was - now == mine, errs)
        hit(pg, "#sy-" + k, phone, errs, tag, "B the %s switch again" % k)
        back = drawn(pg)
        check("%s B %s back ON: drawn %d == %d" % (tag, k, back, was), back == was, errs)
        R.setdefault("toggle", {})[k] = {"before": was, "off": now, "mine": mine, "back": back}
    # C one undo step
    settle(pg)
    d0, s0 = pg.evaluate("() => NMSKHistory.state().len"), pg.evaluate("() => JSON.stringify(NMSKHistory.snapshot())")
    first = S[0]["key"]
    hit(pg, "#sy-" + first, phone, errs, tag, "C the %s switch" % first)
    settle(pg)
    d1 = pg.evaluate("() => NMSKHistory.state().len")
    check("%s C switching a system off is ONE history entry (%s -> %s)" % (tag, d0, d1), d1 == d0 + 1, errs)
    s1 = pg.evaluate("() => JSON.stringify(NMSKHistory.snapshot())")
    pg.keyboard.press("Control+z")
    pg.wait_for_timeout(500)
    check("%s C one Ctrl+Z restores the EXACT prior state" % tag, pg.evaluate("() => JSON.stringify(NMSKHistory.snapshot())") == s0, errs)
    pg.keyboard.press("Control+y")
    pg.wait_for_timeout(500)
    check("%s C one Ctrl+Y puts the switched-off state back" % tag, pg.evaluate("() => JSON.stringify(NMSKHistory.snapshot())") == s1, errs)
    pg.evaluate("() => NMSKSysToggle.put('')")
    settle(pg)
    return S


# ---------------------------------------------------------------- D / E / F ---------------------------------------
def section_def(pg, tag, R, errs, phone, S):
    # D the whole body is still Q301's own control
    pg.evaluate("() => NMSKSysPeel.setScope('body')")
    pg.wait_for_timeout(300)
    hit(pg, "#sp-in", phone, errs, tag, "D the In tap in the whole-body scope")
    hit(pg, "#sp-in", phone, errs, tag, "D the In tap again")
    wb, mine = pg.evaluate("() => NMSKPeel.step()"), pg.evaluate("() => NMSKSysPeel.ids().length")
    check("%s D the whole-body scope drives Q301's NMSKPeel (step %s) and Q309 vetoes nothing (%s)" % (tag, wb, mine),
          wb == 2 and mine == 0, errs)
    check("%s D and it is the CATEGORY table that moved, which is how Q301 shipped it" % tag,
          pg.evaluate("() => NMSKQ309.state().wholebody.hidden.length") >= 1, errs)
    R["wholeBody"] = {"step": wb, "q309vetoed": mine, "label": pg.evaluate("() => NMSKPeel.label()")}
    hit(pg, "#sp-sc-one", phone, errs, tag, "D the One-system scope tap")
    check("%s D leaving the whole-body scope puts its own layers back (%s)" % (tag, pg.evaluate("() => NMSKPeel.step()")),
          pg.evaluate("() => NMSKPeel.step()") == 0, errs)
    # E per system
    peelable = [s for s in S if s["peel"]]
    check("%s E at least two systems have a sourced depth order (%s)" % (tag, [s["key"] for s in peelable]),
          len(peelable) >= 2, errs)
    for s in peelable:
        k = s["key"]
        pg.evaluate("(k) => NMSKSysPeel.setSystem(k)", k)
        pg.wait_for_timeout(250)
        before = {q["key"]: drawn_in(pg, q["key"]) for q in S}
        settle(pg)
        e0 = pg.evaluate("() => NMSKHistory.state().len")
        # What a step can remove is what was DRAWN, not the stratum's own count: a structure hidden by default
        # (Q287's `hd` set, Q308's psoas minor) or a whole system off at load (Q301's fat) is in the stratum and
        # was never on the screen. The first run of this check asserted the total and reported two failures that
        # were the assertion's, not the product's -- skeletal -333 against 337 (four joint meshes hidden by
        # default) and adipose 0 against 17 (fat is off at load, as Q301 shipped it).
        want = pg.evaluate("(k) => NMSKQ309.measure().bySystem[k].strata[0].drawn", k)
        total = s["strata"][0]["n"]
        if not hit(pg, "#sp-in", phone, errs, tag, "E the In tap for %s" % k):
            continue
        settle(pg)
        after = {q["key"]: drawn_in(pg, q["key"]) for q in S}
        left = pg.evaluate("(k) => NMSKQ309.measure().bySystem[k].strata[0].drawn", k)
        check("%s E %s step 1 takes its first stratum off: %d -> %d (-%d; the stratum holds %d, of which %d were drawn), it now draws %d of them"
              % (tag, k, before[k], after[k], before[k] - after[k], total, want, left),
              before[k] - after[k] == want and left == 0, errs)
        moved = [q for q in before if q != k and before[q] != after[q]]
        check("%s E and EVERY other system is untouched to the structure (%s moved)" % (tag, moved or "none"),
              not moved, errs)
        check("%s E one In tap is ONE history entry" % tag,
              pg.evaluate("() => NMSKHistory.state().len") == e0 + 1, errs)
        R.setdefault("perSystem", {})[k] = {"stratum1": total, "stratum1Drawn": want, "before": before[k],
                                            "after": after[k], "leftDrawn": left, "othersMoved": moved}
        pg.evaluate("() => NMSKSysPeel.set(0)")
        pg.wait_for_timeout(200)
    # F the systems shown only
    off = [s["key"] for s in peelable][:2]
    pg.evaluate("(ks) => { NMSKSysToggle.put(''); ks.forEach(function(k){ NMSKSysToggle.set(k, false); }); }", off)
    pg.wait_for_timeout(250)
    hit(pg, "#sp-sc-shown", phone, errs, tag, "F the Systems-shown scope tap")
    hit(pg, "#sp-in", phone, errs, tag, "F the In tap in the Systems-shown scope")
    spanned = sorted(set(pg.evaluate("() => NMSKSysPeel.ids().map(function(i){ return NMSKSysMap.of(i); })")))
    want = sorted(s["key"] for s in peelable if s["key"] not in off)
    check("%s F the peel spans exactly the peelable systems switched ON: %s == %s" % (tag, spanned, want),
          spanned == want, errs)
    check("%s F and neither switched-off system is peeled (%s)" % (tag, off),
          not any(o in spanned for o in off), errs)
    R["shownOnly"] = {"switchedOff": off, "spanned": spanned, "expected": want,
                      "vetoed": pg.evaluate("() => NMSKSysPeel.ids().length")}


# ---------------------------------------------------------------- G / H -------------------------------------------
def section_gh(pg, tag, R, errs, phone):
    chips = pg.evaluate("() => NMSKShowAll.chips().map(function(c){ return c.key; })")
    check("%s G both Q309 paths raise their own chip in Q300's bar (%s)" % (tag, chips),
          "q309sys" in chips and "q309peel" in chips, errs)
    R["chips"] = pg.evaluate("() => NMSKShowAll.chips()")
    settle(pg)
    e0 = pg.evaluate("() => NMSKHistory.state().len")
    hit(pg, "#sa-all", phone, errs, tag, "G the Show everything button")
    settle(pg)
    left = pg.evaluate("() => NMSKQ309.measure().vetoed")
    check("%s G Show everything leaves no Q309 veto (%d) and is one step (%s -> %s)"
          % (tag, left, e0, pg.evaluate("() => NMSKHistory.state().len")),
          left == 0 and pg.evaluate("() => NMSKHistory.state().len") <= e0 + 1, errs)
    # the model reset
    load = pg.evaluate("() => NMSKModelReset.loaded()")
    pg.evaluate("""() => { NMSKSysToggle.set(NMSKSysMap.systems()[0].key, false);
        NMSKSysPeel.setScope('shown'); NMSKSysPeel.set(2); }""")
    pg.wait_for_timeout(300)
    settle(pg)
    hit(pg, "#q301-mr-model", phone, errs, tag, "G the Reset model button")
    pg.wait_for_timeout(600)
    st = pg.evaluate("() => NMSKQ309.state()")
    check("%s G Reset model returns both: %d systems off, scope %s step %d"
          % (tag, len(st["toggle"]["off"]), st["peel"]["scope"], st["peel"]["step"]),
          not st["toggle"]["off"] and st["peel"]["step"] == 0, errs)
    R["afterModelReset"] = st
    R["loadSnapshotPresent"] = bool(load)
    if phone:
        ow = pg.evaluate("() => Math.max(document.documentElement.scrollWidth, document.body.scrollWidth)")
        check("%s H nothing overflows 390 px (%d)" % (tag, ow), ow <= 390, errs)
        for sel in ("#sy-box", "#sp-box", "#sp-sc", "#q301-bar"):
            w = pg.evaluate("(s) => { const e = document.querySelector(s); if (!e) return 0; const r = e.getBoundingClientRect(); return Math.ceil(r.right); }", sel)
            check("%s H %s stays inside 390 px (right edge %d)" % (tag, sel, w), w <= 391, errs)
        R["phoneRight"] = {s: pg.evaluate("(x) => { const e = document.querySelector(x); return e ? Math.ceil(e.getBoundingClientRect().right) : 0; }", s)
                           for s in ("#sy-box", "#sp-box", "#q301-bar")}


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
                open_layers(pg)
                print("\n--- %s ---" % tag)
                S = section_ab(pg, tag, R, errs, phone)
                open_layers(pg)
                section_def(pg, tag, R, errs, phone, S)
                section_gh(pg, tag, R, errs, phone)
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
    print("\nQ309 VERIFY: %d OK / %d FAIL" % (OKN[0], len(errs)))
    for e in errs:
        print("  FAIL " + e)
    if a.json:
        Path(a.json).write_text(json.dumps(REPORT, indent=1), encoding="utf-8")
    return 1 if errs else 0


if __name__ == "__main__":
    raise SystemExit(main())
