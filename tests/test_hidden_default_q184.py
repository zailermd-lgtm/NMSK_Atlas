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


@pytest.mark.parametrize("d,want", [("viewer_m_hr", ROUTE_D), ("viewer_f_hr", [])])
def test_built_bundles(d, want):
    b = REPO / "build" / d / "bundle.json"
    if not b.exists():
        pytest.skip("bundle not built")
    got = sorted({s["id"] for s in json.loads(b.read_text())["structures"] if s.get("hidden_default")})
    assert got == want
