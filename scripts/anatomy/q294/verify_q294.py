#!/usr/bin/env python3
"""Q294: real headless-Chromium check of the page-wide Undo / Redo / Reset, the redesigned Marked / Display screen, the part
slices (one finger, thickness, interval, display-only spread), the abbreviation popup + "i" tips, the measure tools and the
ultrasound sheet thickness under zoom -- on locally served template-only rebuilt pages (one per engine).

Desktop 1400x900 (real mouse clicks / keys) and phone 390x844 (has_touch, real touch taps), per page:
  A  14 real user actions (cut on / axial / +10 mm / exit; slices: part, thickness, interval, spread x2, x3, scope, interval;
     measure: a distance and a 3-point angle tapped on the model, Clear) -> 12 undos (the floating Undo button; desktop: the last
     ones by Ctrl/Cmd+Z) and 12 redos (Redo button / Ctrl+Shift+Z / Ctrl+Y) restore the EXACT recorded snapshot at every step
  B  the Marked / Display screen: marks by tapping the list ticks; "Fade others" / "Everything" / "Only marked" one-tap; the
     summary says what is marked and how each group is drawn, the scene line counts shown / hidden / faded; phone targets >= 36 px,
     no horizontal scroll
  C  part slices: the index finger (Z page; the own page has no separate finger phalanges -> its forearm segment), 1 mm every 10 mm:
     slice count = floor((L - 1) / 10) + 1 with L measured independently from the part's own vertices along the stack axis;
     interval / thickness exact; spread x3 moves the drawn faces by (t - mean) * 2 and leaves every true position unchanged
  D  abbreviation popup: abbreviated labels on; hovering (desktop) / tapping (phone) a short label opens the full name; "i" tips
  E  measure: synthetic geometry through the API (50 mm, 90 / 30 deg, two-line 35 deg, Cobb 35 deg, within 0.5 mm / 0.5 deg);
     real taps on the model (value = |P1 - P2| of the tapped surface points, recomputed here independently); real taps on a 2-D
     image pane at known pixel offsets (120 px / 90 px right triangle, a 20 deg Cobb pair) against the pane's own mm-per-pixel
  F  Reset: changes in several panels -> the Reset button -> the page-start snapshot exactly; Undo brings the changes back
  G  ultrasound: a probe on a deep fascia; the fascia band thickness (mm, leading to trailing -6 dB edge of the sheet's echo) at 1x and at 4x (re-simulated, finer pixel) agree within 0.35 mm and lie in 0.5-2.0 mm -- in the panel (desktop),
     the US mode (phone) and the clean full-screen split (desktop, CINE paused)
  I  thin sheets at their true thickness under every transform: rotation 0 / 45 / 90, tilt 15 (heel, rock), depth 3 / 5 / 8 cm, zoom 4x
     (re-simulated) and the live CINE tier -- the drawn thickness along the beam (the image's own sheet raster) vs t / |m.b| from the
     sheet's own mesh normal m (the only widening allowed: 1 / cos of the cut's obliquity), median ratio 0.8-1.25
  J  probe placement: ONE real drag (mouse / CDP touch) from the probe slides it over the skin to the skin under the release point, the
     axis on the skin normal, the face on the skin, the camera not orbiting; the pad (rotate 15, tilt 5 toward heel / marker, upright) one
     tap each, uncovered; in the panel, the full-screen split, and on a phone the US mode (one tap on its 3-D thumbnail, then its
     full-screen split); the step counts printed
  K  the transducer per type (linear / convex / sector): footprint, housing, face gap to the skin < 0.5 mm, marker ridge on image left
  L  fibres per bundle: deltoid parts, pectoralis major heads, trapezius parts, rectus femoris straight / reflected heads -- bundle
     count, axes > 15 deg apart, pennation = the cited compartments (+-1 deg), the image's fibre direction and the 3-D fibre lines =
     the bundle's own axis at its pennation (+-1 deg)
  H  0 page errors

    python3 scripts/anatomy/q294/verify_q294.py PAGE_DIR [PAGE_DIR ...]
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "q283"))
import verify_q283 as V  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

check = V.check
T = 300000
A = "window.NMSKClinicalTool.api"

SNAP = "() => JSON.stringify(window.NMSKHistory.snapshot())"
HST = "() => window.NMSKHistory.state()"


def wait_idx(pg, before, timeout=20000):
    pg.wait_for_function("(b) => { const s = window.NMSKHistory.state(); return s.idx !== b && !s.pending; }", arg=before, timeout=timeout)


def settle(pg):
    pg.wait_for_timeout(450)
    pg.evaluate("() => window.NMSKHistory.commit()")


def xs_idle(pg):
    pg.wait_for_function("() => !window.xsecCtl.state().busy", timeout=T)


MODEL_PTS = """([n, minGap]) => {
  const a = window.NMSKClinicalTool.api, c = a.canvas, r = c.getBoundingClientRect(), out = [];
  for (let gy = 0.30; gy <= 0.75 && out.length < n; gy += 0.035) for (let gx = 0.32; gx <= 0.68 && out.length < n; gx += 0.03) {
    const x = Math.round(r.left + r.width * gx), y = Math.round(r.top + r.height * gy), el = document.elementFromPoint(x, y);
    if (el !== c) continue;
    const h = a.pick({clientX: x, clientY: y}); if (!h) continue;
    if (out.some(p => Math.hypot(p[0] - x, p[1] - y) < minGap)) continue;
    out.push([x, y]);
  }
  return out; }"""

SURF_PT = """([x, y]) => {               // the surface point under (x, y), computed here (own: the engine's raycast; Z: ray x the picked mesh)
  const a = window.NMSKClinicalTool.api, h = a.pick({clientX: x, clientY: y}); if (!h) return null;
  if (h.point) return h.point;
  const g = a.geometry(h.i), R = a.ray({clientX: x, clientY: y}), o = R.o, d = R.d, P = g.pos, I = g.idx; let best = null;
  for (let k = 0; k < I.length; k += 3) {
    const A = I[k] * 3, B = I[k + 1] * 3, C = I[k + 2] * 3;
    const e1 = [P[B] - P[A], P[B + 1] - P[A + 1], P[B + 2] - P[A + 2]], e2 = [P[C] - P[A], P[C + 1] - P[A + 1], P[C + 2] - P[A + 2]];
    const p = [d[1] * e2[2] - d[2] * e2[1], d[2] * e2[0] - d[0] * e2[2], d[0] * e2[1] - d[1] * e2[0]], det = e1[0] * p[0] + e1[1] * p[1] + e1[2] * p[2];
    if (Math.abs(det) < 1e-12) continue;
    const t0 = [o[0] - P[A], o[1] - P[A + 1], o[2] - P[A + 2]], u = (t0[0] * p[0] + t0[1] * p[1] + t0[2] * p[2]) / det; if (u < 0 || u > 1) continue;
    const q = [t0[1] * e1[2] - t0[2] * e1[1], t0[2] * e1[0] - t0[0] * e1[2], t0[0] * e1[1] - t0[1] * e1[0]], v = (d[0] * q[0] + d[1] * q[1] + d[2] * q[2]) / det; if (v < 0 || u + v > 1) continue;
    const t = (e2[0] * q[0] + e2[1] * q[1] + e2[2] * q[2]) / det; if (t > 1e-6 && (best === null || t < best)) best = t;
  }
  return best === null ? null : [o[0] + d[0] * best, o[1] + d[1] * best, o[2] + d[2] * best]; }"""


def tap_xy(pg, x, y, phone):
    if phone:
        pg.touchscreen.tap(x, y)
    else:
        pg.mouse.click(x, y)
    pg.wait_for_timeout(250)


def close_cards(pg, phone):
    """phones: the structure card / sheets cover the model -- close them the way a user would (their own buttons)"""
    if not phone:
        return
    for sel in pg.evaluate("""() => { const o = []; const mi = document.getElementById('m-info'), ml = document.getElementById('m-list');
        if (mi && mi.getAttribute('aria-pressed') === 'true') o.push('#m-info'); if (ml && ml.getAttribute('aria-pressed') === 'true') o.push('#m-list');
        const inf = document.getElementById('info'); if (inf && !inf.classList.contains('hidden') && document.getElementById('ic') && inf.getBoundingClientRect().width > 0) o.push('#ic');
        const r = document.getElementById('rail'); if (r && r.classList.contains('open')) o.push('#btn-panel'); return o; }"""):
        tap(pg, sel, phone)


def tap(pg, sel, phone):
    V.tap(pg, sel, phone)
    pg.wait_for_timeout(200)


def model_measure(pg, kind, n, phone, errs, tag):
    """arm `kind` in the bar, tap n points on the model, return (state entry, the tapped points, independent surface points)"""
    close_cards(pg, phone)
    tap(pg, f'#ms-bar [data-ms="{kind}"]', phone)
    pts = pg.evaluate(MODEL_PTS, [n, 70])
    if os.environ.get("Q294_DEBUG"):
        print("     measure:", kind, pts, pg.evaluate("() => { const b = document.querySelector('#ms-bar [data-ms]').getBoundingClientRect(); const e = document.elementFromPoint(b.left + 5, b.top + 5); return [window.measureCtl.state().tool, Math.round(b.top), e && (e.id || e.tagName)]; }"), flush=True)
    if len(pts) < n:
        check(f"{tag}: found {len(pts)} model points to tap for {kind}", False, errs)
        return None, pts, []
    surf = [pg.evaluate(SURF_PT, p) for p in pts]
    for p in pts:
        tap_xy(pg, p[0], p[1], phone)
    pg.wait_for_timeout(300)
    st = pg.evaluate("() => window.measureCtl.state()")
    if os.environ.get("Q294_DEBUG"):
        print("     after taps:", st["tool"], st["msg"], len(st["list"]), flush=True)
    return (st["list"][-1] if st["list"] else None), pts, surf


def dist(a, b):
    return sum((x - y) ** 2 for x, y in zip(a, b)) ** 0.5


def ang3(a, b, c):
    import math
    u = [x - y for x, y in zip(a, b)]; v = [x - y for x, y in zip(c, b)]
    return math.degrees(math.acos(max(-1, min(1, sum(p * q for p, q in zip(u, v)) / (dist(a, b) * dist(c, b))))))


# ---------------------------------------------------------------------------------------------------------------- A: undo / redo
def part_a(pg, phone, errs, tag):
    snaps = [pg.evaluate(SNAP)]
    steps = []

    def step(name, fn):
        if os.environ.get("Q294_DEBUG"):
            print("     step:", name, flush=True)
        fn()
        settle(pg)
        s = pg.evaluate(SNAP)
        ok = s != snaps[-1]
        steps.append((name, ok))
        snaps.append(s)

    step("cut on", lambda: tap(pg, "#t-cut", phone))
    step("cut axial", lambda: tap(pg, '#cut-axis [data-axis="y"]', phone))
    step("cut +10 mm", lambda: tap(pg, '#cut-steps [data-step="10"]', phone))
    step("cut exit", lambda: tap(pg, "#cut-exit", phone))
    tap(pg, "#t-slices", phone)
    opt = pg.evaluate("() => { window.partSlices.fill(); const o = Array.from(document.querySelectorAll('#xsp-part option')).map(x => [x.value, x.textContent]); const f = o.find(x => /^Index finger \\(R\\)/.test(x[1])) || o.find(x => /^Forearm \\(R\\)/.test(x[1])) || o.find(x => x[0] === 'card'); return f || null; }")
    step(f"slices part = {opt[1] if opt else None}", lambda: (pg.select_option("#xsp-part", opt[0]), xs_idle(pg)))
    step("thickness 2", lambda: (tap(pg, '#xsp-th [data-xth="2"]', phone), xs_idle(pg)))
    step("interval 5", lambda: (tap(pg, '#xsp-int [data-xint="5"]', phone), xs_idle(pg)))
    step("spread x2", lambda: (tap(pg, '#xsp-gap [data-xgap="2"]', phone), xs_idle(pg)))
    step("spread x3", lambda: (tap(pg, '#xsp-gap [data-xgap="3"]', phone), xs_idle(pg)))
    step("scope", lambda: (tap(pg, "#xsp-scope", phone), xs_idle(pg)))
    step("interval 20", lambda: (tap(pg, '#xsp-int [data-xint="20"]', phone), xs_idle(pg)))
    tap(pg, "#xsp-close", phone)
    tap(pg, "#t-measure", phone)
    step("distance on the model", lambda: model_measure(pg, "dist", 2, phone, errs, tag))
    step("3-point angle on the model", lambda: model_measure(pg, "ang3", 3, phone, errs, tag))
    step("clear measurements", lambda: tap(pg, "#ms-clear", phone))
    n = len(snaps) - 1
    check(f"{tag} A: {n} real actions, each a new history entry ({[s for s in steps if not s[1]]} unchanged)", n >= 13 and all(s[1] for s in steps), errs)
    bad = []
    for k in range(12):
        if not phone and k >= 9:
            pg.keyboard.press("Control+z")
        else:
            tap(pg, "#h-undo", phone)
        pg.wait_for_timeout(250)
        xs_idle(pg)
        if pg.evaluate(SNAP) != snaps[n - 1 - k]:
            bad.append(("undo", k + 1, steps[n - 1 - k][0]))
    check(f"{tag} A: 12 undos each restore the exact recorded state (mismatch {bad[:3]})", not bad, errs)
    bad = []
    for k in range(12):
        if not phone and k == 10:
            pg.keyboard.press("Control+Shift+z")
        elif not phone and k == 11:
            pg.keyboard.press("Control+y")
        else:
            tap(pg, "#h-redo", phone)
        pg.wait_for_timeout(250)
        xs_idle(pg)
        if pg.evaluate(SNAP) != snaps[n - 12 + k + 1]:
            bad.append(("redo", k + 1, steps[n - 12 + k][0]))
    st = pg.evaluate(HST)
    check(f"{tag} A: 12 redos each restore the exact recorded state (mismatch {bad[:3]}); history {st['idx'] + 1}/{st['len']}, redo empty", not bad and not st["canRedo"], errs)
    pg.evaluate("() => { window.xsecCtl.setPart(null); window.measureCtl.open(false); }")
    settle(pg)


# ---------------------------------------------------------------------------------------------------------- B: marked / display
def open_sel(pg, phone, zan):
    if phone:
        tap(pg, "#btn-panel" if zan else "#m-list", phone)
    elif not pg.evaluate("() => { const r = document.getElementById('sel-sec').getBoundingClientRect(); return r.width > 0; }"):
        tap(pg, "#t-lay3", phone)                        # the Q267 "Model only" default hides the side panel: one tap -> Split
    pg.wait_for_timeout(500)


def close_sel(pg, phone, zan):
    if phone:
        tap(pg, "#btn-panel" if zan else "#m-list", phone)
    pg.wait_for_timeout(300)


def part_b(pg, phone, zan, errs, tag):
    open_sel(pg, phone, zan)
    pg.evaluate("() => { const q = document.getElementById(document.getElementById('q') ? 'q' : 'search'); }")
    ids = pg.evaluate("() => Array.from(document.querySelectorAll('.ss-mk[data-id]')).filter(b => { const r = b.getBoundingClientRect(); return r.width > 0 && !b.closest('#i-act') && !b.closest('#info'); }).slice(0, 2).map(b => b.getAttribute('data-id'))")
    for i in ids:
        tap(pg, f'.ss-mk[data-id="{i}"]', phone)
    look = "() => ({sel: document.getElementById('ss-look-sel').textContent, oth: document.getElementById('ss-look-oth').textContent, n: document.getElementById('sel-count').textContent, scene: document.getElementById('ss-scene').textContent, marks: window.NMSKClinicalTool.api.selection().state().marks.length})"
    s0 = pg.evaluate(look)
    check(f"{tag} B: two list ticks tapped -> summary 'Marked {s0['n']} -> {s0['sel']}', 'Others -> {s0['oth']}', scene '{s0['scene']}'", s0["marks"] == 2 and s0["n"] == "2" and s0["sel"] == "shown" and s0["oth"] == "shown" and "shown" in s0["scene"], errs)
    tap(pg, "#sel-p-fadeoth", phone); pg.wait_for_timeout(1700)
    s1 = pg.evaluate(look)
    check(f"{tag} B: one tap 'Fade others' -> 'Others -> {s1['oth']}', scene '{s1['scene']}'", s1["oth"] == "faded" and s1["sel"] == "shown" and "faded" in s1["scene"], errs)
    tap(pg, "#sel-p-isolate", phone); pg.wait_for_timeout(1700)
    s2 = pg.evaluate(look)
    import re
    hid = lambda s: int(re.search(r"(\d+) hidden", s).group(1)) if re.search(r"(\d+) hidden", s) else -1
    check(f"{tag} B: one tap 'Only marked' -> 'Others -> {s2['oth']}', scene '{s2['scene']}' (more hidden than before)", s2["oth"] == "hidden" and hid(s2["scene"]) > hid(s1["scene"]), errs)
    tap(pg, "#ss-q-all", phone); pg.wait_for_timeout(600)
    s3 = pg.evaluate(look)
    check(f"{tag} B: one tap 'Everything' -> both groups shown again, marks kept ({s3['marks']})", s3["sel"] == "shown" and s3["oth"] == "shown" and s3["marks"] == 2, errs)
    g = pg.evaluate("() => { const q = Array.from(document.querySelectorAll('#sel-sec .ss-quick button, #sel-sec .ss-acts button')).map(b => { const r = b.getBoundingClientRect(); return [b.id, Math.round(r.width), Math.round(r.height)]; }); const sec = document.getElementById('sel-sec'); return {q, sw: sec.scrollWidth, cw: sec.clientWidth, details: Array.from(sec.querySelectorAll('details')).map(d => [d.id || d.querySelector('summary').textContent, d.open])}; }")
    check(f"{tag} B: one-tap row {len(g['q'])} buttons{' >= 36 px tall' if phone else ''} ({g['q'][:4]}), no horizontal scroll ({g['sw']} <= {g['cw']}); advanced parts folded {g['details']}",
          len(g["q"]) >= 9 and (not phone or all(h >= 35.5 for _, _, h in g["q"])) and g["sw"] <= g["cw"] + 1 and not any(o for _, o in g["details"]), errs)
    pg.evaluate("() => window.NMSKClinicalTool.api.selection().clear()")
    close_sel(pg, phone, zan)
    settle(pg)


# --------------------------------------------------------------------------------------------------------------- C: part slices
def part_c(pg, phone, zan, errs, tag):
    seg = pg.evaluate("() => { const s = window.partSlices.segments(); const f = s.find(x => /^Index finger \\(R\\)/.test(x.label)) || s.find(x => /^Forearm \\(R\\)/.test(x.label)); return f; }")
    if not seg:
        check(f"{tag} C: a finger or forearm segment on this page", False, errs); return
    if zan:
        check(f"{tag} C: the index finger is its own segment on this page ({seg['label']}: {len(seg['ids'])} phalanges)", seg["label"].startswith("Index finger") and len(seg["ids"]) == 3, errs)
    else:
        check(f"{tag} C: no separate finger phalanges on this page -> the forearm segment ({seg['label']}: {seg['ids']})", seg["label"].startswith("Forearm"), errs)
    r = pg.evaluate("""async (seg) => {
      const X = window.xsecCtl; X.setPart(seg.ids, seg.label); X.setPartThickness(1); X.setPartInterval(10); X.setGap(1); X.setScope('around'); X.rebuildNow();
      const s = X.state(), a = s.axis.a, A = window.NMSKClinicalTool.api, L = A.list();
      let lo = 1e30, hi = -1e30;                               // the part's extent along the stack axis, from its own vertices (not from the controller)
      seg.ids.forEach(id => L.forEach((r, i) => { if (r.id !== id) return; const g = A.geometry(i); if (!g) return; const P = g.pos; for (let k = 0; k < P.length; k += 3) { const t = a[0] * P[k] + a[1] * P[k + 1] + a[2] * P[k + 2]; if (t < lo) lo = t; if (t > hi) hi = t; } }));
      const L0 = hi - lo, exp = Math.floor((L0 - 1) / 10 + 1e-9) + 1;
      const ints = s.planes.slice(1).map((p, k) => p.t - s.planes[k].t), ths = s.planes.map(p => p.far - p.d);
      const before = s.planes.map(p => [p.t, p.d, p.far]);
      X.setGap(3); X.rebuildNow(); const s3 = X.state();
      const after = s3.planes.map(p => [p.t, p.d, p.far]), ts = s3.planes.map(p => p.t), m = ts.reduce((x, y) => x + y, 0) / ts.length;
      const offOk = s3.faces.every(f => Math.abs(f.off - (s3.planes[f.k].t - m) * 2) < 0.02);
      return {L: L0, exp, n: s.planes.length, faces: s.slots, ints: [Math.min(...ints), Math.max(...ints)], ths: [Math.min(...ths), Math.max(...ths)], same: JSON.stringify(before) === JSON.stringify(after), offOk, maxOff: Math.max(...s3.faces.map(f => Math.abs(f.off))), ms: s.ms, slots3: s3.slots};
    }""", seg)
    check(f"{tag} C: 1 mm every 10 mm along {r['L']:.1f} mm -> {r['n']} slices (expected floor((L - 1) / 10) + 1 = {r['exp']}), {r['faces']} faces (near + far each), built in {r['ms']} ms",
          r["n"] == r["exp"] and r["faces"] == 2 * r["n"], errs)
    check(f"{tag} C: interval {r['ints'][0]:.2f}-{r['ints'][1]:.2f} mm, thickness {r['ths'][0]:.2f}-{r['ths'][1]:.2f} mm", abs(r["ints"][0] - 10) < 0.02 and abs(r["ints"][1] - 10) < 0.02 and abs(r["ths"][0] - 1) < 0.02 and abs(r["ths"][1] - 1) < 0.02, errs)
    check(f"{tag} C: spread x3 draws the faces up to {r['maxOff']:.0f} mm apart ((t - mean) x 2 each) and every true position is unchanged ({r['same']})", r["offOk"] and r["same"] and r["maxOff"] > 10 and r["slots3"] == r["faces"], errs)
    pg.evaluate("() => window.xsecCtl.setPart(null)")
    settle(pg)


# ----------------------------------------------------------------------------------------------------------- D: abbreviations
def part_d(pg, phone, errs, tag):
    pg.evaluate("() => { const l = window.NMSKClinicalTool.api.labels(); l.set('text', 'abbr'); l.setMode('vis'); l.refreshNow(); }")
    try:
        pg.wait_for_function("() => Array.from(document.querySelectorAll('.lb-t[data-full]')).some(e => { const r = e.getBoundingClientRect(); return r.width > 4 && document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2) === e; })", timeout=180000)
    except Exception:
        pass
    t = pg.evaluate("() => { const e = Array.from(document.querySelectorAll('.lb-t[data-full]')).find(e => { const r = e.getBoundingClientRect(); return r.width > 4 && document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2) === e; }); if (!e) return null; const r = e.getBoundingClientRect(); return {x: r.left + r.width / 2, y: r.top + r.height / 2, short: e.textContent, full: e.getAttribute('data-full')}; }")
    if not t:
        check(f"{tag} D: an abbreviated label on screen", False, errs)
    else:
        if phone:
            pg.touchscreen.tap(t["x"], t["y"])
        else:
            pg.mouse.move(t["x"], t["y"])
        pg.wait_for_timeout(400)
        s = pg.evaluate("() => NMSKTips.state()")
        close_cards(pg, phone)
        check(f"{tag} D: {'tapping' if phone else 'hovering'} the label '{t['short']}' opens the popup '{s['text']}'", s["open"] and s["text"] == t["full"] and len(t["full"]) > len(t["short"]), errs)
    pg.evaluate("() => { const l = window.NMSKClinicalTool.api.labels(); l.setMode('off'); l.set('text', 'full'); }")
    tp = pg.evaluate("() => { const hit = x => { const r = x.getBoundingClientRect(); return r.width > 0 && document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2) === x; }; const b = Array.from(document.querySelectorAll('.tip-i')).find(hit); return {n: NMSKTips.state().folded, vis: !!b, id: b ? (b.nextElementSibling && b.nextElementSibling.className) : null}; }")
    if tp["vis"]:
        pg.evaluate("() => { const hit = x => { const r = x.getBoundingClientRect(); return r.width > 0 && document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2) === x; }; const b = Array.from(document.querySelectorAll('.tip-i')).find(hit); b.setAttribute('data-vt', '1'); }")
        before = pg.evaluate("() => { const p = document.querySelector('.tip-i[data-vt]').nextElementSibling; return getComputedStyle(p).display; }")
        tap(pg, ".tip-i[data-vt]", phone)
        after = pg.evaluate("() => { const p = document.querySelector('.tip-i[data-vt]').nextElementSibling; return getComputedStyle(p).display; }")
        check(f"{tag} D: {tp['n']} help texts folded behind an 'i'; a tap shows one ({before} -> {after})", tp["n"] >= 8 and before == "none" and after != "none", errs)
        tap(pg, ".tip-i[data-vt]", phone)
    else:
        check(f"{tag} D: {tp['n']} help texts folded behind an 'i'", tp["n"] >= 8, errs)
    settle(pg)


# --------------------------------------------------------------------------------------------------------------------- E: measure
def part_e(pg, phone, errs, tag):
    r = pg.evaluate("""() => { const M = window.measureCtl, c = Math.cos, s = Math.sin, d = Math.PI / 180, out = {};
      M.clear();
      out.dist = M.add('dist', '3d', [[0, 0, 0], [30, 40, 0]]).id;
      M.add('ang3', '3d', [[10, 0, 0], [0, 0, 0], [0, 10, 0]]);
      M.add('ang3', '3d', [[10, 0, 0], [0, 0, 0], [10 * c(30 * d), 10 * s(30 * d), 0]]);
      M.add('ang2', '3d', [[0, 0, 0], [20 * c(10 * d), 20 * s(10 * d), 0], [5, 30, 0], [5 + 20 * c(-25 * d), 30 + 20 * s(-25 * d), 0]]);
      M.add('cobb', '3d', [[0, 0, 0], [40 * c(10 * d), 0, 40 * s(10 * d)], [0, 80, 0], [40 * c(-25 * d), 80, 40 * s(-25 * d)]]);
      return M.state().list.map(x => [x.kind, x.value]); }""")
    want = [("dist", 50.0), ("ang3", 90.0), ("ang3", 30.0), ("ang2", 35.0), ("cobb", 35.0)]
    errs_ = [abs(v - w[1]) for (k, v), w in zip(r, want)]
    check(f"{tag} E: synthetic geometry: {r} vs {[w[1] for w in want]} (max error {max(errs_):.4f})", len(r) == 5 and max(errs_) < 0.5, errs)
    pg.evaluate("() => window.measureCtl.clear()")
    tap(pg, "#t-measure", phone)
    m, pts, surf = model_measure(pg, "dist", 2, phone, errs, tag)
    if m and all(surf):
        exp = dist(surf[0], surf[1])
        check(f"{tag} E: two taps on the model -> {m['label']} vs |P1 - P2| = {exp:.2f} mm of the tapped surface points", abs(m["value"] - exp) < 0.5 and exp > 5, errs)
    m, pts, surf = model_measure(pg, "ang3", 3, phone, errs, tag)
    if m and all(surf):
        exp = ang3(surf[0], surf[1], surf[2])
        check(f"{tag} E: three taps on the model -> {m['label']} vs {exp:.2f} deg from the tapped surface points", abs(m["value"] - exp) < 0.5, errs)
    tap(pg, "#ms-clear", phone)
    st = pg.evaluate("() => window.measureCtl.state().list.length")
    tap(pg, "#h-undo", phone)
    st2 = pg.evaluate("() => window.measureCtl.state().list.length")
    check(f"{tag} E: Clear removes them ({st} left), Undo brings them back ({st2})", st == 0 and st2 == 2, errs)
    pg.evaluate("() => { window.measureCtl.clear(); window.measureCtl.open(false); }")
    settle(pg)


def pane_measure(pg, sel, phone, errs, tag, name):
    """taps at known pixel offsets on a 2-D pane; expected values from the pane's own mm per css pixel. The pane's own ruler button
    opens the bar with Distance armed (a panel may cover the toolbar's Measure button)"""
    pg.evaluate("() => window.measureCtl.open(false)")
    tap(pg, f"{sel} .ms-pane-b", phone)
    g = pg.evaluate("""(sel) => { const e = document.querySelector(sel); if (!e) return null; const id = e.getAttribute('data-ms-id'); const S = window.NMSKMeasure.ctl.surfaces().find(s => s.id === id); if (!S) return null;
       const r = e.getBoundingClientRect(); return {id, x: Math.round(r.left + r.width * 0.3), y: Math.round(r.top + r.height * 0.35), w: r.width, h: r.height}; }""", sel)
    if not g:
        check(f"{tag} E: {name} registered as a measure surface", False, errs); return
    x0, y0 = g["x"], g["y"]
    ok = pg.evaluate("""([sel, pts]) => { const e = document.querySelector(sel); return pts.every(p => { const h = document.elementFromPoint(p[0], p[1]); return !!h && e.contains(h); }); }""", [sel, [[x0, y0], [x0 + 120, y0], [x0, y0 + 90], [x0 + 120, y0 + 46]]])
    check(f"{tag} E: {name}: the four tap points lie on the pane, nothing covers them", ok, errs)
    pts = {"A": (x0, y0), "B": (x0 + 120, y0), "C": (x0, y0 + 90)}
    import math
    D = (x0 + 120, round(y0 + 90 - 120 * math.tan(math.radians(20))))
    for k in "BC":
        tap_xy(pg, *pts[k], phone)
    tap(pg, '#ms-bar [data-ms="ang3"]', phone)
    for k in "CAB":
        tap_xy(pg, *pts[k], phone)
    for k in "ABC":                                   # the tool stays armed after a measurement: three more taps = another angle
        tap_xy(pg, *pts[k], phone)
    tap(pg, '#ms-bar [data-ms="cobb"]', phone)
    for p in (pts["A"], pts["B"], pts["C"], D):
        tap_xy(pg, *p, phone)
    st = pg.evaluate("() => window.measureCtl.state().list")
    sc = pg.evaluate("""(id) => { const L = window.measureCtl.state().list.filter(m => m.surface === id); if (!L.length) return null; const m = L[0];
       const p = m.pts; return Math.hypot(p[1][0] - p[0][0], p[1][1] - p[0][1]); }""", g["id"])
    # the pane's own scale: mm per css pixel, from its two tapped points B, C (150 css px apart) is what the tool measured; the
    # independent reference is the pane's documented scale (pixel size x raster size / css box), read here
    ref = pg.evaluate("""(sel) => { const e = document.querySelector(sel);
       if (e.classList.contains('img-view')) { const I = window.NMSKImaging; const v = I && I.views ? Object.values(I.views()).find(w => w.wrap === e) : null; return v && v.box ? v.px * v.W / v.box.s : null; }
       const U = window.NMSKUltrasound, v = U.views().find(w => w.wrap === e); if (!v) return null; const fr = U.frames()[v.idx]; return fr.plan.px / v.box.s; }""", sel)
    vals = [m for m in st if m["surface"] == g["id"]]
    if ref is None or len(vals) != 4:
        check(f"{tag} E: {name}: 4 measurements tapped ({len(vals)}) and the pane's scale readable ({ref})", False, errs); return
    exp = [("dist", 150 * ref), ("ang3", 90.0), ("ang3", math.degrees(math.atan2(90, 120))), ("cobb", 20.0)]
    errv = [abs(m["value"] - e[1]) for m, e in zip(vals, exp)]
    check(f"{tag} E: {name}: taps at known pixel offsets -> {[(m['kind'], round(m['value'], 2)) for m in vals]} vs {[(k, round(v, 2)) for k, v in exp]} ({ref:.4f} mm/px; max error {max(errv):.3f})",
          max(errv[:1]) < 0.5 and max(errv[1:]) < 0.5, errs)
    pg.evaluate("() => { window.measureCtl.clear(); window.measureCtl.open(false); }")
    settle(pg)


# ----------------------------------------------------------------------------------------------------------------------- F: reset
def part_f(pg, phone, s0, errs, tag):
    close_cards(pg, phone)
    tap(pg, "#t-cut", phone)                            # first (the labels switched on below may sit over the toolbar)
    pg.evaluate("""() => { const A = window.NMSKClinicalTool.api, L = A.list(); A.selection().toggle(L[3].id, true); window.xsecCtl.setPart([L[5].id], 'x');
       window.measureCtl.add('dist', '3d', [[0, 0, 0], [10, 0, 0]]); A.labels().setMode('vis'); }""")
    settle(pg)
    changed = pg.evaluate(SNAP)
    tap(pg, "#h-reset", phone)
    pg.wait_for_timeout(600)
    xs_idle(pg)
    a = pg.evaluate(SNAP)
    ja, j0 = json.loads(a), json.loads(s0)
    diff = [k for k in j0 if json.dumps(j0[k], sort_keys=True) != json.dumps(ja.get(k), sort_keys=True)]
    check(f"{tag} F: changes in 6 places -> Reset -> the page-start state exactly (differs: {diff})", changed != s0 and not diff, errs)
    tap(pg, "#h-undo", phone); pg.wait_for_timeout(400); xs_idle(pg)
    check(f"{tag} F: Undo after Reset brings every change back", pg.evaluate(SNAP) == changed, errs)
    tap(pg, "#h-reset", phone); pg.wait_for_timeout(500)


# --------------------------------------------------------------------------------------------------------------- G: US fascia
BAND = """async ([which]) => {
  const U = window.NMSKUltrasound, v = U.views()[U.state().sel], fr = U.frames()[v.idx], pl = fr.plan;
  function run(p) { const o = []; let a = -1; for (let i = 0; i < p.sheet.length; i++) { const on = p.sheet[i] >= 0; if (on && a < 0) a = i; if ((!on || i === p.sheet.length - 1) && a >= 0) { o.push({dep: p.y0 + (a + i) / 2 * p.px, w: (i - a) * p.px, st: p.sheet[a]}); a = -1; } } return o; }
  function band(p, dep, half) {           // the sheet's echo band: from the leading to the trailing -6 dB edge (amplitude half of its peak), within the sheet +- 0.8 mm
    const at = y => Math.round((y - p.y0) / p.px - 0.5), med = a => { const s = a.slice().sort((x, y) => x - y); return s[s.length >> 1]; };
    const bg = med(p.db.slice(Math.max(0, at(dep - 4)), Math.max(1, at(dep - 2))).concat(p.db.slice(at(dep + 2), at(dep + 4))));
    const i0 = Math.max(1, at(dep - half - 0.8)), i1 = Math.min(p.db.length - 2, at(dep + half + 0.8));
    let pk = -1e9; for (let i = i0; i <= i1; i++) if (p.db[i] > pk) pk = p.db[i];
    const th = pk - 6; let lo = -1, hi = -1;
    for (let i = i0; i <= i1; i++) if (p.db[i] >= th) { if (lo < 0) lo = i; hi = i; }
    const el = lo - (p.db[lo] - th) / Math.max(1e-6, p.db[lo] - p.db[lo - 1]), eh = hi + (p.db[hi] - th) / Math.max(1e-6, p.db[hi] - p.db[hi + 1]);
    return {w: (Math.min(eh, hi + 1) - Math.max(el, lo - 1)) * p.px, pk, bg};
  }
  function isolated(p, dep, half, pk) {    // nothing within 2.5 mm reaches the band's -6 dB level: the band is the sheet's own echo, not a neighbour's
    let mx = -1e9; for (let i = 0; i < p.db.length; i++) { const y = p.y0 + (i + 0.5) * p.px, d = Math.abs(y - dep); if (d > half + 0.7 && d < half + 2.5) mx = Math.max(mx, p.db[i]); }
    return mx < pk - 6;
  }
  let pick = null, b1 = null;
  for (let x = pl.xo0 + 6; x < pl.xo0 + fr.sim.Wo * pl.px - 6 && !pick; x += 1) {
    const p = U.profile(null, x, 'base'); if (!p) continue;
    const r = run(p).filter(q => q.dep > 4 && q.w < 2.0 && q.dep < fr.sim.Ho * p.px + p.y0 - 6);
    for (const q of r) { const mmq = U.sheetMm(q.st), bq = band(p, q.dep, mmq / 2); if (isolated(p, q.dep, mmq / 2, bq.pk)) { pick = {x, dep: q.dep, w: q.w, st: q.st}; b1 = bq; break; } }
  }
  if (!pick) return null;
  const mm = U.sheetMm(pick.st);
  const wr = v.wrap.getBoundingClientRect(), bx = v.box, sc = bx.s / pl.px;
  U.zoomTo(null, 4, (bx.x + (pick.x - pl.xo0) * sc) / wr.width, (bx.y + (pick.dep - pl.yo0) * sc) / wr.height);
  await new Promise(r => setTimeout(r, 120));
  const z = await U.zoomNow(); if (!z) return {pick, b1, z: null};
  const p4 = U.profile(null, pick.x, 'zoom'), b4 = p4 ? band(p4, pick.dep, mm / 2) : null;
  const hi = v.hi ? v.hi.getBoundingClientRect() : null;
  U.zoomTo(null, 1, 0.5, 0.5);
  return {pick, mm, b1, b4, z, base: pl.px, hiShown: !!hi && hi.width > 10, name: U.geo().names[pick.st]};
}"""


def place_on_fascia(pg):
    return pg.evaluate("""async () => { const U = window.NMSKUltrasound; await U.ready(); const g = U.geo(); let si = -1;
      for (let i = 0; i < g.n; i++) if (g.render[i] === 1 && /antebrachial|fascia lata|crural fascia|brachial fascia|deep fascia/i.test(g.names[i])) { si = i; break; }
      if (si < 0) return null; const b = g.bbox, c = [0, 1, 2].map(k => (b[6 * si + k] + b[6 * si + 3 + k]) / 2);
      for (const d of [[0, 0, -1], [-1, 0, 0], [0, 0, 1], [1, 0, 0]]) { const h = U.placeRay(c.map((x, k) => x - d[k] * 300), d); await U.idle();
        const fr = U.frames()[U.state().sel], pl = fr.plan; let hit = 0;
        for (let x = pl.xo0 + 6; x < pl.xo0 + fr.sim.Wo * pl.px - 6; x += 2) { const p = U.profile(null, x, 'base'); if (p && p.sheet.some((q, i) => q === si && i * p.px > 4)) hit++; }
        if (hit > 3) return {name: g.names[si], dir: d, hit}; }
      return {name: g.names[si], dir: null}; }""")


def part_g(pg, phone, where, errs, tag):
    pg.evaluate("() => window.NMSKUltrasound.set({speckle: false, noise: false, textures: false, reverb: false})")
    pg.evaluate("() => window.NMSKUltrasound.idle()")
    pl = place_on_fascia(pg)
    if not pl or not pl.get("dir"):
        check(f"{tag} G [{where}]: probe placed over a deep fascia ({pl})", False, errs); return
    r = pg.evaluate(BAND, ["x"])
    if not r or not r.get("b4"):
        check(f"{tag} G [{where}]: fascia band measured at 1x and 4x ({r})", False, errs); return
    w1, w4 = r["b1"]["w"], r["b4"]["w"]
    check(f"{tag} G [{where}]: '{r['name']}' (drawn {r['mm']:.2f} mm thick) on the image: band {w1:.2f} mm at 1x (pixel {r['base']:.3f} mm) vs {w4:.2f} mm at 4x "
          f"(re-simulated: pixel {r['z']['px']:.3f} mm, {r['z']['lines']} of {r['z']['nLt']} lines, {r['z']['ms']} ms, shown {r['hiShown']})",
          abs(w1 - w4) <= 0.35 and 0.5 <= w1 <= 2.0 and 0.5 <= w4 <= 2.0 and r["z"]["px"] < r["base"] * 0.8 and r["hiShown"], errs)
    pg.evaluate("() => window.NMSKUltrasound.set({speckle: true, textures: true, reverb: true})")


# ------------------------------------------------------------- I: thin sheets at their true thickness under every transform
SHEETS = """async ([cine]) => {
  const U = window.NMSKUltrasound, sleep = ms => new Promise(r => setTimeout(r, ms));
  function run(p) { const o = []; let a = -1; for (let i = 0; i <= p.sheet.length; i++) { const cur = i < p.sheet.length ? p.sheet[i] : -1; if (a >= 0 && cur !== p.sheet[a]) { o.push({dep: p.y0 + (a + i) / 2 * p.px, w: (i - a) * p.px, st: p.sheet[a], a, b: i}); a = -1; } if (cur >= 0 && a < 0) a = i; }
    return o.filter(q => q.a > 0 && q.b < p.sheet.length && p.sheet[q.a - 1] < 0 && p.sheet[q.b] < 0); }
  function samples(maxN) {        // columns across the image: each sheet crossing (one structure, air-free on both sides) -> drawn thickness along the beam vs the mesh's own
    const v = U.views()[U.state().sel], fr = U.frames()[v.idx], pl = fr.plan, out = [];   // expectation t / |m.b| (m = the sheet's local normal, b = the beam): the 1/cos widening only
    for (let x = pl.xo0 + 6; x < pl.xo0 + fr.sim.Wo * pl.px - 6 && out.length < maxN; x += 1.3) {
      const p = U.profile(null, x, 'base'); if (!p) continue;
      for (const q of run(p).filter(q => q.dep > 3 && q.dep < fr.sim.Ho * p.px + p.y0 - 4)) {
        const sa = U.sheetAt(null, x, q.dep, q.st); if (!sa || sa.dist > 0.6 || sa.alongBeam > 2.6) continue;
        out.push({x, dep: q.dep, st: q.st, lab: q.w, exp: sa.alongBeam, t: sa.t, obl: sa.obl, px: p.px}); x += 5; break;
      }
    }
    return out;
  }
  async function zoomed(o, k) { const v = U.views()[U.state().sel], pl = U.frames()[v.idx].plan, wr = v.wrap.getBoundingClientRect(), bx = v.box, sc = bx.s / pl.px;
    U.zoomTo(null, k, (bx.x + (o.x - pl.xo0) * sc) / wr.width, (bx.y + (o.dep - pl.yo0) * sc) / wr.height); await sleep(120);
    const z = await U.zoomNow(), p4 = z && U.profile(null, o.x, 'zoom'); U.zoomTo(null, 1, 0.5, 0.5);
    if (!p4) return null; const r = run(p4).filter(q => q.st === o.st).sort((m, n) => Math.abs(m.dep - o.dep) - Math.abs(n.dep - o.dep))[0];
    return r ? {lab: r.w, px: z.px} : null; }
  const res = [];
  for (const [nm, st, zk] of [["rotation 0, tilt 0", {rot: 0, mTilt: 0, depthCm: 5}, 4], ["rotation 45", {rot: 45}, 0], ["rotation 90", {rot: 90}, 4], ["tilt 15 (heel)", {rot: 0, mTilt: 15, mTiltDir: 90}, 0],
                              ["tilt 15 (rock)", {mTilt: 15, mTiltDir: 0}, 4], ["depth 3 cm", {mTilt: 0, depthCm: 3}, 0], ["depth 8 cm", {depthCm: 8}, 0]]) {
    U.set(st); await U.idle();
    const S = samples(6), z = zk && S.length ? await zoomed(S[0], zk) : null;
    res.push({nm, S, z, zk, zexp: S.length ? S[0].exp : null});
  }
  U.set({depthCm: 5, rot: 0, mTilt: 0}); await U.idle();
  if (cine) {                     // the live CINE tier (a coarser pixel): sampled while it plays
    U.set({cineMode: 'continuous'}); U.set({cine: true});
    let k = 0; while (!U.cineStatus().active && k++ < 100) await sleep(100);
    await sleep(1500);
    const base = U.frames()[U.state().sel].plan.px, S = U.cineStatus().active ? samples(6) : [];
    res.push({nm: "CINE (live tier)", S, z: null, cine: true, active: U.cineStatus().active, px: base});
    U.set({cine: false}); U.set({cineMode: 'step'}); await U.idle();
  }
  return res;
}"""


def part_i(pg, phone, where, errs, tag):
    pg.evaluate("() => { const U = window.NMSKUltrasound; U.set({speckle: false, noise: false, textures: false, reverb: false}); return U.idle(); }")
    pl = place_on_fascia(pg)
    if not pl or not pl.get("dir"):
        check(f"{tag} I [{where}]: probe placed over a deep fascia ({pl})", False, errs); return
    base_px = pg.evaluate("() => { const U = window.NMSKUltrasound; return U.frames()[U.state().sel].plan.px; }")
    res = pg.evaluate(SHEETS, [not phone])
    for r in res:
        S = r["S"]; rat = sorted(o["lab"] / o["exp"] for o in S); med = rat[len(rat) // 2] if rat else None
        desc = ", ".join(f"{o['lab']:.2f}/{o['exp']:.2f}" for o in S[:4])
        px = S[0]["px"] if S else 0
        extra = f" (pixel {px:.3f} mm vs the still frame's {base_px:.3f})" if r.get("cine") else f" (pixel {px:.3f} mm)"
        check(f"{tag} I [{where}] {r['nm']}: drawn sheet thickness along the beam / expected t/|m.b| (mm): {desc}; median ratio {med if med is None else round(med, 2)} over {len(S)} crossings{extra}",
              len(S) >= 2 and med is not None and 0.8 <= med <= 1.25 and (not r.get("cine") or (r.get("active") and px >= base_px * 0.999)), errs)
        if r.get("zk"):
            z = r.get("z")
            check(f"{tag} I [{where}] {r['nm']} at {r['zk']}x (re-simulated): {z and round(z['lab'], 2)} mm at pixel {z and round(z['px'], 3)} vs expected {r['zexp'] and round(r['zexp'], 2)}",
                  bool(z) and abs(z["lab"] - r["zexp"]) <= max(0.2, 0.2 * r["zexp"]) and z["px"] < px * 0.8, errs)
    pg.evaluate("() => window.NMSKUltrasound.set({speckle: true, textures: true, reverb: true})")


# ------------------------------------------------------------------------- J: probe placement and the rotate / tilt pad
def drag_path(pg, phone, a, b, n=10):
    if phone:
        cdp = pg.context.new_cdp_session(pg)
        cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": a[0], "y": a[1], "id": 1}]})
        for k in range(1, n + 1):
            f = k / n
            pg.wait_for_timeout(60)
            cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": a[0] + (b[0] - a[0]) * f, "y": a[1] + (b[1] - a[1]) * f, "id": 1}]})
        cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
        cdp.detach()
    else:
        pg.mouse.move(a[0], a[1]); pg.mouse.down()
        for k in range(1, n + 1):
            f = k / n
            pg.mouse.move(a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f); pg.wait_for_timeout(60)
        pg.mouse.up()
    pg.wait_for_timeout(400)


def part_j(pg, phone, where, errs, tag):
    U = "window.NMSKUltrasound"
    pg.evaluate(f"() => {{ {U}.set({{rot: 0, mTilt: 0, mTiltDir: 0}}); return {U}.idle(); }}")
    if pg.evaluate("() => { const t = document.getElementById('us-tab3d'); return !!t && t.getBoundingClientRect().width > 0; }"):
        tap(pg, "#us-tab3d button", phone); pg.wait_for_timeout(800)          # the US mode on a phone: its 3D tab shows the model with the probe
    pg.evaluate(f"() => {U}.idle()")
    pg.wait_for_timeout(600)
    cv = pg.evaluate("() => { const r = window.NMSKClinicalTool.api.canvas.getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; }")
    if cv[2] < 200 or cv[3] < 160:                                             # the US mode's 3-D thumbnail (phone): one tap on the skin there moves the probe
        P0 = pg.evaluate(f"() => {U}.state().P")
        q = None
        for fx, fy in ((0.3, 0.3), (0.7, 0.3), (0.3, 0.7), (0.7, 0.7), (0.5, 0.2), (0.5, 0.8)):
            c = [cv[0] + cv[2] * fx, cv[1] + cv[3] * fy]
            if pg.evaluate("([x, y]) => document.elementFromPoint(x, y) === window.NMSKClinicalTool.api.canvas", c) and pg.evaluate(f"([x, y]) => {U}.skinAt(x, y)", c):
                q = c; break
        if not q:
            check(f"{tag} J [{where}]: a skin point on the 3-D thumbnail ({[round(v) for v in cv]})", False, errs); return
        sk = pg.evaluate(f"([x, y]) => {U}.skinAt(x, y)", q)
        tap_xy(pg, q[0], q[1], phone); pg.evaluate(f"() => {U}.idle()"); pg.wait_for_timeout(300)
        st = pg.evaluate(f"() => {{ const s = {U}.state(), pi = {U}.probeInfo(); return {{P: s.P, gap: pi && pi.gap, pad: {U}.handles().shown}}; }}")
        off = sum((a - b) ** 2 for a, b in zip(st["P"], sk)) ** 0.5; moved = sum((a - b) ** 2 for a, b in zip(st["P"], P0)) ** 0.5
        check(f"{tag} J [{where}]: the 3-D thumbnail ({round(cv[2])}x{round(cv[3])} px): ONE tap on its skin moves the probe {moved:.1f} mm to the tapped skin point (off {off:.2f} mm), face on the skin "
              f"(gap {st['gap'] if st['gap'] is None else round(st['gap'], 2)} mm); no pad over the thumbnail ({not st['pad']}) -- the full-screen split (one tap) gives the drag + pad", moved > 1 and off < 1.5 and st["gap"] is not None and abs(st["gap"]) < 0.5 and not st["pad"], errs)
        return "thumb"
    h = pg.evaluate(f"() => {U}.handles()")
    tip = h.get("tip")
    ok_tip = bool(tip) and pg.evaluate("([x, y]) => document.elementFromPoint(x, y) === window.NMSKClinicalTool.api.canvas", tip)
    check(f"{tag} J [{where}]: the probe is on the 3-D view ({tip and [round(v) for v in tip]}) and the pad shows ({h.get('shown')})", ok_tip and h.get("shown"), errs)
    if not ok_tip:
        return
    target = None
    for dx, dy in ((0, 45), (0, -45), (45, 0), (-45, 0), (0, 25), (25, 0)):
        q = [tip[0] + dx, tip[1] + dy]
        if pg.evaluate("([x, y]) => document.elementFromPoint(x, y) === window.NMSKClinicalTool.api.canvas", q) and pg.evaluate(f"([x, y]) => {U}.skinAt(x, y)", q):
            target = q; break
    if not target:
        check(f"{tag} J [{where}]: a skin point next to the probe to drag it to", False, errs); return
    P0 = pg.evaluate(f"() => {U}.state().P"); eye0 = pg.evaluate(f"() => {U}.view().eye")
    hist0 = pg.evaluate("() => window.NMSKHistory.state().idx")
    drag_path(pg, phone, tip, target)
    pg.evaluate(f"() => {U}.idle()"); pg.wait_for_timeout(300)
    st = pg.evaluate(f"""([x, y]) => {{ const U = {U}, s = U.state(), sk = U.skinAt(x, y), fr = U.frames()[s.sel], pi = U.probeInfo();
        return {{P: s.P, N: s.N, sk, eye: U.view().eye, pfN0: fr && fr.pf.N0, gap: pi && pi.gap, moves: U.handles().moves}}; }}""", target)
    moved = sum((a - b) ** 2 for a, b in zip(st["P"], P0)) ** 0.5
    off = sum((a - b) ** 2 for a, b in zip(st["P"], st["sk"])) ** 0.5 if st["sk"] else 99
    cam = sum((a - b) ** 2 for a, b in zip(st["eye"], eye0)) ** 0.5
    nok = st["pfN0"] and sum(a * b for a, b in zip(st["pfN0"], st["N"])) > 0.9999
    check(f"{tag} J [{where}]: ONE {'touch' if phone else 'mouse'} drag from the probe slides it {moved:.1f} mm over the skin ({st['moves']} live moves) to the skin under the release point "
          f"(off by {off:.2f} mm), the axis on the skin normal ({nok}), the face on the skin (gap {st['gap'] if st['gap'] is None else round(st['gap'], 2)} mm), the camera did not orbit ({cam:.2f} mm)",
          moved > 3 and off < 1.5 and nok and st["gap"] is not None and abs(st["gap"]) < 0.5 and cam < 0.5 and st["moves"] >= 2, errs)
    def pad(sel):
        hit = pg.evaluate("(s) => { const b = document.querySelector(s); if (!b) return false; const r = b.getBoundingClientRect(); return r.width >= 32 && document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2) === b; }", sel)
        tap(pg, sel, phone); pg.evaluate(f"() => {U}.idle()"); pg.wait_for_timeout(200)
        return hit
    r0 = pg.evaluate(f"() => {U}.state().rot")
    h1 = pad("#us-h-rr"); r1 = pg.evaluate(f"() => {U}.state().rot")
    h2 = pad("#us-h-th")
    t1 = pg.evaluate(f"""() => {{ const U = {U}, s = U.state(), fr = U.frames()[s.mode === 'star' ? 0 : s.sel], d = fr.pf.N.reduce((a, v, i) => a + v * s.N[i], 0);
        return {{tilt: s.mTilt, dir: s.mTiltDir, ang: Math.acos(Math.min(1, d)) * 180 / Math.PI, mode: s.mode}}; }}""")
    h3 = pad("#us-h-tm")
    t2 = pg.evaluate(f"() => {{ const s = {U}.state(); return {{tilt: s.mTilt, dir: s.mTiltDir}}; }}")
    h4 = pad("#us-h-t0"); h5 = pad("#us-h-rl")
    t3 = pg.evaluate(f"() => {{ const s = {U}.state(); return {{tilt: s.mTilt, rot: s.rot}}; }}")
    check(f"{tag} J [{where}]: pad taps (each one tap, uncovered: {[h1, h2, h3, h4, h5]}): rotate {r0} -> {r1} deg; heel tilt -> {t1['tilt']} deg toward {t1['dir']} "
          f"(the {t1['mode']} centre image's axis leans {t1['ang']:.2f} deg); + marker-side tilt -> {t2['tilt']} deg toward {t2['dir']}; upright + rotate back -> tilt {t3['tilt']}, rotation {t3['rot']}",
          all([h1, h2, h3, h4, h5]) and (r0 - r1) % 360 == 15 and t1["tilt"] == 5 and t1["dir"] == 90 and abs(t1["ang"] - 5) < 0.2 and t2["tilt"] == 7 and 130 <= t2["dir"] <= 140 and t3["tilt"] == 0 and t3["rot"] == r0, errs)
    print(f"  steps [{where}]: move the probe = 1 drag (before: 'Place on skin' + a tap, per move); rotate 15 deg = 1 tap (before: a slider / mode-only button); "
          f"tilt 5 deg = 1 tap in any mode (before: mode 2 + a slider); history entries during the test: {pg.evaluate('() => window.NMSKHistory.state().idx') - hist0}", flush=True)


# ---------------------------------------------------------------------- K: the transducer model per type, seated on the skin
def part_k(pg, phone, where, errs, tag):
    U = "window.NMSKUltrasound"
    for pr in ("linear", "convex", "sector"):
        r = pg.evaluate(f"async (p) => {{ const U = {U}; U.set({{probe: p}}); await U.idle(); return {{i: U.probeInfo(), ov: U.overlayItems()}}; }}", pr)
        i = r["i"]; ov = dict(r["ov"] or [])
        if pr == "linear":
            fx, fz = i["arrayW"] + 5, 13
        elif pr == "convex":
            import math
            fx, fz = 2 * (i["R"] * math.sin(i["arrayW"] / (2 * i["R"])) + 3), 20
        else:
            fx, fz = i["arrayW"] + 8, 20
        check(f"{tag} K [{where}] {pr}: footprint {i['footX']:.1f} x {i['footZ']:.0f} mm (expected {fx:.1f} x {fz}), housing {i['height']:.0f} mm, face on the skin "
              f"(gap {i['gap'] if i['gap'] is None else round(i['gap'], 3)} mm, seat {i['ysk']:.2f} mm), marker ridge on the image-left end ({i['markerLeft']}, u {i['markerU']:.1f} mm), drawn ({ov.get('probe')} / {ov.get('marker')} triangles)",
              abs(i["footX"] - fx) < 0.05 and i["footZ"] == fz and i["gap"] is not None and abs(i["gap"]) < 0.5 and i["markerLeft"] and ov.get("probe", 0) > 100 and ov.get("marker", 0) > 0, errs)
    pg.evaluate(f"async () => {{ {U}.set({{probe: 'linear'}}); await {U}.idle(); }}")


# ------------------------------------------------------------------------------------- L: fibres per bundle (Q281 split)
def _bandp(row, name):
    words = [w for w in name.lower().replace("(", " ").replace(")", " ").split() if w not in ("part", "head", "and", "belly")]
    hit = [c for c in row.get("c", []) if any(w in c[0].lower() for w in words)]
    ws = sum(max(1, c[2]) for c in hit)
    return sum(c[1] * max(1, c[2]) for c in hit) / ws if ws else row.get("p", 0)


BUNDLES = {"deltoid": ("deltoid.*_r$|^deltoid_r$", 3), "pectoralis_major": ("pectoralis_major.*_r$|^pectoralis_major_r$", 3),
           "trapezius": ("^trapezius_r$", 3), "rectus_femoris": ("^rectus_femoris(_reflected_head)?_r$", 2)}


def part_l(pg, phone, where, errs, tag):
    import math
    A = json.loads((HERE.parents[2] / "clinical" / "data" / "ultrasound_tissues.json").read_text(encoding="utf-8"))["architecture"]["muscles"]
    U = "window.NMSKUltrasound"
    pg.wait_for_function("() => { const p = window.__partsCtl; return !!p && p.anchors && p.anchors('deltoid', null) !== null; }", timeout=60000)
    for key, (rx, nb) in BUNDLES.items():
        B = [b for b in pg.evaluate(f"(r) => {U}.bundles(r)", rx) if "zfill" not in b["id"]]
        ang = lambda a, b: math.degrees(math.acos(min(1, abs(sum(x * y for x, y in zip(a, b))))))
        pairs = [round(ang(B[i]["a"], B[j]["a"])) for i in range(len(B)) for j in range(i + 1, len(B)) if B[i].get("a") and B[j].get("a")]
        pe = [(b["name"], round(b["pDeg"], 2), round(_bandp(A[key], b["name"]), 2)) for b in B]
        # the image's fibre direction inside each bundle, and the 3-D fibre lines
        f = pg.evaluate(f"""(B) => {{ const U = {U}; return B.map(b => {{ const c = U.bandCentre(b.sid, b.band), r = c && U.fibreAt(b.sid, c);
            if (!r) return null; const d = Math.abs(r.f[0] * b.a[0] + r.f[1] * b.a[1] + r.f[2] * b.a[2]); return {{band: r.band, ang: Math.acos(Math.min(1, d)) * 180 / Math.PI}}; }}); }}""", B)
        lines = pg.evaluate(f"(s) => {U}.fibreLines(s)", sorted({b["sid"] for b in B}))
        lok = []
        for b in B:
            L = [l for l in lines if l["sid"] == b["sid"] and (b["band"] < 0 or l["band"] == b["band"])]
            dev = [abs(ang(l["f"], b["a"]) - b["pDeg"]) for l in L]
            lok.append((len(L), round(max(dev), 2) if dev else None))
        good = (len(B) == nb and all(p > 15 for p in pairs) and all(abs(x[1] - x[2]) <= 1 for x in pe)
                and all(q and (B[i]["band"] < 0 or q["band"] == B[i]["band"]) and abs(q["ang"] - B[i]["pDeg"]) <= 1 for i, q in enumerate(f))
                and all(n > 0 and d is not None and d <= 1 for n, d in lok))
        check(f"{tag} L [{where}] {key}: {len(B)} bundles {[x[0] for x in pe]} on {sorted({b['id'] for b in B})}; axes pairwise {pairs} deg apart "
              f"({sorted({b.get('src') for b in B})}); pennation {[(x[1], x[2]) for x in pe]} (drawn, cited); image fibre vs bundle axis {[q and round(q['ang'], 2) for q in f]} deg; "
              f"3-D lines per bundle (count, max deviation) {lok}", good, errs)


def run(page_dir: Path, errs: list):
    html = V.html_of(page_dir); srv, port = V.serve(page_dir)
    zan = "zan" in page_dir.name
    try:
        with sync_playwright() as pl:
            b = pl.chromium.launch(args=V.LAUNCH_ARGS, executable_path="/opt/pw-browsers/chromium")
            vps = [((1400, 900), False), ((390, 844), True)]
            if os.environ.get("Q294_ONLY") in ("desktop", "phone"):
                vps = [v for v in vps if v[1] == (os.environ["Q294_ONLY"] == "phone")]
            for (w, h), phone in vps:
                ctx = b.new_context(viewport={"width": w, "height": h}, has_touch=phone, is_mobile=phone)
                pg = ctx.new_page(); perr = []
                pg.set_default_timeout(T)
                pg.on("pageerror", lambda e: perr.append(str(e)))
                pg.route("**/*", V.route)
                tag = f"{page_dir.name}@{w}"
                print(f"=== {tag} ===", flush=True)
                pg.goto(f"http://127.0.0.1:{port}/{html}", wait_until="load", timeout=120000)
                V.ready(pg)
                pg.wait_for_function("() => window.NMSKHistory && window.NMSKHistory.active() && window.measureCtl && window.partSlices", timeout=60000)
                pg.evaluate("() => { const A = window.NMSKClinicalTool.api; if (A.stopMotion) A.stopMotion(); }")
                s0 = pg.evaluate(SNAP)
                parts = os.environ.get("Q294_PARTS", "ABCDEFGIJKL")
                for P, fn in (("A", lambda: part_a(pg, phone, errs, tag)), ("B", lambda: part_b(pg, phone, zan, errs, tag)), ("C", lambda: part_c(pg, phone, zan, errs, tag)),
                              ("D", lambda: part_d(pg, phone, errs, tag)), ("E", lambda: part_e(pg, phone, errs, tag)), ("F", lambda: part_f(pg, phone, s0, errs, tag))):
                    if P in parts:
                        if os.environ.get("Q294_SHOT"):
                            pg.screenshot(path=f"{os.environ['Q294_SHOT']}/{page_dir.name}_{w}_{P}.png")
                        try:
                            fn()
                        except Exception as ex:  # noqa: BLE001
                            check(f"{tag} {P}: raised {type(ex).__name__}: {str(ex)[:300]}", False, errs)
                        sys.stdout.flush()
                if any(x in parts for x in "EGIJKL"):
                    try:
                        pg.evaluate("() => window.NMSKUltrasound.ready()")
                        if not phone:
                            tap(pg, "#t-ultrasound", phone); pg.wait_for_timeout(900)
                            pg.evaluate("() => window.NMSKUltrasound.idle()")
                            if "E" in parts:
                                pane_measure(pg, "#us-root .us-view.us-act", phone, errs, tag, "image pane (simulated echo)")
                            if "G" in parts:
                                part_g(pg, phone, "panel", errs, tag)
                            for P2, fn2 in (("I", part_i), ("K", part_k), ("L", part_l), ("J", part_j)):
                                if P2 in parts:
                                    try:
                                        fn2(pg, phone, "panel", errs, tag)
                                    except Exception as ex:  # noqa: BLE001
                                        check(f"{tag} {P2}: raised {type(ex).__name__}: {str(ex)[:300]}", False, errs)
                            if "G" in parts or "J" in parts:
                                pg.evaluate("() => { const U = window.NMSKUltrasound; U.set({cine: false}); }")
                                if pg.evaluate("() => !!document.querySelector('#us-root [data-fs]')"):
                                    pg.evaluate("() => document.querySelector('#us-root [data-fs]').click()")
                                    pg.wait_for_function("() => document.body.classList.contains('us-fs')", timeout=T)
                                    pg.wait_for_timeout(1500)
                                    pg.evaluate("() => { const U = window.NMSKUltrasound; U.set({cine: false}); return U.idle(); }")
                                    if "G" in parts:
                                        part_g(pg, phone, "full-screen split", errs, tag)
                                    if "J" in parts:
                                        try:
                                            part_j(pg, phone, "full-screen split", errs, tag)
                                        except Exception as ex:  # noqa: BLE001
                                            check(f"{tag} J: raised {type(ex).__name__}: {str(ex)[:300]}", False, errs)
                                    pg.keyboard.press("Escape"); pg.wait_for_timeout(800)
                                    if pg.evaluate("() => document.body.classList.contains('us-fs')"):
                                        tap(pg, ".fs-x", phone)
                                    pg.wait_for_function("() => !document.body.classList.contains('us-fs')", timeout=60000)
                                else:
                                    check(f"{tag} G: the full-screen button exists", False, errs)
                        else:
                            if pg.evaluate("() => { const s = document.getElementById('mode-switch'); return !s || s.hidden; }"):
                                tap(pg, "#t-mode", phone); pg.wait_for_timeout(400)
                            tap(pg, '.mw-tile[data-mode="us"]', phone); pg.wait_for_timeout(1500)
                            pg.evaluate("() => window.NMSKUltrasound.idle()")
                            for P2, fn2 in (("I", part_i), ("K", part_k), ("L", part_l), ("J", part_j)):
                                if P2 in parts:
                                    try:
                                        fn2(pg, phone, "US mode", errs, tag)
                                    except Exception as ex:  # noqa: BLE001
                                        check(f"{tag} {P2}: raised {type(ex).__name__}: {str(ex)[:300]}", False, errs)
                            if "G" in parts:
                                part_g(pg, phone, "US mode", errs, tag)
                            if "J" in parts and pg.evaluate("() => !!document.querySelector('.mm-bar .mm-tog[aria-label]')"):
                                try:                                               # the clean full-screen split from the US mode (one tap): the big 3-D half
                                    pg.evaluate("() => window.NMSKUltrasound.set({cine: false})")
                                    tap(pg, ".mm-bar .mm-tog[aria-label]", phone)
                                    pg.wait_for_function("() => document.body.classList.contains('us-fs')", timeout=T); pg.wait_for_timeout(1500)
                                    pg.evaluate("() => { const U = window.NMSKUltrasound; U.set({cine: false}); return U.idle(); }")
                                    part_j(pg, phone, "US mode full-screen split", errs, tag)
                                    if pg.evaluate("() => document.body.classList.contains('us-fs')"):
                                        tap(pg, ".fs-x", phone)
                                    pg.wait_for_function("() => !document.body.classList.contains('us-fs')", timeout=60000)
                                except Exception as ex:  # noqa: BLE001
                                    check(f"{tag} J [US mode full-screen split]: raised {type(ex).__name__}: {str(ex)[:300]}", False, errs)
                                before = pg.evaluate("() => window.NMSKUltrasound.state().gain")
                                pg.evaluate("() => window.NMSKUltrasound.set({gain: 7})")
                                tap(pg, "#mb-reset", phone); pg.wait_for_timeout(600)
                                st = pg.evaluate("() => ({gain: window.NMSKUltrasound.state().gain, mode: document.body.classList.contains('mode-us')})")
                                check(f"{tag} F: in the US mode the bar's Reset restores the mode's controls (gain 7 -> {st['gain']}) without leaving it ({st['mode']})", st["gain"] == 0 and st["mode"], errs)
                    except Exception as ex:  # noqa: BLE001
                        check(f"{tag} G: raised {type(ex).__name__}: {str(ex)[:300]}", False, errs)
                if not phone and "E" in parts and not zan:
                    try:
                        if pg.evaluate("() => !!document.getElementById('t-imaging')"):
                            if pg.evaluate("() => window.NMSKUltrasound && window.NMSKUltrasound.isOpen()"):
                                pg.evaluate("() => window.NMSKUltrasound.close()"); pg.wait_for_timeout(800)
                            if os.environ.get("Q294_SHOT"):
                                pg.screenshot(path=f"{os.environ['Q294_SHOT']}/{page_dir.name}_{w}_CT.png")
                            tap(pg, "#t-imaging", phone); pg.wait_for_timeout(1500)
                            pg.wait_for_function("() => Array.from(document.querySelectorAll('.img-view')).some(v => v.getBoundingClientRect().width > 100)", timeout=T)
                            pg.wait_for_timeout(2500)
                            pane_measure(pg, ".img-view[data-view]", phone, errs, tag, "CT pane")
                    except Exception as ex:  # noqa: BLE001
                        check(f"{tag} E: CT pane raised {type(ex).__name__}: {str(ex)[:300]}", False, errs)
                check(f"{tag} H: 0 page errors ({perr[:3]})", not perr, errs)
                ctx.close()
            b.close()
    finally:
        srv.terminate()


def main():
    errs = []
    for d in sys.argv[1:]:
        run(Path(d), errs)
    print(f"\n{'ALL OK' if not errs else str(len(errs)) + ' FAIL'}")
    return 1 if errs else 0


if __name__ == "__main__":
    raise SystemExit(main())
