"""Q186b: her-CT-skin transfer gate (breast + perineal skin of the female Z-Anatomy viewer)."""
import json
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from scripts.zanatomy import her_skin_transfer_q186b as T  # noqa: E402


def test_raster_max_keeps_the_outermost_surface():
    P = np.array([[0, 0], [10, 0], [0, 10], [0, 0], [10, 0], [0, 10]], float)
    depth = np.array([1, 1, 1, 5, 5, 5], float)            # two stacked copies of one triangle
    out, cov = T.raster_max(P, depth, np.array([[0, 1, 2], [3, 4, 5]]), np.array([0.0, 0.0]), (12, 12))
    assert cov[1, 1] and not cov[10, 10] and out[1, 1] == 5.0


def test_gate_ships_a_small_seam_and_refuses_a_large_one():
    dist = np.stack([np.linspace(0, 60, 400), np.full(400, 4.0)], 1)
    assert T.ship_gate(np.full(100, 4.0), dist)[0]
    ok, why, _ = T.ship_gate(np.full(100, 30.0), np.stack([dist[:, 0], np.full(400, 30.0)], 1))
    assert not ok and len(why) == 2


def test_recorded_measurement_matches_the_decision():
    rep = json.loads((REPO_ROOT / "data" / "derived" / "Q186b_her_skin_transfer.json").read_text())
    for key in ("chest", "perineum"):
        r = rep[key]
        assert r["ship"] == (not r["why_not"])
        # a median seam offset above the blend bound can never pass the 90 % seam gate
        if r["seam_offset_her_minus_neighbour_mm"]["median"] > T.SEAM_BOUND_MM:
            assert not r["ship"]
    assert rep["shipped"] == (rep["chest"]["ship"] or rep["perineum"]["ship"])
