"""Q205: solid bone evidence of HIS two hands from the frozen-CT HU crops (scripts/cryo/q205_ct_hand_crops.py) -> data/derived/Q205_his_hand_ct_evidence.npz
The CT frame of the torso series -> atlas (measured by overlap with the label volume, 18 030 of 26 875 label voxels at the peak, offsets 6 / 895 / -5 mm):
    atlas x = -x_dicom + 6.0,  atlas y = z_dicom + 895.4,  atlas z = -y_dicom - 4.8,   x_dicom = IPP_x + 0.9375 col, y_dicom = IPP_y + 0.9375 row
Evidence rule: HU >= 250 inside the hand box, cavities filled per slice (marrow), 3-D components >= 40 voxels, nothing within 3 mm of his radius / ulna labels; atlas y 34 .. 118 (the torso block;
the fingers below y ~ 32 lie in the legs block and keep the label volume).
    python3 scripts/cryo/q205_ct_hand_evidence.py CT_HAND.npz [OUT.npz]
"""
import sys

import numpy as np
from scipy import ndimage as ndi
from scipy.spatial import cKDTree

HU = 250
BOX = {"r": ((-20.0, 178.0), (108.0, 200.0)), "l": ((-178.0, 20.0), (108.0, 200.0))}
YR = (34.0, 118.0)


def main(src, out):
    z = np.load(src)
    vol, zd, ipp, pix = z["vol"], z["z"], z["ipp"][0], float(z["pix"][0])
    lab = np.load("data/derived/Q205_his_hand_labels.npz")
    res = {}
    cols = np.arange(vol.shape[2])
    rows = np.arange(vol.shape[1])
    ax = -(ipp[0] + pix * cols) + 6.0
    az = -(ipp[1] + pix * rows) - 4.8
    for s in "rl":
        (xa, xb), (za, zb) = BOX[s]
        cm = (ax >= xa) & (ax <= xb)
        rm = (az >= za) & (az <= zb)
        ci, ri = np.flatnonzero(cm), np.flatnonzero(rm)
        ys = zd + 895.4
        ks = np.flatnonzero((ys >= YR[0]) & (ys <= YR[1]))
        sub = vol[np.ix_(ks, ri, ci)] >= HU
        for j in range(len(ks)):
            sub[j] = ndi.binary_fill_holes(ndi.binary_opening(sub[j]))
        l3, n = ndi.label(sub, structure=np.ones((3, 3, 3)))
        sz = np.bincount(l3.ravel())
        keep = np.flatnonzero(sz >= 40)
        keep = keep[keep > 0]
        sub &= np.isin(l3, keep)
        kk, rr, cc = np.nonzero(sub)
        P = np.c_[ax[ci][cc], ys[ks][kk], az[ri][rr]]
        fa = np.vstack([lab[f"radius_{s}"], lab[f"ulna_{s}"]])
        d = cKDTree(fa).query(P)[0]
        P = P[d > 3.0]
        res[f"ct_{s}"] = P.astype(np.float32)
        print(s, len(P))
    np.savez_compressed(out, note=np.array("Q205: his hand bone voxels from the frozen CT (HU >= 250, atlas y 34-118) ; scripts/cryo/q205_ct_hand_evidence.py"), **res)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "data/derived/Q205_his_hand_ct_evidence.npz")
