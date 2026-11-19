#!/usr/bin/env python3
"""Q306: the one engine-side line this round needs, and the two-round-old defect it fixes.

Q306's browser run found that on the OWN engine (the two Imaging pages) a query returning ZERO structures
never reaches the Q298 bar at all:

    if (!rows.length){ listBox.innerHTML = '<p class="hint">Nothing matches that.</p>'; return; }
    ...
    if (window.NMSKQ298 && NMSKQ298.ready()) NMSKQ298.afterList(...);   // never reached

-- an early `return` before the `afterList` call. The Z engine has no such branch: it writes its "No match."
line and then calls `afterList` anyway.

This is a **Q298 defect two rounds old**, not one this round introduced, and it is worst exactly where it
matters most: `cited_but_not_shipped` explanations and Q306's concept cards are the answer precisely WHEN no
structure matched, so on the Imaging pages they have never been shown. `psoas minor` on an Imaging page is
the case the owner asked about, and it returned a bare "Nothing matches that."

The fix is one line per template: tell the bar before returning. `afterList([])` is already safe with an
empty list -- it is what the Z engine effectively passes in the same situation.

Idempotent, and `--check`able like every other sync / patch script in this project.

    python3 scripts/anatomy/q306/patch_engines_q306.py
    python3 scripts/anatomy/q306/patch_engines_q306.py --check
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
OWN = REPO / "viewer/atlas_viewer.template.html"

OLD = ("""if (!rows.length){ listBox.innerHTML = '<p class="hint">Nothing matches that.</p>'; return; }""")
NEW = ("""if (!rows.length){ listBox.innerHTML = '<p class="hint">Nothing matches that.</p>';\n"""
       """    /* Q306: tell the Q298 bar even when nothing matched. Without this the early return skipped the\n"""
       """       afterList call below, so on this engine a cited-but-not-shipped explanation and a Q306 concept\n"""
       """       card -- which are the answer PRECISELY when no structure matched -- were never shown. */\n"""
       """    if (window.NMSKQ298 && NMSKQ298.ready()) NMSKQ298.afterList([]);\n"""
       """    return; }""")


def main() -> int:
    check = "--check" in sys.argv
    s = OWN.read_text(encoding="utf-8")
    done = NEW in s
    if done:
        print("up to date: %s" % OWN.relative_to(REPO))
        return 0
    if s.count(OLD) != 1:
        print("Q306: the own engine's zero-row branch must occur exactly once (found %d)" % s.count(OLD))
        return 1
    if check:
        print("out of date: %s" % OWN.relative_to(REPO))
        return 1
    OWN.write_text(s.replace(OLD, NEW), encoding="utf-8")
    print("patched %s" % OWN.relative_to(REPO))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
