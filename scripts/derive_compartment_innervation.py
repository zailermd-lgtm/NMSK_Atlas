#!/usr/bin/env python3
"""Give every compartment its resolvable nerve ids, derived from the tree.

scripts/resolve_compound_innervation.py did this for the 64 dually
innervated muscles, where it mattered most. The other 340 muscles' 426
compartments still carried only prose, so innervation_branch_ids was
present on a fifth of the atlas and absent on the rest -- a field that is
sometimes there is one nobody can rely on.

HOW EACH COMPARTMENT'S IDS ARE FOUND, IN ORDER.

  1. The nerve entities whose targets name the compartment itself.
  2. Failing that, the ones whose targets name the muscle. 70 compartments
     are the single `_main` compartment of a muscle the tree reaches only by
     muscle id, which is the same link at coarser grain.
  3. The muscle's own stated nerve is added when it is neither equal to nor
     an ancestor of anything already found. Usually it IS an ancestor -- the
     muscle says obturator_n_anterior_division, the tree says
     obturator_n_branch_to_adductor_brevis, and the branch is the finer
     truth. When it is not, both are claims the atlas makes, and the graph
     should hold both: the orbital part of orbicularis oculi is reached by
     the temporal branch in the tree and by the zygomatic branch in the
     muscle's record, and it is in fact supplied by both.

Nothing is invented. Every id written already appears somewhere in the
atlas as an assertion about this compartment or its muscle.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true")
    args = ap.parse_args()

    rec, targets_of = {}, defaultdict(set)
    for path in (DATA_DIR / "nerves").glob("*.json"):
        for n in json.loads(path.read_text(encoding="utf-8")):
            if isinstance(n, dict) and "id" in n:
                rec[n["id"]] = n
                for t in n.get("targets") or []:
                    if isinstance(t, str):
                        targets_of[t].add(n["id"])

    def ancestors(nid):
        out = set()
        while nid in rec:
            nid = rec[nid].get("parent_id")
            if nid:
                out.add(nid)
        return out

    how, unresolved, unioned = Counter(), [], []
    plans = []
    for path in sorted((DATA_DIR / "muscles").rglob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        muscles = payload if isinstance(payload, list) else [payload]
        changed = False
        for m in muscles:
            if not isinstance(m, dict) or "id" not in m:
                continue
            stated = (m.get("innervation") or {}).get("nerve")
            stated = set(stated) if isinstance(stated, list) else ({stated} if stated else set())
            for c in m.get("functional_compartments") or []:
                if c.get("innervation_branch_ids"):
                    how["kept"] += 1
                    continue
                ids = set(targets_of.get(c["id"], ()))
                source = "compartment"
                if not ids:
                    ids = set(targets_of.get(m["id"], ()))
                    source = "muscle"
                if not ids:
                    unresolved.append((c["id"], sorted(stated)))
                    continue
                for s in stated:
                    if s in rec and s not in ids and not any(
                            s in ancestors(i) for i in ids):
                        ids.add(s)
                        unioned.append((c["id"], s, sorted(ids - {s})))
                c["innervation_branch_ids"] = sorted(ids)
                how[source] += 1
                changed = True
        if changed:
            plans.append((path, payload))

    print(f"compartments: {dict(how)}")
    if unioned:
        print(f"\n{len(unioned)} compartment(s) where the muscle's stated nerve is "
              f"neither in the tree's targets nor an ancestor of them, so both "
              f"were kept:")
        for cid, s, others in unioned[:10]:
            print(f"    {cid:40} +{s}  (tree: {others})")
    if unresolved:
        print(f"\n{len(unresolved)} compartment(s) no nerve reaches at either "
              f"grain -- left without ids:")
        for cid, s in unresolved[:10]:
            print(f"    {cid:40} muscle says {s}")
    if not args.write:
        print("\nPass --write to apply.")
        return 0
    for path, payload in plans:
        # Keep each file's own indentation, so the diff shows the anatomy
        # that changed and not a reformat of everything around it.
        text = path.read_text(encoding="utf-8")
        found = re.search(r"\n( +)\S", text)
        indent = len(found.group(1)) if found else 2
        path.write_text(json.dumps(payload, indent=indent, ensure_ascii=text.isascii())
                        + ("\n" if text.endswith("\n") else ""), encoding="utf-8")
    print(f"\nwrote {len(plans)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
