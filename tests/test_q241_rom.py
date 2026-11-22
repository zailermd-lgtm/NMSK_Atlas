"""Q241: the normal range of motion table (single source scripts/anatomy/q241/rom.py), its generated document and the values the sliders use."""
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts/anatomy/q241"))
import rom  # noqa: E402


def test_document_is_generated_from_the_table():
    import make_rom_doc
    assert (REPO / "docs/pose_rom_table.md").read_text(encoding="utf-8") == make_rom_doc.render(), "run: python3 scripts/anatomy/q241/make_rom_doc.py"


def test_values_are_the_q245_literature_bounds():
    R = rom.ROM
    # Q245: the Q241 AAOS-style values were re-checked against the literature (docs/pose_rom_table.md); the values below are the Q245 bounds
    want = {"shoulder_flex": (-60, 179), "shoulder_rot": (-93, 74), "elbow_flex": (0, 150), "forearm_sup": (-84, 91), "wrist_flex": (-76, 79), "wrist_dev": (-38, 23),
            "finger_mcp": (-45, 90), "finger_pip": (0, 100), "hip_flex": (-18, 132), "hip_abd": (-30, 39), "hip_rot": (-40, 34), "knee_flex": (0, 140), "ankle_dp": (-50, 29), "ankle_inv": (-15, 35),
            "cerv_flex": (-69, 66), "cerv_rot": (-81, 81), "lumb_flex": (-25, 60)}
    for k, (lo, hi) in want.items():
        assert (R[k][0], R[k][1]) == (lo, hi), k
    for k, (lo, hi, lab, src) in R.items():
        assert lo < hi and lo <= 0 <= hi or k in ("finger_pip", "finger_dip", "elbow_flex", "knee_flex", "toe_pip", "toe_dip", "toe1_ip", "thumb_cmc_abd", "thumb_mcp"), k
        assert lab and src, k
    assert any("ASSUMPTION" in v[3] for v in R.values())          # assumptions are labelled as such
    for k in ("shoulder_flex", "elbow_flex", "hip_flex", "knee_flex", "ankle_dp"):
        assert "AAOS" in R[k][3]


def test_spine_shares_sum_to_one():
    for reg, labs in (("cervical", ["OCC", "C1", "C2", "C3", "C4", "C5", "C6", "C7"]), ("thoracic", ["T%d" % i for i in range(1, 13)]), ("lumbar", ["L1", "L2", "L3", "L4", "L5"])):
        for dof in ("flex", "lat", "rot"):
            w = rom.spine_weights(reg, labs, dof)
            assert abs(sum(w) - 1.0) < 1e-9 and all(x >= 0 for x in w), (reg, dof)
    w = rom.spine_weights("cervical", ["OCC", "C1", "C2", "C3", "C4", "C5", "C6", "C7"], "rot")
    assert abs(w[1] - 0.5) < 1e-9 and w[0] == 0.0               # C1/C2 carries half of the cervical rotation


def test_every_slider_range_in_the_rigs_comes_from_the_table():
    for f in sorted((REPO / "data/anatomy").glob("pose_rig_*.json")):
        rig = json.loads(f.read_text(encoding="utf-8"))["rig"]
        assert set(rig["rom"]) <= set(rom.ROM)
        for j in rig["joints"]:
            for d in j["dof"]:
                if d.get("drv"):
                    continue
                assert [d["lo"], d["hi"]] == [rom.ROM[d["rk"]][0], rom.ROM[d["rk"]][1]], (f.name, j["id"], d["k"])
        for r in rig["regions"]:
            for d in r["dof"]:
                assert [d["lo"], d["hi"]] == [rom.ROM[d["rk"]][0], rom.ROM[d["rk"]][1]]
