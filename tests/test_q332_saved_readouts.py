"""Q332 -- a saved injection point's readout (nearest vessel / nerve, its distance) is measured again on the posed geometry
when a pose event moves the point's own structure or a vessel / nerve within the measurement's reach, once per burst of
pose events (onPose's 160 ms timer), with the same corridorFor() call the save used; an event that touches nothing within
reach leaves it alone; back at rest the readout is the saved one exactly. Under node, on synthetic box meshes, checked
against the analytic point-to-box distance."""
from __future__ import annotations

import json
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
def test_saved_readout_is_remeasured_on_the_pose_once_per_burst_and_exact_at_rest():
    o = _node(r"""
const fs = require('fs'), vm = require('vm');
const src = fs.readFileSync('clinical/needle_tool.js', 'utf8').replace('global.NMSKClinical = {', 'global.__TP = TP; global.NMSKClinical = {');
const timers = [];
const ctx = vm.createContext({console, performance, setTimeout: f => timers.push(f), clearTimeout: id => { if (id) timers[id - 1] = null; }});
vm.runInContext(src, ctx);
const TP = ctx.__TP;
const box = (lo, hi) => [[lo[0],lo[1],lo[2]],[hi[0],lo[1],lo[2]],[hi[0],hi[1],lo[2]],[lo[0],hi[1],lo[2]],[lo[0],lo[1],hi[2]],[hi[0],lo[1],hi[2]],[hi[0],hi[1],hi[2]],[lo[0],hi[1],hi[2]]];
const F = [[0,2,1],[0,3,2],[4,5,6],[4,6,7],[0,1,5],[0,5,4],[1,2,6],[1,6,5],[2,3,7],[2,7,6],[3,0,4],[3,4,7]], idx = Uint16Array.from(F.flat());
const B = [[[0,0,0],[40,20,10]], [[0,30,0],[40,36,10]], [[500,0,0],[540,6,10]]];   // 0 muscle, 1 artery 20 mm from the point, 2 artery far away
const rest = B.map(b => Float32Array.from(box(b[0], b[1]).flat()));
const shift = (i, d) => Float32Array.from(rest[i].map((v, k) => v + d[k % 3]));
let live = {};
ctx.__poseLive = i => live[i] || null; ctx.__poseRev = 0; ctx.__poseAtRest = true;
const T = Object.create(TP); let calls = 0, drawn = 0, notes = 0;
Object.assign(T, {recs: B.map((b, i) => ({i, id: 's' + i, name: 'S' + i, bmin: b[0].slice(), bmax: b[1].slice()})), cls: ['muscle', 'artery', 'artery'],
  byId: {s0: [0], s1: [1], s2: [2]}, mpS: new Map(), mpAnc: new Map(), restBox: {}, pgeo: {}, gcache: new Map(), gverts: 0,
  api: {kind: 'webgl', geometry: i => ({pos: rest[i], idx: idx}), redraw(){}}, hooks: [() => notes++],
  corr: {R: 30, near: 5, far: 15}, risk: {on: false}, sugg: {cands: [], shown: []}, savedPts: [], mp: {points: [], on: false}, plan: {zone: null},
  entry: null, target: {p: [20, 10, 5], i: 0, n: null}, drawSavedPoint(){ drawn++; }, drawNeedle(){}, render(){}});
const cf = T.corridorFor; T.corridorFor = function () { calls++; return cf.apply(this, arguments); };
const it = T.addSavedPoint(); T.target = null;   // a target-only saved point inside structure 0; the working plan is cleared
const boxD = (p, b) => Math.hypot(...[0,1,2].map(k => Math.max(b[0][k] - p[k], 0, p[k] - b[1][k])));
const d = () => (it.corr.items.find(x => x.id === 's1') || {d: null}).d;
const flush = () => { const f = timers.filter(Boolean); timers.length = 0; f.forEach(g => g()); };
const out = {saved: d(), savedCalls: calls}; calls = 0;
// pose A, a burst of three events moving structure 0 (+6 mm, then +8 mm in y): one re-measure, after the burst
ctx.__poseAtRest = false;
[[0, 3, 0], [0, 6, 0], [0, 8, 0]].forEach((s, k) => { live[0] = shift(0, s); ctx.__poseRev = k + 1; T.onPose({ids: [0]}); });
out.beforeTimer = {calls, d: d()}; flush();
out.A = {calls, d: d(), expect: boxD(it.target.p, B[1]), moved: it.target.p[1] - 10, key: it.corrKey}; calls = 0;
// pose B: only the artery moves (5 mm closer) -- within reach, so measured again although the point did not move
live[1] = shift(1, [0, -5, 0]); ctx.__poseRev = 4; T.onPose({ids: [1]}); flush();
out.B = {calls, d: d(), expect: boxD(it.target.p, [[0,25,0],[40,31,10]])}; calls = 0;
// pose C: only the far artery moves -- nothing within reach, the readout is kept
live[2] = shift(2, [0, 3, 0]); ctx.__poseRev = 5; T.onPose({ids: [2]}); flush();
out.C = {calls, d: d()};
// back at rest
live = {}; ctx.__poseRev = 6; ctx.__poseAtRest = true; T.onPose({ids: [0, 1, 2]}); flush();
out.back = {calls, same: it.corr === it.corr0, d: d(), key: it.corrKey, p: it.target.p.slice()};
out.drawn = drawn; out.notes = notes;
console.log(JSON.stringify(out));
""")
    assert abs(o["saved"] - 20) < 1e-6 and o["savedCalls"] == 1, o
    assert o["beforeTimer"]["calls"] == 0 and abs(o["beforeTimer"]["d"] - 20) < 1e-6, "nothing is measured inside the burst"
    a = o["A"]
    assert a["calls"] == 1 and abs(a["moved"] - 8) < 1e-4 and abs(a["d"] - a["expect"]) < 1e-4 and abs(a["d"] - 12) < 1e-4, o
    assert a["key"] != "rest", o
    b = o["B"]
    assert b["calls"] == 1 and abs(b["d"] - b["expect"]) < 1e-4 and abs(b["d"] - 7) < 1e-4, o
    assert o["C"]["calls"] == 0 and abs(o["C"]["d"] - 7) < 1e-4, "an event with nothing within reach must not re-measure"
    bk = o["back"]
    assert bk["same"] and bk["d"] == 20 and bk["key"] == "rest" and bk["calls"] == 0 and bk["p"] == [20, 10, 5], o
    assert o["drawn"] >= 4 and o["notes"] >= 3, o


def test_remeasure_reuses_corridorFor_and_the_region_follows_the_pose():
    s = SRC.read_text(encoding="utf-8")
    body = s[s.index("TP.remeasureSaved = function"):]
    body = body[:body.index("\n};") + 3]
    assert "self.corridorFor(" in body and "meshSegDist" not in body, "one minimum-distance implementation"
    assert s.count("function meshSegDist(") == 1
    assert "R0.pk === pk" in s, "the risk region cache must be keyed by the pose"
    assert "this.restBox[i] || [R.bmin, R.bmax]" in s, "the fallback calibre must come from the rest box"
    assert "self.poseRerun()" in s and "current pose" in s[s.index("TP.renderSavedPoints"):]
