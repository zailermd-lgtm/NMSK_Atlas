"""Q227: marked structures + saved selection sets, and the cut-face fill (cap), in both viewer templates.

Fragment sync, wiring of both engines, the selection controller under node with a mock DOM (mark, only / hide / ghost, save / load / delete, export /
import, link, remember-last, blocked storage, reset), the cap core on synthetic closed and open meshes (cube, sphere, torus, open cube, torn cube,
painter order, parity, pick lookup), the leak-statistics files and, when present, the headless-Chromium check results."""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
OWN = REPO / "viewer" / "atlas_viewer.template.html"
ZAN = REPO / "viewer" / "zan_atlas.template.html"
SEL = REPO / "viewer" / "selection"
CAP = REPO / "viewer" / "cut_cap" / "cut_cap.js"
sys.path.insert(0, str(REPO / "scripts"))
import sync_q227 as sync  # noqa: E402

NODE = shutil.which("node")
needs_node = pytest.mark.skipif(not NODE, reason="node not available")


# ---------------------------------------------------------------- the shared blocks are in both templates, verbatim
@pytest.mark.parametrize("tpl", [OWN, ZAN], ids=["own", "zan"])
def test_templates_carry_the_shared_blocks_verbatim(tpl):
    t = tpl.read_text(encoding="utf-8")
    for name, (path, b, e) in sync.BLOCKS.items():
        frag = path.read_text(encoding="utf-8").rstrip("\n")
        assert t.count(b) == 1 and t.count(e) == 1, name
        assert t[t.index(b) + len(b):t.index(e)] == "\n" + frag + "\n", f"{tpl.name}: {name} differs from {path.relative_to(REPO)} (run scripts/sync_q227.py)"


def test_sync_check_passes():
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "sync_q227.py"), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_cut_panel_has_the_cap_controls_in_both_templates():
    for tpl in (OWN, ZAN):
        t = tpl.read_text(encoding="utf-8")
        for i in ("cut-fill", "cut-look", "cut-capinfo"):
            assert f'id="{i}"' in t, (tpl.name, i)


@pytest.mark.parametrize("tpl", [OWN, ZAN], ids=["own", "zan"])
def test_engines_wire_selection_and_cap(tpl):
    t = tpl.read_text(encoding="utf-8")
    for needle in ("selCtl = NMSKSelect({", "capCtl = NMSKCap({", "selCtl.look(", "selCtl.tinted(", "selCtl.consumeClick(e)", "selCtl.markButton(",
                   "capCtl.planeChanged()", "capUpload", "window.__selState", "window.__capState", "lookAt:function"):
        assert needle in t, (tpl.name, needle)
    # the selection click is tried after the cut placing click and before the add-on's
    i = t.index("selCtl.consumeClick(e)")
    assert t.index("cutCtl.consumeClick(e)") < i < t.index("addonClick(e)", i - 300)
    assert ('rule(o.id) === "hide"' in t) or ('selCtl.look(s.id)' in t)


def test_own_engine_uses_a_textured_quad_and_line_segments():
    t = OWN.read_text(encoding="utf-8")
    for needle in ("THREE.DataTexture(res.rgba", "THREE.LineSegments(lg", "polygonOffset:true", "capHitAt(e, h)", "NearestFilter"):
        assert needle in t, needle


def test_zan_engine_draws_cap_in_colour_id_and_depth_passes():
    t = ZAN.read_text(encoding="utf-8")
    for needle in ("var cprog = mkProg(CVS, CFS", "drawCap(mvp);", "drawCapPick(lastMVP, depth ? 2 : 1)", "gl.POLYGON_OFFSET_FILL", "uMode>1.5", "capGeom(i, o)",
                   "e.shiftKey&&!panToggle", "capCtl.itemsChanged()"):
        assert needle in t, needle
    assert t.index("drawCap(mvp);") < t.index("drawPartDots(mvp, eye);\n      if (addonDraw.length)")


def test_nothing_private_in_the_fragments():
    for p in list(SEL.glob("*")) + [CAP]:
        txt = p.read_text(encoding="utf-8").lower()
        for w in ("clinical_", "needle", "motor point", "imaging_tool"):
            assert w not in txt, (p.name, w)


# ---------------------------------------------------------------- the cap core under node
CAP_HARNESS = r"""
const fs = require('fs');
const C = new Function(fs.readFileSync(process.argv[2], 'utf8') + ';return NMSKCapCore;')();
function cube(s, c){ const h = s/2, P = []; for (let i = 0; i < 8; i++) P.push(c[0]+((i&1)?h:-h), c[1]+((i&2)?h:-h), c[2]+((i&4)?h:-h));
  const q = [[0,1,3,2],[4,6,7,5],[0,4,5,1],[2,3,7,6],[0,2,6,4],[1,5,7,3]], I = []; q.forEach(f => I.push(f[0],f[1],f[2],f[0],f[2],f[3]));
  return {pos:new Float32Array(P), idx:new Uint16Array(I)}; }
function sphere(R, c, nl=40, nm=64){ const P = [], I = [];
  for (let i = 0; i <= nl; i++){ const th = Math.PI*i/nl; for (let j = 0; j < nm; j++){ const ph = 2*Math.PI*j/nm; P.push(c[0]+R*Math.sin(th)*Math.cos(ph), c[1]+R*Math.cos(th), c[2]+R*Math.sin(th)*Math.sin(ph)); } }
  for (let i = 0; i < nl; i++) for (let j = 0; j < nm; j++){ const a = i*nm+j, b = i*nm+(j+1)%nm, c2 = (i+1)*nm+j, d = (i+1)*nm+(j+1)%nm; I.push(a,c2,b,b,c2,d); }
  return {pos:new Float32Array(P), idx:new Uint16Array(I)}; }
function torus(R, r, c, nu=64, nv=32){ const P = [], I = [];
  for (let i = 0; i < nu; i++){ const u = 2*Math.PI*i/nu; for (let j = 0; j < nv; j++){ const v = 2*Math.PI*j/nv; P.push(c[0]+(R+r*Math.cos(v))*Math.cos(u), c[1]+r*Math.sin(v), c[2]+(R+r*Math.cos(v))*Math.sin(u)); } }
  for (let i = 0; i < nu; i++) for (let j = 0; j < nv; j++){ const a = i*nv+j, b = ((i+1)%nu)*nv+j, c2 = i*nv+(j+1)%nv, d = ((i+1)%nu)*nv+(j+1)%nv; I.push(a,b,c2,c2,b,d); }
  return {pos:new Float32Array(P), idx:new Uint16Array(I)}; }
function item(key, g, cat='muscle', rgb=[.7,.2,.2], a=1){ const mn=[1e9,1e9,1e9], mx=[-1e9,-1e9,-1e9];
  for (let i = 0; i < g.pos.length; i += 3) for (let k = 0; k < 3; k++){ mn[k]=Math.min(mn[k],g.pos[i+k]); mx[k]=Math.max(mx[k],g.pos[i+k]); }
  g.bmin = mn; g.bmax = mx; return {key, name:key, cat, rgb, alpha:a, geom:() => g}; }
function area(res, code){ let n = 0; for (let i = 0; i < res.ids.length; i++) if (res.ids[i] === code) n++; return n*res.px*res.px; }
const out = {};
let r = C.build([item('cube', cube(40,[0,0,0]))], {n:[0,1,0], d:0.3});
out.cube = {area:area(r,1), expect:1600, filled:r.stats.filled, odd:r.stats.odd_rows};
r = C.build([item('sph', sphere(30,[0,0,0]))], {n:[0,1,0], d:10});
out.sphere = {area:area(r,1), expect:Math.PI*(900-100), odd:r.stats.odd_rows};
r = C.build([item('tor', torus(40,10,[0,0,0]))], {n:[0,1,0], d:3});
const rr = Math.sqrt(100-9); out.torus = {area:area(r,1), expect:Math.PI*((40+rr)**2-(40-rr)**2), odd:r.stats.odd_rows};
// the same torus cut through the hole axis: two discs
r = C.build([item('tor', torus(40,10,[0,0,0]))], {n:[0,0,1], d:0});
out.torus_side = {area:area(r,1), expect:2*Math.PI*100, odd:r.stats.odd_rows};
// open cube (the z- face removed: the contour is a U, rows have one crossing): outline only, nothing filled
let oc = cube(40,[0,0,0]); const ix = Array.from(oc.idx); ix.splice(0,6); oc.idx = new Uint16Array(ix);
r = C.build([item('open', oc)], {n:[0,1,0], d:0.3});
out.open = {status:r.items[0].status, filled_px:area(r,1), odd:r.stats.odd_rows, rows:r.stats.rows, lines:r.lines.count, outline_only:r.stats.outline_only};
// an open mesh whose hole is horizontal in plane coordinates is still filled right (the missing edge crosses no row)
let oc2 = cube(40,[0,0,0]); const ix2 = Array.from(oc2.idx); ix2.splice(24,6); oc2.idx = new Uint16Array(ix2);
r = C.build([item('open2', oc2)], {n:[0,1,0], d:0.3});
out.open_horizontal = {status:r.items[0].status, area:area(r,1)};
// a 0.4 mm tear (duplicated vertices of one face): closed by the 1 mm gap closing, repaired by row copy when the closing is off
let tc = cube(40,[0,0,0]); const P2 = Array.from(tc.pos), I2 = Array.from(tc.idx), mp = {};
I2.slice(0,6).forEach((v,k) => { if (mp[v] == null){ mp[v] = P2.length/3; P2.push(P2[3*v]+0.4, P2[3*v+1], P2[3*v+2]); } I2[k] = mp[v]; });
tc = {pos:new Float32Array(P2), idx:new Uint16Array(I2)};
const t0 = C.build([item('tear', tc)], {n:[0,1,0], d:0.3}, {gap:0}), t1 = C.build([item('tear', tc)], {n:[0,1,0], d:0.3}, {gap:1});
out.tear = {open_before:t1.stats.open_ends_before, joined:t1.stats.joined, odd_closed:t1.stats.odd_rows, area_closed:area(t1,1), odd_open:t0.stats.odd_rows, repaired_open:t0.stats.repaired_rows, status_open:t0.items[0].status, area_open:area(t0,1)};
// duplicated faces (double-sided duplicates) must not cancel in the even-odd count
let dc = cube(40,[0,0,0]); dc.idx = new Uint16Array(Array.from(dc.idx).concat(Array.from(dc.idx)));
r = C.build([item('dup', dc)], {n:[0,1,0], d:0.3});
out.duplicate_faces = {area:area(r,1), dup:r.stats.duplicate_segments};
// painter order: a small vessel inside a big muscle is painted last whatever the list order; a bone is painted over a bigger muscle of the same size class
const items = [item('vessel', sphere(5,[0,0,0]), 'vessel', [0,0,1]), item('muscle', cube(80,[0,0,0]), 'muscle')];
r = C.build(items, {n:[0,1,0], d:0.2}); C.recolor(r, items);
out.painter = {order:r.items.map(i => i.key), small:area(r, r.items.find(i => i.key==='vessel').code), big:area(r, r.items.find(i => i.key==='muscle').code),
  hit_small:C.lookup(r,[1,0.2,1]).key, hit_big:C.lookup(r,[30,0.2,30]).key, hit_none:C.lookup(r,[500,0.2,500]) };
// colours: the texture follows the display colours; a colour-only change needs no new section; alpha 0 / translucent
const px = (res, p) => { const u = p[0]*res.U[0]+p[1]*res.U[1]+p[2]*res.U[2], v = p[0]*res.V[0]+p[1]*res.V[1]+p[2]*res.V[2];
  const x = Math.floor((u-res.u0)/res.px), y = Math.floor((v-res.v0)/res.px), o = 4*(y*res.w+x); return Array.from(res.rgba.slice(o, o+4)); };
out.colour_vessel = px(r,[1,0.2,1]); out.colour_muscle = px(r,[30,0.2,30]);
const two = [item('a', sphere(5,[0,0,0]), 'vessel', [0,0,1]), item('b', cube(10,[40,0,0]), 'muscle')]; const r2 = C.build(two, {n:[0,1,0], d:0.2}); C.recolor(r2, two);
out.colour_empty = px(r2,[20,0.2,0]);
items[1].rgb = [0,1,0]; items[1].alpha = 0.5; C.recolor(r, items); out.colour_muscle_after = px(r,[30,0.2,30]);
// a ghost / invisible structure (alpha < 0.2) is not cut at all
r = C.build([item('ghost', cube(40,[0,0,0]), 'muscle', [1,0,0], 0.1)], {n:[0,1,0], d:0.3});
out.ghost = {cut:r.stats.structures_cut, w:r.w};
// the plane misses the mesh
r = C.build([item('far', cube(40,[0,0,0]))], {n:[0,1,0], d:100});
out.miss = {cut:r.stats.structures_cut};
// a slab: the far face at d + th is built separately
const rs = C.build([item('cube', cube(40,[0,0,0]))], {n:[0,1,0], d:15});
out.offset = {area:area(rs,1), expect:1600};
// the outline: a contour segment lies in the plane; a segment inside a later painted structure is not drawn
const il = [item('vessel', sphere(5,[0,0,0]), 'vessel', [0,0,1]), item('muscle', cube(80,[0,0,0]), 'muscle')];
r = C.build(il, {n:[0,1,0], d:0.2});
let maxdev = 0; for (let k = 0; k < r.lines.count*2; k++) maxdev = Math.max(maxdev, Math.abs(r.lines.pos[3*k+1]-0.2));
out.lines = {count:r.lines.count, max_off_plane:maxdev, segs_total:r._cut.reduce((a,c)=>a+c.S.sa.length,0)};
// speed: 300 small spheres
const many = []; for (let i = 0; i < 300; i++) many.push(item('s'+i, sphere(8,[(i%20)*15-150,0,(i/20|0)*15-100],30,40)));
const T = Date.now(); r = C.build(many, {n:[0,1,0], d:0.1}); out.many = {ms:Date.now()-T, filled:r.stats.filled};
console.log(JSON.stringify(out));
"""


@pytest.fixture(scope="module")
def cap_out():
    if not NODE:
        pytest.skip("node not available")
    with tempfile.TemporaryDirectory() as td:
        h = Path(td) / "h.js"
        h.write_text(CAP_HARNESS)
        r = subprocess.run([NODE, str(h), str(CAP)], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_cap_fills_closed_meshes_with_the_analytic_area(cap_out):
    for k, tol in (("cube", 0.01), ("sphere", 0.02), ("torus", 0.02), ("torus_side", 0.02)):
        a = cap_out[k]
        assert abs(a["area"] - a["expect"]) / a["expect"] < tol, (k, a)
        assert a["odd"] == 0, (k, a)


def test_cap_open_mesh_is_outline_only_not_a_wrong_fill(cap_out):
    o = cap_out["open"]
    assert o["status"] == "outline" and o["filled_px"] == 0 and o["odd"] == o["rows"] and o["lines"] > 0 and o["outline_only"] == 1
    h = cap_out["open_horizontal"]                       # the missing face crosses no pixel row: parity holds, the fill is right
    assert h["status"] == "filled" and abs(h["area"] - 1600) < 20


def test_cap_tear_is_closed_within_a_millimetre_and_repaired_otherwise(cap_out):
    t = cap_out["tear"]
    assert t["open_before"] >= 2 and t["joined"] >= 1 and t["odd_closed"] == 0 and abs(t["area_closed"] - 1600) < 6
    assert t["odd_open"] > 0 and t["repaired_open"] > 0 and t["status_open"] == "filled" and abs(t["area_open"] - 1600) < 60


def test_cap_duplicate_faces_do_not_cancel(cap_out):
    assert cap_out["duplicate_faces"]["dup"] > 0 and abs(cap_out["duplicate_faces"]["area"] - 1600) < 20


def test_cap_painter_order_and_pick_lookup(cap_out):
    p = cap_out["painter"]
    assert p["order"] == ["muscle", "vessel"]                          # the small vessel is painted last
    assert abs(p["small"] - 78.4) < 3 and abs(p["big"] - (6400 - 78.5)) < 40
    assert p["hit_small"] == "vessel" and p["hit_big"] == "muscle" and p["hit_none"] is None


def test_cap_colours_follow_the_display_state(cap_out):
    assert cap_out["colour_vessel"] == [0, 0, 255, 255] and cap_out["colour_muscle"][3] == 255 and cap_out["colour_empty"] == [0, 0, 0, 0]
    assert cap_out["colour_muscle_after"] == [0, 255, 0, 128]


def test_cap_skips_ghosts_and_misses_and_offsets(cap_out):
    assert cap_out["ghost"]["cut"] == 0 and cap_out["miss"]["cut"] == 0
    assert abs(cap_out["offset"]["area"] - 1600) / 1600 < 0.01


def test_cap_outline_lies_in_the_plane_and_hides_under_later_fills(cap_out):
    ln = cap_out["lines"]
    assert ln["max_off_plane"] < 1e-3 and 0 < ln["count"] <= ln["segs_total"]


def test_cap_is_fast_enough(cap_out):
    assert cap_out["many"]["filled"] == 300 and cap_out["many"]["ms"] < 1500


# ---------------------------------------------------------------- the selection controller under node (mock DOM)
SEL_HARNESS = r"""
const fs = require('fs');
const src = fs.readFileSync(process.argv[2], 'utf8');
const scenario = process.argv[3];
function el(id){ const e = {id, className:'', hidden:false, style:{}, children:[], _l:{}, value:'', checked:true, disabled:false, open:false, textContent:'', _a:{}, title:'',
  classList:{_s:{}, toggle(k,v){ this._s[k] = v === undefined ? !this._s[k] : !!v; }, add(k){ this._s[k]=true; }, remove(k){ this._s[k]=false; }, contains(k){ return !!this._s[k]; }},
  addEventListener(t,f){ (this._l[t] = this._l[t]||[]).push(f); }, appendChild(c){ this.children.push(c); }, removeAttribute(k){ delete this._a[k]; },
  setAttribute(k,v){ this._a[k]=String(v); }, getAttribute(k){ return this._a[k] == null ? null : this._a[k]; },
  click(){ (this._l.click||[]).forEach(f => f({target:this, stopPropagation(){}})); }, closest(){ return null; }};
  Object.defineProperty(e, 'innerHTML', {set(v){ this._h = v; }, get(){ return this._h || ''; }}); return e; }
const els = {};
global.document = {getElementById(i){ return els[i] || (els[i] = el(i)); }, createElement(){ return el(null); }, querySelectorAll(){ return []; },
  body:el('body'), documentElement:el('html')};
const store = {}; let blocked = scenario === 'blocked';
global.localStorage = {getItem(k){ if (blocked) throw new Error('blocked'); return k in store ? store[k] : null; },
  setItem(k,v){ if (blocked) throw new Error('blocked'); store[k] = String(v); }, removeItem(k){ delete store[k]; }};
global.location = {hash:'', href:'https://example.test/page.html'};
global.navigator = {clipboard:{writeText(t){ global.__copied = t; return Promise.resolve(); }}};
global.window = {addEventListener(){}}; 
let hash = ''; try { hash = JSON.parse(process.argv[4] || '""'); } catch (e) {}
global.location.hash = hash;
eval(src + '; global.NMSKSelect = NMSKSelect;');
const ITEMS = [['biceps_r','Biceps brachii (R)'],['biceps_l','Biceps brachii (L)'],['femur_r','Femur (R)'],['femur_l','Femur (L)'],['sartorius_r','Sartorius (R)'],['skin','Skin']].map(a => ({id:a[0], name:a[1]}));
let refreshes = 0, revealed = [], selectedId = null, picked = null, hoverCleared = 0, engineReset = 0;
const toolbar = el('tb'), canvas = el('canvas');
const E = {modelId:() => 'own:vhm', items:() => ITEMS, refresh(){ refreshes++; }, selected:() => selectedId, select(id){ selectedId = id; }, reveal(ids){ revealed = revealed.concat(ids); },
  listIds:() => ['femur_r','femur_l','nope'], pickId:() => picked, clearHover(){ hoverCleared++; }, resetEngine(){ engineReset++; }, canvas, toolbar, toolClass:'tool', isPhone:() => false};
const out = {};
let C = NMSKSelect(E);
const S = () => C.state();
if (scenario === 'basic' || scenario === 'blocked'){
  out.initial = S();
  out.toolbar = toolbar.children.map(c => c.id);
  C.toggle('biceps_r', true); C.toggle('femur_r', true); C.toggle('nope');            // unknown ids are ignored
  out.marks = S().marks; out.revealed = revealed.slice();
  out.rule_all = ['biceps_r','skin'].map(i => C.rule(i));
  C.setMode('only'); out.rule_only = ['biceps_r','femur_r','skin','femur_l'].map(i => C.rule(i)); out.mode_only = S().mode;
  C.setGhost(); out.rule_ghost = ['biceps_r','skin'].map(i => C.rule(i)); out.ghosting = C.ghosting();
  C.setMode('hide'); out.rule_hide_ghost = ['biceps_r','skin'].map(i => C.rule(i));
  C.setGhost(false); out.rule_hide = ['biceps_r','skin'].map(i => C.rule(i));
  C.setMode('hide'); out.mode_back_to_all = S().mode;                                    // pressing the active mode again returns to "all"
  out.marked_flags = [C.isMarked('biceps_r'), C.isMarked('skin')];
  // mark button + chips
  const b = C.markButton('femur_l'); b.click(); out.markbtn = [b._a['aria-pressed'], S().marks.length];
  // mark list: only ids that exist
  els['sel-markall'].click(); out.after_marklist = S().marks.slice();
  selectedId = 'sartorius_r'; els['sel-markcur'].click(); out.after_markcur = S().marks.indexOf('sartorius_r') >= 0;
  // save / load / delete
  els['sel-name'].value = 'Thigh set'; els['sel-save'].click(); out.sets_after_save = S().sets; out.stored = store['nmsk.sel.v1:own:vhm'] ? JSON.parse(store['nmsk.sel.v1:own:vhm']) : null;
  C.setMode('only');
  els['sel-reset'].click(); out.after_reset = S(); out.reset_calls = [selectedId, hoverCleared, engineReset];
  els['sel-sets'].value = 'Thigh set'; els['sel-load'].click(); out.after_load = S(); out.load_reveals = revealed.length;
  const txt = C.exportText(); out.export = JSON.parse(txt);
  els['sel-del'].click(); out.sets_after_delete = S().sets;
  // import: the exported text brings the set back; unknown ids are dropped
  const o2 = JSON.parse(txt); o2.sets['Mixed'] = {ids:['skin','ghost_id'], mode:'only', ghost:true}; o2.sets['Bad'] = {ids:['zzz'], mode:'all'};
  out.import_ok = C.importText(JSON.stringify(o2)); out.sets_after_import = S().sets;
  out.import_bad = [C.importText('not json'), C.importText(''), C.importText('{"x":1}')];
  els['sel-sets'].value = 'Mixed'; els['sel-load'].click(); out.mixed = S();
  // the link
  els['sel-clear'].click(); C.toggle('femur_r'); C.toggle('skin'); C.setMode('only'); C.setGhost();
  out.link = C.link(); out.status = els['sel-status'].textContent;
  // import from a link string
  els['sel-clear'].click(); out.cleared = S().marks.length; C.importText(out.link); out.from_link = S();
  // multi click: Shift / Ctrl / mark mode / nothing under
  els['sel-reset'].click(); picked = 'femur_l';
  out.click_plain = C.consumeClick({}); out.click_shift = [C.consumeClick({shiftKey:true}), S().marks.slice()];
  out.click_ctrl_toggles_off = [C.consumeClick({ctrlKey:true}), S().marks.slice()]; out.click_meta = [C.consumeClick({metaKey:true}), S().marks.slice()];
  picked = null; out.click_nothing = [C.consumeClick({shiftKey:true}), S().marks.slice()];
  els['sel-markmode'].click(); picked = 'femur_r'; out.markmode = [S().markMode, C.consumeClick({}), S().marks.slice()]; els['sel-markmode'].click();
  // unmarking the last mark leaves "only" mode
  els['sel-reset'].click(); C.toggle('skin'); C.setMode('only'); C.toggle('skin'); out.last_unmarked_mode = S().mode;
  out.mode_without_marks = (C.setMode('only'), S().mode);
  out.refreshes = refreshes;
  out.store_note = els['sel-store'].textContent; out.storageOK = S().storageOK;
}
if (scenario === 'persist'){
  // first session: mark + only + save, "remember last" on
  C.toggle('biceps_r'); C.toggle('femur_l'); C.setMode('only'); els['sel-name'].value = 'A'; els['sel-save'].click();
  out.s1 = S(); const keep = JSON.stringify(store);
  // second session: the remembered selection comes back (marks + mode), the saved set too
  Object.keys(els).forEach(k => delete els[k]); refreshes = 0;
  C = NMSKSelect(E); out.s2 = S(); out.restored = C.restored; out.refresh_on_restore = refreshes > 0;
  // remember off: nothing comes back next time
  els['sel-remember'].checked = false; els['sel-remember']._l.change.forEach(f => f());
  Object.keys(els).forEach(k => delete els[k]); C = NMSKSelect(E); out.s3 = S();
  // a link in the address beats the remembered selection and needs the same model
  global.location.hash = '#nmsksel=own%3Avhm~hide~0~femur_r,skin,gone'; Object.keys(els).forEach(k => delete els[k]); C = NMSKSelect(E); out.s4 = S();
  global.location.hash = '#nmsksel=zan%3Avhm~only~0~femur_r'; Object.keys(els).forEach(k => delete els[k]); C = NMSKSelect(E); out.s5 = S();
}
console.log(JSON.stringify(out));
"""


def run_sel(scenario, hash_=""):
    if not NODE:
        pytest.skip("node not available")
    with tempfile.TemporaryDirectory() as td:
        h = Path(td) / "h.js"
        h.write_text(SEL_HARNESS)
        r = subprocess.run([NODE, str(h), str(SEL / "selection.js"), scenario, json.dumps(hash_)], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


@pytest.fixture(scope="module")
def basic():
    return run_sel("basic")


def test_sel_marks_rules_and_modes(basic):
    o = basic
    assert o["initial"]["marks"] == [] and o["initial"]["mode"] == "all" and o["initial"]["model"] == "own:vhm"
    assert o["toolbar"] == ["t-mark", "t-only", "t-invert"]
    assert o["marks"] == ["biceps_r", "femur_r"] and o["revealed"] == ["biceps_r", "femur_r"]            # the list tick reveals the layer; 'nope' is ignored
    assert o["rule_all"] == ["", ""]
    assert o["rule_only"] == ["", "", "hide", "hide"]
    assert o["rule_ghost"] == ["", "ghost"] and o["ghosting"] is True
    assert o["rule_hide_ghost"] == ["ghost", ""] and o["rule_hide"] == ["hide", ""]
    assert o["mode_back_to_all"] == "all" and o["marked_flags"] == [True, False]


def test_sel_mark_button_list_and_current(basic):
    o = basic
    assert o["markbtn"] == ["true", 3]
    assert o["after_marklist"] == ["biceps_r", "femur_r", "femur_l"]                 # 'Mark list' marks the listed ids that exist, once
    assert o["after_markcur"] is True


def test_sel_save_load_delete_and_storage(basic):
    o = basic
    assert o["sets_after_save"] == ["Thigh set"]
    st = o["stored"]
    assert st["v"] == 1 and st["model"] == "own:vhm" and st["sets"]["Thigh set"]["ids"] == ["biceps_r", "femur_r", "femur_l", "sartorius_r"]
    assert o["after_reset"]["marks"] == [] and o["after_reset"]["mode"] == "all" and o["after_reset"]["ghost"] is False
    assert o["reset_calls"][0] is None and o["reset_calls"][1] >= 1 and o["reset_calls"][2] >= 1        # card closed, hover cleared, the engine's own isolation reset
    assert o["after_load"]["marks"] == ["biceps_r", "femur_r", "femur_l", "sartorius_r"]
    assert o["sets_after_delete"] == []
    assert o["storageOK"] is True and "stay in this browser" in o["store_note"]


def test_sel_export_import_link(basic):
    o = basic
    assert o["export"]["nmsk_selection"] == 1 and o["export"]["model"] == "own:vhm" and "Thigh set" in o["export"]["sets"]
    assert o["import_ok"] is True and o["sets_after_import"] == ["Mixed", "Thigh set"]               # 'Bad' has no id of this model: dropped
    assert o["import_bad"] == [False, False, False]
    assert o["mixed"]["marks"] == ["skin"] and o["mixed"]["mode"] == "only" and o["mixed"]["ghost"] is True
    assert o["link"].startswith("#nmsksel=own%3Avhm~only~1~") and "femur_r" in o["link"] and "skin" in o["link"]
    assert o["cleared"] == 0 and o["from_link"]["marks"] == ["femur_r", "skin"] and o["from_link"]["mode"] == "only" and o["from_link"]["ghost"] is True


def test_sel_clicks_in_3d(basic):
    o = basic
    assert o["click_plain"] is False                                                   # a plain click is the engine's (select)
    assert o["click_shift"] == [True, ["femur_l"]] and o["click_ctrl_toggles_off"] == [True, []] and o["click_meta"] == [True, ["femur_l"]]
    assert o["click_nothing"][0] is True and o["click_nothing"][1] == ["femur_l"]
    assert o["markmode"] == [True, True, ["femur_l", "femur_r"]]
    assert o["last_unmarked_mode"] == "all" and o["mode_without_marks"] == "all"


def test_sel_blocked_storage_falls_back_to_memory():
    o = run_sel("blocked")
    assert o["initial"]["storageOK"] is False
    assert o["sets_after_save"] == ["Thigh set"] and o["stored"] is None and o["storageOK"] is False
    assert "blocks storage" in o["store_note"]
    assert o["after_load"]["marks"] == ["biceps_r", "femur_r", "femur_l", "sartorius_r"]            # sets still work for the session
    assert o["export"]["sets"]["Thigh set"]["ids"][0] == "biceps_r"                                   # and can be exported as text
    assert o["from_link"]["marks"] == ["femur_r", "skin"]


def test_sel_remember_last_and_link_in_the_address():
    o = run_sel("persist")
    assert o["s1"]["marks"] == ["biceps_r", "femur_l"] and o["s1"]["mode"] == "only"
    assert o["s2"]["marks"] == ["biceps_r", "femur_l"] and o["s2"]["mode"] == "only" and o["s2"]["sets"] == ["A"] and "Restored" in o["restored"] and o["refresh_on_restore"]
    assert o["s3"]["marks"] == [] and o["s3"]["sets"] == ["A"] and o["s3"]["remember"] is False
    assert o["s4"]["marks"] == ["femur_r", "skin"] and o["s4"]["mode"] == "hide"                    # unknown id 'gone' dropped
    assert o["s5"]["marks"] == []                                                                  # a link for another model is ignored


# ---------------------------------------------------------------- statistics files + browser results (present after the regeneration / check runs)
PAGES = ["own_m", "own_f", "zan_m", "zan_f", "base_f", "base_m"]


@pytest.mark.parametrize("page", PAGES)
def test_cap_stats_file(page):
    p = REPO / "data" / "derived" / f"Q227_cap_stats_{page}.json"
    if not p.exists():
        pytest.skip("run scripts/q227_cap_stats.js (see PROJECT_STATE Q227)")
    d = json.loads(p.read_text())
    t = d["totals"]
    assert d["page"] == page and t["planes"] >= 6 and t["structures_cut"] > 100
    assert t["filled"] + t["outline_only"] + t["thin"] == t["structures_cut"]
    assert t["odd_row_fraction_in_filled"] < 0.02 and t["outline_only_fraction"] < 0.2 and t["ms_max"] < 500
    assert d["params"]["gap_mm"] == 1.0


@pytest.mark.parametrize("page", PAGES)
def test_browser_check_results(page):
    p = REPO / "data" / "derived" / f"Q227_browser_check_{page}.json"
    if not p.exists():
        pytest.skip("run scripts/zanatomy/q227_check.py (see PROJECT_STATE Q227)")
    d = json.loads(p.read_text())
    assert d["viewports"], "no viewport result"
    for name, v in d["viewports"].items():
        assert v["errors"] == [], (name, v["errors"])
        bad = [k for k, ok in v["checks"].items() if ok is False]
        assert not bad, (name, bad)


# ---------------------------------------------------------------- the six regenerated pages (build/q227, git-ignored: skipped where absent)
SOURCES = {  # page dir name -> candidate source dirs (first that exists), the geometry must be byte identical to it
    "viewer_m_hr": ["build/q224/viewer_m_hr"], "viewer_f_hr": ["build/q224/viewer_f_hr"],
    "viewer_zan_vhm": ["build/q225/viewer_zan_vhm", "build/q221/viewer_zan_vhm"], "viewer_zan_female": ["build/q225/viewer_zan_female", "build/q222/viewer_zan_female"],
    "viewer_base_female": ["build/q222/viewer_base_female"], "viewer_zan_atlas": ["build/q222/viewer_zan_atlas"]}


@pytest.mark.parametrize("name", sorted(SOURCES))
def test_regenerated_page_has_the_blocks_and_identical_geometry(name):
    import hashlib
    d = REPO / "build" / "q227" / name
    if not d.is_dir():
        pytest.skip("run scripts/regen_cut_q218.sh with Q218_OUT=build/q227 (see PROJECT_STATE Q227)")
    src = next((REPO / s for s in SOURCES[name] if (REPO / s).is_dir()), None)
    if src is None:
        pytest.skip("source dir absent")
    html = next(d.glob("atlas_viewer*.html"))
    t = html.read_text(encoding="utf-8")
    for needle in ("function NMSKSelect(E)", "function NMSKCap(E)", "var NMSKCapCore", 'id="sel-sec"', 'id="cut-fill"'):
        assert needle in t, needle
    geo = sorted(d.glob("*_geo_*.txt"))
    assert geo, "no geo files"
    for g in geo:
        assert hashlib.sha256(g.read_bytes()).hexdigest() == hashlib.sha256((src / g.name).read_bytes()).hexdigest(), g.name
    v = json.loads((REPO / "build" / "q227" / "_verify" / f"{name}.json").read_text())
    assert v["OK"] and v["geo_identical"] and v["literals_identical"] and v["new_equals_current_template_plus_same_data"]
