#!/usr/bin/env python3
"""Q301: keep the one control bar, the group sheets, the radiographic render styles, the depth peel, the fat default and
the circled-i panel identical in both templates.

viewer/q301/{q301.css, tissue.js, combos.js, info.js, render.js, peel.js, fat.js, groups.js, q301.js} are the single
source; each template carries them verbatim as one <style> + one <script>, between the `<!-- Q301 html begin -->` /
`<!-- Q301 html end -->` marker lines (right after the Q300 block, so NMSKHistory, NMSKTips, NMSKShowAll and
NMSKModelReset already exist when these run and the per-engine glue can reach all of them).

    python3 scripts/sync_q301.py          # rewrite both templates from the fragments
    python3 scripts/sync_q301.py --check  # exit 1 if a template is out of date
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TEMPLATES = [REPO / "viewer" / "atlas_viewer.template.html", REPO / "viewer" / "zan_atlas.template.html"]
D = REPO / "viewer" / "q301"
# load order matters: tissue and combos hold no DOM, info/groups are mounted by q301.js last
JS = ["tissue.js", "combos.js", "info.js", "render.js", "peel.js", "fat.js", "groups.js", "q301.js"]
BEGIN, END = "<!-- Q301 html begin -->", "<!-- Q301 html end -->"


def fragment() -> str:
    css = (D / "q301.css").read_text(encoding="utf-8").rstrip("\n")
    js = "\n".join((D / n).read_text(encoding="utf-8").rstrip("\n") for n in JS)
    return f"<style>\n{css}\n</style>\n<script>\n{js}\n</script>"


def render(text: str) -> str:
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        raise SystemExit("Q301 marker pair must occur exactly once")
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
