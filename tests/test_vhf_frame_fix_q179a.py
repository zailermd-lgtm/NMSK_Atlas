"""Q179a: her Q48 thigh muscles moved with her tracked outlines' reconstructed lost frame (output checks skip when absent)."""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from scripts.cryo import vhf_frame_fix_q179a as F  # noqa: E402

need_store = pytest.mark.skipif(not F.STORE.exists() or not F.Q.REG_JSON.exists(), reason="Q179a store absent")
need_subject = pytest.mark.skipif(not (F.VH / F.OUT_SUBJ / "manifest.json").exists(), reason="Q179a subject absent")


def test_disp_interpolates_and_is_zero_outside():
    fs = {"y": [-10, 0, 10], "dx": [0.0, 2.0, 0.0], "dz": [0.0, -4.0, 0.0]}
    v = np.array([[1.0, 0.0, 0.0], [1.0, 5.0, 0.0], [1.0, 50.0, 0.0], [1.0, -50.0, 0.0]])
    d = F.disp(v, fs)
    assert d[0].tolist() == [2.0, 0.0, -4.0] and d[1].tolist() == [1.0, 0.0, -2.0]
    assert not d[2].any() and not d[3].any() and not d[:, 1].any()


def test_side_of():
    assert F.side_of("vastus_lateralis_r") == "right" and F.side_of("sartorius_l") == "left"


@need_store
def test_field_matches_reg_table_and_ramps():
    s = json.loads(F.STORE.read_text()); reg = json.loads(F.Q.REG_JSON.read_text()); lo, hi = s["full_weight_levels"]
    assert s["reg_json_md5"] == F.md5(F.Q.REG_JSON)
    for side, fs in s["field"].items():
        y = np.array(fs["y"]); w = np.array(fs["weight"])
        assert w[(y >= lo) & (y <= hi)].min() == 1.0 and w[y == y.max()][0] == 0.0 and w[y == y.min()][0] == 0.0
        for yy in (lo, hi, (lo + hi) // 2):
            i = fs["y"].index(yy)
            assert [fs["dx"][i], fs["dz"][i]] == pytest.approx(reg["sides"][side][str(yy)]["atlas_dx_dz_mm"], abs=1e-3)


@need_store
def test_only_q48_ids_and_volumes_kept():
    s = json.loads(F.STORE.read_text())
    assert s["ids"] and all(v["subject"] in F.SOURCES for v in s["ids"].values())
    assert not any(k.startswith(("femur", "tibia", "hip_bone", "iliopsoas", "gluteus")) for k in s["ids"])
    assert all(abs(v["volume_change_pct"]) < 0.05 for v in s["stats"].values())


@need_store
@need_subject
def test_apply_is_byte_reproducible(tmp_path, monkeypatch):
    d = F.VH / F.OUT_SUBJ; before = {k: hashlib.md5((d / k).read_bytes()).hexdigest() for k in ("vertices.f32", "faces.u32", "manifest.json")}
    if F.stamp() not in (d / "manifest.json").read_text():
        pytest.skip("subject older than the store")
    work = tmp_path / "vh"; work.mkdir()
    for sub in list(F.SOURCES) + ["xfer_vhm2vhf_sep"]:
        if (F.VH / sub).exists() and not (work / sub).exists():
            (work / sub).symlink_to(F.VH / sub)
    monkeypatch.setattr(F, "VH", work)
    F.do_apply(type("A", (), {"if_stale": False})())
    after = {k: hashlib.md5((work / F.OUT_SUBJ / k).read_bytes()).hexdigest() for k in before}
    assert after == before


@pytest.mark.skipif(not F.REPORT.exists(), reason="Q179a report absent")
def test_report_has_source_and_verification():
    r = json.loads(F.REPORT.read_text())
    assert r["source"].startswith("U.S. National Library of Medicine")
    if "verify_bundle" in r:
        v = r["verify_bundle"]
        assert not v["geometry_changed_unintended"] and not v["ids_removed"]
        for aid, row in v["moved_muscles_bundle"].items():
            for bn, b in row["bone"].items():
                assert b["beyond_1mm"][1] <= b["beyond_1mm"][0] + 25, (aid, bn)
