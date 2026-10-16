"""Q243: the HRA v1.10 structures on the pages: reports, guards, ship diffs (0 unlisted), left / right, the lumbar numbering finding, the male skip, and (when build/q243 exists) the built pages."""
import json
import re
import sys
from pathlib import Path

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


VESSEL_IDS = ["uterine_a_l", "uterine_a_r", "uterine_v_l", "uterine_v_r", "internal_iliac_v_l", "internal_iliac_v_r", "internal_pudendal_v_l", "internal_pudendal_v_r",
              "middle_rectal_v_l", "middle_rectal_v_r", "inferior_rectal_v_l", "inferior_rectal_v_r", "superior_rectal_v", "median_sacral_v", "superior_rectal_a"]


def _ves(rep):
    return {k: v for k, v in rep["structures"].items() if k in VESSEL_IDS}


@pytest.mark.parametrize("name,key", [("Q243_report_own_f.json", "own_f"), ("Q243_report_comb_f.json", "comb_f"), ("Q243_report_base_f.json", "base_f")])
def test_every_shipped_vessel_passes_the_guards_and_records_length_and_calibre(name, key):
    rep = J(name)
    ves = _ves(rep)
    assert set(ves) == set(VESSEL_IDS)
    shipped = [k for k, v in ves.items() if not v.get("held")]
    assert set(rep["shipped"]) >= set(shipped) and all(s in shipped for s in rep["shipped"] if s in VESSEL_IDS)
    assert {"own_f": 15, "comb_f": 15, "base_f": 12}[key] == len(shipped)
    for k in shipped:
        g = ves[k]["gates"]
        assert g["pass"] is True
        assert g["bone_min_mm"] >= 1.0 - 1e-6, k                          # bones >= 1 mm
        assert g["skin_distance_min_mm"] >= 15, k                         # inside the skin
        assert g["length_mm"] > 10 and 0.5 < g["calibre_mm"] < 12, k      # tube length + calibre recorded
        assert g["watertight"] and g["volume_cm3"] and g["caps"]["left_open"] == 0
        assert g["max_move_out_of_bone_mm"] <= 6.0 and g["moved_fraction_pct"] <= 40
        assert g["left_right"]["ok"] is True
        assert "vertices_inside_page_organ_pct" in g                      # overlap with neighbours reported


@pytest.mark.parametrize("name", ["Q243_report_own_f.json", "Q243_report_comb_f.json", "Q243_report_base_f.json"])
def test_left_right_by_position_and_by_course(name):
    rep = J(name)
    for k, v in _ves(rep).items():
        g = v["gates"]; lr = g["left_right"]
        if k.endswith("_l"):                                              # atlas +X = right: left structures at negative x, nearer the left hip bone
            assert g["centroid_x_mm"] < 0 and lr["nearest_hip_is_same_side"] and lr["mean_distance_to_hip_mm"]["l"] < lr["mean_distance_to_hip_mm"]["r"], k
        elif k.endswith("_r"):
            assert g["centroid_x_mm"] > 0 and lr["nearest_hip_is_same_side"] and lr["mean_distance_to_hip_mm"]["r"] < lr["mean_distance_to_hip_mm"]["l"], k
        else:
            assert abs(g["centroid_x_mm"]) < 25, k
        if k.startswith("uterine_"):                                      # to the uterus side: reaches the uterus, medial end nearer than the lateral end
            c = g["course"]
            assert c["min_distance_to_uterus_mm"] <= 8 and c["medial_end_to_uterus_mm"] < c["lateral_end_to_uterus_mm"], k
        if k.startswith("internal_pudendal"):                             # along the same-side ischium (pudendal canal), lower end near the ischial tuberosity
            c = g["course"]
            assert c["fraction_within_10mm_of_same_side_hip_pct"] >= 50 and c["inferior_end_to_ischial_tuberosity_mm"] <= 45, k
    assert rep["rectal_order"]["ok"]                                      # superior > middle > inferior rectal vessels


def test_own_f_ship_diff_zero_unlisted_and_counts():
    d = J("Q243_vertex_diff_f.json")
    rep = J("Q243_report_own_f.json")
    assert d["unlisted_changes"] == [] and d["problems"] == [] and d["removed"] == [] and d["card_only"] == []
    assert d["identical"] == d["entries_old"] == 686 and d["entries_new"] == d["entries_old"] + len(d["added"])
    assert sorted(d["added"]) == sorted(d["added_expected"]) == sorted(rep["shipped"])
    assert sum(1 for s in d["added"] if s.startswith("nucleus_pulposus_")) == 14 and sum(1 for s in d["added"] if s.startswith("spinal_cord_segment_")) == 24
    assert len([s for s in d["added"] if s in VESSEL_IDS]) == 15


@pytest.mark.parametrize("key,name", [("comb_f", "Q243_vertex_diff_comb_f.json"), ("base_f", "Q243_vertex_diff_base_f.json")])
def test_z_pages_ship_diff_zero_unlisted(key, name):
    d = J(name)
    assert d["unlisted"] == [] and d["removed"] == [] and d["geometry_changed"] == [] and d["card_only"] == []
    assert sorted(d["added"]) == sorted(d["added_expected"]) and len(d["added"]) == {"comb_f": 15, "base_f": 12}[key]


def test_nucleus_pulposus_inside_the_disc_space_and_cord_inside_the_canal():
    rep = J("Q243_report_own_f.json")
    S = rep["structures"]
    nuc = {k: v for k, v in S.items() if k.startswith("nucleus_")}
    cord = {k: v for k, v in S.items() if k.startswith("cord_")}
    assert len(nuc) == 24 and len(cord) == 29
    for k, v in nuc.items():
        g = v["gates"]
        if v.get("held"):
            assert g["held_reason"]
            continue
        assert g["inside_disc_pct"] >= 95 and g["bone_min_mm"] >= 1.0 - 1e-6 and g["volume_ratio_to_hra"] >= 0.25 and g["watertight"], k
    for k, v in cord.items():
        g = v["gates"]
        if v.get("held"):
            assert g["held_reason"]
            continue
        assert g["canal_inside_pct"] >= 98 and g["canal_tested_pct"] >= 80 and g["bone_min_mm"] >= 1.0 - 1e-6 and g["watertight"], k
    held = sorted(k for k, v in cord.items() if v.get("held"))
    assert held == ["cord_L1", "cord_L2", "cord_T10", "cord_T11", "cord_T12"]            # the HRA cord is wider than her canal at T10-L2 (it touches the HRA vertebrae by up to 2.4 mm in the library's own frame)
    # the nucleus of the HRA L1-L2 disk has no disc on the page
    assert nuc["nucleus_L1-L2"].get("held") and nuc["nucleus_L1-L2"]["gates"]["page_disc"] is None


def test_lumbar_numbering_finding_q185k2():
    rep = J("Q243_report_own_f.json")
    ln = rep["lumbar_numbering"]
    m = ln["mapping"]
    assert [m[f"L{i}"]["page_name"] for i in range(1, 7)] == ["L1", "L1B", "L2", "L3", "L4", "L5"]
    assert all(m[f"L{i}"]["fit_residual_median_mm"] < 1.0 for i in range(1, 7))          # rank match: every one of the six lumbar bodies is the HRA vertebra of the same rank
    assert m["L2"]["page_disc_below"] == "intervertebral_disc_l1_l2" and m["L1"]["page_disc_below"] is None and m["L6"]["page_disc_below"] == "intervertebral_disc_l5_s1"
    assert "RIB-ANCHORED" in ln["consequence"] and "No structure of the page is renamed" in ln["decision"]
    sf = rep["spine_fits"]
    assert all(sf[lv]["residual_median_mm"] < 1.0 for lv in sf if lv != "S1") and len(sf) == 26


def test_male_prostate_zones_not_shipped_with_numbers():
    for name in ("Q243_report_own_m.json", "Q243_report_comb_m.json"):
        r = J(name)
        assert r["ships"] is False and r["centroid_offset_mm"] > r["rule"]["max_centroid_offset_mm"]
        assert r["mean_inside_page_prostate_pct"] < 10 and r["reason"]
        assert r["registration"]["residual_mm"]["median"] < 3 and 0.9 < r["registration"]["scale"] < 1.1
        zl = [k for k in r["zones"] if k.endswith("_l")]
        for k in zl:                                                       # left / right naming: HRA _L zones lie at -X (left) in the atlas frame
            assert r["zones"][k]["centroid"][0] < r["zones"][k.replace("_l", "_r")]["centroid"][0], k


def test_comb_f_spine_not_shipped_because_z_has_its_own():
    r = J("Q243_spine_comb_f.json")
    assert r["z_lumbar_vertebrae"] == 5 and r["hra_lumbar_vertebrae"] == 6
    assert len(r["z_page_already_has"]["nucleus_pulposus"]) >= 20 and r["z_page_already_has"]["spinal_cord_parts"]


def test_parts_table_and_markers():
    t = json.loads((REPO / "data/anatomy/structure_parts_hra_q243.json").read_text())
    assert t["counts"]["parts"] == 18 and {r["structure_id"] for r in t["parts"]} == {"uterus", "uterine_tube"}
    assert all(r["part_type"] == "organ part" and r["refs"] == ["hra_united_female_v110"] and r["hra_node"].startswith("VH_F_") for r in t["parts"])
    assert "urinary_bladder" in t["not_added"]
    g = J("Q243_parts_hra.json")
    for body in ("vhf", "zan_f", "zbase_f"):
        assert g[body]["ok"] == g[body]["total"] == 18
    # left / right: the _l tube parts lie at -X
    xs = {m["part"]: m["xyz"][0] for m in g["vhf"]["markers"]}
    for part in ("ampulla", "isthmus", "infundibulum", "fimbriae"):
        assert xs[f"uterine_tube.{part}_l"] < 0 < xs[f"uterine_tube.{part}_r"]


# ------------------------------------------------------------------------------------------------------------------------------------ built pages
PAGES = {"own_f": ("build/q243/viewer_f_hr", "atlas_viewer_female.html"), "comb_f": ("build/q243/viewer_zan_female", "atlas_viewer_zan_female.html"),
         "base_f": ("build/q243/viewer_base_female", "atlas_viewer_base_female.html")}


def _page(key):
    d, h = PAGES[key]
    p = REPO / d / h
    if not p.exists():
        pytest.skip(f"{d} not built")
    return p.read_text(encoding="utf-8"), REPO / d


def test_own_f_page_has_the_structures_with_subject_labels_and_badges():
    html, d = _page("own_f")
    m = re.search(r'<script[^>]*id="bundle-json"[^>]*>(.*?)</script>', html, re.S)
    structs = json.loads(m.group(1))["structures"]
    by = {}
    for s in structs:
        by.setdefault(s["id"], s)
    for sid in VESSEL_IDS:
        assert by[sid]["subject"] == "xfer_hra2vhf_q243" and by[sid]["cat"] == "vessel"
        b = by[sid]["rec"]["procedural_badge"]
        assert "SAME DONOR" in b and "NOT measured" in b and "centreline length" in b and "model tube diameter" in b and "signed distance" in b
    assert sum(1 for s in structs if s["subject"] == "xfer_hra2vhf_spine_q243") == 38
    assert "xfer_hra2vhf_q243" in json.loads(m.group(1))["subject"] and "xfer_hra2vhf_spine_q243" in json.loads(m.group(1))["subject"]
    assert "xfer_hra2vhf_q243:" in html and "xfer_hra2vhf_spine_q243:" in html                    # SUBJECT_LABELS
    assert 'if (b.indexOf("xfer_hra2") === 0) return "reference_same_donor";' in html              # Source class
    nuc = by["nucleus_pulposus_l2_l3"]["rec"]["procedural_badge"]
    assert "Q185k2" in nuc and "L1B" in nuc and "NOT changed" in nuc


def test_own_f_page_calibre_abbreviations_parts_symmetry():
    html, d = _page("own_f")
    cal = json.loads(re.search(r'id="nmsk-calibre">(.*?)</script>', html, re.S).group(1))["c"]
    for sid in VESSEL_IDS:
        assert sid in cal and cal[sid][0] in ("a", "v") and cal[sid][1] > 0
    assert cal["uterine_a_l"][0] == "a" and cal["uterine_v_l"][0] == "v"
    pdj = json.loads((d / "parts_data.json").read_text())
    assert pdj["counts"]["hra_organ_parts_q243"] == 18 and sum(1 for p in pdj["parts"] if p.get("q") == "q243") == 18
    assert (d / "symmetry_q237.json").exists() and (d / "index.html").read_text(encoding="utf-8") == html


def test_comb_f_and_base_f_pages_have_the_vessels():
    for key, n in (("comb_f", 15), ("base_f", 12)):
        html, d = _page(key)
        i = html.find("window.__ANATOMY_MANIFEST__=")
        man, _ = json.JSONDecoder().raw_decode(html[i + len("window.__ANATOMY_MANIFEST__="):])
        mine = [m for m in man["meshes"] if m["id"] in VESSEL_IDS]
        assert len(mine) == n and all(m["sys"] == "vessel" for m in mine)
        assert all((m.get("vt") == "v") == (not m["id"].endswith(("_a_l", "_a_r", "_a"))) for m in mine)
        assert all("SAME DONOR" in m["rec"]["procedural_badge"] for m in mine)
        cal = json.loads(re.search(r'id="nmsk-calibre">(.*?)</script>', html, re.S).group(1))["c"]
        assert all(m["id"] in cal for m in mine)
        assert json.loads((d / "parts_data.json").read_text())["counts"]["hra_organ_parts_q243"] == 18
