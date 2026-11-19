#!/usr/bin/env python3
"""Q298: keep the shared search / multi-select / expansion modules identical in both viewer templates.

The owner's report was that the search could not find the iliotibial tract by any name he would use, that there was no easy
way to mark SEVERAL structures, and that after picking one there was no way to reach the ones next to it, related to it or
in its functional group. The fix is one set of modules used by both engines, so they behave the same:

viewer/q298/{q298.css, q298.html, search.js, bar.js, multi.js, expand.js, q298.js} is the single source; each template
carries them verbatim as one <style> + the (empty) markup + one <script>, between the `<!-- Q298 html begin -->` /
`<!-- Q298 html end -->` marker lines, right after the Q294 block (NMSKHistory must already exist, because every batch
mark is one undo step of it).

The per-page data -- the resolved aliases, the group memberships, the measured adjacency and the relation table -- is NOT
here: it is the `nmsk-q298` block, filled per page by scripts/anatomy/q298/build_search_q298.py --inject.

    python3 scripts/sync_q298.py          # rewrite both templates from the fragments
    python3 scripts/sync_q298.py --check  # exit 1 if a template is out of date
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TEMPLATES = [REPO / "viewer" / "atlas_viewer.template.html", REPO / "viewer" / "zan_atlas.template.html"]
D = REPO / "viewer" / "q298"
JS = ["search.js", "bar.js", "multi.js", "expand.js", "q298.js"]
BEGIN, END = "<!-- Q298 html begin -->", "<!-- Q298 html end -->"


def fragment() -> str:
    css = (D / "q298.css").read_text(encoding="utf-8").rstrip("\n")
    html = (D / "q298.html").read_text(encoding="utf-8").rstrip("\n")
    js = "\n".join((D / n).read_text(encoding="utf-8").rstrip("\n") for n in JS)
    return f"<style>\n{css}\n</style>\n{html}\n<script>\n{js}\n</script>"


def render(text: str) -> str:
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        raise SystemExit("Q298 marker pair must occur exactly once")
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
