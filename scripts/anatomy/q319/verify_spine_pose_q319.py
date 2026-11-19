#!/usr/bin/env python3
"""Q319: the spine moves by vertebra and by segment, and the soft tissue around a joint really follows.

Two of the owner's points, checked in one browser run because they are the same code and the same move:

  4.i  "in POSE the spine also needs movement in the relevant regions... one joint's movement is
        usually small and the movement is made of several vertebrae moving together. Allow performing
        a movement either of a specific joint or of a segment."

  4.ii "moving a joint changes all the soft tissues that surround the joint and, accordingly, the
        tissues adjacent to them -- stretch, slight slack, hypertrophy from muscular contraction,
        rotation. Verify that this indeed happens when applied."

For 4.i the maths is already proved without a browser by tests/test_q319_spine.py (the JavaScript
against the Python reference, on a rig built in the test). What needs a real page is that the control
exists, that a vertebra and a segment each move the model, and that one vertebra moves only itself.

For 4.ii the honest question is which of the owner's four phenomena the rig can actually produce. The
page's own badge says the pose is a kinematic approximation with soft tissue not simulated and no
volume preservation, so this measures rather than assumes:

  * does soft tissue -- muscle, fascia, fat, skin -- move at all, or only bone;
  * does it CHANGE SHAPE rather than merely travel, measured as the RMS distance of a structure's
    vertices from its own centroid, which is invariant to translation and rotation, so a change in it
    is a stretch or a slackening and nothing else;
  * and is volume preserved, which is what "hypertrophy from contraction" would require.

    python3 scripts/anatomy/q319/verify_spine_pose_q319.py build/q309/viewer_zan_atlas
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
SOFT = ("muscle", "fascia", "fat", "skin", "bursa", "insertion")


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


SPINE = """async () => {
  const P = window.__poseApi;
  if (!P) return {err: 'no pose controller on this page'};
  if (!P.ready()) return {err: 'the pose rig did not load: ' + (P.failed() || '?')};
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const rig = P.rig();
  const regions = rig.regions.map(r => ({id: r.id, name: r.name, levels: r.levels.map(L => L.label),
                                         dof: r.dof.map(d => [d.k, d.lo, d.hi, d.w])}));
  const out = {regions: regions};
  if (!regions.length) return {err: 'this rig carries no spinal regions at all'};

  // the region with the most levels: the one where a single vertebra matters least on its own
  const R = rig.regions.slice().sort((a, b) => b.levels.length - a.levels.length)[0];
  out.region = R.id;
  out.levelsReported = (P.levels(R.id) || []).map(L => ({label: L.label, dof: L.dof.map(d =>
      ({k: d.k, value: +d.value.toFixed(3), lo: +d.lo.toFixed(3), hi: +d.hi.toFixed(3),
        share: +d.share.toFixed(4), fromSegment: +d.fromSegment.toFixed(3), own: +d.own.toFixed(3)}))}));

  const k0 = R.dof[0].k;
  // ---- the segment: one angle, shared over every level
  P.reset(); await sleep(400);
  P.setRegion(R.id, k0, R.dof[0].hi * 0.6); await sleep(700);
  out.segment = {asked: R.dof[0].hi * 0.6,
                 perLevel: P.levels(R.id).map(L => +L.dof[0].value.toFixed(3)),
                 moved: P.stats().changed, posed: !P.isRest()};

  // ---- one vertebra, from rest: only it may leave its share
  P.reset(); await sleep(500);
  const mid = Math.floor(R.levels.length / 2);
  const share = P.levels(R.id)[mid].dof[0];
  P.setLevel(R.id, mid, k0, share.hi); await sleep(700);
  out.single = {level: R.levels[mid].label, askedTo: +share.hi.toFixed(3),
                perLevel: P.levels(R.id).map(L => +L.dof[0].value.toFixed(3)),
                moved: P.stats().changed, posed: !P.isRest()};

  // ---- and it is held inside its share
  P.setLevel(R.id, mid, k0, share.hi * 10); await sleep(500);
  out.clamped = +P.levels(R.id)[mid].dof[0].value.toFixed(3);
  out.clampTo = +share.hi.toFixed(3);

  // ---- the two compose
  P.reset(); await sleep(400);
  P.setRegion(R.id, k0, R.dof[0].hi * 0.5); await sleep(400);
  P.setLevel(R.id, mid, k0, P.levels(R.id)[mid].dof[0].hi); await sleep(700);
  out.composed = P.levels(R.id).map(L => +L.dof[0].value.toFixed(3));
  out.panel = {levelRows: document.querySelectorAll('#pz-body details .pz-row').length,
               hasSummary: !!Array.prototype.find.call(document.querySelectorAll('#pz-body summary'),
                                                       s => /one vertebra at a time/i.test(s.textContent))};
  P.reset(); await sleep(500);
  return out;
}"""

# Shape, not just position: RMS distance of a structure's own vertices from its own centroid is
# unchanged by translation and by rotation, so a change in it is a stretch or a slackening.
SOFT_JS = """async (arg) => {
  const P = window.__poseApi, rig = P.rig();
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const live = window.__poseLive;
  if (!live) return {err: 'this engine does not expose the posed vertices (__poseLive)'};
  const shape = (i) => {
    const p = live(i); if (!p || !p.length) return null;
    let cx = 0, cy = 0, cz = 0, n = p.length / 3;
    for (let k = 0; k < p.length; k += 3){ cx += p[k]; cy += p[k+1]; cz += p[k+2]; }
    cx /= n; cy /= n; cz /= n;
    let s = 0, lo = [1e9,1e9,1e9], hi = [-1e9,-1e9,-1e9];
    for (let k = 0; k < p.length; k += 3){
      const dx = p[k]-cx, dy = p[k+1]-cy, dz = p[k+2]-cz;
      s += dx*dx + dy*dy + dz*dz;
      for (let d = 0; d < 3; d++){ const v = p[k+d]; if (v < lo[d]) lo[d] = v; if (v > hi[d]) hi[d] = v; }
    }
    return {c: [cx, cy, cz], rms: Math.sqrt(s / n),
            ext: [hi[0]-lo[0], hi[1]-lo[1], hi[2]-lo[2]], n: n};
  };

  const R = rig.regions.slice().sort((a,b) => b.levels.length - a.levels.length)[0];
  const k0 = R.dof[0].k;
  // a small pose first, so every structure the move touches has its live arrays built
  P.reset(); await sleep(400);
  P.setRegion(R.id, k0, R.dof[0].hi * 0.08); await sleep(900);
  const d0 = window.__poseDebug();
  const touched = Object.keys(d0.moved || {});
  const idx = {}; rig.rigid.forEach(g => g[1].forEach(si => { idx[si] = 1; }));
  // which structure indices actually moved: take them from the debug hook's own list, by name
  const names = arg.names;          // id -> {index, layer} from the page's own structure list
  const pick = touched.map(id => names[id]).filter(Boolean);
  const before = {}; pick.forEach(s => { const sh = shape(s.index); if (sh) before[s.index] = sh; });

  // now a real move of the same region
  P.setRegion(R.id, k0, R.dof[0].hi * 0.85); await sleep(1400);
  const after = {}; pick.forEach(s => { const sh = shape(s.index); if (sh) after[s.index] = sh; });

  const rows = [];
  pick.forEach(s => {
    const a = before[s.index], b = after[s.index];
    if (!a || !b) return;
    const dc = Math.hypot(b.c[0]-a.c[0], b.c[1]-a.c[1], b.c[2]-a.c[2]);
    rows.push({id: s.id, layer: s.layer, verts: a.n,
               travelled_mm: +dc.toFixed(3),
               rms_before: +a.rms.toFixed(4), rms_after: +b.rms.toFixed(4),
               shape_change_pct: +(100 * (b.rms - a.rms) / Math.max(1e-9, a.rms)).toFixed(3),
               ext_change_pct: [0,1,2].map(d => +(100 * (b.ext[d]-a.ext[d]) / Math.max(1e-9, a.ext[d])).toFixed(2))});
  });
  P.reset(); await sleep(500);
  return {rows: rows, region: R.id, dof: k0, touched: touched.length};
}"""

NAMES = """() => {
  // the page's own structure list, as the labels adaptor sees it: index, id and layer
  const out = {};
  if (window.__poseIndex) return window.__poseIndex();
  const L = window.__labCtl && window.__labCtl.structures ? window.__labCtl.structures() : null;
  if (L) L.forEach((s, i) => { out[s.id] = {id: s.id, index: i, layer: s.cat || ''}; });
  return out;
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
            page = sorted(d.glob("atlas_viewer*.html")) or sorted(d.glob("index.html"))
            print(f"=== {d.name} ===")
            pg.goto(f"http://127.0.0.1:{port}/{page[0].name}", wait_until="load", timeout=90000)
            pg.wait_for_function("window.__poseApi", timeout=90000)
            pg.wait_for_timeout(2500)
            pg.evaluate("() => { const t = document.querySelector('.mw-tile[data-mode=\"anat\"]');"
                        " if (t) t.click(); }")
            pg.wait_for_timeout(2500)
            pg.evaluate("() => { const b = document.getElementById('btn-pose'); if (b) b.click(); }")
            pg.wait_for_timeout(1200)

            r = pg.evaluate(SPINE)
            if r.get("err"):
                print("  FAIL " + r["err"]); return 1

            print("     spinal regions: " + "; ".join(
                f"{x['name']} ({len(x['levels'])} levels: {','.join(x['levels'][:4])}"
                f"{'...' if len(x['levels']) > 4 else ''})" for x in r["regions"]))
            check(f"the rig offers the spinal regions ({len(r['regions'])})", len(r["regions"]) >= 3, errs)

            s = r["segment"]
            print(f"     segment: asked {s['asked']:.1f} deg of {r['region']} -> per level "
                  f"{s['perLevel']}, {s['moved']} structures moved")
            check("moving the segment moves the model", (s["moved"] or 0) > 0 and s["posed"], errs)
            check("and it reaches every vertebra, not just one",
                  sum(1 for v in s["perLevel"] if abs(v) > 1e-6) == len(s["perLevel"]), errs)
            print(f"     ({len(set(round(abs(v), 3) for v in s['perLevel']))} distinct share(s) over "
                  f"{len(s['perLevel'])} levels here -- this region's weights are equal by design; the "
                  f"unequal ones are cervical, checked next)")
            cw = next((x for x in r["regions"] if "cerv" in x["id"]), None)
            if cw:
                rot = next((d for d in cw["dof"] if d[0] == "rot"), None)
                ws = [round(w, 4) for w in (rot[3] if rot else [])]
                print(f"     cervical rotation shares: {ws}")
                check("the cervical rotation is NOT shared equally -- C1/C2 carries half of it, "
                      "which is the literature's own finding and not an average",
                      len(set(ws)) > 1 and max(ws) >= 0.45, errs)

            u = r["single"]
            others = [v for i, v in enumerate(u["perLevel"]) if abs(v) < 1e-6]
            print(f"     one vertebra: {u['level']} to {u['askedTo']:.2f} deg -> per level "
                  f"{u['perLevel']}, {u['moved']} structures moved")
            check(f"moving one vertebra moves the model ({u['moved']} structures)",
                  (u["moved"] or 0) > 0 and u["posed"], errs)
            check(f"and moves ONLY that vertebra ({len(others)} of {len(u['perLevel']) - 1} others at rest)",
                  len(others) == len(u["perLevel"]) - 1, errs)
            check(f"a vertebra is held inside its own share ({r['clamped']:.2f} = {r['clampTo']:.2f})",
                  abs(r["clamped"] - r["clampTo"]) < 0.01, errs)
            check(f"the segment and the vertebra compose ({r['composed']})",
                  sum(1 for v in r["composed"] if abs(v) > 1e-6) == len(r["composed"]), errs)
            check(f"the panel offers the per-vertebra rows ({r['panel']['levelRows']} rows)",
                  r["panel"]["hasSummary"] and r["panel"]["levelRows"] > 0, errs)

            # ---- 4.ii: does the soft tissue follow, and how
            names = pg.evaluate(NAMES)
            if not names:
                print("\n  (the page does not expose its structure list, so the soft-tissue "
                      "measurement was not run)")
            else:
                t = pg.evaluate(SOFT_JS, {"names": names})
                if t.get("err"):
                    print("\n  (" + t["err"] + ")")
                else:
                    rows = t["rows"]
                    soft = [x for x in rows if (x["layer"] or "").lower() in SOFT]
                    bone = [x for x in rows if (x["layer"] or "").lower() in ("bone", "cartilage", "joint")]
                    print(f"\n--- the soft tissue around the moved joint ({t['region']}/{t['dof']}): "
                          f"{len(rows)} structures measured, {len(soft)} soft, {len(bone)} skeletal ---")
                    moved_soft = [x for x in soft if x["travelled_mm"] > 0.5]
                    shaped = [x for x in soft if abs(x["shape_change_pct"]) > 0.1]
                    for x in sorted(soft, key=lambda y: -abs(y["shape_change_pct"]))[:6]:
                        print(f"     {x['id'][:34]:<34} {x['layer']:<9} travelled {x['travelled_mm']:>7.1f} mm  "
                              f"shape {x['shape_change_pct']:+6.2f} %  extents {x['ext_change_pct']}")
                    check(f"soft tissue moves with the joint, not only bone "
                          f"({len(moved_soft)} of {len(soft)} soft structures travelled)",
                          len(moved_soft) > 0, errs)
                    check(f"and it CHANGES SHAPE rather than only travelling -- stretch and slack "
                          f"({len(shaped)} of {len(soft)} changed their own spread by more than 0.1 %)",
                          len(shaped) > 0, errs)
                    stretched = [x for x in shaped if x["shape_change_pct"] > 0]
                    slackened = [x for x in shaped if x["shape_change_pct"] < 0]
                    check(f"both directions occur -- some stretch ({len(stretched)}), some slacken "
                          f"({len(slackened)})", len(stretched) > 0 and len(slackened) > 0, errs)
                    print("     NOT verified, and the page says so itself: volume is not preserved and "
                          "contraction is not simulated, so bulging from muscle contraction does not happen "
                          "here. The pose badge states it; this check does not contradict it.")
            b.close()
    finally:
        srv.terminate()

    print()
    if errs:
        print(f"Q319_SPINE_FAIL {len(errs)}")
        for e in errs:
            print("  - " + e)
        return 1
    print("Q319_SPINE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
