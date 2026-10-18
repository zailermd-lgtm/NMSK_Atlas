"""Q257 -- owner round 2026-10-18 on the ultrasound simulation, part 2 ("enable cine like in a continuous exam"):

The existing cine (Q253) is a STEP player: it snaps S.sel between a fixed, pre-computed set of frames (star's 9
tilt directions, or sweep's n parallel offset planes). The owner wants cine to feel like a live exam -- the probe
continuously sliding / sweeping / tilting through a smooth range of positions, not jumping between N fixed planes.

Investigated per the brief's own two options: (a) raise the frame density until it reads as smooth within the
documented per-frame timing budget (Q228: one 480 px frame = slice kernel 12 ms + physics 47 ms), or (b) actually
re-raster continuously as a position parameter sweeps, never faking smoothness by interpolating between the step
frames. Chose (b): a genuinely continuous mode (S.cineMode = "continuous", alongside the existing "step") that
re-computes a brand-new frame at every displayed position -- sweep mode slides the elevational offset smoothly
across the configured total range (ping-pong at the ends); star mode rotates the tilt DIRECTION continuously at
the fixed tilt angle (a smooth fan, instead of the 8 discrete star directions) -- at a reduced "live" raster tier
(contQuality(): 320x192, the SAME tier already used elsewhere in this file for the star ring / larger sweep
matrices, not a new untested one) so it clears the real per-frame budget. The position advances by REAL measured
wall-clock time between frames (never by a fixed frame count), so a slow device shows honestly coarser steps
instead of a faked constant speed -- the same "no interpolation" honesty the brief asked for.

Real headless-Chromium timing (own female, linear 5 cm default placement, best-of-5, scratchpad/q257/timing3.py
+ timing4.py, session-local): one 320x192 frame ~ 23-26 ms (vs. ~41-76 ms at the old default 480x256, matching
Q228's documented ~60 ms figure); even the slowest requested cine speed (fps 1, 6 s one-way) and the fastest
(fps 8, 0.75 s one-way / one turn) both run with large real-time headroom at this tier (<=125 ms budget at fps
8's nominal re-slice target). Driving the actual UI (NMSKUltrasound.set({cineMode:'continuous'}), set({cine:true}))
showed frames[S.sel].spec genuinely changing (sweep .off and star .dir both moved continuously, not snapping among
the N discrete values) with cineStatus().fpsActual populated from real measured per-frame cost -- see
PROJECT_STATE.md Q257 for the full numbers.

This file is a NODE-level source-contract + numeric-formula regression guard, matching the Q253/Q255 precedent
(no committed DOM/browser pytest harness exists for this tool; the real per-frame headless-Chromium timing and
UI-driven re-slicing check above are session-local scratchpad verification, reported in PROJECT_STATE.md, the
same split Q255 used)."""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
TOOL = REPO / "clinical" / "ultrasound_tool.js"
SRC = TOOL.read_text(encoding="utf-8")
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(not NODE, reason="node not installed")


def _node(code: str, timeout=60):
    r = subprocess.run([NODE, "-e", code], capture_output=True, text=True, timeout=timeout, cwd=str(REPO))
    assert r.returncode == 0, r.stderr[-2500:]
    return r.stdout


# ---------------------------------------------------------------- source-contract guards
def test_cine_mode_default_is_step_so_existing_behaviour_is_unchanged():
    assert re.search(r'cineMode:\s*"step"', SRC), "default must stay 'step' -- continuous is opt-in, never the default"


def test_continuous_branch_exists_in_setcine_and_disables_the_old_interval_path():
    m = re.search(r"function setCine\(on\)\s*\{(.*?)\n    \}", SRC, re.S)
    assert m, "setCine() not found"
    body = m.group(1)
    assert 'S.cineMode === "continuous"' in body
    assert "contState.active = true" in body and "reqFrame(contTick)" in body
    assert "setInterval" in body  # the step path is still there, just gated to the else branch


def test_pump_skips_the_discrete_frame_set_while_continuous_cine_owns_frames_sel():
    m = re.search(r"function pump\(\)\s*\{(.*?)\n    \}", SRC, re.S)
    assert m
    assert "if (!S.open || !AC || !S.P || contState.active) return;" in m.group(1), "pump() must bail out early while continuous cine is running, or it would stomp frames[S.sel] every ~70 ms"


def test_cont_tick_advances_position_by_real_elapsed_time_not_a_fixed_step():
    assert "contState.lastT ? Math.min(250, now - contState.lastT) / 1000 : 0" in SRC, \
        "the continuous loop must pace itself off real wall-clock dt, not a fixed per-tick increment (else it would be a disguised, not a genuine, continuous sweep)"


def test_continuous_mode_reuses_an_existing_vetted_quality_tier_not_full_resolution():
    assert re.search(r"function contQuality\(\)\s*\{\s*return\s*\{maxDim:\s*320,\s*maxLines:\s*192\}", SRC)


def test_continuous_frame_specs_carry_the_fields_computeFrame_poseOf_simOpts_already_expect():
    # contSpecSweep / contSpecStar must produce the same shape frameSpecs() does (id, tilt, dir, off[, rotOverride], label, short) -- this
    # is what lets the continuous path reuse poseOf/refFrame/simOpts/computeFrame/paintView unmodified instead of forking the pipeline.
    for name, fields in [("contSpecSweep", ["id:", "tilt:", "dir:", "off:", "rotOverride:", "label:", "short:"]),
                          ("contSpecStar", ["id:", "tilt:", "dir:", "off:", "label:", "short:"])]:
        m = re.search(r"function " + name + r"\(\w+\)\s*\{(.*?)\n    \}", SRC, re.S)
        assert m, name + " not found"
        for f in fields:
            assert f in m.group(1), name + " missing field " + f


def test_ui_has_a_continuous_toggle_and_a_live_fps_readout():
    assert '"continuous"' in SRC and "ui.cineModeBtn" in SRC
    assert "ui.contOut" in SRC and "updateContReadout" in SRC


def test_frame_scrub_slider_is_disabled_while_continuous_cine_plays():
    assert 'ui.frame.disabled = S.cine && S.cineMode === "continuous"' in SRC


def test_info_panel_discloses_the_continuous_tradeoff_honestly():
    assert "RE-SLICES a new frame at every displayed position" in SRC
    assert "not an interpolation between the step frames" in SRC
    assert "actually achieved re-slice rate" in SRC


def test_cine_status_test_hook_exposes_real_measured_fps():
    assert "cineStatus: function ()" in SRC and "fpsActual: contState.fpsActual" in SRC


# ---------------------------------------------------------------- numeric: the speed formula, run for real (node)
@needs_node
def test_cont_one_way_sec_formula_matches_the_documented_fps_to_seconds_mapping():
    code = r"""
      const fs = require('fs'); const src = fs.readFileSync('clinical/ultrasound_tool.js', 'utf8');
      const m = src.match(/function contOneWaySec\(\) \{ return ([^;]+); \}/);
      if (!m) { console.error('contOneWaySec not found'); process.exit(1); }
      const S = {fps: 0};
      const fn = new Function('S', 'Math', 'return ' + m[1] + ';');
      const out = [1, 2, 3, 5, 8].map(f => { S.fps = f; return Math.round(fn(S, Math) * 100) / 100; });
      console.log(JSON.stringify(out));
    """
    import json
    out = json.loads(_node(code))
    assert out == [6.0, 3.0, 2.0, 1.2, 0.75], out  # fps 1 = slow 6 s sweep/turn, fps 8 = fast 0.75 s -- matches the Info panel + PROJECT_STATE claim


@needs_node
def test_sweep_ping_pong_reverses_exactly_at_the_configured_half_range_and_star_wraps_at_360():
    """Re-implements the exact clamp/reverse and modulo-wrap lines pulled from source (copy-checked below) and
    runs them over a small simulated time series, checking the position never leaves [-half, half] (sweep) or
    [0, 360) (star), and that direction actually reverses at the sweep bound (a real ping-pong, not a one-way
    drift that would silently stop updating the image)."""
    assert "contState.pos > half) { contState.pos = half; contState.dir = -1; } else if (contState.pos < -half) { contState.pos = -half; contState.dir = 1; }" in SRC
    assert '((contState.pos + degPerSec * dt) % 360 + 360) % 360' in SRC
    code = r"""
      let pos = 0, dir = 1; const half = 25; // n=6, spacing=10mm -> half = 10*5/2
      const speed = 50 / 2; // half*2 / oneWaySec(2s)
      let dtSeries = Array(400).fill(0.05); let minP=1e9, maxP=-1e9, reversed=false, lastDir=dir;
      for (const dt of dtSeries) {
        pos += dir * speed * dt;
        if (pos > half) { pos = half; dir = -1; } else if (pos < -half) { pos = -half; dir = 1; }
        if (dir !== lastDir) reversed = true; lastDir = dir;
        minP = Math.min(minP, pos); maxP = Math.max(maxP, pos);
      }
      console.log(JSON.stringify({minP, maxP, reversed, inBounds: minP >= -half - 1e-9 && maxP <= half + 1e-9}));
    """
    import json
    out = json.loads(_node(code))
    assert out["inBounds"] is True and out["reversed"] is True, out
    assert abs(out["maxP"] - 25) < 1e-6 and abs(out["minP"] + 25) < 1e-6, out


@needs_node
def test_js_syntax_still_clean():
    r = subprocess.run([NODE, "--check", str(TOOL)], capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, r.stderr
