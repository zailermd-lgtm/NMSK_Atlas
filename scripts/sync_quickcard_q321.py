#!/usr/bin/env python3
"""Q321: keep the quick card (viewer/quickcard/) identical in both templates.

Owner (translated): "when clicking an organ or a region, the first thing that must open is the name of what was clicked, with
hide, fade, show only, or just select ... boxes sized to their buttons ... placed around the model, not on it."

`viewer/quickcard/{quickcard.css, quickcard.js}` go into each template as one <style> + one <script> between the
`<!-- Q321 html begin -->` / `<!-- Q321 html end -->` markers, placed right after the Q309 block. The module is inert until an
engine calls `NMSKQuickCard.start(adaptor)`; only the Z engine does.

    python3 scripts/sync_quickcard_q321.py          # rewrite both templates from the fragments
    python3 scripts/sync_quickcard_q321.py --check  # exit 1 if a template is out of date
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TEMPLATES = [REPO / "viewer" / "atlas_viewer.template.html", REPO / "viewer" / "zan_atlas.template.html"]
D = REPO / "viewer" / "quickcard"
BEGIN, END = "<!-- Q321 html begin -->", "<!-- Q321 html end -->"
AFTER = "<!-- Q309 html end -->"


def fragment() -> str:
    css = (D / "quickcard.css").read_text(encoding="utf-8").rstrip("\n")
    js = (D / "quickcard.js").read_text(encoding="utf-8").rstrip("\n")
    return f"<style>\n{css}\n</style>\n<script>\n{js}\n</script>"


def render(text: str) -> str:
    if text.count(BEGIN) == 0 and text.count(END) == 0:
        if text.count(AFTER) != 1:
            raise SystemExit("Q321 needs the Q309 end marker exactly once to place itself after")
        i = text.index(AFTER) + len(AFTER)
        text = text[:i] + "\n" + BEGIN + "\n" + END + text[i:]
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        raise SystemExit("Q321 marker pair must occur exactly once")
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
                print(f"out of date: {t.relative_to(REPO)}")
                bad = 1
            else:
                t.write_text(new, encoding="utf-8")
                print(f"synced {t.relative_to(REPO)}")
        else:
            print(f"up to date: {t.relative_to(REPO)}")
    return bad


if __name__ == "__main__":
    raise SystemExit(main())
