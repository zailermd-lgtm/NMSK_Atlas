"""Q325 -- the injection clip: the needle tool's pose anchoring (clinical/needle_tool.js poseAnchor / poseAnchorPlace) and the
scan tool's alignment of its plane on a planned needle (clinical/ultrasound_tool.js clipAlign), under node on synthetic geometry.

* an anchored point is reproduced exactly on the mesh it was taken from, rides a rigidly moved mesh exactly (also a point
  off the surface, inside the structure), and its anchored direction turns with the mesh;
* "Show in scan", in plane: the probe sits on the skin beside the entry, and the scan plane holds both ends of the path;
  out of plane: the plane holds the target and not the entry;
* the needle never enters the raster key (only the frame's sig), so a playing clip reuses the anatomy raster, while the
  pose term stays in it; the public templates carry nothing of this."""
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


def _node(code: str):
    r = subprocess.run([NODE, "-e", code], capture_output=True, text=True, timeout=120, cwd=str(REPO))
    assert r.returncode == 0, r.stderr[-2500:]
    return json.loads(r.stdout.strip().splitlines()[-1])


@needs_node
def test_pose_anchor_rides_a_rigid_motion_exactly():
    o = _node(r"""
const P = require('./clinical/needle_tool.js');
// a closed box mesh, 40 x 20 x 10 mm, 12 triangles
const V = [[0,0,0],[40,0,0],[40,20,0],[0,20,0],[0,0,10],[40,0,10],[40,20,10],[0,20,10]];
const F = [[0,2,1],[0,3,2],[4,5,6],[4,6,7],[0,1,5],[0,5,4],[1,2,6],[1,6,5],[2,3,7],[2,7,6],[3,0,4],[3,4,7]];
const pos = Float32Array.from(V.flat()), idx = Uint16Array.from(F.flat());
const inside = [12.5, 7.25, 3.5], onTop = [31.0, 14.0, 10.0], nTop = [0, 0, 1];
const aI = P.poseAnchor(pos, idx, inside, null), aS = P.poseAnchor(pos, idx, onTop, nTop);
const same = P.poseAnchorPlace(pos, idx, aI).p, sameS = P.poseAnchorPlace(pos, idx, aS);
// rigid motion: 60 deg about an axis through (5, 3, -2), plus a shift
const th = Math.PI / 3, ax = (()=>{const a=[0.3,1,0.2], l=Math.hypot(...a); return a.map(x=>x/l);})(), c0 = [5, 3, -2], sh = [17, -40, 8];
function rot(p){ const v=[p[0]-c0[0],p[1]-c0[1],p[2]-c0[2]], c=Math.cos(th), s=Math.sin(th), d=ax[0]*v[0]+ax[1]*v[1]+ax[2]*v[2];
  const k=[ax[1]*v[2]-ax[2]*v[1], ax[2]*v[0]-ax[0]*v[2], ax[0]*v[1]-ax[1]*v[0]];
  return [0,1,2].map(i=>v[i]*c+k[i]*s+ax[i]*d*(1-c)+c0[i]+sh[i]); }
function rotDir(n){ const z=rot([0,0,0]), q=rot(n); return [q[0]-z[0],q[1]-z[1],q[2]-z[2]]; }
const pos2 = new Float64Array(pos.length); for (let k=0;k<pos.length;k+=3){ const q=rot([pos[k],pos[k+1],pos[k+2]]); pos2.set(q,k); }
const mI = P.poseAnchorPlace(pos2, idx, aI).p, mS = P.poseAnchorPlace(pos2, idx, aS);
const err = (a,b)=>Math.hypot(a[0]-b[0],a[1]-b[1],a[2]-b[2]);
console.log(JSON.stringify({restI: err(same, inside), restS: err(sameS.p, onTop), restN: err(sameS.n, nTop),
  movedI: err(mI, rot(inside)), movedS: err(mS.p, rot(onTop)), movedN: err(mS.n, rotDir(nTop)), dI: aI.d, dS: aS.d}));
""")
    assert o["restI"] < 1e-5 and o["restS"] < 1e-5 and o["restN"] < 1e-6, o      # float32 mesh: sub-micrometre
    assert o["movedI"] < 1e-4, "a point inside the structure must ride a rigid motion exactly"
    assert o["movedS"] < 1e-4 and o["movedN"] < 1e-6, "a surface point and its normal must ride it too"
    assert o["dS"] < 1e-6 and o["dI"] > 1, o


def _clip_align_src():
    src = (REPO / "clinical" / "ultrasound_tool.js").read_text()
    a, b = src.index("    function clipAlign(path) {"), src.index("    function clipNeedleAt(t) {")
    return src[a:b]


@needs_node
@pytest.mark.parametrize("oop", [False, True])
def test_show_in_scan_plane_holds_the_needle(oop):
    code = r"""
require('./clinical/ultrasound_tool.js'); const L = globalThis.NMSKUltrasoundLib;
// a flat, tilted skin (normal n0 through the origin): skinHit = ray / plane, smoothNormal = n0
const n0 = L.unit([0.2, 0.1, 1]);
const LIB = Object.assign({}, L, {
  skinHit: (g, o, d) => { const den = L.dot(d, n0); if (Math.abs(den) < 1e-9) return null; const t = -L.dot(o, n0) / den; return t > 0 ? {t, point: [o[0]+d[0]*t, o[1]+d[1]*t, o[2]+d[2]*t], struct: 0} : null; },
  smoothNormal: () => n0.slice()});
const sub=(a,b)=>[a[0]-b[0],a[1]-b[1],a[2]-b[2]], add=(a,b)=>[a[0]+b[0],a[1]+b[1],a[2]+b[2]], mul=(a,s)=>[a[0]*s,a[1]*s,a[2]*s], dot=L.dot, len=a=>Math.hypot(a[0],a[1],a[2]);
const S = {ab:false, cine:false, rot:0, mTilt:5, mTiltDir:0, mode:'sweep', view:'matrix', sel:3, depthCm:4, focusCm:2};
const clip = {oop: OOP}, axisCache = {}, DEG = Math.PI/180;
const f = new Function('geo','LIB','S','clip','sub','add','mul','dot','len','orientRef','probeW','cutKeep','setAb','setCine','DEG','axisCache', SRC + '; return clipAlign;');
const clipAlign = f({}, LIB, S, clip, sub, add, mul, dot, len, ()=>L.REF.long, ()=>44, ()=>null, ()=>{}, ()=>{}, DEG, axisCache);
// entry on the skin, target 25 mm deep, needle about 45 deg to the skin
const E = [3, -4, -(0.2*3 + 0.1*-4)], T = add(add(E, mul(n0, -25)), [22, 9, 0]);
const ok = clipAlign({A: E, B: T});
const fr = L.probeFrame(S.N, L.REF.long, S.rot, S.mTilt, S.mTiltDir), e = fr.e;
const xE = dot(sub(E, S.P), fr.u), xT = dot(sub(T, S.P), fr.u), yT = dot(sub(T, S.P), fr.b);
console.log(JSON.stringify({ok, onSkin: Math.abs(dot(S.P, n0)), eA: dot(sub(E, S.P), e), eB: dot(sub(T, S.P), e), xE, xT, yT,
  depthCm: S.depthCm, mode: S.mode, view: S.view, mTilt: S.mTilt, sel: S.sel}));
""".replace("OOP", "true" if oop else "false").replace("SRC", json.dumps(_clip_align_src()))
    o = _node(code)
    assert o["ok"] and o["onSkin"] < 1e-9, o
    assert o["mode"] == "star" and o["view"] == "single" and o["mTilt"] == 0 and o["sel"] == 0, "the clip's own single, untilted frame"
    assert o["yT"] > 0 and o["depthCm"] * 10 >= o["yT"], "the target lies below the probe face, inside the image depth"
    if not oop:
        assert abs(o["eA"]) < 1e-9 and abs(o["eB"]) < 1e-9, "in plane: the scan plane must hold both ends of the path"
        assert o["xE"] <= -22, "the entry is beside the probe (at or beyond the footprint's edge), not under it"
        assert o["xT"] > o["xE"], "the needle comes in from the image's left"
    else:
        assert abs(o["eB"]) < 1e-9, "out of plane: the plane holds the target"
        assert abs(o["eA"]) > 5, "and not the entry"
        assert abs(o["xT"]) < 1e-9, "the probe is centred over the target"


def test_needle_is_in_the_frame_sig_not_the_raster_key():
    src = (REPO / "clinical" / "ultrasound_tool.js").read_text()
    rk = re.search(r"\n    function rasterKey\(spec, q\) \{(.*)\n", src).group(1)
    assert "needle" not in rk and "clip" not in rk and "poseTerm()" in rk, "the label raster is shared while only the needle moves; the pose stays in the key"
    sig = re.search(r"fr\.sig = \[(.*)\]\.join", src).group(1)
    assert "needleSig()" in sig
    assert "if (clip.on) return [{id: 0" in src, "a playing clip makes one image, not the nine of the tilt star"
    assert "if (busy || pumpPending) { clip.timer" in src, "a clip frame is asked for only when the previous one is done"


def test_public_templates_stay_neutral():
    for t in ("viewer/zan_atlas.template.html", "viewer/atlas_viewer.template.html"):
        s = (REPO / t).read_text().lower()
        for w in ("needleclip", "scanpath", "clipalign", "us-clip"):
            assert w not in s, (t, w)
