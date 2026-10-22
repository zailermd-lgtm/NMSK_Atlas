#!/usr/bin/env python3
"""Q272: keep the shared clinical WORKSPACE MODES fragment (viewer/modes/) in both viewer templates.

viewer/modes/modes.{css,html,js} is the single source (same pattern as scripts/sync_nerve_groups_q256.py); viewer/modes/glue_{own,zan}.js
is the per-engine host object (camera / selection / sheets snapshot + restore, the 3-D element to dock -- public page functions only).
Each template carries them verbatim between `MODES <kind> begin` / `MODES <kind> end` marker lines (tests/test_q272_modes.py fails if a
template drifts). The marker pairs are inserted idempotently: css / js / glue right after the NERVE-GROUPS pairs of the same kind, html at
BODY level right after the first optional add-on script tag (the NERVE-GROUPS html anchor sits inside the structure rail, which a mode
hides), so the script can be re-run on a template another change touched (it fails loudly when an anchor is gone):

    python3 scripts/sync_modes_q272.py          # rewrite both templates in viewer/
    python3 scripts/sync_modes_q272.py --check  # exit 1 if a template is out of date
"""
from __future__ import annotations
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TEMPLATES = {"own": REPO / "viewer" / "atlas_viewer.template.html", "zan": REPO / "viewer" / "zan_atlas.template.html"}
FR = REPO / "viewer" / "modes"
MARK = {"css": ("/* MODES css begin */", "/* MODES css end */"), "html": ("<!-- MODES html begin -->", "<!-- MODES html end -->"),
        "js": ("/* MODES js begin */", "/* MODES js end */"), "glue": ("/* MODES glue begin */", "/* MODES glue end */")}
# anchor = insert the new marker pair right AFTER this line (same text in both templates); must occur exactly once
ANCHOR_AFTER = {"css": "/* NERVE-GROUPS css end */", "html": '<script src="clinical_needle_tool.js"></script>', "js": "/* NERVE-GROUPS js end */",
                "glue": "/* NERVE-GROUPS glue end */"}


def frag(kind):
    return {"css": FR / "modes.css", "html": FR / "modes.html", "js": FR / "modes.js"}.get(kind)


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
