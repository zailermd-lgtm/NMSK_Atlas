"""Read a viewer bundle back into meshes.

The viewer bundle (`scripts/export_viewer_bundle.py`) is the decimated,
quantised copy of every shipped structure. It is also the only copy of the
male body that survives a container reset (the DU lower-limb STLs cannot be
re-downloaded under the current network policy), so the cross-subject
transfer reads the published male HTML back instead of the source meshes.

Layout (per structure, in `structures` order): nv*3 int16 positions at
`quantum_mm`, then nf*3 uint16 triangle indices. Nothing else in the blob.
"""
from __future__ import annotations

import base64
import json
import re
from pathlib import Path

import numpy as np


def read_bundle_html(path):
    """Return (bundle_json, blob_bytes) from a published viewer HTML."""
    html = Path(path).read_text(encoding="utf-8")
    m = re.search(r'<script id="bundle-json" type="application/json">(.*?)</script>', html, re.S)
    b = re.search(r'<script id="bundle-b64" type="text/plain">(.*?)</script>', html, re.S)
    if not (m and b):
        raise ValueError(f"{path}: no bundle scripts found")
    return json.loads(m.group(1)), base64.b64decode(b.group(1).strip())


def read_bundle_dir(path):
    d = Path(path)
    return json.loads((d / "bundle.json").read_text()), (d / "bundle.bin").read_bytes()


def decode(bundle, blob):
    """Yield (entry, vertices float32 (n,3) mm, faces int32 (m,3)) per structure piece."""
    q = float(bundle["quantum_mm"]); off = 0
    for e in bundle["structures"]:
        nv, nf = int(e["nv"]), int(e["nf"])
        pos = np.frombuffer(blob, np.int16, nv * 3, off).reshape(-1, 3).astype(np.float32) * q
        off += nv * 6
        idx = np.frombuffer(blob, np.uint16, nf * 3, off).reshape(-1, 3).astype(np.int32)
        off += nf * 6
        yield e, pos, idx
    if off != len(blob):
        raise ValueError(f"bundle blob has {len(blob) - off} trailing bytes")


def meshes_by_id(bundle, blob):
    """Concatenate pieces: {atlas_id: {'v','f','subject','cat','side','pieces'}}."""
    out = {}
    for e, v, f in decode(bundle, blob):
        m = out.setdefault(e["id"], {"v": [], "f": [], "subject": e["subject"], "cat": e["cat"],
                                     "side": e.get("side"), "pieces": 0, "rec": e.get("rec")})
        m["f"].append(f + sum(len(x) for x in m["v"])); m["v"].append(v); m["pieces"] += 1
    for m in out.values():
        m["v"] = np.concatenate(m["v"]); m["f"] = np.concatenate(m["f"])
    return out


def mesh_volume_cm3(v, f):
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    return abs(float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum()) / 6.0) / 1000.0
