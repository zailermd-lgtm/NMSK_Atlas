"""Q150: refine Q147's Z-Anatomy forearm/hand transfer to each specimen's OWN
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

METHOD. For each of these volumes, every label is either:
  - a GROUND-TRUTH single muscle (the subject's own volume_mapping.json sets
    its atlas_id) -- already shipped as real geometry (ct_vh{m,f}_forearm/
    ct_vhf_hand); untouched here, a hard constraint on everything else.
  - an OPEN label (atlas_id null) -- a compartment the cryo rule could not
    split, or an individually-named region that volume review rejected as
    unreliable on its own (see each label's own "note") -- with one or more
    "candidates" (the atlas ids that could be inside it; already curated by
    that review, reused verbatim here).

Every open label's own real tissue extent is partitioned among its own
candidates by NEAREST-TRANSFERRED-SEED competition: each candidate's Q147
per-bone-transferred mesh (limb_per_bone_transfer.py), voxelised and eroded
~2mm, seeds a Euclidean-distance Voronoi (scipy distance_transform_edt with
return_indices -- there is no grayscale texture left to watershed on, so this
is the geometric substitute the task's own fallback anticipates), restricted
to the label's own mask, each candidate's final claim additionally clipped to
within MAX_MOVE_MM of its OWN (uneroded) transferred mask -- Q48's "a muscle
may not move more than its own transfer" rule, so a badly-placed transfer
cannot claim tissue nowhere near it. A candidate with a single "candidates"
entry needs no competition: it gets the whole label region outright (a
reviewer already decided that whole blob is (most likely) that one muscle,
just under-confident about the exact volume/name -- see the label's "note").
A candidate absent from Q147's own transferred output (no Z-Anatomy source
mesh for its id at all -- checked per volume, logged) is left unassigned, same
"not shipped" status as Q147 already gave it.

VALIDATION (leave-one-out, same design as Q147/Q48): --holdout ID [ID ...]
temporarily reverts each named ID's own GROUND-TRUTH label back to "open,
candidates=[ID]" (merged into the very same competitive partition above,
alongside genuine open compartments -- other real single-muscle labels stay
fixed/excluded, a hard constraint), then reports how well its own recovered
claim matches its TRUE voxel footprint (centroid distance, volume ratio,
voxel Dice/IoU -- scripts/zanatomy/validate_registration.compare(), on a mesh
marching-cubed from each side so the metric is identical to Q147's own).
Nothing is shipped in this mode.

    # validation
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


def process_volume(nii_path: Path, labels_path: Path, mapping_path: Path, origin: np.ndarray,
                    xfer: dict, holdout: set[str]):
    """Returns (assignments, notes) where assignments: {atlas_id: bool voxel mask (this volume's
    own grid)}, and notes: {atlas_id: str} for anything skipped, plus 'held_out_truth':
    {atlas_id: bool mask} recording each held-out id's ORIGINAL ground-truth footprint (for scoring)."""
    im = nib.load(str(nii_path)); labelvol = np.asanyarray(im.dataobj).astype(np.int32); affine = im.affine
    sampling = tuple(float(x) for x in np.abs(np.diag(affine)[:3]))
    labels = json.loads(Path(labels_path).read_text())["labels"]
    mapping = json.loads(Path(mapping_path).read_text())
    entries = mapping["entries"]

    open_entries = []   # (label_id, [candidate atlas ids], is_holdout)
    held_truth = {}
    notes = {}
    for e in entries:
        lab = e["label"]; aid = e.get("atlas_id")
        if aid and aid in holdout:
            held_truth[aid] = (labelvol == lab)
            # is_holdout=True: even with a single candidate (itself), this must go through the
            # SAME seed+max-move-constrained path as a real open compartment, never the "hand
            # over the whole label" shortcut below -- that shortcut is only honest for a label
            # we are not pretending to be ignorant of. Skipping it here is what makes this a real
            # leave-one-out test instead of reading the answer back out of its own ground truth.
            open_entries.append((lab, [aid], True))
            notes[aid] = "held out for validation: reverted to open, single candidate"
        elif aid:
            continue   # ground truth, fixed, excluded from competition (implicit: never in `region`)
        else:
            cands = e.get("candidates") or []
            if cands:
                # status "no_atlas_entity": a genuine compartment, several muscles the rule truly
                # could not separate -- the reviewer's own considered judgement that this whole
                # blob is (at least) all of `candidates` together. status "review": this specific
                # name's OWN rule-based attempt was reviewed and REJECTED (see the entry's own
                # "note" -- typically "volume more than twice the adult expectation ... a rule
                # artefact of the position lines"), i.e. an untrustworthy, usually oversized guess
                # that swallowed a neighbour's belly -- e.g. male pronator_quadratus's own label is
                # 57 cm3 against an 8-12 cm3 expectation because "at f > 0.9 only its rule is
                # active, so the whole distal muscle section falls to it" (its own note, verbatim).
                # A "review" entry, even with a single candidate, MUST NOT get the free-pass
                # shortcut below -- it goes through the same seed-constrained path as a holdout.
                distrust = e.get("status") == "review"
                open_entries.append((lab, cands, distrust))

    assignments = {}
    for lab, cands, is_holdout in open_entries:
        region = labelvol == lab
        if not region.any():
            for c in cands:
                notes.setdefault(c, "label absent in this volume")
            continue
        avail = [c for c in cands if c in xfer]
        missing = [c for c in cands if c not in xfer]
        for c in missing:
            notes[c] = "no Q147 transferred mesh for this id -- left unassigned"
        if not avail:
            continue
        if len(avail) == 1 and not is_holdout:
            # a genuinely unlabeled region with only one plausible muscle (the prior review's own
            # "candidates" list, e.g. palmaris_longus's own compartment) -- that whole blob is
            # already this candidate's best-known real extent, no seed needed to trust it.
            assignments[avail[0]] = assignments.get(avail[0], np.zeros_like(region)) | region
            continue
        # crop to the label's own local bounding box (+ margin) so the EDT/voxelisation below
        # stay cheap regardless of the full volume's size
        ys, xs, zs = np.where(region)
        pad = 12
        lo = np.maximum(0, [ys.min() - pad, xs.min() - pad, zs.min() - pad])
        hi = np.minimum(region.shape, [ys.max() + pad + 1, xs.max() + pad + 1, zs.max() + pad + 1])
        sl = tuple(slice(int(a), int(b)) for a, b in zip(lo, hi))
        region_c = region[sl]
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
            continue
        _, (ix, iy, iz) = ndi.distance_transform_edt(markers == 0, return_indices=True, sampling=sampling)
        nearest = markers[ix, iy, iz]
        for i, c in enumerate(avail, start=1):
            claim = region_c & (nearest == i)
            if not raw_masks[c].any():
                continue   # this candidate's own transferred mesh never reached this volume at all
            dist_c = ndi.distance_transform_edt(~raw_masks[c], sampling=sampling)
            claim &= dist_c <= MAX_MOVE_MM
            if not claim.any():
                continue
            full = np.zeros(region.shape, bool); full[sl] = claim
            assignments[c] = assignments.get(c, np.zeros_like(region)) | full
    return assignments, notes, held_truth, labelvol, affine, sampling


def mesh_from_mask(mask: np.ndarray, affine: np.ndarray, origin: np.ndarray):
    v, f = vol.mask_surface(mask, step=1, smooth=1.0)
    if len(v) == 0:
        return None, None
    return voxel_to_atlas(v, affine, origin), f


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
    holdout = set(a.holdout)
    missing_seed = [i for i in holdout if i not in xfer]
    if missing_seed:
        print(f"computing on-demand Q147 transfer for held-out real ids not in {a.xfer}: {missing_seed}")
        xfer.update(compute_ondemand_transfer(target, missing_seed))

    all_assign = {}
    all_notes = {}
    val_rows = []
    for vpath, lpath, mpath, ostr in zip(a.volumes, a.labels_list, a.mappings, a.origins):
        origin = np.array([float(t) for t in ostr.split(",")])
        assign, notes, held_truth, labelvol, affine, sampling = process_volume(
            Path(vpath), Path(lpath), Path(mpath), origin, xfer, holdout)
        all_assign.update(assign)
        all_notes.update(notes)
        voxel_cm3 = float(np.prod(sampling)) / 1000.0
        for aid, truth_mask in held_truth.items():
            claim = assign.get(aid)
            real = target.get(aid)
            if real is None or str(real.get("subject", "")).startswith(("xfer_", "zanatomy", "zan_")):
                val_rows.append({"id": aid, "skipped": "no real mesh on target"}); continue
            if claim is None or not claim.any():
                val_rows.append({"id": aid, "volume": Path(vpath).name,
                                  "skipped": "no claim recovered (no seed reached this label)"})
                continue
            cv, cf = mesh_from_mask(claim, affine, origin)
            if cv is None:
                val_rows.append({"id": aid, "volume": Path(vpath).name, "skipped": "empty recovered mesh"})
                continue
            from scripts.zanatomy.validate_registration import compare
            row = {"id": aid, "volume": Path(vpath).name, "real_subject": real["subject"],
                   "claimed_voxels_cm3": round(int(claim.sum()) * voxel_cm3, 1),
                   "truth_voxels_cm3": round(int(truth_mask.sum()) * voxel_cm3, 1)}
            row.update(compare(real["v"].astype(np.float64), real["f"], cv, cf))
            val_rows.append(row)
            print(row)

    if holdout:
        rep = {"source": "Q150 validation: scripts/transfer/refine_limb_transfer.py --holdout. Diagnostics only.",
               "direction": a.direction, "n": len(val_rows), "notes": all_notes, "rows": val_rows}
        if a.report:
            Path(a.report).write_text(json.dumps(rep, indent=1))
            print(f"wrote {a.report}")
        dists = [r["centroid_dist_mm"] for r in val_rows if "centroid_dist_mm" in r]
        if dists:
            print(f"median centroid_dist_mm over {len(dists)} structures: {float(np.median(dists)):.1f}, "
                  f"max: {float(np.max(dists)):.1f}")
        return

    # shipping: only the ids actually refined here (open-label candidates); everything else keeps
    # its Q147 shape (this subject is listed BEFORE xfer_zan2vh{m,f}_limb in the rebuild bundle so
    # only these ids override it; every other transferred id -- most of Q147's 62/23 -- is untouched)
    if not a.out:
        print("no --out: nothing shipped. notes:", json.dumps(all_notes, indent=1)); return
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    verts, faces, structures = [], [], []
    voff = 0
    origins_by_id = {}
    for vpath, lpath, mpath, ostr in zip(a.volumes, a.labels_list, a.mappings, a.origins):
        origins_by_id[Path(vpath).name] = ostr
    # rerun per-volume to keep affine/origin association for meshing (cheap: same process_volume call)
    for vpath, lpath, mpath, ostr in zip(a.volumes, a.labels_list, a.mappings, a.origins):
        origin = np.array([float(t) for t in ostr.split(",")])
        assign, notes, _held, labelvol, affine, sampling = process_volume(
            Path(vpath), Path(lpath), Path(mpath), origin, xfer, set())
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
