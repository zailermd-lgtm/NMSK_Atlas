#!/usr/bin/env python3
"""Q290: real headless-Chromium check of two-finger zoom on every surface, on locally served template-only rebuilt pages.

Phone 390x844 (has_touch, is_mobile): REAL multi-touch -- CDP Input.dispatchTouchEvent with two touch points (touchStart, a
series of touchMove, touchEnd), so the page sees the same pointer events a phone sends.
Desktop 1400x900: ctrl+wheel (what a trackpad pinch sends) through Playwright's mouse with Control held.

A  3-D, both engines (OWN_DIR = own engine, e.g. Imaging F; ZAN_DIR = Z engine, e.g. Base M):
   pinch zoom-in: the point on the focal plane first under the fingers' midpoint is still under it (engine's own toScreen,
   <= 3 px) and the distance fell by the spread ratio; two-finger drag: the point under the fingers moves with them (<= 3 px);
   a combined pinch-out + drag likewise; the "1:1" chip shows; every toolbar button has the same rectangle, is still the
   element on top at its centre, and a real tap on the Cut button still toggles it; tapping the chip restores the camera;
   a double-tap on empty space restores it too
B  desktop, both engines: ctrl+wheel keeps the point under the cursor (<= 3 px); a plain wheel still zooms about the centre
   (target unchanged, distance x1.11 -- the old mouse behaviour); the chip resets
C  US full-screen split (own page, phone, "US אבחנתי" mode): the image under the fingers stays under them while zooming and
   panning (the <img> canvas rectangle, <= 3 px), the in-image watermark stays drawn at its own size on the visible part,
   ✕ / ⋯ unmoved and on top, the CINE play state not toggled by the pinch, chip and double-tap reset; the 3-D half zooms to
   the point too
D  CT slice pane (own page, phone): the anatomy point under the fingers (from the rendered view's own plane frame) stays under
   them after zoom and pan (<= 3 px), the field of view shrank by the spread ratio and the view was re-rendered at it (crisp
   labels), the crosshair did not jump on the first finger, the chip restores the field of view; desktop ctrl+wheel too
E  cross-section multi-slice (Z page, phone): with Cut + the multi-slice stack on, a pinch on the stack zooms to the point,
   the stack stays on with its slices, the Cut panel is unmoved
F  native page zoom (Z page, phone, informational where headless supports Input.synthesizePinchGesture): a pinch on a panel
   zooms the page; the main toolbar is drawn at 1:1 on the visible part; the page chip offers 1:1
G  0 page errors

    python3 scripts/anatomy/q290/verify_q290.py OWN_DIR ZAN_DIR
"""
from __future__ import annotations

import math
import os
import time
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "q283"))
sys.path.insert(0, str(HERE.parent / "q289"))
import verify_q283 as V  # noqa: E402
import verify_q289 as V9  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

check = V.check
TOL = 3.0

FOCAL = """([x, y]) => { const a = window.NMSKClinicalTool.api, v = a.view(), r = a.ray({clientX: x, clientY: y}), n = v.dir, t = v.target;
  const den = n[0] * r.d[0] + n[1] * r.d[1] + n[2] * r.d[2], s = ((t[0] - r.o[0]) * n[0] + (t[1] - r.o[1]) * n[1] + (t[2] - r.o[2]) * n[2]) / den;
  return [r.o[0] + s * r.d[0], r.o[1] + s * r.d[1], r.o[2] + s * r.d[2]]; }"""
CAM = """() => { const v = window.NMSKClinicalTool.api.view(); return {eye: v.eye, target: v.target, dist: Math.hypot(v.eye[0] - v.target[0], v.eye[1] - v.target[1], v.eye[2] - v.target[2])}; }"""
FRAMES = "() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(() => requestAnimationFrame(r))))"
MENUS = """(sels) => { const out = []; sels.forEach(sel => document.querySelectorAll(sel).forEach(e => { if (out.some(o => o.el === e)) return; const r = e.getBoundingClientRect();
    if (r.width < 4 || r.height < 4 || r.bottom < 0 || r.top > innerHeight || r.right < 0 || r.left > innerWidth) return;
    const h = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2); if (!h || !(h === e || e.contains(h))) return;
    if (!e.hasAttribute('data-q290m')) e.setAttribute('data-q290m', String(window.__q290n = (window.__q290n || 0) + 1));
    out.push({el: e, id: e.id || e.className || e.tagName, m: e.getAttribute('data-q290m'), r: [r.left, r.top, r.width, r.height]}); })); return out.map(o => ({id: o.id, m: o.m, r: o.r})); }"""
MENUS_AGAIN = """(prev) => prev.map(p => { const e = document.querySelector('[data-q290m="' + p.m + '"]');
    if (!e) return {id: p.id, ok: false, why: 'gone'}; const r = e.getBoundingClientRect(), h = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
    const same = [r.left, r.top, r.width, r.height].every((v, i) => Math.abs(v - p.r[i]) < 0.6); return {id: p.id, ok: same && !!h && (h === e || e.contains(h)), r: [r.left, r.top, r.width, r.height]}; })"""
PANEL = """(s) => { const p = document.querySelector(s), r = p.getBoundingClientRect(), b = Array.from(p.querySelectorAll('button')).filter(e => e.getBoundingClientRect().width > 0);
    let el = p, scaled = false; while (el && el !== document.documentElement) { const tf = getComputedStyle(el).transform; if (tf && tf !== 'none') scaled = true; el = el.parentElement; }
    return {r: [r.left, r.top, r.width, r.height].map(Math.round), n: b.length, sizes: b.map(e => { const q = e.getBoundingClientRect(); return Math.round(q.width) + 'x' + Math.round(q.height); }).join(','), scaled}; }"""
CHIP = """(sel) => { const a = sel ? document.querySelector(sel) : null, ar = a ? a.getBoundingClientRect() : null;
    const c = Array.from(document.querySelectorAll('.pz-chip:not(.pz-native)')).filter(e => { if (e.hidden || e.style.visibility === 'hidden') return false; if (!ar) return true;
      const r = e.getBoundingClientRect(), x = r.left + r.width / 2, y = r.top + r.height / 2; return x >= ar.left && x <= ar.right && y >= ar.top && y <= ar.bottom; }); if (!c.length) return null;
    const e = c[0], r = e.getBoundingClientRect(), h = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
    return {txt: e.textContent, x: r.left + r.width / 2, y: r.top + r.height / 2, w: r.width, h: r.height, top: !!h && (h === e || e.contains(h)), n: c.length}; }"""


class Touch:
    """two-finger gestures and taps through CDP Input.dispatchTouchEvent (real touch input, not synthetic DOM events)"""

    def __init__(self, pg):
        self.pg = pg
        self.cdp = pg.context.new_cdp_session(pg)

    def _send(self, kind, pts, ts=None):
        p = {"type": kind, "touchPoints": [{"x": x, "y": y, "id": i, "radiusX": 4, "radiusY": 4, "force": 1} for i, (x, y) in enumerate(pts)]}
        if ts is not None:
            p["timestamp"] = ts
        self.cdp.send("Input.dispatchTouchEvent", p)

    def two(self, a0, b0, a1, b1, steps=10):
        self._send("touchStart", [a0, b0])
        for k in range(1, steps + 1):
            t = k / steps
            self._send("touchMove", [(a0[0] + (a1[0] - a0[0]) * t, a0[1] + (a1[1] - a0[1]) * t), (b0[0] + (b1[0] - b0[0]) * t, b0[1] + (b1[1] - b0[1]) * t)])
        self._send("touchEnd", [])
        self.pg.wait_for_timeout(450)          # past the "just pinched" guard (400 ms)

    def pinch(self, m, half0, half1, move=(0, 0), steps=10):
        """fingers horizontally either side of m, spread half0 -> half1, the midpoint travelling by `move`"""
        m1 = (m[0] + move[0], m[1] + move[1])
        self.two((m[0] - half0, m[1]), (m[0] + half0, m[1]), (m1[0] - half1, m1[1]), (m1[0] + half1, m1[1]), steps)

    def tap(self, x, y, ts=None):
        self._send("touchStart", [(x, y)], ts); self._send("touchEnd", [], None if ts is None else ts + 0.04)

    def dbl(self, x, y):
        """two taps 150 ms apart by their input timestamps: under software rendering the page is busy for seconds after the
        first tap (CDP waits for it), as a real phone's queued touches would be -- they carry their own hardware times"""
        t0 = time.time()
        self.tap(x, y, t0); self.tap(x, y, t0 + 0.15)


def frames(pg):
    pg.evaluate(FRAMES); pg.wait_for_timeout(150); pg.evaluate(FRAMES)


def err_px(pg, P, m):
    s = pg.evaluate("(p) => window.NMSKClinicalTool.api.toScreen(p)", P)
    return math.hypot(s[0] - m[0], s[1] - m[1]) if s else 1e9


def canvas_sel(pg):
    return "#view" if pg.evaluate("() => window.NMSKClinicalTool.api.kind") == "webgl" else "#stage canvas"


def on_canvas(pg, sel, pts):
    return pg.evaluate("([s, pts]) => { const c = document.querySelector(s); return pts.every(p => { const e = document.elementFromPoint(p[0], p[1]); return e === c; }); }", [sel, pts])


def free_mid(pg, sel, half, move=(0, 0)):
    """a midpoint where both fingers (start and end of the gesture) land on the 3-D canvas itself, not on a panel over it"""
    return pg.evaluate("""([s, h, mv]) => { const c = document.querySelector(s), r = c.getBoundingClientRect();
        const ok = p => document.elementFromPoint(p[0], p[1]) === c;
        for (let fy = 0.5; fy > 0.08; fy -= 0.04) for (const fx of [0.5, 0.45, 0.55, 0.4, 0.6]) {
          const m = [Math.round(r.left + r.width * fx), Math.round(r.top + r.height * fy)];
          const pts = [[m[0] - h, m[1]], [m[0] + h, m[1]], [m[0] - 45, m[1]], [m[0] + 45, m[1]], [m[0] - h + mv[0], m[1] + mv[1]], [m[0] + h + mv[0], m[1] + mv[1]], m];
          if (pts.every(ok)) return m; }
        return null; }""", [sel, half, list(move)])


def same_cam(a, b, tol=1e-3):
    return abs(a["dist"] - b["dist"]) <= tol * a["dist"] and all(abs(x - y) <= tol * a["dist"] for x, y in zip(a["target"], b["target"]))


MENU_SELS = ["#tools .tool", "#tools button", "#topright .pill", "#mode-bar button", "#t-layout", "#t-lay3"]


def section_A(pg, T, errs, tag):
    sel = canvas_sel(pg)
    r = pg.eval_on_selector(sel, "e => { const b = e.getBoundingClientRect(); return [b.left, b.top, b.width, b.height]; }")
    m = (r[0] + r[2] * 0.42, r[1] + r[3] * 0.52)
    check(f"{tag} A: the fingers land on the 3-D canvas ({sel}, midpoint {m[0]:.0f},{m[1]:.0f})", on_canvas(pg, sel, [(m[0] - 150, m[1]), (m[0] + 150, m[1]), (m[0] - 50, m[1]), (m[0] + 50, m[1])]), errs)
    menus = pg.evaluate(MENUS, MENU_SELS)
    c0 = pg.evaluate(CAM)
    P0 = pg.evaluate(FOCAL, list(m))
    T.pinch(m, 50, 150); frames(pg)
    c1 = pg.evaluate(CAM); e = err_px(pg, P0, m)
    check(f"{tag} A: pinch x3 keeps the point under the fingers ({e:.2f} px) and the distance fell {c0['dist'] / c1['dist']:.2f}x", e <= TOL and abs(c0["dist"] / c1["dist"] - 3) < 0.15, errs)
    P1 = pg.evaluate(FOCAL, list(m)); m2 = (m[0] + 40, m[1] + 60)
    T.pinch(m, 60, 60, move=(40, 60)); frames(pg)
    e = err_px(pg, P1, m2)
    check(f"{tag} A: two-finger drag moves the anatomy with the fingers ({e:.2f} px)", e <= TOL, errs)
    P2 = pg.evaluate(FOCAL, list(m2)); m3 = (m2[0] - 30, m2[1] - 40); d2 = pg.evaluate(CAM)["dist"]
    T.pinch(m2, 100, 70, move=(-30, -40)); frames(pg)
    e = err_px(pg, P2, m3); d3 = pg.evaluate(CAM)["dist"]
    check(f"{tag} A: pinch-out while dragging keeps the point under the fingers ({e:.2f} px, distance x{d3 / d2:.2f})", e <= TOL and abs(d3 / d2 - 100 / 70) < 0.08, errs)
    ch = pg.evaluate(CHIP, sel)
    check(f"{tag} A: the '1:1' chip is shown while zoomed and is on top ({ch and ch['txt']})", ch and ch["top"] and "1:1" in ch["txt"] and "×" in ch["txt"], errs)
    again = pg.evaluate(MENUS_AGAIN, menus)
    bad = [a for a in again if not a["ok"]]
    check(f"{tag} A: {len(menus)} toolbar buttons unmoved, unscaled and on top after the gestures ({bad[:2]})", len(menus) >= 3 and not bad, errs)
    was = pg.get_attribute("#t-cut", "aria-pressed")
    V.tap(pg, "#t-cut", True); pg.wait_for_timeout(600)
    now = pg.get_attribute("#t-cut", "aria-pressed")
    V.tap(pg, "#t-cut", True); pg.wait_for_timeout(600)
    check(f"{tag} A: a real tap on the Cut button still works while zoomed ({was} -> {now} -> {pg.get_attribute('#t-cut', 'aria-pressed')})", was != now and pg.get_attribute("#t-cut", "aria-pressed") == was, errs)
    ch = pg.evaluate(CHIP, sel)
    T.tap(ch["x"], ch["y"]); pg.wait_for_timeout(300); frames(pg)
    c2 = pg.evaluate(CAM)
    check(f"{tag} A: tapping the chip returns the camera to before the pinch (distance {c2['dist']:.1f} vs {c0['dist']:.1f}) and hides the chip", same_cam(c0, c2) and pg.evaluate(CHIP, sel) is None, errs)
    T.pinch((r[0] + r[2] / 2, r[1] + r[3] / 2), 60, 90); frames(pg)
    zoomed = pg.evaluate(CHIP, sel) is not None
    ex = (r[0] + r[2] * 0.05, r[1] + r[3] * 0.62)
    T.dbl(*ex); pg.wait_for_timeout(400); frames(pg)
    c3 = pg.evaluate(CAM)
    check(f"{tag} A: double-tap on empty space returns to 1:1 (zoomed before: {zoomed}; distance {c3['dist']:.1f} vs {c0['dist']:.1f})", zoomed and same_cam(c0, c3) and pg.evaluate(CHIP, sel) is None, errs)
    if pg.evaluate(CHIP, sel):                                        # leave the view at 1:1 for the next section
        ch = pg.evaluate(CHIP, sel); T.tap(ch["x"], ch["y"]); pg.wait_for_timeout(300)


def section_B(pg, errs, tag):
    sel = canvas_sel(pg)
    r = pg.eval_on_selector(sel, "e => { const b = e.getBoundingClientRect(); return [b.left, b.top, b.width, b.height]; }")
    m = (r[0] + r[2] * 0.36, r[1] + r[3] * 0.44)
    c0 = pg.evaluate(CAM); P0 = pg.evaluate(FOCAL, list(m))
    pg.mouse.move(*m); pg.keyboard.down("Control")
    for _ in range(4):
        pg.mouse.wheel(0, -30); pg.wait_for_timeout(120)
    pg.keyboard.up("Control"); frames(pg)
    c1 = pg.evaluate(CAM); e = err_px(pg, P0, m)
    check(f"{tag} B: ctrl+wheel (trackpad pinch) zooms to the cursor ({e:.2f} px, distance x{c1['dist'] / c0['dist']:.2f})", e <= TOL and c1["dist"] < c0["dist"] * 0.75, errs)
    t1 = c1["target"]
    pg.mouse.wheel(0, 100); pg.wait_for_timeout(300); frames(pg)
    c2 = pg.evaluate(CAM)
    check(f"{tag} B: a plain wheel still zooms about the centre as before (target unchanged, distance x{c2['dist'] / c1['dist']:.3f})",
          all(abs(a - b) < 1e-3 * c1["dist"] for a, b in zip(t1, c2["target"])) and c2["dist"] > c1["dist"], errs)
    ch = pg.evaluate(CHIP, sel)
    check(f"{tag} B: the chip is shown ({ch and ch['txt']})", ch and ch["top"], errs)
    pg.mouse.click(ch["x"], ch["y"]); pg.wait_for_timeout(300); frames(pg)
    check(f"{tag} B: clicking the chip restores the view", same_cam(c0, pg.evaluate(CAM)) and pg.evaluate(CHIP, sel) is None, errs)


US_IMG = """() => { const U = window.NMSKUltrasound, v = U.views()[U.state().sel]; const a = v.img.getBoundingClientRect(), w = v.wrap.getBoundingClientRect();
   return {img: [a.left, a.top, a.width, a.height], wrap: [w.left, w.top, w.width, w.height], cine: U.state().cine}; }"""
US_MARK = """() => { const U = window.NMSKUltrasound, v = U.views()[U.state().sel], c = v.ann.getContext('2d'), w = v.ann.getBoundingClientRect(), dpr = v.ann.width / Math.max(1, w.width);
   const x0 = Math.max(0, v.box.x), y0 = Math.max(0, v.box.y), d = c.getImageData(Math.round((x0 + 4) * dpr), Math.round((y0 + 3) * dpr), Math.round(140 * dpr), Math.round(14 * dpr)).data; let px = 0;
   for (let k = 0; k < d.length; k += 4) if (d[k] > 200 && d[k + 1] > 120 && d[k + 1] < 190 && d[k + 3] > 100) px++;
   return {px, annScaled: Math.abs(w.width - v.wrap.getBoundingClientRect().width) > 0.5}; }"""


def us_err(a, b, m0, m1):
    fx, fy = (m0[0] - a[0]) / a[2], (m0[1] - a[1]) / a[3]
    return math.hypot(b[0] + fx * b[2] - m1[0], b[1] + fy * b[3] - m1[1]), b[2] / a[2]


def section_C(pg, T, errs, tag):
    U = "window.NMSKUltrasound"
    pg.wait_for_function(f"() => {U} && window.NMSKModes", timeout=60000)
    pg.evaluate(f"() => {U}.ready()")
    if pg.evaluate("() => { const s = document.getElementById('mode-switch'); return !s || s.hidden; }"):
        V.tap(pg, "#t-mode", True); pg.wait_for_timeout(400)
    V.tap(pg, '.mw-tile[data-mode="us"]', True); pg.wait_for_timeout(1200)
    pg.evaluate(f"() => {U}.idle()")
    placed = V9.place(pg, "rectus_femoris_r") or V9.place(pg, "femur_r")
    pg.evaluate(f"() => {U}.idle()")
    check(f"{tag} C: US mode entered and the probe placed on the thigh", placed is not None and pg.evaluate("() => document.body.classList.contains('mode-us')"), errs)
    fsb = pg.evaluate("() => { const b = Array.from(document.querySelectorAll('[data-fs], .mm-tog')).find(e => /מסך מלא/.test(e.getAttribute('aria-label') || e.title || e.textContent) && e.getBoundingClientRect().width > 0); if (!b) return null; b.setAttribute('data-q290fs', '1'); return true; }")
    V.tap(pg, "[data-q290fs]", True)
    pg.wait_for_function("() => document.body.classList.contains('us-fs')", timeout=180000)
    pg.evaluate(f"() => {U}.idle()"); pg.wait_for_timeout(1500)
    s0 = pg.evaluate(US_IMG)
    check(f"{tag} C: full-screen split on (fs button found: {fsb}); image half {[round(x) for x in s0['wrap']]}", s0["wrap"][2] > 300, errs)
    menus = pg.evaluate(MENUS, [".fs-x", ".fs-more"])
    img = s0["img"]; m = (img[0] + img[2] * 0.55, img[1] + img[3] * 0.5)
    T.pinch(m, 40, 100); pg.evaluate(f"() => {U}.idle()"); frames(pg)
    s1 = pg.evaluate(US_IMG); e, k = us_err(s0["img"], s1["img"], m, m)
    check(f"{tag} C: pinch on the US image keeps the tissue under the fingers ({e:.2f} px, x{k:.2f})", e <= TOL and abs(k - 2.5) < 0.1, errs)
    m2 = (m[0] - 30, m[1] + 25)
    T.pinch(m, 50, 50, move=(-30, 25)); pg.evaluate(f"() => {U}.idle()"); frames(pg)
    s2 = pg.evaluate(US_IMG); e, _ = us_err(s1["img"], s2["img"], m, m2)
    check(f"{tag} C: two-finger drag pans the image with the fingers ({e:.2f} px)", e <= TOL, errs)
    mk = pg.evaluate(US_MARK)
    check(f"{tag} C: the watermark is still drawn at its own size on the visible image ({mk['px']} px; overlay not stretched: {not mk['annScaled']})", mk["px"] > 15 and not mk["annScaled"], errs)
    check(f"{tag} C: the pinch did not toggle the CINE play state ({s0['cine']} -> {s2['cine']})", s0["cine"] == s2["cine"], errs)
    again = pg.evaluate(MENUS_AGAIN, menus); bad = [a for a in again if not a["ok"]]
    check(f"{tag} C: ✕ and ⋯ unmoved, unscaled, on top ({len(menus)} found; {bad[:2]})", len(menus) == 2 and not bad, errs)
    US_SEL = "#us-root .us-views"
    ch = pg.evaluate(CHIP, US_SEL)
    check(f"{tag} C: the chip is shown on the image ({ch and ch['txt']})", ch and ch["top"], errs)
    T.tap(ch["x"], ch["y"]); pg.wait_for_timeout(400); pg.evaluate(f"() => {U}.idle()"); frames(pg)
    s3 = pg.evaluate(US_IMG)
    check(f"{tag} C: the chip returns the image to 1:1 ({[round(x) for x in s3['img']]} vs {[round(x) for x in s0['img']]})", all(abs(a - b) < 1 for a, b in zip(s3["img"], s0["img"])) and pg.evaluate(CHIP, US_SEL) is None, errs)
    T.pinch(m, 40, 80); pg.evaluate(f"() => {U}.idle()"); frames(pg)
    z = pg.evaluate(US_IMG)["img"][2] > s0["img"][2] * 1.5
    T.dbl(m[0], m[1]); pg.wait_for_timeout(500); pg.evaluate(f"() => {U}.idle()"); frames(pg)
    s4 = pg.evaluate(US_IMG)
    check(f"{tag} C: double-tap returns the image to 1:1 (zoomed before: {z})", z and all(abs(a - b) < 1 for a, b in zip(s4["img"], s0["img"])), errs)
    # the 3-D half of the split
    sel = canvas_sel(pg)
    r = pg.eval_on_selector(sel, "e => { const b = e.getBoundingClientRect(); return [b.left, b.top, b.width, b.height]; }")
    m3 = (r[0] + r[2] * 0.5, r[1] + r[3] * 0.5)
    if on_canvas(pg, sel, [(m3[0] - 90, m3[1]), (m3[0] + 90, m3[1])]):
        P = pg.evaluate(FOCAL, list(m3)); d0 = pg.evaluate(CAM)["dist"]
        T.pinch(m3, 40, 90, move=(10, -15)); frames(pg); pg.wait_for_timeout(500); frames(pg)
        e = err_px(pg, P, (m3[0] + 10, m3[1] - 15))
        check(f"{tag} C: the 3-D half zooms to the point too ({e:.2f} px, x{d0 / pg.evaluate(CAM)['dist']:.2f})", e <= TOL, errs)
    else:
        check(f"{tag} C: the 3-D half is under the fingers", False, errs)
    V.tap(pg, ".fs-x", True); pg.wait_for_timeout(1200)
    check(f"{tag} C: ✕ leaves full screen", not pg.evaluate("() => document.body.classList.contains('us-fs')"), errs)
    pg.evaluate("() => { const b = document.querySelector('#mb-exit-x'); if (b && b.getBoundingClientRect().width) b.click(); }"); pg.wait_for_timeout(800)


CT_AT = """([key, x, y]) => { const v = window.NMSKImaging.views()[key], r = v.wrap.getBoundingClientRect(), s = Math.min(r.width, r.height), bx = (r.width - s) / 2, by = (r.height - s) / 2;
   const ix = (x - r.left - bx) / s * v.W, iy = (y - r.top - by) / s * v.H, uu = (v.cu - v.W * v.px / 2) + ix * v.px, vv = (v.cv + v.H * v.px / 2) - iy * v.px, sp = v.spec;
   return {W: [0, 1, 2].map(i => sp.O[i] + sp.u[i] * uu + sp.v[i] * vv), u: sp.u, v: sp.v, mmpx: v.px * v.W / s, px: v.px, fov: window.NMSKImaging.state().fov[key], P: window.NMSKImaging.state().P}; }"""


def ct_err(a, b):
    d = [x - y for x, y in zip(a["W"], b["W"])]
    du = sum(x * y for x, y in zip(d, b["u"])); dv = sum(x * y for x, y in zip(d, b["v"]))
    return math.hypot(du, dv) / b["mmpx"]


def ct_open(pg):
    pg.evaluate("() => window.NMSKImaging.ready()")
    pg.evaluate("() => window.NMSKImaging.open()")
    pg.wait_for_function("() => { const I = window.NMSKImaging, s = I.state(), v = I.views()[s.active]; return s.open && v && v.spec && v.labels && v.labels.length && v.wrap.getBoundingClientRect().width > 100; }", timeout=400000)
    pg.evaluate("() => window.NMSKImaging.idle()")
    key = pg.evaluate("() => window.NMSKImaging.state().active")
    r = pg.evaluate("(k) => { const b = window.NMSKImaging.views()[k].wrap.getBoundingClientRect(); return [b.left, b.top, b.width, b.height]; }", key)
    return key, r


def section_D(pg, T, errs, tag, phone):
    key, r = ct_open(pg)
    m = (r[0] + r[2] * 0.58, r[1] + r[3] * 0.45)
    check(f"{tag} D: CT pane '{key}' open ({[round(x) for x in r]})", r[2] > 100, errs)
    a = pg.evaluate(CT_AT, [key, m[0], m[1]])
    if phone:
        panel0 = pg.evaluate(PANEL, "#img-root")
        T.pinch(m, 30, 75)
    else:
        menus = []
        pg.mouse.move(*m); pg.keyboard.down("Control")
        for _ in range(4):
            pg.mouse.wheel(0, -30); pg.wait_for_timeout(120)
        pg.keyboard.up("Control")
    pg.evaluate("() => window.NMSKImaging.idle()"); frames(pg); pg.evaluate("() => window.NMSKImaging.idle()")
    b = pg.evaluate(CT_AT, [key, m[0], m[1]]); e = ct_err(a, b)
    how = "pinch" if phone else "ctrl+wheel"
    check(f"{tag} D: {how} on the CT pane keeps the anatomy point under the {'fingers' if phone else 'cursor'} ({e:.2f} px; field of view {a['fov']:.0f} -> {b['fov']:.0f} mm, re-rendered at {a['px']:.3f} -> {b['px']:.3f} mm/px)",
          e <= TOL and b["fov"] < a["fov"] * 0.75 and b["px"] < a["px"] * 0.8, errs)
    check(f"{tag} D: the crosshair point did not move ({'the first finger no longer jumps it' if phone else 'wheel'})", all(abs(x - y) < 1e-6 for x, y in zip(a["P"], b["P"])), errs)
    if phone:
        check(f"{tag} D: zoom ratio follows the finger spread (x{a['fov'] / b['fov']:.2f})", abs(a["fov"] / b["fov"] - 2.5) < 0.1, errs)
        m2 = (m[0] + 35, m[1] + 30)
        T.pinch(m, 45, 45, move=(35, 30)); pg.evaluate("() => window.NMSKImaging.idle()"); frames(pg); pg.evaluate("() => window.NMSKImaging.idle()")
        c = pg.evaluate(CT_AT, [key, m2[0], m2[1]]); e = ct_err(b, c)
        check(f"{tag} D: two-finger drag pans the slice with the fingers ({e:.2f} px)", e <= TOL, errs)
        after = pg.evaluate(PANEL, "#img-root")
        check(f"{tag} D: the imaging panel unmoved and unscaled ({after['n']} buttons, same sizes: {after['n'] == panel0['n'] and after['sizes'] == panel0['sizes']}; panel {after['r']} vs {panel0['r']})",
              after["r"] == panel0["r"] and after["n"] == panel0["n"] and after["sizes"] == panel0["sizes"] and not after["scaled"], errs)
    CT_SEL = f'#img-root .img-view[data-view="{key}"]'
    ch = pg.evaluate(CHIP, CT_SEL)
    check(f"{tag} D: the chip is shown on the pane ({ch and ch['txt']})", ch and ch["top"], errs)
    if phone:
        T.tap(ch["x"], ch["y"])
    else:
        pg.mouse.click(ch["x"], ch["y"])
    pg.wait_for_timeout(300); pg.evaluate("() => window.NMSKImaging.idle()")
    f = pg.evaluate("(k) => window.NMSKImaging.state().fov[k]", key)
    check(f"{tag} D: the chip restores the field of view ({f:.0f} vs {a['fov']:.0f} mm)", abs(f - a["fov"]) < 1e-6 and pg.evaluate(CHIP, CT_SEL) is None, errs)
    pg.evaluate("() => window.NMSKImaging.close()"); pg.wait_for_timeout(500)


def section_E(pg, T, errs, tag):
    sel = canvas_sel(pg)
    pg.evaluate("""() => { const a = window.NMSKClinicalTool.api, v = a.view(); a.setCut({normal: [0, 1, 0], point: v.target}); window.xsecCtl.set(true); }""")
    pg.wait_for_function("() => window.xsecCtl.state().on && window.xsecCtl.state().builds > 0", timeout=300000)
    pg.wait_for_timeout(1500); frames(pg)
    st0 = pg.evaluate("() => window.xsecCtl.state()")
    panel = pg.evaluate(MENUS, ["#cut-panel button"])
    m = free_mid(pg, sel, 115, (0, 20))
    check(f"{tag} E: multi-slice stack on ({st0['n']} slices, {st0['spacing']} mm), fingers on the 3-D view next to the Cut panel (midpoint {m})", st0["on"] and m is not None, errs)
    if m is None:
        return
    P = pg.evaluate(FOCAL, list(m)); d0 = pg.evaluate(CAM)["dist"]
    T.pinch(m, 40, 110, move=(0, 20)); frames(pg); pg.wait_for_timeout(600); frames(pg)
    e = err_px(pg, P, (m[0], m[1] + 20)); st1 = pg.evaluate("() => window.xsecCtl.state()")
    check(f"{tag} E: pinch on the cross-section stack zooms to the point ({e:.2f} px, x{d0 / pg.evaluate(CAM)['dist']:.2f}); the stack is unchanged ({st1['n']} slices, on {st1['on']})",
          e <= TOL and st1["on"] and st1["n"] == st0["n"] and st1["spacing"] == st0["spacing"], errs)
    again = pg.evaluate(MENUS_AGAIN, panel); bad = [x for x in again if not x["ok"]]
    check(f"{tag} E: the Cut panel's {len(panel)} buttons unmoved and on top ({bad[:2]})", not bad, errs)
    ch = pg.evaluate(CHIP, sel)
    if ch:
        T.tap(ch["x"], ch["y"]); pg.wait_for_timeout(300)
    pg.evaluate("() => { window.xsecCtl.set(false); window.NMSKClinicalTool.api.setCut(null); }"); pg.wait_for_timeout(500)


def section_F(pg, T, errs, tag):
    if pg.query_selector("#about-btn"):
        V.tap(pg, "#about-btn", True); pg.wait_for_timeout(600)      # the "sources" sheet: ordinary page text, the browser's pinch zoom applies there
    target = pg.evaluate("""() => { for (const s of ['#modal.open .sheet', 'header h1']) { const e = document.querySelector(s); if (!e) continue; const r = e.getBoundingClientRect();
        if (r.width > 20 && getComputedStyle(e).touchAction !== 'none') return [r.left + r.width / 2, Math.min(r.top + r.height / 2, innerHeight / 2), s]; } return null; }""")
    tb = pg.evaluate("() => { const e = document.querySelector('#topright') || document.querySelector('#tools'); const r = e.getBoundingClientRect(); return [r.left, r.top, r.width, r.height]; }")
    if not target:
        print("  note F: no pinch-zoomable header on this page"); return
    try:
        T.cdp.send("Input.synthesizePinchGesture", {"x": int(target[0]), "y": int(target[1]), "scaleFactor": 2.0, "relativeSpeed": 300, "gestureSourceType": "touch"})
    except Exception as ex:  # noqa: BLE001
        print(f"  note F: Input.synthesizePinchGesture not available here ({str(ex)[:80]})"); return
    pg.wait_for_timeout(800)
    s = pg.evaluate("() => window.visualViewport.scale")
    if s <= 1.01:
        print(f"  note F: the headless browser did not zoom the page (visualViewport.scale {s}) -- native zoom not testable here"); return
    vis = pg.evaluate("() => { const e = document.querySelector('#topright') || document.querySelector('#tools'), r = e.getBoundingClientRect(), v = window.visualViewport, s = v.scale;"
                      " return [(r.left - v.offsetLeft) * s, (r.top - v.offsetTop) * s, r.width * s, r.height * s]; }")
    check(f"{tag} F: native page zoom x{s:.2f} (pinch on {target[2]}); the toolbar is drawn at 1:1 where it was ({[round(x) for x in vis]} vs {[round(x) for x in tb]})", all(abs(a - b) < 2 for a, b in zip(vis, tb)), errs)
    nc = pg.evaluate("() => { const c = document.querySelector('.pz-native'); return !!c && !c.hidden; }")
    check(f"{tag} F: the page chip offers 1:1 while the page is zoomed", nc, errs)
    pg.evaluate("() => document.querySelector('.pz-native').click()"); pg.wait_for_timeout(900)
    print(f"  note F: after the page chip, visualViewport.scale = {pg.evaluate('() => window.visualViewport.scale')} (Chromium honours the maximum-scale reset; iOS does not)")
    pg.evaluate("() => { const m = document.querySelector('#modal.open .close'); if (m) m.click(); }")


def run(own_dir: Path, zan_dir: Path, errs: list):
    only = os.environ.get("Q290_ONLY", "")
    with sync_playwright() as pl:
        b = pl.chromium.launch(args=V.LAUNCH_ARGS, executable_path="/opt/pw-browsers/chromium")
        for page_dir in (zan_dir, own_dir):
            html = V.html_of(page_dir); srv, port = V.serve(page_dir)
            try:
                for (w, h), phone in [((390, 844), True), ((1400, 900), False)]:
                    if only and only not in (f"{page_dir.name}@{w}", "phone" if phone else "desktop"):
                        continue
                    ctx = b.new_context(viewport={"width": w, "height": h}, has_touch=phone, is_mobile=phone)
                    pg = ctx.new_page(); perr = []
                    pg.set_default_timeout(400000)
                    pg.on("pageerror", lambda e: perr.append(str(e)))
                    pg.route("**/*", V.route)
                    tag = f"{page_dir.name}@{w}"
                    print(f"=== {tag} ===", flush=True)
                    pg.goto(f"http://127.0.0.1:{port}/{html}", wait_until="load", timeout=180000)
                    V.ready(pg)
                    T = Touch(pg)
                    is_own = pg.evaluate("() => window.NMSKClinicalTool.api.kind") != "webgl"
                    if phone:
                        section_A(pg, T, errs, tag)
                        if is_own:
                            section_D(pg, T, errs, tag, True)
                            section_C(pg, T, errs, tag)
                        else:
                            section_E(pg, T, errs, tag)
                            section_F(pg, T, errs, tag)
                    else:
                        section_B(pg, errs, tag)
                        if is_own:
                            section_D(pg, T, errs, tag, False)
                    check(f"{tag} G: 0 page errors ({perr[:2]})", not perr, errs)
                    ctx.close()
            finally:
                srv.terminate()
        b.close()


def main():
    errs = []
    run(Path(sys.argv[1]), Path(sys.argv[2]), errs)
    print("\nALL OK" if not errs else f"\n{len(errs)} FAILED: " + "; ".join(errs))
    return 0 if not errs else 1


if __name__ == "__main__":
    sys.exit(main())
