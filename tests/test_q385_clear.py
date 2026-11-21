"""Q385: the bar's "Clear N" button is the selection module's own, and both templates carry it."""
from pathlib import Path
R = Path(__file__).resolve().parents[1]
JS = (R / "viewer/selection/selection.js").read_text(encoding="utf-8")
CSS = (R / "viewer/selection/selection.css").read_text(encoding="utf-8")

def test_button_is_built_once_and_calls_clear():
    assert JS.count('barBtn.id = "sel-clear-bar"') == 1
    assert 'barBtn.addEventListener("click", function(){ clearMarks(); })' in JS
    assert "barBtn.hidden = !n" in JS and "barClear(n);" in JS

def test_hidden_wins_over_the_bar_button_display():
    assert "#sel-clear-bar[hidden]{display:none}" in CSS

def test_templates_carry_it():
    for t in ("viewer/zan_atlas.template.html", "viewer/atlas_viewer.template.html"):
        s = (R / t).read_text(encoding="utf-8")
        assert 'barBtn.id = "sel-clear-bar"' in s and "#sel-clear-bar[hidden]{display:none}" in s, t
