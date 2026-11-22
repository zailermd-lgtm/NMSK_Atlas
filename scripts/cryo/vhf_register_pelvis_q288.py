"""Register HER full-resolution pelvic cryosections (vhf_stream_pelvis_q288.py) to her torso CT (Q288).

    python3 scripts/cryo/vhf_register_pelvis_q288.py --photos /dev/shm/q288/photos/pelvis \
        --ct SCRATCH/vh_idc/nii/vhf_torso_0937.nii.gz --out /dev/shm/q288/reg.json

Her 1 mm frame (vhf_register_cryo.py / vhf_resample_cryo.py: anchors.json, frame.json) was lost with a container
reset (Q179), so the pelvic slab is registered again by THE SAME METHOD those scripts used, restricted to the slab:
  * in-plane: rows flipped ('fy': photograph row 0 is posterior), photograph pixel = 0.99 mm (the 1 mm photographs
    of vhf_resample_cryo.py are 3 x 0.33 mm); per level a translation found by phase correlation of the body
    silhouettes (photo: tissue colour, cryo_classes_f; CT: HU > -500, holes filled) on a 1 mm grid, median-filtered
    over 5 levels;
  * height: torso-RAS z = cryo z + 944.7 (Q154 calibration) + d. d is searched over -15..+45 mm (Q179 measured
    14-20 mm at the hips) by the normalised cross-correlation of the TISSUE PATTERN -- photographed fat (class 2)
    against CT fat (-190..-30 HU) and photographed bone-marrow/cortex against CT bone (> 180 HU) -- after the
    in-plane shift, per level; a line d(z) is fitted through the levels whose best NCC is >= 0.5 (both stacks are
    contiguous 1 mm series, so d can only drift as a scale), outliers > 6 mm dropped.
Writes per photograph level: cryo z, RAS z, CT slice, row/col shift (1 mm frame px) and the NCC; the mapping a
photograph pixel (pr, pc) at 0.33 mm -> RAS: frame row r = (Hc-1 - pr/3)*0.99 + RS, col c = (pc/3)*0.99 + CS,
RAS x = 240 - c * 0.9375/0.9375 ... (see to_ras()). Nothing here is anatomy."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import nibabel as nib
import numpy as np
from scipy import ndimage as ndi
from skimage.registration import phase_cross_correlation

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.cryo.cryo_classes_f import classify  # noqa: E402

SC = 0.99          # mm per 1 mm-photograph pixel (vhf_resample_cryo.py)
Q154 = 944.7       # torso-RAS z = cryo z + Q154 (+ d)
GRID = 480         # 1 mm CT grid: col = 240 - RAS x, row = 240 - RAS y  (as her old frame, minus its 110-col pad)


def photo_1mm(px):
    """(h, w, 3) full-res -> 1 mm (3x3 mean)."""
    h, w = px.shape[0] // 3 * 3, px.shape[1] // 3 * 3
    return px[:h, :w].reshape(h // 3, 3, w // 3, 3, 3).mean(axis=(1, 3)).astype(np.uint8)


def photo_masks(im1):
    cl = classify(im1)
    body = ndi.binary_fill_holes(ndi.binary_opening(cl > 0, iterations=2))
    lab, n = ndi.label(body)
    if n:
        sz = ndi.sum(body, lab, range(1, n + 1)); body = np.isin(lab, 1 + np.flatnonzero(sz > 0.05 * sz.max()))
    fat = (cl == 2) & body
    v = im1.max(-1).astype(float); r, g, b = (im1[..., i].astype(float) for i in range(3))
    bone = body & (((cl == 4) | (cl == 5)) | ((r > 150) & (g > 90) & (g < 0.80 * r) & (b < 0.75 * g + 40) & (v > 150)))
    return cl, body, fat, bone


def to_frame(img, RS, CS, shape=(GRID, GRID), order=0):
    """Photograph 1 mm image -> 1 mm CT-frame grid (rows flipped, 0.99 mm px, shift RS/CS)."""
    rr, cc = np.mgrid[0:shape[0], 0:shape[1]].astype(np.float32)
    H = img.shape[0]
    src_r = (H - 1) - (rr - RS) / SC; src_c = (cc - CS) / SC
    return ndi.map_coordinates(img.astype(np.float32), [src_r, src_c], order=order, mode="constant", cval=0)


class CT:
    def __init__(self, path):
        im = nib.load(path); self.z0 = float(im.affine[2, 3]); self.n = im.shape[2]; self.cache = {}
        self.dat = np.asarray(im.dataobj, dtype=np.int16)              # whole volume once (a .gz has no random access)

    def slice(self, k):
        """1 mm grid: row = 240 - RAS y, col = 240 - RAS x (CT voxel i: x = 240 - 0.9375 i)."""
        if k not in self.cache:
            s = np.asarray(self.dat[:, :, k]).astype(np.float32)          # (i, j) -> x, y
            g = ndi.zoom(s, GRID / 512 * 0.9375 * 512 / GRID, order=1)    # 0.9375 mm -> 1 mm: 480 px
            g = g[:GRID, :GRID].T                                          # rows = j (y), cols = i (x)
            self.cache[k] = g
        return self.cache[k]

    def masks(self, k):
        s = self.slice(k)
        body = ndi.binary_fill_holes(s > -500)
        return body, (s > -190) & (s < -30) & body, (s > 180) & body


def ncc(a, b):
    a = a - a.mean(); b = b - b.mean(); return float((a * b).sum() / np.sqrt((a * a).sum() * (b * b).sum() + 1e-6))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--photos", required=True); ap.add_argument("--ct", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--every", type=int, default=4, help="levels used for the height search")
    ap.add_argument("--dmin", type=float, default=-15); ap.add_argument("--dmax", type=float, default=45)
    a = ap.parse_args()
    vol = np.load(a.photos + ".npy", mmap_mode="r"); meta = json.load(open(a.photos + ".json")); ct = CT(a.ct)
    czs = np.array([l["cryo_z"] for l in meta["levels"]])
    pm = {}

    def pmask(k):
        if k not in pm:
            pm[k] = photo_masks(photo_1mm(np.asarray(vol[k])))
        return pm[k]

    def score(k, kk):
        _, pb, pf, pbn = pmask(k)
        cb, cf, cbn = ct.masks(kk)
        B = to_frame(pb, 0, 0) > 0.5
        sh, _, _ = phase_cross_correlation(cb.astype(np.float32), B.astype(np.float32), upsample_factor=1)
        RS, CS = float(sh[0]), float(sh[1])
        F = to_frame(pf, RS, CS); N = to_frame(pbn, RS, CS); Bs = to_frame(pb, RS, CS) > 0.5
        roi = ndi.binary_dilation(cb | Bs, iterations=3)
        s = ncc(np.where(roi, F, 0), np.where(roi, cf, 0)) + 0.5 * ncc(np.where(roi, N, 0), np.where(roi, cbn, 0))
        iou = (cb & Bs).sum() / ((cb | Bs).sum() + 1)
        return s / 1.5, RS, CS, float(iou)

    rows = []
    for k in range(0, len(czs), a.every):
        best = None
        for d in np.arange(a.dmin, a.dmax + 0.1, 1.0):
            kk = int(round(czs[k] + Q154 + d - ct.z0))
            if not 0 <= kk < ct.n:
                continue
            s, RS, CS, iou = score(k, kk)
            if best is None or s > best[0]:
                best = (s, d, RS, CS, iou)
        rows.append({"k": k, "cryo_z": float(czs[k]), "d": float(best[1]), "ncc": round(best[0], 3), "RS": best[2], "CS": best[3], "iou": round(best[4], 3)})
        print(rows[-1], flush=True)
        ct.cache.clear()
    good = [r for r in rows if r["ncc"] >= 0.5]
    z = np.array([r["cryo_z"] for r in good]); d = np.array([r["d"] for r in good])
    for _ in range(3):
        b, a0 = np.polyfit(z, d, 1); res = d - (a0 + b * z); keep = abs(res) <= 6
        if keep.all():
            break
        z, d = z[keep], d[keep]
    rms = float(np.sqrt(((d - (a0 + b * z)) ** 2).mean()))
    print(f"d(z) = {a0:.2f} + {b:.5f} z over {len(z)} levels, rms {rms:.2f} mm")
    # final per-level in-plane shift at the fitted height, every level
    lev = []
    for k in range(len(czs)):
        dd = a0 + b * czs[k]; zr = czs[k] + Q154 + dd; kk = int(round(zr - ct.z0))
        s, RS, CS, iou = score(k, kk); pm.pop(k, None)
        lev.append({"k": k, "cryo_z": float(czs[k]), "ras_z": float(zr), "ct_k": kk, "RS_raw": RS, "CS_raw": CS, "ncc": round(s, 3), "iou": round(iou, 3)})
        if k % 40 == 0:
            print(lev[-1], flush=True); ct.cache.clear()
    RSm = ndi.median_filter(np.array([l["RS_raw"] for l in lev]), size=5, mode="nearest")
    CSm = ndi.median_filter(np.array([l["CS_raw"] for l in lev]), size=5, mode="nearest")
    for l, r_, c_ in zip(lev, RSm, CSm):
        l["RS"], l["CS"] = float(r_), float(c_)
    json.dump({"method": __doc__.split("\n\n")[1].strip(), "q154_offset": Q154, "d_line": [float(a0), float(b)], "d_rms_mm": rms,
               "n_fit": int(len(z)), "search": rows, "levels": lev, "sc": SC, "grid": "1 mm: row = 240 - RAS y, col = 240 - RAS x",
               "photo_h_1mm": int(vol.shape[1] // 3)}, open(a.out, "w"), indent=1)
    print("REG_DONE")


if __name__ == "__main__":
    main()
