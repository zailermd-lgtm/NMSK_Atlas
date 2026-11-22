"""Female deep neck and suboccipital muscles from her registered 1 mm cryosection frame (Q62 step 3). Rule-based; badged.

    python3 scripts/cryo/vhf_deep_neck_from_cryo.py            # writes the volume, key, mapping, report, montage
    python3 scripts/cryo/vhf_deep_neck_from_cryo.py --frame-dir SCRATCH/vh_cryo_f --out data/ct_sources/task_outputs

DATA (all hers). The z-corrected 1 mm frame of her colour cryosections in her torso-CT frame (cryo_frame_rgb.npy /
cryo_frame_cls.npy, frame.json: z = z0 + k; RAS x = 350 - col, y = 240 - row; her CT slice kk = z0 + k - z_ct0 is laid
into frame columns 110..590 at 480/512 -- the conventions of vhf_pecminor_rhomboids.py / split_shoulder_girdle.py --body f)
and her TotalSegmentator labels as anchors: `total` (vertebrae C1-T3, skull, spinal cord and every other organ, as
exclusions), `headneck_muscles_merged` (trapezius, SCM, levator scapulae, scalenes, constrictors as exclusions; the
`prevertebral` label as the longus mass), `headneck_bones_vessels` (carotids, jugulars, styloid as exclusions) and
vhf_erector_columns.nii.gz (her autochthon-derived erector columns, which reach C5: their voxels above the T1 body top
are the cervical semispinalis / longissimus and are CLAIMED here -- the report records the overlap; the erector
volume itself is left as it is, its cervical part is to be clipped when the ES subject is next rebuilt).

Her frozen tissue photographs dark (cryo_classes_f: her `muscle` class covers organ and marrow as well), so the classes
give only fat (excluded) and tissue; the muscle boundaries come from her CT labels (bone, trapezius, SCM, levator,
scalenes, vessels, viscera subtracted) and from the pale fascial septa of the photographs: marker watershed on the
white top-hat (disk 4 px) of the brightness, as vhf_forearm_muscles_from_cryo.py / vhf_arm_muscles_from_cryo.py.

RULES (Standring, Gray's Anatomy 42nd ed., ch. 43 'Neck' and ch. 44 'Back'; Moore, Clinically Oriented Anatomy 8th ed.,
ch. 2 'Back' and ch. 9 'Neck'), per 1 mm level, per side:
  posterior compartment = muscle-dark tissue (3 px-mean brightness < 115, septa closed 2 px, holes < 80 px filled,
    crumbs < 30 px dropped; the fat class and the paler subcutaneous fat are out) posterior to the posterior surface of the vertebra / occiput in its column
    (posterior to the C1 arch's surface carried up through the atlanto-occipital interval; lateral of the bone, posterior
    to the transverse process' posterior surface), within 55 mm of the midline (38 mm above the SCM label's top),
    deep to the trapezius label (everything posterior to the trapezius in its column is out; where no trapezius is
    labelled -- C1-C3 and the midline aponeurosis -- the 10 mm under the skin and the superficial 5 mm of the muscle
    column, its thin sheet, are out), minus the SCM, levator scapulae, scalene, vessel and viscera labels and
    the spinal cord (dilated 3 mm) and bone (dilated 2 mm);
  bands by the bone at the posterior midline: A = C3..T1 (spinous process of C3-C7 or T1), B = C2, C = C1 posterior arch,
    D = the atlanto-occipital interval (no posterior bone), E = the occipital squama (skull);
  rule boxes (BOX_RULES), per band, in (dx = mm lateral of the midline, f = fraction of the compartment's thickness
    in that column from its anterior surface (0, the lamina / arch / occiput) to its posterior surface (1, the
    trapezius)); the boxes tile the compartment, eroded 3 px they are the watershed markers, so each boundary settles
    on the pale septum nearest the rule cut:
    semispinalis cervicis (+ cervical multifidus, inseparable at 1 mm) against the laminae and spinous processes
      (dx < 18-20, f < 0.28), C2..T1;
    semispinalis capitis, the thick medial column beside the ligamentum nuchae (dx < 26, f 0.28-0.75), T1..occiput;
    splenius (capitis + cervicis, one sheet: the cervicis is its inferolateral part and the two have no septum in
      these photographs), the superficial layer deep to trapezius (f > 0.75 medially, > 0.55 lateral of 26 mm);
    suboccipital triangle: rectus capitis posterior minor on the C1 posterior tubercle (dx < 10, f < 0.3), major
      lateral to it from the C2 spine (dx 10-22, f < 0.3), obliquus capitis inferior from the C2 spine to the C1
      transverse process (dx 16/20-30/32, f < 0.30, bands B-C), obliquus capitis superior from the C1 transverse
      process to the occiput (dx 20-32, f < 0.30, bands D-E); the suboccipitals end 10 mm above the foramen magnum's
      posterior rim (the inferior nuchal line);
    longissimus / iliocostalis cervicis-capitis, lateral of the semispinalis and deep to splenius (dx > 20-26 deep,
      dx > 26 to f 0.55): a SINK region so that erector-column muscle is not attributed to the semispinalis; not shipped;
  prevertebral = her `prevertebral` CT label minus vessels, scalenes, bone and fat: longus colli on the anterior
    vertebral bodies (dx <= 0.75 x the anterior body half-width), longus capitis lateral and superior to it, over
    the anterior tubercles, at levels above the C6 body's lower end (C3-C6 tubercles -> basiocciput), both medial of
    the carotid sheath (carotid / jugular labels subtracted); the cut refined by the same watershed;
  septum support = for each adjacent pair, the mean top-hat on the 1 px boundary band over the mean 2 px inside the
    two regions, contact-weighted over all levels (boundary_support of the forearm script): a pair whose boundary is
    not a pale ridge (ratio < MERGE_RATIO) is MERGED into a named compartment and mapped to null.
Levels: the T1 body's upper end (the erector columns hold everything below) up to the compartment's end on the
occipital squama (at most 35 mm above the top of C1). Rectus capitis anterior and lateralis (each ~ 1 cm3, under the
C1 lateral mass) are NOT attempted: no CT label anchors them and the frame's z residual (8.9 mm rms) is larger than
they are. Semispinalis thoracis is NOT attempted: its T1-T6 territory is inside the erector columns' spinalis /
transversospinalis labels of the CT tasks and it is a thin, largely tendinous sheet at 1 mm.
Output: label volume (RAS 1 mm, frame affine) for `ingest_volume_geometry.py convert`, label key, subject mapping,
report (volumes, merges, levels, septum support, erector overlap, literature comparison), montage.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
SCRATCH = "/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/"
FRAME_DIR = SCRATCH + "vh_cryo_f/"
TASK_DIR = REPO / "data/ct_sources/task_outputs"
OFF, CT_W, FRAME_W = 110, 512, 480          # her CT laid into frame columns OFF..OFF+480 at 480/512
BADGE = "rule-based"
VERSION = "2026-09-14"
SOURCE = ("U.S. National Library of Medicine, The Visible Human Project (public domain), female colour cryosections "
          "(1 mm frame) and CT via the NCI Imaging Data Commons; TotalSegmentator v2.18.0 `total`, `headneck_muscles`, "
          "`headneck_bones_vessels` labels as anchors. Rules from Standring S (ed.), Gray's Anatomy, 42nd ed., ch. 43 "
          "'Neck' and ch. 44 'Back', and Moore KL et al., Clinically Oriented Anatomy, 8th ed. Derived data "
          "(scripts/cryo/vhf_deep_neck_from_cryo.py), rule-based.")

# ---- the rules -------------------------------------------------------------------------------------------------------
LAT_LIMIT_MM = 55          # splenius capitis reaches the mastoid ~ 50 mm from the midline
NO_TRAP_SKIN_MM = 10       # where no trapezius is labelled: subcutaneous fat + the thin trapezius sheet
MERGE_RATIO = 1.25         # boundary top-hat / inside top-hat below this: no visible septum -> merge
SUBOCC_ABOVE_RIM_MM = 10   # suboccipitals insert below the inferior nuchal line, ~ 10 mm above the foramen magnum rim
STOP_ABOVE_C1_MM = 35

# band -> {muscle: [(dx0, dx1, f0, f1), ...]}: boxes in (dx = mm lateral of the midline, f = depth fraction through the
# compartment's column, 0 at the bone, 1 at the trapezius). The boxes tile the compartment; eroded 3 px they are the
# watershed markers, so the boundary between two muscles is the pale septum nearest the rule boundary. The sink
# 'erector_cervical' (longissimus / iliocostalis cervicis-capitis) is not shipped.
_SPLENIUS = [(0, 26, 0.75, 1.01), (26, 60, 0.55, 1.01)]     # a broad thin sheet: the superficial quarter medially
_SS_CAP = [(0, 26, 0.28, 0.75)]
_ERECTOR_LAT = [(26, 60, 0.28, 0.55)]
BOX_RULES = {
    "A": {"semispinalis_cervicis": [(0, 20, 0.0, 0.28)], "semispinalis_capitis": _SS_CAP, "splenius": _SPLENIUS,
          "erector_cervical": [(20, 60, 0.0, 0.28)] + _ERECTOR_LAT},
    "B": {"semispinalis_cervicis": [(0, 16, 0.0, 0.28)], "obliquus_capitis_inferior": [(16, 30, 0.0, 0.28)],
          "semispinalis_capitis": _SS_CAP, "splenius": _SPLENIUS,
          "erector_cervical": [(30, 60, 0.0, 0.55), (26, 30, 0.28, 0.55)]},
    "C": {"rectus_capitis_posterior_minor": [(0, 10, 0.0, 0.30)], "rectus_capitis_posterior_major": [(10, 20, 0.0, 0.30)],
          "obliquus_capitis_inferior": [(20, 32, 0.0, 0.30)], "semispinalis_capitis": [(0, 26, 0.30, 0.75)], "splenius": _SPLENIUS,
          "erector_cervical": [(32, 60, 0.0, 0.55), (26, 32, 0.30, 0.55)]},
    "D": {"rectus_capitis_posterior_minor": [(0, 10, 0.0, 0.30)], "rectus_capitis_posterior_major": [(10, 20, 0.0, 0.30)],
          "obliquus_capitis_superior": [(20, 32, 0.0, 0.30)], "semispinalis_capitis": [(0, 26, 0.30, 0.75)], "splenius": _SPLENIUS,
          "erector_cervical": [(32, 60, 0.0, 0.55), (26, 32, 0.30, 0.55)]},
    "E": {"rectus_capitis_posterior_minor": [(0, 10, 0.0, 0.30)], "rectus_capitis_posterior_major": [(10, 20, 0.0, 0.30)],
          "obliquus_capitis_superior": [(20, 32, 0.0, 0.30)], "semispinalis_capitis": [(0, 26, 0.30, 0.75)], "splenius": _SPLENIUS,
          "erector_cervical": [(32, 60, 0.0, 0.55), (26, 32, 0.30, 0.55)]},
    "E_high": {"semispinalis_capitis": [(0, 26, 0.0, 0.65)], "splenius": [(0, 26, 0.65, 1.01), (26, 60, 0.5, 1.01)],
               "erector_cervical": [(26, 60, 0.0, 0.5)]},
}
BAND_ORDER = ("A", "B", "C", "D", "E", "E_high")
LAT_LIMIT_NO_SCM_MM = 38   # above the SCM label's top (C1) the lateral limit falls to the mastoid's deep face
DARK_V = 115               # her frozen muscle: 3 px-mean brightness below this (fat and pale connective tissue above)
MIN_HOLE_PX, MIN_PART_PX = 80, 30
TRAP_SHEET_MM = 5          # where no trapezius is labelled (C1-C3, the midline aponeurosis) its thin sheet: the superficial 5 mm
MARKER_ERODE_PX = 3
PREV_SPLIT = 0.75          # longus colli: dx <= 0.75 x the anterior body half-width; longus capitis lateral of that
SUBOCCIPITALS = ("rectus_capitis_posterior_minor", "rectus_capitis_posterior_major",
                 "obliquus_capitis_inferior", "obliquus_capitis_superior")
POSTERIOR = ("splenius", "semispinalis_capitis", "semispinalis_cervicis") + SUBOCCIPITALS + ("erector_cervical",)
PREVERTEBRAL = ("longus_colli", "longus_capitis")
MUSCLES = POSTERIOR + PREVERTEBRAL
NOT_SHIPPED = {"erector_cervical": "sink for the longissimus / iliocostalis cervicis-capitis lateral of the semispinalis "
                                   "capitis (erector column, not a target; keeps erector muscle out of the semispinalis)"}
ATLAS_OF = {"semispinalis_cervicis": "semispinalis_cervicis", "semispinalis_capitis": "semispinalis_capitis",
            "splenius": None, "rectus_capitis_posterior_minor": "rectus_capitis_posterior_minor",
            "rectus_capitis_posterior_major": "rectus_capitis_posterior_major",
            "obliquus_capitis_inferior": "obliquus_capitis_inferior", "obliquus_capitis_superior": "obliquus_capitis_superior",
            "longus_colli": "longus_colli", "longus_capitis": "longus_capitis", "erector_cervical": None}
CANDIDATES = {"splenius": ["splenius_capitis", "splenius_cervicis"],
              "semispinalis_cervicis": ["semispinalis_cervicis", "multifidus"]}
VERT_IDS = {41: "T3", 42: "T2", 43: "T1", 44: "C7", 45: "C6", 46: "C5", 47: "C4", 48: "C3", 49: "C2", 50: "C1"}
SKULL, SPINAL_CORD = 91, 79
AUTOCHTHON = (86, 87)                     # her erector columns come from these; above T1 they are the cervical semispinalis
NECK_EXCL = list(range(1, 22))            # every headneck muscle label but the prevertebral pair (22, 23)
NECK_TRAP = {"right": 6, "left": 7}
NECK_SCM = {"right": 1, "left": 2}
NECK_PREV = {"right": 22, "left": 23}
BV_EXCL = list(range(1, 13))


def band_of(post_midline_ids, above_c1_arch, k_above_rim_mm=None):
    """Band from the label ids of the bone at the posterior midline (rows behind the vertebral centre, |dx| < 10 mm).
    C2 -> B, C1 -> C, skull -> E (E_high more than SUBOCC_ABOVE_RIM_MM above the foramen magnum's posterior rim),
    any other vertebra -> A; nothing: D once the C1 arch has been passed, else A (an interspinous gap)."""
    ids = set(int(i) for i in post_midline_ids)
    if 49 in ids:
        return "B"
    if 50 in ids:
        return "C"
    if SKULL in ids:
        return "E_high" if (k_above_rim_mm is not None and k_above_rim_mm > SUBOCC_ABOVE_RIM_MM) else "E"
    if ids & set(range(41, 49)):
        return "A"
    return "D" if above_c1_arch else "A"


def depth_fraction(shape, first, last):
    """f = fraction of the way from a column's first (anterior) to last (posterior) compartment row; NaN outside."""
    yy = np.arange(shape[0])[:, None].astype(float)
    span = np.where(last > first, last - first, np.nan)[None, :]
    return (yy - first[None, :]) / span


def rule_regions(band, dx, f, comp):
    """{muscle: mask} from the band's boxes over dx (mm lateral, per pixel) and f (depth fraction, per pixel) inside
    the compartment."""
    out = {}
    for name, boxes in BOX_RULES[band].items():
        m = np.zeros(comp.shape, bool)
        for dx0, dx1, f0, f1 in boxes:
            m |= (dx >= dx0) & (dx < dx1) & (f >= f0) & (f < f1)
        m &= comp
        if m.any():
            out[name] = m
    return out


def prevertebral_regions(pv, dx, body_half_width, above_c6):
    """Longus colli medial (dx <= PREV_SPLIT x the anterior body half-width), longus capitis lateral of it at levels
    above the lower end of the C6 body; all colli below."""
    if not above_c6:
        return {"longus_colli": pv}
    cut = PREV_SPLIT * body_half_width
    out = {"longus_colli": pv & (dx <= cut), "longus_capitis": pv & (dx > cut)}
    return {k: v for k, v in out.items() if v.any()}


def merge_decision(support, ratio=MERGE_RATIO):
    """support: {(a, b): [(contact_px, ridge_ratio), ...]} -> {(a, b): (weighted ratio, contact, merge?)}."""
    merged = {}
    for pair, obs in support.items():
        w = sum(n for n, _ in obs)
        if w == 0:
            continue
        r = sum(n * q for n, q in obs) / w
        merged[pair] = (round(r, 2), int(w), r < ratio)
    return merged


def split_region(th, region, rules, ids):
    """Marker watershed of `region` on the top-hat `th` from the rule regions eroded MARKER_ERODE_PX (a region that
    erodes away keeps its 1 px erosion, then itself): the boundary settles on the pale septum nearest the rule cut."""
    from scipy import ndimage as ndi
    from skimage.segmentation import watershed
    markers = np.zeros(region.shape, np.int32)
    for name, m in rules.items():
        core = ndi.binary_erosion(m, iterations=MARKER_ERODE_PX)
        if core.sum() < 10:
            core = ndi.binary_erosion(m, iterations=1)
        if core.sum() < 10:
            core = m
        markers[core & (markers == 0)] = ids[name]
    if not markers.any():
        return {}
    ws = watershed(th, markers, mask=region)
    return {name: ws == l for name, l in ids.items() if (ws == l).any()}


def boundary_support(th, cur, min_contact_px=15):
    """Per adjacent pair: (contact px, mean top-hat on the 1 px boundary band / mean top-hat 2 px inside)."""
    from scipy import ndimage as ndi
    out = {}; names = list(cur)
    er = {nm: ndi.binary_erosion(cur[nm], iterations=2) for nm in names}
    dil = {nm: ndi.binary_dilation(cur[nm], iterations=1) for nm in names}
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            band = (dil[a] & cur[b]) | (dil[b] & cur[a]); nb = int(band.sum())
            if nb < min_contact_px:
                continue
            inside = er[a] | er[b]
            ratio = float(th[band].mean() / max(th[inside].mean(), 1e-3)) if inside.any() else 0.0
            out[tuple(sorted((a, b)))] = (nb, round(ratio, 2))
    return out


# ---- the data ---------------------------------------------------------------------------------------------------------
class Frame:
    def __init__(self, frame_dir, task_dir):
        import nibabel as nib
        d = Path(frame_dir)
        self.cls = np.load(d / "cryo_frame_cls.npy", mmap_mode="r"); self.rgb = np.load(d / "cryo_frame_rgb.npy", mmap_mode="r")
        self.z0 = float(json.load(open(d / "frame.json"))["z0"]); self.n, self.H, self.W = self.cls.shape
        def load(name):
            im = nib.load(str(Path(task_dir) / name)); return np.asarray(im.dataobj), float(im.affine[2, 3])
        self.tot, self.zT0 = load("vhf_total.nii.gz"); self.neck, self.zN0 = load("vhf_headneck_muscles_merged.nii.gz")
        self.bv, self.zB0 = load("vhf_headneck_bones_vessels.nii.gz"); self.es, self.zE0 = load("vhf_erector_columns.nii.gz")

    def ct(self, arr, zoff, k):
        from scipy import ndimage as ndi
        kk = int(round(self.z0 + k - zoff)); f = np.zeros((self.H, self.W), np.int32)
        if 0 <= kk < arr.shape[2]:
            f[:, OFF:OFF + FRAME_W] = ndi.zoom(arr[:, :, kk], FRAME_W / CT_W, order=0).T
        return f

    def k_of_ct(self, kk):
        return int(round(self.zT0 + kk - self.z0))

    def z_range(self, label_id, arr=None):
        arr = self.tot if arr is None else arr
        z = np.where((arr == label_id).any(axis=(0, 1)))[0]
        return (int(z.min()), int(z.max())) if len(z) else None


def level_masks(fr, k):
    """Everything one level needs, from the photograph classes and the CT labels laid into the frame."""
    from scipy import ndimage as ndi
    c = np.asarray(fr.cls[k]); t = fr.ct(fr.tot, fr.zT0, k); nk = fr.ct(fr.neck, fr.zN0, k); b = fr.ct(fr.bv, fr.zB0, k)
    e = fr.ct(fr.es, fr.zE0, k)
    vert = np.isin(t, list(VERT_IDS)); skull = t == SKULL; bone = vert | skull
    tissue = ndi.binary_fill_holes(ndi.binary_closing(c > 0, iterations=3))
    dskin = ndi.distance_transform_edt(tissue)
    other = ((t > 0) & ~bone & (t != SPINAL_CORD) & ~np.isin(t, AUTOCHTHON)) | np.isin(nk, NECK_EXCL) | np.isin(b, BV_EXCL)
    excl = ndi.binary_dilation(other, iterations=1) | ndi.binary_dilation(t == SPINAL_CORD, iterations=3) \
        | ndi.binary_dilation(bone, iterations=2) | (c == 2) | ~tissue | (dskin <= 4)
    v = ndi.uniform_filter(np.asarray(fr.rgb[k]).max(-1).astype(np.float32), 3)
    dark = ndi.binary_closing(v < DARK_V, iterations=2)          # her muscle, its septa closed over
    return dict(c=c, t=t, nk=nk, b=b, e=e, vert=vert, skull=skull, bone=bone, tissue=tissue, dskin=dskin, excl=excl, dark=dark)


def posterior_compartment(M, side, sgn, mid, vrow, post_ref, H, W):
    """The side's posterior compartment (see the docstring) and the per-column first / last rows."""
    yy, xx = np.mgrid[0:H, 0:W]
    dx = sgn * (xx - mid)
    ref = post_ref.copy()
    bc = np.where(M["bone"].any(axis=0) & (sgn * (np.arange(W) - mid) >= 0))[0]
    if len(bc):                                             # lateral of the bone: behind the transverse process' posterior surface
        tip = bc[np.argmax(sgn * (bc - mid))]; near = bc[np.abs(bc - tip) <= 8]
        tp_row = float(np.where(M["bone"][:, near], yy[:, near], -1).max())
        lat = sgn * (np.arange(W) - mid) > sgn * (tip - mid)
        ref[lat] = tp_row
    behind = yy > ref[None, :]
    trap = M["nk"] == NECK_TRAP[side]
    sup = np.cumsum(trap, axis=0) > 0                       # the trapezius and everything posterior to it
    no_trap_col = ~trap.any(axis=0)
    lat_limit = LAT_LIMIT_MM if (M["nk"] == NECK_SCM[side]).any() else LAT_LIMIT_NO_SCM_MM
    comp = behind & (dx >= 0) & (dx <= lat_limit) & ~M["excl"] & ~sup & ~(no_trap_col[None, :] & (M["dskin"] < NO_TRAP_SKIN_MM))
    comp &= yy > vrow - 5                                   # never anterior of the vertebral centre
    comp &= M["dark"]                                       # muscle-dark: the subcutaneous fat is out whatever its class
    if comp.any():
        comp = fill_small_holes(comp, MIN_HOLE_PX)
        lab, nl = ndi_label(comp)
        sizes = np.bincount(lab.ravel())[1:]
        keep = np.isin(lab, np.where(sizes >= MIN_PART_PX)[0] + 1)   # drop crumbs
        comp &= keep
    first, last = column_extent(comp)
    sheet = no_trap_col[None, :] & (yy > (last - TRAP_SHEET_MM)[None, :])   # the unlabelled trapezius sheet
    comp &= ~sheet
    first, last = column_extent(comp)
    return comp, first, last


def column_extent(comp):
    W = comp.shape[1]; first = np.full(W, np.nan); last = np.full(W, np.nan)
    for cc in np.where(comp.any(axis=0))[0]:
        rs = np.where(comp[:, cc])[0]; first[cc] = rs.min(); last[cc] = rs.max()
    return first, last


def ndi_label(m):
    from scipy import ndimage as ndi
    return ndi.label(m)


def fill_small_holes(m, max_px):
    """Fill the holes of m smaller than max_px (vessels and septa inside a muscle; not a fat pocket)."""
    from scipy import ndimage as ndi
    holes = ndi.binary_fill_holes(m) & ~m
    lab, n = ndi.label(holes)
    if n == 0:
        return m
    sizes = np.bincount(lab.ravel())[1:]
    return m | np.isin(lab, np.where(sizes < max_px)[0] + 1)


def prevertebral_mask(M, side, sgn, mid):
    from scipy import ndimage as ndi
    pv = (M["nk"] == NECK_PREV[side]) & ~(M["c"] == 2) & ~ndi.binary_dilation(np.isin(M["b"], BV_EXCL), iterations=1) \
        & ~ndi.binary_dilation(M["bone"], iterations=1) & ~np.isin(M["nk"], list(range(12, 18))) & M["dark"]
    return pv


def body_half_width(vert, mid, sgn):
    """Half-width of the anterior 8 mm of the vertebra on this side (the body's anterior face, not the transverse
    process)."""
    ys, xs = np.where(vert)
    if len(ys) == 0:
        return None
    front = ys < ys.min() + 8
    d = sgn * (xs[front] - mid)
    return float(max(d.max(), 4.0))


# ---- the run ---------------------------------------------------------------------------------------------------------
def run(a, log=print):
    from scipy import ndimage as ndi
    from skimage.morphology import white_tophat, disk
    fr = Frame(a.frame_dir, a.task_dir); H, W = fr.H, fr.W
    zT1 = fr.z_range(43); zC1 = fr.z_range(50); zC2 = fr.z_range(49); zC6 = fr.z_range(45)
    k_lo = fr.k_of_ct(zT1[1]); k_c1_top = fr.k_of_ct(zC1[1]); k_hi = min(k_c1_top + STOP_ABOVE_C1_MM, fr.n - 1)
    k_c2_bot = fr.k_of_ct(zC2[0]); k_c6_bot = fr.k_of_ct(zC6[0])
    log(f"levels k {k_lo}..{k_hi} (z {fr.z0 + k_lo:.0f}..{fr.z0 + k_hi:.0f}); C2 bottom k {k_c2_bot}, C6 bottom k {k_c6_bot}, C1 top k {k_c1_top}")
    ids = {nm: i + 1 for i, nm in enumerate(MUSCLES)}
    out = {}                                   # k -> per-level label image (raw muscle ids, both sides)
    support = {"right": {}, "left": {}}; bands = {}; erector_overlap = np.zeros(7, np.int64)
    mid = vrow = None; post_ref = None; k_rim = None; c1_arch_seen = False; empty_run = 0
    for k in range(k_lo, k_hi + 1):
        M = level_masks(fr, k); im = np.asarray(fr.rgb[k])
        if M["vert"].any():
            ys, xs = np.where(M["vert"]); mid = float(xs.mean()); vrow = float(ys.mean())
        if mid is None:
            continue
        yy, xx = np.mgrid[0:H, 0:W]
        has_bone = M["bone"].any(axis=0)
        post_row = np.where(has_bone, np.where(M["bone"], yy, -1).max(axis=0), -1).astype(float)
        if post_ref is None:
            post_ref = np.full(W, float(vrow))
        bc = np.where(has_bone)[0]; span = np.zeros(W, bool)
        if len(bc):
            span[bc.min():bc.max() + 1] = True
        # the bone's posterior surface; carried up inside the bone's span (the atlanto-occipital interval), the
        # vertebral centre row lateral of it
        post_ref = np.where(has_bone, post_row, np.where(span, post_ref, float(vrow)))
        pm_ids = np.unique(M["t"][(yy > vrow) & (np.abs(xx - mid) < 10)]); pm_ids = pm_ids[np.isin(pm_ids, list(VERT_IDS) + [SKULL])]
        if 50 in pm_ids:
            c1_arch_seen = True
        if SKULL in pm_ids and k_rim is None:
            k_rim = k
        band = band_of(pm_ids, c1_arch_seen, None if k_rim is None else k - k_rim)
        if bands and BAND_ORDER.index(band) < BAND_ORDER.index(bands[max(bands)]):
            band = bands[max(bands)]                     # bands never go back down (a C2 label above the C1 arch is the dens)
        bands[k] = band
        th = white_tophat(im.max(-1).astype(np.float32), disk(4))
        lvl = np.zeros((H, W), np.uint8); any_comp = False
        dxmap = (xx - mid).astype(float)
        for side, sgn in (("right", -1), ("left", 1)):
            comp, first, last = posterior_compartment(M, side, sgn, mid, vrow, post_ref, H, W)
            if comp.sum() >= 150:
                any_comp = True
            f = depth_fraction((H, W), first, last)
            rules = rule_regions(band, sgn * dxmap, f, comp)
            regs = split_region(th, comp, rules, {nm: ids[nm] for nm in rules})
            # prevertebral
            pvm = prevertebral_mask(M, side, sgn, mid) & (sgn * dxmap >= 0)
            if pvm.sum() >= 20 and M["vert"].any():
                bw = body_half_width(M["vert"], mid, sgn)
                prules = prevertebral_regions(pvm, sgn * dxmap, bw, k > k_c6_bot)
                regs.update(split_region(th, pvm, prules, {nm: ids[nm] for nm in prules}))
            for nm, m in regs.items():
                lvl[m & (lvl == 0)] = ids[nm]
            for pair, obs in boundary_support(th, {nm: m for nm, m in regs.items() if nm in POSTERIOR}).items():
                support[side].setdefault(pair, []).append(obs)
            for pair, obs in boundary_support(th, {nm: m for nm, m in regs.items() if nm in PREVERTEBRAL}).items():
                support[side].setdefault(pair, []).append(obs)
        if lvl.any():
            out[k] = lvl
        erector_overlap += np.bincount(M["e"][lvl > 0].ravel(), minlength=7)[:7]
        empty_run = 0 if any_comp else empty_run + 1
        if k % 10 == 0:
            log(f"k {k} z {fr.z0 + k:.0f} band {band} px {int((lvl > 0).sum())}")
        if band in ("E", "E_high") and empty_run >= 3:
            log(f"compartment ended at k {k}"); break
    # merges
    merges = {}; dec = {s: merge_decision(support[s]) for s in support}
    for pair in set(dec["right"]) | set(dec["left"]):
        obs = [dec[s][pair] for s in ("right", "left") if pair in dec[s]]
        w = sum(o[1] for o in obs); r = sum(o[0] * o[1] for o in obs) / max(w, 1)
        merges[pair] = {"ratio": round(r, 2), "contact_px": int(w), "merge": bool(r < MERGE_RATIO)}
    groups = merge_groups({p for p, d in merges.items() if d["merge"]})
    return fr, out, ids, bands, merges, groups, erector_overlap, (k_lo, k_hi, k_c2_bot, k_c6_bot, k_c1_top, k_rim)


def merge_groups(pairs):
    """Connected components of the merged pairs -> {frozenset(names)}. The sink never merges into a shipped group:
    a pair with erector_cervical is dropped (the boundary is recorded, the sink stays a sink)."""
    pairs = [p for p in pairs if "erector_cervical" not in p]
    groups = []
    for a, b in pairs:
        ga = next((g for g in groups if a in g), None); gb = next((g for g in groups if b in g), None)
        if ga is None and gb is None:
            groups.append({a, b})
        elif ga is None:
            gb.add(a)
        elif gb is None:
            ga.add(b)
        elif ga is not gb:
            ga |= gb; groups.remove(gb)
    return [frozenset(g) for g in groups]


def group_name(g):
    if g <= set(SUBOCCIPITALS):
        return "suboccipital_group"
    if g == {"longus_colli", "longus_capitis"}:
        return "longus_group"
    if g <= {"semispinalis_capitis", "semispinalis_cervicis"}:
        return "semispinalis_group"
    if "splenius" in g and g <= {"splenius", "semispinalis_capitis"}:
        return "splenius_semispinalis_compartment"
    return "_".join(sorted(g)) + "_compartment"


def relabel(ids, groups):
    """Final label table: right block then left block; merged groups become one label per side. Returns the table
    [(name, members)], {label id: (name_side, base name, members, side)} and the raw-id -> label LUT per side."""
    final = []            # (name, members)
    taken = set()
    for nm in MUSCLES:
        g = next((g for g in groups if nm in g), None)
        if g is None:
            final.append((nm, [nm]))
        elif g not in taken:
            taken.add(g); final.append((group_name(g), sorted(g)))
    labels = {}
    for si, side in enumerate(("right", "left")):
        for i, (nm, members) in enumerate(final):
            labels[si * len(final) + i + 1] = (f"{nm}_{side}", nm, members, side)
    lut_r = np.zeros(len(MUSCLES) + 1, np.uint8); lut_l = np.zeros(len(MUSCLES) + 1, np.uint8)
    for lid, (_, nm, members, side) in labels.items():
        for m in members:
            (lut_r if side == "right" else lut_l)[ids[m]] = lid
    return final, labels, lut_r, lut_l


def montage(fr, vol, labels, ks, mid_row_col, path, ka):
    from PIL import Image, ImageDraw
    import colorsys
    n = max(labels) + 1
    lut = np.zeros((n, 3), np.uint8)
    for lid, (nm, base, _, _) in labels.items():
        h = (list(dict.fromkeys(l[1] for l in labels.values())).index(base) * 0.137) % 1.0
        lut[lid] = [int(255 * v) for v in colorsys.hsv_to_rgb(h, 0.85, 1.0)]
    tiles = []
    for name, k in ks:
        im = np.asarray(fr.rgb[k]).copy(); m = vol[k - ka]; ov = im.copy()
        sel = m > 0; ov[sel] = (0.45 * im[sel] + 0.55 * lut[m[sel]]).astype(np.uint8)
        r, c = mid_row_col[k]; r0, c0 = max(int(r) - 70, 0), max(int(c) - 90, 0)
        crop = np.concatenate([im[r0:r0 + 190, c0:c0 + 180], ov[r0:r0 + 190, c0:c0 + 180]], axis=0)
        crop = np.kron(crop, np.ones((2, 2, 1), np.uint8))
        pil = Image.fromarray(crop); ImageDraw.Draw(pil).text((4, 4), f"{name} k={k} z={fr.z0 + k:.0f}", fill=(255, 255, 0))
        tiles.append(np.asarray(pil))
    leg = Image.new("RGB", (tiles[0].shape[1] * len(tiles), 14 * ((len(set(l[1] for l in labels.values())) + 3) // 4 + 1)), (0, 0, 0))
    d = ImageDraw.Draw(leg); x = 4; y = 2; cw = leg.width // 4
    for i, base in enumerate(dict.fromkeys(l[1] for l in labels.values())):
        lid = next(l for l, v in labels.items() if v[1] == base)
        d.rectangle([x, y, x + 10, y + 10], fill=tuple(int(v) for v in lut[lid])); d.text((x + 14, y - 2), base, fill=(255, 255, 255))
        x += cw
        if x + cw > leg.width:
            x = 4; y += 14
    full = np.concatenate([np.concatenate(tiles, axis=1), np.asarray(leg)], axis=0)
    Image.fromarray(full).save(path)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--frame-dir", default=FRAME_DIR); ap.add_argument("--task-dir", default=str(TASK_DIR))
    ap.add_argument("--out", default=str(TASK_DIR / "vhf_deep_neck_cryo.nii.gz"))
    ap.add_argument("--labels-out", default=str(REPO / "mappings/vhf_deep_neck_labels.json"))
    ap.add_argument("--mapping-out", default=str(REPO / "mappings/subjects/ct_vhf_dneck_volume_mapping.json"))
    a = ap.parse_args(argv)
    import nibabel as nib
    fr, out, ids, bands, merges, groups, erector_overlap, (k_lo, k_hi, k_c2_bot, k_c6_bot, k_c1_top, k_rim) = run(a)
    final, labels, lut_r, lut_l = relabel(ids, groups)
    # sides: right = cols < mid (RAS +x is the patient's right; x = 350 - col) -- the per-level regions were built per side
    # of the vertebral midline, so the side of a voxel is the side of its column
    ka, kb = min(out), max(out) + 1
    vol = np.zeros((kb - ka, fr.H, fr.W), np.uint8); mids = {}
    for k in range(ka, kb):
        t = fr.ct(fr.tot, fr.zT0, k); v = np.isin(t, list(VERT_IDS))
        if v.any():
            ys, xs = np.where(v); mids[k] = (float(ys.mean()), float(xs.mean()))
        else:
            mids[k] = mids[k - 1]
        if k in out:
            r, c = mids[k]; left = np.arange(fr.W)[None, :] > c
            vol[k - ka] = np.where(left, lut_l[out[k]], lut_r[out[k]])
    aff = np.array([[-1, 0, 0, 350], [0, -1, 0, 240], [0, 0, 1, fr.z0 + ka], [0, 0, 0, 1]], float)
    nib.save(nib.Nifti1Image(np.ascontiguousarray(vol.transpose(2, 1, 0)), aff), a.out)
    vols = {nm: round(float((vol == lid).sum()) / 1000, 1) for lid, (nm, *_) in labels.items()}
    print("volumes cm3", vols, flush=True)
    # levels used
    zr = lambda k: float(fr.z0 + k)
    levels = {"k_range": [k_lo, k_hi], "z_ras_range": [zr(k_lo), zr(k_hi)], "ct_slice_range": [int(k_lo + fr.z0 - fr.zT0), int(k_hi + fr.z0 - fr.zT0)],
              "T1_body_top_k": k_lo, "C6_body_bottom_k": k_c6_bot, "C2_body_bottom_k": k_c2_bot, "C1_top_k": k_c1_top,
              "foramen_magnum_posterior_rim_k": k_rim, "bands_by_k": {str(k): b for k, b in bands.items()},
              "band_extent_k": {b: [min(k for k, bb in bands.items() if bb == b), max(k for k, bb in bands.items() if bb == b)] for b in set(bands.values())}}
    montage_levels = []
    for nm, vid in (("C1", 50), ("C2", 49), ("C4", 47), ("C6", 45), ("T1", 43)):
        z = fr.z_range(vid); k = fr.k_of_ct((z[0] + z[1]) // 2)
        k = max(min(k, kb - 1), ka); montage_levels.append((nm, k))
    mpath = str(Path(a.out).with_suffix("").with_suffix("")) + ".png"
    montage(fr, vol, labels, [(nm, k) for nm, k in montage_levels], {k: mids[k] for k in mids}, mpath, ka)
    # mapping + key + report
    merged_compartments = {}
    for nm, members in final:
        if len(members) > 1 or nm == "splenius":
            merged_compartments[nm] = members if len(members) > 1 else ["splenius_capitis", "splenius_cervicis"]
    def note_for(lid):
        nm, base, members, side = labels[lid]; v = vols[nm]
        if base == "erector_cervical":
            return f"{v} cm3; NOT shipped: {NOT_SHIPPED['erector_cervical']}."
        if base == "splenius":
            return (f"{v} cm3; compartment: splenius capitis + splenius cervicis, one sheet in these photographs (no septum "
                    f"between the capitis and its inferolateral cervicis part at 1 mm); mapped to null, candidates listed.")
        if len(members) > 1:
            pairs = [f"{p[0]}/{p[1]} ratio {d['ratio']}" for p, d in merges.items() if d["merge"] and set(p) <= set(members)]
            return (f"{v} cm3; compartment holding {', '.join(members)}: the marker watershed found no pale septum between them "
                    f"(boundary / inside top-hat {'; '.join(pairs)} < {MERGE_RATIO}); not split, mapped to null.")
        if base == "semispinalis_cervicis":
            return f"{v} cm3; {BADGE}: semispinalis cervicis with the cervical multifidus (inseparable at 1 mm), C2-T1; below T1 its origin lies inside the erector columns."
        return f"{v} cm3; {BADGE}: position-rule marker relative to her vertebral labels, boundary by the marker watershed on her fascial septa."
    entries = []
    for lid in sorted(labels):
        nm, base, members, side = labels[lid]; atlas = ATLAS_OF.get(base) if len(members) == 1 else None
        sfx = "_r" if side == "right" else "_l"
        cands = []
        if atlas is None:
            cands = [m + sfx for m in (CANDIDATES.get(base) or (members if len(members) > 1 else []))]
        entries.append({"label": lid, "source_structure": nm, "side": side, "status": "curated",
                        "atlas_id": atlas + sfx if atlas else None, "relationship": "exact" if atlas else "no_usable_label",
                        "note": note_for(lid), "candidates": cands})
    readme_key = (f"Label id -> structure name for the Visible Human FEMALE deep neck / suboccipital volume "
                  f"(scripts/cryo/vhf_deep_neck_from_cryo.py), plus the mapping onto atlas entities. A KEY, not data. "
                  f"{BADGE}: markers by position rules relative to her vertebral labels, boundaries by marker watershed on the pale "
                  f"septa of her cryosection photographs; compartments are muscles the photographs do not separate (mapped to null).")
    key = {"_README": [readme_key], "source": SOURCE, "task": "vhf_deep_neck", "version": VERSION, "badge": BADGE,
           "labels": {str(l): labels[l][0] for l in sorted(labels)},
           "merged_compartments": merged_compartments,
           "not_attempted": {"rectus_capitis_anterior": "~1 cm3 under the C1 lateral mass: no CT label anchors it and the frame's z residual (8.9 mm rms) exceeds its size",
                             "rectus_capitis_lateralis": "same as rectus capitis anterior",
                             "semispinalis_thoracis": "its T1-T6 territory is inside the erector columns' spinalis / transversospinalis labels; thin and largely tendinous at 1 mm",
                             "splenius_cervicis": "not separable from splenius capitis (one sheet); carried in the splenius compartment"},
           "atlas": {e["source_structure"]: {"atlas_id": e["atlas_id"], "relationship": e["relationship"], "note": e["note"]} for e in entries}}
    json.dump(key, open(a.labels_out, "w"), indent=1)
    mapping = {"_README": ["Review every entry before running convert.", "Set 'atlas_id' to the correct entity, or null to skip the label.",
                           "'status' is advisory; convert reads 'atlas_id' only."],
               "subject": "ct_vhf_dneck", "source_volume": str(Path(a.out).resolve()), "label_map": "vhf_deep_neck", "entries": entries}
    json.dump(mapping, open(a.mapping_out, "w"), indent=1)
    es_names = {1: "spinalis_right", 2: "longissimus_right", 3: "iliocostalis_right", 4: "spinalis_left", 5: "longissimus_left", 6: "iliocostalis_left"}
    report = {
        "_README": ["Female deep neck and suboccipital muscles by position rules on her registered 1 mm cryosection frame "
                    "(scripts/cryo/vhf_deep_neck_from_cryo.py). Rule-based, derived data."],
        "source": SOURCE, "badge": BADGE, "version": VERSION,
        "volumes_cm3": vols,
        "labels": {str(l): labels[l][0] for l in sorted(labels)},
        "merged": {nm: {"members": members, "why": note_for(next(l for l, v in labels.items() if v[0] == nm + "_right"))}
                   for nm, members in final if len(members) > 1 or nm == "splenius"},
        "not_shipped": {**key["not_attempted"], **NOT_SHIPPED},
        "septum_support": {f"{p[0]}|{p[1]}": d for p, d in merges.items()},
        "merge_ratio_threshold": MERGE_RATIO,
        "levels": levels,
        "rules": {"box_rules_dx0_dx1_f0_f1": BOX_RULES, "marker_erode_px": MARKER_ERODE_PX, "lateral_limit_mm": [LAT_LIMIT_MM, LAT_LIMIT_NO_SCM_MM],
                  "no_trapezius_skin_mm": NO_TRAP_SKIN_MM, "suboccipitals_above_rim_mm": SUBOCC_ABOVE_RIM_MM,
                  "prevertebral": f"longus colli: dx <= {PREV_SPLIT} x the anterior body half-width; longus capitis lateral of that above the C6 body's lower end"},
        "erector_overlap_cm3": {es_names[i]: round(float(erector_overlap[i]) / 1000, 1) for i in range(1, 7) if erector_overlap[i]},
        "erector_overlap_note": "voxels of vhf_erector_columns.nii.gz (autochthon-derived, reaching C5) above the T1 body top that this volume claims as "
                                "semispinalis / longissimus; vhf_erector_columns.nii.gz is unchanged -- clip it at the T1 body top when the ES subject is rebuilt.",
        "literature": {
            "note": "MRI cross-sectional areas, not volumes; compared as mean CSA = volume / craniocaudal extent of the label.",
            "deep_extensors_C3_C6": {"pmid": "21431426", "doi": "10.1007/s00586-011-1774-x",
                                     "value": "multifidus + semispinalis cervicis + semispinalis capitis + splenius capitis CSA 1397-1600 mm2 at C3/4-C5/6 (asymptomatic adults, Okada 2011, Eur Spine J)"},
            "cervical_extensors_female": {"pmid": "16302247", "doi": "10.1002/ca.20252",
                                          "value": "relative CSA of rectus capitis posterior minor/major, multifidus, semispinalis cervicis/capitis, splenius capitis in 42 asymptomatic women (Elliott 2007, Clin Anat); level and side differences, no absolute values in the abstract"},
            "rectus_capitis_posterior_minor": {"pmid": "18174844", "doi": "10.1097/PHM.0b013e3181619766",
                                               "value": "CSA 56-97 mm2 per side (women with tension-type headache, Fernandez-de-las-Penas 2008)"},
            "longus": {"pmid": "37562443", "doi": "10.14245/ns.2346302.151", "value": "longus capitis + colli CSA measured together on axial T2 (Lin 2023, Neurospine); no absolute value in the abstract"},
            "cadaver_morphometry": {"pmid": "9654620", "doi": "10.1097/00007632-199806150-00005",
                                    "value": "muscle mass, fascicle length and PCSA of 14 neck muscles in 10 cadavers (Kamibayashi & Richmond 1998, Spine); PCSA 0.3-15.3 cm2 across muscles, per-muscle masses not in the abstract"},
            "volumes": "not compared: no per-muscle volumetric value verified from an abstract"},
        "montage": mpath, "output": a.out, "labels_file": a.labels_out, "mapping_file": a.mapping_out,
        "limits": ["boundaries are rules + watershed on 1 mm photographs, not traced fascia", "z registration residual 8.9 mm rms",
                   "splenius truncated at the T1 body top (its T1-T6 origin lies under the rhomboid / erector labels)",
                   "semispinalis cervicis truncated at the T1 body top (origin from T1-T6 transverse processes inside the erector columns)",
                   "the trapezius label is thin / absent at C1-C2: the 10 mm under the skin stands in for it there"],
    }
    json.dump(report, open(str(Path(a.out).with_suffix("").with_suffix("")) + "_report.json", "w"), indent=1)
    print("groups", [sorted(g) for g in groups]); print("merges", merges); print("erector overlap", report["erector_overlap_cm3"])
    print("DNECK_DONE")


if __name__ == "__main__":
    main()
