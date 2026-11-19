#!/usr/bin/env python3
"""Q322: keep the MUSCLE INNERVATION mode (viewer/innervation/) identical in both templates.

`viewer/innervation/{innervation.css, innervation.js}` go into each template as one <style> + one <script> between the
`<!-- Q322 html begin -->` / `<!-- Q322 html end -->` markers, placed right after the Q321 block. The module registers the
"inn" workspace mode (viewer/modes/modes.js) only when the page's sidecar innervation_q322.json loads
(scripts/anatomy/q322/build_sidecar_q322.py), so a page without the sidecar is unchanged.

    python3 scripts/sync_innervation_q322.py          # rewrite both templates from the fragments
    python3 scripts/sync_innervation_q322.py --check  # exit 1 if a template is out of date
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TEMPLATES = [REPO / "viewer" / "atlas_viewer.template.html", REPO / "viewer" / "zan_atlas.template.html"]
D = REPO / "viewer" / "innervation"
BEGIN, END = "<!-- Q322 html begin -->", "<!-- Q322 html end -->"
AFTER = "<!-- Q321 html end -->"


def fragment() -> str:
    css = (D / "innervation.css").read_text(encoding="utf-8").rstrip("\n")
    js = (D / "innervation.js").read_text(encoding="utf-8").rstrip("\n")
    return f"<style>\n{css}\n</style>\n<script>\n{js}\n</script>"


def render(text: str) -> str:
    if text.count(BEGIN) == 0 and text.count(END) == 0:
        if text.count(AFTER) != 1:
            raise SystemExit("Q322 needs the Q321 end marker exactly once to place itself after")
        i = text.index(AFTER) + len(AFTER)
        text = text[:i] + "\n" + BEGIN + "\n" + END + text[i:]
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        raise SystemExit("Q322 marker pair must occur exactly once")
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
