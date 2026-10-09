#!/usr/bin/env python3
"""Q202 scope check: per page, which structures differ from the page it was patched from (position + index bytes, manifest entry); everything else must be byte-identical.
    python3 scripts/zanatomy/q202_scopecheck.py -> data/derived/Q202_ship_diff.json"""
import json, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.zanatomy import q202_pages as P

PAIRS = {"base_f": ("build/q197/viewer_base_female", "build/q202/viewer_base_female"), "fit_f": ("build/q199/viewer_zan_female", "build/q202/viewer_zan_female"),
         "fit_m": ("build/q201/viewer_zan_vhm", "build/q202/viewer_zan_vhm"), "base_m": ("build/q197/viewer_zan_atlas", None)}


def diff(old, new, stem):
    m0, b0 = P.load_page(REPO / old, stem); m1, b1 = P.load_page(REPO / new, stem)
    e0 = {m["id"]: m for m in m0["meshes"]}
    out = {"changed": [], "added": [], "removed": [], "unchanged": 0}
    for m in m1["meshes"]:
        o = e0.get(m["id"])
        if o is None:
            out["added"].append(m["id"]); continue
        same = (b1[m["vo"]: m["vo"] + m["vc"] * 6] == b0[o["vo"]: o["vo"] + o["vc"] * 6] and b1[m["io"]: m["io"] + m["ic"] * 6] == b0[o["io"]: o["io"] + o["ic"] * 6]
                and {k: v for k, v in m.items() if k not in ("vo", "io")} == {k: v for k, v in o.items() if k not in ("vo", "io")})
        if same: out["unchanged"] += 1
        else: out["changed"].append(m["id"])
    out["removed"] = sorted(set(e0) - {m["id"] for m in m1["meshes"]})
    out["non_skin_changed"] = [i for i in out["changed"] if not i.startswith("zan_skin_")]
    return out


if __name__ == "__main__":
    res = {}
    for k, (o, n) in PAIRS.items():
        if n is None: continue
        stem = Path(P.PAGES[k][0]).name.replace("viewer_", "atlas_viewer_") if False else P.PAGES[k][1]
        res[k] = diff(o, n, stem)
        r = res[k]
        print(k, "changed", len(r["changed"]), "added", r["added"], "removed", r["removed"], "unchanged", r["unchanged"], "non-skin changed", r["non_skin_changed"])
    (REPO / "data" / "derived" / "Q202_ship_diff.json").write_text(json.dumps(res, indent=1))
