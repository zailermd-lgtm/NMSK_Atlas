"""Q353: Base · Female skin seams, breast / facial muscle tuck, vulvar patch border (scripts/anatomy/q353/conform_skin_q353.py).

Fast: synthetic checks of the move rules and the committed report; the page checks run only when build/q309 carries the Q353 notes."""
import json, sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts/anatomy/q353"))
import conform_skin_q353 as Q  # noqa: E402

REPORT = REPO / "data/derived/Q353_skin_report.json"
PAGE = REPO / "build/q309/viewer_base_female"
BANNED = ("ultrasound", "hounsfield", "t1_se", "imaging_tissues", "tissue table", "nmskultrasound", "acoustic", "mrayl", "b-mode")


def _rep():
    if not REPORT.exists():
        pytest.skip("no Q353 report")
    return json.loads(REPORT.read_text(encoding="utf-8"))["pages"]["atlas_viewer_base_female"]


def test_envelope_is_capped_lipschitz_and_meets_the_requirement():
    X = np.c_[np.linspace(0, 40, 81), np.zeros(81), np.zeros(81)]
    need = X[[40]]
    D = Q.envelope(X, need, np.array([3.0]), np.array([[0, 0, -1.0]]))
    a = np.linalg.norm(D, axis=1)
    assert abs(a[40] - 3.0) < 1e-9 and a.max() <= 3.0 + 1e-9
    assert np.abs(np.diff(a)).max() <= Q.K_ENV * 0.5 + 1e-9          # slope K along the structure, no kink
    assert (D[:, 2] <= 0).all() and np.allclose(D[:, :2], 0)          # inward only


def test_shepard_fades_to_zero_beyond_fall():
    pts = np.array([[0.0, 0, 0]]); vec = np.array([[0, 2.0, 0]])
    X = np.array([[0.0, 0, 0], [Q.FALL / 2, 0, 0], [Q.FALL + 1, 0, 0]])
    D = Q.shepard(X, pts, vec)
    assert np.allclose(D[0], vec[0]) and 0 < D[1, 1] < 2 and np.allclose(D[2], 0)


def test_seg_closest():
    P = np.array([[0.5, 1.0, 0], [2.0, 0, 0]])
    Qp, d = Q.seg_closest(P, np.zeros((2, 3)), np.array([[1.0, 0, 0]] * 2))
    assert np.allclose(Qp, [[0.5, 0, 0], [1, 0, 0]]) and np.allclose(d, [1, 1])


def test_worse_than_tolerance():
    assert not Q.worse_than(dict(outside=0), dict(outside=Q.GAIN_TOL))
    assert Q.worse_than(dict(outside=0), dict(outside=Q.GAIN_TOL + 1))
    assert not Q.worse_than(dict(outside=500), dict(outside=505))      # a known far-out defect: 1 % gain tolerated
    assert Q.worse_than(dict(outside=500), dict(outside=520))


def test_closed_manifold_and_volume_rule():
    f = np.array([[0, 1, 2], [0, 3, 1], [0, 2, 3], [1, 3, 2]])
    assert Q.closed_manifold(f) and not Q.closed_manifold(f[:3])
    assert Q.vol_change(dict(closed_manifold=False, volume_before_mm3=1, volume_after_mm3=2)) is None


def test_report_guards_hold():
    r = _rep()
    assert r["rule_based"] and r["parameters"]["cap_seam_mm"] == Q.CAP_SEAM
    for k, s in r["structures"].items():
        cap = Q.CAP_VULVA if k == "skin_vulva_cvh" else (Q.CAP_SEAM if k.startswith("zan_skin_") else Q.CAP_TUCK)
        assert s["displacement"]["max_mm"] <= cap + 0.01, k
        assert s["card"].count("Q353 ") >= 1, k
    for st, sr in r["steps"].items():
        if sr.get("skipped"):
            continue
        assert sr["ships"] is True or not any(st in s["steps"] for s in r["structures"].values()), st
        assert not sr.get("outside_skin_gained"), st
        for k, t in sr.get("tuck", {}).items():
            if t.get("ships"):
                assert t["after"]["outside"] == 0 and t["guards"]["flipped_pct_moved_faces"] <= Q.FLIP_MAX, k
                assert t["inside_bone"][1] <= t["inside_bone"][0], k
        for k, gd in (sr.get("seam_guards") or {}).items():
            if k in r["structures"]:
                assert gd["flipped_pct_moved_faces"] <= Q.FLIP_MAX, k


def test_chest_seams_closed():
    r = _rep()
    s = r["steps"].get("chest", {}).get("seams") or {}
    if not s:
        pytest.skip("chest seams not in this report")
    before = sum(x["border_gap_before_mm"]["over_1_5mm"] for x in s.values())
    after = sum(x["border_gap_after_mm"]["over_1_5mm"] for x in s.values())
    assert after < 0.2 * before, (before, after)


def test_no_banned_words_or_model_ids_in_script():
    t = (REPO / "scripts/anatomy/q353/conform_skin_q353.py").read_text(encoding="utf-8").lower()
    assert not any(w in t for w in BANNED)
    assert "claude" not in t and "opus" not in t and "sonnet" not in t


def test_page_carries_q353_and_counts_unchanged():
    if not PAGE.exists() or not (PAGE / "index.html.q353").exists():
        pytest.skip("build/q309 page without Q353")
    sys.path.insert(0, str(REPO / "scripts/anatomy/q340"))
    import conform_palm_q340 as C
    man, _, _ = C.read_page(PAGE, "atlas_viewer_base_female")
    t0 = (PAGE / "index.html.q353").read_text(encoding="utf-8")
    man0 = json.loads(C.LIT["manifest"].search(t0).group(1))
    assert [(m["id"], m["vc"], m["ic"]) for m in man["meshes"]] == [(m["id"], m["vc"], m["ic"]) for m in man0["meshes"]]
    tagged = [m["id"] for m in man["meshes"] if "Q353 " in ((m.get("rec") or {}).get("procedural_badge") or "")]
    assert sorted(tagged) == sorted(_rep()["geometry_changed"])
    low = (PAGE / "index.html").read_text(encoding="utf-8").lower()
    for m in man["meshes"]:
        if m["id"] in tagged:
            assert not any(w in m["rec"]["procedural_badge"].lower() for w in BANNED)
