#!/usr/bin/env python3
"""Q328: the needle tool's overlays follow the pose -- saved injection points, motor points and risk halos.

Checked in headless Chromium (software rendering) against a built page that carries the current private add-ons:

  * a knee / elbow is flexed 60 deg: every motor point of a moved structure rides it (the moved limb's points move; a point
    in or on its own structure keeps its distance to that structure's surface within 0.5 mm and stays inside it -- a given
    point lying away from its structure is listed, it rides the local surface), every other motor point keeps its exact coordinates;
    the shown markers ("Emphasize motor points" for the marked muscles, the planned muscle's own motor points) are redrawn
    at the posed points;
  * a saved injection point in the moved limb rides it (entry and target, the same surface distances), its marker is redrawn
    there; a saved point on the other side does not move;
  * the risk halos: every halo is drawn through the page's own structure buffers (the posed vertices), and the halo
    structures of the moved limb carry their posed boxes;
  * back at rest every point is byte-identical to where it was; the per-event cost stays small; no page errors.

    python3 scripts/anatomy/q328/verify_overlays_pose_q328.py <build dir> [--size 1400x900]
"""
from __future__ import annotations

import argparse
import socket
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

ARGS = ["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]
CASES = [("tibialis_anterior_r", "knee_r", [0.2, -1.2, 1.0]), ("flexor_carpi_radialis_r", "elbow_r", [0.0, -1.2, 1.0])]


def serve(d):
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close()
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(p), "--bind", "127.0.0.1", "-d", str(d)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1); return srv, p


PROBE = r"""async (cases) => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const T = window.NMSKClinicalTool, PZ = window.__poseApi, PURE = window.NMSKClinical && window.NMSKClinical.pure;
  const U = window.NMSKUltrasound, LIB = window.NMSKUltrasoundLib;
  if (!T || !PZ || !PURE || !U || !LIB) return {err: 'needle tool / scan tool / pose rig missing'};
  await U.ready();
  for (let k = 0; k < 150 && T.mp.msg === 'loading...'; k++) await sleep(100);
  if (T.mp.msg === 'loading...') return {err: 'the add-on data did not load'};
  const hasMp = T.mp.points.length > 0;   // a body without motor-point data: those checks are reported as not applicable
  const pick = cases.find(c => T.byId[c[0]] && T.byId[c[0].replace(/_r$/, '_l')] && PZ.rig().joints.some(j => j.id === c[1]));
  if (!pick) return {err: 'no test muscle on this page'};
  const [mid, jid, d0] = pick, l = Math.hypot(...d0), dOut = d0.map(x => x / l);
  const add = (a, b, s) => [a[0] + b[0]*s, a[1] + b[1]*s, a[2] + b[2]*s], dist = (a, b) => Math.hypot(a[0]-b[0], a[1]-b[1], a[2]-b[2]);
  const same = (a, b) => a.length === b.length && a.every((v, k) => v === b[k]);
  const surf = (s, p) => { const g = T.geom(s); return g ? PURE.poseAnchor(g.pos, g.idx, p, null).d : 1e9; };
  const out = {muscle: mid, joint: jid};

  // overlay capture: the last geometry set under each name
  const cap = {}, o0 = T.ov.set.bind(T.ov), r0 = T.ov.remove.bind(T.ov);
  T.ov.set = function (name, geos, spec) { const r = o0(name, geos, spec); cap[name] = [].concat(geos).filter(Boolean).map(g => Float64Array.from(g.pos)); return r; };
  T.ov.remove = function (name) { delete cap[name]; return r0(name); };
  const nearV = (name, p) => { let b = 1e9; (cap[name] || []).forEach(P => { for (let k = 0; k < P.length; k += 3) { const d = Math.hypot(P[k]-p[0], P[k+1]-p[1], P[k+2]-p[2]); if (d < b) b = d; } }); return b; };
  const centroid = name => { const P = (cap[name] || [])[0]; if (!P) return null; const c = [0, 0, 0], n = P.length / 3; for (let k = 0; k < P.length; k++) c[k % 3] += P[k] / n; return c; };
  // pose events: which structures moved, and what the overlay step costs
  const movedIds = new Set(); window.addEventListener('nmsk-pose-rev', e => ((e.detail && e.detail.ids) || []).forEach(i => movedIds.add(i)));
  const cost = [], po = T.poseOverlays.bind(T); T.poseOverlays = function (ids) { const t0 = performance.now(), r = po(ids); cost.push(performance.now() - t0); return r; };
  const drawn = new Set(), ds = T.api.webgl && T.api.webgl.drawStructure;
  if (ds) T.api.webgl.drawStructure = function (i) { drawn.add(i); return ds(i); };

  // a plan into a muscle: target inside it, entry where the line leaves the skin
  function planInto(m) {
    const mi = T.byId[m][0], g = T.geom(mi), n = g.pos.length / 3; let c = [0, 0, 0];
    for (let k = 0; k < n; k++) for (let a = 0; a < 3; a++) c[a] += g.pos[3*k + a] / n;
    const dm = m.endsWith('_l') ? [-dOut[0], dOut[1], dOut[2]] : dOut, back = [-dm[0], -dm[1], -dm[2]];
    const o = add(c, dm, 300), hs = T.rayAll(mi, o, back, 0, 1e9).map(q => q.t).sort((a, b) => a - b);
    if (hs.length < 2) return null;
    const Tg = add(o, dm, -(hs[0] + hs[1]) / 2), geo = U.geo();
    const h = LIB.skinHit(geo, add(Tg, dm, 300), back, null);   // the entry where the line leaves the skin (the scan tool's own skin test, as Q325)
    if (!h) return null;
    NeedlePath.setPoints(h.point, Tg, geo.recs[h.struct].id, m);
    return {mi, skin: h.struct};
  }
  const pa = planInto(mid); if (!pa) return {err: 'could not plan into ' + mid};
  const s1 = T.addSavedPoint();
  const pb = planInto(mid.replace(/_r$/, '_l')); if (!pb) return {err: 'could not plan into the other side'};
  const s2 = T.addSavedPoint();
  NeedlePath.plan(mid); await sleep(300);           // the planned muscle's own motor points (plan-mp)
  out.hasMp = hasMp; out.mpMsg = T.mp.msg;
  const sel = T.api.selection();
  const mpIds = Array.from(new Set(T.mp.points.map(p => p.structure_id).filter(id => T.byId[id])));
  sel.markIds(mpIds, true); await sleep(300);
  T.emphasize(true); T.halos(true); await sleep(600);

  const rest = T.mp.points.map(p => p.pos.slice()), restD = T.mp.points.map(p => { const s = T.mpStructure(p); return s == null ? null : surf(s, p.pos); });
  const sv = it => ({E: it.entry.p.slice(), T: it.target.p.slice(), dE: surf(it.entry._anc.s, it.entry.p), dT: surf(it.target._anc.s, it.target.p)});
  const S1 = sv(s1), S2 = sv(s2);
  out.n = {mp: T.mp.points.length, shown: T.visibleMpPoints().length, plan: T.plan.zone ? T.plan.zone.mps.length : 0, halos: 0};

  // ---- flex 60 deg (in two steps: the second one measures the cost once the points are anchored)
  movedIds.clear(); cost.length = 0;
  PZ.set(jid, 'flex', 30); await sleep(300);
  const c1 = cost.slice(); cost.length = 0;
  PZ.set(jid, 'flex', 60); await sleep(900);
  const c2 = cost.slice();
  out.cost = {first: Math.max(0, ...c1), next: Math.max(0, ...c2)};
  const shownSet = new Set(T.visibleMpPoints()), planSet = new Set(T.plan.zone ? T.plan.zone.mps : []);
  const mv = {n: 0, moved: 0, maxMove: 0, maxDd: 0, worst: null, on: 0, onMoved: 0, left: 0, off: [], still: 0, stillSame: 0, shownMoved: 0, shownOff: 0, planMoved: 0, planOff: 0};
  T.mp.points.forEach((p, k) => {
    const s = T.mpStructure(p);
    if (s != null && movedIds.has(s)) {
      mv.n++; const m = dist(p.pos, rest[k]); if (m > 3) mv.moved++; mv.maxMove = Math.max(mv.maxMove, m);
      const dd = Math.abs(surf(s, p.pos) - restD[k]), inR = T.insideMesh(s, rest[k]);
      if (inR && !T.insideMesh(s, p.pos)) mv.left++;
      if (restD[k] < 5) { mv.on++; if (m > 3) mv.onMoved++; if (dd > mv.maxDd) { mv.maxDd = dd; mv.worst = p.id; } }
      else if (dd >= 0.5) mv.off.push([p.id, +restD[k].toFixed(1), +surf(s, p.pos).toFixed(1)]);   // a given point lying 5+ mm away from its own structure
      if (shownSet.has(p)) { mv.shownMoved++; if (Math.abs(nearV('mp-core', p.pos) - 1.8) > 0.05) mv.shownOff++; }
      if (planSet.has(p)) { mv.planMoved++; if (Math.abs(nearV('plan-mp', p.pos) - 2.0) > 0.05) mv.planOff++; }
    } else { mv.still++; if (same(p.pos, rest[k])) mv.stillSame++; }
  });
  out.mp = mv;
  const c1s = centroid('n-tgt-s' + s1.id);
  out.saved = {s1E: dist(s1.entry.p, S1.E), s1T: dist(s1.target.p, S1.T), s1dE: Math.abs(surf(s1.entry._anc.s, s1.entry.p) - S1.dE), s1dT: Math.abs(surf(s1.target._anc.s, s1.target.p) - S1.dT),
               s1Marker: c1s ? dist(c1s, s1.target.p) : 1e9, s1Moved: movedIds.has(s1.target._anc.s),
               s2Same: same(s2.entry.p, S2.E) && same(s2.target.p, S2.T), s2Moved: movedIds.has(s2.target._anc.s) || movedIds.has(s2.entry._anc.s)};
  // halos: drawn from the page's structure buffers, the moved ones carry their posed boxes
  drawn.clear(); T.api.redraw(); await sleep(400);
  const hl = Array.from(document.querySelectorAll('#ncl-halo-list li')).length;
  const haloIdx = T.recs.map((r, i) => i).filter(i => T.cls[i] && T.api.visible(i) && drawn.has(i));
  const movedHalo = haloIdx.filter(i => movedIds.has(i));
  let boxOk = 0, posedMove = 0;
  movedHalo.forEach(i => {
    const L = window.__poseLive(i), R = window.__poseRestPos(i); if (!L || !R) return;
    const lo = [1e30, 1e30, 1e30], hi = [-1e30, -1e30, -1e30]; let mx = 0;
    for (let k = 0; k < L.length; k += 3) { for (let c = 0; c < 3; c++) { lo[c] = Math.min(lo[c], L[k+c]); hi[c] = Math.max(hi[c], L[k+c]); } mx = Math.max(mx, Math.hypot(L[k]-R[k], L[k+1]-R[k+1], L[k+2]-R[k+2])); }
    if (lo.every((v, c) => Math.abs(v - T.recs[i].bmin[c]) < 1e-3) && hi.every((v, c) => Math.abs(v - T.recs[i].bmax[c]) < 1e-3)) boxOk++;
    if (mx > 3) posedMove++;
  });
  out.halo = {drawn: drawn.size, haloRows: hl, haloed: haloIdx.length, moved: movedHalo.length, boxOk, posedMove, viaHost: !!ds};
  out.n.halos = haloIdx.length;

  // ---- back at rest: byte-identical
  PZ.reset(); await sleep(900);
  out.back = {mp: T.mp.points.every((p, k) => same(p.pos, rest[k])), s1: same(s1.entry.p, S1.E) && same(s1.target.p, S1.T), s2: same(s2.entry.p, S2.E) && same(s2.target.p, S2.T),
              shownAtRest: Array.from(shownSet).every(p => Math.abs(nearV('mp-core', p.pos) - 1.8) <= 0.05)};
  T.halos(false); T.emphasize(false); sel.markIds(mpIds, false);
  return out;
}"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("build_dir")
    ap.add_argument("--size", default="1400x900")
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

    r = {"err": "page did not load"}
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
            r = pg.evaluate(PROBE, [list(c) for c in CASES])
            b.close()
    finally:
        srv.terminate()

    if r.get("err"):
        print("  FAIL " + r["err"])
        print("Q328_OVERLAYS_FAIL")
        return 1
    m, s, h, bk, n = r["mp"], r["saved"], r["halo"], r["back"], r["n"]
    print(f"     {r['muscle']} / {r['joint']}: {n['mp']} motor points ({n['shown']} shown, {n['plan']} planned), {n['halos']} halos drawn")
    print(f"     overlay step per pose event: first {r['cost']['first']:.1f} ms (anchoring), then {r['cost']['next']:.1f} ms")
    if not r["hasMp"]:
        print(f"     n/a  motor-point checks: {r['mpMsg']}")
    else:
        check(f"motor points of the moved structures ride them ({m['moved']} of {m['n']} moved > 3 mm, max {m['maxMove']:.1f} mm)", m["n"] > 0 and m["moved"] > 0)
        check(f"those given within 5 mm of their structure keep their distance to its surface ({m['on']} points, {m['onMoved']} moved; max change {m['maxDd']:.3f} mm{', ' + str(m['worst']) if m['worst'] else ''})",
              m["onMoved"] > 0 and m["maxDd"] < 0.5)
        check(f"those inside their structure stay inside it ({m['left']} left it)", m["left"] == 0)
        for pid, d0, d1 in m["off"]:
            print(f"     info: {pid} is given {d0} mm off its own structure (rides the local surface; now {d1} mm from it)")
        check(f"motor points elsewhere keep their exact coordinates ({m['stillSame']} of {m['still']})", m["still"] > 0 and m["stillSame"] == m["still"])
        check(f"the shown motor-point markers are redrawn at the posed points ({m['shownMoved'] - m['shownOff']} of {m['shownMoved']})", m["shownMoved"] > 0 and m["shownOff"] == 0)
        check(f"the planned muscle's own motor points are redrawn there ({m['planMoved'] - m['planOff']} of {m['planMoved']})", m["planMoved"] > 0 and m["planOff"] == 0)
    check(f"the saved point in the moved limb rides it (entry {s['s1E']:.1f} / target {s['s1T']:.1f} mm)", s["s1Moved"] and s["s1E"] > 3 and s["s1T"] > 3)
    check(f"its surface distances are unchanged (entry {s['s1dE']:.3f} / target {s['s1dT']:.3f} mm)", s["s1dE"] < 0.5 and s["s1dT"] < 0.5)
    check(f"its marker is redrawn at the posed target ({s['s1Marker']:.3f} mm)", s["s1Marker"] < 0.1)
    check("the saved point on the other side does not move", not s["s2Moved"] and s["s2Same"])
    check(f"every halo is drawn through the page's own (posed) structure buffers ({h['haloed']} halos)", h["viaHost"] and h["haloed"] > 0 and h["haloRows"] > 0)
    check(f"the halos of the moved limb carry their posed surfaces ({h['posedMove']} of {h['moved']} moved > 3 mm, {h['boxOk']} posed boxes)",
          h["moved"] > 0 and h["posedMove"] > 0 and h["boxOk"] == h["moved"])
    check("back at rest: every motor point is byte-identical", bk["mp"] or not r["hasMp"])
    check("back at rest: both saved points are byte-identical", bk["s1"] and bk["s2"])
    check("back at rest: the motor-point markers are at the given points", bk["shownAtRest"])
    check(f"the per-event overlay step stays small (first {r['cost']['first']:.0f} ms < 400, then {r['cost']['next']:.0f} ms < 40)",
          r["cost"]["first"] < 400 and r["cost"]["next"] < 40)
    check(f"no page errors ({len(page_errors)})", not page_errors)
    for e in page_errors[:5]:
        print("     page error: " + e[:300])
    print()
    if errs:
        print(f"Q328_OVERLAYS_FAIL {len(errs)}")
        return 1
    print("Q328_OVERLAYS_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
