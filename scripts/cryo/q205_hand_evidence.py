"""Q205: bone evidence of HIS two hands from the full-resolution crops of scripts/cryo/q205_hand_crops.py -> data/derived/Q205_his_hand_photo_evidence.npz
(cream bone pixels, same rule as scripts/cryo/q192_hand_evidence.py: value > 165, saturation < 0.46, r-g < 36, b > 80, g > 0.8 r; inside the hand tissue, deeper than 4.5 mm; blobs >= 12 mm2),
block-reduced to 1 mm voxels (>= 50 % of the 3 x 3 pixels) in atlas mm.  Real pixels only.
    python3 scripts/cryo/q205_hand_evidence.py CROPS.npz [OUT.npz]
"""
import sys

import numpy as np
from scipy import ndimage as ndi

PX = 0.33


def cream(im):
    f = im.astype(np.float32)
    r, g, b = f[..., 0], f[..., 1], f[..., 2]
    v = f.max(-1)
    sat = (v - f.min(-1)) / np.maximum(v, 1)
    return (v > 165) & (sat < 0.46) & ((r - g) < 36) & (b > 80) & (g > 0.80 * r)


def tissue(im):
    i16 = im.astype(np.int16)
    T = (i16[..., 0] > i16[..., 2] + 20) & (i16.max(-1) > 45)
    T = ndi.binary_opening(T, iterations=2)
    lab, n = ndi.label(T)
    if n:
        sz = ndi.sum(T, lab, range(1, n + 1))
        T = np.isin(lab, 1 + np.flatnonzero(sz > 400))
    return ndi.binary_fill_holes(T)


def level_mask(im, depth_mm=4.5, min_area_mm2=12.0):
    T = tissue(im)
    deep = ndi.distance_transform_edt(T) * PX > depth_mm
    c = ndi.binary_opening(cream(im) & deep, iterations=1)
    lab, n = ndi.label(c)
    if n:
        a = ndi.sum(c, lab, range(1, n + 1)) * PX * PX
        c = np.isin(lab, 1 + np.flatnonzero(a >= min_area_mm2))
    return c, T


def main(crops, out):
    z = np.load(crops)
    reg = z["reg"]
    res = {}
    for si, s in enumerate("rl"):
        X0, Y0 = reg[si]
        ev = []
        for li, y in enumerate(z["ys"]):
            im = z[f"crop_{s}"][li]
            c, T = level_mask(im)
            H, W = c.shape
            h3, w3 = H // 3, W // 3
            blk = c[:h3 * 3, :w3 * 3].reshape(h3, 3, w3, 3).mean((1, 3)) >= 0.5
            rr, cc = np.nonzero(blk)
            r0, r1, c0, c1 = z[f"box_px_{s}"]
            row = r0 + rr * 3 + 1.0
            col = c0 + cc * 3 + 1.0
            x = X0 + 6.0 - PX * col
            zz = Y0 - 4.8 + PX * row
            ev.append(np.c_[x, np.full(len(x), float(y)), zz])
        res[f"cream_{s}"] = np.vstack(ev).astype(np.float32)
        print(s, len(res[f"cream_{s}"]))
    np.savez_compressed(out, note=np.array("Q205: cream bone voxels (1 mm) of his hands from his full-resolution cryosection photographs, atlas mm, frame = the Q185a2 arm registration carried down the hand"), **res)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "data/derived/Q205_his_hand_photo_evidence.npz")
