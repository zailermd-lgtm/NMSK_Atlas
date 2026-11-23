#!/usr/bin/env python3
"""Q391: the muscles peel by their textbook layers, region by region, and can be hidden gently one by one.

Owner (translated from Hebrew, 2026-11-22): "The division into levels in one system does not necessarily match the
levels of another system. For the muscles, for example, it is a MUST to work by the known layers. Also allow gently
hiding muscle by muscle."

Real headless Chromium, desktop 1400x900 with real clicks and phone 390x844 with real taps, on each page given.
Every claim is a count read from the page's own state (NMSKSysMap, NMSKMusHide, NMSKQ309.measure / drawnOf):

A  THE LAYERS. The muscle system is layered by region (>= 25 regions), its strata are "layer n of its region"
   (n = 1..7, the back's seven), every muscle on the page has a sourced or a badged layer (no remainder), and the
   walk goes region by region with the layer number never decreasing inside a region.
B  THE PEEL. One system = muscles, one tap In: exactly the page's layer-1 muscles are hidden, every other system's
   drawn count is unchanged, and the status names "outermost layer of its region".
C  GENTLY. A real tap on "Hide next": the muscle is still drawn while it fades; the engine is handed a falling opacity
   over >= 4 drawn frames and >= 240 ms (about 250 ms on a real GPU; never fewer than 6 frames, so a slow software
   renderer like this container's slows the fade instead of popping), then it is not drawn; the status names it, its region and its layer. "Back" brings it back the same way.
D  THE LIST. Three hidden -> three chips; a chip brings back its own muscle only; "Show all" brings back every one.
E  ONE UNDO STEP. A step is one history entry; Ctrl+Z restores the exact prior snapshot; Ctrl+Y re-applies it.
F  A REGION. Choosing "Sole of the foot" in the select walks only the sole, layers 1 -> 4 in order.
G  THE CARD. A muscle opened in the quick card shows its region and layer and fades out from "Fade out".
H  POSED, CUT, LABELLED. With a joint moved, the cut on and the labels on, a step still fades out and ends hidden,
   and the pose, the cut and the labels are still on afterwards.
I  Q301 IS UNTOUCHED. The whole-body peel still steps on NMSKPeel and leaves the muscle list as it was.
J  THE PHONE, 0 PAGE ERRORS. No horizontal overflow at 390 px; the page reports no errors.

    python3 scripts/anatomy/q391/verify_layers_q391.py PAGE_DIR... [--viewport 1400|390] [--json OUT]
Run behind the one browser lock:  flock /tmp/nmsk_browser.lock python3 ...
Ends with one line: Q391_LAYERS_OK or Q391_LAYERS_FAIL."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "q309"))
import verify_q309 as Q  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

V = Q.V
OK, BAD = [0], []
REPORT: dict = {}


def check(label, cond):
    if cond:
        OK[0] += 1
        print("  OK   " + label)
    else:
        BAD.append(label)
        print("  FAIL " + label)
    return bool(cond)


def ev(pg, js, arg=None):
    return pg.evaluate(js, arg) if arg is not None else pg.evaluate(js)


def tap(pg, sel, phone, tag, what):
    top = False
    for wait in (120, 600, 1500):           # a passing chip (zoom, Show everything) can sit over it for a moment: look again
        pg.evaluate("(s) => { const e = document.querySelector(s); if (e) e.scrollIntoView({block:'center'}); }", sel)
        pg.wait_for_timeout(wait)
        top = Q.ontop(pg, sel)
        if top:
            break
    cover = "" if top else ev(pg, """(s) => { const e = document.querySelector(s); if (!e) return 'missing';
        const r = e.getBoundingClientRect(); const t = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
        return t ? ((t.id || '') + '.' + String(t.className || '').slice(0, 30) + ' @' + Math.round(r.left) + ',' + Math.round(r.top)) : 'nothing'; }""", sel)
    check("%s %s is the top element at its own centre (%s)%s" % (tag, what, sel, (" -- covered by " + cover) if cover else ""), top)
    if not top:
        return False
    if phone:
        r = ev(pg, "(s) => { const r = document.querySelector(s).getBoundingClientRect(); return {x:r.x + r.width/2, y:r.y + r.height/2}; }", sel)
        pg.touchscreen.tap(r["x"], r["y"])
    else:
        pg.click(sel)
    return True


SYS = "() => NMSKMusHide.state().system"


def drawn_of(pg, ids):
    """the engine's own count of these exact ids drawn now (Q309's verification hook)"""
    return ev(pg, "(ids) => NMSKQ309.drawnOf(ids)", ids)


def fade_curve(tr, ids):
    """the opacity the engine was handed for these ids, frame by frame: first value, direction, duration"""
    vals = [(f["t"], min(f["live"][i] for i in ids if i in f["live"])) for f in tr if any(i in f["live"] for i in ids)]
    if not vals:
        return {"frames": 0, "first": -1, "mono": "", "ms": 0}
    v = [x[1] for x in vals]
    mono = "down" if all(b <= a for a, b in zip(v, v[1:])) else "up" if all(b >= a for a, b in zip(v, v[1:])) else "mixed"
    if len(v) == 1 or len(set(v)) == 1:          # one value (a slow software frame rate): its side says which way
        mono = "down" if v[0] > 0.5 else "up"
    end = next((f["t"] for f in tr if not any(i in f["live"] for i in ids)), vals[-1][0])
    return {"frames": len(v), "first": v[0], "mono": mono, "ms": int(end - vals[0][0]), "vals": v[:12]}


def wait_fade(pg, ms=15000):
    t = 0
    while t < ms:
        if ev(pg, "() => NMSKMusHide.state().fading") == 0:
            return t
        pg.wait_for_timeout(50)
        t += 50
    return -1


def open_box(pg, phone=False, tag=""):
    """Q309's boxes live in Q301's "systems" group (Q318's name for it); NMSKGroups.open TOGGLES, so only when closed"""
    pg.evaluate("""() => { if (!window.NMSKGroups) return;
        if (NMSKGroups.isOpen() !== 'systems') NMSKGroups.open('systems'); }""")
    pg.wait_for_timeout(500)
    pg.evaluate("() => { const e = document.getElementById('mh-box'); if (e) e.scrollIntoView({block:'center'}); }")
    pg.wait_for_timeout(250)
    if tag and ev(pg, "() => { const b = document.getElementById('mh-body'); return !!b && b.hidden; }"):
        # folded by default; one real tap opens it
        tap(pg, "#mh-open", phone, tag, "the Muscle by muscle fold")
        pg.wait_for_timeout(300)
        check("%s the fold opens on one tap (aria-expanded %s)" % (tag, ev(pg, "() => document.getElementById('mh-open').getAttribute('aria-expanded')")),
              ev(pg, "() => !document.getElementById('mh-body').hidden"))


def run_view(pg, tag, phone, R):
    k = ev(pg, SYS)
    # ---------------- A
    a = ev(pg, """(k) => { const S = NMSKSysMap.systems().filter(s => s.key === k)[0], regs = NMSKSysMap.regions(k);
        const ord = NMSKMusHide.order(); let mono = true, seen = {}, last = {}, back = [];
        ord.forEach(u => { if (last[u.region] && u.layer < last[u.region]) mono = false; last[u.region] = u.layer;
          if (seen[u.region] && seen[u.region] !== 'open') back.push(u.region); Object.keys(seen).forEach(r => { if (r !== u.region) seen[r] = 'closed'; }); seen[u.region] = 'open'; });
        return {n:S.n, peel:S.peel, strata:S.strata.map(t => [t.key, t.label, t.n, t.basis]), regions:regs.length,
                units:ord.length, mono:mono, interleaved:back.length,
                conv:ord.filter(u => (NMSKSysMap.layerOf(u.ids[0]) || {}).basis === 'convention').length}; }""", k)
    R["A"] = a
    keys = [s[0] for s in a["strata"]]
    check("%s A muscles layered by region: %d regions, %d muscles, peel offered" % (tag, a["regions"], a["n"]), a["regions"] >= 25 and a["peel"])
    check("%s A strata are layers 1..%d of each region (%s)" % (tag, len(keys), ",".join(keys)),
          keys[:1] == ["L1"] and all(x.startswith("L") for x in keys) and "Outermost" in a["strata"][0][1])
    check("%s A every muscle has a layer (no unsourced remainder: %s)" % (tag, "rest" not in keys), "rest" not in keys and sum(s[2] for s in a["strata"]) == a["n"])
    check("%s A the walk is region by region (no region revisited: %d) and outer -> inner inside each" % (tag, a["interleaved"]), a["mono"] and a["interleaved"] == 0)
    # ---------------- B
    open_box(pg, phone, tag)
    ev(pg, "(k) => NMSKSysPeel.setSystem(k)", k)
    pg.wait_for_timeout(300)
    other0 = ev(pg, "(k) => { const m = NMSKQ309.measure().bySystem; const o = {}; Object.keys(m).forEach(s => { if (s !== k) o[s] = m[s].drawn; }); return o; }", k)
    tap(pg, "#sp-in", phone, tag, "B the In tap (muscles)")
    pg.wait_for_timeout(400)
    b = ev(pg, """(k) => { const ids = NMSKSysPeel.ids(), L1 = NMSKSysMap.stratumIds(k, 0); const m = NMSKQ309.measure().bySystem;
        const o = {}; Object.keys(m).forEach(s => { if (s !== k) o[s] = m[s].drawn; });
        return {n:ids.length, L1:L1.length, same:ids.length === L1.length && ids.every(i => L1.indexOf(i) >= 0), other:o,
                txt:document.getElementById('sp-state').textContent}; }""", k)
    check("%s B step 1 hides exactly the %d layer-1 muscles (%d)" % (tag, b["L1"], b["n"]), b["same"] and b["n"] > 0)
    check("%s B every other system draws as before" % tag, b["other"] == other0)
    check("%s B the status names the layer (%r)" % (tag, b["txt"][:80]), "outermost layer of its region" in b["txt"])
    ev(pg, "() => { NMSKSysPeel.set(0); NMSKSysPeel.setScope('body'); }")
    pg.wait_for_timeout(300)
    # ---------------- C
    open_box(pg, phone, tag)
    Q.settle(pg)
    u = ev(pg, "() => NMSKMusHide.order()[0]")
    d0 = drawn_of(pg, u["ids"])
    h0 = ev(pg, "() => NMSKHistory.state().len")
    s0 = ev(pg, "() => JSON.stringify(NMSKHistory.snapshot())")
    ev(pg, "() => NMSKMusHide.trace(true)")
    tap(pg, "#mh-next", phone, tag, "C Hide next")
    mid = ev(pg, "(ids) => ({fading:NMSKMusHide.state().fading, drawn:NMSKQ309.drawnOf(ids)})", u["ids"])
    t = wait_fade(pg)
    end = drawn_of(pg, u["ids"])
    txt = ev(pg, "() => document.getElementById('mh-state').textContent")
    tr = ev(pg, "() => NMSKMusHide.trace()")
    fo = fade_curve(tr, u["ids"])
    R["C"] = {"unit": u, "d0": d0, "mid": mid, "t": t, "end": end, "txt": txt, "curve": fo}
    check("%s C %s is drawn while it fades (%d of %d meshes, %d fading, read in one go)" % (tag, u["name"], mid["drawn"], d0, mid["fading"]),
          d0 > 0 and mid["fading"] > 0 and mid["drawn"] == d0)
    check("%s C a smooth fade out: first frame %.2f, never rising, lasted %d ms over %d frame(s) %s" % (tag, fo["first"], fo["ms"], fo["frames"], fo.get("vals")),
          fo["frames"] >= 4 and fo["first"] >= 0.9 and fo["mono"] == "down" and fo["ms"] >= 240)
    check("%s C the fade ends and then it is not drawn (%d)" % (tag, end), t >= 0 and end == 0)
    check("%s C the status names it, its region and its layer (%r)" % (tag, txt[:90]), u["name"] in txt and "layer 1 of" in txt)
    # ---------------- E (on this step)
    Q.settle(pg)
    h1 = ev(pg, "() => NMSKHistory.state().len")
    s1 = ev(pg, "() => JSON.stringify(NMSKHistory.snapshot())")
    check("%s E one step is one history entry (%d -> %d)" % (tag, h0, h1), h1 == h0 + 1)
    pg.keyboard.press("Control+z"); pg.wait_for_timeout(600)
    check("%s E Ctrl+Z restores the exact prior state, muscle drawn again (%d)" % (tag, drawn_of(pg, u["ids"])),
          ev(pg, "() => JSON.stringify(NMSKHistory.snapshot())") == s0 and drawn_of(pg, u["ids"]) == d0)
    pg.keyboard.press("Control+y"); pg.wait_for_timeout(600)
    check("%s E Ctrl+Y puts it back hidden" % tag, ev(pg, "() => JSON.stringify(NMSKHistory.snapshot())") == s1 and drawn_of(pg, u["ids"]) == 0)
    # ---------------- C: Back
    ev(pg, "() => NMSKMusHide.trace(true)")
    tap(pg, "#mh-back", phone, tag, "C Back")
    midb = ev(pg, "(ids) => ({fading:NMSKMusHide.state().fading, drawn:NMSKQ309.drawnOf(ids)})", u["ids"])
    tb = wait_fade(pg)
    fi = fade_curve(ev(pg, "() => NMSKMusHide.trace()"), u["ids"])
    check("%s C Back: drawn at once (%d of %d), fading in from %.2f, rising, %d ms" % (tag, midb["drawn"], d0, fi["first"], fi["ms"]),
          midb["drawn"] == d0 and fi["frames"] >= 4 and fi["first"] <= 0.1 and fi["mono"] == "up" and fi["ms"] >= 240 and tb >= 0
          and ev(pg, "() => NMSKMusHide.state().hidden") == 0 and drawn_of(pg, u["ids"]) == d0)
    # ---------------- D
    for _ in range(3):
        tap(pg, "#mh-next", phone, tag, "D Hide next")
        pg.wait_for_timeout(120)
    wait_fade(pg)
    d = ev(pg, "() => ({chips:document.querySelectorAll('#mh-list .mh-chip').length, st:NMSKMusHide.state(), o:NMSKMusHide.order().slice(0, 3)})")
    check("%s D three steps -> three chips, %d muscles hidden" % (tag, d["st"]["hidden"]), d["chips"] == 3 and d["st"]["steps"] == 3)
    second = d["o"][1]
    tap(pg, "#mh-list .mh-chip[data-k='1']", phone, tag, "D the second chip")
    wait_fade(pg)
    check("%s D the chip brought back %s only" % (tag, second["name"]),
          drawn_of(pg, second["ids"]) == len(second["ids"]) and drawn_of(pg, d["o"][0]["ids"]) == 0 and ev(pg, "() => NMSKMusHide.state().steps") == 2)
    tap(pg, "#mh-all", phone, tag, "D Show all")
    wait_fade(pg)
    check("%s D Show all: nothing hidden, the first muscle drawn again" % tag,
          ev(pg, "() => NMSKMusHide.state().hidden") == 0 and drawn_of(pg, d["o"][0]["ids"]) == len(d["o"][0]["ids"]))
    # ---------------- F
    pg.evaluate("() => document.getElementById('mh-region').scrollIntoView({block:'center'})")
    pg.select_option("#mh-region", "sole")
    pg.wait_for_timeout(250)
    f = ev(pg, "() => { const o = NMSKMusHide.order(); return {regions:[...new Set(o.map(u => u.region))], layers:o.map(u => u.layer), next:NMSKMusHide.state().next, first:o[0] && o[0].key}; }")
    check("%s F the select walks only the sole (%s), layers %s" % (tag, f["regions"], f["layers"]),
          f["regions"] == ["sole"] and f["layers"] == sorted(f["layers"]) and f["layers"][:1] == [1] and f["layers"][-1:] == [4] and f["next"] == f["first"])
    tap(pg, "#mh-next", phone, tag, "F Hide next in the sole")
    wait_fade(pg)
    ff = ev(pg, "() => ({st:NMSKMusHide.state(), txt:document.getElementById('mh-state').textContent})")
    check("%s F the first sole step is a 1st-layer muscle (%r)" % (tag, ff["txt"][:80]), "Sole of the foot" in ff["txt"] and "layer 1 of 4" in ff["txt"])
    ev(pg, "() => { NMSKMusHide.clear(); NMSKMusHide.setRegion('all'); }")
    wait_fade(pg)
    # ---------------- G
    g = ev(pg, """(k) => { const ids = NMSKSysMap.regions(k).filter(r => r.key === 'forearm_ant')[0].layers[1].ids;
        const id = ids[0]; NMSKQuick.open(id, null, null);
        const row = document.querySelector('.qc .mh-card'); return {id, row: row ? row.textContent : null}; }""", k)
    pg.wait_for_timeout(300)
    ok_card = g["row"] is not None
    check("%s G the quick card shows the muscle's region and layer (%r)" % (tag, g["row"]), ok_card and "layer 2 of 3" in (g["row"] or ""))
    if ok_card and tap(pg, "#mh-card-hide", phone, tag, "G Fade out on the card"):
        pg.wait_for_timeout(60)
        gm = ev(pg, "() => NMSKMusHide.state().fading")
        wait_fade(pg)
        check("%s G it fades (%d fading) and ends hidden, listed once" % (tag, gm),
              gm > 0 and drawn_of(pg, [g["id"]]) == 0 and ev(pg, "(id) => NMSKMusHide.hidden().indexOf(id) >= 0", g["id"]) and ev(pg, "() => NMSKMusHide.state().steps") == 1)
    ev(pg, "() => { NMSKMusHide.clear(); if (window.NMSKQuick && NMSKQuick.close) NMSKQuick.close(); }")
    wait_fade(pg)
    # ---------------- H
    hp = ev(pg, """() => { const A = window.__poseApi; if (!A || !A.ready()) return {pose:false};
        let J = A.rig().joints || []; if (!Array.isArray(J)) J = Object.keys(J).map(k => Object.assign({id:k}, J[k]));
        J = J.filter(j => j && !j.driven && j.dof && j.dof.length);
        J.sort((a, b) => (['shoulder_r', 'elbow_r', 'hip_r', 'knee_r'].indexOf(a.id) + 1 || 99) - (['shoulder_r', 'elbow_r', 'hip_r', 'knee_r'].indexOf(b.id) + 1 || 99));
        let moved = null;
        for (const j of J){ for (const d of j.dof){ A.set(j.id, d.k, d.lo + 0.7 * (d.hi - d.lo)); if (!A.isRest()){ moved = j.id + '.' + d.k; break; } } if (moved) break; }
        return {pose:!!moved, moved, rest:A.isRest()}; }""")
    pg.wait_for_timeout(600)
    ev(pg, "() => { const b = document.getElementById('t-cut'); if (b) b.click(); }")
    pg.wait_for_timeout(700)
    ev(pg, "() => { const b = document.getElementById('t-labels'); if (b && b.getAttribute('aria-pressed') !== 'true') b.click(); }")
    pg.wait_for_timeout(700)
    cut0 = ev(pg, "() => { const b = document.getElementById('cut-exit'); return !!(b && b.offsetParent !== null) || /on|true/.test(String((document.getElementById('t-cut') || {}).getAttribute && document.getElementById('t-cut').getAttribute('aria-pressed'))); }")
    lab0 = ev(pg, "() => { const b = document.getElementById('t-labels'); return !!b && b.getAttribute('aria-pressed') === 'true'; }")
    hu = ev(pg, "() => NMSKMusHide.order()[0]")
    hd0 = drawn_of(pg, hu["ids"])
    ev(pg, "() => NMSKMusHide.next()")
    pg.wait_for_timeout(60)
    hmid = ev(pg, "() => NMSKMusHide.state().fading")
    wait_fade(pg)
    hend = drawn_of(pg, hu["ids"])
    after = ev(pg, """() => ({rest: window.__poseApi ? __poseApi.isRest() : null,
        cut: (function(){ const b = document.getElementById('cut-exit'); return !!(b && b.offsetParent !== null) || /on|true/.test(String((document.getElementById('t-cut') || {}).getAttribute && document.getElementById('t-cut').getAttribute('aria-pressed'))); })(),
        lab: (function(){ const b = document.getElementById('t-labels'); return !!b && b.getAttribute('aria-pressed') === 'true'; })()})""")
    R["H"] = {"pose": hp, "cut": cut0, "labels": lab0, "d0": hd0, "fading": hmid, "end": hend, "after": after}
    check("%s H posed (%s), cut on (%s), labels on (%s): %s fades (%d) and ends hidden (%d -> %d)" % (tag, hp.get("moved"), cut0, lab0, hu["name"], hmid, hd0, hend),
          hp.get("pose") and hmid > 0 and hend == 0 and (hd0 > 0 or cut0))
    check("%s H the pose, the cut and the labels are still on afterwards (%s)" % (tag, after),
          after["rest"] is False and after["cut"] == cut0 and after["lab"] == lab0)
    ev(pg, "() => { NMSKMusHide.clear(); if (window.__poseApi) __poseApi.reset(); const b = document.getElementById('cut-exit'); if (b) b.click(); }")
    wait_fade(pg)
    pg.wait_for_timeout(500)
    # ---------------- I
    ev(pg, "() => NMSKMusHide.next()")
    wait_fade(pg)
    n0 = ev(pg, "() => NMSKMusHide.state().hidden")
    open_box(pg, phone, tag)
    ev(pg, "() => NMSKSysPeel.setScope('body')")
    pg.wait_for_timeout(250)
    tap(pg, "#sp-in", phone, tag, "I the whole-body In tap")
    pg.wait_for_timeout(500)
    wb = ev(pg, "() => ({wb:NMSKPeel.step(), mine:NMSKSysPeel.ids().length, mh:NMSKMusHide.state().hidden, vet:NMSKMusHide.ids().length})")
    check("%s I whole body steps Q301's NMSKPeel (%d), the scoped peel vetoes nothing, the %d hidden muscle(s) stay" % (tag, wb["wb"], n0),
          wb["wb"] == 1 and wb["mine"] == 0 and wb["mh"] == n0 and wb["vet"] == n0)
    ev(pg, "() => { NMSKSysPeel.set(0); NMSKMusHide.clear(); }")
    wait_fade(pg)
    # ---------------- J
    if phone:
        open_box(pg, phone, tag)
        ov = ev(pg, "() => ({sw:document.scrollingElement.scrollWidth, w:innerWidth, box:(function(){ const r = document.getElementById('mh-box').getBoundingClientRect(); return [Math.round(r.left), Math.round(r.right)]; })()})")
        check("%s J no horizontal overflow (%s)" % (tag, ov), ov["sw"] <= ov["w"] and ov["box"][0] >= 0 and ov["box"][1] <= ov["w"])


def run_page(page_dir: Path, only=0):
    tag0 = Q.KEY.get(page_dir.name, page_dir.name)
    html = V.html_of(page_dir)
    srv, port = V.serve(page_dir)
    try:
        with sync_playwright() as pl:
            b = pl.chromium.launch(args=V.LAUNCH_ARGS, executable_path="/opt/pw-browsers/chromium")
            for (w, h), phone in (((1400, 900), False), ((390, 844), True)):
                if only and w != only:
                    continue
                tag = "%s_%d" % (tag0, w)
                R = REPORT.setdefault(tag, {})
                ctx = b.new_context(viewport={"width": w, "height": h}, has_touch=phone, is_mobile=phone, device_scale_factor=1)
                pg = ctx.new_page()
                perr: list = []
                pg.on("pageerror", lambda e: perr.append(str(e)))
                pg.route("**/*", V.route)
                pg.goto("http://127.0.0.1:%d/%s" % (port, html), wait_until="load", timeout=180000)
                Q.ready(pg)
                print("\n--- %s ---" % tag)
                try:
                    run_view(pg, tag, phone, R)
                except Exception as e:  # a crash is a FAIL with its reason, never a silent pass
                    check("%s the run completed (%s)" % (tag, str(e).splitlines()[0][:160]), False)
                R["pageErrors"] = perr
                check("%s J 0 page errors %s" % (tag, perr[:2]), not perr)
                ctx.close()
            b.close()
    finally:
        srv.terminate()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pages", nargs="+")
    ap.add_argument("--viewport", type=int, default=0)
    ap.add_argument("--json", default="")
    a = ap.parse_args()
    for p in a.pages:
        run_page(Path(p), a.viewport)
    if a.json:
        Path(a.json).write_text(json.dumps(REPORT, indent=1, default=str), encoding="utf-8")
    print("\nQ391 VERIFY: %d OK / %d FAIL" % (OK[0], len(BAD)))
    for e in BAD:
        print("  FAIL " + e)
    print("Q391_LAYERS_OK" if not BAD else "Q391_LAYERS_FAIL")
    return 0 if not BAD else 1


if __name__ == "__main__":
    raise SystemExit(main())
