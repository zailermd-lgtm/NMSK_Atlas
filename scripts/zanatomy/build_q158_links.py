"""Q158: find additional, DETERMINISTIC Z-Anatomy name -> this project's atlas id
PARENT links for the MSK + peripheral-nerve categories (bone, muscle, tendon,
ligament, bursa, cartilage, fascia, nerve) that `scripts/zanatomy/map_names.py`'s
generic fuzzy matcher correctly declined to guess (status ambiguous/unmatched/
grouped in the committed, frozen `data/derived/zanatomy_name_map.json` -- left
exactly as Q141 produced it, per the standing rule `scripts/zanatomy/zan_source.py`
already documents; this script never edits that file or map_names.py).

Q158b (lead review of Q158's first cut): each link named here is a PARENT
reference only -- the Z-Anatomy object it names stays its OWN separate,
individually-selectable mesh under its own id; only its info card gains a
"part of <parent>" note and the parent's own cited facts, clearly labelled as
the parent's. Nothing here is ever geometry to concatenate. (Q158's first cut
fed these atlas ids into `zan_source.load_source()` to MERGE matching Z-Anatomy
objects into one fused mesh per id -- e.g. all 8 carpal bones unioned into one
`carpals_l` blob -- which made individual structures like "scaphoid" or "rib 5"
impossible to select on their own; reverted, see `zan_source.load_extra_links()`'s
own docstring and PROJECT_STATE.md Q158b.)

Every link written here is DERIVED, not a fuzzy score: either

  1. "grouped_unique" / "grouped_default": the name map already found (via its
     own real containment check -- the atlas entity's own name/name_ta literally
     lists this exact structure, e.g. carpals_l's name_ta spells out all eight
     carpal bones) that this Z-Anatomy object belongs inside a coarser atlas
     group, and after restricting the (possibly >1) candidates to the one whose
     CATEGORY matches the tissue class the Z-Anatomy name itself states (see
     `local_tissue_category` below), exactly one candidate remains.
  2. "tissue_disambiguated_ambiguous": the name map's own top-2 candidates were
     too close to call (status "ambiguous"), but they are of DIFFERENT tissue
     categories (e.g. a muscle vs a same-named ligament, or a tendon vs a bursa)
     and the Z-Anatomy name itself states which one it is (contains the literal
     word "muscle"/"ligament"/"tendon"/"bone"/"cartilage"/"fascia"/"bursa"/
     "nerve") -- so the tie is broken by a textual fact already in the source
     name, not by score.
  3. "muscle_head_or_part": the Z-Anatomy name is literally "<qualifier> part/head
     of <parent muscle>[ muscle]" (its own real anatomical vocabulary for a head
     or belly this project's own registry does not split out, e.g. "Humero-ulnar
     head of flexor digitorum superficialis" or "Scapular spinal part of deltoid
     muscle") -- these often score BELOW map_names.py's own min-score (the extra
     qualifier dilutes the token overlap too much even for its fuzzy matcher to
     try), so they never reach "ambiguous"/"grouped" at all. Extracts just the
     stated PARENT muscle name and requires it to score EXACT (>=0.999, unambiguous)
     against a single `category=="muscle"` atlas entity on the object's own side --
     re-using map_names.py's own normalise()/similarity()/fast_propose() verbatim,
     restricted to muscle-only candidates, never a second scoring scheme.
  4. "numbered_series_<kind>": a small set of explicit, curated regexes for
     anatomical series this project's own registry keeps as ONE coarse group
     entity per side/region rather than one id per member -- numbered ribs
     ("First rib".."Twelfth rib" -> ribs_l/r), numbered vertebrae ("Vertebra
     C3".."Vertebra L5" -> cervical_vertebrae/thoracic_vertebrae/
     lumbar_vertebrae), and phalanges named by ordinal digit ("Proximal phalanx
     of fourth finger of hand" -> phalanges_hand_l/r, "... of foot" ->
     phalanges_foot_l/r) -- the digit ordinal doesn't matter since the atlas
     entity is the whole per-hand/per-foot group, not one id per finger.

"Never guess" is inherited: every candidate this script considers already
passed map_names.py's own real matching machinery (grouping containment, or a
close-scoring fuzzy candidate) -- this script only ever REMOVES wrong-category
noise or a small set of curated regexes for series this project already groups
coarsely, it never invents a new textual comparison of its own. Anything left
ambiguous after the tissue filter (e.g. "Collateral metacarpophalangeal
ligaments", tied between two THUMB-only ligament ids with no generic
all-digits entity to point at) is left unmatched, not guessed.

Output: data/derived/Q158_new_links.json -- {"links": [...]} read (read-only
metadata, never merged) by `scripts/zanatomy/zan_source.py`'s
`load_extra_links()` and attached by `scripts/zanatomy/build_zan_atlas_viewer.py`
as a `part_of`/`part_of_id` reference on that Z-Anatomy object's own,
still-separate orphan mesh, plus "excluded_reviewed" for the doubtful ties
this script's own logic produced but a human spot-check below declined.

Usage:
    python3 scripts/zanatomy/build_q158_links.py \\
        --namemap data/derived/zanatomy_name_map.json \\
        --inventory data/derived/zanatomy_inventory.json \\
        --out data/derived/Q158_new_links.json
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from engine import vh_ingest as vh  # noqa: E402
from scripts.zanatomy.map_names import (  # noqa: E402
    MARGIN, build_cache, fast_propose, load_full_atlas, strip_suffix,
)
from scripts.zanatomy.zan_source import (  # noqa: E402
    _ALLOWED_SYSTEMS, _is_cross_category_junk, _side_of_atlas_id,
)

DATA_DIR = REPO / "data"

# Systems this task is scoped to: MSK + peripheral nerve. CardioVascular,
# Lymphoid and Visceral (vessels/lymphatics/organs) are out of scope --
# never considered here, so nothing below can touch them.
TARGET_SYSTEMS = {"Muscular", "Skeletal", "Joints", "Nervous"}

MIN_SCORE = 0.55  # exactly map_names.py's own threshold, reused as a floor for
                   # the ambiguous tier (never accept a tissue-filtered survivor
                   # scoring below what map_names.py itself requires for a 1:1 match)

# Z-Anatomy names for brain/cord/special-sense structures the "Nervous" system
# also carries -- this project's own atlas has NO CNS entities at all (Q141),
# so these can never legitimately resolve to anything; skipped up front rather
# than relying on "no candidate happened to exist" (task: never touch these).
CNS_NAME_HINTS = (
    "brain", "cerebr", "cerebell", "medulla oblongata", "pons", "midbrain",
    "thalamus", "hypothalamus", "spinal cord", "ventricle", "pituitary",
    "hippocamp", "amygdala", "corpus callosum", "basal gangli", "pineal",
    "olfactory bulb", "optic chiasm", "optic nerve", "retina", "cornea",
    "lens", "eyeball", "dorsal root", "rootlet", "dura mater", "arachnoid",
    "pia mater", "meninge", "cauda equina", "choroid plexus", "gyrus",
    "sulcus", "lobule", "insula", "cingulate", "white matter", "gray matter",
    "aqueduct", "spinal nerve", "globus pallidus", "putamen", "caudate",
)


def is_cns(name: str) -> bool:
    low = name.lower()
    return any(h in low for h in CNS_NAME_HINTS)


# Local re-implementation of engine.vh_ingest.tissue_category(), extended with
# "bursa" and "nerve" (that module's own version omits both -- it was built for
# a DU release with no bursa data and where nerve-vs-not was never ambiguous).
# Deliberately a SEPARATE table here rather than editing that module: it is
# reused unchanged everywhere else (the DU-release matcher, map_names.py's own
# scoring), and this task's own standing rule is to add downstream, not touch
# the shared matcher -- see this module's own docstring.
_TISSUE_WORDS = {
    "bone": "bone", "bones": "bone",
    "muscle": "muscle", "muscles": "muscle",
    "cartilage": "cartilage", "cartilages": "cartilage",
    "ligament": "ligament", "ligaments": "ligament",
    "tendon": "tendon", "tendons": "tendon",
    "fascia": "fascia",
    "bursa": "bursa", "bursae": "bursa",
    "nerve": "nerve", "nerves": "nerve",
}


def local_tissue_category(name: str) -> str | None:
    text = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", name)
    for token in re.split(r"[_\-.,()\[\]/\s]+", text.lower()):
        cat = _TISSUE_WORDS.get(token)
        if cat:
            return cat
    return None


# --------------------------------------------------------------------------
# Tier: grouped / ambiguous tissue disambiguation, reusing map_names.py's own
# already-computed candidates verbatim (no rescoring).
# --------------------------------------------------------------------------

def resolve_grouped_or_ambiguous(entry: dict) -> tuple[str, str] | None:
    """Returns (atlas_id, rule) or None. `entry` is one zanatomy_name_map.json
    entry with status in {"grouped", "ambiguous"}."""
    name = entry["zanatomy_name"]
    cands = entry.get("candidates") or []
    if not cands:
        return None
    if entry["status"] == "ambiguous":
        # Ambiguity is fundamentally about the top score's own near-ties (map_names.py's
        # own MARGIN); a distant 3rd candidate (e.g. a stray 0.2-score cross-match) is
        # noise, not a real contender, and must not make the tissue filter see >1
        # survivor and give up on an otherwise clean tie-break.
        top_score = cands[0]["score"]
        contenders = [c for c in cands if (top_score - c["score"]) < MARGIN]
    else:
        contenders = cands
    tissue = local_tissue_category(name)
    if tissue:
        survivors = [c for c in contenders if c["category"] == tissue]
    else:
        survivors = list(contenders)
    ids = {c["entity_id"] for c in survivors}
    if len(ids) != 1:
        return None
    winner = survivors[0]
    if entry["status"] == "ambiguous" and winner["score"] < MIN_SCORE:
        return None
    rule = ("tissue_disambiguated_ambiguous" if entry["status"] == "ambiguous"
            else ("grouped_tissue_disambiguated" if tissue else "grouped_unique"))
    return winner["entity_id"], rule


# --------------------------------------------------------------------------
# Tier: curated numbered-series regexes, for atlas ids this project keeps as
# ONE coarse group per side/region rather than one id per member. These never
# reach map_names.py's "grouped" status because the group entity's own name
# never lists the individual members (unlike carpals_l's name_ta, which spells
# out all eight bones by name and so IS caught by the tier above) -- there is
# nothing for a generic containment check to find, hence a small explicit
# table instead of a fuzzy score.
# --------------------------------------------------------------------------

_ORDINAL_RIB = (
    "first|second|third|fourth|fifth|sixth|seventh|eighth|ninth|tenth|"
    "eleventh|twelfth"
)
_RIB_RE = re.compile(rf"^({_ORDINAL_RIB})\s+rib$", re.I)
_VERTEBRA_RE = re.compile(r"^vertebra\s+([ctl])(\d{1,2})$", re.I)
_PHALANX_RE = re.compile(
    r"^(?:distal|middle|proximal)\s+phalanx\s+of\s+"
    r"(?:first|second|third|fourth|fifth)\s+finger\s+of\s+(hand|foot)$", re.I)

_VERTEBRA_GROUP = {"c": "cervical_vertebrae", "t": "thoracic_vertebrae", "l": "lumbar_vertebrae"}


def numbered_series_match(base_name: str, side: str | None) -> tuple[str, str] | None:
    """`base_name` is the Z-Anatomy name with its trailing `.xx` suffix already
    stripped (map_names.strip_suffix); `side` is the inventory object's own
    parsed side field."""
    m = _RIB_RE.match(base_name)
    if m:
        if side not in ("left", "right"):
            return None
        return f"ribs_{'r' if side == 'right' else 'l'}", "numbered_series_rib"

    m = _VERTEBRA_RE.match(base_name)
    if m:
        letter = m.group(1).lower()
        aid = _VERTEBRA_GROUP.get(letter)
        if aid:
            return aid, "numbered_series_vertebra"
        return None

    m = _PHALANX_RE.match(base_name)
    if m:
        if side not in ("left", "right"):
            return None
        part = "hand" if m.group(1).lower() == "hand" else "foot"
        return f"phalanges_{part}_{'r' if side == 'right' else 'l'}", "numbered_series_phalanx"

    return None


_HEAD_OR_PART_RE = re.compile(
    r"^\(?\s*(?P<qualifier>.+?)\s+(?:part|head)\s+of\s+(?:the\s+)?"
    r"(?P<parent>.+?)(?:\s+muscle)?\s*\)?$", re.I)


def muscle_head_or_part_match(base_name: str, side: str | None, muscle_cache) -> tuple[str, str] | None:
    """`base_name` has its trailing `.xx` suffix already stripped. `muscle_cache`
    is `map_names.build_cache()` pre-filtered to `category == "muscle"` only, so
    a parent name that happens to also read like a bone/ligament can never win
    here -- see this module's own docstring, tier 3."""
    m = _HEAD_OR_PART_RE.match(base_name)
    if not m:
        return None
    parent = m.group("parent").strip()
    if not parent:
        return None
    cands = fast_propose(parent, muscle_cache, side=side, top_n=2)
    if not cands:
        return None
    best = cands[0]
    if best.score < vh.EXACT:
        return None
    if len(cands) > 1 and cands[1].score >= vh.EXACT:
        return None  # two muscles both named exactly this parent -- never guess
    return best.entity_id, "muscle_head_or_part"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--namemap", default=str(DATA_DIR / "derived" / "zanatomy_name_map.json"))
    ap.add_argument("--inventory", default=str(DATA_DIR / "derived" / "zanatomy_inventory.json"))
    ap.add_argument("--out", default=str(DATA_DIR / "derived" / "Q158_new_links.json"))
    args = ap.parse_args(argv)

    namemap = json.loads(Path(args.namemap).read_text())
    inventory = json.loads(Path(args.inventory).read_text())
    objs_by_name = {o["name"]: o for o in inventory["objects"]}
    atlas = load_full_atlas()
    atlas_ids = {e.entity_id for e in atlas}
    id_to_cat = {e.entity_id: e.category for e in atlas}
    muscle_cache = build_cache([e for e in atlas if e.category == "muscle"])

    def ships(name: str, obj: dict, aid: str) -> str | None:
        """None if this exact link would actually reach the viewer through
        `zan_source.load_source()`'s OWN safety nets (reused here unchanged,
        not reimplemented) -- otherwise the reason it would be silently
        dropped there, so this script never claims a link that isn't real."""
        cat = id_to_cat.get(aid)
        if cat is None:
            return "unknown atlas id"
        if _is_cross_category_junk(name, cat):
            return "cross-category junk name for this category"
        if obj["system"] not in _ALLOWED_SYSTEMS.get(cat, {obj["system"]}):
            return f"system {obj['system']!r} not allowed for category {cat!r}"
        wanted_side = _side_of_atlas_id(aid)
        obj_side = obj.get("side")
        if wanted_side and obj_side and obj_side != wanted_side:
            return f"side mismatch: {aid} wants {wanted_side}, object is {obj_side}"
        return None

    links = []
    excluded = []
    seen_names = set()

    for entry in namemap["entries"]:
        if entry["system"] not in TARGET_SYSTEMS:
            continue
        name = entry["zanatomy_name"]
        if name in seen_names:
            continue
        if is_cns(name):
            continue
        status = entry["status"]
        if status not in ("unmatched", "ambiguous", "grouped"):
            continue  # already exact/confident (map_names.py's own job) or NC-excluded
        obj = objs_by_name.get(name)
        if obj is None:
            continue

        result = None
        rule = None
        if status in ("grouped", "ambiguous"):
            got = resolve_grouped_or_ambiguous(entry)
            if got:
                result, rule = got
            elif entry.get("candidates"):
                excluded.append({
                    "zanatomy_name": name, "system": entry["system"], "status": status,
                    "reason": "tissue filter left >1 or 0 candidates -- still ambiguous",
                    "candidates": entry["candidates"],
                })
        if result is None and status == "unmatched":
            got = numbered_series_match(strip_suffix(name), obj.get("side"))
            if got:
                result, rule = got
        if (result is None and entry["system"] == "Muscular"
                and status in ("unmatched", "ambiguous", "grouped")):
            got = muscle_head_or_part_match(strip_suffix(name), obj.get("side"), muscle_cache)
            if got:
                result, rule = got

        if result is None:
            continue
        if result not in atlas_ids:
            raise ValueError(f"{name!r}: rule {rule} produced unknown atlas id {result!r}")
        dead_reason = ships(name, obj, result)
        if dead_reason:
            excluded.append({
                "zanatomy_name": name, "system": entry["system"], "status": status,
                "reason": f"rule {rule} proposed {result!r} but it would never ship: {dead_reason}",
                "candidates": entry.get("candidates", []),
            })
            continue

        seen_names.add(name)
        links.append({
            "zanatomy_name": name,
            "system": entry["system"],
            "side": obj.get("side"),
            "atlas_id": result,
            "rule": rule,
            "prior_status": status,
            "prior_score": entry.get("score"),
        })

    from collections import Counter
    counts = Counter(l["rule"] for l in links)

    out = {
        "source": (
            "Q158b (2026-09-25, lead review of Q158's first cut): additional "
            "deterministic Z-Anatomy name -> PARENT atlas id links for the MSK + "
            "peripheral-nerve categories, layered on top of the frozen "
            "data/derived/zanatomy_name_map.json (never edited) -- see "
            "scripts/zanatomy/build_q158_links.py's own module docstring for the "
            "exact rules. READ-ONLY metadata: scripts/zanatomy/zan_source.py's "
            "load_extra_links() reads it, and scripts/zanatomy/build_zan_atlas_"
            "viewer.py attaches each link as a part_of/part_of_id reference on the "
            "Z-Anatomy object's own, still-separate orphan mesh -- never merged "
            "into the parent's geometry (Q158's first cut did that; reverted)."
        ),
        "generated": "2026-09-25",
        "counts_by_rule": dict(counts),
        "total_links": len(links),
        "links": sorted(links, key=lambda l: (l["rule"], l["zanatomy_name"])),
        "excluded_reviewed": excluded,
    }
    Path(args.out).write_text(json.dumps(out, indent=1))
    print(f"wrote {len(links)} links ({dict(counts)}) and {len(excluded)} excluded to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
