"""Q223: the committed audit outputs exist and have the agreed schema (file existence / keys only; the audit itself is read-only and takes ~1.5 h)."""
import json
from pathlib import Path

DER = Path(__file__).resolve().parents[1] / "data" / "derived"
PAGES = ["own_m", "own_f", "z_male_fit", "z_female_fit", "z_base_f", "z_male"]
REGIONS = ["head_neck", "shoulder", "arm", "elbow", "forearm", "wrist_hand", "thorax", "abdomen_pelvis", "hip", "thigh", "knee", "leg", "ankle_foot"]
TYPES = ["gap", "detached_piece", "detached_end", "flat_cut", "outside_skin", "bone_penetration", "soft_in_bone", "muscle_in_muscle", "ragged_boundary"]


def test_page_jsons_schema():
    for k in PAGES:
        d = json.loads((DER / f"Q223_audit_{k}.json").read_text())
        assert set(d["regions_13"]) == set(REGIONS)
        for g in REGIONS:
            r = d["regions_13"][g]
            assert len(r["structures_major_moderate_minor"]) == 3 and set(r["findings_by_type"]) == set(TYPES)
            assert "missing_expected_neighbours" in r
        assert len(d["structures_major_moderate_minor_now"]) == 3 and "q209_structures_major_moderate_minor" in d
        assert d["junction_audit_q198"]["elbow_L_R_q209_now"][1] in (["OK", "OK"], ["DEFECT", "DEFECT"], ["OK", "DEFECT"], ["DEFECT", "OK"])


def test_bases_reproduce_q209():
    for k, want in (("z_male", [75, 125, 160]), ("z_base_f", [75, 125, 154])):
        assert json.loads((DER / f"Q223_audit_{k}.json").read_text())["structures_major_moderate_minor_now"] == want


def test_top15_summary_and_renders():
    t = json.loads((DER / "Q223_top15.json").read_text())
    assert [x["rank"] for x in t["top15"]] == list(range(1, 16)) and t["audit_artefacts"]
    assert all(x["fix"] and x["ids"] for x in t["top15"])
    assert "Top 15" in (DER / "Q223_audit_summary.md").read_text()
    assert len(list(DER.glob("Q223_render_*.png"))) == 5
