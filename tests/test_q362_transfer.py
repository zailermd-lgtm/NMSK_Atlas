"""Q362: real organ geometry of the frozen Imaging pages registered onto the Base pages (scripts/anatomy/q362/transfer_organs_q362.py).

Static checks always run; the report checks run when data/derived/Q362_transfer_report.json exists; the page checks run when the page in
build/q309 carries a Q362 structure (after the main thread's apply)."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
for p in ("scripts/anatomy/q362", "scripts/zanatomy", "scripts/anatomy/q336"):
    sys.path.insert(0, str(REPO / p))

T = pytest.importorskip("transfer_organs_q362")
REPORT = REPO / "data/derived/Q362_transfer_report.json"
FORBIDDEN = ("ultrasound", "hounsfield", "t1_se", "imaging_tissues", "tissue table", "nmskultrasound", "acoustic", "mrayl", "b-mode")


def test_kidneys_m_is_never_a_default_step():
    assert "kidneys_m" not in T.DEFAULT_STEPS["base_m"]
    assert "kidneys_m" in T.ALL_STEPS["base_m"]
    assert all(o.get("cross_sex") for o in T.ORGANS if o["step"] == "kidneys_m")


def test_ids_unique_per_page_and_sided():
    for key in ("base_m", "base_f"):
        ids = [o["id"] for o in T.ORGANS if o["key"] == key]
        assert len(ids) == len(set(ids)), ids
    for o in T.ORGANS:
        if o["side"] in "lr":
            assert o["id"].endswith("_" + o["side"]), o["id"]
        assert o["sys"] in ("viscera", "muscle")


def test_sources_are_the_frozen_pages_read_only():
    src = (REPO / "scripts/anatomy/q362/srcpage_q362.py").read_text(encoding="utf-8")
    assert "write_" not in src and ".write(" not in src
    assert set(T.SRC) == {"m", "f"} and all(p.name in ("viewer_m_hr", "viewer_f_hr") for p in T.SRC.values())


def _report():
    if not REPORT.exists():
        pytest.skip("no Q362 report yet")
    return json.loads(REPORT.read_text(encoding="utf-8"))


def test_report_guards_and_shape():
    R = _report()
    assert R["schema"] == "nmsk.q362.transfer_report.v1"
    for page, rep in R["pages"].items():
        for sid, it in rep["structures"].items():
            reg = it["registration"]
            assert reg["warp"] == "none"
            if it["status"] != "ship":
                assert it["held"], f"{page} {sid}: held without a reason"
                continue
            assert not it["guards"]["in_bone"] and it["guards"]["outside_skin_vertices"] == 0, sid
            assert it["guards"]["closed"], sid
            # the shape is the source's: only a uniform scale (+ a capped rigid nudge)
            assert abs(it["shape"]["volume_ratio"] / it["shape"]["volume_ratio_expected_scale3"] - 1) < 0.03, sid
            assert it["shape"]["deviation_from_similarity_mm"] <= T.NUDGE_CAP + 1e-6, sid
            assert not [c for c in it["book_checks"] if c["verdict"] == "differs" and c["check"] not in T.NONBLOCKING], sid


def test_shipped_records_carry_provenance_and_clean_card_text():
    import card_rules_q354 as CR
    R = _report()
    for page, rep in R["pages"].items():
        for sid, it in rep["structures"].items():
            if it["status"] != "ship" or "rec" not in it:
                continue
            rec = it["rec"]
            for k in ("source", "geom_src", "method", "procedural_badge", "notes"):
                assert rec.get(k), (sid, k)
            assert "NOT Z-Anatomy geometry" in rec["geom_src"]
            assert "public domain" in rec["source"]
            m = re.match(r"^(.{40,140}?[.;])(\s|$)", rec["procedural_badge"])
            assert m, f"{sid}: the badge's first sentence must be 40-140 characters"
            assert "registered" in m.group(1).lower()
            text = json.dumps(rec).lower()
            assert not [w for w in FORBIDDEN if w in text], sid
            assert "Mannan" in rec["source"] or "Gray's Atlas" in rec["source"]
            assert not CR.raw_hits(CR.card_text(rec, {})), sid


def _page_ids(d):
    import pagegeo_q336 as P
    return [m for m in P.manifest(d)["meshes"]]


@pytest.mark.parametrize("dirname", ["viewer_zan_atlas", "viewer_base_female"])
def test_applied_page_order_and_hidden(dirname):
    d = REPO / "build/q309" / dirname
    if not d.is_dir():
        pytest.skip("no build page")
    ms = _page_ids(d)
    ids = [m["id"] for m in ms]
    new = [o["id"] for o in T.ORGANS if o["key"] == T.DIRKEY[dirname] and o["id"] in ids]
    if not new:
        pytest.skip("Q362 not applied on this page")
    if dirname == "viewer_base_female":
        assert ids[-2:] == ["skin_vulva_cvh", "skin_perineum_rule_q358"]
    by = {m["id"]: m for m in ms}
    for o in T.ORGANS:
        if o["id"] in ids:
            for h in o.get("hide", []):
                if h in by:
                    assert by[h].get("hd") == 1, (o["id"], h)
            assert "NOT Z-Anatomy geometry" in by[o["id"]]["rec"]["geom_src"]
