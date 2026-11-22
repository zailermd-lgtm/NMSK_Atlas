"""Q272 -- clinical WORKSPACE MODES (viewer/modes/): the shared fragment is carried verbatim in both templates, the body-class CSS hides
the anatomy chrome (CSS only, nothing destroyed), the mode-bar / switcher copy is the owner's approved Hebrew, and the public templates
still never name a private clinical tool (the providers live in clinical/*.js and register through the generic NMSKModes hook)."""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
FR = REPO / "viewer" / "modes"
OWN = (REPO / "viewer" / "atlas_viewer.template.html").read_text(encoding="utf-8")
ZAN = (REPO / "viewer" / "zan_atlas.template.html").read_text(encoding="utf-8")


def between(text, b, e):
    i = text.index(b) + len(b); j = text.index(e)
    return text[i:j].strip("\n")


def test_sync_script_is_a_no_op():
    r = subprocess.run([sys.executable, str(REPO / "scripts" / "sync_modes_q272.py"), "--check"], capture_output=True, text=True, cwd=str(REPO))
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.parametrize("kind,fname,marks", [
    ("css", "modes.css", ("/* MODES css begin */", "/* MODES css end */")),
    ("html", "modes.html", ("<!-- MODES html begin -->", "<!-- MODES html end -->")),
    ("js", "modes.js", ("/* MODES js begin */", "/* MODES js end */")),
])
def test_fragment_verbatim_in_both_templates(kind, fname, marks):
    body = (FR / fname).read_text(encoding="utf-8").rstrip("\n")
    for t in (OWN, ZAN):
        assert t.count(marks[0]) == 1 and t.count(marks[1]) == 1
        assert between(t, *marks) == body


def test_glue_verbatim_per_engine():
    assert between(OWN, "/* MODES glue begin */", "/* MODES glue end */") == (FR / "glue_own.js").read_text(encoding="utf-8").rstrip("\n")
    assert between(ZAN, "/* MODES glue begin */", "/* MODES glue end */") == (FR / "glue_zan.js").read_text(encoding="utf-8").rstrip("\n")


def test_body_class_css_hides_the_chrome_not_js():
    css = (FR / "modes.css").read_text(encoding="utf-8")
    rule = re.search(r"body\.mode-on #app>header[^{]*\{display:none!important\}", css, re.S)
    assert rule, "the chrome-hiding rule is missing"
    sel = rule.group(0)
    for chrome in ("#app>aside", "#inspector", ".mob-bar", "#tools", "#brand", "#topright", "#rail", "#info", "#foot", "#cut-panel", "#lab-panel", "#pm-panel"):
        assert "body.mode-on " + chrome in sel, chrome
    assert "body.mode-us #mode-back" in css and "body.mode-cmp #mode-back" in css
    js = (FR / "modes.js").read_text(encoding="utf-8")
    assert 'classList.add("mode-on", "mode-" + key)' in js and 'classList.remove("mode-on", "mode-" + cur' in js
    assert 'shell.hidden = true' in js and "mode-shell" in js      # the shell is hidden on exit, never destroyed; chrome is only ever class-toggled


def test_mode_bar_and_switcher_copy():
    html = (FR / "modes.html").read_text(encoding="utf-8")
    for copy in ("מה עושים היום?", "אנטומיה", "תכנון הזרקה", "US אבחנתי", "השוואת דימות", "יציאה למצב אנטומיה", "Imaging · זכר", "Combined · נקבה",
                 "כל מצב פותח מסך משלו. תמיד אפשר לחזור לכאן מהכפתור בפינה."):
        assert copy in html, copy
    assert 'dir="rtl"' in html
    assert "emoji" not in html.lower()
    js = (FR / "modes.js").read_text(encoding="utf-8")
    assert 'text:"מצב"' in js                         # the toolbar button
    assert "#0E7C86" in (FR / "modes.css").read_text() and "#2B6CB0" in (FR / "modes.css").read_text() and "#B5651D" in (FR / "modes.css").read_text()


def test_public_templates_stay_generic():
    for t in (OWN, ZAN):
        low = between(t, "/* MODES js begin */", "/* MODES js end */").lower() + between(t, "<!-- MODES html begin -->", "<!-- MODES html end -->").lower()
        for bad in ("ultrasound", "nmskultrasound", "needle", "nmskclinical", "nmskimaging", "nmskreference"):
            assert bad not in low, bad


def test_providers_live_in_the_private_files_and_use_public_apis():
    nd = (REPO / "clinical" / "needle_tool.js").read_text(encoding="utf-8")
    us = (REPO / "clinical" / "ultrasound_tool.js").read_text(encoding="utf-8")
    im = (REPO / "clinical" / "imaging_tool.js").read_text(encoding="utf-8")
    assert 'NMSKModes.register("inj"' in nd and 'NMSKModes.register("us"' in us and 'NMSKModes.register("cmp"' in im
    for copy in ("הצע נקודות כניסה", "סמן ידנית על העור", "מדידה בלבד · ספי צבע", "תנוחה ספסטית", "אחיזות (O/I)"):
        assert copy in nd, copy
    for copy in ("סימולציה מהמשים – לא אולטרסאונד", "הקש על העור כדי להזיז את המתמר", "השווה לצד הנגדי (A/B)", "הגדרות מתקדמות"):
        assert copy in us, copy
    for copy in ("דימות המטופל", "האטלס — חתך תואם", "נטען מקומית · לא נשלח", "סימון פגיעה", "לא אבחנה"):
        assert copy in im, copy
    # the compare mode marks through the selection controller's public API only (Q232 rule), never its internals
    cmp_src = im[im.index("function compareMode"):im.index("5. ATTACH")]
    assert "sel.mark(r.id, true)" in cmp_src and "sel.isMarked" in cmp_src
    assert "marks[" not in cmp_src and "set[" not in cmp_src
