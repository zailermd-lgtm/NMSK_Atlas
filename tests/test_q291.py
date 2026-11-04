"""Q291 -- ultrasound transmit frequency 1-18 MHz in whole-MHz steps, typical per-probe bands as a soft hint, the probe / depth
mismatch check at 13-18 MHz, and the B-mode kernel's behaviour at both ends of the range (no NaN, no aliasing of the speckle,
no frame-time blow-up). The real-browser pass is scripts/anatomy/q291/verify_q291.py."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
TOOL = REPO / "clinical" / "ultrasound_tool.js"
TABLE = REPO / "clinical" / "data" / "ultrasound_tissues.json"
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(not NODE, reason="node not installed")
US = json.loads(TABLE.read_text(encoding="utf-8"))


def _node(code: str, timeout=120):
    r = subprocess.run([NODE, "-e", code], capture_output=True, text=True, timeout=timeout, cwd=str(REPO))
    assert r.returncode == 0, r.stderr[-2500:]
    return json.loads(r.stdout)


def test_table_range_defaults_and_bands():
    r = US["freq_range_mhz"]
    assert (r["min"], r["max"], r["step"]) == (1, 18, 1)
    assert "freq_presets_mhz" not in US
    p = US["probes"]
    assert [p[k]["freq_default"] for k in ("linear", "convex", "sector")] == [10, 4, 3]
    assert [p[k]["freq_band_mhz"] for k in ("linear", "convex", "sector")] == [[4, 18], [1, 6], [1, 5]]
    for k in p:
        b = p[k]["freq_band_mhz"]
        assert b[0] <= p[k]["freq_default"] <= b[1]               # each default sits inside its own typical band
        assert re.search(r"(GE|Philips) [A-Za-z0-9-]+", p[k]["freq_band_src"])   # a named probe behind every band


@needs_node
def test_range_clamp_and_band_note():
    o = _node(r"""
      require('./clinical/ultrasound_tool.js'); const L = globalThis.NMSKUltrasoundLib, US = require('./clinical/data/ultrasound_tissues.json');
      const r = L.freqRange(US), n = (f, p) => L.freqBandNote(f, p, US);
      console.log(JSON.stringify({c: [0, 1, 7.5, 12.4, 18, 25, 'x'].map(r.clamp), lin: [3, 4, 18].map(f => n(f, 'linear').inBand),
        cx: [1, 6, 7].map(f => n(f, 'convex').inBand), sec: [5, 6].map(f => n(f, 'sector').inBand), txt: n(7, 'convex').text, he: n(7, 'convex').he}));
    """)
    assert o["c"] == [1, 1, 8, 12, 18, 18, 1]
    assert o["lin"] == [False, True, True] and o["cx"] == [True, True, False] and o["sec"] == [True, False]
    assert "outside" in o["txt"] and "1–6 MHz" in o["txt"] and "מחוץ" in o["he"]


@needs_node
def test_mismatch_at_13_to_18_mhz():
    o = _node(r"""
      require('./clinical/ultrasound_tool.js'); const L = globalThis.NMSKUltrasoundLib;
      console.log(JSON.stringify({d5: L.probeMismatch(18, 5, 0.6), d4: L.probeMismatch(18, 4, 0.6), d6: L.probeMismatch(13, 6, 0.6),
        hand: L.probeMismatch(3, 2, 0.6), abdo: L.probeMismatch(15, 15, 0.6), lin: L.probeMismatch(10, 5, 0.6)}));
    """)
    assert o["d5"]["kind"] == "deep_highfreq" and o["d5"]["fMax"] == 15 and "≤ 15 MHz" in o["d5"]["text"]
    assert o["d4"] is None and o["lin"] is None                    # 18 MHz to 4 cm = 86 dB round trip; the linear default is quiet
    assert o["d6"]["kind"] == "deep_highfreq" and o["d6"]["fMax"] == 12
    assert o["abdo"]["fMax"] < 6 and "1–5 MHz" in o["abdo"]["text"]
    assert "10–18 MHz" in o["hand"]["text"]


@needs_node
def test_kernel_is_finite_darker_and_not_slower_across_1_to_18_mhz():
    o = _node(r"""
      require('./clinical/imaging_tool.js'); require('./clinical/ultrasound_tool.js');
      const I = globalThis.NMSKImagingLib, U = globalThis.NMSKUltrasoundLib, T = require('./clinical/data/imaging_tissues.json'), US = require('./clinical/data/ultrasound_tissues.json');
      const C = I.compileTable(T), AC = U.compileAcoustics(US, C), K = k => C.by[k]._i;
      const g = U.fanGeom('linear', 44, 0, 0, 50), pl = U.planRaster(g, 320, {maxLines: 192}), lab = new Uint8Array(pl.W * pl.H);
      for (let y = 0; y < pl.H; y++) for (let x = 0; x < pl.W; x++) { const Y = pl.yr0 + (y + .5) * pl.px; lab[y * pl.W + x] = Y < 0 ? C.ids.air : Y < 3 ? K('fat') : K('muscle'); }
      const run = f => U.simulate({AC, geom: g, plan: pl, lab, sid: null, freq: f, depthMm: 50, gainDb: 0, tgcDb: 0, focusMm: 25, speckle: true, textures: false, reverb: true, noise: false, seed: 5,
        frame: {O: [0, 0, 0], u: [1, 0, 0], b: [0, -1, 0]}, axisOf: null});
      for (let i = 0; i < 3; i++) run(7.5);
      const out = {};
      for (const f of [1, 2, 7.5, 12, 18]) {
        let best = 1e9, r; for (let i = 0; i < 3; i++) { const t0 = Date.now(); r = run(f); best = Math.min(best, Date.now() - t0); }
        let bad = 0, far = [], near = [];
        for (let oy = 0; oy < r.Ho; oy++) for (let ox = 0; ox < r.Wo; ox++) { const v = r.db[oy * r.Wo + ox]; if (!isFinite(v)) { bad++; continue; }
          const X = pl.xo0 + (ox + .5) * pl.px, Y = pl.yo0 + (oy + .5) * pl.px; if (Math.abs(X) < 8) { if (Y > 8 && Y < 14) near.push(v); if (Y > 40 && Y < 45) far.push(v); } }
        const m = a => a.reduce((s, v) => s + v, 0) / a.length;
        out[f] = {ms: best, bad, near: m(near), far: m(far), ax: r.axFw, lat: r.latFw(25)};
      }
      console.log(JSON.stringify({out, ds: pl.ds}));
    """)
    r, ds = o["out"], o["ds"]
    assert all(v["bad"] == 0 for v in r.values())
    fs = ["1", "2", "7.5", "12", "18"]
    assert all(r[a]["far"] > r[b]["far"] for a, b in zip(fs[1:], fs[2:]))           # higher frequency -> darker far field (0.6 dB/cm/MHz)
    assert r["18"]["far"] < r["7.5"]["far"] - 30
    assert all(r[a]["lat"] > r[b]["lat"] and r[a]["ax"] > r[b]["ax"] for a, b in zip(fs, fs[1:]))   # finer resolution with frequency
    assert abs(r["18"]["ax"] - 2.5 * 1.54 / 18 / 2) < 1e-6 and r["18"]["ax"] < ds                  # 0.107 mm: below one sample step
    assert r["18"]["ms"] <= 2 * r["7.5"]["ms"] + 15 and r["1"]["ms"] <= 4 * r["7.5"]["ms"] + 30   # no frame-time blow-up at either end


def test_speckle_floor_and_kernel_caps_in_source():
    src = TOOL.read_text(encoding="utf-8")
    assert "cellAx = Math.max(GL.speckle.cell_ax_wavelengths * lam, 2 * ds)" in src
    assert "Math.min(pl.capA || 16, Math.ceil(sa * 2.5))" in src and "Math.min(pl.capL || 28, Math.ceil(sl * 2.5))" in src   # Q294: 16 / 28 at 1x; a zoom plan scales them to the same extent in mm
    assert "q291_floor" in US["global"]["speckle"]


def test_ui_stepper_everywhere_and_no_old_presets():
    src = TOOL.read_text(encoding="utf-8")
    assert "[3.5, 5, 7.5, 12]" not in src and "freqBtns" not in src and "freq_presets_mhz" not in src
    for where in ('where: "panel"', 'where: "card"', 'where: "fs"'):
        assert where in src
    assert re.search(r'freqStepper\(\{he: true, label: "תדר", range: true', src)               # the mode card keeps a slider between − and +
    pres = re.findall(r'\{key: "(\w+)", label: "[^"]+", clsKey: "\w+", depthCm: [\d.]+, dr: \d+, freq: ([\d.]+)', src)
    assert dict(pres) == {"tear": "12", "entrap": "12", "tendon": "12", "joint": "8"}
    assert "freq: 10, depthCm: 5" in src                                                          # initial state = the linear default
    assert "Frequency 1–18 MHz in whole-MHz steps" in src                                         # help text
    assert '"fq-b"' in src and "min-width:40px;min-height:36px" in src                            # tap-friendly targets


def test_readme_documents_the_range():
    t = (REPO / "docs" / "VIEWER_README.md").read_text(encoding="utf-8")
    assert "## Ultrasound frequency, 1 to 18 MHz (Q291)" in t and "Philips S5-1" in t and "GE C1-6-D" in t


def test_public_set_keeps_every_branch_after_the_freq_clamp():
    """the freq clamp in NMSKUltrasound.set() must not swallow the P / N branch behind a line comment"""
    src = TOOL.read_text(encoding="utf-8")
    line = next(l for l in src.splitlines() if 'k === "freq"' in l and "clamp(p.freq)" in l)
    code = line.split("//")[0]
    assert 'else if (k === "P" || k === "N") S[k] = p[k].slice();' in code
