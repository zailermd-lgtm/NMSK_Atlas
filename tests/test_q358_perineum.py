"""Q358: Base · Female vulva / perineum skin -- the real CVH surface cleaned, the skin ring closed by a rule-based surface."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts/anatomy/q358"))
import perineum_skin_q358 as Q  # noqa: E402

REPORT = REPO / "data/derived/Q358_perineum_report.json"
DOC = REPO / "docs/Q358_perineum_skin.md"
PAGE = REPO / "build/q309/viewer_base_female"
FORBIDDEN = ["ultrasound", "hounsfield", "t1_se", "imaging_tissues", "tissue table", "nmskultrasound", "acoustic", "mrayl", "b-mode"]


def test_every_atlas_fact_has_a_book_and_page():
    assert len(Q.ATLAS) >= 6
    for k, v in Q.ATLAS.items():
        assert v["fact"] and re.search(r"\bpp?\. \d+", v["cite"]), k
        assert "Mannan" in v["cite"] or "Gray's Atlas" in v["cite"], k
    assert abs(Q.INCH_MM - 25.4) < 1e-9


def test_slab_is_closed_and_consistently_wound():
    """the slab builder (used for the re-cut real surface and the rule surface) closes any open sheet"""
    import trimesh
    n = 6
    g = np.array([[i, j, 0.0] for j in range(n) for i in range(n)])
    F = []
    for j in range(n - 1):
        for i in range(n - 1):
            a = j * n + i
            F += [[a, a + 1, a + n + 1], [a, a + n + 1, a + n]]
    F = np.array(F)
    V, Fs, used = Q.slab(g, g - np.array([0, 0, 3.0]), F)
    t = trimesh.Trimesh(V, Fs, process=False)
    assert t.is_watertight and t.is_winding_consistent
    assert abs(abs(t.volume) - 25 * 3.0) < 1e-6
    assert len(used) == n * n


def test_resample_keeps_every_polyline_vertex():
    poly = np.array([[0, 0, 0], [10, 0, 0], [10, 7, 0], [0, 7, 0.0]])
    cnt = Q.split_counts(poly, 12)
    assert cnt.sum() == 12 and (cnt >= 1).all()
    pts = Q.resample_poly(poly, cnt)
    for p in poly:
        assert np.min(np.linalg.norm(pts - p, axis=1)) < 1e-9


@pytest.mark.skipif(not REPORT.exists(), reason="report not generated")
def test_report_guards_and_closure():
    r = json.loads(REPORT.read_text(encoding="utf-8"))
    assert r["schema"] == "nmsk.q358.perineum.v1"
    g = r["guards"]
    assert g["pass"] and g["ring_closed"] and g["no_structure_gains_outside_skin"]
    assert g["real_vertices_move_max_mm"] <= g["real_move_cap_mm"] + 0.01
    assert r["ring_open_slices_y_mm"]["after"] == []
    assert r["ring_open_slices_y_mm"]["before"], "the open ring was the defect"
    rs = r["rule_surface"]
    assert rs["id"] == Q.NEW_ID and rs["watertight"] and rs["winding_consistent"]
    assert rs["volume_cm3"] > 0 and rs["outer_area_mm2"] > 0
    c = r["real_surface_cleaning"]
    assert c["kept"]["outer_area_mm2"] > 0   # (the CVH source has non-manifold edges: not watertight)
    sm = c.get("staircase_smoothing")
    if sm:   # the optional staircase smoothing: capped, borders pinned
        assert sm["move_max_mm"] <= Q.CAP_REAL + 1e-6 and sm["pinned"] > 0
    else:
        assert c["vertices_moved"] == 0
    assert len(c["loose_pieces_removed"]) >= 1
    for v in r["atlas_facts"].values():
        assert v["cite"]


@pytest.mark.skipif(not REPORT.exists(), reason="report not generated")
def test_tucks_stay_within_the_q353_cap():
    r = json.loads(REPORT.read_text(encoding="utf-8"))
    for k, t in r.get("tuck", {}).get("structures", {}).items():
        if t["ships"]:
            assert t["displacement"]["max_mm"] <= 8.0 + 1e-6, k


def test_new_card_is_badged_rule_based_with_citations():
    rep = {"rim": {"vertices": 36}, "rule_surface": {"outer_area_mm2": 1.0, "area_visible_estimate_mm2": 1.0, "volume_cm3": 1.0},
           "real_surface_cleaning": {"kept": {"outer_area_mm2": 1.0}}, "landmarks": {}}
    e = Q.new_entry(rep)
    assert e["id"] == Q.NEW_ID and e["sys"] == "skin" and e["side"] == "m"
    b = e["rec"]["procedural_badge"]
    assert b.startswith("RULE-BASED SURFACE") and "Mannan" in b and "Gray's Atlas" in b
    assert "RULE-BASED" in e["rec"]["geom_src"]


def test_no_forbidden_words_and_no_model_identifiers():
    files = [REPO / "scripts/anatomy/q358/perineum_skin_q358.py", Path(__file__)]
    files += [p for p in (REPORT, DOC) if p.exists()]
    for p in files:
        t = p.read_text(encoding="utf-8").lower()
        for w in FORBIDDEN:
            if p == Path(__file__) and w in FORBIDDEN:
                continue
            assert w not in t, (p, w)
        if p != Path(__file__):
            assert not re.search(r"claude-|opus|sonnet|haiku", t), p


@pytest.mark.skipif(not (PAGE / "index.html").exists(), reason="build page not present")
def test_build_page_state_is_consistent():
    """before the apply the page has no rule surface and the vulva is the last mesh; after it the rule surface is the last mesh
    and the vulva card carries the cleaning note"""
    man, blob, _ = Q.read(PAGE)
    ids = [m["id"] for m in man["meshes"]]
    if Q.NEW_ID in ids:
        assert ids[-1] == Q.NEW_ID and ids[-2] == Q.CVH_ID
        cv = next(m for m in man["meshes"] if m["id"] == Q.CVH_ID)
        assert "Q358 cleaning" in cv["rec"]["procedural_badge"]
    else:
        assert ids[-1] == Q.CVH_ID
