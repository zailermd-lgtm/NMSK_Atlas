"""Female LEFT forearm muscles from her FULL-RESOLUTION cryosection crops (Q62 step 1, left side). Rule-based; badged.

    python3 scripts/cryo/vhf_left_forearm_muscles_from_cryo.py --crops SCRATCH/vh_cryo_f \
        --bones build/vhf_left_forearm_bones.nii.gz \
        --out data/ct_sources/task_outputs/vhf_left_forearm_muscles_cryo.nii.gz --montage-dir SCRATCH/vh_cryo_f

The left counterpart of vhf_forearm_muscles_from_cryo.py (her rules, her watershed, her report format,
imported directly); what differs:

BONE SEED. Her right forearm seeds the bone tracker from her CT radius/ulna mesh sections (ct_vhf_armb),
which does not exist for the left arm (outside her CT's field of view, Q30/Q39). Her left forearm bones
were instead segmented directly IN the photographs by colour threshold (Q64 Phase 3,
scripts/cryo/vhf_left_forearm_segment_phase3.py -> build/vhf_left_forearm_bones.nii.gz, indexed
(Z, H, W) identically to arm_full_left.npy -- the same crop level j, no registration needed). That
per-slice mask seeds the SAME dt_bone()/track_bones() tracker used on the right, at an anchor level
picked inside the phase-3 volume's confident radius/ulna z-range (0-149 of 491): there is therefore no
CT-to-photo residual to report (both the seed and the tracked disc come from the same photographs).

Everything else -- island/muscle/bone classification, the radius-ulna frame, MARKER_RULES (unscaled,
same body), compartments(), the marker watershed on the fascial-septa top-hat, boundary_support scoring
and the merge-into-compartments fallback -- is imported unchanged from the right-arm module, because it
operates purely in per-level pixel space and is not handedness-specific.

Output: label volume (RAS, 0.5 x 0.5 x 1 mm) for `ingest_volume_geometry.py convert`, label key, subject
mapping, report, montage.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import nibabel as nib
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
from skimage.morphology import white_tophat, disk

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.cryo.vhf_forearm_muscles_from_cryo import (  # noqa: E402
    PX, MARKER_RULES, SEED_PX, GROUP_ID, BADGE as _BADGE, ArmCrops, island_mask, classes, pale_filled,
    dt_bone, bone_mask, bone_frame, marker_positions, level_fraction, snap, compartments, split_level,
    boundary_support, level_region, palette)

BADGE = _BADGE
SOURCE = ("U.S. National Library of Medicine, The Visible Human Project (public domain), female cryosections at full "
          "resolution (0.33 mm) via the NCI Imaging Data Commons; her left forearm bones (Q64 Phase 3, colour "
          "threshold in the same photographs) seed the bone tracker. Derived data "
          "(scripts/cryo/vhf_left_forearm_muscles_from_cryo.py), rule-based.")
BONE_LABEL = {"radius": 1, "ulna": 2}


# ----------------------------------------------------------------------------------------------- bone tracking (left)
def track_bones_left(crops, bones, j_anchor, j_lo, j_hi, log=print, merge_mm=15.0, lost_max=8):
    """Like track_bones() in the right-arm module, but seeded from the phase-3 pixel-space bone volume
    instead of a CT mesh section; residual is not tracked (no independent modality to compare to)."""
    out = {}
    L = crops.level(j_anchor); im = crops.image(j_anchor)
    cent = {}
    for b, lab in BONE_LABEL.items():
        m = np.asarray(bones[j_anchor]) == lab
        if not m.any():
            raise SystemExit(f"no phase-3 {b} mask at anchor level {j_anchor}")
        cent[b] = tuple(float(v) for v in ndi.center_of_mass(m))

    def one(j, prev, lost, first=False):
        L = crops.level(j); im = crops.image(j); ref = tuple(np.mean([prev["radius"], prev["ulna"]], axis=0))
        isl, er = island_mask(im, ref)
        if isl is None:
            return None
        cl = classes(im, isl); pale = pale_filled(cl, isl); dt = ndi.distance_transform_edt(pale); dist = ndi.distance_transform_edt(isl)
        rec = {"island": isl, "erode": er, "cl": cl, "im": im, "L": L, "found": {}, "ct": {}}
        for b in ("radius", "ulna"):
            h = dt_bone(dt, dist, prev[b], 9.0 if first else 6.0 + 2.0 * lost[b])
            if h is None:
                rec[b] = (prev[b][0], prev[b][1], 0.0, None); rec["found"][b] = False
            else:
                rec[b] = (h[0], h[1], h[2], bone_mask(pale, *h)); rec["found"][b] = True
            if j < bones.shape[0]:
                m = np.asarray(bones[j]) == BONE_LABEL[b]
                if m.any():
                    rec["ct"][b] = tuple(float(v) for v in ndi.center_of_mass(m))
        return rec

    rec = one(j_anchor, cent, {"radius": 0, "ulna": 0}, first=True)
    if rec is None or not all(rec["found"].values()):
        raise SystemExit("bones not found in the photograph at the anchor level")
    out[j_anchor] = rec
    for rng in (range(j_anchor - 1, j_lo - 1, -1), range(j_anchor + 1, j_hi + 1)):
        prev = {b: out[j_anchor][b][:2] for b in ("radius", "ulna")}; lost = {"radius": 0, "ulna": 0}
        for j in rng:
            r = one(j, prev, lost)
            if r is None:
                log(f"  bone track stops at level {j} (no island)"); break
            for b in ("radius", "ulna"):
                if r["found"][b]:
                    prev[b] = r[b][:2]; lost[b] = 0
                else:
                    lost[b] += 1
            if max(lost.values()) > lost_max:
                log(f"  bone track stops at level {j} (bone lost)"); break
            if np.hypot(prev["radius"][0] - prev["ulna"][0], prev["radius"][1] - prev["ulna"][1]) * PX < merge_mm:
                log(f"  bone track stops at level {j} (discs merge)"); break
            out[j] = r
    return out


def segment_bounds_left(track, bones):
    """Proximal end: the first tracked level where the phase-3 radius label has a section (its top is the
    radial head); distal end: the last tracked level."""
    js = sorted(track)
    top = [j for j in js if j < bones.shape[0] and (np.asarray(bones[j]) == BONE_LABEL["radius"]).any() and all(track[j]["found"].values())]
    return (min(top), max(js)) if top else (None, None)


def level_frame_left(t, orient_prev):
    U = np.array(t["ulna"][:2]); R = np.array(t["radius"][:2]); isl = t["island"]
    dist_out, idx = ndi.distance_transform_edt(isl, return_indices=True)
    um = t["ulna"][3]
    if um is not None and um.any():
        ys, xs = np.where(um); k = np.argmin(dist_out[ys, xs]); skin = np.array([idx[0][ys[k], xs[k]], idx[1][ys[k], xs[k]]], float) - U
    else:
        ui, uj = int(round(U[0])), int(round(U[1])); skin = np.array([idx[0][ui, uj], idx[1][ui, uj]], float) - U
    e, n, d = bone_frame(U, R, skin)
    if orient_prev is not None and np.dot(n, orient_prev) < 0:
        n = -n
    return U, R, e, n, d


def run(a, log=print):
    crops = ArmCrops(a.crops, side="left")
    bones = np.asarray(nib.load(a.bones).dataobj).astype(np.uint8)
    cache = Path(a.cache) if getattr(a, "cache", None) else None
    if cache and cache.exists():
        import pickle; track = pickle.load(open(cache, "rb")); log(f"bone track from cache {cache}")
    else:
        track = track_bones_left(crops, bones, a.anchor, a.j_lo, a.j_hi, log)
        if cache:
            import pickle; pickle.dump(track, open(cache, "wb"), protocol=4)
    j_top, j_bot = segment_bounds_left(track, bones)
    if j_top is None:
        raise SystemExit("no level with two separate bone discs")
    log(f"segment levels {j_top}..{j_bot}  (atlas y {crops.level(j_top)['y']:.0f} .. {crops.level(j_bot)['y']:.0f})")
    names = list(MARKER_RULES); ids = {nm: i + 1 for i, nm in enumerate(names)}; groups = {nm: MARKER_RULES[nm][5] for nm in names}
    labels_by_level = {}; area = {nm: 0.0 for nm in names}; unassigned = 0.0; orient_prev = None; frames = {}; support = {}
    for j in range(j_top, j_bot + 1):
        t = track.get(j)
        if t is None:
            continue
        U, R, e, n, d = level_frame_left(t, orient_prev); orient_prev = n; ru, rr = t["ulna"][2], t["radius"][2]
        f = level_fraction(j, j_top, j_bot); frames[j] = {"U": U.tolist(), "R": R.tolist(), "e": e.tolist(), "n": n.tolist(), "f": round(f, 3)}
        region = level_region(t); comp = compartments(region.shape, U, R, ru, rr, e, n)
        th = white_tophat(t["im"].max(-1).astype(np.float32), disk(4))
        seeds = marker_positions(U, R, ru, rr, e, n, f); frames[j]["seeds"] = {nm: [float(p[0]), float(p[1])] for nm, p in seeds.items()}
        cur, left = split_level(th, region, comp, seeds, ids, groups)
        for nm, m in cur.items():
            area[nm] += m.sum() * PX * PX
        unassigned += left.sum() * PX * PX
        for pair, v in boundary_support(th, cur, ids).items():
            support.setdefault(pair, []).append((j,) + v)
        lab = np.zeros(region.shape, np.uint8)
        for nm, m in cur.items():
            lab[m] = ids[nm]
        labels_by_level[j] = lab
        if j % 20 == 0:
            log(f"  level {j} f={f:.2f} y={t['L']['y']:.0f} regions={len(cur)} unassigned={left.sum() * PX * PX:.0f} mm2")
    return crops, track, (j_top, j_bot), labels_by_level, ids, area, unassigned, frames, support


def to_volume(crops, labels_by_level, dx=0.5):
    js = sorted(labels_by_level); ext = []
    for j in js:
        lab = labels_by_level[j]; ys, xs = np.where(lab > 0)
        if len(ys) == 0:
            continue
        L = crops.level(j); x, y = crops.px_to_ras(L, [ys.min(), ys.max()], [xs.min(), xs.max()]); ext.append((x.min(), x.max(), y.min(), y.max()))
    ext = np.array(ext); x0, x1 = ext[:, 0].min() - 2, ext[:, 1].max() + 2; y0, y1 = ext[:, 2].min() - 2, ext[:, 3].max() + 2
    zt = np.array([crops.level(j)["z_true"] for j in js]); z0, z1 = np.floor(zt.min()), np.ceil(zt.max())
    nx, ny, nz = int(np.ceil((x1 - x0) / dx)) + 1, int(np.ceil((y1 - y0) / dx)) + 1, int(z1 - z0) + 1
    vol = np.zeros((nx, ny, nz), np.uint8); gx = x0 + dx * np.arange(nx); gy = y0 + dx * np.arange(ny)
    for k in range(nz):
        z = z0 + k; j = js[int(np.argmin(np.abs(zt - z)))]
        if abs(zt[js.index(j)] - z) > 1.0:
            continue
        L = crops.level(j); lab = labels_by_level[j]
        pc = ((350.0 - gx - 110 - L["CS"]) / 0.99) * 3 - L["w"][2]; pr = (405 - 1 - (240.0 - gy - L["RS"]) / 0.99) * 3 - L["w"][0]
        ci = np.round(pc).astype(int); ri = np.round(pr).astype(int)
        okc = (ci >= 0) & (ci < lab.shape[1]); okr = (ri >= 0) & (ri < lab.shape[0])
        sl = np.zeros((nx, ny), np.uint8)
        sub = lab[np.ix_(ri[okr], ci[okc])]
        sl[np.ix_(okc, okr)] = sub.T
        vol[:, :, k] = sl
    aff = np.array([[dx, 0, 0, x0], [0, dx, 0, y0], [0, 0, 1.0, z0], [0, 0, 0, 1]])
    return vol, aff


def montage(crops, track, labels_by_level, ids, frames, levels, path, colors):
    tiles = []
    for j in levels:
        t = track.get(j); lab = labels_by_level.get(j)
        if t is None or lab is None:
            continue
        im = t["im"].copy(); isl = t["island"]; ys, xs = np.where(isl)
        r0, r1, c0, c1 = max(0, ys.min() - 6), ys.max() + 6, max(0, xs.min() - 6), xs.max() + 6
        for nm, l in ids.items():
            m = lab == l
            if m.any():
                edge = m & ~ndi.binary_erosion(m, iterations=2); im[edge] = colors[l]
        for b in ("radius", "ulna"):
            if t[b][3] is not None:
                e = t[b][3] & ~ndi.binary_erosion(t[b][3], iterations=2); im[e] = (255, 255, 255)
        sub = Image.fromarray(im[r0:r1, c0:c1]); dr = ImageDraw.Draw(sub)
        fr = frames.get(j)
        if fr:
            U = np.array(fr["U"]) - (r0, c0); R = np.array(fr["R"]) - (r0, c0); n = np.array(fr["n"])
            dr.line([(U[1], U[0]), (R[1], R[0])], fill=(255, 255, 255), width=1)
            M = (U + R) / 2; dr.line([(M[1], M[0]), (M[1] + n[1] * 30, M[0] + n[0] * 30)], fill=(0, 255, 255), width=2)
        for nm, p in (fr.get("seeds", {}) if fr else {}).items():
            y, x = p[0] - r0, p[1] - c0; dr.line([(x - 4, y), (x + 4, y)], fill=colors[ids.get(nm, 0)], width=2); dr.line([(x, y - 4), (x, y + 4)], fill=colors[ids.get(nm, 0)], width=2)
        dr.text((3, 3), f"j{j} y{t['L']['y']:.0f} f{fr['f'] if fr else '-'}", fill=(255, 255, 0))
        for nm, l in ids.items():
            m = lab[r0:r1, c0:c1] == l
            if m.sum() > 60:
                cy, cx = np.mean(np.where(m), axis=1); dr.text((cx - 8, cy - 4), nm.split("_")[0][:3] + "".join(w[0] for w in nm.split("_")[1:]), fill=colors[l])
        tiles.append(sub)
    if not tiles:
        return None
    cols = 3; rows = (len(tiles) + cols - 1) // cols; tw = max(t.width for t in tiles); th = max(t.height for t in tiles)
    out = Image.new("RGB", (cols * tw, rows * th))
    for i, t in enumerate(tiles):
        out.paste(t, ((i % cols) * tw, (i // cols) * th))
    out.save(path); return str(path)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--crops", required=True, help="SCRATCH/vh_cryo_f (arm_full_left.npy, arm_full_bbox.json)")
    ap.add_argument("--bones", default=str(REPO / "build/vhf_left_forearm_bones.nii.gz"))
    ap.add_argument("--anchor", type=int, default=60, help="crop level (index into arm_full_left.npy) where the phase-3 bone volume seeds the tracker")
    ap.add_argument("--j-lo", type=int, default=0); ap.add_argument("--j-hi", type=int, default=490)
    ap.add_argument("--out", default=str(REPO / "data/ct_sources/task_outputs/vhf_left_forearm_muscles_cryo.nii.gz"))
    ap.add_argument("--labels-out", default=str(REPO / "mappings/vhf_left_forearm_muscles_labels.json"))
    ap.add_argument("--mapping-out", default=str(REPO / "mappings/subjects/ct_vhf_left_forearm_volume_mapping.json"))
    ap.add_argument("--montage-dir", default=None); ap.add_argument("--montage-levels", default="")
    ap.add_argument("--cache", default=None)
    ap.add_argument("--merge", default=str(REPO / "scripts/cryo/vhf_left_forearm_merge.json"))
    a = ap.parse_args(argv)
    crops, track, (j_top, j_bot), labels_by_level, ids, area, unassigned, frames, support = run(a)
    merge_raw = json.load(open(a.merge)) if a.merge and Path(a.merge).exists() else {}
    merge = {k: (v["members"] if isinstance(v, dict) else v) for k, v in merge_raw.items() if not k.startswith("_")}
    merge_note = {k: v.get("note", "") for k, v in merge_raw.items() if isinstance(v, dict)}
    final_ids = dict(ids); final_names = {l: nm for nm, l in ids.items()}; remap = np.arange(max(ids.values()) + 1, dtype=np.uint8)
    for comp, members in merge.items():
        keep = ids[members[0]]
        for mm in members:
            remap[ids[mm]] = keep; final_ids.pop(mm, None)
        final_ids[comp] = keep; final_names[keep] = comp
        for mm in members[1:]:
            final_names.pop(ids[mm], None)
    for j in labels_by_level:
        labels_by_level[j] = remap[labels_by_level[j]]
    vol, aff = to_volume(crops, labels_by_level)
    vox = float(abs(np.linalg.det(aff[:3, :3])))
    vols = {nm: round(float((vol == l).sum() * vox / 1000.0), 1) for nm, l in sorted(final_ids.items(), key=lambda kv: kv[1])}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    nib.save(nib.Nifti1Image(vol, aff), a.out)
    colors = palette(len(ids)); mont = []
    if a.montage_dir:
        levels = [int(t) for t in a.montage_levels.split(",")] if a.montage_levels else [int(round(j_top + (j_bot - j_top) * q)) for q in (0.05, 0.2, 0.4, 0.6, 0.8, 0.95)]
        p = montage(crops, track, labels_by_level, final_ids, frames, levels, Path(a.montage_dir) / "forearm_muscles_left.png", colors)
        if p:
            mont.append(p)
    membership = {comp: members for comp, members in merge.items()}
    supp = {f"{p[0]}|{p[1]}": {"levels": len(v), "median_ridge_ratio": round(float(np.median([x[2] for x in v])), 2),
                               "frac_levels_ratio_ge_1.8": round(float(np.mean([x[2] >= 1.8 for x in v])), 2),
                               "contact_mm": round(float(np.mean([x[1] for x in v])) * PX, 1)} for p, v in sorted(support.items()) if len(v) >= 5}
    report = {"_README": [f"Female LEFT forearm muscles from her full-resolution cryosections ({Path(__file__).name}); {BADGE}. "
                          "Bone tracker seeded from the phase-3 pixel-space bone volume (same photographs, no cross-modality "
                          "registration); markers by the same textbook position rules as her right forearm; boundaries by a "
                          "marker watershed on the pale fascial septa; muscles the photographs do not separate merged into compartments."],
              "source": SOURCE, "badge": BADGE, "segment_levels": [j_top, j_bot],
              "segment_atlas_y": [round(crops.level(j_top)["y"], 1), round(crops.level(j_bot)["y"], 1)],
              "voxel_mm": [float(aff[0, 0]), float(aff[1, 1]), float(aff[2, 2])],
              "volumes_cm3": vols, "unassigned_muscle_cm3": round(unassigned / 1000.0, 1), "merged_compartments": membership,
              "montages": mont, "labels": {str(l): nm for l, nm in sorted(final_names.items())},
              "boundary_support": supp}
    Path(str(a.out).replace(".nii.gz", "_report.json")).write_text(json.dumps(report, indent=1))
    key = {"_README": [f"Label id -> structure for the Visible Human FEMALE LEFT forearm muscle volume ({Path(__file__).name}). A KEY, not data. {BADGE}: "
                       "see the script docstring for the rule; compartments are muscles the photographs do not separate (mapped to null)."],
           "source": SOURCE, "task": "vhf_left_forearm_muscles", "version": "2026-09-18", "badge": BADGE,
           "labels": {str(l): nm for l, nm in sorted(final_names.items())}, "merged_compartments": membership}
    Path(a.labels_out).write_text(json.dumps(key, indent=1))
    entries = []
    for l, nm in sorted(final_names.items()):
        if nm in merge:
            entries.append({"label": l, "source_structure": nm, "side": "left", "status": "no_atlas_entity", "atlas_id": None,
                            "relationship": "no_usable_label", "note": f"{BADGE}; compartment holding {', '.join(merge[nm])} ({vols.get(nm, 0)} cm3), not split: "
                            f"{merge_note.get(nm, 'the photographs show no septum the watershed could follow between them at most levels')}",
                            "candidates": [m + "_l" for m in merge[nm]]})
        else:
            entries.append({"label": l, "source_structure": nm, "side": "left", "status": "review", "atlas_id": None, "relationship": "exact",
                            "note": f"{BADGE}: position-rule marker in the radius-ulna frame, boundary by the marker watershed on her fascial septa; {vols.get(nm, 0)} cm3. "
                                    "NOT yet confirmed against a textbook volume range -- review before setting atlas_id.",
                            "candidates": [nm + "_l"]})
    Path(a.mapping_out).write_text(json.dumps({"_README": ["Review every entry before running convert.", "Set 'atlas_id' to the correct entity, or null to skip the label.",
                                                            "'status' is advisory; convert reads 'atlas_id' only."],
                                                "subject": "ct_vhf_left_forearm", "source_volume": str(Path(a.out).resolve()), "label_map": "vhf_left_forearm_muscles",
                                                "entries": entries}, indent=2))
    print(json.dumps({"segment": [j_top, j_bot], "volumes_cm3": vols, "unassigned_cm3": round(unassigned / 1000, 1), "montages": mont}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
