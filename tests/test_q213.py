"""Q213: the TARGET MUSCLES of the two female needle-layer pages (own female, Z fitted to her): motor-point algorithm fixes, in-bone repair, added hand muscles, split opponens.

Synthetic tests run everywhere; tests on the built pages / bundles skip when the page is not built.  The clinical-file guards compare ONLY clinical_needle_tool.js (the motor-point
and risk files legitimately differ between the Q212 / Q211 pages and the Q213 pages)."""
import json
import re
import sys
from pathlib import Path

import numpy as np
import pytest
import trimesh

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(REPO / "scripts" / "clinical"))
from scripts.clinical import motor_points_q187 as M  # noqa: E402
from scripts.transfer import q213_inbone as IB  # noqa: E402

OWN_BUNDLE_Q212 = REPO / "build/viewer_f_hr_q212"
OWN_BUNDLE_Q213 = REPO / "build/viewer_f_hr_q213"
OWN_PAGE_Q213 = REPO / "build/q213/viewer_f_hr"
OWN_PAGE_Q212 = REPO / "build/q212/viewer_f_hr"
Z_PAGE_Q213 = REPO / "build/q213/viewer_zan_female"
Z_PAGE_Q211 = REPO / "build/q211/viewer_zan_female"
STEM_Z = "atlas_viewer_zan_female"


def box(lo, hi):
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    m = trimesh.creation.box(extents=hi - lo)
    m.apply_translation((lo + hi) / 2)
    return np.asarray(m.vertices, float), np.asarray(m.faces, np.int64)


def mesh(lo, hi, cat="muscle", sub=3):
    v, f = box(lo, hi)
    tm = trimesh.Trimesh(v, f, process=False)
    for _ in range(sub):
        tm = tm.subdivide()
    return {"cat": cat, "v": np.asarray(tm.vertices, float), "f": np.asarray(tm.faces, np.int64)}


# ---------------------------------------------------------------- algorithm: the whole muscle (own pages: measured mesh + Z-fill pieces)
def tube_body():
    """a muscle along y cut flat at y=100 and continued by a Z-fill piece up to y=200; her bones at the sides"""
    meshes = {
        "foo_r": mesh((50, 0, -5), (60, 100, 5)),
        "foo_r_zfill9": mesh((50, 100, -5), (60, 200, 5)),
        "foo_r_other": mesh((0, 0, 0), (1, 1, 1)),    # not a piece of foo_r
    }
    return M.Body("vhf", meshes)


def test_pieces_union_and_piece_at():
    b = tube_body()
    assert b.pieces("foo_r") == ["foo_r", "foo_r_zfill9"]
    V, F = b.union("foo_r")
    assert V[:, 1].min() == 0 and V[:, 1].max() == 200 and len(F) == 2 * 768
    assert b.piece_at("foo_r", np.array([55.0, 50.0, 0.0])) == "foo_r"
    assert b.piece_at("foo_r", np.array([55.0, 150.0, 0.0])) == "foo_r_zfill9"
    assert b.piece_at("foo_r", np.array([555.0, 150.0, 0.0])) is None
    zb = M.Body("zan_f", {"foo_r": mesh((0, 0, 0), (1, 1, 1)), "foo_r_zfill9": mesh((0, 0, 0), (1, 1, 1))})
    assert zb.pieces("foo_r") == ["foo_r"]           # Z pages carry no Z-fill pieces


def test_level_rule_is_measured_on_the_whole_muscle_not_on_its_flat_cut_piece():
    b = tube_body()
    rule = M.R("foo", "caetano2020", "motor_point", "level", "synthetic", A="mend_org:+sup", B="mend_ins:+sup", f=(0, 33), nerve="n")
    res, why = M.place(b, rule, "r")
    assert res is not None, why
    y = float(res["pos"][1])
    assert 130.0 <= y <= 200.0, y                    # origin = the top of the CONTINUED muscle (y=200): the proximal third is y 133-200, not 67-100 of the base piece
    assert res["structure_id"] == "foo_r_zfill9"      # the point lies in the continuation piece -> that piece is the structure id
    assert abs(res["line_len"] - 200.0) < 5.0


def test_component_near_picks_the_hand_island():
    v1, f1 = box((0, 0, 0), (10, 10, 10))
    v2, f2 = box((0, -900, 0), (10, -890, 10))
    V = np.vstack([v1, v2]); F = np.vstack([f1, f2 + len(v1)])
    hv, hf = M.component_near(V, F, np.array([5.0, 20.0, 5.0]))
    assert len(hv) == len(v1) and hv[:, 1].min() == 0 and hf.max() < len(hv)
    fv, ff = M.component_near(V, F, np.array([5.0, -880.0, 5.0]))
    assert fv[:, 1].max() < 0


def test_rules_carry_the_q213_aliases():
    tp = [r for r in M.RULES if r["muscle"] == "tibialis_posterior"]
    assert len(tp) == 3 and all(r["parts"]["zan"] == "zan_tibialis_posterior_muscle_{s}" for r in tp)
    odm = [r for r in M.RULES if r["muscle"] == "opponens_digiti_minimi"]
    assert odm and all(r["near"] == "abductor_digiti_minimi_hand_{s}" for r in odm)
    pl = [r for r in M.RULES if r["muscle"] == "palmaris_longus"][0]
    b = M.Body("vhf", {"zan_palmaris_longus_muscle_l": mesh((0, 0, 0), (10, 100, 10))})
    assert M.structure_for(b, pl, "l") == ("zan_palmaris_longus_muscle_l", True)      # her own page names its left palmaris longus like the Z source


def test_mastoid_of_an_own_page_is_measured_on_the_cranium_not_the_styloid_stub():
    scm = mesh((50, 500, -20), (60, 660, 0))
    meshes = {"sternocleidomastoid_r": scm, "temporal_r": mesh((36, 685, 0), (42, 706, 12)),     # the styloid stub (250 vertices in her bundle): 26 mm from the SCM top
              "cranium": mesh((-70, 665, -90), (72, 845, 100))}
    b = M.Body("vhf", meshes)
    mast = b.lm("mastoid", "r")
    assert 600 < mast[1] < 720 and mast[2] > -91
    assert np.linalg.norm(mast - np.array([55.0, 660.0, -10.0])) < 25.0
    with pytest.raises(M.LandmarkMissing):          # a Z page keeps its own rule (temporal bone only): unchanged behaviour
        M.Body("zan_f", {"sternocleidomastoid_r": scm, "temporal_r": mesh((36, 685, 0), (42, 706, 12))}).lm("mastoid", "r")


# ---------------------------------------------------------------- in-bone repair
def bone_and_muscle(overlap=4.0):
    b = mesh((-10, -50, -10), (10, 150, 10), sub=2)
    bone = (b["v"], b["f"])
    mus = box((10 - overlap, 0, -8), (32, 100, 8))      # a slab lying `overlap` mm inside the bone along one face
    return bone, mus


def test_inbone_repair_pushes_out_and_keeps_the_ends_and_volume():
    (bv, bf), (mv, mf) = bone_and_muscle(2.5)
    # refine the slab so that it has interior vertices to move
    tm = trimesh.Trimesh(mv, mf).subdivide().subdivide().subdivide()
    mv, mf = np.asarray(tm.vertices), np.asarray(tm.faces)
    field = IB.BoneField({"b": (bv, bf)})
    ins0, _, _ = field.inside(mv)
    assert ins0.mean() > 0.05
    nv, rep = IB.repair(mv, mf, field)
    assert nv is not None and rep["accepted"], rep
    ins1, _, _ = field.inside(nv)
    assert ins1[~IB.ends_mask(mv)].mean() * 100 <= IB.GATE_PCT
    assert IB.VOL_LO <= rep["volume_ratio"] <= IB.VOL_HI and rep["flipped_pct"] <= 0.5
    ends = IB.ends_mask(mv)
    assert np.linalg.norm(nv[ends] - mv[ends], axis=1).max() < 4.0 + 1e-6      # origin / insertion zones are held (anchored)


def test_inbone_repair_refuses_a_move_that_changes_the_volume_too_much():
    ok, why = IB.accept(dict(inside_before_pct=40.0, inside_after_pct=2.0, mean_move_mm=1.0, max_move_mm=5.0, volume_ratio=1.7, flipped_pct=0.0, stretched_before=0.0, stretched_after=1.0))
    assert not ok and any("volume" in w for w in why)
    ok, why = IB.accept(dict(inside_before_pct=40.0, inside_after_pct=2.0, mean_move_mm=9.0, max_move_mm=14.0, volume_ratio=1.0, flipped_pct=0.0, stretched_before=0.0, stretched_after=1.0))
    assert not ok and any("move" in w for w in why)
    ok, why = IB.accept(dict(inside_before_pct=20.0, inside_after_pct=3.0, mean_move_mm=1.0, max_move_mm=5.0, volume_ratio=1.05, flipped_pct=0.1, stretched_before=0.0, stretched_after=1.0))
    assert ok, why


def test_seam_vertices_stay_put():
    (bv, bf), (mv, mf) = bone_and_muscle(2.5)
    tm = trimesh.Trimesh(mv, mf).subdivide().subdivide().subdivide()
    mv, mf = np.asarray(tm.vertices), np.asarray(tm.faces)
    field = IB.BoneField({"b": (bv, bf)})
    seam = mv[:, 1] > 90.0
    nv, rep = IB.chain(mv, mf, field, (40.0, 10.0, 3.0), anchors=seam)
    assert np.linalg.norm(nv[seam] - mv[seam], axis=1).max() < 1.0      # anchored at weight 200


def test_overlap_guard_refuses_a_push_into_a_neighbour_muscle():
    (bv, bf), (mv, mf) = bone_and_muscle(2.5)
    tm = trimesh.Trimesh(mv, mf).subdivide().subdivide().subdivide()
    mv, mf = np.asarray(tm.vertices), np.asarray(tm.faces)
    field = IB.BoneField({"b": (bv, bf)})
    calls = [0]

    def ov(V):
        calls[0] += 1
        return 0.0 if calls[0] == 1 else 60.0
    nv, rep = IB.repair(mv, mf, field, overlap=ov)
    assert nv is None and any("muscle overlap" in w for w in rep["why_not"])
    nb = mesh((200, 0, -8), (230, 100, 8), sub=2)
    mo = IB.MuscleOverlap({"far": (nb["v"], nb["f"])})
    assert mo.pct(mv) == 0.0
    nv, rep = IB.repair(mv, mf, field, overlap=lambda V: mo.pct(V))
    assert nv is not None and rep["overlap_before_pct"] == 0.0 and rep["overlap_after_pct"] == 0.0
    near = mesh((9, -10, -12), (30, 110, 12), sub=2)                  # the neighbour sits where the slab itself is: the share is measured against the OTHER muscles only
    mo2 = IB.MuscleOverlap({"self": (near["v"], near["f"])})
    assert mo2.pct(mv, skip=("self",)) == 0.0 and mo2.pct(mv) > 30.0


# ---------------------------------------------------------------- built artefacts
def _bundle(d):
    from scripts.transfer.q200_bundle import Bundle
    return Bundle(d)


def _skip_if_missing(*paths):
    for p in paths:
        if not Path(p).exists():
            pytest.skip(f"{p} not built")


def test_own_bundle_changes_only_listed_entries_and_every_change_is_badged():
    _skip_if_missing(OWN_BUNDLE_Q212 / "bundle.json", OWN_BUNDLE_Q213 / "bundle.json", REPO / "data/derived/Q213_own_female_report.json")
    rep = json.loads((REPO / "data/derived/Q213_own_female_report.json").read_text())
    A, B = _bundle(OWN_BUNDLE_Q212), _bundle(OWN_BUNDLE_Q213)
    n0 = len(A.items)
    changed, added = set(), set()
    for k, it in enumerate(B.items):
        if k < n0:
            o = A.items[k]
            assert it["e"]["id"] == o["e"]["id"] and it["e"]["subject"] == o["e"]["subject"]
            if it["raw"] != o["raw"] or it["e"] != o["e"]:
                changed.add(it["e"]["id"])
        else:
            added.add(it["e"]["id"])
    listed = set(rep["repaired"])
    assert changed == listed, (sorted(changed - listed), sorted(listed - changed))
    assert added == set(rep["added"])
    for k, it in enumerate(B.items):
        e = it["e"]
        if e["id"] in listed and k < n0:
            assert "Q213" in e["rec"]["procedural_badge"] and "belly" in e["rec"]["procedural_badge"]
        if e["id"] in added:
            assert e["subject"] == "xfer_zan2vhf_hand_q213" and e["cat"] == "muscle"
            b = e["rec"]["procedural_badge"]
            assert "Z-Anatomy" in b and "Not measured on her" in b and "position estimate" in b
    for sid in rep["unhidden"]:
        assert not any(x["e"]["id"] == sid and x["e"].get("hidden_default") for x in B.items)


def test_repaired_muscles_met_their_gates():
    _skip_if_missing(REPO / "data/derived/Q213_own_female_report.json", REPO / "data/derived/Q213_zfit_report.json")
    for name in ("Q213_own_female_report.json", "Q213_zfit_report.json"):
        rep = json.loads((REPO / "data/derived" / name).read_text())
        for sid, r in rep["repaired"].items():
            assert r["accepted"], sid
            assert IB.VOL_LO <= r["volume_ratio"] <= IB.VOL_HI and r["flipped_pct"] <= 0.5, sid
            assert r["mean_move_mm"] <= IB.MEAN_MOVE_MAX and r["max_move_mm"] <= IB.MAX_MOVE_MAX, sid
            assert r["inside_after_belly_pct"] <= max(IB.GATE_PCT, 0.4 * r["inside_before_belly_pct"]), sid
        for sid, r in rep["held"].items():
            assert not r["accepted"] and r["why_not"], sid


def test_new_subject_is_described_and_classed():
    txt = (REPO / "viewer" / "atlas_viewer.template.html").read_text(encoding="utf-8")
    m = re.search(r"^\s{2}xfer_zan2vhf_hand_q213:\s*\"(.*)\",?$", txt, re.M)
    assert m and "FILLED from Z-Anatomy" in m.group(1) and "not measured on her" in m.group(1)


def test_z_page_changes_only_listed_meshes_and_splits_the_merged_opponens():
    _skip_if_missing(Z_PAGE_Q213 / f"{STEM_Z}.html", REPO / "data/derived/Q213_zfit_report.json")
    from scripts.zanatomy import q202_pages as P2
    rep = json.loads((REPO / "data/derived/Q213_zfit_report.json").read_text())
    sd = rep["ship_diff"]
    assert sd["geometry_changed_but_not_listed"] == []
    assert sorted(sd["added"]) == ["opponens_digiti_minimi_foot_l", "opponens_digiti_minimi_foot_r"] and sd["removed"] == []
    mo, bo = P2.load_page(Z_PAGE_Q211, STEM_Z)
    mn, bn = P2.load_page(Z_PAGE_Q213, STEM_Z)
    So, Sn = P2.decode(mo, bo), P2.decode(mn, bn)
    for s in "rl":
        hand, foot = Sn[f"opponens_digiti_minimi_{s}"], Sn[f"opponens_digiti_minimi_foot_{s}"]
        assert hand["v"][:, 1].min() > 0 > foot["v"][:, 1].max()                    # hand island above the feet
        assert len(hand["v"]) + len(foot["v"]) == len(So[f"opponens_digiti_minimi_{s}"]["v"])
        assert "Q213" in (hand["m"].get("rec") or {}).get("procedural_badge", "")
    assert rep["ship_diff"]["geometry_changed"] == len(rep["repaired"]) + 2


@pytest.mark.parametrize("page,ref", [(OWN_PAGE_Q213, OWN_PAGE_Q212), (Z_PAGE_Q213, Z_PAGE_Q211)])
def test_clinical_needle_tool_unchanged_in_the_q213_pages(page, ref):
    if not (page / "clinical_needle_tool.js").exists():
        pytest.skip("q213 page not built / clinical files not staged")
    assert (page / "clinical_needle_tool.js").read_bytes() == (ref / "clinical_needle_tool.js").read_bytes()
    assert (page / "clinical_needle_tool.js").read_bytes() == (REPO / "clinical" / "needle_tool.js").read_bytes()


@pytest.mark.parametrize("vk,page_html,page_bin", [("vhf", OWN_PAGE_Q213 / "atlas_viewer_female.html", OWN_BUNDLE_Q213 / "bundle.bin"),
                                                    ("zan_f", Z_PAGE_Q213 / f"{STEM_Z}.html", None)])
def test_q213_motor_points_lie_in_their_structure_on_the_q213_page(vk, page_html, page_bin):
    if not page_html.exists():
        pytest.skip("q213 page not built")
    q215 = (REPO / "build/q215/viewer_f_hr/atlas_viewer_female.html", REPO / "build/viewer_f_hr_q215/bundle.bin")
    if vk == "vhf" and q215[0].exists() and q215[1].exists():            # Q215: the own female motor points are regenerated on the Q215 page (hip / thigh target muscles re-bounded)
        page_html, page_bin = q215
    q216 = (REPO / "build/q216/viewer_f_hr/atlas_viewer_female.html", REPO / "build/viewer_f_hr_q216/bundle.bin")
    if vk == "vhf" and q216[0].exists() and q216[1].exists():            # Q216: ... regenerated on the Q216 page (nerve corridor, ends, islands, flat facets)
        page_html, page_bin = q216
    q217 = (REPO / "build/q217/viewer_m_hr/atlas_viewer_male.html", REPO / "build/viewer_m_hr_q217/bundle.bin")
    if vk == "vhm" and q217[0].exists() and q217[1].exists():            # Q217: the own male motor points are regenerated on the Q217 page
        page_html, page_bin = q217
    q225 = REPO / "build/q225_fit/viewer_zan_female/atlas_viewer_zan_female.html"
    if vk == "zan_f" and q225.exists():                                  # Q225: the Z female fitted motor points are regenerated on the Q225 page (left elbow / patella / rib re-seat, wrist / shoulder carried)
        page_html = q225
    mp = json.loads((REPO / "clinical" / "data" / "motor_points.json").read_text())["viewers"][vk]["points"]
    saved = M.VIEWERS[vk]
    M.VIEWERS[vk] = {**saved, "html": page_html, **({"bin": page_bin} if page_bin else {})}
    try:
        meshes = M.load_viewer(vk)
    finally:
        M.VIEWERS[vk] = saved
    assert mp
    for p in mp:
        m = meshes.get(p["structure_id"])
        if m is None:          # Q214: a muscle added to the own female page after Q213 (its points are checked in tests/test_q214.py)
            assert vk == "vhf" and p["structure_id"].startswith(("splenius_", "fibularis_brevis", "flexor_pollicis_brevis")), p["id"]
            continue
        q = np.array(p["pos"], float)
        ok = bool(M.inside(q, m["v"], m["f"])[0]) or float(np.min(np.linalg.norm(m["v"] - q, axis=1))) <= 1.0
        assert ok, (vk, p["id"])
        assert p["side"] == p["atlas_id"][-1] and (q[0] + 4.3) * (1 if p["side"] == "r" else -1) > -6.0     # no left / right swap


def test_q213_motor_point_coverage_recorded_and_the_fixed_cases_are_placed():
    cov_path = REPO / "data/derived/Q187_motor_points_coverage.json"
    bef_path = REPO / "data/derived/Q213_motor_points_coverage_before.json"
    mp = json.loads((REPO / "clinical/data/motor_points.json").read_text())
    if not (cov_path.exists() and bef_path.exists()):
        pytest.skip("coverage files missing")
    cov = json.loads(cov_path.read_text())["viewers"]
    bef = json.loads(bef_path.read_text())["viewers"]
    assert (bef["vhf"]["points"], len(bef["vhf"]["failed"]), len(bef["vhf"]["not_placed"])) == (170, 15, 23)      # the published state (main session, after Q212)
    assert (bef["zan_f"]["points"], len(bef["zan_f"]["failed"]), len(bef["zan_f"]["not_placed"])) == (191, 11, 6)
    for vk in ("vhf", "zan_f"):
        assert cov[vk]["points"] == len(mp["viewers"][vk]["points"])
        assert cov[vk]["points"] > bef[vk]["points"]
        assert len(cov[vk]["failed"]) <= len(bef[vk]["failed"]) and len(cov[vk]["not_placed"]) < len(bef[vk]["not_placed"])
    assert cov["zan_f"]["not_placed"] == []                                         # tibialis posterior (Z id zan_tibialis_posterior_muscle_*) is placed now
    assert "tibialis_posterior" in cov["zan_f"]["muscles_with_points"]
    assert "sternocleidomastoid" in cov["vhf"]["muscles_with_points"]               # mastoid measured on her cranium
    assert "palmaris_longus" in cov["vhf"]["muscles_with_points"]                    # her page's Z-named left palmaris longus + the added right one
    # no point of the opponens digiti minimi lies in the foot island
    for vk in ("vhf", "zan_f"):
        for p in mp["viewers"][vk]["points"]:
            if p["atlas_id"].startswith("opponens_digiti_minimi"):
                assert p["pos"][1] > -100.0, p["id"]
