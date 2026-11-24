"""Q379: the chest-border join's pure functions -- projection onto a neighbour's border polyline, the order-keeping run plan
(polyline vertices welded, the rest inside an edge), and the page's 16-bit round trip keeping a vertex on the edge within the
engine's 0.03 mm."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "anatomy" / "q379"))
import chest_borders_q379 as Q  # noqa: E402


def test_polyline_projection():
    Qp = np.array([[0.0, 0, 0], [10, 0, 0], [10, 10, 0]])
    s, d, k, t = Q.polyline_project(np.array([4.0, 1.5, 0]), Qp)
    assert k == 0 and abs(t - 0.4) < 1e-9 and abs(d - 1.5) < 1e-9 and abs(s - 4.0) < 1e-9
    s, d, k, t = Q.polyline_project(np.array([11.0, 6.0, 0.5]), Qp)
    assert k == 1 and abs(s - 16.0) < 1e-9 and abs(d - np.hypot(1.0, 0.5)) < 1e-9
    p, k, t = Q.at_arc(Qp, 16.0)
    assert k == 1 and np.allclose(p, [10, 6, 0])


def test_plan_run_snaps_vertices_and_keeps_order():
    Qp = np.array([[0.0, 0, 0], [10, 0, 0], [20, 0, 0]])                       # one interior neighbour vertex at x = 10
    Pr = np.array([[3.0, 0.8, 0], [9.0, 0.6, 0], [12.0, 0.9, 0], [16.0, 0.5, 0]])   # a subdivided chest border lying 0.5-0.9 mm off
    out, st = Q.plan_run(Pr, Qp, cap=4.0)
    assert st == "ok"
    assert [o["kind"] for o in out] == ["edge", "vertex", "edge", "edge"]
    assert np.allclose(out[1]["target"], [10, 0, 0])                          # the nearest point takes the neighbour's vertex
    xs = [o["target"][0] for o in out]
    assert xs == sorted(xs) and len(set(xs)) == 4                              # order kept, nothing collapsed
    for o in out:
        assert abs(o["target"][1]) < 1e-12                                     # ON the neighbour's border
        if o["kind"] == "edge":
            assert Q.T_MIN <= o["t"] <= 1 - Q.T_MIN                            # inside its edge (the engine's 0.02 < t < 0.98)
    assert max(o["move"] for o in out) < 1.5


def test_plan_run_refuses_over_cap_and_bridges():
    Qp = np.array([[0.0, 0, 0], [10, 0, 0]])
    out, st = Q.plan_run(np.array([[5.0, 6.0, 0]]), Qp, cap=4.0)
    assert st == "cap" and out == [None]
    Qb = np.array([[0.0, 0, 0], [4, 0, 0], [5, 0, 0], [10, 0, 0]])             # segment 1 is a bridge between two pieces
    out, st = Q.plan_run(np.array([[4.5, 0.3, 0], [7.0, 0.3, 0]]), Qb, cap=4.0, attach=[True, False, True], snap=False)
    assert st == "ok" and out[0]["kind"] == "edge" and out[0]["seg"] in (0, 2)  # moved off the bridge onto a real edge


def test_quantisation_round_trip_stays_on_edge():
    rng = np.random.default_rng(379)
    mn, span = np.array([-180.123, 300.456, -90.0]), np.array([95.5, 210.25, 160.75])   # a lateral-thorax-sized box
    for _ in range(200):
        a = mn + rng.random(3) * span; b = np.clip(a + rng.normal(size=3) * 6, mn, mn + span)
        tgt = a + rng.uniform(0.05, 0.95) * (b - a)
        q0 = Q.encode(tgt, mn, span)
        naive = Q.decode(q0, mn, span)
        code, p, res = Q.best_code(tgt, mn, span, a, b)
        assert code is not None and res <= Q.seg_point(naive, a, b)[2] + 1e-12   # never worse than plain rounding
        assert res < 0.01                                                         # far inside the engine's 0.03 mm
        t = Q.seg_point(p, a, b)[0]
        assert 0.02 < t < 0.98
        assert np.allclose(Q.decode(code, mn, span), p)
    code, p, res = Q.best_code(mn - 1.0, mn, span)                              # outside the box: refused, never clipped
    assert code is None


def test_layout_loops_runs():
    # a 2 x 1 quad strip as a Q360 slab: [outer | inner]
    P = np.array([[0.0, 0, 0], [1, 0, 0], [2, 0, 0], [0, 1, 0], [1, 1, 0], [2, 1, 0]])
    Fo = np.array([[0, 1, 4], [0, 4, 3], [1, 2, 5], [1, 5, 4]])
    F = np.vstack([Fo, Fo[:, ::-1] + 6])
    nv, om, im = Q.q360_layout(np.vstack([P, P - [0, 0, 3]]), F)
    assert nv == 6 and om.sum() == 4 and im.sum() == 4
    (loop,) = Q.border_loops(Fo)
    assert sorted(loop) == [0, 1, 2, 3, 4, 5]
    locked = {v: v in (0, 2) for v in loop}
    runs = Q.runs_of(loop, locked)
    assert len(runs) == 2 and sorted(len(r[1]) for r in runs) == [1, 3]
