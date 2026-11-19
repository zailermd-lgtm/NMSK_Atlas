#!/usr/bin/env python3
"""Q382: keep the layout / zoom-chip settings module identical in both templates.

Owner (translated): "the dimensions window should be visible on every size change for 10 seconds and then disappear ... in Settings it can be
changed"; "allow moving the different boxes on the screen by dragging ... and also in SETTINGS".

viewer/layout/{layout.css, layout.js} are the single source; each template carries them verbatim as one <style> + one <script>, between the
`<!-- Q382 html begin -->` / `<!-- Q382 html end -->` marker lines, right after the Q305 block (NMSKMove, NMSKInfo and NMSKGroups exist by then).
The boxes themselves are NMSKMove's (viewer/q305/move.js, synced by sync_q305.py); the zoom chip is NMSKPinch's (viewer/pinch/pinch.js, sync_pinch_q290.py).

    python3 scripts/sync_layout_q382.py          # rewrite both templates from the fragments
    python3 scripts/sync_layout_q382.py --check  # exit 1 if a template is out of date
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TEMPLATES = [REPO / "viewer" / "atlas_viewer.template.html", REPO / "viewer" / "zan_atlas.template.html"]
D = REPO / "viewer" / "layout"
JS = ["layout.js"]
BEGIN, END = "<!-- Q382 html begin -->", "<!-- Q382 html end -->"
AFTER = "<!-- Q305 html end -->"


def fragment() -> str:
    css = (D / "layout.css").read_text(encoding="utf-8").rstrip("\n")
    js = "\n".join((D / n).read_text(encoding="utf-8").rstrip("\n") for n in JS)
    return f"<style>\n{css}\n</style>\n<script>\n{js}\n</script>"


def render(text: str) -> str:
    if text.count(BEGIN) == 0 and text.count(END) == 0:
        # first run: open the marker pair immediately after the Q305 block
        if text.count(AFTER) != 1:
            raise SystemExit("Q382 needs the Q305 end marker exactly once to place itself after")
        i = text.index(AFTER) + len(AFTER)
        text = text[:i] + "\n" + BEGIN + "\n" + END + text[i:]
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        raise SystemExit("Q382 marker pair must occur exactly once")
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
