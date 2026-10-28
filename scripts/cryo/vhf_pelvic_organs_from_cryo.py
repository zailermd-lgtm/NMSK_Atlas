"""HER pelvic organs from her own full-resolution colour cryosections (Q288).

    python3 scripts/cryo/vhf_pelvic_organs_from_cryo.py segment --photos /dev/shm/q288/photos/pelvis --reg /dev/shm/q288/reg.json \
        --seeds data/derived/Q288_seeds.json --z-top -1808 --z-bot -1912 --out /dev/shm/q288/seg.npz
    python3 scripts/cryo/vhf_pelvic_organs_from_cryo.py volume --seg /dev/shm/q288/seg.npz --reg /dev/shm/q288/reg.json \
        --out data/ct_sources/task_outputs/vhf_pelvic_organs_cryo.nii.gz

SOURCE: U.S. National Library of Medicine, The Visible Human Project (public domain): the female 'Fullcolor - direct digital'
cryosection series (IDC 56f8119f-5940-48c1-96ee-8d445dc0b5fd, 0.33 mm pixels, 0.33 mm apart; used every 1 mm) and her torso CT
(IDC b9cf8e7a-...), streamed by vhf_stream_pelvis_q288.py and registered by vhf_register_pelvis_q288.py.

METHOD (badge "photo-segmented, operator-seeded"): a 3-D RANDOM WALKER (Grady 2006, doi:10.1109/TPAMI.2006.233;
skimage.segmentation.random_walker) on the photographs' colour (CIE L*a*b*, 0.67 mm in-plane, 1 mm between levels). Every
boundary is decided by the colour edges of her own photographs. Seeds:
  * ORGAN seeds: small discs placed by eye INSIDE each organ on gridded crops of the photographs, at listed levels only
    (data/derived/Q288_seeds.json, committed: every seed is auditable). No outline is drawn by hand.
  * COMPETING seeds, automatic: photographed fat (cryo_classes_f class 2, value > 150, eroded 2 mm), blue embedding gel,
    near-black bowel content (value < 60, eroded), and her own CT labels
    (colon -> rectum only where the photograph is dark content or gel: the label is 3-5 mm off the rectal wall in places) (TotalSegmentator `total`, data/ct_sources/task_outputs/
    vhf_total.nii.gz) mapped through the registration and eroded 2 mm: urinary_bladder -> bladder, colon -> rectum/colon,
    hip bones / femora / sacrum / gluteals / iliopsoas -> other. Her `small_bowel` label is NOT used: on her unenhanced CT it
    covers her uterus (Q287).
Each organ = the walker's label, per level holes filled, then the 3-D component connected to its seeds. Nothing is
interpolated between levels, nothing is drawn from an atlas."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import nibabel as nib
import numpy as np
from scipy import ndimage as ndi

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.cryo.cryo_classes_f import classify  # noqa: E402

DS = 2                                  # working grid: 2 x 0.333 mm = 0.667 mm
WIN = (300, 780, 580, 1040)             # rows, cols of the streamed window searched (full-res)
LAB = {1: "uterus", 2: "vagina", 3: "urethra", 4: "bladder", 5: "rectum_anal_canal", 9: "other"}
CT_OTHER = (25, 75, 76, 77, 78, 80, 81, 82, 83, 84, 85, 88, 89)


class Reg:
    def __init__(self, path):
        R = json.load(open(path)); self.L = R["levels"]; self.H1 = R["photo_h_1mm"]; self.SC = R["sc"]
        self.cz = np.array([l["cryo_z"] for l in self.L]); self.rz = np.array([l["ras_z"] for l in self.L])

    def k(self, z):
        return int(np.argmin(abs(self.cz - z)))

    def p2frame(self, k, pr, pc):
        l = self.L[k]
        return l["RS"] + (self.H1 - 1 - np.asarray(pr, float) / 3) * self.SC, l["CS"] + (np.asarray(pc, float) / 3) * self.SC

    def frame2p(self, k, fr, fc):
        l = self.L[k]
        return 3 * ((self.H1 - 1) - (np.asarray(fr, float) - l["RS"]) / self.SC), 3 * (np.asarray(fc, float) - l["CS"]) / self.SC


def ct_labels_on_photo(reg, k, lab, shape, r0, c0):
    pr, pc = np.mgrid[0:shape[0], 0:shape[1]]
    fr, fc = reg.p2frame(k, r0 + pr * DS + DS / 2, c0 + pc * DS + DS / 2)
    i = np.clip(np.rint(fc / 0.9375).astype(int), 0, 511); j = np.clip(np.rint(fr / 0.9375).astype(int), 0, 511)
    return lab[i, j, reg.L[k]["ct_k"]]


def segment(a):
    from skimage.color import rgb2lab
    from skimage.segmentation import random_walker
    vol = np.load(a.photos + ".npy", mmap_mode="r"); reg = Reg(a.reg)
    seeds = json.load(open(a.seeds))["seeds"]
    lab = np.asarray(nib.load(REPO / "data/ct_sources/task_outputs/vhf_total.nii.gz").dataobj).astype(np.uint8)
    r0, r1, c0, c1 = WIN; h, w = (r1 - r0) // DS, (c1 - c0) // DS
    zs = [z for z in range(int(a.z_top), int(a.z_bot) - 1, -1)]
    ks = [reg.k(z) for z in zs]
    X = np.zeros((len(zs), h, w, 3), np.float32); S = np.zeros((len(zs), h, w), np.uint8)
    er2 = int(round(2 / (DS / 3)))
    yy, xx = np.mgrid[0:h, 0:w]
    for n, (z, k) in enumerate(zip(zs, ks)):
        px = np.asarray(vol[k, r0:r1, c0:c1]).astype(np.float32)
        sm = px.reshape(h, DS, w, DS, 3).mean(axis=(1, 3))
        X[n] = rgb2lab(np.clip(ndi.uniform_filter(sm, size=(3, 3, 1)) / 255, 0, 1))
        im = sm.astype(np.uint8); cl = classify(im); v = im.max(-1).astype(float)
        r, g, b = (im[..., i].astype(float) for i in range(3))
        other = ndi.binary_erosion((cl == 2) & (v > 150), iterations=er2) | (b > r + 5) | ndi.binary_erosion(v < 60, iterations=2)
        L = ct_labels_on_photo(reg, k, lab, (h, w), r0, c0)
        other |= ndi.binary_erosion(np.isin(L, CT_OTHER), iterations=er2)
        s = np.zeros((h, w), np.uint8); s[other] = 9
        s[ndi.binary_erosion(L == 21, iterations=er2)] = 4
        s[ndi.binary_erosion(L == 20, iterations=er2) & ((v < 100) | (b > r + 5))] = 5   # rectum: her CT label, only on its dark content / gel
        for lb, per in seeds.items():
            for rr, cc, rad in per.get(str(z), []):
                d = ((yy - (rr - r0) / DS) ** 2 + (xx - (cc - c0) / DS) ** 2) <= (rad / DS) ** 2
                if lb != "9":   # no AUTOMATIC competing seed within 8 mm of an organ seed: the pale cervical stroma passes the fat colour rule
                    near = ((yy - (rr - r0) / DS) ** 2 + (xx - (cc - c0) / DS) ** 2) <= ((rad + 24) / DS) ** 2
                    s[near & (s == 9)] = 0
                s[d] = int(lb)
        S[n] = s
    print("seeds:", {LAB[v]: int((S == v).sum()) for v in LAB}, flush=True)
    # restrict the walk to the slab's organ-bearing core: unlabelled pixels far (> 25 mm) from any organ seed become 'other'
    org = np.isin(S, [1, 2, 3])
    if org.any():
        dist = ndi.distance_transform_edt(~org, sampling=(1.0, DS / 3, DS / 3))
        S[(S == 0) & (dist > a.reach)] = 9
    P = random_walker(X, S, beta=a.beta, mode="cg_j", tol=1e-3, channel_axis=-1, spacing=(1.0, DS / 3, DS / 3))
    out = np.zeros_like(P, np.uint8)
    for v in (1, 2, 3):
        m = P == v
        for n in range(len(m)):
            m[n] = ndi.binary_fill_holes(m[n])
        cc, nc = ndi.label(m)
        keep = np.unique(cc[(S == v) & (cc > 0)])
        out[np.isin(cc, keep) & (out == 0)] = v
    np.savez_compressed(a.out, seg=out, walker=P.astype(np.uint8), seeds=S, zs=np.array(zs), ks=np.array(ks), win=np.array(WIN), ds=DS)
    print("SEG_DONE", {LAB[v]: int((out == v).sum()) for v in (1, 2, 3)})


def to_ct_grid(seg_npz, reg_path, ref=REPO / "data/ct_sources/task_outputs/vhf_total.nii.gz"):
    """the walker's labels -> her CT grid (vhf_total.nii.gz: 0.9375 mm, z 1 mm), each CT slice from the photograph level nearest in RAS z"""
    D = np.load(seg_npz); seg = D["seg"]; ks = D["ks"]; r0, r1, c0, c1 = D["win"]; ds = int(D["ds"]); reg = Reg(reg_path)
    img = nib.load(str(ref)); A = img.affine; nz = img.shape[2]; z0 = float(A[2, 3])
    out = np.zeros(img.shape, np.uint8)
    rz = np.array([reg.L[k]["ras_z"] for k in ks])
    ii, jj = np.mgrid[0:512, 0:512]
    fc, fr = ii * 0.9375, jj * 0.9375
    for kk in range(nz):
        zr = z0 + kk
        n = int(np.argmin(abs(rz - zr)))
        if abs(rz[n] - zr) > 0.75 or not seg[n].any():
            continue
        pr, pc = reg.frame2p(int(ks[n]), fr, fc)
        a = np.floor((pr - r0) / ds).astype(int); b = np.floor((pc - c0) / ds).astype(int)
        ok = (a >= 0) & (a < seg.shape[1]) & (b >= 0) & (b < seg.shape[2])
        sl = np.zeros((512, 512), np.uint8); sl[ok] = seg[n][a[ok], b[ok]]
        out[:, :, kk] = sl
    return out, A


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    s = sp.add_parser("segment"); s.add_argument("--photos", required=True); s.add_argument("--reg", required=True)
    s.add_argument("--seeds", required=True); s.add_argument("--z-top", type=float, required=True); s.add_argument("--z-bot", type=float, required=True)
    s.add_argument("--beta", type=float, default=90.0); s.add_argument("--reach", type=float, default=25.0); s.add_argument("--out", required=True)
    v = sp.add_parser("volume"); v.add_argument("--seg", required=True); v.add_argument("--reg", required=True); v.add_argument("--out", required=True)
    v.add_argument("--keep", default="1", help="labels written (comma list); the others are not shipped")
    a = ap.parse_args()
    if a.cmd == "segment":
        segment(a)
    else:
        out, A = to_ct_grid(a.seg, a.reg)
        keep = [int(t) for t in a.keep.split(",")]
        out[~np.isin(out, keep)] = 0
        nib.save(nib.Nifti1Image(out, A), a.out)
        vc = float(abs(np.linalg.det(A[:3, :3]))) / 1000
        print("VOLUME_DONE", {LAB[k]: round(float((out == k).sum()) * vc, 2) for k in keep})


if __name__ == "__main__":
    main()
