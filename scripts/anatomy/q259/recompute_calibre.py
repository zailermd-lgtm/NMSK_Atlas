#!/usr/bin/env python3
"""Q259: full per-page recompute of data/anatomy/calibre.json from build/q259_pre (same method Q258 used: make_calibre.py's
own table_for()/validate(), not the Q249-only additive calibre_add.py alone, so the new nerve ids get real entries).
    python3 scripts/anatomy/q259/recompute_calibre.py
"""
from __future__ import annotations
import json, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts")); sys.path.insert(0, str(REPO / "scripts/anatomy/q240")); sys.path.insert(0, str(REPO / "scripts/anatomy/q236"))
import make_calibre as MC  # noqa: E402
from pages import PAGES    # noqa: E402

PRE = REPO / "build/q259_pre"


def main():
    doc = json.loads(MC.OUT.read_text(encoding="utf-8"))
    for dname, fname in PAGES.items():
        p = PRE / dname / fname
        if not p.exists():
            print("MISSING", p); continue
        tab = MC.table_for(p)
        from collections import Counter
        cnt = Counter((v[0], v[2]) for v in tab.values())
        doc["pages"][dname] = {"source": str(p.parent.relative_to(REPO)), "count": len(tab), "c": {k: v for k, v in sorted(tab.items())},
                                "by_kind_level": {f"{k}{l}": n for (k, l), n in sorted(cnt.items())}, "checks": MC.validate(tab)}
        print(dname, len(tab), dict(sorted(doc["pages"][dname]["by_kind_level"].items())))
    MC.OUT.write_text(json.dumps(doc, separators=(",", ":")) + "\n", encoding="utf-8")
    print("wrote", MC.OUT.relative_to(REPO), MC.OUT.stat().st_size, "bytes")


if __name__ == "__main__":
    main()
