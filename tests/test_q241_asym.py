"""Q241 part 1: left / right pose difference of the six models (data/derived/Q241_pose_asymmetry.json): the BASIC models are symmetric by construction, the reconstructed ones are posed asymmetrically,
and the bone-driven pose normalisation explains most of the tissue offset."""
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
D = json.loads((REPO / "data/derived/Q241_pose_asymmetry.json").read_text())["pages"]
MD = (REPO / "data/derived/Q241_pose_asymmetry.md").read_text()


def test_all_six_pages_and_the_report():
    assert set(D) == {"own_m", "own_f", "comb_m", "comb_f", "base_m", "base_f"}
    for p in D.values():
        assert len(p["angles"]) >= 13 and p["trunk"] and p["tissue"]["all"]["n"] > 100
    assert "Verdict" in MD and "Base · Male" in MD and "BY DESIGN" in MD


def test_basic_models_are_symmetric_in_pose():
    for k in ("base_m", "base_f"):
        p = D[k]
        assert p["exceed"] == []
        big = [r for r in p["angles"] if r["group"] not in ("fingers", "toes") and abs(r["diff"]) > 0.3]
        assert not big, big
        assert max(abs(r["diff"]) for r in p["angles"]) < 5                         # toes / fingers: landmark noise of tiny bones only
        assert all(abs(t["rotation_deg"]) < 0.6 and abs(t["tilt_deg"]) < 0.6 for t in p["trunk"] if not t["item"].startswith("vertebra") or True)
        assert abs(p["pelvis_vs_trunk"]["obliquity_deg"]) < 0.2 and abs(p["pelvis_vs_trunk"]["rotation_deg"]) < 0.2
        assert p["bone_pairs_median_msd_mm"] < 1.0                                   # the left bones are mirror copies of the right ones
        assert p["tissue"]["muscle"]["centroid_mm_after"] < 2.0                      # no pose component in the tissue asymmetry
    assert D["base_m"]["angles"] == D["base_f"]["angles"]                            # one skeleton


def test_reconstructed_models_have_real_pose_differences_and_normalisation_helps():
    for k in ("own_m", "own_f", "comb_m", "comb_f"):
        p = D[k]
        assert p["bone_pairs_median_msd_mm"] > 5.0
        m = p["tissue"]["muscle"]
        assert m["centroid_mm_after"] < m["centroid_mm_before"] * 0.75, (k, m)
        assert m["iou_pose_median"] > m["iou_mirror_median"] + 0.15, (k, m)
        assert m["iou_ge_06_after"] > m["iou_ge_06_before"]
        c = p["tissue"]["classification"]
        assert c["explained_by_pose"] > c["symmetric_already"]
    # the legs / feet of the individuals are posed differently (VH specimens): their bone registration rotates the left leg
    seg = {s["seg"]: s for s in D["comb_f"]["segment_registration"]}
    assert max(seg[n]["rot_deg"] for n in ("fem_l", "tib_l", "foot_l") if n in seg) > 5


def test_thresholds_are_documented_as_assumptions():
    assert "ASSUMPTIONS" in MD and "Sadeghi" in MD
