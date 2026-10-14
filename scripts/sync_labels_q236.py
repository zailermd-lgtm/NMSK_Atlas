#!/usr/bin/env python3
"""Q236: keep the shared structure-labels block identical in both viewer templates.

viewer/labels/labels.{css,html,js} is the single source; each template carries it verbatim between `LABELS <kind> begin` / `LABELS <kind> end` marker lines
(tests/test_q236_labels.py fails if a template drifts). The page-specific parts (the engine adaptor, the draw() / hover() / apply() hooks, the theme variables)
live in the templates themselves. The per-page abbreviation table sits between `NMSK-ABBREV begin/end` and is filled by scripts/anatomy/q236/make_abbrevs.py --inject.

    python3 scripts/sync_labels_q236.py          # rewrite both templates from the fragments
    python3 scripts/sync_labels_q236.py --check  # exit 1 if a template is out of date

Only the text between the markers is replaced, and the file is re-read immediately before it is written (other agents edit these templates).
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TEMPLATES = [REPO / "viewer" / "atlas_viewer.template.html", REPO / "viewer" / "zan_atlas.template.html"]
FRAGS = {"css": REPO / "viewer/labels/labels.css", "html": REPO / "viewer/labels/labels.html", "js": REPO / "viewer/labels/labels.js"}
MARK = {"css": ("/* LABELS css begin */", "/* LABELS css end */"),
        "html": ("<!-- LABELS html begin -->", "<!-- LABELS html end -->"),
        "js": ("/* LABELS js begin */", "/* LABELS js end */")}


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
                if t.read_text(encoding="utf-8") != old:          # re-read right before writing
                    print(f"{t.name} changed while syncing; run again"); return 2
                t.write_text(new, encoding="utf-8"); print(f"synced {t.relative_to(REPO)}")
        else:
            print(f"up to date: {t.relative_to(REPO)}")
    return bad


if __name__ == "__main__":
    raise SystemExit(main())
