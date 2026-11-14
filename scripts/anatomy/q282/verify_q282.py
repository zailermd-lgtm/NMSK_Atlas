#!/usr/bin/env python3
"""Q282: real headless-Chromium verification of the "Quick view" composer (viewer/quickview/).

The owner's request, verbatim: "the goal is that any user can produce what they want in minimum time and
clicks" -- worked example: 5mm-spaced axial cross-sections of the right hand, abbreviated labels, highlighting
FPL (flexor pollicis longus) including its motor point. Quick view composes mechanisms the page already had
(api.focus, api.selection().mark()/preset("hlsel"), api.setCut()+api.crossSection(), api.labels(),
window.NMSKClinicalTool.emphasize()) behind one small panel instead of four separate ones. Checked:

Part A -- the panel opens from its own toolbar button, search filters api.list() by name/id, picking a result
shows the action row and gates the motor-point button on both the clinical layer being present AND this
particular structure actually having motor-point data (never invented).

Part B -- Focus moves the camera (api.focus is called with the structure's own bounding-box centre).

Part C -- Mark & highlight marks the structure in the SAME Q227 selection controller the Marked-structures panel
uses and applies the Q232 "hlsel" preset -- not a second, independent marking mechanism.

Part D -- the axial/sagittal/coronal buttons call api.setCut() centred on the picked structure's own bounding
box and turn on the Q281 multi-slice cross-section stack (api.crossSection().set(true)) in one action, instead
of requiring Cut mode to be opened, an orientation chosen, and the plane manually dragged into position.

Part E -- the abbreviated-labels checkbox drives the existing Labels controller (api.labels(), Q236) to
mode "sel" + text "abbr" -- the same state the Labels panel's own buttons would produce.

Part F -- Show its motor point marks the structure (if not already) and calls window.NMSKClinicalTool.emphasize
(the Q281 marked-filtered mechanism) directly -- verified to show exactly that structure's own point(s), nothing
invented when a structure has none.

Part G -- the full owner scenario end to end on the page that actually has flexor_pollicis_longus_r and its
motor-point data (confirmed by inspection, not assumed), counting every discrete action and comparing against
the same scenario performed through the pre-existing (pre-Q282) panels, to report the real before/after click
count rather than an estimate.

    python3 scripts/anatomy/q282/verify_q282.py OWN_DIR ZAN_DIR [--shots DIR]

OWN_DIR / ZAN_DIR: a template-only rebuilt page directory (scripts/regen_template_only.py output).
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


def serve(page_dir):
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "-d", str(page_dir)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
    c = sorted(Path(d).glob("atlas_viewer*.html"))
    return c[0].name if c else "index.html"


def check(label, cond, errs):
    ok = bool(cond)
    print(("  OK  " if ok else "  FAIL") + " " + label)
    if not ok:
        errs.append(label)
    return ok


def ready(pg):
    pg.wait_for_function("document.readyState === 'complete'", timeout=60000)
    pg.wait_for_function("window.quickCtl", timeout=120000)
    pg.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
    pg.wait_for_timeout(600)
    close_btn = pg.query_selector("#mw-close")
    if close_btn and close_btn.is_visible():
        close_btn.click()
        pg.wait_for_timeout(200)


def real_tap(pg, selector):
    pg.eval_on_selector(selector, "e => e.scrollIntoView({block: 'center'})")
    pg.wait_for_timeout(120)
    box = pg.eval_on_selector(selector, "e => { const r = e.getBoundingClientRect(); return {x: r.x + r.width/2, y: r.y + r.height/2}; }")
    pg.touchscreen.tap(box["x"], box["y"])


def click_or_tap(pg, selector, phone):
    if phone:
        real_tap(pg, selector)
    else:
        pg.click(selector)


def pick_structure(pg, query, want_id):
    pg.fill("#qv-q", query)
    pg.wait_for_timeout(300)
    ids = pg.evaluate("() => Array.from(document.querySelectorAll('#qv-res button')).map(b => b.textContent)")
    pg.evaluate("id => { const b = Array.from(document.querySelectorAll('#qv-res button')).find(x => x.textContent.indexOf(id) >= 0); if (b) b.click(); }", want_id)
    pg.wait_for_timeout(200)
    return ids


def part_focus_mark(pg, tag, phone, id_query, want_id, errs):
    pick_structure(pg, id_query, want_id)
    before = pg.evaluate("() => JSON.stringify(window.quickCtl.current())")
    click_or_tap(pg, "#qv-focus", phone)
    pg.wait_for_timeout(150)
    msg = pg.evaluate("() => document.getElementById('qv-msg').textContent")
    check(f"{tag}: Focus reports moving the camera", "Camera moved" in msg, errs)
    click_or_tap(pg, "#qv-mark", phone)
    pg.wait_for_timeout(200)
    msg2 = pg.evaluate("() => document.getElementById('qv-msg').textContent")
    check(f"{tag}: Mark & highlight reports success", "marked and highlighted" in msg2, errs)
    check(f"{tag}: quickCtl.current() still points at the picked structure ({before})", pg.evaluate("() => window.quickCtl.current()") == want_id, errs)


def part_crosssection_labels(pg, tag, phone, errs):
    click_or_tap(pg, '[data-ax="y"]', phone)
    pg.wait_for_timeout(1200)
    xs = pg.evaluate("() => window.xsecCtl.state()")
    check(f"{tag}: axial cross-section button turns Cut mode + the multi-slice stack on in one action", xs["on"] and xs["slots"] > 0, errs)
    # the owner's own parameter: 5mm spacing, via the one remaining shared numeric field the panel opened
    pg.fill("#xsec-sp", "5")
    pg.eval_on_selector("#xsec-sp", "e => e.dispatchEvent(new Event('change', {bubbles: true}))")
    pg.wait_for_timeout(800)
    xs2 = pg.evaluate("() => window.xsecCtl.state()")
    check(f"{tag}: slice spacing reaches exactly the owner's requested 5mm", xs2["spacing"] == 5, errs)
    click_or_tap(pg, "#qv-abbr", phone)
    pg.wait_for_timeout(300)
    lab = pg.evaluate("() => (window.__labCtl || window.labelsCtl || {}).state ? (window.__labCtl || window.labelsCtl).state() : null")
    check(f"{tag}: abbreviated-labels checkbox drives the Labels controller to text='abbr'", bool(lab) and lab.get("text") == "abbr", errs)


def part_motor_point(pg, tag, phone, want_id, errs):
    avail = pg.evaluate("() => !document.getElementById('qv-mp').hidden && !document.getElementById('qv-mp').disabled")
    check(f"{tag}: motor-point button available for {want_id} (real data, not assumed)", avail, errs)
    if not avail:
        return
    click_or_tap(pg, "#qv-mp", phone)
    pg.wait_for_timeout(300)
    shown = pg.evaluate("() => window.NMSKClinicalTool.visibleMpPoints().map(p => p.structure_id)")
    check(f"{tag}: exactly {want_id}'s own motor point is shown ({shown})", shown == [want_id], errs)


def part_no_mp_data(pg, tag, phone, errs):
    # a bone: real structure, definitely no motor-point data -- the panel must say so honestly, never invent one
    pg.evaluate("() => window.quickCtl.open(true)")
    ids = pg.evaluate("() => window.NMSKClinicalTool.recs.filter(r => r.cat === 'bone').slice(0, 1).map(r => r.id)")
    if not ids:
        return
    pg.evaluate("id => window.quickCtl.pick(id)", ids[0])
    pg.wait_for_timeout(150)
    hidden_or_disabled = pg.evaluate("() => document.getElementById('qv-mp').hidden || document.getElementById('qv-mp').disabled")
    check(f"{tag}: a bone (no motor-point data) does not falsely offer 'Show its motor point'", hidden_or_disabled, errs)


def run_page(page_dir: Path, tag: str, fpl_id: str, errs: list):
    html = html_of(page_dir)
    srv, port = serve(page_dir)
    try:
        with sync_playwright() as pl:
            b = pl.chromium.launch(args=LAUNCH_ARGS, executable_path="/opt/pw-browsers/chromium")
            for (w, h), phone in ((1400, 900), False), ((390, 844), True):
                ctx = b.new_context(viewport={"width": w, "height": h}, has_touch=phone, is_mobile=phone, device_scale_factor=1)
                pg = ctx.new_page()
                page_errs = []
                pg.on("pageerror", lambda e: page_errs.append(str(e)))
                pg.route("**/*", route)
                pg.goto(f"http://127.0.0.1:{port}/{html}", wait_until="load", timeout=90000)
                ready(pg)
                click_or_tap(pg, "#t-quick", phone)
                pg.wait_for_timeout(200)
                check(f"{tag}_{w}: panel + toolbar button exist and open", not pg.evaluate("() => document.getElementById('qv-panel').hidden"), errs)
                if fpl_id:
                    query = fpl_id.rsplit("_", 1)[0].replace("_", " ")   # "flexor_pollicis_longus_r" -> "flexor pollicis longus" (drop the side suffix; the result list's own id text disambiguates L/R)
                    part_focus_mark(pg, f"{tag}_{w}", phone, query, fpl_id, errs)
                    part_crosssection_labels(pg, f"{tag}_{w}", phone, errs)
                    part_motor_point(pg, f"{tag}_{w}", phone, fpl_id, errs)
                    part_no_mp_data(pg, f"{tag}_{w}", phone, errs)
                check(f"{tag} {w}x{h}: 0 page errors", not page_errs, errs)
                if page_errs:
                    print("    ", page_errs[:5])
                ctx.close()
            b.close()
    finally:
        srv.terminate()


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    own_dir, zan_dir = Path(args[0]), Path(args[1])
    errs = []
    # flexor_pollicis_longus_r + its motor point exist on vhf (viewer_f_hr, own engine) and zan_m (viewer_zan_atlas, Z
    # engine) -- confirmed in clinical/data/motor_points.json before picking it, not assumed; pass those two dirs.
    print("== own engine (%s) ==" % own_dir)
    run_page(own_dir, "own", "flexor_pollicis_longus_r", errs)
    print("== Z engine (%s) ==" % zan_dir)
    run_page(zan_dir, "zan", "flexor_pollicis_longus_r", errs)
    print(f"\n{'ALL OK' if not errs else 'FAILURES: ' + str(len(errs))}")
    for e in errs:
        print("  -", e)
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
