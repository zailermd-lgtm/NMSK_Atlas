#!/usr/bin/env python3
"""Q306: keep the search-coverage module identical in both templates, and give its data block a home.

Owner (translated from Hebrew): "pelvic tilt is missing, functional muscle groups are missing, psoas minor
is missing. Check what else is missing and fix it, so the search works as well as possible."

Two splices, both idempotent and both `--check`able:

1. `viewer/q306/{q306.css, q306.js}` go into each template as one <style> + one <script> between the
   `<!-- Q306 html begin/end -->` markers, placed right after the Q305 block -- so NMSKQ298Bar, NMSKMulti
   and the rest are already defined when this runs. Q298's bar calls `NMSKQ306.render(...)` through one
   guarded `if (window.NMSKQ306)`, so a page without this block behaves exactly as it did before.

2. The EMPTY `<!-- NMSK-Q306 begin --><script id="nmsk-q306">{}</script><!-- NMSK-Q306 end -->` data block,
   placed immediately after Q298's own data block. `scripts/anatomy/q306/build_search_q306.py --inject`
   fills it per page at build time. It is a SEPARATE block from Q298's on purpose: Q298's comes out of
   every regen byte-identical, which is what `scripts/anatomy/q303/assert_blocks_q303.py` checks.

    python3 scripts/sync_q306.py          # rewrite both templates from the fragments
    python3 scripts/sync_q306.py --check  # exit 1 if a template is out of date
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TEMPLATES = [REPO / "viewer" / "atlas_viewer.template.html", REPO / "viewer" / "zan_atlas.template.html"]
D = REPO / "viewer" / "q306"
JS = ["q306.js"]
BEGIN, END = "<!-- Q306 html begin -->", "<!-- Q306 html end -->"
AFTER = "<!-- Q305 html end -->"
DBEGIN, DEND = "<!-- NMSK-Q306 begin -->", "<!-- NMSK-Q306 end -->"
DBLOCK = DBEGIN + '<script type="application/json" id="nmsk-q306">{}</script>' + DEND
DAFTER = "<!-- NMSK-Q298 end -->"


def fragment() -> str:
    css = (D / "q306.css").read_text(encoding="utf-8").rstrip("\n")
    js = "\n".join((D / n).read_text(encoding="utf-8").rstrip("\n") for n in JS)
    return f"<style>\n{css}\n</style>\n<script>\n{js}\n</script>"


def render(text: str) -> str:
    # 1. the module
    if text.count(BEGIN) == 0 and text.count(END) == 0:
        if text.count(AFTER) != 1:
            raise SystemExit("Q306 needs the Q305 end marker exactly once to place itself after")
        i = text.index(AFTER) + len(AFTER)
        text = text[:i] + "\n" + BEGIN + "\n" + END + text[i:]
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        raise SystemExit("Q306 marker pair must occur exactly once")
    i, j = text.index(BEGIN) + len(BEGIN), text.index(END)
    text = text[:i] + "\n" + fragment() + "\n" + text[j:]
    # 2. the data block, right after Q298's -- the build step fills it, the template ships it empty
    if text.count(DBEGIN) == 0 and text.count(DEND) == 0:
        if text.count(DAFTER) != 1:
            raise SystemExit("Q306 needs the NMSK-Q298 end marker exactly once to place its block after")
        k = text.index(DAFTER) + len(DAFTER)
        text = text[:k] + "\n" + DBLOCK + text[k:]
    if text.count(DBEGIN) != 1 or text.count(DEND) != 1:
        raise SystemExit("the NMSK-Q306 marker pair must occur exactly once")
    return text


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
