"""Q214: the muscles the OWN pages still lacked (splenius capitis / cervicis, fibularis brevis, flexor pollicis brevis): transfer-fit guards, scope of the Q214 bundles, badges and clinical files.

Synthetic tests run everywhere; tests on the built bundles / pages / reports skip when the artefact is not built.  The clinical-file guards compare ONLY clinical_needle_tool.js (the motor-point
file is regenerated for the Q214 pages: points of the new muscles lie in their structure)."""
import json
import re
import sys
from pathlib import Path

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
from scripts.transfer import q214_targets as T  # noqa: E402

BUNDLES = {"vhm": (REPO / "build/viewer_m_hr_q212", REPO / "build/viewer_m_hr_q214"), "vhf": (REPO / "build/viewer_f_hr_q213", REPO / "build/viewer_f_hr_q214")}
PAGES = {"vhm": (REPO / "build/q212/viewer_m_hr", REPO / "build/q214/viewer_m_hr", "atlas_viewer_male.html"),
         "vhf": (REPO / "build/q213/viewer_f_hr", REPO / "build/q214/viewer_f_hr", "atlas_viewer_female.html")}
WANT = {"splenius_capitis": "rl", "splenius_cervicis": "rl", "fibularis_brevis": "rl", "flexor_pollicis_brevis": "r"}


def sheet(lo, hi, sub=3):
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    m = trimesh.creation.box(extents=hi - lo)
    m.apply_translation((lo + hi) / 2)
    for _ in range(sub):
        m = m.subdivide()
    return np.asarray(m.vertices, float), np.asarray(m.faces, np.int64)


def plate(x, half=12.0, n=25):
    """a point cloud of a flat bone surface at x"""
    g = np.linspace(-half, half, n)
    yy, zz = np.meshgrid(g, g)
    return np.column_stack([np.full(yy.size, float(x)), yy.ravel(), zz.ravel()])


def stub_context(skin_half=60.0, neighbours=None):
    """a Context without a bundle: no bones, a box skin, the given neighbouring muscles {id: (v, f)}"""
    ctx = F.Context.__new__(F.Context)
    ctx.bones, ctx.muscles = {}, dict(neighbours or {})
    ctx.bone_field = IB.BoneField({})
    sv, sf = sheet((-skin_half,) * 3, (skin_half + 100.0, skin_half, skin_half), sub=3)
    ctx.skin = trimesh.Trimesh(sv, sf, process=False)
    ctx.skin_tree = cKDTree(trimesh.sample.sample_surface(ctx.skin, 20000)[0])
    ctx.muscle_overlap = IB.MuscleOverlap(ctx.muscles)
    return ctx


# ---------------------------------------------------------------- the pull of the attachments
def test_pull_ends_lands_the_end_zones_on_the_bones_and_keeps_the_belly():
    v, f = sheet((0, -5, -5), (100, 5, 5))
    u, t, zlo, zhi = F.axis_and_zones(v)
    a, b = plate(-10.0), plate(112.0)
    za, zb = F.assign_targets(v, zlo, zhi, a, b)
    assert float(v[za][:, 0].mean()) < 20 < 80 < float(v[zb][:, 0].mean())
    nv, info = F.pull_ends(v, f, [(za, a), (zb, b)])
    assert nv is not None and not any(i.get("refused") for i in info)
    assert F.zone_dist(nv, za, a) < 1.5 and F.zone_dist(nv, zb, b) < 1.5
    mid = (v[:, 0] > 40) & (v[:, 0] < 60)
    assert np.linalg.norm(nv[mid] - v[mid], axis=1).mean() < 3.0           # the belly follows, it is not dragged by the full pull
    assert F.VOL_LO < IB.volume(nv, f) / IB.volume(v, f) < F.VOL_HI           # the muscle is stretched 100 -> ~120 mm by the two pulls: its volume follows within the guard bounds


def test_pull_ends_refuses_an_end_that_is_too_far_from_its_bone():
    v, f = sheet((0, -5, -5), (100, 5, 5))
    u, t, zlo, zhi = F.axis_and_zones(v)
    a, b = plate(-10.0), plate(112.0 + F.ATTACH_CAP_MM + 5.0)
    za, zb = F.assign_targets(v, zlo, zhi, a, b)
    nv, info = F.pull_ends(v, f, [(za, a), (zb, b)])
    assert nv is None and any(i.get("refused") for i in info)


def test_assign_targets_orients_the_ends_by_the_smaller_total_distance():
    v, f = sheet((0, -5, -5), (100, 5, 5))
    u, t, zlo, zhi = F.axis_and_zones(v)
    near_hi, near_lo = plate(105.0), plate(-5.0)
    za, zb = F.assign_targets(v, zlo, zhi, near_hi, near_lo)       # "origin" bone is at the x = 105 end
    assert float(v[za][:, 0].mean()) > 80 and float(v[zb][:, 0].mean()) < 20


# ---------------------------------------------------------------- the guards
def evaluate(ctx, v0, v1, f, a, b):
    u, t, zlo, zhi = F.axis_and_zones(v0)
    za, zb = F.assign_targets(v0, zlo, zhi, a, b)
    return F.evaluate(v0, v1, f, ctx, za, zb, a, b, F.length_mm(v0, zlo, zhi), IB.volume(v0, f), ())


def test_evaluate_passes_a_clean_muscle_and_refuses_each_guard_violation():
    v0, f = sheet((0, -5, -5), (100, 5, 5))
    a, b = plate(-1.0), plate(101.0)
    ctx = stub_context()
    ok = evaluate(ctx, v0, v0.copy(), f, a, b)
    assert ok["why_not"] == [], ok["why_not"]
    assert ok["guards"]["volume_ratio"] == 1.0 and ok["guards"]["inside_skin_pct"] == 100.0 and ok["guards"]["overlap_vol_pct"] == 0.0
    # volume: a muscle fattened x1.6 in two directions (x2.6 volume)
    fat = v0 * np.array([1.0, 1.6, 1.6])
    assert any("volume" in w for w in evaluate(ctx, v0, fat, f, a, b)["why_not"])
    # length: stretched to 1.4 x
    long = v0 * np.array([1.4, 1.0, 1.0])
    assert any("length" in w for w in evaluate(ctx, v0, long, f, a, b)["why_not"])
    # skin: pushed through the skin surface (box skin spans y -60..60)
    out = v0 + np.array([0.0, 58.0, 0.0])
    why = evaluate(ctx, v0, out, f, a, b)["why_not"]
    assert any("skin" in w for w in why), why
    # end off its bone
    off = v0 + np.array([0.0, 0.0, 30.0])
    assert any("from its bone" in w for w in evaluate(ctx, v0, off, f, a, b)["why_not"])
    # move: a rigid shift of 8 mm along the belly is a mean move above the gate
    sh = v0 + np.array([0.0, 8.0, 0.0])
    assert any("move" in w for w in evaluate(ctx, v0, sh, f, a, b)["why_not"])


def test_overlap_gate_is_the_volume_share_inside_other_muscles():
    v0, f = sheet((0, -5, -5), (100, 5, 5))
    a, b = plate(-1.0), plate(101.0)
    nv, nf = sheet((-10, -20, -20), (110, 20, 20), sub=2)                     # a neighbour that contains the whole muscle
    ctx = stub_context(neighbours={"nb#0": (nv, nf)})
    r = evaluate(ctx, v0, v0.copy(), f, a, b)
    assert r["guards"]["overlap_vol_pct"] > F.OVERLAP_MAX and any("neighbouring muscles" in w for w in r["why_not"])
    far, ff = sheet((0, 30, -5), (100, 40, 5), sub=2)
    ctx2 = stub_context(neighbours={"nb#0": (far, ff)})
    assert evaluate(ctx2, v0, v0.copy(), f, a, b)["guards"]["overlap_vol_pct"] == 0.0
    half, fh = sheet((0, 0, -5), (100, 5, 5), sub=2)                           # half of the muscle's volume inside a neighbour
    ctx3 = stub_context(neighbours={"nb#0": (half, fh)})
    pct = F.OverlapField(ctx3).pct(v0, f)
    assert 35.0 < pct < 70.0, pct
    ctx4 = stub_context(neighbours={"nb#0": (v0, f)})                           # skip_ids: the muscle's own id does not count against it
    assert F.OverlapField(ctx4, skip_ids=("nb",)).pct(v0, f) == 0.0 and F.OverlapField(ctx4).pct(v0, f) == 100.0


def test_overlap_harm_names_the_neighbours_a_new_muscle_pushes_over_the_line():
    nb, nf = sheet((0, 0, -5), (100, 20, 5), sub=2)
    ctx = stub_context(neighbours={"nb#0": (nb, nf)})
    of = ctx.overlap_field()
    v0, f = sheet((0, -4, -4), (100, 6, 4))                      # overlaps the neighbour by ~60 % of its own volume, the neighbour by ~25 % of its
    harm = of.harm(v0, f)
    assert harm and harm[0][0] == "nb" and harm[0][2] > harm[0][1] == 0.0
    far, ff = sheet((0, 60, -5), (100, 70, 5), sub=2)
    assert of.harm(far, ff) == []
    # a Z-fill continuation piece counts with its muscle: the overlap between the two pieces of one muscle is not an overlap of two muscles
    ctx2 = stub_context(neighbours={"mus#0": sheet((0, 0, -5), (60, 10, 5), sub=2), "mus_zfill212#1": sheet((50, 0, -5), (100, 10, 5), sub=2)})
    assert (ctx2.overlap_field().cnt > 1).sum() == 0


def test_shallow_bone_clamp_brings_an_embedded_end_back_to_the_clamp_depth():
    bone_v, bone_f = sheet((-30, -30, -30), (0, 30, 30), sub=2)               # a bone block, surface at x = 0
    ctx = stub_context()
    ctx.bone_field = IB.BoneField({"b#0": (bone_v, bone_f)})
    ctx.bones = {"b#0": (bone_v, bone_f)}
    v, f = sheet((-12, -4, -4), (60, 4, 4), sub=3)                              # a muscle whose end is buried 12 mm in the bone
    bd = ctx.bone_depth()
    assert bd.depth(v).max() > 8.0
    cur = F.shallow_bone_clamp(v, f, ctx, v)
    assert bd.depth(cur).max() <= F.BONE_CLAMP_MM + 1.0                         # on the Q204 lattice (2 mm voxels): back to the clamp depth
    assert F.BONE_DEPTH_MAX_MM > F.BONE_CLAMP_MM
    assert np.linalg.norm(cur[v[:, 0] > 30] - v[v[:, 0] > 30], axis=1).max() < 8.0       # the free end is not carried along rigidly (a rigid shift would move it by the whole ~12 mm)


def test_skin_inset_brings_vertices_back_under_the_skin():
    ctx = stub_context(skin_half=30.0)
    v = np.array([[0.0, 0.0, 0.0], [0.0, 29.5, 0.0], [0.0, 45.0, 0.0]])        # inside, 0.5 mm under the skin, outside
    w = ctx.skin_inset(v)
    assert np.allclose(w[0], v[0])
    ins, depth = ctx.skin_state(w)
    assert ins == 100.0 and depth >= F.SKIN_DEPTH_MIN_MM


def test_vertebra_levels_and_landmark_sets():
    ctx = stub_context()
    for i, y in enumerate((540, 560, 580, 600)):            # four "cervical" pieces, C1 = topmost
        v, f = sheet((-15, y - 8, -40), (15, y + 8, 0), sub=1)
        ctx.bones[f"cervical_vertebrae#{i}"] = (v, f)
    lv = F.vertebra_pieces(ctx, "cervical_vertebrae")
    assert [l for l, _ in lv] == [1, 2, 3, 4] and lv[0][1][:, 1].mean() > lv[-1][1][:, 1].mean()
    sp = F.spinous_pts(ctx, "cervical_vertebrae", 4, 4)
    assert len(sp) and sp[:, 2].max() <= -40 + 18.0 + 1e-6 and 520 < sp[:, 1].mean() < 560           # the posterior part of the 4th (lowest) piece
    tp = F.transverse_pts(ctx, "cervical_vertebrae", 1, 3, "r")
    assert len(tp) and (tp[:, 0] > 0).all()


def test_gates_are_the_documented_ones():
    assert (F.OVERLAP_MAX, F.OVERLAP_NOTE_MAX) == (60.0, 40.0)                # Q198 / Q204 muscle_overlap_pct severity-2 / severity-1 lines
    assert F.OVERLAP_MAX == 60.0 and F.VOL_LO == 0.75 and F.VOL_HI == 1.30 and F.LEN_LO == 0.85 and F.LEN_HI == 1.20
    assert F.BELLY_IN_BONE_MAX == 5.0 and F.SKIN_DEPTH_MIN_MM == 1.0 and F.ATTACH_CAP_MM == 25.0 and F.BONE_DEPTH_MAX_MM == 5.0 and F.FLIP_MAX_PCT == 1.0


def test_target_table_covers_the_task():
    assert T.WANT == WANT
    assert T.z_id("splenius_cervicis", "r") == "zan_splenius_colli_muscle_r" and T.z_id("splenius_capitis", "l") == "splenius_capitis_l"
    assert set(T.LANDMARK_TEXT) == set(WANT)


# ---------------------------------------------------------------- built artefacts
def _bundle(d):
    from scripts.transfer.q200_bundle import Bundle
    return Bundle(d)


def _skip_if_missing(*paths):
    for p in paths:
        if not Path(p).exists():
            pytest.skip(f"{p} not built")


def _report(body):
    p = REPO / f"data/derived/Q214_{body}_report.json"
    _skip_if_missing(p)
    return json.loads(p.read_text())


@pytest.mark.parametrize("body", ["vhm", "vhf"])
def test_every_wanted_muscle_is_added_or_skipped_with_a_reason_and_absence_was_verified(body):
    rep = _report(body)
    for stem, sides in WANT.items():
        for s in sides:
            nid = f"{stem}_{s}"
            ab = rep["absence"][nid]
            assert ab["on_bundle"] is False and ab["z_present"] is True and nid not in ab["bundle_ids_with_stem"]
            src = BUNDLES[body][0] / "bundle.json"
            if src.exists():                                                  # re-verified against the source bundle's own manifest
                ids = {e["id"] for e in json.loads(src.read_text())["structures"]}
                assert nid not in ids
                assert sorted(i for i in ids if i.startswith(stem)) == ab["bundle_ids_with_stem"]
            assert (nid in rep["added"]) != (nid in rep["skipped"]), nid
            if nid in rep["skipped"]:
                why = rep["skipped"][nid]
                assert why and (isinstance(why, str) or why["why_not"]), nid
    assert len(rep["added"]) + len(rep["skipped"]) == sum(len(v) for v in WANT.values())


@pytest.mark.parametrize("body", ["vhm", "vhf"])
def test_added_muscles_met_every_guard(body):
    rep = _report(body)
    for nid, r in rep["added"].items():
        g = r["guards"]
        assert r["why_not"] == [], nid
        assert g["belly_in_bone_pct"] <= F.BELLY_IN_BONE_MAX and g["in_bone_pct"] <= F.ALL_IN_BONE_MAX, nid
        assert g["overlap_vol_pct"] <= F.OVERLAP_MAX, nid
        assert g["inside_skin_pct"] == 100.0 and g["min_skin_depth_mm"] >= F.SKIN_DEPTH_MIN_MM, nid
        assert F.VOL_LO <= g["volume_ratio"] <= F.VOL_HI and F.LEN_LO <= g["length_ratio"] <= F.LEN_HI, nid
        assert g["flipped_pct"] <= F.FLIP_MAX_PCT and max(g["end_dist_mm"]) <= F.END_DIST_MAX_MM, nid
        assert g["mean_move_mm"] <= F.MEAN_MOVE_MAX and g["max_move_mm"] <= F.MAX_MOVE_MAX, nid
    for nid, why in rep["skipped"].items():
        if isinstance(why, dict):
            assert why["why_not"], nid


@pytest.mark.parametrize("body", ["vhm", "vhf"])
def test_bundle_keeps_every_source_entry_byte_for_byte_and_only_adds_the_reported_muscles(body):
    a, b = BUNDLES[body]
    _skip_if_missing(a / "bundle.json", b / "bundle.json", REPO / f"data/derived/Q214_{body}_report.json")
    rep = _report(body)
    A, B = _bundle(a), _bundle(b)
    n0 = len(A.items)
    assert len(B.items) == n0 + len(rep["added"])
    for k, it in enumerate(A.items):
        assert B.items[k]["raw"] == it["raw"] and B.items[k]["e"] == it["e"], it["e"]["id"]
    assert sorted(it["e"]["id"] for it in B.items[n0:]) == sorted(rep["added"])
    assert (b / "bundle.bin").read_bytes()[: len((a / "bundle.bin").read_bytes())] == (a / "bundle.bin").read_bytes()
    subject = T.BODY[body]["subject"]
    for it in B.items[n0:]:
        e = it["e"]
        assert e["cat"] == "muscle" and e["subject"] == subject and e["side"] in ("right", "left")
        badge = e["rec"]["procedural_badge"]
        r = rep["added"][e["id"]]
        for need in ("Z-Anatomy", "Z-fill", "Q214 validation median error", "Volume", "Not measured on", "position estimate", "gate"):
            assert need in badge, (e["id"], need)
        assert f"{r['guards']['volume_cm3']} cm3" in badge
        assert e["rec"].get("origin") and e["rec"].get("insertion") and e["rec"]["name"]
        v, f = B.mesh(it)
        assert len(v) > 100 and f.max() < len(v)
        assert abs(abs(trimesh.Trimesh(v, f, process=False).volume) / 1000.0 - r["guards"]["volume_cm3"]) < 0.05 * r["guards"]["volume_cm3"] + 0.2    # the shipped (quantised) mesh has the reported volume


def test_scope_check_json_lists_no_unlisted_change():
    p = REPO / "data/derived/Q214_vertex_diff.json"
    _skip_if_missing(p)
    d = json.loads(p.read_text())
    for body in ("vhm", "vhf"):
        x = d[body]
        assert x["unlisted_changes"] == [] and x["bin_prefix_identical"] and x["added_equals_report"] and x["identical"] == x["entries_source"]
        assert x["quantum_same"] and x["entries_new"] == x["entries_source"] + len(x["added"])


def test_new_subjects_are_described_and_classed_filled_from_z():
    txt = (REPO / "viewer" / "atlas_viewer.template.html").read_text(encoding="utf-8")
    from scripts import audit_q189_model_separation as AU
    for sub, who in (("xfer_zan2vhm_q214", "him"), ("xfer_zan2vhf_q214", "her")):
        m = re.search(r"^\s{2}%s:\s*\"(.*)\",?$" % sub, txt, re.M)
        assert m and "FILLED from Z-Anatomy" in m.group(1) and f"not measured on {who}" in m.group(1)
        assert AU.classify(sub, "Z-Anatomy ...")[0] == "filled_zan"


@pytest.mark.parametrize("body", ["vhm", "vhf"])
def test_clinical_needle_tool_unchanged_in_the_q214_pages(body):
    ref, page, _ = PAGES[body]
    if not (page / "clinical_needle_tool.js").exists():
        pytest.skip("q214 page not built / clinical files not staged")
    assert (page / "clinical_needle_tool.js").read_bytes() == (ref / "clinical_needle_tool.js").read_bytes()
    assert (page / "clinical_needle_tool.js").read_bytes() == (REPO / "clinical" / "needle_tool.js").read_bytes()


@pytest.mark.parametrize("body", ["vhm", "vhf"])
def test_q214_motor_points_lie_in_their_structure_and_cover_the_added_muscles(body):
    ref, page, html = PAGES[body]
    bundle = BUNDLES[body][1]
    if not (page / html).exists():
        pytest.skip("q214 page not built")
    q215 = (REPO / "build/q215/viewer_f_hr", REPO / "build/viewer_f_hr_q215")
    if body == "vhf" and (q215[0] / html).exists() and q215[1].exists():     # Q215: the own female motor points are regenerated on the Q215 page (hip / thigh target muscles re-bounded)
        page, bundle = q215
    mp = json.loads((REPO / "clinical" / "data" / "motor_points.json").read_text())["viewers"][body]["points"]
    saved = M.VIEWERS[body]
    M.VIEWERS[body] = {**saved, "html": page / html, "bin": bundle / "bundle.bin"}
    try:
        meshes = M.load_viewer(body)
    finally:
        M.VIEWERS[body] = saved
    assert mp
    for p in mp:
        m = meshes[p["structure_id"]]
        q = np.array(p["pos"], float)
        ok = bool(M.inside(q, m["v"], m["f"])[0]) or float(np.min(np.linalg.norm(m["v"] - q, axis=1))) <= 1.0
        assert ok, (body, p["id"])
        assert p["side"] == p["atlas_id"][-1]
    rep = _report(body)
    placed = {p["structure_id"] for p in mp}
    cov = json.loads((REPO / "data/derived/Q187_motor_points_coverage.json").read_text())["viewers"][body]
    for nid in rep["added"]:
        stem = re.sub(r"_(r|l)$", "", nid)
        if any(r["muscle"] == stem for r in M.RULES):
            assert nid in placed, nid                                        # the rule of the added muscle is placed on it
            assert not any(nid in x["rule"] for x in cov["not_placed"]), nid
    for nid in rep["skipped"]:
        stem = re.sub(r"_(r|l)$", "", nid)
        if any(r["muscle"] == stem for r in M.RULES):
            assert any(x["rule"].startswith(nid) and "no structure" in x["why"] for x in cov["not_placed"]), nid     # a muscle that was not added stays 'not placed' (never forced)


def test_her_cryosection_splenius_compartment_was_checked_against_the_same_guards_and_recorded():
    rep = _report("vhf")
    for s in "rl":
        oe = rep["own_evidence"][f"splenius_capitis_{s}"]
        assert oe["accepted"] is False and oe["why_not"]
        g = oe["guards"]
        assert g["volume_ratio"] > F.VOL_HI or g["length_ratio"] < F.LEN_LO                 # 1.35-1.59 x the Z pair, cut flat at the T1 body top
    assert rep["own_evidence"]["splenius_cervicis_r"]["accepted"] is False
    own = json.loads((REPO / "data/derived/Q214_splenius_own.json").read_text())
    for s in "rl":
        x = own[f"splenius_{s}"]
        assert x["watertight"] and 60 < x["voxel_volume_cm3"] < 85 and x["y_range_mm"][0] > 585
        assert x["z_fit_vertices_outside_her_compartment_pct"]["z_capitis"] > 90
    for nid, r in rep["added"].items():
        if nid.startswith("splenius"):
            assert "Cross-check with her own cryosection splenius compartment" in r["badge"] and "her_cryo_compartment" in r


def test_skip_evidence_numbers_support_the_reasons():
    p = REPO / "data/derived/Q214_skip_evidence.json"
    _skip_if_missing(p)
    d = json.loads(p.read_text())
    for body in ("vhm", "vhf"):
        for s in "rl":
            x = d[body][f"fibularis_{s}"]
            assert x["own_over_z_longus_plus_brevis"] > 1.0                          # the existing lateral mesh is already larger than the two Z muscles together
    th = d["vhm"]["thumb_r"]
    assert th["has_first_metacarpal_entry"] is False and th["z_first_metacarpal_to_own_metacarpal_mesh_median_mm"]["median"] > 25.0      # his hand skeleton has no thumb
    assert d["vhf"]["thumb_r"]["has_first_metacarpal_entry"] is True and d["vhf"]["thumb_r"]["z_thumb_proximal_phalanx_to_own_phalanges_mesh_mm"]["median"] > 5.0
