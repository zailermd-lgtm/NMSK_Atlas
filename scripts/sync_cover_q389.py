#!/usr/bin/env python3
"""Q389: keep the display-covering ("underwear") module in the Z template in step with its single source.

viewer/cover/{cover.css, cover.js} are the module (state, control, the bound-vertex maths), viewer/cover/glue_zan.js the WebGL
adaptor.  The covering exists on the Base pages only, which are built from viewer/zan_atlas.template.html, so only that
template carries it (the own engine's template is not touched).  Four places, all owned by this script:
  1. the page's data block      `<!-- NMSK-COVER begin -->...<!-- NMSK-COVER end -->`  (empty `{}` in the template; filled per page by
                                scripts/anatomy/q389/make_cover_q389.py --inject at regen) -- placed after the NMSK-COLOURS block
  2. the module                 `<!-- Q389 html begin -->` .. `<!-- Q389 html end -->`  -- one <style> + one <script>, after the Q386 block
  3. the engine glue            `/* COVER glue begin */` .. `/* COVER glue end */`      -- after the POSE glue (it reads the posed skin)
  4. the draw call              one line in the scene pass, right after the opaque paints

    python3 scripts/sync_cover_q389.py          # rewrite the template from the fragments
    python3 scripts/sync_cover_q389.py --check  # exit 1 if the template is out of date
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TEMPLATE = REPO / "viewer" / "zan_atlas.template.html"
D = REPO / "viewer" / "cover"

DATA_BEGIN, DATA_END = "<!-- NMSK-COVER begin -->", "<!-- NMSK-COVER end -->"
DATA_LINE = DATA_BEGIN + '<script type="application/json" id="nmsk-cover">{}</script>' + DATA_END
DATA_AFTER = "<!-- NMSK-COLOURS end -->"
MOD_BEGIN, MOD_END = "<!-- Q389 html begin -->", "<!-- Q389 html end -->"
MOD_AFTER = "<!-- Q386 html end -->"
GLUE_BEGIN, GLUE_END = "/* COVER glue begin */", "/* COVER glue end */"
GLUE_AFTER = "/* POSE glue end */"
DRAW_ANCHOR = "      opa.forEach(function(B){ paint(B,1,solid); });\n"
DRAW_LINE = "      if (coverZ) coverZ.draw();      /* Q389: the display covering (not a structure: no picking, no labels) */\n"


def once(text: str, needle: str, what: str) -> int:
    if text.count(needle) != 1:
        raise SystemExit(f"Q389 sync: {what} must occur exactly once in the template (found {text.count(needle)})")
    return text.index(needle)


def block(text: str, begin: str, end: str, after: str, body: str, what: str) -> str:
    if text.count(begin) == 0 and text.count(end) == 0:
        i = once(text, after, f"the anchor of {what}") + len(after)
        text = text[:i] + "\n" + begin + "\n" + end + text[i:]
    once(text, begin, what + " begin marker")
    once(text, end, what + " end marker")
    i, j = text.index(begin) + len(begin), text.index(end)
    return text[:i] + "\n" + body + "\n" + text[j:]


def render(text: str) -> str:
    if DATA_BEGIN not in text:
        i = once(text, DATA_AFTER, "the NMSK-COLOURS block") + len(DATA_AFTER)
        text = text[:i] + "\n" + DATA_LINE + text[i:]
    once(text, DATA_BEGIN, "the NMSK-COVER data block")
    css = (D / "cover.css").read_text(encoding="utf-8").rstrip("\n")
    js = (D / "cover.js").read_text(encoding="utf-8").rstrip("\n")
    text = block(text, MOD_BEGIN, MOD_END, MOD_AFTER, f"<style>\n{css}\n</style>\n<script>\n{js}\n</script>", "the Q389 module")
    glue = (D / "glue_zan.js").read_text(encoding="utf-8").rstrip("\n")
    text = block(text, GLUE_BEGIN, GLUE_END, GLUE_AFTER, glue, "the COVER glue")
    if DRAW_LINE not in text:
        i = once(text, DRAW_ANCHOR, "the opaque paint of the scene pass") + len(DRAW_ANCHOR)
        text = text[:i] + DRAW_LINE + text[i:]
    once(text, DRAW_LINE, "the covering's draw call")
    return text


def main() -> int:
    check = "--check" in sys.argv
    old = TEMPLATE.read_text(encoding="utf-8")
    new = render(old)
    if new != old:
        if check:
            print(f"out of date: {TEMPLATE.relative_to(REPO)}")
            return 1
        TEMPLATE.write_text(new, encoding="utf-8")
        print(f"synced {TEMPLATE.relative_to(REPO)}")
    else:
        print(f"up to date: {TEMPLATE.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
