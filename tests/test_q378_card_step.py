"""Q378: a card action is its own undo step.

The page history (viewer/q294/history.js) commits a click about 320 ms later; the quick card's Hide / Fade / Show only /
Select committed at once. Pressed before the click's commit, the action was folded into the click's entry, and one Undo took
the selection back with it -- the engine then selected nothing and closed the card (every structure, both Base pages).
`NMSKQuickCard.step(H, f)` seals what is pending, acts, commits. Node level; the browser check is
scripts/anatomy/q321/verify_quickcard_q321.py (Hide -> Undo by id)."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
NODE = shutil.which("node")
needs_node = pytest.mark.skipif(not NODE, reason="node not installed")
JS = (REPO / "viewer/quickcard/quickcard.js").read_text(encoding="utf-8")

PRE = """global.window = {addEventListener(){}};
  global.document = {addEventListener(){}, getElementById(){ return null; }, createElement(){ return {style:{}, setAttribute(){}, addEventListener(){}, appendChild(){}}; }, body:{appendChild(){}}};
  const fs = require('fs');
  eval(fs.readFileSync('viewer/q294/history.js','utf8') + ';global.H=NMSKHistory;');
  eval(fs.readFileSync('viewer/quickcard/quickcard.js','utf8') + ';global.Q=NMSKQuickCard;');
  let sel = null, hid = [];
  H.register('engine', {get:() => ({sel, hid:hid.slice()}), set:v => { sel = v.sel; hid = v.hid.slice(); }});
  H.start({floating:false, max:20});
  const click = id => { sel = id; H.schedule(); };          // the engine's select(); the commit is debounced
  const out = {};"""


def node(src: str) -> dict:
    r = subprocess.run([NODE, "-e", PRE + src + ";console.log(JSON.stringify(out)); process.exit(0);"], capture_output=True, text=True, timeout=120, cwd=str(REPO))
    assert r.returncode == 0, r.stderr[-2000:]
    return json.loads(r.stdout.strip().splitlines()[-1])


@needs_node
def test_the_old_sequence_folds_the_click_into_the_action():
    """The mechanism, on the real history module: act + commit while the click is still pending = ONE entry."""
    o = node("""click(7); const i0 = H.state().idx, pending = H.state().pending;
      hid.push(7); H.commit(); out.steps = H.state().idx - i0; out.pending = pending;
      H.undo(); out.sel = sel; out.hid = hid;""")
    assert o["pending"] is True and o["steps"] == 1
    assert o["sel"] is None and o["hid"] == []          # the selection went with the Hide: this closed the card


@needs_node
def test_step_makes_the_action_its_own_undo_step():
    o = node("""click(7); const i0 = H.state().idx;
      out.ret = Q.step(H, () => { hid.push(7); return 'r'; }); out.steps = H.state().idx - i0; out.pending = H.state().pending;
      H.undo(); out.sel = sel; out.hid = hid.slice();
      H.undo(); out.sel2 = sel; H.redo(); H.redo(); out.redo = [sel, hid.slice()];""")
    assert o["ret"] == "r" and o["steps"] == 2 and o["pending"] is False
    assert o["sel"] == 7 and o["hid"] == []             # Undo takes back the Hide alone: the structure stays selected
    assert o["sel2"] is None and o["redo"] == [7, [7]]  # the click is the step before it; Redo brings both back


@needs_node
def test_step_adds_nothing_when_nothing_is_pending_or_changes():
    o = node("""click(7); H.commit(); const i0 = H.state().idx;
      Q.step(H, () => { hid.push(7); }); out.one = H.state().idx - i0;
      Q.step(H, () => {}); out.none = H.state().idx - i0;""")
    assert o["one"] == 1 and o["none"] == 1


@needs_node
def test_step_acts_without_a_history_or_with_a_failing_one():
    o = node("""let n = 0; out.a = Q.step(null, () => ++n); out.b = Q.step({}, () => ++n);
      out.c = Q.step({active(){ return false; }, commit(){ throw new Error('must not commit'); }}, () => ++n);
      out.d = Q.step({active(){ return true; }, commit(){ throw new Error('x'); }}, () => ++n);""")
    assert [o["a"], o["b"], o["c"], o["d"]] == [1, 2, 3, 4]


def test_every_card_action_is_sealed_first():
    """Each place the card changes page state seals the pending step before it acts."""
    assert re.search(r'e\.addEventListener\("click", function\(ev\)\{ ev\.stopPropagation\(\); if \(cur\) step\(window\.NMSKHistory, function\(\)\{ f\(cur\); \}\); \}\);', JS)
    assert re.search(r'hist\(\); c\.setUserColour\(hex, "ids", ids\); hist\(\);', JS)
    assert re.search(r'hist\(\);[^\n]*\n\s*var n = c\.markIds\(ids, true, false, true\);\s*\n\s*hist\(\);', JS)
    assert "step:step" in JS


def test_both_templates_carry_it():
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "sync_quickcard_q321.py"), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    for t in ("viewer/zan_atlas.template.html", "viewer/atlas_viewer.template.html"):
        assert "function step(H, f){" in (REPO / t).read_text(encoding="utf-8")


def test_the_verifier_names_structures_and_never_subscripts_a_missing_card():
    v = (REPO / "scripts/anatomy/q321/verify_quickcard_q321.py").read_text(encoding="utf-8")
    assert "HIDE_UNDO_IDS" in v and "hide_undo_by_id(pg, T)" in v and "class CardGone" in v
    assert not re.search(r"card_info\(pg\)\[\"(labels|pressed)\"\]", v)
