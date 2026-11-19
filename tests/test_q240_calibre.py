"""Q240: calibre of vessels / nerves (scripts/anatomy/q240): the tube-diameter estimator on synthetic tubes with a known radius, the kind / level rules, the stored
table data/anatomy/calibre.json (shape, levels follow the documented thresholds, the 20 named checks against textbook calibres), uniqueness of the abbreviations of the
vessels / nerves, and the inject path (NMSK-CALIBRE markers in both templates, a page gets exactly its own table)."""
import json
import re
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
Q = REPO / "scripts" / "anatomy" / "q240"
sys.path.insert(0, str(Q)); sys.path.insert(0, str(REPO / "scripts" / "anatomy" / "q236"))
import calibre  # noqa: E402
import make_calibre as mc  # noqa: E402

CAL = REPO / "data" / "anatomy" / "calibre.json"
OWN = REPO / "viewer" / "atlas_viewer.template.html"
ZAN = REPO / "viewer" / "zan_atlas.template.html"


# ------------------------------------------------------------------------------ the estimator
def tube(r, L=200.0, nring=24, nrow=40, curve=0.0, branch=False):
    """open tube along x (optionally bent in the xy plane); returns V, F"""
    V, F = [], []
    for i in range(nrow):
        t = L * i / (nrow - 1)
        if curve:
            ang = t * curve; cx, cy = np.sin(ang) / curve, (1 - np.cos(ang)) / curve; tx, ty = np.cos(ang), np.sin(ang)
        else:
            cx, cy, tx, ty = t, 0.0, 1.0, 0.0
        for k in range(nring):
            a = 2 * np.pi * k / nring
            nx, ny = -ty, tx
            V.append([cx + r * np.cos(a) * nx, cy + r * np.cos(a) * ny, r * np.sin(a)])
    V = np.array(V)
    for i in range(nrow - 1):
        for k in range(nring):
            a, b, c, d = i * nring + k, i * nring + (k + 1) % nring, (i + 1) * nring + k, (i + 1) * nring + (k + 1) % nring
            F += [[a, b, c], [b, d, c]]
    return V, np.array(F)


@pytest.mark.parametrize("r,L", [(0.5, 60), (1.5, 150), (4.0, 200), (12.5, 250)])
def test_straight_tube_diameter(r, L):
    V, F = tube(r, L)
    d = calibre.tube_diameter(V, F)["diameter_mm"]
    assert abs(d - 2 * r) / (2 * r) < 0.08, (r, d)


def test_curved_tube_diameter():
    V, F = tube(3.0, L=240, nrow=80, curve=1 / 70.0)                 # bends through ~ 195 degrees (an aortic-arch-like curve)
    r = calibre.tube_diameter(V, F)
    assert abs(r["diameter_mm"] - 6.0) / 6.0 < 0.20, r


def test_branch_stub_does_not_inflate_the_trunk():
    V, F = tube(4.0, L=200)
    V2, F2 = tube(1.0, L=60, nrow=12)
    V2 = V2[:, [1, 0, 2]] + np.array([0, 4.0, 0]) + np.array([100, 0, 0])      # a thin branch leaving the trunk sideways
    VV, FF = np.vstack([V, V2]), np.vstack([F, F2 + len(V)])
    d = calibre.tube_diameter(VV, FF)["diameter_mm"]
    assert 6.0 <= d <= 9.5, d


def test_degenerate_inputs():
    assert calibre.tube_diameter(np.zeros((3, 3)), np.zeros((1, 3), int))["diameter_mm"] is None


# ------------------------------------------------------------------------------ kind / level rules
@pytest.mark.parametrize("sid,cat,kind", [
    ("abdominal_aorta", "vessel", "a"), ("femoral_a_r", "vessel", "a"), ("zan_radial_artery_l", "vessel", "a"), ("zan_anterior_temporal_branch_l", "vessel", "a"),
    ("inferior_vena_cava", "vessel", "v"), ("zan_basilic_vein_l", "vessel", "v"), ("straight_sinus", "vessel", "v"), ("zan_brachial_veins_r", "vessel", "v"),
    ("zan_left_ventricle", "vessel", None), ("zan_right_semilunar_leaflet_of_pulmonary_valve", "vessel", None), ("zan_unnamed", "vessel", None),
    ("sciatic_n", "nerve", "n"), ("zan_proper_palmar_digital_branches_of_ulnar_nerve_r", "nerve", "n"), ("brachial_trunk_superior_r", "nerve", "n"),
    ("zan_caudate_nucleus_r", "nerve", None), ("zan_fornix_l", "nerve", None), ("zan_optic_tract_r", "nerve", None), ("zan_sclera_l", "nerve", None),
    ("biceps_brachii_r", "muscle", None),
])
def test_kind_rules(sid, cat, kind):
    assert mc.kind_of(sid, cat) == kind


def test_levels_follow_the_documented_thresholds():
    assert [mc.level_of("a", d, "zan_x_artery")[0] for d in (25, 6.0, 5.9, 3.0, 2.9, 1.5, 1.4, 0.2)] == [1, 1, 2, 2, 3, 3, 4, 4]
    assert [mc.level_of("n", d, "zan_x_nerve")[0] for d in (12, 4.0, 3.9, 2.0, 1.9, 1.0, 0.9)] == [1, 1, 2, 2, 3, 3, 4]
    assert mc.level_of("n", None, "zan_x_nerve")[0] == 4


def test_named_trunks_are_promoted_and_flagged():
    assert mc.level_of("n", 1.6, "median_n_lateral_root_r") == (1, 1)           # thin mesh, named trunk
    assert mc.level_of("a", 2.2, "zan_brachial_artery_r") == (1, 1)
    assert mc.level_of("a", 9.0, "zan_femoral_artery_r") == (1, 0)             # already main by calibre: not promoted
    assert mc.level_of("a", 2.2, "zan_radial_artery_r")[0] == 3                # not a trunk
    assert mc.level_of("n", 1.4, "zan_dorsal_digital_branches_of_radial_nerve_r")[0] == 3


# ------------------------------------------------------------------------------ the stored table
@pytest.fixture(scope="module")
def doc():
    if not CAL.exists():
        pytest.skip("data/anatomy/calibre.json not generated")
    return json.loads(CAL.read_text())


def test_table_shape_and_levels(doc):
    assert doc["version"] == 1 and set(doc["definition"]["kinds"]) == {"a", "v", "n"}
    assert len(doc["pages"]) == 6
    for pg, e in doc["pages"].items():
        assert e["count"] == len(e["c"]) > 50, pg
        for sid, (k, d, lv, pr) in e["c"].items():
            assert k in "avn" and 1 <= lv <= 4 and pr in (0, 1)
            assert d is None or 0 < d < 80, (pg, sid, d)
            if not pr and d is not None:
                lad = mc.LEVEL_N if k == "n" else mc.LEVEL_A
                assert lv == next(i + 1 for i, (_, lo) in enumerate(lad) if d >= lo), (pg, sid, d, lv)
        kinds = {v[0] for v in e["c"].values()}
        assert kinds == {"a", "v", "n"}, pg
        n1 = sum(1 for v in e["c"].values() if v[2] == 1)
        assert 20 <= n1 <= 0.4 * len(e["c"]) or len(e["c"]) < 100, (pg, n1)       # main trunks are a minority


def test_no_brain_parts_among_the_nerves(doc):
    for pg, e in doc["pages"].items():
        bad = [s for s, v in e["c"].items() if v[0] == "n" and re.search(r"nucleus|tract|fornix|sclera|vitreous|cuneus|colliculus|vermis|fasciculus", s)]
        assert not bad, (pg, bad[:5])


def test_twenty_named_checks_against_textbook_calibres(doc):
    for pg, e in doc["pages"].items():
        rows = e["checks"]
        assert len(rows) == 20, pg
        found = [r for r in rows if r["id"]]
        within = [r for r in found if r["verdict"] in ("within range", "within x1.6")]
        # the two bodies with the most complete vessel / nerve set must agree with textbook calibres for most checks, every page for the great vessels
        assert len(within) >= 0.6 * len(found), (pg, [(r["check"], r["model_mm"]) for r in found if r not in within])
        for r in found:
            if r["check"] in ("Descending thoracic aorta", "Abdominal aorta", "Inferior vena cava", "Superior vena cava"):
                assert r["verdict"] != "outside x1.6", (pg, r)
    f = doc["pages"]["viewer_zan_female"]["checks"]
    assert sum(1 for r in f if r["verdict"] == "within range") >= 9


@pytest.mark.parametrize("d", ["viewer_m_hr", "viewer_f_hr", "viewer_zan_vhm", "viewer_zan_female", "viewer_base_female", "viewer_zan_atlas"])
def test_vessel_nerve_abbreviations_are_unique_and_follow_the_rules(doc, d):
    """the abbreviation table (Q236 rules) of the regenerated page: every vessel / nerve has its own abbreviation, sided ones end -R / -L"""
    from pages import PAGES, read_structs
    p = REPO / "build" / "q240" / d / PAGES[d]
    if not p.exists():
        pytest.skip("build/q240 not present")
    h = p.read_text(encoding="utf-8")
    ab = json.loads(re.search(r'id="nmsk-abbrev">(.*?)</script>', h, re.S).group(1))["a"]
    cal = json.loads(re.search(r'id="nmsk-calibre">(.*?)</script>', h, re.S).group(1))["c"]
    assert cal, d
    side = {x["id"]: x["side"] for x in read_structs(h)}
    seen = {}
    for sid in cal:
        a, gen, nm = ab[sid]
        assert a.lower() not in seen, (d, a, sid, seen.get(a.lower()))
        seen[a.lower()] = sid
        assert re.fullmatch(r"[A-Za-z0-9/.\-]+", a), a
        sd = str(side.get(sid) or "").lower()
        if sd in ("r", "right"):
            assert a.rsplit(".", 1)[0].endswith("-R"), (sid, a)
        if sd in ("l", "left"):
            assert a.rsplit(".", 1)[0].endswith("-L"), (sid, a)
    # the same abbreviation is never shared with a non-vessel structure of the page either
    for sid, (a, g, nm) in ab.items():
        if sid not in cal and a.lower() in seen:
            raise AssertionError((d, a, sid, seen[a.lower()]))


# ------------------------------------------------------------------------------ the inject path
@pytest.mark.parametrize("tpl", [OWN, ZAN])
def test_templates_carry_the_calibre_markers_once(tpl):
    s = tpl.read_text(encoding="utf-8")
    assert s.count(mc.BEGIN) == 1 and s.count(mc.END) == 1 and 'id="nmsk-calibre"' in s
    assert s.index("NMSK-ABBREV end") < s.index(mc.BEGIN)


def test_inject_writes_the_page_its_own_table(tmp_path, doc):
    d = tmp_path / "viewer_f_hr"
    d.mkdir()
    page = OWN.read_text(encoding="utf-8")
    (d / "atlas_viewer_female.html").write_text(page, encoding="utf-8")
    assert mc.inject(d) == 1
    s = (d / "atlas_viewer_female.html").read_text(encoding="utf-8")
    m = re.search(r'id="nmsk-calibre">(.*?)</script>', s, re.S)
    t = json.loads(m.group(1))
    assert t["v"] == 1 and len(t["c"]) == doc["pages"]["viewer_f_hr"]["count"]
    sid, v = next(iter(t["c"].items()))
    assert v == list(doc["pages"]["viewer_f_hr"]["c"][sid])
    assert s.count(mc.BEGIN) == 1 and "<" not in m.group(1)
