"""Q384 verifier, parts R (E1 + E2: every permitted axis can be turned from every direction of view) and P (E4: the panel's
"This joint only" view and its tile). See verify_pose_q384.py.

Owner, 2026-11-22: "the elbow needs an option for extension and flexion. At the shoulder the rings are very far away and, to
reach them, the pointer passes over other joints' rings, and the shoulder rings disappear [this changes if I rotate the
figure] -- it must be possible, in every pose, to rotate on the permitted axes." / "the POSE window takes half the screen:
it must be possible to see only the joint I am pointing at and changing, as one of the options, and to shrink it right down
to a small tile without closing POSE."

R measures, for the big joints of both sides and a thumb and a finger joint, in the six standard views and three fixed
oblique ones: is the hub on the screen; does EVERY axis of the joint have a handle (a ring, or a bar where the ring is seen
edge-on); how far out is the inner ring (px) against the distance to the nearest other joint's hub; how many other hubs lie
inside it. Then real drags: the knee's bar from the front, the elbow's flexion handle from the front, the back and an
oblique view."""
from __future__ import annotations

import math

import numpy as np

JOINTS = ["shoulder", "elbow", "wrist", "hip", "knee", "ankle", "thumb_cmc", "f3_mcp"]
VIEWS = [("front", 0.0, 0.05), ("back", math.pi, 0.05), ("left", -math.pi / 2, 0.05), ("right", math.pi / 2, 0.05), ("top", 0.0, 1.35), ("bottom", 0.0, -1.35),
         ("oblique1", 0.7, 0.4), ("oblique2", -2.1, -0.3), ("oblique3", 2.6, 0.8)]
CAP, FLOOR, SHARE = 52.0, 20.0, 0.42

JS_MEASURE = """(ids) => { const P = window.__poseApi, Q = window.__q384, W = innerWidth, H = innerHeight, out = [];
  const leads = P.rig().joints.filter(j => !j.driven && j.dof && j.dof.length).map(j => j.id);
  const pos = {}; for (const id of leads){ const a = Q.at(id); if (a) pos[id] = a; }
  for (const id of ids){
    const a = pos[id]; if (!a || a[0] < 8 || a[1] < 8 || a[0] > W - 8 || a[1] > H - 8){ out.push({id, on: false}); continue; }
    const held = P.ringHold(id), s = P.ringState();
    const mine = new Set(s.rings.map(r => r[0]));
    let near = 1e9, inside = 0; const r0 = s.px ? s.px[0] : 0;
    for (const o in pos){ if (mine.has(o)) continue; const d = Math.hypot(pos[o][0] - a[0], pos[o][1] - a[1]); if (d > 1 && d < near) near = d; }
    for (const o of s.dots || []){ if (!mine.has(o[0]) && Math.hypot(o[1] - a[0], o[2] - a[1]) < r0 - 0.5) inside++; }
    out.push({id, on: true, held, axes: s.rings.length, handles: s.handles.length, bars: s.handles.filter(h => h.bar).length, r0, near, inside,
              missing: s.rings.filter((r, k) => !s.handles.some(h => h.k === k)).map(r => r[1])});
    P.ringHold(null);
  }
  return out; }"""


def _handle(pg, jid, key):
    """the grab element of one axis of the held / shown joint -> {bar, pts} in screen px"""
    return pg.evaluate("""([jid, key]) => { const P = window.__poseApi, s = P.ringState(); const k = s.rings.findIndex(r => r[0] === jid && r[1] === key);
      const g = [...document.querySelectorAll('#pz-rings .pz-grab')].filter(e => +e.dataset.k === k)[0]; if (!g) return null;
      if (g.dataset.bar) return {bar: true, k, pts: [[+g.getAttribute('x1'), +g.getAttribute('y1')], [+g.getAttribute('x2'), +g.getAttribute('y2')]]};
      return {bar: false, k, pts: g.getAttribute('points').trim().split(/\\s+/).map(t => t.split(',').map(Number))}; }""", [jid, key])


def _drag_path(h, pg=None):
    """screen points of a drag along the handle, starting where THIS handle is the one on top (two bars cross at the hub)"""
    p = h["pts"]
    def top(pt):
        return pg is None or pg.evaluate("([x, y, k]) => { const e = document.elementFromPoint(x, y); return !!(e && e.classList.contains('pz-grab') && +e.dataset.k === k); }", [pt[0], pt[1], h["k"]])
    if h["bar"]:
        a, b = np.array(p[0]), np.array(p[1])
        for t0, t1 in ((0.72, 0.98), (0.02, 0.28), (0.3, 0.7), (0.5, 0.9)):
            path = [[float(v) for v in a + (b - a) * t] for t in np.linspace(t0, t1, 7)]
            if top(path[0]):
                return path
        return path
    for m in (len(p) // 2, len(p) // 4, 3 * len(p) // 4, 1):
        if top(p[m]):
            break
    return [p[min(len(p) - 1, m + k)] for k in range(0, 8)]


def part_r(pg, check, frame):
    print("R. every axis reachable from every view (E1 + E2), mouse 1400x900", flush=True)
    pg.evaluate("() => { const P = window.__poseApi; P.reset(); P.open(true); P.open(false); P.panelView({solo: false, mini: false}); }")
    pg.wait_for_timeout(500)
    ids = [j + "_" + s for j in JOINTS for s in ("l", "r")]
    rows, miss, big, crowd, bars = [], [], [], [], 0
    for name, az, el in VIEWS:
        pg.evaluate("(c) => window.__q338.cam(c)", {"az": az, "el": el, "dist": 2600.0, "tgt": [0.0, 0.0, 0.0]})
        pg.wait_for_timeout(450)
        for r in pg.evaluate(JS_MEASURE, ids):
            r["view"] = name; rows.append(r)
            if not r["on"]:
                continue
            bars += r["bars"]
            if r["handles"] != r["axes"] or r["missing"]:
                miss.append((name, r["id"], r["missing"]))
            if r["r0"] > CAP + 0.5 or r["r0"] > max(FLOOR, SHARE * r["near"]) + 0.5:
                big.append((name, r["id"], round(r["r0"]), round(r["near"])))
            if r["inside"] and r["r0"] > FLOOR + 0.5:
                crowd.append((name, r["id"], r["inside"]))
    on = [r for r in rows if r["on"]]
    check("%d joint views measured (%d joints x %d views; %d with the hub off the screen)" % (len(on), len(ids), len(VIEWS), len(rows) - len(on)), len(on) >= 0.8 * len(rows))
    check("every axis of every joint has a handle in every view -- a ring, or a bar where the ring is edge-on (%d bars in all); missing: %s" % (bars, miss[:4]), not miss and bars > 0)
    r0 = [r["r0"] for r in on]
    check("the inner ring is never further out than %.0f px nor than %.2f of the way to the nearest other joint (floor %.0f px): %.0f..%.0f px, median %.0f; too far: %s" % (
        CAP, SHARE, FLOOR, min(r0), max(r0), float(np.median(r0)), big[:4]), not big)
    check("no other joint's hub lies inside a joint's inner ring unless the ring is at its %.0f px floor: %s" % (FLOOR, crowd[:4]), not crowd)
    sh = [r for r in on if r["id"].startswith("shoulder")]
    check("the shoulder's rings, whole figure on the screen: inner ring %.0f..%.0f px (was 52 px at every zoom), nearest other hub %.0f..%.0f px" % (
        min(r["r0"] for r in sh), max(r["r0"] for r in sh), min(r["near"] for r in sh), max(r["near"] for r in sh)), max(r["r0"] for r in sh) <= CAP)
    # real drags
    for jid, key, views in (("knee_l", "flex", [("front", 0.0)]), ("elbow_l", "flex", [("front", 0.0), ("back", math.pi), ("oblique", 0.9)]),
                            ("elbow_r", "flex", [("front", 0.0), ("back", math.pi), ("oblique", -0.9)])):
        for vn, az in views:
            pg.evaluate("() => { const P = window.__poseApi; P.ringHold(null); P.reset(); }")
            c = pg.evaluate("(j) => window.__q384.world(j)", jid)
            frame(pg, c, 1300.0, az=az)
            pg.mouse.move(5, 400)
            pg.evaluate("(j) => window.__poseApi.ringHold(j)", jid); pg.wait_for_timeout(250)
            h = _handle(pg, jid, key)
            if not check("%s from the %s: its %s axis has a handle (%s)" % (jid, vn, key, "bar" if h and h["bar"] else "ring" if h else None), h is not None):
                continue
            q0 = pg.evaluate("(j) => window.__poseApi.pose().j[j][0]", jid)
            pts = _drag_path(h, pg)
            under = pg.evaluate("(p) => window.__q384.under(p[0], p[1])", pts[0])
            pg.mouse.move(pts[0][0], pts[0][1]); pg.mouse.down()
            for p in pts[1:]:
                pg.mouse.move(p[0], p[1]); pg.wait_for_timeout(30)
            pg.mouse.up(); pg.wait_for_timeout(350)
            q1 = pg.evaluate("(j) => window.__poseApi.pose().j[j][0]", jid)
            check("%s from the %s: dragging that %s turns the joint (%.0f -> %.0f deg; under the pointer: %s)" % (jid, vn, "bar" if h["bar"] else "ring", q0, q1, under), abs(q1 - q0) > 4)
    pg.evaluate("() => { const P = window.__poseApi; P.ringHold(null); P.reset(); }")
    return dict(rows=rows)


def part_p(pg, check, frame):
    print("P. the panel: this joint only, and the tile (E4)", flush=True)
    pg.evaluate("() => { const P = window.__poseApi; P.ringHold(null); P.reset(); }")
    pg.mouse.move(5, 500); pg.wait_for_timeout(400)
    pg.evaluate("() => { const P = window.__poseApi; P.panelView({solo: false, mini: false, forget: true}); P.open(true); }")
    pg.wait_for_timeout(600)
    info = """() => { const p = document.getElementById('pose-panel'), r = p.getBoundingClientRect();
      const vis = e => !!(e.offsetParent !== null && e.getClientRects().length);
      const rg = [...p.querySelectorAll('#pz-body input[type=range]')].filter(vis);
      return {hidden: p.hidden, w: r.width, h: r.height, ranges: rg.map(e => e.getAttribute('aria-label')), cls: p.className,
              name: document.getElementById('pz-tile-name').textContent, body: vis(document.getElementById('pz-body')), hint: vis(p.querySelector('.pz-solo-hint')),
              view: window.__poseApi.panelView(), rings: window.__poseApi.ringState().on, store: localStorage.getItem('nmsk.pose.panel.v1')}; }"""
    full = pg.evaluate(info)
    check("default view as before: the whole list (%d sliders shown of the first group, panel %dx%d)" % (len(full["ranges"]), full["w"], full["h"]),
          not full["view"]["solo"] and not full["view"]["mini"] and len(full["ranges"]) >= 4)
    pg.click("#pz-solo"); pg.wait_for_timeout(250)
    s0 = pg.evaluate(info)
    check("'This joint only' with no joint chosen: no sliders, a line saying what to do (%d sliders, hint %s)" % (len(s0["ranges"]), s0["hint"]), s0["view"]["solo"] and not s0["ranges"] and s0["hint"])
    pg.evaluate("() => window.__poseApi.ringHold('knee_l')"); pg.wait_for_timeout(250)
    s1 = pg.evaluate(info)
    check("holding the left knee: the panel shows that joint's slider and nothing else (%s), %d px high (the full list: %d)" % (s1["ranges"], s1["h"], full["h"]),
          len(s1["ranges"]) == 1 and "Knee" in s1["ranges"][0] and s1["ranges"][0].strip().endswith("l") and s1["h"] < 0.6 * full["h"])
    pg.evaluate("() => window.__poseApi.ringHold('elbow_r')"); pg.wait_for_timeout(250)
    s2 = pg.evaluate(info)
    check("holding the right elbow: its flexion / extension slider and the forearm rotation, right side only (%s)" % s2["ranges"],
          len(s2["ranges"]) == 2 and any("Flexion" in t and "xtension" in t for t in s2["ranges"]) and all(t.strip().endswith("r") for t in s2["ranges"]))
    v = pg.evaluate("""() => { const g = [...document.querySelectorAll('#pz-body input[type=range]')].filter(e => e.offsetParent !== null && /Flexion/.test(e.getAttribute('aria-label')))[0];
      g.value = 100; g.dispatchEvent(new Event('input', {bubbles: true})); window.__poseApi.update(); return window.__poseApi.pose().j.elbow_r[0]; }""")
    check("and that slider turns the elbow (-> %.0f deg)" % v, round(v) == 100)
    pg.evaluate("() => window.__poseApi.ringHold(null)"); pg.mouse.move(5, 500); pg.wait_for_timeout(300)
    s3 = pg.evaluate(info)
    check("let go, pointer elsewhere: the last joint stays in the panel (%s)" % s3["ranges"], len(s3["ranges"]) == 2)
    pg.click("#pz-min"); pg.wait_for_timeout(250)
    t = pg.evaluate(info)
    check("the tile: %dx%d px, title + '%s', no list; Pose is still on (panel not hidden, rings %s) and the pose is kept (elbow %.0f deg)" % (
        t["w"], t["h"], t["name"], t["rings"], pg.evaluate("() => window.__poseApi.pose().j.elbow_r[0]")),
        t["view"]["mini"] and not t["hidden"] and not t["body"] and t["h"] <= 64 and t["w"] <= 320 and "Elbow" in t["name"] and t["rings"]
        and round(pg.evaluate("() => window.__poseApi.pose().j.elbow_r[0]")) == 100)
    check("both choices are remembered in this browser (%s)" % t["store"], t["store"] and '"solo":true' in t["store"] and '"mini":true' in t["store"])
    pg.click("#pz-title"); pg.wait_for_timeout(250)
    e = pg.evaluate(info)
    check("a press on the tile opens the panel again, still on 'this joint only' (%dx%d, %d sliders)" % (e["w"], e["h"], len(e["ranges"])), not e["view"]["mini"] and e["body"] and len(e["ranges"]) == 2)
    pg.click("#pz-solo"); pg.wait_for_timeout(250)
    f = pg.evaluate(info)
    check("'This joint only' off: the whole list again (%d sliders shown)" % len(f["ranges"]), not f["view"]["solo"] and len(f["ranges"]) >= 4)
    pg.evaluate("() => { const P = window.__poseApi; P.reset(); P.panelView({solo: false, mini: false}); P.open(false); }")


def part_touch(pg, check, frame, touch):
    """390x844, a finger: the elbow's flexion handle from the front and the back; the tile and the q344 Less / More toggle"""
    print("R / P. touch 390x844", flush=True)
    for vn, az in (("front", 0.0), ("back", math.pi)):
        pg.evaluate("() => { const P = window.__poseApi; P.ringHold(null); P.reset(); P.open(true); P.open(false); }")
        c = pg.evaluate("(j) => window.__q384.world(j)", "elbow_l")
        pg.wait_for_timeout(1200)                  # the sheet that Pose opened on a phone has gone and the canvas has its size back
        frame(pg, c, 1500.0, az=az)
        dots = {}
        for _try in range(3):                      # the dots are redrawn as the picture settles: tap where the dot is NOW
            pg.wait_for_timeout(400)
            s = pg.evaluate("() => window.__poseApi.ringState()")
            dots = {x[0]: x[1:] for x in s.get("dots", [])}
            if "elbow_l" not in dots:
                continue
            pg.touchscreen.tap(*dots["elbow_l"]); pg.wait_for_timeout(450)
            if pg.evaluate("() => window.__poseApi.ringState().held") == "elbow_l":
                break
        if not check("touch, %s: the left elbow has a dot to tap, and the tap holds it (%d dots, %d tap(s))" % (vn, len(dots), _try + 1),
                     pg.evaluate("() => window.__poseApi.ringState().held") == "elbow_l"):
            continue
        h = _handle(pg, "elbow_l", "flex")
        st = pg.evaluate("() => { const s = window.__poseApi.ringState(); return [s.joint, s.held, s.rings, s.handles, s.px]; }")
        if not check("touch, %s: the held elbow offers its flexion / extension handle (%s; state %s)" % (vn, "bar" if h and h["bar"] else "ring" if h else None, st if h is None else "ok"), h is not None):
            continue
        q0 = pg.evaluate("() => window.__poseApi.pose().j.elbow_l[0]")
        pts = _drag_path(h, pg)
        touch("touchStart", pts[0][0], pts[0][1])
        for p in pts[1:]:
            touch("touchMove", p[0], p[1]); pg.wait_for_timeout(30)
        touch("touchEnd"); pg.wait_for_timeout(400)
        q1 = pg.evaluate("() => window.__poseApi.pose().j.elbow_l[0]")
        check("touch, %s: a finger on it turns the elbow (%.0f -> %.0f deg)" % (vn, q0, q1), abs(q1 - q0) > 4)
    pg.evaluate("() => { const P = window.__poseApi; P.ringHold(null); P.reset(); P.panelView({solo: false, mini: false}); P.open(true); }")
    pg.wait_for_timeout(1300)
    a = pg.evaluate("""() => { const p = document.getElementById('pose-panel'), r = p.getBoundingClientRect(), tg = p.querySelector('.q344-tg');
      return {h: r.height, tg: tg ? tg.textContent : null, c: p.getAttribute('data-q344')}; }""")
    check("phone: the panel opens compact with its Less / More toggle as before (%s, %d px high)" % (a["tg"], a["h"]), a["tg"] in ("More", "Less"))
    if a["tg"]:
        pg.evaluate("() => document.querySelector('#pose-panel .q344-tg').click()"); pg.wait_for_timeout(300)
        b = pg.evaluate("() => { const p = document.getElementById('pose-panel'); return {h: p.getBoundingClientRect().height, tg: p.querySelector('.q344-tg').textContent}; }")
        check("phone: Less / More still toggles (%s -> %s, %d -> %d px)" % (a["tg"], b["tg"], a["h"], b["h"]), b["tg"] != a["tg"])
    pg.evaluate("() => document.getElementById('pz-min').click()"); pg.wait_for_timeout(300)
    t = pg.evaluate("() => { const p = document.getElementById('pose-panel'), r = p.getBoundingClientRect(); return {w: r.width, h: r.height, hidden: p.hidden, r: r.right, b: r.bottom}; }")
    check("phone: the tile is %dx%d px (the sheet was %d px high) and on the screen" % (t["w"], t["h"], a["h"]), not t["hidden"] and t["h"] <= 64 and t["w"] <= 320 and t["r"] <= 392 and t["b"] <= 846)
    pg.evaluate("() => { const P = window.__poseApi; P.panelView({solo: false, mini: false}); P.open(false); P.reset(); }")
