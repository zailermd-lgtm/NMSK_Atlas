"""Q62 step 7: head/neck/larynx muscles transferred onto the VH female's own bones (zan_to_vhf_head_neck)."""
import json
from pathlib import Path

import numpy as np
import pytest

from scripts.transfer import zan_to_vhf_head_neck as H

REPO = Path(__file__).resolve().parents[1]


def test_ids_are_existing_entities_and_disjoint_from_not_mapped():
    tg = H.targets()
    assert len(tg) == len(set(tg)) == 58
    for aid in list(tg) + list(H.NOT_MAPPED):
        assert (REPO / "data" / "muscles" / "head_and_neck" / f"{aid}.json").exists(), aid
    assert not set(tg) & set(H.NOT_MAPPED)
    assert H.zan_parts("thyroarytenoid_r") == ["zan_external_part_of_thyro_arytenoid_muscle_r",
                                                "zan_thyro_epiglottic_part_of_thyro_arytenoid_muscle_r"]
    assert H.zan_parts("frontalis_l") == ["frontalis_l"]


def test_mask_lookup_inverts_voxels_to_atlas():
    from engine import volume_ingest as vol
    A = np.array([[-0.938, 0, 0, 240.0], [0, -0.938, 0, 240.0], [0, 0, 1.0, -1022.0], [0, 0, 0, 1]])
    O = np.array([7.769, -885.229, 14.137])
    m = np.zeros((20, 20, 20), bool); m[5, 6, 7] = True
    p = vol.voxels_to_atlas(np.array([[5.0, 6.0, 7.0]]), A) - O
    look = H.MaskLookup(m, A, O)
    assert look(p)[0] and not look(p + 5.0)[0]
    assert np.allclose(H.to_vox(p, A, O), [[5, 6, 7]])


def test_shipped_rows_pass_gates():
    rp = REPO / "data" / "derived" / "Q62s7_vhf_head_neck.json"
    if not rp.exists():
        pytest.skip("report not built")
    d = json.loads(rp.read_text())
    for aid in d["summary"]["shipped"]:
        r = d["rows"][aid]
        assert r["outside_skin_frac_after"] == 0.0
        assert r["inside_bone_frac_after"] <= H.MAX_INSIDE_BONE
        assert r["inside_airway_frac"] <= H.MAX_IN_AIRWAY
        assert r["overlap_frac_total"] <= H.MAX_OVERLAP
        assert r["carrier_local"]["median_mm"] <= H.MAX_CARRIER_MM
        assert not d["summary"]["group_carrier"][r["group"]]["held"]
        assert "TRANSFERRED" in r["badge"] and "Z-Anatomy" in r["badge"]
