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
import base64
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
# 11 MB of binary per file (~14.7 MB of base64, under the 16 MB text-file cap); a multiple of 3 so
# the files' base64 texts concatenate into one valid base64 string in the page.
BIN_CHUNK = 10_999_998


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bundle", default="build/viewer")
    ap.add_argument("-o", "--out", default="build/viewer/atlas_viewer.html")
    ap.add_argument("--title", default=None,
                    help="Q143: replace the page's <title> text (default keeps "
                         "'NMSK Atlas Viewer') -- for a bundle that is not the main body, "
                         "e.g. the Z-Anatomy reference model.")
    ap.add_argument("--external-bin", action="store_true",
                    help="Q163: write the geometry as sibling base64 <out-stem>_geo_NN.txt files (each "
                         "under the artifact host's 16 MB text-file cap) fetched by the page, instead of "
                         "inlining it -- lifts the single-page size ceiling; publish them with the page.")
    ap.add_argument("--template", default=None,
                    help="Q197: template file (default viewer/atlas_viewer.template.html). With an existing "
                         "bundle.json/bundle.b64 and --external-bin this is the template-only re-render: no "
                         "geometry is recomputed and the geo files come out byte-identical to the bundle's.")
    args = ap.parse_args()

    src = REPO_ROOT / args.bundle
    template = (Path(args.template) if args.template else REPO_ROOT / "viewer" / "atlas_viewer.template.html").read_text(encoding="utf-8")
    if args.title:
        template = template.replace(
            "<title>NMSK Atlas Viewer</title>", f"<title>{args.title}</title>", 1)
    payload = (src / "bundle.json").read_text(encoding="utf-8")
    b64 = (src / "bundle.b64").read_text(encoding="utf-8").strip()

    # A literal "</script>" anywhere inside a script element ends it, whatever
    # the surrounding quotes think. JSON escapes the slash back out again.
    payload = payload.replace("</", "<\\/")
    if "</script" in b64.lower():
        raise SystemExit("base64 payload contains a script terminator")

    out = REPO_ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    bin_files = []
    if args.external_bin:
        raw = base64.b64decode(b64)
        for i, o in enumerate(range(0, len(raw), BIN_CHUNK)):
            name = f"{out.stem}_geo_{i:02d}.txt"
            (out.parent / name).write_text(base64.b64encode(raw[o:o + BIN_CHUNK]).decode("ascii"), encoding="ascii")
            bin_files.append({"path": name, "bytes": len(raw[o:o + BIN_CHUNK])})
        b64 = ""
    html = (template.replace("__BUNDLE_JSON__", payload).replace("__BUNDLE_BIN_FILES__", json.dumps(bin_files))
            .replace("__BUNDLE_B64__", b64))
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out}  ({len(html) / 1e6:.2f} MB)")
    for f in bin_files:
        print(f"  geometry file {f['path']}  ({f['bytes'] / 1e6:.2f} MB binary)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
