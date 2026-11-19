"""Q254 item 5 -- CT/MRI slices going blank and staying blank under rapid crosshair-dragging.

Root cause (found via a real headless-Chromium interactive repro, scripts kept under the session's scratchpad,
not committed): `pointOf()` mapped a drag's screen pixel to a 3-D point using the VIEW'S LIVE spec (spec.O tracks
the current S.P for the ax/co/sa views). Once events arrive faster than the 30 ms markDirty debounce -- which
happens on any sufficiently fast real drag, not just a synthetic one -- a redraw can land *mid-gesture*, re-centring
the view on the point the drag only just set. The next move's pixel offset is then added on top of that already-
shifted centre instead of the original one: a feedback loop. Confirmed empirically (node not needed for the repro
itself, see PROJECT_STATE Q254): an unthrottled synthetic drag of ~160 pointer-moves pushed S.P to kilometres
outside the body's own bounding box, at which point every MPR view renders a uniform (blank) image and --
critically -- stays that way, since nothing ever pulls S.P back into range.

Fix: `freezeFrame(v)` snapshots the view's pixel->3D mapping (O, u, v, n, u0, v0, px) once, on pointer-down;
`onPointer`'s "down" and "move" handlers for a crosshair drag pass that SAME frozen frame to every
`setAnchorFromView(..., frame)` call for the rest of that one gesture, so the mapping no longer moves out from
under the user mid-drag. A fresh frame is captured on the next pointer-down (so single clicks, and the start of
every new gesture, are unaffected and still use the then-current, correctly-displayed frame).

These are source-contract guards (the UI/interaction layer is not reachable from node in isolation -- see
test_q246_raster.py's docstring for the same constraint on this file) plus a direct node run of the two pure
pixel<->3D functions themselves (`pointOf`, `freezeFrame`), executed from the real shipped source text, which
demonstrates the fix's actual arithmetic: a simulated redraw mid-drag diverges under the OLD (live-frame) formula
and stays bounded under the NEW (frozen-frame) one.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SRC = (REPO / "clinical" / "imaging_tool.js").read_text(encoding="utf-8")
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(not NODE, reason="node not installed")


def _fn(name: str) -> str:
    m = re.search(r"\n(\s*function %s\(.*?\n\s*\}\n)" % re.escape(name), SRC, re.S)
    assert m, f"{name} not found in imaging_tool.js"
    return m.group(1)


# ---------------------------------------------------------------- source-contract guards
def test_freeze_frame_defined():
    assert "function freezeFrame(v)" in SRC


def test_point_of_takes_a_frame_param():
    assert re.search(r"function pointOf\(v, ix, iy, along, frame\)", SRC)
    # and actually uses it (falls back to the live v.spec only when no frame is given)
    body = _fn("pointOf")
    assert "frame ||" in body or "frame||" in body.replace(" ", "")


def test_set_anchor_from_view_forwards_frame():
    assert re.search(r"function setAnchorFromView\(v, ix, iy, frame\)", SRC)
    body = _fn("setAnchorFromView")
    assert re.search(r"pointOf\(v, ix, iy, along, frame\)", body)


def test_cross_drag_sites_pass_the_frozen_frame():
    # old buggy pattern (both call sites with no 4th arg) must be gone
    assert "setAnchorFromView(v, q[0], q[1]);" not in SRC
    # down: captures a frame and uses it immediately
    assert re.search(r'drag = \{mode: "cross", v: v, frame0: freezeFrame\(v\)\}; if \(inside\) setAnchorFromView\(v, q\[0\], q\[1\], drag\.frame0\);', SRC)
    # move: reuses the SAME frame captured at down, not a fresh live one
    assert re.search(r'drag\.mode === "cross" && drag\.v === v && inside\) setAnchorFromView\(v, q\[0\], q\[1\], drag\.frame0\);', SRC)


def test_readout_path_unaffected():
    # the hover readout (not a drag mutation) must keep reading the LIVE frame (no frame arg) -- only the
    # drag-anchor path needed freezing
    assert re.search(r"var p = pointOf\(v, ix, iy, v\.offs\.length \? v\.offs\[v\.mid\] : 0\), valTxt;", SRC)


# ---------------------------------------------------------------- direct numeric run of the shipped functions
@needs_node
def test_frozen_frame_stops_the_feedback_loop_numerically(tmp_path):
    point_of = _fn("pointOf")
    freeze_frame = _fn("freezeFrame")
    script = tmp_path / "check.js"
    script.write_text(
        point_of + "\n" + freeze_frame + "\n" + r"""
function makeView(O, px) {
  return {spec: {O: O.slice(), u: [1, 0, 0], v: [0, 0, 1], n: [0, -1, 0]}, cu: 0, cv: 0, px: px, W: 320, H: 320};
}
// a drag of 8 moves, each a pixel offset of +40px from view-centre (a believable fast, steady drag), with a
// redraw landing after moves 2, 4 and 6 (i.e. S.P / spec.O updates mid-gesture) -- exactly the race window a
// fast real drag opens once events outrun the 30 ms debounce.
var OFFSET_PX = 40, REDRAW_AFTER = [2, 4, 6];

function runOld() {
  var v = makeView([0, 0, 0], 1.4);
  for (var i = 1; i <= 8; i++) {
    var ix = v.W / 2 + OFFSET_PX, iy = v.H / 2;              // same screen pixel every move (steady hand)
    var p = pointOf(v, ix, iy, 0);                            // OLD call site: no frame -> reads v.spec (live)
    if (REDRAW_AFTER.indexOf(i) >= 0) v.spec.O = p.slice();   // a redraw re-centres the view on the just-set point
  }
  return v.spec.O;
}
function runNew() {
  var v = makeView([0, 0, 0], 1.4);
  var frame = freezeFrame(v);                                 // captured ONCE, at the gesture's pointer-down
  var last = null;
  for (var i = 1; i <= 8; i++) {
    var ix = v.W / 2 + OFFSET_PX, iy = v.H / 2;
    var p = pointOf(v, ix, iy, 0, frame);                      // NEW call site: frozen frame throughout
    last = p;
    if (REDRAW_AFTER.indexOf(i) >= 0) v.spec.O = p.slice();    // the view still redraws/re-centres on screen...
  }
  return last;                                                 // ...but the drag's own mapping never re-reads it
}
var oldEnd = runOld(), newEnd = runNew();
var oldDist = Math.hypot(oldEnd[0], oldEnd[1], oldEnd[2]);
var newDist = Math.hypot(newEnd[0], newEnd[1], newEnd[2]);
var expected = OFFSET_PX * 1.4;                                 // one honest 40 px move = 56 mm, nothing more
console.log(JSON.stringify({oldDist: oldDist, newDist: newDist, expected: expected}));
if (!(oldDist > expected * 2)) throw new Error("expected the OLD (live-frame) formula to run away well past one offset's worth; got " + oldDist);
if (Math.abs(newDist - expected) > 1e-6) throw new Error("expected the NEW (frozen-frame) formula to land at exactly one offset's worth (" + expected + "); got " + newDist);
"""
    )
    r = subprocess.run([NODE, str(script)], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stdout + r.stderr
