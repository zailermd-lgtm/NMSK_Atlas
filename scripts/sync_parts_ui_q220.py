#!/usr/bin/env python3
"""Q220: keep the shared Parts-UI block identical in both viewer templates.

viewer/parts_ui/parts_ui.{css,html,js} is the single source; each template carries it verbatim between
`PARTS-UI <kind> begin` / `PARTS-UI <kind> end` marker lines (tests/test_q220.py fails if a template drifts).

    python3 scripts/sync_parts_ui_q220.py          # rewrite both templates from the fragments
    python3 scripts/sync_parts_ui_q220.py --check  # exit 1 if a template is out of date
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TEMPLATES = [REPO / "viewer" / "atlas_viewer.template.html", REPO / "viewer" / "zan_atlas.template.html"]
FRAGS = {"css": REPO / "viewer/parts_ui/parts_ui.css", "html": REPO / "viewer/parts_ui/parts_ui.html",
         "js": REPO / "viewer/parts_ui/parts_ui.js"}
MARK = {"css": ("/* PARTS-UI css begin */", "/* PARTS-UI css end */"),
        "html": ("<!-- PARTS-UI html begin -->", "<!-- PARTS-UI html end -->"),
        "js": ("/* PARTS-UI js begin */", "/* PARTS-UI js end */")}


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
