"""Q186: Z-Anatomy viewer inventory accounting and skin inclusion."""
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.zanatomy.zan_inventory_audit import classify_objects  # noqa: E402
from scripts.zanatomy.build_zan_atlas_viewer import (  # noqa: E402
    MALE_ONLY_SKIN, SKIN_LAYER, classify_layer, skin_pool,
)


def _inv(name, system, side=None, faces=10, lic="CC-BY-SA-4.0"):
    return {"name": name, "system": system, "side": side, "face_count": faces, "vertex_count": 20, "license": lic}


def test_every_source_object_gets_exactly_one_reason():
    src = [
        {"name": "Regions of face.g", "file": "Regions of human body100.fbx", "system": "Integument", "type": "EMPTY"},
        {"name": "Abduction", "file": "References100.fbx", "system": "References", "type": "MESH"},
        {"name": "Gnathion.j", "file": "SkeletalSystem100.fbx", "system": "Skeletal", "type": "MESH"},
        {"name": "Pisohamate ligament.l", "file": "Joints100.fbx", "system": "Joints", "type": "MESH"},
        {"name": "Kidney.l", "file": "VisceralSystem100.fbx", "system": "Visceral", "type": "MESH"},
        {"name": "Biceps brachii muscle.l", "file": "MuscularSystem100.fbx", "system": "Muscular", "type": "MESH"},
        {"name": "Biceps brachii muscle.el", "file": "MuscularSystem100.fbx", "system": "Muscular", "type": "MESH"},
        {"name": "Biceps brachii muscle.l", "file": "SkeletalSystem100.fbx", "system": "Skeletal", "type": "MESH"},
        {"name": "Short head of biceps.l", "file": "MuscularSystem100.fbx", "system": "Muscular", "type": "MESH"},
        {"name": "Urogenital region.l", "file": "Regions of human body100.fbx", "system": "Integument", "type": "MESH"},
        {"name": "Pubic hairs", "file": "Regions of human body100.fbx", "system": "Integument", "type": "MESH"},
        {"name": "Lost thing.r", "file": "MuscularSystem100.fbx", "system": "Muscular", "type": "MESH"},
    ]
    inventory = {o["name"]: o for o in [
        _inv("Kidney.l", "Visceral", "left", lic="CC-BY-NC-4.0 (EXCLUDED)"),
        _inv("Biceps brachii muscle.l", "Muscular", "left"),
        _inv("Biceps brachii muscle.el", "Muscular", "left"),
        _inv("Short head of biceps.l", "Muscular", "left"),
        _inv("Urogenital region.l", "Integument", "left"),
        _inv("Pubic hairs", "Integument"),
        _inv("Lost thing.r", "Muscular", "right"),
    ]}
    prov = {"biceps_brachii_l": {"route": "matched", "sources": ["Biceps brachii muscle.l", "Short head of biceps.l"]},
            "zan_skin_urogenital_region_l": {"route": "skin", "sources": ["Urogenital region.l"]}}
    rows = classify_objects(src, inventory, {"entries": []}, prov, set(prov))
    got = {(r["file"][:4], r["name"]): r["reason"] for r in rows}
    assert len(rows) == len(src) and all(r["status"] in ("in_viewer", "absent") for r in rows)
    assert got[("Regi", "Regions of face.g")] == "group_node"
    assert got[("Refe", "Abduction")] == "reference_diagram"
    assert got[("Skel", "Gnathion.j")] == "pin_marker"
    assert got[("Join", "Pisohamate ligament.l")] == "source_placeholder"
    assert got[("Visc", "Kidney.l")] == "excluded_nc_licensed"
    assert got[("Musc", "Biceps brachii muscle.l")] == "shipped_merged"
    assert got[("Musc", "Biceps brachii muscle.el")] == "origin_insertion_decal"
    assert got[("Skel", "Biceps brachii muscle.l")] == "source_placeholder"  # not extracted under Skeletal
    assert got[("Regi", "Urogenital region.l")] == "shipped"
    assert got[("Regi", "Pubic hairs")] == "hair_not_shipped"
    assert got[("Musc", "Lost thing.r")] == "not_shipped_unexplained"
    # female variant: the dropped male-only skin is reported as such, never as unexplained
    rows_f = classify_objects(src, inventory, {"entries": []}, prov, {"biceps_brachii_l"},
                              {"zan_skin_urogenital_region_l"})
    assert {r["name"]: r["reason"] for r in rows_f}["Urogenital region.l"] == "male_only_not_on_female"


def test_skin_pool_one_id_per_object_hair_off_and_male_skin_listed():
    inv = {"objects": [
        {"name": "Frontal region.l", "side": "left"}, {"name": "Frontal region.r", "side": "right"},
        {"name": "Nail plate (foot).l", "side": "left"}, {"name": "Hairs of head", "side": None},
        {"name": "Urogenital region.r", "side": "right"}, {"name": "Pubic hairs", "side": None}]}
    pool = skin_pool(inv)
    assert set(pool) == {"zan_skin_frontal_region_l", "zan_skin_frontal_region_r", "zan_skin_nail_plate_foot_l",
                         "zan_skin_urogenital_region_r"}
    assert pool["zan_skin_frontal_region_l"]["name"] == "Frontal region (skin)"
    assert pool["zan_skin_nail_plate_foot_l"]["name"] == "Nail plate (foot)"
    assert "zan_skin_hairs_of_head" in skin_pool(inv, with_hair=True)
    assert {"zan_skin_urogenital_region_l", "zan_skin_urogenital_region_r", "zan_skin_pubic_hairs"} <= MALE_ONLY_SKIN
    assert classify_layer("skin", "Frontal region (skin)") == SKIN_LAYER


def test_committed_inventory_accounts_for_every_object_and_ships_the_skin():
    path = REPO_ROOT / "data" / "derived" / "Q186_zan_inventory.json"
    if not path.exists():
        pytest.skip("Q186 inventory not built")
    d = json.loads(path.read_text())
    for v in ("male", "female"):
        assert "not_shipped_unexplained" not in d["counts_by_reason"][v]
        assert not d["viewer_totals"][v]["provenance_ids_missing_from_page"]
    by = {(r["file"], r["name"]): r for r in d["rows"]}
    face = by[("Regions of human body100.fbx", "Nasal region.l")]
    assert face["male"]["status"] == face["female"]["status"] == "in_viewer"
    uro = by[("Regions of human body100.fbx", "Urogenital region.r")]
    assert uro["male"]["status"] == "in_viewer" and uro["female"]["reason"] == "male_only_not_on_female"
    assert all(r["male"]["reason"] == "excluded_nc_licensed" for r in d["rows"]
               if (r.get("licence") or "CC-BY-SA").startswith("CC-BY-NC"))
