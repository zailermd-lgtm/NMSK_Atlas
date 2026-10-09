"""The clinical layer: where a needle goes.

Motor endplate zones and injection target points are what turn this atlas
into an injection-planning tool, and they are the one part of it that a
clinician acts on directly. A zone with no source, a percentage range the
wrong way round, or a reference line naming only one of its two ends is
worse than a missing zone, because it still renders as a target.
"""
import json
import re
from pathlib import Path

MUSCLES = Path(__file__).resolve().parent.parent / "data" / "muscles"


def _compartments():
    for path in sorted(MUSCLES.rglob("*.json")):
        payload = json.loads(path.read_text())
        for m in (payload if isinstance(payload, list) else [payload]):
            if not isinstance(m, dict) or "id" not in m:
                continue
            for c in m.get("functional_compartments") or []:
                yield path.name, m, c


def test_every_endplate_zone_is_usable_and_sourced():
    """A zone is a measurement someone will put a needle on."""
    bad = []
    for filename, _m, c in _compartments():
        for z in c.get("motor_endplate_zones") or []:
            lo, hi = z["zone_percent_range"]
            if not 0 <= lo <= hi <= 100:
                bad.append(f"{c['id']}: range {[lo, hi]} is not an ordered 0-100 pair")
            if not z.get("reference_line_from") or not z.get("reference_line_to"):
                bad.append(f"{c['id']}: a percentage along a line needs BOTH ends named")
            if z["reference_line_from"] == z["reference_line_to"]:
                bad.append(f"{c['id']}: both ends of the reference line are the same landmark")
            src = z.get("source") or ""
            if len(src) < 40:
                bad.append(f"{c['id']}: source {src!r} is too thin to trace")
            if "doi:" not in src.lower() and "doi.org" not in src.lower():
                bad.append(f"{c['id']}: source names no DOI")
    assert not bad, f"{len(bad)} problem(s):\n" + "\n".join(bad[:15])


def test_a_zone_that_is_not_an_injection_target_says_so_with_a_reason():
    """Some sources map a nerve-dense region and then explicitly rule it out
    as a puncture site -- behind the pleura, a gland or a plexus. Recording
    the anatomy is right; letting a consumer select it as a target is not."""
    bad = [f"{c['id']}: recommended_as_injection_target is false with no reason in notes"
           for _f, _m, c in _compartments()
           for z in c.get("motor_endplate_zones") or []
           if z.get("recommended_as_injection_target") is False
           and len(z.get("notes", "")) < 30]
    assert not bad, "\n".join(bad)


def test_every_injection_target_point_carries_its_three_coordinates():
    """A target point is strictly richer than a zone: a zone gives a level
    along the limb, a point adds the transverse position and the depth. A
    point missing one of the three is a zone wearing a point's name."""
    bad = []
    for _f, _m, c in _compartments():
        for p in c.get("injection_target_points") or []:
            for field in ("transverse_percent", "longitudinal_percent"):
                if not isinstance(p.get(field), (int, float)):
                    bad.append(f"{c['id']}: target point has no numeric {field}")
            # Depth comes in two forms and both are legitimate. A percentage
            # of the limb's own thickness scales with the patient and is
            # preferred. An absolute depth in millimetres does not scale --
            # it is the mean of the source's cadaver sample, and is what the
            # deep cervical sources report, because a neck has no "limb
            # thickness" to take a fraction of. An absolute depth is only
            # usable if the surface it is measured from is named.
            pct = p.get("depth_percent_of_limb_thickness")
            mm = p.get("depth_mm")
            if not isinstance(pct, (int, float)) and not isinstance(mm, (int, float)):
                bad.append(f"{c['id']}: target point states no depth, in either form")
            if isinstance(mm, (int, float)) and not p.get("depth_measured_from"):
                bad.append(f"{c['id']}: depth_mm {mm} with no surface to measure it from")
            for a, b in (("transverse_line_from", "transverse_line_to"),
                         ("longitudinal_line_from", "longitudinal_line_to")):
                if not p.get(a) or not p.get(b):
                    bad.append(f"{c['id']}: {a}/{b} not both named")
            if "doi:" not in (p.get("source") or "").lower():
                bad.append(f"{c['id']}: target point source names no DOI")
    assert not bad, f"{len(bad)} problem(s):\n" + "\n".join(bad[:15])


def test_the_clinical_layer_is_bilaterally_complete():
    """A zone measured on a cadaver is not a property of one side. A muscle
    that carries one on the right and not on the left would silently offer a
    target for half the patients."""
    have = {}
    for _f, _m, c in _compartments():
        stem = re.sub(r"_(r|l)(?=_|$)", "", c["id"], count=1)
        side = re.search(r"_(r|l)(?=_|$)", c["id"])
        if side:
            have.setdefault(stem, set()).add(side.group(1)) if (
                c.get("motor_endplate_zones") or c.get("injection_target_points")) else None
    lopsided = sorted(s for s, sides in have.items() if len(sides) < 2)
    assert not lopsided, ("carry clinical targets on one side only:\n"
                          + "\n".join(lopsided[:15]))


def test_a_zone_percentage_is_never_silently_reinterpreted_as_a_fascicle_fraction():
    """The published reference lines run in varying directions relative to
    each muscle's own origin-to-insertion axis -- several run distal to
    proximal -- so copying a zone percentage into
    position_fraction_along_fascicle would invert some of them. Any
    compartment whose fascicle fraction is marked 'measured' must therefore
    cite its own evidence, not inherit a zone."""
    bad = []
    for _f, _m, c in _compartments():
        z = c.get("neuromuscular_junction_zone") or {}
        if z.get("evidence") == "measured" and not z.get("location_description"):
            bad.append(f"{c['id']}: fascicle fraction claims to be measured but "
                       f"says nothing about where the measurement came from")
    assert not bad, "\n".join(bad)
