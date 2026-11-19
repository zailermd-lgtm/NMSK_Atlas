"""Q375: the border census's pure matching -- the engine's rim rule, a point on a border edge (T-junction) vs a shared vertex vs an
offset pair, on two synthetic closed skin slabs that meet along one border cut at different vertices (as the finger slabs meet the
palm: twice the border vertices on one side)."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "anatomy" / "q375"))
import border_census_q375 as BC  # noqa: E402


def slab(x0, x1, y0, y1, nx, ny, t=2.7):
    """a closed slab: outer grid at z=0 (normal +z), inner grid at z=-t, side walls round the border, all faces wound outward"""
    xs, ys = np.linspace(x0, x1, nx), np.linspace(y0, y1, ny)
    P = [(x, y, 0.0) for y in ys for x in xs] + [(x, y, -t) for y in ys for x in xs]
    n = nx * ny
    o = lambda i, j: j * nx + i
    F = []
    for j in range(ny - 1):
        for i in range(nx - 1):
            a, b, c, d = o(i, j), o(i + 1, j), o(i + 1, j + 1), o(i, j + 1)
            F += [(a, b, c), (a, c, d), (n + a, n + c, n + b), (n + a, n + d, n + c)]
    ring = [o(i, 0) for i in range(nx)] + [o(nx - 1, j) for j in range(1, ny)] + \
           [o(i, ny - 1) for i in range(nx - 2, -1, -1)] + [o(0, j) for j in range(ny - 2, 0, -1)]      # counter-clockwise from +z
    for k in range(len(ring)):
        a, b = ring[k], ring[(k + 1) % len(ring)]
        F += [(a, n + a, n + b), (a, n + b, b)]
    return np.array(P, float), np.array(F, int)


def test_on_segment():
    a, b = np.zeros(3), np.array([10.0, 0, 0])
    t, d = BC.on_segment(np.array([2.5, 0.01, 0]), a, b)
    assert abs(t - 0.25) < 1e-9 and abs(d - 0.01) < 1e-9
    t, d = BC.on_segment(np.array([-3.0, 4.0, 0]), a, b)
    assert t == 0.0 and abs(d - 5.0) < 1e-9


def test_rim_rule_finds_the_border_only():
    P, F = slab(0, 20, 0, 20, 5, 5)
    r, _ = BC.rim_vertices(P, F)
    border = (np.isclose(P[:, 0], 0) | np.isclose(P[:, 0], 20) | np.isclose(P[:, 1], 0) | np.isclose(P[:, 1], 20))
    assert (r == border).all()


def test_t_junctions_vs_shared():
    A = slab(0, 20, 10, 30, 5, 2)      # fine: border vertices at x = 0, 5, 10, 15, 20 along y = 10
    B = slab(0, 20, -10, 10, 3, 2)     # coarse: x = 0, 10, 20
    c = BC.classify(*A, *B)
    assert len(c["border"]) == 10      # 5 outer + 5 inner along the shared border; the far border is 20 mm away
    assert len(c["shared"]) == 6 and len(c["tjunction"]) == 4 and len(c["offset"]) == 0
    assert set(np.round(A[0][c["tjunction"], 0]).astype(int)) == {5, 15}
    c2 = BC.classify(*B, *A)           # the coarse side: every border vertex shared
    assert len(c2["border"]) == 6 and len(c2["shared"]) == 6 and len(c2["tjunction"]) == 0


def test_offset_pair_and_outer_never_to_inner():
    A = slab(0, 20, 10, 30, 3, 2)
    PB, FB = slab(0, 20, -10, 10, 3, 2)
    k = int(np.where(np.isclose(PB[:, 0], 10) & np.isclose(PB[:, 1], 10) & np.isclose(PB[:, 2], 0))[0][0])
    PB = PB.copy(); PB[k, 1] -= 0.8      # the outer middle border vertex of B 0.8 mm off its partner
    c = BC.classify(*A, PB, FB)
    j = int(np.where(np.isclose(A[0][:, 0], 10) & np.isclose(A[0][:, 1], 10) & np.isclose(A[0][:, 2], 0))[0][0])
    assert j in set(c["offset"].tolist()) and abs(float(c["offset_mm"].max()) - 0.8) < 1e-6
    assert len(c["shared"]) == 5       # the other two outer and three inner pairs
    # a thin slab: the inner sheet of B 0.9 mm under the outer -- the outer vertex of A must never pair with B's inner one
    A2 = slab(0, 20, 10, 30, 3, 2, t=0.9)
    PB2, FB2 = slab(0, 20, -10, 10, 3, 2, t=0.9)
    PB2 = PB2.copy(); PB2[k, 2] += 5.0      # B's outer partner gone far away; its inner vertex is the nearest rim vertex now
    c3 = BC.classify(*A2, PB2, FB2)
    assert j not in set(c3["offset"].tolist())
