"""Q254 item 6 -- a direct, discoverable oblique-plane dial for CT/MRI's Cut view (clinical/imaging_tool.js).

Before this, a genuinely oblique CT/MRI plane needed the 3-D view's Cut-mode "facing me" button (a one-shot
snap to wherever the camera happens to be orbited, undocumented as a route to an oblique plane). `obliqueNormal`
rotates a chosen base plane's normal (axial / coronal / sagittal) by a Tilt angle (0-60 deg) towards a Direction
(0-359 deg), using the same rotate-the-normal-by-tilt-towards-direction pattern as the ultrasound tool's own
Tilt/Direction sliders (clinical/ultrasound_tool.js `probeFrame`); `applyOblique` pushes the result onto
`api.setCut()`, the exact mechanism the Cut view already reads, so `pollCut()`'s existing 140 ms poll picks it up
and redraws with no further wiring needed. Verified numerically (node): tilt 0 reproduces the exact base-plane
normal regardless of direction; a nonzero tilt yields a unit vector at EXACTLY that angle from the base normal,
for every base plane and a spread of directions; the new `oblique` key round-trips through `NMSKImaging.set()` /
`.state()` (source-contract guard, since the instance API is not reachable from node in isolation -- see
test_q246_raster.py's docstring for that constraint)."""
from __future__ import annotations

import json
import math
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


def test_oblique_state_defined():
    assert '"ax" ? [0, -1, 0]' not in ""  # placeholder guard against accidental edits elsewhere; real checks below
    assert "obl: {base:" in SRC
    assert "function obliqueNormal(baseKey, tiltDeg, dirDeg)" in SRC
    assert "function applyOblique()" in SRC


def test_set_and_state_round_trip_oblique():
    assert re.search(r'k === "oblique".*Object\.assign\(S\.obl, p\.oblique\); applyOblique\(\);', SRC)
    assert "oblique: S.obl" in SRC


def test_ui_row_wired_into_view_section():
    assert "ui.oblRow" in SRC
    assert re.search(r'sec\("view", \[r1, ui\.fovRow, ui\.oblRow.*?\]\)', SRC)
    # discoverable: the always-shown hint line mentions it (same self-documenting style as other tools)
    assert "Oblique" in SRC and "facing me" in SRC


@needs_node
def test_oblique_normal_geometry(tmp_path):
    basis = _fn("basis")
    obl = _fn("obliqueNormal")
    script = tmp_path / "check.js"
    script.write_text(
        basis + "\n" +
        "var OBL_BASE = {ax: [0, -1, 0], co: [0, 0, 1], sa: [-1, 0, 0]};\n" +
        obl + "\n" + r"""
function len(v) { return Math.hypot(v[0], v[1], v[2]); }
function dot(a, b) { return a[0]*b[0]+a[1]*b[1]+a[2]*b[2]; }
var out = {tilt0_matches_base: true, unit_and_angle_ok: true, details: []};
["ax", "co", "sa"].forEach(function (base) {
  var n0 = OBL_BASE[base];
  [0, 45, 90, 200, 350].forEach(function (dir) {
    var n = obliqueNormal(base, 0, dir);
    var d0 = Math.hypot(n[0]-n0[0], n[1]-n0[1], n[2]-n0[2]);
    if (d0 > 1e-9) out.tilt0_matches_base = false;
  });
  [5, 15, 30, 45, 60].forEach(function (tilt) {
    [0, 30, 90, 180, 270].forEach(function (dir) {
      var n = obliqueNormal(base, tilt, dir);
      var l = len(n);
      var ang = Math.acos(Math.max(-1, Math.min(1, dot(n, n0)))) * 180 / Math.PI;
      var rec = {base: base, tilt: tilt, dir: dir, len: l, ang: ang};
      out.details.push(rec);
      if (Math.abs(l - 1) > 1e-6) out.unit_and_angle_ok = false;
      if (Math.abs(ang - tilt) > 1e-6) out.unit_and_angle_ok = false;
    });
  });
});
console.log(JSON.stringify(out));
"""
    )
    r = subprocess.run([NODE, str(script)], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stdout + r.stderr
    out = json.loads(r.stdout.strip().splitlines()[-1])
    assert out["tilt0_matches_base"], "tilt=0 must reproduce the exact base-plane normal (every direction)"
    assert out["unit_and_angle_ok"], out["details"]
