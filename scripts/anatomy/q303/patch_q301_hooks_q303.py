#!/usr/bin/env python3
"""Q303: two small, idempotent additions to Q301's own modules, because this round needs them.

Exactly the gap Q301 recorded in its own H0: "a module cannot be in a list built before it started", which is why Q301
gave Q300's NMSKShowAll an `add(source)`. Q303's controls are owned by MODULES that start after Q301's control bar was
built from one table, and its compatibility rows are owned by a round that did not exist when Q301's table was written.
So:
  viewer/q301/groups.js  gains  addTo(groupKey, member)   -- join an EXISTING group (this round joins "View"), with the
                                                             same member shape the table uses, re-rendering the sheet if
                                                             that group happens to be open
  viewer/q301/combos.js  gains  addPair(row)              -- add one compatibility row, ignoring a duplicate pair

Both files are carried into the two templates by scripts/sync_q301.py as usual, so nothing else changes.

    python3 scripts/anatomy/q303/patch_q301_hooks_q303.py          # apply (idempotent)
    python3 scripts/anatomy/q303/patch_q301_hooks_q303.py --check   # exit 1 if a file still needs it
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
GROUPS = REPO / "viewer" / "q301" / "groups.js"
COMBOS = REPO / "viewer" / "q301" / "combos.js"

GROUPS_EDIT = (
    "    open:openSheet, close:closeSheet, isOpen:function(){ return cur; }, refresh:paint,",
    "    /* Q303: a module that starts AFTER this bar was built cannot be in the table it was built from -- the same gap\n"
    "       Q301 closed in Q300's NMSKShowAll with add(source). A member joins an EXISTING group here, in the same shape\n"
    "       the table uses, so a later round adds to View instead of adding a new top-level button. */\n"
    "    addTo:function(key, m){\n"
    "      if (!m || !(m.el || m.adopt || m.label)) return false;\n"
    "      var g = null; G.forEach(function(q){ if (q.key === key) g = q; });\n"
    "      if (!g) return false;\n"
    "      g.members.push(m);\n"
    "      if (cur === key){ closeSheet(); openSheet(key); } else paint();\n"
    "      return true;\n"
    "    },\n"
    "    open:openSheet, close:closeSheet, isOpen:function(){ return cur; }, refresh:paint,",
)

COMBOS_EDIT = (
    "    add:function(p){ if (p && p.key && typeof p.active === \"function\"){ P[p.key] = p; sig = \"\"; refresh(); } },",
    "    add:function(p){ if (p && p.key && typeof p.active === \"function\"){ P[p.key] = p; sig = \"\"; refresh(); } },\n"
    "    /* Q303: one more row in the same table, from a round that did not exist when the table was written. A pair\n"
    "       already present is left alone, so re-registering is harmless. */\n"
    "    addPair:function(r){\n"
    "      if (!r || !r.a || !r.b) return false;\n"
    "      for (var i = 0; i < PAIRS.length; i++) if (PAIRS[i].a === r.a && PAIRS[i].b === r.b) return false;\n"
    "      PAIRS.push(r); sig = \"\"; refresh(); return true;\n"
    "    },",
)


def one(path: Path, old: str, new: str, check: bool) -> int:
    t = path.read_text(encoding="utf-8")
    if new in t:
        print(f"up to date: {path.relative_to(REPO)}")
        return 0
    n = t.count(old)
    if n != 1:
        raise SystemExit(f"{path.name}: anchor occurs {n} times, expected 1")
    if check:
        print(f"out of date: {path.relative_to(REPO)}")
        return 1
    path.write_text(t.replace(old, new), encoding="utf-8")
    print(f"patched {path.relative_to(REPO)}")
    return 0


def main() -> int:
    check = "--check" in sys.argv
    return max(one(GROUPS, *GROUPS_EDIT, check=check), one(COMBOS, *COMBOS_EDIT, check=check))


if __name__ == "__main__":
    raise SystemExit(main())
