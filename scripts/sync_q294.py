#!/usr/bin/env python3
"""Q294: keep the shared undo / redo / reset history, the measure tools, the part-slices panel and the less-text helpers
(abbreviation popup, "i" tips) identical in both viewer templates.

viewer/q294/{q294.css, q294.html, history.js, measure.js, tips.js, partslice.js} are the single source; each template carries
them verbatim, as one <style> + the panel markup + one <script>, between the `<!-- Q294 html begin -->` / `<!-- Q294 html end -->`
marker lines (right after the PINCH block, before the optional add-ons, which register their image panes with NMSKMeasure).

    python3 scripts/sync_q294.py          # rewrite both templates from the fragments
    python3 scripts/sync_q294.py --check  # exit 1 if a template is out of date
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TEMPLATES = [REPO / "viewer" / "atlas_viewer.template.html", REPO / "viewer" / "zan_atlas.template.html"]
D = REPO / "viewer" / "q294"
JS = ["history.js", "measure.js", "tips.js", "partslice.js"]
BEGIN, END = "<!-- Q294 html begin -->", "<!-- Q294 html end -->"


def fragment() -> str:
    css = (D / "q294.css").read_text(encoding="utf-8").rstrip("\n")
    html = (D / "q294.html").read_text(encoding="utf-8").rstrip("\n")
    js = "\n".join((D / n).read_text(encoding="utf-8").rstrip("\n") for n in JS)
    return f"<style>\n{css}\n</style>\n{html}\n<script>\n{js}\n</script>"


def render(text: str) -> str:
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        raise SystemExit("Q294 marker pair must occur exactly once")
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
