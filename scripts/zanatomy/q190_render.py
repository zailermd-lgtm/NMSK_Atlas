"""Q190 render helpers: orthographic flat-shaded WebGL2 renders in headless Chromium (swiftshader) + transverse-cut line plots.

    scene = [{"v": (n,3) mm, "f": (m,3), "color": (r,g,b)}]   views = [{"name", "az", "el", "target", "half", ("clip_y": (lo, hi))}]
Atlas frame: +X right, +Y superior, +Z anterior.  az 0 = seen from the front (camera at +Z), 90 = from her left side is -X ... see _eye().
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import numpy as np

HTML = r"""<!doctype html><meta charset=utf-8><body style="margin:0;background:#fff"><canvas id=c width=%(W)d height=%(H)d></canvas>
<script>
const gl=document.getElementById('c').getContext('webgl2',{antialias:true,preserveDrawingBuffer:true});
const vs=`#version 300 es
in vec3 p; in vec3 col; uniform mat4 M; out vec3 vp; out vec3 vc; void main(){vp=p;vc=col;gl_Position=M*vec4(p,1.);}`;
const fs=`#version 300 es
precision highp float; in vec3 vp; in vec3 vc; uniform vec3 L; uniform vec2 clipy; out vec4 o;
void main(){ if(vp.y<clipy.x||vp.y>clipy.y) discard; vec3 n=normalize(cross(dFdx(vp),dFdy(vp))); float d=abs(dot(n,L)); o=vec4(vc*(0.28+0.72*d),1.);}`;
function sh(t,s){const x=gl.createShader(t);gl.shaderSource(x,s);gl.compileShader(x);if(!gl.getShaderParameter(x,gl.COMPILE_STATUS))throw gl.getShaderInfoLog(x);return x}
const pr=gl.createProgram();gl.attachShader(pr,sh(gl.VERTEX_SHADER,vs));gl.attachShader(pr,sh(gl.FRAGMENT_SHADER,fs));gl.linkProgram(pr);gl.useProgram(pr);
window.load=async function(){
  const j=await (await fetch('scene.json')).json();
  const P=new Float32Array(await (await fetch('pos.bin')).arrayBuffer());
  const C=new Float32Array(await (await fetch('col.bin')).arrayBuffer());
  window.nv=P.length/3;
  for(const [name,arr,sz] of [['p',P,3],['col',C,3]]){const b=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,b);gl.bufferData(gl.ARRAY_BUFFER,arr,gl.STATIC_DRAW);
    const l=gl.getAttribLocation(pr,name);gl.enableVertexAttribArray(l);gl.vertexAttribPointer(l,sz,gl.FLOAT,false,0,0);}
  window.ready=true;
};
window.draw=function(M,L,clip){gl.viewport(0,0,%(W)d,%(H)d);gl.enable(gl.DEPTH_TEST);gl.clearColor(1,1,1,1);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);
  gl.uniformMatrix4fv(gl.getUniformLocation(pr,'M'),false,new Float32Array(M));gl.uniform3fv(gl.getUniformLocation(pr,'L'),L);gl.uniform2fv(gl.getUniformLocation(pr,'clipy'),clip);
  gl.drawArrays(gl.TRIANGLES,0,window.nv);gl.finish();};
</script>"""


def _eye(az, el):
    a, e = np.radians(az), np.radians(el)
    return np.array([np.sin(a) * np.cos(e), np.sin(e), np.cos(a) * np.cos(e)])   # az 0 -> +Z (front), 90 -> +X, 180 -> -Z (back)


def _matrix(az, el, target, half, aspect=1.0, depth=2000.0):
    d = _eye(az, el)
    up = np.array([0, 1.0, 0]) if abs(el) < 80 else np.array([0, 0, -1.0 if el > 0 else 1.0])
    z = d
    x = np.cross(up, z); x /= np.linalg.norm(x)
    y = np.cross(z, x)
    R = np.stack([x, y, z])
    t = -R @ np.asarray(target, float)
    V = np.eye(4); V[:3, :3] = R; V[:3, 3] = t
    P = np.diag([1 / (half * aspect), 1 / half, -1 / depth, 1.0])
    M = P @ V
    return M.T.flatten().tolist()   # column-major for GL


def render(scene, views, out_dir, size=(760, 760), prefix=""):
    """scene = [{"v","f","color"}]; views = [{"name","az","el","target","half","clip_y"?}] -> writes out_dir/<prefix><name>.png"""
    from playwright.sync_api import sync_playwright
    out_dir = Path(out_dir); out_dir.mkdir(parents=True, exist_ok=True)
    W, H = size
    tri = []
    col = []
    for m in scene:
        v = np.asarray(m["v"], np.float32)[np.asarray(m["f"])].reshape(-1, 3)
        tri.append(v)
        col.append(np.tile(np.asarray(m["color"], np.float32), (len(v), 1)))
    P = np.concatenate(tri); C = np.concatenate(col)
    tmp = Path(tempfile.mkdtemp(prefix="q190r_", dir=out_dir))
    (tmp / "pos.bin").write_bytes(P.tobytes()); (tmp / "col.bin").write_bytes(C.tobytes()); (tmp / "scene.json").write_text("{}")
    (tmp / "index.html").write_text(HTML % {"W": W, "H": H})
    with sync_playwright() as pw:
        br = pw.chromium.launch(executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome", args=["--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
                                                           "--ignore-gpu-blocklist", "--allow-file-access-from-files"])
        pg = br.new_page(viewport={"width": W, "height": H})
        pg.goto((tmp / "index.html").as_uri())
        pg.evaluate("window.load()")
        pg.wait_for_function("window.ready===true", timeout=120000)
        for vw in views:
            M = _matrix(vw["az"], vw["el"], vw["target"], vw["half"])
            L = (_eye(vw["az"] - 25, vw["el"] + 25)).tolist()
            clip = list(vw.get("clip_y", (-1e9, 1e9)))
            pg.evaluate("([M,L,c])=>window.draw(M,L,c)", [M, L, clip])
            pg.locator("#c").screenshot(path=str(out_dir / f"{prefix}{vw['name']}.png"))
        br.close()
    for f in tmp.iterdir():
        f.unlink()
    tmp.rmdir()


def section_lines(v, f, y):
    """polyline segments of the plane y=const through a triangle mesh -> (k,2,2) array of (x,z) pairs (vectorised)"""
    v = np.asarray(v, float); f = np.asarray(f)
    t = v[f]                                   # (m,3,3)
    s = t[:, :, 1] - y
    keep = (s.min(1) < 0) & (s.max(1) > 0)
    t, s = t[keep], s[keep]
    if not len(t):
        return np.zeros((0, 2, 2))
    pts = np.full((len(t), 3, 2), np.nan)
    for e, (a, b) in enumerate(((0, 1), (1, 2), (2, 0))):
        cr = s[:, a] * s[:, b] < 0
        u = np.where(cr, s[:, a] / np.where(cr, s[:, a] - s[:, b], 1.0), 0.0)
        q = t[:, a] + u[:, None] * (t[:, b] - t[:, a])
        pts[cr, e] = q[cr][:, [0, 2]]
    ok = (~np.isnan(pts[:, :, 0])).sum(1) == 2
    pts = pts[ok]
    order = np.argsort(np.isnan(pts[:, :, 0]), axis=1, kind="stable")[:, :2]
    return np.take_along_axis(pts, order[:, :, None], axis=1)
