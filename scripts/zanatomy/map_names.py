"""Q141 phase 1: map Z-Anatomy object names -> this project's entity ids.

Reads data/derived/zanatomy_inventory.json (scripts/zanatomy/extract_fbx.py's output)
and this project's own entity registry across ALL tissue directories (muscles,
tendons, ligaments, fascia, skeleton, nerves, vascular, cartilage, bursae), and
proposes a match for every kept Z-Anatomy object.

Reuses this project's OWN existing name-matching machinery
(engine/vh_ingest.py: normalise(), similarity(), propose_matches(),
find_grouping_entity(), the EXACT threshold) and its exact classification policy
from scripts/ingest_vh_geometry.py's `propose` subcommand (min-score 0.55,
ambiguity margin 0.08, "confident" only when the winner clears both the exact
threshold or the margin over the runner-up) -- rather than inventing a second
name-matching scheme for a second third-party source. The only addition is a
loader for data/bursae/*.json, which engine/vh_ingest.py's CATEGORY_BY_DIR does
not cover (the Denver release it was built for never ships bursae); it is added
here as extra AtlasEntity records rather than by editing that module.

"Never guess": a match is written as `atlas_id` in the output only for
status in {"confident", "exact"}. "ambiguous" and "unmatched" both leave
atlas_id null and carry their candidates for a human to decide.

Usage:
    python3 scripts/zanatomy/map_names.py \\
        --inventory data/derived/zanatomy_inventory.json \\
        --out data/derived/zanatomy_name_map.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from engine import vh_ingest as vh  # noqa: E402

DATA_DIR = REPO_ROOT / "data"

MIN_SCORE = 0.55   # same default as scripts/ingest_vh_geometry.py's `propose --min-score`
MARGIN = 0.08      # same default as scripts/ingest_vh_geometry.py's `propose --margin`

_SUFFIX_RE = re.compile(r"\.([A-Za-z0-9]+)$")


def strip_suffix(name: str) -> str:
    return _SUFFIX_RE.sub("", name)


# --------------------------------------------------------------------------
# Atlas entity index: engine.vh_ingest's loader plus bursae (not in its
# CATEGORY_BY_DIR -- see module docstring).
# --------------------------------------------------------------------------

def load_full_atlas():
    atlas = list(vh.load_atlas_index())
    for path in sorted(DATA_DIR.glob("bursae/*.json")):
        payload = json.loads(path.read_text())
        for entity in vh._iter_entities(payload):
            entity_id = entity.get("id")
            if not entity_id:
                continue
            names = tuple(dict.fromkeys(
                n for n in (entity.get("name_common"), entity.get("name_ta"),
                            entity.get("name"), vh._id_to_name(entity_id))
                if isinstance(n, str) and n.strip()
            ))
            side = entity.get("side")
            atlas.append(vh.AtlasEntity(
                entity_id=entity_id, category="bursa",
                side=side if side in ("left", "right") else None,
                names=names, source_file=str(path.relative_to(DATA_DIR)),
            ))
    return atlas


# --------------------------------------------------------------------------
# "Currently missing" entities, per Q117/recount_tissue_gaps.py's own method,
# read directly from the committed audit rather than re-deriving it (the
# audit needs both build/viewer_*/bundle.json to exist; this script does not).
# --------------------------------------------------------------------------

Q117_TYPES = ("bones", "bursae", "cartilage", "fascia", "ligaments",
              "muscles", "nerves", "tendons", "vascular")


def load_missing_ids(q117_path: Path) -> dict:
    d = json.loads(q117_path.read_text())
    return {t: set(d["by_type"][t]["neither"]) for t in Q117_TYPES if t in d["by_type"]}


# --------------------------------------------------------------------------
# Fast scoring: engine.vh_ingest.AtlasEntity.normalised is a @property that
# calls normalise() (several regexes, including a per-synonym substitution
# loop) fresh on every access. vh.propose_matches()/vh.find_grouping_entity()
# both read it once per (query, atlas-entity) pair, which is fine for the DU
# release's ~130 source meshes but not for ~3200 Z-Anatomy objects against a
# ~1580-entity atlas (~5M re-normalisations either way). Below precomputes
# each atlas entity's normalised names ONCE and reimplements the same two
# functions' scoring logic against that cache -- same thresholds, same
# similarity()/normalise() primitives, same results, no per-query recompute.
# --------------------------------------------------------------------------

def build_cache(atlas):
    return [(e, tuple(vh.normalise(n) for n in e.names)) for e in atlas]


def fast_propose(query_raw, cache, *, side=None, top_n=3):
    query = vh.normalise(query_raw)
    if not query:
        return []
    scored = []
    for entity, norm_names in cache:
        if side and entity.side and entity.side != side:
            continue
        best_score, best_name = 0.0, ""
        for norm, raw in zip(norm_names, entity.names):
            s = vh.similarity(query, norm)
            if s > best_score:
                best_score, best_name = s, raw
        if best_score > 0.0:
            scored.append(vh.MatchCandidate(entity.entity_id, entity.category,
                                             round(best_score, 4), best_name))
    scored.sort(key=lambda c: (-c.score, c.entity_id))
    return scored[:top_n]


def fast_find_grouping(query_raw, cache, *, side=None):
    query = set(vh.normalise(query_raw).split())
    if not query:
        return []
    hits = []
    for entity, norm_names in cache:
        if side and entity.side and entity.side != side:
            continue
        for norm, raw in zip(norm_names, entity.names):
            tokens = set(norm.split())
            if query < tokens and len(tokens) > len(query):
                hits.append(vh.MatchCandidate(entity.entity_id, entity.category,
                                               round(len(query) / len(tokens), 4), raw))
                break
    hits.sort(key=lambda c: (-c.score, c.entity_id))
    return hits[:3]


def classify(source_name: str, side, cache):
    """Exactly scripts/ingest_vh_geometry.py's `propose` classification policy
    (confident / exact / ambiguous / unmatched / grouped), applied here."""
    cands = fast_propose(source_name, cache, side=side, top_n=3)
    best = cands[0] if cands else None
    runner = cands[1] if len(cands) > 1 else None

    if best is not None and best.score >= vh.EXACT and (runner is None or runner.score < vh.EXACT):
        return "exact", best.entity_id, cands, None
    if best is None or best.score < MIN_SCORE:
        grouped = fast_find_grouping(source_name, cache, side=side)
        if grouped:
            return "grouped", None, grouped, (
                f"No 1:1 entity; the atlas carries this inside the coarser "
                f"'{grouped[0].entity_id}'."
            )
        return "unmatched", None, cands, None
    if runner and (best.score - runner.score) < MARGIN:
        return "ambiguous", None, cands, f"top two within {MARGIN} of each other"
    return "confident", best.entity_id, cands, None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--inventory", default=str(DATA_DIR / "derived" / "zanatomy_inventory.json"))
    ap.add_argument("--q117", default=str(DATA_DIR / "derived" / "Q117_full_completeness_audit.json"))
    ap.add_argument("--out", default=str(DATA_DIR / "derived" / "zanatomy_name_map.json"))
    args = ap.parse_args(argv)

    inventory = json.loads(Path(args.inventory).read_text())
    atlas = load_full_atlas()
    cache = build_cache(atlas)
    print(f"atlas index: {len(atlas)} entities across {len(set(e.category for e in atlas))} categories "
          f"(muscles/tendons/ligaments/fascia/skeleton(bone)/nerves/vascular(vessel)/cartilage/bursae)")

    entries = []
    counts = Counter()
    matched_atlas_ids = set()

    for obj in inventory["objects"]:
        if obj["license"] != "CC-BY-SA-4.0":
            counts["excluded_nc_licensed"] += 1
            entries.append({
                "zanatomy_name": obj["name"], "system": obj["system"], "side": obj["side"],
                "status": "excluded_nc_licensed", "atlas_id": None, "score": None,
                "matched_name": None, "candidates": [],
                "note": obj["license"],
            })
            continue

        base = strip_suffix(obj["name"])
        status, atlas_id, cands, note = classify(base, obj["side"], cache)
        counts[status] += 1
        if len(entries) % 500 == 0:
            print(f"  ...{len(entries)}/{len(inventory['objects'])}", flush=True)
        if atlas_id:
            matched_atlas_ids.add(atlas_id)
        # Runner-up candidates only matter for a human review, i.e. only for
        # "ambiguous" (top two too close to call) and "grouped" (which coarser
        # entity, of up to 3, might be the right one) -- keeping them for every
        # one of ~3200 objects roughly doubled this file's size for no benefit
        # on the other four statuses, where the single winner already says it all.
        keep_candidates = status in ("ambiguous", "grouped")
        entries.append({
            "zanatomy_name": obj["name"],
            "system": obj["system"],
            "side": obj["side"],
            "status": status,
            "atlas_id": atlas_id,
            "score": (cands[0].score if cands else None),
            "matched_name": (cands[0].matched_name if cands else None),
            "candidates": ([
                {"entity_id": c.entity_id, "category": c.category, "score": c.score,
                 "matched_name": c.matched_name}
                for c in cands
            ] if keep_candidates else []),
            "note": note,
        })

    # atlas entities Z-Anatomy has NO confident/exact object for at all (either
    # direction of "unmatched both ways": this is the atlas->zanatomy direction;
    # zanatomy->atlas direction is every entry above with status in
    # {"unmatched", "ambiguous", "grouped"}).
    atlas_ids_all = {e.entity_id for e in atlas}
    atlas_with_no_zanatomy_match = sorted(atlas_ids_all - matched_atlas_ids)

    # Coverage of currently-missing (neither-body) entities per Q117.
    missing_by_type = load_missing_ids(Path(args.q117))
    coverage = {}
    for t, missing_ids in missing_by_type.items():
        can_supply = sorted(missing_ids & matched_atlas_ids)
        coverage[t] = {
            "currently_missing_count": len(missing_ids),
            "zanatomy_can_supply_count": len(can_supply),
            "zanatomy_can_supply_ids": can_supply,
            "still_no_source_count": len(missing_ids) - len(can_supply),
        }

    result = {
        "source": (
            "Q141 (2026-09-23): name mapping from Z-Anatomy (CC BY-SA 4.0) inventory "
            "objects (data/derived/zanatomy_inventory.json) to this project's own entity "
            "ids, via scripts/zanatomy/map_names.py, reusing engine/vh_ingest.py's "
            "normalise()/similarity()/propose_matches() and scripts/ingest_vh_geometry.py's "
            "exact classification policy (min_score=0.55, margin=0.08) unchanged. Coverage "
            "counts are cross-referenced against data/derived/Q117_full_completeness_audit.json's "
            "'neither' (missing on both bodies) lists. Phase 1 only: no geometry registered or "
            "shipped by this step -- see docs/GEOMETRY_SOURCES.md / PROJECT_STATE.md Q141."
        ),
        "generated": "2026-09-23",
        "policy": {
            "min_score": MIN_SCORE, "margin": MARGIN, "exact_threshold": vh.EXACT,
            "statuses": {
                "exact": "normalised score >= EXACT (0.999), unambiguous -- atlas_id set",
                "confident": "best score >= min_score, clears runner-up by >= margin -- atlas_id set",
                "ambiguous": "top two candidates within margin of each other -- atlas_id left null, never guessed",
                "unmatched": "best score < min_score and no coarser grouping entity found -- atlas_id null",
                "grouped": "no 1:1 entity but a coarser atlas entity contains it by name (many-to-one) -- atlas_id null, candidates name the group",
                "excluded_nc_licensed": "Z-Anatomy object flagged non-commercial-licensed by extract_fbx.py -- never matched, regardless of name",
            },
        },
        "counts": dict(counts),
        "total_zanatomy_objects": len(inventory["objects"]),
        "total_atlas_entities": len(atlas),
        "atlas_entities_with_a_zanatomy_match": len(matched_atlas_ids),
        "atlas_entities_with_no_zanatomy_match": atlas_with_no_zanatomy_match,
        "missing_entity_coverage_by_tissue_type": coverage,
        "entries": entries,
    }

    out_path = Path(args.out)
    out_path.write_text(json.dumps(result, indent=1))

    print("\n=== status counts ===")
    for k, v in counts.most_common():
        print(f"  {k}: {v}")
    print("\n=== missing-entity coverage (of Q117's 'neither' lists) ===")
    for t, c in coverage.items():
        print(f"  {t}: {c['zanatomy_can_supply_count']} / {c['currently_missing_count']} "
              f"can be supplied by Z-Anatomy (confident/exact match)")
    print(f"\nwrote {out_path}")


if __name__ == "__main__":
    main()
