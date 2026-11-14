"""Q294 measure, one-tap kinds: circumference / section area / surface area / volume / expected CT value (viewer/q294/measure.js,
NMSKMeasureCore). Each formula is checked on analytic meshes built here, under node: a unit cube (volume 1, area 6, also unwelded
and with one triangle flipped), capped cylinders (the polygon's exact perimeter / area and the circle's within the discretisation),
an oblique cut (ellipse area pi r^2 / cos t), a tube (the loop at the tap: outer, wall, canal), a UV sphere, an open mesh (refused),
and the expected-value lookup against the page's own reference (only a sourced status gives a number)."""
from __future__ import annotations

import json
import math
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")
pytestmark = pytest.mark.skipif(not NODE, reason="node not installed")

PRELUDE = r"""
eval(require('fs').readFileSync('viewer/q294/measure.js','utf8').split('var NMSKMeasure = ')[0]); const C = NMSKMeasureCore;
function cube(){ const P=[0,0,0, 1,0,0, 1,1,0, 0,1,0, 0,0,1, 1,0,1, 1,1,1, 0,1,1];
  const I=[0,2,1, 0,3,2, 4,5,6, 4,6,7, 0,1,5, 0,5,4, 1,2,6, 1,6,5, 2,3,7, 2,7,6, 3,0,4, 3,4,7]; return {pos:new Float32Array(P), idx:new Uint32Array(I)}; }
function unweld(m){ const P=[], I=[]; for (let k=0;k<m.idx.length;k++){ const v=m.idx[k]; P.push(m.pos[3*v],m.pos[3*v+1],m.pos[3*v+2]); I.push(k); } return {pos:new Float64Array(P), idx:new Uint32Array(I)}; }
/* cylinder along y, radius r, y in [0,h], N sides; caps optional; inward=true flips the winding (an inner wall) */
function tube(r, h, N, caps, inward){ const P=[], I=[];
  for (let j=0;j<2;j++) for (let k=0;k<N;k++){ const a=2*Math.PI*k/N; P.push(r*Math.cos(a), j*h, r*Math.sin(a)); }
  for (let k=0;k<N;k++){ const a=k, b=(k+1)%N, c=N+(k+1)%N, d=N+k; if (!inward) I.push(a,c,b, a,d,c); else I.push(a,b,c, a,c,d); }
  if (caps){ const c0=P.length/3; P.push(0,0,0); const c1=P.length/3; P.push(0,h,0);
    for (let k=0;k<N;k++){ I.push(c0,k,(k+1)%N); I.push(c1,N+(k+1)%N,N+k); } }
  return {pos:new Float64Array(P), idx:new Uint32Array(I)}; }
function merge(a, b){ const n=a.pos.length/3; return {pos:Float64Array.from([...a.pos, ...b.pos]), idx:Uint32Array.from([...a.idx, ...Array.from(b.idx, x=>x+n)])}; }
/* closed tube wall: outer radius ro, inner ri, annular caps */
function hollow(ro, ri, h, N){ const o=tube(ro,h,N,false,false), i=tube(ri,h,N,false,true), m=merge(o,i), I=Array.from(m.idx);
  for (let k=0;k<N;k++){ const k1=(k+1)%N, io=2*N; I.push(k, k1, io+k1, k, io+k1, io+k); I.push(N+k, io+N+k1, N+k1, N+k, io+N+k, io+N+k1); }
  return {pos:m.pos, idx:Uint32Array.from(I)}; }
function sphere(R, nl, nm){ const P=[], I=[];
  for (let i=0;i<=nl;i++){ const t=Math.PI*i/nl; for (let j=0;j<nm;j++){ const p=2*Math.PI*j/nm; P.push(R*Math.sin(t)*Math.cos(p), R*Math.sin(t)*Math.sin(p), R*Math.cos(t)); } }
  for (let i=0;i<nl;i++) for (let j=0;j<nm;j++){ const a=i*nm+j, b=i*nm+(j+1)%nm, c=(i+1)*nm+(j+1)%nm, d=(i+1)*nm+j; I.push(a,d,c, a,c,b); }
  return {pos:new Float64Array(P), idx:new Uint32Array(I)}; }
"""


def run(body: str) -> dict:
    r = subprocess.run([NODE, "-e", PRELUDE + body], capture_output=True, text=True, timeout=120, cwd=str(REPO))
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout.strip().splitlines()[-1])


def poly_perim(r, n):
    return 2 * n * r * math.sin(math.pi / n)


def poly_area(r, n):
    return 0.5 * n * r * r * math.sin(2 * math.pi / n)


def test_unit_cube_volume_area_and_watertightness():
    o = run("""const c=cube(), f=cube(); [f.idx[0],f.idx[1]]=[f.idx[1],f.idx[0]];
      const s=C.solid(c.pos,c.idx), u=C.solid(unweld(c).pos, unweld(c).idx), x=C.solid(f.pos,f.idx);
      console.log(JSON.stringify({s, u, x, ls:C.structLabel('vol', s).text, lx:C.structLabel('vol', x), la:C.structLabel('surf', s).text}));""")
    s, u, x = o["s"], o["u"], o["x"]
    assert s["closed"] and s["oriented"] and s["boundary"] == 0 and abs(s["volume"] - 1) < 1e-12 and abs(s["area"] - 6) < 1e-12
    assert u["closed"] and u["verts"] == 8 and abs(u["volume"] - 1) < 1e-12        # 36 loose corners weld back into one closed cube
    assert x["closed"] and not x["oriented"] and x["volume"] is None and x["misoriented"] > 0   # one flipped triangle: no number
    assert o["ls"] == "Volume 0.00 cm³"                                             # 1 mm^3 = 0.001 cm^3
    assert o["lx"]["v"] is None and "not consistently oriented" in o["lx"]["text"] and "volume not reported" in o["lx"]["text"]
    assert o["la"] == "Surface area 0.1 cm²"                                        # 6 mm^2


def test_open_mesh_is_refused():
    o = run("""const t=tube(5,40,64,false,false), s=C.solid(t.pos,t.idx); console.log(JSON.stringify({s, l:C.structLabel('vol', s), a:C.structLabel('surf', s)}));""")
    s = o["s"]
    assert not s["closed"] and s["volume"] is None and s["boundary"] == 2 * 64
    assert o["l"]["v"] is None and o["l"]["text"] == "Volume: not closed (128 boundary edges) -- volume not reported"
    assert abs(s["area"] - poly_perim(5, 64) * 40) < 1e-9                           # the surface area of an open mesh is still a sum of triangles
    assert o["a"]["text"].endswith("(open mesh)")


def test_cylinder_section_perpendicular_to_long_axis():
    N, r, h = 96, 5.0, 40.0
    o = run(f"""const m=tube({r},{h},{N},true,false), s=C.solid(m.pos,m.idx), ax=C.longAxis(m.pos,m.idx);
      const sec=C.sectionAt(m.pos,m.idx,[{r},13,0],null);
      console.log(JSON.stringify({{s, ax, perim:sec.perim, area:sec.area, n:sec.n, loops:sec.loops, how:sec.how,
        lc:C.structLabel('circ',sec).text, la:C.structLabel('area',sec).text}}));""")
    assert abs(abs(o["ax"][1]) - 1) < 1e-9                                         # the long axis of a 40 x 10 cylinder is y
    assert abs(o["perim"] - poly_perim(r, N)) < 1e-9 and abs(o["area"] - poly_area(r, N)) < 1e-9   # exact for the mesh
    assert abs(o["perim"] / (2 * math.pi * r) - 1) < 1e-3 and abs(o["area"] / (math.pi * r * r) - 1) < 1e-3   # the circle, within discretisation
    assert o["loops"] == 1 and "long axis" in o["how"]
    assert abs(o["s"]["volume"] - poly_area(r, N) * h) < 1e-9                      # prism volume = base polygon x height
    assert o["lc"] == "Circumference %.1f mm" % poly_perim(r, N) and o["la"].startswith("Section area %.2f cm²" % (poly_area(r, N) / 100))


def test_oblique_cut_plane_gives_the_ellipse():
    N, r, t = 256, 5.0, math.radians(30)
    n = [0, math.cos(t), math.sin(t)]
    o = run(f"""const m=tube({r},60,{N},true,false), n={json.dumps(n)}, p=[0,30,0];
      const sec=C.sectionAt(m.pos,m.idx,p,[n[0],n[1],n[2],-(n[1]*30)]);
      const far=C.sectionAt(m.pos,m.idx,p,[0,1,0,-500]);
      console.log(JSON.stringify({{a:sec.area, p:sec.perim, how:sec.how, far:far.err||null}}));""")
    a_exact = math.pi * r * r / math.cos(t)
    assert abs(o["a"] / a_exact - 1) < 1e-3 and "cut plane" in o["how"]
    b = r / math.cos(t)                                                              # ellipse r x r/cos t: Ramanujan perimeter
    hh = ((b - r) / (b + r)) ** 2
    assert abs(o["p"] / (math.pi * (r + b) * (1 + 3 * hh / (10 + math.sqrt(4 - 3 * hh)))) - 1) < 1e-3
    assert o["far"] == "the cut plane does not cross this structure"


def test_tube_picks_the_loop_at_the_tap():
    N = 128
    o = run(f"""const m=hollow(10,6,40,{N}), s=C.solid(m.pos,m.idx), pl=[0,1,0,-20];
      const outer=C.sectionAt(m.pos,m.idx,[10,20,0],null), wall=C.sectionAt(m.pos,m.idx,[8,20,0],pl), canal=C.sectionAt(m.pos,m.idx,[1,20,1],pl), inner=C.sectionAt(m.pos,m.idx,[0,20,6],null);
      console.log(JSON.stringify({{v:s.volume, closed:s.closed, outer:outer.perim, wall:wall.perim, canal:canal.perim, inner:inner.perim, loops:outer.loops}}));""")
    assert o["closed"] and abs(o["v"] - (poly_area(10, N) - poly_area(6, N)) * 40) < 1e-6   # the canal's inward wall subtracts itself
    assert o["loops"] == 2
    assert abs(o["outer"] - poly_perim(10, N)) < 1e-9 and abs(o["wall"] - poly_perim(10, N)) < 1e-9
    assert abs(o["canal"] - poly_perim(6, N)) < 1e-9 and abs(o["inner"] - poly_perim(6, N)) < 1e-9


def test_sphere_equator_and_volume():
    R = 10.0
    o = run(f"""const m=sphere({R},128,256), s=C.solid(m.pos,m.idx), sec=C.sectionAt(m.pos,m.idx,[{R},0,0],[0,0,1,0]);
      console.log(JSON.stringify({{v:s.volume, a:s.area, closed:s.closed, perim:sec.perim, area:sec.area}}));""")
    assert o["closed"]
    assert abs(o["v"] / (4 / 3 * math.pi * R ** 3) - 1) < 1e-3 and abs(o["a"] / (4 * math.pi * R * R) - 1) < 1e-3
    assert abs(o["perim"] / (2 * math.pi * R) - 1) < 1e-3 and abs(o["area"] / (math.pi * R * R) - 1) < 1e-3


def test_expected_value_only_when_sourced():
    table = json.loads((REPO / "clinical" / "data" / "imaging_tissues.json").read_text(encoding="utf-8"))
    o = run("""const T=require('./viewer/q301/tissue.js'); const none=C.pointValue(T,{cat:'muscle',id:'x',name:'x'});
      T.adopt(JSON.parse(require('fs').readFileSync('clinical/data/imaging_tissues.json','utf8')));
      const out={none, real:C.pointValue(T,{cat:'muscle',id:'biceps_brachii_r',name:'Biceps brachii'}), k:{}};
      T.keys().forEach(function(k){ out.k[k]=C.pointValue(Object.assign({},T,{classOf:function(){ return k; }}),{}); });
      console.log(JSON.stringify(out));""")
    assert o["none"]["v"] is None and o["none"]["text"].startswith("No sourced value")
    sourced = {"verified", "derived", "secondary_checked"}
    for c in table["classes"]:
        r = o["k"][c["key"]]
        if c["ct"].get("status") in sourced:
            assert r["v"] == c["ct"]["hu"] and r["unit"] == "HU", c["key"]
        else:
            assert r["v"] is None and r["text"].startswith("No sourced value"), c["key"]
    assert o["real"]["cls"] in {c["key"] for c in table["classes"]}
