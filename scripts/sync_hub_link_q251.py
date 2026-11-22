#!/usr/bin/env python3
"""Q251: a small, always-visible "Hub" control in both viewer templates, linking back to the atlas hub
(viewer/atlas_hub.html, published at HUB_URL) so a viewer page is never a dead end -- the person can always
get back to the model-picker to switch models.

Mirrors the hub's OWN outbound linking mechanism exactly (viewer/atlas_hub.html: `<a class="open"
href="..." target="_blank" rel="noopener">Open viewer ↗</a>`), since that is the one proven to work from
inside the sandboxed artifact iframe this project runs in -- a plain cross-origin anchor, not window.open()
or a same-tab navigation.

Lives in the existing toolbar of each template so it picks up the toolbar's own visual style and stays
visible in Cut mode exactly like the other toolbar buttons (same requirement as the Q236 label legend):
  - atlas_viewer.template.html ("own"/Imaging pages): inside #tools, styled as a `.tool` button.
  - zan_atlas.template.html (Z / Base / Combined pages): inside #topright, styled as a `.pill` button.

Inserted idempotently at fixed anchors (same pattern as scripts/sync_symview_q237.py), so the script can be
re-run safely on a template another change touched.

    python3 scripts/sync_hub_link_q251.py          # rewrite both templates in viewer/
    python3 scripts/sync_hub_link_q251.py --check  # exit 1 if a template is out of date
    python3 scripts/sync_hub_link_q251.py --dir DIR  # operate on DIR/{atlas_viewer,zan_atlas}.template.html
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
HUB_URL = "https://claude.ai/artifact/LyQVpCZcYWXQT5Ek8M984T"
HUB_TITLE = "Back to the atlas hub — choose a different model"

OWN_CSS = ('.tool[aria-pressed="true"]{background:var(--accent);color:var(--accent-ink);border-color:var(--accent)}\n'
           'a.tool{text-decoration:none;color:inherit;cursor:pointer;display:inline-flex;align-items:center}')
OWN_HTML = ('      <a class="tool" id="t-hub" href="' + HUB_URL + '" target="_blank" rel="noopener" title="' + HUB_TITLE + '">Hub</a>\n'
            '      <button class="tool" id="t-iso" aria-pressed="false">Isolate</button>')

ZAN_CSS = ('  .pill.on{background:color-mix(in srgb,var(--accent) 14%,transparent)}\n'
           '  a.pill{text-decoration:none;color:inherit;cursor:pointer;display:inline-block}')
ZAN_HTML = ('  <a class="pill" id="t-hub" href="' + HUB_URL + '" target="_blank" rel="noopener" title="' + HUB_TITLE + '">hub</a>\n'
            '  <button class="pill" id="btn-panel">layers</button>')

# (css anchor-old, css-new), (html anchor-old, html-new) -- `new` contains `old`; a template already carrying
# `new` is left untouched (idempotent); `old` must occur exactly once.
EDITS = {
    "own": {"css": (OWN_CSS.split("\n", 1)[0], OWN_CSS), "html": (OWN_HTML.split("\n", 1)[1], OWN_HTML)},
    "zan": {"css": (ZAN_CSS.split("\n", 1)[0], ZAN_CSS), "html": (ZAN_HTML.split("\n", 1)[1], ZAN_HTML)},
}


def apply_edits(text: str, kind: str) -> str:
    for old, new in EDITS[kind].values():
        if new in text:
            continue
        if text.count(old) != 1:
            raise SystemExit(f"anchor not found exactly once for {kind}: {old[:60]!r}")
        text = text.replace(old, new, 1)
    return text


def render(text: str, kind: str) -> str:
    return apply_edits(text, kind)


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    check = "--check" in argv
    d = REPO / "viewer"
    if "--dir" in argv:
        d = Path(argv[argv.index("--dir") + 1])
    templates = [(d / "atlas_viewer.template.html", "own"), (d / "zan_atlas.template.html", "zan")]
    bad = 0
    for t, kind in templates:
        if not t.is_file():
            continue
        old = t.read_text(encoding="utf-8")
        new = render(old, kind)
        if new != old:
            if check:
                print(f"out of date: {t}"); bad = 1
            else:
                if t.read_text(encoding="utf-8") != old:
                    print(f"{t.name} changed while syncing; run again"); return 2
                t.write_text(new, encoding="utf-8"); print(f"synced {t}")
        else:
            print(f"up to date: {t}")
    return bad


if __name__ == "__main__":
    raise SystemExit(main())
