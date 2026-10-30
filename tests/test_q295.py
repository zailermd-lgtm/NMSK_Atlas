"""Q295: fat and voids -- the cross-section rasteriser, the report (before / after void fractions, fat volumes, triangles, penetration,
realness) and the six built pages carrying the `fat` system (scripts/anatomy/q295/)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest
import trimesh

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts/anatomy/q295"))

REPORT = REPO / "data/derived/Q295_fat_report.json"
PAGE_REPORT = REPO / "data/derived/Q295_page_report.json"
KEYS = ["own_f", "own_m", "base_f", "base_m", "comb_f", "comb_m"]
DIRS = {"own_m": "viewer_m_hr", "own_f": "viewer_f_hr", "base_m": "viewer_zan_atlas", "base_f": "viewer_base_female",
        "comb_m": "viewer_zan_vhm", "comb_f": "viewer_zan_female"}
STEM = {"own_m": "atlas_viewer_male", "own_f": "atlas_viewer_female", "base_m": "atlas_viewer_zan_atlas", "base_f": "atlas_viewer_base_female",
        "comb_m": "atlas_viewer_zan_male_fitted", "comb_f": "atlas_viewer_zan_female"}


def test_raster_fills_a_closed_sphere_and_a_hollow_shell():
    import sl295 as S
    s = trimesh.creation.icosphere(subdivisions=4, radius=20.0)
    inner = trimesh.creation.icosphere(subdivisions=4, radius=10.0); inner.invert()
    for mesh, area in ((s, np.pi * 400), (trimesh.util.concatenate([s, inner]), np.pi * 300)):
        V = np.asarray(mesh.vertices); F = np.asarray(mesh.faces)
        N = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])

        class P:          # minimal page: one structure
            pass
        pg = P(); pg.V = V.astype(np.float32); pg.F = F; pg.fs = np.zeros(len(F), np.int32); pg.N = N
        pg.ymin = V[F][:, :, 1].min(1); pg.ymax = V[F][:, :, 1].max(1); pg.order = np.argsort(pg.ymin); pg.ymin_sorted = pg.ymin[pg.order]
        sid, seg = S.Page.segments(pg, 0.3)
        pix, psid, bad = S.raster(sid, seg, (-30.0, -30.0, 0.5, 120, 120))
        assert not bad
        got = len(np.unique(pix)) * 0.25
        assert abs(got - area) / area < 0.03, (got, area)


def test_sheet_categories_are_outline_only():
    import sl295 as S
    assert {"fascia", "joint", "bursa", "insertion"} <= S.SHEET


@pytest.mark.skipif(not REPORT.exists(), reason="Q295 report not built")
def test_report_before_after_and_realness():
    r = json.loads(REPORT.read_text())
    assert set(r["pages"]) == set(KEYS)
    for k, P in r["pages"].items():
        regs = P["regions"]
        assert len(regs) >= 10, k
        for name, e in regs.items():
            assert e["void_after"] < e["void_before"], (k, name)
            assert e["fat_penetration_frac"] < 0.15, (k, name, e["fat_penetration_frac"])
        # most of the interior filled on the trunk and the thigh
        for name in ("abdomen", "pelvis", "thigh"):
            assert regs[name]["void_after"] < 0.25, (k, name, regs[name]["void_after"])
        sh = P["shipped"]
        assert sh["fat_sub"]["mesh_cm3"] > 5000 and sh["fat_deep"]["mesh_cm3"] > 300, (k, sh)
        assert P["triangles_total"] <= 650000
        for g in sh.values():
            assert 15 < g["dihedral_mean_deg"] < 45 and g["defect_edge_frac"] < 0.02
        lo = P["left_out"]["thickness_hist_cm3"]
        thin = lo["0-2 mm"] + lo["2-4 mm"]; tot = sum(lo.values())
        assert thin / tot > 0.9, (k, lo)          # what stays empty is a seam of a few mm, not an unexplained hole


@pytest.mark.skipif(not PAGE_REPORT.exists(), reason="Q295 pages not built")
@pytest.mark.parametrize("key", KEYS)
def test_page_has_the_fat_system(key):
    d = REPO / "build/q295" / DIRS[key]
    if not d.exists():
        pytest.skip("build/q295 not present")
    rep = json.loads(PAGE_REPORT.read_text())[key]
    h = (d / f"{STEM[key]}.html").read_text(encoding="utf-8")
    if key.startswith("own"):
        i = h.find("window.__ANATOMY_BUNDLE__=")
        assert '"cat":"fat"' in h or '"cat": "fat"' in h
        assert 'fat:       {hex:0xE9D08A, label:"Fat & unlabelled soft tissue"}' in h
    else:
        i = h.find("window.__ANATOMY_MANIFEST__=") + len("window.__ANATOMY_MANIFEST__=")
        man = json.JSONDecoder().raw_decode(h[i:])[0]
        fat = [m for m in man["meshes"] if m["sys"] == "fat"]
        assert sorted(m["id"] for m in fat) == sorted(rep["added"])
        assert sum(m["ic"] for m in fat) == rep["triangles_added"]
        for m in fat:
            assert "MEASURED FROM IMAGING" in m["rec"]["procedural_badge"] and m["rec"]["geom_src"].startswith("Q295")
        assert '"fat","skin"];' in h and "alphaFor.fat = 0.12" in h
    assert "capA(it)" in h                       # the cut-face fill keeps the faint fat solid


def test_templates_and_class_map():
    own = (REPO / "viewer/atlas_viewer.template.html").read_text(encoding="utf-8")
    zan = (REPO / "viewer/zan_atlas.template.html").read_text(encoding="utf-8")
    cap = (REPO / "viewer/cut_cap/cut_cap.js").read_text(encoding="utf-8")
    assert "function capA(it)" in cap and cap.split("function capA(it)")[1][:200] in own and cap.split("function capA(it)")[1][:200] in zan
    assert 'sysAlpha[c] = c === "fat" ? 0.12 : 1;' in own
    assert '{k:"fat",label:"Fat & unlabelled soft tissue"}' in zan
    rules = json.loads((REPO / "clinical/data/imaging_tissues.json").read_text())["mapping_rules"]["rules"]
    fr = [r for r in rules if r.get("cat") == ["fat"]]
    assert [r["cls"] for r in fr] == ["soft_unassigned", "fat"]
