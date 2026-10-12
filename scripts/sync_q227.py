#!/usr/bin/env python3
"""Q227: keep the shared selection-sets block and the cut-face-fill block identical in both viewer templates.

viewer/selection/selection.{css,html,js} and viewer/cut_cap/cut_cap.js are the single sources; each template carries them verbatim between
`SELECTION <kind> begin/end` and `CUT-CAP js begin/end` marker lines (tests/test_q227.py fails if a template drifts). The cut panel's two
buttons live in viewer/cut_mode/cut_mode.html (scripts/sync_cut_mode_q197.py).

    python3 scripts/sync_q227.py          # rewrite both templates from the fragments
    python3 scripts/sync_q227.py --check  # exit 1 if a template is out of date

Only the text between the markers is replaced, and the file is re-read immediately before it is written (other agents edit these templates).
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TEMPLATES = [REPO / "viewer" / "atlas_viewer.template.html", REPO / "viewer" / "zan_atlas.template.html"]
BLOCKS = {  # name -> (fragment file, begin marker, end marker)
    "selection.css": (REPO / "viewer/selection/selection.css", "/* SELECTION css begin */", "/* SELECTION css end */"),
    "selection.html": (REPO / "viewer/selection/selection.html", "<!-- SELECTION html begin -->", "<!-- SELECTION html end -->"),
    "selection.js": (REPO / "viewer/selection/selection.js", "/* SELECTION js begin */", "/* SELECTION js end */"),
    "cut_cap.js": (REPO / "viewer/cut_cap/cut_cap.js", "/* CUT-CAP js begin */", "/* CUT-CAP js end */"),
}


def render(text: str) -> str:
    for _name, (path, b, e) in BLOCKS.items():
        frag = path.read_text(encoding="utf-8").rstrip("\n")
        if text.count(b) != 1 or text.count(e) != 1:
            raise SystemExit(f"marker pair {b!r} must occur exactly once")
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
                cur = t.read_text(encoding="utf-8")          # re-read right before writing
                if cur != old:
                    print(f"{t.name} changed while syncing; run again"); return 2
                t.write_text(new, encoding="utf-8"); print(f"synced {t.relative_to(REPO)}")
        else:
            print(f"up to date: {t.relative_to(REPO)}")
    return bad


if __name__ == "__main__":
    raise SystemExit(main())
