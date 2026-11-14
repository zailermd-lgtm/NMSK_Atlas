#!/usr/bin/env python3
"""Q301: the ENGINE SIDE of the round, applied to both templates as exact, idempotent string replacements.

Everything that can be shared lives in viewer/q301/ and is spliced by scripts/sync_q301.py. What cannot be shared is
here, because the two engines draw by different means: one is three.js with a MeshPhongMaterial per structure, the other
is this project's own WebGL with per-layer batches. Each replacement is anchored on a unique string and refuses to guess.

    python3 scripts/anatomy/q301/patch_engines_q301.py          # apply (idempotent)
    python3 scripts/anatomy/q301/patch_engines_q301.py --check   # exit 1 if a template still needs it
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
OWN = REPO / "viewer" / "atlas_viewer.template.html"
ZAN = REPO / "viewer" / "zan_atlas.template.html"

# ---------------------------------------------------------------- the Z engine (own WebGL) -----------------------
Z_EDITS = [
    # 1. the fragment shader: the DRR branch. alpha = 1 - exp(-mu * d0) per structure, flat white, no shading --
    #    ordinary SRC_ALPHA blending over black then accumulates 1 - PRODUCT(1 - a_i) = 1 - exp(-SUM mu_i d0),
    #    which is Beer-Lambert, and is order independent so nothing has to be depth sorted.
    (
        '      "uniform vec3 uColor;uniform float uAlpha;uniform float uHL;" +',
        '      "uniform vec3 uColor;uniform float uAlpha;uniform float uHL;" +\n'
        '      "uniform float uXr;uniform float uMu;uniform float uD0;uniform float uFlat;" +      // Q301: the radiographic style\n',
    ),
    (
        '      " gl_FragColor=vec4(c,uAlpha);}";',
        '      " if(uFlat>0.0) c=uColor*mix(0.34+d*0.74+f,1.0,uFlat)+rim*uColor*(1.0-uFlat);" +   // Q301: in CT / MRI the grey IS the datum, so the shading must not swamp it\n'
        '      " if(uXr>0.5){gl_FragColor=vec4(1.0,1.0,1.0,clamp(1.0-exp(-uMu*uD0),0.004,0.995));}" +   // Q301: a DRR\n'
        '      " else gl_FragColor=vec4(c,uAlpha);}";',
    ),
    # The Q301 uniforms go in an array of their OWN rather than being appended to that literal: sync_symview_q237.py
    # anchors on the exact text of the existing list, and extending it in place broke that script's "already applied"
    # probe. A separate call leaves every earlier round's anchor byte-identical.
    (
        '    ["uMVP","uN","uColor","uAlpha","uHL","uClip","uClip2","uClipOn","uBoxMin","uBoxMax","uBoxOn","uSymOn","uSym"].forEach(function (n) {\n'
        '      U[n] = gl.getUniformLocation(prog, n);\n'
        '    });',
        '    ["uMVP","uN","uColor","uAlpha","uHL","uClip","uClip2","uClipOn","uBoxMin","uBoxMax","uBoxOn","uSymOn","uSym"].forEach(function (n) {\n'
        '      U[n] = gl.getUniformLocation(prog, n);\n'
        '    });\n'
        '    ["uXr","uMu","uD0","uFlat"].forEach(function (n) {      // Q301: the radiographic styles, kept apart so no earlier round\'s anchor moves\n'
        '      U[n] = gl.getUniformLocation(prog, n);\n'
        '    });',
    ),
    # 2. the style's own state, next to Q300's boneRead
    (
        '    var boneRead = 0, presetName = "", fadeLegacy = false;',
        '    /* Q301: the model-wide render style. `grey` replaces every structure colour, `mu` is its real attenuation\n'
        '       (from the page\'s own clinical tissue reference), `d0` the path length per crossing (the 3 taps, and our convention). */\n'
        '    var q301 = {mode:"colour", grey:null, mu:null, d0:0.10, flatten:0}, q301Grey = new Map();\n'
        '    var boneRead = 0, presetName = "", fadeLegacy = false;',
    ),
    # 3. the grey replaces the colour; one stable array per quantised grey so the draw runs still merge by reference
    (
        '    function colOf(o) {\n      var c = (o.vt === "v" && COL.vein) ? COL.vein : (COL[o.layer] || [0.6,0.6,0.6]);',
        '    function colOf(o) {\n'
        '      if (q301.grey){                                   // Q301: a radiographic style paints greys, not tissue colours\n'
        '        var g = Math.round(Math.max(0, Math.min(1, q301.grey(o))) * 64) / 64, a = q301Grey.get(g);\n'
        '        if (!a){ a = [g, g, g]; q301Grey.set(g, a); }\n'
        '        return a;\n'
        '      }\n'
        '      var c = (o.vt === "v" && COL.vein) ? COL.vein : (COL[o.layer] || [0.6,0.6,0.6]);',
    ),
    # 4. in X-ray every layer must land in the TRANSLUCENT pass, where the shader owns the alpha
    (
        '    function layerAlpha(k) { var v = addonOpacity ? addonOpacity(k) : null; return v == null ? alphaFor[k] : Math.min(alphaFor[k], v); }',
        '    function layerAlpha(k) {\n'
        '      if (q301.mode === "xray") return 0.5;             // Q301: any value in (0.01, 0.999) -- the DRR shader sets the real alpha\n'
        '      var v = addonOpacity ? addonOpacity(k) : null; return v == null ? alphaFor[k] : Math.min(alphaFor[k], v); }',
    ),
    # 5. mu is part of the run key, so a run is flushed when the attenuation changes as well as the colour
    (
        '        var s=-1,c=0,cc=null;\n'
        '        function fl(){ if(s>=0){ gl.uniform3f(U.uColor,cc[0],cc[1],cc[2]); gl.drawElements(gl.TRIANGLES,c,gl.UNSIGNED_SHORT,s*2); } s=-1;c=0;cc=null; }\n'
        '        for (var i=0;i<B.objs.length;i++) {\n'
        '          var e=B.objs[i];\n'
        '          if (!test(e)) { fl(); continue; }\n'
        '          var col=colOf(e);\n'
        '          if (s>=0 && col!==cc) fl();\n'
        '          if (s<0) { s=e.iStart; cc=col; }\n'
        '          c+=e.iCount;\n'
        '        }\n'
        '        fl();',
        '        var s=-1,c=0,cc=null,mm=-1;\n'
        '        function fl(){ if(s>=0){ gl.uniform3f(U.uColor,cc[0],cc[1],cc[2]); if(q301.mu) gl.uniform1f(U.uMu,mm); gl.drawElements(gl.TRIANGLES,c,gl.UNSIGNED_SHORT,s*2); } s=-1;c=0;cc=null;mm=-1; }\n'
        '        for (var i=0;i<B.objs.length;i++) {\n'
        '          var e=B.objs[i];\n'
        '          if (!test(e)) { fl(); continue; }\n'
        '          var col=colOf(e), mu=q301.mu ? q301.mu(e) : -1;      // Q301: the attenuation is part of the run key\n'
        '          if (s>=0 && (col!==cc || mu!==mm)) fl();\n'
        '          if (s<0) { s=e.iStart; cc=col; mm=mu; }\n'
        '          c+=e.iCount;\n'
        '        }\n'
        '        fl();',
    ),
    # 6. uXr / uD0 are set once per frame, next to the other per-frame uniforms
    (
        '      } else gl.uniform1f(U.uBoxOn,0);\n\n      gl.enableVertexAttribArray(0); gl.enableVertexAttribArray(1);',
        '      } else gl.uniform1f(U.uBoxOn,0);\n\n'
        '      gl.uniform1f(U.uXr, q301.mode === "xray" ? 1 : 0);   // Q301: the DRR branch of the fragment shader\n'
        '      gl.uniform1f(U.uD0, q301.d0);\n'
        '      gl.uniform1f(U.uMu, 1);\n'
        '      gl.uniform1f(U.uFlat, q301.flatten || 0);\n'
        '      gl.enableVertexAttribArray(0); gl.enableVertexAttribArray(1);',
    ),
    # 7. Q300's bone pass is for the colour view: in a DRR the bone stands out from its own attenuation
    (
        '      if (boneRead > 0 && (presetName === "xray" || selGroupFadedQ300())){',
        '      if (boneRead > 0 && q301.mode === "colour" && (presetName === "xray" || selGroupFadedQ300())){   // Q301: paused by any radiographic style, as on the own engine',
    ),
    # 8. the fat layer is OFF when the page loads (Q301 item 6); the 0.12 alpha is kept for when it is switched on
    (
        '    var on = {}; LK.forEach(function (k) { on[k] = true; });',
        '    var on = {}; LK.forEach(function (k) { on[k] = true; });\n'
        '    on.fat = false;        // Q301: plain fat is shown only when explicitly asked; it still fills every cut face (NMSKCapCore.capA)',
    ),
    # 9. the cut face keeps its fat whatever the 3-D state is -- Q295's whole point was that a section must not read as hollow
    (
        '        OBJ.forEach(function(o, i){\n          if (!vis(o)) return;\n          var lk = selLook(o),',
        '        OBJ.forEach(function(o, i){\n'
        '          if (!vis(o)){\n'
        '            if (!(o.layer === "fat" && !on.fat && !hidden.has(o) && passClip(o) && passBox(o))) return;\n'
        '            out.push({key:o.id, name:o.name, cat:"fat", rgb:colOf(o), alpha:Math.max(0.9, alphaFor.fat),   // Q301: fat fills the cut face even when it is not drawn in 3-D\n'
        '              geom:(function(j, p){ return function(){ return capGeom(j, p); }; })(i, o)});\n'
        '            return;\n'
        '          }\n'
        '          var lk = selLook(o),',
        2,
    ),
    # NOTE, deliberately no edit: Q300's own "tissue off" path turned out generic enough. It snapshots the page's load
    #       visibility as ON0 and reports only what the USER switched off (`q300LayersOff`), and ON0 is captured long
    #       after the Q301 fat default is applied -- so the default needs no adjustment there, "Show everything" rightly
    #       leaves fat as the page ships it, and NMSKFat's own registered path is what brings it back.
    # 13. the Z engine's own `reset` button puts every tissue layer back on, which would switch the fat back on against
    #     the Q301 default. It is a reset to the page's defaults, and off IS the default now.
    (
        '      LK.forEach(function(k){on[k]=true;alphaFor[k]=1;});\n'
        '      alphaFor.skin=0.3;',
        '      LK.forEach(function(k){on[k]=true;alphaFor[k]=1;});\n'
        '      alphaFor.skin=0.3;\n'
        '      alphaFor.fat=0.12;\n'
        '      if (window.NMSKFat) NMSKFat.set(false); else on.fat=false;      // Q301: plain fat is off by default, and a reset goes to the default',
    ),
]

# ---------------------------------------------------------------- the own engine (three.js) ----------------------
OWN_EDITS = [
    # 1. the style's own state
    (
        'var XRAY_A = {bone:1, cartilage:0.85, ligament:0.5, tendon:0.5, nerve:1, vessel:0.8, muscle:0.22, organ:0.25, fat:0.05, other:0.12};',
        'var XRAY_A = {bone:1, cartilage:0.85, ligament:0.5, tendon:0.5, nerve:1, vessel:0.8, muscle:0.22, organ:0.25, fat:0.05, other:0.12};\n'
        '/* Q301: the model-wide render style. The spec comes from NMSKRenderStyle and holds greyOf() (the grey each\n'
        '   structure\'s own HU / spin-echo signal gives) and, for the DRR, alphaOf() = 1 - exp(-mu * d0). Ordinary alpha\n'
        '   blending over black then accumulates Beer-Lambert\'s exp(-SUM mu_i d_i), order independently. */\n'
        'var q301spec = null;',
    ),
    # 2. the override, last in the per-mesh loop so it wins over every colour and opacity rule above it
    (
        '    m.material.transparent = m.material.opacity < 1;\n    m.material.depthWrite = m.material.opacity > 0.85;\n  });',
        '    m.material.transparent = m.material.opacity < 1;\n'
        '    m.material.depthWrite = m.material.opacity > 0.85;\n'
        '    if (q301spec && q301spec.mode !== "colour" && vis){           // Q301: the radiographic styles, last word on colour and alpha\n'
        '      var gq = Math.max(0, Math.min(1, q301spec.greyOf(s.cat, s.id, s.name, null)));\n'
        '      if (q301spec.alphaOf){                                       // X-ray: a flat, unlit white whose alpha is the attenuation\n'
        '        m.material.color.setRGB(0, 0, 0);\n'
        '        m.material.emissive.setRGB(1, 1, 1);\n'
        '        m.material.opacity = Math.max(0.004, Math.min(0.995, q301spec.alphaOf(s.cat, s.id, s.name, null)));\n'
        '        m.material.side = THREE.DoubleSide;                        // a ray really does cross a closed shell twice\n'
        '        m.material.transparent = true; m.material.depthWrite = false;\n'
        '      } else {                                                     // CT / MRI: the grey, with the shading kept as a depth cue\n'
        '        var fl = q301spec.flatten == null ? 0.6 : q301spec.flatten;   // the grey IS the datum: the shading must not swamp it\n'
        '        m.material.color.setRGB(gq * (1 - fl * 0.4), gq * (1 - fl * 0.4), gq * (1 - fl * 0.4));\n'
        '        m.material.emissive.setRGB(gq * fl, gq * fl, gq * fl);\n'
        '        m.material.side = THREE.FrontSide;\n'
        '      }\n'
        '    } else if (q301spec === null && m.material.side !== THREE.FrontSide) m.material.side = THREE.FrontSide;\n'
        '  });',
    ),
    # 3. Q300's bone pass belongs to the colour view (see the Z engine's note)
    (
        '  var brOn = boneRead > 0 && (xray || (selCtl && selCtl.active() && (function(){',
        '  var brOn = boneRead > 0 && !(q301spec && q301spec.mode !== "colour") /* Q301: any style pauses it */ && (xray || (selCtl && selCtl.active() && (function(){',
    ),
    # 4. the fat system is OFF when the page loads
    (
        '  on[c] = (c === "bone" || c === "muscle" || c === "fat");   // Q295: fat on but faint (fills the cut faces / cross-sections)',
        '  on[c] = (c === "bone" || c === "muscle");   // Q295 put fat on but faint; Q301: off at load, one tap away, still filling every cut face',
    ),
    (
        '    meshes.forEach(function(m){\n      if (!m.visible) return;\n      var s = m.userData, c = m.material.color;',
        '    meshes.forEach(function(m){\n'
        '      var s = m.userData, c = m.material.color;\n'
        '      if (!m.visible){\n'
        '        /* Q301: fat is off at load, but a section drawn without it reads as hollow -- Q295\'s whole point --\n'
        '           so a fat structure hidden ONLY because its system is off still fills the cut face and the cross-section. */\n'
        '        if (!(s.cat === "fat" && !on.fat && !hideOverride[s.id] && (!s.hidden_default || !!hdShown[s.id]))) return;\n'
        '        out.push({key:s.id, name:(s.rec && s.rec.name) || s.id, cat:s.cat, rgb:[c.r, c.g, c.b], alpha:Math.max(0.9, sysAlpha.fat == null ? 0.12 : sysAlpha.fat),\n'
        '                  geom:function(){ var gg = m.geometry; if (!gg.boundingBox) gg.computeBoundingBox(); return {pos:gg.attributes.position.array, idx:gg.index.array, bmin:gg.boundingBox.min.toArray(), bmax:gg.boundingBox.max.toArray()}; }});\n'
        '        return;\n'
        '      }',
        2,
    ),
]


GLUE_BEGIN, GLUE_END = "/* Q301 glue begin */", "/* Q301 glue end */"
ANCHOR = "window.__q300dbg = {"


def splice_glue(path: Path, glue_file: Path, check: bool) -> int:
    """put the engine's own Q301 wiring into the template, between markers, so re-running updates it in place"""
    t = path.read_text(encoding="utf-8")
    body = glue_file.read_text(encoding="utf-8").rstrip("\n")
    block = f"{GLUE_BEGIN}\n{body}\n{' ' * 6}{GLUE_END}\n"
    if t.count(GLUE_BEGIN) == 1 and t.count(GLUE_END) == 1:
        i, j = t.index(GLUE_BEGIN), t.index(GLUE_END) + len(GLUE_END) + 1
        new = t[:i] + block + t[j:]
    else:
        if t.count(ANCHOR) != 1:
            raise SystemExit(f"{path.name}: glue anchor occurs {t.count(ANCHOR)} times, expected 1")
        i = t.index(ANCHOR)
        new = t[:i] + block + (" " * 6) + t[i:]
    if new == t:
        print(f"glue up to date: {path.relative_to(REPO)}")
        return 0
    if check:
        print(f"glue out of date: {path.relative_to(REPO)}")
        return 1
    path.write_text(new, encoding="utf-8")
    print(f"glue spliced: {path.relative_to(REPO)} ({len(body)} bytes)")
    return 0


def apply(path: Path, edits, check: bool) -> int:
    t0 = t = path.read_text(encoding="utf-8")
    todo = []
    for e in edits:
        old, new = e[0], e[1]
        want = e[2] if len(e) > 2 else 1
        if new in t:
            continue                                   # already applied (idempotent)
        n = t.count(old)
        if n != want:
            raise SystemExit(f"{path.name}: anchor occurs {n} times, expected {want}:\n  {old.splitlines()[0][:110]}")
        t = t.replace(old, new)                        # `want` of them: the cut face and the cross-section share a builder
        todo.append(f"x{want} " + old.splitlines()[0].strip()[:76])
    if t == t0:
        print(f"up to date: {path.relative_to(REPO)}")
        return 0
    if check:
        print(f"out of date: {path.relative_to(REPO)} ({len(todo)} edits pending)")
        for d in todo:
            print("    " + d)
        return 1
    path.write_text(t, encoding="utf-8")
    print(f"patched {path.relative_to(REPO)} ({len(todo)} edits)")
    return 0


def main() -> int:
    check = "--check" in sys.argv
    HERE = Path(__file__).resolve().parent
    return max(apply(ZAN, Z_EDITS, check), apply(OWN, OWN_EDITS, check),
               splice_glue(ZAN, HERE / "glue_zan.js", check), splice_glue(OWN, HERE / "glue_own.js", check))


if __name__ == "__main__":
    raise SystemExit(main())
