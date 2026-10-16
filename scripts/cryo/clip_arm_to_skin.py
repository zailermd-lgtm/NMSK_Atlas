"""Clip a male arm-muscle label volume to his own whole-body CT skin silhouette.

Visual QA found deltoid_r (17% of vertices) and triceps_brachii_r/l (17-27%) poking through his
skin at the shoulder/upper arm. Both label volumes already share the torso CT block's z origin
(z0=-863, the same --origin used at convert time), so a direct affine reprojection into the skin
grid is exact, not approximate. Any label voxel whose centre maps outside the skin silhouette is
dropped -- pure subtraction, no new geometry.

v2: an exact-boundary clip (v1) still left triceps_brachii poking through at the elbow (visible from
a back-view render the shoulder-only check in v1 didn't cover) -- the same lesson as the female
tibialis-anterior fix (PROJECT_STATE Q69): the skin and muscle volumes are Gaussian-smoothed at
different sigmas before marching cubes (1.5 vs 1.0), so their isosurfaces don't nest exactly even
when the hard voxel masks do. Now clips against the skin mask eroded by a few mm, matching Q69's fix.
"""
import sys, numpy as np, nibabel as nib
from scipy import ndimage as ndi

LAB_PATH, OUT_PATH = sys.argv[1], sys.argv[2]
MARGIN_PX = int(sys.argv[3]) if len(sys.argv) > 3 else 3
SKIN = "/home/user/NMSK_Atlas/data/ct_sources/task_outputs/vhm_skin_ct.nii.gz"

lab_img = nib.load(LAB_PATH)
lab = np.asarray(lab_img.dataobj).copy()
skin_img = nib.load(SKIN)
skin_hard = np.asarray(skin_img.dataobj) > 0
skin = ndi.binary_erosion(skin_hard, structure=np.ones((3, 3, 3)), iterations=MARGIN_PX) if MARGIN_PX > 0 else skin_hard
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
