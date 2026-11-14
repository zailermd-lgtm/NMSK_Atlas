#!/usr/bin/env python3
"""Q290: keep the shared two-finger zoom helper (NMSKPinch) identical in both viewer templates.

viewer/pinch/pinch.{css,js} is the single source; each template carries it verbatim, as one <style> + one <script>, between
the `<!-- PINCH html begin -->` / `<!-- PINCH html end -->` marker lines (placed before the optional clinical add-ons, which use it).

    python3 scripts/sync_pinch_q290.py          # rewrite both templates from the fragments
    python3 scripts/sync_pinch_q290.py --check  # exit 1 if a template is out of date
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TEMPLATES = [REPO / "viewer" / "atlas_viewer.template.html", REPO / "viewer" / "zan_atlas.template.html"]
CSS = REPO / "viewer/pinch/pinch.css"
JS = REPO / "viewer/pinch/pinch.js"
BEGIN, END = "<!-- PINCH html begin -->", "<!-- PINCH html end -->"


def fragment() -> str:
    css = CSS.read_text(encoding="utf-8").rstrip("\n")
    js = JS.read_text(encoding="utf-8").rstrip("\n")
    return f"<style>\n{css}\n</style>\n<script>\n{js}\n</script>"


def render(text: str) -> str:
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        raise SystemExit("PINCH marker pair must occur exactly once")
    i, j = text.index(BEGIN) + len(BEGIN), text.index(END)
    return text[:i] + "\n" + fragment() + "\n" + text[j:]


def main() -> int:
    check = "--check" in sys.argv
    bad = 0
    for t in TEMPLATES:
        old = t.read_text(encoding="utf-8")
        new = render(old)
        if new != old:
            if check:
                print(f"out of date: {t.relative_to(REPO)}"); bad = 1
            else:
                t.write_text(new, encoding="utf-8"); print(f"synced {t.relative_to(REPO)}")
        else:
            print(f"up to date: {t.relative_to(REPO)}")
    return bad


if __name__ == "__main__":
    raise SystemExit(main())
