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


def _is_displaced(text: str, at: int) -> str | None:
    """A qualifier shortly before the match means 'not here'."""
    window = text[max(0, at - QUALIFIER_WINDOW):at]
    for word in DISPLACEMENT_QUALIFIERS:
        if word in window:
            return word.strip()
    return None


def _match(landmark_text: str, candidates: list):
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
    """
    text = landmark_text.lower()
    wanted = _ordinals(text)
    scored = []
    for name, pos in candidates:
        tokens = _tokens(name)
        if not tokens or not all(t in text for t in tokens[:2]):
            continue
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
        # the wrong bone. Only disqualify when BOTH sides state an ordinal:
        # a landmark named for the group ("metatarsal heads") is a legitimate
        # match for a text that names one ray, and a stray digit in prose
        # ("each with 2 heads, bipennate") must not be read as a ray.
        mine = _ordinals(name)
        if wanted and mine and not (wanted & mine):
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
        key = (site_hits, site_hits / max(len(site), 1), other_hits,
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

                resolved_per_compartment = None
                if comp_qualifiers:
                    split = _split_by_compartments(
                        landmark_text, [q for q, _ in comp_qualifiers])
                    if split is not None:
                        resolved_per_compartment = {}
                        for q, comp_id in comp_qualifiers:
                            p, _skip = _match(split[q], candidates)
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

                pos, skipped = _match(landmark_text, candidates)
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
