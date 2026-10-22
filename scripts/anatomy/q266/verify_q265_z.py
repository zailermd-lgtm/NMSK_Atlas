#!/usr/bin/env python3
"""Q266: the FULL real-render verification Q265 owed but could not deliver (disk pressure aborted it mid-run),
for every Q265-shipped new structure on the four Z pages (own pages use a direct-geometry check instead -- see
verify_q265_own.py -- because the own-page sliceNow() harness has a known, already-diagnosed-as-unfixable quirk,
see PROJECT_STATE.md Q258/Q260/Q263).

One browser launch per page (not per structure, to keep this affordable): loads the page once, then for EVERY
Q265-shipped item on that page calls window.NMSKImaging.sliceNow() at the item's own real midpoint (the mean of
its first/last waypoint -- a point guaranteed to be ON the shipped tube, not a guess) and records the per-pixel
tissue-class histogram (same method as every prior round's verify_imaging.py). A real screenshot of the CT panel
is taken once per page (not once per structure, to keep disk small) at the FIRST item's own point, as the same
kind of visual proof prior rounds shipped.

    python3 scripts/anatomy/q266/verify_q265_z.py PAGE_DIR HTML ITEMS_JSON OUT_JSON SHOT_PNG
      ITEMS_JSON: [{"id":..., "point":[x,y,z]}, ...]
"""
from __future__ import annotations
import json, socket, subprocess, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[3]
THREE = "/tmp/three_x/package/build/three.min.js"


def main():
    page_dir, html, items_json, out_json, shot_png = sys.argv[1:6]
    items = json.loads(Path(items_json).read_text())
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "-d", str(REPO / page_dir)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    out = {"page": page_dir, "results": [], "page_errors": []}
    try:
        with sync_playwright() as pl:
            b = pl.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"], executable_path="/opt/pw-browsers/chromium")

            def route(rq):
                u = rq.request.url
                if "three" in u and u.endswith(".js") and ("cdnjs" in u or "jsdelivr" in u or "unpkg" in u):
                    rq.fulfill(body=open(THREE, "rb").read(), content_type="application/javascript")
                elif "fonts.g" in u:
                    rq.abort()
                else:
                    rq.continue_()

            errs = []
            ctx = b.new_context(viewport=dict(width=1200, height=900))
            pg = ctx.new_page()
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.route("**/*", route)
            pg.goto(f"http://127.0.0.1:{port}/{html}", wait_until="load", timeout=60000)
            pg.wait_for_function("window.NMSKImaging && window.NMSKUltrasound", timeout=60000)

            def log(m):
                print(m, file=sys.stderr, flush=True)

            pg.evaluate("() => window.NMSKImaging.ready()")
            pg.evaluate("() => window.NMSKImaging.open()")

            pg.evaluate("(p) => window.NMSKImaging.set({modality:'ct', P:p})", items[0]["point"])
            pg.evaluate("() => window.NMSKImaging.idle()")
            for n, it in enumerate(items):
                t0 = time.time()
                P = it["point"]
                sl = pg.evaluate("""(p) => window.NMSKImaging.sliceNow({O:p, n:[0,1,0], W:64, H:64, fov:80}).then(r => {
                    var lab = r.labels[0], cnt = {};
                    for (var i=0;i<lab.length;i++){ var k = window.NMSKImaging.classOf(lab[i]); cnt[k]=(cnt[k]||0)+1; }
                    return cnt;
                })""", P)
                out["results"].append({"id": it["id"], "point": P, "ct_slice_classes": sl})
                Path(out_json).write_text(json.dumps(out, indent=1))
                log(f"  [{n+1}/{len(items)}] {it['id']}: {sl} ({time.time()-t0:.1f}s)")
                if n == 0:
                    try:
                        pg.locator("#img-root").screenshot(path=shot_png)
                    except Exception as e:  # noqa: BLE001
                        out["shot_err"] = str(e)
            pg.evaluate("() => window.NMSKImaging.close()")
            out["page_errors"] = errs[:10]
            ctx.close()
            b.close()
    finally:
        srv.terminate()
    Path(out_json).write_text(json.dumps(out, indent=1))
    print(json.dumps({"page": page_dir, "n": len(items), "page_errors": len(out["page_errors"])}))


if __name__ == "__main__":
    main()
