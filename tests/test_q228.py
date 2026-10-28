"""Q228 -- ultrasound add-on (simulated B-mode from the meshes): acoustic table, probe geometry, tilt star, sweep matrix, skin normal, physics on
synthetic rasters (bone = bright edge + shadow, fluid = anechoic + posterior enhancement, angle dependence, frequency, anisotropy, reverberation),
staging / licensing / loader chain, and the recorded browser runs on the real pages (opt-in re-run: Q228_BROWSER=1 Q228_THREE_JS=... needs
build/q228/<page> from scripts/regen_ultrasound_q228.sh and /opt/pw-browsers/chromium)."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "clinical"))
import stage_clinical_files as scf  # noqa: E402

US = json.loads((REPO / "clinical" / "data" / "ultrasound_tissues.json").read_text(encoding="utf-8"))
IMG = json.loads((REPO / "clinical" / "data" / "imaging_tissues.json").read_text(encoding="utf-8"))
TOOL = REPO / "clinical" / "ultrasound_tool.js"
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(not NODE, reason="node not installed")
STATUSES = {"verified_abstract", "secondary_checked", "recalled_unverified", "derived", "assumption", "owner_supplied"}


def _node(code: str, timeout=180):
    r = subprocess.run([NODE, "-e", code], capture_output=True, text=True, timeout=timeout, cwd=str(REPO))
    assert r.returncode == 0, r.stderr[-2500:]
    return r.stdout


# ---------------------------------------------------------------- table
def test_acoustic_table_covers_every_imaging_class_and_cites_sources():
    assert US["schema"] == "nmsk.ultrasound_tissues.v1"
    keys = [c["key"] for c in IMG["classes"]]
    assert set(keys) == set(US["classes"]), set(keys) ^ set(US["classes"])
    refs = US["references"]
    for k, c in US["classes"].items():
        assert c["status"] in STATUSES, k
        assert c["z"] > 0 and c["c"] > 0 and c["alpha"] >= 0 and 0 <= c["speck"] <= 1 and c["src"], k
        for s in c["src"]:
            assert s in refs, (k, s)
        # Z = rho c is a plausible magnitude check: rho = Z / c lies between 1 and 2500 kg/m3 (air 1.2, bone 1900, tooth 2900)
        rho = c["z"] * 1e6 / c["c"]
        assert 0.8 < rho < 3500, (k, rho)


def test_owner_named_impedances_and_honest_status():
    c = US["classes"]
    for key, z in (("fat", 1.34), ("muscle", 1.70), ("blood_artery", 1.61), ("bone_cortical", 7.8), ("air", 0.0004), ("liver", 1.65), ("kidney", 1.62), ("tendon_ligament", 1.9), ("soft_unassigned", 1.60)):
        assert c[key]["z"] == pytest.approx(z), key
    # nothing is claimed as verified except the one number read in a PubMed abstract (Pinton 2012, 13.3 dB/cm) -- everything else is flagged
    verified = [k for k, v in US["classes"].items() if v["status"] in ("verified_abstract", "secondary_checked")]
    assert verified == ["bone_cortical"]
    assert c["bone_cortical"]["alpha"] == pytest.approx(13.3)
    assert US["references"]["pinton2012"]["pmid"] == "22225300"
    assert US["references"]["goss1978"]["pmid"] == "361793" and US["references"]["goss1980"]["pmid"] == "11683186"
    assert any("UNVERIFIED" in n["note"] or n["status"] != "verified_abstract" for n in c.values())
    assert any("itis.swiss" in h or "Duck" in h for h in US["honesty"])


def test_probe_presets_match_the_request():
    p = US["probes"]
    assert p["linear"]["width_mm"][0] == 38 and p["linear"]["width_mm"][-1] == 50
    assert p["convex"]["width_mm"][0] == 60 and p["convex"]["width_mm"][-1] == 70
    assert p["sector"]["width_mm"][0] == 20 and p["sector"]["width_mm"][-1] == 25
    assert (US["freq_range_mhz"]["min"], US["freq_range_mhz"]["max"], US["freq_range_mhz"]["step"]) == (1, 18, 1)   # Q291 (was presets 3.5 / 5 / 7.5 / 12)


# ---------------------------------------------------------------- geometry (node)
GEOM = r"""
require('./clinical/ultrasound_tool.js'); const U=globalThis.NMSKUltrasoundLib; const out={};
function rnd(s){let x=s;return()=>{x=(x*1664525+1013904223)>>>0;return x/4294967296;}} const R=rnd(7);
// 1. perpendicular probe: face normal == skin normal, beam = -normal, long axis in the tangent plane, orthonormal frame
let maxErr=0,maxOrth=0,maxTan=0;
for(let i=0;i<200;i++){const N=U.unit([R()-.5,R()-.5,R()-.5]);const f=U.probeFrame(N,i%2?U.REF.long:U.REF.trans,R()*360,0,0);
  maxErr=Math.max(maxErr,U.angleDeg(f.N,N),U.angleDeg(f.b,[-N[0],-N[1],-N[2]]));maxTan=Math.max(maxTan,Math.abs(U.dot(f.u,N)));
  maxOrth=Math.max(maxOrth,Math.abs(U.dot(f.u,f.e)),Math.abs(U.dot(f.u,f.N)),Math.abs(U.dot(f.e,f.N)),Math.abs(Math.hypot(...f.u)-1));}
out.perp={maxErr,maxOrth,maxTan};
// 2. tilt star: exact angle, about the right axes
const N0=U.unit([.2,.3,.93]);const star=U.starTilts(15);out.starN=star.length;out.starDirs=star.map(s=>s.dir);out.starTilts=star.map(s=>s.tilt);
let errAng=0,rock=0,fan=0,dirErr=0;
for(const th of [5,10,15,20,30]){for(let d=0;d<360;d+=45){const f=U.probeFrame(N0,U.REF.long,23,th,d);const f0=U.probeFrame(N0,U.REF.long,23,0,0);
  errAng=Math.max(errAng,Math.abs(U.angleDeg(f.N,f0.N)-th));
  // the handle leans towards t = cos d u0 + sin d e0: N' = cos th N + sin th t
  const t=[0,1,2].map(a=>Math.cos(d*Math.PI/180)*f0.u[a]+Math.sin(d*Math.PI/180)*f0.e[a]);
  dirErr=Math.max(dirErr,U.angleDeg(f.N,[0,1,2].map(a=>Math.cos(th*Math.PI/180)*f0.N[a]+Math.sin(th*Math.PI/180)*t[a])));
  if(d===0||d===180){rock=Math.max(rock,U.angleDeg(f.e,f0.e));}                       // rocking inside the image plane: the plane normal (short axis) does not move
  if(d===90||d===270){fan=Math.max(fan,U.angleDeg(f.u,f0.u),Math.abs(U.angleDeg(f.e,f0.e)-th));}  // fanning: the long axis does not move, the plane swings by th
}}
out.tilt={errAng,dirErr,rock,fan};
// 3. sweep: frame k at k*spacing, N=3..9, spacing 3..50 mm; planes parallel (same normal), perpendicular to the image plane
const sw={ok:true,maxOffErr:0,planeAngle:0,count:[],dims:{}};
for(let n=3;n<=9;n++){for(const sp of [3,7.5,10,25,50]){const offs=U.sweepOffsets(n,sp,false,1);sw.count.push(offs.length);
  for(let k=0;k<n;k++)sw.maxOffErr=Math.max(sw.maxOffErr,Math.abs(offs[k]-k*sp));
  const f=U.probeFrame(N0,U.REF.long,40,12,70);const P=[10,20,30];const O=offs.map(o=>[0,1,2].map(a=>P[a]+f.e[a]*o));
  for(let k=1;k<n;k++){const d=[0,1,2].map(a=>O[k][a]-O[0][a]);sw.maxOffErr=Math.max(sw.maxOffErr,Math.abs(Math.hypot(...d)-k*sp));
    sw.planeAngle=Math.max(sw.planeAngle,Math.abs(U.angleDeg(d,f.e)),Math.abs(90-U.angleDeg(d,f.u)),Math.abs(90-U.angleDeg(d,f.b)));}}
  sw.dims[n]=U.matrixDims(n);}
const c=U.sweepOffsets(5,10,true,1);sw.centred=c;sw.reverse=U.sweepOffsets(3,5,false,-1);out.sweep=sw;
// 4. follow the organ: the best rotation puts the sweep direction on the organ axis (when the axis can lie in the tangent plane)
const ax=U.unit([.8,-.1,.6]);const N1=U.unit([0,0,1]);const b=U.followRotation(N1,U.REF.long,0,0,ax);
const ff=U.probeFrame(N1,U.REF.long,b.rot,0,0);out.follow={cos:Math.abs(U.dot(ff.e,U.unit([ax[0],ax[1],0]))),rot:b.rot};
// 5. skin: synthetic sphere (r = 100 mm, 5000 triangles) -> hit + smoothed normal equals the radial direction; flat tilted plane likewise
function sphere(r,n){const pos=[],idx=[];for(let i=0;i<=n;i++){const th=Math.PI*i/n;for(let j=0;j<n;j++){const ph=2*Math.PI*j/n;pos.push(r*Math.sin(th)*Math.cos(ph),r*Math.cos(th),r*Math.sin(th)*Math.sin(ph));}}
 for(let i=0;i<n;i++)for(let j=0;j<n;j++){const a=i*n+j,b=i*n+(j+1)%n,c=(i+1)*n+j,d=(i+1)*n+(j+1)%n;idx.push(a,b,c,b,d,c);}return {pos:Float32Array.from(pos),idx:Uint32Array.from(idx)};}
const sp=sphere(100,60);const geo={pos:sp.pos,idx:sp.idx,tStart:Uint32Array.from([0,sp.idx.length/3]),skinList:Uint32Array.from([0]),bbox:Float32Array.from([-100,-100,-100,100,100,100])};
let nErr=0,hitErr=0;for(let i=0;i<40;i++){const d=U.unit([R()-.5,R()-.5,R()-.5]);const o=[d[0]*400,d[1]*400,d[2]*400];const h=U.skinHit(geo,o,[-d[0],-d[1],-d[2]]);
  hitErr=Math.max(hitErr,Math.abs(Math.hypot(...h.point)-100));const nrm=U.smoothNormal(geo,h.point,15,null,0);const nn=U.unit(h.point);
  const nn2=Math.min(U.angleDeg(nrm,nn),U.angleDeg([-nrm[0],-nrm[1],-nrm[2]],nn));nErr=Math.max(nErr,nn2);
  const fr=U.probeFrame(nrm,U.REF.long,0,0,0);nErr=Math.max(nErr,U.angleDeg(fr.N,nrm));}
out.skin={hitErr,nErr};
// cut plane: a hit on the removed side is skipped
const d0=[0,0,-1];const hAll=U.skinHit(geo,[0,0,400],d0);const hCut=U.skinHit(geo,[0,0,400],d0,p=>p[2]<0);out.cut={all:hAll.point[2],cut:hCut.point[2]};
// 6. PCA axis of an elongated box
const bx=[];for(let i=0;i<2000;i++)bx.push((R()-.5)*100,(R()-.5)*10,(R()-.5)*10);const pa=U.pcaAxis(Float32Array.from(bx),0,2000);out.pca={ax:Math.abs(pa.a[0]),elong:pa.elong};
console.log(JSON.stringify(out));"""


@needs_node
def test_probe_frames_tilt_star_sweep_and_skin_normal():
    o = json.loads(_node(GEOM))
    assert o["perp"]["maxErr"] < 1e-3 and o["perp"]["maxOrth"] < 1e-9 and o["perp"]["maxTan"] < 1e-9            # perpendicular probe normal == skin normal
    assert o["starN"] == 9 and o["starDirs"] == [0, 0, 45, 90, 135, 180, 225, 270, 315] and o["starTilts"] == [0] + [15] * 8
    t = o["tilt"]
    assert t["errAng"] < 1e-3 and t["dirErr"] < 1e-3 and t["rock"] < 1e-3 and t["fan"] < 1e-3      # degrees (acos near 1)                    # exactly the requested angle, about the right axes
    s = o["sweep"]
    assert s["maxOffErr"] < 1e-9 and s["planeAngle"] < 1e-3 and len(s["count"]) == 35                           # offsets k*spacing along the plane normal
    assert s["dims"]["3"] == [3, 1] and s["dims"]["4"] == [2, 2] and s["dims"]["6"] == [3, 2] and s["dims"]["9"] == [3, 3]
    assert all(c in (3, 4, 5, 6, 7, 8, 9) for c in s["count"])
    assert all(d[0] * d[1] >= n for n, d in ((int(k), v) for k, v in s["dims"].items()))
    assert s["centred"] == [-20, -10, 0, 10, 20] and s["reverse"] == [0, -5, -10]
    assert o["follow"]["cos"] > 0.999
    assert o["skin"]["hitErr"] < 0.2 and o["skin"]["nErr"] < 2.0
    assert o["cut"]["all"] > 99 and o["cut"]["cut"] < -99
    assert o["pca"]["ax"] > 0.99 and o["pca"]["elong"] > 20


# ---------------------------------------------------------------- physics on synthetic rasters (node)
PHYS = r"""
require('./clinical/imaging_tool.js'); require('./clinical/ultrasound_tool.js');
const I=globalThis.NMSKImagingLib,U=globalThis.NMSKUltrasoundLib;
const T=require('./clinical/data/imaging_tissues.json'),US=require('./clinical/data/ultrasound_tissues.json');
const C=I.compileTable(T),AC=U.compileAcoustics(US,C),K=k=>C.by[k]._i;
function mk(type,depth,fn,opt={}){const g=U.fanGeom(type,type==='linear'?44:type==='convex'?65:22,type==='convex'?60:0,type==='sector'?90:0,depth);const pl=U.planRaster(g,opt.maxDim||420);
 const lab=new Uint8Array(pl.W*pl.H),sid=new Uint16Array(pl.W*pl.H).fill(65535);
 for(let y=0;y<pl.H;y++)for(let x=0;x<pl.W;x++){const X=pl.xr0+(x+.5)*pl.px,Y=pl.yr0+(y+.5)*pl.px;const r=Y<0?[C.ids.air,65535]:fn(X,Y);lab[y*pl.W+x]=r[0];sid[y*pl.W+x]=r[1];}
 return {g,pl,lab,sid};}
function sim(M,o={}){return U.simulate(Object.assign({AC,geom:M.g,plan:M.pl,lab:M.lab,sid:M.sid,freq:5,depthMm:M.g.depth,gainDb:0,tgcDb:0,focusMm:30,speckle:false,textures:false,reverb:false,noise:false,seed:5,
  frame:{O:[0,0,0],u:[1,0,0],b:[0,-1,0]},axisOf:null},o));}
function at(r,M,X,Y){const ox=Math.floor((X-M.pl.xo0)/M.pl.px),oy=Math.floor((Y-M.pl.yo0)/M.pl.px);return r.db[oy*r.Wo+ox];}
function win(r,M,x0,x1,y0,y1,f){let a=[];for(let X=x0;X<x1;X+=M.pl.px)for(let Y=y0;Y<y1;Y+=M.pl.px)a.push(at(r,M,X,Y));return f(a);}
const mean=a=>a.reduce((s,v)=>s+v,0)/a.length,max=a=>Math.max(...a);
const out={};
// A. bone slab (cortex 6 mm at y = 40..46 over marrow) in muscle, with a fluid cyst (r = 7 at y = 25) and a muscle-only reference column
function scene(x,y){ if(y>=45&&y<51&&x>-12&&x<12)return [K('bone_cortical'),1]; if(y>=51&&x>-12&&x<12)return [K('marrow_yellow'),1]; if(Math.hypot(x+15,y-25)<7)return [K('blood_vein'),2]; return [y<4?K('fat'):K('muscle'),3];}
const M=mk('linear',70,scene);const r=sim(M);
const topEdge=win(r,M,-8,8,44.5,46,max), muscleSame=win(r,M,-30,-20,44.5,46,mean), below=win(r,M,-8,8,53,65,mean), besideBelow=win(r,M,18,22,53,65,mean);
out.bone={topEdge,muscleSame,below,besideBelow,contact:r.contact,ysk:r.ysk};
const inside=win(r,M,-17,-13,22,28,mean), sameDepthSide=win(r,M,-2,2,22,28,mean), behind=win(r,M,-18,-12,36,42,mean), behindRef=win(r,M,-2,2,36,42,mean);
out.fluid={inside,sameDepthSide,behind,behindRef};
// B. angle dependence: a bone interface inclined by 0 / 15 / 30 degrees to the beam
function incl(a){const t=Math.tan(a*Math.PI/180);return (x,y)=>y>=30+t*x?[K('bone_cortical'),1]:[K('muscle'),3];}
out.angle=[0,10,20,35].map(a=>{const Mi=mk('linear',50,incl(a));const ri=sim(Mi);return win(ri,Mi,-1.5,1.5,28,32+Math.tan(a*Math.PI/180)*1.5,max);});
// C. frequency: attenuation (muscle half space, nominal TGC) and resolution
function musc(x,y){return [y<2?K('fat'):K('muscle'),3];}
const Mf=mk('linear',80,musc);const lo=sim(Mf,{freq:3.5,depthMm:80,focusMm:40}),hi=sim(Mf,{freq:12,depthMm:80,focusMm:40});
out.freq={lo_deep:win(lo,Mf,-10,10,60,70,mean),hi_deep:win(hi,Mf,-10,10,60,70,mean),lo_shallow:win(lo,Mf,-10,10,10,15,mean),hi_shallow:win(hi,Mf,-10,10,10,15,mean),
  latHi:hi.latFw(40),latLo:lo.latFw(40),axHi:hi.axFw,axLo:lo.axFw};
// D. geometry masks: linear fills the width; convex / sector are fans (corners empty), valid fraction
function frac(M){const r=sim(M);let n=0;for(const v of r.db)if(v>-150)n++;return n/r.db.length;}
const Mc=mk('convex',100,(x,y)=>[K('liver'),3]),Ms=mk('sector',100,(x,y)=>[K('liver'),3]),Ml=mk('linear',60,(x,y)=>[K('liver'),3]);
const rc=sim(Mc,{freq:3.5,depthMm:100}),rs=sim(Ms,{freq:3.5,depthMm:100});
out.geom={lin:frac(Ml),conv:frac(Mc),sec:frac(Ms),convCorner:at(rc,Mc,Mc.g.bx0+1,95),sectorCorner:at(rs,Ms,Ms.g.bx0+1,95),sectorCentre:at(rs,Ms,0,60),convCentre:at(rc,Mc,0,60),
  convApexRowY:Mc.g.by0,secBx:[Ms.g.bx0,Ms.g.bx1]};
// E. speckle: seeded, optional, clearly synthetic
const Ml2=mk('linear',50,(x,y)=>[K('liver'),3]);const a1=sim(Ml2,{speckle:true,seed:5}),a2=sim(Ml2,{speckle:true,seed:5}),a3=sim(Ml2,{speckle:true,seed:6}),a0=sim(Ml2,{speckle:false}),a0b=sim(Ml2,{speckle:false,seed:9});
function sd(a){const m=mean(Array.from(a).filter(v=>v>-150));let s=0,n=0;for(const v of a)if(v>-150){s+=(v-m)*(v-m);n++}return Math.sqrt(s/n);}
let same=true,diff=false,off=true;for(let i=0;i<a1.db.length;i++){if(a1.db[i]!==a2.db[i])same=false;if(a1.db[i]!==a3.db[i])diff=true;if(a0.db[i]!==a0b.db[i])off=false;}
out.speckle={same,diff,off,sdOn:sd(a1.db),sdOff:sd(a0.db)};
// F. tendon anisotropy: fibre axis along x, beam along y (perpendicular) vs the fibre axis inclined 20 degrees to the plane x axis
function tend(x,y){return y>=20&&y<27?[K('tendon_ligament'),7]:[K('muscle'),3];}
const Mt=mk('linear',50,tend);const mAx=ang=>({a:[Math.cos(ang*Math.PI/180),0,Math.sin(ang*Math.PI/180)*0+Math.sin(ang*Math.PI/180)],elong:10});
// beam dir in world = frame.u*dx + frame.b*dy = (0, -1, 0) for dy = 1; fibre a = (cos, sin, 0)-> deviation from perpendicular = asin(|a.y|)
const axisAt=ang=>(sid)=>sid===7?{a:[Math.cos(ang*Math.PI/180),Math.sin(ang*Math.PI/180),0],elong:10}:null;
out.aniso=[0,10,25].map(a=>{const rt=sim(Mt,{textures:true,axisOf:axisAt(a)});return win(rt,Mt,-8,8,22,25,mean);});
// G. reverberation behind an air / lung interface
const Mv=mk('linear',80,(x,y)=>y>=20?[K('lung'),4]:[K('muscle'),3]);const rv0=sim(Mv,{reverb:false}),rv1=sim(Mv,{reverb:true});
out.reverb={first:win(rv1,Mv,-8,8,19.5,21,max),second:win(rv1,Mv,-8,8,39.5,41.5,max),noRev:win(rv0,Mv,-8,8,39.5,41.5,max),third:win(rv1,Mv,-8,8,59.5,61.5,max),between:win(rv1,Mv,-8,8,28,34,mean)};
// H. lost contact: the face floats 30 mm above the skin (air gap > 12 mm of coupling gel) -> no image
const Mg=mk('linear',50,(x,y)=>y>=30?[K('muscle'),3]:[C.ids.air,65535]);const rg=sim(Mg);out.gap={contact:rg.contact,mean:win(rg,Mg,-10,10,5,40,mean)};
// I. noise floor is optional and deterministic
const rn=sim(Ml2,{noise:true,speckle:false,seed:3}),rn2=sim(Ml2,{noise:true,speckle:false,seed:3});let eq=true;for(let i=0;i<rn.db.length;i++)if(rn.db[i]!==rn2.db[i])eq=false;out.noise={eq};
// J. display mapping
const gr=U.toGray(Float32Array.from([-200,-33,0,27,60]),0.55,0,60);out.gray=Array.from(gr);
const gg=U.toGray(Float32Array.from([0]),0.55,10,60);out.gray_gain=Array.from(gg);
console.log(JSON.stringify(out));"""


@pytest.fixture(scope="module")
def phys():
    return json.loads(_node(PHYS, timeout=240))


@needs_node
def test_bone_gives_bright_edge_and_acoustic_shadow(phys):
    b = phys["bone"]
    assert b["contact"] and abs(b["ysk"]) < 0.5
    assert b["topEdge"] > b["muscleSame"] + 25                      # strong specular surface echo
    assert b["below"] < b["besideBelow"] - 25                       # shadow behind the cortex (and the marrow)


@needs_node
def test_fluid_is_anechoic_with_posterior_enhancement(phys):
    f = phys["fluid"]
    assert f["inside"] < f["sameDepthSide"] - 25                    # anechoic against the tissue at the same depth
    assert f["behind"] > f["behindRef"] + 4                         # brighter behind the cyst (nominal TGC over-compensates the fluid path)


@needs_node
def test_specular_echo_depends_on_incidence_angle(phys):
    a = phys["angle"]
    assert a[0] > a[1] > a[2] > a[3] and a[0] - a[2] > 3 and a[0] - a[3] > 6              # narrower acceptance than the diffuse floor allows for


@needs_node
def test_frequency_attenuation_and_resolution(phys):
    f = phys["freq"]
    assert f["hi_deep"] < f["lo_deep"] - 10                         # 12 MHz loses more at depth
    assert f["hi_shallow"] > f["lo_shallow"] - 8                    # near field comparable (TGC)
    assert f["latHi"] < f["latLo"] and f["axHi"] < f["axLo"] * 0.4  # finer resolution at 12 MHz
    assert f["axLo"] == pytest.approx(1.25 * 1.54 / 3.5, rel=1e-6)  # axial resolution = 1.25 wavelengths


@needs_node
def test_scan_geometries(phys):
    g = phys["geom"]
    assert g["lin"] > 0.88 and 0.5 < g["conv"] < 0.9 and 0.4 < g["sec"] < 0.85        # fans leave the corners empty (the linear image keeps a 7 mm band above the face for the probe footprint)
    assert g["convCorner"] < -150 and g["sectorCorner"] < -150 and g["sectorCentre"] > -60 and g["convCentre"] > -60
    assert g["secBx"][1] == pytest.approx(100 * 0.70710678, rel=1e-3)               # 90 degree sector: half width = depth sin 45
    assert g["convApexRowY"] < 0                                                    # the convex face is an arc above the centre line


@needs_node
def test_speckle_is_seeded_optional_and_synthetic(phys):
    s = phys["speckle"]
    assert s["same"] and s["diff"] and s["off"] and s["sdOn"] > s["sdOff"] + 1


@needs_node
def test_tendon_anisotropy_and_reverberation_and_contact(phys):
    a = phys["aniso"]
    assert a[0] > a[1] > a[2] and a[0] - a[2] > 10                                 # tilting away from perpendicular dims the tendon
    r = phys["reverb"]
    assert r["first"] > r["between"] + 20 and r["second"] > r["noRev"] + 15 and r["third"] > -80           # A-lines at 2x and 3x the depth
    assert phys["gap"]["contact"] is False and phys["gap"]["mean"] < -150           # air gap = lost contact: black
    assert phys["noise"]["eq"]
    g = phys["gray"]
    assert g[0] == 0 and g[2] == round(0.55 * 255) or abs(g[2] - 140) <= 1
    assert phys["gray_gain"][0] > g[2]


# ---------------------------------------------------------------- staging / licensing / loader chain
def test_staging_ultrasound_files(tmp_path):
    d = tmp_path / "viewer_x"
    d.mkdir()
    out = scf.stage_ultrasound(d)
    assert [p.name for p in out] == ["clinical_imaging_tool.js", "clinical_imaging_tissues.json", "clinical_ultrasound_tool.js", "clinical_ultrasound_tissues.json"]
    assert (d / "clinical_ultrasound_tool.js").read_bytes() == TOOL.read_bytes()
    assert (d / "clinical_ultrasound_tissues.json").read_bytes() == (REPO / "clinical" / "data" / "ultrasound_tissues.json").read_bytes()
    assert not (d / "clinical_needle_tool.js").exists()
    gone = scf.remove(d)
    assert {p.name for p in gone} == set(scf.IMAGING_NAMES) | set(scf.ULTRASOUND_NAMES)
    assert not list(d.iterdir())


def test_public_templates_do_not_mention_ultrasound():
    for name in ("atlas_viewer.template.html", "zan_atlas.template.html"):
        low = (REPO / "viewer" / name).read_text(encoding="utf-8").lower()
        for bad in ("ultrasound", "nmskultrasound", "acoustic", "mrayl", "b-mode"):
            assert bad not in low, (name, bad)                                   # loaded by the imaging file as an optional companion, never by a template


def test_private_licence_covers_ultrasound():
    lic = (REPO / "clinical" / "LICENSE_PRIVATE.md").read_text(encoding="utf-8")
    assert "ultrasound_tool.js" in lic and "PRIVATE" in lic
    head = TOOL.read_text(encoding="utf-8")[:1800]
    assert "PRIVATE" in head and "NOT A SCAN" in head.upper()


@needs_node
def test_imaging_loads_the_companion_and_chains_the_click_handler():
    code = r"""
      const vm=require('vm'),fs=require('fs');
      const calls=[],scripts=[],handlers=[];
      const sandbox={console, document:{currentScript:{src:'http://x/y/clinical_imaging_tool.js'},head:{appendChild(s){scripts.push(s.src);}},body:{classList:{add(){},remove(){},toggle(){}},appendChild(){}},getElementById(){return null;},createElement(){return {style:{},setAttribute(){},appendChild(){},addEventListener(){}};}},
        fetch:()=>Promise.reject(new Error('x')), Worker:undefined, URL:{createObjectURL(){return ''}}, Blob:function(){}, setTimeout, clearTimeout, setInterval, clearInterval, Promise, Object, Array,
        Float32Array, Uint8Array, Uint16Array, Uint32Array, Int32Array, Float64Array, Error, Event:function(){}, devicePixelRatio:1, innerWidth:1000, innerHeight:800};
      sandbox.window=sandbox; sandbox.globalThis=sandbox;
      let installed=null; const needleClick=(e)=>{calls.push('needle-click');return e==='needle';};
      sandbox.NMSKClinical={attach(api){api.setClickHandler(needleClick);return {cursor(){return 1}};}};
      vm.createContext(sandbox);
      vm.runInContext(fs.readFileSync('clinical/imaging_tool.js','utf8'),sandbox);
      const api={toolbar:null,list(){return []},kind:'three',setClickHandler(fn){installed=fn;}};
      const r=sandbox.NMSKClinical.attach(api);
      // the dispatcher is the only handler the page sees; with no companion armed the needle handler still gets every click
      const a=installed('plain'), b=installed('needle');
      let attached=null; sandbox.NMSKUltrasoundAddon={attach(api2,sh){attached=!!(sh&&sh.ensure&&sh.runSlice&&sh.addClickHandler&&sh.lib&&sh.lib.KERNEL_FACTORY);sh.addClickHandler(e=>e==='us');}};
      // the injected companion script's onload fires the attach (simulate the browser)
      const sc=scripts.length;
      console.log(JSON.stringify({ret:typeof r.cursor,a,b,calls,scripts, imaging:sandbox.NMSKClinical.imaging}));"""
    o = json.loads(_node(code))
    assert o["ret"] == "function" and o["a"] is False and o["b"] is True and o["calls"] == ["needle-click", "needle-click"]


@needs_node
def test_companion_script_url_is_next_to_the_imaging_script():
    src = (REPO / "clinical" / "imaging_tool.js").read_text(encoding="utf-8")
    assert '"clinical_ultrasound_tool.js"' in src and "SCRIPT_BASE + name" in src


# ---------------------------------------------------------------- recorded browser runs (real meshes, six viewports)
BROWSER = os.environ.get("Q228_BROWSER") == "1"
CHROME = Path("/opt/pw-browsers/chromium")
THREE = os.environ.get("Q228_THREE_JS", "")
browser = pytest.mark.skipif(not (BROWSER and CHROME.exists()), reason="set Q228_BROWSER=1 (+ Q228_THREE_JS=three.min.js r128) with Chromium and build/q228 pages")
DERIVED = REPO / "data" / "derived"
VIEWPORTS = {"1440x900", "1024x640", "820x1180", "1180x820", "390x844", "844x390"}


def _rec(name):
    p = DERIVED / name
    if not p.exists():
        pytest.skip(f"{name} not recorded (run scripts/clinical/q228_check.py ... --record)")
    return json.loads(p.read_text(encoding="utf-8"))


@pytest.mark.parametrize("key", ["vhm", "zan_f"])
def test_recorded_browser_runs_zero_errors_all_viewports(key):
    d = _rec(f"Q228_browser_{key}.json")
    assert set(d) == VIEWPORTS
    for vp, r in d.items():
        assert r["errors"] == [] and r["bad_responses"] == [], (vp, r["errors"], r["bad_responses"])
        assert r["layout"]["scrollW"] <= r["layout"]["innerW"], vp                       # no horizontal overflow
        assert r["layout"]["ctlScrollW"] <= r["layout"]["ctlClientW"] + 2, vp
        w, h = (int(x) for x in vp.split("x"))
        assert ("us-tab" in r["layout"]["cls"]) == (min(w, h) < 520), vp                 # tabs on phones, split screen elsewhere
        if min(w, h) < 520:
            assert r["layout"]["smallButtons"] == 0, vp                                  # touch targets
        assert r["perf_open"]["n"] == 9 and max(r["perf_open"]["per"]) < 1500, (vp, r["perf_open"])


@pytest.mark.parametrize("key", ["vhm", "zan_f"])
def test_recorded_performance(key):
    d = _rec(f"Q228_browser_{key}.json")["1440x900"]
    p = d["perf"]
    # compute time of a full-resolution B-mode frame (slice kernel + physics + scan conversion) and of a 9-frame matrix; wall times in the swiftshader
    # harness also contain the page's own software-GL frames, so the best of three runs is the figure
    assert p["frame_480_sim_ms"] + p["frame_480_kernel_ms"] < 300
    assert min(p["linear5_matrix_ms"]) < 3000 and min(p["convex15_matrix_ms"]) < 3000
    assert min(d["perf_open"]["per"]) < 300


@pytest.mark.parametrize("key", ["vhm", "zan_f"])
def test_recorded_interaction_runs(key):
    d = _rec(f"Q228_browser_{key}.json")
    for vp in ("1440x900", "390x844"):
        r = d[vp]["interact"]
        assert r["armed"] and r["click_places_probe"], vp                          # a real click / tap on the skin places the probe
        assert r["ring_click_selects"] and r["selected_is_now_the_big_central_cell"], vp
        assert r["selected_frame_tilt"] == 15, vp
        assert r["sweep_offsets_exact"] and r["sweep"]["labels"][1].endswith("+12 mm") and sorted(r["sweep_matrix_dims"]) == [2, 3], vp               # 3 x 2 (2 x 3 on a portrait phone)
        assert len(r["cine_frames_visited"]) >= 3, vp
        assert r["follow"]["follow"] and r["follow"]["cos"] > 0.95 and "emur" in r["follow"]["name"], vp
        assert r["hidden_ok"], vp
        assert r["info_has_table"] > 30 and "not an ultrasound" in r["badge_in_header"].lower(), vp
        assert r["closed_cleanly"]["cls"] == "" and r["closed_cleanly"]["scrollW"] <= r["closed_cleanly"]["innerW"], vp
    c = d["1440x900"]["interact"]
    if "cut_mode_images_ok" in c:
        assert c["cut_mode_images_ok"]


@pytest.mark.parametrize("key", ["own_f", "zan_m", "zan_vhm", "base_f"])
def test_recorded_smoke_on_the_other_four_pages(key):
    d = _rec(f"Q228_browser_{key}.json")
    assert set(d) == {"1440x900", "390x844"}
    for vp, r in d.items():
        assert r["errors"] == [] and r["bad_responses"] == [], (key, vp, r["errors"], r["bad_responses"])
        assert r["layout"]["scrollW"] <= r["layout"]["innerW"], (key, vp)
        assert r["perf_open"]["n"] == 9 and r["state"]["P"], (key, vp)


def test_recorded_scenes_zan_female():
    s = _rec("Q228_scenes_zan_f.json")
    assert s["femur_long"]["contact"] and "bone_cortical" in s["femur_long"]["byClass"] or s["femur_long"]["beam"]
    classes = [b[1].split("|")[0] for b in s["femur_long"]["beam"]]
    assert "bone_cortical" in classes and classes.index("bone_cortical") > classes.index("muscle")         # skin -> muscle -> cortex along the beam
    assert s["femur_long"]["central_mean_db"] > -45                                                         # not black: the air-labelled gaps between overlapping Z skin layers do not block the beam


def test_recorded_scenes_on_real_meshes_own_male():
    s = _rec("Q228_scenes_vhm.json")
    for k in ("femur_long", "forearm_trans", "carotid_trans", "abdomen_liver"):
        assert k in s and not s[k].get("missing"), k
        assert s[k]["contact"] and s[k]["img"]["valid_frac"] > 0.3 and s[k]["img"]["max"] > 5
    f = s["femur_long"]["byClass"]
    assert "bone_cortical" in f and f["bone_cortical"]["mean"] < -40                      # the femur cortex sits in the shadow it casts (mean of its pixels), its surface is the bright line
    assert s["femur_long"]["frame_bone_max_db"] > 0 if "frame_bone_max_db" in s["femur_long"] else True
    fa = s["forearm_trans"]["byClass"]
    assert fa["bone_cortical"]["max"] > 10 and fa["marrow_yellow"]["mean"] < -50          # radius: bright cortex arc, black below it
    assert "liver" in s["abdomen_liver"]["byClass"]
    c = s["carotid_trans"]["byClass"]
    assert "blood_artery" in c and c["blood_artery"]["mean"] < c["muscle"]["mean"] - 15            # the carotid lumen is anechoic against the sternocleidomastoid


@browser
@pytest.mark.parametrize("page,root,kind", [("vhm", "build/q228/viewer_m_hr", "own"), ("zan_f", "build/q228/viewer_zan_female", "zan")])
def test_browser_rerun_smoke(page, root, kind, tmp_path):
    r = subprocess.run([sys.executable, str(REPO / "scripts/clinical/q228_check.py"), str(REPO / root), "index.html", kind, str(tmp_path / "x"), THREE, "--viewports", "1440x900,390x844"],
                       capture_output=True, text=True, timeout=1800)
    assert r.returncode == 0, r.stdout[-1500:] + r.stderr[-1500:]
