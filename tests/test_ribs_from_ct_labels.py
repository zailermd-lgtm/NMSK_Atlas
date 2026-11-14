"""Q182: ribs re-surfaced from the CT rib labels (scripts/ribs_from_ct_labels.py)."""
import re
from pathlib import Path

from scripts.ribs_from_ct_labels import LABELS, mapping, merge_records

REPO = Path(__file__).resolve().parents[1]


def _rec(aid, vo, vc, fo, fc, lo, hi, src):
    return {"atlas_id": aid, "source_structure": src, "source_file": f"v.nii.gz#{src}", "vertex_offset": vo,
            "vertex_count": vc, "face_offset": fo, "triangle_count": fc, "bbox_min_mm": lo, "bbox_max_mm": hi}


def test_mapping_is_the_24_rib_labels_onto_two_ids():
    m = mapping("vhf")
    assert [e["label"] for e in m["entries"]] == list(range(92, 116))
    assert {e["atlas_id"] for e in m["entries"]} == set(LABELS)
    assert all(e["source_structure"].startswith("rib_" + ("left" if e["atlas_id"] == "ribs_l" else "right"))
               for e in m["entries"])


def test_merge_records_one_piece_per_side_contiguous_only():
    s = [_rec("ribs_l", 0, 10, 0, 16, [0, 0, 0], [1, 1, 1], "a"), _rec("ribs_l", 10, 5, 16, 6, [-1, 0, 0], [1, 2, 1], "b"),
         _rec("ribs_r", 15, 4, 22, 4, [5, 5, 5], [6, 6, 6], "c")]
    out = merge_records(s)
    assert [r["atlas_id"] for r in out] == ["ribs_l", "ribs_r"]
    assert out[0]["vertex_count"] == 15 and out[0]["triangle_count"] == 22 and out[0]["vertex_offset"] == 0
    assert out[0]["bbox_min_mm"] == [-1, 0, 0] and out[0]["bbox_max_mm"] == [1, 2, 1]
    assert s[0]["vertex_count"] == 10   # input untouched
    gap = [s[0], _rec("ribs_l", 11, 5, 16, 6, [0, 0, 0], [1, 1, 1], "b")]
    assert len(merge_records(gap)) == 2


def test_rebuild_scripts_list_rib_subject_before_the_body_subject():
    m = (REPO / "scripts" / "vhm_rebuild_bundle.sh").read_text()
    f = (REPO / "scripts" / "cryo" / "vhf_rebuild_bundle.sh").read_text()
    assert re.search(r"ct_vhm_ribs (ct_vhm_ccart )?ct_vhm ", m) and "ribs_from_ct_labels.py build --body vhm" in m
    assert "--subject ct_vhf_ribs --subject ct_vhf " in f and "ribs_from_ct_labels.py build --body vhf" in f


def test_trunk_transfer_rides_the_rib_refit_and_report_differs_only_in_ribs():
    import json
    for t, p in (("vhm", "scripts/vhm_rebuild_bundle.sh"), ("vhf", "scripts/cryo/vhf_rebuild_bundle.sh")):
        assert f"zan_to_vh_trunk_leg.py --target {t} --q168 data/derived/Q182_q168_ribrefit_{t}.json" in (REPO / p).read_text()
        old = json.loads((REPO / "data" / "derived" / f"Q168_zan_to_{t}.json").read_text())["bone_fits"]
        new = json.loads((REPO / "data" / "derived" / f"Q182_q168_ribrefit_{t}.json").read_text())["bone_fits"]
        assert set(old) == set(new)
        assert {u for u in old if json.dumps(old[u], sort_keys=True) != json.dumps(new[u], sort_keys=True)} == {"ribs_l", "ribs_r"}
        assert all(new[r]["residual_mm"] < old[r]["residual_mm"] for r in ("ribs_l", "ribs_r"))
