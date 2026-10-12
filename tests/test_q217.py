"""Q217: male LEFT forearm / elbow (own male Q214 page + Z male fitted Q211 page): the forearm muscles = the Z base muscles carried onto his forearm by one twisted-tube map, joined to the page's hand-side
tendon part, pushed inside his skin / out of his bones, separated by a 1 mm fascial interface; muscle ends onto his bones.

Synthetic tests run everywhere; tests on the built bundle / pages / reports skip when the artefact is not built."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest
import trimesh

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from scripts.transfer import q217_carry as CA  # noqa: E402
from scripts.transfer import q217_common as C  # noqa: E402
from scripts.transfer import q217_ends as E  # noqa: E402
from scripts.transfer import q217_slide as SL  # noqa: E402
from scripts.transfer import q217_twist as TW  # noqa: E402

OFF = np.array([0.13, 0.07, 0.11])


def box(lo, hi, sub=3):
    lo, hi = np.asarray(lo, float) + OFF, np.asarray(hi, float) + OFF
    m = trimesh.creation.box(extents=hi - lo)
    m.apply_translation((lo + hi) / 2)
    for _ in range(sub):
        m = m.subdivide()
    return np.asarray(m.vertices, float), np.asarray(m.faces, np.int64)


def tube(p0, p1, r, sections=24):
    m = trimesh.creation.cylinder(radius=r, segment=np.array([p0, p1], float) + OFF, sections=sections)
    v, f = trimesh.remesh.subdivide_to_size(np.asarray(m.vertices, float), np.asarray(m.faces, np.int64), max_edge=2.0)
    return np.asarray(v, float), np.asarray(f, np.int64)


def rot_y(a):
    c, s = np.cos(a), np.sin(a)
    return np.array([[c, 0, s], [0, 1, 0], [-s, 0, c]])


# ------------------------------------------------------------------------------------------------ twisted-tube map
def two_bones(n=60):
    """a radius-like and an ulna-like bar along y, 30 mm apart in x, as vertex clouds"""
    y = np.linspace(100, 300, n)
    r = np.stack([np.full(n, -20.0), y, np.zeros(n)], 1)
    u = np.stack([np.full(n, 10.0), y, np.zeros(n)], 1)
    ring = lambda c: np.concatenate([c + np.array([dx, 0, dz]) for dx, dz in ((3, 0), (-3, 0), (0, 3), (0, -3))])
    return ring(r), ring(u)


def test_twist_map_is_the_identity_when_the_bones_do_not_move():
    r, u = two_bones()
    tm = TW.TwistMap({"radius_l": r, "ulna_l": u}, {"radius_l": r.copy(), "ulna_l": u.copy()})
    x = np.random.default_rng(1).uniform([-40, 120, -20], [30, 280, 20], (300, 3))
    assert np.abs(tm(x) - x).max() < 1e-6


def twisted(r, u, total_deg, shift):
    """page bones = base bones turned about the axis x = -5, z = 0 by an angle growing linearly with y, plus a shift"""
    def f(p):
        a = np.radians(total_deg) * (p[:, 1] - 100) / 200.0
        c, s = np.cos(a), np.sin(a)
        q = p - np.array([-5.0, 0, 0])
        x = c * q[:, 0] + s * q[:, 2]
        z = -s * q[:, 0] + c * q[:, 2]
        return np.stack([x - 5.0, q[:, 1], z], 1) + shift
    return f(r), f(u)


def test_twist_map_follows_a_pronation_twist_of_the_bones_and_keeps_two_muscles_apart():
    r, u = two_bones()
    shift = np.array([7.0, -3.0, 11.0])
    rp, up = twisted(r, u, 90.0, shift)
    tm = TW.TwistMap({"radius_l": r, "ulna_l": u}, {"radius_l": rp, "ulna_l": up})
    # the two bone centrelines land on the page's (within 2 mm)
    cl_b = np.stack([np.full(40, -20.0), np.linspace(130, 270, 40), np.zeros(40)], 1)
    cl_p = twisted(cl_b, cl_b, 90.0, shift)[0]
    assert np.linalg.norm(tm(cl_b) - cl_p, axis=1).max() < 2.5
    # two disjoint muscle meshes stay disjoint (and keep their volume within 8 %) under the map
    va, fa = box([-30, 150, -10], [-10, 250, 10])
    vb, fb = box([0, 150, -10], [20, 250, 10])
    ma = trimesh.Trimesh(tm(va), fa, process=False)
    mb = trimesh.Trimesh(tm(vb), fb, process=False)
    v0 = abs(trimesh.Trimesh(va, fa, process=False).volume)
    assert abs(abs(ma.volume) / v0 - 1) < 0.08
    rows, tot = C.overlap_voxels({"a": (ma.vertices, ma.faces), "b": (mb.vertices, mb.faces)}, lo=(-90, 100, -60), hi=(60, 300, 80))
    assert tot < 0.05


# ------------------------------------------------------------------------------------------------ seam join
def test_join_closed_gives_one_watertight_surface_and_lands_b_on_a():
    a = tube([0, 100, 0], [0, 200, 0], 5.0)
    b = tube([6.0, 60, 2.0], [6.0, 140, 2.0], 5.0)           # the page's tendon part: 6 mm off in x, 2 mm in z, overlapping the seam plane y = 120
    v, f, info = CA.join_closed(a[0], a[1], b[0], b[1], 120.0)
    assert info["rim_loops"] == [1, 1]
    assert info.get("watertight") is True
    tm = trimesh.Trimesh(v, f, process=False)
    assert tm.is_watertight
    # B's rim sits on A's: the rim centroids at the plane agree within 1 mm
    c = CA.loops_at(v, f, 119.0)
    assert len(c) == 1 and np.linalg.norm(c[0][[0, 2]] - np.array([0.0, 0.0]) - OFF[[0, 2]]) < 1.0


def test_join_without_a_section_returns_the_carried_muscle_whole():
    a = tube([0, 150, 0], [0, 200, 0], 5.0)
    b = tube([0, 60, 0], [0, 100, 0], 5.0)
    v, f, info = CA.join_closed(a[0], a[1], b[0], b[1], 120.0)
    assert info["note"] == "no seam" and len(v) == len(a[0])


# ------------------------------------------------------------------------------------------------ tile / separator
def test_separator_pulls_two_overlapping_boxes_apart_without_a_dent():
    va, fa = box([0, 0, 0], [20, 60, 20])
    vb, fb = box([18, 0, 0], [38, 60, 20])
    SL.BOX_LO = np.array([-20.0, -20.0, -20.0])
    SL.BOX_HI = np.array([60.0, 80.0, 40.0])
    sk = type("S", (), {"signed": lambda self, p: np.full(len(p), -20.0, np.float32)})()
    sp = SL.Separator({"a": (va, fa), "b": (vb, fb)}, {}, {}, None, y_win=(-100.0, 1000.0), ramp_mm=1.0, log=lambda *a: None)
    for lam in (3.0, 3.0, 1.5, 1.5, 0.75, 0.75, 0.4, 0.4, 0.2, 0.2, 0.2, 0.2):
        sp.step(lam)
    rows, tot = C.overlap_voxels({k: (sp.x[k], sp.f[k]) for k in sp.ids}, lo=(-20, -20, -20), hi=(60, 80, 40))
    assert tot < 0.5                                         # from 2 x 60 x 20 = 2.4 cm3 of overlap
    from scipy.spatial import cKDTree
    pa, pb = SL.surface_samples(sp.x["a"], sp.f["a"], 0.5), SL.surface_samples(sp.x["b"], sp.f["b"], 0.5)
    dd = cKDTree(pb).query(pa)[0]
    assert float((dd < 0.3).mean()) < 0.12                    # the 1.0 mm fascial interface (0.5 mm each): only residual contacts at edges / corners are left
    v0 = abs(trimesh.Trimesh(va, fa, process=False).volume)
    for k in sp.ids:
        assert abs(abs(trimesh.Trimesh(sp.x[k], sp.f[k], process=False).volume) / v0 - 1) < 0.1


# ------------------------------------------------------------------------------------------------ ends
def test_end_plan_gives_the_origin_bone_to_the_proximal_end_and_the_insertion_bone_to_the_distal_end():
    from scripts.transfer.q217_slide import surface_samples
    hum = box([-10, 150, -10], [10, 200, 10])
    rad = box([-10, 40, -10], [10, 90, 10])
    bt = E.bone_trees({"humerus_l": hum, "radius_l": rad})
    v, f = tube([0, 100, 0], [0, 140, 0], 4.0)               # between the two bones, 10 mm from each
    rec = {"origin": "humerus_l: epicondyle", "insertion": "radius_l: styloid"}
    plan = E.plan(v, rec, bt)
    got = {nm: (bid, round(p5)) for nm, z, bid, p5, mn in plan}
    assert got["hi"][0] == "humerus_l" and got["lo"][0] == "radius_l"
    assert 5 <= got["hi"][1] <= 20 and 5 <= got["lo"][1] <= 20
    assert E.named_bones(rec) == ["humerus_l", "radius_l"]


def test_overlap_voxels_counts_the_shared_volume_of_two_boxes():
    va, fa = box([0, 0, 0], [10, 10, 10])
    vb, fb = box([5, 0, 0], [15, 10, 10])
    rows, tot = C.overlap_voxels({"a": (va, fa), "b": (vb, fb)}, lo=(-5, -5, -5), hi=(20, 15, 15))
    assert abs(tot - 0.5) < 0.05                              # 5 x 10 x 10 mm = 0.5 cm3
    assert abs(rows["a"]["shared_pct"] - 50.0) < 4.0


# ------------------------------------------------------------------------------------------------ built artefacts
NEW_BUNDLE = REPO / "build/viewer_m_hr_q217"
OLD_BUNDLE = REPO / "build/viewer_m_hr_q214"
ZPAGE = REPO / "build/q217/viewer_zan_vhm"
ZOLD = REPO / "build/q211/viewer_zan_vhm"
DER = REPO / "data/derived"


def _need(p):
    if not Path(p).exists():
        pytest.skip(f"{p} not built")


def test_zan_page_scope_check_lists_no_unlisted_change():
    _need(DER / "Q217_ship_diff_zan.json")
    r = json.loads((DER / "Q217_ship_diff_zan.json").read_text())
    assert r["geometry_changed_but_not_listed"] == [] and r["added"] == [] and r["removed"] == []
    assert r["unchanged"] > 2800


def test_zan_changed_muscles_are_inside_the_skin_and_out_of_the_bones_and_overlap_fell():
    _need(DER / "Q217_zan_metrics.json")
    m = json.loads((DER / "Q217_zan_metrics.json").read_text())
    a, b = m["before"], m["after"]
    assert b["total_shared_cm3"] < 0.25 * a["total_shared_cm3"]
    for i, x in b["per_muscle"].items():
        assert x["outside_skin_pct"] <= 1.0, (i, x["outside_skin_pct"])
        assert x["in_bone_pct"] <= 2.0, (i, x["in_bone_pct"])


def test_own_bundle_keeps_every_other_entry_byte_for_byte_and_the_source_class():
    _need(NEW_BUNDLE / "bundle.json")
    from scripts.transfer.q200_bundle import Bundle
    A, N = Bundle(OLD_BUNDLE), Bundle(NEW_BUNDLE)
    rep = json.loads((DER / "Q217_own_report.json").read_text())
    listed = set(rep["replaced"]) | set(rep["added"]) | set(rep["removed"])
    na = {it["e"]["id"]: it for it in N.items}
    for it in A.items:
        i = it["e"]["id"]
        if i in listed:
            continue
        assert i in na and na[i]["raw"] == it["raw"] and na[i]["e"] == it["e"], i
    for i in rep["added"]:
        assert na[i]["e"]["subject"] == "xfer_zan2vhm_arm_q217"
    for i in rep["replaced"]:
        assert na[i]["e"]["subject"].startswith("xfer_zan2vhm_limb") or na[i]["e"]["subject"].startswith("xfer_zan2")
