"""Q295 tissue oracle: atlas-frame points (x right, y superior, z anterior; mm) -> tissue class from the body's own imaging.
VHF: her fresh CT (torso block + femur-to-toes block, Q-registered shift); VHM: his colour cryosections (frozen CT cannot separate fat),
colour classes of scripts/cryo/cryo_classes.py, registration of scripts/cryo/resample_cryo_to_ct_frame.py.
Classes: 0 unknown (outside the field of view), 1 air, 2 fat, 3 soft tissue (muscle / organ / connective / fluid), 4 bone, 5 lung/gas."""
from __future__ import annotations
import sys
import numpy as np
import nibabel as nib
from scipy import ndimage as ndi

REPO = str(__import__("pathlib").Path(__file__).resolve().parents[3])
sys.path.insert(0, REPO + "/scripts/cryo")
import os
# her torso CT (IDC b9cf8e7a, stacked by scripts/stack_dicom_series.py on the vhf_total grid) and her femur-to-toes CT (IDC af18f5e4,
# scripts/download_idc_series.py + scripts/stack_dicom_series.py --ps 0.722656); neither is stored in the repository
VHF_TORSO = os.environ.get("Q295_VHF_TORSO_CT", "/dev/shm/q295/vhf_torso_0937.nii.gz")
VHF_LEGS = os.environ.get("Q295_VHF_LEGS_CT", "/dev/shm/q295/vhf_legs_ct.nii.gz")
ORIGIN = {"vhf": np.array([7.769, -885.229, 14.137]), "vhm": np.array([-6.035, -895.476, 4.787])}
NAMES = {0: "unknown", 1: "air", 2: "fat", 3: "soft", 4: "bone", 5: "lung/gas"}
HU_FAT = (-190, -30)


def hu_class(h):
    c = np.full(h.shape, 3, np.uint8)
    c[h < -400] = 1
    c[(h >= HU_FAT[0]) & (h <= HU_FAT[1])] = 2
    c[(h < HU_FAT[0]) & (h >= -400)] = 2          # partial volume fat/air at the surface
    c[h > 200] = 4
    return c


class VHF:
    def __init__(self):
        self.vols = []
        for path, shift in ((VHF_TORSO, np.zeros(3)), (VHF_LEGS, np.array([5.99, -3.59, -943.5]))):
            im = nib.load(path)
            self.vols.append((np.asarray(im.dataobj), np.linalg.inv(im.affine), shift))

    def hu(self, P):
        """atlas points -> HU (nan outside both fields of view); torso block wins where both cover"""
        P = np.asarray(P, np.float64) + ORIGIN["vhf"]
        ras = np.c_[P[:, 0], P[:, 2], P[:, 1]]
        out = np.full(len(P), np.nan)
        for vol, Ainv, sh in self.vols:
            todo = np.isnan(out)
            if not todo.any():
                break
            r = ras[todo] - sh
            ijk = (Ainv @ np.c_[r, np.ones(len(r))].T)[:3].T
            ok = np.all((ijk >= 0) & (ijk <= np.array(vol.shape) - 1), 1)
            # inside the reconstruction circle (the scanner's 240 mm radius field)
            ok &= np.hypot(r[:, 0], r[:, 1]) < 238
            v = np.full(len(r), np.nan)
            if ok.any():
                v[ok] = ndi.map_coordinates(vol, ijk[ok].T, order=1, mode="nearest")
            o = out[todo]; o[ok] = v[ok]; out[todo] = o
        return out

    def cls(self, P):
        h = self.hu(P); c = np.zeros(len(h), np.uint8); k = ~np.isnan(h); c[k] = hu_class(h[k]); return c


class VHM:
    """his 1 mm colour cryosections (SCRATCH/vh_cryo/cryo_1mm.npy) -> classes per slice, cached"""
    def __init__(self):
        from cryo_classes import classify
        self.classify = classify
        self.vol = np.load(REPO + "/SCRATCH/vh_cryo/cryo_1mm.npy", mmap_mode="r"); self.cache = {}
        import os
        if os.path.exists(self.PRE):
            self.pre = np.load(self.PRE, mmap_mode="r")

    PRE = "/dev/shm/q295/vhm_cryo_cls.npy"

    def precompute(self):
        """all slices classified once (Base M maps every page level across many cryo slices)"""
        import os
        if not os.path.exists(self.PRE):
            out = np.lib.format.open_memmap(self.PRE + ".tmp.npy", mode="w+", dtype=np.uint8, shape=self.vol.shape[:3])
            for k in range(self.vol.shape[0]):
                out[k] = self.slice_cls(k)
                if len(self.cache) > 4:
                    self.cache.clear()
            out.flush(); del out; os.replace(self.PRE + ".tmp.npy", self.PRE)
        self.pre = np.load(self.PRE, mmap_mode="r")

    def slice_cls(self, idx):
        if getattr(self, "pre", None) is not None:
            return self.pre[idx]
        if idx not in self.cache:
            if len(self.cache) > 40:
                self.cache.clear()
            im = np.asarray(self.vol[idx]); c = self.classify(im)
            out = np.zeros(c.shape, np.uint8)
            out[c == 0] = 1; out[c == 1] = 3; out[c == 2] = 2; out[c == 3] = 3; out[c == 4] = 3; out[c == 5] = 4
            # non-tissue pixels INSIDE the body silhouette (dark kidney / blood / bowel gas / lumen) = 5, not air
            body = ndi.binary_fill_holes(ndi.binary_opening(c > 0, iterations=2))
            out[body & (c == 0)] = 5
            self.cache[idx] = out
        return self.cache[idx]

    def cls(self, P):
        P = np.asarray(P, np.float64) + ORIGIN["vhm"]
        x, y, z = P[:, 0], P[:, 2], P[:, 1]                 # RAS
        legs = z < -863.0
        c = np.where(legs, (336.0 - x) / 0.99, (338.0 - x) / 0.99)
        r = np.where(legs, (y + 163.96) / 0.99, (y + 159.96) / 0.99)
        idx = np.rint(-16.0 - z).astype(int)
        out = np.zeros(len(P), np.uint8)
        H, W = self.vol.shape[1], self.vol.shape[2]
        ri, ci = np.rint(r).astype(int), np.rint(c).astype(int)
        ok = (idx >= 0) & (idx < self.vol.shape[0]) & (ri >= 0) & (ri < H) & (ci >= 0) & (ci < W)
        for k in np.unique(idx[ok]):
            m = ok & (idx == k)
            out[m] = self.slice_cls(int(k))[ri[m], ci[m]]
        return out


def make(body):
    return VHF() if body == "vhf" else VHM()


def coarse_map(reg, grid, y0, step=4):
    """the registration evaluated on a step-pixel lattice and bilinearly interpolated (smooth TPS: < 0.1 mm error at 4 mm)"""
    u0, v0, res, W, H = grid
    hj, hi = np.arange(0, H + step, step), np.arange(0, W + step, step)
    JJ, II = np.meshgrid(hj, hi, indexing="ij")
    Q = np.c_[u0 + (II.ravel() + 0.5) * res, np.full(II.size, y0), v0 + (JJ.ravel() + 0.5) * res]
    M = reg(Q).reshape(len(hj), len(hi), 3)
    jj, ii = np.mgrid[0:H, 0:W]
    out = np.stack([ndi.map_coordinates(M[..., k], [jj.ravel() / step, ii.ravel() / step], order=1, mode="nearest") for k in range(3)], 1)
    return out


def slice_classes(orc, reg, grid, y0, body, max_shift=12, min_area=400):
    """tissue class of every pixel of one axial page slice, with a per-body-part in-plane shift (<= max_shift mm, integer pixels) that
    best overlays the imaging body silhouette on the page's own skin silhouette (corrects the few-mm CT/cryo-to-page offsets and limbs
    that moved between blocks). Returns (cls (H,W) uint8, shifts list)."""
    u0, v0, res, W, H = grid
    jj, ii = np.mgrid[0:H, 0:W]
    P = np.c_[u0 + (ii.ravel() + 0.5) * res, np.full(H * W, y0), v0 + (jj.ravel() + 0.5) * res]
    if reg is not None:
        P = coarse_map(reg, grid, y0)
    c = orc.cls(P).reshape(H, W)
    ob = (c >= 2)
    out = c.copy(); shifts = []
    lab, n = ndi.label(body)
    for k in range(1, n + 1):
        m = lab == k
        if m.sum() < min_area:
            continue
        ys, xs = np.nonzero(m); a0, a1 = max(ys.min() - max_shift, 0), min(ys.max() + max_shift + 1, H); b0, b1 = max(xs.min() - max_shift, 0), min(xs.max() + max_shift + 1, W)
        A_ = m[a0:a1, b0:b1].astype(np.float32); B_ = ob[a0:a1, b0:b1].astype(np.float32)
        best = (-1.0, 0, 0)
        FA = np.fft.rfft2(A_); FB = np.fft.rfft2(B_)
        cc = np.fft.irfft2(FA * np.conj(FB), s=A_.shape)          # cc[dy,dx] = sum A(p) B(p - d)
        for dy in range(-max_shift, max_shift + 1):
            for dx in range(-max_shift, max_shift + 1):
                v = cc[dy % A_.shape[0], dx % A_.shape[1]]
                if v > best[0]:
                    best = (v, dy, dx)
        _, dy, dx = best
        inter0 = float((A_ * B_).sum())
        if best[0] <= inter0 * 1.01:
            dy = dx = 0
        if dy or dx:
            src_j = np.clip(ys - dy, 0, H - 1); src_i = np.clip(xs - dx, 0, W - 1)
            out[ys, xs] = c[src_j, src_i]
        shifts.append((int(dy), int(dx), int(m.sum())))
    slice_classes.last_P = P
    return out, shifts
