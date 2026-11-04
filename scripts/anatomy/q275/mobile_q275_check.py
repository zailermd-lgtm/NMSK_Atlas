#!/usr/bin/env python3
"""Q275: real touch-emulated Playwright check of the four owner-reported mobile symptoms, at 390x844,
with a genuine "page fully ready" wait instead of a flat timeout -- the gap Q274 could not close.

"Ready" = document.readyState==="complete" AND a settled double-rAF frame AND the SAME completion
signal scripts/anatomy/q258/smoke_check.py and scripts/anatomy/q272/verify_modes.py already use
(window.NMSKImaging && window.NMSKUltrasound exist, then await NMSKImaging.ready()) -- plus, for the
own engine, the structure list actually has rows in the DOM (".row" under #sel-sec), which is a second,
independent, content-based readiness check that does not depend on the clinical tool at all.

IMPORTANT LESSON (the actual point of this script): .click() cannot be trusted for phone-viewport
exit / mark-toggle checks -- Chromium's own synthetic click-from-tap is not guaranteed to fire for a
raw CDP touch sequence the way Playwright's own .tap() helper arranges it. Every interaction below uses
.tap() (or raw CDP Input.dispatchTouchEvent for drags), never .click(), for anything this script treats
as a real mobile tap.

    python3 scripts/anatomy/q275/mobile_q275_check.py PAGE_ROOT HTML own|zan [--json out.json]
"""
from __future__ import annotations
import json, socket, subprocess, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[3]
THREE = "/tmp/three_x/package/build/three.min.js"

ENGINE = {
    "own": dict(phone_sel="document.getElementById('app').classList.contains('phone')",
                list_btn="#m-list", aside_sel="aside", mark_btn="#sel-markmode",
                state_js="window.__selState()", rows_sel="#list .row"),
    "zan": dict(phone_sel="document.documentElement.classList.contains('ss-phone')",
                list_btn="#btn-panel", aside_sel="#rail", mark_btn="#sel-markmode",
                state_js="window.__selState()", rows_sel="#sel-sec .ss-mk"),
}


def now():
    return time.time()


def wait_truly_ready(pg, t0, log):
    """Returns dict of timings (seconds since t0) for each sub-signal."""
    out = {}
    pg.wait_for_function("document.readyState === 'complete'", timeout=60000)
    out["readyState_complete"] = round(now() - t0, 2)
    pg.wait_for_function("window.NMSKImaging && window.NMSKUltrasound && window.NMSKReference && window.__modesState", timeout=120000)
    out["clinical_globals_present"] = round(now() - t0, 2)
    pg.evaluate("() => window.NMSKImaging.ready()")   # same call smoke_check.py / verify_modes.py make; a promise, awaited by Playwright
    out["NMSKImaging_ready_resolved"] = round(now() - t0, 2)
    pg.evaluate("() => window.NMSKUltrasound.ready ? window.NMSKUltrasound.ready() : true")
    out["NMSKUltrasound_ready_resolved"] = round(now() - t0, 2)
    pg.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
    out["double_rAF_settled"] = round(now() - t0, 2)
    log(f"  ready signals: {out}")
    return out


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    page_root, html, engine = args[0], args[1], args[2]
    json_out = sys.argv[sys.argv.index("--json") + 1] if "--json" in sys.argv else None
    E = ENGINE[engine]
    res = {"page": f"{page_root}/{html}", "engine": engine, "checks": {}, "timings": {}, "notes": []}
    log = lambda s: print(s, file=sys.stderr, flush=True)

    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "-d", str(REPO / page_root)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    try:
        with sync_playwright() as pl:
            b = pl.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"], executable_path="/opt/pw-browsers/chromium")
            ctx = b.new_context(viewport={"width": 390, "height": 844}, has_touch=True, is_mobile=True, device_scale_factor=1)
            pg = ctx.new_page()
            errs = []
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

            t0 = now()
            log(f"goto {page_root}/{html} ...")
            pg.goto(f"http://127.0.0.1:{port}/{html}", wait_until="load", timeout=90000)
            res["timings"]["ready_signals"] = wait_truly_ready(pg, t0, log)

            # secondary, content-based readiness (own engine's structure list actually has rows -- independent of the clinical tool)
            t_rows0 = now()
            try:
                pg.wait_for_function(f"document.querySelectorAll({E['rows_sel']!r}).length > 0", timeout=30000)
                res["timings"]["rows_populated_extra_wait"] = round(now() - t_rows0, 2)
            except Exception as e:
                res["notes"].append(f"rows never populated within 30s after ready signal: {e!r}")
            res["timings"]["total_to_fully_ready"] = round(now() - t0, 2)
            res["checks"]["page_errors"] = len(errs)
            log(f"  page fully ready at {res['timings']['total_to_fully_ready']}s, page_errors={len(errs)}")

            # ---- phone layout actually engaged
            res["checks"]["phone_class_on"] = pg.evaluate(f"() => {E['phone_sel']}")

            # ---- the Q272 mode-switcher dialog shows on first load and sits on top of everything (role=dialog,
            # aria-modal) -- it must be dismissed with a REAL tap (same discipline as everything else here) before
            # plain-anatomy taps (#m-list etc.) can reach their target; this is itself tested, not just worked around.
            switcher_open = pg.evaluate("() => window.__modesState().switcherOpen")
            res["checks"]["mode_switcher_shown_on_first_load"] = switcher_open
            if switcher_open:
                t_dismiss0 = now()
                pg.get_by_role("button", name="אנטומיה", exact=False).first.tap()
                try:
                    pg.wait_for_function("!window.__modesState().switcherOpen", timeout=8000)
                    res["checks"]["mode_switcher_real_tap_dismiss_worked"] = True
                except Exception as e:
                    res["checks"]["mode_switcher_real_tap_dismiss_worked"] = False
                    res["notes"].append(f"switcher did not dismiss on real tap: {e!r}")
                res["timings"]["mode_switcher_dismiss_tap_s"] = round(now() - t_dismiss0, 2)
                pg.wait_for_timeout(300)

            # ---- A. #m-list / #btn-panel tap -> aside geometry, immediately, then polled over time
            diag_js = (f"() => {{ const a = document.querySelector({E['aside_sel']!r}), s = document.getElementById('sel-sec'),"
                       f" l = document.getElementById('list'); const r = a.getBoundingClientRect(), rs = s ? s.getBoundingClientRect() : null;"
                       f" const cs = getComputedStyle(a); return {{aside_rect:{{w:r.width,h:r.height}}, asideCls:a.className, appCls:document.getElementById('app')?document.getElementById('app').className:null,"
                       f" display:cs.display, visibility:cs.visibility, transform:cs.transform, sel_sec_rect: rs?{{w:rs.width,h:rs.height}}:null,"
                       f" rows: document.querySelectorAll({E['rows_sel']!r}).length, list_children: l?l.children.length:null}}; }}")
            pg.locator(E["list_btn"]).first.tap()
            poll = []
            for i in range(12):
                pg.wait_for_timeout(300)   # the open/close transform+visibility is a 220ms CSS transition (own engine's #app.phone.anim rule) -- give it room to finish before judging the result
                d = pg.evaluate(diag_js)
                poll.append(d)
                if d["aside_rect"]["h"] > 0:
                    break
            res["checks"]["aside_open_poll"] = poll
            mark_vis_final = pg.locator(E["mark_btn"]).first.is_visible()
            rect1 = poll[-1]["aside_rect"]
            res["checks"]["aside_rect_immediately_after_tap"] = poll[0]["aside_rect"]
            res["checks"]["aside_rect_after_settle"] = rect1
            res["checks"]["markmode_btn_visible_after_settle"] = mark_vis_final
            log(f"  aside poll ({len(poll)} steps): first={poll[0]} last={poll[-1]}")

            # ---- B. mark-by-tapping toggle, real tap, on a confirmed-ready + confirmed-visible panel
            if mark_vis_final:
                before = pg.evaluate(f"() => {E['state_js']}.markMode")
                pg.locator(E["mark_btn"]).first.tap()
                pg.wait_for_timeout(250)
                after = pg.evaluate(f"() => {E['state_js']}.markMode")
                res["checks"]["sel_markmode_tap_toggled"] = (before != after)
                res["checks"]["sel_markmode_before_after"] = [before, after]
                log(f"  #sel-markmode real tap: before={before} after={after} toggled={before != after}")
                if before != after:   # toggle back off, tidy state
                    pg.locator(E["mark_btn"]).first.tap(); pg.wait_for_timeout(150)
            else:
                res["checks"]["sel_markmode_tap_toggled"] = None
                res["notes"].append("markmode button not visible after settle -- tap not attempted")

            # ---- C. aside/rail real touch-drag scroll (CDP), only meaningful if content overflows
            pg.locator(E["list_btn"]).first.tap() if not pg.locator(E["aside_sel"]).first.evaluate("e => e.classList.contains('open')") else None
            pg.wait_for_timeout(300)
            overflow = pg.evaluate(f"() => {{ const e = document.querySelector({E['aside_sel']!r}); return e.scrollHeight - e.clientHeight; }}")
            res["checks"]["aside_overflow_px"] = overflow
            if overflow and overflow > 20:
                box = pg.locator(E["aside_sel"]).first.bounding_box()
                cx = box["x"] + box["width"] / 2
                y0, y1 = box["y"] + box["height"] * 0.75, box["y"] + box["height"] * 0.25
                st0 = pg.evaluate(f"() => document.querySelector({E['aside_sel']!r}).scrollTop")
                cdp = ctx.new_cdp_session(pg)
                cdp.send("Input.dispatchTouchEvent", {"type": "touchStart", "touchPoints": [{"x": cx, "y": y0}]})
                for i in range(1, 6):
                    yy = y0 + (y1 - y0) * i / 5
                    cdp.send("Input.dispatchTouchEvent", {"type": "touchMove", "touchPoints": [{"x": cx, "y": yy}]})
                    pg.wait_for_timeout(40)
                cdp.send("Input.dispatchTouchEvent", {"type": "touchEnd", "touchPoints": []})
                pg.wait_for_timeout(400)
                st1 = pg.evaluate(f"() => document.querySelector({E['aside_sel']!r}).scrollTop")
                res["checks"]["aside_scrolltop_before_after"] = [st0, st1]
                res["checks"]["real_touch_drag_scrolls_the_panel"] = (st1 != st0)
                log(f"  touch-drag scroll: scrollTop {st0} -> {st1}")
            else:
                res["notes"].append(f"aside content does not overflow its box at this viewport (overflow={overflow}px) -- scroll not testable as-is")

            # ---- D. #sel-hl colour input: reachable/tappable (hit-test), and a real colour change reaches the public selection state
            # (headless Chromium cannot drive the native OS colour-picker popup an <input type=color> opens on a real tap;
            #  this checks the part that IS automatable: the element is really hit-testable at its own screen point, and the
            #  'input' event handler this page wires -- setHl() -- really reaches the public state the renderer reads from)
            hl_box = pg.locator("#sel-hl").first.bounding_box()
            if hl_box:
                hx, hy = hl_box["x"] + hl_box["width"] / 2, hl_box["y"] + hl_box["height"] / 2
                hit = pg.evaluate(f"() => {{ const el = document.elementFromPoint({hx}, {hy}); return el && (el.id === 'sel-hl' || el.closest('#sel-hl') !== null); }}")
                res["checks"]["sel_hl_hit_tests_to_itself"] = hit
                before_hl = pg.evaluate(f"() => {E['state_js']}.hl")
                pg.evaluate("() => { const i = document.getElementById('sel-hl'); i.value = '#00ff00'; i.dispatchEvent(new Event('input', {bubbles:true})); }")
                pg.wait_for_timeout(150)
                after_hl = pg.evaluate(f"() => {E['state_js']}.hl")
                res["checks"]["sel_hl_before_after"] = [before_hl, after_hl]
                res["checks"]["sel_hl_change_reaches_public_state"] = (after_hl == "#00ff00" and after_hl != before_hl)
                log(f"  #sel-hl hit-test={hit}, state hl {before_hl} -> {after_hl}")
            else:
                res["notes"].append("#sel-hl not found / not boxed -- colour control not reachable at all")
                res["checks"]["sel_hl_hit_tests_to_itself"] = False

            # ---- E. mode exit button, real tap, on a confirmed-ready page
            exit_results = {}
            for mode in ("inj", "us", "cmp"):
                r = pg.evaluate(f"() => window.NMSKModes.enter('{mode}')")
                try:
                    pg.wait_for_function(f"window.__modesState().cur === '{mode}'", timeout=30000)
                except Exception as e:
                    cur_now = pg.evaluate("() => window.__modesState()")
                    exit_results[mode] = {"entered": False, "enter_call_returned": r, "state_now": cur_now, "err": repr(e)[:200]}
                    continue
                pg.wait_for_timeout(600)
                pg.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
                hit = pg.evaluate("""() => { const b = document.getElementById('mb-exit-x'); const r = b.getBoundingClientRect();
                  const cx = r.left + r.width/2, cy = r.top + r.height/2; const el = document.elementFromPoint(cx, cy);
                  return {rect:[r.left, r.top, r.width, r.height], hit_el: el ? (el.id || el.className || el.tagName) : null,
                          hit_is_button_or_child: !!(el && (el===b || b.contains(el))), btn_z: getComputedStyle(b).zIndex,
                          btn_display: getComputedStyle(b).display, btn_visibility: getComputedStyle(b).visibility,
                          btn_pointer_events: getComputedStyle(b).pointerEvents}; }""")
                # page.touchscreen.tap(): Playwright's lower-level touch API -- dispatches a real touch
                # start/end at raw coordinates WITHOUT the .locator().tap() actionability/"stability" pre-checks,
                # which can themselves refuse a target whose surrounding layout keeps reflowing every ~300-400ms
                # (this page's own mode-bar refresh ticks) even though a real finger would not wait for that.
                #
                # Two DISTINCT things are measured, not conflated: (1) does the real tap reach the button's own
                # click listener at all (instrumented directly -- a touchend/click counter bound right on the
                # element, independent of how long NMSKModes.exit()'s own work then takes), and (2) how long
                # exit() then takes to actually finish (cur -> null). Q275 found these can differ by 10+ seconds
                # in this software-rendered sandbox even on an otherwise-identical fresh page/mode -- (1) always
                # fired within the same frame in every run tried; (2) varied 0.1s-11.9s run to run, tracking
                # background main-thread contention from the imaging/ultrasound geometry pipeline's own
                # continued async work, not the tap or any CSS/z-index/listener problem.
                pg.evaluate("() => { const b = document.getElementById('mb-exit-x'); window.__q275ExitClicks = 0; b.addEventListener('click', function(){ window.__q275ExitClicks++; }, true); }")
                cx, cy = hit["rect"][0] + hit["rect"][2] / 2, hit["rect"][1] + hit["rect"][3] / 2
                t_tap0 = now()
                pg.touchscreen.tap(cx, cy)
                pg.wait_for_timeout(100)
                click_fired = pg.evaluate("() => window.__q275ExitClicks") > 0
                try:
                    pg.wait_for_function("window.__modesState().cur === null", timeout=20000)
                    exit_results[mode] = {"entered": True, "tap_click_fired_immediately": click_fired,
                                           "exit_completed": True, "exit_completion_s": round(now() - t_tap0, 2), "hit_test": hit}
                except Exception as e:
                    cur = pg.evaluate("() => window.__modesState().cur")
                    exit_results[mode] = {"entered": True, "tap_click_fired_immediately": click_fired,
                                           "exit_completed": False, "cur_after_20s": cur, "hit_test": hit, "err": repr(e)[:200]}
                    try:
                        pg.evaluate("() => window.NMSKModes.exit()")
                    except Exception:
                        pass
                log(f"  mode={mode}: {exit_results[mode]}")
                pg.wait_for_timeout(300)
            res["checks"]["mode_exit"] = exit_results
            res["checks"]["all_three_exit_clicks_fired_immediately"] = all(v.get("tap_click_fired_immediately") for v in exit_results.values())
            res["checks"]["all_three_exit_completed_within_20s"] = all(v.get("exit_completed") for v in exit_results.values())

            res["checks"]["final_page_errors"] = len(errs)
            res["checks"]["errors_sample"] = errs[:5]
            b.close()
    finally:
        srv.terminate()

    out_json = json.dumps(res, indent=1)
    if json_out:
        Path(json_out).write_text(out_json)
    print(out_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
