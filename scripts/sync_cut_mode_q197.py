#!/usr/bin/env python3
"""Q197: keep the shared Cut-mode block identical in both viewer templates.

viewer/cut_mode/cut_mode.{css,html,js} is the single source; each template carries it verbatim between
`CUT-MODE <kind> begin` / `CUT-MODE <kind> end` marker lines (tests/test_cut_mode_q197.py fails if a template drifts).

    python3 scripts/sync_cut_mode_q197.py          # rewrite both templates from the fragments
    python3 scripts/sync_cut_mode_q197.py --check  # exit 1 if a template is out of date
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TEMPLATES = [REPO / "viewer" / "atlas_viewer.template.html", REPO / "viewer" / "zan_atlas.template.html"]
FRAGS = {"css": REPO / "viewer/cut_mode/cut_mode.css", "html": REPO / "viewer/cut_mode/cut_mode.html",
         "js": REPO / "viewer/cut_mode/cut_mode.js"}
MARK = {"css": ("/* CUT-MODE css begin */", "/* CUT-MODE css end */"),
        "html": ("<!-- CUT-MODE html begin -->", "<!-- CUT-MODE html end -->"),
        "js": ("/* CUT-MODE js begin */", "/* CUT-MODE js end */")}


def render(text: str) -> str:
    for kind, (b, e) in MARK.items():
        frag = FRAGS[kind].read_text(encoding="utf-8").rstrip("\n")
        if text.count(b) != 1 or text.count(e) != 1:
            raise SystemExit(f"marker pair for {kind} must occur exactly once")
        i, j = text.index(b) + len(b), text.index(e)
        # markers sit on their own lines; the fragment goes between them verbatim
        text = text[:i] + "\n" + frag + "\n" + text[j:]
    return text


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
