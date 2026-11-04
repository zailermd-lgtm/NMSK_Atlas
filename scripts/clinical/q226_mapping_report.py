#!/usr/bin/env python3
"""Q226 -- structure -> tissue-class mapping coverage report for the imaging simulation, per page.

Applies clinical/data/imaging_tissues.json `mapping_rules` (first match wins; same rules as clinical/imaging_tool.js) to the structure
list of each built page and writes data/derived/Q226_mapping_<page>.json: counts per class / rule / bone kind, the UNASSIGNED structures
(generic soft tissue, flagged in the UI) and the structures a rule claimed only by category (default branch of its category).

    python3 scripts/clinical/q226_mapping_report.py [--page vhm ...] [--root DIR]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "clinical"))
from q226_structures import PAGES, page_structures  # noqa: E402

TABLE = REPO / "clinical" / "data" / "imaging_tissues.json"


def load_table() -> dict:
    return json.loads(TABLE.read_text(encoding="utf-8"))


def compile_rules(T: dict):
    keys = [c["key"] for c in T["classes"]]
    out = []
    for ix, r in enumerate(T["mapping_rules"]["rules"]):
        assert r["cls"] in keys, f"rule {ix}: unknown class {r['cls']}"
        out.append({"ix": ix, "cat": r.get("cat"), "re": re.compile(r["re"], re.I) if r.get("re") else None, "vt": r.get("vt"),
                    "cls": r["cls"], "kind": r.get("kind"), "render": r.get("render"), "why": r.get("why", "")})
    return out


def classify(rules, T: dict, rec: dict) -> dict:
    text = (str(rec.get("id") or "") + " " + str(rec.get("name") or "")).lower().replace("_", " ")
    for r in rules:
        if r["cat"] and rec["cat"] not in r["cat"]:
            continue
        if r["vt"] and rec.get("vt") != r["vt"]:
            continue
        if r["re"] and not r["re"].search(text):
            continue
        return {"cls": r["cls"], "kind": r["kind"], "render": r["render"], "rule": r["ix"]}
    return {"cls": T["mapping_rules"]["fallback"]["cls"], "kind": None, "render": None, "rule": -1}


def report(key: str, root: Path | None = None) -> dict:
    T = load_table()
    rules = compile_rules(T)
    S = page_structures(key, root)
    classes = {c["key"]: c for c in T["classes"]}
    by_cls, by_rule, kinds, per_cat, renders = Counter(), Counter(), Counter(), defaultdict(Counter), Counter()
    members = defaultdict(list)
    unassigned = []
    for s in S:
        c = classify(rules, T, s)
        by_cls[c["cls"]] += 1
        by_rule[c["rule"]] += 1
        per_cat[s["cat"]][c["cls"]] += 1
        if c["kind"]:
            kinds[c["kind"]] += 1
        renders[c["render"] or "fill"] += 1
        if len(members[c["cls"]]) < 6:
            members[c["cls"]].append(s["id"])
        if classes[c["cls"]].get("unassigned"):
            unassigned.append({"id": s["id"], "name": s["name"], "cat": s["cat"]})
    n = len(S)
    return {
        "schema": "nmsk.imaging_mapping_report.v1", "page": key, "table": "clinical/data/imaging_tissues.json",
        "structures": n, "assigned_by_rule": n - len(unassigned), "unassigned": len(unassigned),
        "coverage": round((n - len(unassigned)) / n, 4) if n else None,
        "by_class": dict(sorted(by_cls.items(), key=lambda kv: -kv[1])),
        "by_rule": {str(k): v for k, v in sorted(by_rule.items())},
        "bone_kinds": dict(kinds),
        "render": dict(renders),
        "by_category": {k: dict(v) for k, v in per_cat.items()},
        "examples": dict(members),
        "unassigned_structures": unassigned,
        "note": "unassigned = generic 'soft tissue (unassigned)' in the simulation (HU 40, T1 1000 / T2 60 ms); structures not listed here were claimed by an explicit rule, but a rule can be coarse (e.g. every bone not long/tubular/skull is 'flat_irregular').",
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--page", nargs="*", default=list(PAGES))
    ap.add_argument("--root", default=None)
    a = ap.parse_args(argv)
    out_dir = REPO / "data" / "derived"
    for k in a.page:
        rep = report(k, Path(a.root) if a.root else None)
        (out_dir / f"Q226_mapping_{k}.json").write_text(json.dumps(rep, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"{k}: {rep['structures']} structures, {rep['unassigned']} unassigned ({rep['coverage']:.1%} covered); classes {len(rep['by_class'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
