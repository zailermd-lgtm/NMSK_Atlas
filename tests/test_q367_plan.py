"""Q367: the injection mode's plan-first flow, marker pair and Safety panel -- the pure geometry (plane locus, size classes), the
private / public split, no invented thresholds, and the regen step for the vessel calibre sibling. (The browser behaviour is checked
by scripts/anatomy/q367/verify_plan_q367.py.)"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
JS = REPO / "clinical" / "needle_tool.js"
sys.path.insert(0, str(REPO / "scripts" / "clinical"))
import stage_clinical_files as scf  # noqa: E402


def node(code: str):
    r = subprocess.run(["node", "-e", "const P = require(" + json.dumps(str(JS)) + ");\n" + code], capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


BOX = r"""
function box(c, h) {   // an axis-aligned closed box centred c, half sizes h: 8 vertices, 12 outward triangles
  const v = [], f = [[0,2,1],[0,3,2],[4,5,6],[4,6,7],[0,1,5],[0,5,4],[2,3,7],[2,7,6],[1,2,6],[1,6,5],[0,4,7],[0,7,3]];
  for (const [x, y, z] of [[-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1],[-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]]) v.push(c[0]+x*h[0], c[1]+y*h[1], c[2]+z*h[2]);
  return {pos: Float32Array.from(v), idx: Uint16Array.from(f.flat())};
}
"""


def test_plane_locus_is_midway_and_bounded_by_the_gap():
    out = node(BOX + r"""
      const A = box([0, 0, 0], [10, 10, 2]), B = box([0, 0, 7], [10, 10, 2]);          // two slabs, faces 3 mm apart (z = 2 and z = 5)
      const r = P.planeLocus(A.pos, A.idx, B.pos, B.idx, 5, 3000);
      const far = P.planeLocus(A.pos, A.idx, B.pos, B.idx, 2, 3000);                     // gap limit below the 3 mm: no plane
      const zs = r.pts.map(o => o.m[2]);
      console.log(JSON.stringify({n: r.pts.length, minGap: r.minGap, zmin: Math.min(...zs), zmax: Math.max(...zs), farN: far.pts.length,
        mid: r.pts.every(o => Math.abs(P.closestOnMesh(A.pos, A.idx, o.m).d - P.closestOnMesh(B.pos, B.idx, o.m).d) < 1e-6)}));
    """)
    assert out["n"] > 0 and abs(out["minGap"] - 3) < 1e-6
    assert abs(out["zmin"] - 3.5) < 1e-6 and abs(out["zmax"] - 3.5) < 1e-6 and out["mid"]
    assert out["farN"] == 0


def test_size_classes_follow_the_thresholds_and_the_trunk_flag():
    out = node(r"""console.log(JSON.stringify([P.sizeClass(7, 0, [6, 3]), P.sizeClass(6, 0, [6, 3]), P.sizeClass(4, 0, [6, 3]), P.sizeClass(2.9, 0, [6, 3]),
      P.sizeClass(1, 1, [6, 3]), P.sizeClass(null, 0, [6, 3])]))""")
    assert out == ["L", "L", "M", "S", "L", None]


def test_closest_on_mesh():
    out = node(BOX + r"""const A = box([0, 0, 0], [1, 1, 1]); const r = P.closestOnMesh(A.pos, A.idx, [3, 0, 0]); console.log(JSON.stringify(r));""")
    assert abs(out["d"] - 2) < 1e-9 and abs(out["q"][0] - 1) < 1e-9


def test_no_invented_thresholds_and_rules_start_empty():
    js = JS.read_text(encoding="utf-8")
    m = re.search(r"TP\.safeInit = function \(\) \{\n  var S = this\.safe = \{rules: \{\}", js)
    assert m, "the rules must start empty (rule off) -- no cited source gives a distance figure"
    assert 'var SAFE_THR0 = {n: [4, 2], a: [6, 3], v: [6, 3]};' in js          # Q240 calibre levels, labelled a convention on the panel
    assert "מוסכמה" in js and "לא המלצה" in js
    assert 'localStorage.getItem(SAFE_STORE)' in js and 'var SAFE_STORE = "nmsk-inj-safety-v1";' in js


def test_marker_pair_is_one_definition_used_by_both_tools():
    js = JS.read_text(encoding="utf-8")
    us = (REPO / "clinical" / "ultrasound_tool.js").read_text(encoding="utf-8")
    assert 'tip: {color: "#56B4E9"' in js and 'entry: {color: "#E69F00"' in js
    assert "global.NMSKPlanMarkers = {MK: MK, draw2d: drawMk2d}" in js and "G.NMSKPlanMarkers" in us
    assert "addOcta(new Geo(), this.target.p" in js and "addRing(new Geo(), this.entry.p" in js


def test_no_private_words_or_logic_in_public_files():
    bad = ("nmsk-inj-safety", "clinical_vessel_calibre", "planeLocus", "NMSKPlanMarkers", "ultrasound", "hounsfield", "t1_se", "imaging_tissues",
           "tissue table", "nmskultrasound", "acoustic", "mrayl", "b-mode")
    for name in ("atlas_viewer.template.html", "zan_atlas.template.html"):
        low = (REPO / "viewer" / name).read_text(encoding="utf-8").lower()
        for w in bad:
            assert w.lower() not in low, (name, w)
    for f in list((REPO / "viewer").rglob("*.js")) + list((REPO / "viewer").rglob("*.css")):
        low = f.read_text(encoding="utf-8").lower()
        for w in bad:
            assert w.lower() not in low, (f, w)


def test_regen_builds_the_vessel_calibre_for_the_base_pages_and_remove_cleans_it(tmp_path):
    src = (REPO / "scripts" / "regen_template_only.py").read_text(encoding="utf-8")
    i = src.index('run(["python3", "scripts/clinical/build_vessel_calibre_q367.py", p, str(dst)])')
    assert 'if p in ("base_m", "base_f"):' in src[i - 220:i]
    assert src.index("build_injection_guide_q347.py") < i < src.index('(dst / "index.html").write_bytes')
    (tmp_path / "clinical_vessel_calibre.json").write_text("{}")
    scf.remove(tmp_path)
    assert not (tmp_path / "clinical_vessel_calibre.json").exists()


@pytest.mark.parametrize("page,d", [("base_m", "viewer_zan_atlas"), ("base_f", "viewer_base_female")])
def test_vessel_calibre_sibling_contract(page, d, tmp_path):
    src = REPO / "build" / "q309" / d
    if not src.is_dir():
        pytest.skip("build/q309 not present")
    import shutil
    for f in src.glob("atlas_viewer_*"):
        if f.suffix in (".html", ".txt"):
            shutil.copyfile(f, tmp_path / f.name)
    import build_vessel_calibre_q367 as vc
    assert vc.main([page, str(tmp_path)]) == 0
    j = json.loads((tmp_path / vc.NAME).read_text(encoding="utf-8"))
    assert j["schema"] == "nmsk.vessel_calibre.v1" and j["page"] == page and j["n"] == len(j["c"]) > 300
    c = j["c"]
    assert c["abdominal_aorta"][1] == 1 and c["abdominal_aorta"][0] > 12          # a named trunk, flagged, measured large
    radial = [v for k, v in c.items() if re.fullmatch(r"zan_radial_artery_[lr]", k)]
    assert radial and all(v[0] is not None and 1.5 < v[0] < 6 for v in radial)   # textbook 2.5-3.5 mm (q240 CHECKS); a decimated mesh, so a wide band
    assert "PRIVATE" in j["licence"] and "Q240 tube estimator" in j["method"]
