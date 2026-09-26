"""Q147: per-bone (not global/segment) dominant-bone selection and blending for the
forearm/hand/foot Z-Anatomy transfer -- scripts/transfer/limb_per_bone_transfer.py."""
import sys
from pathlib import Path

import numpy as np
import trimesh

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
from scripts.transfer import bone_frames  # noqa: E402
from scripts.transfer.limb_per_bone_transfer import (  # noqa: E402
    dominant_bones, in_scope, blend_by_bones, push_off_bones, clip_to_skin_mesh, base_bone,
)


def test_base_bone_strips_side_suffix():
    assert base_bone("radius_r") == "radius" and base_bone("phalanges_hand_l") == "phalanges_hand"
    assert base_bone("sciatic_n") == "sciatic_n"  # no _r/_l -- left untouched, not mis-stripped


def test_dominant_bones_from_attachments_keeps_radius_and_ulna_separate():
    # flexor_digitorum_superficialis_r-shaped record: origin on the humerus (proximal,
    # out of this task's local bone set), insertion on the hand, one via-point on the
    # carpals -- radius/ulna must still be added (region upper_limb, the belly itself
    # is forearm) and radius/ulna must NEVER be merged into one bone id.
    rec = {"attachments": {"origin_bone": "humerus_r", "insertion_bone": "phalanges_hand_r",
                            "via_points": [{"bone_frame": "carpals_r"}]}}
    bones = dominant_bones(rec, "upper_limb", "r")
    assert bones == ["carpals_r", "phalanges_hand_r", "radius_r", "ulna_r"]
    assert "radius_r" in bones and "ulna_r" in bones and "radius_r" != "ulna_r"


def test_dominant_bones_single_bone_ligament():
    rec = {"attachments": {"bone_a": "ulna_r", "landmark_a": "olecranon"}}
    assert dominant_bones(rec, "elbow", "r") == ["ulna_r"]


def test_dominant_bones_region_fallback_when_no_attachments():
    assert dominant_bones({}, "ankle_foot", "l") == ["metatarsals_l", "phalanges_foot_l", "tarsals_l"]
    assert dominant_bones({}, "forearm", "r") == ["radius_r", "ulna_r"]


def test_in_scope_excludes_leg_but_keeps_intrinsic_foot():
    # fibularis brevis/tertius-shaped: lower_limb region but touches fibula (a LEG bone)
    # -- out of Q147 scope even though it is a real, currently-missing structure.
    assert in_scope("lower_limb", {"fibula"}) is False
    # abductor_hallucis-shaped: lower_limb region, bones entirely within the foot set.
    assert in_scope("lower_limb", {"tarsals", "phalanges_foot"}) is True
    assert in_scope("wrist_hand", set()) is True
    assert in_scope("elbow", {"ulna"}) is False


def _box(size, centre):
    sx, sy, sz = [s / 2 for s in size]
    v = np.array([[x, y, z] for x in (-sx, sx) for y in (-sy, sy) for z in (-sz, sz)], np.float64) + np.array(centre)
    f = np.array([[0, 1, 3], [0, 3, 2], [4, 6, 7], [4, 7, 5], [0, 4, 5], [0, 5, 1],
                  [2, 3, 7], [2, 7, 6], [0, 2, 6], [0, 6, 4], [1, 5, 7], [1, 7, 3]], np.int64)
    return v, f


def _bone_map_entry(src_v, dst_v, tree_points=None):
    from scipy.spatial import cKDTree
    fs, fd = bone_frames.bone_frame(src_v), bone_frames.bone_frame(dst_v)
    A, t = bone_frames.bone_affine(fs, fd, uniform=True)
    # a real bone's own cKDTree is built from its full (dense) mesh, not 8 box
    # corners -- `tree_points` lets a test give it a shape closer to a real bone's
    # own vertex density along its length, while the box corners above still fit
    # a well-conditioned PCA frame.
    return {"A": A, "t": t, "side": "right", "tree": cKDTree(tree_points if tree_points is not None else src_v),
            "det": float(np.linalg.det(A)), "src": fs, "dst": fd}


def test_blend_by_bones_single_candidate_matches_bone_affine_exactly():
    rng = np.random.default_rng(2)
    radius_src, _ = _box((10, 250, 8), (30, 0, 0))
    radius_dst, _ = _box((11, 230, 9), (28, 0, 5))
    maps = {"radius_r": _bone_map_entry(radius_src, radius_dst)}
    v = rng.uniform(-1, 1, (50, 3)) * np.array([5, 100, 4]) + np.array([30, 0, 0])
    out, used = blend_by_bones(v, maps, ["radius_r"])
    expect = bone_frames.apply(maps["radius_r"]["A"], maps["radius_r"]["t"], v)
    assert np.allclose(out, expect) and used == {"radius_r": 1.0}


def test_blend_by_bones_weights_by_nearest_bone_side_by_side():
    # radius/ulna sit side by side (as in the real forearm) with DIFFERENT scale
    # factors -- a vertex near one bone should be dominated by that bone's own
    # affine, never averaged 50/50 regardless of which side it is on.
    radius_src, _ = _box((10, 250, 8), (30, 0, 0))
    radius_dst, _ = _box((10, 250, 8), (30, 0, 0))          # identity map (no scale change)
    ulna_src, _ = _box((10, 250, 8), (-30, 0, 0))
    ulna_dst, _ = _box((20, 250, 8), (-30, 0, 0))           # 2x scale in X only
    # dense per-bone point clouds (a real bone mesh's own vertices span its whole
    # shaft, not just 8 box corners) so nearest-vertex distance means something at
    # y=0, in the middle of the shaft, not just near the box's own corners.
    ys = np.linspace(-120, 120, 60)
    radius_cloud = np.stack([np.full_like(ys, 30.0), ys, np.zeros_like(ys)], axis=1)
    ulna_cloud = np.stack([np.full_like(ys, -30.0), ys, np.zeros_like(ys)], axis=1)
    maps = {"radius_r": _bone_map_entry(radius_src, radius_dst, tree_points=radius_cloud),
            "ulna_r": _bone_map_entry(ulna_src, ulna_dst, tree_points=ulna_cloud)}
    near_radius = np.array([[29.0, 0.0, 0.0]])
    near_ulna = np.array([[-29.0, 0.0, 0.0]])
    out_r, used_r = blend_by_bones(near_radius, maps, ["radius_r", "ulna_r"], k_nearest=2)
    out_u, used_u = blend_by_bones(near_ulna, maps, ["radius_r", "ulna_r"], k_nearest=2)
    assert used_r["radius_r"] > 0.9   # near the radius: radius affine dominates
    assert used_u["ulna_r"] > 0.9     # near the ulna: ulna affine dominates
    assert abs(out_r[0, 0] - 29.0) < 1.0         # radius map is ~identity here
    assert out_r[0, 0] != out_u[0, 0]            # the two bones' own (different) affines actually took effect


def test_blend_by_bones_no_driving_bone_returns_reason():
    v = np.zeros((5, 3))
    out, reason = blend_by_bones(v, {}, ["radius_l", "ulna_l"])
    assert out is None and "no driving bone" in reason


def test_push_off_bones_moves_interior_point_to_surface():
    bone = trimesh.creation.box(extents=[20, 20, 20])
    pts = np.array([[0.0, 0.0, 0.0], [100.0, 0.0, 0.0]])   # first is deep inside, second far outside
    out, n_pushed = push_off_bones(pts, [bone], clearance_mm=1.0)
    assert n_pushed == 1
    assert not bone.contains(out[:1])[0]
    assert np.allclose(out[1], pts[1])   # untouched: already outside


def test_clip_to_skin_mesh_pulls_outside_vertex_back_in():
    skin = trimesh.creation.icosphere(radius=50.0)
    v = np.array([[0.0, 0.0, 0.0], [200.0, 0.0, 0.0]])  # centre (inside) + far outside
    out, n_clipped = clip_to_skin_mesh(v, skin)
    assert n_clipped == 1
    assert skin.contains(out[1:2])[0]
    assert np.allclose(out[0], v[0])


def test_clip_to_skin_mesh_no_skin_is_a_noop():
    v = np.array([[0.0, 0.0, 0.0]])
    out, n = clip_to_skin_mesh(v, None)
    assert n == 0 and np.allclose(out, v)
