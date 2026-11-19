"""Q205 page I/O: Q202's decode / re-pack (q202_pages) extended by (a) metadata-only patches (card name + atlas facts, geometry bytes untouched) and (b) a clean-baseline card
repair: the fitted Z pages built between Q200 and Q204 show raw ids as card names / lack origin-insertion-nerve facts (export_viewer_bundle.load_atlas_records let data/derived/Q200+ rows
shadow the atlas records; fixed in Q204).  The clean base page (same builder, no fit) carries the right name + record for every id; a fitted page differs from it only by the fit badge, so
    card(fitted) := card(base) + fit badge of the fitted page.
Proven on the published pages: 2905 of 2966 (male) / 2877 of 2939 (female) cards already equal the base card minus badge; only the shadowed ones differ.
"""
from __future__ import annotations

import base64
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "scripts" / "zanatomy"))
sys.path.insert(0, str(REPO))
import build_zan_atlas_viewer as B  # noqa: E402
from scripts.zanatomy import q202_pages as P2  # noqa: E402

load_page, decode, decode_one = P2.load_page, P2.decode, P2.decode_one


def strip_badge(rec):
    r = dict(rec or {})
    r.pop("procedural_badge", None)
    return r


def card_repairs(man, base_man):
    """{id: (name, rec)} for every card of `man` whose name / record (minus badge) differs from the clean base page's card of the same id"""
    be = {m["id"]: m for m in base_man["meshes"]}
    out = {}
    for m in man["meshes"]:
        b = be.get(m["id"])
        if b is None:
            continue
        if m["name"] != b["name"] or strip_badge(m.get("rec")) != strip_badge(b.get("rec")):
            rec = strip_badge(b.get("rec"))
            badge = (m.get("rec") or {}).get("procedural_badge")
            if badge:
                rec["procedural_badge"] = badge
            out[m["id"]] = (b["name"], rec if rec else None)
    return out


def save_page(d_out, stem, man, blob, replace=None, meta=None, add=(), totals=None):
    """replace: {id: (v, f, rec_or_None)} new geometry (re-quantised by the builder's pack_mesh); meta: {id: (name, rec)} card-only changes (geometry bytes copied);
    add: [(entry_without_geometry, v, f)].  Untouched structures are copied byte for byte."""
    replace, meta = replace or {}, meta or {}
    d_out = Path(d_out)
    d_out.mkdir(parents=True, exist_ok=True)
    meshes, chunks, off = [], [], 0
    for m in man["meshes"]:
        n = dict(m)
        if m["id"] in meta:
            nm, rec = meta[m["id"]]
            n["name"] = nm
            if rec is None:
                n.pop("rec", None)
            else:
                n["rec"] = rec
        if m["id"] in replace:
            v, f, rec = replace[m["id"]]
            fields, packed = B.pack_mesh(np.asarray(v, float), np.asarray(f), off)
            n.update(fields)
            if rec is not None:
                n["rec"] = rec
            meshes.append(n)
            chunks.append(packed)
            off += len(packed)
        else:
            pos = blob[m["vo"]: m["vo"] + m["vc"] * 6]
            idx = blob[m["io"]: m["io"] + m["ic"] * 6]
            n["vo"], n["io"] = off, off + len(pos)
            meshes.append(n)
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
    t = json.loads(json.dumps(man["totals"]))
    t["meshes"] = len(meshes)
    t.update(totals or {})
    man2["totals"] = t
    for f in d_out.glob(f"{stem}*"):
        f.unlink()
    bin_files = []
    for name, chunk in B.split_blob(new_blob, stem):
        (d_out / name).write_text(base64.b64encode(chunk).decode("ascii"), encoding="ascii")
        bin_files.append({"path": name, "bytes": len(chunk), "enc": "base64"})
    (d_out / f"{stem}.html").write_text(B.render_html(man2, new_blob, bin_files), encoding="utf-8")
    return man2, new_blob
