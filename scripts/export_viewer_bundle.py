#!/usr/bin/env python3
"""Pack converted geometry plus the atlas records into one embeddable bundle.

The converted Visible Human geometry is 55 MB of float32 vertices and uint32
faces -- more than three million triangles, which is right for measuring
against and far too much to put inside a single self-contained page. This
writes a viewing copy: decimated, quantised, and carrying the atlas data for
each structure so the viewer can answer "what is this" without a server.

DECIMATION IS BY VERTEX CLUSTERING, not by collapsing edges in order of
error. Every vertex falls into a cubic cell, each cell becomes one vertex at
the mean of its members, and any triangle whose corners end up in fewer than
three distinct cells disappears. It is crude next to a quadric-error
simplifier and it is the right crude: it never moves a surface further than
half a cell diagonal, so a 3 mm grid cannot misplace a muscle belly by more
than about 2.6 mm, and the error is bounded by a number stated up front
rather than by whatever a heuristic decides to spend.

THE CELL SIZE IS PER STRUCTURE, chosen to hit a triangle budget. A femur and
a gemellus should not be decimated at the same rate: the femur is long and
mostly smooth, the gemellus is small and would vanish. Each structure gets a
budget by category and the grid is fitted to it by bisection.

Positions are quantised to int16 at 0.25 mm, which spans +/-8 metres and is
finer than the decimation by an order of magnitude, so the quantisation is
never the dominant error.

    python3 scripts/export_viewer_bundle.py --subject vhm_both -o build/viewer
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

DATA_DIR = REPO_ROOT / "data"
BUILD_DIR = REPO_ROOT / "build" / "vh"

# Triangles to keep, by what the structure is. Bone carries the landmarks and
# is what everything else is measured against, so it keeps the most; a muscle
# belly is a blob whose shape reads at a tenth of the detail.
BUDGET = {
    "bone": 4500,
    "muscle": 1800,
    "cartilage": 1200,
    "ligament": 900,
    "tendon": 900,
    "vessel": 1500,
    "nerve": 1500,
}
DEFAULT_BUDGET = 1500
QUANTUM_MM = 0.25

# Indices are uint16, which is the whole reason for the budgets above: at
# these sizes no structure comes near 65536 vertices, and the index array --
# three per triangle against one position per vertex -- is what actually
# fills the file. uint32 indices doubled the bundle on their own.
MAX_VERTS = 65536


def cluster(verts: np.ndarray, faces: np.ndarray, cell: float):
    """Vertex clustering at a cubic cell size. Returns (verts, faces)."""
    keys = np.floor(verts / cell).astype(np.int64)
    _uniq, inverse = np.unique(keys, axis=0, return_inverse=True)
    n = int(inverse.max()) + 1
    sums = np.zeros((n, 3))
    counts = np.zeros(n)
    np.add.at(sums, inverse, verts)
    np.add.at(counts, inverse, 1)
    new_verts = sums / counts[:, None]
    new_faces = inverse[faces]
    keep = ((new_faces[:, 0] != new_faces[:, 1])
            & (new_faces[:, 1] != new_faces[:, 2])
            & (new_faces[:, 0] != new_faces[:, 2]))
    new_faces = new_faces[keep]
    if len(new_faces) == 0:
        return new_verts, new_faces
    used, new_faces = np.unique(new_faces, return_inverse=True)
    return new_verts[used], new_faces.reshape(-1, 3)


def decimate_to(verts, faces, budget):
    """Fit the cell size to a triangle budget by bisection on the grid."""
    if len(faces) <= budget:
        return verts, faces, 0.0
    extent = float(np.linalg.norm(verts.max(axis=0) - verts.min(axis=0)))
    lo, hi = extent / 400.0, extent / 6.0
    best = None
    for _ in range(14):
        mid = (lo + hi) / 2
        v, f = cluster(verts, faces, mid)
        if len(f) > budget:
            lo = mid
        else:
            best = (v, f, mid)
            hi = mid
        if hi - lo < extent / 4000.0:
            break
    if best is None:
        v, f = cluster(verts, faces, hi)
        best = (v, f, hi)
    return best


def load_atlas_records():
    """atlas_id -> the record the viewer shows, flattened from data/."""
    out = {}
    for path in sorted(DATA_DIR.rglob("*.json")):
        if path.parent.name == "rig":
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        for rec in (payload if isinstance(payload, list) else [payload]):
            if isinstance(rec, dict) and isinstance(rec.get("id"), str):
                out.setdefault(rec["id"], (path.parent.name, rec))
    return out


def summarise(folder, rec):
    """What the inspector panel shows. Kept small on purpose."""
    out = {
        "name": rec.get("name_common") or rec.get("name") or rec.get("id"),
        "latin": rec.get("name_ta"),
        "folder": folder,
        "region": rec.get("region"),
        "source": rec.get("source"),
        "notes": rec.get("notes"),
    }
    att = rec.get("attachments") or {}
    if att:
        out["origin"] = f"{att.get('origin_bone', '')}: {att.get('origin_landmark', '')}".strip(": ")
        out["insertion"] = f"{att.get('insertion_bone', '')}: {att.get('insertion_landmark', '')}".strip(": ")
    inn = (rec.get("innervation") or {}).get("nerve")
    if inn:
        out["nerve"] = inn if isinstance(inn, list) else [inn]
    comps = []
    for c in rec.get("functional_compartments") or []:
        arch = c.get("fiber_architecture") or {}
        zones = [{
            "range": z.get("zone_percent_range"),
            "from": z.get("reference_line_from"),
            "to": z.get("reference_line_to"),
            "method": z.get("method"),
            "notes": z.get("notes"),
            "source": z.get("source"),
        } for z in c.get("motor_endplate_zones") or []]
        points = [{
            "label": p.get("label"),
            "transverse": [p.get("transverse_line_from"), p.get("transverse_line_to"),
                           p.get("transverse_percent")],
            "longitudinal": [p.get("longitudinal_line_from"), p.get("longitudinal_line_to"),
                             p.get("longitudinal_percent")],
            "depth_pct": p.get("depth_percent_of_limb_thickness"),
            "depth_mm": p.get("depth_mm"),
            "depth_from": p.get("depth_measured_from"),
            "risk": p.get("structures_at_risk"),
            "path": p.get("needle_path"),
            "source": p.get("source"),
        } for p in c.get("injection_target_points") or []]
        nmj = c.get("neuromuscular_junction_zone") or {}
        comps.append({
            "id": c.get("id"),
            "arch_type": arch.get("architecture_type"),
            "pcsa": arch.get("physiological_cross_section_area_mm2"),
            "fiber_mm": arch.get("optimal_fascicle_length_mm"),
            "pennation": arch.get("pennation_deg"),
            "force_n": arch.get("max_isometric_force_N"),
            "nmj_frac": nmj.get("position_fraction_along_fascicle"),
            "nmj_band": nmj.get("band_width_fraction"),
            "nmj_evidence": nmj.get("evidence"),
            "nerves": c.get("innervation_branch_ids"),
            "branch": c.get("innervation_branch"),
            "function": c.get("function_note"),
            "zones": zones,
            "points": points,
        })
    if comps:
        out["compartments"] = comps
    if rec.get("supplies_or_drains"):
        out["supplies"] = rec["supplies_or_drains"][:24]
    if rec.get("targets"):
        out["targets"] = [t for t in rec["targets"] if isinstance(t, str)][:24]
    return {k: v for k, v in out.items() if v}


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--subject", default="vhm_both")
    ap.add_argument("-o", "--out", default="build/viewer")
    args = ap.parse_args()

    src = BUILD_DIR / args.subject
    manifest = json.loads((src / "manifest.json").read_text())
    verts = np.frombuffer((src / "vertices.f32").read_bytes(), dtype=np.float32).reshape(-1, 3)
    faces = np.frombuffer((src / "faces.u32").read_bytes(), dtype=np.uint32).reshape(-1, 3)

    atlas = load_atlas_records()
    from engine import vh_ingest as vh
    category = {e.entity_id: e.category for e in vh.load_atlas_index()}

    parts, blobs, index = [], [], []
    vert_base = 0
    kept_tris = 0
    for s in manifest["structures"]:
        aid = s["atlas_id"]
        v = verts[s["vertex_offset"]:s["vertex_offset"] + s["vertex_count"]].astype(np.float64)
        f = (faces[s["face_offset"]:s["face_offset"] + s["triangle_count"]].astype(np.int64)
             - s["vertex_offset"])
        cat = category.get(aid, "other")
        dv, df, cell = decimate_to(v, f, BUDGET.get(cat, DEFAULT_BUDGET))
        if len(df) == 0:
            print(f"  {aid}: decimated away, kept at full resolution")
            dv, df, cell = v, f, 0.0
        if len(dv) > MAX_VERTS:
            raise SystemExit(
                f"{aid}: {len(dv)} vertices exceeds the uint16 index limit; "
                f"lower the budget for category {cat!r}")
        q = np.rint(dv / QUANTUM_MM).astype(np.int16)
        idx = df.astype(np.uint16)
        blobs.append(q.tobytes())
        blobs.append(idx.tobytes())
        folder, rec = atlas.get(aid, (None, None))
        entry = {
            "id": aid,
            "cat": cat,
            "side": s.get("side"),
            "nv": int(q.shape[0]),
            "nf": int(idx.shape[0]),
            "cell": round(cell, 2),
            "tris_full": s["triangle_count"],
        }
        if rec is not None:
            entry["rec"] = summarise(folder, rec)
        index.append(entry)
        kept_tris += len(df)
        vert_base += len(dv)
        parts.append(aid)

    blob = b"".join(blobs)
    out_dir = REPO_ROOT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    bundle = {
        "subject": args.subject,
        "frame": manifest["frame"],
        "quantum_mm": QUANTUM_MM,
        "source_triangles": manifest["triangle_count"],
        "triangles": int(kept_tris),
        "attribution": manifest.get("attribution"),
        "structures": index,
    }
    (out_dir / "bundle.json").write_text(json.dumps(bundle, separators=(",", ":")))
    (out_dir / "bundle.bin").write_bytes(blob)
    b64 = base64.b64encode(blob).decode("ascii")
    (out_dir / "bundle.b64").write_text(b64)

    print(f"\n{len(index)} structures")
    print(f"triangles  {manifest['triangle_count']:,} -> {kept_tris:,} "
          f"({100 * kept_tris / manifest['triangle_count']:.1f}%)")
    print(f"binary     {len(blob) / 1e6:.2f} MB, base64 {len(b64) / 1e6:.2f} MB")
    print(f"index      {len(json.dumps(bundle)) / 1e6:.2f} MB")
    print(f"wrote      {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
