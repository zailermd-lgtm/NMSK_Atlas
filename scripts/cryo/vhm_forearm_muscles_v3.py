"""Male RIGHT forearm muscles from his own full-resolution (0.33 mm) cryosection photographs, v3 (Q165). Rule-based;
every structure badged. Writes subject ct_vhm_forearm_v3 (passing muscles only).

    python3 scripts/cryo/vhm_forearm_muscles_v3.py --cryo SCRATCH/vh_cryo_m_forearm_q151 SCRATCH/q164_m_forearm/ext \
        --q164-work SCRATCH/q164_m_forearm/work --work SCRATCH/q165_m_forearm
    python3 scripts/cryo/vhm_forearm_muscles_v3.py --stamp build/vh/ct_vhm_forearm_v3      # after the converter

Q164 (vhm_forearm_muscles_fullres.py, imported here, not edited) was not shipped for two reasons, fixed here:
 1. TISSUE CLASS FIRST. Every resliced voxel gets a tissue class from its photographed colour with the repo's male
    colour rule (cryo_classes.classify, the rule every male cryo script uses; the female pipeline's retune
    cryo_classes_f exists because HER frozen muscle was darker and 20 % of her in-body pixels stayed unclassified --
    both rules are measured on his forearm and the choice is reported): muscle / fat / pale (tendon, fascia, nerve)
    / bone (his CT radius/ulna resliced, dilated 1 mm, or white cortex) / other (unclassified: vessels, skin, clot).
    ONLY muscle-class voxels may carry a muscle label (Q164 closed the muscle mask 1 mm and filled holes up to 8 mm2,
    so septa and small fat/vessel islands were counted). Photograph colours are resliced NEAREST, so every voxel's
    class is the class of one real photograph pixel.
 2. SEPTUM-FOLLOWING BOUNDARIES. The 3-D marker watershed runs on an elevation that is HIGH on the pale septa and
    next to non-muscle ((1-w) x (1 - min(distance to non-muscle, 3 mm) / 3 mm) + w x pale-ridge strength, the ridge
    = paleness g/r minus its 5.5 mm local median, / 0.15, clipped 0..1: a thin pale septum crossing a red belly),
    inside the muscle-class
    mask only, compactness 0. Seeds = Q164's own markers (her MARKER_RULES x1.15 + the superficial RING), taken every
    --seed-stride mm along the axis (not every slice, so the 3-D flood follows a belly between rule points) and each
    moved to the lowest elevation within 2.5 mm (the belly, off a septum).
 3. NON-CIRCULAR EXPECTATIONS. expected_i = repo architecture volume_i (PCSA x fascicle length / cos pennation,
    data/muscles/upper_limb/<id>_r.json) x ONE factor measured on HIS OWN separately segmented upper-arm muscles:
    factor = (his biceps_brachii_r + brachialis_r + triceps_brachii_r mesh volumes, build/vh, the same subject
    priority as scripts/vhm_rebuild_bundle.sh) / (the same three muscles' architecture volumes). No per-muscle
    published volume table is stored offline in the repo (Holzbaur et al. 2007 is cited by abstract only).
 4. SHIP GATE per muscle: 0.5x-2.0x the scaled expectation; main 26-connected component >= 0.98 (islands < 1 %
    dropped first, repo rule); median over slices of the fraction of its boundary on non-muscle / pale-septum
    pixels >= 0.5. Muscles that arise above his radial-head plane (PT, BR, ECRL, anconeus) are OUT OF RANGE: only
    their part below that plane is segmented, so they are reported, not shipped.

Outputs: label volume data/ct_sources/task_outputs/vhm_forearm_muscles_v3.nii.gz (torso RAS, positive-determinant
affine), label key mappings/vhm_forearm_muscles_v3_labels.json, mapping
mappings/subjects/ct_vhm_forearm_v3_volume_mapping.json, report data/derived/Q165_vhm_forearm_v3.json, montage PNG
in --work.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import pickle
import sys
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "4"); os.environ.setdefault("OPENBLAS_NUM_THREADS", "4")
import numpy as np  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO)); sys.path.insert(0, str(Path(__file__).resolve().parent))
import vhm_forearm_muscles_fullres as Q  # noqa: E402  (Q164: registration, reslicing, rules, gate helpers)

BADGE = "rule-based"
SUBJECT = "ct_vhm_forearm_v3"
LABEL_MAP = "vhm_forearm_muscles_v3"
SOURCE = ("U.S. National Library of Medicine, The Visible Human Project (public domain): male cryosection photographs at "
          "full resolution (0.33 mm, IDC series 4aaf9181-fb6a-4a4c-bf49-d1eb9ed4a385, instances 1575-1819) and his CT "
          "radius/ulna labels (data/ct_sources/task_outputs/vhm_arm_bones_cryo_completed.nii.gz) for registration. "
          "Derived data (scripts/cryo/vhm_forearm_muscles_v3.py): rule-based segmentation (colour tissue classes, "
          "position-rule markers, 3-D marker watershed on the pale fascial septa inside the muscle class), not traced "
          "by an anatomist. Expectations: repository architecture volumes (Holzbaur, Murray & Delp 2005 Ann Biomed Eng "
          "33:829) scaled by his own upper-arm muscle volumes.")
TISSUE = {"outside": 0, "muscle": 1, "fat": 2, "pale": 3, "bone": 4, "other": 5}
OUT_OF_RANGE = ("pronator_teres", "brachioradialis", "extensor_carpi_radialis_longus", "anconeus")
ARM_MUSCLES = ("biceps_brachii", "brachialis", "triceps_brachii")
# his upper-arm meshes: first subject holding the id wins (the order of scripts/vhm_rebuild_bundle.sh)
ARM_SUBJECTS = ("ct_vhm_armm_contfix_mesh", "ct_vhm_armm_contfix", "ct_vhm_armm")


# ----------------------------------------------------------------------------------------------- pure functions
def tissue_map(cls, island, bone):
    """Colour classes (cryo_classes codes: 1 tissue, 2 fat, 3 muscle, 4 pale, 5 white) -> TISSUE codes, inside the
    island only; `bone` (his CT bone, dilated) or white cortex -> bone."""
    cls = np.asarray(cls); isl = np.asarray(island, bool); b = np.asarray(bone, bool)
    t = np.zeros(cls.shape, np.uint8)
    t[isl] = TISSUE["other"]
    t[isl & (cls == 2)] = TISSUE["fat"]; t[isl & (cls == 4)] = TISSUE["pale"]; t[isl & (cls == 3)] = TISSUE["muscle"]
    t[isl & ((cls == 5) | b)] = TISSUE["bone"]
    return t


def muscle_fraction_nonbone(t):
    """Muscle-class share of the non-bone cross-section (island minus bone)."""
    t = np.asarray(t); nb = (t > 0) & (t != TISSUE["bone"])
    return float((t == TISSUE["muscle"]).sum() / max(int(nb.sum()), 1))


def separability(v_muscle, v_fat):
    """Muscle vs fat brightness (colour max) separation: (Fisher ratio (m1-m2)^2/(s1^2+s2^2), overlap = share of
    all muscle+fat values lying between the muscle 97.5th and the fat 2.5th percentile when those cross, else 0)."""
    a = np.asarray(v_muscle, float); b = np.asarray(v_fat, float)
    fisher = float((a.mean() - b.mean()) ** 2 / max(a.var() + b.var(), 1e-9))
    hi, lo = np.percentile(a, 97.5), np.percentile(b, 2.5)
    both = np.concatenate([a, b])
    ov = float(((both >= lo) & (both <= hi)).mean()) if hi > lo else 0.0
    return fisher, ov


def paleness_residual(rgb, inside, sigma_px=0.5, bg_px=11):
    """One slice: paleness g/r (muscle ~0.5, fat/fascia ~0.9) smoothed sigma_px, minus its local median over bg_px
    (the belly's own colour), 0.5 outside `inside`. A thin pale septum inside a red belly is a positive ridge; the
    brightness top-hat Q164 used also fires on fibre texture (1.8 x its muscle median lies within 1 px of 68 % of
    belly-interior pixels on him)."""
    from scipy import ndimage as ndi
    im = np.asarray(rgb, np.float32); P = im[..., 1] / np.maximum(im[..., 0], 1.0)
    P = np.where(np.asarray(inside, bool), P, 0.5)
    P = ndi.gaussian_filter(P, sigma_px) if sigma_px else P
    return (P - ndi.median_filter(P, size=bg_px)).astype(np.float32)


def elevation(muscle, ridge, ds=0.5, dmax_mm=3.0, w_ridge=0.5):
    """Watershed elevation per slice: (1 - w) x (1 - min(in-plane distance to non-muscle, dmax) / dmax) + w x ridge
    (0..1). High on septa and next to non-muscle, low in the middle of a belly."""
    from scipy import ndimage as ndi
    m = np.asarray(muscle, bool); r = np.asarray(ridge, np.float32)
    m3 = m[None] if m.ndim == 2 else m; r3 = r[None] if r.ndim == 2 else r
    E = np.ones(m3.shape, np.float32)
    for i in range(m3.shape[0]):
        if m3[i].any():
            d = ndi.distance_transform_edt(m3[i]) * ds
            E[i] = (1 - w_ridge) * (1 - np.minimum(d, dmax_mm) / dmax_mm) + w_ridge * r3[i]
    return E[0] if m.ndim == 2 else E


def boundary_septum_fractions(L, onsep, min_px=10):
    """One slice. L: labels (0 = unlabelled); onsep: bool, pixels within 1 px of non-muscle or a pale septum.
    Returns {label: (fraction of its boundary pixels (4-neighbour) on onsep, fraction of its CONTACT pixels
    (touching another label) on onsep or None, n boundary px)} for labels with >= min_px boundary pixels."""
    from scipy import ndimage as ndi
    L = np.asarray(L).astype(np.int32); cross = ndi.generate_binary_structure(2, 1)
    mx = ndi.maximum_filter(L, footprint=cross, mode="constant", cval=0)
    mn = ndi.minimum_filter(L, footprint=cross, mode="constant", cval=0)
    bnd = (L > 0) & ((mx != L) | (mn != L))
    Lp = np.where(L > 0, L, 1 << 20)
    mn2 = ndi.minimum_filter(Lp, footprint=cross, mode="constant", cval=1 << 20)
    contact = (L > 0) & ((mx != L) | ((mn2 != L) & (mn2 < (1 << 20))))
    n = int(L.max()) + 1
    nb = np.bincount(L[bnd], minlength=n); ns = np.bincount(L[bnd & onsep], minlength=n)
    nc = np.bincount(L[contact], minlength=n); ncs = np.bincount(L[contact & onsep], minlength=n)
    return {l: (float(ns[l] / nb[l]), (float(ncs[l] / nc[l]) if nc[l] >= min_px else None), int(nb[l]))
            for l in range(1, n) if nb[l] >= min_px}


def scale_factor(his, arch):
    """ONE size factor: sum of his measured volumes / sum of the architecture volumes of the same muscles."""
    keys = sorted(his)
    if set(keys) != set(arch):
        raise ValueError("his and architecture volumes must name the same muscles")
    return float(sum(his[k] for k in keys) / sum(arch[k] for k in keys))


def gate_v3(v, expected, main_frac, sep_median, lo=0.5, hi=2.0, min_main=0.98, min_sep=0.5, out_of_range=False):
    """(ship, reason). Repo gate (volume ratio, main component) + boundary-on-septum/non-muscle median >= min_sep."""
    if out_of_range:
        return False, "OUT OF RANGE: arises above his radial-head plane; only the part below it is segmented"
    ok, why = Q.gate(v, expected, main_frac, lo, hi, min_main)
    if not ok:
        return False, why
    if sep_median < min_sep:
        return False, f"boundary on septum/non-muscle {sep_median:.2f} (median over slices) < {min_sep}"
    return True, f"{why}, boundary on septum/non-muscle {sep_median:.2f}"


def move_to_basin(pt, E, allowed, r_px):
    """The allowed pixel of lowest elevation within r_px of pt (row, col), or None."""
    r, c = int(round(pt[0])), int(round(pt[1])); H, W = E.shape
    r0, r1, c0, c1 = max(r - r_px, 0), min(r + r_px + 1, H), max(c - r_px, 0), min(c + r_px + 1, W)
    if r0 >= r1 or c0 >= c1:
        return None
    yy, xx = np.mgrid[r0:r1, c0:c1]; win = allowed[r0:r1, c0:c1] & ((yy - r) ** 2 + (xx - c) ** 2 <= r_px * r_px)
    if not win.any():
        return None
    e = np.where(win, E[r0:r1, c0:c1], np.inf); k = np.unravel_index(int(np.argmin(e)), e.shape)
    return int(yy[k]), int(xx[k])


def mesh_volume_cm3(V, F):
    """Enclosed volume (cm3) of a closed triangle mesh (mm) by the divergence theorem."""
    V = np.asarray(V, float); F = np.asarray(F, np.int64)
    a, b, c = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    return float(abs(np.einsum("ij,ij->i", a, np.cross(b, c)).sum()) / 6.0 / 1000.0)


# ----------------------------------------------------------------------------------------------- stages
def build_rgb_stack(ph, isl_by_level, T):
    """The photographs laid into Q164's torso-RAS stack (same grid as Q.build_stack): RGB uint8, 0 outside the
    island. Returns (rgb (nz, nr, nc, 3), grid)."""
    r0, _, c0, _ = Q.BOX; js = sorted(isl_by_level); ext = []
    for j in js:
        rr, cc = np.where(isl_by_level[j]); x, y = Q.photo_to_ras([rr.min() + r0, rr.max() + r0], [cc.min() + c0, cc.max() + c0], *T[j])
        ext.append((x.min(), x.max(), y.min(), y.max()))
    ext = np.array(ext); Xg0 = ext[:, 1].max() + 1.0; Yg0 = ext[:, 2].min() - 1.0
    nr = int(np.ceil((ext[:, 3].max() + 1.0 - Yg0) / Q.PX)) + 1; nc = int(np.ceil((Xg0 - ext[:, 0].min() + 1.0) / Q.PX)) + 1
    rgb = np.zeros((len(js), nr, nc, 3), np.uint8)
    for k, j in enumerate(js):
        im = ph.crop(j); isl = isl_by_level[j]
        dr = int(round((T[j][1] - Yg0) / Q.PX)) + r0; dc = int(round((Xg0 - T[j][0]) / Q.PX)) + c0
        rr, cc = np.where(isl); gr = rr + dr; gc = cc + dc; ok = (gr >= 0) & (gr < nr) & (gc >= 0) & (gc < nc)
        rgb[k, gr[ok], gc[ok]] = im[rr[ok], cc[ok]]
    return rgb, (float(Xg0), float(Yg0), Q.inst_to_z(ph.levels[js[0]]))


def reslice_rgb(rgb, grid, c, a, us, ss, ts):
    """Nearest-neighbour RGB on Q164's forearm-frame planes (every voxel = one real photograph pixel)."""
    from scipy.ndimage import map_coordinates
    v1, v2 = Q.frame_basis(a); S, Tt = np.meshgrid(ss, ts, indexing="ij"); out = np.zeros((len(us), len(ss), len(ts), 3), np.uint8)
    chans = [np.ascontiguousarray(rgb[..., ch]) for ch in range(3)]
    for i, u in enumerate(us):
        P = c[None, None, :] + u * a + S[..., None] * v1 + Tt[..., None] * v2
        k, r, cc = Q.stack_index(P[..., 0], P[..., 1], P[..., 2], grid)
        for ch in range(3):
            out[i, ..., ch] = map_coordinates(chans[ch], [k, r, cc], order=0, mode="constant", cval=0)
    return out


def classify_frame(rgb, classify):
    return np.stack([classify(rgb[i]) for i in range(rgb.shape[0])])


def his_arm_volumes(build=REPO / "build/vh"):
    """{muscle: (cm3, subject)} of his right biceps/brachialis/triceps meshes, first subject in ARM_SUBJECTS wins."""
    out = {}
    for s in ARM_SUBJECTS:
        d = Path(build) / s
        if not (d / "manifest.json").exists():
            continue
        ms = Q.load_subject_meshes(d, [m + "_r" for m in ARM_MUSCLES if m not in out])
        for aid, (v, f) in ms.items():
            out[aid[:-2]] = (round(mesh_volume_cm3(v, f), 1), s)
    missing = [m for m in ARM_MUSCLES if m not in out]
    if missing:
        raise SystemExit(f"his upper-arm meshes missing for {missing} in {ARM_SUBJECTS}")
    return out


def seeds_from_q164(info, E, muscle, ids, stride, r_move_px, r_seed_px):
    """Q164's per-slice rule seeds (info['frames'][i]['seeds']) on every stride-th slice of the segment, each moved to
    the lowest elevation within r_move_px inside the muscle class, grown to a disk of r_seed_px inside it."""
    from scipy import ndimage as ndi
    markers = np.zeros(muscle.shape, np.int32); n = 0
    fr = info["frames"]; keep = [i for i in sorted(fr) if (i - info["i_top"]) % stride == 0]
    yy, xx = np.mgrid[0:muscle.shape[1], 0:muscle.shape[2]]
    for i in keep:
        for nm, p in fr[i]["seeds"].items():
            q = move_to_basin(p, E[i], muscle[i] & (markers[i] == 0), r_move_px)
            if q is None:
                continue
            disk = ((yy - q[0]) ** 2 + (xx - q[1]) ** 2 <= r_seed_px * r_seed_px) & muscle[i] & (markers[i] == 0)
            lab, _ = ndi.label(disk); disk = lab == lab[q]
            markers[i][disk] = ids[nm]; n += 1
    return markers, keep, n


def montage(rgb, lab, B, info, us, path, slices, ncol, up=2):
    """Row 1: the resliced photograph; row 2: labels (alpha 0.55) over it, non-muscle left unlabelled, label edges
    black, CT radius/ulna outlines white."""
    from PIL import Image, ImageDraw
    from scipy import ndimage as ndi
    from vhf_forearm_muscles_from_cryo import palette
    p = palette(ncol); col = np.array([p[k] for k in range(ncol + 1)], np.uint8); tops, bots = [], []
    for i in slices:
        im = rgb[i].copy(); L = lab[i]; ov = im.copy(); m = L > 0
        ov[m] = (0.55 * col[L[m]] + 0.45 * im[m]).astype(np.uint8)
        edge = m & (ndi.maximum_filter(L, 3) != ndi.minimum_filter(np.where(m, L, 255), 3)); ov[edge] = 0
        for b in (2, 3):
            bm = B[i] == b; ov[bm & ~ndi.binary_erosion(bm)] = 255
        a_ = np.kron(im, np.ones((up, up, 1), np.uint8)); b_ = np.kron(ov, np.ones((up, up, 1), np.uint8))
        pa = Image.fromarray(a_); ImageDraw.Draw(pa).text((4, 4), f"u {us[i]:.0f} mm  f {(i - info['i_top']) / max(info['i_bot'] - info['i_top'], 1):.2f}", fill=(255, 255, 0))
        tops.append(np.asarray(pa)); bots.append(b_)
    Image.fromarray(np.concatenate([np.concatenate(tops, 1), np.concatenate(bots, 1)], 0)).save(path)
    return str(path)


def badge_text(v, exp, factor, sep, sep_contact):
    ct = "" if sep_contact is None else f" (where it touches another muscle: {round(100 * sep_contact)} %)"
    return (f"Rule-based segmentation from his own cryosection photographs (Visible Human male, 0.33 mm, instances "
            f"1575-1819), not traced anatomy: only voxels whose photographed colour is muscle are labelled (fat, "
            f"tendon/fascia, vessels and skin excluded); position-rule seeds and a 3-D watershed on the pale septa "
            f"place the boundaries; median {round(100 * sep)} % of its outline per section lies on a septum or "
            f"non-muscle{ct}. Measured volume {v:.1f} cm3 vs expectation {exp:.1f} cm3 (repository architecture "
            f"volume x {factor:.2f}, the ratio of his own upper-arm muscle volumes to theirs). Only the part between "
            f"his radial-head and distal-radius planes is segmented.")


# ----------------------------------------------------------------------------------------------- main
def main(argv=None):
    import nibabel as nib
    from scipy import ndimage as ndi
    from skimage.segmentation import watershed
    from cryo_classes import classify as classify_m
    from cryo_classes_f import classify as classify_f
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cryo", nargs="+", help="photograph caches (as Q164)")
    ap.add_argument("--q164-work", help="Q164 work dir holding isl.pkl, track.pkl, frame.npz")
    ap.add_argument("--work", help="scratch folder for the v3 cache and the montage")
    ap.add_argument("--bones", default=str(REPO / "data/ct_sources/task_outputs/vhm_arm_bones_cryo_completed.nii.gz"))
    ap.add_argument("--scale", type=float, default=1.15)
    ap.add_argument("--seed-stride", type=int, default=16, help="slices (mm) between seeded slices")
    ap.add_argument("--w-ridge", type=float, default=0.8)
    ap.add_argument("--septum-pale", type=float, default=0.10, help="paleness residual counted as a pale septum")
    ap.add_argument("--ridge-full", type=float, default=0.15, help="paleness residual at which the ridge term is 1")
    ap.add_argument("--ridge-sigma-u", type=float, default=0.0, help="Gaussian sigma (slices) of the ridge along the axis")
    ap.add_argument("--min-speck-mm2", type=float, default=4.0, help="in-plane muscle-class specks smaller than this are not labelled")
    ap.add_argument("--out", default=str(REPO / "data/ct_sources/task_outputs/vhm_forearm_muscles_v3.nii.gz"))
    ap.add_argument("--labels-out", default=str(REPO / f"mappings/{LABEL_MAP}_labels.json"))
    ap.add_argument("--mapping-out", default=str(REPO / f"mappings/subjects/{SUBJECT}_volume_mapping.json"))
    ap.add_argument("--report", default=str(REPO / "data/derived/Q165_vhm_forearm_v3.json"))
    ap.add_argument("--stamp", default=None, help="only stamp badges from --mapping-out onto this converted subject dir")
    a = ap.parse_args(argv)
    if a.stamp:
        print(f"stamped {Q.stamp_badges(a.stamp, a.mapping_out)} badges"); return 0
    if not (a.cryo and a.work and a.q164_work):
        ap.error("--cryo, --q164-work and --work are required unless --stamp")
    W = Path(a.work); W.mkdir(parents=True, exist_ok=True); Q4 = Path(a.q164_work)
    F = dict(np.load(Q4 / "frame.npz")); us, ss, ts, c, ax = F["us"], F["ss"], F["ts"], F["c"], F["a"]; ds = float(ss[1] - ss[0])
    p = W / "rgb_frame.npy"
    if p.exists():
        rgb = np.load(p)
    else:
        ph = Q.Photos(*a.cryo); isl = pickle.load(open(Q4 / "isl.pkl", "rb")); tr = pickle.load(open(Q4 / "track.pkl", "rb"))
        T, _rel = Q.smooth_translation(tr, ph.n); del tr
        st, grid = build_rgb_stack(ph, isl, T); del isl
        rgb = reslice_rgb(st, grid, c, ax, us, ss, ts); del st
        np.save(p, rgb)
    cls = classify_frame(rgb, classify_m); isl3 = F["island"]; B = F["B"]
    agree = float(((cls == 3) == F["muscle"])[isl3].mean())
    print(f"frame {rgb.shape}, class-3 agreement with Q164's resliced muscle mask {agree:.4f}")
    bone = np.stack([ndi.binary_dilation(B[i] > 0, iterations=2) for i in range(len(us))])
    tis = tissue_map(cls, isl3, bone)
    # ---- the segment (radial head .. distal radius), Q164's rule seeds and frames
    rules = Q.her_rules(a.scale)
    muscle_all = tis == TISSUE["muscle"]
    _lab_q164, info = Q.segment_frame(dict(F, muscle=muscle_all), rules, compactness=0.05)
    del _lab_q164
    it, ib = info["i_top"], info["i_bot"]; seg = np.zeros((len(us), 1, 1), bool); seg[it:ib + 1] = True
    ids = info["ids"]; names = list(ids)
    # ---- tissue totals and the classifier check
    vox = ds * ds * float(us[1] - us[0]) / 1000.0            # cm3 per frame voxel
    tot = {k: round(float((tis[it:ib + 1] == v).sum() * vox), 1) for k, v in TISSUE.items() if v}
    unc = {}
    for nm, fn in (("male cryo_classes", classify_m), ("female cryo_classes_f", classify_f)):
        sub = [i for i in range(it, ib + 1, 10)]
        cc = np.stack([fn(rgb[i]) for i in sub]); nb = isl3[sub] & ~bone[sub]
        unc[nm] = {"unclassified_share_of_nonbone": round(float((cc[nb] == 1).mean() + (cc[nb] == 0).mean()), 4),
                   "muscle_share_of_nonbone": round(float((cc[nb] == 3).mean()), 4)}
    vv = rgb.max(-1)
    fisher, overlap = separability(vv[seg & (tis == TISSUE["muscle"])][::7], vv[seg & (tis == TISSUE["fat"])][::7])
    mid = (it + ib) // 2
    midfr = [muscle_fraction_nonbone(tis[i]) for i in range(mid - 5, mid + 6)]
    print(f"tissue totals (cm3, segment): {tot}; muscle/non-bone at mid-forearm {np.mean(midfr):.3f}; "
          f"muscle vs fat brightness Fisher {fisher:.1f}, overlap {overlap:.3f}; unclassified {unc}")
    # ---- the elevation and the watershed inside the muscle class
    musc = muscle_all & seg
    small = np.zeros_like(musc)
    for i in range(it, ib + 1):
        lb, n = ndi.label(musc[i])
        if n:
            sz = np.bincount(lb.ravel()); sm = sz * ds * ds < a.min_speck_mm2; sm[0] = False; small[i] = sm[lb]
    musc &= ~small
    pres = np.zeros(musc.shape, np.float32)
    for i in range(it, ib + 1):
        pres[i] = paleness_residual(rgb[i], isl3[i])
    rp = ndi.gaussian_filter1d(pres, a.ridge_sigma_u, axis=0) if a.ridge_sigma_u > 0 else pres   # septa are sheets along the axis
    ridge = np.clip(rp / a.ridge_full, 0, 1)
    E = elevation(musc, ridge, ds, 3.0, a.w_ridge)
    markers, seeded, nseed = seeds_from_q164(info, E, musc, ids, a.seed_stride, int(round(2.5 / ds)), int(round(1.0 / ds)))
    lab = watershed(E, markers, mask=musc, compactness=0.0).astype(np.uint8)
    unl = float((musc & (lab == 0)).sum() * vox)
    print(f"seeds {nseed} on {len(seeded)} slices; labelled {float((lab > 0).sum() * vox):.1f} cm3, muscle class not reached {unl:.1f} cm3")
    # ---- boundary on septum / non-muscle
    nonm = (tis != TISSUE["muscle"]) | small
    septum = (pres >= a.septum_pale) & isl3
    per = {nm: [] for nm in names}; perc = {nm: [] for nm in names}; inv = {v: k for k, v in ids.items()}; base = []
    for i in range(it, ib + 1):
        onsep = ndi.binary_dilation(nonm[i] | septum[i], structure=np.ones((3, 3), bool))
        if musc[i].any():
            base.append(float(onsep[musc[i]].mean()))
        for l, (f_all, f_ct, _n) in boundary_septum_fractions(lab[i], onsep).items():
            per[inv[l]].append(f_all)
            if f_ct is not None:
                perc[inv[l]].append(f_ct)
    # ---- volumes (RAS grid, as Q164), expectations, gate
    vol, aff = Q.frame_to_ras_volume(lab, us, ss, ts, c, ax)
    voxr = float(abs(np.linalg.det(aff[:3, :3])))
    vols = {nm: round(float((vol == l).sum() * voxr / 1000.0), 1) for nm, l in ids.items()}
    ex = Q.expectations_from_repo(names); arch_arm = Q.expectations_from_repo(list(ARM_MUSCLES))
    his = his_arm_volumes()
    factor = scale_factor({k: v[0] for k, v in his.items()}, {k: arch_arm[k][0] for k in ARM_MUSCLES})
    rows = {}
    for nm, l in ids.items():
        mf, ncomp = Q.main_component_fraction(vol == l)
        exp = ex[nm][0] * factor
        sm = float(np.median(per[nm])) if per[nm] else 0.0
        sc = float(np.median(perc[nm])) if perc[nm] else None
        ok, why = gate_v3(vols[nm], exp, mf, sm, out_of_range=nm in OUT_OF_RANGE)
        rows[nm] = {"label": l, "volume_cm3": vols[nm], "expected_cm3": round(exp, 1), "ratio": round(vols[nm] / exp, 2) if exp else None,
                    "architecture_volume_cm3": ex[nm][0], "expectation_source": ex[nm][1],
                    "main_component_fraction": round(mf, 4), "components_26": ncomp,
                    "boundary_on_septum_or_nonmuscle_median": round(sm, 3), "boundary_on_septum_or_nonmuscle_mean": round(float(np.mean(per[nm])), 3) if per[nm] else None,
                    "contact_boundary_on_septum_median": None if sc is None else round(sc, 3), "slices": len(per[nm]),
                    "out_of_range": nm in OUT_OF_RANGE, "ship": ok, "reason": why}
        print(f"  {nm:32s} {vols[nm]:6.1f} cm3 exp {exp:6.1f} x{vols[nm] / exp:.2f} main {mf:.3f} sep {sm:.2f} contact {sc if sc is None else round(sc, 2)}  {'SHIP' if ok else 'no: ' + why[:60]}")
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    shipped_ids = {ids[nm] for nm, r in rows.items() if r["ship"]}
    nib.save(nib.Nifti1Image(vol, aff), a.out)
    q = [int(it + (ib - it) * f) for f in (0.1, 0.3, 0.5, 0.7, 0.9)]
    mont = montage(rgb, lab, B, info, us, W / "vhm_forearm_v3_montage.png", q, len(ids))
    key = {"_README": [f"Label id -> structure for the Visible Human MALE right forearm muscle volume v3 ({Path(__file__).name}). A KEY, not data. {BADGE}."],
           "source": SOURCE, "task": LABEL_MAP, "version": "2026-09-29", "badge": BADGE, "labels": {str(l): nm for nm, l in ids.items()}}
    Path(a.labels_out).write_text(json.dumps(key, indent=1))
    entries = []
    for nm, r in rows.items():
        e = {"label": r["label"], "source_structure": nm, "side": "right", "relationship": "exact", "candidates": [nm + "_r"]}
        if r["ship"]:
            e.update(status="curated", atlas_id=nm + "_r",
                     procedural_badge=badge_text(r["volume_cm3"], r["expected_cm3"], factor, r["boundary_on_septum_or_nonmuscle_median"], r["contact_boundary_on_septum_median"]),
                     note=f"{BADGE}; SHIPPED: {r['reason']}. Expectation source: {r['expectation_source']} x his upper-arm factor {factor:.3f}.")
        else:
            e.update(status="review", atlas_id=None, note=f"{BADGE}; NOT SHIPPED: {r['reason']}. Expectation source: {r['expectation_source']} x his upper-arm factor {factor:.3f}.")
        entries.append(e)
    Path(a.mapping_out).write_text(json.dumps({"_README": ["Review every entry before running convert.", "Set 'atlas_id' to the correct entity, or null to skip the label.",
                                                            "'status' is advisory; convert reads 'atlas_id' only. 'procedural_badge' is stamped onto the converted manifest by this script's --stamp."],
                                                "subject": SUBJECT, "source_volume": str(Path(a.out).resolve()), "label_map": LABEL_MAP, "entries": entries}, indent=2))
    report = {"source": SOURCE, "badge": BADGE, "script": "scripts/cryo/vhm_forearm_muscles_v3.py", "subject": SUBJECT,
              "reuses": "Q164 registration, reslicing and rule seeds (scripts/cryo/vhm_forearm_muscles_fullres.py; its isl.pkl, track.pkl, frame.npz)",
              "segment": {"u_mm": [float(us[it]), float(us[ib])], "slices": int(ib - it + 1), "rule": "radial head .. distal radius of his CT radius label along the axis"},
              "tissue_classes": {"classifier": "scripts/cryo/cryo_classes.py (male rule), photograph colours resliced nearest",
                                 "class3_agreement_with_q164_muscle_mask": round(agree, 4),
                                 "totals_cm3_segment": tot, "muscle_labelled_cm3": round(float((lab > 0).sum() * vox), 1),
                                 "muscle_specks_dropped_cm3": round(float(small.sum() * vox), 1), "muscle_not_reached_cm3": round(unl, 1),
                                 "mid_forearm_muscle_fraction_of_nonbone": {"u_mm": float(us[mid]), "mean_11_slices": round(float(np.mean(midfr)), 3),
                                                                            "range": [round(min(midfr), 3), round(max(midfr), 3)]},
                                 "muscle_vs_fat_brightness": {"fisher_ratio": round(fisher, 2), "overlap_share": round(overlap, 4),
                                                              "muscle_median_v": int(np.median(vv[seg & (tis == TISSUE["muscle"])])),
                                                              "fat_median_v": int(np.median(vv[seg & (tis == TISSUE["fat"])]))},
                                 "rule_comparison_every_10th_slice": unc},
              "watershed": {"elevation": f"(1-w) x (1 - min(dist to non-muscle, 3 mm)/3 mm) + w x ridge, w = {a.w_ridge}; ridge = paleness residual (g/r minus its 5.5 mm local median) / {a.ridge_full}, clipped 0..1",
                            "mask": "muscle class only (in-plane specks < %.1f mm2 dropped)" % a.min_speck_mm2, "compactness": 0.0,
                            "seeds": f"Q164 rule seeds every {a.seed_stride} mm, moved to the lowest elevation within 2.5 mm, disk 1 mm", "n_seeds": nseed},
              "septum_metric": {"definition": f"per slice, share of a muscle's 4-neighbour boundary pixels within 1 px of a non-muscle pixel or a pale-septum pixel (paleness residual >= {a.septum_pale}); median over slices",
                                "chance_baseline_all_muscle_pixels_median": round(float(np.median(base)), 3)},
              "expectations": {"rule": "V = PCSA x optimal fascicle length / cos(pennation) (data/muscles/upper_limb/<id>_r.json) x ONE factor from his own upper arm",
                               "factor": round(factor, 4),
                               "his_upper_arm_cm3": {k: {"volume_cm3": v[0], "subject": f"build/vh/{v[1]}"} for k, v in his.items()},
                               "architecture_upper_arm_cm3": {k: arch_arm[k][0] for k in ARM_MUSCLES},
                               "published_per_muscle_volumes_offline": "none in data/ (Holzbaur et al. 2007 J Biomech 40:742 is cited by abstract only)",
                               "forearm_architecture_total_cm3": round(sum(v[0] for v in ex.values()), 1),
                               "forearm_expected_total_cm3": round(sum(v[0] for v in ex.values()) * factor, 1)},
              "gate": "0.5 <= volume/expected <= 2.0; main 26-connected component >= 0.98 (islands < 1 % dropped); boundary on septum/non-muscle median >= 0.5; PT/BR/ECRL/anconeus out of range",
              "muscles": rows, "montage": mont, "shipped": [nm + "_r" for nm, r in rows.items() if r["ship"]],
              "shipped_label_ids": sorted(shipped_ids)}
    Path(a.report).parent.mkdir(parents=True, exist_ok=True); Path(a.report).write_text(json.dumps(report, indent=1))
    print(f"factor {factor:.3f} from {his}; shipped {len(report['shipped'])}: {report['shipped']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
