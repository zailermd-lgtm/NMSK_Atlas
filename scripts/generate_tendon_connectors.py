#!/usr/bin/env python3
"""Generate PROCEDURAL/RULE-BASED tendon connector meshes bridging already-shipped
muscle geometry to already-shipped bone geometry.

Q118's own investigation (see PROJECT_STATE.md) found `data/tendons/` (51 entities) at
literal 0% geometry coverage on either body (Q117). This script does NOT segment new
tendon anatomy from imaging -- this project has none for tendons. It generates a
disclosed, geometrically-derived connector for the SMALL subset of tendons where BOTH
endpoints (a muscle mesh and a bone landmark) already resolve to real, already-anchored
3D coordinates through this project's OWN existing landmark/anchor system
(`scripts/audit_landmarks_vs_geometry.py:build_frames` + `data/rig/anchors.json` +
`data/skeleton/bones.json`'s own numeric landmarks). This is the exact same honesty
bar Q104's intervertebral discs used: real position (measured from real bone/muscle
geometry), an geometrically arbitrary but disclosed cross-section, never claimed as
segmented tendon imaging.

WHY ONLY 3 OF 51 TENDONS (6 of 51 counting left/right separately x further doubled
for two sides = 6 unique tendon ids, 12 mesh instances across both bodies):

`build_frames()` -- the ONE place this codebase turns a bone-local landmark into a
world coordinate -- currently only constructs a MEASURED frame for femur, hip_bone
and patella on this session's geometry. It cannot for tibia, tarsals, humerus, radius,
ulna, scapula, clavicle, carpals, metacarpals, phalanges, hyoid, mandible or sternum,
because its cartilage-mesh identification keys (filename substrings like
'tibialateral'/'tibiamedial'/'tibiadistal'/'cartilage,talus') no longer match this
session's "recovered from the published viewer" cartilage naming (fused
'knee_articular_cartilage_l/r', 'ankle_articular_cartilage_l/r', etc). That is a real,
pre-existing pipeline gap, not something this script invents a workaround for -- per
this item's own hard constraint ("do not guess at attachment coordinates ... decline
it"), every tendon whose distal bone is one of those un-resolvable bones is declined,
not patched around. See PROJECT_STATE.md's Q118 entry for the full accounting of all
51 tendons.

Of the 12 tendons whose distal bone IS resolvable (femur x6, hip_bone x4, patella x2),
this script ships only:
  - iliopsoas_tendon_{r,l}            (femur, lesser trochanter)     -- clean, 9-11mm gap
  - adductor_magnus_distal_tendon_{r,l} (femur, adductor tubercle)   -- clean, ~13-15mm gap
  - quadriceps_tendon_{r,l}           (patella, base)                -- clean, has a
    project-DECLARED via-point path for all 4 contributing muscles, clear of bone

and DECLINES (see PROJECT_STATE.md for the measured reason each time):
  - gluteal_tendon_complex_{r,l}      (feasible numbers, but a broad flat_aponeurotic
    2-muscle sheet is a materially different shape claim than a tapered cord and was
    not attempted this session -- time-boxed, not because the numbers are bad)
  - proximal_hamstring_tendon_{r,l}   (2 of 3 contributing heads are clean; the third,
    biceps_femoris's origin, is BLOCKED BY BONE in a straight line -- a genuine wrap
    case this project's rig schema has no via-point for; modeling only 2 of 3
    documented heads would misrepresent an already-fully-documented 3-muscle structure)
  - conjoint_tendon_{r,l}             (its own parent muscle, internal_oblique_r, has
    NO shipped geometry in this session's raw ingest at all; transversus_abdominis has
    no anchor of any kind; both parents are Q114's own flagged "one rule-based
    abdominal-wall construction" fragmentation case)

GEOMETRY METHOD (once both endpoints resolve):
  1. muscle endpoint = the vertex of the muscle's OWN shipped mesh nearest the world
     landmark point (real, measured -- never assumed to be the muscle's bounding-box
     tip).
  2. bone endpoint = the world position of the bone's own already-authored landmark
     (via `data/rig/anchors.json` where a muscle_insertion anchor exists, or directly
     from `data/skeleton/bones.json`'s own numeric landmark otherwise -- adductor
     magnus has no anchors.json entry but its bone DOES carry the numbered "adductor
     tubercle (adductor magnus insertion)" landmark directly).
  3. LENGTH = the real, measured straight-line distance between those two points on
     THIS body's own geometry -- never invented, never copied from the other body.
  4. CROSS-SECTION is the one genuinely arbitrary modeling choice, exactly like Q104's
     disc radius: the muscle-end radius is MEASURED (the RMS spread of the muscle's own
     vertices within 15mm of its endpoint, projected perpendicular to the tendon axis
     -- a real number describing how thick the belly is where it narrows into tendon,
     not a segmented tendon caliper), clamped to [3, 18] mm as a sanity guard; the
     bone-end radius is that value x0.55 (a disclosed modeling simplification: real
     tendons narrow toward their bony footprint; this project has no imaging to measure
     the real taper ratio). quadriceps_tendon is the one case with 4 converging
     contributors sharing one documented insertion point (all four muscles' own
     `data/rig/anchors.json` entries carry the IDENTICAL local_position_mm on the
     patella) -- modeled as 4 separate tapering cords converging to and WELDED at that
     one shared point, so the combined structure is a single connected component, not
     as one fused trilaminar sheet (a disclosed simplification from the real trilaminar
     anatomy Zeiss et al. 1992 describes, already cited in this tendon's own record).

Every generated tendon's manifest `source_file` reads
"PROCEDURAL/RULE-BASED (Q118) ... not segmented from imaging", and
`data/tendons/*.json`'s own record for each id gets a `procedural_geometry` block with
the real measured length/radius and this same disclosure, so the badge survives in the
subject metadata, the entity record, AND PROJECT_STATE.md.

Usage:
    python3 scripts/generate_tendon_connectors.py --body male
    python3 scripts/generate_tendon_connectors.py --body female
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.audit_landmarks_vs_geometry import build_frames, place  # noqa: E402

DATA_DIR = REPO_ROOT / "data"
BUILD_DIR = REPO_ROOT / "build" / "vh"

# Same first-subject-wins order the real rebuild scripts use (scripts/vhm_rebuild_bundle.sh,
# scripts/cryo/vhf_rebuild_bundle.sh), so the geometry pulled here is EXACTLY what
# already ships for that body, not a stand-in built for this script alone.
def male_order() -> list[str]:
    order = []
    if (BUILD_DIR / "ct_vhm_pfloor_fix" / "manifest.json").exists():
        order.append("ct_vhm_pfloor_fix")
    order += ["ct_vhm_foot", "vhm_both"]
    return order


def female_order() -> list[str]:
    order = ["ct_vhf_head", "ct_vhf_legs", "ct_vhf_tarsal", "ct_vhf_armb"]
    if (BUILD_DIR / "ct_vhf_descaorta" / "manifest.json").exists():
        order.append("ct_vhf_descaorta")
    if (BUILD_DIR / "ct_vhf_hyoid_fix" / "manifest.json").exists():
        order.append("ct_vhf_hyoid_fix")
    order += ["ct_vhf"]
    if (BUILD_DIR / "ct_vhf_xfersepta_fix" / "manifest.json").exists():
        order.append("ct_vhf_xfersepta_fix")
    order += ["xfer_vhm2vhf_sep", "xfer_vhm2vhf"]
    return order


# The tendon ids this script attempts, mirroring the resolvable set documented above.
# Each entry: (tendon_id, [(contributing_muscle_id, distal_ratio), ...], bone_id,
#              landmark source: ("anchor", muscle_id) or ("bone_landmark", substring))
TENDON_PLAN = {
    "iliopsoas_tendon": {
        "muscles": ["iliopsoas"], "bone": "femur",
        "landmark": ("anchor", "iliopsoas"),
    },
    "adductor_magnus_distal_tendon": {
        "muscles": ["adductor_magnus"], "bone": "femur",
        "landmark": ("bone_landmark", "adductor tubercle"),
    },
    "quadriceps_tendon": {
        "muscles": ["rectus_femoris", "vastus_medialis", "vastus_lateralis", "vastus_intermedius"],
        "bone": "patella",
        "landmark": ("anchor", "rectus_femoris"),
    },
}

MIN_RADIUS_MM = 3.0
MAX_RADIUS_MM = 18.0
DISTAL_TAPER_RATIO = 0.55


def load_geometry_merged(order: list[str], needed_ids: set[str]):
    """{atlas_id: (N,3) float64 world-mm vertices}, first subject in `order` to carry
    an id wins -- reproduces exactly what scripts/export_viewer_bundle.py's own
    claimed_by_prior_subjects logic would ship for that id."""
    out: dict[str, np.ndarray] = {}
    claimed: set[str] = set()
    for sub in order:
        mf = BUILD_DIR / sub / "manifest.json"
        if not mf.exists():
            continue
        man = json.loads(mf.read_text())
        verts = np.fromfile(BUILD_DIR / sub / "vertices.f32", dtype="<f4").reshape(-1, 3).astype(np.float64)
        this_subject: dict[str, list] = {}
        for s in man["structures"]:
            aid = s["atlas_id"]
            if aid not in needed_ids or aid in claimed:
                continue
            v0, vn = s["vertex_offset"], s["vertex_count"]
            this_subject.setdefault(aid, []).append(verts[v0:v0 + vn])
        for aid, chunks in this_subject.items():
            out[aid] = chunks
            claimed.add(aid)
    return {k: np.vstack(v) for k, v in out.items()}


def nearest_point(cloud: np.ndarray, target: np.ndarray) -> np.ndarray:
    d = np.linalg.norm(cloud - target[None, :], axis=1)
    return cloud[int(np.argmin(d))]


def measured_radius(cloud: np.ndarray, endpoint: np.ndarray, axis: np.ndarray,
                    window_mm: float = 15.0) -> float:
    """RMS spread of the muscle's own vertices near its endpoint, projected
    perpendicular to the tendon axis -- a real measurement of how thick the belly is
    where it narrows into tendon, not an assumed constant. Clamped to a sane range as
    a guard against a degenerate/near-empty window, never silently used unclamped."""
    d = np.linalg.norm(cloud - endpoint[None, :], axis=1)
    near = cloud[d <= window_mm]
    if len(near) < 8:
        near = cloud[np.argsort(d)[:8]]
    rel = near - endpoint[None, :]
    along = rel @ axis
    perp = rel - np.outer(along, axis)
    rms = float(np.sqrt(np.mean(np.sum(perp * perp, axis=1))))
    return float(np.clip(rms, MIN_RADIUS_MM, MAX_RADIUS_MM))


def ring(center: np.ndarray, axis: np.ndarray, radius: float, n: int = 14) -> np.ndarray:
    """n points around `center`, in the plane perpendicular to `axis`, radius `radius`.
    Degenerate (radius ~ 0) collapses every point to `center` -- used for the
    quadriceps tendon's shared converging apex."""
    ref = np.array([1.0, 0.0, 0.0]) if abs(axis[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    u = ref - axis * float(ref @ axis)
    u /= np.linalg.norm(u)
    v = np.cross(axis, u)
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False)
    return np.vstack([center + radius * (np.cos(a) * u + np.sin(a) * v) for a in angles])


def tapered_tube(p0: np.ndarray, p1: np.ndarray, r0: float, r1: float, n: int = 14):
    """A capped frustum (or cone, if r1==0) from p0 (radius r0) to p1 (radius r1)."""
    axis = p1 - p0
    length = float(np.linalg.norm(axis))
    axis = axis / length
    ring0 = ring(p0, axis, r0, n)
    verts = [ring0]
    faces = []
    if r1 <= 1e-6:
        apex_idx = n
        verts.append(p1[None, :])
        for i in range(n):
            j = (i + 1) % n
            faces.append([i, j, apex_idx])
    else:
        ring1 = ring(p1, axis, r1, n)
        verts.append(ring1)
        for i in range(n):
            j = (i + 1) % n
            faces.append([i, j, n + j])
            faces.append([i, n + j, n + i])
    verts = np.vstack(verts)
    # Cap the p0 end (fan from its centroid) so the piece is closed there; the p1 end
    # is either the shared apex (already closed, a point) or is left open ONLY when a
    # caller says so (not used here -- every shipped tendon in this script caps both
    # ends, since none of them continue into another already-shipped mesh at p1).
    cap0 = len(verts)
    verts = np.vstack([verts, p0[None, :]])
    for i in range(n):
        j = (i + 1) % n
        faces.append([j, i, cap0])
    if r1 > 1e-6:
        cap1 = len(verts)
        verts = np.vstack([verts, p1[None, :]])
        for i in range(n):
            j = (i + 1) % n
            faces.append([n + i, n + j, cap1])
    return verts, np.array(faces, dtype=np.int64)


def weld(verts: np.ndarray, faces: np.ndarray, tol_mm: float = 0.01):
    """Merge vertices at (near-)identical positions so pieces that meet at a shared
    point (the quadriceps tendon's 4 converging cords) become ONE connected mesh, not
    4 touching-but-topologically-separate ones."""
    key = np.round(verts / tol_mm).astype(np.int64)
    _, first_index, inverse = np.unique(key, axis=0, return_index=True, return_inverse=True)
    inverse = np.asarray(inverse).reshape(-1)
    new_verts = verts[first_index]
    new_faces = inverse[faces.reshape(-1)].reshape(faces.shape)
    return new_verts, new_faces


def mesh_components(faces: np.ndarray, n_verts: int) -> int:
    adj = [[] for _ in range(n_verts)]
    for a, b, c in faces:
        adj[a] += [b, c]; adj[b] += [a, c]; adj[c] += [a, b]
    seen = np.zeros(n_verts, dtype=bool)
    n_comp = 0
    for start in range(n_verts):
        if seen[start]:
            continue
        n_comp += 1
        stack = [start]
        seen[start] = True
        while stack:
            u = stack.pop()
            for w in adj[u]:
                if not seen[w]:
                    seen[w] = True
                    stack.append(w)
    return n_comp


def build_tendon(tendon_id: str, plan: dict, by_atlas_id: dict, frames: dict, bones: dict):
    side = tendon_id[-2:]  # "_r" or "_l"
    bone_id = plan["bone"] + side
    frame = frames.get(bone_id)
    if frame is None:
        return None, f"no measured frame for {bone_id}"
    bone_record = bones.get(bone_id)

    if plan["landmark"][0] == "anchor":
        anchors = json.loads((DATA_DIR / "rig" / "anchors.json").read_text())
        rep = plan["landmark"][1] + tendon_id[-2:]  # e.g. "iliopsoas" + "_r"
        hit = [a for a in anchors if a["owner_entity"] == rep and a["anchor_type"] == "muscle_insertion"]
        if not hit:
            return None, f"no muscle_insertion anchor for {rep}"
        local_mm = hit[0]["local_position_mm"]
    else:
        needle = plan["landmark"][1]
        hits = [lm for lm in bone_record.get("landmarks", []) if needle in lm["name"].lower()]
        if len(hits) != 1:
            return None, f"expected exactly one bone landmark containing {needle!r}, found {len(hits)}"
        local_mm = hits[0]["position_local_mm"]

    target_world = place(local_mm, frame, bone_record)

    pieces = []
    per_muscle = {}
    for m in plan["muscles"]:
        mid = m + tendon_id[-2:]
        cloud = by_atlas_id.get(mid)
        if cloud is None:
            return None, f"no shipped geometry for {mid} on this body"
        endpoint = nearest_point(cloud, target_world)
        axis_vec = target_world - endpoint
        gap = float(np.linalg.norm(axis_vec))
        if gap < 1e-3:
            return None, f"{mid} already touches the target point (gap {gap:.2f} mm) -- no tendon to model"
        axis = axis_vec / gap
        r0 = measured_radius(cloud, endpoint, axis)
        r1 = 0.0 if len(plan["muscles"]) > 1 else max(MIN_RADIUS_MM * 0.5, r0 * DISTAL_TAPER_RATIO)
        v, f = tapered_tube(endpoint, target_world, r0, r1)
        pieces.append((v, f))
        per_muscle[mid] = {"gap_mm": round(gap, 2), "proximal_radius_mm": round(r0, 2)}

    all_v, all_f, off = [], [], 0
    for v, f in pieces:
        all_v.append(v)
        all_f.append(f + off)
        off += len(v)
    verts = np.vstack(all_v)
    faces = np.vstack(all_f)
    verts, faces = weld(verts, faces)
    n_comp = mesh_components(faces, len(verts))

    meta = {
        "target_world_mm": [round(float(x), 2) for x in target_world],
        "bone": bone_id,
        "per_muscle": per_muscle,
        "n_components": n_comp,
        "n_vertices": int(len(verts)),
        "n_faces": int(len(faces)),
    }
    return (verts, faces, meta), None


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--body", choices=["male", "female"], required=True)
    ap.add_argument("-o", "--out-dir", default=str(DATA_DIR / "ct_sources" / "task_outputs"))
    args = ap.parse_args()

    order = male_order() if args.body == "male" else female_order()
    suffix_ids = set()
    for tid, plan in TENDON_PLAN.items():
        for side in ("r", "l"):
            for m in plan["muscles"]:
                suffix_ids.add(m + "_" + side)
            suffix_ids.add(plan["bone"] + "_" + side)
    by_atlas_id = load_geometry_merged(order, suffix_ids)
    frames = build_frames(by_atlas_id, {}, {})
    bones = {b["id"]: b for b in json.loads((DATA_DIR / "skeleton" / "bones.json").read_text())}

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    report = {}
    for tid, plan in TENDON_PLAN.items():
        for side in ("r", "l"):
            full_id = f"{tid}_{side}"
            result, err = build_tendon(full_id, plan, by_atlas_id, frames, bones)
            if err:
                print(f"[{args.body}] {full_id}: DECLINED -- {err}")
                report[full_id] = {"status": "declined", "reason": err}
                continue
            verts, faces, meta = result
            obj_path = out_dir / f"tendon_{args.body}_{full_id}.obj"
            with open(obj_path, "w") as f:
                f.write(f"# procedural tendon connector, Q118, body={args.body}, id={full_id}\n")
                for x, y, z in verts:
                    f.write(f"v {x:.4f} {y:.4f} {z:.4f}\n")
                for a, b, c in faces:
                    f.write(f"f {a+1} {b+1} {c+1}\n")
            print(f"[{args.body}] {full_id}: OK, {meta['n_vertices']} verts, "
                  f"{meta['n_faces']} faces, {meta['n_components']} component(s) -> {obj_path}")
            report[full_id] = {"status": "generated", **meta, "obj_path": str(obj_path)}

    report_path = out_dir / f"tendon_generation_report_{args.body}.json"
    report_path.write_text(json.dumps(report, indent=2))
    print(f"wrote {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
