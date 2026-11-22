"""Q377: the skin census's pure functions -- border pairing across slabs, a separated pair rejoined to one position, a spike taken
back with its shared copy, and the slab's thickness kept, on two synthetic closed slabs that share one border."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts" / "anatomy" / "q377"))
import skin_q377 as S  # noqa: E402


def slab(x0, x1, nx=5, ny=4, t=2.7):
    """closed slab over [x0, x1] x [0, 3]: outer grid z=0, inner grid z=-t, side walls; faces wound outward"""
    xs, ys = np.linspace(x0, x1, nx), np.linspace(0.0, 3.0, ny)
    P = np.array([(x, y, 0.0) for y in ys for x in xs] + [(x, y, -t) for y in ys for x in xs])
    n = nx * ny
    o = lambda i, j: j * nx + i
    F = []
    for j in range(ny - 1):
        for i in range(nx - 1):
            a, b, c, d = o(i, j), o(i + 1, j), o(i + 1, j + 1), o(i, j + 1)
            F += [(a, b, c), (a, c, d), (n + a, n + c, n + b), (n + a, n + d, n + c)]
    ring = [o(i, 0) for i in range(nx)] + [o(nx - 1, j) for j in range(1, ny)] + \
           [o(i, ny - 1) for i in range(nx - 2, -1, -1)] + [o(0, j) for j in range(ny - 2, 0, -1)]
    for k in range(len(ring)):
        a, b = ring[k], ring[(k + 1) % len(ring)]
        F += [(a, n + a, n + b), (a, n + b, b)]
    return P, np.array(F)


def two():
    PA, F = slab(0.0, 4.0)
    PB, _ = slab(4.0, 8.0)
    PB = PB + np.array([1e-4, 0, 0])          # the page's per-mesh quantisation: micrometres apart
    return PA, PB, F


def test_border_pairing_finds_the_shared_border_only():
    PA, PB, F = two()
    pairs, groups = S.coincident_groups([PA, PB])
    # the shared border: x = 4 on both sheets, 4 rows each
    assert len(pairs) == 8 and len(groups) == 8
    assert set(pairs[:, 0]) == {0} and set(pairs[:, 2]) == {1}
    assert np.allclose(PA[pairs[:, 1], 0], 4.0) and np.allclose(PB[pairs[:, 3], 0], 4.0, atol=1e-3)


def test_separated_pair_is_rejoined_at_the_mean_of_the_predictions():
    PA, PB, F = two()
    pairs, groups = S.coincident_groups([PA, PB])
    a_v, b_v = int(pairs[0, 1]), int(pairs[0, 3])
    XA, XB = PA.copy(), PB.copy()
    XB[b_v] += np.array([0.0, 0.0, 0.6])        # Base·F: the pair came apart 0.6 mm
    pred = [PA.copy(), PB.copy()]
    pred[1][b_v] += np.array([0.0, 0.0, 0.2])   # the two local maps disagree a little
    X1, moved, rules = S.group_targets(groups, [XA, XB], [XA.copy(), XB.copy()], [np.zeros(len(PA), bool), np.zeros(len(PB), bool)], pred=pred)
    assert np.allclose(X1[0][a_v], X1[1][b_v])                       # one common position: welded again
    assert np.allclose(X1[0][a_v], (pred[0][a_v] + pred[1][b_v]) / 2)
    assert moved[0][a_v] and moved[1][b_v]
    assert [r for _, r in rules] == ["separated, no spike: mean of predictions"]
    # the other border pairs were joined and stay exactly where they are
    others = [g for g in range(len(groups)) if g != rules[0][0]]
    for g in others:
        for m, v in groups[g]:
            assert np.array_equal(X1[m][v], [XA, XB][m][v])


def test_spike_moves_with_its_shared_copy_and_a_half_spike_is_frozen():
    PA, PB, F = two()
    pairs, groups = S.coincident_groups([PA, PB])
    a_v, b_v = int(pairs[0, 1]), int(pairs[0, 3])
    XA, XB = PA.copy(), PB.copy()
    XA[a_v] += [0, 0, 5.0]; XB[b_v] += [0, 0, 5.0]       # a spike on the border: both copies (still joined)
    P1 = [XA.copy(), XB.copy()]; P1[0][a_v] = PA[a_v]; P1[1][b_v] = PB[b_v] + [0, 0, 0.01]
    mv = [np.zeros(len(PA), bool), np.zeros(len(PB), bool)]; mv[0][a_v] = mv[1][b_v] = True
    X1, moved, _ = S.group_targets(groups, [XA, XB], P1, mv)
    assert np.allclose(X1[0][a_v], X1[1][b_v]) and abs(X1[0][a_v][2]) < 0.01
    # only one side flagged while the copies are still joined: nothing moves (moving would open the border)
    mv2 = [mv[0].copy(), np.zeros(len(PB), bool)]
    X2, moved2, rules2 = S.group_targets(groups, [XA, XB], P1, mv2)
    assert np.array_equal(X2[0][a_v], XA[a_v]) and not moved2[0][a_v]
    assert ("joined, not all spikes: frozen" in [r for _, r in rules2])


def test_thickness_is_measured_against_the_other_sheet_and_kept():
    PA, F = slab(0.0, 4.0)
    pj, has = S.sheet_partner(PA, F)
    inner = [j * 5 + i for j in (1, 2) for i in (1, 2, 3)]          # away from the side walls (whose normals tilt)
    inner += [20 + v for v in inner]
    assert has[inner].all()
    t = S.thickness(PA, pj)
    assert np.allclose(t[inner], 2.7)
    # an outer vertex spiked 3 mm inward (through the inner sheet) and put back: thickness back to 2.7
    X = PA.copy(); X[6] += [0, 0, -3.0]
    assert abs(S.thickness(X, pj)[6] - 0.3) < 1e-9
    X[6] = PA[6]
    assert np.allclose(S.thickness(X, pj)[inner], 2.7)
