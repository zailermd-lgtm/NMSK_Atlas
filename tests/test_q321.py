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


def test_q335_defaults_and_settings():
    """Q335: docked top-left, no line while the structure is coloured, the groups row under the name; all three settable."""
    assert 'pos:"tl", lead:"auto", chips:"card"' in JS
    for v in ('"tl", "point", "drag"', '"auto", "always", "never"', '"card", "bottom"'):
        assert v in JS, v
    assert "localStorage" in JS and "try {" in JS
    assert "STUB = 36" in JS            # the marker is never a line across the model


def test_q335_one_window_more_expands_in_place():
    assert "data-nm-hosted" in JS and "detEl.appendChild(inf)" in JS and '"Less"' in JS
    assert ".qc-det #info{position:static !important" in CSS


def test_q335_grip_and_menu_through_the_box_mover():
    assert 'Mv.add(QB)' in JS and 'Mv.menu("qcard"' in JS and 'into:"qc-tools"' in JS
    move = (REPO / "viewer" / "q305" / "move.js").read_text(encoding="utf-8")
    for k in ("function dots(b)", "function openMenu(b)", "function dock(b, at)", "function resetBox(b)", '"Dock top-left"', '"Reset position"'):
        assert k in move, k


def test_q335_engine_adaptor_has_marked_and_details():
    assert "marked:function(id)" in ZAN and "details:function()" in ZAN
    assert "marked:function(id)" not in OWN


def test_q335_chips_host_hook():
    bar = (REPO / "viewer" / "q298" / "bar.js").read_text(encoding="utf-8")
    assert "window.NMSKQ8Host" in bar and "window.NMSKQ8Host = function" in JS
    css = (REPO / "viewer" / "q298" / "q298.css").read_text(encoding="utf-8")
    assert "width:max-content" in css[css.index(".q8-float{"):]


def test_q335_related_structures_is_one_button_with_a_family_menu():
    assert '"Related structures \\u25be"' in JS and "function relOpen()" in JS and 'role", "menu"' in JS
    for k in ('key:"grp"', 'key:"adj"', 'key:"rel"'):
        assert k in JS, k
    assert "family:family" in JS and "f.items" in JS        # room for families with a sub-menu (myofascial lines, innervation)
    assert ".qc-chips #q8-exp{display:none !important}" in CSS


def test_q335_status_line_is_short_and_has_no_script_paths():
    q = (REPO / "viewer" / "q298" / "q298.js").read_text(encoding="utf-8")
    ex = (REPO / "viewer" / "q298" / "expand.js").read_text(encoding="utf-8")
    assert "function plain(t)" in q and "scripts\\/" in q and 'className = "q8-i"' in q
    assert "MEASURED, not an anatomical claim:" not in ex and "adjacent structures marked" in ex
    bar = (REPO / "viewer" / "q298" / "bar.js").read_text(encoding="utf-8")
    assert "if (id !== lastSel)" in bar                      # the line follows the selection


def test_q335_phone_layout_rules():
    q301 = (REPO / "viewer" / "q301" / "q301.css").read_text(encoding="utf-8")
    tail = q301[q301.index("Q335"):]
    assert "@media (max-width:560px)" in tail and "overflow-x:auto" in tail and "flex-wrap:nowrap" in tail
    sa = (REPO / "viewer" / "q300" / "showall.js").read_text(encoding="utf-8")
    assert '"Show all"' in sa and 'classList.toggle("sa-row", narrow)' in sa
    css = (REPO / "viewer" / "q300" / "q300.css").read_text(encoding="utf-8")
    assert "body:has(#sa-bar:not([hidden])) #brand" in css


def test_q335_tendon_sheath_class_from_the_name():
    assert '"tendon sheath" : o.layer' in ZAN
