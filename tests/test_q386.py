"""Q386: every box can be resized and has a text size; the module is synced into both templates and stays clear of the engine canvas."""
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
JS = (REPO / "viewer/resize/resize.js").read_text(encoding="utf-8")
CSS = (REPO / "viewer/resize/resize.css").read_text(encoding="utf-8")


def test_resize_module_is_synced_into_both_templates():
    for s in ("sync_resize_q386.py", "sync_layout_q382.py", "sync_q305.py"):
        r = subprocess.run(["python3", "scripts/" + s, "--check"], cwd=REPO, capture_output=True, text=True)
        assert r.returncode == 0, s + "\n" + r.stdout + r.stderr


def test_private_words_stay_out_of_the_new_module():
    low = (JS + CSS + (REPO / "viewer/layout/layout.js").read_text(encoding="utf-8")).lower()
    for w in ("ultrasound", "hounsfield", "t1_se", "imaging_tissues", "tissue table", "nmskultrasound", "acoustic", "mrayl", "b-mode"):
        assert w not in low


def test_text_steps_are_80_to_160_in_tens_and_floor_is_10px():
    m = re.search(r"STEPS = \[([^\]]+)\]", JS)
    assert [int(x) for x in m.group(1).split(",")] == list(range(80, 161, 10))
    assert re.search(r"FLOOR = 10\b", JS)


def test_text_is_scaled_on_the_boxes_children_never_on_a_canvas():
    assert ".q386-f > :not(.nm-grip):not(.nm-dots){zoom:" in CSS
    assert not re.search(r"querySelector(All)?\(['\"][^'\")]*canvas", JS, re.I) and "getElementById(\"view\")" not in JS


def test_box_registry_has_the_hooks_the_module_uses():
    mv = (REPO / "viewer/q305/move.js").read_text(encoding="utf-8")
    for name in ("extraItems:", "shift:", "keep:"):
        assert name in mv
    for call in ("m.extraItems", "m.shift", "m.keep"):
        assert call in JS


def test_settings_has_the_text_size_rows_and_reset_calls_the_module():
    lay = (REPO / "viewer/layout/layout.js").read_text(encoding="utf-8")
    assert 'id="q386-g"' in lay and "NMSKResize.setGlobal" in lay and "NMSKResize.setBox" in lay and "NMSKResize.reset()" in lay
