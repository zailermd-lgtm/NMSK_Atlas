#!/usr/bin/env python3
"""Q307: real headless-Chromium check of the nerve placement fix (desktop 1400x900 real clicks + phone 390x844
real touch).

A  THE OWNER'S OWN CASE, END TO END. "Lateral antebrachial cutaneous nerve" is typed into the page's OWN search box
   (`#q` on an Imaging page, `#search` on a Z page -- the difference that bit Q297), the row is opened with a real
   click / a real touch, and its card is asserted to carry Q307's measured placement: the distance to the page's
   own brachioradialis, the distance to its own musculocutaneous nerve, how far short of the wrist it stops, and
   both cadaveric citations. On the two Imaging pages, where it did not exist at all before this round, the card
   must also open with "NOT SEGMENTED FROM THIS SUBJECT'S OWN IMAGING" and must never say "Measured on this body".
   Both sides are checked, because the whole point of the round is that a nerve must not exist on one side only.
B  THE POSITION IS MEASURED IN THE BROWSER, off the page's own buffers, not taken from a data file: the nerve's own
   vertices against the page's own radius, ulna, brachioradialis and musculocutaneous nerve, and the answer must
   match data/derived/Q307_lacn_measurements.json.
C  THE REPAIRED NERVES. On Imaging M the right tibial nerve was a 40 mm mirrored stub with its plantar nerves
   436.6 mm away; on Imaging F the left tibial and left femoral were 37 and 29 mm. Each is measured in the page
   and must now be the full nerve, with its own branches touching it.
D  EVERY TRANSFERRED STRUCTURE IS ON THE PAGE, in the `nerve` layer, with a bounding box matching the geometry
   report to 0.2 mm, and the page's counts are the report's counts.
E  Q303's ON-SCREEN MISSING-NERVE LIST shrank: the upper-limb names it used to report missing on an Imaging page
   are not reported missing any more, read from the page's own probe.
F  0 page errors, both viewports.

    python3 scripts/anatomy/q307/verify_q307.py PAGE_DIR... [--json OUT] [--phone=0|1]
"""
from __future__ import annotations
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "scripts/anatomy/q283"))
sys.path.insert(0, str(REPO / "scripts/anatomy/q304"))
import verify_q283 as V        # noqa: E402
import verify_q304 as Q4       # noqa: E402  (its ready / open_card / press / name_of / close_card carry six
                               #              harness lessons each; reusing the code is how they stay heeded)
from playwright.sync_api import sync_playwright  # noqa: E402

KEY = Q4.KEY
LACN = "zan_lateral_antebrachial_cutaneous_nerve"
NAME = "Lateral antebrachial cutaneous nerve"
OKN = [0]
REPORT: dict = {}
UPPER_NOT_MISSING = ["median", "ulnar", "radial", "axillary", "suprascapular", "long thoracic"]

# Measured in the page, off its own buffers: the nerve in a forearm frame built from the page's own radius and
# ulna, exactly as place307.py does it on disk, so the two answers are comparable.
POS_JS = r"""(side) => {
  const a = window.NMSKClinicalTool ? window.NMSKClinicalTool.api : null;
  function rows() {
    if (a) return a.list().map(r => ({id: r.id, i: r.i}));
    const o = (window.__ANATOMY_MANIFEST__ || {meshes: []}).meshes || [];
    return o.map((m, i) => ({id: m.id, i: i}));
  }
  function pts(id) {
    const R = rows().filter(r => r.id === id);
    if (!R.length) return null;
    const out = [];
    for (const r of R) {
      let g = null;
      if (a) g = a.geometry(r.i);
      else if (window.__ANATOMY_GEOM__) g = window.__ANATOMY_GEOM__(r.i);
      if (!g || !g.pos) return null;
      for (let k = 0; k < g.pos.length; k += 3) out.push([g.pos[k], g.pos[k+1], g.pos[k+2]]);
    }
    return out;
  }
  function mean(P){ const c=[0,0,0]; P.forEach(p=>{c[0]+=p[0];c[1]+=p[1];c[2]+=p[2];}); return c.map(v=>v/P.length); }
  function sub(p,q){ return [p[0]-q[0],p[1]-q[1],p[2]-q[2]]; }
  function dot(p,q){ return p[0]*q[0]+p[1]*q[1]+p[2]*q[2]; }
  function norm(p){ const n=Math.sqrt(dot(p,p))||1e-9; return [p[0]/n,p[1]/n,p[2]/n]; }
  function axis(P){ // power iteration on the covariance: the mesh's own principal direction
    const c = mean(P); let v = [1,0,0];
    for (let it = 0; it < 40; it++) {
      const w = [0,0,0];
      for (const p of P) { const d = sub(p,c), s = dot(d,v); w[0]+=s*d[0]; w[1]+=s*d[1]; w[2]+=s*d[2]; }
      v = norm(w);
    }
    return [c, v];
  }
  function minDist(A, B) { // sampled: every 7th point of A against every 11th of B, enough for a mm-level answer
    let best = 1e18;
    for (let i = 0; i < A.length; i += 7) for (let j = 0; j < B.length; j += 11) {
      const d = sub(A[i], B[j]), s = d[0]*d[0]+d[1]*d[1]+d[2]*d[2];
      if (s < best) best = s;
    }
    return Math.sqrt(best);
  }
  const L = pts("zan_lateral_antebrachial_cutaneous_nerve_" + side);
  const rad = pts("radius_" + side), uln = pts("ulna_" + side), hum = pts("humerus_" + side);
  const br = pts("brachioradialis_" + side), mcn = pts("musculocutaneous_n_" + side);
  if (!L || !rad || !uln || !hum) return {present: !!L, frame: false};
  let [c, u] = axis(rad);
  const t = rad.map(p => dot(sub(p, c), u));
  const tmin = Math.min.apply(null, t), tmax = Math.max.apply(null, t);
  const e0 = [c[0]+u[0]*tmin, c[1]+u[1]*tmin, c[2]+u[2]*tmin];
  const e1 = [c[0]+u[0]*tmax, c[1]+u[1]*tmax, c[2]+u[2]*tmax];
  if (minDist([e0], hum) > minDist([e1], hum)) { u = [-u[0],-u[1],-u[2]]; }
  const t2 = rad.map(p => dot(sub(p, c), u));
  const t2min = Math.min.apply(null, t2), t2max = Math.max.apply(null, t2);
  const L0 = [c[0]+u[0]*t2min, c[1]+u[1]*t2min, c[2]+u[2]*t2min];
  const len = t2max - t2min;
  const cu = mean(uln);
  let w = sub(c, cu); const s = dot(w, u); w = norm([w[0]-s*u[0], w[1]-s*u[1], w[2]-s*u[2]]);
  const tL = L.map(p => dot(sub(p, L0), u) / len);
  const rL = L.map(p => dot(sub(p, c), w)).sort((x, y) => x - y);
  return {present: true, frame: true, nv: L.length,
          t_min: Math.min.apply(null, tL), t_max: Math.max.apply(null, tL),
          radial_p50: rL[Math.floor(rL.length / 2)],
          ulna_axis_p50: (function(){ const q = uln.map(p => dot(sub(p, c), w)).sort((x,y)=>x-y);
                                      return q[Math.floor(q.length/2)]; })(),
          d_brachioradialis: br ? minDist(L, br) : null,
          d_musculocutaneous: mcn ? minDist(L, mcn) : null};
}"""

LEN_JS = r"""(ids) => {
  const a = window.NMSKClinicalTool.api, L = a.list(), out = {};
  function pts(id) {
    const R = L.filter(r => r.id === id); if (!R.length) return null;
    const o = [];
    for (const r of R) { const g = a.geometry(r.i); if (!g) return null;
      for (let k = 0; k < g.pos.length; k += 3) o.push([g.pos[k], g.pos[k+1], g.pos[k+2]]); }
    return o;
  }
  function mean(P){ const c=[0,0,0]; P.forEach(p=>{c[0]+=p[0];c[1]+=p[1];c[2]+=p[2];}); return c.map(v=>v/P.length); }
  function sub(p,q){ return [p[0]-q[0],p[1]-q[1],p[2]-q[2]]; }
  function dot(p,q){ return p[0]*q[0]+p[1]*q[1]+p[2]*q[2]; }
  function norm(p){ const n=Math.sqrt(dot(p,p))||1e-9; return [p[0]/n,p[1]/n,p[2]/n]; }
  ids.forEach(function(pair){
    const A = pts(pair[0]), B = pair[1] ? pts(pair[1]) : null;
    if (!A) { out[pair[0]] = null; return; }
    const c = mean(A); let v = [1,0,0];
    for (let it = 0; it < 40; it++) { const w=[0,0,0];
      for (const p of A) { const d = sub(p,c), s = dot(d,v); w[0]+=s*d[0]; w[1]+=s*d[1]; w[2]+=s*d[2]; }
      v = norm(w); }
    const t = A.map(p => dot(sub(p,c), v));
    let d = null;
    // EVERY vertex against every vertex, stride 1. A strided version (every 5th of A against every 7th of B)
    // over-read the parent/branch gap by millimetres on a 600-vertex tube whose vertices sit about 1 mm apart --
    // it reported 5.15 and 7.69 mm for femoral_n -> saphenous_n on Imaging F where the dense surface measurement
    // in val307 gives 0.36 and 0.27 mm, and those two numbers were the only FAILs of a 392-assertion run. The
    // threshold is Q298's measured 3.46 mm contact band, so the sampling has to be finer than the threshold.
    if (B) { let best = 1e18;
      for (let i = 0; i < A.length; i++) for (let j = 0; j < B.length; j++) {
        const q = sub(A[i], B[j]), s = q[0]*q[0]+q[1]*q[1]+q[2]*q[2]; if (s < best) best = s; }
      d = Math.sqrt(best); }
    out[pair[0]] = {axis_len: Math.max.apply(null, t) - Math.min.apply(null, t), nv: A.length, d_parent: d};
  });
  return out;
}"""


def check(label, cond, errs):
    good = V.check(label, cond, errs)
    if good:
        OKN[0] += 1
    return good


def card_text(pg, side_name, phone, want):
    """open the card through the page's own search box with a real press, and return its text."""
    txt = Q4.open_card(pg, side_name, phone, want=want)
    return txt or ""


def section_a(pg, T, R, errs, phone, key, lacn):
    """the owner's own case, through the real UI, on both sides."""
    own = key in ("own_m", "own_f")
    seen = {}
    for side in ("l", "r"):
        sid = LACN + "_" + side
        nm = Q4.name_of(pg, sid) or NAME
        txt = card_text(pg, nm, phone, want=NAME.split()[0])
        seen[side] = len(txt)
        ok = check("%s: the %s lateral antebrachial cutaneous nerve's card opens through the page's own search box "
                   "(%d characters)" % (T, side.upper(), len(txt)), len(txt) > 400, errs)
        if not ok:
            continue
        check("%s: %s card carries Q307's measured placement" % (T, side.upper()),
              "Q307 MEASURED PLACEMENT" in txt, errs)
        check("%s: %s card states how far short of the wrist it stops" % (T, side.upper()),
              "short of the wrist" in txt, errs)
        check("%s: %s card states its measured distance to the brachioradialis" % (T, side.upper()),
              "brachioradialis surface" in txt, errs)
        check("%s: %s card names its parent, the musculocutaneous nerve" % (T, side.upper()),
              "musculocutaneous nerve" in txt, errs)
        check("%s: %s card carries both cadaveric citations" % (T, side.upper()),
              "38128746" in txt and "38934998" in txt, errs)
        check("%s: %s card states the two defects that remain" % (T, side.upper()),
              "THE TWO DEFECTS THAT REMAIN" in txt, errs)
        if own:
            check("%s: %s card opens by saying it was NOT segmented from this subject's own imaging" % (T, side.upper()),
                  "NOT SEGMENTED FROM THIS SUBJECT'S OWN IMAGING" in txt, errs)
            check("%s: %s card never says 'Measured on this body'" % (T, side.upper()),
                  "Measured on this body" not in txt, errs)
            check("%s: %s card states the gate it had to pass" % (T, side.upper()),
                  "WHY IT WAS ALLOWED ONTO THE PAGE AT ALL" in txt, errs)
            check("%s: %s card says the nerve did not exist on this page before Q307" % (T, side.upper()),
                  "DID NOT EXIST ON THIS PAGE BEFORE Q307" in txt, errs)
        Q4.close_card(pg, phone)
    R["card_chars"] = seen
    check("%s: the nerve's card opens on BOTH sides, which is the whole point of the round" % T,
          seen.get("l", 0) > 400 and seen.get("r", 0) > 400, errs)


def section_b(pg, T, R, errs, key, lacn):
    """the position measured in the browser, off the page's own buffers."""
    for side in ("l", "r"):
        got = pg.evaluate(POS_JS, side)
        R.setdefault("measured", {})[side] = got
        if not check("%s: the %s nerve and its own radius / ulna / humerus are all readable in the page"
                     % (T, side.upper()), got.get("present") and got.get("frame"), errs):
            continue
        want = lacn["pages"][key][side]
        check("%s: %s it is RADIAL of the radius' own axis in the page (%.1f mm, the ulna's axis at %.1f mm)"
              % (T, side.upper(), got["radial_p50"], got["ulna_axis_p50"]),
              got["radial_p50"] > 0 and got["ulna_axis_p50"] < got["radial_p50"], errs)
        check("%s: %s it stops short of the wrist in the page too (t_max %.3f, so %.0f %% of the forearm short)"
              % (T, side.upper(), got["t_max"], 100 * (1 - got["t_max"])), 0.55 <= got["t_max"] <= 0.82, errs)
        check("%s: %s the position measured in the browser matches the data file (t_max %.3f vs %.3f)"
              % (T, side.upper(), got["t_max"], want["t_along_the_forearm"][1]),
              abs(got["t_max"] - want["t_along_the_forearm"][1]) <= 0.06, errs)
        if got.get("d_brachioradialis") is not None:
            check("%s: %s it lies against the brachioradialis in the page (%.2f mm)"
                  % (T, side.upper(), got["d_brachioradialis"]), got["d_brachioradialis"] <= 9.0, errs)


def section_c(pg, T, R, errs, key):
    """the repaired nerves, measured in the page."""
    PAIRS = {"own_m": [("tibial_n_r", "lateral_plantar_n_r", 300.0), ("tibial_n_l", "lateral_plantar_n_l", 300.0)],
             "own_f": [("tibial_n_l", "lateral_plantar_n_l", 250.0), ("tibial_n_r", "lateral_plantar_n_r", 250.0),
                       ("femoral_n_l", "saphenous_n_l", 250.0), ("femoral_n_r", "saphenous_n_r", 250.0)]}.get(key, [])
    if not PAIRS:
        return
    got = pg.evaluate(LEN_JS, [[a, b] for a, b, _ in PAIRS])
    R["repaired"] = got
    for a, b, minlen in PAIRS:
        g = got.get(a)
        if not check("%s: %s is readable in the page" % (T, a), g, errs):
            continue
        check("%s: %s is the FULL nerve, not a stub (%.1f mm along its own axis, needs >= %.0f)"
              % (T, a, g["axis_len"], minlen), g["axis_len"] >= minlen, errs)
        check("%s: %s meets its own branch %s (%.2f mm, Q298's measured contact threshold is 3.46 mm)"
              % (T, a, b, g["d_parent"]), g["d_parent"] is not None and g["d_parent"] <= 3.46, errs)


def section_d(pg, T, R, errs, key, boxes, rep):
    """every transferred structure is on the page, in the nerve layer, at the geometry the report records."""
    ids = pg.evaluate("() => window.NMSKClinicalTool.api.list().map(m => m.id)")
    want = rep[key]["ids"]
    missing = [i for i in want if i not in ids]
    check("%s: all %d structures this round carried are on the page (%d missing)" % (T, len(want), len(missing)),
          not missing, errs)
    bad = []
    for sid in want:
        g = pg.evaluate(Q4.BOX_JS, sid)
        if not g:
            bad.append((sid, "not readable")); continue
        if g["cat"] != "nerve":
            bad.append((sid, "layer " + str(g["cat"]))); continue
        b = boxes[sid]
        if max(abs(a - c) for a, c in zip(g["min"], b["min"]) ) > 0.2 or \
           max(abs(a - c) for a, c in zip(g["max"], b["max"]) ) > 0.2:
            bad.append((sid, "bbox"))
    R["bbox_bad"] = bad
    check("%s: every one of them is in the `nerve` layer with the bounding box the report records to 0.2 mm "
          "(%d bad)" % (T, len(bad)), not bad, errs)


def section_e(pg, T, R, errs, key):
    """Q303's on-screen missing-nerve list."""
    got = pg.evaluate("() => (window.NMSKNerves && NMSKNerves.absent) ? NMSKNerves.absent() : null")
    if got is None:
        check("%s: Q303's own `NMSKNerves.absent()` probe is readable" % T, False, errs); return
    miss = [str(x).lower() for x in (got.get("missing") or [])]
    R["q303_missing"] = miss
    still = [n for n in UPPER_NOT_MISSING if any(n in m for m in miss)]
    check("%s: Q303's on-screen list no longer reports the upper-limb nerves missing (%d of %d still named: %s)"
          % (T, len(still), len(UPPER_NOT_MISSING), still or "none"), not still, errs)


def run_page(d: Path, errs: list, only_phone=None):
    key = KEY[d.name]
    own = key in ("own_m", "own_f")
    html = V.html_of(d)
    srv, port = V.serve(d)
    lacn = json.loads((REPO / "data/derived/Q307_lacn_measurements.json").read_text())
    rep = json.loads((REPO / "data/derived/Q307_nerve_transfer.json").read_text())
    boxes = {}
    if own:
        import numpy as np
        z = np.load("/dev/shm/q307/nerves/%s_nerves.npz" % key)
        for sid in rep[key]["ids"]:
            V3 = z[sid + "__v"].astype(float)
            boxes[sid] = {"min": V3.min(0).round(3).tolist(), "max": V3.max(0).round(3).tolist()}
    out = REPORT.setdefault(key, {})
    try:
        with sync_playwright() as pl:
            sizes = [((1400, 900), False), ((390, 844), True)]
            if only_phone is not None:
                sizes = [sizes[1]] if only_phone else [sizes[0]]
            for (w, h), phone in sizes:
                # one browser per viewport, never one for the run: Q304 measured that a single Chromium process
                # across six passes over pages of 4.9-5.8 MB makes the later passes miss.
                b = pl.chromium.launch(args=V.LAUNCH_ARGS, executable_path="/opt/pw-browsers/chromium")
                T = "%s_%d" % (key, w)
                R = out.setdefault(str(w), {})
                del Q4.MISSED[:]
                ctx = b.new_context(viewport={"width": w, "height": h}, has_touch=phone, is_mobile=phone,
                                    device_scale_factor=1)
                pg = ctx.new_page(); perr = []
                pg.on("pageerror", lambda e: perr.append(str(e)))
                pg.route("**/*", V.route)
                pg.goto("http://127.0.0.1:%d/%s" % (port, html), wait_until="load", timeout=240000)
                Q4.ready(pg)
                print("\n--- %s ---" % T)
                section_a(pg, T, R, errs, phone, key, lacn)
                section_b(pg, T, R, errs, key, lacn)
                if own:
                    section_c(pg, T, R, errs, key)
                    section_d(pg, T, R, errs, key, boxes, rep)
                    section_e(pg, T, R, errs, key)
                check("%s: 0 page errors" % T, not perr, errs)
                if perr:
                    print("    page errors:", perr[:3])
                R["unreachable"] = list(Q4.MISSED)
                if Q4.MISSED:
                    print("    controls a finger could not reach:", Q4.MISSED)
                ctx.close(); b.close()
    finally:
        srv.terminate()


def main(argv):
    dirs, out, only_phone = [], None, None
    i = 0
    while i < len(argv):
        a = argv[i]
        if a == "--json":
            out = argv[i + 1]; i += 2; continue
        if a.startswith("--phone="):
            only_phone = a.split("=")[1] == "1"; i += 1; continue
        dirs.append(Path(a)); i += 1
    errs: list = []
    for d in dirs:
        run_page(d, errs, only_phone)
    print("\n==== Q307 verify: %d OK, %d FAIL" % (OKN[0], len(errs)))
    for e in errs:
        print("  FAIL", e)
    if out:
        Path(out).write_text(json.dumps({"ok": OKN[0], "fail": errs, "pages": REPORT}, indent=1, default=float),
                             encoding="utf-8")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
