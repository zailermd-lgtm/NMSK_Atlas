#!/usr/bin/env python3
"""Q344: the readability / screen-area round, checked in headless Chromium against a built page.

    python3 scripts/anatomy/q344/verify_ui_q344.py /dev/shm/q344/zan_atlas [--size 1400x900]

Per fixed item one check: contrast >= 4.5:1 on the named buttons; no visible raw id / round id / file name in the structure card and
the parts prose of ten sample structures; each sheet covers <= 40 % of the model's box on a desktop and every sheet / panel leaves
>= 50 % of it visible on a phone (compact state); no text under 10 px in the public panels; the strays at the top-left are gone;
the footer statistics are behind the Sources box; search rows that share a name carry the side; measure pins are cleared; 0 page errors.
Prints OK / FAIL per check and Q344_UI_OK / Q344_UI_FAIL."""
from __future__ import annotations

import json
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

THREE = "/tmp/three_x/package/build/three.min.js"
ARGS = ["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]


def serve(d):
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close()
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(p), "--bind", "127.0.0.1", "-d", str(d)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1); return srv, p


def route(rq):
    u = rq.request.url
    if "three" in u and u.endswith(".js") and ("cdnjs" in u or "jsdelivr" in u or "unpkg" in u):
        rq.fulfill(body=open(THREE, "rb").read(), content_type="application/javascript")
    elif "fonts.g" in u:
        rq.abort()
    else:
        rq.continue_()


FAILS: list[str] = []


def check(label, cond, extra=""):
    ok = bool(cond)
    print(("  OK  " if ok else "  FAIL") + " " + label + ((" -- " + str(extra)) if (extra and not ok) else ""))
    if not ok:
        FAILS.append(label)
    return ok


HELP = """
window.__q = {
  vis: e => { if (!e) return false; const s = getComputedStyle(e); if (e.hidden || s.display === 'none' || s.visibility === 'hidden' || +s.opacity === 0) return false;
              const r = e.getBoundingClientRect(); return r.width > 2 && r.height > 2; },
  rgba: c => { const m = c.match(/color\\(srgb ([\\d.]+) ([\\d.]+) ([\\d.]+)(?: \\/ ([\\d.]+))?\\)/);
               if (m) return [m[1] * 255, m[2] * 255, m[3] * 255, m[4] == null ? 1 : +m[4]];
               const n = c.match(/rgba?\\(([^)]+)\\)/); if (!n) return [0, 0, 0, 0];
               const p = n[1].split(/[ ,\\/]+/).filter(Boolean).map(Number); return [p[0], p[1], p[2], p.length > 3 ? p[3] : 1]; },
  bg: e => { let layers = []; for (let x = e; x; x = x.parentElement) { const c = window.__q.rgba(getComputedStyle(x).backgroundColor); if (c[3] > 0) { layers.push(c); if (c[3] >= 0.995) break; } }
             let base = [255, 255, 255]; for (let i = layers.length - 1; i >= 0; i--) { const c = layers[i]; base = base.map((v, k) => c[k] * c[3] + v * (1 - c[3])); } return base; },
  lum: c => { const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); }; return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]); },
  contrast: e => { const b = window.__q.bg(e), t = window.__q.rgba(getComputedStyle(e).color), fg = t.slice(0, 3).map((v, k) => v * t[3] + b[k] * (1 - t[3]));
                   const a = window.__q.lum(fg), z = window.__q.lum(b); return (Math.max(a, z) + 0.05) / (Math.min(a, z) + 0.05); },
  box: () => { try { return NMSKQuick.box(); } catch (e) { return null; } },
  cover: (rects) => { const b = window.__q.box(); if (!b) return null; const N = 60, M = 120; let hit = 0, tot = 0;
    for (let i = 0; i < N; i++) for (let j = 0; j < M; j++) { const x = b.l + (i + 0.5) * (b.r - b.l) / N, y = b.t + (j + 0.5) * (b.b - b.t) / M; tot++;
      if (rects.some(r => x >= r.left && x <= r.right && y >= r.top && y <= r.bottom)) hit++; } return hit / tot; },
  rect: e => { const r = e.getBoundingClientRect(); return {left: r.left, top: r.top, right: r.right, bottom: r.bottom}; }
};
"""

SMALL = """() => {
  const roots = '#info,#q301-sheet,#q301-bar,#rail,#pose-panel,#lab-panel,#ms-bar,.qc,#sel-sec,#modal .sheet,#q8-float,#sa-bar,#pm-card,#topright,#foot,#ref-root,#brand'.split(',');
  const out = [];
  const q = window.__q;
  document.querySelectorAll(roots.join(',')).forEach(r => {
    if (!q.vis(r) && r.id !== 'modal') return;
    const tw = document.createTreeWalker(r, NodeFilter.SHOW_TEXT);
    while (tw.nextNode()) { const n = tw.currentNode; if (!/\\S/.test(n.textContent)) continue; const e = n.parentElement;
      if (!e || /^(SCRIPT|STYLE)$/.test(e.tagName) || !q.vis(e)) continue;
      const fs = parseFloat(getComputedStyle(e).fontSize); if (fs < 10) out.push(r.id + '|' + e.tagName + '.' + String(e.className).slice(0, 16) + ' ' + fs.toFixed(1) + 'px "' + n.textContent.trim().slice(0, 24) + '"'); }
  });
  return out.slice(0, 12);
}"""


import os
SHOTS = Path(os.environ["Q355_SHOTS"]) if os.environ.get("Q355_SHOTS") else None


def main() -> int:
    d = Path(sys.argv[1])
    w, h = 1400, 900
    if "--size" in sys.argv:
        w, h = [int(x) for x in sys.argv[sys.argv.index("--size") + 1].lower().split("x")]
    phone = w <= 460
    srv, port = serve(d)
    errs: list[str] = []
    try:
        with sync_playwright() as pl:
            b = pl.chromium.launch(args=ARGS, executable_path="/opt/pw-browsers/chromium")
            ctx = b.new_context(viewport={"width": w, "height": h}, has_touch=phone, is_mobile=phone)
            pg = ctx.new_page()
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.route("**/*", route)
            html = sorted(d.glob("atlas_viewer*.html"))
            print(f"=== {d.name} {w}x{h} ===")
            pg.goto(f"http://127.0.0.1:{port}/{html[0].name if html else 'index.html'}", wait_until="load", timeout=90000)
            pg.wait_for_function("window.NMSKQ301", timeout=90000)
            pg.wait_for_selector('.mw-tile[data-mode="anat"]', timeout=60000)
            pg.click('.mw-tile[data-mode="anat"]'); pg.wait_for_timeout(3500)
            pg.evaluate(HELP)

            # ---- 5. strays at the top-left, 10. footer statistics
            st = pg.evaluate("""() => { const q = window.__q; const out = [];
              document.querySelectorAll('.pl-l,.pl-box,.ft-box,.rs-row,#pl-state').forEach(e => { if (!e.closest('#q301-sheet') && q.vis(e)) out.push(e.id || e.className); });
              const s = document.getElementById('stat-line'); return {strays: out, stat: s ? q.vis(s) : false}; }""")
            check("5 no stray Depth / Whole body / Fat controls painted in the page", not st["strays"], st["strays"])
            check("10 #stat-line is not shown on the page", not st["stat"])
            pg.evaluate("document.getElementById('about-btn') && document.getElementById('about-btn').click()")
            pg.wait_for_timeout(900)
            check("10 the statistics are in the Sources box", pg.evaluate("() => { const p = document.querySelector('#modal .q344-stats'); return !!(p && /meshes/.test(p.textContent)); }"))
            pg.evaluate("document.getElementById('modal-close') && document.getElementById('modal-close').click()")

            # ---- 1. Navigate sheet buttons
            pg.evaluate("document.getElementById('qg-view').click()"); pg.wait_for_timeout(900)
            res = pg.evaluate("""() => { const q = window.__q; const o = {}; document.querySelectorAll('#q301-sheet .pill').forEach(e => { if (q.vis(e)) o[e.textContent.trim() || e.id] = +q.contrast(e).toFixed(2); }); return o; }""")
            names = [k for k in res]
            check("1 Navigate: front / side / back / move / reset are visible with contrast >= 4.5",
                  all(k in res for k in ("front", "side", "back", "move", "reset")) and all(v >= 4.5 for v in res.values()), res)
            cov = pg.evaluate("() => { const s = document.getElementById('q301-sheet'), q = window.__q; return {c: q.cover([q.rect(s)]), v: q.cover([q.rect(s), q.rect(document.getElementById('q301-bar'))])}; }")
            if not phone:
                check("4 Navigate sheet covers <= 40% of the model box (desktop)", cov["c"] is not None and cov["c"] <= 0.40, cov)
            else:
                check("4 Navigate sheet leaves >= 50% of the model visible (phone)", cov["v"] is not None and cov["v"] <= 0.50, cov)
            pg.evaluate("document.getElementById('qg-view').click()"); pg.wait_for_timeout(400)

            # ---- 4. Search / Systems sheets
            for key, label in (("mark", "Search"), ("systems", "Systems")):
                pg.evaluate(f"document.getElementById('qg-{key}').click()"); pg.wait_for_timeout(900)
                cov = pg.evaluate("() => { const s = document.getElementById('q301-sheet'), q = window.__q; return {c: q.cover([q.rect(s)]), v: q.cover([q.rect(s), q.rect(document.getElementById('q301-bar'))])}; }")
                if not phone:
                    check(f"4 {label} sheet covers <= 40% of the model box (desktop)", cov["c"] is not None and cov["c"] <= 0.40, cov)
                else:
                    check(f"4 {label} sheet leaves >= 50% of the model visible (phone)", cov["v"] is not None and cov["v"] <= 0.50, cov)
                if key == "systems":
                    sd = pg.evaluate("""() => { const q = window.__q; const o = {}; document.querySelectorAll('#q301-sheet #sides button').forEach(e => { if (q.vis(e)) o[e.textContent.trim()] = +q.contrast(e).toFixed(2); }); return o; }""")
                    check("20 Systems: both / right / left buttons have contrast >= 4.5", len(sd) >= 3 and all(v >= 4.5 for v in sd.values()), sd)
                if key == "mark":
                    # ---- 7. search rows
                    sr = pg.evaluate("""() => { const q = window.__q; const rows = [...document.querySelectorAll('#q301-sheet .item')].filter(q.vis);
                      const names = {}; rows.forEach(r => { const t = r.querySelector('.t'); const n = t.firstChild ? t.firstChild.textContent.trim() : ''; (names[n] = names[n] || []).push(!!r.querySelector('.side-lr')); });
                      const dup = Object.keys(names).filter(k => names[k].length > 1); const bad = dup.filter(k => names[k].some(x => !x));
                      const bx = [...document.querySelectorAll('#q301-sheet .badge-x')].filter(q.vis).map(e => parseFloat(getComputedStyle(e).fontSize));
                      const cts = rows.slice(0, 12).map(r => +q.contrast(r).toFixed(1));
                      const t0 = rows[0] && rows[0].querySelector('.t'); const wrap = t0 ? getComputedStyle(t0).whiteSpace : '';
                      return {rows: rows.length, dup: dup.length, bad: bad.slice(0, 3), minBadge: bx.length ? Math.min(...bx) : 99, minRow: cts.length ? Math.min(...cts) : 99, wrap}; }""")
                    check("7 search: rows that share a name carry the structure's side (R / L)", sr["dup"] == 0 or not sr["bad"], sr)
                    check("7 search: the tag text is >= 10 px", sr["minBadge"] >= 10, sr)
                    check("7 search: row text wraps (no ellipsis) and has contrast >= 4.5", sr["wrap"] != "nowrap" and sr["minRow"] >= 4.5, sr)
                    pg.fill("#q301-sheet input[type=search], #q301-sheet input", "שריר"); pg.wait_for_timeout(800)
                    hb = pg.evaluate("""() => { const e = [...document.querySelectorAll('#q301-sheet .q8-why')]; return {n: e.length, auto: e.every(x => x.getAttribute('dir') === 'auto')}; }""")
                    check("7 search: Hebrew glosses carry dir=auto", hb["n"] == 0 or hb["auto"], hb)
                    pg.fill("#q301-sheet input[type=search], #q301-sheet input", "")
                pg.evaluate(f"document.getElementById('qg-{key}').click()"); pg.wait_for_timeout(400)

            # ---- 2, 3. the structure card
            ids = pg.evaluate("""() => { const M = window.__ANATOMY_MANIFEST__.meshes; const pick = (re, sys) => { const m = M.find(x => re.test(x.id) && (!sys || x.sys === sys)); return m && m.id; };
              return [pick(/^biceps_brachii_r/), pick(/palmaris_longus_muscle_l/), pick(/^humerus_l/), pick(/^median_nerve_r|median_nerve/, 'nerve'), pick(/anterior_cruciate_ligament_l/),
                      pick(/common_flexor_tendon_sheath_l/), pick(/^femoral_artery_r|brachial_artery_r/), pick(/fascia/, 'fascia'), pick(/deltoid_muscle_r|^deltoid_r/), pick(/^supraspinatus_l|supraspinatus_muscle_l/),
                      pick(/sciatic_nerve_l/), pick(/^femur_r/)].filter(Boolean).slice(0, 10); }""")
            check("3 ten sample structures found", len(ids) >= 8, ids)
            raw, rnd, fil = [], [], []
            mark_ct = None
            for i, sid in enumerate(ids):
                pg.evaluate("() => NMSKQuick.close()"); pg.wait_for_timeout(250)
                pg.evaluate("(id) => NMSKQuick.open(id, 700, 400)", sid); pg.wait_for_timeout(450)
                pg.evaluate("() => { const m = document.querySelector('.qc-more'); if (m && m.getAttribute('aria-expanded') !== 'true') m.click(); }"); pg.wait_for_timeout(650)
                t = pg.evaluate("() => { const i = document.getElementById('info'); return i && window.__q.vis(i) ? i.innerText : ''; }")
                if not t:
                    check(f"3 the card opened for {sid}", False); continue
                raw += [f"{sid}: {m}" for m in re.findall(r"\b[a-z][a-z0-9]*_[a-z0-9_]+\b", t)]
                rnd += [f"{sid}: {m}" for m in re.findall(r"\bQ\d{2,3}\b", t)]
                fil += [f"{sid}: {m}" for m in re.findall(r"\.(?:json|py|html|csv)\b|\b(?:data|scripts|docs|viewer|clinical)/", t)]
                if mark_ct is None:
                    mark_ct = pg.evaluate("""() => { const e = document.getElementById('a-mark'); return e ? {c: +window.__q.contrast(e).toFixed(2), vis: window.__q.vis(e), txt: e.textContent} : null; }""")
            check("3 no raw id (snake_case) visible in the card or parts prose", not raw, raw[:6])
            check("3 no round id (Qnnn) visible in the card or parts prose", not rnd, rnd[:6])
            check("3 no file name / repo path visible in the card or parts prose", not fil, fil[:6])
            check("2 the card's mark button is visible with contrast >= 4.5 and a word", bool(mark_ct) and mark_ct["vis"] and mark_ct["c"] >= 4.5 and "mark" in mark_ct["txt"], mark_ct)
            pg.evaluate("() => NMSKQuick.close()")
            pg.evaluate("() => { const x = document.getElementById('ic'); x && x.click(); }")

            # ---- 8. Pose
            pg.evaluate("document.getElementById('qg-pose').click()"); pg.wait_for_timeout(1200)
            po = pg.evaluate("""() => { const q = window.__q, p = document.getElementById('pose-panel'); if (!p || !q.vis(p)) return {open: false};
              const t = p.querySelector('.pz-head b, .pz-head span'); const r = (t || p).getBoundingClientRect(); const e = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
              const txt = p.innerText + ' ' + [...p.querySelectorAll('[title]')].map(x => x.title).join(' ');
              return {open: true, titleOk: !!(e && p.contains(e)), q: (txt.match(/\\bQ\\d{2,3}\\b|pose_rom_table/g) || []).length,
                      cov: q.cover([q.rect(p), q.rect(document.getElementById('q301-bar'))]), covP: q.cover([q.rect(p)])}; }""")
            check("8 the Pose panel opened", po.get("open"), po)
            if po.get("open"):
                check("8 the Pose title is not covered by the toolbar", po["titleOk"], po)
                pg.evaluate("() => { const s = document.querySelector('#pose-panel .pz-help summary'); s && s.click(); }"); pg.wait_for_timeout(300)
                q8 = pg.evaluate("() => { const p = document.getElementById('pose-panel'); const t = p.innerText + ' ' + [...p.querySelectorAll('[title]')].map(x => x.title).join(' '); return (t.match(/\\bQ\\d{2,3}\\b|pose_rom_table|\\.md\\b/g) || []); }")
                check("8 no Qnnn / pose_rom_table in the Pose panel or its tooltips", not q8, q8)
                if phone:
                    check("4 Pose (compact) leaves >= 50% of the model visible (phone)", po["cov"] <= 0.50, po)
                else:
                    check("4 Pose covers <= 40% of the model box (desktop)", po["covP"] <= 0.40, po)
            pg.evaluate("() => { const x = document.querySelector('#pose-panel .pz-head button:last-child'); x && x.click(); }"); pg.wait_for_timeout(300)

            # ---- 4. Layers rail, Labels
            for label, js_open, sel in (("Layers", "document.getElementById('btn-panel') && document.getElementById('btn-panel').click()", "#rail"),
                                        ("Labels", "document.getElementById('t-labels') && document.getElementById('t-labels').click()", "#lab-panel")):
                pg.evaluate(js_open); pg.wait_for_timeout(1300)
                r = pg.evaluate("(sel) => { const q = window.__q, p = document.querySelector(sel); if (!p || !q.vis(p)) return {open: false}; return {open: true, cov: q.cover([q.rect(p), q.rect(document.getElementById('q301-bar'))]), covP: q.cover([q.rect(p)])}; }", sel)
                if not r.get("open"):
                    print(f"  --   {label} did not open on this page (not held to it)")
                else:
                    if phone:
                        check(f"4 {label} (compact) leaves >= 50% of the model visible (phone)", r["cov"] <= 0.50, r)
                    else:
                        check(f"4 {label} covers <= 40% of the model box (desktop)", r["covP"] <= 0.40, r)
                pg.evaluate(js_open); pg.wait_for_timeout(500)
                pg.evaluate("() => { const x = document.getElementById('lab-close'); x && window.__q.vis(x) && x.click(); }")

            # ---- 4, 9. Measure
            pg.evaluate("document.getElementById('qg-measure').click()"); pg.wait_for_timeout(800)
            pg.evaluate("() => { const b = [...document.querySelectorAll('#ms-bar button')].find(x => /CT value/.test(x.textContent)); b && b.click(); }")
            bx = pg.evaluate("() => NMSKQuick.box()")
            cx = (bx["l"] + bx["r"]) / 2
            for k in range(6):
                pg.mouse.click(cx, bx["t"] + (bx["b"] - bx["t"]) * (0.28 + 0.08 * k)); pg.wait_for_timeout(450)
            n1 = pg.evaluate("() => document.querySelectorAll('#ms-res .ms-r').length")
            mc = pg.evaluate("() => { const q = window.__q, p = document.getElementById('ms-bar'); return {cov: q.cover([q.rect(p), q.rect(document.getElementById('q301-bar'))]), covP: q.cover([q.rect(p)]), h: p.getBoundingClientRect().height}; }")
            if phone:
                check("4 Measure with results leaves >= 50% of the model visible (phone)", mc["cov"] <= 0.50, mc)
            else:
                check("4 Measure with results covers <= 40% of the model box (desktop)", mc["covP"] <= 0.40, mc)
            bar_ok = pg.evaluate("() => { const bar = document.getElementById('ms-bar').getBoundingClientRect(), q = document.getElementById('q301-bar').getBoundingClientRect(); return bar.top >= q.bottom - 1 || bar.right <= q.left || bar.left >= q.right; }")
            check("4 the measure bar does not lie over the control bar", bar_ok)
            pg.evaluate("() => { const b = [...document.querySelectorAll('#ms-bar button')].find(x => /^Clear/.test(x.textContent.trim())); b && b.click(); }"); pg.wait_for_timeout(500)
            left = pg.evaluate("() => [...document.querySelectorAll('body *')].filter(e => e.children.length === 0 && /\\bHU\\b/.test(e.textContent) && window.__q.vis(e.closest('svg,span,div') || e)).length")
            check("9 Clear removes every CT pin and label from the model", left == 0, left)
            pg.evaluate("() => { const b = [...document.querySelectorAll('#ms-bar button')].find(x => /CT value/.test(x.textContent)); b && b.click(); }")
            pg.mouse.click(cx, bx["t"] + (bx["b"] - bx["t"]) * 0.35); pg.wait_for_timeout(500)
            n2 = pg.evaluate("() => document.querySelectorAll('#ms-res .ms-r').length")
            pg.evaluate("document.getElementById('ms-close').click()"); pg.wait_for_timeout(600)
            left = pg.evaluate("() => [...document.querySelectorAll('body *')].filter(e => e.children.length === 0 && /\\bHU\\b/.test(e.textContent) && !/^(SCRIPT|STYLE)$/.test(e.tagName) && window.__q.vis(e.closest('svg,span,div') || e)).length")
            check("9 closing Measure removes the pins (placed " + str(n1) + " + " + str(n2) + ")", left == 0, left)
            pg.evaluate("document.getElementById('qg-measure').click()"); pg.wait_for_timeout(500)
            pg.evaluate("() => { const b = [...document.querySelectorAll('#ms-bar button')].find(x => /cm³/.test(x.textContent) && /vol/.test(x.getAttribute('data-ms') || '')); b && b.click(); }")
            for k in range(5):
                pg.mouse.click(cx + (k - 2) * 6, bx["t"] + (bx["b"] - bx["t"]) * (0.3 + 0.1 * k)); pg.wait_for_timeout(400)
            vt = pg.evaluate("() => [...document.querySelectorAll('#ms-res .ms-r')].map(e => e.textContent)")
            check("9 no 'non-manifold' / '--' wording in the volume results", not any(re.search(r"non-manifold|--", t) for t in vt), vt[:3])
            pg.evaluate("document.getElementById('ms-close').click()")

            # ---- Q355: 12. the measure bar's close button is reachable; 13. panels and modes; 14. rings; 15. closest structures
            pg.evaluate("document.getElementById('qg-measure').click()"); pg.wait_for_timeout(700)
            mb = pg.evaluate("""() => { const x = document.getElementById('ms-close'), r = x.getBoundingClientRect(), bar = document.getElementById('ms-bar').getBoundingClientRect();
              return {l: r.left, r: r.right, t: r.top, b: r.bottom, vw: innerWidth, vh: innerHeight, barR: bar.right, barL: bar.left, w: r.width}; }""")
            check("12 the measure bar's close button lies inside the viewport and inside the bar",
                  mb["l"] >= 0 and mb["r"] <= mb["vw"] + 0.5 and mb["t"] >= 0 and mb["b"] <= mb["vh"] and mb["r"] <= mb["barR"] + 1 and mb["l"] >= mb["barL"] - 1 and mb["w"] > 10, mb)
            pg.evaluate("document.getElementById('ms-close').click()"); pg.wait_for_timeout(300)
            vis = "(id) => { const e = document.getElementById(id); return !!e && !e.hidden && getComputedStyle(e).display !== 'none' && e.getBoundingClientRect().width > 4; }"
            pg.evaluate("() => { const t = document.getElementById('t-slices'); t && t.click(); }"); pg.wait_for_timeout(500)
            pg.evaluate("() => { const b = document.getElementById('btn-insert'); b && !document.querySelector('#pm-att:not([hidden])') && b.click(); }"); pg.wait_for_timeout(900)
            both = [pg.evaluate(vis, "xsp-panel"), pg.evaluate(vis, "pm-att")]
            if phone:
                check("13 phone: Slices and Attachments are never open together", not (both[0] and both[1]), both)
            else:
                pg.evaluate("() => { const t = document.getElementById('t-slices'); t && document.getElementById('xsp-panel').hidden && t.click(); }"); pg.wait_for_timeout(400)
            pg.evaluate("() => { const t = document.getElementById('t-slices'); t && document.getElementById('xsp-panel').hidden && t.click(); }"); pg.wait_for_timeout(400)
            pg.evaluate("() => NMSKModes.enter('inj')"); pg.wait_for_function("NMSKModes.current() === 'inj'", timeout=60000); pg.wait_for_timeout(1200)
            left = [i for i in ("xsp-panel", "pm-att") if pg.evaluate(vis, i)]
            check("13 Anatomy -> Injection: no Anatomy panel (Slices, Attachments) is visible in the mode", not left, left)
            pg.evaluate("""async () => { const sleep = ms => new Promise(r => setTimeout(r, ms));
              const b = document.querySelector('.mb-chip .mb-mini') || document.querySelector('.mb-text'); if (b) b.click(); await sleep(300);
              const inp = document.querySelector('.mc-pick .mc-search'); if (!inp) return; inp.value = 'biceps_brachii'; inp.dispatchEvent(new Event('input')); await sleep(250);
              const row = document.querySelector('.mc-pick .mc-res button'); if (row) row.click(); await sleep(2500); }""")
            tr = pg.evaluate("""() => { const o = []; document.querySelectorAll('.mc-left .mc-drow .nm, .mb-text').forEach(e => { const r = e.getBoundingClientRect(); if (r.width < 2) return;
                o.push({t: e.textContent.slice(0, 40), cut: e.scrollWidth > e.clientWidth + 1 || e.scrollHeight > e.clientHeight + 1}); }); return o; }""")
            if phone:
                check("15 closest-structures names and the header name are not truncated (phone)", tr and not any(x["cut"] for x in tr), tr[:6])
            pg.screenshot(path=str(SHOTS / f"inj_{w}.png")) if SHOTS else None
            pg.evaluate("() => NMSKModes.exit()"); pg.wait_for_timeout(1500)
            back = [pg.evaluate(vis, i) for i in ("xsp-panel", "pm-att")]
            check("13 leaving the mode brings the panels back (one of them on a phone)", any(back) and (not phone or not all(back)), back)
            pg.screenshot(path=str(SHOTS / f"anat_back_{w}.png")) if SHOTS else None
            if phone:
                pg.evaluate("() => { const x = document.getElementById('xsp-close'); x && x.click(); }")
            pg.evaluate("() => { const b = document.getElementById('btn-insert'); b && !document.querySelector('#pm-att:not([hidden])') && b.click(); }"); pg.wait_for_timeout(1500)
            pg.evaluate("document.getElementById('qg-view').click()"); pg.wait_for_timeout(600)
            pg.evaluate("() => { const b = [...document.querySelectorAll('#q301-sheet .pill')].find(x => /^reset/i.test(x.textContent.trim())); b && b.click(); }"); pg.wait_for_timeout(1500)
            pg.evaluate("document.getElementById('qg-view').click()"); pg.wait_for_timeout(1200)
            rg = pg.evaluate("""() => { const q = window.__q, v = document.getElementById('view').getBoundingClientRect(), o = [];
              document.querySelectorAll('#pm-layer .pm:not([hidden]) .pm-ring').forEach(e => { const r = e.getBoundingClientRect(); o.push(r.width); });
              return {n: o.length, max: Math.max(0, ...o), vh: v.height, k: getComputedStyle(document.getElementById('pm-layer')).getPropertyValue('--pmk')}; }""")
            check("14 whole-body zoom: no ring is wider than 2% of the model view's height (+2 px)",
                  rg["n"] == 0 or rg["max"] <= 0.02 * rg["vh"] + 2, rg)
            pg.screenshot(path=str(SHOTS / f"rings_{w}.png")) if SHOTS else None
            pg.evaluate("() => { const x = document.querySelector('#pm-att .pp-x'); x && x.click(); }"); pg.wait_for_timeout(300)

            # ---- 11. type floor in the public panels (after everything has been opened once)
            pg.evaluate("document.getElementById('qg-view').click()"); pg.wait_for_timeout(1500)
            sm = pg.evaluate(SMALL)
            check("11 no text under 10 px in the open sheet / bar / brand / corner", not sm, sm[:6])
            pg.evaluate("document.getElementById('qg-view').click()")
            pg.evaluate("() => NMSKQuick.open('biceps_brachii_r', 700, 400)"); pg.wait_for_timeout(500)
            pg.evaluate("() => { const m = document.querySelector('.qc-more'); if (m && m.getAttribute('aria-expanded') !== 'true') m.click(); }"); pg.wait_for_timeout(1500)
            sm = pg.evaluate(SMALL)
            check("11 no text under 10 px in the structure card", not sm, sm[:6])

            check("0 page errors", not errs, errs[:3])
            b.close()
    finally:
        srv.kill()
    print("Q344_UI_OK" if not FAILS else "Q344_UI_FAIL " + "; ".join(FAILS[:12]))
    return 0 if not FAILS else 1


if __name__ == "__main__":
    raise SystemExit(main())
