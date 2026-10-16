#!/usr/bin/env python3
"""Q226 -- read the structure list (id, name, category, side, vt, bbox) out of a BUILT viewer page, for the
imaging tissue-mapping report and its tests. Own pages: the `bundle-json` literal (cat = bundle category,
bbox not stored here); Z pages: the `__ANATOMY_MANIFEST__` literal (cat = sys layer).  Pure reader, no geometry."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts"))

# page key -> (build dir under the Q226 inputs, html name, viewer key of the add-on data, kind)
PAGES = {
    "vhm":      ("build/q224/viewer_m_hr",        "atlas_viewer_male.html",             "own"),
    "vhf":      ("build/q224/viewer_f_hr",        "atlas_viewer_female.html",           "own"),
    "zan_m":    ("build/q222/viewer_zan_atlas",   "atlas_viewer_zan_atlas.html",        "zan"),
    "zan_f":    ("build/q222/viewer_zan_female",  "atlas_viewer_zan_female.html",       "zan"),
    "zan_vhm":  ("build/q222/viewer_zan_vhm",     "atlas_viewer_zan_male_fitted.html",  "zan"),
    "base_f":   ("build/q222/viewer_base_female", "atlas_viewer_base_female.html",       "zan"),
}
STAGED = {k: ("build/q226/" + v[0].rsplit("/", 1)[1], v[1], v[2]) for k, v in PAGES.items()}


def structures_from_html(path: Path) -> list[dict]:
    html = Path(path).read_text(encoding="utf-8")
    m = re.search(r'<script id="bundle-json" type="application/json">(.*?)</script>', html, re.S)
    out = []
    if m:                                   # own page
        for s in json.loads(m.group(1))["structures"]:
            out.append({"id": s["id"], "name": (s.get("rec") or {}).get("name") or s["id"], "cat": s["cat"],
                        "side": s.get("side"), "vt": None})
        return out
    i = html.index("window.__ANATOMY_MANIFEST__=")
    man, _ = json.JSONDecoder().raw_decode(html[i + len("window.__ANATOMY_MANIFEST__="):])
    for s in man["meshes"]:
        side = s.get("side")
        out.append({"id": s.get("id") or s["name"], "name": s["name"], "cat": s["sys"],
                    "side": None if side == "m" else side, "vt": s.get("vt")})
    return out


def page_structures(key: str, root: Path | None = None) -> list[dict]:
    d, html, _ = PAGES[key]
    p = (root or REPO) / d / html
    if not p.is_file():
        p = REPO / STAGED[key][0] / STAGED[key][1]
    return structures_from_html(p)


if __name__ == "__main__":
    from collections import Counter
    for k in PAGES:
        try:
            S = page_structures(k)
        except Exception as e:  # noqa: BLE001
            print(k, "ERR", e); continue
        print(k, len(S), dict(Counter(s["cat"] for s in S)))
