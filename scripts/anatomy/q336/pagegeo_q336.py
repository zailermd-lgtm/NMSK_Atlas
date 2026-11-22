"""Q336: read a built Base page's manifest / geometry (the builder's layout, as scripts/anatomy/q333/fix_chest_wall_q333.py)."""
from __future__ import annotations

import base64
import json
import re
from pathlib import Path

import numpy as np

LIT = {"files": re.compile(r"^window\.__ANATOMY_BIN_FILES__=(.*);$", re.M),
       "manifest": re.compile(r"^window\.__ANATOMY_MANIFEST__=(.*);$", re.M)}


def page_html(d: Path) -> Path:
    return sorted(Path(d).glob("atlas_viewer_*.html"))[0]


def manifest(d: Path):
    t = page_html(d).read_text(encoding="utf-8")
    return json.loads(LIT["manifest"].search(t).group(1))


def read_page(d: Path):
    d = Path(d)
    t = page_html(d).read_text(encoding="utf-8")
    man = json.loads(LIT["manifest"].search(t).group(1))
    files = json.loads(LIT["files"].search(t).group(1))
    blob = b"".join(base64.b64decode((d / f["path"]).read_bytes()) for f in files)
    return man, blob, files


def dec(m, blob):
    q = np.frombuffer(blob, np.uint16, m["vc"] * 3, m["vo"]).reshape(-1, 3).astype(np.float64)
    f = np.frombuffer(blob, np.uint16, m["ic"] * 3, m["io"]).reshape(-1, 3).astype(np.int64)
    return np.asarray(m["min"]) + q / 65535.0 * np.asarray(m["span"]), f


def by_id(man):
    return {m["id"]: m for m in man["meshes"]}


def bbox(m):
    mn = np.asarray(m["min"], float)
    return mn, mn + np.asarray(m["span"], float)


def region_target(man):
    """camera target: 25 mm below the centre of the pubic symphysis disc (the page's own mesh)"""
    m = by_id(man)["pubic_symphysis_disc"]
    lo, hi = bbox(m)
    c = (lo + hi) / 2
    return [0.0, float(c[1] - 25), float(c[2] - 20)]
