"""Q157: scripts/zanatomy/build_zan_atlas_viewer.py -- the full-body Z-Anatomy
reference viewer exporter (owner's preferred August-viewer UI, fed by this
project's own pipeline).

Runs the REAL exporter against the real, gitignored Z-Anatomy extraction
(build/zanatomy/, ~90 MB) at a tiny --budget-scale (fast: decimation itself is
not this build's bottleneck, per-object npz loading across ~2570 structures
is, so a smaller budget does not meaningfully speed this up -- a small scale
is used anyway so a future, slower decimator would not make this suite slow).
Skips cleanly when that build output isn't present, matching this repo's
established pattern for build-dependent tests (see
tests/test_intervertebral_discs.py's own module docstring, and
tests/test_zanatomy_corrections.py, which documents the same rule from the
other side: never touch build/zanatomy/ from a fast, always-runnable test).

Three checks, all read off ONE real build (module-scoped fixture, so the
~90 MB extraction is only walked once for this whole file):
  1. every emitted id is unique (a duplicate would silently overwrite the
     first structure's own geometry offsets when read back by name/id).
  2. no structure's own `rec` carries a `clinical` key -- this project's
     private clinical layer (trigger points, special tests, referred-pain
     compilations) must never enter this CC BY-SA-facing build.
  3. every structure this build's own `apply_correction()` actually warped
     (Q144/Q145's posterior interosseous nerve, both sides -- the manifest's
     own `totals.corrected_ids`) carries a `rec.procedural_badge` naming the
     correction and its citation, the "procedural/transfer badge" convention.
"""
import sys
from pathlib import Path

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.zanatomy.build_zan_atlas_viewer import (  # noqa: E402
    DEFAULT_CORRECTIONS_DIR, DEFAULT_INVENTORY, DEFAULT_NAMEMAP,
    DEFAULT_ZAN_DIR, build,
)


@pytest.fixture(scope="module")
def manifest():
    if not Path(DEFAULT_ZAN_DIR).exists():
        pytest.skip("build/zanatomy not present (gitignored Z-Anatomy extraction)")
    man, _blob, _origin = build(
        zan_dir=Path(DEFAULT_ZAN_DIR), inventory_path=Path(DEFAULT_INVENTORY),
        namemap_path=Path(DEFAULT_NAMEMAP), corrections_dir=Path(DEFAULT_CORRECTIONS_DIR),
        budget_scale=0.02, close_gaps=False,  # Q162 closure: unit-tested below + committed report
    )
    return man


def test_every_id_is_unique(manifest):
    ids = [m["id"] for m in manifest["meshes"]]
    assert len(ids) == len(set(ids)), "exporter emitted the same id twice"
    assert len(ids) > 2000  # sanity: the real matched+orphan pool is ~2570 structures


def test_no_structure_carries_a_clinical_key(manifest):
    for m in manifest["meshes"]:
        rec = m.get("rec") or {}
        assert "clinical" not in rec, f"{m['id']} carries a clinical key"
    # belt-and-braces: the manifest itself has no top-level clinical block either
    assert "clinical" not in manifest


def test_corrected_structures_carry_a_citation_badge(manifest):
    corrected_ids = manifest["totals"]["corrected_ids"]
    assert corrected_ids, "expected at least the Q144/Q145 posterior interosseous nerve correction"
    # Q162: plus the contralateral mirror repairs (gap closure is off in this fixture)
    repaired = {r["id"] for r in manifest["totals"]["contralateral_repairs"]["repaired"]}
    # Q186: plus the orphans whose side was inferred/swapped from their position (badged with the reason)
    q186 = manifest["totals"]["q186_fixes"]
    resided = {x["now"] for k in ("side_inferred", "side_swapped") for x in q186[k]}
    assert set(corrected_ids) == {"posterior_interosseous_n_l", "posterior_interosseous_n_r"} | repaired | resided
    by_id = {m["id"]: m for m in manifest["meshes"]}
    for aid in ("posterior_interosseous_n_l", "posterior_interosseous_n_r"):
        badge = (by_id[aid].get("rec") or {}).get("procedural_badge")
        assert badge, f"{aid} is listed as corrected but carries no badge"
        assert "PMID" in badge and "arcade of Frohse" in badge

    # an UNCORRECTED structure (the radial nerve trunk itself) must carry no badge
    for side in ("radial_n_l", "radial_n_r"):
        assert side in by_id, f"expected the side-split {side} to be shipped"
        assert not (by_id[side].get("rec") or {}).get("procedural_badge")


def test_matched_structures_carry_real_atlas_facts(manifest):
    by_id = {m["id"]: m for m in manifest["meshes"]}
    pt = by_id.get("pronator_teres_l") or by_id.get("pronator_teres_r")
    assert pt is not None, "expected pronator teres to be matched from Z-Anatomy"
    rec = pt["rec"]
    assert rec["name"] == "Pronator teres"
    assert rec["origin"] and rec["insertion"]
    assert rec["nerve"] == ["median_n"]
    assert rec["compartments"][0]["pcsa"] == 430


def test_no_source_objects_are_merged_into_one_shipped_mesh(manifest):
    """Q158b (lead review of Q158's first cut): Q158's own "grouped_*"/
    "numbered_series_*"/"muscle_head_or_part" rules must attach a PARENT link
    (this object's info card names a coarser atlas entity and borrows its
    facts) rather than concatenate this object's geometry into the parent's
    mesh. No two distinct Z-Anatomy source objects may ever collapse into one
    shipped id: every parent-linked structure ships under its own `zan_`
    orphan id, and no shipped mesh's own id is a raw multi-part group id
    (carpals_l/ribs_r/cervical_vertebrae/phalanges_hand_l/... -- Q158's first
    cut shipped these as fused blobs; Z-Anatomy has no single source object
    for any of them, so none should ever appear as a mesh id here)."""
    by_id = {m["id"]: m for m in manifest["meshes"]}
    ids = list(by_id)

    parent_linked = [m for m in manifest["meshes"] if (m.get("rec") or {}).get("part_of_id")]
    assert parent_linked, "expected at least the Q158b carpal/rib/vertebra/muscle-head parent links"
    for m in parent_linked:
        assert m["id"].startswith("zan_"), (
            f"{m['id']} carries a part_of link but is not shipped as its own separate "
            f"orphan mesh -- looks merged into its parent's geometry")

    # these coarse group ids have NO single Z-Anatomy source object of their
    # own (Q158's first cut only ever populated them by fusing several
    # distinct real objects together) -- they must never be a mesh id here.
    never_own_mesh = ["carpals_l", "carpals_r", "ribs_l", "ribs_r",
                       "cervical_vertebrae", "thoracic_vertebrae", "lumbar_vertebrae",
                       "phalanges_hand_l", "phalanges_hand_r",
                       "phalanges_foot_l", "phalanges_foot_r"]
    for aid in never_own_mesh:
        assert aid not in ids, f"{aid} is shipped as its own mesh -- looks like fused/merged geometry again"

    # a real single named bone/muscle-head must still be individually
    # selectable, each carrying its OWN geometry and its parent's facts.
    scaphoid = by_id.get("zan_scaphoid_bone_l")
    assert scaphoid is not None, "expected scaphoid to ship as its own selectable structure"
    assert scaphoid["rec"]["part_of_id"] == "carpals_l"

    rib5 = by_id.get("zan_fifth_rib_r")
    assert rib5 is not None, "expected a single rib to ship as its own selectable structure"
    assert rib5["rec"]["part_of_id"] == "ribs_r"

    l3 = by_id.get("zan_vertebra_l3")
    assert l3 is not None, "expected a single vertebra to ship as its own selectable structure"
    assert l3["rec"]["part_of_id"] == "lumbar_vertebrae"

    tri_head = by_id.get("zan_long_head_of_triceps_brachii_l")
    assert tri_head is not None, "expected a muscle head to ship as its own selectable structure"
    assert tri_head["rec"]["part_of_id"] == "triceps_brachii_l"

    # a fused carpal blob (8 bones unioned, Q158's own first cut) would carry
    # thousands of vertices; a single decimated carpal bone must not.
    assert scaphoid["vc"] < 500, "scaphoid's own vertex count looks fused (too large for a single carpal bone)"


def test_quadric_decimation_keeps_a_thin_tube_in_one_piece():
    # Q159: vertex clustering split long thin nerves/vessels into beads; quadric must not.
    import numpy as np
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    from scripts.zanatomy.build_zan_atlas_viewer import decimate
    n_ring, n_len = 12, 400
    t = np.linspace(0, 2 * np.pi, n_ring, endpoint=False)
    z = np.linspace(0, 400.0, n_len)
    v = np.array([[1.5 * np.cos(a), 1.5 * np.sin(a), zz] for zz in z for a in t])
    f = []
    for i in range(n_len - 1):
        for j in range(n_ring):
            a, b = i * n_ring + j, i * n_ring + (j + 1) % n_ring
            f += [[a, b, a + n_ring], [b, b + n_ring, a + n_ring]]
    f = np.array(f)
    dv, df = decimate(v, f, "test_tube_n", "nerve", 0.22)
    assert len(df) < len(f)
    e = np.concatenate([df[:, [0, 1]], df[:, [1, 2]], df[:, [2, 0]]])
    ncomp, _ = connected_components(coo_matrix((np.ones(len(e)), (e[:, 0], e[:, 1])), shape=(len(dv),) * 2),
                                    directed=False)
    assert ncomp == 1


def test_external_bin_split_is_even_and_lossless():
    from scripts.zanatomy.build_zan_atlas_viewer import render_html, split_blob
    blob = bytes(range(256)) * 1001
    parts = split_blob(blob, "page", max_bytes=10_001)
    assert all(len(c) % 2 == 0 for _, c in parts[:-1])
    assert b"".join(c for _, c in parts) == blob
    files = [{"path": p, "bytes": len(c)} for p, c in parts]
    html = render_html({"meshes": []}, blob, files)
    assert '__ANATOMY_BIN__=""' in html and parts[0][0] in html


def test_inside_out_mesh_is_turned_outward():
    # Q160: an inside-out closed mesh (negative signed volume) must come out outward-facing.
    import numpy as np
    import trimesh
    from scripts.zanatomy.build_zan_atlas_viewer import orient_outward
    box = trimesh.creation.box(extents=(10.0, 20.0, 30.0))
    v, f = np.asarray(box.vertices), np.asarray(box.faces)[:, ::-1]  # flip every triangle
    def signed_volume(v, f):
        a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
        return np.einsum("ij,ij->i", a, np.cross(b, c)).sum() / 6
    assert signed_volume(v, f) < 0
    ov, of = orient_outward(v, f)
    assert abs(signed_volume(ov, of) - 6000.0) < 1e-6


def test_viewer_template_picks_by_pixel_and_draws_two_sided():
    from scripts.zanatomy.build_zan_atlas_viewer import TEMPLATE_PATH
    t = TEMPLATE_PATH.read_text(encoding="utf-8")
    assert "readPixels" in t and "renderIds" in t      # Q160 ID-buffer picking
    assert "o.radius/s.w" not in t                      # old bounding-sphere picking gone
    assert "gl_FrontFacing" in t and "gl.enable(gl.CULL_FACE)" not in t


def test_layer_rules_for_fascia_bursa_ligament_and_veins():
    # Q161: owner-requested colouring; "Tensor fasciae latae" must stay a muscle
    from scripts.zanatomy.build_zan_atlas_viewer import classify_layer, is_vein
    assert classify_layer("muscle", "Tensor fasciae latae.l") == "muscle"
    assert classify_layer("muscle", "Fascia lata.r") == "fascia"
    assert classify_layer("muscle", "Suprapatellar bursa.l") == "bursa"
    assert classify_layer("muscle", "Tendon sheath of tibialis anterior.l") == "bursa"
    assert classify_layer("fascia", "Flexor retinaculum of wrist.l") == "joint"
    assert is_vein("Great saphenous vein", "zan_great_saphenous_vein_l")
    assert is_vein("Brachiocephalic vein", "brachiocephalic_v_r")
    assert not is_vein("Femoral artery", "zan_femoral_artery_l")


def test_junk_filter_is_whole_word():
    from scripts.zanatomy.zan_source import _is_cross_category_junk
    assert not _is_cross_category_junk("Tensor fasciae latae.l", "muscle")
    assert _is_cross_category_junk("Deep fascia of leg.l", "muscle")


def test_matched_but_rejected_objects_are_still_shipped(manifest):
    # Q161: TFL (junk-filter victim) and the patellar retinacula / lumbricals (rejected
    # sub-parts of multi-part ids) used to vanish from every viewer
    ids = {m["id"] for m in manifest["meshes"]}
    for need in ("tensor_fasciae_latae_l", "zan_medial_patellar_retinaculum_l",
                 "zan_lumbrical_muscles_of_hand_r"):
        assert need in ids, need


def _box(center, size, sub=4):
    import trimesh
    m = trimesh.creation.box(extents=size)
    for _ in range(sub):
        m = m.subdivide()
    return np.asarray(m.vertices) + np.asarray(center, float), np.asarray(m.faces, np.int64)


def test_gap_between_parallel_muscles_closes_to_the_cited_interface():
    # Q162: two slabs 3 mm apart -> both move toward each other, gap ~1 mm, never overlapping
    from scripts.zanatomy import muscle_gap_closure as G
    a = _box((-11.5, 0, 0), (20, 40, 40))   # faces at x = -1.5
    b = _box((11.5, 0, 0), (20, 40, 40))    # faces at x = +1.5
    out = G.close_gaps({"a": a, "b": b}, {}, {})
    va, vb = out["a"][0], out["b"][0]
    mid = lambda v: v[(np.abs(v[:, 1]) < 10) & (np.abs(v[:, 2]) < 10)]  # centre of the contact face
    gap = mid(vb)[:, 0].min() - mid(va)[:, 0].max()
    assert 0.8 <= gap <= 1.4, gap
    assert out["a"][1]["volume_cm3_after"] > out["a"][1]["volume_cm3_before"]
    audit = G.audit({"a": (va, a[1]), "b": (vb, b[1])})
    assert audit["a"]["inside"] == 0 and audit["b"]["inside"] == 0


def test_gap_closure_never_moves_toward_a_nerve_or_vessel():
    # a 'nerve' plate in the 3 mm gap is an obstacle: the muscles stop 0.5 mm short of it
    from scripts.zanatomy import muscle_gap_closure as G
    a = _box((-11.5, 0, 0), (20, 40, 40))
    b = _box((11.5, 0, 0), (20, 40, 40))
    nerve = _box((0, 0, 0), (0.4, 60, 60), sub=3)       # faces at x = +-0.2
    out = G.close_gaps({"a": a, "b": b}, {}, {"n": nerve})
    assert out["a"][0][:, 0].max() <= -0.2 - G.OBSTACLE_MARGIN_MM + 1e-6
    assert out["b"][0][:, 0].min() >= 0.2 + G.OBSTACLE_MARGIN_MM - 1e-6


def test_contralateral_repairs_are_badged(manifest):
    # Q162: the broken left-side objects the mirror audit found are replaced by the mirrored right side
    by_id = {m["id"]: m for m in manifest["meshes"]}
    rep = manifest["totals"]["contralateral_repairs"]
    assert rep["pairs_audited"] > 500 and not rep["repair_targets_missing"]
    for r in rep["repaired"]:
        badge = (by_id[r["id"]].get("rec") or {}).get("procedural_badge", "")
        assert "contralateral repair" in badge, r["id"]


def test_committed_gap_closure_report_shows_closure_without_new_overlap():
    import json
    rep = json.loads((REPO_ROOT / "data" / "derived" / "Q162_gap_closure_contralateral.json").read_text())
    g = rep["gap_closure"]
    assert g["changed_muscles"] > 100
    assert g["after"]["frac_vertices_gap_gt_1_25mm"] < 0.7 * g["before"]["frac_vertices_gap_gt_1_25mm"]
    assert g["after"]["frac_vertices_inside_other_muscle"] <= g["before"]["frac_vertices_inside_other_muscle"] + 0.002


# ---------------------------------------------------------------- Q168 female variant
def test_fit_badge_uses_the_measured_error_or_says_it_is_a_region_estimate():
    from scripts.zanatomy.build_zan_atlas_viewer import fit_badge
    rep = {"per_structure": {"biceps_brachii_r": {
               "her_subject": "ct_vhf_armm_contfix", "centroid_mm": 17.5, "surface_mm": 17.4,
               "raw_centroid_mm": 53.4, "raw_surface_mm": 15.3, "her_extent_ratio": 0.5, "fit_target": False}},
           "region_of_structure": {"deltoid_r": "upper_limb"},
           "region_errors": {"upper_limb": {"n": 6, "surface_mm": {"median": 11.7, "max": 20.0}},
                             "whole_body": {"n": 183, "surface_mm": {"median": 6.1, "max": 28.0}}}}
    measured = fit_badge("biceps_brachii_r", rep, False)
    assert "Measured on her own CT mesh" in measured and "17.4" in measured and "cut off by the scan" in measured
    est = fit_badge("deltoid_r", rep, False)
    assert "Not measured" in est and "11.7" in est and "upper/limb" in est
    assert "cannot be checked" in fit_badge("unknown_l", rep, True)
    assert "6.1" in fit_badge("unknown_l", rep, True)  # falls back to the whole-body error


def test_female_wording_replaces_each_template_anchor_once():
    from scripts.zanatomy.build_zan_atlas_viewer import TEMPLATE_PATH, apply_vhf_wording
    html = apply_vhf_wording(TEMPLATE_PATH.read_text(encoding="utf-8"))
    assert "<title>NMSK Atlas — Z-Anatomy fitted to the female</title>" in html
    assert "Fitted to a real body (Q168)" in html


def test_committed_female_build_report_drops_male_only_and_badges_every_structure():
    import json
    from scripts.transfer.zan_to_vhf_whole_body import MALE_ONLY_IDS
    from scripts.zanatomy.build_zan_atlas_viewer import MALE_ONLY_SKIN  # Q186: penile/scrotal skin, pubic hair
    path = REPO_ROOT / "data" / "derived" / "Q168_zan_female_report.json"
    if not path.exists():
        pytest.skip("female variant not built")
    rep = json.loads(path.read_text())
    fit = rep["fit_to_vhf"]
    assert set(fit["male_only_dropped"]) <= MALE_ONLY_IDS | MALE_ONLY_SKIN and len(fit["male_only_dropped"]) >= 20
    assert fit["structures"] == rep["meshes"]
    assert fit["measured_on_her_mesh"] >= 150


def test_native_female_wording_replaces_each_template_anchor_once():
    from scripts.zanatomy.build_zan_atlas_viewer import NATIVE_FEMALE_WORDING, TEMPLATE_PATH, apply_vhf_wording
    html = apply_vhf_wording(TEMPLATE_PATH.read_text(encoding="utf-8"), NATIVE_FEMALE_WORDING)
    assert "<title>NMSK Atlas — Female base model</title>" in html
    assert "The source has no female body" in html and "fitted to any specimen" in html


def test_committed_native_female_report_is_unfitted_and_drops_male_only():
    """Q196: the unadapted female variant carries no fit and drops only male-only ids."""
    import json
    from scripts.transfer.zan_to_vhf_whole_body import MALE_ONLY_IDS
    from scripts.zanatomy.build_zan_atlas_viewer import MALE_ONLY_SKIN
    path = REPO_ROOT / "data" / "derived" / "Q196_zan_female_native_report.json"
    if not path.exists():
        pytest.skip("native female variant not built")
    rep = json.loads(path.read_text())
    assert "fit_to_vhf" not in rep and "trunk_refit" not in rep
    nf = rep["native_female"]
    assert nf["fitted_to_any_specimen"] is False
    assert len(nf["male_only_dropped"]) >= 20 and set(nf["male_only_dropped"]) <= MALE_ONLY_IDS | MALE_ONLY_SKIN
    assert nf["structures"] == rep["meshes"]


def test_atlas_records_ignore_derived_audit_rows():
    """Q204: data/derived/*.json audit rows ({"id": <structure id>, ...}) sort before data/muscles and used to shadow the real atlas record
    (card name = raw id, folder 'derived', no origin/insertion/nerve) on every page built after Q200."""
    from scripts.export_viewer_bundle import load_atlas_records
    rec = load_atlas_records().get("pronator_teres_l")
    assert rec is not None and rec[0] != "derived"
    assert rec[1].get("name_common") == "Pronator teres"
