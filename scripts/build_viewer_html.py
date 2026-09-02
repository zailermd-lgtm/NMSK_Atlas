#!/usr/bin/env python3
"""Fold the exported bundle into viewer/atlas_viewer.template.html.

The viewer has to be one self-contained file: an artifact cannot fetch its
own data at runtime, and a clinician opening this offline has no server. So
the geometry is embedded as base64 and the atlas records as JSON, both into
<script> tags the page reads back rather than into JavaScript literals --
which keeps the anatomy out of the parser's expression grammar, where an
apostrophe in "Gray's Anatomy" would otherwise end a string.

    python3 scripts/build_viewer_html.py -o build/viewer/atlas_viewer.html
"""
from __future__ import annotations

import argparse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bundle", default="build/viewer")
    ap.add_argument("-o", "--out", default="build/viewer/atlas_viewer.html")
    args = ap.parse_args()

    src = REPO_ROOT / args.bundle
    template = (REPO_ROOT / "viewer" / "atlas_viewer.template.html").read_text(encoding="utf-8")
    payload = (src / "bundle.json").read_text(encoding="utf-8")
    b64 = (src / "bundle.b64").read_text(encoding="utf-8").strip()

    # A literal "</script>" anywhere inside a script element ends it, whatever
    # the surrounding quotes think. JSON escapes the slash back out again.
    payload = payload.replace("</", "<\\/")
    if "</script" in b64.lower():
        raise SystemExit("base64 payload contains a script terminator")

    html = template.replace("__BUNDLE_JSON__", payload).replace("__BUNDLE_B64__", b64)
    out = REPO_ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out}  ({len(html) / 1e6:.2f} MB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
