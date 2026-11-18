"""Q362: read-only access to the two frozen own-engine Imaging pages (viewer_m_hr, viewer_f_hr) and to a Z-engine Base page.

Own engine (viewer/atlas_viewer.template.html, __atlasMain): the page carries a `bundle-json` literal (structures in draw order, each
with nv / nf) and `var BIN_FILES = [...]`; the geometry is the base64 of the concatenated geo files, and per structure (in order)
nv*3 int16 positions (x quantum_mm, atlas frame: +X right, +Y superior, +Z anterior, mm) then nf*3 uint16 indices. Several
structures may share one id (e.g. the 5 `lumbar_vertebrae`, in bundle order); they are returned as id#k (k = 0, 1, ...).
Nothing here writes anything."""
from __future__ import annotations

import base64
import json
import re
from pathlib import Path

import numpy as np

OWN_LIT = {"json": re.compile(r'<script id="bundle-json" type="application/json">(.*?)</script>', re.S),
           "files": re.compile(r"^var BIN_FILES = (.*);$", re.M)}


def own_html(d: Path) -> Path:
    c = [p for p in sorted(Path(d).glob("atlas_viewer_*.html"))]
    assert c, f"{d}: no atlas_viewer_*.html"
    return c[0]


def read_own(d: Path, want=None):
    """{key: dict(v, f, rec, cat, side, subject, name, id)} for the structures in `want` (ids; None = all). key = id, or id#k."""
    d = Path(d)
    t = own_html(d).read_text(encoding="utf-8")
    B = json.loads(OWN_LIT["json"].search(t).group(1))
    files = json.loads(OWN_LIT["files"].search(t).group(1))
    blob = b"".join(base64.b64decode((d / f["path"]).read_bytes()) for f in files)
    q = float(B["quantum_mm"])
    out, seen, off = {}, {}, 0
    for s in B["structures"]:
        nv, nf = int(s["nv"]), int(s["nf"])
        k = seen.get(s["id"], 0); seen[s["id"]] = k + 1
        key = s["id"] if k == 0 else f"{s['id']}#{k}"
        if want is None or s["id"] in want or key in want:
            v = np.frombuffer(blob, "<i2", nv * 3, off).reshape(-1, 3).astype(np.float64) * q
            f = np.frombuffer(blob, "<u2", nf * 3, off + nv * 6).reshape(-1, 3).astype(np.int64)
            out[key] = dict(id=s["id"], v=v, f=f, rec=s.get("rec") or {}, cat=s.get("cat"), side=s.get("side"),
                            subject=s.get("subject"), name=(s.get("rec") or {}).get("name"))
        off += nv * 6 + nf * 6
    assert off == len(blob), f"{d}: geometry length {len(blob)} != structures {off}"
    if want is not None:
        for k_ in list(seen):
            if seen[k_] > 1 and k_ in want and k_ in out:
                out[k_ + "#0"] = out[k_]
    return out, B


def bundle_meta(d: Path):
    t = own_html(d).read_text(encoding="utf-8")
    return json.loads(OWN_LIT["json"].search(t).group(1))
