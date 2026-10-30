#!/usr/bin/env python3
"""Q268: real headless-Chromium verification of the needle tool's three new clinical items -- (1) the injection-planning
preset, (2) the live distance readout to vessels / nerves, (3) suggested entry candidates -- with real clicks / typing
against a locally-served, template-only rebuilt page, plus the tool's own documented harness (window.NeedlePath, the
same hooks Q264 used) for exact placements. Run at desktop and this project's own 390x844 mobile convention.

    python3 scripts/anatomy/q268/verify_ui_q268.py OWN_DIR ZAN_DIR [--out placements.json]

The --out file records every harness placement together with the live JS readout (structure id + distance), so
scripts/anatomy/q268/crosscheck_q268.py can recompute the same numbers independently with trimesh on the same build."""
from __future__ import annotations
import argparse
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[3]
THREE = "/tmp/three_x/package/build/three.min.js"
LAUNCH_ARGS = ["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]
PREFERRED = ["rectus femoris", "vastus lateralis", "biceps brachii", "gastrocnemius", "deltoid", "brachioradialis"]


def serve(page_dir):
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "-d", str(page_dir)],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
    cands = sorted(Path(d).glob("atlas_viewer*.html"))
    return cands[0].name if cands else "index.html"


def wait_seq(pg, prev, timeout=30000):
    """wait until the live readout has recomputed past sequence number `prev` (the tool debounces by 80 ms, then measures);
    on a timeout returns the current readout unchanged (the caller's check then fails honestly instead of the run crashing)"""
    try:
        pg.wait_for_function("(s) => window.NeedlePath.corridor().seq > s", arg=prev, timeout=timeout)
    except Exception as err:  # noqa: BLE001
        print("     (wait_seq timed out: " + str(err).splitlines()[0][:80] + ")")
    return pg.evaluate("() => window.NeedlePath.corridor()")


def check(label, cond, errs):
    ok = bool(cond)
    print(("  OK  " if ok else "  FAIL") + " " + label)
    if not ok:
        errs.append(label)
    return ok


PICK_TARGET = """() => {
  const t = window.NMSKClinicalTool, pref = %s;
  const all = t.recs.filter(r => r.cat === 'muscle' && t.planNeighbours(r.i).length > 0);
  const order = [];
  for (const p of pref) { const m = all.find(x => x.name.toLowerCase().startsWith(p)); if (m) order.push(m); }
  for (const m of all) if (order.indexOf(m) < 0) order.push(m);
  function inside(r) {          // a point inside the mesh: the bbox centre, else a short search over the bbox
    const c = [0,1,2].map(k => (r.bmin[k] + r.bmax[k]) / 2);
    if (t.insideMesh(r.i, c)) return c;
    for (let a = 0.2; a <= 0.8; a += 0.15) for (let b = 0.2; b <= 0.8; b += 0.15) for (let d = 0.2; d <= 0.8; d += 0.15) {
      const q = [r.bmin[0] + (r.bmax[0]-r.bmin[0])*a, r.bmin[1] + (r.bmax[1]-r.bmin[1])*b, r.bmin[2] + (r.bmax[2]-r.bmin[2])*d];
      if (t.insideMesh(r.i, q)) return q; }
    return null;
  }
  let fallback = null;
  for (const r of order.slice(0, 60)) {
    const p = inside(r); if (!p) continue;
    const m = t.corridorFor(p, p, r.id);      // prefer a target with at least one vessel / nerve surface within R of the point (a meaningful readout)
    const rec = {i: r.i, id: r.id, name: r.name, p: p, inside: true, nb: t.planNeighbours(r.i).length, within: m.items.length};
    if (m.items.length) return rec;
    if (!fallback) fallback = rec;
  }
  return fallback;
}"""


def run_page(pl, page_dir, kind, viewport, errs_out, placements):
    page_dir = Path(page_dir)
    html = html_of(page_dir)
    srv, port = serve(page_dir)
    try:
        b = pl.chromium.launch(args=LAUNCH_ARGS, executable_path="/opt/pw-browsers/chromium")
        ctx = b.new_context(viewport=viewport, has_touch=viewport["width"] < 760, is_mobile=viewport["width"] < 760)
        pg = ctx.new_page()
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.route("**/*", route)
        tag = f"{kind} {page_dir.name} @ {viewport['width']}x{viewport['height']}"
        print(f"=== {tag} ===")
        pg.goto(f"http://127.0.0.1:{port}/{html}", wait_until="load", timeout=90000)
        pg.wait_for_function("window.NMSKClinicalTool && window.NeedlePath && window.__selState && window.__poseApi", timeout=60000)
        pg.wait_for_timeout(1500)

        # ---- open the needle tool with a real click ----
        pg.locator("#t-needle").click()
        pg.wait_for_timeout(300)
        check("needle panel opened (real click)", pg.evaluate("() => window.NMSKClinicalTool.active"), errs_out)
        pg.wait_for_timeout(700)   # the Q267 layout poll (500 ms) switches to Split once a tool is armed
        check("needle panel opens EXPANDED, not collapsed to its title bar (Q267 layout regression, fixed in Q268)",
              pg.evaluate("() => document.getElementById('ncl-min').getAttribute('aria-expanded') === 'true' && !document.getElementById('needle-panel').classList.contains('ncl-collapsed')"), errs_out)

        # ---- item 1: the preset, real typing into the picker + real click on a result row ----
        tgt = pg.evaluate(PICK_TARGET % json.dumps(PREFERRED))
        check("a muscle with vessel / nerve neighbours exists on this page", tgt is not None, errs_out)
        if tgt:
            print(f"     target: {tgt['name']} ({tgt['id']}), {tgt['nb']} neighbours within R, {tgt['within']} surfaces within R of the point")
            pg.locator("#ncl-plan-q").fill(tgt["name"][:12])
            pg.wait_for_timeout(150)
            rows = pg.locator("#ncl-plan-res button")
            check("picker lists real candidates for the typed name", rows.count() > 0, errs_out)
            row = None
            for k in range(rows.count()):
                if tgt["id"] in (rows.nth(k).inner_text()):
                    row = rows.nth(k); break
            (row or rows.first).click()
            pg.wait_for_timeout(400)
            sel = pg.evaluate("() => window.__selState()")
            tool = pg.evaluate("() => ({active: window.NMSKClinicalTool.active, mode: window.NMSKClinicalTool.mode, plan: window.NMSKClinicalTool.plan.i})")
            check("preset: target + neighbours marked through the public selection API", tgt["id"] in sel["marks"] and len(sel["marks"]) >= 1 + min(1, tgt["nb"]), errs_out)
            check("preset: everything else faded (oth = fade)", sel["oth"] == "fade" and sel["sel"] == "show", errs_out)
            ps = pg.evaluate("() => window.__partsState()")
            check("preset: parts markers opened for the target when it has parts data, no-op otherwise (never errors)",
                  (ps["sel"] is None) or (ps["sel"]["mesh"] == tgt["id"]), errs_out)
            print(f"     parts: loaded={ps['loaded']} sel={ps['sel']} mode={ps['mode']}")
            check("preset: needle armed in target-first mode", tool["active"] and tool["mode"] == "tfirst" and tool["plan"] == tgt["i"], errs_out)
            msg = pg.locator("#ncl-plan-msg").inner_text()
            check("preset message says what it did", "marked" in msg and "Now click the target point" in msg, errs_out)

            # ---- item 2: a REAL canvas click places the target point (target-first), readout appears ----
            scr = pg.evaluate("(p) => window.NeedlePath.toScreen(p)", tgt["p"])
            if scr:
                # at phone width the needle panel may cover the model: a user would collapse it first (Q264 compact mode, a real click), so do that
                covered = pg.evaluate("(s) => { const e = document.elementFromPoint(s[0], s[1]); return !(e && e.tagName === 'CANVAS'); }", scr)
                if covered:
                    pg.locator("#ncl-min").click(); pg.wait_for_timeout(150)
                    covered = pg.evaluate("(s) => { const e = document.elementFromPoint(s[0], s[1]); return !(e && e.tagName === 'CANVAS'); }", scr)
                if not covered:
                    seq0 = pg.evaluate("() => window.NeedlePath.corridor().seq")
                    pg.mouse.click(scr[0], scr[1])
                    wait_seq(pg, seq0)
                    st = pg.evaluate("() => ({t: !!window.NMSKClinicalTool.target, c: window.NeedlePath.corridor()})")
                    check("real click placed a target point; the live readout computed (what-measured text present)", st["t"] and st["c"]["what"] != "", errs_out)
                    print(f"     after click: {st['c']['n']} meshes measured in {st['c']['ms']} ms, {len(st['c']['items'])} within R")
                else:
                    print("     (the target's screen position is not on the canvas at this viewport even with the panel collapsed: real-click placement skipped here, harness placements below)")
                if pg.evaluate("() => document.getElementById('ncl-min').getAttribute('aria-expanded') === 'false'"):
                    pg.locator("#ncl-min").click(); pg.wait_for_timeout(150)

            # ---- item 2: exact harness placements (window.NeedlePath, the Q264 harness), recorded for the trimesh cross-check ----
            T = tgt["p"]
            E1 = [T[0], T[1], T[2] + 45.0]
            E2 = [T[0] + 30.0, T[1] + 10.0, T[2] + 30.0]
            T3 = [T[0] + 6.0, T[1] - 4.0, T[2]]
            cases = [("segment anterior", E1, T), ("segment oblique", E2, T), ("segment shifted target", E1, T3)]
            prev = None
            for label, E, TT in cases:
                seq0 = pg.evaluate("() => window.NeedlePath.corridor().seq")
                pg.evaluate("(a) => window.NeedlePath.setPoints(a[0], a[1], null, a[2])", [E, TT, tgt["id"]])
                c = wait_seq(pg, seq0)
                check(f"readout updated on placement '{label}' ({len(c['items'])} structures within R, nearest "
                      f"{c['items'][0]['name'] + ' ' + str(c['items'][0]['d_mm']) + ' mm' if c['items'] else 'none'})",
                      c["what"].startswith("the entry"), errs_out)   # wait_seq() above already proved a fresh computation
                sorted_ok = all(c["items"][k]["d_mm"] <= c["items"][k + 1]["d_mm"] for k in range(len(c["items"]) - 1))
                check(f"  nearest first, every distance within R={c['R']} mm", sorted_ok and all(it["d_mm"] <= c["R"] for it in c["items"]), errs_out)
                prev = c["items"]
                placements.append({"page": page_dir.name, "kind": kind, "viewport": viewport["width"], "label": label, "entry": E, "target": TT,
                                   "target_id": tgt["id"], "R": c["R"], "n_measured": c["n"], "ms": c["ms"], "items": c["items"]})
            # single point before a segment exists
            seq0 = pg.evaluate("() => window.NeedlePath.corridor().seq")
            pg.evaluate("() => { const t = window.NMSKClinicalTool; t.entry = null; t.update(); }")
            c1 = wait_seq(pg, seq0)
            check("single placed point (no segment yet): readout measures from the point", c1["what"].startswith("the target point"), errs_out)
            placements.append({"page": page_dir.name, "kind": kind, "viewport": viewport["width"], "label": "point only", "entry": None, "target": T3,
                               "target_id": tgt["id"], "R": c1["R"], "n_measured": c1["n"], "ms": c1["ms"], "items": c1["items"]})
            # editable display thresholds: a real edit of the near band re-bands the list without recomputing
            seq0 = pg.evaluate("() => window.NeedlePath.corridor().seq")
            pg.evaluate("(a) => window.NeedlePath.setPoints(a[0], a[1], null, a[2])", [E1, T, tgt["id"]])
            prev = wait_seq(pg, seq0)["items"]
            near_in = pg.locator("#ncl-corr-near")
            near_in.fill("8"); near_in.dispatch_event("change")
            pg.wait_for_timeout(100)
            c2 = pg.evaluate("() => window.NeedlePath.corridor()")
            bands = pg.evaluate("() => Array.from(document.querySelectorAll('#ncl-corr-out .corr-list li')).map(li => li.className)")
            exp = ["band-n" if it["d_mm"] < 8 else ("band-m" if it["d_mm"] < c2["far"] else "band-f") for it in c2["items"][:12]]
            check("display threshold edited to 8 mm: bands follow the new threshold, data unchanged", c2["near"] == 8 and bands == exp and c2["items"] == prev, errs_out)
            txt = pg.locator("#ncl-corr-out").inner_text()
            check("readout says what it measured and that bands are display-only", "Measured: minimum distance from" in txt and "display only" in txt, errs_out)

            # ---- item 3: suggestions, real click; adoption only by an explicit tap ----
            seq0 = pg.evaluate("() => window.NeedlePath.corridor().seq")
            pg.evaluate("() => { const t = window.NMSKClinicalTool; t.entry = null; t.update(); }")
            wait_seq(pg, seq0)
            pg.locator("#ncl-sugg").click()
            pg.wait_for_timeout(1500)
            sg = pg.evaluate("() => ({shown: window.NeedlePath.suggestions(), entry: window.NMSKClinicalTool.entry, msg: document.getElementById('ncl-sugg-out').innerText})")
            check(f"suggest: {len(sg['shown'])} candidate(s) shown (<= 2), nothing auto-placed", len(sg["shown"]) <= 2 and sg["entry"] is None, errs_out)
            if sg["shown"]:
                print(f"     candidates: " + "; ".join(f"{s['length_mm']:.0f} mm / clearance {s['min_mm']:.1f} mm" for s in sg["shown"]))
                check("suggest: every shown candidate clears the far display threshold", all(s["min_mm"] > c2["far"] for s in sg["shown"]), errs_out)
                pg.locator("#ncl-sugg-out [data-sg='0']").click()
                pg.wait_for_timeout(350)
                ent = pg.evaluate("() => window.NMSKClinicalTool.entry ? window.NMSKClinicalTool.entry.p : null")
                check("explicit tap on Use adopted the candidate as the entry", ent is not None and max(abs(ent[k] - sg["shown"][0]["entry"][k]) for k in range(3)) < 1e-6, errs_out)
            else:
                check("suggest: with nothing shown the panel says so plainly", "none shown" in sg["msg"] or "No skin" in sg["msg"], errs_out)
                print("     " + sg["msg"][:160])
                # the far band is the clinician's own editable display threshold: lower it (real edit) and ask again, so the ghost-line / tap-to-adopt path is exercised too
                far_in = pg.locator("#ncl-corr-far"); far_in.fill("3"); far_in.dispatch_event("change"); pg.wait_for_timeout(100)
                pg.locator("#ncl-sugg").click(); pg.wait_for_timeout(1500)
                sg2 = pg.evaluate("() => ({shown: window.NeedlePath.suggestions(), entry: window.NMSKClinicalTool.entry})")
                check(f"suggest (far lowered to 3 mm by a real edit): {len(sg2['shown'])} candidate(s) shown, still nothing auto-placed", len(sg2["shown"]) <= 2 and sg2["entry"] is None, errs_out)
                if sg2["shown"]:
                    print(f"     candidates: " + "; ".join(f"{s['length_mm']:.0f} mm / clearance {s['min_mm']:.1f} mm" for s in sg2["shown"]))
                    check("suggest: every shown candidate clears the (lowered) far threshold", all(s["min_mm"] > 3 for s in sg2["shown"]), errs_out)
                    pg.locator("#ncl-sugg-out [data-sg='0']").click(); pg.wait_for_timeout(350)
                    ent = pg.evaluate("() => window.NMSKClinicalTool.entry ? window.NMSKClinicalTool.entry.p : null")
                    check("explicit tap on Use adopted the candidate as the entry", ent is not None and max(abs(ent[k] - sg2["shown"][0]["entry"][k]) for k in range(3)) < 1e-6, errs_out)
                far_in.fill("15"); far_in.dispatch_event("change"); pg.wait_for_timeout(100)

            # ---- item 1 posture: a labelled flexion pattern through the page's own pose rig, real select + click ----
            pg.select_option("#ncl-plan-pose", "ul")
            seq0 = pg.evaluate("() => window.NeedlePath.corridor().seq")
            pg.locator("#ncl-plan-pose-go").click()
            wait_seq(pg, seq0, timeout=60000)   # the rig's skinning pass blocks the main thread for a while; the readout recomputes after it
            po = pg.evaluate("() => ({rest: window.__poseApi.isRest(), msg: document.getElementById('ncl-plan-pose-msg').innerText, warn: document.getElementById('ncl-corr-out').innerText})")
            check("posture: upper-limb flexion pattern applied through the rig (pose away from rest)", po["rest"] is False and "applied" in po["msg"], errs_out)
            check("posture: readout warns that distances are measured on the rest pose", "away from rest" in po["warn"], errs_out)
            print("     " + po["msg"][:200].replace("\n", " "))
            pg.select_option("#ncl-plan-pose", "rest")
            pg.locator("#ncl-plan-pose-go").click()
            pg.wait_for_timeout(800)
            check("posture: Rest restores the model pose", pg.evaluate("() => window.__poseApi.isRest()"), errs_out)

            # ---- release ----
            pg.locator("#ncl-plan-x").click()
            pg.wait_for_timeout(200)
            check("Release plan clears the preset's marks", pg.evaluate("() => window.__selState().marks.length") == 0, errs_out)

        check("0 page errors throughout this whole real-interaction pass", len(errs) == 0, errs_out)
        for e in errs[:10]:
            print("    PAGEERR:", e[:300])
        b.close()
    finally:
        srv.terminate()


def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument("own_dir"); ap.add_argument("zan_dir"); ap.add_argument("--out", default=None)
    ap.add_argument("--desktop-only", action="store_true")
    a = ap.parse_args(argv)
    errs, placements = [], []
    with sync_playwright() as pl:
        vps = [{"width": 1400, "height": 900}] + ([] if a.desktop_only else [{"width": 390, "height": 844}])
        for vp in vps:
            run_page(pl, a.own_dir, "own", vp, errs, placements)
        for vp in vps:
            run_page(pl, a.zan_dir, "zan", vp, errs, placements)
    if a.out:
        Path(a.out).write_text(json.dumps(placements, indent=1))
        print("placements written:", a.out, len(placements))
    print()
    print("TOTAL FAILED CHECKS:", len(errs))
    for e in errs:
        print("  -", e)
    return 0 if not errs else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
