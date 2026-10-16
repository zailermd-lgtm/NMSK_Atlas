#!/usr/bin/env python3
"""Q236: abbreviation table for the six pages.

    python3 scripts/anatomy/q236/make_abbrevs.py                  # (re)write data/anatomy/abbreviations.json from the latest page dirs
    python3 scripts/anatomy/q236/make_abbrevs.py --inject DIR...  # put the page's own table into the page html (and index.html) of each page dir

The table of a page is computed from that page's own structure names / sides (abbrev.py, deterministic), so the build path never depends on a stale file:
--inject writes it between the `NMSK-ABBREV begin/end` markers of the template as <script type="application/json" id="nmsk-abbrev">{"v":1,"a":{id:[abbr, generated, short name]}}</script>.
data/anatomy/abbreviations.json is the reviewable copy (the convention, the KNOWN table, every page's map); tests/test_q236_abbrev.py checks it against the generator.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import abbrev  # noqa: E402
from pages import PAGES, REPO, read_structs  # noqa: E402

OUT = REPO / "data/anatomy/abbreviations.json"
SRC_ROOTS = ["build/q236", "build/q235", "build/q234", "build/q233"]        # first dir that has the page wins
BEGIN, END = "<!-- NMSK-ABBREV begin -->", "<!-- NMSK-ABBREV end -->"
CONVENTION = ("BASE[-R|-L]: side suffix from the structure's side. Established abbreviations only from KNOWN (each a standard published one); everything else is generated "
              "(g=1): initials of the content words, or the first three letters of a single word; collisions lengthen the generated ones, never the known ones.")


def page_path(d: str) -> Path | None:
    for r in SRC_ROOTS:
        p = REPO / r / d / PAGES[d]
        if p.exists():
            return p
    return None


def table_for(html: str) -> dict:
    return abbrev.build(read_structs(html))


def block(tab: dict) -> str:
    js = json.dumps({"v": 1, "a": tab}, ensure_ascii=False, separators=(",", ":")).replace("<", "\\u003c")
    return f'{BEGIN}<script type="application/json" id="nmsk-abbrev">{js}</script>{END}'


def inject(d: Path) -> int:
    n = 0
    for f in sorted(d.glob("*.html")):
        s = f.read_text(encoding="utf-8")
        if s.count(BEGIN) != 1 or s.count(END) != 1:
            continue
        i, j = s.index(BEGIN), s.index(END) + len(END)
        tab = table_for(s)
        f.write_text(s[:i] + block(tab) + s[j:], encoding="utf-8")
        print(f"abbreviations: {f.relative_to(REPO) if f.is_relative_to(REPO) else f}: {len(tab)} structures, {sum(1 for v in tab.values() if not v[1])} established")
        n += 1
    if not n:
        raise SystemExit(f"no page with the NMSK-ABBREV markers in {d}")
    return n


def main(argv: list[str]) -> int:
    if argv and argv[0] == "--inject":
        for a in argv[1:]:
            inject(Path(a))
        return 0
    pages = {}
    for d in PAGES:
        p = page_path(d)
        if p is None:
            print(f"skip {d}: no page found under {SRC_ROOTS}")
            continue
        tab = table_for(p.read_text(encoding="utf-8"))
        pages[d] = {"source": str(p.parent.relative_to(REPO)), "count": len(tab), "map": {k: v[:2] for k, v in sorted(tab.items())}}
        print(d, p.parent.relative_to(REPO), len(tab))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({"version": 1, "convention": CONVENTION, "known": dict(sorted(abbrev.KNOWN.items())), "reserved": sorted(abbrev.RESERVED), "pages": pages},
                              ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print("wrote", OUT.relative_to(REPO), OUT.stat().st_size, "bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
