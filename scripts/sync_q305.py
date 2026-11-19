#!/usr/bin/env python3
"""Q305: keep the movable boxes identical in both templates.

Owner (translated from Hebrew): "let the various boxes on the screen be moved around."

viewer/q305/{q305.css, guard.js, move.js, q305.js} are the single source; each template carries them verbatim as one
<style> + one <script>, between the `<!-- Q305 html begin -->` / `<!-- Q305 html end -->` marker lines, right after the
Q303 block -- so NMSKHistory, NMSKShowAll, NMSKModelReset, NMSKGroups and NMSKInfo are already defined when these run.
The module boots itself (it waits for the history and the control bar to start), so unlike Q301 and Q303 this round
needs NO per-engine glue and NO `patch_engines` script at all: a box is moved by its own `translate`, which composes
with whatever `transform`, `left` and `top` the stylesheets and the earlier rounds' placement code set. That is also
why every earlier round's page block comes out of the regen byte-identical.

    python3 scripts/sync_q305.py          # rewrite both templates from the fragments
    python3 scripts/sync_q305.py --check  # exit 1 if a template is out of date
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TEMPLATES = [REPO / "viewer" / "atlas_viewer.template.html", REPO / "viewer" / "zan_atlas.template.html"]
D = REPO / "viewer" / "q305"
# load order: guard holds no state and no DOM, move needs it, q305.js last because it is the boot and names the boxes
JS = ["guard.js", "move.js", "q305.js"]
BEGIN, END = "<!-- Q305 html begin -->", "<!-- Q305 html end -->"
AFTER = "<!-- Q303 html end -->"


def fragment() -> str:
    css = (D / "q305.css").read_text(encoding="utf-8").rstrip("\n")
    js = "\n".join((D / n).read_text(encoding="utf-8").rstrip("\n") for n in JS)
    return f"<style>\n{css}\n</style>\n<script>\n{js}\n</script>"


def render(text: str) -> str:
    if text.count(BEGIN) == 0 and text.count(END) == 0:
        # first run: open the marker pair immediately after the Q303 block
        if text.count(AFTER) != 1:
            raise SystemExit("Q305 needs the Q303 end marker exactly once to place itself after")
        i = text.index(AFTER) + len(AFTER)
        text = text[:i] + "\n" + BEGIN + "\n" + END + text[i:]
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        raise SystemExit("Q305 marker pair must occur exactly once")
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
