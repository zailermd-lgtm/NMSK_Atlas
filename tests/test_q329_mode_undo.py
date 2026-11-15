"""Q329: a workspace mode's own display state never enters the page-wide undo history for good.

- The selection controller keeps a mode's colours (mcol, setModeColours) apart from the user's (ucol): snapshot() / restore()
  never carry them, so the history cannot record them.
- The innervation mode colours through setModeColours and clears them on exit (it no longer writes ucol through restore()).
- The history has a mode session (beginScope / endScope) that NMSKModes opens on enter and closes after the screen is restored.
- The sources are synced into both templates; the session logic behaves as specified (run in node when available)."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
SEL = REPO / "viewer/selection/selection.js"
INN = REPO / "viewer/innervation/innervation.js"
HIST = REPO / "viewer/q294/history.js"
MODES = REPO / "viewer/modes/modes.js"
TEMPLATES = [REPO / "viewer/zan_atlas.template.html", REPO / "viewer/atlas_viewer.template.html"]


def _fn(src: str, name: str) -> str:
    i = src.index("function " + name + "(")
    return src[i:src.index("\n  }\n", i)]


def test_selection_snapshot_never_carries_mode_colours():
    s = SEL.read_text(encoding="utf-8")
    assert "var mcol = null;" in s and "setModeColours:setModeColours" in s
    snap = s[s.index("function snapshot(){"):s.index("\n", s.index("function snapshot(){"))]
    assert "mcol" not in snap
    assert "mcol" not in _fn(s, "restore") and "mcol" not in _fn(s, "pack")
    assert "function userHex(id){ var c = colOf(id);" in s and "!colOf(id); }" in s


def test_innervation_uses_mode_colours():
    s = INN.read_text(encoding="utf-8")
    ap = s[s.index("function applyColours()"):s.index("\n", s.index("function applyColours()"))]
    assert "setModeColours(colourMap())" in ap and "restore" not in ap and "ucol" not in s
    assert "C.setModeColours(null)" in _fn(s, "exit")


def test_modes_open_and_close_the_history_session():
    s = MODES.read_text(encoding="utf-8")
    en, ex = _fn(s, "enter"), _fn(s, "exit")
    assert en.index('hist("beginScope")') < en.index("snap = takeSnapshot()") < en.index("p.enter(ctx)")
    assert ex.index("restoreSnapshot(snap)") < ex.index('hist("endScope")')
    h = HIST.read_text(encoding="utf-8")
    assert "beginScope:beginScope, endScope:endScope" in h


def test_synced_into_both_templates():
    for t in TEMPLATES:
        s = t.read_text(encoding="utf-8")
        for frag in ("setModeColours:setModeColours", "c.setModeColours(colourMap())", 'hist("endScope")', "beginScope:beginScope, endScope:endScope"):
            assert frag in s, (t.name, frag)


NODE = r"""
const fs = require("fs");
const stub = () => ({style:{}, setAttribute(){}, appendChild(){}, addEventListener(){}, insertBefore(){}});
global.window = global; global.document = {getElementById(){ return null; }, addEventListener(){}, createElement:stub, body:stub()};
global.setInterval = () => 0;
eval(fs.readFileSync(process.argv[2], "utf8").replace("var NMSKHistory =", "global.NMSKHistory ="));
const H = NMSKHistory;
let eng = {on:["bone","muscle","skin"], hid:[]}, sel = {marks:[], ucol:{a:"#111111"}};
H.register("engine", {get:() => JSON.parse(JSON.stringify(eng)), set:v => { eng = JSON.parse(JSON.stringify(v)); }});
H.register("selection", {get:() => JSON.parse(JSON.stringify(sel)), set:v => { sel = JSON.parse(JSON.stringify(v)); }});
H.start({floating:false});
const pre = JSON.stringify({eng, sel});
H.beginScope();
eng.on = ["bone","muscle"]; sel.marks = ["m1","m2"]; H.commit();          // the mode's look
eng.hid = [7]; H.commit();                                                  // the user's Hide inside the mode
H.undo(); const inUndo = eng.hid.length; H.redo(); const inRedo = eng.hid.length;
eng.on = ["bone","muscle","skin"]; sel.marks = []; H.endScope();            // exit puts the screen back
const out = {inUndo, inRedo, afterExit:JSON.stringify(eng)};
H.undo(); out.u1 = {eng:JSON.parse(JSON.stringify(eng)), sel:JSON.parse(JSON.stringify(sel))};
out.u2 = H.undo(); out.redo = H.redo(); out.end = {eng, sel}; out.len = H.state().len; out.pre = pre;
console.log(JSON.stringify(out));
"""


@pytest.mark.skipif(not shutil.which("node"), reason="node not installed")
def test_history_session_rebases_mode_owned_fields(tmp_path):
    js = tmp_path / "t.js"; js.write_text(NODE, encoding="utf-8")
    r = subprocess.run(["node", str(js), str(HIST)], capture_output=True, text=True, timeout=60)
    assert r.returncode == 0, r.stderr
    o = json.loads(r.stdout.strip().splitlines()[-1])
    assert o["inUndo"] == 0 and o["inRedo"] == 1                 # Undo / Redo of the user's own step inside the mode
    assert o["u1"]["eng"] == {"on": ["bone", "muscle", "skin"], "hid": []}   # the Hide undone, the mode's layers NOT back
    assert o["u1"]["sel"] == {"marks": [], "ucol": {"a": "#111111"}}          # nor the mode's marks; the user colour stays
    assert o["u2"] is False                                       # the mode's own entry collapsed into the one before it
    assert o["redo"] is True and o["end"]["eng"]["hid"] == [7] and o["end"]["eng"]["on"] == ["bone", "muscle", "skin"]
    assert o["len"] == 2
