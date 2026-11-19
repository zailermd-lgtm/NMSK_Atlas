#!/usr/bin/env python3
"""Q309: keep the systems / scoped-layers modules identical in both templates, and ship their table with them.

Owner (translated from Hebrew): "Also allow display by SYSTEMS with an on/off button, and by LAYERS -- for the
whole body, per system, and for the displayed systems only."

Two splices, both idempotent and both `--check`able:

1. `viewer/q309/{q309.css, sysmap.js, systoggle.js, syspeel.js, q309.js}` go into each template as one <style> +
   one <script> between the `<!-- Q309 html begin/end -->` markers, placed right after the Q306 block -- so
   NMSKHistory, NMSKShowAll, NMSKPeel, NMSKGroups, NMSKCombos and NMSKInfo all exist when this runs.

2. `data/anatomy/system_layers_q309.json`, inlined as
   `<!-- NMSK-Q309-LAYERS begin --><script id="nmsk-q309-layers">...</script><!-- NMSK-Q309-LAYERS end -->`
   right after Q306's data block. Unlike every earlier data block this one is NOT per page and needs no build-time
   `--inject`: the table is the same bytes on all six pages and the module resolves it against each page's own
   structures at load, so a stratum that matches nothing there is simply not offered. That is also why the block
   can be written here, by the sync script, and comes out of every regen byte-identical.

    python3 scripts/sync_q309.py          # rewrite both templates from the fragments
    python3 scripts/sync_q309.py --check  # exit 1 if a template is out of date
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TEMPLATES = [REPO / "viewer" / "atlas_viewer.template.html", REPO / "viewer" / "zan_atlas.template.html"]
D = REPO / "viewer" / "q309"
JS = ["sysmap.js", "systoggle.js", "syspeel.js", "q309.js"]
TABLE = REPO / "data" / "anatomy" / "system_layers_q309.json"
BEGIN, END = "<!-- Q309 html begin -->", "<!-- Q309 html end -->"
AFTER = "<!-- Q306 html end -->"
DBEGIN, DEND = "<!-- NMSK-Q309-LAYERS begin -->", "<!-- NMSK-Q309-LAYERS end -->"
DAFTER = "<!-- NMSK-Q306 end -->"


def fragment() -> str:
    css = (D / "q309.css").read_text(encoding="utf-8").rstrip("\n")
    js = "\n".join((D / n).read_text(encoding="utf-8").rstrip("\n") for n in JS)
    return f"<style>\n{css}\n</style>\n<script>\n{js}\n</script>"


def data_block() -> str:
    t = json.loads(TABLE.read_text(encoding="utf-8"))
    # compact, and </script> can never appear inside: asserted rather than escaped
    s = json.dumps(t, ensure_ascii=False, separators=(",", ":"))
    if "</script" in s.lower():
        raise SystemExit("the Q309 table contains a </script> sequence")
    return DBEGIN + '<script type="application/json" id="nmsk-q309-layers">' + s + "</script>" + DEND


def render(text: str) -> str:
    # 1. the modules
    if text.count(BEGIN) == 0 and text.count(END) == 0:
        if text.count(AFTER) != 1:
            raise SystemExit("Q309 needs the Q306 end marker exactly once to place itself after")
        i = text.index(AFTER) + len(AFTER)
        text = text[:i] + "\n" + BEGIN + "\n" + END + text[i:]
    if text.count(BEGIN) != 1 or text.count(END) != 1:
        raise SystemExit("Q309 marker pair must occur exactly once")
    i, j = text.index(BEGIN) + len(BEGIN), text.index(END)
    text = text[:i] + "\n" + fragment() + "\n" + text[j:]
    # 2. the table, right after Q306's data block
    if text.count(DBEGIN) == 0 and text.count(DEND) == 0:
        if text.count(DAFTER) != 1:
            raise SystemExit("Q309 needs the NMSK-Q306 end marker exactly once to place its table after")
        k = text.index(DAFTER) + len(DAFTER)
        text = text[:k] + "\n" + data_block() + text[k:]
    if text.count(DBEGIN) != 1 or text.count(DEND) != 1:
        raise SystemExit("the NMSK-Q309-LAYERS marker pair must occur exactly once")
    a, b = text.index(DBEGIN), text.index(DEND) + len(DEND)
    text = text[:a] + data_block() + text[b:]
    return text


def main() -> int:
    check = "--check" in sys.argv
    bad = 0
    for t in TEMPLATES:
        old = t.read_text(encoding="utf-8")
        new = render(old)
        if new != old:
            if check:
                print(f"out of date: {t.relative_to(REPO)}")
                bad = 1
            else:
                t.write_text(new, encoding="utf-8")
                print(f"synced {t.relative_to(REPO)}")
        else:
            print(f"up to date: {t.relative_to(REPO)}")
    return bad


if __name__ == "__main__":
    raise SystemExit(main())
