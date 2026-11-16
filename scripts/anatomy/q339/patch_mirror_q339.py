#!/usr/bin/env python3
"""Q339: the Z engine drew a MIRROR IMAGE of the patient -- fix it as a handedness flip of the view (idempotent).

    python3 scripts/anatomy/q339/patch_mirror_q339.py            # patch viewer/zan_atlas.template.html
    python3 scripts/anatomy/q339/patch_mirror_q339.py --check    # exit 1 unless every edit is in place
    python3 scripts/anatomy/q339/patch_mirror_q339.py FILE...    # patch built pages instead (test copies)

Run it as `flock /tmp/nmsk_sync.lock python3 scripts/anatomy/q339/patch_mirror_q339.py` (other agents edit the template).

Why: the data frame is atlas mm with +X = the patient's RIGHT, +Y superior, +Z anterior -- a left-handed frame. The engine
rendered it through an ordinary right-handed look-at camera, so the anterior view put the patient's right on the viewer's
RIGHT (a mirror image: liver, caecum and every `_r` structure on the wrong side of the screen).

What changes (nothing in the data, no id renamed, no geometry mirrored):
  1. mL(): the view matrix's x row is negated after the up vector is built from it (det < 0). The screen's right is then
     -(camera right) of the old camera: the front view puts the patient's right on the viewer's left, the back view on the
     right, and the right lateral view (the "side" preset, eye at +X) puts anterior on the viewer's right. lastRight/lastUp,
     the pick ray, pickPoint(), proj()/toScreen() and the pinch / zoom-at-point axes all come from this matrix, so labels,
     rings, markers, IZ rings, attachment points, the quick card's leader, measure overlays, the cut caps, the ID and depth
     passes and every add-on that uses api.ray()/toScreen()/the after-draw MVP follow without a change of their own.
  2. The winding a mirrored projection produces is reversed, so the front face is CW (gl_FrontFacing feeds the two-sided
     normal flip of the main shader); the Symmetric view's reflected pass, which reverses it once more, uses CCW.
  3. Screen-space input re-signed so the model follows the pointer as before: one-finger / mouse orbit (dx -> az), the auto
     spin, the face-centring offset of lookAt(), and the add-on api.orbit() turn step (Learn panel's half / full turn and
     the clinical full-screen view keep their on-screen sense). Pan, pinch, wheel zoom-at-point, the pose rings' drag,
     cut, measure and needle / probe drags already work through the matrix or the ray and need nothing.
  4. A small R / L (or A / P on a lateral view) orientation marker in the bottom-right corner of the view, pointer-transparent,
     with the full words in its title; the front / side / back buttons say which view they give.
  5. A test hook window.__q339 (anatomyApi, the screen-right axis, the marker's letters).
Saved cameras (az, el, dist, target) are the EYE's position in the model frame, not a screen convention: a saved view still
looks at the same face of the body from the same side and is read unchanged."""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
TEMPLATE = REPO / "viewer/zan_atlas.template.html"

EDITS = [
    ("view matrix handedness flip",
     "      var y=[z[1]*x[2]-z[2]*x[1],z[2]*x[0]-z[0]*x[2],z[0]*x[1]-z[1]*x[0]];\n"
     "      return new Float32Array([x[0],y[0],z[0],0,",
     "      var y=[z[1]*x[2]-z[2]*x[1],z[2]*x[0]-z[0]*x[2],z[0]*x[1]-z[1]*x[0]];\n"
     "      x=[-x[0],-x[1],-x[2]];   /* Q339: the model frame is left-handed (+X = the patient's right, +Y superior, +Z anterior); a right-handed\n"
     "         look-at drew it as a mirror image. Negating the view's x row (det < 0) makes the screen's right the patient's left in an anterior view. */\n"
     "      return new Float32Array([x[0],y[0],z[0],0,"),
    ("front face CW under the mirrored projection",
     "      gl.enable(gl.DEPTH_TEST); gl.disable(gl.CULL_FACE);\n\n      var ce=Math.cos(cam.el), se=Math.sin(cam.el);\n",
     "      gl.enable(gl.DEPTH_TEST); gl.disable(gl.CULL_FACE);\n"
     "      gl.frontFace(gl.CW);      // Q339: the view matrix has det < 0 (see mL), which reverses the winding on screen; gl_FrontFacing must stay true on the outside\n\n"
     "      var ce=Math.cos(cam.el), se=Math.sin(cam.el);\n"),
    ("symmetric pass winding (reflected once more)",
     "gl.frontFace(gl.CW); symPass = true;",
     "gl.frontFace(gl.CCW); symPass = true;   /* Q339: the reflection reverses the CW winding of the mirrored view once more */"),
    ("symmetric pass restores CW",
     "try { scenePass(); } finally { symPass = false; gl.frontFace(gl.CCW);",
     "try { scenePass(); } finally { symPass = false; gl.frontFace(gl.CW);"),
    ("orbit drag follows the pointer",
     "else { cam.az-=dx*0.0065; cam.el=",
     "else { cam.az+=dx*0.0065; /* Q339: re-signed for the true (non-mirrored) view, so a drag to the right still carries the surface right */ cam.el="),
    ("auto spin keeps its on-screen direction",
     "if(spinning){cam.az+=0.0022;need=true;}",
     "if(spinning){cam.az-=0.0022;need=true;}   // Q339: same on-screen spin as before the handedness fix"),
    ("lookAt centring offset",
     "for (var k = 0; k < 3; k++) cam.tgt[k] -= x[k] * (fr.cx - 0.5) * ww + y[k] * (0.5 - fr.cy) * hw;",
     "for (var k = 0; k < 3; k++) cam.tgt[k] -= -x[k] * (fr.cx - 0.5) * ww + y[k] * (0.5 - fr.cy) * hw;      // Q339: x is the old camera right; the screen's right is -x"),
    ("api.orbit keeps its on-screen sense",
     "orbit:function(d){ cam.az += d; stopSpin(); need=true; },",
     "orbit:function(d){ cam.az -= d; stopSpin(); need=true; },      // Q339: a turn step with the same on-screen sense as before the handedness fix"),
    ("view buttons say which view",
     '  <button class="pill" data-view="front">front</button>\n'
     '  <button class="pill" data-view="side">side</button>\n'
     '  <button class="pill" data-view="back">back</button>\n',
     '  <button class="pill" data-view="front" title="Anterior view: the patient\'s right is on your left">front</button>\n'
     '  <button class="pill" data-view="side" title="Right lateral view: the patient\'s right side, anterior on your right">side</button>\n'
     '  <button class="pill" data-view="back" title="Posterior view: the patient\'s right is on your right">back</button>\n'),
    ("orientation marker element",
     '<div id="foot">\n  <button class="pill" data-view="front"',
     '<style id="q339-orient-css">\n'
     '#q339-orient{position:fixed;right:10px;bottom:calc(10px + env(safe-area-inset-bottom,0px));z-index:5;display:flex;align-items:center;gap:4px;'
     'padding:2px 7px;border-radius:9px;background:rgba(255,255,255,.62);color:#3a4550;font:600 11px/16px system-ui,sans-serif;'
     'letter-spacing:.04em;pointer-events:none;user-select:none;width:max-content}\n'
     '#q339-orient .q339-bar{display:inline-block;width:18px;height:1px;background:currentColor;opacity:.55}\n'
     '</style>\n'
     '<div id="q339-orient" role="img" aria-label="Orientation"><span class="q339-l"></span><span class="q339-bar"></span><span class="q339-r"></span></div>\n'
     '<div id="foot">\n  <button class="pill" data-view="front"'),
    ("orientation marker update",
     "    var lastMVP=null, lastEye=null, lastRight=null, lastUp=null, lastFwd=[0,0,-1];\n",
     "    var lastMVP=null, lastEye=null, lastRight=null, lastUp=null, lastFwd=[0,0,-1];\n"
     "    /* Q339: the R / L (A / P on a lateral view) marker: which side of the PATIENT is on each side of the screen, read from the\n"
     "       screen's right axis in the model frame (+X right, +Y superior, +Z anterior). Written only when it changes. */\n"
     "    var q339O = {el:null, k:\"\"}, Q339W = {R:\"the patient's right\", L:\"the patient's left\", A:\"anterior\", P:\"posterior\", S:\"superior\", I:\"inferior\"};\n"
     "    function q339Orient(){\n"
     "      var el = q339O.el || (q339O.el = document.getElementById(\"q339-orient\")), r = lastRight; if (!el || !r) return;\n"
     "      var a = [Math.abs(r[0]), Math.abs(r[1]), Math.abs(r[2])], i = a[0] >= a[1] && a[0] >= a[2] ? 0 : (a[2] >= a[1] ? 2 : 1), P = [[\"L\",\"R\"],[\"I\",\"S\"],[\"P\",\"A\"]][i];\n"
     "      var lt = r[i] > 0 ? P[0] : P[1], rt = r[i] > 0 ? P[1] : P[0];\n"
     "      if (lt + rt === q339O.k) return; q339O.k = lt + rt;\n"
     "      el.querySelector(\".q339-l\").textContent = lt; el.querySelector(\".q339-r\").textContent = rt;\n"
     "      var t = \"Orientation: \" + Q339W[lt] + \" on your left, \" + Q339W[rt] + \" on your right\"; el.title = t; el.setAttribute(\"aria-label\", t);\n"
     "    }\n"),
    ("orientation marker refresh per frame",
     "      lastRight=[view[0],view[4],view[8]]; lastUp=[view[1],view[5],view[9]]; lastFwd=[-view[2],-view[6],-view[10]];\n",
     "      lastRight=[view[0],view[4],view[8]]; lastUp=[view[1],view[5],view[9]]; lastFwd=[-view[2],-view[6],-view[10]];\n"
     "      q339Orient();      // Q339\n"),
    ("test hook",
     "    // ================= Q188 add-on hook =================\n",
     "    window.__q339 = {api:function(){ return anatomyApi(); }, right:function(){ return lastRight ? lastRight.slice() : null; },      // Q339 test hook\n"
     "                     orient:function(){ return q339O.k; }, cam:function(){ return {az:cam.az, el:cam.el, dist:cam.dist, tgt:cam.tgt.slice()}; },\n"
     "                     pickable:function(i){ return !!(OBJ[i] && pickable(OBJ[i], false)); }};\n"
     "    // ================= Q188 add-on hook =================\n"),
]


def apply(text: str) -> tuple[str, list[str], list[str]]:
    done, missing = [], []
    for name, old, new in EDITS:
        if new in text:
            done.append(name)
            continue
        n = text.count(old)
        if n != 1:
            missing.append(f"{name}: anchor found {n}x")
            continue
        text = text.replace(old, new, 1)
        done.append(name)
    return text, done, missing


def main(argv: list[str]) -> int:
    check = "--check" in argv
    files = [Path(a) for a in argv if not a.startswith("--")] or [TEMPLATE]
    bad = 0
    for f in files:
        t0 = f.read_text(encoding="utf-8")
        if check:
            miss = [name for name, _old, new in EDITS if new not in t0]
            print(f"{f.name}: {len(EDITS) - len(miss)}/{len(EDITS)} Q339 edits in place" + (f"; missing: {miss}" if miss else ""))
            bad += bool(miss)
            continue
        t1, done, missing = apply(t0)
        if missing:
            print(f"{f.name}: NOT patched -- {missing}")
            bad += 1
            continue
        if t1 != t0:
            f.write_text(t1, encoding="utf-8")
        print(f"{f.name}: {'patched' if t1 != t0 else 'already patched'} ({len(done)} edits)")
    print("Q339_PATCH_" + ("FAIL" if bad else "OK"))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
