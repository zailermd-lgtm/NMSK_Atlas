#!/usr/bin/env python3
"""Q383 (owner 7.2) -- the transducer is moved by hand ON the 3-D model.

    python3 scripts/anatomy/q383/verify_drag_q383.py PAGE_DIR [--size WxH] [--shots DIR]

Real input only (Playwright mouse at 1400x900, CDP touch points at 390x844), on a regenerated Base page, in the scan workspace:
  A  the drawn transducer has a screen target (hull of its housing) and a contact reference point that lies ON the skin mesh
  B  a press ON the transducer, held and moved: the transducer slides over the skin to the skin under the pointer (minus the press
     offset), the camera does not move, rotation and tilt keep their values, the image follows, the pad follows
  C  that drag is exactly ONE step of the page history: Undo puts the transducer back, Redo moves it again
  D  a press OUTSIDE the transducer, moved: the camera moves, the transducer stays where it is on the body
  E  a drag that leaves the body: the transducer stays on the skin at its last valid contact
  F  a tap on the skin still seats the transducer there (one step), no page error
Prints OK / FAIL lines and Q383_DRAG_OK / Q383_DRAG_FAIL."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common_q383 import U, Checks, dist, enter_scan, idle, open_page  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

STATE = f"""() => {{
  const U = {U}, s = U.state(), v = U.view(), h = window.NMSKHistory.state(), pi = U.probeInfo(), t = U.probeTarget(), hd = U.handles(), fr = U.frames()[s.sel] || U.frames()[0];
  let sum = 0; if (fr && fr.sim) {{ const d = fr.sim.db; for (let i = 0; i < d.length; i += 97) sum = (sum * 31 + Math.round(d[i] * 4)) | 0; }}
  return {{P: s.P, N: s.N, rot: s.rot, tilt: s.mTilt, dir: s.mTiltDir, eye: v.eye, target: v.target, idx: h.idx, len: h.len, gap: pi ? pi.gap : null, contact: pi ? pi.contact : null,
    hull: t ? t.hull : null, tip: t ? t.tip : null, tw: t ? t.w : 0, th: t ? t.h : 0, cw: t ? t.contact : null, pad: hd.shown, padRot: hd.rot, padTilt: hd.tilt, moves: hd.moves,
    O: fr ? fr.O : null, img: sum, hist: window.NMSKHistory.snapshot().us_probe || null, placing: s.placing}};
}}"""


def centroid(h):
    return [sum(p[0] for p in h) / len(h), sum(p[1] for p in h) / len(h)]


def on_canvas(pg, x, y):
    return pg.evaluate("([x, y]) => { const e = document.elementFromPoint(x, y); return !!e && e.tagName === 'CANVAS' && (e.id === 'view' || e.id === 'gl' || !!e.closest('#view, #app')); }", [x, y])


def gesture(pg, phone, a, b, n=8, hold=140):
    if phone:
        cdp = pg.context.new_cdp_session(pg)
        cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": a[0], "y": a[1], "id": 1}]})
        pg.wait_for_timeout(hold)
        for k in range(1, n + 1):
            f = k / n
            cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": a[0] + (b[0] - a[0]) * f, "y": a[1] + (b[1] - a[1]) * f, "id": 1}]})
            pg.wait_for_timeout(70)
        cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
        cdp.detach()
    else:
        pg.mouse.move(a[0], a[1]); pg.mouse.down(); pg.wait_for_timeout(hold)
        for k in range(1, n + 1):
            f = k / n
            pg.mouse.move(a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f); pg.wait_for_timeout(70)
        pg.mouse.up()
    pg.wait_for_timeout(500)


def skin_at(pg, x, y):
    return pg.evaluate(f"([x, y]) => {U}.skinAt(x, y)", [x, y])


def find_step(pg, st, press, reach):
    """a drag vector d (px): the contact point's destination tip + d has skin under it and both ends of the pointer path are on the canvas"""
    for r in (reach, reach * 0.7, reach * 1.4):
        for dx, dy in ((0, -1), (0, 1), (-0.7, -0.7), (0.7, -0.7), (-0.7, 0.7), (0.7, 0.7), (-1, 0), (1, 0)):
            d = [dx * r, dy * r]
            tip2 = [st["tip"][0] + d[0], st["tip"][1] + d[1]]
            if not on_canvas(pg, press[0] + d[0], press[1] + d[1]) or not on_canvas(pg, tip2[0], tip2[1]):
                continue
            p = skin_at(pg, tip2[0], tip2[1])
            if p and dist(p, st["P"]) > 4:
                return d
    return None


def find_outside(pg, st, reach):
    """a press point on the 3-D canvas that is NOT on the transducer (hit test null), with room to move"""
    cx, cy = centroid(st["hull"])
    for r in (90, 70, 120, 50, 150, 36):
        for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0), (0.7, 0.7), (-0.7, 0.7), (0.7, -0.7), (-0.7, -0.7)):
            a = [cx + dx * r, cy + dy * r]; b = [a[0] + reach, a[1]]
            if on_canvas(pg, a[0], a[1]) and on_canvas(pg, b[0], b[1]) and not pg.evaluate(f"([x, y, t]) => {U}.probeHit(x, y, t)", [a[0], a[1], False]):
                return a, b
    return None, None


def run(pg, T, check, phone, shots, tag):
    st = pg.evaluate(STATE)
    check(f"{T} A the drawn transducer has a screen target ({st['tw']:.0f} x {st['th']:.0f} px hull, {len(st['hull'] or [])} corners) and its contact point is on the 3-D view",
          st["hull"] and len(st["hull"]) >= 3 and st["tip"] and on_canvas(pg, st["tip"][0], st["tip"][1]))
    if not st["hull"]:
        return
    under = skin_at(pg, st["tip"][0], st["tip"][1])
    off = dist(under, st["cw"]) if under else None
    check(f"{T} A the contact reference point lies on the skin mesh (skin under its screen position {('%.2f' % off) if off is not None else 'none'} mm away, face-to-skin gap "
          f"{('%.2f' % st['gap']) if st['gap'] is not None else 'none'} mm, tolerance 1.5)", off is not None and off <= 1.5 and st["gap"] is not None and abs(st["gap"]) <= 1.5)
    ov = dict(pg.evaluate(f"() => {U}.overlayItems()") or [])
    check(f"{T} A the contact reference point is drawn (overlay 'contact' {ov.get('contact', 0)} + rim {ov.get('contactRim', 0)} triangles)", ov.get("contact", 0) > 0 and ov.get("contactRim", 0) > 0)
    hit_tip = pg.evaluate(f"([x, y, t]) => {U}.probeHit(x, y, t)", [st["tip"][0], st["tip"][1], phone])
    check(f"{T} A the hit test takes a press at the contact point and one at the middle of the housing", bool(hit_tip) and bool(pg.evaluate(f"([x, y, t]) => {U}.probeHit(x, y, t)", centroid(st["hull"]) + [phone])))

    # ---- B: press ON the transducer and drag
    press = centroid(st["hull"])
    reach = max(14.0, min(60.0, 2.2 * max(st["tw"], st["th"])))
    d = find_step(pg, st, press, reach)
    if not check(f"{T} B a destination on the skin next to the transducer ({d})", d is not None):
        return
    if shots:
        pg.screenshot(path=str(shots / f"q383_drag_{tag}_0_before.png"))
    gesture(pg, phone, press, [press[0] + d[0], press[1] + d[1]])
    idle(pg)
    s1 = pg.evaluate(STATE)
    if shots:
        pg.screenshot(path=str(shots / f"q383_drag_{tag}_1_after.png"))
    want = skin_at(pg, st["tip"][0] + d[0], st["tip"][1] + d[1])
    moved = dist(s1["P"], st["P"]); err = dist(s1["P"], want) if want else None
    cam = dist(s1["eye"], st["eye"]) + dist(s1["target"], st["target"])
    check(f"{T} B a {'touch' if phone else 'mouse'} press on the transducer, held and moved {d[0]:.0f},{d[1]:.0f} px: the transducer moved {moved:.1f} mm over the skin ({s1['moves']} live moves)", moved > 2 and s1["moves"] >= 2)
    check(f"{T} B the contact point followed the pointer's ray onto the skin (off the skin point under the pointer by {('%.2f' % err) if err is not None else 'none'} mm, tolerance 1.0)", err is not None and err <= 1.0)
    check(f"{T} B the camera did not move (eye + target moved {cam:.4f} mm)", cam < 1e-3)
    check(f"{T} B the transducer sits on the skin there (gap {('%.2f' % s1['gap']) if s1['gap'] is not None else 'none'} mm, skin contact {s1['contact']})", s1["gap"] is not None and abs(s1["gap"]) <= 1.5 and s1["contact"])
    check(f"{T} B rotation and tilt kept ({s1['rot']}° / {s1['tilt']}° toward {s1['dir']}°; the pad reads {s1['padRot']}° / {s1['padTilt']}°)",
          s1["rot"] == st["rot"] and s1["tilt"] == st["tilt"] and s1["dir"] == st["dir"] and s1["padRot"] == s1["rot"] and s1["padTilt"] == s1["tilt"])
    check(f"{T} B the image follows: the selected frame is taken at the new contact ({dist(s1['O'], s1['P']):.3f} mm) and its pixels changed", dist(s1["O"], s1["P"]) < 0.01 and s1["img"] != st["img"])

    # ---- C: one undo step
    check(f"{T} C the drag is ONE step of the page history (entry {st['idx']} -> {s1['idx']})", s1["idx"] == st["idx"] + 1 and s1["hist"] is not None)
    pg.evaluate("() => window.NMSKHistory.undo()"); idle(pg)
    s2 = pg.evaluate(STATE)
    check(f"{T} C Undo: the transducer is back where it was ({dist(s2['P'], st['P']):.3f} mm), the camera unchanged", dist(s2["P"], st["P"]) < 0.01 and dist(s2["eye"], s1["eye"]) < 1e-3 and s2["idx"] == st["idx"])
    pg.evaluate("() => window.NMSKHistory.redo()"); idle(pg)
    s3 = pg.evaluate(STATE)
    check(f"{T} C Redo: at the dragged place again ({dist(s3['P'], s1['P']):.3f} mm)", dist(s3["P"], s1["P"]) < 0.01 and s3["idx"] == s1["idx"])

    # ---- D: press OUTSIDE the transducer
    a, b = find_outside(pg, s3, 46 if not phone else 30)
    if check(f"{T} D a press point on the 3-D view that is not on the transducer ({a})", a is not None):
        gesture(pg, phone, a, b)
        idle(pg)
        s4 = pg.evaluate(STATE)
        cam4 = dist(s4["eye"], s3["eye"]) + dist(s4["target"], s3["target"])
        check(f"{T} D a press outside the transducer, moved: the camera moved ({cam4:.1f} mm) and the transducer stayed on the body ({dist(s4['P'], s3['P']):.3f} mm)", cam4 > 1 and dist(s4["P"], s3["P"]) < 0.01)
        check(f"{T} D ... and that is no transducer step in the history (us_probe unchanged)", s4["hist"] == s3["hist"])
    else:
        s4 = s3

    # ---- E: a drag that leaves the body
    s4 = pg.evaluate(STATE)
    press = centroid(s4["hull"]); out = None
    for dx, dy in ((1, 0), (-1, 0), (0, -1), (0, 1)):
        for r in (60, 90, 130, 180, 240):
            q = [s4["tip"][0] + dx * r, s4["tip"][1] + dy * r]; pp = [press[0] + dx * r, press[1] + dy * r]
            if on_canvas(pg, pp[0], pp[1]) and on_canvas(pg, q[0], q[1]) and not skin_at(pg, q[0], q[1]):
                out = [dx * r, dy * r]; break
        if out:
            break
    if out is None:
        print(f"     {T} E skipped: no point without skin within reach of the transducer on this view")
    else:
        gesture(pg, phone, press, [press[0] + out[0], press[1] + out[1]], n=10)
        idle(pg)
        s5 = pg.evaluate(STATE)
        check(f"{T} E a drag that ends off the body ({out[0]:.0f},{out[1]:.0f} px): the transducer stays on the skin at its last valid contact (moved {dist(s5['P'], s4['P']):.1f} mm, "
              f"gap {('%.2f' % s5['gap']) if s5['gap'] is not None else 'none'} mm, contact {s5['contact']}), the camera did not move",
              s5["gap"] is not None and abs(s5["gap"]) <= 1.5 and s5["contact"] and dist(s5["eye"], s4["eye"]) < 1e-3)
        check(f"{T} E ... one more history step at most ({s4['idx']} -> {s5['idx']})", s5["idx"] - s4["idx"] in (0, 1))

    # ---- F: a tap on the skin still seats the transducer
    s6 = pg.evaluate(STATE)
    tp = None
    for dx, dy in ((0, 1), (0, -1), (1, 0), (-1, 0)):
        for r in (40, 60, 28):
            q = [s6["tip"][0] + dx * r, s6["tip"][1] + dy * r]
            if on_canvas(pg, q[0], q[1]) and skin_at(pg, q[0], q[1]) and not pg.evaluate(f"([x, y, t]) => {U}.probeHit(x, y, t)", [q[0], q[1], phone]):
                tp = q; break
        if tp:
            break
    if tp and s6["placing"]:
        want = skin_at(pg, tp[0], tp[1])
        if phone:
            pg.touchscreen.tap(tp[0], tp[1])
        else:
            pg.mouse.click(tp[0], tp[1])
        pg.wait_for_timeout(700); idle(pg)
        s7 = pg.evaluate(STATE)
        check(f"{T} F a tap on the skin beside the transducer seats it there ({dist(s7['P'], want):.2f} mm from the tapped skin point) as one history step ({s6['idx']} -> {s7['idx']})",
              dist(s7["P"], want) <= 1.0 and s7["idx"] == s6["idx"] + 1)
    else:
        print(f"     {T} F skipped: no free skin point beside the transducer (placing armed: {s6['placing']})")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("build_dir")
    ap.add_argument("--size", default="1400x900")
    ap.add_argument("--shots", default=None)
    a = ap.parse_args()
    d = Path(a.build_dir).resolve()
    W, H = (int(x) for x in a.size.split("x"))
    phone = W <= 500
    shots = Path(a.shots) if a.shots else None
    if shots:
        shots.mkdir(parents=True, exist_ok=True)
    check = Checks(); page_errors: list[str] = []
    print(f"=== Q383 drag: {d.name} @ {W}x{H} ===")
    with sync_playwright() as pl:
        srv, b, pg = open_page(pl, d, W, H, page_errors)
        try:
            enter_scan(pg)
            if phone:        # the phone shows the model as a 92 px thumbnail: the scan workspace's own switch gives it the picture area
                pg.evaluate("() => { const b = document.querySelector('.mm-swap-btn'); if (b && b.getAttribute('aria-pressed') !== 'true') b.click(); }")
                pg.wait_for_timeout(900); idle(pg)
            # bring the transducer to a comfortable size in the view (the camera tool of the tool itself: "Zoom to probe")
            pg.evaluate(f"() => {{ const U = {U}, s = U.state(); U.focusOn(s.P, 620); }}")
            pg.wait_for_timeout(1200); idle(pg)
            run(pg, f"[{d.name} {W}x{H} scan workspace]", check, phone, shots, f"{d.name}_{W}x{H}_mode")
            if not phone:
                # the thumbnail-sized transducer of the workspace's default view: still a usable target (minimum size rule)
                pg.evaluate(f"() => {{ const U = {U}, s = U.state(); U.focusOn(s.P, 2600); }}")
                pg.wait_for_timeout(1200); idle(pg)
                run(pg, f"[{d.name} {W}x{H} scan workspace, transducer small]", check, phone, shots, f"{d.name}_{W}x{H}_small")
        finally:
            b.close(); srv.terminate()
    check(f"no page error ({page_errors[:2]})", not page_errors)
    print(f"{check.n - len(check.errs)} OK, {len(check.errs)} FAIL")
    print("Q383_DRAG_OK" if not check.errs else "Q383_DRAG_FAIL")
    return 0 if not check.errs else 1


if __name__ == "__main__":
    sys.exit(main())
