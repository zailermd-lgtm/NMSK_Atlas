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
    return [t for t in cleaned.split() if len(t) > 3]


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
    scored = []
    for name, pos in candidates:
        tokens = _tokens(name)
        if not tokens or not all(t in text for t in tokens[:2]):
            continue
        # Score by how many of the landmark's tokens the text contains, with
        # the fraction only as a tiebreak. Ordering matters and both orders
        # were tried: fraction-first penalises a long descriptive landmark
        # name, and sent obturator internus to the LESSER trochanter -- a
        # different feature 60 mm away -- because "lesser trochanter
        # (iliopsoas insertion)" scored 2/4 against 4/11 for its own facet,
        # whose name lists every muscle attaching there. Raw count first
        # gives 4 against 2 and picks the facet.
        hits = sum(1 for t in tokens if t in text)
        scored.append((hits, hits / len(tokens), name, pos, tokens))
    if not scored:
        return None, None
    scored.sort(key=lambda r: (-r[0], -r[1]))
    if len(scored) > 1 and scored[0][:2] == scored[1][:2]:
        # Two landmarks fit equally well. Silently taking either would be a
        # coin toss recorded as a coordinate.
        return None, (f"matches {scored[0][2]!r} and {scored[1][2]!r} equally "
                      f"well; the text does not say which")
    _, _, name, pos, tokens = scored[0]
    qualifier = _is_displaced(text, text.find(tokens[0]))
    if qualifier:
        return None, (f"matched {name!r} but the text says "
                      f"{qualifier!r} it, so the landmark is not the "
                      f"attachment site")
    return pos, None


def main():
    bones = _load(DATA_DIR / "skeleton" / "bones.json")
    lut = _bone_landmark_lookup(bones)

    muscle_files = list((DATA_DIR / "muscles").rglob("*.json"))
    anchors = []
    displaced = []
    total_ends = 0
    matched_ends = 0

    for path in muscle_files:
        payload = _load(path)
        entities = payload if isinstance(payload, list) else [payload]
        for m in entities:
            att = m.get("attachments")
            if not att:
                continue
            for role, bone_key, landmark_key in (
                ("muscle_origin", "origin_bone", "origin_landmark"),
                ("muscle_insertion", "insertion_bone", "insertion_landmark"),
            ):
                total_ends += 1
                bone_id = att.get(bone_key)
                landmark_text = att.get(landmark_key, "")
                pos, skipped = _match(landmark_text, lut.get(bone_id, []))
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

    print(f"anchors written: {len(anchors)}")
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
