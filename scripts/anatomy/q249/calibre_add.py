#!/usr/bin/env python3
"""Q249: add the new rule-based nerves (and nothing else) of a Q249 page dir to data/anatomy/calibre.json (the Q240 calibre table), additively: kind n, mean tube diameter estimated from the shipped mesh
(scripts/anatomy/q240/calibre.py) and the level of the Q240 nerve ladder (trunk >= 4 mm or a named trunk, branches 2-4, small 1-2, fine < 1).  Every other entry of the file is left byte for byte.
    python3 scripts/anatomy/q249/calibre_add.py KEY PAGE_DIR        (KEY = own_m ... base_f; the table key is the page dir name)
Run scripts/anatomy/q240/make_calibre.py --inject PAGE_DIR afterwards."""
from __future__ import annotations
import json, sys
from collections import Counter
from pathlib import Path
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts")); sys.path.insert(0, str(REPO / "scripts/anatomy/q240")); sys.path.insert(0, str(REPO / "scripts/anatomy/q236")); sys.path.insert(0, str(REPO / "scripts/anatomy/q220"))
import numpy as np  # noqa: E402
import make_calibre as MC  # noqa: E402
from calibre import tube_diameter  # noqa: E402


def main(key, d):
    d = Path(d); dirkey = d.name
    z = np.load(REPO / f"data/derived/Q249_rule_{key}.npz"); j = json.loads((REPO / f"data/derived/Q249_rule_{key}.json").read_text())
    doc = json.loads(MC.OUT.read_text(encoding="utf-8"))
    pg = doc["pages"].setdefault(dirkey, {"source": str(d), "count": 0, "c": {}})
    ids = [s for s in j["cards"] if f"{s}__v" in z.files]
    for sid in ids:
        k = MC.kind_of(sid, "nerve")
        if not k:
            raise SystemExit(f"{sid}: no nerve kind from the id (rename it so the Q240 NERVE pattern matches)")
        r = tube_diameter(z[f"{sid}__v"].astype(float), z[f"{sid}__f"])
        lv, pr = MC.level_of(k, r["diameter_mm"], sid)
        pg["c"][sid] = [k, r["diameter_mm"], lv, pr]
    pg["c"] = dict(sorted(pg["c"].items()))
    pg["count"] = len(pg["c"])
    cnt = Counter((v[0], v[2]) for v in pg["c"].values())
    pg["by_kind_level"] = {f"{k}{l}": c for (k, l), c in sorted(cnt.items())}
    pg["q249_added"] = sorted(ids)
    MC.OUT.write_text(json.dumps(doc, separators=(",", ":")) + "\n", encoding="utf-8")
    print(f"calibre_add: {dirkey}: {len(ids)} Q249 nerves added ({key}); table now {pg['count']} entries")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
