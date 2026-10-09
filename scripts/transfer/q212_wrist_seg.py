#!/usr/bin/env python3
"""Q212: HIS wrist re-segmented from his own frozen CT (HU crops, series 5d409385, public NCI IDC mirror; the same crops as scripts/cryo/q205_ct_hand_crops.py).

Problem (Q203): his hand "carpals" label (data/derived/Q205_his_hand_labels.npz `carp_*`, 23.6 / 32.7 cm3) is the HU >= 600 seed component of the hand mass cut by planes; it
contains the DISTAL RADIUS EPIPHYSIS (the articular plate) and the ULNAR HEAD, because the radius / ulna labels were cut at the plane where the carpal row was thought to start.
The radiocarpal joint cleft is visible in the CT (dark line between the scaphoid / lunate and the radial articular plate).

Method: a marker-controlled watershed on the smoothed HU (-HU is the relief, so the joint clefts are the ridges) restricted to the old labels plus the bone-density (HU >= 140)
voxels within 8 mm of them. Markers: radius label (shaft side), ulna label (shaft side), carpal label > 14 mm distal of the radius end, metacarpal label; extra markers for the
radius epiphysis = the Z-Anatomy radius fitted to HIS labels (Q201 page; it lies on the CT epiphysis within ~3 mm) inside the old carpal label, >= 3 mm proximal of the cleft side of
the plate, and for the ulnar head = a cylinder along his ulna axis, 6 mm beyond the label end (seeds), 12 mm at most (result). Z-Anatomy supplies markers only; every voxel of the result is his CT / his labels.

    python3 scripts/transfer/q212_wrist_seg.py --side r|l --ct CT_HAND.npz --out build/q212/wrist_seg_r.npz
Outputs: bool masks `R_new` (radius epiphysis voxels, not in his radius label), `U_new` (ulnar head voxels, not in his ulna label), `C_new` (carpals) on the 0.5 mm grid."""
from __future__ import annotations
import argparse
import sys
import time
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi
from scipy.ndimage import map_coordinates
from skimage.segmentation import watershed

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(REPO / "scripts" / "zanatomy"))

H = 0.5
BOX = {"r": ((95, 195), (36, 135), (80, 160)), "l": ((-200, -95), (40, 140), (75, 160))}
TLOW = 140.0          # bone-density voxels (smoothed HU) allowed within 8 mm of the old labels
DT = 14.0             # carpal markers: old carpal label more than this far distal of the radius label end
ZSEED_T = -3.0        # radius-epiphysis markers lie at least 3 mm proximal of the plate's distal face (t = 0 is the old radius label end, - = distal)


def load_ct(path):
    z = np.load(path)
    return z["vol"], z["z"], z["ipp"][0], float(z["pix"][0])


def sample_hu(vol, zd, ipp, pix, pts):
    """trilinear HU at atlas points; atlas = (-x_dicom + 6.0, z_dicom + 895.4, -y_dicom - 4.8) (Q205 frame measured against his label volume)"""
    xd = -(pts[:, 0] - 6.0); yd = -(pts[:, 2] + 4.8); zdd = pts[:, 1] - 895.4
    col = (xd - ipp[0]) / pix; row = (yd - ipp[1]) / pix
    k = np.interp(zdd, zd, np.arange(len(zd)))
    return map_coordinates(vol, [k, row, col], order=1, cval=-1000, mode="constant")


def segment(side, ct, labels, zradius=None, log=print):
    vol, zd, ipp, pix = ct
    (x0, x1), (y0, y1), (z0, z1) = BOX[side]
    xs, ys, zs = np.arange(x0, x1, H), np.arange(y0, y1, H), np.arange(z0, z1, H)
    G = np.stack(np.meshgrid(xs, ys, zs, indexing="ij"), -1)
    flat = G.reshape(-1, 3)
    hu = np.empty(len(flat), np.float32)
    for i in range(0, len(flat), 2_000_000):
        hu[i:i + 2_000_000] = sample_hu(vol, zd, ipp, pix, flat[i:i + 2_000_000])
    hu = hu.reshape(len(xs), len(ys), len(zs))
    R, U, C, MC = (labels[f"{n}_{side}"] for n in ("radius", "ulna", "carp", "mc"))
    A = np.vstack([R, U]); c = A.mean(0)
    u = np.linalg.svd(A - c, full_matrices=False)[2][0]
    if u[1] < 0:
        u = -u                                            # towards the elbow
    tR = ((R - c) @ u).min(); tU = ((U - c) @ u).min()
    origin = c + u * tR
    rel = G - origin; T = rel @ u; rad = np.linalg.norm(rel - T[..., None] * u, axis=-1)
    roi = (T > -48) & (T < 30) & (rad < 42)

    def vox(P):
        i = np.round((P[:, 0] - xs[0]) / H).astype(int); j = np.round((P[:, 1] - ys[0]) / H).astype(int); k = np.round((P[:, 2] - zs[0]) / H).astype(int)
        ok = (i >= 0) & (i < len(xs)) & (j >= 0) & (j < len(ys)) & (k >= 0) & (k < len(zs))
        return i[ok], j[ok], k[ok]

    def labvol(P):
        m = np.zeros(hu.shape, bool); i, j, k = vox(P); m[i, j, k] = True
        return ndi.binary_dilation(ndi.binary_closing(ndi.binary_dilation(m, iterations=1), iterations=1), iterations=1)
    Lr, Lu, Lc, Lm = (labvol(P) for P in (R, U, C, MC))
    allL = Lr | Lu | Lc | Lm
    sm = ndi.gaussian_filter(hu, 0.9)
    mask = (allL | ((sm >= TLOW) & ndi.binary_dilation(allL, iterations=8))) & roi
    mk = np.zeros(hu.shape, np.int8)
    er = lambda m: ndi.binary_erosion(m, iterations=1)  # noqa: E731
    mk[er(Lr & (T >= 3.0)) & mask] = 1
    mk[er(Lu & (T >= (tU - tR) + 3.0)) & mask] = 2
    mk[er(Lc & (T <= -DT)) & mask] = 3
    mk[er(Lm) & mask] = 4
    nz = {}
    if zradius is not None:                               # Z radius fitted to his labels: seeds for the epiphysis inside the old carpal label
        zs_ = ndi.binary_erosion(zradius, iterations=3) & (T >= ZSEED_T) & (Lc | Lr) & mask
        mk[zs_ & (mk == 0)] = 1; nz["z_radius_seeds"] = int(zs_.sum())
    # ulnar head: cylinder along his ulna axis, 6 mm beyond the label end (seeds), 12 mm at most (result)
    Uv = U[(((U - c) @ u) < tU + 40.0)]
    cu = Uv.mean(0); uu = np.linalg.svd(Uv - cu, full_matrices=False)[2][0]
    if uu @ u < 0:
        uu = -uu
    tt = (G - cu) @ uu; r2 = np.linalg.norm((G - cu) - tt[..., None] * uu, axis=-1)
    tend = ((U - cu) @ uu).min()
    cyl = (tt <= tend + 3.0) & (tt >= tend - 6.0) & (r2 < 6.0)
    uh = er(cyl & (Lc | Lu) & mask) & (mk == 0)
    mk[uh] = 2; nz["ulna_head_seeds"] = int(uh.sum())
    log({"markers": {int(k): int((mk == k).sum()) for k in (1, 2, 3, 4)}, **nz})
    ws = watershed(-sm, markers=mk, mask=mask | (mk > 0))
    far_u = (ws == 2) & (tt < tend - 12.0)                # the ulnar head cannot reach more than 12 mm beyond his ulna label: that part is carpal
    ws[far_u] = 3
    new_r = (ws == 1) & ~Lr
    new_u = (ws == 2) & ~Lu
    cn = (ws == 3)
    vol_cm3 = lambda m: round(float(m.sum()) * H ** 3 / 1000, 2)  # noqa: E731
    stats = dict(old_carp_cm3=vol_cm3(Lc), radius_new_cm3=vol_cm3(new_r), ulna_new_cm3=vol_cm3(new_u), carpals_new_cm3=vol_cm3(cn), old_radius_label_cm3=vol_cm3(Lr & roi),
                 carp_label_to_radius=vol_cm3(Lc & (ws == 1)), carp_label_to_ulna=vol_cm3(Lc & (ws == 2)), carp_label_to_carpals=vol_cm3(Lc & (ws == 3)), carp_label_to_mc=vol_cm3(Lc & (ws == 4)),
                 radius_t_range_mm=[round(float(T[ws == 1].min()), 1), round(float(T[ws == 1].max()), 1)], carpal_t_range_mm=[round(float(T[cn].min()), 1), round(float(T[cn].max()), 1)],
                 seeds=nz, axis=u.round(3).tolist(), origin=origin.round(2).tolist())
    log(stats)
    return dict(xs=xs, ys=ys, zs=zs, ws=ws.astype(np.int8), Lr=Lr, Lu=Lu, Lc=Lc, Lm=Lm, hu=sm.astype(np.float32), origin=origin, u=u, stats=stats)


if __name__ == "__main__":
    import json
    ap = argparse.ArgumentParser()
    ap.add_argument("--side", required=True, choices=["r", "l"]); ap.add_argument("--ct", required=True); ap.add_argument("--out", required=True)
    ap.add_argument("--zradius", default=None, help="npz with a bool `radius` volume on the same grid (Z-Anatomy radius fitted to his labels)")
    a = ap.parse_args()
    t = time.time()
    lab = np.load(REPO / "data/derived/Q205_his_hand_labels.npz")
    zr = np.load(a.zradius)["radius"] if a.zradius else None
    r = segment(a.side, load_ct(a.ct), lab, zr)
    st = r.pop("stats")
    np.savez_compressed(a.out, **r, stats=np.array(json.dumps(st)))
    print("done", round(time.time() - t, 1))
