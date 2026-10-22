"""Q254 item 7 -- CT/MRI slice-position cine with a speed control (clinical/imaging_tool.js), built on top of
item 5's drag-drift fix (not before it, per the brief).

`cineTick()` steps `S.P` along the ACTIVE view's own plane normal (axial / coronal / sagittal, or an oblique Cut
plane from item 6 alike) by a fixed step in mm, `setCine(on)` drives it on a `setInterval` at the chosen fps, and
the fps `<select>` (1 / 2 / 3 / 5 / 8) is modelled directly on the ultrasound tool's existing `cineBtn` / `fps`
row (`clinical/ultrasound_tool.js`, shared `ui.playBox` pattern since Q253) for a consistent control across both
tools. These are source-contract guards (the UI/interaction layer is not reachable from node in isolation -- see
test_q246_raster.py's docstring for that constraint) plus a direct node run of the bounce logic that keeps the
cine inside the body's own bounding box rather than running off it."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SRC = (REPO / "clinical" / "imaging_tool.js").read_text(encoding="utf-8")
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(not NODE, reason="node not installed")


def test_cine_state_and_functions_defined():
    assert "cine: false, fps: 3" in SRC
    assert "function cineTick()" in SRC
    assert "function setCine(on)" in SRC


def test_cine_steps_the_active_views_own_normal():
    m = re.search(r"function cineTick\(\).*?\n(\s*\}\n)", SRC, re.S)
    assert m
    body = m.group(0)
    assert "viewSpec(S.active)" in body        # works for ax/co/sa AND an oblique Cut plane (item 6), not just one view
    assert "spec.n[0]" in body and "spec.n[1]" in body and "spec.n[2]" in body


def test_fps_selector_matches_ultrasound_tools_options():
    us_opts = re.search(r"\[1, 2, 3, 5, 8\]\.map\(function \(f\) \{ return el\(\"option\"", (REPO / "clinical" / "ultrasound_tool.js").read_text(encoding="utf-8"))
    img_opts = re.search(r"\[1, 2, 3, 5, 8\]\.map\(function \(f\) \{ return el\(\"option\"", SRC)
    assert us_opts and img_opts, "both tools should offer the same fps choices"


def test_cine_stops_on_close_and_round_trips_through_set_state():
    assert "setCine(false); applyLayout();" in SRC
    assert re.search(r'k === "cine".*setCine\(!!p\.cine\);', SRC)
    assert "cine: S.cine, fps: S.fps" in SRC


@needs_node
def test_cine_tick_bounce_logic_numerically(tmp_path):
    m = re.search(r"var CINE_STEP_MM = 2, cineDir = 1;\n(\s*function cineTick\(\) \{.*?\n\s*\}\n)", SRC, re.S)
    assert m
    cine_tick_src = m.group(0)
    script = tmp_path / "check.js"
    script.write_text(
        r"""
var S = {open: true, active: "ax", P: [0, 0, 0]};
var geo = {bodyBox: {lo: [-100, -100, -100], hi: [100, 100, 100]}};
function viewSpec(key) { return {n: [0, 1, 0]}; }   // a fixed-normal view, like axial
var markedDirty = 0;
function markDirty() { markedDirty++; }
function setCine(on) { S.cine = !!on; }
""" + cine_tick_src + r"""
var positions = [];
for (var i = 0; i < 400; i++) { cineTick(); positions.push(S.P[1]); }
var lo = Math.min.apply(null, positions), hi = Math.max.apply(null, positions);
var out = {lo: lo, hi: hi, ticks: markedDirty, bounced: lo > -140 && hi < 140 && (hi - lo) > 50};
console.log(JSON.stringify(out));
if (!out.bounced) throw new Error("cine should bounce back and forth within (roughly) the bodyBox, not run off it: " + JSON.stringify(out));
"""
    )
    r = subprocess.run([NODE, str(script)], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stdout + r.stderr
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert out["bounced"], out
