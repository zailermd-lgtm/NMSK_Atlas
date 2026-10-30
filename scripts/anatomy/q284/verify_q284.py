#!/usr/bin/env python3
"""Q284: real headless-Chromium verification of the computed moment arms in the Learn panel.

Owner's point: a muscle's action follows from its line of action relative to the joint -- iliopsoas passes medial to the femur to the
lesser trochanter, so flexion should come with some adduction and slight rotation. Q284 computes the moment arms of every muscle
about every pose-rig joint it crosses from the page's own meshes and shows them, badged as computed, in the Learn card; an opt-in
toggle adds the computed secondary components to the simulation. Checked on both engines, desktop click and phone touch:

A  the page carries its own nmsk-moments block and the panel decodes it (key = this page)
B  iliopsoas (r): the card shows the computed table for each of the page's iliopsoas structures, and the numbers the browser shows are
   exactly the committed data/anatomy/moment_arms_<key>.json; hip flexion moment arm > 15 mm at 0 / 45 / 90 deg on every structure
C  the badge says 'computed ... not a textbook statement'; the psoas literature checks are listed with their quotes and DOI links
D  secondary components: off -> hip flexion leaves hip ab/adduction untouched; on -> the same button moves hip ab/adduction by the
   computed ratio (the sign of the computed abduction moment arm) and the pose returns exactly to the start
E  other muscles: gastrocnemius plantarflexes and flexes the knee, biceps flexes the elbow (numbers from the card's own data)
F  0 page errors

    python3 scripts/anatomy/q284/verify_q284.py OWN_DIR ZAN_DIR
"""
from __future__ import annotations
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "q283"))
import verify_q283 as V  # noqa: E402  (same harness: server, three.js route, taps, samplers)
from playwright.sync_api import sync_playwright  # noqa: E402

REPO = HERE.parents[2]
DIRKEY = {"viewer_m_hr": "own_m", "viewer_f_hr": "own_f", "viewer_zan_atlas": "base_m", "viewer_base_female": "base_f", "viewer_zan_vhm": "comb_m", "viewer_zan_female": "comb_f"}
check, tap, tap_text, api = V.check, V.tap, V.tap_text, V.api


def run_page(page_dir: Path, tag: str, errs: list):
    key = DIRKEY[page_dir.name]
    data = json.loads((REPO / "data/anatomy" / ("moment_arms_%s.json" % key)).read_text(encoding="utf-8"))["s"]
    html = V.html_of(page_dir)
    srv, port = V.serve(page_dir)
    try:
        with sync_playwright() as pl:
            b = pl.chromium.launch(args=V.LAUNCH_ARGS, executable_path="/opt/pw-browsers/chromium")
            for (w, h), phone in ((1400, 900), False), ((390, 844), True):
                T = f"{tag}_{w}"
                ctx = b.new_context(viewport={"width": w, "height": h}, has_touch=phone, is_mobile=phone, device_scale_factor=1)
                pg = ctx.new_page()
                page_errs = []
                pg.on("pageerror", lambda e: page_errs.append(str(e)))
                pg.route("**/*", V.route)
                pg.goto(f"http://127.0.0.1:{port}/{html}", wait_until="load", timeout=90000)
                V.ready(pg)
                # A
                pg.wait_for_function("window.learnCtl.moments().loaded", timeout=60000)
                mk = pg.evaluate("() => window.learnCtl.moments().key")
                check(f"{T}: A nmsk-moments block decoded, key {mk} = {key}", mk == key, errs)
                # B
                tap(pg, "#t-learn", phone); pg.wait_for_timeout(200)
                pg.fill("#ln-q", "iliopsoas"); pg.wait_for_timeout(250)
                tap_text(pg, "#ln-res", "(r)", phone); pg.wait_for_timeout(500)
                card = pg.evaluate("() => window.learnCtl.moments().card")
                ids = [c["id"] for c in card]
                check(f"{T}: B the card has computed moment arms for the page's iliopsoas structures ({ids})", ids and not pg.evaluate("() => document.getElementById('ln-ma-wrap').hidden"), errs)
                def num(o):          # JS prints 0.0 as 0: compare as numbers, not as JSON text
                    return {k: [e[0], e[1], [float(a) for a in e[2]], {d: [float(x) for x in v] for d, v in e[3].items()}] for k, e in o.items()}
                same = all(num(c["j"]) == num(data[c["id"]]["j"]) for c in card)
                check(f"{T}: B browser numbers = committed data/anatomy/moment_arms_{key}.json", same, errs)
                for c in card:
                    hip = next((v for k, v in c["j"].items() if k == "hip_r"), None)
                    flex = hip[3]["flex"] if hip else None
                    check(f"{T}: B {c['id']} hip flexion moment arm > 15 mm at {hip[2] if hip else '?'} deg ({flex})", flex and all(x > 15 for x in flex), errs)
                    abd = hip[3]["abd"] if hip else None
                    rot = hip[3]["rot"] if hip else None
                    print(f"     {c['id']}: flex {flex}  abd {abd}  rot {rot}")
                if key.startswith("base") or key.startswith("comb"):
                    check(f"{T}: B on the Z page the whole-iliopsoas card carries both psoas major and iliacus ({ids})", any("psoas" in i for i in ids) and any("iliacus" in i for i in ids), errs)
                rows = pg.evaluate("() => document.querySelectorAll('#ln-ma table').length")
                check(f"{T}: B {rows} moment-arm table(s) rendered", rows >= len(card), errs)
                # C
                txt = pg.evaluate("() => document.getElementById('ln-ma').textContent")
                check(f"{T}: C badge 'computed from this body's geometry ... not a textbook statement'", "Computed from this body's geometry" in txt and "not a textbook statement" in txt, errs)
                links = pg.evaluate("() => Array.from(document.querySelectorAll('#ln-ma a')).map(a => a.href)")
                check(f"{T}: C psoas literature checks with quotes and DOI links ({len(links)} links)", "Skyrme" in txt and "Blemker" in txt and any("doi.org/10.1007/s10439-005-1433-7" in l for l in links), errs)
                # D -- on the psoas part where the page has one, else the whole muscle
                if pg.evaluate("() => Array.from(document.querySelectorAll('#ln-parts button')).some(b => b.textContent.indexOf('Psoas major') >= 0)"):
                    tap_text(pg, "#ln-parts", "Psoas major", phone); pg.wait_for_timeout(400)
                card = pg.evaluate("() => window.learnCtl.moments().card")
                hip = [c["j"]["hip_r"] for c in card if "hip_r" in c["j"]]
                abd0 = sum(x[3]["abd"][0] for x in hip)
                a0 = api(pg, "api.pose().pose().j.hip_r")
                smp = V.sample_during(pg, "api.pose().pose().j.hip_r.slice()", lambda: tap_text(pg, "#ln-acts", "Hip flexion", phone), phone, "animating")
                dab = max(abs(s[1] - a0[1]) for s in smp) if smp else 99
                check(f"{T}: D secondary off: hip flexion leaves ab/adduction untouched (max change {dab:.3f} deg)", smp and dab < 0.01, errs)
                tap(pg, "#ln-sec", phone); pg.wait_for_timeout(150)
                check(f"{T}: D secondary toggle ticked by a real {'tap' if phone else 'click'}", pg.evaluate("() => document.getElementById('ln-sec').checked"), errs)
                smp = V.sample_during(pg, "api.pose().pose().j.hip_r.slice()", lambda: tap_text(pg, "#ln-acts", "Hip flexion", phone), phone, "animating")
                fl = max(s[0] for s in smp) - a0[0] if smp else 0
                ext = min(s[1] for s in smp) - a0[1] if abd0 < 0 else max(s[1] for s in smp) - a0[1]
                check(f"{T}: D secondary on: flexion +{fl:.1f} deg brings ab/adduction {ext:+.1f} deg, the sign of the computed abduction moment arm ({abd0:+.1f} mm)",
                      smp and fl > 15 and abs(ext) > 1 and (ext > 0) == (abd0 > 0), errs)
                msg = pg.evaluate("() => document.getElementById('ln-act-msg').textContent")
                check(f"{T}: D the message names the computed secondary components", "computed secondary components" in msg, errs)
                end = api(pg, "api.pose().pose().j.hip_r")
                check(f"{T}: D pose back exactly at the start ({end} vs {a0})", all(abs(x - y) < 0.01 for x, y in zip(end, a0)), errs)
                tap(pg, "#ln-sec", phone); pg.wait_for_timeout(100)
                # E
                for mus, jn, dof, sgn in (("gastrocnemius", "ankle_r", "dp", -1), ("gastrocnemius", "knee_r", "flex", 1), ("biceps_brachii", "elbow_r", "flex", 1)):
                    if not pg.evaluate(f"() => window.learnCtl.pickMuscle('{mus}', 'r')"):
                        continue
                    pg.wait_for_timeout(300)
                    card = pg.evaluate("() => window.learnCtl.moments().card")
                    has = [c for c in card if jn in c["j"]]
                    if not has:
                        why = [c["x"].get(jn) for c in card if jn in (c.get("x") or {})]
                        print(f"  INFO {T}: {mus} has no {jn} moment arm on this page ({why[0] if why else 'its mesh does not cross that joint'})")
                        continue
                    zero = [c["j"][jn][3][dof][[float(a) for a in c["j"][jn][2]].index(0.0)] for c in has if 0.0 in [float(a) for a in c["j"][jn][2]]]
                    check(f"{T}: E {mus} {jn} {dof} sign {sgn:+d} at 0 deg ({zero})", zero and all(x * sgn > 0 for x in zero), errs)
                check(f"{T}: F 0 page errors", not page_errs, errs)
                if page_errs:
                    print("    ", page_errs[:5])
                ctx.close()
            b.close()
    finally:
        srv.terminate()


def main():
    own, zan = Path(sys.argv[1]), Path(sys.argv[2])
    errs = []
    run_page(own, "own", errs)
    run_page(zan, "zan", errs)
    print("\nALL OK" if not errs else f"\n{len(errs)} FAILED: " + "; ".join(errs))
    return 0 if not errs else 1


if __name__ == "__main__":
    raise SystemExit(main())
