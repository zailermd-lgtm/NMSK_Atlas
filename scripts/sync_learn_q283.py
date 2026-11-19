#!/usr/bin/env python3
"""Q283: keep the shared Learn block identical in both viewer templates.

viewer/learn/learn.{css,html,js} and viewer/learn/learn_data.json (built by scripts/anatomy/q283/build_learn.py) are the
single source; each template carries them verbatim between `LEARN <kind> begin` / `LEARN <kind> end` marker lines (the data
as a <script type="application/json" id="nmsk-learn"> block).

    python3 scripts/sync_learn_q283.py          # rewrite both templates from the fragments
    python3 scripts/sync_learn_q283.py --check  # exit 1 if a template is out of date
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TEMPLATES = [REPO / "viewer" / "atlas_viewer.template.html", REPO / "viewer" / "zan_atlas.template.html"]
FRAGS = {"css": REPO / "viewer/learn/learn.css", "html": REPO / "viewer/learn/learn.html", "js": REPO / "viewer/learn/learn.js",
         "data": REPO / "viewer/learn/learn_data.json"}
MARK = {"css": ("/* LEARN css begin */", "/* LEARN css end */"),
        "html": ("<!-- LEARN html begin -->", "<!-- LEARN html end -->"),
        "data": ("<!-- LEARN data begin -->", "<!-- LEARN data end -->"),
        "js": ("/* LEARN js begin */", "/* LEARN js end */")}


def frag(kind: str) -> str:
    text = FRAGS[kind].read_text(encoding="utf-8").rstrip("\n")
    if kind == "data":
        text = '<script type="application/json" id="nmsk-learn">' + text.replace("</", "<\\/") + "</script>"
    return text


def render(text: str) -> str:
    for kind, (b, e) in MARK.items():
        if text.count(b) != 1 or text.count(e) != 1:
            raise SystemExit(f"marker pair for {kind} must occur exactly once")
        i, j = text.index(b) + len(b), text.index(e)
        text = text[:i] + "\n" + frag(kind) + "\n" + text[j:]
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
                if t.read_text(encoding="utf-8") != old:
                    print(f"{t.name} changed while syncing; run again"); return 2
                t.write_text(new, encoding="utf-8"); print(f"synced {t.relative_to(REPO)}")
        else:
            print(f"up to date: {t.relative_to(REPO)}")
    return bad


if __name__ == "__main__":
    raise SystemExit(main())
