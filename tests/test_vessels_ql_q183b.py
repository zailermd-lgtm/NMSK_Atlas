"""Q183b: his ct_s1159 vessels + quadratus lumborum, route per structure (scripts/vessels_ql_q183b.py)."""
import json
import re
from pathlib import Path

import numpy as np

from scripts.vessels_ql_q183b import GATES, IDS, OWN_SHIP, SHIP, calibre_mm, gate, own_mapping

REPO = Path(__file__).resolve().parents[1]


def test_local_thickness_calibre_of_a_cylinder():
    z, y, x = np.ogrid[:120, :40, :40]
    cyl = np.broadcast_to(((y - 20) ** 2 + (x - 20) ** 2) <= 10 ** 2, (120, 40, 40)).copy()
    assert 19.0 <= calibre_mm(cyl, (1, 1, 1))["median"] <= 21.5


def test_gate_uses_penetration_position_and_calibre():
    r = {"outside_skin_frac": 0.0, "largest_component_share": 1.0, "in_bone_gt1mm_frac": 0.0, "in_lung_gt1mm_frac": 0.0,
         "calibre_mm": {"median": 8.0}, "published": {"within_3sd": True}, "should_touch_mm": {},
         "his_label_fragment": {"voxels": 500, "to_mesh_median_mm": 1.2, "within_5mm_frac": 1.0}}
    assert gate(r, 8.0)["pass"]
    assert not gate({**r, "in_lung_gt1mm_frac": GATES["in_lung_frac"] + 0.01}, 8.0)["pass"]
    assert not gate({**r, "his_label_fragment": {"voxels": 500, "to_mesh_median_mm": 22.0, "within_5mm_frac": 0.0}}, 8.0)["pass"]
    assert not gate(r, 2.0)["pass"]          # 4x her own calibre


def test_report_routes_match_the_shipped_lists_and_rebuild_order():
    rep = json.loads((REPO / "data" / "derived" / "Q183b_vessels_ql.json").read_text())["structures"]
    assert set(rep) == set(IDS)
    assert {k for k, e in rep.items() if e["route"] == "a"} == set(OWN_SHIP)
    assert {k for k, e in rep.items() if e["route"] == "c"} == set(SHIP)
    m = own_mapping("ct_vhm_vessels", OWN_SHIP)
    assert m["source_volume"].endswith("vhm_total.nii.gz") and {e["atlas_id"] for e in m["entries"]} <= set(OWN_SHIP)
    sh = (REPO / "scripts" / "vhm_rebuild_bundle.sh").read_text()
    order = re.search(r"for s in (ct_vhm_foot .*?); do SUBJ", sh).group(1).split()
    for s in ("ct_vhm_vessels", "ct_vhm_qlh", "xfer_vhf2vhm_vessels"):
        assert order.index(s) < order.index("ct_s1159_abd") and order.index(s) < order.index("ct_s1159")
    assert sh.index("costal_cartilage_from_ct_labels.py stamp") < sh.index("vessels_ql_q183b.py stamp")
