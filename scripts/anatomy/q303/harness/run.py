#!/usr/bin/env python3
"""Q303 Phase 1: the standalone harness. Real Chromium, a FAKE host with fake providers, so every shared module of
this round is proved before either template is touched -- the method Q300 used. It loads the REAL modules out of
viewer/, so it cannot drift from what ships. Desktop 1400x900 and phone 390x844.

    python3 scripts/anatomy/q303/harness/run.py"""
from __future__ import annotations
import math, socket, subprocess, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]
ERRS: list = []
OK = [0]


def ck(label, cond):
    good = bool(cond)
    OK[0] += 1 if good else 0
    print(("  OK   " if good else "  FAIL ") + label)
    if not good:
        ERRS.append(label)
    return good


def serve(d):
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "-d", str(d)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    return srv, port


def run(pg, phone):
    tag = "phone" if phone else "desktop"
    print("\n== %s ==" % tag)
    pg.wait_for_function("window.__ready === true", timeout=30000)
    pg.wait_for_timeout(200)

    # ---- PCA: the rule's own arithmetic, on shapes whose answer is known by construction ----
    r = pg.evaluate("() => NMSKViews.report(['fascia_lata_r'])")
    ck("sheet: classified as a sheet (%s)" % r["shape"], r["shape"] == "sheet")
    ck("sheet: its minor axis is its normal, |e3.z| = %.4f >= 0.999" % abs(r["e3"][2]), abs(r["e3"][2]) >= 0.999)
    ck("sheet: looking along the minor axis is the bigger silhouette (%.3f vs %.3f)" % (r["silhouetteAlongMinor"], r["silhouetteAlongMajor"]),
       r["silhouetteAlongMinor"] > r["silhouetteAlongMajor"] * 2)
    r2 = pg.evaluate("() => NMSKViews.report(['sciatic_n_r'])")
    ck("rod: classified as a rod (%s)" % r2["shape"], r2["shape"] == "rod")
    ck("rod: its major axis is the shaft, |e1.y| = %.4f >= 0.999" % abs(r2["e1"][1]), abs(r2["e1"][1]) >= 0.999)
    ck("rod: its minor axis is across the shaft, |e3.y| = %.4f <= 0.01" % abs(r2["e3"][1]), abs(r2["e3"][1]) <= 0.01)
    ck("rod: the silhouette gain of the rule is %.3f" % (r2["gain"] or 0), (r2["gain"] or 0) > 3)

    # ---- the target: the owner's order, and NOTHING when nothing is chosen ----
    pg.evaluate("() => { window.__h.mark([]); window.__h.select(null); NMSKTarget.forget(); document.getElementById('q').value = ''; }")
    ck("target: nothing chosen -> no target", pg.evaluate("() => NMSKTarget.get() === null"))
    pg.evaluate("() => window.__h.select('tibial_n_r')")
    t = pg.evaluate("() => NMSKTarget.state().target")
    ck("target: a selected structure is the target (%s)" % t["kind"], t["kind"] == "selected" and t["ids"] == ["tibial_n_r"])
    pg.evaluate("() => window.__h.mark(['sciatic_n_r', 'median_n_r'])")
    t = pg.evaluate("() => NMSKTarget.state().target")
    ck("target: the marked set beats the selection (%s, n=%d)" % (t["kind"], len(t["ids"])), t["kind"] == "marked" and len(t["ids"]) == 2)
    box = pg.evaluate("() => { const s = window.__h.structures().filter(x => ['sciatic_n_r','median_n_r'].indexOf(x.id) >= 0);"
                      " const lo = [1e30,1e30,1e30], hi = [-1e30,-1e30,-1e30];"
                      " s.forEach(x => { for (let k = 0; k < 3; k++){ lo[k] = Math.min(lo[k], x.bmin[k]); hi[k] = Math.max(hi[k], x.bmax[k]); } });"
                      " return [0,1,2].map(k => (lo[k] + hi[k]) / 2); }")
    d = max(abs(a - b) for a, b in zip(box, t["c"]))
    ck("target: its centre IS the combined bounding-box centre (max axis error %.4f mm)" % d, d < 0.02)
    # the search pick, through a REAL click on the list row, which is how Q298 hands one over
    pg.evaluate("() => { window.__h.mark([]); window.__h.select(null); document.getElementById('q').value = 'sural'; }")
    pg.click("#list .row[data-id='sural_n_r']")
    pg.wait_for_timeout(120)
    pg.evaluate("() => window.__h.select(null)")
    t = pg.evaluate("() => NMSKTarget.state().target")
    ck("target: a picked search result is remembered (%s)" % (t and t["kind"]), t and t["kind"] == "search" and t["ids"] == ["sural_n_r"])

    # ---- auto-focus, per mode, with the measured offset ----
    nums = {}
    pg.evaluate("() => { window.__h.mark(['tibial_n_r']); NMSKHistory.commit(); }")
    want = pg.evaluate("() => NMSKTarget.get().c")
    # CT / MR
    pg.evaluate("() => { window.NMSKImaging.close(); window.NMSKImaging.open(); }")
    pg.wait_for_timeout(500)
    st = pg.evaluate("() => ({img: window.__h.img(), last: NMSKAutoFocus.last()})")
    off = max(abs(a - b) for a, b in zip(st["img"]["P"], want))
    nums["ct_mm"] = off
    ck("focus CT/MR: the slice point is the target centre (max axis error %.4f mm)" % off, off < 0.02)
    ck("focus CT/MR: every pane's in-plane centre released", all(v is None for _, v in st["img"]["CP"]))
    ck("focus CT/MR: the notice names the target", (st["last"] or {}).get("label") == "Tibial nerve (right)")
    # ultrasound
    pg.evaluate("() => { window.NMSKUltrasound.close(); window.NMSKUltrasound.open(); }")
    pg.wait_for_timeout(500)
    us = pg.evaluate("() => window.__h.us()")
    rad = math.hypot(us["P"][0], us["P"][2])          # the harness skin is a vertical cylinder of radius 250
    e = pg.evaluate("() => window.__h.eye()")
    cross = math.dist(us["P"], want)
    nums["us_skin_mm"] = abs(rad - 250)
    last = pg.evaluate("() => NMSKAutoFocus.last()")
    ck("focus US: the probe is seated ON the skin (|r - 250| = %.4f mm, came in from %s)"
       % (abs(rad - 250), (last.get("result") or {}).get("from")), abs(rad - 250) < 0.5 and last["ok"])
    # it must be the skin point between the camera and the target, i.e. nearer the eye than the target is
    ck("focus US: seated on the side the camera is on (%.1f mm from the eye vs %.1f for the target)"
       % (math.dist(us["P"], e), math.dist(want, e)), math.dist(us["P"], e) < math.dist(want, e))
    # cut
    pg.evaluate("() => { window.__fakeCut.exit(); window.__fakeCut.enter(); }")
    pg.wait_for_timeout(500)
    c = pg.evaluate("() => ({cut: window.__h.cut(), last: NMSKAutoFocus.last()})")
    aw = sum(n * p for n, p in zip(c["cut"]["n0"], want))
    nums["cut_mm"] = abs(c["cut"]["a"] - aw)
    ck("focus cut: the plane passes through the centre (offset error %.4f mm along its own normal)" % abs(c["cut"]["a"] - aw),
       abs(c["cut"]["a"] - aw) < 0.02)
    ck("focus cut: the plane kept the orientation the user chose", c["cut"]["ori"] == "x")
    # cross-section, plane mode and part mode
    pg.evaluate("() => { window.__fakeXsec.set(false); window.__fakeXsec.setMode('plane'); window.__fakeCut.restore({on:true, ori:'x', n0:[1,0,0], a:0, a0:0, th:0}); }")
    pg.wait_for_timeout(450)
    pg.evaluate("() => window.__fakeXsec.set(true)")
    pg.wait_for_timeout(500)
    c2 = pg.evaluate("() => window.__h.cut()")
    ck("focus cross-section (plane): the stack's plane is centred (%.4f mm)" % abs(c2["a"] - aw), abs(c2["a"] - aw) < 0.02)
    pg.evaluate("() => { window.__fakeXsec.set(false); window.__fakeXsec.setMode('part'); }")
    pg.wait_for_timeout(450)                 # the watcher polls every 250 ms: leaving and re-entering must be two events
    pg.evaluate("() => window.__fakeXsec.set(true)")
    pg.wait_for_timeout(500)
    x = pg.evaluate("() => window.__h.xsec()")
    ck("focus cross-section (part): the stack's part becomes the chosen structures", x["part"] == ["tibial_n_r"])
    # a render style frames the camera
    pg.evaluate("() => { window.NMSKRenderStyle.set('colour'); }")
    pg.wait_for_timeout(300)
    pg.evaluate("() => { window.NMSKRenderStyle.set('xray'); }")
    pg.wait_for_timeout(500)
    cam = pg.evaluate("() => window.__h.cam()")
    off = max(abs(a - b) for a, b in zip(cam["tgt"], want))
    nums["style_mm"] = off
    ck("focus style: the camera target is the centre (%.4f mm)" % off, off < 0.02)

    # ---- nothing chosen: NOTHING moves, in every mode ----
    pg.evaluate("() => { window.__h.mark([]); window.__h.select(null); NMSKTarget.forget(); document.getElementById('q').value = '';"
                " window.NMSKImaging.close(); window.NMSKUltrasound.close(); window.__fakeCut.exit(); window.__fakeXsec.set(false);"
                " window.NMSKRenderStyle.set('colour'); }")
    pg.wait_for_timeout(500)
    before = pg.evaluate("() => ({cam: window.__h.cam(), img: window.__h.img().P, us: window.__h.us().P, cut: window.__h.cut().a})")
    pg.evaluate("() => { window.NMSKImaging.open(); window.NMSKUltrasound.open(); window.__fakeCut.enter(); window.__fakeXsec.set(true); window.NMSKRenderStyle.set('ct'); }")
    pg.wait_for_timeout(900)
    after = pg.evaluate("() => ({cam: window.__h.cam(), img: window.__h.img().P, us: window.__h.us().P, cut: window.__h.cut().a})")
    ck("nothing chosen: the camera did not move", before["cam"] == after["cam"])
    ck("nothing chosen: the slice point did not move", before["img"] == after["img"])
    ck("nothing chosen: the probe did not move", before["us"] == after["us"])
    ck("nothing chosen: the cut plane did not move", before["cut"] == after["cut"])
    ck("nothing chosen: the module says why", "nothing is marked" in (pg.evaluate("() => (NMSKAutoFocus.last() || {}).why") or ""))

    # ---- one undo step ----
    pg.evaluate("() => { window.NMSKImaging.close(); window.__fakeCut.exit(); window.__fakeXsec.set(false); window.NMSKRenderStyle.set('colour');"
                " window.__h.mark(['sciatic_n_r']); NMSKHistory.commit(); }")
    pg.wait_for_timeout(450)                 # leaving and re-entering must be two events for the watcher, as it is for a human
    n0 = pg.evaluate("() => NMSKHistory.state().idx")
    p0 = pg.evaluate("() => window.__h.img().P")
    pg.evaluate("() => window.NMSKImaging.open()")
    pg.wait_for_timeout(600)
    n1 = pg.evaluate("() => NMSKHistory.state().idx")
    p1 = pg.evaluate("() => window.__h.img().P")
    ck("one undo step: the focus added exactly one entry (%d -> %d)" % (n0, n1), n1 == n0 + 1)
    ck("one undo step: the slice point really moved", p1 != p0)
    pg.evaluate("() => NMSKHistory.undo()")
    pg.wait_for_timeout(200)
    p2 = pg.evaluate("() => window.__h.img().P")
    ck("one undo step: one Undo puts the slice point back (%s)" % (p2 == p0), p2 == p0)
    pg.evaluate("() => NMSKHistory.redo()")
    pg.wait_for_timeout(200)
    ck("one undo step: Redo brings it forward", pg.evaluate("() => window.__h.img().P") == p1)

    # ---- the off switch ----
    pg.evaluate("() => { NMSKAutoFocus.setOn(false); window.NMSKImaging.close(); }")
    pg.wait_for_timeout(450)
    pb = pg.evaluate("() => window.__h.img().P")
    pg.evaluate("() => window.NMSKImaging.open()")
    pg.wait_for_timeout(600)
    ck("off switch: with Follow off, nothing moves", pg.evaluate("() => window.__h.img().P") == pb)
    pg.evaluate("() => NMSKAutoFocus.setOn(true)")
    ck("off switch: the toggle reports its state", pg.evaluate("() => NMSKAutoFocus.on() === true"))

    # ---- four up ----
    pg.evaluate("() => { window.NMSKImaging.close(); NMSKFourUp.leave(); }")
    pg.wait_for_timeout(150)
    ck("four-up: one view by default", pg.evaluate("() => NMSKFourUp.layout()") == "one")
    h0 = pg.evaluate("() => NMSKHistory.state().idx")
    pg.evaluate("() => NMSKFourUp.enter()")
    pg.wait_for_timeout(250)
    P = pg.evaluate("() => window.__h.panes()")
    ck("four-up: four panes handed to the engine", P and len(P) == 4)
    ck("four-up: one undo step (%d -> %d)" % (h0, pg.evaluate("() => NMSKHistory.state().idx")),
       pg.evaluate("() => NMSKHistory.state().idx") == h0 + 1)
    keys = [p["key"] for p in P]
    ck("four-up: the conventional set %s" % keys, keys == ["ant", "lat", "sup", "free"])
    dirs = []
    for p in P:
        ce = math.cos(p["el"])
        dirs.append((ce * math.sin(p["az"]), math.sin(p["el"]), ce * math.cos(p["az"])))
    worst = max(abs(sum(a * b for a, b in zip(dirs[i], dirs[j]))) for i in range(4) for j in range(i + 1, 4))
    ck("four-up: the four cameras are distinct (worst |cos| between view directions %.3f)" % worst, worst < 0.98)
    tg = [tuple(round(v, 4) for v in p["tgt"]) for p in P]
    ck("four-up: ONE model -- all four share the target and the distance", len(set(tg)) == 1 and len(set(round(p["dist"], 4) for p in P)) == 1)
    cov = sum(p["w"] * p["h"] for p in P)
    ck("four-up: the panes tile the canvas exactly (area %.3f)" % cov, abs(cov - 1.0) < 1e-9)
    # the pointer map is the identity on the pane's own corners
    m = pg.evaluate("""() => {
      const r = window.__h.canvasRect(), out = [];
      ['ant','lat','sup','free'].forEach(k => {
        const q = NMSKFourUp.paneRect(k);
        const c = NMSKFourUp.mapXY(q.left + q.width/2, q.top + q.height/2, k);
        out.push({k:k, dx:c[0] - (r.left + r.width/2), dy:c[1] - (r.top + r.height/2),
                  at:NMSKFourUp.paneAt(q.left + q.width/2, q.top + q.height/2)});
      });
      return out; }""")
    ck("four-up: a pane's centre maps to the canvas centre (max %.3f px)" % max(max(abs(x["dx"]), abs(x["dy"])) for x in m),
       all(abs(x["dx"]) < 0.6 and abs(x["dy"]) < 0.6 for x in m))
    ck("four-up: each pane's centre resolves to that pane", all(x["at"] == x["k"] for x in m))
    # sync: a change of state is shared, because there is only one
    pg.evaluate("() => { window.NMSKRenderStyle.set('ct'); window.__h.select('femur_r'); }")
    pg.wait_for_timeout(200)
    ck("four-up: still four panes after a style change (one model, four cameras)",
       len(pg.evaluate("() => window.__h.panes()") or []) == 4)
    # expand and restore
    pg.evaluate("() => NMSKFourUp.expand('lat')")
    pg.wait_for_timeout(200)
    ck("four-up: expand gives one view of that pane", pg.evaluate("() => [NMSKFourUp.layout(), NMSKFourUp.shown()]") == ["one", "lat"])
    latcam = pg.evaluate("() => window.__h.cam()")
    ck("four-up: the expanded pane's own camera is installed (az %.3f)" % latcam["az"], abs(latcam["az"] - math.pi / 2) < 1e-6)
    pg.evaluate("() => NMSKFourUp.restore()")
    pg.wait_for_timeout(200)
    ck("four-up: restore gives four again", pg.evaluate("() => NMSKFourUp.layout()") == "four")
    pg.evaluate("() => NMSKHistory.undo()")
    pg.wait_for_timeout(200)
    ck("four-up: one Undo after restore goes back to the expanded pane",
       pg.evaluate("() => [NMSKFourUp.layout(), NMSKFourUp.shown()]") == ["one", "lat"])
    pg.evaluate("() => { NMSKFourUp.restore(); NMSKModelReset.run ? NMSKModelReset.run() : document.getElementById('q301-mr-model') && document.getElementById('q301-mr-model').click(); }")
    pg.wait_for_timeout(400)
    ck("four-up: the model reset returns a single view", pg.evaluate("() => NMSKFourUp.layout()") == "one")

    # ---- facing me ----
    pg.evaluate("() => { window.__h.mark([]); window.__h.select('fascia_lata_r'); window.__h.setCam({az:0.9, el:0.6, dist:1800, tgt:[0,850,0]}); }")
    h0 = pg.evaluate("() => NMSKHistory.state().idx")
    f = pg.evaluate("() => NMSKViews.facing()")
    pg.wait_for_timeout(150)
    ck("facing me (sheet): applied, read as a %s" % f["shape"], f["ok"] and f["shape"] == "sheet")
    ck("facing me (sheet): the chosen axis is within %.3f deg of the view direction" % f["angle_deg"], f["angle_deg"] <= 2.0)
    ck("facing me: one undo step", pg.evaluate("() => NMSKHistory.state().idx") == h0 + 1)
    c_before = pg.evaluate("() => ({az:0.9, el:0.6})")
    pg.evaluate("() => NMSKHistory.undo()")
    pg.wait_for_timeout(150)
    cu = pg.evaluate("() => window.__h.cam()")
    ck("facing me: one Undo returns the camera (az %.3f el %.3f)" % (cu["az"], cu["el"]),
       abs(cu["az"] - c_before["az"]) < 1e-3 and abs(cu["el"] - c_before["el"]) < 1e-3)
    pg.evaluate("() => { window.__h.select('sciatic_n_r'); }")
    f2 = pg.evaluate("() => NMSKViews.facing()")
    ck("facing me (rod): read as a %s, %.3f deg off its minor axis" % (f2["shape"], f2["angle_deg"]),
       f2["ok"] and f2["shape"] == "rod" and f2["angle_deg"] <= 2.0)
    # and the rod's long axis really does lie across the view
    ax = pg.evaluate("() => NMSKViews.report(['sciatic_n_r']).e1")
    e = pg.evaluate("() => window.__h.eye()")
    cm = pg.evaluate("() => window.__h.cam()")
    vd = [cm["tgt"][i] - e[i] for i in range(3)]
    ln = math.sqrt(sum(v * v for v in vd)) or 1
    cosa = abs(sum(ax[i] * vd[i] / ln for i in range(3)))
    ck("facing me (rod): the shaft lies across the view (|cos| with the view direction %.4f)" % cosa, cosa < 0.05)

    # ---- saved views ----
    pg.evaluate("() => { try { localStorage.removeItem('nmsk.q303.views.harness'); } catch(e){} NMSKViews.del('Posterior ITB'); }")
    pg.evaluate("() => window.__h.setCam({az:2.1, el:-0.3, dist:900, tgt:[40, 600, -20]})")
    pg.evaluate("() => NMSKViews.save('Posterior ITB')")
    saved = pg.evaluate("() => NMSKViews.list()")
    ck("saved views: one is stored under its name", any(v["name"] == "Posterior ITB" for v in saved))
    pg.evaluate("() => window.__h.setCam({az:0.0, el:0.0, dist:1800, tgt:[0, 850, 0]})")
    h0 = pg.evaluate("() => NMSKHistory.state().idx")
    pg.evaluate("() => NMSKViews.apply('Posterior ITB')")
    pg.wait_for_timeout(150)
    c = pg.evaluate("() => window.__h.cam()")
    err = max(abs(c["az"] - 2.1), abs(c["el"] + 0.3), abs(c["dist"] - 900),
              max(abs(a - b) for a, b in zip(c["tgt"], [40, 600, -20])))
    ck("saved views: one tap returns the SAME camera (max component error %.5f)" % err, err < 1e-3)
    ck("saved views: one undo step", pg.evaluate("() => NMSKHistory.state().idx") == h0 + 1)
    pg.reload()
    pg.wait_for_function("window.__ready === true", timeout=30000)
    ck("saved views: they survive a reload", any(v["name"] == "Posterior ITB" for v in pg.evaluate("() => NMSKViews.list()")))
    pg.evaluate("() => NMSKViews.del('Posterior ITB')")
    ck("saved views: delete removes it", not any(v["name"] == "Posterior ITB" for v in pg.evaluate("() => NMSKViews.list()")))
    # a saved view that also changes the PANE LAYOUT must still be one entry: two nested steps would commit twice
    pg.evaluate("() => { NMSKViews.del('Four up view'); NMSKFourUp.enter(); }")
    pg.wait_for_timeout(250)
    pg.evaluate("() => NMSKViews.save('Four up view')")
    pg.evaluate("() => NMSKFourUp.leave()")
    pg.wait_for_timeout(250)
    pg.evaluate("() => NMSKHistory.commit()")
    h0 = pg.evaluate("() => NMSKHistory.state().idx")
    pg.evaluate("() => NMSKViews.apply('Four up view')")
    pg.wait_for_timeout(350)
    ck("saved views: one that also restores four panes is still ONE undo step (%d -> %d)" % (h0, pg.evaluate("() => NMSKHistory.state().idx")),
       pg.evaluate("() => NMSKHistory.state().idx") == h0 + 1)
    ck("saved views: and it really restored the four panes", pg.evaluate("() => NMSKFourUp.layout()") == "four")
    pg.evaluate("() => NMSKHistory.undo()")
    pg.wait_for_timeout(300)
    ck("saved views: one Undo returns BOTH the camera and the single view",
       pg.evaluate("() => NMSKFourUp.layout()") == "one")
    pg.evaluate("() => { NMSKViews.del('Four up view'); NMSKFourUp.leave(); }")

    # ---- nerve emphasis ----
    cen = pg.evaluate("() => NMSKNerves.census()")
    ck("nerves: the census counts the nerve structures (%d)" % cen["n"], cen["n"] == 6)
    ck("nerves: it reports how many are drawn under one pixel (%d of %d at %.3f mm/px)" % (cen["subPixel"], cen["n"], cen["mmPerPx"]),
       cen["subPixel"] >= 1)
    sm = pg.evaluate("() => NMSKNerves.sample()")
    print("     sample: " + "; ".join("%s d=%s true=%s drawn=%s" % (x["name"], x["dia_mm"], x["truePx"], x["drawnPx"]) for x in sm))
    h0 = pg.evaluate("() => NMSKHistory.state().idx")
    pg.evaluate("() => { window.__h.setCatOn('nerve', false); NMSKNerves.set(1); }")
    pg.wait_for_timeout(200)
    sp = pg.evaluate("() => window.__h.nerveSpec()")
    ck("nerves: Clear hands the engine a pass over every nerve (%s structures, wmin %s px)" % (sp and sp["n"], sp and sp["wmin"]),
       sp and sp["on"] and sp["n"] == 6 and sp["wmin"] == 2.2)
    ck("nerves: it switched the nerve layer back on (composes with the system toggle)",
       pg.evaluate("() => window.__h.catOn().nerve") is True)
    ck("nerves: one undo step", pg.evaluate("() => NMSKHistory.state().idx") == h0 + 1)
    w = pg.evaluate("() => ({small: NMSKNerves.widthOf('sural_n_r'), big: NMSKNerves.widthOf('sciatic_n_r')})")
    ck("nerves: the small one is widened to the minimum (%.3f px true -> %.3f px drawn)" % (w["small"]["truePx"], w["small"]["drawnPx"]),
       abs(w["small"]["drawnPx"] - 2.2) < 1e-6 and w["small"]["truePx"] < 2.2)
    ck("nerves: a nerve already wider than the minimum is NOT widened (%.3f -> %.3f px)" % (w["big"]["truePx"], w["big"]["drawnPx"]),
       abs(w["big"]["drawnPx"] - max(2.2, w["big"]["truePx"])) < 1e-6)
    pg.evaluate("() => NMSKNerves.set(2)")
    pg.wait_for_timeout(150)
    sp2 = pg.evaluate("() => window.__h.nerveSpec()")
    ck("nerves: Strong is wider and stronger (%s px, alpha %s)" % (sp2["wmin"], sp2["alpha"]), sp2["wmin"] > sp["wmin"] and sp2["alpha"] > sp["alpha"])
    pg.evaluate("() => NMSKHistory.undo()")
    pg.wait_for_timeout(150)
    ck("nerves: one Undo goes back a step", pg.evaluate("() => NMSKNerves.level()") == 1)
    ab = pg.evaluate("() => NMSKNerves.absent()")
    ck("nerves: it names the major nerves this page does not carry (%d of %d)" % (len(ab["missing"]), len(ab["missing"]) + len(ab["have"])),
       "fibular (peroneal)" in ab["missing"] and "sciatic" not in ab["missing"])
    ck("nerves: the shared shader is one string for both engines (%s)" % pg.evaluate("() => NMSKNervePass.hash()"),
       pg.evaluate("() => NMSKNervePass.vs().indexOf('gl_PointSize = uPt;') > 0"))
    pg.evaluate("() => NMSKNerves.set(0)")

    # ---- the compatibility rows and the View group ----
    mx = pg.evaluate("() => NMSKCombos.pairs().filter(r => r.a === 'fourup' || r.a === 'nerves')")
    ck("combos: the round's rows are registered (%d)" % len(mx), len(mx) == 7)
    pg.evaluate("() => { delete window.__fakeMeasure; NMSKFourUp.enter(); NMSKCombos.refresh(); }")
    v = pg.evaluate("() => NMSKCombos.verdict('measure')")
    ck("combos: four views disables Measure, with its reason on the screen", v["disabled"] and "pane" in v["reason"])
    pg.evaluate("() => { NMSKFourUp.leave(); window.NMSKRenderStyle.set('xray'); NMSKCombos.refresh(); }")
    v = pg.evaluate("() => NMSKCombos.verdict('nerves')")
    ck("combos: a radiographic style disables the nerve emphasis and says what to use instead",
       v["disabled"] and "Colour" in v["reason"])
    pg.evaluate("() => window.NMSKRenderStyle.set('colour')")
    g = pg.evaluate("() => NMSKGroups.groups().filter(x => x.key === 'view')[0]")
    ck("View group: the round's controls joined it rather than adding a top-level button (%d members)" % g["n"], g["n"] >= 5)
    pg.evaluate("() => NMSKGroups.open('view')")
    pg.wait_for_timeout(200)
    ids = pg.evaluate("() => ['q303-four','q303-facing','q303-vsave','q303-af','q303-centre','nv-box']"
                      ".map(i => { const e = document.getElementById(i); return e && document.getElementById('q301-sheet').contains(e); })")
    ck("View group: every new control is really inside the sheet %s" % ids, all(ids))

    # ---- the circled i: the round's five sections are generated from the real numbers, so BUILDING them is the test ----
    pg.evaluate("() => NMSKInfo.open()")
    pg.wait_for_timeout(400)
    secs = pg.evaluate("() => NMSKInfo.sections()")
    want = ["q303focus", "q303four", "q303facing", "q303nerves"]
    ck("the circled i carries this round's sections %s" % [x for x in want if x in secs],
       all(x in secs for x in want))
    txt = pg.evaluate("""() => {
      const out = {};
      ['q303focus','q303four','q303facing','q303nerves'].forEach(k => {
        const d = document.getElementById('qi-' + k);
        out[k] = d ? d.textContent.length : 0;
      });
      return out; }""")
    ck("every one of them really rendered %s" % txt, all(v > 300 for v in txt.values()))
    ck("the nerve section quotes the page's own measured numbers",
       pg.evaluate("""() => { const d = document.getElementById('qi-q303nerves');
         return !!d && d.textContent.indexOf(' mm') >= 0 && d.textContent.indexOf('display aid') >= 0; }"""))
    ck("the four-pane section names the convention and whose it is",
       pg.evaluate("""() => { const d = document.getElementById('qi-q303four');
         return !!d && d.textContent.indexOf('Slicer') >= 0 && d.textContent.indexOf('ours') >= 0; }"""))
    pg.evaluate("() => NMSKInfo.close()")
    pg.wait_for_timeout(200)

    # ---- it fits, and nothing of this round covers anything ----
    sc = pg.evaluate("() => ({w: document.documentElement.scrollWidth, c: document.documentElement.clientWidth})")
    ck("layout: no horizontal scroll (%d <= %d)" % (sc["w"], sc["c"]), sc["w"] <= sc["c"] + 1)
    pg.evaluate("() => { NMSKGroups.close(); NMSKFourUp.enter(); window.__h.mark(['tibial_n_r']); NMSKAutoFocus.focus('ct'); }")
    pg.wait_for_timeout(400)
    cover = pg.evaluate("""() => {
      const out = [];
      ['q301-undo','q301-redo','q301-reset','q301-mr-model','q303-exp-ant','q303-exp-lat','q303-exp-sup','q303-exp-free']
        .forEach(id => {
          const e = document.getElementById(id);
          if (!e) { out.push([id, 'missing']); return; }
          const r = e.getBoundingClientRect();
          if (!(r.width > 0 && r.height > 0)) { out.push([id, 'zero size']); return; }
          const h = document.elementFromPoint(r.x + r.width/2, r.y + r.height/2);
          const ok = h === e || e.contains(h) || (h && h.contains(e));
          out.push([id, ok ? 'ok' : (h ? h.tagName.toLowerCase() + (h.id ? '#' + h.id : '.' + h.className) : 'none')]);
        });
      return out; }""")
    bad = [c for c in cover if c[1] != "ok"]
    ck("layout: nothing covers Undo / Redo / the two resets / the four expand buttons %s" % (bad or "(all clear)"), not bad)
    sizes = pg.evaluate("""() => ['q303-exp-ant','q303-exp-lat','q303-exp-sup','q303-exp-free'].map(id => {
      const r = document.getElementById(id).getBoundingClientRect(); return [Math.round(r.width), Math.round(r.height)]; })""")
    ck("layout: the expand buttons are at least 24 px %s" % sizes, all(a >= 24 and b >= 24 for a, b in sizes))
    prect = pg.evaluate("() => ['ant','lat','sup','free'].map(k => { const r = NMSKFourUp.paneRect(k); return [Math.round(r.width), Math.round(r.height)]; })")
    print("     pane size (CSS px): %s" % prect)
    nums["pane"] = prect
    # a real touch / click inside a pane reaches that pane
    q = pg.evaluate("() => NMSKFourUp.paneRect('sup')")
    x, y = q["left"] + q["width"] / 2, q["top"] + q["height"] / 2
    if phone:
        pg.touchscreen.tap(x, y)
    else:
        pg.mouse.click(x, y)
    pg.wait_for_timeout(250)
    ck("input: a real %s inside the Superior pane makes it the active one" % ("touch" if phone else "click"),
       pg.evaluate("() => NMSKFourUp.state().active") == "sup")
    ck("input: the pointer really was remapped (%d events)" % pg.evaluate("() => NMSKFourUp.state().remapped"),
       pg.evaluate("() => NMSKFourUp.state().remapped") > 0 and pg.evaluate("() => NMSKFourUp.state().refused") == 0)
    pg.evaluate("() => NMSKFourUp.leave()")
    return nums


def main():
    srv, port = serve(REPO)
    out = {}
    try:
        with sync_playwright() as pw:
            b = pw.chromium.launch(args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"], executable_path="/opt/pw-browsers/chromium")
            for phone in (False, True):
                ctx = b.new_context(viewport={"width": 390, "height": 844} if phone else {"width": 1400, "height": 900},
                                    has_touch=phone, is_mobile=phone, device_scale_factor=2 if phone else 1)
                pg = ctx.new_page()
                errs = []
                pg.on("pageerror", lambda e: errs.append(str(e)))
                pg.goto("http://127.0.0.1:%d/scripts/anatomy/q303/harness/host.html" % port)
                out["phone" if phone else "desktop"] = run(pg, phone)
                ck("0 page errors (%s)" % (errs[:2] or ""), not errs)
                ctx.close()
            b.close()
    finally:
        srv.terminate()
    print("\n%d OK, %d FAIL" % (OK[0], len(ERRS)))
    for e in ERRS:
        print("  - " + e)
    print(out)
    return 1 if ERRS else 0


if __name__ == "__main__":
    raise SystemExit(main())
