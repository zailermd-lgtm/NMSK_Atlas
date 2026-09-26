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
        budget_scale=0.02,
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
    assert set(corrected_ids) == {"posterior_interosseous_n_l", "posterior_interosseous_n_r"}
    by_id = {m["id"]: m for m in manifest["meshes"]}
    for aid in corrected_ids:
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
