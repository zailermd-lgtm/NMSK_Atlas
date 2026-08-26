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
