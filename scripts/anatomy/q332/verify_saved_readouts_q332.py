#!/usr/bin/env python3
"""Q332: a saved injection point's readout (nearest vessel / nerve and its distance) is measured again on the posed body.

Checked in headless Chromium (software rendering) against a built page that carries the current private add-ons:

  * saved points in the calf (popliteus, plantaris, gastrocnemius, soleus) and the forearm (pronator teres, brachioradialis),
    each planned into the muscle with the entry on the skin, plus one on the other limb;
  * the knee / elbow is flexed 60 deg in two quick steps: the readouts are measured again once, after the burst; at least
    one changes; every re-measured readout equals an independent measurement made here from the posed vertex buffers
    (window.__poseLive, sampled segment-to-triangle distance -- not the add-on's code) within 0.5 mm; the list says
    "current pose";
  * the points on the other limb (and the other joint's points) keep their saved values exactly;
  * back at rest every readout is the saved one exactly and the list says "rest pose"; no page errors.

    python3 scripts/anatomy/q332/verify_saved_readouts_q332.py <page dir> [--size 1400x900]
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
CASES = [("knee_r", ["popliteus_r", "plantaris_r", "gastrocnemius_r", "soleus_r"]),
         ("elbow_r", ["pronator_teres_r", "brachioradialis_r"])]
TOL = 0.5


def serve(d):
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close()
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(p), "--bind", "127.0.0.1", "-d", str(d)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1); return srv, p


PROBE = r"""async ([cases, TOL]) => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const T = window.NMSKClinicalTool, PZ = window.__poseApi, U = window.NMSKUltrasound, LIB = window.NMSKUltrasoundLib, NP = window.NeedlePath;
  if (!T || !PZ || !U || !LIB || !NP) return {err: 'needle tool / scan tool / pose rig missing'};
  await U.ready();
  if (!T.active) T.toggle(true);
  const add = (a, b, s) => [a[0] + b[0]*s, a[1] + b[1]*s, a[2] + b[2]*s], dist = (a, b) => Math.hypot(a[0]-b[0], a[1]-b[1], a[2]-b[2]);
  const joints = new Set(PZ.rig().joints.map(j => j.id));
  // ---- a plan into a muscle: the target midway through it, the entry where the shortest of a few lines leaves the skin
  const DIRS = [[1,0,0],[-1,0,0],[0,1,0],[0,-1,0],[0.7,0.7,0],[-0.7,0.7,0],[0.7,-0.7,0],[-0.7,-0.7,0]];
  function planInto(m) {
    if (!T.byId[m]) return null;
    const mi = T.byId[m][0], g = T.geom(mi), n = g.pos.length / 3, geo = U.geo(); let c = [0, 0, 0], best = null;
    for (let k = 0; k < n; k++) for (let a = 0; a < 3; a++) c[a] += g.pos[3*k + a] / n;
    DIRS.forEach(d => {
      const back = [-d[0], -d[1], -d[2]], o = add(c, d, 300), hs = T.rayAll(mi, o, back, 0, 1e9).map(q => q.t).sort((a, b) => a - b);
      if (hs.length < 2) return;
      const Tg = add(o, d, -(hs[0] + hs[1]) / 2), h = LIB.skinHit(geo, add(Tg, d, 300), back, null);
      if (!h) return;
      const L = dist(h.point, Tg);
      if (!best || L < best.L) best = {E: h.point, Tg, L, skin: geo.recs[h.struct].id};
    });
    if (!best) return null;
    NP.setPoints(best.E, best.Tg, best.skin, m);
    const it = T.addSavedPoint();
    return it ? {id: it.id, muscle: m} : null;
  }
  // ---- the independent measurement: posed vertex buffers + the page's index buffers, sampled segment, own point-triangle code
  function ptTri2(p, P, a, b, c) {
    const ax = P[a], ay = P[a+1], az = P[a+2], abx = P[b]-ax, aby = P[b+1]-ay, abz = P[b+2]-az, acx = P[c]-ax, acy = P[c+1]-ay, acz = P[c+2]-az;
    const apx = p[0]-ax, apy = p[1]-ay, apz = p[2]-az, d1 = abx*apx+aby*apy+abz*apz, d2 = acx*apx+acy*apy+acz*apz;
    const q = (x, y, z) => { const dx = p[0]-x, dy = p[1]-y, dz = p[2]-z; return dx*dx+dy*dy+dz*dz; };
    if (d1 <= 0 && d2 <= 0) return q(ax, ay, az);
    const bpx = p[0]-P[b], bpy = p[1]-P[b+1], bpz = p[2]-P[b+2], d3 = abx*bpx+aby*bpy+abz*bpz, d4 = acx*bpx+acy*bpy+acz*bpz;
    if (d3 >= 0 && d4 <= d3) return q(P[b], P[b+1], P[b+2]);
    const vc = d1*d4 - d3*d2;
    if (vc <= 0 && d1 >= 0 && d3 <= 0) { const v = d1/(d1-d3); return q(ax+v*abx, ay+v*aby, az+v*abz); }
    const cpx = p[0]-P[c], cpy = p[1]-P[c+1], cpz = p[2]-P[c+2], d5 = abx*cpx+aby*cpy+abz*cpz, d6 = acx*cpx+acy*cpy+acz*cpz;
    if (d6 >= 0 && d5 <= d6) return q(P[c], P[c+1], P[c+2]);
    const vb = d5*d2 - d1*d6;
    if (vb <= 0 && d2 >= 0 && d6 <= 0) { const w = d2/(d2-d6); return q(ax+w*acx, ay+w*acy, az+w*acz); }
    const va = d3*d6 - d5*d4;
    if (va <= 0 && (d4-d3) >= 0 && (d5-d6) >= 0) { const w = (d4-d3)/((d4-d3)+(d5-d6)); return q(P[b]+w*(P[c]-P[b]), P[b+1]+w*(P[c+1]-P[b+1]), P[b+2]+w*(P[c+2]-P[b+2])); }
    const den = 1/(va+vb+vc), v = vb*den, w = vc*den;
    return q(ax+abx*v+acx*w, ay+aby*v+acy*w, az+abz*v+acz*w);
  }
  const CORR = {artery: 1, vein: 1, nerve: 1};
  function independent(sp) {
    const A = sp.entry || sp.target, B = sp.target, R = sp.R, L = dist(A, B), ns = Math.max(1, Math.ceil(L / 0.2));
    const S = []; for (let k = 0; k <= ns; k++) S.push(add(A, [B[0]-A[0], B[1]-A[1], B[2]-A[2]], k / ns));
    const lo = [0,1,2].map(k => Math.min(A[k], B[k]) - R), hi = [0,1,2].map(k => Math.max(A[k], B[k]) + R), out = [];
    T.recs.forEach((r, i) => {
      if (!CORR[T.cls[i]] || r.id === sp.skip_id) return;
      const g = T.api.geometry(i); if (!g) return;
      const P = (typeof window.__poseLive === 'function' && window.__poseLive(i)) || g.pos, I = g.idx;
      let best = Infinity;
      for (let f = 0; f < I.length; f += 3) {
        const a = I[f]*3, b = I[f+1]*3, c = I[f+2]*3; let skip = false;
        for (let k = 0; k < 3 && !skip; k++) { const mn = Math.min(P[a+k], P[b+k], P[c+k]), mx = Math.max(P[a+k], P[b+k], P[c+k]); if (mx < lo[k] || mn > hi[k]) skip = true; }
        if (skip) continue;
        for (let s = 0; s < S.length; s++) { const d2 = ptTri2(S[s], P, a, b, c); if (d2 < best) best = d2; }
      }
      best = Math.sqrt(best);
      if (best <= R) out.push({i, id: r.id, d: best});
    });
    out.sort((x, y) => x.d - y.d);
    return out;
  }
  const sps = () => NP.savedPoints(), byId = id => sps().find(s => s.id === id);
  const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
  const listText = () => { const e = document.getElementById('ncl-save-pose'); return e ? e.textContent : null; };
  // every saved point first, at rest
  const res = {cases: [], pts: []}, all = [];
  cases.forEach(([jid, muscles]) => {
    if (!joints.has(jid)) return;
    const mine = [];
    muscles.forEach(m => { const p = planInto(m); if (p) { p.joint = jid; mine.push(p); all.push(p); } });
    const other = mine.length ? planInto(mine[0].muscle.replace(/_r$/, '_l')) : null;
    if (other) { other.joint = jid; other.other = true; all.push(other); }
  });
  T.clear && T.clear();   // the working plan is cleared: only the saved points are left
  await sleep(400);
  if (!all.length) return {err: 'no saved point could be planned'};
  const saved = {}; sps().forEach(s => { saved[s.id] = s; });
  all.forEach(p => { const s = saved[p.id]; p.nearest0 = s.nearest ? [s.nearest.name, +s.nearest.d_mm.toFixed(2)] : null; });
  res.restText = listText();
  // count the re-measures per pose burst
  let reCalls = 0; const rm = T.remeasureSaved.bind(T); T.remeasureSaved = function () { const n = rm(); reCalls += n; return n; };
  for (const [jid] of cases) {
    if (!joints.has(jid)) continue;
    const C = {joint: jid, pts: []};
    reCalls = 0;
    PZ.set(jid, 'flex', 30); PZ.set(jid, 'flex', 60);
    const immediate = sps();
    await sleep(900);
    C.reCalls = reCalls; C.text = listText();
    const now = sps();
    C.unchangedBeforeTimer = immediate.every(s => same(s.items, saved[s.id].items));
    for (const p of all) {
      const s = now.find(x => x.id === p.id), s0 = saved[p.id], mine = p.joint === jid && !p.other;
      const row = {muscle: p.muscle, mine, other: !!p.other, measured_in: s.measured_in, keptSame: same(s.items, s0.items) && same(s.saved_items, s0.items)};
      if (mine) {
        const ind = independent(s), byI = {}; ind.forEach(x => { byI[x.i] = x.d; });
        let worst = 0, missing = 0;
        s.items.forEach(x => { if (byI[x.i] == null) missing++; else worst = Math.max(worst, Math.abs(byI[x.i] - x.d_mm)); });
        const n0 = s.items[0], i0 = ind[0];
        row.nearest = n0 ? [n0.id, +n0.d_mm.toFixed(2)] : null; row.indNearest = i0 ? [i0.id, +i0.d.toFixed(2)] : null;
        row.nearestDiff = n0 && i0 ? Math.abs(n0.d_mm - i0.d) : (n0 || i0 ? 1e9 : 0);
        row.worst = worst; row.missing = missing; row.nItems = s.items.length;
        const d0 = {}; s0.items.forEach(x => { d0[x.i] = x.d_mm; });
        row.change = Math.max(0, ...s.items.filter(x => d0[x.i] != null).map(x => Math.abs(x.d_mm - d0[x.i])));
        row.setChanged = !same(s.items.map(x => x.i), s0.items.map(x => x.i));
        row.nearestChange = n0 && s0.items[0] ? Math.abs(n0.d_mm - s0.items[0].d_mm) : 0;
      }
      C.pts.push(row);
    }
    PZ.reset(); await sleep(900);
    const back = sps();
    C.backSame = back.every(s => same(s.items, saved[s.id].items) && s.n === saved[s.id].n);
    C.backKey = back.every(s => s.measured_in === 'rest');
    C.backText = listText();
    res.cases.push(C);
  }
  res.pts = all.map(p => ({muscle: p.muscle, joint: p.joint, other: !!p.other, nearest0: p.nearest0}));
  T.clearSavedPoints();
  return res;
}"""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("page_dir")
    ap.add_argument("--size", default="1400x900")
    a = ap.parse_args()
    d = Path(a.page_dir).resolve()
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
            r = pg.evaluate(PROBE, [[[j, m] for j, m in CASES], TOL])
            b.close()
    finally:
        srv.terminate()

    if r.get("err"):
        print("  FAIL " + r["err"])
        print("Q332_READOUTS_FAIL")
        return 1
    for p in r["pts"]:
        print(f"     saved: {p['muscle']:<20} ({p['joint']}{', other limb' if p['other'] else ''}) nearest at save {p['nearest0']}")
    check(f"the saved-points list says \"rest pose\" at rest ({r['restText']!r})", r["restText"] and "rest pose" in r["restText"])
    check(f"both joints exercised ({len(r['cases'])})", len(r["cases"]) == 2)
    for C in r["cases"]:
        mine = [p for p in C["pts"] if p["mine"]]
        rest = [p for p in C["pts"] if not p["mine"]]
        print(f"   -- {C['joint']} flexed 60 deg: {len(mine)} points of this limb, {len(rest)} elsewhere")
        for p in mine:
            print(f"     {p['muscle']:<20} now {p['nearest']} (independent {p['indNearest']}); worst item diff {p['worst']:.3f} mm over {p['nItems']}; "
                  f"change since save {p['change']:.2f} mm (nearest {p['nearestChange']:.2f}){'; the list of structures within R changed' if p['setChanged'] else ''}")
        check(f"{C['joint']}: nothing is re-measured inside the burst", C["unchangedBeforeTimer"])
        check(f"{C['joint']}: one re-measure per point after the burst ({C['reCalls']} for {len(mine)} points)", 0 < C["reCalls"] <= len(mine) + len(rest) and C["reCalls"] >= 1)
        check(f"{C['joint']}: the points of the flexed limb are measured on the current pose",
              mine and all(p["measured_in"] != "rest" for p in mine))
        check(f"{C['joint']}: at least one readout changes (max {max((p['change'] for p in mine), default=0):.2f} mm; "
              f"{sum(p['setChanged'] for p in mine)} with another set of structures within R)",
              any(p["change"] > TOL or p["setChanged"] for p in mine))
        check(f"{C['joint']}: every re-measured readout equals the independent measurement of the posed meshes within {TOL} mm "
              f"(worst {max((max(p['worst'], p['nearestDiff']) for p in mine), default=0):.3f} mm)",
              mine and all(p["worst"] < TOL and p["nearestDiff"] < TOL and p["missing"] == 0 for p in mine))
        check(f"{C['joint']}: the other limb's / other joint's saved points keep their values exactly ({sum(p['keptSame'] for p in rest)} of {len(rest)})",
              rest and all(p["keptSame"] and p["measured_in"] == "rest" for p in rest))
        check(f"{C['joint']}: the list says \"current pose\" while posed ({C['text']!r})", C["text"] and "current pose" in C["text"])
        check(f"{C['joint']}: back at rest every readout is the saved one exactly", C["backSame"] and C["backKey"])
        check(f"{C['joint']}: the list says \"rest pose\" back at rest", C["backText"] and "rest pose" in C["backText"])
    check(f"no page errors ({len(page_errors)})", not page_errors)
    for e in page_errors[:5]:
        print("     page error: " + e[:300])
    print()
    if errs:
        print(f"Q332_READOUTS_FAIL {len(errs)}")
        return 1
    print("Q332_READOUTS_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
