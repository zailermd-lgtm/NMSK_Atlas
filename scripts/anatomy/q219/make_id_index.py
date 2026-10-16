#!/usr/bin/env python3
"""Snapshot of the structure ids of the four bodies -> data/derived/Q219_structure_ids.json (so tests do not need build/).
    python3 scripts/anatomy/q219/make_id_index.py"""
import json, re, sys
from pathlib import Path
REPO = Path(__file__).resolve().parents[3]
BODIES = {
    "vhm": ("own", REPO / "build/viewer_m_hr_q217/bundle.json"),
    "vhf": ("own", REPO / "build/viewer_f_hr_q216/bundle.json"),
    "zan_m": ("zan", REPO / "build/q221/viewer_zan_vhm/atlas_viewer_zan_male_fitted.html"),
    "zan_f": ("zan", REPO / "build/q220/viewer_zan_female/atlas_viewer_zan_female.html"),
}
out = {}
for k, (kind, p) in BODIES.items():
    if kind == "own":
        b = json.loads(p.read_text())
        out[k] = {"source": str(p.relative_to(REPO)), "ids": {e["id"]: e["cat"] for e in b["structures"]}}
    else:
        h = p.read_text(encoding="utf-8")
        i = h.find("window.__ANATOMY_MANIFEST__=") + len("window.__ANATOMY_MANIFEST__=")
        man = json.JSONDecoder().raw_decode(h[i:])[0]
        out[k] = {"source": str(p.relative_to(REPO)), "ids": {m["id"]: m["sys"] for m in man["meshes"]}}
(REPO / "data/derived/Q219_structure_ids.json").write_text(json.dumps(out, sort_keys=True))
print({k: len(v["ids"]) for k, v in out.items()})
