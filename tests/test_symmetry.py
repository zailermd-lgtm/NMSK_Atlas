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

    "medial surface" and "lateral surface" are excluded for the same reason
    even when they lead, because which way a surface FACES says nothing about
    where it sits: the medial surfaces of the third to fifth metatarsals are
    lateral of the metatarsal frame's origin.
    """
    low = re.sub(r"\b(medial|lateral)\s+surfaces?\b", " ", name.lower())
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


# --------------------------------------------------------------------------
# laterality in the nerve and vessel graphs
# --------------------------------------------------------------------------

_SIDE_TOKEN = re.compile(r"_(r|l)(?=_|$)")
_LIST_REFS = ("targets", "supplies_or_drains", "anastomoses_with",
              "root_contributions")


def _mirror(ref: str) -> str:
    return _SIDE_TOKEN.sub(lambda m: "_l" if m.group(1) == "r" else "_r",
                           ref, count=1)


def _tree_records():
    for folder in ("nerves", "vascular"):
        for path in sorted((BONES.parent.parent / folder).glob("*.json")):
            payload = json.loads(path.read_text())
            for rec in (payload if isinstance(payload, list) else [payload]):
                if isinstance(rec, dict) and "id" in rec:
                    yield path.name, rec


def _one_sided_targets(records):
    """Side-agnostic entities whose sided references name only one side."""
    bad = []
    for filename, rec in records:
        if _SIDE_TOKEN.search(rec["id"]):
            continue
        for field in _LIST_REFS:
            refs = rec.get(field) or []
            for ref in refs:
                # Free text is legitimate in `targets` -- the schema says it
                # holds "muscle compartment ids and/or skin dermatome
                # regions" -- so only entries carrying a side token are ids.
                if isinstance(ref, str) and _SIDE_TOKEN.search(ref):
                    if _mirror(ref) not in refs:
                        bad.append(f"{filename}: {rec['id']}.{field} has "
                                   f"{ref!r} but not {_mirror(ref)!r}")
    return bad


def _crossed_sides(records):
    """Sided entities whose sided references name the OTHER side."""
    bad = []
    for filename, rec in records:
        own = _SIDE_TOKEN.search(rec["id"])
        if not own:
            continue
        for field in _LIST_REFS:
            for ref in rec.get(field) or []:
                if not isinstance(ref, str):
                    continue
                hit = _SIDE_TOKEN.search(ref)
                if hit and hit.group(1) != own.group(1):
                    bad.append(f"{filename}: {rec['id']} is _{own.group(1)} "
                               f"but {field} names {ref!r}")
    return bad


def test_a_side_agnostic_nerve_reaches_both_sides():
    """Nerve ids are side-agnostic by convention -- 393 of 404 muscles cite an
    unsided nerve -- so one entity stands for the left nerve and the right.
    Its targets once did not: 359 references to right-side compartments and
    ZERO to the left, which made the graph complete in one direction and half
    empty in the other. That is worse than being visibly incomplete in both,
    because "what does the axillary nerve supply?" answered confidently with
    half the body."""
    assert not _one_sided_targets(_tree_records()), \
        "\n".join(_one_sided_targets(_tree_records())[:20])


def test_a_sided_nerve_does_not_supply_the_other_side():
    """The left recurrent laryngeal nerve had been given the RIGHT laryngeal
    compartments -- all five of them -- so it appeared to supply the right
    larynx while nothing reached the left."""
    assert not _crossed_sides(_tree_records()), \
        "\n".join(_crossed_sides(_tree_records())[:20])


def test_both_laterality_checks_catch_the_faults_they_are_for():
    """Verified by feeding each check the fault it exists to catch."""
    half = [("x.json", {"id": "axillary_n",
                        "targets": ["deltoid_r_anterior"]})]
    assert _one_sided_targets(half), "a one-sided target list went unnoticed"
    assert not _crossed_sides(half), "an unsided entity cannot cross sides"

    crossed = [("x.json", {"id": "vagus_n_recurrent_laryngeal_branch_l",
                           "targets": ["vocalis_r_main"]})]
    assert _crossed_sides(crossed), "a nerve supplying the other side went unnoticed"

    # A midline muscle is not sided and must not be demanded in pairs.
    midline = [("x.json", {"id": "some_n", "targets": ["transverse_arytenoid_main"]})]
    assert not _one_sided_targets(midline)
    # Nor is free text an id to be mirrored.
    prose = [("x.json", {"id": "some_n",
                         "targets": ["laryngeal mucosa below the vocal folds"]})]
    assert not _one_sided_targets(prose)


# Vessels that exist on one side only. Anatomy, not a gap -- and the reason
# has to be stated, or this list becomes a place to hide missing data.
UNILATERAL_VESSELS = {
    "brachiocephalic_trunk_r":
        "arises from the aortic arch and divides into the right common "
        "carotid and right subclavian; on the left those two come off the "
        "arch directly, so there is no left brachiocephalic trunk",
}


def _vessels_without_a_counterpart(ids):
    return sorted(i for i in ids
                  if _SIDE_TOKEN.search(i)
                  and _mirror(i) not in ids
                  and i not in UNILATERAL_VESSELS)


def _vessel_ids():
    out = set()
    for path in sorted((BONES.parent.parent / "vascular").glob("*.json")):
        for rec in json.loads(path.read_text()):
            if isinstance(rec, dict) and "id" in rec:
                out.add(rec["id"])
    return out


def test_every_sided_vessel_has_its_other_side():
    """The left arm, the left leg and the left side of the neck had no
    arteries and no veins at all: 129 vessel entities with no counterpart,
    every limb and head/neck file right-side only while the trunk files were
    complete. For an atlas meant to say what a needle would pass through,
    that was half of every patient."""
    missing = _vessels_without_a_counterpart(_vessel_ids())
    assert not missing, "\n".join(missing[:20])


def test_the_vessel_symmetry_check_catches_a_missing_side():
    ids = _vessel_ids()
    assert "common_carotid_a_l" in ids, "the left carotid should exist by now"
    assert _vessels_without_a_counterpart(ids - {"common_carotid_a_l"}) == \
        ["common_carotid_a_r"]


def test_a_genuinely_unilateral_vessel_is_excused_with_a_reason():
    ids = _vessel_ids()
    assert "brachiocephalic_trunk_r" in ids
    assert "brachiocephalic_trunk_l" not in ids, \
        "there is no left brachiocephalic trunk; mirroring invented a vessel"
    for eid, why in UNILATERAL_VESSELS.items():
        assert len(why) > 40, f"{eid} is excused without a real reason"


def test_the_left_carotid_comes_off_the_arch_not_a_mirrored_trunk():
    """The one place the mirror could not just flip a suffix: the right common
    carotid's parent is the brachiocephalic trunk, and copying that would have
    hung the left carotid off a vessel that does not exist."""
    for path in sorted((BONES.parent.parent / "vascular").glob("*.json")):
        for rec in json.loads(path.read_text()):
            if isinstance(rec, dict) and rec.get("id") == "common_carotid_a_l":
                assert rec.get("parent_id") == "aortic_arch_and_great_vessels", \
                    rec.get("parent_id")
                return
    raise AssertionError("common_carotid_a_l not found")


def _muscles_no_nerve_reaches():
    targeted = set()
    for _f, rec in _tree_records():
        for t in rec.get("targets") or []:
            if isinstance(t, str):
                targeted.add(t)
    out = []
    for path in sorted((BONES.parent.parent / "muscles").rglob("*.json")):
        payload = json.loads(path.read_text())
        for m in (payload if isinstance(payload, list) else [payload]):
            if not isinstance(m, dict) or "id" not in m:
                continue
            comps = [c["id"] for c in m.get("functional_compartments", [])
                     if isinstance(c, dict) and "id" in c]
            if not any(c in targeted for c in comps + [m["id"]]):
                out.append((m["id"], (m.get("innervation") or {}).get("nerve")))
    return out


def test_every_muscle_is_reached_by_a_nerve():
    """107 muscles were the target of no nerve entity -- all eleven tongue
    muscles say hypoglossal_n and the hypoglossal nerve listed none of them;
    sixteen forearm extensors say posterior_interosseous_n and it listed none
    of those. The muscle-to-nerve direction was authored and the reverse was
    not, for a third of the body.

    The last sixteen were muscles whose nerve was packed into one string --
    "intercostal_nerves", "median_n_1_2_ulnar_n_3_4" -- which no entity could
    match. Those strings are gone: innervation.nerve is now a list of real
    ids where a muscle has more than one, each compartment names its own in
    innervation_branch_ids, and every nerve so named lists the compartment
    back. Nothing is excused any more."""
    assert not _muscles_no_nerve_reaches(), \
        "\n".join(f"{m} (says {n!r})" for m, n in _muscles_no_nerve_reaches())


def test_no_innervation_is_a_packed_pseudo_id():
    """'femoral_n_and_obturator_n' looked like an id and was not one. An
    allow-list in the validator excused 22 such strings, which is how 64
    muscles came to point at nothing while every check passed."""
    from engine import validators
    problems = [p for p in validators.validate_bone_references()
                if "innervation" in p]
    assert not problems, "\n".join(problems[:10])


def test_the_validator_catches_a_packed_string_again(tmp_path, monkeypatch):
    """Verified by putting one back."""
    from engine import validators
    src = BONES.parent.parent / "muscles"
    victim = next(p for p in src.rglob("pectineus_r.json"))
    payload = json.loads(victim.read_text())
    payload["innervation"]["nerve"] = "femoral_n_and_obturator_n"
    fake = tmp_path / "data"
    (fake / "muscles").mkdir(parents=True)
    (fake / "nerves").mkdir()
    (fake / "skeleton").mkdir()
    # The validator returns early without a skeleton, and that one line of
    # complaint would be filtered out below -- which is how a first version
    # of this test passed vacuously.
    (fake / "skeleton" / "bones.json").write_text(BONES.read_text())
    for n in (BONES.parent.parent / "nerves").glob("*.json"):
        (fake / "nerves" / n.name).write_text(n.read_text())
    (fake / "muscles" / "pectineus_r.json").write_text(json.dumps(payload))
    monkeypatch.setattr(validators, "DATA_DIR", fake)
    problems = [p for p in validators.validate_bone_references() if "innervation" in p]
    assert any("femoral_n_and_obturator_n" in p for p in problems), problems
