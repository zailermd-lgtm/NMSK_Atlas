"""Q241: the Pose fragment in both templates (single source, markers, engine hooks, rig placeholder), its wording, storage guards and syntax."""
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
OWN = (REPO / "viewer/atlas_viewer.template.html").read_text()
ZAN = (REPO / "viewer/zan_atlas.template.html").read_text()
FR = REPO / "viewer/pose"


def between(text, b, e):
    i = text.index(b) + len(b)
    return text[i:text.index(e, i)].strip("\n")


def test_templates_carry_the_fragment_verbatim_and_sync_is_a_no_op():
    r = subprocess.run([sys.executable, "scripts/sync_pose_q241.py", "--check"], cwd=REPO, capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    for kind, f, (b, e) in (("css", "pose.css", ("/* POSE css begin */", "/* POSE css end */")), ("html", "pose.html", ("<!-- POSE html begin -->", "<!-- POSE html end -->")),
                            ("js", "pose.js", ("/* POSE js begin */", "/* POSE js end */"))):
        frag = (FR / f).read_text().rstrip("\n")
        for t in (OWN, ZAN):
            assert t.count(b) == 1 and t.count(e) == 1 and between(t, b, e) == frag, kind
    for t, g in ((OWN, "glue_own.js"), (ZAN, "glue_zan.js")):
        assert between(t, "/* POSE glue begin */", "/* POSE glue end */") == (FR / g).read_text().rstrip("\n")
    for t in (OWN, ZAN):
        assert t.count("<!-- NMSK-POSE-RIG begin -->") == 1 and 'id="nmsk-pose-rig"' in t


def test_zan_engine_hooks():
    assert "o.vOff = base;" in ZAN and "window.__poseLive && window.__poseLive(i)" in ZAN
    g = (FR / "glue_zan.js").read_text()
    assert "gl.bufferSubData" in g and "capGeomCache = {}" in g and "o.bmin = lo" in g and "labelsCtl.dirty()" in g
    o = (FR / "glue_own.js").read_text()
    assert "computeBoundingBox" in o and "needsUpdate = true" in o and "labelsCtl.dirty()" in o


def test_wording_and_safety():
    js = (FR / "pose.js").read_text(); html = (FR / "pose.html").read_text()
    assert "kinematic approximation, soft tissue not simulated (no collision / volume preservation)" in html
    for w in ("Reset to model pose", "Anatomical position", "Symmetric pose R", "Link left and right", "Save pose", "Load pose", "population averages", "R\u2192L", "L\u2192R"):
        assert w in js, w
    # localStorage only inside try / catch
    for m in re.finditer(r"localStorage\.(getItem|setItem)", js):
        before = js[max(0, m.start() - 160):m.start()]
        assert "try {" in before, before
    assert "http://" not in js and "https://" not in js and "fetch(" not in js        # no network: the rig is embedded
    assert "DecompressionStream" in js


def test_pose_js_parses_and_exports_the_core():
    node = shutil.which("node")
    if node is None:
        pytest.skip("node not installed")
    p = subprocess.run([node, "-e", "const s=require('fs').readFileSync(process.argv[1],'utf8');const r=new Function(s+';return {c:NMSKPoseCore,p:NMSKPose};')();console.log(Object.keys(r.c).sort().join(','), typeof r.p)",
                        str(FR / "pose.js")], capture_output=True, text=True)
    assert p.returncode == 0, p.stderr
    assert "fk" in p.stdout and "decodeSkin" in p.stdout and "function" in p.stdout
