#!/usr/bin/env python3
"""Q281: real headless-Chromium verification of three owner-requested features this round shipped.

Part A -- motor points (NMJ) only for marked muscles: the needle tool's "Emphasize motor points" toggle
(clinical/needle_tool.js, TP.emphasize) now filters clinical/data/motor_points.json's points by the viewer's own
Marked-structures set (viewer/selection/, api.selection().state().marks) instead of showing every motor point in
the body. Checked: 0 marked -> 0 points shown; mark one muscle that HAS motor-point data -> only that muscle's
point(s) shown; re-marking a different muscle updates the shown set live (onHostChange()).

Part B -- the injection-planning preset's new "expected injection zone": picking a target (clinical/needle_tool.js,
TP.planPick -> TP.planZone/TP.renderPlanZone) now shows, together, the target's own origin/insertion/adjacent-tissue
parts (viewer/parts_ui/, grouped by structure_parts.json's own part_sets -- this project's own bundle concept) and
its own motor point(s) (NMJ), drawn via a dedicated overlay independent of Part A's global toggle. Checked on the
deltoid, which has both a multi-bundle part_set (deltoid.heads, 3 named heads) and 3 sourced motor points (Yi et al.
2023, each literally naming "anterior/middle/posterior belly" in its own citation text) -- in both the bare tool's
own panel (#ncl-plan-zone) and the mode-inj Hebrew clinical workspace card (its own zone list).

Part C -- multi-slice cross-section (viewer/cut_cap/, NMSKCrossSection): with Cut mode on, a new toggle shows N
(3-12) parallel real cross-sections (NMSKCapCore.build called once per plane, not one slice repeated) stepped along
the current cut plane's own normal, spacing adjustable by mouse wheel / touch drag over the panel. Checked: turning
it on with Cut mode off is refused with a clear message and 0 faces; turning Cut mode on first, then the
cross-section toggle, builds the requested slice count's worth of real faces; changing the slice count and the
wheel-driven spacing both trigger a rebuild with the new slot count / spacing recorded in state().

    python3 scripts/anatomy/q281/verify_q281.py OWN_DIR ZAN_DIR [--shots DIR]

OWN_DIR / ZAN_DIR: a template-only rebuilt page directory (scripts/regen_template_only.py output), e.g.
/dev/shm/q281/viewer_m_hr and /dev/shm/q281/viewer_zan_atlas.
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
    pg.wait_for_function("window.NMSKClinicalTool && window.__modesState", timeout=120000)
    pg.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
    pg.wait_for_timeout(600)
    # the "what do you want to do today?" mode-switch dialog opens on first load and intercepts every click
    # underneath it until dismissed -- close it the real way (its own close button) before touching anything else
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


# ---------- Part A: NMJ only for marked muscles ----------
def part_a(pg, tag, phone, errs, shots):
    pg.evaluate("() => { if (!window.NMSKClinicalTool.active) window.NeedlePath.toggle(true); }")
    has_sel = pg.evaluate("() => !!(window.NMSKClinicalTool.api.selection && window.NMSKClinicalTool.api.selection())")
    check(f"{tag}: a selection controller is reachable from the add-on (api.selection())", has_sel, errs)
    if not has_sel:
        return
    pg.evaluate("() => window.NMSKClinicalTool.api.selection().clear()")
    # a muscle id that HAS motor-point data on this body (the tool's own loaded list, not guessed)
    mid = pg.evaluate("() => { const p = window.NMSKClinicalTool.mp.points[0]; if (!p) return null; const r = window.NMSKClinicalTool.recs.find(x => x.id === p.structure_id || x.id === p.atlas_id); return r ? r.id : null; }")
    check(f"{tag}: found a structure id with real motor-point data to test with", bool(mid), errs)
    if not mid:
        return
    click_or_tap(pg, "#ncl-mp-on", phone)
    pg.wait_for_timeout(150)
    n0 = pg.evaluate("() => window.NMSKClinicalTool.visibleMpPoints().length")
    check(f"{tag} ({'tap' if phone else 'click'}): 0 muscles marked -> 0 motor points shown (not every point in the body)", n0 == 0, errs)
    pg.evaluate("id => window.NMSKClinicalTool.api.selection().mark(id, true)", mid)
    pg.wait_for_timeout(150)
    shown = pg.evaluate("() => window.NMSKClinicalTool.visibleMpPoints()")
    all_match = shown and all(p.get("structure_id") == mid or p.get("atlas_id") == mid for p in shown)
    check(f"{tag}: marking that one muscle shows only ITS own motor point(s) ({len(shown) if shown else 0} shown, all matching)", bool(shown) and all_match, errs)
    if shots:
        pg.screenshot(path=str(shots / f"mp_marked_{tag}.png"))
    pg.evaluate("id => window.NMSKClinicalTool.api.selection().mark(id, false)", mid)
    pg.wait_for_timeout(150)
    n2 = pg.evaluate("() => window.NMSKClinicalTool.visibleMpPoints().length")
    check(f"{tag}: unmarking it again drops back to 0 shown (live update via onHostChange)", n2 == 0, errs)
    click_or_tap(pg, "#ncl-mp-on", phone)  # turn emphasis back off
    pg.evaluate("() => window.NMSKClinicalTool.api.selection().clear()")


# ---------- Part B: injection-zone landmarks (bundles + NMJ) ----------
def part_b_bare_tool(pg, tag, phone, errs, shots):
    pg.evaluate("() => { if (!window.NMSKClinicalTool.active) window.NeedlePath.toggle(true); }")
    rec = pg.evaluate("""() => {
      const tool = window.NMSKClinicalTool;
      let r = tool.recs.find(x => x.id === 'deltoid_r' || x.id === 'deltoid_l' || x.name === 'Deltoid');
      if (!r) r = tool.recs.find(x => x.cat === 'muscle');
      return r ? {i: r.i, id: r.id, name: r.name} : null;
    }""")
    check(f"{tag}: found a target to plan an injection into", bool(rec), errs)
    if not rec:
        return
    pg.evaluate("i => window.NMSKClinicalTool.planPick(i)", rec["i"])
    pg.wait_for_timeout(300)
    zone = pg.evaluate("() => { const z = window.NMSKClinicalTool.plan.zone; return z ? {groups: z.groups.length, mps: z.mps.length} : null; }")
    check(f"{tag} ({rec['name']}): planPick computed an injection-zone object (groups + motor points)", zone is not None, errs)
    if zone is None:
        return
    is_deltoid = "deltoid" in rec["id"]
    if is_deltoid:
        check(f"{tag}: deltoid has >=1 bundle/landmark group (origin/insertion/adjacent-tissue parts)", zone["groups"] >= 1, errs)
        check(f"{tag}: deltoid has multiple sourced motor points (3, Yi et al. 2023 anterior/middle/posterior belly)", zone["mps"] >= 2, errs)
    html = pg.evaluate("() => document.getElementById('ncl-plan-zone').innerHTML")
    check(f"{tag}: the bare tool's own panel (#ncl-plan-zone) rendered the zone (non-empty)", bool(html and html.strip()), errs)
    if zone["mps"]:
        labels = pg.evaluate("() => Array.from(document.querySelectorAll('.ncl-zone-mp')).map(b => b.textContent)")
        check(f"{tag}: at least one motor-point row rendered as a clickable button", len(labels) == zone["mps"], errs)
        if is_deltoid and labels:
            named = any(w in " ".join(labels).lower() for w in ("anterior", "middle", "posterior"))
            check(f"{tag}: deltoid's points are labelled from their OWN cited rule text (anterior/middle/posterior belly), not a fabricated mapping", named, errs)
    if shots:
        pg.screenshot(path=str(shots / f"zone_bare_{tag}.png"))
    pg.evaluate("() => window.NMSKClinicalTool.planRelease()")
    cleared = pg.evaluate("() => document.getElementById('ncl-plan-zone').innerHTML.trim() === '' && window.NMSKClinicalTool.plan.zone === null")
    check(f"{tag}: Release plan clears the zone list and overlay state", cleared, errs)


def part_b_mode(pg, tag, phone, errs, shots):
    pg.evaluate("() => window.NMSKModes.enter('inj')")
    pg.wait_for_timeout(400)
    entered = pg.evaluate("() => window.__modesState().cur") == "inj"
    check(f"{tag} mode-inj: entered", entered, errs)
    if not entered:
        return
    rec = pg.evaluate("""() => {
      const tool = window.NMSKClinicalTool;
      let r = tool.recs.find(x => x.id === 'deltoid_r' || x.id === 'deltoid_l' || x.name === 'Deltoid');
      if (!r) r = tool.recs.find(x => x.cat === 'muscle');
      return r ? r.i : null;
    }""")
    if rec is not None:
        pg.evaluate("i => window.NMSKClinicalTool.planPick(i)", rec)
        pg.wait_for_timeout(400)
    zone_html = pg.evaluate("() => { const z = document.querySelectorAll('.mi .mc-sec'); return z.length; }")
    check(f"{tag} mode-inj: the Hebrew card rendered zone buttons (אזור ההזרקה הצפוי)", zone_html > 0, errs)
    title = pg.evaluate("() => { const t = Array.from(document.querySelectorAll('.mi .mc-lbl')).map(e => e.textContent); return t.some(x => x.includes('אזור ההזרקה')); }")
    check(f"{tag} mode-inj: the 'אזור ההזרקה הצפוי' section title is present", title, errs)
    if shots:
        pg.screenshot(path=str(shots / f"zone_mode_{tag}.png"))
    pg.evaluate("() => window.NMSKModes.exit()")
    pg.wait_for_timeout(300)
    check(f"{tag} mode-inj: exit left the mode cleanly", pg.evaluate("() => window.__modesState().cur") is None, errs)


# ---------- Part C: multi-slice cross-section ----------
def part_c(pg, tag, phone, errs, shots):
    has_xsec = pg.evaluate("() => !!window.xsecCtl")
    check(f"{tag}: xsecCtl is present on the page", has_xsec, errs)
    if not has_xsec:
        return
    # the needle tool's own floating panel (left open by Part B) covers much of the screen, including the #t-cut
    # toolbar button this part needs to click -- close it first (a real page would have it closed too before the
    # owner goes looking for Cut mode)
    pg.evaluate("() => { if (window.NMSKClinicalTool.active) window.NeedlePath.toggle(false); }")
    pg.wait_for_timeout(150)
    # ensure Cut mode is really off (its own toolbar toggle never pressed yet), then turn cross-section on directly
    # (xsecCtl.set(true), bypassing the DOM: #xsec-on lives inside #cut-panel, which is only visible once Cut mode's
    # own toolbar button has been used at least once -- this checks the refusal LOGIC itself, same mixed-fidelity
    # convention Q276's own script already used for test setup vs. the feature's real click-driven path below)
    was_cut_on = pg.evaluate("() => document.getElementById('t-cut').getAttribute('aria-pressed') === 'true'")
    check(f"{tag}: Cut mode starts off", not was_cut_on, errs)
    pg.evaluate("() => window.xsecCtl.set(true)")
    pg.wait_for_timeout(200)
    st0 = pg.evaluate("() => window.xsecCtl.state()")
    check(f"{tag}: cross-section with Cut mode OFF builds 0 faces (refused, not faked)", st0["on"] and st0["slots"] == 0, errs)
    info_txt = pg.evaluate("() => document.getElementById('xsec-info').textContent")
    check(f"{tag}: the panel says Cut mode must be on first", "Cut mode" in info_txt, errs)
    pg.evaluate("() => window.xsecCtl.set(false)")
    pg.wait_for_timeout(150)
    # now turn Cut mode on via the real toolbar button (#t-cut, both templates)
    if pg.query_selector("#t-cut"):
        click_or_tap(pg, "#t-cut", phone)
    else:
        pg.evaluate("() => window.cutCtl && window.cutCtl.set && window.cutCtl.set(true)")
    pg.wait_for_timeout(300)
    cut_on = pg.evaluate("() => document.getElementById('t-cut').getAttribute('aria-pressed') === 'true'")
    check(f"{tag}: Cut mode is on", cut_on, errs)
    if not cut_on:
        return
    pg.evaluate("() => { const n = document.getElementById('xsec-n'); n.value = 5; n.dispatchEvent(new Event('change')); }")
    click_or_tap(pg, "#xsec-on", phone)
    pg.wait_for_timeout(500)
    st1 = pg.evaluate("() => window.xsecCtl.state()")
    check(f"{tag}: 5 slices, 0 mm thickness -> exactly 5 faces built (one zero-thickness plane each)", st1["on"] and st1["n"] == 5 and st1["slots"] == 5, errs)
    if shots:
        pg.screenshot(path=str(shots / f"xsec5_{tag}.png"))
    # change slice count to 8 -> rebuild to 8 faces
    pg.evaluate("() => { const n = document.getElementById('xsec-n'); n.value = 8; n.dispatchEvent(new Event('change')); }")
    pg.wait_for_timeout(500)
    st2 = pg.evaluate("() => window.xsecCtl.state()")
    check(f"{tag}: raising the slice count to 8 rebuilds to 8 faces", st2["n"] == 8 and st2["slots"] == 8, errs)
    # thickness > 0 -> near+far pair per slice: 2x faces
    pg.evaluate("() => { const t = document.getElementById('xsec-th'); t.value = 4; t.dispatchEvent(new Event('change')); }")
    pg.wait_for_timeout(500)
    st3 = pg.evaluate("() => window.xsecCtl.state()")
    check(f"{tag}: thickness 4 mm -> each of the 8 slices becomes a near+far pair (16 faces)", st3["slots"] == 16, errs)
    # desktop: mouse wheel over the panel changes the spacing; phone (has_touch/is_mobile context): a real synthetic
    # touchstart/touchmove drag instead -- Playwright's mouse.wheel() does not fire a 'wheel' event in a touch-emulated
    # context (there is no mouse there), matching how a real phone user would actually interact (drag, not scroll-wheel)
    sp_before = pg.evaluate("() => window.xsecCtl.state().spacing")
    body = pg.query_selector("#xsec-body")
    if body:
        box = body.bounding_box()
        if box:
            cx, cy = box["x"] + box["width"] / 2, box["y"] + min(30, box["height"] / 2)
            if phone:
                pg.evaluate("""([cx, cy]) => {
                  const el = document.getElementById('xsec-body');
                  function touch(type, y) {
                    const t = new Touch({identifier: 1, target: el, clientX: cx, clientY: y});
                    el.dispatchEvent(new TouchEvent(type, {touches: type === 'touchend' ? [] : [t], changedTouches: [t], bubbles: true, cancelable: true}));
                  }
                  touch('touchstart', cy); touch('touchmove', cy + 40); touch('touchend', cy + 40);
                }""", [cx, cy])
            else:
                pg.mouse.move(cx, cy)
                pg.mouse.wheel(0, 100)
    pg.wait_for_timeout(500)
    sp_after = pg.evaluate("() => window.xsecCtl.state().spacing")
    check(f"{tag} ({'touch-drag' if phone else 'mouse-wheel'}): the panel changed the slice spacing ({sp_before} -> {sp_after})", sp_after != sp_before, errs)
    # turn off: faces must be fully cleared
    pg.evaluate("() => { const t = document.getElementById('xsec-th'); t.value = 0; t.dispatchEvent(new Event('change')); }")
    click_or_tap(pg, "#xsec-on", phone)
    pg.wait_for_timeout(300)
    st4 = pg.evaluate("() => window.xsecCtl.state()")
    check(f"{tag}: turning the toggle off clears every uploaded face (0 slots)", not st4["on"] and st4["slots"] == 0, errs)
    if pg.evaluate("() => document.getElementById('t-cut').getAttribute('aria-pressed') === 'true'"):
        click_or_tap(pg, "#t-cut", phone)


def run_page(page_dir: Path, tag: str, shots: Path, errs: list):
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
                part_a(pg, f"{tag}_{w}", phone, errs, shots)
                part_b_bare_tool(pg, f"{tag}_{w}", phone, errs, shots)
                part_b_mode(pg, f"{tag}_{w}", phone, errs, shots)
                part_c(pg, f"{tag}_{w}", phone, errs, shots)
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
    shots = None
    if "--shots" in sys.argv:
        shots = Path(sys.argv[sys.argv.index("--shots") + 1]); shots.mkdir(parents=True, exist_ok=True)
    errs = []
    print("== own engine (%s) ==" % own_dir)
    run_page(own_dir, "own", shots, errs)
    print("== Z engine (%s) ==" % zan_dir)
    run_page(zan_dir, "zan", shots, errs)
    print(f"\n{'ALL OK' if not errs else 'FAILURES: ' + str(len(errs))}")
    for e in errs:
        print("  -", e)
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
