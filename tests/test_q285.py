"""Q285: her breasts from TotalSegmentator `breasts` on her own CT (the browser behaviour is scripts/anatomy/q285/verify_q285.py)."""
import base64
import json
import zlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_both_sides_shipped_and_every_gate_met():
    r = json.loads((REPO / "data/derived/Q285_vhf_breast_report.json").read_text())
    assert r["shipped"] == ["breast_ct_r", "breast_ct_l"] and not r["held"]
    for s in r["sides"].values():
        assert s["outside_skin_gt1mm_frac"] == 0.0 and s["in_bone_gt1mm_frac"] <= 0.05
        assert not s["edge_touch"] and s["largest_component_share"] >= 0.85 and abs(s["mesh_vs_label"] - 1) <= 0.03
        assert s["overlap_total_labels_frac"] == 0.0


def test_volumes_and_asymmetry_are_the_reported_ones():
    r = json.loads((REPO / "data/derived/Q285_vhf_breast_report.json").read_text())
    rr, ll = r["sides"]["right"]["kept_voxel_cm3"], r["sides"]["left"]["kept_voxel_cm3"]
    assert 950 < rr < 1050 and 830 < ll < 920
    assert abs(r["asymmetry_pct_of_mean"] - 100 * abs(rr - ll) / (0.5 * (rr + ll))) < 0.1


def test_pose_rig_has_the_two_new_entries_spliced_after_the_committed_ones():
    j = json.loads((REPO / "data/anatomy/pose_rig_own_f.json").read_text())
    rig = j["rig"]
    assert rig["count"] == 1043 and len(rig["nv"]) == 1043
    new = [e for e in rig["skin"] if e[0] in (1041, 1042)]
    assert len(new) == 2
    w = zlib.decompress(base64.b64decode(j["weights_zlib_b64"]))
    offs = sorted(e[4] for e in rig["skin"])
    assert offs == sorted(set(offs)) and max(e[4] for e in new) < len(w)
    assert all(e[4] >= max(x[4] for x in rig["skin"] if x[0] < 1041) for e in new)
