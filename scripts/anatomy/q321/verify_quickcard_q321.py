#!/usr/bin/env python3
"""Q321 / Q335: the name card, measured in a real Chromium on a Z-engine page, at 1400x900 and 390x844.

    python3 scripts/anatomy/q321/verify_quickcard_q321.py build/q309/viewer_base_female [--no-patch] [--size WxH ...]

A built page is copied to /dev/shm/q321v_<dir> and, unless --no-patch, patched by the same text the source edits produce
(scripts/sync_q300.py, sync_q301.py, sync_q305.py, sync_q298.py, sync_quickcard_q321.py + scripts/anatomy/q321/patch_q321.py).
Q335 defaults: the card docks in the top-left of the view and stays there from click to click, has a grip and a three-dots
menu, draws no line while the structure is drawn in the selection tint (and never a long one), opens its details IN place
(More / Less), and carries the groups / adjacent / related row under its buttons, as wide as that row.
Prints OK / FAIL lines and a final Q321_QUICKCARD_OK / Q321_QUICKCARD_FAIL."""
from __future__ import annotations

import importlib.util
import os
import re
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts/anatomy/q319"))
import verify_search_q319 as V            # noqa: E402  (serve / route / open_page helpers)
from playwright.sync_api import sync_playwright  # noqa: E402

ERRS = V.ERRS
check = V.check
STUB_CAP = 40          # px: no line segment of the card's marker may be longer (owner: "a line that crosses the whole body")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def page_copy(src: Path, patch: bool) -> Path:
    dst = Path("/dev/shm") / ("q321v_%s_%d" % (src.name, os.getpid()))     # per run: concurrent runs never share a copy
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)
    for f in src.iterdir():
        if f.suffix == ".html":
            shutil.copy(f, dst / f.name)
        else:
            os.symlink(f.resolve(), dst / f.name)
    if patch:
        mods = [_load(n, REPO / "scripts" / (n + ".py")) for n in ("sync_q300", "sync_q301", "sync_q305", "sync_q298", "sync_quickcard_q321")]
        p321 = _load("p321", REPO / "scripts/anatomy/q321/patch_q321.py")
        for f in dst.glob("atlas_viewer*.html"):
            t = f.read_text(encoding="utf-8")
            for m in mods:
                t = m.render(t)
            f.write_text(p321.apply(t), encoding="utf-8")
    return dst


def card_info(pg):
    return pg.evaluate("""() => { const c = document.querySelector('.qc'); if (!c || c.hidden) return null;
      const r = c.getBoundingClientRect(), row = c.querySelector('.qc-row');
      const bs = [...row.querySelectorAll('button')].filter(b => !b.hidden), nm = c.querySelector('.qc-name');
      return {name: nm.textContent, sub: c.querySelector('.qc-sub').textContent, l: r.left, t: r.top, r: r.right, b: r.bottom, w: r.width, h: r.height,
              labels: bs.map(b => b.textContent), pressed: bs.map(b => b.getAttribute('aria-pressed')),
              rowRight: Math.max(...bs.map(b => b.getBoundingClientRect().right)), rows: new Set(bs.map(b => Math.round(b.getBoundingClientRect().top))).size,
              headRight: c.querySelector('.qc-x').getBoundingClientRect().right,
              chipsRight: (() => { const e = c.querySelector('#q8-exp'); if (!e || e.hidden) return 0; return e.getBoundingClientRect().right; })(),
              nameW: nm.scrollWidth, overflow: c.scrollWidth > c.clientWidth + 1, open: c.classList.contains('qc-open')}; }""")


def state(pg):
    return pg.evaluate("""() => { const v = window.__viewerState(), s = window.NMSKSelectCtl.state();
      return {hidden: v.hidden, faded: v.faded, marks: s.marks.slice(), mode: s.mode}; }""")


def box(pg):
    return pg.evaluate("() => window.NMSKQuick.box()")


def lead(pg):
    return pg.evaluate("() => window.NMSKQuick.lead()")


def overlap(a, b, pad=0):
    return a["l"] < b["r"] + pad and a["r"] > b["l"] - pad and a["t"] < b["b"] + pad and a["b"] > b["t"] - pad


def fixed_obstacles(pg):
    return pg.evaluate("""() => ['brand','topright','rail','foot','cut-panel','needle-panel','pm-card','info','pl-box'].map(i => document.getElementById(i))
      .concat([...document.querySelectorAll('.qg-bar,.qg-sheet,.ft-note,.pl-note')]).filter(e => e && !e.closest('.qc') && e.getClientRects().length && getComputedStyle(e).display !== 'none')
      .map(e => { const r = e.getBoundingClientRect(); return {id: e.id || e.className, l: r.left, t: r.top, r: r.right, b: r.bottom}; }).filter(r => r.r - r.l > 2 && r.b - r.t > 2)""")


def clear_card(pg):
    pg.evaluate("() => { if (window.NMSKQuick) NMSKQuick.close(); }")


def setp(pg, k, v):
    return pg.evaluate("([k, v]) => NMSKQuick.set(k, v)", [k, v])


def canvas_rect(pg):
    return pg.evaluate("() => { const r = document.querySelector('canvas').getBoundingClientRect(); return {l: r.left, t: r.top, r: r.right, b: r.bottom}; }")


def scan(pg, rx, only_layer=None, grid=26, avoid_card=False):
    """Real mouse clicks over the model's screen box until the card names something matching rx (and, if given, whose sub
    line starts with only_layer). Returns (x, y, card) or None."""
    b = box(pg) or {"l": 40, "t": 40, "r": pg.viewport_size["width"] - 40, "b": pg.viewport_size["height"] - 40}
    cr = canvas_rect(pg)
    l, t, r, bt = max(b["l"], cr["l"] + 4), max(b["t"], cr["t"] + 4), min(b["r"], cr["r"] - 4), min(b["b"], cr["b"] - 4)
    for iy in range(grid):
        for ix in range(grid):
            x = l + (r - l) * (ix + 0.5) / grid; y = t + (bt - t) * (iy + 0.5) / grid
            if not pg.evaluate(f"() => {{ const e = document.elementFromPoint({x}, {y}); return !!e && e.tagName === 'CANVAS'; }}"):
                continue                                   # the top bar, the rail or the card itself lie over part of the model's box
            pg.mouse.click(x, y); pg.wait_for_timeout(35 if pg.viewport_size["width"] >= 1000 else 450)   # phone: taps closer than the double-tap window read as a double-tap
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


def drag_el(pg, sel, dx, dy):
    r = pg.evaluate("(s) => { const e = document.querySelector(s); if (!e) return null; const q = e.getBoundingClientRect(); return [q.left + q.width / 2, q.top + q.height / 2]; }", sel)
    if not r:
        return False
    pg.mouse.move(r[0], r[1]); pg.mouse.down()
    for i in range(1, 9):
        pg.mouse.move(r[0] + dx * i / 8, r[1] + dy * i / 8); pg.wait_for_timeout(16)
    pg.mouse.up(); pg.wait_for_timeout(300)
    return True


def orbit(pg, x, y):
    pg.mouse.move(x, y); pg.mouse.down()
    for i in range(1, 9):
        pg.mouse.move(x + 7 * i, y + 2 * i); pg.wait_for_timeout(16)
    pg.mouse.up(); pg.wait_for_timeout(350)


def free(pg, x, y):
    return pg.evaluate(f"() => {{ const e = document.elementFromPoint({x}, {y}); return !!e && e.tagName === 'CANVAS'; }}")


def click_model(pg, x, y):
    """click (x, y) if the model is what is there; else (phone: the docked card can sit over that point) find another point"""
    if free(pg, x, y):
        pg.mouse.click(x, y); pg.wait_for_timeout(450)
        return x, y
    r = scan(pg, r".", None, grid=10)
    return (r[0], r[1]) if r else (x, y)


def wait_ready(pg):
    pg.wait_for_function("window.NMSKQuick && window.NMSKHistory && NMSKHistory.active() && window.NMSKQ305 && NMSKQ305.ready()", timeout=60000)
    pg.wait_for_timeout(1500)


def reload(pg):
    pg.reload(wait_until="load", timeout=90000)
    pg.wait_for_function("window.NMSKQ301 && window.NMSKQ298 && window.NMSKSelectCtl", timeout=90000)
    try:
        pg.wait_for_selector('.mw-tile[data-mode="anat"]', timeout=60000)
        pg.click('.mw-tile[data-mode="anat"]'); pg.wait_for_timeout(3000)
    except Exception:
        pass
    wait_ready(pg)


def menu_of(pg, key):
    """Open the box's ⋮ with a real click and describe the menu."""
    pg.evaluate("() => NMSKMove.closeMenu()")
    ok = pg.evaluate("(k) => { const d = document.getElementById('nm-d-' + k); if (!d) return false; d.click(); return true; }", key)
    if not ok:
        return None
    pg.wait_for_timeout(120)
    return pg.evaluate("""() => { const m = document.getElementById('nm-menu'); if (!m) return null; const r = m.getBoundingClientRect();
      const its = [...m.querySelectorAll('.nm-mi')];
      return {key: m.getAttribute('data-nm'), items: its.map(i => i.getAttribute('data-k') || i.textContent), w: r.width, h: r.height, l: r.left, t: r.top, r: r.right, b: r.bottom,
              overflow: m.scrollWidth > m.clientWidth + 1, widest: Math.max(...its.map(i => i.scrollWidth)), focus: document.activeElement && document.activeElement.classList.contains('nm-mi')}; }""")


def press_item(pg, k):
    return pg.evaluate("(k) => { const i = document.querySelector('#nm-menu .nm-mi[data-k=\"' + k + '\"]'); if (!i) return false; i.click(); return true; }", k)


def row_fit(pg, sel):
    """width of a row of chips against the span of its visible children"""
    return pg.evaluate("""(s) => { const e = document.querySelector(s); if (!e || e.hidden || !e.getClientRects().length) return null; const r = e.getBoundingClientRect();
      const ks = [...e.children].filter(c => c.getClientRects().length && getComputedStyle(c).display !== 'none').map(c => c.getBoundingClientRect());
      if (!ks.length) return null;
      return {w: r.width, l: r.left, r: r.right, content: Math.max(...ks.map(k => k.right)) - Math.min(...ks.map(k => k.left)), rows: new Set(ks.map(k => Math.round((k.top + k.bottom) / 8))).size, parent: e.parentNode.id}; }""", sel)


CONTRAST = """(sel) => {
  function rgb(c){ const m = c.match(/rgba?\\(([^)]+)\\)/); if (!m) return null; const p = m[1].split(',').map(Number); return {r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1}; }
  function lum(c){ const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b); }
  function over(top, bot){ return {r: top.r * top.a + bot.r * (1 - top.a), g: top.g * top.a + bot.g * (1 - top.a), b: top.b * top.a + bot.b * (1 - top.a), a: 1}; }
  function bg(e){ const st = []; let n = e; while (n && n.nodeType === 1){ const c = rgb(getComputedStyle(n).backgroundColor); if (c && c.a > 0) st.push(c); if (c && c.a >= 0.999) break; n = n.parentElement; }
    let out = {r: 40, g: 40, b: 40, a: 1}; for (let i = st.length - 1; i >= 0; i--) out = over(st[i], out); return out; }
  const bad = [];
  document.querySelectorAll(sel).forEach(e => { if (!e.getClientRects().length || getComputedStyle(e).visibility === 'hidden' || !e.textContent.trim()) return;
    const cs = getComputedStyle(e); let op = 1, n = e; while (n && n.nodeType === 1){ op *= +getComputedStyle(n).opacity; n = n.parentElement; }
    const b = bg(e); let f = rgb(cs.color); f = over({r: f.r, g: f.g, b: f.b, a: f.a * op}, b);
    const L1 = lum(f), L2 = lum(b), cr = (Math.max(L1, L2) + 0.05) / (Math.min(L1, L2) + 0.05);
    const need = (e.disabled || e.getAttribute('aria-disabled') === 'true') ? 3 : 4.5;
    if (cr < need) bad.push(e.textContent.trim().slice(0, 24) + ' ' + cr.toFixed(2)); });
  return bad; }"""


def contrast_fail(pg, sel):
    return pg.evaluate(CONTRAST, sel)


def dev_strings(pg):
    return pg.evaluate("""() => { const t = document.body.innerText.toLowerCase(); return ['voxel', 'scripts/', 'rasterised', 'rasterized', '.py'].filter(w => t.includes(w)); }""")


def grip_text(pg, key):
    """text of the box that lies under its grip or its ⋮ (owner: 'a grip must have its own space, never overlap text')"""
    return pg.evaluate("""(k) => { const g = document.getElementById('nm-g-' + k), d = document.getElementById('nm-d-' + k); if (!g) return null;
      const box = g.closest('[id]') && (NMSKMove.box(k) && (typeof NMSKMove.box(k).el === 'function' ? NMSKMove.box(k).el() : document.getElementById(NMSKMove.box(k).el)));
      if (!box) return null; const rs = [g, d].filter(Boolean).map(e => e.getBoundingClientRect()); const hits = [];
      const w = document.createTreeWalker(box, NodeFilter.SHOW_TEXT); let n;
      while ((n = w.nextNode())){ if (!n.textContent.trim() || (n.parentElement && (n.parentElement.closest('.nm-grip,.nm-dots')))) continue;
        const pe = n.parentElement; if (!pe || !pe.getClientRects().length || getComputedStyle(pe).visibility === 'hidden') continue;
        const rg = document.createRange(); rg.selectNodeContents(n);
        for (const q of rg.getClientRects()) for (const r of rs) if (q.left < r.right - 1 && q.right > r.left + 1 && q.top < r.bottom - 1 && q.bottom > r.top + 1) hits.push(n.textContent.trim().slice(0, 20)); }
      return [...new Set(hits)]; }""", key)


def boxes_overlap(pg):
    """the phone layout: no two of card / chips strip / toolbar / bottom chips / title overlap"""
    return pg.evaluate("""() => { const L = [['card', document.querySelector('.qc')], ['strip', document.getElementById('q8-float')], ['toolbar', document.getElementById('q301-bar')], ['pills', document.getElementById('topright')],
        ['hidden', document.getElementById('sa-bar')], ['title', document.getElementById('brand')]].concat([...document.querySelectorAll('.pz-chip')].map(z => ['zoom', z]));
      const R = L.filter(([n, e]) => e && !e.hidden && e.getClientRects().length && getComputedStyle(e).display !== 'none' && getComputedStyle(e).visibility !== 'hidden')
        .map(([n, e]) => { const r = e.getBoundingClientRect(); return {n, l: r.left, t: r.top, r: r.right, b: r.bottom}; }).filter(r => r.r - r.l > 2 && r.b - r.t > 2);
      const out = []; for (let i = 0; i < R.length; i++) for (let j = i + 1; j < R.length; j++){ const a = R[i], b = R[j];
        if (a.l < b.r - 1 && a.r > b.l + 1 && a.t < b.b - 1 && a.b > b.t + 1) out.push(a.n + '/' + b.n); }
      return {pairs: out, present: R.map(r => r.n)}; }""")


def box_menu_tests(pg, T, k, w, h):
    mn = menu_of(pg, k)
    good = mn is not None and mn["key"] == k and all(i in mn["items"] for i in ("dock-tl", "dock-tr", "dock-bl", "dock-br", "reset"))
    check(f"{T} ⋮ on '{k}' opens its menu ({mn and len(mn['items'])} items, {mn and round(mn['w'])} px wide, sized to content)",
          good and not mn["overflow"] and mn["w"] <= mn["widest"] + 14 and mn["r"] <= w and mn["b"] <= h)
    pg.keyboard.press("Escape"); pg.wait_for_timeout(100)
    gone = pg.evaluate("() => !document.getElementById('nm-menu')")
    gt = grip_text(pg, k)
    check(f"{T} '{k}': its grip and ⋮ cover none of its text{' ' + str(gt) if gt else ''}", not gt)
    r0 = pg.evaluate("(k) => NMSKMove.rect(k)", k)
    menu_of(pg, k); press_item(pg, "dock-br"); pg.wait_for_timeout(250)
    r1 = pg.evaluate("(k) => NMSKMove.rect(k)", k); off = pg.evaluate("(k) => NMSKMove.off(k)", k)
    # a dock that would cover a control is refused with a note and the box stays (the Q305 rule) -- that is a pass too
    refused = pg.evaluate("() => { const n = document.querySelector('.nm-note'); return !!n && !n.hidden && /^Not there/.test(n.textContent); }") and bool(r0 and r1) \
        and abs(r1["left"] - r0["left"]) < 3 and abs(r1["top"] - r0["top"]) < 3
    pg.evaluate("() => { const n = document.querySelector('.nm-note'); if (n) n.hidden = true; }")
    moved = bool(r0 and r1) and (abs(r1["left"] - r0["left"]) > 2 or abs(r1["top"] - r0["top"]) > 2 or (r0["left"] + r0["width"] >= w - 40 and r0["top"] + r0["height"] >= h - 40))
    toward = bool(r1) and (r1["width"] > w / 2 or r1["left"] + r1["width"] / 2 > w / 2) and (r1["height"] > h / 2 or r1["top"] + r1["height"] / 2 > h / 2)
    menu_of(pg, k); press_item(pg, "reset"); pg.wait_for_timeout(250)
    r2 = pg.evaluate("(k) => NMSKMove.rect(k)", k); off2 = pg.evaluate("(k) => NMSKMove.off(k)", k)
    back = bool(r0 and r2) and abs(r2["left"] - r0["left"]) < 3 and abs(r2["top"] - r0["top"]) < 3 and not off2["dx"] and not off2["dy"] and not off2["slot"]
    check(f"{T} '{k}': Escape closes the menu, Dock bottom-right moves it there ({r0 and (r0['left'], r0['top'])}->{r1 and (r1['left'], r1['top'])}, off {off}), Reset puts it back"
          f" [closed={gone} moved={moved} toward={toward} refused={refused} back={back} {r2 and (r2['left'], r2['top'])}]",
          gone and ((moved and toward) or refused) and back)


def run_size(pl, d: Path, w: int, h: int, tag: str):
    print(f"--- {tag} {w}x{h}")
    srv, b, pg = V.open_page(pl, d, w, h)
    desk = w >= 1000
    T = f"[{tag} {w}]"
    try:
        wait_ready(pg)
        check(f"{T} card module, engine adaptor and the box mover present", pg.evaluate("() => !!(window.NMSKQuick && window.NMSKQuickCard && window.NMSKMove && NMSKMove.menu)"))
        check(f"{T} defaults: {pg.evaluate('() => NMSKQuick.prefs()')}", pg.evaluate("() => { const p = NMSKQuick.prefs(); return p.pos === 'tl' && p.lead === 'auto' && p.chips === 'card'; }"))
        # ---- 1. a click opens the card, docked top-left, clear of the chrome, the same place on the next click
        found = scan(pg, r".", grid=14)
        check(f"{T} a click on the model opens the card (first thing that opens)", found is not None)
        if not found:
            return
        x, y, c = found
        check(f"{T} card names the clicked structure: '{c['name']}' ({c['sub']})", bool(c["name"]) and bool(c["sub"]))
        check(f"{T} buttons: {c['labels']}", c["labels"][:4] == ["Hide", "Fade", "Show only", "Select"] and "Zoom to" in c["labels"] and any(l.startswith("More") for l in c["labels"]))
        full = pg.evaluate("() => getComputedStyle(document.getElementById('info')).display")
        check(f"{T} the full card is not what opens first (#info display={full})", full == "none")
        cr = canvas_rect(pg); obs = fixed_obstacles(pg); card = {k: c[k] for k in "ltrb"}
        check(f"{T} docked top-left: ({card['l']:.0f},{card['t']:.0f}) in the upper-left of the view", card["l"] <= cr["l"] + 260 and card["t"] <= cr["t"] + h * 0.4 and card["l"] >= 0 and card["t"] >= 0 and card["r"] <= w)
        hits = [o["id"] for o in obs if overlap(card, o)]
        check(f"{T} card clear of the fixed controls ({len(obs)} measured){' ' + str(hits) if hits else ''}", not hits)
        ld = lead(pg)
        check(f"{T} auto line: none while the structure is drawn in the selection tint (line={ld})", ld is None)
        content = max(c["rowRight"], c["chipsRight"]) - c["l"]
        check(f"{T} width {c['w']:.0f}px = content ({content:.0f}px incl. padding, {c['rows']} row(s), no overflow)",
              not c["overflow"] and c["w"] <= max(content, c["nameW"] + 90) + 14 and (c["rows"] == 1 or c["w"] >= w - 40))
        found2 = scan(pg, r"^(?!" + re.escape(c["name"]) + r"$)", grid=11)
        if found2:
            c2 = found2[2]
            check(f"{T} stable: a click on '{c2['name']}' leaves it at the same corner ({c2['l']:.0f},{c2['t']:.0f})", abs(c2["l"] - c["l"]) < 1.5 and abs(c2["t"] - c["t"]) < 1.5)
            x, y = found2[0], found2[1]
        ox, oy = (x, y)
        orbit(pg, *((x, y) if free(pg, x, y) else (w // 2, int(h * 0.8))))
        c3 = card_info(pg)
        check(f"{T} docked card stays while the model is orbited (and at the same place)", c3 is not None and abs(c3["l"] - card["l"]) < 1.5 and abs(c3["t"] - card["t"]) < 1.5)
        tb = pg.evaluate("() => { const b = document.getElementById('q301-bar'); const r = b.getBoundingClientRect(); return r.height; }")
        if not desk:
            check(f"{T} the toolbar is one row on a phone ({tb:.0f} px = {100 * tb / h:.1f}% of the view, <= 12%)", tb <= 0.12 * h)
        sh = pg.evaluate("""() => { for (const id of ['zan_common_flexor_tendon_sheath_l', 'zan_common_flexor_tendon_sheath_r']){ NMSKQuick.open(id, 200, 400);
            const c = document.querySelector('.qc'); if (c && !c.hidden && NMSKQuick.current() === id) return c.querySelector('.qc-sub').textContent; } return null; }""")
        if sh is not None:
            check(f"{T} a tendon sheath is named as one, not by its system ('{sh}')", sh.lower().startswith("tendon sheath"))
        else:
            print("     (no common flexor tendon sheath on this page)")
        clear_card(pg)
        # ---- 2. groups / adjacent / related: ONE "Related structures" button on the card, opening a small menu (default);
        #         or the strip at the bottom of the screen. Short user lines, the method behind an (i), contrast, stale lines.
        rr = scan(pg, r".", None, grid=10)              # the orbit turned the model: find a structure again
        if rr:
            ox, oy = rr[0], rr[1]
        pg.wait_for_timeout(800)
        rb = pg.evaluate("() => { const b = document.querySelector('.qc .qc-relb'); return b && !b.hidden && b.getClientRects().length ? b.textContent : null; }")
        exp_vis = pg.evaluate("() => { const e = document.getElementById('q8-exp'); return !!e && e.getClientRects().length > 0; }")
        check(f"{T} the card carries ONE '{rb}' button, not a row of chips (row visible={exp_vis})", bool(rb) and rb.startswith("Related structures") and not exp_vis)
        fl = pg.evaluate("() => document.getElementById('q8-float').hidden")
        check(f"{T} no strip at the bottom while they live on the card", fl is True)
        pg.evaluate("() => document.querySelector('.qc .qc-relb').click()"); pg.wait_for_timeout(250)
        rm = pg.evaluate("""() => { const m = document.getElementById('qc-relmenu'); if (!m) return null; const r = m.getBoundingClientRect(); const its = [...m.querySelectorAll('.qc-rmi')];
          return {fams: its.map(i => i.getAttribute('data-fam')), labels: its.map(i => i.textContent), w: r.width, widest: Math.max(...its.map(i => i.scrollWidth)), r: r.right, b: r.bottom,
                  focus: document.activeElement && document.activeElement.classList.contains('qc-rmi')}; }""")
        check(f"{T} 'Related structures' opens a menu {rm and rm['labels']} sized to content ({rm and round(rm['w'])} px)",
              rm is not None and rm["fams"][:3] == ["grp", "adj", "rel"] and rm["w"] <= rm["widest"] + 14 and rm["r"] <= w and rm["b"] <= h and rm["focus"])
        bad = contrast_fail(pg, "#qc-relmenu .qc-rmi, .qc .qc-b")
        check(f"{T} card and menu text readable (contrast){' ' + str(bad[:3]) if bad else ''}", not bad)
        pg.keyboard.press("Escape"); pg.wait_for_timeout(120)
        check(f"{T} Escape closes the menu first, the card stays", pg.evaluate("() => !document.getElementById('qc-relmenu')") and card_info(pg) is not None)
        n0 = len(state(pg)["marks"])
        pg.evaluate("() => document.querySelector('.qc .qc-relb').click()"); pg.wait_for_timeout(200)
        okadj = pg.evaluate("() => { const i = document.querySelector('#qc-relmenu .qc-rmi[data-fam=adj]'); if (!i || i.classList.contains('qc-off')) return false; i.click(); return true; }")
        pg.wait_for_timeout(600)
        if okadj:
            n1 = len(state(pg)["marks"])
            st_ = pg.evaluate("""() => { const s = document.getElementById('q8-status'); if (!s) return null; const r = s.getBoundingClientRect();
              return {text: s.firstChild ? s.firstChild.textContent : '', inCard: !!s.closest('.qc'), shown: r.height > 0, info: !!s.querySelector('.q8-i')}; }""")
            check(f"{T} Adjacent from the menu marks the neighbours (marks {n0}->{n1}) and says one short line in the card: '{st_ and st_['text']}'",
                  n1 > n0 and st_ and st_["inCard"] and st_["shown"] and len(st_["text"]) <= 70 and st_["info"])
            dev = dev_strings(pg)
            check(f"{T} no developer text visible (voxel / scripts/ / rasterised){' ' + str(dev) if dev else ''}", not dev)
            pg.evaluate("() => document.querySelector('#q8-status .q8-i').click()"); pg.wait_for_timeout(120)
            more = pg.evaluate("() => { const d = document.querySelector('#q8-status .q8-more'); return d && !d.hidden ? d.textContent : null; }")
            check(f"{T} the (i) opens the method on request, without a script path ({more and len(more)} chars)", bool(more) and "scripts/" not in more)
            pg.evaluate("() => document.querySelector('#q8-status .q8-i').click()")
            pg.evaluate("() => NMSKHistory.undo()"); pg.wait_for_timeout(300)
            check(f"{T} Undo takes the marks back ({len(state(pg)['marks'])} == {n0})", len(state(pg)["marks"]) == n0)
            # stale: another structure -> the line about the old one goes
            o2 = scan(pg, r"^(?!" + re.escape(card_info(pg)["name"]) + r"$)", grid=11)
            pg.wait_for_timeout(900)
            stale = pg.evaluate("() => { const s = document.getElementById('q8-status'); return s ? s.textContent : ''; }")
            check(f"{T} after another structure is picked the old line is gone ('{stale[:40]}')", o2 is not None and not stale)
        setp(pg, "chips", "bottom"); pg.wait_for_timeout(900)
        f2 = row_fit(pg, "#q8-exp"); fb = pg.evaluate("() => { const e = document.getElementById('q8-float'); if (e.hidden) return null; const r = e.getBoundingClientRect(); return {l: r.left, r: r.right, w: r.width, b: r.bottom}; }")
        check(f"{T} bottom placement: the chips move to the strip ({f2 and f2['parent']}), the card's button hides",
              f2 is not None and f2["parent"] == "q8-float" and fb is not None and pg.evaluate("() => document.querySelector('.qc .qc-relb').hidden"))
        if f2 and fb:
            pad = 68 + 8 + 2 + 14     # the strip's own padding (room for its grip and ⋮) and border
            # one row: as wide as that row; wrapped (a phone, the chips need it): no wider than the view allows
            check(f"{T} bottom strip width {fb['w']:.0f} = its row {f2['content']:.0f} + padding ({f2['rows']} row(s)), not a full-width row",
                  (fb["w"] <= f2["content"] + pad + 4 if f2["rows"] == 1 else (not desk and fb["w"] <= w - 14))
                  and (fb["w"] < w * 0.7 if desk else fb["w"] <= w - 14) and fb["b"] >= h - 90 - (60 if not desk else 0))
            bad = contrast_fail(pg, "#q8-float .q8-b")
            check(f"{T} strip chips readable in every state (contrast){' ' + str(bad[:3]) if bad else ''}", not bad)
            mb = menu_of(pg, "expand")
            check(f"{T} the strip's ⋮ menu carries the placement choice ({mb and mb['items'][-2:]})", mb is not None and "chips-card" in mb["items"] and "chips-bottom" in mb["items"])
            pg.evaluate("() => NMSKMove.closeMenu()")
            gt = grip_text(pg, "expand")
            check(f"{T} the strip's grip and ⋮ have their own space (no text under them){' ' + str(gt) if gt else ''}", not gt)
        setp(pg, "chips", "card"); pg.wait_for_timeout(900)
        f3 = pg.evaluate("() => { const e = document.getElementById('q8-exp'); return e ? e.parentNode.id : null; }")
        check(f"{T} back on the card ({f3})", f3 == "qc-chips")
        # ---- 3. Escape and empty space close it
        pg.keyboard.press("Escape"); pg.wait_for_timeout(150)
        check(f"{T} Escape closes the card", card_info(pg) is None)
        ox, oy = click_model(pg, ox, oy)
        check(f"{T} a second click on the same structure opens it again", card_info(pg) is not None)
        pg.mouse.click(6, h // 2 if not desk else h - 6); pg.wait_for_timeout(300)
        check(f"{T} a click on empty space closes it", card_info(pg) is None)
        # ---- 4. one structure of each kind, on its own layer, with real clicks
        kinds = [("muscle", r".", "muscle", {"muscle"}), ("bone", r".", "bone", {"bone"}), ("nerve", r".", "nerve", {"nerve"}), ("ligament", r"ligament", "joint", {"joint", "bone"})]
        for kind, rx, lay, keep in kinds:
            solo_layers(pg, keep)
            r = scan(pg, rx, lay, grid=18)
            if not r and kind == "ligament":
                r = scan(pg, r"ligament|capsule|membrane", None, grid=18)
            check(f"{T} click on a {kind}: card opens" + (f" -> '{r[2]['name']}' ({r[2]['sub']})" if r else " (none found on this page)"), r is not None)
            if r:
                nm = pg.evaluate("() => document.querySelector('#info h2') && document.querySelector('#info h2').textContent")
                check(f"{T} {kind}: card name matches the structure the page selected ('{nm}')", nm == r[2]["name"])
            clear_card(pg)
        # ---- 5. buttons, on a muscle (all layers back on), each undone with the page's own Undo
        solo_layers(pg, {k for k in pg.evaluate("() => [...document.querySelectorAll('#layers [data-cat]')].map(e => e.getAttribute('data-cat'))")})
        m = scan(pg, r".", "muscle", grid=16) or scan(pg, r".", None, grid=14)
        check(f"{T} a structure to press buttons on", m is not None)
        if m:
            def press(label):
                pg.evaluate("(l) => { const b = [...document.querySelectorAll('.qc-b')].find(e => e.textContent === l); b.click(); }", label); pg.wait_for_timeout(450)

            def undo():
                pg.evaluate("() => NMSKHistory.undo()"); pg.wait_for_timeout(300)
            s0 = state(pg)
            press("Hide"); s = state(pg)
            check(f"{T} Hide removes it (hidden {s0['hidden']}->{s['hidden']}), button reads Unhide, card stays", s["hidden"] == s0["hidden"] + 1 and "Unhide" in card_info(pg)["labels"])
            ld = lead(pg)
            check(f"{T} auto line once it is no longer coloured: a short marker at the point ({ld and round(ld['len'])} px <= {STUB_CAP})",
                  ld is not None and ld["len"] <= STUB_CAP and abs(ld["x2"] - m[0]) < 1.5 and abs(ld["y2"] - m[1]) < 1.5)
            snapA = pg.evaluate("() => JSON.stringify(NMSKHistory.snapshot())"); stA = pg.evaluate("() => NMSKHistory.state()")
            pg.wait_for_timeout(900)
            ov = boxes_overlap(pg)
            check(f"{T} layout with something hidden: no overlap among {ov['present']}{' ' + str(ov['pairs']) if ov['pairs'] else ''}", not ov["pairs"] and "hidden" in ov["present"])
            gt = grip_text(pg, "hidden")
            check(f"{T} the hidden bar's grip and ⋮ cover none of its text{' ' + str(gt) if gt else ''}", gt == [])
            bad = contrast_fail(pg, "#sa-bar .sa-t, #sa-bar .sa-all")
            check(f"{T} hidden bar text readable{' ' + str(bad) if bad else ''}", not bad)
            snapB = pg.evaluate("() => JSON.stringify(NMSKHistory.snapshot())"); stB = pg.evaluate("() => NMSKHistory.state()")
            if snapA != snapB or stA["idx"] != stB["idx"]:
                import json as _j
                a_, b_ = _j.loads(snapA), _j.loads(snapB)
                print(f"     (history moved during the checks: idx {stA['idx']}->{stB['idx']}; keys changed: {[k for k in set(a_) | set(b_) if a_.get(k) != b_.get(k)]})")
                for k in [k for k in set(a_) | set(b_) if a_.get(k) != b_.get(k)]:
                    print("       ", k, str(a_.get(k))[:200], "->", str(b_.get(k))[:200])
            pg.evaluate("() => { window.__qlog = []; const o = NMSKQuick.close; if (!o.__w){ NMSKQuick.close = function(){ window.__qlog.push(new Error().stack.split('\\n').slice(1, 7).join(' | ')); return o.apply(this, arguments); }; NMSKQuick.close.__w = 1; } }")
            undo(); s = state(pg)
            check(f"{T} Undo brings it back (hidden {s['hidden']}), the card stays (closed by: {pg.evaluate('() => window.__qlog')})", s["hidden"] == s0["hidden"] and card_info(pg) is not None)
            press("Fade"); s = state(pg)
            check(f"{T} Fade fades it (faded {s0['faded']}->{s['faded']}), pressed state shown", s["faded"] == s0["faded"] + 1 and card_info(pg)["pressed"][1] == "true")
            undo(); s = state(pg)
            check(f"{T} Undo reverts the fade (faded {s['faded']})", s["faded"] == s0["faded"])
            press("Show only"); s = state(pg)
            check(f"{T} Show only isolates it (mode {s['mode']}, marks {len(s['marks'])})", s["mode"] == "only" and len(s["marks"]) == 1 and card_info(pg)["pressed"][2] == "true")
            undo(); s = state(pg)
            check(f"{T} Undo reverts show-only (mode {s['mode']}, marks {len(s['marks'])})", s["mode"] != "only" and len(s["marks"]) == len(s0["marks"]))
            press("Select"); s = state(pg)
            check(f"{T} Select marks it (marks {len(s['marks'])}), pressed state shown", len(s["marks"]) == 1 and card_info(pg)["pressed"][3] == "true")
            press("Select"); s = state(pg)
            check(f"{T} Select again unmarks it", len(s["marks"]) == 0)
            # More: the details open IN the same window, at the same place, and the window still moves
            before = card_info(pg)
            press("More…"); pg.wait_for_timeout(300)
            after = card_info(pg)
            det = pg.evaluate("() => { const i = document.getElementById('info'); return {inCard: !!i.closest('.qc'), disp: getComputedStyle(i).display, h: i.getBoundingClientRect().height}; }")
            check(f"{T} More opens the details inside the same window (in card={det['inCard']}, display={det['disp']}, {det['h']:.0f}px)",
                  after is not None and after["open"] and det["inCard"] and det["disp"] != "none" and det["h"] > 30)
            check(f"{T} after More the window's top-left is unchanged ({before['l']:.0f},{before['t']:.0f})->({after and round(after['l'])},{after and round(after['t'])})",
                  after is not None and abs(after["l"] - before["l"]) < 1.5 and abs(after["t"] - before["t"]) < 1.5)
            check(f"{T} expanded window stays inside the view (bottom {after and round(after['b'])} <= {h})", after is not None and after["b"] <= h + 1)
            drag_el(pg, "#nm-g-qcard", 40, 30); a2 = card_info(pg)
            check(f"{T} expanded window is still draggable by its grip ({after and round(after['l'])},{after and round(after['t'])})->({a2 and round(a2['l'])},{a2 and round(a2['t'])})"
                  + ("" if desk else " (phone: snaps to a slot)"),
                  a2 is not None and a2["open"] and ((abs(a2["l"] - after["l"] - 40) < 3 and abs(a2["t"] - after["t"] - 30) < 3) if desk
                                                     else abs(a2["l"] - after["l"]) + abs(a2["t"] - after["t"]) > 10))
            press("Less"); pg.wait_for_timeout(200)
            l2 = card_info(pg); det2 = pg.evaluate("() => !!document.getElementById('info').closest('.qc')")
            check(f"{T} Less folds the details back (card open={l2 and l2['open']}, details in card={det2})", l2 is not None and not l2["open"] and not det2)
            pg.evaluate("() => NMSKMove.reset('qcard')"); pg.wait_for_timeout(200)
            # Zoom to
            d0 = pg.evaluate("() => __viewerState().cam.dist")
            if card_info(pg):
                press("Zoom to"); d1 = pg.evaluate("() => __viewerState().cam.dist")
                check(f"{T} Zoom to focuses the structure (camera distance {d0:.0f}->{d1:.0f})", d1 != d0)
            pg.evaluate("() => { const r = document.getElementById('q301-mr-model'); if (r) r.click(); }"); pg.wait_for_timeout(600)
        # ---- 6. the line modes
        clear_card(pg)
        for mode in ("always", "never", "auto"):
            setp(pg, "lead", mode)
            r = scan(pg, r".", None, grid=12)
            if not r:
                check(f"{T} line mode {mode}: a structure to click", False); continue
            ld = lead(pg)
            if mode == "always":
                check(f"{T} line 'Always': a short marker ending at the clicked point ({ld and round(ld['len'])} px <= {STUB_CAP})",
                      ld is not None and ld["len"] <= STUB_CAP and abs(ld["x2"] - r[0]) < 1.5 and abs(ld["y2"] - r[1]) < 1.5)
            else:
                check(f"{T} line '{mode}': no line ({ld})", ld is None)
        # ---- 7. the position modes
        setp(pg, "pos", "point"); clear_card(pg)
        r = scan(pg, r".", None, grid=12)
        if r:
            cp = card_info(pg); P = {"l": r[0], "t": r[1], "r": r[0], "b": r[1]}; bx = box(pg)
            check(f"{T} 'Beside the clicked point': does not cover the point ({r[0]:.0f},{r[1]:.0f})", not overlap(cp, P, 6))
            if desk:
                check(f"{T} 'Beside the clicked point': outside the model's screen box", not (bx and overlap(cp, bx)))
            hits = [o["id"] for o in fixed_obstacles(pg) if overlap(cp, o)]
            check(f"{T} 'Beside the clicked point': clear of the fixed controls {hits if hits else ''}", not hits)
            orbit(pg, *((r[0], r[1]) if free(pg, r[0], r[1]) else (w // 2, int(h * 0.8))))
            check(f"{T} 'Beside the clicked point': an orbit closes it, as before", card_info(pg) is None)
        setp(pg, "pos", "tl"); clear_card(pg)
        r = scan(pg, r".", None, grid=12)
        if r:
            c0 = card_info(pg)
            drag_el(pg, "#nm-g-qcard", 60, 45 if desk else 160); c1 = card_info(pg)
            p1 = pg.evaluate("() => NMSKQuick.prefs().pos")
            check(f"{T} drag by the grip moves it ({c0['l']:.0f},{c0['t']:.0f})->({c1 and round(c1['l'])},{c1 and round(c1['t'])}) and the mode becomes '{p1}'",
                  c1 is not None and p1 == "drag" and ((abs(c1["l"] - c0["l"] - 60) < 3 and abs(c1["t"] - c0["t"] - 45) < 3) if desk
                                                       else abs(c1["l"] - c0["l"]) + abs(c1["t"] - c0["t"]) > 10))
            setp(pg, "pos", "tl"); c2 = card_info(pg)
            check(f"{T} 'Top-left' puts it back in the corner, the dragged place kept", c2 is not None and abs(c2["l"] - c0["l"]) < 1.5 and abs(c2["t"] - c0["t"]) < 1.5)
            setp(pg, "pos", "drag"); c3 = card_info(pg)
            check(f"{T} 'Where I dragged it' brings it back to the dragged place", c3 is not None and abs(c3["l"] - c1["l"]) < 1.5 and abs(c3["t"] - c1["t"]) < 1.5)
            reload(pg)
            r2 = scan(pg, r".", None, grid=12)
            c4 = r2 and card_info(pg)
            check(f"{T} after a reload the card opens where it was dragged ({c4 and round(c4['l'])},{c4 and round(c4['t'])}), mode '{pg.evaluate('() => NMSKQuick.prefs().pos')}'",
                  bool(c4) and abs(c4["l"] - c1["l"]) < 2.5 and abs(c4["t"] - c1["t"]) < 2.5)
            mq = menu_of(pg, "qcard")
            check(f"{T} name card ⋮: position / line / groups / buttons items ({mq and len(mq['items'])} items)",
                  mq is not None and all(k in mq["items"] for k in ("pos-tl", "pos-point", "pos-drag", "lead-auto", "lead-always", "lead-never", "chips-card", "chips-bottom", "show-zoom", "size", "close")))
            press_item(pg, "reset"); pg.wait_for_timeout(200); c5 = card_info(pg)
            check(f"{T} ⋮ Reset position: back in the top-left corner, mode '{pg.evaluate('() => NMSKQuick.prefs().pos')}'",
                  c5 is not None and abs(c5["l"] - c0["l"]) < 1.5 and abs(c5["t"] - c0["t"]) < 1.5 and pg.evaluate("() => NMSKQuick.prefs().pos") == "tl")
            h0 = c5["h"] if c5 else 0
            menu_of(pg, "qcard"); press_item(pg, "size"); pg.wait_for_timeout(150); c6 = card_info(pg)
            check(f"{T} ⋮ Compact size makes it smaller ({h0:.0f}->{c6 and round(c6['h'])} px)", c6 is not None and c6["h"] < h0)
            menu_of(pg, "qcard"); press_item(pg, "size"); pg.wait_for_timeout(150)
            menu_of(pg, "qcard"); press_item(pg, "close"); pg.wait_for_timeout(150)
            check(f"{T} ⋮ Close closes the card", card_info(pg) is None)
        # ---- 8. the ⋮ menu on every box that has a grip, and its common items
        scan(pg, r".", None, grid=10)
        pg.evaluate("() => NMSKMove.refresh()"); pg.wait_for_timeout(700)
        def present():
            return pg.evaluate("() => NMSKMove.state().boxes.filter(b => b.present && b.grip).map(b => ({key: b.key, dots: b.dots}))")
        boxes = present()
        # the panels are opened after the always-there boxes are done, so a panel's bottom sheet never decides a dock test
        tested = []
        for opener in (None, "Pose", "Measure"):
            if opener:
                pg.evaluate("(g) => { const b = [...document.querySelectorAll('#q301-groups .qg-g')].find(x => x.textContent.trim() === g); if (b) b.click(); }", opener)
                pg.wait_for_timeout(1500); pg.evaluate("() => NMSKMove.refresh()"); pg.wait_for_timeout(700)
                boxes = [b for b in present() if b["key"] not in tested]
                check(f"{T} {opener} open: its box has a grip and a ⋮ ({[x['key'] for x in boxes]})", boxes and all(x["dots"] for x in boxes))
            else:
                check(f"{T} every box with a grip has a ⋮ ({[x['key'] for x in boxes]})", boxes and all(x["dots"] for x in boxes))
            for bx_ in boxes:
                tested.append(bx_["key"])
                box_menu_tests(pg, T, bx_["key"], w, h)
        # keyboard: Enter on the ⋮ opens, arrows move, Escape closes and returns focus; outside click closes
        kb = pg.evaluate("() => { const d = document.querySelector('.nm-dots'); if (!d) return null; d.focus(); return d.id; }")
        if kb:
            pg.keyboard.press("Enter"); pg.wait_for_timeout(120)
            f0 = pg.evaluate("() => !!document.getElementById('nm-menu') && document.activeElement.classList.contains('nm-mi')")
            pg.keyboard.press("ArrowDown"); f1 = pg.evaluate("() => document.activeElement.getAttribute('data-k')")
            pg.keyboard.press("Escape"); pg.wait_for_timeout(100)
            f2 = pg.evaluate("() => !document.getElementById('nm-menu') && document.activeElement && document.activeElement.classList.contains('nm-dots')")
            check(f"{T} ⋮ keyboard: Enter opens with focus on the first item, ArrowDown -> '{f1}', Escape closes and returns focus", f0 and f1 == "dock-tr" and f2)
            pg.evaluate("(i) => document.getElementById(i).click()", kb); pg.wait_for_timeout(100)
            pg.mouse.click(w // 2, h - 4 if desk else h // 2); pg.wait_for_timeout(150)
            check(f"{T} ⋮ menu closes on an outside click", pg.evaluate("() => !document.getElementById('nm-menu')"))
        for g in ("Pose", "Measure"):
            pg.evaluate("(g) => { const b = [...document.querySelectorAll('#q301-groups .qg-g')].find(x => x.textContent.trim() === g); if (b) b.click(); }", g); pg.wait_for_timeout(500)
        # ---- 9. tools keep priority: with Mark mode on, a click marks and the card does not open
        clear_card(pg)
        r = scan(pg, r".", None, grid=10); clear_card(pg)
        if r:
            pg.evaluate("() => { const b = document.getElementById('t-mark'); if (b) b.click(); }"); pg.wait_for_timeout(200)
            nb = len(state(pg)["marks"])
            pg.mouse.click(r[0], r[1]); pg.wait_for_timeout(350)
            check(f"{T} Mark mode consumes the click: no card, marks {nb}->{len(state(pg)['marks'])}", card_info(pg) is None)
            pg.evaluate("() => { const b = document.getElementById('t-mark'); if (b) b.click(); }")
        check(f"{T} no page errors so far", not [e for e in ERRS if e.startswith("page error")])
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
            for attempt in range(3):
                n0 = len(ERRS)
                try:
                    run_size(pl, d, w, h, src.name)
                    break
                except Exception as e:                     # a browser closed from outside (shared machine): run this size again
                    if "closed" not in str(e).lower() or attempt == 2:
                        raise
                    del ERRS[n0:]
                    print(f"     (browser closed from outside during {w}x{h}: running this size again)")
    shutil.rmtree(d, ignore_errors=True)
    print("Q321_QUICKCARD_FAIL" if ERRS else "Q321_QUICKCARD_OK")
    for e in ERRS:
        print("   ", e)
    return 1 if ERRS else 0


if __name__ == "__main__":
    raise SystemExit(main())
