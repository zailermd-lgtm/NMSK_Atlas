"""Q62 step 7b: the same Z-Anatomy head/neck/larynx (+ foot lumbricals) transfer onto the VH MALE's own bones."""
import json
from pathlib import Path

import pytest

from scripts.transfer import zan_to_vhf_foot_intrinsics as FT
from scripts.transfer import zan_to_vhf_head_neck as H

REPO = Path(__file__).resolve().parents[1]


def test_male_targets_and_female_text_unchanged():
    tg = H.targets("vhm")
    assert len(tg) == len(set(tg)) == 60 and {"platysma_r", "platysma_l"} <= set(tg)
    assert H.targets() == H.targets("vhf") and "platysma_r" not in H.targets()
    for aid in tg:
        assert (REPO / "data" / "muscles" / "head_and_neck" / f"{aid}.json").exists(), aid
    t = "Q62 step 7: she has no mesh; fits her CT"
    assert H.pron(t) == t and H.pron(t, "vhm") == "Q62 step 7b: he has no mesh; fits his CT"
    assert FT.his("her skin") == "her skin" and FT.his("her skin", "vhm") == "his skin"
    assert H.TARGETS["vhm"]["subject"] == "xfer_zan2vhm_head" and FT.TARGETS["vhm"]["subject"] == "xfer_zan2vhm_foot"


@pytest.mark.parametrize("name", ["Q62s7b_vhm_head_neck.json", "Q62s7b_vhm_foot_lumbricals.json"])
def test_male_shipped_rows_pass_gates(name):
    rp = REPO / "data" / "derived" / name
    if not rp.exists():
        pytest.skip("report not built")
    d = json.loads(rp.read_text())
    for aid in d["summary"]["shipped"]:
        r = d["rows"][aid]
        assert r["outside_skin_frac_after"] == 0.0
        assert r["inside_bone_frac_after"] <= H.MAX_INSIDE_BONE
        assert r.get("overlap_frac_total", 0.0) <= H.MAX_OVERLAP
        assert "TRANSFERRED" in r["badge"] and " her " not in r["badge"] and "Q62 step 7b" in r["badge"]
        if "inside_airway_frac" in r:
            assert r["inside_airway_frac"] <= H.MAX_IN_AIRWAY
            assert r["carrier_local"]["median_mm"] <= H.MAX_CARRIER_MM
        else:
            assert r["rides_on"]["weighted_median_fit_mm"] <= FT.MAX_BONE_FIT_MM
