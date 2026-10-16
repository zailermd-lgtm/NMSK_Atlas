"""Q253 (partial) -- ultrasound tool upgrades, owner round 2026-10-16:
  (2) probe-frequency / depth mismatch warning: pure-function unit tests (LIB.probeMismatch), numeric.
  (3)+(4) cine single-frame movie + tilt schematic now available in STAR mode too (previously sweep-only):
       no browser/DOM harness exists yet to click-test the UI, so this is a source-level regression guard
       for the specific gates that were fixed, not a rendered-pixel check. A real browser pass (Q228-style,
       e.g. extending scripts/clinical/q228_check.py) is still open -- see PROJECT_STATE.md Q253.
Items 1 (per-muscle fiber orientation), 5 (CT/MRI slice-scrub flicker), 6 (oblique CT/MRI planes) and
7 (CT/MRI cine) are investigated in PROJECT_STATE.md Q253 but not implemented in this round.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
TOOL = REPO / "clinical" / "ultrasound_tool.js"
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(not NODE, reason="node not installed")


def _node(code: str, timeout=60):
    r = subprocess.run([NODE, "-e", code], capture_output=True, text=True, timeout=timeout, cwd=str(REPO))
    assert r.returncode == 0, r.stderr[-2500:]
    return r.stdout


# ---------------------------------------------------------------- (2) probe/depth mismatch
@needs_node
def test_probe_mismatch_flags_the_owners_two_named_examples():
    code = r"""
      require('./clinical/ultrasound_tool.js'); const L = globalThis.NMSKUltrasoundLib;
      const hand = L.probeMismatch(3.5, 2, 0.6);      // owner's example: 3 MHz probe on the hand
      const abdo = L.probeMismatch(12, 15, 0.6);       // owner's example: 12 MHz probe on the abdomen
      console.log(JSON.stringify({hand, abdo}));
    """
    import json
    o = json.loads(_node(code))
    assert o["hand"]["kind"] == "shallow_lowfreq"
    assert o["abdo"]["kind"] == "deep_highfreq" and o["abdo"]["loss"] > 90


@needs_node
def test_probe_mismatch_silent_on_every_probe_presets_own_default():
    """The three probe presets' own (freq_default, depth_default_cm) pairs in ultrasound_tissues.json must
    never trigger the warning -- a realistic, on-label probe choice should never be flagged."""
    import json
    US = json.loads((REPO / "clinical" / "data" / "ultrasound_tissues.json").read_text(encoding="utf-8"))
    alpha = US["global"]["tgc_alpha_ref_db_cm_mhz"]
    pairs = [(p["freq_default"], p["depth_default_cm"]) for p in US["probes"].values()]
    code = r"""
      require('./clinical/ultrasound_tool.js'); const L = globalThis.NMSKUltrasoundLib;
      const pairs = %s, alpha = %s;
      console.log(JSON.stringify(pairs.map(p => L.probeMismatch(p[0], p[1], alpha))));
    """ % (json.dumps(pairs), alpha)
    out = json.loads(_node(code))
    assert out == [None] * len(pairs), out


@needs_node
def test_probe_mismatch_uses_the_tools_own_tgc_reference_attenuation_not_an_invented_number():
    import json
    US = json.loads((REPO / "clinical" / "data" / "ultrasound_tissues.json").read_text(encoding="utf-8"))
    alpha = US["global"]["tgc_alpha_ref_db_cm_mhz"]
    assert alpha == 0.6  # the exact number cited in probeMismatch's comment and used by the tool's existing TGC
    code = r"""
      require('./clinical/ultrasound_tool.js'); const L = globalThis.NMSKUltrasoundLib;
      console.log(JSON.stringify(L.probeMismatch(10, 8, %s)));
    """ % alpha
    o = json.loads(_node(code))
    loss = 2 * alpha * 10 * 8
    assert o is not None and abs(o["loss"] - loss) < 1e-9


def test_probe_mismatch_warning_wired_into_the_on_image_annotation():
    src = TOOL.read_text(encoding="utf-8")
    assert "LIB.probeMismatch(S.freq, S.depthCm" in src
    assert "PROBE/DEPTH MISMATCH" in src


# ---------------------------------------------------------------- (3)/(4) star-mode cine + tilt schematic
def test_cine_is_no_longer_gated_to_sweep_mode_only():
    src = TOOL.read_text(encoding="utf-8")
    assert 'S.cine = !!on && S.mode === "sweep"' not in src, "old gate (star mode could never cine) must be gone"
    assert "S.cine = !!on;" in src
    # the tick must use the mode-correct frame count (star always has 9; S.n only applies to sweep)
    assert 'var nF = S.mode === "star" ? 9 : S.n;' in src


def test_star_mode_can_use_the_single_cineable_view_not_only_the_fixed_grid():
    src = TOOL.read_text(encoding="utf-8")
    assert 'S.mode === "star" && S.view !== "single"' in src


def test_cine_view_fps_frame_controls_are_shared_by_both_modes_not_hidden_in_star_mode():
    src = TOOL.read_text(encoding="utf-8")
    # previously this whole block lived only inside ui.sweepBox (display:none in star mode)
    assert "ui.playBox" in src
    assert 'sec("mode", [ui.starBox, ui.sweepBox, ui.playBox])' in src


def test_tilt_schematic_panel_exists_and_tracks_the_current_star_frame():
    src = TOOL.read_text(encoding="utf-8")
    assert "us-schem" in src and "function drawSchematic" in src
    assert "drawSchematic();" in src  # called from relayoutViews, which every selection/cine-tick path already calls
    assert "spec.id === i + 1" in src  # highlights the dot matching the frame actually on screen


@needs_node
def test_node_sandbox_still_loads_cleanly_after_the_q253_edits():
    # smoke test: the file must still parse and expose the same LIB surface node tests rely on (Q228 etc.)
    code = r"""
      require('./clinical/ultrasound_tool.js'); const L = globalThis.NMSKUltrasoundLib;
      console.log(JSON.stringify({ok: typeof L.simulate === 'function' && typeof L.probeMismatch === 'function'}));
    """
    import json
    assert json.loads(_node(code))["ok"] is True
