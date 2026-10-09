"""Q187 motor points (private clinical layer): schema, citations, and every point inside its muscle."""
import json
import re
import sys
from pathlib import Path

import numpy as np
import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from scripts.clinical import motor_points_q187 as M  # noqa: E402

DATA = REPO / "clinical" / "data" / "motor_points.json"
TOL_MM = M.FAIL_MM


@pytest.fixture(scope="module")
def mp():
    if not DATA.exists():
        pytest.skip("clinical/data/motor_points.json not built")
    return json.loads(DATA.read_text())


def test_schema(mp):
    assert mp["schema"] == "nmsk.motor_points.v1"
    assert mp["licence"].startswith("Private")
    assert re.fullmatch(r"\d{4}-\d\d-\d\d", mp["generated"])
    assert set(mp["viewers"]) == {"vhm", "vhf", "zan_m", "zan_f"}
    keys = {"id", "structure_id", "atlas_id", "muscle_name", "side", "kind", "pos", "depth_from_skin_mm",
            "projection_mm", "uncertainty_mm", "nerve", "source", "badge"}
    for vk, v in mp["viewers"].items():
        assert v["frame"] == M.FRAME
        ids = [p["id"] for p in v["points"]]
        assert len(ids) == len(set(ids)), vk
        for p in v["points"]:
            assert set(p) == keys, (vk, p["id"])
            assert p["id"].startswith(f"mp.{p['atlas_id']}.")
            assert p["side"] in ("r", "l", "midline")
            assert p["kind"] in ("motor_point", "innervation_zone")
            assert len(p["pos"]) == 3 and all(isinstance(x, (int, float)) for x in p["pos"])
            assert p["depth_from_skin_mm"] is None or p["depth_from_skin_mm"] >= 0
            assert 0 <= p["projection_mm"] <= TOL_MM
            assert p["uncertainty_mm"] > 0
            assert p["badge"].startswith("Rule-based from ")


def test_every_point_cited(mp):
    for v in mp["viewers"].values():
        for p in v["points"]:
            s = p["source"]
            assert s["citation"] and s["rule"], p["id"]
            assert re.fullmatch(r"10\.\d{4,}/\S+", s["doi"]), p["id"]
            assert re.fullmatch(r"\d{7,8}", s["pmid"]), p["id"]


def test_rules_reference_known_sources():
    for r in M.RULES:
        assert r["src"] in M.SOURCES
        assert r["kind"] in ("motor_point", "innervation_zone")


@pytest.mark.parametrize("vk", ["vhm", "vhf", "zan_m", "zan_f"])
def test_points_inside_their_muscle(mp, vk):
    vw = M.VIEWERS[vk]
    if not Path(vw["html"]).exists():
        pytest.skip(f"{vw['html']} not built")
    meshes = M.load_viewer(vk)
    pts = mp["viewers"][vk]["points"]
    assert pts, vk
    for p in pts:
        m = meshes[p["structure_id"]]
        assert m["cat"] == "muscle", p["id"]
        q = np.array(p["pos"], float)
        ok = bool(M.inside(q, m["v"], m["f"])[0])
        if not ok:  # tolerance: rounding of pos to 0.1 mm at a thin muscle's surface
            ok = float(np.min(np.linalg.norm(m["v"] - q, axis=1))) <= 1.0
        assert ok, (vk, p["id"])
