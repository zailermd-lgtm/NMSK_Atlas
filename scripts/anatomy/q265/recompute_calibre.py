#!/usr/bin/env python3
"""Q265: per-page recompute of data/anatomy/calibre.json from build/q265_pre (same method Q258-Q263 used:
make_calibre.py's own table_for()/validate(), not the Q249-only additive calibre_add.py alone, so the new ids get
real entries). Reads/writes the WHOLE calibre.json doc on every call (one dname at a time, not all six at once):
this round's own disk budget is tight (591 MB free, each page bundle ~40-60 MB) after an earlier environment
lockout (see PROJECT_STATE.md Q265), so pages are built, calibred and deleted ONE AT A TIME rather than all six
`build/q265_pre/<dir>` directories existing at once.
    python3 scripts/anatomy/q265/recompute_calibre.py DNAME      (DNAME = one of pages.PAGES' own keys, e.g. viewer_m_hr)
    python3 scripts/anatomy/q265/recompute_calibre.py            (all six, if all six build/q265_pre dirs happen to exist)
"""
from __future__ import annotations
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts")); sys.path.insert(0, str(REPO / "scripts/anatomy/q240")); sys.path.insert(0, str(REPO / "scripts/anatomy/q236"))
import make_calibre as MC  # noqa: E402
from pages import PAGES    # noqa: E402

PRE = REPO / "build/q265_pre"


def one(dname, fname):
    doc = json.loads(MC.OUT.read_text(encoding="utf-8"))
    p = PRE / dname / fname
    if not p.exists():
        print("MISSING", p); return
    tab = MC.table_for(p)
    from collections import Counter
    cnt = Counter((v[0], v[2]) for v in tab.values())
    doc["pages"][dname] = {"source": str(p.parent.relative_to(REPO)), "count": len(tab), "c": {k: v for k, v in sorted(tab.items())},
                            "by_kind_level": {f"{k}{l}": n for (k, l), n in sorted(cnt.items())}, "checks": MC.validate(tab)}
    print(dname, len(tab), dict(sorted(doc["pages"][dname]["by_kind_level"].items())))
    MC.OUT.write_text(json.dumps(doc, separators=(",", ":")) + "\n", encoding="utf-8")
    print("wrote", MC.OUT.relative_to(REPO), MC.OUT.stat().st_size, "bytes")


def main():
    if len(sys.argv) > 1:
        dname = sys.argv[1]
        one(dname, PAGES[dname])
    else:
        for dname, fname in PAGES.items():
            one(dname, fname)


if __name__ == "__main__":
    main()
