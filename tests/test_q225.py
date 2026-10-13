"""Q225: Z-fitted pages -- left-elbow bones re-seated (ulna / radius on the humerus by joint congruency), patellae re-seated on the femoral trochlea, floating ribs on their vertebra, wrist / shoulder soft tissue
carried (tear relaxation), clinical files of the female page regenerated.  Synthetic tests of the helpers (signed-distance field, pair report, tapered rigid correction, re-seat of two toy bars, guards) and, when
the Q225 pages are built, the page-level guards: ship-diff scope (0 unlisted), exact bone-bone penetration <= 1 mm at the left elbow / patellae / floating ribs, joint space vs the base model, per-bone fit error in
the card badge, the wrist tears down, the cards, the final pages with parts_data.json, the female clinical files (and none for the male)."""
import json
import re
import sys
from pathlib import Path

import numpy as np
import pytest
import trimesh

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.zanatomy import q225_core as K5  # noqa: E402
from scripts.zanatomy import q225_elbow as EL  # noqa: E402
from scripts.zanatomy import q225_joint as J  # noqa: E402

DER = REPO / "data" / "derived"
FIT = {"male": REPO / "build" / "q225_fit" / "viewer_zan_vhm", "female": REPO / "build" / "q225_fit" / "viewer_zan_female"}
FINAL = {"male": REPO / "build" / "q225" / "viewer_zan_vhm", "female": REPO / "build" / "q225" / "viewer_zan_female"}
STEM = {"male": "atlas_viewer_zan_male_fitted", "female": "atlas_viewer_zan_female"}
SHIP = {w: DER / f"Q225_ship_diff_{w}.json" for w in FIT}
built = pytest.mark.skipif(not all((FIT[w] / f"{STEM[w]}.html").exists() and SHIP[w].exists() for w in FIT), reason="Q225 pages not built")
final = pytest.mark.skipif(not ((FINAL["male"] / f"{STEM['male']}.html").exists() and (FINAL["female"] / "index.html").exists()), reason="Q225 final pages not built")


def box(c, size):
    m = trimesh.creation.box(extents=size)
    m.apply_translation(c)
    return np.asarray(m.vertices, float), np.asarray(m.faces, np.int64)


# ------------------------------------------------------------------------------------------------ synthetic
def test_sdf_is_negative_inside_positive_outside_and_measures_distance():
    v, f = box((0, 0, 0), (20, 20, 20))
    s = J.Sdf(v, f, pad=10.0, h=1.0)
    assert s(np.array([[0.0, 0, 0]]))[0] < -8.0            # deep inside
    assert abs(s(np.array([[14.0, 0, 0]]))[0] - 4.0) < 1.0       # 4 mm outside the face at x = 10
    assert s(np.array([[60.0, 0, 0]]))[0] > 40.0                   # far outside: keeps growing


def test_pair_report_overlap_and_gap():
    va, fa = box((0, 0, 0), (20, 20, 20))
    vb, fb = box((17, 0, 0), (20, 20, 20))               # overlaps by 3 mm
    r = J.pair_report(va, fa, vb, fb, sdf_a=J.Sdf(va, fa, h=0.5), sdf_b=J.Sdf(vb, fb, h=0.5))
    assert -4.0 <= r["min_clearance_mm"] < -1.5          # surface samples of b are up to 3 mm deep in a (a box has few vertices: the vertex rule sees only its corners)
    vc, fc = box((24, 0, 0), (20, 20, 20))               # 4 mm gap
    r2 = J.pair_report(va, fa, vc, fc, sdf_a=J.Sdf(va, fa, h=0.5), sdf_b=J.Sdf(vc, fc, h=0.5))
    assert r2["max_depth_mm"] == 0.0 and abs(r2["min_clearance_mm"] - 4.0) < 0.8 and abs(r2["patch_p05_mm"] - 4.0) < 0.8


def test_taper_correction_is_zero_beyond_its_length_and_full_at_the_joint_end():
    v, _ = box((0, 50, 0), (10, 100, 10))                # a bar along y, joint end at y = 0
    tp = EL.Taper(v, np.array([0.0, 0, 0]), taper=0.4)
    par = np.array([2.0, 3.0, 1.0, 0.02, -0.01, 0.03])
    d = tp.disp(v, par)
    t = (v[:, 1] - v[:, 1].min()) / 100.0
    assert np.allclose(d[t > 0.4], 0.0)                                   # the far end is not touched
    assert np.linalg.norm(d[t < 0.01] - par[:3], axis=1).max() < 1.0     # full correction at the joint end (rotation about its centre adds < 1 mm here)
    rigid = EL.Taper(v, np.array([0.0, 0, 0]), taper=0.4, rigid=True)
    assert np.allclose(rigid.weight(v), 1.0)


def test_reseat_separates_two_overlapping_toy_bones_and_keeps_the_far_end():
    # fixed 'humerus' block; moving 'ulna' bar whose joint end overlaps it by 6 mm; base joint space 1.5 mm
    hv, hf = box((0, 0, 0), (30, 30, 30))
    uv, uf = box((0, 15 + 70 - 6, 0), (14, 140, 14))     # joint end at y = 15 - 6 + ... overlaps the block top
    gaps = {("hum", "uln"): 1.5}
    bones = {"hum": (hv, hf), "uln": (uv, uf)}
    R = EL.reseat(bones, {}, gaps, np.array([0.0, 15.0, 0.0]), ["uln"], ["hum"], dict(taper=0.5, w_reg=0.05, w_pull=2.0, floor_frac=0.8), log=lambda *a: None)
    jb, ja = list(R["report"]["joint_before"].values())[0], list(R["report"]["joint_after"].values())[0]
    assert jb["max_penetration_mm"] >= 3.0
    assert ja["max_penetration_mm"] <= 1.0
    assert abs(ja["joint_space_p05_mm"] - 1.5) <= 1.5
    far = np.argmax(uv[:, 1])
    assert np.linalg.norm(R["W"]["uln"][uv[:, 1] > uv[:, 1].max() - 20] - uv[uv[:, 1] > uv[:, 1].max() - 20], axis=1).max() < 0.5      # wrist end untouched


def test_guard_helpers():
    from scripts.zanatomy import q225_build as B
    v, f = box((0, 0, 0), (10, 10, 10))
    assert abs(B.mesh_volume(v, f) - 1000.0) < 1e-6
    lo, hi = B.edge_stretch(v, v * 1.1, f)
    assert abs(lo - 1.1) < 1e-6 and abs(hi - 1.1) < 1e-6
    assert B.GUARDS["max_penetration_mm"] <= 1.0 and B.GUARDS["volume_ratio"][0] > 0.9 and B.GUARDS["volume_ratio"][1] < 1.12


def test_dense_own_tree_sees_triangle_interiors():
    v, f = box((0, 0, 0), (40, 40, 40))
    t = EL.own_tree(v, f, spacing=2.0)
    assert t.query(np.array([[0.0, 0.0, 20.0]]))[0][0] < 2.5          # centre of a 40 mm face: its vertices are 28 mm away


# ------------------------------------------------------------------------------------------------ built pages
EXPECTED_BONES = {"ulna_l", "radius_l", "patella_l", "patella_r", "zan_eleventh_rib_l", "zan_eleventh_rib_r", "zan_twelfth_rib_l", "zan_twelfth_rib_r", "zan_second_rib_l"}
MEAS = {w: DER / f"Q225_bone_measures_{w}_q225.json" for w in FIT}
MEAS0 = {w: DER / f"Q225_bone_measures_{w}_src.json" for w in FIT}
BA = {w: DER / f"Q225_before_after_{w}.json" for w in FIT}


def pr(d, k):
    a, b = k.split("|")
    return d.get(k) or d.get(f"{b}|{a}")


@built
@pytest.mark.parametrize("which", ["male", "female"])
def test_ship_diff_scope_zero_unlisted(which):
    r = json.loads(SHIP[which].read_text())
    assert r["geometry_changed_but_not_listed"] == [] and r["added"] == [] and r["removed"] == [] and r["card_only"] == []
    assert r["unchanged"] > 2500
    changed = set(r["geometry_changed"])
    assert changed == set(r["stages"])                                     # every listed structure changed, every changed one is listed
    pg = K5.load(which, src=FIT[which])
    sysd = {i: pg.sys(i) for i in changed}
    assert not [i for i, s in sysd.items() if s == "skin"]                 # skin untouched (byte identical)
    bones = {i for i, s in sysd.items() if s == "bone"}
    assert bones == EXPECTED_BONES - ({"zan_second_rib_l"} if which == "male" else set())


@built
@pytest.mark.parametrize("which", ["male", "female"])
def test_every_changed_card_carries_numbers_and_bone_cards_the_exact_check(which):
    r = json.loads(SHIP[which].read_text())
    pg = K5.load(which, src=FIT[which])
    for i in r["geometry_changed"]:
        badge = (pg.S[i]["m"].get("rec") or {}).get("procedural_badge", "")
        assert "Q225" in badge, i
        if pg.sys(i) == "bone":
            assert "Exact bone-bone check" in badge and "Rule-based, nothing invented" in badge, i
            if i in ("ulna_l", "radius_l"):
                assert "joint space on the unfitted base model" in badge and "Fit error to" in badge, i
        else:
            assert "Before -> after" in badge or "Before (published page) -> after" in badge, i


@built
@pytest.mark.parametrize("which", ["male", "female"])
def test_left_elbow_bones_no_longer_interpenetrate_and_have_a_joint_space(which):
    a, b = json.loads(MEAS[which].read_text())["pairs"], json.loads(MEAS0[which].read_text())["pairs"]
    for k in ("humerus_l|ulna_l", "humerus_l|radius_l", "radius_l|ulna_l"):
        assert pr(b, k)["max_penetration_mm"] >= 2.5, k                      # the defect existed
        assert pr(a, k)["max_penetration_mm"] <= 1.0, k                      # the exact (0.5 mm solid) penetration is one lattice step at most
        sp = pr(a, k)["joint_space_p05_mm"]
        assert sp is not None and 0.3 <= sp <= 5.5, k                         # a joint space (base model 0.8 / 4.6 / 1.6 mm), not a gap of centimetres


@built
@pytest.mark.parametrize("which", ["male", "female"])
def test_patellae_and_floating_ribs_sit_on_their_bones(which):
    a, b = json.loads(MEAS[which].read_text())["pairs"], json.loads(MEAS0[which].read_text())["pairs"]
    pats = [k for k in a if "patella" in k]
    assert len(pats) == 2
    for k in pats:
        assert pr(b, k)["min_clearance_mm"] > 8.0 and pr(a, k)["min_clearance_mm"] < 3.0 and pr(a, k)["max_penetration_mm"] <= 1.0
    ribs = [k for k in a if "rib" in k]
    assert len(ribs) == (5 if which == "female" else 4)
    for k in ribs:
        assert pr(b, k)["min_clearance_mm"] > 5.5 and pr(a, k)["min_clearance_mm"] < 1.5 and pr(a, k)["max_penetration_mm"] <= 1.0


@built
@pytest.mark.parametrize("which", ["male", "female"])
def test_bone_moves_are_bounded_and_the_wrist_end_is_untouched(which):
    r = json.loads(SHIP[which].read_text())
    pgb, pga = K5.load(which), K5.load(which, src=FIT[which])
    for n in EXPECTED_BONES - ({"zan_second_rib_l"} if which == "male" else set()):
        d = np.linalg.norm(pga.v(n) - pgb.v(n), axis=1)
        assert d.max() <= 20.0 and d.max() > 0.5, n
        if n in ("ulna_l", "radius_l"):
            v = pgb.v(n)
            c = v.mean(0)
            ax = np.linalg.svd(v - c, full_matrices=False)[2][0]
            t = (v - c) @ ax
            lo, hi = d[t < t.min() + 0.38 * (t.max() - t.min())].max(), d[t > t.min() + 0.62 * (t.max() - t.min())].max()
            assert min(lo, hi) < 0.2                                           # one end of the bone is not moved at all (the wrist end)
    m = json.loads((DER / f"Q225_moved_{which}.json").read_text())["all_changed"]
    assert all(v["max_mm"] <= 40.0 for k, v in m.items() if v["sys"] != "bone")


@pytest.mark.skipif(not all(p.exists() for p in BA.values()), reason="Q225 before/after not built")
@pytest.mark.parametrize("which", ["male", "female"])
def test_wrist_tears_and_junction_numbers_improved_no_new_majors(which):
    d = json.loads(BA[which].read_text())
    fs = d["fit_seams_q198"]
    for jn in ("wrist_l", "wrist_r"):
        assert fs["after"][jn]["frac_gt5"] < fs["before"][jn]["frac_gt5"] - 0.2, jn
    assert fs["after"]["elbow_l"]["frac_gt5"] <= max(fs["before"]["elbow_l"]["frac_gt5"] + 0.06, 0.08)      # carried soft tissue: male 0.2 -> 5 % of pairs > 5 mm (Q217 = 0.2 %), female 14 -> 3 %
    assert fs["after"]["elbow_l"]["tear_max_mm"] <= fs["before"]["elbow_l"]["tear_max_mm"] + 1.0
    sev = d["q198_junction_audit"]["severity_major_moderate_minor"]
    assert sev["q225_after"][0] <= sev["q223_before"][0]                       # no new junction majors
    j = {(x["junction"], x["side"]): x for x in d["q198_junction_audit"]["junctions_after"]}
    jb = {(x["junction"], x["side"]): x for x in d["q198_junction_audit"]["junctions_before"]}
    for key in (("elbow", "l"), ("knee", "l"), ("knee", "r")):
        assert j[key]["bone_penetration_mm_now"] <= max(jb[key]["bone_penetration_mm_now"], 1.5) + 0.01, key


@final
def test_final_pages_carry_parts_sidecar_and_the_right_clinical_files():
    for w in FINAL:
        p = json.loads((FINAL[w] / "parts_data.json").read_text())
        assert "nmsk.parts_sidecar" in json.dumps(p)[:600]
        assert len(p["geometry"]["dropped"]) == 0
        assert p["geometry"].get("placements", p.get("placements", 1))
    fem = FINAL["female"]
    assert (fem / "clinical_motor_points.json").exists() and (fem / "clinical_risk.json").exists()
    assert (fem / "clinical_needle_tool.js").read_bytes() == (REPO / "clinical" / "needle_tool.js").read_bytes()
    assert json.loads((fem / "clinical_motor_points.json").read_text())["viewers"]["zan_f"]["points"]
    assert json.loads((fem / "clinical_motor_points.json").read_text())["viewers"]["zan_f"] == json.loads((REPO / "clinical" / "data" / "motor_points.json").read_text())["viewers"]["zan_f"]
    # Q233 regenerated clinical/data/risk_zan_f.json with the five HRA female organs added: the Q225 page's file must equal it minus those rows (and the generation date)
    q225_risk, repo_risk = json.loads((fem / "clinical_risk.json").read_text()), json.loads((REPO / "clinical" / "data" / "risk_zan_f.json").read_text())
    q233_ids = {"uterus", "ovary_l", "ovary_r", "uterine_tube_l", "uterine_tube_r"}
    strip = lambda d: {k: ([r for r in v if r.get("id") not in q233_ids] if k == "structures" else ({c: n for c, n in v.items() if c != "organ"} if k == "counts" else v)) for k, v in d.items() if k != "generated"}
    assert strip(q225_risk) == strip(repo_risk)
    assert not list(FINAL["male"].glob("clinical_*"))                           # the Z male fitted page has no clinical files
    assert (fem / "index.html").read_bytes() == (fem / "atlas_viewer_zan_female.html").read_bytes()


@final
def test_regen_verify_files_ok():
    for n in ("viewer_zan_vhm", "viewer_zan_female"):
        v = json.loads((REPO / "build" / "q225" / "_verify" / f"{n}.json").read_text())
        assert v["literals_identical"] and v["geo_identical"] and v["new_equals_current_template_plus_same_data"]


@final
def test_final_geometry_is_the_fitted_page_geometry_byte_for_byte():
    for w, stem in (("male", "atlas_viewer_zan_male_fitted"), ("female", "atlas_viewer_zan_female")):
        for g in sorted(FIT[w].glob(f"{stem}_geo_*.txt")):
            assert g.read_bytes() == (FINAL[w] / g.name).read_bytes()


@pytest.mark.skipif(not (DER / "Q225_motor_points_coverage_before.json").exists(), reason="clinical regeneration not run")
def test_female_motor_points_regenerated_and_other_viewers_kept():
    mp = json.loads((REPO / "clinical" / "data" / "motor_points.json").read_text())["viewers"]
    assert set(mp) >= {"vhm", "vhf", "zan_m", "zan_f"} and len(mp["zan_f"]["points"]) >= 190
    before = json.loads((DER / "Q225_motor_points_coverage_before.json").read_text())
    assert before["viewer"] == "zan_f" and before["n_points"] >= 190
    risk = json.loads((REPO / "clinical" / "data" / "risk_zan_f.json").read_text())
    assert risk and len(json.dumps(risk)) > 1000


def test_end_distances_keep_the_order_of_the_two_ends_when_the_structure_moves():
    from scipy.spatial import cKDTree
    from scripts.zanatomy import q225_build as B
    rng = np.random.default_rng(1)
    bar = np.column_stack([rng.normal(0, 3, 400), np.linspace(0, 100, 400), rng.normal(0, 3, 400)])
    tree = cKDTree(np.array([[0.0, -2.0, 0.0], [0.0, 160.0, 0.0]]))           # bone 'below' the low end (2 mm) and 60 mm beyond the high end
    d = B.end_distances_stable(bar, tree)
    assert d[0] < 10 and d[1] > 50
    th = np.radians(25.0)
    R = np.array([[1, 0, 0], [0, np.cos(th), -np.sin(th)], [0, np.sin(th), np.cos(th)]])
    d2 = B.end_distances_stable(bar @ R.T + np.array([0.0, 0.0, 3.0]), tree)       # tilted + shifted: still the low end first
    assert d2[0] < d2[1]
    d3 = B.end_distances_stable(bar[::-1].copy(), tree)                             # vertex order must not matter
    assert abs(d3[0] - d[0]) < 1e-9 and abs(d3[1] - d[1]) < 1e-9
