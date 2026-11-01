"""Q296: the Open Anatomy survey, the legacy-VTK reader, the ossicle bone-point registration, the geometry report and
the four Z pages carrying the imported SPL Inner Ear Atlas structures (scripts/anatomy/q296/)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts/anatomy/q296"))

EAR_REPORT = REPO / "data/derived/Q296_ear_report.json"
PAGE_REPORT = REPO / "data/derived/Q296_page_report.json"
KEYS = ["base_f", "base_m", "comb_f", "comb_m"]
DIRS = {"base_m": "viewer_zan_atlas", "base_f": "viewer_base_female", "comb_m": "viewer_zan_vhm", "comb_f": "viewer_zan_female"}
STEM = {"base_m": "atlas_viewer_zan_atlas", "base_f": "atlas_viewer_base_female",
        "comb_m": "atlas_viewer_zan_male_fitted", "comb_f": "atlas_viewer_zan_female"}
UIDS = ("labyrinth", "spiral_lamina", "fenestra_cochleae", "stapedius")
LIC = REPO / "third_party/openanatomy_spl"


# ---------------------------------------------------------------- the reader
def test_vtk_reader_ascii_and_binary_agree(tmp_path):
    import oavtk296
    V = np.array([[0, 0, 0], [10, 0, 0], [0, 10, 0], [0, 0, 10]], float)
    F = np.array([[0, 1, 2], [0, 1, 3], [0, 2, 3], [1, 2, 3]])
    a = tmp_path / "a.vtk"
    with a.open("w") as fh:
        fh.write("# vtk DataFile Version 4.0\nt\nASCII\nDATASET POLYDATA\n")
        fh.write(f"POINTS {len(V)} float\n" + "\n".join(" ".join(str(x) for x in p) for p in V) + "\n")
        fh.write(f"POLYGONS {len(F)} {4 * len(F)}\n" + "\n".join("3 " + " ".join(str(i) for i in t) for t in F) + "\n")
    bv, bf = tmp_path / "b.vtk", None
    with bv.open("wb") as fh:
        fh.write(b"# vtk DataFile Version 4.0\nt\nBINARY\nDATASET POLYDATA\n")
        fh.write(f"POINTS {len(V)} float\n".encode()); fh.write(V.astype(">f4").tobytes())
        fh.write(f"\nPOLYGONS {len(F)} {4 * len(F)}\n".encode())
        fh.write(np.hstack([np.full((len(F), 1), 3), F]).astype(">i4").tobytes())
    for p in (a, bv):
        V2, F2 = oavtk296.read_polydata(str(p))
        assert np.allclose(V2, V) and np.array_equal(np.sort(F2, axis=1), np.sort(F, axis=1)), p
    assert bf is None


def test_vtk_reader_fan_triangulates_a_quad(tmp_path):
    import oavtk296
    p = tmp_path / "q.vtk"
    with p.open("w") as fh:
        fh.write("# vtk DataFile Version 3.0\nt\nASCII\nDATASET POLYDATA\nPOINTS 4 float\n0 0 0\n1 0 0\n1 1 0\n0 1 0\nPOLYGONS 1 5\n4 0 1 2 3\n")
    V, F = oavtk296.read_polydata(str(p))
    assert len(V) == 4 and len(F) == 2


def test_vtk_reader_rejects_a_non_vtk_file(tmp_path):
    import oavtk296
    p = tmp_path / "x.vtk"; p.write_bytes(b"not a vtk file at all\n")
    with pytest.raises(ValueError):
        oavtk296.read_polydata(str(p))


# ---------------------------------------------------------------- the registration
def _rot(ax, th):
    ax = np.asarray(ax, float); ax = ax / np.linalg.norm(ax); K = np.array([[0, -ax[2], ax[1]], [ax[2], 0, -ax[0]], [-ax[1], ax[0], 0]])
    return np.eye(3) + np.sin(th) * K + (1 - np.cos(th)) * K @ K


@pytest.mark.parametrize("reflect", [False, True])
def test_registration_recovers_a_known_similarity(reflect):
    import reg296
    rng = np.random.default_rng(3)
    src = {k: rng.normal(size=(400, 3)) * 3 + c for k, c in zip(reg296.OSSICLES, ([0, 0, 0], [6, 1, 0], [0, 7, 2]))}
    s, R, t = 0.3, _rot([0.3, 1, 0.2], 0.7), np.array([40.0, 700.0, -3.0])
    if reflect:
        R = R @ np.diag([-1.0, 1.0, 1.0])
    dst = {k: s * v @ R.T + t for k, v in src.items()}
    M = reg296.fit(src, dst)
    assert M["mode"] == ("reflect" if reflect else "proper"), M["mode"]
    assert abs(M["s"] - s) < 1e-3, M["s"]
    assert M["rms"] < 0.05, M["rms"]
    assert np.allclose(reg296.apply(M, src["malleus"]), dst["malleus"], atol=0.05)


def test_registration_prefers_the_better_handedness():
    import reg296
    rng = np.random.default_rng(5)
    # a chiral point set: a right-handed helix cannot be matched by a proper rotation to its mirror
    th = np.linspace(0, 6, 300)
    H = np.stack([np.cos(th), np.sin(th), th / 3], 1) * 4
    src = {k: H + rng.normal(scale=0.01, size=H.shape) + np.array(c) for k, c in zip(reg296.OSSICLES, ([0, 0, 0], [12, 0, 0], [0, 12, 0]))}
    dst = {k: v * np.array([-1.0, 1, 1]) for k, v in src.items()}
    M = reg296.fit(src, dst)
    assert M["mode"] == "reflect" and M["rms"] < 0.2, (M["mode"], M["rms"])


# ---------------------------------------------------------------- the licence obligations
def test_part_b_licence_text_is_shipped_in_full_with_the_required_preface():
    t = (LIC / "LICENSE").read_text(encoding="utf-8")
    assert ('All or portions of this licensed product (such portions are the "Software") have been obtained' in t
            and "under license from The Brigham and Women's Hospital, Inc. and are subject to the following terms" in t)
    assert "PART A. CONTRIBUTION AGREEMENT" in t and "PART B. DOWNLOADING AGREEMENT" in t and "PART C. MISCELLANEOUS" in t
    b = t.split("PART B. DOWNLOADING AGREEMENT")[1].split("PART C. MISCELLANEOUS")[0]
    for n in range(1, 9):                                     # all eight paragraphs of Part B, not just the grant
        assert f"\n{n}. " in b, n
    assert "research purposes only" in b and "may be used to endorse or promote" in b
    assert "does not grant any rights with respect to third party software" in b


def test_notice_keeps_the_attributions_and_the_required_citation():
    n = (LIC / "NOTICE").read_text(encoding="utf-8")
    for s in ("Bartling", "Jakab", "Kikinis", "German Cancer Research Center", "Brigham and Women's Hospital",
              "AJNR Am J Neuroradiol. 2004", "P41 RR013218", "P41 EB015902", "Open Anatomy"):
        assert s in n, s
    assert "endorse" in n and "research purposes only" in n.lower()


def test_modifications_are_marked_as_such():
    r = (LIC / "README.md").read_text(encoding="utf-8")
    for s in ("modified version", "decimation", "mirror", "right ear", "similarity"):
        assert s.lower() in r.lower(), s
    g = (REPO / "docs/GEOMETRY_SOURCES.md").read_text(encoding="utf-8")
    assert "Open Anatomy" in g and "3D Slicer License Part B" in g


def test_the_survey_document_exists_and_covers_all_seven_atlases():
    s = (REPO / "docs/research/Q296_openanatomy_survey.md").read_text(encoding="utf-8")
    for a in ("Inner Ear", "Liver", "Abdominal", "Knee", "Head and Neck", "Brain", "Mauritanian"):
        assert a in s, a
    assert "Cooper" in s and "levator ani" in s            # the owner's missing-structure list is answered
    assert "Part B" in s


# ---------------------------------------------------------------- the geometry report
@pytest.mark.skipif(not EAR_REPORT.exists(), reason="Q296 geometry report not built")
def test_geometry_report_is_anatomically_sane():
    r = json.loads(EAR_REPORT.read_text())
    assert set(r["pages"]) == set(KEYS)
    assert r["decimate"] == 0.4
    assert set(r["atlas"]) >= {"Model_10_Labyrinth", "Model_140_Malleus_Bone"}
    for st in r["atlas"].values():
        assert len(st["sha256"]) == 64 and st["bytes"] > 1000 and st["url"].startswith("https://www.openanatomy.org/")
    for k, P in r["pages"].items():
        for s in ("l", "r"):
            fit = P[f"_fit_{s}"]
            assert fit["mode"] == ("reflect" if s == "l" else "proper"), (k, s)
            assert fit["median_mm"] < 0.4 and fit["p95_mm"] < 1.0 and fit["max_mm"] < 2.0, (k, s, fit)
            assert 0.25 < fit["s"] < 0.36, (k, s, fit["s"])       # the atlas is ~3.1-3.4x life size
            for uid in UIDS:
                e = P[f"{uid}_{s}"]
                assert e["tris"] == pytest.approx(round(e["tris_atlas"] * 0.4), abs=4), (k, uid)
                assert abs(e["cm3"] - e["cm3_undecimated"]) / e["cm3_undecimated"] < 0.03, (k, uid)
                assert 5 < e["dihedral_mean_deg"] < 45 and e["defect_edges_pct"] < 2.0, (k, uid, e)
            lab = P[f"labyrinth_{s}"]
            assert 0.12 < lab["cm3"] < 0.28, (k, s, lab["cm3"])          # bony labyrinth ~130-260 mm3
            assert 12 < max(lab["ext_mm"]) < 24, (k, s, lab["ext_mm"])
            assert P[f"spiral_lamina_{s}"]["inside_temporal_bone_pct"] > 80, (k, s)
            assert P[f"fenestra_cochleae_{s}"]["inside_temporal_bone_pct"] > 95, (k, s)
            for uid in UIDS:                                            # nothing clashes with a bone, the skin or an organ
                for h in P[f"{uid}_{s}"]["overlap"]:
                    assert h["cat"] not in ("bone", "skin", "viscera", "organ") or h["pct_of_volume"] < 2.0, (k, uid, h)


@pytest.mark.skipif(not EAR_REPORT.exists(), reason="Q296 geometry report not built")
def test_the_left_side_is_the_mirror_of_the_right():
    r = json.loads(EAR_REPORT.read_text())["pages"]
    for k, P in r.items():
        for uid in UIDS:
            a, b = P[f"{uid}_l"], P[f"{uid}_r"]
            assert a["tris"] == pytest.approx(b["tris"], abs=4), (k, uid)
            assert abs(a["cm3"] - b["cm3"]) / max(b["cm3"], 1e-9) < 0.01, (k, uid)


# ---------------------------------------------------------------- the pages
@pytest.mark.skipif(not PAGE_REPORT.exists(), reason="Q296 pages not built")
@pytest.mark.parametrize("key", KEYS)
def test_page_carries_the_imported_structures(key):
    d = REPO / "build/q296" / DIRS[key]
    if not d.exists():
        pytest.skip("build/q296 not present")
    rep = json.loads(PAGE_REPORT.read_text())[key]
    h = (d / f"{STEM[key]}.html").read_text(encoding="utf-8")
    i = h.find("window.__ANATOMY_MANIFEST__=") + len("window.__ANATOMY_MANIFEST__=")
    man = json.JSONDecoder().raw_decode(h[i:])[0]
    oa = [m for m in man["meshes"] if m["id"].startswith("oa_")]
    assert sorted(m["id"] for m in oa) == sorted(rep["added"])
    assert sum(m["ic"] for m in oa) == rep["triangles_added"]
    assert len(oa) == 8 and {m["side"] for m in oa} == {"l", "r"}
    for m in oa:
        r = m["rec"]
        assert "IMPORTED REAL MESH, NOT RULE-BASED" in r["procedural_badge"]
        assert "3D Slicer License Part B" in r["procedural_badge"] and "MODIFIED version" in r["procedural_badge"]
        assert "Brigham and Women's Hospital" in r["source"] and "PMID 15466345" in r["source"]
        assert r["geom_src"].startswith("SPL Inner Ear Atlas") and "third_party/openanatomy_spl/LICENSE" in r["geom_src"]
        assert m["sys"] == ("muscle" if "stapedius" in m["id"] else "bone")
    assert "obtained under license from The Brigham and Women's Hospital" in man["attribution"]
    assert "IMPORTED REAL MESHES" in man["attribution"]


@pytest.mark.skipif(not PAGE_REPORT.exists(), reason="Q296 pages not built")
@pytest.mark.parametrize("key", KEYS)
def test_pose_rig_covers_the_new_structures(key):
    rep = json.loads(PAGE_REPORT.read_text())[key]
    rig = json.loads((REPO / f"data/anatomy/pose_rig_{key}.json").read_text())["rig"]
    # Q297 removed one mesh (the generated perineal surface closure) from the two female Z pages, so the rig is that
    # much shorter than the Q296 high-water index; the count still has to equal the page's own mesh count.
    q297 = REPO / "data/derived/Q297_page_report.json"
    dropped = len(json.loads(q297.read_text(encoding="utf-8"))["pages"][key].get("dropped") or []) if q297.exists() else 0
    assert rig["count"] == rep["new_indices"][-1] + 1 - dropped
    assert len(rig["nv"]) == rig["count"]
    covered = {i for e in rig["skin"] for i in [e[0]]} | {i for _, lst in rig["rigid"] for i in lst}
    # the Q297 removal sat at a LOWER index than every Q296 import (the perineal closure is index 2939, the imports
    # start above 3200), so each Q296 index moved down by the number of meshes removed below it
    want = {i - dropped for i in rep["new_indices"]}
    assert want <= covered, sorted(want - covered)
    assert "Q296" in rig["notes"]
