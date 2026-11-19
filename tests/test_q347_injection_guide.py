"""Q347: the injection guide in the injection-planning mode -- the private sibling's data contract, the public/private split,
and the regen staging step. (The browser behaviour is checked by scripts/anatomy/q347/verify_injection_guide_q347.py.)"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "clinical"))
import build_injection_guide_q347 as bg  # noqa: E402
import stage_clinical_files as scf  # noqa: E402

PRIVATE = json.loads((REPO / "clinical" / "data" / "innervation_injection_q322.json").read_text(encoding="utf-8"))
PUBLIC = json.loads((REPO / "data" / "anatomy" / "innervation_q322.json").read_text(encoding="utf-8"))
FIELDS = ("injection_points", "sites", "scan_start", "manoeuvre", "at_risk", "src", "cite")


@pytest.fixture(scope="module", params=bg.PAGES)
def built(request, tmp_path_factory):
    d = tmp_path_factory.mktemp(request.param)
    assert bg.main([request.param, str(d)]) == 0
    return request.param, json.loads((d / bg.NAME).read_text(encoding="utf-8"))


def test_contract_and_values_verbatim(built):
    page, g = built
    assert g["schema"] == "nmsk.injection_guide.page.v1" and g["page"] == page
    assert g["source"]["doi"] == "10.23736/S1973-9087.26.09497-9" == PUBLIC["sources"]["guv2026"]["doi"]
    assert set(g["muscles"]) == set(PRIVATE["muscles"]) == set(PUBLIC["muscles"]) and len(g["muscles"]) == 60
    for k, m in g["muscles"].items():
        for f in FIELDS:                       # shown exactly as extracted: never reworded by the build
            assert m[f] == PRIVATE["muscles"][k].get(f), (k, f)


def test_every_at_risk_text_has_its_named_structures(built):
    _, g = built
    for k, m in g["muscles"].items():
        assert bool(m["at_risk"]) == bool(m["risk"]), k
        for r in m["risk"]:
            assert r["name"] and isinstance(r["stems"], list), (k, r)
            assert r["stems"] or r.get("note"), (k, r["name"])       # an unmapped name says why
            for st in r["stems"]:
                assert re.fullmatch(r"[a-z0-9_]+", st) and not st.endswith(("_l", "_r")), (k, st)   # the side is the target's, added on the page


def test_conflicts_are_the_documented_table_text_ones(built):
    _, g = built
    with_c = {k for k, m in g["muscles"].items() if m["conflict"]}
    assert with_c == {"latissimus_dorsi", "flexor_pollicis_longus", "adductor_longus", "gastrocnemius", "soleus",
                      "flexor_digitorum_longus", "flexor_hallucis_longus"}
    for k in with_c:
        c = g["muscles"][k]["conflict"]
        assert c["adopted"] and c["other"] and c["adopted"] != c["other"]
    doc = (REPO / "docs" / "Q322_innervation_sources.md").read_text(encoding="utf-8")
    assert "Internal inconsistencies of the guide" in doc


def test_scan_starts_name_a_measured_landmark_and_show_frames_stay_in_range(built):
    page, g = built
    lm = json.loads((REPO / "data" / "derived" / f"Q322_iz_bands_{page}.json").read_text(encoding="utf-8"))["landmarks"]
    rig = {j["id"]: j for j in json.loads((REPO / "data" / "anatomy" / f"pose_rig_{page}.json").read_text(encoding="utf-8"))["rig"]["joints"]}
    for k, m in g["muscles"].items():
        for sc in m["scan"]:
            assert m["scan_start"], k
            assert sc["l"] == lm[sc["landmark"]]["l"] and sc["r"] == lm[sc["landmark"]]["r"], (k, sc["landmark"])
            assert sc["plane"] in (None, "trans")
            # the landmark is named in the guide's own scan-start text
            words = {"scapula_inferior_angle": "scapula", "coracoid_tip": "coracoid", "medial_femoral_condyle": "medial femoral condyle",
                     "medial_malleolus": "medial malleolus", "lateral_malleolus_tip": "lateral malleolus", "fibular_head": "fibular head"}
            want = words[sc["landmark"]]
            text = m["scan_start"] if "as fibularis longus" not in m["scan_start"] else g["muscles"]["fibularis_longus"]["scan_start"]
            assert want in text, (k, want)
        for fr in m["show"] or []:
            assert m["manoeuvre"], k
            for jn, dofs in fr.items():
                for side in ("l", "r"):
                    j = rig[jn + "_" + side]
                    for dk, deg in dofs.items():
                        d = [x for x in j["dof"] if x["k"] == dk][0]
                        assert d["lo"] <= deg <= d["hi"], (k, jn, dk, deg)


def test_no_private_words_in_public_files():
    bad = ("clinical_injection_guide", "injection_guide", "guideScan", "useGuideSite", "injection_points", "scan_start", "at_risk",
           "ultrasound", "hounsfield", "t1_se", "imaging_tissues", "tissue table", "nmskultrasound", "acoustic", "mrayl", "b-mode")
    for name in ("atlas_viewer.template.html", "zan_atlas.template.html"):
        low = (REPO / "viewer" / name).read_text(encoding="utf-8").lower()
        for w in bad[:7]:
            assert w.lower() not in low, (name, w)
    for f in list((REPO / "viewer").rglob("*.js")) + list((REPO / "viewer").rglob("*.css")):
        low = f.read_text(encoding="utf-8").lower()
        for w in bad[:7]:
            assert w.lower() not in low, (f, w)
    pub = (REPO / "data" / "anatomy" / "innervation_q322.json").read_text(encoding="utf-8")
    for w in ('"injection_points"', '"scan_start"', '"at_risk"', '"manoeuvre"'):
        assert w not in pub, w
    sidecar = (REPO / "scripts" / "anatomy" / "q322" / "build_sidecar_q322.py").read_text(encoding="utf-8")
    assert "innervation_injection_q322" not in sidecar and "clinical/" not in sidecar   # the public builder never reads the private layer


def test_private_tool_reads_the_sibling_and_the_public_sidecar():
    js = (REPO / "clinical" / "needle_tool.js").read_text(encoding="utf-8")
    assert 'get("clinical_injection_guide.json")' in js and '"innervation_q322.json"' in js
    assert "nmsk.injection_guide.page.v1" in js and "nmsk.innervation.page.v1" in js


def test_regen_builds_it_for_the_base_pages_and_remove_cleans_it(tmp_path):
    src = (REPO / "scripts" / "regen_template_only.py").read_text(encoding="utf-8")
    i = src.index('run(["python3", "scripts/clinical/build_injection_guide_q347.py", p, str(dst)])')
    assert 'if p in ("base_m", "base_f"):' in src[i - 200:i]
    assert src.index('clinical/data/motor_points.json", dst / "clinical_motor_points.json"') < i < src.index('(dst / "index.html").write_bytes')
    (tmp_path / "clinical_injection_guide.json").write_text("{}")
    scf.remove(tmp_path)
    assert not (tmp_path / "clinical_injection_guide.json").exists()


def test_median_nerve_is_never_mapped_to_its_branches(built):
    _, g = built
    rows = [r for m in g["muscles"].values() for r in m["risk"] if r["name"] == "median nerve"]
    assert rows and all(r["stems"] == [] and "trunk" in r["note"] for r in rows)   # the branches on the body are not the trunk
