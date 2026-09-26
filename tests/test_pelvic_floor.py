"""The pure rule functions of scripts/cryo/vhf_pelvic_floor_from_cryo.py exercised on a synthetic female pelvis,
without the cryosection frame: the level anchors (the apex of the pubic arch, the ischial spine), the pelvic boxes
(obturator internus band, the levator ani lining the cavity, the coccygeus behind the anal canal), the perineal
boxes (deep pouch above, superficial pouch below), the merge decision and naming, the plausibility gate, and the
consistency of the shipped label key with the subject mapping."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from scripts.cryo import vhf_pelvic_floor_from_cryo as pf  # noqa: E402


# ---- a synthetic pelvis ------------------------------------------------------------------------------------------
H = W = 120
MID, ANAL_ROW = 60.0, 70.0          # the midline column and the anal canal's centre row


def fields(k=0, side=+1):
    """(dx, dy, d_bone, d_visc) for one side of a synthetic level: the pelvic ring is a circle of radius 40 about
    (60, 60) and the viscera a disc of radius 12 about the anal canal's centre."""
    yy, xx = np.mgrid[0:H, 0:W]
    dx = side * (xx - MID)
    dy = yy - ANAL_ROW
    r = np.hypot(yy - 60.0, xx - MID)
    d_bone = np.abs(40.0 - r)                       # distance to the bony ring
    d_visc = np.maximum(np.hypot(yy - ANAL_ROW, xx - MID) - 12.0, 0.0)
    return dx, dy, d_bone, d_visc


def test_pubic_arch_apex_is_the_lowest_level_that_is_still_closed():
    # the symphysis closes the ring from level 98 upwards; below it the rami diverge
    gaps = {k: (0.0 if k >= 98 else 18.0 + float(98 - k) * 4) for k in range(70, 130)}
    assert pf.arch_apex_k(gaps, 70, 116) == 98
    gaps[95] = 1.0                                  # a stray closed level well below the arch is not the apex
    assert pf.arch_apex_k(gaps, 70, 116) == 98


def test_ischial_spine_is_where_the_posterior_hip_reaches_furthest_medially():
    medial = {k: 60.0 + abs(k - 138) * 0.8 for k in range(106, 150)}
    assert pf.spine_k(medial, 106, 149) == 138
    assert pf.spine_k({}, 106, 149) is None


def test_obturator_internus_takes_the_band_on_the_bone_and_the_levator_lines_the_cavity():
    dx, dy, d_bone, d_visc = fields(k=100)
    boxes = pf.pelvic_boxes(dx, dy, d_bone, d_visc, k=100, k_spine=138)
    oi, lev = boxes["obturator_internus"], boxes["levator_ani"]
    assert not (oi & lev).any()                                     # the boxes tile, they do not overlap
    # a point on the bony ring, well off the midline, is obturator internus
    assert oi[60, 60 - 38] and not lev[60, 60 - 38]
    # a point just outside the viscera, medial to the bone band, is levator ani
    assert lev[int(ANAL_ROW), int(MID) - 14] and not oi[int(ANAL_ROW), int(MID) - 14]
    # nothing further than LEV_REACH_MM from the viscera is levator ani
    far = d_visc > pf.LEV_REACH_MM
    assert not (lev & far).any()


def test_coccygeus_only_exists_behind_the_anal_canal_near_the_ischial_spine():
    dx, dy, d_bone, d_visc = fields()
    low = pf.pelvic_boxes(dx, dy, d_bone, d_visc, k=100, k_spine=138)
    assert "coccygeus" not in low                                   # 38 mm below the spine: out of range
    high = pf.pelvic_boxes(dx, dy, d_bone, d_visc, k=138, k_spine=138)
    cocc = high["coccygeus"]
    assert cocc.any()
    assert (dy[cocc] >= pf.COCC_POST_MM).all()                      # never anterior to the anal canal's centre
    assert (dx[cocc] >= pf.COCC_MIN_DX).all()                       # never on the midline raphe
    assert not (cocc & high["levator_ani"]).any()


def test_deep_pouch_above_the_arch_superficial_below():
    dx, dy, d_bone, _ = fields()
    deep = pf.perineal_boxes(dx, dy, d_bone, k=96, k_arch=98, k_hip_bot=72)
    shallow = pf.perineal_boxes(dx, dy, d_bone, k=80, k_arch=98, k_hip_bot=72)
    assert "deep_transverse_perineal" in deep and "bulbospongiosus" not in deep
    assert "bulbospongiosus" in shallow and "deep_transverse_perineal" not in shallow
    bs = shallow["bulbospongiosus"]
    assert (dy[bs] <= -pf.UG_POST_MM).all()                         # anterior to the anal canal, by the vagina
    assert (dx[bs] <= pf.BS_LAT_MM).all()
    for boxes in (deep, shallow):                                   # the boxes tile the region exactly once
        stack = np.stack(list(boxes.values()))
        assert (stack.sum(axis=0) == 1).all()


def test_superficial_transverse_perineal_only_at_the_tuberosity_levels():
    dx, dy, d_bone, _ = fields()
    at = pf.perineal_boxes(dx, dy, d_bone, k=76, k_arch=98, k_hip_bot=72)
    above = pf.perineal_boxes(dx, dy, d_bone, k=88, k_arch=98, k_hip_bot=72)
    assert "superficial_transverse_perineal" in at
    assert "superficial_transverse_perineal" not in above
    stp = at["superficial_transverse_perineal"]
    assert (dy[stp] >= pf.STP_DY_MM[0]).all() and (dy[stp] <= pf.STP_DY_MM[1]).all()


def test_ischiocavernosus_sits_on_the_ramus():
    dx, dy, d_bone, _ = fields()
    boxes = pf.perineal_boxes(dx, dy, d_bone, k=80, k_arch=98, k_hip_bot=72)
    ic = boxes["ischiocavernosus"]
    assert ic.any()
    assert (d_bone[ic] <= pf.IC_MM).all() and (dx[ic] >= pf.IC_MIN_DX).all()


def test_merge_decision_and_grouping():
    support = {("a", "b"): [(100, 1.0), (100, 1.1)],        # no septum -> merge
               ("b", "c"): [(50, 2.0)],                     # a pale ridge -> keep apart
               ("a", "obturator_internus"): [(80, 1.0)]}    # a sink never merges into a shipped group
    dec = pf.merge_decision(support)
    assert dec[("a", "b")][2] is True and dec[("b", "c")][2] is False
    groups = pf.merge_groups({p for p, d in dec.items() if d[2]})
    assert groups == [frozenset({"a", "b"})]


def test_group_names_follow_the_anatomy():
    assert pf.group_name(frozenset({"levator_ani", "coccygeus"})) == "pelvic_diaphragm"
    assert pf.group_name(frozenset({"bulbospongiosus", "ischiocavernosus"})) == "perineal_muscles"
    assert pf.group_name(frozenset({"deep_transverse_perineal",
                                    "superficial_transverse_perineal"})) == "transverse_perineal_compartment"
    assert pf.group_name(frozenset({"deep_transverse_perineal", "bulbospongiosus",
                                    "ischiocavernosus"})) == "urogenital_diaphragm"


def test_plausibility_gate():
    assert pf.plausibility("levator_ani", 40.0, 40, 20.0) is None
    assert "more than" in pf.plausibility("levator_ani", 200.0, 40, 100.0)
    assert "levels" in pf.plausibility("coccygeus", 4.0, 2, 4.0)
    assert "cm3" in pf.plausibility("coccygeus", 0.4, 20, 0.4)


# ---- the shipped artefacts ---------------------------------------------------------------------------------------
KEY = REPO / "mappings/vhf_pelvic_floor_labels.json"
MAPPING = REPO / "mappings/subjects/ct_vhf_pfloor_volume_mapping.json"


@pytest.mark.skipif(not KEY.exists() or not MAPPING.exists(), reason="the volume has not been built")
def test_key_and_mapping_agree_and_nothing_unsupported_is_mapped():
    key = json.loads(KEY.read_text())
    mapping = json.loads(MAPPING.read_text())
    assert mapping["subject"] == "ct_vhf_pfloor" and mapping["label_map"] == "vhf_pelvic_floor"
    assert {str(e["label"]): e["source_structure"] for e in mapping["entries"]} == key["labels"]
    for e in mapping["entries"]:
        base = e["source_structure"].replace("_right", "").replace("_left", "")
        if base in pf.SINKS:
            assert e["atlas_id"] is None, f"{e['source_structure']} is a sink and must not be mapped"
        if e["atlas_id"] is None:
            assert e["note"], "every unmapped label must say why"
        else:
            assert e["atlas_id"].startswith(pf.ATLAS_OF[base])


@pytest.mark.skipif(not MAPPING.exists(), reason="the volume has not been built")
def test_every_mapped_entity_exists_in_the_atlas():
    mapping = json.loads(MAPPING.read_text())
    for e in mapping["entries"]:
        if e["atlas_id"]:
            assert (REPO / f"data/muscles/trunk/{e['atlas_id']}.json").exists(), e["atlas_id"]
