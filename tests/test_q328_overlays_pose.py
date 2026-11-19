"""Q328 -- the needle tool's overlays follow the pose: saved injection points and motor points ride the structure they
belong to through the Q325 anchoring (TP.anchorPoint / TP.ridePoint, no second implementation), only for the structures
in the pose event's ids, and are exactly their given coordinates again at rest. Under node, on synthetic geometry: the
add-on's own Tool prototype run on a minimal stand-in for the tool's state (no DOM)."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(not NODE, reason="node not installed")
SRC = REPO / "clinical" / "needle_tool.js"


def _node(code: str):
    r = subprocess.run([NODE, "-e", code], capture_output=True, text=True, timeout=120, cwd=str(REPO))
    assert r.returncode == 0, r.stderr[-2500:]
    return json.loads(r.stdout.strip().splitlines()[-1])


@needs_node
def test_saved_and_motor_points_ride_the_pose_and_come_back_exactly():
    o = _node(r"""
const fs = require('fs'), vm = require('vm');
const src = fs.readFileSync('clinical/needle_tool.js', 'utf8').replace('global.NMSKClinical = {', 'global.__TP = TP; global.NMSKClinical = {');
const ctx = vm.createContext({console}); vm.runInContext(src, ctx);
const TP = ctx.__TP;
// two closed boxes, 40 x 20 x 10 mm: structure 0 (moves), structure 1 (shifted 100 mm in x, never moves)
const V = [[0,0,0],[40,0,0],[40,20,0],[0,20,0],[0,0,10],[40,0,10],[40,20,10],[0,20,10]];
const F = [[0,2,1],[0,3,2],[4,5,6],[4,6,7],[0,1,5],[0,5,4],[1,2,6],[1,6,5],[2,3,7],[2,7,6],[3,0,4],[3,4,7]];
const idx = Uint16Array.from(F.flat());
const rest = [Float32Array.from(V.flat()), Float32Array.from(V.map(v => [v[0] + 100, v[1], v[2]]).flat())];
const th = Math.PI / 3, c0 = [5, 3, -2], sh = [17, -40, 8];
function rot(p){ const v=[p[0]-c0[0],p[1]-c0[1],p[2]-c0[2]], c=Math.cos(th), s=Math.sin(th);   // 60 deg about z, plus a shift
  return [v[0]*c - v[1]*s + c0[0] + sh[0], v[0]*s + v[1]*c + c0[1] + sh[1], v[2] + c0[2] + sh[2]]; }
const posed0 = new Float32Array(rest[0].length); for (let k=0;k<posed0.length;k+=3) posed0.set(rot([rest[0][k],rest[0][k+1],rest[0][k+2]]), k);
let live = {};
ctx.__poseLive = i => live[i] || null; ctx.__poseRev = 0; ctx.__poseAtRest = true;
const T = Object.create(TP), calls = {plan: 0, saved: 0};
Object.assign(T, {recs: [{id: 'm0', bmin: [0,0,0], bmax: [40,20,10]}, {id: 'm1', bmin: [100,0,0], bmax: [140,20,10]}],
  byId: {m0: [0], m1: [1]}, mpS: new Map(), mpAnc: new Map(), restBox: {}, pgeo: {}, gcache: new Map(), gverts: 0,
  api: {kind: 'webgl', geometry: i => ({pos: rest[i], idx: idx}), redraw(){}},
  savedPts: [], mp: {points: [], on: false}, plan: {zone: null},
  drawPlanMp(){ calls.plan++; }, drawSavedPoint(){ calls.saved++; }});
const mp0 = {structure_id: 'm0', pos: [12.5, 7.25, 3.5]}, mp1 = {structure_id: 'm1', pos: [112.5, 7.25, 3.5]};
const g0 = mp0.pos.slice(), g1 = mp1.pos.slice();
T.mp.points = [mp0, mp1]; T.plan.zone = {mps: [mp0]};
// a saved point: entry on the top face of structure 0, target inside it, anchored as the working plan anchors it
const e = {p: [31, 14, 10], i: 0, n: [0, 0, 1]}, t = {p: [20, 10, 5], i: 0, n: null};
T.anchorPoint(e, 0); T.anchorPoint(t, 0);
const it = {id: 1, entry: {p: e.p.slice(), i: 0, _anc: Object.assign({}, e._anc)}, target: {p: t.p.slice(), i: 0, _anc: Object.assign({}, t._anc)}, L: 0};
it.entry._anc.src = it.entry.p; it.target._anc.src = it.target.p; T.savedPts = [it];
const E0 = it.entry.p.slice(), T0 = it.target.p.slice();
const err = (a,b)=>Math.hypot(a[0]-b[0],a[1]-b[1],a[2]-b[2]);
// pose: structure 0 moves (posed vertices + posed box), 1 does not; the event names only structure 0
live[0] = posed0; ctx.__poseRev = 1; ctx.__poseAtRest = false;
T.restBox[0] = [[0,0,0],[40,20,10]]; T.recs[0].bmin = [-1e3,-1e3,-1e3]; T.recs[0].bmax = [-999,-999,-999];   // a posed box far from the rest point
const shown = T.poseOverlays([0]);
const posed = {shown, mp0: err(mp0.pos, rot(g0)), mp1Same: mp1.pos.every((v,k)=>v===g1[k]), entry: err(it.entry.p, rot(E0)), target: err(it.target.p, rot(T0)),
               L: Math.abs(it.L - err(E0, T0)), plan: calls.plan, saved: calls.saved, sOf: T.mpStructure(mp0)};
// an event that names only structure 1: nothing of structure 0 is re-derived
calls.plan = 0; const p0 = mp0.pos; ctx.__poseRev = 2; const none = T.poseOverlays([1]);
const other = {shown: none, plan: calls.plan, same: mp0.pos === p0};
// back at rest: the given / placed coordinates, exactly
live[0] = Float32Array.from(rest[0]); ctx.__poseRev = 3; ctx.__poseAtRest = true;
T.poseOverlays([0]);
const back = {mp0: mp0.pos.every((v,k)=>v===g0[k]), entry: it.entry.p.every((v,k)=>v===E0[k]), target: it.target.p.every((v,k)=>v===T0[k])};
console.log(JSON.stringify({posed, other, back}));
""")
    p, oth, b = o["posed"], o["other"], o["back"]
    assert p["shown"] and p["plan"] == 1 and p["saved"] == 1, o
    assert p["mp0"] < 1e-4, "a motor point inside a rigidly moved muscle must ride it exactly"
    assert p["mp1Same"], "a motor point of a structure the event does not name must not move"
    assert p["entry"] < 1e-4 and p["target"] < 1e-4 and p["L"] < 1e-4, o
    assert p["sOf"] == 0, "the motor point's structure is decided on the rest box, not the posed one"
    assert not oth["shown"] and oth["plan"] == 0 and oth["same"], o
    assert b["mp0"] and b["entry"] and b["target"], f"back at rest the points must be exactly where they were given: {b}"


def test_one_anchoring_implementation_and_notes_updated():
    s = SRC.read_text(encoding="utf-8")
    body = s[s.index("TP.poseOverlays = function"):]
    body = body[:body.index("\n};") + 3]
    assert "anchorPoint(" in body and "ridePoint(" in body and "poseAnchor(" not in body, "Q328 must reuse the Q325 anchoring"
    assert s.count("function poseAnchor(") == 1 and s.count("function poseAnchorPlace(") == 1
    assert "do not follow the pose" not in s and "rest-pose data" not in s
    assert re.search(r"this\.poseOverlays\(ids\)", s), "the pose event must re-derive the overlays"
