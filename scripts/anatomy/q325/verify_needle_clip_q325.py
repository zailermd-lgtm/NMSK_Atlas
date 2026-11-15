#!/usr/bin/env python3
"""Q325: the injection clip -- a planned needle played in the probe image, at rest and in a posed body.

Checked in headless Chromium (software rendering) against a built page that carries the current private add-ons:

  * a needle planned into a muscle (entry on the skin, tip inside the muscle) is shown in the scan: the probe is seated so
    that the scan plane holds the whole path (both ends within 0.05 mm of the plane), and the needle is painted;
  * Play advances the tip entry -> target: the tip gets closer to the target on every frame, the painted needle never
    shrinks, the clip ends exactly at the target with the needle painted; enough frames for a clip (>= 5);
  * the joint is flexed 60 deg: the planned entry and target ride their structures (moved, tip still inside the muscle,
    entry still on the skin), the scan plane follows (holds the posed path again, the raster key carries the pose), and
    the clip plays to the posed target; back at rest the plan is exactly where it was placed;
  * a plan made IN the posed body (tip inside the posed muscle) plays to its target too; the out-of-plane view holds the
    target and not the entry;
  * no page errors.

    python3 scripts/anatomy/q325/verify_needle_clip_q325.py <build dir> [--size 1400x900] [--shots DIR]
"""
from __future__ import annotations

import argparse
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ARGS = ["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]
# muscle, joint, outward direction of the needle (model frame: +x left? +y up, +z anterior), on both Base pages
CASES = [("tibialis_anterior_r", "knee_r", [0.2, -1.2, 1.0]), ("flexor_carpi_radialis_r", "elbow_r", [0.0, -1.2, 1.0])]


def serve(d):
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close()
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(p), "--bind", "127.0.0.1", "-d", str(d)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1); return srv, p


PROBE = r"""async (cases) => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const T = window.NMSKClinicalTool, U = window.NMSKUltrasound, LIB = window.NMSKUltrasoundLib, PZ = window.__poseApi, PURE = window.NMSKClinical.pure;
  if (!T || !U || !PZ) return {err: 'needle tool / scan tool / pose rig missing'};
  await U.ready();
  const out = {steps: {}};
  const pick = cases.find(c => T.byId[c[0]] && PZ.rig().joints.some(j => j.id === c[1]));
  if (!pick) return {err: 'no test muscle on this page'};
  const [mid, jid, dOut0] = pick, mi = T.byId[mid][0], dOut = LIB.unit(dOut0);
  out.muscle = mid; out.joint = jid;
  const add = (a, b, s) => [a[0] + b[0]*s, a[1] + b[1]*s, a[2] + b[2]*s], dist = (a, b) => Math.hypot(a[0]-b[0], a[1]-b[1], a[2]-b[2]);

  // the target picker of the injection mode, as a user would
  const inp = document.querySelector('.mc-pick .mc-search');
  if (inp) { inp.value = mid; inp.dispatchEvent(new Event('input')); await sleep(200); const b = document.querySelector('.mc-pick .mc-res button'); if (b) b.click(); await sleep(800); }
  out.pickedTarget = T.plan.i === mi;

  // a target INSIDE the muscle (the middle of the first in/out pair along the needle line) and the entry where that line leaves the skin
  function planNow() {
    const g = T.geom(mi), n = g.pos.length / 3; let c = [0, 0, 0];
    for (let k = 0; k < n; k++) for (let a = 0; a < 3; a++) c[a] += g.pos[3*k + a] / n;
    const o = add(c, dOut, 300), hs = T.rayAll(mi, o, [-dOut[0], -dOut[1], -dOut[2]], 0, 1e9).map(q => q.t).sort((a, b) => a - b);
    if (hs.length < 2) return null;
    const Tg = add(o, dOut, -(hs[0] + hs[1]) / 2), geo = U.geo();
    const h = LIB.skinHit(geo, add(Tg, dOut, 300), [-dOut[0], -dOut[1], -dOut[2]], null);
    if (!h) return null;
    NeedlePath.setPoints(h.point, Tg, geo.recs[h.struct].id, mid);
    return {E: h.point, T: Tg, skin: h.struct};
  }
  async function idle() { await sleep(250); await U.idle(); }
  function onSkin(p, s) { const g = T.geom(s); return g ? PURE.poseAnchor(g.pos, g.idx, p, null).d : 1e9; }
  function snap() { const s = U.needleClip.state(); return {P: U.state().P, pathA: s.path && s.path.A, O: (U.frames()[0] || {}).O, nfr: U.frames().length, on: s.on, t: s.t, plane: s.plane, px: s.px, pxIn: s.pxIn, tip: s.tip, target: s.target, len: s.len, offered: s.offered, rk: (U.frames()[0] || {}).rk || ''}; }
  async function play() {
    const pb = Array.from(document.querySelectorAll('#us-root .us-clip button')).find(b => b.title.startsWith('Replay'));
    pb.click(); await sleep(100);
    const t0 = performance.now(); while (U.needleClip.state().playing && performance.now() - t0 > -1 && performance.now() - t0 < 90000) await sleep(100);
    await idle();
    const s = U.needleClip.state(), H = s.hist, tgt = s.target;
    const d = H.map(x => dist(x.tip, tgt)), gaps = H.slice(1).map((x, k) => x.at - H[k].at);
    return {n: H.length, ms: performance.now() - t0, lastT: H.length ? H[H.length - 1].t : null, endTip: s.tip ? dist(s.tip, tgt) : null, endPx: H.length ? H[H.length - 1].pxIn : 0,
            closer: d.slice(1).every((x, k) => x < d[k] - 1e-9), grows: H.slice(1).every((x, k) => x.pxIn >= H[k].pxIn), firstPx: H.length ? H[0].pxIn : 0,
            medGap: gaps.length ? gaps.slice().sort((a, b) => a - b)[gaps.length >> 1] : null, planeMax: Math.max(...H.map(x => x.plane ? Math.max(Math.abs(x.plane.A), Math.abs(x.plane.B)) : 1e9))};
  }

  // ---- 1. at rest
  const p0 = planNow(); if (!p0) return {err: 'could not plan a path into ' + mid};
  await sleep(300);
  const rep0 = NeedlePath.report();
  out.steps.rest = {L: rep0.length_mm, tipInside: T.insideMesh(mi, T.target.p), targetId: rep0.target_id, offeredBtn: !!Array.from(document.querySelectorAll('button')).find(b => b.textContent === 'הצג בסריקה' && b.offsetParent !== null)};
  const E0 = T.entry.p.slice(), T0 = T.target.p.slice();
  const sb = Array.from(document.querySelectorAll('button')).find(b => b.textContent === 'הצג בסריקה');
  if (sb) sb.click(); else await U.needleClip.show({});
  await sleep(500); await idle();
  out.steps.rest.show = snap();
  out.steps.rest.play = await play();

  // ---- 2. flex the joint 60 deg: the plan rides, the plane follows
  PZ.set(jid, 'flex', 60); await sleep(700); await idle();
  const rk1 = (U.frames()[0] || {}).rk || '';
  out.steps.posed = {entryMoved: dist(T.entry.p, E0), targetMoved: dist(T.target.p, T0), tipInside: T.insideMesh(mi, T.target.p),
                     entryOnSkin: onSkin(T.entry.p, p0.skin), show: snap(), rkPose: /pose\d+/.test(rk1)};
  out.steps.posed.play = await play();

  // ---- 3. back at rest: exactly where it was placed
  PZ.reset(); await sleep(700); await idle();
  out.steps.back = {entry: dist(T.entry.p, E0), target: dist(T.target.p, T0), exact: T.entry.p.every((v, k) => v === E0[k]) && T.target.p.every((v, k) => v === T0[k]), show: snap()};

  // ---- 4. a plan made IN the posed body
  PZ.set(jid, 'flex', 60); await sleep(700); await idle();
  const p2 = planNow(); if (!p2) return Object.assign(out, {err: 'could not plan in the posed body'});
  await sleep(300); await U.needleClip.show({}); await idle();
  out.steps.posedPlan = {tipInside: T.insideMesh(mi, T.target.p), entryOnSkin: onSkin(T.entry.p, p2.skin), fromRest: dist(T.target.p, T0), show: snap()};
  out.steps.posedPlan.play = await play();

  // ---- 5. out of plane: the plane crosses the needle at the target
  const ob = Array.from(document.querySelectorAll('#us-root .us-clip button')).find(b => b.textContent === 'out of plane');
  ob.click(); await sleep(400); await idle();
  out.steps.oop = snap(); out.steps.oop.play = await play();
  U.needleClip.show({oop: false}); await idle();
  return out;
}"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("build_dir")
    ap.add_argument("--size", default="1400x900")
    ap.add_argument("--shots", default=None)
    a = ap.parse_args()
    d = Path(a.build_dir).resolve()
    W, H = (int(x) for x in a.size.split("x"))
    srv, port = serve(d)
    errs: list[str] = []
    page_errors: list[str] = []

    def check(label, cond):
        ok = bool(cond)
        print(("  OK   " if ok else "  FAIL ") + label)
        if not ok:
            errs.append(label)

    try:
        with sync_playwright() as pl:
            b = pl.chromium.launch(args=ARGS, executable_path="/opt/pw-browsers/chromium")
            pg = b.new_page(viewport={"width": W, "height": H})
            pg.on("pageerror", lambda e: page_errors.append(str(e)))
            pg.route("**/*", lambda rq: rq.abort() if "fonts.g" in rq.request.url else rq.continue_())
            html = sorted(d.glob("atlas_viewer*.html"))
            print(f"=== {d.name} @ {W}x{H} ===")
            pg.goto(f"http://127.0.0.1:{port}/{html[0].name if html else 'index.html'}", wait_until="load", timeout=180000)
            pg.wait_for_function("window.NMSKUltrasound && window.NMSKClinicalTool && window.__poseApi && window.__poseApi.ready()", timeout=180000)
            pg.wait_for_timeout(1500)
            t = pg.query_selector('.mw-tile[data-mode="inj"]')
            if t:
                pg.evaluate("el => el.click()", t)
            pg.wait_for_timeout(2000)
            r = pg.evaluate(PROBE, [list(c) for c in CASES])
            if a.shots:
                Path(a.shots).mkdir(parents=True, exist_ok=True)
                pg.screenshot(path=str(Path(a.shots) / f"q325_{d.name}_{W}x{H}.png"))
            b.close()
    finally:
        srv.terminate()

    if r.get("err"):
        print("  FAIL " + r["err"])
        print("Q325_NEEDLECLIP_FAIL")
        return 1
    s = r["steps"]
    print(f"     {r['muscle']} / {r['joint']}: path {s['rest']['L']:.1f} mm")
    for k in ("rest", "posed", "posedPlan", "oop"):
        p = s[k]["play"]
        print(f"     {k}: {p['n']} frames in {p['ms']:.0f} ms (median gap {p['medGap']} ms), end px {p['endPx']}, end tip {p['endTip']}")

    def plane_ok(sh, tol=0.05):
        return sh["plane"] and abs(sh["plane"]["A"]) < tol and abs(sh["plane"]["B"]) < tol

    def play_ok(name, p):
        check(f"{name}: the clip has frames ({p['n']} >= 5)", p["n"] >= 5)
        check(f"{name}: the tip gets closer to the target on every frame", p["closer"])
        check(f"{name}: the needle in the image never shrinks and grows ({p['firstPx']} -> {p['endPx']} px inside the image)", p["grows"] and p["endPx"] > p["firstPx"])
        check(f"{name}: the clip ends at the target (t = {p['lastT']}, tip {p['endTip']} mm off)", p["lastT"] == 1 and p["endTip"] is not None and p["endTip"] < 1e-6)

    rs = s["rest"]
    check("the injection mode picked the target muscle", r["pickedTarget"])
    check(f"rest: the planned tip lies inside {r['muscle']}", rs["tipInside"] and rs["targetId"] == r["muscle"])
    check("rest: 'Show in scan' is offered for the planned path", rs["offeredBtn"])
    check(f"rest: the scan plane holds the path (ends {rs['show']['plane']} mm off the plane)", rs["show"]["on"] and plane_ok(rs["show"]))
    check(f"rest: the needle is in the image ({rs['show']['pxIn']} of {rs['show']['px']} px inside the image)", rs["show"]["pxIn"] > 20)
    check("rest: the clip bar is shown", rs["show"]["offered"])
    play_ok("rest", rs["play"])
    ps = s["posed"]
    check(f"posed 60 deg: the entry and the target ride their structures (moved {ps['entryMoved']:.1f} / {ps['targetMoved']:.1f} mm)", ps["entryMoved"] > 3 and ps["targetMoved"] > 3)
    check("posed: the tip is still inside the muscle", ps["tipInside"])
    check(f"posed: the entry is still on the skin ({ps['entryOnSkin']:.3f} mm)", ps["entryOnSkin"] < 0.5)
    check(f"posed: the scan plane holds the posed path ({ps['show']['plane']})", plane_ok(ps["show"]))
    check("posed: the frame's raster key carries the pose (no stale frame)", ps["rkPose"])
    check(f"posed: the needle is in the image ({ps['show']['pxIn']} px)", ps["show"]["pxIn"] > 20)
    play_ok("posed", ps["play"])
    bk = s["back"]
    check(f"back at rest: the plan is exactly where it was placed ({bk['entry']}, {bk['target']})", bk["exact"])
    check("back at rest: the scan plane holds it again", plane_ok(bk["show"]) and "pose" not in bk["show"]["rk"].split("|")[-1])
    pp = s["posedPlan"]
    check("planned in the posed body: the tip is inside the posed muscle", pp["tipInside"])
    check(f"planned in the posed body: the entry is on the posed skin ({pp['entryOnSkin']:.3f} mm)", pp["entryOnSkin"] < 0.5)
    check(f"planned in the posed body: the plane holds the path ({pp['show']['plane']})", plane_ok(pp["show"]) and pp["show"]["pxIn"] > 20)
    play_ok("posed plan", pp["play"])
    oo = s["oop"]
    check(f"out of plane: the plane holds the target, not the entry ({oo['plane']})",
          oo["plane"] and abs(oo["plane"]["B"]) < 0.05 and abs(oo["plane"]["A"]) > 1.0)
    check(f"out of plane: the tip shows at the target ({oo['play']['endPx']} px)", oo["play"]["lastT"] == 1 and oo["play"]["endPx"] > 0)
    check(f"no page errors ({len(page_errors)})", not page_errors)
    for e in page_errors[:5]:
        print("     page error: " + e[:300])
    print()
    if errs:
        print(f"Q325_NEEDLECLIP_FAIL {len(errs)}")
        return 1
    print("Q325_NEEDLECLIP_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
