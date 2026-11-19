"""Generalizes scripts/recount_muscle_gaps.py's exact method to every tissue-type data directory
under data/ that holds per-entity JSON records with an "id" field: how many entities have a mesh
on both/either/neither published viewer, matching each entity's own "id" against the "id" field of
each build/viewer_*/bundle.json's structures.

Unlike the muscle-only script, most other tissue types store several entities per file (a list of
records) rather than one file per entity, and use a different field name for their region/grouping
("plexus" for nerves, "tree_name" for vascular trees) or none at all (skeleton/joints.json, an
articulation/DOF table with no per-entity mesh -- excluded, see TYPES below). The extraction logic
below handles both file shapes with the same "must be a dict with a non-empty 'id'" test the muscle
script already uses to skip its own index file, so a reference table like
data/nerves/spinal_and_cranial_nerve_roots.json (myotome/dermatome/cranial-nerve entries with no
"id" at all -- confirmed not a nerve_branch entity list by engine/validators.py's own schema
dispatch) is skipped the same way, not miscounted.

    python3 scripts/recount_tissue_gaps.py [--type NAME ...] [--out FILE.json]

Requires both viewers to have been exported (build/viewer_m/bundle.json, build/viewer_f/bundle.json);
run scripts/export_viewer_bundle.py first if either is missing or stale. Reads the LIVE published
bundles only, not any pending unpublished rebuild sitting in build/viewer_*/atlas_viewer_*.html.
"""
import argparse
import glob
import json
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

# name -> (glob pattern(s) relative to REPO, region/grouping field, one-line note on what's excluded and why)
TYPES = {
    "muscles": (["data/muscles/**/*.json"], "region",
                "one file per entity (data/muscles/<region>/<name>.json); data/muscles/muscle_index.json "
                "is a list with no dict entries and is skipped by the same id-and-dict test."),
    "tendons": (["data/tendons/*.json"], "region", "one file per body region, each a list of tendon entities."),
    "ligaments": (["data/ligaments/*.json"], "region", "one file per joint/region, each a list of ligament entities."),
    "fascia": (["data/fascia/*.json"], "region", "one file per body region, each a list of fascia entities."),
    "bones": (["data/skeleton/bones.json"], "region",
              "data/skeleton/joints.json deliberately excluded: its 60 records are kinematic "
              "articulations (DOF ranges, coordinate systems), not mesh entities -- 0 of its ids "
              "appear in either bundle by design, not as a gap (a joint is not rendered as its own "
              "mesh; it is implied by its adjoining bones)."),
    "cartilage": (["data/cartilage/*.json"], "region", "one file per cartilage group, each a list of entities."),
    "bursae": (["data/bursae/*.json"], "region", "one file per joint region, each a list of bursa entities."),
    "nerves": (["data/nerves/*.json"], "plexus",
               "data/nerves/spinal_and_cranial_nerve_roots.json is a nested reference table "
               "(spinal_nerves/cranial_nerves/sources), not an entity list -- its items carry no "
               "'id' field at all and are skipped, matching engine/validators.py's own schema "
               "dispatch note that it is 'a reference table, not a nerve_branch entity list'."),
    "vascular": (["data/vascular/*.json"], "tree_name", "one file per arterial/venous/lymphatic tree, each a list of vessel entities."),
}


def entity_ids(patterns):
    """Same method as recount_muscle_gaps.py's entity_ids(), generalized to also accept files whose
    top level is a LIST of entity dicts (most non-muscle types) rather than one dict per file
    (muscles). Any list item, or whole-file dict, without a non-empty 'id' is skipped -- this is what
    silently excludes index files and reference tables with no per-entity id."""
    ids = {}
    for pattern in patterns:
        for f in glob.glob(str(REPO / pattern), recursive=True):
            d = json.load(open(f))
            if isinstance(d, dict) and d.get("id"):
                ids[d["id"]] = d
            elif isinstance(d, list):
                for item in d:
                    if isinstance(item, dict) and item.get("id"):
                        ids[item["id"]] = item
    return ids


def bundle_ids(bundle_path):
    d = json.load(open(bundle_path))
    return set(s["id"] for s in d.get("structures", []) if s.get("id"))


def base_name(eid):
    for suf in ("_l", "_r"):
        if eid.endswith(suf):
            return eid[: -len(suf)]
    return eid


def audit_one(type_name, male, female):
    patterns, region_field, note = TYPES[type_name]
    ents = entity_ids(patterns)

    both, either, neither = [], [], []
    for eid, rec in ents.items():
        m, f = eid in male, eid in female
        if m and f:
            both.append(eid)
        elif m or f:
            either.append([eid, "male" if m else "female"])
        else:
            neither.append(eid)

    distinct_missing = sorted(set(base_name(e) for e in neither))
    region_counts = dict(Counter(ents[e].get(region_field, "?") for e in neither))

    return {
        "type": type_name,
        "region_field": region_field,
        "note": note,
        "total_entities": len(ents),
        "both": sorted(both),
        "both_count": len(both),
        "either": sorted(either),
        "either_count": len(either),
        "neither": sorted(neither),
        "neither_count": len(neither),
        "at_least_one_count": len(both) + len(either),
        "distinct_missing": distinct_missing,
        "distinct_missing_count": len(distinct_missing),
        "region_counts": region_counts,
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--type", action="append", choices=sorted(TYPES), default=None,
                     help="restrict to one or more tissue types (default: all)")
    ap.add_argument("--out", default=None, help="optional path to write the full result JSON (per type)")
    a = ap.parse_args(argv)

    male = bundle_ids(REPO / "build/viewer_m/bundle.json")
    female = bundle_ids(REPO / "build/viewer_f/bundle.json")

    types = a.type or sorted(TYPES)
    results = {}
    for t in types:
        r = audit_one(t, male, female)
        results[t] = r
        print(f"=== {t} ===")
        print("  total entities:", r["total_entities"])
        print("  meshes on BOTH bodies:", r["both_count"])
        print("  meshes on AT LEAST ONE:", r["at_least_one_count"])
        print("  on NEITHER:", r["neither_count"])
        print("  distinct missing (base name, both sides collapsed):", r["distinct_missing_count"])
        print("  by", r["region_field"], "(missing-on-both entity count):", r["region_counts"])

    if a.out:
        json.dump(results, open(a.out, "w"), indent=1)
        print("wrote", a.out)


if __name__ == "__main__":
    main()
