import json

import numpy as np
import pytest

from scripts.repair_continuity_q152 import (
    bridge_label_in_volume,
    classify_component,
    drop_mesh_islands,
    find_z_gap,
    mesh_components,
)


# ---------------------------------------------------------------------------
# classify_component / find_z_gap -- the pure gap-bridge vs island vs
# not-Z-aligned decision rule, independent of any real volume.
# ---------------------------------------------------------------------------

def test_tiny_far_component_is_dropped_as_island():
    # < 2% of volume AND > 15mm away -> DROP_ISLAND, regardless of any gap.
    assert classify_component(vol_frac=0.005, dist_mm=40.0,
                               has_z_gap=False, gap_mm=None) == "DROP_ISLAND"


def test_island_rule_wins_over_gap_when_both_apply():
    # A tiny speck that also happens to sit across an empty Z-run is still
    # dropped, not bridged -- less invasive, and per this rule's own
    # precedence (island checked first).
    assert classify_component(vol_frac=0.01, dist_mm=20.0,
                               has_z_gap=True, gap_mm=3.0) == "DROP_ISLAND"


def test_short_gap_is_bridged():
    assert classify_component(vol_frac=0.3, dist_mm=8.0,
                               has_z_gap=True, gap_mm=9.9) == "GAP_BRIDGE"
    assert classify_component(vol_frac=0.3, dist_mm=8.0,
                               has_z_gap=True, gap_mm=10.0) == "GAP_BRIDGE"  # inclusive


def test_gap_over_10mm_is_not_bridged():
    assert classify_component(vol_frac=0.3, dist_mm=8.0,
                               has_z_gap=True, gap_mm=10.1) == "GAP_TOO_LARGE"


def test_large_component_with_no_z_gap_is_not_z_aligned():
    # e.g. a genuinely separate anatomical belly sitting beside the main
    # body rather than above/below it in Z.
    assert classify_component(vol_frac=0.4, dist_mm=25.0,
                               has_z_gap=False, gap_mm=None) == "NOT_Z_ALIGNED"


def test_find_z_gap_detects_disjoint_run():
    has_gap, gap_mm, lo, hi = find_z_gap(main_zmin=0, main_zmax=10,
                                          other_zmin=15, other_zmax=20,
                                          z_spacing_mm=1.0)
    assert has_gap
    assert lo == 11 and hi == 14
    assert gap_mm == pytest.approx(4.0)


def test_find_z_gap_none_when_ranges_touch_or_overlap():
    has_gap, gap_mm, _lo, _hi = find_z_gap(0, 10, 10, 20, 1.0)
    assert not has_gap and gap_mm is None
    has_gap, gap_mm, _lo, _hi = find_z_gap(0, 10, 5, 20, 1.0)
    assert not has_gap and gap_mm is None


def test_find_z_gap_respects_spacing_mm():
    # 3 missing slices at 4mm spacing = 12mm, not 3mm.
    has_gap, gap_mm, _lo, _hi = find_z_gap(0, 5, 9, 20, 4.0)
    assert has_gap
    assert gap_mm == pytest.approx(3 * 4.0)


# ---------------------------------------------------------------------------
# bridge_label_in_volume -- shape-interpolation fill on a real (synthetic)
# labelled volume: never extrapolates, never overwrites another label.
# ---------------------------------------------------------------------------

def _disc(shape, center, radius):
    yy, xx = np.mgrid[0:shape[0], 0:shape[1]]
    return ((yy - center[0]) ** 2 + (xx - center[1]) ** 2) <= radius ** 2


def test_bridge_fills_only_the_empty_gap_slice():
    # z=0 and z=2 real (label 5); z=1 is a genuine gap. z is axis 0 here.
    Z, Y, X = 4, 20, 20
    vol = np.zeros((Z, Y, X), np.int32)
    vol[0][_disc((Y, X), (10, 10), 6)] = 5
    vol[2][_disc((Y, X), (10, 10), 6)] = 5
    bridged, n_added = bridge_label_in_volume(vol, label=5, z_ax=0, z_spacing_mm=1.0)
    assert n_added > 0
    assert (bridged[1] == 5).any()          # the gap slice is now filled
    assert (bridged[0] == 5).sum() == (vol[0] == 5).sum()   # real slices unchanged
    assert (bridged[2] == 5).sum() == (vol[2] == 5).sum()
    assert not (bridged[3] == 5).any()      # never extrapolates past the last real slice


def test_bridge_never_overwrites_another_label():
    # A second structure (label 9) sits exactly where the bridge would want
    # to grow into at the gap slice; it must survive untouched, and the
    # bridged label must not claim those voxels.
    Z, Y, X = 3, 20, 20
    vol = np.zeros((Z, Y, X), np.int32)
    vol[0][_disc((Y, X), (10, 10), 8)] = 5
    vol[2][_disc((Y, X), (10, 10), 8)] = 5
    vol[1][_disc((Y, X), (10, 10), 4)] = 9  # a neighbour occupying the gap's centre
    other_before = (vol[1] == 9).sum()
    bridged, _n = bridge_label_in_volume(vol, label=5, z_ax=0, z_spacing_mm=1.0)
    assert (bridged[1] == 9).sum() == other_before
    assert not np.any((bridged[1] == 5) & (vol[1] == 9))


def test_bridge_only_fills_approved_ranges_not_every_gap():
    # A label with TWO gaps: z=1 (short, approved) and z=5..7 (long, NOT
    # approved -- e.g. it measured over the 10mm cap). Only the approved one
    # may be filled, even though interpolate_labels_z's own default would
    # happily fill both between the label's first and last real slice.
    Z, Y, X = 9, 20, 20
    vol = np.zeros((Z, Y, X), np.int32)
    for z in (0, 2, 4, 8):
        vol[z][_disc((Y, X), (10, 10), 6)] = 3
    bridged, n_added = bridge_label_in_volume(vol, label=3, z_ax=0, z_spacing_mm=1.0,
                                               approved_ranges=[(1, 1)])
    assert (bridged[1] == 3).any()          # approved gap filled
    assert not (bridged[5] == 3).any()      # unapproved gap left alone
    assert not (bridged[6] == 3).any()
    assert not (bridged[7] == 3).any()
    assert n_added > 0


def test_bridge_respects_a_non_leading_z_axis():
    # Same fill, but z is the LAST array axis (as codes-derived z_ax can be
    # for a differently-oriented affine) -- must transpose correctly.
    Y, X, Z = 20, 20, 4
    vol = np.zeros((Y, X, Z), np.int32)
    vol[..., 0][_disc((Y, X), (10, 10), 6)] = 7
    vol[..., 2][_disc((Y, X), (10, 10), 6)] = 7
    bridged, n_added = bridge_label_in_volume(vol, label=7, z_ax=2, z_spacing_mm=1.0)
    assert n_added > 0
    assert (bridged[..., 1] == 7).any()
    assert not (bridged[..., 3] == 7).any()


# ---------------------------------------------------------------------------
# mesh_components / drop_mesh_islands -- mesh-space island drop, never
# touching a component that doesn't independently pass the island rule.
# ---------------------------------------------------------------------------

def _grid_mesh(center, n=10, spacing=1.0):
    """An n x n flat triangulated grid (one connected component, ~2*(n-1)^2
    faces) -- used as a stand-in 'real muscle' mesh with enough faces that a
    single stray triangle is a meaningfully small fraction of the total,
    which a fixed-topology box (always 12 faces regardless of scale) is
    not."""
    xs, ys = np.meshgrid(np.arange(n) * spacing, np.arange(n) * spacing)
    v = np.stack([xs.ravel(), ys.ravel(), np.zeros(n * n)], axis=1) + center
    faces = []
    for i in range(n - 1):
        for j in range(n - 1):
            a, b, c, d = i * n + j, i * n + j + 1, (i + 1) * n + j, (i + 1) * n + j + 1
            faces.append([a, b, c])
            faces.append([b, d, c])
    return v, np.array(faces)


def _box_mesh(center, half=1.0):
    """8 verts / 12 faces box centred at `center`."""
    signs = np.array([[sx, sy, sz] for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)])
    v = center + signs * half
    # a valid (if not outward-consistent) triangulation is enough for connectivity tests
    faces = np.array([
        [0, 1, 2], [1, 3, 2], [4, 6, 5], [5, 6, 7],
        [0, 4, 1], [1, 4, 5], [2, 3, 6], [3, 7, 6],
        [0, 2, 4], [2, 6, 4], [1, 5, 3], [3, 5, 7],
    ])
    return v, faces


def test_mesh_components_splits_two_disjoint_boxes():
    v1, f1 = _box_mesh(np.array([0.0, 0.0, 0.0]))
    v2, f2 = _box_mesh(np.array([100.0, 100.0, 100.0]))
    v = np.concatenate([v1, v2])
    f = np.concatenate([f1, f2 + len(v1)])
    comps = mesh_components(v, f)
    assert len(comps) == 2
    assert comps[0].sum() == len(f1)  # both boxes have equal face count; order stable either way
    assert comps[0].sum() + comps[1].sum() == len(f)


def test_drop_mesh_islands_drops_only_the_qualifying_speck(tmp_path, monkeypatch):
    import scripts.repair_continuity_q152 as m
    monkeypatch.setattr(m, "BUILD", tmp_path)

    main_v, main_f = _grid_mesh(np.array([0.0, 0.0, 0.0]), n=20)   # big body, 722 faces
    island_v, island_f = _box_mesh(np.array([200.0, 0.0, 0.0]), half=0.3)  # tiny, far speck (12 faces)
    v = np.concatenate([main_v, island_v])
    f = np.concatenate([main_f, island_f + len(main_v)])

    subject_dir = tmp_path / "ct_test_subject"
    subject_dir.mkdir()
    (subject_dir / "vertices.f32").write_bytes(v.astype(np.float32).tobytes())
    (subject_dir / "faces.u32").write_bytes(f.astype(np.uint32).tobytes())
    manifest = {"subject": "ct_test_subject", "frame": "atlas",
                "structures": [{"atlas_id": "fake_muscle_l", "side": "left",
                                 "vertex_offset": 0, "face_offset": 0,
                                 "vertex_count": int(len(v)), "triangle_count": int(len(f))}]}
    (subject_dir / "manifest.json").write_text(json.dumps(manifest))

    result = m.drop_mesh_islands("ct_test_subject", "fake_muscle_l", "left")
    assert result["dropped"] is True
    assert result["n_dropped"] == 1
    # the surviving mesh keeps exactly the main box's faces
    assert len(result["kept_faces"]) == len(main_f)
    assert result["dropped_face_frac"] == pytest.approx(len(island_f) / len(f), abs=1e-4)


def test_drop_mesh_islands_keeps_a_second_real_belly(tmp_path, monkeypatch):
    """Two comparably-sized, comparably-close components (e.g. a genuinely
    two-headed muscle) must NOT be treated as an island -- neither one is
    < 2% of the total nor far enough away to qualify."""
    import scripts.repair_continuity_q152 as m
    monkeypatch.setattr(m, "BUILD", tmp_path)

    v1, f1 = _box_mesh(np.array([0.0, 0.0, 0.0]), half=10.0)
    v2, f2 = _box_mesh(np.array([12.0, 0.0, 0.0]), half=10.0)  # close second head, similar size
    v = np.concatenate([v1, v2])
    f = np.concatenate([f1, f2 + len(v1)])

    subject_dir = tmp_path / "ct_test_subject2"
    subject_dir.mkdir()
    (subject_dir / "vertices.f32").write_bytes(v.astype(np.float32).tobytes())
    (subject_dir / "faces.u32").write_bytes(f.astype(np.uint32).tobytes())
    manifest = {"subject": "ct_test_subject2", "frame": "atlas",
                "structures": [{"atlas_id": "fake_two_head_l", "side": "left",
                                 "vertex_offset": 0, "face_offset": 0,
                                 "vertex_count": int(len(v)), "triangle_count": int(len(f))}]}
    (subject_dir / "manifest.json").write_text(json.dumps(manifest))

    result = m.drop_mesh_islands("ct_test_subject2", "fake_two_head_l", "left")
    assert result["dropped"] is False
    assert "did not carry over" in result["reason"] or "1 component" in result["reason"]
