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

How far is "legitimately" is itself a measurement, not a judgement. Splitting
that distance along the belly's own long axis -- past the end versus off to
the side -- assumes the tendon carries on in the direction the belly points.
For anything crossing a retinaculum that is simply false: flexor hallucis
longus turns a right angle behind the medial malleolus, and scored 155 mm
"off to the side" of a muscle it is attached to correctly. So the straight
line from muscle to attachment is tested against the bones, because a tendon
cannot pass through bone. Where it is blocked, the anchor is reported as
needing a path rather than as misplaced -- which moved 35 of the 45 flagged
attachments out of the error list and into a specific, actionable one.

None of this is pass/fail. These coordinates were authored as approximations
with no geometry to check against; the point is to find out how good they are
and which ones are wrong.

    python3 scripts/audit_landmarks_vs_geometry.py --subject vhm_both
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from engine import vh_ingest as vh  # noqa: E402
from engine import volume_ingest  # noqa: E402
from engine.vh_ingest import fit_sphere  # noqa: E402
from engine.geometry import bone_length_along_axis, local_to_world  # noqa: E402
# Q132: the vertebra-level parser generate_anchors.py already has and tests
# (Q130) -- reused here, not reimplemented, so a landmark naming "C1" or
# "T11" is recognised identically by the audit's identity check and by the
# anchor generator that placed it.
from generate_anchors import _vertebra_levels  # noqa: E402

BUILD_DIR = REPO_ROOT / "build" / "vh"
DATA_DIR = REPO_ROOT / "data"

# Q131: reverse TotalSegmentator label id -> name, used to identify individual
# thoracic/lumbar vertebrae exactly where a manifest record's own source_file
# encodes the raw label id (see _vertebra_pieces_exact below).
_TOTALSEG_ID_TO_NAME = {int(k): v for k, v in json.loads(
    (REPO_ROOT / "mappings" / "totalsegmentator_labels.json").read_text())["labels"].items()}


def load_geometry(subject: str):
    out = BUILD_DIR / subject
    manifest = json.loads((out / "manifest.json").read_text())
    verts = np.fromfile(out / "vertices.f32", dtype="<f4").reshape(-1, 3).astype(np.float64)
    tris = np.fromfile(out / "faces.u32", dtype="<u4").reshape(-1, 3).astype(np.int64)
    blocks, by_atlas_id, faces_by_atlas_id = {}, {}, {}
    base_of: dict = {}
    for rec in manifest["structures"]:
        v0, vn = rec["vertex_offset"], rec["vertex_count"]
        f0, fn = rec["face_offset"], rec["triangle_count"]
        atlas_id = rec["atlas_id"]
        chunk = verts[v0:v0 + vn]
        # Faces index the global vertex array. Rebase them onto the entity's
        # own concatenated vertices, so connectivity survives without dragging
        # 1.5 million vertices through every component search -- and so an
        # entity assembled from several meshes (seven tarsals, two
        # gastrocnemius heads) keeps each mesh's faces pointing at its own.
        faces_by_atlas_id.setdefault(atlas_id, []).append(
            tris[f0:f0 + fn] - v0 + base_of.get(atlas_id, 0))
        base_of[atlas_id] = base_of.get(atlas_id, 0) + vn
        # One source file can now produce SEVERAL structures: the forefoot
        # mesh is split into metatarsals and phalanges. Keying blocks by
        # filename and keeping the first, as this did, silently gave both
        # entities the same partial mesh.
        # Q143: a manifest with no per-structure `source_file` (the Z-Anatomy
        # reference model's own ingestion carries `source_structure` instead) keys
        # blocks by that or, failing that, the atlas id itself -- this function's
        # own anchor-resolution caller already treats a bone with no measurable
        # frame as "skip it, text description only", so a degenerate key here
        # costs nothing, it just never matches an anchor's `parent_bone_frame`.
        blocks.setdefault(rec.get("source_file") or rec.get("source_structure") or atlas_id, []).append(chunk)
        by_atlas_id.setdefault(atlas_id, []).append(chunk)
    return (manifest,
            {k: np.vstack(v) for k, v in blocks.items()},
            {k: np.vstack(v) for k, v in by_atlas_id.items()},
            {k: np.concatenate(v) for k, v in faces_by_atlas_id.items()})


def find(blocks, *needles):
    """The one mesh whose filename contains every needle."""
    hits = [v for k, v in blocks.items()
            if all(n.lower() in k.lower().replace("_", "") for n in needles)]
    return hits[0] if len(hits) == 1 else None


def _mesh_components_by_height(verts: np.ndarray, faces: np.ndarray,
                               min_size: int = 500) -> list:
    """Splits ONE atlas entity's mesh into its disconnected mesh-connectivity
    pieces (Q130) -- the same technique `scripts/verify_rib_continuity.py`
    and `scripts/audit_full_continuity_q112.py` use for a different purpose
    (measuring fragmentation), reused here to instead PICK OUT a piece: a
    region entity like `cervical_vertebrae` holds several real, physically
    separate bones (C1-C7) sharing no vertex, so its pieces ARE the
    individual vertebrae. Returns each component's own vertex array (not
    face indices), largest-by-height first, dropping fragments under
    `min_size` vertices (decimation noise, not a real vertebra/rib).

    This does NOT work for every region entity: `ribs_r`/`ribs_l` come back
    as ONE component (all 12 ribs), because Q109's continuity fix
    deliberately voxel-dilated and re-meshed them into a single connected
    blob to close the real anatomical gaps between adjacent ribs -- the
    same property that makes their main_frac ~1.0 also destroys the
    per-rib separation this function depends on. Confirmed empirically
    (2 components, one of size ~50-18 vertices of decimation noise) before
    ribs were ruled out as a Q130 target this way.
    """
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    n = len(verts)
    i = np.concatenate([faces[:, 0], faces[:, 1], faces[:, 2]])
    j = np.concatenate([faces[:, 1], faces[:, 2], faces[:, 0]])
    graph = coo_matrix((np.ones(len(i)), (i, j)), shape=(n, n))
    ncomp, labels = connected_components(graph, directed=False)
    sizes = np.bincount(labels, minlength=ncomp)
    pieces = [verts[labels == c] for c in range(ncomp) if sizes[c] >= min_size]
    pieces.sort(key=lambda p: -p[:, 1].mean())
    return pieces


def _vertebra_pieces_exact(manifest, by_atlas_id: dict, atlas_id: str,
                           prefix: str, expected: list) -> dict | None:
    """Q131: identify each individual vertebra EXACTLY, when the manifest's
    own records make it possible, instead of inferring it from mesh shape.

    `ct_vhf`'s manifest keeps one structure record per raw TotalSegmentator
    vertebra label -- `source_file` literally ends '#31' for `vertebrae_L1`
    (id 31) -- because that build ingested straight from `vhf_total.nii.gz`
    per label. `load_geometry` concatenates same-atlas_id records in the
    manifest's own order to build `by_atlas_id`, so re-walking the manifest
    and slicing off each record's own `vertex_count` in that same order
    recovers exactly which chunk is which vertebra, with no shape inference
    at all. `ct_vhm` ('recovered from the published male viewer') carries no
    such id in its source_file, so this returns None there and the caller
    falls back to `_mesh_components_by_height` (Q130's method).
    """
    if manifest is None:
        return None
    concatenated = by_atlas_id.get(atlas_id)
    if concatenated is None:
        return None
    recs = [r for r in manifest["structures"] if r["atlas_id"] == atlas_id]
    offset = 0
    pieces = {}
    for r in recs:
        n = r["vertex_count"]
        chunk = concatenated[offset:offset + n]
        offset += n
        m = re.search(r"#(\d+)$", r["source_file"])
        if not m:
            return None
        name = _TOTALSEG_ID_TO_NAME.get(int(m.group(1)))
        if not name or not name.startswith(f"vertebrae_{prefix}"):
            return None
        pieces[name.replace("vertebrae_", "")] = chunk
    return pieces if set(pieces) == set(expected) else None


def _vertebra_pieces_by_height(by_atlas_id: dict, faces_by_atlas_id: dict,
                               atlas_id: str, expected: list) -> dict | None:
    """Fallback for a subject whose manifest does not carry a raw label id
    (`ct_vhm`): Q130's mesh-connectivity + height-ordering, with a relative
    size filter added -- `ct_vhf` (not `ct_vhm`) turned out to carry
    decimation-noise fragments up to ~1500 vertices, well past Q130's flat
    500-vertex floor, so a fragment far smaller than the real per-vertebra
    pieces (which are themselves all similar size) is dropped by comparison
    to the largest piece found rather than by a fixed count."""
    verts = by_atlas_id.get(atlas_id)
    faces = faces_by_atlas_id.get(atlas_id)
    if verts is None or faces is None or len(verts) < 500:
        return None
    comps = _mesh_components_by_height(verts, faces, min_size=500)
    if comps:
        floor = 0.25 * max(len(c) for c in comps)
        comps = [c for c in comps if len(c) >= floor]
    if len(comps) != len(expected):
        return None
    return {lvl: comps[i] for i, lvl in enumerate(expected)}


def _identify_vertebrae(manifest, by_atlas_id, faces_by_atlas_id, atlas_id, prefix, expected):
    pieces = _vertebra_pieces_exact(manifest, by_atlas_id, atlas_id, prefix, expected)
    if pieces is not None:
        return pieces, "exact per-record TotalSegmentator label id"
    pieces = _vertebra_pieces_by_height(by_atlas_id, faces_by_atlas_id, atlas_id, expected)
    if pieces is not None:
        return pieces, "mesh-connectivity components sorted by height (Q130 method)"
    return None, None


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


def metatarsal_rays(by_atlas_id, faces_by_atlas_id, side: str):
    """The five metatarsals of one foot, ordered medial to lateral.

    Available only because the forefoot mesh is split during ingest; before
    that, the five bones were inside one surface with the toes.
    """
    verts = by_atlas_id.get(f"metatarsals_{side}")
    faces = faces_by_atlas_id.get(f"metatarsals_{side}")
    if verts is None or faces is None:
        return []
    clouds = [verts[np.unique(faces[c])] for c in vh.mesh_components(faces)]
    if len(clouds) != 5:
        return []
    # +X is the subject's right, so on the right foot medial is the low-X end
    # and on the left foot the high-X end.
    clouds.sort(key=lambda c: c[:, 0].mean() * (1.0 if side == "r" else -1.0))
    return clouds


def ray_ends(ray: np.ndarray, proximal_ref: np.ndarray):
    """The proximal and distal end centroids of one long bone."""
    centre = ray.mean(axis=0)
    axis = np.linalg.svd(ray - centre, full_matrices=False)[2][0]
    if float((centre - proximal_ref) @ axis) < 0:
        axis = -axis
    t = (ray - centre) @ axis
    return (ray[t < np.quantile(t, 0.1)].mean(axis=0),
            ray[t > np.quantile(t, 0.9)].mean(axis=0))


# The seven tarsal bones, as they're named when a subject's CT segmentation
# couldn't be joined into one `tarsals_{side}` blob and instead carries each
# bone as its own atlas id (Q136). build_frames() unions these as a fallback
# reference point for the metatarsal rays when the combined blob is absent.
_TARSAL_BONE_IDS = ("calcaneus", "talus", "cuboid", "navicular",
                     "cuneiform_medial", "cuneiform_intermediate", "cuneiform_lateral")

# Which individual bone each name inside a group entity refers to. The key is
# the member's own mesh; the values are the words a landmark would use for it.
# 'sustentaculum tali' is the giveaway case: the name says talus but the shelf
# is part of the CALCANEUS, so a word-overlap rule would test the wrong bone.
_MEMBER_WORDS = {
    "talus": ("talus", "talar", "trochlea", "subtalar"),
    "calcaneous": ("calcaneus", "calcaneal", "achilles", "sustentaculum"),
    "navicular": ("navicular",),
    "cuboid": ("cuboid",),
    "medialcuneiform": ("medial cuneiform",),
    "intermediatecuneiform": ("intermediate cuneiform",),
    "lateralcuneiform": ("lateral cuneiform",),
}
# Ordinals only. A muscle's name is not a claim about where it attaches:
# 'hallucis' says a muscle acts on the great toe, and reading it as 'first
# metatarsal' flagged adductor hallucis, which genuinely arises from the
# bases of the second to fourth. The same for 'digiti minimi' and the fifth,
# where abductor digiti minimi arises from the calcaneus. Only a name that
# states a ray is testable against that ray.
_RAY_WORDS = {
    "MT1": ("1st metatarsal", "first metatarsal"),
    "MT2": ("2nd metatarsal", "second metatarsal"),
    "MT3": ("3rd metatarsal", "third metatarsal"),
    "MT4": ("4th metatarsal", "fourth metatarsal"),
    "MT5": ("5th metatarsal", "fifth metatarsal"),
}

# A vertebra-group's members are keyed by level ("C1", "T11", ...), which is
# how expected_member (below) tells this kind of group apart from the tarsal/
# ray ones and switches to _vertebra_levels() instead of a word table.
_VERTEBRA_KEY_RE = re.compile(r"^[CTLS]\d{1,2}$")

# The three region entities that are ONE atlas/mesh id for several real,
# separate vertebrae (Q130/Q131): (atlas_id, level prefix, every level it
# should contain, craniocaudally). build_frames() below uses the identical
# (atlas_id, prefix, expected) tuples for thoracic/lumbar to find each
# entity's own origin via the same _identify_vertebrae(); cervical's frame
# is found by separate, older code that only needs its top two levels.
_VERTEBRA_GROUPS = (
    ("cervical_vertebrae", "C", [f"C{i}" for i in range(1, 8)]),
    ("thoracic_vertebrae", "T", [f"T{i}" for i in range(1, 13)]),
    ("lumbar_vertebrae", "L", [f"L{i}" for i in range(1, 6)]),
)


def named_members(blocks, by_atlas_id, faces_by_atlas_id, manifest=None):
    """Bone groups whose individual members can be told apart geometrically.

    The tarsals arrive as seven separate meshes and the metatarsals fall out
    as five connected components once the forefoot block is split, so for
    these two entities a landmark that names one bone can be tested against
    that bone rather than against the group.

    Q132 generalises the same idea to the three vertebral-column entities
    (cervical/thoracic/lumbar_vertebrae) using Q130/Q131's own already-
    verified per-vertebra identification (`_identify_vertebrae`: an exact
    per-record TotalSegmentator label id where the manifest carries one,
    mesh-connectivity components sorted by height otherwise) instead of
    re-deriving it -- this was ad hoc, one-off code in build_frames() before
    today; now any future landmark or anchor naming a single vertebra level
    is checked the same way automatically, on whichever subject is loaded.

    ribs_l/ribs_r are NOT included, checked here rather than assumed: Q109's
    continuity fix voxel-dilated and re-meshed all 12 ribs per side into one
    connected blob (confirmed again for this item -- both subjects, both
    sides come back as exactly 1 mesh-connectivity component of 48k-67k
    vertices, nothing near the 12-piece count), and the manifest lost the
    per-rib boundary at the same step (even ct_vhf, whose per-vertebra
    manifest records give vertebrae their exact identity for free, holds
    only ONE combined structures record per rib side). Both of Q130/Q131's
    reused methods fail for the same reason, so rather than invent a third,
    untested method (e.g. nearest-voxel lookup into the raw
    vhm_total.nii.gz/vhf_total.nii.gz label volumes, which still carry the
    12 individual per-rib labels), this item reports ribs honestly as
    unnameable at the mesh level post-fusion and scopes the identity check
    down to vertebrae.
    """
    out = {}
    for side, tag in (("r", "right"), ("l", "left")):
        members = {}
        for stem in _MEMBER_WORDS:
            mesh = find(blocks, tag, "bone" + stem)
            if mesh is not None:
                members[stem] = mesh
        if len(members) == len(_MEMBER_WORDS):
            out[f"tarsals_{side}"] = members
        rays = metatarsal_rays(by_atlas_id, faces_by_atlas_id, side)
        if rays:
            out[f"metatarsals_{side}"] = {f"MT{i+1}": r for i, r in enumerate(rays)}
    for atlas_id, prefix, expected in _VERTEBRA_GROUPS:
        pieces, _how = _identify_vertebrae(manifest, by_atlas_id, faces_by_atlas_id,
                                           atlas_id, prefix, expected)
        if pieces:
            out[atlas_id] = pieces
    return out


def expected_member(name: str, members: dict):
    """Which member of the group this landmark's own name claims, if one.

    Returns None when the name claims none or more than one, because a
    landmark named 'cuneiforms' or 'metatarsal heads' is deliberately about
    the whole group and testing it against a single bone would invent a
    failure.
    """
    sample = next(iter(members))
    if _VERTEBRA_KEY_RE.match(sample):
        # Reuse generate_anchors.py's own vertebra-level parser (Q130) so a
        # landmark saying "C1" or "of T11" is read the same way here as it
        # is when an anchor is matched to it.
        hits = {lvl.upper() for lvl in _vertebra_levels(name)} & set(members)
        return hits.pop() if len(hits) == 1 else None
    words = _RAY_WORDS if sample.startswith("MT") else _MEMBER_WORDS
    low = name.lower()
    hits = {m for m, terms in words.items()
            if m in members and any(t in low for t in terms)}
    return hits.pop() if len(hits) == 1 else None


# How deep inside a bone a path may run before it counts as going THROUGH it.
# Not zero, because a tendon lying in its groove is supposed to touch bone --
# that is what a pulley is -- and a landmark measured on a surface sits a
# millimetre or two either side of it. A path through the body of the talus
# runs 15 mm deep or more, so the two are not close.
MAX_TENDON_DEPTH_MM = 5.0


def path_through_bone(points: np.ndarray, meshes: dict, faces: dict):
    """Which bone, if any, a polyline runs deep inside.

    Returns (bone id, depth in mm), or (None, 0.0) when the path only grazes
    surfaces.

    Depth is measured to the nearest VERTEX, not to the nearest point of the
    nearest triangle, so on a coarsely tessellated mesh it reads deeper than
    it is: a point 1 mm under a surface whose vertices are 12 mm apart scores
    6 mm. The meshes here carry roughly millimetre edges, where the two agree
    closely enough for a 5 mm threshold; anything much coarser would need a
    real point-to-triangle distance.
    """
    lo, hi = points.min(axis=0) - 1.0, points.max(axis=0) + 1.0
    worst, worst_bone = 0.0, None
    for bone_id, verts in meshes.items():
        f = faces.get(bone_id)
        if f is None or not is_bone(bone_id):
            continue
        if np.any(verts.min(axis=0) > hi) or np.any(verts.max(axis=0) < lo):
            continue          # bounding boxes do not even overlap
        inside = vh.points_inside_mesh(points, verts, f)
        if not inside.any():
            continue
        depth = float(nearest_distance(points[inside], verts).max())
        if depth > worst:
            worst, worst_bone = depth, bone_id
    return (worst_bone, worst) if worst > MAX_TENDON_DEPTH_MM else (None, 0.0)


def load_via_points():
    """Each muscle's declared wrap path, as {muscle_id: [via point, ...]}."""
    out = {}
    for path in sorted((DATA_DIR / "muscles").rglob("*.json")):
        payload = json.loads(path.read_text())
        for m in (payload if isinstance(payload, list) else [payload]):
            pts = (m.get("attachments") or {}).get("via_points") or []
            if pts:
                out[m["id"]] = pts
    return out


def via_path(owner, anchor, via_points, frames, bones=None):
    """The declared path in world coordinates, or None if there is not one.

    Only insertions get a path here: via_points are stored proximal-to-distal,
    so they describe the route from the belly out to the insertion.
    """
    pts = via_points.get(owner)
    if not pts or anchor.get("anchor_type") != "muscle_insertion":
        return None
    out = []
    for vp in pts:
        frame = frames.get(vp.get("bone_frame"))
        if frame is None:
            return None
        out.append(place(vp["position_local_mm"], frame,
                         (bones or {}).get(vp.get("bone_frame"))))
    return out


def blocked_by_bone(cloud: np.ndarray, target: np.ndarray, meshes: dict,
                    faces: dict, samples: int = 60):
    """Which bone, if any, the straight line from a muscle to `target` enters.

    The muscle end used is its own point nearest the target, so this asks the
    most generous version of the question: even taking the shortest route the
    belly offers, does the tendon still have to go through bone?

    Returns the bone's entity id, or None when the straight path is clear.
    """
    if cloud is None:
        return None
    start = cloud[np.argmin(np.linalg.norm(cloud - target, axis=1))]
    return path_through_bone(np.linspace(start, target, samples), meshes, faces)[0]


# Only bone blocks a tendon. Tendons run through and between muscle bellies
# constantly, and the cartilage meshes are joint surfaces sitting on top of
# the bones they belong to, so counting either would report every tendon in
# the body as obstructed.
_BONE_STEMS = ("femur", "tibia", "fibula", "patella", "hip_bone", "sacrum",
               "coccyx", "tarsals", "metatarsals", "phalanges_foot")


def is_bone(entity_id: str) -> bool:
    return entity_id.startswith(_BONE_STEMS)


def nearest_distance(points: np.ndarray, cloud: np.ndarray, chunk: int = 256):
    """Distance from each point to the nearest vertex of the mesh."""
    out = np.empty(len(points))
    for i in range(0, len(points), chunk):
        block = points[i:i + chunk]
        d = np.linalg.norm(cloud[None, :, :] - block[:, None, :], axis=2)
        out[i:i + chunk] = d.min(axis=1)
    return out


def _with_colocated_bones(by_atlas_id: dict, manifest: dict | None) -> dict:
    """`by_atlas_id`, filled out with bones from OTHER already-converted
    subjects that are PROVABLY in this subject's own coordinate space --
    not merely the same body. Registering two independently-segmented
    scans of the same person is real image-registration work this script
    does not attempt; this only recognises when that work was never
    needed in the first place.

    `scripts/transfer/bundle_to_subjects.py` partitions ONE decimated
    viewer bundle into per-subject folders purely by an entity's own
    recorded `subject` tag, copying every vertex unchanged -- no
    transform, no re-origin, nothing fitted. So any two subjects whose
    manifests carry the IDENTICAL `source_kind` string naming that
    recovery ("recovered from the published ... viewer (Version N)")
    came out of that one split and share their world frame down to the
    bit. That is the male's actual situation: `ct_vhm` holds his scapulae,
    `ct_vhm_arm` his humeri, both cut from the one 'recovered from the
    published male viewer (Version 25)' bundle -- confirmed empirically,
    not just by label, before this was written: their Y-extents overlap
    exactly where the glenohumeral joint should sit (scapula 444-608 mm,
    humerus 250-590 mm).

    A `source_kind` of anything else ('labelled volume (NIfTI)', etc.) is
    NOT treated as colocation: that text recurs across genuinely
    different, independently-segmented scans (the female's CT, the
    male's own separately-ingested neck/foot volumes) with no shared
    frame at all, so this only ever fires for subjects tagged with a
    specific bundle-recovery provenance, never a generic ingest kind.
    """
    kind = (manifest or {}).get("source_kind", "")
    this_subject = (manifest or {}).get("subject")
    if not kind.startswith("recovered from the published") or this_subject is None:
        return by_atlas_id
    merged = None
    for d in sorted(BUILD_DIR.iterdir()):
        if not d.is_dir() or d.name == this_subject:
            continue
        mpath = d / "manifest.json"
        if not mpath.exists():
            continue
        try:
            other = json.loads(mpath.read_text())
        except Exception:
            continue
        if other.get("source_kind") != kind:
            continue
        missing = {r["atlas_id"] for r in other["structures"]} - by_atlas_id.keys()
        if not missing:
            continue
        _, _, sib_by_atlas_id, _ = load_geometry(d.name)
        for aid in missing:
            if aid in sib_by_atlas_id:
                merged = merged if merged is not None else dict(by_atlas_id)
                merged[aid] = sib_by_atlas_id[aid]
    return merged if merged is not None else by_atlas_id


def build_frames(by_atlas_id, blocks, faces_by_atlas_id, manifest=None):
    """Every bone frame this script can MEASURE, as
    {entity_id: (origin, basis, how it was found, which axes are fitted,
                 length along the long axis in mm, or None)}.

    The length is the 1st-99th percentile extent of the bone's own vertices
    along the frame's Y, measured only where that axis is fitted. It is what
    `reference_length_mm` in bones.json was measured with on the male, and
    what `engine.geometry.local_to_world` divides it by to put a landmark on
    a subject of another size (Q43).

    Separate from main() because the wrap paths need the same frames: a
    via point is stored in a bone's local coordinates, and putting it in
    the world needs exactly this.
    """
    by_atlas_id = _with_colocated_bones(by_atlas_id, manifest)
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
        elif f"tibia_{side}" not in frames:
            # Q138: this release ("recovered from the published male viewer")
            # does not carry separate tibialateral/tibialmedial/tibiadistal
            # sub-meshes at all -- it ships ONE fused 'knee_articular_
            # cartilage_{side}' mesh instead, which is exactly the gap
            # scripts/generate_tendon_connectors.py's own docstring already
            # documents (Q118) as the reason build_frames() could not
            # construct a tibia frame. The femoral-condyle cap and the two
            # tibial-plateau pads are real, physically separate anatomy with
            # no shared mesh vertex between them (confirmed here by mesh
            # connectivity, the same technique Q130 used to pull individual
            # vertebrae out of a fused CT label) -- they were only ever fused
            # under one filename, not one mesh. Which piece is which is not
            # assumed from position: each candidate tibial piece is checked
            # against the REAL tibia bone mesh by nearest-surface distance
            # before it is used, exactly the house standard applied to every
            # other landmark in this file.
            knee_verts = by_atlas_id.get(f"knee_articular_cartilage_{side}")
            knee_faces = faces_by_atlas_id.get(f"knee_articular_cartilage_{side}")
            tibia_mesh = by_atlas_id.get(f"tibia_{side}")
            femur_mesh = by_atlas_id.get(f"femur_{side}")
            if (knee_verts is not None and knee_faces is not None
                    and tibia_mesh is not None and len(knee_verts) >= 150):
                from scipy.spatial import cKDTree
                comps = _mesh_components_by_height(knee_verts, knee_faces, min_size=50)
                tib_pieces = []
                tibia_tree = cKDTree(tibia_mesh)
                femur_tree = cKDTree(femur_mesh) if femur_mesh is not None else None
                for c in comps:
                    d_tib, _ = tibia_tree.query(c)
                    if femur_tree is not None:
                        d_fem, _ = femur_tree.query(c)
                        if d_fem.mean() < d_tib.mean():
                            continue  # closer to the femur: the condylar cap, not tibial
                    tib_pieces.append((c, d_tib.mean()))
                # Real acceptance check, not an assumption: exactly two
                # pieces, and both genuinely touching the tibia surface
                # (a joint-cartilage gap of a few mm, never tens of mm).
                if len(tib_pieces) == 2 and max(d for _, d in tib_pieces) <= 5.0:
                    (piece_a, _), (piece_b, _) = tib_pieces
                    sign = 1.0 if side == "r" else -1.0
                    # Lateral = farther from the midline, mirrored per side
                    # exactly like every other left/right convention in this
                    # file (e.g. the clavicle's medial/lateral split above).
                    if piece_a[:, 0].mean() * sign >= piece_b[:, 0].mean() * sign:
                        lat, med = piece_a, piece_b
                    else:
                        lat, med = piece_b, piece_a
                    centre = np.vstack([lat, med]).mean(axis=0)
                    trans = lat.mean(axis=0) - med.mean(axis=0)
                    # No distal tibial plafond cartilage in this release
                    # either, so the long axis target falls back to the
                    # bone's own distal 2% by height, the same convention
                    # already used for the radius/ulna/fibula above.
                    distal = tibia_mesh[tibia_mesh[:, 1] <= np.quantile(tibia_mesh[:, 1], 0.02)]
                    frames[f"tibia_{side}"] = (centre, orthonormal_frame(
                        centre, distal.mean(axis=0), trans),
                        "centroid of the two tibial-plateau cartilage pieces, "
                        "split by mesh connectivity out of this release's single "
                        "fused 'knee_articular_cartilage' mesh and confirmed "
                        "tibial (not femoral) by real nearest-surface distance "
                        f"(<={max(d for _, d in tib_pieces):.1f} mm to the tibia "
                        "mesh, both pieces); transverse axis from lateral-minus-"
                        "medial plateau; long axis toward the distal 2% of the "
                        "tibia's OWN mesh (no distal tibial plafond cartilage in "
                        "this release to point it at, unlike the femur/tibial-"
                        "plateau branch above)", "both")

    # Hip: acetabular sphere centre, with the transverse axis taken from the
    # line between the two acetabula -- so it needs both sides present.
    acetabula = {}
    for side, tag in (("r", "right"), ("l", "left")):
        cup = find(blocks, tag, "cartilage", "pelvisacetabulum")
        if cup is not None:
            acetabula[side] = fit_sphere(cup)
    # A CT ships no cartilage. TotalSegmentator labels bone and nothing else,
    # so every frame above -- each of which keys on a cartilage mesh the
    # Denver release happens to carry -- finds nothing, and the audit reports
    # "no bone had both a measurable frame and geometry" on a scan that is
    # perfectly good. The femoral head is still there, in the femur label;
    # it just has to be isolated from the bone by direction instead of read
    # off a separate mesh. That is exactly what the volume ingest already
    # does to recover the atlas origin, so the same routine serves here.
    for side, tag in (("r", "right"), ("l", "left")):
        if f"femur_{side}" in frames:
            continue
        femur = by_atlas_id.get(f"femur_{side}")
        if femur is None or len(femur) < 64:
            continue
        try:
            centre, radius, rms = volume_ingest.femoral_head_centre(
                femur, "right" if side == "r" else "left")
        except Exception:
            continue
        lo, hi = volume_ingest.HEAD_RADIUS_MM["femur"]
        if not (lo <= radius <= hi and rms <= 3.0):
            print(f"  femur_{side}: head fit rejected (r={radius:.1f} mm, "
                  f"rms={rms:.2f} mm), so no frame for it")
            continue
        distal = femur[femur[:, 1] < np.percentile(femur[:, 1], 4)].mean(axis=0)
        frames[f"femur_{side}"] = (
            centre, orthonormal_frame(centre, distal, None),
            f"femoral head isolated from the bone by direction and sphere-"
            f"fitted, r={radius:.1f} mm, rms={rms:.2f} mm; long axis to the "
            f"distal 4% of the shaft; NO cartilage in this scan, so the "
            f"transverse axis is convention, not fitted", "long")
        # The hip frame's own origin_landmark is the acetabular joint centre,
        # and the femoral head centre IS that centre to within the joint
        # space. With no acetabular cartilage to fit, this is the honest
        # substitute -- and it is named as such rather than passed off as a
        # fit of the socket.
        acetabula.setdefault(side, (centre, radius, rms))

    if {"r", "l"} <= set(acetabula):
        across = acetabula["r"][0] - acetabula["l"][0]
        for side in ("r", "l"):
            if f"hip_bone_{side}" in frames:
                continue
            centre, radius, rms = acetabula[side]
            up = np.array([0.0, 1.0, 0.0])
            cup = find(blocks, "right" if side == "r" else "left",
                       "cartilage", "pelvisacetabulum")
            how = ("acetabular sphere fit" if cup is not None
                   else "FEMORAL HEAD centre standing in for the acetabular "
                        "centre, there being no acetabular cartilage in this scan")
            frames[f"hip_bone_{side}"] = (centre, orthonormal_frame(
                centre, centre - up * 100.0, across),
                f"{how}, r={radius:.1f} mm, rms={rms:.2f} mm; "
                f"transverse axis from the interacetabular line; superior axis "
                f"by anatomical-position convention, not fitted", "transverse")

    # ---- the foot, the fibula and the patella --------------------------
    #
    # These carry 54 anchors between them and until now not one was checked,
    # because a frame was only ever fitted for the femur, tibia and pelvis.
    # Every one of these frames is anchored on a MEASURED origin; where an
    # axis is the anatomical-position convention rather than a fit, it is
    # tagged ASSUMED and the report says so.
    for side, tag in (("r", "right"), ("l", "left")):
        fibula = by_atlas_id.get(f"fibula_{side}")
        if fibula is not None:
            # The fibular head is the superior end: the bone runs almost
            # vertically, so the extremes along world Y are head and malleolus.
            head = fibula[fibula[:, 1] > np.quantile(fibula[:, 1], 0.98)].mean(axis=0)
            tip = fibula[fibula[:, 1] < np.quantile(fibula[:, 1], 0.02)].mean(axis=0)
            frames[f"fibula_{side}"] = (
                head, orthonormal_frame(head, tip),
                "the fibular head, as the superior 2% of the shaft; long axis "
                "to the lateral malleolus", "long")

        patella = by_atlas_id.get(f"patella_{side}")
        if patella is not None:
            frames[f"patella_{side}"] = (
                patella.mean(axis=0), np.eye(3),
                "the patellar centroid; axes by anatomical-position convention, "
                "not fitted", "neither")

        # The tarsal frame's origin is the talar trochlea, which is exactly
        # what the talar articular cartilage mesh is.
        dome = find(blocks, tag, "cartilage", "talus")
        if dome is not None:
            frames[f"tarsals_{side}"] = (
                dome.mean(axis=0), np.eye(3),
                "the talar trochlea, measured as the centroid of the talar "
                "articular cartilage; axes by anatomical-position convention, "
                "not fitted", "neither")
        elif f"tarsals_{side}" not in frames:
            # Q138: same fused-cartilage gap as the tibia's knee frame above
            # -- this release ships one 'ankle_articular_cartilage_{side}'
            # mesh instead of a separate talar-dome sub-mesh. Split by mesh
            # connectivity (real: the talar dome and tibial plafond share no
            # vertex) and identified by which real bone mesh each piece sits
            # nearer to (talus vs tibia), the same verification standard as
            # the knee split above.
            ankle_verts = by_atlas_id.get(f"ankle_articular_cartilage_{side}")
            ankle_faces = faces_by_atlas_id.get(f"ankle_articular_cartilage_{side}")
            # This release keeps the seven tarsals as separate atlas ids
            # (no combined 'tarsals_{side}' blob -- see the Q136 note by the
            # metatarsal code below), so the talus is looked up directly.
            tarsal_mesh = by_atlas_id.get(f"tarsals_{side}")
            if tarsal_mesh is None:
                tarsal_mesh = by_atlas_id.get(f"talus_{side}")
            tibia_mesh = by_atlas_id.get(f"tibia_{side}")
            if (ankle_verts is not None and ankle_faces is not None
                    and tarsal_mesh is not None and tibia_mesh is not None
                    and len(ankle_verts) >= 100):
                comps = _mesh_components_by_height(ankle_verts, ankle_faces, min_size=30)
                if len(comps) == 2:
                    from scipy.spatial import cKDTree
                    tarsal_tree = cKDTree(tarsal_mesh)
                    tibia_tree = cKDTree(tibia_mesh)
                    scored = []
                    for c in comps:
                        d_tar, _ = tarsal_tree.query(c)
                        d_tib, _ = tibia_tree.query(c)
                        scored.append((c, d_tar.mean(), d_tib.mean()))
                    talar = min(scored, key=lambda t: t[1])
                    if talar[1] <= 5.0 and talar[1] < talar[2]:
                        frames[f"tarsals_{side}"] = (
                            talar[0].mean(axis=0), np.eye(3),
                            "the talar trochlea, measured as the centroid of "
                            "the talar-dome piece split by mesh connectivity "
                            "out of this release's single fused "
                            "'ankle_articular_cartilage' mesh, confirmed "
                            f"talar (not tibial) by real nearest-surface "
                            f"distance ({talar[1]:.1f} mm to the tarsal mesh "
                            f"vs {talar[2]:.1f} mm to the tibia mesh); axes by "
                            "anatomical-position convention, not fitted", "neither")

        # The metatarsal frame sits on the bases and runs out to the heads.
        # Both ends are measured, so its long axis is fitted -- and since the
        # foot is plantarflexed in this cadaver, that axis is nothing like
        # world Y, so assuming otherwise would have been badly wrong.
        #
        # The axis has to come from the RAYS, not from the group. The five
        # metatarsals form a fan about 80 mm across and each bone is only
        # 70 mm long, so the group's own principal axis is the diagonal of
        # the fan: fitting it that way put the "metatarsal bases" origin at
        # world x=201, which is the fifth metatarsal, not the middle of
        # anything. Each ray's principal axis is unambiguous, and their mean
        # is the direction the forefoot actually points.
        rays = metatarsal_rays(by_atlas_id, faces_by_atlas_id, side)
        tarsal_cloud = by_atlas_id.get(f"tarsals_{side}")
        if tarsal_cloud is None:
            # No combined blob (Q136): some subjects instead carry the seven
            # tarsals as separate atlas ids. Their union, same subject and
            # same coordinate space, is the identical reference point --
            # purely a fallback, so a subject that already has the combined
            # blob is completely unaffected.
            individual = [by_atlas_id[f"{bone}_{side}"] for bone in _TARSAL_BONE_IDS
                          if f"{bone}_{side}" in by_atlas_id]
            if len(individual) == len(_TARSAL_BONE_IDS):
                tarsal_cloud = np.vstack(individual)
        if rays and tarsal_cloud is not None:
            ends = [ray_ends(r, tarsal_cloud.mean(axis=0)) for r in rays]
            base = np.mean([e[0] for e in ends], axis=0)
            heads = np.mean([e[1] for e in ends], axis=0)
            axis = heads - base
            axis /= np.linalg.norm(axis)
            frames[f"metatarsals_{side}"] = (
                base, orthonormal_frame(base, heads),
                "the mean of the five metatarsal bases; long axis to the mean "
                "of the five heads, each ray measured separately", "long")

            ph = by_atlas_id.get(f"phalanges_foot_{side}")
            if ph is not None:
                u = (ph - base) @ axis
                prox = ph[u < np.quantile(u, 0.05)].mean(axis=0)
                tips = ph[u > np.quantile(u, 0.95)].mean(axis=0)
                frames[f"phalanges_foot_{side}"] = (
                    prox, orthonormal_frame(prox, tips),
                    "the proximal phalangeal bases; long axis to the toe tips",
                    "long")
        elif f"metatarsals_{side}" not in frames and tarsal_cloud is not None:
            # Q138: this session's forefoot mesh does NOT split into all five
            # metatarsals (metatarsal_rays() needs exactly 5 mesh-connectivity
            # components and gets 2 here: this release's 2nd-5th metatarsals
            # are still one fused block, only the 1st is its own component --
            # real anatomy, not a bug: the four lesser metatarsal bases lock
            # together at the tarsometatarsal joint far more tightly than the
            # 1st does against the medial cuneiform, so a coarse mesh keeps
            # THAT joint gap and loses the others. That one real gap is
            # exactly the bone tibialis_anterior and fibularis_longus both
            # insert on ("1st metatarsal base (peroneus longus, tibialis
            # anterior insertion)" in data/skeleton/bones.json), so it is
            # used alone rather than declining the whole bone: identified by
            # being both the SMALLER of the two components and the more
            # MEDIAL by real vertex position (mirrored per side, same
            # convention metatarsal_rays() itself uses) -- never assumed from
            # size alone. This frame is honest about being narrower than the
            # 5-ray one: its origin is the 1st metatarsal's OWN base, not the
            # mean of all five, so a landmark naming a DIFFERENT metatarsal
            # (5th metatarsal base/tuberosity, metatarsal heads as a group)
            # is not placed through it and stays unresolved, same as before.
            faces = faces_by_atlas_id.get(f"metatarsals_{side}")
            verts = by_atlas_id.get(f"metatarsals_{side}")
            if faces is not None and verts is not None:
                comp_faces = vh.mesh_components(faces)
                if len(comp_faces) == 2:
                    clouds = [verts[np.unique(faces[c])] for c in comp_faces]
                    sign = 1.0 if side == "r" else -1.0
                    by_size = sorted(clouds, key=len)
                    smaller, larger = by_size[0], by_size[1]
                    more_medial = (smaller[:, 0].mean() * sign
                                   < larger[:, 0].mean() * sign)
                    if more_medial:
                        base, head = ray_ends(smaller, tarsal_cloud.mean(axis=0))
                        frames[f"metatarsals_{side}"] = (
                            base, orthonormal_frame(base, head),
                            "the 1st metatarsal's OWN base (this release's forefoot "
                            "mesh keeps metatarsals 2-5 fused as one block; only the "
                            "1st is its own mesh-connectivity component, identified "
                            "as the smaller AND more medial of the two real pieces); "
                            "long axis to its own head -- landmarks naming a "
                            "different metatarsal are not placed through this frame",
                            "long")


    # ---- the upper body ------------------------------------------------
    #
    # Nothing above the hip has ever been measured: the Denver release is
    # pelvis to ankle. These frames are built from atlas ids rather than
    # source filenames, so they work with geometry from EITHER ingest -- an
    # STL release or a segmented CT -- and stay silent when the entity is
    # absent, which is what happens on a lower-limb-only subject.
    for side in ("r", "l"):
        full = "right" if side == "r" else "left"

        # The humeral head is a ball joint fitted exactly like the femoral
        # head, and for the same reason: the greater TUBERCLE sits lateral to
        # it and often reaches higher, so isolating the head by height fits
        # the tubercle instead.
        humerus = by_atlas_id.get(f"humerus_{side}")
        if humerus is not None and len(humerus) > 100:
            centre, radius, rms = volume_ingest.proximal_head_centre(humerus, full)
            lo, hi = volume_ingest.HEAD_RADIUS_MM["humerus"]
            if lo <= radius <= hi and rms <= 3.0:
                # `<=`, not `<`: a humerus cut flat by a CT field of view has
                # more than 2% of its vertices AT the minimum, and a strict
                # comparison then selects nothing and the frame comes out NaN
                # (the male's right humerus did, silently, until 2026-09-14).
                distal = humerus[humerus[:, 1] <= np.quantile(humerus[:, 1], 0.02)]
                frames[f"humerus_{side}"] = (
                    centre, orthonormal_frame(centre, distal.mean(axis=0)),
                    f"a sphere fit to the humeral head, r={radius:.1f} mm, "
                    f"rms={rms:.2f} mm; long axis to the distal end", "long")

        # Radius and ulna (added 2026-09-11, when the Visible Human arms
        # arrived). The atlas puts their origins at the PROXIMAL joint
        # surfaces (radial head; trochlear notch) with the long axis running
        # distally, so: origin = the proximal 2% of the bone along the
        # subject's superior axis, long axis to the distal 2%. On the VH
        # male those proximal ends come from the cryosection walk and are
        # +-10 mm at the elbow, which is the honest precision of this frame.
        for bone_name in ("radius", "ulna"):
            bone = by_atlas_id.get(f"{bone_name}_{side}")
            if bone is not None and len(bone) > 100:
                prox = bone[bone[:, 1] >= np.quantile(bone[:, 1], 0.98)]
                dist = bone[bone[:, 1] <= np.quantile(bone[:, 1], 0.02)]
                frames[f"{bone_name}_{side}"] = (
                    prox.mean(axis=0), orthonormal_frame(prox.mean(axis=0), dist.mean(axis=0)),
                    "the proximal 2% of the bone along the superior axis "
                    "(radial head / trochlear notch, +-10 mm at the elbow on "
                    "the VH male); long axis to the distal 2%", "long")

        # The clavicle's frame origin is the sternoclavicular joint, which is
        # its MEDIAL end -- the end nearest the midline. Measuring it that way
        # rather than taking an extreme along world X matters, because the
        # bone that had a mirrored landmark set is this one, and a frame built
        # from the same mistaken convention would hide it.
        clavicle = by_atlas_id.get(f"clavicle_{side}")
        if clavicle is not None and len(clavicle) > 20:
            towards_midline = np.abs(clavicle[:, 0])
            medial = clavicle[towards_midline <= np.quantile(towards_midline, 0.05)]
            lateral = clavicle[towards_midline >= np.quantile(towards_midline, 0.95)]
            frames[f"clavicle_{side}"] = (
                medial.mean(axis=0),
                orthonormal_frame(medial.mean(axis=0), lateral.mean(axis=0)),
                "the sternoclavicular end, as the 5% of the bone nearest the "
                "midline; long axis out to the acromial end", "long")

        # The scapula's origin is the glenoid centre. The glenoid is a shallow
        # fossa with no rim to fit, but it is the part of the scapula that
        # FACES the humeral head, so the humerus locates it -- and if there is
        # no humerus in the scan there is no defensible glenoid either.
        scapula = by_atlas_id.get(f"scapula_{side}")
        if scapula is not None and f"humerus_{side}" in frames:
            head = frames[f"humerus_{side}"][0]
            near = scapula[np.linalg.norm(scapula - head, axis=1)
                           <= np.quantile(np.linalg.norm(scapula - head, axis=1), 0.02)]
            glenoid = near.mean(axis=0)
            # Only the origin is measurable: the scapula has no long axis to
            # fit, and a frame built from the medial border (tried first)
            # points its Y toward the glenoid and its Z downward, which no
            # hand-authored landmark could be written in. Axes are therefore
            # the anatomical-position convention, as for the hip bone and
            # sternum: X right, Y up, Z anterior, at the glenoid centre.
            frames[f"scapula_{side}"] = (
                glenoid, np.eye(3),
                "the glenoid, as the 2% of the scapula closest to the fitted "
                "humeral head centre; axes by anatomical-position convention, "
                "not fitted", "neither")

    # The menton is the lowest point of the mandibular symphysis in the
    # midline; the mandible's authored frame originates there. Axes are the
    # anatomical-position convention: the bone has no fittable long axis.
    #
    # Q123 investigated a fitted alternative: the two TMJ condyles ARE
    # separately identifiable in this mesh with no cartilage or per-condyle
    # label needed (the superior 5% of the bone by height splits cleanly
    # into two point clouds either side of the midline with a genuinely
    # empty gap between them, no vertices within 30 mm of the midline in
    # that band; the resulting intercondylar width is stable across a wide
    # range of band sizes and agrees between the two bodies to within 1 mm:
    # 99.5 mm male, 100.4 mm female). But the menton-to-condyle-midpoint
    # line is NOT close to world-vertical -- the condyles sit well
    # POSTERIOR to the menton, not just superior to it, so that axis tilts
    # ~33-42 degrees off world Y. The existing hand-authored mandible
    # landmarks in bones.json were written in plain world-aligned axes
    # (condylar process at local y=+55, meaning "55 mm above the menton" in
    # WORLD Y, not "55mm along a menton-to-condyle line"). Fitting that
    # tilted frame and re-placing the existing landmarks through it was
    # tested directly with this script: median distance-to-bone-surface
    # for the mandible's own landmarks went from 4-8 mm (both bodies, the
    # current convention) to 25-28 mm -- a measured, unambiguous
    # regression, not a correction, because the fitted axis and the
    # authored coordinates use two different, incompatible conventions.
    # DECLINED for this reason (a genuinely different, correctly-measured
    # transverse-plus-long frame is possible here, but shipping it would
    # need bones.json's mandible landmarks re-authored in ITS coordinates,
    # which is out of this item's scope of not touching already-authored
    # landmark data); a good, scoped follow-up for a future session.
    mandible = by_atlas_id.get("mandible")
    if mandible is not None and len(mandible) > 20:
        midline = mandible[np.abs(mandible[:, 0] - np.median(mandible[:, 0])) < 6.0]
        if len(midline) > 5:
            frames["mandible"] = (
                midline[np.argmin(midline[:, 1])], np.eye(3),
                "the menton, as the lowest point of the symphysis within 6 mm "
                "of the mandibular midline; axes by anatomical-position "
                "convention, not fitted", "neither")

    # The hyoid's authored origin is the anterior midline point of its body.
    hyoid = by_atlas_id.get("hyoid")
    if hyoid is not None and len(hyoid) > 20:
        midline = hyoid[np.abs(hyoid[:, 0] - np.median(hyoid[:, 0])) < 6.0]
        if len(midline) > 5:
            frames["hyoid"] = (
                midline[np.argmax(midline[:, 2])], np.eye(3),
                "the anterior midline point of the hyoid body; axes by "
                "anatomical-position convention, not fitted", "neither")

    # The jugular notch is the superior midline notch of the manubrium: the
    # most superior point, taken near the midline so a clavicular facet
    # cannot win it.
    sternum = by_atlas_id.get("sternum")
    if sternum is not None and len(sternum) > 20:
        midline = sternum[np.abs(sternum[:, 0] - np.median(sternum[:, 0])) < 12.0]
        if len(midline) > 20:
            notch = midline[midline[:, 1] >= np.quantile(midline[:, 1], 0.98)]
            frames["sternum"] = (
                notch.mean(axis=0), np.eye(3),
                "the jugular notch, as the superior 2% of the manubrium within "
                "12 mm of the sternal midline; axes by anatomical-position "
                "convention, not fitted", "neither")

    # Q130: the atlas (C1) and axis (C2). `cervical_vertebrae` is ONE mesh
    # entity for all 7 vertebrae (bones.json has no per-level bone, same as
    # thoracic/lumbar), so there is no atlas_id to key straight off. But
    # unlike ribs (fused into one blob by Q109's continuity fix -- see
    # below), the 7 cervical vertebrae are NOT welded to each other in this
    # mesh: they come back as separate mesh-connectivity components, one
    # per vertebra, confirmed on both bodies (7 components female, 7 real +
    # 1 tiny stray fragment male). C1 is the topmost by mean Y (it is
    # physically the highest vertebra) and C2 the next-topmost; verified
    # against the raw per-vertebra TotalSegmentator labels (`vertebrae_C1`
    # id 50, `vertebrae_C2` id 49 in vhm_total.nii.gz/vhf_total.nii.gz,
    # mappings/totalsegmentator_labels.json) by comparing TRANSLATION-
    # INVARIANT shape (component span and the tip-minus-tubercle offset
    # within a component, since this mesh's own origin differs from the
    # raw scan's): C2 candidate spans (59.5, 43.2, 50.2) mm here vs (59.1,
    # 45.0, 49.7) mm from the raw C2 label (male), (54.1, 40.9, 51.5) vs
    # (55.3, 40.0, 50.6) (female); C1's tip-minus-tubercle offset (43.2,
    # 3.0, 28.8) here vs (37.5, 2.0, 29.1) from the raw label (male), (40.5,
    # 3.0, 29.4) vs (42.2, 6.0, 29.1) (female) -- all agree to a few mm, not
    # the ~900 mm this atlas's own translated origin would show if the
    # match were wrong. Origin is the dens tip (matches bones.json's
    # documented "C1 (atlas) superior articular facets / dens of C2"): the
    # most superior point of C2 within 8 mm of the midline. Axes by
    # anatomical-position convention, not fitted -- like sternum/mandible/
    # hyoid above, this bone has no long axis this script fits.
    cervical = by_atlas_id.get("cervical_vertebrae")
    cervical_faces = faces_by_atlas_id.get("cervical_vertebrae")
    if cervical is not None and cervical_faces is not None and len(cervical) > 500:
        comps = _mesh_components_by_height(cervical, cervical_faces, min_size=500)
        if len(comps) >= 2:
            c1, c2 = comps[0], comps[1]
            c2_mid = c2[np.abs(c2[:, 0]) < 8.0]
            if len(c2_mid) > 5:
                dens_tip = c2_mid[np.argmax(c2_mid[:, 1])]
                frames["cervical_vertebrae"] = (
                    dens_tip, np.eye(3),
                    "the dens tip: the most superior point of the SECOND-"
                    "topmost cervical mesh component (by mean Y) within 8 mm "
                    "of the midline, C1 and C2 identified by height ordering "
                    "and cross-checked by shape against the raw per-vertebra "
                    "CT labels (see above); axes by anatomical-position "
                    "convention, not fitted", "neither")

    # Q131: thoracic_vertebrae (T1-T12) and lumbar_vertebrae (L1-L5), the
    # next two region entities of the same kind as cervical_vertebrae above
    # (one atlas entity for several real, separate bones). Both come back as
    # clean per-vertebra mesh-connectivity pieces on both bodies (12 and 5,
    # matching count -- confirmed, not assumed), and on `ct_vhf` the exact
    # identity is not even inferred: `_vertebra_pieces_exact` reads it
    # straight off the manifest's own per-record TotalSegmentator label id.
    # Origin is each entity's OWN documented origin_landmark: the most
    # superior point of T1 (thoracic) / L1 (lumbar) within 8 mm of the
    # midline. `fitted="long"` (unlike cervical's "neither") because the two
    # subjects' column lengths measured this way are close (thoracic 305.8
    # vs 306.7 mm, lumbar 184.5 vs 196.8 mm) but not identical, and several
    # landmarks sit 200+ mm from the origin where even a small ratio error
    # compounds -- Q43's existing along-axis scaling removes exactly that.
    #
    # WHAT DID NOT GENERALISE (measured directly, not assumed): Q130's own
    # "measure the landmark on the male mesh" convention, applied the same
    # way here, does NOT reach Q130's 0.4-1.3 mm bar for any of 8 candidate
    # single-level landmarks tried (T1/T2/T4/T6/T7/T11 transverse or spinous
    # process, L1 transverse process) -- cross-subject placement error
    # measured at 12-50 mm, an order of magnitude worse than cervical. Cause
    # isolated by comparing the SAME conceptual point measured from the
    # decimated mesh vs. straight from the raw CT label mask on the SAME
    # subject (ct_vhm): they disagree by up to 44 mm on the male build alone
    # (`recovered from the published male viewer`, coarse: ~2900 vertices
    # per vertebra), while the same check on `ct_vhf` (TotalSegmentator-
    # direct, 10000-24000 vertices per vertebra) agrees with its own CT to
    # 6-9 mm -- so the male mesh, not genuine anatomy or a frame bug, is
    # the unreliable side FOR THIS FEATURE SIZE (it was reliable enough for
    # cervical's much larger transverse-process/tubercle features). Measuring
    # from `ct_vhf` instead and cross-checking placement against `ct_vhm`'s
    # own mesh gave 2 candidates within a few mm both ways (see bones.json)
    # and 6 that did not -- shipped only the 2, left the rest out rather than
    # ship a landmark known to disagree with its own source by a centimeter
    # or more.
    for atlas_id, prefix, expected in (
        ("thoracic_vertebrae", "T", [f"T{i}" for i in range(1, 13)]),
        ("lumbar_vertebrae", "L", [f"L{i}" for i in range(1, 6)]),
    ):
        pieces, how = _identify_vertebrae(manifest, by_atlas_id, faces_by_atlas_id,
                                          atlas_id, prefix, expected)
        if pieces is None:
            continue
        top = pieces[expected[0]]
        top_mid = top[np.abs(top[:, 0]) < 8.0]
        if len(top_mid) <= 5:
            continue
        origin = top_mid[np.argmax(top_mid[:, 1])]
        frames[atlas_id] = (
            origin, np.eye(3),
            f"the superior endplate of {expected[0]}: its most superior point "
            f"within 8 mm of the midline, {expected[0]} identified via {how}; "
            "axes by anatomical-position convention, not fitted", "long")

    # Length along the fitted long axis, for the landmark scaling (Q43).
    # Frames whose long axis is the anatomical-position convention (pelvis,
    # scapula, sternum ...) get None: a landmark on them stays in millimetres.
    for bone_id, (origin, basis, how, fitted) in list(frames.items()):
        mesh = by_atlas_id.get(bone_id)
        length = (bone_length_along_axis(mesh, origin, basis[1])
                  if fitted in ("both", "long") and mesh is not None and len(mesh) > 1
                  else None)
        frames[bone_id] = (origin, basis, how, fitted, length)

    return frames


def place(local_mm, frame, bone_record):
    """A local point of `bone_record`'s frame in world coordinates, on THIS
    subject: the one place the along-axis scaling is applied here."""
    origin, basis = frame[0], frame[1]
    return local_to_world(local_mm, origin, basis,
                          (bone_record or {}).get("reference_length_mm"),
                          frame[4] if len(frame) > 4 else None)


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--subject", default="vhm_both")
    ap.add_argument("--worst", type=int, default=12)
    args = ap.parse_args()

    try:
        manifest, blocks, by_atlas_id, faces_by_atlas_id = load_geometry(args.subject)
    except FileNotFoundError:
        raise SystemExit(f"No converted geometry for {args.subject!r}. "
                         f"Run the ingest's convert step first.")

    bones = {b["id"]: b for b in json.loads(
        (DATA_DIR / "skeleton" / "bones.json").read_text())}

    frames = build_frames(by_atlas_id, blocks, faces_by_atlas_id, manifest)

    meshes = dict(by_atlas_id)

    print(f"subject {args.subject}\n")
    rows = []
    for bone_id, (origin, basis, how, fitted, length) in sorted(frames.items()):
        mesh = meshes.get(bone_id)
        bone = bones.get(bone_id)
        if mesh is None or not bone:
            continue
        ref_len = bone.get("reference_length_mm")
        factor = (length / ref_len) if (ref_len and length) else 1.0
        # A landmark at the frame's own origin cannot test anything -- it IS
        # the origin. The femoral head sits at [0,0,0] by definition, so its
        # "distance to the surface" is just the head radius and says nothing
        # about the authored coordinates.
        # Distance-to-surface is only meaningful for a landmark that is
        # SUPPOSED to be on the surface. Two kinds are not:
        #   - a landmark at the frame's own origin IS the origin, so its
        #     distance is just the joint radius and tests nothing;
        #   - a foramen or canal is a HOLE. A point at the centre of the
        #     obturator foramen is correctly about 20 mm from any bone, and
        #     scoring that as the second-worst error in the set, as this did,
        #     was the check misreading a hole as a mistake.
        skipped_kinds = {"foramen_or_canal"}
        landmarks, holes = [], []
        for lm in bone.get("landmarks", []):
            if not lm.get("position_local_mm"):
                continue
            if np.linalg.norm(lm["position_local_mm"]) <= 1e-6:
                continue
            (holes if lm.get("kind") in skipped_kinds else landmarks).append(lm)
        if not landmarks:
            continue
        local = np.array([lm["position_local_mm"] for lm in landmarks], float)
        world = np.vstack([place(p, frames[bone_id], bone) for p in local])
        dist = nearest_distance(world, mesh)
        # Split the error along the bone's own long axis from the error across
        # it: the long axis is measured, the transverse rotation is not, so
        # the two are not equally trustworthy.
        delta = world - mesh[np.argmin(
            np.linalg.norm(mesh[None, :, :] - world[:, None, :], axis=2), axis=1)]
        along = np.abs(delta @ basis[1])
        across = np.sqrt(np.maximum(dist ** 2 - along ** 2, 0.0))
        print(f"{bone_id}   frame origin from {how}")
        if ref_len and length:
            print(f"  along-axis landmark coordinates scaled by {factor:.3f} "
                  f"(this bone {length:.1f} mm, reference {ref_len:.1f} mm)")
        extra = (f", {len(holes)} foramen/canal excluded (a hole is not a "
                 f"surface)" if holes else "")
        print(f"  {len(landmarks)} landmarks{extra}, distance to nearest "
              f"bone surface:")
        print(f"    median {np.median(dist):6.1f} mm   mean {dist.mean():6.1f}"
              f"   max {dist.max():6.1f}")
        # Which axis is trustworthy differs by bone, and BOTH tags have to be
        # read off the frame rather than assumed. The femur and tibia have
        # both axes fitted; the pelvis's long axis is the anatomical-position
        # convention and only its transverse axis is fitted; the metatarsals
        # are the other way round -- long axis fitted on the five rays,
        # transverse taken from the world frame. Printing "across it (fitted)"
        # unconditionally, as this did, credited three bones with a precision
        # they do not have.
        tag = {"both": ("fitted", "fitted"),
               "long": ("fitted", "ASSUMED"),
               "transverse": ("ASSUMED", "fitted"),
               "neither": ("ASSUMED", "ASSUMED")}[fitted]
        print(f"    along the long axis ({tag[0]}): median "
              f"{np.median(along):.1f} mm; across it ({tag[1]}): "
              f"median {np.median(across):.1f} mm")
        # Size, before anyone reads the along-axis figure as an error.
        #
        # A landmark's along-axis coordinate is a distance in millimetres from
        # a joint centre, so it only means the same thing on a bone of the
        # same length. Run this against a subject whose humerus is 20 mm
        # shorter than the one the coordinates were written for and EVERY
        # distal landmark reads 20 mm past the end -- which is a real
        # mismatch, but a mismatch of scale, not of placement, and treating
        # it as placement would move correct landmarks to fit one body.
        #
        # This mattered little on the Visible Human, where the coordinates
        # and the geometry describe the same person. It matters immediately
        # on a CT of somebody else.
        if fitted in ("both", "long"):
            along_bone = (mesh - origin) @ basis[1]
            span = float(along_bone.max() - along_bone.min())
            reach = float(np.abs(local[:, 1]).max() * factor)
            note = ""
            if reach > span:
                note = ("   <-- the atlas reaches PAST the end of this bone; "
                        "read the along-axis figures as scale, not placement")
            print(f"    bone measures {span:.0f} mm along that axis; the most "
                  f"distal landmark sits {reach:.0f} mm out{note}")
        for lm, d, a, c in sorted(zip(landmarks, dist, along, across),
                                  key=lambda t: -t[1])[:3]:
            print(f"      {d:6.1f} mm  (along {a:5.1f}, across {c:5.1f})  "
                  f"{lm['name'][:62]}")
        print()
        rows.extend((d, bone_id, lm["name"]) for lm, d in zip(landmarks, dist))

    # ---- identity check: is it on the bone it NAMES? ---------------------
    #
    # The sharpest version of the wrong-feature problem. Distance-to-surface
    # cannot catch a mediolateral mirror inside a group of bones at all: a
    # point placed on the fifth metatarsal instead of the first is still on
    # a metatarsal, 3 mm from a surface, and scores as a good landmark.
    #
    # Two atlas entities are groups whose members the release ships or yields
    # separately -- the seven tarsals as seven meshes, the five metatarsals as
    # five connected components once the forefoot is split. So for those, a
    # landmark that names one member can be tested against that member, and
    # this is the only check here that can see a mirror.
    print("\nis each landmark on the bone it NAMES?")
    all_anchors = json.loads((DATA_DIR / "rig" / "anchors.json").read_text())
    named = named_members(blocks, by_atlas_id, faces_by_atlas_id, manifest)
    identity_bad = []
    for bone_id, members in sorted(named.items()):
        if bone_id not in frames or bone_id not in bones:
            continue
        items = [(lm["name"], lm["position_local_mm"])
                 for lm in bones[bone_id].get("landmarks", [])
                 if lm.get("position_local_mm")]
        items += [(a["id"], a["local_position_mm"]) for a in all_anchors
                  if a.get("parent_bone_frame") == bone_id]
        for name, local in items:
            want = expected_member(name, members)
            if want is None:
                continue          # names no single member; nothing to test
            world = place(local, frames[bone_id], bones[bone_id])
            got = min(members, key=lambda m: float(
                np.linalg.norm(members[m] - world, axis=1).min()))
            if got != want:
                identity_bad.append((bone_id, name, want, got))
    if identity_bad:
        print(f"  {len(identity_bad)} land on the WRONG member of their group:")
        for bone_id, name, want, got in identity_bad:
            print(f"    {bone_id:16} names {want:12} sits on {got:12}  {name[:44]}")
    else:
        print("  every landmark naming one member of a bone group sits on it.")

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
            level = (place(pick[a_name], frames[f"{stem}_{side}"], bone) - origin) @ basis[1]
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
    muscle_cloud = by_atlas_id

    checked, bone_far, muscle_far, wraps, no_muscle = [], [], [], [], 0
    routed = []
    via_points = load_via_points()
    for a in anchors:
        frame = frames.get(a.get("parent_bone_frame"))
        if not frame:
            continue
        world = place(a["local_position_mm"], frame, bones.get(a.get("parent_bone_frame")))
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
            # Distinguish an attachment that lies BEYOND the end of its muscle
            # from one that is off to the side. The DU meshes carry no tendon,
            # so a muscle with a long proximal tendon legitimately begins far
            # from its bony origin: semimembranosus starts 89 mm below the
            # ischial tuberosity, while biceps femoris and semitendinosus --
            # same tuberosity, short tendons -- start right at it. Calling
            # that an error, as an earlier version of this report did, blamed
            # the atlas for anatomy the geometry simply does not contain.
            # "Past the end" has to be measured along the MUSCLE's own long
            # axis, not world Y. Piriformis, the gemelli and obturator
            # internus all run transversely and reach the greater trochanter
            # by a sideways tendon; measured along Y they score zero past the
            # end and their missing tendon is misread as a placement error.
            centred = cloud - cloud.mean(axis=0)
            axis = np.linalg.svd(centred.T @ centred)[0][:, 0]
            proj = centred @ axis
            t = float((world - cloud.mean(axis=0)) @ axis)
            beyond = max(0.0, t - float(proj.max()), float(proj.min()) - t)
            lateral = float(np.sqrt(max(d_muscle ** 2 - beyond ** 2, 0.0)))
        checked.append((a["id"], owner, d_bone, d_muscle,
                        a.get("anchor_type", ""),
                        beyond if cloud is not None else float("nan"),
                        lateral if cloud is not None else float("nan")))
        if d_bone == d_bone and d_bone > 20:
            bone_far.append((d_bone, a["id"], owner))
        # Only an attachment that is off to the SIDE of its muscle is a
        # placement error; one past the end is a missing tendon.
        #
        # ...unless the tendon TURNS A CORNER, and then this split means
        # nothing. Splitting the distance along the belly's own long axis
        # assumes the tendon carries on in that direction. Flexor hallucis
        # longus runs down the deep posterior compartment, behind the medial
        # malleolus, under the sustentaculum tali and forward along the sole
        # to the great toe: a right angle. That scored 155 mm "off to the
        # side" of a muscle it is correctly attached to.
        #
        # A tendon cannot pass through bone. So the straight line from the
        # muscle to its attachment is tested against every bone in the way,
        # and where it is blocked the muscle is reported as needing a wrap
        # path rather than as a misplaced anchor.
        if d_muscle == d_muscle and lateral > 20:
            # A muscle that DECLARES a path gets tested on that path, not on
            # the straight line. That is the point of via_points: they are
            # the atlas's answer to this check, so the check has to read them.
            route = via_path(owner, a, via_points, frames, bones)
            if route is not None:
                start = cloud[np.argmin(np.linalg.norm(cloud - route[0], axis=1))]
                pts = [start] + route + [world]
                blocker = next(
                    (b for b, _d in (path_through_bone(np.linspace(u, v, 60),
                                                       meshes, faces_by_atlas_id)
                                     for u, v in zip(pts, pts[1:])) if b), None)
                if blocker is None:
                    routed.append((a["id"], owner, len(route)))
                else:
                    wraps.append((a["id"], owner, d_muscle,
                                  f"{blocker} (despite {len(route)} via point(s))"))
            else:
                blocker = blocked_by_bone(cloud, world, meshes, faces_by_atlas_id)
                if blocker:
                    wraps.append((a["id"], owner, d_muscle, blocker))
                else:
                    muscle_far.append((d_muscle, a["id"], owner, beyond, lateral))

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
            side_only = np.array([c[6] for c in checked
                                  if c[4] == kind and c[6] == c[6]])
            print(f"  {kind:16} to its own muscle: median {np.median(sub):5.1f}"
                  f" mm total, of which off to the SIDE: median "
                  f"{np.median(side_only):5.1f} mm, "
                  f"{int((side_only > 20).sum())}/{len(side_only)} beyond 20 mm")
        if no_muscle:
            print(f"  ({no_muscle} anchors own a structure with no geometry here)")
        if bone_far:
            print(f"\n  {len(bone_far)} anchors far from its bone:")
            for d, aid, owner in sorted(bone_far, reverse=True)[:10]:
                print(f"    {d:6.1f} mm  {aid[:52]:54} -> {owner}")
        if muscle_far:
            print(f"\n  {len(muscle_far)} anchors OFF TO THE SIDE of their own "
                  f"muscle (past-the-end and wrapping tendons excluded):")
            for d, aid, owner, beyond, lateral in sorted(muscle_far, reverse=True)[:10]:
                print(f"    side {lateral:6.1f} mm (of {d:6.1f} total, "
                      f"{beyond:5.1f} past the end)  {aid[:44]:46} -> {owner}")
        if routed:
            print(f"\n  {len(routed)} attachments reached by a DECLARED path, "
                  f"clear of bone the whole way:")
            for aid, owner, n in sorted(routed):
                print(f"    {n} via point(s)  {aid[:52]:54} -> {owner}")
        if wraps:
            print(f"\n  {len(wraps)} attachments their muscle cannot reach in a "
                  f"straight line: bone is in the way. Not a placement error "
                  f"against the muscle -- either the tendon wraps and the path "
                  f"is missing (the quadriceps over the patella, flexor "
                  f"hallucis longus under the sustentaculum), or the anchor is "
                  f"on the far side of its own bone (fibularis longus arises "
                  f"ON the fibula named below). Both need looking at; neither "
                  f"is fixed by moving the anchor toward the belly:")
            for aid, owner, d, blocker in sorted(wraps, key=lambda r: -r[2]):
                print(f"    {d:6.1f} mm  blocked by {blocker:16} {aid[:44]:46}")

    # ---- collapsed landmarks: many muscles on one coordinate ------------
    #
    # This needs no geometry and applies to the whole atlas, but the geometry
    # is what made it visible. The iliac crest is a 90 mm ARC on the ilium.
    # The atlas gives it one point, and six muscles -- tensor fasciae latae,
    # quadratus lumborum, longissimus, iliocostalis and both obliques -- all
    # anchor to that same coordinate, though they attach at different places
    # along it. The atlas's point sits on the ANTERIOR crest; the crest's
    # highest point is 49 mm away on the POSTERIOR crest, and both are
    # legitimately "the iliac crest". No single coordinate can be right for
    # all six, which is why moving it would not have helped.
    shared = {}
    for a in anchors:
        key = (a.get("parent_bone_frame"), tuple(a.get("local_position_mm", [])))
        shared.setdefault(key, []).append(a["owner_entity"])
    crowded = sorted(((len(v), k, v) for k, v in shared.items() if len(v) >= 4),
                     reverse=True)
    if crowded:
        print(f"\nlandmarks carrying 4+ different muscles on ONE coordinate")
        print("  a broad attachment line collapsed to a point -- each muscle "
              "takes its own part of it, so no single value fits them all")
        for n, (bone, pos), owners in crowded[:8]:
            print(f"  {n:2} muscles at {bone} {list(pos)}: "
                  f"{', '.join(sorted(owners)[:5])}"
                  f"{' ...' if len(owners) > 5 else ''}")

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

Which axes are fitted differs by bone and each block above says so. Femur
and tibia have both fitted, so an error either way is the landmark's. The
pelvis's superior axis is the anatomical-position convention, so read its
along-axis figure with that in mind -- though in practice the pelvic errors
sit on the FITTED transverse axis, which is what makes them actionable.

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
