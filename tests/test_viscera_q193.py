"""Q193: organs of both own models from their own TotalSegmentator `total` labels (scripts/viscera_from_ct_labels_q193.py)."""
import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from scripts import audit_q189_model_separation as A  # noqa: E402
from scripts import viscera_from_ct_labels_q193 as V  # noqa: E402

TPL = (REPO / "viewer" / "atlas_viewer.template.html").read_text()


def test_subjects_classify_as_measured_in_the_source_facet():
    for s in ("ct_vhm_viscera", "ct_vhf_viscera"):
        assert A.classify(s, None)[0] == "measured"
        lab = A.LABELS[s]
        assert "measured on this body by automatic segmentation, not hand-drawn" in lab
        assert "TotalSegmentator total task" in lab
        assert not re.search(r"rule|z-anatomy|transferred from|not measured on", lab, re.I)


def test_organ_table_labels_exist_and_are_not_shared():
    seen = {}
    for rid, labs, name, side, region in V.ORGANS:
        assert rid in V.REFS and all(str(x) in V.TS for x in labs)
        for x in labs:
            assert x not in seen, (x, rid, seen[x])
            seen[x] = rid
        assert side in (None, "left", "right")
    # sides follow the anatomical TS label names
    for rid, labs, _n, side, _r in V.ORGANS:
        if side:
            assert all(V.TS[str(x)].endswith(side) or side in V.TS[str(x)] for x in labs)


def test_badge_text_never_reads_as_transfer_or_rule():
    row = {"labels": [5], "label_names": ["liver"], "kept_voxel_cm3": 1.0, "ratio_to_reference": 1.7, "largest_component_share": 1.0,
           "mesh_vs_label": 1.0, "outside_skin_frac": 0.0, "in_bone_gt1mm_frac": 0.0, "max_overlap_frac": 0.0,
           "touches_array_edge": ["z_bottom"], "reference": {"kind": "published", "source": "X 2002, Y", "value_cm3": 1360.0, "window_cm3": None}}
    for body in ("vhm", "vhf"):
        b = V.badge(body, "liver", row)
        assert b.startswith("Q193: measured on this body") and "SIZE CAVEAT" in b and "Clipped" in b
        assert not re.match(r"\s*rule-based", b, re.I)
        assert not re.search(r"z-anatomy|transferred from|not measured on", b, re.I)


@pytest.mark.parametrize("body", ["vhm", "vhf"])
def test_report_holds_are_reasoned_and_shipped_pass_gates(body):
    p = REPO / "data" / "derived" / f"Q193_viscera_{body}.json"
    if not p.exists():
        pytest.skip("Q193 report not built")
    d = json.loads(p.read_text())
    assert d["shipped"] and set(d["held"]).isdisjoint(d["shipped"])
    for k, why in d["held"].items():
        assert why
    for k in d["shipped"]:
        r = d["organs"][k]
        assert r["outside_skin_frac"] == 0 and r["in_bone_gt1mm_frac"] <= 0.05 and r["max_overlap_frac"] <= 0.10
        assert abs(r["mesh_vs_label"] - 1) <= 0.03 and r["largest_component_share"] >= 0.85
        assert r["reference"]["source"]
    if "shipped_audit" in d:
        assert all(x["pass"] for x in d["shipped_audit"]["rows"].values())


def test_big_organs_are_faded_not_hidden_and_organ_system_stays_off_at_load():
    assert 'on[c] = (c === "bone" || c === "muscle");' in TPL
    assert "FADED_ORGANS" in TPL and "Math.min(base, 0.55)" in TPL
