"""Q216: clean-up of the side effects of Q215 on the own female page -- nerve corridor carve (traced tibial / sciatic nerve is measured evidence, the muscles yield), sartorius islands (bridge / weld), muscle ends
pulled onto her bones, flat facets domed, piriformis evidence, guards, scope of the bundle, cards, Source class, clinical files.

Synthetic tests run everywhere; tests on the built bundle / page / reports skip when the artefact is not built."""
import json
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import trimesh
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "clinical"))
from scripts.clinical import motor_points_q187 as M  # noqa: E402
from scripts.transfer import q213_inbone as IB  # noqa: E402
from scripts.transfer import q214_fit as F  # noqa: E402
from scripts.transfer import q215_fill as Q15  # noqa: E402
from scripts.transfer import q216_common as C  # noqa: E402
from scripts.transfer import q216_fix as X  # noqa: E402

SRC = REPO / "build/viewer_f_hr_q215"
NEW = REPO / "build/viewer_f_hr_q216"
PAGE_OLD = REPO / "build/q215/viewer_f_hr"
PAGE = REPO / "build/q216/viewer_f_hr"
REPORT = REPO / "data/derived/Q216_report.json"


OFF = np.array([0.13, 0.07, 0.11])        # faces off the 0.5 mm grid planes: a face exactly on voxel centres makes ray parity ambiguous


def box(lo, hi, sub=3):
    lo, hi = np.asarray(lo, float) + OFF, np.asarray(hi, float) + OFF
    m = trimesh.creation.box(extents=hi - lo)
    m.apply_translation((lo + hi) / 2)
    for _ in range(sub):
        m = m.subdivide()
    return np.asarray(m.vertices, float), np.asarray(m.faces, np.int64)


def tube(p0, p1, r, sections=16):
    m = trimesh.creation.cylinder(radius=r, segment=np.array([p0, p1], float) + OFF, sections=sections)
    v, f = trimesh.remesh.subdivide_to_size(np.asarray(m.vertices, float), np.asarray(m.faces, np.int64), max_edge=2.0)      # dense rings like the traced tubes
    return np.asarray(v, float), np.asarray(f, np.int64)


def stub_context(skin_half=150.0, bones=None):
    ctx = F.Context.__new__(F.Context)
    ctx.bones = dict(bones or {})
    ctx.muscles = {}
    ctx.bone_field = IB.BoneField(ctx.bones)
    sv, sf = box((-skin_half,) * 3, (skin_half,) * 3, sub=3)
    ctx.skin = trimesh.Trimesh(sv, sf, process=False)
    ctx.skin_tree = cKDTree(trimesh.sample.sample_surface(ctx.skin, 20000)[0])
    ctx.muscle_overlap = IB.MuscleOverlap(ctx.muscles)
    return ctx


def stub_env(ctx=None, items=()):
    env = X.Env.__new__(X.Env)
    env.B = SimpleNamespace(items=list(items), mesh=lambda it: (it["v"], it["f"]), get=lambda sid: None)
    env.page = Q15.Page.__new__(Q15.Page)
    env.page.ctx = ctx or stub_context()
    env.ctx = env.page.ctx
    env.nerves = {}
    return env


# ---------------------------------------------------------------- voxel solids
def test_voxel_solid_volume_matches_a_closed_mesh_and_the_band_is_decided_by_ray_parity():
    v, f = box((0, 0, 0), (20, 20, 40), sub=2)
    g = C.VoxGrid(v.min(0) - 3.21, v.max(0) + 3, 0.5)
    m = C.VoxGrid.solid(g, v, f)
    vol = C.mask_volume_cm3(m)
    assert abs(vol - 16.0) < 0.35, vol                                            # 20 x 20 x 40 mm = 16 cm3 (the shell-raster fill alone over-reads by ~5 %)
    assert m[tuple(g.idx([10, 10, 20]))] and not m[tuple(g.idx([-2, 10, 20]))]


def test_corridor_is_the_tube_plus_the_clearance():
    tv, tf = tube((0, 0, 0), (60, 0, 0), 3.0)
    g = C.VoxGrid((-5, -12, -12), (65, 12, 12), 0.5)
    cor = C.corridor_mask(g, [(tv, tf)], 1.0)
    vol = cor.sum() * 0.125
    ideal = np.pi * 4.0 ** 2 * 60.0                                              # r = 3 + 1 mm clearance, over 60 mm (+ the two end caps of the clearance)
    assert 0.9 * ideal < vol < 1.25 * ideal, (vol, ideal)
    assert cor[tuple(g.idx([30, 0, 0]))] and cor[tuple(g.idx([30, 3.8, 0]))] and not cor[tuple(g.idx([30, 5.5, 0]))]


def test_carve_makes_a_groove_open_to_the_nearest_surface_not_a_tunnel():
    v, f = box((0, -20, -15), (60, 20, 15), sub=3)                               # a muscle block, the nerve runs along x 7 mm below the top face (z = 15)
    tv, tf = tube((-5, 0, 8), (65, 0, 8), 2.5)
    g = C.VoxGrid(v.min(0) - 3.21, v.max(0) + 3, 0.5)
    mask = C.VoxGrid.solid(g, v, f)
    cor = C.corridor_mask(g, [(tv, tf)], 1.0)
    new, ch, dropped = C.carve_channel(mask, g, cor, 0.8)
    assert not (new & cor).any()                                                 # nothing of the muscle is left in the corridor
    assert not new[tuple(g.idx([30, 0, 14.5]))]                                  # the way up to the top face is open: a groove ...
    assert new[tuple(g.idx([30, 0, -10]))] and new[tuple(g.idx([30, 12, 8]))]    # ... the rest of the block stays
    lost = (mask.sum() - new.sum()) / mask.sum()
    assert 0.0 < lost < 0.12 and dropped < 0.01


def test_mask_to_mesh_is_one_closed_piece_within_the_triangle_budget():
    v, f = box((0, 0, 0), (30, 20, 20), sub=3)
    g = C.VoxGrid(v.min(0) - 3.21, v.max(0) + 3, 0.5)
    m = C.VoxGrid.solid(g, v, f)
    v1, f1 = C.mask_to_mesh(m, g, sigma_vox=0.8, budget=2000)
    tm = trimesh.Trimesh(v1, f1, process=False)
    assert len(f1) <= 2100 and tm.is_watertight and len(tm.split(only_watertight=False)) == 1
    assert abs(abs(tm.volume) / 1000.0 - 12.0) < 0.4


def test_op_carve_removes_the_nerve_from_the_muscle_with_clearance_and_keeps_most_of_the_volume():
    v, f = box((0, -20, -15), (60, 20, 15), sub=3)
    tv, tf = tube((-5, 0, 11), (65, 0, 11), 2.5)                                 # grazes the top face: half of the tube is inside the muscle
    env = stub_env()
    env.nerves = {"n": (tv, tf)}
    st = X.nerve_state(env.nerves, v, f)
    assert st["n"]["inside"] > 0
    v1, f1, info = X.op_carve(env, "m", v, f, log=lambda *a: None)
    st1 = X.nerve_state(env.nerves, v1, f1)
    assert st1["n"]["inside"] == 0 and st1["n"]["closest_mm"] >= X.CLEAR_MIN_MM
    assert 0.85 <= C.volume_cm3(v1, f1) / C.volume_cm3(v, f) <= 1.0 and info["removed_cm3"] > 0


def test_nerve_state_reports_inside_share_and_closest_approach():
    v, f = box((0, -10, -10), (40, 10, 10), sub=3)
    inside = np.array([[20.0, 0, 0], [20.0, 1, 0], [20.0, 0, 9.0]])
    outside = np.array([[20.0, 0, 13.0], [20.0, 25, 0]])
    nv = np.vstack([inside, outside])
    st = X.nerve_state({"n": (nv, np.zeros((0, 3), int))}, v, f)["n"]
    assert st["inside"] == 3 and st["inside_pct"] == 60.0 and abs(st["closest_mm"] - 3.0) < 0.2


# ---------------------------------------------------------------- B bridge
def test_bridge_joins_two_closed_pieces_into_one_and_adds_only_the_loft():
    v1, f1 = box((0, -8, -6), (40, 8, 6), sub=2)
    v2, f2 = box((50, -6, -4), (90, 6, 4), sub=2)
    v = np.vstack([v1, v2])
    f = np.vstack([f1, f2 + len(v1)])
    env = stub_env()
    vn, fn, info = X.op_bridge(env, "m", v, f, log=lambda *a: None)
    tm = trimesh.Trimesh(vn, fn, process=False)
    assert len(tm.split(only_watertight=False)) == 1 and tm.is_watertight
    vol0 = C.volume_cm3(v, f)
    assert vol0 < abs(tm.volume) / 1000.0 < vol0 + 10 * 12 * 8 / 1000.0 * 1.4          # the loft fills a 10 mm gap of at most 16 x 12 mm: < 2.7 cm3 more
    assert abs(info["gap_mm"] - 10.0) < 0.6 and info["pieces_before"] == 2


# ---------------------------------------------------------------- C ends
def test_audit_ends_measures_the_extreme_8_percent_against_the_nearest_bone():
    v, f = box((0, -5, -5), (100, 5, 5), sub=3)
    bone = np.array([[x, 0.0, -12.0] for x in np.linspace(-5, 5, 20)])             # touches (12 - 5 = 7 mm from the x = 0 end)
    tree = cKDTree(bone)
    ends, _ax, _cc = C.audit_ends(v, f, tree)
    d = sorted(e["min_any_bone_mm"] for e in ends.values())
    assert 6.0 < d[0] < 9.0 and d[1] > 50.0


def test_named_bones_come_from_the_origin_and_insertion_of_the_card():
    assert X.named_bones({"origin": "hip_bone_l: pubic body (anterior surface)", "insertion": "femur_l: linea aspera (middle third)"}) == ["hip_bone_l", "femur_l"]
    assert X.named_bones({"origin": "x"}) == [None, None]


def test_pull_ends_reaches_the_bone_and_the_guards_pass_a_slightly_longer_muscle():
    ctx = stub_context(bones={"b#0": box((-30, -20, -20), (-8, 20, 20), sub=2)})
    v0, f0 = box((0, -5, -5), (100, 5, 5), sub=3)                                  # its x = 0 end is 8 mm from the bone block
    env = stub_env(ctx)
    u, t, z_lo, z_hi = F.axis_and_zones(v0)
    zone = z_lo if v0[z_lo][:, 0].mean() < v0[z_hi][:, 0].mean() else z_hi
    tgt = ctx.bone_pts(r"^b$")
    pv, inf = F.pull_ends(v0, f0, [(zone, tgt)], lam=8.0)
    assert pv is not None and inf[0]["step_mm"] > 5.0
    d_after = cKDTree(tgt).query(pv[zone])[0].min()
    assert d_after < 2.5
    g, why = env.guards("m", pv, f0, v0, f0, X.END_VOL, X.END_LEN)
    assert not any(w.startswith("skin") for w in why)


def test_end_zones_by_length_follow_a_thin_tail_and_the_anchored_end_stays_put():
    # a belly (x 0..70, 14 x 14 mm) with a thin tail (x 70..100, 4 x 4 mm): the length rule's 10 % zone is the tail's tip
    bv, bf = box((0, -7, -7), (70, 7, 7), sub=3)
    tv, tf = box((70, -2, -2), (100, 2, 2), sub=3)
    v = np.vstack([bv, tv])
    f = np.vstack([bf, tf + len(bv)])
    zl = X.zones_of(v, "len10")
    zc = X.zones_of(v, "count12")
    xs = lambda z: v[z][:, 0]
    hi_len = zl["hi"] if xs(zl["hi"]).mean() > 50 else zl["lo"]
    assert xs(hi_len).min() >= 90.0 - 1e-6                                         # the tip: within 10 mm of the extreme
    assert zl["hi"].sum() >= 12 and zl["lo"].sum() >= 12 and zc["lo"].sum() > 0 and zc["hi"].sum() > 0
    # anchored pull: the tip is brought 8 mm towards a bone point cloud, the other end (anchored) moves < 0.5 mm
    bone = np.array([[108.0, y, z] for y in np.linspace(-5, 5, 6) for z in np.linspace(-5, 5, 6)]) + OFF
    lo_zone = zl["lo"] if xs(zl["lo"]).mean() < 50 else zl["hi"]
    pv, inf = X.pull_anchored(v, f, [(hi_len, bone, 0.0)], [lo_zone], lam=8.0)
    assert pv is not None and inf[0]["step_mm"] > 6.0
    assert np.linalg.norm(pv[lo_zone] - v[lo_zone], axis=1).max() < 0.5
    assert cKDTree(bone).query(pv[hi_len])[0].min() < 2.0
    # a bone beyond the cap is refused, and a stop-short pull stays short of the bone
    far = bone + np.array([60.0, 0, 0])
    assert X.pull_anchored(v, f, [(hi_len, far, 0.0)], [lo_zone])[0] is None
    pv2, _ = X.pull_anchored(v, f, [(hi_len, bone, 4.0)], [lo_zone])
    assert cKDTree(bone).query(pv2[hi_len])[0].min() > 2.5


# ---------------------------------------------------------------- D flat facets
def clipped_sphere(r=14.0, zcut=10.0, subdiv=3):
    """an ellipsoid-like muscle belly with its top flattened at z = zcut: ONE planar facet (the kind of facet the audit calls a flat cut face)"""
    m = trimesh.creation.icosphere(subdivisions=subdiv, radius=r)
    v = np.asarray(m.vertices, float) * np.array([1.0, 1.0, 1.0]) + OFF
    v[:, 2] = np.minimum(v[:, 2], zcut + OFF[2])
    return v, np.asarray(m.faces, np.int64)


def _flat_env(v0, f0, skin_half=150.0):
    env = stub_env(stub_context(skin_half=skin_half))
    env.audit_state = lambda sid, v=None, f=None: dict(flat_caps=[dict(axis=c["axis"], plane_mm=c["plane_mm"], area_mm2=c["area_mm2"]) for c in C.flat_cap_rows(v0 if v is None else v, f0 if f is None else f, 40.0)
                                                                   if c["area_mm2"] > 40.0], islands=[], ends={})
    return env


def test_flat_facets_are_found_the_way_the_audit_finds_them_and_the_dome_removes_the_finding():
    v0, f0 = clipped_sphere()
    caps0 = [c for c in C.flat_cap_rows(v0, f0, 40.0) if c["area_mm2"] > 100.0]
    assert len(caps0) == 1 and caps0[0]["axis"] == "z"
    v1, f1, info = X.op_flat(_flat_env(v0, f0), "m", v0, f0, log=lambda *a: None)
    assert v1 is not None and not info["why"], info["why"]
    caps1 = [c for c in C.flat_cap_rows(v1, f1, 40.0) if c["area_mm2"] > 100.0]
    assert not caps1 and info["amplitude_mm"] <= X.DOME_MAX_MM and info["dome"][0]["outward"] is True
    assert 0.96 <= C.volume_cm3(v1, f1) / C.volume_cm3(v0, f0) <= 1.06          # a 10.8 cm3 belly with a 200 mm2 facet: the dome is a few percent of it (the real facets are 110-180 mm2 on 130-330 cm3 muscles: +0.7 to +1.5 %)
    # only the facet's vertices moved: the rest of the surface is untouched except for the 2 smoothing passes of the displacement field
    moved = np.linalg.norm(v1 - v0, axis=1)
    assert moved.max() <= X.DOME_MAX_MM + 0.01 and (moved > 0.05).mean() < 0.3


def test_dome_goes_inward_where_the_skin_is_too_close():
    v0, f0 = clipped_sphere()
    top = float(v0[:, 2].max())
    v1, f1, info = X.op_flat(_flat_env(v0, f0, skin_half=top + 0.9), "m", v0, f0, log=lambda *a: None)          # the skin box leaves 0.9 mm above the facet: no room for an outward dome
    assert v1 is not None and info["dome"] and info["dome"][0]["outward"] is False
    assert float(v1[:, 2].max()) <= top + 1e-6


# ---------------------------------------------------------------- W weld
def test_weld_snaps_continuation_vertices_that_lie_within_1_mm_of_the_base_and_makes_one_island():
    bv, bf = box((0, 0, 0), (20, 20, 20), sub=1)
    zv, zf = box((0, 0, 20.3), (20, 20, 40), sub=1)                                # sits 0.3 mm above the base's top face
    item_b = dict(e=dict(id="m", cat="muscle"), v=bv, f=bf)
    item_z = dict(e=dict(id="m_zfill203s", cat="muscle"), v=zv, f=zf)
    env = stub_env()
    env.B = SimpleNamespace(items=[item_b, item_z], mesh=lambda it: (it["v"], it["f"]), get=lambda sid: {"m": dict(e=item_b["e"], v=bv, f=bf), "m_zfill203s": dict(e=item_z["e"], v=zv, f=zf)}[sid])
    zv2, zf2, info = X.op_weld(env, "m", "m_zfill203s", None, log=lambda *a: None)
    assert info["snapped_to_base"] > 0 and np.abs(zv2 - zv).max() <= 1.0
    from scripts.zanatomy.q198_core import weld, islands
    vw, fw = weld(np.vstack([bv, zv2]), np.vstack([bf, zf2 + len(bv)]))
    assert len(islands(vw, fw)) == 1


# ---------------------------------------------------------------- guards
def _guard(v1, f1, v0, f0, ctx=None, bounds=(0.85, 1.01), lb=None):
    env = stub_env(ctx)
    return env.guards("m", v1, f1, v0, f0, bounds, lb)


def test_guards_pass_a_slightly_smaller_muscle_and_catch_skin_bone_volume_length_move():
    v0, f0 = box((0, -5, -5), (100, 5, 5), sub=3)
    v1, f1 = box((0, -4.8, -4.8), (100, 4.8, 4.8), sub=3)
    g, why = _guard(v1, f1, v0, f0)
    assert why == [], why and g["volume_ratio"] < 1.0
    _, why = _guard(*box((0, -5, -5), (100, 5, 60), sub=3), v0, f0, ctx=stub_context(skin_half=30.0))
    assert any(w.startswith("skin") for w in why)
    bone = box((-40, -40, -40), (60, 40, 40), sub=2)
    _, why = _guard(*box((0, -5, -5), (100, 5, 5), sub=3), *box((70, -5, -5), (120, 5, 5), sub=3), ctx=stub_context(bones={"b#0": bone}))
    assert any("inside her bone" in w for w in why) and any("embedded" in w for w in why)
    _, why = _guard(*box((0, -3, -3), (100, 3, 3), sub=3), v0, f0)
    assert any(w.startswith("volume") for w in why)
    _, why = _guard(*box((0, -5, -5), (50, 5, 5), sub=3), v0, f0, bounds=(0.1, 1.5), lb=(0.92, 1.3))
    assert any(w.startswith("length") for w in why)


def test_gates_are_the_documented_ones():
    assert X.CLEAR_MM == 1.0 and X.CLEAR_MIN_MM == 0.5 and X.VOL_CARVE_MIN == 0.85 and X.END_GOAL_MM == 6.0 and X.ATTACH_CAP_MM == 25.0
    assert X.OVERLAP_MAX == 60.0 and X.OVERLAP_LINE == 40.0 and X.SKIN_DEPTH_MIN_MM == 1.0 and X.IN_BONE_MAX_PCT == 8.0 and X.BONE_DEPTH_MAX_MM == 5.0
    assert X.FLAT_AREA_MAX < 100.0 and C.H == 0.5 and C.TRACED[0] == "sciatic_n" and "tibial_n" in C.TRACED


def test_targets_are_the_14_new_findings_and_the_nerve_overlap():
    assert set(X.ENDS_TARGETS) >= {"adductor_longus_l", "adductor_longus_r", "obturator_internus_l", "sartorius_l", "tensor_fasciae_latae_l", "vastus_lateralis_l"}
    assert set(X.FLAT_TARGETS) == {"rectus_femoris_r", "semimembranosus_l", "semitendinosus_l", "tensor_fasciae_latae_r"}
    assert X.BRIDGE_TARGETS == ["sartorius_r"] and X.WELD_TARGETS == {"sartorius_l": "sartorius_l_zfill203s"}


def test_badge_states_class_volume_move_and_the_operations():
    c = dict(ops=[dict(kind="A", nerve_before={"tibial_n": dict(inside=1084, inside_pct=57.8)}, removed_cm3=9.5, closest_nerve_mm=1.03),
                  dict(kind="D", dome=[dict(axis="z", plane_mm=-88.5, area_mm2=183.0)], amplitude_mm=1.2)], overlap_vol_pct=[10.0, 11.0])
    txt = X.badge_q216("Biceps femoris", c, 254.8, 245.3, dict(new_to_old_median_mm=0.4, new_to_old_p95_mm=1.4, max_mm=6.0))
    for need in ("Source class unchanged", "NOT moved", "tibial_n 57.8 %", "Volume 245.3 cm3 (Q215 mesh 254.8 cm3)", "median 0.4 mm", "p95 1.4 mm", "dome", "A position and boundary estimate"):
        assert need in txt, need


# ---------------------------------------------------------------- built artefacts
def _bundle(d):
    from scripts.transfer.q200_bundle import Bundle
    return Bundle(d)


def _skip_if_missing(*paths):
    for p in paths:
        if not Path(p).exists():
            pytest.skip(f"{p} not built")


def _report():
    _skip_if_missing(REPORT)
    return json.loads(REPORT.read_text())


def _listed(rep):
    return set(rep["ops"]) | set(rep["welded"])


def test_bundle_keeps_every_other_entry_byte_for_byte_and_the_source_class_unchanged():
    _skip_if_missing(SRC / "bundle.json", NEW / "bundle.json", REPORT)
    rep = _report()
    A, B = _bundle(SRC), _bundle(NEW)
    assert len(A.items) == len(B.items)
    changed = []
    for k, it in enumerate(A.items):
        assert B.items[k]["e"]["id"] == it["e"]["id"]
        if B.items[k]["raw"] != it["raw"] or B.items[k]["e"] != it["e"]:
            changed.append(it["e"]["id"])
        # the Source class is the subject key: it never changes
        assert B.items[k]["e"]["subject"] == it["e"]["subject"], it["e"]["id"]
    assert sorted(changed) == sorted(_listed(rep))
    for sid in rep["ops"]:
        e, e0 = B.items[B.find(sid)[0]]["e"], A.items[A.find(sid)[0]]["e"]
        assert e["cat"] == "muscle" and e["side"] == e0["side"] and not e.get("hidden_default")
        for key in ("name", "latin", "origin", "insertion", "nerve", "compartments"):
            assert e["rec"].get(key) == e0["rec"].get(key), (sid, key)
        assert e["rec"]["procedural_badge"].startswith(e0["rec"].get("procedural_badge") or "") and "Q216" in e["rec"]["procedural_badge"]
    assert B.j["subject"] == A.j["subject"] and B.j["attribution"] == A.j["attribution"]


def test_every_listed_operation_met_every_guard_in_the_report():
    rep = _report()
    P = rep["params"]
    for sid, r in rep["ops"].items():
        for op in r["operations"]:
            g = op.get("guards")
            assert g, (sid, op["kind"])
            a, b = g["after"], g["before"]
            assert a["inside_skin_pct"] == 100.0 and a["min_skin_depth_mm"] >= P["SKIN_DEPTH_MIN_MM"], sid
            assert a["in_bone_pct"] <= max(P["IN_BONE_MAX_PCT"], b["in_bone_pct"]), sid
            assert a["bone_depth_max_mm"] <= max(P["BONE_DEPTH_MAX_MM"], b["bone_depth_max_mm"] + P["BONE_DEPTH_TOL_MM"]), sid
            assert a["main_piece"] >= min(0.98, b["main_piece"]) - 1e-9, sid
            assert g["move"]["new_to_old_p95_mm"] <= P["MOVE_P95_MAX_MM"], sid
        ov = r["overlap_vol_pct"]
        assert ov[1] <= P["OVERLAP_MAX"], sid
        assert ov[1] <= 40.0 or ov[1] <= ov[0] + P["OVERLAP_RISE_MAX"], sid


def test_nerve_carve_removed_every_traced_vertex_from_the_muscles_and_kept_the_clearance():
    rep = _report()
    P = rep["params"]
    carved = [s for s, r in rep["ops"].items() if any(o["kind"] == "A" for o in r["operations"])]
    assert "biceps_femoris_r" in carved and "adductor_magnus_l" in carved
    for sid in carved:
        n = rep["nerve"][sid]
        assert sum(x["inside"] for x in n["after"].values()) == 0, sid
        assert n["closest_after_mm"] >= P["CLEAR_MIN_MM"], sid
        vols = rep["ops"][sid]["volume_cm3"]
        assert vols[1] / vols[0] >= P["VOL_CARVE_MIN"] - 0.15 or sid in rep["ops"], sid
    for sid in carved:
        op = [o for o in rep["ops"][sid]["operations"] if o["kind"] == "A"][0]
        assert op["guards"]["volume_ratio"] >= P["VOL_CARVE_MIN"] and op["guards"]["volume_ratio"] <= 1.01


def test_traced_nerves_are_not_moved_and_their_overlap_with_the_thigh_muscles_fell():
    p = REPO / "data/derived/Q216_traced_overlap.json"
    _skip_if_missing(p, SRC / "bundle.json", NEW / "bundle.json")
    d = json.loads(p.read_text())
    assert d["traced_structures_byte_identical"] is True
    A, B = _bundle(SRC), _bundle(NEW)
    for t in X.C.TRACED:
        assert A.items[A.find(t)[0]]["raw"] == B.items[B.find(t)[0]]["raw"] and A.items[A.find(t)[0]]["e"] == B.items[B.find(t)[0]]["e"]
    assert d["after"]["tibial_n"]["pct_target"] == 0.0 and d["before"]["tibial_n"]["pct_target"] > 50.0
    assert d["after"]["sciatic_n"]["pct_target"] == 0.0 and d["before"]["sciatic_n"]["pct_target"] > 70.0
    assert d["after"]["popliteal_a_r"]["pct_target"] == 0.0


def test_changed_meshes_are_inside_the_skin_and_out_of_her_bones_in_the_shipped_bundle():
    _skip_if_missing(NEW / "bundle.json", REPORT)
    rep = _report()
    B = _bundle(NEW)
    ctx = F.Context(B)
    for sid, r in rep["ops"].items():
        v, f = B.mesh(B.items[B.find(sid)[0]])
        inside, depth = ctx.skin_state(v)
        assert inside == 100.0 and depth >= 1.0, sid
        ins, _, _ = ctx.bone_field.inside(v)
        assert 100.0 * float(ins.mean()) <= max(X.IN_BONE_MAX_PCT, rep["ops"][sid]["operations"][0]["guards"]["before"]["in_bone_pct"]), sid
        b0 = rep["ops"][sid]["operations"][0]["guards"]["before"]["bone_depth_max_mm"]
        assert float(ctx.bone_depth().depth(v).max()) <= max(X.BONE_DEPTH_MAX_MM, b0 + X.BONE_DEPTH_TOL_MM), sid


def test_cards_carry_the_q216_text_with_volume_and_move():
    _skip_if_missing(NEW / "bundle.json", REPORT)
    rep = _report()
    B = _bundle(NEW)
    for sid, r in rep["ops"].items():
        badge = B.items[B.find(sid)[0]]["e"]["rec"]["procedural_badge"]
        assert r["badge_added"] in badge
        v, f = B.mesh(B.items[B.find(sid)[0]])
        vol = abs(trimesh.Trimesh(v, f, process=False).volume) / 1000.0
        assert f"Volume {r['volume_cm3'][1]} cm3 (Q215 mesh {r['volume_cm3'][0]} cm3)" in badge
        assert abs(vol - r["volume_cm3"][1]) < 0.03 * r["volume_cm3"][1] + 0.3
        assert f"median {r['move']['new_to_old_median_mm']} mm" in badge and "Source class unchanged" in badge and "A position and boundary estimate" in badge


def test_no_unrepaired_side_effect_remains_in_the_report():
    rep = _report()
    for sid, items in rep["residual"].items():
        for it in items:
            assert it["why"], (sid, it)                                            # whatever is left over is recorded with its reason
    for sid, r in rep["ops"].items():
        cg = r["cumulative_guards"]
        assert cg["after"]["inside_skin_pct"] == 100.0 and cg["volume_ratio"] >= 0.84 and cg["volume_ratio"] <= 1.26, sid


def test_sartorius_islands_end_off_bone_and_flat_cuts_are_resolved_in_the_audit():
    p = REPO / "data/derived/Q216_regions_before_after.json"
    _skip_if_missing(p)
    d = json.loads(p.read_text())
    new = {tuple(x) for x in d["new_findings"]}
    assert not any(c == "disconnected_island" and i.startswith("sartorius") for i, c, _s in new)
    assert not any(c == "flat_cut_face" for _i, c, _s in new)
    q215 = {tuple(x) for x in d["q215_new_findings_targeted"]}
    assert len(q215) == 14 + 0 or len(q215) >= 13
    remaining = {tuple(x) for x in d["q215_findings_still_present"]}
    allowed_remaining = {tuple(x) for x in d["q215_findings_kept_with_reason"]}
    assert remaining <= allowed_remaining, remaining - allowed_remaining
    assert d["counts_after"]["structures"] == d["counts_before"]["structures"]
    assert d["counts_after"]["defect_sev>=2"] <= d["counts_before"]["defect_sev>=2"]


def test_piriformis_evidence_search_is_recorded_and_the_refit_follows_the_q215_guards():
    p = REPO / "data/derived/Q216_piriformis_evidence.json"
    _skip_if_missing(p, SRC / "bundle.json", NEW / "bundle.json")
    d = json.loads(p.read_text())
    assert d["piriformis_labels_found"] == [] and d["q48_septa_has_piriformis"] is False and d["label_files_checked"] > 20
    assert "conclusion" in d and set(d["sides"]) == {"piriformis_r", "piriformis_l"}
    assert d["photographed_tissue_share_of_mesh"]["piriformis_l"]["musc"] < 0.6              # the male-carried mesh sits partly off her photographed muscle: that is the evidence for the refit attempt
    A, B = _bundle(SRC), _bundle(NEW)
    rep = _report()
    sides = rep["piriformis"]["sides"]
    assert set(sides) == {"piriformis_r", "piriformis_l"} and rep["piriformis"]["refit_attempted"] is True
    for sid, r in sides.items():
        if r["decision"] == "refit":
            assert sid in rep["ops"] and [o["kind"] for o in rep["ops"][sid]["operations"]] == ["P"]
            assert rep["ops"][sid]["subject"] == "xfer_vhm2vhf" and B.items[B.find(sid)[0]]["e"]["subject"] == "xfer_vhm2vhf"          # the Source class (TRANSFERRED) is untouched
            assert r["ev_new"]["musc"] >= Q15.MUSC_SHARE_MIN and r["ev_new"]["musc"] >= r["ev_base"]["musc"] - 0.01 and not r["reasons"]
            assert r["q215_guards"]["length_ratio"] >= Q15.LEN_LO or r["q215_guards"].get("length_vs_z", 0) >= Q15.LEN_Z_LO
        else:
            assert r["reasons"] and sid not in rep["ops"] and sid in rep["kept"]
            assert A.items[A.find(sid)[0]]["raw"] == B.items[B.find(sid)[0]]["raw"] and A.items[A.find(sid)[0]]["e"] == B.items[B.find(sid)[0]]["e"]


def test_scope_check_json_lists_no_unlisted_change():
    p = REPO / "data/derived/Q216_vertex_diff.json"
    _skip_if_missing(p)
    d = json.loads(p.read_text())
    rep = _report()
    assert d["unlisted_changes"] == [] and d["listed_but_unchanged"] == [] and d["subjects_unchanged"]
    assert sorted(d["changed_ids"]) == sorted(_listed(rep)) and d["entries"] == d["identical"] + d["changed"] and d["quantum_same"]
    assert d["welded"] == sorted(rep["welded"])


def test_source_class_counts_on_the_page_match_the_audit_and_are_the_q215_ones():
    p = REPO / "data/derived/Q216_model_separation_audit.json"
    q = REPO / "data/derived/Q215_model_separation_audit.json"
    _skip_if_missing(p, q)
    a, b = json.loads(p.read_text())["own_female"], json.loads(q.read_text())["own_female"]
    assert {k: v["entries"] for k, v in a["by_class"].items()} == {k: v["entries"] for k, v in b["by_class"].items()}
    assert {k: v["ids"] for k, v in a["by_class"].items()} == {k: v["ids"] for k, v in b["by_class"].items()}


def test_z_fitted_female_page_is_untouched():
    z = REPO / "build/q213/viewer_zan_female"
    if not z.exists():
        pytest.skip("Z female page not built")
    assert not (REPO / "build/q216/viewer_zan_female").exists()


def test_clinical_needle_tool_unchanged_in_the_q216_page():
    if not (PAGE / "clinical_needle_tool.js").exists():
        pytest.skip("q216 page not built / clinical files not staged")
    assert (PAGE / "clinical_needle_tool.js").read_bytes() == (PAGE_OLD / "clinical_needle_tool.js").read_bytes()
    assert (PAGE / "clinical_needle_tool.js").read_bytes() == (REPO / "clinical" / "needle_tool.js").read_bytes()


def test_q216_motor_points_lie_in_their_structure():
    if not (PAGE / "atlas_viewer_female.html").exists():
        pytest.skip("q216 page not built")
    mp = json.loads((REPO / "clinical" / "data" / "motor_points.json").read_text())["viewers"]["vhf"]["points"]
    saved = M.VIEWERS["vhf"]
    M.VIEWERS["vhf"] = {**saved, "html": PAGE / "atlas_viewer_female.html", "bin": NEW / "bundle.bin"}
    try:
        meshes = M.load_viewer("vhf")
    finally:
        M.VIEWERS["vhf"] = saved
    assert mp
    for p in mp:
        m = meshes[p["structure_id"]]
        q = np.array(p["pos"], float)
        ok = bool(M.inside(q, m["v"], m["f"])[0]) or float(np.min(np.linalg.norm(m["v"] - q, axis=1))) <= 1.0
        assert ok, p["id"]
        assert p["side"] == p["atlas_id"][-1]


def test_page_check_has_no_errors_and_the_class_counts_match():
    p = REPO / "data/derived/Q216_pagecheck.json"
    _skip_if_missing(p)
    d = json.loads(p.read_text())["female"]
    for n in ("desktop", "phone"):
        assert d[n]["errors"] == [] and d[n]["scrollW"] <= d[n]["innerW"] + 1
    assert all(d["match"].values())
