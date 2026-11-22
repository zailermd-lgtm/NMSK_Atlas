#!/usr/bin/env python3
"""Q334: no imaginary lines between the pieces of one continuous structure (skin regions first) on the Z engine.

    flock /tmp/nmsk_sync.lock python3 scripts/anatomy/q334/patch_seams_q334.py [--check] [FILE ...]
    python3 scripts/anatomy/q334/patch_seams_q334.py --hook-only PAGE.html     # a TEST COPY as before the fix (+ the hook)

FILE defaults to viewer/zan_atlas.template.html (the Z engine). A built page html (index.html / atlas_viewer_*.html) carries the
same engine text and can be patched the same way for a quick test copy. Idempotent: each block lives between its own markers and
is replaced in place. --check exits 1 when a FILE is not up to date. The own-engine template is never touched.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
DEFAULT = REPO / "viewer/zan_atlas.template.html"

# (name, anchor text that the block goes right AFTER, block file)
BLOCKS = [
    ("weld", "    boot(\"Uploading to GPU…\", 0.72); await nf();\n", "seams_weld_q334.js"),
    ("upload", "    OBJ.forEach(function (o) { o.pos = null; o.nrm = null; o.idx = null; });\n", "seams_upload_q334.js"),
    ("walls", "    var addonDraw = [], addonClick = null, addonOpacity = null;\n", "seams_walls_q334.js"),
    ("runs", "      function runs(B, test) {\n", "seams_runs_q334.js"),
    ("hook", "      hidden:hidden.size, faded:faded.size, solo:soloLayer, side:sideFilter\n    }; };\n", "seams_hook_q334.js"),
]


def begin(n):
    return f"/* Q334 {n} begin */"


def end(n):
    return f"/* Q334 {n} end */"


def strip(text: str, names) -> str:
    """remove the named blocks (a test copy of the page as it was before the fix keeps only the read-only hook)"""
    for name in names:
        b, e = text.find(begin(name)), text.find(end(name))
        if b >= 0 and e > b:
            text = text[:text.rfind("\n", 0, b) + 1] + text[text.find("\n", e) + 1:]
    return text


def apply(text: str, only=None) -> str:
    for name, anchor, fn in BLOCKS:
        if only is not None and name not in only:
            continue
        body = (HERE / fn).read_text(encoding="utf-8").rstrip("\n")
        blk = f"    {begin(name)}\n{body}\n    {end(name)}\n"
        b, e = text.find(begin(name)), text.find(end(name))
        if b >= 0 and e > b:
            ls = text.rfind("\n", 0, b) + 1
            le = text.find("\n", e) + 1
            text = text[:ls] + blk + text[le:]
            continue
        n = text.count(anchor)
        if n != 1:
            raise SystemExit(f"Q334: anchor for '{name}' found {n} times (need exactly 1)")
        i = text.index(anchor) + len(anchor)
        text = text[:i] + blk + text[i:]
    return text


def main() -> int:
    check = "--check" in sys.argv
    hook_only = "--hook-only" in sys.argv      # test copies only: the page as before the fix, plus the read-only hook
    files = [Path(a) for a in sys.argv[1:] if not a.startswith("--")] or [DEFAULT]
    bad = 0
    for f in files:
        old = f.read_text(encoding="utf-8")
        new = apply(strip(old, ["weld", "upload", "walls", "runs"]), ["hook"]) if hook_only else apply(old)
        if check:
            ok = new == old
            print(("Q334 up to date: " if ok else "Q334 NOT up to date: ") + str(f))
            bad += 0 if ok else 1
        elif new != old:
            f.write_text(new, encoding="utf-8")
            print("Q334 patched: " + str(f))
        else:
            print("Q334 unchanged: " + str(f))
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
