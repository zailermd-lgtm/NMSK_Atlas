"""Q288: her uterus from her own colour cryosections (scripts/cryo/vhf_*_q288.py, vhf_pelvic_organs_from_cryo.py, scripts/anatomy/q288/)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts/anatomy/q288"))


def _rep(name):
    return json.loads((REPO / "data/derived" / name).read_text())


def test_photo_to_frame_mapping_flips_rows_and_round_trips(tmp_path):
    from scripts.cryo.vhf_pelvic_organs_from_cryo import Reg
    p = tmp_path / "reg.json"
    p.write_text(json.dumps({"levels": [{"cryo_z": -1830.0, "ras_z": -865.0, "ct_k": 157, "RS": 47.0, "CS": -27.0}], "photo_h_1mm": 333, "sc": 0.99}))
    r = Reg(p)
    pr, pc = np.array([0.0, 300.0, 996.0]), np.array([0.0, 750.0, 1500.0])
    fr, fc = r.p2frame(0, pr, pc)
    assert fr[0] > fr[1] > fr[2]                       # photograph row 0 is posterior: frame row (240 - RAS y) falls as the photo row grows
    assert np.all(np.diff(fc) > 0)                     # columns keep their sense (no left-right flip)
    br, bc = r.frame2p(0, fr, fc)
    assert np.allclose(br, pr) and np.allclose(bc, pc)


def test_register_to_frame_is_the_same_mapping():
    from scripts.cryo.vhf_register_pelvis_q288 import to_frame
    img = np.zeros((10, 12), np.float32); img[1, 3] = 1          # photograph row 1 (posterior side) -> second-to-last frame row at RS = 0
    out = to_frame(img, 0, 0, shape=(10, 12))
    r, c = np.unravel_index(np.argmax(out), out.shape)
    assert r == 8 and abs(c - 3) <= 1


def test_seed_file_is_auditable():
    d = json.loads((REPO / "data/derived/Q288_seeds.json").read_text())
    assert set(d["seeds"]) <= {"1", "2", "3", "9"} and set(d["labels"]) >= {"1", "2", "3", "9"}
    for lb, per in d["seeds"].items():
        for z, discs in per.items():
            assert -1900 < float(z) < -1800
            for rr, cc, rad in discs:
                assert 300 <= rr < 780 and 580 <= cc < 1040 and 2 <= rad <= 24      # inside the searched window, small discs only
    assert len(d["seeds"]["1"]) == 18


def test_gates_hold_bad_uteri():
    import uterus_q288 as U
    ok = {"components": 1, "mesh_vs_voxels": 1.0, "voxel_cm3": 35.0, "ct_hu": {"fat_frac": 0.1},
          "inside_her_ct_labels_frac": {"small_bowel": 0.6, "urinary_bladder": 0.0}}
    assert U.gates(ok) == []                          # her small_bowel label is reported, not gated (it covers her uterus on CT, Q287)
    for k, v in (("components", 2), ("mesh_vs_voxels", 1.05), ("voxel_cm3", 120.0)):
        assert U.gates({**ok, k: v})
    assert U.gates({**ok, "ct_hu": {"fat_frac": 0.3}})
    assert U.gates({**ok, "inside_her_ct_labels_frac": {"small_bowel": 0.0, "urinary_bladder": 0.4}})


def test_shipped_uterus_report_and_item():
    r = _rep("Q288_uterus_report.json")
    assert r["held"] == [] and 10 <= r["voxel_cm3"] <= 90
    assert r["components"] == 1 and abs(r["mesh_vs_voxels"] - 1) < 0.03
    assert -10 < r["ct_hu"]["median"] < 80 and r["ct_hu"]["fat_frac"] < 0.15
    assert r["vs_hra_uterus_on_combined_f"]["centroid_distance_mm"] < 25
    items = json.loads((REPO / "build/vh/ct_vhf_uterus/items.json").read_text())
    assert [i["id"] for i in items] == ["uterus_cryo_vhf"]
    b = items[0]["badge"]
    assert "random walker" in b and "Q288_seeds.json" in b and "Jirapinyo" in b and "PMID 9676090" in b
    assert not b.lower().lstrip().startswith("rule-based")


def test_pages_hide_the_hra_uterus_and_rigs_cover_the_new_entry():
    c = _rep("Q288_comb_f_report.json")
    assert c["added"] == ["uterus_cryo_vhf"] and c["hidden_default"] == ["uterus"] and c["new_indices"] == [3243]
    import base64, zlib
    for key, n in (("comb_f", 3246), ("own_f", 1053)):          # Q293 spliced +2 after the uterus (RF reflected heads)
        j = json.loads((REPO / f"data/anatomy/pose_rig_{key}.json").read_text()); rig = j["rig"]
        assert rig["count"] == n and len(rig["nv"]) == n
        covered = {e[0] for e in rig["skin"]} | {i for _, lst in rig["rigid"] for i in lst}
        assert n - 3 in covered
        w = zlib.decompress(base64.b64decode(j["weights_zlib_b64"]))
        offs = sorted(e[4] for e in rig["skin"]); assert offs == sorted(set(offs)) and offs[-1] < len(w)
    src = (REPO / "scripts/anatomy/q288/own_f_q288.py").read_text()
    assert 'x["e"]["hidden_default"] = True' in src and 'HIDE = ["uterus"]' in src


def test_subject_label_synced_and_measured():
    r = subprocess.run([sys.executable, str(REPO / "scripts/sync_subjects_q288.py"), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout
    t = (REPO / "viewer/atlas_viewer.template.html").read_text(encoding="utf-8")
    line = next(l for l in t.splitlines() if l.strip().startswith("ct_vhf_uterus:"))
    assert "rule" not in line.lower()                 # classifySource -> 'measured' (segmented on her photographs)
    assert t.index("ct_vhf_breast_fgt:") < t.index("ct_vhf_uterus:") < t.index("xfer_hrasculpt2vhf_q234:")
