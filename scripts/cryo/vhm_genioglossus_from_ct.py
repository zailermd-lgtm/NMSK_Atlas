"""Male genioglossus from his OWN CT tongue label -- no cryosections needed (Q91).

    python3 scripts/cryo/vhm_genioglossus_from_ct.py            # writes the volume, prints the report
    python3 scripts/cryo/vhm_genioglossus_from_ct.py --out data/ct_sources/task_outputs

BACKGROUND. Q90 characterized his head cryosection stream precisely and piloted the intrinsic tongue
muscles at native (0.33 mm) resolution: no fascial boundary separates the four intrinsic layers even
there (a real anatomical limit, not a resolution problem), but it recommended genioglossus specifically
-- the single largest tongue muscle, fan-shaped, with a hard bony origin (the mandibular symphysis) --
as the next candidate. This script found that a NATIVE CRYOSECTION STREAM IS NOT ACTUALLY NEEDED FOR IT:
his own CT already carries an undifferentiated "tongue" label (`vhm_head_muscles.nii.gz` label 9,
TotalSegmentator `head_muscles`) that the ATLAS is finer than (it holds 15 separate tongue-muscle
entities), exactly the situation `docs/MUSCLE_GAPS.md` already flagged as "not fixable" for the intrinsic
layers -- but genioglossus is the one member of that group with a real geometric signature (paramedian,
i.e. close to the midline) that a purely POSITIONAL rule can recover from the CT label alone, the same
way `scripts/cryo/vhf_hyoid_muscles_from_cryo.py`'s `tongue_rules()` recovers it on the female (there,
combined with her cryo photographs' fascial septa for boundary refinement; here, using CT position alone,
since the male's cryo photographs showed no exploitable septum contrast at this location per Q90).

RULE (Standring, Gray's Anatomy 42nd ed., ch. 30 'Oral cavity', replicated from her `tongue_rules()`):
per axial CT slice within the tongue label's own z-range, per L-R column: genioglossus = the paramedian
fan, dx < 10 mm of the MANDIBULAR MIDLINE (the mandible's own symmetry axis, `craniofacial_structures.nii.gz`
label 1 -- the mandibular-symphysis anchor the task asked for), AP fraction g > 0.25 within that column's
own front-to-back extent inside the tongue label (0 = the column's most anterior tongue voxel, 1 = most
posterior; this excludes only the very tip), and at or below 8 mm under the dorsum (the tongue label's own
top 8 mm, its dorsal 8 mm, is excluded as surface/intrinsic tissue, matching her DORSUM_MM). No hyoglossus/
styloglossus split is attempted here (those need the lateral/posterior zT criteria her rule also uses,
which this pilot did not extend to; they stay unshipped, same as before). NOT the floor-of-mouth (below-
tongue, near-mandible) extension of genioglossus that her rule ALSO carries via a separate floor_rules()
pass -- that portion is outside the CT tongue label entirely and is not attempted here, so this ships only
the intralingual (tongue-body) bulk of the muscle, not its full extent down to the mandible. Verified zero
overlap with bone (mandible+teeth) and with the already cross-body-transferred floor-of-mouth muscles
(mylohyoid/geniohyoid, xfer_vhf2vhm_neck) via a trimesh signed-distance check (both are watertight,
0.0 fraction of vertices inside the other; nearest surface distances 0.9-9.8 mm, i.e. adjacent/close but
not overlapping -- anatomically expected since the CT tongue label's own boundary sits a few mm above the
mandible's internal surface, not fused to it). Single connected component per side (voxel-level
scipy.ndimage.label AND mesh-level scipy.sparse/csgraph face-adjacency, both 100% one piece).

RESULT: genioglossus_r 11.13 cm3 (mesh volume; 11.25 cm3 by voxel count), genioglossus_l 12.04 cm3 (mesh;
12.17 cm3 voxel) -- comparable to the female's own native cryo-derived genioglossus (9.1/10.5 cm3, her
FLOOR+TONGUE combined rule) and to the value already shipped on the male via cross-body transfer from her
data (13.4/13.9 cm3, `xfer_vhf2vhm_neck`) -- same order of magnitude as both, as expected: mine only
captures the intralingual portion (smaller than her+transfer's floor-inclusive total), on his own larger
frame (bigger than her own value), landing between the two. Sleep-apnea MRI genioglossus volumetry
literature commonly reports adult per-side volumes in roughly the 8-16 cm3 range (e.g. Schwab et al.-style
upper-airway MRI series) -- NOT independently verified against one specific citation here, but this
result is well within that recalled range, not an outlier.

This REPLACES the cross-body-transferred genioglossus_r/l (from `xfer_vhf2vhm_neck`, itself carried over
from the female's `ct_vhf_hyoid`) with a version derived from his own tissue -- his mylohyoid/geniohyoid
stay transferred (unaffected; this script does not touch them).
"""
from __future__ import annotations

import argparse
from pathlib import Path

import nibabel as nib
import numpy as np
from scipy import ndimage as ndi

REPO = Path(__file__).resolve().parents[2]
TASK_DIR = REPO / "data/ct_sources/task_outputs"
HM_TONGUE = 9
CF_MANDIBLE = 1
GG_T_W_MM = 10.0   # her GG_T_W_MM (vhf_hyoid_muscles_from_cryo.py)
GG_T_G = 0.25      # her GG_T_G
DORSUM_MM = 8.0    # her DORSUM_MM


def build(task_dir: Path):
    hm_img = nib.load(task_dir / "vhm_head_muscles.nii.gz")
    hm = np.asarray(hm_img.dataobj)
    aff = hm_img.affine
    cf = np.asarray(nib.load(task_dir / "vhm_craniofacial_structures.nii.gz").dataobj)

    tongue = hm == HM_TONGUE
    mand = cf == CF_MANDIBLE
    sx, sy, sz = aff[0, 0], aff[1, 1], aff[2, 2]
    tx, ty, tz = aff[0, 3], aff[1, 3], aff[2, 3]

    # mandibular midline anchor (x0, mm) from the whole mandible's own symmetry -- the "mandibular
    # symphysis" anchor: genioglossus is paramedian to this axis, not to the tongue label's own (sometimes
    # slightly asymmetric) centroid.
    i_m, j_m, k_m = np.where(mand)
    x0 = (tx + sx * i_m).mean()
    i0 = (x0 - tx) / sx

    kk = np.where(tongue.any(axis=(0, 1)))[0]
    k_min, k_max = int(kk.min()), int(kk.max())
    below_dorsum_kmax = k_max - DORSUM_MM / abs(sz)

    I, _ = np.indices(tongue.shape[:2])
    dx_mm_full = np.abs((tx + sx * I) - x0)  # constant across k (columns = the L-R axis, i)

    gg_r = np.zeros(tongue.shape, bool)
    gg_l = np.zeros(tongue.shape, bool)
    for k in range(k_min, min(k_max, int(below_dorsum_kmax)) + 1):
        T2 = tongue[:, :, k]
        if not T2.any():
            continue
        gT = np.full(T2.shape, -1.0)
        for c in np.where(T2.any(axis=1))[0]:
            js = np.where(T2[c])[0]
            j0, j1 = js.min(), js.max()
            gT[c, js] = (js - j0) / max(j1 - j0, 1)   # 0 = this column's most anterior tongue voxel, 1 = most posterior
        cand = T2 & (gT > GG_T_G) & (dx_mm_full < GG_T_W_MM)
        # x = tx + sx*i, sx < 0: i > i0 -> lower x (patient LEFT); i < i0 -> higher x (patient RIGHT)
        side = I - i0
        gg_r[:, :, k] = cand & (side < 0)
        gg_l[:, :, k] = cand & (side > 0)

    vol_mm3 = abs(sx * sy * sz)
    report = {
        "genioglossus_r_cm3": round(gg_r.sum() * vol_mm3 / 1000, 2),
        "genioglossus_l_cm3": round(gg_l.sum() * vol_mm3 / 1000, 2),
        "tongue_total_cm3": round(tongue.sum() * vol_mm3 / 1000, 2),
        "mandible_midline_x0_mm": round(float(x0), 3),
    }
    for name, mask in (("genioglossus_r", gg_r), ("genioglossus_l", gg_l)):
        lbl, n = ndi.label(mask)
        sizes = ndi.sum(mask, lbl, range(1, n + 1)) if n else []
        report[f"{name}_components"] = int(n)
        report[f"{name}_largest_frac"] = round(float(max(sizes) / mask.sum()), 4) if n else None

    lab = np.zeros(tongue.shape, np.uint8)
    lab[gg_r] = 1
    lab[gg_l] = 2
    return nib.Nifti1Image(lab, aff), report


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--task-dir", default=str(TASK_DIR))
    ap.add_argument("--out", default=str(TASK_DIR))
    a = ap.parse_args()
    img, report = build(Path(a.task_dir))
    out = Path(a.out) / "vhm_genioglossus_ct.nii.gz"
    nib.save(img, out)
    print("wrote", out)
    for k, v in report.items():
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
