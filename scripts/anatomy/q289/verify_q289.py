#!/usr/bin/env python3
"""Q289: real headless-Chromium check of the ultrasound CINE motion types, the clean split full-screen view and the muscle fibre /
septum rendering, on locally served template-only rebuilt pages carrying the private US add-on. Desktop 1400x900 with real mouse
clicks (the US panel), phone 390x844 with real touch taps (the "US אבחנתי" workspace mode), per page given.

A  every motion type (long, circ, rot, tilt, track) started from its chip: a path is computed from the page's meshes, the CINE runs
   (the position advances by measured time), the direction arrow at the image edge is shown with a Hebrew direction label;
   track with no structure chosen first arms "tap the structure"; long/circ/track samples lie on the skin with the face at 90 deg
   (the frame's beam axis equals the sample's own skin normal)
B  playback: one way (stops at the far end), back and forth (turns round, stops back at the start), loop (keeps going)
C  the ± window control: "whole body part" off + the range slider set by a real drag / tap -> the long path spans that window
D  the clean split full screen: only the 3-D half, the image half and the two small corner buttons are on screen (12 x 12 grid of
   elementFromPoint hits), the halves are side by side on the desktop and stacked (3-D above) on the phone; the tiny in-image
   watermark is drawn; the arrow sits inside the image half; tapping the image pauses / resumes; the ⋯ sheet switches the type in
   place; Esc (desktop) / ✕ (phone) exits and the page's own layout comes back
E  fibres (desktop): a tibialis anterior image cuts its documented central aponeurosis (septum samples > 0), the fibre direction
   differs on the two sides of it (bipennate, cited angle), the hover readout names the architecture source; a muscle without data
   is labelled "generic line of action"; the 3-D view carries the fibre lines / septum sheet items
F  0 page errors

    python3 scripts/anatomy/q289/verify_q289.py PAGE_DIR [PAGE_DIR ...]
"""
from __future__ import annotations
import json
import math
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "q283"))
import verify_q283 as V  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

check, tap = V.check, V.tap
U = "window.NMSKUltrasound"
MOTIONS = {"long": "אורכי", "circ": "היקפי", "rot": "סיבוב", "tilt": "הטיה", "track": "מעקב מבנה"}


def ms(pg):
    return pg.evaluate(f"() => {U}.motionState()")


def wait_path(pg, kind, timeout=120000):
    pg.wait_for_function(f"(k) => {{ const s = {U}.motionState(); return s.motion === k && s.path && s.path.kind === k && !s.building && s.active; }}", arg=kind, timeout=timeout)


def wait_moving(pg, timeout=120000):
    """two different positions of the running CINE (software rendering: a frame can take long)"""
    p0 = ms(pg)["pos"]
    pg.wait_for_function(f"(p) => Math.abs({U}.motionState().pos - p) > 1e-3", arg=p0, timeout=timeout)
    return p0, ms(pg)["pos"]


def place(pg, sid_id):
    """probe on the skin straight in front of a structure (the same LIB.skinHit placement 'Place on skin' uses)"""
    return pg.evaluate("""(id) => { const g = window.NMSKUltrasound.geo(); let s = -1; for (let i = 0; i < g.n; i++) if (g.recs[i].id === id) { s = i; break; }
        if (s < 0) return null; const b = Array.from(g.bbox.slice(s * 6, s * 6 + 6)), c = [(b[0] + b[3]) / 2, (b[1] + b[4]) / 2, (b[2] + b[5]) / 2];
        const r = window.NMSKUltrasound.placeRay([c[0], c[1], c[2] + 700], [0, 0, -1]); return r ? {sid: s, P: r.P, N: r.N} : null; }""", sid_id)


def sid_of(pg, sid_id):
    return pg.evaluate("(id) => { const g = window.NMSKUltrasound.geo(); for (let i = 0; i < g.n; i++) if (g.recs[i].id === id) return i; return -1; }", sid_id)


def chip(pg, scope, key, phone):
    tap(pg, f"{scope} [data-mo={key}]", phone)


def drag_range(pg, selector, frac, phone):
    """move a range input to `frac` of its track: a real mouse drag on the desktop, a real tap on the track on the phone"""
    pg.eval_on_selector(selector, "e => e.scrollIntoView({block: 'center'})"); pg.wait_for_timeout(100)
    r = pg.eval_on_selector(selector, "e => { const b = e.getBoundingClientRect(); return {x: b.x, y: b.y, w: b.width, h: b.height, rtl: getComputedStyle(e).direction === 'rtl'}; }")
    if r["rtl"]:      # the Hebrew sheets are right-to-left: the minimum is at the right end of the track
        frac = 1 - frac
    x, y = r["x"] + 8 + (r["w"] - 16) * frac, r["y"] + r["h"] / 2
    if phone:
        pg.touchscreen.tap(x, y)
    else:
        pg.mouse.move(r["x"] + r["w"] / 2, y); pg.mouse.down(); pg.mouse.move(x, y, steps=3); pg.mouse.up()
    pg.wait_for_timeout(300)


GRID = """() => { const out = {bad: [], n: 0}, W = innerWidth, H = innerHeight,
    model = document.getElementById(document.getElementById('view') && window.NMSKClinicalTool && window.NMSKClinicalTool.api.kind === 'webgl' ? 'view' : 'app'),
    ok = [document.getElementById('us-cinefs'), model, document.querySelector('#us-root .us-views'), document.querySelector('.fs-x'), document.querySelector('.fs-more')];
  for (let i = 0; i < 12; i++) for (let j = 0; j < 12; j++) { const x = (i + 0.5) * W / 12, y = (j + 0.5) * H / 12, e = document.elementFromPoint(x, y); out.n++;
    if (!e || !ok.some(o => o && (o === e || o.contains(e)))) out.bad.push([Math.round(x), Math.round(y), e ? (e.id || e.className || e.tagName).toString().slice(0, 40) : null]); }
  // "visible" = displayed AND actually on top somewhere: the mode bar keeps its layout under the opaque backdrop, which is the point
  const vis = s => { const e = document.querySelector(s); if (!e) return false; const r = e.getBoundingClientRect(), cs = getComputedStyle(e); if (cs.display === 'none' || cs.visibility === 'hidden' || r.width <= 0 || r.height <= 0) return false;
    for (let i = 1; i < 6; i++) for (let j = 1; j < 4; j++) { const h = document.elementFromPoint(r.x + r.width * i / 6, r.y + r.height * j / 4); if (h && (h === e || e.contains(h))) return true; } return false; };
  out.ctl = vis('#us-root .us-ctl'); out.head = vis('#us-root .us-head'); out.modebar = vis('#mode-bar');
  out.buttons = Array.from(document.querySelectorAll('button')).filter(b => { const r = b.getBoundingClientRect(); if (r.width < 1 || r.height < 1) return false; const e = document.elementFromPoint(r.x + r.width / 2, r.y + r.height / 2); return e === b || b.contains(e); }).map(b => b.className || b.textContent.trim().slice(0, 12));
  const r3 = model.getBoundingClientRect(), ru = document.getElementById('us-root').getBoundingClientRect(), s3 = document.querySelector('#us-cinefs .fs-3d').getBoundingClientRect(), su = document.querySelector('#us-cinefs .fs-us').getBoundingClientRect();
  out.r3 = [r3.x, r3.y, r3.width, r3.height].map(Math.round); out.ru = [ru.x, ru.y, ru.width, ru.height].map(Math.round);
  out.s3 = [s3.x, s3.y, s3.width, s3.height].map(Math.round); out.su = [su.x, su.y, su.width, su.height].map(Math.round);
  const ab = document.querySelector('#us-root .us-arrow'), ar = ab.getBoundingClientRect(); out.arrow = {shown: !ab.hidden && ar.width > 0, r: [ar.x, ar.y, ar.width, ar.height].map(Math.round), txt: ab.textContent, ang: ab.getAttribute('data-ang'), kind: ab.getAttribute('data-kind')};
  return out; }"""

MARK = """() => { const U = window.NMSKUltrasound, s = U.state(), v = U.views()[s.sel]; if (!v || !v.box) return {px: 0};
  const c = v.ann.getContext('2d'), dpr = v.ann.width / Math.max(1, v.ann.getBoundingClientRect().width), b = v.box;
  const d = c.getImageData(Math.round((b.x + 4) * dpr), Math.round((b.y + 3) * dpr), Math.round(Math.min(140, b.w - 8) * dpr), Math.round(14 * dpr)).data; let px = 0;
  for (let k = 0; k < d.length; k += 4) if (d[k] > 200 && d[k + 1] > 120 && d[k + 1] < 190 && d[k + 3] > 100) px++;
  return {px}; }"""


def near(a, b, tol=3):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def section_A_to_D(pg, phone, errs, scope, tag, model_sel):
    # ---- A: every motion type from its chip ----
    thigh = place(pg, "rectus_femoris_r") or place(pg, "femur_r")
    check(f"{tag} A: probe placed on the anterior thigh skin", thigh is not None, errs)
    pg.evaluate(f"() => {U}.idle()")
    for key in ["long", "circ", "rot", "tilt", "track"]:
        if key == "track":
            pg.evaluate(f"() => {U}.set({{followSid: -1}})")
            chip(pg, scope, "track", phone); pg.wait_for_timeout(400)
            st = pg.evaluate(f"() => {U}.state()")
            if pg.evaluate("() => window.NMSKClinicalTool.api.selectedId ? window.NMSKClinicalTool.api.selectedId() : null") is None:
                check(f"{tag} A track: with no structure chosen the chip arms 'tap the structure' (pick armed, CINE not started)", st["motion"] == "track" and st["pick3d"] and not st["cine"], errs)
            else:
                print(f"  note: the page has a selected structure -- track takes it directly (no arming step)")
            sid = sid_of(pg, "sartorius_r")
            if sid < 0:
                sid = sid_of(pg, "rectus_femoris_r")
            pg.evaluate(f"(s) => {U}.set({{followSid: s}})", sid)   # what the 3-D tap's pick hands over (setFollow) -- starts the track
        else:
            chip(pg, scope, key, phone)
        wait_path(pg, key)
        p0, p1 = wait_moving(pg)
        st = ms(pg)
        pth = st["path"]
        check(f"{tag} A {key}: path from the meshes ({pth['n']} samples, {round(pth['total'])} {pth['unit']}, region {pth['region']['kind']} {pth['region']['name']}) and the CINE runs (pos {p0:.1f} -> {p1:.1f})",
              pth["total"] > 0 and (pth["unit"] == "deg" or pth["n"] >= 2) and p1 != p0, errs)
        pg.wait_for_function(f"() => {{ const s = {U}.motionState(); return s.info && s.info.he; }}", timeout=60000)
        info = ms(pg)["info"]
        arrow = pg.evaluate("() => { const a = document.querySelector('#us-root .us-arrow'); const r = a.getBoundingClientRect(); return {shown: !a.hidden, w: r.width, txt: a.textContent}; }")
        heb = any("֐" <= ch <= "׿" for ch in info["he"])
        check(f"{tag} A {key}: direction arrow shown at the image edge, Hebrew label '{info['he'][:48]}'", arrow["shown"] and heb and (info["ang"] is not None or info["curved"] or info["toward"]), errs)
        if key in ("long", "circ", "track"):
            sm = pg.evaluate(f"() => {U}.pathSamples()")
            ok90 = pg.evaluate("""() => { const f = window.NMSKUltrasound.frames()[window.NMSKUltrasound.state().sel]; const b = f.pf.b, N = f.spec.N;
                return Math.acos(Math.min(1, Math.abs(b[0] * N[0] + b[1] * N[1] + b[2] * N[2]))) * 180 / Math.PI; }""")
            contact = pg.evaluate(f"() => {{ const f = {U}.frames()[{U}.state().sel]; return !!(f && f.sim && f.sim.contact); }}")
            check(f"{tag} A {key}: the face stays at 90 deg to the skin normal (beam vs normal {ok90:.2f} deg), skin contact in the live frame", ok90 < 0.5 and contact, errs)
            if key == "long":
                lens = [math.dist(sm[i]["P"], sm[i + 1]["P"]) for i in range(len(sm) - 1)]
                check(f"{tag} A long: consecutive samples stay together on the skin (max step {max(lens):.1f} mm)", max(lens) < 40, errs)
    # ---- B: playback (rot: 180 deg, fast) ----
    chip(pg, scope, "rot", phone); wait_path(pg, "rot")
    if pg.evaluate(f"(s) => {{ const b = document.querySelector(s + ' [data-mm]'); return !!b && b.getAttribute('aria-expanded') !== 'true'; }}", scope):
        tap(pg, f"{scope} [data-mm]", phone)
    drag_range(pg, f"{scope} [data-ms]", 1.0, phone)
    check(f"{tag} B: speed slider moved to 'very fast' by a real {'tap' if phone else 'drag'}", ms(pg)["opts"]["speed"] == 5, errs)
    for mode, loop in (("once", False), ("back", False), ("once", True)):
        tap(pg, f"{scope} [data-mp={mode}]", phone)
        if ms(pg)["opts"]["loop"] != loop:
            tap(pg, f"{scope} [data-ml]", phone)
        o = ms(pg)["opts"]
        check(f"{tag} B: playback set to {mode}{' + loop' if loop else ''} by taps", o["back"] == (mode == "back") and o["loop"] == loop, errs)
        chip(pg, scope, "rot", phone); pg.wait_for_timeout(200)   # a second tap on the playing type stops it ...
        if not ms(pg)["active"]:
            chip(pg, scope, "rot", phone)                          # ... and the next tap starts a fresh run
        wait_path(pg, "rot")
        pg.evaluate(f"() => {{ window.__q289 = []; window.__q289T = setInterval(() => {{ const s = {U}.motionState(); window.__q289.push([s.pos, s.dir, s.active, s.done]); }}, 30); }}")
        if not loop:
            pg.wait_for_function(f"() => {U}.motionState().done", timeout=240000)
        else:
            pg.wait_for_function("() => window.__q289.some((x, i) => i && x[0] < window.__q289[i - 1][0] - 90 && x[1] > 0)", timeout=240000)
        smp = pg.evaluate("() => { clearInterval(window.__q289T); return window.__q289; }")
        st = ms(pg)
        if mode == "once" and not loop:
            check(f"{tag} B one way: ran forward only and stopped at the far end (pos {st['pos']:.0f} of 180, active {st['active']})", st["done"] and not st["active"] and abs(st["pos"] - 180) < 1e-6 and all(x[1] > 0 for x in smp), errs)
        elif mode == "back":
            check(f"{tag} B back and forth: turned round at 180 and stopped back at the start (pos {st['pos']:.0f})", st["done"] and any(x[1] < 0 for x in smp) and abs(st["pos"]) < 1e-6, errs)
        else:
            check(f"{tag} B loop: wrapped back to the start and kept running (active {st['active']})", st["active"] and not st["done"], errs)
    tap(pg, f"{scope} [data-mp=back]", phone)
    # ---- C: the window control ----
    chip(pg, scope, "long", phone); wait_path(pg, "long")
    if ms(pg)["opts"]["extAuto"]:
        tap(pg, f"{scope} [data-ea]", phone)
    drag_range(pg, f"{scope} [data-ex]", 0.2, phone)
    pg.wait_for_function(f"() => {{ const s = {U}.motionState(); return s.path && !s.building && s.path.kind === 'long' && !s.opts.extAuto && s.active && (s.path.win[1] - s.path.win[0]) <= s.opts.extCm * 10 + 1; }}", timeout=120000)
    st = ms(pg); w = st["path"]["win"]
    check(f"{tag} C: window set to {st['opts']['extCm']} cm by the slider -> the long path spans {round(w[1] - w[0])} mm around the probe", not st["opts"]["extAuto"] and abs((w[1] - w[0]) - st["opts"]["extCm"] * 10) < 15, errs)
    # ---- D: clean split full screen ----
    before = pg.evaluate(f"(s) => {{ const r = document.querySelector(s).getBoundingClientRect(); return [r.x, r.y, r.width, r.height].map(Math.round); }}", model_sel)
    tap(pg, f"{scope} [data-fs]", phone)
    pg.wait_for_function("() => document.body.classList.contains('us-fs')", timeout=180000)
    pg.wait_for_timeout(1500)
    pg.wait_for_function("() => { const a = document.querySelector('#us-root .us-arrow'); return a && !a.hidden; }", timeout=120000)
    g = pg.evaluate(GRID)
    check(f"{tag} D: nothing but the two halves and the two corner buttons on screen ({g['n'] - len(g['bad'])}/{g['n']} grid hits allowed; bad {g['bad'][:3]})", not g["bad"] and not g["ctl"] and not g["head"] and not g["modebar"], errs)
    check(f"{tag} D: the only buttons hit-testable are ✕ and ⋯ ({g['buttons']})", sorted(g["buttons"]) == ["fs-more", "fs-x"], errs)
    lay_ok = (g["s3"][1] + g["s3"][3] <= g["su"][1] + 2 and g["s3"][2] > 300) if phone else (g["s3"][0] + g["s3"][2] <= g["su"][0] + 2 and g["s3"][3] > 800)
    check(f"{tag} D: halves {'stacked, 3-D above' if phone else 'side by side, 3-D left'} (3-D {g['s3']}, image {g['su']}); the model and the image fill them", lay_ok and near(g["r3"], g["s3"]) and near(g["ru"], g["su"]), errs)
    a = g["arrow"]
    inside = a["r"][0] >= g["su"][0] - 1 and a["r"][1] >= g["su"][1] - 1 and a["r"][0] + a["r"][2] <= g["su"][0] + g["su"][2] + 1 and a["r"][1] + a["r"][3] <= g["su"][1] + g["su"][3] + 1
    check(f"{tag} D: direction arrow inside the image half ('{a['txt'][:40]}', angle {a['ang']})", a["shown"] and inside and bool(a["txt"]), errs)
    pg.wait_for_function(MARK.replace("return {px};", "return px > 15;").replace("{px: 0}", "false"), timeout=60000)
    check(f"{tag} D: the tiny 'simulation, not a scan' watermark is drawn inside the image ({pg.evaluate(MARK)['px']} watermark pixels)", pg.evaluate(MARK)["px"] > 15, errs)
    was = ms(pg)["cine"]
    tap(pg, "#us-root .us-views", phone); pg.wait_for_timeout(300)
    paused = ms(pg)["cine"]
    tap(pg, "#us-root .us-views", phone); pg.wait_for_timeout(300)
    check(f"{tag} D: a tap on the image pauses ({was} -> {paused}) and the next resumes ({ms(pg)['cine']})", was and not paused and ms(pg)["cine"], errs)
    tap(pg, ".fs-more", phone); pg.wait_for_timeout(300)
    check(f"{tag} D: ⋯ opens the one secondary sheet (motion types, playback, speed, plane, window)", pg.evaluate("() => { const s = document.querySelector('.fs-sheet'); return !s.hidden && s.querySelectorAll('[data-mo]').length === 5 && !!s.querySelector('[data-ex]') && !!s.querySelector('[data-ms]'); }"), errs)
    chip(pg, ".fs-sheet", "circ", phone); wait_path(pg, "circ")
    check(f"{tag} D: the sheet switches to 'circ' without leaving full screen", pg.evaluate("() => document.body.classList.contains('us-fs')"), errs)
    if phone:
        tap(pg, ".fs-x", phone)
    else:
        pg.keyboard.press("Escape")
    pg.wait_for_timeout(1200)
    after = pg.evaluate(f"(s) => {{ const r = document.querySelector(s).getBoundingClientRect(); return [r.x, r.y, r.width, r.height].map(Math.round); }}", model_sel)
    check(f"{tag} D: {'✕' if phone else 'Esc'} leaves full screen and the 3-D view is back where it was ({before} -> {after})", not pg.evaluate("() => document.body.classList.contains('us-fs')") and near(before, after, 4), errs)
    chip(pg, scope, "circ", phone); pg.wait_for_timeout(300)   # stop


def section_E(pg, errs, tag):
    pg.evaluate(f"() => {U}.set({{motion: null, cine: false, mode: 'sweep', view: 'single'}})")
    p = place(pg, "tibialis_anterior_r")
    check(f"{tag} E: probe over tibialis anterior", p is not None, errs)
    sid = sid_of(pg, "tibialis_anterior_r")
    info = pg.evaluate(f"(s) => {U}.archInfo(s)", sid)
    check(f"{tag} E: TA architecture = bipennate, cited 15->6 deg (Hiblar 2003), one central aponeurosis sheet", info.get("type") == "bipennate" and len(info["sheets"]) == 1 and "PMID 15098705" in info["label"], errs)
    c, w = info["c"], info["w"]
    sh = info["sheets"][0]["off"]
    pa = [c[i] + w[i] * (sh + 4) for i in range(3)]
    pb = [c[i] + w[i] * (sh - 4) for i in range(3)]
    fa = pg.evaluate(f"([s, p]) => {U}.fibreAt(s, p)", [sid, pa]); fb = pg.evaluate(f"([s, p]) => {U}.fibreAt(s, p)", [sid, pb])
    ang = lambda f: math.degrees(math.acos(min(1, abs(sum(f["f"][i] * info["a"][i] for i in range(3))))))
    wa = sum(fa["f"][i] * w[i] for i in range(3)); wb = sum(fb["f"][i] * w[i] for i in range(3))
    check(f"{tag} E: fibres on the two sides of the central sheet lean opposite ways at the cited angle ({ang(fa):.1f} / {ang(fb):.1f} deg)", wa * wb < 0 and 5 < ang(fa) < 16 and 5 < ang(fb) < 16, errs)
    for ref in ("trans", "long"):
        pg.evaluate(f"(r) => {U}.set({{refKey: r, rot: 0, depthCm: 5}})", ref); pg.evaluate(f"() => {U}.idle()")
        stt = pg.evaluate(f"() => {{ const f = {U}.frames()[0]; return f && f.sim ? f.sim.stats : null; }}")
        check(f"{tag} E: {ref} image: fibre-direction texture samples {stt['archSamples']}, central aponeurosis (hyperechoic) samples {stt['sepSamples']}", stt["archSamples"] > 1000 and stt["sepSamples"] > 0, errs)
    mus = pg.evaluate(f"() => {U}.imageMuscles()")
    ov = dict(pg.evaluate(f"() => {U}.overlayItems()") or [])
    check(f"{tag} E: 3-D view carries faint fibre lines ({ov.get('fibres')}) and the septum sheet ({ov.get('septa')}) for the muscles the image cuts ({[m['id'] for m in mus]})", (ov.get("fibres") or 0) > 0 and (ov.get("septa") or 0) > 0, errs)
    box = pg.eval_on_selector("#us-root .us-view:not([style*='display: none'])", "e => { const r = e.getBoundingClientRect(); return {x: r.x, y: r.y, w: r.width, h: r.height}; }")
    hit = None
    for fy in (0.35, 0.45, 0.55, 0.3, 0.6, 0.25):
        for fx in (0.5, 0.4, 0.6):
            pg.mouse.move(box["x"] + box["w"] * fx, box["y"] + box["h"] * fy); pg.wait_for_timeout(120)
            t = pg.inner_text("#us-root .us-read")
            if "fibres:" in t:
                hit = t; break
        if hit:
            break
    check(f"{tag} E: hovering a muscle in the image names its fibre architecture and source ('{(hit or '')[-110:]}')", bool(hit) and ("PMID" in hit or "(" in hit.split("fibres:")[1]), errs)
    gen = pg.evaluate("""() => { const U = window.NMSKUltrasound, g = U.geo(); for (let i = 0; i < g.n; i++) { if (U.classOf(i) !== 'muscle') continue; const a = U.archInfo(i); if (a.generic) return {id: g.recs[i].id, label: a.label}; } return null; }""")
    check(f"{tag} E: a muscle without architecture data is labelled as the generic line of action ({gen and gen['id']})", gen is not None and "generic line of action" in gen["label"], errs)


def run(page_dir: Path, errs: list):
    html = V.html_of(page_dir); srv, port = V.serve(page_dir)
    try:
        with sync_playwright() as pl:
            b = pl.chromium.launch(args=V.LAUNCH_ARGS, executable_path="/opt/pw-browsers/chromium")
            vps = [((1400, 900), False), ((390, 844), True)]
            if os.environ.get("Q289_ONLY") in ("desktop", "phone"):    # re-run one viewport only
                vps = [v for v in vps if v[1] == (os.environ["Q289_ONLY"] == "phone")]
            for (w, h), phone in vps:
                ctx = b.new_context(viewport={"width": w, "height": h}, has_touch=phone, is_mobile=phone)
                pg = ctx.new_page(); perr = []
                pg.set_default_timeout(180000)   # software rendering: the page is busy re-slicing CINE frames between events
                pg.on("pageerror", lambda e: perr.append(str(e)))
                pg.route("**/*", V.route)
                tag = f"{page_dir.name}@{w}"
                print(f"=== {tag} ===")
                pg.goto(f"http://127.0.0.1:{port}/{html}", wait_until="load", timeout=120000)
                V.ready(pg)
                pg.wait_for_function(f"() => {U} && window.NMSKModes", timeout=60000)
                pg.evaluate(f"() => {U}.ready()")
                kind = pg.evaluate("() => window.NMSKClinicalTool.api.kind")
                model_sel = "#view" if kind == "webgl" else "#app"
                if phone:
                    if pg.evaluate("() => { const s = document.getElementById('mode-switch'); return !s || s.hidden; }"):
                        tap(pg, "#t-mode", phone); pg.wait_for_timeout(400)
                    tap(pg, '.mw-tile[data-mode="us"]', phone); pg.wait_for_timeout(1200)
                    check(f"{tag}: 'US אבחנתי' mode entered by a tap on its tile", pg.evaluate("() => document.body.classList.contains('mode-us')"), errs)
                    pg.evaluate(f"() => {U}.idle()")
                    tap(pg, ".mm-bar .mm-tog[aria-expanded]", phone); pg.wait_for_timeout(300)
                    check(f"{tag}: one tap on 'תנועה' opens the short list of 5 motion types", pg.evaluate("() => { const p = document.querySelector('.mm-mopop'); return !p.hidden && p.querySelectorAll('[data-mo]').length === 5; }"), errs)
                    section_A_to_D(pg, phone, errs, ".mm-mopop", tag, model_sel)
                else:
                    tap(pg, "#t-ultrasound", phone); pg.wait_for_timeout(800)
                    pg.evaluate(f"() => {U}.idle()")
                    if pg.evaluate("() => { const t = document.querySelector('#us-root .sectabs [data-sec=mode]'); return !!t && t.getBoundingClientRect().width > 0; }"):
                        tap(pg, "#us-root .sectabs [data-sec=mode]", phone)
                    section_A_to_D(pg, phone, errs, "#us-root .us-ctl .us-mo", tag, model_sel)
                    section_E(pg, errs, tag)
                check(f"{tag} F: 0 page errors ({perr[:2]})", not perr, errs)
                ctx.close()
            b.close()
    finally:
        srv.terminate()


def main():
    errs = []
    for d in sys.argv[1:]:
        run(Path(d), errs)
    print("\nALL OK" if not errs else f"\n{len(errs)} FAILED: " + "; ".join(errs))
    return 0 if not errs else 1


if __name__ == "__main__":
    sys.exit(main())
