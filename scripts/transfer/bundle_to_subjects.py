"""Unpack a published viewer bundle into per-subject geometry folders.

    python3 scripts/transfer/bundle_to_subjects.py VIEWER.html [--out build/vh] [--only vhm_both ...]

Writes build/vh/<subject>/{manifest.json,vertices.f32,faces.u32} in the
layout `scripts/export_viewer_bundle.py` reads, so a body whose source
meshes are gone (the male's DU STLs cannot be re-downloaded under the
current network policy, and his cryosection skin is not in the repository)
can still be re-exported with additions. The meshes are the bundle's
decimated, 0.25 mm-quantised copies, not the originals -- the manifest says
so -- and nothing about them is re-derived here.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.transfer.bundle_io import read_bundle_html, read_bundle_dir, decode  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("bundle", help="published viewer HTML, or a directory with bundle.json + bundle.bin")
    ap.add_argument("--out", default="build/vh")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--label", default="recovered from the published viewer bundle")
    a = ap.parse_args()
    p = Path(a.bundle)
    bundle, blob = read_bundle_dir(p) if p.is_dir() else read_bundle_html(p)
    subjects_in_order = bundle["subject"].split("+")
    attributions = bundle.get("attribution") or []
    per = {}
    for e, v, f in decode(bundle, blob):
        s = e["subject"]
        if a.only and s not in a.only:
            continue
        d = per.setdefault(s, {"v": [], "f": [], "st": []})
        voff = sum(len(x) for x in d["v"]); foff = sum(len(x) for x in d["f"])
        d["st"].append({"atlas_id": e["id"], "source_structure": e["id"], "side": e.get("side"),
                        "source_file": f"{a.label}#{e['id']}", "vertex_offset": voff, "face_offset": foff,
                        "vertex_count": int(len(v)), "triangle_count": int(len(f)),
                        "bbox_min_mm": [round(float(x), 4) for x in v.min(axis=0)],
                        "bbox_max_mm": [round(float(x), 4) for x in v.max(axis=0)],
                        "tris_full_at_source": int(e.get("tris_full", len(f)))})
        d["v"].append(v.astype(np.float32)); d["f"].append((f + voff).astype(np.uint32))
    for s, d in per.items():
        V = np.concatenate(d["v"]); F = np.concatenate(d["f"])
        out = Path(a.out) / s; out.mkdir(parents=True, exist_ok=True)
        V.tofile(out / "vertices.f32"); F.tofile(out / "faces.u32")
        i = subjects_in_order.index(s) if s in subjects_in_order else None
        att = attributions[i] if i is not None and i < len(attributions) else []
        att = list(att) if isinstance(att, list) else [att]
        att.append(f"Geometry here is the viewer's decimated copy ({a.label}); the source meshes had "
                   f"{sum(x['tris_full_at_source'] for x in d['st'])} triangles.")
        manifest = {"subject": s, "frame": bundle["frame"], "source_volume": None,
                    "source_kind": a.label, "vertex_count": int(len(V)),
                    "triangle_count": int(sum(x["tris_full_at_source"] for x in d["st"])),
                    "bbox_min_mm": [round(float(x), 4) for x in V.min(axis=0)],
                    "bbox_max_mm": [round(float(x), 4) for x in V.max(axis=0)],
                    "attribution": att, "structures": d["st"]}
        (out / "manifest.json").write_text(json.dumps(manifest, indent=1))
        print(f"{s:16s} {len(d['st']):4d} pieces {len(V):8d} vertices -> {out}")
    print("subject order:", "+".join(s for s in subjects_in_order if s in per))


if __name__ == "__main__":
    main()
