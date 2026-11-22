#!/usr/bin/env python3
"""Q295: real headless-Chromium check (desktop 1400x900 real clicks + phone 390x844 real touch) of the `fat` system on the rebuilt pages.

A  the page has the fat system: its category is listed with as many structures as the page report added; subcutaneous fat, deep fat and
   unlabelled soft tissue are all there, drawn at load, faint (system opacity 12 %)
B  the system toggle (own engine: the Systems row; Z engine: the layer row) hides every fat structure and shows them again
C  cross-sections: an axial cut through the thigh / abdomen with "Fill cross-section" on: the cut-face line reports filled structures; the
   in-page cut-face kernel (NMSKCapCore.build, the same code the button runs) FILLS the fat meshes at that plane (not outline-only), with
   their alpha raised to solid (capA); the share of the skin's section that is filled rises when the fat system is on (fat on vs off)
D  0 page errors; desktop screenshots of the filled cut face

    python3 scripts/anatomy/q295/verify_q295.py PAGE_DIR... [--shots DIR] [--phone=N]"""
from __future__ import annotations
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE.parent / "q283"))
import verify_q283 as V  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

check, tap, api = V.check, V.tap, V.api
KEY = {"viewer_m_hr": "own_m", "viewer_f_hr": "own_f", "viewer_zan_atlas": "base_m", "viewer_base_female": "base_f",
       "viewer_zan_vhm": "comb_m", "viewer_zan_female": "comb_f"}

CAP_JS = """([y, withFat]) => {
  const a = window.NMSKClinicalTool.api, L = a.list();
  const items = [];
  L.forEach(r => { if (!a.visible(r.i)) return; if (!withFat && r.cat === 'fat') return;
    items.push({key: r.id, name: r.name, cat: r.cat, rgb: [0.5, 0.5, 0.5], alpha: r.cat === 'fat' ? 0.12 : 1,
                geom: () => { const g = a.geometry(r.i); if (!g) return null; let mn = [1e9,1e9,1e9], mx = [-1e9,-1e9,-1e9];
                  for (let k = 0; k < g.pos.length; k += 3) for (let c = 0; c < 3; c++) { const v = g.pos[k + c]; if (v < mn[c]) mn[c] = v; if (v > mx[c]) mx[c] = v; }
                  return {pos: g.pos, idx: g.idx, bmin: mn, bmax: mx}; }}); });
  const res = NMSKCapCore.build(items, {n: [0, 1, 0], d: y}, {px: 1.0, maxDim: 1400});
  const st = {filled: 0, outline: 0, fat_filled: 0, fat_outline: 0, fat_names: []};
  (res.items || []).forEach(r => { const it = items[r.ii]; const f = r.status === 'filled';
    if (f) st.filled++; else st.outline++;
    if (it.cat === 'fat') { if (f) { st.fat_filled++; st.fat_names.push(it.name); } else st.fat_outline++; } });
  let px = 0; if (res.ids) for (let k = 0; k < res.ids.length; k++) if (res.ids[k] > 0) px++; st.px_filled = px;
  st.fat_names = st.fat_names.slice(0, 6);
  return st; }"""


def toggle_sel(own):
    return '#systems .sys[data-cat="fat"]' if own else '.layer-row[data-cat="fat"] button.layer'


def reach(pg, sel, phone):
    for _ in range(4):
        if pg.is_visible(sel):
            return True
        if pg.is_visible("#btn-panel"):
            tap(pg, "#btn-panel", phone)
        elif pg.is_visible("#m-list"):            # own engine, phone layout: the list / systems bottom sheet
            tap(pg, "#m-list", phone)
        elif pg.is_visible("#t-lay3"):
            tap(pg, "#t-lay3", phone)
        pg.wait_for_timeout(400)
    return pg.is_visible(sel)


def run_page(b, d: Path, phone: bool, errs, shots):
    key = KEY[d.name]; own = key.startswith("own")
    rep = json.loads((REPO / "data/derived/Q295_page_report.json").read_text())[key]
    fr = json.loads((REPO / "data/derived/Q295_fat_report.json").read_text())["pages"][key]
    html = V.html_of(d); srv, port = V.serve(d)
    try:
        w, h = (390, 844) if phone else (1400, 900)
        T = f"{key}_{w}"
        ctx = b.new_context(viewport={"width": w, "height": h}, has_touch=phone, is_mobile=phone, device_scale_factor=1)
        pg = ctx.new_page(); perr = []
        pg.on("pageerror", lambda e: perr.append(str(e)))
        pg.route("**/*", V.route)
        pg.goto(f"http://127.0.0.1:{port}/{html}", wait_until="load", timeout=300000)
        V.ready(pg)
        if not pg.evaluate("() => typeof NMSKCapCore !== 'undefined'"):
            # the page keeps its copy of the cut-face kernel in a closure: load the same file (sync_q227 keeps them byte-identical)
            pg.add_script_tag(content=(REPO / "viewer/cut_cap/cut_cap.js").read_text(encoding="utf-8"))
        cats = api(pg, "api.categories ? api.categories() : null") or pg.evaluate("() => window.NMSKClinicalTool.api.list().reduce((o, r) => (o[r.cat] = (o[r.cat] || 0) + 1, o), {})")
        fat = api(pg, "api.list().filter(r => r.cat === 'fat').map(r => ({i: r.i, id: r.id, name: r.name}))")
        ids = sorted({x["id"] for x in fat})
        check(f"{T}: A fat system with {len(ids)} structures (page report {len(rep['added'])})", ids == sorted(rep["added"]), errs)
        kinds = {k: sum(1 for x in ids if x.startswith(k)) for k in ("fat_subcut_", "fat_deep_", "soft_unlabelled_")}
        check(f"{T}: A subcutaneous / deep fat / unlabelled soft tissue all present {kinds}", all(kinds.values()), errs)
        vis0 = [api(pg, f"api.visible({x['i']})") for x in fat]
        check(f"{T}: A drawn at load ({sum(vis0)} / {len(vis0)})", all(vis0), errs)
        sel = toggle_sel(own)
        ok = reach(pg, sel, phone)
        sl = pg.evaluate("""(own) => { if (!own) { const s = document.querySelector('.layer-row[data-cat="fat"] input[type=range]'); return s ? +s.value : null; }
                          return null; }""", own)
        if not own:
            check(f"{T}: A faint by default (layer opacity {sl} %)", sl == 12, errs)
        check(f"{T}: B the fat system toggle is reachable by {'touch' if phone else 'click'}", ok, errs)
        if ok:
            tap(pg, sel, phone); pg.wait_for_timeout(500)
            off = [api(pg, f"api.visible({x['i']})") for x in fat]
            tap(pg, sel, phone); pg.wait_for_timeout(500)
            on = [api(pg, f"api.visible({x['i']})") for x in fat]
            check(f"{T}: B toggle hides all fat ({sum(off)} left) and shows it again ({sum(on)} / {len(on)})", not any(off) and all(on), errs)
        for reg in ("thigh", "abdomen"):
            ya, yb = fr["regions"][reg]["y_range"] if "y_range" in fr["regions"][reg] else (None, None)
            y = 0.5 * (ya + yb)
            with_fat = pg.evaluate(CAP_JS, [y, True]); no_fat = pg.evaluate(CAP_JS, [y, False])
            check(f"{T}: C axial cut at {reg} y={y:.0f}: the cut-face kernel fills {with_fat['fat_filled']} fat meshes "
                  f"(outline-only {with_fat['fat_outline']}; {with_fat['fat_names'][:3]}); filled section area {with_fat['px_filled']} mm2 with fat vs {no_fat['px_filled']} mm2 without",
                  with_fat["fat_filled"] >= 2 and with_fat["fat_filled"] > with_fat["fat_outline"] and with_fat["px_filled"] > no_fat["px_filled"], errs)
        # the real UI: cut there and press "Fill cross-section"
        ya, yb = fr["regions"]["thigh"]["y_range"]; y = 0.5 * (ya + yb)
        api(pg, f"api.setCut({{normal: [0, -1, 0], point: [0, {y}, 0]}})"); pg.wait_for_timeout(800)
        if reach(pg, "#cut-fill", phone):
            if pg.get_attribute("#cut-fill", "aria-pressed") != "true":
                tap(pg, "#cut-fill", phone)
            pg.wait_for_function("(document.getElementById('cut-capinfo') || {}).textContent.indexOf('filled') >= 0", timeout=60000)
            info = pg.evaluate("() => document.getElementById('cut-capinfo').textContent")
            check(f"{T}: C 'Fill cross-section' at the thigh reports filled structures ({info[:90]})", "filled" in info, errs)
            if shots and not phone and pg.is_visible("#cut-look"):
                tap(pg, "#cut-look", phone); pg.wait_for_timeout(2000)
                pg.screenshot(path=str(shots / f"Q295_cut_thigh_{key}.png"))
        else:
            check(f"{T}: C the cut panel's Fill cross-section is reachable", False, errs)
        api(pg, "api.setCut(null)"); pg.wait_for_timeout(300)
        check(f"{T}: D 0 page errors", not perr, errs)
        if perr:
            print("    ", perr[:3])
        ctx.close()
    finally:
        srv.terminate()


def main():
    dirs = [Path(a) for k, a in enumerate(sys.argv[1:], 1) if not a.startswith("--") and sys.argv[k - 1] != "--shots" and Path(a).is_dir()]
    shots = None; phone_n = 6
    for k, a in enumerate(sys.argv):
        if a == "--shots":
            shots = Path(sys.argv[k + 1]); shots.mkdir(parents=True, exist_ok=True)
        if a.startswith("--phone="):
            phone_n = int(a.split("=")[1])
    errs = []
    with sync_playwright() as pl:
        b = pl.chromium.launch(args=V.LAUNCH_ARGS, executable_path="/opt/pw-browsers/chromium")
        for n, d in enumerate(dirs):
            run_page(b, d, False, errs, shots)
            if n < phone_n:
                run_page(b, d, True, errs, shots)
        b.close()
    print("ALL OK" if not errs else f"{len(errs)} FAIL")
    return 1 if errs else 0


if __name__ == "__main__":
    raise SystemExit(main())
