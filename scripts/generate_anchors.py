#!/usr/bin/env python3
"""Derive data/rig/anchors.json from the muscle/fascia data + bones.json's
numeric landmark coordinates.

This is a best-effort convenience generator, not the sole source of truth:
it matches a muscle's textual `origin_landmark`/`insertion_landmark`
against the referenced bone's `landmarks[].name` by substring, and only
emits an anchor where a bone landmark actually carries a numeric
`position_local_mm` (most whole-body breadth bones intentionally don't --
see docs/ARCHITECTURE.md; numeric coordinates are prioritized for the
flagship upper-limb chain). Run after any change to data/skeleton/bones.json
or data/muscles/**.

Coverage is reported explicitly (never silently partial) per the "no silent
caps" principle in the Workflow quality guidance this project follows.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"


def _load(path: Path):
    return json.loads(path.read_text())


def _bone_landmark_lookup(bones: list[dict]) -> dict:
    """bone_id -> list of (landmark_name_lower, position_local_mm)"""
    lut = {}
    for b in bones:
        entries = [(lm["name"].lower(), lm["position_local_mm"])
                   for lm in b.get("landmarks", []) if "position_local_mm" in lm]
        lut[b["id"]] = entries
    return lut


# Words that place an attachment somewhere OTHER than the landmark they
# qualify. "posterior tibia (medial, below soleal line)" names the soleal line
# in order to say the origin is not there, and a plain substring match read
# that as a hit: flexor digitorum longus was anchored exactly on the soleal
# line, 46-55 mm from its own muscle in the Visible Human geometry, which is
# how this was found. Matching a negation as a match is worse than not
# matching, because it produces a confident coordinate instead of a gap.
DISPLACEMENT_QUALIFIERS = (
    "below", "above", "beneath", "under", "distal to", "proximal to",
    "inferior to", "superior to", "medial to", "lateral to", "anterior to",
    "posterior to", "just ", "adjacent to", "lateral of", "medial of",
)
QUALIFIER_WINDOW = 28


def _tokens(name: str) -> list:
    """Significant words of a landmark name, punctuation stripped.

    Only parentheses were stripped before. A landmark named "greater
    trochanter, lateral facet (...)" then produced the token "trochanter,"
    -- with the comma -- which matches nothing, so every facet landmark
    added for the trochanter silently failed to match and the muscles kept
    resolving to the old catch-all point.
    """
    cleaned = re.sub(r"[^\w\s]", " ", name.lower())
    # Each word once. A name that repeats a word -- "lower area, lateral
    # part (adductor magnus, hamstring part)" -- scored that word twice for
    # any text containing it, which is how quadratus femoris, whose text
    # names the tuberosity's lateral BORDER, was sent to its lower area.
    return list(dict.fromkeys(t for t in cleaned.split() if len(t) > 3))


_ORDINAL_WORDS = {"first": 1, "second": 2, "third": 3, "fourth": 4, "fifth": 5}

# Digits are also named, not numbered. "great toe" IS digit 1 and "little
# toe" IS digit 5, so a text naming digits 2-4 must be disqualified from a
# landmark on the hallux -- which is how the dorsal interossei, inserting on
# digits 2, 3 and 4, came to tie between the medial and the lateral side of
# the great toe's proximal phalanx. "pollicis" and "hallucis" are deliberately
# NOT here: they name a muscle, not the bone a landmark sits on, and a
# landmark named for its muscle would then disqualify every other digit.
_DIGIT_NAMES = {"great toe": 1, "hallux": 1, "big toe": 1, "thumb": 1,
                "little toe": 5, "fifth toe": 5, "little finger": 5}


def _ordinals(text: str) -> set:
    """Which rays or digits a piece of text names, as numbers.

    _tokens() drops words of three characters or fewer, so "1st" and "5th"
    were invisible to the matcher: fibularis tertius, whose text correctly
    reads "5th metatarsal base", scored two tokens against "1st metatarsal
    base" and one against "5th metatarsal tuberosity", and was anchored on
    the FIRST metatarsal -- the opposite side of the foot from where it
    inserts. An ordinal is not worth a point; it is a disqualifier.
    """
    low = text.lower()
    found = {n for word, n in _ORDINAL_WORDS.items() if word in low}
    found |= {n for phrase, n in _DIGIT_NAMES.items() if phrase in low}
    found |= {int(d) for d in re.findall(r"(?<![a-z0-9])([1-5])(?:st|nd|rd|th)?"
                                         r"(?![a-z0-9])", low)}
    for lo, hi in re.findall(r"([1-5])\s*(?:-|--|to)\s*([1-5])", low):
        found |= set(range(int(lo), int(hi) + 1))
    return found


# The vertebral column's own ordinals: C1-C7, T1-T12, L1-L5, S1-S5, in
# craniocaudal order so a cross-region range ("C7-T3", "T7-L5") resolves to
# every level in between, not just its two endpoints.
_VERTEBRA_LEVELS = ([f"c{i}" for i in range(1, 8)] + [f"t{i}" for i in range(1, 13)]
                    + [f"l{i}" for i in range(1, 6)] + [f"s{i}" for i in range(1, 6)])
_VERTEBRA_INDEX = {lvl: i for i, lvl in enumerate(_VERTEBRA_LEVELS)}
_VERTEBRA_RANGE_RE = re.compile(r"\b([ctls])\s?(\d{1,2})\s*(?:-|--|–|to)\s*([ctls])\s?(\d{1,2})\b")
_VERTEBRA_SINGLE_RE = re.compile(r"\b([ctls])\s?(\d{1,2})\b")


def _vertebra_levels(text: str) -> set:
    """Which vertebra levels ('c1', 't6', 'l3', ...) a piece of text names.

    Q130 added the first numeric landmarks on a bone entity that spans
    several real, separate vertebrae ('cervical_vertebrae' is one atlas
    entity for C1-C7). A landmark for one specific level -- 'transverse
    process of the atlas (C1)' -- shares every other word with muscle text
    naming a DIFFERENT level's transverse process ('anterior tubercles of
    transverse processes C3-C6'), so plain token-overlap scoring alone
    would win the C1 landmark for a muscle that plainly excludes C1. This
    is the same class of bug _ordinals() exists to prevent for rays/ribs,
    for a letter-prefixed numbering scheme it does not parse. A level
    named in a landmark that the text's own set does not contain is
    disqualifying, exactly like an out-of-range ray or rib -- but stricter
    in one respect: unlike ray/rib text, where an unnumbered mention is
    read as the whole group, a bone this coarse-grained's OWN generic
    per-level text ('superior surface of one spinous process' --
    interspinales, true at every cervical level, naming none of them)
    must not silently default onto whichever single level happens to have
    a number -- so a landmark with a level and text with NONE never match
    (checked as `mine <= text`, which is false whenever text is empty).
    """
    low = text.lower()
    found = set()
    for m in _VERTEBRA_RANGE_RE.finditer(low):
        a, b = f"{m.group(1)}{int(m.group(2))}", f"{m.group(3)}{int(m.group(4))}"
        if a in _VERTEBRA_INDEX and b in _VERTEBRA_INDEX:
            lo, hi = sorted((_VERTEBRA_INDEX[a], _VERTEBRA_INDEX[b]))
            found.update(_VERTEBRA_LEVELS[lo:hi + 1])
    for m in _VERTEBRA_SINGLE_RE.finditer(low):
        lvl = f"{m.group(1)}{int(m.group(2))}"
        if lvl in _VERTEBRA_INDEX:
            found.add(lvl)
    return found


def _is_displaced(text: str, at: int) -> str | None:
    """A qualifier shortly before the match means 'not here'."""
    window = text[max(0, at - QUALIFIER_WINDOW):at]
    for word in DISPLACEMENT_QUALIFIERS:
        if word in window:
            return word.strip()
    return None


# Anatomical qualifiers paired across many unrelated muscle families
# (rhomboid MINOR / teres MINOR / pectoralis MINOR; vastus LATERALIS / vastus
# MEDIALIS; adductor LONGUS / BREVIS / MAGNUS; gluteus MEDIUS ...). A muscle's
# own name often contains one of these, but it is not a safe way to
# recognise the muscle: it collides with every other family that reuses the
# same qualifier for a different muscle at the same or a neighbouring site.
# The FAMILY word ("rhomboid", "vastus", "extensor") is what actually
# identifies the muscle; qualifiers are excluded from self-reference matching
# so a shared qualifier alone can never manufacture a false self-reference.
_GENERIC_MUSCLE_QUALIFIERS = {
    "minor", "major", "medius", "minimus", "lateralis", "medialis",
    "longus", "brevis", "magnus", "profundus", "superficialis",
    "anterior", "posterior", "superior", "inferior", "internus",
    "externus", "tertius", "quartus", "quintus",
}


def _muscle_ref_tokens(name_common: str) -> set:
    """The informative words of a muscle's own display name, for checking
    whether a candidate landmark's own text names this muscle. Excludes
    bare anatomical qualifiers (see _GENERIC_MUSCLE_QUALIFIERS) since those
    are shared across unrelated muscle families and would produce false
    positives on their own."""
    return {t for t in _tokens(name_common) if t not in _GENERIC_MUSCLE_QUALIFIERS}


def _self_referencing(ref_tokens: set, landmark_tokens: list) -> bool:
    """True if the landmark's own name text names the owning muscle, via any
    informative ref token appearing as (or as the stem of, e.g. plural
    'rhomboids' for 'rhomboid') one of the landmark's own tokens."""
    return any(lt == rt or lt.startswith(rt) or rt.startswith(lt)
               for rt in ref_tokens for lt in landmark_tokens)


def _match(landmark_text: str, candidates: list, muscle_ref_tokens: set | None = None):
    """Returns (position, skipped_reason). Exactly one is ever non-None.

    Picks the MOST SPECIFIC landmark that matches, not the first one found.
    The original took the first candidate whose first two significant tokens
    appeared in the text, which made every facet of a named prominence
    indistinguishable: "greater trochanter, lateral facet" and "greater
    trochanter, superior border" both reduce to "greater trochanter" under
    that rule, so all seven muscles attaching to the trochanter collapsed
    onto whichever landmark happened to be listed first. Scoring by how many
    of a landmark's own tokens the text actually contains lets a muscle that
    names its facet find its facet.

    `muscle_ref_tokens`, when given, is the owning muscle's own informative
    name tokens (see _muscle_ref_tokens()). A candidate whose OWN name
    explicitly names this muscle is preferred outright, ahead of every
    other criterion below: `_match()` otherwise has no idea which muscle it
    is placing an anchor for, and picks between candidates on how much text
    they share with the attachment description alone -- which loses when an
    unrelated candidate happens to share more incidental words (the muscle's
    own text naming a neighbour, or its own bone's descriptive prose
    colliding with a generic landmark's full name, e.g. "at the root of the
    spine" coincidentally saturating "spine of scapula (trapezius
    insertion...)"). A landmark that already names the muscle attaching
    there removes that guesswork entirely, so it outranks raw token overlap.
    """
    text = landmark_text.lower()
    wanted = _ordinals(text)
    scored = []
    for name, pos in candidates:
        tokens = _tokens(name)
        # The gate must look at the SITE only. Taking the first two tokens of
        # the whole name pulled the second one out of the attachment list
        # for any one-word site -- "manubrium (sternocleidomastoid, ...)"
        # demanded that "sternocleidomastoid" appear in the text, which
        # rejected every plain "manubrium" origin (found 2026-09-10 when the
        # sternum first got numeric landmarks).
        # Either rule may admit a candidate: the whole-name rule keeps every
        # match that ever worked (a clarifying parenthetical inside a site,
        # "external (gluteal) surface", is part of the site's own words);
        # the site rule admits one-word sites whose second whole-name token
        # is an attaching muscle.
        site_tokens = _tokens(re.sub(r"\([^)]*\)", " ", name)) or tokens
        if not tokens or not (all(t in text for t in tokens[:2])
                              or all(t in text for t in site_tokens[:2])):
            continue
        self_ref = bool(muscle_ref_tokens) and _self_referencing(muscle_ref_tokens, tokens)
        # A landmark name has two parts: the SITE ("ischial tuberosity,
        # lateral border") and, in parentheses, WHO attaches there. Only the
        # site describes where the landmark is. The attachment list is a
        # hazard when scored the same way, because a muscle's text often
        # names its neighbours in order to place itself relative to them --
        # fibularis brevis arises "deep to fibularis longus" -- and every
        # landmark listing that neighbour then scores as if it had been
        # named. The site is scored first; the attachment list only breaks
        # ties between sites that fit equally.
        site = set(_tokens(re.sub(r"\([^)]*\)", " ", name)))
        # A landmark that names a different ray is not a weaker match, it is
        # the wrong bone. Only disqualify when BOTH sides state an ordinal
        # AND neither's set contains the other's: a landmark named for the
        # group ("metatarsal heads") is a legitimate match for a text that
        # names one ray, a stray digit in prose ("each with 2 heads,
        # bipennate") must not be read as a ray, and a text naming one ray a
        # broader landmark's ordinals already cover is legitimate too.
        # Overlap alone is not enough: a landmark for digits 2-4 (the dorsal
        # interossei's own site) shares the digit 4 with text naming digits
        # 3-5 (plantar interossei) merely because the ranges are adjacent,
        # not because either names the other's site -- plantar interossei's
        # insertion was anchored on the dorsal interossei's landmark this way.
        mine = _ordinals(name)
        if wanted and mine and not (wanted <= mine or mine <= wanted):
            continue
        # Vertebra levels (Q130): stricter than the ray/rib check above --
        # a landmark naming one level must have that level IN the text's
        # own set, full stop, not just a non-empty overlap. See
        # _vertebra_levels()'s own docstring for why an unnumbered text
        # must not default onto a numbered landmark here.
        mine_v = _vertebra_levels(name)
        if mine_v and not (mine_v <= _vertebra_levels(text)):
            continue
        # Score by how many of the landmark's tokens the text contains, with
        # the fraction only as a tiebreak. Ordering matters and both orders
        # were tried: fraction-first penalises a long descriptive landmark
        # name, and sent obturator internus to the LESSER trochanter -- a
        # different feature 60 mm away -- because "lesser trochanter
        # (iliopsoas insertion)" scored 2/4 against 4/11 for its own facet,
        # whose name lists every muscle attaching there. Raw count first
        # gives 4 against 2 and picks the facet.
        site_hits = sum(1 for t in tokens if t in site and t in text)
        other_hits = sum(1 for t in tokens if t not in site and t in text)
        key = (int(self_ref), site_hits, site_hits / max(len(site), 1), other_hits,
               (site_hits + other_hits) / len(tokens))
        scored.append((key, name, pos, tokens))
    if not scored:
        return None, None
    scored.sort(key=lambda r: tuple(-v for v in r[0]))
    if len(scored) > 1 and scored[0][0] == scored[1][0]:
        # Two landmarks fit equally well. Silently taking either would be a
        # coin toss recorded as a coordinate.
        return None, (f"matches {scored[0][1]!r} and {scored[1][1]!r} equally "
                      f"well; the text does not say which")
    _, name, pos, tokens = scored[0]
    qualifier = _is_displaced(text, text.find(tokens[0]))
    if qualifier:
        return None, (f"matched {name!r} but the text says "
                      f"{qualifier!r} it, so the landmark is not the "
                      f"attachment site")
    return pos, None


_COMPARTMENT_STOPWORDS = {"part", "head", "belly", "division", "compartment",
                          "the", "and", "muscle"}


def _compartment_qualifier(name: str) -> str | None:
    """The one word a compartment's own name contributes that its siblings
    don't -- 'Adductor part' -> 'adductor', 'Hamstring (ischiocondylar) part'
    -> 'hamstring', 'Medial head' -> 'medial'. None if nothing distinctive
    is left, which is the common case (most compartments are 'Main' or
    numbered, not textually distinguishable, and are left alone)."""
    cleaned = re.sub(r"\([^)]*\)", " ", name.lower())
    cleaned = re.sub(r"[^\w\s]", " ", cleaned)
    words = [w for w in cleaned.split() if w not in _COMPARTMENT_STOPWORDS]
    return words[0] if words else None


def _split_by_compartments(text: str, qualifiers: list) -> dict | None:
    """One muscle, one `attachments` block, but a text like 'adductor part:
    X; hamstring part: Y' or '...base: medial head to A, lateral head to B'
    is really two claims wearing one field. A single match then has to
    pick one candidate for text that names two different sites, which is
    exactly the tie _match refuses rather than guess.

    Splits the text at each compartment's own qualifying word (first
    occurrence, whichever comes first in the running text) and prepends
    whatever precedes the first qualifier -- the shared site context both
    compartments need ('proximal phalanx of the great toe, base:') -- to
    every piece. Returns {qualifier: reconstructed_text}, or None if any
    qualifier is missing from the text or two land at the same position
    (nothing to split on, or the split would be ambiguous)."""
    low = text.lower()
    positions = []
    for q in qualifiers:
        m = re.search(rf"\b{re.escape(q)}\b", low)
        if m is None:
            return None
        positions.append((m.start(), q))
    if len(set(p for p, _ in positions)) != len(positions):
        return None
    positions.sort()
    preamble = text[:positions[0][0]]
    out = {}
    for i, (start, q) in enumerate(positions):
        end = positions[i + 1][0] if i + 1 < len(positions) else len(text)
        chunk = text[start:end]
        out[q] = (preamble + " " + chunk) if preamble else chunk
    return out


# `_match()` used to pick between candidate landmarks without knowing which
# muscle it was placing (Q133 fixed that: see `muscle_ref_tokens` on
# `_match()` and `_self_referencing()`). A full audit against every one of
# the 238 anchors, cross-checked against the muscle's own text and the real
# geometry, found three cases where that cost the right answer, all
# originally pinned here as named overrides. The self-reference mechanism
# now resolves `rhomboid_minor_r/l` insertion and `extensor_carpi_ulnaris_r/l`
# origin correctly on its own (their correct landmark already passes the
# ordinary word-overlap gate below; self-reference only had to outrank the
# flawed tiebreak that previously chose the wrong one) -- verified by
# temporarily removing each override and confirming `_match()` alone
# reproduces the same coordinate, then diffing the full corpus to confirm
# nothing else moved. Both are removed below.
#
# `vastus_lateralis_r/l` origin is NOT fixable the same way and keeps its
# override: its correct landmark, "gluteal tuberosity/linea aspera (...
# vastus medialis/lateralis ...)", doesn't share its first two tokens with
# vastus_lateralis's own text ("linea aspera (lateral lip), greater
# trochanter, intertrochanteric line" -- "linea aspera" is the landmark's
# 3rd/4th token, not its first two), so it never enters `_match()`'s
# candidate list at all; self-reference can only rank candidates that are
# already in that list. Loosening the gate to admit self-referencing
# candidates regardless of word-overlap position DOES make this one
# resolve correctly, but a full-corpus diff of that version showed 95 newly
# resolved anchors and 35 changed coordinates across dozens of unrelated
# muscles (pronator_teres, deltoid, stylohyoid, teres_major, the hallucis
# muscles, and more) -- far too broad to verify safe in this pass, and
# exactly the "corrects the target, silently changes something unverified
# elsewhere" failure this section already warns about. So the override
# stays; a real gate-side fix (letting self-reference admit a candidate
# without granting it blanket priority over everything else the gate
# protects against) is still open.
_KNOWN_MISMATCH_OVERRIDES = {
    # The original documented case (see ROADMAP.md's landmark-audit section
    # and validate_moment_arms.py): "linea aspera (lateral lip), greater
    # trochanter, intertrochanteric line" scores 3 site-word hits against
    # "greater trochanter lateral facet (gluteus medius insertion)" -- a
    # facet belonging to a different muscle -- against only 2 against the
    # correct, explicitly self-naming landmark. Raw site-hit count is
    # primary by design (the obturator internus/lesser trochanter case this
    # function's docstring describes needs exactly that), so no reordering
    # of the existing criteria reaches this one without unreordering that
    # one. See the comment above for why the self-reference mechanism
    # (Q133) doesn't reach this one either: its correct landmark never
    # enters `_match()`'s candidate list to be ranked.
    ("vastus_lateralis_r", "muscle_origin"): "vastus medialis/lateralis",
    ("vastus_lateralis_l", "muscle_origin"): "vastus medialis/lateralis",
}


def _apply_override(muscle_id: str, role: str, candidates: list):
    """The verified-correct landmark's position for a (muscle, role) pair
    _match() gets wrong, identified by a substring unique to that
    landmark's name; None if this pair has no override, so the caller
    falls through to _match() as normal."""
    needle = _KNOWN_MISMATCH_OVERRIDES.get((muscle_id, role))
    if needle is None:
        return None
    hits = [pos for name, pos in candidates if needle in name]
    assert len(hits) == 1, (
        f"override for {muscle_id} {role} expected exactly one landmark "
        f"containing {needle!r}, found {len(hits)} -- bones.json changed "
        f"under this override; fix or remove the entry")
    return hits[0]


def main():
    bones = _load(DATA_DIR / "skeleton" / "bones.json")
    lut = _bone_landmark_lookup(bones)

    muscle_files = list((DATA_DIR / "muscles").rglob("*.json"))
    anchors = []
    displaced = []
    total_ends = 0
    matched_ends = 0

    per_compartment_anchors = 0
    for path in muscle_files:
        payload = _load(path)
        entities = payload if isinstance(payload, list) else [payload]
        for m in entities:
            att = m.get("attachments")
            if not att:
                continue
            # A muscle whose compartments each carry their own distinguishing
            # word ('adductor part' / 'hamstring part', 'medial head' /
            # 'lateral head') can have its single attachments text split one
            # clause per compartment. Most muscles' compartments don't
            # (single compartment, or several identical 'Fascicle N' ones)
            # and this is simply None for them -- unchanged, whole-muscle
            # behaviour below.
            comps = m.get("functional_compartments", [])
            comp_qualifiers = None
            if len(comps) >= 2:
                quals = [(_compartment_qualifier(c.get("name", "")), c.get("id"))
                         for c in comps]
                if (all(q for q, _ in quals)
                        and len(set(q for q, _ in quals)) == len(quals)):
                    comp_qualifiers = quals

            for role, bone_key, landmark_key in (
                ("muscle_origin", "origin_bone", "origin_landmark"),
                ("muscle_insertion", "insertion_bone", "insertion_landmark"),
            ):
                total_ends += 1
                bone_id = att.get(bone_key)
                landmark_text = att.get(landmark_key, "")
                candidates = lut.get(bone_id, [])
                muscle_ref_tokens = _muscle_ref_tokens(m.get("name_common", ""))

                resolved_per_compartment = None
                if comp_qualifiers:
                    split = _split_by_compartments(
                        landmark_text, [q for q, _ in comp_qualifiers])
                    if split is not None:
                        resolved_per_compartment = {}
                        for q, comp_id in comp_qualifiers:
                            p, _skip = _match(split[q], candidates, muscle_ref_tokens)
                            if p is None:
                                resolved_per_compartment = None
                                break
                            resolved_per_compartment[comp_id] = (p, split[q])

                if resolved_per_compartment is not None:
                    matched_ends += 1
                    for comp_id, (pos, chunk_text) in resolved_per_compartment.items():
                        per_compartment_anchors += 1
                        anchors.append({
                            "id": f"anchor_{comp_id}_{role.split('_')[1]}",
                            "anchor_type": role,
                            "owner_entity": comp_id,
                            "parent_bone_frame": bone_id,
                            "local_position_mm": pos,
                            "notes": "auto-derived, per functional compartment "
                                     f"(one shared attachments field split by "
                                     f"compartment), from bone landmark match "
                                     f"against '{chunk_text[:60]}'",
                        })
                    continue

                override_pos = _apply_override(m["id"], role, candidates)
                if override_pos is not None:
                    matched_ends += 1
                    anchors.append({
                        "id": f"anchor_{m['id']}_{role.split('_')[1]}",
                        "anchor_type": role,
                        "owner_entity": m["id"],
                        "parent_bone_frame": bone_id,
                        "local_position_mm": override_pos,
                        "notes": "manually verified override, not the automatic "
                                 "matcher's own pick -- see PROJECT_STATE.md "
                                 "for why this pair needed one",
                    })
                    continue

                pos, skipped = _match(landmark_text, candidates, muscle_ref_tokens)
                if skipped:
                    displaced.append((m["id"], role, skipped))
                if pos is not None:
                    matched_ends += 1
                    anchors.append({
                        "id": f"anchor_{m['id']}_{role.split('_')[1]}",
                        "anchor_type": role,
                        "owner_entity": m["id"],
                        "parent_bone_frame": bone_id,
                        "local_position_mm": pos,
                        "notes": f"auto-derived from bone landmark match against '{landmark_text[:60]}'",
                    })

            # Via points (Q138): unlike origin/insertion, a via point's own
            # position is given directly and numerically in the muscle's own
            # attachments (schema/muscle.schema.json), not resolved by
            # text-matching against a bone's landmark list -- so it needs no
            # lookup, just emission, one anchor per entry, in path order
            # (a "sequence" field the rig schema does not restrict, added
            # purely so a consumer can reconstruct origin -> via... ->
            # insertion without re-parsing the muscle file). Whole-muscle
            # only: attachments (and its via_points) is one field shared by
            # every compartment, the same as origin_bone/insertion_bone,
            # never split per compartment even when origin/insertion text is.
            for i, via in enumerate(att.get("via_points", [])):
                bone_frame = via.get("bone_frame")
                pos = via.get("position_local_mm")
                if not bone_frame or pos is None:
                    continue
                anchors.append({
                    "id": f"anchor_{m['id']}_via_{i}",
                    "anchor_type": "muscle_via_point",
                    "owner_entity": m["id"],
                    "parent_bone_frame": bone_frame,
                    "local_position_mm": pos,
                    "sequence": i,
                    "notes": "auto-derived from the muscle's own attachments.via_points"
                             f"[{i}]" + (f" ('{via['structure'][:60]}')" if via.get("structure") else ""),
                })

    # A midline bone (mandible, sternum, occipital ...) carries ONE landmark
    # for a bilateral feature, authored for the subject's RIGHT (+X). A
    # left-side muscle attaching there must get the mirror image, or both
    # masseters would insert on the right angle of the mandible.
    bone_side = {b["id"]: b.get("side") for b in bones}
    for a in anchors:
        if bone_side.get(a["parent_bone_frame"]) == "midline" \
                and re.search(r"_l(?:_|$)", a["owner_entity"]) \
                and a["local_position_mm"][0] != 0:
            x, y, z = a["local_position_mm"]
            a["local_position_mm"] = [-x, y, z]
            a["notes"] += "; X mirrored for the left side of a midline bone"

    (DATA_DIR / "rig").mkdir(parents=True, exist_ok=True)
    with open(DATA_DIR / "rig" / "anchors.json", "w") as f:
        json.dump(anchors, f, indent=2)

    print(f"anchors written: {len(anchors)}"
          + (f" ({per_compartment_anchors} of them per-compartment, "
             f"from a shared attachments field that named more than one site)"
             if per_compartment_anchors else ""))
    if displaced:
        # Reported, never silent. A refused match is a gap the caller can see
        # and fill; a wrong match is a coordinate nobody questions.
        print(f"\n{len(displaced)} endpoint(s) refused because the text places "
              f"the attachment AWAY from the landmark it names:")
        for owner, role, why in sorted(displaced):
            print(f"  {owner} {role.split('_')[1]}: {why}")
    print(f"attachment endpoints with a resolved numeric anchor: {matched_ends}/{total_ends} "
          f"({100*matched_ends/total_ends:.1f}%)")
    print("Unmatched endpoints have no numeric bone landmark yet (breadth-pass bones intentionally "
          "carry descriptive landmarks only, per docs/ARCHITECTURE.md) -- this is expected and not "
          "a bug; see docs/ROADMAP.md for the plan to extend numeric coordinates region by region.")


if __name__ == "__main__":
    main()
