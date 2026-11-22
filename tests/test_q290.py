"""Q290: two-finger zoom on every surface (3-D canvases of both engines, US image incl. the full-screen split, CT / MRI slice
panes, the reference image), zoom-to-point, native page zoom allowed.

Static + node checks only (the browser behaviour, with real CDP multi-touch, is scripts/anatomy/q290/verify_q290.py)."""
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
OWN = (REPO / "viewer" / "atlas_viewer.template.html").read_text(encoding="utf-8")
ZAN = (REPO / "viewer" / "zan_atlas.template.html").read_text(encoding="utf-8")
PINCH = (REPO / "viewer" / "pinch" / "pinch.js").read_text(encoding="utf-8")
US = (REPO / "clinical" / "ultrasound_tool.js").read_text(encoding="utf-8")
IMG = (REPO / "clinical" / "imaging_tool.js").read_text(encoding="utf-8")
NODE = shutil.which("node")


def node(code):
    r = subprocess.run([NODE, "-e", code], cwd=REPO, capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stderr[-2000:]
    return json.loads(r.stdout.strip().splitlines()[-1])


def test_pinch_helper_is_synced_into_both_templates_before_the_clinical_addons():
    r = subprocess.run(["python3", "scripts/sync_pinch_q290.py", "--check"], cwd=REPO, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    for t in (OWN, ZAN):
        assert t.count("<!-- PINCH html begin -->") == 1 and PINCH.strip() in t
        assert t.index("<!-- PINCH html end -->") < t.index('<script src="clinical_needle_tool.js">')


def test_viewport_allows_native_zoom_and_canvases_keep_their_own_gestures():
    for t in (OWN, ZAN):
        for m in re.findall(r'<meta name="viewport" content="([^"]+)"', t):
            assert "user-scalable=no" not in m and "maximum-scale" not in m, m
    assert "#stage canvas{touch-action:none}" in OWN
    assert re.search(r"#view\{[^}]*touch-action:none", ZAN)
    assert re.search(r"\.us-view\{[^}]*touch-action:none", US)
    assert re.search(r"\.img-view\{[^}]*touch-action:none", IMG)
    assert re.search(r"\.ref-stage\{[^}]*touch-action:none", IMG)


@pytest.mark.parametrize("name,t,old_wheel", [("own", OWN, "dist * (1 + Math.sign(e.deltaY) * 0.11)"), ("zan", ZAN, "cam.dist*(1+e.deltaY*0.0012)")])
def test_engines_zoom_to_point_and_keep_the_old_mouse_wheel(name, t, old_wheel):
    assert "function pzZoomAt" in t and "function pzPan" in t and "function pzReset" in t
    assert old_wheel in t                                         # a plain mouse wheel is unchanged
    wheel = t[t.index("pzZoomAt(e.clientX, e.clientY") - 200:t.index("pzZoomAt(e.clientX, e.clientY")]
    assert "e.ctrlKey" in wheel                                   # only ctrl+wheel (a trackpad pinch) zooms to the cursor
    assert re.search(r"pzTap\(e\)\) pzReset\(\)", t)               # double-tap on empty space = 1:1
    assert "NMSKPinch.chip(" in t


def test_clinical_surfaces_use_the_shared_helper():
    assert "function pinchView(v)" in US and "pinchView(v);" in US
    assert "v.box = ib;" in US and "function X(x) { return ib.x" in US     # the image is zoomed, the text keeps its size
    assert "w.pz && w.pz.busy()" in US                            # lifting two fingers is not a tap (no CINE pause)
    for f in ("function pinchStart(v)", "function keepUnder(v, W, cx, cy)", "function zoomAt(v, cx, cy, f)", "drag.pend"):
        assert f in IMG, f
    assert "NMSKPinch.track(ui.stage" in IMG


@pytest.mark.skipif(NODE is None, reason="node not installed")
def test_view_transform_keeps_the_point_under_the_fingers():
    code = "global.window = {};\n" + PINCH + r"""
const P = window.NMSKPinch, z = P.view(1, 8), out = {};
// content point under (120, 80) before; zoom x2.5 about it, then pan: the point follows the fingers exactly
const bx = (120 - z.tx) / z.k, by = (80 - z.ty) / z.k;
z.pan(15, -10).about(135, 70, 2.5);
const s = z.map(bx, by); out.err = Math.hypot(s[0] - 135, s[1] - 70); out.k = z.k;
z.about(0, 0, 100); out.kmax = z.k;                              // clamped to 8
z.reset(); z.about(50, 50, 0.5); out.kmin = z.k;                  // never below 1:1
z.reset(); z.about(10, 10, 3); z.pan(500, 500).clamp(200, 100); out.clamp = [z.tx, z.ty];
const d = P.dbl(); out.mouse = d({pointerType: "mouse", clientX: 0, clientY: 0}) || d({pointerType: "mouse", clientX: 0, clientY: 0});
const d2 = P.dbl(); out.touch = [d2({pointerType: "touch", clientX: 5, clientY: 5}), d2({pointerType: "touch", clientX: 9, clientY: 7})];
out.pair = P.pair([{x: 0, y: 0}, {x: 30, y: 40}]);
console.log(JSON.stringify(out));"""
    r = node(code)
    assert r["err"] < 1e-9 and abs(r["k"] - 2.5) < 1e-12
    assert r["kmax"] == 8 and r["kmin"] == 1
    assert r["clamp"] == [0, 0]
    assert r["mouse"] is False and r["touch"] == [False, True]
    assert r["pair"] == {"x": 15, "y": 20, "d": 50}


def test_verify_script_uses_real_cdp_multitouch():
    v = (REPO / "scripts" / "anatomy" / "q290" / "verify_q290.py").read_text(encoding="utf-8")
    assert "Input.dispatchTouchEvent" in v and '"touchStart"' in v and '"touchMove"' in v
