"""Q250: Base . Female with a female skeleton and Combined . Female with her own pelvis: reports, indicators (before / after), guards, ship diff, wording, and (when build/q250 exists) the built page dirs."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
D = REPO / "data" / "derived"
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO / "scripts" / "anatomy"))


def J(name):
    p = D / name
    if not p.exists():
        pytest.skip(f"{name} not built")
    return json.loads(p.read_text())


IND = None


def ind():
    global IND
    if IND is None:
        IND = J("Q250_sex_indicators.json")
    return IND


def test_base_female_subpubic_angle_is_female_after_and_was_male_before():
    P = ind()["pages"]
    assert P["Base F (before Q250)"]["subpubic_angle_deg"] < 62 and P["Base F (before Q250)"]["subpubic_angle_deg"] == P["Base M"]["subpubic_angle_deg"]   # the old Base female WAS the male body
    assert P["Base F (Q250)"]["subpubic_angle_deg"] >= 78.6                                                        # PubMed 32274246 CT cut-off (male 68.6 +- 7.6, female 87.4 +- 6.5)
    assert P["Imaging-based M (his own CT)"]["subpubic_angle_deg"] < 78.6 < P["Imaging-based F (her own CT)"]["subpubic_angle_deg"]


def test_combined_female_pelvis_is_hers_after():
    P = ind()["pages"]
    assert P["Combined F (before Q250)"]["subpubic_angle_deg"] < 70
    assert P["Combined F (Q250)"]["subpubic_angle_deg"] >= 78.6
    assert abs(P["Combined F (Q250)"]["intertuberous_mm"] - P["Imaging-based F (her own CT)"]["intertuberous_mm"]) < 25


def test_pelvic_indicators_move_toward_the_women_reference_range():
    R = ind(); P = R["pages"]; ts = R["ts_women"]
    assert ts["subpubic_angle_deg"]["n"] >= 40                                                                        # n CT women, TotalSegmentator v2.0.1, CC BY 4.0
    for k in ("intertuberous_mm", "bi_iliac_breadth_mm", "inlet_index_ap_over_transverse_pct"):
        old, new, t = P["Base F (before Q250)"][k], P["Base F (Q250)"][k], ts[k]
        assert abs(new - t["mean"]) <= 2 * t["sd"], k                                  # inside the women range (mean +- 2 SD) after ...
        if k != "bi_iliac_breadth_mm":
            assert abs(old - t["mean"]) > 1.0 * t["sd"], k                              # ... and the old male-derived value was not (outlet width: old 86.5 vs 106 +- 13; inlet index 61 vs 93 +- 10)
    assert abs(P["Base F (Q250)"]["shoulder_to_hip_ratio"] - P["Imaging-based F (her own CT)"]["shoulder_to_hip_ratio"]) < abs(P["Base F (before Q250)"]["shoulder_to_hip_ratio"] - P["Imaging-based F (her own CT)"]["shoulder_to_hip_ratio"])


def test_target_ranges_are_cited_or_flagged_unverified():
    R = ind()
    for k in R["keys"]:
        assert k["literature"] or k["kind"] == "ts", k["key"]
        if k["kind"] == "unv":
            assert "UNVERIFIED" in k["literature"]
    assert any("32274246" in k["literature"] for k in R["keys"])


def _warp_report(name):
    return J(name)


@pytest.mark.parametrize("name", ["Q250_base_f_warp_report_her.json", "Q250_comb_f_warp_report.json"])
def test_warp_report_guards_and_attachments(name):
    r = _warp_report(name)
    w = r["warp"]
    assert w["newly_in_bone_vertices"] >= 0 and "attachment_distance_after_mm" in w
    a = w["attachment_distance_after_mm"]
    assert a["fraction_le_1mm"] >= 0.999 and a["max"] <= 1.05                    # origins / insertions (vertices within 1 mm of a bone) stay within 1 mm of the moved bone
    st = r["structures"]
    assert all("area_ratio" in s and "mean_move_mm" in s for s in st.values())


def test_base_female_report_lists_the_registration_and_the_female_target():
    f = [n for n in ("Q250_base_f_warp_report_her.json",) if (D / n).exists()]
    if not f:
        pytest.skip("not built")
    r = json.loads((D / f[0]).read_text())
    assert r["pelvis_target"] in ("her", "mean")
    pr = r["pelvis_registration"]
    assert pr["_symphysis"]["gap_after_mm"] <= 3.0                              # pubic symphysis closed like a real one (it was 6.3 mm on the Z male pelvis)
    assert pr["hip_bone_l"]["median_mm"] < 4 and pr["sacrum"]["median_mm"] < 4
    sk = r["skeleton"]
    assert sk["segment_scale_from_her"]["leg_thigh"] < 1.0 and sk["trunk_field"]["smoothing"] > 0
    assert len(r["dropped_hra_structures"]) >= 30                               # the HRA organs / vessels / ligaments are re-registered on the new pelvis, not carried


def test_ship_diff_has_no_unlisted_structure_for_the_two_pages():
    for n in ("Q250_vertex_diff_base_f.json", "Q250_vertex_diff_comb_f.json"):
        r = J(n)
        assert r["unlisted"] == [], n


def test_wording_no_longer_says_male_derived_body_in_the_name():
    t = (REPO / "scripts/set_titles_q231.py").read_text()
    assert '"atlas_viewer_base_female.html": "Base · Female",' in t
    b = (REPO / "scripts/zanatomy/build_zan_atlas_viewer.py").read_text()
    assert "Z-Anatomy deformed onto a female skeleton" in b and "ONE woman" in b or "ONE woman (59 years old)" in b
    assert "HuBMAP" in b and "Combined &middot; Female" in b
    hub = (REPO / "viewer/atlas_hub.html").read_text()
    assert "Base · Female (male-derived body)" not in hub


def test_built_pages_have_the_q250_badges_and_titles():
    base = REPO / "build/q250/viewer_base_female"
    if not (base / "atlas_viewer_base_female.html").exists():
        pytest.skip("build/q250 not built")
    from scripts.zanatomy import q205_pages as P5
    man, blob = P5.load_page(base, "atlas_viewer_base_female")
    by = {m["id"]: m for m in man["meshes"]}
    assert "Q250 female skeleton" in by["hip_bone_l"]["rec"]["procedural_badge"] and "uterus" in by and "vagina" in by
    assert "Q250 female skeleton" in by["zan_biceps_brachii_l" if "zan_biceps_brachii_l" in by else "biceps_brachii_l"]["rec"]["procedural_badge"]
    assert "Q250" in man["attribution"]
    html = (base / "atlas_viewer_base_female.html").read_text(encoding="utf-8")
    assert "<title>NMSK Atlas — Base · Female</title>" in html and "male-derived body)" not in html.split("</title>")[0]
    comb = REPO / "build/q250/viewer_zan_female"
    manc, _ = P5.load_page(comb, "atlas_viewer_zan_female")
    byc = {m["id"]: m for m in manc["meshes"]}
    assert "Q250 own pelvis" in byc["hip_bone_l"]["rec"]["procedural_badge"] and "Q250" in manc["attribution"]
