"""Q144/Q145: the correction-file loader/applier (scripts/zanatomy/apply_corrections.py)
and the radial-nerve correction file it reads (data/corrections/zanatomy/radial_n.json).

Deliberately does not touch build/zanatomy/ (the ~90MB gitignored Z-Anatomy
extraction) or build/vh/zan_ref_* -- those are exercised by actually running
scripts/zanatomy/build_zan_reference.py, not by this fast, always-runnable suite.
Q145's own lateral-push tests below follow the same rule: they build a tiny
synthetic Skeletal/ directory (a few points for "Humerus", a trimesh primitive
for the bone to push away from) under tmp_path rather than reading the real
extraction, so they stay fast and runnable with no Z-Anatomy data on disk.
"""
import json

import numpy as np
import pytest
import trimesh

from scripts.zanatomy.apply_corrections import (
    DEFAULT_CORRECTIONS_DIR, _bone_repulsion_direction, _centreline_by_y,
    _load_bone_mesh, apply_correction, bump_warp_y, load_corrections,
)


def _raw_from_atlas(v: np.ndarray) -> np.ndarray:
    """Inverse of zan_source.to_atlas_frame(), so a test can specify synthetic
    geometry directly in the atlas frame (X right, Y superior, Z anterior) and
    write it to a fake .npz the way extract_fbx.py's real output stores it (raw
    Z-Anatomy frame), for _load_bone_mesh()/apply_correction() to read back."""
    out = np.empty_like(v)
    out[:, 0] = -v[:, 0]
    out[:, 1] = -v[:, 2]
    out[:, 2] = v[:, 1]
    return out


def _write_bone_npz(path, atlas_vertices, faces):
    path.parent.mkdir(parents=True, exist_ok=True)
    np.savez(path, vertices_mm=_raw_from_atlas(atlas_vertices), faces=np.asarray(faces))


def test_bump_warp_y_anchors_and_clamping():
    anchors = [(0.0, 0.0), (-10.0, -5.0), (-20.0, 0.0)]
    y = np.array([5.0, 0.0, -5.0, -10.0, -15.0, -20.0, -25.0])
    shift = bump_warp_y(y, anchors)
    # exactly on an anchor -> exactly that anchor's shift
    assert shift[1] == pytest.approx(0.0)   # y=0
    assert shift[3] == pytest.approx(-5.0)  # y=-10
    assert shift[5] == pytest.approx(0.0)   # y=-20
    # outside the outermost anchors -> clamped to the nearest anchor's shift
    assert shift[0] == pytest.approx(0.0)    # y=5, above the top anchor
    assert shift[6] == pytest.approx(0.0)    # y=-25, below the bottom anchor
    # between anchors -> strictly between the two anchor shifts (smoothstep)
    assert -5.0 < shift[2] < 0.0   # y=-5, between (0, 0) and (-10, -5)
    assert -5.0 < shift[4] < 0.0   # y=-15, between (-10, -5) and (-20, 0)


def test_bump_warp_y_is_smooth_and_monotonic_for_a_dense_sample():
    # a bump whose shift magnitude is smaller than the anchor spacing must keep
    # y' = y + shift(y) strictly increasing -- no self-intersection/fold in the
    # warped mesh (Q144's own "bounded displacement, no topology change" rule).
    anchors = [(0.0, 0.0), (-20.0, -8.0), (-60.0, 0.0)]
    y = np.linspace(10, -70, 4000)
    shift = bump_warp_y(y, anchors)
    warped = y + shift
    # y is descending here, so warped must be strictly descending too
    assert np.all(np.diff(warped) < 0)


def test_load_corrections_finds_radial_n():
    corrections = load_corrections()
    assert "posterior_interosseous_n_r" in corrections
    assert "posterior_interosseous_n_l" in corrections
    rec = corrections["posterior_interosseous_n_r"]
    assert rec is corrections["posterior_interosseous_n_l"], "both sides share one correction file"
    c = rec["correction"]
    assert set(c["applies_to_ids"]) == {"posterior_interosseous_n_r", "posterior_interosseous_n_l"}
    assert len(c["anchors_offset_from_LE_mm"]) >= 2
    for off, shift in c["anchors_offset_from_LE_mm"]:
        assert isinstance(off, (int, float)) and isinstance(shift, (int, float))
    assert c["procedural_badge_note"]
    # every landmark the audit measured must carry a citation or be explicitly
    # marked unsourced -- "never invented" (task instruction), checked structurally.
    for lm in rec["landmarks"]:
        assert lm["citation"] or lm["status"].startswith("unsourced")


def test_load_corrections_empty_directory_is_a_noop(tmp_path):
    assert load_corrections(tmp_path) == {}


def test_apply_correction_is_a_noop_for_an_uncorrected_id():
    v = np.random.RandomState(0).rand(20, 3).astype(np.float64)
    out, note = apply_correction("some_other_nerve_r", v, DEFAULT_CORRECTIONS_DIR, load_corrections())
    assert note is None
    assert np.array_equal(out, v)


def test_correction_file_is_well_formed_json():
    path = DEFAULT_CORRECTIONS_DIR / "radial_n.json"
    rec = json.loads(path.read_text())
    assert rec["correction"]["applies_to_ids"]
    assert rec["landmarks"]
    # at least one landmark corrected, at least one left alone -- this task's
    # own "only correct what's actually out of range" rule, checked structurally
    # rather than trusting the prose.
    statuses = {lm["corrected"] for lm in rec["landmarks"]}
    assert statuses == {True, False}


def test_radial_n_correction_has_a_lateral_push_q145():
    """Q145's own addition: the arcade-of-Frohse landmark is now a 3-D warp, not
    just Y -- checked structurally so a future edit can't silently drop the
    lateral-push component and quietly regress to Q144's partial fix."""
    rec = json.loads((DEFAULT_CORRECTIONS_DIR / "radial_n.json").read_text())
    lateral = rec["correction"]["lateral_push"]
    assert lateral["away_from"]
    assert len(lateral["anchors_offset_from_LE_mm"]) >= 2
    assert lateral["max_mm"] > 0
    # the two independently-referenced targets (Aggarwal direct-LE, Hazani
    # converted-via-radial-head) must be kept as SEPARATE fields, not pooled into
    # one merged cited_range (this task's own explicit instruction).
    entry = next(lm for lm in rec["landmarks"] if lm["id"] == "e_pin_supinator_entry")
    assert entry["cited_range"] is None
    assert isinstance(entry["aggarwal_target_distal_to_LE_mm"], (int, float))
    assert isinstance(entry["hazani_target_distal_to_LE_mm"], (int, float))
    assert entry["corrected"] is True


# -- Q145: _centreline_by_y / _bone_repulsion_direction / lateral_push, on synthetic
# geometry (no build/zanatomy/ needed) --------------------------------------------

def test_centreline_by_y_tracks_a_simple_path():
    # a straight diagonal "nerve" from (0,100,0) to (10,0,5): the per-Y-bin
    # centroid should itself lie on that same line at every sampled Y.
    t = np.linspace(0, 1, 500)
    v = np.stack([10 * t, 100 * (1 - t), 5 * t], axis=1)
    cl = _centreline_by_y(v, nbins=20)
    assert cl[0, 1] > cl[-1, 1]  # sorted superior (high Y) -> inferior (low Y)
    expected_x = 10 * (1 - cl[:, 1] / 100)
    assert np.allclose(cl[:, 0], expected_x, atol=1.0)


def test_bone_repulsion_direction_points_away_from_the_bone():
    # a bone (unit cube) centred on the Y axis at X=Z=0; centreline samples sit
    # off to the +X side -- the repulsion direction should point further +X.
    bone = trimesh.creation.box(extents=[10, 200, 10])
    bone.vertices[:, 1] += 50  # centre the box's Y-extent near the nerve's own range
    centreline = np.array([[8.0, y, 0.0] for y in np.linspace(90, 10, 30)])
    direction = _bone_repulsion_direction(centreline[:, 1], centreline, bone)
    assert direction.shape == (30, 2)
    assert np.all(direction[:, 0] > 0.9)  # essentially pure +X, away from the box
    norms = np.linalg.norm(direction, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-6)


def test_apply_correction_lateral_push_moves_vertices_away_from_named_bone(tmp_path):
    """End-to-end apply_correction() with a synthetic Skeletal/ directory: checks
    the lateral_push component actually increases clearance from the named bone
    in the anchored region, leaves the untouched (zero-magnitude) anchors alone,
    and that the existing bone-avoidance pass still runs afterwards."""
    zan_dir = tmp_path

    # Synthetic "Humerus.r": a handful of points whose lowest-Y (distal) 15mm slab
    # has its most-lateral (max X) point at atlas Y=905 -- lateral_epicondyle_y()
    # will read that as LE_y=905 (the min-Y point itself, since it is also the
    # most-lateral one in that slab).
    humerus_atlas = np.array([
        [30.0, 905.0, 0.0], [10.0, 908.0, 2.0], [20.0, 950.0, -3.0],
        [15.0, 1000.0, 0.0], [-5.0, 905.0, 1.0],
    ])
    _write_bone_npz(zan_dir / "Skeletal" / "Humerus.r.npz", humerus_atlas,
                     faces=[[0, 1, 2]])

    # Synthetic "Radius.r": a box the nerve will run close alongside.
    bone = trimesh.creation.box(extents=[10, 200, 10])
    bone.vertices[:, 1] += 800  # atlas Y in [700, 900], i.e. distal to the LE at 900
    _write_bone_npz(zan_dir / "Skeletal" / "Radius.r.npz", bone.vertices, bone.faces)

    # Synthetic PIN: a straight vertical line just outside the box's +X face
    # (box spans X in [-5,5]; nerve at X=6, i.e. 1mm clearance). Endpoints sit
    # exactly at the two zero-magnitude anchors (LE_y=905, offsets -5/-190).
    y = np.linspace(900.0, 715.0, 200)
    v = np.stack([np.full_like(y, 6.0), y, np.zeros_like(y)], axis=1)

    corr = {
        "correction": {
            "applies_to_ids": ["test_nerve_r"],
            "anchors_offset_from_LE_mm": [[-5.0, 0.0], [-190.0, 0.0]],  # no Y-shift: isolate the lateral push
            "lateral_push": {
                "away_from": "Radius",
                "anchors_offset_from_LE_mm": [[-5.0, 0.0], [-95.0, 5.0], [-190.0, 0.0]],
                "max_mm": 8.0,
            },
            "avoid_penetration_of": ["Radius"],
            "procedural_badge_note": "test",
        }
    }
    corrections = {"test_nerve_r": corr}
    out, note = apply_correction("test_nerve_r", v, zan_dir, corrections)

    assert note == "test"
    assert out.shape == v.shape
    # Y is untouched by this correction file (both Y-anchors are shift=0).
    assert np.allclose(out[:, 1], v[:, 1])
    # the midpoint (offset ~-95mm from LE, the lateral_push plateau) must have moved
    # further from the box than it started (clearance increased).
    mid = len(v) // 2
    bone_mesh = _load_bone_mesh(zan_dir, "r", "Radius")
    before = bone_mesh.nearest.on_surface(v[mid:mid + 1])[1][0]
    after = bone_mesh.nearest.on_surface(out[mid:mid + 1])[1][0]
    assert after > before + 1.0
    # the two zero-magnitude anchors (near the very ends) are left in place.
    assert np.allclose(out[0], v[0], atol=1e-6)
    assert np.allclose(out[-1], v[-1], atol=1e-6)
    # bone-avoidance pass still guarantees no penetration anywhere.
    assert bone_mesh.contains(out).sum() == 0
