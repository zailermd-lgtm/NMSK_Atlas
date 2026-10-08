"""Q205 scope check: structure-by-structure comparison of two pages (geometry bytes, card).  python3 scripts/zanatomy/q205_shipdiff.py OLD_DIR NEW_DIR STEM [OUT.json]"""
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q205_pages as P  # noqa: E402


def diff(old, new, stem, listed=None):
    mo, bo = P.load_page(old, stem)
    mn, bn = P.load_page(new, stem)
    eo = {m["id"]: m for m in mo["meshes"]}
    en = {m["id"]: m for m in mn["meshes"]}
    out = {"added": sorted(set(en) - set(eo)), "removed": sorted(set(eo) - set(en)), "geometry_changed": {}, "card_only": [], "unchanged": 0}
    for i, m in en.items():
        o = eo.get(i)
        if o is None:
            continue
        pn = bn[m["vo"]: m["vo"] + m["vc"] * 6] + bn[m["io"]: m["io"] + m["ic"] * 6]
        po = bo[o["vo"]: o["vo"] + o["vc"] * 6] + bo[o["io"]: o["io"] + o["ic"] * 6]
        if pn != po or m["min"] != o["min"]:
            vo, _ = P.decode_one(o, bo)
            vn, _ = P.decode_one(m, bn)
            mv = float(np.linalg.norm(vn - vo, axis=1).max()) if len(vo) == len(vn) else None
            out["geometry_changed"][i] = {"max_vertex_change_mm": None if mv is None else round(mv, 2), "vertices": [len(vo), len(vn)]}
        elif m.get("rec") != o.get("rec") or m["name"] != o["name"]:
            out["card_only"].append(i)
        else:
            out["unchanged"] += 1
    if listed is not None:
        out["geometry_changed_but_not_listed"] = sorted(set(out["geometry_changed"]) - set(listed))
    return out


if __name__ == "__main__":
    r = diff(sys.argv[1], sys.argv[2], sys.argv[3])
    if len(sys.argv) > 4:
        Path(sys.argv[4]).write_text(json.dumps(r, indent=1))
    print({k: (len(v) if hasattr(v, "__len__") else v) for k, v in r.items()})
