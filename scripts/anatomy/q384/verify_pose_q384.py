#!/usr/bin/env python3
"""Q384: the Pose tool -- deformation (B), elbow flexion / extension (C), the held joint (D).

Owner, on the live Base page with "Rings on the model", hip then knee flexed:
  "During hip flexion and then knee flexion, distortions appeared. The great saphenous vein is plainly distorted. Make sure
   that when a joint's position changes the tissues glide over one another and give a rounder and straighter look."
  "The skin looks torn when a joint's state changes. It has to stretch over the tissues."
  "The elbow lacks extension-flexion."
  "When a joint is chosen for moving -- stay moving its parts until another click on the joint, then it lets go."

    python3 scripts/anatomy/q384/verify_pose_q384.py <page dir> [--part bcd] [--shots DIR] [--json FILE]

B  reads the POSED vertices back from the page (window.__poseLive) in five poses and measures, by structure id, with
   scripts/anatomy/q384/pose_metrics_q384.py: the largest bend between consecutive 10 mm centreline segments, the smallest
   cross-section ratio, the length change, and the gap between skin border vertices that coincide at rest. The rest
   geometry must come back bit for bit after Reset. The time of one pose update is reported.
C  the elbow: the panel's "Elbow - Flexion (+) / extension (0)" slider and the ring both turn the forearm through
   0..150 degrees (docs/pose_rom_table.md `elbow_flex`), both sides; the rings at the elbow offer flexion wherever the
   pointer comes from.
R  (E1 + E2) every permitted axis of every joint has a handle in every view; ring size by the joint's room on the screen;
   real drags of the knee's bar and the elbow's flexion handle from the front, the back and an oblique view; touch.
P  (E4) the panel's "This joint only" view and the tile.
H  (E5) finger abduction / adduction, thumb axial rotation and the Opposition control: part_h_q384.py.
E  (E3) every placed origin / insertion of a muscle stays on its bone: part_e_q384.py, attach_q384.py.
D  a click on a joint holds it; the rings stay while the pointer wanders over other joints and a drag that wanders still
   turns the held joint; a second click lets go, a click on another joint switches, Escape lets go; with a mouse at
   1400x900 and with touch at 390x844; one held drag = one undo step.
Prints one line per check and VERIFY_POSE_Q384_OK / _FAIL. The page dir is never written: a private copy carries the
read-only test hook of Q338 (camera, layers)."""
from __future__ import annotations

import base64
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "scripts/anatomy/q338"))
sys.path.insert(0, str(HERE))
import pagehook_q338 as PH  # noqa: E402

V = PH.V
ERRS: list[str] = []


def check(label, cond):
    ok = bool(cond)
    print(("  OK  " if ok else "  FAIL") + " " + label, flush=True)
    if not ok:
        ERRS.append(label)
    return ok


JS_LIB = """() => {
  const P = window.__poseApi;
  window.__q384 = {
    world(id){ const r = P.rig(), j = r.joints.filter(q => q.id === id)[0], par = r.segs[j.seg][1], M = P.matrices()[par], c = j.c;
      return [M[0]*c[0] + M[1]*c[1] + M[2]*c[2] + M[3], M[4]*c[0] + M[5]*c[1] + M[6]*c[2] + M[7], M[8]*c[0] + M[9]*c[1] + M[10]*c[2] + M[11]]; },
    at(id){ return P.screen(this.world(id)); },
    under(x, y){ const e = document.elementFromPoint(x, y); return e ? (e.id || e.tagName) + '.' + (e.getAttribute('class') || '') : null; },
    grab(k){ const g = document.querySelectorAll('#pz-rings .pz-grab')[k]; if (!g) return null;
      let pts;
      if (g.dataset.bar){      // E2: a ring seen edge-on is a bar: 17 points along its far end (two bars cross at the hub)
        const a = [+g.getAttribute('x1'), +g.getAttribute('y1')], b = [+g.getAttribute('x2'), +g.getAttribute('y2')]; pts = [];
        for (let i = 0; i < 17; i++){ const u = 0.70 + 0.28 * i / 16; pts.push([a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u]); }
      } else pts = g.getAttribute('points').trim().split(/\\s+/).map(s => s.split(',').map(Number));
      return {pts, j: g.dataset.j, bar: !!g.dataset.bar, n: document.querySelectorAll('#pz-rings .pz-grab').length}; },
    hist(){ return window.NMSKHistory ? NMSKHistory.state() : null; },
    b64(i){ const a = window.__poseLive(i); if (!a) return null; const u = new Uint8Array(a.buffer, a.byteOffset, a.byteLength); let s = ''; const n = 0x8000;
      for (let k = 0; k < u.length; k += n) s += String.fromCharCode.apply(null, u.subarray(k, k + n)); return btoa(s); }
  };
  return true;
}"""


def ring_state(pg):
    return pg.evaluate("() => window.__poseApi.ringState()")


def pose_of(pg, jid):
    return pg.evaluate("(j) => window.__poseApi.pose().j[j]", jid)


def open_pose(pg, panel=False):
    pg.wait_for_function("window.__poseApi && __poseApi.ready()", timeout=180000)
    pg.evaluate(JS_LIB)
    pg.evaluate("(p) => { const P = window.__poseApi; P.reset(); P.open(true); if (!p) P.open(false); }", panel)
    pg.wait_for_timeout(700)


def frame(pg, tgt, dist, az=0.0):
    pg.evaluate("(c) => window.__q338.cam(c)", {"az": az, "el": 0.05, "dist": dist, "tgt": tgt})
    pg.wait_for_timeout(600)


# ------------------------------------------------------------------------------------------------ C
def part_c(pg):
    print("C. elbow flexion / extension", flush=True)
    open_pose(pg, panel=True)
    info = pg.evaluate("""() => { const P = window.__poseApi, out = {};
      const sec = [...document.querySelectorAll('#pz-body .pz-g')].filter(s => (s.querySelector('.pz-gh') || {}).textContent === 'Elbow / forearm')[0];
      out.group = !!sec; if (!sec) return out;
      const hb = sec.querySelector('.pz-gh'); if (hb.getAttribute('aria-expanded') !== 'true') hb.click();
      out.rows = [...sec.querySelectorAll('.pz-row')].map(r => ({lab: r.querySelector('.pz-lab').textContent,
        cells: [...r.querySelectorAll('.pz-cell')].map(c => { const g = c.querySelector('input[type=range]'); return {side: c.querySelector('.pz-sd').textContent, min: +g.min, max: +g.max, v: +g.value, aria: g.getAttribute('aria-label')}; })}));
      out.dof = ['elbow_r', 'elbow_l'].map(id => { const j = P.rig().joints.filter(q => q.id === id)[0]; return j ? j.dof.map(d => [d.k, d.lo, d.hi, d.q0, d.rk]) : null; });
      out.rom = (P.rig().rom || {}).elbow_flex || null;
      return out; }""")
    check("the panel has the group 'Elbow / forearm'", info.get("group"))
    row = [r for r in info.get("rows", []) if "Flexion" in r["lab"] and "xtension" in r["lab"]]
    check("with a row for elbow flexion / extension (%r), one slider per side" % (row[0]["lab"] if row else None), row and len(row[0]["cells"]) == 2)
    rom = info.get("rom") or [None, None]
    check("the range is docs/pose_rom_table.md `elbow_flex`: 0 (extension) to 150 (flexion) -- rig says %s" % (info.get("dof"),),
          all(d and d[0][0] == "flex" and d[0][1] == 0 and d[0][2] == 150 and d[0][4] == "elbow_flex" for d in info.get("dof", [])) and rom[0] == 0 and rom[1] == 150)
    for side in ("r", "l"):
        jid = "elbow_" + side
        q0 = pose_of(pg, jid)[0]
        res = pg.evaluate("""async (side) => { const P = window.__poseApi, sleep = ms => new Promise(r => setTimeout(r, ms)), out = [];
          const sec = [...document.querySelectorAll('#pz-body .pz-g')].filter(s => s.querySelector('.pz-gh').textContent === 'Elbow / forearm')[0];
          const row = [...sec.querySelectorAll('.pz-row')].filter(r => /Flexion/.test(r.querySelector('.pz-lab').textContent))[0];
          const cell = [...row.querySelectorAll('.pz-cell')].filter(c => c.querySelector('.pz-sd').textContent === side.toUpperCase())[0];
          const g = cell.querySelector('input[type=range]');
          const idx = window.__poseIndex(), hand = Object.keys(idx).filter(k => idx[k].layer === 'bone' && new RegExp('(radius|ulna).*_' + side + '$', 'i').test(k));
          for (const v of [120, 0, 150, 60]){ g.value = v; g.dispatchEvent(new Event('input', {bubbles: true})); await sleep(450); P.update();
            const d = window.__poseDebug().moved; out.push([v, P.pose().j['elbow_' + side][0], Math.max(0, ...hand.map(h => d[h] || 0))]); }
          return {out, hand}; }""", side)
        o = res["out"]
        check("%s: the slider turns the elbow to 120, 0 (full extension), 150, 60 -> %s" % (side.upper(), [x[1] for x in o]),
              [round(x[1]) for x in o] == [120, 0, 150, 60])
        check("%s: and the forearm bones follow (%s moved %s mm at those angles)" % (side.upper(), res["hand"], [x[2] for x in o]),
              res["hand"] and o[0][2] > 100 and o[2][2] > o[0][2] and o[1][2] > 5)
        pg.evaluate("() => window.__poseApi.reset()"); pg.wait_for_timeout(400)
    # the rings: from wherever the pointer comes, the elbow offers flexion
    pg.evaluate("() => window.__poseApi.open(false)")
    for side in ("r", "l"):
        jid, fid, wid = "elbow_" + side, "forearm_" + side, "wrist_" + side
        c = pg.evaluate("(j) => window.__q384.world(j)", jid)
        frame(pg, c, 1100.0)
        pe, pf, pw = [pg.evaluate("(j) => window.__q384.at(j)", x) for x in (jid, fid, wid)]
        pg.mouse.move(5, 300)
        # approach from the hand: the forearm joint's centre is met first
        n = 14
        for k in range(n + 1):
            pg.mouse.move(pw[0] + (pf[0] - pw[0]) * k / n, pw[1] + (pf[1] - pw[1]) * k / n); pg.wait_for_timeout(25)
        pg.wait_for_timeout(350)
        s = ring_state(pg)
        rings = s.get("rings") or [[s.get("joint"), r[0]] for r in (s.get("range") or [])]
        check("%s rings, pointer coming up the forearm from the wrist: a flexion ring is offered (rings: %s)" % (side.upper(), rings),
              [jid, "flex"] in [list(r) for r in rings])
        check("%s rings: forearm rotation is offered in the same set" % side.upper(), [fid, "sup"] in [list(r) for r in rings])
        # a real drag on the flexion ring
        gi = [i for i, r in enumerate(rings) if list(r) == [jid, "flex"]]
        g = pg.evaluate("(k) => window.__q384.grab(k)", gi[0]) if gi else None
        if check("%s rings: the flexion ring can be grabbed" % side.upper(), g and g["j"] == jid and len(g["pts"]) > 4):
            pts = g["pts"]; m = len(pts) // 2; q0 = pose_of(pg, jid)[0]
            pg.mouse.move(pts[m][0], pts[m][1]); pg.mouse.down()
            for k in range(1, 9):
                p = pts[min(len(pts) - 1, m + k)]; pg.mouse.move(p[0], p[1]); pg.wait_for_timeout(40)
            pg.mouse.up(); pg.wait_for_timeout(400)
            q1 = pose_of(pg, jid)[0]
            check("%s rings: dragging it turns the elbow (%.0f -> %.0f deg), not the forearm rotation" % (side.upper(), q0, q1), abs(q1 - q0) > 8)
            lim = pg.evaluate("""(k) => { const P = window.__poseApi, o = []; P.ringTurn(k, -1000); o.push(P.pose().j[P.ringState().rings[k][0]][0]); P.ringTurn(k, 1000); o.push(P.pose().j[P.ringState().rings[k][0]][0]); return o; }""", gi[0])
            check("%s rings: the ring runs from full extension to full flexion (%s)" % (side.upper(), lim), [round(x) for x in lim] == [0, 150])
        pg.evaluate("() => { const P = window.__poseApi; P.ringHold && P.ringHold(null); P.reset(); }"); pg.wait_for_timeout(300)
        pg.mouse.move(5, 300); pg.wait_for_timeout(200)


# ------------------------------------------------------------------------------------------------ D
def part_d_mouse(pg, shots=None, tag=""):
    print("D. the held joint, mouse 1400x900", flush=True)
    open_pose(pg, panel=False)
    frame(pg, [-80.0, -250.0, 0.0], 1500.0, az=-1.1)      # from the front the knee's one ring is edge-on: look from the side
    K, H, A = [pg.evaluate("(j) => window.__q384.at(j)", x) for x in ("knee_l", "hip_l", "ankle_l")]
    check("knee, hip and ankle are apart on the screen (%.0f / %.0f px)" % (np.hypot(K[0] - H[0], K[1] - H[1]), np.hypot(K[0] - A[0], K[1] - A[1])),
          np.hypot(K[0] - H[0], K[1] - H[1]) > 140)
    pg.mouse.move(K[0] + 30, K[1] + 4); pg.wait_for_timeout(120); pg.mouse.move(K[0] + 2, K[1] + 1); pg.wait_for_timeout(400)
    s = ring_state(pg)
    check("the pointer over the knee shows its rings (%s), nothing held yet" % s["joint"], s["joint"] == "knee_l" and not s.get("held"))
    pg.evaluate("() => window.NMSKHistory && NMSKHistory.commit()")      # whatever came before (the camera move) is its own step
    h0 = pg.evaluate("() => window.__q384.hist()")
    cam0 = pg.evaluate("() => window.__q338.cam()")
    pg.mouse.click(K[0], K[1]); pg.wait_for_timeout(400)
    s = ring_state(pg)
    held_ui = pg.evaluate("() => ({cls: document.getElementById('pz-rings').getAttribute('class'), lab: [...document.querySelectorAll('#pz-rings .pz-jlab')].map(t => t.textContent), halo: document.querySelectorAll('#pz-rings .pz-halo').length, status: document.getElementById('pz-status').textContent})")
    check("a click on the joint holds it (held = %s)" % s.get("held"), s.get("held") == "knee_l")
    check("and it is shown as held: halo, label %s, status %r" % (held_ui["lab"], held_ui["status"][:40]),
          held_ui["halo"] == 1 and any("held" in t for t in held_ui["lab"]) and "Holding" in held_ui["status"])
    cam1 = pg.evaluate("() => window.__q338.cam()")
    card = pg.evaluate("() => { const c = document.querySelector('.qc'); return !!(c && !c.hidden); }")
    check("the click reached neither the camera nor the picker (no name card opened)", not card and cam1 == cam0)
    # wander over the hip, the ankle and away
    for tgt in (H, A, [K[0] + 400, K[1] - 200], H):
        for k in range(1, 11):
            pg.mouse.move(K[0] + (tgt[0] - K[0]) * k / 10, K[1] + (tgt[1] - K[1]) * k / 10); pg.wait_for_timeout(20)
        pg.wait_for_timeout(260)
    s = ring_state(pg)
    check("the pointer wandered over the hip, the ankle and off the model: the knee still has the rings (%s, %d grab paths)" % (s["joint"], s["paths"]),
          s["joint"] == "knee_l" and s.get("held") == "knee_l" and s["paths"] >= 1)
    check("the hip under the pointer only offers its dot (peek = %s)" % s.get("peek"), s.get("peek") == "hip_l")
    if shots:
        pg.screenshot(path=str(Path(shots) / ("q384_D_held_%s_1400.png" % tag)))
    # a held drag that wanders over the hip
    g = pg.evaluate("() => window.__q384.grab(0)")
    q0, hq0 = pose_of(pg, "knee_l")[0], pose_of(pg, "hip_l")[:]
    pts = g["pts"]; m = len(pts) // 3
    pg.wait_for_timeout(1600)
    h1 = pg.evaluate("() => window.__q384.hist()")
    pg.mouse.move(pts[m][0], pts[m][1]); pg.mouse.down()
    for k in range(1, 7):
        p = pts[min(len(pts) - 1, m + k)]; pg.mouse.move(p[0], p[1]); pg.wait_for_timeout(30)
    qa = pose_of(pg, "knee_l")[0]
    for k in range(1, 9):
        pg.mouse.move(p[0] + (H[0] - p[0]) * k / 8, p[1] + (H[1] - p[1]) * k / 8); pg.wait_for_timeout(30)
    qb = pose_of(pg, "knee_l")[0]
    sd = ring_state(pg)
    pg.mouse.up(); pg.wait_for_timeout(1800)
    h2 = pg.evaluate("() => window.__q384.hist()")
    s = ring_state(pg)
    check("a drag on its ring turns the knee (%.0f -> %.0f) and keeps turning it while the pointer is over the hip (-> %.0f, dragging %s)" % (q0, qa, qb, sd["dragging"]),
          abs(qa - q0) > 5 and abs(qb - qa) > 1 and sd["dragging"] and sd["joint"] == "knee_l")
    check("the hip did not move (%s)" % pose_of(pg, "hip_l"), pose_of(pg, "hip_l") == hq0)
    check("after the drag the knee is still held", s.get("held") == "knee_l" and not s["dragging"])
    if h1 and h2:
        check("one held drag = one undo step (history %d -> %d; the hold click itself added %d)" % (h1["idx"], h2["idx"], h1["idx"] - h0["idx"]),
              h2["idx"] - h1["idx"] == 1 and h1["idx"] == h0["idx"])
        pg.evaluate("() => window.NMSKHistory.undo()"); pg.wait_for_timeout(700)
        check("and Undo takes the whole drag back (knee %.1f, was %.1f)" % (pose_of(pg, "knee_l")[0], q0), abs(pose_of(pg, "knee_l")[0] - q0) < 0.6)
    # a click on another joint switches
    pg.mouse.move(H[0] + 40, H[1] + 10); pg.wait_for_timeout(100); pg.mouse.move(H[0] + 3, H[1] + 2); pg.wait_for_timeout(350)
    Hn = pg.evaluate("(j) => window.__q384.at(j)", "hip_l")
    pg.mouse.click(Hn[0], Hn[1]); pg.wait_for_timeout(400)
    s = ring_state(pg)
    check("a click on another joint takes that one (held = %s, rings on %s)" % (s.get("held"), s["joint"]), s.get("held") == "hip_l" and s["joint"] == "hip_l")
    pg.mouse.click(Hn[0], Hn[1]); pg.wait_for_timeout(400)
    s = ring_state(pg)
    check("a second click on the held joint lets go (held = %s)" % s.get("held"), not s.get("held"))
    pg.mouse.move(K[0] + 300, K[1]); pg.wait_for_timeout(300)
    check("and the rings follow the pointer again (%s away from every joint)" % ring_state(pg)["joint"], ring_state(pg)["joint"] is None)
    Kn = pg.evaluate("(j) => window.__q384.at(j)", "knee_l")
    pg.mouse.move(Kn[0] + 2, Kn[1] + 2); pg.wait_for_timeout(300); pg.mouse.click(Kn[0], Kn[1]); pg.wait_for_timeout(300)
    a = ring_state(pg).get("held")
    pg.keyboard.press("Escape"); pg.wait_for_timeout(300)
    check("Escape lets go (held %s -> %s)" % (a, ring_state(pg).get("held")), a == "knee_l" and not ring_state(pg).get("held"))
    pg.evaluate("() => window.__poseApi.reset()"); pg.wait_for_timeout(300)


def part_d_touch(pl, d, shots=None, tag="", part="d"):
    print("D. the held joint, touch 390x844", flush=True)
    srv, port = V.serve(d)
    b = pl.chromium.launch(args=V.ARGS, executable_path="/opt/pw-browsers/chromium")
    try:
        ctx = b.new_context(viewport={"width": 390, "height": 844}, device_scale_factor=1, has_touch=True, is_mobile=True)
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: ERRS.append("page error (touch): " + str(e)))
        pg.route("**/*", V.route)
        html = sorted(d.glob("atlas_viewer*.html"))[0]
        pg.goto(f"http://127.0.0.1:{port}/{html.name}", wait_until="load", timeout=180000)
        pg.wait_for_function("window.__q338 && window.__poseApi", timeout=180000)
        try:
            pg.wait_for_selector('.mw-tile[data-mode="anat"]', timeout=120000)
            pg.evaluate("() => document.querySelector('.mw-tile[data-mode=\"anat\"]').click()")
            pg.wait_for_timeout(2500)
        except Exception:
            pass
        open_pose(pg, panel=False)
        cdp = ctx.new_cdp_session(pg)

        def touch(kind, x=None, y=None):
            cdp.send("Input.dispatchTouchEvent", {"type": kind, "touchPoints": [] if x is None else [{"x": x, "y": y}]})
        if "r" in part or "p" in part:
            import part_r_q384 as PRR
            PRR.part_touch(pg, check, frame, touch)
        if "d" not in part:
            ctx.close(); return
        open_pose(pg, panel=False)
        frame(pg, [-80.0, -250.0, 0.0], 2300.0, az=-1.1)
        pg.wait_for_timeout(500)
        s = ring_state(pg)
        dots = {x[0]: x[1:] for x in s.get("dots", [])}
        check("touch: with the rings on, the joints are offered as dots to tap (%d; knee %s, hip %s)" % (len(dots), "knee_l" in dots, "hip_l" in dots),
              s.get("touch") and "knee_l" in dots and "hip_l" in dots)
        if "knee_l" not in dots or "hip_l" not in dots:
            return
        u = pg.evaluate("(p) => window.__q384.under(p[0], p[1])", dots["knee_l"])
        check("touch: the knee's dot is on top at its place (%s)" % u, u and "pz-hit" in u)
        pg.touchscreen.tap(*dots["knee_l"]); pg.wait_for_timeout(500)
        s = ring_state(pg)
        check("touch: a tap on the knee holds it and draws its rings (held %s, %d grab paths)" % (s.get("held"), s["paths"]), s.get("held") == "knee_l" and s["paths"] >= 1)
        if shots:
            pg.screenshot(path=str(Path(shots) / ("q384_D_held_%s_390.png" % tag)))
        # a touch drag along the ring, then on over the hip
        g = pg.evaluate("() => window.__q384.grab(0)")
        pts = g["pts"]; m = len(pts) // 3; q0 = pose_of(pg, "knee_l")[0]; hq0 = pose_of(pg, "hip_l")[:]
        touch("touchStart", pts[m][0], pts[m][1])
        for k in range(1, 7):
            p = pts[min(len(pts) - 1, m + k)]; touch("touchMove", p[0], p[1]); pg.wait_for_timeout(30)
        qa = pose_of(pg, "knee_l")[0]      # along the handle; a bar (E2) reads the finger's way ALONG it, so the wander below may take the angle back
        Hp = dots["hip_l"]
        for k in range(1, 7):
            touch("touchMove", p[0] + (Hp[0] - p[0]) * k / 6, p[1] + (Hp[1] - p[1]) * k / 6); pg.wait_for_timeout(30)
        q1 = pose_of(pg, "knee_l")[0]; dragging = ring_state(pg)["dragging"]
        touch("touchEnd"); pg.wait_for_timeout(500)
        s = ring_state(pg)
        check("touch: a finger on the %s turns the knee (%.0f -> %.0f) and the knee stays the one being turned while the finger wanders over the hip (-> %.0f, dragging %s); hip unchanged; still held" % (
            "bar" if g.get("bar") else "ring", q0, qa, q1, dragging), abs(qa - q0) > 5 and dragging and pose_of(pg, "hip_l") == hq0 and s.get("held") == "knee_l")
        dots = {x[0]: x[1:] for x in s.get("dots", [])}
        if check("touch: the other joints keep their dots while one is held (hip %s)" % ("hip_l" in dots), "hip_l" in dots):
            pg.touchscreen.tap(*dots["hip_l"]); pg.wait_for_timeout(500)
            s = ring_state(pg)
            check("touch: a tap on another joint takes that one (held %s)" % s.get("held"), s.get("held") == "hip_l")
            dots = {x[0]: x[1:] for x in s.get("dots", [])}
            pg.touchscreen.tap(*dots["hip_l"]); pg.wait_for_timeout(500)
            s = ring_state(pg)
            check("touch: a second tap on the held joint lets go (held %s, %d grab paths)" % (s.get("held"), s["paths"]), not s.get("held") and s["paths"] == 0)
        ctx.close()
    finally:
        b.close(); srv.terminate()


def main() -> int:
    args = sys.argv[1:]
    d = Path(args[0]) if args and not args[0].startswith("--") else REPO / "build/q309/viewer_zan_atlas"
    if not d.is_absolute():
        d = REPO / d
    part = args[args.index("--part") + 1] if "--part" in args else "bcdeprh"
    shots = args[args.index("--shots") + 1] if "--shots" in args else None
    jf = args[args.index("--json") + 1] if "--json" in args else None
    tag = "F" if "female" in d.name else "M"
    if shots:
        Path(shots).mkdir(parents=True, exist_ok=True)
    from playwright.sync_api import sync_playwright
    tmp = Path(tempfile.mkdtemp(prefix="q384v_"))
    copy = PH.test_copy(d, tmp / d.name)
    out = {}
    try:
        with sync_playwright() as pl:
            srv, b, pg = PH.open_page(pl, copy, w=1400, h=900, errs=ERRS)
            try:
                if "c" in part:
                    part_c(pg)
                if "d" in part:
                    part_d_mouse(pg, shots, tag)
                if "b" in part:
                    import part_b_q384 as PB
                    out["b"] = PB.run(pg, d, check, shots, tag)
                if "r" in part or "p" in part:
                    import part_r_q384 as PRR
                    open_pose(pg, panel=False)
                    if "r" in part:
                        out["r"] = PRR.part_r(pg, check, frame)
                    if "p" in part:
                        PRR.part_p(pg, check, frame)
                if "h" in part:
                    import part_h_q384 as PH5
                    open_pose(pg, panel=False)
                    PH5.run(pg, check)
                if "e" in part:
                    import part_e_q384 as PE
                    pg.wait_for_function("window.__poseApi && __poseApi.ready()", timeout=180000)
                    pg.evaluate(JS_LIB)
                    out["e"] = PE.run(pg, d, check)
            finally:
                b.close(); srv.terminate()
            if "d" in part or "r" in part or "p" in part:
                part_d_touch(pl, copy, shots, tag, part)
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    if jf:
        Path(jf).write_text(json.dumps(out, indent=1, default=float), encoding="utf-8")
    for e in ERRS:
        print("  !! " + e)
    print("VERIFY_POSE_Q384_%s (%s, parts %s, %d failed)" % ("FAIL" if ERRS else "OK", d.name, part, len(ERRS)))
    return 1 if ERRS else 0


if __name__ == "__main__":
    raise SystemExit(main())
