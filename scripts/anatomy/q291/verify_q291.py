#!/usr/bin/env python3
"""Q291: real headless-Chromium check of the 1-18 MHz ultrasound frequency stepper, on locally served template-only rebuilt pages.

Desktop 1400x900 (mouse clicks), panel (#t-ultrasound):
  A  the Probe tab's stepper shows the linear default "10 MHz"; clicking − down to 1 MHz and + up to 18 MHz and − back to 10: at
     every step the label and the tool state agree, the selected image was re-simulated (its own checksum changed), the image has
     no NaN / Inf, − is disabled at 1 and + at 18; the out-of-band note shows exactly below the linear band (1-3 MHz)
  B  probe defaults and bands: Convex -> 4 MHz (in band, no note), + to 7 -> note; Sector -> 3 MHz, + to 6 -> note; Linear -> 10
  C  kernel time on the selected frame's own body raster (the tool's simAt hook): 1 / 7.5 (the old preset) / 12 / 18 MHz, best of 5
Phone 390x844 (has_touch, real touch taps), the "US אבחנתי" mode:
  D  the mode card's −/+ (≥ 36 px targets, inside the 390 px width, no horizontal page scroll) step 10 -> 1 -> 18 -> 10 with the
     same per-step checks, the Hebrew out-of-band note at 1-3 MHz; the slider between the buttons follows
  E  the clean full-screen CINE view: its ⋯ sheet has the same stepper; with CINE playing, + / − change the frequency and the
     running CINE re-simulates at it
F  0 page errors

    python3 scripts/anatomy/q291/verify_q291.py PAGE_DIR [PAGE_DIR ...]
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "q283"))
import verify_q283 as V  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

check = V.check
U = "window.NMSKUltrasound"
STEP_T = 240000

STATE = """(box) => { const U = window.NMSKUltrasound, S = U.state(), b = document.querySelector('[data-fq-box="' + box + '"]');
  const fr = U.frames()[S.sel] || U.frames()[0]; let h = 0, bad = 0;
  if (fr && fr.sim) { const d = fr.sim.db; for (let i = 0; i < d.length; i += 3) { const v = d[i]; if (!isFinite(v)) bad++; else h = (h * 31 + Math.round(v * 4)) | 0; } }
  const q = s => b && b.querySelector(s), note = q('[data-fqn]'), minus = q('[data-fq="-"]'), plus = q('[data-fq="+"]'), rng = q('input[type=range]');
  const vis = e => !!e && e.getBoundingClientRect().width > 0 && getComputedStyle(e).display !== 'none';
  return {freq: S.freq, probe: S.probe, label: q('[data-fqv]') ? q('[data-fqv]').textContent : null, note: note ? note.textContent : null, noteVis: vis(note) && !!note.textContent,
    band: b && b.getAttribute('data-band'), minusDis: !!(minus && minus.disabled), plusDis: !!(plus && plus.disabled), rng: rng ? +rng.value : null,
    sig: fr ? String(fr.sig).split('|')[0] : null, sum: h, bad: bad, simMs: fr ? fr.simMs : null}; }"""
RECTS = """(box) => { const b = document.querySelector('[data-fq-box="' + box + '"]'); if (!b) return null;
  return Array.from(b.querySelectorAll('button')).map(e => { const r = e.getBoundingClientRect(), c = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
    return {w: r.width, h: r.height, l: r.left, r: r.right, top: !!c && (c === e || e.contains(c))}; }); }"""


def idle(pg):
    pg.evaluate(f"() => {U}.idle()")


def press(pg, box, which, phone):
    V.tap(pg, f'[data-fq-box="{box}"] [data-fq="{which}"]', phone)
    pg.wait_for_timeout(120)
    idle(pg)


def sweep(pg, box, phone, errs, tag, he):
    """10 -> 1 -> 18 -> 10 with a check at every step"""
    st = pg.evaluate(STATE, box)
    seq = list(range(st["freq"] - 1, 0, -1)) + list(range(2, 19)) + list(range(17, 9, -1))
    fails, prev, times, notes = [], st, [], {}
    for f in seq:
        press(pg, box, "-" if f < prev["freq"] else "+", phone)
        s = pg.evaluate(STATE, box)
        ok = (s["freq"] == f and s["label"] == f"{f} MHz" and s["sig"] == str(f) and s["sum"] != prev["sum"] and s["bad"] == 0
              and s["minusDis"] == (f == 1) and s["plusDis"] == (f == 18) and (s["rng"] is None or s["rng"] == f)
              and s["noteVis"] == (f < 4) and (f >= 4 or (("מחוץ" in s["note"]) if he else ("outside" in s["note"]))))
        if not ok:
            fails.append((f, {k: s[k] for k in ("freq", "label", "sig", "bad", "minusDis", "plusDis", "noteVis", "rng")}, s["sum"] == prev["sum"]))
        if s["simMs"] is not None:
            times.append((f, s["simMs"]))
        if f in (1, 3, 4, 18):
            notes[f] = s["note"]
        prev = s
    check(f"{tag}: stepped {len(seq)} times 10->1->18->10; label / state / re-simulated image / no NaN / end-stops / out-of-band note correct at every step ({fails[:3]})", not fails, errs)
    check(f"{tag}: out-of-band note at 1 MHz '{notes.get(1)}', none in band (4 MHz '{notes.get(4)}', 18 MHz '{notes.get(18)}')", notes.get(1) and not notes.get(4) and not notes.get(18), errs)
    if times:
        ms = [t for _, t in times]
        print(f"     per-step kernel time of the selected frame: min {min(ms)} / max {max(ms)} ms; at 1 MHz {dict(times).get(1)}, 18 MHz {dict(times).get(18)}")
    return times


def run(page_dir: Path, errs: list, results: dict):
    html = V.html_of(page_dir); srv, port = V.serve(page_dir)
    try:
        with sync_playwright() as pl:
            b = pl.chromium.launch(args=V.LAUNCH_ARGS, executable_path="/opt/pw-browsers/chromium")
            vps = [((1400, 900), False), ((390, 844), True)]
            if os.environ.get("Q291_ONLY") in ("desktop", "phone"):
                vps = [v for v in vps if v[1] == (os.environ["Q291_ONLY"] == "phone")]
            for (w, h), phone in vps:
                ctx = b.new_context(viewport={"width": w, "height": h}, has_touch=phone, is_mobile=phone)
                pg = ctx.new_page(); perr = []
                pg.set_default_timeout(STEP_T)
                pg.on("pageerror", lambda e: perr.append(str(e)))
                pg.route("**/*", V.route)
                tag = f"{page_dir.name}@{w}"
                print(f"=== {tag} ===")
                pg.goto(f"http://127.0.0.1:{port}/{html}", wait_until="load", timeout=120000)
                V.ready(pg)
                pg.wait_for_function(f"() => {U} && window.NMSKModes", timeout=60000)
                pg.evaluate(f"() => {U}.ready()")
                if not phone:
                    V.tap(pg, "#t-ultrasound", phone); pg.wait_for_timeout(800); idle(pg)
                    if pg.evaluate("() => { const t = document.querySelector('#us-root .sectabs [data-sec=probe]'); return !!t && t.getBoundingClientRect().width > 0; }"):
                        V.tap(pg, "#us-root .sectabs [data-sec=probe]", phone)
                    s = pg.evaluate(STATE, "panel")
                    check(f"{tag} A: the panel's stepper shows the linear default ({s['label']}, probe {s['probe']}, no note: {not s['noteVis']})", s["label"] == "10 MHz" and s["probe"] == "linear" and not s["noteVis"], errs)
                    rc = pg.evaluate(RECTS, "panel")
                    check(f"{tag} A: − and + are on top and at least 36 px tall ({[(round(r['w']), round(r['h'])) for r in rc]})", rc and len(rc) == 2 and all(r["top"] and r["h"] >= 35.5 and r["w"] >= 39.5 for r in rc), errs)
                    results[f"{tag} panel"] = sweep(pg, "panel", phone, errs, f"{tag} A", False)
                    # B: probe defaults and bands
                    out = []
                    for k, f0, up_to in (("convex", 4, 7), ("sector", 3, 6)):
                        V.tap(pg, f"#us-root .us-ctl button[title^='{'Curvilinear' if k == 'convex' else 'Phased-array'}']", phone); pg.wait_for_timeout(200); idle(pg)
                        s0 = pg.evaluate(STATE, "panel")
                        for _ in range(up_to - f0):
                            press(pg, "panel", "+", phone)
                        s1 = pg.evaluate(STATE, "panel")
                        out.append((k, s0["label"], s0["noteVis"], s1["label"], s1["note"]))
                        check(f"{tag} B: {k} default {s0['label']} in band (no note), {s1['label']} out of band: '{s1['note']}'",
                              s0["probe"] == k and s0["freq"] == f0 and not s0["noteVis"] and s1["freq"] == up_to and s1["noteVis"] and "outside" in s1["note"] and s1["bad"] == 0, errs)
                    V.tap(pg, "#us-root .us-ctl button[title^='Linear array']", phone); pg.wait_for_timeout(200); idle(pg)
                    s = pg.evaluate(STATE, "panel")
                    check(f"{tag} B: back to linear -> {s['label']}", s["freq"] == 10 and s["probe"] == "linear", errs)
                    # C: kernel time on the real raster
                    t = {}
                    for _ in range(3):                                    # interleaved rounds, best of each: no JIT / GC order bias
                        for f in (18, 7.5, 1, 12):
                            v = pg.evaluate(f"() => {U}.simAt({f}, 2)")
                            if f not in t or v["ms"] < t[f]["ms"]:
                                t[f] = v
                    results[f"{tag} kernel"] = {f: (round(v["ms"], 1), v["nonFinite"], round(v["mean"], 1) if v["mean"] is not None else None) for f, v in t.items()}
                    r18, r75 = t[18]["ms"], t[7.5]["ms"]
                    check(f"{tag} C: kernel on the selected frame's body raster ({t[18]['Wo']}x{t[18]['Ho']}, ds {t[18]['ds']:.3f} mm): 1 MHz {t[1]['ms']:.1f} ms, 7.5 MHz {r75:.1f} ms, 12 MHz {t[12]['ms']:.1f} ms, 18 MHz {r18:.1f} ms "
                          f"(18 / 7.5 = {r18 / r75:.2f}); no NaN / Inf; mean dB {t[7.5]['mean']:.1f} -> {t[18]['mean']:.1f} (darker far field)",
                          all(v["nonFinite"] == 0 for v in t.values()) and r18 <= 1.5 * r75 + 5 and t[18]["mean"] < t[7.5]["mean"], errs)
                else:
                    if pg.evaluate("() => { const s = document.getElementById('mode-switch'); return !s || s.hidden; }"):
                        V.tap(pg, "#t-mode", phone); pg.wait_for_timeout(400)
                    V.tap(pg, '.mw-tile[data-mode="us"]', phone); pg.wait_for_timeout(1200)
                    check(f"{tag}: 'US אבחנתי' mode entered by a tap on its tile", pg.evaluate("() => document.body.classList.contains('mode-us')"), errs)
                    idle(pg)
                    pg.eval_on_selector('[data-fq-box="card"]', "e => e.scrollIntoView({block: 'center'})"); pg.wait_for_timeout(200)
                    rc = pg.evaluate(RECTS, "card")
                    sw = pg.evaluate("() => [document.documentElement.scrollWidth, innerWidth]")
                    check(f"{tag} D: card − / + tap targets {[(round(r['w']), round(r['h'])) for r in rc]} on top, inside 390 px; page scroll width {sw[0]} <= {sw[1]}",
                          rc and len(rc) == 2 and all(r["top"] and r["h"] >= 35.5 and r["w"] >= 39.5 and r["l"] >= 0 and r["r"] <= w for r in rc) and sw[0] <= sw[1], errs)
                    s = pg.evaluate(STATE, "card")
                    check(f"{tag} D: the card shows {s['label']} (slider {s['rng']})", s["label"] == "10 MHz" and s["rng"] == 10, errs)
                    results[f"{tag} card"] = sweep(pg, "card", phone, errs, f"{tag} D", True)
                    # E: full-screen CINE sheet
                    V.tap(pg, ".mm-bar .mm-tog[aria-label]", phone); pg.wait_for_timeout(1500)
                    pg.wait_for_function(f"() => {U}.fsState().on && {U}.motionState().active", timeout=STEP_T)
                    V.tap(pg, ".fs-more", phone); pg.wait_for_timeout(400)
                    check(f"{tag} E: the full-screen ⋯ sheet holds the stepper ({pg.evaluate(STATE, 'fs')['label']})", pg.evaluate(STATE, "fs")["label"] == "10 MHz", errs)
                    seen = []
                    for which, want in (("+", 11), ("+", 12), ("-", 11)):
                        V.tap(pg, f'[data-fq-box="fs"] [data-fq="{which}"]', phone)
                        pg.wait_for_function(f"() => {{ const U = {U}, S = U.state(), fr = U.frames()[S.sel]; return S.freq === {want} && fr && String(fr.sig).split('|')[0] === '{want}'; }}", timeout=STEP_T)
                        s = pg.evaluate(STATE, "fs"); ms = pg.evaluate(f"() => {U}.motionState()")
                        seen.append((s["label"], s["sig"], ms["active"]))
                    check(f"{tag} E: with CINE playing, the sheet's + / − change the frequency and the running CINE re-simulates at it ({seen})",
                          [x[0] for x in seen] == ["11 MHz", "12 MHz", "11 MHz"] and all(x[2] for x in seen), errs)
                    pg.keyboard.press("Escape"); pg.wait_for_timeout(500)
                check(f"{tag} F: 0 page errors ({perr[:2]})", not perr, errs)
                ctx.close()
            b.close()
    finally:
        srv.terminate()


def main():
    errs, results = [], {}
    for d in sys.argv[1:]:
        run(Path(d), errs, results)
    for k, v in results.items():
        print(f"  {k}: {v}")
    print("\nALL OK" if not errs else f"\n{len(errs)} FAILED: " + "; ".join(errs))
    return 0 if not errs else 1


if __name__ == "__main__":
    sys.exit(main())
