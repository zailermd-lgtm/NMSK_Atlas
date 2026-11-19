"""Regenerate the muscle-completeness counts used in docs/MUSCLE_GAPS.md and PROJECT_STATE's Q62 entries:
how many muscle entities (data/muscles/**/*.json) have a mesh on both/either/neither published viewer, by
matching each entity's own "id" against the "id" field of each build/viewer_*/bundle.json's structures.

    python3 scripts/recount_muscle_gaps.py [--out FILE.json]

Requires both viewers to have been exported (build/viewer_m/bundle.json, build/viewer_f/bundle.json);
run scripts/export_viewer_bundle.py first if either is missing or stale.
"""
import argparse
import glob
import json
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def entity_ids():
    ids = {}
    for f in glob.glob(str(REPO / "data/muscles/**/*.json"), recursive=True):
        d = json.load(open(f))
        if not isinstance(d, dict) or "id" not in d:
            continue  # e.g. data/muscles/muscle_index.json is an index list, not a record
        ids[d["id"]] = d.get("region", "?")
    return ids


def bundle_ids(bundle_path):
    d = json.load(open(bundle_path))
    return set(s["id"] for s in d.get("structures", []) if s.get("id"))


def base_name(eid):
    for suf in ("_l", "_r"):
        if eid.endswith(suf):
            return eid[: -len(suf)]
    return eid


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", default=None, help="optional path to write the full result JSON")
    a = ap.parse_args(argv)

    ents = entity_ids()
    male = bundle_ids(REPO / "build/viewer_m/bundle.json")
    female = bundle_ids(REPO / "build/viewer_f/bundle.json")

    both, either, neither = [], [], []
    for eid, region in ents.items():
        m, f = eid in male, eid in female
        if m and f:
            both.append(eid)
        elif m or f:
            either.append([eid, "male" if m else "female"])
        else:
            neither.append(eid)

    distinct_missing = sorted(set(base_name(e) for e in neither))
    region_counts = dict(Counter(ents[e] for e in neither))

    print("total entities", len(ents))
    print("meshes on BOTH bodies:", len(both))
    print("meshes on AT LEAST ONE:", len(both) + len(either))
    print("on NEITHER:", len(neither))
    print("distinct muscles missing on both:", len(distinct_missing))
    print("by region (missing-on-both entity count):", region_counts)

    if a.out:
        json.dump(
            {
                "total_entities": len(ents),
                "both": sorted(both),
                "either": sorted(either),
                "neither": sorted(neither),
                "distinct_missing": distinct_missing,
                "region_counts": region_counts,
            },
            open(a.out, "w"),
            indent=1,
        )
        print("wrote", a.out)


if __name__ == "__main__":
    main()
