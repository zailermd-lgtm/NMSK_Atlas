"""Q235: the Imaging-based and Combined female pages with the Chinese Visible Human perineal / urethral structures (and the skipped Base page): reports, gates, ship diffs (0 unlisted), honesty of the cards, source class,
audit, browser check. Skips the parts whose build output is absent."""
import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
D = REPO / "data/derived"
PAGES = {
    "own_f": dict(report="Q235_report_own_f.json", diff="Q235_vertex_diff_f.json", dir="build/q235/viewer_f_hr", html="atlas_viewer_female.html", label="Imaging-based"),
    "comb_f": dict(report="Q235_report_comb_f.json", diff="Q235_vertex_diff_comb_f.json", dir="build/q235/viewer_zan_female", html="atlas_viewer_zan_female.html", label="Combined"),
}
ALL_IDS = {"clitoris_cavernous_body", "vestibular_bulb_l", "vestibular_bulb_r", "bartholin_gland_l", "bartholin_gland_r", "bulbospongiosus_cvh", "ischiocavernosus_cvh_l", "ischiocavernosus_cvh_r",
           "superficial_transverse_perineal_cvh", "deep_perineal_muscle_cvh", "urethral_sphincter_cvh", "urethral_sphincter_raphe_cvh", "urethral_compressor_cvh", "urethrovaginal_sphincter_cvh",
           "urethra_female_submucous_layer", "perineal_body", "urethra_female_lumen"}
ATTACH = {"ischiocavernosus_cvh_l", "ischiocavernosus_cvh_r", "clitoris_cavernous_body", "deep_perineal_muscle_cvh", "superficial_transverse_perineal_cvh", "urethral_sphincter_cvh", "urethral_compressor_cvh"}


def rj(name):
    p = D / name
    if not p.exists():
        pytest.skip(f"{name} not built")
    return json.loads(p.read_text())


@pytest.mark.parametrize("k", list(PAGES))
def test_every_shipped_structure_passed_every_gate(k):
    r = rj(PAGES[k]["report"])
    t = r["tolerances"]
    st = r["structures"]
    assert set(st) == ALL_IDS and set(r["shipped"]) | set(r["held"]) == ALL_IDS and not (set(r["shipped"]) & set(r["held"]))
    for sid in r["shipped"]:
        g = st[sid]["gates"]
        assert g["pass"] and g["fail_reasons"] == []
        assert g["vertices_outside_skin_envelope"] == 0 and g["skin_distance_min_mm"] >= t["skin_min_mm"]
        if sid in ATTACH:
            assert g["bone_min_mm"] >= t["bone_min_attach_mm"] - 1e-6 and g["max_move_out_of_bone_mm"] <= t["max_shift_mm"] and g["vertices_moved_out_of_bone"] <= t["max_shift_fraction"] * g["vertices"]
        else:
            assert g["bone_min_mm"] >= t["bone_min_free_mm"] and g["vertices_moved_out_of_bone"] == 0
        for organ, v in g["page_organ_overlap"].items():
            assert v["pct_deeper_than_tol"] <= t["soft_max_share_deeper_pct"], (sid, organ)
        assert st[sid]["info"]["closed"] and st[sid]["info"]["volume_cvh_cm3"] > 0
    for sid in r["held"]:
        assert st[sid]["gates"]["fail_reasons"]            # a held structure names why
    o = r["order_checks"]
    assert o["meatus_anterior_to_vaginal_wall_mm"] >= -t["soft_tolerance_mm"] and o["clitoral_body_anterior_to_meatus_mm"] > 0
    if k == "own_f":
        assert not r["held"]


def test_base_female_was_skipped_with_a_reason():
    r = rj("Q235_report_base_f.json")
    assert r["skipped_page"] and "not sound" in r["skipped_page"] and "male-derived" in r["skipped_page"]
    assert {"clitoris_cavernous_body", "ischiocavernosus_cvh_l", "ischiocavernosus_cvh_r"} & set(r["held"])      # the bone-attached structures fail on the male-derived pelvis
    assert r["inferior_pelvis_mm"]["p90"] > 6 and r["registration"]["transform"]["scale"] < 1.0


@pytest.mark.parametrize("k", list(PAGES))
def test_ship_diff_has_no_unlisted_change(k):
    d = rj(PAGES[k]["diff"])
    if k == "own_f":
        assert d["unlisted_changes"] == [] and d["problems"] == [] and d["removed"] == []
        assert sorted(d["added"]) == sorted(rj(PAGES[k]["report"])["shipped"]) and d["entries_new"] - d["entries_old"] == len(d["added"])
        assert d["bundle_bytes_added"] < 600_000
    else:
        assert d["unlisted"] == [] and d["geometry_changed"] == [] and d["removed"] == []
        assert sorted(d["added"]) == sorted(d["added_expected"]) and sorted(d["card_only"]) == sorted(d["card_only_expected"])
    # the card-only changes are the HRA structures' absence sentences (Q233 organs, Q234 vagina / ligaments / breasts)
    assert {"uterus", "vagina", "ovary_l"} <= set(d["card_only"]) and not any(i in ALL_IDS for i in d["card_only"])


def test_cards_are_honest_about_the_other_person_and_the_side():
    for k, c in PAGES.items():
        p = REPO / c["dir"] / c["html"]
        if not p.exists():
            pytest.skip("pages not built")
        t = p.read_text()
        assert "doi:10.1371/journal.pone.0132226" in t and "CC BY 4.0" in t and "Wu" in t and "Chinese Visible Human" in t
        assert "REAL SEGMENTATION OF ANOTHER PERSON" in t and "NOT segmented from this scan" in t
        assert "side assigned by registration; not determinable from the source" in t and "ASSIGNED BY THE REGISTRATION" in t
        assert "CAPPED" in t and "flat disc" in t                                               # the urethral lumen is capped and says so
        assert "third_party/cvh_wu2015 listed it as an 'open sheet' only because its triangle winding is inconsistent" in t
        assert "Q235 added" in t and "The vulva, labia, clitoris and the female urethra are not in the HRA set and are not built." not in " ".join(t.split())
        assert "the labia majora and minora, the mons pubis and the vulvar skin surface are not built" in " ".join(t.split()) or "are not in the CVH set and are not built" in " ".join(t.split())


def test_no_labia_no_cvh_skin_no_vaginal_wall_were_shipped():
    for k in PAGES:
        r = rj(PAGES[k]["report"])
        ids = " ".join(r["structures"])
        assert not re.search(r"labi|skin|mons|vaginal_wall|vagina_cvh|ovary|round_lig|ureter|bladder", ids), ids
        assert "vaginal wall (CVH 21) and the uterine / vaginal lumen (CVH 19)" in r["not_shipped_by_choice"]


def test_own_bundle_subject_class_and_template():
    b = REPO / "build/viewer_f_hr_q235/bundle.json"
    if not b.exists():
        pytest.skip("bundle not built")
    j = json.loads(b.read_text())
    subs = {s["id"]: s["subject"] for s in j["structures"]}
    assert all(subs[i] == "xfer_cvh2vhf_q235" for i in ALL_IDS if i in subs) and ALL_IDS <= set(subs)
    assert subs["vagina"] == "xfer_hra2vhf_q234" and subs["uterus"] == "xfer_hra2vhf_q233"
    assert any("Wu" in a and "doi:10.1371/journal.pone.0132226" in a for a in j["attribution"])
    t = (REPO / "viewer/atlas_viewer.template.html").read_text()
    assert re.search(r'^\s*xfer_cvh2vhf_q235: "', t, re.M)
    assert 'k:"registered_other_person"' in t and 'b.indexOf("xfer_cvh2") === 0) return "registered_other_person"' in t
    assert "Chinese Visible Human female (Wu et al. 2015, CC BY 4.0), registered onto this body, not segmented from this scan" in t
    # the existing 'Another person's CT' class (case s1159, hidden by default) is NOT reused: a different meaning
    assert 'k:"other_specimen"' in t and "NOT this body's geometry; hidden by default" in t


def test_page_dirs_have_the_unified_titles_and_index():
    for k, c in PAGES.items():
        d = REPO / c["dir"]
        if not d.exists():
            pytest.skip("pages not built")
        page = (d / c["html"]).read_bytes()
        assert (d / "index.html").read_bytes() == page
        title = re.search(rb"<title>(.*?)</title>", page).group(1).decode()
        assert c["label"] in title and "Female" in title and "Male" not in title.replace("male-derived", "")
        assert (d / "parts_data.json").exists()


def test_audit_counts_the_new_structures_as_present():
    a = rj("Q233_sex_audit.json")
    for k in ("own_f", "comb_f"):
        inv = a["pages"][k]["after_q233"]["inventory"]
        present = set(inv["female_only_present"])
        assert {"vagina", "clitoris", "vestibular_glands_bulb", "female_urethra"} <= present, k
        assert {"labia_majora", "labia_minora", "mons_pubis", "ovarian_vessels"} <= set(inv["female_only_absent"]), k
        for item in ("clitoris", "vestibular_glands_bulb", "female_urethra"):
            assert all("ANOTHER PERSON'S real segmentation" in h["provenance"] for h in inv["female_only_present"][item]), (k, item)
    b = a["pages"]["base_f"]["after_q233"]["inventory"]
    assert {"clitoris", "female_urethra", "vestibular_glands_bulb"} <= set(b["female_only_absent"])         # Base female: skipped, still absent
    assert any("Q235" in json.dumps(f) for f in a["fixes_applied"])


def test_browser_check_has_no_page_errors():
    r = rj("Q235_pagecheck.json")
    assert len(r) == 2
    for d, res in r.items():
        for dev, info in res.items():
            assert [e for e in info["errors"] if "net::ERR_FAILED" not in e] == [], (d, dev, info["errors"])
            assert info["scrollW"] <= info["innerW"], (d, dev)
            assert all(v is True for kk, v in info["expected_present"].items() if kk != "_structures_seen"), (d, dev, info["expected_present"])


def test_renders_were_saved():
    for n in ("own_f_perineum_inferior", "own_f_perineum_sagittal_midline", "comb_f_perineum_inferior", "comb_f_perineum_sagittal"):
        assert (D / f"Q235_render_{n}.png").exists()
