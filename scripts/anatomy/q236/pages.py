"""Q236: read (id, name, side) of every structure of a built viewer page (own template: bundle-json; Z template: __ANATOMY_MANIFEST__)."""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
# page dir -> page file. The Q236 output dirs are build/q236/<dir>.
PAGES = {
    "viewer_m_hr": "atlas_viewer_male.html", "viewer_f_hr": "atlas_viewer_female.html", "viewer_zan_vhm": "atlas_viewer_zan_male_fitted.html",
    "viewer_zan_female": "atlas_viewer_zan_female.html", "viewer_base_female": "atlas_viewer_base_female.html", "viewer_zan_atlas": "atlas_viewer_zan_atlas.html",
}


def read_structs(html: str) -> list[dict]:
    m = re.search(r'<script[^>]*id="bundle-json"[^>]*>(.*?)</script>', html, re.S)
    out, seen = [], set()
    if m:                                                      # own template
        for s in json.loads(m.group(1))["structures"]:
            if s["id"] in seen:
                continue
            seen.add(s["id"])
            out.append({"id": s["id"], "name": (s.get("rec") or {}).get("name") or s["id"], "side": s.get("side")})
        return out
    i = html.find("window.__ANATOMY_MANIFEST__=")
    if i < 0:
        raise ValueError("neither bundle-json nor __ANATOMY_MANIFEST__ found")
    man, _ = json.JSONDecoder().raw_decode(html[i + len("window.__ANATOMY_MANIFEST__="):])
    for r in man["meshes"]:
        if r["id"] in seen:
            continue
        seen.add(r["id"])
        out.append({"id": r["id"], "name": r["name"], "side": r.get("side")})
    return out
