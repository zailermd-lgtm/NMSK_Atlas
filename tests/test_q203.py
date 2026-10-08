"""Q203: shoulder-girdle / seam / long-bone-end completion of the two OWN reconstructed models with Z-Anatomy, badged, measured data untouched.

Unit tests use synthetic meshes; the build tests (skipped when build/viewer_*_q203 is absent) check the shipped bundles and derived numbers."""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

import numpy as np
import pytest
import trimesh

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.transfer.q200_bundle import Bundle  # noqa: E402
from scripts.transfer.q200_continue import find_caps  # noqa: E402
from scripts.transfer.q200_merge import merge_structure  # noqa: E402
from scripts.transfer import q203_complete as C  # noqa: E402

DER = REPO / "data" / "derived"
Q200 = {"vhm": REPO / "build/viewer_m_hr_q200", "vhf": REPO / "build/viewer_f_hr_q200"}
Q203 = {"vhm": REPO / "build/viewer_m_hr_q203", "vhf": REPO / "build/viewer_f_hr_q203"}
NEW_SUBJECTS = {"vhm": {"xfer_zan2vhm_shoulder_q203", "xfer_zan2vhm_seams_q203"}, "vhf": {"xfer_zan2vhf_shoulder_q203", "xfer_zan2vhf_seams_q203"}}


def _json(name):
    p = DER / name
    if not p.exists():
        pytest.skip(f"{name} not present")
    return json.loads(p.read_text())


# ---------------------------------------------------------------- units
def test_z_ids_use_the_parts_z_anatomy_has():
    assert C.z_ids("deltoid_l") == ["zan_clavicular_part_of_deltoid_muscle_l", "zan_acromial_part_of_deltoid_muscle_l", "zan_scapular_spinal_part_of_deltoid_muscle_l"]
    assert len(C.z_ids("triceps_brachii_r")) == 3 and all(i.endswith("_r") for i in C.z_ids("triceps_brachii_r"))
    assert len(C.z_ids("pectoralis_major_l")) == 3
    assert C.z_ids("supraspinatus_l") == ["supraspinatus_l"]
    assert C.z_ids("sacrum") == ["sacrum"]


def test_gates_are_the_documented_ones():
    assert C.MIN_BEYOND_MUSCLE == 6.0 and C.MAX_SHIFT_MM == 30.0 and C.MIN_CAP_MM2 == 100.0
    assert C.E.FIT_ERR_MAX_MM == 25.0


def test_suffix_and_subject_tables_are_consistent():
    assert set(C.SUFFIX) == {"sh", "seam"}
    for (body, grp), subj in C.SUBJECT.items():
        assert subj.startswith("xfer_zan2") and subj.endswith("_q203") and body[2:] in subj


def _box_pair():
    a = trimesh.creation.box(extents=(10, 10, 10)); a.apply_translation([0, 5, 0])      # y in [0, 10]
    b = trimesh.creation.box(extents=(10, 10, 10)); b.apply_translation([0, 15, 0])     # y in [10, 20]
    return a, b


def test_merge_with_weld_closes_the_seam_ring():
    a, b = _box_pair()
    mv, mf = np.asarray(a.vertices, float), np.asarray(a.faces, np.int64)
    cap = find_caps(mv, mf, minarea=20.0, at_end=0.5)
    top = [c for c in cap if c["axis"] == "y" and abs(c["pos"] - 10.0) < 0.1]
    assert top
    from shapely.geometry import box as sbox
    covered = [dict(axis="y", pos=10.0, polys=[np.asarray(sbox(-5, -5, 5, 5).exterior.coords)[:-1].tolist()])]
    # the continuation = the upper box without its bottom face: its ring 0 coincides with the cap outline
    pv, pf = np.asarray(b.vertices, float), np.asarray(b.faces, np.int64)
    keep = ~(np.abs(pv[pf][:, :, 1] - 10.0) < 1e-6).all(1)
    v, f, info = merge_structure(mv, mf, pv, pf[keep], covered, weld=True)
    m = trimesh.Trimesh(v, f, process=False)
    assert info["cap_faces_removed"] >= 2
    assert m.is_watertight


def test_the_seam_json_writer_tolerates_bone_end_pieces():
    src = (REPO / "scripts/transfer/q203_complete.py").read_text()
    assert '"covered" in r and "axis" in r' in src


# ---------------------------------------------------------------- the shipped bundles
@pytest.mark.parametrize("body", ["vhm", "vhf"])
def test_q203_bundle_nothing_measured_changed_and_additions_are_badged(body):
    if not (Q203[body] / "bundle.json").exists():
        pytest.skip("q203 bundle not built")
    A, B = Bundle(Q200[body]), Bundle(Q203[body])
    n0 = len(A.items)
    assert len(B.items) > n0
    for ia, it in enumerate(A.items):                      # every Q200 entry (and with it every Q193 entry) stays in place, byte for byte
        n = B.items[ia]
        assert n["e"]["id"] == it["e"]["id"] and n["e"]["subject"] == it["e"]["subject"]
        assert n["raw"] == it["raw"], it["e"]["id"]
    for it in B.items[n0:]:
        e = it["e"]
        assert e["subject"] in NEW_SUBJECTS[body], e["id"]
        assert re.search(r"_zfill203s?$", e["id"]), e["id"]
        assert "Z-Anatomy" in e["rec"]["procedural_badge"] and "not edited" in e["rec"]["procedural_badge"], e["id"]
        assert re.search(r"validation", e["rec"]["procedural_badge"]), e["id"]
        v, f = B.mesh(it)
        assert np.linalg.norm(v[f[:, 0]] - v[f[:, 1]], axis=1).max() < 150.0, e["id"]          # nothing torn across the body


def test_new_subjects_are_described_and_classed_as_z_fill():
    txt = (REPO / "viewer" / "atlas_viewer.template.html").read_text(encoding="utf-8")
    for s in sorted(set().union(*NEW_SUBJECTS.values())):
        assert re.search(rf"^\s{{2}}{s}:\s*\"", txt, re.M), s
        assert s.startswith("xfer_zan2")


def test_vertex_diff_no_measured_entry_changed():
    d = _json("Q203_vertex_diff.json")
    for body, v in d.items():
        assert v["vs_q193"]["changed_non_Z"] == 0 and v["vs_q200"]["changed_non_Z"] == 0, body
        assert v["vs_q200"]["changed"] == [], body                      # Q203 adds only: not even a Z entry of Q200 moved
        assert v["vs_q200"]["identical"] == v["entries_q200"]
        assert v["entries_q203"] == v["entries_q200"] + v["added_count"]


@pytest.mark.parametrize("body", ["vhm", "vhf"])
def test_continuations_sit_on_a_cap_plane_of_their_measured_structure(body):
    seams = _json(f"Q203_seams_{body}.json")
    if not (Q203[body] / "bundle.json").exists():
        pytest.skip("q203 bundle not built")
    B = Bundle(Q203[body])
    checked = 0
    for nid, lst in seams.items():
        base = B.get(re.sub(r"_zfill203s?$", "", nid))
        assert base is not None, nid
        planes = [(c["axis"], c["pos"]) for kw in (dict(), dict(minarea=40.0, at_end=2.5)) for c in find_caps(base["v"], base["f"], **kw)]
        piece = B.get(nid)
        for s in lst:
            assert any(a == s["axis"] and abs(p - s["pos"]) < 4.0 for a, p in planes), (nid, s["axis"], s["pos"], planes[:4])
            k = "xyz".index(s["axis"])
            assert (np.abs(piece["v"][:, k] - s["pos"]) < 0.35).sum() >= 4
            checked += 1
    assert checked >= 20


def test_before_after_shoulder_flat_caps_down_and_counts_recorded():
    d = _json("Q203_before_after.json")
    for key in ("own_m", "own_f"):
        for side in "lr":
            sh = d[key][f"shoulder_{side}"]
            assert sh["after"]["flat_cap_area_mm2"] <= 0.6 * sh["before"]["flat_cap_area_mm2"], (key, side)
            assert sh["after"]["flat_caps"] < sh["before"]["flat_caps"]
    for key in ("own_m", "own_f"):
        tot = d[key]["total"]
        assert tot["after"]["flat_cap_area_mm2"] < tot["before"]["flat_cap_area_mm2"]


def test_wrist_ends_added_for_his_radius_and_ulna_and_her_right_ulna():
    rm = _json("Q203_rows_vhm.json"); rf = _json("Q203_rows_vhf.json")
    got = {(r["id"], r["end"]) for r in rm if r.get("stage") == "bone_end" and r.get("status") == "continued"}
    assert {("ulna_r", "distal"), ("ulna_l", "distal")} <= got            # his ulnar heads; his radii end where his carpals start (Z end would sit 30-50 % inside them: held)
    held = {(r["id"], r["end"]) for r in rm if r.get("stage") == "bone_end" and str(r.get("status", "")).startswith("held") and "carpal" in r.get("status", "")}
    assert ("radius_l", "distal") in held
    gf = {(r["id"], r["end"]) for r in rf if r.get("stage") == "bone_end" and r.get("status") == "continued"}
    assert ("ulna_r", "distal") in gf
    for r in rm + rf:
        if r.get("stage") == "bone_end" and r.get("status") == "continued":
            assert r["fit_err_median_mm"] <= 5.0 and r["beyond_mm"] >= 6.0 and r["inside_other_bone_frac"] <= 0.25


def test_source_facet_counts_recorded_and_page_equals_audit():
    a = _json("Q203_model_separation_audit.json")
    for key in ("own_m", "own_f"):
        bc = a[key]["by_class"]
        assert bc["filled_zan"]["entries"] > 0
        assert sum(v["entries"] for v in bc.values()) == a[key]["entries"] if "entries" in a[key] else True
    chk = _json("Q203_pagecheck.json")
    for which in ("male", "female"):
        assert chk[which]["match"]["desktop"] and chk[which]["match"]["phone"], which
        assert chk[which]["desktop"]["errors"] == [] and chk[which]["phone"]["errors"] == []
