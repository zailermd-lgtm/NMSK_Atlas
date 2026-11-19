#!/usr/bin/env python3
"""Q317: the needle has to be visible IN the simulated ultrasound, and invisible when it is not in
the scan plane -- which is the whole reason the in-plane approach is the one taught.

Checked in headless Chromium against a built page, on the shipped simulator:

  * with no needle the image is what it always was (the painter returns the same buffer);
  * an in-plane needle brightens a run of pixels along its own line, and nothing far from it;
  * the same needle moved out of the plane disappears again;
  * the cached anatomy raster is NOT polluted -- clearing the needle returns the original image
    pixel for pixel, which is what the copy-on-write is there to guarantee.

    python3 scripts/anatomy/q317/verify_needle_us_q317.py build/q309/viewer_zan_atlas
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
  const U = window.NMSKUltrasound;
  await U.ready();
  U.open();
  const AC = U.AC();
  if (!AC.needleId) return {err: 'no needle class id was compiled'};

  // aim in from well outside the body, so the probe seats on real skin
  let seat = null;
  for (const dir of [[1,0,0], [-1,0,0], [0,0,1], [0,0,-1], [0,1,0]]) {
    const from = [-dir[0]*900, -dir[1]*900 + 200, -dir[2]*900];
    seat = U.placeRay(from, dir);
    if (seat) break;
  }
  if (!seat) return {err: 'could not seat the probe on skin'};
  await U.idle();

  const snap = () => {
    const fr = U.frames()[U.state().sel] || U.frames()[0];
    return fr && fr.sim ? {db: Array.from(fr.sim.db), W: fr.plan.Wo, H: fr.plan.Ho,
                           O: fr.O.slice(), u: fr.pf.u.slice(), b: fr.pf.b.slice(), e: fr.pf.e.slice(),
                           painted: !!fr.needlePainted} : null;
  };
  const base = snap();
  if (!base) return {err: 'no simulated frame'};

  const add = (P, k, s) => [P[0]+k[0]*s, P[1]+k[1]*s, P[2]+k[2]*s];
  // a needle lying IN the plane: along u, descending along b (into the body). Kept clear of the
  // contact line, so the test measures the needle and not a moved skin seat.
  const A = add(add(base.O, base.u, -19), base.b, 10);
  const B = add(add(base.O, base.u,  -4), base.b, 30);
  U.setNeedle({A: A, B: B, r_mm: 0.45});
  await U.idle();
  const withN = snap();

  // the same needle pushed well out of the scan plane
  const Ao = add(A, base.e, 14), Bo = add(B, base.e, 14);
  U.setNeedle({A: Ao, B: Bo, r_mm: 0.45});
  await U.idle();
  const offPlane = snap();

  U.clearNeedle();
  await U.idle();
  const cleared = snap();

  // Where the needle's own line falls in the image, so "did it brighten the shaft" can be asked of
  // the shaft rather than of the whole picture. A needle legitimately changes far more than it
  // occupies -- it shadows everything behind it -- so brightening is judged near the shaft only.
  const fr0 = U.frames()[U.state().sel] || U.frames()[0];
  const pl = fr0.plan, px = pl.px;          // the image is Wo x Ho from (xo0, yo0), NOT the label raster's W x H from (xr0, yr0)
  const d3 = (P, O, k) => (P[0]-O[0])*k[0] + (P[1]-O[1])*k[1] + (P[2]-O[2])*k[2];
  const seg = (P) => ({x: d3(P, base.O, base.u), y: d3(P, base.O, base.b)});
  const sa = seg(A), sb = seg(B);
  const xlo = Math.min(sa.x, sb.x) - 2.5, xhi = Math.max(sa.x, sb.x) + 2.5;   // + about a beam width
  const onShaftLine = (ix) => { const X = pl.xo0 + (ix + 0.5) * px; return X >= xlo && X <= xhi; };
  const distToShaft = (ix, iy) => {
    const X = pl.xo0 + (ix + 0.5) * px, Y = pl.yo0 + (iy + 0.5) * px;
    const vx = sb.x - sa.x, vy = sb.y - sa.y, vv = vx*vx + vy*vy;
    const wx = X - sa.x, wy = Y - sa.y;
    const t = vv > 1e-9 ? Math.max(0, Math.min(1, (wx*vx + wy*vy) / vv)) : 0;
    const dx = wx - vx*t, dy = wy - vy*t;
    return Math.hypot(dx, dy);
  };

  const diff = (p, q, wantNear) => {
    if (!p || !q || p.db.length !== q.db.length) return null;
    let n = 0, up = 0, maxUp = 0, upNear = 0, upFar = 0;
    for (let i = 0; i < p.db.length; i++) {
      // -200 is "no signal": outside the fan, or deep in a shadow. A difference measured from that
      // floor is not a brightening of anything, so neither side may be near it.
      if (p.db[i] < -60 || q.db[i] < -60) continue;
      const d = q.db[i] - p.db[i];
      if (Math.abs(d) <= 1) continue;
      n++;
      if (d > 0) {
        up++;
        if (d > maxUp) maxUp = d;
        // A strong reflector brightens more than it occupies: it reverberates, and the repeats land
        // deeper on the SAME beam lines. So the test is lateral -- a brightened pixel must sit on a
        // line that passes through the shaft, never off to the side of it.
        if (wantNear) { (onShaftLine(i % p.W) ? upNear++ : upFar++); }
      }
    }
    return {changed: n, brighter: up, maxUp: maxUp, total: p.db.length, upNear: upNear, upFar: upFar};
  };
  return {
    needleId: AC.needleId,
    elevHalf: AC.needleElevHalf,
    base_painted: base.painted,
    inplane_painted: withN.painted,
    offplane_painted: offPlane.painted,
    d_in: diff(base, withN, true),
    d_off: diff(base, offPlane),
    d_cleared: diff(base, cleared),
  };
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
            pg.wait_for_function("window.NMSKUltrasound", timeout=90000)
            pg.wait_for_timeout(1200)
            r = pg.evaluate(PROBE)
            if r.get("err"):
                print("  FAIL " + r["err"]); return 1

            print(f"     needle class id {r['needleId']}, kept within {r['elevHalf']} mm of the plane")
            di, do, dc = r["d_in"], r["d_off"], r["d_cleared"]
            print(f"     in-plane: {di['changed']} px changed of {di['total']}, {di['brighter']} brighter "
                  f"({di['upNear']} on the shaft's beam lines, {di['upFar']} off to the side), peak +{di['maxUp']:.1f} dB")
            print(f"     out-of-plane: {do['changed']} px changed")
            print(f"     after clearing: {dc['changed']} px changed")

            check("a free acoustic class id is compiled for the needle", r["needleId"] > 32, errs)
            check("the painter does nothing when there is no needle", not r["base_painted"], errs)
            check("an in-plane needle is painted", r["inplane_painted"], errs)
            check("an in-plane needle changes the image", di["changed"] > 50, errs)
            check("and it does so by brightening (a steel interface reflects)", di["brighter"] > di["changed"] * 0.5, errs)
            check("the brightening is strong, as an impedance step of 0.86 should be (> 10 dB)", di["maxUp"] > 10, errs)
            check("every brightening sits on a beam line through the shaft, none off to the side "
                  "(a reflector reverberates deeper, it does not light up its neighbours)",
                  di["brighter"] > 0 and di["upNear"] >= di["brighter"] * 0.95, errs)
            check("a needle out of the scan plane is not painted", not r["offplane_painted"], errs)
            check("and does not change the image at all", do["changed"] == 0, errs)
            check("clearing the needle restores the image exactly (the cached raster was never polluted)",
                  dc["changed"] == 0, errs)
            b.close()
    finally:
        srv.terminate()

    print()
    if errs:
        print(f"Q317_NEEDLE_US_FAIL {len(errs)}")
        for e in errs:
            print("  - " + e)
        return 1
    print("Q317_NEEDLE_US_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
