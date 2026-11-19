"""Q336: a test copy of a built page with the read-only hook (hook_q336.js); the page dir itself is never touched."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "scripts/anatomy/q319"))
import verify_search_q319 as V  # noqa: E402  serve / route / ARGS / THREE

ANCHOR = "      hidden:hidden.size, faded:faded.size, solo:soloLayer, side:sideFilter\n    }; };\n"


def test_copy(src: Path, dst: Path) -> Path:
    if dst.exists():
        shutil.rmtree(dst)
    dst.mkdir(parents=True)
    hook = (HERE / "hook_q336.js").read_text(encoding="utf-8")
    for f in Path(src).iterdir():
        if f.name.endswith((".q318", ".q333", ".q336")):
            continue
        if f.suffix == ".html":
            t = f.read_text(encoding="utf-8")
            assert t.count(ANCHOR) == 1, f"{f}: hook anchor not found exactly once"
            i = t.index(ANCHOR) + len(ANCHOR)
            (dst / f.name).write_text(t[:i] + hook + t[i:], encoding="utf-8")
        else:
            os.symlink(f.resolve(), dst / f.name)
    return dst


def open_page(pl, d: Path, w=1400, h=900, errs=None):
    srv, port = V.serve(d)
    b = pl.chromium.launch(args=V.ARGS, executable_path="/opt/pw-browsers/chromium")
    pg = b.new_page(viewport={"width": w, "height": h}, device_scale_factor=1)
    errs = V.ERRS if errs is None else errs
    pg.on("pageerror", lambda e: errs.append("page error: " + str(e)))
    pg.route("**/*", V.route)
    html = sorted(d.glob("atlas_viewer*.html"))[0]
    pg.goto(f"http://127.0.0.1:{port}/{html.name}", wait_until="load", timeout=120000)
    pg.wait_for_function("window.__q336 && window.NMSKSelectCtl", timeout=120000)
    try:
        pg.wait_for_selector('.mw-tile[data-mode="anat"]', timeout=120000)
        pg.evaluate("() => document.querySelector('.mw-tile[data-mode=\"anat\"]').click()")
        pg.wait_for_timeout(2500)
    except Exception:
        pass
    return srv, b, pg
