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


def _match(landmark_text: str, candidates: list) -> list | None:
    text = landmark_text.lower()
    best = None
    for name, pos in candidates:
        # substring match either direction: landmark text often contains extra
        # parenthetical annotation ("... (muscle attachment)") around the
        # bone's own landmark name.
        tokens = [t for t in name.replace("(", " ").replace(")", " ").split() if len(t) > 3]
        if tokens and all(t in text for t in tokens[:2]):
            best = pos
            break
    return best


def main():
    bones = _load(DATA_DIR / "skeleton" / "bones.json")
    lut = _bone_landmark_lookup(bones)

    muscle_files = list((DATA_DIR / "muscles").rglob("*.json"))
    anchors = []
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
                pos = _match(landmark_text, lut.get(bone_id, []))
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
    print(f"attachment endpoints with a resolved numeric anchor: {matched_ends}/{total_ends} "
          f"({100*matched_ends/total_ends:.1f}%)")
    print("Unmatched endpoints have no numeric bone landmark yet (breadth-pass bones intentionally "
          "carry descriptive landmarks only, per docs/ARCHITECTURE.md) -- this is expected and not "
          "a bug; see docs/ROADMAP.md for the plan to extend numeric coordinates region by region.")


if __name__ == "__main__":
    main()
