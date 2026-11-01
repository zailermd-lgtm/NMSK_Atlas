#!/usr/bin/env python3
"""Q298: read one viewer page's structure list, its names and its geometry, for the search / adjacency / relation builders.

Deliberately metadata-first (like scripts/anatomy/q297/prov297.py): `structures()` never touches the geometry blob, so the
search and relation builders stay fast; `meshes()` decodes it for the adjacency builder only.

The two engines differ, so this module is the one place that knows how:
  own pages (viewer_m_hr / viewer_f_hr)  -- a `bundle-json` block + the packed binary; names live in entry["rec"]["name"]
  Z pages  (the four Z dirs)             -- window.__ANATOMY_MANIFEST__ ; names live in mesh["name"], Latin in rec["latin"]
"""
from __future__ import annotations

import base64
import json
import re
import sys
import unicodedata
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
DIRS = {
    "own_m": ("viewer_m_hr", "atlas_viewer_male.html", "own"),
    "own_f": ("viewer_f_hr", "atlas_viewer_female.html", "own"),
    "base_m": ("viewer_zan_atlas", "atlas_viewer_zan_atlas.html", "zan"),
    "base_f": ("viewer_base_female", "atlas_viewer_base_female.html", "zan"),
    "comb_m": ("viewer_zan_vhm", "atlas_viewer_zan_male_fitted.html", "zan"),
    "comb_f": ("viewer_zan_female", "atlas_viewer_zan_female.html", "zan"),
}
KEYS = list(DIRS)
DIRKEY = {v[0]: k for k, v in DIRS.items()}
_HTML: dict = {}
_STRUCT: dict = {}


# ---------------------------------------------------------------- normalisation (the same rule the viewer module uses)
_PUNCT = re.compile(r"[^0-9a-z֐-׿]+")


def fold(s: str) -> str:
    """Lower case, strip accents, every run of punctuation / space to one space. Hebrew letters are kept as they are."""
    s = unicodedata.normalize("NFKD", str(s or "")).lower()
    s = "".join(c for c in s if not unicodedata.combining(c))
    return _PUNCT.sub(" ", s).strip()


def strip_parens(s: str) -> str:
    """'Iliotibial (IT) tract/band' -> 'Iliotibial  tract/band'; 'Olfactory nerve (CN I) (left)' -> 'Olfactory nerve'."""
    out, depth = [], 0
    for ch in str(s or ""):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif depth == 0:
            out.append(ch)
    return "".join(out)


_SIDE = re.compile(r" (l|r|left|right|lt|rt)$")


def keys_of(name: str) -> list:
    """The comparison keys of a page display name, most specific first:
         the whole folded name;
         the name with every parenthesised qualifier removed  ('Iliotibial (IT) tract/band', 'Olfactory nerve (CN I) (left)');
         either of those with a trailing side token removed    (the own pages write 'Median nerve.l' / 'Median nerve.r')."""
    out = []
    for k in (fold(name), fold(strip_parens(name))):
        for v in (k, _SIDE.sub("", k)):
            if v and v not in out:
                out.append(v)
    return out


# ---------------------------------------------------------------- page reading
def html(key: str, src) -> str:
    ck = (key, str(src))
    if ck not in _HTML:
        dn, hn, _ = DIRS[key]
        d = Path(src) if Path(src).is_absolute() else REPO / src
        p = d / dn / hn
        if not p.exists():
            p = d / dn / "index.html"
        _HTML[ck] = p.read_text(encoding="utf-8")
    return _HTML[ck]


def structures(key: str, src) -> list:
    """[{id, name, latin, cat, side, part_of, part_of_id, rec}] in the page's own order. No geometry decoded."""
    ck = (key, str(src))
    if ck in _STRUCT:
        return _STRUCT[ck]
    h = html(key, src)
    out = []
    if DIRS[key][2] == "own":
        bj = json.loads(re.search(r'<script id="bundle-json" type="application/json">(.*?)</script>', h, re.S).group(1))
        for e in bj["structures"]:
            rec = e.get("rec") or {}
            out.append({"id": e["id"], "name": rec.get("name") or e["id"], "latin": rec.get("latin") or "",
                        "cat": e.get("cat") or "", "side": e.get("side") or "", "part_of": rec.get("part_of") or "",
                        "part_of_id": rec.get("part_of_id") or "", "rec": rec})
    else:
        man = json.loads(re.search(r"^window\.__ANATOMY_MANIFEST__=(.*);$", h, re.M).group(1))
        for m in man["meshes"]:
            rec = m.get("rec") or {}
            out.append({"id": m["id"], "name": m.get("name") or m["id"], "latin": rec.get("latin") or "",
                        "cat": m.get("sys") or "", "side": m.get("side") or "", "part_of": rec.get("part_of") or "",
                        "part_of_id": rec.get("part_of_id") or "", "rec": rec})
    _STRUCT[ck] = out
    return out


def learn(key: str, src):
    """The page's own nmsk-learn block (Q283 muscle facts: origin / insertion bone ids, nerves, motions, heads) or None."""
    h = html(key, src)
    m = re.search(r'<script type="application/json" id="nmsk-learn">(.*?)</script>', h, re.S)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except Exception:
        return None


def blob(key: str, src) -> bytes:
    h = html(key, src)
    d = (Path(src) if Path(src).is_absolute() else REPO / src) / DIRS[key][0]
    files = json.loads(re.search(r"BIN_FILES(?:__)?\s*=\s*(\[.*?\])\s*;?\s*$", h, re.M).group(1))
    return b"".join(base64.b64decode((d / f["path"]).read_text().strip()) for f in files)


def meshes(key: str, src):
    """Yield (index, id, vertices float32 (mm), faces int32) for every structure, in the page's own order."""
    h = html(key, src)
    b = blob(key, src)
    if DIRS[key][2] == "own":
        sys.path.insert(0, str(REPO))
        from scripts.transfer.bundle_io import decode  # noqa: E402
        bj = json.loads(re.search(r'<script id="bundle-json" type="application/json">(.*?)</script>', h, re.S).group(1))
        for i, (e, v, f) in enumerate(decode(bj, b)):
            yield i, e["id"], np.asarray(v, np.float32), np.asarray(f, np.int32)
    else:
        man = json.loads(re.search(r"^window\.__ANATOMY_MANIFEST__=(.*);$", h, re.M).group(1))
        for i, r in enumerate(man["meshes"]):
            q = np.frombuffer(b, np.uint16, r["vc"] * 3, r["vo"]).reshape(-1, 3).astype(np.float32)
            f = np.frombuffer(b, np.uint16, r["ic"] * 3, r["io"]).reshape(-1, 3).astype(np.int32)
            v = np.asarray(r["min"], np.float32) + q / np.float32(65535.0) * np.asarray(r["span"], np.float32)
            yield i, r["id"], v, f
