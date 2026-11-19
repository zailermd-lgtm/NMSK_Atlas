"""Pure functions of scripts/cryo/vhm_forearm_muscles_v4.py (Q166)."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts" / "cryo"))
import vhm_forearm_muscles_v4 as V4  # noqa: E402


def test_pair_stats_counts_boundary_pairs_2d_and_3d():
    L = np.array([[1, 1, 2], [1, 1, 2]]); E = np.array([[0, 0.2, 1.0], [0, 0.4, 0.0]])
    st = V4.pair_stats(L, E)
    assert list(st) == [(1, 2)] and st[(1, 2)][1] == 2 and np.isclose(st[(1, 2)][0], 1.4)   # max(0.2,1.0)+max(0.4,0)
    L3 = np.stack([L, np.full(L.shape, 3)])
    st3 = V4.pair_stats(L3, np.zeros(L3.shape))
    assert set(st3) == {(1, 2), (1, 3), (2, 3)} and st3[(1, 3)][1] == 4


def test_merge_weak_keeps_only_the_supported_boundary():
    L = np.zeros((6, 9), int); L[:, :3] = 1; L[:, 3:6] = 2; L[:, 6:] = 3
    E = np.zeros(L.shape); E[:, 5:7] = 1.0          # pale evidence only on the 2|3 boundary
    M = V4.merge_weak(L, E, 0.5)
    assert (M[:, :6] == M[0, 0]).all() and (M[:, 6:] != M[0, 0]).all() and len(np.unique(M)) == 2


def test_merge_weak_pools_boundaries_after_a_merge():
    # 1|2 weak; 1|3 strong and 2|3 weak: after 1+2 merge the pooled boundary to 3 is 50 % supported -> kept at 0.5
    L = np.array([[1, 3], [2, 3]]); E = np.array([[0.0, 1.0], [0.0, 0.0]])
    M = V4.merge_weak(L, E, 0.5)
    assert M[0, 0] == M[1, 0] and M[0, 1] != M[0, 0]


def test_septum_lines_are_one_pixel_and_regions_split_by_them():
    M = np.zeros((5, 8), int); M[:, :4] = 1; M[:, 4:] = 2
    ln = V4.septum_lines(M)
    assert ln.sum() == 5 and ln[:, 4].all()
    lab, n = V4.regions(M > 0, ln, min_px=2)
    assert n == 2 and (lab[:, 4] == 0).all()
    lab2, n2 = V4.regions(M > 0, ln, min_px=16)
    assert n2 == 1                                   # the 5 x 3 = 15 px piece is dropped


def test_iou_links_one_to_one_and_threshold():
    A = np.zeros((4, 10), int); A[:, :5] = 1; A[:, 5:] = 2
    B = np.zeros((4, 10), int); B[:, :10] = 7        # a fused slice: IoU 0.5 with each -> exactly at threshold
    assert sorted(x[:2] for x in V4.iou_links(A, B, 0.5)) == [(1, 7), (2, 7)]
    assert V4.iou_links(A, B, 0.51) == []
    C = np.zeros((4, 10), int); C[:, :6] = 1          # shifted by one column
    assert [x[:2] for x in V4.iou_links(A, C, 0.5)] == [(1, 1)]


def test_mutual_links_keep_the_larger_partner_of_a_fused_region():
    A = np.zeros((4, 10), int); A[:, :7] = 1; A[:, 7:] = 2
    B = np.ones((4, 10), int)
    assert [x[:2] for x in V4.mutual_links(A, B, 0.5)] == [(1, 1)]


def test_track_links_through_slices_and_one_gap_and_never_chains_two_bellies():
    R = np.zeros((5, 4, 10), np.int32)
    R[0, :, :5] = 1; R[0, :, 5:] = 2
    R[1, :, :5] = 1; R[1, :, 5:] = 2
    R[2, :, :] = 1                                   # septum missed: one fused region
    R[3, :, :5] = 1; R[3, :, 5:] = 2
    R[4, :, :5] = 2; R[4, :, 5:] = 1                 # label ids differ per slice; overlap decides
    B, n = V4.track(R, 0.51, skip=True, mode="iou")
    assert B[0, 0, 0] == B[1, 0, 0] == B[3, 0, 0] == B[4, 0, 0]          # left belly bridged over the fused slice
    assert B[0, 0, 9] == B[1, 0, 9] == B[3, 0, 9] == B[4, 0, 9]
    assert B[0, 0, 0] != B[0, 0, 9] and B[2, 0, 0] not in (B[0, 0, 0], B[0, 0, 9])
    assert n == 3


def test_name_bellies_majority_and_purity():
    belly = np.array([1, 1, 1, 1, 1, 2, 2, 2, 2, 2, 3, 3])
    rule = np.array([4, 4, 4, 4, 5, 4, 4, 5, 5, 0, 0, 0])
    nm = V4.name_bellies(belly, rule, 0.6)
    assert nm[1][0] == 4 and np.isclose(nm[1][1], 0.8)
    assert nm[2][0] == 0 and np.isclose(nm[2][1], 0.4)                  # impure -> unnamed
    assert nm[3][0] == 0


def test_contact_on_septum_uses_photographed_evidence_only():
    L = np.zeros((6, 11), int); L[:, :5] = 1; L[:, 6:] = 2          # one blank (septum line) column between them
    ev = np.zeros(L.shape, bool)
    c0 = V4.contact_on_septum(L, ev, reach=2, min_px=3)
    assert c0[1][0] == 0.0 and c0[2][0] == 0.0
    ev[:3, 5] = True                                                  # pale pixels on the top half of the line
    c1 = V4.contact_on_septum(L, ev, reach=2, min_px=3)
    assert 0.4 < c1[1][0] < 0.8


def test_gate_v4_and_stable_set():
    assert V4.gate_v4(10, 10, 0.99, 0.8)[0]
    assert not V4.gate_v4(10, 10, 0.99, 0.6)[0]
    assert not V4.gate_v4(10, 10, 0.99, None)[0]
    assert not V4.gate_v4(30, 10, 0.99, 0.9)[0]
    assert not V4.gate_v4(10, 10, 0.95, 0.9)[0]
    assert "OUT OF RANGE" in V4.gate_v4(10, 10, 0.99, 0.9, out_of_range=True)[1]
    assert V4.stable_set([{"a", "b"}, {"b", "c"}, {"b"}]) == {"b"} and V4.stable_set([]) == set()
