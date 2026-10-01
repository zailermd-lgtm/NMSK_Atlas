"""Q188: the private needle-planning add-on -- risk classification, the halo-radius
formula, path scoring, the staging script, and the generic hook in both viewer templates."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
MODULE = REPO / "clinical" / "needle_tool.js"
sys.path.insert(0, str(REPO / "scripts" / "clinical"))
import risk_structures_q188 as risk  # noqa: E402
import stage_clinical_files as stage  # noqa: E402

NODE = shutil.which("node")


def js(expr: str):
    """Evaluate an expression against the module's pure exports (`M`) in node."""
    if not NODE:
        pytest.skip("node not available")
    code = f"const M = require({json.dumps(str(MODULE))}); process.stdout.write(JSON.stringify({expr}));"
    return json.loads(subprocess.run([NODE, "-e", code], check=True, capture_output=True, text=True).stdout)


CASES = [
    ({"id": "femoral_v_r", "name": "Femoral vein", "cat": "vessel"}, "vein"),
    ({"id": "femoral_a_r", "name": "Femoral artery", "cat": "vessel"}, "artery"),
    ({"id": "inferior_vena_cava", "name": "Inferior vena cava", "cat": "vessel"}, "vein"),
    ({"id": "brachiocephalic_trunk_r", "name": "Brachiocephalic trunk", "cat": "vessel"}, "artery"),
    ({"id": "aortic_arch_and_great_vessels", "name": "Aortic arch", "cat": "vessel"}, "artery"),
    ({"id": "zan_x", "name": "Posterior tibial veins", "cat": "vessel", "vt": "v"}, "vein"),
    ({"id": "zan_y", "name": "Great saphenous", "cat": "vessel", "vt": "v"}, "vein"),
    ({"id": "zan_heart", "name": "Left ventricle", "cat": "vessel"}, "artery"),
    ({"id": "sciatic_n", "name": "Sciatic nerve", "cat": "nerve"}, "nerve"),
    ({"id": "zan_cord", "name": "Spinal cord", "cat": "cns"}, "nerve"),
    ({"id": "zan_gyrus", "name": "Angular gyrus", "cat": "cns"}, "organ"),
    ({"id": "zan_lobe", "name": "Inferior lobe of left lung", "cat": "viscera"}, "lung"),
    ({"id": "zan_pleura", "name": "Parietal pleura", "cat": "viscera"}, "lung"),
    ({"id": "zan_jej", "name": "Jejunum", "cat": "viscera"}, "organ"),
    ({"id": "urinary_bladder", "name": "Urinary bladder", "cat": "organ"}, "organ"),
    ({"id": "zan_td", "name": "Thoracic duct", "cat": "lymph"}, "vein"),
    ({"id": "zan_node", "name": "Axillary lymph nodes", "cat": "lymph"}, None),
    ({"id": "femur_r", "name": "Femur", "cat": "bone"}, "bone"),
    ({"id": "biceps_femoris_r", "name": "Biceps femoris", "cat": "muscle"}, None),
    ({"id": "skin", "name": "Integumentum commune", "cat": "fascia"}, None),
]


def test_risk_table_is_strict_json_and_python_classifies():
    table = risk.load_risk_table()
    assert set(table["classes"]) >= {"artery", "vein", "nerve", "lung", "organ", "bone"}
    for rec, want in CASES:
        assert risk.classify(rec, table) == want, rec


def test_browser_and_script_classify_identically():
    recs = [c[0] for c in CASES]
    got = js(f"{json.dumps(recs)}.map(M.classify)")
    assert got == [c[1] for c in CASES]


def test_halo_radius_formula():
    d = js("M.HALO_DEFAULTS")
    assert d["mult"]["artery"] > d["mult"]["nerve"] > d["mult"]["organ"] > d["mult"]["vein"]
    assert d["rMin"] == 2 and d["rMax"] == 50
    r = js("[M.haloRadius('artery',3,0), M.haloRadius('vein',1,0), M.haloRadius('artery',12,100),"
           " M.haloRadius('artery',4,50), M.haloRadius('vein',4,50), M.haloRadius('artery',1,50), M.haloRadius('artery',8,50),"
           " M.haloRadius('artery',4,20), M.haloRadius('artery',4,150), M.haloRadius('organ',500,5000), M.haloRadius('bone',5,50),"
           " M.haloRadius('artery',3,0,Object.assign({},M.HALO_DEFAULTS,{b0:6}))]")
    assert r[0] == pytest.approx(4.0)                     # b0 at the reference calibre, no depth
    assert r[1] == pytest.approx(2.0)                     # small vein clamps to the 2 mm floor
    assert r[2] == pytest.approx(1.0 * (4 * 2 + 0.035 * 100))
    assert r[3] > r[4]                                    # arteries riskier than veins
    assert r[6] > r[3] > r[5]                             # large riskier than small
    assert r[8] > r[3] > r[7]                             # deeper / longer trajectory -> larger margin
    assert r[9] == pytest.approx(50.0)                    # 50 mm ceiling
    assert r[10] == 0                                     # bone is not haloed (it blocks instead)
    assert r[11] == pytest.approx(6.0)                    # exposed parameter takes effect


def test_path_scoring_colours():
    s = js("[M.scorePath([{cls:'artery',rCal:3,clear:30}],60,false).colour,"
           " M.scorePath([{cls:'artery',rCal:3,clear:3}],60,false).colour,"
           " M.scorePath([{cls:'artery',rCal:3,clear:0.2}],60,false).colour,"
           " M.scorePath([],60,true).colour,"
           " M.scorePath([{cls:'artery',rCal:3,clear:30}],60,false).cost < M.scorePath([{cls:'artery',rCal:3,clear:8}],60,false).cost]")
    assert s == ["green", "amber", "red", "red", True]


def test_fibonacci_directions_are_unit_and_spread():
    v = js("Array.from(M.fibonacciSphere(200))")
    pts = [v[i:i + 3] for i in range(0, len(v), 3)]
    assert len(pts) == 200
    assert all(abs(sum(c * c for c in p) - 1) < 1e-5 for p in pts)
    assert abs(sum(p[1] for p in pts)) < 1e-3


def test_risk_files_schema():
    for v in ("vhm", "vhf", "zan_m", "zan_f"):
        p = REPO / "clinical" / "data" / f"risk_{v}.json"
        if not p.exists():
            pytest.skip(f"{p} not generated")
        d = json.loads(p.read_text())
        assert d["schema"] == "nmsk.clinical_risk.v1" and d["viewer"] == v and "PRIVATE" in d["licence"]
        assert d["structures"] and all(s["r_mm"] > 0 and s["class"] in ("artery", "vein", "nerve", "lung", "organ")
                                       for s in d["structures"])
        assert "pos" not in json.dumps(d["structures"][0])   # measurements only, no geometry


def test_calibre_of_a_tube():
    import trimesh
    tube = trimesh.creation.cylinder(radius=4.0, height=120.0, sections=48)
    r, how, hits = risk.calibre_radius(tube.vertices, tube.faces)
    assert how == "sdf" and hits >= 8 and r == pytest.approx(4.0, rel=0.08)


def _fake_build(tmp_path, name):
    d = tmp_path / name
    d.mkdir()
    (d / "page.html").write_text("<html>anatomy</html>")
    (d / "page_geo_00.txt").write_text("AAAA")
    return d


def _fake_clinical(tmp_path, with_mp=True):
    c = tmp_path / "clinical"
    (c / "data").mkdir(parents=True)
    (c / "needle_tool.js").write_text("/* private */")
    for v in ("vhm", "vhf", "zan_m", "zan_f"):
        (c / "data" / f"risk_{v}.json").write_text(json.dumps({"viewer": v}))
    if with_mp:
        (c / "data" / "motor_points.json").write_text('{"schema":"nmsk.motor_points.v1"}')
    return c


def test_stage_copies_the_three_private_files_per_viewer(tmp_path):
    clin = _fake_clinical(tmp_path)
    for name, key in stage.DIR_VIEWER.items():
        d = _fake_build(tmp_path, name)
        files = stage.stage(d, clinical=clin)
        assert sorted(f.name for f in files) == sorted(stage.NAMES)
        assert json.loads((d / "clinical_risk.json").read_text())["viewer"] == key
        assert (d / "page.html").read_text() == "<html>anatomy</html>"      # the anatomy page is untouched
        assert (d / "page_geo_00.txt").read_text() == "AAAA"
        gone = stage.remove(d)
        assert sorted(p.name for p in gone) == sorted(stage.NAMES)
        assert sorted(p.name for p in d.iterdir()) == ["page.html", "page_geo_00.txt"]


def test_stage_without_motor_points_and_with_an_override(tmp_path):
    clin = _fake_clinical(tmp_path, with_mp=False)
    d = _fake_build(tmp_path, "viewer_m_hr")
    (d / "clinical_motor_points.json").write_text("stale")
    files = stage.stage(d, clinical=clin)
    assert sorted(f.name for f in files) == ["clinical_needle_tool.js", "clinical_risk.json"]
    assert not (d / "clinical_motor_points.json").exists()                  # never a stale copy
    fx = REPO / "tests" / "fixtures" / "q188_motor_points_fixture.json"
    stage.stage(d, clinical=clin, motor_points=fx)
    assert json.loads((d / "clinical_motor_points.json").read_text())["schema"] == "nmsk.motor_points.v1"
    with pytest.raises(SystemExit):
        stage.stage(_fake_build(tmp_path, "viewer_unknown"), clinical=clin)


@pytest.mark.parametrize("tpl", ["atlas_viewer.template.html", "zan_atlas.template.html"])
def test_templates_carry_only_a_generic_hook(tpl):
    t = (REPO / "viewer" / tpl).read_text(encoding="utf-8")
    assert '<script src="clinical_needle_tool.js"></script>' in t
    assert "window.NMSKClinical.attach(anatomyApi())" in t
    for api in ("list:", "visible:", "geometry:", "pick:", "ray:", "view:", "toScreen:", "cut:", "setCut:",
                "setOpacityOverride:", "setCategoryOn:", "setClickHandler:"):
        assert api in t, api
    for private in ("haloRadius", "motor_points", "needleCrossings", "runSafer", "RISK_TABLE"):
        assert private not in t, private


def test_fixture_is_labelled_and_module_is_private():
    fx = json.loads((REPO / "tests" / "fixtures" / "q188_motor_points_fixture.json").read_text())
    assert fx["schema"] == "nmsk.motor_points.v1" and "FIXTURE" in fx["licence"]
    head = MODULE.read_text(encoding="utf-8")[:1200]
    assert "PRIVATE" in head and "not clinical guidance" in head.lower()
