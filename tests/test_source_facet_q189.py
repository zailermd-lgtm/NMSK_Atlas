"""Q189: the own viewers' Source facet (viewer/atlas_viewer.template.html) and its audit (scripts/audit_q189_model_separation.py)."""
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from scripts import audit_q189_model_separation as A  # noqa: E402

TPL = (REPO / "viewer" / "atlas_viewer.template.html").read_text()


def test_classes_from_subject_names():
    c = lambda s, b=None: A.classify(s, b)[0]  # noqa: E731
    assert c("xfer_zan2vhm_limb") == c("xfer_zan2vhf_head") == "filled_zan"
    assert c("xfer_vhm2vhf_sep_contfix_mesh") == c("xfer_vhf2vhm_neck") == c("ct_vhf_xfersepta_fix_contfix") == "transferred"
    assert c("ct_s1159_abd") == "other_specimen"
    assert c("ct_vhm_pfloor_fix", "RULE-BASED (Q172): ...") == "rule_based"
    assert c("ct_vhf_dneck_contfix_mesh") == "rule_based"          # description says rule-based
    assert c("ct_vhm_ggl") == "rule_based"                          # label added in Q189 (mapping notes say rule-based)
    assert c("ct_vhm_head") == c("vhm_both") == c("ct_vhf_head") == "measured"


def test_default_view_is_unchanged_by_the_facet():
    # every class starts on, colouring starts off: the default visibility line of Q184 is still the one in apply()
    assert "var vis = on[s.cat] && (!s.hidden_default || !!hdShown[s.id]);" in TPL
    assert "srcOn[c.k] = true;" in TPL and "var srcOn = {}, srcCount = {}, srcColour = false;" in TPL
    assert "if (srcOn[s.src] === false) vis = false;" in TPL


def test_inspector_states_the_source_and_minimizes():
    for phrase in ("Measured on this body", "Filled from Z-Anatomy (reference model), fitted to this body",
                   "Transferred from the other Visible Human body", "NOT this body's geometry"):
        assert phrase in TPL
    assert 'id="insp-min"' in TPL and "nmsk_info_min" in TPL


def test_js_and_python_classifier_agree_on_rules():
    js = TPL[TPL.index("function classifySource"):TPL.index("function sourceError")]
    assert 'indexOf("xfer_zan2") === 0' in js and "/(^|_)xfer/" in js and 'indexOf("ct_s1159") === 0' in js
    assert "/rule/i.test(SUBJECT_LABELS[b]" in js and "rule-based" in js


def test_built_audit_is_consistent():
    p = REPO / "data" / "derived" / "Q189_model_separation_audit.json"
    if not p.exists():
        return
    d = json.loads(p.read_text())
    for k in ("male", "female"):
        o = d[f"own_{k}"]
        assert sum(v["entries"] for v in o["by_class"].values()) == o["entries"]
        assert all(len(v) == 0 for v in o["mislabel_checks"].values()), o["mislabel_checks"]
        z = d[f"zan_{k}"]
        assert z["bbox_identical_to_own_mesh_of_same_id"] == [] and z["badge_mentions_specimen_geometry"] == []
    assert d["zan_female"]["fitted_onto_her_skeleton_badged"] == d["zan_female"]["meshes"]
    assert d["zan_male"]["fitted_onto_her_skeleton_badged"] == 0


def test_hub_names_the_two_kinds():
    hub = (REPO / "viewer" / "atlas_hub.html").read_text()
    assert "Base atlas model" in hub and "Reconstructed from imaging" in hub and "adapted to the reconstruction" in hub and "badged as a fill" in hub
