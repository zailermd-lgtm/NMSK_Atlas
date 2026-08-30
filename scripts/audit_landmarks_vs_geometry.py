#!/usr/bin/env python3
"""Test hand-authored bone landmarks against the real bone surfaces.

`data/skeleton/bones.json` gives every bone a local frame and a set of
landmarks in that frame's coordinates -- greater trochanter, adductor
tubercle, medial malleolus and so on. Those numbers were written by hand from
anatomical description. `data/rig/anchors.json` then places ~200 muscle
attachments against them. Nothing has ever checked that they land on the bone.

WHAT IS MEASURED, AND WHAT IS ASSUMED.

To put a landmark in world space you need the bone's frame: an origin and an
orientation. Both are measured from the geometry here, not assumed, for the
bones where the frame definition in bones.json names something the meshes
actually contain:

  femur   origin = centre of a least-squares sphere through the femoral head
                   cartilage, which is what "hip joint center" means.
          Y axis = from that centre toward the midpoint of the distal
                   condyles, per the ISB convention the file cites (Wu 2002).
          This matters: the femur is oblique. Assuming its long axis were
          vertical would misplace the distal landmarks by tens of millimetres
          and the check would be measuring my own assumption.
  tibia   origin = centroid of the two tibial plateau cartilages.
          Y axis = from there toward the centroid of the distal tibial
                   (plafond) cartilage.
          X axis = lateral plateau minus medial plateau.
  hip     origin = centre of a sphere through the acetabular cartilage, which
                   is what "hip (acetabulum) joint center" denotes.
          X axis = the line between the two acetabular centres.
          Y axis = world superior, orthogonalised. The pelvis is defined in
                   the anatomical position and the world frame IS that
                   position, so this is a convention rather than a fit, and
                   is the one assumed axis left anywhere in this script.

TWO METRICS, BECAUSE ONE OF THEM IS BLIND.

Distance to the nearest point of the bone's own mesh is the obvious figure of
merit, and it is not enough. A landmark can name the WRONG FEATURE and still
sit close to the bone, having slid ALONG the surface rather than off it. The
lateral epicondyle scored a comfortable 7.1 mm while being 18 mm too medial.

So paired landmarks are also checked against the dimension they imply. Those
two epicondyles implied a bicondylar width of 65 mm where the geometry
measures 83 -- and a distance BETWEEN two landmarks does not depend on where
either one sits. That is what caught it.

Anchors get a third check: a muscle attachment must be near its bone AND near
the muscle that owns it. Origins and insertions are reported separately,
because the DU meshes are muscle bellies with no tendon, so a tendinous
insertion on a bony prominence is legitimately far from its own muscle.

None of this is pass/fail. These coordinates were authored as approximations
with no geometry to check against; the point is to find out how good they are
and which ones are wrong.

    python3 scripts/audit_landmarks_vs_geometry.py --subject vhm_both
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from engine.vh_ingest import fit_sphere  # noqa: E402

BUILD_DIR = REPO_ROOT / "build" / "vh"
DATA_DIR = REPO_ROOT / "data"


def load_geometry(subject: str):
    out = BUILD_DIR / subject
    manifest = json.loads((out / "manifest.json").read_text())
    verts = np.fromfile(out / "vertices.f32", dtype="<f4").reshape(-1, 3).astype(np.float64)
    blocks = {}
    for rec in manifest["structures"]:
        v0, vn = rec["vertex_offset"], rec["vertex_count"]
        blocks.setdefault(rec["source_file"], verts[v0:v0 + vn])
    return manifest, blocks


def find(blocks, *needles):
    """The one mesh whose filename contains every needle."""
    hits = [v for k, v in blocks.items()
            if all(n.lower() in k.lower().replace("_", "") for n in needles)]
    return hits[0] if len(hits) == 1 else None


def epicondylar_axis(mesh: np.ndarray, origin: np.ndarray,
                     long_axis: np.ndarray, frac: float = 0.18) -> np.ndarray:
    """Mediolateral direction from the widest span of the distal end.

    ISB fixes the femoral and tibial transverse axis on the two epicondyles.
    Taking the distal `frac` of the bone along its own long axis and using the
    two most widely separated points there recovers that line from geometry,
    which removes the last assumed degree of freedom: without it the frame is
    free to rotate about the shaft and any across-axis landmark error is
    partly the assumption rather than the landmark.
    """
    proj = (mesh - origin) @ long_axis
    distal = mesh[proj <= np.quantile(proj, frac)] if (proj <= 0).any() else mesh
    # Widest separation within the distal block, searched on its own spread.
    centred = distal - distal.mean(axis=0)
    perp = centred - np.outer(centred @ long_axis, long_axis)
    u, _, _ = np.linalg.svd(perp.T @ perp)
    axis = u[:, 0]
    return axis / np.linalg.norm(axis)


def orthonormal_frame(origin: np.ndarray, distal: np.ndarray,
                      transverse: np.ndarray | None = None) -> np.ndarray:
    """Rows are the frame's X, Y, Z in world coordinates.

    Y runs origin -> distal but the atlas's +Y is SUPERIOR, so it is negated:
    a landmark 440 mm down the shaft is stored as y = -440.
    """
    y = origin - distal
    y /= np.linalg.norm(y)
    x = transverse if transverse is not None else np.array([1.0, 0.0, 0.0])
    x = x - y * float(x @ y)
    if np.linalg.norm(x) < 1e-6:
        x = np.array([0.0, 0.0, 1.0])
        x = x - y * float(x @ y)
    x /= np.linalg.norm(x)
    # Keep +X pointing to the subject's right, whichever way the fit came out.
    if x[0] < 0:
        x = -x
    return np.vstack([x, y, np.cross(x, y)])


def nearest_distance(points: np.ndarray, cloud: np.ndarray, chunk: int = 256):
    """Distance from each point to the nearest vertex of the mesh."""
    out = np.empty(len(points))
    for i in range(0, len(points), chunk):
        block = points[i:i + chunk]
        d = np.linalg.norm(cloud[None, :, :] - block[:, None, :], axis=2)
        out[i:i + chunk] = d.min(axis=1)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--subject", default="vhm_both")
    ap.add_argument("--worst", type=int, default=12)
    args = ap.parse_args()

    try:
        manifest, blocks = load_geometry(args.subject)
    except FileNotFoundError:
        raise SystemExit(f"No converted geometry for {args.subject!r}. "
                         f"Run the ingest's convert step first.")

    bones = {b["id"]: b for b in json.loads(
        (DATA_DIR / "skeleton" / "bones.json").read_text())}

    frames = {}
    for side, tag in (("r", "right"), ("l", "left")):
        head = find(blocks, tag, "cartilage", "femurhead")
        cond = find(blocks, tag, "cartilage", "femurdistal")
        femur = find(blocks, tag, "bonefemur")
        if head is not None and cond is not None and femur is not None:
            centre, radius, rms = fit_sphere(head)
            y = centre - cond.mean(axis=0)
            y /= np.linalg.norm(y)
            trans = epicondylar_axis(femur, centre, y)
            frames[f"femur_{side}"] = (centre, orthonormal_frame(
                centre, cond.mean(axis=0), trans), f"femoral head sphere fit, "
                f"r={radius:.1f} mm, rms={rms:.2f} mm; transverse axis from "
                f"the distal epicondylar spread", "both")

        lat = find(blocks, tag, "cartilage", "tibialateral")
        # The release spells this 'TibialMedial' on the right and
        # 'TibiaMedial' on the left. `or` cannot be used to pick between two
        # arrays -- numpy raises on their truth value -- so test explicitly.
        med = find(blocks, tag, "cartilage", "tibialmedial")
        if med is None:
            med = find(blocks, tag, "cartilage", "tibiamedial")
        plaf = find(blocks, tag, "cartilage", "tibiadistal")
        if lat is not None and med is not None and plaf is not None:
            centre = np.vstack([lat, med]).mean(axis=0)
            # The plateau cartilages themselves give the transverse axis
            # directly: lateral minus medial is the mediolateral line.
            trans = lat.mean(axis=0) - med.mean(axis=0)
            frames[f"tibia_{side}"] = (centre, orthonormal_frame(
                centre, plaf.mean(axis=0), trans), "centroid of both tibial "
                "plateau cartilages; long axis toward the plafond, transverse "
                "axis from lateral-minus-medial plateau", "both")

    # Hip: acetabular sphere centre, with the transverse axis taken from the
    # line between the two acetabula -- so it needs both sides present.
    acetabula = {}
    for side, tag in (("r", "right"), ("l", "left")):
        cup = find(blocks, tag, "cartilage", "pelvisacetabulum")
        if cup is not None:
            acetabula[side] = fit_sphere(cup)
    if {"r", "l"} <= set(acetabula):
        across = acetabula["r"][0] - acetabula["l"][0]
        for side in ("r", "l"):
            centre, radius, rms = acetabula[side]
            up = np.array([0.0, 1.0, 0.0])
            frames[f"hip_bone_{side}"] = (centre, orthonormal_frame(
                centre, centre - up * 100.0, across),
                f"acetabular sphere fit, r={radius:.1f} mm, rms={rms:.2f} mm; "
                f"transverse axis from the interacetabular line; superior axis "
                f"by anatomical-position convention, not fitted", "transverse")

    meshes = {"femur_r": find(blocks, "right", "bonefemur"),
              "femur_l": find(blocks, "left", "bonefemur"),
              "tibia_r": find(blocks, "right", "bonetibia"),
              "tibia_l": find(blocks, "left", "bonetibia"),
              "hip_bone_r": find(blocks, "right", "bonepelvis"),
              "hip_bone_l": find(blocks, "left", "bonepelvis")}

    print(f"subject {args.subject}\n")
    rows = []
    for bone_id, (origin, basis, how, fitted) in sorted(frames.items()):
        mesh = meshes.get(bone_id)
        bone = bones.get(bone_id)
        if mesh is None or not bone:
            continue
        # A landmark at the frame's own origin cannot test anything -- it IS
        # the origin. The femoral head sits at [0,0,0] by definition, so its
        # "distance to the surface" is just the head radius and says nothing
        # about the authored coordinates.
        landmarks = [lm for lm in bone.get("landmarks", [])
                     if lm.get("position_local_mm")
                     and np.linalg.norm(lm["position_local_mm"]) > 1e-6]
        if not landmarks:
            continue
        local = np.array([lm["position_local_mm"] for lm in landmarks], float)
        world = origin + local @ basis
        dist = nearest_distance(world, mesh)
        # Split the error along the bone's own long axis from the error across
        # it: the long axis is measured, the transverse rotation is not, so
        # the two are not equally trustworthy.
        delta = world - mesh[np.argmin(
            np.linalg.norm(mesh[None, :, :] - world[:, None, :], axis=2), axis=1)]
        along = np.abs(delta @ basis[1])
        across = np.sqrt(np.maximum(dist ** 2 - along ** 2, 0.0))
        print(f"{bone_id}   frame origin from {how}")
        print(f"  {len(landmarks)} landmarks, distance to nearest bone surface:")
        print(f"    median {np.median(dist):6.1f} mm   mean {dist.mean():6.1f}"
              f"   max {dist.max():6.1f}")
        # Which axis is trustworthy differs by bone. The femur and tibia have
        # a FITTED long axis; the pelvis's long axis is the anatomical-position
        # convention and only its transverse axis is fitted. Calling both
        # "measured" would quietly credit the pelvis with a precision it does
        # not have, and its landmarks' errors sit mostly on that very axis.
        long_tag = "fitted" if fitted == "both" else "ASSUMED"
        print(f"    along the long axis ({long_tag}): median "
              f"{np.median(along):.1f} mm; across it (fitted): "
              f"median {np.median(across):.1f} mm")
        for lm, d, a, c in sorted(zip(landmarks, dist, along, across),
                                  key=lambda t: -t[1])[:3]:
            print(f"      {d:6.1f} mm  (along {a:5.1f}, across {c:5.1f})  "
                  f"{lm['name'][:62]}")
        print()
        rows.extend((d, bone_id, lm["name"]) for lm, d in zip(landmarks, dist))

    # ---- span check: does the atlas imply the right bone dimensions? -----
    #
    # Distance-to-surface has a blind spot. A landmark can name the WRONG
    # FEATURE and still sit near the bone, because it slid along the surface
    # rather than off it. The lateral epicondyle scored a mild 7.1 mm that
    # way while being 18 mm too medial; what exposed it was that the two
    # epicondyles then implied a bicondylar width of 65 mm where the geometry
    # measures 83 mm on both sides. A distance between two landmarks is
    # independent of where either one sits, so it catches what the other
    # check cannot.
    print("\ndistances between paired landmarks -- atlas vs measured")
    pairs = [("femur", "medial epicondyle", "lateral epicondyle",
              "bicondylar width")]
    for stem, a_name, b_name, label in pairs:
        for side in ("r", "l"):
            bone = bones.get(f"{stem}_{side}")
            if not bone or f"{stem}_{side}" not in frames:
                continue
            pick = {}
            for lm in bone.get("landmarks", []):
                for want in (a_name, b_name):
                    if lm["name"].startswith(want):
                        pick[want] = np.array(lm["position_local_mm"], float)
            if len(pick) != 2:
                continue
            origin, basis = frames[f"{stem}_{side}"][:2]
            mesh = meshes[f"{stem}_{side}"]
            local = (mesh - origin) @ basis.T
            level = pick[a_name][1]
            band = local[np.abs(local[:, 1] - level) < 8.0]
            if len(band) < 20:
                continue
            measured = float(band[:, 0].max() - band[:, 0].min())
            stated = float(abs(pick[a_name][0] - pick[b_name][0]))
            flag = "" if abs(stated - measured) < 8 else "   <-- MISMATCH"
            print(f"  {stem}_{side}  {label}: atlas {stated:5.1f} mm, "
                  f"measured {measured:5.1f} mm{flag}")

    # ---- anchors: are muscle attachments on their own muscle? ------------
    #
    # data/rig/anchors.json places 205 muscle origins and insertions in bone
    # frames. A landmark only has to be on its bone; an ANCHOR has to be on
    # its bone AND on the muscle that owns it. The second half has never been
    # testable before, and it is the one that catches an attachment placed on
    # the correct bone but at the wrong end of it.
    anchors = json.loads((DATA_DIR / "rig" / "anchors.json").read_text())
    # blocks is keyed by source file; regroup it by the atlas entity each
    # mesh was mapped to, so a muscle split across two meshes (the
    # gastrocnemius heads, say) is tested as the one entity the anchor names.
    by_atlas_id = {}
    for rec in manifest["structures"]:
        block = blocks.get(rec["source_file"])
        if block is not None:
            by_atlas_id.setdefault(rec["atlas_id"], []).append(block)
    muscle_cloud = {k: np.vstack(v) for k, v in by_atlas_id.items()}

    checked, bone_far, muscle_far, no_muscle = [], [], [], 0
    for a in anchors:
        frame = frames.get(a.get("parent_bone_frame"))
        if not frame:
            continue
        origin, basis = frame[:2]
        world = origin + np.array(a["local_position_mm"], float) @ basis
        bone_mesh = meshes.get(a["parent_bone_frame"])
        d_bone = (float(nearest_distance(world[None, :], bone_mesh)[0])
                  if bone_mesh is not None else float("nan"))
        owner = a.get("owner_entity")
        cloud = muscle_cloud.get(owner)
        if cloud is None:
            no_muscle += 1
            d_muscle = float("nan")
        else:
            d_muscle = float(nearest_distance(world[None, :], cloud)[0])
        checked.append((a["id"], owner, d_bone, d_muscle, a.get("anchor_type", "")))
        if d_bone == d_bone and d_bone > 20:
            bone_far.append((d_bone, a["id"], owner))
        if d_muscle == d_muscle and d_muscle > 20:
            muscle_far.append((d_muscle, a["id"], owner))

    if checked:
        db = np.array([c[2] for c in checked])
        print(f"\nanchors on bones with a measured frame: {len(checked)} of "
              f"{len(anchors)}")
        print(f"  to its own bone   median {np.median(db):5.1f} mm   "
              f"{int((db > 20).sum())} beyond 20 mm")
        # Origins and insertions are not comparable here. These meshes are
        # muscle BELLIES: the DU segmentation does not include tendon. A
        # tendinous insertion on a bony prominence is therefore legitimately
        # far from its own muscle -- piriformis inserts on the greater
        # trochanter by a tendon that simply is not in the geometry. A fleshy
        # ORIGIN has no such excuse, so that is where this check has teeth.
        for kind in ("muscle_origin", "muscle_insertion"):
            sub = np.array([c[3] for c in checked
                            if c[4] == kind and c[3] == c[3]])
            if not len(sub):
                continue
            note = ("" if kind == "muscle_origin"
                    else "   (tendon absent from these meshes -- see note)")
            print(f"  {kind:16} to its own muscle: median {np.median(sub):5.1f}"
                  f" mm, {int((sub > 20).sum())}/{len(sub)} beyond 20 mm{note}")
        if no_muscle:
            print(f"  ({no_muscle} anchors own a structure with no geometry here)")
        muscle_far = [r for r in muscle_far
                      if next(c[4] for c in checked if c[1] == r[2]
                              and c[0] == r[1]) == "muscle_origin"]
        for label, rowset in (("far from its bone", bone_far),
                              ("ORIGINS far from their own muscle", muscle_far)):
            if rowset:
                print(f"\n  {len(rowset)} anchors {label}:")
                for d, aid, owner in sorted(rowset, reverse=True)[:10]:
                    print(f"    {d:6.1f} mm  {aid[:52]:54} -> {owner}")

    if not rows:
        print("No bone had both a measurable frame and geometry.")
        return 0

    all_d = np.array([r[0] for r in rows])
    print(f"overall: {len(rows)} landmarks, median {np.median(all_d):.1f} mm "
          f"from the bone surface, {int((all_d < 15).sum())} within 15 mm, "
          f"{int((all_d > 40).sum())} beyond 40 mm")
    print(f"\nworst {args.worst}:")
    for d, bone_id, name in sorted(rows, key=lambda t: -t[0])[:args.worst]:
        print(f"  {d:6.1f} mm  {bone_id:9} {name[:70]}")
    print("""
These are approximations being measured, not tests being failed. The
coordinates were written from anatomical description without geometry to
check against; this is the first time there has been any.

Both frame axes are measured from the geometry -- the long axis from the
joint centres, the transverse axis from the epicondyles or the plateau
cartilages -- so an across-axis error belongs to the landmark, not to the
frame. An earlier version of this report said the rotation was unmeasured;
that was left behind after the epicondylar fit was added.

Read the paired-landmark spans above as well as the distances. A landmark
can name the WRONG FEATURE and still sit close to the bone, because it slid
ALONG the surface rather than off it, and distance-to-surface cannot see
that. The lateral epicondyle scored a comfortable 7.1 mm while being 18 mm
too medial; only the implied bicondylar width, 65 mm against 83 measured,
gave it away.
""")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
