"""The viewer template carries the controls the docs describe."""
from pathlib import Path

import pytest

TEMPLATE = Path(__file__).resolve().parent.parent / "viewer" / "atlas_viewer.template.html"


@pytest.fixture(scope="module")
def template() -> str:
    return TEMPLATE.read_text(encoding="utf-8")


def test_bundle_placeholders_present(template):
    assert "__BUNDLE_JSON__" in template and "__BUNDLE_B64__" in template
    assert "BUNDLE.quantum_mm" in template, "vertices must be scaled by the bundle's quantum"


def test_needle_path_controls(template):
    for needle in ('id="t-needle"', 'id="needle-panel"', 'id="needle-clear"',
                   'id="needle-status"', 'id="needle-report"'):
        assert needle in template


def test_needle_path_functions(template):
    for fn in ("needleToggle", "needleClear", "needleAddPoint", "needleSetPoints",
               "needleClick", "needleHits", "needleCrossings", "needleSkinDepth",
               "needleReport", "needleRender", "pickHit"):
        assert f"function {fn}(" in template, fn
    assert "window.NeedlePath" in template
    assert 'e.key === "Escape"' in template


def test_needle_path_documented():
    readme = (TEMPLATE.parent.parent / "docs" / "VIEWER_README.md").read_text(encoding="utf-8")
    assert "## Needle path" in readme
    assert "not a clinical recommendation" in readme


def test_template_renders_the_clinical_block_and_exporter_compacts_it():
    from pathlib import Path
    REPO = Path(__file__).resolve().parents[1]
    tpl = (REPO / "viewer" / "atlas_viewer.template.html").read_text()
    assert "BUNDLE.clinical" in tpl and "Trigger points and referred pain" in tpl
    from scripts.export_viewer_bundle import compact_clinical
    c = compact_clinical([{"document": "d", "compiled": "2026", "function_biomechanics": "f", "adjacent_structures": "dropped",
                           "trigger_points": [{"location": "L", "referred_pain": "R", "source": "S", "notes": "dropped"}],
                           "tests": [{"name": "T", "sensitivity": 91, "specificity": None, "source": "S", "performance": "dropped"}],
                           "caveat": "c", "sources": ["s1"]}])
    assert c[0]["trigger_points"] == [{"location": "L", "referred_pain": "R", "source": "S"}]
    assert c[0]["tests"] == [{"name": "T", "sensitivity": 91, "source": "S"}] and "adjacent_structures" not in c[0]
