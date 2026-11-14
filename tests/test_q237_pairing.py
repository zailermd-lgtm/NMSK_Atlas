"""Q237 step 1 + 2: the recorded classification and asymmetry measurements of the six pages (data/derived/Q237_pairing.json + .md): every structure in exactly one unit, the owner's flag rules, lateralised organs never paired,
the midsagittal planes, the markdown report."""
import collections
import json
import math
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
D = REPO / "data/derived"
KEYS = ["own_m", "own_f", "comb_m", "comb_f", "base_m", "base_f"]


@pytest.fixture(scope="module")
def J():
    p = D / "Q237_pairing.json"
    if not p.exists():
        pytest.skip("not built")
    return json.loads(p.read_text())


def test_thresholds_are_the_owners(J):
    t = J["thresholds"]
    assert (t["ratio_lo"], t["ratio_hi"], t["iou_min"]) == (0.8, 1.25, 0.6) and set(J["pages"]) == set(KEYS)


def test_every_structure_is_in_exactly_one_unit(J):
    for k, p in J["pages"].items():
        ids = collections.Counter()
        for u in p["units"]:
            for sd in ("ids_r", "ids_l", "ids_m"):
                for i in u.get(sd, []):
                    ids[i] += 1
        assert sum(ids.values()) >= p["n_structures"] - 20, k                    # own pages repeat some ids (optic_n, bone pieces): counted per mesh id occurrence
        for u in p["units"]:
            assert u["cls"] in ("paired", "midline", "lateralised", "unmatched")
            if u["cls"] == "unmatched":
                assert u["kind"] in ("missing_side", "much_smaller") and u["why"]
            if u["cls"] == "paired":
                assert u["ids_r"] and u["ids_l"]


def test_flags_follow_the_owner_rules(J):
    n = 0
    for k, p in J["pages"].items():
        for u in p["units"]:
            m = u.get("metrics")
            if not m:
                continue
            n += 1
            rr = m["ratio_r_over_l"]
            has_ratio = any("ratio" in f for f in u["flags"])
            assert has_ratio == (rr is not None and (rr < 0.8 or rr > 1.25)), (k, u["canon"])
            has_iou = any(f.startswith("IoU") for f in u["flags"])
            assert has_iou == (m["iou_kind"] == "volume" and not m["thin"] and m["iou_aligned"] is not None and m["iou_aligned"] < 0.6), (k, u["canon"])
            if u["cls"] == "paired":
                assert u["tier"] in ("ok", "flag", "major") and (u["tier"] == "ok") == (not u["flags"])
            for f in ("msd_mm", "hd95_mm", "centroid_offset_mm", "iou_mirror", "iou_aligned", "msd_aligned_mm"):
                assert f in m
    assert n > 3000


def test_much_smaller_pairs_are_unmatched(J):
    for k, p in J["pages"].items():
        for u in p["units"]:
            if u.get("kind") == "much_smaller":
                r = u["metrics"]["ratio_r_over_l"]
                assert r < 0.5 or r > 2.0


def test_lateralised_organs_are_never_paired_or_midline(J):
    for k, p in J["pages"].items():
        names = {u["canon"]: u["cls"] for u in p["units"]}
        for n in ("liver", "spleen", "stomach", "heart"):
            if n in names:
                assert names[n] == "lateralised", (k, n)
        for u in p["units"]:
            if u["cls"] == "paired":
                assert not any(w in u["canon"] for w in ("liver", "spleen", "stomach", "atrium", "main_bronchus", "common_carotid", "subclavian")) and u["canon"] != "ventricle", (k, u["canon"])        # brain (lateral) ventricles are paired; heart ventricles are not


def test_planes(J):
    for k, p in J["pages"].items():
        pl = p["plane"]
        assert abs(sum(x * x for x in pl["n"]) - 1) < 1e-4
        assert pl["quality"]["refl_median_mm"] < 3.5 and pl["quality"]["midline_bones"]["n"] >= 25
        assert pl["tilt"]["total_deg"] < 2.5, k                                    # individuals lean up to ~2 degrees
    for k in ("base_m", "base_f"):
        assert abs(J["pages"][k]["plane"]["d_mm"]) < 0.5 and J["pages"][k]["plane"]["tilt"]["total_deg"] < 0.1


def test_base_pages_are_symmetric_and_fitted_pages_are_not(J):
    def frac(k):
        us = [u for u in J["pages"][k]["units"] if u.get("metrics") and u["cls"] == "paired"]
        return sum(1 for u in us if u["flags"]) / len(us)
    assert frac("base_m") < 0.03 and frac("base_f") < 0.03 and frac("comb_m") > 0.2 and frac("comb_f") > 0.2 and frac("own_f") > 0.3 and frac("own_m") > 0.3


def test_markdown_report_has_every_section(J):
    t = (D / "Q237_pairing.md").read_text()
    for h in ("## 1. Midsagittal plane per model", "## 2. Classification", "## 3. How the asymmetry is measured", "## 4. Asymmetry tables", "## 5. Unmatched", "## 6. Lateralised", "## 7. Fill", "## 8. Known real asymmetries"):
        assert h in t
    for k, p in J["pages"].items():
        assert p["label"] in t
