#!/usr/bin/env python3
"""Q319: a nerve must read as strongly as its clinical importance deserves, without being drawn wider than it is.

Owner (Q319.4.iv, translated): "make sure the nerve marking is more prominent, because their diameter is small but
their position is very important."

What is measured, in headless Chromium with real WebGL (software rasteriser):

  1. COLOUR.  The WCAG contrast ratio of the nerve colour (--t-nerve, read out of the template under test, both
     themes) against bone, fascia, fat, skin, cartilage, muscle, artery and vein. Nerve yellow is bright, so on the
     pale tissues it is about 1.1 : 1 -- no width rescues that.
  2. PIXELS, on a SCENE.  The template's OWN `NMSKNervePass` (its shader strings and its width / ring helpers, cut out of
     the template text, so the Z template and the own-engine template are each tested as shipped) paints vertical
     tubes over flat bands in the tissue colours. Nerve, artery and vein tubes of the SAME true calibre are laid out
     side by side; arteries and veins are drawn at their true width and get no pass, nerves get the pass at the
     "Clear" and "Strong" steps read out of the template. For each tube: the drawn width (pixels that differ from the
     background) and the CONSPICUOUS width (pixels whose WCAG ratio to the pixel they cover is >= 3 : 1, the
     threshold WCAG 1.4.11 sets for graphical objects). "Before" is the template at git HEAD, "after" the working tree.
  3. HONESTY.  The core width is still exactly max(step minimum, true width); a nerve already wider than the step is
     not made wider than its own width plus the rim; arteries and veins are untouched.
  4. A BUILT PAGE, if one exists under /dev/shm/<name> or build/q309/<name>: the engine's own pass compiles, draws, and
     its own pixel meter (`__q303px`) reads more nerve after than before.

THE SCENE IS SYNTHETIC. It is not a built page and the numbers are not a measurement of the Z-Anatomy or the
own-engine meshes: tissue colours are the page's own tokens times one fixed shading factor, and a sub-pixel base tube
is drawn as a one-pixel point at its coverage. What it measures is what the pass and the colour do to a thin tube of a
known calibre over a known tissue. A page-level measurement needs a built page (page mode, item 4).

    python3 scripts/anatomy/q319/verify_nerves_q319.py [viewer_zan_atlas|viewer_m_hr ...]   (default: both)
"""
from __future__ import annotations

import json
import re
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

REPO = Path(__file__).resolve().parents[3]
THREE = Path("/tmp/three_x/package/build/three.min.js")
ARGS = ["--use-gl=swiftshader", "--enable-unsafe-swiftshader", "--ignore-gpu-blocklist"]
TEMPLATE = {"viewer_zan_atlas": "viewer/zan_atlas.template.html", "viewer_m_hr": "viewer/atlas_viewer.template.html"}
CONSPICUOUS = 3.0          # WCAG 2.1 SC 1.4.11 non-text contrast, for a graphical object
SHADE = 0.85               # one fixed shading factor for every tissue and every tube in the scene
MM_PER_PX = 2.0            # a whole-body view: ~1700 mm into ~850 px (the Q303 comment's own figure)
# true calibres laid out in the scene, mm: (kind, calibre). Pairs of the same calibre are the comparison.
TUBES = [("n", 0.4), ("n", 1.0), ("a", 1.0), ("v", 1.0), ("n", 2.0), ("a", 2.0), ("v", 2.0), ("n", 8.0), ("a", 8.0)]


# ---------------------------------------------------------------- scaffolding (as verify_toprow_q318) -------------
def serve(d):
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close()
    srv = subprocess.Popen([sys.executable, "-m", "http.server", str(p), "--bind", "127.0.0.1", "-d", str(d)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1); return srv, p


def route(rq):
    u = rq.request.url
    if "three" in u and u.endswith(".js") and ("cdnjs" in u or "jsdelivr" in u or "unpkg" in u):
        rq.fulfill(body=THREE.read_bytes() if THREE.exists() else b"", content_type="application/javascript")
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


# ---------------------------------------------------------------- what is read out of a template -------------------
def head_text(rel):
    return subprocess.run(["git", "show", "HEAD:" + rel], cwd=REPO, capture_output=True, text=True, check=True).stdout


def pass_source(t):
    a = t.index("var NMSKNervePass = (function(){")
    b = t.index('if (typeof module !== "undefined" && module.exports) module.exports = NMSKNervePass;', a)
    return t[a:b]


def px_source(t):
    a = t.index("var NMSKPx = (function(){")
    return t[a:t.index('if (typeof module !== "undefined" && module.exports) module.exports = NMSKPx;', a)]


def steps(t):
    m = re.search(r"var STEP = \[(.*?)\];", t, re.S)
    out = []
    for w, a, lab in re.findall(r"\{w:([\d.]+), a:([\d.]+), label:\"(\w+)\"\}", m.group(1)):
        out.append({"label": lab, "w": float(w), "a": float(a)})
    return out


def tokens(t):
    """The tissue colours. The Z template carries --t-* tokens (first block light, next dark); the own-engine template has
    one fixed TISSUE table (arteries and veins are both `vessel`, fascia is `tendon`, skin is `other`)."""
    blocks = re.findall(r"(--t-bone:[^}]*?)\}", t, re.S)
    if blocks:
        return {th: dict(re.findall(r"--t-([a-z]+):\s*(#[0-9a-fA-F]{6})", b)) for th, b in zip(("light", "dark"), blocks[:2])}
    tb = {k: "#%06x" % int(h, 16) for k, h in re.findall(r"^\s*([a-z]+):\s*\{hex:0x([0-9A-Fa-f]{6})", t[t.index("var TISSUE = {"):], re.M)}
    tb = {k: ("#" + v[1:].lower()) for k, v in tb.items()}
    tb.update({"fascia": tb["tendon"], "skin": tb["other"], "vein": tb["vessel"]})
    return {"page": tb}


def lin(c):
    c /= 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def lum(h):
    r, g, b = (int(h[i:i + 2], 16) for i in (1, 3, 5))
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def ratio(a, b):
    la, lb = lum(a), lum(b)
    return (max(la, lb) + 0.05) / (min(la, lb) + 0.05)


# ---------------------------------------------------------------- the scene ---------------------------------------
HARNESS = """<!doctype html><meta charset=utf-8><body style="margin:0"><canvas id=c width=900 height=640></canvas>
<script>__PASS__
__PX__
window.__go = function(cfg){
  var cv = document.getElementById('c'), W = cv.width, H = cv.height;
  var gl = cv.getContext('webgl', {preserveDrawingBuffer:true, antialias:false, alpha:false});
  function sh(t, s){ var o = gl.createShader(t); gl.shaderSource(o, s); gl.compileShader(o);
    if (!gl.getShaderParameter(o, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(o)); return o; }
  function prog(vs, fs){ var p = gl.createProgram(); gl.attachShader(p, sh(gl.VERTEX_SHADER, vs));
    gl.attachShader(p, sh(gl.FRAGMENT_SHADER, fs)); gl.linkProgram(p);
    if (!gl.getProgramParameter(p, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(p)); return p; }
  function rgb(h){ return [1,3,5].map(function(i){ return parseInt(h.substr(i,2),16)/255 * cfg.shade; }); }
  // flat quads + base tubes: a plain program (colour, alpha, point size) -- NOT the template's shader
  var base = prog('attribute vec2 p; uniform float s; void main(){ gl_Position = vec4(p,0.,1.); gl_PointSize = s; }',
                  'precision mediump float; uniform vec4 c; void main(){ gl_FragColor = c; }');
  function ndc(x, y){ return [x / W * 2 - 1, 1 - y / H * 2]; }
  function buf(a){ var b = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, b); gl.bufferData(gl.ARRAY_BUFFER, new Float32Array(a), gl.STATIC_DRAW); return b; }
  function drawBase(b, mode, n, col, a, size){
    gl.useProgram(base); gl.bindBuffer(gl.ARRAY_BUFFER, b);
    var l = gl.getAttribLocation(base, 'p'); gl.enableVertexAttribArray(l); gl.vertexAttribPointer(l, 2, gl.FLOAT, false, 0, 0);
    gl.uniform4f(gl.getUniformLocation(base, 'c'), col[0], col[1], col[2], a);
    gl.uniform1f(gl.getUniformLocation(base, 's'), size || 1);
    gl.drawArrays(mode, 0, n);
  }
  var bands = cfg.bands, tubes = cfg.tubes, bh = H / bands.length;
  function clear(){ gl.disable(gl.BLEND); gl.clearColor(0.5,0.5,0.5,1); gl.clear(gl.COLOR_BUFFER_BIT); }
  function backgrounds(){
    bands.forEach(function(b, i){
      var y0 = i * bh, y1 = (i + 1) * bh, a = ndc(0, y0), c = ndc(W, y1);
      drawBase(buf([a[0],a[1], c[0],a[1], a[0],c[1], c[0],c[1]]), gl.TRIANGLE_STRIP, 4, rgb(cfg.col[b]), 1, 1);
    });
  }
  var cols = [];   // one column per tube: x centre
  tubes.forEach(function(t, k){ cols.push(Math.round(40 + k * (W - 80) / (tubes.length - 1))); });
  var geo = [];    // per band, per tube: the vertex array in NDC (0.25 px spacing along the tube)
  bands.forEach(function(b, i){
    var y0 = i * bh + 24, y1 = (i + 1) * bh - 24;
    tubes.forEach(function(t, k){
      var v = [];
      for (var y = y0; y <= y1; y += 0.25){ var p = ndc(cols[k] + 0.5, y); v.push(p[0], p[1]); }
      geo.push({band:i, k:k, kind:t.kind, mm:t.mm, n:v.length / 2, b:buf(v)});
    });
  });
  function tubesBase(){
    gl.enable(gl.BLEND); gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
    geo.forEach(function(g){
      var tpx = g.mm / cfg.mmpp, col = rgb(cfg.col[g.kind === 'n' ? 'nerve' : g.kind === 'a' ? 'vessel' : 'vein']);
      // true width drawn faithfully down to one pixel; below that, the one-pixel point at its coverage
      drawBase(g.b, gl.POINTS, g.n, col, Math.min(1, tpx), Math.max(1, tpx));
    });
  }
  // the template's own pass program
  var P = NMSKNervePass, pp = prog(P.vs(), P.fs());
  function U(n){ return gl.getUniformLocation(pp, n); }
  function passDraw(step){
    gl.useProgram(pp); gl.enable(gl.BLEND); gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
    var I = new Float32Array([1,0,0,0, 0,1,0,0, 0,0,1,0, 0,0,0,1]);
    gl.uniformMatrix4fv(U('projectionMatrix'), false, I); gl.uniformMatrix4fv(U('viewMatrix'), false, I);
    gl.uniformMatrix4fv(U('modelMatrix'), false, I);
    gl.uniform4f(U('uC1'), 0,0,0,1); gl.uniform4f(U('uC2'), 0,0,0,1);
    gl.uniform3f(U('uCtr'), 0,0,0); gl.uniform3f(U('uFwd'), 0,0,-1);
    var nc = rgb(cfg.col.nerve);
    // the pass takes the colour UNSHADED in the Z glue (COL.nerve); the scene's base tubes are shaded -- as on a page
    var nerveCol = [1,3,5].map(function(i){ return parseInt(cfg.col.nerve.substr(i,2),16)/255; });   // UNSHADED, as the Z glue's COL.nerve
    gl.uniform1f(U('uAlpha'), step.a);
    var hasRim = (typeof P.casing === 'function') && (typeof P.ring === 'function');
    var l = gl.getAttribLocation(pp, 'position');
    function vb(g){ return g.b3 || (g.b3 = (function(){ var a = new Float32Array(g.n * 3), s = cfg._v[g.band + ':' + g.k];
      for (var i = 0; i < g.n; i++){ a[i*3] = s[i*2]; a[i*3+1] = s[i*2+1]; a[i*3+2] = 0; }
      var b = gl.createBuffer(); gl.bindBuffer(gl.ARRAY_BUFFER, b); gl.bufferData(gl.ARRAY_BUFFER, a, gl.STATIC_DRAW); return b; })()); }
    // the glue's own order: every nerve's casing first (core + 2 rim), then every nerve's core on top
    (hasRim ? [0, 1] : [1]).forEach(function(sweep){
      var c = sweep === 0 ? P.casing() : nerveCol;
      gl.uniform3f(U('uColor'), c[0], c[1], c[2]);
      geo.forEach(function(g){
        if (g.kind !== 'n') return;
        gl.uniform1f(U('uPt'), P.width(g.mm, cfg.mmpp, step.w, 1) + (sweep === 0 ? 2 * P.ring(1) : 0));
        gl.bindBuffer(gl.ARRAY_BUFFER, vb(g));
        gl.enableVertexAttribArray(l); gl.vertexAttribPointer(l, 3, gl.FLOAT, false, 0, 0);
        gl.drawArrays(gl.POINTS, 0, g.n);
      });
    });
  }
  function read(){ var b = new Uint8Array(W * H * 4); gl.readPixels(0, 0, W, H, gl.RGBA, gl.UNSIGNED_BYTE, b); return b; }
  return {W:W, H:H, bh:bh, cols:cols, geo:geo.map(function(g){ return {band:g.band, k:g.k, kind:g.kind, mm:g.mm}; }),
    render:function(mode, step){
      clear(); backgrounds();
      if (mode === 'bg') return read();
      tubesBase();
      if (mode === 'pass') passDraw(step);
      return read();
    }};
};
</script>"""


def lumw(rgb):
    return 0.2126 * lin(rgb[0]) + 0.7152 * lin(rgb[1]) + 0.0722 * lin(rgb[2])


SCENE_JS = r"""(cfg) => {
  // vertex arrays by band:tube, kept so the pass draws exactly the vertices the base draws
  cfg._v = {};
  const W = 900, H = 640, bh = H / cfg.bands.length;
  cfg.bands.forEach((b, i) => cfg.tubes.forEach((t, k) => {
    const x = Math.round(40 + k * (W - 80) / (cfg.tubes.length - 1)) + 0.5, v = [];
    for (let y = i * bh + 24; y <= (i + 1) * bh - 24; y += 0.25) v.push(x / W * 2 - 1, 1 - y / H * 2);
    cfg._v[i + ':' + k] = v;
  }));
  const S = window.__go(cfg);
  const lin = c => { c /= 255; return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4); };
  const L = (b, o) => 0.2126 * lin(b[o]) + 0.7152 * lin(b[o + 1]) + 0.0722 * lin(b[o + 2]);
  const bg = S.render('bg'), base = S.render('base');
  const res = {W: S.W, H: S.H, tubes: [], passes: {}};
  const pass = {};
  cfg.steps.forEach(s => { pass[s.label] = S.render('pass', s); });
  const measure = (img, band, k, kind) => {
    const x0 = S.cols[k] - 8, x1 = S.cols[k] + 9, y0 = Math.round(band * S.bh + 30), y1 = Math.round((band + 1) * S.bh - 30);
    let fp = 0, cons = 0, rows = 0, rowFp = new Array(x1 - x0).fill(0);
    for (let y = y0; y < y1; y++) {
      rows++;
      for (let x = x0; x < x1; x++) {
        const o = ((S.H - 1 - y) * S.W + x) * 4;                       // readPixels is bottom-up
        const a = L(img, o), b = L(bg, o);
        if (Math.abs(a - b) < 1e-4 && img[o] === bg[o] && img[o + 1] === bg[o + 1] && img[o + 2] === bg[o + 2]) continue;
        if (Math.abs(img[o] - bg[o]) + Math.abs(img[o + 1] - bg[o + 1]) + Math.abs(img[o + 2] - bg[o + 2]) < 6) continue;
        fp++;
        const r = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
        if (r >= cfg.thr) cons++;
      }
    }
    return {fp: fp / rows, cons: cons / rows};
  };
  S.geo.forEach(g => {
    const e = {band: cfg.bands[g.band], kind: g.kind, mm: g.mm, truePx: g.mm / cfg.mmpp};
    e.base = measure(base, g.band, g.k, g.kind);
    cfg.steps.forEach(s => { e[s.label] = measure(pass[s.label], g.band, g.k, g.kind); });
    res.tubes.push(e);
  });
  return res;
}"""


def scene(pg, port, t, label, theme, errs):
    tok = tokens(t)[theme]
    col = dict(tok)
    stp = [s for s in steps(t) if s["w"] > 0]
    cfg = {"shade": SHADE, "mmpp": MM_PER_PX, "thr": CONSPICUOUS, "steps": stp,
           "bands": ["bone", "fascia", "fat", "muscle", "skin"], "col": col,
           "tubes": [{"kind": k, "mm": m} for k, m in TUBES]}
    html = HARNESS.replace("__PASS__", pass_source(t)).replace("__PX__", px_source(t))
    d = Path(tempfile.mkdtemp(prefix="q319_"))
    (d / "h.html").write_text(html, encoding="utf-8")
    srv, p = serve(d)
    try:
        pg.goto(f"http://127.0.0.1:{p}/h.html", wait_until="load")
        return pg.evaluate(SCENE_JS, cfg), cfg
    finally:
        srv.terminate()


def table(res, cfg, tag):
    by = {}
    for e in res["tubes"]:
        by.setdefault((e["band"], e["kind"], e["mm"]), e)
    return by


def run_template(pl, name, errs):
    rel = TEMPLATE[name]
    after = (REPO / rel).read_text(encoding="utf-8")
    before = head_text(rel)
    print(f"\n=== {name}  ({rel}) ===")
    stp = [s for s in steps(after) if s["w"] > 0]
    print("     steps: " + ", ".join(f"{s['label']} {s['w']} px / alpha {s['a']}" for s in stp))

    # 1. colour, from this template's own tokens
    for theme in tokens(after):
        tk = tokens(after)[theme]
        r = {k: round(ratio(tk["nerve"], tk[k]), 2) for k in ("bone", "fascia", "fat", "skin", "cartilage", "muscle", "vessel", "vein")}
        print(f"     colour {theme}: nerve {tk['nerve']} vs {r}")
        check(f"{theme}: nerve yellow is under 1.5:1 against bone, fascia and fat (so width alone cannot make it read): "
              f"{[r['bone'], r['fascia'], r['fat']]}", max(r["bone"], r["fascia"], r["fat"]) < 1.5, errs)

    b = pl.chromium.launch(args=ARGS, executable_path="/opt/pw-browsers/chromium")
    try:
        for theme in tokens(after):
            pg = b.new_page(viewport={"width": 1000, "height": 700})
            pg.on("pageerror", lambda e: errs.append("page error: " + str(e)))
            rb, cfg = scene(pg, None, before, name, theme, errs)
            ra, _ = scene(pg, None, after, name, theme, errs)
            pg.close()
            B, A = table(rb, cfg, "before"), table(ra, cfg, "after")
            print(f"     -- scene, {theme} theme, {MM_PER_PX} mm per pixel; width in px per unit length of tube "
                  f"(drawn / conspicuous at >= {CONSPICUOUS}:1)")
            for band in cfg["bands"]:
                for mm in (0.4, 1.0, 2.0, 8.0):
                    n = A.get((band, "n", mm)); a_ = A.get((band, "a", mm)); v_ = A.get((band, "v", mm))
                    nb = B.get((band, "n", mm))
                    if not n:
                        continue
                    for s in stp:
                        L = s["label"]
                        line = (f"     {band:6s} {mm:>4} mm {L:6s} nerve before {nb[L]['fp']:.2f}/{nb[L]['cons']:.2f}  "
                                f"after {n[L]['fp']:.2f}/{n[L]['cons']:.2f}")
                        if a_ and v_:
                            line += f"   artery {a_[L]['fp']:.2f}/{a_[L]['cons']:.2f}  vein {v_[L]['fp']:.2f}/{v_[L]['cons']:.2f}"
                        print(line)
            # the checks, on the 1.0 mm pair (a small nerve with a real artery of the same calibre) and the 0.4 mm one
            for band in ("bone", "fascia", "fat", "skin", "muscle"):
                for L in [s["label"] for s in stp]:
                    n1, n0 = A[(band, "n", 1.0)][L], B[(band, "n", 1.0)][L]
                    a1 = A[(band, "a", 1.0)][L]; v1 = A[(band, "v", 1.0)][L]
                    check(f"{theme} {band} {L}: 1.0 mm nerve is conspicuous over {n1['cons']:.2f} px, before it was {n0['cons']:.2f} "
                          f"(artery {a1['cons']:.2f}, vein {v1['cons']:.2f} at the same calibre)",
                          n1["cons"] >= 2.0 * max(a1["cons"], v1["cons"], 0.5) and n1["cons"] >= n0["cons"] and n1["cons"] >= 2.0, errs)
                    s0 = A[(band, "n", 0.4)][L]
                    check(f"{theme} {band} {L}: even the 0.4 mm nerve reaches {s0['cons']:.2f} conspicuous px "
                          f"(before {B[(band, 'n', 0.4)][L]['cons']:.2f})", s0["cons"] >= 1.5, errs)
                    # honesty: a nerve already wider than the step is not widened by more than the rim, and vessels are untouched
                    big_a, big_b = A[(band, "n", 8.0)][L], B[(band, "n", 8.0)][L]
                    check(f"{theme} {band} {L}: the 8 mm nerve (true {8.0 / MM_PER_PX:.1f} px) gains only the rim "
                          f"({big_b['fp']:.2f} -> {big_a['fp']:.2f} px)", 0 <= big_a["fp"] - big_b["fp"] <= 2.2, errs)
                    check(f"{theme} {band} {L}: artery and vein drawn the same before and after "
                          f"({B[(band, 'a', 1.0)][L]['fp']:.2f}/{B[(band, 'v', 1.0)][L]['fp']:.2f} -> {a1['fp']:.2f}/{v1['fp']:.2f})",
                          abs(B[(band, 'a', 1.0)][L]["fp"] - a1["fp"]) < 1e-6 and abs(B[(band, 'v', 1.0)][L]["fp"] - v1["fp"]) < 1e-6, errs)
    finally:
        b.close()
    return after, before


def shaders(ps):
    return ps[ps.index("var VS ="):re.search(r"\n  var (RING_CSS|api)\b", ps).start()]


def static_checks(srcs, errs):
    print("\n=== both engines ===")
    for name, (after, before) in srcs.items():
        pa, pb = pass_source(after), pass_source(before)
        check(f"{name}: the width formula is unchanged (core = max(step minimum, true width) * dpr)",
              "Math.max(wmin_px || 0, truePx) * (dpr || 1)" in pa and "Math.max(wmin_px || 0, truePx) * (dpr || 1)" in pb, errs)
        check(f"{name}: both shader stages (cut, far half, point size, round dot) are byte-identical to HEAD",
              shaders(pa) == shaders(pb), errs)
        check(f"{name}: the glue draws the casing from the shared helper, wider by two rims", "NMSKNervePass.casing()" in after and "NMSKNervePass.ring(" in after, errs)
    if len(srcs) == 2:
        k = list(srcs)
        check("the shared pass is byte-identical in the two templates",
              pass_source(srcs[k[0]][0]) == pass_source(srcs[k[1]][0]), errs)
    if "viewer_m_hr" in srcs:
        check("own engine: the casing twin is drawn before the core twin (renderOrder 997 < 998)",
              "renderOrder = 997" in srcs["viewer_m_hr"][0] and "renderOrder = 998" in srcs["viewer_m_hr"][0], errs)


PAGE_JS = """async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const N = window.NMSKNerves; if (!N) return {err: 'no NMSKNerves on the page'};
  N.set(0); await sleep(1200); const p0 = window.__q303px ? window.__q303px(2) : null;
  N.set(1); await sleep(2500); const p1 = window.__q303px ? window.__q303px(2) : null;
  const nv = window.__q303nv ? window.__q303nv() : null;
  N.set(0);
  return {p0, p1, nv, census: N.census()};
}"""


def page_check(pl, name, errs):
    cand = [Path("/dev/shm") / name, REPO / "build" / "q309" / name]
    # a build directory restored from its published artifact holds only index.html: that IS the page
    def pages(c):
        return sorted(c.glob("atlas_viewer*.html")) or sorted(c.glob("index.html"))
    d = next((c for c in cand if c.is_dir() and pages(c)), None)
    if d is None:
        print(f"\n--- {name}: no built page under /dev/shm or build/q309; the page-level measurement was NOT run "
              f"(scene numbers above are synthetic) ---")
        return
    print(f"\n--- {name}: built page {d} ---")
    srv, port = serve(d)
    try:
        b = pl.chromium.launch(args=ARGS, executable_path="/opt/pw-browsers/chromium")
        pg = b.new_page(viewport={"width": 1400, "height": 950})
        pg.on("pageerror", lambda e: errs.append("page error: " + str(e)))
        pg.route("**/*", route)
        pg.goto(f"http://127.0.0.1:{port}/{pages(d)[0].name}", wait_until="load", timeout=90000)
        pg.wait_for_function("window.NMSKNerves", timeout=90000); pg.wait_for_timeout(2500)
        # Press the workspace tile through the DOM, not the mouse. Since Q318 the control row adopts the
        # engine's buttons into a hidden parking node, and the published index.html wrapper can keep the
        # mode switcher out of view entirely -- a real click then waits for a visibility that never comes.
        # Its absence is not a failure: the page is already in its default workspace.
        pg.evaluate("() => { const t = document.querySelector('.mw-tile[data-mode=\"anat\"]');"
                    " if (t) t.click(); }")
        pg.wait_for_timeout(2500)
        # A page that never started the module offers no emphasis at all: say so, do not crash on it.
        if not pg.evaluate("() => !!(window.NMSKNerves && NMSKNerves.state().started)"):
            print(f"--- {name}: this page does not offer nerve emphasis -- NMSKQ303.start is called here "
                  f"without a `nerves` adaptor, so the control is never started. Nothing to measure on the "
                  f"page; the scene figures above still apply to its shader. ---")
            b.close()
            return {"not_offered": True}
        r = pg.evaluate(PAGE_JS)
        b.close()
    finally:
        srv.terminate()
    if r.get("err"):
        check(r["err"], False, errs); return
    check(f"the engine's own pass compiled and drew ({json.dumps(r['nv'])[:120]})", r["nv"] and not r["nv"].get("fail") and r["nv"].get("step", 0) > 0, errs)
    if r["p0"] and r["p1"]:
        print(f"     nerve share of pixels {r['p0']['nerveFrac']} -> {r['p1']['nerveFrac']}")
        check("the page's own meter reads more nerve with the emphasis on", r["p1"]["nerveFrac"] > r["p0"]["nerveFrac"], errs)


def main() -> int:
    names = [a for a in sys.argv[1:] if a in TEMPLATE] or ["viewer_zan_atlas", "viewer_m_hr"]
    errs: list[str] = []
    srcs = {}
    with sync_playwright() as pl:
        for n in names:
            srcs[n] = run_template(pl, n, errs)
            page_check(pl, n, errs)
    static_checks(srcs, errs)
    print()
    if errs:
        print(f"Q319_NERVES_FAIL {len(errs)}")
        for e in errs:
            print("  - " + e)
        return 1
    print("Q319_NERVES_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
