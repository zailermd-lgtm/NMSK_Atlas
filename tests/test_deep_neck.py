"""The pure rule functions of scripts/cryo/vhf_deep_neck_from_cryo.py without the frame: the band from the bone at the
posterior midline, the depth fraction, the box rules tiling every band's compartment, the prevertebral cut, the
merge decision, and the consistency of the shipped label key with the subject mapping."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
from scripts.cryo import vhf_deep_neck_from_cryo as dn  # noqa: E402


def test_band_follows_the_bone_at_the_posterior_midline():
    assert dn.band_of([44], False) == "A"                      # C7 spinous process
    assert dn.band_of([49, 50], False) == "B"                  # C2 (its spine) wins over a C1 crumb
    assert dn.band_of([50], True) == "C"                       # C1 posterior arch
    assert dn.band_of([], True) == "D"                         # the atlanto-occipital interval
    assert dn.band_of([], False) == "A"                        # an interspinous gap lower down
    assert dn.band_of([91], True, 4) == "E"                    # occipital squama, below the inferior nuchal line
    assert dn.band_of([91], True, dn.SUBOCC_ABOVE_RIM_MM + 1) == "E_high"


def test_depth_fraction_runs_from_the_bone_to_the_trapezius():
    first = np.array([10.0, np.nan]); last = np.array([30.0, np.nan])
    f = dn.depth_fraction((40, 2), first, last)
    assert f[10, 0] == 0.0 and f[30, 0] == 1.0 and abs(f[20, 0] - 0.5) < 1e-9
    assert np.isnan(f[:, 1]).all()                             # an empty column has no depth


def test_box_rules_tile_each_band_without_overlap():
    dx, f = np.meshgrid(np.arange(0, 55, 0.5), np.arange(0, 1.0, 0.01))
    for band, rules in dn.BOX_RULES.items():
        cover = np.zeros(dx.shape, int)
        for boxes in rules.values():
            for dx0, dx1, f0, f1 in boxes:
                cover += ((dx >= dx0) & (dx < dx1) & (f >= f0) & (f < f1)).astype(int)
        assert cover.max() == 1, f"band {band}: overlapping boxes"
        assert cover.min() == 1, f"band {band}: a gap in the tiling"


def test_rule_regions_put_the_layers_in_order():
    H, W = 60, 80; comp = np.zeros((H, W), bool); comp[10:50, 0:60] = True      # 40 px thick, 60 px wide, right side
    dx = np.tile(np.arange(W, dtype=float), (H, 1)); first = np.where(comp.any(axis=0), 10.0, np.nan); last = np.where(comp.any(axis=0), 49.0, np.nan)
    f = dn.depth_fraction((H, W), first, last)
    r = dn.rule_regions("A", dx, f, comp)
    assert set(r) == {"semispinalis_cervicis", "semispinalis_capitis", "splenius", "erector_cervical"}
    ys = {nm: np.where(m[:, 5])[0] for nm, m in r.items() if m[:, 5].any()}     # a medial column
    assert ys["semispinalis_cervicis"].max() < ys["semispinalis_capitis"].min() < ys["semispinalis_capitis"].max() < ys["splenius"].min()
    assert not r["semispinalis_cervicis"][:, 40].any() and r["erector_cervical"][:, 40].any()   # lateral of 20 mm: erector
    rc = dn.rule_regions("C", dx, f, comp)
    assert "rectus_capitis_posterior_minor" in rc and "obliquus_capitis_inferior" in rc and "semispinalis_cervicis" not in rc
    assert "obliquus_capitis_superior" in dn.rule_regions("D", dx, f, comp)


def test_prevertebral_cut_is_at_the_body_half_width():
    pv = np.zeros((10, 40), bool); pv[2:8, 0:30] = True
    dx = np.tile(np.arange(40, dtype=float), (10, 1))
    r = dn.prevertebral_regions(pv, dx, body_half_width=12.0, above_c6=True)
    assert r["longus_colli"][:, 8].any() and not r["longus_colli"][:, 10].any()      # cut at 0.75 x 12 = 9 mm
    assert r["longus_capitis"][:, 10].any()
    assert set(dn.prevertebral_regions(pv, dx, 12.0, above_c6=False)) == {"longus_colli"}


def test_merge_decision_and_groups():
    d = dn.merge_decision({("a", "b"): [(100, 1.0), (100, 1.2)], ("b", "c"): [(50, 3.0)]}, ratio=1.25)
    assert d[("a", "b")][2] is True and d[("b", "c")][2] is False
    g = dn.merge_groups({("rectus_capitis_posterior_major", "rectus_capitis_posterior_minor"),
                         ("erector_cervical", "rectus_capitis_posterior_major")})
    assert g == [frozenset({"rectus_capitis_posterior_major", "rectus_capitis_posterior_minor"})]   # the sink never merges
    assert dn.group_name(g[0]) == "suboccipital_group"
    assert dn.group_name(frozenset({"longus_colli", "longus_capitis"})) == "longus_group"


def test_relabel_keeps_right_then_left_blocks():
    ids = {nm: i + 1 for i, nm in enumerate(dn.MUSCLES)}
    final, labels, lut_r, lut_l = dn.relabel(ids, [frozenset({"rectus_capitis_posterior_major", "rectus_capitis_posterior_minor"})])
    n = len(final)
    assert labels[1][3] == "right" and labels[n + 1][3] == "left" and len(labels) == 2 * n
    assert lut_r[ids["rectus_capitis_posterior_major"]] == lut_r[ids["rectus_capitis_posterior_minor"]]
    assert lut_l[ids["splenius"]] == lut_r[ids["splenius"]] + n


KEY = REPO / "mappings/vhf_deep_neck_labels.json"
MAPPING = REPO / "mappings/subjects/ct_vhf_dneck_volume_mapping.json"


@pytest.mark.skipif(not (KEY.exists() and MAPPING.exists()), reason="deep neck volume not built")
def test_shipped_key_and_mapping_agree():
    key = json.load(open(KEY)); mp = json.load(open(MAPPING))
    assert key["badge"] == "rule-based" and mp["label_map"] == "vhf_deep_neck" and mp["subject"] == "ct_vhf_dneck"
    by_label = {e["label"]: e for e in mp["entries"]}
    assert set(map(int, key["labels"])) == set(by_label)
    ids = set()
    for p in (REPO / "data/muscles").rglob("*.json"):
        d = json.load(open(p)); ids |= {e["id"] for e in (d if isinstance(d, list) else [d]) if isinstance(e, dict) and "id" in e}
    for lid, name in key["labels"].items():
        e = by_label[int(lid)]
        assert e["source_structure"] == name and name.endswith("_" + e["side"])
        assert key["atlas"][name]["atlas_id"] == e["atlas_id"]
        if e["atlas_id"]:
            assert e["atlas_id"] in ids, e["atlas_id"]
            assert e["atlas_id"].endswith("_r" if e["side"] == "right" else "_l")
        else:
            assert e["relationship"] == "no_usable_label"
    for name, members in key["merged_compartments"].items():
        assert key["atlas"][name + "_right"]["atlas_id"] is None and len(members) >= 2
    shipped = [e["atlas_id"] for e in mp["entries"] if e["atlas_id"]]
    assert len(shipped) == len(set(shipped))                    # no entity claimed twice
