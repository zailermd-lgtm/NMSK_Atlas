"""Q381: a planned needle path never crosses bone, and the tip's default point lies inside its structure -- the pure geometry
(clinical/needle_tool.js: segMeshHits, meshInside, meshCentre), checked in node against independent numpy computations, plus the
source-level contract of the rule (one test, reused; hyaline cartilage blocks, fibrocartilage and ligaments do not).
The browser behaviour is checked by scripts/anatomy/q381/verify_plan_q381.py."""
from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
JS = REPO / "clinical" / "needle_tool.js"
SRC = JS.read_text(encoding="utf-8")


def node(code: str, stdin: str = ""):
    r = subprocess.run(["node", "-e", "const P = require(" + json.dumps(str(JS)) + ");\n" + code], input=stdin, capture_output=True, text=True, timeout=180)
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


SHAPES = r"""
function box(c, h) {   // an axis-aligned closed box centred c, half sizes h: 8 vertices, 12 outward triangles
  const v = [], f = [[0,2,1],[0,3,2],[4,5,6],[4,6,7],[0,1,5],[0,5,4],[2,3,7],[2,7,6],[1,2,6],[1,6,5],[0,4,7],[0,7,3]];
  for (const [x, y, z] of [[-1,-1,-1],[1,-1,-1],[1,1,-1],[-1,1,-1],[-1,-1,1],[1,-1,1],[1,1,1],[-1,1,1]]) v.push(c[0]+x*h[0], c[1]+y*h[1], c[2]+z*h[2]);
  return {pos: Float32Array.from(v), idx: Uint16Array.from(f.flat())};
}
function tube(path, r, seg) {   // a closed tube of radius r around a polyline (rings + two caps), outward triangles
  const pos = [], idx = [], n = path.length, sub = (a, b) => [a[0]-b[0], a[1]-b[1], a[2]-b[2]], nrm = a => { const l = Math.hypot(...a) || 1; return a.map(x => x / l); };
  const cross = (a, b) => [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]];
  for (let k = 0; k < n; k++) {
    const t = nrm(sub(path[Math.min(n - 1, k + 1)], path[Math.max(0, k - 1)])), e1 = nrm(cross(t, [0, 0, 1])), e2 = cross(t, e1);
    for (let j = 0; j < seg; j++) { const a = 2 * Math.PI * j / seg; pos.push(...[0, 1, 2].map(q => path[k][q] + r * (Math.cos(a) * e1[q] + Math.sin(a) * e2[q]))); }
  }
  for (let k = 0; k + 1 < n; k++) for (let j = 0; j < seg; j++) { const a = k * seg + j, b = k * seg + (j + 1) % seg, c = a + seg, d = b + seg; idx.push(a, c, b, b, c, d); }
  const c0 = pos.length / 3; pos.push(...path[0]); const c1 = c0 + 1; pos.push(...path[n - 1]);
  for (let j = 0; j < seg; j++) { idx.push(c0, j, (j + 1) % seg); idx.push(c1, (n - 1) * seg + (j + 1) % seg, (n - 1) * seg + j); }
  return {pos: Float32Array.from(pos), idx: Uint16Array.from(idx)};
}
"""


def tri_hits(pos, idx, A, B):
    """independent: segment vs triangles (numpy Moller-Trumbore), parameters in mm from A"""
    V = np.asarray(pos, float).reshape(-1, 3); F = np.asarray(idx).reshape(-1, 3)
    A = np.asarray(A, float); B = np.asarray(B, float); L = np.linalg.norm(B - A); d = (B - A) / L
    a = V[F[:, 0]]; e1 = V[F[:, 1]] - a; e2 = V[F[:, 2]] - a
    p = np.cross(d, e2); det = (e1 * p).sum(1); ok = np.abs(det) > 1e-12
    inv = np.where(ok, 1 / np.where(ok, det, 1), 0); s = A - a; u = (s * p).sum(1) * inv
    q = np.cross(s, e1); v = (q @ d) * inv; t = (e2 * q).sum(1) * inv
    m = ok & (u >= 0) & (v >= 0) & (u + v <= 1) & (t >= 0) & (t <= L)
    return sorted(float(x) for x in t[m])


def test_segment_through_beside_and_onto_a_bone_box():
    out = node(SHAPES + r"""
      const bone = box([0, 0, 0], [10, 40, 10]);
      const through = P.segMeshHits(bone.pos, bone.idx, [-30, 5, 1], [30, 5, 1]);       // crosses both faces
      const beside = P.segMeshHits(bone.pos, bone.idx, [-30, 5, 15], [30, 5, 15]);       // passes 5 mm above it
      const onto = P.segMeshHits(bone.pos, bone.idx, [-30, 5, 1], [-10, 5, 1]);          // the tip rests ON the near face
      const into = P.segMeshHits(bone.pos, bone.idx, [-30, 5, 1], [0, 5, 1]);            // the tip inside the bone
      const short = P.segMeshHits(bone.pos, bone.idx, [-30, 5, 1], [-12, 5, 1]);         // stops 2 mm before it
      const from_behind = P.segMeshHits(bone.pos, bone.idx, [30, 5, 1], [-10, 5, 1]);    // reaches the same surface point through the bone
      const t = a => a.map(h => +h.t.toFixed(6));
      console.log(JSON.stringify({through: t(through), beside: t(beside), onto: t(onto), into: t(into), short: t(short), from_behind: t(from_behind)}));
    """)
    assert out["through"] == [20, 40] and out["beside"] == [] and out["short"] == []
    assert out["onto"] == [20] and out["into"] == [20]              # a touch at the tip is reported at t = L; the caller decides
    assert out["from_behind"] == [20, 40]                            # the surface point from behind: a crossing 20 mm before the tip


def test_segment_hits_agree_with_numpy_on_a_curved_mesh():
    rng = np.random.default_rng(381)
    segs = [[list(map(float, rng.uniform(-60, 60, 3))), list(map(float, rng.uniform(-60, 60, 3)))] for _ in range(120)]
    out = node(SHAPES + r"""
      const path = []; for (let k = 0; k <= 40; k++) { const a = Math.PI * k / 40; path.push([40 * Math.cos(a), 40 * Math.sin(a) - 20, 6 * Math.sin(3 * a)]); }
      const m = tube(path, 9, 14), segs = JSON.parse(require('fs').readFileSync(0, 'utf8'));
      console.log(JSON.stringify({pos: Array.from(m.pos), idx: Array.from(m.idx), hits: segs.map(s => P.segMeshHits(m.pos, m.idx, s[0], s[1]).map(h => h.t))}));
    """, json.dumps(segs))
    n_hit = 0
    for s, got in zip(segs, out["hits"]):
        want = tri_hits(out["pos"], out["idx"], s[0], s[1])
        assert len(got) == len(want), (s, got, want)
        assert all(abs(a - b) < 1e-4 for a, b in zip(got, want))
        n_hit += bool(want)
    assert n_hit >= 20                                               # the sample really exercises crossings


def test_mesh_centre_is_inside_where_the_vertex_mean_is_not():
    out = node(SHAPES + r"""
      // a banana: a tube along a half circle (radius 40) -- its vertex mean lies in the hollow of the arc, outside the mesh
      const path = []; for (let k = 0; k <= 40; k++) { const a = Math.PI * k / 40; path.push([40 * Math.cos(a), 40 * Math.sin(a), 0]); }
      const m = tube(path, 8, 16), n = m.pos.length / 3, mean = [0, 0, 0];
      for (let v = 0; v < n; v++) for (let k = 0; k < 3; k++) mean[k] += m.pos[3 * v + k] / n;
      const c = P.meshCentre(m.pos, m.idx), again = P.meshCentre(m.pos, m.idx);
      // a belly with a long thin tendon: the centre goes to the belly, not to the tendon
      const bt = []; for (let k = 0; k <= 30; k++) bt.push([0, -3 * k, 0]);
      const belly = tube([[0, 60, 0], [0, 45, 0], [0, 30, 0], [0, 15, 0], [0, 0, 0]], 14, 16), tend = tube(bt, 2, 10);
      const pos = Array.from(belly.pos).concat(Array.from(tend.pos)), off = belly.pos.length / 3, idx = Array.from(belly.idx).concat(Array.from(tend.idx).map(i => i + off));
      const two = {pos: Float32Array.from(pos), idx: Uint16Array.from(idx)}, c2 = P.meshCentre(two.pos, two.idx);
      // rejected candidates are never returned
      const c3 = P.meshCentre(m.pos, m.idx, {reject: p => p[0] > 0});
      // an open sheet has no inside: said so
      const sheet = {pos: Float32Array.from([0,0,0, 10,0,0, 10,10,0, 0,10,0]), idx: Uint16Array.from([0,1,2, 0,2,3])}, c4 = P.meshCentre(sheet.pos, sheet.idx);
      console.log(JSON.stringify({mean, meanIn: P.meshInside(m.pos, m.idx, mean), meanD: P.closestOnMesh(m.pos, m.idx, mean).d,
        c, cIn: P.meshInside(m.pos, m.idx, c.p), cD: P.closestOnMesh(m.pos, m.idx, c.p).d, same: JSON.stringify(c) === JSON.stringify(again),
        c2, c3x: c3.p[0], c3in: c3.inside, c4}));
    """)
    assert not out["meanIn"] and out["meanD"] > 5                    # the old default: outside the banana
    assert out["c"]["inside"] and out["cIn"] and out["same"]
    assert abs(out["cD"] - out["c"]["r"]) < 1e-6 and 6.5 < out["c"]["r"] <= 8.01   # mid-thickness of a radius-8 tube
    assert abs(np.hypot(out["c"]["p"][0], out["c"]["p"][1]) - 40) < 1.5 and abs(out["c"]["p"][2]) < 1.5   # on the tube's axis
    assert out["c2"]["inside"] and out["c2"]["p"][1] > 5 and out["c2"]["r"] > 10                             # in the belly (radius 14), not the tendon
    assert out["c3in"] and out["c3x"] <= 0
    assert out["c4"]["inside"] is False and out["c4"]["r"] == 0


def test_one_bone_rule_reused_and_what_blocks():
    # the blocking set: the bone class and the cartilage layer's HYALINE pieces; fibrocartilage and ligaments are not in it
    m = re.search(r"var HYALINE_RE = /([^/]+)/;", SRC)
    assert m
    hy = re.compile(m.group(1))
    for i in ("knee_articular_cartilage_l", "hip_articular_cartilage_r", "costal_cartilage_r", "zan_costal_cartilage_of_first_rib_l", "zan_triradiate_cartilage_l"):
        assert hy.search(i), i
    for i in ("medial_meniscus_l", "intervertebral_disc_l4_l5", "acetabular_labrum_r", "glenoid_labrum_l", "pubic_symphysis_disc", "zan_interosseous_membrane_of_leg_l"):
        assert not hy.search(i), i
    assert 'self.cls[i] === "bone" || (r.cat === "cartilage" && HYALINE_RE.test(r.id))' in SRC
    # every way a path is made goes through the one test: the placement update, the suggestions, the shortest entry, the offered entry
    assert re.search(r"TP\.update = function \(\) \{.*?this\.blockRun\(\);", SRC, re.S)
    sug = SRC[SRC.index("TP.suggest = function"):SRC.index("TP.clearSuggestions = function")]
    assert sug.count("boneFreeRay") >= 2 and "self.boneCheck(en.E, T).blocked" in sug
    sh = SRC[SRC.index("TP.shortestEntry = function"):SRC.index("TP.isCorrStruct = function")]
    assert "boneFreeRay" in sh and "boneCheck" in sh
    near = SRC[SRC.index("TP.entryNear = function"):SRC.index("TP.blockRun = function")]
    assert "pathValid" in near and "none: true" in near
    assert "var bone = gather(this.blockers());" in SRC               # the search grid holds the same set
    # ligaments / membranes are listed, never blocking; no invented safety figure
    assert re.search(r"var PASS_CATS = \{joint: 1, ligament: 1, cartilage: 1\};", SRC)
    assert "var SAFE_THR0 = {n: [4, 2], a: [6, 3], v: [6, 3]};" in SRC and "S.rules = {}" in SRC


def test_default_tip_is_the_inside_centre_on_the_current_mesh():
    st = SRC[SRC.index("TP.setTargetAt = function"):SRC.index("Q347: the INJECTION GUIDE")]
    assert "this.centreOf(i)" in st and "this.api.geometry(i)" not in st      # not the mean of the REST vertices any more
    co = SRC[SRC.index("TP.centreOf = function"):SRC.index("TP.plCentreFollow = function")]
    assert "this.geom(i)" in co and "meshCentre(" in co and "insideMesh(j, p)" in co
    assert "self.plCentreFollow();" in SRC[SRC.index("TP.onPose = function"):SRC.index("TP.savedReach = function")]


def test_skin_looks_use_engine_state_and_are_put_back():
    t = (REPO / "viewer" / "zan_atlas.template.html").read_text(encoding="utf-8")
    assert "setCategoryAlpha:function(k,a)" in t and "setCategoryPlain:function(k,v)" in t and "categoryAlpha:function(k)" in t
    assert 'selCtl && !plainLayer[o.layer] ? selCtl.look(o.id) : ""' in t          # a plain layer is drawn as the layers say
    assert "skinOk = !!(skinCat && api.setCategoryAlpha && api.categoryAlpha && api.setCategoryPlain)" in SRC   # an engine without the API: no control
    ex = SRC[SRC.index("  function exit() {"):SRC.index("  function reset() {")]
    assert "api.setCategoryPlain(skinCat, false); api.setCategoryOn(skinCat, skin0.on); api.setCategoryAlpha(skinCat, skin0.a);" in ex
    assert 'NMSKHistory.register("inj_skin"' in SRC                                # the look travels with the page-wide undo


def test_safety_has_no_built_in_default():
    # the default is the set the user declares; nothing is pre-filled
    assert "S.def = SAFE_ROWS.some(" in SRC and "TP.safeState = function" in SRC
    init = SRC[SRC.index("TP.safeInit = function"):SRC.index("TP.safeSave = function")]
    assert "rules: {}" in init and not re.search(r"rules: \{[a-zA-Z]", init)
