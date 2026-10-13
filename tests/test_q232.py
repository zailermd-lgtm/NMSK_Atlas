"""Q232: selection INVERT + per-group display states (show / fade / hide / ghost / x-ray / highlight), presets, helpers and keys, in both viewer templates.

Fragment sync (verbatim in both templates), the controller under node with a mock DOM (invert with layer / hidden / side / source filtering, toggling back,
edits while inverted, group states and the fade opacity, presets, Q227 mode/ghost compatibility, saved sets incl. the inverse flag, export / import / link,
reset, helper buttons, keys), and the engine wiring of both templates (fade alpha, hide = no draw / no pick / no cap, highlight colour, add-on contract)."""
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
sys.path.insert(0, str(REPO / "scripts"))
import sync_q227 as sync  # noqa: E402

NODE = shutil.which("node")

HARNESS = r"""
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
global.document = {getElementById(i){ return els[i] || (els[i] = el(i)); }, createElement(){ return el(null); }, querySelectorAll(){ return []; }, body:el('body'), documentElement:el('html')};
const store = {};
global.localStorage = {getItem(k){ return k in store ? store[k] : null; }, setItem(k,v){ store[k] = String(v); }, removeItem(k){ delete store[k]; }};
global.location = {hash:'', href:'https://example.test/page.html'};
global.navigator = {clipboard:{writeText(t){ global.__copied = t; return Promise.resolve(); }}};
let keyHandler = null;
global.window = {addEventListener(t, f){ if (t === 'keydown') keyHandler = f; }};
eval(src + '; global.NMSKSelect = NMSKSelect;');
// 8 structures; layer "bone" off, femur_l is on the hidden side, ghost_x is default-hidden: not eligible
const ITEMS = [['biceps_r','Biceps brachii (R)','muscle'],['biceps_l','Biceps brachii (L)','muscle'],['femur_r','Femur (R)','bone'],['femur_l','Femur (L)','bone'],
  ['sartorius_r','Sartorius (R)','muscle'],['skin','Skin','skin'],['liver','Liver','organ'],['ghost_x','Extra','muscle']].map(a => ({id:a[0], name:a[1], cat:a[2]}));
let elig = ['biceps_r','biceps_l','sartorius_r','liver','femur_r'];       // shown now: layers + hidden + side + facet already applied by the engine
let refreshes = 0, revealed = [], selectedId = null, engineReset = 0;
const toolbar = el('tb'), canvas = el('canvas');
const E = {modelId:() => 'own:vhm', items:() => ITEMS, refresh(){ refreshes++; }, selected:() => selectedId, select(id){ selectedId = id; }, reveal(ids){ revealed = revealed.concat(ids); },
  listIds:() => ['femur_r','femur_l'], pickId:() => null, clearHover(){}, resetEngine(){ engineReset++; }, canvas, toolbar, toolClass:'tool', isPhone:() => false,
  eligible:() => elig.slice(), categories:() => [{key:'muscle', label:'Muscles', count:4},{key:'bone', label:'Bones', count:2}],
  idsOfCategory:(k) => ITEMS.filter(i => i.cat === k).map(i => i.id)};
const out = {};
let C = NMSKSelect(E);
const S = () => C.state();
const ids = (xs) => xs.slice().sort();
const key = (k, o) => { const ev = Object.assign({key:k, target:{tagName:'BODY'}, prevented:false, stopped:false, preventDefault(){ this.prevented = true; }, stopImmediatePropagation(){ this.stopped = true; }}, o || {}); C.onKey(ev); return ev; };
if (scenario === 'invert'){
  C.toggle('biceps_r'); C.toggle('femur_l');                         // femur_l is marked but not eligible
  out.before = ids(S().marks);
  out.ok = C.invert();
  out.tint_inv = C.tinted('biceps_l'); out.after = ids(S().marks); out.inverted = S().inverted; out.left = ids(S().left);
  out.rule_after = ['biceps_r','femur_l','biceps_l','liver','skin'].map(i => C.look(i));
  out.count = els['sel-count'].textContent; out.chips = els['sel-chips'].innerHTML;
  out.refreshed = refreshes > 0;
  // edits while inverted: unmark sartorius (= leave it out), mark biceps_r back
  C.mark('sartorius_r', false); C.mark('biceps_r', true);
  out.edited = ids(S().marks); out.edited_left = ids(S().left);
  // back
  C.invert(); out.back = ids(S().marks); out.back_inverted = S().inverted;
  // nothing marked: invert marks all eligible; everything eligible marked: refuse
  C.clear(); out.cleared_inverted = S().inverted;
  C.invert(); out.from_empty = ids(S().marks);
  const r2 = C.invert(); out.back_to_empty = S().marks.length;
  C.toggle('biceps_r'); C.toggle('biceps_l'); C.toggle('sartorius_r'); C.toggle('liver'); C.toggle('femur_r');
  out.refuse = C.invert(); out.refuse_marks = S().marks.length;
  // eligibility is read at invert time
  C.clear(); C.toggle('liver'); elig = ['biceps_r','liver']; C.invert(); out.dyn = ids(S().marks);
}
if (scenario === 'states'){
  C.toggle('biceps_r'); C.toggle('femur_r');
  out.init = [S().sel, S().oth, S().fade, S().hl];
  out.look0 = ['biceps_r','skin'].map(i => C.look(i));
  C.setGroup('oth', 'fade'); out.fade_look = ['biceps_r','skin'].map(i => C.look(i)); out.fade_alpha = C.fadeAlpha(); out.translucent = C.translucent();
  C.setFade(0.4); out.fade40 = C.fadeAlpha(); C.setFade(0); out.fade0_look = C.look('skin'); out.fade0_rule = C.rule('skin');
  C.setFade(1.7); out.fade_clamped = C.fadeAlpha(); C.setFade(0.15);
  C.setGroup('oth', 'fade'); out.toggle_off = S().oth;                          // clicking the active state again goes back to show
  C.setGroup('sel', 'hl'); out.hl_look = ['biceps_r','skin'].map(i => C.look(i)); out.tinted_hl = C.tinted('biceps_r'); out.hl_hex = C.hlHex();
  C.setHl('#00ff80'); out.hl_hex2 = C.hlHex(); C.setHl('red'); out.hl_hex3 = C.hlHex();
  C.setGroup('oth', 'hl'); out.oth_hl = S().oth;                                // highlight is for the selected group only
  C.setGroup('sel', 'xray'); C.setGroup('oth', 'ghost'); out.xg = ['biceps_r','skin'].map(i => C.look(i)); out.ghosting = C.ghosting(); out.rule_xg = ['biceps_r','skin'].map(i => C.rule(i));
  C.setGroup('sel', 'show', true); C.setGroup('oth', 'show', true); out.tinted_show = [C.tinted('biceps_r'), C.tinted('skin')];
  C.setTint(false); out.tinted_off = C.tinted('biceps_r'); C.setTint(true);
  // presets
  out.presets = {};
  ['isolate','fadeoth','fadesel','hidesel','hlsel'].forEach(k => { C.preset(k); out.presets[k] = [S().sel, S().oth, S().mode]; });
  C.preset('hlsel'); out.preset_toggle = [S().sel, S().oth];                     // pressing the active preset again restores everything
  C.preset('isolate'); out.reveal_on_isolate = revealed.slice();
  // keys
  C.reset();
  C.toggle('biceps_r');
  out.key_i = (() => { const ev = key('i'); return [ev.prevented, ev.stopped, S().inverted]; })(); key('i');
  key('f'); out.key_f = [S().sel, S().oth]; key('f'); out.key_f2 = [S().sel, S().oth];
  key('F', {shiftKey:true}); out.key_sf = [S().sel, S().oth]; key('F', {shiftKey:true});
  key('h'); out.key_h = [S().sel, S().oth]; key('h'); key('H', {shiftKey:true}); out.key_sh = [S().sel, S().oth]; key('H', {shiftKey:true});
  out.key_typing = (() => { const ev = key('i', {target:{tagName:'INPUT'}}); return [ev.prevented, S().inverted]; })();
  out.key_ctrl = (() => { const ev = key('f', {ctrlKey:true}); return [ev.prevented, S().oth]; })();
  C.clear(); out.key_nomarks = (() => { const ev = key('h'); return [ev.prevented, ev.stopped]; })();
  // helpers
  C.markVisible(); out.mark_visible = ids(S().marks);
  C.clear(); C.markCategory('muscle', true); out.mark_cat = ids(S().marks); C.markCategory('muscle', false); out.unmark_cat = S().marks.length;
}
if (scenario === 'legacy'){
  C.toggle('biceps_r'); C.toggle('femur_r');
  C.setMode('only'); out.only = [S().sel, S().oth, S().mode, S().ghost]; C.setGhost(); out.only_ghost = [S().sel, S().oth, S().mode, S().ghost];
  C.setMode('hide'); out.hide = [S().sel, S().oth, S().mode, S().ghost]; C.setGhost(false); out.hide_plain = [S().sel, S().oth, S().mode, S().ghost];
  C.setMode('hide'); out.all = [S().sel, S().oth, S().mode, S().ghost];
  C.setGroup('oth', 'fade'); out.fade_mode = S().mode;                             // new states are not one of the old modes
  C.mark('biceps_r', false); C.mark('femur_r', false); out.last_unmark = [S().sel, S().oth, S().fade];
}
if (scenario === 'saved'){
  C.toggle('biceps_r'); C.toggle('femur_l'); C.invert(); C.setGroup('oth', 'fade'); C.setFade(0.3); C.setGroup('sel', 'hl'); C.setHl('#112233');
  out.saved = C.save('Inv'); out.stored = JSON.parse(store['nmsk.sel.v1:own:vhm']);
  out.option = els['sel-sets'].innerHTML;
  C.reset(); out.after_reset = [S().marks.length, S().inverted, S().sel, S().oth, S().fade];
  elig = ['biceps_r','biceps_l','sartorius_r','liver','femur_r','skin'];      // the facet changed: skin is shown now
  C.load('Inv'); out.loaded = ids(S().marks); out.loaded_inv = S().inverted; out.loaded_left = ids(S().left); out.loaded_states = [S().sel, S().oth, S().fade, S().hl];
  C.invert(); out.plain_marks = ids(S().marks);                                  // back to the explicit set
  C.invert();
  const txt = C.exportText(); const o = JSON.parse(txt); out.export_set = o.sets.Inv; out.export_current = o.current;
  C.del('Inv'); out.deleted = Object.keys(JSON.parse(store['nmsk.sel.v1:own:vhm']).sets).length;
  C.reset(); out.import_ok = C.importText(txt); out.imported_sets = S().sets;
  C.load('Inv'); out.reimported = [ids(S().marks).length, S().inverted, S().oth, S().fade];
  // a Q227 set (mode + ghost, no states) still loads
  const legacy = {nmsk_selection:1, model:'own:vhm', sets:{Old:{ids:['biceps_r','femur_r'], mode:'only', ghost:true}, Old2:{ids:['skin'], mode:'hide', ghost:false}, Bad:{ids:['zzz']}}};
  out.legacy_import = C.importText(JSON.stringify(legacy));
  C.load('Old'); out.old = [S().sel, S().oth, S().mode, S().ghost, S().inverted]; C.load('Old2'); out.old2 = [S().sel, S().oth, S().mode];
  // a hostile import: bad states / fade / colour are ignored
  C.importText(JSON.stringify({sets:{X:{ids:['biceps_r'], ss:'__proto__', os:'hl', fade:7, hl:'javascript:1', inv:1}}}));
  C.load('X'); out.hostile = [S().sel, S().oth, S().fade, S().hl, S().inverted];
}
if (scenario === 'link'){
  C.toggle('biceps_r'); C.toggle('femur_l'); C.invert(); C.setGroup('oth', 'xray'); C.setFade(0.55); C.setGroup('sel', 'hl');
  out.link = C.link();
  const link = out.link;
  Object.keys(els).forEach(k => delete els[k]); Object.keys(store).forEach(k => delete store[k]);
  global.location.hash = link; C = NMSKSelect(E);
  out.from_link = ids(S().marks); out.from_link_state = [S().inverted, S().sel, S().oth, S().fade, S().hl, ids(S().left)];
  // an old four-field link
  Object.keys(els).forEach(k => delete els[k]); Object.keys(store).forEach(k => delete store[k]);
  global.location.hash = '#nmsksel=own%3Avhm~only~1~femur_r,skin'; C = NMSKSelect(E);
  out.old_link = [ids(S().marks), S().sel, S().oth, S().mode, S().inverted];
  // paste of a link into the import box
  C.reset(); out.paste = C.importText(link); out.pasted = [ids(S().marks).length, S().inverted];
}
if (scenario === 'reset'){
  C.toggle('biceps_r'); C.invert(); C.setGroup('oth', 'fade'); C.setFade(0.5); C.reset();
  out.reset = [S().marks.length, S().inverted, S().sel, S().oth, S().ghost, S().markMode, S().fade, engineReset];
  out.toolbar = toolbar.children.map(c => [c.id, c.hidden]);
}
console.log(JSON.stringify(out));
"""


def run(scenario):
    if not NODE:
        pytest.skip("node not available")
    with tempfile.TemporaryDirectory() as td:
        h = Path(td) / "h.js"
        h.write_text(HARNESS)
        r = subprocess.run([NODE, str(h), str(SEL / "selection.js"), scenario], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


# ---------------------------------------------------------------- shared fragment
@pytest.mark.parametrize("tpl", [OWN, ZAN], ids=["own", "zan"])
def test_fragment_verbatim_in_both_templates(tpl):
    t = tpl.read_text(encoding="utf-8")
    for name, (path, b, e) in sync.BLOCKS.items():
        frag = path.read_text(encoding="utf-8").rstrip("\n")
        assert t[t.index(b) + len(b):t.index(e)] == "\n" + frag + "\n", f"{tpl.name}: {name} differs (run scripts/sync_q227.py)"


def test_panel_has_the_controls():
    h = (SEL / "selection.html").read_text(encoding="utf-8")
    for i in ("sel-invert", "sel-markvis", "sel-cat", "sel-markcat", "sel-unmarkcat", "sel-fade", "sel-hl", "sel-tint", "sel-p-isolate", "sel-p-fadeoth", "sel-p-fadesel",
              "sel-p-hidesel", "sel-p-hlsel", "sel-only", "sel-hide", "sel-ghost", "sel-reset"):
        assert f'id="{i}"' in h, i
    for g, states in (("sel", ("show", "fade", "hide", "hl", "ghost", "xray")), ("oth", ("show", "fade", "hide", "ghost", "xray"))):
        for s in states:
            assert f'data-g="{g}" data-s="{s}"' in h, (g, s)
    assert 'data-g="oth" data-s="hl"' not in h


# ---------------------------------------------------------------- the controller
def test_invert_respects_eligibility_and_toggles_back():
    o = run("invert")
    assert o["before"] == ["biceps_r", "femur_l"]
    assert o["ok"] is True and o["inverted"] is True
    # everything eligible except the marked ones; femur_l (hidden side) and skin / ghost_x (layer off, default-hidden) are not marked
    assert o["after"] == ["biceps_l", "femur_r", "liver", "sartorius_r"]
    assert o["left"] == ["biceps_r", "femur_l"] and o["tint_inv"] is False        # no amber tint while inverted (the marked set is the whole rest)
    assert o["count"] == "4" and "Inverted: all other 4" in o["chips"] and "not Biceps brachii (R)" in o["chips"] and "not Femur (L)" in o["chips"]
    assert o["refreshed"] is True
    # edits while inverted act on the complement; inverting back gives the swapped edit
    assert o["edited"] == ["biceps_l", "biceps_r", "femur_r", "liver"] and o["edited_left"] == ["femur_l", "sartorius_r"]
    assert o["back"] == ["femur_l", "sartorius_r"] and o["back_inverted"] is False
    assert o["cleared_inverted"] is False
    assert o["from_empty"] == ["biceps_l", "biceps_r", "femur_r", "liver", "sartorius_r"] and o["back_to_empty"] == 0
    assert o["refuse"] is False and o["refuse_marks"] == 5            # everything shown is marked: nothing to invert to
    assert o["dyn"] == ["biceps_r"]                                   # eligibility is read when Invert is pressed


def test_group_states_fade_alpha_presets_helpers_and_keys():
    o = run("states")
    assert o["init"] == ["show", "show", 0.15, "#ffb000"]
    assert o["look0"] == ["", ""]
    assert o["fade_look"] == ["", "fade"] and o["fade_alpha"] == 0.15 and o["translucent"] is True
    assert o["fade40"] == 0.4
    assert o["fade0_look"] == "hide" and o["fade0_rule"] == "hide"      # 0 % = not drawn (no pick, no cap)
    assert o["fade_clamped"] == 1
    assert o["toggle_off"] == "show"
    assert o["hl_look"] == ["hl", ""]
    assert o["tinted_hl"] is False and o["hl_hex"] == 0xFFB000 and o["hl_hex2"] == 0x00FF80 and o["hl_hex3"] == 0x00FF80
    assert o["oth_hl"] == "show"
    assert o["xg"] == ["xray", "ghost"] and o["ghosting"] is True and o["rule_xg"] == ["", "ghost"]
    assert o["tinted_show"] == [True, False] and o["tinted_off"] is False
    assert o["presets"] == {"isolate": ["show", "hide", "only"], "fadeoth": ["show", "fade", "all"], "fadesel": ["fade", "show", "all"], "hidesel": ["hide", "show", "hide"],
                            "hlsel": ["hl", "show", "all"]}
    assert o["preset_toggle"] == ["show", "show"]
    assert o["reveal_on_isolate"][-2:] == ["biceps_r", "femur_r"]
    assert o["key_i"] == [True, True, True]
    assert o["key_f"] == ["show", "fade"] and o["key_f2"] == ["show", "show"]
    assert o["key_sf"] == ["fade", "show"]
    assert o["key_h"] == ["hide", "show"] and o["key_sh"] == ["show", "hide"]
    assert o["key_typing"] == [False, False] and o["key_ctrl"] == [False, "show"]
    assert o["key_nomarks"] == [False, False]                          # nothing marked: the page's own i / f / h keys are left alone
    assert o["mark_visible"] == ["biceps_l", "biceps_r", "femur_r", "liver", "sartorius_r"]
    assert o["mark_cat"] == ["biceps_l", "biceps_r", "ghost_x", "sartorius_r"] and o["unmark_cat"] == 0


def test_q227_modes_map_onto_the_new_model():
    o = run("legacy")
    assert o["only"] == ["show", "hide", "only", False]
    assert o["only_ghost"] == ["show", "ghost", "only", True]
    assert o["hide"] == ["ghost", "show", "hide", True]
    assert o["hide_plain"] == ["hide", "show", "hide", False]
    assert o["all"] == ["show", "show", "all", False]
    assert o["fade_mode"] == "all"
    assert o["last_unmark"] == ["show", "show", 0.15]                  # the last unmark resets the states (the fade value stays)


def test_saved_sets_with_inverse_flag_export_import_and_old_sets():
    o = run("saved")
    assert o["saved"] is True
    s = o["stored"]["sets"]["Inv"]
    assert s["inv"] is True and s["ids"] == ["biceps_r", "femur_l"] and s["ss"] == "hl" and s["os"] == "fade" and s["fade"] == 0.3 and s["hl"] == "#112233"
    assert "Inv (2, inverse)" in o["option"]
    assert o["after_reset"] == [0, False, "show", "show", 0.3]
    # re-evaluated against what is eligible NOW (skin became eligible)
    assert o["loaded"] == ["biceps_l", "femur_r", "liver", "sartorius_r", "skin"] and o["loaded_inv"] is True and o["loaded_left"] == ["biceps_r", "femur_l"]
    assert o["loaded_states"] == ["hl", "fade", 0.3, "#112233"]
    assert o["plain_marks"] == ["biceps_r", "femur_l"]            # Invert on the loaded inverse gives the explicit set back
    assert o["export_set"]["inv"] is True and o["export_current"]["inv"] is True and o["export_current"]["ids"] == ["biceps_r", "femur_l"]
    assert o["deleted"] == 0 and o["import_ok"] is True and "Inv" in o["imported_sets"]
    assert o["reimported"] == [5, True, "fade", 0.3]
    assert o["legacy_import"] is True
    assert o["old"] == ["show", "ghost", "only", True, False] and o["old2"] == ["hide", "show", "hide"]
    assert o["hostile"] == ["show", "show", 0.3, "#112233", True]       # bad state names / fade / colour are ignored, the previous values stay


def test_link_round_trip_old_links_and_paste():
    o = run("link")
    assert o["link"].startswith("#nmsksel=own%3Avhm~") and o["link"].count("~") == 4
    assert o["from_link"] == ["biceps_l", "femur_r", "liver", "sartorius_r"]
    assert o["from_link_state"] == [True, "hl", "xray", 0.55, "#ffb000", ["biceps_r", "femur_l"]]
    assert o["old_link"] == [["femur_r", "skin"], "show", "ghost", "only", False]
    assert o["paste"] is True and o["pasted"] == [4, True]


def test_reset_clears_inverse_and_states():
    o = run("reset")
    assert o["reset"][:6] == [0, False, "show", "show", False, False] and o["reset"][6] == 0.5 and o["reset"][7] == 1
    assert ["t-invert", True] in o["toolbar"]


# ---------------------------------------------------------------- the engines
@pytest.mark.parametrize("tpl", [OWN, ZAN], ids=["own", "zan"])
def test_engines_use_the_display_states(tpl):
    t = tpl.read_text(encoding="utf-8")
    for needle in ("selCtl.look(", "selCtl.tinted(", "selCtl.hlHex()", "selCtl.fadeAlpha()", "eligible:function", "categories:function", "idsOfCategory:function"):
        assert needle in t, (tpl.name, needle)
    assert 'selCtl.isMarked(' not in t.split("/* SELECTION js end */")[1]


def test_own_engine_fade_hide_highlight_and_cap():
    t = OWN.read_text(encoding="utf-8")
    a = t[t.index("function apply(){"):t.index('document.getElementById("t-iso")')]
    assert 'if (sr === "hide") vis = false;' in a and "m.visible = vis;" in a                       # hidden: not drawn, not picked (pickHit takes visible meshes), no cap item
    assert 'sr === "fade" && !isSel' in a and "selCtl.fadeAlpha()" in a
    assert 'sr === "xray"' in a and "sr === \"hl\"" in a and "selCtl.hlHex()" in a
    assert "m.material.opacity" in a and "capCtl.itemsChanged()" in a
    cap = t[t.index("capCtl = NMSKCap({"):t.index("upload:capUpload")]
    assert "if (!m.visible) return;" in cap and "alpha:m.material.opacity" in cap                   # a faded structure's cap uses its opacity; hidden ones have none
    assert "visible:function(i){ return !!meshes[i].visible; }" in t                                # add-on contract unchanged


def test_zan_engine_fade_hide_highlight_pick_cap_and_addon_contract():
    t = ZAN.read_text(encoding="utf-8")
    assert 'selCtl.rule(o.id) === "hide"' in t                                                      # hidden: vis() false -> no draw, no ID pass, no cap item
    assert "selAlpha(\"fade\"" in t and "selAlpha(\"xray\"" in t and "selAlpha(\"ghost\"" in t and "hlOnly" in t
    assert "function isThin(o)" in t and "!isThin(o)" in t and "selCtl.translucent()" in t
    i = t.index("capCtl = NMSKCap({")
    cap = t[i:t.index("upload:capUpload", i)]
    assert "selAlpha(lk" in cap and "if (!vis(o)) return;" in cap and "colOf(o)" in cap
    assert "visible:function(i){ var o=OBJ[i]; return vis(o)&&!faded.has(o); }" in t               # add-on contract unchanged
