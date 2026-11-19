"""Q233 tests: sex-correctness audit schema + verdict fields, no male-only organ on the female pages, female organs on the Imaging-based female (and the two Z female pages), male genitalia on his page,
ship diffs (0 unlisted), registration / organ guards, wording, licence files. Tests that need the git-ignored build dirs skip when they are absent."""
import json, math, sys
from pathlib import Path
import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "anatomy"))
D = REPO / "data/derived"
AUDIT = json.loads((D / "Q233_sex_audit.json").read_text())
PAGES = ["own_m", "own_f", "base_m", "base_f", "comb_m", "comb_f"]
VERDICTS = {"male", "female", "ambiguous", "not_measurable"}
FEMALE_PAGES = ["own_f", "base_f", "comb_f"]
NEW_ORGANS = ["uterus", "ovary_l", "ovary_r", "uterine_tube_l", "uterine_tube_r"]


def test_audit_schema():
    assert AUDIT["schema"] == "q233_sex_audit_v1"
    for k in ("pages", "references", "q44_transfers", "zanatomy_female_search", "claims_audit", "fixes_applied", "cannot_be_fixed", "limits", "honest_names", "fat_distribution"):
        assert k in AUDIT, k
    assert list(AUDIT["pages"]) == PAGES
    for k, p in AUDIT["pages"].items():
        for st in ("before_q233", "after_q233"):
            s = p[st]
            for f in ("inventory", "wrong_sex_structures", "measures", "skeletal_overall", "structures", "raw_measures"):
                assert f in s, (k, st, f)
            for f in ("male_only_present", "female_only_present", "male_only_absent", "female_only_absent", "surface_patches"):
                assert f in s["inventory"]
        assert {"declared_sex", "skeleton", "subpubic_angle", "wrong_sex_after"} <= set(p["overall"])


def test_every_measure_has_reference_and_verdict_fields():
    for k, p in AUDIT["pages"].items():
        keys = [m["key"] for m in p["before_q233"]["measures"]]
        assert {"subpubic_angle", "greater_sciatic_notch", "ischiopubic_index", "sacral_index", "femoral_head_diameter", "bicondylar_breadth", "shoulder_to_hip", "q_angle", "breast_envelope"} <= set(keys)
        for m in p["before_q233"]["measures"]:
            assert m["verdict"] in VERDICTS, (k, m["key"], m["verdict"])
            for f in ("reference_male", "reference_female", "reference_status", "citation", "reliability", "note", "label", "unit"):
                assert f in m, (k, m["key"], f)


def test_subpubic_angle_verdicts_against_verified_numbers():
    sub = {k: [m for m in p["before_q233"]["measures"] if m["key"] == "subpubic_angle"][0] for k, p in AUDIT["pages"].items()}
    assert sub["own_m"]["verdict"] == "male" and sub["own_f"]["verdict"] == "female"
    assert sub["base_m"]["verdict"] == "male" and sub["base_f"]["verdict"] == "male"          # the Base female IS the male body
    assert sub["comb_m"]["verdict"] == "male"
    assert sub["comb_f"]["verdict"] == "male"                                                 # Z male-derived bones fitted to her keep a male-range angle
    assert sub["own_f"]["reference_status"] == "verified_abstract"
    assert abs(sub["own_f"]["value"] - 87.4) < 6.5 and abs(sub["own_m"]["value"] - 68.6) < 7.6


def test_base_female_skeleton_identical_to_base_male():
    a, b = AUDIT["pages"]["base_m"]["before_q233"]["raw_measures"], AUDIT["pages"]["base_f"]["before_q233"]["raw_measures"]
    for k in ("subpubic_angle_deg", "bi_iliac_breadth_mm", "intertuberous_mm", "sciatic_notch_hull_angle_deg", "ischiopubic_index", "femoral_head_diameter_r_mm"):
        assert a[k] == b[k], k
    # Q250 rebuilt the Base female (a female skeleton target): the audit now names it 'Base . Female'; the Q233 'before' measures above stay the historical record
    assert AUDIT["honest_names"]["base_f"] in ("Base · Female", "Base · Female (male-derived body)")
    assert AUDIT["pages"]["base_f"]["before_q233"]["skeletal_overall"]["verdict"].startswith("mostly male")


def test_no_male_only_organ_on_female_pages_and_no_female_organ_on_male_pages():
    for k in FEMALE_PAGES:
        for st in ("before_q233", "after_q233"):
            inv = AUDIT["pages"][k][st]["inventory"]["male_only_present"]
            assert not [i for i in inv if i != "male_urethra"], (k, st, list(inv))
            assert not AUDIT["pages"][k][st]["wrong_sex_structures"], (k, st)
    for k in ("own_m", "base_m", "comb_m"):
        for st in ("before_q233", "after_q233"):
            assert not AUDIT["pages"][k][st]["inventory"]["female_only_present"], (k, st)
            assert not AUDIT["pages"][k][st]["wrong_sex_structures"], (k, st)


def test_female_organs_present_after_q233_on_all_three_female_pages():
    for k in FEMALE_PAGES:
        inv = AUDIT["pages"][k]["after_q233"]["inventory"]["female_only_present"]
        assert {"uterus", "ovary", "uterine_tube"} <= set(inv), (k, list(inv))
        ids = {h["id"] for hs in inv.values() for h in hs}
        assert set(NEW_ORGANS) <= ids, (k, ids)
        for hs in inv.values():     # Q233 organs: reference organs of the same donor; Q234 additions (vagina, ligaments, breasts): HRA objects / sculpted reference model (never "measured")
            assert all(("HRA reference organ of the SAME donor" in h["provenance"]) or ("HRA" in h["provenance"] and "not measured" in h["provenance"]) or ("ANOTHER PERSON'S real segmentation" in h["provenance"] and "Chinese Visible Human" in h["provenance"]) for h in hs)       # Q235: the CVH structures of the Imaging-based / Combined pages
    for k in FEMALE_PAGES:      # before: none of the three had any
        assert not AUDIT["pages"][k]["before_q233"]["inventory"]["female_only_present"], k
    absent = AUDIT["pages"]["own_f"]["after_q233"]["inventory"]["female_only_absent"]
    assert "vagina" not in absent and {"labia_majora", "labia_minora", "mons_pubis", "ovarian_vessels"} <= set(absent)       # Q234 added the vagina; the labia etc. stay honestly absent, not invented
    assert not ({"clitoris", "female_urethra", "vestibular_glands_bulb"} & set(absent))                                    # Q235 added them on the Imaging-based page from the Chinese Visible Human (another person)
    # Q251: base_f is no longer skipped outright by Q235 (its Q250-warped pelvis fits the CVH ischiopubic arch well
    # enough for most of the CVH perineal structures); female_urethra and vestibular_glands_bulb now ship there too.
    # Only the clitoris remains absent (clitoris_cavernous_body stays held: a real ~5 mm bone penetration on this
    # page's pelvis that is not fixable without fabricating geometry).
    assert {"labia_majora", "labia_minora", "clitoris"} <= set(AUDIT["pages"]["base_f"]["after_q233"]["inventory"]["female_only_absent"])
    assert "female_urethra" in set(AUDIT["pages"]["base_f"]["after_q233"]["inventory"]["female_only_present"])


def test_male_genitalia_on_his_own_page():
    inv = AUDIT["pages"]["own_m"]["after_q233"]["inventory"]["male_only_present"]
    assert {"testis", "epididymis", "ductus_deferens", "seminal_vesicle", "prostate", "penis_corpora_glans"} <= set(inv)
    assert list(AUDIT["pages"]["own_m"]["before_q233"]["inventory"]["male_only_present"]) == ["prostate"]
    assert all("Z-Anatomy" in h["provenance"] or "measured" in h["provenance"] for hs in inv.values() for h in hs)


@pytest.mark.parametrize("which", ["f", "m", "comb_f", "base_f"])
def test_ship_diff_zero_unlisted(which):
    d = json.loads((D / f"Q233_vertex_diff_{which}.json").read_text())
    assert d.get("unlisted_changes", d.get("unlisted")) == []
    assert d.get("problems", []) == []
    if which == "f":
        assert [r["id"] for r in d["removed"]] == ["coccyx"] and d["removed"][0]["subject"] == "xfer_vhm2vhf"
        assert sorted(d["added"]) == sorted(NEW_ORGANS) and d["card_only"] == ["sacrum"]
        assert d["entries_new"] == d["entries_old"] - 1 + 5
    elif which == "m":
        assert len(d["added"]) == 14 and d["removed"] == [] and d["identical"] == d["entries_old"]
    else:
        assert sorted(d["added"]) == sorted(NEW_ORGANS) and d["removed"] == [] and d["geometry_changed"] == []
        assert sorted(d["card_only"]) == sorted(d["card_only_expected"])


def test_registration_and_organ_guards():
    reg = json.loads((D / "Q233_hra_to_vhf_transform.json").read_text())
    R = np.array(reg["rotation"])
    assert abs(np.linalg.det(R) - 1) < 1e-4 and np.allclose(R @ R.T, np.eye(3), atol=1e-4)
    assert 0.9 < reg["scale"] < 1.0 and reg["residual_mm"]["median"] < 2.0 and reg["residual_mm"]["rms"] < 3.0
    rep = json.loads((D / "Q233_report_own_f.json").read_text())
    assert set(rep["organs"]) == set(NEW_ORGANS)
    vol = {k: v["gates"]["volume_cm3"] for k, v in rep["organs"].items()}
    assert 10 < vol["uterus"] < 60 and all(0.2 < vol[k] < 5 for k in ("ovary_l", "ovary_r")) and all(0.1 < vol[k] < 3 for k in ("uterine_tube_l", "uterine_tube_r"))
    for k, v in rep["organs"].items():
        g = v["gates"]
        assert g["pass"] and g["inside_skin"] and g["bone_min_mm"] >= 0.5 and g["overlap_total_pct"] <= 5.0 and g["watertight"], k
        assert v["envelope"]["closed_surface_to_source_mm"]["p95"] < 1.0, k
    for which in ("comb_f", "base_f"):
        r = json.loads((D / f"Q233_report_{which}.json").read_text())
        for k, v in r["organs"].items():
            assert v["gates"]["bone_min_mm"] >= 0.5 and v["gates"]["skin_distance_min_mm"] >= 20 and not v.get("held"), (which, k)
    rb = json.loads((D / "Q233_report_base_f.json").read_text())["registration"]
    assert rb["residual_mm"]["median"] < 4 and rb["scale"] < 1.0


def test_male_fill_guards():
    rep = json.loads((D / "Q233_report_own_m.json").read_text())
    for k, v in rep["organs"].items():
        g = v["gates"]
        assert not v.get("held"), k
        assert g["inside_skin_pct"] >= 99.0 and g["bone_min_mm"] >= 0.5, (k, g)
    assert rep["subject"].startswith("xfer_zan2vhm")           # Source class 'Filled from Z-Anatomy' in the template's classifier


def test_hra_files_and_licence():
    d = REPO / "third_party/hra_vh_f"
    for n in ("VH_F_Uterus", "VH_F_Ovary_L", "VH_F_Ovary_R", "VH_F_Fallopian_Tube_L", "VH_F_Fallopian_Tube_R", "VH_F_Pelvis"):
        assert (d / f"{n}.glb").stat().st_size > 1000
    t = (d / "NOTICE.md").read_text()
    assert "CC BY 4.0" in t and "b036a91aaf7234f462b1249d4a5f4fb0e982f412" in t and "Visible Human" in t


def test_wording_is_honest_about_the_base_female():
    b = (REPO / "scripts/zanatomy/build_zan_atlas_viewer.py").read_text()
    # Q250 rewrote the Base female wording (deformed onto a female skeleton); the Q233 'NOT a female body' sentence is superseded and the honest limits are in the new text
    assert "DEFORMS that body onto a FEMALE skeleton" in b and "not an average woman" in b and "male-derived" in b
    assert "No female reproductive organs are shown and none were invented" not in b and "No female reproductive organs are shown:" not in b
    assert "HuBMAP" in b
    t = (REPO / "scripts/set_titles_q231.py").read_text()
    assert '"atlas_viewer_base_female.html": "Base · Female",' in t         # Q250: the name no longer carries '(male-derived body)'; the page intro and the cards say how the body was made


def test_zanatomy_search_is_recorded():
    z = AUDIT["zanatomy_female_search"]
    assert z["answer"].startswith("NO") and "TO-DO" in z["answer"]
    txt = json.dumps(z)
    for needle in ("e214005da8dc0a226176165f0a4d4e32f2155e0f", "7,184 objects", "parts_list_e.txt", "z-anatomy.com", "VH_F_Uterus"):
        assert needle in txt, needle
    assert "what_the_owner_would_need_to_provide" in z


def test_references_are_pubmed_abstracts():
    assert len(AUDIT["references"]) >= 15
    for r in AUDIT["references"]:
        assert r["pmid"].isdigit() and r["verified"].startswith("abstract")
    assert any(r["pmid"] == "32274246" and "68.6" in r["values"] and "87.4" in r["values"] for r in AUDIT["references"])


def test_q44_listing_and_sex_specific_review():
    t = AUDIT["q44_transfers"]
    assert "coccyx" in t["listing"]["own_f"]["xfer_vhm2vhf"]
    assert any(x["id"] == "coccyx" and x["sex_specific"] and x["action"].startswith("REMOVED") for x in t["sex_specific_review"]["own_f"])


def test_geometry_helpers_on_synthetic_shapes():
    import trimesh
    from scripts.anatomy.q233 import dimorphism as DM
    from scripts.anatomy.q233 import hra_register as H
    rng = np.random.default_rng(1)
    c0 = np.array([3.0, -2.0, 5.0]); r0 = 23.0
    P = rng.normal(size=(2000, 3)); P = c0 + r0 * P / np.linalg.norm(P, axis=1)[:, None]
    c, r, rms = DM.fit_sphere(P)
    assert np.allclose(c, c0, atol=1e-6) and abs(r - r0) < 1e-6
    sph = trimesh.creation.icosphere(subdivisions=3, radius=10.0)
    top, bot = sph.vertices[:, 1] >= 0, None
    f = sph.faces
    cy = sph.vertices[f][:, :, 1].mean(axis=1)
    up, lo = f[cy >= 0], f[cy < 0]
    parts = [("a", sph.vertices, up), ("b", sph.vertices, lo)]            # two OPEN hemispheres whose union is the sphere
    V, F, info = H.closed_surface(parts, pitch=0.5, close_it=2)
    assert info["watertight"] and info["components"] == 1
    assert abs(info["volume_cm3"] * 1000 - 4 / 3 * math.pi * 1000) / (4 / 3 * math.pi * 1000) < 0.06
    # registration on a rotated + scaled copy
    A = rng.normal(size=(500, 3)) * [30, 20, 10]
    th = 0.4; Rz = np.array([[math.cos(th), -math.sin(th), 0], [math.sin(th), math.cos(th), 0], [0, 0, 1]])
    B = 1.07 * A @ Rz.T + [5, -3, 2]
    s, R, t = H.umeyama(A, B)
    assert abs(s - 1.07) < 1e-6 and np.allclose(R, Rz, atol=1e-6) and np.allclose(t, [5, -3, 2], atol=1e-5)


def test_final_pages_if_built():
    b = REPO / "build/q233"
    if not (b / "viewer_f_hr/index.html").exists():
        pytest.skip("build/q233 not present")
    sys.path.insert(0, str(REPO))
    from scripts.zanatomy import q205_pages as P5
    for d, stem in (("viewer_zan_female", "atlas_viewer_zan_female"), ("viewer_base_female", "atlas_viewer_base_female")):
        man, blob = P5.load_page(b / d, stem)
        by = {m["id"]: m for m in man["meshes"]}
        assert set(NEW_ORGANS) <= set(by) and all(by[i]["sys"] == "viscera" for i in NEW_ORGANS)
        assert "HuBMAP Human Reference Atlas" in man["attribution"]
        assert "SAME DONOR" in by["uterus"]["rec"]["procedural_badge"]
        assert not any(i in by for i in ("zan_testis_l", "zan_prostate", "zan_glans_penis"))
    html = (b / "viewer_base_female/atlas_viewer_base_female.html").read_text(encoding="utf-8")
    assert "<title>NMSK Atlas — Base · Female (male-derived body)</title>" in html and "NOT a female body" in html
    for d in b.glob("_verify/*.json"):
        assert json.loads(d.read_text())["OK"], d.name
    own = json.loads((REPO / "build/viewer_f_hr_q233/bundle.json").read_text())
    ids = [e["id"] for e in own["structures"]]
    assert set(NEW_ORGANS) <= set(ids) and "coccyx" not in ids
    assert {e["subject"] for e in own["structures"] if e["id"] in NEW_ORGANS} == {"xfer_hra2vhf_q233"}
