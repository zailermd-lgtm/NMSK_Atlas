"""Q283: the Learn panel's data and wiring (the browser behaviour is scripts/anatomy/q283/verify_q283.py)."""
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TEMPLATES = [REPO / "viewer/atlas_viewer.template.html", REPO / "viewer/zan_atlas.template.html"]


def run(*args):
    return subprocess.run([sys.executable, *args], capture_output=True, text=True, cwd=REPO)


def test_learn_data_is_built_from_the_current_sources_and_every_quote_is_verbatim():
    r = run("scripts/anatomy/q283/build_learn.py", "--check")
    assert r.returncode == 0, r.stdout + r.stderr


def test_templates_carry_the_learn_block_verbatim():
    r = run("scripts/sync_learn_q283.py", "--check")
    assert r.returncode == 0, r.stdout


def test_iliacus_adduction_is_recorded_as_not_animated_and_never_mapped():
    a = json.loads((REPO / "data/anatomy/muscle_actions_q283.json").read_text(encoding="utf-8"))
    for row in a["rows"]:
        if row["m"] == "iliopsoas" and row.get("c") in (None, "iliacus"):
            assert all(mv[1] != "abd" for mv in row["mv"]), row
    assert any(x["m"] == "iliopsoas" and x["c"] == "iliacus" and "adduction" in x["what"] for x in a["not_animated"])


def test_every_mapped_row_names_a_quote_and_a_known_source():
    a = json.loads((REPO / "data/anatomy/muscle_actions_q283.json").read_text(encoding="utf-8"))
    for row in a["rows"]:
        assert row["q"].strip() and (row["src"] == "actions" or row["src"][5:] in a["cites"]), row


def test_both_templates_expose_the_two_api_additions_and_start_the_controller():
    for t in TEMPLATES:
        s = t.read_text(encoding="utf-8")
        assert "selectedId:function()" in s and "orbit:function(d)" in s, t.name
        assert "NMSKLearn(anatomyApi())" in s and "window.learnCtl = learnCtl" in s, t.name
        assert 'id="nmsk-learn"' in s and 'id="ln-panel"' in s, t.name
