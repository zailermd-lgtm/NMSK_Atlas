#!/usr/bin/env python3
"""Q343: keep the name card's group families + Parts chooser (viewer/groups342/) identical in both templates.

Owner (translated): "select groups of muscle fibres of the large muscles instead of the whole muscle ... ONE button
'Related structures' ... a group of ANATOMY TRAINS ... a group by INNERVATION [root, peripheral, cerebral]".

`viewer/groups342/{groups342.css, groups342.js}` go into each template as one <style> + one <script> between the
`<!-- Q343 html begin -->` / `<!-- Q343 html end -->` markers, placed right after the Q321 (name card) block, whose
registry (`NMSKQuickCard.family` / `.addon`) it registers with at load. Inert where no engine starts the card (own engine);
on a page without the sidecar `groups_q342.json` the two families say "None" and no Parts chooser shows.

    python3 scripts/sync_groups342_q343.py          # rewrite both templates from the fragments
    python3 scripts/sync_groups342_q343.py --check  # exit 1 if a template is out of date
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TEMPLATES = [REPO / "viewer" / "atlas_viewer.template.html", REPO / "viewer" / "zan_atlas.template.html"]
D = REPO / "viewer" / "groups342"
BEGIN, END = "<!-- Q343 html begin -->", "<!-- Q343 html end -->"
AFTER = "<!-- Q321 html end -->"


def fragment() -> str:
    css = (D / "groups342.css").read_text(encoding="utf-8").rstrip("\n")
    js = (D / "groups342.js").read_text(encoding="utf-8").rstrip("\n")
    return f"<style>\n{css}\n</style>\n<script>\n{js}\n</script>"


def render(text: str) -> str:
    if text.count(BEGIN) == 0 and text.count(END) == 0:
        if text.count(AFTER) != 1:
            raise SystemExit("Q343 needs the Q321 end marker exactly once to place itself after")
        i = text.index(AFTER) + len(AFTER)
        text = text[:i] + "\n" + BEGIN + "\n" + END + text[i:]
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        raise SystemExit("Q343 marker pair must occur exactly once")
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
