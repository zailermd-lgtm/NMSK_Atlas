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
