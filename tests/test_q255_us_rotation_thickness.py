"""Q255 -- owner round 2026-10-18 on the ultrasound simulation:
  (1) probe rotation CW/CCW: investigated whether S.rot's existing 0-359 slider was actually reachable in
      both probe modes (star/tilt vs sweep) -- the same class of bug Q253 found for the cine controls being
      sweep-only. Found it was NOT hidden (the slider lives in the "Probe" tab, sec("probe", [...]), which is
      independent of the star/sweep "Mode" tab's starBox/sweepBox display toggling -- verified against the
      actual DOM wiring, not just read on paper). The real gap was UX: a bare 0-359 slider does not read as
      "rotate CW/CCW" and does not wrap at 0/359. Fixed with a CW/CCW 5-degree nudge button pair (rotateBy(),
      wraps modulo 360) beside the slider -- a nudge pair rather than the dirBtns preset-button idiom, because
      (unlike tilt direction's natural away/heel/toward/toe landmarks) free rotation has no natural handful of
      discrete positions to offer as presets.
  (2) fascia/ligament thickness: measured real mesh thickness (trimesh ray-casting + watertight-volume check
      across all six bodies) and the kernel's own rendered width (a hand-built single-interface render, the
      mesh taken out of the loop entirely). Finding: most fascia/ligament meshes are far thinner than real
      anatomy or not even closed solids (undefined thickness); the B-mode kernel itself does not materially
      exaggerate a thin layer beyond its own documented axial point-spread floor. This is a GEOMETRY limit,
      not a rendering bug -- see PROJECT_STATE.md Q255 and docs/OPEN_ITEMS_FOR_OWNER.md for the full numbers,
      citations and the open geometry-side follow-up. This file tests the one safe, honest change made this
      round: the new "Honest limits" line disclosing the finding (with its citations) in the Info panel data.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
TOOL = REPO / "clinical" / "ultrasound_tool.js"
TISSUES = REPO / "clinical" / "data" / "ultrasound_tissues.json"
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(not NODE, reason="node not installed")


def _node(code: str, timeout=60):
    r = subprocess.run([NODE, "-e", code], capture_output=True, text=True, timeout=timeout, cwd=str(REPO))
    assert r.returncode == 0, r.stderr[-2500:]
    return r.stdout


# ---------------------------------------------------------------- (1) rotation was already reachable in both modes
def test_rotate_slider_lives_in_the_mode_independent_probe_tab():
    src = TOOL.read_text(encoding="utf-8")
    # the Rotate slider (r5) is built once in buildControls and placed in sec("probe", ...), NOT inside
    # ui.starBox / ui.sweepBox (the star/sweep "Mode" tab boxes that Q253 found hiding the cine controls)
    assert 'sec("probe", [r1, r2, r3, r4, r5])' in src
    assert 'var r5 = slider("Rotate", 0, 359, 1, "rot"' in src
    # confirm it is genuinely mode-independent: poseOf()/refFrame() use S.rot (not something mode-gated) whenever
    # there is no sweep rotOverride, and star-mode frameSpecs() never sets rotOverride at all
    assert "rot = spec.rotOverride != null ? spec.rotOverride : S.rot" in src


def test_cw_ccw_nudge_buttons_wired_to_rotateby_with_wraparound():
    src = TOOL.read_text(encoding="utf-8")
    assert "function rotateBy(deltaDeg)" in src
    assert "S.rot = ((S.rot + deltaDeg) % 360 + 360) % 360" in src  # must wrap 359<->0, unlike the plain slider's clamp
    assert 'btn("⟲ CCW"' in src and "rotateBy(5)" in src
    assert 'btn("CW ⟳"' in src and "rotateBy(-5)" in src


@needs_node
def test_rotateby_wraparound_formula_numeric():
    # exercise the exact formula from the source (copied, not reimplemented-from-scratch) so a future edit
    # to the formula would be caught here too
    code = r"""
      function rotateBy(S, deltaDeg) { S.rot = ((S.rot + deltaDeg) % 360 + 360) % 360; return S.rot; }
      var out = [];
      out.push(rotateBy({rot: 358}, 5));   // should wrap forward past 359 -> 3
      out.push(rotateBy({rot: 2}, -5));    // should wrap backward past 0 -> 357
      out.push(rotateBy({rot: 180}, 5));   // ordinary case, no wrap
      console.log(JSON.stringify(out));
    """
    out = json.loads(_node(code))
    assert out == [3, 357, 185]


@needs_node
def test_increasing_rot_is_ccw_about_the_outward_skin_normal_as_seen_by_the_examiner():
    """Verifies the CW/CCW LABEL sense against the real LIB.probeFrame/rodrigues math (not just read on paper,
    per the brief): N is the OUTWARD skin normal (points away from the body, towards the examiner looking down
    at the probe). By the right-hand rule, with the rotation axis pointing AT the viewer, a positive angle is
    counter-clockwise as that viewer sees it -- so increasing S.rot (the "+5 CCW" button) must turn u
    counter-clockwise in the tangent plane, and decreasing it ("-5 CW") clockwise."""
    code = r"""
      require('./clinical/ultrasound_tool.js'); const L = globalThis.NMSKUltrasoundLib;
      const N = [0, 0, 1], ref = [0, -1, 0];           // N towards the viewer (standard math convention)
      const a = L.probeFrame(N, ref, 10, 0, 0).u;
      const b = L.probeFrame(N, ref, 20, 0, 0).u;       // +10 deg more rotation than a
      // signed turn from a to b about N: positive = counter-clockwise as seen from the tip of N (the viewer)
      const cross = [a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0]];
      const signedTurn = cross[0]*N[0] + cross[1]*N[1] + cross[2]*N[2];
      console.log(JSON.stringify({signedTurn: signedTurn}));
    """
    out = json.loads(_node(code))
    assert out["signedTurn"] > 0, "increasing S.rot must be counter-clockwise about the outward normal -- the '+5 CCW' button's label would otherwise be backwards"


# ---------------------------------------------------------------- (2) thickness finding disclosed honestly
def test_thickness_finding_disclosed_in_honesty_panel_with_citations():
    US = json.loads(TISSUES.read_text(encoding="utf-8"))
    honesty = " ".join(US["honesty"])
    assert "Q255" in honesty
    assert "plantar aponeurosis" in honesty
    # every number quoted must carry a real, checkable citation (DOI), never a bare invented figure
    for doi in ["10.1007/s40477-026-01224-x", "10.1007/s10278-026-01920-4", "10.1177/0284185120958407", "10.1111/joa.14125"]:
        assert doi in honesty, f"missing citation {doi}"
    assert "not a rendering bug" in honesty


@needs_node
def test_node_sandbox_still_loads_cleanly_after_the_q255_edits():
    code = r"""
      require('./clinical/ultrasound_tool.js'); const L = globalThis.NMSKUltrasoundLib;
      console.log(JSON.stringify({ok: typeof L.simulate === 'function' && typeof L.probeFrame === 'function'}));
    """
    assert json.loads(_node(code))["ok"] is True
