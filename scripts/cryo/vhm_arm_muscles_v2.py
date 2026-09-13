"""Visible Human MALE upper-arm compartments, v2: the humerus located in the photograph, self-contained.

    python3 scripts/cryo/vhm_arm_muscles_v2.py --stream SCRATCH/vh_cryo_m_arm --ct SCRATCH/vh_idc/nii/vhm_torso_0937.nii.gz \
        --out data/ct_sources/task_outputs/vhm_arm_muscles_cryo_v2.nii.gz

Q51 (2026-09-13): the male's v1 arm rule gave biceps 472/475 and triceps 675/762 cm3, far above textbook
(200-300 / 350-450 for a man), and the female's v2 showed why such rules go wrong: the CT humerus label
placed on the photographs with one shift constant sits beside the real bone lower down the arm. This
version needs no registered frame (his 1 mm frame did not survive the container reset): it reads the
arm levels streamed from IDC (every slice, 3x downsampled to ~1 mm), finds each arm as a separate
tissue island in the photograph, locates the humerus as the round non-muscle hole inside the arm's
muscle compartment, applies the same compartment rules as on her (posterior of the coronal plane
through the bone = triceps; anterior within 22 mm of the bone in the distal 65 % = brachialis; proximal
40 %, medial, within 15 mm = coracobrachialis; the rest = biceps; muscle within 45 mm of the bone),
and registers each arm island to his CT (torso block) by matching centroids -- translation only, the
photographs of this series lie with the spine at the top and the patient's left on the image right
(checked on four levels spanning the arm). Output: a label volume on his CT grid (torso RAS), the
volumes, and overlays. Rule-based: badge it, record the volumes. Nothing here is anatomy."""
import argparse, json, os, sys
import numpy as np, nibabel as nib
from scipy import ndimage as ndi
from PIL import Image
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cryo_classes import classify

ap = argparse.ArgumentParser()
ap.add_argument("--stream", required=True); ap.add_argument("--ct", required=True)
ap.add_argument("--out", default="data/ct_sources/task_outputs/vhm_arm_muscles_cryo_v2.nii.gz")
ap.add_argument("--origin-y", type=float, default=-895.476, help="atlas origin's RAS z in the torso frame")
ap.add_argument("--hum-y", default="590,250,603,262", help="humerus head top / lower end (atlas y) right, left")
ap.add_argument("--px", type=float, default=0.99, help="photograph pixel after the 3x downsample, mm")
ap.add_argument("--overlay", default=None)
ap.add_argument("--bundle", default="data/derived/viewer_bundles/vhm_v25")
ap.add_argument("--deltoid", default="data/ct_sources/task_outputs/vhm_deltoid_cryo.nii.gz"); ap.add_argument("--cuff", default="data/ct_sources/task_outputs/vhm_rotator_cuff_cryo.nii.gz")
ap.add_argument("--total", default="data/ct_sources/task_outputs/vhm_total.nii.gz"); ap.add_argument("--abd", default="data/ct_sources/task_outputs/vhm_abdominal_muscles.nii.gz")
a = ap.parse_args()
vol = np.load(f"{a.stream}/cryo_1mm.npy", mmap_mode="r"); idx = json.load(open(f"{a.stream}/cryo_index.json"))
inst = np.array([r[1] for r in idx]); i_of = inst - 1001                       # cryo index (vertex = 0); y = 879.476 - i
ct = nib.load(a.ct); A = ct.affine; ctd = np.asanyarray(ct.dataobj); zs = A[2, 3] + np.arange(ctd.shape[2]) * A[2, 2]
htop_r, hbot_r, htop_l, hbot_l = [float(t) for t in a.hum_y.split(",")]
OUT = {"biceps_right": 1, "brachialis_right": 2, "coracobrachialis_right": 3, "triceps_right": 4,
       "biceps_left": 5, "brachialis_left": 6, "coracobrachialis_left": 7, "triceps_left": 8}
out = np.zeros(ctd.shape, np.uint8); found = {"right": 0, "left": 0}; slices = {"right": 0, "left": 0}; renders = []


tot = nib.load(a.total); totd = np.asanyarray(tot.dataobj)                    # his TotalSegmentator total labels, same CT grid
abd = nib.load(a.abd); abdd = np.asanyarray(abd.dataobj)
key = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "mappings", "totalsegmentator_labels.json")))["labels"]
inv = {v: int(k) for k, v in key.items()}
HUM = {"right": inv["humerus_right"], "left": inv["humerus_left"]}
assert totd.shape == ctd.shape, (totd.shape, ctd.shape)
# his complete humeri (CT + photograph watershed, ct_vhm_arm) from the recovered bundle: the seed for the bone search at every
# level -- the frozen-CT TotalSegmentator humerus label stops ~100 mm below the head
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
from scripts.transfer.bundle_io import read_bundle_dir, meshes_by_id
_b, _blob = read_bundle_dir(a.bundle); _M = meshes_by_id(_b, _blob)
HUMV = {"right": _M["humerus_r"]["v"], "left": _M["humerus_l"]["v"]}
OX, OZ = -6.035, 4.787                                                        # atlas origin (torso frame) x and RAS-y components


def humerus_seed(side, yatlas):
    v = HUMV[side]; sel = np.abs(v[:, 1] - yatlas) < 3.0
    if sel.sum() < 6:
        return None
    return float(v[sel, 0].mean() + OX), float(v[sel, 2].mean() + OZ)        # RAS x, RAS y


def to_photo(x, y, T):
    """RAS (x, y) -> photo (row, col) under the slice's translation T = (rowB, colB, xB, yB)."""
    rowB, colB, xB, yB = T
    return rowB + (y - yB) / a.px, colB - (x - xB) / a.px


def ct_mask_in_photo(mask, T, shape):
    ii, jj = np.where(mask)
    if len(ii) == 0:
        return np.zeros(shape, bool)
    x = A[0, 3] + A[0, 0] * ii; y = A[1, 3] + A[1, 1] * jj
    r, c_ = to_photo(x, y, T); r = np.rint(r).astype(int); c_ = np.rint(c_).astype(int)
    ok = (r >= 0) & (r < shape[0]) & (c_ >= 0) & (c_ < shape[1]); out_ = np.zeros(shape, bool); out_[r[ok], c_[ok]] = True
    return ndi.binary_closing(out_, iterations=1)


def photo_humerus(c, est_rc, tissue):
    """The humerus as photographed: the round non-muscle hole of the closed muscle class nearest the estimate."""
    comp = ndi.binary_fill_holes(ndi.binary_closing((c == 3) & tissue, iterations=2))
    holes = comp & ~(c == 3) & ~ndi.binary_dilation(c == 3, iterations=1); hl, hn = ndi.label(holes)
    best = None
    for i in range(1, hn + 1):
        m = hl == i; n = int(m.sum())
        if n < 120 or n > 1100:
            continue
        sol = n / max(int(ndi.binary_closing(m, iterations=3).sum()), 1)
        if sol < 0.6:
            continue
        cy, cx = ndi.center_of_mass(m); d = np.hypot(cy - est_rc[0], cx - est_rc[1])
        if d <= 45 and (best is None or d < best[0]):
            best = (d, m)
    return None if best is None else best[1]


# his rule-based deltoid and rotator cuff (1 mm frame grid, torso RAS: x = 350 - i, y = 240 - j, same z as the CT) resampled
# onto the CT grid per slice, so the arm rule never re-labels them
_delt = np.asanyarray(nib.load(a.deltoid).dataobj); _cuff = np.asanyarray(nib.load(a.cuff).dataobj)
_ci, _cj = np.mgrid[0:ctd.shape[0], 0:ctd.shape[1]]
_fi = np.clip(np.rint(110 + 0.9375 * _ci).astype(int), 0, 699); _fj = np.clip(np.rint(0.9375 * _cj).astype(int), 0, 479)


def frame_labels_on_ct(kc):
    if not (0 <= kc < _delt.shape[2]):
        return np.zeros(ctd.shape[:2], bool)
    return (_delt[_fi, _fj, kc] > 0) | (_cuff[_fi, _fj, kc] > 0)


resid = []
for j in range(len(idx)):
    i = int(i_of[j]); yatlas = 879.476 - i; z = yatlas + a.origin_y; kc = int(round((z - A[2, 3]) / A[2, 2]))
    if not (0 <= kc < ctd.shape[2]):
        continue
    im = np.asarray(vol[j]); c = classify(im)
    tissue = ndi.binary_fill_holes(ndi.binary_closing(c > 0, iterations=2)); tissue[:40] = False
    lab, n = ndi.label(tissue)
    if n == 0:
        continue
    sizes = np.bincount(lab.ravel())[1:]; body_p = np.isin(lab, np.where(sizes >= 0.02 * sizes.max())[0] + 1)
    sl = ctd[:, :, kc]; body_c = ndi.binary_fill_holes(sl > -500); lc, nc = ndi.label(body_c)
    if nc == 0:
        continue
    sc = np.bincount(lc.ravel())[1:]; body_c = np.isin(lc, np.where(sc >= 0.02 * sc.max())[0] + 1)
    rowB, colB = ndi.center_of_mass(body_p); ic, jc = ndi.center_of_mass(body_c)
    T = (rowB, colB, A[0, 3] + A[0, 0] * ic, A[1, 3] + A[1, 1] * jc)
    trunk_lbl = ((totd[:, :, kc] > 0) & ~np.isin(totd[:, :, kc], list(HUM.values()))) | (abdd[:, :, kc] > 0) | frame_labels_on_ct(kc)
    trunk_p = ndi.binary_dilation(ct_mask_in_photo(trunk_lbl, T, c.shape), iterations=3)
    lab_slice = np.zeros(c.shape, np.uint8)
    for side in ("right", "left"):
        htop, hbot = (htop_r, hbot_r) if side == "right" else (htop_l, hbot_l)
        if not (hbot + 10 <= yatlas <= htop - 70):
            continue
        seed = humerus_seed(side, yatlas)
        if seed is None:
            continue
        est = to_photo(seed[0], seed[1], T)
        h = photo_humerus(c, est, tissue); slices[side] += 1
        if h is None:
            yy0, xx0 = np.mgrid[0:c.shape[0], 0:c.shape[1]]
            h = ((yy0 - est[0]) ** 2 + (xx0 - est[1]) ** 2) < (12 / a.px) ** 2      # a 12 mm disc at the seed
        else:
            found[side] += 1
            cy0, cx0 = ndi.center_of_mass(h); resid.append(float(np.hypot(cy0 - est[0], cx0 - est[1]) * a.px))
        base = 0 if side == "right" else 4
        ys, xs = np.where(h); cy, cx = ys.mean(), xs.mean(); yy, xx = np.mgrid[0:c.shape[0], 0:c.shape[1]]
        # the arm: its own tissue island when separate, else the 70 mm disc about the bone; never his CT-labelled trunk
        lt, nt = ndi.label(ndi.binary_opening(tissue, iterations=6)); isl = lt[int(round(cy)), int(round(cx))]
        arm = (lt == isl) if (isl > 0 and (lt == isl).sum() < 30000) else tissue.copy()
        arm = ndi.binary_dilation(arm, iterations=6) & tissue & (((yy - cy) ** 2 + (xx - cx) ** 2) < (70 / a.px) ** 2) & ~trunk_p
        mall = arm & (c == 3) & ~h; op = ndi.binary_opening(mall, iterations=1); el, en = ndi.label(op)
        if en == 0:
            continue
        dh = ndi.distance_transform_edt(~h) * a.px; mind = ndi.minimum(dh, el, np.arange(1, en + 1))
        keep = np.arange(1, en + 1)[np.asarray(mind) <= 45]
        if len(keep) == 0:
            continue
        musc = ndi.binary_dilation(np.isin(el, keep), iterations=1) & mall
        ant = yy > cy                                    # anterior is DOWN the image (spine at the top)
        frac = (htop - 70 - yatlas) / max((htop - 70) - (hbot + 10), 1)
        medial = (xx < cx) if side == "left" else (xx > cx)   # toward the trunk (image centre)
        # distal 40 %: muscle lateral of the bone beyond 25 mm is the forearm's origin (brachioradialis / extensors), not arm
        lateral = (xx > cx) if side == "left" else (xx < cx)
        musc &= ~((frac > 0.6) & lateral & (np.abs(xx - cx) * a.px > 25))
        o = np.zeros_like(lab_slice); p_ = musc & ~ant; o[p_] = base + 4
        # frac runs 0 at the top of the segment to 1 at the elbow: brachialis in the distal 65 %, coracobrachialis in the proximal 40 %
        an = musc & ant; brach = an & (dh <= 22) & (frac > 0.35); o[brach] = base + 2
        cor = an & (frac <= 0.4) & (dh <= 15) & medial; o[cor] = base + 3
        o[an & ~brach & ~cor] = base + 1
        rr, cc_ = np.where(o > 0)
        x = T[2] - (cc_ - T[1]) * a.px; y = T[3] + (rr - T[0]) * a.px
        ii2 = np.rint((x - A[0, 3]) / A[0, 0]).astype(int); jj2 = np.rint((y - A[1, 3]) / A[1, 1]).astype(int)
        ok = (ii2 >= 0) & (ii2 < ctd.shape[0]) & (jj2 >= 0) & (jj2 < ctd.shape[1])
        out[ii2[ok], jj2[ok], kc] = o[rr[ok], cc_[ok]]
        lab_slice[o > 0] = o[o > 0]
    if a.overlay and j % 36 == 0 and lab_slice.any():
        lut = np.array([[0, 0, 0], [0, 255, 255], [255, 0, 255], [255, 255, 0], [0, 255, 0]], np.uint8)
        pic = im.copy(); m = lab_slice > 0; col = lut[(lab_slice - 1) % 4 + 1]
        pic[m] = (0.5 * col[m] + 0.5 * pic[m]).astype(np.uint8)
        renders.append(pic[40:380])
print("photo-humerus vs CT-label residual mm: median", round(float(np.median(resid)), 1) if resid else None, "n", len(resid), flush=True)
vox = float(abs(np.linalg.det(A[:3, :3])))
rep = {name: round(float((out == v).sum()) * vox / 1000, 1) for name, v in OUT.items()}
rep["humerus_found_in_photo_slices"] = found
print("volumes cm3", rep, flush=True)
nib.save(nib.Nifti1Image(out, A), a.out)
json.dump({"_README": ["Male upper-arm muscles by the compartment rules on his cryosection photographs, v2 (scripts/cryo/vhm_arm_muscles_v2.py): "
                       "humerus located in the photograph, each arm island registered to his CT by centroid; rule-based, derived data."],
           "source": "U.S. National Library of Medicine, The Visible Human Project (public domain), male cryosections and CT via the NCI Imaging Data Commons.",
           "volumes_cm3": rep}, open(a.out.replace(".nii.gz", "_report.json"), "w"), indent=1)
if a.overlay and renders:
    Image.fromarray(np.concatenate(renders, axis=0)).save(a.overlay); print("overlay", a.overlay)
