#!/usr/bin/env python3
"""Give side-agnostic nerves and vessels their left-side targets.

THE DEFECT. Nerve ids in this atlas are side-agnostic by convention: 393 of
404 muscles cite an unsided nerve like `axillary_n`, and only two nerve
entities carry a side at all. One entity therefore stands for both the left
and the right nerve.

Their target lists do not. Across the nerve trees there are 359 references to
right-side muscle compartments and ZERO to left-side ones. So "which muscles
does the axillary nerve supply?" answers with half the body, while "what
innervates the left deltoid?" answers correctly -- the graph is complete in
one direction and half empty in the other, which is worse than being visibly
incomplete in both.

THE FIX. For every side-agnostic entity, each sided reference in a LIST-valued
field gains its mirror, but only when that mirror actually exists. A
reference to something the atlas does not carry is never invented; it is
reported, because a missing left-side compartment is a gap in the muscle data
and papering over it here would hide it.

`motor_entry_point.target_muscle_compartment` was the same defect in a
single-valued field, and was fixed afterwards by letting it hold a list: 71
of 74 motor points named the right side alone, and each now names both.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"

# Fields that hold a list of ids this entity points at.
LIST_REFERENCE_FIELDS = ("targets", "supplies_or_drains", "anastomoses_with",
                         "root_contributions")

_SIDE = re.compile(r"_(r|l)(?=_|$)")


def flip(ref: str) -> str:
    """Swap the side token in an id: 'deltoid_r_anterior' -> 'deltoid_l_anterior'."""
    return _SIDE.sub(lambda m: "_l" if m.group(1) == "r" else "_r", ref, count=1)


def is_sided(ref: str) -> bool:
    return bool(_SIDE.search(ref))


def every_id() -> set:
    """Every id anything could legitimately point at, compartments included.

    Nerve targets name muscle COMPARTMENTS ('supraspinatus_r_anterior'), not
    just muscles, so the entity index used by the geometry ingest -- which
    deliberately drops compartments -- is the wrong list to check against.
    """
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
        try:
            walk(json.loads(path.read_text(encoding="utf-8")))
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{path}: {exc}") from None
    return out


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    known = every_id()
    added, absent, touched = Counter(), Counter(), {}

    for path in sorted(list((DATA_DIR / "nerves").glob("*.json"))
                       + list((DATA_DIR / "vascular").glob("*.json"))):
        payload = json.loads(path.read_text(encoding="utf-8"))
        records = payload if isinstance(payload, list) else [payload]
        changed = False
        for rec in records:
            if not isinstance(rec, dict) or "id" not in rec:
                continue
            if is_sided(rec["id"]):
                # A sided entity's targets should stay on its own side.
                continue
            for field in LIST_REFERENCE_FIELDS:
                refs = rec.get(field)
                if not isinstance(refs, list) or not refs:
                    continue
                have = set(refs)
                extra = []
                for ref in refs:
                    if not isinstance(ref, str) or not is_sided(ref):
                        continue
                    twin = flip(ref)
                    if twin in have or twin in extra:
                        continue
                    if twin in known:
                        extra.append(twin)
                        added[field] += 1
                    else:
                        absent[twin] += 1
                if extra:
                    # Keep each pair together rather than appending in a block,
                    # so the list still reads as anatomy rather than as a diff.
                    merged = []
                    for ref in refs:
                        merged.append(ref)
                        if isinstance(ref, str) and is_sided(ref):
                            twin = flip(ref)
                            if twin in extra and twin not in merged:
                                merged.append(twin)
                    rec[field] = merged
                    changed = True
        if changed:
            touched[path] = payload

    print(f"{sum(added.values())} references would be added across "
          f"{len(touched)} files")
    for field, n in added.most_common():
        print(f"    {field:22} {n}")
    if absent:
        print(f"\n{len(absent)} mirrored ids DO NOT EXIST and were not added -- "
              f"each is a gap in the data they point at:")
        for ref, n in absent.most_common(15):
            print(f"    {ref:44} referenced {n}x")
    if not args.write:
        print("\nPass --write to apply.")
        return 0
    for path, payload in touched.items():
        path.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
    print(f"\nwrote {len(touched)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
