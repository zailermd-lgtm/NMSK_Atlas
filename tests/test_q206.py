"""Q206: the wrist / hand soft-tissue carry (bone-anchored field, guards), the continuity metric, and (when the Q206 pages are built) the page-level guards: scope = the listed structures only,
only non-bone / non-muscle structures moved, female clinical files unchanged, no card name equals its raw id, every moved card carries its before -> after numbers."""
import json
import re
import sys
from pathlib import Path

import numpy as np
import pytest
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from scripts.zanatomy import q206_carry as C  # noqa: E402
from scripts.zanatomy import q206_env as EN  # noqa: E402
from scripts.zanatomy import q205_pages as P  # noqa: E402

PAGES = {"male": (REPO / "build" / "q206" / "viewer_zan_vhm", "atlas_viewer_zan_male_fitted", REPO / "build" / "q205" / "viewer_zan_vhm"),
         "female": (REPO / "build" / "q206" / "viewer_zan_female", "atlas_viewer_zan_female", REPO / "build" / "q205" / "viewer_zan_female")}


# ------------------------------------------------------------------------------------------------ synthetic: field / guards
def icosphere(r=10.0, n=2):
    t = (1 + 5 ** 0.5) / 2
    v = np.array([[-1, t, 0], [1, t, 0], [-1, -t, 0], [1, -t, 0], [0, -1, t], [0, 1, t], [0, -1, -t], [0, 1, -t], [t, 0, -1], [t, 0, 1], [-t, 0, -1], [-t, 0, 1]], float)
    f = np.array([[0, 11, 5], [0, 5, 1], [0, 1, 7], [0, 7, 10], [0, 10, 11], [1, 5, 9], [5, 11, 4], [11, 10, 2], [10, 7, 6], [7, 1, 8], [3, 9, 4], [3, 4, 2], [3, 2, 6], [3, 6, 8], [3, 8, 9],
                  [4, 9, 5], [2, 4, 11], [6, 2, 10], [8, 6, 7], [9, 8, 1]])
    for _ in range(n):
        v = list(v / np.linalg.norm(v, axis=1, keepdims=True))
        cache, nf = {}, []

        def mid(a, b):
            k = tuple(sorted((a, b)))
            if k not in cache:
                m = (v[a] + v[b]) / 2
                v.append(m / np.linalg.norm(m))
                cache[k] = len(v) - 1
            return cache[k]
        for a, b, c in f:
            ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
            nf += [[a, ab, ca], [b, bc, ab], [c, ca, bc], [ab, bc, ca]]
        v, f = np.array(v), np.array(nf)
    return v / np.linalg.norm(v, axis=1, keepdims=True) * r, f


class FakeEnv:
    """a bone ball of radius 10 at the origin; skin = a plane at x = +40 (outside is x > 40)"""
    def __init__(self):
        g = np.linspace(-30, 60, 91)
        X, Y, Z = np.meshgrid(g, g[:61], g[:61], indexing="ij")
        r = np.sqrt(X ** 2 + (Y - 0) ** 2 + (Z - 0) ** 2)
        lo = np.array([-30.0, -30.0, -30.0])
        self.bone = {"r": EN.Fields((r - 10.0).astype(np.float32), lo, 1.0)}
        self.skin = EN.Fields((X - 40.0).astype(np.float32), lo, 1.0)

    def depth(self, P, side):
        return np.maximum(-self.bone[side].value(P, outside=1.0), 0.0)

    def skin_sd(self, P):
        return self.skin.value(P)


def test_fields_value_and_gradient_point_outward():
    env = FakeEnv()
    P = np.array([[5.0, 0.0, 0.0], [20.0, 0.0, 0.0]])
    d = env.depth(P, "r")
    assert abs(d[0] - 5.0) < 0.6 and d[1] == 0.0
    g = env.bone["r"].gradient(P)
    assert g[0, 0] > 0.9 and g[1, 0] > 0.9


def test_push_out_removes_a_tube_from_the_bone_and_keeps_it_coherent():
    env = FakeEnv()
    # a straight tube (ring of 6) along y through the bone's top
    ys = np.arange(-20, 21, 2.0)
    ang = np.linspace(0, 2 * np.pi, 7)[:-1]
    v = np.array([[6.0 + 0.8 * np.cos(a), y, 0.8 * np.sin(a)] for y in ys for a in ang])
    f = []
    for i in range(len(ys) - 1):
        for k in range(6):
            a, b, c, d = i * 6 + k, i * 6 + (k + 1) % 6, (i + 1) * 6 + k, (i + 1) * 6 + (k + 1) % 6
            f += [[a, b, c], [b, d, c]]
    f = np.array(f)
    ins0 = (env.depth(v, "r") > 1.0).mean()
    v1 = C.push_out(env, "r", v, f, 1.0, 5.0)
    assert ins0 > 0.2
    assert (env.depth(v1, "r") > 1.5).mean() < ins0 * 0.2
    assert np.linalg.norm(v1 - v, axis=1).max() <= C.PUSH_MAX + 1e-6
    # ring stays a ring: the radius of the cross-section changes by less than 40 %
    ring0 = np.linalg.norm(v[:6] - v[:6].mean(0), axis=1).mean()
    ring1 = np.linalg.norm(v1[ys.size // 2 * 6: ys.size // 2 * 6 + 6] - v1[ys.size // 2 * 6: ys.size // 2 * 6 + 6].mean(0), axis=1).mean()
    assert abs(ring1 / ring0 - 1) < 0.4


def test_clamp_skin_brings_vertices_back_inside_but_not_more_than_the_cap():
    env = FakeEnv()
    v, f = icosphere(3.0, 2)
    v = v + np.array([45.0, 0, 0])                              # 5 mm outside the plane at x = 40
    v1 = C.clamp_skin(env, v, f, 5.0)
    assert (env.skin_sd(v1) > 1.0).mean() < 0.1
    assert np.linalg.norm(v1 - v, axis=1).max() <= C.SKIN_MAX + 1e-6
    far = v + np.array([60.0, 0, 0])                            # 65 mm outside: capped, not teleported
    v2 = C.clamp_skin(env, far, f, 5.0)
    assert np.linalg.norm(v2 - far, axis=1).max() <= C.SKIN_MAX + 1e-6


def test_guard_respects_the_displacement_cap_of_the_candidate():
    env = FakeEnv()
    v, f = icosphere(2.0, 2)
    r = v.copy()
    v = v + np.array([2.0, 0, 0])
    g = C.guard(env, "r", v, f, r, "vessel", "x", v, None)
    assert np.linalg.norm(g - v, axis=1).max() <= C.CAP_MM + 1e-6
    assert env.depth(g, "r").max() < 2.0


def test_wrist_field_follows_the_moved_bone_and_vanishes_far_away():
    ico_v, ico_f = icosphere(10.0, 2)
    by = {"hand_bone_r": {"cat": "bone", "v": ico_v + np.array([8.0, 0, 0]), "f": ico_f}, "fixed_bone_r": {"cat": "bone", "v": ico_v + np.array([60.0, 0, 0]), "f": ico_f}}
    pre = {"hand_bone_r": ico_v.copy(), "fixed_bone_r": ico_v + np.array([60.0, 0, 0])}
    F = C.WristField("r", by, pre, np.zeros(3))
    assert list(F.moving) == ["hand_bone_r"]
    near = F(np.array([[11.0, 0.0, 0.0]]))[0]
    assert 5.0 < near[0] < 8.0 and abs(near[1]) < 0.5
    far = F(np.array([[400.0, 0.0, 0.0]]))[0]
    assert np.linalg.norm(far) < 0.5
    on_fixed = F(np.array([[70.0, 0.0, 0.0]]))[0]
    assert np.linalg.norm(on_fixed) < 1.5


def test_cost_prefers_inside_skin_and_outside_bone():
    base = {"outside_skin_pct": 0.0, "inside_bone_pct": 0.0, "stretched_pct": 0.0, "folded_pct": 0.0}
    bad = dict(base, outside_skin_pct=20.0, inside_bone_pct=30.0)
    assert C.cost(base, "vessel", base) < C.cost(bad, "vessel", base)
    assert C.cost(dict(base, inside_bone_pct=30.0), "ligament", base) < C.cost(dict(base, inside_bone_pct=30.0), "vessel", base)       # ligaments may touch bone


def test_zone_filter_takes_arm_structures_only():
    d = {"cat": "vessel"}
    tree = cKDTree(np.zeros((1, 3)))
    v = np.zeros((4, 3))
    assert C.in_zone("r", "zan_ulnar_artery_r", d, v, v, tree, np.zeros(3), {"zan_ulnar_artery_r": "forearm_hand"})
    assert not C.in_zone("r", "zan_external_iliac_artery_r", d, v, v, tree, np.zeros(3), {"zan_external_iliac_artery_r": "lower_limb"})
    assert not C.in_zone("r", "zan_ulnar_artery_l", d, v, v, tree, np.zeros(3), {"zan_ulnar_artery_l": "forearm_hand"})
    assert not C.in_zone("r", "radius_r", {"cat": "bone"}, v, v, tree, np.zeros(3), {"radius_r": "forearm_hand"})
    assert not C.in_zone("r", "pronator_teres_r", {"cat": "muscle"}, v, v, tree, np.zeros(3), {"pronator_teres_r": "forearm_hand"})


# ------------------------------------------------------------------------------------------------ continuity metric
def test_continuity_chain_gap_is_the_closest_vertex_distance():
    from scripts.zanatomy import q206_continuity as CT
    S = [{"id": "zan_radial_artery_r", "v": np.array([[0.0, 0, 0], [0, 10, 0]])}, {"id": "zan_deep_palmar_arch_r", "v": np.array([[3.0, 12, 0], [30, 0, 0]])}]
    g = CT.gaps(S, "r")
    assert g == {"zan_radial_artery -> zan_deep_palmar_arch": round(float(np.hypot(3, 2)), 2)}


# ------------------------------------------------------------------------------------------------ committed result files
def test_summary_file_has_both_pages_and_the_wrist_counts():
    f = REPO / "data" / "derived" / "Q206_summary.json"
    if not f.exists():
        pytest.skip("summary not written")
    s = json.loads(f.read_text())
    for w in ("male", "female"):
        assert set(s[w]["wrist_junction_major_moderate_minor"]) >= {"before", "after"}


# ------------------------------------------------------------------------------------------------ page level (only when the pages are built)
def have(which):
    d, stem, _ = PAGES[which]
    return (d / f"{stem}.html").exists() and (REPO / "data" / "derived" / f"Q206_ship_diff_{which}.json").exists()


@pytest.mark.parametrize("which", ["male", "female"])
def test_scope_only_listed_structures_changed_and_none_is_bone_or_muscle(which):
    if not have(which):
        pytest.skip("Q206 page not built here")
    r = json.loads((REPO / "data" / "derived" / f"Q206_ship_diff_{which}.json").read_text())
    assert r["geometry_changed_but_not_listed"] == []
    assert r["added"] == [] and r["removed"] == []
    man, _ = P.load_page(PAGES[which][2], PAGES[which][1])
    sysof = {m["id"]: m["sys"] for m in man["meshes"]}
    assert all(sysof[i] not in ("bone", "muscle", "skin") for i in r["geometry_changed"])


@pytest.mark.parametrize("which", ["male", "female"])
def test_moved_cards_carry_before_after_numbers_and_no_card_name_is_a_raw_id(which):
    if not have(which):
        pytest.skip("Q206 page not built here")
    d, stem, _ = PAGES[which]
    man, _ = P.load_page(d, stem)
    r = json.loads((REPO / "data" / "derived" / f"Q206_ship_diff_{which}.json").read_text())
    E = {m["id"]: m for m in man["meshes"]}
    for i in r["geometry_changed"]:
        b = (E[i].get("rec") or {}).get("procedural_badge") or ""
        assert " Q206:" in b and "Before -> after" in b, i
    assert not [m["id"] for m in man["meshes"] if m["name"] == m["id"]]


def test_female_clinical_files_are_the_q205_ones_unchanged():
    d = PAGES["female"][0]
    src = PAGES["female"][2]
    if not d.exists():
        pytest.skip("Q206 female page not built here")
    for f in src.glob("clinical_*"):
        assert (d / f.name).read_bytes() == f.read_bytes()
