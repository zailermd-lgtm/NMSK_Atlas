#!/usr/bin/env python3
"""Q239 -- does the imaging (CT / MRI) + ultrasound tool come up on a page under HOSTING-MIMIC conditions? Headless Chromium (swiftshader).

    python3 scripts/clinical/q239_check.py PAGE_DIR PAGE.html own|zan OUT_PREFIX --cond strict --vp 1366x768 [--shots-dir data/derived/q239] [--json out.json]

Conditions (scripts/clinical/q239_host.py): base | plain | nosniff | nosib | sbx | strict
  strict = every sibling file answered 404 (inline only) + .js/.json as text/plain + nosniff + page wrapped like the artifact service does + a sandboxed iframe
           (allow-scripts only, opaque origin).  The toolbar buttons and both tools must work on the PASTED code and tables alone.
Per run: toolbar buttons visible, tooltip / panel diagnostic lines say "ready", CT (bone + soft) / MRI T1 / T2 / MIP / MPR / single, ultrasound star (perpendicular
+ tilt) and sweep with 3 and 9 frames; each image checked for content (pixel spread of the panel screenshot and of the tool's own canvases); page errors = 0.
Prints / writes one JSON object; screenshots are small palette PNGs."""
from __future__ import annotations

import io
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from q239_host import serve  # noqa: E402

THREE = "/tmp/three_x/package/build/three.min.js"
CONDS = {
    "base": {}, "plain": dict(mime="plain", wrap=True), "nosniff": dict(mime="plain", nosniff=True, wrap=True), "nosib": dict(hide=("clinical_",), wrap=True),
    "sbx": dict(mime="plain", wrap=True, sandbox="allow-scripts"),
    "strict": dict(mime="plain", nosniff=True, wrap=True, sandbox="allow-scripts", hide=("clinical_",)),
}
SPREAD_JS = """(sel)=>{var out=[]; [].forEach.call(document.querySelectorAll(sel),function(c){ if(!c.width||!c.height||c.offsetParent===null) return;
  var x=c.getContext('2d'), w=Math.min(c.width,256), h=Math.min(c.height,256), d; try{ d=x.getImageData(0,0,c.width,c.height).data; }catch(e){ return; }
  var n=0,s=0,s2=0; for(var i=0;i<d.length;i+=16){ var v=(d[i]+d[i+1]+d[i+2])/3; n++; s+=v; s2+=v*v; } var m=s/n; out.push({w:c.width,h:c.height,std:Math.round(Math.sqrt(Math.max(0,s2/n-m*m))*10)/10}); }); return out; }"""


def pixel_stats(png: bytes):
    from PIL import Image
    import numpy as np
    im = Image.open(io.BytesIO(png)).convert("L")
    a = np.asarray(im, dtype=np.float32)
    vals, counts = np.unique(a.astype(np.uint8), return_counts=True)
    mode = vals[counts.argmax()]
    return {"std": round(float(a.std()), 1), "ink": round(float((np.abs(a - mode) > 12).mean()), 3), "w": a.shape[1], "h": a.shape[0]}


def save_small(png: bytes, path: Path, max_w=640):
    from PIL import Image
    im = Image.open(io.BytesIO(png)).convert("RGB")
    if im.width > max_w:
        im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
    im = im.convert("P", palette=Image.ADAPTIVE, colors=48)
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path, optimize=True)
    return path.stat().st_size


def _t(msg):
    import os
    if os.environ.get("Q239_TRACE"):
        print("[%s] %s" % (time.strftime("%H:%M:%S"), msg), file=sys.stderr, flush=True)


def run(page_dir, page, kind, cond, vp, shots_dir=None, tag="", quick=False):
    from playwright.sync_api import sync_playwright
    opts = dict(CONDS[cond]); outer = "sandbox" in opts
    srv, port = serve(page_dir, page=page, **opts)
    w, h = map(int, vp.split("x")); mobile = min(w, h) < 520
    R = {"page": page, "cond": cond, "vp": vp, "checks": {}, "errors": [], "shots": {}}
    ck = R["checks"]
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(executable_path="/opt/pw-browsers/chromium", args=["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"])
            ctx = b.new_context(viewport={"width": w, "height": h}, has_touch=mobile, is_mobile=mobile, device_scale_factor=1)
            pg = ctx.new_page(); pg.set_default_timeout(240000)
            errs = R["errors"]
            pg.on("pageerror", lambda e: errs.append("pageerror:" + str(e)[:200]))

            def on_console(m):
                t = m.text
                if m.type != "error" or "GPU stall" in t:
                    return
                if "Failed to load resource" in t and "404" in t and cond in ("nosib", "strict"):          # the siblings are deliberately absent
                    return
                if "Refused to execute script" in t and "clinical_" in t and cond in ("nosniff", "strict"):   # the sibling files are deliberately refused
                    return
                errs.append("console:" + t[:200])
            pg.on("console", on_console)
            pg.route("**/fonts.g*.com/**", lambda r: r.fulfill(status=200, body="", content_type="text/css"))
            pg.route("**/three*.js", lambda r: r.fulfill(path=THREE, content_type="application/javascript"))
            pg.goto(f"http://127.0.0.1:{port}/" + ("__outer.html" if outer else page))
            if outer:
                pg.wait_for_selector("iframe#app")
                pg.wait_for_timeout(1500)
            F = pg.frames[1] if outer else pg.main_frame
            F.wait_for_function("window.NMSKImaging", timeout=600000)
            pg.wait_for_timeout(2500)
            if kind == "zan":
                F.evaluate("document.getElementById('btn-spin') && document.getElementById('btn-spin').classList.contains('on') && document.getElementById('btn-spin').click()")
            R["code"] = F.evaluate("window.NMSKClinicalDiag||null")
            btn = lambda id: F.locator("#" + id).first
            press = lambda id: (btn(id).tap() if mobile else btn(id).click())
            vis = F.evaluate("""()=>{function v(id){var e=document.getElementById(id); if(!e) return null; var r=e.getBoundingClientRect(); return {text:e.textContent,tip:e.title,x:Math.round(r.left),y:Math.round(r.top),w:Math.round(r.width),h:Math.round(r.height),
                 inside:r.left>=0&&r.top>=0&&r.right<=innerWidth&&r.bottom<=innerHeight&&r.width>8}} return {i:v('t-imaging'),u:v('t-ultrasound'),W:innerWidth,H:innerHeight}}""")
            R["buttons"] = vis
            ck["btn_ct_mri_visible"] = bool(vis["i"] and vis["i"]["inside"] and "ct" in vis["i"]["text"].lower() and "mri" in vis["i"]["text"].lower())
            ck["btn_ultrasound_visible"] = bool(vis["u"] and vis["u"]["inside"] and "ultrasound" in vis["u"]["text"].lower())
            _t("buttons seen"); F.wait_for_function("document.getElementById('t-imaging').title.indexOf('ready (v')>0", timeout=60000)
            F.wait_for_function("document.getElementById('t-ultrasound').title.indexOf('ready (v')>0", timeout=60000)
            R["tooltips"] = F.evaluate("[document.getElementById('t-imaging').title, document.getElementById('t-ultrasound').title]")
            ck["tooltip_imaging_ready"] = "Imaging tool: ready (v" in R["tooltips"][0] and "tissues " in R["tooltips"][0]
            ck["tooltip_ultrasound_ready"] = "Ultrasound tool: ready (v" in R["tooltips"][1] and "tissues " in R["tooltips"][1]
            ck["code_inline"] = bool(R["code"] and R["code"].get("imaging", {}).get("code") == "inline" and R["code"].get("ultrasound", {}).get("code") == "inline")
            ck["table_inline"] = bool(R["code"] and R["code"]["imaging"].get("table") == "inline" and R["code"]["ultrasound"].get("table") == "inline")
            shots = Path(shots_dir) if shots_dir else None
            nshot = [0]

            def shot(name, root_sel):
                png = pg.screenshot()
                try:
                    box = F.locator(root_sel).first.bounding_box()
                    if outer:
                        fb = pg.locator("iframe#app").bounding_box(); box = {"x": box["x"] + fb["x"], "y": box["y"] + fb["y"], "width": box["width"], "height": box["height"]}
                    clip = {"x": max(0, box["x"]), "y": max(0, box["y"]), "width": min(w - max(0, box["x"]), box["width"]), "height": min(h - max(0, box["y"]), box["height"])}
                    png = pg.screenshot(clip=clip)
                except Exception as e:
                    errs.append("shot-clip:" + str(e)[:100])
                st = pixel_stats(png)
                R["shots"][name] = st
                if shots is not None:
                    save_small(png, shots / f"{tag}_{vp}_{name}.png")
                return st

            # ---------------- imaging
            _t("press imaging"); press("t-imaging")
            F.wait_for_function("NMSKImaging.geo() !== null", timeout=600000)
            F.wait_for_function("(function(){var v=NMSKImaging.views();return Object.keys(v).some(function(k){return v[k].stats&&v[k].stats.tier===1;});})()", timeout=600000)
            _t("imaging first images"); F.evaluate("NMSKImaging.idle()"); pg.wait_for_timeout(1200)
            R["imaging_diag"] = F.evaluate("(document.querySelector('#img-root .img-diag')||{}).textContent")
            R["imaging_hint"] = F.evaluate("(function(){var e=document.querySelector('#img-root .img-hint'); return e&&e.style.display!=='none'?e.textContent:null})()")
            ck["imaging_diag_ready"] = bool(R["imaging_diag"] and "Imaging tool: ready (v" in R["imaging_diag"])
            ck["imaging_panel_visible"] = F.evaluate("(function(){var r=document.getElementById('img-root').getBoundingClientRect(); return r.width>200&&r.height>150&&r.right>0&&r.bottom>0&&r.left<innerWidth})()")
            ck["imaging_cut_exists"] = F.evaluate("(function(){var c=document.getElementById('cut-state'); return !!(window.NMSKImaging && NMSKImaging.state().P)})()")
            ck["imaging_hint_shown"] = bool(R["imaging_hint"])

            def img(name, patch, wait=700):
                F.evaluate("NMSKImaging.set(%s)" % json.dumps(patch)); pg.wait_for_timeout(300)
                F.evaluate("NMSKImaging.idle()"); pg.wait_for_timeout(wait)
                st = shot(name, "#img-root")
                sp = F.evaluate(SPREAD_JS, "#img-root canvas:not(.ann)")
                R.setdefault("canvas_std", {})[name] = [x["std"] for x in sp]
                ck["img_" + name] = st["std"] > 12 and st["ink"] > 0.02 and bool(sp) and max(x["std"] for x in sp) > 10
            img("ct_soft_mpr", {"modality": "ct", "ctWindow": "soft", "layout": "mpr", "thick": 5, "slab": "avg"})
            img("ct_bone", {"ctWindow": "bone"})
            img("mri_t1", {"modality": "mr", "seq": "t1_se"})
            img("mri_t2", {"seq": "t2_se"})
            if not quick:
                img("ct_mip", {"modality": "ct", "ctWindow": "bone", "thick": 25, "slab": "mip"})
            img("ct_single", {"modality": "ct", "ctWindow": "soft", "layout": "single", "active": "cut", "thick": 5, "slab": "avg"})
            R["layout"] = F.evaluate("""(function(){var r=document.getElementById('img-root').getBoundingClientRect(); return {cls:document.body.className, scrollW:document.documentElement.scrollWidth, innerW:innerWidth, panel:[Math.round(r.left),Math.round(r.top),Math.round(r.width),Math.round(r.height)]}})()""")
            ck["no_horizontal_scroll"] = R["layout"]["scrollW"] <= R["layout"]["innerW"] + 1
            F.evaluate("NMSKImaging.close()"); pg.wait_for_timeout(900)
            ck["imaging_closed_3d_back"] = F.evaluate("!document.body.classList.contains('nmsk-img')")

            # ---------------- ultrasound
            _t("press ultrasound"); press("t-ultrasound")
            F.evaluate("NMSKUltrasound.ready()"); F.evaluate("NMSKUltrasound.idle()"); pg.wait_for_timeout(1200)
            R["ultrasound_diag"] = F.evaluate("(document.querySelector('#us-root .us-diag')||{}).textContent")
            ck["ultrasound_diag_ready"] = bool(R["ultrasound_diag"] and "Ultrasound tool: ready (v" in R["ultrasound_diag"])
            ck["ultrasound_panel_visible"] = F.evaluate("(function(){var r=document.getElementById('us-root').getBoundingClientRect(); return r.width>200&&r.height>150&&r.right>0&&r.bottom>0&&r.left<innerWidth})()")

            def us(name, patch, wait=700):
                F.evaluate("NMSKUltrasound.set(%s)" % json.dumps(patch)); F.evaluate("NMSKUltrasound.idle()"); pg.wait_for_timeout(wait)
                st = shot(name, "#us-root")
                sp = F.evaluate(SPREAD_JS, "#us-root canvas:not(.ann)")
                R.setdefault("canvas_std", {})[name] = [x["std"] for x in sp]
                ck["us_" + name] = st["std"] > 8 and st["ink"] > 0.02 and bool(sp) and max(x["std"] for x in sp) > 6
            us("star_perp_tilt", {"mode": "star", "probe": "linear", "tilt": 15, "depthCm": 5})
            us("sweep3", {"mode": "sweep", "n": 3, "spacing": 8})
            us("sweep9", {"mode": "sweep", "n": 9, "spacing": 6})
            R["us_frames"] = F.evaluate("NMSKUltrasound.frames().length")
            ck["us_nine_frames"] = R["us_frames"] == 9
            F.evaluate("NMSKUltrasound.close()"); pg.wait_for_timeout(600)
            ck["no_page_errors"] = not errs
            b.close()
    except Exception as e:                                                     # a timeout / crash is a finding, not an exception for the caller
        R["errors"].append("harness:" + str(e)[:300])
        ck["completed"] = False
    finally:
        srv.shutdown()
    ck.setdefault("completed", True)
    R["ok"] = all(ck.values()) and not R["errors"]
    return R


def main(argv=None):
    a = list(argv or sys.argv[1:])
    def opt(name, default=None):
        if name in a:
            i = a.index(name); v = a[i + 1]; del a[i:i + 2]; return v
        return default
    cond = opt("--cond", "strict"); vp = opt("--vp", "1366x768"); shots = opt("--shots-dir"); out = opt("--json"); tag = opt("--tag", "")
    quick = "--quick" in a
    if quick:
        a.remove("--quick")
    page_dir, page, kind = a[:3]
    t0 = time.time()
    R = run(page_dir, page, kind, cond, vp, shots, tag or page.replace("atlas_viewer_", "").replace(".html", ""), quick)
    R["seconds"] = round(time.time() - t0)
    s = json.dumps(R, indent=1)
    if out:
        Path(out).parent.mkdir(parents=True, exist_ok=True); Path(out).write_text(s + "\n")
    print(json.dumps({k: R[k] for k in ("page", "cond", "vp", "ok", "seconds", "errors")}), {k: v for k, v in R["checks"].items() if not v})
    return 0 if R["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
