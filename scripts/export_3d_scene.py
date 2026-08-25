#!/usr/bin/env python3
"""Export a solid-geometry 3D scene from the atlas's numeric data, for the
standalone viewer artifact.

Emits, per structure, a parametric SOLID primitive (tapered capsule /
ellipsoid) rather than a bare point, so the viewer can render shaded
volumes: bone shafts, muscle bellies, ligament cords, cartilage pads and
tendon cords.

HONESTY NOTE (read before treating this as ground truth): bones.json's
numeric landmarks and joints.json's ROM data are real, cited data,
covering only the upper- and lower-limb flagship chains (see
docs/VERIFICATION.md's ~34.5% anchor-resolution figure). This script adds
two things that do NOT exist elsewhere in the repo:

  1. A derived REST-POSE assembly of the per-bone local frames into one
     connected skeleton, by matching each joint to the parent bone's
     landmark that names that same joint, and assuming IDENTITY ROTATION
     between adjacent local frames (no per-bone axis-orientation data
     exists to compute a real one). Bone LENGTHS and attachment
     POSITIONS ALONG each bone are accurate to the cited data; the
     overall limb silhouette is a schematic reference configuration.
  2. VOLUMETRIC THICKNESS. The atlas stores no bone diameters or muscle
     belly cross-sections in millimetres of *geometry* -- muscle PCSA is
     a physiological cross-section (force-relevant), not an anatomical
     belly width. Every radius below is therefore an illustrative
     modelling constant chosen for legibility, NOT measured data. Bone
     radii come from a per-bone table; muscle belly radii are derived
     from PCSA only as a relative size cue (bigger PCSA -> thicker
     belly), deliberately compressed via a cube root and clamped.

This is a schematic solid preview, not a segmented scan-derived mesh.
docs/ROADMAP.md Stage 5 covers the real path to true surface geometry
(NIH Visible Human / BodyParts3D / Z-Anatomy import). All of the above is
surfaced in the viewer's own "About this data" panel.
"""
import json
import math
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from engine import geometry as geo  # noqa: E402

DATA = REPO_ROOT / "data"


def load(*parts):
    return json.loads((DATA / Path(*parts)).read_text())


BONES = {b["id"]: b for b in load("skeleton", "bones.json")}
JOINTS = {j["id"]: j for j in load("skeleton", "joints.json")}
ANCHORS = load("rig", "anchors.json")


def landmark(bone_id, name_substr):
    for lm in BONES[bone_id].get("landmarks", []):
        if name_substr.lower() in lm["name"].lower() and "position_local_mm" in lm:
            return np.array(lm["position_local_mm"], dtype=float)
    raise KeyError(f"no landmark matching '{name_substr}' on {bone_id}")


JOINT_LANDMARK_MATCH = {
    "glenohumeral_r": ("scapula_r", "glenoid cavity", False),
    "glenohumeral_l": ("scapula_l", "glenoid cavity", False),
    "elbow_r": ("humerus_r", "trochlea (humeroulnar", False),
    "elbow_l": ("humerus_l", "trochlea (humeroulnar", False),
    "radioulnar_r": ("ulna_r", "radial notch", False),
    "radioulnar_l": ("ulna_l", "radial notch", False),
    "wrist_r": ("radius_r", "carpal articular surface", False),
    "wrist_l": ("radius_l", "carpal articular surface", False),
    "first_carpometacarpal_r": ("carpals_r", "capitate", True),
    "first_carpometacarpal_l": ("carpals_l", "capitate", True),
    "metacarpophalangeal_r": ("metacarpals_r", "metacarpal heads", False),
    "metacarpophalangeal_l": ("metacarpals_l", "metacarpal heads", False),
    "hip_r": ("hip_bone_r", "acetabulum", False),
    "hip_l": ("hip_bone_l", "acetabulum", False),
    "knee_r": ("femur_r", "medial/lateral condyles", False),
    "knee_l": ("femur_l", "medial/lateral condyles", False),
    "patellofemoral_r": ("femur_r", "patellar (trochlear) groove", False),
    "patellofemoral_l": ("femur_l", "patellar (trochlear) groove", False),
    "proximal_tibiofibular_r": ("tibia_r", "medial/lateral condyles", True),
    "proximal_tibiofibular_l": ("tibia_l", "medial/lateral condyles", True),
    "ankle_r": ("tibia_r", "medial malleolus", True),
    "ankle_l": ("tibia_l", "medial malleolus", True),
    "metatarsophalangeal_r": ("metatarsals_r", "metatarsal heads", False),
    "metatarsophalangeal_l": ("metatarsals_l", "metatarsal heads", False),
}
SYNTHETIC_CHAIN = {
    "tarsals_r": ("metatarsals_r", "tarsals_r", "cuneiforms", True),
    "tarsals_l": ("metatarsals_l", "tarsals_l", "cuneiforms", True),
}

# NOTE on clavicle: clavicle_{r,l}'s authored local frame puts its lateral
# (acromial) landmark at NEGATIVE local X, the opposite sign convention
# from every other limb bone here. Chaining through it under this script's
# identity-rotation simplification would place the right arm on the LEFT.
# Each arm chain is therefore rooted at the SCAPULA, and clavicle is drawn
# as an independently-rooted element. A real internal-consistency quirk in
# data/skeleton/bones.json worth fixing at source in a future pass.
ROOTS = {
    "scapula_r": geo.vec3(170, 470, 15),
    "scapula_l": geo.vec3(-170, 470, 15),
    "clavicle_r": geo.vec3(30, 480, 20),
    "clavicle_l": geo.vec3(-30, 480, 20),
    "hip_bone_r": geo.vec3(90, 0, 0),
    "hip_bone_l": geo.vec3(-90, 0, 0),
}
CHAINS = {
    "scapula_r": ["glenohumeral_r", "elbow_r", "radioulnar_r", "wrist_r", "first_carpometacarpal_r", "metacarpophalangeal_r"],
    "scapula_l": ["glenohumeral_l", "elbow_l", "radioulnar_l", "wrist_l", "first_carpometacarpal_l", "metacarpophalangeal_l"],
    "hip_bone_r": ["hip_r", "knee_r", "patellofemoral_r", "proximal_tibiofibular_r", "ankle_r", "metatarsophalangeal_r"],
    "hip_bone_l": ["hip_l", "knee_l", "patellofemoral_l", "proximal_tibiofibular_l", "ankle_l", "metatarsophalangeal_l"],
}
STANDALONE_ROOTS = ["clavicle_r", "clavicle_l"]

global_tf = {}
approx_joints = set()


def place_root(bone_id):
    global_tf[bone_id] = geo.Transform(np.eye(3), ROOTS[bone_id])


def try_resolve_joint(jid):
    j = JOINTS[jid]
    if j["parent_bone"] not in global_tf or j["child_bone"] in global_tf:
        return False
    lb, substr, approx = JOINT_LANDMARK_MATCH[jid]
    if approx:
        approx_joints.add(jid)
    global_tf[j["child_bone"]] = geo.Transform(np.eye(3), global_tf[j["parent_bone"]].apply(landmark(lb, substr)))
    return True


def try_resolve_synthetic():
    out = False
    for tid, (mid, lb, substr, approx) in SYNTHETIC_CHAIN.items():
        if tid in global_tf and mid not in global_tf:
            global_tf[mid] = geo.Transform(np.eye(3), global_tf[tid].apply(landmark(lb, substr)))
            approx_joints.add(f"{tid}->{mid} (synthetic, no joints.json entry)")
            out = True
    return out


for root, chain in CHAINS.items():
    place_root(root)
for root in STANDALONE_ROOTS:
    place_root(root)
for _ in range(10):
    progressed = try_resolve_synthetic()
    for chain in CHAINS.values():
        for jid in chain:
            if try_resolve_joint(jid):
                progressed = True
    if not progressed:
        break

RESOLVED = set(global_tf.keys())

# ---------------------------------------------------------------------------
# ILLUSTRATIVE bone shaft radii, mm. NOT measured data -- chosen so relative
# bone thickness reads correctly (femur thicker than fibula, etc.).
# ---------------------------------------------------------------------------
BONE_RADIUS = {
    "humerus": 15, "ulna": 9, "radius": 9, "femur": 20, "tibia": 15, "fibula": 7,
    "clavicle": 8, "scapula": 0, "hip_bone": 0, "patella": 0, "carpals": 0,
    "metacarpals": 5, "phalanges_hand": 4, "tarsals": 0, "metatarsals": 5,
    "phalanges_foot": 4,
}
# Bones modelled as an ELLIPSOID blob (flat/irregular bones) rather than a
# shaft: (rx, ry, rz) mm, centred on the bone's own landmark centroid.
BONE_BLOB = {
    "scapula": (52, 78, 14), "hip_bone": (34, 74, 46), "patella": (20, 20, 9),
    "carpals": (26, 15, 14), "tarsals": (28, 24, 34),
}


def base_name(bone_id):
    return bone_id[:-2] if bone_id.endswith(("_r", "_l")) else bone_id


def bone_landmarks_global(bone_id):
    tf = global_tf[bone_id]
    pts = []
    for lm in BONES[bone_id].get("landmarks", []):
        if "position_local_mm" in lm:
            pts.append((lm, tf.apply(np.array(lm["position_local_mm"], dtype=float))))
    return pts


def r3(v):
    return [round(float(x), 1) for x in v]


# ============================== BONE SOLIDS ==============================
bone_solids = []
bone_points = []

for bid in sorted(RESOLVED):
    bn = base_name(bid)
    lms = bone_landmarks_global(bid)
    if not lms:
        continue
    for lm, p in lms:
        bone_points.append({"bone": bid, "name": lm["name"], "kind": lm.get("kind", ""), "xyz": r3(p)})
    pts = np.array([p for _, p in lms])

    if bn in BONE_BLOB:
        rx, ry, rz = BONE_BLOB[bn]
        c = pts.mean(axis=0)
        bone_solids.append({
            "id": bid, "name": BONES[bid].get("name_common", bid), "shape": "ellipsoid",
            "center": r3(c), "radii": [rx, ry, rz],
        })
    else:
        # shaft: capsule between the two most-separated landmarks
        best = (0.0, None, None)
        for i in range(len(pts)):
            for j in range(i + 1, len(pts)):
                d = float(np.linalg.norm(pts[i] - pts[j]))
                if d > best[0]:
                    best = (d, pts[i], pts[j])
        if best[1] is None or best[0] < 1.0:
            continue
        r = BONE_RADIUS.get(bn, 8)
        bone_solids.append({
            "id": bid, "name": BONES[bid].get("name_common", bid), "shape": "capsule",
            "a": r3(best[1]), "b": r3(best[2]), "ra": r, "rb": r * 0.88,
        })

# skeleton scaffold edges
skeleton_edges = []
for chain in CHAINS.values():
    for jid in chain:
        j = JOINTS[jid]
        if j["child_bone"] in global_tf and j["parent_bone"] in global_tf:
            skeleton_edges.append({
                "joint": jid,
                "from_xyz": r3(global_tf[j["parent_bone"]].t),
                "to_xyz": r3(global_tf[j["child_bone"]].t),
            })

# ============================== MUSCLE SOLIDS ==============================
MUSCLE_FILES = {}
for f in (DATA / "muscles").rglob("*.json"):
    if f.name == "muscle_index.json":
        continue
    payload = json.loads(f.read_text())
    for m in (payload if isinstance(payload, list) else [payload]):
        MUSCLE_FILES[m["id"]] = m

anchor_by_muscle = {}
for a in ANCHORS:
    anchor_by_muscle.setdefault(a["owner_entity"], {})[a["anchor_type"]] = a


def anchor_global(a):
    if a["parent_bone_frame"] not in global_tf:
        return None
    return global_tf[a["parent_bone_frame"]].apply(np.array(a["local_position_mm"], dtype=float))


def muscle_pcsa(m):
    tot = 0.0
    for c in m.get("functional_compartments", []):
        tot += float(c.get("fiber_architecture", {}).get("physiological_cross_section_area_mm2") or 0)
    return tot


muscle_solids = []
for mid, d in anchor_by_muscle.items():
    if "muscle_origin" not in d or "muscle_insertion" not in d:
        continue
    o, i = anchor_global(d["muscle_origin"]), anchor_global(d["muscle_insertion"])
    if o is None or i is None:
        continue
    m = MUSCLE_FILES.get(mid, {})
    pcsa = muscle_pcsa(m)
    # ILLUSTRATIVE belly radius: cube-root-compressed PCSA, clamped. NOT a
    # measured anatomical width -- PCSA is a physiological (force) cross
    # section, used here only as a relative size cue.
    r = 6.0 + 1.55 * (pcsa ** (1.0 / 3.0)) if pcsa > 0 else 8.0
    r = max(5.0, min(30.0, r))
    muscle_solids.append({
        "id": mid, "name": m.get("name_common", mid.replace("_", " ")),
        "region": m.get("region", ""), "shape": "capsule",
        "a": r3(o), "b": r3(i), "ra": round(r, 1), "rb": round(r * 0.55, 1),
        "pcsa": round(pcsa, 1),
        "compartments": len(m.get("functional_compartments", [])),
        "nerve": (m.get("innervation") or {}).get("nerve", ""),
        "roots": (m.get("innervation") or {}).get("root_levels", ""),
        "actions": m.get("actions", [])[:3],
    })

# ============================== LIG / CART / TENDON SOLIDS ==============================
def joint_center(jid):
    j = JOINTS.get(jid)
    if not j or j["child_bone"] not in global_tf:
        return None
    return global_tf[j["child_bone"]].t


def bone_center(bid):
    return global_tf[bid].t if bid in global_tf else None


soft_solids = []


def add_soft(kind, eid, name, region, pos, radii, note=""):
    soft_solids.append({
        "kind": kind, "id": eid, "name": name, "region": region,
        "shape": "ellipsoid", "center": r3(pos), "radii": list(radii),
        "approximate": True, "note": note,
    })


for f in sorted((DATA / "ligaments").glob("*.json")):
    for e in json.loads(f.read_text()):
        pos = joint_center(e.get("joint")) if e.get("joint") else None
        if pos is None:
            pos = bone_center((e.get("attachments") or {}).get("bone_a"))
        if pos is None:
            continue
        add_soft("ligament", e["id"], e.get("name_common", e["id"]), e.get("region", ""), pos,
                 (11, 11, 11), f"{len(e.get('bands', []))} documented band(s)")

for f in sorted((DATA / "cartilage").glob("*.json")):
    for e in json.loads(f.read_text()):
        pos = joint_center(e.get("joint")) if e.get("joint") else None
        if pos is None:
            pos = bone_center(e.get("parent_bone")) or bone_center((e.get("attachments") or {}).get("bone_a"))
        if pos is None:
            continue
        add_soft("cartilage", e["id"], e.get("name_common", e["id"]), e.get("region", ""), pos,
                 (15, 8, 15), f"{len(e.get('parts', []))} documented part(s)")

for f in sorted((DATA / "tendons").glob("*.json")):
    for e in json.loads(f.read_text()):
        dist = (e.get("attachments") or {}).get("distal_attachment", {})
        pos = bone_center(dist.get("ref")) if dist.get("type") == "bone" else None
        if pos is None:
            continue
        add_soft("tendon", e["id"], e.get("name_common", e["id"]), e.get("region", ""), pos,
                 (8, 14, 8), f"{len(e.get('parts', []))} documented part(s)")

scene = {
    "meta": {
        "note": (
            "SCHEMATIC SOLID PREVIEW, not a scan-derived mesh. Two separate accuracy levels are "
            "mixed here on purpose, and it matters which is which. ACCURATE (cited data, see "
            "docs/SOURCES.md): bone lengths, the position of every landmark and muscle attachment "
            "along its bone, which muscle attaches where, PCSA/compartment/innervation figures. "
            "ILLUSTRATIVE (modelling constants chosen for legibility, NOT measurements): every "
            "RADIUS and THICKNESS on screen -- the atlas stores no bone diameters or muscle belly "
            "widths, so bone radii come from a hand-set table and muscle belly radii are a "
            "cube-root-compressed function of PCSA (a physiological force cross-section, not an "
            "anatomical width) used only as a relative size cue. Also illustrative: the overall "
            "pose (identity rotation is assumed between adjacent bone frames -- no per-bone "
            "orientation data exists yet) and the shoulder/pelvis root placements. Ligament, "
            "cartilage and tendon blobs mark their governing joint or bone REGION only, never a "
            "real attachment footprint. Only the limb chains are drawn: the trunk, spine and skull "
            "have no numeric coordinates in the atlas yet (~34.5% of all attachment endpoints are "
            "numerically resolved -- see docs/VERIFICATION.md). Real surface geometry is "
            "docs/ROADMAP.md Stage 5."
        ),
        "approximated_joints": sorted(approx_joints),
        "resolved_bone_count": len(RESOLVED),
    },
    "bone_solids": bone_solids,
    "bone_points": bone_points,
    "skeleton_edges": skeleton_edges,
    "muscle_solids": muscle_solids,
    "soft_solids": soft_solids,
}

out = DATA / "rig" / "scene_3d_preview.json"
out.write_text(json.dumps(scene, indent=1))
print(f"bones: {len(bone_solids)} solids ({len(bone_points)} landmarks)")
print(f"muscles: {len(muscle_solids)} solids")
print(f"soft tissue: {len(soft_solids)} "
      f"(lig {sum(1 for s in soft_solids if s['kind']=='ligament')}, "
      f"cart {sum(1 for s in soft_solids if s['kind']=='cartilage')}, "
      f"tend {sum(1 for s in soft_solids if s['kind']=='tendon')})")
print(f"wrote {out} ({out.stat().st_size/1024:.0f} KB)")
