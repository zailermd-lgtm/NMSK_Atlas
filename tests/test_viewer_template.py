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


def test_nerve_depth_profile_rows_and_course_table():
    """Q58: a nerve's depth below the skin along its course -- one row per 20 mm
    band of atlas y with the shallowest point and its nearest skin point -- and
    the inspector's course table with its show/needle actions."""
    import sys
    from pathlib import Path
    import numpy as np
    from scipy.spatial import cKDTree
    repo = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(repo / "scripts"))
    import export_viewer_bundle as ev
    # a skin cylinder of radius 50 around the y axis, a nerve line at x = 30 running y = 0..100
    ang = np.linspace(0, 2 * np.pi, 360, endpoint=False)
    ys = np.arange(-20, 130, 2.0)
    skin = np.array([[50 * np.cos(a), y, 50 * np.sin(a)] for y in ys for a in ang[::6]])
    nerve = np.array([[30.0, y, 0.0] for y in np.linspace(0, 100, 400)])
    rows = ev.depth_profile(nerve, cKDTree(skin), skin, step=20.0)
    assert len(rows) in (5, 6) and all(len(r) == 8 for r in rows)
    assert all(abs(r[1] - 20.0) < 1.5 for r in rows), rows          # 50 - 30 = 20 mm below the skin
    assert all(abs(r[2] - 30.0) < 1e-6 and abs(r[4]) < 1e-6 for r in rows)  # the shallowest point is on the line
    assert all(abs(np.hypot(r[5], r[7]) - 50.0) < 1e-6 for r in rows)      # the entry point is on the skin
    html = (repo / "viewer" / "atlas_viewer.template.html").read_text()
    for needle in ("Depth below skin along the course", "function courseShow", "function courseNeedle",
                   "depth_profile:s.depth_profile", "table.course"):
        assert needle in html, needle


def test_thin_sheets_are_decimated_by_quadric_collapse_not_clustering():
    """A 4 mm sheet vertex-clustered at a cell wider than its thickness turns into a lace of holes; the sheet ids
    go through quadric edge collapse instead, which keeps a closed sheet closed."""
    import sys
    from pathlib import Path
    import numpy as np
    import trimesh
    pytest.importorskip("fast_simplification")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    import export_viewer_bundle as ev
    assert {"diaphragm", "external_intercostals_r", "external_intercostals_l"} <= ev.SHEET_IDS
    # a closed 4 mm thick slab, 200 x 200 mm, finely triangulated (like a label-volume sheet)
    slab = trimesh.creation.box(extents=(200.0, 4.0, 200.0)).subdivide().subdivide().subdivide().subdivide()
    v, f = ev.decimate_quadric(slab.vertices, slab.faces, 800)
    out = trimesh.Trimesh(v, f, process=False)
    assert len(f) < len(slab.faces) and out.is_watertight, (len(f), out.is_watertight)   # a cube collapses less than a real sheet; the closed surface is the point
    assert abs(out.volume - slab.volume) / slab.volume < 0.05
