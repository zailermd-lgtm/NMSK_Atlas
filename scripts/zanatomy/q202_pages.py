"""Q202 page I/O: decode / patch / re-pack a built Z-Anatomy page (manifest + uint16 geometry blob), byte-identical for every structure that is not replaced.

    man, blob = load_page(dir, stem); S = decode(man, blob)      # id -> dict(m=manifest entry, v=float64 (n,3), f=int64 (m,3))
    save_page(dir_out, stem, man, blob, replace={id: (v, f, rec_or_None)}, add=[(entry_without_geometry, v, f)])
"""
from __future__ import annotations

import base64
import json
import re
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "zanatomy"))
import build_zan_atlas_viewer as B  # noqa: E402

PAGES = {  # key: (dir, stem)
    "base_m": ("build/q197/viewer_zan_atlas", "atlas_viewer_zan_atlas"),
    "base_f": ("build/q197/viewer_base_female", "atlas_viewer_base_female"),
    "fit_m": ("build/q201/viewer_zan_vhm", "atlas_viewer_zan_male_fitted"),
    "fit_f": ("build/q199/viewer_zan_female", "atlas_viewer_zan_female"),
}


def load_page(d, stem):
    d = Path(d)
    html = (d / f"{stem}.html").read_text(encoding="utf-8")
    i = html.index("window.__ANATOMY_MANIFEST__=") + len("window.__ANATOMY_MANIFEST__=")
    man, _ = json.JSONDecoder().raw_decode(html[i:])
    files = json.loads(re.search(r"window\.__ANATOMY_BIN_FILES__=(\[.*?\]);\s*window\.__ANATOMY_MANIFEST__=", html, re.S).group(1))
    blob = b"".join(base64.b64decode((d / f["path"]).read_bytes()) for f in files)
    return man, blob


def decode_one(m, blob):
    vc, ic = m["vc"], m["ic"]
    q = np.frombuffer(blob, np.uint16, vc * 3, m["vo"]).reshape(-1, 3).astype(np.float64)
    f = np.frombuffer(blob, np.uint16, ic * 3, m["io"]).reshape(-1, 3).astype(np.int64)
    v = np.asarray(m["min"]) + q / 65535.0 * np.asarray(m["span"])
    return v, f


def decode(man, blob, only=None):
    out = {}
    for m in man["meshes"]:
        if only is not None and not only(m):
            continue
        v, f = decode_one(m, blob)
        out[m["id"]] = {"m": m, "v": v, "f": f}
    return out


def save_page(d_out, stem, man, blob, replace=None, add=(), totals_fix=True):
    """re-pack: untouched structures are copied byte for byte (position + index bytes, manifest entry unchanged); replaced ones are re-quantised by the builder's pack_mesh"""
    replace = replace or {}
    d_out = Path(d_out)
    d_out.mkdir(parents=True, exist_ok=True)
    meshes, chunks, off = [], [], 0
    for m in man["meshes"]:
        if m["id"] in replace:
            v, f, rec = replace[m["id"]]
            fields, packed = B.pack_mesh(np.asarray(v, float), np.asarray(f), off)
            n = dict(m)
            n.update(fields)
            if rec is not None:
                n["rec"] = rec
            meshes.append(n)
            chunks.append(packed)
            off += len(packed)
        else:
            pos = blob[m["vo"]: m["vo"] + m["vc"] * 6]
            idx = blob[m["io"]: m["io"] + m["ic"] * 6]
            n = dict(m)
            n["vo"], n["io"] = off, off + len(pos)
            meshes.append({k: n[k] for k in m})
            chunks += [pos, idx]
            off += len(pos) + len(idx)
    for entry, v, f in add:
        fields, packed = B.pack_mesh(np.asarray(v, float), np.asarray(f), off)
        n = dict(entry)
        n.update(fields)
        meshes.append(n)
        chunks.append(packed)
        off += len(packed)
    new_blob = b"".join(chunks)
    man2 = dict(man)
    man2["meshes"] = meshes
    if add and totals_fix:
        t = json.loads(json.dumps(man["totals"]))
        t["meshes"] = len(meshes)
        for entry, _, _ in add:
            t["by_layer"][entry["sys"]] = t["by_layer"].get(entry["sys"], 0) + 1
            if "cat" in entry:
                pass
            t["by_category"]["skin"] = t["by_category"].get("skin", 0) + 1 if entry["sys"] == "skin" else t["by_category"].get("skin", 0)
        man2["totals"] = t
    for f in d_out.glob(f"{stem}*"):
        f.unlink()
    bin_files = []
    for name, chunk in B.split_blob(new_blob, stem):
        (d_out / name).write_text(base64.b64encode(chunk).decode("ascii"), encoding="ascii")
        bin_files.append({"path": name, "bytes": len(chunk), "enc": "base64"})
    (d_out / f"{stem}.html").write_text(B.render_html(man2, new_blob, bin_files), encoding="utf-8")
    return man2, new_blob
