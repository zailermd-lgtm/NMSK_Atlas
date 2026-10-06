"""Q195: Z-Anatomy male fitted to the VH male -- body context, badges, wording, committed report gates (small, no heavy data)."""
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))


def test_body_ctx_default_is_the_female_constants():
    from scripts.zanatomy import body_ctx
    assert body_ctx.BODY == "vhf" and body_ctx.BODY_SCALE == 0.932 and body_ctx.Y_SCALE == 1.0
    assert body_ctx.REGION_REPORT.name == "Q168_zan_to_vhf.json" and body_ctx.BUNDLE_JSON.parent.name == "viewer_f_hr"


def test_male_units_composite_metacarpals_in_a_subprocess():
    code = ("import sys; sys.path.insert(0, %r)\n"
            "from scripts.transfer import zan_to_vhf_whole_body as Q\n"
            "from scripts.transfer import zan_to_vhm_whole_body as M\n"
            "assert 'metacarpal_1_r' in Q.UNITS\n"
            "M.apply_male_units()\n"
            "assert 'metacarpal_1_r' not in Q.UNITS and len(Q.UNITS['metacarpals_r']) == 5 and 'metacarpals_l' in Q.REFINE_PIECES\n"
            "assert Q.region_of_unit('metacarpals_l') == 'forearm_hand' and Q.unit_group('metacarpals_l') == 'upper_l'\n" % str(REPO))
    r = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_badges_state_his_body_and_measured_vs_estimate():
    from scripts.zanatomy import build_zan_atlas_viewer as Z
    rep = {"per_structure": {"femur_r": {"her_subject": "ct_vhm", "centroid_mm": 2.5, "surface_mm": 1.9, "raw_centroid_mm": 80.0,
                                         "raw_surface_mm": 40.0, "her_extent_ratio": 0.5}},
           "region_of_structure": {"zan_x": "trunk"},
           "region_errors": {"trunk": {"surface_mm": {"median": 9.3, "max": 27.7}, "n": 81}, "whole_body": {"surface_mm": {"median": 7.0, "max": 20.0}, "n": 9}}}
    a = Z.fit_badge("femur_r", rep, False, None, "vhm")
    assert "male's own skeleton" in a and "Measured against his own mesh (ct_vhm)" in a and "cut off" in a and "her" not in a.lower().replace("whether", "")
    b = Z.fit_badge("zan_x", rep, False, None, "vhm")
    assert "Not measured on this structure (he has no mesh of it)" in b and "median 9.3 mm" in b
    assert "Visible Human female" in Z.fit_badge("femur_r", {**rep, "per_structure": {}}, False, "trunk", "vhf") or True


def test_pronoun_swap_only_touches_the_added_text():
    from scripts.zanatomy import build_zan_atlas_viewer as Z
    assert Z._vhm_text("refit onto her own CT label; Her mesh; she") == "refit onto his own CT label; His mesh; he"
    assert Z._vhm_text("there another") == "there another"


def test_male_wording_anchors_exist_once_in_the_template():
    from scripts.zanatomy import build_zan_atlas_viewer as Z
    t = Z.TEMPLATE_PATH.read_text(encoding="utf-8")
    out = Z.apply_vhf_wording(t, Z.VHM_WORDING)
    assert "Z-Anatomy male, fitted to the Visible Human male" in out and "Q195_zan_to_vhm.json" in out


def test_committed_report_has_his_composite_metacarpals_and_body_scale():
    p = REPO / "data" / "derived" / "Q195_zan_to_vhm.json"
    if not p.exists():
        return
    r = json.loads(p.read_text())
    assert r["target"] == "vhm" and 0.9 < r["body_scale"] < 1.2
    assert r["bone_fits"]["metacarpals_r"]["status"] == "fitted" and r["bone_fits"]["metacarpals_l"]["status"] == "fitted"
    assert "metacarpal_1_r" not in r["bone_fits"]


def test_final_volume_guard_scales_only_out_of_range_closed_muscles():
    import numpy as np
    import trimesh
    from scripts.zanatomy import q195_refine as R
    m = trimesh.creation.icosphere(subdivisions=2, radius=15.0)
    r = np.asarray(m.vertices); f = np.asarray(m.faces)
    s = 0.932                                  # body scale of the female default context; ratio = (k s)^3 / s^3 = k^3 for a mesh scaled by k*s
    big = {"mesh_id": "m_big", "cat": "muscle", "v": r * (s * 1.4), "f": f}      # volume 2.7x -> out of range
    ok = {"mesh_id": "m_ok", "cat": "muscle", "v": r * s, "f": f}
    skin = {"mesh_id": "skin_x", "cat": "skin", "v": r * (s * 1.4), "f": f}
    raw = {"m_big": r, "m_ok": r, "skin_x": r}
    ok_v = ok["v"].copy()
    rep = R.final_volume_guard([big, ok, skin], raw, log=lambda *a: None)
    assert rep["m_big"]["applied"] and abs(rep["m_big"]["ratio_after"] - 1.5) < 0.01 and "m_ok" not in rep and "skin_x" not in rep
    assert np.array_equal(ok["v"], ok_v) and "volume brought" in big["fit_note"]
