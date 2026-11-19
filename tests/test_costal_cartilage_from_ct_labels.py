"""Q183: his costal cartilages from his own CT label 117 (scripts/costal_cartilage_from_ct_labels.py)."""
import re
from pathlib import Path

from scripts.costal_cartilage_from_ct_labels import IDS, badge, fix_manifest, mapping

REPO = Path(__file__).resolve().parents[1]


def test_mapping_is_label_117_split_at_the_sternum_midline():
    (e,) = mapping()["entries"]
    assert e["label"] == 117 and e["source_structure"] == "costal_cartilages"
    assert e["splitter"] == "midline" and e["split_parts"] == {"right": "costal_cartilage_r", "left": "costal_cartilage_l"}
    assert mapping()["source_volume"].endswith("vhm_total.nii.gz")


def test_fix_manifest_sets_side_and_is_idempotent():
    m = {"structures": [{"atlas_id": a, "side": None} for a in IDS.values()], "attribution": ["x"]}
    m = fix_manifest(fix_manifest(m))
    assert [s["side"] for s in m["structures"]] == list(IDS)
    assert len(m["attribution"]) == 2


def test_rebuild_lists_own_cartilage_before_s1159_and_badges_the_rest():
    sh = (REPO / "scripts" / "vhm_rebuild_bundle.sh").read_text()
    order = re.search(r"for s in (ct_vhm_foot .*?); do SUBJ", sh).group(1).split()
    assert order.index("ct_vhm_ccart") < order.index("ct_s1159") and order.index("ct_vhm_ccart") < order.index("ct_vhm")
    assert "costal_cartilage_from_ct_labels.py build" in sh and "costal_cartilage_from_ct_labels.py stamp" in sh
    r = {"should_touch": {"aorta": 18.2}, "outside_skin_frac": 0.0, "in_his_bone_frac": 0.509, "in_his_lung_frac": 0.0,
         "his_own_label": {"name": "aorta", "mesh_to_label_median_mm": 59.2}}
    b = badge("abdominal_aorta", r)
    assert "NOT HIS GEOMETRY" in b and "s1159" in b and "50.9 % inside his bone" in b and "59.2 mm" in b
