#!/usr/bin/env python3
"""Q258: verify the brachial plexus actually RENDERS in the CT/MRI and ultrasound simulators at the interscalene location
(real headless-Chromium output, not code reasoning): window.NMSKImaging.sliceNow() for per-pixel tissue-class ground
truth + a real screenshot of the imaging panel; window.NMSKUltrasound.placeRay()/overlayItems() for the structures
actually under the probe + a real screenshot of the ultrasound panel.

    python3 scripts/anatomy/q258/verify_imaging.py PAGE_DIR HTML X Y Z OUT_PREFIX
"""
from __future__ import annotations
import socket, subprocess, sys, time, json
from pathlib import Path
from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[3]
THREE = "/tmp/three_x/package/build/three.min.js"


def main():
    page_dir, html, x, y, z, prefix = sys.argv[1:7]
    P = [float(x), float(y), float(z)]
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "-d", str(REPO / page_dir)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    out = {}
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
            pg.goto(f"http://127.0.0.1:{port}/{html}", wait_until="load")
            pg.wait_for_function("window.NMSKImaging && window.NMSKUltrasound", timeout=60000)

            def log(m):
                print(m, file=sys.stderr, flush=True)

            # ---- CT ----
            log("ct: ready")
            pg.evaluate("() => window.NMSKImaging.ready()")
            log("ct: open")
            pg.evaluate("() => window.NMSKImaging.open()")
            log("ct: set")
            pg.evaluate("(p) => window.NMSKImaging.set({modality:'ct', P:p})", P)
            log("ct: idle")
            pg.evaluate("() => window.NMSKImaging.idle()")
            log("ct: slicenow")
            time.sleep(1)
            # axial plane (normal = +Y, the standard view for the interscalene triangle clinically: fixed neck
            # level, X/Z cross-section) -- a coronal attempt at this same point on an own page first showed 100%
            # bone_cortical (caught before shipping: a direct bone-distance check confirmed the point itself is
            # 17 mm clear of every nearby bone, so a wide coronal window through the dense shoulder girdle at this
            # subject's own z-depth, not the point, was responsible)
            sl = pg.evaluate("""(p) => window.NMSKImaging.sliceNow({O:p, n:[0,1,0], W:160, H:160, fov:110}).then(r => {
                var lab = r.labels[0], cnt = {};
                for (var i=0;i<lab.length;i++){ var k = window.NMSKImaging.classOf(lab[i]); cnt[k]=(cnt[k]||0)+1; }
                return cnt;
            })""", P)
            out["ct_slice_classes"] = sl
            try:
                pg.locator("#img-root").screenshot(path=f"{prefix}_ct.png")
            except Exception as e:
                out["ct_shot_err"] = str(e)

            # ---- MRI ----
            pg.evaluate("(p) => window.NMSKImaging.set({modality:'mri', seq:'t1_se', P:p})", P)
            pg.evaluate("() => window.NMSKImaging.idle()")
            time.sleep(1)
            try:
                pg.locator("#img-root").screenshot(path=f"{prefix}_mri.png")
            except Exception as e:
                out["mri_shot_err"] = str(e)
            pg.evaluate("() => window.NMSKImaging.close()")
            ctx.close()

            # ---- Ultrasound (fresh page: the imaging panel being open interfered with the ultrasound companion's
            # own skin raycast in an earlier attempt, caught by a standalone repro before shipping this script) ----
            ctx = b.new_context(viewport=dict(width=1200, height=900))
            pg = ctx.new_page()
            pg.on("pageerror", lambda e: errs.append(str(e)))
            pg.route("**/*", route)
            pg.goto(f"http://127.0.0.1:{port}/{html}", wait_until="load")
            pg.wait_for_function("window.NMSKUltrasound", timeout=60000)
            pg.evaluate("() => window.NMSKUltrasound.ready()")
            pg.evaluate("() => window.NMSKUltrasound.open()")
            # straight lateral-to-medial approach at the SAME height/depth as P: start 120 mm further out on the
            # midline-side the point is already on, ray pointing straight back toward it (0 vertical/AP offset) --
            # a direct perpendicular probe placement at the interscalene point itself, not an oblique guess.
            sgn = -1.0 if P[0] < 0 else 1.0
            frm = [P[0] - sgn * 120.0, P[1], P[2]]
            dirn = [sgn * 120.0, 0.0, 0.0]
            hit = pg.evaluate("(a) => window.NMSKUltrasound.placeRay(a[0], a[1])", [frm, dirn])
            out["us_place_hit"] = hit
            if hit:
                pg.evaluate("() => window.NMSKUltrasound.idle()")
                time.sleep(1)
                ov = pg.evaluate("() => window.NMSKUltrasound.overlayItems()")
                out["us_overlay_items"] = ov
                try:
                    pg.locator("#us-root").screenshot(path=f"{prefix}_us.png", timeout=15000)
                except Exception as e:
                    out["us_shot_err"] = str(e)
            else:
                out["us_overlay_items"] = None

            out["page_errors"] = errs[:5]
            b.close()
    finally:
        srv.terminate()
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
