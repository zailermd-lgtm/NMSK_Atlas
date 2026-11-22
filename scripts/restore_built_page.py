#!/usr/bin/env python3
"""Rebuild the engine's own page file from a build directory restored out of a published artifact.

WHY THIS EXISTS. `build/` is in .gitignore, so a rebuilt container arrives with no built pages at all
and every browser check and every page-parsing test has nothing to run against. The pages can be
fetched back from the published artifacts -- that is the only copy there is -- but an artifact serves
the page as `index.html` wrapped in the artifact service's own skeleton, while the project's loaders
and tests want the unwrapped file under its engine name (`atlas_viewer_zan_atlas.html` and so on).

The wrapper is a fixed prefix: the service's `<!doctype html>...<body>` followed by the real page,
which begins at the SECOND `<!doctype html>`. Stripping to there is a definite operation, not a
reconstruction by guesswork -- and this script refuses rather than guess if the file does not have
that shape. What it writes is the published page body, byte for byte.

    python3 scripts/restore_built_page.py build/q309/viewer_zan_atlas
    python3 scripts/restore_built_page.py build/q309/*            # every directory restored so far

The engine page name is taken from the geometry sidecars already in the directory
(`atlas_viewer_<name>_geo_00.txt` -> `atlas_viewer_<name>.html`), because those are what the page
itself loads and so they cannot disagree with it.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

DOCTYPE = "<!doctype html>"


def page_name(d: Path) -> str | None:
    """the engine's own page name, from the geometry sidecars the page loads"""
    for g in sorted(d.glob("atlas_viewer_*_geo_*.txt")):
        m = re.match(r"(atlas_viewer_.+)_geo_\d+\.txt$", g.name)
        if m:
            return m.group(1) + ".html"
    return None


def strip_wrapper(text: str) -> tuple[str, str]:
    """-> (body, how). Raises ValueError if the file is not a wrapped artifact page."""
    first = text.find(DOCTYPE)
    if first != 0:
        raise ValueError("does not begin with a doctype")
    second = text.find(DOCTYPE, first + 1)
    if second < 0:
        return text, "already unwrapped (one doctype only)"
    head = text[:second]
    if "<body>" not in head or len(head) > 4096:
        raise ValueError(f"the leading block is not the artifact skeleton ({len(head)} bytes)")
    return text[second:], f"stripped a {len(head)}-byte artifact skeleton"


def one(d: Path) -> int:
    idx = d / "index.html"
    if not idx.is_file():
        print(f"  skip {d.name}: no index.html"); return 0
    name = page_name(d)
    if not name:
        print(f"  skip {d.name}: no geometry sidecars, so the page name cannot be established"); return 0
    out = d / name
    body, how = strip_wrapper(idx.read_text(encoding="utf-8", errors="strict"))
    if out.is_file() and out.read_text(encoding="utf-8", errors="strict") == body:
        print(f"  {d.name}: {name} already matches ({how})"); return 0
    out.write_text(body, encoding="utf-8")
    print(f"  {d.name}: wrote {name}, {len(body):,} bytes -- {how}")
    return 1


def main() -> int:
    args = sys.argv[1:]
    if not args:
        print(__doc__); return 2
    n = 0
    for a in args:
        d = Path(a)
        if not d.is_dir():
            print(f"  skip {a}: not a directory"); continue
        try:
            n += one(d)
        except ValueError as err:
            print(f"  FAIL {d.name}: {err}")
            return 1
    print(f"restored {n} page file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
