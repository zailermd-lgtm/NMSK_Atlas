#!/usr/bin/env python3
"""Q317: headless-Chromium checks of the needle tool's new aim, against a real built page.

Owner (Q317): "let the needle be rotated and/or its direction changed from the deep tip, from the
part where it crosses the skin, or from the hub, depending on what you want held and what you want
moved. Also let a skin entry point and an injection point be decided, and the system works out the
direction, the distance and the rest."

So the two things to prove are geometric, and are proved here on the shipped file, in a browser,
against the page's own meshes -- not on a copy of the arithmetic:

  * the pair of angles the panel shows is the axis the two placed points actually make
    (dirFrom(aimAngles()) must come back to the same unit vector), and
  * turning the needle holds exactly the point the pivot names and keeps its length.

    python3 scripts/anatomy/q317/verify_q317.py build/q309/viewer_zan_atlas [more dirs...]
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
LAUNCH_ARGS = ["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]
TOL = 1e-6


def serve(page_dir):
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "-d", str(page_dir)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    return srv, port


def route(rq):
    u = rq.request.url
    if "three" in u and u.endswith(".js") and ("cdnjs" in u or "jsdelivr" in u or "unpkg" in u):
        rq.fulfill(body=open(THREE, "rb").read(), content_type="application/javascript")
    elif "fonts.g" in u:
        rq.abort()
    else:
        rq.continue_()


def html_of(d: Path) -> str:
    c = sorted(d.glob("atlas_viewer*.html"))
    return c[0].name if c else "index.html"


def check(label, cond, errs):
    ok = bool(cond)
    print(("  OK  " if ok else "  FAIL") + " " + label)
    if not ok:
        errs.append(label)
    return ok


# Places a needle on a real muscle, then exercises the aim through the tool's own methods.
PROBE = """() => {
  const t = window.NMSKClinicalTool;
  const V = {
    sub: (a,b)=>[a[0]-b[0],a[1]-b[1],a[2]-b[2]],
    add: (a,b)=>[a[0]+b[0],a[1]+b[1],a[2]+b[2]],
    mul: (a,s)=>[a[0]*s,a[1]*s,a[2]*s],
    dot: (a,b)=>a[0]*b[0]+a[1]*b[1]+a[2]*b[2],
    len: a=>Math.hypot(a[0],a[1],a[2]),
    dist:(a,b)=>Math.hypot(a[0]-b[0],a[1]-b[1],a[2]-b[2]),
  };
  const norm = a => { const l = V.len(a) || 1; return [a[0]/l, a[1]/l, a[2]/l]; };

  // a real muscle, its bbox centre as the deep target, and an entry well outside it
  const m = t.recs.find(r => r.cat === 'muscle');
  if (!m) return {err: 'no muscle on this page'};
  const T = [0,1,2].map(k => (m.bmin[k] + m.bmax[k]) / 2);
  const span = Math.max(20, V.len(V.sub(m.bmax, m.bmin)));
  const E = V.add(T, V.mul(norm([0.6, 0.5, 0.62]), span));
  t.setPath(E, T, null, m.id);
  if (!t.entry || !t.target) return {err: 'setPath did not place'};

  const out = {target_name: m.name, mode: t.mode, pivots: {}};

  // 1. the angles are the axis: dirFrom(aimAngles()) must be the placed axis again
  const L0 = V.dist(t.entry.p, t.target.p);
  const u0 = V.mul(V.sub(t.target.p, t.entry.p), 1 / L0);
  const a0 = t.aimAngles();
  out.aim = a0;
  out.roundtrip_dot = a0 ? V.dot(norm(t.dirFrom(a0.tilt, a0.az)), u0) : null;
  out.length0 = L0;

  // 2. turning holds the point the pivot names, and keeps the length
  const u2 = norm(V.add(u0, V.mul(norm([-u0[1], u0[0], 0.3]), 0.45)));   // a genuinely different axis
  const hubLen = Math.max(10, 7 * t.rDisp);
  for (const pv of ['skin', 'tip', 'hub']) {
    t.setPath(E, T, null, m.id);                 // same start every time
    t.pivot = pv;
    const Eb = t.entry.p.slice(), Tb = t.target.p.slice();
    const Lb = V.dist(Eb, Tb), ub = V.mul(V.sub(Tb, Eb), 1 / Lb);
    const held = pv === 'tip' ? Tb
               : pv === 'skin' ? Eb
               : V.add(Tb, V.mul(ub, -(t.len + hubLen)));          // the hub end, behind the tip
    const ok = t.aimTo(u2);
    const Ea = t.entry.p.slice(), Ta = t.target.p.slice();
    const La = V.dist(Ea, Ta), ua = V.mul(V.sub(Ta, Ea), 1 / La);
    const heldAfter = pv === 'tip' ? Ta
                    : pv === 'skin' ? Ea
                    : V.add(Ta, V.mul(ua, -(t.len + hubLen)));
    out.pivots[pv] = {
      applied: ok,
      held_moved_mm: V.dist(held, heldAfter),
      length_change_mm: Math.abs(La - Lb),
      axis_dot: V.dot(ua, u2),
      tip_moved_mm: V.dist(Tb, Ta),
      entry_moved_mm: V.dist(Eb, Ea),
    };
  }

  // 3. the placement's report carries the direction
  t.setPath(E, T, null, m.id);
  const R = t.report();
  out.report_aim = R && R.aim ? {tilt: R.aim.tilt, az: R.aim.az} : null;
  out.report_pivot = R ? R.pivot : null;
  out.report_len = R ? R.length_mm : null;

  // 4. the pivot row follows the mode: offered with two points, not in the direction mode
  t.setMode('two', true); t.setPath(E, T, null, m.id); t.syncAimUI();
  out.row_two = !document.getElementById('ncl-pivot-row').hidden;
  out.box_two = !document.getElementById('ncl-dirbox').hidden;
  t.setMode('dir'); t.syncAimUI();
  out.row_dir = !document.getElementById('ncl-pivot-row').hidden;
  return out;
}"""


def run(pl, page_dir: Path, errs):
    html = html_of(page_dir)
    srv, port = serve(page_dir)
    try:
        b = pl.chromium.launch(args=LAUNCH_ARGS, executable_path="/opt/pw-browsers/chromium")
        ctx = b.new_context(viewport={"width": 1280, "height": 900})
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errs.append(f"{page_dir.name}: page error: {e}"))
        pg.route("**/*", route)
        print(f"=== {page_dir.name} ===")
        pg.goto(f"http://127.0.0.1:{port}/{html}", wait_until="load", timeout=90000)
        pg.wait_for_function("window.NMSKClinicalTool && window.NeedlePath", timeout=60000)
        pg.wait_for_timeout(1200)

        r = pg.evaluate(PROBE)
        if r.get("err"):
            errs.append(f"{page_dir.name}: {r['err']}")
            print("  FAIL " + r["err"])
            return
        print(f"     target {r['target_name']}, path {r['length0']:.1f} mm, "
              f"aim {r['aim']['tilt']:.1f} deg / {r['aim']['az']:.1f} deg")

        check("the two angles shown are the axis the two points make (round trip)",
              r["roundtrip_dot"] is not None and abs(r["roundtrip_dot"] - 1) < 1e-9, errs)
        check("report() carries the direction the placement implies",
              r["report_aim"] and abs(r["report_aim"]["tilt"] - r["aim"]["tilt"]) < 1e-9, errs)
        check("report() names the pivot in force", r["report_pivot"] in ("skin", "tip", "hub"), errs)

        for pv, label in (("skin", "the skin crossing"), ("tip", "the tip"), ("hub", "the hub")):
            d = r["pivots"][pv]
            check(f"turning about {label}: it is applied", d["applied"], errs)
            check(f"turning about {label}: {label} stays put ({d['held_moved_mm']:.2e} mm)",
                  d["held_moved_mm"] < 1e-6, errs)
            check(f"turning about {label}: the path keeps its length ({d['length_change_mm']:.2e} mm)",
                  d["length_change_mm"] < 1e-6, errs)
            check(f"turning about {label}: the needle ends on the asked-for axis",
                  abs(d["axis_dot"] - 1) < 1e-9, errs)
        # and the pivot really is a choice: holding the tip must move the entry, and holding the skin the tip
        check("holding the tip moves the entry instead", r["pivots"]["tip"]["entry_moved_mm"] > 1.0, errs)
        check("holding the skin moves the tip instead", r["pivots"]["skin"]["tip_moved_mm"] > 1.0, errs)

        check("the pivot is offered once two points are placed", r["row_two"] and r["box_two"], errs)
        check("the pivot is not offered in the direction mode, where the entry is the pivot by construction",
              not r["row_dir"], errs)
        ctx.close(); b.close()
    finally:
        srv.terminate()


def main() -> int:
    dirs = [Path(a) for a in sys.argv[1:]] or [REPO / "build" / "q309" / "viewer_zan_atlas"]
    errs: list[str] = []
    with sync_playwright() as pl:
        for d in dirs:
            run(pl, d if d.is_absolute() else REPO / d, errs)
    print()
    if errs:
        print(f"Q317_VERIFY_FAIL {len(errs)}")
        for e in errs:
            print("  - " + e)
        return 1
    print("Q317_VERIFY_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
