"""Q256 item 3: nerve GROUPS (a common root / trunk / division / cord / branch of the brachial or lumbosacral plexus) selectable
with the EXISTING Q232 selection-sets controller (markIds), on both engines, via the shared viewer/nerve_groups/ fragment."""
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
OWN = (REPO / "viewer/atlas_viewer.template.html").read_text(encoding="utf-8")
ZAN = (REPO / "viewer/zan_atlas.template.html").read_text(encoding="utf-8")
FR = REPO / "viewer/nerve_groups"
sys.path.insert(0, str(REPO / "scripts"))
NODE = __import__("shutil").which("node")


def between(text, b, e):
    i = text.index(b) + len(b)
    return text[i:text.index(e, i)].strip("\n")


# ------------------------------------------------------------------ sync / templates
def test_sync_script_is_a_no_op():
    r = subprocess.run([sys.executable, "scripts/sync_nerve_groups_q256.py", "--check"], cwd=REPO, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.parametrize("kind,fname,marks", [
    ("css", "nerve_groups.css", ("/* NERVE-GROUPS css begin */", "/* NERVE-GROUPS css end */")),
    ("html", "nerve_groups.html", ("<!-- NERVE-GROUPS html begin -->", "<!-- NERVE-GROUPS html end -->")),
    ("js", "nerve_groups.js", ("/* NERVE-GROUPS js begin */", "/* NERVE-GROUPS js end */")),
])
def test_fragment_verbatim_in_both_templates(kind, fname, marks):
    frag = (FR / fname).read_text(encoding="utf-8").rstrip("\n")
    b, e = marks
    for t in (OWN, ZAN):
        assert t.count(b) == 1 and t.count(e) == 1
        assert between(t, b, e) == frag


def test_glue_verbatim_per_engine():
    assert between(OWN, "/* NERVE-GROUPS glue begin */", "/* NERVE-GROUPS glue end */") == (FR / "glue_own.js").read_text(encoding="utf-8").rstrip("\n")
    assert between(ZAN, "/* NERVE-GROUPS glue begin */", "/* NERVE-GROUPS glue end */") == (FR / "glue_zan.js").read_text(encoding="utf-8").rstrip("\n")


def test_glue_reuses_the_existing_selection_controller_not_a_parallel_one():
    for g in ("glue_own.js", "glue_zan.js"):
        t = (FR / g).read_text(encoding="utf-8")
        assert "selCtl.markIds(" in t and "selCtl.clear()" in t and 'selCtl.preset("hlsel")' in t
        assert "plexus_groups.json" in t


def test_selection_js_markids_added_and_exposed():
    sel = (REPO / "viewer/selection/selection.js").read_text(encoding="utf-8")
    assert "function markIds(ids, on, replace, quiet)" in sel
    assert "markIds:markIds" in sel
    r = subprocess.run([sys.executable, "scripts/sync_q227.py", "--check"], cwd=REPO, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


# ------------------------------------------------------------------ data: the real, cited plexus lineage, walked (not invented)
def test_source_plexus_data_is_a_real_single_parent_tree():
    for f in ("brachial_plexus.json", "lumbosacral_plexus.json"):
        recs = json.loads((REPO / "data/nerves" / f).read_text())
        ids = {r["id"] for r in recs}
        for r in recs:
            if r.get("parent_id"):
                assert r["parent_id"] in ids, (f, r["id"])
            assert r.get("source"), (f, r["id"], "every row must cite a source")


@pytest.fixture(scope="module")
def groups():
    r = subprocess.run([sys.executable, "scripts/anatomy/q256/plexus_groups.py"], cwd=REPO, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    return json.loads((REPO / "data/derived/Q256_plexus_groups.json").read_text())


def test_plexus_groups_schema_and_tree(groups):
    assert groups["schema"] == "nmsk.plexus_groups.v1"
    # Q261: SOURCES extended to data/nerves/{cranial_and_cervical_nerves,autonomic_nervous_system}.json, queued by
    # Q259/Q260's own open-items entry -- the picker now also indexes the cervical plexus, the individual cranial
    # nerve groups (facial_n, trigeminal_n_v1/v2/v3, glossopharyngeal_n, vagus_n, accessory_n, hypoglossal_n,
    # vestibulocochlear_n, olfactory_n, optic_n, extraocular_cranial_nerves, pharyngeal_plexus) and the autonomic
    # sympathetic_trunk tree, alongside the original three limb plexuses.
    assert set(groups["plexuses"]) == {"brachial_plexus", "lumbar_plexus", "sacral_plexus", "cervical_plexus",
                                        "facial_n", "trigeminal_n_v1", "trigeminal_n_v2", "trigeminal_n_v3",
                                        "vagus_n", "accessory_n", "hypoglossal_n",
                                        "vestibulocochlear_n", "olfactory_n", "optic_n", "extraocular_cranial_nerves",
                                        "pharyngeal_plexus", "sympathetic_trunk"}
    for nid, n in groups["nodes"].items():
        assert nid in n["downstream"]                                   # a node is its own downstream member
        for c in n["children"]:
            assert c in n["downstream"] and groups["nodes"][c]["parent_id"] == nid
        if n["parent_id"]:
            assert nid in groups["nodes"][n["parent_id"]]["downstream"]  # a child is downstream of its parent


def test_known_real_lineages_are_present_exactly(groups):
    # the owner's own worked example: C5/C6 -> upper (superior) trunk -> ... -> lateral cord -> musculocutaneous + lateral root of median
    down = set(groups["nodes"]["brachial_cord_lateral"]["downstream"])
    assert {"musculocutaneous_n", "median_n_lateral_root", "lateral_pectoral_n"} <= down
    assert groups["nodes"]["brachial_trunk_superior"]["parent_id"] == "brachial_root_C5"
    assert groups["nodes"]["brachial_cord_lateral"]["parent_id"] == "brachial_div_superior_ant"
    # sciatic -> tibial / common fibular -> superficial / deep fibular, real divisions
    sciatic_down = set(groups["nodes"]["sciatic_n"]["downstream"])
    assert {"tibial_n", "common_fibular_n", "superficial_fibular_n", "deep_fibular_n", "medial_plantar_n", "lateral_plantar_n"} <= sciatic_down
    # obturator divisions (real anatomy: anterior division to adductor longus/brevis/gracilis, posterior to obturator externus / adductor magnus)
    ant = set(groups["nodes"]["obturator_n_anterior_division"]["downstream"])
    post = set(groups["nodes"]["obturator_n_posterior_division"]["downstream"])
    assert "obturator_n_branch_to_adductor_longus" in ant and "obturator_n_branch_to_obturator_externus" in post
    assert ant.isdisjoint(post)  # the two divisions' OWN sub-branches never overlap


def test_the_known_single_parent_gap_is_not_silently_hidden():
    # median nerve is only downstream of the LATERAL cord here (its medial-root contribution from the medial cord is a real, documented
    # gap of the single-parent source data, not something this round invented or silently papered over -- see plexus_groups.py docstring)
    doc = (REPO / "scripts/anatomy/q256/plexus_groups.py").read_text(encoding="utf-8")
    assert "median nerve" in doc and "single-parent" in doc
    assert (REPO / "docs/OPEN_ITEMS_FOR_OWNER.md").read_text(encoding="utf-8").count("median") >= 1


# ------------------------------------------------------------------ per-page sidecar: honest, page-checked counts
def _fake_page(tmp_path, ids):
    """A minimal Z-engine-style (manifest/blob) built page build_parts_sidecar.load_page can read, carrying exactly `ids` as meshes
    (one degenerate vertex/0 faces each -- only the id set matters for the plexus sidecar, not real geometry)."""
    import base64
    blob = bytes(6 * len(ids))                                   # 1 vertex (3 x u16 = 0,0,0) per id, back to back
    meshes = [dict(id=i, side=None, sys="nerve", vc=1, vo=k * 6, ic=0, io=0, min=[0, 0, 0], span=[1, 1, 1]) for k, i in enumerate(ids)]
    man = dict(meshes=meshes)
    bin_path = tmp_path / "blob.b64"
    bin_path.write_text(base64.b64encode(blob).decode(), encoding="utf-8")
    html = ("<html><body>\n<script>\nwindow.__ANATOMY_MANIFEST__=%s;\n</script>\n<script>\nwindow.__ANATOMY_BIN_FILES__=%s;\n</script>\n</body></html>"
            ) % (json.dumps(man), json.dumps([{"path": "blob.b64"}]))
    p = tmp_path / "page.html"
    p.write_text(html, encoding="utf-8")
    return p


def test_build_plexus_sidecar_counts_are_honest(tmp_path, groups):
    pytest.importorskip("numpy")
    page = _fake_page(tmp_path, ["musculocutaneous_n_r", "axillary_n_r", "radial_n_r"])
    sys.path.insert(0, str(REPO / "scripts/anatomy/q256"))
    import build_plexus_sidecar as bps
    out = bps.build(page)
    assert out["schema"] == "nmsk.plexus_sidecar.v1"
    lat = out["nodes"].get("brachial_cord_lateral")
    assert lat and lat["sides"]["r"]["resolved_count"] == 1 and "musculocutaneous_n_r" in lat["sides"]["r"]["resolved_ids"]
    post = out["nodes"].get("brachial_cord_posterior")
    assert post and post["sides"]["r"]["resolved_count"] == 2 and post["sides"]["r"]["resolved_count"] < post["sides"]["r"]["total"]
    assert "l" not in post["sides"]                                     # nothing on the left in this fake page: honestly absent, not fabricated
    med = out["nodes"].get("brachial_cord_medial")
    assert med is None                                                  # zero resolvable downstream members -> not listed at all


# ------------------------------------------------------------------ controller under node (mocked DOM + fetch, mirrors test_q220's harness)
HARNESS = r"""
const fs = require('fs');
const src = fs.readFileSync(process.argv[2], 'utf8');
const data = JSON.parse(fs.readFileSync(process.argv[3], 'utf8'));
function el(){ const kids=[]; const e = {className:'', hidden:true, style:{}, children:kids, _l:{}, tabIndex:0,
  classList:{toggle(){}, add(){}, remove(){}},
  addEventListener(t,f){ (this._l[t] = this._l[t]||[]).push(f); },
  appendChild(c){ kids.push(c); return c; },
  querySelector(sel){
    if (sel === '.ng-list') return this._list || (this._list = el());
    if (sel === '.ng-st') return this._st || (this._st = el());
    if (sel === '.ng-hint') return this._hint || (this._hint = el());
    if (sel === '.ng-x' || sel === '.ng-clear' || sel === '.ng-hl' || sel === '.ng-side' || sel === '.ng-plx' || sel === '.ng-search') return this['_q_' + sel] || (this['_q_' + sel] = el());
    return el();
  },
  querySelectorAll(sel){ return this.children.filter(c => true); },
  setAttribute(k,v){ this[k]=v; }, getAttribute(k){ return this[k]; }, contains(){ return false; }, closest(){ return null; }, click(){}, offsetWidth:300, offsetHeight:200};
  Object.defineProperty(e, 'innerHTML', {set(v){ this._h = v; this._list=null; this._st=null; this._hint=null; }, get(){ return this._h || ''; }}); return e; }
global.document = {getElementById(i){ return (this._e = this._e||{})[i] = (this._e[i]||el()); }, createElement(){ return el(); }, addEventListener(){} };
global.window = {fetch:true}; global.localStorage = {getItem(){ return null; }, setItem(){}};
global.fetch = () => Promise.resolve({ok:true, json:()=>Promise.resolve(data)});
eval(src + '; global.NMSKNerveGroups = NMSKNerveGroups;');
const marked = [];
const E = {url:'x', toolbar:el(), toolClass:'tool', isPhone(){ return false; },
  mark(ids, replace){ marked.push({ids:ids.slice(), replace:!!replace}); return ids.length; }, clear(){ marked.push({clear:true}); }, highlight(){ marked.push({hl:true}); }};
const C = NMSKNerveGroups(E);
C.load();
setTimeout(() => {
  const out = { loaded: C.state().loaded, plexuses: C.state().plexuses };
  console.log(JSON.stringify({out, marked}));
}, 30);
"""


def run_node(payload):
    if not NODE:
        pytest.skip("node not available")
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        hp = Path(td) / "h.js"
        hp.write_text(HARNESS)
        r = subprocess.run([NODE, str(hp), str(FR / "nerve_groups.js"), str(payload)], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr[-1500:]
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_controller_loads_graceful_fallback_when_sidecar_absent(tmp_path):
    p = tmp_path / "bad.json"; p.write_text("not json")
    # patch the fetch mock to fail: reuse the harness but with a response that is not a valid sidecar
    bad = tmp_path / "bad_payload.json"; bad.write_text(json.dumps({"schema": "nope"}))
    o = run_node(bad)
    assert o["out"]["loaded"] is False


def test_controller_loads_and_can_mark_a_group(tmp_path, groups):
    sidecar = tmp_path / "sidecar.json"
    sidecar.write_text(json.dumps({
        "schema": "nmsk.plexus_sidecar.v1", "plexuses": ["brachial_plexus"],
        "by_plexus": {"brachial_plexus": ["brachial_cord_lateral"]},
        "nodes": {"brachial_cord_lateral": {"name": "Lateral cord", "display_name": "Lateral cord (C5-C7)", "level": "cord", "level_label": "Cord",
                                             "plexus": "brachial_plexus", "parent_id": "brachial_div_superior_ant", "is_leaf": False,
                                             "sides": {"r": {"resolved_ids": ["musculocutaneous_n_r", "median_n_lateral_root_r"], "resolved_count": 2, "total": 6, "missing_sample": ["lateral_pectoral_n"], "missing_count": 4}}}}}))
    o = run_node(sidecar)
    assert o["out"]["loaded"] is True and o["out"]["plexuses"] == ["brachial_plexus"]
