"""Q294 -- page-wide Undo / Redo / Reset, the Marked / Display summary, part slices (thickness, interval, spread), abbreviation popup +
"i" tips, measure tools, ultrasound: sheet thickness under every transform, zoom re-simulation, probe placement / model, per-bundle
fibres. Unit level (node); the real-browser check is scripts/anatomy/q294/verify_q294.py (log data/derived/Q294_browser_check.log)."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
Q = REPO / "viewer" / "q294"
OWN = REPO / "viewer" / "atlas_viewer.template.html"
ZAN = REPO / "viewer" / "zan_atlas.template.html"
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(not NODE, reason="node not installed")
sys.path.insert(0, str(REPO / "scripts"))


def node(src: str) -> dict:
    r = subprocess.run([NODE, "-e", src], capture_output=True, text=True, timeout=120, cwd=str(REPO))
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_sync_is_current_and_verbatim():
    import sync_q294 as S
    frag = S.fragment()
    for t in (OWN, ZAN):
        txt = t.read_text(encoding="utf-8")
        assert txt.count(S.BEGIN) == 1 and txt.count(S.END) == 1
        assert txt[txt.index(S.BEGIN) + len(S.BEGIN):txt.index(S.END)] == "\n" + frag + "\n", t.name
        assert txt.index("<!-- PINCH html end -->") < txt.index(S.BEGIN)
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "sync_q294.py"), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout


@pytest.mark.parametrize("tpl", [OWN, ZAN], ids=["own", "zan"])
def test_engines_wire_history_measure_slices(tpl):
    t = tpl.read_text(encoding="utf-8")
    for k in ('register("engine"', 'register("selection"', 'register("cut"', 'register("slices"', 'register("labels"', "NMSKMeasure.start(", "NMSKPartSlices.start(", "NMSKHistory.start(", "NMSKTips.start()",
              "measureCtl.consumeClick(e)", "onTop:function", "focus:function", "stats:function"):
        assert k in t, k
    assert "ultrasound" not in t.lower()                                       # the Q228 rule: the public templates never name the private modality


def test_selection_panel_keeps_every_control_and_adds_the_summary():
    h = (REPO / "viewer" / "selection" / "selection.html").read_text(encoding="utf-8")
    for i in ("sel-invert", "sel-markvis", "sel-cat", "sel-markcat", "sel-unmarkcat", "sel-fade", "sel-hl", "sel-tint", "sel-p-isolate", "sel-p-fadeoth", "sel-p-fadesel",
              "sel-p-hidesel", "sel-p-hlsel", "sel-only", "sel-hide", "sel-ghost", "sel-reset", "sel-undo", "sel-redo", "ss-look-sel", "ss-look-oth", "ss-scene", "ss-q-all", "ss-fadetaps"):
        assert f'id="{i}"' in h, i
    assert h.index('id="ss-det-groups"') < h.index('data-g="sel" data-s="show"') and '<details class="ss-det" id="ss-det-more">' in h


@needs_node
def test_measure_core_math():
    o = node("""eval(require('fs').readFileSync('viewer/q294/measure.js','utf8').split('var NMSKMeasure = ')[0]); const C = NMSKMeasureCore, d = Math.PI/180;
      const out = {dist: C.dist([0,0,0],[30,40,0]), a90: C.angle3([10,0,0],[0,0,0],[0,10,0]), a30: C.angle3([1,0,0],[0,0,0],[Math.cos(30*d),Math.sin(30*d),0]),
        l35: C.lineAngle([0,0],[Math.cos(10*d),Math.sin(10*d)],[5,5],[5+Math.cos(-25*d),5+Math.sin(-25*d)]), lobt: C.lineAngle([0,0],[1,0],[0,0],[-1,0.0001]),
        cobb: C.cobb([0,0,0],[Math.cos(10*d),0,Math.sin(10*d)],[0,80,0],[Math.cos(-25*d),80,Math.sin(-25*d)],[0,0,1]),
        t: C.rayMesh([0,0,-5],[0,0,1],new Float32Array([-1,-1,0, 1,-1,0, 0,1,0]),new Uint16Array([0,1,2])), miss: C.rayMesh([5,5,-5],[0,0,1],new Float32Array([-1,-1,0, 1,-1,0, 0,1,0]),new Uint16Array([0,1,2])),
        lab: C.label('cobb', C.value('cobb', [[0,0],[1,0],[0,1],[1,1.2]]))};
      console.log(JSON.stringify(out));""")
    assert abs(o["dist"] - 50) < 1e-9 and abs(o["a90"] - 90) < 1e-9 and abs(o["a30"] - 30) < 1e-6
    assert abs(o["l35"] - 35) < 1e-6 and o["lobt"] < 0.01                       # lines have no direction: 180 deg = 0 deg
    assert abs(o["cobb"]["deg"] - 35) < 1e-6 and abs(o["cobb"]["perp"] - 35) < 1e-6 and o["cobb"]["view"] < 0.01   # seen along the plane's normal the two lines are parallel
    assert abs(o["t"] - 5) < 1e-6 and o["miss"] is None
    assert o["lab"] == "Cobb 11.3°"


@needs_node
def test_part_planes_count_spread_crop_and_window():
    o = node("""eval(require('fs').readFileSync('viewer/cut_cap/cut_cap.js','utf8') + ';global.X=NMSKCrossSectionCore;global.K=NMSKCapCore;');
      const pts = new Float32Array(300); for (let i = 0; i < 100; i++){ pts[3*i] = i * 0.8237; pts[3*i+1] = Math.sin(i) * 3; pts[3*i+2] = Math.cos(i) * 3; }
      const ax = X.axisOf([pts]), pl = X.partPlanes(ax, 10, 1, 80), pl0 = X.partPlanes(ax, 10, 0, 80), off = X.spreadOffsets(pl.map(p => p.t), 3);
      const res = {n:[1,0,0], d:5, O:[5,0,0], w:2, lines:{pos:new Float32Array([5,0,0, 5,1,0]), col:null, owner:null, count:1}};
      const sh = X.shifted(res, 7);
      const P = [], I = []; const q = [[-20,-20],[20,-20],[20,20],[-20,20]]; q.forEach(c => { P.push(-5, c[0], c[1], 5, c[0], c[1]); });
      for (let k = 0; k < 4; k++){ const a = 2*k, b = 2*((k+1)%4); I.push(a, b, a+1, b, b+1, a+1); }
      const it = [{key:'t', name:'t', cat:'muscle', rgb:[1,0,0], alpha:1, geom:() => ({pos:new Float32Array(P), idx:new Uint32Array(I), bmin:[-5,-20,-20], bmax:[5,20,20]})}];
      const full = K.build(it, {n:[1,0,0], d:0}, {gap:1, px:0.5}), win = K.build(it, {n:[1,0,0], d:0}, {gap:1, px:0.5, win:[-5,-5,5,5]}), out = K.build(it, {n:[1,0,0], d:0}, {gap:1, px:0.5, win:[30,30,40,40]});
      const cr = X.crop({pos:new Float32Array(P), idx:new Uint32Array(I)}, [-1, -21, -21], [1, 21, 0]);
      console.log(JSON.stringify({len:ax.len, a:ax.a, n:pl.length, n0:pl0.length, step:pl[1].t - pl[0].t, th:pl[0].far.d - pl[0].near.d, first:pl[0].t - ax.t0, last:ax.t1 - (pl[pl.length-1].t + 1),
        off, shO:sh.O, shL:Array.from(sh.lines.pos), orig:res.O, origL:Array.from(res.lines.pos), fullW:full.w * full.px, winW:win.w * win.px, outN:out.items.length, crT:cr.idx.length / 3, crV:cr.pos.length / 3}));""")
    assert abs(o["len"] - 81.55) < 0.05 and abs(o["a"][0]) > 0.999
    assert o["n"] == 9 and o["n0"] == 9 and abs(o["step"] - 10) < 1e-9 and abs(o["th"] - 1) < 1e-9     # floor((81.55 - 1) / 10) + 1 = 9
    assert abs(o["first"] - o["last"]) < 1e-6                                   # centred on the part
    assert abs(sum(o["off"])) < 1e-6 and abs(o["off"][-1] - 80) < 1e-6           # (t - mean) x (3 - 1)
    assert o["shO"] == [12, 0, 0] and o["shL"][0] == 12 and o["orig"] == [5, 0, 0] and o["origL"][0] == 5   # the display copy moved, the original did not
    assert o["fullW"] > 40 and o["winW"] <= 10 + 4 * 0.5 + 0.01 and o["outN"] == 0
    assert 0 < o["crT"] < 8 and o["crV"] <= 8                                   # only the triangles touching the box, compact vertices


@needs_node
def test_history_undo_redo_reset_and_branching():
    o = node("""global.window = {addEventListener(){}};
      global.document = {addEventListener(){}, getElementById(){ return null; }, createElement(){ return {style:{}, setAttribute(){}, addEventListener(){}, appendChild(){}}; }, body:{appendChild(){}}};
      eval(require('fs').readFileSync('viewer/q294/history.js','utf8') + ';global.H=NMSKHistory;');
      let a = 0, b = 'x'; H.register('a', {get:() => a, set:v => { a = v; }, reset:() => { a = 0; }}); H.register('b', {get:() => b, set:v => { b = v; }, reset:() => { b = 'x'; }});
      H.start({floating:false, max:20});
      for (let i = 1; i <= 25; i++){ a = i; H.commit(); }
      const len = H.state().len; let u = 0; while (H.undo()) u++;
      const after = a; for (let i = 0; i < 3; i++) H.redo(); const r3 = a;
      b = 'y'; H.commit(); const canRedo = H.canRedo();
      H.reset(); const rs = [a, b]; H.undo(); const back = [a, b];
      console.log(JSON.stringify({len, u, after, r3, canRedo, rs, back, noop:H.commit()}));""")
    assert o["len"] == 20 and o["u"] == 19 and o["after"] == 6 and o["r3"] == 9
    assert o["canRedo"] is False and o["rs"] == [0, "x"] and o["back"] == [9, "y"] and o["noop"] is False


def test_ultrasound_sheet_table_is_cited():
    US = json.loads((REPO / "clinical" / "data" / "ultrasound_tissues.json").read_text(encoding="utf-8"))
    st = US["sheet_thickness"]
    assert 0.5 <= st["default_mm"] <= 1.5 and "924" in st["default_src"] and "10.1007/s00276-009-0474-2" in st["default_src"]
    for r in st["rules"]:
        re.compile(r["re"]); assert 0.3 <= r["mm"] <= 4 and r["src"]
    names = {"Fascia lata": 1.0, "Thoracolumbar fascia": 1.0, "Plantar aponeurosis (fascia)": 3.0, "Antebrachial (deep) fascia of the forearm": 0.9}
    for n, mm in names.items():
        got = next((r["mm"] for r in st["rules"] if re.search(r["re"], n, re.I)), st["default_mm"])
        assert got == mm, (n, got)


@needs_node
def test_zoom_plan_resamples_only_the_window():
    o = node("""require('./clinical/ultrasound_tool.js'); const U = globalThis.NMSKUltrasoundLib;
      const out = {};
      [['linear', 44, 0, 0], ['convex', 65, 60, 0], ['sector', 22, 0, 90]].forEach(p => {
        const g = U.fanGeom(p[0], p[1], p[2], p[3], 50);
        const base = U.planRaster(g, 480, {maxLines:256}), win = [-5, 15, 5, 25], z = U.zoomPlan(g, base, win, base.px / 4);
        out[p[0]] = {base:[base.px, base.nL, base.ds], z:[z.px, z.nL, z.L0, z.L1, z.ds, z.capA, z.capL, z.W, z.H, z.Wo, z.Ho, z.sMax, z.xo0, z.yo0]};
      });
      console.log(JSON.stringify(out));""")
    for k, v in o.items():
        px, nL, ds = v["base"]; zpx, znL, L0, L1, zds, capA, capL, W, H, Wo, Ho, sMax, xo0, yo0 = v["z"]
        assert abs(zpx - px / 4) < 1e-9 and znL > nL and 0 <= L0 < L1 < znL and (L1 - L0 + 1) < znL, k
        assert abs(xo0 + 5) < 1e-9 and abs(yo0 - 15) < 1e-9 and abs(Wo * zpx - 10) < 2 * zpx and abs(Ho * zpx - 10) < 2 * zpx
        assert capA >= 16 and capL >= 28 and sMax < 50 + 25


def test_slicer_and_simulator_hooks_in_source():
    src = (REPO / "clinical" / "imaging_tool.js").read_text(encoding="utf-8")
    assert "R.sheetMm ? R.sheetMm[st4] / px : 0" in src
    us = (REPO / "clinical" / "ultrasound_tool.js").read_text(encoding="utf-8")
    assert us.count("sheetMm: sheetMm()") == 2                                 # the 1x frame and the zoom window use the same table
    assert "if (o.seat) { ysk = o.seat.ysk; contact = o.seat.contact; }" in us


def test_labels_carry_the_full_name_and_tips_skip_live_lines():
    lab = (REPO / "viewer" / "labels" / "labels.js").read_text(encoding="utf-8")
    assert 'e.t.setAttribute("data-full", fl)' in lab
    tips = (Q / "tips.js").read_text(encoding="utf-8")
    assert 'p.hasAttribute("aria-live")' in tips and '[data-full], abbr[title]' in tips


def test_cut_and_cross_section_expose_snapshot_restore():
    cm = (REPO / "viewer" / "cut_mode" / "cut_mode.js").read_text(encoding="utf-8")
    assert "snapshot: function()" in cm and "restore: function(o)" in cm
    cc = (REPO / "viewer" / "cut_cap" / "cut_cap.js").read_text(encoding="utf-8")
    for k in ("setPart:setPart", "setPartThickness:setPartTh", "setPartInterval:setPartInt", "setGap:setGap", "snapshot:snapshot", "restore:restore"):
        assert k in cc, k
    z = ZAN.read_text(encoding="utf-8")
    assert "function capAny()" in z and "if (!capGL[0] && !capGL[1]) return;" not in z   # the stack (slots 900+) draws without a Cut-mode face too


@needs_node
def test_sheet_drawn_at_physical_thickness_with_the_oblique_factor_only():
    """root cause of the over-thick zoomed fascia: a sheet was ONE raster pixel wide (its width in mm followed the pixel: depth,
    quality tier, zoom). Now: t mm at every pixel, widened only by 1/cos of the cut's obliquity (true in-plane width)."""
    o = node(r"""require('./clinical/imaging_tool.js'); const L = globalThis.NMSKImagingLib, K = L.KERNEL_FACTORY();
      function sheetGeo(beta) { const e1 = [-Math.sin(beta), 0, Math.cos(beta)], P = [];
        for (const [a, b] of [[-50, -50], [50, -50], [50, 50], [-50, 50]]) P.push(a * e1[0], b, a * e1[2]);
        const lo = [0, 1, 2].map(q => Math.min(...[0, 1, 2, 3].map(k => P[3 * k + q]))), hi = [0, 1, 2].map(q => Math.max(...[0, 1, 2, 3].map(k => P[3 * k + q])));
        return {n: 1, pos: new Float32Array(P), idx: new Uint32Array([0, 1, 2, 0, 2, 3]), vStart: new Int32Array([0, 4]), tStart: new Int32Array([0, 2]), bbox: new Float32Array(lo.concat(hi)),
          cls: new Uint8Array([7]), kind: new Uint8Array([0]), skin: new Uint8Array([0]), render: new Uint8Array([1]), order: new Int32Array([0]), skinList: new Int32Array([])}; }
      const out = {}; let key = 0;
      for (const deg of [0, 30, 60]) { K.setGeometry(sheetGeo(deg * Math.PI / 180));
        for (const px of [0.25, 0.0625]) { const W = Math.round(20 / px), H = W;
          const R = {W, H, O: [0, 0, 0], u: [1, 0, 0], v: [0, 1, 0], n: [0, 0, 1], u0: -10, v0: 10, px, smin: -1, smax: 1, s: 0, wantSid: true, skinMm: 0, ids: {air: 0, fat: 1}, bone: {}, holeMax: 0};
          const row = lab => { let c = 0; const j = H >> 1; for (let i = 0; i < W; i++) if (lab[j * W + i] === 7) c++; return c * px; };
          out[deg + '@' + px] = [row(K.slice(Object.assign({key: 'k' + key++, sheetMm: new Float32Array([0.9])}, R)).lab), row(K.slice(Object.assign({key: 'k' + key++}, R)).lab)]; } }
      console.log(JSON.stringify(out));""")
    for k, (phys, old) in o.items():
        deg, px = k.split("@"); deg, px = float(deg), float(px)
        want = 0.9 / __import__("math").cos(__import__("math").radians(deg))
        assert abs(phys - want) <= px + 1e-6, (k, phys, want)                    # t / cos(obliquity), to one pixel
        assert abs(old - px) < 1e-9, (k, old)                                   # the old rule: one pixel whatever the pixel (CT / MR keep it)


@needs_node
def test_bundle_axes_converge_on_the_insertion_and_drive_the_fibre_direction():
    o = node(r"""require('./clinical/ultrasound_tool.js'); const U = globalThis.NMSKUltrasoundLib;
      const P = []; for (let y = -50; y <= 50; y += 2) for (let f = 0; f <= 1.0001; f += 0.05) for (const z of [-3, 3]) P.push(100 * f, y * (1 - f), z);   // a fan: origins x=0 (medial), insertion (100, 0)
      const pos = new Float32Array(P), n = P.length / 3;
      const spec = {t: 'convergent_triangular', p: 0, c: [['Upper part', 0, 1], ['Middle part', 0, 1], ['Lower part', 0, 1]],
        parts: {axis: 'superior', ins: 'lateral', bands: [[0, 0.33, 'lower part'], [0.33, 0.67, 'middle part'], [0.67, 1, 'upper part']]}};
      const ar = U.archFrame(pos, 0, n, spec, {dirs: {anterior: [0, 0, 1], superior: [0, 1, 0], medial: [-1, 0, 0]}});
      const f = ar.bands.map((b, i) => { const pt = [20, [-35, 0, 35][i], 0]; const v = U.fibreAt(ar, ...pt).slice(); return {band: ar._band, f: v, a: b.a}; });
      const an = U.bundleAxis(pos, 0, n, 1, null, null, [1, 0, 0], {o: [0, 0, 0], i: [10, 10, 0]});
      console.log(JSON.stringify({axes: ar.bands.map(b => b.a), f, an}));""")
    lo, mid, up = o["axes"]
    assert lo[1] > 0.2 and up[1] < -0.2 and abs(mid[1]) < 0.1                 # lower bundle runs up to the insertion, upper runs down, middle across
    for i, q in enumerate(o["f"]):
        assert q["band"] == i and abs(sum(a * b for a, b in zip(q["f"], q["a"]))) > 0.9999   # p = 0: the fibre IS the bundle's own axis
    assert abs(o["an"][0] - 0.7071) < 1e-3 and abs(o["an"][1] - 0.7071) < 1e-3   # placed markers: origin -> insertion


def test_bundle_rows_cover_the_four_muscles_and_resolve_to_compartments():
    A = json.loads((REPO / "clinical" / "data" / "ultrasound_tissues.json").read_text(encoding="utf-8"))["architecture"]["muscles"]
    want = {"deltoid": 3, "pectoralis_major": 3, "trapezius": 3, "rectus_femoris": 2}
    for k, nb in want.items():
        p = A[k]["parts"]; assert len(p["bands"]) == nb and p.get("ins") and p.get("rule"), k
        for b in p["bands"]:
            words = [w for w in b[2].lower().replace("(", " ").replace(")", " ").split() if w not in ("part", "head", "and", "belly")]
            assert any(any(w in c[0].lower() for w in words) for c in A[k]["c"]), (k, b[2])   # each bundle names its own cited compartment
    assert A["rectus_femoris"]["parts"]["split"] == "mesh" and A["rectus_femoris"]["parts"]["whole"] == "straight (direct) head"


def test_probe_model_pad_drag_and_hooks_in_source():
    us = (REPO / "clinical" / "ultrasound_tool.js").read_text(encoding="utf-8")
    for k in ("function probeShape(geom)", "function probeInfo(vi)", "function onDragDown(e)", "function tiltBy(dirDeg, deg)", "function basedFrame(N0, rot, tilt, dir)",
              "probeMesh(probeG, sel.O, sel.pf, sel.geom, sel.sim ? sel.sim.ysk : 0)", "sheetAt: function (vi, xmm, ymm, st)", "bundles: function (re)", "fibreLines: function (sids)",
              'mk("us-h-rr"', 'mk("us-h-th"', 'mk("us-h-t0"', "cv.width >= 200 && cv.height >= 160", "function anchorFn(key, side)"):
        assert k in us, k
    assert "starBase() ? S.mTilt" in us                                          # the user's tilt is part of the raster key in the star mode
    pu = (REPO / "viewer" / "parts_ui" / "parts_ui.js").read_text(encoding="utf-8")
    assert "anchors:function(st, side)" in pu
    for t in (OWN, ZAN):
        assert "anchors:function(st, side)" in t.read_text(encoding="utf-8"), t.name   # synced (sync_parts_ui_q220.py)
