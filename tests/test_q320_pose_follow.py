"""Q320 -- the probe image follows the joint pose: the slicing kernel's posed set (clinical/imaging_tool.js setPose + R.posed) and the
probe tool's pose sync / raster key (clinical/ultrasound_tool.js syncPose, rasterKey), on synthetic meshes under node.
A posed slice must differ, a slice back at rest must be byte-identical to the rest slice, and the raster key must carry a pose term
that disappears again at rest. The public templates only carry the neutral pose revision (__poseRev / "nmsk-pose-rev")."""
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
    r = subprocess.run([NODE, "-e", code], capture_output=True, text=True, timeout=240, cwd=str(REPO))
    assert r.returncode == 0, r.stderr[-2500:]
    return json.loads(r.stdout.strip().splitlines()[-1])


@needs_node
def test_kernel_posed_slice_differs_and_rest_is_byte_identical():
    o = _node(r"""
require('./clinical/imaging_tool.js'); const L=globalThis.NMSKImagingLib;
const C=L.compileTable(require('./clinical/data/imaging_tissues.json'));
function cyl(r,y0,y1,n,cx){const p=[],ix=[];for(let i=0;i<n;i++){const a=2*Math.PI*i/n;p.push(cx+r*Math.cos(a),y0,r*Math.sin(a),cx+r*Math.cos(a),y1,r*Math.sin(a));}
  p.push(cx,y0,0,cx,y1,0);const c0=2*n,c1=c0+1;for(let i=0;i<n;i++){const j=(i+1)%n,a=2*i,b=2*i+1,c=2*j,d=2*j+1;ix.push(a,c,b,b,c,d,c0,c,a,c1,b,d);}return {pos:Float32Array.from(p),idx:Uint32Array.from(ix)};}
const parts=[{g:cyl(100,-50,50,96,0),cls:C.ids.skin,skin:1},{g:cyl(15,-30,30,64,-20),cls:C.by.muscle._i}];
let nv=0,nt=0;parts.forEach(p=>{nv+=p.g.pos.length/3;nt+=p.g.idx.length/3});
const pos=new Float32Array(nv*3),idx=new Uint32Array(nt*3),vS=new Uint32Array(3),tS=new Uint32Array(3),bb=new Float32Array(12);let vo=0,to=0;
parts.forEach((p,i)=>{vS[i]=vo;tS[i]=to;pos.set(p.g.pos,vo*3);for(let q=0;q<p.g.idx.length;q++)idx[to*3+q]=p.g.idx[q]+vo;const mn=[1e9,1e9,1e9],mx=[-1e9,-1e9,-1e9];
  for(let q=0;q<p.g.pos.length;q+=3)for(let a=0;a<3;a++){mn[a]=Math.min(mn[a],p.g.pos[q+a]);mx[a]=Math.max(mx[a],p.g.pos[q+a]);}bb.set([...mn,...mx],i*6);vo+=p.g.pos.length/3;to+=p.g.idx.length/3;});
vS[2]=vo;tS[2]=to;
const Kn=L.KERNEL_FACTORY();Kn.setGeometry({n:2,pos,idx,vStart:vS,tStart:tS,bbox:bb,cls:Uint8Array.from([C.ids.skin,C.by.muscle._i]),kind:new Uint8Array(2),skin:Uint8Array.from([1,0]),render:new Uint8Array(2),order:Uint32Array.from([1]),skinList:Uint32Array.from([0])});
const restMuscle=pos.slice(vS[1]*3,vS[2]*3);
const bone={};let seq=0;const b=L.basis([0,-1,0]);
function sl(posed){return Kn.slice({key:'k'+(++seq),W:96,H:96,O:[0,0,0],u:b.u,v:b.v,n:b.n,u0:-120,v0:120,px:2.5,smin:0,smax:0,s:0,wantSid:true,skinMm:1.8,ids:C.ids,bone,posed:posed?1:0}).lab;}
function h(a){let x=2166136261>>>0;const u=new Uint8Array(a.buffer,a.byteOffset,a.byteLength);for(const c of u){x^=c;x=Math.imul(x,16777619)>>>0;}return x;}
const r0=h(sl(0));
const live=restMuscle.slice();for(let k=0;k<live.length;k+=3)live[k]+=45;           // the muscle "moved" 45 mm
Kn.setPose({ids:[1],live:[live],rest:[null]},true);
const p1=h(sl(1)), r1=h(sl(0)), p2=h(sl(1));
console.log(JSON.stringify({r0,p1,r1,p2,pkgUntouched:h(pos.slice(vS[1]*3,vS[2]*3))===h(restMuscle)}));
""")
    assert o["p1"] != o["r0"], "the posed slice must differ from the rest slice"
    assert o["r1"] == o["r0"], "a slice back at rest must reproduce the rest slice byte for byte"
    assert o["p2"] == o["p1"], "posed -> rest -> posed must give the same posed slice"
    assert o["pkgUntouched"], "the main-thread kernel must not write into the page's shared package"


def _q320_block():
    src = (REPO / "clinical" / "ultrasound_tool.js").read_text()
    a, b = src.index("    var geoR = null, poseU"), src.index("    function axisOf(sid) {")
    rk = re.search(r"\n    function rasterKey\(spec, q\) \{.*\n", src).group(0)
    return src[a:b] + rk


@needs_node
def test_raster_key_carries_the_pose_and_returns_to_rest():
    harness = r"""
const BLOCK = %s;
const geoR = {n:2, vStart:Uint32Array.from([0,4,8]), skin:Uint8Array.from([1,0]), skinList:Uint32Array.from([0]),
  pos:Float32Array.from([0,0,0, 10,0,0, 0,10,0, 10,10,0,  0,0,-20, 5,0,-20, 0,5,-20, 5,5,-20]), bbox:Float32Array.from([0,0,0,10,10,0, 0,0,-20,5,5,-20])};
const restSkin = geoR.pos.slice(0,12), restM = geoR.pos.slice(12,24);
const G = {__poseRev:0, __poseAtRest:undefined, live:{}, addEventListener(){},
  __poseLive(i){ return G.live[i] || null; }, __poseRestPos(i){ return G.live[i] ? (i ? restM : restSkin) : null; }};
const S = {probe:'linear', depthCm:5, P:[4,4,0], N:[0,0,1], rot:0, refKey:'long', hidden:false, mTilt:0, mTiltDir:0, open:true, ab:false, skinStruct:0};
const sent = [];
const sh = {setPose(m){ sent.push(m.ids.slice()); }};
const LIB = {smoothNormal(g,P,r,N){ return N; }, skinHit(){ return null; }, dot(a,b){ return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]; }};
const env = {G, S, sh, LIB, axisCache:{}, archCache:{}, genCache:{}, lastOverlayKey:'x', geo:geoR, refresh(){}, probeW(){ return 40; }, starBase(){ return false; }};
const f = new Function('env', 'with (env) { ' + BLOCK + '; geoR = env.geo; return {syncPose, rasterKey, geo: () => geo}; }');
const T = f(env);
const spec = {tilt:0, dir:0, off:0}, q = {maxDim:480, maxLines:256};
const k0 = T.rasterKey(spec, q), P0 = S.P;
function shift(a, d){ const o = a.slice(); for (let k = 0; k < o.length; k += 3){ o[k] += d[0]; o[k+1] += d[1]; o[k+2] += d[2]; } return o; }
G.live = {0: shift(restSkin, [0, 30, 0]), 1: shift(restM, [0, 30, 0])}; G.__poseRev = 1; G.__poseAtRest = false;
const ch1 = T.syncPose(), k1 = T.rasterKey(spec, q), P1 = S.P.slice(), posedPos = Array.from(T.geo().pos.slice(0, 3));
G.live = {0: shift(restSkin, [0, 30, 0]), 1: shift(restM, [0, 60, 0])}; G.__poseRev = 2;
""" % json.dumps(_q320_block())
    # the event listener is the only way dirty ids reach the block: re-create it with a recording addEventListener
    harness = harness.replace("addEventListener(){}", "addEventListener(n, fn){ G.fire = fn; }")
    harness += r"""
G.fire({detail:{ids:[1]}});                // a second change: only structure 1 (the event names it), the skin did not move
const ch2 = T.syncPose(), k2 = T.rasterKey(spec, q);
G.live = {0: restSkin.slice(), 1: restM.slice()}; G.__poseRev = 3; G.__poseAtRest = true; G.fire({detail:{ids:[0,1]}});
const ch3 = T.syncPose(), k3 = T.rasterKey(spec, q), g = T.geo();
let same = true; for (let k = 0; k < geoR.pos.length; k++) if (g.pos[k] !== geoR.pos[k]) same = false;
console.log(JSON.stringify({k0, k1, k2, k3, ch1, ch2, ch3, sent, P0, P1, P3: S.P, posedPos, same, rawUntouched: geoR.pos[1] === 0,
  caches: Object.keys(env.axisCache).length}));
"""
    o = _node(harness)
    assert o["ch1"] and o["ch2"] and o["ch3"]
    assert o["k1"] != o["k0"] and o["k1"].endswith("|pose1"), o["k1"]
    assert o["k2"].endswith("|pose2") and o["k2"] != o["k1"]
    assert o["k3"] == o["k0"], "back at the model pose the raster key must equal the rest key exactly"
    assert o["sent"] == [[0, 1], [1], [0, 1]], "only the structures that changed are sent to the worker"
    assert o["posedPos"] == [0, 30, 0], "the tool's own geometry copy carries the posed vertices"
    assert o["P1"] == [4, 34, 0], "a probe on skin that moved rides with that skin patch"
    assert o["P3"] == o["P0"], "back at rest the probe returns to its exact rest seat"
    assert o["same"], "back at rest the tool's geometry equals the rest package exactly"
    assert o["rawUntouched"], "the shared rest package is never written"


def test_public_pose_hook_is_neutral():
    bad = re.compile(r"ultrasound|hounsfield|t1_se|imaging_tissues|tissue table|nmskultrasound|acoustic|mrayl|b-mode", re.I)
    for f in ["viewer/pose/pose.js", "viewer/pose/glue_own.js", "viewer/pose/glue_zan.js",
              "viewer/atlas_viewer.template.html", "viewer/zan_atlas.template.html"]:
        t = (REPO / f).read_text()
        assert not bad.search(t), f
    for f in ["viewer/atlas_viewer.template.html", "viewer/zan_atlas.template.html"]:
        t = (REPO / f).read_text()
        assert "nmsk-pose-rev" in t and "window.__poseRestPos" in t and "window.__poseLive" in t, f
