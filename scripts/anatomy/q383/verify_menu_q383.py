#!/usr/bin/env python3
"""Q383 (owner 7.1) -- the scan workspace is the image + the transducer control; everything else is ONE central menu.

    python3 scripts/anatomy/q383/verify_menu_q383.py PAGE_DIR [--size WxH] [--shots DIR]

  A  defaults unchanged on entering the workspace (probe, frequency, depth, gain, mode, view, CINE mode, toggles)
  B  the screen: outside the menu, the transducer pad and the page's own top bar there is no control left around the image; the
     menu has its six groups, only the first one open; it scrolls inside its card (no page scroll, nothing wider than the screen)
  C  EVERY control the workspace had before this round (the fixed list below, by its id / attribute / label) is still in the page
     exactly once, is reached by a real press on its group's title, is then visible and on top, and still does its job
  D  the control ids other verifiers use are unchanged (pad ids, data-preset, data-fq-box="card", .mm-bar .mm-tog[aria-label],
     .mm-swap-btn, #us-ctlbtn, mb-undo / mb-redo / mb-reset / mb-exit)
Prints OK / FAIL lines and Q383_MENU_OK / Q383_MENU_FAIL."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common_q383 import U, Checks, enter_scan, idle, open_page  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

# (key, group, css selector | None, text the control's label contains | None)  -- the workspace's controls before Q383
CONTROLS = [
    ("depth slider", "image", 'input[type=range][aria-label="עומק"]', None),
    ("frequency -", "image", '[data-fq-box="card"] .fq-b[data-fq="-"]', None),
    ("frequency slider", "image", '[data-fq-box="card"] input.fq-r', None),
    ("frequency +", "image", '[data-fq-box="card"] .fq-b[data-fq="+"]', None),
    ("gain slider", "image", 'input[type=range][aria-label="הגבר"]', None),
    ("longitudinal", "probe", ".mc-row .mm-sec", "אורכי"),
    ("transverse", "probe", ".mc-row .mm-sec", "רוחבי"),
    ("rotate 15", "probe", ".mc-row .mm-sec", "סובב"),
    ("preset tear", "proto", '[data-preset="tear"]', None),
    ("preset entrapment", "proto", '[data-preset="entrap"]', None),
    ("preset tendon", "proto", '[data-preset="tendon"]', None),
    ("preset joint", "proto", '[data-preset="joint"]', None),
    ("A / B compare", "proto", ".mm-primary", None),
    ("CINE play", "cine", ".mm-play", None),
    ("motion types", "cine", ".mm-bar > .mm-tog", "תנועה"),
    ("full screen", "cine", '.mm-bar .mm-tog[aria-label="מסך מלא"]', None),
    ("CINE scrub", "cine", 'input[type=range][aria-label="CINE"]', None),
    ("continuous", "cine", ".mm-bar > .mm-tog", "רציף"),
    ("steps", "cine", ".mm-bar > .mm-tog", "צעדים"),
    ("tissue thickness", "layers", None, "עובי רקמה"),
    ("save image", "more", None, "שמור תמונה"),
    ("advanced settings", "more", None, "הגדרות מתקדמות"),
]
PAD = ["us-h-rl", "us-h-th", "us-h-rr", "us-h-tm", "us-h-t0", "us-h-ta", "us-h-tt"]
BAR = ["mb-undo", "mb-redo", "mb-reset"]

FIND = """([sel, txt]) => {
  const root = document.getElementById('mode-shell') || document.body;
  let L = [...root.querySelectorAll(sel || 'button')]; if (txt) L = L.filter(b => (b.textContent || '').includes(txt));     // 'includes': a toggle's label changes with its state
  L = L.filter(e => !e.closest('.fs-sheet, .us-fs, #us-root'));
  if (!L.length) return {n: 0};
  const e = L[0]; e.scrollIntoView({block: 'center'});
  const r = e.getBoundingClientRect(), t = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2), g = e.closest('details[data-g]');
  return {n: L.length, x: r.left + r.width / 2, y: r.top + r.height / 2, w: r.width, h: r.height, top: !!t && (t === e || e.contains(t) || t.contains(e)), group: g ? g.getAttribute('data-g') : null, gopen: g ? g.open : null,
    inMenu: !!e.closest('#us-menu'), right: r.right, left: r.left, over: t ? (t.tagName + '#' + t.id + '.' + String(t.className).slice(0, 30)) : null};
}"""
ST = f"() => {{ const s = {U}.state(), r = document.getElementById('us-root'); return {{probe: s.probe, freq: s.freq, depth: s.depthCm, gain: s.gain, mode: s.mode, view: s.view, cineMode: s.cineMode, cine: s.cine, thick: !!s.thickness, ab: !!s.ab, refKey: s.refKey, rot: s.rot, preset: s.preset || null, placing: s.placing, adv: !!r && !r.classList.contains('ctl-off'), fs: {U}.fsState().on, dr: s.dr, speckle: s.speckle, textures: s.textures}}; }}"


def press(pg, phone, x, y):
    if phone:
        pg.touchscreen.tap(x, y)
    else:
        pg.mouse.click(x, y)
    pg.wait_for_timeout(350)


def open_group(pg, phone, key):
    """a REAL press on the group's title; -> open afterwards"""
    r = pg.evaluate("""(k) => { const d = document.querySelector('#us-menu details[data-g="' + k + '"]'); if (!d) return null; if (d.open) return {open: true};
      const s = d.querySelector('summary'); s.scrollIntoView({block: 'center'}); const b = s.getBoundingClientRect(); return {open: false, x: b.left + b.width / 2, y: b.top + b.height / 2, h: b.height}; }""", key)
    if r is None:
        return False
    if not r["open"]:
        press(pg, phone, r["x"], r["y"])
    return bool(pg.evaluate("""(k) => document.querySelector('#us-menu details[data-g="' + k + '"]').open""", key))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("build_dir")
    ap.add_argument("--size", default="1400x900")
    ap.add_argument("--shots", default=None)
    a = ap.parse_args()
    d = Path(a.build_dir).resolve()
    W, H = (int(x) for x in a.size.split("x"))
    phone = W <= 500
    shots = Path(a.shots) if a.shots else None
    if shots:
        shots.mkdir(parents=True, exist_ok=True)
    check = Checks(); page_errors: list[str] = []
    T = f"[{d.name} {W}x{H}]"
    print(f"=== Q383 menu: {d.name} @ {W}x{H} ===")
    with sync_playwright() as pl:
        srv, b, pg = open_page(pl, d, W, H, page_errors)
        try:
            enter_scan(pg)
            if shots:
                pg.screenshot(path=str(shots / f"q383_menu_{d.name}_{W}x{H}_0_default.png"))
            s0 = pg.evaluate(ST)
            want = {"probe": "linear", "freq": 10, "depth": 5, "gain": 0, "mode": "star", "view": "matrix", "cineMode": "step", "cine": False, "thick": False, "ab": False, "refKey": "long", "rot": 0, "preset": None,
                    "placing": True, "adv": False, "dr": 60, "speckle": True, "textures": True}
            bad = {k: (s0.get(k), v) for k, v in want.items() if s0.get(k) != v}
            check(f"{T} A defaults unchanged on entering the workspace ({'all ' + str(len(want)) if not bad else bad})", not bad)

            # ---- B: the screen
            g = pg.evaluate(f"() => {U}.menu.groups()")
            check(f"{T} B the menu has its six groups {[x['key'] for x in g]}, only 'image' open", [x["key"] for x in g] == ["image", "probe", "proto", "cine", "layers", "more"] and [x["key"] for x in g if x["open"]] == ["image"])
            around = pg.evaluate("""() => {
              const vis = e => { const r = e.getBoundingClientRect(), cs = getComputedStyle(e); return r.width > 2 && r.height > 2 && cs.visibility !== 'hidden' && cs.display !== 'none' && r.bottom > 0 && r.top < innerHeight; };
              const top = e => { const r = e.getBoundingClientRect(), t = document.elementFromPoint(Math.min(innerWidth - 1, Math.max(0, r.left + r.width / 2)), Math.min(innerHeight - 1, Math.max(0, r.top + r.height / 2))); return !!t && (t === e || e.contains(t) || t.contains(e)); };
              const all = [...document.querySelectorAll('button, input, select, summary')].filter(vis).filter(top);
              const out = all.filter(e => !e.closest('#us-menu, #us-hdl, .mode-bar, #mode-bar, .mb-end, .mm-swap-btn, #hist-bar') && !e.classList.contains('mm-swap-btn'));
              const hero = document.querySelector('.mm-hero').getBoundingClientRect(), menu = document.getElementById('us-menu'), mr = menu.getBoundingClientRect();
              return {n: all.length, left: out.map(e => (e.id || e.className || e.tagName) + ':' + (e.textContent || '').trim().slice(0, 16)), hero: [hero.width, hero.height], menuScroll: [menu.scrollHeight, menu.clientHeight], menuBox: [mr.left, mr.top, mr.right, mr.bottom],
                page: [document.documentElement.scrollWidth, innerWidth], ruler: [...document.querySelectorAll('#us-root .ms-pane-b')].filter(vis).length};
            }""")
            check(f"{T} B around the image there is no control outside the menu, the pad and the page's top bar ({around['left'][:4]}); the image tiles carry no button of their own ({around['ruler']})",
                  not around["left"] and around["ruler"] == 0)
            frac = around["hero"][0] * around["hero"][1] / (W * H)
            check(f"{T} B the picture area is {around['hero'][0]:.0f} x {around['hero'][1]:.0f} px ({frac * 100:.0f} % of the screen; before Q383 {'952 x 737, 56 %' if not phone else '390 x 390, 46 %'}), no horizontal page scroll ({around['page']})",
                  around["page"][0] <= around["page"][1] + 1 and (frac >= 0.60 if not phone else frac >= 0.45))

            # ---- C: every earlier control: once in the page, reached through its group, on top, operable
            for key, grp, sel, txt in CONTROLS:
                opened = open_group(pg, phone, grp)
                f = pg.evaluate(FIND, [sel, txt])
                ok = f["n"] == 1 and opened and f.get("inMenu") and f.get("group") == grp and f.get("top") and f["w"] >= 24 and f["h"] >= 16 and f["left"] >= -1 and f["right"] <= W + 1
                check(f"{T} C '{key}': once in the page ({f['n']}), in group '{f.get('group')}' opened by a press on its title ({opened}), visible and on top ({f.get('top')}, {f.get('w', 0):.0f} x {f.get('h', 0):.0f} px)", ok)
            if shots:
                pg.screenshot(path=str(shots / f"q383_menu_{d.name}_{W}x{H}_1_all_open.png"))
            sc = pg.evaluate("() => { const m = document.getElementById('us-menu'), s = m.closest('.mm-side'); return {m: [m.scrollHeight, m.clientHeight], s: [s.scrollHeight, s.clientHeight], page: [document.documentElement.scrollHeight, innerHeight]}; }")
            check(f"{T} C with every group open the menu scrolls inside its own column (menu {sc['m']}, column {sc['s']}), the page itself does not grow ({sc['page']})",
                  (sc["m"][0] > sc["m"][1] or sc["s"][0] > sc["s"][1]) and sc["page"][0] <= sc["page"][1] + 2)

            def act(key, expect, label):
                sel, txt = next((c[2], c[3]) for c in CONTROLS if c[0] == key)
                f = pg.evaluate(FIND, [sel, txt])
                if not (f["n"] and f.get("top")):
                    check(f"{T} C operate '{key}': reachable (on top of it: {f.get('over')})", False); return None
                press(pg, phone, f["x"], f["y"]); pg.wait_for_timeout(500)
                s = pg.evaluate(ST)
                check(f"{T} C operate '{key}': {label} ({ {k: s[k] for k in expect} })", all(s[k] == v for k, v in expect.items()))
                return s

            act("transverse", {"refKey": "trans"}, "the plane turns transverse")
            act("longitudinal", {"refKey": "long"}, "and back to longitudinal")
            act("rotate 15", {"rot": 15}, "rotates 15°")
            pg.evaluate(f"() => {U}.set({{rot: 0}})")
            act("frequency +", {"freq": 11}, "11 MHz")
            act("frequency -", {"freq": 10}, "10 MHz again")
            for lab, key, val in (("עומק", "depth", 4), ("הגבר", "gain", 6)):
                pg.evaluate("([lab, v]) => { const e = document.querySelector('#us-menu input[type=range][aria-label=\"' + lab + '\"]'); e.value = String(v); e.dispatchEvent(new Event('input', {bubbles: true})); }", [lab, val])
                pg.wait_for_timeout(300)
                s = pg.evaluate(ST)
                check(f"{T} C operate '{key} slider': {key} = {s[key]}", s[key] == val)
            pg.evaluate(f"() => {U}.set({{depthCm: 5, gain: 0}})")
            act("continuous", {"cineMode": "continuous"}, "CINE mode continuous")
            act("steps", {"cineMode": "step"}, "CINE mode steps")
            act("tissue thickness", {"thick": True}, "thickness readout on")
            act("tissue thickness", {"thick": False}, "and off")
            act("advanced settings", {"adv": True}, "the advanced panel opens")
            act("advanced settings", {"adv": False}, "and closes")
            act("CINE play", {"cine": True}, "CINE plays")
            act("CINE play", {"cine": False}, "and stops")
            f = pg.evaluate(FIND, [".mm-bar > .mm-tog", "תנועה"]); press(pg, phone, f["x"], f["y"])
            check(f"{T} C operate 'motion types': the list of motion types opens inside the menu", pg.evaluate("() => { const p = document.querySelector('#us-menu .mm-mopop'); return !!p && !p.hidden && p.getBoundingClientRect().height > 20; }"))
            f = pg.evaluate(FIND, [".mm-bar > .mm-tog", "תנועה"]); press(pg, phone, f["x"], f["y"])
            f = pg.evaluate(FIND, ['[data-preset="tendon"]', None]); press(pg, phone, f["x"], f["y"]); pg.wait_for_timeout(900)
            s = pg.evaluate(ST)
            check(f"{T} C operate 'preset tendon': the preset is applied (preset {s['preset']})", s["preset"] == "tendon")
            pg.evaluate(f"() => {{ {U}.dismissWizard(); {U}.set({{cine: false}}); }}"); pg.wait_for_timeout(400)
            ms = pg.evaluate("""() => { const b = [...document.querySelectorAll('#us-menu button')].filter(x => x.textContent.trim().startsWith('מדידה'))[0]; if (!b) return null; b.scrollIntoView({block: 'center'}); const r = b.getBoundingClientRect(); return {x: r.left + r.width / 2, y: r.top + r.height / 2, n: document.querySelectorAll('#us-root .ms-pane-b').length}; }""")
            if check(f"{T} C the measuring tool of the image tiles has its entry in the menu ({ms})", bool(ms) and ms["n"] >= 1):
                press(pg, phone, ms["x"], ms["y"]); pg.wait_for_timeout(600)
                mb = pg.evaluate("() => { const e = document.querySelector('.ms-bar, #ms-bar'); return e ? !e.hidden && e.getBoundingClientRect().height > 10 : null; }")
                check(f"{T} C operate 'measure': the measuring bar opens ({mb})", mb is True)
                pg.evaluate("() => { const b = document.querySelector('#us-root .ms-pane-b'); if (b) b.click(); }"); pg.wait_for_timeout(300)
            f = pg.evaluate(FIND, ['.mm-bar .mm-tog[aria-label="מסך מלא"]', None]); press(pg, phone, f["x"], f["y"]); pg.wait_for_timeout(1500)
            check(f"{T} C operate 'full screen': the split full-screen view opens", pg.evaluate(f"() => {U}.fsState().on"))
            pg.evaluate(f"() => {U}.fs(false)"); pg.wait_for_timeout(1200)
            act("A / B compare", {"ab": True}, "the two-sided compare is on")
            act("A / B compare", {"ab": False}, "and off")

            # ---- D: ids other verifiers use
            ids = pg.evaluate("""([pad, bar]) => ({pad: pad.filter(i => document.querySelectorAll('#' + i).length === 1).length, bar: bar.filter(i => !!document.getElementById(i)).length, exit: !!document.querySelector('#mb-exit, #mb-exit-x'),
              presets: document.querySelectorAll('#mode-shell [data-preset]').length, card: document.querySelectorAll('[data-fq-box="card"]').length, fsb: document.querySelectorAll('.mm-bar .mm-tog[aria-label]').length,
              swap: document.querySelectorAll('.mm-swap-btn').length, ctl: document.querySelectorAll('#us-ctlbtn').length})""", [PAD, BAR])
            check(f"{T} D ids / selectors of other verifiers unchanged ({ids})", ids["pad"] == len(PAD) and ids["bar"] == len(BAR) and ids["exit"] and ids["presets"] == 4 and ids["card"] == 1 and ids["fsb"] == 1 and ids["swap"] == 1 and ids["ctl"] == 1)
            hd = pg.evaluate(f"() => {{ const U = {U}; const before = U.state().rot; document.getElementById('us-h-rl').click(); const mid = U.state().rot; document.getElementById('us-h-rr').click(); return [before, mid, U.state().rot]; }}")
            check(f"{T} D the transducer pad still works (rotation {hd})", hd[1] == (hd[0] + 15) % 360 and hd[2] == hd[0])
        finally:
            b.close(); srv.terminate()
    check(f"no page error ({page_errors[:2]})", not page_errors)
    print(f"{check.n - len(check.errs)} OK, {len(check.errs)} FAIL")
    print("Q383_MENU_OK" if not check.errs else "Q383_MENU_FAIL")
    return 0 if not check.errs else 1


if __name__ == "__main__":
    sys.exit(main())
