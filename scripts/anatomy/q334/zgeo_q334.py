#!/usr/bin/env python3
"""Q334: read a Z page's geometry (manifest + quantised blob) the way the engine's loader does. Read-only helper."""
import base64, json, os, re
import numpy as np


def _literal(s, name):
    m = re.search(r'window\.%s\s*=\s*' % re.escape(name), s)
    if not m:
        return None
    dec = json.JSONDecoder()
    v, _ = dec.raw_decode(s, m.end())
    return v


def load(page_dir):
    html = os.path.join(page_dir, "index.html")
    s = open(html, encoding="utf-8").read()
    man = _literal(s, "__ANATOMY_MANIFEST__")
    files = _literal(s, "__ANATOMY_BIN_FILES__")
    parts = []
    for f in files:
        raw = open(os.path.join(page_dir, f["path"]), "rb").read()
        b = base64.b64decode(raw.strip()) if f.get("enc") == "base64" else raw
        assert len(b) == f["bytes"], f["path"]
        parts.append(b)
    return man, b"".join(parts)


def mesh(man, binb, i):
    r = man["meshes"][i]
    vc, ic = r["vc"], r["ic"]
    q = np.frombuffer(binb, dtype="<u2", count=vc * 3, offset=r["vo"]).reshape(-1, 3).astype(np.float64)
    pos = np.asarray(r["min"], float) + q / 65535.0 * np.asarray(r["span"], float)
    idx = np.frombuffer(binb, dtype="<u2", count=ic * 3, offset=r["io"]).reshape(-1, 3).astype(np.int64)
    return pos.astype(np.float32).astype(np.float64), idx
