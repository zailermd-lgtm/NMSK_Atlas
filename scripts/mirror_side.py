#!/usr/bin/env python3
"""Generate a left-side ('_l') data file from its right-side ('_r') source,
by bilateral mirroring: negate the X (medial-lateral) component of every
local_position_mm-shaped numeric triple, and rewrite every '_r' id/reference
suffix to '_l' (side: "right" -> "left"). This is a straightforward mirror
because bones.json already defines every paired bone's local frame with the
same X-negation convention (see docs/ARCHITECTURE.md) -- mirroring data
authored against the right side is anatomically exact for a normal,
non-handedness-dependent skeleton, and keeps depth-authored regions (like
the upper-limb flagship) from needing every number written twice by hand.

Usage:
    python scripts/mirror_side.py data/muscles/upper_limb/deltoid_r.json
    python scripts/mirror_side.py data/muscles/upper_limb/*.json
"""
from __future__ import annotations

import copy
import glob
import json
import re
import sys


def _mirror_value(v):
    if isinstance(v, list):
        if len(v) == 3 and all(isinstance(x, (int, float)) for x in v):
            return [-v[0], v[1], v[2]]
        return [_mirror_value(x) for x in v]
    if isinstance(v, dict):
        return {k: _mirror_value(x) for k, x in v.items()}
    if isinstance(v, str):
        # matches '_r' immediately followed by an id/punctuation boundary
        # (another '_', ')', '/', whitespace, ',', '.') or end-of-string,
        # e.g. 'deltoid_r' -> 'deltoid_l', 'deltoid_r_anterior_1' -> 'deltoid_l_anterior_1',
        # '(humerus_r)' -> '(humerus_l)', 'carpals_r/metacarpals_r' -> both flipped.
        # Deliberately does NOT touch plain English text (free-form notes), which never
        # contain a literal underscore immediately before 'r'.
        v2 = re.sub(r"_r(?=[_)/\s,.]|$)", "_l", v)
        if v == "right":
            v2 = "left"
        return v2
    return v


def mirror_file(path: str) -> str:
    with open(path) as f:
        data = json.load(f)
    mirrored = _mirror_value(copy.deepcopy(data))
    if isinstance(mirrored, dict) and mirrored.get("side") == "right":
        mirrored["side"] = "left"
    out_path = re.sub(r"_r(\.json)$", r"_l\1", path)
    if out_path == path:
        raise ValueError(f"{path}: filename does not end in _r.json, refusing to overwrite")
    with open(out_path, "w") as f:
        json.dump(mirrored, f, indent=2)
    return out_path


if __name__ == "__main__":
    paths = []
    for arg in sys.argv[1:]:
        paths.extend(glob.glob(arg))
    if not paths:
        print("usage: mirror_side.py <file_r.json> [...]", file=sys.stderr)
        sys.exit(1)
    for p in paths:
        out = mirror_file(p)
        print(f"{p} -> {out}")
