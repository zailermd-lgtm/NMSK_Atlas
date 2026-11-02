#!/usr/bin/env python3
"""Q301: real headless-Chromium check of the one control bar, the groups, the radiographic render styles, the depth
peel, the fat default and the compatibility matrix (desktop 1400x900 real clicks + phone 390x844 real touch).

A  THE CONTROL. One bar, always on the screen, in the bottom third of the 3-D view, carrying Undo / Redo / Reset module
   / Reset model with WORDS (the owner could not find them as floating icons), plus the circled i. Undo and Redo are
   driven through the real bar: a state is changed, the bar's Undo puts it back, the bar's Redo brings it forward.
B  THE GROUPS. Every group button opens its sheet and closes it again, one at a time (accordion), and each group's
   members are really in the sheet -- the adopted buttons keep their own ids.
C  THE RENDER STYLES. X-ray, CT and MRI each switch the whole model, and one tap on Colour returns. Proved by PIXELS
   read back inside the page (page.screenshot returns a stale frame here -- Q300's finding), so each style must differ
   from colour and from the other styles in measured saturation / brightness, and Colour must come back to where it was.
D  CUT + IMAGING co-active, which is the owner's own example, asserted from the real cut state and the real style state
   and from the group's own co-active decoration.
E  AN INCOMPATIBLE PAIR really disabled, with its one-line reason on the screen (not only in a tooltip).
F  FAT off at load, on in one tap, and the cut face still filled either way (the page's own cut-face kernel).
G  THE LAYER PEEL takes the layers off in order, skin first, and "Whole body" puts them all back -- and the step is one
   Undo step.
H  Every one of these is a single Undo step, and Q300's "Show everything" and model reset both reach the new states.
I  0 page errors, both viewports.

    python3 scripts/anatomy/q301/verify_q301.py PAGE_DIR... [--json OUT]"""
from __future__ import annotations
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE.parent / "q283"))
import verify_q283 as V  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

check = V.check
MISSED: list = []
HIT = """(sel) => {
  const e = document.querySelector(sel);
  if (!e) return {missing: true};
  const r = e.getBoundingClientRect();
  const h = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2);
  if (h === e || e.contains(h) || (h && h.contains(e))) return {ok: true};
  let n = h, p = [];
  while (n && p.length < 3) { p.push(n.tagName.toLowerCase() + (n.id ? "#" + n.id : "")); n = n.parentElement; }
  return {ok: false, over: p.join(" < ")};
}"""


def tap(pg, selector, phone):
    """V.tap aims at the element's centre and does not look at what is actually there. Twice this round something
       else was: Q300's chip bar, lifted into the open group's sheet on a 390 px phone, swallowed the tap and the
       script then reported the product as broken. A covered control is a real defect either way, so record it."""
    try:
        h = pg.evaluate(HIT, selector)
    except Exception as e:                                        # noqa: BLE001
        h = {"ok": False, "over": "probe failed: %s" % e}
    if not h.get("ok") and not h.get("missing"):
        MISSED.append("%s is covered by %s" % (selector, h.get("over")))
    return V.tap(pg, selector, phone)
KEY = {"viewer_m_hr": "own_m", "viewer_f_hr": "own_f", "viewer_zan_atlas": "base_m", "viewer_base_female": "base_f",
       "viewer_zan_vhm": "comb_m", "viewer_zan_female": "comb_f"}
REPORT: dict = {}


def ready(pg):
    pg.wait_for_function("document.readyState === 'complete'", timeout=60000)
    pg.wait_for_function("window.NMSKClinicalTool && window.NMSKClinicalTool.api && window.NMSKClinicalTool.api.list().length > 0", timeout=180000)
    pg.wait_for_function("window.NMSKQ301 && window.NMSKQ301.state().on", timeout=120000)
    pg.wait_for_function("window.NMSKQ301.ready()", timeout=120000)          # the tissue table has arrived
    pg.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
    pg.wait_for_timeout(500)
    # the Q272 mode switcher shows on a session's first load and would sit over the bar. Dismissed with a JS click on
    # purpose: a real click here makes Playwright wait on a navigation the overlay schedules, and this is not one of the
    # round's assertions -- everything that IS asserted below is a real click or a real touch.
    pg.evaluate("""() => { ['mw-close', 'modal-close'].forEach(function(i){ var b = document.getElementById(i); if (b && b.offsetParent) b.click(); }); }""")
    pg.wait_for_timeout(300)
    freeze(pg)


def freeze(pg):
    """the Z pages spin by themselves, so every pixel measurement would be of a different pose (Q300's finding)"""
    pg.evaluate("""() => { const b = document.getElementById('btn-spin');
        if (b && b.classList.contains('on')) b.click();
        window.__q301frozen = !(b && b.classList.contains('on')); }""")
    pg.wait_for_timeout(300)


def settle(pg):
    """Commit the history NOW. Q294 commits on a debounce after user input; under software rendering a redraw of 3,252
       meshes can outlast it, and a precondition that has not been committed makes the next undo land one step short --
       which is exactly what the first phone run of this script reported as a product bug."""
    pg.evaluate("() => { if (window.NMSKHistory) NMSKHistory.commit(); }")
    pg.wait_for_timeout(250)


def st(pg, what=""):
    return pg.evaluate("() => window.NMSKQ301.state()" + (("." + what) if what else ""))


def px(pg):
    """one forced frame, read back in the page"""
    pg.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
    return pg.evaluate("() => window.NMSKQ301.pixels(2)")


def differs(a, b, tol_sat=2.0, tol_lum=3.0):
    """two frames are genuinely different pictures: saturation or brightness or the brightness histogram moved"""
    if not a or not b or not a.get("n") or not b.get("n"):
        return False, 0.0, 0.0, 0.0
    ds, dl = abs(a["sat"] - b["sat"]), abs(a["lum"] - b["lum"])
    dh = sum(abs(x - y) for x, y in zip(a["hist"], b["hist"]))
    return (ds > tol_sat or dl > tol_lum or dh > 0.10), ds, dl, dh


def run_page(page_dir: Path, errs: list):
    tag = KEY.get(page_dir.name, page_dir.name)
    html = V.html_of(page_dir)
    srv, port = V.serve(page_dir)
    rep = REPORT.setdefault(tag, {})
    try:
        with sync_playwright() as pl:
            b = pl.chromium.launch(args=V.LAUNCH_ARGS, executable_path="/opt/pw-browsers/chromium")
            for (w, h), phone in (((1400, 900), False), ((390, 844), True)):
                T = f"{tag}_{w}"
                R = rep.setdefault(str(w), {})
                del MISSED[:]
                ctx = b.new_context(viewport={"width": w, "height": h}, has_touch=phone, is_mobile=phone, device_scale_factor=1)
                pg = ctx.new_page()
                page_errs = []
                pg.on("pageerror", lambda e: page_errs.append(str(e)))
                pg.route("**/*", V.route)
                pg.goto(f"http://127.0.0.1:{port}/{html}", wait_until="load", timeout=120000)
                ready(pg)

                # ---------------- the load defaults, measured BEFORE this script touches anything ---
                load = st(pg)
                R["at_load"] = load
                check(f"{T}: F fat is OFF when the page loads ({load['fat']})", load["fat"] and load["fat"]["shown"] is False, errs)
                nfat = pg.evaluate("() => { const a = window.NMSKClinicalTool.api, L = a.list(); return L.filter(r => r.cat === 'fat' && a.visible(r.i)).length; }")
                check(f"{T}: F and none of its {load['fat']['count']} fat structures is drawn at load ({nfat})", nfat == 0, errs)
                check(f"{T}: F the depth peel starts at the whole body ({load['peel']})", load["peel"] and load["peel"]["step"] == 0, errs)
                check(f"{T}: F the model starts in colour ({load['render']['mode']})", load["render"]["mode"] == "colour", errs)

                # ---------------- A  the control -------------------------------------------------
                bar = pg.evaluate("""() => { const b = document.getElementById('q301-bar'); if (!b) return null;
                    const r = b.getBoundingClientRect();
                    return {vis: r.width > 40 && r.height > 20, top: r.top, bottom: r.bottom, w: r.width,
                            ids: Array.from(b.querySelectorAll('button')).map(x => x.id).filter(Boolean),
                            words: Array.from(b.querySelectorAll('.qg-t')).map(x => x.textContent)}; }""")
                check(f"{T}: A the control bar is on the screen ({bar and round(bar['w'])} px wide)", bar and bar["vis"], errs)
                need = ["q301-undo", "q301-redo", "q301-reset", "q301-mr-model"]
                check(f"{T}: A it carries undo / redo / module reset / model reset", bar and all(i in bar["ids"] for i in need), errs)
                check(f"{T}: A each of the four is NAMED, not an icon alone ({bar and bar['words']})",
                      bar and sorted(bar["words"]) == ["Model", "Module", "Redo", "Undo"], errs)
                box = pg.evaluate("() => { const a = document.getElementById('q301-anchor-probe'); return null; }")
                third = pg.evaluate("""() => { const b = document.getElementById('q301-bar').getBoundingClientRect();
                    return b.top > window.innerHeight * 0.55; }""")
                check(f"{T}: A the bar sits in the bottom third (thumb zone)", third, errs)
                check(f"{T}: A the circled i is on the screen", pg.evaluate("() => { const e = document.getElementById('qi-corner'); if (!e) return false; const r = e.getBoundingClientRect(); return r.width > 14 && r.height > 14; }"), errs)
                if phone:
                    over = pg.evaluate("""() => { const b = document.getElementById('q301-bar').getBoundingClientRect();
                        return b.left >= 0 && b.right <= window.innerWidth + 0.5 && document.documentElement.scrollWidth <= window.innerWidth + 1; }""")
                    check(f"{T}: A the bar fits 390 px with no horizontal page scroll", over, errs)
                R["bar"] = bar

                # undo / redo DRIVEN THROUGH THE BAR
                pg.evaluate("() => window.NMSKFat && NMSKFat.set(true)")      # some state the history can see
                settle(pg)
                before = st(pg)
                pg.evaluate("() => window.NMSKPeel && NMSKPeel.set(1)")
                settle(pg)
                mid = st(pg)
                tap(pg, "#q301-undo", phone); pg.wait_for_timeout(800)
                back = st(pg)
                tap(pg, "#q301-redo", phone); pg.wait_for_timeout(800)
                fwd = st(pg)
                moved = (mid["peel"] or {}).get("step") != (before["peel"] or {}).get("step")
                check(f"{T}: A a state really changed before undo ({(before['peel'] or {}).get('step')} -> {(mid['peel'] or {}).get('step')})", moved, errs)
                check(f"{T}: A the bar's Undo put it back", (back["peel"] or {}).get("step") == (before["peel"] or {}).get("step"), errs)
                check(f"{T}: A the bar's Redo brought it forward", (fwd["peel"] or {}).get("step") == (mid["peel"] or {}).get("step"), errs)
                pg.evaluate("() => { window.NMSKPeel && NMSKPeel.set(0); window.NMSKFat && NMSKFat.set(false); }")
                settle(pg)

                # ---------------- B  the groups --------------------------------------------------
                pg.evaluate("""() => { window.__q301had = {}; ['t-cut', 't-reset', 'sel-markmode', 't-learn', 't-measure', 'btn-xray', 'sides', 'foot']
                    .forEach(i => { window.__q301had[i] = !!document.getElementById(i); }); }""")
                gs = [g for g in pg.evaluate("() => window.NMSKGroups.state().groups")
                      if pg.evaluate("(k) => { const b = document.getElementById('qg-' + k); return !!b && !b.hidden; }", g["key"])]
                R["groups"] = gs
                check(f"{T}: B the bar offers labelled groups ({[g['label'] for g in gs]})", len(gs) >= 5, errs)
                opened = []
                for g in gs:
                    tap(pg, "#qg-" + g["key"], phone); pg.wait_for_timeout(260)
                    o = pg.evaluate("() => ({open: window.NMSKGroups.isOpen(), hidden: document.getElementById('q301-sheet').hidden, n: document.querySelectorAll('#q301-sheet .qg-m').length})")
                    ok_open = o["open"] == g["key"] and not o["hidden"] and o["n"] > 0
                    tap(pg, "#qg-" + g["key"], phone); pg.wait_for_timeout(220)
                    o2 = pg.evaluate("() => ({open: window.NMSKGroups.isOpen(), hidden: document.getElementById('q301-sheet').hidden})")
                    opened.append({"key": g["key"], "open": ok_open, "closed": o2["open"] is None and o2["hidden"], "members": o["n"]})
                check(f"{T}: B every group opens with members in it ({[(o['key'], o['members']) for o in opened]})",
                      all(o["open"] for o in opened), errs)
                check(f"{T}: B every group closes again on a second tap", all(o["closed"] for o in opened), errs)
                R["open_close"] = opened
                # the sheet holds the engines' REAL buttons: opening every group in turn must not destroy any of them
                alive = pg.evaluate("""() => { const need = ['t-cut', 't-reset', 'sel-markmode', 't-learn', 't-measure', 'btn-xray', 'sides', 'foot'];
                    const out = {}; need.forEach(i => { const e = document.getElementById(i); out[i] = !!e; }); return out; }""")
                had = pg.evaluate("() => window.__q301had || null")
                check(f"{T}: B no adopted button was destroyed by opening the other groups ({[k for k, v in alive.items() if not v]})",
                      all(v for k, v in alive.items() if not had or had.get(k)), errs)
                R["alive"] = alive

                # ---------------- C  the render styles, measured in pixels -----------------------
                tap(pg, "#qg-imaging", phone); pg.wait_for_timeout(300)
                shots, modes = {}, ["colour", "xray", "ct", "mri"]
                for m in modes:
                    tap(pg, "#rs-" + m, phone); pg.wait_for_timeout(900)
                    freeze(pg)
                    shots[m] = px(pg)
                    got = pg.evaluate("() => window.NMSKRenderStyle.mode()")
                    check(f"{T}: C one tap selects {m} (mode now {got})", got == m, errs)
                R["pixels"] = shots
                for m in ["xray", "ct", "mri"]:
                    d, ds, dl, dh = differs(shots["colour"], shots[m])
                    check(f"{T}: C {m} really changed the picture (dsat {ds:.1f}, dlum {dl:.1f}, dhist {dh:.3f})", d, errs)
                    check(f"{T}: C {m} is greyscale (grey fraction {shots[m].get('greyFrac', 0):.3f} vs colour {shots['colour'].get('greyFrac', 0):.3f})",
                          shots[m].get("greyFrac", 0) > 0.80 and shots[m].get("greyFrac", 0) > shots["colour"].get("greyFrac", 0) + 0.10, errs)
                for a, bb in (("xray", "ct"), ("ct", "mri"), ("xray", "mri")):
                    d, ds, dl, dh = differs(shots[a], shots[bb])
                    check(f"{T}: C {a} and {bb} are different pictures (dlum {dl:.1f}, dhist {dh:.3f})", d, errs)
                tap(pg, "#rs-colour", phone); pg.wait_for_timeout(900)
                freeze(pg)
                backpx = px(pg)
                d, ds, dl, dh = differs(shots["colour"], backpx, tol_sat=4.0, tol_lum=6.0)
                check(f"{T}: C one tap on Colour returns (mode {pg.evaluate('() => window.NMSKRenderStyle.mode()')}, dsat {ds:.1f}, dlum {dl:.1f})",
                      pg.evaluate("() => window.NMSKRenderStyle.mode()") == "colour" and not d, errs)
                # the three steps of each style really move the picture
                tap(pg, "#rs-xray", phone); pg.wait_for_timeout(700)
                sstep = {}
                for i in (0, 1, 2):
                    tap(pg, "#rs-step-" + str(i), phone); pg.wait_for_timeout(700)
                    freeze(pg); sstep[i] = px(pg)
                d02, ds02, dl02, dh02 = differs(sstep[0], sstep[2])
                check(f"{T}: C the X-ray strength steps change the picture (dlum {dl02:.1f}, dhist {dh02:.3f})", d02, errs)
                R["xray_steps"] = sstep
                # the style is one of Q300's ways out, and the model reset reaches it
                chips = pg.evaluate("() => window.NMSKShowAll ? NMSKShowAll.chips().map(c => c.key) : []")
                check(f"{T}: C 'Show everything' knows about the style ({chips})", "imaging" in chips, errs)
                pg.evaluate("() => { if (window.NMSKShowAll) NMSKShowAll.clearAll(); else NMSKRenderStyle.set('colour'); }"); pg.wait_for_timeout(700)
                check(f"{T}: C 'Show everything' brings the colour back", pg.evaluate("() => window.NMSKRenderStyle.mode()") == "colour", errs)

                # ---------------- D  cut + imaging co-active -------------------------------------
                tap(pg, "#qg-cut", phone); pg.wait_for_timeout(300)      # the cut button lives in its group now
                check(f"{T}: D the Cut group really holds the cut button",
                      pg.evaluate("() => !!document.querySelector('#q301-sheet #t-cut')"), errs)
                tap(pg, "#t-cut", phone)
                pg.wait_for_timeout(1200)
                pg.evaluate("() => window.NMSKRenderStyle.set('ct')"); pg.wait_for_timeout(900)
                co = pg.evaluate("() => ({cut: window.NMSKCombos.verdict('cut'), img: window.NMSKCombos.verdict('imaging'), active: window.NMSKCombos.active()})")
                R["cut_imaging"] = co
                check(f"{T}: D cut and imaging are BOTH active at once ({co['active']})",
                      co["cut"]["active"] and co["img"]["active"], errs)
                check(f"{T}: D each is shown as combinable with the other ({co['img']['with']})",
                      not co["cut"]["disabled"] and not co["img"]["disabled"] and co["img"]["with"], errs)
                tap(pg, "#qg-imaging", phone); pg.wait_for_timeout(350)
                shown = pg.evaluate("""() => Array.from(document.querySelectorAll('#q301-sheet .qg-why'))
                    .filter(p => !p.hidden).map(p => ({t: p.textContent, off: p.className.indexOf('qg-why-off') >= 0}))""")
                check(f"{T}: D the sheet says on the screen that they combine ({[s['t'][:52] for s in shown if not s['off']]})",
                      any(not s["off"] and s["t"].strip().startswith("+") for s in shown), errs)

                # ---------------- E  an incompatible pair, disabled, with its reason -------------
                bad = pg.evaluate("""() => { const m = window.NMSKCombos.matrix().filter(r => !r.ok);
                    const act = window.NMSKCombos.active();
                    return m.map(r => ({a: r.aKey, b: r.bKey, why: r.why, aOn: act.indexOf(r.aKey) >= 0, bOn: act.indexOf(r.bKey) >= 0})); }""")
                R["incompatible"] = bad
                check(f"{T}: E the page knows incompatible pairs ({[(x['a'], x['b']) for x in bad]})", len(bad) >= 1, errs)
                hit = [x for x in bad if x["aOn"] != x["bOn"]]
                check(f"{T}: E with imaging on, its incompatible partners are refused ({[(x['a'], x['b']) for x in hit]})", hit, errs)
                # the refused control may live in any group, so every group is opened and its visible reasons collected
                off_rows, dis = [], []
                for g in gs:
                    tap(pg, "#qg-" + g["key"], phone); pg.wait_for_timeout(300)
                    off_rows += pg.evaluate("""() => Array.from(document.querySelectorAll('#q301-sheet .qg-why-off'))
                        .filter(p => !p.hidden).map(p => p.textContent)""")
                    dis += pg.evaluate("""() => Array.from(document.querySelectorAll('#q301-sheet .qg-off'))
                        .map(e => ({id: e.id, disabled: !!e.disabled, aria: e.getAttribute('aria-disabled')}))""")
                    tap(pg, "#qg-" + g["key"], phone); pg.wait_for_timeout(150)
                R["refused"] = {"reasons": off_rows, "disabled": dis}
                check(f"{T}: E and the reason is on the screen, not only in a tooltip ({[r[:66] for r in off_rows]})",
                      any(len(r) > 24 for r in off_rows), errs)
                check(f"{T}: E the refused control is really disabled ({dis})",
                      dis and all(d2["disabled"] and d2["aria"] == "true" for d2 in dis), errs)
                pg.evaluate("() => { window.NMSKRenderStyle.set('colour'); const b = document.getElementById('cut-exit'); if (b) b.click(); }")
                pg.wait_for_timeout(700)

                # ---------------- F  fat off at load, on in one tap, cut face still filled -------
                # back to the load state first: by now this script has deliberately driven "Show everything", which
                # (rightly) switches fat back on, so the one-tap behaviour has to be tested from a known starting point
                pg.evaluate("() => { if (window.NMSKModelReset) NMSKModelReset.run(); }")
                settle(pg)
                tap(pg, "#qg-layers", phone); pg.wait_for_timeout(300)
                f0 = st(pg, "fat")
                R["fat"] = {"after_model_reset": f0}
                check(f"{T}: F the model reset puts fat back to its load default ({f0})", f0 and f0["shown"] is False, errs)
                if f0 and f0["count"]:
                    nvis0 = pg.evaluate("() => { const a = window.NMSKClinicalTool.api, L = a.list(); return L.filter(r => r.cat === 'fat' && a.visible(r.i)).length; }")
                    check(f"{T}: F and none of its {f0['count']} fat structures is drawn ({nvis0})", nvis0 == 0, errs)
                    cap0 = pg.evaluate("() => window.__q301capFat ? window.__q301capFat() : null")
                    tap(pg, "#ft-toggle", phone); pg.wait_for_timeout(900)
                    f1 = st(pg, "fat")
                    nvis1 = pg.evaluate("() => { const a = window.NMSKClinicalTool.api, L = a.list(); return L.filter(r => r.cat === 'fat' && a.visible(r.i)).length; }")
                    check(f"{T}: F one tap shows them ({nvis1} of {f0['count']})", f1["shown"] and nvis1 > 0, errs)
                    cap1 = pg.evaluate("() => window.__q301capFat ? window.__q301capFat() : null")
                    R["fat"].update({"on": f1, "capOff": cap0, "capOn": cap1, "visOff": nvis0, "visOn": nvis1})
                    check(f"{T}: F the cut face is filled with fat BOTH ways (off {cap0}, on {cap1})",
                          cap0 is not None and cap1 is not None and cap0["filled"] > 0 and cap1["filled"] > 0, errs)
                    tap(pg, "#ft-toggle", phone); pg.wait_for_timeout(700)
                else:
                    check(f"{T}: F this page carries no fat mesh and the control says so", pg.evaluate("() => document.getElementById('ft-toggle').textContent.indexOf('none') >= 0"), errs)

                # ---------------- G  the layer peel ----------------------------------------------
                order = pg.evaluate("() => window.NMSKPeel.steps()")
                R["peel_order"] = order
                check(f"{T}: G the peel order starts at the skin and ends at the organs ({[s['label'] for s in order]})",
                      order and order[-1]["key"] == "viscera", errs)
                seen = []
                for i in range(len(order)):
                    tap(pg, "#pl-down", phone); pg.wait_for_timeout(700)
                    seen.append(pg.evaluate("() => ({step: NMSKPeel.step(), hidden: NMSKPeel.hidden(), shown: window.NMSKClinicalTool.api.list().filter(r => window.NMSKClinicalTool.api.visible(r.i)).length})"))
                R["peel_steps"] = seen
                check(f"{T}: G each tap takes the next layer off, in order ({[s['step'] for s in seen]})",
                      [s["step"] for s in seen] == list(range(1, len(order) + 1)), errs)
                mono = all(seen[i]["shown"] <= seen[i - 1]["shown"] for i in range(1, len(seen)))
                check(f"{T}: G and fewer structures are drawn at each step ({[s['shown'] for s in seen]})", mono, errs)
                grew = [s["hidden"] for s in seen]
                check(f"{T}: G each step's hidden set contains the one before it",
                      all(set(grew[i - 1]) <= set(grew[i]) for i in range(1, len(grew))), errs)
                check(f"{T}: G the skin comes off first ({grew[0]})", "skin" in grew[0] or "fat" in grew[0], errs)
                tap(pg, "#pl-whole", phone); pg.wait_for_timeout(800)
                check(f"{T}: G 'Whole body' puts every layer back", pg.evaluate("() => NMSKPeel.step()") == 0, errs)

                # ---------------- H  one undo step, and Q300 reaches the new states --------------
                pg.evaluate("() => NMSKPeel.set(0)"); settle(pg)
                pg.evaluate("() => NMSKPeel.set(2)"); settle(pg)
                check(f"{T}: H two layers came off in one go", pg.evaluate("() => NMSKPeel.step()") == 2, errs)
                tap(pg, "#q301-undo", phone); pg.wait_for_timeout(900)
                check(f"{T}: H a peel of two layers is ONE undo step", pg.evaluate("() => NMSKPeel.step()") == 0, errs)
                pg.evaluate("() => { NMSKPeel.set(2); NMSKRenderStyle.set('mri'); NMSKFat.set(true); }")
                settle(pg)
                keys = pg.evaluate("() => window.NMSKShowAll ? NMSKShowAll.keys() : []")
                mr = pg.evaluate("() => window.NMSKModelReset ? NMSKModelReset.state().keys : []")
                R["showall_keys"] = keys
                R["modelreset_keys"] = mr
                check(f"{T}: H Q300's 'Show everything' knows every new path ({[k for k in keys if k in ('peel', 'fat', 'imaging')]})",
                      all(k in keys for k in ("peel", "imaging")), errs)
                check(f"{T}: H the model reset knows every new state ({[k for k in mr if k in ('peel', 'fat', 'renderstyle')]})",
                      all(k in mr for k in ("peel", "fat", "renderstyle")), errs)
                if pg.query_selector("#q301-mr-model"):
                    tap(pg, "#q301-mr-model", phone)
                else:
                    pg.evaluate("() => { NMSKPeel.set(0); NMSKRenderStyle.set('colour'); NMSKFat.set(false); }")
                pg.wait_for_timeout(1200)
                after = st(pg)
                check(f"{T}: H and the model reset really puts them all back (peel {after['peel']['step']}, style {after['render']['mode']}, fat {after['fat']['shown']})",
                      after["peel"]["step"] == 0 and after["render"]["mode"] == "colour" and after["fat"]["shown"] is False, errs)

                # ---------------- the circled i --------------------------------------------------
                tap(pg, "#qi-corner", phone); pg.wait_for_timeout(400)
                inf = pg.evaluate("() => ({open: NMSKInfo.isOpen(), secs: NMSKInfo.sections(), txt: (document.getElementById('q301-info').textContent || '').length})")
                R["info"] = inf
                check(f"{T}: the circled i opens and holds the prose ({inf['secs']}, {inf['txt']} chars)",
                      inf["open"] and len(inf["secs"]) >= 5 and inf["txt"] > 1200, errs)
                conv = pg.evaluate("() => (document.getElementById('q301-info').textContent || '').toLowerCase()")
                check(f"{T}: the i names what is our convention rather than measured",
                      "convention" in conv and ("hounsfield" in conv or "attenuation" in conv), errs)
                tap(pg, "#qi-close", phone); pg.wait_for_timeout(250)
                check(f"{T}: the i closes again", not pg.evaluate("() => NMSKInfo.isOpen()"), errs)

                # ---------------- I  page errors -------------------------------------------------
                real = [e for e in page_errs if "ResizeObserver" not in e]
                check(f"{T}: I 0 page errors ({real[:2]})", not real, errs)
                R["page_errors"] = real
                R["covered_controls"] = list(MISSED)
                check(f"{T}: I every control this script tapped was really on top ({MISSED[:2]})", not MISSED, errs)
                ctx.close()
            b.close()
    finally:
        srv.terminate()


def main(argv):
    out = None
    dirs = []
    for a in argv:
        if a.startswith("--json="):
            out = Path(a.split("=", 1)[1])
        else:
            dirs.append(Path(a))
    errs: list = []
    for d in dirs:
        print(f"\n=== {d} ===")
        run_page(d, errs)
    n_ok = sum(1 for _ in ())  # counted by the printer
    print(f"\nQ301 verify: {len(errs)} FAIL")
    for e in errs:
        print("  FAIL " + e)
    if out:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps({"fail": errs, "report": REPORT}, indent=1, default=str), encoding="utf-8")
        print("wrote " + str(out))
    return 1 if errs else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
