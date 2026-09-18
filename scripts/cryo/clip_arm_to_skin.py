"""Clip a male arm-muscle label volume to his own whole-body CT skin silhouette.

Visual QA found deltoid_r (17% of vertices) and triceps_brachii_r/l (17-27%) poking through his
skin at the shoulder/upper arm. Both label volumes already share the torso CT block's z origin
(z0=-863, the same --origin used at convert time), so a direct affine reprojection into the skin
grid is exact, not approximate. Any label voxel whose centre maps outside the skin silhouette is
dropped -- pure subtraction, no new geometry.
"""
import sys, numpy as np, nibabel as nib

LAB_PATH, OUT_PATH = sys.argv[1], sys.argv[2]
SKIN = "/home/user/NMSK_Atlas/data/ct_sources/task_outputs/vhm_skin_ct.nii.gz"

lab_img = nib.load(LAB_PATH)
lab = np.asarray(lab_img.dataobj).copy()
skin_img = nib.load(SKIN)
skin = np.asarray(skin_img.dataobj) > 0
inv_skin = np.linalg.inv(skin_img.affine)

nz = np.where(lab.any(axis=(0, 1)))[0]
removed = 0
per_label = {}
for k in nz:
    sl = lab[:, :, k]
    hit = np.where(sl > 0)
    if len(hit[0]) == 0:
        continue
    ii, jj = hit
    ras = nib.affines.apply_affine(lab_img.affine, np.c_[ii, jj, np.full(len(ii), k)])
    vox = np.rint(nib.affines.apply_affine(inv_skin, ras)).astype(int)
    ok = ((vox[:, 0] >= 0) & (vox[:, 0] < skin.shape[0]) &
          (vox[:, 1] >= 0) & (vox[:, 1] < skin.shape[1]) &
          (vox[:, 2] >= 0) & (vox[:, 2] < skin.shape[2]))
    inside = np.zeros(len(ii), bool)
    inside[ok] = skin[vox[ok, 0], vox[ok, 1], vox[ok, 2]]
    bad = ~inside
    if bad.any():
        vals = sl[ii[bad], jj[bad]]
        for l in np.unique(vals):
            per_label[int(l)] = per_label.get(int(l), 0) + int((vals == l).sum())
        sl[ii[bad], jj[bad]] = 0
        lab[:, :, k] = sl
        removed += int(bad.sum())

print("voxels removed:", removed, "by label:", per_label)
nib.save(nib.Nifti1Image(lab, lab_img.affine, lab_img.header), OUT_PATH)
print("wrote", OUT_PATH)
