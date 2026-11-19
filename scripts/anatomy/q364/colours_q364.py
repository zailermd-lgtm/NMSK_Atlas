#!/usr/bin/env python3
"""Q364: per-structure display colours for the Z engine (Base pages), from data/anatomy/structure_colours_q364.json.

    python3 scripts/anatomy/q364/colours_q364.py --inject DIR...    # put the page's resolved table into the page html (and index.html) of each page dir
    python3 scripts/anatomy/q364/colours_q364.py --check DIR...     # print what each page would get, change nothing

The page embeds {"v":1,"c":{id:[colour, alpha]}} between the `NMSK-COLOURS begin/end` markers of the Z template (the
nmsk-calibre precedent, Q240): only ids that exist on that page, colour '#rrggbb' or '@<layer>' (the layer's theme colour).
Committed data, no recompute; run by scripts/regen_template_only.py for the Base pages.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DATA = REPO / "data/anatomy/structure_colours_q364.json"
BEGIN, END = "<!-- NMSK-COLOURS begin -->", "<!-- NMSK-COLOURS end -->"
MAN_RE = re.compile(r"^window\.__ANATOMY_MANIFEST__=(.*);$", re.M)
HEX = re.compile(r"^#[0-9a-f]{6}$")
LAYERS = {"bone", "cartilage", "joint", "insertion", "muscle", "fascia", "bursa", "nerve", "cns", "vessel", "lymph", "viscera", "fat", "skin"}


def load() -> list[dict]:
    d = json.loads(DATA.read_text(encoding="utf-8"))
    assert d.get("schema") == "nmsk.structure_colours.v1", DATA
    for e in d["entries"]:
        h = e["hex"]
        assert HEX.match(h) or (h.startswith("@") and h[1:] in LAYERS), f"bad colour {h!r}"
        assert 0 < float(e.get("alpha", 1)) <= 1, f"bad alpha in {e}"
    return d["entries"]


def table_for(ids: list[str], entries: list[dict]) -> dict[str, list]:
    tab = {}
    for e in entries:
        a = round(float(e.get("alpha", 1)), 3)
        for b in e["ids"]:
            for i in (b, b + "_l", b + "_r"):
                if i in ids:
                    tab[i] = [e["hex"], a]
    return tab


def block(tab: dict) -> str:
    js = json.dumps({"v": 1, "c": {k: tab[k] for k in sorted(tab)}}, separators=(",", ":")).replace("<", "\\u003c")
    return f'{BEGIN}<script type="application/json" id="nmsk-colours">{js}</script>{END}'


def inject(d: Path, write=True) -> int:
    entries = load()
    n = 0
    for f in sorted(d.glob("*.html")):
        s = f.read_text(encoding="utf-8")
        if s.count(BEGIN) != 1 or s.count(END) != 1:
            continue
        m = MAN_RE.search(s)
        if not m:
            continue
        ids = {x["id"] for x in json.loads(m.group(1))["meshes"]}
        tab = table_for(ids, entries)
        if write:
            i, j = s.index(BEGIN), s.index(END) + len(END)
            f.write_text(s[:i] + block(tab) + s[j:], encoding="utf-8")
        print(f"colours: {f.name}: {len(tab)} structures" + ("" if write else " (check only)"))
        n += 1
    if not n:
        raise SystemExit(f"no page with the NMSK-COLOURS markers and a manifest in {d}")
    return n


def main(argv: list[str]) -> int:
    if argv and argv[0] in ("--inject", "--check") and argv[1:]:
        for a in argv[1:]:
            inject(Path(a), write=argv[0] == "--inject")
        return 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
