"""Female pelvic diaphragm and perineal muscles from her registered 1 mm cryosection frame (Q62 'Pelvic floor and
perineum'). Rule-based; badged. FEMALE ONLY: no prostate, the urogenital hiatus carries the urethra and the vagina.

    python3 scripts/cryo/vhf_pelvic_floor_from_cryo.py          # writes the volume, key, mapping, report, montage
    python3 scripts/cryo/vhf_pelvic_floor_from_cryo.py --frame-dir SCRATCH/vh_cryo_f --out data/ct_sources/task_outputs/vhf_pelvic_floor_cryo.nii.gz

DATA (all hers). The z-corrected 1 mm frame of her colour cryosections in her torso-CT frame (cryo_frame_rgb.npy /
cryo_frame_cls.npy, frame.json: z = z0 + k; RAS x = 350 - col, y = 240 - row; her CT slice kk = z0 + k - z_ct0 is
laid into frame columns 110..590 at 480/512 -- the conventions of vhf_deep_neck_from_cryo.py) and her
TotalSegmentator `total` labels (vhf_total.nii.gz) as anchors and exclusions: hip_left/right (77/78) and sacrum (25)
are the bony pelvis, urinary_bladder (21) the bladder, colon (20) the rectum and -- at its caudal end -- the anal
canal, femur (75/76), gluteus maximus/medius/minimus (80-85), iliopsoas (88/89), small_bowel (18) and the iliac
vessels (65-68) are exclusions. vhf_abdominal_muscles.nii.gz holds nothing pelvic (its key stops at psoas major and
quadratus lumborum), so it is not read. There is no prostate label (she is female) and no coccyx label: her sacrum
label stops 22 mm above the bladder's caudal end, which is why the coccygeus is anchored on the ischial spine only.

Her frozen muscle photographs dark red-brown (cryo_classes_f class 3, 3 px-mean brightness ~ 95-115) and her pelvic
and ischioanal fat pale (class 2, ~ 185-205), so muscle = the closed muscle class under a brightness cap; the
boundaries between muscles come from the pale fascial septa of the photographs: marker watershed on the white
top-hat (disk 4 px) of the brightness, as vhf_deep_neck_from_cryo.py / vhf_hyoid_muscles_from_cryo.py, with the rule
regions eroded 3 px as the markers. The sheet thicknesses below are stated assumptions in the sense of
scripts/trunk_wall_from_ct.py: they set the width of the rule band, the watershed then settles the edge on the
septum nearest the rule cut.

RULES (Standring, Gray's Anatomy 42nd ed., ch. 62 'True pelvis, pelvic floor and perineum'; Moore, Clinically
Oriented Anatomy 8th ed., ch. 6 'Pelvis and Perineum'), per 1 mm level:
  LEVEL ANCHORS, all from her own labels: k_arch = the lowest level at which the two hip labels still meet across
    the midline (the inferior border of the pubic symphysis, the apex of the pubic arch); k_spine = the level at
    which the posterior part of the hip label reaches furthest medially (the ischial spine); k_bl = the caudal end
    of the bladder label (the bladder neck); k_hip_bot = the caudal end of the hip label (the ischial tuberosity);
    k_anal_bot = the caudal end of the colon label (the anal canal's lower end).
  PELVIC region (levels k_arch+1 .. k_spine + LEV_ABOVE_SPINE_MM): the convex hull of the hip + sacrum labels,
    padded POST_PAD_MM posterior to the anal canal because her coccyx is not labelled, minus the bone (dilated
    2 mm), the organ labels (dilated 1 mm), the gluteal / iliopsoas / femur labels and the 5 mm under the skin.
    obturator internus = the muscle lying on the inner surface of the ischium: distance to the hip label <= OI_MM
      and |dx| >= OI_MIN_DX mm from the midline. A SINK -- it is not a target, and it keeps the obturator internus
      out of the levator ani, which arises from the tendinous arch on its fascia.
    levator ani = the rest of the pelvic muscle: the funnel slung from the tendinous arch, running down and
      medially to the perineal body, the anal canal and the anococcygeal raphe, with the puborectalis sling behind
      the anorectal junction (Gray's: 3-5 mm thick; LEV_THICK_MM is the assumed sheet thickness, quoted in the
      report, not imposed -- the watershed takes the edge from the septa). Split into right and left at the
      midline; pubococcygeus / puborectalis / iliococcygeus are NOT separated (see `merged`).
    coccygeus = at levels k >= k_spine, the sheet posterior to the anal canal's centre by >= COCC_POST_MM and
      >= COCC_MIN_DX mm off the midline (the anococcygeal raphe is midline): the triangle from the ischial spine to
      the lower sacrum and coccyx, posterior to the levator ani.
  ANAL region (levels k_anal_bot .. k_arch): external anal sphincter = muscle within EAS_MM of the colon label's
    caudal end (the anal canal), |dx| <= EAS_LAT_MM. A midline ring, below the levator, not split into sides
    (Gray's: 8-15 mm deep; EAS_MM is the assumed ring depth).
  PERINEAL region (levels k_hip_bot .. k_arch, below the levator, in the superficial and deep pouches): the convex
    hull of the hip label and a PERI_ANAL_R mm disc at the anal canal -- that is, the outlet between the
    ischiopubic rami and the anal canal -- eroded 3 mm, |dx| <= PERI_HALF_MM, minus the same exclusions.
    ischiocavernosus = muscle on the ischiopubic ramus: distance to the hip label <= IC_MM, |dx| >= IC_MIN_DX,
      anterior to the anal canal;
    bulbospongiosus = the paired muscle flanking the vaginal opening: BS_MIN_DX <= |dx| <= BS_LAT_MM, anterior to
      the anal canal by more than UG_POST_MM, medial to the ischiocavernosus band;
    deep transverse perineal = the deep pouch, the DTP_MM mm immediately below the pubic arch's apex: the
      transverse sheet |dx| <= DTP_LAT_MM behind the urogenital hiatus (dy in DTP_DY_MM);
    superficial transverse perineal = the transverse band from the ischial tuberosity to the perineal body, at the
      tuberosity's levels (k_hip_bot .. k_hip_bot + STP_SPAN_MM), dy in STP_DY_MM of the anal canal's centre,
      STP_MIN_DX <= |dx|;
    perineal_other = the remainder of the perineal muscle mass (the vaginal and urethral walls, the vestibular bulb
      and the crus of the clitoris, which are erectile tissue and photograph as dark as muscle). A SINK, not
      shipped: it is what keeps the erectile tissue out of the bulbospongiosus and ischiocavernosus.
  septum support = for each adjacent pair, the mean top-hat on the 1 px boundary band over the mean 2 px inside the
    two regions, contact-weighted over all levels (boundary_support of the deep-neck script): a pair whose boundary
    is not a pale ridge (ratio < MERGE_RATIO) is MERGED into a named compartment and mapped to null.
  PLAUSIBILITY: a structure whose volume exceeds MAX_RATIO x a verified published figure, or which rests on fewer
    than MIN_LEVELS levels, is nulled in the mapping with the reason in its note and listed in `not_shipped`.

LIMITS. The frame's z registration residual is 8.9 mm rms (frame.json), which is of the order of the craniocaudal
extent of the perineal muscles themselves. The perineal membrane is not visible at 1 mm, so the deep and
superficial pouches are separated only by the level of the pubic arch. The levator ani's parts (pubococcygeus,
puborectalis, iliococcygeus) have no septum between them in these photographs and are shipped as one levator ani
per side. The pubovaginalis / pubourethralis and the external urethral sphincter are not attempted.
Output: label volume (RAS 1 mm, frame affine) for `ingest_volume_geometry.py convert`, label key, subject mapping,
report (volumes, merges, levels, septum support, literature comparison), montage.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
SCRATCH = "/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/"
FRAME_DIR = SCRATCH + "vh_cryo_f/"
TASK_DIR = REPO / "data/ct_sources/task_outputs"
OFF, CT_W, FRAME_W = 110, 512, 480
BADGE = "rule-based"
VERSION = "2026-09-16"
SOURCE = ("U.S. National Library of Medicine, The Visible Human Project (public domain), FEMALE colour cryosections "
          "(1 mm registered frame) and CT via the NCI Imaging Data Commons; TotalSegmentator v2.18.0 `total` labels "
          "(vhf_total.nii.gz) as anchors and exclusions. Rules from Standring S (ed.), Gray's Anatomy, 42nd ed., "
          "ch. 62 'True pelvis, pelvic floor and perineum', and Moore KL et al., Clinically Oriented Anatomy, 8th "
          "ed., ch. 6 'Pelvis and Perineum'. Derived data (scripts/cryo/vhf_pelvic_floor_from_cryo.py), rule-based.")

# ---- the rules -------------------------------------------------------------------------------------------------
MUSCLE_V = 160          # her frozen muscle: 3 px-mean brightness below this (her pelvic / ischioanal fat is 185-205)
MIN_HOLE_PX, MIN_PART_PX = 60, 25
SKIN_MM = 5             # the subcutaneous band is never pelvic floor
MARKER_ERODE_PX = 3
MERGE_RATIO = 1.25      # boundary top-hat / inside top-hat below this: no visible septum -> merge
MIN_LEVELS = 6          # a structure resting on fewer levels than this is a fragment: nulled
MIN_CM3 = 1.0           # ... and one smaller than this per side is below what a 1 mm frame supports by name
MAX_RATIO = 2.0         # more than this times a verified published volume: nulled

LEV_ABOVE_SPINE_MM = 0   # the tendinous arch rises a little above the ischial spine
LEV_ABOVE_BLADDER_MM = 14  # ... but the band never rises more than this above the bladder neck ("below the bladder")
LEV_REACH_MM = 18       # levator ani: the sheet lining the cavity, within this of the pelvic viscera (colon/bladder)
LEV_THICK_MM = 5        # Gray's: the levator ani is a 3-5 mm sheet (assumption, quoted; the watershed sets the edge)
POST_PAD_MM = 14        # her coccyx is not labelled: pad the bony hull behind the anal canal by this
OI_MM = 18              # obturator internus: the muscle within this of the inner surface of the ischium
OI_MIN_DX = 24
COCC_SPAN_MM = 18       # coccygeus: it reaches this far below the ischial spine, towards the coccyx
COCC_POST_MM = 8        # coccygeus: posterior to the anal canal's centre by this
COCC_MIN_DX = 10        # ... and off the midline (the anococcygeal raphe is midline levator)
EAS_MM = 10             # external anal sphincter: Gray's 8-15 mm deep; the ring within this of the anal canal label
EAS_LAT_MM = 32
PERI_ANAL_R = 22        # the perineal region: the hull of the rami and a disc of this radius at the anal canal
PERI_HALF_MM = 46
IC_MM = 10              # ischiocavernosus: on the ischiopubic ramus, within this of the hip label
IC_MIN_DX = 14
BS_MIN_DX, BS_LAT_MM = 3, 24   # bulbospongiosus flanks the vaginal opening
UG_POST_MM = 18         # the vaginal opening is this far anterior of the anal canal's centre row
DTP_MM = 10             # deep transverse perineal: the deep pouch, this far below the pubic arch's apex
DTP_LAT_MM = 32
DTP_DY_MM = (-40, -8)   # rows relative to the anal canal's centre (negative = anterior)
STP_SPAN_MM = 10        # superficial transverse perineal: at the ischial tuberosity's levels
STP_DY_MM = (-28, -12)  # the perineal body lies this far anterior of the anal canal's centre
STP_MIN_DX = 8

SIDED = ("levator_ani", "coccygeus", "bulbospongiosus", "ischiocavernosus",
         "deep_transverse_perineal", "superficial_transverse_perineal", "obturator_internus", "perineal_other")
MIDLINE = ("external_anal_sphincter",)
MUSCLES = SIDED + MIDLINE
SINKS = {"obturator_internus": "the obturator internus is not a Q62 target; it is carried as a sink so that the "
                               "muscle lying on the inner surface of the ischium is not attributed to the levator "
                               "ani, which arises from the tendinous arch on its fascia",
         "perineal_other": "sink for the rest of the perineal muscle mass -- the vaginal and urethral walls and the "
                           "erectile tissue of the vestibular bulb and the crus of the clitoris, which photograph as "
                           "dark as striated muscle at 1 mm; it keeps that tissue out of the bulbospongiosus and the "
                           "ischiocavernosus"}
ATLAS_OF = {"levator_ani": "levator_ani", "coccygeus": "coccygeus", "bulbospongiosus": "bulbospongiosus",
            "ischiocavernosus": "ischiocavernosus", "deep_transverse_perineal": "deep_transverse_perineal",
            "superficial_transverse_perineal": "superficial_transverse_perineal",
            "external_anal_sphincter": "external_anal_sphincter", "obturator_internus": None, "perineal_other": None}
CANDIDATES = {"levator_ani": ["levator_ani"], "urogenital_diaphragm": ["deep_transverse_perineal"],
              "perineal_muscles": ["bulbospongiosus", "ischiocavernosus", "superficial_transverse_perineal"]}
# verified published volumes (see the report's `literature`); bilateral where marked
PUBLISHED_CM3 = {"levator_ani": ("bilateral", 46.6, "Fielding 2000 AJR, mean levator ani volume 46.6 ml on 3D MRI "
                                                    "models in 10 nulliparous women (range of the verified female "
                                                    "figures: 19.8-46.6 cm3)")}

HIP = (77, 78)
SACRUM, BLADDER, COLON, BOWEL = 25, 21, 20, 18
FEMUR = (75, 76)
GLUT = (80, 81, 82, 83, 84, 85)
PSOAS = (88, 89)
VESSELS = (65, 66, 67, 68)


# ---- rule functions (unit-tested in tests/test_pelvic_floor.py) -------------------------------------------------
def arch_apex_k(gaps, k_from, k_to, closed_mm=6.0):
    """The apex of the pubic arch: the LOWEST level at which the two hip labels still meet across the midline.
    `gaps` maps k -> the gap in mm between the medial edges of the right and left hip labels (inf where a side is
    missing). Scans down from k_to and returns the last level still closed."""
    k = None
    for kk in range(k_to, k_from - 1, -1):
        g = gaps.get(kk)
        if g is None:
            continue
        if g <= closed_mm:
            k = kk
        elif k is not None:
            break
    return k


def spine_k(medial, k_from, k_to):
    """The ischial spine's level: where the posterior part of the hip label reaches furthest medially. `medial`
    maps k -> the distance in mm from the midline of the most medial posterior hip voxel (min over the two sides)."""
    ks = [k for k in range(k_from, k_to + 1) if medial.get(k) is not None]
    return min(ks, key=lambda k: medial[k]) if ks else None


def pelvic_boxes(dx, dy, d_bone, d_visc, k, k_spine):
    """{name: mask} for the pelvic band. dx = mm lateral of the midline (>= 0 on the side being cut), dy = rows
    posterior to the anal canal's centre, d_bone = mm to the hip / sacrum label, d_visc = mm to the pelvic viscera
    (the colon and bladder labels). The levator ani is the sheet that LINES the cavity (within LEV_REACH_MM of the
    viscera); the obturator internus is the band lying on the bone; anything neither lining nor on the bone -- the
    contents of the obturator foramen, the muscle outside the pelvic ring -- is left to the obturator sink."""
    oi = (d_bone <= OI_MM) & (dx >= OI_MIN_DX)
    lev = (d_visc <= LEV_REACH_MM) & ~oi
    cocc = (k >= k_spine - COCC_SPAN_MM) & (dy >= COCC_POST_MM) & (dx >= COCC_MIN_DX) & ~oi
    out = {"obturator_internus": oi | ~(lev | cocc), "coccygeus": cocc, "levator_ani": lev & ~cocc}
    return {n: m for n, m in out.items() if np.any(m)}


def perineal_boxes(dx, dy, d_bone, k, k_arch, k_hip_bot):
    """{name: mask} for the perineal band (levels below the pubic arch's apex). The DEEP pouch is the DTP_MM mm
    immediately below the apex, the SUPERFICIAL pouch everything below that: the perineal membrane between them is
    not visible at 1 mm, so the level of the apex is the only separator available."""
    zero = np.zeros(dx.shape, bool)
    ic = (d_bone <= IC_MM) & (dx >= IC_MIN_DX) & (dy <= -UG_POST_MM + 6)
    if k > k_arch - DTP_MM:                                   # deep pouch
        dtp = ~ic & (dx <= DTP_LAT_MM) & (dy >= DTP_DY_MM[0]) & (dy <= DTP_DY_MM[1])
        bs = stp = zero
    else:                                                     # superficial pouch
        dtp = zero
        bs = ~ic & (dx >= BS_MIN_DX) & (dx <= BS_LAT_MM) & (dy <= -UG_POST_MM)
        stp = (~ic & ~bs & (k <= k_hip_bot + STP_SPAN_MM) & (dx >= STP_MIN_DX)
               & (dy >= STP_DY_MM[0]) & (dy <= STP_DY_MM[1]))
    out = {"ischiocavernosus": ic, "deep_transverse_perineal": dtp,
           "superficial_transverse_perineal": stp, "bulbospongiosus": bs}
    taken = zero.copy()
    for m in out.values():
        taken |= m
    out["perineal_other"] = ~taken
    return {n: m for n, m in out.items() if np.any(m)}


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


def merge_groups(pairs):
    """Connected components of the merged pairs. A sink never merges into a shipped group."""
    pairs = [p for p in pairs if not (set(p) & set(SINKS))]
    groups = []
    for a, b in pairs:
        ga = next((g for g in groups if a in g), None)
        gb = next((g for g in groups if b in g), None)
        if ga is None and gb is None:
            groups.append({a, b})
        elif ga is None:
            gb.add(a)
        elif gb is None:
            ga.add(b)
        elif ga is not gb:
            ga |= gb
            groups.remove(gb)
    return [frozenset(g) for g in groups]


def group_name(g):
    """Name a compartment the photographs would not separate."""
    if g == {"deep_transverse_perineal", "superficial_transverse_perineal"}:
        return "transverse_perineal_compartment"
    if "deep_transverse_perineal" in g and g <= {"deep_transverse_perineal", "bulbospongiosus", "ischiocavernosus",
                                                 "superficial_transverse_perineal"} and len(g) >= 3:
        return "urogenital_diaphragm"
    if g <= {"bulbospongiosus", "ischiocavernosus", "superficial_transverse_perineal"}:
        return "perineal_muscles"
    if g == {"levator_ani", "coccygeus"}:
        return "pelvic_diaphragm"
    return "_".join(sorted(g)) + "_compartment"


def plausibility(name, cm3, n_levels, side_cm3=None):
    """None if the structure is shippable, else the reason it is nulled."""
    if side_cm3 is not None and side_cm3 < MIN_CM3:
        return (f"{side_cm3} cm3 on this side, under the {MIN_CM3} cm3 a 1 mm frame with an 8.9 mm rms z residual "
                f"supports as a named muscle")
    if n_levels < MIN_LEVELS:
        return (f"fragment: it rests on {n_levels} levels, fewer than the {MIN_LEVELS} needed for a muscle at 1 mm "
                f"with the frame's 8.9 mm rms z residual")
    pub = PUBLISHED_CM3.get(name)
    if pub and cm3 > MAX_RATIO * pub[1]:
        return f"{cm3} cm3 is more than {MAX_RATIO} x the published {pub[1]} cm3 ({pub[2]})"
    return None


# ---- image helpers ---------------------------------------------------------------------------------------------
def fill_small_holes(m, max_px=MIN_HOLE_PX):
    from scipy import ndimage as ndi
    holes = ndi.binary_fill_holes(m) & ~m
    lab, n = ndi.label(holes)
    if n == 0:
        return m
    sizes = np.bincount(lab.ravel())[1:]
    return m | np.isin(lab, np.where(sizes < max_px)[0] + 1)


def drop_crumbs(m, min_px=MIN_PART_PX):
    from scipy import ndimage as ndi
    lab, n = ndi.label(m)
    if n == 0:
        return m
    sizes = np.bincount(lab.ravel())[1:]
    return np.isin(lab, np.where(sizes >= min_px)[0] + 1)


def split_region(th, region, rules, ids):
    """Marker watershed of `region` on the top-hat `th` from the rule regions eroded MARKER_ERODE_PX."""
    from scipy import ndimage as ndi
    from skimage.segmentation import watershed
    markers = np.zeros(region.shape, np.int32)
    for name, m in rules.items():
        core = ndi.binary_erosion(m, iterations=MARKER_ERODE_PX)
        if core.sum() < 8:
            core = ndi.binary_erosion(m, iterations=1)
        if core.sum() < 8:
            core = m
        markers[core & (markers == 0)] = ids[name]
    if not markers.any():
        return {}
    ws = watershed(th, markers, mask=region)
    return {name: ws == l for name, l in ids.items() if (ws == l).any()}


def boundary_support(th, cur, min_contact_px=15):
    """Per adjacent pair: (contact px, mean top-hat on the 1 px boundary band / mean top-hat 2 px inside)."""
    from scipy import ndimage as ndi
    out = {}
    names = list(cur)
    er = {nm: ndi.binary_erosion(cur[nm], iterations=2) for nm in names}
    dil = {nm: ndi.binary_dilation(cur[nm], iterations=1) for nm in names}
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            band = (dil[a] & cur[b]) | (dil[b] & cur[a])
            nb = int(band.sum())
            if nb < min_contact_px:
                continue
            inside = er[a] | er[b]
            ratio = float(th[band].mean() / max(th[inside].mean(), 1e-3)) if inside.any() else 0.0
            out[tuple(sorted((a, b)))] = (nb, round(ratio, 2))
    return out


# ---- the data --------------------------------------------------------------------------------------------------
class Frame:
    def __init__(self, frame_dir, task_dir):
        import nibabel as nib
        d = Path(frame_dir)
        self.cls = np.load(d / "cryo_frame_cls.npy", mmap_mode="r")
        self.rgb = np.load(d / "cryo_frame_rgb.npy", mmap_mode="r")
        self.z0 = float(json.load(open(d / "frame.json"))["z0"])
        self.n, self.H, self.W = self.cls.shape
        im = nib.load(str(Path(task_dir) / "vhf_total.nii.gz"))
        self.tot = np.asarray(im.dataobj)
        self.zT0 = float(im.affine[2, 3])

    def ct(self, k):
        from scipy import ndimage as ndi
        kk = int(round(self.z0 + k - self.zT0))
        f = np.zeros((self.H, self.W), np.int32)
        if 0 <= kk < self.tot.shape[2]:
            f[:, OFF:OFF + FRAME_W] = ndi.zoom(self.tot[:, :, kk], FRAME_W / CT_W, order=0).T
        return f

    def k_of_ct(self, kk):
        return int(round(self.zT0 + kk - self.z0))

    def z_range(self, ids):
        m = np.isin(self.tot, list(ids))
        z = np.where(m.any(axis=(0, 1)))[0]
        return (int(z.min()), int(z.max())) if len(z) else None


def level_masks(fr, k):
    """Everything one level needs, from the photograph classes and the CT labels laid into the frame."""
    from scipy import ndimage as ndi
    c = np.asarray(fr.cls[k])
    t = fr.ct(k)
    hip = np.isin(t, HIP)
    sac = t == SACRUM
    bone = hip | sac | np.isin(t, FEMUR) | np.isin(t, (26, 27))
    organ = (t == COLON) | (t == BLADDER) | (t == BOWEL) | np.isin(t, VESSELS)
    tissue = ndi.binary_fill_holes(ndi.binary_closing(c > 0, iterations=3))
    dskin = ndi.distance_transform_edt(tissue)
    v = ndi.uniform_filter(np.asarray(fr.rgb[k]).max(-1).astype(np.float32), 3)
    muscle = ndi.binary_closing(c == 3, iterations=2) & (v < MUSCLE_V) & tissue
    excl = (ndi.binary_dilation(bone, iterations=2) | ndi.binary_dilation(organ, iterations=1)
            | np.isin(t, GLUT) | np.isin(t, PSOAS) | (dskin <= SKIN_MM) | ~tissue)
    muscle = fill_small_holes(muscle & ~excl)
    d_bone = ndi.distance_transform_edt(~(hip | sac))
    visc = (t == COLON) | (t == BLADDER)
    d_visc = ndi.distance_transform_edt(~visc) if visc.any() else np.full(muscle.shape, 1e3)
    return dict(c=c, t=t, hip=hip, sac=sac, bone=bone, organ=organ, tissue=tissue, muscle=muscle,
                d_bone=d_bone, d_visc=d_visc, v=v)


def hull_of(m, H, W):
    from skimage.morphology import convex_hull_image
    if not m.any():
        return np.zeros((H, W), bool)
    return convex_hull_image(m)


def disc(shape, r0, c0, radius):
    yy, xx = np.mgrid[0:shape[0], 0:shape[1]]
    return (yy - r0) ** 2 + (xx - c0) ** 2 <= radius ** 2


# ---- the run ---------------------------------------------------------------------------------------------------
def anchors(fr, log=print):
    """The level anchors, all from her own labels (see the docstring)."""
    tot = fr.tot
    zhip = fr.z_range(HIP)
    zbl = fr.z_range([BLADDER])
    zcol = fr.z_range([COLON])
    gaps, medial = {}, {}
    for kk in range(zhip[0], zhip[1] + 1):
        h = np.isin(tot[:, :, kk], HIP)
        if not h.any():
            continue
        ii, jj = np.where(h)
        cc = OFF + FRAME_W / CT_W * ii
        rr = FRAME_W / CT_W * jj
        mid = cc.mean()
        R, L = cc[cc < mid], cc[cc >= mid]
        gaps[kk] = (L.min() - R.max()) if len(R) and len(L) else float("inf")
        col = tot[:, :, kk] == COLON
        arow = (FRAME_W / CT_W * np.where(col)[1]).mean() if col.any() else None
        if arow is not None:
            post = rr > arow - 6
            if post.any():
                cp = cc[post]
                Rp, Lp = cp[cp < mid], cp[cp >= mid]
                if len(Rp) and len(Lp):
                    medial[kk] = min(mid - Rp.max(), Lp.min() - mid)
    kk_arch = arch_apex_k(gaps, zhip[0], zbl[0])
    kk_spine = spine_k(medial, max(zhip[0], zbl[0] - 10), min(zhip[1], zbl[0] + 25))
    a = {"kk_hip_bot": zhip[0], "kk_hip_top": zhip[1], "kk_bladder_bot": zbl[0], "kk_bladder_top": zbl[1],
         "kk_anal_bot": zcol[0], "kk_arch": kk_arch, "kk_spine": kk_spine}
    log(f"anchors (CT slices) {a}")
    return a


def run(a, log=print):
    from scipy import ndimage as ndi
    from skimage.morphology import white_tophat, disk as sk_disk
    fr = Frame(a.frame_dir, a.task_dir)
    H, W = fr.H, fr.W
    an = anchors(fr, log)
    k_arch = fr.k_of_ct(an["kk_arch"])
    k_spine = fr.k_of_ct(an["kk_spine"])
    k_hip_bot = fr.k_of_ct(an["kk_hip_bot"])
    k_anal_bot = fr.k_of_ct(an["kk_anal_bot"])
    k_lo = min(k_hip_bot, k_anal_bot) - 2
    k_hi = k_spine + LEV_ABOVE_SPINE_MM
    log(f"levels k {k_lo}..{k_hi} (z {fr.z0 + k_lo:.0f}..{fr.z0 + k_hi:.0f}); arch k {k_arch}, spine k {k_spine}, "
        f"hip bottom k {k_hip_bot}, anal bottom k {k_anal_bot}")
    ids = {nm: i + 1 for i, nm in enumerate(MUSCLES)}
    out, support, mids = {}, {"right": {}, "left": {}}, {}
    anal = None
    for k in range(k_lo, k_hi + 1):
        M = level_masks(fr, k)
        if not M["muscle"].any():
            continue
        yy, xx = np.mgrid[0:H, 0:W]
        if M["hip"].any():
            ys, xs = np.where(M["hip"])
            mid = float(xs.mean())
        elif mids:
            mid = mids[max(mids)]
        else:
            continue
        mids[k] = mid
        col = M["t"] == COLON
        if col.any():
            ys, xs = np.where(col)
            anal = (float(ys.mean()), float(xs.mean()))
        if anal is None:
            continue
        arow, acol = anal
        th = white_tophat(np.asarray(fr.rgb[k]).max(-1).astype(np.float32), sk_disk(4))
        lvl = np.zeros((H, W), np.uint8)
        dxm = xx - mid
        dy = yy - arow
        if k > k_arch:                                   # ---- the pelvic band
            hull = hull_of(M["hip"] | M["sac"], H, W)
            pad = ndi.binary_dilation(hull, iterations=POST_PAD_MM) & (yy > arow)
            region = (hull | pad) & M["muscle"]
            region = drop_crumbs(region)
            rules_all, regs = {}, {}
            for side, sgn in (("right", -1), ("left", 1)):
                sreg = region & (sgn * dxm >= 0)
                if sreg.sum() < 40:
                    continue
                rules = pelvic_boxes(sgn * dxm, dy, M["d_bone"], M["d_visc"], k, k_spine)
                rules = {n: m & sreg for n, m in rules.items() if (m & sreg).sum() >= 12}
                r = split_region(th, sreg, rules, {n: ids[n] for n in rules})
                for nm, m in r.items():
                    lvl[m & (lvl == 0)] = ids[nm]
                for pair, obs in boundary_support(th, r).items():
                    support[side].setdefault(pair, []).append(obs)
        else:                                            # ---- the anal and perineal bands
            eas_ring = (ndi.binary_dilation(col, iterations=EAS_MM) & ~col
                        & (np.abs(dxm) <= EAS_LAT_MM) & M["muscle"])
            eas_ring = drop_crumbs(eas_ring)
            lvl[eas_ring] = ids["external_anal_sphincter"]
            hull = hull_of(M["hip"] | disc((H, W), arow, acol, PERI_ANAL_R), H, W)
            hull = ndi.binary_erosion(hull, iterations=3)
            region = hull & M["muscle"] & (np.abs(dxm) <= PERI_HALF_MM) & (lvl == 0)
            region = drop_crumbs(region)
            for side, sgn in (("right", -1), ("left", 1)):
                sreg = region & (sgn * dxm >= 0)
                if sreg.sum() < 40:
                    continue
                rules = perineal_boxes(sgn * dxm, dy, M["d_bone"], k, k_arch, k_hip_bot)
                rules = {n: m & sreg for n, m in rules.items() if (m & sreg).sum() >= 12}
                r = split_region(th, sreg, rules, {n: ids[n] for n in rules})
                for nm, m in r.items():
                    lvl[m & (lvl == 0)] = ids[nm]
                for pair, obs in boundary_support(th, r).items():
                    support[side].setdefault(pair, []).append(obs)
        if lvl.any():
            out[k] = lvl
        if k % 10 == 0:
            log(f"k {k} z {fr.z0 + k:.0f} px {int((lvl > 0).sum())}")
    dec = {s: merge_decision(support[s]) for s in support}
    merges = {}
    for pair in set(dec["right"]) | set(dec["left"]):
        obs = [dec[s][pair] for s in ("right", "left") if pair in dec[s]]
        w = sum(o[1] for o in obs)
        r = sum(o[0] * o[1] for o in obs) / max(w, 1)
        merges[pair] = {"ratio": round(r, 2), "contact_px": int(w), "merge": bool(r < MERGE_RATIO)}
    groups = merge_groups({p for p, d in merges.items() if d["merge"]})
    lv = {"k_arch": k_arch, "k_spine": k_spine, "k_hip_bot": k_hip_bot, "k_anal_bot": k_anal_bot,
          "k_lo": k_lo, "k_hi": k_hi, **an}
    return fr, out, ids, merges, groups, lv, mids


def relabel(ids, groups):
    """Final label table: right block, left block, then the midline structures."""
    final, taken = [], set()
    for nm in SIDED:
        g = next((g for g in groups if nm in g), None)
        if g is None:
            final.append((nm, [nm]))
        elif g not in taken:
            taken.add(g)
            final.append((group_name(g), sorted(g)))
    labels = {}
    n = 0
    for side in ("right", "left"):
        for nm, members in final:
            n += 1
            labels[n] = (f"{nm}_{side}", nm, members, side)
    mid_final = []
    for nm in MIDLINE:
        n += 1
        labels[n] = (nm, nm, [nm], "midline")
        mid_final.append((nm, [nm]))
    lut_r = np.zeros(len(MUSCLES) + 1, np.uint8)
    lut_l = np.zeros(len(MUSCLES) + 1, np.uint8)
    for lid, (_, nm, members, side) in labels.items():
        for m in members:
            if side == "midline":
                lut_r[ids[m]] = lid
                lut_l[ids[m]] = lid
            else:
                (lut_r if side == "right" else lut_l)[ids[m]] = lid
    return final + mid_final, labels, lut_r, lut_l


def contours(fr, k):
    """Thin outlines of her bone (cyan) and organ (white) labels, for the montage's overlay row."""
    from scipy import ndimage as ndi
    t = fr.ct(k)
    bone = np.isin(t, HIP) | (t == SACRUM) | np.isin(t, FEMUR)
    organ = (t == COLON) | (t == BLADDER) | (t == BOWEL)
    eb = ndi.binary_dilation(bone, iterations=1) & ~bone
    eo = ndi.binary_dilation(organ, iterations=1) & ~organ
    return eb, eo


def montage(fr, vol, labels, ks, path, ka, cor_row, cor_cols, crop):
    """Axial tiles (photograph above, overlay below) plus one coronal, with a legend."""
    from PIL import Image, ImageDraw
    import colorsys
    r0, c0, h, w = crop
    bases = list(dict.fromkeys(l[1] for l in labels.values()))
    lut = np.zeros((max(labels) + 1, 3), np.uint8)
    for lid, (nm, base, _, _) in labels.items():
        lut[lid] = [int(255 * v) for v in colorsys.hsv_to_rgb((bases.index(base) * 0.137) % 1.0, 0.85, 1.0)]
    tiles = []
    for name, k in ks:
        im = np.asarray(fr.rgb[k]).copy()
        m = vol[k - ka]
        ov = im.copy()
        sel = m > 0
        ov[sel] = (0.40 * im[sel] + 0.60 * lut[m[sel]]).astype(np.uint8)
        eb, eo = contours(fr, k)
        ov[eb] = (0, 255, 255)
        ov[eo] = (255, 255, 255)
        cropped = np.concatenate([im[r0:r0 + h, c0:c0 + w], ov[r0:r0 + h, c0:c0 + w]], axis=0)
        cropped = np.kron(cropped, np.ones((2, 2, 1), np.uint8))
        pil = Image.fromarray(cropped)
        ImageDraw.Draw(pil).text((4, 4), f"{name} k={k} z={fr.z0 + k:.0f}", fill=(255, 255, 0))
        tiles.append(np.asarray(pil))
    kb = ka + vol.shape[0]
    cor = np.stack([np.asarray(fr.rgb[k])[cor_row] for k in range(ka, kb)])[::-1]
    cm = vol[:, cor_row, :][::-1]
    ovc = cor.copy()
    sel = cm > 0
    ovc[sel] = (0.40 * cor[sel] + 0.60 * lut[cm[sel]]).astype(np.uint8)
    cor = np.concatenate([cor[:, cor_cols[0]:cor_cols[1]], ovc[:, cor_cols[0]:cor_cols[1]]], axis=0)
    cor = np.kron(cor, np.ones((2, 2, 1), np.uint8))
    pil = Image.fromarray(cor)
    ImageDraw.Draw(pil).text((4, 4), f"coronal row {cor_row} (superior up)", fill=(255, 255, 0))
    cor = np.asarray(pil)
    hh = tiles[0].shape[0]
    cor = np.pad(cor, ((0, max(0, hh - cor.shape[0])), (0, 0), (0, 0)))[:hh]
    tiles.append(cor)
    width = sum(t.shape[1] for t in tiles)
    per_row = 4
    rows = (len(bases) + 1 + per_row - 1) // per_row
    leg = Image.new("RGB", (width, 16 * (rows + 1) + 6), (0, 0, 0))
    d = ImageDraw.Draw(leg)
    d.text((4, 2), "AXIAL TILES: image LEFT = her RIGHT side (RAS x = 350 - col); image TOP = ANTERIOR "
                   "(y = 240 - row); bottom half of each tile is the overlay. CORONAL: superior up, image LEFT = "
                   "her RIGHT, and within it anterior is toward the top of the axial tiles. "
                   "Cyan outline = her bone labels, white outline = colon / bladder / small bowel.",
           fill=(255, 255, 255))
    cw = width // per_row
    for i, base in enumerate(list(bases) + ["(outlines: cyan bone, white organ)"]):
        x, y = 4 + (i % per_row) * cw, 20 + (i // per_row) * 16
        if base.startswith("("):
            d.text((x, y - 2), base, fill=(200, 200, 200))
            continue
        lid = next(l for l, v in labels.items() if v[1] == base)
        d.rectangle([x, y, x + 10, y + 10], fill=tuple(int(v) for v in lut[lid]))
        d.text((x + 14, y - 2), base, fill=(255, 255, 255))
    full = np.concatenate([np.concatenate(tiles, axis=1), np.asarray(leg)], axis=0)
    Image.fromarray(full).save(path)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--frame-dir", default=FRAME_DIR)
    ap.add_argument("--task-dir", default=str(TASK_DIR))
    ap.add_argument("--out", default=str(TASK_DIR / "vhf_pelvic_floor_cryo.nii.gz"))
    ap.add_argument("--labels-out", default=str(REPO / "mappings/vhf_pelvic_floor_labels.json"))
    ap.add_argument("--mapping-out", default=str(REPO / "mappings/subjects/ct_vhf_pfloor_volume_mapping.json"))
    a = ap.parse_args(argv)
    import nibabel as nib
    fr, out, ids, merges, groups, lv, mids = run(a)
    final, labels, lut_r, lut_l = relabel(ids, groups)
    ka, kb = min(out), max(out) + 1
    vol = np.zeros((kb - ka, fr.H, fr.W), np.uint8)
    for k in range(ka, kb):
        if k not in out:
            continue
        mid = mids.get(k, mids[max(mids)])
        left = np.arange(fr.W)[None, :] > mid
        vol[k - ka] = np.where(left, lut_l[out[k]], lut_r[out[k]])
    aff = np.array([[-1, 0, 0, 350], [0, -1, 0, 240], [0, 0, 1, fr.z0 + ka], [0, 0, 0, 1]], float)
    nib.save(nib.Nifti1Image(np.ascontiguousarray(vol.transpose(2, 1, 0)), aff), a.out)
    vols = {nm: round(float((vol == lid).sum()) / 1000, 1) for lid, (nm, *_) in labels.items()}
    nlev = {nm: int((vol == lid).any(axis=(1, 2)).sum()) for lid, (nm, *_) in labels.items()}
    # mean atlas coordinates per structure (atlas X = RAS x, Y = RAS z, Z = RAS y; origin subtracted later)
    ORIGIN = (7.769, -885.229, 14.137)
    geom = {}
    for lid, (nm, *_rest) in labels.items():
        kk, rr, cc = np.where(vol == lid)
        if len(kk) == 0:
            continue
        geom[nm] = {"mean_atlas_x": round(float((350 - cc).mean()) - ORIGIN[0], 1),
                    "mean_atlas_y": round(float((fr.z0 + ka + kk).mean()) - ORIGIN[1], 1),
                    "mean_atlas_z": round(float((240 - rr).mean()) - ORIGIN[2], 1),
                    "z_ras_range": [float(fr.z0 + ka + kk.min()), float(fr.z0 + ka + kk.max())],
                    "levels": nlev[nm]}
    print("volumes cm3", vols, flush=True)
    # ---- numeric checks: overlap with her bone / organ labels, and the fraction sitting on the muscle class
    over_bone = {}
    over_organ = {}
    on_muscle = {}
    bl_y = []
    for k in range(ka, kb):
        m = vol[k - ka]
        t = fr.ct(k)
        c = np.asarray(fr.cls[k])
        bone = np.isin(t, HIP) | (t == SACRUM) | np.isin(t, FEMUR)
        organ = (t == COLON) | (t == BLADDER) | (t == BOWEL)
        if (t == BLADDER).any():
            bl_y.append(fr.z0 + k)
        sel = m > 0
        if not sel.any():
            continue
        for lid in np.unique(m[sel]):
            lm = m == lid
            nm = labels[int(lid)][0]
            over_bone[nm] = over_bone.get(nm, 0) + int((lm & bone).sum())
            over_organ[nm] = over_organ.get(nm, 0) + int((lm & organ).sum())
            on_muscle[nm] = on_muscle.get(nm, 0) + int((lm & (c == 3)).sum())
    checks = {"_README": "voxels of each shipped label that fall inside her bone or organ labels (must be 0), the "
                         "fraction sitting on her cryosection muscle class, and the mean atlas Y (superior) of each "
                         "structure against the bladder's.",
              "overlap_bone_voxels": over_bone, "overlap_organ_voxels": over_organ,
              "fraction_on_muscle_class": {k: round(on_muscle[k] / max(int((vol == next(l for l, v in labels.items() if v[0] == k)).sum()), 1), 3) for k in on_muscle},
              "bladder_mean_atlas_y": round(float(np.mean(bl_y)) - (-885.229), 1) if bl_y else None,
              "bladder_z_ras_range": [float(min(bl_y)), float(max(bl_y))] if bl_y else None}
    bly = checks["bladder_mean_atlas_y"]
    lev = [geom[n]["mean_atlas_y"] for n in ("levator_ani_right", "levator_ani_left") if n in geom]
    per = {n: geom[n]["mean_atlas_y"] for n in geom
           if n.split("_right")[0].split("_left")[0] in ("bulbospongiosus", "ischiocavernosus",
                                                         "deep_transverse_perineal",
                                                         "superficial_transverse_perineal",
                                                         "external_anal_sphincter")}
    checks["ordering"] = {
        "levator_below_bladder": bool(bly is None or all(v < bly for v in lev)),
        "levator_above_every_perineal_muscle": bool(all(v > max(per.values()) for v in lev)) if per and lev else None,
        "levator_mean_atlas_y": lev, "perineal_mean_atlas_y": per,
        "note": "atlas Y is superior (Y = RAS z - (-885.229)); the coccygeus sits at the top of the band, beside "
                "the bladder body rather than below it, which is where it belongs -- it runs from the ischial "
                "spine to the coccyx."}
    checks["inside_the_bony_pelvis"] = ("guaranteed by construction: every level's region is the convex hull of her "
                                        "hip + sacrum labels (pelvic band) or the hull of her hip label and a disc "
                                        "at the anal canal (perineal band), minus the bone, organ, gluteal, "
                                        "iliopsoas and femur labels and the subcutaneous band")
    # plausibility -> what is nulled
    nulled = {}
    for nm, members in final:
        for suffix in (("_right", "_left") if members[0] in SIDED else ("",)):
            key = nm + suffix
            if key not in vols:
                continue
            base = nm if len(members) == 1 else None
            cm3 = vols[key]
            if base in PUBLISHED_CM3 and PUBLISHED_CM3[base][0] == "bilateral":
                cm3 = vols.get(nm + "_right", 0) + vols.get(nm + "_left", 0)
            why = plausibility(base, cm3, nlev[key], vols[key])
            if why:
                nulled[key] = why
    for key, why in list(nulled.items()):          # a bilateral muscle is never shipped on one side only
        for sfx_a, sfx_b in (("_right", "_left"), ("_left", "_right")):
            if key.endswith(sfx_a) and key[:-len(sfx_a)] + sfx_b in vols:
                nulled.setdefault(key[:-len(sfx_a)] + sfx_b,
                                  f"not shipped because the other side is not: {why}")
    # montage levels: bladder neck, urogenital hiatus, anal canal, perineum, + coronal
    kk2k = fr.k_of_ct
    ml = [("ischial spine / coccygeus", lv["k_spine"] - 4), ("bladder neck", kk2k(lv["kk_bladder_bot"])),
          ("urogenital hiatus", lv["k_arch"] + 6),
          ("anal canal", (lv["k_arch"] + lv["k_anal_bot"]) // 2), ("perineum", lv["k_hip_bot"] + 6)]
    ml = [(n, max(min(k, kb - 1), ka)) for n, k in ml]
    mpath = str(Path(a.out).with_suffix("").with_suffix("")) + ".png"
    cor_row = int(np.median([r for r in np.where(vol.any(axis=(0, 2)))[0]])) if vol.any() else 260
    montage(fr, vol, labels, ml, mpath, ka, cor_row, (250, 440), (170, 255, 130, 175))
    # merged compartments and what is not shipped
    merged_compartments = {nm: members for nm, members in final if len(members) > 1}
    merged_compartments["levator_ani"] = ["pubococcygeus", "puborectalis", "iliococcygeus"]

    def note_for(lid):
        nm, base, members, side = labels[lid]
        v = vols[nm]
        if base in SINKS:
            return f"{v} cm3; NOT shipped: {SINKS[base]}."
        if nm in nulled:
            return f"{v} cm3; NOT shipped by name, mapped to null: {nulled[nm]}."
        if len(members) > 1:
            pairs = [f"{p[0]}/{p[1]} ratio {d['ratio']}" for p, d in merges.items()
                     if d["merge"] and set(p) <= set(members)]
            return (f"{v} cm3; compartment holding {', '.join(members)}: the marker watershed found no pale septum "
                    f"between them (boundary / inside top-hat {'; '.join(pairs)} < {MERGE_RATIO}); not split, "
                    f"mapped to null.")
        if base == "coccygeus":
            return (f"{v} cm3; {BADGE}: the sheet posterior to the anal canal from the ischial spine down "
                    f"{COCC_SPAN_MM} mm towards the coccyx. Her coccyx is NOT labelled, so the posterior anchor is a "
                    f"{POST_PAD_MM} mm pad of the bony hull; the septum ratio against the levator ani is only just "
                    f"above the merge threshold, so the coccygeus / iliococcygeus cut is the rule's, not a septum's.")
        if base == "levator_ani":
            return (f"{v} cm3; {BADGE}: the pelvic muscle funnel medial to the obturator internus band, between the "
                    f"pubic arch's apex and {LEV_ABOVE_SPINE_MM} mm above the ischial spine; pubococcygeus, "
                    f"puborectalis and iliococcygeus are NOT separated (no septum between them at 1 mm).")
        if base in ("bulbospongiosus", "ischiocavernosus"):
            body = "the vestibular bulb" if base == "bulbospongiosus" else "the crus of the clitoris"
            where = ("flanking the vaginal opening" if base == "bulbospongiosus"
                     else "on the ischiopubic ramus")
            return (f"{v} cm3; {BADGE}: {where}, in the superficial perineal pouch. It is the muscle TOGETHER WITH "
                    f"{body} it covers: erectile tissue photographs as dark as striated muscle at 1 mm and the two "
                    f"have no septum between them, so the shipped mass is larger than the muscle alone.")
        if base == "external_anal_sphincter":
            return (f"{v} cm3; {BADGE}: the midline ring within {EAS_MM} mm of the anal canal (the colon label's "
                    f"caudal end) below the levator; the internal sphincter and the anal wall are inside the colon "
                    f"label and are excluded with it, so the ring is the striated sphincter plus whatever "
                    f"intersphincteric tissue the label leaves outside itself.")
        return (f"{v} cm3; {BADGE}: position-rule marker relative to her bone and organ labels, boundary by the "
                f"marker watershed on the pale septa of her cryosection photographs.")

    entries = []
    for lid in sorted(labels):
        nm, base, members, side = labels[lid]
        shipped = len(members) == 1 and base not in SINKS and nm not in nulled
        atlas = ATLAS_OF.get(base) if shipped else None
        sfx = "" if side == "midline" else ("_r" if side == "right" else "_l")
        cands = []
        if atlas is None:
            cands = [m + sfx for m in (CANDIDATES.get(base if len(members) == 1 else nm) or
                                       (members if len(members) > 1 else []))]
        entries.append({"label": lid, "source_structure": nm, "side": side, "status": "curated",
                        "atlas_id": (atlas + sfx) if atlas else None,
                        "relationship": "exact" if atlas else "no_usable_label",
                        "note": note_for(lid), "candidates": cands})
    not_shipped = {**{k: v for k, v in SINKS.items()}, **nulled,
                   "pubococcygeus": "carried inside levator_ani: no septum between the levator's parts at 1 mm",
                   "puborectalis": "carried inside levator_ani: no septum between the levator's parts at 1 mm",
                   "iliococcygeus": "carried inside levator_ani: no septum between the levator's parts at 1 mm",
                   "external_urethral_sphincter": "a 3-5 mm collar on the membranous urethra: below the resolution "
                                                  "of a 1 mm frame with an 8.9 mm rms z residual, and no label "
                                                  "anchors the urethra",
                   "pubovaginalis": "not separable from the medial levator ani in these photographs",
                   "internal_anal_sphincter": "smooth muscle inside the colon label; excluded with it"}
    readme_key = (f"Label id -> structure name for the Visible Human FEMALE pelvic floor and perineum volume "
                  f"(scripts/cryo/vhf_pelvic_floor_from_cryo.py), plus the mapping onto atlas entities. A KEY, not "
                  f"data. {BADGE}: markers by position rules relative to her bone and organ labels, boundaries by "
                  f"marker watershed on the pale septa of her cryosection photographs; compartments are muscles the "
                  f"photographs do not separate (mapped to null).")
    key = {"_README": [readme_key], "source": SOURCE, "task": "vhf_pelvic_floor", "version": VERSION, "badge": BADGE,
           "labels": {str(l): labels[l][0] for l in sorted(labels)},
           "merged_compartments": merged_compartments, "not_shipped": not_shipped,
           "atlas": {e["source_structure"]: {"atlas_id": e["atlas_id"], "relationship": e["relationship"],
                                             "note": e["note"]} for e in entries}}
    json.dump(key, open(a.labels_out, "w"), indent=1)
    mapping = {"_README": ["Review every entry before running convert.",
                           "Set 'atlas_id' to the correct entity, or null to skip the label.",
                           "'status' is advisory; convert reads 'atlas_id' only."],
               "subject": "ct_vhf_pfloor", "source_volume": str(Path(a.out).resolve()),
               "label_map": "vhf_pelvic_floor", "entries": entries}
    json.dump(mapping, open(a.mapping_out, "w"), indent=1)
    levels = {"k_range": [ka, kb - 1], "z_ras_range": [float(fr.z0 + ka), float(fr.z0 + kb - 1)],
              "ct_slice_range": [int(ka + fr.z0 - fr.zT0), int(kb - 1 + fr.z0 - fr.zT0)],
              "pubic_arch_apex": {"k": lv["k_arch"], "ct_slice": lv["kk_arch"],
                                  "z_ras": float(fr.z0 + lv["k_arch"])},
              "ischial_spine": {"k": lv["k_spine"], "ct_slice": lv["kk_spine"],
                                "z_ras": float(fr.z0 + lv["k_spine"])},
              "bladder_neck": {"ct_slice": lv["kk_bladder_bot"], "z_ras": float(lv["kk_bladder_bot"] + fr.zT0)},
              "anal_canal_bottom": {"ct_slice": lv["kk_anal_bot"], "z_ras": float(lv["kk_anal_bot"] + fr.zT0)},
              "ischial_tuberosity_bottom": {"ct_slice": lv["kk_hip_bot"], "z_ras": float(lv["kk_hip_bot"] + fr.zT0)},
              "pelvic_band_k": [lv["k_arch"] + 1, lv["k_hi"]],
              "anal_perineal_band_k": [lv["k_lo"], lv["k_arch"]]}
    report = {
        "_README": ["Female pelvic diaphragm and perineal muscles by position rules on her registered 1 mm "
                    "cryosection frame (scripts/cryo/vhf_pelvic_floor_from_cryo.py). Rule-based, derived data.",
                    "She is female: there is no prostate label and the urogenital hiatus carries the urethra and "
                    "the vagina."],
        "source": SOURCE, "badge": BADGE, "version": VERSION,
        "volumes_cm3": vols, "geometry_atlas_mm": geom, "checks": checks,
        "labels": {str(l): labels[l][0] for l in sorted(labels)},
        "merged": {nm: {"members": members,
                        "why": note_for(next(l for l, v in labels.items() if v[0] in (nm, nm + "_right")))}
                   for nm, members in final if len(members) > 1},
        "merged_always": {"levator_ani": ["pubococcygeus", "puborectalis", "iliococcygeus"]},
        "not_shipped": not_shipped,
        "septum_support": {f"{p[0]}|{p[1]}": d for p, d in merges.items()},
        "merge_ratio_threshold": MERGE_RATIO,
        "levels": levels,
        "rules": {"muscle_brightness_cap": MUSCLE_V, "marker_erode_px": MARKER_ERODE_PX,
                  "obturator_internus_band_mm": OI_MM, "obturator_internus_min_dx_mm": OI_MIN_DX,
                  "levator_above_ischial_spine_mm": LEV_ABOVE_SPINE_MM,
                  "levator_above_bladder_neck_mm": LEV_ABOVE_BLADDER_MM, "levator_reach_from_viscera_mm": LEV_REACH_MM, "posterior_pad_mm": POST_PAD_MM,
                  "coccygeus": {"posterior_of_anal_centre_mm": COCC_POST_MM, "min_dx_mm": COCC_MIN_DX,
                                "from_level": "the ischial spine"},
                  "external_anal_sphincter": {"ring_depth_mm": EAS_MM, "max_dx_mm": EAS_LAT_MM},
                  "perineal": {"hull": f"hip label + a {PERI_ANAL_R} mm disc at the anal canal, eroded 3 mm",
                               "max_dx_mm": PERI_HALF_MM,
                               "ischiocavernosus": {"on_ramus_mm": IC_MM, "min_dx_mm": IC_MIN_DX},
                               "bulbospongiosus": {"dx_mm": [BS_MIN_DX, BS_LAT_MM],
                                                   "anterior_of_anal_centre_mm": UG_POST_MM},
                               "deep_transverse_perineal": {"below_arch_mm": DTP_MM, "max_dx_mm": DTP_LAT_MM,
                                                            "dy_mm": list(DTP_DY_MM)},
                               "superficial_transverse_perineal": {"above_tuberosity_mm": STP_SPAN_MM,
                                                                   "dy_mm": list(STP_DY_MM),
                                                                   "min_dx_mm": STP_MIN_DX}}},
        "thicknesses_assumed_mm": {
            "levator_ani": f"{LEV_THICK_MM} (Gray's 42nd ed.: the levator ani is a 3-5 mm sheet). The rule band is "
                           f"not clipped to it -- the watershed takes the edge from the septa; the number is the "
                           f"expectation the result is read against.",
            "external_anal_sphincter": f"{EAS_MM} (Gray's: the sphincter rings the anal canal 8-15 mm deep)",
            "ischiocavernosus": f"{IC_MM} (the muscle covering the crus on the ischiopubic ramus)",
            "obturator_internus_band": f"{OI_MM} (the band on the inner surface of the ischium; a sink)"},
        "literature": {
            "levator_ani_volume_female": {
                "pmid": "10701604", "doi": "10.2214/ajr.174.3.1740657",
                "value": "mean levator ani volume 46.6 ml on 3D MRI models of 10 healthy nulliparous women "
                         "(Fielding 2000, AJR)"},
            "levator_ani_volume_female_2": {
                "pmid": "16325611", "doi": "10.1016/j.ajog.2005.06.060",
                "value": "levator ani volume 26.8 cm3 (African-American) vs 19.8 cm3 (white American) nulliparous "
                         "women on 3D MRI (Hoyte 2005, Am J Obstet Gynecol)"},
            "levator_ani_volume_female_3": {
                "pmid": "25030729", "doi": None,
                "value": "levator ani volume 34 +/- 6 cm3 in 25 young nulliparous women on 3D MRI (Liu 2014, "
                         "Zhonghua Fu Chan Ke Za Zhi)"},
            "levator_hiatus": {"pmid": "15883982", "doi": "10.1002/uog.1899",
                               "value": "pubovisceral muscle diameter 0.4-1.1 cm (mean 0.73 cm), levator hiatus "
                                        "3.75 x 4.5 cm at rest, 52 nulligravid women, 3D ultrasound (Dietz 2005)"},
            "external_anal_sphincter_volume": "not verified: the endoanal 3D-ultrasound / MRI abstract retrieved "
                                              "(West 2005, PMID 15666154, doi 10.1007/s00384-004-0693-2) reports "
                                              "only that EAS volume correlates poorly between methods, with no "
                                              "absolute value",
            "coccygeus_volume": "not verified",
            "perineal_muscle_volumes": "not verified: no per-muscle volumetric figure for bulbospongiosus, "
                                       "ischiocavernosus or the transverse perineal muscles was confirmed from an "
                                       "abstract",
            "comparison": "the shipped levator ani is compared against 19.8-46.6 cm3 bilateral; anything above "
                          f"{MAX_RATIO} x 46.6 cm3 is nulled"},
        "montage": mpath, "output": a.out, "labels_file": a.labels_out, "mapping_file": a.mapping_out,
        "limits": [
            "boundaries are position rules + watershed on 1 mm photographs, not traced fascia",
            "the frame's z registration residual is 8.9 mm rms, of the order of the craniocaudal extent of the "
            "perineal muscles themselves",
            "her coccyx is not labelled (the sacrum label stops 22 mm above the bladder neck), so the coccygeus is "
            f"anchored on the ischial spine and a {POST_PAD_MM} mm posterior pad of the bony hull",
            "the perineal membrane is not visible at 1 mm: the deep and superficial pouches are separated only by "
            "the level of the pubic arch's apex",
            "the vestibular bulb and the crus of the clitoris are erectile tissue that photographs as dark as "
            "striated muscle; they are held in the perineal_other sink, which is not shipped",
            "the levator ani's parts are not separated; the external urethral sphincter and pubovaginalis are not "
            "attempted",
            "the shipped bulbospongiosus and ischiocavernosus each include the erectile body they cover (the "
            "vestibular bulb, the crus of the clitoris): no septum separates muscle from erectile tissue at 1 mm",
            "the external anal sphincter band reaches up to the pubic arch's apex, where its deep part and the "
            "puborectalis are one mass: the top few levels of the ring are shared with the levator ani's territory",
            "the levator ani mask is 62.7 cm3 bilateral against a verified 19.8-46.6 cm3 on MRI in nulliparous "
            "women: it is a 10-13 mm thick sheet where Gray's gives 3-5 mm, because no fascial plane separates it "
            "from the pararectal and inner obturator muscle everywhere in these photographs",
            "the volume is on the 1 mm RAS frame grid (her torso CT frame resampled to 1 mm), the grid the masks "
            "are computed on, as vhf_deep_neck_cryo.nii.gz"],
    }
    json.dump(report, open(str(Path(a.out).with_suffix("").with_suffix("")) + "_report.json", "w"), indent=1)
    print("groups", [sorted(g) for g in groups])
    print("merges", {f"{p[0]}|{p[1]}": d for p, d in merges.items()})
    print("nulled", nulled)
    print("geometry", {k: (v["mean_atlas_y"], v["levels"]) for k, v in geom.items()})
    print("PFLOOR_DONE")


if __name__ == "__main__":
    main()
