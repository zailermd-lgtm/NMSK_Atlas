"""Q239 -- the imaging + ultrasound tools must not depend on four sibling files being served (published pages: the owner could not see them).

Fast tests: the build step that pastes the code + tissue tables into a built page (round trip, idempotence, escaping, only imaging + ultrasound, the public templates stay
untouched), the staging CLI, the visible diagnostics / always-present buttons in the tool sources, the hosting-mimic server.
Browser matrix (opt-in re-run: Q239_BROWSER=1; recorded results data/derived/q239/matrix.json): scripts/clinical/q239_matrix.py."""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "clinical"))
import inline_clinical_q239 as ic  # noqa: E402
import q239_host as host  # noqa: E402
import stage_clinical_files as scf  # noqa: E402

TEMPLATES = {"own": REPO / "viewer" / "atlas_viewer.template.html", "zan": REPO / "viewer" / "zan_atlas.template.html"}
NODE = shutil.which("node")


@pytest.mark.parametrize("kind", ["own", "zan"])
def test_roundtrip_and_idempotent(kind):
    t = TEMPLATES[kind].read_text(encoding="utf-8")
    assert t.count('<script src="clinical_imaging_tool.js"></script>') == 1 and "nmsk-imaging-inline" not in t     # the public template carries only the generic hook
    n = ic.inline_into(t)
    assert ic.status(n) == {"imaging": True, "ultrasound": True}
    assert ic.uninline(n) == t                                   # the page before inlining, byte for byte
    assert ic.inline_into(n) == n                                # idempotent
    assert ic.inline_into(n, ultrasound=False).count('id="nmsk-ultrasound-inline"') == 0
    assert n.index('<script src="clinical_needle_tool.js"></script>') < n.index('id="nmsk-imaging-inline"')   # runs after the needle hook, so it chains onto it


def test_block_is_well_formed_and_limited_to_imaging_and_ultrasound():
    t = TEMPLATES["own"].read_text(encoding="utf-8")
    n = ic.inline_into(t)
    block = n[n.index("<!-- NMSK_INLINE_IMAGING begin"):n.index("<!-- NMSK_INLINE_IMAGING end -->")]
    assert block.count("<script") == block.count("</script>") == 4
    assert not re.search(r"needle|motor_points|clinical_risk", re.sub(r"<script[^>]*>.*?</script>", "", block, flags=re.S))      # nothing but the four script elements
    for name, rel in (("nmsk-imaging-tissues", "data/imaging_tissues.json"), ("nmsk-ultrasound-tissues", "data/ultrasound_tissues.json")):
        m = re.search(r'<script type="application/json" id="%s">(.*?)</script>' % name, block, re.S)
        assert json.loads(m.group(1)) == json.loads((REPO / "clinical" / rel).read_text(encoding="utf-8"))
    assert "NMSKClinicalDiag" in block


def test_escaping_of_script_end_tags():
    assert "</script" not in ic._js("var a = '</script><!-- x';").lower() and "<!--" not in ic._js("var a = '<!--';")
    j = ic._json('{"a": "</script><!--"}')
    assert "</script" not in j and "<!--" not in j and json.loads(j)["a"] == "</script><!--"


def test_stage_cli_inlines_and_uninlines(tmp_path):
    d = tmp_path / "viewer_x"; d.mkdir()
    t = TEMPLATES["zan"].read_text(encoding="utf-8")
    (d / "atlas_viewer_x.html").write_text(t, encoding="utf-8"); (d / "index.html").write_text(t, encoding="utf-8")
    assert scf.main(["--ultrasound", str(d)]) == 0
    for h in ("atlas_viewer_x.html", "index.html"):
        assert ic.status((d / h).read_text(encoding="utf-8")) == {"imaging": True, "ultrasound": True}
    assert all((d / n).is_file() for n in scf.IMAGING_NAMES + scf.ULTRASOUND_NAMES)            # the files beside the page stay as the fallback
    assert not (d / "clinical_needle_tool.js").exists()                                         # needle / risk / motor points are never staged here
    assert scf.main(["--uninline", str(d)]) == 0 and (d / "index.html").read_text(encoding="utf-8") == t
    assert scf.main(["--ultrasound", "--no-inline", str(d)]) == 0 and (d / "index.html").read_text(encoding="utf-8") == t
    assert scf.main(["--imaging-only", str(d)]) == 0
    assert ic.status((d / "index.html").read_text(encoding="utf-8")) == {"imaging": True, "ultrasound": False}
    assert scf.main(["--remove", str(d)]) == 0 and (d / "index.html").read_text(encoding="utf-8") == t


def test_regen_scripts_go_through_the_inlining_stage_step():
    # every regeneration path stages through `stage_clinical_files.py --ultrasound` (which now pastes the code in); none passes --no-inline
    for f in ("regen_q232.sh", "regen_ultrasound_q228.sh"):
        s = (REPO / "scripts" / f).read_text(encoding="utf-8")
        assert "stage_clinical_files.py --ultrasound" in s and "--no-inline" not in s, f


def test_tool_sources_have_diagnostics_and_always_present_buttons():
    im = (REPO / "clinical" / "imaging_tool.js").read_text(encoding="utf-8")
    us = (REPO / "clinical" / "ultrasound_tool.js").read_text(encoding="utf-8")
    for needle in ("Imaging tool: ready (v", "Imaging tool: NOT ready", '"CT / MRI"', "nmsk-imaging-tissues", "floatBar", "rescueButtons", "NMSKClinicalDiag", "fetchText", "XMLHttpRequest",
                   "No cut was set", "Ultrasound tool: NOT available", "defines no ultrasound tool", "nmsk-imaging-hint"):
        assert needle in im, needle
    for needle in ("Ultrasound tool: ready (v", "Ultrasound tool: NOT ready", "nmsk-ultrasound-tissues", "toolbarHost", "us-diag", "nmsk-ultrasound-hint"):
        assert needle in us, needle
    assert "G.NMSKClinical.imaging) return" in im                       # a second load (inline + file) is ignored


@pytest.mark.skipif(not NODE, reason="node not installed")
def test_tools_parse_and_double_load_is_ignored():
    code = r"""
    const fs=require('fs'); const sb={}; sb.window=sb; sb.globalThis=sb; sb.document={currentScript:null,getElementById(){return null},createElement(){return {style:{},setAttribute(){}}},head:{appendChild(){}},body:{classList:{contains(){return false}},appendChild(){}}};
    const vm=require('vm'); vm.createContext(sb);
    vm.runInContext(fs.readFileSync('clinical/imaging_tool.js','utf8'),sb); const first=sb.NMSKClinical; if(!first||!first.imaging) throw new Error('imaging not defined');
    vm.runInContext(fs.readFileSync('clinical/imaging_tool.js','utf8'),sb); if(sb.NMSKClinical!==first) throw new Error('second load replaced the first');
    vm.runInContext(fs.readFileSync('clinical/ultrasound_tool.js','utf8'),sb); if(typeof sb.NMSKUltrasoundAddon.attach!=='function') throw new Error('no ultrasound addon');
    console.log('ok');"""
    r = subprocess.run([NODE, "-e", code], capture_output=True, text=True, cwd=str(REPO), timeout=60)
    assert r.returncode == 0 and "ok" in r.stdout, r.stderr[-1500:]


def test_hosting_mimic_server(tmp_path):
    (tmp_path / "p.html").write_text("<html><body>x</body></html>"); (tmp_path / "clinical_a.js").write_text("1"); (tmp_path / "t.json").write_text("{}")
    srv, port = host.serve(tmp_path, mime="plain", nosniff=True, wrap=True, hide=("clinical_",), sandbox="allow-scripts", page="p.html")
    try:
        def get(path):
            try:
                r = urllib.request.urlopen(f"http://127.0.0.1:{port}/{path}")
                return r.status, r.headers
            except urllib.error.HTTPError as e:
                return e.code, e.headers
        s, h = get("t.json"); assert s == 200 and h["Content-Type"] == "text/plain" and h["X-Content-Type-Options"] == "nosniff" and h["Access-Control-Allow-Origin"] == "*"
        assert get("clinical_a.js")[0] == 404
        body = urllib.request.urlopen(f"http://127.0.0.1:{port}/p.html").read().decode()
        assert body.startswith("<!doctype html><html><head><meta charset=utf8>") and body.endswith("</body></html>")
        assert 'sandbox="allow-scripts"' in urllib.request.urlopen(f"http://127.0.0.1:{port}/__outer.html").read().decode()
    finally:
        srv.shutdown()


# ---------------------------------------------------------------- recorded browser matrix (re-run: scripts/clinical/q239_matrix.py)
MATRIX = REPO / "data" / "derived" / "q239" / "matrix.json"


@pytest.mark.skipif(not MATRIX.is_file(), reason="matrix not recorded here (python3 scripts/clinical/q239_matrix.py, needs Chromium + build/q239)")
def test_recorded_matrix_all_ok():
    res = json.loads(MATRIX.read_text())
    strict = [r for r in res if r["cond"] == "strict"]
    assert len(strict) == 12 and {r["vp"] for r in strict} == {"1366x768", "390x844"} and len({r["tag"] for r in strict}) == 6
    bad = [(r["tag"], r["cond"], r["vp"], r["failed"], r["errors"][:2]) for r in res if not r["ok"]]
    assert not bad, bad
    assert {r["cond"] for r in res} >= {"strict", "base", "plain", "nosniff", "nosib", "sbx"}


@pytest.mark.skipif(os.environ.get("Q239_BROWSER") != "1" or not (REPO / "build" / "q239" / "viewer_m_hr").is_dir(), reason="set Q239_BROWSER=1 with build/q239")
def test_browser_strict_own_male_desktop():
    sys.path.insert(0, str(REPO / "scripts" / "clinical"))
    import q239_check as ck
    r = ck.run(str(REPO / "build" / "q239" / "viewer_m_hr"), "atlas_viewer_male.html", "own", "strict", "1366x768", None, "t", True)
    assert r["ok"], (r["errors"], [k for k, v in r["checks"].items() if not v])
