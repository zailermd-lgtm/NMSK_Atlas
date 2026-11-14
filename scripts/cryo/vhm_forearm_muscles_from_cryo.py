"""Male RIGHT forearm muscles from his FULL-RESOLUTION cryosection crops (Q62 step 1, male). Rule-based; badged.

    python3 scripts/cryo/vhm_forearm_muscles_from_cryo.py --crops SCRATCH/vh_cryo_m_fa \
        --ct SCRATCH/vh_idc/nii/vhm_torso_0937.nii.gz --bones data/ct_sources/task_outputs/vhm_arm_bones_cryo_completed.nii.gz \
        --out data/ct_sources/task_outputs/vhm_forearm_muscles_cryo.nii.gz --cache SCRATCH/vh_cryo_m_fa/track.pkl

The male counterpart of vhf_forearm_muscles_from_cryo.py (her rules, her watershed, her report format); what differs:

DATA. crops.npy (vhm_stream_crops.py): 0.33 mm RGB crops of one fixed photograph box (crops_bbox.json "box" =
r0,r1,c0,c1) at every 1 mm level, levels = DICOM instance numbers (1001 = vertex): torso RAS z = 985 - instance,
atlas y = z + 895.476. His photographs of this block lie with the spine at the TOP and the patient's left on the
image RIGHT (checked on the 1 mm arm stream, vhm_arm_muscles_v2.py) -- the same handedness as her crops (photo top =
posterior, photo left = the subject's right), so her marker offsets (e: ulna -> radius, n: flexor) carry over.

REGISTRATION (photo -> his torso CT, per level). He has no registered cryo frame in the repository, so each level is
placed by the body-centroid translation of vhm_arm_muscles_v2.py (photograph tissue silhouette vs CT body silhouette,
frames_1mm.npy vs vhm_torso_0937.nii.gz; 0.99 mm per 1 mm-frame pixel, 0.33 mm per crop pixel), and then the
photographed bone discs are laid ON his CT radius/ulna sections (vhm_arm_bones_cryo_completed.nii.gz, labels 2/3):
the per-level residual (disc centre minus CT section centroid, median-filtered over 21 levels) is subtracted, so the
muscles wrap the bones the viewer shows (subject ct_vhm_arm). Both residuals are in the report
(ct_to_photo_shift_mm: body-centroid registration only; after_bone_correction_mm: what remains).

COLOURS (his frozen block, cryo_classes.classify): muscle = class 3 (red-brown, uniformly dark), bright = fat | pale |
white (his cortex is white, the marrow cream, both bright); the bone disc = the largest circle inscribed in the bright
class (marrow holes <= 400 mm2 filled) within reach of the previous level's centre and >= 7 mm from the skin, seeded at
one level (--anchor, default instance 1700) from the CT sections (search 15 mm), tracked both ways as hers.
The pale fascial septa are thin but visible: the split is her marker watershed on the white top-hat (disk 4 px) of the
brightness inside the muscle mass.

RULES: MARKER_RULES are hers (textbook positions, mm from the bone SURFACES in the ulna-radius frame, per f-window),
their mm offsets scaled by --scale (default 1.15: a 90 kg, 1.80 m man against her). Compartments (flexor / lateral /
extensor), the seed snap, the segment (radial head = top of his CT radius label, instance 1613, to the last level
with two separate discs) and the boundary scoring are hers (imported). Muscles whose within-compartment boundaries
run on a pale line at >= 70 % of levels are shipped; the rest are merged into named compartments
(vhm_forearm_merge.json, --merge) and mapped to null with the reason.

ORIENTATION (flexor side) checked two independent ways: (1) the frame itself -- the ulna's subcutaneous posterior
border is the skin nearest the ulna, the flexor side is away from it; (2) his CT thumb metacarpal (label 10
metacarpals_right, the component farthest from the line through the others at a hand level) lies on the flexor side
of the last tracked bone line (the palm). The flexor/extensor muscle-area ratio is reported as a third, weaker check.

LIMITS: translation-only registration per level (no rotation), CT bones only as seeds; the radial head/neck of his CT
radius is partly labelled ulna (known defect of vhm_arm_bones), so the proximal end of the segment is +-10 mm; the
carpus is not entered (the track ends where the discs merge); nothing here is anatomy -- badge it.

Output: label volume (torso RAS, 0.5 x 0.5 x 1 mm, positive-determinant affine; convert with
--origin '-6.035,-895.476,4.787'), label key, subject mapping, report, montage PNG (6 levels, outlines on the photographs).
"""
from __future__ import annotations

import argparse
import json
import os
import pickle
import sys
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "2"); os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
import numpy as np  # noqa: E402
import nibabel as nib  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402
from scipy import ndimage as ndi  # noqa: E402
from skimage.morphology import white_tophat, disk  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(Path(__file__).resolve().parent))
from cryo_classes import classify  # noqa: E402
from scripts.cryo.vhf_forearm_muscles_from_cryo import (  # noqa: E402
    MARKER_RULES as HER_RULES, GROUP_ID, SEED_PX, bone_frame, compartments, snap, split_level, boundary_support,
    dt_bone as _dt_bone, bone_mask, level_fraction, palette)

PX = 0.33                                        # mm per full-resolution photograph pixel (3 x 0.33 = 0.99 per 1 mm-frame px)
PX1 = 0.99                                       # mm per 1 mm-frame (3x downsampled) pixel
Z_OF_INST = 985.0                                # torso RAS z = 985 - instance
ORIGIN = (-6.035, -895.476, 4.787)               # atlas origin in his torso RAS (x, z, y components)
BONES_AFF = (350.0, 240.0, -1113.0)              # vhm_arm_bones: x = 350 - i, y = 240 - j, z = -1113 + k
BONE_ID = {"radius": 2, "ulna": 3, "carpals": 9, "metacarpals": 10}
BADGE = "rule-based"
SOURCE = ("U.S. National Library of Medicine, The Visible Human Project (public domain), male cryosections at full "
          "resolution (0.33 mm) and frozen CT via the NCI Imaging Data Commons. Derived data "
          "(scripts/cryo/vhm_forearm_muscles_from_cryo.py), rule-based.")
MARROW_MM2 = 400.0
EXPECTED_CM3 = {"flexor_carpi_ulnaris": (25, 35), "flexor_digitorum_profundus": (55, 70), "flexor_digitorum_superficialis": (40, 55),
                "brachioradialis": (35, 45), "extensor_digitorum": (15, 25)}     # reviewer-supplied ranges for a 90 kg man; not verified against literature


def plausibility(vols):
    """{muscle: {cm3, expected, verdict}} for the shipped muscles with a reviewer-supplied range; 'off >2x' when the
    volume is above twice the upper or below half the lower bound."""
    out = {}
    for nm, (lo, hi) in EXPECTED_CM3.items():
        if nm in vols:
            v = vols[nm]; out[nm] = {"cm3": v, "expected_cm3": [lo, hi], "verdict": "off >2x" if (v > 2 * hi or v < lo / 2) else ("in range" if lo <= v <= hi else "outside range, < 2x")}
    return out


def scaled_rules(scale, rules=HER_RULES):
    """Her marker table with the mm offsets scaled (f-windows and groups unchanged)."""
    return {nm: (anc, em * scale, nm_ * scale, f0, f1, grp) for nm, (anc, em, nm_, f0, f1, grp) in rules.items()}


def marker_positions(U, R, ru, rr, e, n, f, rules, active_only=True):
    """Rule seeds for level fraction f: {name: (row, col)} px. Offsets are mm from the anchor bone's SURFACE."""
    U = np.asarray(U, float); R = np.asarray(R, float); M = (U + R) / 2; out = {}
    for name, (anc, em, nm, f0, f1, _g) in rules.items():
        if active_only and not (f0 <= f <= f1):
            continue
        base = {"U": U, "R": R, "M": M}[anc]; rad = {"U": ru, "R": rr, "M": 0.0}[anc]
        ev = em / PX + (np.sign(em) * rad if em else 0.0); nv = nm / PX + (np.sign(nm) * rad if nm else 0.0)
        out[name] = tuple(base + e * ev + n * nv)
    return out


def inst_to_z(inst):
    return Z_OF_INST - float(inst)


def photo_to_ras(T, box, pr, pc, corr=(0.0, 0.0)):
    """Crop px (row, col) -> torso RAS (x, y) under the level's translation T = (rowB, colB, xB, yB) (1 mm-frame px /
    RAS mm) and crop box (r0, r1, c0, c1); corr (px) = shift subtracted first (bone correction)."""
    rowB, colB, xB, yB = T; r0, _, c0, _ = box
    row1 = (np.asarray(pr, float) - corr[0] + r0) / 3.0; col1 = (np.asarray(pc, float) - corr[1] + c0) / 3.0
    return xB - (col1 - colB) * PX1, yB + (row1 - rowB) * PX1


def ras_to_photo(T, box, x, y, corr=(0.0, 0.0)):
    rowB, colB, xB, yB = T; r0, _, c0, _ = box
    row1 = rowB + (np.asarray(y, float) - yB) / PX1; col1 = colB - (np.asarray(x, float) - xB) / PX1
    return row1 * 3.0 - r0 + corr[0], col1 * 3.0 - c0 + corr[1]


def thumb_side(centroids, n_ras):
    """centroids: (k, 2) RAS (x, y) of the metacarpal components at one level (k >= 4); the thumb = the one farthest
    from the line fitted through the others. Returns (signed offset along n_ras in mm, thumb index)."""
    P = np.asarray(centroids, float); best = None
    for i in range(len(P)):
        Q = np.delete(P, i, 0); c = Q.mean(0); u, s, vt = np.linalg.svd(Q - c); d = vt[0]; nrm = np.array([-d[1], d[0]])
        off = float(np.dot(P[i] - c, nrm)); res = float(np.abs((Q - c) @ nrm).mean())
        score = abs(off) - res
        if best is None or score > best[0]:
            best = (score, i, off, nrm)
    _, i, off, nrm = best
    sign = 1.0 if np.dot(nrm, n_ras) >= 0 else -1.0
    return off * sign, i


def ship_or_merge(support, groups, min_frac=0.7, min_levels=5):
    """From the boundary_support summary {"a|b": {levels, frac_levels_ratio_ge_1.8}}: a muscle ships when every
    within-compartment boundary it has (>= min_levels shared levels) runs on a pale line at >= min_frac of levels;
    the weak pairs are returned for merging. Returns (ship set, weak pairs list)."""
    weak = []; involved = set()
    for key, v in support.items():
        a, b = key.split("|")
        if groups.get(a) != groups.get(b) or v["levels"] < min_levels:
            continue
        involved |= {a, b}
        if v["frac_levels_ratio_ge_1.8"] < min_frac:
            weak.append((a, b, v["frac_levels_ratio_ge_1.8"]))
    bad = {a for a, b, _ in weak} | {b for a, b, _ in weak}
    return set(groups) - bad, weak


# ----------------------------------------------------------------------------------------------- data
class MaleCrops:
    def __init__(self, crops_dir, ct_path, bones_path):
        d = Path(crops_dir); self.b = json.load(open(d / "crops_bbox.json")); self.box = self.b["box"]; self.levels = self.b["levels"]
        self.a = np.load(d / "crops.npy", mmap_mode="r"); self.f1 = np.load(d / "frames_1mm.npy", mmap_mode="r")
        ct = nib.load(ct_path); self.A = ct.affine; self.ct = ct.dataobj
        self.bones = np.asanyarray(nib.load(bones_path).dataobj); self.n = len(self.levels); self._T = {}

    def image(self, j):
        return np.asarray(self.a[j])

    def level(self, j):
        inst = self.levels[j]; z = inst_to_z(inst)
        return {"j": j, "inst": inst, "z": z, "y": z - ORIGIN[1], "T": self.register(j)}

    def register(self, j):
        """Body-centroid translation (vhm_arm_muscles_v2.py): (rowB, colB) 1 mm-frame px of the photograph body,
        (xB, yB) RAS of the CT body at the same z."""
        if j in self._T:
            return self._T[j]
        c = classify(np.asarray(self.f1[j])); tissue = ndi.binary_fill_holes(ndi.binary_closing(c > 0, iterations=2)); tissue[:40] = False
        lab, n = ndi.label(tissue); sizes = np.bincount(lab.ravel())[1:]
        body_p = np.isin(lab, np.where(sizes >= 0.02 * sizes.max())[0] + 1)
        z = inst_to_z(self.levels[j]); A = self.A; kc = int(round((z - A[2, 3]) / A[2, 2]))
        sl = np.asarray(self.ct[:, :, kc]); body_c = ndi.binary_fill_holes(sl > -500); lc, nc = ndi.label(body_c)
        sc = np.bincount(lc.ravel())[1:]; body_c = np.isin(lc, np.where(sc >= 0.02 * sc.max())[0] + 1)
        rowB, colB = ndi.center_of_mass(body_p); ic, jc = ndi.center_of_mass(body_c)
        T = (float(rowB), float(colB), float(A[0, 3] + A[0, 0] * ic), float(A[1, 3] + A[1, 1] * jc)); self._T[j] = T
        return T

    def bone_section(self, L, name):
        """(centroid (row, col) px, mask) of his CT bone label at this level under the body registration, or None."""
        k = int(round(L["z"] - BONES_AFF[2]))
        if not (0 <= k < self.bones.shape[2]):
            return None
        m = self.bones[:, :, k] == BONE_ID[name]
        if not m.any():
            return None
        ii, jj = np.where(m); x = BONES_AFF[0] - ii; y = BONES_AFF[1] - jj
        pr, pc = ras_to_photo(L["T"], self.box, x, y); shape = self.a.shape[1:3]
        r = np.rint(pr).astype(int); c = np.rint(pc).astype(int); ok = (r >= 0) & (r < shape[0]) & (c >= 0) & (c < shape[1])
        mask = np.zeros(shape, bool); mask[r[ok], c[ok]] = True; mask = ndi.binary_closing(ndi.binary_dilation(mask, iterations=2), iterations=2)
        return (float(pr.mean()), float(pc.mean())), mask


# ----------------------------------------------------------------------------------------------- photo classes
def island_mask(c, ref, prev_isl=None, max_px=120000):
    """The forearm's own tissue component (classify > 0 closed and filled), separated from the trunk it lies beside.
    With the previous level's island (tracking): the tissue is split by the nearest muscle core -- forearm muscle =
    class-3 components lying (>= 50 %) inside the previous island dilated 10 px, trunk muscle = the other components
    >= 500 px, fat to the forearm when twice as close to its muscle as to the trunk's, <= 20 mm from it and within 12 px of the
    previous island -- so the levels where his forearm's skin is pressed flat on the trunk's (1711..1750) still separate.
    Otherwise (the anchor), the smallest erosion (12..60 px) that leaves the component at `ref` under max_px, grown
    back inside the tissue."""
    t0 = ndi.binary_fill_holes(ndi.binary_closing(c > 0, iterations=3))
    rr, cc = int(round(ref[0])), int(round(ref[1]))
    if prev_isl is not None:
        mm = ndi.binary_closing(c == 3, iterations=3); lab, n = ndi.label(mm)
        if n:
            idx = range(1, n + 1); sizes = np.asarray(ndi.sum(mm, lab, idx)); near = ndi.binary_dilation(prev_isl, iterations=10)
            inside = np.asarray(ndi.sum(near, lab, idx)) / np.maximum(sizes, 1)
            F = np.isin(lab, np.where(inside >= 0.5)[0] + 1); T = mm & ~F & np.isin(lab, np.where(sizes >= 500)[0] + 1)
            if F.any():
                dF = ndi.distance_transform_edt(~F); dT = ndi.distance_transform_edt(~T) if T.any() else np.full(dF.shape, np.inf)
                keep = t0 & (dF < 0.5 * dT) & (dF <= 60) & ndi.binary_dilation(prev_isl, iterations=12)
                lab2, n2 = ndi.label(keep)                        # fat is the forearm's when twice as close to its muscle as to the trunk's, <= 20 mm from it, near the previous island
                if n2:
                    i = lab2[rr, cc] if (0 <= rr < lab2.shape[0] and 0 <= cc < lab2.shape[1]) else 0
                    if i == 0:
                        ii = ndi.distance_transform_edt(lab2 == 0, return_indices=True)[1]
                        r_ = min(max(rr, 0), lab2.shape[0] - 1); c_ = min(max(cc, 0), lab2.shape[1] - 1); i = lab2[ii[0][r_, c_], ii[1][r_, c_]]
                    g = ndi.binary_fill_holes(lab2 == i)
                    if g.sum() < max_px:
                        return g, 0
    for it in (12, 18, 24, 30, 40, 50, 60):
        t = ndi.binary_erosion(t0, iterations=it); lab, n = ndi.label(t)
        if n == 0:
            continue
        i = lab[rr, cc] if (0 <= rr < lab.shape[0] and 0 <= cc < lab.shape[1]) else 0
        if i == 0:
            idx = ndi.distance_transform_edt(lab == 0, return_indices=True)[1]
            r_ = min(max(rr, 0), lab.shape[0] - 1); c_ = min(max(cc, 0), lab.shape[1] - 1); i = lab[idx[0][r_, c_], idx[1][r_, c_]]
        m = lab == i
        if m.sum() < max_px:
            g = m
            for _ in range(it + 2):
                g = ndi.binary_dilation(g, iterations=1) & t0
            return g, it
    return None, None


def bright_filled(c, isl):
    """fat | pale | white closed 2 px with holes <= 400 mm2 (the marrow) filled."""
    p0 = ndi.binary_closing(np.isin(c, (2, 4, 5)) & isl, iterations=2); holes = ndi.binary_fill_holes(p0) & ~p0; hl, hn = ndi.label(holes)
    if hn:
        hs = ndi.sum(holes, hl, range(1, hn + 1)); small = np.zeros(hn + 1, bool); small[1:] = hs * PX * PX <= MARROW_MM2; p0 = p0 | small[hl]
    return p0


def dt_bone(dt, dist, prev, search_mm, skin_mm=7.0, min_r_mm=4.0):
    """Her inscribed-circle rule in his px (PX = 0.33): the search radius and skin clearance are given in mm."""
    yy, xx = np.mgrid[0:dt.shape[0], 0:dt.shape[1]]
    win = (np.hypot(yy - prev[0], xx - prev[1]) * PX <= search_mm) & (dist * PX >= skin_mm)
    if not win.any():
        return None
    v = np.where(win, dt, -1.0); cy, cx = np.unravel_index(int(np.argmax(v)), v.shape); r = float(dt[cy, cx])
    return (float(cy), float(cx), r) if r * PX >= min_r_mm else None


# ----------------------------------------------------------------------------------------------- bone tracking
def track_bones(crops, j_anchor, j_lo, j_hi, log=print, merge_mm=15.0, lost_max=8):
    out = {}; residual = {}
    L = crops.level(j_anchor); cent = {}
    for b in ("radius", "ulna"):
        s = crops.bone_section(L, b)
        if s is None:
            raise SystemExit(f"no CT {b} section at anchor level {j_anchor}")
        cent[b] = s[0]

    def one(j, prev, lost, first=False, prev_isl=None):
        L = crops.level(j); im = crops.image(j); c = classify(im); ref = tuple(np.mean([prev["radius"], prev["ulna"]], axis=0))
        isl, er = island_mask(c, ref, prev_isl)
        if isl is None:
            return None
        bright = bright_filled(c, isl); dt = ndi.distance_transform_edt(bright); dist = ndi.distance_transform_edt(isl)
        rec = {"island": isl, "erode": er, "muscle": (c == 3) & isl, "L": L, "found": {}, "ct": {}}
        for b in ("radius", "ulna"):
            h = dt_bone(dt, dist, prev[b], 15.0 if first else 6.0 + 2.0 * lost[b])
            if h is None:
                rec[b] = (prev[b][0], prev[b][1], 0.0, None); rec["found"][b] = False
            else:
                rec[b] = (h[0], h[1], h[2], bone_mask(bright, *h)); rec["found"][b] = True
            s = crops.bone_section(L, b)
            if s is not None:
                rec["ct"][b] = s[0]
                if rec["found"][b]:
                    residual.setdefault(b, {})[j] = [round(float((rec[b][0] - s[0][0]) * PX), 1), round(float((rec[b][1] - s[0][1]) * PX), 1)]
        return rec

    rec = one(j_anchor, cent, {"radius": 0, "ulna": 0}, first=True)
    if rec is None or not all(rec["found"].values()):
        raise SystemExit("bones not found in the photograph at the anchor level")
    out[j_anchor] = rec
    for rng in (range(j_anchor - 1, j_lo - 1, -1), range(j_anchor + 1, j_hi + 1)):
        prev = {b: out[j_anchor][b][:2] for b in ("radius", "ulna")}; lost = {"radius": 0, "ulna": 0}; prev_isl = out[j_anchor]["island"]
        for j in rng:
            r = one(j, prev, lost, prev_isl=prev_isl)
            if r is None:
                log(f"  bone track stops at level {j} (no island)"); break
            prev_isl = r["island"]
            for b in ("radius", "ulna"):
                if r["found"][b]:
                    prev[b] = r[b][:2]; lost[b] = 0
                else:
                    lost[b] += 1
            if max(lost.values()) > lost_max:
                log(f"  bone track stops at level {j} (bone lost)"); break
            if np.hypot(prev["radius"][0] - prev["ulna"][0], prev["radius"][1] - prev["ulna"][1]) * PX < merge_mm:
                log(f"  bone track stops at level {j} (discs merge)"); break
            out[j] = r
    return out, residual


def segment_bounds(track, crops):
    """Top: the first tracked level (from the elbow) with both discs found at which his CT radius label has a section
    (its top is the radial head); bottom: the last tracked level."""
    js = sorted(track); top = [j for j in js if "radius" in track[j]["ct"] and all(track[j]["found"].values())]
    return (min(top), max(js)) if top else (None, None)


def bone_correction(track, residual, size=21):
    """Per level, the px shift (row, col) that lays the photographed discs on the CT sections: the mean over both bones
    of the residual, median-filtered over `size` levels and held constant beyond the last level with a residual."""
    js = sorted(track); per = {}
    for j in js:
        v = [residual[b][j] for b in residual if j in residual[b]]
        if v:
            per[j] = np.mean(v, axis=0) / PX
    if not per:
        return {j: np.zeros(2) for j in js}
    ks = np.array(sorted(per)); arr = np.array([per[k] for k in ks])
    sm = np.stack([ndi.median_filter(arr[:, i], size=min(size, len(ks)), mode="nearest") for i in range(2)], 1)
    return {j: np.array([np.interp(j, ks, sm[:, 0]), np.interp(j, ks, sm[:, 1])]) for j in js}


# ----------------------------------------------------------------------------------------------- per-level split
def level_region(t):
    isl = t["island"]; region = ndi.binary_closing(t["muscle"], iterations=3) & isl
    holes = ndi.binary_fill_holes(region) & ~region; hl, hn = ndi.label(holes)
    if hn:
        hs = ndi.sum(holes, hl, range(1, hn + 1)); small = np.zeros(hn + 1, bool); small[1:] = hs * PX * PX <= 8.0; region |= small[hl]
    bones = np.zeros(isl.shape, bool)
    for b in ("radius", "ulna"):
        if t[b][3] is not None:
            bones |= ndi.binary_dilation(t[b][3], iterations=2)
    return region & ~bones


def level_frame(t, orient_prev):
    U = np.array(t["ulna"][:2]); R = np.array(t["radius"][:2]); isl = t["island"]
    dist_out, idx = ndi.distance_transform_edt(isl, return_indices=True); um = t["ulna"][3]
    if um is not None and um.any():
        ys, xs = np.where(um); k = np.argmin(dist_out[ys, xs]); skin = np.array([idx[0][ys[k], xs[k]], idx[1][ys[k], xs[k]]], float) - U
    else:
        ui, uj = int(round(U[0])), int(round(U[1])); skin = np.array([idx[0][ui, uj], idx[1][ui, uj]], float) - U
    e, n, d = bone_frame(U, R, skin)
    flipped = False
    if orient_prev is not None and np.dot(n, orient_prev) < 0:
        n = -n; flipped = True
    return U, R, e, n, d, flipped


def run(a, log=print):
    crops = MaleCrops(a.crops, a.ct, a.bones); cache = Path(a.cache) if a.cache else None
    j_anchor = crops.levels.index(a.anchor); j_lo = crops.levels.index(a.lo) if a.lo else 0; j_hi = crops.levels.index(a.hi) if a.hi else crops.n - 1
    if a.hi is None:                                  # the track ends at the radiocarpal joint = the top of his CT carpal label
        kc = np.where((crops.bones == BONE_ID["carpals"]).any(axis=(0, 1)))[0]
        if len(kc):
            inst_c = int(round(Z_OF_INST - (BONES_AFF[2] + kc.max())))      # proximal end of the carpus = largest z
            if inst_c in crops.levels:
                j_hi = min(j_hi, crops.levels.index(inst_c)); log(f"track capped at instance {inst_c} (top of his CT carpals)")
    if cache and cache.exists():
        track, residual = pickle.load(open(cache, "rb")); log(f"bone track from cache {cache}")
    else:
        track, residual = track_bones(crops, j_anchor, j_lo, j_hi, log)
        if cache:
            pickle.dump((track, residual), open(cache, "wb"), protocol=4)
    j_top, j_bot = segment_bounds(track, crops)
    if j_top is None:
        raise SystemExit("no level with two separate bone discs")
    corr = bone_correction(track, residual)
    log(f"segment levels {crops.levels[j_top]}..{crops.levels[j_bot]} (instances; atlas y {crops.level(j_top)['y']:.0f} .. {crops.level(j_bot)['y']:.0f})")
    rules = scaled_rules(a.scale); names = list(rules); ids = {nm: i + 1 for i, nm in enumerate(names)}; groups = {nm: rules[nm][5] for nm in names}
    labels_by_level = {}; area = {nm: 0.0 for nm in names}; unassigned = 0.0; orient_prev = None; frames = {}; support = {}; flips = 0
    area_side = {"flexor": 0.0, "extensor": 0.0}
    for j in range(j_top, j_bot + 1):
        t = track.get(j)
        if t is None:
            continue
        U, R, e, n, d, fl = level_frame(t, orient_prev); orient_prev = n; flips += fl; ru, rr = t["ulna"][2], t["radius"][2]
        f = level_fraction(j, j_top, j_bot); frames[j] = {"U": U.tolist(), "R": R.tolist(), "e": e.tolist(), "n": n.tolist(), "f": round(f, 3), "d_mm": round(d * PX, 1)}
        region = level_region(t); comp = compartments(region.shape, U, R, ru, rr, e, n)
        yy, xx = np.mgrid[0:region.shape[0], 0:region.shape[1]]; tt = (yy - U[0]) * n[0] + (xx - U[1]) * n[1]
        area_side["flexor"] += (region & (tt > 0)).sum() * PX * PX; area_side["extensor"] += (region & (tt <= 0)).sum() * PX * PX
        th = white_tophat(crops.image(j).max(-1).astype(np.float32), disk(4))
        seeds = marker_positions(U, R, ru, rr, e, n, f, rules); frames[j]["seeds"] = {nm: [float(p[0]), float(p[1])] for nm, p in seeds.items()}
        cur, left = split_level(th, region, comp, seeds, ids, groups)
        for nm, m in cur.items():
            area[nm] += m.sum() * PX * PX
        unassigned += left.sum() * PX * PX
        for pair, v in boundary_support(th, cur, ids).items():
            support.setdefault(pair, []).append((j,) + v)
        lab = np.zeros(region.shape, np.uint8)
        for nm, m in cur.items():
            lab[m] = ids[nm]
        labels_by_level[j] = lab
        if j % 20 == 0:
            log(f"  level {crops.levels[j]} f={f:.2f} y={t['L']['y']:.0f} regions={len(cur)} unassigned={left.sum() * PX * PX:.0f} mm2")
    return crops, track, residual, corr, (j_top, j_bot), labels_by_level, ids, area, unassigned, frames, support, flips, area_side


def to_volume(crops, labels_by_level, corr, dx=0.5):
    """Per-level label images onto one torso-RAS grid (dx mm in-plane, 1 mm along z). Returns (vol, affine)."""
    js = sorted(labels_by_level); ext = []
    for j in js:
        lab = labels_by_level[j]; ys, xs = np.where(lab > 0)
        if len(ys) == 0:
            continue
        L = crops.level(j); x, y = photo_to_ras(L["T"], crops.box, [ys.min(), ys.max()], [xs.min(), xs.max()], corr[j]); ext.append((x.min(), x.max(), y.min(), y.max()))
    ext = np.array(ext); x0, x1 = ext[:, 0].min() - 2, ext[:, 1].max() + 2; y0, y1 = ext[:, 2].min() - 2, ext[:, 3].max() + 2
    zs = np.array([crops.level(j)["z"] for j in js]); z0, z1 = np.floor(zs.min()), np.ceil(zs.max())
    nx, ny, nz = int(np.ceil((x1 - x0) / dx)) + 1, int(np.ceil((y1 - y0) / dx)) + 1, int(z1 - z0) + 1
    vol = np.zeros((nx, ny, nz), np.uint8); gx = x0 + dx * np.arange(nx); gy = y0 + dx * np.arange(ny)
    for k in range(nz):
        z = z0 + k; i = int(np.argmin(np.abs(zs - z)))
        if abs(zs[i] - z) > 0.5:
            continue
        j = js[i]; L = crops.level(j); lab = labels_by_level[j]
        pr, _ = ras_to_photo(L["T"], crops.box, np.full(ny, gx[0]), gy, corr[j]); _, pc = ras_to_photo(L["T"], crops.box, gx, np.full(nx, gy[0]), corr[j])
        r = np.rint(pr).astype(int); c = np.rint(pc).astype(int)
        okr = np.where((r >= 0) & (r < lab.shape[0]))[0]; okc = np.where((c >= 0) & (c < lab.shape[1]))[0]
        if len(okr) == 0 or len(okc) == 0:
            continue
        sub = lab[np.ix_(r[okr], c[okc])]                      # (ny_ok, nx_ok)
        sl = np.zeros((nx, ny), np.uint8); sl[np.ix_(okc, okr)] = sub.T; vol[:, :, k] = sl
    aff = np.array([[dx, 0, 0, x0], [0, dx, 0, y0], [0, 0, 1.0, z0], [0, 0, 0, 1]])
    return vol, aff


def montage(crops, track, labels_by_level, ids, frames, levels, path, colors):
    tiles = []
    for j in levels:
        t = track.get(j); lab = labels_by_level.get(j)
        if t is None or lab is None:
            continue
        im = crops.image(j).copy(); isl = t["island"]; ys, xs = np.where(isl)
        r0, r1, c0, c1 = max(0, ys.min() - 6), ys.max() + 6, max(0, xs.min() - 6), xs.max() + 6
        for nm, l in ids.items():
            m = lab == l
            if m.any():
                edge = m & ~ndi.binary_erosion(m, iterations=2); im[edge] = colors[l]
        for b in ("radius", "ulna"):
            if t[b][3] is not None:
                e = t[b][3] & ~ndi.binary_erosion(t[b][3], iterations=2); im[e] = (255, 255, 255)
        sub = Image.fromarray(im[r0:r1, c0:c1]); dr = ImageDraw.Draw(sub); fr = frames.get(j)
        if fr:
            U = np.array(fr["U"]) - (r0, c0); R = np.array(fr["R"]) - (r0, c0); n = np.array(fr["n"])
            dr.line([(U[1], U[0]), (R[1], R[0])], fill=(255, 255, 255), width=1)
            M = (U + R) / 2; dr.line([(M[1], M[0]), (M[1] + n[1] * 30, M[0] + n[0] * 30)], fill=(0, 255, 255), width=2)
            for nm, p in fr.get("seeds", {}).items():
                y, x = p[0] - r0, p[1] - c0; col = colors[ids.get(nm, 0)]
                dr.line([(x - 4, y), (x + 4, y)], fill=col, width=2); dr.line([(x, y - 4), (x, y + 4)], fill=col, width=2)
        dr.text((3, 3), f"i{t['L']['inst']} y{t['L']['y']:.0f} f{fr['f'] if fr else '-'}", fill=(255, 255, 0))
        for nm, l in ids.items():
            m = lab[r0:r1, c0:c1] == l
            if m.sum() > 60:
                cy, cx = np.mean(np.where(m), axis=1); dr.text((cx - 8, cy - 4), nm.split("_")[0][:3] + "".join(w[0] for w in nm.split("_")[1:]), fill=colors[l])
        tiles.append(sub)
    if not tiles:
        return None
    cols = 3; rows = (len(tiles) + cols - 1) // cols; tw = max(t.width for t in tiles); th = max(t.height for t in tiles)
    out = Image.new("RGB", (cols * tw, rows * th))
    for i, t in enumerate(tiles):
        out.paste(t, ((i % cols) * tw, (i // cols) * th))
    out.save(path); return str(path)


def thumb_check(crops, frames, j_bot):
    """His CT thumb metacarpal against the flexor normal of the last tracked frame, at the hand level with the most
    metacarpal components (>= 4). Returns dict or None."""
    fr = frames[j_bot]; n = np.array(fr["n"]); n_ras = np.array([-n[1], n[0]])           # px (row, col) -> RAS (x, y): x = -col, y = +row
    best = None
    for k in range(crops.bones.shape[2]):
        m = crops.bones[:, :, k] == BONE_ID["metacarpals"]
        if m.sum() < 50:
            continue
        lab, nc = ndi.label(m)
        if nc < 4:
            continue
        sizes = ndi.sum(m, lab, range(1, nc + 1)); keep = [i + 1 for i, s in enumerate(sizes) if s >= 10]
        if len(keep) < 4:
            continue
        cents = [ndi.center_of_mass(lab == i) for i in keep]; P = np.array([[BONES_AFF[0] - c[0], BONES_AFF[1] - c[1]] for c in cents])
        off, ti = thumb_side(P, n_ras)
        if best is None or len(keep) > best["n_components"]:
            best = {"z": float(BONES_AFF[2] + k), "n_components": len(keep), "thumb_offset_mm_along_flexor_normal": round(off, 1), "thumb_xy": P[ti].round(1).tolist()}
    return best


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--crops", required=True); ap.add_argument("--ct", required=True)
    ap.add_argument("--bones", default=str(REPO / "data/ct_sources/task_outputs/vhm_arm_bones_cryo_completed.nii.gz"))
    ap.add_argument("--anchor", type=int, default=1700, help="instance where the CT radius and ulna sections seed the bone tracker")
    ap.add_argument("--lo", type=int, default=None); ap.add_argument("--hi", type=int, default=None)
    ap.add_argument("--scale", type=float, default=1.15, help="factor on her marker mm offsets (his larger forearm)")
    ap.add_argument("--out", default=str(REPO / "data/ct_sources/task_outputs/vhm_forearm_muscles_cryo.nii.gz"))
    ap.add_argument("--labels-out", default=str(REPO / "mappings/vhm_forearm_muscles_labels.json"))
    ap.add_argument("--mapping-out", default=str(REPO / "mappings/subjects/ct_vhm_forearm_volume_mapping.json"))
    ap.add_argument("--montage", default=None, help="PNG path (default: <out> with .png)"); ap.add_argument("--montage-levels", default="")
    ap.add_argument("--cache", default=None); ap.add_argument("--merge", default=str(REPO / "scripts/cryo/vhm_forearm_merge.json"))
    a = ap.parse_args(argv)
    crops, track, residual, corr, (j_top, j_bot), labels_by_level, ids, area, unassigned, frames, support, flips, area_side = run(a)
    merge_raw = json.load(open(a.merge)) if a.merge and Path(a.merge).exists() else {}
    merge = {k: (v["members"] if isinstance(v, dict) else v) for k, v in merge_raw.items() if not k.startswith("_")}
    merge_note = {k: v.get("note", "") for k, v in merge_raw.items() if isinstance(v, dict)}
    final_ids = dict(ids); final_names = {l: nm for nm, l in ids.items()}; remap = np.arange(max(ids.values()) + 1, dtype=np.uint8)
    for comp, members in merge.items():
        keep = ids[members[0]]
        for mm in members:
            remap[ids[mm]] = keep; final_ids.pop(mm, None)
        final_ids[comp] = keep; final_names[keep] = comp
        for mm in members[1:]:
            final_names.pop(ids[mm], None)
    raw_vols = {nm: round(area[nm] / 1000.0, 1) for nm in ids}
    for j in labels_by_level:
        labels_by_level[j] = remap[labels_by_level[j]]
    vol, aff = to_volume(crops, labels_by_level, corr); vox = float(abs(np.linalg.det(aff[:3, :3])))
    vols = {nm: round(float((vol == l).sum() * vox / 1000.0), 1) for nm, l in sorted(final_ids.items(), key=lambda kv: kv[1])}
    Path(a.out).parent.mkdir(parents=True, exist_ok=True); nib.save(nib.Nifti1Image(vol, aff), a.out)
    colors = palette(len(ids)); mpath = a.montage or str(a.out).replace(".nii.gz", ".png")
    levels = [int(t) for t in a.montage_levels.split(",")] if a.montage_levels else [int(round(j_top + (j_bot - j_top) * q)) for q in (0.05, 0.2, 0.4, 0.6, 0.8, 0.95)]
    mont = montage(crops, track, labels_by_level, final_ids, frames, levels, mpath, colors)
    after = {}
    for b, v in residual.items():
        d = [np.array(v[j]) - corr[j] * PX for j in v if j in corr]
        after[b] = {"mean_mm": np.mean(d, axis=0).round(1).tolist(), "sd_mm": np.std(d, axis=0).round(1).tolist()} if d else None
    res_summary = {b: {"n_levels": len(v), "mean_mm": np.mean(list(v.values()), axis=0).round(1).tolist(), "sd_mm": np.std(list(v.values()), axis=0).round(1).tolist(),
                       "at_levels": {str(crops.levels[k]): v[k] for k in sorted(v) if k % 30 == 10}} for b, v in residual.items()}
    supp = {f"{p[0]}|{p[1]}": {"levels": len(v), "median_ridge_ratio": round(float(np.median([x[2] for x in v])), 2),
                               "frac_levels_ratio_ge_1.8": round(float(np.mean([x[2] >= 1.8 for x in v])), 2),
                               "contact_mm": round(float(np.mean([x[1] for x in v])) * PX, 1)} for p, v in sorted(support.items()) if len(v) >= 5}
    groups = {nm: HER_RULES[nm][5] for nm in ids}; ship, weak = ship_or_merge(supp, groups)
    thumb = thumb_check(crops, frames, j_bot)
    orientation = {"frame_rule": "flexor side = away from the skin nearest the ulna (its subcutaneous posterior border); frame never flips between adjacent levels",
                   "frame_flips_forced": int(flips), "thumb_metacarpal": thumb,
                   "flexor_over_extensor_muscle_area": round(area_side["flexor"] / max(area_side["extensor"], 1.0), 2),
                   "verdict": ("consistent: thumb metacarpal on the flexor side" if thumb and thumb["thumb_offset_mm_along_flexor_normal"] > 0 else "CHECK: thumb metacarpal not on the flexor side")
                              + (", flexor mass larger" if area_side["flexor"] > area_side["extensor"] else ", flexor mass NOT larger")}
    report = {"_README": [f"Male right forearm muscles from his full-resolution cryosections ({Path(__file__).name}); {BADGE}. Bones tracked in the photographs; "
                          "markers by her textbook position rules (offsets x scale) in the radius-ulna frame; boundaries by a marker watershed on the pale fascial "
                          "septa; muscles the photographs do not separate merged into compartments.",
                          "ct_to_photo_shift_mm: photographed disc centre minus the CT section centre under the body-centroid registration, [photo rows, photo cols] mm; "
                          "after_bone_correction_mm: the same after the smoothed per-level bone correction that the volume uses (the muscles are laid on his CT bones).",
                          "raw_watershed_volumes_cm3: per rule marker before merging; ship_rule: within-compartment boundary on a pale line (ridge ratio >= 1.8) at >= 70 % of shared levels."],
              "source": SOURCE, "badge": BADGE, "scale": a.scale, "segment_instances": [crops.levels[j_top], crops.levels[j_bot]],
              "segment_ras_z": [crops.level(j_top)["z"], crops.level(j_bot)["z"]], "segment_atlas_y": [round(crops.level(j_top)["y"], 1), round(crops.level(j_bot)["y"], 1)],
              "ct_to_photo_shift_mm": res_summary, "after_bone_correction_mm": after, "orientation": orientation,
              "voxel_mm": [float(aff[0, 0]), float(aff[1, 1]), float(aff[2, 2])], "volumes_cm3": vols, "raw_watershed_volumes_cm3": raw_vols,
              "unassigned_muscle_cm3": round(unassigned / 1000.0, 1), "merged_compartments": merge, "montages": [mont] if mont else [],
              "labels": {str(l): nm for l, nm in sorted(final_names.items())}, "boundary_support": supp,
              "ship_rule": {"ship": sorted(ship), "weak_pairs": [{"pair": [x, y], "frac": z} for x, y, z in weak]},
              "volume_plausibility": {"_note": "expected ranges supplied by the reviewer for a 90 kg man, not verified against literature", **plausibility(vols)},
              "literature": {"citation": "Holzbaur KR, Murray WM, Gold GE, Delp SL. Upper limb muscle volumes in adult subjects. J Biomech 2007;40(4):742-749. "
                                         "doi:10.1016/j.jbiomech.2006.11.011 (PubMed 17241636, verified 2026-09-14)",
                             "note": "per-muscle volumes are in the paper's tables, not readable here: not verified; the abstract gives total upper-limb muscle "
                                     "volume 1427-4426 cm3 across 10 subjects (20th-percentile female to 97th-percentile male), wrist-crossing muscles 16 % of it."}}
    Path(str(a.out).replace(".nii.gz", "_report.json")).write_text(json.dumps(report, indent=1))
    key = {"_README": [f"Label id -> structure for the Visible Human MALE right forearm muscle volume ({Path(__file__).name}). A KEY, not data. {BADGE}: "
                       "see the script docstring for the rule; compartments are muscles the photographs do not separate (mapped to null)."],
           "source": SOURCE, "task": "vhm_forearm_muscles", "version": "2026-09-14", "badge": BADGE,
           "labels": {str(l): nm for l, nm in sorted(final_names.items())}, "merged_compartments": merge}
    Path(a.labels_out).write_text(json.dumps(key, indent=1))
    entries = []
    for l, nm in sorted(final_names.items()):
        if nm in merge:
            entries.append({"label": l, "source_structure": nm, "side": "right", "status": "no_atlas_entity", "atlas_id": None, "relationship": "no_usable_label",
                            "note": f"{BADGE}; compartment holding {', '.join(merge[nm])} ({vols.get(nm, 0)} cm3), not split: "
                                    f"{merge_note.get(nm, 'the photographs show no septum the watershed could follow between them at most levels')}",
                            "candidates": [m + "_r" for m in merge[nm]]})
        else:
            entries.append({"label": l, "source_structure": nm, "side": "right", "status": "curated", "atlas_id": nm + "_r", "relationship": "exact",
                            "note": f"{BADGE}: position-rule marker in the radius-ulna frame, boundary by the marker watershed on his fascial septa; {vols.get(nm, 0)} cm3."
                                    + (" REVIEW: volume outside 5-80 cm3, the region may hold a neighbour's belly." if not 5.0 <= vols.get(nm, 0) <= 80.0 else "")
                                    + (f" REVIEW: {vols.get(nm, 0)} cm3 is more than 2x off the expected {EXPECTED_CM3[nm][0]}-{EXPECTED_CM3[nm][1]} cm3."
                                       if plausibility(vols).get(nm, {}).get("verdict") == "off >2x" else ""),
                            "candidates": []})
    Path(a.mapping_out).write_text(json.dumps({"_README": ["Review every entry before running convert.", "Set 'atlas_id' to the correct entity, or null to skip the label.",
                                                            "'status' is advisory; convert reads 'atlas_id' only."],
                                                "subject": "ct_vhm_forearm", "source_volume": str(Path(a.out).resolve()), "label_map": "vhm_forearm_muscles",
                                                "entries": entries}, indent=2))
    print(json.dumps({"segment_instances": [crops.levels[j_top], crops.levels[j_bot]], "volumes_cm3": vols, "raw": raw_vols, "unassigned_cm3": round(unassigned / 1000, 1),
                      "residual": res_summary, "after": after, "orientation": orientation, "ship": report["ship_rule"], "montage": mont}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
