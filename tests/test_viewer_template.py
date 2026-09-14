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
