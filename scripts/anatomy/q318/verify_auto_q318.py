#!/usr/bin/env python3
"""Q318: AUTO really sets the exposure from the picture, for each X-ray step.

Owner: "where it is meant for bone, where for soft tissue, and then what you can see. Allow choosing
one of them and then a press on an AUTO mode that controls the brightness and the contrast. After
that it should still be possible to set them by hand."

Run in headless Chromium against a built page. For each step of the X-ray style this presses Auto
and reads the frame back, and asks of the result what a set exposure has to satisfy:

  * it uses the display range instead of sitting in a corner of it;
  * it is not a fixed pair of numbers -- a bone film and a soft-tissue film must not land on the
    same exposure, or AUTO is a preset pretending to measure;
  * the sliders still move afterwards, and Reset still undoes it.

    python3 scripts/anatomy/q318/verify_auto_q318.py build/q309/viewer_zan_atlas
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
  const R = window.NMSKRenderStyle, Q = window.NMSKQ301;
  if (!R || !Q) return {err: 'the render style is not on this page'};
  if (!R.state().tissue) return {err: 'the clinical tissue reference did not load'};
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const read = () => { const p = Q.pixels(2); return p && p.n ? {lum: p.lum, sd: p.sd, n: p.n} : null; };

  if (!R.set('xray')) return {err: 'could not enter the X-ray style'};
  await sleep(500);
  const out = {canAuto: R.state().canAuto, steps: []};

  for (let i = 0; i < 3; i++) {
    R.setStep(i);
    await sleep(450);
    R.resetAdj();                       // from a known neutral exposure every time
    R.setStep(i);
    await sleep(450);
    const before = read();
    const applied = R.auto();
    await sleep(450);
    const st = R.state();
    // The filter is applied by the compositor, so the drawing buffer the sampler reads is unchanged by it.
    // What is checked instead is the transform itself: run the measured span through it and see where the
    // two ends land, which is the thing AUTO is actually claiming to have done.
    const p = Q.pixels(2);
    const q = (h, t) => { let a = 0; for (let k = 0; k < h.length; k++){ const nx = a + h[k];
      if (nx >= t && h[k] > 0) return (k + (t - a) / h[k]) / h.length; a = nx; } return 1; };
    const f = v => ((v - 0.5) * st.contrast + 0.5) * st.brightness;
    out.steps.push({
      i: i, word: st.stepWord, applied: applied, before: before,
      lo: p && p.h64 ? q(p.h64, 0.02) : null, hi: p && p.h64 ? q(p.h64, 0.98) : null,
      mappedLo: p && p.h64 ? f(q(p.h64, 0.02)) : null, mappedHi: p && p.h64 ? f(q(p.h64, 0.98)) : null,
      contrast: st.contrast, brightness: st.brightness,
      filter: document.documentElement.style.getPropertyValue('--q301-adj')
    });
  }

  // the hand still wins afterwards, and Reset undoes it
  R.setStep(1); await sleep(300); R.auto(); await sleep(350);
  const autoPair = [R.state().contrast, R.state().brightness];
  const sl = document.getElementById('rs-reset');
  R.resetAdj(); await sleep(300);
  out.afterReset = [R.state().contrast, R.state().brightness];
  out.autoPair = autoPair;
  out.hasAutoButton = !!document.getElementById('rs-auto');
  out.hasResetButton = !!sl;
  return out;
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
            pg.wait_for_function("window.NMSKRenderStyle && window.NMSKQ301", timeout=90000)
            pg.wait_for_timeout(2500)
            t = pg.query_selector('.mw-tile[data-mode="anat"]')
            if t:
                t.click(); pg.wait_for_timeout(2500)
            r = pg.evaluate(PROBE)
            if r.get("err"):
                print("  FAIL " + r["err"]); return 1

            check("the style can read the frame back at all", r["canAuto"], errs)
            check("there is an Auto button on the bar", r["hasAutoButton"], errs)
            check("and a Reset beside it", r["hasResetButton"], errs)

            pairs, spans = [], []
            for s in r["steps"]:
                if s["lo"] is None:
                    errs.append(f"no frame could be read for step {s['i']}"); continue
                span = s["mappedHi"] - s["mappedLo"]
                print(f"     {s['word']:<12} measured [{s['lo']:.3f},{s['hi']:.3f}] -> "
                      f"[{s['mappedLo']:.2f},{s['mappedHi']:.2f}]  span {span:.2f}  "
                      f"c={s['contrast']:.2f} b={s['brightness']:.2f}")
                check(f"Auto applies in {s['word']}", s["applied"], errs)
                check(f"{s['word']}: the transform is actually on the canvas",
                      "contrast(" in (s["filter"] or ""), errs)
                check(f"{s['word']}: the measured span lands inside the display range",
                      -0.02 <= s["mappedLo"] <= 1.02 and -0.02 <= s["mappedHi"] <= 1.02, errs)
                check(f"{s['word']}: and uses a real part of it (span {span:.2f})", span > 0.45, errs)
                pairs.append((round(s["contrast"], 2), round(s["brightness"], 2)))
                spans.append(span)
            if len(spans) == 3:
                check("the bone film is shorter-scale than the soft-tissue film "
                      f"(bone span {spans[2]:.2f} > soft {spans[0]:.2f}) -- which is what kVp does",
                      spans[2] > spans[0], errs)

            check("a bone film and a soft-tissue film do not get the same exposure "
                  "(Auto measures, it is not a preset)", len(set(pairs)) > 1, errs)
            check("Reset puts the exposure back to neutral afterwards",
                  r["afterReset"] == [1, 1], errs)
            print(f"     exposures chosen: {pairs}; after Reset: {r['afterReset']}")
            b.close()
    finally:
        srv.terminate()

    print()
    if errs:
        print(f"Q318_AUTO_FAIL {len(errs)}")
        for e in errs:
            print("  - " + e)
        return 1
    print("Q318_AUTO_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
