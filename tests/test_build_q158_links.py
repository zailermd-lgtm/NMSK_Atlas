"""Q158: unit tests for scripts/zanatomy/build_q158_links.py's own deterministic
rules -- fast, no dependency on build/zanatomy or any real data file, so they
always run (unlike tests/test_build_zan_atlas_viewer.py's real-pipeline checks).
"""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.zanatomy.build_q158_links import (  # noqa: E402
    is_cns, local_tissue_category, muscle_head_or_part_match,
    numbered_series_match, resolve_grouped_or_ambiguous,
)
from scripts.zanatomy.map_names import build_cache, load_full_atlas  # noqa: E402


# --------------------------------------------------------------------------
# local_tissue_category / is_cns
# --------------------------------------------------------------------------

def test_tissue_category_reads_the_stated_tissue_word():
    assert local_tissue_category("Acromial part of deltoid muscle.l") == "muscle"
    assert local_tissue_category("Ulnar collateral ligament.r") == "ligament"
    assert local_tissue_category("Calcaneal tendon.l") == "tendon"
    assert local_tissue_category("Subcutaneous acromial bursa.l") == "bursa"
    assert local_tissue_category("Deep branch of radial nerve.r") == "nerve"
    assert local_tissue_category("Costal cartilage of first rib.l") == "cartilage"


def test_tissue_category_is_none_when_the_name_states_no_class():
    assert local_tissue_category("Psoas major.l") is None
    assert local_tissue_category("First rib.r") is None


def test_is_cns_flags_brain_and_special_sense_names():
    assert is_cns("Globus pallidus.l")
    assert is_cns("Cingulate gyrus (Posteroventral part*).l")
    assert is_cns("Retina.r")
    assert not is_cns("Median nerve.r")
    assert not is_cns("Deltoid muscle.l")


# --------------------------------------------------------------------------
# resolve_grouped_or_ambiguous: tissue-word tie-break, reused verbatim from
# map_names.py's own already-computed candidates.
# --------------------------------------------------------------------------

def _entry(name, status, candidates):
    return {"zanatomy_name": name, "status": status, "candidates": candidates}


def test_ambiguous_tie_broken_by_stated_tissue_word():
    entry = _entry("Acromial part of deltoid muscle.l", "ambiguous", [
        {"entity_id": "deltoid_l", "category": "muscle", "score": 0.8667},
        {"entity_id": "deltoid_ligament_l", "category": "ligament", "score": 0.8667},
    ])
    assert resolve_grouped_or_ambiguous(entry) == ("deltoid_l", "tissue_disambiguated_ambiguous")


def test_ambiguous_stays_unresolved_when_tissue_word_absent():
    # "Radial collateral ligament" states "ligament" so this case DOES resolve in
    # the real pipeline; here the fixture omits any tissue word from the name to
    # check the no-signal path stays unresolved rather than guessing.
    entry = _entry("Something.l", "ambiguous", [
        {"entity_id": "a_l", "category": "muscle", "score": 0.7},
        {"entity_id": "b_l", "category": "nerve", "score": 0.65},
    ])
    assert resolve_grouped_or_ambiguous(entry) is None


def test_ambiguous_low_scoring_noise_candidate_does_not_block_resolution():
    """A stray low-score same-tissue candidate (e.g. 'Helicis major' scoring 0.2
    against a real 0.9 pectoralis-major tie) must not make the tissue filter see
    2 survivors and give up -- only candidates within the classifier's own
    ambiguity margin (0.08) of the top score count as real contenders."""
    entry = _entry("Clavicular head of pectoralis major muscle.l", "ambiguous", [
        {"entity_id": "pectoralis_major_l", "category": "muscle", "score": 0.9},
        {"entity_id": "pectoralis_major_tendon_l", "category": "tendon", "score": 0.9},
        {"entity_id": "helicis_major_l", "category": "muscle", "score": 0.2},
    ])
    assert resolve_grouped_or_ambiguous(entry) == ("pectoralis_major_l", "tissue_disambiguated_ambiguous")


def test_grouped_wrong_tissue_single_candidate_is_rejected():
    """'Trapezoid ligament' groups (by name-substring containment) inside
    carpals_l's own name_ta list -- but carpals_l is a BONE entity and the
    Z-Anatomy name says 'ligament', so this single candidate must be rejected,
    not accepted just because it is the only one."""
    entry = _entry("Trapezoid ligament.l", "grouped", [
        {"entity_id": "carpals_l", "category": "bone", "score": 0.1111},
    ])
    assert resolve_grouped_or_ambiguous(entry) is None


def test_grouped_single_bone_candidate_accepted():
    entry = _entry("Scaphoid bone.l", "grouped", [
        {"entity_id": "carpals_l", "category": "bone", "score": 0.1111},
    ])
    assert resolve_grouped_or_ambiguous(entry) == ("carpals_l", "grouped_tissue_disambiguated")


def test_grouped_genuine_ambiguity_stays_unresolved():
    """'Collateral metacarpophalangeal ligaments' (plural, all digits) ties
    between two THUMB-only ligament ids with no generic all-digits entity --
    both survive the tissue filter (both are ligaments), so this must stay
    unresolved rather than guess one thumb-specific id."""
    entry = _entry("Collateral metacarpophalangeal ligaments.l", "grouped", [
        {"entity_id": "thumb_mcp_rcl_l", "category": "ligament", "score": 0.4},
        {"entity_id": "thumb_mcp_ucl_l", "category": "ligament", "score": 0.4},
    ])
    assert resolve_grouped_or_ambiguous(entry) is None


# --------------------------------------------------------------------------
# numbered_series_match: ribs / vertebrae / phalanges rolling up to this
# project's own coarse per-side/per-region group entities.
# --------------------------------------------------------------------------

def test_numbered_rib_maps_to_the_side_group():
    assert numbered_series_match("First rib", "right") == ("ribs_r", "numbered_series_rib")
    assert numbered_series_match("Twelfth rib", "left") == ("ribs_l", "numbered_series_rib")


def test_numbered_rib_without_a_resolved_side_is_declined():
    assert numbered_series_match("First rib", None) is None


def test_numbered_vertebra_maps_to_its_region_group():
    assert numbered_series_match("Vertebra C3", None) == ("cervical_vertebrae", "numbered_series_vertebra")
    assert numbered_series_match("Vertebra T9", None) == ("thoracic_vertebrae", "numbered_series_vertebra")
    assert numbered_series_match("Vertebra L2", None) == ("lumbar_vertebrae", "numbered_series_vertebra")


def test_phalanx_by_ordinal_digit_maps_to_hand_or_foot_group_regardless_of_digit():
    # the digit ordinal is irrelevant: this project's registry has no per-digit
    # phalanx id, only one group per hand/foot per side.
    assert numbered_series_match(
        "Proximal phalanx of fourth finger of hand", "left") == ("phalanges_hand_l", "numbered_series_phalanx")
    assert numbered_series_match(
        "Distal phalanx of first finger of foot", "right") == ("phalanges_foot_r", "numbered_series_phalanx")


def test_non_numbered_name_does_not_match_any_series_rule():
    assert numbered_series_match("Deltoid muscle", "left") is None
    assert numbered_series_match("Radiate ligament of head of rib", "right") is None


# --------------------------------------------------------------------------
# muscle_head_or_part_match: against the REAL atlas (small, in-repo JSON --
# not the gitignored Z-Anatomy build), reusing map_names.py's own cache.
# --------------------------------------------------------------------------

def _muscle_cache():
    atlas = load_full_atlas()
    return build_cache([e for e in atlas if e.category == "muscle"])


def test_muscle_head_or_part_extracts_the_stated_parent_muscle():
    cache = _muscle_cache()
    got = muscle_head_or_part_match("Long head of triceps brachii", "left", cache)
    assert got == ("triceps_brachii_l", "muscle_head_or_part")


def test_muscle_head_or_part_handles_trailing_muscle_word_and_parens():
    cache = _muscle_cache()
    got = muscle_head_or_part_match(
        "(Abdominal part of pectoralis major muscle)", "right", cache)
    assert got == ("pectoralis_major_r", "muscle_head_or_part")


def test_muscle_head_or_part_declines_when_parent_is_not_an_exact_muscle_name():
    cache = _muscle_cache()
    assert muscle_head_or_part_match("Some undefined part of nothing at all muscle", "left", cache) is None


def test_muscle_head_or_part_declines_a_name_with_no_head_or_part_phrasing():
    cache = _muscle_cache()
    assert muscle_head_or_part_match("Deltoid muscle", "left", cache) is None
