"""Q212: remaining flat-cut planes of the two OWN reconstructed models completed with badged Z-Anatomy where Z reaches the cut; his wrist re-segmented from his own CT.

Unit tests use synthetic data; the build tests (skipped when build/viewer_*_q212 is absent) check the shipped bundles, pages and derived numbers."""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.transfer.q200_bundle import Bundle  # noqa: E402
from scripts.transfer import q212_complete as Q  # noqa: E402
from scripts.transfer import q212_wrist_mesh as WM  # noqa: E402

DER = REPO / "data" / "derived"
Q203 = {"vhm": REPO / "build/viewer_m_hr_q203", "vhf": REPO / "build/viewer_f_hr_q203"}
Q212 = {"vhm": REPO / "build/viewer_m_hr_q212", "vhf": REPO / "build/viewer_f_hr_q212"}
PAGES203 = {"m": REPO / "build/q203/viewer_m_hr", "f": REPO / "build/q203/viewer_f_hr"}
PAGES212 = {"m": REPO / "build/q212/viewer_m_hr", "f": REPO / "build/q212/viewer_f_hr"}
HIDDEN = {"carpals_r", "carpals_l", "ulna_r_zfill203s"}


def _json(name):
    p = DER / name
    if not p.exists():
        pytest.skip(f"{name} not present")
    return json.loads(p.read_text())


# ---------------------------------------------------------------- units
def test_alias_table_reaches_the_z_meshes_q203_missed():
    assert Q.z_ids("temporalis_l") == ["zan_temporalis_muscle_l"]
    assert Q.z_ids("tibialis_posterior_r") == ["zan_tibialis_posterior_muscle_r"]
    assert Q.z_ids("semispinalis_cervicis_l") == ["zan_semispinalis_colli_muscle_l"]
    assert Q.z_ids("iliopsoas_r") == ["zan_psoas_major_r", "zan_iliacus_muscle_r"]
    assert len(Q.z_ids("levator_ani_l")) == 4 and Q.z_ids("levator_ani_l")[0] == "levator_ani_l"
    assert Q.z_ids("deltoid_l")[0].startswith("zan_clavicular_part_of_deltoid")        # the Q203 parts still resolve
    assert Q.z_ids("supraspinatus_l") == ["supraspinatus_l"]
    assert "semispinalis_capitis" not in Q.ALIAS                                      # Z-Anatomy has no semispinalis capitis: no wrong substitute


def test_gates_documented():
    assert Q.C.MIN_BEYOND_MUSCLE == 6.0 and Q.C.MAX_SHIFT_MM == 30.0 and Q.E.FIT_ERR_MAX_MM == 25.0       # unchanged Q203 gates
    assert Q.FIT_REV_MAX_MM == 8.0 and Q.FIT_BELLY_MAX_MM == 10.0 and Q.LOFT_RATIO_MAX == 12.0
    assert Q.TIP_MAX_MM == 20.0 and Q.TIP_MIN_BEYOND_MM == 30.0 and Q.TAG == "_zfill212"
    for (body, grp), subj in Q.C.SUBJECT.items():
        assert subj == f"xfer_zan2{body}_seams_q212"


def test_cleft_is_left_out_between_radius_end_and_carpals():
    ws = np.zeros((30, 10, 10), np.int8)
    ws[:14] = 1; ws[16:] = 3                         # two bones, a 2-voxel gap of unassigned voxels between them is NOT what the watershed gives: it assigns every voxel
    ws[14:16] = 3
    hu = np.full(ws.shape, 500.0, np.float32); hu[13:17] = 100.0       # low-HU cleft across the partition surface
    seg = dict(ws=ws, Lc=np.ones(ws.shape, bool), hu=hu)
    p = WM.pieces(seg)
    assert not (p["radius_distal"] & p["carpals"]).any()
    assert not p["radius_distal"][13:17].any() and not p["carpals"][13:17].any()      # cleft voxels belong to neither
    assert p["radius_distal"][:10].all() and p["carpals"][20:].all()                  # bone far from the cleft stays


def test_mesh_of_a_box_is_closed_and_decimated():
    m = np.zeros((40, 40, 40), bool); m[10:30, 10:30, 10:30] = True
    xs = np.arange(40) * 0.5
    v, f, st = WM.mesh_of(m, xs, xs, xs)
    import trimesh
    tm = trimesh.Trimesh(v, f)
    assert tm.is_watertight and abs(st["volume_cm3"] - 1.0) < 0.05 and len(f) >= 400


# ---------------------------------------------------------------- the shipped bundles
@pytest.mark.parametrize("body", ["vhm", "vhf"])
def test_q212_bundle_adds_only_and_every_addition_is_badged(body):
    if not (Q212[body] / "bundle.json").exists():
        pytest.skip("q212 bundle not built")
    A, B = Bundle(Q203[body]), Bundle(Q212[body])
    n0 = len(A.items)
    assert len(B.items) > n0
    for ia, it in enumerate(A.items):                      # every Q203 entry (hence every measured one) keeps its mesh bytes, id and subject
        n = B.items[ia]
        assert n["e"]["id"] == it["e"]["id"] and n["e"]["subject"] == it["e"]["subject"]
        assert n["raw"] == it["raw"], it["e"]["id"]
        hid = bool(n["e"].get("hidden_default")) and not it["e"].get("hidden_default")
        assert hid == (body == "vhm" and it["e"]["id"] in HIDDEN), it["e"]["id"]       # only the three superseded entries of his wrist start hidden
    for it in B.items[n0:]:
        e = it["e"]
        bad = e["rec"]["procedural_badge"]
        if e["subject"] == f"xfer_zan2{body}_seams_q212":
            assert re.search(r"_zfill212$", e["id"]), e["id"]
            assert "Z-Anatomy" in bad and "not edited" in bad and "validation" in bad, e["id"]
        else:
            assert body == "vhm" and e["subject"] == "ct_vhm_wrist_q212" and re.search(r"(_distal_q212|carpals_[rl]_q212)$", e["id"]), e["id"]
            assert "re-segmented from his frozen CT" in bad and "no Z-Anatomy geometry" in bad
        v, f = B.mesh(it)
        assert np.linalg.norm(v[f[:, 0]] - v[f[:, 1]], axis=1).max() < 300.0, e["id"]


def test_vertex_diff_file():
    d = _json("Q212_vertex_diff.json")
    for body, v in d.items():
        assert v["mesh_bytes_changed"] == [] and v["mesh_bytes_identical"] == v["entries_q203"]
        assert v["entries_q212"] == v["entries_q203"] + v["added_count"]
    assert set(d["vhm"]["hidden_by_default_added"]) == HIDDEN and d["vhf"]["hidden_by_default_added"] == []
    assert len(d["vhm"]["measured_added"]) == 6 and d["vhf"]["measured_added"] == []


@pytest.mark.parametrize("body", ["vhm", "vhf"])
def test_continued_rows_obey_the_gates(body):
    rows = [r for r in _json(f"Q212_rows_{body}.json") if r.get("stage") == "muscle" and r.get("status") == "continued"]
    assert rows
    for r in rows:
        assert r["beyond_mm"] >= 6.0 and r["shift_mm"] <= 30.0
        if r["fit_rule"].startswith("one-sided"):
            assert r["fit_err_median_mm"] <= 25.0, r["id"]
        else:
            assert r["fit_rule"].startswith("two-sided") and r["fit_err_median_mm"] > 25.0
            nums = [float(x) for x in re.findall(r"(\d+\.\d+) mm", r["fit_rule"])]
            assert nums[1] <= 8.0 and nums[2] <= 10.0, r["fit_rule"]
        if r["mode"] == "loft":
            assert r["z_to_cap_area"] <= 12.0
        if "tip_to_bone_mm" in r:
            assert r["tip_to_bone_mm"] <= 20.0


def test_her_right_biceps_is_continued_by_the_two_sided_gate_and_his_wrist_items_are_recorded():
    r = _json("Q212_rows_vhf.json")
    b = [x for x in r if x["id"] == "biceps_brachii_r" and abs(x["pos"] - 521.7) < 0.5 and x["stage"] == "muscle"][0]
    assert b["status"] == "continued" and b["fit_rule"].startswith("two-sided") and b["fit_err_median_mm"] == pytest.approx(30.4, abs=0.2)
    w = _json("Q212_wrist_report.json")
    for sd in "rl":
        seg = w["his_wrist"][sd]["segmentation"]
        assert 3.5 <= seg["carp_label_to_radius"] <= 6.5          # cm3 of his carpal label that is distal radius epiphysis
        assert 1.0 <= seg["carp_label_to_ulna"] <= 2.5
        for k, m in w["his_wrist"][sd]["meshes"].items():
            if m["photo"]["within_1p5mm"] is not None and m["photo"]["in_photo_box"] >= 0.3:
                assert m["photo"]["within_1p5mm"] >= 0.55, (sd, k)          # independent check against his cryosection photographs
    for nm, t in w["his_wrist"]["truncation_vs_Z_page"].items():
        if nm.startswith("radius"):
            assert t["z_beyond_new"] <= 4.0 and t["gained_mm"] >= 14.0      # was 15-18 mm short of the Z fit
    h = w["her_left_wrist"]
    for nm in ("radius", "ulna"):                                           # her photographs show a cream-to-cream gap as wide as the model's: nothing to close
        assert h[nm]["evidence_gap_min_mm"] > 5.0 and h[nm]["evidence_gap_p1_mm"] + 3.0 >= h[nm]["mesh_gap_min_mm"]


def test_before_after_numbers():
    d = _json("Q212_global_caps.json")
    for body in ("vhm", "vhf"):
        b, a = d[body]["before_q203"], d[body]["after_q212"]
        assert a["by_cat"]["muscle"]["area_mm2"] < b["by_cat"]["muscle"]["area_mm2"]
        assert a["by_cat"]["muscle"]["caps"] <= b["by_cat"]["muscle"]["caps"]
    q = _json("Q212_before_after.json")
    for key in ("own_m", "own_f"):
        t = q[key]["total"]
        assert t["after"]["flat_cap_area_mm2"] < t["before"]["flat_cap_area_mm2"]
    r = _json("Q212_remaining_caps.json")
    assert any("coincides with the end of the Z structure" in k for k in r["vhm"]) and any("measured mass larger" in k for k in r["vhf"])


# ---------------------------------------------------------------- template, page, clinical
def test_new_subjects_are_described_and_classed():
    txt = (REPO / "viewer" / "atlas_viewer.template.html").read_text(encoding="utf-8")
    for s in ("xfer_zan2vhm_seams_q212", "xfer_zan2vhf_seams_q212", "ct_vhm_wrist_q212"):
        m = re.search(rf"^\s{{2}}{s}:\s*\"(.*)\",?$", txt, re.M)
        assert m, s
    assert not re.search(r"rule", re.search(r"^\s{2}ct_vhm_wrist_q212:\s*\"(.*)\"", txt, re.M).group(1), re.I)     # class 'measured', not 'rule-based'


def test_source_facet_counts_recorded_and_page_equals_audit():
    a = _json("Q212_model_separation_audit.json")
    chk = _json("Q212_pagecheck.json")
    for which, key in (("male", "own_male"), ("female", "own_female")):
        bc = a[key]["by_class"]
        assert chk[which]["match"]["desktop"] and chk[which]["match"]["phone"], which
        assert chk[which]["desktop"]["errors"] == [] and chk[which]["phone"]["errors"] == []
        assert chk[which]["desktop"]["entry_classes"] == {c: v["entries"] for c, v in bc.items() if v["entries"]}
        assert chk[which]["desktop"]["group_classes"] == {c: v["ids"] for c, v in bc.items() if v["ids"]}
    old = _json("Q203_model_separation_audit.json")
    assert a["own_male"]["by_class"]["measured"]["ids"] == old["own_male"]["by_class"]["measured"]["ids"] + 6
    assert a["own_male"]["by_class"]["filled_zan"]["ids"] == old["own_male"]["by_class"]["filled_zan"]["ids"] + 2
    assert a["own_female"]["by_class"]["filled_zan"]["ids"] == old["own_female"]["by_class"]["filled_zan"]["ids"] + 8
    assert a["own_female"]["by_class"]["measured"] == old["own_female"]["by_class"]["measured"]


@pytest.mark.parametrize("which", ["m", "f"])
def test_clinical_needle_tool_unchanged_in_the_q212_pages(which):
    if not (PAGES212[which] / "clinical_needle_tool.js").exists():
        pytest.skip("q212 page not built")
    assert (PAGES212[which] / "clinical_needle_tool.js").read_bytes() == (PAGES203[which] / "clinical_needle_tool.js").read_bytes()
