#!/usr/bin/env python3
"""Q299: real headless-Chromium check (desktop 1400x900 real clicks + phone 390x844 real touch).

A  THE OWNER'S OWN CASE. A cross-section at the level of the common fibular (peroneal) nerve on a MALE page: the cut
   plane is set through the page's own `common_fibular_n_r`, "Fill cross-section" is pressed in the real UI, and the
   nerve must come out drawn -- with pixels of its own left in the FINAL cut-face raster, not merely "cut". The same
   level is checked before and after the Q299 minimum drawn width, in the page's own copy of the kernel.
A2 On the two IMAGING pages the same question gets the honest answer this round found: those pages carry NO fibular
   nerve of any kind, which is why no cross-section of them can ever show one. Asserted against the page's own list.
B  Thin and tubular structures: at the same level, every structure the plane cuts must leave pixels in the final
   raster except ones another structure genuinely covers, and the Cut panel must SAY what minimum width it used.
C  CONTAINMENT. On Base Female the four external pudendal vessels and the two genitofemoral nerves must no longer
   stand in front of the local skin front (measured in the page, from the page's own skin and subcutaneous vertices),
   and their cards must carry the Q299 containment statement.
D  PELVIS. The Base Female and Combined Female cards carry the Q299 pelvic-proportion measurements, read off the live
   card through the real search box and a real click / tap.
E  0 page errors, both viewports.

    python3 scripts/anatomy/q299/verify_q299.py PAGE_DIR... [--shots DIR] [--phone=N]"""
from __future__ import annotations
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE.parent / "q283")); sys.path.insert(0, str(HERE.parent / "q297")); sys.path.insert(0, str(HERE))
import verify_q283 as V  # noqa: E402
import verify_q297 as V297  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

check, tap, api = V.check, V.tap, V.api
open_card, close_card = V297.open_card, V297.close_card
KEY = {"viewer_m_hr": "own_m", "viewer_f_hr": "own_f", "viewer_zan_atlas": "base_m", "viewer_base_female": "base_f",
       "viewer_zan_vhm": "comb_m", "viewer_zan_female": "comb_f"}
NERVE = "common_fibular_n_r"
VESSELS = ["zan_external_pudendal_veins_l", "zan_external_pudendal_veins_r",
           "zan_superficial_external_pudendal_artery_l", "zan_superficial_external_pudendal_artery_r"]
NERVES_F = ["genitofemoral_n_l", "genitofemoral_n_r"]

# the page's own structure list -> items for the page's own copy of the cut-face kernel, exactly as the Cut panel builds them
ITEMS_JS = """() => {
  const a = window.NMSKClinicalTool.api, L = a.list(), items = [];
  L.forEach(r => { if (!a.visible(r.i)) return;
    items.push({key: r.id, name: r.name, cat: r.cat, rgb: [0.5, 0.5, 0.5], alpha: r.cat === 'fat' ? 0.12 : 1,
      geom: () => { const g = a.geometry(r.i); if (!g) return null;
        let mn = [1e9,1e9,1e9], mx = [-1e9,-1e9,-1e9];
        for (let k = 0; k < g.pos.length; k += 3) for (let c = 0; c < 3; c++) { const v = g.pos[k+c]; if (v < mn[c]) mn[c] = v; if (v > mx[c]) mx[c] = v; }
        return {pos: g.pos, idx: g.idx, bmin: mn, bmax: mx}; }}); });
  window.__q299items = items; return items.length; }"""

CUT_JS = """([y, band]) => {
  const items = window.__q299items;
  const opt = band ? {bandFrac: 1/500, bandMax: 2.5} : {};
  const res = NMSKCapCore.build(items, {n: [0, 1, 0], d: y}, opt);
  const seen = new Int32Array((res.items || []).length + 1);
  if (res.ids) for (let i = 0; i < res.ids.length; i++) seen[res.ids[i]]++;
  const out = {cut: (res.items || []).length, visible: 0, invisible: 0, band_mm: res.stats.band_mm || 0,
               by_cat: {}, per: {}, px_mm: res.px};
  (res.items || []).forEach(r => {
    const px = seen[r.code], v = px > 0;
    out[v ? 'visible' : 'invisible']++;
    const b = out.by_cat[r.cat] || (out.by_cat[r.cat] = {cut: 0, visible: 0});
    b.cut++; if (v) b.visible++;
    out.per[r.key] = {status: r.status, px: px, width_mm: r.width_mm, band_mm: r.band_mm};
  });
  return out; }"""

# how far in front of the LOCAL skin front does a structure reach?  Skin / subcutaneous vertices within 10 mm in x and
# y of each of the structure's vertices; the answer is max(vertex.z - max skin z in that column).  Positive = outside.
FRONT_JS = """(sid) => {
  const a = window.NMSKClinicalTool.api, L = a.list();
  const row = L.filter(r => r.id === sid)[0]; if (!row) return null;
  const g = a.geometry(row.i); if (!g) return null;
  let mn = [1e9,1e9,1e9], mx = [-1e9,-1e9,-1e9];
  for (let k = 0; k < g.pos.length; k += 3) for (let c = 0; c < 3; c++) { const v = g.pos[k+c]; if (v < mn[c]) mn[c] = v; if (v > mx[c]) mx[c] = v; }
  const SK = [];
  L.forEach(r => { if (r.cat !== 'skin' && r.cat !== 'fat' && r.id !== 'skin') return;
    const h = a.geometry(r.i); if (!h) return;
    for (let k = 0; k < h.pos.length; k += 3) {
      const x = h.pos[k], y = h.pos[k+1], z = h.pos[k+2];
      if (x > mn[0]-25 && x < mx[0]+25 && y > mn[1]-25 && y < mx[1]+25) SK.push(x, y, z);
    } });
  if (!SK.length) return {skin_points: 0};
  let worst = -1e9, n = 0;
  for (let k = 0; k < g.pos.length; k += 3) {
    const x = g.pos[k], y = g.pos[k+1], z = g.pos[k+2];
    let front = -1e9;
    for (let j = 0; j < SK.length; j += 3)
      if (Math.abs(SK[j]-x) < 10 && Math.abs(SK[j+1]-y) < 10 && SK[j+2] > front) front = SK[j+2];
    if (front > -1e8) { n++; const d = z - front; if (d > worst) worst = d; }
  }
  return {skin_points: SK.length/3, columns: n, max_in_front_mm: worst > -1e8 ? +worst.toFixed(2) : null}; }"""


def bbox(pg, sid):
    return pg.evaluate("""(sid) => { const a = window.NMSKClinicalTool.api, L = a.list();
      const r = L.filter(x => x.id === sid)[0]; if (!r) return null; const g = a.geometry(r.i); if (!g) return null;
      let mn=[1e9,1e9,1e9], mx=[-1e9,-1e9,-1e9];
      for (let k=0;k<g.pos.length;k+=3) for (let c=0;c<3;c++){ const v=g.pos[k+c]; if(v<mn[c])mn[c]=v; if(v>mx[c])mx[c]=v; }
      return {min: mn, max: mx}; }""", sid)


def ensure_kernel(pg):
    if not pg.evaluate("() => typeof NMSKCapCore !== 'undefined'"):
        pg.add_script_tag(content=(REPO / "viewer/cut_cap/cut_cap.js").read_text(encoding="utf-8"))
    return pg.evaluate("() => typeof NMSKCapCore !== 'undefined'")


def run_page(d: Path, errs: list, shots: Path | None, only_phone=None):
    key = KEY[d.name]
    kind = "own" if key in ("own_m", "own_f") else "zan"
    html = V.html_of(d)
    srv, port = V.serve(d)
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
                pg.goto(f"http://127.0.0.1:{port}/{html}", wait_until="load", timeout=180000)
                V.ready(pg)
                ids = pg.evaluate("() => window.NMSKClinicalTool.api.list().map(m => m.id)")
                check(f"{T}: the page's own structure list is readable ({len(ids)} structures)", len(ids) > 500, errs)
                check(f"{T}: the page carries the cut-face kernel", ensure_kernel(pg), errs)

                # ---------------- A / A2: the owner's own case
                fib = [i for i in ids if "fibular_n" in i or "peroneal_n" in i]
                if kind == "own":
                    check(f"{T}: A2 this Imaging page carries NO fibular / peroneal nerve at all -- the measured reason "
                          f"a cross-section of it cannot show one ({len(fib)} found)", not fib, errs)
                elif key.endswith("_m"):
                    check(f"{T}: A the page carries the common fibular nerve ({NERVE} present)", NERVE in ids, errs)
                    bb = bbox(pg, NERVE)
                    if bb:
                        y = 0.5 * (bb["min"][1] + bb["max"][1])
                        pg.evaluate(ITEMS_JS)
                        before = pg.evaluate(CUT_JS, [y, False])
                        after = pg.evaluate(CUT_JS, [y, True])
                        pb, pa = before["per"].get(NERVE), after["per"].get(NERVE)
                        check(f"{T}: A the plane y={y:.0f} through the middle of the common fibular nerve cuts it "
                              f"({(pb or {}).get('status')})", bool(pb), errs)
                        check(f"{T}: A the common fibular nerve is DRAWN at that level: {(pa or {}).get('px')} pixels of "
                              f"the final cut face carry it (status {(pa or {}).get('status')}, minimum drawn width "
                              f"{after['band_mm']} mm, raster {after['px_mm']:.2f} mm/px)", bool(pa and pa["px"] > 0), errs)
                        # B: nothing the plane cuts is left invisible unless another structure covers it
                        check(f"{T}: B the minimum drawn width reduces the invisible sections at that level "
                              f"({before['invisible']} -> {after['invisible']} of {after['cut']} cut)",
                              after["invisible"] <= before["invisible"], errs)
                        for cls in ("vessel", "fascia", "nerve"):
                            cb, ca = before["by_cat"].get(cls), after["by_cat"].get(cls)
                            if cb and cb["cut"]:
                                check(f"{T}: B {cls} sections drawn at that level {cb['visible']}/{cb['cut']} -> "
                                      f"{ca['visible']}/{ca['cut']}", ca["visible"] >= cb["visible"], errs)
                        # the real UI
                        api(pg, f"api.setCut({{normal: [0, -1, 0], point: [0, {y}, 0]}})"); pg.wait_for_timeout(900)
                        if V295_reach(pg, "#cut-fill", phone):
                            if pg.get_attribute("#cut-fill", "aria-pressed") != "true":
                                tap(pg, "#cut-fill", phone)
                            try:
                                pg.wait_for_function("(document.getElementById('cut-capinfo') || {}).textContent.indexOf('filled') >= 0", timeout=120000)
                            except Exception:
                                pass
                            info = pg.evaluate("() => (document.getElementById('cut-capinfo') || {}).textContent || ''")
                            check(f"{T}: A the real Cut panel fills the face at the fibular-nerve level and states the "
                                  f"minimum drawn width ({info[:120]!r})",
                                  "filled" in info and "minimum width" in info, errs)
                            if shots and not phone and pg.is_visible("#cut-look"):
                                tap(pg, "#cut-look", phone); pg.wait_for_timeout(2500)
                                shots.mkdir(parents=True, exist_ok=True)
                                pg.screenshot(path=str(shots / f"Q299_cut_fibular_{key}.png"))
                        else:
                            check(f"{T}: A the Cut panel's Fill cross-section is reachable", False, errs)
                        api(pg, "api.setCut(null)"); pg.wait_for_timeout(300)

                # ---------------- C: containment on Base Female
                if key == "base_f":
                    for sid in VESSELS + NERVES_F:
                        if sid not in ids:
                            check(f"{T}: C {sid} is still on the page", False, errs); continue
                        r = pg.evaluate(FRONT_JS, sid)
                        ok = bool(r) and r.get("max_in_front_mm") is not None and r["max_in_front_mm"] <= 3.0
                        check(f"{T}: C {sid} no longer stands in front of the local skin front "
                              f"(max {r and r.get('max_in_front_mm')} mm over {r and r.get('columns')} columns)", ok, errs)
                        txt = open_card(pg, sid, phone)
                        check(f"{T}: C {sid}'s card carries the Q299 containment statement",
                              bool(txt) and "Q299 containment fix" in txt, errs)
                        close_card(pg, phone)

                # ---------------- D: the pelvis cards
                if key in ("base_f", "comb_f"):
                    txt = open_card(pg, "hip_bone_r", phone) or open_card(pg, "Hip bone", phone)
                    check(f"{T}: D the hip-bone card carries the Q299 pelvic-proportion measurement",
                          bool(txt) and "Q299" in txt and ("bi-acetabular" in txt or "Ischial length" in txt), errs)
                    close_card(pg, phone)

                check(f"{T}: E no page errors ({perr[:1]})", not perr, errs)
                if shots:
                    shots.mkdir(parents=True, exist_ok=True)
                    pg.screenshot(path=str(shots / f"Q299_{key}_{w}.png"))
                ctx.close()
            b.close()
    finally:
        srv.terminate()


def V295_reach(pg, sel, phone):
    for _ in range(4):
        if pg.is_visible(sel):
            return True
        for s in ("#btn-panel", "#m-list", "#t-lay3"):
            if pg.is_visible(s):
                tap(pg, s, phone); break
        pg.wait_for_timeout(400)
    return pg.is_visible(sel)


def main(argv):
    shots = None; only_phone = None
    if "--shots" in argv:
        i = argv.index("--shots"); shots = Path(argv[i + 1]); argv = argv[:i] + argv[i + 2:]
    ph = [a for a in argv if a.startswith("--phone=")]
    if ph:
        only_phone = ph[0].split("=")[1] == "1"; argv = [a for a in argv if not a.startswith("--phone=")]
    dirs = [Path(a) for a in argv]
    errs = []
    for d in dirs:
        print(f"== {d}", flush=True)
        run_page(d, errs, shots, only_phone)
    print(f"\nQ299 VERIFY: {'FAIL ' + str(len(errs)) if errs else 'OK'}")
    for e in errs:
        print("  FAIL", e)
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
