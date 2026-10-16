"""Q248: the new ligaments on the six pages: ship diffs (0 unlisted), guards of every shipped structure (data/derived/Q248_*.json), sex rules, left / right by x position, source badges, the audit, and (when build/q248
exists) the built pages."""
import json
import re
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
D = REPO / "data" / "derived"
for p in (REPO, REPO / "scripts", REPO / "scripts" / "anatomy", REPO / "scripts" / "anatomy" / "q248"):
    sys.path.insert(0, str(p))

KEYS = ["own_f", "comb_f", "base_f", "own_m", "comb_m", "base_m"]
DIRS = {"own_m": "viewer_m_hr", "own_f": "viewer_f_hr", "base_m": "viewer_zan_atlas", "base_f": "viewer_base_female", "comb_m": "viewer_zan_vhm", "comb_f": "viewer_zan_female"}


def J(name):
    p = D / name
    if not p.exists():
        pytest.skip(f"{name} not built")
    return json.loads(p.read_text())


@pytest.mark.parametrize("key", KEYS)
def test_ship_diff_has_no_unlisted_change(key):
    d = J(f"Q248_vertex_diff_{key}.json")
    assert sorted(d["added"]) == sorted(d["added_expected"])
    assert not d.get("removed")
    assert not d.get("unlisted", d.get("unlisted_changes")), d
    assert not d.get("problems")
    assert not d.get("geometry_changed")
    assert not d.get("card_only")


@pytest.mark.parametrize("key", KEYS)
def test_rule_based_guards(key):
    r = J(f"Q248_rule_{key}.json")
    shipped = {k: v for k, v in r["structures"].items() if v["status"] == "ship"}
    assert shipped, "no rule-based ligament shipped"
    for sid, v in shipped.items():
        rep = v["report"]
        assert rep["vertices_deeper_1mm"] == 0, sid
        assert rep["watertight"] and rep["volume_cm3"] > 0, sid
        for end, a in rep["attachments"].items():
            if a["signed_distance_mm"] is not None:
                assert abs(a["signed_distance_mm"]) <= 1.0, (sid, end)
        assert not v["held"]
        so = rep["soft_overlap"]
        if key.startswith("own"):
            assert so["muscle_fraction_deeper_6mm"] <= 0.25 and so["organ_fraction_deeper_3mm"] <= 0.10, sid
        card = r["cards"][sid]
        assert card["rec"]["procedural_badge"].startswith("RULE-BASED (Q248)")
        assert "MODELLING CHOICE" in card["rec"]["procedural_badge"] or "modelling choice" in card["rec"]["procedural_badge"].lower()
        assert "PMID" in card["rec"]["source"] or "Terminologia" in card["rec"]["source"]


@pytest.mark.parametrize("key", KEYS)
def test_rule_based_sex_rules_and_lengths(key):
    r = J(f"Q248_rule_{key}.json")
    ids = {k for k, v in r["structures"].items() if v["status"] == "ship"}
    female = key.endswith("_f")
    assert not any(i.startswith("puboprostatic") for i in ids) if female else True
    assert not any(i.startswith("pubovesical") for i in ids) if not female else True
    for i in ids:
        L = r["structures"][i]["report"]["length_mm"]
        if i.startswith(("tendinous_arch", "arcus_tendineus")):
            assert 50 <= L <= 110, (i, L)                  # published ~10 cm for the arcus tendineus fasciae pelvis
        if i.startswith("patellar_ligament"):
            assert 30 <= L <= 60, (i, L)                   # Aithal Padur 2021: range 3-6 cm
        if i.startswith(("puboprostatic", "pubovesical")):
            assert 5 <= L <= 45, (i, L)


@pytest.mark.parametrize("key", KEYS)
def test_left_right_by_x_position(key):
    r = J(f"Q248_rule_{key}.json")
    z = np.load(D / f"Q248_rule_{key}.npz")
    for sid, v in r["structures"].items():
        if v["status"] != "ship":
            continue
        side = v["side"]
        x = z[f"{sid}__v"][:, 0].mean()
        if side == "l":
            assert x < -3, (sid, x)
        elif side == "r":
            assert x > 3, (sid, x)
        else:
            assert abs(x) < 20, (sid, x)
        assert sid.endswith("_l") == (side == "l") and sid.endswith("_r") == (side == "r")


@pytest.mark.parametrize("key", ["own_f", "own_m"])
def test_transferred_z_ligaments_pass_their_gates(key):
    x = J(f"Q248_xfer_{key}.json")
    n = 0
    for sid, rep in x["structures"].items():
        if rep["status"] != "ship":
            assert rep["held_reasons"] or rep.get("reason")
            continue
        n += 1
        assert rep["vertices_deeper_1mm_in_bone"] == 0
        assert max(f.get("median_mm", 0) for f in rep["carriers"].values()) <= 2.5
        assert rep["soft_overlap"]["muscle_fraction_deeper_6mm"] <= 0.25 and rep["soft_overlap"]["organ_fraction_deeper_3mm"] <= 0.10
        assert rep["side"]["ok"]
        assert 0.6 <= rep["length_mm"]["ratio"] <= 1.6
        assert rep["edge_stretch"]["p95"] <= 3.0
        assert rep["skin_min_depth_mm"] is None or rep["skin_min_depth_mm"] >= 1.0
    assert n >= 40
    # the pelvic girdle is covered
    ok = {s for s, r in x["structures"].items() if r["status"] == "ship"}
    assert any("sacrotuberous" in s for s in ok) or any("sacrospinous" in s for s in ok) or any("sacro_iliac" in s for s in ok)


def test_audit_document_counts_and_ranks():
    p = D / "Q248_ligament_audit.md"
    if not p.exists():
        pytest.skip("audit not built")
    t = p.read_text()
    for lbl in ("Imaging-based F", "Combined F", "Base F", "Imaging-based M", "Combined M", "Base M"):
        assert lbl in t
    assert "## 4. Missing items ranked by relevance" in t and "no source" in t
    assert t.index("Pelvic floor and perineum") < t.index("Hip") < t.index("Wrist and hand")
    assert "Terminologia Anatomica" in t and "PMID" in t


@pytest.mark.parametrize("key", KEYS)
def test_built_page_holds_the_new_structures(key):
    sh = J(f"Q248_shipped_{key}.json")
    page = REPO / "build" / "q248" / DIRS[key]
    if not page.exists():
        pytest.skip("build/q248 not built")
    import lig_pages as PG
    E = PG.load(key, "build/q248")
    for sid, v in sh.items():
        assert sid in E, sid
        badge = E[sid]["rec"].get("procedural_badge", "")
        assert badge.startswith(("RULE-BASED (Q248)", "FILLED from Z-Anatomy (Q248)", "REGISTERED OTHER PERSON (Q248)")), sid
        assert len(E[sid]["v"]) > 3
    old = PG.load(key, "build/q244")
    assert set(E) - set(old) == set(sh)
    assert len(E) == len(old) + len(sh)
