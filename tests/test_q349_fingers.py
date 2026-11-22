"""Q349: finger nerve / artery order and the venous arch (scripts/anatomy/q349/conform_fingers_q349.py).

Fast: synthetic checks of the move rule and the committed report; the page checks run only when build/q309 carries the Q349 notes."""
import json, re, sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts/anatomy/q349"))
import conform_fingers_q349 as Q  # noqa: E402

REPORT = REPO / "data/derived/Q349_fingers_report.json"
PAGES = {"atlas_viewer_zan_atlas": REPO / "build/q309/viewer_zan_atlas", "atlas_viewer_base_female": REPO / "build/q309/viewer_base_female"}


def _pair(delta, dr=None, root=3.0):
    g = np.arange(-10, 80.5, 0.5)
    delta = np.full(len(g), float(delta)) if np.isscalar(delta) else delta
    dr = np.full(len(g), 2.0) if dr is None else dr
    mreq = np.maximum(Q.M_MIN, np.sqrt(np.maximum(0, (0.6 + 0.6 + Q.GAP) ** 2 - dr ** 2)))
    s_req = root + Q.ZONE
    both = np.ones(len(g), bool)
    return dict(grid=g, delta=delta, dr=dr, mreq=mreq, reg=both & (g >= s_req), both=both, root_nerve_s=root, root_artery_s=root,
                requirement_from_s=s_req, radius_nerve=0.6, radius_artery=0.6)


def test_envelope_is_lipschitz_and_above():
    g = np.arange(0, 20, 0.5); T = np.zeros(len(g)); T[20] = 3.0
    E = Q.envelope(T, g, 0.2)
    assert (E >= T).all() and np.abs(np.diff(E)).max() <= 0.2 * 0.5 + 1e-9 and E[20] == 3.0


def test_plan_meets_rule_distally_and_is_zero_at_the_root():
    p = _pair(-3.0)
    for lam in Q.LAMS:
        pl = Q.plan_pair(p, lam)
        g = p["grid"]
        assert (pl["delta_after"][p["reg"]] >= p["mreq"][p["reg"]] - 1e-9).all()          # nerve palmar to the artery distal of the root zone
        assert np.abs(pl["dn"][g <= 3.0]).max() < 1e-9 and np.abs(pl["da"][g <= 3.0]).max() < 1e-9  # unmoved at the junction with the parent
        assert abs(pl["dn"].max() - lam * 3.5) < 1e-6 and abs(pl["da"].max() - (1 - lam) * 3.5) < 1e-6   # the minimum: shortfall + M_MIN
        assert p["root_nerve_s"] <= pl["crossing_planned_s"] <= p["requirement_from_s"]


def test_plan_crosses_where_the_strands_are_radially_apart():
    g = np.arange(-10, 80.5, 0.5)
    dr = np.where((g > 9) & (g < 11), 3.0, 0.2)
    pl = Q.plan_pair(_pair(-3.0, dr=dr), 0.5)
    assert 9 < pl["crossing_planned_s"] < 11


def test_plan_leaves_a_right_order_alone():
    pl = Q.plan_pair(_pair(+2.0), 0.5)
    assert pl["need_max_mm"] == 0 and np.abs(pl["dn"]).max() == 0 and np.abs(pl["da"]).max() == 0


def test_winding_inside_outside():
    import trimesh
    b = trimesh.creation.box(extents=(2, 2, 2))
    w = Q.winding(np.array([[0, 0, 0], [3, 0, 0]], float), np.asarray(b.vertices), np.asarray(b.faces))
    assert abs(abs(w[0]) - 1) < 1e-6 and abs(w[1]) < 1e-6


@pytest.mark.skipif(not REPORT.exists(), reason="no Q349 report")
def test_report_shipped_pairs_meet_the_rule_within_the_guards():
    rep = json.loads(REPORT.read_text(encoding="utf-8"))
    assert rep["schema"] == "nmsk.q349.fingers_report.v1"
    for stem, pg in rep["pages"].items():
        assert any("pp. 166, 168" in s for s in pg["sources"]) and any("pp. 137, 166, 182" in s for s in pg["sources"])
        shipped = {s: {n for n, r in pg["sides"][s]["pairs"].items() if r.get("ships")} for s in "rl"}
        assert shipped["r"] == shipped["l"], stem                                         # the hands stay mirror images
        for s in "rl":
            sd = pg["sides"][s]
            for n, r in sd["pairs"].items():
                if r.get("ships"):
                    assert r["planned_after_distal_order_with_clearance_pct"] == 100.0, (stem, s, n)
                    assert sd["pairs_after"][n]["distal_order_right_pct"] == 100.0, (stem, s, n)      # re-measured on the result
                    assert max(r["nerve_move"]["max_mm"], r["artery_move"]["max_mm"]) <= Q.CAP + 1e-6
                    assert not r["tries"][-1]["fails"]
                else:
                    assert r.get("reason") or r.get("denied"), (stem, s, n)
            for k, st in sd["structures"].items():
                assert st["displacement"]["max_mm"] <= max(Q.CAP, Q.CAP_V) + 1e-6
                assert st["flipped_pct_moved_faces"] <= 0.5
            for w, x in sd["palm_webs_after"].items():                                    # the palm order (nerve deep) is kept
                assert x["nerve_deep_pct"] >= sd["palm_webs_before"][w]["nerve_deep_pct"] - 1e-9


def _manifest(page_dir):
    html = sorted(Path(page_dir).glob("atlas_viewer_*.html"))[0].read_text(encoding="utf-8")
    return json.loads(re.search(r"^window\.__ANATOMY_MANIFEST__=(.*);$", html, re.M).group(1))


@pytest.mark.parametrize("stem", sorted(PAGES))
def test_page_carries_the_conform_with_unchanged_counts(stem):
    d = PAGES[stem]
    if not d.exists():
        pytest.skip("build/q309 absent")
    man = _manifest(d)
    tagged = sorted(m["id"] for m in man["meshes"] if Q.TAG in ((m.get("rec") or {}).get("procedural_badge") or ""))
    if not tagged:
        pytest.skip("Q349 not applied to this page yet")
    rep = json.loads(REPORT.read_text(encoding="utf-8"))["pages"][stem]
    assert tagged == rep["geometry_changed"]
    bk = sorted(d.glob("atlas_viewer_*.html.q349"))
    assert bk, "original page not kept as *.q349"
    old = {m["id"]: (m["vc"], m["ic"]) for m in json.loads(re.search(r"^window\.__ANATOMY_MANIFEST__=(.*);$", bk[0].read_text(encoding="utf-8"), re.M).group(1))["meshes"]}
    assert {m["id"]: (m["vc"], m["ic"]) for m in man["meshes"]} == old                  # vertex / triangle counts: the pose rig contract
