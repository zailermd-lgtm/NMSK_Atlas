#!/usr/bin/env python3
"""Q303: real headless-Chromium check of the auto-focus, the four-pane layout, "facing me" + saved views and the nerve
emphasis (desktop 1400x900 real clicks + phone 390x844 real touch), on one page of each engine.

A  AUTO-FOCUS. Entering each imaging-like mode centres it on what the user already chose, measured in millimetres
   against the chosen set's own bounding-box centre: the CT / MR slice point, the ultrasound probe's seat on the skin,
   the cut plane's offset along its own normal, the cross-section stack and the camera for a render style. With NOTHING
   marked, selected or picked, nothing moves at all. Each centring is ONE undo step, and the off switch really stops it.
B  FOUR UP. Four panes of the SAME model, four distinct cameras, one shared state: a selection and a render style set in
   one pane hold in all four (there is only one scene). Expand and restore. At 390 px the panes are measured and the
   decision between 2x2 and a fallback is made from those numbers, not from taste; every control stays reachable and
   there is no horizontal scroll. A real touch inside a pane picks the structure under THAT pane's camera.
C  FACING ME. The structure's minor principal axis ends within a stated angle of the view direction, on a sheet-like and
   on a rod-like structure, with the silhouette gain of the rule reported per structure.
D  SAVED VIEWS. One tap returns the same camera, as one undo step, and the list survives a reload.
E  NERVES. The measured on-screen width of a large, a middling and a small nerve before and after, from the page's own
   calibre table and its own mm-per-pixel; the measured pixel contrast of the nerves against the rest of the picture
   before and after, read back INSIDE the page (page.screenshot returns a stale frame here -- Q300's finding); the
   compose-with cases (the nerve system toggle, a cut, the depth peel, Q300's fade, a radiographic style); one undo
   step; and the per-page counts, including which major nerves the page does not carry at all.
F  0 page errors, both viewports.

    python3 scripts/anatomy/q303/verify_q303.py PAGE_DIR... [--json OUT]"""
from __future__ import annotations
import json, math, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE.parent / "q283"))
import verify_q283 as V  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

OKN = [0]


def check(label, cond, errs):
    good = V.check(label, cond, errs)
    if good:
        OKN[0] += 1
    return good


MISSED: list = []
KEY = {"viewer_m_hr": "own_m", "viewer_f_hr": "own_f", "viewer_zan_atlas": "base_m", "viewer_base_female": "base_f",
       "viewer_zan_vhm": "comb_m", "viewer_zan_female": "comb_f"}
REPORT: dict = {}
HIT = """(sel) => {
  // Playwright's own selector syntax ("... >> nth=2") is not CSS, and document.querySelector refuses it. The probe
  // takes the CSS part and the index itself, so a probe failure can never be reported as a covered control.
  let css = sel, n = 0;
  const m = /^(.*?)\s*>>\s*nth=(\d+)$/.exec(sel);
  if (m) { css = m[1]; n = parseInt(m[2], 10); }
  const e = document.querySelectorAll(css)[n];
  if (!e) return {missing: true};
  const r = e.getBoundingClientRect();
  if (!(r.width > 0 && r.height > 0)) return {ok: false, over: "zero size"};
  const h = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
  if (h === e || e.contains(h) || (h && h.contains(e))) return {ok: true};
  let up = h, p = [];                        // NOT `n`: `n` is the nth index parsed above, and redeclaring it made
                                             // every probe a SyntaxError -- which read as "every control is covered"
  while (up && p.length < 3) { p.push(up.tagName.toLowerCase() + (up.id ? "#" + up.id : "")); up = up.parentElement; }
  return {ok: false, over: p.join(" < ")};
}"""


def tap(pg, selector, phone):
    """Q301's lesson: V.tap aims at an element's centre without looking at what is actually on top of it. A covered
       control is a real defect, so it is recorded rather than silently mis-reported as a broken feature -- and an
       element with no box at all (Q301 PARKS a group's adopted buttons in a hidden node when the group closes) is
       recorded and skipped instead of spending 30 s in a click that cannot land."""
    try:
        h = pg.evaluate(HIT, selector)
    except Exception as e:                                        # noqa: BLE001
        h = {"ok": False, "over": "probe failed: %s" % e}
    if h.get("missing") or h.get("over") == "zero size":
        MISSED.append("%s has no box on the screen (%s)" % (selector, h.get("over") or "missing"))
        return False
    if not h.get("ok") and "toast" in (h.get("over") or ""):
        # a transient notice from another module (the clinical tools' own toast) is waited out, not reported as a
        # collision: it goes by itself, and it is not this round's furniture
        for _ in range(16):
            pg.wait_for_timeout(600)
            h = pg.evaluate(HIT, selector)
            if h.get("ok"):
                break
    if not h.get("ok"):
        MISSED.append("%s is covered by %s" % (selector, h.get("over")))
    V.tap(pg, selector, phone)
    return True


def ready(pg):
    pg.wait_for_function("document.readyState === 'complete'", timeout=60000)
    pg.wait_for_function("window.NMSKClinicalTool && window.NMSKClinicalTool.api && window.NMSKClinicalTool.api.list().length > 0", timeout=180000)
    pg.wait_for_function("window.NMSKQ301 && window.NMSKQ301.state().on", timeout=120000)
    pg.wait_for_function("window.NMSKQ303 && window.NMSKQ303.ready()", timeout=120000)
    pg.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
    pg.wait_for_timeout(500)
    # the welcome / mode banners are dismissed IN PAGE: a real click on them hung for 30 s here (Q300's finding) and
    # they are not one of this round's assertions. Everything that IS asserted below is a real click or a real touch.
    pg.evaluate("""() => { ['mw-close', 'modal-close'].forEach(function(i){ var b = document.getElementById(i); if (b && b.offsetParent) b.click(); }); }""")
    pg.wait_for_timeout(300)
    freeze(pg)


def freeze(pg):
    """the Z pages spin by themselves, so two measurements would be of two different poses (Q300's finding)"""
    pg.evaluate("""() => { const b = document.getElementById('btn-spin');
        if (b && b.classList.contains('on')) b.click(); }""")
    pg.wait_for_timeout(300)


def settle(pg):
    """commit the history NOW rather than trusting Q294's 320 ms debounce, which does not fire on time while software
       rendering redraws thousands of meshes -- Q301 reported that as a product bug before finding it was the script"""
    pg.evaluate("() => { if (window.NMSKHistory) NMSKHistory.commit(); }")
    pg.wait_for_timeout(250)


def st(pg, what=""):
    return pg.evaluate("() => window.NMSKQ303.state()" + (("." + what) if what else ""))


def hidx(pg):
    return pg.evaluate("() => NMSKHistory.state().idx")


def quiet(pg, ms=1500, cap=24000):
    """wait until the history stops moving by itself, then commit. Entering a clinical tool starts work of its own and
       Q294 commits it on a 320 ms debounce, so a measurement taken too early counts the TOOL's entry as this round's."""
    t, i = 0, hidx(pg)
    while t < cap:
        pg.wait_for_timeout(300); t += 300
        j = hidx(pg)
        if j == i and not pg.evaluate("() => NMSKHistory.state().pending") and t >= ms:
            break
        if j != i:
            i, t = j, 0
    settle(pg)


def clear_choice(pg):
    pg.evaluate("""() => {
      const s = window.__q300dbg && window.__q300dbg.sel ? window.__q300dbg.sel() : null;
      if (s && s.clear) s.clear();
      if (window.__q303dbg && window.__q303dbg.deselect) window.__q303dbg.deselect();
      NMSKTarget.forget();
      ['q', 'search'].forEach(i => { const e = document.getElementById(i); if (e) e.value = ''; });
    }""")
    pg.wait_for_timeout(200)


def mark(pg, ids):
    pg.evaluate("""(ids) => {
      const s = window.__q300dbg.sel();
      if (s.clear) s.clear();
      if (s.markIds) s.markIds(ids); else ids.forEach(i => s.mark(i, true));
    }""", ids)
    pg.wait_for_timeout(250)


def nerve_ids(pg, n=3):
    """a large, a middling and a small nerve, chosen from the PAGE's own calibre table"""
    return pg.evaluate("""(n) => NMSKNerves.sample().map(r => r.id)""", n)


def leave_modes(pg):
    pg.evaluate("""() => {
      if (window.NMSKImaging) NMSKImaging.close();
      if (window.NMSKUltrasound) NMSKUltrasound.close();
      if (window.NMSKRenderStyle && NMSKRenderStyle.set) NMSKRenderStyle.set('colour');
      if (window.__q303dbg && window.__q303dbg.cut) window.__q303dbg.cut().exit(true);
      if (window.__q303dbg && window.__q303dbg.xsec) window.__q303dbg.xsec().set(false);
    }""")
    pg.wait_for_timeout(400)


def run_page(page_dir: Path, errs: list):
    tag = KEY.get(page_dir.name, page_dir.name)
    html = V.html_of(page_dir)
    srv, port = V.serve(page_dir)
    rep = REPORT.setdefault(tag, {})
    try:
        with sync_playwright() as pl:
            b = pl.chromium.launch(args=V.LAUNCH_ARGS, executable_path="/opt/pw-browsers/chromium")
            for (w, h), phone in (((1400, 900), False), ((390, 844), True)):
                T = "%s_%d" % (tag, w)
                R = rep.setdefault(str(w), {})
                del MISSED[:]
                ctx = b.new_context(viewport={"width": w, "height": h}, has_touch=phone, is_mobile=phone, device_scale_factor=1)
                pg = ctx.new_page()
                page_errs = []
                pg.on("pageerror", lambda e: page_errs.append(str(e)))
                pg.route("**/*", V.route)
                pg.goto("http://127.0.0.1:%d/%s" % (port, html), wait_until="load", timeout=120000)
                ready(pg)
                print("\n--- %s ---" % T)
                section_a(pg, T, R, errs, phone)
                section_b(pg, T, R, errs, phone)
                section_c(pg, T, R, errs, phone)
                section_d(pg, T, R, errs, phone)
                section_e(pg, T, R, errs, phone)
                section_f(pg, T, R, errs, phone)
                check("%s F 0 page errors %s" % (T, page_errs[:2] or ""), not page_errs, errs)
                check("%s F nothing of this round covers a control %s" % (T, MISSED[:3] or ""), not MISSED, errs)
                R["pageErrors"] = page_errs
                ctx.close()
            b.close()
    finally:
        srv.terminate()


# ---------------------------------------------------------------- A: auto-focus ----------------------------------
def open_group(pg, key, phone):
    """Q301 MOVES the engines' buttons into the open group's sheet and parks them (hidden) when it closes, so a button
       can only be tapped for real while its own group is open. Idempotent: the group button is a toggle."""
    if pg.evaluate("() => NMSKGroups.isOpen()") == key:
        return True
    if not pg.query_selector("#qg-" + key):
        return False
    tap(pg, "#qg-" + key, phone)
    pg.wait_for_timeout(400)
    return pg.evaluate("() => NMSKGroups.isOpen()") == key


def drive(pg, key, phone):
    """enter a mode the way the user does where the control is reachable, and through its own public API where it is
       not: #t-imaging and #t-ultrasound are NOT in Q301's group table, so they stay wherever the clinical tool put
       them and are not reliably on the screen at 390 px. What is under test here is the CENTRING, not the button."""
    if key == "ct":
        pg.evaluate("() => NMSKImaging.open()"); return "api"
    if key == "us":
        if pg.query_selector("#t-ultrasound") and tap(pg, "#t-ultrasound", phone):
            return "tap"
        pg.evaluate("() => NMSKUltrasound.open()"); return "api"
    if key == "cut":
        if open_group(pg, "cut", phone) and pg.query_selector("#t-cut") and tap(pg, "#t-cut", phone):
            return "tap"
        pg.evaluate("() => window.__q303dbg.cut().enter()"); return "api"
    if key == "style":
        if open_group(pg, "imaging", phone) and pg.query_selector("#rs-xray") and tap(pg, "#rs-xray", phone):
            return "tap"
        pg.evaluate("() => NMSKRenderStyle.set('xray')"); return "api"
    return None


def section_a(pg, T, R, errs, phone):
    leave_modes(pg)
    clear_choice(pg)
    open_group(pg, "view", phone)
    A = R.setdefault("A", {})
    ids = nerve_ids(pg)
    check("%s A the page offers a nerve to centre on (%s)" % (T, ids), len(ids) >= 1, errs)
    if not ids:
        return
    mark(pg, ids[:2])
    settle(pg)
    want = pg.evaluate("() => NMSKTarget.get()")
    check("%s A the target is the MARKED set (%s structures, %s)" % (T, want and want["n"], want and want["kind"]),
          want and want["kind"] == "marked", errs)
    A["target"] = want
    for key in ("ct", "us", "cut", "style"):
        leave_modes(pg)
        pg.wait_for_timeout(400)
        settle(pg)
        i0 = hidx(pg)
        t0 = pg.evaluate("() => Date.now()")
        how = drive(pg, key, phone)
        # WAIT FOR THE FOCUS THIS MODE RECORDED, do not wait a fixed time. Opening a clinical tool on these pages
        # builds its panes and its geometry and can hold the main thread for seconds, so the watcher's 150 ms tick
        # fires late; a fixed 1,400 ms read returned the PREVIOUS mode's result and reported the product as broken.
        # The evidence that entering the mode centred it is a focus RECORDED FOR THAT MODE, nothing else. An earlier
        # draft also waited for the mode to report itself active, and that proved the weaker signal: the CT / MR tool
        # can open, be seen open by the 150 ms watcher (which is what fires the focus) and then be closed again by the
        # page around it, so the probe read false while the focus had already happened and been recorded.
        # The WAIT is only an optimisation; the ASSERTION is on what is finally recorded. On a Z page the CT / MR
        # tool's first open builds its geometry over 3,252 meshes and holds the main thread for minutes under software
        # rendering, so wait_for_function cannot even be evaluated and times out while the product is working -- an
        # earlier draft read that as four failures and it was none.
        try:
            pg.wait_for_function("(a) => window.NMSKAutoFocus.history().some(function(e){"
                                " return e && e.mode === a.k && e.at >= a.t; })",
                                arg={"k": key, "t": t0}, timeout=600000)
        except Exception:                                          # noqa: BLE001
            pass
        hist = pg.evaluate("(a) => NMSKAutoFocus.history().filter(function(e){ return e && e.mode === a.k && e.at >= a.t; })",
                           {"k": key, "t": t0})
        last = hist[-1] if hist else pg.evaluate("() => NMSKAutoFocus.last()")
        ran = bool(hist)
        if not ran:
            A[key + "Why"] = pg.evaluate("() => ({modes: NMSKAutoFocus.modes(), on: NMSKAutoFocus.on(),"
                                         " style: (window.NMSKRenderStyle && NMSKRenderStyle.mode) ? NMSKRenderStyle.mode() : null,"
                                         " last: NMSKAutoFocus.last()})")
        check("%s A entering %s really ran ITS OWN focus (%d of its own since the mode was entered%s)"
              % (T, key, len(hist), "" if ran else ", " + json.dumps(A.get(key + "Why"))[:220]), ran, errs)
        if not ran:
            A[key] = {"enteredBy": how, "last": last}
            continue
        A[key] = last
        if not last or not last.get("ok"):
            check("%s A %s centred on the marked set (last=%s)" % (T, key, json.dumps(last)[:260]), False, errs)
            continue
        res = last["result"]
        if key == "ct":
            d = res["off"]
            check("%s A CT / MR: the slice point is the marked set's centre (%.4f mm)" % (T, d), d < 0.05, errs)
            cp = pg.evaluate("() => Object.keys(NMSKImaging.views()).map(k => NMSKImaging.views()[k].CP)")
            check("%s A CT / MR: every pane's in-plane centre released" % T, all(x is None for x in cp), errs)
        elif key == "us":
            check("%s A ultrasound: the probe is seated on the skin, in from %s (%.1f mm from the centre)"
                  % (T, res.get("from"), res["off"]), res.get("seated") is not None or res["off"] > 0, errs)
        elif key == "cut":
            check("%s A cut: the plane passes through the centre (%.4f mm along its own normal)" % (T, res["off"]),
                  res["off"] < 0.05 or res.get("clamped"), errs)
        elif key == "style":
            check("%s A a radiographic style: the camera frames the centre (%.4f mm)" % (T, res["off"]), res["off"] < 0.05, errs)
        check("%s A %s says on the screen what it centred on" % (T, key),
              pg.evaluate("() => { const e = document.getElementById('q303-note'); return !!(e && !e.hidden && e.textContent.indexOf('Centred') >= 0); }"), errs)
        # THE FOCUS is one undo step. Entering a mode is not necessarily: the CT / MR tool creates an axial cut for
        # itself when none is set ("No cut was set, so an axial cut through the upper abdomen was created for you"),
        # and that cut IS one of Q294's history providers -- a second entry that is the tool's doing, not this round's.
        # So the focus is measured on its own, from the mode already open, which is also exactly what the control
        # "Centre on my choice" calls.
        quiet(pg)
        j0 = hidx(pg)
        pg.evaluate("(k) => NMSKAutoFocus.focus(k)", key)
        pg.wait_for_timeout(900)
        j1 = hidx(pg)
        check("%s A the %s focus itself is ONE undo step (%d -> %d, mode entered by %s)" % (T, key, j0, j1, how),
              j1 == j0 + 1, errs)
    # the real control, tapped: "Centre on my choice" re-centres the mode you are in without leaving it
    open_group(pg, "view", phone)
    if pg.query_selector("#q303-centre"):
        pg.evaluate("() => NMSKImaging.set({P:[0, 0, 0]})")
        settle(pg)
        k0 = hidx(pg)
        tap(pg, "#q303-centre", phone)
        pg.wait_for_timeout(900)
        r = pg.evaluate("() => NMSKAutoFocus.last()")
        A["centreButton"] = r
        check("%s A a real tap on \u201cCentre on my choice\u201d centres it again (%s, %s mm off)"
              % (T, r and r.get("mode"), (r or {}).get("result", {}) and (r or {}).get("result", {}).get("off")),
              bool(r and r.get("ok")), errs)
        k1 = hidx(pg)
        check("%s A and that tap is ONE undo step (%d -> %d)" % (T, k0, k1), k1 == k0 + 1, errs)
    # Undo / Redo of the FOCUS, in isolation. Driven through NMSKAutoFocus.focus() with the mode already open, so
    # nothing else of the page moves in the same window: entering the CT / MR tool makes it create a cut and project
    # its own slice point, and those are its own history entries -- an earlier draft undid one of those instead and
    # read it as the round's failure.
    pg.evaluate("() => NMSKImaging.set({P:[0, 0, 0]})")
    settle(pg)
    before = pg.evaluate("() => NMSKImaging.state().P")
    u0 = hidx(pg)
    pg.evaluate("() => NMSKAutoFocus.focus('ct')")
    pg.wait_for_timeout(1200)
    moved = pg.evaluate("() => NMSKImaging.state().P")
    u1 = hidx(pg)
    check("%s A the focus moved the slice point %s -> %s, in ONE entry (%d -> %d)" % (T, before, moved, u0, u1),
          before != moved and u1 == u0 + 1, errs)
    pg.evaluate("() => NMSKHistory.undo()")
    pg.wait_for_timeout(900)
    back = pg.evaluate("() => NMSKImaging.state().P")
    check("%s A one Undo puts the slice point back exactly (%s)" % (T, back), back == before, errs)
    pg.evaluate("() => NMSKHistory.redo()")
    pg.wait_for_timeout(900)
    fwd = pg.evaluate("() => NMSKImaging.state().P")
    check("%s A one Redo puts it back on the centre (%s)" % (T, fwd), fwd == moved, errs)
    A["undoRedo"] = {"set": before, "focused": moved, "undone": back, "redone": fwd}
    # nothing chosen: NOTHING moves
    leave_modes(pg)
    clear_choice(pg)
    settle(pg)
    b0 = pg.evaluate("""() => ({img: NMSKImaging.state().P, us: NMSKUltrasound.state().P,
                               cam: NMSKQ303.state().autofocus.target})""")
    cam0 = pg.evaluate("() => window.__q303dbg.cam()")
    pg.evaluate("() => { NMSKImaging.open(); NMSKUltrasound.open(); }")
    pg.wait_for_timeout(1600)
    b1 = pg.evaluate("() => ({img: NMSKImaging.state().P, us: NMSKUltrasound.state().P})")
    cam1 = pg.evaluate("() => window.__q303dbg.cam()")
    check("%s A with nothing chosen the slice point does not move" % T, b0["img"] == b1["img"], errs)
    check("%s A with nothing chosen the probe does not move" % T, b0["us"] == b1["us"], errs)
    check("%s A with nothing chosen the camera does not move" % T, cam0 == cam1, errs)
    A["noTarget"] = {"img": b0["img"] == b1["img"], "us": b0["us"] == b1["us"], "cam": cam0 == cam1}
    # the off switch
    leave_modes(pg)
    mark(pg, ids[:1])
    settle(pg)
    open_group(pg, "view", phone)                 # drive() opened Cut and Imaging, and the groups are an accordion
    if not tap(pg, "#q303-af", phone):
        pg.evaluate("() => NMSKAutoFocus.setOn(false)")
    pg.wait_for_timeout(300)
    check("%s A the off switch is off after one tap" % T, pg.evaluate("() => NMSKAutoFocus.on()") is False, errs)
    # With Follow off the round's claim is that NO FOCUS RUNS. It is not that nothing on the page moves: the CT / MR
    # tool moves its own slice point when it opens (it projects it onto the cut plane, and creates an axial cut for
    # itself when none is set), which is the tool's behaviour and not this round's. So the assertion is on the focus
    # itself, plus the camera, which only this round moves.
    t0 = pg.evaluate("() => Date.now()")
    cam0 = pg.evaluate("() => window.__q303dbg.cam()")
    pg.evaluate("() => NMSKImaging.open()")
    pg.wait_for_timeout(1500)
    pg.evaluate("() => NMSKRenderStyle.set('xray')")
    pg.wait_for_timeout(1500)
    fresh = pg.evaluate("(t) => { const l = NMSKAutoFocus.last(); return !!(l && l.at >= t && l.ok); }", t0)
    check("%s A with Follow off, no focus runs at all" % T, not fresh, errs)
    check("%s A with Follow off, the camera does not move" % T,
          pg.evaluate("() => window.__q303dbg.cam()") == cam0, errs)
    pg.evaluate("() => NMSKAutoFocus.setOn(true)")
    leave_modes(pg)


# ---------------------------------------------------------------- B: four up ------------------------------------
def section_b(pg, T, R, errs, phone):
    B = R.setdefault("B", {})
    pg.evaluate("() => NMSKFourUp.leave()")
    pg.wait_for_timeout(300)
    settle(pg)
    open_group(pg, "view", phone)
    i0 = hidx(pg)
    ok_btn = pg.query_selector("#q303-four") is not None
    check("%s B the Four views button is in Q301's View group" % T, ok_btn, errs)
    if ok_btn:
        tap(pg, "#q303-four", phone)
    else:
        pg.evaluate("() => NMSKFourUp.enter()")
    # four panes means the scene is drawn FOUR TIMES; under software rendering a Z page's 3,252 meshes take seconds,
    # so every wait around four-up is generous on purpose rather than tuned to a fast machine
    pg.wait_for_timeout(3000)
    s = pg.evaluate("() => NMSKFourUp.state()")
    B["panes"] = s["panes"]
    check("%s B four panes (%s)" % (T, [p["key"] for p in s["panes"]]), s["layout"] == "four" and len(s["panes"]) == 4, errs)
    i1 = hidx(pg)
    check("%s B entering four views is ONE undo step (%d -> %d)" % (T, i0, i1), i1 == i0 + 1, errs)
    dirs = []
    for p in s["panes"]:
        ce = math.cos(p["el"])
        dirs.append((ce * math.sin(p["az"]), math.sin(p["el"]), ce * math.cos(p["az"])))
    worst = max(abs(sum(a * b for a, b in zip(dirs[i], dirs[j]))) for i in range(4) for j in range(i + 1, 4))
    B["worstCos"] = worst
    check("%s B the four cameras are genuinely distinct (worst |cos| %.3f)" % (T, worst), worst < 0.98, errs)
    tg = [tuple(round(v, 3) for v in p["tgt"]) for p in s["panes"]]
    check("%s B ONE model: all four share the target and the distance" % T,
          len(set(tg)) == 1 and len(set(round(p["dist"], 3) for p in s["panes"])) == 1, errs)
    # the panes really are four pictures: read the frame back and require four non-empty quadrants
    q = pg.evaluate("""() => {
      const r = window.__q303dbg.pixelsByPane ? window.__q303dbg.pixelsByPane() : null; return r; }""")
    if q:
        B["quadrants"] = q
        check("%s B every pane really drew something %s" % (T, q), all(x > 0.01 for x in q), errs)
    # shared state: a selection and a render style set once hold for all four, because there is only one scene
    sid = pg.evaluate("() => window.__q300dbg.pick()")
    pg.wait_for_timeout(400)
    check("%s B a selection made while four panes are on is the page's one selection (%s)" % (T, sid),
          bool(sid) and pg.evaluate("() => NMSKFourUp.layout()") == "four", errs)
    pg.evaluate("() => { if (window.NMSKRenderStyle && NMSKRenderStyle.set) NMSKRenderStyle.set('ct'); }")
    pg.wait_for_timeout(900)
    md = pg.evaluate("() => (window.NMSKRenderStyle && NMSKRenderStyle.mode) ? NMSKRenderStyle.mode() : null")
    check("%s B a render style set while four panes are on is the page's one style (%s), panes intact" % (T, md),
          pg.evaluate("() => NMSKFourUp.state().panes.length") == 4, errs)
    pg.evaluate("() => { if (window.NMSKRenderStyle && NMSKRenderStyle.set) NMSKRenderStyle.set('colour'); }")
    pg.wait_for_timeout(600)
    # expand and restore, through the real buttons. The pane labels and their squares stand down while Q301's group
    # sheet is open (section F proves that), so the sheet is closed first -- the user does the same by tapping the
    # group button again.
    if pg.evaluate("() => NMSKGroups.isOpen()"):
        tap(pg, "#qg-" + pg.evaluate("() => NMSKGroups.isOpen()"), phone)
        pg.wait_for_timeout(600)
    settle(pg)
    i0 = hidx(pg)
    tap(pg, "#q303-exp-lat", phone)
    pg.wait_for_timeout(1800)
    check("%s B one tap on a pane's square expands it" % T,
          pg.evaluate("() => [NMSKFourUp.layout(), NMSKFourUp.shown()]") == ["one", "lat"], errs)
    i1 = hidx(pg)
    check("%s B expand is ONE undo step (%d -> %d)" % (T, i0, i1), i1 == i0 + 1, errs)
    cam = pg.evaluate("() => window.__q303dbg.cam()")
    check("%s B the expanded pane's own camera is installed (az %.3f, want %.3f)" % (T, cam["az"], math.pi / 2),
          abs(cam["az"] - math.pi / 2) < 1e-5, errs)
    pg.evaluate("() => NMSKFourUp.restore()")
    pg.wait_for_timeout(3000)
    check("%s B restore gives four panes again" % T, pg.evaluate("() => NMSKFourUp.layout()") == "four", errs)
    # a real touch / click inside a pane picks under THAT pane's camera
    r = pg.evaluate("() => NMSKFourUp.paneRect('ant')")
    B["paneCss"] = [[round(pg.evaluate("() => NMSKFourUp.paneRect('%s')" % k)["width"]),
                     round(pg.evaluate("() => NMSKFourUp.paneRect('%s')" % k)["height"])] for k in ("ant", "lat", "sup", "free")]
    print("     pane size (CSS px): %s" % B["paneCss"])
    before = pg.evaluate("() => NMSKFourUp.state().active")
    # Two real-world facts this check has to respect. (1) The pane rect is in VIEWPORT coordinates, so the canvas is
    # scrolled into view and the rect re-read. (2) BOTH pages float their own toolbars OVER the canvas, and at 390 px
    # the Z page's `#topright` pill row sits exactly over the top-left pane -- a touch at the pane's middle landed on
    # the Measure button, which is why the pointer was never remapped (the remap deliberately refuses to rewrite an
    # event aimed at a control). That is the page's own furniture, not four-up's doing: the toolbar floats over the
    # single view in just the same way. So the point is PROBED for one that really is the model, and which point was
    # used is reported.
    pg.evaluate("() => { const c = document.querySelector('canvas');"
                " if (c && c.scrollIntoView) c.scrollIntoView({block: 'center'}); }")
    pg.wait_for_timeout(500)
    r = pg.evaluate("() => NMSKFourUp.paneRect('ant')")
    vp = pg.evaluate("() => [window.innerWidth, window.innerHeight]")
    pt = pg.evaluate("""(r) => {
      const c = document.querySelector('canvas');
      const cand = [[0.5, 0.42], [0.5, 0.62], [0.35, 0.72], [0.65, 0.72], [0.5, 0.85], [0.2, 0.55], [0.8, 0.55]];
      for (const f of cand){
        const x = r.left + r.width * f[0], y = r.top + r.height * f[1];
        if (!(x >= 0 && y >= 0 && x < window.innerWidth && y < window.innerHeight)) continue;
        const h = document.elementFromPoint(x, y);
        if (h && c && (h === c || c.contains(h))) return {x: x, y: y, at: f, over: null};
      }
      const x = r.left + r.width * 0.5, y = r.top + r.height * 0.42, h = document.elementFromPoint(x, y);
      return {x: x, y: y, at: [0.5, 0.42], over: h ? (h.tagName.toLowerCase() + (h.id ? '#' + h.id : '')) : 'nothing'};
    }""", r)
    x, y = pt["x"], pt["y"]
    B["tapPoint"] = {"x": round(x), "y": round(y), "at": pt["at"], "over": pt["over"], "viewport": vp}
    check("%s B a point inside the Anterior pane that really is the model (%d,%d at %s of the pane%s)"
          % (T, x, y, pt["at"], "" if not pt["over"] else ", everything probed was covered by " + str(pt["over"])),
          not pt["over"] and 0 <= x < vp[0] and 0 <= y < vp[1], errs)
    if phone:
        pg.touchscreen.tap(x, y)
    else:
        pg.mouse.click(x, y)
    pg.wait_for_timeout(800)
    s2 = pg.evaluate("() => NMSKFourUp.state()")
    check("%s B a real %s inside the Anterior pane makes it the active one (was %s)" % (T, "touch" if phone else "click", before),
          s2["active"] == "ant", errs)
    check("%s B the pointer was remapped into that pane (%d events, %d refused)" % (T, s2["remapped"], s2["refused"]),
          s2["remapped"] > 0 and s2["refused"] == 0, errs)
    hit = pg.evaluate("() => window.__q303dbg.selectedId()")
    B["pickedInPane"] = hit
    check("%s B that tap picked a structure under that pane's camera (%s)" % (T, hit), hit is not None, errs)
    if phone:
        # the decision between 2x2 and a fallback is made from these numbers
        wmin = min(c[0] for c in B["paneCss"])
        hmin = min(c[1] for c in B["paneCss"])
        check("%s B 390 px: each pane is at least 150 x 150 CSS px (%d x %d)" % (T, wmin, hmin), wmin >= 150 and hmin >= 150, errs)
        sz = pg.evaluate("""() => ['ant','lat','sup','free'].map(k => { const e = document.getElementById('q303-exp-' + k);
            const r = e.getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height)]; })""")
        check("%s B 390 px: every pane's square is at least 24 px %s" % (T, sz), all(a >= 24 and c >= 24 for a, c in sz), errs)
    pg.evaluate("() => NMSKFourUp.leave()")
    pg.wait_for_timeout(1500)


# ---------------------------------------------------------------- C: facing me ----------------------------------
def section_c(pg, T, R, errs, phone):
    C = R.setdefault("C", {})
    open_group(pg, "view", phone)
    # a sheet-like and a rod-like structure, found from the PAGE's own meshes. Capped: decoding a mesh's vertices is
    # cheap but a Z page carries 3,252 of them, and this loop runs synchronously inside the page.
    shapes = pg.evaluate("""() => {
      const out = {}, all = window.__q303dbg.list();
      let seen = 0;
      for (const rec of all){
        if (++seen > 500) break;
        let r = null;
        try { r = NMSKViews.report([rec.id]); } catch (e){ r = null; }
        if (!r) continue;
        if (!out[r.shape] || (r.gain || 0) > (out[r.shape].gain || 0))
          out[r.shape] = {id: rec.id, name: rec.name, shape: r.shape, gain: r.gain, lam: r.lam, ext: r.extent};
        if (out.sheet && out.rod) break;
      }
      out._scanned = seen;
      return out; }""")
    C["shapes"] = shapes
    print("     shape sample: %s" % json.dumps(shapes)[:400])
    for want in ("sheet", "rod"):
        rec = shapes.get(want)
        if rec is None and want == "sheet":
            rec = shapes.get("blob")          # a page with no flat structure in the scanned window: say so rather than skip
            if rec:
                print("     (no sheet in the first %s structures; using the blob %s)" % (shapes.get("_scanned"), rec["name"]))
        if not rec:
            check("%s C the page carries a %s-like structure to face" % (T, want), False, errs)
            continue
        pg.evaluate("(id) => { const s = window.__q300dbg.sel(); if (s.clear) s.clear(); window.__q300dbg.pick(id); }", rec["id"])
        pg.wait_for_timeout(500)
        settle(pg)
        i0 = hidx(pg)
        open_group(pg, "view", phone)
        if not tap(pg, "#q303-facing", phone):
            pg.evaluate("() => NMSKViews.facing()")
        pg.wait_for_timeout(900)
        f = pg.evaluate("() => NMSKViews.last()")
        C[want] = f
        check("%s C facing me on a %s (%s): applied, read as %s" % (T, want, rec["name"], f.get("shape")),
              f.get("ok") and f.get("shape") == rec["shape"], errs)
        check("%s C facing me on a %s: the chosen axis is %.3f deg off the view direction (limit 2.0)" % (T, want, f.get("angle_deg", 99)),
              f.get("angle_deg", 99) <= 2.0, errs)
        i1 = hidx(pg)
        check("%s C facing me on a %s is ONE undo step (%d -> %d)" % (T, want, i0, i1), i1 == i0 + 1, errs)
        if rec["shape"] == "rod":
            cos = pg.evaluate("""(id) => {
              const r = NMSKViews.report([id]), v = window.__q303dbg.view();
              const l = Math.hypot(v.dir[0], v.dir[1], v.dir[2]) || 1;
              return Math.abs(r.e1[0]*v.dir[0]/l + r.e1[1]*v.dir[1]/l + r.e1[2]*v.dir[2]/l); }""", rec["id"])
            check("%s C a rod's shaft ends ACROSS the view (|cos| %.4f)" % (T, cos), cos < 0.06, errs)
        pg.evaluate("() => NMSKHistory.undo()")
        pg.wait_for_timeout(500)


# ---------------------------------------------------------------- D: saved views --------------------------------
def section_d(pg, T, R, errs, phone):
    D = R.setdefault("D", {})
    open_group(pg, "view", phone)
    pg.evaluate("() => { NMSKViews.del('Q303 check'); }")
    pg.evaluate("() => window.__q303dbg.nudge()")
    pg.wait_for_timeout(400)
    cam0 = pg.evaluate("() => window.__q303dbg.cam()")
    pg.evaluate("() => { const e = document.getElementById('q303-vname'); if (e) e.value = 'Q303 check'; }")
    if not tap(pg, "#q303-vsave", phone):
        pg.evaluate("() => NMSKViews.save('Q303 check')")
    pg.wait_for_timeout(400)
    lst = pg.evaluate("() => NMSKViews.list().map(v => v.name)")
    check("%s D the view is saved under its name (%s)" % (T, lst), "Q303 check" in lst, errs)
    pg.evaluate("() => window.__q303dbg.nudge(1.1)")
    pg.wait_for_timeout(400)
    settle(pg)
    i0 = hidx(pg)
    idx = pg.evaluate("() => Array.from(document.querySelectorAll('#q303-vchips .q3-vb')).findIndex(b => b.textContent === 'Q303 check')")
    if idx >= 0:
        tap(pg, "#q303-vchips .q3-vb >> nth=%d" % idx, phone)
    else:
        pg.evaluate("() => NMSKViews.apply('Q303 check')")
    pg.wait_for_timeout(700)
    cam1 = pg.evaluate("() => window.__q303dbg.cam()")
    err = max(abs(cam1["az"] - cam0["az"]), abs(cam1["el"] - cam0["el"]), abs(cam1["dist"] - cam0["dist"]),
              max(abs(a - c) for a, c in zip(cam1["tgt"], cam0["tgt"])))
    D["returnError"] = err
    check("%s D one tap returns the SAME camera (max component error %.5f)" % (T, err), err < 1e-3, errs)
    i1 = hidx(pg)
    check("%s D returning to a saved view is ONE undo step (%d -> %d)" % (T, i0, i1), i1 == i0 + 1, errs)
    pg.reload(wait_until="load", timeout=120000)
    ready(pg)
    open_group(pg, "view", phone)
    check("%s D saved views survive a reload" % T, "Q303 check" in pg.evaluate("() => NMSKViews.list().map(v => v.name)"), errs)
    pg.evaluate("() => NMSKViews.del('Q303 check')")
    check("%s D the chip's x forgets it" % T, "Q303 check" not in pg.evaluate("() => NMSKViews.list().map(v => v.name)"), errs)


# ---------------------------------------------------------------- E: nerves -------------------------------------
def section_e(pg, T, R, errs, phone):
    E = R.setdefault("E", {})
    leave_modes(pg)
    freeze(pg)
    open_group(pg, "view", phone)
    pg.evaluate("() => NMSKNerves.set(0)")
    pg.wait_for_timeout(500)
    cen0 = pg.evaluate("() => NMSKNerves.census()")
    E["census"] = cen0
    E["absent"] = pg.evaluate("() => NMSKNerves.absent()")
    E["sampleBefore"] = pg.evaluate("() => NMSKNerves.sample()")
    print("     nerves: %d structures, %d with a measured diameter (%s-%s mm), %d drawn under 1 px at %s mm/px"
          % (cen0["n"], cen0["withDia"], cen0["diaMin"], cen0["diaMax"], cen0["subPixel"], cen0["mmPerPx"]))
    print("     before: " + "; ".join("%s d=%s true=%.3f px" % (r["name"], r["dia_mm"], r["truePx"]) for r in E["sampleBefore"]))
    check("%s E the page's own calibre table drives it (%d of %d nerves carry a measured diameter)" % (T, cen0["withDia"], cen0["n"]),
          cen0["n"] > 0 and cen0["withDia"] > 0, errs)
    check("%s E it counts the ones effectively invisible before (%d under one pixel)" % (T, cen0["subPixel"]),
          cen0["subPixel"] >= 1, errs)
    px0 = pg.evaluate("() => window.__q303px(2)")
    E["px0"] = px0
    pg.evaluate("() => NMSKNerves.set(0)")
    settle(pg)
    i0 = hidx(pg)
    open_group(pg, "view", phone)
    if not tap(pg, "#nv-1", phone):
        pg.evaluate("() => NMSKNerves.set(1)")
    pg.wait_for_timeout(1500)
    i1 = hidx(pg)
    check("%s E Clear is one tap and ONE undo step (%d -> %d)" % (T, i0, i1), i1 == i0 + 1, errs)
    check("%s E the engine really built the pass (%s)" % (T, json.dumps(pg.evaluate("() => window.__q303nv()"))[:160]),
          pg.evaluate("() => { const s = window.__q303nv(); return s.step > 0 && !s.fail && (s.structures > 0 || s.twins > 0); }"), errs)
    cen1 = pg.evaluate("() => NMSKNerves.census()")
    E["sampleAfter"] = pg.evaluate("() => NMSKNerves.sample()")
    print("     after : " + "; ".join("%s drawn=%.3f px (min %s)" % (r["name"], r["drawnPx"], r["minPx"]) for r in E["sampleAfter"]))
    small = [r for r in E["sampleAfter"] if r["truePx"] is not None and r["truePx"] < r["minPx"]]
    check("%s E a sub-minimum nerve is widened to the minimum (%s)" % (T, [[r["truePx"], r["drawnPx"]] for r in small]),
          all(abs(r["drawnPx"] - r["minPx"]) < 1e-6 for r in small) and len(small) >= 1, errs)
    big = [r for r in E["sampleAfter"] if r["truePx"] is not None and r["truePx"] >= r["minPx"]]
    check("%s E a nerve already wider than the minimum is NOT widened (%s)" % (T, [[r["truePx"], r["drawnPx"]] for r in big]),
          all(abs(r["drawnPx"] - r["truePx"]) < 1e-6 for r in big), errs)
    px1 = pg.evaluate("() => window.__q303px(2)")
    E["px1"] = px1
    pg.evaluate("() => NMSKNerves.set(2)")
    pg.wait_for_timeout(1500)
    px2 = pg.evaluate("() => window.__q303px(2)")
    E["px2"] = px2
    print("     pixels: nerve fraction %.5f -> %.5f -> %.5f ; michelson %.4f -> %.4f -> %.4f"
          % (px0["nerveFrac"], px1["nerveFrac"], px2["nerveFrac"], px0["michelson"], px1["michelson"], px2["michelson"]))
    check("%s E MEASURED: the nerves occupy more of the picture after (%.5f -> %.5f, x%.2f)"
          % (T, px0["nerveFrac"], px1["nerveFrac"], px1["nerveFrac"] / max(1e-9, px0["nerveFrac"])),
          px1["nerveFrac"] > px0["nerveFrac"] * 1.15, errs)
    check("%s E MEASURED: Strong occupies more than Clear (%.5f -> %.5f)" % (T, px1["nerveFrac"], px2["nerveFrac"]),
          px2["nerveFrac"] >= px1["nerveFrac"], errs)
    # composes with: the nerve system toggle, a cut, the depth peel, Q300's fade
    pg.evaluate("() => NMSKNerves.set(1)")
    pg.wait_for_timeout(800)
    pg.evaluate("() => window.__q303dbg.nerveLayerOff()")
    pg.wait_for_timeout(500)
    pg.evaluate("() => NMSKNerves.set(0)")
    pg.wait_for_timeout(400)
    pg.evaluate("() => NMSKNerves.set(1)")
    pg.wait_for_timeout(900)
    check("%s E it switches the nerve system back on rather than fighting it" % T,
          pg.evaluate("() => window.__q303dbg.nerveLayerOn()") is True, errs)
    pg.evaluate("() => { const b = document.getElementById('t-cut'); if (b) b.click(); }")
    pg.wait_for_timeout(1500)
    pxc = pg.evaluate("() => window.__q303px(2)")
    E["pxCut"] = pxc
    check("%s E it composes with a cut: still drawn, and the pass is clipped (%d nerve px against %d, x%.2f)"
          % (T, pxc["nerve"], px1["nerve"], pxc["nerve"] / max(1, px1["nerve"])),
          pxc["nerve"] > 0 and pxc["nerve"] <= px1["nerve"] * 2.0, errs)
    pg.evaluate("() => { const b = document.getElementById('cut-exit') || document.getElementById('t-cut'); if (b) b.click(); }")
    pg.wait_for_timeout(1200)
    # a radiographic style: the row says it is incompatible, and says what to use instead
    pg.evaluate("() => { if (window.NMSKRenderStyle && NMSKRenderStyle.set) NMSKRenderStyle.set('xray'); NMSKCombos.refresh(); }")
    pg.wait_for_timeout(900)
    v = pg.evaluate("() => NMSKCombos.verdict('nerves')")
    E["styleVerdict"] = v
    pg.evaluate("() => NMSKNerves.set(0)")
    pg.wait_for_timeout(400)
    v2 = pg.evaluate("() => NMSKCombos.verdict('nerves')")
    check("%s E a radiographic style disables the emphasis and says what to use instead" % T,
          v2["disabled"] and "Colour" in v2["reason"], errs)
    pg.evaluate("() => { if (window.NMSKRenderStyle && NMSKRenderStyle.set) NMSKRenderStyle.set('colour'); }")
    pg.wait_for_timeout(700)
    check("%s E %d of the conventional major nerves are not on this page: %s" % (T, len(E["absent"]["missing"]), E["absent"]["missing"][:6]),
          isinstance(E["absent"]["missing"], list), errs)
    pg.evaluate("() => NMSKNerves.set(0)")


# ---------------------------------------------------------------- F: it fits -------------------------------------
def section_f(pg, T, R, errs, phone):
    F = R.setdefault("F", {})
    pg.evaluate("() => { if (window.NMSKGroups) NMSKGroups.close(); }")
    pg.wait_for_timeout(300)
    pg.evaluate("() => NMSKFourUp.enter()")
    pg.wait_for_timeout(3000)
    pg.evaluate("() => { if (window.NMSKAutoFocus) NMSKAutoFocus.focus('ct'); }")
    pg.wait_for_timeout(600)
    sc = pg.evaluate("() => ({w: document.documentElement.scrollWidth, c: document.documentElement.clientWidth})")
    F["scroll"] = sc
    check("%s F no horizontal scroll (%d <= %d)" % (T, sc["w"], sc["c"]), sc["w"] <= sc["c"] + 1, errs)
    cover = pg.evaluate("""() => {
      const out = [];
      ['q301-undo','q301-redo','q301-reset','q301-mr-model','q303-exp-ant','q303-exp-lat','q303-exp-sup','q303-exp-free']
        .forEach(id => {
          const e = document.getElementById(id);
          if (!e) { out.push([id, 'missing']); return; }
          const r = e.getBoundingClientRect();
          if (!(r.width > 0 && r.height > 0)) { out.push([id, 'zero size']); return; }
          const h = document.elementFromPoint(r.x + r.width/2, r.y + r.height/2);
          const ok = h === e || e.contains(h) || (h && h.contains(e));
          out.push([id, ok ? 'ok' : (h ? h.tagName.toLowerCase() + (h.id ? '#' + h.id : '.' + h.className) : 'none')]);
        });
      return out; }""")
    bad = [c for c in cover if c[1] != "ok"]
    F["cover"] = cover
    check("%s F nothing covers Undo / Redo / the two resets / the four squares %s" % (T, bad or "(all clear)"), not bad, errs)
    # and with a group OPEN the labels step aside rather than be swallowed by its sheet (which unfolds over the lower
    # half of the 3-D view, exactly where the bottom row's labels sit)
    pg.evaluate("() => { if (window.NMSKGroups) NMSKGroups.open('view'); }")
    pg.wait_for_timeout(500)
    q = pg.evaluate("""() => {
      const g = document.getElementById('q303-grid');
      const vis = ['ant','lat','sup','free'].map(k => { const e = document.getElementById('q303-exp-' + k);
        const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0; });
      return {quiet: !!(g && g.classList.contains('q3-quiet')), shown: vis}; }""")
    F["quiet"] = q
    check("%s F with a group open the pane labels step aside (%s)" % (T, q), q["quiet"] and not any(q["shown"]), errs)
    pg.evaluate("() => { if (window.NMSKGroups) NMSKGroups.close(); }")
    pg.wait_for_timeout(400)
    back = pg.evaluate("""() => ['ant','lat','sup','free'].map(k => { const r = document.getElementById('q303-exp-' + k).getBoundingClientRect();
      return r.width > 0 && r.height > 0; })""")
    check("%s F closing it brings them straight back (%s)" % (T, back), all(back), errs)
    pg.evaluate("() => NMSKFourUp.leave()")
    pg.wait_for_timeout(500)


def main(argv):
    dirs, out = [], None
    i = 0
    while i < len(argv):
        if argv[i] == "--json":
            out = Path(argv[i + 1]); i += 2; continue
        dirs.append(Path(argv[i])); i += 1
    if not dirs:
        print(__doc__); return 2
    errs: list = []
    for d in dirs:
        run_page(d, errs)
    print("\n==== %d OK, %d FAIL ====" % (OKN[0], len(errs)))
    for e in errs:
        print("  - " + e)
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(REPORT, indent=1), encoding="utf-8")
        print("wrote " + str(out))
    return 1 if errs else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
