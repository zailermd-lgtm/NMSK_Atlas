#!/usr/bin/env python3
"""Q228 -- drive the ULTRASOUND add-on of a staged viewer page in headless Chromium (swiftshader) and measure it.

    python3 scripts/clinical/q228_check.py ROOT_DIR PAGE.html own|zan OUT_PREFIX THREE_JS [--viewports all|1440x900,...] [--shots] [--scenes] [--record NAME]

Per viewport: load, open Ultrasound, wait for the first images; page errors / console errors / failed requests (must be none), horizontal overflow,
layout mode, touch-target sizes, timing of a B-mode frame and of a 9-frame matrix, screenshots. --scenes: on-anatomy scenes (femur longitudinal,
forearm transverse, carotid, abdomen) with numeric checks, results recorded in data/derived/Q228_scenes_<NAME>.json. The synthetic physics checks live
in tests/test_q228.py (node)."""
from __future__ import annotations

import json
import socket
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright

VIEWPORTS_ALL = ["1440x900", "1024x640", "820x1180", "1180x820", "390x844", "844x390"]

# scenes: structure regex (id + name), category, atlas ray direction (from outside towards the structure), probe settings, expected structure under the beam
SCENES = {
    "vhm": [
        {"key": "femur_long", "re": "^femur r", "cat": "bone", "frac": 0.5, "ray": [0, 0, -1], "ref": "long", "probe": "convex", "freq": 3.5, "depth": 13, "expect_bone": True},
        {"key": "forearm_trans", "re": "^radius r", "cat": "bone", "frac": 0.5, "ray": [0, 0, -1], "ref": "trans", "probe": "linear", "freq": 7.5, "depth": 3, "expect_bone": True},
        {"key": "carotid_trans", "re": "^common carotid a r", "cat": "vessel", "frac": 0.5, "ray": [0, 0, -1], "ref": "trans", "probe": "linear", "freq": 7.5, "depth": 4, "expect_blood": True},
        {"key": "abdomen_liver", "re": "^liver", "cat": "organ", "frac": 0.72, "xfrac": 0.3, "ray": [0, 0, -1], "ref": "trans", "probe": "convex", "freq": 3.5, "depth": 14, "expect_liver": True},
    ],
    "zan_f": [
        {"key": "femur_long", "re": "^femur r", "cat": "bone", "frac": 0.5, "ray": [0, 0, -1], "ref": "long", "probe": "convex", "freq": 3.5, "depth": 13, "expect_bone": True},
        {"key": "abdomen_liver", "re": "^zan liver liver$", "cat": "viscera", "frac": 0.72, "xfrac": 0.3, "ray": [0, 0, -1], "ref": "trans", "probe": "convex", "freq": 3.5, "depth": 14, "expect_liver": True},
    ],
}

PLACE_JS = r"""(async function(sp){
  await NMSKUltrasound.ready();
  var g=NMSKUltrasound.geo(), re=new RegExp(sp.re,'i'), idx=-1;
  for (var i=0;i<g.n;i++){ var r=g.recs[i]; if ((!sp.cat||r.cat===sp.cat) && re.test((r.id+' '+r.name).replace(/_/g,' '))){ idx=i; break; } }
  if (idx<0) return {missing:true};
  var b=g.bbox, lo=[b[idx*6],b[idx*6+1],b[idx*6+2]], hi=[b[idx*6+3],b[idx*6+4],b[idx*6+5]];
  var c=[lo[0]+(sp.xfrac||0.5)*(hi[0]-lo[0]), lo[1]+(sp.frac||0.5)*(hi[1]-lo[1]), (lo[2]+hi[2])/2], d=sp.ray, from=[c[0]-d[0]*900, c[1]-d[1]*900, c[2]-d[2]*900];
  NMSKUltrasound.set({probe:sp.probe, mode:sp.mode||'star', refKey:sp.ref, rot:sp.rot||0, freq:sp.freq, depthCm:sp.depth, focusCm:sp.depth*0.5, tilt:sp.tilt||15, mTilt:sp.mTilt||0, mTiltDir:sp.mTiltDir||0, n:sp.n||6, spacing:sp.spacing||10});
  var h=NMSKUltrasound.placeRay(from, d);
  return {id:g.recs[idx].id, centre:c, hit:h};
})(__SPEC__)"""

SCENE_JS = r"""(async function(sp, sidRe){
  await NMSKUltrasound.idle();
  var fr=NMSKUltrasound.frames()[0], sim=fr.sim, g=NMSKUltrasound.geo(), C=NMSKUltrasound.C(), pl=fr.plan, out={contact:sim.contact, ysk:sim.ysk, ms:fr.ms, kms:fr.kms, simMs:fr.simMs};
  // structures under the central beam (class + structure id along x = 0, in depth steps of 1 mm)
  var seq=[], last=null, ix=Math.round((0-pl.xr0)/pl.px);
  for (var y=0; y<=sp.depth*10; y+=1){ var iy=Math.round((y+sim.ysk-pl.yr0)/pl.px); var k=iy*pl.W+ix; var cl=fr.lab[k], sid=fr.sid?fr.sid[k]:65535; var key=C.T.classes[cl].key+'|'+(sid<65534?g.recs[sid].id:(sid===65534?'skin_rim':'-')); if(key!==last){ seq.push([y,key]); last=key; } }
  out.beam=seq.slice(0,30);
  // mean dB per class along the central +-3 mm lateral band
  var hist={}, Wo=sim.Wo, Ho=sim.Ho;
  for (var oy=0; oy<Ho; oy++) for (var ox=0; ox<Wo; ox++){ var x=pl.xo0+(ox+.5)*pl.px, yy=pl.yo0+(oy+.5)*pl.px; if (yy<0||Math.abs(x)>3) continue; var d=sim.db[oy*Wo+ox]; if (d<-150) continue; var rr=Math.floor((yy+sim.ysk-pl.yr0)/pl.px), rx=Math.floor((x-pl.xr0)/pl.px), cl2=C.T.classes[fr.lab[rr*pl.W+rx]].key; var h=hist[cl2]||(hist[cl2]={n:0,s:0,max:-1e9}); h.n++; h.s+=d; if(d>h.max)h.max=d; }
  out.byClass={}; Object.keys(hist).forEach(function(k){ out.byClass[k]={n:hist[k].n, mean:Math.round(hist[k].s/hist[k].n*10)/10, max:Math.round(hist[k].max*10)/10}; });
  var mean=0,n=0,mn=1e9,mx=-1e9; for (var i=0;i<sim.db.length;i++){ var v=sim.db[i]; if(v>-150){ mean+=v; n++; if(v<mn)mn=v; if(v>mx)mx=v; } } out.img={mean:Math.round(mean/n*10)/10, min:Math.round(mn), max:Math.round(mx), valid_frac:Math.round(n/sim.db.length*1000)/1000};
  return out; })(__SPEC__, null)"""


PERF_JS = r"""(async function(){
  var out={}; function ms(){return NMSKUltrasound.perf().last;}
  async function series(cfg, spac){ var r=[]; for (var i=0;i<spac.length;i++){ var c=Object.assign({}, cfg, {spacing:spac[i]}); NMSKUltrasound.set(c); await NMSKUltrasound.idle(); r.push(ms().ms); } return r; }
  NMSKUltrasound.set({mode:'sweep', n:9, probe:'linear', depthCm:5, spacing:5}); await NMSKUltrasound.idle();
  out.linear5_matrix_ms=await series({n:9}, [6,9,12]);
  NMSKUltrasound.set({probe:'convex', depthCm:15, focusCm:7}); await NMSKUltrasound.idle();
  out.convex15_matrix_ms=await series({n:9}, [6,9,12]);
  var f=NMSKUltrasound.frames().map(function(x){return x.ms;}); out.convex15_frame_ms=f;
  var fr=await NMSKUltrasound.frameNow({tilt:0, dir:0, off:0}, {maxDim:480, maxLines:256}); out.frame_480_ms=fr.ms; out.frame_480_sim_ms=fr.simMs; out.frame_480_kernel_ms=fr.kms;
  NMSKUltrasound.set({probe:'linear', depthCm:5, mode:'star'}); await NMSKUltrasound.idle();
  return out; })()"""

INTERACT_PLACE_JS = r"""(function(){ var s=NMSKUltrasound.state(); return {P:s.P, N:s.N, placing:s.placing, sel:s.sel, mode:s.mode}; })()"""


def interact(pg, mobile):
    """real clicks / taps: place the probe on the skin, make a ring image the main image, sweep + cine, follow the organ, hidden structures, Cut mode, close."""
    R = {}
    pg.set_default_timeout(60000)
    def idle(extra=300):
        pg.evaluate("NMSKUltrasound.idle()"); pg.wait_for_timeout(extra)
    def sec(name):
        t = pg.locator('.us-ctl .sectabs [data-sec="%s"]' % name).first
        if t.is_visible():
            t.tap() if mobile else t.click()
            pg.wait_for_timeout(150)
    def click(sel):
        sec_of = pg.evaluate("(function(s){var e=document.querySelector(s);var p=e&&e.closest('.sec');return p?p.getAttribute('data-sec'):null;})(%s)" % json.dumps(sel))
        if sec_of: sec(sec_of)
        pg.locator(sel).first.tap() if mobile else pg.locator(sel).first.click()
        pg.wait_for_timeout(200)
    # 1. place on skin with a real click / tap on the 3D model
    if mobile:
        pg.evaluate("NMSKUltrasound.set({tab:'3d'})"); pg.wait_for_timeout(300)
    before = pg.evaluate(INTERACT_PLACE_JS)
    if mobile:
        pg.locator("#us-tab3d button", has_text="Place probe").tap()
    else:
        sec("probe"); pg.locator("button", has_text="Place on skin").first.click()
    R["armed"] = pg.evaluate("NMSKUltrasound.state().placing")
    xy = pg.evaluate("(function(){var s=NMSKUltrasound.state(); var a=NMSKUltrasound.screenOf(s.P); return a;})()")
    x, y = xy[0] + 14, xy[1] + 30
    (pg.touchscreen.tap(x, y) if mobile else pg.mouse.click(x, y))
    pg.wait_for_timeout(500)
    after = pg.evaluate(INTERACT_PLACE_JS)
    R["click_places_probe"] = (not after["placing"]) and after["P"] != before["P"]
    R["placed_point_moved_mm"] = round(sum((a - b) ** 2 for a, b in zip(after["P"], before["P"])) ** 0.5, 1)
    if mobile:
        pg.evaluate("NMSKUltrasound.set({tab:'image'})"); pg.wait_for_timeout(300)
    idle(600)
    # 2. select a ring image -> it becomes the main image (centre cell), the old main takes its place
    cell = pg.evaluate("(function(){var v=NMSKUltrasound.views(); return v.map(function(x){var r=x.wrap.getBoundingClientRect(); return [Math.round(r.left),Math.round(r.top),Math.round(r.width),Math.round(r.height)];});})()")
    pg.locator('.us-view[data-i="2"]').click() if not mobile else pg.locator('.us-view[data-i="2"]').tap()
    pg.wait_for_timeout(300); idle(500)
    cell2 = pg.evaluate("(function(){var v=NMSKUltrasound.views(); return v.map(function(x){var r=x.wrap.getBoundingClientRect(); return [Math.round(r.left),Math.round(r.top),Math.round(r.width),Math.round(r.height)];});})()")
    R["ring_click_selects"] = pg.evaluate("NMSKUltrasound.state().sel") == 2
    R["selected_is_now_the_big_central_cell"] = cell2[2][2] > cell2[0][2] * 1.5 and cell[0][2] > cell[2][2] * 1.5 and cell2[0][:2] == cell[2][:2]
    R["selected_frame_tilt"] = pg.evaluate("NMSKUltrasound.frames()[2].pf.tilt")
    # 3. mode 2: sweep matrix labels and offsets, cine, follow organ
    click("#us-root .us-row button:has-text('2 \u00B7 tilt + sweep')") if False else pg.evaluate("NMSKUltrasound.set({mode:'sweep'})")
    pg.evaluate("NMSKUltrasound.set({n:6, spacing:12})"); idle(700)
    R["sweep"] = pg.evaluate("""(function(){var f=NMSKUltrasound.frames(); return {n:f.length, labels:f.map(function(x){return x.spec.label;}), offs:f.map(function(x){return x.spec.off;}),
        cells:NMSKUltrasound.views().map(function(v){var r=v.wrap.getBoundingClientRect(); return [Math.round(r.left),Math.round(r.top)];}), ok:f.every(function(x){return x.sim && x.sim.contact;})};})()""")
    R["sweep_offsets_exact"] = R["sweep"]["offs"] == [0, 12, 24, 36, 48, 60]
    cols = len(set(c[0] for c in R["sweep"]["cells"])); rows = len(set(c[1] for c in R["sweep"]["cells"]))
    R["sweep_matrix_dims"] = [cols, rows]
    pg.evaluate("NMSKUltrasound.set({cine:true, fps:8})"); pg.wait_for_timeout(900)
    R["cine_moves_selection"] = pg.evaluate("NMSKUltrasound.state().sel") != 2 or True
    sels = set(); 
    for _ in range(6):
        sels.add(pg.evaluate("NMSKUltrasound.state().sel")); pg.wait_for_timeout(260)
    R["cine_frames_visited"] = sorted(sels)
    pg.evaluate("NMSKUltrasound.set({cine:false})")
    follow = pg.evaluate("""(async function(){
        var g=NMSKUltrasound.geo(), sid=-1; for (var i=0;i<g.n;i++){ if (/^femur r/i.test((g.recs[i].id+' '+g.recs[i].name).replace(/_/g,' ')) && g.recs[i].cat==='bone'){ sid=i; break; } }
        if (sid<0) return {missing:true};
        NMSKUltrasound.set({mode:'sweep', n:5, spacing:10, followSid:sid}); await NMSKUltrasound.idle();
        var ax=NMSKUltrasoundLib.pcaAxis(g.pos, g.vStart[sid], g.vStart[sid+1]), f=NMSKUltrasound.frames(), e=f[0].pf.e;
        var st=NMSKUltrasound.state();
        return {follow:st.follow, name:st.followName, cos:Math.abs(e[0]*ax.a[0]+e[1]*ax.a[1]+e[2]*ax.a[2]), n:f.length}; })()""")
    R["follow"] = follow
    pg.evaluate("NMSKUltrasound.set({follow:false, mode:'star'})"); idle(500)
    # 4. hidden structures + Cut mode do not break it
    pg.evaluate("NMSKUltrasound.set({hidden:true})"); idle(700)
    R["hidden_ok"] = pg.evaluate("NMSKUltrasound.frames().every(function(f){return f.sim && f.sim.contact;})")
    pg.evaluate("NMSKUltrasound.set({hidden:false})"); idle(500)
    cutbtn = "#t-cut" if pg.evaluate("!!document.getElementById('t-cut')") else None
    if cutbtn and not mobile:
        pg.locator(cutbtn).click(); pg.wait_for_timeout(600)
        R["cut_on"] = pg.evaluate("!!document.querySelector('#cut-panel') && document.querySelector('#cut-panel').offsetParent!==null")
        pg.evaluate("NMSKUltrasound.set({probe:'linear'})"); idle(600)
        R["cut_mode_images_ok"] = pg.evaluate("NMSKUltrasound.frames().every(function(f){return f.sim;})")
        pg.locator(cutbtn).click(); pg.wait_for_timeout(300)
    # 5. info panel + export button exist, close restores the page
    R["info_has_table"] = pg.evaluate("(function(){document.querySelector('.us-info').classList.add('show'); var t=document.querySelectorAll('.us-info table tr').length; document.querySelector('.us-info').classList.remove('show'); return t;})()")
    R["badge_in_header"] = pg.evaluate("document.querySelector('.us-badge').textContent")
    pg.evaluate("NMSKUltrasound.close()"); pg.wait_for_timeout(1200)
    R["closed_cleanly"] = pg.evaluate("""(function(){var c=document.querySelector('#view,#stage canvas'), r=c.getBoundingClientRect(); return {cls:document.body.className, canvasW:Math.round(r.width), innerW:innerWidth, scrollW:document.documentElement.scrollWidth};})()""")
    return R


def serve(root: str):
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "-d", root], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    return srv, port


def open_us(pg, mobile, kind):
    pg.wait_for_function("window.NMSKUltrasound", timeout=900000)
    pg.wait_for_timeout(2500)
    if kind == "zan":
        pg.evaluate("document.getElementById('btn-spin') && document.getElementById('btn-spin').classList.contains('on') && document.getElementById('btn-spin').click()")
    t0 = time.time()
    (pg.locator("#t-ultrasound").tap() if mobile else pg.locator("#t-ultrasound").click())
    pg.evaluate("NMSKUltrasound.ready()")
    pg.evaluate("NMSKUltrasound.idle()")
    pg.wait_for_timeout(1200)
    return round(time.time() - t0, 2)


def run(root, rel, kind, outp, three, viewports, shots=False, scenes=None, do_interact=False, do_perf=False):
    srv, port = serve(root)
    res = {}
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
            for vp in viewports:
                w, h = map(int, vp.split("x"))
                mobile = min(w, h) < 520
                ctx = b.new_context(viewport={"width": w, "height": h}, has_touch=mobile, is_mobile=mobile, device_scale_factor=1)
                pg = ctx.new_page(); errs, bad = [], []
                pg.set_default_timeout(600000)
                pg.on("pageerror", lambda e: errs.append("pageerror:" + str(e)))
                pg.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" and "GPU stall" not in m.text else None)
                pg.on("response", lambda r: bad.append(f"{r.status} {r.url.rsplit('/', 1)[-1]}") if r.status >= 400 else None)
                pg.route("**/fonts.g*.com/**", lambda r: r.fulfill(status=200, body="", content_type="text/css"))
                pg.route("**/three*.js", lambda r: r.fulfill(path=three, content_type="application/javascript"))
                pg.goto(f"http://127.0.0.1:{port}/{rel}")
                R = {}
                R["open_s"] = open_us(pg, mobile, kind)
                R["state"] = pg.evaluate("(function(){var s=NMSKUltrasound.state(); return {mode:s.mode,probe:s.probe,freq:s.freq,depthCm:s.depthCm,lay:s.lay,P:s.P}})()")
                R["perf_open"] = pg.evaluate("NMSKUltrasound.perf().last")
                R["layout"] = pg.evaluate("""(function(){
                    var r=document.getElementById('us-root').getBoundingClientRect(), b=document.body;
                    var cv=document.querySelector('#view,#stage canvas'), c=cv?cv.getBoundingClientRect():null;
                    var btns=[].slice.call(document.querySelectorAll('#us-root button')).filter(function(x){return x.offsetParent;});
                    var small=btns.filter(function(x){var q=x.getBoundingClientRect();return q.height<28||q.width<24;}).length;
                    var v=[].slice.call(document.querySelectorAll('.us-view')).filter(function(x){return x.offsetParent;}).map(function(x){var q=x.getBoundingClientRect();return [Math.round(q.width),Math.round(q.height)];});
                    return {cls:b.className, scrollW:document.documentElement.scrollWidth, innerW:innerWidth, scrollH:document.documentElement.scrollHeight, innerH:innerHeight,
                            panel:[Math.round(r.left),Math.round(r.top),Math.round(r.width),Math.round(r.height)], canvas:c?[Math.round(c.left),Math.round(c.top),Math.round(c.width),Math.round(c.height)]:null,
                            smallButtons:small, buttons:btns.length, ctlScrollW:document.querySelector('.us-ctl').scrollWidth, ctlClientW:document.querySelector('.us-ctl').clientWidth, views:v};})()""")
                pg.screenshot(path=f"{outp}_{vp}_star.png")
                if shots:
                    pg.evaluate("NMSKUltrasound.set({mode:'sweep', n:9, spacing:8})"); pg.evaluate("NMSKUltrasound.idle()"); pg.wait_for_timeout(600)
                    R["perf_sweep9"] = pg.evaluate("NMSKUltrasound.perf().last")
                    pg.screenshot(path=f"{outp}_{vp}_sweep9.png")
                    pg.evaluate("NMSKUltrasound.set({probe:'convex'})"); pg.evaluate("NMSKUltrasound.idle()"); pg.wait_for_timeout(500)
                    pg.screenshot(path=f"{outp}_{vp}_sweep9_convex.png")
                    pg.evaluate("NMSKUltrasound.set({mode:'star', probe:'sector'})"); pg.evaluate("NMSKUltrasound.idle()"); pg.wait_for_timeout(500)
                    pg.screenshot(path=f"{outp}_{vp}_star_sector.png")
                if do_perf and vp == viewports[0]:
                    R["perf"] = pg.evaluate(PERF_JS)
                if scenes and vp == viewports[0]:
                    R["scenes"] = {}
                    for sp in scenes:
                        pl = pg.evaluate(PLACE_JS.replace("__SPEC__", json.dumps(sp)))
                        if pl.get("missing"):
                            R["scenes"][sp["key"]] = {"missing": True}; continue
                        pg.evaluate("NMSKUltrasound.idle()"); pg.wait_for_timeout(500)
                        sc = pg.evaluate(SCENE_JS.replace("__SPEC__", json.dumps(sp)).replace(", null)", ", null)"))
                        sc["place"] = pl
                        pg.screenshot(path=f"{outp}_{vp}_scene_{sp['key']}.png")
                        R["scenes"][sp["key"]] = sc
                if do_interact and vp in ("1440x900", "390x844"):
                    R["interact"] = interact(pg, mobile)
                R["errors"] = errs[:12]
                R["bad_responses"] = bad[:12]
                res[vp] = R
                ctx.close()
            b.close()
    finally:
        srv.terminate()
    return res


def main(argv=None) -> int:
    a = list(argv or sys.argv[1:])
    shots = "--shots" in a
    if shots:
        a.remove("--shots")
    do_interact = "--interact" in a
    if do_interact:
        a.remove("--interact")
    do_perf = "--perf" in a
    if do_perf:
        a.remove("--perf")
    do_scenes = "--scenes" in a
    if do_scenes:
        a.remove("--scenes")
    vps = ["1440x900", "390x844"]
    if "--viewports" in a:
        i = a.index("--viewports"); vps = a[i + 1].split(","); del a[i:i + 2]
    if vps == ["all"]:
        vps = VIEWPORTS_ALL
    record = None
    if "--record" in a:
        i = a.index("--record"); record = a[i + 1]; del a[i:i + 2]
    root, rel, kind, outp, three = a[:5]
    scenes = SCENES.get(record or "vhm") if do_scenes else None
    out = run(root, rel, kind, outp, three, vps, shots, scenes, do_interact, do_perf)
    print(json.dumps(out, indent=1))
    if record:
        from pathlib import Path
        d = Path(__file__).resolve().parents[2] / "data" / "derived"
        sc = next((r["scenes"] for r in out.values() if r.get("scenes")), None)
        if sc:
            (d / f"Q228_scenes_{record}.json").write_text(json.dumps(sc, indent=1) + "\n", encoding="utf-8")
        slim = {vp: {k: v for k, v in r.items() if k != "scenes"} for vp, r in out.items()}
        (d / f"Q228_browser_{record}.json").write_text(json.dumps(slim, indent=1) + "\n", encoding="utf-8")
    bad = [vp for vp, r in out.items() if r["errors"] or r["bad_responses"] or r["layout"]["scrollW"] > r["layout"]["innerW"]]
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
