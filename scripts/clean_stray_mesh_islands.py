#!/usr/bin/env python3
"""Clean spurious stray mesh islands: TotalSegmentator/photograph mislabeled-voxel
noise that survives ingest as a tiny, disconnected fragment floating far from a
structure's real body (Q88, following up on Q87's audit).

Q87 found this is NOT a positioning bug and NOT the documented multi-belly-muscle
pattern (biceps femoris, gastrocnemius, intercostals, interossei, ...): it is a
segmentation-quality defect -- a handful of mislabeled voxels, isolated from the
structure's main mass, that marching cubes turns into its own tiny closed shard.
The flagship example: `ct_vhf`'s `lumbar_vertebrae` carries a 454-vertex/1.8%
fragment 140 mm from its main body. Roughly 150 structure-pieces across both
bodies show the same pattern at similarly small rates.

DETECTION (mesh level, both bodies' currently-shipped geometry): for every
structure piece in every `build/vh/<subject>/manifest.json`, split its mesh into
connected components by FACE adjacency (this session's established method) and
flag any component that is simultaneously:
  - small: <=2% of the piece's vertices, <=1% of its volume, AND <=1.5 cm3
    absolute (chosen because every legitimately-shipped separate muscle belly/
    slip/small intrinsic in this atlas -- e.g. a single lumbrical or interosseous
    -- runs several cm3 or more; a TotalSegmentator noise fleck at this scan
    resolution is a few hundred voxels, well under a cm3), AND
  - far: >=40 mm from the main component's centroid (Q87's own example, and the
    threshold this session's audits already used), AND
  - the piece's main component is still >=95% of it even before dropping
    anything (so a genuinely fragmented structure -- Q78's internal_oblique/
    transversus_abdominis at 44-49% largest -- is never touched: it fails this
    gate and is left alone, logged separately).
A structure whose name matches a KNOWN_MULTIPIECE keyword (documented
multi-bellied muscles, tendons, retinacula -- anywhere a real second piece is
anatomically expected) or whose subject is a runtime cross-subject transfer
with no committed source volume is still scanned but classified as
skip_known_multipiece / skip_no_durable_source for manual review rather than
cleaned automatically, per the task's own conservative instruction.

TWO WAYS TO APPLY A FIX, in order of preference:
  1. volume  -- when the structure's committed source .nii.gz and the exact
     recipe (labels key, origin, smoothing) used to convert it are known (see
     SUBJECT_RECIPES below, read off `scripts/vhm_rebuild_bundle.sh` /
     `scripts/cryo/vhf_rebuild_bundle.sh`), the same stray voxels are located
     in 3-D (scipy.ndimage.label, 26-connectivity) and zeroed in the label
     volume itself, which is then re-surfaced with the project's own
     `ingest_volume_geometry.py convert`. This is durable: a future from-
     scratch rebuild reproduces the clean mesh because the fix lives in the
     committed source, not just in `build/`.
  2. mesh    -- otherwise, the flagged component's vertices/faces are removed
     directly from `build/vh/<subject>/{vertices.f32,faces.u32,manifest.json}`
     (rewriting offsets for every structure in the file). This always works
     and is what actually ships (export_viewer_bundle.py reads build/vh
     directly), but is NOT durable across a from-scratch rebuild if the
     subject's source volume is unavailable or not wired into a rebuild
     script -- the same class of limitation already documented for Q71/72/78.

Usage:
    python3 scripts/clean_stray_mesh_islands.py scan [--out REPORT.json]
    python3 scripts/clean_stray_mesh_islands.py apply --subject ct_vhf --all
    python3 scripts/clean_stray_mesh_islands.py apply --subject ct_vhf --atlas-id lumbar_vertebrae
    python3 scripts/clean_stray_mesh_islands.py verify --subject ct_vhf
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))
BUILD_DIR = REPO_ROOT / "build" / "vh"

# --------------------------------------------------------------------------
# thresholds -- see module docstring for why these numbers
# --------------------------------------------------------------------------
MIN_MAIN_FRAC = 0.95        # the piece must already be overwhelmingly one body
MAX_COMPONENT_VERT_FRAC = 0.02
MAX_COMPONENT_VOL_FRAC = 0.01
MAX_COMPONENT_VOL_MM3 = 1500.0   # 1.5 cm3
MIN_DIST_MM = 40.0
MAX_DROP_COMPONENTS = 3
MAX_TOTAL_DROP_VERT_FRAC = 0.02

# Documented multi-piece-by-anatomy muscles/tendons/retinacula (Q76-Q81's own
# fragmentation work, plus standard anatomy): a real second piece is expected
# here, so these are scanned but never auto-cleaned.
KNOWN_MULTIPIECE_KEYWORDS = (
    "biceps_femoris", "gastrocnemius", "pectoralis", "serratus", "digastric",
    "intercostal", "interosse", "lumbrical", "flexor_digitorum",
    "extensor_digitorum", "extensor_hallucis", "flexor_hallucis",
    "adductor_magnus", "triceps", "biceps_brachii", "multifidus", "scalenus",
    "scalene", "rhomboid", "trapezius", "retinaculum", "tendon",
    "sternocleidomastoid", "omohyoid", "sternohyoid", "constrictor",
    "levator_costarum",
)

# Subjects with no committed label volume behind the currently-shipped mesh at
# all (pure runtime cross-subject transfer, or male subjects recovered from the
# decimated vhm_v25 bundle because their own full-resolution source was lost --
# see Q71/72/78/81): mesh-level fix only, never volume-level.
NO_DURABLE_SOURCE_SUBJECTS = {
    "xfer_vhm2vhf", "xfer_vhf2vhm", "xfer_vhf2vhm_neck",
    "vhm_both", "ct_vhm", "ct_vhm_abd", "ct_vhm_abw", "ct_s1159", "ct_s1159_abd",
    "ct_vhm_head", "ct_vhm_headm", "ct_vhm_orbit", "ct_vhm_neckbv", "ct_vhm_skin",
}

# subject -> (committed .nii.gz relative to repo root, labels key, origin "x,y,z", smooth)
# Read directly off scripts/vhm_rebuild_bundle.sh and scripts/cryo/vhf_rebuild_bundle.sh
# (the project's own idempotent rebuild recipes), not re-derived.
T = "data/ct_sources/task_outputs"
_VHM_ORIGIN = "-6.035,-895.476,4.787"   # male torso-block frame
SUBJECT_RECIPES = {
    "ct_vhf": (f"{T}/vhf_total.nii.gz", "totalsegmentator", None, 1.0),
    "ct_vhf_abd": (f"{T}/vhf_abdominal_muscles.nii.gz", "totalsegmentator_abdominal_muscles", None, 1.0),
    "ct_vhf_legs": (f"{T}/vhf_lower_limb_bones.nii.gz", "vhf_legs", None, 1.0),
    "ct_vhf_shsp": (f"{T}/vhf_shoulder_split_cryo.nii.gz", "vhf_shoulder_split", None, 1.0),
    "ct_vhf_forearm": (f"{T}/vhf_forearm_muscles_cryo.nii.gz", "vhf_forearm_muscles", None, 1.0),
    "ct_vhf_cuff": (f"{T}/vhf_rotator_cuff_cryo.nii.gz", "vhf_rotator_cuff", None, 1.0),
    "ct_vhf_es": (f"{T}/vhf_erector_columns.nii.gz", "vhf_erector", None, 1.0),
    "ct_vhf_dneck": (f"{T}/vhf_deep_neck_cryo.nii.gz", "vhf_deep_neck", None, 1.0),
    "ct_vhf_delt": (f"{T}/vhf_deltoid_cryo.nii.gz", "vhf_deltoid", None, 1.0),
    "ct_vhf_pfloor": (f"{T}/vhf_pelvic_floor_cryo.nii.gz", "vhf_pelvic_floor", None, 1.0),
    "ct_vhf_hyoid": (f"{T}/vhf_hyoid_muscles_cryo.nii.gz", "vhf_hyoid_muscles", None, 1.0),
    "ct_vhf_armb": (f"{T}/vhf_arm_bones_ct.nii.gz", "vhf_arm_bones", None, 1.0),
    "ct_vhf_neck": (f"{T}/vhf_headneck_muscles_merged.nii.gz", "totalsegmentator_headneck_muscles", None, 1.0),
    "ct_vhf_neckbv": (f"{T}/vhf_headneck_bones_vessels.nii.gz", "totalsegmentator_headneck_bones_vessels", None, 1.0),
    "ct_vhf_headm": (f"{T}/vhf_head_muscles.nii.gz", "totalsegmentator_head_muscles", None, 1.0),
    "ct_vhf_head": (f"{T}/vhf_craniofacial_structures.nii.gz", "totalsegmentator_craniofacial_structures", None, 1.0),
    "xfer_vhm2vhf_sep": (f"{T}/vhf_xfer_lowerlimb_septa.nii.gz", "vhf_xfer_septa", None, 1.0),
    "ct_vhm_shsp": (f"{T}/vhm_shoulder_split_cryo.nii.gz", "vhm_shoulder_split", _VHM_ORIGIN, 1.0),
    "ct_vhm_forearm": (f"{T}/vhm_forearm_muscles_cryo.nii.gz", "vhm_forearm_muscles", _VHM_ORIGIN, 1.0),
    "ct_vhm_armm": (f"{T}/vhm_arm_muscles_cryo_v2.nii.gz", "vhm_arm_muscles", _VHM_ORIGIN, 1.0),
    "ct_vhm_neck": (f"{T}/vhm_headneck_muscles_merged.nii.gz", "totalsegmentator_headneck_muscles", _VHM_ORIGIN, 1.0),
    "ct_vhm_twall": (f"{T}/vhm_trunk_wall.nii.gz", "vhm_trunk_wall", _VHM_ORIGIN, 1.0),
    "ct_vhm_foot": (f"{T}/vhm_foot_bones.nii.gz", "vhm_foot", "-8.755,-202.476,5.677", 1.0),
    "ct_vhm_cuff": (f"{T}/vhm_rotator_cuff_cryo.nii.gz", "vhm_rotator_cuff", _VHM_ORIGIN, 1.0),
    "ct_vhm_delt": (f"{T}/vhm_deltoid_cryo.nii.gz", "vhm_deltoid", _VHM_ORIGIN, 1.0),
    "ct_vhm_pmr": (f"{T}/vhm_pecminor_rhomboids_cryo.nii.gz", "vhm_pecminor_rhomboids", _VHM_ORIGIN, 1.0),
    "ct_vhm_es": (f"{T}/vhm_erector_columns.nii.gz", "vhm_erector", _VHM_ORIGIN, 1.0),
    "ct_vhm_arm": (f"{T}/vhm_arm_bones_cryo_completed.nii.gz", "vhm_arm_bones", _VHM_ORIGIN, 1.0),
}
_FEMALE_ORIGIN_CACHE = None


def female_origin() -> str:
    """The female torso-block origin, recovered the same way vhf_rebuild_bundle.sh
    does it: fit the femoral heads in her own total-segmentation volume. Cached
    because it is the same fit every time and `inspect` is not free."""
    global _FEMALE_ORIGIN_CACHE
    if _FEMALE_ORIGIN_CACHE is not None:
        return _FEMALE_ORIGIN_CACHE
    out = subprocess.run(
        [sys.executable, "scripts/ingest_volume_geometry.py", "inspect",
         f"{T}/vhf_total.nii.gz", "--labels", "totalsegmentator"],
        cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("--origin"):
            _FEMALE_ORIGIN_CACHE = line.split("'")[1]
            return _FEMALE_ORIGIN_CACHE
    raise SystemExit("could not recover the female atlas origin from `inspect`")


def recipe_for(subject: str):
    r = SUBJECT_RECIPES.get(subject)
    if r is None:
        return None
    path, labels, origin, smooth = r
    if origin is None:
        origin = female_origin()
    return (REPO_ROOT / path), labels, origin, smooth


# --------------------------------------------------------------------------
# mesh-level connected-component analysis (shared by scan and both apply modes)
# --------------------------------------------------------------------------

def face_adjacency_labels(nv: int, faces: np.ndarray):
    e0 = np.r_[faces[:, 0], faces[:, 1], faces[:, 2]]
    e1 = np.r_[faces[:, 1], faces[:, 2], faces[:, 0]]
    g = coo_matrix((np.ones(len(e0), dtype=np.int8), (e0, e1)), shape=(nv, nv))
    n_comp, labels = connected_components(g, directed=False)
    return n_comp, labels


def mesh_volume_mm3(v: np.ndarray, f: np.ndarray) -> float:
    if len(f) == 0:
        return 0.0
    a, b, c = v[f[:, 0]], v[f[:, 1]], v[f[:, 2]]
    return abs(float(np.einsum("ij,ij->i", a, np.cross(b, c)).sum()) / 6.0)


def analyze_piece(v: np.ndarray, f: np.ndarray):
    """None if the piece is one component; else a dict of per-component stats
    plus the raw per-vertex `labels` array so a caller can build a keep-mask."""
    n_comp, labels = face_adjacency_labels(len(v), f)
    if n_comp <= 1:
        return None
    sizes = np.bincount(labels, minlength=n_comp)
    order = np.argsort(sizes)[::-1]
    main = int(order[0])
    main_centroid = v[labels == main].mean(axis=0)
    total_vol = mesh_volume_mm3(v, f)
    comps = []
    for c in order:
        vmask = labels == c
        fmask = labels[f[:, 0]] == c
        comps.append(dict(
            id=int(c), size=int(sizes[c]), vert_frac=float(sizes[c] / len(v)),
            centroid=v[vmask].mean(axis=0).tolist(),
            dist_from_main_mm=float(np.linalg.norm(v[vmask].mean(axis=0) - main_centroid)),
            volume_mm3=mesh_volume_mm3(v, f[fmask]),
        ))
    return dict(main_id=main, main_frac=float(sizes[main] / len(v)),
                total_vertices=int(len(v)), total_volume_mm3=total_vol,
                components=comps, labels=labels)


def is_known_multipiece(atlas_id: str) -> bool:
    low = atlas_id.lower()
    return any(k in low for k in KNOWN_MULTIPIECE_KEYWORDS)


def decide_drops(info: dict):
    """Component ids to remove, or [] if this piece should not be touched."""
    if info["main_frac"] < MIN_MAIN_FRAC:
        return []
    total_vol = info["total_volume_mm3"] or 1.0
    candidates = [c for c in info["components"] if c["id"] != info["main_id"]]
    drops = []
    for c in sorted(candidates, key=lambda c: c["size"]):
        if (c["vert_frac"] <= MAX_COMPONENT_VERT_FRAC
                and c["volume_mm3"] <= MAX_COMPONENT_VOL_MM3
                and (c["volume_mm3"] / total_vol) <= MAX_COMPONENT_VOL_FRAC
                and c["dist_from_main_mm"] >= MIN_DIST_MM):
            drops.append(c)
    if not drops:
        return []
    total_drop_frac = sum(c["vert_frac"] for c in drops)
    if len(drops) > MAX_DROP_COMPONENTS or total_drop_frac > MAX_TOTAL_DROP_VERT_FRAC:
        return []
    # anything left un-flagged among the non-main components (too big/close/etc)
    # means this piece isn't cleanly "one body + tiny specks" -- be conservative
    # and skip the whole piece rather than partially clean it.
    if len(drops) != len(candidates):
        return []
    return [c["id"] for c in drops]


# --------------------------------------------------------------------------
# scan
# --------------------------------------------------------------------------

def load_subject_mesh(subject_dir: Path):
    manifest = json.loads((subject_dir / "manifest.json").read_text())
    verts = np.fromfile(subject_dir / "vertices.f32", dtype="<f4").reshape(-1, 3)
    faces = np.fromfile(subject_dir / "faces.u32", dtype="<u4").reshape(-1, 3)
    return manifest, verts, faces


def scan_all():
    results = []
    for subj_dir in sorted(BUILD_DIR.iterdir()):
        if not (subj_dir / "manifest.json").is_file():
            continue
        subject = subj_dir.name
        manifest, verts, faces = load_subject_mesh(subj_dir)
        for s in manifest["structures"]:
            vo, vc = s["vertex_offset"], s["vertex_count"]
            fo, fc = s["face_offset"], s["triangle_count"]
            v = verts[vo:vo + vc]
            f = faces[fo:fo + fc] - vo
            if fc == 0 or f.min() < 0 or f.max() >= vc:
                continue
            info = analyze_piece(v, f)
            if info is None:
                continue
            drops = decide_drops(info)
            atlas_id = s["atlas_id"]
            if not drops:
                # still worth recording if it *would* have qualified at the
                # wider Q87 audit thresholds, for the follow-up list
                status = "skip_no_clean_drop"
            elif is_known_multipiece(atlas_id):
                status = "skip_known_multipiece"
            elif subject in SUBJECT_RECIPES and subject not in NO_DURABLE_SOURCE_SUBJECTS:
                status = "clean_durable"
            else:
                status = "clean_mesh_only"
            drop_info = [c for c in info["components"] if c["id"] in drops]
            results.append(dict(
                subject=subject, atlas_id=atlas_id, side=s.get("side"),
                source_file=s.get("source_file"), status=status,
                total_vertices=info["total_vertices"],
                total_volume_mm3=round(info["total_volume_mm3"], 2),
                main_frac=round(info["main_frac"], 4),
                n_components=len(info["components"]),
                drops=[dict(size=c["size"], vert_frac=round(c["vert_frac"], 5),
                            volume_mm3=round(c["volume_mm3"], 3),
                            dist_from_main_mm=round(c["dist_from_main_mm"], 1))
                       for c in drop_info],
            ))
    return results


def cmd_scan(args):
    results = scan_all()
    by_status = {}
    for r in results:
        by_status.setdefault(r["status"], []).append(r)
    for status, items in sorted(by_status.items()):
        print(f"{status:24s} {len(items)}")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(results, indent=2))
    print(f"\nwrote {out} ({len(results)} structure-pieces with >1 component)")
    return 0


# --------------------------------------------------------------------------
# apply -- mesh level (always works; not durable unless volume-level also ran)
# --------------------------------------------------------------------------

def apply_mesh_fix(subject: str, atlas_ids, verbose=True):
    """Remove the flagged stray component(s) for the given atlas_ids (or every
    clean-able structure in the subject when atlas_ids is None) directly from
    build/vh/<subject>. Rewrites the whole subject (offsets shift). Returns a
    list of removal records."""
    subj_dir = BUILD_DIR / subject
    manifest, verts, faces = load_subject_mesh(subj_dir)
    wanted = set(atlas_ids) if atlas_ids else None

    out_structs = []
    v_blocks, f_blocks = [], []
    vbase = fbase = 0
    removals = []
    for s in manifest["structures"]:
        vo, vc = s["vertex_offset"], s["vertex_count"]
        fo, fc = s["face_offset"], s["triangle_count"]
        v = verts[vo:vo + vc]
        f_local = faces[fo:fo + fc] - vo
        atlas_id = s["atlas_id"]
        new_v, new_f = v, f_local
        if (wanted is None or atlas_id in wanted) and fc > 0:
            info = analyze_piece(v, f_local)
            if info is not None:
                drops = decide_drops(info)
                if drops and not is_known_multipiece(atlas_id):
                    labels = info["labels"]
                    keep_vmask = ~np.isin(labels, drops)
                    old_to_new = -np.ones(len(v), dtype=np.int64)
                    old_to_new[keep_vmask] = np.arange(int(keep_vmask.sum()))
                    keep_fmask = keep_vmask[f_local[:, 0]]  # a face's verts share one component
                    new_v = v[keep_vmask]
                    new_f = old_to_new[f_local[keep_fmask]]
                    dropped = [c for c in info["components"] if c["id"] in drops]
                    removals.append(dict(
                        subject=subject, atlas_id=atlas_id, side=s.get("side"),
                        before_vertices=int(len(v)), after_vertices=int(len(new_v)),
                        before_volume_mm3=round(info["total_volume_mm3"], 2),
                        removed_volume_mm3=round(sum(c["volume_mm3"] for c in dropped), 3),
                        removed_components=[dict(
                            size=c["size"], vert_frac=round(c["vert_frac"], 5),
                            volume_mm3=round(c["volume_mm3"], 3),
                            dist_from_main_mm=round(c["dist_from_main_mm"], 1))
                            for c in dropped],
                    ))
                    if verbose:
                        print(f"  {subject}/{atlas_id}: removed {len(dropped)} component(s), "
                              f"{len(v) - len(new_v)} verts, "
                              f"{sum(c['volume_mm3'] for c in dropped) / 1000:.3f} cm3 "
                              f"of {info['total_volume_mm3'] / 1000:.2f} cm3")
        rec = dict(s)
        rec["vertex_offset"] = vbase
        rec["face_offset"] = fbase
        rec["vertex_count"] = int(len(new_v))
        rec["triangle_count"] = int(len(new_f))
        if len(new_v):
            rec["bbox_min_mm"] = [round(float(x), 4) for x in new_v.min(axis=0)]
            rec["bbox_max_mm"] = [round(float(x), 4) for x in new_v.max(axis=0)]
        out_structs.append(rec)
        v_blocks.append(new_v.astype(np.float32))
        f_blocks.append((new_f + vbase).astype(np.uint32))
        vbase += len(new_v)
        fbase += len(new_f)

    if not removals:
        if verbose:
            print(f"  {subject}: nothing to change")
        return removals

    all_v = np.concatenate(v_blocks) if v_blocks else np.zeros((0, 3), np.float32)
    all_f = np.concatenate(f_blocks) if f_blocks else np.zeros((0, 3), np.uint32)
    (subj_dir / "vertices.f32").write_bytes(all_v.tobytes())
    (subj_dir / "faces.u32").write_bytes(all_f.tobytes())
    manifest["structures"] = out_structs
    manifest["vertex_count"] = int(len(all_v))
    manifest["triangle_count"] = int(len(all_f))
    if len(all_v):
        manifest["bbox_min_mm"] = [round(float(x), 4) for x in all_v.min(axis=0)]
        manifest["bbox_max_mm"] = [round(float(x), 4) for x in all_v.max(axis=0)]
    (subj_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return removals


# --------------------------------------------------------------------------
# apply -- label-volume level (durable) + reconvert
# --------------------------------------------------------------------------

def voxel_components_for_label(volume: np.ndarray, label: int, affine: np.ndarray):
    """3-D 26-connectivity components of one label's mask, in mm."""
    from scipy import ndimage
    mask = volume == label
    if not mask.any():
        return None
    structure = np.ones((3, 3, 3), dtype=np.uint8)
    lab_vol, n = ndimage.label(mask, structure=structure)
    if n <= 1:
        return None
    voxel_mm3 = abs(float(np.linalg.det(affine[:3, :3])))
    sizes = ndimage.sum(np.ones_like(lab_vol), lab_vol, index=range(1, n + 1))
    order = np.argsort(sizes)[::-1] + 1  # component ids, largest first
    main = int(order[0])
    main_ijk = np.array(ndimage.center_of_mass(mask, lab_vol, main))
    main_mm = (affine @ np.r_[main_ijk, 1.0])[:3]
    comps = []
    for cid in order:
        ijk = np.array(ndimage.center_of_mass(mask, lab_vol, int(cid)))
        mm = (affine @ np.r_[ijk, 1.0])[:3]
        size = int(sizes[int(cid) - 1])
        comps.append(dict(id=int(cid), size=size, volume_mm3=size * voxel_mm3,
                           dist_from_main_mm=float(np.linalg.norm(mm - main_mm))))
    total_vox = int(mask.sum())
    return dict(main_id=main, main_frac=comps[0]["size"] / total_vox,
                total_voxels=total_vox, total_volume_mm3=total_vox * voxel_mm3,
                components=comps, label_volume=lab_vol)


def decide_voxel_drops(info: dict):
    total_vol = info["total_volume_mm3"] or 1.0
    if info["main_frac"] < MIN_MAIN_FRAC:
        return []
    candidates = [c for c in info["components"] if c["id"] != info["main_id"]]
    drops = []
    for c in sorted(candidates, key=lambda c: c["size"]):
        frac = c["size"] / info["total_voxels"]
        if (frac <= MAX_COMPONENT_VERT_FRAC
                and c["volume_mm3"] <= MAX_COMPONENT_VOL_MM3
                and (c["volume_mm3"] / total_vol) <= MAX_COMPONENT_VOL_FRAC
                and c["dist_from_main_mm"] >= MIN_DIST_MM):
            drops.append(c)
    if not drops or len(drops) != len(candidates):
        return []
    if len(drops) > MAX_DROP_COMPONENTS:
        return []
    return drops


def labels_present_for_atlas_id(manifest, atlas_id, side):
    """The integer label id(s) in the source volume behind this manifest
    structure, read off its own recorded `source_file` ("name.nii.gz#12")."""
    out = []
    for s in manifest["structures"]:
        if s["atlas_id"] == atlas_id and s.get("side") == side:
            sf = s.get("source_file", "")
            if "#" in sf:
                tail = sf.rsplit("#", 1)[1]
                if tail.isdigit():
                    out.append(int(tail))
    return out


def apply_volume_fix(subject: str, atlas_ids=None, dry_run=False, verbose=True):
    """Clean the committed label volume behind `subject`, then reconvert via
    the project's own ingest_volume_geometry.py so build/vh/<subject> is
    regenerated from the cleaned source (not just vertex surgery)."""
    import nibabel as nib

    recipe = recipe_for(subject)
    if recipe is None:
        raise SystemExit(f"no known recipe for {subject}; use apply-mesh instead")
    vol_path, labels_key, origin, smooth = recipe
    if not vol_path.is_file():
        raise SystemExit(f"{vol_path} not found on disk")

    subj_dir = BUILD_DIR / subject
    manifest = json.loads((subj_dir / "manifest.json").read_text())
    wanted = set(atlas_ids) if atlas_ids else {s["atlas_id"] for s in manifest["structures"]}

    img = nib.load(str(vol_path))
    data = np.asarray(img.dataobj)
    affine = np.asarray(img.affine, dtype=float)
    data = np.round(data).astype(np.int32) if not np.issubdtype(data.dtype, np.integer) else data.astype(np.int32)

    label_ids = set()
    for s in manifest["structures"]:
        if s["atlas_id"] in wanted:
            label_ids.update(labels_present_for_atlas_id(manifest, s["atlas_id"], s.get("side")))

    removals = []
    changed = False
    for label in sorted(label_ids):
        info = voxel_components_for_label(data, label, affine)
        if info is None:
            continue
        drops = decide_voxel_drops(info)
        if not drops:
            continue
        lab_vol = info["label_volume"]
        drop_ids = {c["id"] for c in drops}
        zero_mask = np.isin(lab_vol, list(drop_ids))
        n_before = int((data == label).sum())
        if not dry_run:
            data[zero_mask] = 0
        changed = True
        removals.append(dict(
            subject=subject, label=int(label), voxels_before=n_before,
            voxels_removed=int(zero_mask.sum()),
            volume_removed_mm3=round(sum(c["volume_mm3"] for c in drops), 3),
            total_volume_mm3=round(info["total_volume_mm3"], 3),
            components_removed=[dict(size=c["size"], dist_from_main_mm=round(c["dist_from_main_mm"], 1))
                                 for c in drops],
        ))
        if verbose:
            print(f"  {subject}: label {label}: removed {len(drops)} voxel-component(s), "
                  f"{zero_mask.sum()}/{n_before} voxels, "
                  f"{sum(c['volume_mm3'] for c in drops) / 1000:.4f} of "
                  f"{info['total_volume_mm3'] / 1000:.2f} cm3")

    if not changed:
        if verbose:
            print(f"  {subject}: no label-volume-level drops found")
        return removals
    if dry_run:
        return removals

    nib.save(nib.Nifti1Image(data, affine, img.header), str(vol_path))

    mapping_src = REPO_ROOT / "mappings" / "subjects" / f"{subject}_volume_mapping.json"
    mapping_dst = BUILD_DIR / f"{subject}_volume_mapping.json"
    if mapping_src.is_file():
        shutil.copy(mapping_src, mapping_dst)
    if not mapping_dst.is_file():
        raise SystemExit(f"no mapping at {mapping_dst}; cannot reconvert {subject}")

    cmd = [sys.executable, "scripts/ingest_volume_geometry.py", "convert", str(vol_path),
           "--labels", labels_key, "--subject", subject, "--origin", origin,
           "--smooth", str(smooth)]
    if verbose:
        print("  " + " ".join(cmd))
    subprocess.run(cmd, cwd=REPO_ROOT, check=True)
    return removals


# --------------------------------------------------------------------------
# verify
# --------------------------------------------------------------------------

def cmd_verify(args):
    subj_dir = BUILD_DIR / args.subject
    manifest, verts, faces = load_subject_mesh(subj_dir)
    for s in manifest["structures"]:
        if args.atlas_id and s["atlas_id"] != args.atlas_id:
            continue
        vo, vc = s["vertex_offset"], s["vertex_count"]
        fo, fc = s["face_offset"], s["triangle_count"]
        v = verts[vo:vo + vc]
        f = faces[fo:fo + fc] - vo
        if fc == 0:
            continue
        info = analyze_piece(v, f)
        if info is None:
            print(f"{s['atlas_id']:35s} side={str(s.get('side')):6s} 1 component (100.0%)")
        else:
            print(f"{s['atlas_id']:35s} side={str(s.get('side')):6s} "
                  f"{info['main_frac']*100:5.1f}% main, {len(info['components'])} components")
    return 0


# --------------------------------------------------------------------------
# apply (CLI)
# --------------------------------------------------------------------------

def cmd_apply(args):
    scan_report = json.loads(Path(args.scan).read_text()) if Path(args.scan).is_file() else scan_all()
    items = [r for r in scan_report if r["subject"] == args.subject]
    if args.atlas_id:
        items = [r for r in items if r["atlas_id"] == args.atlas_id]
    items = [r for r in items if r["status"] in ("clean_durable", "clean_mesh_only")]
    if not items:
        print("nothing to apply")
        return 0
    atlas_ids = sorted({r["atlas_id"] for r in items})
    use_volume = (not args.mesh_only) and args.subject in SUBJECT_RECIPES
    removals = []
    if use_volume:
        removals = apply_volume_fix(args.subject, atlas_ids, dry_run=args.dry_run)
        # reconvert regenerates build/vh/<subject> wholesale, which supersedes
        # any previous mesh-only patch -- nothing further to do at mesh level.
    else:
        if not args.dry_run:
            removals = apply_mesh_fix(args.subject, atlas_ids)
        else:
            print(f"(dry run) would mesh-clean {args.subject}: {atlas_ids}")
    if removals and args.report:
        out = Path(args.report)
        prior = json.loads(out.read_text()) if out.is_file() else []
        prior.extend(removals)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(prior, indent=2))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_scan = sub.add_parser("scan")
    p_scan.add_argument("--out", default="data/derived/stray_mesh_islands_scan.json")
    p_scan.set_defaults(fn=cmd_scan)

    p_apply = sub.add_parser("apply")
    p_apply.add_argument("--subject", required=True)
    p_apply.add_argument("--atlas-id", default=None)
    p_apply.add_argument("--all", action="store_true", help="(kept for readability; default is all flagged in the subject)")
    p_apply.add_argument("--mesh-only", action="store_true", help="skip the durable volume-level path even if a recipe is known")
    p_apply.add_argument("--dry-run", action="store_true")
    p_apply.add_argument("--scan", default="data/derived/stray_mesh_islands_scan.json")
    p_apply.add_argument("--report", default="data/derived/stray_mesh_islands_report.json")
    p_apply.set_defaults(fn=cmd_apply)

    p_verify = sub.add_parser("verify")
    p_verify.add_argument("--subject", required=True)
    p_verify.add_argument("--atlas-id", default=None)
    p_verify.set_defaults(fn=cmd_verify)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
