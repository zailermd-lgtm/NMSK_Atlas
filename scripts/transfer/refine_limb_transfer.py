"""Q150/Q150b: refine Q147's Z-Anatomy forearm/hand transfer to each specimen's OWN
segmented muscle tissue, the same idea as Q48's refine_transfer_to_septa.py but
on VOLUMETRIC LABELS instead of raw cryosection crops.

WHY NOT CROPS. Q48's method needs a fascial-ridge texture (white top-hat of the
photograph brightness) to place a boundary between two neighbouring bellies.
The full-resolution crops that texture comes from (SCRATCH/vh_cryo_f,
SCRATCH/vh_cryo_m_fa, .../hand -- everything scripts/cryo/*forearm*.py and
vhf_hand_muscles_from_cryo.py read via --crops) did NOT survive the container
reset (checked: no SCRATCH/ or *cryo_frame* path exists anywhere on this
container) and cannot be re-fetched (same denied-hosts network policy noted
throughout this project for the DU/IDC sources). Per this task's own stated
fallback, this script uses the CT/muscle-mass volumes those crop-based scripts
ALREADY PRODUCED and committed to data/ct_sources/task_outputs/ (
vhm_forearm_muscles_cryo.nii.gz, vhf_forearm_muscles_cryo.nii.gz,
vhf_hand_muscles_cryo.nii.gz) -- REAL, non-transferred segmentations of this
specimen's own tissue, already reviewed once (mappings/*_labels.json's
"merged_compartments", each subject's own *_volume_mapping.json "candidates").

METHOD (shipping). For each of these volumes, every label is either:
  - a GROUND-TRUTH single muscle (the subject's own volume_mapping.json sets
    its atlas_id) -- already shipped as real geometry (ct_vh{m,f}_forearm/
    ct_vhf_hand); untouched here, a hard constraint on everything else (never
    entered into any competitive region below).
  - an OPEN label (atlas_id null) -- a compartment the cryo rule could not
    split ("status": "no_atlas_entity"), or an individually-named region that
    volume review REJECTED as unreliable on its own ("status": "review" --
    typically an oversized rule artefact that swallowed a neighbour's belly,
    see the label's own "note") -- with one or more "candidates" (the atlas
    ids that could be inside it; already curated by that review, reused
    verbatim here).

Every open label's own real tissue extent is partitioned among its own
candidates by `partition_region()`: NEAREST-TRANSFERRED-SEED competition
(each candidate's Q147 per-bone-transferred mesh, voxelised and eroded ~2mm,
a Euclidean-distance Voronoi via scipy distance_transform_edt -- there is no
grayscale texture left to watershed on, so this is the geometric substitute
the task's own fallback anticipates), each candidate's final claim clipped to
within MAX_MOVE_MM of its OWN (uneroded) transferred mask (Q48's "a muscle
may not move more than its own transfer" rule) and, at shipping time, to at
least MIN_SHIP_VOL_FRACTION of Q147's own volume (a smaller claim means the
seed barely reached the real tissue -- kept as Q147, disclosed, not shipped
as a sliver). The ONE exception, never run through partition_region: a
"no_atlas_entity" label with exactly one candidate is handed the whole blob
outright -- the reviewer's own considered judgement that this whole blob is
(at least) all of `candidates` together, not something this script need
re-derive from a seed. A "review"-status label, even with one candidate,
gets NO such free pass (see the Q150 fix below) -- it must reach through
partition_region like everything else.

VALIDATION (Q150b -- leave-one-out, same design intent as Q147/Q48, FIXED
after a lead review caught a leak in the first Q150 cut): --holdout ID [ID
...] scores how well this method could have recovered each named real
muscle's own shape if it did not already have one, WITHOUT ever using that
muscle's own true footprint as "the region" to search within (the original
bug: an id with only one candidate -- itself -- was searched for inside its
OWN already-known true label, so the answer was read back out of the ground
truth it was being scored against; every held-out id happened to be exactly
this single-candidate case, which is why it scored ~1mm). Two variants, both
built on partition_region() (never a free pass, regardless of candidate
count):
  - "neighbor" (--holdout-mode neighbor, the default): the competitive region
    is the held-out id's own true label UNION every other real label that
    touches it within NEIGHBOUR_DILATE_MM (both other single ground-truth
    muscles and other open compartments) -- their OWN true voxels are ALSO
    thrown into the open, contested pool (not kept fixed), and every
    candidate (the held-out id plus every neighbour's own candidate(s)) is
    seeded ONLY by its own Q147 transferred mesh, never its true shape. Only
    the held-out id's own resulting claim is scored.
  - "whole_limb" (--holdout-mode whole_limb): the harshest variant -- the
    competitive region is EVERY labelled voxel in the whole volume (the
    entire forearm or hand segment), candidates are every real+candidate
    atlas id this volume's mapping names at all, run ONCE per volume (shared
    across every held-out id, since the setup is identical), then each
    held-out id's own claim is scored. Simulates recovering this one
        muscle's shape with NO boundary information anywhere in the segment,
    only bone-driven transfer position.
Both variants are reported; ship/no-ship is decided on these, never on the
leaked numbers the first Q150 cut produced.

    # validation (neighbor + whole_limb, both reported)
    python3 scripts/transfer/refine_limb_transfer.py --direction zan2m \
        --target build/viewer_m --xfer build/vh/xfer_zan2vhm_limb \
        --volume data/ct_sources/task_outputs/vhm_forearm_muscles_cryo.nii.gz \
            --labels mappings/vhm_forearm_muscles_labels.json \
            --mapping build/vh/ct_vhm_forearm_volume_mapping.json --origin=-6.035,-895.476,4.787 \
        --holdout flexor_digitorum_superficialis_r flexor_digitorum_profundus_r abductor_pollicis_longus_r \
        --report data/derived/Q150_validation_male.json

    # shipping (no --holdout)
    python3 scripts/transfer/refine_limb_transfer.py --direction zan2m \
        --target build/viewer_m --xfer build/vh/xfer_zan2vhm_limb \
        --volume data/ct_sources/task_outputs/vhm_forearm_muscles_cryo.nii.gz \
            --labels mappings/vhm_forearm_muscles_labels.json \
            --mapping build/vh/ct_vhm_forearm_volume_mapping.json --origin=-6.035,-895.476,4.787 \
        --badge-median-mm 11.2 --badge-max-mm 24.8 \
        -o build/vh/xfer_zan2vhm_limb_refined --report data/derived/refine_report_zan2vhm_limb.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import nibabel as nib
import trimesh
from scipy import ndimage as ndi

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.transfer.bundle_io import read_bundle_dir, read_bundle_html, meshes_by_id, mesh_volume_cm3  # noqa: E402
from engine import volume_ingest as vol  # noqa: E402
from scripts.transfer.limb_per_bone_transfer import (  # noqa: E402
    build_bone_maps, blend_by_bones, push_off_bones, clip_to_skin_mesh, dominant_bones,
    _bone_universe, synth_tarsal_blocks, synth_source_blocks, side_suffix)
from scripts.transfer.cross_subject_transfer import side_of  # noqa: E402
from scripts.zanatomy import zan_source  # noqa: E402
from scripts.export_viewer_bundle import load_atlas_records  # noqa: E402

MAX_MOVE_MM = 12.0          # Q48 used 8mm on thigh-scale muscles; forearm/hand compartments are
                             # smaller but Q147's own placement error is worse, so a bit more slack
ERODE_ITERS = 3              # ~2-3mm of the seed's own outer shell, not used to seed a neighbour
MIN_SHIP_VOL_CM3 = 1.0       # a refined claim smaller than this (or than MIN_SHIP_VOL_FRACTION of
                             # Q147's own transferred volume) is a sign the seed barely reached the
                             # real tissue at all (see extensor_digitorum_r/male: Q147 shipped 3.4
                             # cm3, refinement here found only 0.01cm3 of it within 12mm of the real
                             # compartment) -- Q147's own shape, imperfect but non-degenerate, is
                             # kept instead of overwriting it with a sliver (same "disclose, don't
                             # ship broken" practice as Q147's own >50%-outside-skin reject).
MIN_SHIP_VOL_FRACTION = 0.15
NEIGHBOUR_DILATE_MM = 5.0    # Q150b: how far a held-out id's own label is grown to find which
                             # other real labels count as its "anatomical neighbours"


def voxel_to_atlas(idx: np.ndarray, affine: np.ndarray, origin: np.ndarray) -> np.ndarray:
    return vol.voxels_to_atlas(idx.astype(np.float64), affine) - origin


def atlas_to_voxel(pts: np.ndarray, affine: np.ndarray, origin: np.ndarray) -> np.ndarray:
    """Inverse of voxel_to_atlas: atlas mm -> this volume's own voxel indices (float)."""
    p = pts + origin
    ras = np.stack([p[:, 0], p[:, 2], p[:, 1]], axis=1)   # atlas (x,y,z) -> RAS (x,z-as-y? ) see voxels_to_atlas
    homo = np.hstack([ras, np.ones((len(ras), 1))])
    inv = np.linalg.inv(affine)
    return (inv @ homo.T).T[:, :3]


def voxelize_mesh(v_atlas: np.ndarray, f: np.ndarray, affine: np.ndarray, origin: np.ndarray,
                   shape: tuple, pitch: float = 0.6) -> np.ndarray:
    """A filled boolean mask, this volume's own voxel grid, True where a transferred mesh's
    interior lands (trimesh voxelise+fill in ATLAS mm, same approach as refine_transfer_to_septa.py)."""
    if len(v_atlas) < 4:
        return np.zeros(shape, bool)
    try:
        tm = trimesh.Trimesh(v_atlas, f, process=False)
        vox = tm.voxelized(pitch=pitch).fill()
        pts = vox.points
    except Exception:
        return np.zeros(shape, bool)
    idx = np.rint(atlas_to_voxel(pts, affine, origin)).astype(np.int64)
    ok = (idx[:, 0] >= 0) & (idx[:, 0] < shape[0]) & (idx[:, 1] >= 0) & (idx[:, 1] < shape[1]) & \
         (idx[:, 2] >= 0) & (idx[:, 2] < shape[2])
    out = np.zeros(shape, bool)
    out[idx[ok, 0], idx[ok, 1], idx[ok, 2]] = True
    return out


def compute_ondemand_transfer(dst_all: dict, ids: list[str]) -> dict:
    """Q147's own per-bone transfer (limb_per_bone_transfer.py), computed fresh for `ids` that
    are NOT in Q147's shipped output -- true for every id already real on this specimen (Q147's
    own default_ids() skips whatever the target already has, so a held-out real muscle's own
    Z-Anatomy estimate was never computed or saved anywhere). Mirrors limb_per_bone_transfer.py's
    own --validate code path exactly (same functions, imported, not reimplemented)."""
    dst_own = {k: m for k, m in dst_all.items() if not str(m.get("subject", "")).startswith(("xfer_", "zanatomy", "zan_"))}
    dst_own = synth_tarsal_blocks(dst_own)
    src = zan_source.load_source()
    src = synth_tarsal_blocks(src)
    src = synth_source_blocks(src, zan_source.DEFAULT_ZAN_DIR)
    atlas_records = load_atlas_records()
    maps = build_bone_maps(src, dst_own)
    skin_m = dst_all.get("skin")
    skin_mesh = trimesh.Trimesh(skin_m["v"].astype(np.float64), skin_m["f"], process=False) if skin_m else None
    bone_cache: dict = {}

    def bone_mesh(bid):
        if bid not in bone_cache:
            m = dst_own.get(bid)
            bone_cache[bid] = trimesh.Trimesh(m["v"].astype(np.float64), m["f"], process=False) if m else None
        return bone_cache[bid]

    out = {}
    for aid in ids:
        m = src.get(aid)
        if m is None:
            continue
        v = m["v"].astype(np.float64); f = m["f"]
        side = side_of(aid, m)
        if side not in ("right", "left"):
            continue
        ss = "r" if side == "right" else "l"
        _, rec = atlas_records.get(aid, (None, None))
        region = (rec or {}).get("region") or (m.get("rec") or {}).get("region")
        dominant = dominant_bones(rec or {}, region, ss)
        if not dominant:
            continue
        nv, used = blend_by_bones(v, maps, dominant)
        if nv is None:
            continue
        universe, _ = _bone_universe(dominant)
        avoid_ids = [f"{b}_{ss}" for b in universe]
        nv, _ = push_off_bones(nv, [bone_mesh(b) for b in avoid_ids])
        nv, _ = clip_to_skin_mesh(nv, skin_mesh)
        out[aid] = (nv, f)
    return out


def load_xfer(d: Path):
    d = Path(d)
    man = json.loads((d / "manifest.json").read_text())
    V = np.fromfile(d / "vertices.f32", np.float32).reshape(-1, 3)
    F = np.fromfile(d / "faces.u32", np.uint32).reshape(-1, 3)
    out = {}
    for s in man["structures"]:
        v = V[s["vertex_offset"]:s["vertex_offset"] + s["vertex_count"]].astype(np.float64)
        f = F[s["face_offset"]:s["face_offset"] + s["triangle_count"]].astype(np.int64) - s["vertex_offset"]
        out[s["atlas_id"]] = (v, f)
    return out


def entry_candidates(e: dict) -> list[str]:
    """This mapping entry's own atlas id(s): [atlas_id] if it is already ground truth, else its
    reviewed `candidates` list (empty if it has neither -- e.g. a tendon-only compartment with
    no plausible muscle at all)."""
    if e.get("atlas_id"):
        return [e["atlas_id"]]
    return list(e.get("candidates") or [])


def load_grid(nii_path: Path):
    im = nib.load(str(nii_path))
    labelvol = np.asanyarray(im.dataobj).astype(np.int32)
    affine = im.affine
    sampling = tuple(float(x) for x in np.abs(np.diag(affine)[:3]))
    return labelvol, affine, sampling


def partition_region(region: np.ndarray, cands: list[str], xfer: dict, affine: np.ndarray,
                      origin: np.ndarray, sampling: tuple, pad: int = 12) -> dict[str, np.ndarray]:
    """Constrained nearest-transferred-seed competition for `region` among `cands`: EVERY
    candidate is seeded ONLY by its own Q147 transferred mesh (voxelised, eroded), never by any
    ground truth, and its final claim is clipped to MAX_MOVE_MM of that same seed. Returns
    {atlas_id: bool mask, full `region.shape`} for whichever candidates claimed anything --
    candidates that never reach `region` at all are simply absent. THIS FUNCTION NEVER TAKES A
    SHORTCUT for a single candidate -- shared by process_volume's review/no_atlas_entity path
    and every --holdout validation variant, so a held-out id can never be handed its own region
    unconditionally (the Q150 leak this was written to close)."""
    ys, xs, zs = np.where(region)
    if len(ys) == 0:
        return {}
    lo = np.maximum(0, [ys.min() - pad, xs.min() - pad, zs.min() - pad])
    hi = np.minimum(region.shape, [ys.max() + pad + 1, xs.max() + pad + 1, zs.max() + pad + 1])
    sl = tuple(slice(int(a), int(b)) for a, b in zip(lo, hi))
    region_c = region[sl]
    avail = [c for c in cands if c in xfer]
    if not avail:
        return {}
    raw_masks = {}
    markers = np.zeros(region_c.shape, np.int32)
    for i, c in enumerate(avail, start=1):
        v, f = xfer[c]
        full_mask = voxelize_mesh(v, f, affine, origin, region.shape)
        raw_masks[c] = full_mask[sl]
        seed = ndi.binary_erosion(raw_masks[c], iterations=ERODE_ITERS)
        if not seed.any():
            seed = raw_masks[c]
        markers[seed] = i
    if not (markers > 0).any():
        return {}
    _, (ix, iy, iz) = ndi.distance_transform_edt(markers == 0, return_indices=True, sampling=sampling)
    nearest = markers[ix, iy, iz]
    out = {}
    for i, c in enumerate(avail, start=1):
        claim = region_c & (nearest == i)
        if not raw_masks[c].any():
            continue   # this candidate's own transferred mesh never reached this volume at all
        dist_c = ndi.distance_transform_edt(~raw_masks[c], sampling=sampling)
        claim &= dist_c <= MAX_MOVE_MM
        if not claim.any():
            continue
        full = np.zeros(region.shape, bool); full[sl] = claim
        out[c] = full
    return out


def process_volume(nii_path: Path, labels_path: Path, mapping_path: Path, origin: np.ndarray, xfer: dict):
    """SHIPPING only (no holdout concept here at all -- see validate_holdout for that). Returns
    (assignments, notes, labelvol, affine, sampling)."""
    labelvol, affine, sampling = load_grid(nii_path)
    entries = json.loads(Path(mapping_path).read_text())["entries"]

    open_entries = []   # (label_id, [candidate atlas ids], free_pass_allowed)
    notes = {}
    for e in entries:
        if e.get("atlas_id"):
            continue   # ground truth, fixed, excluded from competition (never in any `region`)
        cands = e.get("candidates") or []
        if cands:
            # status "no_atlas_entity": a genuine compartment, several muscles the rule truly
            # could not separate -- the reviewer's own considered judgement that this whole blob
            # is (at least) all of `candidates` together. status "review": this specific name's
            # OWN rule-based attempt was reviewed and REJECTED (see the entry's own "note" --
            # typically "volume more than twice the adult expectation ... a rule artefact of the
            # position lines"), i.e. an untrustworthy, usually oversized guess that swallowed a
            # neighbour's belly -- e.g. male pronator_quadratus's own note: "57 cm3 against 8-12
            # expected -- its rule takes the whole distal section". A "review" entry, even with a
            # single candidate, gets NO free pass -- it goes through partition_region like a
            # multi-candidate compartment.
            free_pass = e.get("status") == "no_atlas_entity"
            open_entries.append((e["label"], cands, free_pass))

    assignments = {}
    for lab, cands, free_pass in open_entries:
        region = labelvol == lab
        if not region.any():
            for c in cands:
                notes.setdefault(c, "label absent in this volume")
            continue
        avail = [c for c in cands if c in xfer]
        for c in [c for c in cands if c not in xfer]:
            notes[c] = "no Q147 transferred mesh for this id -- left unassigned"
        if not avail:
            continue
        if len(avail) == 1 and free_pass:
            assignments[avail[0]] = assignments.get(avail[0], np.zeros_like(region)) | region
            continue
        for c, mask in partition_region(region, cands, xfer, affine, origin, sampling).items():
            assignments[c] = assignments.get(c, np.zeros_like(region)) | mask
    return assignments, notes, labelvol, affine, sampling


def mesh_from_mask(mask: np.ndarray, affine: np.ndarray, origin: np.ndarray):
    v, f = vol.mask_surface(mask, step=1, smooth=1.0)
    if len(v) == 0:
        return None, None
    return voxel_to_atlas(v, affine, origin), f


def neighbour_region_and_candidates(labelvol: np.ndarray, entries: list[dict], lab_h: int,
                                     sampling: tuple, dilate_mm: float = NEIGHBOUR_DILATE_MM):
    """Q150b neighbour variant's own region+candidate builder, factored out so a test can check
    it directly: the held-out label's own true footprint UNION every other real label touching
    it within `dilate_mm` (their own true voxels included in the OPEN, contested region -- never
    kept fixed), and the candidate list is the held-out id plus every one of those neighbours'
    own entry_candidates(). Cropped to a local box first so the distance transform stays cheap."""
    by_label = {e["label"]: e for e in entries}
    mask_h = labelvol == lab_h
    ys, xs, zs = np.where(mask_h)
    pad_vox = int(np.ceil(dilate_mm / max(min(sampling), 1e-6))) + 2
    lo = np.maximum(0, [ys.min() - pad_vox, xs.min() - pad_vox, zs.min() - pad_vox])
    hi = np.minimum(labelvol.shape, [ys.max() + pad_vox + 1, xs.max() + pad_vox + 1, zs.max() + pad_vox + 1])
    sl = tuple(slice(int(a), int(b)) for a, b in zip(lo, hi))
    sub = labelvol[sl]
    submask_h = sub == lab_h
    dist = ndi.distance_transform_edt(~submask_h, sampling=sampling)
    near = (dist <= dilate_mm) & (sub > 0) & (sub != lab_h)
    touching = set(int(x) for x in np.unique(sub[near]))
    region = labelvol == lab_h
    cands = set()
    h_entry = by_label.get(lab_h)
    if h_entry:
        cands.update(entry_candidates(h_entry))
    for nl in touching:
        region = region | (labelvol == nl)
        e = by_label.get(nl)
        if e:
            cands.update(entry_candidates(e))
    return region, sorted(cands), touching


def score_holdout(h_id: str, claim, target: dict, affine, origin, sampling) -> dict:
    voxel_cm3 = float(np.prod(sampling)) / 1000.0
    real = target.get(h_id)
    if real is None or str(real.get("subject", "")).startswith(("xfer_", "zanatomy", "zan_")):
        return {"id": h_id, "skipped": "no real mesh on target"}
    if claim is None or not claim.any():
        return {"id": h_id, "skipped": "no claim recovered (no seed reached this region)"}
    cv, cf = mesh_from_mask(claim, affine, origin)
    if cv is None:
        return {"id": h_id, "skipped": "empty recovered mesh"}
    from scripts.zanatomy.validate_registration import compare
    row = {"id": h_id, "real_subject": real["subject"], "claimed_voxels_cm3": round(int(claim.sum()) * voxel_cm3, 1)}
    row.update(compare(real["v"].astype(np.float64), real["f"], cv, cf))
    return row


def validate_holdout(nii_path: Path, labels_path: Path, mapping_path: Path, origin: np.ndarray,
                      xfer: dict, target: dict, holdout_ids: list[str], mode: str):
    """Q150b: score each of `holdout_ids` WITHOUT ever searching inside its own isolated true
    label (see module docstring for "neighbor" vs "whole_limb"). Mutates `xfer` in place with
    any on-demand transfers it needed. Returns (rows, notes)."""
    labelvol, affine, sampling = load_grid(nii_path)
    entries = json.loads(Path(mapping_path).read_text())["entries"]
    id_to_label = {e["atlas_id"]: e["label"] for e in entries if e.get("atlas_id")}
    notes = {}
    rows = []

    def ensure_seeds(ids):
        missing = [i for i in ids if i not in xfer]
        if missing:
            xfer.update(compute_ondemand_transfer(target, missing))

    if mode == "whole_limb":
        all_cands = sorted({c for e in entries for c in entry_candidates(e)})
        ensure_seeds(all_cands)
        region_all = labelvol > 0
        result = partition_region(region_all, all_cands, xfer, affine, origin, sampling)
        for h_id in holdout_ids:
            lab_h = id_to_label.get(h_id)
            if lab_h is None:
                notes[h_id] = "not a ground-truth id in this volume's mapping"
                continue
            rows.append(score_holdout(h_id, result.get(h_id), target, affine, origin, sampling))
    elif mode == "neighbor":
        # pre-compute every held-out id's own (region, candidates) FIRST, then call
        # ensure_seeds() ONCE with the union of everything missing -- compute_ondemand_transfer
        # reloads the whole Z-Anatomy source and rebuilds every bone map from scratch each call,
        # so doing that per held-out id (14 held-out muscles on the female forearm) rather than
        # once was the difference between ~1 minute and ~20+ minutes.
        per_id = {}
        all_missing_cands: set[str] = set()
        for h_id in holdout_ids:
            lab_h = id_to_label.get(h_id)
            if lab_h is None:
                notes[h_id] = "not a ground-truth id in this volume's mapping"
                continue
            region, cands, touching = neighbour_region_and_candidates(labelvol, entries, lab_h, sampling)
            per_id[h_id] = (region, cands, touching)
            all_missing_cands.update(cands)
        ensure_seeds(sorted(all_missing_cands))
        for h_id, (region, cands, touching) in per_id.items():
            result = partition_region(region, cands, xfer, affine, origin, sampling)
            notes[h_id] = f"neighbours: {sorted(touching)}, candidates: {cands}"
            rows.append(score_holdout(h_id, result.get(h_id), target, affine, origin, sampling))
    else:
        raise ValueError(f"unknown --holdout-mode {mode!r}")
    return rows, notes


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--direction", choices=["zan2m", "zan2f"], required=True)
    ap.add_argument("--target", required=True, help="the specimen's own current bundle (dir or html)")
    ap.add_argument("--xfer", required=True, help="Q147's own transfer output dir (build/vh/xfer_zan2vh{m,f}_limb)")
    ap.add_argument("--volume", action="append", required=True, dest="volumes")
    ap.add_argument("--labels", action="append", required=True, dest="labels_list")
    ap.add_argument("--mapping", action="append", required=True, dest="mappings")
    ap.add_argument("--origin", action="append", required=True, dest="origins")
    ap.add_argument("--holdout", nargs="*", default=[])
    ap.add_argument("--holdout-mode", choices=["neighbor", "whole_limb", "both"], default="both")
    ap.add_argument("--badge-median-mm", type=float, default=None)
    ap.add_argument("--badge-max-mm", type=float, default=None)
    ap.add_argument("-o", "--out", default=None)
    ap.add_argument("--report", default=None)
    a = ap.parse_args()
    n = len(a.volumes)
    assert len(a.labels_list) == n and len(a.mappings) == n and len(a.origins) == n

    tp = Path(a.target)
    bt, blobt = read_bundle_dir(tp) if tp.is_dir() else read_bundle_html(tp)
    target = meshes_by_id(bt, blobt)
    xfer = load_xfer(a.xfer)
    holdout = list(a.holdout)

    if holdout:
        modes = ["neighbor", "whole_limb"] if a.holdout_mode == "both" else [a.holdout_mode]
        report = {"source": ("Q150b validation: scripts/transfer/refine_limb_transfer.py --holdout. "
                              "Every candidate (including the held-out id) is seeded ONLY by its own "
                              "Q147 transferred mesh; a held-out id's own true label is never used as "
                              "its exclusive search region. Diagnostics only."),
                  "direction": a.direction, "modes": {}}
        for mode in modes:
            all_rows = []
            all_notes = {}
            for vpath, lpath, mpath, ostr in zip(a.volumes, a.labels_list, a.mappings, a.origins):
                origin = np.array([float(t) for t in ostr.split(",")])
                rows, notes = validate_holdout(Path(vpath), Path(lpath), Path(mpath), origin,
                                                xfer, target, holdout, mode)
                for r in rows:
                    r["volume"] = Path(vpath).name
                all_rows.extend(rows); all_notes.update(notes)
                for r in rows:
                    print(mode, r)
            dists = [r["centroid_dist_mm"] for r in all_rows if "centroid_dist_mm" in r]
            summary = {"n": len(all_rows), "n_scored": len(dists), "notes": all_notes, "rows": all_rows}
            if dists:
                summary["median_centroid_dist_mm"] = round(float(np.median(dists)), 1)
                summary["max_centroid_dist_mm"] = round(float(np.max(dists)), 1)
                print(f"[{mode}] median centroid_dist_mm over {len(dists)}: {summary['median_centroid_dist_mm']}, "
                      f"max: {summary['max_centroid_dist_mm']}")
            report["modes"][mode] = summary
        if a.report:
            Path(a.report).write_text(json.dumps(report, indent=1))
            print(f"wrote {a.report}")
        return

    # shipping: only the ids actually refined here (open-label candidates); everything else keeps
    # its Q147 shape (this subject is listed BEFORE xfer_zan2vh{m,f}_limb in the rebuild bundle so
    # only these ids override it; every other transferred id -- most of Q147's 62/23 -- is untouched)
    if not a.out:
        print("no --out: nothing shipped."); return
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    verts, faces, structures = [], [], []
    voff = 0
    all_notes = {}
    for vpath, lpath, mpath, ostr in zip(a.volumes, a.labels_list, a.mappings, a.origins):
        origin = np.array([float(t) for t in ostr.split(",")])
        assign, notes, labelvol, affine, sampling = process_volume(Path(vpath), Path(lpath), Path(mpath), origin, xfer)
        all_notes.update(notes)
        voxel_cm3 = float(np.prod(sampling)) / 1000.0
        for aid, mask in sorted(assign.items()):
            refined_vol = int(mask.sum()) * voxel_cm3
            q147_vol = mesh_volume_cm3(*xfer[aid]) if aid in xfer else 0.0
            if refined_vol < max(MIN_SHIP_VOL_CM3, MIN_SHIP_VOL_FRACTION * q147_vol):
                all_notes[aid] = (f"refined claim too small ({refined_vol:.2f} cm3 vs Q147's own "
                                  f"{q147_vol:.1f} cm3) -- kept as Q147, not shipped here")
                continue
            v, f = mesh_from_mask(mask, affine, origin)
            if v is None:
                continue
            badge = ("Refined to this specimen's own segmented forearm/hand tissue "
                     "(scripts/transfer/refine_limb_transfer.py, Q150) within Q147's Z-Anatomy "
                     "per-bone transfer -- generic Z-Anatomy shape, boundary now constrained to the "
                     "specimen's own real tissue extent" +
                     (f"; validation median error {a.badge_median_mm:.1f} mm, max {a.badge_max_mm:.1f} mm"
                      if a.badge_median_mm is not None else "") + ".")
            v32 = v.astype(np.float32)
            structures.append({"atlas_id": aid, "source_structure": aid, "side": "right",
                                "source_file": f"{Path(vpath).name}#refined",
                                "vertex_offset": voff, "face_offset": sum(len(x) for x in faces),
                                "vertex_count": int(len(v32)), "triangle_count": int(len(f)),
                                "bbox_min_mm": [round(float(x), 4) for x in v32.min(axis=0)],
                                "bbox_max_mm": [round(float(x), 4) for x in v32.max(axis=0)],
                                "procedural_badge": badge})
            verts.append(v32); faces.append((f + voff).astype(np.uint32)); voff += len(v32)
    V = np.concatenate(verts) if verts else np.zeros((0, 3), np.float32)
    Fc = np.concatenate(faces) if faces else np.zeros((0, 3), np.uint32)
    V.tofile(out / "vertices.f32"); Fc.tofile(out / "faces.u32")
    manifest = {"subject": out.name, "frame": "atlas: +X right, +Y superior, +Z anterior, millimetres",
                "source_volume": None, "source_kind": "Q150 refinement of Q147 zanatomy transfer to own tissue",
                "vertex_count": int(len(V)), "triangle_count": int(len(Fc)),
                "bbox_min_mm": [round(float(x), 4) for x in V.min(axis=0)] if len(V) else None,
                "bbox_max_mm": [round(float(x), 4) for x in V.max(axis=0)] if len(V) else None,
                "attribution": ["Refined from the Z-Anatomy per-bone transfer (Q147) to this specimen's own "
                                "segmented forearm/hand muscle-tissue extent (scripts/transfer/"
                                "refine_limb_transfer.py, Q150). Still a generic Z-Anatomy shape internally; only "
                                "the boundary against neighbouring tissue and against unrelated compartments is "
                                "now the specimen's own."],
                "license": "CC-BY-SA-4.0", "structures": structures}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=1))
    rep = {"source": manifest["attribution"][0] + " Derived data (scripts/transfer/refine_limb_transfer.py, Q150).",
           "direction": a.direction, "n": len(structures), "notes": all_notes,
           "ids": [s["atlas_id"] for s in structures]}
    if a.report:
        Path(a.report).write_text(json.dumps(rep, indent=1))
    print(f"{out.name}: {len(structures)} refined structures: {[s['atlas_id'] for s in structures]}")
    print("not refined (kept as Q147):", json.dumps(all_notes, indent=1))


if __name__ == "__main__":
    main()
