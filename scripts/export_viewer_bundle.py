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
    "bone": 6000,
    "muscle": 3600,
    "cartilage": 1200,
    "ligament": 900,
    "tendon": 900,
    "vessel": 1500,
    "nerve": 1500,
}
DEFAULT_BUDGET = 1500
# A few entities are far larger than their category's typical member and
# read as crude at the category budget: the whole skull is one composite
# 'bone'.
BUDGET_OVERRIDES = {"cranium": 14000, "mandible": 6000, "skin": 30000,
                    "sciatic_n": 12000,   # a 6 mm cord 200 mm long breaks into fragments at the nerve budget's 5 mm cells
                    "diaphragm": 12000, "external_intercostals_r": 8000, "external_intercostals_l": 8000}  # 4 mm sheets: same problem   # a 6 mm cord 200 mm long breaks into fragments at the nerve budget's 5 mm cells
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


# Thin sheets (a 4 mm diaphragm, the intercostal sheets) cannot be vertex-clustered: once the cell exceeds the
# thickness the two faces of the sheet merge and the mesh turns into a lace of holes. Those ids are decimated
# by quadric edge collapse instead (fast_simplification), which keeps a sheet a sheet; clustering stays for
# everything else so the rest of the page is unchanged.
# A thin CORD is the same failure in one fewer dimension: sciatic_n (Q113) is a ~6 mm tube, and even at its
# own BUDGET_OVERRIDE (12000, already raised once for exactly this), vertex-clustering's grid cell -- sized
# to hit the triangle budget over the whole ~230 mm length -- exceeds the tube's diameter in places and
# merges/severs cross-sections that the source mesh has genuinely connected: measured directly (Q113), the
# shipped bundle's sciatic_n main_frac was 0.332 (11 components) even though the underlying full-resolution
# mesh it was decimated FROM measured 0.621 (6 components, after also fixing an unrelated over-smoothing
# defect, see Q113) -- i.e. clustering alone was manufacturing about half of the shipped fragmentation.
# Quadric edge collapse on that same source mesh at the same triangle budget preserves it: 0.612 (6
# components), matching the pre-decimation number. Added here rather than given its own set/budget path
# because the mechanism (clustering cannot represent geometry thinner than its own cell) is identical to
# the sheet case above, just one dimension down.
SHEET_IDS = {"diaphragm", "external_intercostals_r", "external_intercostals_l", "sciatic_n"}


def decimate_quadric(verts, faces, budget):
    """Quadric edge-collapse decimation to about `budget` triangles; None when the library is missing."""
    try:
        import fast_simplification as fs
    except ImportError:
        return None
    if len(faces) <= budget:
        return verts, faces
    v, f = fs.simplify(np.ascontiguousarray(verts, dtype=np.float32), np.ascontiguousarray(faces, dtype=np.int32),
                       target_reduction=1.0 - budget / len(faces), agg=7)
    return v.astype(np.float64), f.astype(np.int64)


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


def resolve_anchor_points(subject: str):
    """muscle_id -> {"origin": [x,y,z], "insertion": [x,y,z]} in the atlas's
    global mm frame, for every anchor whose bone has real measured geometry.

    Anchors are stored in data/rig/anchors.json as a LOCAL position plus the
    bone frame that owns it -- the same frames
    scripts/audit_landmarks_vs_geometry.py fits from the ingested geometry
    (femoral head sphere, tibial plateau transverse axis, etc.), reused here
    rather than re-derived. Bones with no real geometry yet (everything
    above the hip) have no frame, so their anchors are silently skipped --
    the viewer then falls back to the text description alone, same as
    before this existed.
    """
    anchors_path = DATA_DIR / "rig" / "anchors.json"
    if not anchors_path.exists():
        return {}
    anchors = json.loads(anchors_path.read_text())
    if not anchors:
        return {}
    from scripts.audit_landmarks_vs_geometry import load_geometry as _load_geom, build_frames, place
    _manifest, blocks, by_atlas_id, faces_by_atlas_id = _load_geom(subject)
    frames = build_frames(by_atlas_id, blocks, faces_by_atlas_id)
    # The anchors' along-axis coordinates are millimetres on the MALE bone;
    # `place` stretches them by this subject's measured length over the
    # bone's reference_length_mm (Q43), so the same anchor sits at the same
    # fraction of her femur as of his.
    bones = {b["id"]: b for b in json.loads(
        (DATA_DIR / "skeleton" / "bones.json").read_text())}
    out = {}
    role_key = {"muscle_origin": "origin", "muscle_insertion": "insertion"}
    for a in anchors:
        frame = frames.get(a["parent_bone_frame"])
        if frame is None:
            continue
        world = place(a["local_position_mm"], frame, bones.get(a["parent_bone_frame"]))
        if not np.all(np.isfinite(world)):
            # a degenerate bone frame (a recovered, decimated mesh can give one) would put NaN into the
            # bundle JSON and break the viewer's JSON.parse; the text description alone is shown instead
            continue
        # A compartment-level anchor (e.g. 'flexor_hallucis_brevis_r_medial')
        # is filed under its own id, not the muscle's -- the inspector below
        # only looks up the muscle id, so a handful of multi-headed muscles
        # (flexor hallucis brevis, adductor magnus) won't show a point here
        # even though one exists; their whole-muscle text description is
        # unaffected, same as before this existed.
        out.setdefault(a["owner_entity"], {})[role_key.get(a["anchor_type"], a["anchor_type"])] = \
            [round(float(x), 1) for x in world]
    return out


def compact_clinical(entries):
    """The owner's `clinical` block (data/muscles, Q60) reduced to what the inspector shows: the document, the
    function paragraph, trigger points with their referred pain, what refers pain INTO the muscle, the tests with
    their sensitivity/specificity, his caveat and the sources. Shared by both sides, so the bundle keys it by the
    base id once (about 3 KB per muscle instead of 9 KB per side)."""
    out = []
    for e in entries or []:
        out.append({k: e[k] for k in ("document", "compiled", "compiled_by", "function_biomechanics", "pain_referred_into_this_muscle_from",
                                       "pain_referred_into_territory", "caveat", "tests_caveat", "sources") if e.get(k)}
                   | ({"trigger_points": [{k: t[k] for k in ("location", "referred_pain", "source") if t.get(k)} for t in e["trigger_points"]]}
                      if e.get("trigger_points") else {})
                   | ({"tests": [{k: t.get(k) for k in ("name", "sensitivity", "specificity", "accuracy", "source") if t.get(k) is not None}
                                 for t in e["tests"]]} if e.get("tests") else {}))
    return out


def summarise(folder, rec, anchor_points=None):
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
        # Text alone left "pes anserinus" naming three different tendons'
        # worth of muscle at the same vague spot. Where the muscle's own
        # bone HAS real measured geometry, the anchor generator already
        # resolved this to an actual point (data/rig/anchors.json); adding
        # it here is the difference between reading a place-name and being
        # shown where it is.
        pts = (anchor_points or {}).get(rec.get("id"))
        if pts:
            if pts.get("origin"):
                out["origin_point_mm"] = pts["origin"]
            if pts.get("insertion"):
                out["insertion_point_mm"] = pts["insertion"]
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


def add_skin_depth(index, subjects):
    """Depth below the body surface for every structure in the index, in mm:
    the shallowest and the median distance of its surface from the 'skin'
    mesh, when one of the subjects carries one. This is the number an
    injection plan starts from, so it rides in the bundle and the viewer
    shows it. Computed on the source meshes (subsampled), not the decimated
    ones; nothing here is anatomy, it is a distance."""
    from scipy.spatial import cKDTree
    meshes = {}
    for sub in subjects:
        d = BUILD_DIR / sub
        m = json.loads((d / "manifest.json").read_text())
        v = np.fromfile(d / "vertices.f32", np.float32).reshape(-1, 3)
        for st in m["structures"]:
            a = st["vertex_offset"]; n = st["vertex_count"]
            meshes.setdefault((sub, st["atlas_id"]), []).append(v[a:a + n])
    skin = [np.concatenate(pts) for (sub, aid), pts in meshes.items() if aid == "skin"]
    if not skin:
        return 0
    skin_pts = np.concatenate(skin)[::2]; tree = cKDTree(skin_pts); done = 0
    for e in index:
        pts = meshes.get((e["subject"], e["id"]))
        if not pts or e["id"] == "skin":
            continue
        pv = np.concatenate(pts); pv = pv[::max(1, len(pv) // 4000)]
        dist, _ = tree.query(pv)
        e["depth_min"] = round(float(dist.min()), 1); e["depth_med"] = round(float(np.median(dist)), 1); done += 1
        if e.get("cat") == "nerve":
            prof = depth_profile(np.concatenate(pts), tree, skin_pts)
            if prof:
                e["depth_profile"] = prof
    return done


PROFILE_STEP_MM = 20.0


def depth_profile(pv, tree, skin_pts, step=PROFILE_STEP_MM):
    """A nerve's depth below the skin ALONG ITS COURSE: the structure's vertices
    binned every `step` mm of atlas y (superior axis); per bin the shallowest
    vertex, its distance to the skin, and the skin point nearest to it, so the
    viewer can list the course level by level and put a needle on any row
    (entry = that skin point, target = that vertex). Rows are
    [y_level, depth_mm, px, py, pz, sx, sy, sz], nearest 0.1 mm. Geometry only."""
    if len(pv) < 10:
        return []
    pv = pv[::max(1, len(pv) // 20000)]
    lo = np.floor(pv[:, 1].min() / step) * step
    rows = []
    for y0 in np.arange(lo, pv[:, 1].max() + step, step):
        sel = pv[(pv[:, 1] >= y0) & (pv[:, 1] < y0 + step)]
        if len(sel) < 3:
            continue
        d, j = tree.query(sel); k = int(d.argmin())
        p = sel[k]; s = skin_pts[j[k]]
        rows.append([round(float(y0 + step / 2), 1), round(float(d[k]), 1)] +
                    [round(float(t), 1) for t in p] + [round(float(t), 1) for t in s])
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--subject", action="append",
                     help="repeatable. Earlier subjects win on an atlas_id collision, so "
                          "list the most-trusted/most-complete subject first (e.g. "
                          "--subject vhm_both --subject ct_s1371 lets a second real "
                          "specimen fill in structures the first doesn't have -- upper-body "
                          "bone from a CT case, say -- without overwriting anything the "
                          "first subject already carries).")
    ap.add_argument("-o", "--out", default="build/viewer")
    ap.add_argument("--budget-scale", type=float, default=1.0,
                    help="multiply every triangle budget (categories and overrides) by this; the page must stay "
                         "under the 16 MB artifact cap, so a body with many structures ships at 0.8-0.9")
    args = ap.parse_args()
    scale = args.budget_scale
    subjects = args.subject or ["vhm_both"]

    atlas = load_atlas_records()
    from engine import vh_ingest as vh
    category = {e.entity_id: e.category for e in vh.load_atlas_index()}

    parts, blobs, index = [], [], []
    kept_tris = 0
    source_tris_total = 0
    # Claimed at subject granularity, not structure granularity: one atlas
    # entity can legitimately arrive as SEVERAL mesh parts sharing one
    # atlas_id even within a single subject (the gastrocnemius heads, the
    # forefoot splitter) -- those must all be kept. What must NOT repeat is
    # a later subject re-adding an id an earlier, higher-priority subject
    # already fully provided, so this set is only updated once a subject's
    # own structures have all been processed, not structure-by-structure.
    claimed_by_prior_subjects = set()
    anchor_points = {}
    frame = None
    attributions = []
    subject_totals = {}
    for subject in subjects:
        src = BUILD_DIR / subject
        manifest = json.loads((src / "manifest.json").read_text())
        verts = np.frombuffer((src / "vertices.f32").read_bytes(), dtype=np.float32).reshape(-1, 3)
        faces = np.frombuffer((src / "faces.u32").read_bytes(), dtype=np.uint32).reshape(-1, 3)
        frame = frame or manifest["frame"]
        if manifest.get("attribution"):
            attributions.append(manifest["attribution"])
        source_tris_total += manifest["triangle_count"]

        subj_anchors = resolve_anchor_points(subject)
        for mid, pts in subj_anchors.items():
            anchor_points.setdefault(mid, pts)

        kept_here = 0
        this_subject_ids = set()
        for s in manifest["structures"]:
            aid = s["atlas_id"]
            if aid in claimed_by_prior_subjects:
                continue
            this_subject_ids.add(aid)
            v = verts[s["vertex_offset"]:s["vertex_offset"] + s["vertex_count"]].astype(np.float64)
            f = (faces[s["face_offset"]:s["face_offset"] + s["triangle_count"]].astype(np.int64)
                 - s["vertex_offset"])
            cat = category.get(aid, "other")
            budget = max(200, int(BUDGET_OVERRIDES.get(aid, BUDGET.get(cat, DEFAULT_BUDGET)) * scale))
            q = decimate_quadric(v, f, budget) if aid in SHEET_IDS else None
            if q is not None:
                dv, df = q; cell = 0.0
            else:
                dv, df, cell = decimate_to(v, f, budget)
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
                "subject": subject,
            }
            if rec is not None:
                entry["rec"] = summarise(folder, rec, anchor_points)
            index.append(entry)
            kept_tris += len(df)
            kept_here += len(df)
            parts.append(aid)
        subject_totals[subject] = kept_here
        claimed_by_prior_subjects |= this_subject_ids



    n_depth = add_skin_depth(index, subjects)
    print(f"depth below skin attached to {n_depth} structures")
    blob = b"".join(blobs)
    out_dir = REPO_ROOT / args.out
    out_dir.mkdir(parents=True, exist_ok=True)
    clinical = {}
    for entry in index:
        folder, rec = atlas.get(entry["id"], (None, None))
        if rec is not None and rec.get("clinical"):
            base = entry["id"][:-2] if entry["id"].endswith(("_r", "_l")) else entry["id"]
            clinical.setdefault(base, compact_clinical(rec["clinical"]))
    bundle = {
        "subject": "+".join(subjects),
        "clinical": clinical,
        "frame": frame,
        "quantum_mm": QUANTUM_MM,
        "source_triangles": source_tris_total,
        "triangles": int(kept_tris),
        "attribution": attributions[0] if len(attributions) == 1 else (attributions or None),
        "structures": index,
    }
    (out_dir / "bundle.json").write_text(json.dumps(bundle, separators=(",", ":")))
    (out_dir / "bundle.bin").write_bytes(blob)
    b64 = base64.b64encode(blob).decode("ascii")
    (out_dir / "bundle.b64").write_text(b64)

    print(f"\n{len(index)} structures from {len(subjects)} subject(s): {', '.join(subjects)}")
    for subject, n in subject_totals.items():
        print(f"  {subject}: {n:,} triangles kept")
    print(f"triangles  {source_tris_total:,} -> {kept_tris:,} "
          f"({100 * kept_tris / source_tris_total:.1f}%)")
    print(f"binary     {len(blob) / 1e6:.2f} MB, base64 {len(b64) / 1e6:.2f} MB")
    print(f"index      {len(json.dumps(bundle)) / 1e6:.2f} MB")
    print(f"wrote      {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
