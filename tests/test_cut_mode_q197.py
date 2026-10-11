"""Q197: one Cut mode in both viewer templates, and the template-only / re-inject rebuild paths that carry it to the six pages."""
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
FRAG = REPO / "viewer" / "cut_mode"
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "scripts" / "zanatomy"))
import sync_cut_mode_q197 as sync  # noqa: E402
import rebuild_html_from_built as rb  # noqa: E402

NODE = shutil.which("node")
IDS = ["t-cut", "cut-panel", "cut-svg", "cut-axis", "cut-place", "cut-hint", "cut-side-a", "cut-side-b", "cut-flip", "cut-pos",
       "cut-mm", "cut-steps", "cut-reset", "cut-exit", "cut-min",
       "cut-th", "cut-thsl", "cut-thick"]          # Q218: slice thickness (readout, slider, preset buttons)


@pytest.mark.parametrize("tpl", [OWN, ZAN], ids=["own", "zan"])
def test_templates_carry_the_shared_cut_block_verbatim(tpl):
    t = tpl.read_text(encoding="utf-8")
    for kind, (b, e) in sync.MARK.items():
        frag = (FRAG / f"cut_mode.{kind}").read_text(encoding="utf-8").rstrip("\n")
        assert t.count(b) == 1 and t.count(e) == 1, kind
        assert t[t.index(b) + len(b):t.index(e)] == "\n" + frag + "\n", f"{tpl.name}: {kind} block differs from viewer/cut_mode (run scripts/sync_cut_mode_q197.py)"


@pytest.mark.parametrize("tpl", [OWN, ZAN], ids=["own", "zan"])
def test_templates_have_the_controls_and_handlers(tpl):
    t = tpl.read_text(encoding="utf-8")
    for i in IDS:
        assert f'id="{i}"' in t, i
    for axis in ("x", "y", "z", "view"):
        assert f'data-axis="{axis}"' in t
    for step in ("-10", "-1", "1", "10"):
        assert f'data-step="{step}"' in t
    for th in ("2", "5", "10", "25", "0"):                                   # Q218: thickness presets, 0 = "all"
        assert f'data-th="{th}"' in t
    assert re.search(r'id="cut-thsl" type="range" min="1" max="100"', t)
    for needle in ("function NMSKCutMode(E)", "consumeClick", "setFromSpec", "ArrowRight", "PageUp", "wheel", "pickPoint",
                   "NMSKCutMode({", "cutCtl.consumeClick", "cutCtl.overlay()"):
        assert needle in t, needle
    # the placing click is tried before the add-on's click handler
    assert t.index("cutCtl.consumeClick(e)") < t.index("addonClick(e)", t.index("cutCtl.consumeClick(e)") - 200)


def test_old_split_cut_ui_is_gone():
    z, o = ZAN.read_text(encoding="utf-8"), OWN.read_text(encoding="utf-8")
    for old in ("clip-on", "clip-pos", "clip-flip", "clip-axis"):
        assert f'id="{old}"' not in z, old
    assert "clipFaceView" not in z and "cutViewNormal" not in o and "cutUpdate" not in o


def test_hook_contract_unchanged_for_the_addon():
    """The add-on reads api.cut() (kept half: n.p + c >= 0), calls setCut({normal, point}) and clips its halos with
    api.three.clippingPlanes(); the trajectory meshes stay unclipped on purpose."""
    o, z = OWN.read_text(encoding="utf-8"), ZAN.read_text(encoding="utf-8")
    assert "clippingPlanes:function(){ return cut.on ? cutPlanes : null; }" in o
    assert "cut:function(){ return cut.on ? [cutLocal.normal.x, cutLocal.normal.y, cutLocal.normal.z, cutLocal.constant] : null; }" in o
    assert "cut:function(){ if(!clip.on) return null; var P=clipPlane(); return [-P[0],-P[1],-P[2],-P[3]]; }" in z
    assert "ctx={gl:gl, mvp:mvp, eye:eye, W:W, H:H, clip:clip.on?clipPlane():null, clip2:clip.on?clipPlane2():null}" in z   # Q218: clip2 is additive
    flat = lambda t: re.sub(r"\s*(//|/\*|\*/)?\s+", " ", t)
    assert "needle trajectory is NOT clipped" in flat(o) and "needle trajectory is not clipped" in flat(z)
    # anchor markers are clipped with the anatomy
    assert "originMarker, insertionMarker" in o


def test_zan_picking_pass_and_depth_pass_share_the_plane():
    z = ZAN.read_text(encoding="utf-8")
    assert z.count("dot(vP,uClip.xyz)+uClip.w>0.0") == 3          # screen shader, ID pick shader, depth pick shader
    assert "function pickPoint(mx, my)" in z and "renderIds(lastPickAll, true)" in z


def test_slice_thickness_in_both_engines():
    """Q218: the kept slab is 0 <= kn.p + c <= th; own = a second three.js clipping plane (also in the picking filter), Z = a
    second uniform in the screen, ID and depth shaders plus the AABB cull; both hand the add-on the same kept-half cut() and an
    optional cutSlab() (+ ctx.clip2 on Z) so halos / picks that honour them stay inside the slab."""
    o, z = OWN.read_text(encoding="utf-8"), ZAN.read_text(encoding="utf-8")
    assert "cutPlanes = [cutWorld, cutWorld2]" in o
    assert "cutWorld.distanceToPoint(h.point) >= 0 && cutWorld2.distanceToPoint(h.point) >= 0" in o
    assert "cutWorld2.constant = (th > 0 ? th : 1e7) - c - cutWorld2.normal.dot(root.position)" in o
    assert "apply:function(kn, c, on, th)" in o and "apply:function(kn, c, on, th)" in z
    assert "cutSlab:function(){ return cut.on ? cutCtl.state().th : 0; }" in o
    assert "cutSlab:function(){ return clip.on ? cutCtl.state().th : 0; }" in z
    assert z.count("uniform vec4 uClip2;") == 3
    assert z.count("dot(vP,uClip2.xyz)+uClip2.w>0.0") == 3
    for lst in ('"uClip","uClip2","uClipOn"',):
        assert z.count(lst) == 3, lst                                          # U, PUid, DU uniform tables
    assert z.count("uniform4f(U.uClip2") == 1 and z.count("uniform4f(PU.uClip2") == 1       # screen pass + ID/depth pass (PU = ID or depth table)
    assert "clip.P2=th>0 ? [kn[0], kn[1], kn[2], c-th] : [0,0,0,-1]" in z
    assert "m <= 0 && m2 <= 0" in z                                            # AABB cull tests both planes
    n = (REPO / "clinical" / "needle_tool.js").read_text(encoding="utf-8")
    assert "uniform vec4 uClip2" in n and "ctx.clip2" in n and "this.api.cutSlab" in n   # add-on side, all optional


def _run_controller(script: str):
    if not NODE:
        pytest.skip("node not available")
    js = (FRAG / "cut_mode.js").read_text(encoding="utf-8")
    harness = r"""
const els = {};
function mk(id){ const e = {id, hidden:false, dataset:{}, style:{}, textContent:'', value:'0', min:'0', max:'0', _l:{}, _a:{}, children:[],
  classList:{_s:new Set(), toggle(c,v){ v===undefined?(this._s.has(c)?this._s.delete(c):this._s.add(c)):(v?this._s.add(c):this._s.delete(c)); }, contains(c){ return this._s.has(c); }},
  setAttribute(k,v){ this._a[k]=String(v); }, getAttribute(k){ return this._a[k]; }, addEventListener(t,f){ (this._l[t]=this._l[t]||[]).push(f); },
  querySelectorAll(sel){ return sel==='#cut-axis button' ? axes : sel==='#cut-steps button' ? steps : sel==='#cut-thick button' ? ths : []; }, innerHTML:'' }; els[id]=e; return e; }
const ths = ['2','5','10','25','0'].map(a => { const e = mk('th_'+a); e.dataset.th = a; return e; });
const axes = ['x','y','z','view'].map(a => { const e = mk('ax_'+a); e.dataset.axis = a; return e; });
const steps = ['-10','-1','1','10'].map(a => { const e = mk('st_'+a); e.dataset.step = a; return e; });
['cut-th','cut-thsl'].forEach(id => { mk(id); });
els['cut-thsl'].max = '100'; els['cut-thsl'].min = '1';
['cut-panel','cut-svg','t-cut','cut-pos','cut-side-a','cut-side-b','cut-flip','cut-mm','cut-state','cut-place','cut-hint','cut-reset','cut-exit','cut-min'].forEach(mk);
const winL = {};
global.window = {addEventListener(t,f){ (winL[t]=winL[t]||[]).push(f); }};
global.document = {getElementById:id => els[id], body:{classList:els['cut-panel'].classList}, documentElement:{clientWidth:1000, clientHeight:800}};
const bounds = {min:[-100,-900,-60], max:[100,900,60]};
let applied = null, cam = {fwd:[0,0,-1], tgt:[0,0,0]};
""" + js + r"""
const ctl = NMSKCutMode({bounds:()=>bounds, target:()=>cam.tgt, forward:()=>cam.fwd, apply:(kn,c,on,th)=>{ applied={kn,c,on,th}; },
  project:p => [p[0], p[1], 0, 1000], canvasRect:()=>({left:0,top:0,right:1000,bottom:800,width:1000,height:800}),
  pickPoint:e => e.hit || null, isPhone:()=>false});
const click = id => els[id]._l.click.forEach(f => f({}));
const key = (k, extra) => winL.keydown.forEach(f => f(Object.assign({key:k, target:{tagName:'BODY'}, preventDefault(){}}, extra||{})));
""" + script
    r = subprocess.run([NODE, "-e", harness], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


def test_controller_default_plane_and_side_are_the_old_default():
    out = _run_controller("""
click('t-cut');
const s = ctl.state(), a = applied;
process.stdout.write(JSON.stringify({s, a}));""")
    assert out["s"]["on"] and out["s"]["ori"] == "x" and out["s"]["rs"] == 1 and out["s"]["offset"] == 0
    # kept half is -x of the plane through the centre: -1*x + 0 >= 0
    assert out["a"]["kn"] == [-1, 0, 0] and out["a"]["c"] == 0 and out["a"]["on"] is True


def test_controller_facing_me_removes_the_near_half_by_default():
    out = _run_controller("""
cam.fwd = [0,0,-1]; click('t-cut'); click('ax_view');
process.stdout.write(JSON.stringify({s: ctl.state(), a: applied}));""")
    # forward = -z: the removed (near) side is where n0.x - a < 0 i.e. z > 0; kept: kn = n0 = (0,0,-1), c = -a = 0
    assert out["s"]["ori"] == "view" and out["s"]["rs"] == -1
    assert out["a"]["kn"] == [0, 0, -1] and out["a"]["c"] == 0


def test_controller_place_on_model_move_flip_keep_orientation_and_side():
    out = _run_controller("""
click('t-cut'); click('ax_y'); click('cut-place');
const used = ctl.consumeClick({hit:[10, 123, -5]});
const placed = ctl.state(), ap = applied;
click('st_10'); click('st_10'); key('ArrowUp'); key('ArrowDown', {shiftKey:true}); key('PageUp'); key('PageDown'); key('ArrowLeft');
const moved = ctl.state();
click('cut-flip'); const flipped = ctl.state(), af = applied;
click('cut-reset'); const reset = ctl.state();
click('cut-exit'); const exited = ctl.state(), ae = applied;
process.stdout.write(JSON.stringify({used, placed, ap, moved, flipped, af, reset, exited, ae}));""")
    assert out["used"] is True and out["placed"]["placed"] and out["placed"]["anchor"] == [10, 123, -5]
    assert out["placed"]["offset"] == 0 and out["placed"]["ori"] == "y"
    # through the clicked point, +Y side removed: kept kn = (0,-1,0), c = 123
    assert out["ap"]["kn"] == [0, -1, 0] and out["ap"]["c"] == 123
    assert out["moved"]["ori"] == "y" and out["moved"]["rs"] == 1 and out["moved"]["n0"] == [0, 1, 0]
    assert out["moved"]["offset"] == 20 + 1 - 10 + 10 - 10 - 1 == 10
    assert out["flipped"]["rs"] == -1 and out["flipped"]["offset"] == 10 and out["flipped"]["n0"] == [0, 1, 0]
    assert out["af"]["kn"] == [0, 1, 0] and out["af"]["c"] == -133                    # keep y >= 133
    assert out["reset"]["ori"] == "x" and out["reset"]["rs"] == 1 and out["reset"]["offset"] == 0 and not out["reset"]["placed"]
    assert out["exited"]["on"] is False and out["ae"]["on"] is False


def test_controller_clamps_to_the_model_and_addon_setcut_round_trip():
    out = _run_controller("""
click('t-cut'); click('ax_y'); ctl.move(1e6); const hi = ctl.state().a; ctl.move(-1e6); const lo = ctl.state().a;
ctl.setFromSpec({normal:[0,0,-1], point:[0,5,7]}); const s = ctl.state(), a = applied;
ctl.setFromSpec(null);
process.stdout.write(JSON.stringify({hi, lo, s, a, off: ctl.state().on}));""")
    assert out["hi"] == 900 and out["lo"] == -900
    assert out["s"]["on"] and out["s"]["ori"] == "view" and out["s"]["anchor"] == [0, 5, 7]
    assert out["a"]["kn"] == [0, 0, -1] and out["a"]["c"] == 7 and out["off"] is False


def test_controller_slice_thickness():
    out = _run_controller("""
click('t-cut'); click('ax_y');
const t0 = ctl.state().th, a0 = applied;
click('th_5'); const t5 = ctl.state().th, a5 = applied, lab5 = els['cut-th'].textContent, sl5 = els['cut-thsl'].value, pr5 = els['th_5']._a['aria-pressed'];
click('cut-flip'); const af = applied;                       // flipping the side keeps the thickness
ctl.move(7); const am = applied;
click('th_25'); const t25 = ctl.state().th;
els['cut-thsl'].value = '3.5'; els['cut-thsl']._l.input.forEach(f => f({})); const t35 = ctl.state().th;
els['cut-thsl'].value = '100'; els['cut-thsl']._l.input.forEach(f => f({})); const tmax = ctl.state().th, labmax = els['cut-th'].textContent;
ctl.setThickness(1e6); const tcap = ctl.state().th;
ctl.setThickness(0.01); const tmin = ctl.state().th;
ctl.setThickness(5); click('cut-exit'); const aexit = applied, texit = ctl.state().th;       // exit keeps the value but the engine is told "off"
click('t-cut'); const aback = applied;
ctl.setFromSpec({normal:[0,0,-1], point:[0,5,7]}); const aspec = applied;                      // the add-on's plane keeps the whole rest
ctl.setThickness(5); click('cut-reset'); const tr = ctl.state().th, ar = applied;
process.stdout.write(JSON.stringify({t0, a0, t5, a5, lab5, sl5, pr5, af, am, t25, t35, tmax, labmax, tcap, tmin, aexit, texit, aback, aspec, tr, ar}));""")
    assert out["t0"] == 0 and out["a0"]["th"] == 0                          # default: the whole rest of the body (old behaviour)
    assert out["t5"] == 5 and out["a5"]["th"] == 5 and out["a5"]["kn"] == [0, -1, 0]
    assert out["lab5"] == "5.0 mm slice" and out["sl5"] == "5" and out["pr5"] == "true"
    assert out["af"]["th"] == 5 and out["af"]["kn"] == [0, 1, 0] and out["am"]["th"] == 5
    assert out["t25"] == 25 and out["t35"] == 3.5
    assert out["tmax"] == 0 and out["labmax"] == "whole rest of body"       # slider at its far end = all
    assert out["tcap"] == 100 and out["tmin"] == 0.5
    assert out["aexit"]["on"] is False and out["texit"] == 5 and out["aback"]["on"] is True and out["aback"]["th"] == 5
    assert out["aspec"]["th"] == 0 and out["tr"] == 0 and out["ar"]["th"] == 0


def test_click_does_nothing_unless_armed():
    out = _run_controller("""
click('t-cut'); process.stdout.write(JSON.stringify({a: ctl.consumeClick({hit:[1,2,3]}), s: ctl.state().placed}));""")
    assert out == {"a": False, "s": False}


# ---------- rebuild paths ----------
def _fake_built(tmp_path, variant, tpl_text):
    bin_files = [{"path": "p_geo_00.txt", "bytes": 4}]
    man = {"variant": variant, "meshes": [{"name": "a", "x": "</script> in a name"}]} if variant else {"meshes": []}
    manifest = json.dumps(man, separators=(",", ":")).replace("</", "<\\/")
    html = rb.render(tpl_text, {"bin": '""', "files": json.dumps(bin_files), "manifest": manifest})
    d = tmp_path / "built"
    d.mkdir(exist_ok=True)
    (d / "p.html").write_text(html, encoding="utf-8")
    (d / "p_geo_00.txt").write_text("QUJD", encoding="ascii")
    return d / "p.html", html, manifest


@pytest.mark.parametrize("variant", [None, "vhf", "vhm", "native_female"])
def test_reinject_reproduces_data_blocks_and_wording(tmp_path, variant):
    old_tpl = ZAN.read_text(encoding="utf-8")        # stand-in for "the template the page was built from"
    built, html, manifest = _fake_built(tmp_path, variant, old_tpl)
    new_tpl = tmp_path / "new.template.html"
    new_tpl.write_text(old_tpl.replace("<style>", "<style>/* new template marker */", 1), encoding="utf-8")
    out = tmp_path / "out" / "p.html"
    rc = rb.main([str(built), "-o", str(out), "--template", str(new_tpl), "--old-template", str(ZAN)])
    assert rc == 0
    new = out.read_text(encoding="utf-8")
    assert "/* new template marker */" in new
    assert rb.extract_data(new) == rb.extract_data(html)                      # data literals byte-identical
    assert rb.extract_data(new)["manifest"] == manifest
    assert (out.parent / "p_geo_00.txt").read_bytes() == b"QUJD"              # geo file copied
    expect = {"vhf": "fitted", "vhm": "Visible Human male", "native_female": "Female base"}.get(variant)
    title = re.search(r"<title>(.*?)</title>", new).group(1)
    assert (expect in title) if expect else ("reference body" in title)


def test_reinject_refuses_to_write_next_to_the_built_page(tmp_path):
    built, _, _ = _fake_built(tmp_path, None, ZAN.read_text(encoding="utf-8"))
    with pytest.raises(SystemExit):
        rb.main([str(built), "-o", str(built.parent / "again.html")])


def test_build_viewer_html_template_only_path(tmp_path):
    """--template renders an existing bundle with another template; the external geo files are the bundle's bytes."""
    import base64
    sys.path.insert(0, str(REPO))
    blob = bytes(range(256)) * 40
    bundle = tmp_path / "b"
    bundle.mkdir()
    (bundle / "bundle.json").write_text('{"structures":[]}')
    (bundle / "bundle.b64").write_text(base64.b64encode(blob).decode())
    tpl = tmp_path / "t.html"
    tpl.write_text("<title>NMSK Atlas Viewer</title><script>__BUNDLE_JSON__|__BUNDLE_BIN_FILES__|\"__BUNDLE_B64__\"</script>")
    out = tmp_path / "o" / "page.html"
    subprocess.run([sys.executable, str(REPO / "scripts" / "build_viewer_html.py"), "--bundle", str(bundle), "-o", str(out),
                    "--external-bin", "--template", str(tpl)], check=True, capture_output=True, cwd=REPO)
    assert base64.b64decode((out.parent / "page_geo_00.txt").read_text()) == blob
    assert '{"structures":[]}|[{"path": "page_geo_00.txt"' in out.read_text()
