"""Q240 (A): view-dependent culling of the Parts markers.

Shared controller (viewer/parts_ui/parts_ui.js) under node with a synthetic engine (an orthographic-ish camera, a hand-made depth image + ID image): modes Off / Visible + near /
Selected only / All, occlusion by the depth image (own-structure exception), the depth band, selected / marked / hovered exemption with the see-through flag, the
"Show hidden ones of selected muscles" switch, Cut mode, persistence, the fallback of a page without the culling adaptor; plus the wiring in both templates (adaptor members, the
depth pass of each engine, hooks) and the build chain (regen_q240.sh, sync scripts)."""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
OWN = REPO / "viewer" / "atlas_viewer.template.html"
ZAN = REPO / "viewer" / "zan_atlas.template.html"
FRAG = REPO / "viewer" / "parts_ui"
sys.path.insert(0, str(REPO / "scripts"))
import sync_parts_ui_q220 as sync  # noqa: E402

NODE = shutil.which("node")

HARNESS = r"""
const fs = require('fs');
const src = fs.readFileSync(process.argv[2], 'utf8');
const sc = JSON.parse(process.argv[3]);
function el(){ const e = {className:'', hidden:false, style:{}, children:[], _l:{}, classList:{toggle(){}, add(){}, remove(){}},
  addEventListener(t,f){ (this._l[t] = this._l[t]||[]).push(f); }, appendChild(c){ this.children.push(c); }, querySelector(){ return el(); },
  querySelectorAll(){ return []; }, setAttribute(k,v){ this[k]=v; }, getBoundingClientRect(){ return {left:0,top:0,right:100,bottom:30,width:100,height:30}; },
  contains(){ return false; }, closest(){ return null; }, click(){}, offsetWidth:300, offsetHeight:200};
  Object.defineProperty(e, 'innerHTML', {set(v){ this._h = v; this.firstChild = el(); }, get(){ return this._h || ''; }}); return e; }
const store = {};
global.localStorage = {getItem:k => (k in store ? store[k] : null), setItem:(k,v) => { store[k] = String(v); }};
if (sc.noStorage) global.localStorage = {getItem(){ throw new Error('blocked'); }, setItem(){ throw new Error('blocked'); }};
if (sc.preset) store['nmsk.parts.v1'] = JSON.stringify(sc.preset);
global.document = {getElementById(i){ return (this._e = this._e||{})[i] = (this._e[i]||el()); }, createElement(){ return el(); }, addEventListener(){}, documentElement:{clientWidth:1400, clientHeight:900}};
global.window = {fetch:true, matchMedia:()=>({matches:true})}; global.matchMedia = window.matchMedia;
const data = sc.data;
global.fetch = () => Promise.resolve({ok:true, json:()=>Promise.resolve(data)});
eval(src + '; global.NMSKParts = NMSKParts;');
// synthetic camera: looks along -z from z = 1000; NDC x = p.x / 500, y = p.y / 500; view depth w = 1000 - p.z
const IDS = {m_front:1, m_back:2, m_far:3, wall:9};
let wall = null, cutState = null, visible = {}, dots = [], marks = [], depthCalls = 0, redraws = 0;
const BW = 100, BH = 80;
function pix(p){ const w = 1000 - p[2]; return [Math.floor((p[0] / 500 * 0.5 + 0.5) * BW), Math.floor((0.5 - 0.5 * p[1] / 500) * BH), w]; }
function image(){
  const z = new Float32Array(BW * BH), ids = new Uint16Array(BW * BH);
  (sc.surfaces || []).forEach(s => { for (let y = s.y0; y < s.y1; y++) for (let x = s.x0; x < s.x1; x++){ z[y * BW + x] = s.z; ids[y * BW + x] = IDS[s.id] || 0; } });
  return {w:BW, h:BH, z, ids};
}
const E = {url:'x', canvasRect:()=>({left:0,top:0,right:1000,bottom:800,width:1000,height:800}),
  project:(p)=>{ const w = 1000 - p[2]; return [p[0] / 500 * w, p[1] / 500 * w, 0, w]; },
  cut:()=>cutState, meshVisible:(id)=>visible[id]!==false, focusAt(){}, redraw(){ redraws++; }, setDots:(l)=>{ dots = l; }, toolbar:el(), toolClass:'tool', onLoaded(){},
  marked:()=>marks};
if (!sc.noCull){
  E.depthImage = (w) => { depthCalls++; if (sc.depthNull) return null; const im = image(); return {w:im.w, h:im.h, z:im.z}; };
  E.idImage = (all, w) => { const im = image(); return {w:im.w, h:im.h, ids:im.ids}; };
  E.idOf = (id) => IDS[id] || 0;
}
const C = NMSKParts(E);
C.load();
setTimeout(() => {
  const out = {};
  const S = () => C.state();
  const vis = () => S().markers.filter(m => m.vis).map(m => m.j);
  const step = () => { C.update(); C.cullNow(); C.update(); };
  out.init = {mode:S().mode, band:S().band, hid:S().hid, canCull:S().canCull};
  for (const k of (sc.steps || [])){
    if (k.mode) C.setMode(k.mode);
    if (k.band != null) C.setBand(k.band);
    if (k.select !== undefined) C.select(k.select);
    if (k.hover !== undefined) C.hover(k.hover);
    if (k.marks) marks = k.marks;
    if (k.cut !== undefined) cutState = k.cut;
    if (k.hide) visible[k.hide] = false;
    if (k.hid !== undefined){ C.settings(); }
    step();
    out[k.tag] = {vis:vis(), why:S().markers.map(m => m.why), cull:S().markers.map(m => m.cull), behind:S().markers.map(m => m.behind), mode:S().mode, band:S().band, dots:dots.length};
  }
  out.store = store['nmsk.parts.v1'] || null;
  out.depthCalls = depthCalls;
  out.cullState = S().cull;
  console.log(JSON.stringify(out));
}, 50);
"""


def sidecar():
    parts = [{"id": f"p{i}", "n": f"Part {i}", "ty": "insertion_point", "r": [], "u": 0, "set": None} for i in range(6)]
    refs = {}
    pl = [  # (part, side, xyz, carriers)
        (0, "r", [-200, 100, 0], ["m_front"]),         # front muscle, depth 1000
        (1, "r", [0, 100, -300], ["m_back"]),          # deep: view depth 1300
        (2, "l", [200, -100, -700], ["m_far"]),        # far: view depth 1700
        (3, "l", [-100, -150, -50], ["m_front"]),      # next to the wall's edge, behind the wall surface
        (4, "m", [100, 0, 600], ["m_front"]),          # nearest: view depth 400, nearer than the test wall at 500
        (5, "r", [300, 150, -20], ["m_back"]),
    ]
    placed = [{"p": p, "s": s, "xyz": xyz, "c": "rule_based", "e": 10, "rule": "r", "mt": "r", "car": car, "eb": "x"} for p, s, xyz, car in pl]
    mesh_parts = {"m_front": {"s": "m", "p": [0, 3, 4]}, "m_back": {"s": "m", "p": [1, 5]}, "m_far": {"s": "m", "p": [2]}}
    return {"schema": "nmsk.parts_sidecar.v1", "parts": parts, "refs": refs, "sets": {}, "mesh_parts": mesh_parts, "placed": placed, "text_only": {}, "partial": {}}


def run(scn):
    if not NODE:
        pytest.skip("node not available")
    import tempfile
    scn = dict(scn); scn["data"] = sidecar()
    with tempfile.TemporaryDirectory() as td:
        hp = Path(td) / "h.js"
        hp.write_text(HARNESS)
        r = subprocess.run([NODE, str(hp), str(FRAG / "parts_ui.js"), json.dumps(scn)], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr[-1500:]
    return json.loads(r.stdout.strip().splitlines()[-1])


def full(z):
    return {"x0": 0, "x1": 100, "y0": 0, "y1": 80, "z": z}


def test_q256_marker_layer_is_off_by_default_even_when_selected():
    # the owner's ask: these source-reliability dots must not appear in the normal display until the user opts in
    wall = [full(500)]
    o = run({"surfaces": wall, "steps": [{"tag": "sel", "select": "m_back"}]})
    assert o["init"]["mode"] == "off"
    assert o["sel"]["mode"] == "off" and o["sel"]["vis"] == []                        # selecting a structure alone does not reveal its dots
    o2 = run({"surfaces": wall, "steps": [{"tag": "on", "select": "m_back", "mode": "sel"}]})
    assert o2["on"]["vis"] == [1, 5]                                                   # turning the panel on (opt-in) is what shows them


def test_defaults_without_a_surface_everything_in_the_band_is_shown():
    # Q256: the marker layer itself defaults to Off (opt-in, not seen in the normal display); "near" is exercised explicitly here
    o = run({"surfaces": [], "steps": [{"tag": "a", "mode": "near"}]})
    assert o["init"] == {"mode": "off", "band": 55, "hid": True, "canCull": True}
    assert o["a"]["vis"] == [0, 1, 2, 3, 4, 5] and all(c == 0 for c in o["a"]["cull"])      # no surface in the image: nothing hides anything, no depth range -> no band


def test_occlusion_by_a_nearer_surface_and_the_own_structure_exception():
    wall = [full(500)]                                          # a surface at view depth 500 over the whole image: everything behind it is hidden
    o = run({"surfaces": wall, "steps": [{"tag": "a", "band": 100, "mode": "near"}]})
    assert o["a"]["vis"] == [4]                                 # only the marker nearer than the wall (view depth 400)
    assert [c & 1 for c in o["a"]["cull"]] == [1, 1, 1, 1, 0, 1]
    # the front muscle's own surface at the marker's pixel (carrier id 1 at depth 1000 - 30): the marker lies under its own muscle's surface -> shown, though not within 6 mm
    own = [full(500)]
    own.append({"x0": 29, "x1": 33, "y0": 31, "y1": 35, "z": 970, "id": "m_front"})       # around marker 0's pixel (30, 32)
    o = run({"surfaces": own, "steps": [{"tag": "a", "band": 100, "mode": "near"}]})
    assert 0 in o["a"]["vis"] and 1 not in o["a"]["vis"]


def test_depth_band_front_share_of_the_visible_depth():
    surf = [{"x0": 0, "x1": 5, "y0": 0, "y1": 80, "z": 900}, {"x0": 95, "x1": 100, "y0": 0, "y1": 80, "z": 1800}]       # visible depth range 900 .. 1800 (edge strips; the marker pixels stay empty)
    st = [{"tag": "b55", "mode": "near"}, {"tag": "b100", "band": 100}, {"tag": "b20", "band": 20}, {"tag": "b55again", "band": 55}]
    o = run({"surfaces": surf, "steps": st})
    # band 55 % -> far limit 900 + 0.55 * 900 = 1395: the markers at view depth 1000 / 1300 pass, 1700 does not
    assert 2 not in o["b55"]["vis"] and {0, 1}.issubset(o["b55"]["vis"]) and o["b55"]["cull"][2] & 2
    assert 2 in o["b100"]["vis"] and all(c == 0 for c in o["b100"]["cull"])                  # the slider's top = all depths
    assert set(o["b20"]["vis"]) < set(o["b55"]["vis"]) or o["b20"]["vis"] == [4]           # 900 + 180 = 1080: only the nearer markers
    assert o["b55again"]["vis"] == o["b55"]["vis"]
    assert o["b20"]["band"] == 20 and json.loads(o["store"])["band"] == 55                  # persisted (last value)


def test_selected_marked_hovered_are_exempt_and_drawn_see_through():
    wall = [full(500)]
    o = run({"surfaces": wall, "steps": [{"tag": "none", "mode": "near"}, {"tag": "sel", "select": "m_back"}, {"tag": "off", "select": "m_back", "mode": "near"}]})
    assert o["none"]["vis"] == [4]
    assert o["sel"]["vis"] == [1, 4, 5] or o["sel"]["vis"] == [1, 5, 4] or sorted(o["sel"]["vis"]) == [1, 4, 5]
    assert o["sel"]["behind"][1] is True and o["sel"]["behind"][5] is True and not o["sel"]["behind"][4]
    # hover and marks do the same
    o = run({"surfaces": wall, "steps": [{"tag": "hov", "hover": "m_far", "mode": "near"}, {"tag": "unhov", "hover": None}, {"tag": "mk", "marks": ["m_front"]}]})
    assert 2 in o["hov"]["vis"] and o["hov"]["behind"][2] is True
    assert 2 not in o["unhov"]["vis"]
    assert {0, 3} <= set(o["mk"]["vis"])


def test_hidden_of_selected_switch_off_culls_them_like_the_rest():
    wall = [full(500)]
    o = run({"surfaces": wall, "preset": {"mode": "near", "band": 55, "hid": False}, "steps": [{"tag": "sel", "select": "m_back"}]})
    assert o["init"]["hid"] is False
    assert 1 not in o["sel"]["vis"] and o["sel"]["why"][1] == "occ"


def test_modes():
    wall = [full(500)]
    steps = [{"tag": "off", "mode": "off", "select": "m_back"}, {"tag": "sel", "mode": "sel"}, {"tag": "all", "mode": "all"}, {"tag": "near", "mode": "near"}]
    o = run({"surfaces": wall, "steps": steps})
    assert o["off"]["vis"] == []
    assert sorted(o["sel"]["vis"]) == [1, 5]                                        # selected only: the two markers of the selected structure (hidden behind the wall -> see-through)
    assert o["sel"]["behind"][1] is True
    assert sorted(o["all"]["vis"]) == [0, 1, 2, 3, 4, 5]                            # everything; the occluded ones are flagged
    assert o["all"]["behind"][0] is True and o["all"]["behind"][4] is False
    assert 4 in o["near"]["vis"] and 0 not in o["near"]["vis"]


def test_cut_mode_still_hides_the_removed_side_even_for_selected():
    cut = {"kn": [1, 0, 0], "c": 0, "th": 0}                                         # kept half-space x >= 0
    steps = [{"tag": "c", "select": "m_front", "cut": cut, "mode": "near"}]
    o = run({"surfaces": [], "steps": steps})
    assert o["c"]["why"][0] == "cut" and o["c"]["why"][3] == "cut" and 4 in o["c"]["vis"] and 0 not in o["c"]["vis"]


def test_hidden_structure_and_layer_off_still_hide():
    o = run({"surfaces": [], "steps": [{"tag": "h", "hide": "m_front", "mode": "near"}]})
    assert o["h"]["why"][0] == "hidden" and 0 not in o["h"]["vis"]


def test_throttled_capture_and_dirty():
    o = run({"surfaces": [], "steps": [{"tag": "a", "mode": "near"}, {"tag": "b"}, {"tag": "c"}]})
    assert o["depthCalls"] == 3                                                       # one depth pass per forced capture (cullNow); the throttle applies to overlay()
    assert o["cullState"]["ms"] >= 0 and o["cullState"]["img"] == "100x80"


def test_no_depth_pass_when_nothing_can_be_shown():
    cut = {"kn": [1, 0, 0], "c": -5000, "th": 0}                                      # every marker is on the removed side
    o = run({"surfaces": [], "steps": [{"tag": "a", "cut": cut, "mode": "near"}, {"tag": "b"}]})
    assert o["a"]["vis"] == [] and o["depthCalls"] == 0


def test_a_gpu_without_a_depth_pass_falls_back_to_selection_mode():
    o = run({"depthNull": True, "surfaces": [], "steps": [{"tag": "a", "mode": "near"}, {"tag": "b"}, {"tag": "c", "select": "m_back"}]})
    assert o["c"]["mode"] == "sel" and sorted(o["c"]["vis"]) == [1, 5]


def test_page_without_the_culling_adaptor_behaves_as_before():
    o = run({"noCull": True, "surfaces": [], "steps": [{"tag": "n", "select": "m_back", "mode": "sel"}, {"tag": "x", "mode": "near"}, {"tag": "all", "mode": "all"}]})
    assert o["init"]["mode"] == "off" and o["init"]["canCull"] is False               # Q256: off by default regardless of canCull
    assert sorted(o["n"]["vis"]) == [1, 5] and o["x"]["mode"] == "sel"                 # 'near' is refused, the selection mode stays
    assert o["depthCalls"] == 0 and len(o["all"]["vis"]) == 6


def test_blocked_storage_does_not_break_it():
    o = run({"noStorage": True, "surfaces": [], "steps": [{"tag": "a", "band": 30}]})
    assert o["a"]["band"] == 30 and o["store"] is None


# ---------------------------------------------------------------- templates / build chain
@pytest.mark.parametrize("tpl", [OWN, ZAN])
def test_templates_carry_the_fragment_and_the_adaptor_members(tpl):
    t = tpl.read_text(encoding="utf-8")
    assert sync.render(t) == t
    seg = t[t.index("partsCtl = NMSKParts({"):]
    seg = seg[:seg.index("window.__partsState")]
    for name in ("idImage", "depthImage", "idOf", "marked"):
        assert re.search(r"\b" + name + r"\s*:", seg), name
    assert "partsCtl.hover(" in t and "partsCtl.dirty()" in t and "window.__partsCtl" in t
    assert 'id="pm-panel"' in t


@pytest.mark.parametrize("tpl", [OWN, ZAN])
def test_q256_markers_default_off_in_the_committed_templates(tpl):
    t = tpl.read_text(encoding="utf-8")
    assert 'var P = {mode:"off", band:55, hid:true};' in t
    assert 'var P = {mode:canCull ? "near" : "sel"' not in t   # the pre-Q256 on-by-default initial state must be gone


def test_engine_depth_passes():
    o, z = OWN.read_text(encoding="utf-8"), ZAN.read_text(encoding="utf-8")
    # own: the labels' flat-colour pass with a packed-RGBA depth material (same camera, cut planes, isolation as the screen); linear view depth from the packed value
    assert "MeshDepthMaterial({depthPacking:THREE.RGBADepthPacking" in o and "labGeo.dmat.clippingPlanes = cut.on ? cutPlanes : null" in o
    assert "idImage:function(all, w, depth)" in o and "if (depth){ m.material = labGeo.dmat; return; }" in o
    # Z: the existing depth pass (renderIds(.., true, ..)) in a corner of the picking buffer, decoded like pickPoint
    assert "function zDepthImage(w)" in z and "renderIds(false, true, sc)" in z and "if (!lastMVP || !depthOK) return null" in z
    assert "if (depth) return zDepthImage(w);" in z and "renderIds(all, false, sc)" in z


def test_labels_engine_accessor_exists():
    assert "engine:function(){ return E; }" in (REPO / "viewer" / "labels" / "labels.js").read_text(encoding="utf-8")


def test_regen_script_and_check_files_exist():
    s = (REPO / "scripts" / "regen_q240.sh").read_text()
    assert "build/q240" in s and "make_calibre.py --inject" in s and "make_abbrevs.py --inject" in s and "regen_q232.sh" in s
    assert (REPO / "scripts" / "anatomy" / "q240" / "browser_check.py").exists()


@pytest.mark.parametrize("key,d,html", [("own_f", "viewer_f_hr", "atlas_viewer_female.html"), ("zan_f", "viewer_zan_female", "atlas_viewer_zan_female.html"),
                                        ("base_m", "viewer_zan_atlas", "atlas_viewer_zan_atlas.html")])
def test_regenerated_page_carries_the_new_blocks(key, d, html):
    p = REPO / "build" / "q240" / d / html
    if not p.exists():
        pytest.skip("build/q240 not present")
    s = p.read_text(encoding="utf-8")
    assert sync.render(s) == s
    for needle in ('id="nmsk-calibre"', 'id="nmsk-abbrev"', 'id="pm-panel"', "depthImage", "MeshDepthMaterial" if key.startswith("own") else "zDepthImage"):
        assert needle in s, needle
    assert (p.parent / "index.html").read_text(encoding="utf-8") == s
    assert (p.parent / "parts_data.json").exists() and (p.parent / "symmetry_q237.json").exists()
    v = REPO / "build" / "q240" / "_verify" / f"{d}.json"
    if v.exists():
        j = json.loads(v.read_text())
        assert j.get("geo_identical") is True and j.get("literals_identical") is True
