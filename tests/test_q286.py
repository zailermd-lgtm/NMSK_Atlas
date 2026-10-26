"""Q286: open TotalSegmentator tasks `head_glands_cavities` / `vertebrae_body` on the VH bodies' own CT (browser behaviour:
scripts/anatomy/q286/verify_q286.py)."""
import base64
import json
import subprocess
import sys
import zlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
REP = {(b, k): json.loads((REPO / f"data/derived/Q286_{b}_{k}_report.json").read_text()) for b in ("vhm", "vhf") for k in ("head", "spine")}


def test_shipped_structures_met_every_gate_and_held_ones_say_why():
    for (b, k), r in REP.items():
        assert all(r["held"][h] for h in r["held"])                       # every held item carries at least one reason
        if k == "head":
            for cls, c in r["classes"].items():
                sid = cls.replace("_gland_right", "_gland_r").replace("_gland_left", "_gland_l")
                if c["largest_component_share"] < 0.85 or abs(c["mesh_vs_label"] - 1) > 0.03 or c["outside_skin_gt1mm_frac"] > 0 \
                        or c["in_bone_gt1mm_frac"] > 0.05 or c["hu"]["boundary_contrast"] < 5:
                    assert not any(s == sid for s in r["shipped"]), (b, cls)
        for lvl in r.get("shipped", []):
            if k == "spine":
                c = r["levels"][lvl]
                assert c["in_bone_gt1mm_frac"] <= 0.02 and c["lung_gt1mm_frac"] == 0 and c["outside_skin_gt1mm_frac"] == 0
                assert all(s["ok"] for s in c["size_vs_published"].values())


def test_shipping_set_is_the_reported_one():
    assert REP[("vhm", "head")]["shipped"] == ["lens_r", "lens_l"]
    assert sorted(REP[("vhf", "head")]["shipped"]) == sorted(["submandibular_gland_r", "submandibular_gland_l", "lens_r", "lens_l", "soft_palate"])
    assert sorted(REP[("vhm", "spine")]["shipped"]) == ["intervertebral_disc_c6_c7", "intervertebral_disc_c7_t1"]
    assert REP[("vhf", "spine")]["shipped"] == []
    for b in ("vhm", "vhf"):
        pol = REP[(b, "head")]["not_shipped_by_policy"]
        assert {"nasopharynx", "oropharynx", "hypopharynx", "hard_palate"} <= set(pol)


def test_items_match_reports():
    import pytest
    if not (REPO / "build/vh/ct_vhm_hgc/items.json").exists():
        pytest.skip("build/ (git-ignored) not present")
    for subj, (b, k) in (("ct_vhm_hgc", ("vhm", "head")), ("ct_vhf_hgc", ("vhf", "head")), ("ct_vhm_disc_ts", ("vhm", "spine")),
                         ("ct_vhf_disc_ts", ("vhf", "spine"))):
        items = json.loads((REPO / "build/vh" / subj / "items.json").read_text()) if (REPO / "build/vh" / subj / "items.json").exists() else []
        assert sorted(i["id"] for i in items) == sorted(s for s in REP[(b, k)]["shipped"] if " " not in s)
        assert all("Q286" in i["rec"]["procedural_badge"] for i in items)


def test_pose_rigs_keep_committed_entries_and_cover_the_pages():
    for key, n in (("own_m", 898), ("own_f", 1048)):
        j = json.loads((REPO / f"data/anatomy/pose_rig_{key}.json").read_text())
        rig = j["rig"]
        assert rig["count"] == n and len(rig["nv"]) == n
        w = zlib.decompress(base64.b64decode(j["weights_zlib_b64"]))
        offs = [e[4] for e in rig["skin"]]
        assert len(offs) == len(set(offs)) and max(offs) < len(w)
        assert len({e[0] for e in rig["skin"]}) == len(rig["skin"])


def test_subject_labels_in_sync():
    r = subprocess.run([sys.executable, str(REPO / "scripts/sync_subjects_q286.py"), "--check"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout
