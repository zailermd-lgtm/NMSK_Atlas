#!/usr/bin/env python3
"""Q226 -- drive the IMAGING add-on of a staged viewer page in headless Chromium (swiftshader) and measure it.

    python3 scripts/clinical/q226_check.py ROOT_DIR PAGE.html own|zan OUT_PREFIX THREE_JS [--viewports 1440x900,390x844] [--shots]

Per viewport: load, open Imaging, wait for the first full images, then
  * page errors / console errors / failed requests (must be none),
  * layout: no horizontal overflow, panel and 3D region inside the viewport, split mode chosen (side / stack / tab),
  * timing of the first slice and of a re-slice after moving the cut plane,
  * screenshots (CT bone window, CT soft, MRI T1, T2, STIR, MIP, triplanar MPR, ...) when --shots.
Prints one JSON object. The numeric checks on known structures live in tests/test_q226.py (they use the same page)."""
from __future__ import annotations

import json
import socket
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright

# numeric check on real meshes: slice through the middle of known structures (axial through the bbox centre) and read the classes of the
# pixels the structure owns (sid raster) -- run inside the page, results compared in tests/test_q226.py
NUMERIC_JS = r"""(async function(specs){
  var g=NMSKImaging.geo(), C=NMSKImaging.C(), T=C.T, out={};
  for (var si=0; si<specs.length; si++){
    var sp=specs[si], re=new RegExp(sp.re,'i'), idx=-1;
    for (var i=0;i<g.n;i++){ var r=g.recs[i]; if ((!sp.cat||r.cat===sp.cat) && re.test((r.id+' '+r.name).replace(/_/g,' '))){ idx=i; break; } }
    if (idx<0){ out[sp.key]={missing:true}; continue; }
    var b=g.bbox, lo=[b[idx*6],b[idx*6+1],b[idx*6+2]], hi=[b[idx*6+3],b[idx*6+4],b[idx*6+5]];
    var O=[(lo[0]+hi[0])/2,lo[1]+(sp.frac||0.5)*(hi[1]-lo[1]),(lo[2]+hi[2])/2], W=256, fov=sp.fov||200, px=fov/W;
    var res=await NMSKImaging.sliceNow({O:O,n:[0,-1,0],W:W,fov:fov,offsets:[0],center:O});
    var lab=res.labels[0], sid=res.sid, hist={}, n=0, sx=0, sy=0;
    for (var k=0;k<lab.length;k++) if (sid[k]===idx){ var key=T.classes[lab[k]].key; hist[key]=(hist[key]||0)+1; n++; sx+=k%W; sy+=Math.floor(k/W); }
    var cx=n?Math.round(sx/n):0, cy=n?Math.round(sy/n):0, centre=T.classes[lab[cy*W+cx]].key, owner=sid[cy*W+cx];
    // nearest owned pixel to the centroid (the centroid of a ring can be outside the structure)
    var best=1e9, bk=-1; for (var k2=0;k2<lab.length;k2++) if (sid[k2]===idx){ var dx=k2%W-cx, dy=Math.floor(k2/W)-cy, d=dx*dx+dy*dy; if (d<best){best=d;bk=k2;} }
    out[sp.key]={id:g.recs[idx].id, cat:g.recs[idx].cat, cls:T.classes[g.cls[idx]].key, kind:g.kind[idx], pixels:n, area_mm2:Math.round(n*px*px), hist:hist, centreClass:centre, centreOwner:owner===idx, nearestClass: bk>=0?T.classes[lab[bk]].key:null,
      hu_centre: T.classes[lab[cy*W+cx]].ct.hu, parityBad: res.stats.parityBad, ms: res.stats.ms};
  }
  return out; })(__SPECS__)"""

NUMERIC_SPECS = {
    "vhf": [{"key": "femur_shaft", "re": "^femur r", "cat": "bone", "frac": 0.5, "fov": 120}, {"key": "femur_end", "re": "^femur r", "cat": "bone", "frac": 0.03, "fov": 160},
            {"key": "muscle", "re": "^rectus femoris r", "cat": "muscle", "frac": 0.5, "fov": 250}, {"key": "liver", "re": "^liver", "cat": "organ", "fov": 400},
            {"key": "vessel", "re": "^abdominal aorta", "cat": "vessel", "fov": 150}, {"key": "lung", "re": "^lung r", "cat": "organ", "fov": 400},
            {"key": "kidney", "re": "^kidney r", "cat": "organ", "fov": 200}, {"key": "spleen", "re": "^spleen", "cat": "organ", "fov": 200}],
    "vhm": [{"key": "femur_shaft", "re": "^femur r", "cat": "bone", "frac": 0.5, "fov": 120}, {"key": "femur_end", "re": "^femur r", "cat": "bone", "frac": 0.03, "fov": 160},
            {"key": "muscle", "re": "^rectus femoris r", "cat": "muscle", "frac": 0.5, "fov": 250}, {"key": "liver", "re": "^liver", "cat": "organ", "fov": 400},
            {"key": "vessel", "re": "^abdominal aorta", "cat": "vessel", "fov": 150}, {"key": "lung", "re": "^lung r", "cat": "organ", "fov": 400}],
    "zan_f": [{"key": "femur_shaft", "re": "^femur r", "cat": "bone", "frac": 0.5, "fov": 120}, {"key": "femur_end", "re": "^femur r", "cat": "bone", "frac": 0.03, "fov": 160},
              {"key": "muscle", "re": "^vastus lateralis r", "cat": "muscle", "frac": 0.5, "fov": 250}, {"key": "liver", "re": "^zan liver liver$", "cat": "viscera", "fov": 400},
              {"key": "vessel", "re": "^abdominal aorta", "cat": "vessel", "fov": 150}],
}
def interact(pg, mobile):
    """clicks / taps / buttons: crosshair <-> cut plane coupling, readout, slab modes, thickness, 3D slab link, close restores the page."""
    R = {}
    pg.set_default_timeout(30000)
    def idle(extra=500):
        pg.evaluate("NMSKImaging.idle()"); pg.wait_for_timeout(extra)
    tap = (lambda x, y: pg.touchscreen.tap(x, y)) if mobile else (lambda x, y: pg.mouse.click(x, y))
    click = (lambda sel: pg.locator(sel).first.tap()) if mobile else (lambda sel: pg.locator(sel).first.click())
    pg.evaluate("NMSKImaging.set({layout:'mpr', modality:'ct', ctWindow:'soft', thick:5, slab:'avg'})")
    if mobile:                                   # 4 views are stacked in a 2x2 grid even on the phone; make sure the controls do not hide them
        pg.evaluate("document.getElementById('img-root').classList.remove('ctl-off')")
    idle(900)
    st0 = pg.evaluate("NMSKImaging.state()")
    cs0 = pg.evaluate("(document.getElementById('cut-state')||{}).textContent")
    box = pg.locator('.img-view[data-view="co"]').bounding_box()
    tap(box["x"] + box["width"] * 0.5, box["y"] + box["height"] * 0.22)          # a point higher up in the coronal view
    idle(1200)
    st1 = pg.evaluate("NMSKImaging.state()"); cs1 = pg.evaluate("(document.getElementById('cut-state')||{}).textContent")
    R["click_coronal_moves_anchor"] = abs(st1["P"][1] - st0["P"][1]) > 5
    R["click_coronal_moves_cut_plane"] = cs0 != cs1
    R["cut_state"] = [cs0, cs1]
    box = pg.locator('.img-view[data-view="ax"]').bounding_box()
    tap(box["x"] + box["width"] * 0.6, box["y"] + box["height"] * 0.5)
    idle(900)
    ro = pg.locator(".img-read").text_content()
    R["readout"] = ro
    R["readout_has_tissue_and_hu"] = (" | " in ro) and ("HU" in ro)
    st2 = pg.evaluate("NMSKImaging.state()")
    R["axial_click_keeps_plane_y"] = abs(st2["P"][1] - st1["P"][1]) < 1.0
    def section(name):
        t = pg.locator('.img-ctl .sectabs [data-sec="%s"]' % name).first
        if t.is_visible():
            t.tap() if mobile else t.click()
            pg.wait_for_timeout(200)
    section("slab")
    click('.img-ctl [data-slab="mip"]')
    idle(600)
    R["mip_mode"] = pg.evaluate("NMSKImaging.state().slab") == "mip"
    click('.img-ctl [data-th="10"]')
    idle(600)
    R["thick_10"] = pg.evaluate("NMSKImaging.state().thick") == 10
    # slab set in the page's own Cut panel is adopted by the imaging panel
    pg.evaluate("(function(){var b=document.querySelector('#cut-thick [data-th=\"25\"]'); b && b.click();})()")
    try:
        pg.wait_for_function("NMSKImaging.state().thick === 25", timeout=30000)
    except Exception:
        pass
    R["cut_panel_slab_adopted"] = pg.evaluate("NMSKImaging.state().thick") == 25
    # 3D slab link pushes the imaging thickness to the cut panel
    click('.img-ctl [data-th="3"]')
    pg.evaluate("(function(){var b=[].slice.call(document.querySelectorAll('.img-ctl button')).filter(function(x){return x.textContent==='3D slab';})[0]; b && b.click();})()")
    pg.wait_for_timeout(600)
    R["cut_th_text_after_link"] = pg.evaluate("(document.getElementById('cut-th')||{}).textContent")
    # a quick numeric look at the images: not all black, not all white
    R["views_have_content"] = pg.evaluate("""(function(){var v=NMSKImaging.views(), ok={}; Object.keys(v).forEach(function(k){var a=v[k].val; if(!a){ok[k]=false;return;} var mn=1e9,mx=-1e9; for(var i=0;i<a.length;i+=7){if(a[i]<mn)mn=a[i]; if(a[i]>mx)mx=a[i];} ok[k]=mx-mn>100;}); return ok;})()""")
    # close restores the 3D page
    pg.evaluate("NMSKImaging.close()")
    pg.wait_for_timeout(1200)
    R["closed_cleanly"] = pg.evaluate("""(function(){var c=document.querySelector('#view,#stage canvas'), r=c.getBoundingClientRect(); return {cls:document.body.className, canvasW:Math.round(r.width), innerW:innerWidth, rootVisible:getComputedStyle(document.getElementById('img-root')).display};})()""")
    return R


NUMERIC_SPECS_PLACEHOLDER = None
# slab behaviour on real meshes: sub-slices 0..20 mm through the upper thigh (axial), HU per class; MIP >= average >= MinIP at every pixel, and the
# bone pixels (HU > 300) of the MIP grow with thickness while MinIP shrinks them
SLAB_JS = r"""(async function(){
  var g=NMSKImaging.geo(), C=NMSKImaging.C(), lut=NMSKImaging.lut('ct'), bb=g.bodyBox, y=bb.lo[1]+0.42*(bb.hi[1]-bb.lo[1]);
  var O=[(bb.lo[0]+bb.hi[0])/2,y,(bb.lo[2]+bb.hi[2])/2], offs=[]; for (var k=0;k<=20;k++) offs.push(k);
  var res=await NMSKImaging.sliceNow({O:O,n:[0,-1,0],W:256,fov:300,offsets:offs}), N=256*256, L=res.labels, out={sub:L.length}, ok=true, sMip=0, sMin=0, bone={single:0,mip5:0,mip20:0,min20:0,avg20:0};
  function stat(upTo,mode){ var c=0; for (var i=0;i<N;i++){ var mx=-1e9,mn=1e9,sum=0; for (var s=0;s<=upTo;s++){ var v=lut[L[s][i]]; if(v>mx)mx=v; if(v<mn)mn=v; sum+=v; } var val=mode==='mip'?mx:mode==='min'?mn:sum/(upTo+1); if(val>300)c++; } return c; }
  for (var i=0;i<N;i+=3){ var mx=-1e9,mn=1e9,sum=0; for (var s=0;s<L.length;s++){ var v=lut[L[s][i]]; if(v>mx)mx=v; if(v<mn)mn=v; sum+=v; } var av=sum/L.length; if(!(mx>=av-1e-6&&av>=mn-1e-6)) ok=false; if(mx>av+1)sMip++; if(mn<av-1)sMin++; }
  bone.single=stat(0,'avg'); bone.mip5=stat(5,'mip'); bone.mip20=stat(20,'mip'); bone.min20=stat(20,'min'); bone.avg20=stat(20,'avg');
  out.order_ok=ok; out.strict_mip=sMip; out.strict_min=sMin; out.bone_pixels=bone; return out; })()"""

VIEWPORTS_ALL = ["1440x900", "1024x640", "820x1180", "1180x820", "390x844", "844x390"]


def serve(root: str):
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1", "-d", root], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1)
    return srv, port


def run(root, rel, kind, outp, three, viewports, shots=False, eval_after=None, numeric=None, do_interact=False):
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
                pg.on("console", lambda m: errs.append("console:" + m.text) if m.type == "error" else None)
                pg.on("response", lambda r: bad.append(f"{r.status} {r.url.rsplit('/', 1)[-1]}") if r.status >= 400 else None)
                pg.route("**/fonts.g*.com/**", lambda r: r.fulfill(status=200, body="", content_type="text/css"))
                pg.route("**/three*.js", lambda r: r.fulfill(path=three, content_type="application/javascript"))
                pg.goto(f"http://127.0.0.1:{port}/{rel}")
                pg.wait_for_function("window.NMSKImaging", timeout=900000)
                pg.wait_for_timeout(2500)
                if kind == "zan":
                    pg.evaluate("document.getElementById('btn-spin') && document.getElementById('btn-spin').classList.contains('on') && document.getElementById('btn-spin').click()")
                R = {}
                t0 = time.time()
                if mobile:
                    pg.locator("#t-imaging").tap()
                else:
                    pg.locator("#t-imaging").click()
                pg.wait_for_function("NMSKImaging.geo() !== null", timeout=600000)
                R["geometry_s"] = round(time.time() - t0, 2)
                pg.wait_for_function("(function(){var v=NMSKImaging.views();return Object.keys(v).some(function(k){return v[k].stats&&v[k].stats.tier===1;});})()", timeout=600000)
                pg.evaluate("NMSKImaging.idle()")
                pg.wait_for_timeout(1500)
                R["state"] = pg.evaluate("NMSKImaging.state()")
                R["geo_timing"] = pg.evaluate("NMSKImaging.geo().timing")
                R["perf"] = pg.evaluate("""(async function(){
                    var g=NMSKImaging.geo(), bb=g.bodyBox, out={n:g.n, nv:g.nv, nt:g.nt}, ms=function(f){var t=performance.now();return f().then(function(){return Math.round(performance.now()-t);});};
                    var ys=[0.25,0.5,0.7].map(function(f){return bb.lo[1]+f*(bb.hi[1]-bb.lo[1]);});
                    out.axial512_ms=[]; for (var i=0;i<ys.length;i++){ var O=[(bb.lo[0]+bb.hi[0])/2,ys[i],(bb.lo[2]+bb.hi[2])/2]; out.axial512_ms.push(await ms(function(){return NMSKImaging.sliceNow({O:O,n:[0,-1,0],W:512,fov:500,offsets:[0]});})); }
                    var O2=[(bb.lo[0]+bb.hi[0])/2,ys[1],(bb.lo[2]+bb.hi[2])/2]; var offs=[]; for (var k=0;k<=24;k++) offs.push(k);
                    out.axial512_25sub_ms=await ms(function(){return NMSKImaging.sliceNow({O:O2,n:[0,-1,0],W:512,fov:500,offsets:offs});});
                    out.coronal512_ms=await ms(function(){return NMSKImaging.sliceNow({O:O2,n:[0,0,1],W:512,fov:1800,offsets:[0]});});
                    out.sagittal512_ms=await ms(function(){return NMSKImaging.sliceNow({O:O2,n:[-1,0,0],W:512,fov:1800,offsets:[0]});});
                    return out; })()""")
                R["first_slice_ms"] = pg.evaluate("NMSKImaging.perf().history.filter(function(x){return x.tier===1;}).slice(0,1)")
                R["layout"] = pg.evaluate("""(function(){
                    var r=document.getElementById('img-root').getBoundingClientRect(), b=document.body;
                    var cv=document.querySelector('#view,#stage canvas'), c=cv?cv.getBoundingClientRect():null;
                    var btns=[].slice.call(document.querySelectorAll('#img-root button')).filter(function(x){return x.offsetParent;});
                    var small=btns.filter(function(x){var q=x.getBoundingClientRect();return q.height<28||q.width<24;}).length;
                    return {cls:b.className, scrollW:document.documentElement.scrollWidth, innerW:innerWidth, scrollH:document.documentElement.scrollHeight, innerH:innerHeight,
                            panel:[Math.round(r.left),Math.round(r.top),Math.round(r.width),Math.round(r.height)], canvas:c?[Math.round(c.left),Math.round(c.top),Math.round(c.width),Math.round(c.height)]:null,
                            smallButtons:small, buttons:btns.length, ctlScrollW:document.querySelector('.img-ctl').scrollWidth, ctlClientW:document.querySelector('.img-ctl').clientWidth};})()""")
                pg.screenshot(path=f"{outp}_{vp}_open.png")
                if numeric:
                    R["numeric"] = pg.evaluate(NUMERIC_JS.replace("__SPECS__", json.dumps(numeric)))
                    R["slab"] = pg.evaluate(SLAB_JS)
                if eval_after:
                    R["eval"] = pg.evaluate(eval_after)
                if shots:
                    def go(patch, name, wait=900):
                        pg.evaluate("NMSKImaging.set(%s)" % json.dumps(patch)); pg.wait_for_timeout(300)
                        pg.evaluate("NMSKImaging.idle()"); pg.wait_for_timeout(wait)
                        pg.screenshot(path=f"{outp}_{vp}_{name}.png")
                    go({"modality": "ct", "ctWindow": "bone", "layout": "mpr"}, "ct_bone_mpr")
                    go({"ctWindow": "soft"}, "ct_soft_mpr")
                    go({"modality": "mr", "seq": "t1_se"}, "mr_t1_mpr")
                    go({"seq": "t2_se"}, "mr_t2_mpr")
                    go({"seq": "stir"}, "mr_stir_mpr")
                    go({"modality": "ct", "ctWindow": "bone", "thick": 25, "slab": "mip"}, "ct_bone_mip25")
                    go({"modality": "ct", "ctWindow": "soft", "layout": "single", "active": "cut", "thick": 5, "slab": "avg"}, "ct_soft_single")
                if do_interact:
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
    vps = ["1440x900", "390x844"]
    if "--viewports" in a:
        i = a.index("--viewports"); vps = a[i + 1].split(","); del a[i:i + 2]
    if vps == ["all"]:
        vps = VIEWPORTS_ALL
    numeric = None
    if "--numeric" in a:
        i = a.index("--numeric"); numeric = NUMERIC_SPECS[a[i + 1]]; del a[i:i + 2]
    do_interact = "--interact" in a
    if do_interact:
        a.remove("--interact")
    numeric_only = "--numeric-only" in a
    if numeric_only:
        a.remove("--numeric-only")
    record = None
    if "--record" in a:
        i = a.index("--record"); record = a[i + 1]; del a[i:i + 2]
    root, rel, kind, outp, three = a[:5]
    out = run(root, rel, kind, outp, three, vps, shots, numeric=numeric, do_interact=do_interact)
    print(json.dumps(out, indent=1))
    if record:
        from pathlib import Path
        d = Path(__file__).resolve().parents[2] / "data" / "derived"
        num = next((r["numeric"] for r in out.values() if r.get("numeric")), None)
        sl = next((r["slab"] for r in out.values() if r.get("slab")), None)
        if num and sl:
            num = dict(num, _slab=sl)
        if num:
            (d / f"Q226_numeric_{record}.json").write_text(json.dumps(num, indent=1) + "\n", encoding="utf-8")
        slim = {vp: {k: v for k, v in r.items() if k not in ("numeric", "slab")} for vp, r in out.items()}
        if not numeric_only:
            (d / f"Q226_browser_{record}.json").write_text(json.dumps(slim, indent=1) + "\n", encoding="utf-8")
    bad = [vp for vp, r in out.items() if r["errors"] or r["bad_responses"] or r["layout"]["scrollW"] > r["layout"]["innerW"]]
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
