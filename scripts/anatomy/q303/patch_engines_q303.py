#!/usr/bin/env python3
"""Q303: the ENGINE SIDE of the round, applied to both templates as exact, idempotent string replacements.

Everything that can be shared lives in viewer/q303/ and is spliced by scripts/sync_q303.py. What cannot be shared is
here, because only the two engines know how to draw: four panes are four viewports over one scene, and each engine owns
its own draw loop. Each replacement is anchored on a unique string and refuses to guess.

The pane trick, and why it needs so little: in a 2x2 grid every pane is exactly half the canvas in each direction, so a
pane is a SCALED COPY of the full canvas with the same projection. The engines' picking, ray casting, dragging and
pinching therefore work untouched -- NMSKFourUp maps a pointer inside a pane to the full-canvas pixel it corresponds to
with one linear scale (in viewer/q303/fourup.js), and the ACTIVE pane is drawn LAST so the engine's own `lastMVP` /
camera end up being that pane's, which is what the picking path reads.

    python3 scripts/anatomy/q303/patch_engines_q303.py          # apply (idempotent)
    python3 scripts/anatomy/q303/patch_engines_q303.py --check   # exit 1 if a template still needs it
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
OWN = REPO / "viewer" / "atlas_viewer.template.html"
ZAN = REPO / "viewer" / "zan_atlas.template.html"

# ---------------------------------------------------------------- the Z engine (own WebGL) -----------------------
Z_EDITS = [
    # 1. draw() becomes a loop over the panes; the body it used to be is drawPane().
    (
        "    var drawCount = 0;\n"
        "    function draw() {\n"
        "      drawCount++;\n",
        "    var drawCount = 0;\n"
        "    /* Q303: four panes of the same model, each with its own camera. One scene, four viewports -- every other\n"
        "       piece of state (selection, marks, hiding, the layers, the peel, the style, the cut) is the engine's\n"
        "       single state, so the panes cannot disagree. The ACTIVE pane is drawn LAST on purpose: lastMVP / lastEye /\n"
        "       lastRight / lastUp are left holding its camera, which is exactly what pick(), pickPoint() and the\n"
        "       add-on ray path read, so none of them needs an edit. */\n"
        "    var q303panes = null;\n"
        "    function q303setPanes(L){ q303panes = (L && L.length) ? L : null; need = true; }\n"
        "    function q303cur(){ return q303panes ? q303panes._cur : null; }\n"
        "    function q303ph(){ var p = q303cur() || (q303panes && q303panes.length ? q303panes[0] : null); return p ? p.h : 1; }\n"
        "    function q303vp(){\n"
        "      var p = q303cur();\n"
        "      if (!p){ gl.disable(gl.SCISSOR_TEST); gl.viewport(0, 0, W, H); return; }\n"
        "      var x = Math.round(p.x * W), y = Math.round((1 - p.y - p.h) * H);\n"
        "      var w = Math.max(1, Math.round(p.w * W)), h = Math.max(1, Math.round(p.h * H));\n"
        "      gl.enable(gl.SCISSOR_TEST); gl.scissor(x, y, w, h); gl.viewport(x, y, w, h);\n"
        "    }\n"
        "    function q303aspect(){ var p = q303cur(); return p ? (p.w * W) / Math.max(1, p.h * H) : W / Math.max(1, H); }\n"
        "    function draw(){\n"
        "      var P = q303panes;\n"
        "      if (!P){ drawPane(); return; }\n"
        "      var ord = P.slice().sort(function(a, b){ return (a.active ? 1 : 0) - (b.active ? 1 : 0); });\n"
        "      var sv = {az:cam.az, el:cam.el, dist:cam.dist, tgt:cam.tgt.slice()};\n"
        "      for (var qi = 0; qi < ord.length; qi++){\n"
        "        P._cur = ord[qi];\n"
        "        cam.az = ord[qi].az; cam.el = ord[qi].el; cam.dist = ord[qi].dist; cam.tgt = ord[qi].tgt.slice();\n"
        "        drawPane();\n"
        "      }\n"
        "      P._cur = null;\n"
        "      cam.az = sv.az; cam.el = sv.el; cam.dist = sv.dist; cam.tgt = sv.tgt;\n"
        "      gl.disable(gl.SCISSOR_TEST); gl.viewport(0, 0, W, H);\n"
        "    }\n"
        "    function drawPane() {\n"
        "      drawCount++;\n"
        "      q303vp();\n",
    ),
    # 2. the projection takes the PANE's aspect (identical to the canvas's in a 2x2, but written for any grid)
    (
        "      var mvp=mMul(mP(0.85,W/H,HGT*0.02,HGT*14),view);",
        "      var mvp=mMul(mP(0.85,q303aspect(),HGT*0.02,HGT*14),view);   /* Q303: the pane's own aspect */",
    ),
    # 3. the one-camera overlays stand down while four panes are on (they are drawn for ONE camera over the whole
    #    canvas, so in four panes they would be in the wrong place; the i says so and expanding a pane brings them back)
    (
        "      if (cutCtl) cutCtl.overlay();\n"
        "      if (partsCtl) partsCtl.overlay();\n"
        "      if (labelsCtl) labelsCtl.update();       // Q236: structure labels (DOM / SVG overlay; throttled ID pass inside)\n"
        "    }",
        "      if (!q303panes){                         /* Q303: these are drawn for ONE camera over the whole canvas */\n"
        "        if (cutCtl) cutCtl.overlay();\n"
        "        if (partsCtl) partsCtl.overlay();\n"
        "        if (labelsCtl) labelsCtl.update();       // Q236: structure labels (DOM / SVG overlay; throttled ID pass inside)\n"
        "      }\n"
        "    }",
    ),
    # 4. the ID / depth passes render into their own framebuffer at full size: the pane scissor must not survive into them
    (
        "    function renderIds(all, depth, sc) {      // sc (Q236): render into the lower-left sc * W x sc * H corner only (the small label ID image)\n"
        "      var PP = depth ? dprog : pprog, PU = depth ? DU : PUid;\n"
        "      pickTarget();",
        "    function renderIds(all, depth, sc) {      // sc (Q236): render into the lower-left sc * W x sc * H corner only (the small label ID image)\n"
        "      var PP = depth ? dprog : pprog, PU = depth ? DU : PUid;\n"
        "      gl.disable(gl.SCISSOR_TEST);            // Q303: a pane's scissor must never reach the ID / depth image\n"
        "      pickTarget();",
    ),
    # 5. pan and pinch-zoom measure in pixels of the view they act in, which is a pane when four are on
    (
        "    function pzPxWorld(){ var r=canvas.getBoundingClientRect(); return 2*cam.dist*Math.tan(0.425)/Math.max(1,r.height); }",
        "    function pzPxWorld(){ var r=canvas.getBoundingClientRect(); return 2*cam.dist*Math.tan(0.425)/Math.max(1,r.height*q303ph()); }   /* Q303: a pane is the view now */",
    ),
]

# ---------------------------------------------------------------- the own engine (three.js) ----------------------
OWN_EDITS = [
    # 1. the whole draw(), replaced by a pane-aware one. autoClear is turned off and each pane clears its own scissor
    #    box, or renderer.render() would wipe the panes drawn before it.
    (
        "function draw(){\n"
        "  if (partsCtl) partsCtl.update();          // Q220: which part markers are drawn (selection / toggle, cut + slab, layer state)\n"
        "  renderer.render(scene, camera);\n"
        "  drawAxes(); drawScale();\n"
        "  if (cutCtl) cutCtl.overlay();\n"
        "  if (partsCtl) partsCtl.overlay();\n"
        "  if (labelsCtl) labelsCtl.update();       // Q236: structure labels (DOM / SVG overlay; throttled ID pass inside)\n"
        "}",
        "/* Q303: four panes of the same model, each with its own camera. One scene, four viewports -- every other piece\n"
        "   of state (selection, marks, hiding, the layers, the peel, the style, the cut) is the engine's single state,\n"
        "   so the panes cannot disagree. The ACTIVE pane is drawn LAST and its camera is left installed, which is what\n"
        "   pickHit() reads, so the picking path needs no edit. The one-camera overlays (the labels, the gnomon, the\n"
        "   scale bar, the cut outline, the part markers) stand down while four panes are on rather than being drawn in\n"
        "   the wrong place; the circled i says so, and expanding a pane brings them straight back. */\n"
        "var q303panes = null, q303cur = null;\n"
        "function q303setPanes(L){ q303panes = (L && L.length) ? L : null; draw(); }\n"
        "function q303ph(){ var p = q303cur || (q303panes && q303panes.length ? q303panes[0] : null); return p ? p.h : 1; }\n"
        "function draw(){\n"
        "  if (partsCtl) partsCtl.update();          // Q220: which part markers are drawn (selection / toggle, cut + slab, layer state)\n"
        "  var P = q303panes;\n"
        "  if (P){\n"
        "    var w = Math.max(1, stage.clientWidth), h = Math.max(1, stage.clientHeight);\n"
        "    var sv = {az:az, el:el, dist:dist, tgt:target.clone()}, ac = renderer.autoClear;\n"
        "    var ord = P.slice().sort(function(a, b){ return (a.active ? 1 : 0) - (b.active ? 1 : 0); });\n"
        "    renderer.autoClear = false; renderer.setScissorTest(true);\n"
        "    ord.forEach(function(p){\n"
        "      q303cur = p;\n"
        "      var x = Math.round(p.x * w), y = Math.round((1 - p.y - p.h) * h);\n"
        "      var pw = Math.max(1, Math.round(p.w * w)), ph = Math.max(1, Math.round(p.h * h));\n"
        "      renderer.setViewport(x, y, pw, ph); renderer.setScissor(x, y, pw, ph);\n"
        "      az = p.az; el = p.el; dist = p.dist;\n"
        "      target.set(p.tgt[0] + root.position.x, p.tgt[1] + root.position.y, p.tgt[2] + root.position.z);\n"
        "      camera.aspect = pw / ph; camera.updateProjectionMatrix(); place();\n"
        "      renderer.clear();\n"
        "      renderer.render(scene, camera);\n"
        "    });\n"
        "    renderer.setScissorTest(false); renderer.autoClear = ac;\n"
        "    renderer.setViewport(0, 0, w, h);\n"
        "    az = sv.az; el = sv.el; dist = sv.dist; target.copy(sv.tgt);\n"
        "    place();                                 /* the active pane's camera stays installed: pickHit() uses it */\n"
        "    q303cur = null;\n"
        "    return;\n"
        "  }\n"
        "  if (stage.clientHeight > 0 && camera.aspect !== stage.clientWidth / stage.clientHeight){\n"
        "    camera.aspect = stage.clientWidth / stage.clientHeight; camera.updateProjectionMatrix(); place();   /* Q303: leaving four panes restores the full-canvas aspect */\n"
        "  }\n"
        "  renderer.render(scene, camera);\n"
        "  drawAxes(); drawScale();\n"
        "  if (cutCtl) cutCtl.overlay();\n"
        "  if (partsCtl) partsCtl.overlay();\n"
        "  if (labelsCtl) labelsCtl.update();       // Q236: structure labels (DOM / SVG overlay; throttled ID pass inside)\n"
        "}",
    ),
    # 2. pan and pinch-zoom measure in pixels of the view they act in, which is a pane when four are on
    (
        "function pzPxWorld(){ var r = renderer.domElement.getBoundingClientRect(); return 2 * dist * Math.tan(camera.fov * Math.PI / 360) / Math.max(1, r.height); }",
        "function pzPxWorld(){ var r = renderer.domElement.getBoundingClientRect(); return 2 * dist * Math.tan(camera.fov * Math.PI / 360) / Math.max(1, r.height * q303ph()); }   /* Q303: a pane is the view now */",
    ),
]

GLUE_BEGIN, GLUE_END = "/* Q303 glue begin */", "/* Q303 glue end */"
ANCHOR = "window.__q300dbg = {"


def splice_glue(path: Path, glue_file: Path, check: bool) -> int:
    """put the engine's own Q303 wiring into the template, between markers, so re-running updates it in place"""
    t = path.read_text(encoding="utf-8")
    body = glue_file.read_text(encoding="utf-8").rstrip("\n")
    indent = " " * (6 if path is ZAN else 2)
    block = f"{GLUE_BEGIN}\n{body}\n{indent}{GLUE_END}\n"
    if t.count(GLUE_BEGIN) == 1 and t.count(GLUE_END) == 1:
        i, j = t.index(GLUE_BEGIN), t.index(GLUE_END) + len(GLUE_END) + 1
        new = t[:i] + block + t[j:]
    else:
        if t.count(ANCHOR) != 1:
            raise SystemExit(f"{path.name}: glue anchor occurs {t.count(ANCHOR)} times, expected 1")
        i = t.index(ANCHOR)
        new = t[:i] + block + indent + t[i:]
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
        t = t.replace(old, new)
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
