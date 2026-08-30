"""Tests for the Visible Human geometry ingest.

The dataset itself is ~355 GB and is not vendored, so these build small
synthetic STL files and exercise the reader, the name matcher, and the
coordinate transform against them.
"""
import json
import math
import struct
import sys
from pathlib import Path

import numpy as np
import json
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from engine import vh_ingest as vh  # noqa: E402


# --------------------------------------------------------------------------
# fixtures
# --------------------------------------------------------------------------

def _tetra(offset=(0.0, 0.0, 0.0)) -> np.ndarray:
    ox, oy, oz = offset
    v = np.array([
        [0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 2.0, 0.0], [0.0, 0.0, 3.0],
    ]) + np.array([ox, oy, oz])
    faces = [(0, 1, 2), (0, 1, 3), (0, 2, 3), (1, 2, 3)]
    return np.array([[v[a], v[b], v[c]] for a, b, c in faces])


def _write_binary_stl(path: Path, tris: np.ndarray) -> None:
    with path.open("wb") as fh:
        fh.write(b"test".ljust(80, b"\0"))
        fh.write(struct.pack("<I", len(tris)))
        for tri in tris.astype("<f4"):
            fh.write(struct.pack("<3f", 0, 0, 0))
            fh.write(tri.tobytes())
            fh.write(b"\0\0")


def _write_ascii_stl(path: Path, tris: np.ndarray) -> None:
    lines = ["solid t"]
    for tri in tris:
        lines.append(" facet normal 0 0 0\n  outer loop")
        lines += [f"   vertex {x:.6f} {y:.6f} {z:.6f}" for x, y, z in tri]
        lines.append("  endloop\n endfacet")
    lines.append("endsolid t")
    path.write_text("\n".join(lines))


# --------------------------------------------------------------------------
# STL reading
# --------------------------------------------------------------------------

def test_reads_binary_and_ascii_stl_identically(tmp_path):
    tris = _tetra()
    _write_binary_stl(tmp_path / "b.stl", tris)
    _write_ascii_stl(tmp_path / "a.stl", tris)
    binary = vh.read_stl(tmp_path / "b.stl")
    ascii_ = vh.read_stl(tmp_path / "a.stl")
    assert binary.shape == ascii_.shape == (4, 3, 3)
    np.testing.assert_allclose(binary, tris, atol=1e-5)
    np.testing.assert_allclose(ascii_, tris, atol=1e-5)


def test_ascii_stl_beginning_with_solid_is_not_misread_as_binary(tmp_path):
    """The 'starts with solid' heuristic is unreliable; size must decide."""
    path = tmp_path / "a.stl"
    _write_ascii_stl(path, _tetra())
    assert path.read_bytes()[:5] == b"solid"
    assert not vh._looks_binary_stl(path)


def test_truncated_binary_stl_is_rejected(tmp_path):
    path = tmp_path / "b.stl"
    _write_binary_stl(path, _tetra())
    path.write_bytes(path.read_bytes()[:-20])
    with pytest.raises(ValueError):
        vh.read_stl(path)


def test_weld_collapses_shared_vertices(tmp_path):
    tris = _tetra()
    verts, faces = vh.weld(tris)
    # A tetrahedron is 4 triangles x 3 corners = 12 loose vertices, 4 unique.
    assert tris.reshape(-1, 3).shape[0] == 12
    assert verts.shape == (4, 3)
    assert faces.shape == (4, 3)
    # Welding must not move any geometry.
    np.testing.assert_allclose(verts[faces], tris, atol=1e-4)


# --------------------------------------------------------------------------
# name handling
# --------------------------------------------------------------------------

@pytest.mark.parametrize("name,expect_base,expect_side", [
    ("Soleus_R", "Soleus", "right"),
    ("Soleus_L", "Soleus", "left"),
    ("Left_Gastrocnemius", "Gastrocnemius", "left"),
    ("vastus lateralis right", "vastus lateralis", "right"),
    ("Iliacus", "Iliacus", None),
    ("Sacrum", "Sacrum", None),
])
def test_split_side(name, expect_base, expect_side):
    base, side = vh.split_side(name)
    assert (base, side) == (expect_base, expect_side)


def test_split_side_does_not_eat_a_trailing_letter_of_a_word():
    """'Patella' ends in 'a', not a side marker; 'Pectoral' ends in 'l'."""
    assert vh.split_side("Patella") == ("Patella", None)
    assert vh.split_side("Pectoral") == ("Pectoral", None)


def test_normalise_handles_camel_case_and_synonyms():
    assert vh.normalise("VastusLateralis.stl") == "vastus lateralis"
    assert vh.normalise("PeroneusLongus") == "fibularis longus"
    assert vh.normalise("ACL") == "anterior cruciate"


def test_no_synonym_mangles_a_real_anatomical_word():
    """Regression: expanding 'long' -> 'longus' renamed the biceps femoris
    long head to a 'longus head'. Truncation expansions are banned."""
    assert vh.normalise("BicepsFemorisLongHead") == "biceps femoris long head"
    assert vh.normalise("Latissimus dorsi") == "latissimus dorsi"
    assert vh.normalise("Vastus medialis") == "vastus medialis"
    assert vh.normalise("Gluteus maximus") == "gluteus maximus"
    assert vh.normalise("Posterior tibial") == "posterior tibial"


def test_left_and_right_ids_do_not_normalise_to_the_same_string():
    """Regression: bare 'l'/'r' were once stopwords, which silently mapped
    right-side meshes onto left-side entities."""
    left = vh.normalise(vh._id_to_name("biceps_femoris_l_long_head"))
    right = vh.normalise(vh._id_to_name("biceps_femoris_r_long_head"))
    assert left == right == "biceps femoris long head"
    # The side is carried by AtlasEntity.side, not by the name -- so the
    # names matching is correct, and the side filter is what disambiguates.


def test_similarity_rewards_near_subsets_but_not_containment():
    close = vh.similarity("rectus femoris", "rectus femoris quadriceps")
    assert close > 0.8
    # 'talus' inside the seven-bone tarsal group is containment, not a match.
    far = vh.similarity("talus", "tarsal talus calcaneus navicular cuneiform cuboid")
    assert far < 0.5


# --------------------------------------------------------------------------
# atlas index and matching
# --------------------------------------------------------------------------

def test_atlas_index_excludes_functional_compartments():
    """Compartments have ids too, but geometry attaches to whole entities."""
    entities = vh.load_atlas_index()
    assert entities, "atlas index is empty"
    ids = {e.entity_id for e in entities}
    assert "adductor_brevis_l" in ids
    assert not any(i.endswith("_main") for i in ids), \
        "functional_compartment ids leaked into the entity index"


def test_matcher_never_crosses_sides():
    atlas = vh.load_atlas_index()
    for side, suffix in (("right", "_r"), ("left", "_l")):
        for candidate in vh.propose_matches("Adductor brevis", atlas, side=side):
            entity = next(e for e in atlas if e.entity_id == candidate.entity_id)
            assert entity.side in (None, side)
        best = vh.propose_matches("Adductor brevis", atlas, side=side)[0]
        assert best.entity_id.endswith(suffix)


def test_grouping_entity_found_for_a_component_bone():
    atlas = vh.load_atlas_index()
    for side, suffix in (("left", "_l"), ("right", "_r")):
        hits = vh.find_grouping_entity("Talus", atlas, side=side)
        assert hits, f"talus should be found inside the tarsal group ({side})"
        assert hits[0].entity_id == f"tarsals{suffix}"


def test_paired_bones_carry_matching_names():
    """Left and right of the same bone must describe the same anatomy, or
    the matcher resolves one side and silently fails the other."""
    entities = [e for e in vh.load_atlas_index(["bone"]) if e.side]
    by_base = {}
    for e in entities:
        base = e.entity_id[:-2] if e.entity_id.endswith(("_l", "_r")) else e.entity_id
        by_base.setdefault(base, {})[e.side] = e
    mismatched = []
    for base, sides in by_base.items():
        if "left" not in sides or "right" not in sides:
            continue
        if base == "ribs":
            continue  # legitimately side-specific: costae sinistra vs dextra
        left, right = sides["left"], sides["right"]
        if len(left.names[1]) != len(right.names[1]) and \
                abs(len(left.names[1]) - len(right.names[1])) > 4:
            mismatched.append(f"{base}: {left.names[1]!r} vs {right.names[1]!r}")
    assert not mismatched, "left/right names disagree:\n" + "\n".join(mismatched)


# --------------------------------------------------------------------------
# coordinate frame
# --------------------------------------------------------------------------

def test_parse_axes_identity():
    np.testing.assert_array_equal(vh.parse_axes("+x,+y,+z"), np.eye(3))


def test_parse_axes_swaps_and_flips():
    """'+x,+z,-y' means: atlas Y takes source z, atlas Z takes source -y."""
    axes = vh.parse_axes("+x,+z,-y")
    out = vh.to_atlas_frame(np.array([[1.0, 2.0, 3.0]]), axes, 1.0)
    np.testing.assert_allclose(out, [[1.0, 3.0, -2.0]])


@pytest.mark.parametrize("spec", ["+x,+x,+z", "x,y", "+a,+b,+c", ""])
def test_parse_axes_rejects_bad_specs(spec):
    with pytest.raises(ValueError):
        vh.parse_axes(spec)


def test_axis_permutations_preserve_lengths():
    """Any signed permutation is a rotation/reflection: distances survive."""
    rng = np.random.default_rng(0)
    pts = rng.normal(size=(50, 3)) * 100
    for spec in ("+x,+y,+z", "+x,+z,-y", "-z,+y,+x", "-y,-x,-z"):
        out = vh.to_atlas_frame(pts, vh.parse_axes(spec), 1.0)
        np.testing.assert_allclose(
            np.linalg.norm(out, axis=1), np.linalg.norm(pts, axis=1), atol=1e-9)


def test_unit_scaling():
    axes = vh.parse_axes("+x,+y,+z")
    metres = np.array([[0.0, 0.43, 0.0]])
    out = vh.to_atlas_frame(metres, axes, vh.UNIT_SCALE_TO_MM["m"])
    np.testing.assert_allclose(out, [[0.0, 430.0, 0.0]])


@pytest.mark.parametrize("units,scale", [("mm", 1.0), ("cm", 0.1), ("m", 0.001)])
def test_infer_frame_guesses_units_from_magnitude(units, scale):
    lo = np.array([-100.0, 0.0, -50.0]) * scale
    hi = np.array([100.0, 900.0, 50.0]) * scale
    report = vh.infer_frame(lo, hi)
    assert report.guessed_units == units
    assert report.longest_axis == 1


def test_infer_frame_flags_implausible_extents():
    report = vh.infer_frame(np.zeros(3), np.array([1e-9, 2e-9, 3e-9]))
    assert report.guessed_units is None
    assert any("not a plausible" in n for n in report.notes)


# --------------------------------------------------------------------------
# Regressions found by running against the real DU release
#
# Everything below reproduces a bug that only appeared once actual
# VHM_Right_*_smooth.stl filenames were available. The module was written
# without the dataset in hand and guessed the convention; these are the
# places the guess was wrong.
# --------------------------------------------------------------------------

def _atlas_stub():
    """Minimal atlas covering the entities the regressions turn on."""
    return [
        vh.AtlasEntity("achilles_tendon_r", "tendon", "right",
                       ("Achilles tendon", "Tendo calcaneus"), "t.json"),
        vh.AtlasEntity("tarsals_r", "bone", "right",
                       ("Tarsal bones (7)",
                        "Ossa tarsi (talus, calcaneus, naviculare, "
                        "cuneiforme x3, cuboideum)"), "b.json"),
        vh.AtlasEntity("femur_r", "bone", "right",
                       ("Femur (thigh bone)", "Os femoris"), "b.json"),
        vh.AtlasEntity("knee_articular_cartilage_r", "cartilage", "right",
                       ("Knee articular cartilage",), "c.json"),
    ]


def test_dataset_tokens_do_not_dilute_the_score():
    """Subject and processing-variant tokens are file metadata, not anatomy.

    'VHM ... smooth' left two junk tokens in every single name. Against the
    real release that was enough to drive an otherwise exact match to 0.
    """
    assert vh.normalise("VHM_Bone_Femur_smooth.stl") == "femur"
    assert vh.normalise("VHF_Muscle_Soleus_original") == "soleus"


def test_source_misspellings_are_corrected():
    """Spellings observed in the release itself, not guessed abbreviations."""
    assert vh.normalise("Bone_Calcaneous") == "calcaneus"
    assert vh.normalise("Muscle_Illiacus") == "iliacus"
    assert vh.normalise("Muscle_QuadratisFemoris") == "quadratus femoris"


def test_tissue_class_is_read_from_the_name():
    assert vh.tissue_category("VHM_Right_Bone_Calcaneous_smooth.stl") == "bone"
    assert vh.tissue_category("VHM_Right_Cartilage_FemurDistal_smooth") == "cartilage"
    assert vh.tissue_category("Right_Muscle_Soleus") == "muscle"
    # A name that states no tissue class must not be forced into one, or
    # datasets that do not encode it would match nothing at all.
    assert vh.tissue_category("Soleus_R.stl") is None


def test_bone_does_not_match_a_tendon_however_well_the_words_line_up():
    """The calcaneus bone scored 0.90 against achilles_tendon_r and was
    written out as 'confident', because the Achilles is also the calcaneal
    tendon. Tissue class disqualifies it the way a side marker would."""
    atlas = _atlas_stub()
    name, side = vh.split_side("VHM_Right_Bone_Calcaneous_smooth.stl")

    unconstrained = vh.propose_matches(name, atlas, side=side, category="tendon")
    assert unconstrained and unconstrained[0].entity_id == "achilles_tendon_r", (
        "the tempting wrong match must still exist -- otherwise this test "
        "would pass for the wrong reason")

    got = vh.propose_matches(name, atlas, side=side)
    assert all(c.category == "bone" for c in got)
    assert "achilles_tendon_r" not in {c.entity_id for c in got}


def test_cartilage_does_not_collide_with_its_bone():
    """Cartilage_FemurDistal matched femur_r, which then collided with the
    real femur mesh and dragged both into 'grouped'."""
    atlas = _atlas_stub()
    got = vh.propose_matches("VHM_Cartilage_FemurDistal_smooth", atlas, side="right")
    assert "femur_r" not in {c.entity_id for c in got}


def test_grouping_also_respects_tissue_class():
    atlas = _atlas_stub()
    hits = vh.find_grouping_entity("VHM_Bone_Calcaneous_smooth", atlas, side="right")
    assert {h.entity_id for h in hits} == {"tarsals_r"}


# --------------------------------------------------------------------------
# Curated overrides
# --------------------------------------------------------------------------

def test_override_key_separates_bone_from_cartilage():
    """The release ships Bone_Patella and Cartilage_Patella, which normalise
    identically once the class token is dropped. The key must not collide."""
    assert vh.override_key("VHM_Right_Bone_Patella_smooth.stl") == "bone|patella"
    assert (vh.override_key("VHM_Right_Cartilage_Patella_smooth.stl")
            == "cartilage|patella")


def test_override_key_is_none_without_a_tissue_class():
    assert vh.override_key("Soleus_R.stl") is None


def test_shipped_overrides_load_and_target_real_entities():
    """Every curated override must name an entity that actually exists, or it
    is a silent no-op that looks like a decision."""
    overrides = vh.load_overrides()
    assert overrides, "the shipped override table should not be empty"
    ids = {e.entity_id for e in vh.load_atlas_index()}
    for key, entry in overrides.items():
        resolved = vh.apply_override(entry, "right")
        assert resolved["atlas_id"] in ids, f"{key} -> {resolved['atlas_id']}"
        assert entry.get("note"), f"{key} has no recorded reason"
        assert entry["relationship"] in {"exact", "part_of", "compartment"}


def test_override_side_placeholder_resolves_both_ways():
    entry = {"match": "bone|talus", "atlas_id": "tarsals_{side}",
             "relationship": "part_of", "note": "x"}
    assert vh.apply_override(entry, "right")["atlas_id"] == "tarsals_r"
    assert vh.apply_override(entry, "left")["atlas_id"] == "tarsals_l"


def test_override_refuses_to_guess_a_missing_side():
    """A sided template with no side marker would produce a broken ID."""
    entry = {"match": "bone|talus", "atlas_id": "tarsals_{side}",
             "relationship": "part_of", "note": "x"}
    with pytest.raises(ValueError, match="side"):
        vh.apply_override(entry, None)


def test_compartment_overrides_name_a_real_compartment():
    """A compartment override that points at a compartment the atlas does not
    have would attach geometry to nothing."""
    import json as _json
    overrides = vh.load_overrides()
    known = set()
    for path in (vh.DATA_DIR / "muscles").rglob("*.json"):
        if path.name == "muscle_index.json":
            continue
        payload = _json.loads(path.read_text())
        for muscle in (payload if isinstance(payload, list) else [payload]):
            if not isinstance(muscle, dict):
                continue
            for comp in muscle.get("functional_compartments", []):
                known.add(comp.get("id"))
    checked = 0
    for key, entry in overrides.items():
        if entry["relationship"] != "compartment":
            continue
        resolved = vh.apply_override(entry, "right")
        assert resolved["compartment_id"] in known, (
            f"{key} -> {resolved['compartment_id']}")
        checked += 1
    assert checked, "expected at least one compartment override to check"


# --------------------------------------------------------------------------
# Origin recovery
# --------------------------------------------------------------------------

def test_fit_sphere_recovers_a_known_sphere():
    rng = np.random.default_rng(7)
    unit = rng.normal(size=(3000, 3))
    unit /= np.linalg.norm(unit, axis=1, keepdims=True)
    truth, radius = np.array([10.0, -20.0, 30.0]), 24.5
    centre, got_r, rms = vh.fit_sphere(unit * radius + truth)
    np.testing.assert_allclose(centre, truth, atol=1e-6)
    assert abs(got_r - radius) < 1e-6
    assert rms < 1e-6


def test_fit_sphere_works_on_a_partial_cap():
    """A femoral head mesh is a cap, not a whole sphere, and the centroid of a
    cap is nowhere near its centre -- which is exactly why this fits rather
    than averages."""
    rng = np.random.default_rng(11)
    unit = rng.normal(size=(6000, 3))
    unit /= np.linalg.norm(unit, axis=1, keepdims=True)
    cap = unit[unit[:, 2] > 0.3]
    truth, radius = np.array([5.0, 5.0, 5.0]), 25.0
    points = cap * radius + truth
    centre, got_r, _ = vh.fit_sphere(points)
    np.testing.assert_allclose(centre, truth, atol=1e-6)
    assert np.linalg.norm(points.mean(axis=0) - truth) > 5.0, (
        "the centroid must actually be far from the centre, or this test "
        "would pass even for a naive mean")


def test_fit_sphere_rms_flags_a_non_spherical_mesh():
    rng = np.random.default_rng(3)
    slab = rng.uniform(-30, 30, size=(2000, 3))
    slab[:, 2] *= 0.02
    _, _, rms = vh.fit_sphere(slab)
    assert rms > 1.5, "a flat slab must not pass as a femoral head"


def test_parse_origin_round_trip():
    np.testing.assert_allclose(
        vh.parse_origin("-346.042, 176.42,425.42"), [-346.042, 176.42, 425.42])


@pytest.mark.parametrize("bad", ["1,2", "1,2,3,4", "a,b,c", ""])
def test_parse_origin_rejects_malformed(bad):
    with pytest.raises(ValueError):
        vh.parse_origin(bad)


def test_origin_translation_happens_before_rotation():
    """--origin is quoted in source units, as inspect prints it, so the
    subtraction has to precede the axis permutation."""
    axes = vh.parse_axes("-x,-z,+y")
    origin = np.array([346.042, 176.42, 425.42])
    moved = vh.to_atlas_frame((origin - origin).reshape(1, 3), axes, 1.0)
    np.testing.assert_allclose(moved, [[0.0, 0.0, 0.0]], atol=1e-12)


# --------------------------------------------------------------------------
# Regressions found by running against the LEFT side as well
#
# The two sides of the release are not spelled consistently with each other,
# and the left folder carries the midline bones. Neither was visible from the
# right side alone.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("left,right", [
    ("Muscle_ExtensorHallicusLongus", "Muscle_ExtensorHallucisLongus"),
    ("Muscle_FlexorHallicusLongus", "Muscle_FlexorHallucisLongus"),
    ("Muscle_Semitendonosus", "Muscle_Semitendinosus"),
    ("Muscle_QuadratusFemoris", "Muscle_QuadratisFemoris"),
])
def test_the_two_sides_normalise_to_the_same_string(left, right):
    """A mapping made against one side has to apply to the other."""
    assert vh.normalise(left) == vh.normalise(right)


def test_extensor_hallucis_is_not_extensor_digitorum():
    """The left spelling scored 0.50 against extensor digitorum longus -- just
    under the 0.55 threshold. Once corrected it must match its own muscle
    outright, not squeak past a near neighbour."""
    atlas = [
        vh.AtlasEntity("extensor_hallucis_longus_l", "muscle", "left",
                       ("Extensor hallucis longus",), "m.json"),
        vh.AtlasEntity("extensor_digitorum_longus_l", "muscle", "left",
                       ("Extensor digitorum longus",), "m.json"),
    ]
    name, side = vh.resolve_side("VHM_Left_Muscle_ExtensorHallicusLongus_smooth.stl")
    got = vh.propose_matches(name, atlas, side=side)
    assert got[0].entity_id == "extensor_hallucis_longus_l"
    assert got[0].score >= vh.EXACT


@pytest.mark.parametrize("name", [
    "VHM_Left_Bone_Sacrum_smooth.stl",
    "VHM_Left_Bone_Coccyx_smooth.stl",
])
def test_midline_bones_do_not_inherit_the_folder_side(name):
    """The release files the sacrum and coccyx under Left. They are midline
    bones, and stamping side='left' on them would carry a falsehood into
    every manifest downstream."""
    _, side = vh.resolve_side(name)
    assert side is None


def test_resolve_side_still_reads_a_real_side():
    assert vh.resolve_side("VHM_Left_Bone_Femur_smooth.stl")[1] == "left"
    assert vh.resolve_side("VHM_Right_Bone_Femur_smooth.stl")[1] == "right"


def test_left_spellings_have_their_own_override_entries():
    """'longus' cannot be normalised to 'long' -- that would corrupt adductor
    longus and every other longus -- so the left spelling needs its own key."""
    overrides = vh.load_overrides()
    for key in ("muscle|biceps femoris long", "muscle|biceps femoris longus",
                "cartilage|tibial medial", "cartilage|tibia medial"):
        assert key in overrides, key
    assert (vh.apply_override(overrides["muscle|biceps femoris longus"], "left")
            ["compartment_id"] == "biceps_femoris_l_long_head")


# --------------------------------------------------------------------------
# Regression: the side marker appearing twice in one path
#
# Found on a real download, stored as .../Left/VHM_Left_Bone_Sacrum.stl, so
# the folder and the filename each carry the side. Removing only the first
# left "left" behind as an anatomical token.
# --------------------------------------------------------------------------

def test_duplicated_side_marker_is_fully_stripped():
    base, side = vh.split_side("Left VHM_Left_Bone_Sacrum_smooth")
    assert side == "left"
    assert vh.normalise(base) == "sacrum", (
        "a residual side token makes this 'left sacrum', which is not a "
        "midline structure and not the atlas's 'sacrum' either")


def test_duplicated_side_marker_restores_the_exact_match():
    """The extra token dropped extensor digitorum longus from 1.00 to 0.95 --
    below the exact-match rule and inside the ambiguity margin of extensor
    digitorum, a different muscle. It became unmappable."""
    atlas = [
        vh.AtlasEntity("extensor_digitorum_longus_l", "muscle", "left",
                       ("Extensor digitorum longus",), "m.json"),
        vh.AtlasEntity("extensor_digitorum_l", "muscle", "left",
                       ("Extensor digitorum",), "m.json"),
    ]
    name, side = vh.resolve_side(
        "Left VHM_Left_Muscle_ExtensorDigitorumLongus_smooth.stl")
    got = vh.propose_matches(name, atlas, side=side)
    assert got[0].entity_id == "extensor_digitorum_longus_l"
    assert got[0].score >= vh.EXACT, (
        f"expected an exact match, got {got[0].score}")


def test_nested_layout_finds_midline_bones():
    for name in ("Left VHM_Left_Bone_Sacrum_smooth.stl",
                 "Left VHM_Left_Bone_Coccyx_smooth.stl"):
        assert vh.resolve_side(name)[1] is None


def test_a_name_claiming_both_sides_is_not_guessed():
    """`Left/..._Right_...` is a contradiction. Believing half of it silently
    is exactly the error class this module exists to prevent."""
    assert vh.side_markers("Left VHM_Right_Bone_Femur") == {"left", "right"}
    assert vh.split_side("Left VHM_Right_Bone_Femur")[1] is None


def test_single_letter_markers_still_need_delimiters():
    assert vh.split_side("Soleus_L")[1] == "left"
    assert vh.split_side("Iliacus")[1] is None
    assert vh.split_side("Left Soleus_L")[1] == "left"


# --------------------------------------------------------------------------
# Geometry audit
# --------------------------------------------------------------------------

def test_mesh_volume_matches_an_analytic_sphere():
    """The whole volume audit rests on this being right, so it is tested
    against a shape whose volume is known in closed form."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "audit", Path(__file__).resolve().parent.parent
        / "scripts" / "audit_geometry_vs_atlas.py")
    audit = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(audit)

    # icosahedron subdivided to a near-sphere
    t = (1 + 5 ** 0.5) / 2
    v = np.array([[-1, t, 0], [1, t, 0], [-1, -t, 0], [1, -t, 0],
                  [0, -1, t], [0, 1, t], [0, -1, -t], [0, 1, -t],
                  [t, 0, -1], [t, 0, 1], [-t, 0, -1], [-t, 0, 1]], float)
    f = np.array([[0, 11, 5], [0, 5, 1], [0, 1, 7], [0, 7, 10], [0, 10, 11],
                  [1, 5, 9], [5, 11, 4], [11, 10, 2], [10, 7, 6], [7, 1, 8],
                  [3, 9, 4], [3, 4, 2], [3, 2, 6], [3, 6, 8], [3, 8, 9],
                  [4, 9, 5], [2, 4, 11], [6, 2, 10], [8, 6, 7], [9, 8, 1]])
    for _ in range(4):
        cache, vl, nf = {}, list(v), []
        def mid(a, b):
            key = (min(a, b), max(a, b))
            if key not in cache:
                cache[key] = len(vl)
                vl.append((vl[a] + vl[b]) / 2)
            return cache[key]
        for a, b, c in f:
            ab, bc, ca = mid(a, b), mid(b, c), mid(c, a)
            nf += [[a, ab, ca], [b, bc, ab], [c, ca, bc], [ab, bc, ca]]
        v, f = np.array(vl), np.array(nf)
    r = 30.0
    v = v / np.linalg.norm(v, axis=1, keepdims=True) * r

    assert audit.is_closed(f)
    got = audit.mesh_volume_mm3(v, f)
    exact = 4 / 3 * np.pi * r ** 3
    assert abs(got / exact - 1) < 0.005

    # The divergence theorem is translation invariant; the converted geometry
    # sits nowhere near the origin, so this must hold far from it.
    moved = audit.mesh_volume_mm3(v + np.array([500.0, -900.0, 300.0]), f)
    assert abs(moved - got) < 1e-6

    # An open surface must be rejected rather than given a plausible number.
    assert not audit.is_closed(f[:-1])


def test_anchor_generator_refuses_a_displaced_landmark():
    """"below soleal line" names the soleal line in order to say the origin is
    NOT there. A plain substring match read that as a hit and anchored flexor
    digitorum longus exactly on it, 46-55 mm from its own muscle in the
    Visible Human geometry. A wrong coordinate is worse than a missing one:
    nobody questions it."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "genanchors", Path(__file__).resolve().parent.parent
        / "scripts" / "generate_anchors.py")
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)

    candidates = [("soleal line (soleus, popliteus, tibialis posterior origin)",
                   [-6.1, -60, -4.6])]

    pos, skipped = gen._match("posterior tibia (medial, below soleal line)",
                              candidates)
    assert pos is None and skipped and "below" in skipped

    pos, skipped = gen._match("above the soleal line", candidates)
    assert pos is None and "above" in skipped

    # An unqualified mention must still match, or the guard would break every
    # attachment that legitimately sits on its landmark.
    pos, skipped = gen._match("soleal line of the tibia", candidates)
    assert pos == [-6.1, -60, -4.6] and skipped is None


def test_a_hole_is_not_a_surface_feature():
    """The obturator foramen is a hole roughly 35x45 mm. A landmark at its
    centre is CORRECTLY about 20 mm from any bone, and the audit was scoring
    that as the second-worst error in the set. Landmarks of kind
    'foramen_or_canal' are excluded from the distance-to-surface check for
    the same reason a landmark at the frame's own origin is."""
    bones = json.loads((vh.DATA_DIR / "skeleton" / "bones.json").read_text())
    hip = next(b for b in bones if b["id"] == "hip_bone_r")
    kinds = {lm["name"]: lm.get("kind") for lm in hip["landmarks"]}
    assert any(k == "foramen_or_canal" for k in kinds.values()), (
        "this test is meaningless if no landmark is marked as a hole")
    foramen = [n for n, k in kinds.items() if k == "foramen_or_canal"]
    assert any(n.startswith("obturator foramen") for n in foramen)


def _gen():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "genanchors", Path(__file__).resolve().parent.parent
        / "scripts" / "generate_anchors.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_landmark_tokens_ignore_punctuation():
    """A landmark named "greater trochanter, lateral facet (...)" produced the
    token "trochanter," -- with the comma -- under the old tokeniser, which
    matches nothing. Every trochanteric facet added silently failed to match
    and the muscles kept resolving to the old catch-all point."""
    gen = _gen()
    assert "trochanter" in gen._tokens("greater trochanter, lateral facet")
    assert not any("," in t for t in
                   gen._tokens("greater trochanter, lateral facet (x)"))


def test_most_specific_landmark_wins():
    """Seven muscles attach to different facets of the greater trochanter.
    Matching on the first two tokens alone made them indistinguishable."""
    gen = _gen()
    candidates = [
        ("greater trochanter (gluteus medius/minimus, piriformis, obturator "
         "internus insertion)", [63.7, -20, -18.1]),
        ("greater trochanter, superior border (piriformis insertion)",
         [18.1, 14.9, 1.2]),
    ]
    pos, skipped = gen._match("greater trochanter (superior border)", candidates)
    assert pos == [18.1, 14.9, 1.2] and skipped is None


def test_raw_count_beats_fraction_for_a_long_landmark_name():
    """Scoring by fraction first sent obturator internus to the LESSER
    trochanter, 60 mm from its own facet, because its facet's name lists
    every muscle attaching there and so scores a poor fraction."""
    gen = _gen()
    candidates = [
        ("lesser trochanter (iliopsoas insertion)", [10, -45, -15]),
        ("greater trochanter, medial surface and trochanteric fossa "
         "(obturator internus, gemelli, obturator externus insertion)",
         [23.2, -47.1, -32.1]),
    ]
    pos, _ = gen._match(
        "greater trochanter (medial surface, via lesser sciatic notch)",
        candidates)
    assert pos == [23.2, -47.1, -32.1]


def test_an_equal_match_is_refused_not_guessed():
    gen = _gen()
    candidates = [("linea aspera", [1, 2, 3]), ("adductor tubercle", [4, 5, 6])]
    pos, skipped = gen._match("linea aspera and adductor tubercle",
                              candidates)
    assert pos is None and "equally" in skipped
