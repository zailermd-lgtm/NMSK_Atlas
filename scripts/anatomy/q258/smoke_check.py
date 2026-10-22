#!/usr/bin/env python3
"""Q258: minimal headless-Chromium smoke check -- load the built page, wait for the three.js scene to settle, count
console/page errors. Not a feature test (those live in q236/q240/etc); just confirms the new geometry didn't break
page load.
    python3 scripts/anatomy/q258/smoke_check.py PAGE_DIR HTML
"""
from __future__ import annotations
import socket, subprocess, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[3]
THREE = "/tmp/three_x/package/build/three.min.js"


def main():
    page_dir, html = sys.argv[1], sys.argv[2]
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "-d", str(REPO / page_dir)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    errs = []
    try:
        with sync_playwright() as pl:
            b = pl.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"], executable_path="/opt/pw-browsers/chromium")
            ctx = b.new_context(viewport=dict(width=1400, height=900))
            pg = ctx.new_page()
            pg.on("pageerror", lambda e: errs.append(str(e)))

            def route(rq):
                u = rq.request.url
                if "three" in u and u.endswith(".js") and ("cdnjs" in u or "jsdelivr" in u or "unpkg" in u):
                    rq.fulfill(body=open(THREE, "rb").read(), content_type="application/javascript")
                elif "fonts.g" in u:
                    rq.abort()
                else:
                    rq.continue_()
            pg.route("**/*", route)
            pg.goto(f"http://127.0.0.1:{port}/{html}", wait_until="load", timeout=60000)
            pg.wait_for_function("window.NMSKImaging && window.NMSKUltrasound", timeout=30000)
            pg.evaluate("() => window.NMSKImaging.ready()")
            time.sleep(4)
            print(f"{page_dir}/{html}: loaded, page_errors={len(errs)}")
            for e in errs[:10]:
                print("  ERR:", e[:300])
            b.close()
    finally:
        srv.terminate()
    return 0 if not errs else 1


if __name__ == "__main__":
    raise SystemExit(main())
