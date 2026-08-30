from engine import validators


def test_bilateral_entities_have_mirror_counterparts():
    problems = validators.validate_symmetry()
    assert not problems, "\n".join(problems)


import json  # noqa: E402
import re  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402

BONES = (Path(__file__).resolve().parent.parent
         / "data" / "skeleton" / "bones.json")


def _side_claimed(name: str):
    """Which side a landmark's own name states, when it states one about the
    landmark AS A WHOLE.

    The qualifier only counts as the FIRST word or inside parentheses. Both
    of those describe the landmark itself -- "medial epicondyle", "acromial
    (lateral) end". A side word further into the name usually qualifies a
    SURFACE of a feature that sits on the other side: the greater trochanter's
    medial surface and trochanteric fossa is a medial-facing part of the most
    LATERAL prominence of the femur, and reading it as a medial landmark
    would flag a coordinate measured off the geometry as an error.
    """
    low = name.lower()
    scope = (low.split() or [""])[0] + " " + " ".join(re.findall(r"\(([^)]*)\)", low))
    medial, lateral = "medial" in scope, "lateral" in scope
    if medial == lateral:
        return None
    return "medial" if medial else "lateral"


def _contradictions(bones):
    """Landmarks whose x sign contradicts the side their name states."""
    bad = []
    for bone in bones:
        bone_id = bone.get("id", "")
        if not bone_id.endswith(("_r", "_l")):
            continue
        # +x is the subject's right, so medial is toward -x on the right limb
        # and toward +x on the left.
        outward = 1.0 if bone_id.endswith("_r") else -1.0
        for lm in bone.get("landmarks", []):
            pos = lm.get("position_local_mm")
            side = _side_claimed(lm["name"]) if pos else None
            if not side:
                continue
            want = -outward if side == "medial" else outward
            if pos[0] * want < 0:
                bad.append(f"{bone_id} {lm['name']!r}: names {side} but x={pos[0]}")
    return bad


def test_landmarks_named_medial_or_lateral_are_on_that_side():
    """A cheap net for mediolateral inversion on bones with no geometry.

    The whole clavicle was stored mirrored on both sides: the right acromial
    end sat at x=-150, putting the acromioclavicular joint 300 mm from where
    it belongs with the scapula, humerus and the rest of the upper limb
    hanging off it. Nothing caught it, because the geometry audit can only
    check the lower limb and every other check is a distance, which a mirror
    leaves unchanged.
    """
    bones = json.loads(BONES.read_text())
    assert not _contradictions(bones), "\n".join(_contradictions(bones))


def test_the_mediolateral_check_actually_catches_a_mirror():
    """Verify the check by breaking the data it is meant to protect."""
    bones = json.loads(BONES.read_text())
    victim = next(lm for b in bones if b.get("id") == "clavicle_r"
                  for lm in b.get("landmarks", [])
                  if lm["name"].startswith("acromial"))
    victim["position_local_mm"][0] *= -1
    bad = _contradictions(bones)
    assert any("clavicle_r" in b for b in bad), bad


def test_a_medial_surface_of_a_lateral_feature_is_not_flagged():
    """The trochanteric fossa is a medial-facing part of the femur's most
    LATERAL prominence, and its coordinate was measured off the geometry.
    A rule that read the word 'medial' anywhere would call it an error."""
    assert _side_claimed(
        "greater trochanter medial surface and trochanteric fossa "
        "(obturator internus, gemelli, obturator externus insertion)") is None
    assert _side_claimed("medial epicondyle") == "medial"
    assert _side_claimed("acromial (lateral) end") == "lateral"
