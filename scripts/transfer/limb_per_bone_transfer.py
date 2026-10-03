"""Q147: fill forearm/hand/foot soft tissue on both Visible Human specimens by
transferring Z-Anatomy structures with a PER-BONE (not global/segment) registration
onto each specimen's own bones -- owner's standing direction ("use Z-Anatomy for
completeness, correct later"), replacing Q142's broad multi-bone spatial blend for
exactly this region (Q142's own validation found 18-83mm centroid error there,
largely blamed on forearm pronation/pose differences between a generic body and a
real specimen).

METHOD. For every missing structure, its DOMINANT bone(s) come from the entity
registry's own attachment fields first (muscle/tendon `attachments.origin_bone` /
`insertion_bone` / `via_points[].bone_frame`; ligament `attachments.bone_a`/`bone_b`;
fascia/retinaculum `bony_attachments[].bone`), restricted to the forearm/hand or
leg/foot bone set (never humerus/scapula/femur -- a structure that also touches one
of those keeps only its LOCAL bone(s), the proximal end is not this task's problem
and already sits correctly on the specimen's own real humerus/scapula); a region-
name fallback (`dominant_bones_by_region`) only fires when a record carries no
usable attachment at all. Radius and ulna are ALWAYS kept as separate candidates
(never averaged into one "forearm" frame) -- this is the pronation fix: a vertex
nearer the ulna gets the ulna's own rigid+uniform-scale affine (bone_frame/
bone_affine, both UNCHANGED, straight from bone_frames.py), a vertex nearer the
radius gets the radius's; the same nearest-bone-of-a-small-set rule serves as the
"proximal->distal weight" the task asks for on a carpals->phalanges or
tibia/fibula->tarsals chain, since distance to a bone further down the chain grows
monotonically along it. `cross_subject_transfer.build_bone_maps` is reused
UNCHANGED for the affine-per-bone step (TRUNCATED clipping for the female's
FOV-clipped radius/ulna included); only the BLEND is new (`blend_by_bones`,
restricted per-structure candidate set instead of `blend_transfer`'s broad
per-region one).

SAFETY. After the blend: `push_off_bones` (adapted from
scripts/zanatomy/apply_corrections.py's own `_push_off_bones`, same push-to-
surface-plus-clearance-along-the-interior-ray method, but against the DESTINATION
specimen's own bone meshes instead of Z-Anatomy's) pushes any vertex now inside a
local bone back out to its surface; `clip_to_skin_mesh` (a mesh-containment
equivalent of cross_subject_transfer.py's own NIfTI-based `clip_to_skin`, used
because a raw skin volume does not necessarily survive a container reset while the
built skin mesh in the destination bundle always does) pulls any vertex left
outside the specimen's own skin back to just inside it.

VALIDATION (required before shipping, not a shipping gate -- see PROJECT_STATE.md
Q147/Q142): the identical method, run on ids that ALREADY have real, non-transferred
geometry on the target (male: ct_vhm_forearm; female: ct_vhf_forearm/
ct_vhf_left_forearm), scored against that real mesh by
scripts/zanatomy/validate_registration.py's own `compare()` (centroid distance,
volume ratio, 2mm-voxel Dice/IoU), imported unchanged. The measured median centroid
error feeds the shipped subjects' own procedural_badge text, honestly, per
structure -- Q142's "ship nothing" bar is NOT applied here; the owner's own
instruction this time is "ship an estimate, badge it, correct later".

    python3 scripts/transfer/limb_per_bone_transfer.py --direction zan2m \
        --male-html build/viewer_m -o build/vh/xfer_zan2vhm_limb \
        --report data/derived/transfer_report_zan2vhm_limb.json

    python3 scripts/transfer/limb_per_bone_transfer.py --direction zan2f \
        --female-bundle build/viewer_f -o build/vh/xfer_zan2vhf_limb \
        --report data/derived/transfer_report_zan2vhf_limb.json

    # validation (ids that are already real on the target; --validate names the
    # target bundle to score against; nothing is shipped in this mode)
    python3 scripts/transfer/limb_per_bone_transfer.py --direction zan2m --male-html build/viewer_m \
        --ids flexor_digitorum_superficialis_r flexor_digitorum_profundus_r abductor_pollicis_longus_r \
        --validate build/viewer_m -o build/vh/_val_zan2vhm_limb --report data/derived/Q147_validation_male.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
from scipy.spatial import cKDTree

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.transfer.bundle_io import read_bundle_html, read_bundle_dir, meshes_by_id, mesh_volume_cm3  # noqa: E402
from scripts.transfer.bone_frames import bone_frame, bone_affine, apply  # noqa: E402
from scripts.transfer.cross_subject_transfer import TRUNCATED, side_of  # noqa: E402
from scripts.zanatomy import zan_source  # noqa: E402
from scripts.export_viewer_bundle import load_atlas_records  # noqa: E402

FOREARM_HAND_BASES = {"radius", "ulna", "carpals", "metacarpals", "phalanges_hand"}
FOOT_BASES = {"tarsals", "metatarsals", "phalanges_foot"}
LEG_BASES = {"tibia", "fibula"}
ALL_LOCAL_BASES = FOREARM_HAND_BASES | FOOT_BASES | LEG_BASES

SOFTEN_MM = 8.0
MIN_VERTICES = 64
BONE_PUSH_CLEARANCE_MM = 1.0
TWIST_CANDIDATES = 12
TWIST_SAMPLE = 800
OUTSIDE_SKIN_REJECT_FRACTION = 0.5

# tarsal pieces this project's own registry/Z-Anatomy match ships as SEPARATE bones
# (talus/calcaneus/cuboid/navicular/cuneiform_*) -- neither specimen ships a "tarsals_r/l"
# BLOCK bone of its own (only Q142's own xfer_vhm2vhf synthesises one for the female, which
# own_only-style filtering here excludes as "not this body's own"), but Z-Anatomy's own
# "Tarsals.r/l" DOES exist as a single matched source object (see zan_source), and this
# task's own dominant-bone rule for foot structures names "tarsals" -- so a destination
# "tarsals_<side>" frame is synthesised here, once, as the union of whichever of the seven
# split pieces the specimen actually has.
TARSAL_PIECES = ("talus", "calcaneus", "cuboid", "navicular",
                  "cuneiform_medial", "cuneiform_intermediate", "cuneiform_lateral")


def _rotate_about_axis(axis: np.ndarray, theta: float) -> np.ndarray:
    axis = axis / np.linalg.norm(axis)
    K = np.array([[0, -axis[2], axis[1]], [axis[2], 0, -axis[0]], [-axis[1], axis[0], 0]])
    return np.eye(3) + np.sin(theta) * K + (1 - np.cos(theta)) * (K @ K)


def _identity_frame(v: np.ndarray) -> dict:
    """Exactly bone_frame()'s own identity-branch computation (same percentile
    box, R forced to eye(3)), factored out so it can be applied to EITHER body
    on demand -- see _consistent_frames()."""
    c = v.mean(axis=0)
    proj = v - c
    lo, hi = np.percentile(proj, 1, axis=0), np.percentile(proj, 99, axis=0)
    return {"R": np.eye(3), "ext": hi - lo, "centre": c + (lo + hi) / 2, "n": int(len(v))}


def _consistent_frames(src_v: np.ndarray, dst_v: np.ndarray) -> tuple[dict, dict]:
    """bone_frame()'s identity branch (LONG_RATIO) reassigns axis0 to plain atlas
    X for a not-"long-enough" bone, instead of "the long axis" as the PCA branch
    does for axis0 -- a real, different meaning. If ONE body's own bone crosses
    that ratio threshold and the other does not (the female's own tarsal union
    does; Z-Anatomy's does not -- found chasing an ICP cost of ~450mm, an order
    of magnitude worse than every other bone here, for a structure whose OWN two
    frames' axis0 turned out to mean two different things), `bone_affine` silently
    maps one body's LONG axis onto the other's plain X axis. Forces BOTH frames to
    the identity branch together whenever EITHER one alone would use it, so
    axis0/1/2 mean the same (atlas X/Y/Z) thing on both sides -- a safe, if less
    pose-adaptive, common ground -- rather than ever crossing a PCA frame with an
    identity one."""
    fs, fd = bone_frame(src_v), bone_frame(dst_v)
    if np.allclose(fs["R"], np.eye(3)) != np.allclose(fd["R"], np.eye(3)):
        fs, fd = _identity_frame(src_v), _identity_frame(dst_v)
    return fs, fd


def robust_bone_affine(src_v: np.ndarray, dst_v: np.ndarray, uniform: bool,
                        n_candidates: int = TWIST_CANDIDATES, sample: int = TWIST_SAMPLE):
    """bone_frames.bone_frame()'s own cross-sectional axis pick ("each remaining
    principal axis points along whichever ATLAS axis it is closest to") is only a
    fair common reference between two bodies when the bone's long axis is ITSELF
    close to one atlas axis on BOTH of them. A real specimen's forearm/limb can be
    posed well away from Z-Anatomy's own neutral standing pose (this task's whole
    point) -- when that happens the snap can give the two bodies a genuinely
    DIFFERENT in-plane (cross-sectional) axis correspondence, which showed up here
    as soft tissue thrown up to ~700mm from its bone (see PROJECT_STATE.md Q147;
    the male's own real ulna_r long axis runs diagonally, nowhere near atlas Y).

    Verified, not assumed, and fixed the way the task's own method note suggests
    ("fit rigid+uniform-scale (or ICP after coarse landmark alignment)"): tries
    `n_candidates` extra twists of the coarse bone_affine() fit about the
    destination bone's own long axis as ICP starting points (a plain nearest-
    neighbour RMS score, tried first, barely separated the candidates -- the
    ulna's own shape is not asymmetric enough for that alone to disambiguate a
    twist that only shows up once something AWAY from the bone, like a nearby
    muscle, is placed by it), runs `trimesh.registration.icp` (rigid, no
    reflection, no extra scale -- scale already fixed by bone_affine) from each,
    and keeps the twist+ICP-refinement with the lowest final ICP cost. A bone
    bone_frame() itself judged not "long" (its own atlas-identity branch,
    LONG_RATIO) is left exactly as bone_frame/bone_affine already computed it --
    twisting around an arbitrary axis for a blob-shaped bone (carpals, phalanges)
    would not mean anything, and ICP has nothing to disambiguate there either."""
    import trimesh
    fs, fd = _consistent_frames(src_v, dst_v)
    if np.allclose(fd["R"], np.eye(3)):
        A, t = bone_affine(fs, fd, uniform=uniform)
        return A, t, fs, fd
    rng = np.random.default_rng(0)
    src_s = src_v[rng.choice(len(src_v), min(sample, len(src_v)), replace=False)] if len(src_v) > sample else src_v
    dst_s = dst_v[rng.choice(len(dst_v), min(sample, len(dst_v)), replace=False)] if len(dst_v) > sample else dst_v
    axis = fd["R"][:, 0]
    best = None
    for k in range(n_candidates):
        theta = 2 * np.pi * k / n_candidates
        Rk = _rotate_about_axis(axis, theta)
        fd_k = {"R": fd["R"].copy(), "ext": fd["ext"], "centre": fd["centre"]}
        fd_k["R"][:, 1:] = Rk @ fd["R"][:, 1:]
        A, t = bone_affine(fs, fd_k, uniform=uniform)
        pts = apply(A, t, src_s)
        try:
            matrix, _, cost = trimesh.registration.icp(pts, dst_s, max_iterations=25, scale=False, reflection=False)
        except Exception:
            continue
        if best is None or cost < best[0]:
            best = (cost, A, t, fd_k, matrix)
    if best is None:
        A, t = bone_affine(fs, fd, uniform=uniform)
        return A, t, fs, fd
    _, A, t, fd_best, matrix = best
    A2 = matrix[:3, :3] @ A
    t2 = matrix[:3, :3] @ t + matrix[:3, 3]
    return A2, t2, fs, fd_best


def build_bone_maps(src: dict, dst: dict) -> dict:
    """Q147's own per-bone map builder -- reuses bone_frame/bone_affine and the
    TRUNCATED clip table UNCHANGED from cross_subject_transfer.py (same clipping,
    same female radius/ulna FOV handling), but fits each bone's rotation with
    `robust_bone_affine` above instead of a single bone_affine() call, and ALWAYS
    uniform-scales (the task's own stated method: "fit rigid+uniform-scale ...
    Z-Anatomy bone -> specimen bone"), not just the TRUNCATED bones --
    cross_subject_transfer.py's own non-uniform per-axis scale, tried first here
    too, stretched a thin sheet structure (plantar_aponeurosis_r) to 18x its own
    volume in a single axis: whichever of a coarse bone box's 3 axes happens to
    scale most between the two bodies is not a safe axis to scale a sheet's own
    thickness by non-uniformly."""
    maps = {}
    for aid, m in src.items():
        if m["cat"] != "bone" or aid not in dst or dst[aid]["cat"] != "bone":
            continue
        direction = TRUNCATED.get(aid)
        clip = {"top": 200.0, "bottom": -200.0}.get(direction)
        src_v = m["v"] if clip is None else m["v"][m["v"][:, 1] >= m["v"][:, 1].max() - clip] if clip >= 0 else \
            m["v"][m["v"][:, 1] <= m["v"][:, 1].min() - clip]
        A, t, fs, fd = robust_bone_affine(src_v, dst[aid]["v"], uniform=True)
        maps[aid] = {"A": A, "t": t, "side": side_of(aid, m), "tree": cKDTree(m["v"]),
                     "det": float(np.linalg.det(A)), "src": fs, "dst": fd}
    return maps


def synth_tarsal_blocks(meshes: dict) -> dict:
    """Add a synthetic "tarsals_<side>" bone entry, the union of whichever
    TARSAL_PIECES `meshes` actually has, for any side that does not already
    carry one of its own -- neither specimen ships one, AND Z-Anatomy's own
    matched inventory has no single "Tarsals.r/l" object either (verified, not
    assumed: both split the same seven ways -- see TARSAL_PIECES), so this is
    called on BOTH the source and the destination meshes dict. A no-op (returns
    `meshes` unchanged, same object) wherever a "tarsals_<side>" already exists."""
    out = dict(meshes)
    for side in ("r", "l"):
        aid = f"tarsals_{side}"
        if aid in out:
            continue
        vs, fs, voff = [], [], 0
        for piece in TARSAL_PIECES:
            m = meshes.get(f"{piece}_{side}")
            if m is None:
                continue
            vs.append(m["v"].astype(np.float64)); fs.append(m["f"].astype(np.int64) + voff)
            voff += len(m["v"])
        if vs:
            out[aid] = {"v": np.concatenate(vs), "f": np.concatenate(fs), "cat": "bone",
                        "side": "right" if side == "r" else "left", "subject": "synthetic_tarsal_union"}
    return out


# Z-Anatomy's own matched inventory (data/derived/zanatomy_name_map.json) has no single
# block object for the carpus, metacarpus, hand/foot phalanges or metatarsus either --
# each ships as individual named bones (e.g. "Scaphoid bone.r", "Fifth metacarpal
# bone.r") that map_names.py's generic matcher does not confidently score against this
# project's own block ids (verified, not assumed: none of these 5 ids are keys of
# zan_source.load_source()'s own output). Named here as a UNION of many raw parts --
# unlike zan_source's own small by-name overrides (Q142/Q144 precedent, a single id
# swap), so it lives in this file rather than that shared, reused module; map_names.py
# and the committed zanatomy_name_map.json are both left exactly as Q141 produced them.
FOOT_HAND_BLOCK_PARTS = {
    "carpals": ["Scaphoid bone", "Lunate bone", "Triquetrum bone", "Pisiform bone",
                "Trapezium bone", "Trapezoid bone", "Capitate bone", "Hamate bone"],
    "metacarpals": [f"{o} metacarpal bone" for o in ("First", "Second", "Third", "Fourth", "Fifth")],
    "phalanges_hand": [f"{p} phalanx of {o} finger of hand" for o in
                        ("First", "Second", "Third", "Fourth", "Fifth") for p in ("Proximal", "Middle", "Distal")],
    "metatarsals": [f"{o} metatarsal bone" for o in ("First", "Second", "Third", "Fourth", "Fifth")],
    "phalanges_foot": [f"{p} phalanx of {o} finger of foot" for o in
                        ("First", "Second", "Third", "Fourth", "Fifth") for p in ("Proximal", "Middle", "Distal")],
}


def synth_source_blocks(src: dict, zan_dir) -> dict:
    """The SOURCE (Z-Anatomy) side of FOOT_HAND_BLOCK_PARTS -- the destination
    specimens already ship every one of these 5 ids as a real block bone (own
    imaging), so only Z-Anatomy needs synthesising. Missing individual parts (a
    name this build's own extraction does not have) are silently skipped, same
    as zan_source's own `_mesh_for_cands`."""
    from scripts.zanatomy.zan_source import safe_filename, to_atlas_frame
    out = dict(src)
    for base, names in FOOT_HAND_BLOCK_PARTS.items():
        for side in ("r", "l"):
            aid = f"{base}_{side}"
            if aid in out:
                continue
            vs, fs_, voff = [], [], 0
            for name in names:
                path = Path(zan_dir) / "Skeletal" / f"{safe_filename(f'{name}.{side}')}.npz"
                if not path.exists():
                    continue
                d = np.load(path)
                vs.append(to_atlas_frame(d["vertices_mm"]))
                fs_.append(d["faces"].astype(np.int64) + voff)
                voff += len(vs[-1])
            if vs:
                out[aid] = {"v": np.concatenate(vs).astype(np.float32), "f": np.concatenate(fs_),
                            "cat": "bone", "side": "right" if side == "r" else "left",
                            "subject": "zanatomy", "rec": {"region": None}}
    return out


def base_bone(bone_id: str) -> str:
    return bone_id[:-2] if bone_id.endswith(("_r", "_l")) else bone_id


def extract_attachment_bones(rec: dict) -> list[str]:
    """Every bone id an entity record names anywhere reasonable, in a stable
    (origin, insertion, via-points, ligament ends, fascia attachments) order --
    used both to pick this structure's own dominant bone(s) and, in
    default_ids(), to decide whether it is in this task's forearm/hand/foot scope
    at all (see module docstring)."""
    out = []
    att = rec.get("attachments") or {}
    for k in ("origin_bone", "insertion_bone", "bone_a", "bone_b"):
        if att.get(k):
            out.append(att[k])
    for vp in att.get("via_points") or []:
        if vp.get("bone_frame"):
            out.append(vp["bone_frame"])
    for e in rec.get("bony_attachments") or []:
        if e.get("bone"):
            out.append(e["bone"])
    return out


def dominant_bones(rec: dict, region: str | None, side: str) -> list[str]:
    """This structure's own dominant bone(s), `<base>_<side>` ids, side already
    resolved to this exact structure's own side (never the other side)."""
    bases = {base_bone(b) for b in extract_attachment_bones(rec) if base_bone(b) in ALL_LOCAL_BASES}
    region = (region or "").lower()
    if not bases:
        # region-name fallback only: no usable attachment field on this record at all
        if region == "forearm":
            bases = {"radius", "ulna"}
        elif region in ("wrist_hand", "hand", "wrist"):
            bases = {"carpals", "metacarpals", "phalanges_hand"}
        elif region == "leg":
            bases = {"tibia", "fibula"}
        elif region in ("ankle_foot", "foot"):
            bases = {"tarsals", "metatarsals", "phalanges_foot"}
        elif region == "upper_limb":
            bases = {"radius", "ulna"}
        elif region == "lower_limb":
            bases = {"tibia", "fibula"}
    elif region == "upper_limb" and not (bases & {"radius", "ulna"}):
        # e.g. FDS: origin_bone is humerus (filtered out, proximal/out of scope) and
        # insertion/via-points only reach phalanges_hand/carpals -- the belly itself
        # is still mostly forearm, so radius/ulna must stay in the candidate set.
        bases |= {"radius", "ulna"}
    return sorted(f"{b}_{side}" for b in bases)


def in_scope(region: str | None, bases: set[str]) -> bool:
    """Whether a structure (by its region and the LOCAL bases extract_attachment_bones
    found) is this task's forearm/hand/foot scope -- NOT general leg/thigh/knee/elbow,
    even if a bone in that broader region happens to be tibia/fibula (e.g. fibularis
    brevis/tertius, popliteofibular ligament: real gaps, but leg-region, out of Q147)."""
    region = (region or "").lower()
    if region in ("wrist_hand", "hand", "wrist", "forearm"):
        return True
    if region == "upper_limb" and bases and bases <= FOREARM_HAND_BASES:
        return True
    if region == "ankle_foot":
        return True
    if region == "lower_limb" and bases and bases <= FOOT_BASES:
        return True
    return False


def default_ids(src: dict, dst_ids: set[str], atlas_records: dict) -> list[str]:
    out = []
    for aid, m in src.items():
        if m["cat"] not in ("muscle", "tendon", "ligament", "fascia", "bursa"):
            continue
        if aid in dst_ids:
            continue
        side = side_of(aid, m)
        if side not in ("right", "left"):
            continue
        _, rec = atlas_records.get(aid, (None, None))
        if rec is None:
            continue
        region = rec.get("region")
        bases = {base_bone(b) for b in extract_attachment_bones(rec) if base_bone(b) in ALL_LOCAL_BASES}
        if in_scope(region, bases):
            out.append(aid)
    return sorted(out)


def blend_by_bones(v: np.ndarray, maps: dict, bones: list[str], k_nearest: int = 3):
    """Blend v's own per-bone affines (from `maps`, built by
    cross_subject_transfer.build_bone_maps -- unchanged) restricted to `bones`
    ONLY, weighted by inverse-square distance to each candidate bone's own nearest
    surface vertex (see module docstring for why this both handles the radius/ulna
    pronation split and stands in for a proximal->distal weight along a bone
    chain). Returns (None, reason) if none of `bones` has a map (e.g. the female's
    missing left forearm/hand bones -- no driving bone on that side at all)."""
    cands = [b for b in bones if b in maps]
    if not cands:
        return None, "no driving bone available on this specimen (" + ",".join(bones) + ")"
    if len(cands) == 1:
        b = cands[0]
        return apply(maps[b]["A"], maps[b]["t"], v), {b: 1.0}
    k = min(k_nearest, len(cands))
    D = np.stack([maps[b]["tree"].query(v)[0] for b in cands], axis=1)
    order = np.argsort(D, axis=1)[:, :k]
    w = 1.0 / (np.take_along_axis(D, order, 1) + SOFTEN_MM) ** 2
    w /= w.sum(axis=1, keepdims=True)
    out = np.zeros_like(v, dtype=np.float64)
    used = {}
    for j in range(order.shape[1]):
        for bi in np.unique(order[:, j]):
            sel = order[:, j] == bi
            b = cands[bi]
            out[sel] += w[sel, j:j + 1] * apply(maps[b]["A"], maps[b]["t"], v[sel])
            used[b] = used.get(b, 0.0) + float(w[sel, j].sum())
    tot = sum(used.values())
    return out, {b: round(x / tot, 3) for b, x in sorted(used.items(), key=lambda kv: -kv[1])}


def push_off_bones(points: np.ndarray, bone_meshes: list, clearance_mm: float = BONE_PUSH_CLEARANCE_MM):
    """Adapted from scripts/zanatomy/apply_corrections.py's own `_push_off_bones`
    (same interior-point -> nearest-surface-point -> +clearance along the point-to-
    surface RAY method, not the face normal -- see that module for why), against
    a list of already-built trimesh.Trimesh bone meshes instead of loading them
    from a Z-Anatomy npz path."""
    out = points.copy()
    n_pushed = 0
    for mesh in bone_meshes:
        if mesh is None or len(out) == 0:
            continue
        inside = mesh.contains(out)
        if not inside.any():
            continue
        n_pushed += int(inside.sum())
        interior = out[inside]
        closest, _, _ = mesh.nearest.on_surface(interior)
        direction = closest - interior
        length = np.linalg.norm(direction, axis=1, keepdims=True)
        length[length == 0] = 1.0
        pushed = closest + (direction / length) * clearance_mm
        still_in = mesh.contains(pushed)
        if still_in.any():
            pushed[still_in] = closest[still_in] + (direction[still_in] / length[still_in]) * (clearance_mm * 4)
        out[inside] = pushed
    return out, n_pushed


def clip_to_skin_mesh(v: np.ndarray, skin_mesh, iters: int = 16):
    """Mesh-containment equivalent of cross_subject_transfer.py's own NIfTI-based
    `clip_to_skin`: pulls any vertex OUTSIDE the destination specimen's own skin
    mesh back to just inside it, along the ray to this structure's own (already-
    inside) centroid. A raw skin label volume does not necessarily survive a
    container reset; the built skin mesh already sitting in the destination
    bundle always does, so this needs nothing else re-derived.

    Vectorised bisection: every bad vertex's own binary search runs in lock-step
    (one `skin_mesh.contains()` call per ITERATION, over every bad vertex at
    once), not one call per vertex per iteration -- `contains()` is a full
    ray-cast against the whole mesh, so that one change is ~2 orders of
    magnitude fewer calls for a structure with hundreds of bad vertices."""
    if skin_mesh is None or len(v) == 0:
        return v, 0
    ins = skin_mesh.contains(v)
    bad = np.where(~ins)[0]
    if len(bad) == 0:
        return v, 0
    centroid = v[ins].mean(axis=0) if ins.any() else v.mean(axis=0)
    d = v[bad] - centroid
    lo = np.zeros(len(bad)); hi = np.ones(len(bad))
    for _ in range(iters):
        mid = (lo + hi) / 2
        cand = centroid + mid[:, None] * d
        c_ins = skin_mesh.contains(cand)
        lo = np.where(c_ins, mid, lo)
        hi = np.where(c_ins, hi, mid)
    out = v.copy()
    out[bad] = centroid + lo[:, None] * d
    return out, len(bad)


def _bone_universe(dominant: list[str]) -> tuple[set, str]:
    bases = {base_bone(b) for b in dominant}
    if bases & FOREARM_HAND_BASES:
        return FOREARM_HAND_BASES, side_suffix(dominant[0])
    if bases & (FOOT_BASES | LEG_BASES):
        return FOOT_BASES | LEG_BASES, side_suffix(dominant[0])
    return set(), side_suffix(dominant[0]) if dominant else ""


def side_suffix(bone_id: str) -> str:
    return "r" if bone_id.endswith("_r") else "l"


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--direction", choices=["zan2m", "zan2f"], required=True)
    ap.add_argument("--male-html", help="required for zan2m: the male body's own current bundle")
    ap.add_argument("--female-bundle", default="build/viewer_f")
    ap.add_argument("--zanatomy-dir", default=str(zan_source.DEFAULT_ZAN_DIR))
    ap.add_argument("--zanatomy-inventory", default=str(zan_source.DEFAULT_INVENTORY))
    ap.add_argument("--zanatomy-namemap", default=str(zan_source.DEFAULT_NAMEMAP))
    ap.add_argument("--ids", nargs="*", help="restrict to these atlas ids (default: every in-scope id the target lacks)")
    ap.add_argument("--exclude", nargs="*", default=[])
    ap.add_argument("--validate", default=None,
                     help="a bundle dir/html to score the transferred --ids against (their REAL mesh there) "
                          "instead of shipping; writes centroid/volume/Dice per id via "
                          "scripts/zanatomy/validate_registration.py's own compare(). Requires --ids.")
    ap.add_argument("--badge-error-mm", type=float, default=None,
                     help="measured validation median centroid error (mm) to bake into every shipped "
                          "structure's procedural_badge text; omit to leave the badge without a number "
                          "(e.g. for a --validate run, which ships nothing)")
    ap.add_argument("--badge-max-error-mm", type=float, default=None,
                     help="Q150: measured validation MAX centroid error (mm, the worst-case FDP-class "
                          "outlier) to add alongside --badge-error-mm's median -- honesty about the "
                          "worst case, not just the typical one, matters for a clinician reading the "
                          "badge. Ignored if --badge-error-mm is not also given.")
    ap.add_argument("-o", "--out", required=True)
    ap.add_argument("--report", default=None)
    a = ap.parse_args()
    if a.direction == "zan2m" and not a.male_html:
        ap.error("--direction zan2m needs --male-html")
    if a.validate and not a.ids:
        ap.error("--validate needs --ids")

    if a.direction == "zan2m":
        mp = Path(a.male_html)
        bm, blobm = read_bundle_dir(mp) if mp.is_dir() else read_bundle_html(mp)
        dst_all = meshes_by_id(bm, blobm)
    else:
        bf, blobf = read_bundle_dir(a.female_bundle)
        dst_all = meshes_by_id(bf, blobf)
    dst_own = {k: m for k, m in dst_all.items() if not str(m.get("subject", "")).startswith(("xfer_", "zanatomy", "zan_"))}
    dst_own = synth_tarsal_blocks(dst_own)

    src = zan_source.load_source(inventory_path=a.zanatomy_inventory, namemap_path=a.zanatomy_namemap,
                                  zan_dir=a.zanatomy_dir)
    # Z-Anatomy's own matched inventory splits the tarsus the same seven ways (no
    # "Tarsals.r/l" object of its own either) -- synthesise its side of the pair too,
    # or build_bone_maps below would never see a "tarsals_<side>" match on EITHER side.
    src = synth_tarsal_blocks(src)
    src = synth_source_blocks(src, a.zanatomy_dir)
    atlas_records = load_atlas_records()
    maps = build_bone_maps(src, dst_own)

    ids = a.ids or default_ids(src, set(dst_all), atlas_records)
    ids = [i for i in ids if i not in set(a.exclude)]

    import trimesh
    skin_m = dst_all.get("skin")
    skin_mesh = trimesh.Trimesh(skin_m["v"].astype(np.float64), skin_m["f"], process=False) if skin_m else None
    bone_mesh_cache: dict[str, "trimesh.Trimesh | None"] = {}

    def bone_mesh(bone_id):
        if bone_id not in bone_mesh_cache:
            m = dst_own.get(bone_id)
            bone_mesh_cache[bone_id] = trimesh.Trimesh(m["v"].astype(np.float64), m["f"], process=False) if m else None
        return bone_mesh_cache[bone_id]

    verts, faces, structures, report = [], [], [], []
    voff = 0
    skipped = {}
    val_target = None
    if a.validate:
        vp = Path(a.validate)
        bt, blobt = read_bundle_dir(vp) if vp.is_dir() else read_bundle_html(vp)
        val_target = meshes_by_id(bt, blobt)

    for aid in ids:
        m = src.get(aid)
        if m is None:
            skipped[aid] = "no Z-Anatomy source mesh for this id"
            continue
        v = m["v"].astype(np.float64)
        f = m["f"]
        if len(v) < MIN_VERTICES:
            skipped[aid] = f"degenerate source mesh ({len(v)} vertices)"
            continue
        side = side_of(aid, m)
        if side not in ("right", "left"):
            skipped[aid] = "no side on this id -- forearm/hand/foot structures are always one-sided"
            continue
        ss = "r" if side == "right" else "l"
        _, rec = atlas_records.get(aid, (None, None))
        region = (rec or {}).get("region") or (m.get("rec") or {}).get("region")
        dominant = dominant_bones(rec or {}, region, ss)
        if not dominant:
            skipped[aid] = f"no dominant bone could be determined (region={region!r})"
            continue
        nv, used = blend_by_bones(v, maps, dominant)
        if nv is None:
            skipped[aid] = used  # the "no driving bone available" message
            continue
        if skin_mesh is not None and val_target is None:
            frac_outside = float((~skin_mesh.contains(nv)).mean())
            if frac_outside > OUTSIDE_SKIN_REJECT_FRACTION:
                # the per-bone blend put MOST of this structure outside the specimen's own
                # skin -- a sign the fit failed for this particular structure (e.g. a small
                # muscle far from its driving bone's own centroid, where a residual
                # cross-sectional rotation error is amplified into a large lever-arm
                # displacement), not something clip_to_skin_mesh should paper over by
                # collapsing most of the mesh onto the skin surface (or, with NO vertex
                # left inside to anchor a centroid, onto one single degenerate point).
                # Skipped and disclosed rather than shipped broken -- this project's own
                # standing practice (see e.g. ct_vhm_forearm's own "far above expectation,
                # stay unshipped" regions).
                skipped[aid] = (f"per-bone transform put {frac_outside:.0%} of this structure outside the "
                                f"specimen's own skin (driving bones {list(used)}) -- not shipped")
                continue
        universe, _ = _bone_universe(dominant)
        avoid_ids = [f"{b}_{ss}" for b in universe]
        nv, n_pushed = push_off_bones(nv, [bone_mesh(b) for b in avoid_ids])
        nv, n_clipped = clip_to_skin_mesh(nv, skin_mesh)

        if val_target is not None:
            real = val_target.get(aid)
            if real is None or str(real.get("subject", "")).startswith(("xfer_", "zanatomy", "zan_")):
                skipped[aid] = "no real (non-transferred) mesh for this id on the validation target"
                continue
            from scripts.zanatomy.validate_registration import compare  # noqa: E402
            row = {"id": aid, "real_subject": real["subject"], "driving_bones": used,
                   "bone_penetration_vertices_before_pushoff": n_pushed}
            row.update(compare(real["v"].astype(np.float64), real["f"], nv, f))
            report.append(row)
            print(row)
            continue  # validation mode: nothing is shipped

        disp = np.linalg.norm(nv - v, axis=1)
        row = {"atlas_id": aid, "category": m["cat"], "side": side, "region": region,
               "driving_bones": used, "bone_penetration_vertices_before_pushoff": n_pushed,
               "vertices_clipped_to_skin": n_clipped,
               "volume_src_cm3": round(mesh_volume_cm3(v, f), 2), "volume_out_cm3": round(mesh_volume_cm3(nv, f), 2),
               "displacement_mm_median": round(float(np.median(disp)), 1)}
        report.append(row)
        nv32 = nv.astype(np.float32)
        err_txt = ""
        if a.badge_error_mm is not None:
            err_txt = f"; validation median error {a.badge_error_mm:.1f} mm"
            if a.badge_max_error_mm is not None:
                err_txt += f", max {a.badge_max_error_mm:.1f} mm"
        badge = ("Transferred from the Z-Anatomy reference model (CC BY-SA 4.0; Z-Anatomy / BodyParts3D) onto "
                 "this specimen's own bones -- generic shape" + err_txt + ".")
        structures.append({"atlas_id": aid, "source_structure": aid, "side": side,
                            "source_file": f"zanatomy viewer bundle#{aid}",
                            "vertex_offset": voff, "face_offset": sum(len(x) for x in faces),
                            "vertex_count": int(len(nv32)), "triangle_count": int(len(f)),
                            "bbox_min_mm": [round(float(x), 4) for x in nv32.min(axis=0)],
                            "bbox_max_mm": [round(float(x), 4) for x in nv32.max(axis=0)],
                            "procedural_badge": badge,
                            "transfer": {"from": "zanatomy", "driving_bones": used, "method": "per_bone_dominant"}})
        verts.append(nv32); faces.append((f + voff).astype(np.uint32)); voff += len(nv32)

    if val_target is not None:
        rep = {"source": "Q147 validation: scripts/transfer/limb_per_bone_transfer.py --validate. Diagnostics only.",
               "direction": a.direction, "n": len(report), "skipped": skipped, "rows": report}
        if a.report:
            Path(a.report).write_text(json.dumps(rep, indent=1))
            print(f"wrote {a.report}")
        dists = [r["centroid_dist_mm"] for r in report if "centroid_dist_mm" in r]
        if dists:
            print(f"median centroid_dist_mm over {len(dists)} structures: {float(np.median(dists)):.1f}")
        return

    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    V = np.concatenate(verts) if verts else np.zeros((0, 3), np.float32)
    Fc = np.concatenate(faces) if faces else np.zeros((0, 3), np.uint32)
    V.astype(np.float32).tofile(out / "vertices.f32"); Fc.astype(np.uint32).tofile(out / "faces.u32")
    err_note = ""
    if a.badge_error_mm is not None:
        err_note = f" ({a.badge_error_mm:.1f} mm median centroid error"
        if a.badge_max_error_mm is not None:
            err_note += f", {a.badge_max_error_mm:.1f} mm max"
        err_note += ")"
    attribution = [
        "GENERIC MODEL, NOT SEGMENTED FROM THIS SPECIMEN: forearm, hand and foot soft tissue (muscles, tendons, "
        "ligaments, retinacula) from Z-Anatomy (CC BY-SA 4.0), registered onto this specimen's OWN bones one bone "
        "at a time (radius and ulna kept separate to absorb pronation/pose differences; scripts/transfer/"
        "limb_per_bone_transfer.py, Q147) -- not the broader multi-bone spatial blend used elsewhere in this "
        "project. Shipped only for ids this project has no real-data mesh for on this specimen; real geometry "
        "always wins (this subject is listed last). See PROJECT_STATE.md Q147 for the validation table this "
        f"badge's error figure comes from{err_note}.",
        "Z-Anatomy: models by the Z-Anatomy project (BodyParts3D upstream credited in its own LICENSE), app by "
        "Lluis Vinent Juanico -- see third_party/z-anatomy/NOTICE and third_party/z-anatomy/README.md. "
        "Licensed CC BY-SA 4.0; this registered derivative remains CC BY-SA 4.0 (ShareAlike).",
    ]
    manifest = {"subject": out.name, "frame": "atlas: +X right, +Y superior, +Z anterior, millimetres",
                "source_volume": None, "source_kind": "cross-subject transfer zanatomy -> " + ("vhm" if a.direction == "zan2m" else "vhf"),
                "vertex_count": int(len(V)), "triangle_count": int(len(Fc)),
                "bbox_min_mm": [round(float(x), 4) for x in V.min(axis=0)] if len(V) else None,
                "bbox_max_mm": [round(float(x), 4) for x in V.max(axis=0)] if len(V) else None,
                "attribution": attribution, "license": "CC-BY-SA-4.0",
                "bone_maps": {b: {"det": round(mp["det"], 3), "side": mp["side"]} for b, mp in maps.items()},
                "structures": structures}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1))
    rep = {"source": attribution[0] + " " + attribution[1] + " Derived data (scripts/transfer/limb_per_bone_transfer.py).",
           "direction": a.direction, "badge_error_mm": a.badge_error_mm, "badge_max_error_mm": a.badge_max_error_mm, "n": len(report),
           "not_transferred": skipped, "rows": report}
    rp = Path(a.report) if a.report else out / "transfer_report.json"
    rp.write_text(json.dumps(rep, indent=1))
    print(f"{out.name}: {len(structures)} structures, {len(V)} vertices, {len(Fc)} triangles; "
          f"not transferred: {sorted(skipped)}")
    for r in report:
        print(f"  {r['atlas_id']:36s} {r['category']:9s} {r['volume_src_cm3']:7.2f} -> {r['volume_out_cm3']:7.2f} cm3 "
              f"disp {r['displacement_mm_median']:6.1f} mm  pushoff {r['bone_penetration_vertices_before_pushoff']:4d}  "
              f"clipped {r['vertices_clipped_to_skin']:4d}  {list(r['driving_bones'])[:3]}")


if __name__ == "__main__":
    main()
