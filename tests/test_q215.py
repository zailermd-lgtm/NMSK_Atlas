"""Q215: the male-carried HIP / THIGH target muscles of the own female page re-bounded on her own evidence (her femur-registered cryosections + her bones / own muscles), guards, scope of the bundle,
badges, Source class, clinical files.

Synthetic tests run everywhere; tests on the built bundle / page / reports skip when the artefact is not built.  The Z-fitted female page is separate and must not change; the clinical-file guards compare
ONLY clinical_needle_tool.js (the motor-point file is regenerated for the Q215 page: points of the replaced muscles lie in their structure)."""
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
from scripts.transfer import q215_fill as Fi  # noqa: E402
from scripts.transfer import q215_refit as RF  # noqa: E402
from scripts.transfer import q215_common as C  # noqa: E402
from scripts.cryo import vhf_thigh_refit_q181 as R  # noqa: E402

SRC = REPO / "build/viewer_f_hr_q214"
NEW = REPO / "build/viewer_f_hr_q215"
PAGE_OLD = REPO / "build/q214/viewer_f_hr"
PAGE = REPO / "build/q215/viewer_f_hr"
REPORT = REPO / "data/derived/Q215_report.json"
SUBJECT = "xfer_vhm2vhf_sep_q215"


def sheet(lo, hi, sub=3):
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    m = trimesh.creation.box(extents=hi - lo)
    m.apply_translation((lo + hi) / 2)
    for _ in range(sub):
        m = m.subdivide()
    return np.asarray(m.vertices, float), np.asarray(m.faces, np.int64)


def stub_context(skin_half=150.0, bones=None):
    """a Context without a bundle: the given bones {id: (v, f)}, a box skin, no neighbouring muscles"""
    ctx = F.Context.__new__(F.Context)
    ctx.bones = dict(bones or {})
    ctx.muscles = {}
    ctx.bone_field = IB.BoneField(ctx.bones)
    sv, sf = sheet((-skin_half,) * 3, (skin_half,) * 3, sub=3)
    ctx.skin = trimesh.Trimesh(sv, sf, process=False)
    ctx.skin_tree = cKDTree(trimesh.sample.sample_surface(ctx.skin, 20000)[0])
    ctx.muscle_overlap = IB.MuscleOverlap(ctx.muscles)
    return ctx


def stub_page(ctx):
    p = Fi.Page.__new__(Fi.Page)
    p.ctx = ctx
    return p


EVB = dict(voxels=1000, musc=0.55, non_muscle=0.45, unknown=0.0)
EVN = dict(voxels=900, musc=0.80, non_muscle=0.20, unknown=0.0)


def bpts_of(v):
    return v.copy()


# ---------------------------------------------------------------- the refit helpers
A_TEST = np.array([[-1.0, 0, 0, 350.0], [0, -1.0, 0, 240.0], [0, 0, 1.0, -100.0], [0, 0, 0, 1.0]])


def test_solid_masks_fill_a_closed_muscle_and_a_bone_shell_with_a_pin_hole_in_index_space():
    # a closed 20 mm cube and the same cube with ONE triangle missing (an open CT bone shell has such holes); the index of an atlas point is
    # ((x + ox - 350) / -1, (z + oz - 240) / -1, y + oy + 100)
    ox, oy, oz = R.ORIGIN
    cx, cy, cz = 350.0 - ox - 100.0, 150.0 - oy, 240.0 - oz - 100.0
    v, f = sheet((cx - 10, cy - 10, cz - 10), (cx + 10, cy + 10, cz + 10), sub=4)
    closed = trimesh.Trimesh(v, f, process=False)
    holed = trimesh.Trimesh(v.copy(), f[1:], process=False)                          # one 1.25 mm triangle missing
    B, Cm = RF.solid_masks((700, 480, 810), A_TEST, [("shell", holed)], [("cube", closed)])
    assert 6500 < int(Cm.sum()) < 9500                                    # 20 x 20 x 20 voxels (1 mm) = 8000
    assert 6000 < int(B.sum()) < 9500                                     # the holed shell is filled too (a per-level section raster as in Q181 leaves open shells empty)
    ii = np.argwhere(Cm)
    assert (ii.max(0) - ii.min(0)).max() <= 22


def test_bridge_gaps_fills_an_interior_empty_run_only():
    out = np.zeros((20, 20, 30), np.uint8)
    for k in list(range(2, 8)) + list(range(13, 20)):
        out[5:12, 5:12, k] = 7
    out[:, :, 10] = 0
    done = RF.bridge_gaps(out, [7], np.zeros(out.shape, bool))
    assert done == {7: [(8, 12)]}
    for k in range(8, 13):
        assert (out[:, :, k] == 7).sum() > 20                              # bridged between its two bounding sections
    assert (out[:, :, 0] == 7).sum() == 0 and (out[:, :, 25] == 7).sum() == 0     # the ends are not extended


def test_bridge_gaps_never_enters_forbidden_voxels():
    out = np.zeros((20, 20, 30), np.uint8)
    for k in list(range(2, 8)) + list(range(13, 20)):
        out[5:12, 5:12, k] = 7
    forbid = np.zeros(out.shape, bool)
    forbid[:, :, 9:12] = True
    RF.bridge_gaps(out, [7], forbid)
    assert (out[:, :, 10][forbid[:, :, 10]] == 7).sum() == 0


def test_level_step_removes_bone_own_muscle_and_far_non_muscle_but_keeps_near_muscle_and_held(monkeypatch):
    L0 = np.zeros((30, 30), np.uint8)
    res_in = np.zeros((30, 30), np.uint8)
    res_in[2:28, 2:28] = 3                                  # target label 3
    res_in[2:6, 2:6] = 9                                    # a held label 9 in one corner
    monkeypatch.setattr(RF, "_orig_level", lambda *a, **k: res_in.copy())
    B = np.zeros((30, 30), bool); B[10:14, 10:14] = True    # bone
    Cmu = np.zeros((30, 30), bool); Cmu[20:24, 20:24] = True    # her own muscle
    mus = np.ones((30, 30), np.uint8)                       # 1 = photographed non-muscle everywhere ...
    mus[8:16, 18:28] = 2                                    # ... except a muscle strip
    res = RF._level_no_bone(L0, L0, (None, None), mus, B, Cmu, 8, {9})
    assert (res[B] == 3).sum() == 0 and (res[Cmu] == 3).sum() == 0
    assert (res[8:16, 18:28] == 3).sum() > 40                         # on photographed muscle: kept
    assert (res[2:6, 2:6] == 9).all()                                  # a held label is never touched
    assert res[26, 3] == 0                                            # photographed non-muscle > NEAR_MM from muscle: removed
    near = res[8:16, 16:18]                                          # within NEAR_MM of muscle: kept
    assert (near == 3).sum() > 0


def test_seam_blend_keeps_the_old_end_section_at_the_seam_and_the_refit_below_the_band():
    ids = R.label_ids()
    aid = "adductor_brevis_l"
    l = ids[aid]
    base = np.zeros((40, 40, 120), np.uint8)
    out = np.zeros_like(base)
    base[5:20, 5:20, 10:81] = l                              # the old muscle, flat cut at k = 80
    out[9:24, 9:24, 10:81] = l                               # the re-fitted one is 4 voxels off
    A = np.array([[-1.0, 0, 0, 350.0], [0, -1.0, 0, 240.0], [0, 0, 1.0, 0.0], [0, 0, 0, 1.0]])
    ys = 80 + A[2, 3] - R.ORIGIN[1]
    refit_slice = (out[:, :, 55] == l).copy()
    done = RF.seam_blend(out, base, {aid: ys}, np.zeros(base.shape, bool), A, band_mm=20)
    assert done[aid][0] == 80 and done[aid][1] == 60
    assert np.array_equal(out[:, :, 80] == l, base[:, :, 80] == l)       # the old section at the seam (the continuation stays welded)
    assert np.array_equal(out[:, :, 55] == l, refit_slice)               # below the band: the re-fit untouched
    mid = out[:, :, 70] == l
    assert mid.any() and mid.sum() > 100                                  # a morph in between
    assert (base[:, :, 70] == l).sum() > 0 and not np.array_equal(mid, base[:, :, 70] == l)


def test_evidence_shares_count_photographed_muscle_fat_and_unknown(tmp_path):
    ks = [3, 4]
    for side, (i0, i1) in R.SIDE_I.items():
        mus = np.zeros((2, i1 - i0, 480), np.uint8)
        mus[:, 10:20, 10:20] = 2
        mus[:, 20:30, 10:20] = 1
        (tmp_path / f"p1_{side}.json").write_text(json.dumps({"ks": ks, "i0": i0, "i1": i1}))
        np.save(tmp_path / f"p1_{side}_mus.npy", mus)
    D = np.zeros((700, 480, 810), np.uint8)
    D[10:20, 10:20, 3:5] = 5                              # on muscle
    D[20:30, 10:20, 3:5] = 5                              # on photographed non-muscle
    D[30:40, 10:20, 3:5] = 5                              # unknown (mus == 0)
    sh = Fi.Evidence(tmp_path).shares(D, {"x_r": 5})["x_r"]
    assert sh["voxels"] == 3 * 100 * 2
    assert abs(sh["musc"] - 1 / 3) < 1e-3 and abs(sh["non_muscle"] - 1 / 3) < 1e-3 and abs(sh["unknown"] - 1 / 3) < 1e-3


# ---------------------------------------------------------------- the guards
def _cand(lo, hi, sub=3):
    return sheet(lo, hi, sub)


def _eval(v1, f1, v0, f0, ctx=None, evb=EVB, evn=EVN, zref=None, zfm=None, zlen=None):
    ctx = ctx or stub_context()
    return Fi.evaluate(stub_page(ctx), "x_r", v1, f1, v0, f0, bpts_of(v1), evb, evn, zref, zfm or [], zlen)


def test_a_good_candidate_passes_every_individual_guard():
    v0, f0 = _cand((0, -5, -5), (100, 5, 5))
    v1, f1 = _cand((0, -4, -4), (100, 4, 4))                                   # 0.64 of the volume, same length, inside the skin, no bone
    g, why = _eval(v1, f1, v0, f0, zref=6.0, zlen=100.0)
    assert why == [], why
    assert g["fit_error_vs_label"]["median_mm"] < 0.1 and g["length_ratio"] > 0.99 and 0.6 < g["volume_ratio"] < 0.7


def test_skin_guard():
    v0, f0 = _cand((0, -5, -5), (100, 5, 5))
    v1, f1 = _cand((0, -5, -5), (100, 5, 60))                                  # reaches z = 60, a skin box of half-width 30 ends before it
    g, why = _eval(v1, f1, v0, f0, ctx=stub_context(skin_half=30.0))
    assert any(w.startswith("skin") for w in why)


def test_bone_guard():
    bone = sheet((-40, -40, -40), (60, 40, 40), sub=2)
    ctx = stub_context(bones={"b#0": bone})
    v0, f0 = _cand((70, -5, -5), (120, 5, 5))
    v1, f1 = _cand((0, -5, -5), (100, 5, 5))                                   # half of it inside the bone block
    g, why = _eval(v1, f1, v0, f0, ctx=ctx)
    assert any("inside her bone" in w for w in why) and any("embedded" in w for w in why)


def test_photographed_muscle_share_guards():
    v0, f0 = _cand((0, -5, -5), (100, 5, 5))
    v1, f1 = _cand((0, -4, -4), (100, 4, 4))
    g, why = _eval(v1, f1, v0, f0, evn=dict(EVN, musc=0.30, non_muscle=0.7))
    assert any("lies on her photographed muscle" in w for w in why)
    g, why = _eval(v1, f1, v0, f0, evb=dict(EVB, musc=0.80), evn=dict(EVN, musc=0.60))
    assert any("share fell" in w for w in why)


def test_evidence_volume_guard_blocks_a_loss_of_photographed_muscle_but_not_a_gain():
    v0, f0 = _cand((0, -5, -5), (100, 5, 5))
    v1, f1 = _cand((0, -3, -3), (100, 3, 3))                                  # 0.36 of the volume
    g, why = _eval(v1, f1, v0, f0, evb=dict(EVB, musc=0.70), evn=dict(EVN, musc=0.75))
    assert any("photographed-muscle volume" in w for w in why) or any("volume x" in w for w in why)
    big1, bigf1 = _cand((0, -6, -6), (100, 6, 6))
    g, why = _eval(big1, bigf1, v0, f0, evb=dict(EVB, musc=0.20), evn=dict(EVN, musc=0.80))
    assert g["evidence_volume_ratio"] > 4 and not any("photographed-muscle volume" in w for w in why)      # a gain (the old mesh lay 10 mm off her muscle) is not a reason to refuse


def test_collapse_guard():
    v0, f0 = _cand((0, -8, -8), (100, 8, 8))
    v1, f1 = _cand((0, -3, -3), (100, 3, 3))                                  # 0.14 of the volume
    g, why = _eval(v1, f1, v0, f0, evb=dict(EVB, musc=0.2), evn=dict(EVN, musc=0.9))
    assert any("volume x" in w and "gate >=" in w for w in why)


def test_length_guard_with_and_without_the_z_reference():
    v0, f0 = _cand((0, -5, -5), (100, 5, 5))
    v1, f1 = _cand((0, -5, -5), (60, 5, 5))                                   # 0.6 of the length
    g, why = _eval(v1, f1, v0, f0)
    assert any(w.startswith("length") for w in why)
    g, why = _eval(v1, f1, v0, f0, zlen=80.0)                                 # 0.75 of the Z reference length -> allowed (the old mesh is known to be wrong)
    assert not any(w.startswith("length") for w in why)
    g, why = _eval(v1, f1, v0, f0, zlen=150.0)
    assert any(w.startswith("length") for w in why)


def test_main_piece_guard_and_move_guard():
    v0, f0 = _cand((0, -5, -5), (100, 5, 5))
    a, fa = _cand((0, -5, -5), (40, 5, 5))
    b, fb = _cand((60, -5, -5), (100, 5, 5))
    v1, f1 = np.vstack([a, b]), np.vstack([fa, fb + len(a)])
    g, why = _eval(v1, f1, v0, f0)
    assert any("main piece" in w for w in why)
    v2, f2 = _cand((0, 28, -5), (100, 38, 5))                                  # 33 mm away from the old mesh
    g, why = _eval(v2, f2, v0, f0)
    assert any("from the old mesh" in w and "mm" in w for w in why)


def test_z_reference_volume_gate():
    v0, f0 = _cand((0, -5, -5), (100, 5, 5))
    v1, f1 = _cand((0, -5, -5), (100, 5, 5))
    g, why = _eval(v1, f1, v0, f0, zref=0.2)                                  # x50 of the reference
    assert any("Z-Anatomy female reference" in w for w in why)
    g, why = _eval(v1, f1, v0, f0, zref=g["after"]["volume_cm3"] * 1.5)
    assert not any("Z-Anatomy female reference" in w for w in why)


def test_seam_guard_for_a_zfill_continuation():
    v0, f0 = _cand((0, -5, -5), (100, 5, 5))
    zv, zf = _cand((100, -5, -5), (120, 5, 5), sub=2)                          # the continuation touches the old end face at x = 100
    ok1, okf1 = _cand((0, -5, -5), (100, 5, 5))
    g, why = _eval(ok1, okf1, v0, f0, zfm=[(zv, zf)])
    assert not any("Z-fill continuation" in w for w in why) and g["seam_gap_mm"]["p95"] < 1.0
    far, farf = _cand((0, -5, -5), (88, 5, 5))                                 # the new end face stopped 12 mm short
    g, why = _eval(far, farf, v0, f0, zfm=[(zv, zf)])
    assert any("Z-fill continuation" in w for w in why)


def test_gates_are_the_documented_ones():
    assert (Fi.OVERLAP_MAX, Fi.OVERLAP_NOTE) == (60.0, 40.0)
    assert Fi.SKIN_DEPTH_MIN_MM == 1.0 and Fi.IN_BONE_MAX_PCT == 8.0 and Fi.BONE_DEPTH_MAX_MM == 5.0
    assert Fi.MUSC_SHARE_MIN == 0.45 and Fi.EVID_LO == 0.60 and Fi.COLLAPSE_MIN == 0.25 and Fi.LEN_LO == 0.75 and Fi.LEN_Z_LO == 0.60
    assert Fi.MOVE_P95_MAX_MM == 25.0 and Fi.SEAM_MAX_MM == 2.5 and Fi.MAIN_PIECE_MIN == 0.98 and Fi.SQUEEZE_MIN == 0.80 and Fi.BUDGET == 9000
    assert Fi.SUBJECT == SUBJECT and RF.MIN_PIECE_FRAC == 0.15 and RF.NEAR_MM == 2


def test_target_table_is_the_male_carried_hip_thigh_set():
    assert set(C.HIP_THIGH) == {"obturator_internus", "piriformis", "adductor_brevis", "adductor_longus", "adductor_magnus", "gracilis", "sartorius", "tensor_fasciae_latae",
                                "rectus_femoris", "vastus_lateralis", "vastus_medialis", "vastus_intermedius", "biceps_femoris", "semitendinosus", "semimembranosus"}
    t = RF.target_ids()
    assert len(t) == 28 and "piriformis_r" not in t and all(x[-2:] in ("_r", "_l") for x in t)         # piriformis is not in the Q48 septa volume
    q213 = json.loads((REPO / "data/derived/Q213_target_muscle_audit.json").read_text())
    for s in C.HIP_THIGH:
        for x in "rl":
            assert q213[f"{s}_{x}"]["own_cls"] == "transferred"                   # all of them were the male's (Q213)


def test_severity_ranks_the_scale_mismatch_and_the_leaky_muscle_first():
    q213 = {"a_r": dict(vol_cm3=dict(vhf=140.0, vhm=150.0, zan_f=25.0), own_q204=dict(overlap_pct=20.0, inside_bone_pct=2.0)),
            "b_r": dict(vol_cm3=dict(vhf=100.0, vhm=170.0, zan_f=95.0), own_q204=dict(overlap_pct=5.0, inside_bone_pct=0.0))}
    rows = Fi.severity_rows(None, {"a_r": dict(musc=0.3), "b_r": dict(musc=0.7)}, ["a_r", "b_r"], q213)
    assert rows["a_r"]["score"] > rows["b_r"]["score"] and rows["a_r"]["scale_vs_male"] == round(140 / 150, 2)


def test_badge_states_class_volume_error_and_guards():
    c = dict(guards=dict(before=dict(volume_cm3=140.0, in_bone_pct=7.0), after=dict(volume_cm3=60.0, in_bone_pct=0.0), volume_ratio=0.43, length_ratio=0.9, fit_error_vs_label=dict(median_mm=0.5, p95_mm=1.0, max_mm=1.4),
                        move=dict(median_mm=3.0, p95_mm=9.0, max_mm=20.0), overlap_vol_pct=[20.0, 15.0], z_ref_cm3=25.0, volume_vs_z=2.4), ev=[dict(musc=0.27, non_muscle=0.7), dict(musc=0.62, non_muscle=0.38)],
             bridged_y_mm=[[-131.0, -127.0]])
    b = Fi.badge("Obturator internus", "obturator_internus_r", c, dict(vol_male=112.8, scale_vs_male=1.28))
    for need in ("TRANSFERRED", "Q215", "Volume 60.0 cm3", "previous mesh 140.0 cm3", "Fit error", "median 0.5 mm", "0.27 -> 0.62", "Guards passed", "not measured", "bridged", "112.8"):
        assert need in b, need


def test_new_subject_is_described_and_classed_transferred():
    txt = (REPO / "viewer" / "atlas_viewer.template.html").read_text(encoding="utf-8")
    from scripts import audit_q189_model_separation as AU
    m = re.search(r"^\s{2}%s:\s*\"(.*)\",?$" % SUBJECT, txt, re.M)
    assert m and m.group(1).startswith("TRANSFERRED from the Visible Human male, not measured on her") and "registered" in m.group(1)
    assert AU.classify(SUBJECT, "...")[0] == "transferred"
    assert AU.classify("xfer_vhm2vhf_sep", "...")[0] == "transferred"


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


def test_every_target_is_replaced_or_kept_with_a_reason():
    rep = _report()
    assert set(rep["replaced"]) | set(rep["kept"]) == set(rep["targets"]) and not (set(rep["replaced"]) & set(rep["kept"]))
    assert len(rep["replaced"]) <= 26                                              # "up to ~25 muscle-sides this round"
    for aid, k in rep["kept"].items():
        assert k["why_not"], aid
    assert "piriformis_r" in rep["piriformis"]


def test_replaced_muscles_met_every_guard():
    rep = _report()
    P = rep["params"]
    for aid, r in rep["replaced"].items():
        g = r["guards"]
        a, b = g["after"], g["before"]
        assert a["inside_skin_pct"] == 100.0 and a["min_skin_depth_mm"] >= P["SKIN_DEPTH_MIN_MM"], aid
        assert a["in_bone_pct"] <= P["IN_BONE_MAX_PCT"] and a["bone_depth_max_mm"] <= P["BONE_DEPTH_MAX_MM"], aid
        assert g["musc_share"][1] >= P["MUSC_SHARE_MIN"] and g["musc_share"][1] >= g["musc_share"][0] - 0.01, aid
        assert g["evidence_volume_ratio"] >= P["EVID_LO"] and g["volume_ratio"] >= P["COLLAPSE_MIN"], aid
        assert g["length_ratio"] >= P["LEN_LO"] or g.get("length_vs_z", 0) >= P["LEN_Z_LO"], aid
        assert a["main_piece"] >= min(P["MAIN_PIECE_MIN"], b["main_piece"]) - 1e-9, aid
        assert g["move_new_to_old_p95_mm"] <= P["MOVE_P95_MAX_MM"], aid
        assert g["overlap_vol_pct"][1] <= P["OVERLAP_MAX"], aid
        assert P["Z_GATE"][0] <= g.get("volume_vs_z", 1.0) <= P["Z_GATE"][1], aid
        if "seam_gap_mm" in g:
            assert g["seam_gap_mm"]["p95"] <= P["SEAM_MAX_MM"], aid
        assert g["fit_error_vs_label"]["p95_mm"] < 2.5, aid


def test_bundle_keeps_every_other_entry_byte_for_byte():
    _skip_if_missing(SRC / "bundle.json", NEW / "bundle.json", REPORT)
    rep = _report()
    A, B = _bundle(SRC), _bundle(NEW)
    assert len(A.items) == len(B.items)
    changed = []
    for k, it in enumerate(A.items):
        assert B.items[k]["e"]["id"] == it["e"]["id"]
        if B.items[k]["raw"] != it["raw"] or B.items[k]["e"] != it["e"]:
            changed.append(it["e"]["id"])
    assert sorted(changed) == sorted(rep["replaced"])
    for aid in changed:
        e = B.items[B.find(aid)[0]]["e"]
        e0 = A.items[A.find(aid)[0]]["e"]
        assert e["subject"] == SUBJECT and e0["subject"].startswith("xfer_vhm2vhf_sep") and e["cat"] == "muscle" and e["side"] == e0["side"]
        for key in ("name", "latin", "origin", "insertion", "nerve", "compartments"):
            assert e["rec"].get(key) == e0["rec"].get(key), (aid, key)
        assert not e.get("hidden_default")
    assert SUBJECT in B.j["subject"].split("+") and len(B.j["attribution"]) == len(B.j["subject"].split("+"))


def test_replaced_cards_carry_the_badge_with_volume_and_fit_error():
    _skip_if_missing(NEW / "bundle.json", REPORT)
    rep = _report()
    B = _bundle(NEW)
    for aid, r in rep["replaced"].items():
        it = B.items[B.find(aid)[0]]
        badge = it["e"]["rec"]["procedural_badge"]
        assert badge == r["badge"]
        for need in ("TRANSFERRED", "Q215", "Fit error", "Guards passed", "not measured", "A position and boundary estimate"):
            assert need in badge, (aid, need)
        g = r["guards"]
        assert f"Volume {g['after']['volume_cm3']} cm3" in badge and f"median {g['fit_error_vs_label']['median_mm']} mm" in badge
        v, f = B.mesh(it)
        vol = abs(trimesh.Trimesh(v, f, process=False).volume) / 1000.0
        assert abs(vol - g["after"]["volume_cm3"]) < 0.03 * g["after"]["volume_cm3"] + 0.3          # the shipped (quantised) mesh has the reported volume


def test_replaced_meshes_are_inside_the_skin_and_out_of_her_bones_in_the_shipped_bundle():
    _skip_if_missing(NEW / "bundle.json", REPORT)
    rep = _report()
    B = _bundle(NEW)
    ctx = F.Context(B)
    for aid in rep["replaced"]:
        v, f = B.mesh(B.items[B.find(aid)[0]])
        inside, depth = ctx.skin_state(v)
        assert inside == 100.0 and depth >= 1.0, aid
        ins, _, _ = ctx.bone_field.inside(v)
        assert 100.0 * float(ins.mean()) <= Fi.IN_BONE_MAX_PCT, aid
        assert float(ctx.bone_depth().depth(v).max()) <= Fi.BONE_DEPTH_MAX_MM, aid


def test_scope_check_json_lists_no_unlisted_change():
    p = REPO / "data/derived/Q215_vertex_diff.json"
    _skip_if_missing(p)
    d = json.loads(p.read_text())
    rep = _report()
    assert d["unlisted_changes"] == [] and d["listed_but_unchanged"] == [] and d["replaced_carry_q215_subject"]
    assert sorted(d["changed_ids"]) == sorted(rep["replaced"]) and d["entries"] == d["identical"] + d["changed"] and d["quantum_same"]


def test_source_class_counts_on_the_page_match_the_audit_and_the_z_fill_class_is_unchanged():
    p = REPO / "data/derived/Q215_model_separation_audit.json"
    q = REPO / "data/derived/Q214_model_separation_audit.json"
    _skip_if_missing(p, q)
    a, b = json.loads(p.read_text())["own_female"], json.loads(q.read_text())["own_female"]
    rep = _report()
    assert a["by_class"]["filled_zan"] == b["by_class"]["filled_zan"]                      # nothing became / stopped being Z-Anatomy fill
    assert a["by_class"]["transferred"]["entries"] == b["by_class"]["transferred"]["entries"]     # replaced muscles stay transferred
    assert len(rep["replaced"]) > 0


def test_z_fitted_female_page_is_untouched():
    z = REPO / "build/q213/viewer_zan_female"
    if not z.exists():
        pytest.skip("Z female page not built")
    assert not (REPO / "build/q215/viewer_zan_female").exists()                                # Q215 builds no Z page: nothing to regenerate there


def test_clinical_needle_tool_unchanged_in_the_q215_page():
    if not (PAGE / "clinical_needle_tool.js").exists():
        pytest.skip("q215 page not built / clinical files not staged")
    assert (PAGE / "clinical_needle_tool.js").read_bytes() == (PAGE_OLD / "clinical_needle_tool.js").read_bytes()
    assert (PAGE / "clinical_needle_tool.js").read_bytes() == (REPO / "clinical" / "needle_tool.js").read_bytes()


def test_q215_motor_points_lie_in_their_structure():
    if not (PAGE / "atlas_viewer_female.html").exists():
        pytest.skip("q215 page not built")
    mp = json.loads((REPO / "clinical" / "data" / "motor_points.json").read_text())["viewers"]["vhf"]["points"]
    saved = M.VIEWERS["vhf"]
    M.VIEWERS["vhf"] = {**saved, "html": PAGE / "atlas_viewer_female.html", "bin": NEW / "bundle.bin"}
    try:
        meshes = M.load_viewer("vhf")
    finally:
        M.VIEWERS["vhf"] = saved
    assert mp
    rep = _report()
    placed = {p["structure_id"] for p in mp}
    for p in mp:
        m = meshes[p["structure_id"]]
        q = np.array(p["pos"], float)
        ok = bool(M.inside(q, m["v"], m["f"])[0]) or float(np.min(np.linalg.norm(m["v"] - q, axis=1))) <= 1.0
        assert ok, p["id"]
        assert p["side"] == p["atlas_id"][-1]
    stems = {r["muscle"] for r in M.RULES}
    assert any(a in placed for a in rep["replaced"] if re.sub(r"_(r|l)$", "", a) in stems)


def test_q204_before_after_json_records_the_replaced_rows():
    p = REPO / "data/derived/Q215_regions_before_after.json"
    _skip_if_missing(p)
    d = json.loads(p.read_text())
    rep = _report()
    assert set(d["replaced_rows"]) == set(rep["replaced"])
    s = d["replaced_sum"]
    assert s["mean_inside_bone_pct_after"] <= s["mean_inside_bone_pct_before"] and s["inside_bone_findings_after"] <= s["inside_bone_findings_before"]
    assert d["counts_before"]["structures"] == d["counts_after"]["structures"]


def test_page_check_has_no_errors_and_the_class_counts_match():
    p = REPO / "data/derived/Q215_pagecheck.json"
    _skip_if_missing(p)
    d = json.loads(p.read_text())["female"]
    for n in ("desktop", "phone"):
        assert d[n]["errors"] == [] and d[n]["scrollW"] <= d[n]["innerW"] + 1
    assert all(d["match"].values())
