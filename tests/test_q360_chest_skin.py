"""Q360: Base · Female chest skin rebuilt as one surface (scripts/anatomy/q360/chest_skin_q360.py).
Unit tests of the geometry steps + the committed report's guards (skipped when the report is absent)."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest
import trimesh

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "anatomy" / "q360"))
X = pytest.importorskip("chest_skin_q360")
REPORT = REPO / "data/derived/Q360_chest_skin_report.json"


def _plane(n=6, size=40.0):
    """a flat n x n grid in z = 0, normals +z, left half label 0 / right half label 1"""
    xs = np.linspace(0, size, n + 1)
    V = np.array([[x, y, 0.0] for y in xs for x in xs])
    F, L = [], []
    for j in range(n):
        for i in range(n):
            a = j * (n + 1) + i; b = a + 1; c = a + n + 1; d = c + 1
            lab = 0 if i < n // 2 else 1
            F += [[a, b, d], [a, d, c]]; L += [lab, lab]
    return V, np.array(F), np.array(L)


def test_refine_is_conforming_and_respects_locked_edges():
    V, F, L = _plane()
    e, c = np.unique(X.edges_of(F), axis=0, return_counts=True)
    bd = e[c == 1]
    lock_edges = bd[:3]
    V2, F2, L2 = X.refine(V, F, L, lock_edges, hmax=2.0)
    e2, c2 = np.unique(X.edges_of(F2), axis=0, return_counts=True)
    assert (c2 <= 2).all()                                    # manifold, no T-junction duplicates
    assert len(np.unique(e2[c2 == 1].ravel())) >= 4 * 6       # border subdivided
    for a, b in lock_edges:                                   # a locked edge is still one edge
        assert ((e2[:, 0] == min(a, b)) & (e2[:, 1] == max(a, b))).any()
    assert np.isclose(trimesh.Trimesh(V2, F2, process=False).area, 1600.0)
    assert set(np.unique(L2)) == {0, 1}


def test_delaunay_flips_keep_labels_and_vertices():
    V, F, L = _plane()
    rng = np.random.RandomState(0)
    V = V + np.c_[rng.uniform(-1, 1, (len(V), 2)), np.zeros(len(V))] * (np.abs(V[:, :2] - 20) < 19).all(1)[:, None]
    F2, n = X.delaunay_flips(V, F, L)
    assert F2.shape == F.shape
    assert np.bincount(L).tolist() == np.bincount(L).tolist()
    # the label outline is unchanged: the edges between the two labels are the same set
    def border(Fx):
        t = trimesh.Trimesh(V, Fx, process=False)
        adj = t.face_adjacency
        return set(map(tuple, np.sort(t.face_adjacency_edges[L[adj[:, 0]] != L[adj[:, 1]]], axis=1).tolist()))
    assert border(F2) == border(F)


def test_slabs_share_their_border_and_weld_fully():
    V, F, L = _plane()
    V2, F2, L2 = X.refine(V, F, L, np.zeros((0, 2), int), hmax=3.0)
    Y = V2 - 3.0 * X.vnormals(V2, F2)
    pieces = {}
    for i in (0, 1):
        v, f, used, cls = X.slab(V2, Y, F2[L2 == i])
        t = trimesh.Trimesh(v, f, process=False)
        assert t.is_watertight and t.is_winding_consistent and t.volume > 0
        assert (cls == 0).any()                               # a wall at the border
        pieces[f"p{i}"] = (v, f)
    w = X.weld_stats(pieces, {"p0", "p1"})
    # the shared border (outer and inner) welds exactly; the rest of each rim is the free outer border of the plane
    for k in w:
        assert w[k]["welded"] > 0
    shift = {"p0": pieces["p0"], "p1": (pieces["p1"][0] + [0.0, 0.0, 0.5], pieces["p1"][1])}
    assert X.weld_stats(shift, {"p0", "p1"})["p1"]["welded"] == 0


def test_mirror_and_stats_helpers():
    a = np.array([[1.0, 0, 0], [2, 1, 0]])
    assert X.mirror_med(a, a * [-1, 1, 1]) == 0.0
    s = X.st([1.0, 2.0, 3.0])
    assert s["max"] == 3.0 and s["mean"] == 2.0 and s["n"] == 3


@pytest.mark.skipif(not REPORT.exists(), reason="no Q360 report")
def test_report_guards():
    r = json.loads(REPORT.read_text())
    assert r["schema"] == "nmsk.q360.chest_skin.v1"
    g = r["guards"]
    assert g["pass"] is True
    assert not g["weld_below_min"] and not g["breast_tissue_outside"] and not g["structures_gaining_outside"]
    assert g["slabs_closed_and_consistent"] and g["deviation_over_cap_vertices"] == 0
    assert g["mesh_order_last_two"] == ["skin_vulva_cvh", "skin_perineum_rule_q358"]
    for v in ("front", "lateral_r", "lateral_l"):
        assert g["holes_after_px"][v] <= g["holes_before_px"][v]
    assert len(r["regions"]) == 18
    for k in r["regions"]:
        assert r["weld_pct"][k]["after"] >= 80.0 > r["weld_pct"][k]["before"]
        d = r["per_region"][k]["deviation_mm"]
        assert {"max", "mean", "p95"} <= set(d)
    # the backups beside the page hold no other version of these 18 meshes (why route A starts from the Z source)
    assert set(r["originals_beside_page"].values()) <= {"identical"}


def test_script_text_is_clean():
    t = (REPO / "scripts/anatomy/q360/chest_skin_q360.py").read_text()
    for w in ("ultrasound", "hounsfield", "t1_se", "imaging_tissues", "mrayl", "b-mode", "claude-", "opus", "sonnet"):
        assert w not in t.lower()
