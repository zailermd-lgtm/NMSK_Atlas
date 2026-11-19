#!/usr/bin/env python3
"""Q347: the injection guide in the injection-planning mode (private add-on), checked in headless Chromium on a built page.

  * for biceps brachii, flexor carpi radialis, gastrocnemius and latissimus dorsi (a muscle with an unplaced band): the Guide
    section shows the private json's values exactly (points, sites, scan start, manoeuvre, at risk, citation + DOI); one row per
    IZ band of the public sidecar, its placement state as the sidecar's, "Use site" only on placed bands, the reason on the others;
  * "Use site N" puts the target on the band's centroid (within 0.5 mm) and inside the muscle; the at-risk rows' distances equal
    the corridor measurement (target point, then a suggested entry's path); "Highlight" marks the mapped structures;
  * a joint posed 60 deg: the target rides its muscle (same surface distance, still inside) and the rows equal the corridor
    re-measured after the burst; back at rest the target and the corridor are identical;
  * a muscle the guide does not cover shows no Guide section; the needle panel shows the same section (English);
  * desktop: "Show on the model" (great toe) and "Start scan here" (medial malleolus) on flexor hallucis longus;
  * phone: the Guide is one line (closed), the step sheet leaves >= 50 % of the model visible;
  * no raw ids / developer strings, contrast >= 4.5:1 (the Q344 audit); no page errors.

    python3 scripts/anatomy/q347/verify_injection_guide_q347.py <page dir> [--size 1400x900]
"""
from __future__ import annotations

import argparse
import socket
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "q344"))
import verify_clinical_ui_q344 as q344  # noqa: E402  (the Q344 readability audit: raw ids, contrast, unit order)

ARGS = ["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]
CASES = [("biceps_brachii", "elbow_r", "flex"), ("flexor_carpi_radialis", "elbow_r", "flex"),
         ("gastrocnemius", "knee_r", "flex"), ("latissimus_dorsi", "shoulder_r", "abd")]
NOT_IN_GUIDE = ["supraspinatus_r", "infraspinatus_r", "gluteus_maximus_r"]   # the first that exists and the guide does not cover

HELPERS = r"""() => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const T = window.NMSKClinicalTool, S = () => T.guide.side, G = () => T.guide.data;
  const box = key => document.querySelector('.mc-guide[data-guide="' + key + '"]');
  async function pick(id) {
    if (!document.querySelector('.mc-pick')) { const b = document.querySelector('.mb-chip .mb-mini'); if (b) b.click(); await sleep(250); }
    const inp = document.querySelector('.mc-pick .mc-search'); if (!inp) return false;
    inp.value = id; inp.dispatchEvent(new Event('input')); await sleep(150);
    const rows = Array.from(document.querySelectorAll('.mc-pick .mc-res button'));
    const row = rows[0]; if (!row) return false;
    row.click(); await sleep(1000); return true;
  }
  function rightId(key) { return S().muscles[key].structures.find(x => /_r$/.test(x) && T.byId[x]); }
  function surf(i, p) { const g = T.geom(i); return g ? window.NMSKClinical.pure.poseAnchor(g.pos, g.idx, p, null).d : 1e9; }
  function riskCmp(key) {
    const c = T.corridor(), b = box(key); if (!b) return null;
    return Array.from(b.querySelectorAll('.g-rrow[data-g-ids]')).map(r => {
      const ids = r.dataset.gIds.split(' '), ds = c.items.filter(it => ids.includes(it.id)).map(it => it.d_mm), exp = ds.length ? Math.min(...ds) : null;
      const got = r.dataset.gD === '' ? null : +r.dataset.gD, txt = r.querySelector('.g-d').textContent;
      const ok = exp == null ? got == null : (got != null && Math.abs(got - exp) < 0.0015 && txt.indexOf((Math.round(exp * 10) / 10).toFixed(1)) >= 0);
      return {ids: ids.join(' '), exp, got, txt, ok};
    });
  }
  async function corrSettled(seq0) { for (let k = 0; k < 60; k++) { await sleep(100); if (T.corridor().seq > seq0 && !T.corr.timer) return true; } return false; }
  window.__q347 = {sleep, pick, rightId, box, surf, riskCmp, corrSettled};
  return !!T;
}"""

CASE = r"""async ([key, joint, dof]) => {
  const H = window.__q347, T = window.NMSKClinicalTool, PZ = window.__poseApi, S = T.guide.side, G = T.guide.data, sleep = H.sleep;
  const sid = H.rightId(key); if (!sid) return {key, err: 'no right-side structure on this page'};
  if (!(await H.pick(sid))) return {key, err: 'target picker failed'};
  const rec = T.recs[T.plan.i]; const o = {key, sid, picked: rec ? rec.id : null};
  let b = H.box(key); o.shown = !!b; if (!b) return o;
  if (!b.open) { b.open = true; await sleep(80); }
  const m = G.muscles[key], s = v => v == null ? null : String(v), tx = sel => { const e = H.box(key).querySelector(sel); return e ? e.textContent : null; };
  o.vals = {points: [tx('[data-g=points] bdi'), s(m.injection_points)], sites: [tx('[data-g=sites] bdi'), s(m.sites)], scan: [tx('[data-g=scan] bdi'), s(m.scan_start)],
            manoeuvre: [tx('[data-g=manoeuvre] bdi'), s(m.manoeuvre)], at_risk: [tx('[data-g=risk] bdi'), s(m.at_risk)],
            cite: [(H.box(key).querySelectorAll('[data-g=cite] bdi')[1] || {}).textContent, s(m.cite)],
            doi: [(H.box(key).querySelector('a[href*="doi.org"]') || {}).href || '', 'https://doi.org/' + G.source.doi]};
  o.conflict = m.conflict ? [tx('[data-g=conflict]') || '', m.conflict.adopted, m.conflict.other] : null;
  const iz = S.muscles[key].iz, bands = S.bands.filter(x => x.m === key && x.s === 'r');
  const els = Array.from(H.box(key).querySelectorAll('.g-site'));
  o.sites = els.map((e, n) => { const bd = bands.find(x => x.iz === n), L = S.lines[iz[n].line] || {};
    return {n: n + 1, st: e.dataset.gSt, want: bd ? bd.st : 'none', btn: !!e.querySelector('[data-g-use]'), pct: iz[n].pct == null || e.textContent.indexOf(iz[n].pct + '%') >= 0,
            line: !L.label || e.textContent.indexOf(L.label) >= 0, reason: bd && bd.st === 'failed' ? e.textContent.indexOf(bd.reason.slice(0, 40)) >= 0 : true}; });
  o.nIz = iz.length;
  o.use = [];
  for (let n = 0; n < iz.length; n++) {
    const bd = bands.find(x => x.iz === n); if (!bd || bd.st !== 'placed') continue;
    const btn = H.box(key).querySelector('[data-g-use="' + (n + 1) + '"]'); if (!btn) { o.use.push({n: n + 1, err: 'no button'}); continue; }
    btn.click(); await sleep(450);
    const p = T.target.p, d = Math.hypot(p[0] - bd.dot[0], p[1] - bd.dot[1], p[2] - bd.dot[2]);
    const wh = H.box(key).querySelector('[data-g-site="' + (n + 1) + '"] [data-g-where]');
    o.use.push({n: n + 1, d, inside: (T.byId[sid] || []).some(i => T.insideMesh(i, p)), surf: H.surf(T.target.i, p), where: wh ? wh.dataset.gWhere : null, whereTxt: wh ? wh.textContent : '', pressed: (H.box(key).querySelector('[data-g-use="' + (n + 1) + '"]') || {}).getAttribute ? H.box(key).querySelector('[data-g-use="' + (n + 1) + '"]').getAttribute('aria-pressed') : null});
  }
  if (!T.target) return o;
  // risk rows vs the corridor: target point, then a path from a suggested entry
  await H.corrSettled(-1); await sleep(200);
  o.riskT = H.riskCmp(key);
  const seqA = T.corridor().seq;
  const pr = document.querySelector('.mc-primary'); if (pr && !pr.disabled) pr.click();
  for (let k = 0; k < 80 && !T.sugg.shown.length && !T.sugg.msg; k++) await sleep(100);
  o.sugg = T.sugg.shown.length;
  if (T.sugg.shown.length) { T.adoptSuggestion(T.sugg.shown[0]); T.notify(); await H.corrSettled(seqA); await sleep(250); }
  o.path = !!T.entry;
  o.riskP = H.riskCmp(key);
  // highlight
  const hb = H.box(key).querySelector('[data-g-risk-on]');
  if (hb) {
    hb.click(); await sleep(500);
    const hl = T.guide.hl, marks = (T.api.selection() && T.api.selection().state().marks) || [];
    const ids = hl ? Object.keys(hl.set).map(i => T.recs[+i].id) : [];
    o.hl = {n: hl ? hl.n : 0, marked: ids.every(id => marks.indexOf(id) >= 0), pressed: (H.box(key).querySelector('[data-g-risk-on]') || {}).getAttribute('aria-pressed')};
    H.box(key).querySelector('[data-g-risk-on]').click(); await sleep(400);
    o.hl.off = !T.guide.hl;
  }
  // pose 60 deg and back
  const moved = new Set(), on = e => ((e.detail && e.detail.ids) || []).forEach(i => moved.add(i));
  window.addEventListener('nmsk-pose-rev', on);
  const t0 = T.target.p.slice(), e0 = T.entry ? T.entry.p.slice() : null, ti = T.target.i, d0 = H.surf(ti, t0);
  const c0 = T.corridor().items.map(x => x.id + ':' + x.d_mm).join('|');
  const seq0 = T.corridor().seq;
  PZ.set(joint, dof, 60); await sleep(400); await H.corrSettled(seq0); await sleep(300);
  const t1 = T.target.p.slice();
  o.pose = {joint, moved: moved.has(ti), dist: Math.hypot(t1[0] - t0[0], t1[1] - t0[1], t1[2] - t0[2]), dSurf: Math.abs(H.surf(ti, t1) - d0),
            inside: (T.byId[sid] || []).some(i => T.insideMesh(i, t1)), seq: T.corridor().seq > seq0, rows: H.riskCmp(key), away: T.poseAway()};
  const seq1 = T.corridor().seq;
  PZ.reset(); await sleep(400); await H.corrSettled(seq1); await sleep(300);
  window.removeEventListener('nmsk-pose-rev', on);
  o.back = {target: T.target.p.every((v, k) => v === t0[k]), entry: !e0 || T.entry.p.every((v, k) => v === e0[k]),
            corr: T.corridor().items.map(x => x.id + ':' + x.d_mm).join('|') === c0, rows: H.riskCmp(key), rest: PZ.isRest()};
  return o;
}"""

FHL = r"""async () => {
  const H = window.__q347, T = window.NMSKClinicalTool, PZ = window.__poseApi, U = window.NMSKUltrasound, HI = window.NMSKHistory, sleep = H.sleep, key = 'flexor_hallucis_longus';
  const sid = H.rightId(key); if (!sid) return {err: 'no flexor hallucis longus'};
  await H.pick(sid); const b = H.box(key); if (!b) return {err: 'no guide section'};
  if (!b.open) b.open = true;
  const u = b.querySelector('[data-g-use="1"]'); if (u) { u.click(); await sleep(600); }
  const o = {};
  // "Show on the model": once from rest, once from a pose the user set (knee 30 deg)
  async function show(label) {
    const sh = H.box(key) && H.box(key).querySelector('[data-g-show]'); if (!sh || !T.target) return {label, err: 'no button / target'};
    if (HI && HI.commit) HI.commit();
    const P0 = JSON.stringify(PZ.pose()), t0 = T.target.p.slice(), len0 = HI ? HI.state().len : null;
    const moved = new Set(), on = e => ((e.detail && e.detail.ids) || []).forEach(i => moved.add(i)); window.addEventListener('nmsk-pose-rev', on);
    sh.click(); await sleep(300); const busy0 = T.guide.busy;
    for (let k = 0; k < 200 && T.guide.busy; k++) await sleep(100);
    await sleep(1200); window.removeEventListener('nmsk-pose-rev', on);
    const pushed = HI && HI.commit ? HI.commit() : false;
    return {label, busy0, moved: moved.size, done: !T.guide.busy, pose: JSON.stringify(PZ.pose()) === P0, target: T.target.p.every((v, k) => v === t0[k]),
            hist: HI ? [len0, HI.state().len, pushed] : null};
  }
  o.show = [await show('from rest')];
  PZ.set('knee_r', 'flex', 30); await sleep(1200); if (HI && HI.commit) HI.commit();
  o.show.push(await show('from a pose (knee 30)'));
  // "Start scan here": at rest and posed (knee 30, the tibia moves): the probe goes on the skin over the (posed) landmark
  async function scan(label) {
    const sc = H.box(key).querySelector('[data-g-scan="0"]'); if (!sc || !U) return {label, err: 'no button'};
    const g = T.guide.data.muscles[key].scan[0], bi = T.byId[g.bone + '_r'][0], w = {p: g.r.slice(), i: bi, n: null};
    if (!PZ.isRest()) { T.anchorPoint(w, bi, true); T.ridePoint(w); }
    Object.keys(T.guide.msg).forEach(k => delete T.guide.msg[k]); T.notify(); await sleep(100);
    const sc2 = H.box(key).querySelector('[data-g-scan="0"]'); sc2.click();
    for (let k = 0; k < 400 && !(H.box(key).querySelector('[data-g=scan-msg]')); k++) await sleep(100);
    const st = U.state();
    return {label, msg: (H.box(key).querySelector('[data-g=scan-msg]') || {}).textContent || '', ref: st.refKey,
            d: st.P ? Math.hypot(st.P[0] - w.p[0], st.P[1] - w.p[1], st.P[2] - w.p[2]) : null, lm: w.p.map(x => +x.toFixed(1))};
  }
  o.scan = [await scan('posed (knee 30)')];
  U.close(); await sleep(400); PZ.reset(); await sleep(1200);
  o.scan.push(await scan('rest'));
  U.close(); await sleep(400);
  return o;
}"""

MEDIAN = r"""async () => {
  const H = window.__q347, T = window.NMSKClinicalTool, out = [];
  for (const key of ['brachialis', 'pronator_teres', 'flexor_digitorum_superficialis']) {
    const sid = H.rightId(key); if (!sid) continue;
    await H.pick(sid); const b = H.box(key); if (!b) { out.push({key, err: 'no section'}); continue; }
    const v = T.guideView(T.plan.i), med = v.risk.find(r => r.name === 'median nerve');
    const un = Array.from(b.querySelectorAll('[data-g-unmapped]')).map(e => e.dataset.gUnmapped);
    const hb = b.querySelector('[data-g-risk-on]'); let hlIds = [];
    if (hb) { hb.click(); await H.sleep(400); hlIds = T.guide.hl ? Object.keys(T.guide.hl.set).map(i => T.recs[+i].id) : []; H.box(key).querySelector('[data-g-risk-on]').click(); await H.sleep(300); }
    out.push({key, mapped: med ? med.idx.length : -1, listed: un.indexOf('median nerve') >= 0, medianHl: hlIds.filter(id => /median/.test(id)), hl: hlIds.length});
  }
  return out;
}"""

NOT_IN = r"""async (ids) => {
  const H = window.__q347, T = window.NMSKClinicalTool;
  const id = ids.find(x => T.byId[x] && !T.guideKey(T.recs[T.byId[x][0]])); if (!id) return {err: 'no uncovered muscle found'};
  await H.pick(id);
  const g = document.querySelector('.mc-guide'), host = document.querySelector('.mc-guide-host');
  return {id, picked: T.plan.i != null ? T.recs[T.plan.i].id : null, section: !!g, hostHidden: !host || host.hidden};
}"""

PHONE = r"""async () => {
  const H = window.__q347, T = window.NMSKClinicalTool, key = 'biceps_brachii';
  await H.pick(H.rightId(key)); await H.sleep(400);
  const b = H.box(key); if (!b) return {err: 'no guide section'};
  const sh = document.querySelector('.mc-right').getBoundingClientRect(), mm = document.getElementById('mode-main').getBoundingClientRect();
  const sum = b.querySelector('summary').getBoundingClientRect(), br = b.getBoundingClientRect();
  return {open: b.open, sumH: sum.height, boxH: br.height, sheetTop: sh.top, sheetH: sh.height, mainTop: mm.top, mainH: mm.height, H: innerHeight,
          visible: Math.max(0, Math.min(sh.top, mm.bottom) - mm.top) / mm.height};
}"""

PANEL = r"""async () => {
  const H = window.__q347, T = window.NMSKClinicalTool, key = 'biceps_brachii', G = T.guide.data;
  window.NeedlePath.plan(H.rightId(key)); T.toggle(true); T.renderPlanGuide(); await H.sleep(500);
  const g = document.querySelector('#ncl-plan-guide .ncl-guide[data-guide="' + key + '"]');
  const out = {shown: !!g, sites: g ? (g.querySelector('[data-g=sites] bdi') || {}).textContent : null, want: G.muscles[key].sites};
  window.NeedlePath.releasePlan(); T.toggle(false); return out;
}"""


def serve(d):
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close()
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(p), "--bind", "127.0.0.1", "-d", str(d)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    return srv, p


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("build_dir")
    ap.add_argument("--size", default="1400x900")
    a = ap.parse_args()
    d = Path(a.build_dir).resolve()
    W, H = (int(x) for x in a.size.split("x"))
    phone = W <= 500
    srv, port = serve(d)
    errs: list[str] = []
    page_errors: list[str] = []

    def check(label, cond):
        ok = bool(cond)
        print(("  OK   " if ok else "  FAIL ") + label)
        if not ok:
            errs.append(label)

    try:
        with sync_playwright() as pl:
            b = pl.chromium.launch(args=ARGS, executable_path="/opt/pw-browsers/chromium")
            ctx = b.new_context(viewport={"width": W, "height": H}, has_touch=phone, is_mobile=phone, device_scale_factor=1,
                                color_scheme="dark" if phone else "light")
            pg = ctx.new_page()
            pg.on("pageerror", lambda e: page_errors.append(str(e)))
            pg.route("**/*", lambda rq: rq.abort() if "fonts.g" in rq.request.url else rq.continue_())
            print(f"=== {d.name} @ {W}x{H} ===")
            pg.goto(f"http://127.0.0.1:{port}/index.html", wait_until="load", timeout=180000)
            pg.wait_for_function("window.NMSKUltrasound && window.NMSKClinicalTool && window.NMSKModes && window.__poseApi && window.__poseApi.ready()", timeout=180000)
            pg.wait_for_function("window.NMSKClinicalTool.guide && window.NMSKClinicalTool.guide.data && window.NMSKClinicalTool.guide.side", timeout=60000)
            pg.wait_for_timeout(1500)
            pg.evaluate("() => { const c = document.getElementById('mw-close'); if (c) c.click(); }")
            check("helpers installed", pg.evaluate(HELPERS))
            pg.evaluate("() => window.NMSKModes.enter('inj')")
            pg.wait_for_timeout(1800)

            if phone:
                r = pg.evaluate(PHONE)
                if r.get("err"):
                    check("phone: " + r["err"], False)
                else:
                    print(f"     phone: guide open={r['open']} summary {r['sumH']:.0f} px, box {r['boxH']:.0f} px; sheet top {r['sheetTop']:.0f} / main {r['mainTop']:.0f}+{r['mainH']:.0f}")
                    check("phone: the Guide starts closed, one line", not r["open"] and r["sumH"] <= 30 and r["boxH"] <= 50)
                    check(f"phone: the step sheet leaves >= 50 % of the model visible ({r['visible'] * 100:.0f} %)", r["visible"] >= 0.5)
                    q344.audit_state(pg, "phone: injection mode with the Guide closed", ["#mode-shell"], check, None)
                    pg.evaluate("() => { const g = document.querySelector('.mc-guide'); if (g) g.open = true; }")
                    q344.audit_state(pg, "phone: injection mode with the Guide open", ["#mode-shell"], check, None)
                    pg.evaluate("() => { const g = document.querySelector('.mc-guide'); if (g) g.open = false; }")

            for key, joint, dof in CASES:
                r = pg.evaluate(CASE, [key, joint, dof])
                print(f"  -- {key} ({r.get('sid')})")
                if r.get("err"):
                    check(f"{key}: {r['err']}", False)
                    continue
                check(f"{key}: Guide section shown for the picked target ({r['picked']})", r["shown"] and r["picked"] == r["sid"])
                if not r["shown"]:
                    continue
                for k, (got, want) in r["vals"].items():
                    check(f"{key}: {k} shown exactly as the json ({want!r})", got == want)
                if r["conflict"]:
                    t, ad, ot = r["conflict"]
                    check(f"{key}: table/text conflict: adopted and other shown", ad in t and ot in t)
                st = r["sites"]
                check(f"{key}: one row per IZ band ({len(st)} of {r['nIz']})", len(st) == r["nIz"])
                check(f"{key}: each site's placement as the sidecar's ({[s['st'] for s in st]})", all(s["st"] == s["want"] for s in st))
                check(f"{key}: 'Use site' only on placed bands", all(s["btn"] == (s["want"] == "placed") for s in st))
                check(f"{key}: each site shows its % and line; unplaced ones their reason", all(s["pct"] and s["line"] and s["reason"] for s in st))
                for u in r["use"]:
                    if u.get("err"):
                        check(f"{key}: site {u['n']}: {u['err']}", False)
                        continue
                    where = "inside the muscle" if u["inside"] else f"{u['surf']:.2f} mm outside its surface"
                    check(f"{key}: Use site {u['n']} -> target {u['d']:.3f} mm from the band centroid, {where} (said: {u['whereTxt']!r}), button pressed",
                          u["d"] <= 0.5 and u["pressed"] == "true" and ((u["inside"] and u["where"] == "in") or (not u["inside"] and u["surf"] <= 0.5 and u["where"] == "surface")))
                for lab, rows in (("target point", r.get("riskT")), ("suggested path" if r.get("path") else "path (no suggestion)", r.get("riskP"))):
                    if rows is None:
                        continue
                    check(f"{key}: at-risk distances = corridor measurement, {lab} ({[x['txt'] for x in rows]})", all(x["ok"] for x in rows))
                if r.get("hl"):
                    h = r["hl"]
                    check(f"{key}: Highlight marks the mapped structures ({h['n']} pieces) and turns off again", h["n"] > 0 and h["marked"] and h["pressed"] == "true" and h["off"])
                p, bk = r["pose"], r["back"]
                if p["moved"]:
                    check(f"{key}: {p['joint']} 60 deg: the target rides its muscle ({p['dist']:.1f} mm, surface distance change {p['dSurf']:.3f} mm, inside)",
                          p["dSurf"] < 0.5 and p["inside"] and p["away"])
                else:
                    check(f"{key}: {p['joint']} 60 deg does not move this muscle: the target stays", p["dist"] == 0)
                check(f"{key}: posed: the rows equal the corridor re-measured after the burst", p["seq"] and all(x["ok"] for x in p["rows"]))
                check(f"{key}: back at rest: target, entry and corridor identical, rows equal", bk["rest"] and bk["target"] and bk["entry"] and bk["corr"] and all(x["ok"] for x in bk["rows"]))

            r = pg.evaluate(NOT_IN, NOT_IN_GUIDE)
            if r.get("err"):
                check(r["err"], False)
            else:
                check(f"a muscle the guide does not cover ({r['id']}) shows no Guide section", r["picked"] == r["id"] and not r["section"] and r["hostHidden"])

            if not phone:
                pg.evaluate("async () => { await window.__q347.pick(window.__q347.rightId('biceps_brachii')); const b = window.__q347.box('biceps_brachii'); if (b) b.open = true; }")
                pg.wait_for_timeout(600)
                q344.audit_state(pg, "desktop: injection mode with the Guide open (biceps)", ["#mode-shell"], check, None)
                r = pg.evaluate(FHL)
                if r.get("err"):
                    check("flexor hallucis longus: " + r["err"], False)
                else:
                    for x in r["show"]:
                        if x.get("err"):
                            check(f"FHL show ({x['label']}): {x['err']}", False)
                            continue
                        check(f"FHL: 'Show on the model' {x['label']}: the toe moves ({x['moved']} structures), it ends, the pose is exactly the one before, target identical, no Undo entry (history {x['hist']})",
                              x["busy0"] and x["moved"] > 0 and x["done"] and x["pose"] and x["target"] and (x["hist"] is None or (x["hist"][0] == x["hist"][1] and not x["hist"][2])))
                    for x in r["scan"]:
                        if x.get("err"):
                            check(f"FHL scan ({x['label']}): {x['err']}", False)
                            continue
                        print(f"     scan start ({x['label']}): {x}")
                        check(f"FHL: 'Start scan here' {x['label']}: the probe sits on the skin over the medial malleolus ({x['d'] if x['d'] is None else round(x['d'], 1)} mm < 25), transverse",
                              x["d"] is not None and x["d"] < 25 and x["ref"] == "trans")
                for x in pg.evaluate(MEDIAN):
                    if x.get("err"):
                        check(f"{x['key']}: {x['err']}", False)
                        continue
                    check(f"{x['key']}: 'median nerve' listed as no matching structure, nothing mapped, no median branch highlighted ({x['hl']} pieces highlighted)",
                          x["mapped"] == 0 and x["listed"] and not x["medianHl"])
                pg.evaluate("() => window.NMSKModes.exit()")
                pg.wait_for_timeout(1500)
                r = pg.evaluate(PANEL)
                check(f"needle panel: the planned muscle's Guide (English) with the same sites ({r['sites']!r})", r["shown"] and r["sites"] == r["want"])
            else:
                pg.evaluate("() => window.NMSKModes.exit()")
                pg.wait_for_timeout(800)
            b.close()
    finally:
        srv.terminate()

    check(f"no page errors ({len(page_errors)})", not page_errors)
    for e in page_errors[:5]:
        print("     page error: " + e[:300])
    print()
    if errs:
        print(f"Q347_GUIDE_FAIL {len(errs)}")
        return 1
    print("Q347_GUIDE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
