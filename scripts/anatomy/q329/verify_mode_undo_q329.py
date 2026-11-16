#!/usr/bin/env python3
"""Q329: a workspace mode's own display state never comes back through the page-wide Undo after the mode is left.

    python3 scripts/anatomy/q329/verify_mode_undo_q329.py /dev/shm/q329/viewer_zan_atlas [--size WxH]

Runs on a built (regen) page dir as it is (no patching; the page's innervation_q322.json sidecar must be beside it).
Scenario A: enter the innervation mode, colour by nerve, pick a trunk chip (the mode marks its muscles, the rest faded), a real
click on a muscle, Hide on the click card; Undo / Redo inside the mode (the Hide toggles, the mode's colours stay); exit;
Undo, Undo again -> no innervation colour, none of the mode's layers / marks / fade comes back, the Hide is undone; Redo back
to the state the exit left. Scenario B: a user colour set before entering survives the mode, the exit and the Undo.
Also: no page-history snapshot ever carries the mode's colours. Prints OK / FAIL lines and Q329_MODEUNDO_OK / _FAIL."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts/anatomy/q319"))
import verify_search_q319 as V            # noqa: E402  (serve / route / open_page / check / ERRS)
from playwright.sync_api import sync_playwright  # noqa: E402

ERRS = V.ERRS
check = V.check
GREY = "#9aa3ab"

SNAP = """() => { const h = NMSKHistory.snapshot(), c = NMSKSelectCtl.colourState(), s = NMSKSelectCtl.state();
  return {on: (h.engine || {}).on, hid: (h.engine || {}).hid || [], ucolH: (h.selection || {}).ucol || {}, drawn: c.ids, user: c.user || c.ids,
          mode: c.mode || 0, marks: s.marks.slice().sort(), oth: s.oth, sel: s.sel, hs: NMSKHistory.state(), cur: __modesState().cur}; }"""


def snap(pg):
    return pg.evaluate(SNAP)


def wait_hist(pg):
    pg.wait_for_timeout(450)                 # the page-wide history commits 320 ms after an input settles
    pg.evaluate("() => NMSKHistory.commit()")


def no_inn(s, inn, user_ok):
    """True when nothing drawn or recorded is an innervation colour (user_ok = the user's own colours that may be drawn)."""
    drawn = {k: v for k, v in s["drawn"].items() if not (k in user_ok and user_ok[k] == v)}
    rec = {k: v for k, v in s["ucolH"].items() if not (k in user_ok and user_ok[k] == v)}
    return s["mode"] == 0 and not drawn and not rec and not (set(s["drawn"].values()) & inn - set(user_ok.values()))


def enter_inn(pg):
    pg.evaluate("() => NMSKModes.show()"); pg.wait_for_timeout(300)
    pg.evaluate("() => document.querySelector('.mw-tile[data-mode=inn]').click()"); pg.wait_for_timeout(1500)
    return pg.evaluate("() => __innState().on")


def click_muscle(pg, target):
    pg.evaluate("() => { if (window.NMSKQuick) NMSKQuick.close(); }")   # Q335: the docked name card may sit over the arm
    pt = pg.evaluate(f"() => NMSKInnervation.screenOf('{target}')")
    if not pt:
        return None
    for dx, dy in [(0, 0), (0, -8), (0, 8), (-6, 0), (6, 0), (0, -16), (0, 16), (-4, -12), (4, 12)]:
        x, y = pt[0] + dx, pt[1] + dy
        if not pg.evaluate(f"() => {{ const e = document.elementFromPoint({x}, {y}); return !!e && e.tagName === 'CANVAS'; }}"):
            continue
        pg.mouse.click(x, y); pg.wait_for_timeout(700)
        name = pg.evaluate("() => { const c = document.querySelector('.qc'); return c && !c.hidden ? c.querySelector('.qc-name').textContent : null; }")
        if name and re.search(r"biceps", name, re.I):
            return name
    return None


def press(pg, sel):
    return pg.evaluate("(s) => { const e = document.querySelector(s); if (!e) return false; e.click(); return true; }", sel)


def exit_mode(pg):
    press(pg, "#mb-exit"); pg.wait_for_timeout(1500)


def scenario(pl, d, w, h, tag, D, inn, user_hex):
    T = f"[{tag} {w} {'B user colour' if user_hex else 'A'}]"
    n0 = len(ERRS)
    srv, b, pg = V.open_page(pl, d, w, h)
    try:
        pg.wait_for_function("window.__innState && __innState().loaded && __modesState().registered.indexOf('inn') >= 0 && NMSKHistory.active()", timeout=60000)
        user = {}
        if user_hex:
            # the user's own colour, set through the Selection group's controller as its colour box does, then committed
            pg.evaluate(f"() => {{ NMSKSelectCtl.markIds(['biceps_brachii_l'], true, true, true); NMSKSelectCtl.setUserColour('{user_hex}', 'all'); NMSKSelectCtl.clear(); }}")
            wait_hist(pg)
            user = {"biceps_brachii_l": user_hex}
            check(f"{T} user colour set before the mode ({snap(pg)['drawn']})", snap(pg)["drawn"] == user)
        pre = snap(pg)
        check(f"{T} enter the innervation mode", enter_inn(pg))
        press(pg, ".inn-ctl [data-by=root]"); pg.wait_for_timeout(300)
        press(pg, ".inn-ctl [data-by=nerve]"); pg.wait_for_timeout(400)
        s = snap(pg)
        trunk = D["muscles"]["biceps_brachii"]["trunks"][0]
        want = {t["key"]: t["colour"].lower() for t in D["trunks"]}[trunk]
        check(f"{T} coloured by nerve: biceps {s['drawn'].get('biceps_brachii_l')} == {want}, {s['mode']} mode colours drawn", s["drawn"].get("biceps_brachii_l") == want and s["mode"] > 10)
        check(f"{T} the history snapshot holds no mode colour (selection.ucol {s['ucolH']})", s["ucolH"] == user)
        # a trunk chip: the mode marks its muscles, the rest faded
        press(pg, f".inn-ctl [data-kind=trunk][data-key='{trunk}']"); pg.wait_for_timeout(500)
        s_tr = snap(pg)
        check(f"{T} trunk chip {trunk}: {len(s_tr['marks'])} muscles marked, rest {s_tr['oth']}", len(s_tr["marks"]) > 0 and s_tr["oth"] == "fade")
        name = click_muscle(pg, "biceps_brachii_r")
        check(f"{T} a real click on the biceps opens the click card ('{name}')", bool(name))
        hid0 = len(snap(pg)["hid"])
        press(pg, ".qc [data-qc=hide]"); wait_hist(pg)
        s_h = snap(pg)
        check(f"{T} Hide on the click card: {len(s_h['hid'])} hidden (was {hid0}); colours still drawn ({s_h['mode']})", len(s_h["hid"]) > hid0 and s_h["mode"] > 10)
        check(f"{T} the history snapshot after Hide holds no mode colour", s_h["ucolH"] == user)
        # Undo / Redo of the user's own action inside the mode
        press(pg, "#mb-undo"); pg.wait_for_timeout(400)
        s_u = snap(pg)
        check(f"{T} Undo inside the mode: the Hide undone ({len(s_u['hid'])}), colours stay ({s_u['mode']})", len(s_u["hid"]) == hid0 and s_u["mode"] > 10 and s_u["drawn"].get("biceps_brachii_l") == want)
        press(pg, "#mb-redo"); pg.wait_for_timeout(400)
        s_r = snap(pg)
        check(f"{T} Redo inside the mode: hidden again ({len(s_r['hid'])}), colours stay", len(s_r["hid"]) == len(s_h["hid"]) and s_r["mode"] > 10)
        exit_mode(pg)
        s_x = snap(pg)
        check(f"{T} exit: mode off, no mode colour, user colours {s_x['drawn']} == {user}", s_x["cur"] is None and no_inn(s_x, inn, user) and s_x["drawn"] == user)
        check(f"{T} exit: layers, marks, groups back as before the mode", s_x["on"] == pre["on"] and s_x["marks"] == pre["marks"] and s_x["oth"] == pre["oth"])
        check(f"{T} exit: the Hide made in the mode stays ({len(s_x['hid'])})", len(s_x["hid"]) == len(s_h["hid"]))
        seen = []
        for i in (1, 2):
            if not pg.evaluate("() => NMSKHistory.canUndo()"):
                check(f"{T} Undo #{i}: nothing left to undo (fine)", True)
                break
            press(pg, "#h-undo"); pg.wait_for_timeout(500)
            s_ui = snap(pg); seen.append(s_ui)
            check(f"{T} Undo #{i} after exit: no innervation colour back (drawn {s_ui['drawn']}, mode {s_ui['mode']})", no_inn(s_ui, inn, user))
            check(f"{T} Undo #{i}: none of the mode's layers / marks / fade back (marks {len(s_ui['marks'])}, oth {s_ui['oth']}, layers {'same' if s_ui['on'] == pre['on'] else s_ui['on']})",
                  s_ui["on"] == pre["on"] and s_ui["oth"] != "fade" and not (set(s_ui["marks"]) & set(s_tr["marks"]) - set(pre["marks"])) and s_ui["cur"] is None)
            if i == 1:
                check(f"{T} Undo #1: the Hide is undone ({len(s_ui['hid'])} hidden, before the mode {len(pre['hid'])})", len(s_ui["hid"]) == len(pre["hid"]))
                if user_hex:
                    check(f"{T} Undo #1: the user colour survives ({s_ui['drawn']})", s_ui["drawn"] == user)
        n = 0
        while pg.evaluate("() => NMSKHistory.canRedo()") and n < 6:
            press(pg, "#h-redo"); pg.wait_for_timeout(450); n += 1
            check(f"{T} Redo #{n}: no innervation colour", no_inn(snap(pg), inn, user))
        s_e = snap(pg)
        check(f"{T} Redo back to the exit state: Hide again ({len(s_e['hid'])}), colours {s_e['drawn']}, layers same",
              n >= 1 and s_e["hid"] == s_x["hid"] and s_e["drawn"] == user and s_e["on"] == s_x["on"] and s_e["marks"] == s_x["marks"])
    finally:
        b.close(); srv.terminate()
    check(f"{T} 0 page errors", not any(e.startswith("page error") for e in ERRS[n0:]))


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    sizes = [(1400, 900)]
    if "--size" in sys.argv:
        sizes = [tuple(int(v) for v in a.split("x")) for a in sys.argv[sys.argv.index("--size") + 1:] if re.match(r"\d+x\d+$", a)]
        args = [a for a in args if not re.match(r"\d+x\d+$", a)]
    d = Path(args[0]).resolve() if args else Path("/dev/shm/q329/viewer_zan_atlas")
    D = json.loads((d / "innervation_q322.json").read_text(encoding="utf-8"))
    inn = {t["colour"].lower() for t in D["trunks"]} | {r["colour"].lower() for r in D["roots"]} | {GREY}
    user_hex = next(h for h in ("#e36fa6", "#3f7fd6", "#4ca65a", "#e8892b") if h not in inn)
    with sync_playwright() as pl:
        for w, h in sizes:
            print(f"--- {d.name} {w}x{h}")
            scenario(pl, d, w, h, d.name, D, inn, None)
            scenario(pl, d, w, h, d.name, D, inn, user_hex)
    print("Q329_MODEUNDO_FAIL" if ERRS else "Q329_MODEUNDO_OK")
    for e in ERRS:
        print("   ", e)
    return 1 if ERRS else 0


if __name__ == "__main__":
    raise SystemExit(main())
