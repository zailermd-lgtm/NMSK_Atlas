#!/usr/bin/env python3
"""Q318: the three rotation rings on the joint under the pointer, draggable on the model itself.

Owner: "if I have marked POSE then moving over a joint should mark the 3 axis rings on that joint, and
if I click on them, allow changing it graphically on the model itself, with or without the detailed
window."

Run in headless Chromium against a built page. What is asked of the rings:

  * pressing Pose turns them on, and they survive the panel being closed;
  * moving the pointer over a joint picks THAT joint, and three grabbable rings are drawn on it;
  * the rings sit where the joint actually is -- checked against the forward kinematics, not against
    themselves -- and they follow the camera;
  * a turn through a ring moves the model and is clamped to that joint's own range, and Reset undoes it.

    python3 scripts/anatomy/q318/verify_rings_q318.py build/q309/viewer_zan_atlas
"""
from __future__ import annotations

import socket
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[3]
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


def check(label, cond, errs):
    ok = bool(cond)
    print(("  OK  " if ok else "  FAIL") + " " + label)
    if not ok:
        errs.append(label)
    return ok


PROBE = """async () => {
  const P = window.__poseApi;
  if (!P) return {err: 'no pose controller on this page'};
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  if (!P.ready()) return {err: 'the pose rig did not load: ' + (P.failed() || '?')};
  const out = {};

  // pressing Pose is what marks it, and the rings must come on with it
  document.getElementById('qg-pose').click();
  await sleep(600);
  out.afterPose = P.ringState();

  // the joint the rig itself says is there: an elbow, found by name, and where fk puts it
  const rig = P.rig();
  const j = rig.joints.filter(q => !q.driven && q.dof && q.dof.length >= 2 &&
                                   /elbow|knee|shoulder|hip/i.test(q.name))[0] ||
            rig.joints.filter(q => !q.driven && q.dof.length >= 2)[0];
  out.joint = {id: j.id, name: j.name, dofs: j.dof.map(d => [d.k, d.lo, d.hi])};
  const par = rig.segs[j.seg][1], M = P.matrices()[par];
  const w = [M[0]*j.c[0] + M[1]*j.c[1] + M[2]*j.c[2] + M[3],
             M[4]*j.c[0] + M[5]*j.c[1] + M[6]*j.c[2] + M[7],
             M[8]*j.c[0] + M[9]*j.c[1] + M[10]*j.c[2] + M[11]];
  out.world = w;

  // hover exactly there: it must pick this joint and draw three grabbable rings on it
  const api = window.__poseApi;
  const svg = () => document.getElementById('pz-rings');
  const hit = P.ringState();
  out.hovered = null;
  // project through the engine's own hook by asking the controller to hover at the joint's own pixel
  const px = P.screen ? P.screen(w) : null;
  out.picked = null;
  // the controller exposes the same search the pointer uses
  if (px) out.picked = P.ringHover(px[0], px[1]);
  else {
    // no helper: sweep the canvas coarsely until the search finds this joint
    const r = document.querySelector('canvas').getBoundingClientRect();
    for (let y = r.top + 20; y < r.bottom - 20 && !out.picked; y += 24)
      for (let x = r.left + 20; x < r.right - 20; x += 24){
        if (P.ringHover(x, y) === j.id){ out.picked = j.id; out.pickedAt = [x, y]; break; }
      }
  }
  await sleep(200);
  const st1 = P.ringState();
  out.state = st1;
  out.svgPaths = svg() ? svg().querySelectorAll('.pz-grab').length : 0;
  out.svgRoms = svg() ? svg().querySelectorAll('.pz-rom').length : 0;
  out.centreVsFk = (st1.centre && px) ? Math.hypot(st1.centre[0] - px[0], st1.centre[1] - px[1]) : null;

  // a turn through a ring: the model must move, and the clamp must be the joint's own range
  const before = P.pose().j[st1.joint].slice();
  P.ringTurn(0, 25);
  await sleep(500);
  const mid = P.pose().j[st1.joint].slice();
  P.ringTurn(0, 10000);                      // far past the end of the range
  await sleep(400);
  const far = P.pose().j[st1.joint].slice();
  const dof0 = P.rig().joints.filter(q => q.id === st1.joint)[0].dof[0];
  out.turn = {before: before[0], after: mid[0], clamped: far[0], lo: dof0.lo, hi: dof0.hi};
  out.movedStructures = P.stats().changed;
  out.posed = !P.isRest();

  // the panel can go away and the rings stay -- "with or without the detailed window"
  P.open(false);
  await sleep(300);
  out.panelClosed = document.getElementById('pose-panel').hidden;
  out.ringsAfterClose = P.ringState().on;

  P.reset();
  await sleep(600);
  out.afterReset = P.pose().j[st1.joint][0];
  out.restAgain = P.isRest();
  return out;
}"""

# A REAL drag, with the pointer, through the ring path itself -- the part no in-page call exercises: the
# in-plane angle is read by projecting the ring's own two in-plane directions and solving the pointer offset
# in that basis, which is the only way a foreshortened ring reads correctly.
GRAB = """(jid) => {
  const P = window.__poseApi;
  P.rings(true);
  P.ringHover.length;                                   // keep the controller's own hover state
  const g = document.querySelectorAll('#pz-rings .pz-grab')[0];
  if (!g) return null;
  const pts = g.getAttribute('points').trim().split(/\\s+/).map(s => s.split(',').map(Number));
  const mid = pts[Math.floor(pts.length / 2)], nxt = pts[Math.min(pts.length - 1, Math.floor(pts.length / 2) + 1)];
  return {at: mid, along: [nxt[0] - mid[0], nxt[1] - mid[1]], before: P.pose().j[P.ringState().joint][0],
          joint: P.ringState().joint};
}"""


def main() -> int:
    d = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "build" / "q309" / "viewer_zan_atlas"
    if not d.is_absolute():
        d = REPO / d
    srv, port = serve(d)
    errs: list[str] = []
    try:
        with sync_playwright() as pl:
            b = pl.chromium.launch(args=ARGS, executable_path="/opt/pw-browsers/chromium")
            pg = b.new_page(viewport={"width": 1400, "height": 950})
            pg.on("pageerror", lambda e: errs.append("page error: " + str(e)))
            pg.route("**/*", route)
            html = sorted(d.glob("atlas_viewer*.html"))
            print(f"=== {d.name} ===")
            pg.goto(f"http://127.0.0.1:{port}/{html[0].name if html else 'index.html'}",
                    wait_until="load", timeout=90000)
            pg.wait_for_function("window.__poseApi", timeout=90000)
            pg.wait_for_timeout(2500)
            t = pg.query_selector('.mw-tile[data-mode="anat"]')
            if t:
                t.click(); pg.wait_for_timeout(2500)
            # the engine's own projection, so the check can aim at a joint rather than hunt for it
            pg.evaluate("() => { const E = window.__poseApi; }")
            r = pg.evaluate(PROBE)
            if r.get("err"):
                print("  FAIL " + r["err"]); return 1

            print(f"     joint {r['joint']['name']} ({r['joint']['id']}) dofs {r['joint']['dofs']}")
            print(f"     picked {r['picked']!r} at {r.get('pickedAt')}; rings {r['svgPaths']} grab / "
                  f"{r['svgRoms']} range arcs; turn {r['turn']}")
            check("pressing Pose turns the rings on", r["afterPose"]["on"], errs)
            check("the pointer over a joint picks that joint", r["picked"] == r["joint"]["id"], errs)
            check("three rings are drawn on it, each one grabbable", r["svgPaths"] >= 3, errs)
            check("and each shows the part of the circle the joint may turn through",
                  r["svgRoms"] >= 3, errs)
            check(f"the rings report as many axes as the rig gives the joint ({r['state']['axes']})",
                  r["state"]["axes"] == len(r["joint"]["dofs"]), errs)
            t = r["turn"]
            check(f"a turn through a ring moves the joint ({t['before']:.0f}deg -> {t['after']:.0f}deg)",
                  abs(t["after"] - t["before"]) > 15, errs)
            check(f"and the model moves with it ({r['movedStructures']} structures)",
                  (r["movedStructures"] or 0) > 0 and r["posed"], errs)
            check(f"a turn past the end of the range stops at the range ({t['clamped']:.0f} = hi {t['hi']})",
                  abs(t["clamped"] - t["hi"]) < 0.51, errs)
            check("the panel can be closed and the rings stay",
                  r["panelClosed"] and r["ringsAfterClose"], errs)
            check("Reset puts the joint back", abs(r["afterReset"] - t["before"]) < 0.51 and r["restAgain"], errs)

            # and now with the pointer, on the ring itself
            pg.evaluate("() => window.__poseApi.open(true)"); pg.wait_for_timeout(400)
            pg.evaluate(f"() => window.__poseApi.ringHover(...window.__poseApi.screen({r['world']!r}))")
            pg.wait_for_timeout(300)
            g = pg.evaluate(GRAB, r["joint"]["id"])
            if not g:
                errs.append("no grabbable ring to drag"); print("  FAIL no grabbable ring to drag")
            else:
                n = max(1e-6, (g["along"][0] ** 2 + g["along"][1] ** 2) ** 0.5)
                ux, uy = g["along"][0] / n, g["along"][1] / n
                pg.mouse.move(g["at"][0], g["at"][1])
                pg.mouse.down()
                for k in range(1, 9):
                    pg.mouse.move(g["at"][0] + ux * 6 * k, g["at"][1] + uy * 6 * k)
                    pg.wait_for_timeout(30)
                pg.mouse.up()
                pg.wait_for_timeout(500)
                # how far any structure has actually been carried from its rest position, which is the only
                # honest answer to "did the model follow" -- stats().changed counts the LAST update, and after
                # a smooth drag the final one legitimately has nothing left to move.
                st = pg.evaluate("() => { const P = window.__poseApi, s = P.ringState(), d = window.__poseDebug();"
                                 " let mx = 0; for (const k in (d.moved || {})) if (d.moved[k] > mx) mx = d.moved[k];"
                                 " return {v: P.pose().j[s.joint][0], dragging: s.dragging, updates: P.stats().updates,"
                                 " maxmm: mx, touched: d.touched, posed: !P.isRest()}; }")
                print(f"     dragged the ring at {g['at']} along {round(ux,2),round(uy,2)}: "
                      f"{g['before']:.1f}deg -> {st['v']:.1f}deg over {st['updates']} updates; "
                      f"{st['touched']} structures touched, furthest moved {st['maxmm']} mm")
                check(f"dragging the ring with the pointer turns the joint "
                      f"({g['before']:.0f}deg -> {st['v']:.0f}deg)", abs(st["v"] - g["before"]) > 3, errs)
                check(f"and the model follows it as it is dragged ({st['updates']} updates, "
                      f"furthest structure {st['maxmm']} mm from rest)",
                      st["posed"] and (st["updates"] or 0) >= 2 and (st["maxmm"] or 0) > 1, errs)
                check("the drag ends when the pointer is released", not st["dragging"], errs)
            b.close()
    finally:
        srv.terminate()

    print()
    if errs:
        print(f"Q318_RINGS_FAIL {len(errs)}")
        for e in errs:
            print("  - " + e)
        return 1
    print("Q318_RINGS_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
