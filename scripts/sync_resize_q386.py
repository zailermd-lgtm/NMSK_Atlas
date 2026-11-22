#!/usr/bin/env python3
"""Q386: keep the resize / text-size module identical in both templates.

Owner (translated): "All the windows must also be allowed to shrink or grow in screen area, and scroll as needed, and control of the font size."

viewer/resize/{resize.css, resize.js} are the single source; each template carries them verbatim as one <style> + one <script>, between the
`<!-- Q386 html begin -->` / `<!-- Q386 html end -->` marker lines, right after the Q382 block (NMSKMove and NMSKLayout exist by then).
The boxes themselves are NMSKMove's (viewer/q305/move.js, synced by sync_q305.py); the Settings rows are NMSKLayout's (sync_layout_q382.py).

    python3 scripts/sync_resize_q386.py          # rewrite both templates from the fragments
    python3 scripts/sync_resize_q386.py --check  # exit 1 if a template is out of date
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TEMPLATES = [REPO / "viewer" / "atlas_viewer.template.html", REPO / "viewer" / "zan_atlas.template.html"]
D = REPO / "viewer" / "resize"
JS = ["resize.js"]
BEGIN, END = "<!-- Q386 html begin -->", "<!-- Q386 html end -->"
AFTER = "<!-- Q382 html end -->"


def fragment() -> str:
    css = (D / "resize.css").read_text(encoding="utf-8").rstrip("\n")
    js = "\n".join((D / n).read_text(encoding="utf-8").rstrip("\n") for n in JS)
    return f"<style>\n{css}\n</style>\n<script>\n{js}\n</script>"


def render(text: str) -> str:
    if text.count(BEGIN) == 0 and text.count(END) == 0:
        # first run: open the marker pair immediately after the Q382 block
        if text.count(AFTER) != 1:
            raise SystemExit("Q386 needs the Q382 end marker exactly once to place itself after")
        i = text.index(AFTER) + len(AFTER)
        text = text[:i] + "\n" + BEGIN + "\n" + END + text[i:]
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        raise SystemExit("Q386 marker pair must occur exactly once")
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
