#!/usr/bin/env python3
"""Q256: keep the shared "Nerve groups" fragment (viewer/nerve_groups/) in both viewer templates.

viewer/nerve_groups/nerve_groups.{css,html,js} is the single source (same pattern as scripts/sync_parts_ui_q220.py);
viewer/nerve_groups/glue_{own,zan}.js is the per-engine instantiation (same pattern as scripts/sync_symview_q237.py's glue_*.js --
it only calls the shared controller's public API plus the EXISTING selCtl.markIds/clear/preset, no new engine hooks). Each template
carries them verbatim between `NERVE-GROUPS <kind> begin` / `NERVE-GROUPS <kind> end` marker lines (tests/test_q256_nerve_groups.py
fails if a template drifts). The marker pairs are inserted idempotently right after the SELECTION fragment's own end markers (css/html/
js) and right after the SYMVIEW glue block (so selCtl already exists), so the script can be re-run on a template another change
touched (it fails loudly when an anchor is gone):

    python3 scripts/sync_nerve_groups_q256.py          # rewrite both templates in viewer/
    python3 scripts/sync_nerve_groups_q256.py --check  # exit 1 if a template is out of date
"""
from __future__ import annotations
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TEMPLATES = {"own": REPO / "viewer" / "atlas_viewer.template.html", "zan": REPO / "viewer" / "zan_atlas.template.html"}
FR = REPO / "viewer" / "nerve_groups"
MARK = {"css": ("/* NERVE-GROUPS css begin */", "/* NERVE-GROUPS css end */"), "html": ("<!-- NERVE-GROUPS html begin -->", "<!-- NERVE-GROUPS html end -->"),
        "js": ("/* NERVE-GROUPS js begin */", "/* NERVE-GROUPS js end */"), "glue": ("/* NERVE-GROUPS glue begin */", "/* NERVE-GROUPS glue end */")}
# anchor = insert the new marker pair right AFTER this line (same text in both templates); must occur exactly once
ANCHOR_AFTER = {"css": "/* SELECTION css end */", "html": "<!-- SELECTION html end -->", "js": "/* SELECTION js end */", "glue": "/* SYMVIEW glue end */"}


def frag(kind):
    return {"css": FR / "nerve_groups.css", "html": FR / "nerve_groups.html", "js": FR / "nerve_groups.js"}.get(kind)


def render(text: str, eng: str) -> str:
    glue = (FR / ("glue_%s.js" % eng)).read_text(encoding="utf-8").rstrip("\n")
    for kind, (b, e) in MARK.items():
        if b in text:
            if text.count(b) != 1 or text.count(e) != 1:
                raise SystemExit("marker pair for %s must occur exactly once" % kind)
            continue
        anchor = ANCHOR_AFTER[kind]
        if text.count(anchor) != 1:
            raise SystemExit("%s: anchor for the %s marker pair must occur exactly once: %r (found %d)" % (eng, kind, anchor, text.count(anchor)))
        text = text.replace(anchor, "%s\n%s\n%s" % (anchor, b, e), 1)
    for kind, (b, e) in MARK.items():
        body = glue if kind == "glue" else frag(kind).read_text(encoding="utf-8").rstrip("\n")
        i, j = text.index(b) + len(b), text.index(e)
        text = text[:i] + "\n" + body + "\n" + text[j:]
    return text


def main() -> int:
    check = "--check" in sys.argv
    bad = 0
    for eng, t in TEMPLATES.items():
        old = t.read_text(encoding="utf-8")
        new = render(old, eng)
        if new != old:
            if check:
                print("out of date: %s" % t.relative_to(REPO)); bad = 1
            else:
                t.write_text(new, encoding="utf-8"); print("synced %s" % t.relative_to(REPO))
        else:
            print("up to date: %s" % t.relative_to(REPO))
    return bad


if __name__ == "__main__":
    raise SystemExit(main())
