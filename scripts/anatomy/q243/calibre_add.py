#!/usr/bin/env python3
"""Q243: add the new pelvic vessels (and nothing else) of a Q243 page dir to data/anatomy/calibre.json (the Q240 calibre table), additively: kind (a / v), mean tube diameter estimated from the shipped mesh
(scripts/anatomy/q240/calibre.py) and the level of the Q240 ladder. Every other entry of the file is left byte for byte as it is.
    python3 scripts/anatomy/q243/calibre_add.py KEY PAGE_DIR        (KEY = own_f | comb_f | base_f, only used for the message; the table key is the page dir name)
Run scripts/anatomy/q240/make_calibre.py --inject PAGE_DIR afterwards to put the page's table into the page."""
from __future__ import annotations
import json, sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts")); sys.path.insert(0, str(REPO / "scripts/anatomy/q240")); sys.path.insert(0, str(REPO / "scripts/anatomy/q236"))
sys.path.insert(0, str(REPO / "scripts/anatomy/q220"))
import numpy as np  # noqa: E402
import make_calibre as MC  # noqa: E402
from calibre import tube_diameter  # noqa: E402
from pages import PAGES  # noqa: E402
sys.path.insert(0, str(REPO / "scripts/anatomy"))
from scripts.anatomy.q243.vessels import VESSELS  # noqa: E402


def main(key, d):
    d = Path(d)
    dirkey = d.name
    html = d / PAGES[dirkey]
    import build_parts_sidecar as sc
    kind, meshes = sc.load_page(html)
    ids = {v[0] for v in VESSELS}
    doc = json.loads(MC.OUT.read_text(encoding="utf-8"))
    pg = doc["pages"].setdefault(dirkey, {"source": str(d.relative_to(REPO)) if d.is_relative_to(REPO) else str(d), "count": 0, "c": {}})
    n = 0
    for sid, sd, cat, V, F in meshes:
        if sid not in ids:
            continue
        k = MC.kind_of(sid, cat)
        if not k:
            raise SystemExit(f"{sid}: no kind from {cat}")
        r = tube_diameter(np.asarray(V), np.asarray(F))
        lv, pr = MC.level_of(k, r["diameter_mm"], sid)
        pg["c"][sid] = [k, r["diameter_mm"], lv, pr]
        n += 1
    pg["c"] = dict(sorted(pg["c"].items()))
    pg["count"] = len(pg["c"])
    cnt = Counter((v[0], v[2]) for v in pg["c"].values())
    pg["by_kind_level"] = {f"{k}{l}": c for (k, l), c in sorted(cnt.items())}
    pg["q243_added"] = sorted(s for s in pg["c"] if s in ids)
    MC.OUT.write_text(json.dumps(doc, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"calibre_add: {dirkey}: {n} Q243 vessels added ({key}); table now {pg['count']} entries")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
