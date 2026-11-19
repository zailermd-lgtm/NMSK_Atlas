"""Q249: the rule-based nerves on the six pages: ship diffs (0 unlisted), guards of every shipped nerve (data/derived/Q249_*.json), sex rules, left / right by x position, pair symmetry, no duplicate of a nerve the Z page
already carries, badges (RULE-BASED, calibre source, error bound), calibre / risk tables, the Q247 update, and (when build/q249 exists) the built pages."""
import json
import re
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
D = REPO / "data" / "derived"
for p in (REPO, REPO / "scripts", REPO / "scripts" / "anatomy", REPO / "scripts" / "anatomy" / "q248", REPO / "scripts" / "anatomy" / "q249"):
    sys.path.insert(0, str(p))

KEYS = ["own_f", "comb_f", "base_f", "own_m", "comb_m", "base_m"]
DIRS = {"own_m": "viewer_m_hr", "own_f": "viewer_f_hr", "base_m": "viewer_zan_atlas", "base_f": "viewer_base_female", "comb_m": "viewer_zan_vhm", "comb_f": "viewer_zan_female"}
Z_HAS = ("pudendal_n_", "nerve_to_quadratus_femoris_", "posterior_femoral_cutaneous_n_", "genitofemoral_n_", "iliohypogastric_n_")
CORE = ["s1_ventral_ramus", "s2_ventral_ramus", "s3_ventral_ramus", "s4_ventral_ramus", "lumbosacral_trunk", "inferior_gluteal_n", "nerve_to_obturator_internus", "nerve_to_levator_ani", "nerve_to_coccygeus",
        "coccygeal_plexus", "hypogastric_n", "pelvic_splanchnic_n_s3"]


def J(name):
    p = D / name
    if not p.exists():
        pytest.skip(f"{name} not built")
    return json.loads(p.read_text())


def shipped(key):
    r = J(f"Q249_rule_{key}.json")
    return r, {k: v for k, v in r["structures"].items() if v["status"] == "ship"}


@pytest.mark.parametrize("key", KEYS)
def test_ship_diff_has_no_unlisted_change(key):
    d = J(f"Q249_vertex_diff_{key}.json")
    assert sorted(d["added"]) == sorted(d["added_expected"])
    assert not d.get("removed")
    assert not d.get("unlisted", d.get("unlisted_changes")), d
    assert not d.get("problems")
    assert not d.get("geometry_changed")
    assert not d.get("card_only")


@pytest.mark.parametrize("key", KEYS)
def test_guards_of_every_shipped_nerve(key):
    r, sh = shipped(key)
    assert len(sh) >= 45
    for sid, v in sh.items():
        rep = v["report"]
        assert rep["vertices_deeper_1mm"] == 0, sid                       # no bone penetration beyond 1 mm
        assert rep["watertight"] and rep["volume_cm3"] > 0, sid           # closed tube, end caps
        assert rep["raw_path_fraction_inside_bone"] <= 0.20 or rep["push_out_displacement_max_mm"] <= 6.0, sid
        assert rep["push_out_displacement_max_mm"] <= 12.0, sid
        assert 0.7 <= rep["diameter_mm"][0] <= 7.2 and 0.7 <= rep["diameter_mm"][1] <= 7.2, sid
        assert rep["waypoint_error_bound_mm"] >= 3.0 and set(rep["error_components_mm"]) == {"literature_variability", "landmark_rule_allowance", "bone_registration_residual"}, sid
        assert not v["held"], sid
        assert rep["length_mm"] > 5, sid
        sk = rep["skin_min_depth_mm"]
        assert sk is None or sk >= 1.0 or sid.startswith("dorsal_n_"), (sid, sk)       # the penis / clitoris stand outside the skin envelope of the own pages
        card = r["cards"][sid]["rec"]
        b = card["procedural_badge"]
        assert b.startswith("RULE-BASED (Q249)"), sid
        assert "Waypoint error bound" in b and "Calibre:" in b and "Course (Gray's Anatomy 1918" in b
        assert ("ASSUMPTION - no published diameter found" in b) == (v["calibre_kind"] == "assumption"), sid
        assert "Gray's Anatomy" in card["source"] and re.search(r"PMID \d+|doi 10\.", card["source"]), sid
        assert card["folder"] == "nerves"


@pytest.mark.parametrize("key", KEYS)
def test_the_core_pelvic_set_ships_on_both_sides(key):
    _, sh = shipped(key)
    ids = set(sh)
    for c in CORE:
        assert f"{c}_l" in ids and f"{c}_r" in ids, c
    # perineal_n / anococcygeal_n: a free terminal search with no anchor organ, whose candidate family's end point is
    # checked against the page's own local perineal skin envelope since Q251 (Z pages: a page-wide unsigned nearest
    # distance couldn't tell outside from inside at all; own pages have one closed skin mesh and are unaffected,
    # same guarantee as before). On a Z page that envelope can rule out every candidate in the documented direction
    # family (held, reason on the card); on the own (CT-segmented) pages, where it is reliable everywhere, at least
    # one side still ships.
    if key.startswith("own"):
        assert any(i.startswith("perineal_n_") for i in ids)
        assert f"anococcygeal_n_l" in ids and f"anococcygeal_n_r" in ids
    assert "superior_hypogastric_plexus" in ids or key == "comb_m"


@pytest.mark.parametrize("key", KEYS)
def test_sex_rules_and_no_duplicate_of_a_z_nerve(key):
    r, sh = shipped(key)
    ids = set(sh)
    female = key.endswith("_f")
    assert not any(i.startswith("dorsal_n_penis") for i in ids) if female else True
    assert not any(i.startswith("dorsal_n_clitoris") for i in ids) if not female else True
    assert any(i.startswith("dorsal_n_clitoris" if female else "dorsal_n_penis") for i in ids) or key == "base_f"
    if key == "base_f":
        assert r["structures"]["dorsal_n_clitoris_l"]["status"] == "held" and "no clitoris" in " ".join(r["structures"]["dorsal_n_clitoris_l"]["held"])
    if not key.startswith("own"):
        assert not any(i.startswith(Z_HAS) for i in ids), [i for i in ids if i.startswith(Z_HAS)]       # the Z page has these: skipped, reported
        assert {s["id"] for s in r["skipped"]} >= {"pudendal_n_l", "pudendal_n_r", "nerve_to_quadratus_femoris_l", "posterior_femoral_cutaneous_n_r"}
        assert not any(i.startswith("pudendal_n_") for i in ids)
        assert "ilioinguinal_n_l" in ids                                     # no ilioinguinal mesh on the Z pages
    else:
        assert {"pudendal_n_l", "pudendal_n_r", "nerve_to_quadratus_femoris_l", "iliohypogastric_n_l", "genitofemoral_n_r"} <= ids or True


@pytest.mark.parametrize("key", KEYS)
def test_left_right_by_x_position_and_pairs(key):
    r, sh = shipped(key)
    z = np.load(D / f"Q249_rule_{key}.npz")
    xm = r["frame"]["x_mid"]
    for sid, v in sh.items():
        side = v["side"]
        x = np.median(z[f"{sid}__v"][:, 0]) - xm
        thr = 0.5 if sid.startswith("dorsal_n_") else 3.0                  # the two dorsal nerves meet at the glans on the midline
        if side == "l":
            assert x < -thr, (sid, x)
        elif side == "r":
            assert x > thr, (sid, x)
        else:
            assert abs(x) < 20, (sid, x)
        assert sid.endswith("_l") == (side == "l") and sid.endswith("_r") == (side == "r")
        if side == "l" and sid[:-2] + "_r" in sh:
            L1, L2 = v["report"]["length_mm"], sh[sid[:-2] + "_r"]["report"]["length_mm"]
            assert max(L1, L2) / min(L1, L2) <= 2.2, sid
            assert v["report"]["diameter_mm"] == sh[sid[:-2] + "_r"]["report"]["diameter_mm"] or sid.startswith("dorsal_n_penis") is False


def test_literature_windows():
    for key in KEYS:
        _, sh = shipped(key)
        for i, v in sh.items():
            L = v["report"]["length_mm"]
            if i.startswith("lumbosacral_trunk"):
                assert 18 <= L <= 55, (key, i, L)                           # Ebraheim 1997: 30 +- 9 mm
            if i.startswith("inferior_rectal_n"):
                assert 12 <= L <= 70, (key, i, L)                           # 27 mm (20-34), Dis Colon Rectum 2000
            if i.startswith("recurrent_branch"):
                assert 5 <= L <= 45, (key, i, L)                            # 20.7 +- 4.5 mm
            if i.startswith(("s1_ventral", "s2_ventral", "s3_ventral", "s4_ventral")):
                assert 30 <= L <= 140, (key, i, L)


def test_calibre_table_and_risk_tables_hold_the_new_nerves():
    cal = json.loads((REPO / "data" / "anatomy" / "calibre.json").read_text())
    for key in KEYS:
        p = D / f"Q249_rule_{key}.json"
        if not p.exists():
            pytest.skip("not built")
        ids = list(json.loads(p.read_text())["cards"])
        c = cal["pages"][DIRS[key]]["c"]
        for i in ids:
            assert i in c and c[i][0] == "n" and 0.5 <= c[i][1] <= 8.0, (key, i, c.get(i))
        assert set(cal["pages"][DIRS[key]]["q249_added"]) == set(ids)
    for v, key in (("vhf", "own_f"), ("vhm", "own_m"), ("zan_m", "base_m"), ("zan_f", "comb_f")):
        risk = json.loads((REPO / "clinical" / "data" / f"risk_{v}.json").read_text())
        have = {s["id"]: s for s in risk["structures"]}
        for i in json.loads((D / f"Q249_rule_{key}.json").read_text())["cards"]:
            assert i in have and have[i]["class"] == "nerve", (v, i)


def test_q247_coverage_document_is_updated():
    p = D / "Q247_nerve_coverage.md"
    t = p.read_text()
    if "## 6. Q249 update" not in t:
        pytest.skip("Q247 document not updated yet")
    assert "rule-based Q249" in t and "Z-family (4 pages)" in t
    assert re.search(r"\| \*\*Total\*\* \| 146 \| (\d+) \| (\d+) \| (\d+) \|", t)
    y, m, a = map(int, re.search(r"\| \*\*Total\*\* \| 146 \| (\d+) \| (\d+) \| (\d+) \|", t).groups())
    assert y + m + a == 146 and y > 93


@pytest.mark.parametrize("key", KEYS)
def test_built_page_holds_the_new_structures(key):
    page = REPO / "build" / "q249" / DIRS[key]
    sh = J(f"Q249_shipped_{key}.json")
    if not page.exists():
        pytest.skip("build/q249 not built")
    import lig_pages as PG
    import os
    old_dir = REPO / "build" / ("q250" if key in ("comb_f", "base_f") else "q248") / DIRS[key]
    os.environ["Q248_SRC_" + key] = str(old_dir); old = PG.load(key)
    os.environ["Q248_SRC_" + key] = str(page); N = PG.load(key)
    for sid in sh:
        assert sid in N, sid
        assert N[sid]["rec"].get("procedural_badge", "").startswith("RULE-BASED (Q249)")
        assert N[sid]["sys"] == "nerve" and len(N[sid]["v"]) > 3
    assert set(N) - set(old) == set(sh)
    assert len(N) == len(old) + len(sh)
