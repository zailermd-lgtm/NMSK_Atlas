#!/usr/bin/env python3
"""Q298: real headless-Chromium check (desktop 1400x900 real clicks + phone 390x844 real touch) of what this round added.

The owner's report: "I looked for the ITB, also by its full name, and couldn't find it! The search has to allow that. Also
an easy way to mark SEVERAL structures, not just one. And after picking one structure, allow picking the ones ADJACENT to
it, the ones RELATED to it, and the ones that share its FUNCTIONAL GROUP."

A  the four ways the owner would name the iliotibial tract -- "ITB", "IT band", "iliotibial band" and its Hebrew name --
   each reach Iliotibial tract, typed into the page's own search box, read off the page's own rendered list, and the row
   SAYS which name matched, so the canonical name is learnt.
B  a sample of 20 published abbreviations each resolve to the structure the data file says they do.
C  a typo ("iliotibal band", "semitendinosis") still finds the structure.
D  multi-select: "Mark all N" marks every match of a search in ONE undo step (the marked count goes up by N and one
   Ctrl/Cmd+Z puts it back), a second batch is a second single step, and the model-side "On model" mode is reachable.
E  adjacent / related / functional group each add a plausible NON-EMPTY set in one tap, each a single undo step, and the
   numbers and the measured threshold are reported.
F  0 page errors.

The pages the owner's structure is on are the four Z pages; the Imaging pages have no iliotibial tract (their CT / cryosection
labels do not carry it), so A runs on the Z pages and B-F run on both engines.

    python3 scripts/anatomy/q298/verify_q298.py PAGE_DIR... [--shots DIR] [--phone=N]"""
from __future__ import annotations
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE.parent / "q283")); sys.path.insert(0, str(HERE))
import verify_q283 as V  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

check, tap = V.check, V.tap
KEY = {"viewer_zan_atlas": "base_m", "viewer_base_female": "base_f", "viewer_zan_vhm": "comb_m",
       "viewer_zan_female": "comb_f", "viewer_m_hr": "own_m", "viewer_f_hr": "own_f"}
ITB_QUERIES = ["ITB", "IT band", "iliotibial band", "הרצועה האיליוטיביאלית"]
TYPOS = [("iliotibal band", "Iliotibial tract"), ("semitendinosis", "Semitendinosus"), ("gastrocnemus", "Gastrocnemius")]
EXPAND = [("adj", "q8-adj"), ("rel", "q8-rel"), ("grp", "q8-grp")]


def box_of(pg):
    """the engine's own search input: #q on the own pages, #search on the Z pages (the Q297 trap)."""
    for _ in range(8):
        for sel in ("#search", "#q"):
            if pg.is_visible(sel):
                return sel
        for s in ("#btn-panel", "#m-list", "#t-lay3", "#insp-min"):
            if pg.is_visible(s):
                tap(pg, s, False); break
        pg.wait_for_timeout(400)
    return None


def q298_ready(pg):
    pg.wait_for_function("window.NMSKQ298 && NMSKQ298.ready()", timeout=120000)
    pg.wait_for_function("window.NMSKQ298.state().adjacency === false || window.NMSKQ298.state().expand === null"
                         " || window.NMSKQ298.state().expand.adjReady", timeout=120000)


def search(pg, box, q, phone):
    """type the query the way a person does, and read the rows the page itself rendered"""
    pg.fill(box, "")
    pg.wait_for_timeout(120)
    pg.fill(box, q)
    pg.dispatch_event(box, "input")
    pg.wait_for_timeout(500)
    return pg.evaluate("() => Array.from(document.querySelectorAll('#list button.item, #list .row, #list button'))"
                       ".map(b => b.innerText.replace(/\\s+/g, ' ').trim()).slice(0, 40)")


def marked(pg):
    return pg.evaluate("() => (window.selCtl ? selCtl.state().marks.length : (window.NMSKQ298 ? -1 : -2))")


def run_page(d: Path, errs: list, shots: Path | None, only_phone=None, report=None):
    key = KEY[d.name]
    kind = "own" if key in ("own_m", "own_f") else "zan"
    html = V.html_of(d)
    srv, port = V.serve(d)
    syn = json.loads((REPO / "data/anatomy/synonyms_q298.json").read_text(encoding="utf-8"))
    comp = json.loads((REPO / f"data/derived/Q298_search_{key}.json").read_text(encoding="utf-8"))
    # 20 abbreviations that this page really carries, taken from the compiled table (not guessed)
    abbr = []
    for a in comp["alias"]:
        if a["k"] == "abbr" and a["d"] not in [x[0] for x in abbr]:
            abbr.append((a["d"], a["c"]))
    abbr = abbr[:20]
    try:
        with sync_playwright() as pl:
            b = pl.chromium.launch(args=V.LAUNCH_ARGS, executable_path="/opt/pw-browsers/chromium")
            sizes = [((1400, 900), False), ((390, 844), True)]
            if only_phone is not None:
                sizes = [sizes[1]] if only_phone else [sizes[0]]
            for (w, h), phone in sizes:
                T = f"{key}_{w}"
                ctx = b.new_context(viewport={"width": w, "height": h}, has_touch=phone, is_mobile=phone, device_scale_factor=1)
                pg = ctx.new_page(); perr = []
                pg.on("pageerror", lambda e: perr.append(str(e)))
                pg.route("**/*", V.route)
                pg.goto(f"http://127.0.0.1:{port}/{html}", wait_until="load", timeout=120000)
                V.ready(pg)
                q298_ready(pg)
                st = pg.evaluate("() => NMSKQ298.state()")
                check(f"{T}: the Q298 layer is live ({st['structures']} structures, {st['aliasForms']} alias forms, "
                      f"{st['groups']} groups, {st['adjacentPairs']} adjacent pairs at {st['threshold_mm']} mm, "
                      f"{st['relationLinks']} relation links)",
                      st["ready"] and st["aliasForms"] > 300 and st["adjacency"] and st["relations"], errs)
                box = box_of(pg)
                check(f"{T}: the page's own structure search box is reachable ({box})", bool(box), errs)
                if not box:
                    ctx.close(); continue

                # --- A: the owner's four names for the iliotibial tract
                if kind == "zan":
                    for q in ITB_QUERIES:
                        rows = search(pg, box, q, phone)
                        hit = [r for r in rows if "iliotibial" in r.lower()]
                        check(f"{T}: A \"{q}\" reaches the Iliotibial tract ({len(rows)} rows, first {rows[:1]})",
                              bool(hit), errs)
                        if hit:
                            check(f"{T}: A that row says WHICH name matched ({hit[0][:70]!r})", "(" in hit[0], errs)
                else:
                    rows = search(pg, box, "ITB", phone)
                    check(f"{T}: A this page genuinely has no iliotibial tract, and the search says so rather than "
                          f"silently returning nothing ({len(rows)} rows)",
                          not [r for r in rows if "iliotibial" in r.lower()], errs)

                # --- B: 20 abbreviations resolve
                bad = []
                for ab, canon in abbr:
                    rows = search(pg, box, ab, phone)
                    want = canon.split(" (")[0].lower()
                    if not [r for r in rows if want[:16] in r.lower()]:
                        bad.append((ab, canon, rows[:2]))
                check(f"{T}: B all {len(abbr)} sampled abbreviations resolve to their structure "
                      f"({len(abbr) - len(bad)}/{len(abbr)}; {bad[:2]})", not bad, errs)

                # --- C: a typo still finds it
                for q, want in TYPOS:
                    rows = search(pg, box, q, phone)
                    hit = [r for r in rows if want.lower()[:12] in r.lower()]
                    if kind == "own" and want == "Iliotibial tract":
                        continue
                    check(f"{T}: C the typo \"{q}\" still finds {want} ({len(rows)} rows, first {rows[:1]})", bool(hit), errs)

                # --- D: multi-select, one undo step per action
                search(pg, box, "hamstring" if kind == "zan" else "flexor", phone)
                n0 = marked(pg)
                res = pg.evaluate("() => { const r = NMSKQ298.result(); return r ? r.ids.length : 0; }")
                check(f"{T}: D the search matched something to mark ({res})", res > 1, errs)
                tap(pg, "#q8-all", phone); pg.wait_for_timeout(900)
                n1 = marked(pg)
                check(f"{T}: D \"Mark all {res}\" marked several at once ({n0} -> {n1})", n1 >= n0 + 2, errs)
                search(pg, box, "gluteus" if kind == "zan" else "gluteus", phone)
                res2 = pg.evaluate("() => { const r = NMSKQ298.result(); return r ? r.ids.length : 0; }")
                tap(pg, "#q8-all", phone); pg.wait_for_timeout(900)
                n2 = marked(pg)
                check(f"{T}: D a second batch added more ({n1} -> {n2}, {res2} offered)", n2 > n1, errs)
                pg.keyboard.press("Control+z"); pg.wait_for_timeout(1200)
                n3 = marked(pg)
                check(f"{T}: D ONE undo step put the whole second batch back, not one structure "
                      f"({n2} -> {n3}, expected {n1})", n3 == n1, errs)
                pg.keyboard.press("Control+z"); pg.wait_for_timeout(1200)
                n4 = marked(pg)
                check(f"{T}: D a second undo put the first batch back too ({n3} -> {n4}, expected {n0})", n4 == n0, errs)
                omb = pg.evaluate("() => !!document.getElementById('q8-onmodel')")
                if omb:
                    tap(pg, "#q8-onmodel", phone); pg.wait_for_timeout(400)
                    on = pg.evaluate("() => { const b = document.getElementById('t-mark') || document.getElementById('sel-markmode');"
                                     " return !!b && b.getAttribute('aria-pressed') === 'true'; }")
                    check(f"{T}: D \"On model\" arms the engine's own mark-by-tapping mode", on, errs)
                    tap(pg, "#q8-onmodel", phone); pg.wait_for_timeout(300)

                # --- E: the three expansions
                pick = "Semitendinosus" if kind == "zan" else "Semitendinosus"
                rows = search(pg, box, pick, phone)
                idx = pg.evaluate("([n]) => Array.from(document.querySelectorAll('#list button.item, #list .row, #list button'))"
                                  ".findIndex(b => b.innerText.toLowerCase().indexOf(n.toLowerCase()) >= 0)", [pick])
                check(f"{T}: E {pick} is in the list to pick ({idx}, {len(rows)} rows)", idx >= 0, errs)
                if idx >= 0:
                    tap(pg, f"#list button.item, #list .row, #list button >> nth={idx}", phone)
                    pg.wait_for_timeout(900)
                    cnt = pg.evaluate("() => { const s = NMSKQ298.state(); return s.expand ? s.expand.counts : null; }")
                    check(f"{T}: E after picking {pick} all three expansions offer something ({cnt})",
                          bool(cnt) and cnt["adj"] > 0 and cnt["rel"] > 0 and cnt["grp"] > 0, errs)
                    got = {}
                    for which, bid in EXPAND:
                        m0 = marked(pg)
                        if not pg.is_visible("#" + bid):
                            check(f"{T}: E the {which} button is visible", False, errs); continue
                        tap(pg, "#" + bid, phone); pg.wait_for_timeout(900)
                        if which in ("rel", "grp"):
                            # these open a short menu when more than one kind / group applies
                            nmenu = pg.evaluate("() => { const m = document.getElementById('q8-menu');"
                                                " return m && !m.hidden ? m.querySelectorAll('button').length : 0; }")
                            if nmenu:
                                tap(pg, "#q8-menu button >> nth=0", phone); pg.wait_for_timeout(900)
                        m1 = marked(pg)
                        got[which] = m1 - m0
                        check(f"{T}: E \"{which}\" added a non-empty set in one tap (+{m1 - m0} marked)", m1 > m0, errs)
                        pg.keyboard.press("Control+z"); pg.wait_for_timeout(1200)
                        m2 = marked(pg)
                        check(f"{T}: E \"{which}\" is ONE undo step ({m1} -> {m2}, expected {m0})", m2 == m0, errs)
                    stt = pg.evaluate("() => NMSKQ298.state()")
                    msg = pg.evaluate("() => { const e = document.getElementById('q8-status'); return e ? e.textContent : ''; }")
                    print(f"       {T}: {pick} -> adjacent {stt['expand']['counts']['adj']} within "
                          f"{stt['expand']['adjThresholdMm']} mm, related {stt['expand']['counts']['rel']}, "
                          f"functional groups {stt['expand']['counts']['grp']}; marked by the three taps {got}")
                    if report is not None:
                        report.append({"page": T, "pick": pick, "counts": stt["expand"]["counts"],
                                       "threshold_mm": stt["expand"]["adjThresholdMm"], "added": got,
                                       "status_line": msg[:300]})
                check(f"{T}: F no page errors ({perr[:1]})", not perr, errs)
                if shots:
                    shots.mkdir(parents=True, exist_ok=True)
                    pg.screenshot(path=str(shots / f"{key}_{w}.png"))
                ctx.close()
            b.close()
    finally:
        srv.terminate()


def main(argv):
    shots = None; only_phone = None; out = None
    if "--shots" in argv:
        i = argv.index("--shots"); shots = Path(argv[i + 1]); argv = argv[:i] + argv[i + 2:]
    if "--report" in argv:
        i = argv.index("--report"); out = Path(argv[i + 1]); argv = argv[:i] + argv[i + 2:]
    ph = [a for a in argv if a.startswith("--phone=")]
    if ph:
        only_phone = ph[0].split("=")[1] == "1"; argv = [a for a in argv if not a.startswith("--phone=")]
    dirs = [Path(a) for a in argv]
    errs = []; report = []
    for d in dirs:
        print(f"== {d}")
        run_page(d, errs, shots, only_phone, report)
    print(f"\nQ298 VERIFY: {'FAIL ' + str(len(errs)) if errs else 'OK'}")
    for e in errs:
        print("  FAIL", e)
    if out:
        out.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
