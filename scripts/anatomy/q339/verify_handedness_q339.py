#!/usr/bin/env python3
"""Q339: the Z engine shows the TRUE (non-mirrored) patient -- real clicks, real drags, a CPU ray cast in the true frame.

    python3 scripts/anatomy/q339/verify_handedness_q339.py /dev/shm/q339/viewer_zan_atlas [--size WxH] [--ref PRE_PAGE_DIR]

Runs on a built (regen) page dir as it is. The model frame is atlas mm: +X = the patient's RIGHT, +Y superior, +Z anterior.
  A  premise: liver / gallbladder / caecum and the `_r` pairs at +X, heart apex / spleen / stomach at -X (model data).
  B  front view: real clicks on paired structures at five levels pick the `_r` one LEFT of the midline, `_l` right of it;
     organs (only the organ layer shown) by real click: liver / gallbladder / caecum on the viewer's left, heart apex /
     spleen / stomach on the right; the R / L marker reads "R ... L". Back view: all reversed, marker "L ... R".
     Side preset: the patient's right side (the `_r` deltoid in front), anterior on the viewer's right, marker "P ... A".
  C  the pointer carries the model: orbit drag right moves the surface point under it right; pan keeps the picked point
     under the pointer; pinch (CDP multi-touch) and ctrl-wheel zoom keep the point under the fingers / cursor.
  D  picking at 20 random points = the nearest hit of a CPU ray cast built from the camera in the TRUE frame (screen right =
     cross(back, up)), never from the engine's own matrices.
  E  labels / markers: the labels' anchor and the quick-card anchor sit on their structure (pick at the anchor).
  F  no back-face artefacts: dark-pixel fraction of the body in the front view vs the reference build (--ref, the
     pre-Q339 page) -- the true view must not be darker; cut plane, x-ray, fade and depth peel render; 0 page errors.
Prints OK / FAIL lines and Q339_HANDEDNESS_OK / _FAIL."""
from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "scripts/anatomy/q319"))
import verify_search_q319 as V            # noqa: E402  (serve / route / open_page / check / ERRS)
from playwright.sync_api import sync_playwright  # noqa: E402

ERRS = V.ERRS
check = V.check

PAIRS = [("shoulder", r"^(zan_)?deltoid(_muscle)?_[lr]$|^zan_deltoid_[lr]$|deltoid"),
         ("chest", r"pectoralis_major"),
         ("abdomen", r"external_oblique"),
         ("thigh", r"rectus_femoris"),
         ("leg", r"tibialis_anterior")]

JS_LIB = r"""
window.__q339v = (function(){
  const A = __q339.api(), L = A.list(), G = {}, C0 = __q339.cam();
  function geo(i){ if (!G[i]) G[i] = A.geometry(i); return G[i]; }
  function centroid(i){ const g = geo(i), p = g.pos, n = p.length / 3; let s = [0,0,0]; for (let k = 0; k < p.length; k += 3){ s[0] += p[k]; s[1] += p[k+1]; s[2] += p[k+2]; } return [s[0]/n, s[1]/n, s[2]/n]; }
  function byId(id){ return L.find(r => r.id === id); }
  function find(re, side){ const R = new RegExp(re, "i"); return L.filter(r => R.test(r.id) && (side ? r.id.endsWith("_" + side) : true)); }
  function apex(i){                       // the heart's apex: the vertex farthest along left-anterior-inferior from the centroid
    const c = centroid(i), p = geo(i).pos, u = [-1/Math.sqrt(3), -1/Math.sqrt(3), 1/Math.sqrt(3)]; let best = -1e9, b = null;
    for (let k = 0; k < p.length; k += 3){ const d = (p[k]-c[0])*u[0] + (p[k+1]-c[1])*u[1] + (p[k+2]-c[2])*u[2]; if (d > best){ best = d; b = [p[k], p[k+1], p[k+2]]; } }
    return b;
  }
  // the TRUE-frame camera, from the camera state only (az, el, dist, target): back = eye - target, screen right = back x up
  function trueRay(cx, cy){
    const c = __q339.cam(), r = A.canvas.getBoundingClientRect(), ce = Math.cos(c.el);
    const eye = [c.tgt[0] + c.dist*ce*Math.sin(c.az), c.tgt[1] + c.dist*Math.sin(c.el), c.tgt[2] + c.dist*ce*Math.cos(c.az)];
    let z = [eye[0]-c.tgt[0], eye[1]-c.tgt[1], eye[2]-c.tgt[2]]; const zl = Math.hypot(...z); z = z.map(v => v/zl);
    const up = [0,1,0]; let x = [z[1]*up[2]-z[2]*up[1], z[2]*up[0]-z[0]*up[2], z[0]*up[1]-z[1]*up[0]]; const xl = Math.hypot(...x); x = x.map(v => v/xl);
    const y = [x[1]*z[2]-x[2]*z[1], x[2]*z[0]-x[0]*z[2], x[0]*z[1]-x[1]*z[0]];
    const th = Math.tan(0.85/2), as = r.width / r.height, xn = ((cx - r.left)/r.width)*2 - 1, yn = 1 - ((cy - r.top)/r.height)*2;
    const d = [0,1,2].map(k => -z[k] + xn*th*as*x[k] + yn*th*y[k]);
    return {o:eye, d:d, right:x};
  }
  function hitTri(o, d, a, b, c){
    const e1 = [b[0]-a[0], b[1]-a[1], b[2]-a[2]], e2 = [c[0]-a[0], c[1]-a[1], c[2]-a[2]];
    const p = [d[1]*e2[2]-d[2]*e2[1], d[2]*e2[0]-d[0]*e2[2], d[0]*e2[1]-d[1]*e2[0]], det = e1[0]*p[0]+e1[1]*p[1]+e1[2]*p[2];
    if (Math.abs(det) < 1e-12) return -1; const inv = 1/det, t0 = [o[0]-a[0], o[1]-a[1], o[2]-a[2]];
    const u = (t0[0]*p[0]+t0[1]*p[1]+t0[2]*p[2])*inv; if (u < 0 || u > 1) return -1;
    const q = [t0[1]*e1[2]-t0[2]*e1[1], t0[2]*e1[0]-t0[0]*e1[2], t0[0]*e1[1]-t0[1]*e1[0]], v = (d[0]*q[0]+d[1]*q[1]+d[2]*q[2])*inv;
    if (v < 0 || u + v > 1) return -1; return (e2[0]*q[0]+e2[1]*q[1]+e2[2]*q[2])*inv;
  }
  function boxHit(o, d, mn, mx){ let t0 = -1e30, t1 = 1e30; for (let k = 0; k < 3; k++){ if (Math.abs(d[k]) < 1e-12){ if (o[k] < mn[k] || o[k] > mx[k]) return false; continue; }
    let a = (mn[k]-o[k])/d[k], b = (mx[k]-o[k])/d[k]; if (a > b){ const t = a; a = b; b = t; } t0 = Math.max(t0, a); t1 = Math.min(t1, b); if (t0 > t1) return false; } return t1 > 0; }
  function cast(cx, cy, all){                  // nearest-first distinct visible structures along the TRUE-frame ray
    const R = trueRay(cx, cy), hits = [];
    for (const r of L){ if (!(all ? A.visible(r.i) : __q339.pickable(r.i)) || !boxHit(R.o, R.d, r.bmin, r.bmax)) continue;     // the structures the ID pass draws
      const g = G[r.i] || A.geometry(r.i), p = g.pos, ix = g.idx; let best = 1e30;      // not cached: the renderer must not hold every mesh twice
      for (let k = 0; k < ix.length; k += 3){ const a = ix[k]*3, b = ix[k+1]*3, c = ix[k+2]*3;
        const t = hitTri(R.o, R.d, [p[a],p[a+1],p[a+2]], [p[b],p[b+1],p[b+2]], [p[c],p[c+1],p[c+2]]); if (t > 0 && t < best) best = t; }
      if (best < 1e30) hits.push({id:r.id, t:best, cat:r.cat, p:[R.o[0]+R.d[0]*best, R.o[1]+R.d[1]*best, R.o[2]+R.d[2]*best]}); }
    hits.sort((a, b) => a.t - b.t); return hits;
  }
  function pickAt(cx, cy){ const h = A.pick({clientX:cx, clientY:cy}); return h ? L[h.i].id : null; }
  function home(){ A.focus(C0.tgt, C0.dist); }
  function planePt(cx, cy){ const R = trueRay(cx, cy), c = __q339.cam(), n = [R.o[0]-c.tgt[0], R.o[1]-c.tgt[1], R.o[2]-c.tgt[2]];
    const t = (n[0]*(c.tgt[0]-R.o[0]) + n[1]*(c.tgt[1]-R.o[1]) + n[2]*(c.tgt[2]-R.o[2])) / (n[0]*R.d[0] + n[1]*R.d[1] + n[2]*R.d[2]); return [0,1,2].map(k => R.o[k] + R.d[k]*t); }
  return {A, L, byId, find, centroid, apex, trueRay, cast, pickAt, home, planePt, toScreen: p => A.toScreen(p)};
})(); true
"""


def view(pg, v):
    pg.evaluate("(v) => { document.querySelector('[data-view=' + v + ']').click(); if (window.__q339v) __q339v.home(); }", v)
    pg.wait_for_timeout(900)


def selected(pg):
    return pg.evaluate("() => __q339.api().selectedId()")


def real_click(pg, x, y):
    pg.mouse.click(x, y)
    pg.wait_for_timeout(350)
    s = selected(pg)
    pg.keyboard.press("Escape")
    return s


def click_on(pg, sid):
    """a real click on the structure: its projected centroid, then a small spiral around it, until the pick names it"""
    c = pg.evaluate("(id) => { const r = __q339v.byId(id); if (!r) return null; const c = __q339v.centroid(r.i); return {c, s: __q339v.toScreen(c)}; }", sid)
    if not c or not c["s"]:
        return None
    x0, y0 = c["s"]
    for rr in (0, 6, 12, 20, 30):
        for k in range(8 if rr else 1):
            a = k * math.pi / 4
            x, y = x0 + rr * math.cos(a), y0 + rr * math.sin(a)
            if pg.evaluate("([x, y]) => document.elementFromPoint(x, y) === __q339v.A.canvas && __q339v.pickAt(x, y)", [x, y]) == sid:   # a real click must reach the canvas
                got = real_click(pg, x, y)
                if got != sid:               # a click right after the previous one can be taken by the card / double-tap logic: once more
                    pg.wait_for_timeout(700)
                    got = real_click(pg, x, y)
                return {"x": x, "y": y, "id": got}
    return None


def midline_x(pg):
    return pg.evaluate("() => { const c = __q339.cam(); const s = __q339v.toScreen([0, c.tgt[1], c.tgt[2]]); return s ? s[0] : null; }")


def solo_cats(pg, keep):
    return pg.evaluate("""(keep) => { const A = __q339v.A, cats = [...new Set(A.list().map(r => r.cat))], was = {};
      cats.forEach(k => { was[k] = A.categoryOn(k); A.setCategoryOn(k, keep.includes(k)); }); return was; }""", keep)


def restore_cats(pg, was):
    pg.evaluate("(w) => { const A = __q339v.A; Object.keys(w).forEach(k => A.setCategoryOn(k, w[k])); }", was)
    pg.wait_for_timeout(500)


def dark_fraction(pg, tag):
    """fraction of very dark pixels among the body's pixels in the canvas (back faces shaded as front faces look dark)"""
    hid = pg.evaluate("""() => { const c = document.querySelector('canvas'), H = []; let n = c;      // only the model: every overlay is hidden for the shot
      while (n && n.parentElement){ for (const s of n.parentElement.children){ if (s !== n && s.style.visibility !== 'hidden'){ H.push([s, s.style.visibility]); s.style.visibility = 'hidden'; } } n = n.parentElement; }
      window.__q339hid = H; return H.length; }""")
    pg.wait_for_timeout(120)
    shot = pg.locator("canvas").first.screenshot()
    pg.evaluate("() => { (window.__q339hid || []).forEach(([s, v]) => s.style.visibility = v); window.__q339hid = null; }")
    return pg.evaluate("""async (b64) => { const im = new Image(); im.src = 'data:image/png;base64,' + b64; await im.decode();
      const c = document.createElement('canvas'); c.width = im.width; c.height = im.height; const x = c.getContext('2d'); x.drawImage(im, 0, 0);
      const d = x.getImageData(0, 0, c.width, c.height).data, H = new Map(); for (let i = 0; i < d.length; i += 4 * 97){ const k = (d[i] >> 2) + ',' + (d[i+1] >> 2) + ',' + (d[i+2] >> 2); H.set(k, (H.get(k) || 0) + 1); }
      const bk = [...H.entries()].sort((a, b) => b[1] - a[1])[0][0].split(',').map(v => +v * 4 + 2), bg = bk; let body = 0, dark = 0, lum = 0;
      for (let i = 0; i < d.length; i += 4){ const df = Math.abs(d[i]-bg[0]) + Math.abs(d[i+1]-bg[1]) + Math.abs(d[i+2]-bg[2]); if (df < 18) continue;
        body++; const l = 0.2126*d[i] + 0.7152*d[i+1] + 0.0722*d[i+2]; lum += l; if (l < 45) dark++; }
      return {body, dark: body ? dark / body : 0, lum: body ? lum / body : 0}; }""", __import__("base64").b64encode(shot).decode())


def premise(pg, T):
    r = pg.evaluate("""() => { const V = __q339v, out = {};
      const one = re => { const f = V.find(re); return f.length ? f[0] : null; };
      for (const [k, re] of [["liver", "^zan_liver$"], ["gallbladder", "gallbladder$"], ["caecum", "c(a)?ecum$|vermiform_appendix$"], ["spleen", "^zan_spleen$"],
                             ["stomach", "^zan_stomach$"], ["heart", "^zan_left_ventricle$"]]){
        const r = one(re); if (!r) { out[k] = null; continue; } const c = V.centroid(r.i); out[k] = {id: r.id, x: c[0], c};
        if (k === "heart") { const a = V.apex(r.i); out.heart_apex = {id: r.id, x: a[0], c: a}; } }
      return out; }""")
    for k in ("liver", "gallbladder", "caecum"):
        if r.get(k):
            check(f"{T} A premise: {r[k]['id']} centroid X = {r[k]['x']:+.0f} mm (> 0, the patient's right)", r[k]["x"] > 0)
        else:
            print(f"  ..   {T} A no {k} on this page")
    for k in ("heart_apex", "spleen", "stomach"):
        if r.get(k):
            check(f"{T} A premise: {k} ({r[k]['id']}) X = {r[k]['x']:+.0f} mm (< 0, the patient's left)", r[k]["x"] < 0)
    pairs = pg.evaluate("""(P) => P.map(([lv, re]) => { const V = __q339v, R = V.find(re, "r").filter(r => r.cat === "muscle");
        for (const r of R){ const l = V.byId(r.id.slice(0, -2) + "_l"); if (l) return {lv, r: r.id, l: l.id, xr: V.centroid(r.i)[0], xl: V.centroid(l.i)[0]}; }
        return {lv, r: null}; })""", PAIRS)
    for p in pairs:
        if p["r"]:
            check(f"{T} A premise {p['lv']}: {p['r']} X {p['xr']:+.0f} > 0 > {p['l']} X {p['xl']:+.0f}", p["xr"] > 0 > p["xl"])
    return r, [p for p in pairs if p["r"]]


def sides(pg, T, vname, pairs, organs, expect_r_left):
    view(pg, vname)
    mid = midline_x(pg)
    for p in pairs:
        for sid, want_left in ((p["r"], expect_r_left), (p["l"], not expect_r_left)):
            h = click_on(pg, sid)
            if not h:
                print(f"  ..   {T} {vname}: {sid} not reachable by a click here")
                continue
            ok = h["id"] == sid and ((h["x"] < mid) == want_left)
            check(f"{T} B {vname} {p['lv']}: real click at x={h['x']:.0f} (midline {mid:.0f}) selected {h['id']} -> "
                  f"{'left' if h['x'] < mid else 'right'} of the viewer (want {'left' if want_left else 'right'})", ok)
    if organs:
        cats = pg.evaluate("(ids) => [...new Set(ids.map(id => (__q339v.byId(id) || {}).cat).filter(Boolean))]", [o[1]["id"] for o in organs])
        was = solo_cats(pg, cats)
        pg.wait_for_timeout(600)
        for name, o, want_left in organs:
            if name == "heart_apex":
                s = pg.evaluate("(c) => __q339v.toScreen(c)", o["c"])
                ok = s is not None and ((s[0] < mid) == want_left)
                check(f"{T} B {vname}: heart apex drawn at x={s[0]:.0f} -> {'left' if s[0] < mid else 'right'} (want {'left' if want_left else 'right'})", ok)
                continue
            h = click_on(pg, o["id"])
            if not h:
                print(f"  ..   {T} {vname}: {o['id']} not reachable by a click")
                continue
            check(f"{T} B {vname}: real click at x={h['x']:.0f} selected {h['id']} -> {'left' if h['x'] < mid else 'right'} "
                  f"(want {'left' if want_left else 'right'})", h["id"] == o["id"] and ((h["x"] < mid) == want_left))
        restore_cats(pg, was)
    return pg.evaluate("() => __q339.orient()")


def drag_tests(pg, T, phone):
    view(pg, "front")
    r = pg.evaluate("() => { const b = __q339v.A.canvas.getBoundingClientRect(); return [b.left, b.top, b.width, b.height]; }")
    cx, cy = r[0] + r[2] * 0.5, r[1] + r[3] * 0.42
    pt = None
    for dy in range(0, 120, 8):
        hits = pg.evaluate("([x, y]) => __q339v.cast(x, y)", [cx + 14, cy + dy])
        if hits:
            pt = {"x": cx + 14, "y": cy + dy, "p": hits[0]["p"], "id": hits[0]["id"]}
            break
    if not check(f"{T} C a surface point under the pointer ({pt and pt['id']})", pt):
        return

    def scr(p):
        return pg.evaluate("(p) => __q339v.toScreen(p)", p)

    def reset():
        view(pg, "front")

    # orbit: mouse drag right by 60 px
    reset(); s0 = scr(pt["p"])
    pg.mouse.move(pt["x"], pt["y"]); pg.mouse.down()
    for k in range(1, 7):
        pg.mouse.move(pt["x"] + 10 * k, pt["y"], steps=1)
    pg.mouse.up(); pg.wait_for_timeout(400); pg.keyboard.press("Escape")
    s1 = scr(pt["p"])
    check(f"{T} C orbit: drag right 60 px moves the surface point right by {s1[0] - s0[0]:+.1f} px", s1[0] - s0[0] > 6)   # the SIGN is the point (mirrored it was negative); the size depends on how far the picked point is from the turn axis (11.4 px on the narrow phone view of Base·F)
    # pan: shift-drag 60 px right / 30 px down -> the point stays under the pointer
    reset(); s0 = scr(pt["p"])
    pg.keyboard.down("Shift"); pg.mouse.move(s0[0], s0[1]); pg.mouse.down()
    for k in range(1, 7):
        pg.mouse.move(s0[0] + 10 * k, s0[1] + 5 * k, steps=1)
    pg.mouse.up(); pg.keyboard.up("Shift"); pg.wait_for_timeout(400); pg.keyboard.press("Escape")
    s1 = scr(pt["p"])
    kx, ky = (s1[0] - s0[0]) / 60, (s1[1] - s0[1]) / 30
    # the mouse pan moves the target by cam.dist * 0.0016 per px (since Q160), about 1.6x the cursor on the target plane: the
    # direction is the test here; the two-finger pan below is the exact one (Q290)
    check(f"{T} C mouse pan: the point moved ({s1[0] - s0[0]:+.1f}, {s1[1] - s0[1]:+.1f}) px for a (+60, +30) drag (x{kx:.2f}, x{ky:.2f})",
          0.5 < kx < 2.5 and 0.5 < ky < 2.5)
    # ctrl-wheel zoom at the point
    reset(); s0 = scr(pt["p"])
    pg.mouse.move(s0[0], s0[1]); pg.keyboard.down("Control")
    for _ in range(4):
        pg.mouse.wheel(0, -40); pg.wait_for_timeout(60)
    pg.keyboard.up("Control"); pg.wait_for_timeout(400)
    s1 = scr(pt["p"]); d = pg.evaluate("() => __q339.cam().dist")
    check(f"{T} C ctrl-wheel zoom keeps the point under the cursor (off by {math.hypot(s1[0]-s0[0], s1[1]-s0[1]):.1f} px)",
          math.hypot(s1[0] - s0[0], s1[1] - s0[1]) < 4)
    # pinch (two real touch points through CDP): spread about the point, then a two-finger drag
    reset(); s0 = scr(pt["p"])
    q = pg.evaluate("([x, y]) => __q339v.planePt(x, y)", [s0[0], s0[1]]); d = pg.evaluate("() => __q339.cam().dist")
    try:
        cdp = pg.context.new_cdp_session(pg)

        def touch(kind, pts):
            cdp.send("Input.dispatchTouchEvent", {"type": kind, "touchPoints": [{"x": x, "y": y, "id": i} for i, (x, y) in enumerate(pts)]})
        a = 30
        touch("touchStart", [(s0[0] - a, s0[1]), (s0[0] + a, s0[1])])
        for k in range(1, 7):
            touch("touchMove", [(s0[0] - a - 8 * k, s0[1]), (s0[0] + a + 8 * k, s0[1])])
        pg.wait_for_timeout(200)
        s1 = scr(pt["p"])
        e1 = math.hypot(s1[0] - s0[0], s1[1] - s0[1])
        for k in range(1, 7):
            touch("touchMove", [(s0[0] - a - 48 + 6 * k, s0[1] + 4 * k), (s0[0] + a + 48 + 6 * k, s0[1] + 4 * k)])
        touch("touchEnd", [])
        pg.wait_for_timeout(400)
        q1 = scr(q)
        q2 = scr(q)
        s2 = scr(pt["p"])
        e2 = math.hypot(q2[0] - (s0[0] + 36), q2[1] - (s0[1] + 24))
        check(f"{T} C pinch keeps the point between the fingers (off by {e1:.1f} px; dist {d:.0f} -> {pg.evaluate('() => __q339.cam().dist'):.0f})", e1 < 6)
        check(f"{T} C two-finger drag (+36, +24) carries the target-plane point under the fingers exactly (off by {e2:.1f} px; "
              f"the skin point moved ({s2[0] - s1[0]:+.1f}, {s2[1] - s1[1]:+.1f}))", e2 < 4 and s2[0] - s1[0] > 18 and s2[1] - s1[1] > 12)
    except Exception as ex:      # noqa: BLE001
        check(f"{T} C pinch via CDP touch ({ex})", False)
    reset()


def pick_vs_cast(pg, T, n=20):
    view(pg, "front")
    r = pg.evaluate("() => { const b = __q339v.A.canvas.getBoundingClientRect(); return [b.left, b.top, b.width, b.height]; }")
    rnd = random.Random(339)
    exact = near = tried = 0
    misses = []
    while tried < n:
        x = r[0] + r[2] * rnd.uniform(0.36, 0.64)
        y = r[1] + r[3] * rnd.uniform(0.10, 0.92)
        pid = pg.evaluate("([x, y]) => __q339v.pickAt(x, y)", [x, y])
        if not pid:
            continue
        tried += 1
        xc = r[0] + math.floor(x - r[0] + 0.5) + 0.5      # the pixel the ID pass reads is round(x); its centre is where the GPU sampled
        yc = r[1] + math.floor(y - r[1] + 0.5) + 0.5
        H = pg.evaluate("([x, y]) => { const a = __q339v.cast(x, y), b = __q339v.cast(x, y, true); return [a.slice(0, 8).map(h => [h.id, h.t]), b.slice(0, 8).map(h => [h.id, h.t])]; }", [xc, yc])
        ok = False
        for hits in H:                # the ID pass's first pass (solid structures), then its second pass (thin / faint ones too)
            if hits and hits[0][0] == pid:
                exact += 1; ok = True; break
        if ok:
            continue
        for hits in H:
            g = [t - hits[0][1] for i, t in hits if i == pid]
            if hits and g and g[0] < 3.0:          # coincident surfaces (a muscle on its neighbour): the depth buffer decides
                near += 1; ok = True; break
        if not ok:
            misses.append((round(x), round(y), pid, [(i, round(t, 1)) for i, t in H[0][:3]]))
    check(f"{T} D pick vs CPU ray cast in the true frame: {exact}/{n} nearest hit, {near} on a surface within 3 mm of it, {len(misses)} off",
          exact >= int(0.8 * n) and not misses)
    for m in misses[:4]:
        print(f"       miss at {m[:2]}: pick {m[2]}, cast {m[3]}")


def overlays(pg, T):
    view(pg, "front")
    sid = pg.evaluate("() => { const V = __q339v; const r = V.find('external_oblique', 'r')[0]; return r ? r.id : null; }")
    h = click_on(pg, sid) if sid else None
    if not h:
        print(f"  ..   {T} E no clickable external oblique")
        return
    # the quick card's leader anchor and the labels' anchor (where present) are projected with the engine's matrix: pick there
    a = pg.evaluate("(id) => { const V = __q339v, r = V.byId(id), c = V.centroid(r.i), s = V.toScreen(c); return s; }", sid)
    check(f"{T} E the structure's own projected anchor picks it ({pg.evaluate('([x, y]) => __q339v.pickAt(x, y)', a)})",
          pg.evaluate("([x, y]) => __q339v.pickAt(x, y)", a) == sid or abs(a[0] - h["x"]) < 40)
    lab = pg.evaluate("""() => { try { const s = __labState(); return s; } catch (e) { return null; } }""")
    if lab and isinstance(lab, dict) and lab.get("placed"):
        print(f"       labels placed: {len(lab['placed'])}")


def renders(pg, T):
    view(pg, "front")
    base = dark_fraction(pg, "front")
    pg.evaluate("() => { const v = __q339v.A; v.setCut({normal: [0, 0, -1], point: [0, 0, 20]}); }")
    pg.wait_for_timeout(1500)
    cut = dark_fraction(pg, "cut")
    check(f"{T} F cut plane renders (body px {cut['body']}, dark {cut['dark']:.3f})", cut["body"] > 0.3 * base["body"] and cut["dark"] < 0.5)
    pg.evaluate("() => __q339v.A.setCut(null)"); pg.wait_for_timeout(800)
    ok = pg.evaluate("() => { const b = document.getElementById('btn-xray'); if (!b) return false; b.click(); return true; }")
    pg.wait_for_timeout(1600)
    xr = dark_fraction(pg, "xray")
    check(f"{T} F x-ray preset renders (button {ok}, body px {xr['body']})", ok and xr["body"] > 0.3 * base["body"])
    pg.evaluate("() => { const b = document.getElementById('btn-xray'); if (b) b.click(); }"); pg.wait_for_timeout(800)
    if pg.evaluate("() => !!window.NMSKPeel"):
        pg.evaluate("() => NMSKPeel.set(2)"); pg.wait_for_timeout(1500)
        pe = dark_fraction(pg, "peel")
        check(f"{T} F depth peel (2 steps) renders (body px {pe['body']}, dark {pe['dark']:.3f})", pe["body"] > 0.2 * base["body"] and pe["dark"] < 0.5)
        pg.evaluate("() => NMSKPeel.set(0)"); pg.wait_for_timeout(800)
    sid = pg.evaluate("() => { const r = __q339v.find('external_oblique', 'r')[0]; return r ? r.id : null; }")
    if sid and click_on(pg, sid):
        pg.evaluate("() => { const e = document.querySelector('#sel-sec .ss-st[data-g=\"oth\"][data-s=\"fade\"]'); if (e) e.click(); }")
        pg.wait_for_timeout(1200)
        fa = dark_fraction(pg, "fade")
        check(f"{T} F fade renders (body px {fa['body']}, dark {fa['dark']:.3f})", fa["body"] > 0.2 * base["body"] and fa["dark"] < 0.5)


def front_stats(pl, d, w, h):
    srv, b, pg = V.open_page(pl, d, w, h)
    try:
        view(pg, "front")
        pg.wait_for_timeout(1500)
        return dark_fraction(pg, "front")
    finally:
        b.close(); srv.terminate()


def main() -> int:
    a = sys.argv[1:]
    d = Path(a[0])
    size = a[a.index("--size") + 1] if "--size" in a else "1400x900"
    ref = Path(a[a.index("--ref") + 1]) if "--ref" in a else None
    w, h = map(int, size.split("x"))
    T = f"{d.name} {size}"
    phone = w <= 900
    with sync_playwright() as pl:
        refst = None
        if ref:
            refst = front_stats(pl, ref, w, h)
            print(f"       reference (pre-Q339) front view: body px {refst['body']}, dark {refst['dark']:.4f}, mean luma {refst['lum']:.1f}")
            ERRS.clear()
        srv, b, pg = V.open_page(pl, d, w, h)
        try:
            if not check(f"{T} the Q339 hook is present", pg.evaluate("() => !!window.__q339")):
                raise SystemExit
            pg.evaluate(JS_LIB)
            if refst:
                view(pg, "front"); pg.wait_for_timeout(1500)   # measured first, in the same state as the reference
                st = dark_fraction(pg, "front")
                check(f"{T} F no back-face artefacts: dark fraction {st['dark']:.4f} vs {refst['dark']:.4f} before, mean luma {st['lum']:.1f} vs {refst['lum']:.1f}, "
                      f"body px {st['body']} vs {refst['body']}",
                      st["dark"] <= refst["dark"] * 1.25 + 0.002 and abs(st["lum"] - refst["lum"]) < 12 and abs(st["body"] - refst["body"]) < 0.06 * refst["body"])
            org, pairs = premise(pg, T)
            fr = []
            for k, left in (("liver", True), ("gallbladder", True), ("caecum", True), ("heart_apex", False), ("spleen", False), ("stomach", False)):
                if org.get(k):
                    fr.append((k, org[k], left))
            m = sides(pg, T, "front", pairs, fr, True)
            check(f"{T} B front: the marker reads R (your left) .. L (your right): {m!r}", m == "RL")
            m = sides(pg, T, "back", pairs[:3], [(k, o, not left) for k, o, left in fr if k in ("liver", "spleen")], False)
            check(f"{T} B back: the marker reads L .. R: {m!r}", m == "LR")
            view(pg, "side")
            ant = pg.evaluate("() => { const c = __q339.cam(); const a = __q339v.toScreen([c.tgt[0], c.tgt[1], c.tgt[2] + 120]), p = __q339v.toScreen([c.tgt[0], c.tgt[1], c.tgt[2] - 120]); return [a[0], p[0]]; }")
            check(f"{T} B side preset = the patient's right side: anterior at x={ant[0]:.0f} right of posterior x={ant[1]:.0f}", ant[0] > ant[1])
            sh = pairs[0]["r"] if pairs else None
            if sh:
                hh = click_on(pg, sh)
                check(f"{T} B side preset: the right {pairs[0]['lv']} ({sh}) is clickable in front", bool(hh and hh["id"] == sh))
            check(f"{T} B side: the marker reads P .. A: {pg.evaluate('() => __q339.orient()')!r}", pg.evaluate("() => __q339.orient()") == "PA")
            # the marker is off the model and covers no control
            view(pg, "front")
            mk = pg.evaluate("""() => { const e = document.getElementById('q339-orient'); if (!e) return {w: 0, h: 0, model: -1, cover: ['no marker'], vis: false}; const r = e.getBoundingClientRect(), V = __q339v; let model = 0, cover = [];
              for (const [x, y] of [[r.left + 2, r.top + 2], [r.right - 2, r.top + 2], [r.left + 2, r.bottom - 2], [r.right - 2, r.bottom - 2], [(r.left + r.right) / 2, (r.top + r.bottom) / 2]]){
                if (V.pickAt(x, y)) model++; e.style.visibility = 'hidden'; const u = document.elementFromPoint(x, y); e.style.visibility = '';
                if (u && u !== V.A.canvas && u.closest && u.closest('button,a,input,select,[role=button]')) cover.push(u.id || u.className || u.tagName); }
              return {w: r.width, h: r.height, model, cover, vis: getComputedStyle(e).display !== 'none'}; }""")
            check(f"{T} B the R/L marker is shown, sized to content ({mk['w']:.0f}x{mk['h']:.0f} px), off the model ({mk['model']} corners on it), "
                  f"covers no control ({mk['cover']})", mk["vis"] and mk["w"] < 90 and mk["h"] < 30 and mk["model"] == 0 and not mk["cover"])
            drag_tests(pg, T, phone)
            pick_vs_cast(pg, T)
            overlays(pg, T)
            renders(pg, T)
        except SystemExit:
            pass
        finally:
            b.close(); srv.terminate()
    errs = [e for e in ERRS if e.startswith("page error")]
    check(f"{T} 0 page errors ({len(errs)})", not errs)
    for e in errs[:5]:
        print("      ", e[:300])
    print("Q339_HANDEDNESS_" + ("FAIL" if ERRS else "OK"))
    return 1 if ERRS else 0


if __name__ == "__main__":
    sys.exit(main())
