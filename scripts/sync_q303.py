#!/usr/bin/env python3
"""Q303: keep the auto-focus, the four-pane layout, "facing me" + saved views and the nerve emphasis identical in both
templates.

viewer/q303/{q303.css, pca.js, step.js, px.js, nervepass.js, target.js, autofocus.js, fourup.js, views.js, nerves.js, q303.js} are the
single source; each template carries them verbatim as one <style> + one <script>, between the `<!-- Q303 html begin -->`
/ `<!-- Q303 html end -->` marker lines (right after the Q301 block, so NMSKHistory, NMSKTips, NMSKShowAll,
NMSKModelReset, NMSKGroups, NMSKCombos and NMSKInfo already exist when these run and the per-engine glue can reach all
of them).

    python3 scripts/sync_q303.py          # rewrite both templates from the fragments
    python3 scripts/sync_q303.py --check  # exit 1 if a template is out of date
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TEMPLATES = [REPO / "viewer" / "atlas_viewer.template.html", REPO / "viewer" / "zan_atlas.template.html"]
D = REPO / "viewer" / "q303"
# load order matters: pca, step and nervepass hold no DOM and no state, target before autofocus / views (they read it),
# and q303.js last because it mounts everything into Q301's View group
JS = ["pca.js", "step.js", "px.js", "nervepass.js", "target.js", "autofocus.js", "fourup.js", "views.js", "nerves.js", "q303.js"]
BEGIN, END = "<!-- Q303 html begin -->", "<!-- Q303 html end -->"


def fragment() -> str:
    css = (D / "q303.css").read_text(encoding="utf-8").rstrip("\n")
    js = "\n".join((D / n).read_text(encoding="utf-8").rstrip("\n") for n in JS)
    return f"<style>\n{css}\n</style>\n<script>\n{js}\n</script>"


def render(text: str) -> str:
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        raise SystemExit("Q303 marker pair must occur exactly once")
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
