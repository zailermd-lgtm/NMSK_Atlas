"""Q199: bone evidence of her LEFT ARM (humerus shaft + elbow) in her cryosection photographs -> data/derived/Q199_left_arm_evidence.npz

Same photographs and frame as Q192 / Q194 (atlas x = AX - 0.33 col, y = cryo z + 1850, z = -166.4 + 0.33 row, AX 352.2 left).  Colour rules only, no learned model:
  bone blob   = pixels whose 7 px (4.6 mm) grey-erosion of the value channel is > 150 and saturation < 0.5 (cream-white, uniform; fat and skin lose it to the dark cell
                walls), dilated back, as 2-D blobs of 40..2500 mm2 whose 3..10 px outer ring is >= 45 % dark muscle-coloured tissue (value 40..150, r >= g+8, r >= b+8)
                -> the blob is inside the muscle mass = bone, not subcutaneous fat
  elbow_pts   = the voxels of those blobs at y = 312..354, at least 18 mm inside her photograph silhouette (Q194 masks), left arm only            (mm x 10, int16)
  shaft_pts   = per level y = 380 and 430..500 (10 mm apart), the centre (x, z) of the humerus disc: the blob with the best ring fraction within 45 mm of her CT humerus label
                (ring fraction >= 0.7)                                                                                                    (y, x, z mm)
    python3 scripts/cryo/q199_arm_evidence.py --stack arm_ds2.npy --json arm_ds2.json      # the cached stack (below)
    python3 scripts/cryo/q199_arm_evidence.py --stream                                       # streams slices (z -1220 .. -1700, every 3rd = 1 mm) from the NCI IDC mirror, 2x down-sampled
"""
from __future__ import annotations

import argparse
import io
import json
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "data" / "derived" / "Q199_left_arm_evidence.npz"
PX, AZ, AX = 0.33, -166.4, 352.2
PIX = 2 * PX
WIN = (700, 960)            # columns of the 2x down-sampled photograph holding her left arm
Y_TOP = 630                 # y of slice 0 of the stack (cryo z -1220)


def bone_mask(im, thr=150, sz=7):
    f = im.astype(np.float32)
    v = f.max(-1)
    sat = (v - f.min(-1)) / np.maximum(v, 1)
    ve = ndi.grey_erosion(ndi.median_filter(v, size=3), size=(sz, sz))
    return ndi.binary_dilation((ve > thr) & (sat < 0.5), iterations=sz // 2)


def muscle(im):
    f = im.astype(np.float32)
    r, g, b = f[..., 0], f[..., 1], f[..., 2]
    v = f.max(-1)
    return ndi.binary_closing((v < 150) & (v > 40) & (r >= g + 8) & (r >= b + 8), iterations=1)


def blobs(im, ring_min):
    bm, mus = bone_mask(im), muscle(im)
    lab, n = ndi.label(bm)
    out = []
    for k in range(1, n + 1):
        reg = lab == k
        a = reg.sum() * PIX ** 2
        if a < 40 or a > 2500:
            continue
        ring = ndi.binary_dilation(reg, iterations=10) & ~ndi.binary_dilation(reg, iterations=3)
        mf = float((mus & ring).sum() / max(ring.sum(), 1))
        if mf >= ring_min:
            out.append((reg, mf, a))
    return out


def extract(stack, her_humerus_v, masks_npz, log=print):
    sys.path.insert(0, str(REPO))
    from scripts.zanatomy import q194_forearm as F
    P = F.load_photo_masks(masks_npz)
    T = P["skin"] > 0.5
    lo = F.GRID_LO
    depth = np.stack([ndi.distance_transform_edt(ndi.binary_fill_holes(T[:, i, :])) for i in range(T.shape[1])], 1)
    pts = []
    for y in range(312, 355):
        im = np.asarray(stack[Y_TOP - y][:, WIN[0]:WIN[1]])
        keep = np.zeros(im.shape[:2], bool)
        for reg, _, _ in blobs(im, 0.45):
            keep |= reg
        rr, cc = np.nonzero(keep)
        x, z = AX - PX * 2 * (cc + WIN[0]), AZ + PX * 2 * rr
        ix, iy, iz = np.round(x - lo[0]).astype(int), int(round(y - lo[1])), np.round(z - lo[2]).astype(int)
        ok = (ix >= 0) & (ix < T.shape[0]) & (iz >= 0) & (iz < T.shape[2])
        ok[ok] = depth[ix[ok], iy, iz[ok]] >= 18.0
        pts.append(np.c_[x[ok], np.full(ok.sum(), y), z[ok]])
    elbow = np.vstack(pts)
    shaft = []
    for y in [380] + list(range(430, 501, 10)):
        b = her_humerus_v[np.abs(her_humerus_v[:, 1] - y) < 2.5]
        c = (b[:, 0].mean(), b[:, 2].mean())
        im = np.asarray(stack[Y_TOP - y][:, WIN[0]:WIN[1]])
        best = None
        for reg, mf, a in blobs(im, 0.7):
            rr, cc = np.nonzero(reg)
            x, z = AX - PX * 2 * (cc.mean() + WIN[0]), AZ + PX * 2 * rr.mean()
            d = float(np.hypot(x - c[0], z - c[1]))
            if d < 45 and (best is None or mf - d / 60 > best[0]):
                best = (mf - d / 60, x, z, mf, a, d)
        if best:
            shaft.append((y, best[1], best[2]))
            log(f"  y {y}: her CT humerus ({c[0]:.1f},{c[1]:.1f}) -> photo disc ({best[1]:.1f},{best[2]:.1f}) ring {best[3]:.2f} area {best[4]:.0f}")
    return elbow, np.array(shaft)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stack")
    ap.add_argument("--stream", action="store_true")
    ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args(argv)
    sys.path.insert(0, str(REPO))
    if a.stream:
        import urllib.request
        import pydicom
        from concurrent.futures import ThreadPoolExecutor
        from scripts.cryo import q192_hand_evidence as E
        index = E.load_index(Path("/tmp/q199_work"))
        zs = np.array([r[2] for r in index])
        sel = sorted([i for i in range(0, len(index), 3) if -1700 <= zs[i] <= -1220], key=lambda i: -zs[i])

        def get(i):
            d = urllib.request.urlopen(E.B + index[i][0], timeout=60).read()
            return pydicom.dcmread(io.BytesIO(d)).pixel_array[:1216:2, :2048:2]
        with ThreadPoolExecutor(8) as ex:
            stack = np.stack(list(ex.map(get, sel)))
    else:
        stack = np.load(a.stack, mmap_mode="r")
    from scripts.transfer.zan_to_vhf_whole_body import load_her_meshes
    hv = load_her_meshes()["humerus_l"]["v"]
    elbow, shaft = extract(stack, hv, REPO / "data" / "derived" / "Q194_left_forearm_photo_masks.npz")
    np.savez_compressed(a.out, elbow_pts_mm10=np.round(elbow * 10).astype(np.int16), shaft_y_x_z=shaft.astype(np.float32),
                        note=np.array("Q199: bone evidence of her left arm in her cryosection photographs (frame as Q192); scripts/cryo/q199_arm_evidence.py"))
    print("wrote", a.out, "elbow points", len(elbow), "shaft levels", len(shaft))


if __name__ == "__main__":
    main()
