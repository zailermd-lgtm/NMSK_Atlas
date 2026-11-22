#!/usr/bin/env python3
"""Q301: give Q300's "Show everything" guard one more entry point.

Q300's NMSKShowAll takes its hiding paths in start({sources:[...]}), which is right for the paths the engine's own glue
knows about. Q301 adds three more that are owned by MODULES, not by the glue -- the radiographic render style, the depth
peel and the fat default -- and a module cannot be in a list that was built before it started. So NMSKShowAll gains
`add(source)`, the same descriptor shape, registered after start(). Four lines, additive, and `sync_q300.py` then carries
it into both templates as usual.

    python3 scripts/anatomy/q301/patch_showall_q301.py          # apply (idempotent)
    python3 scripts/anatomy/q301/patch_showall_q301.py --check   # exit 1 if it still needs it
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
F = REPO / "viewer" / "q300" / "showall.js"
OLD = "    refresh:render,"
NEW = """    /* Q301: a path owned by a MODULE rather than by the engine's glue (the render style, the depth peel, the fat)
       cannot be in a list built before it started, so it registers itself here, with the same descriptor. */
    add:function(s){
      if (!s || !s.key || typeof s.active !== "function" || typeof s.clear !== "function") return false;
      S = S.filter(function(q){ return q.key !== s.key; });
      S.push(s); sig = ""; render();
      return true;
    },
    refresh:render,"""


def main() -> int:
    check = "--check" in sys.argv
    t = F.read_text(encoding="utf-8")
    if "add:function(s){" in t:
        print(f"up to date: {F.relative_to(REPO)}")
        return 0
    if t.count(OLD) != 1:
        raise SystemExit(f"{F.name}: anchor occurs {t.count(OLD)} times, expected 1")
    if check:
        print(f"out of date: {F.relative_to(REPO)}")
        return 1
    F.write_text(t.replace(OLD, NEW, 1), encoding="utf-8")
    print(f"patched {F.relative_to(REPO)} (NMSKShowAll.add)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
