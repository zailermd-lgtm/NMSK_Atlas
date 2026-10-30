"""Q220 (= Q219 phase 2): the sourced PARTS model in the viewers -- a Parts list in every structure card and point markers on the model.

Covers: the shared UI block is identical in both templates; the controller logic under node (card rows, disputed-count note, unverified badge,
citation links, marker visibility for selection / toggle / cut + slab / hidden structure, graceful fallback); the per-page sidecar parts_data.json
(public anatomy layer, no clinical content, positions == the Q219 / Q220 geometry files, never 'measured', error bound present, placements
checked against the page's own geometry); the unfitted-Z-body placements and the proof that the fitted placements do not fit the base pages;
the regeneration path (geo files byte-identical, sidecar present).  Browser checks: scripts/zanatomy/q220_partscheck.py (PROJECT_STATE Q220)."""
import hashlib
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
sys.path.insert(0, str(REPO / "scripts" / "anatomy" / "q220"))
import sync_parts_ui_q220 as sync  # noqa: E402
import build_parts_sidecar as sc  # noqa: E402

NODE = shutil.which("node")
TABLE = REPO / "data/anatomy/structure_parts.json"
DER = REPO / "data/derived"
PAGES = {  # page key -> (dir, html, body, kind)
    "own_m": ("viewer_m_hr", "atlas_viewer_male.html", "vhm", "own"),
    "own_f": ("viewer_f_hr", "atlas_viewer_female.html", "vhf", "own"),
    "zan_m": ("viewer_zan_vhm", "atlas_viewer_zan_male_fitted.html", "zan_m", "zan"),
    "zan_f": ("viewer_zan_female", "atlas_viewer_zan_female.html", "zan_f", "zan"),
    "base_m": ("viewer_zan_atlas", "atlas_viewer_zan_atlas.html", "zbase_m", "zan"),
    "base_f": ("viewer_base_female", "atlas_viewer_base_female.html", "zbase_f", "zan"),
}


def page_html(key):
    d, h, _b, _k = PAGES[key]
    # Q274: build/q265 preferred when present -- the current reference build (post-Q250/Q252 Base F skeleton warp +
    # CVH additions); build/q220 / build/q218 are the original, now-stale Q220-round snapshots kept as a fallback only.
    for root in ("build/q265", "build/q220", "build/q218"):
        p = REPO / root / d / h
        if p.exists():
            return p
    return None


# ---------------------------------------------------------------- templates
@pytest.mark.parametrize("tpl", [OWN, ZAN], ids=["own", "zan"])
def test_templates_carry_the_shared_parts_block_verbatim(tpl):
    t = tpl.read_text(encoding="utf-8")
    for kind, (b, e) in sync.MARK.items():
        frag = (FRAG / f"parts_ui.{kind}").read_text(encoding="utf-8").rstrip("\n")
        assert t.count(b) == 1 and t.count(e) == 1, kind
        assert t[t.index(b) + len(b):t.index(e)] == "\n" + frag + "\n", f"{tpl.name}: {kind} block differs from viewer/parts_ui (run scripts/sync_parts_ui_q220.py)"


@pytest.mark.parametrize("tpl", [OWN, ZAN], ids=["own", "zan"])
def test_templates_wire_the_parts_controller(tpl):
    t = tpl.read_text(encoding="utf-8")
    for needle in ("function NMSKParts(E)", "NMSKParts({", 'url:"parts_data.json"', "partsCtl.update()", "partsCtl.overlay()", "partsCtl.select(",
                   "partsCtl.cardHtml()", "partsCtl.bind(", "partsCtl.load()", "cutCtl.state().th", "setDots", "meshVisible", "onLoaded", "__partsState",
                   'id="pm-layer"', 'id="pm-card"'):
        assert needle in t, needle
    # the markers follow the cut: the adaptor hands the kept half + the slab thickness (api.cutSlab() / state.th) to the shared code
    assert re.search(r"cut:function\(\)\{[^}]*th:cutCtl\.state\(\)\.th", t.replace(" ", "")) or "th:cutCtl.state().th" in t
    # fallback: a failed fetch / invalid file leaves the viewer as it was
    assert "}).catch(function(){ D = null; });" in t


def test_engine_specific_dot_drawing():
    o, z = OWN.read_text(encoding="utf-8"), ZAN.read_text(encoding="utf-8")
    assert "new THREE.Points(" in o and "depthTest:true" in o and "sizeAttenuation:false" in o       # three: depth-tested points under root
    assert "gl.POINTS" in z and "drawPartDots(mvp, eye)" in z and "gl.depthMask(false)" in z          # Z: GL points after the anatomy, depth test on
    assert z.index("drawPartDots(mvp, eye);") < z.index("if (addonDraw.length)")
    # the toggle lives in the toolbar of each page
    for t in (o, z):
        assert "toolbar:document.getElementById(" in t


# ---------------------------------------------------------------- controller under node (mock DOM)
NODE_HARNESS = r"""
const fs = require('fs');
const src = fs.readFileSync(process.argv[2], 'utf8');
const data = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
function el(){ const e = {className:'', hidden:false, style:{}, children:[], _l:{}, classList:{toggle(){}, add(){}, remove(){}},
  addEventListener(t,f){ (this._l[t] = this._l[t]||[]).push(f); }, appendChild(c){ this.children.push(c); }, querySelector(){ return el(); },
  querySelectorAll(){ return []; }, setAttribute(k,v){ this[k]=v; }, contains(){ return false; }, closest(){ return null; }, click(){}, offsetWidth:300, offsetHeight:200};
  Object.defineProperty(e, 'innerHTML', {set(v){ this._h = v; this.firstChild = el(); }, get(){ return this._h || ''; }}); return e; }
global.document = {getElementById(i){ return (this._e = this._e||{})[i] = (this._e[i]||el()); }, createElement(){ return el(); },
  addEventListener(){}, documentElement:{clientWidth:1400, clientHeight:900}};
global.window = {fetch:true, matchMedia:()=>({matches:true})}; global.matchMedia = window.matchMedia;
global.fetch = () => Promise.resolve({ok:true, json:()=>Promise.resolve(data)});
eval(src + '; global.NMSKParts = NMSKParts;');
const scenario = JSON.parse(process.argv[4]);
const toolbar = el();
let cutState = null, visible = {}, dots = [];
const E = {url:'x', canvasRect:()=>({left:0,top:0,right:1000,bottom:800,width:1000,height:800}), project:(p)=>[p[0]/1000, p[1]/1000, 0, 1],
  cut:()=>cutState, meshVisible:(id)=>visible[id]!==false, focusAt(){}, redraw(){}, setDots:(l)=>{ dots = l; }, toolbar, toolClass:'tool', onLoaded(){}};
const C = NMSKParts(E);
C.load();
setTimeout(() => {
  const out = {};
  out.loaded = C.state().loaded;
  out.toolbar_button = toolbar.children.length;
  C.select(scenario.mesh);
  out.card = C.cardHtml();
  out.sel = C.state().sel;
  C.setMode('sel');           // Q256: the marker layer defaults to Off; opt in the same way the real panel does
  C.update(); out.sel_visible = C.state().markers.filter(m=>m.vis).map(m=>m.part);
  C.setShowAll(true); C.update(); out.all_visible = C.state().markers.filter(m=>m.vis).length; out.total = C.state().placements;
  C.setShowAll(false);
  // cut: the marker of the first selected placement, kept half n.p + c >= 0 (+ slab th)
  const m = C.state().markers.filter(x=>x.why !== 'off')[0];
  if (m){
    const p = m.xyz, n = [0,1,0];
    const at = (d, th) => { cutState = {kn:n, c:-(n[1]*p[1]) + d, th:th}; C.update(); return C.state().markers[m.j]; };   // marker sits d mm inside the kept half
    out.cut_removed = at(-5, 0).why; out.cut_kept = at(5, 0).why; out.slab_inside = at(3, 5).why; out.slab_beyond = at(8, 5).why; out.slab_edge = at(5, 5).why; out.slab_zero_all = at(500, 0).why;
    cutState = null; visible[m.part] = true; C.update(); out.no_cut = C.state().markers[m.j].why;
    const carriers = data.placed[m.j].car; carriers.forEach(c => visible[c] = false); C.update(); out.hidden_structure = C.state().markers[m.j].why;
  }
  console.log(JSON.stringify(out));
}, 50);
"""


def run_node(sidecar, mesh):
    if not NODE:
        pytest.skip("node not available")
    h = REPO / "build" / "_q220_node_harness.js" if False else None
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        hp = Path(td) / "h.js"
        hp.write_text(NODE_HARNESS)
        r = subprocess.run([NODE, str(hp), str(FRAG / "parts_ui.js"), str(sidecar), json.dumps({"mesh": mesh})], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr[-800:]
    return json.loads(r.stdout.strip().splitlines()[-1])


@pytest.fixture(scope="module")
def sidecars(tmp_path_factory):
    out = {}
    d = tmp_path_factory.mktemp("sidecars")
    for k in ("own_m", "zan_m"):
        h = page_html(k)
        if h is None:
            continue
        j = sc.build(h, PAGES[k][2])
        f = d / f"{k}.json"
        f.write_text(json.dumps(j, separators=(",", ":")))
        out[k] = (f, j)
    return out


def test_controller_card_rows_notes_and_links(sidecars):
    if "own_m" not in sidecars:
        pytest.skip("build/q218 or build/q220 pages not present")
    f, j = sidecars["own_m"]
    o = run_node(f, "semimembranosus_r")
    assert o["loaded"] and o["toolbar_button"] == 1
    card = o["card"]
    assert card.count('class="pm-row"') >= 8 and "Sources disagree on the count" in card
    for n in ("<b>3</b>", "<b>5</b>", "<b>6</b>"):          # semimembranosus: 3 / 5 / 6 insertions
        assert n in card
    assert "https://pubmed.ncbi.nlm.nih.gov/" in card and "https://doi.org/" in card
    assert 'class="pm-ty pm-ty-insertion_point">insertion<' in card and 'class="pm-ty pm-ty-origin_part">origin<' in card      # type badges
    d = run_node(f, "deltoid_r")
    assert d["card"].count('class="pm-row"') >= 3
    assert re.search(r'pm-ty-head_belly">head<', d["card"])
    assert "unverified" in d["card"]                       # the deltoid origin rows are textbook-only: flagged
    assert 'data-pm-mesh="deltoid_r"' in d["card"]


def test_controller_markers_follow_selection_toggle_cut_slab_and_layer(sidecars):
    if "own_m" not in sidecars:
        pytest.skip("pages not present")
    f, j = sidecars["own_m"]
    o = run_node(f, "deltoid_r")
    assert len(o["sel_visible"]) >= 1 and o["sel_visible"] == ["deltoid.insertion_deltoid_tuberosity_complex"]
    assert o["all_visible"] > len(o["sel_visible"]) and o["total"] == len(j["placed"])
    assert o["cut_removed"] == "cut" and o["cut_kept"] == ""
    assert o["slab_inside"] == "" and o["slab_beyond"] == "cut" and o["slab_edge"] == "" and o["slab_zero_all"] == ""
    assert o["no_cut"] == "" and o["hidden_structure"] == "hidden"


def test_controller_no_card_without_parts_and_graceful_when_data_invalid(sidecars):
    if "own_m" not in sidecars:
        pytest.skip("pages not present")
    f, j = sidecars["own_m"]
    o = run_node(f, "skin")                                     # a mesh without parts
    assert o["card"] == "" and o["sel"] is None


# ---------------------------------------------------------------- the data layer
def test_sidecar_is_public_anatomy_layer_only():
    h = page_html("own_m")
    if h is None:
        pytest.skip("pages not present")
    j = sc.build(h, "vhm")
    txt = json.dumps(j).lower()
    for bad in ("motor_point", "needle", "trigger point", "clinical_", "endplate", "injection", "risk"):
        assert bad not in txt, bad
    assert j["schema"] == "nmsk.parts_sidecar.v1" and "CC BY-SA" in j["license"] and "No clinical content" in j["license"]
    assert set(j["source_classes"]) == {"rule_based", "z_fill"}


@pytest.mark.parametrize("key", list(PAGES))
def test_sidecar_content_per_page(key):
    h = page_html(key)
    if h is None:
        pytest.skip("pages not present")
    body = PAGES[key][2]
    j = sc.build(h, body)
    kind, meshes = sc.load_page(h)
    ids = {m[0] for m in meshes}
    n = len(j["parts"])
    assert n >= (150 if kind == "own" else 250)
    assert all(m in ids for m in j["mesh_parts"]) and all(0 <= i < n for e in j["mesh_parts"].values() for i in e["p"])
    geo = json.loads((DER / sc.GEOFILE[body]).read_text())
    gm = {(x["part_id"], x["side"]): x for x in geo["placed"]}
    seen = set()
    for pl in j["placed"]:
        pid = j["parts"][pl["p"]]["id"]
        g = gm[(pid, pl["s"])]
        assert pl["xyz"] == [round(v, 2) for v in g["position_mm"]]
        assert pl["c"] in ("rule_based", "z_fill") and pl["c"] != "measured"
        assert pl["e"] is not None or pl.get("ext"), "a placement needs an error bound or (Z part mesh in the reference body) the extent of the mesh it stands for"
        assert pl["mt"] and pl["rule"] and pl["car"] and all(c in ids for c in pl["car"])
        seen.add((pid, pl["s"]))
    assert len(seen) == len(j["placed"])
    assert j["geometry"]["placements_valid_on_this_page"] == len(j["placed"]) == j["counts"]["placements"]
    assert not j["geometry"]["dropped"], j["geometry"]["dropped"][:3]
    # every text-only part says why; nothing placed is also listed as text-only except a one-sided placement
    for pid, why in j["text_only"].items():
        assert why
    # verified rows cite a journal reference with a PMID; unverified rows (textbook / owner) cite their source and carry the flag + note
    for p in j["parts"]:
        refs = [j["refs"][k] for k in p["r"]]
        assert refs, p["id"]
        if p.get("u"):
            assert p.get("note") and all(r["k"] != "journal" or r["pmid"] for r in refs), p["id"]
        else:
            assert any(r["k"] == "journal" and r["pmid"] for r in refs), p["id"]
    assert j["counts"]["unverified"] == sum(1 for p in j["parts"] if p.get("u")) > 0
    # the owner's examples are reachable on this page
    st = {p["st"] for p in j["parts"]}
    assert {"deltoid", "semimembranosus", "tibialis_posterior"} <= st
    if kind == "zan":
        assert "collateral_interphalangeal_ligaments_of_hand" in st
    d = [e for m, e in j["mesh_parts"].items() if m.startswith("deltoid_r") or "deltoid_muscle_r" in m]
    assert d and all(len(e["p"]) >= 3 for e in d)


def test_semimembranosus_and_tibialis_posterior_on_z_pages():
    """The Q219 id snapshot missed the Z names (zan_tibialis_posterior_muscle_l ...): the sidecar maps them by name as well."""
    h = page_html("zan_m")
    if h is None:
        pytest.skip("pages not present")
    j = sc.build(h, "zan_m")
    assert "zan_tibialis_posterior_muscle_r" in j["mesh_parts"] and len(j["mesh_parts"]["zan_tibialis_posterior_muscle_r"]["p"]) >= 8
    assert "semimembranosus_r" in j["mesh_parts"]
    assert "zan_clavicular_part_of_deltoid_muscle_r" in j["mesh_parts"]
    assert "zan_collateral_interphalangeal_ligaments_of_hand_r" in j["mesh_parts"]
    assert len(j["sets"]) >= 5 and any(len(s["counts"]) >= 2 for s in j["sets"].values())


# ---------------------------------------------------------------- base pages: fitted placements do not fit the reference body
def test_fitted_placements_do_not_coincide_with_the_unfitted_base_body():
    hm, hf = page_html("base_m"), page_html("base_f")
    if hm is None or hf is None:
        pytest.skip("pages not present")
    saved = dict(sc.GEOFILE)
    try:
        for base_key, fitted, h in (("zbase_m", "Q219_parts_zan_m.json", hm), ("zbase_f", "Q219_parts_zan_f.json", hf)):
            sc.GEOFILE[base_key] = fitted
            j = sc.build(h, base_key)
            n_all = j["geometry"]["placements_in_file_for_this_page"]
            dropped = len(j["geometry"]["dropped"])
            assert dropped / n_all > 0.3, (base_key, dropped, n_all)       # the fit moves structures by up to ~90 mm: the frames do not coincide
            assert max(float(re.search(r"lies (\d+) mm", d["why"]).group(1)) for d in j["geometry"]["dropped"]) > 60
    finally:
        sc.GEOFILE.clear(); sc.GEOFILE.update(saved)


@pytest.mark.parametrize("b", ["zbase_m", "zbase_f"])
def test_base_body_placements_file(b):
    g = json.loads((DER / f"Q220_parts_{b}.json").read_text())
    assert g["body"] == b and g["counts"]["placed"] >= 100
    for x in g["placed"]:
        assert x["source_class"] in ("rule_based", "z_fill") and x["source_class"] != "measured"
        assert x["error_bound_mm"] is not None or (x["rule"] == "z_part_mesh" and x.get("bbox_mm")), x["part_id"]


def test_base_placements_are_computed_on_the_base_meshes():
    """Same rules as Q219, run on the unfitted Z body: every placement is on / in / within its bound of the base page's own meshes."""
    for key in ("base_m", "base_f"):
        h = page_html(key)
        if h is None:
            pytest.skip("pages not present")
        j = sc.build(h, PAGES[key][2])
        assert not j["geometry"]["dropped"] and len(j["placed"]) >= 100
        assert j["counts"]["parts_placed"] >= 55


# ---------------------------------------------------------------- regeneration
def test_regen_script_writes_the_sidecar_and_keeps_geometry():
    t = (REPO / "scripts/regen_cut_q218.sh").read_text()
    assert "build_parts_sidecar.py" in t and "parts_data.json" in t and "BODY=(" in t and "zbase_m" in t
    for key, (d, h, body, kind) in PAGES.items():
        v = REPO / "build/q220/_verify" / f"{d}.json"
        p = REPO / "build/q220" / d
        if not v.exists():
            continue
        r = json.loads(v.read_text().splitlines()[0])
        assert r["OK"] and r["geo_identical"] and r["literals_identical"] and r["new_equals_current_template_plus_same_data"], key
        assert (p / "parts_data.json").exists()


def _sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def test_q220_geo_files_identical_to_q218():
    n = 0
    for d, h, _b, _k in PAGES.values():
        a, b = REPO / "build/q218" / d, REPO / "build/q220" / d
        if not (a.exists() and b.exists()):
            continue
        for g in sorted(a.glob("*_geo_[0-9][0-9].txt")):
            assert _sha(g) == _sha(b / g.name), g
            n += 1
    if not n:
        pytest.skip("build/q218 + build/q220 not present")
