#!/usr/bin/env python3
"""Q321: the quick card, measured in a real Chromium on a Z-engine page, at 1400x900 and 390x844.

    python3 scripts/anatomy/q321/verify_quickcard_q321.py build/q309/viewer_base_female [--no-patch] [--size WxH ...]

A built page that predates the change is copied to /dev/shm and patched by the same replacements the source edit makes
(scripts/sync_quickcard_q321.py + patch_q321.py); a page that already carries the card is used as it is.
Prints OK / FAIL lines and a final Q321_QUICKCARD_OK / Q321_QUICKCARD_FAIL."""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts/anatomy/q319"))
import verify_search_q319 as V            # noqa: E402  (serve / route / open_page / press / patched_copy helpers)
from playwright.sync_api import sync_playwright  # noqa: E402

ERRS = V.ERRS
check = V.check


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def page_copy(src: Path, patch: bool) -> Path:
    d = V.patched_copy(src, patch)
    if patch:
        s321 = _load("s321", REPO / "scripts/sync_quickcard_q321.py")
        p321 = _load("p321", REPO / "scripts/anatomy/q321/patch_q321.py")
        for f in d.glob("atlas_viewer*.html"):
            t = f.read_text(encoding="utf-8")
            if "NMSKQuickCard" not in t:
                t = s321.render(t)
            f.write_text(p321.apply(t), encoding="utf-8")
    return d


CARD = "document.querySelector('.qc')"
RECT = "(e) => { const r = e.getBoundingClientRect(); return {l: r.left, t: r.top, r: r.right, b: r.bottom, w: r.width, h: r.height}; }"


def card_info(pg):
    return pg.evaluate("""() => { const c = document.querySelector('.qc'); if (!c || c.hidden) return null;
      const r = c.getBoundingClientRect(), row = c.querySelector('.qc-row'), head = c.querySelector('.qc-head');
      const bs = [...row.querySelectorAll('button')], last = bs[bs.length - 1].getBoundingClientRect();
      const nm = c.querySelector('.qc-name');
      return {name: nm.textContent, sub: c.querySelector('.qc-sub').textContent, l: r.left, t: r.top, r: r.right, b: r.bottom, w: r.width, h: r.height,
              labels: bs.map(b => b.textContent), pressed: bs.map(b => b.getAttribute('aria-pressed')),
              rowRight: Math.max(...bs.map(b => b.getBoundingClientRect().right)), rowLeft: r.left, rows: new Set(bs.map(b => Math.round(b.getBoundingClientRect().top))).size,
              sw: c.scrollWidth, ow: c.offsetWidth, nameW: nm.scrollWidth, overflow: c.scrollWidth > c.clientWidth + 1}; }""")


def state(pg):
    return pg.evaluate("""() => { const v = window.__viewerState(), s = window.NMSKSelectCtl.state();
      return {hidden: v.hidden, faded: v.faded, marks: s.marks.slice(), mode: s.mode}; }""")


def box(pg):
    return pg.evaluate("() => window.NMSKQuick.box()")


def overlap(a, b, pad=0):
    return a["l"] < b["r"] + pad and a["r"] > b["l"] - pad and a["t"] < b["b"] + pad and a["b"] > b["t"] - pad


def fixed_obstacles(pg):
    return pg.evaluate("""() => ['brand','topright','rail','foot','cut-panel','needle-panel','pm-card','info'].map(i => document.getElementById(i))
      .concat([...document.querySelectorAll('.qg-bar,.qg-sheet')]).filter(e => e && e.getClientRects().length && getComputedStyle(e).display !== 'none')
      .map(e => { const r = e.getBoundingClientRect(); return {id: e.id || e.className, l: r.left, t: r.top, r: r.right, b: r.bottom}; }).filter(r => r.r - r.l > 2 && r.b - r.t > 2)""")


def clear_card(pg):
    pg.evaluate("() => { if (window.NMSKQuick) NMSKQuick.close(); }")


def scan(pg, rx, only_layer=None, grid=26):
    """Real mouse clicks over the model's screen box until the quick card names something matching rx (and, if given, whose
    sub line starts with only_layer). Returns (x, y, card) or None."""
    b = box(pg) or {"l": 40, "t": 40, "r": pg.viewport_size["width"] - 40, "b": pg.viewport_size["height"] - 40}
    cr = pg.evaluate("() => { const r = document.querySelector('canvas').getBoundingClientRect(); return {l: r.left, t: r.top, r: r.right, b: r.bottom}; }")
    l, t, r, bt = max(b["l"], cr["l"] + 4), max(b["t"], cr["t"] + 4), min(b["r"], cr["r"] - 4), min(b["b"], cr["b"] - 4)
    for iy in range(grid):
        for ix in range(grid):
            x = l + (r - l) * (ix + 0.5) / grid; y = t + (bt - t) * (iy + 0.5) / grid
            pg.mouse.click(x, y); pg.wait_for_timeout(35)
            c = card_info(pg)
            if c and re.search(rx, c["name"], re.I) and (not only_layer or c["sub"].lower().startswith(only_layer)):
                return x, y, c
    return None


def layer_btn(pg, key, on):
    return pg.evaluate("""([k, on]) => { const b = document.querySelector('#layers [data-cat="' + k + '"] button.layer'); if (!b) return null;
      if ((b.getAttribute('aria-pressed') === 'true') !== on) b.click(); return b.getAttribute('aria-pressed'); }""", [key, on])


def solo_layers(pg, keep):
    keys = pg.evaluate("() => [...document.querySelectorAll('#layers [data-cat]')].map(e => e.getAttribute('data-cat'))")
    for k in keys:
        layer_btn(pg, k, k in keep)
    pg.wait_for_timeout(400)
    return keys


def run_size(pl, d: Path, w: int, h: int, tag: str):
    print(f"--- {tag} {w}x{h}")
    srv, b, pg = V.open_page(pl, d, w, h)
    try:
        pg.wait_for_function("window.NMSKQuick && window.NMSKHistory && NMSKHistory.active()", timeout=60000)
        pg.wait_for_timeout(1500)
        check(f"[{tag} {w}] quick card module and engine adaptor present", pg.evaluate("() => !!(window.NMSKQuick && window.NMSKQuickCard)"))
        # ---- 1. the default view: a click on the body opens the card, and it is around the model, not on it
        found = scan(pg, r".", grid=14)
        check(f"[{tag} {w}] a click on the model opens the card (first thing that opens)", found is not None)
        if not found:
            return
        x, y, c = found
        check(f"[{tag} {w}] card names the clicked structure: '{c['name']}' ({c['sub']})", bool(c["name"]) and bool(c["sub"]))
        check(f"[{tag} {w}] buttons: {c['labels']}", c["labels"][:4] == ["Hide", "Fade", "Show only", "Select"] and "Zoom to" in c["labels"] and any(l.startswith("More") for l in c["labels"]))
        full = pg.evaluate("() => { const i = document.getElementById('info'); return getComputedStyle(i).display; }")
        check(f"[{tag} {w}] the full card is not what opens first (#info display={full})", full == "none")
        bx = box(pg); obs = fixed_obstacles(pg); card = {k: c[k] for k in "ltrb"}
        P = {"l": x, "t": y, "r": x, "b": y}
        vw, vh = w, h
        check(f"[{tag} {w}] card inside the viewport ({card['l']:.0f},{card['t']:.0f})-({card['r']:.0f},{card['b']:.0f})", card["l"] >= 0 and card["t"] >= 0 and card["r"] <= vw and card["b"] <= vh)
        check(f"[{tag} {w}] card does not cover the clicked point ({x:.0f},{y:.0f})", not overlap(card, P, 6))
        hits = [o["id"] for o in obs if overlap(card, o)]
        check(f"[{tag} {w}] card clear of the fixed controls ({len(obs)} measured){' ' + str(hits) if hits else ''}", not hits)
        on_model = bool(bx and overlap(card, bx))
        if w >= 1000:
            check(f"[{tag} {w}] card outside the model's screen box ({bx and [round(bx[k]) for k in 'ltrb']})", not on_model)
        else:
            print(f"     (phone: card on the model box = {on_model}; fallback = edge farthest from the click)")
        lead = pg.evaluate("() => { const l = document.querySelector('.qc-lead'); if (!l || l.hidden) return null; const n = l.querySelector('line'); return [+n.getAttribute('x2'), +n.getAttribute('y2')]; }")
        check(f"[{tag} {w}] leader line ends at the clicked point", lead is not None and abs(lead[0] - x) < 1.5 and abs(lead[1] - y) < 1.5)
        # ---- 2. size to content
        content = c["rowRight"] - c["l"]
        check(f"[{tag} {w}] width {c['w']:.0f}px = content (row right edge {content:.0f}px incl. padding, {c['rows']} row(s), no overflow)",
              not c["overflow"] and c["w"] <= max(content, c["nameW"] + 44) + 14 and (c["rows"] == 1 or c["w"] >= vw - 40))
        # ---- 3. Escape and empty space close it
        pg.keyboard.press("Escape"); pg.wait_for_timeout(150)
        check(f"[{tag} {w}] Escape closes the card", card_info(pg) is None)
        pg.mouse.click(x, y); pg.wait_for_timeout(300)
        check(f"[{tag} {w}] a second click on the same structure opens it again", card_info(pg) is not None)
        pg.mouse.click(6, h // 2 if w < 1000 else h - 6); pg.wait_for_timeout(300)
        check(f"[{tag} {w}] a click on empty space closes it", card_info(pg) is None)
        # ---- 4. one structure of each kind, on its own layer, with real clicks
        kinds = [("muscle", r".", "muscle", {"muscle"}), ("bone", r".", "bone", {"bone"}), ("nerve", r".", "nerve", {"nerve"}), ("ligament", r"ligament", "joint", {"joint", "bone"})]
        got = {}
        for kind, rx, lay, keep in kinds:
            solo_layers(pg, keep)
            r = scan(pg, rx, lay, grid=18)
            if not r and kind == "ligament":
                r = scan(pg, r"ligament|capsule|membrane", None, grid=18)
            check(f"[{tag} {w}] click on a {kind}: card opens" + (f" -> '{r[2]['name']}' ({r[2]['sub']})" if r else " (none found on this page)"), r is not None)
            if r:
                nm = pg.evaluate("() => document.querySelector('#info h2') && document.querySelector('#info h2').textContent")
                check(f"[{tag} {w}] {kind}: card name matches the structure the page selected ('{nm}')", nm == r[2]["name"])
                got[kind] = r
            clear_card(pg)
        # ---- 5. buttons, on the muscle (all layers back on), each undone with the page's own Undo
        solo_layers(pg, {k for k in pg.evaluate("() => [...document.querySelectorAll('#layers [data-cat]')].map(e => e.getAttribute('data-cat'))")})
        pg.evaluate("() => { const u = document.getElementById('sel-undo'); }")
        m = scan(pg, r".", "muscle", grid=16) or scan(pg, r".", None, grid=14)
        check(f"[{tag} {w}] a structure to press buttons on", m is not None)
        if m:
            def press(label):
                pg.evaluate("(l) => { const b = [...document.querySelectorAll('.qc-b')].find(e => e.textContent === l); b.click(); }", label); pg.wait_for_timeout(450)
            def undo():
                pg.evaluate("() => NMSKHistory.undo()"); pg.wait_for_timeout(300)
            s0 = state(pg); nm = card_info(pg)["name"]
            press("Hide"); s = state(pg)
            check(f"[{tag} {w}] Hide removes it (hidden {s0['hidden']}->{s['hidden']}), button reads Unhide, card stays", s["hidden"] == s0["hidden"] + 1 and "Unhide" in card_info(pg)["labels"])
            undo(); s = state(pg)
            check(f"[{tag} {w}] Undo brings it back (hidden {s['hidden']})", s["hidden"] == s0["hidden"])
            press("Fade"); s = state(pg)
            check(f"[{tag} {w}] Fade fades it (faded {s0['faded']}->{s['faded']}), pressed state shown", s["faded"] == s0["faded"] + 1 and card_info(pg)["pressed"][1] == "true")
            undo(); s = state(pg)
            check(f"[{tag} {w}] Undo reverts the fade (faded {s['faded']})", s["faded"] == s0["faded"])
            press("Show only"); s = state(pg)
            check(f"[{tag} {w}] Show only isolates it (mode {s['mode']}, marks {len(s['marks'])})", s["mode"] == "only" and len(s["marks"]) == 1 and card_info(pg)["pressed"][2] == "true")
            undo(); s = state(pg)
            check(f"[{tag} {w}] Undo reverts show-only (mode {s['mode']}, marks {len(s['marks'])})", s["mode"] != "only" and len(s["marks"]) == len(s0["marks"]))
            press("Select"); s = state(pg)
            check(f"[{tag} {w}] Select marks it (marks {len(s['marks'])}), pressed state shown", len(s["marks"]) == 1 and card_info(pg)["pressed"][3] == "true")
            press("Select"); s = state(pg)
            check(f"[{tag} {w}] Select again unmarks it", len(s["marks"]) == 0)
            # More opens the full card
            press("More…")
            disp = pg.evaluate("() => getComputedStyle(document.getElementById('info')).display")
            check(f"[{tag} {w}] More... opens the full card (#info display={disp}) and closes the quick card", disp != "none" and card_info(pg) is None)
            pg.keyboard.press("Escape"); pg.wait_for_timeout(200)
            # Zoom to
            pg.mouse.click(m[0], m[1]); pg.wait_for_timeout(350)
            d0 = pg.evaluate("() => __viewerState().cam.dist")
            if card_info(pg):
                press("Zoom to"); d1 = pg.evaluate("() => __viewerState().cam.dist")
                check(f"[{tag} {w}] Zoom to focuses the structure (camera distance {d0:.0f}->{d1:.0f})", d1 != d0)
        # ---- 6. tools keep priority: with Mark mode on, a click marks and the quick card does not open
        pg.evaluate("() => { const b = document.getElementById('t-mark'); if (b) b.click(); }"); pg.wait_for_timeout(200)
        clear_card(pg); nb = len(state(pg)["marks"])
        pg.mouse.click(x, y); pg.wait_for_timeout(350)
        check(f"[{tag} {w}] Mark mode consumes the click: no quick card, marks {nb}->{len(state(pg)['marks'])}", card_info(pg) is None)
        pg.evaluate("() => { const b = document.getElementById('t-mark'); if (b) b.click(); }")
        check(f"[{tag} {w}] no page errors so far", not [e for e in ERRS if e.startswith("page error")])
    finally:
        b.close(); srv.terminate()


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    sizes = [(1400, 900), (390, 844)]
    if "--size" in sys.argv:
        sizes = [tuple(int(v) for v in a.split("x")) for a in sys.argv[sys.argv.index("--size") + 1:] if re.match(r"\d+x\d+$", a)]
        args = [a for a in args if not re.match(r"\d+x\d+$", a)]
    src = Path(args[0]) if args else REPO / "build/q309/viewer_base_female"
    d = page_copy(src, "--no-patch" not in sys.argv)
    with sync_playwright() as pl:
        for w, h in sizes:
            run_size(pl, d, w, h, src.name)
    print("Q321_QUICKCARD_FAIL" if ERRS else "Q321_QUICKCARD_OK")
    for e in ERRS:
        print("   ", e)
    return 1 if ERRS else 0


if __name__ == "__main__":
    raise SystemExit(main())
