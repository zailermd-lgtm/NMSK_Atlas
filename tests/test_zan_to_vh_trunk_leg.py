"""Q62 step 9: Z-Anatomy trunk + small lower-limb muscles onto BOTH own-model bodies (zan_to_vh_trunk_leg.py)."""
import json
from pathlib import Path

import pytest

from scripts.transfer import zan_to_vh_trunk_leg as TL

REPO = Path(__file__).resolve().parents[1]


def test_region_table_ids_are_entities_and_male_only_never_on_her():
    ents = set(TL.entity_ids())
    assert set(TL.GROUP_OF) <= ents and set(TL.NOT_BUILDABLE) <= ents
    assert not set(TL.GROUP_OF) & set(TL.NOT_BUILDABLE)
    assert TL.MALE_ONLY <= set(TL.NOT_BUILDABLE)
    her = TL.not_built("vhf", set())
    assert all(her[a].startswith("male-only") for a in TL.MALE_ONLY)
    assert all(not TL.not_built("vhm", set())[a].startswith("male-only") for a in TL.MALE_ONLY)
    assert TL.targets("vhf", {"subclavius_r"}) == [a for a in TL.GROUP_OF if a != "subclavius_r"]
    assert TL.pron("her CT", "vhf") == "her CT" and TL.pron("her CT", "vhm") == "his CT"


@pytest.mark.parametrize("t", ["vhf", "vhm"])
def test_shipped_rows_pass_gates(t):
    rp = TL.TARGETS[t]["report"]
    if not rp.exists():
        pytest.skip("report not built")
    d = json.loads(rp.read_text())
    if t == "vhf":
        assert not TL.MALE_ONLY & set(d["summary"]["targets"])
    for aid in d["summary"]["shipped"]:
        r = d["rows"][aid]
        assert r["outside_skin_frac_after"] == 0.0
        assert r["inside_bone_frac_after_push"] <= TL.MAX_INSIDE_BONE
        assert r["inside_lung_frac"] <= TL.MAX_IN_LUNG
        assert r["overlap_frac_total"] <= TL.MAX_OVERLAP
        assert r["carrier_local"]["median_mm"] <= TL.MAX_CARRIER_MM
        assert r["volume_kept_after_fix"] >= TL.MIN_VOL_KEPT and r["skin_moved_frac"] <= TL.MAX_SKIN_MOVED
        assert "Q62 step 9: TRANSFERRED" in r["badge"] and (t == "vhf" or " her " not in r["badge"])
