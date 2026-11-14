#!/usr/bin/env python3
"""Q318: the control row really IS the top row, and nothing it replaced is still drawn.

Owner: "the SEARCH, SYSTEMS and so on row is supposed to replace the whole top row of HUB, mode,
SOURCES and so on" and "POSE -- if there is only one tile that opens and it then opens the window
that matters, do that at once and skip the pointless step in between."

Run in headless Chromium against a built page. What is asked of the layout:

  * the bar sits at the top of the view, not the bottom, and an opened group unfolds below it;
  * the corner it replaced is gone, and the page title is no longer under it;
  * every entry the owner named is on the bar, and pressing Pose opens the pose panel at once;
  * the slice stack still rebuilds -- the poll must not be able to starve it.

    python3 scripts/anatomy/q318/verify_toprow_q318.py build/q309/viewer_zan_atlas
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
ARGS = ["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]
WANT = ["mark", "systems", "cut", "imaging", "pose", "measure", "needle", "favorites", "ref", "page", "view"]


def serve(d):
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close()
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(p), "--bind", "127.0.0.1", "-d", str(d)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1); return srv, p


def route(rq):
    u = rq.request.url
    if "three" in u and u.endswith(".js") and ("cdnjs" in u or "jsdelivr" in u or "unpkg" in u):
        rq.fulfill(body=open(THREE, "rb").read(), content_type="application/javascript")
    elif "fonts.g" in u:
        rq.abort()
    else:
        rq.continue_()


def check(label, cond, errs):
    ok = bool(cond)
    print(("  OK  " if ok else "  FAIL") + " " + label)
    if not ok:
        errs.append(label)
    return ok


LAYOUT = """() => {
  const bar = document.getElementById('q301-bar');
  if (!bar) return {err: 'the control bar is not on this page'};
  const r = bar.getBoundingClientRect();
  const stage = document.getElementById('viewer') || document.getElementById('c') || document.body;
  const sr = stage.getBoundingClientRect();
  const keys = [].slice.call(bar.querySelectorAll('.qg-g')).map(b => (b.id || '').replace(/^qg-/, ''));
  const vis = el => { if (!el) return false; const s = getComputedStyle(el);
    if (s.display === 'none' || s.visibility === 'hidden' || +s.opacity === 0) return false;
    const q = el.getBoundingClientRect(); return q.width > 1 && q.height > 1; };
  const br = document.getElementById('brand');
  const brr = br && vis(br) ? br.getBoundingClientRect() : null;
  // whatever the bar now lies on top of: the thing the owner asked it to REPLACE must not still be drawn
  const over = [];
  document.querySelectorAll('body *').forEach(e => {
    if (e.closest('#q301-bar') || e.closest('#q301-sheet') || e.closest('#q301-park')) return;
    if (!vis(e)) return;
    const q = e.getBoundingClientRect();
    if (q.right < r.left + 4 || q.left > r.right - 4 || q.bottom < r.top + 4 || q.top > r.bottom - 4) return;
    if (q.height > 400 || q.width > 1.5 * r.width) return;      // the stage and the page itself are underneath everything
    over.push(e.tagName + '#' + (e.id || '') + '.' + String(e.className || '').slice(0, 24));
  });
  const park = document.getElementById('q301-park');
  return {
    keys: keys, barTop: r.top, barBottom: r.bottom, stageTop: sr.top, stageH: sr.height, over: over.slice(0, 12),
    brandVisible: !!brr, brandTop: brr ? brr.top : null,
    lift: getComputedStyle(document.documentElement).getPropertyValue('--q301-bar-h').trim(),
    parked: park ? park.children.length : 0,
    // every button a group claims must be reachable exactly once -- adoption MOVES the node, it never copies it;
    // a page that never had one at all (the two engines differ) reports 0 and is not held to it
    dupes: ['t-mode', 't-hub', 'about-btn', 'btn-pose', 't-needle', 't-imaging', 't-reference', 't-ultrasound']
      .map(id => [id, document.querySelectorAll('#' + id).length])
  };
}"""

POSE = """async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const g = document.getElementById('qg-pose');
  if (!g) return {err: 'no Pose entry on the bar'};
  g.click();
  await sleep(500);
  const sheet = document.getElementById('q301-sheet');
  const panel = document.getElementById('pose-panel');
  const vis = el => { if (!el) return false; const s = getComputedStyle(el);
    if (el.hidden || s.display === 'none' || s.visibility === 'hidden') return false;
    const q = el.getBoundingClientRect(); return q.width > 1 && q.height > 1; };
  return {sheetOpen: !!(sheet && !sheet.hidden && vis(sheet)), panelOpen: vis(panel),
          panelId: panel ? panel.id : null};
}"""

SLICES = """async () => {
  const C = window.xsecCtl;
  if (!C) return {err: 'the cross-section controller is not on this page'};
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const t = document.getElementById('t-cut');            // the stack slices along the Cut plane, so that goes on first
  if (!t) return {err: 'the Cut tool is not on this page'};
  t.click(); await sleep(1200);
  C.set(true); await sleep(700);
  const a = C.state();
  await sleep(2500);                                     // the render loop polls itemsChanged() throughout this
  const b = C.state();
  return {first: {builds: a.builds, slots: a.slots, msg: a.msg},
          later: {builds: b.builds, slots: b.slots, msg: b.msg, planes: b.planes.length}};
}"""


def main() -> int:
    d = Path(sys.argv[1]) if len(sys.argv) > 1 else REPO / "build" / "q309" / "viewer_zan_atlas"
    if not d.is_absolute():
        d = REPO / d
    srv, port = serve(d)
    errs: list[str] = []
    try:
        with sync_playwright() as pl:
            b = pl.chromium.launch(args=ARGS, executable_path="/opt/pw-browsers/chromium")
            pg = b.new_page(viewport={"width": 1400, "height": 950})
            pg.on("pageerror", lambda e: errs.append("page error: " + str(e)))
            pg.route("**/*", route)
            html = sorted(d.glob("atlas_viewer*.html"))
            print(f"=== {d.name} ===")
            pg.goto(f"http://127.0.0.1:{port}/{html[0].name if html else 'index.html'}",
                    wait_until="load", timeout=90000)
            pg.wait_for_function("window.NMSKQ301", timeout=90000)
            pg.wait_for_timeout(2500)
            t = pg.query_selector('.mw-tile[data-mode="anat"]')
            if t:
                t.click(); pg.wait_for_timeout(2500)

            L = pg.evaluate(LAYOUT)
            if L.get("err"):
                print("  FAIL " + L["err"]); return 1
            print(f"     entries: {L['keys']}")
            print(f"     bar {L['barTop']:.0f}..{L['barBottom']:.0f} of a {L['stageH']:.0f} px view; "
                  f"lift {L['lift']!r}; title {L['brandTop']}")
            missing = [k for k in WANT if k not in (L["keys"] or [])]
            check(f"every entry the owner named is on the bar (missing: {missing})", not missing, errs)
            check("the bar is in the top third of the view, not the bottom",
                  L["barTop"] < L["stageTop"] + L["stageH"] / 3, errs)
            check(f"nothing the row replaced is still drawn under it ({L['over']})", not L["over"], errs)
            check(f"the buttons the entries claim were taken out of the engine's own bars ({L['parked']} of them)",
                  L["parked"] >= 20, errs)
            if L["brandVisible"]:
                check("the page title is out of the bar's row",
                      L["brandTop"] is not None and L["brandTop"] > L["barBottom"], errs)
            check("nothing anchored to the bottom is lifted any more, since the bar left it",
                  L["lift"] in ("0px", "0"), errs)
            for i, n in L["dupes"]:
                check(f"#{i} exists at most once (adoption moves the node, it does not copy it)", n <= 1, errs)

            P = pg.evaluate(POSE)
            if P.get("err"):
                errs.append(P["err"]); print("  FAIL " + P["err"])
            else:
                check("pressing Pose opens the pose panel", P["panelOpen"], errs)
                check("and does not stop at a sheet holding one button first", not P["sheetOpen"], errs)
            pg.keyboard.press("Escape"); pg.wait_for_timeout(400)

            S = pg.evaluate(SLICES)
            if S.get("err"):
                errs.append(S["err"]); print("  FAIL " + S["err"])
            else:
                a, z = S["first"] or {}, S["later"] or {}
                print(f"     slices: builds {a.get('builds')} -> {z.get('builds')}, "
                      f"slots {z.get('slots')}, planes {z.get('planes')}, msg {str(z.get('msg'))[:70]!r}")
                check("the slice stack rebuilds instead of being starved by the poll",
                      (z.get("builds") or 0) >= 1, errs)
                check("and the poll does not then rebuild it over and over",
                      (z.get("builds") or 0) <= 3, errs)
                check(f"the slices are actually there ({z.get('slots')} faces, {z.get('planes')} planes)",
                      (z.get("slots") or 0) >= 3 and (z.get("planes") or 0) >= 3, errs)
                check(f"and the build reported no error ({z.get('msg')!r})", not z.get("msg"), errs)
            b.close()
    finally:
        srv.terminate()

    print()
    if errs:
        print(f"Q318_TOPROW_FAIL {len(errs)}")
        for e in errs:
            print("  - " + e)
        return 1
    print("Q318_TOPROW_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
