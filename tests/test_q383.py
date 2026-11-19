"""Q383 -- the scan kernel after the owner's "very low level" verdict: structure sheaths as interfaces, an array's beam, a gain
curve that follows the tissue, septa as specular sheets, clean bone shadow (node, synthetic rasters; no browser)."""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(not NODE, reason="node not installed")
TABLE = json.loads((REPO / "clinical" / "data" / "ultrasound_tissues.json").read_text(encoding="utf-8"))

JS = r"""
require('./clinical/imaging_tool.js'); require('./clinical/ultrasound_tool.js');
const I=globalThis.NMSKImagingLib,U=globalThis.NMSKUltrasoundLib;
const T=require('./clinical/data/imaging_tissues.json'),US=require('./clinical/data/ultrasound_tissues.json');
const C=I.compileTable(T),AC=U.compileAcoustics(US,C),K=k=>C.by[k]._i;
function mk(depth,fn){const g=U.fanGeom('linear',44,0,0,depth),pl=U.planRaster(g,420);const lab=new Uint8Array(pl.W*pl.H),sid=new Uint16Array(pl.W*pl.H).fill(65535);
 for(let y=0;y<pl.H;y++)for(let x=0;x<pl.W;x++){const X=pl.xr0+(x+.5)*pl.px,Y=pl.yr0+(y+.5)*pl.px;const r=Y<0?[C.ids.air,65535]:fn(X,Y);lab[y*pl.W+x]=r[0];sid[y*pl.W+x]=r[1];}return {g,pl,lab,sid};}
function sim(M,o={}){return U.simulate(Object.assign({AC,geom:M.g,plan:M.pl,lab:M.lab,sid:M.sid,freq:10,depthMm:M.g.depth,gainDb:0,tgcDb:0,focusMm:M.g.depth/2,speckle:false,textures:true,reverb:true,noise:false,seed:5,
  frame:{O:[0,0,0],u:[1,0,0],b:[0,-1,0],e:[0,0,1]},axisOf:null},o));}
function at(r,M,X,Y){const ox=Math.floor((X-M.pl.xo0)/M.pl.px),oy=Math.floor((Y-M.pl.yo0)/M.pl.px);return r.db[oy*r.Wo+ox];}
function win(r,M,x0,x1,y0,y1,f){let a=[];for(let X=x0;X<x1;X+=M.pl.px)for(let Y=y0;Y<y1;Y+=M.pl.px)a.push(at(r,M,X,Y));return f(a);}
const mean=a=>a.reduce((s,v)=>s+v,0)/a.length,max=a=>Math.max(...a);
const out={};
// A. two muscle meshes (ids 3 | 4) that touch along a line inclined by a degrees: no change of tissue class, only of structure
function two(a){const t=Math.tan(a*Math.PI/180);return (x,y)=>[y<2?K('fat'):K('muscle'),y<2?65535:(y>=20+t*x?4:3)];}
out.sheath=[0,20,45,80].map(a=>{const M=mk(40,two(a)),r=sim(M),t=Math.tan(a*Math.PI/180);return win(r,M,-1,1,20-Math.abs(t)-0.8,20+Math.abs(t)+0.8,max)-win(r,M,-8,8,8,14,mean);});
const M0=mk(40,two(0));out.noSheath=win(sim(M0,{sheath:false}),M0,-1,1,19.2,20.8,max)-win(sim(M0,{sheath:false}),M0,-8,8,8,14,mean);
out.sheathR={muscle:AC.shR[K('muscle')],nerve:AC.shR[K('nerve')],artery:AC.shR[K('blood_artery')],bone:AC.shR[K('bone_cortical')],fat:AC.shR[K('fat')]};
// B. a muscle half space under a strongly attenuating sheet (the fascia row): like tissue alike with depth; the nominal curve does not
function half(x,y){return [y<2?K('fat'):y<3.2?K('tendon_ligament'):K('muscle'),y<2?65535:y<3.2?7:3];}
const Mh=mk(40,half),ra=sim(Mh,{textures:false}),rf=sim(Mh,{textures:false,tgcFixed:true});
out.tgc={autoTop:win(ra,Mh,-10,10,6,10,mean),autoDeep:win(ra,Mh,-10,10,30,36,mean),fixTop:win(rf,Mh,-10,10,6,10,mean),fixDeep:win(rf,Mh,-10,10,30,36,mean),auto:ra.tgc.auto,fixed:rf.tgc.auto};
// C. the beam: lateral width near the skin, at the focus, deep; D. bone: bright edge, clean shadow, no ghost at twice its depth
out.beam=[2,5,20,38].map(s=>ra.latFw(s));
function bone(x,y){return [y<2?K('fat'):y>=15&&y<21?K('bone_cortical'):y>=21?K('marrow_yellow'):K('muscle'),y<2?65535:y>=15?9:3];}
const Mb=mk(40,bone),rb=sim(Mb,{textures:false});
out.bone={edge:win(rb,Mb,-8,8,14.4,15.8,max),muscle:win(rb,Mb,-8,8,6,12,mean),ghost:win(rb,Mb,-8,8,29,31.5,max),shadow:win(rb,Mb,-8,8,23,28,mean)};
// E. septa: a muscle whose fibres lie along x (plane lateral) = a long-axis view; along z (out of plane) = a short-axis view
function musc(x,y){return [y<2?K('fat'):K('muscle'),y<2?65535:3];}
const Mm=mk(30,musc);
function runs(r){let tot=0,n=0;const W=r.Wo,H=r.Ho;const v=[];for(let i=0;i<r.db.length;i++)if(r.db[i]>-150)v.push(r.db[i]);v.sort((a,b)=>a-b);const th=v[Math.floor(v.length*0.5)]+6;
  for(let y=Math.floor(H*0.3);y<Math.floor(H*0.9);y++){let run=0;for(let x=0;x<W;x++){if(r.db[y*W+x]>th)run++;else{if(run>0){tot+=run;n++;}run=0;}}if(run>0){tot+=run;n++;}}return n?tot/n*Mm.pl.px:0;}
out.runLong=runs(sim(Mm,{axisOf:()=>({a:[1,0,0],elong:10})}));out.runShort=runs(sim(Mm,{axisOf:()=>({a:[0,0,1],elong:10})}));
// F. fat lobules: septa present with textures, absent without
function fat(x,y){return [K('fat'),65535];}
const Mf=mk(30,fat);function sd(r){const a=[];for(const v of r.db)if(v>-150)a.push(v);const m=mean(a);return Math.sqrt(mean(a.map(v=>(v-m)*(v-m))));}
out.fat={on:sd(sim(Mf)),off:sd(sim(Mf,{textures:false})),n:sim(Mf).stats.fatSamples};
console.log(JSON.stringify(out));"""


@pytest.fixture(scope="module")
def o():
    r = subprocess.run([NODE, "-e", JS], capture_output=True, text=True, timeout=240, cwd=str(REPO))
    assert r.returncode == 0, r.stderr[-2500:]
    return json.loads(r.stdout)


@needs_node
def test_a_structure_boundary_inside_one_tissue_class_is_a_bright_line_that_fades_with_the_angle(o):
    s = o["sheath"]
    assert s[0] > 15 and s[0] > s[2] > s[3]            # square to the beam: > 15 dB above the muscle; 45 deg dimmer; along the beam nearly gone
    assert s[0] - s[3] > 12 and s[3] < 8
    assert o["noSheath"] < 3                            # without the rule there is nothing there: the two meshes are one tissue class
    r = o["sheathR"]
    assert r["muscle"] == pytest.approx(2 * ((1.9 - 1.7) / (1.9 + 1.7)) ** 2, rel=1e-4)     # two faces of a collagen layer, from the table's own impedances
    assert r["nerve"] > r["muscle"] and r["artery"] > r["muscle"] and r["bone"] == 0 and r["fat"] == 0


@needs_node
def test_the_gain_follows_the_tissue_and_the_nominal_curve_is_still_available(o):
    t = o["tgc"]
    assert t["auto"] is True and t["fixed"] is False
    assert abs(t["autoTop"] - t["autoDeep"]) < 2.5      # muscle reads alike at 8 mm and at 33 mm
    assert t["fixTop"] - t["fixDeep"] > 12              # the fixed 0.6 dB/cm/MHz curve: 8 dB darker per centimetre of muscle at 10 MHz


@needs_node
def test_the_beam_is_an_array_s_and_bone_leaves_a_clean_shadow(o):
    b = o["beam"]
    assert max(b) <= 1.0 and b[0] <= 1.0                # was 8 mm at the skin with a fixed-focus beam
    k = o["bone"]
    assert k["edge"] > k["muscle"] + 25 and k["shadow"] < k["muscle"] - 25
    assert k["ghost"] < k["muscle"] - 25                # no repeat of the cortex at twice its depth (reverberation is for gas only)


@needs_node
def test_septa_are_lines_along_the_fibres_and_short_marks_across_them(o):
    assert o["runLong"] > 3.0 and o["runLong"] > 2.5 * o["runShort"]          # mean length (mm) of a bright run along an image row
    assert o["fat"]["n"] > 1000 and o["fat"]["on"] > o["fat"]["off"] + 0.5      # fat lobules: septa only with the textures on


def test_table_rows_added_in_q383_carry_their_status_and_sources():
    g, refs = TABLE["global"], TABLE["references"]
    assert g["beam"]["array"] is True and g["beam"]["status"] == "assumption"
    assert g["tgc"]["auto"] is True and g["tgc"]["status"] == "convention" and g["tgc"]["max_db"] == 90
    sh = TABLE["interfaces"]["sheath"]
    assert sh["status"] == "rule" and set(sh["classes"]) == {"muscle", "nerve", "blood_artery", "blood_vein"} and "schleip2015" in sh["src"]
    assert TABLE["artefacts"]["reverb"]["r_min"] > 0.41                         # above a bone surface (muscle | cortical bone R = 0.41)
    for k in ("pillen2011", "peetrons2002", "silvestri1995", "schleip2015"):
        assert k in refs and refs[k]["basis"]
    assert refs["pillen2011"]["pmid"] == "22196753" and refs["silvestri1995"]["pmid"] == "7568840" and refs["peetrons2002"]["pmid"] == "11868072"
    assert TABLE["textures"]["fat"]["status"] == "assumption" and TABLE["classes"]["fat"]["texture"] == "fat"
