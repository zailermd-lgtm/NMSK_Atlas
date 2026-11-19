#!/usr/bin/env python3
"""Q300: keep the "show everything" guard, the model reset and the bone-through control identical in both templates.

viewer/q300/{q300.css, showall.js, modelreset.js, bonexray.js} are the single source; each template carries them verbatim
as one <style> + one <script>, between the `<!-- Q300 html begin -->` / `<!-- Q300 html end -->` marker lines (right after
the Q294 block, so NMSKHistory and NMSKTips already exist when these run and the engines can reach all three).

    python3 scripts/sync_q300.py          # rewrite both templates from the fragments
    python3 scripts/sync_q300.py --check  # exit 1 if a template is out of date
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TEMPLATES = [REPO / "viewer" / "atlas_viewer.template.html", REPO / "viewer" / "zan_atlas.template.html"]
D = REPO / "viewer" / "q300"
JS = ["showall.js", "modelreset.js", "bonexray.js"]
BEGIN, END = "<!-- Q300 html begin -->", "<!-- Q300 html end -->"


def fragment() -> str:
    css = (D / "q300.css").read_text(encoding="utf-8").rstrip("\n")
    js = "\n".join((D / n).read_text(encoding="utf-8").rstrip("\n") for n in JS)
    return f"<style>\n{css}\n</style>\n<script>\n{js}\n</script>"


def render(text: str) -> str:
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        raise SystemExit("Q300 marker pair must occur exactly once")
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
