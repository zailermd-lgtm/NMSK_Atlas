"""Q235: the CVH meshes are closed solids (README correction), the axis map, the registration record and the chirality statement. Pure geometry / JSON checks (no page build needed except where marked)."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "anatomy"))
D = REPO / "data/derived"
from scripts.anatomy.q235 import cvh, solid, structs as ST  # noqa: E402


def rj(name):
    p = D / name
    if not p.exists():
        pytest.skip(f"{name} not built")
    return json.loads(p.read_text())


CLOSED = {"clitoris_cavernous_body": (1.9167, 1), "vestibular_bulb": (1.031, 2), "bartholin_gland": (0.588, 2), "bulbospongiosus_cvh": (2.8343, 1), "ischiocavernosus_cvh": (3.2755, 2),
          "urethral_compressor_cvh": (1.1698, 1), "urethrovaginal_sphincter_cvh": (0.449, 1), "urethral_sphincter_raphe_cvh": (0.1491, 1), "urethra_female_submucous_layer": (1.3807, 1)}
KISSING = {"superficial_transverse_perineal_cvh", "deep_perineal_muscle_cvh", "urethral_sphincter_cvh", "perineal_body"}


@pytest.mark.parametrize("key", list(CLOSED))
def test_structure_is_a_closed_edge_manifold_solid_with_a_checked_volume(key):
    parts = ST.build(key, -1)
    vol, n = CLOSED[key]
    assert len(parts) == n
    for p in parts:
        i = p["info"]
        assert i["closed"] and i["edge_manifold"] and i["open_edges"] == 0 and i["nonmanifold_edges"] == 0
        assert i["volume_cvh_cm3"] > 0
        assert abs(i["volume_montecarlo_cm3"] - i["volume_cvh_cm3"]) <= max(4 * i["volume_montecarlo_se_cm3"], 0.05 * i["volume_cvh_cm3"]), i
    assert abs(sum(p["info"]["volume_cvh_cm3"] for p in parts) - vol) < 0.01


@pytest.mark.parametrize("key", sorted(KISSING))
def test_kissing_edge_structures_are_closed_except_for_four_triangle_edges(key):
    for p in ST.build(key, 1):
        i = p["info"]
        assert i["open_edges"] == 0 and 0 < i["nonmanifold_edges"] <= 3 and not i["edge_manifold"]
        assert i["volume_cvh_cm3"] > 0.3 and abs(i["volume_montecarlo_cm3"] - i["volume_cvh_cm3"]) <= max(4 * i["volume_montecarlo_se_cm3"], 0.06 * i["volume_cvh_cm3"]), i


def test_readme_claim_vs_directed_edge_check():
    # the old 'open sheet' label: directed-edge check on the raw file says open, undirected says closed
    j = {s["index"]: s for s in cvh.index().values()}
    V, F = cvh.load_raw(39)
    nb, nn = solid.edge_stats(F)
    comp = max(solid.components(V, F), key=lambda c: len(c[1]))
    assert j[39]["open_edges_after_welding"] > 0 and j[39]["volume_cm3"] is None
    assert solid.edge_stats(comp[1]) == (0, 0)


def test_lumen_cut_and_cap():
    p = ST.urethral_lumen(1)[0]
    i = p["info"]
    assert i["closed"] and i["capped"] and 0.02 < i["volume_cvh_cm3"] < 0.04 and i["cut_plane"]["lumen_cross_section_mm2"] < ST.LUMEN_AREA_CUT_MM2
    assert abs(i["cut_plane"]["cap_area_mm2"] - i["cut_plane"]["lumen_cross_section_mm2"]) < 1e-6 and 20 < i["cut_plane"]["lumen_length_mm"] < 30


@pytest.mark.parametrize("sx", [1, -1])
def test_axis_map_keeps_the_solid_outward(sx):
    V, F = cvh.load_raw(38)
    comp = max(solid.components(V, F), key=lambda c: len(c[1]))
    f2 = solid.orient_bfs(*comp)
    W, G = cvh.to_atlas(comp[0], sx, f2)
    assert solid.signed_volume_cm3(W, G) > 0 and abs(solid.signed_volume_cm3(W, G) - solid.signed_volume_cm3(comp[0], f2)) < 1e-6
    assert W[:, 1].max() == pytest.approx(-comp[0][:, 2].min()) and W[:, 2].min() == pytest.approx(-comp[0][:, 1].max())      # Y = -z (superior), Z = -y (anterior)


def test_mirror_symmetric_pairs_are_the_two_conventions_of_each_other():
    a = {round(p["x_mid"], 1) for p in ST.build("vestibular_bulb", 1)}
    b = {round(-p["x_mid"], 1) for p in ST.build("vestibular_bulb", -1)}
    assert a == b and len(a) == 2


def test_registration_record():
    r = rj("Q235_cvh_to_vhf_transform.json")
    assert r["schema"] == "q235_cvh_to_vhf_v1" and r["chosen_sx"] in (1, -1)
    assert 1.05 < r["scale"] < 1.15 and abs(np.linalg.det(np.array(r["rotation"])) - 1) < 1e-4
    res = r["residual_mm"]
    assert res["all CVH bone vertices"]["median"] < 2.2 and res["all CVH bone vertices"]["p90"] < 5.0
    for k in ("pubic symphysis region (|x-184|<8)", "ischial tuberosity region (lowest 25 mm of the hip bones)", "sacrum+coccyx (closed mesh), all"):
        assert res[k]["median"] < 2.5, k
    assert set(r["by_sx"]) == {"1", "-1"}
    ch = r["chirality"]
    assert ch["determinable"] is False and "not determinable" in ch["conclusion"]
    assert all(abs(v["difference_minus1_minus_plus1_mm"]) < 2.0 for v in ch["asymmetric_structures"].values())
    assert "round ligaments are not used" in ch["decision_rule"]
    cc = r["crosscheck"]
    assert {"bladder wall (CVH 27) vs page bladder", "vaginal wall (CVH 21) vs HRA vagina", "uterine wall (CVH 17) vs HRA uterus"} <= set(cc)


def test_third_party_notice_and_readme_are_corrected():
    t = (REPO / "third_party/cvh_wu2015")
    assert "Correction (Q235)" in (t / "README.md").read_text() and "CLOSED solids" in (t / "README.md").read_text()
    n = (t / "NOTICE.md").read_text()
    assert "Q235" in n and "CC BY 4.0" in n and "NOT the authors' coordinates" in n
