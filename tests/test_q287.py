"""Q287: Combined · Female gets her own skin, her CT breasts and their fibroglandular tissue (browser behaviour:
scripts/anatomy/q287/verify_q287.py)."""
import base64
import json
import sys
import zlib
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts/anatomy/q287"))


def _rep(name):
    return json.loads((REPO / "data/derived" / name).read_text())


def test_fgt_rule_is_the_stated_threshold():
    import breast_fgt_q287 as F
    ct = np.array([-200, -100, -31, -30, 0, 60, 200], np.float32).reshape(1, 1, 7)
    breast = np.ones_like(ct, bool)
    none, deep = np.zeros_like(breast), np.ones_like(breast)
    assert F.fgt_rule(breast, ct, none, deep).ravel().tolist() == [False, False, False, True, True, True, True]
    excl = none.copy(); excl[..., 5] = True
    shallow = deep.copy(); shallow[..., 4] = False
    assert F.fgt_rule(breast, ct, excl, shallow).ravel().tolist() == [False, False, False, True, False, False, True]
    assert not F.fgt_rule(~breast, ct, none, deep).any()


def test_fgt_both_sides_shipped_inside_her_breast_and_in_the_cited_range():
    r = _rep("Q287_breast_fgt_report.json")
    assert r["shipped"] == ["breast_fgt_ct_r", "breast_fgt_ct_l"] and not r["held"]
    lo, hi = r["gates"]["vgf_range"]
    for s in r["sides"].values():
        assert s["outside_breast_gt1mm_frac"] <= 0.01 and abs(s["shipped_vs_voxels"] - 1) <= 0.10
        assert lo <= s["glandular_fraction"] <= hi
        assert abs(s["glandular_fraction"] - s["fgt_voxel_cm3"] / s["breast_cm3"]) < 2e-3
    assert {x["pmid"] for x in r["references"]} == {"23231281", "20095256"}


def test_comb_f_report_adds_her_structures_and_hides_the_replaced_ones():
    r = _rep("Q287_comb_f_report.json")
    assert r["added"] == ["skin_ct_vhf", "breast_ct_r", "breast_ct_l", "breast_fgt_ct_r", "breast_fgt_ct_l"]
    assert r["new_indices"] == [3238, 3239, 3240, 3241, 3242]
    assert r["z_skin_patches_hidden_default"] == 249 and len(r["hra_sculpted_breast_hidden_default"]) == 12
    assert r["her_skin"]["watertight"] and r["non_skin_inside_pct_2mm"] > 99
    for b in list(r["breasts"].values()) + list(r["breast_fgt"].values()):
        assert b["outside_her_skin_gt1mm_pct"] == 0.0


def test_z_template_hides_and_fades_by_default_and_reset_restores_both():
    t = (REPO / "viewer/zan_atlas.template.html").read_text(encoding="utf-8")
    assert "hd: !!rec.hd, fd: !!rec.fd }" in t
    assert "if (o.hd) hidden.add(o); else if (o.fd) faded.add(o);" in t
    assert t.count("hidden.clear(); faded.clear(); hideDefaults();") == 2 and t.count("hidden.clear(); faded.clear(); hideDefaults(); soloLayer = null;") == 1
    assert "hideDefaults(); faded.clear()" not in t


def _rig(key):
    j = json.loads((REPO / f"data/anatomy/pose_rig_{key}.json").read_text())
    return j["rig"], zlib.decompress(base64.b64decode(j["weights_zlib_b64"]))


def test_pose_rigs_carry_the_new_entries_after_the_committed_ones():
    rig, w = _rig("comb_f")
    assert rig["count"] == 3244 and len(rig["nv"]) == 3244          # Q288 spliced one more (her uterus, index 3243)
    covered = {e[0] for e in rig["skin"]} | {i for _, lst in rig["rigid"] for i in lst}
    assert set(range(3238, 3243)) <= covered
    offs = sorted(e[4] for e in rig["skin"]); assert offs == sorted(set(offs)) and offs[-1] < len(w)
    rig, w = _rig("own_f")
    assert rig["count"] == 1051 and len(rig["nv"]) == 1051          # Q288: + her uterus


def test_uterus_on_her_ct_was_measured_not_separable():
    r = _rep("Q287_uterus_ct_feasibility.json")
    u = r["organs"]["uterus"]
    assert u["total_labels"].get("18", 0) / sum(u["total_labels"].values()) > 0.5      # her TS small-bowel label covers most of it
    assert r["dice"] < 0.2
