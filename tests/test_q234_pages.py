"""Q234: the three female pages with the HRA vagina / ligaments / breasts: reports, ship diffs (0 unlisted), page dirs, honesty of the cards, audit, browser check. Skips the parts whose build output is absent."""
import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
D = REPO / "data/derived"
PAGES = {
    "own_f": dict(report="Q234_report_own_f.json", diff="Q234_vertex_diff_f.json", dir="build/q234/viewer_f_hr", html="atlas_viewer_female.html", label="Imaging-based"),
    "comb_f": dict(report="Q234_report_comb_f.json", diff="Q234_vertex_diff_comb_f.json", dir="build/q234/viewer_zan_female", html="atlas_viewer_zan_female.html", label="Combined"),
    "base_f": dict(report="Q234_report_base_f.json", diff="Q234_vertex_diff_base_f.json", dir="build/q234/viewer_base_female", html="atlas_viewer_base_female.html", label="Base"),
}
PELVIC = {"vagina", "round_ligament_uterus_l", "round_ligament_uterus_r", "uterosacral_ligament_l", "uterosacral_ligament_r", "cardinal_ligament_uterus_l", "cardinal_ligament_uterus_r", "broad_ligament_uterus",
          "ovarian_ligament_l", "ovarian_ligament_r", "suspensory_ligament_ovary_l", "suspensory_ligament_ovary_r", "mesosalpinx_l", "mesosalpinx_r", "mesovarium_l", "mesovarium_r"}
BREAST_KINDS = ("breast_fat", "mammary_gland", "lactiferous_ducts", "areola", "nipple", "breast_suspensory_ligaments")


def rj(name):
    p = D / name
    if not p.exists():
        pytest.skip(f"{name} not built")
    return json.loads(p.read_text())


@pytest.mark.parametrize("k", list(PAGES))
def test_report_gates_and_what_was_held(k):
    r = rj(PAGES[k]["report"])
    st = r["structures"]
    assert PELVIC <= set(st)
    for sid in PELVIC:
        v = st[sid]
        if v.get("held"):
            continue
        g = v["gates"]
        assert g["pass"] and g["bone_min_mm"] >= 0.25 and g["skin_distance_min_mm"] >= 8
    # a breast is shipped whole or not at all
    for side in "lr":
        parts = [st[f"{b}_{side}"] for b in BREAST_KINDS]
        held = [bool(p.get("held")) for p in parts]
        assert all(held) or not any(held), (k, side)
        if not any(held):
            for p in parts:
                g = p["gates"]
                assert g["pass"] and g["skin_inside_min_mm"] >= 0.0 and g["pectoralis_major_min_mm"] >= -1.0 and g["bone_min_mm"] >= 1.0, (k, side)
        else:
            assert "held_reason" in parts[0]["gates"] and r["warp"][side]["ratio_median"] is not None
    if k == "own_f":
        assert not any(v.get("held") for v in st.values())       # everything is on the Imaging-based page
        fat = {s: st[f"breast_fat_{s}"]["gates"] for s in "lr"}
        assert all(fat[s]["volume_cm3"] / fat[s]["volume_hra_cm3"] >= 0.25 for s in "lr")
        assert fat["l"]["skin_inside_min_mm"] >= 1.0 and fat["r"]["pectoralis_major_min_mm"] > 0


@pytest.mark.parametrize("k", list(PAGES))
def test_ship_diff_has_no_unlisted_change(k):
    d = rj(PAGES[k]["diff"])
    if k == "own_f":
        assert d["unlisted_changes"] == [] and d["problems"] == [] and d["removed"] == [] and d["entries_new"] - d["entries_old"] == len(d["added"])
        assert sorted(d["card_only"]) == sorted(["uterus", "ovary_l", "ovary_r", "uterine_tube_l", "uterine_tube_r"])
        assert d["bundle_bytes_added"] < 1_300_000                                  # bundle growth stays modest (raw bytes)
    else:
        assert d["unlisted"] == [] and d["geometry_changed"] == [] and d["removed"] == []
        assert sorted(d["added"]) == sorted(d["added_expected"]) and sorted(d["card_only"]) == sorted(d["card_only_expected"])
    assert PELVIC <= set(d["added"]) or any(h for h in rj(PAGES[k]["report"])["structures"].values() if h.get("held"))


def test_breast_cards_say_they_are_a_sculpted_reference_model():
    for k in PAGES:
        p = REPO / PAGES[k]["dir"] / PAGES[k]["html"]
        if not p.exists():
            pytest.skip("pages not built")
        t = p.read_text()
        assert "ccf-3d-reference-object-library" in t and "f1a3a63f110e27ff0736047d52d04dba5d3087f9" in t        # CC BY 4.0 attribution on the page
        assert "VH_F_mammary_gland_L/R" in t and "sculpted from scratch" in t
        r = rj(PAGES[k]["report"])
        if not r["structures"]["breast_fat_l"].get("held"):
            assert "REFERENCE MODEL, NOT donor data" in t and "FITTED INTO THE SKIN ENVELOPE" in t
        assert "added in Q234 as separate structures" in t or "were added in Q234" in t               # the Q233 organs no longer say the vagina / ligaments are absent
        assert "NOT in the HRA set and not built" not in t and "NOT in the HRA set and are not drawn" not in t


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
    t = (REPO / PAGES["base_f"]["dir"] / PAGES["base_f"]["html"]).read_text()
    assert "male-derived body" in t


def test_own_bundle_subjects_and_class():
    b = REPO / "build/viewer_f_hr_q234/bundle.json"
    if not b.exists():
        pytest.skip("bundle not built")
    j = json.loads(b.read_text())
    subs = {s["id"]: s["subject"] for s in j["structures"]}
    assert subs["vagina"] == "xfer_hra2vhf_q234" and subs["uterosacral_ligament_l"] == "xfer_hra2vhf_q234"
    assert subs["breast_fat_l"] == subs["nipple_r"] == "xfer_hrasculpt2vhf_q234"
    assert subs["uterus"] == "xfer_hra2vhf_q233"
    # every Q234 subject has a label in the own template (the Source facet and the card line read it)
    t = (REPO / "viewer/atlas_viewer.template.html").read_text()
    for s in set(subs.values()):
        if "q234" in s:
            assert re.search(r"^\s*" + s + r': "', t, re.M)


def test_audit_counts_the_new_structures_as_present():
    a = rj("Q233_sex_audit.json")
    for k in ("own_f", "comb_f", "base_f"):
        after = a["pages"][k]["after_q233"]["inventory"]
        present = set(after["female_only_present"])
        assert {"vagina", "uterine_ovarian_ligaments"} <= present, k
        if k == "base_f":
            # Q251: base_f ships most CVH perineal structures too now (Q250's pelvis warp fits well enough); only
            # the clitoris remains absent (clitoris_cavernous_body stays held: a real bone penetration there).
            assert {"labia_majora", "labia_minora", "clitoris"} <= set(after["female_only_absent"]), k
            assert {"female_urethra", "vestibular_glands_bulb"} <= present, k
        else:       # Q235: the Imaging-based and Combined pages got the clitoris, vestibular bulbs / glands and the female urethra from the Chinese Visible Human; the labia, mons pubis, ovarian vessels stay absent
            assert {"labia_majora", "labia_minora", "mons_pubis", "ovarian_vessels"} <= set(after["female_only_absent"]), k
            assert {"clitoris", "female_urethra", "vestibular_glands_bulb"} <= present, k
        rep_name = PAGES[k]["report"]
        if k == "base_f" and (REPO / "data/derived/Q250_chain_Q234_report_base_f.json").exists() and (json.loads((D / "Q233_sex_audit.json").read_text()).get("q250")):
            rep_name = "Q250_chain_Q234_report_base_f.json"          # Q250 rebuilt the Base female (female chest envelope: the breasts ship); the Q234 original report stays the historical record
        held_breast = rj(rep_name)["structures"]["breast_fat_l"].get("held")
        assert ("mammary_gland" in present) != bool(held_breast), k
    assert any("Q234" in json.dumps(f) for f in a["fixes_applied"])


def test_browser_check_has_no_page_errors():
    r = rj("Q234_pagecheck.json")
    for d, res in r.items():
        for dev, info in res.items():
            assert [e for e in info["errors"] if "net::ERR_FAILED" not in e] == [], (d, dev, info["errors"])      # ERR_FAILED = the Google-Fonts request the harness aborts
            assert info["scrollW"] <= info["innerW"], (d, dev)
            assert all(v is True for kk, v in info["expected_present"].items() if kk != "_structures_seen"), (d, dev, info["expected_present"])


def test_renders_were_saved():
    for n in ("own_f_breast_front", "own_f_breast_l_sagittal", "own_f_pelvis_front"):
        assert (D / f"Q234_render_{n}.png").exists()
