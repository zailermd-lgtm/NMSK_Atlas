#!/usr/bin/env python3
"""Q344-B: UI defects of the private clinical tools (needle panel, scan panel, injection / scan / compare mode cards).

Checked in headless Chromium (software rendering) against a built page that carries the current private add-ons.  In each of
needle panel (all sections opened), scan panel, mode inj (target picker open, a target picked, entries suggested), mode us,
mode cmp (and mode inn, reported only -- its UI is not owned by the clinical files) the visible text is audited:

  * no raw id (snake_case structure id, "Q123" round id, file name, viewer key) in visible text, titles or placeholders;
  * contrast >= 4.5:1 on every text, button and field (background sampled from the rendered pixels; disabled controls exempt);
  * no text smaller than 10 px;
  * number + unit strings read in the right visual order ("10 MHz", "+0 dB": sign, digits, then Latin unit);
  * the shared drag grip / menu dots cover no title or text of the panel they belong to;
  * the injection target picker is opaque; the "not available" note of the mode wall is not shown on a page that opens every mode;
  * phone (width <= 500): the needle panel in its compact state leaves >= 50 % of the model visible, can be expanded, and
    its expanded height is capped; the scan / compare modes keep a usable model area;
  * no page errors.

    python3 scripts/anatomy/q344/verify_clinical_ui_q344.py <page dir> [--size 1400x900] [--shots DIR]
"""
from __future__ import annotations

import argparse
import io
import re
import socket
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

from playwright.sync_api import sync_playwright
from PIL import Image

ARGS = ["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]

# ------------------------------------------------------------------------------------------------ in-page audit
AUDIT = r"""(roots) => {
  const out = {items: [], texts: [], units: [], grips: [], covered: []};
  const vis = el => { const cs = getComputedStyle(el); if (cs.display === 'none' || cs.visibility === 'hidden') return false;
    const r = el.getBoundingClientRect(); return r.width > 1 && r.height > 1; };
  const opac = el => { let o = 1; for (let e = el; e && e.nodeType === 1; e = e.parentElement) o *= +getComputedStyle(e).opacity; return o; };
  const inCtl = el => !!el.closest('.nm-grip,.nm-dots,.nm-menu,[class*="nm-g"]');
  const rootEls = roots.flatMap(s => [].slice.call(document.querySelectorAll(s))).filter(vis);
  const seen = new Set();
  const textRect = el => {
    const rg = document.createRange(); const ns = [].slice.call(el.childNodes).filter(n => n.nodeType === 3 && n.textContent.trim());
    if (!ns.length) return null; rg.setStartBefore(ns[0]); rg.setEndAfter(ns[ns.length - 1]);
    const rs = [].slice.call(rg.getClientRects()).filter(r => r.width > 0.5 && r.height > 0.5);
    if (!rs.length) return null;
    let l = 1e9, t = 1e9, r = -1e9, b = -1e9; rs.forEach(q => { l = Math.min(l, q.left); t = Math.min(t, q.top); r = Math.max(r, q.right); b = Math.max(b, q.bottom); });
    return {l, t, r, b};
  };
  let allText = '', attrText = [];
  rootEls.forEach(root => {
    [root].concat([].slice.call(root.querySelectorAll('*'))).forEach(el => {
      if (seen.has(el) || !vis(el) || inCtl(el)) return; seen.add(el);
      if (['SCRIPT', 'STYLE', 'CANVAS', 'SVG', 'PATH'].includes(el.tagName.toUpperCase())) return;
      ['title', 'aria-label', 'placeholder'].forEach(a => { const v = el.getAttribute(a); if (v) attrText.push(v); });
      const direct = [].slice.call(el.childNodes).filter(n => n.nodeType === 3).map(n => n.textContent).join('').trim();
      const ctl = el.matches('input:not([type=range]):not([type=checkbox]):not([type=file]),select,textarea');
      if (!direct && !ctl) return;
      const cs = getComputedStyle(el);
      const trc = textRect(el);
      let rc = (ctl || el.tagName === 'BUTTON') ? (() => { const r = el.getBoundingClientRect(); return {l: r.left, t: r.top, r: r.right, b: r.bottom}; })() : trc;
      if (!rc) return;
      const cx = Math.min(innerWidth - 1, Math.max(0, (rc.l + rc.r) / 2)), cy = Math.min(innerHeight - 1, Math.max(0, (rc.t + rc.b) / 2));
      const top = document.elementFromPoint(cx, cy);
      const onTop = !!top && (top === el || el.contains(top) || top.contains(el));
      const offscreen = rc.r < 0 || rc.b < 0 || rc.l > innerWidth || rc.t > innerHeight;
      // clipped by an overflow ancestor?
      let clipped = false;
      for (let a = el.parentElement; a && a !== document.body; a = a.parentElement) {
        const ac = getComputedStyle(a); if (/(hidden|auto|scroll|clip)/.test(ac.overflowX + ac.overflowY)) { const ar = a.getBoundingClientRect();
          if (rc.b < ar.top + 1 || rc.t > ar.bottom - 1 || rc.r < ar.left + 1 || rc.l > ar.right - 1) { clipped = true; break; } }
      }
      const txt = (ctl ? (el.value || el.getAttribute('placeholder') || '') : direct);
      const it = {tag: el.tagName.toLowerCase(), cls: String(el.className && el.className.baseVal != null ? el.className.baseVal : el.className).slice(0, 40), id: el.id || '',
                  text: txt.slice(0, 60), trc: trc || rc, fs: parseFloat(cs.fontSize), color: cs.color, op: opac(el), rc, onTop, offscreen, clipped,
                  disabled: !!(el.disabled || el.getAttribute('aria-disabled') === 'true' || el.closest('[disabled]')),
                  ctl, tcov: top ? ((top.id ? '#' + top.id : '') + '.' + String(top.className || '').slice(0, 30)) : null};
      if (offscreen || clipped) return;
      if (!onTop) { out.covered.push({text: txt.slice(0, 40), by: it.tcov, tag: it.tag}); }
      out.items.push(it);
    });
    allText += '\n' + (root.innerText || '');
  });
  // controls half off the screen (a button pushed past an edge shows as a sliver)
  out.edge = [];
  rootEls.forEach(root => [].slice.call(root.querySelectorAll('button,input,select')).forEach(e => {
    if (!vis(e)) return; const r = e.getBoundingClientRect();
    if (!(r.left < -1 || r.right > innerWidth + 1)) return;
    for (let a = e.parentElement; a; a = a.parentElement) { const x = getComputedStyle(a).overflowX; if (x === 'auto' || x === 'scroll') return; }
    out.edge.push((e.textContent || e.getAttribute('aria-label') || e.tagName).trim().slice(0, 24) + ' @' + Math.round(r.left) + '..' + Math.round(r.right));
  }));
  out.texts = allText.split('\n').map(s => s.trim()).filter(Boolean);
  out.attrs = attrText;
  // number + unit visual order
  rootEls.forEach(root => {
    const tw = document.createTreeWalker(root, NodeFilter.SHOW_TEXT); const nodes = []; let s = '', n;
    while ((n = tw.nextNode())) { const p = n.parentElement; if (!p || !vis(p) || p.closest('style,script')) continue; nodes.push({n, o: s.length}); s += n.textContent; }
    const rect = (a, b) => { // the client rect of logical offsets a..b
      const parts = []; nodes.forEach(x => { const e = x.o + x.n.textContent.length; if (e <= a || x.o >= b) return;
        const rg = document.createRange(); rg.setStart(x.n, Math.max(0, a - x.o)); rg.setEnd(x.n, Math.min(x.n.textContent.length, b - x.o));
        parts.push.apply(parts, [].slice.call(rg.getClientRects()).filter(r => r.width > 0.3)); });
      if (!parts.length) return null; return {l: Math.min.apply(0, parts.map(r => r.left)), r: Math.max.apply(0, parts.map(r => r.right)), t: Math.min.apply(0, parts.map(r => r.top))};
    };
    const re = /([+−\-]?)(\d+(?:\.\d+)?)[\s ⁦⁩‎‏]*(MHz|kHz|dB|HU)\b|\b(MHz|dB)[\s ]*([+−\-]?)(\d+(?:\.\d+)?)/g; let m;
    while ((m = re.exec(s))) {
      const reversedLogical = !!m[4];
      const full = m[0];
      let numA, numB, unitA, unitB, signA = -1;
      if (!reversedLogical) { numA = m.index + m[1].length; numB = numA + m[2].length; unitB = m.index + full.length; unitA = unitB - m[3].length; if (m[1]) signA = m.index; }
      else { unitA = m.index; unitB = unitA + m[4].length; numA = m.index + full.length - m[6].length; numB = m.index + full.length; if (m[5]) signA = numA - 1; }
      const rn = rect(numA, numB), ru = rect(unitA, unitB), rs = signA >= 0 ? rect(signA, signA + 1) : null;
      if (!rn || !ru) continue;
      const numFirst = rn.r <= ru.l + 1;
      const signFirst = !rs || rs.l <= rn.l + 1;
      out.units.push({s: full.replace(/[⁦⁩‎‏]/g, ''), ok: numFirst && signFirst, numFirst, signFirst});
    }
  });
  // the shared grips / dots against the text of their own panel
  [].slice.call(document.querySelectorAll('.nm-grip,.nm-dots')).filter(vis).forEach(g => {
    const gr = g.getBoundingClientRect(); const host = g.parentElement;
    if (!host || !rootEls.some(r => r === host || r.contains(host) || host.contains(r))) return;
    out.grips.push({id: g.id || g.className, r: [gr.left, gr.top, gr.right, gr.bottom]});
  });
  return out;
}"""

RAW_ID = [
    (re.compile(r"\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b"), "snake_case id"),
    (re.compile(r"\bQ\d{3}\b"), "round id"),
    (re.compile(r"\b[\w-]+\.(?:json|js|py|csv|html|txt|glb|png)\b", re.I), "file name"),
    (re.compile(r"\b(?:viewer_[a-z_]+|zan_atlas|base_female|zan_m|zan_f|base_m|base_f)\b"), "viewer key"),
    (re.compile(r"\bPrivate\b"), "'Private' marker"),
]


WALL = """() => { const w = document.getElementById('mode-switch'); if (!w || w.hidden) return null;
  const tiles = [].slice.call(w.querySelectorAll('.mw-tile')); const shown = [].slice.call(w.querySelectorAll('.mw-na')).filter(e => { const r = e.getBoundingClientRect(); return r.width > 1 && getComputedStyle(e).display !== 'none'; });
  return {tiles: tiles.map(t => [t.dataset.mode, !!t.disabled]), shownNa: shown.map(e => e.textContent.trim())}; }"""


def serve(d):
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close()
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(p), "--bind", "127.0.0.1", "-d", str(d)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    return srv, p


def parse_color(s: str):
    """rgb()/rgba()/color(srgb r g b / a) -> (r, g, b, a) 0..255"""
    m = re.match(r"rgba?\(([^)]*)\)", s)
    if m:
        v = [float(x) for x in re.split(r"[,\s/]+", m.group(1).strip()) if x]
        return (v[0], v[1], v[2], v[3] if len(v) > 3 else 1.0)
    m = re.match(r"color\(srgb ([^)]*)\)", s)
    if m:
        v = [float(x) for x in re.split(r"[\s/]+", m.group(1).strip()) if x]
        return (v[0] * 255, v[1] * 255, v[2] * 255, v[3] if len(v) > 3 else 1.0)
    return (0, 0, 0, 1.0)


def lum(c):
    def f(x):
        x /= 255.0
        return x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2])


def contrast(a, b):
    la, lb = lum(a), lum(b)
    if la < lb:
        la, lb = lb, la
    return (la + 0.05) / (lb + 0.05)


def bg_inside(img: Image.Image, rc):
    """background of a control (button / field): the most common colour inside its box (a focus ring or border is a thin outline, the text is sparse)"""
    W, H = img.size
    l, t, r, b = max(0, int(rc["l"]) + 1), max(0, int(rc["t"]) + 1), min(W - 1, int(rc["r"]) - 1), min(H - 1, int(rc["b"]) - 1)
    if r <= l or b <= t:
        return None
    px = img.load()
    cnt = Counter()
    for y in range(t, b + 1, 2):
        for x in range(l, r + 1, 2):
            cnt[px[x, y]] += 1
    return cnt.most_common(1)[0][0] if cnt else None


def bg_of(img: Image.Image, rc, pad=3):
    """background colour of a text box: the most common colour on a ring just outside (and, if that fails, inside) its box"""
    W, H = img.size
    l, t, r, b = max(0, int(rc["l"]) - pad), max(0, int(rc["t"]) - pad), min(W - 1, int(rc["r"]) + pad), min(H - 1, int(rc["b"]) + pad)
    if r <= l or b <= t:
        return None
    px = img.load()
    cnt = Counter()
    for x in range(l, r + 1, 2):
        cnt[px[x, t]] += 1; cnt[px[x, b]] += 1
    for y in range(t, b + 1, 2):
        cnt[px[l, y]] += 1; cnt[px[r, y]] += 1
    return cnt.most_common(1)[0][0] if cnt else None


def audit_state(pg, label, roots, check, notes, strict=True, ids_strict=True):
    """returns the audit dict; records OK/FAIL"""
    pg.wait_for_timeout(250)
    a = pg.evaluate(AUDIT, roots)
    img = Image.open(io.BytesIO(pg.screenshot())).convert("RGB")
    dpr = img.size[0] / pg.evaluate("innerWidth")
    # raw ids
    bad = []
    for t in a["texts"] + a["attrs"]:
        for rx, nm in RAW_ID:
            m = rx.search(t)
            if m:
                bad.append(f"{nm}: {m.group(0)}")
    # text smaller than 10 px
    small = sorted({f"{i['text']!r} {i['fs']:.1f}px" for i in a["items"] if i["fs"] < 10 and i["text"]})
    # contrast
    lows = []
    for i in a["items"]:
        if i["disabled"] or not i["onTop"] or not i["text"]:
            continue
        rc = {k: v * dpr for k, v in i["rc"].items()}
        bg = bg_inside(img, rc) if (i["ctl"] or i["tag"] in ("button", "input", "select")) else bg_of(img, rc)
        if bg is None:
            continue
        fg = parse_color(i["color"])
        al = fg[3] * i["op"]
        fgc = tuple(fg[k] * al + bg[k] * (1 - al) for k in range(3))
        c = contrast(fgc, bg)
        if c < 4.5:
            lows.append(f"{i['tag']}.{i['cls'].split(' ')[0]} {i['text'][:28]!r} {c:.2f} fg{tuple(round(x) for x in fgc)} bg{bg}")
    # units
    badu = [u["s"] for u in a["units"] if not u["ok"]]
    # grips
    gcov = []
    for g in a["grips"]:
        gl, gt, gr, gb = g["r"]
        for i in a["items"]:
            if "nm-" in i["cls"]:
                continue
            rc = i["trc"]
            if min(gr, rc["r"]) - max(gl, rc["l"]) > 2 and min(gb, rc["b"]) - max(gt, rc["t"]) > 2:
                gcov.append(f"{g['id']} {[round(x) for x in g['r']]} over {i['text'][:24]!r} {[round(rc[k]) for k in ('l','t','r','b')]}")
    edge = a["edge"]
    ok_all = not (bad or small or lows or badu or gcov or edge)
    pre = "  OK   " if ok_all else ("  FAIL " if strict else "  note ")
    print(f"{pre}{label}: {len(a['items'])} texts, {len(a['units'])} number+unit, {len(a['grips'])} grips")
    for nm, lst in (("raw id", sorted(set(bad))), ("< 10 px", small), ("contrast < 4.5", sorted(set(lows))), ("unit order", badu), ("grip covers text", sorted(set(gcov))), ("control past the screen edge", edge)):
        if lst:
            print(f"         {nm}: {lst[:8]}{' ...' if len(lst) > 8 else ''}")
    if not ok_all and strict:
        check(f"{label}: readable (see above)", False)
    elif ok_all:
        check(f"{label}: readable", True)
    return a


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("build_dir")
    ap.add_argument("--size", default="1400x900")
    ap.add_argument("--shots", default=None)
    a = ap.parse_args()
    d = Path(a.build_dir).resolve()
    W, H = (int(x) for x in a.size.split("x"))
    phone = W <= 500
    srv, port = serve(d)
    errs: list[str] = []
    page_errors: list[str] = []
    shots = Path(a.shots) if a.shots else None
    if shots:
        shots.mkdir(parents=True, exist_ok=True)

    def check(label, cond):
        ok = bool(cond)
        print(("  OK   " if ok else "  FAIL ") + label)
        if not ok:
            errs.append(label)

    def shot(pg, name):
        if shots:
            pg.screenshot(path=str(shots / f"q344_{d.name}_{W}x{H}_{name}.png"))

    try:
        with sync_playwright() as pl:
            b = pl.chromium.launch(args=ARGS, executable_path="/opt/pw-browsers/chromium")
            ctx = b.new_context(viewport={"width": W, "height": H}, has_touch=phone, is_mobile=phone, device_scale_factor=1,
                                color_scheme="dark" if phone else "light")
            pg = ctx.new_page()
            pg.on("pageerror", lambda e: page_errors.append(str(e)))
            pg.route("**/*", lambda rq: rq.abort() if "fonts.g" in rq.request.url else rq.continue_())
            print(f"=== {d.name} @ {W}x{H} ===")
            pg.goto(f"http://127.0.0.1:{port}/index.html", wait_until="load", timeout=180000)
            pg.wait_for_function("window.NMSKUltrasound && window.NMSKClinicalTool && window.NMSKModes && window.__poseApi && window.__poseApi.ready()", timeout=180000)
            pg.wait_for_timeout(2000)

            # ---- the mode wall: every tile opens on this page, so no "not available" note may be shown
            wall = pg.evaluate(WALL)

            if wall:
                for _ in range(40):          # the tiles of the add-on modes are enabled as the add-ons attach: wait for them
                    if not any(x[1] for x in wall["tiles"]):
                        break
                    pg.wait_for_timeout(500)
                    wall = pg.evaluate(WALL)
                print("     wall tiles:", wall["tiles"])
                check("mode wall: no tile disabled and no 'not available' note shown on a page that opens every mode",
                      not any(x[1] for x in wall["tiles"]) and not wall["shownNa"])
                pg.evaluate("() => { const c = document.getElementById('mw-close'); if (c) c.click(); }")
            else:
                print("     (no mode wall on this load)")
            pg.wait_for_timeout(500)
            pg.evaluate("() => { if (window.NMSKModes.current && window.NMSKModes.current()) window.NMSKModes.exit(); }")
            pg.wait_for_timeout(800)

            # ---- 1. the needle panel (anatomy screen)
            pg.evaluate("() => { const b = document.getElementById('t-needle'); if (b) b.click(); }")
            pg.wait_for_timeout(900)
            np_ = pg.evaluate("() => { const e = document.getElementById('needle-panel'); if (!e || e.hidden) return null; const r = e.getBoundingClientRect(); return {r: [r.left, r.top, r.right, r.bottom], coll: e.classList.contains('ncl-collapsed'), mv: e.getAttribute('data-nmsk-move')}; }")
            check("needle panel opens", bool(np_))
            if np_:
                check("needle panel opts in to the shared drag grip (data-nmsk-move)", bool(np_["mv"]))
                if phone:
                    box = pg.evaluate("() => { const b = window.NMSKQuick && window.NMSKQuick.box && window.NMSKQuick.box(); return b ? JSON.parse(JSON.stringify(b)) : null; }")
                    r = np_["r"]
                    if box:
                        bl, bt = box.get("l", box.get("left", box.get("x"))), box.get("t", box.get("top", box.get("y")))
                        br = box.get("r", box.get("right", (bl + box["w"]) if "w" in box else None)); bb = box.get("b", box.get("bottom", (bt + box["h"]) if "h" in box else None))
                        area = max(0, br - bl) * max(0, bb - bt)
                        ov = max(0, min(br, r[2]) - max(bl, r[0])) * max(0, min(bb, r[3]) - max(bt, r[1]))
                        vis = 1 - ov / area if area else 1
                    else:
                        vis = 1 - max(0, r[3] - r[1]) * max(0, r[2] - r[0]) / (W * H)
                    print(f"     needle panel (phone, first open): collapsed={np_['coll']} rect={[round(x) for x in r]} model visible {vis*100:.0f} %")
                    check("phone: needle panel in its compact state leaves >= 50 % of the model visible", vis >= 0.5)
                    st = pg.evaluate("() => { const t = document.querySelector('#needle-panel #needle-status'); return t ? t.getBoundingClientRect().height : 0; }")
                    check("phone: the compact needle panel still shows the current step line", st > 0 and bool(pg.evaluate("() => (document.getElementById('needle-status').textContent || '').trim().length > 0")))
                    pg.click("#ncl-min", timeout=5000)           # a real tap expands it
                    pg.wait_for_timeout(400)
                    check("phone: one tap expands the compact needle panel", not pg.evaluate("() => document.getElementById('needle-panel').classList.contains('ncl-collapsed')"))
                    r2 = pg.evaluate("() => { const r = document.getElementById('needle-panel').getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; }")
                    check(f"phone: expanded needle panel height capped at 50 % of the screen ({(r2[3]-r2[1]):.0f} of {H} px)", (r2[3] - r2[1]) <= 0.5 * H + 1)
                pg.evaluate("() => { const e = document.getElementById('needle-panel'); [].forEach.call(e.querySelectorAll('details'), d => d.open = true); e.classList.remove('ncl-collapsed'); const m = document.getElementById('ncl-min'); if (m) m.setAttribute('aria-expanded', 'true'); }")
                pg.wait_for_timeout(300)
                shot(pg, "needle")
                audit_state(pg, "needle panel (all sections open)", ["#needle-panel"], check, None)
                pg.evaluate("() => { const e = document.getElementById('needle-panel'); [].forEach.call(e.querySelectorAll('details'), d => d.open = false); }")
                pg.evaluate("() => { const b = document.getElementById('ncl-close'); if (b) b.click(); }")
                pg.wait_for_timeout(400)

            # ---- 2. the scan panel (anatomy screen)
            pg.evaluate("() => window.NMSKUltrasound.open()")
            pg.wait_for_timeout(1500)
            sp = pg.evaluate("() => { const e = document.getElementById('us-root'); return e ? {mv: e.getAttribute('data-nmsk-move'), vis: e.getBoundingClientRect().width > 10} : null; }")
            check("scan panel opts in to the shared drag grip (data-nmsk-move)", bool(sp and sp["mv"]))
            shot(pg, "scanpanel")
            audit_state(pg, "scan panel", ["#us-root"], check, None)
            pg.evaluate("() => window.NMSKUltrasound.close()")
            pg.wait_for_timeout(500)

            # ---- 3. injection mode
            pg.evaluate("() => window.NMSKModes.enter('inj')")
            pg.wait_for_timeout(1800)
            roots = ["#mode-shell"]
            audit_state(pg, "mode inj (cards)", roots, check, None)
            pg.evaluate("() => { const b = document.querySelector('.mc-right .mc-desk, .mb-chip .mb-mini, .mb-text'); if (b) b.click(); }")
            pg.wait_for_timeout(500)
            pk = pg.evaluate("""() => { const p = document.querySelector('.mc-pick'); if (!p) return null; const cs = getComputedStyle(p); const c = cs.backgroundColor;
              const rows = [].slice.call(p.querySelectorAll('.mc-res button')).map(b => b.textContent.trim()); return {bg: c, rows: rows.slice(0, 6), n: rows.length}; }""")
            check("inj: target picker opens", bool(pk))
            if pk:
                m = parse_color(pk["bg"])
                check(f"inj: target picker background opaque ({pk['bg']})", m[3] >= 0.999)
                print("     picker rows:", pk["rows"][:4])
                shot(pg, "inj_picker")
                audit_state(pg, "mode inj (target picker)", roots, check, None)
                pg.evaluate("() => { const i = document.querySelector('.mc-pick .mc-search'); if (i) { i.value = 'abductor hallucis'; i.dispatchEvent(new Event('input')); } }")
                pg.wait_for_timeout(300)
                audit_state(pg, "mode inj (target picker, searched)", roots, check, None)
                pg.evaluate("() => { const b = document.querySelector('.mc-pick .mc-res button'); if (b) b.click(); }")
                pg.wait_for_timeout(1000)
            pg.evaluate("() => { const b = document.querySelector('.mc-primary'); if (b && !b.disabled) b.click(); }")
            pg.wait_for_timeout(1200)
            shot(pg, "inj_cards")
            audit_state(pg, "mode inj (target picked, entries suggested)", roots, check, None)
            pg.evaluate("() => window.NMSKModes.exit()")
            pg.wait_for_timeout(2500)

            # ---- 4. scan mode
            pg.evaluate("() => window.NMSKModes.enter('us')")
            pg.wait_for_timeout(2200)
            shot(pg, "us")
            au = audit_state(pg, "mode us", roots + ["#us-root"], check, None)
            units = [u["s"] for u in au["units"]]
            print("     number+unit strings:", units[:8])
            check("us: a frequency reads 'N MHz' (number before unit)", any("MHz" in u["s"] and u["ok"] for u in au["units"]))
            if phone:
                sw = pg.evaluate("""async () => { const b = document.querySelector('.mm-swap-btn'); if (!b || getComputedStyle(b).display === 'none') return null;
                  const area = () => { const c = document.querySelector('#mode-shell ~ canvas, body > canvas, canvas'); const r = (window.NMSKQuick && window.NMSKQuick.box && window.NMSKQuick.box()) || null; return r; };
                  const cv = [].slice.call(document.querySelectorAll('canvas')).filter(c => c.getBoundingClientRect().width > 50).map(c => { const r = c.getBoundingClientRect(); return {w: r.width, h: r.height, cls: c.parentElement.id || ''}; });
                  b.click(); await new Promise(r => setTimeout(r, 900));
                  const cv2 = [].slice.call(document.querySelectorAll('canvas')).filter(c => c.getBoundingClientRect().width > 50).map(c => { const r = c.getBoundingClientRect(); return {w: r.width, h: r.height}; });
                  const label = b.textContent; b.click(); await new Promise(r => setTimeout(r, 400));
                  return {before: cv, after: cv2, label}; }""")
                if sw:
                    big = max((c["w"] * c["h"] for c in sw["after"]), default=0)
                    print(f"     scan mode on a phone: model {max((c['w'] for c in sw['before'] if c['w'] < 200), default=0):.0f} px thumbnail -> {big ** 0.5:.0f} px square after the switch ({sw['label']!r})")
                    small = max((c["w"] * c["h"] for c in sw["before"] if c["w"] < 200), default=0)
                    check(f"phone scan mode: one-tap switch gives the 3-D model >= 40 % of the screen ({big / (W * H) * 100:.0f} %)", big / (W * H) >= 0.4)
                else:
                    check("phone scan mode: a one-tap model / scan switch exists", False)
            pg.evaluate("() => window.NMSKModes.exit()")
            pg.wait_for_timeout(2500)

            # ---- 5. compare mode
            pg.evaluate("() => window.NMSKModes.enter('cmp')")
            pg.wait_for_timeout(2200)
            shot(pg, "cmp")
            audit_state(pg, "mode cmp", roots + ["#ref-root", "#us-root"], check, None)
            if phone:
                c3 = pg.evaluate("""async () => { const b = document.querySelector('.mm-3dm'); if (!b || getComputedStyle(b).display === 'none') return null;
                  b.click(); await new Promise(r => setTimeout(r, 900));
                  const cv = [].slice.call(document.querySelectorAll('canvas')).filter(c => c.getBoundingClientRect().width > 50 && getComputedStyle(c).visibility !== 'hidden').map(c => { const r = c.getBoundingClientRect(); return {w: r.width, h: r.height}; });
                  b.click(); await new Promise(r => setTimeout(r, 300)); return cv; }""")
                big = max((c["w"] * c["h"] for c in (c3 or [])), default=0)
                print(f"     compare mode on a phone: 3-D view {big ** 0.5:.0f} px square after the switch")
                check(f"phone compare mode: one-tap 3-D switch gives the model >= 25 % of the screen ({big / (W * H) * 100:.0f} %)", big / (W * H) >= 0.25)
            pg.evaluate("() => window.NMSKModes.exit()")
            pg.wait_for_timeout(2500)

            # ---- 6. innervation mode (not owned by the clinical files: reported only)
            try:
                pg.evaluate("() => window.NMSKModes.enter('inn')")
                pg.wait_for_timeout(2000)
                audit_state(pg, "mode inn (reported only, viewer-owned)", roots, check, None, strict=False)
                pg.evaluate("() => window.NMSKModes.exit()")
            except Exception as e:  # noqa: BLE001
                print("  note mode inn:", str(e)[:100])
            b.close()
    finally:
        srv.terminate()

    check("no page errors" + (f" ({page_errors[:2]})" if page_errors else ""), not page_errors)
    ok = not errs
    print("Q344_CLINICAL_UI_OK" if ok else "Q344_CLINICAL_UI_FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
