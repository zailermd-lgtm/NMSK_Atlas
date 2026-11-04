#!/usr/bin/env python3
"""Build the left-side vascular tree, which the atlas does not have.

THE DEFECT. Unlike the nerves, vessel ids ARE sided. And the sided ones are
almost all right: 129 vessel entities have no counterpart, and the pattern is
not scattered. The trunk trees are complete on both sides -- 94 sided
entities, none lonely -- while every limb and head/neck file is right-side
only, all of it:

    head_neck_arterial   14 sided, 14 with no left
    head_neck_venous     17 sided, 17 with no left
    upper_limb_arterial  30 sided, 30 with no left
    upper_limb_venous    14 sided, 14 with no left
    lower_limb_arterial  26 sided, 26 with no left
    lower_limb_venous    21 sided, 21 with no left

So the left arm, the left leg and the left side of the neck have no arteries
and no veins. For an atlas meant to say what a needle would pass through,
that is half of every patient.

WHY MIRRORING IS SAFE HERE, AND WHERE IT IS NOT. These records carry no
geometry -- the only numeric field is approx_diameter_mm, which is
side-independent -- so a mirrored vessel is pure topology: the same tree with
its side tokens flipped. Nothing is being placed in space, so nothing can be
placed wrongly.

What mirroring CANNOT do is decide anatomy, so three things are handled by
name rather than by rule:

  * Genuinely unilateral vessels are excluded. The brachiocephalic trunk
    exists only on the right; on the left the common carotid and subclavian
    arise straight off the aortic arch. Mirroring it would invent a vessel.

  * Notes that name a side are rewritten or the entity is excluded. Three do:
    the brachiocephalic trunk (excluded), the transverse sinus (whose note
    says the RIGHT is usually dominant, which is a fact about the right one),
    and the anterior jugular vein (whose note is about both and mirrors fine).

  * A parent that is not simply the mirror of its own is remapped by name.
    The lymphatic trunks are the case: the left drain to the thoracic duct
    and the right to the right lymphatic duct, which is correct asymmetry,
    not a gap.

Every reference in a mirrored record is checked to resolve before anything is
written.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
VASCULAR = DATA_DIR / "vascular"

_SIDE = re.compile(r"_(r|l)(?=_|$)")
_BARE_ID = re.compile(r"[a-z0-9_]+")

# Vessels that exist on one side only. Anatomy, not a gap.
UNILATERAL = {
    "brachiocephalic_trunk_r":
        "The brachiocephalic trunk arises from the aortic arch and divides "
        "into the right common carotid and right subclavian arteries. On the "
        "left those two arise from the arch directly, so there is no left "
        "brachiocephalic trunk to mirror.",
}

# Where the twin's parent is NOT simply the mirror of the original's parent.
# Keyed by the parent being replaced, for the cases where the whole class
# flips (the lymphatic ducts), and by the child where only that vessel's
# origin differs.
PARENT_REMAP = {
    "thoracic_duct": "right_lymphatic_duct",
    "right_lymphatic_duct": "thoracic_duct",
}
PARENT_REMAP_BY_CHILD = {
    "common_carotid_a_r": (
        "aortic_arch_and_great_vessels",
        "The right common carotid arises from the brachiocephalic trunk, but "
        "the left arises from the aortic arch directly. Mirroring the parent "
        "would hang it off a brachiocephalic trunk that does not exist."),
}

# Notes that assert something about one side specifically.
NOTE_REWRITE = {
    "transverse_sinus_r": (
        "Usually asymmetric, the right being dominant in most people",
        "Usually asymmetric, the right being dominant in most people, so this "
        "left sinus is the smaller of the pair in the majority"),
}

# Notes that name a side but say the same thing about both vessels.
NOTE_SIDE_IS_SYMMETRIC = {
    "anterior_jugular_v_r":
        "Its note describes the two anterior jugulars joining each other "
        "above the sternum, which is one fact about the pair and reads the "
        "same from either side.",
}

LIST_REFERENCE_FIELDS = ("supplies_or_drains", "anastomoses_with", "targets")


def flip(ref: str) -> str:
    return _SIDE.sub(lambda m: "_l" if m.group(1) == "r" else "_r", ref, count=1)


def every_id() -> set:
    out = set()

    def walk(node):
        if isinstance(node, dict):
            if isinstance(node.get("id"), str):
                out.add(node["id"])
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    for path in sorted(DATA_DIR.rglob("*.json")):
        walk(json.loads(path.read_text(encoding="utf-8")))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    known = every_id()
    plans, excluded, unresolved, needs_review = {}, [], [], []

    for path in sorted(VASCULAR.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        by_id = {r["id"]: r for r in payload if isinstance(r, dict) and "id" in r}
        made = []
        for rec in payload:
            if not isinstance(rec, dict) or "id" not in rec:
                continue
            eid = rec["id"]
            if not _SIDE.search(eid) or flip(eid) in known:
                continue
            if eid in UNILATERAL:
                excluded.append((eid, UNILATERAL[eid]))
                continue

            twin = json.loads(json.dumps(rec))     # deep copy
            twin["id"] = flip(eid)
            parent = rec.get("parent_id")
            if parent:
                if eid in PARENT_REMAP_BY_CHILD:
                    twin["parent_id"] = PARENT_REMAP_BY_CHILD[eid][0]
                else:
                    twin["parent_id"] = PARENT_REMAP.get(parent, flip(parent))
            for field in LIST_REFERENCE_FIELDS:
                refs = rec.get(field)
                if isinstance(refs, list):
                    # Side tokens are flipped in free text too -- "serratus
                    # anterior_r" inside a prose entry names a real sided
                    # structure and must move with the vessel -- but only bare
                    # ids are later checked for existence.
                    twin[field] = [flip(r) if isinstance(r, str) else r
                                   for r in refs]
            if eid in NOTE_REWRITE:
                old, new = NOTE_REWRITE[eid]
                if old not in twin.get("notes", ""):
                    raise SystemExit(
                        f"{eid}: the note this script expects to rewrite has "
                        f"changed, so the rewrite would no longer be true. "
                        f"Looked for {old!r}.")
                twin["notes"] = twin["notes"].replace(old, new)
            elif (re.search(r"\b(right|left)\b", str(rec.get("notes", "")), re.I)
                  and eid not in NOTE_SIDE_IS_SYMMETRIC):
                # A note that names a side, copied verbatim onto the opposite
                # vessel, states something false about it. Refuse rather than
                # guess which way to rewrite it.
                needs_review.append((eid, rec["notes"]))
                continue
            made.append(twin)
            by_id[twin["id"]] = twin
        if made:
            plans[path] = (payload, made)

    # Every reference in the new records must resolve, against the atlas plus
    # everything this run is about to add.
    after = set(known) | {t["id"] for _p, (_pl, made) in plans.items() for t in made}
    for path, (_payload, made) in plans.items():
        for twin in made:
            refs = [twin.get("parent_id")] + [
                r for f in LIST_REFERENCE_FIELDS for r in (twin.get(f) or [])]
            for ref in refs:
                # Only a bare id is a reference to check. `supplies_or_drains`
                # legitimately holds prose -- "1st/2nd intercostal spaces,
                # serratus anterior_r" -- and demanding that resolve would
                # report a description as a broken link.
                if not isinstance(ref, str) or not _BARE_ID.fullmatch(ref):
                    continue
                if _SIDE.search(ref) and ref not in after:
                    unresolved.append((twin["id"], ref))

    total = sum(len(m) for _p, m in plans.values())
    print(f"{total} vessels would be created across {len(plans)} files")
    for path, (_payload, made) in sorted(plans.items()):
        print(f"    {path.name:28} +{len(made)}")
    for eid, why in excluded:
        print(f"\n  NOT mirrored: {eid}\n    {why}")
    if needs_review:
        print(f"\n  {len(needs_review)} note(s) name a side and have not been "
              f"reviewed, so those vessels were NOT mirrored -- copying the "
              f"note verbatim would state something false about the twin:")
        for eid, note in needs_review:
            print(f"    {eid}\n      {note[:150]}")
    if unresolved:
        print(f"\n  {len(unresolved)} reference(s) in the new records do not "
              f"resolve; nothing will be written:")
        for eid, ref in unresolved[:12]:
            print(f"    {eid:38} -> {ref}")
        return 1
    if not args.write:
        print("\nPass --write to apply.")
        return 0
    for path, (payload, made) in plans.items():
        payload.extend(made)
        path.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    print(f"\nwrote {len(plans)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
