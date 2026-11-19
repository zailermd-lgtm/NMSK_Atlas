"""Q365: head nerves placed on the Base pages (scripts/anatomy/q365/place_nerves_q365.py).

Checks the method's pieces directly, the JSON report of the last run, and -- once the round is applied to build/q309 -- the pages
themselves (ids present, trailing block kept last, pose rig in step, cards badged)."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pytest
import trimesh

REPO = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(REPO / "scripts/anatomy/q365"), str(REPO / "scripts"), str(REPO / "scripts/zanatomy")]

REPORT = REPO / "data/derived/Q365_nerves_report.json"
PAGES = {"base_m": REPO / "build/q309/viewer_zan_atlas/atlas_viewer_zan_atlas.html",
         "base_f": REPO / "build/q309/viewer_base_female/atlas_viewer_base_female.html"}
KEY = "window.__ANATOMY_MANIFEST__="
NEW = ("trigeminal_n_v2_infraorbital_branch", "greater_occipital_n", "third_occipital_n", "suboccipital_n")


def _manifest(p: Path):
    h = p.read_text(encoding="utf-8")
    i = h.index(KEY) + len(KEY)
    return json.JSONDecoder().raw_decode(h[i:])[0]


def test_cap_loops_closes_an_open_tube():
    import place_nerves_q365 as Q
    m = trimesh.creation.cylinder(radius=1.0, height=10.0, sections=12)
    v, f = np.asarray(m.vertices), np.asarray(m.faces)
    keep = (v[f].mean(1)[:, 2] > -4.0)                    # cut one end off: an open tube
    vv, ff = Q.submesh(v, f, keep)
    V, F, loops = Q.cap_loops(vv, ff)
    t = trimesh.Trimesh(V, F, process=False)
    assert loops >= 1 and t.is_watertight and t.is_winding_consistent


def test_kink_measure():
    import place_nerves_q365 as Q
    straight = np.c_[np.zeros(5), np.arange(5.0), np.zeros(5)]
    assert Q.kink_deg(straight) < 1e-6
    bent = np.array([[0, 0, 0], [0, 1, 0], [1, 1, 0]], float)
    assert abs(Q.kink_deg(bent) - 90.0) < 1e-6


def test_q357_note_leads_with_one_short_sentence():
    import card_rules_q354 as R
    long = ("Q357: moved out of the L1 vertebra, L2 vertebra, L3 vertebra, L4 vertebra, T12 vertebra, where the source registration left 105 "
            "of its vertices up to 5.2 mm inside the bone (the vessel does not pass through the bone there); each part moved along the "
            "bone's outward normal to 0.5 mm outside the surface.")
    t, _ = R.split_badge(long)
    assert t.startswith("Q357: moved out of bone (5.2 mm deep") and "L4 vertebra" in t and "105" in t
    card = R.card_text({"procedural_badge": t}, {})
    assert card.endswith("not a passage).") and len(card) <= 140
    assert R.split_badge(t)[0] == t                       # idempotent


@pytest.mark.skipif(not REPORT.exists(), reason="no Q365 run recorded")
def test_report_every_placed_nerve_passed_its_guards():
    rep = json.loads(REPORT.read_text(encoding="utf-8"))
    assert rep["schema"] == "nmsk.q365.nerves_report.v1"
    for stem, p in rep["pages"].items():
        placed = {k: s for k, s in p["structures"].items() if s["status"] == "ship"}
        assert any(k.startswith("trigeminal_n_v2_infraorbital_branch") for k in placed), stem
        for k, s in placed.items():
            g = s["q365_guards"]
            assert g["pass"] and not g["in_bone"] and g["outside_skin_vertices"] == 0 and g["closed"], (stem, k)
            assert g["length_ratio"] is None or g["length_ratio"] <= 1.6, (stem, k)
        for k, s in p["structures"].items():
            if s["status"] != "ship":
                assert s["held"], (stem, k)                # every structure not placed says why
        io = [s for k, s in placed.items() if k.startswith("trigeminal_n_v2_infraorbital_branch")]
        for s in io:
            r = s["report"]
            assert r["infraorbital"]["watertight"] and r["maxillary_rest"]["watertight"]
            tot = r["infraorbital"]["vertices"] + r["maxillary_rest"]["vertices"] - r["infraorbital"]["caps"] - r["maxillary_rest"]["caps"]
            assert r["source_vertices"] <= tot <= r["source_vertices"] * 1.05    # every source vertex kept; only the cut ring is shared


@pytest.mark.parametrize("key", sorted(PAGES))
def test_applied_page(key):
    p = PAGES[key]
    if not p.exists():
        pytest.skip("page absent")
    man = _manifest(p)
    ids = [m["id"] for m in man["meshes"]]
    if not any(i.startswith("greater_occipital_n") for i in ids):
        pytest.skip("Q365 not applied to this build page yet")
    by = {m["id"]: m for m in man["meshes"]}
    for n in NEW:
        for s in "lr":
            assert f"{n}_{s}" in by, (key, n, s)
    for s in "lr":
        io = by[f"trigeminal_n_v2_infraorbital_branch_{s}"]["rec"]["procedural_badge"]
        assert "Z-ANATOMY GEOMETRY, NOT RULE-BASED" in io
        for n in ("greater_occipital_n", "third_occipital_n", "suboccipital_n"):
            r = by[f"{n}_{s}"]["rec"]
            assert r["procedural_badge"].startswith("RULE-BASED") and "Mannan" in r["source"], (key, n, s)
    if "skin_vulva_cvh" in ids:
        assert ids[-2:] == ["skin_vulva_cvh", "skin_perineum_rule_q358"]
    rig = json.loads((REPO / f"data/anatomy/pose_rig_{key}.json").read_text(encoding="utf-8"))["rig"]
    assert rig["count"] == len(ids) and rig["nv"] == [int(m["vc"]) for m in man["meshes"]]
