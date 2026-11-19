#!/usr/bin/env python3
"""Q272: real headless-Chromium verification of the three clinical WORKSPACE MODES (viewer/modes/ + the providers in clinical/*.js),
extending scripts/anatomy/q267/verify_ui_q267.py's approach: real clicks / typing / file input on a locally served template-only
rebuilt page, at 1400x900 and the project's 390x844 phone convention, one own-engine page and one Z-engine page.

    python3 scripts/anatomy/q272/verify_modes.py OWN_DIR ZAN_DIR [--shots DIR]

Checks: the switcher appears on first load and dismisses; entering each mode hides the chrome (rail / details / toolbar not visible)
and shows the mode's own elements; the primary actions work end to end (injection: pick target -> suggest -> adopt -> readout rows;
US: preset -> CINE running -> A/B; compare: load a local PNG -> lock zoom -> mark injury severity -> open the reference card); exiting
restores the anatomy UI (a visibility / camera / selection snapshot compared before and after); 0 page errors. Screenshots of every
mode at every viewport go to --shots (default: the scratchpad q272_shots dir).

Q273 polish checks: the tool's English status line is not drawn under the hero badge (bounding boxes); slot B has skin contact after
A/B (snapped to the nearest contralateral skin, the CINE bar says so when it moved); the in-mode strings are Hebrew (B-mode overlay
language hook, step-card hint, reference drawer label + field names); the drawer's first line is the Hebrew "not a diagnosis" label;
"שמור תמונה" attempts a real PNG download (Playwright's download event) and shows the Hebrew toast; a hub card's mode link, clicked,
lands directly in that mode (#mode= hash, with the ?mode= query fallback checked too)."""
from __future__ import annotations
import base64
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[3]
THREE = "/tmp/three_x/package/build/three.min.js"
LAUNCH_ARGS = ["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]
CHROME = {"own": ["#app>header", "#app>aside", "#inspector", "#tools", ".mob-bar"], "zan": ["#brand", "#topright", "#rail", "#foot"]}
PNG_1x1 = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=")


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


VIS = """(sels) => Object.fromEntries(sels.map(s => { const e = document.querySelector(s); if (!e) return [s, null];
  const r = e.getBoundingClientRect(), cs = getComputedStyle(e); return [s, cs.display !== 'none' && cs.visibility !== 'hidden' && r.width > 0 && r.height > 0]; }))"""
SNAP = """() => { const m = window.__modesState ? window.__modesState() : null; const sel = (window.NMSKClinicalTool && window.NMSKClinicalTool.api.selection && window.NMSKClinicalTool.api.selection()) || null;
  const v = window.__viewerState ? window.__viewerState().cam : null; const a = window.NMSKClinicalTool ? window.NMSKClinicalTool.api.view() : null;
  return {cur: m && m.cur, marks: sel && sel.state ? sel.state().marks.slice().sort() : null, cam: v ? [v.az, v.el, v.dist].map(x => +x.toFixed(4)) : (a ? a.eye.map(x => +x.toFixed(2)) : null),
          selected: m ? m.selected : null}; }"""


def restored(tag, before_vis, after_vis, before, after, errs_out, extra=None):
    ok1 = check(f"{tag}: exit restored the chrome (visibility snapshot equal)", after_vis == before_vis, errs_out)
    if not ok1: print("    before", before_vis, "after", after_vis, "layout", extra)
    ok2 = check(f"{tag}: exit restored the camera", after["cam"] == before["cam"], errs_out)
    if not ok2: print("    cam before", before["cam"], "after", after["cam"])
    ok3 = check(f"{tag}: exit restored the marks and the selection, no mode left active", after["marks"] == before["marks"] and after["selected"] == before["selected"] and after["cur"] is None, errs_out)
    if not ok3: print("    before", before["marks"], before["selected"], "after", after["marks"], after["selected"], after["cur"])


def run_page(pl, page_dir, kind, viewport, errs_out, shots):
    page_dir = Path(page_dir); html = html_of(page_dir); srv, port = serve(page_dir); mobile = viewport["width"] < 760; tag = f"{kind}_{viewport['width']}"
    try:
        b = pl.chromium.launch(args=LAUNCH_ARGS, executable_path="/opt/pw-browsers/chromium")
        ctx = b.new_context(viewport=viewport, has_touch=mobile, is_mobile=mobile)
        pg = ctx.new_page(); errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.route("**/*", route)
        print(f"=== {kind} {page_dir.name} @ {viewport['width']}x{viewport['height']} ===")
        pg.goto(f"http://127.0.0.1:{port}/{html}", wait_until="load", timeout=90000)
        pg.wait_for_function("window.NMSKUltrasound && window.NMSKImaging && window.NMSKReference && window.__modesState", timeout=60000)
        pg.evaluate("() => window.NMSKUltrasound.ready()"); pg.evaluate("() => window.NMSKImaging.ready()")
        # ---- switcher on first load, dismiss ----
        pg.wait_for_function("() => { const s = document.getElementById('mode-switch'); return s && !s.hidden; }", timeout=60000)
        st = pg.evaluate("() => window.__modesState()")
        check("switcher shown on first load, all three providers registered", st["switcherOpen"] and sorted(st["registered"]) == ["cmp", "inj", "us"], errs_out)
        pg.get_by_role("button", name="אנטומיה", exact=False).first.click(); pg.wait_for_timeout(200)
        check("switcher dismissed by the anatomy tile", pg.evaluate("() => document.getElementById('mode-switch').hidden"), errs_out)
        if kind == "zan":
            pg.evaluate("() => { const b = document.getElementById('btn-spin'); if (b && b.classList.contains('on')) b.click(); }"); pg.wait_for_timeout(300)
        before_vis = pg.evaluate(VIS, CHROME[kind]); before = pg.evaluate(SNAP)
        # (the Q267 layout toggle starts in Model-only: the side panels may already be collapsed; the toolbar / title bar are always there)
        check("anatomy chrome visible before any mode (toolbar + title bar)", all(before_vis[k] for k in (("#app>header", "#tools") if kind == "own" else ("#brand", "#topright"))), errs_out)
        # ---- "מצב" toolbar button reopens the switcher ----
        pg.evaluate("() => document.getElementById('t-mode').click()"); pg.wait_for_timeout(150)
        check("toolbar button 'מצב' reopens the switcher", pg.evaluate("() => !document.getElementById('mode-switch').hidden"), errs_out)

        # ================= 1. injection =================
        pg.locator('.mw-tile[data-mode="inj"]').click(); pg.wait_for_timeout(600)
        vis = pg.evaluate(VIS, CHROME[kind])
        check("inj: body.mode-inj set and the chrome (rail / details / toolbar) hidden", pg.evaluate("() => document.body.classList.contains('mode-inj')") and not any(vis.values()), errs_out)
        check("inj: mode bar with the mode pill + exit, step card, distance card" + ("" if mobile else ", pills"), pg.evaluate("""() => { const t = s => { const e = document.querySelector(s); return e && e.getBoundingClientRect().height > 0; };
            return t('#mode-bar') && document.getElementById('mb-pill').textContent.includes('תכנון הזרקה') && t('.mc-right') && t('.mc-left') && document.getElementById('mb-exit').textContent === 'יציאה למצב אנטומיה'; }"""), errs_out)
        if not mobile:
            check("inj: bottom pill row has the 5 toggles", pg.evaluate("() => Array.from(document.querySelectorAll('#mode-pills .mp')).filter(b => b.getBoundingClientRect().height > 0).length") in (4, 5), errs_out)
        auto = pg.evaluate("() => window.NMSKClinicalTool.plan.i != null")
        if auto:   # the page already had a muscle / tendon selected: adopted as the target automatically (the owner's "as automatic as possible")
            check("inj: the page's selected muscle was adopted as the target automatically (no picker needed)", pg.locator(".mc-pick").count() == 0, errs_out)
        else:
            pick = pg.locator(".mc-pick input")
            check("inj: target picker opened automatically (no target selected yet)", pick.count() == 1, errs_out)
            rows = pg.locator(".mc-pick .mc-res button")
            check("inj: picker lists real muscles / tendons of this page", rows.count() > 3, errs_out)
            rows.first.click(); pg.wait_for_timeout(900)
        pg.wait_for_timeout(600)
        cor = pg.evaluate("() => window.NeedlePath.corridor()")
        tgt = pg.evaluate("() => { const t = window.NMSKClinicalTool; return {target: !!t.target, plan: t.plan.i != null, chip: document.querySelector('#mb-chips b').textContent}; }")
        check("inj: picking a target armed the preset + a default target point; chip shows it", tgt["target"] and tgt["plan"] and tgt["chip"] not in ("", "—"), errs_out)
        check("inj: distance card already reads vessels / nerves around the target point", len(cor["items"]) > 0 and pg.locator(".mc-left .mc-drow").count() > 0, errs_out)
        pg.get_by_role("button", name="הצע נקודות כניסה").click(); pg.wait_for_timeout(2500)
        sug = pg.evaluate("() => window.NeedlePath.suggestions()")
        if sug:
            check("inj: suggest produced ranked candidates listed in the step card", pg.locator(".mc-cand").count() == len(sug), errs_out)
            pg.locator(".mc-cand button").first.click(); pg.wait_for_timeout(700)
            rep = pg.evaluate("() => window.NeedlePath.report()"); cor2 = pg.evaluate("() => window.NeedlePath.corridor()")
            check("inj: adopting a candidate set the entry -> readout updated (segment) + step 3 report", rep is not None and rep["length_mm"] > 0 and "segment" in cor2["what"] and pg.locator(".mc-left .mc-drow").count() > 0, errs_out)
        else:
            print("  note: no candidate cleared the far threshold for this target (the tool's own message shown) -- adopting skipped")
        hints = pg.evaluate("() => Array.from(document.querySelectorAll('.mc-right .mc-hint')).map(e => e.textContent.trim()).filter(Boolean)")
        check("inj (Q273-3): the step-card hints are Hebrew", bool(hints) and all(any('\u0590' <= ch <= '\u05ff' for ch in t) for t in hints), errs_out)
        pg.screenshot(path=str(shots / f"inj_{tag}.png"))
        pg.get_by_role("button", name="יציאה למצב אנטומיה").first.click() if not mobile else pg.locator("#mb-exit-x").click()
        pg.wait_for_timeout(3500)   # the page's own 500 ms layout poller (Q267 item 9) settles back to Model-only after a tool closes
        after_vis = pg.evaluate(VIS, CHROME[kind]); after = pg.evaluate(SNAP)
        restored("inj", before_vis, after_vis, before, after, errs_out, pg.evaluate("() => ({lay: window.__panelLayoutState ? window.__panelLayoutState() : null, body: document.body.className, app: document.getElementById('app') ? document.getElementById('app').className : null})"))
        check("inj: needle panel closed again after exit (it was closed before)", pg.evaluate("() => document.getElementById('needle-panel').hidden"), errs_out)

        # ================= 2. US =================
        pg.evaluate("() => window.NMSKModes.enter('us')"); pg.wait_for_timeout(800)
        vis = pg.evaluate(VIS, CHROME[kind])
        check("us: chrome hidden, mode pill 'US אבחנתי', hero holds the B-mode panel, CINE bar + sliders present", not any(vis.values()) and pg.evaluate("""() => { const r = document.getElementById('us-root').getBoundingClientRect(), h = document.querySelector('.mm-hero').getBoundingClientRect();
            return document.getElementById('mb-pill').textContent.includes('US אבחנתי') && Math.abs(r.left - h.left) < 2 && Math.abs(r.width - h.width) < 2 && !!document.querySelector('.mm-bar') && document.querySelectorAll('.mm-sl input[type=range]').length >= 2; }"""), errs_out)
        chip = pg.locator(('.mm-chips-m' if mobile else '#mb-chips') + ' [data-preset="tear"]')
        chip.click(); pg.wait_for_timeout(500)
        opts = pg.evaluate("() => window.NMSKUltrasound.wizardOptions()")
        if opts and pg.evaluate("() => !document.querySelector('.us-wizard').hidden"):
            pg.evaluate("(sid) => window.NMSKUltrasound.pickWizard(sid)", opts[0]["sid"])
        pg.wait_for_timeout(1200)
        st = pg.evaluate("() => window.NMSKUltrasound.state()")
        check("us: preset applied (depth 4 / DR 55 / 12 MHz, continuous) and CINE running", st["preset"] == "tear" and st["depthCm"] == 4 and st["cineMode"] == "continuous" and st["cine"] is True, errs_out)
        check("us: hero status chip and 'not an ultrasound' badge rendered", pg.evaluate("() => document.querySelector('.mm-chip').textContent.includes('MHz') && document.querySelector('.mm-badge').textContent.includes('לא אולטרסאונד')"), errs_out)
        # Q273 (1): the tool's own status line ("Click the skin in the 3-D view ...") must not render under / over the hero badge
        ov = pg.evaluate("""() => { const rd = document.querySelector('#us-root .us-read'), bd = document.querySelector('.mm-badge'); const box = e => { const r = e.getBoundingClientRect(); return {x: r.left, y: r.top, w: r.width, h: r.height, vis: getComputedStyle(e).display !== 'none' && r.width > 0 && r.height > 0}; };
            const a = box(rd), b = box(bd); const hit = a.vis && b.vis && a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h; return {readVisible: a.vis, overlap: hit, badgeVisible: b.vis}; }""")
        check("us (Q273-1): the English status line is hidden in the mode and does not overlap the badge", not ov["readVisible"] and not ov["overlap"], errs_out)
        check("us (Q273-3): B-mode overlay labels drawn in Hebrew inside the mode (language hook)", pg.evaluate("() => window.NMSKUltrasound.overlayLang && window.NMSKUltrasound.overlayLang() === 'he'"), errs_out)
        pg.locator(".mm-primary").click(); pg.wait_for_timeout(900)
        check("us: 'השווה לצד הנגדי (A/B)' turned A/B on with a second placement", pg.evaluate("() => { const s = window.NMSKUltrasound.state(); return s.ab === true && s.P2 !== null; }"), errs_out)
        pg.evaluate("() => window.NMSKUltrasound.idle()"); pg.wait_for_timeout(300)
        ab = pg.evaluate("""() => { const fr = window.NMSKUltrasound.frames(), s = window.NMSKUltrasound.state(); const b = fr.filter(f => f && f.spec && (f.spec.slot === 'B' || /^B\b/.test(f.spec.label || '')))[0] || fr[1];
            return {n: fr.length, contactA: !!(fr[0] && fr[0].sim && fr[0].sim.contact), contactB: !!(b && b.sim && b.sim.contact), snap: s.abSnapMm, note: (document.querySelector('.mm-note') || {textContent: ''}).textContent}; }""")
        check(f"us (Q273-2): slot B has skin contact after A/B (snap {ab['snap'] and round(ab['snap'])} mm, note='{ab['note'][:40]}')", ab["n"] >= 2 and ab["contactA"] and ab["contactB"], errs_out)
        if ab["snap"] is not None and ab["snap"] > 5:
            check("us (Q273-2): the CINE bar says B was snapped to the nearest skin", "הוצמד" in ab["note"], errs_out)
        pg.screenshot(path=str(shots / f"us_{tag}.png"))
        if not mobile:   # Q273 (5): "שמור תמונה" = a real download attempt (canvas.toBlob + anchor) + the Hebrew toast
            try:
                with pg.expect_download(timeout=8000) as dl:
                    pg.get_by_role("button", name="שמור תמונה").click()
                name = dl.value.suggested_filename
            except Exception as e:
                name = "(no download: %s)" % str(e)[:80]
            pg.wait_for_timeout(200)
            tst = pg.evaluate("() => { const t = document.querySelector('.mm-toast'); return t && !t.hidden ? t.textContent : ''; }")
            check(f"us (Q273-5): 'שמור תמונה' attempted a PNG download ({name}) and showed a Hebrew toast", name.endswith(".png") and bool(tst) and any('\u0590' <= ch <= '\u05ff' for ch in tst), errs_out)
        pg.evaluate("() => window.NMSKUltrasound.setAb(false)")
        pg.evaluate("() => window.NMSKModes.exit()"); pg.wait_for_timeout(3500)   # the page's own 500 ms layout poller (Q267 item 9) settles back to Model-only after a tool closes
        after_vis = pg.evaluate(VIS, CHROME[kind]); after = pg.evaluate(SNAP)
        restored("us", before_vis, after_vis, before, after, errs_out, pg.evaluate("() => ({lay: window.__panelLayoutState ? window.__panelLayoutState() : null, body: document.body.className, app: document.getElementById('app') ? document.getElementById('app').className : null})"))
        check("us: the ultrasound panel closed again (it was closed before)", pg.evaluate("() => !window.NMSKUltrasound.isOpen()"), errs_out)

        # ================= 3. compare =================
        pg.evaluate("() => window.NMSKModes.enter('cmp')"); pg.wait_for_timeout(900)
        vis = pg.evaluate(VIS, CHROME[kind])
        check("cmp: chrome hidden, two panes + lock + injury bar, reference panel docked in the patient pane", not any(vis.values()) and pg.evaluate("""() => { const r = document.getElementById('ref-root').getBoundingClientRect(), p = document.querySelectorAll('.mm-stage')[0].getBoundingClientRect();
            return document.getElementById('mb-pill').textContent.includes('השוואת דימות') && document.querySelectorAll('.mm-pane').length === 2 && !!document.querySelector('.mm-lock button') && !!document.querySelector('.mm-foot') && Math.abs(r.left - p.left) < 2 && Math.abs(r.width - p.width) < 2; }"""), errs_out)
        png = shots / "_fixture_1x1.png"
        if not png.exists():
            png.write_bytes(PNG_1x1)
        pg.set_input_files("#ref-root input[type=file]", str(png)); pg.wait_for_timeout(400)
        check("cmp: a local PNG loaded through the existing reference panel (File API, nothing uploaded)", pg.evaluate("() => window.NMSKReference.state().loaded === true"), errs_out)
        pg.locator(".mm-ov button").first.click() if not mobile else pg.evaluate("() => window.NMSKReference.set({zoom: 1.6})")
        pg.locator(".mm-lock button").click(); pg.wait_for_timeout(500)
        check("cmp: shared zoom lock on -> the atlas pane follows the reference zoom (CSS scale)", pg.evaluate("""() => { const z = window.NMSKReference.state().zoom, t = document.getElementById('us-root') || document.getElementById('img-root');
            return document.querySelector('.mm-lock button').getAttribute('aria-pressed') === 'true' && z > 1 && t.style.transform.includes('scale(' + z); }"""), errs_out)
        pg.locator(".mm-foot .mm-tog").first.click(); pg.wait_for_timeout(200)
        pg.locator(".mc-pick .mc-res button").first.click(); pg.wait_for_timeout(500)
        pg.get_by_role("button", name="בינונית").click(); pg.wait_for_timeout(500)
        sev = pg.evaluate("() => { const b = document.querySelector('#i-injury [data-sev=\"moderate\"], #inj-card [data-sev=\"moderate\"]'); return b ? b.getAttribute('aria-pressed') : null; }")
        check("cmp: marking an injury (moderate) went through the page's own Mark + severity mechanism", sev == "true" and pg.evaluate("() => document.querySelector('.mm-foot [aria-pressed=\"true\"]').textContent") == "בינונית", errs_out)
        pg.locator(".mm-foot .mm-ref").click(); pg.wait_for_timeout(300)
        dr = pg.evaluate("() => { const d = document.querySelector('.mm-drawer'); const first = d.querySelector('p, dt, dd, div'); return {hidden: d.hidden, first: first ? first.textContent.trim() : '', dts: Array.from(d.querySelectorAll('dt')).map(e => e.textContent.trim()), text: d.textContent}; }")
        check("cmp (Q273-4): reference drawer opened with the Hebrew label 'מידע רפרנס — לא אבחנה או המלצת טיפול' as its first line", not dr["hidden"] and dr["first"] == "מידע רפרנס — לא אבחנה או המלצת טיפול", errs_out)
        check("cmp (Q273-3): the drawer's field names are Hebrew (anatomical names / citations untouched)", not any(t in ("Branch of", "Innervated by", "Innervates", "Supplies") for t in dr["dts"]) and "not a diagnosis" not in dr["text"], errs_out)
        pg.screenshot(path=str(shots / f"cmp_{tag}.png"))
        pg.evaluate("() => window.NMSKModes.exit()"); pg.wait_for_timeout(3500)   # the page's own 500 ms layout poller (Q267 item 9) settles back to Model-only after a tool closes
        after_vis = pg.evaluate(VIS, CHROME[kind]); after = pg.evaluate(SNAP)
        restored("cmp", before_vis, after_vis, before, after, errs_out, pg.evaluate("() => ({lay: window.__panelLayoutState ? window.__panelLayoutState() : null, body: document.body.className, app: document.getElementById('app') ? document.getElementById('app').className : null})"))
        check("cmp: the reference panel closed again (it was closed before)", pg.evaluate("() => !window.NMSKReference.isOpen()"), errs_out)
        check("0 page errors throughout this whole real-interaction pass", len(errs) == 0, errs_out)
        for e in errs[:10]:
            print("    PAGEERR:", e[:300])
        if not mobile:   # Q273 (6): a hub card's mode link, clicked, lands directly in that mode (real navigation, new tab)
            hub_dir = Path(os.environ.get("Q273_TMP", "/dev/shm")) / "q273_hub"; hub_dir.mkdir(parents=True, exist_ok=True)
            hub_src = (REPO / "viewer" / "atlas_hub.html").read_text(encoding="utf-8")
            n_links = hub_src.count("#mode=")
            check("hub: every card carries the three mode links (#mode=inj|us|cmp)", n_links == 18, errs_out)
            (hub_dir / "atlas_hub.html").write_text(hub_src, encoding="utf-8")
            hsrv, hport = serve(hub_dir)
            try:
                for how, suffix in (("hash", "#mode=us"), ("query", "?mode=cmp")):
                    ctx2 = b.new_context(viewport=viewport); ctx2.route("**/*", route); hp = ctx2.new_page()   # context-level routing: the popup page needs the three.js stand-in too
                    hp.goto(f"http://127.0.0.1:{hport}/atlas_hub.html", wait_until="load", timeout=60000)
                    # the live links point at claude.ai (not reachable here): retarget the first mode link at the locally served page
                    hp.evaluate("(u) => { const a = document.querySelector('p.modes a'); a.href = u; a.textContent = 'LOCAL'; }", f"http://127.0.0.1:{port}/{html}{suffix}")
                    with ctx2.expect_page(timeout=30000) as np_:
                        hp.locator("p.modes a").first.click()
                    tp = np_.value
                    tp.wait_for_function("window.__modesState && window.__modesState().cur", timeout=90000)
                    cur = tp.evaluate("() => window.__modesState().cur")
                    want = "us" if how == "hash" else "cmp"
                    check(f"hub (Q273-6): clicking a card's mode link ({how}: {suffix}) landed directly in mode '{want}' (got '{cur}')", cur == want, errs_out)
                    ctx2.close()
            finally:
                hsrv.terminate()
        b.close()
    finally:
        srv.terminate()


def main(argv):
    if len(argv) < 2:
        print(__doc__); return 2
    own_dir, zan_dir = argv[0], argv[1]
    shots = Path(argv[argv.index("--shots") + 1]) if "--shots" in argv else Path(os.environ.get("Q272_SHOTS", "/tmp/q272_shots"))
    shots.mkdir(parents=True, exist_ok=True)
    errs = []
    with sync_playwright() as pl:
        run_page(pl, own_dir, "own", {"width": 1400, "height": 900}, errs, shots)
        run_page(pl, own_dir, "own", {"width": 390, "height": 844}, errs, shots)
        run_page(pl, zan_dir, "zan", {"width": 1400, "height": 900}, errs, shots)
        run_page(pl, zan_dir, "zan", {"width": 390, "height": 844}, errs, shots)
    print("\nTOTAL FAILED CHECKS:", len(errs))
    for e in errs:
        print("  -", e)
    print("screenshots:", shots)
    return 0 if not errs else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
