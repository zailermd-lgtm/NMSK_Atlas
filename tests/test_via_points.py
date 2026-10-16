"""The via-point mechanism (Q138): a muscle's real path can now include one
or more via points between its origin and insertion (schema/muscle.
schema.json's attachments.via_points, emitted as `muscle_via_point` anchors
by scripts/generate_anchors.py), for the muscles whose real path is not one
straight chord -- semitendinosus wrapping the posteromedial tibial condyle
being the case this project's own straight-line moment-arm method had
already found itself 3-5mm short against a published 15-35mm range for.

These tests cover the MECHANISM (the tendon-excursion crossing-segment
decomposition in scripts/validate_moment_arms.py's own module docstring),
independent of any one muscle's real numbers, plus a regression check that
the real data this session added parses the way it is meant to.
"""
import json
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
DATA_DIR = REPO_ROOT / "data"

from scripts.validate_moment_arms import moment_arm, path_moment_arm  # noqa: E402

AXIS_POINT = np.array([0.0, 0.0, 0.0])
AXIS_DIR = np.array([1.0, 0.0, 0.0])


def _frame(origin):
    """A trivial identity-basis frame, exactly the shape build_frames() and
    place() expect: (origin, basis, how, which-axes, length-or-None)."""
    return (np.array(origin, float), np.eye(3), "synthetic", "both", None)


def test_path_moment_arm_matches_two_point_formula_with_no_via_points():
    """No via points: must reduce EXACTLY to the pre-Q138 straight-chord
    formula, since a muscle with no via_points is the overwhelming majority
    of this dataset and must be completely unaffected."""
    anchors_by_id = {
        ("m", "muscle_origin"): {"parent_bone_frame": "A", "local_position_mm": [10, 20, 0]},
        ("m", "muscle_insertion"): {"parent_bone_frame": "B", "local_position_mm": [-5, -30, 4]},
    }
    frames = {"A": _frame([0, 0, 0]), "B": _frame([0, 0, 0])}
    bones = {}
    r = path_moment_arm(anchors_by_id, {}, "m", frames, bones, AXIS_POINT, AXIS_DIR)
    a = np.array([10, 20, 0], float)
    b = np.array([-5, -30, 4], float)
    assert r == moment_arm(a, b, AXIS_POINT, AXIS_DIR)


def test_via_point_on_the_insertion_bone_uses_the_origin_to_via_segment():
    """The wrap case this was built for: origin on one bone, via point AND
    insertion both on the other. The via->insertion segment sits entirely
    within one rigid body and must contribute nothing -- the whole result
    must equal moment_arm(origin, via), not moment_arm(origin, insertion)."""
    anchors_by_id = {
        ("m", "muscle_origin"): {"parent_bone_frame": "A", "local_position_mm": [50, 20, 8]},
        ("m", "muscle_insertion"): {"parent_bone_frame": "B", "local_position_mm": [0, -40, 10]},
    }
    via = [{"parent_bone_frame": "B", "local_position_mm": [0, -10, -5], "sequence": 0}]
    frames = {"A": _frame([0, 0, 0]), "B": _frame([0, 0, 0])}
    bones = {}
    r = path_moment_arm(anchors_by_id, {"m": via}, "m", frames, bones, AXIS_POINT, AXIS_DIR)
    origin = np.array([50, 20, 8], float)
    via_pt = np.array([0, -10, -5], float)
    insertion = np.array([0, -40, 10], float)
    assert r == moment_arm(origin, via_pt, AXIS_POINT, AXIS_DIR)
    assert r != moment_arm(origin, insertion, AXIS_POINT, AXIS_DIR)


def test_missing_frame_returns_none_same_as_before():
    anchors_by_id = {
        ("m", "muscle_origin"): {"parent_bone_frame": "A", "local_position_mm": [1, 2, 3]},
        ("m", "muscle_insertion"): {"parent_bone_frame": "MISSING", "local_position_mm": [4, 5, 6]},
    }
    r = path_moment_arm(anchors_by_id, {}, "m", {"A": _frame([0, 0, 0])}, {}, AXIS_POINT, AXIS_DIR)
    assert r is None


def test_via_points_sequence_is_respected_not_insertion_order():
    """generate_anchors.py writes 'sequence' from the muscle's own
    via_points array order; path_moment_arm must walk the path in that
    order, not in whatever order the anchors happen to appear in the list,
    since two-or-more-via-point muscles (feasible for tibialis anterior /
    fibularis longus in the future) depend on it."""
    anchors_by_id = {
        ("m", "muscle_origin"): {"parent_bone_frame": "A", "local_position_mm": [10, 0, 0]},
        ("m", "muscle_insertion"): {"parent_bone_frame": "C", "local_position_mm": [0, 0, 10]},
    }
    # Deliberately out of order to prove sorting happens in validate_moment_arms.main(),
    # so build via_points_by_muscle pre-sorted here as main() would.
    via_unsorted = [
        {"parent_bone_frame": "B", "local_position_mm": [0, 5, 0], "sequence": 1},
        {"parent_bone_frame": "B", "local_position_mm": [0, -5, 0], "sequence": 0},
    ]
    via_sorted = sorted(via_unsorted, key=lambda a: a["sequence"])
    frames = {"A": _frame([0, 0, 0]), "B": _frame([0, 0, 0]), "C": _frame([0, 0, 0])}
    r = path_moment_arm(anchors_by_id, {"m": via_sorted}, "m", frames, {}, AXIS_POINT, AXIS_DIR)
    # segment0: origin(A) -> via_seq0(B) crosses; segment1: via_seq0(B) -> via_seq1(B) same frame, 0;
    # segment2: via_seq1(B) -> insertion(C) crosses.
    origin = np.array([10, 0, 0], float)
    via0 = np.array([0, -5, 0], float)
    via1 = np.array([0, 5, 0], float)
    insertion = np.array([0, 0, 10], float)
    expected = (moment_arm(origin, via0, AXIS_POINT, AXIS_DIR)
                + moment_arm(via1, insertion, AXIS_POINT, AXIS_DIR))
    assert abs(r - expected) < 1e-9


def test_semitendinosus_via_point_is_a_real_mesh_verified_tibia_landmark():
    """Regression check on the real data this session added: semitendinosus
    carries exactly one via point per side, on the tibia, at the SAME
    coordinate as tibia_{side}'s own already-audited 'posteromedial tibial
    condyle' landmark -- reused, not invented (see the muscle files' own
    notes)."""
    bones = {b["id"]: b for b in json.loads((DATA_DIR / "skeleton" / "bones.json").read_text())}
    for side in ("r", "l"):
        muscle = json.loads(
            (DATA_DIR / "muscles" / "lower_limb" / f"semitendinosus_{side}.json").read_text())
        via = muscle["attachments"]["via_points"]
        assert len(via) == 1
        assert via[0]["bone_frame"] == f"tibia_{side}"
        condyle = next(
            lm for lm in bones[f"tibia_{side}"]["landmarks"]
            if "posteromedial tibial condyle" in lm["name"])
        assert via[0]["position_local_mm"] == condyle["position_local_mm"]


def test_generate_anchors_emits_one_via_point_anchor_per_semitendinosus():
    """data/rig/anchors.json (regenerated by scripts/generate_anchors.py)
    must carry exactly one muscle_via_point anchor per semitendinosus side,
    on the tibia, in addition to its unaffected origin/insertion anchors."""
    anchors = json.loads((DATA_DIR / "rig" / "anchors.json").read_text())
    for side in ("r", "l"):
        muscle_id = f"semitendinosus_{side}"
        via = [a for a in anchors
               if a["owner_entity"] == muscle_id and a["anchor_type"] == "muscle_via_point"]
        assert len(via) == 1, f"{muscle_id}: expected exactly 1 via-point anchor, found {len(via)}"
        assert via[0]["parent_bone_frame"] == f"tibia_{side}"
        origin = [a for a in anchors
                  if a["owner_entity"] == muscle_id and a["anchor_type"] == "muscle_origin"]
        insertion = [a for a in anchors
                     if a["owner_entity"] == muscle_id and a["anchor_type"] == "muscle_insertion"]
        assert len(origin) == 1 and len(insertion) == 1
