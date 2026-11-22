"""Q246 -- continuity of the imaging simulation: unit tests of the raster / partial-volume / hole-fill / open-seam repair / slab / noise / coil-bias functions
(clinical/imaging_tool.js kernel + LIB.renderValues) and of the ultrasound speckle anchoring (clinical/ultrasound_tool.js), on synthetic meshes under node.
No browser and no built page needed."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(not NODE, reason="node not installed")

PRE = r"""
require('./clinical/imaging_tool.js'); const L=globalThis.NMSKImagingLib;
const T=require('./clinical/data/imaging_tissues.json'); const C=L.compileTable(T);
function cyl(r,y0,y1,nseg,cx=0,cz=0,skipQuads=[]){const pos=[],idx=[];for(let i=0;i<nseg;i++){const a=2*Math.PI*i/nseg;pos.push(cx+r*Math.cos(a),y0,cz+r*Math.sin(a));pos.push(cx+r*Math.cos(a),y1,cz+r*Math.sin(a));}
  pos.push(cx,y0,cz,cx,y1,cz);const c0=2*nseg,c1=c0+1;for(let i=0;i<nseg;i++){const j=(i+1)%nseg;const a=2*i,b=2*i+1,c=2*j,d=2*j+1;if(!skipQuads.includes(i))idx.push(a,c,b,b,c,d);idx.push(c0,c,a,c1,b,d);}return {pos:Float32Array.from(pos),idx:Uint32Array.from(idx)};}
function box(x0,x1,y0,y1,z0,z1){const pos=[x0,y0,z0, x1,y0,z0, x1,y1,z0, x0,y1,z0, x0,y0,z1, x1,y0,z1, x1,y1,z1, x0,y1,z1];
  const idx=[0,2,1,0,3,2, 4,5,6,4,6,7, 0,1,5,0,5,4, 3,6,2,3,7,6, 0,4,7,0,7,3, 1,2,6,1,6,5];return {pos:Float32Array.from(pos),idx:Uint32Array.from(idx)};}
function merge(gs){let nv=0,nt=0;gs.forEach(g=>{nv+=g.pos.length/3;nt+=g.idx.length/3});const pos=new Float32Array(nv*3),idx=new Uint32Array(nt*3);let vo=0,to=0;gs.forEach(g=>{pos.set(g.pos,vo*3);for(let q=0;q<g.idx.length;q++)idx[to*3+q]=g.idx[q]+vo;vo+=g.pos.length/3;to+=g.idx.length/3});return {pos,idx};}
const K=(k)=>C.by[k]._i;
function kernelOf(parts){let nv=0,nt=0;parts.forEach(p=>{nv+=p.g.pos.length/3;nt+=p.g.idx.length/3});
  const pos=new Float32Array(nv*3),idx=new Uint32Array(nt*3),vS=new Uint32Array(parts.length+1),tS=new Uint32Array(parts.length+1),bb=new Float32Array(parts.length*6);let vo=0,to=0;
  parts.forEach((p,i)=>{vS[i]=vo;tS[i]=to;pos.set(p.g.pos,vo*3);for(let q=0;q<p.g.idx.length;q++)idx[to*3+q]=p.g.idx[q]+vo;const mn=[1e9,1e9,1e9],mx=[-1e9,-1e9,-1e9];for(let q=0;q<p.g.pos.length;q+=3)for(let a=0;a<3;a++){mn[a]=Math.min(mn[a],p.g.pos[q+a]);mx[a]=Math.max(mx[a],p.g.pos[q+a]);}bb.set([...mn,...mx],i*6);vo+=p.g.pos.length/3;to+=p.g.idx.length/3;});
  vS[parts.length]=vo;tS[parts.length]=to;const order=[];parts.forEach((p,i)=>{if(!p.skin)order.push(i)});order.sort((a,b)=>C.T.classes[parts[a].cls].priority-C.T.classes[parts[b].cls].priority||a-b);
  const Kn=L.KERNEL_FACTORY();Kn.setGeometry({n:parts.length,pos,idx,vStart:vS,tStart:tS,bbox:bb,cls:Uint8Array.from(parts.map(p=>p.cls)),kind:Uint8Array.from(parts.map(p=>p.kind||0)),skin:Uint8Array.from(parts.map(p=>p.skin?1:0)),render:Uint8Array.from(parts.map(p=>p.render||0)),order:Uint32Array.from(order),skinList:Uint32Array.from(parts.map((p,i)=>p.skin?i:-1).filter(i=>i>=0))});return Kn;}
const bone={};Object.values(T.bone_model.kinds).forEach(k=>{bone[k.id]={axial:!!k.axial,tthin:k.tthin,tmax:k.tmax,frac:k.frac,canal:!!k.canal,z0:k.z0||.2,z1:k.z1||.8,ramp:k.ramp||.08}});
let seq=0;
/* axial plane (normal 0,-1,0 -> u = -x ... see basis), W x W pixels of px mm, centred on (cx, cz) */
function slice(Kn,opt){const b=L.basis([0,-1,0]),W=opt.W||64,px=opt.px||1,fov=W*px,O=[opt.cx||0,opt.y||0,opt.cz||0];
  const R={key:'k'+(++seq),W,H:W,O,u:b.u,v:b.v,n:b.n,u0:-fov/2,v0:fov/2,px,smin:opt.s||0,smax:opt.s||0,s:opt.s||0,wantSid:true,skinMm:1.8,ids:C.ids,bone,ss:opt.ss||1};if(opt.holeMax!=null)R.holeMax=opt.holeMax;
  const r=Kn.slice(R);r.W=W;r.px=px;r.basis=b;return r;}
function values(r,lutName,extra){const lut=lutName==='mr'?L.mrTable(C,JSON.parse(JSON.stringify(T.mr_sequences.filter(q=>q.key==='t1_se')[0]))).sig:L.ctTable(C);
  const res={W:r.W,H:r.W,ss:r.ss||1,labels:[r.lab],fine:[r.fine||null],mid:0};return L.renderValues(res,lut,Object.assign({modality:lutName==='mr'?'mr':'ct',slab:'avg',thick:0,px:r.px},extra||{}));}
"""


def _node(code: str, timeout=240):
    r = subprocess.run([NODE, "-e", PRE + code], capture_output=True, text=True, timeout=timeout, cwd=str(REPO))
    assert r.returncode == 0, r.stderr[-2500:]
    return json.loads(r.stdout.strip().splitlines()[-1])


# ---------------------------------------------------------------- partial volume
@needs_node
def test_partial_volume_area_and_subpixel_continuity():
    o = _node(r"""
const R0=14.3, nseg=192;
function scene(cx){return kernelOf([{g:cyl(100,-50,50,96),cls:C.ids.skin,skin:1},{g:cyl(R0,-30,30,nseg,cx,0),cls:K('muscle'),kind:0}]);}
const hu=L.ctTable(C), fat=hu[K('fat')], mus=hu[K('muscle')], out={fat,mus,area:{},edge:{}};
for(const ss of [1,3]){
  out.area[ss]=[];
  for(const sh of [0,0.25,0.5,0.75]){
    const Kn=scene(0), r=slice(Kn,{cx:-sh*1.0,ss}), v=values(r,'ct');   // plane centre moves, mesh stays: the cylinder moves by sh pixel
    let a=0; for(let k=0;k<v.length;k++) a+=(v[k]-fat)/(mus-fat); out.area[ss].push(a/(Math.PI*R0*R0));
  }
  // one edge pixel while the cylinder slides in steps of 0.1 px along the u axis: value must change gradually
  const vals=[]; for(let i=0;i<=20;i++){ const Kn=scene(0), r=slice(Kn,{cx:i*0.1,ss}), v=values(r,'ct'); vals.push((v[32*64+32+14]-fat)/(mus-fat)); }
  out.edge[ss]=vals;
}
console.log(JSON.stringify(out));
""")
    for ss, tol in (("3", 0.012),):
        for ratio in o["area"][ss]:
            assert abs(ratio - 1) < tol, (ss, o["area"][ss])
    err1 = max(abs(r - 1) for r in o["area"]["1"]); err3 = max(abs(r - 1) for r in o["area"]["3"])
    assert err3 < err1 * 0.75 or err3 < 0.005, (err1, err3)
    steps1 = max(abs(b - a) for a, b in zip(o["edge"]["1"], o["edge"]["1"][1:])); steps3 = max(abs(b - a) for a, b in zip(o["edge"]["3"], o["edge"]["3"][1:]))
    assert steps1 > 0.9                                        # one pixel flips from fat to muscle in one 0.1 px step (a binary label)
    assert steps3 < 0.35                                       # 3 x 3 coverage: a 0.1 px move changes the pixel by at most ~1/3 of the contrast
    ev = o["edge"]["3"]; assert all(b <= a + 0.02 for a, b in zip(ev, ev[1:])) or all(b >= a - 0.02 for a, b in zip(ev, ev[1:]))     # monotone while the edge slides across the pixel


@needs_node
def test_slab_midpoint_rule_and_continuity_with_thickness():
    o = _node(r"""
const out={};
out.off5=L.slabOffsets(-2.5,2.5,5,25); out.off1=L.slabOffsets(0,0.8,0.8,25); out.offThin=L.slabOffsets(0,0,0,25); out.cap=L.slabOffsets(-50,50,100,25).length; out.offCut=L.slabOffsets(0,7,7,25);
// avg slab of a sphere cut: liver area vs thickness (grows continuously, no jump when n changes)
const Kn=kernelOf([{g:cyl(100,-60,60,96),cls:C.ids.skin,skin:1},{g:cyl(10,-12,12,64),cls:K('muscle')}]);
const hu=L.ctTable(C),fat=hu[K('fat')],mus=hu[K('muscle')]; const mean=[];
for(let th=0;th<=40;th+=1){ const offs=L.slabOffsets(-th/2,th/2,th,25), labs=[],fine=[]; offs.forEach(s=>{const r=slice(Kn,{s,ss:2}); labs.push(r.lab); fine.push(r.fine);});
  const res={W:64,H:64,ss:2,labels:labs,fine:fine,mid:Math.floor((offs.length-1)/2)}; const v=L.renderValues(res,hu,{modality:'ct',slab:'avg',thick:th,px:1}); let a=0; for(let k=0;k<v.length;k++)a+=(v[k]-fat)/(mus-fat); mean.push(a);}
out.mean=mean; console.log(JSON.stringify(out));
""")
    assert o["off5"] == pytest.approx([-2, -1, 0, 1, 2]) and len(o["off5"]) == 5
    assert o["off1"] == [0.4] and o["offThin"] == [0.0] and o["cap"] == 25
    assert o["offCut"][0] == pytest.approx(0.5) and o["offCut"][-1] == pytest.approx(6.5)
    # cylinder of radius 10 and length 24 mm: the slab (centre 0, +-th/2) covers it fully until th = 24 -> the mean area is CONSTANT then falls to ~ 24/th of it
    m = o["mean"]; full = m[0]
    assert full == pytest.approx(3.14159 * 100, rel=0.05)
    assert all(abs(m[i] - full) / full < 0.02 for i in range(0, 24))
    drops = [abs(m[i + 1] - m[i]) / full for i in range(len(m) - 1)]
    assert max(drops) < 0.09                                    # no jumps when the number of sub-slices changes with the thickness (beyond 25 mm the cap of 25 samples quantises the length: 1-2 samples per step)
    assert all(abs(m[th] / full - min(1.0, 24.0 / th)) < 0.09 for th in range(1, 41))


# ---------------------------------------------------------------- hole fill and open-seam repair
@needs_node
def test_small_enclosed_gap_takes_the_surrounding_tissue_and_is_counted():
    o = _node(r"""
const outer=box(-20,20,-20,20,-20,20), tiny=box(-0.5,0.5,-10,10,-0.5,0.5), big=box(10,16,-10,10,10,16);   // a 1 mm channel (as small as a pixel) and a 6 mm cavity inside ONE muscle (even-odd: holes)
const Kn=kernelOf([{g:cyl(100,-50,50,96),cls:C.ids.skin,skin:1},{g:merge([outer,tiny,big]),cls:K('muscle')}]);
const out={};
for(const hm of [0,1.5]){ const r=slice(Kn,{ss:3,holeMax:hm,W:48}); const atF=(x,z)=>{const ix=Math.floor((-x+24)*3),iy=Math.floor((24-z)*3);return T.classes[r.fine[iy*144+ix]].key;};   // fine sample (3 x 3 per pixel)
  out['hm'+hm]={tiny:atF(-0.1,0.1),big:atF(13,13),holes:r.holesFilled}; }
const r1=slice(Kn,{ss:1,W:48}); out.ss1=T.classes[r1.lab[24*48+24]].key; out.ss1holes=r1.holesFilled;
console.log(JSON.stringify(out));
""")
    assert o["hm0"]["tiny"] == "fat" and o["hm0"]["holes"] == 0                      # filling switched off: the baseline shows
    assert o["hm1.5"]["tiny"] == "muscle" and 0.5 < o["hm1.5"]["holes"] < 3           # filled with the surrounding tissue, counted in pixels (area ~ 1 x 1 mm)
    assert o["hm1.5"]["big"] == "fat" and o["hm0"]["big"] == "fat"                      # a real 6 mm cavity is NOT filled
    assert o["ss1"] in ("muscle", "fat")


@needs_node
def test_open_seam_rows_are_repaired_from_the_neighbouring_rows():
    o = _node(r"""
const R0=14, nseg=96;
const full=kernelOf([{g:cyl(100,-50,50,96),cls:C.ids.skin,skin:1},{g:cyl(R0,-30,30,nseg),cls:K('muscle')}]);
const open=kernelOf([{g:cyl(100,-50,50,96),cls:C.ids.skin,skin:1},{g:cyl(R0,-30,30,nseg,0,0,[5,6,7,8]),cls:K('muscle')}]);   // 4 lateral quads missing: an open seam
const m=K('muscle'), out={};
function area(r){let a=0;for(const c of r.lab) if(c===m) a++; return a;}
const rf=slice(full,{W:64,ss:1}), ro=slice(open,{W:64,ss:1}), ro3=slice(open,{W:64,ss:3});
out.full=area(rf); out.open=area(ro); out.open3=area({lab:ro3.fine})/9; out.parity=ro.parityBad; out.repaired=ro.repairedRows; out.expected=Math.PI*R0*R0;
out.sym=0; for(let k=0;k<rf.lab.length;k++) if((rf.lab[k]===m)!==(ro.lab[k]===m)) out.sym++;
console.log(JSON.stringify(out));
""")
    assert o["parity"] > 0 and o["repaired"] > 0
    assert abs(o["open"] - o["full"]) / o["full"] < 0.06, o                             # the repaired section is the closed one to within a few pixels
    assert o["sym"] < 0.09 * o["full"], o
    assert abs(o["open3"] - o["expected"]) / o["expected"] < 0.08, o


@needs_node
def test_painter_order_is_the_tissue_priority_and_stable():
    o = _node(r"""
// overlapping muscle + bone discs: the higher priority wins at every position and in every slice, with the creation order reversed too
const A=cyl(15,-30,30,64,0,0), B=cyl(15,-30,30,64,10,0);
const k1=kernelOf([{g:cyl(100,-50,50,96),cls:C.ids.skin,skin:1},{g:A,cls:K('muscle')},{g:B,cls:K('bone_cancellous'),kind:0}]);
const k2=kernelOf([{g:cyl(100,-50,50,96),cls:C.ids.skin,skin:1},{g:B,cls:K('bone_cancellous'),kind:0},{g:A,cls:K('muscle')}]);
const pr=(k)=>T.classes[K(k)].priority; const out={prM:pr('muscle'),prB:pr('bone_cancellous')};
let diff=0; for(const s of [-20,-5,0,7,19]){ const a=slice(k1,{s,ss:2}).fine, b=slice(k2,{s,ss:2}).fine; for(let i=0;i<a.length;i++) if(a[i]!==b[i]) diff++; }
out.diff=diff; console.log(JSON.stringify(out));
""")
    assert o["diff"] == 0                                                              # creation order does not matter: priority (then index) decides, identically in every slice


@needs_node
def test_supersampling_budget_and_tiers():
    o = _node(r"""
const out={}; out.t0=L.chooseSS(1,0); out.single=L.chooseSS(1,1); out.s5=L.chooseSS(5,1); out.s9=L.chooseSS(9,1); out.s16=L.chooseSS(16,1); out.s17=L.chooseSS(17,1); out.s25=L.chooseSS(25,1); out.s49=L.chooseSS(49,1); out.cap=L.chooseSS(1,1,2);
out.budgetOk=[1,2,3,4,5,6,8,10,16,25,49].every(n=>{const s=L.chooseSS(n,1);return s*s*n<=Math.max(L.DEFAULTS.ssBudget,n);});
console.log(JSON.stringify(out));
""")
    assert o["t0"] == 1 and o["single"] == 3 and o["s5"] == 3 and o["s9"] == 2 and o["s16"] == 2 and o["s17"] == 1 and o["s25"] == 1 and o["s49"] == 1 and o["cap"] == 2 and o["budgetOk"]


# ---------------------------------------------------------------- noise and coil bias
@needs_node
def test_noise_is_position_seeded_unit_variance_and_follows_the_tissue():
    o = _node(r"""
const out={}; let n=0,s=0,s2=0; for(let i=0;i<60000;i++){const g=L.gnoise(i*0.37+0.11,(i%97)*0.53,(i%31)*0.7,5);n++;s+=g;s2+=g*g;} out.mean=s/n; out.sd=Math.sqrt(s2/n-(s/n)**2);
out.repeat=L.gnoise(1.234,5.67,8.9,5)===L.gnoise(1.234,5.67,8.9,5); out.seed=L.gnoise(1.234,5.67,8.9,5)!==L.gnoise(1.234,5.67,8.9,6);
// the same pixel grid of two planes that are 10 pixels apart (pan) sees the same noise at the same body position
const hu=L.ctTable(C), W=32, px=1.5, lab=new Uint8Array(W*W).fill(C.ids.fat);
const b=L.basis([0,-1,0]);
function render(shiftPx,y,thick){const O=[0,y,0]; const res={W:W,H:W,ss:1,labels:[lab],fine:[null],mid:0,offs:[0]};
  return L.renderValues(res,hu,{modality:'ct',slab:'avg',thick:thick||0,px:px,noise:25,seed:7,offs:[0],plane:{O:O,u:b.u,v:b.v,n:b.n,u0:-W*px/2+shiftPx*px,v0:W*px/2}});}
const A=render(0,10), B=render(10,10), A2=render(0,10), C1=render(0,10.5), D=render(0,200);
const base=hu[C.ids.fat]; let maxPan=0, same=true, fr=0, nn=0;
for(let y=0;y<W;y++)for(let x=0;x<W-10;x++){maxPan=Math.max(maxPan,Math.abs((B[y*W+x]-base)-(A[y*W+x+10]-base)));}
for(let k=0;k<A.length;k++) if(A[k]!==A2[k]) same=false;
function corr(P,Q){let sa=0,sb=0,sab=0,saa=0,sbb=0,m=P.length;for(let i=0;i<m;i++){const p=P[i]-base,q=Q[i]-base;sa+=p;sb+=q;sab+=p*q;saa+=p*p;sbb+=q*q;}return (sab/m-sa/m*sb/m)/Math.sqrt((saa/m-(sa/m)**2)*(sbb/m-(sb/m)**2));}
out.panMaxDiff=maxPan; out.rerenderIdentical=same; out.corr_half_mm=corr(A,C1); out.corr_far=corr(A,D); out.sdImage=Math.sqrt(A.reduce((a,v)=>a+(v-base)**2,0)/A.length);
// slab average: noise falls with sqrt(thickness / correlation length)
const th=render(0,10,12); out.sdSlab=Math.sqrt(th.reduce((a,v)=>a+(v-base)**2,0)/th.length);
console.log(JSON.stringify(out));
""")
    assert abs(o["mean"]) < 0.03 and abs(o["sd"] - 1) < 0.04
    assert o["repeat"] and o["seed"]
    assert o["panMaxDiff"] < 1e-3                       # the noise belongs to the body position: a panned plane shows the shifted pattern
    assert o["rerenderIdentical"]                       # re-rendering (window / level change) does not re-draw the noise
    assert o["corr_half_mm"] > 0.3 and abs(o["corr_far"]) < 0.25
    assert o["sdImage"] == pytest.approx(25, rel=0.1) and o["sdSlab"] < 0.55 * o["sdImage"]


@needs_node
def test_coil_bias_is_smooth_bounded_and_mri_only():
    o = _node(r"""
const out={}; let mx=0,lo=9,hi=-9,g=0; for(let i=0;i<4000;i++){ const x=(i%20)*30-300, y=((i/20)|0)%20*30-300, z=((i/400)|0)*40-200; const f=L.biasField(x,y,z,0.2); lo=Math.min(lo,f); hi=Math.max(hi,f);
  const f2=L.biasField(x+1,y,z,0.2), f3=L.biasField(x,y+1,z,0.2), f4=L.biasField(x,y,z+1,0.2); g=Math.max(g,Math.abs(f2-f),Math.abs(f3-f),Math.abs(f4-f)); }
out.lo=lo; out.hi=hi; out.gradPerMm=g;
const hu=L.ctTable(C), mr=L.mrTable(C,JSON.parse(JSON.stringify(T.mr_sequences.filter(q=>q.key==='t1_se')[0]))).sig, W=16, lab=new Uint8Array(W*W).fill(C.ids.fat), b=L.basis([0,-1,0]);
const pl={O:[0,0,0],u:b.u,v:b.v,n:b.n,u0:-8,v0:8}; const res={W:W,H:W,ss:1,labels:[lab],fine:[null],mid:0,offs:[0]};
const ct=L.renderValues(res,hu,{modality:'ct',px:1,bias:0.3,plane:pl,offs:[0]}), m0=L.renderValues(res,mr,{modality:'mr',px:1,plane:pl,offs:[0]}), m1=L.renderValues(res,mr,{modality:'mr',px:1,bias:0.3,plane:pl,offs:[0]});
out.ctUnchanged=ct.every(v=>v===hu[C.ids.fat]); out.mrChanged=m1.some((v,i)=>Math.abs(v-m0[i])>1e-6*Math.abs(m0[i])+1e-9);
console.log(JSON.stringify(out));
""")
    assert o["lo"] >= 0.8 - 1e-6 and o["hi"] <= 1.2 + 1e-6 and o["lo"] < 0.95 < 1.05 < o["hi"]
    assert o["gradPerMm"] < 0.2 * 2 * 3.1416 / 650 * 3.5 * 0.8                          # amplitude x wave number bound (the three plane waves)
    assert o["ctUnchanged"] and o["mrChanged"]


# ---------------------------------------------------------------- the harness metrics on a synthetic scene
@needs_node
def test_jaggedness_metric_is_lower_with_coverage_and_the_edge_series_is_sane():
    o = _node(r"""
const H=require('./scripts/clinical/q246_lib.js');
const Kn=kernelOf([{g:cyl(26,-50,50,180),cls:C.ids.skin,skin:1}]);
const hu=L.ctTable(C), out={};
for(const ss of [1,3]){ const r=slice(Kn,{W:96,px:1.0,ss}), v=values(r,'ct'); out['jag'+ss]=H.jaggedness(v,96,96,-1000,hu[C.ids.skin]); }
// edge position estimate of a perfect circle: radius from the sub-pixel crossings
const r3=slice(Kn,{W:96,px:1.0,ss:3}), v3=values(r3,'ct'), e=H.edgeSeries(v3,96,96,-1000,hu[C.ids.skin]);
const rs=[]; for(let y=0;y<96;y++){const L_=e.rows[y][0],R_=e.rows[y][1],d=y+0.5-48; if(isFinite(L_)&&isFinite(R_)&&Math.abs(d)<16) rs.push(Math.abs((R_-L_)/2-Math.sqrt(26*26-d*d)));} out.halfWidthErr=rs.reduce((a,b)=>a+b,0)/rs.length;
console.log(JSON.stringify(out));
""")
    assert o["jag1"] > 0.15 and o["jag3"] < 0.12 and o["jag3"] < 0.55 * o["jag1"]
    assert o["halfWidthErr"] < 0.25                                                      # the sub-pixel outline follows the analytic circle (radius 26) to a quarter of a pixel


# ---------------------------------------------------------------- ultrasound: speckle belongs to the body
@needs_node
def test_ultrasound_speckle_is_anchored_to_the_body_not_to_the_frame():
    o = json.loads(subprocess.run([NODE, "-e", r"""
require('./clinical/imaging_tool.js'); require('./clinical/ultrasound_tool.js'); const U=globalThis.NMSKUltrasoundLib, L=globalThis.NMSKImagingLib;
const T=require('./clinical/data/imaging_tissues.json'), C=L.compileTable(T), US=require('./clinical/data/ultrasound_tissues.json'), AC=U.compileAcoustics(US,C);
const geom=U.fanGeom('linear',44,0,0,50), plan=U.planRaster(geom,300,{maxLines:192}), lab=new Uint8Array(plan.W*plan.H).fill(C.by.liver._i);
const N=[0,0,1], ref=U.REF.long;
function frameAt(tilt,dir,off){const pf=U.probeFrame(N,ref,0,tilt,dir); return {O:[0,0,0].map((x,a)=>x+pf.e[a]*off), pf};}
function sim(tilt,dir,off,seedMode){const f=frameAt(tilt,dir,off), r0=U.probeFrame(N,ref,0,0,0);
  const o={AC,geom,plan,lab,sid:null,freq:7.5,depthMm:50,gainDb:0,tgcDb:0,focusMm:25,speckle:true,textures:false,reverb:false,noise:false,seed:11+(seedMode==='perframe'?131*tilt:0),elevMm:off,frame:{O:f.O,u:f.pf.u,b:f.pf.b,e:f.pf.e,zoff:0},axisOf:()=>null};
  if(seedMode!=='legacy'&&seedMode!=='perframe') o.ref={O:[0,0,0],u:r0.u,b:r0.b,e:r0.e};
  return U.simulate(o);}
function ncc(a,b){let n=0,sa=0,sb=0,saa=0,sbb=0,sab=0;for(let k=0;k<a.db.length;k++){if(a.db[k]<-150||b.db[k]<-150)continue;n++;const x=a.db[k],y=b.db[k];sa+=x;sb+=y;saa+=x*x;sbb+=y*y;sab+=x*y;}const ma=sa/n,mb=sb/n;return (sab/n-ma*mb)/Math.sqrt((saa/n-ma*ma)*(sbb/n-mb*mb));}
const out={};
const a=sim(0,90,0), b=sim(1,90,0), c=sim(5,90,0), a2=sim(0,90,0), bl=sim(1,90,0,'perframe');
out.fan1=ncc(a,b); out.fan5=ncc(a,c); out.perframeSeed1deg=ncc(sim(0,90,0,'perframe'),bl); out.repeat=ncc(a,a2); out.sweep1=ncc(sim(0,0,0),sim(0,0,1)); out.sweep30=ncc(sim(0,0,0),sim(0,0,30));
console.log(JSON.stringify(out));"""], capture_output=True, text=True, timeout=240, cwd=str(REPO)).stdout.strip().splitlines()[-1])
    assert o["repeat"] > 0.999                                   # deterministic
    assert o["fan1"] > 0.8                                       # 1 degree of tilt keeps the same grain (body-fixed lattice)
    assert o["perframeSeed1deg"] < 0.55                          # a new seed per frame (the pre-Q246 star) gives independent grain
    assert o["fan1"] > o["perframeSeed1deg"] + 0.3 and o["fan1"] > o["fan5"] > 0.0
    assert o["sweep1"] > 0.7 and o["sweep30"] < o["sweep1"]      # elevation: correlated 1 mm apart, little at 30 mm
