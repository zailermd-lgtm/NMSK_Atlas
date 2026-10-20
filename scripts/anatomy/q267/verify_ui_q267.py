#!/usr/bin/env python3
"""Q267: real headless-Chromium verification of the 7 UI/workflow items (clinical safety-threshold items 1-3 held,
harness-blocked, not attempted this round). Real Playwright clicks/drags against a locally-served, template-only
rebuilt page -- not just "the code looks right". Run at both desktop and the project's own 390x844 mobile convention.

    python3 scripts/anatomy/q267/verify_ui_q267.py OWN_DIR ZAN_DIR

OWN_DIR / ZAN_DIR: a rebuilt page directory (one own-engine page, one Z-engine page), each already carrying the
current clinical_*.js (clinical/stage_clinical_files.py --ultrasound re-run against this round's changes) and the
regenerated plexus_groups.json sidecar (scripts/anatomy/q256/build_plexus_sidecar.py, Q267-extended)."""
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
    cands = sorted(Path(d).glob("atlas_viewer*.html"))
    return cands[0].name if cands else "index.html"


def check(pg, label, cond, errs):
    ok = bool(cond)
    print(("  OK  " if ok else "  FAIL") + " " + label)
    if not ok:
        errs.append(label)
    return ok


def run_page(pl, page_dir, kind, viewport, errs_out):
    page_dir = Path(page_dir)
    html = html_of(page_dir)
    srv, port = serve(page_dir)
    try:
        b = pl.chromium.launch(args=LAUNCH_ARGS, executable_path="/opt/pw-browsers/chromium")
        ctx = b.new_context(viewport=viewport, has_touch=viewport["width"] < 760, is_mobile=viewport["width"] < 760)
        pg = ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.route("**/*", route)
        print(f"=== {kind} {page_dir.name} @ {viewport['width']}x{viewport['height']} ===")
        pg.goto(f"http://127.0.0.1:{port}/{html}", wait_until="load", timeout=60000)
        pg.wait_for_function("window.NMSKUltrasound && window.NMSKImaging && window.NMSKReference", timeout=30000)
        pg.evaluate("() => window.NMSKUltrasound.ready()")
        pg.evaluate("() => window.NMSKImaging.ready()")

        # ---- open ultrasound (real click on its toolbar button) ----
        us_btn = pg.locator("#t-ultrasound")
        us_btn.click()
        pg.wait_for_timeout(300)
        check(pg, "ultrasound panel opened (real click)", pg.evaluate("() => window.NMSKUltrasound.isOpen()"), errs_out)

        # ---- item 4: US diagnostic preset, real click on a category button, real wizard interaction ----
        pre_state = pg.evaluate("() => window.NMSKUltrasound.state()")
        tear_btn = pg.get_by_role("button", name="קרע שריר", exact=True)
        has_tear_btn = tear_btn.count() > 0
        check(pg, "preset category button present in the DOM (real markup, not just state)", has_tear_btn, errs_out)
        if has_tear_btn:
            tear_btn.first.click()
            pg.wait_for_timeout(200)
            st = pg.evaluate("() => window.NMSKUltrasound.state()")
            check(pg, "preset applied: depth/DR/freq changed, CINE mode continuous, Controls collapsed",
                  st["depthCm"] == 4 and st["dr"] == 55 and st["freq"] == 12 and st["cineMode"] == "continuous" and "ctl-off" in pg.evaluate("() => document.getElementById('us-root').className"),
                  errs_out)
            # item 10: the wizard strip, a real question with >=2 candidates -- type to filter, click a real result row
            wiz_hidden = pg.evaluate("() => document.querySelector('.us-wizard').hidden")
            check(pg, "wizard shown (a real disambiguating question, not skipped)", wiz_hidden is False, errs_out)
            opts = pg.evaluate("() => window.NMSKUltrasound.wizardOptions()")
            check(pg, "wizard offers >=2 real candidates from this page's own structure list", len(opts) >= 2, errs_out)
            if opts:
                pg.locator(".us-wizard input").fill(opts[0]["name"].split("_")[0][:3])
                pg.wait_for_timeout(150)
                rows = pg.locator(".us-wizard .wiz-res button")
                if rows.count() > 0:
                    rows.first.click()
                    pg.wait_for_timeout(600)
                    st2 = pg.evaluate("() => window.NMSKUltrasound.state()")
                    check(pg, "picking a wizard row placed the probe (P changed) and started CINE", st2["P"] != pre_state.get("P") and st2["cine"] is True, errs_out)
                    check(pg, "wizard dismissed itself after a real pick", pg.evaluate("() => document.querySelector('.us-wizard').hidden") is True, errs_out)

        # ---- item 5: A/B compare, real click, both slots render ----
        pg.evaluate("() => window.NMSKUltrasound.set({cine:false})")
        ctlbtn = pg.locator("#us-ctlbtn")                                 # the preset step above collapsed Controls; reopen it (same existing toggle) so its own buttons are clickable again
        if ctlbtn.get_attribute("aria-pressed") == "false":
            ctlbtn.click(); pg.wait_for_timeout(150)
        ab_btn = pg.get_by_role("button", name="A / B compare")
        ab_btn.click()
        pg.wait_for_timeout(400)
        abst = pg.evaluate("() => window.NMSKUltrasound.state()")
        check(pg, "A/B toggled on by a real click", abst["ab"] is True, errs_out)
        check(pg, "A/B: slot B got its own placement (mirrored, not left null)", abst["P2"] is not None, errs_out)
        views2 = pg.evaluate("() => window.NMSKUltrasound.views().length")
        check(pg, "A/B: exactly 2 views rendered", views2 == 2, errs_out)
        pg.wait_for_timeout(300)
        frames2 = pg.evaluate("() => window.NMSKUltrasound.frames().map(f => !!(f && f.sim))")
        check(pg, "A/B: both slots actually simulated an image", frames2 == [True, True], errs_out)
        mirror_btn = pg.get_by_role("button", name="mirror B ← A")
        mirror_btn.click()
        pg.wait_for_timeout(300)
        check(pg, "mirror B<-A real click re-seated slot B", pg.evaluate("() => window.NMSKUltrasound.state().P2") is not None, errs_out)
        pg.evaluate("() => window.NMSKUltrasound.setAb(false)")

        # ---- item 6: thickness readout, opt-in off by default, real hover ----
        st0 = pg.evaluate("() => window.NMSKUltrasound.state()")
        check(pg, "thickness readout OFF by default", st0["thickness"] is False, errs_out)
        ctl = pg.locator("#us-ctlbtn")                                   # the preset step above collapsed Controls; reopen it first (existing mechanism)
        if ctl.get_attribute("aria-pressed") == "false":
            ctl.click(); pg.wait_for_timeout(150)
        img_tab = pg.locator('.sectabs [data-sec="image"]')              # a narrow panel shows one tab at a time; the thickness toggle lives in "Image"
        if img_tab.count() and img_tab.is_visible():
            img_tab.click(); pg.wait_for_timeout(100)
        thick_btn = pg.locator("#us-root .us-ctl button", has_text="tissue thickness")
        thick_btn.first.click()
        pg.wait_for_timeout(200)
        check(pg, "thickness toggle is now on (real click)", pg.evaluate("() => window.NMSKUltrasound.state().thickness") is True, errs_out)
        view0 = pg.locator(".us-view").first
        box = view0.bounding_box()
        if box:
            pg.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
            pg.wait_for_timeout(200)
            thick_text = pg.evaluate("() => document.querySelector('.us-thick') ? document.querySelector('.us-thick').textContent : ''")
            check(pg, "live thickness readout text appeared on real hover", "Tissue thickness at cursor" in thick_text, errs_out)
        pg.evaluate("() => window.NMSKUltrasound.close()")

        # ---- item 7: reference picture-in-picture panel ----
        ref_btn = pg.locator("#t-reference")
        check(pg, "reference-panel toolbar button present (collapsed by default)", ref_btn.count() > 0 and pg.evaluate("() => window.NMSKReference.isOpen()") is False, errs_out)
        ref_btn.click()
        pg.wait_for_timeout(200)
        check(pg, "reference panel opened by a real click", pg.evaluate("() => window.NMSKReference.isOpen()"), errs_out)
        test_png = REPO / "scripts/anatomy/q267/_fixture_1x1.png"
        pg.set_input_files("#ref-root input[type=file]", str(test_png))
        pg.wait_for_timeout(300)
        rst = pg.evaluate("() => window.NMSKReference.state()")
        check(pg, "a real local file was loaded (File API, no network request for its content)", rst["loaded"] is True and rst["kind"] == "image", errs_out)
        zoom_slider = pg.locator("#ref-root input[type=range]").first
        zoom_slider.evaluate("el => { el.value = '2.5'; el.dispatchEvent(new Event('input', {bubbles:true})); }")
        pg.wait_for_timeout(100)
        check(pg, "zoom slider (real control) changed state", pg.evaluate("() => window.NMSKReference.state().zoom") == 2.5, errs_out)
        min_btn = pg.locator("#ref-min")
        min_btn.click()
        pg.wait_for_timeout(100)
        check(pg, "compact-panel idiom: real click collapses the reference panel to its title bar", "ref-collapsed" in pg.evaluate("() => document.getElementById('ref-root').className"), errs_out)
        min_btn.click()
        ref_btn.click()  # close again

        # ---- item 9: layout toggle (auto Model-only with nothing armed) ----
        pg.wait_for_timeout(700)
        lay0 = pg.evaluate("() => window.__panelLayoutState()")
        check(pg, "layout auto-returned to Model-only once no clinical tool is armed", lay0["state"] == "model", errs_out)
        lay_btn = pg.locator("#t-lay3")
        lay_btn.click()
        pg.wait_for_timeout(100)
        lay1 = pg.evaluate("() => window.__panelLayoutState()")
        check(pg, "one real click cycles the layout (model -> split)", lay1["state"] == "split", errs_out)

        # ---- item 8: injury severity + reference card, real click on the structure list then Mark then a severity button ----
        if viewport["width"] < 760:                                      # on this project's own mobile layout the structure list is a bottom sheet, opened by its own existing tab/button
            mobile_opener = pg.locator("#m-list" if kind == "own" else "#btn-panel")
            if mobile_opener.count():
                mobile_opener.click(); pg.wait_for_timeout(200)
        first_row = pg.locator(".row, .item").first
        if first_row.count():
            first_row.click()
            pg.wait_for_timeout(200)
            mark_btn = pg.locator("#a-mark")
            if mark_btn.count():
                mark_btn.click()
                pg.wait_for_timeout(150)
                card_sel = "#i-injury" if kind == "own" else "#inj-card"
                sev_btns = pg.locator(f"{card_sel} [data-sev]")
                check(pg, "marking a structure (existing Mark button) revealed the severity row", sev_btns.count() == 3, errs_out)
                if sev_btns.count():
                    sev_btns.nth(1).click()  # moderate
                    pg.wait_for_timeout(150)
                    pressed = pg.evaluate(f"() => document.querySelector('{card_sel} [data-sev=\"moderate\"]').getAttribute('aria-pressed')")
                    check(pg, "real click set severity to moderate", pressed == "true", errs_out)
                    card_text = pg.evaluate(f"() => document.querySelector('{card_sel} .i-inj-card, {card_sel} .inj-body') ? document.querySelector('{card_sel} .i-inj-card, {card_sel} .inj-body').textContent : ''")
                    check(pg, "reference card labelled, not worded as a diagnosis", "not a diagnosis" in card_text, errs_out)
                mark_btn.click()  # unmark again
                pg.wait_for_timeout(150)
                check(pg, "unmarking hides the severity/reference card again", pg.evaluate(f"() => document.querySelector('{card_sel}').innerHTML.trim()") == "", errs_out)

        check(pg, "0 page errors throughout this whole real-interaction pass", len(errs) == 0, errs_out)
        for e in errs[:10]:
            print("    PAGEERR:", e[:300])
        b.close()
    finally:
        srv.terminate()


def main(argv):
    if len(argv) != 2:
        print(__doc__); return 2
    own_dir, zan_dir = argv
    fixture = REPO / "scripts/anatomy/q267/_fixture_1x1.png"
    if not fixture.exists():
        import base64
        fixture.write_bytes(base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="))
    errs = []
    with sync_playwright() as pl:
        run_page(pl, own_dir, "own", {"width": 1400, "height": 900}, errs)
        run_page(pl, own_dir, "own", {"width": 390, "height": 844}, errs)
        run_page(pl, zan_dir, "zan", {"width": 1400, "height": 900}, errs)
        run_page(pl, zan_dir, "zan", {"width": 390, "height": 844}, errs)
    print()
    print("TOTAL FAILED CHECKS:", len(errs))
    for e in errs:
        print("  -", e)
    return 0 if not errs else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
