#!/usr/bin/env python3
"""Make every nerve list the muscles that say it innervates them.

THE DEFECT. 107 muscles are the target of no nerve entity at all. Ask the
graph "what does the hypoglossal nerve supply?" and it answers nothing, while
all eleven tongue muscles say hypoglossal_n in their own innervation field.
The same for the posterior interosseous nerve and sixteen forearm extensors,
the pudendal nerve and nine perineal muscles, the facial nerve branches and
the muscles of expression. The muscle-to-nerve direction was authored; the
nerve-to-muscle direction was not, for a third of the body.

THE FIX. For every muscle whose stated nerve IS an entity in the tree, that
entity gains the muscle's compartments as targets. Nothing is authored: each
link already exists in the muscle's own record and is only being made
visible from the other end. A muscle whose stated nerve is not an entity --
"intercostal_nerves", a segmental series with no single id -- is left as it
is and reported.

Compartment ids are used rather than muscle ids because that is what the
tree already targets ("supraspinatus_r_anterior"), and because for a muscle
with two nerves it is the compartment, not the muscle, that has one nerve.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    nerve_files = {}
    nerve_rec = {}
    for path in sorted((DATA_DIR / "nerves").glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        nerve_files[path] = payload
        for rec in payload:
            if isinstance(rec, dict) and "id" in rec:
                nerve_rec[rec["id"]] = rec
    targeted = defaultdict(set)
    for nid, rec in nerve_rec.items():
        for t in rec.get("targets") or []:
            if isinstance(t, str):
                targeted[t].add(nid)

    to_add = defaultdict(list)          # nerve id -> [compartment ids]
    unresolvable = Counter()
    for path in sorted((DATA_DIR / "muscles").rglob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for m in (payload if isinstance(payload, list) else [payload]):
            if not isinstance(m, dict) or "id" not in m:
                continue
            comps = [c["id"] for c in m.get("functional_compartments", [])
                     if isinstance(c, dict) and "id" in c] or [m["id"]]
            if any(targeted.get(c) for c in comps + [m["id"]]):
                continue                        # some nerve already reaches it
            nerve = (m.get("innervation") or {}).get("nerve")
            if nerve not in nerve_rec:
                unresolvable[nerve or "(none)"] += 1
                continue
            for c in comps:
                to_add[nerve].append(c)

    print(f"{sum(len(v) for v in to_add.values())} targets would be added to "
          f"{len(to_add)} nerves")
    for nid, comps in sorted(to_add.items(), key=lambda kv: -len(kv[1]))[:14]:
        print(f"    {nid:44} +{len(comps)}")
    if unresolvable:
        print(f"\n{sum(unresolvable.values())} muscles left untargeted: their "
              f"stated nerve is not an entity in the tree")
        for n, c in unresolvable.most_common():
            print(f"    {n:52} x{c}")
    if not args.write:
        print("\nPass --write to apply.")
        return 0

    touched = set()
    for nid, comps in to_add.items():
        rec = nerve_rec[nid]
        have = rec.setdefault("targets", [])
        for c in comps:
            if c not in have:
                have.append(c)
        touched.add(nid)
    written = 0
    for path, payload in nerve_files.items():
        if any(isinstance(r, dict) and r.get("id") in touched for r in payload):
            path.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
            written += 1
    print(f"\nwrote {written} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
