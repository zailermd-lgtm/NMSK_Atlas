"""Q364: per-structure colours for the eye (and the dura, the visual pathway, lids, tear passages) in the Z engine.

The committed table (data/anatomy/structure_colours_q364.json), the inject path (NMSK-COLOURS markers, a page gets only its own
ids), the regen step, and the engine's colOf() under node: a table colour beats the layer colour, '@layer' follows the layer, and
the radiographic grey, the selection highlight and the user's own colour ("all / from now on") still win over it. Also the
translucent pass and the click-through rule for near-transparent parts."""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "anatomy" / "q364"))
import colours_q364 as CQ  # noqa: E402

ZAN = REPO / "viewer" / "zan_atlas.template.html"
REGEN = REPO / "scripts" / "regen_template_only.py"
NODE = shutil.which("node")
EYE = ["zan_sclera", "zan_cornea", "zan_iris", "zan_lens", "zan_retina", "zan_vitreous_body"]


def table():
    return {b: e for e in CQ.load() for b in e["ids"]}


def test_eye_parts_have_their_own_colours():
    t = table()
    for b in EYE:
        assert b in t, b
    cols = {t[b]["hex"] for b in EYE}
    assert len(cols) >= 5                                   # sclera, cornea, iris, lens, retina differ
    assert t["zan_sclera"]["hex"] not in ("@cns", "@nerve")
    assert t["zan_cornea"]["alpha"] < 0.35 and t["zan_vitreous_body"]["alpha"] < 0.35      # clear media, clicked through
    assert t["zan_lens"]["alpha"] < 1 and t["zan_iris"]["alpha"] == 1
    assert t["optic_n"]["hex"] == "@nerve"                    # optic nerve keeps the nerve colour
    assert t["zan_spinal_dura"]["hex"].startswith("#")        # the dura is not brain lavender
    for m in ("superior_rectus", "lateral_rectus", "inferior_oblique"):
        assert m not in t                                     # extra-ocular muscles stay muscle-coloured


def test_inject_resolves_against_the_page(tmp_path):
    man = {"meshes": [{"id": i} for i in ("zan_sclera_l", "zan_sclera_r", "optic_n_l", "superior_rectus_r")]}
    tpl = ZAN.read_text(encoding="utf-8")
    m = re.search(re.escape(CQ.BEGIN) + ".*?" + re.escape(CQ.END), tpl, re.S)
    assert m and tpl.count(CQ.BEGIN) == 1
    page = tmp_path / "atlas_viewer_x.html"
    page.write_text(m.group(0) + "\nwindow.__ANATOMY_MANIFEST__=" + json.dumps(man) + ";\n", encoding="utf-8")
    CQ.inject(tmp_path)
    j = json.loads(re.search(r'id="nmsk-colours">(.*?)</script>', page.read_text(encoding="utf-8")).group(1))
    assert set(j["c"]) == {"zan_sclera_l", "zan_sclera_r", "optic_n_l"}
    assert j["c"]["optic_n_l"] == ["@nerve", 1.0]


def test_regen_runs_the_step_for_base_pages_only():
    s = REGEN.read_text(encoding="utf-8")
    assert re.search(r'if p in \("base_m", "base_f"\):[^\n]*Q364[^\n]*\n\s+run\(\["python3", "scripts/anatomy/q364/colours_q364.py", "--inject"', s)


def test_engine_translucent_pass_and_click_through():
    s = ZAN.read_text(encoding="utf-8")
    assert "function solid(e){ return solid0(e) && q364A(e) >= 0.999; }" in s
    assert "q364A(o) >= 0.35" in s                              # pickable(): near-transparent parts are clicked through
    assert "B.q364a.forEach" in s


HARNESS = r"""
var src = require('fs').readFileSync(process.argv[2], 'utf8');
var i = src.indexOf('    function q364Tab() {'), j = src.indexOf('    function sideOK(o) {');
var body = src.slice(i, j);
var table = JSON.stringify({v:1, c:{zan_sclera_r:['#ebe6da', 1], optic_n_r:['@nerve', 1], zan_cornea_r:['#dcecf3', 0.22]}});
var document = {getElementById: function(id){ return id === 'nmsk-colours' ? {textContent: table} : null; }};
var COL = {cns:[0.5,0.4,0.7], nerve:[0.85,0.76,0.25], muscle:[0.7,0.28,0.24], vein:[0.2,0.3,0.6]};
var q301 = {grey:null}, q301Grey = new Map(), userCols = new Map(), markCols = new Map();
var look = {}, user = {};
var selCtl = {look:function(id){ return look[id] || ''; }, hlHex:function(){ return 0xff0000; },
              userHex:function(id){ return user[id] == null ? null : user[id]; }, tinted:function(){ return false; }};
function hlCol(h){ return [((h >> 16) & 255) / 255, ((h >> 8) & 255) / 255, (h & 255) / 255]; }
eval(body);
function hex(c){ return '#' + c.map(function(x){ return ('0' + Math.round(x * 255).toString(16)).slice(-2); }).join(''); }
var sc = {id:'zan_sclera_r', layer:'cns'}, on = {id:'optic_n_r', layer:'cns'}, co = {id:'zan_cornea_r', layer:'cns'}, mu = {id:'lateral_rectus_r', layer:'muscle'};
var out = {sclera: hex(colOf(sc)), optic: colOf(on) === COL.nerve, muscle: colOf(mu) === COL.muscle, stable: colOf(sc) === colOf(sc),
           corneaA: q364A(co), scleraA: q364A(sc), muscleA: q364A(mu)};
user.zan_sclera_r = 0x00ff00; out.user = hex(colOf(sc));
look.zan_sclera_r = 'hl'; out.hl = hex(colOf(sc)); look.zan_sclera_r = '';
q301.grey = function(){ return 0.5; }; out.grey = hex(colOf(sc));
console.log(JSON.stringify(out));
"""


@pytest.mark.skipif(NODE is None, reason="node not available")
def test_colof_table_and_overrides_under_node(tmp_path):
    h = tmp_path / "h.js"
    h.write_text(HARNESS, encoding="utf-8")
    r = subprocess.run([NODE, str(h), str(ZAN)], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    o = json.loads(r.stdout.strip().splitlines()[-1])
    assert o["sclera"] == "#ebe6da"               # the table beats the layer (cns) colour
    assert o["optic"] and o["muscle"] and o["stable"]
    assert o["corneaA"] == 0.22 and o["scleraA"] == 1 and o["muscleA"] == 1
    assert o["user"] == "#00ff00"                 # the user's own colour wins over the table
    assert o["hl"] == "#ff0000"                   # the selection highlight wins over both
    assert o["grey"] == "#808080"                 # the radiographic style wins over everything
