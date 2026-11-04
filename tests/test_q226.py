"""Q226 -- imaging add-on (simulated CT / MRI of the cut plane): tissue table, mapping coverage, kernel numerics, MR equations,
staging / licensing, and (opt-in, needs Chromium + the staged pages) browser checks on real meshes.

Fast tests (default): table schema + citations, JS==Python classification on every page that is built, mapping reports, kernel on
synthetic meshes under node, MR / CT lookup equations, staging, "templates carry only the generic hook".
Browser tests: set Q226_BROWSER=1 (needs build/q226/<page> from scripts/regen_imaging_q226.sh and /opt/pw-browsers/chromium).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "clinical"))
import q226_mapping_report as mr  # noqa: E402
import q226_structures as qs  # noqa: E402
import stage_clinical_files as scf  # noqa: E402

TABLE = json.loads((REPO / "clinical" / "data" / "imaging_tissues.json").read_text(encoding="utf-8"))
TOOL = REPO / "clinical" / "imaging_tool.js"
NODE = shutil.which("node")
STATUSES = {"verified", "secondary_checked", "recalled_unverified", "derived", "assumption"}                      # Q229: verified_abstract -> verified
needs_node = pytest.mark.skipif(not NODE, reason="node not installed")


def _node(code: str, timeout=120):
    r = subprocess.run([NODE, "-e", code], capture_output=True, text=True, timeout=timeout, cwd=str(REPO))
    assert r.returncode == 0, r.stderr[-2000:]
    return r.stdout


def _built(key):
    d, html, _ = qs.PAGES[key]
    return (REPO / d / html).is_file()


# ---------------------------------------------------------------- table schema + citations
def test_table_schema():
    assert TABLE["schema"] == "nmsk.imaging_tissues.v1"
    keys = [c["key"] for c in TABLE["classes"]]
    assert len(keys) == len(set(keys)), "duplicate class keys"
    assert len(keys) < 200 and keys[0] == "air"                      # class ids are uint8; air must be id 0 (the kernel's exterior)
    for must in ("air", "fat", "skin", "muscle", "bone_cortical", "bone_cancellous", "marrow_yellow", "blood_artery", "blood_vein", "liver", "kidney",
                 "lung", "fluid_free", "brain_wm", "brain_gm", "cartilage", "tendon_ligament", "soft_unassigned", "synovial", "nerve", "spleen"):
        assert must in keys, must
    refs = TABLE["references"]
    for c in TABLE["classes"]:
        assert isinstance(c["priority"], (int, float))
        ct, m = c["ct"], c["mri"]
        assert isinstance(ct["hu"], (int, float)) and len(ct["range"]) == 2 and ct["range"][0] <= ct["hu"] <= ct["range"][1], c["key"]
        assert ct["status"] in STATUSES and m["status"] in STATUSES, c["key"]
        assert ct["src"] and m["src"], f"{c['key']}: every row cites a source"
        for k in ct["src"] + m["src"]:
            assert k in refs, f"{c['key']}: unknown reference {k}"
        assert m["pools"] and abs(sum(p["frac"] for p in m["pools"]) - 1) < 1e-9, c["key"]
        for p in m["pools"]:
            assert 0 <= p["pd"] <= 1.0 and p["t1"] > 0 and p["t2"] > 0 and p["t2s"] > 0, c["key"]
            assert isinstance(p["fat"], bool)
        # Q229: every value has a 'ver' entry; a part's status is the weakest of its values; 'verified' needs an OPENED source
        for part, fields in ((ct, ("hu",)), (m, ("pd", "t1", "t2", "t2s"))):
            assert set(part["ver"]) == set(fields), c["key"]
            rank = {"recalled_unverified": 0, "assumption": 1, "secondary_checked": 2, "derived": 3, "verified": 4}
            assert part["status"] == min((e["s"] for e in part["ver"].values()), key=rank.get), c["key"]
            for f, e in part["ver"].items():
                assert e["s"] in STATUSES and e["d"] and e["src"], (c["key"], f)
                for k in e["src"]:
                    assert k in refs, (c["key"], f, k)
                if e["s"] == "verified":
                    assert any(refs[k].get("pubmed_checked") or refs[k].get("opened") for k in e["src"]), (c["key"], f)
                if e["s"] == "recalled_unverified":
                    assert e["d"].startswith("not verified"), (c["key"], f)       # one-line reason
    # CT scale fixed points
    by = {c["key"]: c for c in TABLE["classes"]}
    assert by["air"]["ct"]["hu"] == -1000 and by["fat"]["ct"]["hu"] < -50 and by["bone_cortical"]["ct"]["hu"] > 800
    assert -950 < by["lung"]["ct"]["hu"] < -600 and 0 <= by["fluid_free"]["ct"]["hu"] <= 15


def test_q229_verification_report_matches_table():
    rep = json.loads((REPO / "data" / "derived" / "Q229_tissue_verification.json").read_text(encoding="utf-8"))
    summ = TABLE["verification_summary"]
    vals = [(c["key"], p, f, c[p]["ver"][f]["s"]) for c in TABLE["classes"] for p, fs in (("ct", ("hu",)), ("mri", ("pd", "t1", "t2", "t2s"))) for f in fs]
    assert rep["totals"]["numeric_values"] == summ["numeric_values"] == len(vals) == 33 * 5
    for s, n in summ["counts"].items():
        assert n == sum(1 for v in vals if v[3] == s) == rep["totals"][s], s
    assert rep["totals"]["still_unverified"] == len(vals) - rep["totals"]["verified"] - rep["totals"]["derived"]
    assert rep["totals"]["changed_gt_10pct"] == summ["changed_gt_10pct"] == len(rep["changed_gt_10pct"])
    assert len(rep["tissues"]) == len(TABLE["classes"])
    assert "Q229" in " ".join(TABLE["honesty"])                                # the panel's info text carries the status line
    # the honesty line quotes the same counts as the report
    line = [h for h in TABLE["honesty"] if h.startswith("Q229 verification")][0]
    assert f"{summ['counts']['verified']} verified" in line and f"{summ['counts']['recalled_unverified']} recalled" in line


def test_references_are_citable():
    refs = TABLE["references"]
    pm = {k: r for k, r in refs.items() if r.get("pmid")}
    assert len(pm) >= 10
    for k, r in pm.items():
        assert re.fullmatch(r"\d{6,9}", r["pmid"]), k
        assert r["pubmed_checked"] is True, k
        assert r["cite"] and r["used_for"], k
    # the papers the owner asked for by name
    assert refs["bottomley1984"]["pmid"] == "6482839" and refs["gold2004"]["pmid"] == "15269023" and refs["debazelaire2004"]["pmid"] == "14990831"
    assert "icru44" in refs and refs["icru44"]["pmid"] is None
    # honesty: statuses are explained, and nothing is passed off as a scan
    text = " ".join(TABLE["honesty"]).lower()
    assert "not a scan" in text and "recalled_unverified" in text and "unverified" in text


def test_windows_and_sequences():
    w = {x["key"]: x for x in TABLE["ct_windows"]}
    assert (w["soft"]["width"], w["soft"]["level"]) == (400, 40) and (w["bone"]["width"], w["bone"]["level"]) == (1800, 400)
    assert (w["lung"]["width"], w["lung"]["level"]) == (1500, -600) and (w["brain"]["width"], w["brain"]["level"]) == (80, 40) and "msk" in w
    s = {x["key"]: x for x in TABLE["mr_sequences"]}
    for k in ("t1_se", "t2_se", "pd_se", "pd_fs", "t2_fs", "stir", "t2s_gre", "t1_se_gd"):
        assert k in s, k
    for x in s.values():
        assert x["tr"] > 0 and x["te"] >= 0 and x["kind"] in ("se", "ir", "gre") and 0 < x["fa"] <= 90
    assert s["stir"]["kind"] == "ir" and s["stir"]["ti"] > 0 and s["pd_fs"]["fatsat"] and s["t1_se_gd"]["gd"]


# ---------------------------------------------------------------- mapping rules
def test_rules_reference_known_classes():
    keys = {c["key"] for c in TABLE["classes"]}
    for r in TABLE["mapping_rules"]["rules"]:
        assert r["cls"] in keys
        if r.get("re"):
            re.compile(r["re"], re.I)
    assert TABLE["mapping_rules"]["fallback"]["cls"] == "soft_unassigned"
    for r in TABLE["mapping_rules"]["rules"]:
        if r.get("kind"):
            assert r["kind"] in TABLE["bone_model"]["kinds"]


@pytest.mark.parametrize("page", list(qs.PAGES))
def test_mapping_coverage_report(page):
    if not _built(page) and not (REPO / qs.STAGED[page][0] / qs.STAGED[page][1]).is_file():
        pytest.skip(f"{page} page not built here")
    rep = mr.report(page)
    out = REPO / "data" / "derived" / f"Q226_mapping_{page}.json"
    out.write_text(json.dumps(rep, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    assert rep["structures"] > 500
    assert rep["coverage"] >= 0.99, rep["unassigned_structures"][:10]
    assert rep["unassigned"] == len(rep["unassigned_structures"])
    assert "bone_cortical" in rep["by_class"] and rep["bone_kinds"].get("long", 0) >= 2     # at least the femora


@needs_node
@pytest.mark.parametrize("page", list(qs.PAGES))
def test_js_and_python_classify_identically(page, tmp_path):
    if not _built(page) and not (REPO / qs.STAGED[page][0] / qs.STAGED[page][1]).is_file():
        pytest.skip(f"{page} page not built here")
    S = qs.page_structures(page)
    rules = mr.compile_rules(TABLE)
    py = [mr.classify(rules, TABLE, s) for s in S]
    f = tmp_path / "s.json"
    f.write_text(json.dumps(S), encoding="utf-8")
    code = f"""
      require('./clinical/imaging_tool.js'); const L=globalThis.NMSKImagingLib;
      const T=require('./clinical/data/imaging_tissues.json'); const C=L.compileTable(T);
      const S=JSON.parse(require('fs').readFileSync({json.dumps(str(f))},'utf8'));
      console.log(JSON.stringify(S.map(s=>{{const c=L.classify(C,s);return [T.classes[c.cls].key,c.kind,c.rule,c.render];}})));"""
    js = json.loads(_node(code))
    assert len(js) == len(py)
    bad = [(S[i]["id"], js[i], py[i]) for i in range(len(S)) if js[i][0] != py[i]["cls"] or js[i][1] != py[i]["kind"] or js[i][2] != py[i]["rule"] or js[i][3] != py[i]["render"]]
    assert not bad, bad[:5]


# ---------------------------------------------------------------- MR / CT equations
@needs_node
def test_mr_signal_equations_and_contrast():
    code = """
      require('./clinical/imaging_tool.js'); const L=globalThis.NMSKImagingLib;
      const T=require('./clinical/data/imaging_tissues.json'); const C=L.compileTable(T);
      const seq=k=>JSON.parse(JSON.stringify(T.mr_sequences.find(s=>s.key===k)));
      const id=k=>C.by[k]._i, out={};
      // closed forms (norm removed: compare ratios)
      const mu=T.classes[id('muscle')].mri.pools[0], li=T.classes[id('liver')].mri.pools[0], fa=T.classes[id('fat')].mri.pools[0];
      const se=(p,P)=>p.pd*(1-Math.exp(-P.tr/p.t1))*Math.exp(-P.te/p.t2);
      let P=seq('t1_se'); let m=L.mrTable(C,P);
      out.t1_ratio=[m.sig[id('liver')]/m.sig[id('muscle')], se(li,P)/se(mu,P)];
      out.t1_fat_gt_muscle=m.sig[id('fat')]>m.sig[id('muscle')];
      P=seq('t2_se'); m=L.mrTable(C,P); out.t2_ratio=[m.sig[id('fluid_free')]/m.sig[id('muscle')], se(T.classes[id('fluid_free')].mri.pools[0],P)/se(mu,P)];
      out.t2_csf_gt_fat=m.sig[id('fluid_free')]>m.sig[id('fat')]; out.t2_fat_gt_muscle=m.sig[id('fat')]>m.sig[id('muscle')];
      // fat sat
      P=seq('t2_se'); const ma=L.mrTable(C,P); const a=ma.sig.map(x=>x*ma.norm); P=seq('t2_fs'); P.te=seq('t2_se').te; P.tr=seq('t2_se').tr; const mb=L.mrTable(C,P); const b=mb.sig.map(x=>x*mb.norm);
      out.fs_fat=b[id('fat')]/a[id('fat')]; out.fs_muscle=b[id('muscle')]/a[id('muscle')];
      // STIR: TI = ln2*T1(fat) nulls fat
      P=seq('stir'); P.ti=Math.log(2)*fa.t1; P.tr=1e5; m=L.mrTable(C,P); out.stir_fat=m.sig[id('fat')]; out.stir_muscle=m.sig[id('muscle')];
      // FLAIR: TI=ln2*T1(CSF)
      P=seq('flair'); const cs=T.classes[id('fluid_free')].mri.pools[0]; P.ti=Math.log(2)*cs.t1; P.tr=1e5; m=L.mrTable(C,P); out.flair_csf=m.sig[id('fluid_free')]; out.flair_gm=m.sig[id('brain_gm')];
      // gre: ernst angle behaviour + T2* decay
      P=seq('t2s_gre'); P.te=5; const s5=L.mrTable(C,P); P.te=40; const s40=L.mrTable(C,P);
      out.t2s_decay_cortical=L.mrTable(C,P).sig[id('bone_cortical')];
      out.gre_liver_decay=(s40.sig[id('liver')]*s40.norm)/(s5.sig[id('liver')]*s5.norm);
      out.gre_liver_decay_expected=Math.exp(-35/T.classes[id('liver')].mri.pools[0].t2s);
      // post-gadolinium
      const mpre=L.mrTable(C,seq('t1_se')), mpost=L.mrTable(C,seq('t1_se_gd')); const pre=mpre.sig.map(x=>x*mpre.norm), post=mpost.sig.map(x=>x*mpost.norm);
      out.gd_blood_vs_muscle=[pre[id('blood_vein')]/pre[id('muscle')], post[id('blood_vein')]/post[id('muscle')]];
      out.gd_liver_up=post[id('liver')]/pre[id('liver')]; out.gd_fat_same=post[id('fat')]/pre[id('fat')];
      // flow: void on SE, inflow on GRE
      { const q=seq('t2_se'); const m1=L.mrTable(C,q); q.flow='none'; const m0=L.mrTable(C,q); out.flow_void=(m1.sig[id('blood_artery')]*m1.norm)/(m0.sig[id('blood_artery')]*m0.norm);
        const g=seq('t2s_gre'); const g1=L.mrTable(C,g); g.flow='none'; const g0=L.mrTable(C,g); out.flow_inflow=(g1.sig[id('blood_artery')]*g1.norm)/(g0.sig[id('blood_artery')]*g0.norm); }
      const ct=L.ctTable(C); out.ct=[ct[id('air')],ct[id('fat')],ct[id('fluid_free')],ct[id('muscle')],ct[id('bone_cortical')]];
      console.log(JSON.stringify(out));"""
    o = json.loads(_node(code))
    assert o["t1_ratio"][0] == pytest.approx(o["t1_ratio"][1], rel=1e-6)
    assert o["t2_ratio"][0] == pytest.approx(o["t2_ratio"][1], rel=1e-6)
    assert o["t1_fat_gt_muscle"] and o["t2_csf_gt_fat"] and o["t2_fat_gt_muscle"]           # textbook contrast ordering
    assert o["fs_fat"] == pytest.approx(TABLE["mr_global"]["fat_suppression_residual"], rel=1e-6) and o["fs_muscle"] == pytest.approx(1.0, rel=1e-6)
    assert o["stir_fat"] < 1e-9 and o["stir_muscle"] > 0.1                                   # nulled
    assert o["flair_csf"] < 1e-9 and o["flair_gm"] > 0.1
    assert o["t2s_decay_cortical"] < 1e-3
    assert o["gre_liver_decay"] == pytest.approx(o["gre_liver_decay_expected"], rel=1e-5)
    assert o["gd_blood_vs_muscle"][1] > 2 * o["gd_blood_vs_muscle"][0]
    assert o["gd_liver_up"] > 1.2 and o["gd_fat_same"] == pytest.approx(1.0, rel=1e-9)
    assert o["flow_void"] < 0.2 and o["flow_inflow"] > 1.5                                   # SE flow void, GRE inflow (schematic)
    assert o["ct"][0] == -1000 and o["ct"][1] < o["ct"][2] < o["ct"][3] < o["ct"][4]


# ---------------------------------------------------------------- kernel on synthetic meshes
KERNEL_TEST = r"""
require('./clinical/imaging_tool.js'); const L=globalThis.NMSKImagingLib;
const T=require('./clinical/data/imaging_tissues.json'); const C=L.compileTable(T);
function cyl(r,y0,y1,nseg,cx=0,cz=0){const pos=[],idx=[];for(let i=0;i<nseg;i++){const a=2*Math.PI*i/nseg;pos.push(cx+r*Math.cos(a),y0,cz+r*Math.sin(a));pos.push(cx+r*Math.cos(a),y1,cz+r*Math.sin(a));}
  pos.push(cx,y0,cz,cx,y1,cz);const c0=2*nseg,c1=c0+1;for(let i=0;i<nseg;i++){const j=(i+1)%nseg;const a=2*i,b=2*i+1,c=2*j,d=2*j+1;idx.push(a,c,b,b,c,d,c0,c,a,c1,b,d);}return {pos:Float32Array.from(pos),idx:Uint32Array.from(idx)};}
function sphere(r,cx,cy,cz,n=32){const pos=[],idx=[];for(let i=0;i<=n;i++){const th=Math.PI*i/n;for(let j=0;j<n;j++){const ph=2*Math.PI*j/n;pos.push(cx+r*Math.sin(th)*Math.cos(ph),cy+r*Math.cos(th),cz+r*Math.sin(th)*Math.sin(ph));}}
 for(let i=0;i<n;i++)for(let j=0;j<n;j++){const a=i*n+j,b=i*n+(j+1)%n,c=(i+1)*n+j,d=(i+1)*n+(j+1)%n;idx.push(a,b,c,b,d,c);}return {pos:Float32Array.from(pos),idx:Uint32Array.from(idx)};}
const K=(k)=>C.by[k]._i;
const parts=[{g:cyl(100,-500,500,96),cls:C.ids.skin,kind:0,skin:1},{g:cyl(14,-200,200,64,30,0),cls:K('bone_cortical'),kind:1,skin:0},
 {g:sphere(20,-40,0,0),cls:K('liver'),kind:0,skin:0},{g:sphere(8,-40,0,0),cls:K('blood_artery'),kind:0,skin:0},{g:cyl(12,-300,300,48,-60,60),cls:K('muscle'),kind:0,skin:0}];
let nv=0,nt=0;parts.forEach(p=>{nv+=p.g.pos.length/3;nt+=p.g.idx.length/3});
const pos=new Float32Array(nv*3),idx=new Uint32Array(nt*3),vS=new Uint32Array(parts.length+1),tS=new Uint32Array(parts.length+1),bb=new Float32Array(parts.length*6);
let vo=0,to=0;parts.forEach((p,i)=>{vS[i]=vo;tS[i]=to;pos.set(p.g.pos,vo*3);for(let q=0;q<p.g.idx.length;q++)idx[to*3+q]=p.g.idx[q]+vo;const mn=[1e9,1e9,1e9],mx=[-1e9,-1e9,-1e9];for(let q=0;q<p.g.pos.length;q+=3)for(let a=0;a<3;a++){mn[a]=Math.min(mn[a],p.g.pos[q+a]);mx[a]=Math.max(mx[a],p.g.pos[q+a]);}bb.set([...mn,...mx],i*6);vo+=p.g.pos.length/3;to+=p.g.idx.length/3;});
vS[parts.length]=vo;tS[parts.length]=to;
const order=[];parts.forEach((p,i)=>{if(!p.skin)order.push(i)});order.sort((a,b)=>T.classes[parts[a].cls].priority-T.classes[parts[b].cls].priority);
const Kn=L.KERNEL_FACTORY();Kn.setGeometry({n:parts.length,pos,idx,vStart:vS,tStart:tS,bbox:bb,cls:Uint8Array.from(parts.map(p=>p.cls)),kind:Uint8Array.from(parts.map(p=>p.kind)),skin:Uint8Array.from(parts.map(p=>p.skin)),order:Uint32Array.from(order),skinList:Uint32Array.from([0])});
const bone={};Object.values(T.bone_model.kinds).forEach(k=>{bone[k.id]={axial:!!k.axial,tthin:k.tthin,tmax:k.tmax,frac:k.frac,canal:!!k.canal,z0:k.z0||.2,z1:k.z1||.8,ramp:k.ramp||.08}});
let seq=0;
function slice(nrm,O,s,opt={}){const b=L.basis(nrm),W=opt.W||256,px=opt.px||1.0,fov=W*px;const R={key:'k'+(opt.key||(++seq)),W,H:W,O,u:b.u,v:b.v,n:b.n,u0:-fov/2,v0:fov/2,px,smin:s,smax:s,s,wantSid:true,skinMm:1.8,ids:C.ids,bone};return Kn.slice(R);}
function counts(r){const c={};for(const v of r.lab){const k=T.classes[v].key;c[k]=(c[k]||0)+1}return c;}
const out={};
const r=slice([0,-1,0],[0,0,0],0);out.axial=counts(r);
out.axial_idx=[...r.lab.slice(128*256+128,128*256+129)];
// pixel of atlas (x,z)=(30,0) (bone centre): u=-x, v=z
function at(r,x,z,W=256,px=1,fov=256){const ix=Math.floor((-x+fov/2)/px),iy=Math.floor((fov/2-z)/px);return T.classes[r.lab[iy*W+ix]].key;}
out.centre_bone=at(r,30,0);out.bone_edge=at(r,30+13,0);out.liver=at(r,-40+12,0);out.blood=at(r,-40,0);out.muscle=at(r,-60,60);out.fat=at(r,60,-60);out.air=at(r,0,125);out.skin=at(r,99.3,0);
out.parity=r.parityBad;
// coronal through the bone axis, y long axis: expect cortical shaft walls + canal in the middle, thin cortex near the ends
const rc=slice([0,0,1],[0,0,0],0,{px:2});function atc(r,x,y,W=256,px=2,fov=512){const ix=Math.floor((-x+fov/2)/px),iy=Math.floor((fov/2-y)/px);return T.classes[r.lab[iy*W+ix]].key;}
out.cor_mid_centre=atc(rc,30,0);out.cor_mid_wall=atc(rc,30-11,0);out.cor_end_centre=atc(rc,30,-190);
// slab ordering MIP>=avg>=MinIP by HU, thickness behaviour
const hu=L.ctTable(C);const offs=[];for(let s=-20;s<=20;s+=2)offs.push(s);
const labs=offs.map(s=>slice([0,-1,0],[0,0,0],s,{key:'slab'}).lab);
let ok=true,strictMip=0,strictMin=0;const N=labs[0].length;
for(let k=0;k<N;k++){let sum=0,mx=-1e9,mn=1e9;for(const l of labs){const v=hu[l[k]];sum+=v;if(v>mx)mx=v;if(v<mn)mn=v;}const av=sum/labs.length;if(!(mx>=av-1e-6&&av>=mn-1e-6))ok=false;if(mx>av+1)strictMip++;if(mn<av-1)strictMin++;}
out.order_ok=ok;out.strictMip=strictMip;out.strictMin=strictMin;
// thicker slab sees more: area with HU>200 (bone) in MIP grows with thickness for a tilted structure? use the sphere: liver area at s=15 vs s=0
const a0=counts(slice([0,-1,0],[0,0,0],0)),a15=counts(slice([0,-1,0],[0,0,0],15));out.liver0=a0.liver||0;out.liver15=a15.liver||0;out.liver19=(counts(slice([0,-1,0],[0,0,0],19.5)).liver)||0;out.liver21=(counts(slice([0,-1,0],[0,0,0],21)).liver)||0;
out.area_expected_liver0=Math.PI*(400-64);   // sphere r=20 minus the r=8 vessel
const r15=slice([0,-1,0],[0,0,0],15);out.sphere15_expected=Math.PI*(400-225);out.liver15_plus_blood=(a15.liver||0)+(a15.blood_artery||0);
out.blood15=a15.blood_artery||0;
// cortical ring area for the cylinder r=14: ring thickness min(8, .42*14)=5.88 mm -> canal radius 8.1
out.cort=a0.bone_cortical;out.canal=a0.marrow_yellow;out.cort_expected=Math.PI*(14*14-8.12*8.12);out.canal_expected=Math.PI*8.12*8.12;
// sagittal and coronal bases
out.basis=[L.basis([0,-1,0]),L.basis([0,0,1]),L.basis([-1,0,0]),L.basis([0.3,-0.9,0.1])].map(b=>[L.dirLabel(b.u),L.dirLabel(b.v)]);
// speed: 30 sub-slices on the cached plane
let t=Date.now();const R2={key:'speed',W:512,H:512,O:[0,0,0],u:L.basis([0,-1,0]).u,v:L.basis([0,-1,0]).v,n:[0,-1,0],u0:-256,v0:256,px:1,smin:-15,smax:15,s:0,wantSid:false,skinMm:1.8,ids:C.ids,bone};
for(let s=-15;s<=15;s++){R2.s=s;Kn.slice(R2);}out.ms30=Date.now()-t;
console.log(JSON.stringify(out));
"""


@needs_node
def test_kernel_known_geometry():
    o = json.loads(_node(KERNEL_TEST))
    assert o["centre_bone"] == "marrow_yellow" and o["bone_edge"] == "bone_cortical"
    assert o["liver"] == "liver" and o["blood"] == "blood_artery" and o["muscle"] == "muscle"
    assert o["fat"] == "fat" and o["air"] == "air" and o["skin"] == "skin"             # baseline inside the skin, air outside
    assert o["parity"] == 0
    # areas of a polygonised sphere / cylinder against the analytic ones
    assert o["liver0"] == pytest.approx(o["area_expected_liver0"], rel=0.06)
    assert o["cort"] + o["canal"] == pytest.approx(o["cort_expected"] + o["canal_expected"], rel=0.05)
    assert o["canal"] == pytest.approx(o["canal_expected"], rel=0.12)
    # sphere sliced 15 mm off-centre: radius sqrt(400-225); the vessel sphere (r 8) ends at 8 mm
    assert o["liver15_plus_blood"] == pytest.approx(o["sphere15_expected"], rel=0.08) and o["blood15"] == 0
    assert o["liver19"] > 0 and o["liver21"] == 0                                       # slab sees the 20 mm sphere only up to 20 mm
    # medullary canal only in the shaft, not at the epiphysis end
    assert o["cor_mid_centre"] == "marrow_yellow" and o["cor_mid_wall"] == "bone_cortical" and o["cor_end_centre"] == "bone_cancellous"
    # MIP >= avg >= MinIP at every pixel, and strictly different somewhere (thick-slab combination)
    assert o["order_ok"] and o["strictMip"] > 100 and o["strictMin"] > 100
    # radiological orientation: axial u = patient left on screen right (L), v anterior (A); coronal L,S; sagittal P,S
    assert o["basis"][0] == ["L", "A"] and o["basis"][1] == ["L", "S"] and o["basis"][2] == ["P", "S"]
    assert o["ms30"] < 4000


# ---------------------------------------------------------------- staging / licensing
def test_staging_imaging_files(tmp_path):
    d = tmp_path / "viewer_x"
    d.mkdir()
    out = scf.stage_imaging(d)
    assert [p.name for p in out] == ["clinical_imaging_tool.js", "clinical_imaging_tissues.json"]
    assert (d / "clinical_imaging_tool.js").read_bytes() == TOOL.read_bytes()
    assert (d / "clinical_imaging_tissues.json").read_bytes() == (REPO / "clinical" / "data" / "imaging_tissues.json").read_bytes()
    assert not (d / "clinical_needle_tool.js").exists()                                  # imaging-only stages no needle files
    gone = scf.remove(d)
    assert {p.name for p in gone} == {"clinical_imaging_tool.js", "clinical_imaging_tissues.json"}
    # --imaging with the needle files, then --remove takes all five away
    scf.stage(d, "vhm"); scf.stage_imaging(d)
    assert {p.name for p in d.iterdir()} >= {"clinical_needle_tool.js", "clinical_risk.json", "clinical_imaging_tool.js", "clinical_imaging_tissues.json"}
    scf.remove(d)
    assert not list(d.iterdir())


def test_public_templates_carry_only_the_generic_hook():
    for name in ("atlas_viewer.template.html", "zan_atlas.template.html"):
        t = (REPO / "viewer" / name).read_text(encoding="utf-8")
        assert t.count('<script src="clinical_imaging_tool.js"></script>') == 1, name
        assert t.index("clinical_needle_tool.js") < t.index("clinical_imaging_tool.js") < t.index("<script id=\"bundle-json\"" if "atlas_viewer" in name else "window.__ANATOMY_BIN__")
        # no imaging logic, tissue numbers or table inlined into the public layer
        low = t.lower()
        for bad in ("hounsfield", "t1_se", "tissue table", "imaging_tissues", "mrtable", "nmskimaging"):
            assert bad not in low, (name, bad)


def test_private_licence_covers_imaging():
    lic = (REPO / "clinical" / "LICENSE_PRIVATE.md").read_text(encoding="utf-8")
    assert "PRIVATE" in lic
    head = TOOL.read_text(encoding="utf-8")[:1600]
    assert "PRIVATE" in head and "NOT A SCAN" in head.upper()


def test_tool_chains_onto_needle_addon():
    """Without a needle add-on the imaging script installs window.NMSKClinical.attach; with one it calls it first and returns its value."""
    code = r"""
      const vm=require('vm'),fs=require('fs');
      const calls=[];
      const sandbox={console, document:{currentScript:null,head:{appendChild(){}},body:{classList:{add(){},remove(){},toggle(){}},appendChild(){}},getElementById(){return null;},createElement(){return {style:{},setAttribute(){},appendChild(){},addEventListener(){},classList:{add(){},remove(){},toggle(){}},getContext(){return {}}}}},
        fetch:()=>Promise.reject(new Error('x')), Worker:undefined, URL:{createObjectURL(){return ''}}, Blob:function(){}, setTimeout, clearTimeout, setInterval, clearInterval, Promise, Object, Array, JSON, Math, Date,
        Float32Array, Uint8Array, Uint16Array, Uint32Array, Int32Array, Float64Array, Error, Event:function(){}, devicePixelRatio:1, innerWidth:1000, innerHeight:800};
      sandbox.window=sandbox; sandbox.globalThis=sandbox;
      sandbox.NMSKClinical={attach(api){calls.push('needle');return {cursor(){return 1}};}, extra:42};
      vm.createContext(sandbox);
      vm.runInContext(fs.readFileSync('clinical/imaging_tool.js','utf8'),sandbox);
      const r=sandbox.NMSKClinical.attach({toolbar:null, list(){return []}, kind:'three'});
      console.log(JSON.stringify({calls, extra:sandbox.NMSKClinical.extra, ret:typeof r.cursor, imaging:sandbox.NMSKClinical.imaging}));"""
    o = json.loads(_node(code))
    assert o["calls"] == ["needle"] and o["extra"] == 42 and o["ret"] == "function" and o["imaging"].startswith("q226")


# ---------------------------------------------------------------- browser (opt-in)
BROWSER = os.environ.get("Q226_BROWSER") == "1"
CHROME = Path("/opt/pw-browsers/chromium")
THREE = os.environ.get("Q226_THREE_JS", "")
browser = pytest.mark.skipif(not (BROWSER and CHROME.exists()), reason="set Q226_BROWSER=1 (+ Q226_THREE_JS=three.min.js r128) with Chromium and build/q226 pages")


@browser
@pytest.mark.parametrize("page,kind", [("vhm", "own"), ("zan_f", "zan")])
def test_browser_zero_errors_all_viewports(page, kind):
    d, html, _ = qs.STAGED[page]
    root = REPO / d
    assert (root / "clinical_imaging_tool.js").is_file(), "run scripts/regen_imaging_q226.sh first"
    sys.path.insert(0, str(REPO / "scripts" / "clinical"))
    import q226_check as ck
    res = ck.run(str(root), html, kind, str(REPO / "build" / "q226_renders" / f"t_{page}"), THREE, ck.VIEWPORTS_ALL, shots=False)
    (REPO / "data" / "derived" / f"Q226_browser_{page}.json").write_text(json.dumps(res, indent=1) + "\n", encoding="utf-8")
    for vp, r in res.items():
        assert not r["errors"], (vp, r["errors"])
        assert not r["bad_responses"], (vp, r["bad_responses"])
        assert r["layout"]["scrollW"] <= r["layout"]["innerW"], (vp, r["layout"])


# ---------------------------------------------------------------- recorded numeric checks on the real meshes (scripts/clinical/q226_check.py --numeric)
def _numeric(page):
    f = REPO / "data" / "derived" / f"Q226_numeric_{page}.json"
    if not f.is_file():
        pytest.skip(f"{f.name} not recorded here (run scripts/clinical/q226_check.py ... --numeric {page})")
    return json.loads(f.read_text(encoding="utf-8"))


@pytest.mark.parametrize("page", ["vhm", "zan_f"])
def test_recorded_numeric_checks_on_real_meshes(page):
    n = _numeric(page)
    fs, fe = n["femur_shaft"], n["femur_end"]
    # mid-shaft: cortical ring + medullary canal; the canal is the middle; a plausible femoral cross-section
    assert fs["hist"].get("bone_cortical", 0) > 0 and fs["hist"].get("marrow_yellow", 0) > 0 and fs["nearestClass"] == "marrow_yellow"
    frac = fs["hist"]["bone_cortical"] / fs["pixels"]
    assert 0.25 <= frac <= 0.85, frac
    assert 300 <= fs["area_mm2"] <= 1800, fs["area_mm2"]
    # near the end: no medullary canal, cancellous interior under a thin cortex
    assert fe["hist"].get("bone_cancellous", 0) > 0 and fe["hist"].get("marrow_yellow", 0) <= 0.05 * fe["pixels"]
    assert n["muscle"]["nearestClass"] == "muscle" and n["muscle"]["hu_centre"] == pytest.approx(52, abs=1) and n["muscle"]["hist"]["muscle"] > 0.8 * n["muscle"]["pixels"]
    assert n["liver"]["hist"].get("liver", 0) > 0.8 * n["liver"]["pixels"] and n["liver"]["pixels"] > 500
    assert n["vessel"]["hist"].get("blood_artery", 0) > 0.8 * n["vessel"]["pixels"] and n["vessel"]["pixels"] > 5
    if "lung" in n:
        assert n["lung"]["hist"].get("lung", 0) > 0.8 * n["lung"]["pixels"] and n["lung"]["hu_centre"] == pytest.approx(-800, abs=1)
    for k, v in n.items():
        assert not v.get("missing"), k


@pytest.mark.parametrize("page", ["vhm", "zan_f"])
def test_recorded_browser_runs(page):
    f = REPO / "data" / "derived" / f"Q226_browser_{page}.json"
    if not f.is_file():
        pytest.skip(f"{f.name} not recorded here")
    res = json.loads(f.read_text(encoding="utf-8"))
    assert set(res) >= {"1440x900", "1024x640", "820x1180", "1180x820", "390x844", "844x390"}
    for vp, r in res.items():
        assert not r["errors"] and not r["bad_responses"], (vp, r["errors"])
        assert r["layout"]["scrollW"] <= r["layout"]["innerW"], vp
        assert r["layout"]["smallButtons"] == 0, (vp, r["layout"])
        assert r["first_slice_ms"] and r["first_slice_ms"][0]["ms"] < 1000, (vp, r["first_slice_ms"])
        if "perf" in r:
            assert max(r["perf"]["axial512_ms"]) < 1000, (vp, r["perf"])
    assert res["390x844"]["layout"]["cls"].find("img-tab") >= 0 and res["844x390"]["layout"]["cls"].find("img-tab") >= 0
    assert "img-side" in res["1440x900"]["layout"]["cls"] and "img-stack" in res["820x1180"]["layout"]["cls"]


@pytest.mark.parametrize("page", ["vhm", "zan_f"])
def test_recorded_slab_behaviour_on_real_meshes(page):
    n = _numeric(page)
    if "_slab" not in n:
        pytest.skip("slab record missing (re-run q226_check.py with --numeric)")
    s = n["_slab"]
    assert s["sub"] == 21 and s["order_ok"], s                               # MIP >= average >= MinIP at every sampled pixel
    assert s["strict_mip"] > 50 and s["strict_min"] > 50                       # the three combinations really differ
    b = s["bone_pixels"]
    assert b["mip20"] >= b["mip5"] >= b["single"] * 0.98 and b["min20"] <= b["avg20"] <= b["mip20"], b


def test_recorded_numeric_female_kidney_spleen():
    f = REPO / "data" / "derived" / "Q226_numeric_vhf.json"
    if not f.is_file():
        pytest.skip("Q226_numeric_vhf.json not recorded here")
    n = json.loads(f.read_text(encoding="utf-8"))
    for k, cls in (("kidney", "kidney"), ("spleen", "spleen"), ("liver", "liver")):
        assert not n[k].get("missing"), k
        assert n[k]["hist"].get(cls, 0) > 0.8 * n[k]["pixels"], (k, n[k]["hist"])


@pytest.mark.parametrize("page", ["vhm", "zan_f"])
def test_recorded_interaction_run(page):
    f = REPO / "data" / "derived" / f"Q226_browser_interact_{page}.json"
    if not f.is_file():
        pytest.skip("interaction run not recorded here")
    res = json.loads(f.read_text(encoding="utf-8"))
    assert set(res) == {"1440x900", "390x844"}
    for vp, r in res.items():
        assert not r["errors"], (vp, r["errors"])
        i = r["interact"]
        # crosshair <-> cut plane coupling, readout, slab modes, thickness both ways, clean close
        assert i["click_coronal_moves_anchor"] and i["click_coronal_moves_cut_plane"] and i["axial_click_keeps_plane_y"], (vp, i)
        assert i["readout_has_tissue_and_hu"] and i["mip_mode"] and i["thick_10"] and i["cut_panel_slab_adopted"], (vp, i)
        assert "3.0 mm" in i["cut_th_text_after_link"], (vp, i)
        assert all(i["views_have_content"].values()), (vp, i)
        assert i["closed_cleanly"]["rootVisible"] == "none" and "nmsk-img" not in i["closed_cleanly"]["cls"]
        assert i["closed_cleanly"]["canvasW"] > 0
