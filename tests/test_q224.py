"""Q224: top defects of the OWN pages from the Q223 audit -- vein bridges (rule-based, calibre-continuous, inside skin / clear of bone), duplicate tarsal / carpal meshes (evidence against the CT label), block-edge
muscles (reconnect, extend to bone, dome the flat cut face).

Synthetic tests run everywhere; tests on the built bundles / reports / pages skip when the artefact is not built."""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import trimesh
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from scripts.transfer import q224_veins as V  # noqa: E402
from scripts.transfer import q224_muscles as M  # noqa: E402
from scripts.transfer import q224_dups as D  # noqa: E402

DER = REPO / "data" / "derived"


# ------------------------------------------------------------------------------------------------ synthetic: veins
def tube_piece(y0, y1, r=4.0, x=0.0, z=0.0, sections=24, taper=2.5):
    """a closed tube along y with a rounded (tapering) tip at both ends, like a tracked outline: radius r in the body, shrinking over the last `taper` mm"""
    ys = np.linspace(y0, y1, int(abs(y1 - y0) / 1.5) + 1)
    rings = []
    for y in ys:
        d = min(y - y0, y1 - y) / taper
        rr = r * (np.sqrt(max(1 - (1 - min(d, 1.0)) ** 2, 0.02)) if d < 1.0 else 1.0)
        a = np.linspace(0, 2 * np.pi, sections, endpoint=False)
        rings.append(np.column_stack([x + rr * np.cos(a), np.full(sections, y), z + rr * np.sin(a)]))
    v = np.vstack(rings)
    f = []
    n = len(rings)
    for i in range(n - 1):
        for j in range(sections):
            a, b = i * sections + j, i * sections + (j + 1) % sections
            c, d_ = (i + 1) * sections + j, (i + 1) * sections + (j + 1) % sections
            f += [(a, b, d_), (a, d_, c)]
    v = np.vstack([v, [[x, y0 - 0.2, z]], [[x, y1 + 0.2, z]]])
    lo, hi = len(v) - 2, len(v) - 1
    for j in range(sections):
        f.append((lo, (j + 1) % sections, j))
        f.append((hi, (n - 1) * sections + j, (n - 1) * sections + (j + 1) % sections))
    return v, np.asarray(f, np.int64)


class StubCtx:
    """the two things bridge_vein asks of the page context: skin_state(points) and bone_field.inside(points)"""

    def __init__(self, bone_pts=None):
        self.bone_field = SimpleNamespace(inside=lambda P: (np.zeros(len(P), bool), np.zeros_like(P), np.full(len(P), np.inf)))

    def skin_state(self, P):
        return 100.0, 30.0


def two_pieces(gap=30.0, r2=4.0, dx=0.0):
    v1, f1 = tube_piece(0.0, 80.0, 4.0)
    v2, f2 = tube_piece(80.0 + gap, 150.0, r2, x=dx)
    v = np.vstack([v1, v2])
    f = np.vstack([f1, f2 + len(v1)])
    return v, f


def test_polygon_ellipse_recovers_the_semi_axes():
    t = np.linspace(0, 2 * np.pi, 200, endpoint=False)
    P = np.column_stack([6.0 * np.cos(t), 2.5 * np.sin(t)])
    e = V.polygon_ellipse(P)
    assert abs(e["a"] - 6.0) < 0.2 and abs(e["b"] - 2.5) < 0.1
    assert abs(abs(e["major"][0]) - 1.0) < 1e-3


def test_hermite_leaves_and_arrives_along_the_stump_tangents():
    pA, pB = np.array([0.0, 0, 0]), np.array([10.0, 60.0, 5.0])
    tA, tB = np.array([0, 1.0, 0]), np.array([0, -1.0, 0])
    P = V.hermite(pA, tA, pB, tB, kA=0.75, kB=0.75)
    T = V.tangents(P)
    assert np.allclose(P[0], pA) and np.allclose(P[-1], pB)
    assert T[0] @ tA > 0.97 and T[-1] @ (-tB) > 0.97


def test_a_gapped_tube_becomes_one_piece_with_continuous_calibre():
    v, f = two_pieces(gap=30.0, r2=3.2)
    tree = cKDTree(np.array([[500.0, 500.0, 500.0]]))
    v1, f1, info = V.bridge_vein("synthetic", v, f, StubCtx(), tree)
    assert v1 is not None, info["why"]
    assert info["pieces_after"] == 1 and len(info["pieces"]) == 2
    assert 25.0 <= info["links"][0]["new_part_mm"] <= 45.0                      # a bridge of about the gap, plus the removed tips
    for c in info["calibre_continuity"]:
        assert 0.8 <= c["ratio"] <= 1.25, c
    r = info["links"][0]["radius_mm"]
    assert r["min"] >= 0.9 * 3.2 - 1e-6 and r["max"] <= 1.1 * 4.0 + 1e-6          # between the two stump radii
    # the measured body of the first piece is untouched (mid-body surface within 0.6 mm)
    tm = trimesh.Trimesh(v1, f1, process=False)
    assert tm.is_watertight
    mid = v[(v[:, 1] > 20) & (v[:, 1] < 60)]
    assert trimesh.proximity.closest_point(tm, mid)[1].max() < 0.6


def test_a_bridge_that_would_touch_a_bone_is_refused_or_routed_clear_of_it():
    v, f = two_pieces(gap=30.0)
    # a bone surface sample cloud right on the straight route
    bone = np.column_stack([np.full(400, 0.0), np.linspace(70, 120, 400), np.full(400, 0.0)])
    pts = np.vstack([bone + np.array([dx, 0, dz]) for dx in np.linspace(-4, 4, 5) for dz in np.linspace(-4, 4, 5)])
    tree = cKDTree(pts)

    class Ctx(StubCtx):
        def __init__(self):
            self.bone_field = SimpleNamespace(inside=lambda P: (np.linalg.norm(P[:, [0, 2]], axis=1) < 4.0, np.zeros_like(P), np.zeros(len(P))) if False else (np.zeros(len(P), bool), np.zeros_like(P), np.zeros(len(P))))
    v1, f1, info = V.bridge_vein("synthetic_bone", v, f, Ctx(), tree)
    lk = info["links"][0]
    assert lk["hermite_clearance_mm"] < 3.0                                          # the straight route does hit it
    assert v1 is None or lk["bone_route"] is not None                                # accepted only when routed around it


def test_vein_badge_starts_with_rule_based_so_that_the_viewer_classifies_the_entry_rule_based():
    from scripts.transfer import q224_fix as FX
    info = dict(links=[dict(nearest_vertex_gap_mm=62.0, new_part_mm=70.3, centreline_mm=71.0, radius_mm=dict(start=4.75, end=5.85))], pieces=[1, 2], specks=[], tails_removed_mm3={"0.1": 413.0},
                volume_mm3=dict(bridge_new=6440.0, result=16769.0), old_to_new_mm=dict(max_outside_bridge=0.56, p95_outside_bridge=0.21))
    t = FX.vein_badge("Femoral vein", info)
    assert t.lower().startswith("rule-based bridge") and "NOT measured" in t and "70.3" in t


# ------------------------------------------------------------------------------------------------ synthetic: muscles / duplicates
def box(lo, hi, sub=3):
    m = trimesh.creation.box(extents=np.asarray(hi, float) - np.asarray(lo, float))
    m.apply_translation((np.asarray(lo, float) + np.asarray(hi, float)) / 2)
    for _ in range(sub):
        m = m.subdivide()
    return np.asarray(m.vertices, float), np.asarray(m.faces, np.int64)


def test_conforming_split_keeps_the_mesh_watertight_and_its_volume():
    m = trimesh.creation.box(extents=[20, 20, 10])
    v, f = np.asarray(m.vertices, float), np.asarray(m.faces, np.int64)
    top = [i for i, fc in enumerate(f) if (v[fc][:, 2] > 4.9).all()]
    es = M.facet_edges_longer(v, f, top, 3.0)
    assert es
    for _ in range(3):
        v, f = M.conforming_split(v, f, es)
        top = [i for i, fc in enumerate(f) if (v[fc][:, 2] > 4.9).all()]
        es = M.facet_edges_longer(v, f, top, 3.0)
    tm = trimesh.Trimesh(v, f, process=True)
    assert tm.is_watertight and abs(tm.volume - 4000.0) < 1.0
    assert len(f) > 12


def test_trim_by_removes_the_overlap_of_two_bones():
    B = SimpleNamespace(items=[dict(e=dict(id="a", nf=3000)), dict(e=dict(id="b", nf=3000))],
                        find=lambda s: [0] if s == "a" else [1], get=lambda s: dict(zip(("v", "f"), box([0, 0, 0], [20, 20, 20]) if s == "a" else box([14, 0, 0], [34, 20, 20]))))
    v1, f1, info = D.trim_by(B, "a", "b", min_vol=0.5)
    assert v1 is not None, info
    assert 0.6 < info["volume_ratio"] < 0.8                                         # 6 of 20 mm lost
    assert v1[:, 0].max() < 14.0                                                    # clear of the other bone


def test_candidate_thresholds_are_the_audit_thresholds():
    assert M.CAP_MIN_MM2 == 100.0 and M.ISLAND_SHARE_MIN == 0.02 and M.ISLAND_GAP_MIN == 5.0


# ------------------------------------------------------------------------------------------------ built artefacts
def _need(p):
    if not Path(p).exists():
        pytest.skip(f"{p} not built")


@pytest.mark.parametrize("body", ["m", "f"])
def test_ship_diff_lists_every_change_and_nothing_else(body):
    _need(DER / f"Q224_vertex_diff_{body}.json")
    d = json.loads((DER / f"Q224_vertex_diff_{body}.json").read_text())
    assert d["unlisted_changes"] == [] and d["problems"] == [] and d["added"] == [] and d["order_kept"] and d["quantum_same"]
    assert d["identical"] > 500


@pytest.mark.parametrize("body", ["m", "f"])
def test_report_has_the_vein_bridges_with_length_and_radius_and_the_guards(body):
    _need(DER / f"Q224_report_{body}.json")
    r = json.loads((DER / f"Q224_report_{body}.json").read_text())
    for sid, info in r["veins"].items():
        assert info["pieces_after"] == 1 and not info["why"], (sid, info["why"])
        for lk in info["links"]:
            assert lk["new_part_mm"] > 0 and lk["radius_mm"]["start"] > 0 and lk["radius_mm"]["end"] > 0
        z = info["bridge_zone"]
        assert z["inside_skin_pct"] == 100.0 and z["bridge_only_in_bone"] == 0
        for c in info["calibre_continuity"]:
            assert 0.8 <= c["ratio"] <= 1.25
        assert info["old_to_new_mm"]["p95_outside_bridge"] <= 0.6


def test_male_femoral_vein_right_gap_is_62_mm_and_is_bridged():
    _need(DER / "Q224_report_m.json")
    r = json.loads((DER / "Q224_report_m.json").read_text())["veins"]["femoral_v_r"]
    assert abs(r["links"][0]["nearest_vertex_gap_mm"] - 62.0) < 0.5 and 60.0 <= r["links"][0]["new_part_mm"] <= 80.0


def test_duplicates_removed_with_evidence():
    _need(DER / "Q224_report_f.json")
    f = json.loads((DER / "Q224_report_f.json").read_text())
    assert {r["id"] for r in f["removed"]} == {"tarsals_l", "tarsals_r"}
    for k in ("tarsals_l", "tarsals_r"):
        d = f["duplicates"][k]
        assert d["iou_individuals_union_vs_her_label"] > d["iou_composite_vs_her_label"] + 0.3
    _need(DER / "Q224_report_m.json")
    m = json.loads((DER / "Q224_report_m.json").read_text())
    assert {r["id"] for r in m["removed"]} == {"carpals_l", "carpals_r"} and all(r["hidden_default"] for r in m["removed"])


@pytest.mark.parametrize("body", ["m", "f"])
def test_changed_muscles_keep_their_subject_and_record_volumes(body):
    _need(DER / f"Q224_report_{body}.json")
    r = json.loads((DER / f"Q224_report_{body}.json").read_text())["muscles"]
    assert r["accepted"] == len(r["changed"]) > 20
    for sid, c in r["changed"].items():
        assert len(c["volume_cm3"]) == 2 and c["volume_cm3"][1] > 0 and c["steps"]
        assert 0.84 <= c["cumulative_guards"]["volume_ratio"] <= 1.4 and 0.88 <= c["cumulative_guards"]["length_ratio"] <= 1.35
        assert c["badge_added"].startswith("Q224 block-edge") and "Source class unchanged" in c["badge_added"]
        assert c["cumulative_guards"]["after"]["inside_skin_pct"] == 100.0


@pytest.mark.parametrize("body", ["m", "f"])
def test_new_bundle_veins_are_single_pieces_and_rule_based_badged(body):
    nb = REPO / f"build/viewer_{body}_hr_q224"
    _need(nb / "bundle.json")
    from scripts.transfer.q200_bundle import Bundle
    from scripts.transfer.q224_common import n_pieces_welded
    B = Bundle(nb)
    names = ["femoral_v_r", "femoral_v_l", "internal_jugular_v_r", "internal_jugular_v_l"] if body == "m" else ["internal_jugular_v_r", "internal_jugular_v_l"]
    for sid in names:
        g = B.get(sid)
        assert n_pieces_welded(g["v"], g["f"])[0] == 1, sid
        assert g["e"]["rec"]["procedural_badge"].lower().startswith("rule-based bridge")
    ids = {it["e"]["id"] for it in B.items}
    assert not ({"tarsals_l", "tarsals_r"} & ids if body == "f" else {"carpals_l", "carpals_r"} & ids)


def test_audit_after_has_no_tube_gaps_and_no_group_mesh_penetration_on_the_own_pages():
    _need(DER / "Q224_audit_before_after.json")
    a = json.loads((DER / "Q224_audit_before_after.json").read_text())
    for k in ("own_m", "own_f"):
        b, n = a[k]["q223_before"]["targeted"], a[k]["q224_after"]["targeted"]
        assert len(n["tube_gap_findings"]) < len(b["tube_gap_findings"]) and not [g for g in n["tube_gap_findings"] if "jugular" in g["id"] or "femoral" in g["id"]]
        assert len(n["duplicate_group_mesh_pairs_ge3mm"]) == 0 and len(b["duplicate_group_mesh_pairs_ge3mm"]) > 0
        assert n["flat_cut_faces_over_100mm2_muscles"] < b["flat_cut_faces_over_100mm2_muscles"]


@pytest.mark.parametrize("body", ["m", "f"])
def test_final_page_has_the_parts_sidecar_and_the_clinical_files(body):
    p = REPO / f"build/q224/viewer_{body}_hr"
    _need(p / "parts_data.json")
    for n in ("clinical_needle_tool.js", "clinical_risk.json", "clinical_motor_points.json"):
        assert (p / n).exists(), n
    html = next(p.glob("atlas_viewer*.html")).read_text(encoding="utf-8", errors="ignore")
    assert "cut-thsl" in html and "partsCtl" in html                              # cut slice thickness + parts list of the CURRENT template
