"""Q321: the quick card (viewer/quickcard/) -- source-level assertions. The browser run is
scripts/anatomy/q321/verify_quickcard_q321.py."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
D = REPO / "viewer" / "quickcard"
JS = (D / "quickcard.js").read_text(encoding="utf-8")
CSS = (D / "quickcard.css").read_text(encoding="utf-8")
ZAN = (REPO / "viewer" / "zan_atlas.template.html").read_text(encoding="utf-8")
OWN = (REPO / "viewer" / "atlas_viewer.template.html").read_text(encoding="utf-8")
BANNED = ["ultrasound", "hounsfield", "t1_se", "imaging_tissues", "tissue table", "nmskultrasound", "acoustic", "mrayl", "b-mode"]


def test_module_present_with_the_buttons():
    for label in ["Hide", "Fade", "Show only", "Select", "Zoom to", "More"]:
        assert '"' + label in JS, label
    assert "NMSKSelectCtl" in JS and "setMode" in JS and "markIds" in JS      # marking goes through the selection controller
    assert "max-content" in CSS and "max-width" in CSS


def test_no_banned_words_in_source_or_templates():
    for name, t in (("js", JS), ("css", CSS), ("zan", ZAN), ("own", OWN)):
        low = t.lower()
        for w in BANNED:
            assert w not in low, (name, w)


def test_templates_in_sync():
    r = subprocess.run([sys.executable, str(REPO / "scripts/sync_quickcard_q321.py"), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_engine_wiring_in_the_z_template_only_where_needed():
    assert "NMSKQuick.open(hz?hz.id:null,e.clientX,e.clientY)" in ZAN
    assert "NMSKQuick.sync(" in ZAN and "Q321 quick card glue begin" in ZAN
    assert "NMSKQuickCard.start" not in OWN        # the own-engine template carries the inert module only
    assert OWN.count("<!-- Q321 html begin -->") == 1


def test_tools_keep_priority_in_the_click_chain():
    i = ZAN.index("NMSKQuick.open(hz?hz.id:null")
    pre = ZAN[i - 400:i]
    for tool in ["measureCtl.consumeClick", "cutCtl.consumeClick", "selCtl.consumeClick", "addonClick(e)"]:
        assert tool in pre, tool
