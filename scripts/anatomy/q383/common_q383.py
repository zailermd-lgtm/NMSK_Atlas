"""Q383 -- helpers shared by the three verifiers of the scan tool round (drag, menu, image)."""
from __future__ import annotations

import socket
import subprocess
import sys
import time
from pathlib import Path

ARGS = ["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]
U = "window.NMSKUltrasound"


def serve(d: Path):
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close()
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(p), "--bind", "127.0.0.1", "-d", str(d)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    return srv, p


class Checks:
    def __init__(self):
        self.errs: list[str] = []
        self.n = 0

    def __call__(self, label, cond):
        ok = bool(cond)
        self.n += 1
        print(("  OK   " if ok else "  FAIL ") + label)
        if not ok:
            self.errs.append(label)
        return ok


def open_page(pl, d: Path, W: int, H: int, page_errors: list):
    """-> (server, browser, page) on the page's index.html, mode wall dismissed, anatomy screen."""
    phone = W <= 500
    srv, port = serve(d)
    b = pl.chromium.launch(args=ARGS, executable_path="/opt/pw-browsers/chromium")
    ctx = b.new_context(viewport={"width": W, "height": H}, has_touch=phone, is_mobile=phone, device_scale_factor=1)
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: page_errors.append(str(e)))
    pg.route("**/*", lambda rq: rq.abort() if "fonts.g" in rq.request.url else rq.continue_())
    pg.goto(f"http://127.0.0.1:{port}/index.html", wait_until="load", timeout=180000)
    pg.wait_for_function("window.NMSKUltrasound && window.NMSKClinicalTool && window.NMSKModes && window.NMSKHistory && window.__poseApi && window.__poseApi.ready()", timeout=180000)
    pg.wait_for_timeout(2000)
    pg.evaluate("() => { const c = document.getElementById('mw-close'); if (c) c.click(); }")
    pg.wait_for_timeout(500)
    pg.evaluate("() => { if (window.NMSKModes.current && window.NMSKModes.current()) window.NMSKModes.exit(); }")
    pg.wait_for_timeout(600)
    return srv, b, pg


def idle(pg, extra=250):
    pg.evaluate(f"() => {U}.idle()")
    pg.wait_for_timeout(extra)


def enter_scan(pg):
    pg.evaluate("() => window.NMSKModes.enter('us')")
    pg.wait_for_timeout(1200)
    pg.evaluate(f"() => {U}.ready()")
    idle(pg, 600)


def dist(a, b):
    return sum((a[i] - b[i]) ** 2 for i in range(len(a))) ** 0.5
