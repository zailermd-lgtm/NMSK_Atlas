"""Q185 d/e/h/i/j: the generic bone-carve function against an analytic spherical 'bone'."""
import numpy as np
import trimesh

from scripts.bone_carve_q185 import P, carve, face_normals, fold_guard

R = 20.0


def sphere_bone(pts):
    pts = np.asarray(pts, float); r = np.linalg.norm(pts, axis=1); r[r < 1e-9] = 1e-9
    return R - r, pts / r[:, None]


def _flips(v0, v1, f):
    return int((np.einsum("ij,ij->i", face_normals(v0, f), face_normals(v1, f)) <= 0).sum())


def test_push_moves_shallow_vertices_to_surface():
    m = trimesh.creation.icosphere(3, radius=6.0); v = m.vertices + [R + 3.0, 0, 0]; f = m.faces   # <= 3 mm deep
    d0, _ = sphere_bone(v)
    v1, info = carve(v, f, sphere_bone, "push")
    d1, _ = sphere_bone(v1)
    assert (d0 > 1).mean() > 0.05 and (d1 > 1).sum() == 0 and np.all(d1[d0 > P["inside_tol"]] <= 0.0)
    assert np.allclose(v1[d0 < -2], v[d0 < -2])                                     # outside part untouched
    assert _flips(v, v1, f) == 0 and info["flipped_faces_left"] == 0


def test_push_is_bounded_deep_vertices_stay():
    m = trimesh.creation.icosphere(3, radius=6.0); v = m.vertices + [R + 1.0, 0, 0]; f = m.faces   # 5 mm deep
    d0, _ = sphere_bone(v)
    v1, info = carve(v, f, sphere_bone, "push")
    deep = d0 > P["max_depth"]
    assert deep.any() and np.allclose(v1[deep], v[deep]) and info["n_too_deep"] == int(deep.sum())
    assert np.linalg.norm(v1 - v, axis=1).max() <= P["max_depth"] + P["offset"] + 0.5 + 1e-9
    assert _flips(v, v1, f) == 0


def test_trim_cuts_a_tendon_at_the_bone_surface():
    c = trimesh.creation.cylinder(radius=2.0, height=30.0, sections=12)
    v = c.vertices @ np.array([[0, 0, 1], [0, 1, 0], [1, 0, 0]], float) + [R + 10.0, 0, 0]   # axis along x, 5 mm in bone
    d0, _ = sphere_bone(v)
    v1, info = carve(v, c.faces, sphere_bone, "trim")
    d1, _ = sphere_bone(v1)
    assert (d0 > 1).any() and np.all(d1 <= -P["offset"] + 0.05)
    assert np.allclose(v1[d0 < 0], v[d0 < 0])
    r0 = np.linalg.norm(v[d0 > 1][:, 1:], axis=1); r1 = np.linalg.norm(v1[d0 > 1][:, 1:], axis=1)
    assert np.allclose(r0, r1)                                                      # slid along the axis: radius kept


def test_shell_refuses_large_moves():
    m = trimesh.creation.icosphere(2, radius=3.0); v = m.vertices + [R - 5.0, 0, 0]     # median move >> 3 mm
    v1, info = carve(v, m.faces, sphere_bone, "shell")
    assert info.get("refused") and np.allclose(v1, v)


def test_fold_guard_reverts_a_flip():
    v0 = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [1, 1, 0]], float); f = np.array([[0, 1, 2], [1, 3, 2]])
    v1 = v0.copy(); v1[3] = [-1, -1, 0]                                             # flips the second face
    out, info = fold_guard(v0, v1, f, np.array([False, False, False, True]))
    assert info["flipped_faces_left"] == 0 and _flips(v0, out, f) == 0


# ---------------------------------------------------------------- Q185 b/f/g extensions
def sphere_skin(pts):
    """outside an analytic skin of radius R: (distance outside [> 0 outside], unit direction inwards)"""
    pts = np.asarray(pts, float); r = np.linalg.norm(pts, axis=1); r[r < 1e-9] = 1e-9
    return r - R, -pts / r[:, None]


def test_skin_pull_in_to_one_mm_below_and_bounded():
    from scripts.bone_carve_q185 import P_SKIN
    m = trimesh.creation.icosphere(3, radius=6.0); v = m.vertices + [R - 3.0, 0, 0]; f = m.faces    # <= 3 mm outside
    d0, _ = sphere_skin(v)
    v1, info = carve(v, f, sphere_skin, "push", P_SKIN)
    d1, _ = sphere_skin(v1)
    assert (d0 > 0).mean() > 0.05 and (d1 > 0).sum() == 0 and np.all(d1[d0 > 0] <= -P_SKIN["offset"] + 0.05)
    assert np.allclose(v1[d0 < -2], v[d0 < -2]) and _flips(v, v1, f) == 0
    v = m.vertices + [R + 1.0, 0, 0]                                                                 # up to 7 mm outside
    d0, _ = sphere_skin(v); v1, info = carve(v, f, sphere_skin, "push", P_SKIN)
    far = d0 > P_SKIN["max_depth"]
    assert far.any() and np.allclose(v1[far], v[far]) and info["n_too_deep"] == int(far.sum())


def test_skin_fov_cut_vertices_are_not_pulled():
    from scripts.bone_carve_q185 import SkinField
    K = SkinField.__new__(SkinField); K.cut_lo, K.cut_hi = -233.4, None
    b = K.beyond(np.array([[-240.0, 0, 0], [-231.0, 0, 0], [-228.0, 0, 0], [240.0, 0, 0]]))
    assert b.tolist() == [True, True, False, False]


def test_in_hull_orbit_gate():
    from scipy.spatial import ConvexHull
    from scripts.bone_carve_q185 import in_hull
    H = ConvexHull(trimesh.creation.box(extents=(10, 10, 10)).vertices)
    pts = np.array([[0, 0, 0], [6.0, 0, 0], [9.0, 0, 0]])
    assert in_hull(H, pts, 0.0) == 1 / 3 and in_hull(H, pts, 3.0) == 2 / 3
