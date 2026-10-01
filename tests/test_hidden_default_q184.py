"""Q184: per-structure hidden_default flag -- stamped on Q183b route-d records, forwarded to the bundle, honoured by the viewer."""
import json
from pathlib import Path

import pytest

import scripts.vessels_ql_q183b as q

REPO = Path(__file__).resolve().parents[1]
ROUTE_D = sorted(k for k, e in json.loads(q.REPORT.read_text())["structures"].items() if e["route"] == "d")


def test_route_d_is_the_13_kept_records():
    assert len(ROUTE_D) == 13 and "quadratus_lumborum_r" in ROUTE_D and "superior_vena_cava" not in ROUTE_D


def test_stamp_sets_flag_on_route_d_only(tmp_path, monkeypatch):
    mf = tmp_path / "build" / "vh" / "ct_s1159" / "manifest.json"
    mf.parent.mkdir(parents=True)
    mf.write_text(json.dumps({"structures": [{"atlas_id": "inferior_vena_cava", "procedural_badge": "x"},
                                             {"atlas_id": "superior_vena_cava"}, {"atlas_id": "femur_r"}]}))
    monkeypatch.setattr(q, "REPO", tmp_path)
    q.stamp()
    s = {r["atlas_id"]: r for r in json.loads(mf.read_text())["structures"]}
    assert s["inferior_vena_cava"].get("hidden_default") is True and "Q184" in s["inferior_vena_cava"]["procedural_badge"]
    assert "hidden_default" not in s["superior_vena_cava"] and "hidden_default" not in s["femur_r"]


def test_exporter_and_template_carry_the_flag():
    assert 'entry["hidden_default"] = True' in (REPO / "scripts" / "export_viewer_bundle.py").read_text()
    t = (REPO / "viewer" / "atlas_viewer.template.html").read_text()
    assert "var vis = on[s.cat] && (!s.hidden_default || !!hdShown[s.id]);" in t
    assert "if (s.hidden_default) hdShown[s.id] = true;" in t and "Hidden by default — see note" in t


# + Q185c: discs whose endplate rebuild was held keep the Q104 cylinder, hidden by default
# + Q185 d/e/h/i/j (scripts/bone_carve_q185.py): carve HELD and > 20 % inside the body's own bone -> hidden by default
# + Q185 b/f/g (same script): Q185b bone carve HELD > 20 % (his ECU l); Q185f organ push HELD > 20 % in her own organ labels
Q185_BONE_M = ["coracobrachialis_l", "extensor_carpi_ulnaris_l", "iliopsoas_tendon_l", "rectus_capitis_lateralis_l",
               "rectus_capitis_lateralis_r"]
Q185_BONE_F = ["ankle_articular_cartilage_l", "ankle_articular_cartilage_r", "flexor_digitorum_longus_r",
               "flexor_pollicis_longus_r", "hip_articular_cartilage_l", "hip_articular_cartilage_r", "palmar_interossei_r",
               "popliteus_l", "posterior_cruciate_ligament_l", "quadratus_femoris_r", "rectus_capitis_anterior_l",
               "transversus_abdominis_l", "transversus_abdominis_r"]


@pytest.mark.parametrize("d,want", [("viewer_m_hr", sorted(ROUTE_D + ["intervertebral_disc_c6_c7"] + Q185_BONE_M)),
                                    ("viewer_f_hr", sorted(["intervertebral_disc_c6_c7", "intervertebral_disc_t3_t4"] + Q185_BONE_F))])
def test_built_bundles(d, want):
    b = REPO / "build" / d / "bundle.json"
    if not b.exists():
        pytest.skip("bundle not built")
    got = sorted({s["id"] for s in json.loads(b.read_text())["structures"] if s.get("hidden_default")})
    assert got == want
