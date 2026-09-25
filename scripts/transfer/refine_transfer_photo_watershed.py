"""Q151b: refine Q147's Z-Anatomy forearm/hand transfer using an ACTUAL marker-controlled
watershed on this specimen's OWN cryosection photograph gradient (Q48's method), instead of
Q150b's geometric nearest-transferred-seed distance-transform substitute (which Q150b used only
because the crop-based photograph pipelines' intermediate files did not survive a container
reset). Q151 re-acquired the real full-resolution photographs fresh from the NCI Imaging Data
Commons (data/derived/Q151_reacquisition_summary.json); this script is the first thing that
actually reads them for a refinement (Q151 itself only re-interpolated old label volumes).

REGISTRATION (male). Per level (one real photograph per 1 mm level, matching the existing
vhm_forearm_muscles_cryo.nii.gz grid's Z spacing exactly -- no shape interpolation needed, see
scripts/transfer/shape_interp.py's own "only if slice spacing > 1 mm" rule): torso RAS z = 985 -
instance (vhm_forearm_muscles_from_cryo.py's own documented relation). In-plane: the forearm
island is found directly in the raw full-resolution frame (cryo_classes.classify tissue, the
left-hand side component -- "photo left = the subject's right", the same handedness the
committed male/female forearm scripts document); its own two interior bright (fat/pale/white)
blobs, well inside the skin, are the photographed radius+ulna cross-section, whose COMBINED
pixel centroid is registered by TRANSLATION ONLY (no rotation, same limit the committed script
documents) onto vhm_arm_bones_cryo_completed.nii.gz's (labels 2/3) own combined centroid at the
same torso RAS z -- i.e. the same bone-corrected registration the committed script converges to,
computed directly from the full CT bone volume (available at every level here) rather than
through an intermediate body-silhouette step (whose only CT dependency, the raw torso CT, did
not survive the reset and is out of scope to re-acquire, ct_to_photo_shift_mm's own body-centroid
stage is skipped, landing straight on the bone-corrected result the old pipeline used the body
centroid only to approach). Verified by overlaying the CT radius/ulna cross-sections back onto 3
photographs (proximal/mid/distal) -- see --overlay-dir.

GRADIENT SUBSTRATE. Per level: white_tophat(image.max(-1), disk(4)) (identical call to
refine_transfer_to_septa.py/vhf_forearm_muscles_from_cryo.py's own septa ridge detector) computed
on the native 0.33 mm crop, then resampled (nearest) into vhm_forearm_muscles_cryo.nii.gz's own
0.5x0.5x1 mm grid via the per-level registration above. The EXISTING label volume's own real
tissue extent (vhm_forearm_muscles_cryo.nii.gz, itself a real photograph-derived segmentation
from the same specimen, same registration method, now-lost crops) is reused as the competition
region -- this script's only new contribution is the actual photograph gradient the boundary is
placed on, replacing Q150b's blind nearest-seed Voronoi.

PARTITION. A drop-in replacement for refine_limb_transfer.partition_region with the identical
contract (markers = each candidate's own eroded Q147 mesh, MAX_MOVE_MM clip, no free pass) except
the boundary is placed by skimage.segmentation.watershed(tophat, markers, mask=region) instead of
a Euclidean nearest-marker distance transform. Installed by monkeypatching the name
refine_limb_transfer.partition_region so process_volume/validate_holdout/
neighbour_region_and_candidates run completely UNMODIFIED (their own regression tests,
tests/test_refine_limb_transfer.py, are untouched by this file and keep passing).

    python3 scripts/transfer/refine_transfer_photo_watershed.py --specimen m \
        --cryo-dir SCRATCH/vh_cryo_m_forearm_q151 \
        --volume data/ct_sources/task_outputs/vhm_forearm_muscles_cryo.nii.gz \
        --labels mappings/vhm_forearm_muscles_labels.json \
        --mapping build/vh/ct_vhm_forearm_volume_mapping.json --origin=-6.035,-895.476,4.787 \
        --target build/viewer_m --xfer build/vh/xfer_zan2vhm_limb \
        --holdout flexor_digitorum_superficialis_r flexor_digitorum_profundus_r abductor_pollicis_longus_r \
        --overlay-dir SCRATCH/q151b --report data/derived/Q151b_validation_male.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import nibabel as nib
from scipy import ndimage as ndi
from skimage.morphology import white_tophat, disk
from skimage.segmentation import watershed

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "cryo"))
from cryo_classes import classify  # noqa: E402
import scripts.transfer.refine_limb_transfer as RLT  # noqa: E402

PX = 0.33
BADGE_METHOD = ("Z-Anatomy (CC BY-SA 4.0) shape refined to this specimen's cryosection photographs "
                 "(watershed on tissue boundaries)")

SPECIMENS = {
    "m": dict(z_of_inst=985.0, bones_aff=(350.0, 240.0, -1113.0), bone_ids=(2, 3),
              bones_path=REPO / "data/ct_sources/task_outputs/vhm_arm_bones_cryo_completed.nii.gz"),
}


# --------------------------------------------------------------------------------- registration
def clean_candidate(cls, size_lo=15000, size_hi=200000, w_max=420, h_max=480, bottom_cut=1020):
    tissue = cls > 0
    lab, n = ndi.label(tissue)
    if n == 0:
        return None
    sizes = ndi.sum(tissue, lab, range(1, n + 1))
    cands = []
    for i in range(1, n + 1):
        sz = sizes[i - 1]
        if sz < size_lo or sz > size_hi:
            continue
        ys, xs = np.where(lab == i)
        r0, r1, c0, c1 = ys.min(), ys.max(), xs.min(), xs.max()
        if (c1 - c0) > w_max or (r1 - r0) > h_max or ys.mean() > bottom_cut:
            continue
        cands.append((c0, r0, r1, c0, c1, float(ys.mean()), float(xs.mean()), int(sz)))
    if not cands:
        return None
    cands.sort(key=lambda t: t[0])  # leftmost = subject's right forearm
    _, r0, r1, c0, c1, cy, cx, sz = cands[0]
    return (int(r0), int(r1), int(c0), int(c1)), cy, cx, sz


def bone_disc_centroid(cls, bbox):
    r0, r1, c0, c1 = bbox
    sub_cls = cls[r0:r1 + 1, c0:c1 + 1]
    filled = ndi.binary_fill_holes(ndi.binary_closing(sub_cls > 0, iterations=1))
    interior = ndi.binary_erosion(filled, iterations=18)
    if not interior.any():
        interior = ndi.binary_erosion(filled, iterations=8)
    bright = np.isin(sub_cls, (2, 4, 5)) & interior
    bright = ndi.binary_closing(bright, iterations=2)
    lab, n = ndi.label(bright)
    if n == 0:
        return None
    sizes = ndi.sum(bright, lab, range(1, n + 1))
    order = np.argsort(sizes)[::-1][:2]
    ys_all, xs_all = [], []
    for k in order:
        if sizes[k] < 150:
            continue
        ys, xs = np.where(lab == k + 1)
        ys_all.append(ys); xs_all.append(xs)
    if not ys_all:
        return None
    ys = np.concatenate(ys_all) + r0; xs = np.concatenate(xs_all) + c0
    return float(ys.mean()), float(xs.mean())


def ct_bone_centroid(bones, bones_aff, bone_ids, z):
    k = int(round(z - bones_aff[2]))
    if not (0 <= k < bones.shape[2]):
        return None
    sl = bones[:, :, k]
    m = np.isin(sl, bone_ids)
    if not m.any():
        return None
    ii, jj = np.where(m)
    x = bones_aff[0] - ii; y = bones_aff[1] - jj
    return float(x.mean()), float(y.mean())


def register_series(arr, idx, spec):
    """Per real-photograph instance: {inst: {row_b, col_b, xB, yB, bbox}}. Two-pass: pass 1 finds
    the cleanly-separated forearm island at every level independently (small/round size filter --
    this never actually needs a merge-with-trunk fallback on the male series, checked: 137/137
    clean); pass 2 (unused here, kept only as documented fallback) would predict a crop box by
    polynomial extrapolation for any instance pass 1 missed."""
    order = sorted(range(len(idx)), key=lambda i: idx[i][1])
    insts = [idx[i][1] for i in order]
    bones = np.asanyarray(nib.load(str(spec["bones_path"])).dataobj)
    clean, cls_cache = {}, {}
    for oi, inst in zip(order, insts):
        img = np.asarray(arr[oi])
        cls = classify(img)
        cls_cache[inst] = cls
        c = clean_candidate(cls)
        if c is not None:
            bbox, cy, cx, sz = c
            clean[inst] = {"bbox": bbox, "cy": cy, "cx": cx}
    missing = [i for i in insts if i not in clean]
    T = {}
    H, W = next(iter(cls_cache.values())).shape
    if missing:
        ci = np.array(sorted(clean.keys()))
        cy_arr = np.array([clean[i]["cy"] for i in ci]); cx_arr = np.array([clean[i]["cx"] for i in ci])
        py = np.polyfit(ci, cy_arr, 2); px = np.polyfit(ci, cx_arr, 2)
        med_h = np.median([clean[i]["bbox"][1] - clean[i]["bbox"][0] for i in ci]) / 2
        med_w = np.median([clean[i]["bbox"][3] - clean[i]["bbox"][2] for i in ci]) / 2
    for inst in insts:
        cls = cls_cache[inst]
        if inst in clean:
            r0, r1, c0, c1 = clean[inst]["bbox"]
        else:
            pcy = float(np.polyval(py, inst)); pcx = float(np.polyval(px, inst))
            r0, r1 = int(pcy - med_h), int(pcy + med_h); c0, c1 = int(pcx - med_w), int(pcx + med_w)
        pad = 25
        bbox = (max(0, r0 - pad), min(H - 1, r1 + pad), max(0, c0 - pad), min(W - 1, c1 + pad))
        bd = bone_disc_centroid(cls, bbox)
        z = spec["z_of_inst"] - inst
        ct = ct_bone_centroid(bones, spec["bones_aff"], spec["bone_ids"], z)
        if bd is None or ct is None:
            continue
        row_b, col_b = bd; xB, yB = ct
        T[inst] = {"row_b": row_b, "col_b": col_b, "xB": xB, "yB": yB, "bbox": bbox}
    return T, missing


def save_overlay(arr, idx, spec, T, inst, out_path):
    j = [i for i, e in enumerate(idx) if e[1] == inst][0]
    img = np.asarray(arr[j]).copy()
    t = T[inst]
    r0, r1, c0, c1 = t["bbox"]
    pad = 40
    r0p, r1p, c0p, c1p = max(0, r0 - pad), r1 + pad, max(0, c0 - pad), c1 + pad
    crop = img[r0p:r1p, c0p:c1p].copy()
    bones = np.asanyarray(nib.load(str(spec["bones_path"])).dataobj)
    z = spec["z_of_inst"] - inst
    k = int(round(z - spec["bones_aff"][2]))
    sl = bones[:, :, k]
    m = np.isin(sl, spec["bone_ids"])
    ii, jj = np.where(m)
    x = spec["bones_aff"][0] - ii; y = spec["bones_aff"][1] - jj
    row = t["row_b"] + (y - t["yB"]) / PX; col = t["col_b"] - (x - t["xB"]) / PX
    row = row - r0p; col = col - c0p
    ok = (row >= 0) & (row < crop.shape[0]) & (col >= 0) & (col < crop.shape[1])
    crop[row[ok].astype(int), col[ok].astype(int)] = [0, 255, 0]
    from PIL import Image
    Image.fromarray(crop).save(out_path)


# --------------------------------------------------------------------------------- gradient volume
def build_tophat_volume(arr, idx, spec, T, labelvol_affine, shape):
    """(shape) float32 volume, this label volume's own grid: white_tophat(value, disk(4)) of the
    photograph at every real level, resampled (nearest) via the per-level registration."""
    inst_of_j = {e[1]: i for i, e in enumerate(idx)}
    ni, nj, nk = shape
    ii = np.arange(ni); jj = np.arange(nj)
    I, J = np.meshgrid(ii, jj, indexing="ij")
    wx = labelvol_affine[0, 0] * I + labelvol_affine[0, 3]
    wy = labelvol_affine[1, 1] * J + labelvol_affine[1, 3]
    out = np.zeros(shape, np.float32)
    n_ok = 0
    for k in range(nk):
        wz = labelvol_affine[2, 2] * k + labelvol_affine[2, 3]
        inst = int(round(spec["z_of_inst"] - wz))
        if inst not in T or inst not in inst_of_j:
            continue
        t = T[inst]
        row = t["row_b"] + (wy - t["yB"]) / PX
        col = t["col_b"] - (wx - t["xB"]) / PX
        r0, r1, c0, c1 = t["bbox"]
        pad = 30
        cr0, cr1, cc0, cc1 = max(0, r0 - pad), r1 + pad, max(0, c0 - pad), c1 + pad
        img = np.asarray(arr[inst_of_j[inst]])
        crop = img[cr0:cr1, cc0:cc1]
        value = crop.max(-1).astype(np.float32)
        th = white_tophat(value, disk(4))
        rr = np.rint(row - cr0).astype(np.int64); cc = np.rint(col - cc0).astype(np.int64)
        ok = (rr >= 0) & (rr < th.shape[0]) & (cc >= 0) & (cc < th.shape[1])
        slab = np.zeros((ni, nj), np.float32)
        slab[ok] = th[rr[ok], cc[ok]]
        out[:, :, k] = slab
        n_ok += 1
    return out, n_ok


# --------------------------------------------------------------------------------- watershed partition (drop-in)
_TOPHAT = {"vol": None}


def set_tophat(vol):
    _TOPHAT["vol"] = vol


def partition_region_watershed(region, cands, xfer, affine, origin, sampling, pad=12):
    import time as _t
    _t0 = _t.time()
    tophat = _TOPHAT["vol"]
    assert tophat is not None, "call set_tophat() first"
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
        full_mask = RLT.voxelize_mesh(v, f, affine, origin, region.shape)
        raw_masks[c] = full_mask[sl]
        seed = ndi.binary_erosion(raw_masks[c], iterations=RLT.ERODE_ITERS)
        if not seed.any():
            seed = raw_masks[c]
        markers[seed] = i
    if not (markers > 0).any():
        return {}
    th_c = tophat[sl]
    _tw = _t.time()
    ws = watershed(th_c, markers, mask=region_c)
    print(f"  partition_region_watershed: region {region_c.shape}, {len(avail)} cands, "
          f"watershed {_t.time()-_tw:.2f}s, total {_t.time()-_t0:.2f}s", flush=True)
    out = {}
    for i, c in enumerate(avail, start=1):
        claim = region_c & (ws == i)
        if not raw_masks[c].any():
            continue
        dist_c = ndi.distance_transform_edt(~raw_masks[c], sampling=sampling)
        claim &= dist_c <= RLT.MAX_MOVE_MM
        if not claim.any():
            continue
        full = np.zeros(region.shape, bool); full[sl] = claim
        out[c] = full
    return out


# --------------------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--specimen", choices=["m"], required=True)
    ap.add_argument("--cryo-dir", required=True)
    ap.add_argument("--volume", required=True)
    ap.add_argument("--labels", required=True)
    ap.add_argument("--mapping", required=True)
    ap.add_argument("--origin", required=True)
    ap.add_argument("--target", required=True)
    ap.add_argument("--xfer", required=True)
    ap.add_argument("--holdout", nargs="*", default=[])
    ap.add_argument("--holdout-mode", choices=["neighbor", "whole_limb", "both"], default="both")
    ap.add_argument("--overlay-dir", default=None)
    ap.add_argument("--overlay-insts", nargs=3, type=int, default=None)
    ap.add_argument("-o", "--out", default=None)
    ap.add_argument("--report", default=None)
    a = ap.parse_args()

    spec = SPECIMENS[a.specimen]
    origin = np.array([float(t) for t in a.origin.split(",")])
    arr = np.load(str(Path(a.cryo_dir) / "cryo_1mm.npy"), mmap_mode="r")
    idx = json.load(open(Path(a.cryo_dir) / "cryo_index.json"))

    print("registering", len(idx), "real photograph levels ...")
    T, missing = register_series(arr, idx, spec)
    print(f"registered {len(T)}/{len(idx)} levels (missing: {missing})")

    if a.overlay_dir:
        Path(a.overlay_dir).mkdir(parents=True, exist_ok=True)
        insts_sorted = sorted(T)
        checks = a.overlay_insts or [insts_sorted[0], insts_sorted[len(insts_sorted) // 2], insts_sorted[-1]]
        for inst in checks:
            save_overlay(arr, idx, spec, T, inst, Path(a.overlay_dir) / f"q151b_overlay_{a.specimen}_{inst}.png")
        print("wrote registration overlay PNGs for", checks, "to", a.overlay_dir)

    labelvol, affine, sampling = RLT.load_grid(Path(a.volume))
    print("building photograph gradient volume on grid", labelvol.shape, "...")
    tophat, n_ok = build_tophat_volume(arr, idx, spec, T, affine, labelvol.shape)
    print(f"gradient volume built from {n_ok}/{labelvol.shape[2]} real levels")
    set_tophat(tophat)
    import time as _time2
    _orig_ondemand = RLT.compute_ondemand_transfer

    def _timed_ondemand(dst_all, ids):
        t = _time2.time()
        print(f"compute_ondemand_transfer({ids}) starting ...", flush=True)
        out = _orig_ondemand(dst_all, ids)
        print(f"compute_ondemand_transfer finished in {_time2.time()-t:.1f}s, got {list(out)}", flush=True)
        return out
    RLT.compute_ondemand_transfer = _timed_ondemand

    RLT.partition_region = partition_region_watershed  # drop-in: process_volume/validate_holdout/
                                                        # neighbour_region_and_candidates untouched

    xfer = RLT.load_xfer(Path(a.xfer))

    result = {"source": ("Q151b validation: scripts/transfer/refine_transfer_photo_watershed.py "
                          "-- real marker-controlled watershed on this specimen's own re-acquired "
                          "cryosection photograph gradient, seeded by Q147's Z-Anatomy transfer. "
                          f"registered {len(T)}/{len(idx)} real levels, gradient built from {n_ok}."),
              "specimen": a.specimen, "n_registered": len(T), "n_missing": len(missing)}

    if a.holdout:
        import time as _time
        t0 = _time.time()
        bt, blobt = RLT.read_bundle_dir(Path(a.target)) if Path(a.target).is_dir() else RLT.read_bundle_html(Path(a.target))
        target = RLT.meshes_by_id(bt, blobt)
        print(f"target bundle loaded in {_time.time()-t0:.1f}s, {len(target)} meshes", flush=True)
        modes = ["neighbor", "whole_limb"] if a.holdout_mode == "both" else [a.holdout_mode]
        result["modes"] = {}
        for mode in modes:
            t1 = _time.time()
            print(f"starting holdout mode={mode} ...", flush=True)
            rows, notes = RLT.validate_holdout(Path(a.volume), Path(a.labels), Path(a.mapping), origin,
                                                xfer, target, a.holdout, mode)
            print(f"holdout mode={mode} finished in {_time.time()-t1:.1f}s", flush=True)
            for r in rows:
                print(mode, r)
            dists = [r["centroid_dist_mm"] for r in rows if "centroid_dist_mm" in r]
            dices = [r["dice"] for r in rows if "dice" in r]
            summary = {"n": len(rows), "notes": notes, "rows": rows}
            if dists:
                summary["median_centroid_dist_mm"] = round(float(np.median(dists)), 1)
                summary["max_centroid_dist_mm"] = round(float(np.max(dists)), 1)
                summary["median_dice"] = round(float(np.median(dices)), 3) if dices else None
                print(f"[{mode}] median {summary['median_centroid_dist_mm']}, max {summary['max_centroid_dist_mm']}, "
                      f"median dice {summary['median_dice']}")
            result["modes"][mode] = summary

    if a.report:
        Path(a.report).write_text(json.dumps(result, indent=1, default=str))
        print("wrote", a.report)

    if a.out:
        assign, notes, labelvol2, affine2, sampling2 = RLT.process_volume(Path(a.volume), Path(a.labels), Path(a.mapping), origin, xfer)
        out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
        verts, faces, structures = [], [], []
        voff = 0
        voxel_cm3 = float(np.prod(sampling2)) / 1000.0
        badge_med = result.get("ship_median_mm"); badge_max = result.get("ship_max_mm")
        for aid, mask in sorted(assign.items()):
            refined_vol = int(mask.sum()) * voxel_cm3
            q147_vol = RLT.mesh_volume_cm3(*xfer[aid]) if aid in xfer else 0.0
            if refined_vol < max(RLT.MIN_SHIP_VOL_CM3, RLT.MIN_SHIP_VOL_FRACTION * q147_vol):
                notes[aid] = f"refined claim too small ({refined_vol:.2f} cm3 vs Q147's {q147_vol:.1f} cm3) -- not shipped"
                continue
            v, f = RLT.mesh_from_mask(mask, affine2, origin)
            if v is None:
                continue
            badge = (f"{BADGE_METHOD}; validation median {badge_med} mm, max {badge_max} mm."
                     if badge_med is not None else f"{BADGE_METHOD}.")
            v32 = v.astype(np.float32)
            structures.append({"atlas_id": aid, "source_structure": aid, "side": "right",
                                "source_file": f"{Path(a.volume).name}#photo_watershed",
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
                    "source_kind": "Q151b photograph-gradient watershed refinement of Q147 zanatomy transfer",
                    "vertex_count": int(len(V)), "triangle_count": int(len(Fc)),
                    "bbox_min_mm": [round(float(x), 4) for x in V.min(axis=0)] if len(V) else None,
                    "bbox_max_mm": [round(float(x), 4) for x in V.max(axis=0)] if len(V) else None,
                    "attribution": [f"{BADGE_METHOD} (scripts/transfer/refine_transfer_photo_watershed.py, Q151b)."],
                    "license": "CC-BY-SA-4.0", "structures": structures}
        (out / "manifest.json").write_text(json.dumps(manifest, indent=1))
        print(f"{out.name}: {len(structures)} shipped structures: {[s['atlas_id'] for s in structures]}")
        print("not shipped:", json.dumps({k: v for k, v in notes.items()}, indent=1))


if __name__ == "__main__":
    main()
