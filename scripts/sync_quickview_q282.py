#!/usr/bin/env python3
"""Q282: keep the shared Quick view block identical in both viewer templates.

viewer/quickview/quickview.{css,html,js} is the single source; each template carries it verbatim between
`QUICKVIEW <kind> begin` / `QUICKVIEW <kind> end` marker lines (tests/test_q282.py fails if a template drifts).

    python3 scripts/sync_quickview_q282.py          # rewrite both templates from the fragments
    python3 scripts/sync_quickview_q282.py --check  # exit 1 if a template is out of date
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TEMPLATES = [REPO / "viewer" / "atlas_viewer.template.html", REPO / "viewer" / "zan_atlas.template.html"]
FRAGS = {"css": REPO / "viewer/quickview/quickview.css", "html": REPO / "viewer/quickview/quickview.html",
         "js": REPO / "viewer/quickview/quickview.js"}
MARK = {"css": ("/* QUICKVIEW css begin */", "/* QUICKVIEW css end */"),
        "html": ("<!-- QUICKVIEW html begin -->", "<!-- QUICKVIEW html end -->"),
        "js": ("/* QUICKVIEW js begin */", "/* QUICKVIEW js end */")}


def render(text: str) -> str:
    for kind, (b, e) in MARK.items():
        frag = FRAGS[kind].read_text(encoding="utf-8").rstrip("\n")
        if text.count(b) != 1 or text.count(e) != 1:
            raise SystemExit(f"marker pair for {kind} must occur exactly once")
        i, j = text.index(b) + len(b), text.index(e)
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
                cur = t.read_text(encoding="utf-8")
                if cur != old:
                    print(f"{t.name} changed while syncing; run again"); return 2
                t.write_text(new, encoding="utf-8"); print(f"synced {t.relative_to(REPO)}")
        else:
            print(f"up to date: {t.relative_to(REPO)}")
    return bad


if __name__ == "__main__":
    raise SystemExit(main())
