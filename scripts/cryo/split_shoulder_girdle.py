"""Split the rule-based shoulder-girdle labels of the Visible Human female / male (Q62 step 2).

    python3 scripts/cryo/split_shoulder_girdle.py --body f      # female, boundaries refined on her photographs
    python3 scripts/cryo/split_shoulder_girdle.py --body m      # male, geometric rule only (his 1 mm frame is gone)

(a) The rotator-cuff run (vh?_rotator_cuff_cryo.nii.gz) put every muscle voxel on the DORSAL scapular surface
    below the spine level under one label, "infraspinatus" (female 316 / 297 cm3, male 353 / 340; a real
    infraspinatus is 130-200 cm3), i.e. teres minor and the dorsal part of teres major were swept into it, and its
    "ventral" rule put the belly of teres major, which lies LATERAL of the lateral border on its way to the anterior
    humerus, under subscapularis. This script cuts infraspinatus / teres minor / teres major apart.
(b) The pectoralis-minor / rhomboid run (vh?_pecminor_rhomboids_cryo.nii.gz) left the rhomboids as one mass per
    side; it is cut into rhomboid major and minor.

Anatomical rule encoded (Standring S (ed.), Gray's Anatomy, 42nd ed., ch. 48 'Shoulder girdle and arm';
Terminologia Anatomica A04.6.02.010-012, A04.3.01.012-013):
  * teres MAJOR arises from the dorsal surface of the inferior angle and the lower third of the lateral border and
    inserts on the medial lip of the intertubercular sulcus (anterior humerus); its belly passes below and
    ANTERIOR to teres minor (the long head of triceps between them);
  * teres MINOR arises from the upper two thirds of the lateral border (dorsal) and inserts on the lowest facet
    of the greater tubercle (posterior humerus);
  * INFRASPINATUS fills the infraspinous fossa medial to both;
  * rhomboid MINOR arises from C7-T1 spinous processes and inserts on the medial border at the root of the
    scapular spine; rhomboid MAJOR from T2-T5 spinous processes, below it; the fibres run downward-lateral.
Per axial level below the scapular spine, with P = the lateral border point of the scapula section, s = distance
from P along the blade (medial > 0) and t = distance dorsal of the blade axis: MARKERS are infraspinatus on the
fossa (s > 25 mm), teres minor along the lateral border (-12 < s < 15 mm, dorsal) at levels above the inferior-angle
third of the lateral border, teres major at / below that third (s < 30 mm) and, above it, lateral of the border and
at / anterior of the blade axis (its path to the anterior humerus). The lateral border spans the inferior angle to the
glenoid level (lowest level where the humeral head touches the scapula); its lower third is the teres major
origin. The merged voxels are then assigned to the markers by a marker watershed: on the female on the white
top-hat of her photographs' brightness (fascial lines are ridges), as in scripts/transfer/refine_transfer_to_septa.py;
on the male on a flat surface (nearest marker along the muscle mass). Voxels of the SUBSCAPULARIS label lateral of
the lateral border (below the glenoid level) are taken into the working mass as well: they are teres major's belly
(subscapularis lies on the costal surface, medial of the border); they are counted in the report, and the cuff
subject's subscapularis still contains them, so this subject must be listed before the cuff subject.
The rhomboid mass is cut by the line from the T1 spinous process (most posterior T1 voxel) to the spine root (the
medial border at the spine level, 0.78 of the scapula's height as in the cuff rule) in the coronal projection:
above -> minor, below -> major (the cut follows the fibre direction, obliquely downward-lateral).

Bone geometry comes from the TotalSegmentator CT labels (vh?_total.nii.gz: scapula, humerus, T1), resampled into the
photograph frame exactly as the source runs did (female: per-side column shift of the deltoid registration).
Rule-based; boundaries are rules (male) or rules refined to photographed fascial lines (female), not traced
fascia; badge it "rule-based"; volumes before / after are recorded in the report next to the volume.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

SCRATCH = Path("/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad")
H, W, OFF = 480, 700, 110
SPINE_FRACTION = 0.78          # spine level = inferior angle + 0.78 x height (the cuff runs' rule)
FOSSA_MM, MINOR_LAT_MM, MINOR_MED_MM, MAJOR_MM, MAJOR_DORSAL_MM = 25, -12, 12, 30, 10
GLENOID_GAP_MM = 6
LABELS = ("infraspinatus", "teres_minor", "teres_major", "rhomboid_major", "rhomboid_minor")
PLAUSIBLE_CM3 = {"infraspinatus": (100, 200), "teres_minor": (20, 45), "teres_major": (60, 130),
                 "rhomboid_major": (50, 130), "rhomboid_minor": (10, 40)}
BODY = {
    "f": dict(total="vhf_total.nii.gz", cuff="vhf_rotator_cuff_cryo.nii.gz", pmr="vhf_pecminor_rhomboids_cryo.nii.gz",
              frame=SCRATCH / "vh_cryo_f", shift={"right": (0, 11), "left": (0, -15)}, subject="ct_vhf_shsp",
              origin="7.769,-885.229,14.137", who="female"),
    "m": dict(total="vhm_total.nii.gz", cuff="vhm_rotator_cuff_cryo.nii.gz", pmr="vhm_pecminor_rhomboids_cryo.nii.gz",
              frame=None, shift={"right": (0, 0), "left": (0, 0)}, subject="ct_vhm_shsp",
              origin="-6.035,-895.476,4.787", who="male"),
}
CUFF_IDS = {"right": {"infra": 2, "subscap": 3}, "left": {"infra": 5, "subscap": 6}}
RHOMB_IDS = {"right": 3, "left": 4}
SOURCE = ("U.S. National Library of Medicine, The Visible Human Project (public domain), {who} colour cryosections and CT "
          "via the NCI Imaging Data Commons; TotalSegmentator v2.18.0 scapula / humerus / vertebra labels as anchors. "
          "Rules from Standring S (ed.), Gray's Anatomy, 42nd ed., 'Shoulder girdle and arm'. Derived data "
          "(scripts/cryo/split_shoulder_girdle.py).")


# ----------------------------------------------------------------------------------------------- pure rule
def slice_frame(scap2d, lateral_sign):
    """Lateral border point P (row, col), medial unit vector u along the blade and dorsal unit normal n of one
    axial scapula section. lateral_sign = -1 when lateral is towards smaller columns (patient's right)."""
    ys, xs = np.nonzero(scap2d)
    lat = xs.min() if lateral_sign < 0 else xs.max()
    tip = np.abs(xs - lat) <= 5
    P = np.array([ys[tip].mean(), xs[tip].mean()])
    C = np.array([ys.mean(), xs.mean()])
    u = C - P
    if np.hypot(*u) < 1e-6:
        u = np.array([0.0, -float(lateral_sign)])
    u /= np.hypot(*u)
    n = np.array([u[1], -u[0]])          # perpendicular; dorsal = larger row (posterior)
    if n[0] < 0:
        n = -n
    return P, u, n


def side_levels(scap, hum, gap_mm=GLENOID_GAP_MM):
    """Levels (slice indices) of one side from the scapula / humerus masks (z, row, col): inferior angle z_ia, top
    z_top, spine level z_spine (0.78 of the height), glenoid level z_gl (lowest slice where the humerus lies within
    gap_mm of the scapula; the spine level when the humerus is absent) and z_tm, the top of the lower third of the
    lateral border (teres major origin)."""
    from scipy import ndimage as ndi
    zs = np.nonzero(scap.any(axis=(1, 2)))[0]
    z_ia, z_top = int(zs.min()), int(zs.max())
    z_spine = z_ia + SPINE_FRACTION * (z_top - z_ia)
    z_gl = None
    for z in range(z_ia, z_top + 1):
        if scap[z].any() and hum[z].any():
            if ndi.distance_transform_edt(~scap[z])[hum[z]].min() <= gap_mm:
                z_gl = z
                break
    if z_gl is None:
        z_gl = z_spine
    z_tm = z_ia + (z_gl - z_ia) / 3.0
    return dict(z_ia=z_ia, z_top=z_top, z_spine=float(z_spine), z_gl=float(z_gl), z_tm=float(z_tm))


def teres_markers(merged, scap, lateral_sign, lv):
    """Rule markers inside the merged dorsal mass (z, row, col): 1 infraspinatus, 2 teres minor, 3 teres major."""
    mk = np.zeros(merged.shape, np.uint8)
    rr, cc = np.mgrid[0:merged.shape[1], 0:merged.shape[2]].astype(np.float32)
    for z in np.nonzero(merged.any(axis=(1, 2)))[0]:
        if not scap[z].any():
            continue
        P, u, n = slice_frame(scap[z], lateral_sign)
        s = (rr - P[0]) * u[0] + (cc - P[1]) * u[1]
        t = (rr - P[0]) * n[0] + (cc - P[1]) * n[1]
        m = merged[z]
        infra = m & (s > FOSSA_MM) & (t > -5) & (z > lv["z_ia"] + 20)
        if z > lv["z_gl"] + 5:                       # above the glenoid: tendon zone of the cuff, infraspinatus
            infra = m.copy()
        minor = np.zeros_like(m)
        if lv["z_tm"] <= z <= lv["z_gl"] + 5:
            minor = m & (s > MINOR_LAT_MM) & (s < MINOR_MED_MM) & (t > 0)           # on the dorsal lateral border
            if z >= lv["z_gl"] - 15:                                                # ... and to the greater tubercle
                minor |= m & (s <= MINOR_LAT_MM) & (t >= MAJOR_DORSAL_MM)
        if z < lv["z_tm"]:
            major = m & (s < MAJOR_MM)                                              # inferior-angle origin
        else:
            major = m & (z < lv["z_gl"] - 5) & (s < -5) & (t < MAJOR_DORSAL_MM)     # anterior of teres minor
            if z < lv["z_gl"] - 15:
                major |= m & (s < -8)                                               # the belly lateral of the border
        mk[z][infra] = 1
        mk[z][minor] = 2
        mk[z][major] = 3
    return mk


def assign_to_markers(merged, markers, elevation=None):
    """Marker watershed of the merged mass onto the markers (flat elevation = nearest marker along the mass)."""
    from skimage.segmentation import watershed
    el = np.zeros(merged.shape, np.float32) if elevation is None else elevation
    lab = watershed(el, markers.astype(np.int32), mask=merged).astype(np.uint8)
    return lab


def rhomboid_cut(mask, p_sp, p_root):
    """Cut a rhomboid mass (z, row, col) by the straight line from the T1 spinous process p_sp = (z, col) to the
    spine root p_root = (z, col) in the coronal projection: returns the MINOR part (above the line)."""
    zz, _, cc = np.mgrid[0:mask.shape[0], 0:mask.shape[1], 0:mask.shape[2]].astype(np.float32)
    dz, dc = p_root[0] - p_sp[0], p_root[1] - p_sp[1]
    if abs(dc) < 1e-6:
        z_line = np.full_like(cc, p_sp[0])
    else:
        z_line = p_sp[0] + (cc - p_sp[1]) * dz / dc
    return mask & (zz > z_line)


# ----------------------------------------------------------------------------------------------- data
def main():
    import nibabel as nib
    from scipy import ndimage as ndi
    from PIL import Image

    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--body", choices=("f", "m"), required=True)
    ap.add_argument("--no-photo", action="store_true", help="female: flat watershed instead of the photograph top-hat")
    ap.add_argument("--out", default=None)
    a = ap.parse_args()
    B = BODY[a.body]; T = REPO / "data/ct_sources/task_outputs"
    out_path = Path(a.out) if a.out else T / f"vh{a.body}_shoulder_split_cryo.nii.gz"
    key = json.load(open(REPO / "mappings/totalsegmentator_labels.json"))["labels"]
    labs = {v: int(k) for k, v in key.items()}
    tot = nib.load(T / B["total"]); totd = np.asarray(tot.dataobj); zT0 = float(tot.affine[2, 3])
    cuff = nib.load(T / B["cuff"]); cd = np.asarray(cuff.dataobj).astype(np.uint8); zC0 = float(cuff.affine[2, 3])
    pmr = nib.load(T / B["pmr"]); rd = np.asarray(pmr.dataobj).astype(np.uint8); zR0 = float(pmr.affine[2, 3])
    rgb = None
    if B["frame"] and not a.no_photo:
        rgb = np.load(B["frame"] / "cryo_frame_rgb.npy", mmap_mode="r"); zF0 = json.load(open(B["frame"] / "frame.json"))["z0"]

    def frame_ct(z, shift):
        """CT label slice at RAS z in the photograph frame (row, col), shifted like the source run."""
        kk = int(round(z - zT0)); f = np.zeros((H, W), np.int32)
        if 0 <= kk < totd.shape[2]:
            f[:, OFF:OFF + 480] = ndi.zoom(totd[:, :, kk], 480 / 512, order=0).T
        return np.roll(np.roll(f, shift[0], 0), shift[1], 1)

    def vol_slice(arr, z0, z):
        k = int(round(z - z0))
        return arr[:, :, k].T if 0 <= k < arr.shape[2] else np.zeros((H, W), arr.dtype)

    # common z range: the scapulae's
    zlo = min(zT0 + np.nonzero((totd == labs[f"scapula_{s}"]).any(axis=(0, 1)))[0].min() for s in ("right", "left"))
    zhi = max(zT0 + np.nonzero((totd == labs[f"scapula_{s}"]).any(axis=(0, 1)))[0].max() for s in ("right", "left"))
    zlo, zhi = int(zlo) - 5, int(zhi) + 5
    zs = np.arange(zlo, zhi + 1); nz = len(zs)
    out = np.zeros((nz, H, W), np.uint8)
    ids = {f"{nm}_{sd}": i + 1 for i, (sd, nm) in enumerate((sd, nm) for sd in ("right", "left") for nm in LABELS)}
    report = {"source": SOURCE.format(who=B["who"]), "body": B["who"], "method": {}, "levels_mm": {}, "volumes_cm3": {},
              "taken_from_subscapularis_cm3": {}, "montage": {}, "notes": []}
    tiles_side = {}
    for side, lsign in (("right", -1), ("left", 1)):
        sh = B["shift"][side]; sc_id, hu_id = labs[f"scapula_{side}"], labs[f"humerus_{side}"]
        scap = np.zeros((nz, H, W), bool); hum = np.zeros((nz, H, W), bool)
        infra = np.zeros((nz, H, W), bool); subsc = np.zeros((nz, H, W), bool); rhom = np.zeros((nz, H, W), bool)
        for i, z in enumerate(zs):
            t = frame_ct(z, sh); scap[i] = t == sc_id; hum[i] = t == hu_id
            c = vol_slice(cd, zC0, z); infra[i] = c == CUFF_IDS[side]["infra"]; subsc[i] = c == CUFF_IDS[side]["subscap"]
            rhom[i] = vol_slice(rd, zR0, z) == RHOMB_IDS[side]
        lv = side_levels(scap, hum)
        report["levels_mm"][side] = {k: float(zs[0] + v) for k, v in lv.items()}
        # teres major's belly under the subscapularis label: lateral of the lateral border, below the glenoid level
        taken = np.zeros_like(subsc)
        rr, cc = np.mgrid[0:H, 0:W].astype(np.float32)
        for i in range(nz):
            if not (subsc[i].any() and scap[i].any()) or i >= lv["z_gl"] - 10:
                continue
            P, u, n = slice_frame(scap[i], lsign)
            s = (rr - P[0]) * u[0] + (cc - P[1]) * u[1]
            taken[i] = subsc[i] & (s < -5)
        merged = infra | taken
        # crop for speed
        zz, yy, xx = np.nonzero(merged)
        box = (slice(zz.min(), zz.max() + 1), slice(max(yy.min() - 2, 0), yy.max() + 3), slice(max(xx.min() - 2, 0), xx.max() + 3))
        M = merged[box]; SC = scap[box]
        lvc = dict(lv); lvc.update({k: lv[k] - box[0].start for k in ("z_ia", "z_top", "z_spine", "z_gl", "z_tm")})
        mk = teres_markers(M, SC, lsign, lvc)
        elev = None
        if rgb is not None:
            from skimage.morphology import white_tophat, disk
            elev = np.zeros(M.shape, np.float32)
            for i in range(M.shape[0]):
                im = np.asarray(rgb[int(zs[box[0].start + i] - zF0)])[box[1], box[2]]
                elev[i] = white_tophat(im.max(-1).astype(np.float32), disk(4))
        lab = assign_to_markers(M, mk, elev)
        report["method"][side] = ("markers by rule, boundaries by marker watershed on the white top-hat of her photographs"
                                  if elev is not None else "markers by rule, boundaries by flat marker watershed (nearest marker)")
        for j, nm in enumerate(("infraspinatus", "teres_minor", "teres_major")):
            sub = out[box]; sub[lab == j + 1] = ids[f"{nm}_{side}"]
        # rhomboids: cut at the line T1 spinous process -> spine root
        t1 = totd == labs["vertebrae_T1"]
        ii, jj, kk = np.nonzero(t1)
        post = jj >= jj.max() - 2                       # most posterior voxels (largest j = smallest RAS y)
        z_sp = zT0 + kk[post].mean() - zs[0]
        col_sp = 350.0 - (240.0 - 0.9375 * ii[post].mean())
        z_root = int(round(lv["z_spine"]))
        ys_, xs_ = np.nonzero(scap[z_root]); col_root = float(xs_.max() if lsign < 0 else xs_.min())
        minor = None
        if rhom.any():
            minor = rhomboid_cut(rhom, (z_sp, col_sp), (float(z_root), col_root))
            out[minor] = ids[f"rhomboid_minor_{side}"]; out[rhom & ~minor] = ids[f"rhomboid_major_{side}"]
        report["levels_mm"][side].update({"t1_spinous_z": float(zs[0] + z_sp), "t1_spinous_x": 350.0 - col_sp,
                                          "spine_root_z": float(zs[0] + z_root), "spine_root_x": 350.0 - col_root})
        vb = {"infraspinatus_merged": round(infra.sum() / 1000, 1), "rhomboid_merged": round(rhom.sum() / 1000, 1)}
        va = {nm: round(float((out == ids[f"{nm}_{side}"]).sum()) / 1000, 1) for nm in LABELS}
        report["volumes_cm3"][side] = {"before": vb, "after": va}
        report["taken_from_subscapularis_cm3"][side] = round(taken.sum() / 1000, 1)
        for nm, (lo, hi) in PLAUSIBLE_CM3.items():
            if not lo <= va[nm] <= hi:
                report["notes"].append(f"{side} {nm} {va[nm]} cm3 outside the plausible {lo}-{hi}")
        print(side, lv, "before", vb, "after", va, "taken", report["taken_from_subscapularis_cm3"][side], flush=True)
        tiles_side[side] = (scap, hum, lv)

    # save the volume (frame RAS: col = 350 - x, row = 240 - y, z)
    nzs = np.nonzero(out.any(axis=(1, 2)))[0]; ka, kb = int(nzs.min()), int(nzs.max()) + 1
    aff = np.array([[-1, 0, 0, 350], [0, -1, 0, 240], [0, 0, 1, zs[0] + ka], [0, 0, 0, 1]], float)
    nib.save(nib.Nifti1Image(np.ascontiguousarray(out[ka:kb].transpose(2, 1, 0)), aff), out_path)

    # montage: 6 axial levels per side, photograph (female) or CT labels (male) with the split labels
    lut = {"infraspinatus": (80, 200, 255), "teres_minor": (255, 220, 40), "teres_major": (255, 80, 80),
           "rhomboid_major": (120, 255, 120), "rhomboid_minor": (255, 140, 255)}
    for side in ("right", "left"):
        scap, hum, lv = tiles_side[side]
        cols = slice(90, 450) if side == "right" else slice(250, 610)
        ks = np.nonzero((out[:, :, cols] > 0).any(axis=(1, 2)))[0]; tiles = []
        for i in np.linspace(ks.min() + 3, ks.max() - 3, 6).astype(int):
            if rgb is not None or (B["frame"] and a.no_photo):
                fr = np.load(B["frame"] / "cryo_frame_rgb.npy", mmap_mode="r") if rgb is None else rgb
                im = np.asarray(fr[int(zs[i] - json.load(open(B["frame"] / "frame.json"))["z0"])])[:, cols].copy()
            else:
                t = frame_ct(zs[i], (0, 0))[:, cols]; im = np.zeros(t.shape + (3,), np.uint8); im[t > 0] = (90, 90, 90)
            e = scap[i][:, cols]; im[e & ~ndi.binary_erosion(e)] = (255, 255, 255)
            e = hum[i][:, cols]; im[e & ~ndi.binary_erosion(e)] = (255, 255, 255)
            o = out[i][:, cols]
            for nm in LABELS:
                m = o == ids[f"{nm}_{side}"]
                im[m] = (0.45 * im[m] + 0.55 * np.array(lut[nm])).astype(np.uint8)
            ys, xs = np.nonzero(o > 0); r0, r1 = max(ys.min() - 30, 0), min(ys.max() + 30, H)
            im = im[r0:r1]; im[:2, :] = (255, 255, 255)
            tiles.append(im)
        h = max(t.shape[0] for t in tiles); w = max(t.shape[1] for t in tiles)
        mont = np.concatenate([np.pad(t, ((0, h - t.shape[0]), (0, w - t.shape[1]), (0, 0))) for t in tiles], axis=1)
        p = str(out_path).replace(".nii.gz", f"_{side}.png"); Image.fromarray(mont).save(p); report["montage"][side] = p
    report["legend"] = {nm: f"rgb{lut[nm]}" for nm in LABELS}
    report["_README"] = [f"Shoulder-girdle split of the {B['who']}: infraspinatus / teres minor / teres major and rhomboid major / minor "
                         "by the rules in scripts/cryo/split_shoulder_girdle.py. Rule-based, derived data; badge it."]
    rep_path = str(out_path).replace(".nii.gz", "_report.json"); Path(rep_path).write_text(json.dumps(report, indent=1))

    # label key + subject mapping
    labels = {"_README": [f"Label id -> structure name for the Visible Human {B['who'].upper()} shoulder-girdle split volume "
                          "(scripts/cryo/split_shoulder_girdle.py), plus the mapping onto atlas entities. A KEY, not data.",
                          "Rule-based: the merged 'infraspinatus' of the rotator-cuff run (plus the subscapularis-labelled voxels "
                          "lateral of the lateral border) assigned to infraspinatus / teres minor / teres major by markers from "
                          "the scapula's lateral border and inferior-angle third, boundaries by marker watershed "
                          + ("on her photographs' fascial lines; " if rgb is not None else "on a flat surface (nearest marker); ")
                          + "the rhomboid mass cut at the line T1 spinous process -> spine root. Boundaries are rules, not traced "
                          "fascia; badge it 'rule-based'. This subject must be listed BEFORE the cuff subject (its teres major "
                          "voxels are still inside the cuff subject's subscapularis label)."],
              "source": SOURCE.format(who=B["who"]), "task": f"vh{a.body}_shoulder_split", "version": "2026-09-14",
              "labels": {str(v): k for k, v in ids.items()}, "atlas": {}}
    entries = []
    for name, lid in ids.items():
        nm, sd = name.rsplit("_", 1); aid = f"{nm}_{sd[0]}"
        va = report["volumes_cm3"][sd]["after"][nm]
        note = f"{va} cm3; rule-based split (see _README)."
        if nm.startswith("rhomboid") and a.body == "f":
            # her rhomboid mass (62 / 44 cm3, paraspinal patches, see vhf_pecminor_rhomboids) was never shipped, and the
            # cut gives minor > major: the split is not supported by her data; the labels stay in the volume, unshipped.
            aid = None
            note = (f"{va} cm3; NOT shipped: her rhomboid mass is 62 / 44 cm3 of paraspinal patches (vhf_pecminor_rhomboids "
                    "maps it to null) and the spine-root cut leaves rhomboid minor larger than major; the split is not "
                    "supported by her data.")
        rel = "exact" if aid else "no_usable_label"
        labels["atlas"][name] = {"atlas_id": aid, "relationship": rel, "note": note}
        entries.append({"label": lid, "source_structure": name, "side": sd, "status": "curated", "atlas_id": aid,
                        "relationship": rel, "note": note, "candidates": []})
    lk = REPO / "mappings" / f"vh{a.body}_shoulder_split_labels.json"; lk.write_text(json.dumps(labels, indent=1))
    mp = {"_README": ["Review every entry before running convert.", "Set 'atlas_id' to the correct entity, or null to skip the label.",
                      "'status' is advisory; convert reads 'atlas_id' only."],
          "subject": B["subject"], "source_volume": str(out_path.resolve()), "label_map": f"vh{a.body}_shoulder_split", "entries": entries}
    (REPO / "mappings/subjects" / f"{B['subject']}_volume_mapping.json").write_text(json.dumps(mp, indent=1))
    print("wrote", out_path, rep_path, lk, flush=True)
    for n_ in report["notes"]:
        print("NOTE", n_)


if __name__ == "__main__":
    main()
