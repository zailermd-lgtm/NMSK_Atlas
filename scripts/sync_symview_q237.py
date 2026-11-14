#!/usr/bin/env python3
"""Q237: keep the Symmetric-view fragment (viewer/symview/) and its small engine hooks in both viewer templates.

viewer/symview/symview.{css,html,js} is the shared single source (same pattern as scripts/sync_parts_ui_q220.py); viewer/symview/glue_{own,zan}.js is the per-engine adaptor. Each template carries
them verbatim between `SYMVIEW <kind> begin` / `SYMVIEW <kind> end` marker lines. The marker pairs and the few engine-hook lines (Z shader / vis() / draw(), cut-cap items) are inserted
idempotently at fixed anchors, so the script can be re-run on a template that another change touched (it fails loudly when an anchor is gone):

    python3 scripts/sync_symview_q237.py                  # rewrite both templates in viewer/
    python3 scripts/sync_symview_q237.py --check          # exit 1 if a template is out of date
    python3 scripts/sync_symview_q237.py --dir DIR        # operate on DIR/{atlas_viewer,zan_atlas}.template.html (private template copies for a build)
"""
from __future__ import annotations
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FR = REPO / "viewer" / "symview"
MARK = {"css": ("/* SYMVIEW css begin */", "/* SYMVIEW css end */"), "html": ("<!-- SYMVIEW html begin -->", "<!-- SYMVIEW html end -->"),
        "js": ("/* SYMVIEW js begin */", "/* SYMVIEW js end */"), "glue": ("/* SYMVIEW glue begin */", "/* SYMVIEW glue end */")}
# where the marker pairs go: (kind, anchor line-start text, indent). The pair is inserted BEFORE the anchor.
ANCHORS = {
    "own": {"css": "/* PARTS-UI css begin */", "html": "    <!-- PARTS-UI html begin -->", "js": "/* PARTS-UI js begin */", "glue": "window.__selState = function(){ return selCtl.state(); };"},
    "zan": {"css": "  /* PARTS-UI css begin */", "html": "<!-- PARTS-UI html begin -->", "js": "/* PARTS-UI js begin */", "glue": "    window.__selState = function(){ return selCtl.state(); };"},
}
# engine hooks: (old, new); `new` contains `old`; skipped when `new` is already present; `old` must occur exactly once
MIRROR_LABEL = ("MIRROR IMAGE of the opposite side, fitted to this side's bones; not measured on this side: the structure of this body's own opposite side, reflected about the model's midsagittal plane and fitted to this side's bones "
                "(rigid + uniform scale from the neighbouring bones, a bounded conform step out of the bones and inside the skin); the card gives the source, the fit error and the guard numbers. A real left / right difference is not represented (Q237).")
MIRROR_SAY = "Mirror image of the opposite side, fitted to this side's bones \\u2014 not measured on this side."
EDITS = {
    "own": [
        ('  xfer_cvh2vhf_q235: "ANOTHER PERSON\'S REAL ANATOMY', '  mirror_q237: "' + MIRROR_LABEL + '",\n  xfer_cvh2vhf_q235: "ANOTHER PERSON\'S REAL ANATOMY'),
        ('function classifySource(sub, badge){\n  var b = baseSubject(sub);\n', 'function classifySource(sub, badge){\n  var b = baseSubject(sub);\n  if (b.indexOf("mirror_") === 0) return "mirrored_opposite";      // Q237: the missing side as the mirror of the opposite side\n'),
        ('  {k:"other_specimen", name:"Another person\'s CT",', '  {k:"mirrored_opposite", name:"Mirrored from the opposite side", hex:0xE0583A, say:"' + MIRROR_SAY + '"},\n  {k:"other_specimen", name:"Another person\'s CT",'),
        ("    return out;\n  },\n  upload:capUpload, redraw:function(){ draw(); },",
         "    symCap(out);          // Q237: mirrored copies of the Symmetric view\n    return out;\n  },\n  upload:capUpload, redraw:function(){ draw(); },"),
    ],
    "zan": [
        ('"attribute vec3 aPos;attribute vec3 aNrm;uniform mat4 uMVP;uniform mat3 uN;" +\n             "varying vec3 vN;varying vec3 vP;" +\n             "void main(){vN=uN*aNrm;vP=aPos;gl_Position=uMVP*vec4(aPos,1.0);}";',
         '"attribute vec3 aPos;attribute vec3 aNrm;uniform mat4 uMVP;uniform mat3 uN;uniform float uSymOn;uniform vec4 uSym;" +      // Q237: uSym = (n, d) of the midsagittal plane, reflected when uSymOn is set\n'
         '             "varying vec3 vN;varying vec3 vP;" +\n'
         '             "void main(){vec3 p=aPos;vec3 q=aNrm;if(uSymOn>0.5){float s=dot(p,uSym.xyz)-uSym.w;p=p-2.0*s*uSym.xyz;q=q-2.0*dot(q,uSym.xyz)*uSym.xyz;}vN=uN*q;vP=p;gl_Position=uMVP*vec4(p,1.0);}";'),
        ('["uMVP","uN","uColor","uAlpha","uHL","uClip","uClip2","uClipOn","uBoxMin","uBoxMax","uBoxOn"].forEach(function (n) {\n      U[n] =',
         '["uMVP","uN","uColor","uAlpha","uHL","uClip","uClip2","uClipOn","uBoxMin","uBoxMax","uBoxOn","uSymOn","uSym"].forEach(function (n) {\n      U[n] ='),
        ("      if (!on[o.layer] || alphaFor[o.layer] <= 0.01) return false;\n      if (hidden.has(o)) return false;\n",
         "      if (!on[o.layer] || alphaFor[o.layer] <= 0.01) return false;\n      if (symPass ? !symIsSrc(o) : symHide(o)) return false;      // Q237 Symmetric view: the mirrored pass paints only the source side; the other side's originals are hidden while it is on\n      if (hidden.has(o)) return false;\n"),
        ("      if (!passClip(o) || !passBox(o)) return false;\n      return sideOK(o);\n",
         "      if (!passClip(o) || !passBox(o)) return false;\n      return symPass ? symSideOK(o) : sideOK(o);\n"),
        ("      for (var k = 0; k < 3; k++){ m += P[k] * (P[k] > 0 ? o.bmin[k] : o.bmax[k]); m2 += P2[k] * (P2[k] > 0 ? o.bmin[k] : o.bmax[k]); }\n",
         "      var bn = o.bmin, bx = o.bmax; if (symPass){ var sb = symBox(o); bn = sb[0]; bx = sb[1]; }      // Q237: the mirrored copy is tested with the reflected box\n      for (var k = 0; k < 3; k++){ m += P[k] * (P[k] > 0 ? bn[k] : bx[k]); m2 += P2[k] * (P2[k] > 0 ? bn[k] : bx[k]); }\n"),
        ("      if (!box.on) return true;\n      return !(o.bmax[0] < box.min[0] || o.bmax[1] < box.min[1] || o.bmax[2] < box.min[2] ||\n               o.bmin[0] > box.max[0] || o.bmin[1] > box.max[1] || o.bmin[2] > box.max[2]);\n",
         "      if (!box.on) return true;\n      var bn = o.bmin, bx = o.bmax; if (symPass){ var sb = symBox(o); bn = sb[0]; bx = sb[1]; }      // Q237\n      return !(bx[0] < box.min[0] || bx[1] < box.min[1] || bx[2] < box.min[2] ||\n               bn[0] > box.max[0] || bn[1] > box.max[1] || bn[2] > box.max[2]);\n"),
        ("      var opa=[],tra=[];\n", "      function scenePass(){      // Q237: the whole scene is painted once, and once more (mirrored) when the Symmetric view is on\n      var opa=[],tra=[];\n"),
        ("      gl.depthMask(true); gl.disable(gl.BLEND);\n\n      var hi2 = selected || hovered;\n",
         "      gl.depthMask(true); gl.disable(gl.BLEND);\n      }\n      scenePass();\n      if (sym){\n        gl.uniform1f(U.uSymOn,1); gl.uniform4f(U.uSym,sym.plane.n[0],sym.plane.n[1],sym.plane.n[2],sym.plane.d); gl.frontFace(gl.CW); symPass = true;\n"
         "        try { scenePass(); } finally { symPass = false; gl.frontFace(gl.CCW); gl.uniform1f(U.uSymOn,0); }\n      }\n\n      var hi2 = selected || hovered;\n"),
        ("          out.push({key:o.id, name:o.name, cat:o.layer, rgb:c, alpha:a, geom:function(){ return capGeom(i, o); }});\n        });\n        return out;",
         "          out.push({key:o.id, name:o.name, cat:o.layer, rgb:c, alpha:a, geom:function(){ return capGeom(i, o); }});\n        });\n        symCap(out);          // Q237: mirrored copies of the Symmetric view\n        return out;"),
    ],
}


def frag(kind):
    return {"css": FR / "symview.css", "html": FR / "symview.html", "js": FR / "symview.js"}.get(kind)


def render(text: str, eng: str) -> str:
    glue = (FR / ("glue_%s.js" % eng)).read_text(encoding="utf-8").rstrip("\n")
    # 1. marker pairs (insert before the anchor, once)
    for kind, anchor in ANCHORS[eng].items():
        b, e = MARK[kind]
        if b in text:
            if text.count(b) != 1 or text.count(e) != 1:
                raise SystemExit("marker pair for %s must occur exactly once" % kind)
            continue
        if text.count(anchor) != 1:
            raise SystemExit("%s: anchor for the %s marker pair must occur exactly once: %r (found %d)" % (eng, kind, anchor, text.count(anchor)))
        ind = re.match(r"\s*", anchor).group(0) if kind in ("css", "glue") else ""
        text = text.replace(anchor, "%s%s\n%s%s\n%s" % (ind, b, ind, e, anchor), 1)
    # 2. engine hooks
    for old, new in EDITS[eng]:
        if new in text:
            continue
        if text.count(old) != 1:
            raise SystemExit("%s: engine-hook anchor must occur exactly once (found %d): %r" % (eng, text.count(old), old[:90]))
        text = text.replace(old, new, 1)
    # 3. fragments between the markers
    for kind, (b, e) in MARK.items():
        body = glue if kind == "glue" else frag(kind).read_text(encoding="utf-8").rstrip("\n")
        i, j = text.index(b) + len(b), text.index(e)
        text = text[:i] + "\n" + body + "\n" + text[j:]
        # keep the end marker at column 0 only when it was inserted that way; indentation of a marker line is left as inserted
    return text


def main() -> int:
    check = "--check" in sys.argv
    d = REPO / "viewer"
    if "--dir" in sys.argv:
        d = Path(sys.argv[sys.argv.index("--dir") + 1])
    bad = 0
    for eng, name in (("own", "atlas_viewer.template.html"), ("zan", "zan_atlas.template.html")):
        t = d / name
        old = t.read_text(encoding="utf-8")
        new = render(old, eng)
        if new != old:
            if check:
                print("out of date:", t); bad = 1
            else:
                t.write_text(new, encoding="utf-8"); print("synced", t)
        else:
            print("up to date:", t)
    return bad


if __name__ == "__main__":
    raise SystemExit(main())
