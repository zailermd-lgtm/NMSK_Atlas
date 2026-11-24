"""Q387: the camera orbit is unlimited in both directions (Base pages, Z engine).

Owner, 2026-11-22/23: "360 degrees and more without limiting" -- for the CAMERA; the joints keep their own ranges.
Drags (real mouse on a desktop viewport, real touch through CDP on a phone viewport) a full 360 and a 720 degree loop
vertically and horizontally and checks, frame by frame:
  - no clamp: the elevation goes past +-pi/2 and on round, and past the pole the picture is upside-down (world +Y points
    down on the screen) -- read from the projection, not from the angle;
  - continuity: no frame jumps (the screen right vector and a probe point move by at most one drag step's worth);
  - after a whole loop the view is the one it started from and a pick at the canvas centre returns the same structure;
  - the orientation marker (R / L ...) agrees with where the patient's sides really project, upside-down too;
  - a horizontal drag carries the surface with the pointer upright AND upside-down; pan (right button / two fingers)
    moves the model with the pointer when upside-down; the wheel / pinch zooms without changing the orientation;
  - front / side / back and Reset return to the exact standard view; a saved view stores az / el in (-pi, pi] and
    brings the same picture back, and Undo takes it away again;
  - the pose rig is untouched: its ranges are the same before and after, and a joint driven past its limit still
    stops at the limit.

  python3 scripts/anatomy/q387/verify_camera_q387.py <page dir> [--size 390x844]   -> Q387_CAMERA_OK / Q387_CAMERA_FAIL
"""
import sys, json, math, shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "q321"))
import verify_quickcard_q321 as Q
from playwright.sync_api import sync_playwright

K = 0.0065          # radians per CSS pixel of drag (the engine's orbit gain)

FRAME = """() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(() => {
  const c = __q339.cam(), R = __q339.right(), T = window.__q334, H = T.cam().H, t = c.tgt;
  const pt = (d) => T.toScreen([t[0] + d[0] * H, t[1] + d[1] * H, t[2] + d[2] * H]);
  const ce = Math.cos(c.el), e = [ce * Math.sin(c.az), Math.sin(c.el), ce * Math.cos(c.az)];
  r({az: c.az, el: c.el, dist: c.dist, tgt: t, H: H, eye: e, right: R, orient: __q339.orient(), o: pt([0, 0, 0]),
     up: pt([0, 0.15, 0]), px: pt([0.15, 0, 0]), py: pt([0, 0.15, 0]), pz: pt([0, 0, 0.15]), probe: pt([0.12, 0.08, 0.05])});
})))"""

FREE = """() => { const cv = __q339.api().canvas, r = cv.getBoundingClientRect(), cx = r.left + r.width / 2, cy = r.top + r.height / 2;
  for (let k = 0; k < 40; k++) { const a = k * 2.4, d = k * 6, x = cx + Math.cos(a) * d, y = cy + Math.sin(a) * d;
    if (document.elementFromPoint(x, y) === cv) return {x, y, w: r.width, h: r.height, l: r.left, t: r.top}; }
  return null; }"""

POSE = """() => { const P = window.__poseApi, rig = P.rig();
  return JSON.stringify({rom: rig.rom || null, j: rig.joints.map(j => [j.id, (j.dof || []).map(d => [d.k, d.lo, d.hi])])}); }"""

CLAMP = """() => { const P = window.__poseApi, rig = P.rig(), out = [];
  const want = ['knee_l', 'elbow_r', 'hip_l', 'shoulder_r'];
  let js = rig.joints.filter(j => want.indexOf(j.id) >= 0 && !j.driven && j.dof && j.dof.length);
  if (!js.length) js = rig.joints.filter(j => !j.driven && j.dof && j.dof.length).slice(0, 4);
  for (const j of js) { const d = j.dof[0];
    P.set(j.id, d.k, d.hi + 1000); const a = P.pose().j[j.id][0];
    P.set(j.id, d.k, d.lo - 1000); const b = P.pose().j[j.id][0];
    out.push({id: j.id, k: d.k, lo: d.lo, hi: d.hi, atHi: a, atLo: b}); }
  P.reset(); return out; }"""


def ang(a, b):
    d = (a - b) % (2 * math.pi)
    return d - 2 * math.pi if d > math.pi else d


def main():
    a = sys.argv[1:]; src = Path(a[0]); w, h = 1400, 900
    if "--size" in a: w, h = [int(x) for x in a[a.index("--size") + 1].split("x")]
    phone = w <= 500
    d = Q.page_copy(src, False); bad = 0

    def say(ok, msg):
        nonlocal bad
        print(("  OK   " if ok else "  FAIL ") + msg, flush=True); bad += 0 if ok else 1

    with sync_playwright() as pl:
        if phone:       # a touch device: real touch points through CDP, the page sees pointerType "touch"
            srv, port = Q.V.serve(d)
            b = pl.chromium.launch(args=Q.V.ARGS, executable_path="/opt/pw-browsers/chromium")
            ctx = b.new_context(viewport={"width": w, "height": h}, has_touch=True, is_mobile=True, device_scale_factor=2)
            pg = ctx.new_page(); pg.on("pageerror", lambda e: Q.V.ERRS.append("page error: " + str(e))); pg.route("**/*", Q.V.route)
            html = sorted(d.glob("atlas_viewer*.html"))[0]
            pg.goto(f"http://127.0.0.1:{port}/{html.name}", wait_until="load", timeout=90000)
            pg.wait_for_function("window.NMSKQ301 && window.NMSKQ298 && window.NMSKSelectCtl", timeout=90000)
            try:
                pg.wait_for_selector('.mw-tile[data-mode="anat"]', timeout=120000); pg.tap('.mw-tile[data-mode="anat"]'); pg.wait_for_timeout(3000)
            except Exception:
                print("     (no mode wall to dismiss)")
            cdp = ctx.new_cdp_session(pg)
        else:
            srv, b, pg = Q.V.open_page(pl, d, w, h); cdp = None
        try:
            Q.wait_ready(pg)
            pg.wait_for_function("window.__q339 && window.__q334 && window.__poseApi && __poseApi.ready()", timeout=180000)
            frame = lambda: pg.evaluate(FRAME)
            scr = lambda p: pg.evaluate("(p) => new Promise(r => requestAnimationFrame(() => r(__q334.toScreen(p))))", p)

            def near(f):
                """a FIXED world point between the target and the eye of frame f (the surface facing the viewer)"""
                return [f["tgt"][i] + f["eye"][i] * 0.12 * f["H"] for i in range(3)]

            def reset():
                pg.evaluate("() => __q334.cam({})")        # stops the idle spin first, so the reset view is not turned by a frame
                pg.keyboard.press("r"); pg.wait_for_timeout(400)
            pose0 = pg.evaluate(POSE)
            pg.evaluate("() => { document.activeElement && document.activeElement.blur && document.activeElement.blur(); }")
            reset(); f0 = frame(); P0 = pg.evaluate(FREE)
            say(P0 is not None, "a free point on the canvas to drag from  %s" % json.dumps(P0))
            if P0 is None:
                raise RuntimeError("no free canvas point")
            cx, cy = P0["x"], P0["y"]
            ccx, ccy = P0["w"] / 2, P0["h"] / 2           # canvas-relative centre for picks
            pick = lambda: pg.evaluate("([x, y]) => __q334.pickAt(x, y)", [ccx, ccy])

            def touch(pts, kind):
                cdp.send("Input.dispatchTouchEvent", {"type": kind, "touchPoints": [{"x": p[0], "y": p[1], "id": i} for i, p in enumerate(pts)]})

            def stroke(dx, dy, n, rec=None, button="left", fingers=1):
                """one drag of (dx, dy) CSS px in n steps from the free point; rec collects a frame after every step"""
                if phone:
                    off = [(0, 0)] if fingers == 1 else [(-40, 0), (40, 0)]
                    touch([(cx + o[0], cy + o[1]) for o in off], "touchStart")
                    for i in range(1, n + 1):
                        touch([(cx + o[0] + dx * i / n, cy + o[1] + dy * i / n) for o in off], "touchMove")
                        if rec is not None: rec.append(frame())
                    touch([], "touchEnd")
                else:
                    pg.mouse.move(cx, cy); pg.mouse.down(button=button)
                    for i in range(1, n + 1):
                        pg.mouse.move(cx + dx * i / n, cy + dy * i / n)
                        if rec is not None: rec.append(frame())
                    pg.mouse.up(button=button)
                pg.wait_for_timeout(120)

            def loop(total, vertical, rec):
                left, seg = total, 240
                while left > 0:
                    s = min(seg, left); n = max(1, int(round(s / 12)))
                    stroke(0 if vertical else s, s if vertical else 0, n, rec)
                    left -= s

            def jumps(rec, prev):
                """largest per-frame change of the screen right vector (rad) and of the probe point (px)"""
                mr, mp = 0.0, 0.0
                for f in rec:
                    r0, r1 = prev["right"], f["right"]
                    c = max(-1, min(1, sum(x * y for x, y in zip(r0, r1)) / (math.hypot(*r0) * math.hypot(*r1))))
                    mr = max(mr, math.acos(c))
                    if prev["probe"] and f["probe"]:
                        mp = max(mp, math.hypot(f["probe"][0] - prev["probe"][0], f["probe"][1] - prev["probe"][1]))
                    prev = f
                return mr, mp

            def orient_ok(f):
                """the marker's right-hand letter really projects to the right of the target"""
                k = f["orient"]
                if len(k) != 2: return False
                dirs = {"R": ("px", 1), "L": ("px", -1), "S": ("py", 1), "I": ("py", -1), "A": ("pz", 1), "P": ("pz", -1)}
                key, sg = dirs[k[1]]
                return f[key] is not None and sg * (f[key][0] - f["o"][0]) > 0

            def upside(f):
                return f["up"][1] > f["o"][1]          # world +Y drawn BELOW the target on the screen

            # ---- vertical loops: 360 and 720 degrees over the poles ----
            px_loop = int(round(2 * math.pi / K))     # 967 px = 2 pi + 0.0018 rad
            for turns in (1, 2):
                reset()
                s0 = frame(); id0 = pick(); rec = []
                loop(px_loop * turns, True, rec)
                s1 = frame(); id1 = pick()
                els = [f["el"] for f in rec]
                say(max(els) - s0["el"] > 2 * math.pi * turns - 0.05, "vertical %d deg: no clamp, el ran %.3f -> %.3f rad (max %.3f)" % (360 * turns, s0["el"], s1["el"], max(els)))
                flips = [f for f in rec if math.cos(f["el"]) < -0.3]
                up_ok = [f for f in rec if abs(math.cos(f["el"])) > 0.3 and upside(f) != (math.cos(f["el"]) < 0)]
                say(len(flips) > 0 and not up_ok, "vertical %d deg: past the pole the picture is upside-down (%d frames with cos el < -0.3, %d with the wrong up)" % (360 * turns, len(flips), len(up_ok)))
                mr, mp = jumps(rec, s0)
                lim = 12 * K * 1.6
                say(mr < lim and mp < 0.05 * P0["h"], "vertical %d deg: continuous, max right-vector step %.4f rad (< %.3f), max probe step %.1f px" % (360 * turns, mr, lim, mp))
                say(abs(ang(s1["el"], s0["el"])) < 0.01 and abs(ang(s1["az"], s0["az"])) < 1e-9, "vertical %d deg: back where it started (d el %.4f, d az %.2e)" % (360 * turns, ang(s1["el"], s0["el"]), ang(s1["az"], s0["az"])))
                say(id0 is not None and id0 == id1, "vertical %d deg: the pick at the centre is the same structure (%s / %s)" % (360 * turns, id0, id1))
                bad_or = [f["orient"] for f in rec if not orient_ok(f)]
                say(not bad_or, "vertical %d deg: the R / L marker matches the projection in every frame (%d wrong %s)" % (360 * turns, len(bad_or), bad_or[:3]))

            # ---- horizontal loops ----
            for turns in (1, 2):
                reset()
                s0 = frame(); id0 = pick(); rec = []
                loop(px_loop * turns, False, rec)
                s1 = frame(); id1 = pick()
                say(abs(s1["az"] - s0["az"]) > 2 * math.pi * turns - 0.05, "horizontal %d deg: az ran %.3f -> %.3f rad" % (360 * turns, s0["az"], s1["az"]))
                mr, mp = jumps(rec, s0)
                say(mr < 12 * K * 1.6, "horizontal %d deg: continuous, max right-vector step %.4f rad, max probe step %.1f px" % (360 * turns, mr, mp))
                say(abs(ang(s1["az"], s0["az"])) < 0.01 and abs(s1["el"] - s0["el"]) < 1e-9, "horizontal %d deg: back where it started" % (360 * turns))
                say(id0 is not None and id0 == id1, "horizontal %d deg: the pick at the centre is the same structure (%s / %s)" % (360 * turns, id0, id1))
                bad_or = [f["orient"] for f in rec if not orient_ok(f)]
                say(not bad_or, "horizontal %d deg: the R / L marker matches the projection in every frame (%d wrong)" % (360 * turns, len(bad_or)))

            # ---- the surface follows the pointer, upright and upside-down; pan when upside-down ----
            reset()
            a = frame(); P = near(a); x0 = scr(P)[0]; stroke(30, 0, 3); x1 = scr(P)[0]
            say(x1 > x0 + 3, "upright: a drag to the right carries the near surface right (%.1f -> %.1f)" % (x0, x1))

            def pan_move():
                f = frame(); q0 = scr(f["tgt"])
                stroke(70, 50, 7, fingers=2) if phone else stroke(70, 50, 7, button="right")
                q1 = scr(f["tgt"]); return q1[0] - q0[0], q1[1] - q0[1]
            ux, uy = pan_move()        # upright reference: the mouse pan has its own gain (cam.dist * 0.0016 per px), the touch pan is 1:1
            stroke(0, int(round(math.pi / K)), 20)       # over the top to upside-down
            a = frame()
            say(math.cos(a["el"]) < -0.9 and upside(a), "half a vertical turn: upside-down (el %.3f)" % a["el"])
            P = near(a); x0 = scr(P)[0]; stroke(30, 0, 3); x1 = scr(P)[0]
            say(x1 > x0 + 3, "upside-down: a drag to the right still carries the near surface right (%.1f -> %.1f)" % (x0, x1))
            ddx, ddy = pan_move(); b2 = frame()
            kx, ky = (1.0, 1.0) if phone else (ux / 70.0, uy / 50.0)
            say(ux > 0 and uy > 0 and abs(ddx - 70 * kx) < 0.12 * 70 * kx and abs(ddy - 50 * ky) < 0.12 * 50 * ky,
                "upside-down: %s moves the model with the pointer (%.1f, %.1f) for (70, 50); upright (%.1f, %.1f)" % ("two-finger pan" if phone else "right-button pan", ddx, ddy, ux, uy))
            r0 = b2["right"]
            if phone:
                touch([(cx - 60, cy), (cx + 60, cy)], "touchStart")
                for i in range(1, 6): touch([(cx - 60 - 8 * i, cy), (cx + 60 + 8 * i, cy)], "touchMove")
                touch([], "touchEnd")
            else:
                pg.mouse.move(cx, cy); pg.mouse.wheel(0, 300)
            pg.wait_for_timeout(250); c2 = frame()
            same = sum(x * y for x, y in zip(r0, c2["right"])) / (math.hypot(*r0) * math.hypot(*c2["right"]))
            say(abs(c2["dist"] - b2["dist"]) > 1e-6 and same > 0.99999 and upside(c2), "upside-down: %s zooms (dist %.1f -> %.1f) and keeps the orientation" % ("pinch" if phone else "wheel", b2["dist"], c2["dist"]))

            # ---- saved view (stored wrapped) + undo ----
            stroke(0, px_loop + 300, 40)            # raw el now beyond 2 pi
            sv = frame()
            on = pg.evaluate("() => !!(window.NMSKViews && NMSKViews.state().on)")
            if on:
                rec = pg.evaluate("() => NMSKViews.save('q387 test')")
                c = rec["cam"] if rec else None
                say(c is not None and -math.pi < c["az"] <= math.pi and -math.pi < c["el"] <= math.pi, "a saved view stores az / el in (-pi, pi]  %s (raw el %.3f)" % (c and [round(c["az"], 4), round(c["el"], 4)], sv["el"]))
                stroke(120, 80, 8); mid = frame()
                pg.evaluate("() => NMSKViews.apply('q387 test')"); pg.wait_for_timeout(300); ap = frame()
                dd = math.hypot(ap["probe"][0] - sv["probe"][0], ap["probe"][1] - sv["probe"][1]) + math.hypot(ap["up"][0] - sv["up"][0], ap["up"][1] - sv["up"][1])
                say(dd < 0.5, "applying it brings the same picture back, upside-down included (%.3f px)" % dd)
                pg.evaluate("() => NMSKHistory.undo()"); pg.wait_for_timeout(400); un = frame()
                du = math.hypot(un["probe"][0] - mid["probe"][0], un["probe"][1] - mid["probe"][1])
                say(du < 0.5, "Undo takes the applied view back (%.3f px)" % du)
                pg.evaluate("() => NMSKViews.del && NMSKViews.del('q387 test')")
            else:
                print("     (the saved-views control is off on this page: skipped)")

            # ---- presets and reset are exact ----
            ref = {}
            for v, az in (("front", 0.0), ("side", math.pi / 2), ("back", math.pi)):
                stroke(0, 400, 10); stroke(200, 0, 8)          # somewhere upside-down / turned
                pg.evaluate("(v) => document.querySelector('[data-view=' + v + ']').click()", v); f = frame()
                exp_r = [-math.cos(az), 0.0, math.sin(az)]     # the screen right of el = 0 (Q339's handedness: -x of the look-at)
                er = max(abs(x - y) for x, y in zip(f["right"], exp_r))
                say(f["az"] == az and f["el"] == 0 and er < 1e-6 and not upside(f) and orient_ok(f), "%s preset: exact (az %.6f el %.6f, right err %.1e, marker %s)" % (v, f["az"], f["el"], er, f["orient"]))
            stroke(0, 700, 20)
            reset(); f = frame()
            dd = max(abs(f[k] - f0[k]) for k in ("az", "el", "dist")) + max(abs(x - y) for x, y in zip(f["tgt"], f0["tgt"]))
            dp = math.hypot(f["probe"][0] - f0["probe"][0], f["probe"][1] - f0["probe"][1])
            say(dd == 0 and dp < 0.01, "Reset returns to the exact standard view (cam diff %.2e, probe %.4f px)" % (dd, dp))

            # ---- the pose rig is untouched ----
            pose1 = pg.evaluate(POSE)
            say(pose0 == pose1, "the pose rig's ranges are the same before and after the camera loops (%d chars)" % len(pose0))
            cl = pg.evaluate(CLAMP)
            okc = cl and all(abs(x["atHi"] - x["hi"]) < 1e-9 and abs(x["atLo"] - x["lo"]) < 1e-9 for x in cl)
            say(bool(okc), "a joint driven past its limit still stops at it  %s" % json.dumps(cl))
            say(not Q.V.ERRS, "no page errors %s" % Q.V.ERRS[:2])
        finally:
            b.close(); srv.terminate()
    shutil.rmtree(d, ignore_errors=True)
    print("Q387_CAMERA_OK" if not bad else "Q387_CAMERA_FAIL %d" % bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
