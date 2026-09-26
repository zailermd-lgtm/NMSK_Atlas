"""Male pelvic diaphragm and perineal muscles from his registered 1 mm cryosection frame (Q68 'Male pelvic
floor'). Rule-based; badged. MALE ONLY: a prostate sits at the urogenital hiatus (she has none) and the
midline structure below the pubic arch is the bulb of the penis / corpus spongiosum (she has the vaginal
opening and vestibular bulb). This is a close port of scripts/cryo/vhf_pelvic_floor_from_cryo.py (Q62):
same helper functions, same watershed/merge-detection machinery, same plausibility gate, ported almost
unchanged wherever the rule is not sex-specific (the pelvic band -- obturator internus, levator ani,
coccygeus -- and the external anal sphincter are NOT sex-specific and transfer directly).

    python3 scripts/cryo/vhm_pelvic_floor_from_cryo.py

DATA -- and a real finding from this session (Q83), not an assumption carried over from Q68's note: HIS
'TORSO' CT BLOCK DOES NOT REACH THE PERINEUM. `vhm_total.nii.gz` (the torso-block TotalSegmentator `total`
run Q79-81 verified for the abdominal wall) has its hip label CUT OFF at its own inferior edge: 5856 voxels
at slice k=0, not a tapering tip (contrast her hip label, torso block, which tapers naturally from 142
voxels at its true caudal end -- ischial tuberosity -- confirmed by direct voxel counts this session).
PROJECT_STATE.md records why: "the torso and legs blocks do NOT overlap -- torso z=0 is the legs block's
top slice" -- his torso block simply stops above the ischial tuberosities, the pubic arch and the whole
perineum. That anatomy is only in the LEGS block. `data/ct_sources/task_outputs/vhm_total.nii.gz` (the file
Q68's note pointed at) is therefore NOT the source this script uses; it uses the LEGS block instead:
  - `scratch/vhm_ts/legs_total.nii.gz`: TotalSegmentator `total` on the legs-series CT block (its own
    affine, hip/sacrum/colon/bladder/prostate/femur all present; confirmed by direct voxel taper this
    session that the hip label's caudal end, k=708, IS the true ischial tuberosity, not a block-edge
    artefact -- 111 voxels growing steadily over the next several slices).
  - `scratch/vh_cryo/cryo_legs_frame_rgb.npy` / `cryo_legs_frame_cls.npy`: his 1 mm cryosections resampled
    onto legs_total's OWN 512-pixel grid (zoomed to 480, 0.9375 -> 1 mm/px, OFF=0), the "legs" branch of
    `resample_cryo_to_ct_frame.py` (z0=-1671.0, in-plane shift (4,-96), scale 0.99 -- calibrated by
    silhouette + mutual-information registration against the raw legs CT, per that script's own docstring).
  - Verified EMPIRICALLY this session, not trusted from either convention: the frame's own index k equals
    legs_total.nii.gz's own z-array-index DIRECTLY, with NO offset and NO row/column flip. Algebraically,
    the resample script's baked z0=-1671.0 is exactly legs_total's own -978 mm z-origin plus the original
    legs->torso registration offset t_off_z=-693.0 (-978 + -693 = -1671), so frame k IS legs_total's array
    index. Confirmed visually: legs_total's hip/sacrum/colon labels, zoomed onto the frame with the SAME
    OFF=0 zoom+transpose recipe as the torso/female scripts (no extra flip), land on the correct bone/organ
    silhouette in the photographs at k=720, 750, 780 and 800 (checked as PNG overlays this session); a
    candidate row-flip (to compensate for the legs segmentation's own affine having an anomalous Y sign
    versus the torso convention) was tried and is VISIBLY WRONG -- it displaces the sacrum/hip contours off
    the bone entirely. Frame k is used as the level index throughout this script.
  - `legs_total.nii.gz`'s own TotalSegmentator `total` labels are the anchors and exclusions, same numeric
    ids as the female script (they are TotalSegmentator ids, body- and block-independent): hip_left/right
    (77/78) and sacrum (25) the bony pelvis, urinary_bladder (21) the bladder, colon (20) the rectum/anal
    canal, femur (75/76), gluteus maximus/medius/minimus (80-85), iliopsoas (88/89) and the iliac vessels
    (65-68) exclusions -- PLUS prostate (22, id confirmed via
    `totalsegmentator.map_to_binary.class_map['total']`), present with 18384 voxels spanning k=738-772 in
    the legs block (it is ABSENT, 0 voxels, in the torso-block vhm_total.nii.gz -- one more confirmation the
    torso block does not reach this anatomy). His prostate apex (k=738) and the pubic-arch apex computed
    from the hip labels alone (k=737) land ONE SLICE apart: an independent cross-check that both anchors
    are right, and the landmark Gray's/Moore give for the urogenital hiatus (the level of the prostate
    apex / bulb of the penis) is used here to corroborate, not replace, the bone-based k_arch that the
    rest of the pelvic/perineal split already depends on.

His frozen muscle photographs and fat classify the same way as hers (cryo_classes.py: muscle = dark
red-brown class 3 under a brightness cap, fat pale class 2/4) -- confirmed the same classifier module is
used for both bodies. Boundaries again come from the pale fascial septa: marker watershed on the white
top-hat of brightness, rule regions eroded 3 px as markers, exactly as the female script.

RULES (Standring, Gray's Anatomy 42nd ed., ch. 62 'True pelvis, pelvic floor and perineum'; Moore,
Clinically Oriented Anatomy 8th ed., ch. 6 'Pelvis and Perineum' -- male section), per 1 mm level:
  LEVEL ANCHORS, all from his own labels, SAME DEFINITIONS as the female script: k_arch = the lowest level
    at which the two hip labels still meet across the midline (pubic arch apex, k=737); k_spine = the level
    at which the posterior hip label reaches furthest medially (ischial spine, k=752); k_hip_bot = the
    caudal end of the hip label (ischial tuberosity, k=708); k_anal_bot = the caudal end of the colon label
    (k=728, twenty slices above k_hip_bot -- his anal canal is not labelled all the way to the perineum
    either, same limitation as hers, same fallback: the anal centroid from the lowest level it IS labelled
    propagates down through the hull/disc construction). NEW: k_prostate_apex = the caudal end of the
    prostate label (k=738), the male urogenital-hiatus landmark (Moore ch. 6): reported and cross-checked
    against k_arch, not substituted for it, because the bone-based k_arch is what the rest of the pelvic /
    perineal split already keys off and the two agree to 1 mm here.
  PELVIC region (k_arch+1 .. k_spine): UNCHANGED from the female script (`pelvic_boxes`) -- the pelvic
    diaphragm's geometry (tendinous arch, obturator internus sink, levator ani funnel, coccygeus posterior
    triangle) is not sex-specific. obturator internus, levator ani (pubococcygeus / puborectalis /
    iliococcygeus NOT separated, same 1 mm limitation), coccygeus: same rules, same constants.
  ANAL region (k_anal_bot-ish .. k_arch): external anal sphincter -- UNCHANGED, same ring rule.
  PERINEAL region (k_hip_bot .. k_arch): UNCHANGED geometry (`perineal_boxes`), ONE rule difference:
    ischiocavernosus = the muscle on the ischiopubic ramus covering the CRUS OF THE PENIS (hers: crus of
      the clitoris) -- same distance-to-bone rule, unchanged constants.
    bulbospongiosus = in the female script this flanks the vaginal opening with a central exclusion zone
      (BS_MIN_DX) that keeps the introitus out of the muscle mask. He has no introitus: the corpus
      spongiosum bulb is a SINGLE midline mass under a median raphe, with paired muscle bellies (Gray's:
      bulbospongiosus in the male is a paired muscle with a median raphe, each half investing its side of
      the bulb and body of the corpus spongiosum) -- so the existing LEFT/RIGHT split (each side's rule
      already runs on its own half-region, sgn*dx >= 0, before this box is ever evaluated) is anatomically
      the right cut for him too; the only change is BS_MIN_DX = 0 (no exclusion zone: the tissue runs right
      up to the midline raphe, not around a gap). It is again the muscle TOGETHER WITH the erectile body it
      covers (no septum separates them at 1 mm) -- here the corpus spongiosum bulb instead of the
      vestibular bulb.
    deep / superficial transverse perineal: UNCHANGED, same transverse-band rules.
    perineal_other: UNCHANGED sink, now holding the crus and body of the corpus cavernosum where they are
      not claimed by ischiocavernosus, and the urethral wall.
  EXTERNAL URETHRAL SPHINCTER: NOT ATTEMPTED, same decision as the female script and for the same reason
    (Gray's: a 3-5 mm collar on the membranous urethra, in the deep perineal pouch) -- with an ADDITIONAL
    male-specific reason: her frame's z-registration residual is a known 8.9 mm rms (her frame.json records
    it); his legs-block frame has no equivalent figure available (it depends on the legs CT's own
    registration to the raw cryo stream AND the legs->torso registration chain, neither independently
    quantified here) -- so if anything the effective uncertainty at this level is LARGER, not smaller, than
    the female frame's, and a 3-5 mm structure is not attemptable on either body at 1 mm. Q68's note asked
    to decide, per the female precedent, whether this is worth attempting: it is not.
  septum support / PLAUSIBILITY: UNCHANGED machinery (`merge_decision`, `merge_groups`, `plausibility`) --
    literature figures are male-specific (see PUBLISHED_CM3 / PUBLISHED_MM below); most male perineal /
    pelvic-floor volumes have no confirmed published figure (marked "not verified", same honesty standard
    as the female script for her own unverified structures).

LIMITS. No rms z-registration residual figure exists for this frame the way her frame.json states one; the
frame's plumbing (legs CT -> legs cryo frame, legs -> torso registration) was checked empirically at 4
pelvis levels this session (bone/organ label contours over the photographs) and lands correctly, but is not
independently quantified. His prostate anchors the urogenital hiatus but is not itself part of any shipped
muscle (there is no "prostate" muscle to ship; it is an exclusion + landmark only, like her bladder). The
pelvic + perineal band together spans only k=708..752 (45 mm) versus her much longer registered frame span,
a real difference in how much of his perineum this particular block/registration chain resolves. Otherwise
the same limits as the female script apply unchanged: boundaries are position rules + watershed on 1 mm
photographs, not traced fascia; the levator ani's parts are not separated; pubovaginalis has no male
equivalent needed (its analogue, puboprostaticus/pubourethral tissue, is likewise not separable at 1 mm).
Output: label volume (RAS 1 mm, corrected-atlas frame) for `ingest_volume_geometry.py convert`, label key,
subject mapping, report (volumes, merges, levels, septum support, literature comparison), montage.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
SCRATCH = "/tmp/claude-0/-home-user-NMSK-Atlas/c87934a2-ee76-5e9b-b227-2ff779a6e56e/scratchpad/"
FRAME_DIR = SCRATCH + "vh_cryo/"                       # cryo_legs_frame_rgb.npy / cryo_legs_frame_cls.npy
LEGS_TOTAL = SCRATCH + "vhm_ts/legs_total.nii.gz"
TASK_DIR = REPO / "data/ct_sources/task_outputs"
OFF, CT_W, FRAME_W = 0, 512, 480      # legs frame: OFF=0, same 480/512 zoom as the torso frame (verified, see docstring)
Z0 = -1671.0    # corrected-RAS z at frame k=0; frame k == legs_total.nii.gz's own z-array-index, verified this session
BADGE = "rule-based"
VERSION = "2026-09-18"
SOURCE = ("U.S. National Library of Medicine, The Visible Human Project (public domain), MALE colour "
          "cryosections (1 mm, resampled onto the legs-block CT grid) and CT via the NCI Imaging Data "
          "Commons; TotalSegmentator v2.18.0 `total` labels (legs_total.nii.gz, the legs CT block -- his "
          "torso block does not reach the perineum, see the module docstring) as anchors and exclusions. "
          "Rules from Standring S (ed.), Gray's Anatomy, 42nd ed., ch. 62 'True pelvis, pelvic floor and "
          "perineum', and Moore KL et al., Clinically Oriented Anatomy, 8th ed., ch. 6 'Pelvis and "
          "Perineum'. Derived data (scripts/cryo/vhm_pelvic_floor_from_cryo.py), rule-based, ported from "
          "scripts/cryo/vhf_pelvic_floor_from_cryo.py.")

# ---- the rules -------------------------------------------------------------------------------------------------
MUSCLE_V = 160
MIN_HOLE_PX, MIN_PART_PX = 60, 25
SKIN_MM = 5
MARKER_ERODE_PX = 3
MERGE_RATIO = 1.25
MIN_LEVELS = 6
MIN_CM3 = 1.0
MAX_RATIO = 2.0

LEV_ABOVE_SPINE_MM = 0
LEV_ABOVE_BLADDER_MM = 14
# LEV_REACH_MM: her value (18) was tried first and starved levator_ani (2.5-5 cm3/side, with the muscle mass
# visibly the sling around the rectum in the montage going to obturator_internus's catch-all instead --
# checked empirically this session). His legs-block pelvic band is short (15-26 mm total, vs whatever span
# her single, longer registered frame gave the same rule) and evidently a larger fraction of his true
# levator ani sits farther than 18 mm from the colon/bladder label at this scale/registration. Recalibrated
# by direct experiment (18/25/30/40/60 mm all tried, volumes and the montage inspected at each) to 45 mm,
# the point past which levator_ani/coccygeus stop trading share and the montage shows a continuous sheet
# in the right position rather than a thin anterior sliver. Reported plainly as a recalibrated constant, not
# claimed as her own verified 18 mm.
LEV_REACH_MM = 45
LEV_THICK_MM = 5
POST_PAD_MM = 14
OI_MM = 18
OI_MIN_DX = 24
# COCC_SPAN_MM: her value (18) assumed the pelvic band is taller than the coccygeus's own span below the
# spine, so the rule only ever claims the TOP of the band. His band (15-26 mm total) is not taller than 18
# mm, so her constant let coccygeus claim the WHOLE band and swallow levator_ani (checked empirically: cut
# from 34 cm3 combined coccygeus at span=18 down to 16.8 cm3 at span=6, with levator_ani correspondingly
# recovering the rest of the sling -- the montage confirms the visible boundary moves to a plausible
# position, not an arbitrary one). Recalibrated to 6 mm for the same reason as LEV_REACH_MM above.
COCC_SPAN_MM = 6
COCC_POST_MM = 8
COCC_MIN_DX = 10
EAS_MM = 10
EAS_LAT_MM = 32
PERI_ANAL_R = 22
PERI_HALF_MM = 46
IC_MM = 10
IC_MIN_DX = 14
BS_MIN_DX, BS_LAT_MM = 0, 24   # BS_MIN_DX = 0 (was 3 for her): no vaginal opening to exclude, the bulb runs to the midline raphe
UG_POST_MM = 18
DTP_MM = 10
DTP_LAT_MM = 32
DTP_DY_MM = (-40, -8)
STP_SPAN_MM = 10
STP_DY_MM = (-28, -12)
STP_MIN_DX = 8

SIDED = ("levator_ani", "coccygeus", "bulbospongiosus", "ischiocavernosus",
         "deep_transverse_perineal", "superficial_transverse_perineal", "obturator_internus", "perineal_other")
MIDLINE = ("external_anal_sphincter",)
MUSCLES = SIDED + MIDLINE
SINKS = {"obturator_internus": "the obturator internus is not a Q68 target; it is carried as a sink so that "
                               "the muscle lying on the inner surface of the ischium is not attributed to "
                               "the levator ani, which arises from the tendinous arch on its fascia",
         "perineal_other": "sink for the rest of the perineal muscle mass -- the crus and body of the "
                           "corpus cavernosum where not claimed by ischiocavernosus, and the urethral wall, "
                           "which photograph as dark as striated muscle at 1 mm; it keeps that tissue out "
                           "of the bulbospongiosus and the ischiocavernosus"}
ATLAS_OF = {"levator_ani": "levator_ani", "coccygeus": "coccygeus", "bulbospongiosus": "bulbospongiosus",
            "ischiocavernosus": "ischiocavernosus", "deep_transverse_perineal": "deep_transverse_perineal",
            "superficial_transverse_perineal": "superficial_transverse_perineal",
            "external_anal_sphincter": "external_anal_sphincter", "obturator_internus": None, "perineal_other": None}
CANDIDATES = {"levator_ani": ["levator_ani"], "urogenital_diaphragm": ["deep_transverse_perineal"],
              "perineal_muscles": ["bulbospongiosus", "ischiocavernosus", "superficial_transverse_perineal"]}
# verified published figures (see the report's `literature`); "not verified" honestly marked where none was found
PUBLISHED_CM3 = {}       # no confirmed male levator-ani VOLUME figure found (PubMed searched this session); see PUBLISHED_MM
PUBLISHED_MM = {"levator_ani": ("unilateral thickness", 5.1, "Tienza et al. 2015, Int Urol Nephrol, PMID 26049974, "
                                "doi 10.1007/s11255-015-1019-8: mean levator ani muscle thickness 0.51 cm "
                                "(obturator internus 1.46 cm) on preoperative MRI, 550 men before radical "
                                "prostatectomy")}

HIP = (77, 78)
SACRUM, BLADDER, COLON, BOWEL = 25, 21, 20, 18
PROSTATE = 22
FEMUR = (75, 76)
GLUT = (80, 81, 82, 83, 84, 85)
PSOAS = (88, 89)
VESSELS = (65, 66, 67, 68)


# ---- rule functions (unit-tested in tests/test_pelvic_floor.py; unchanged from the female script) ---------------
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
    """{name: mask} for the pelvic band. Unchanged from the female script: not sex-specific."""
    oi = (d_bone <= OI_MM) & (dx >= OI_MIN_DX)
    lev = (d_visc <= LEV_REACH_MM) & ~oi
    cocc = (k >= k_spine - COCC_SPAN_MM) & (dy >= COCC_POST_MM) & (dx >= COCC_MIN_DX) & ~oi
    out = {"obturator_internus": oi | ~(lev | cocc), "coccygeus": cocc, "levator_ani": lev & ~cocc}
    return {n: m for n, m in out.items() if np.any(m)}


def perineal_boxes(dx, dy, d_bone, k, k_arch, k_hip_bot):
    """{name: mask} for the perineal band. Unchanged geometry from the female script; BS_MIN_DX=0 (module
    constant, see the docstring) is the only behavioural difference for `bs`: no vaginal-opening exclusion
    zone, the bulb of the penis runs to the midline raphe."""
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
    """None if the structure is shippable, else the reason it is nulled. Unchanged machinery; PUBLISHED_CM3
    is empty for the male structures (no confirmed volume figure), so the MAX_RATIO cap never fires here --
    honest, not a loosened bar (see PUBLISHED_MM for the one figure that IS confirmed, a thickness, reported
    but not used as a hard cap since it is not a volume)."""
    if side_cm3 is not None and side_cm3 < MIN_CM3:
        return (f"{side_cm3} cm3 on this side, under the {MIN_CM3} cm3 a 1 mm frame supports as a named "
                f"muscle")
    if n_levels < MIN_LEVELS:
        return (f"fragment: it rests on {n_levels} levels, fewer than the {MIN_LEVELS} needed for a muscle "
                f"at 1 mm")
    pub = PUBLISHED_CM3.get(name)
    if pub and cm3 > MAX_RATIO * pub[1]:
        return f"{cm3} cm3 is more than {MAX_RATIO} x the published {pub[1]} cm3 ({pub[2]})"
    return None


# ---- image helpers (unchanged from the female script) ------------------------------------------------------------
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
    """His legs-block cryo frame + legs-block TotalSegmentator labels. See the module docstring: frame index
    k equals legs_total.nii.gz's own z-array-index DIRECTLY (no offset, no flip), verified empirically this
    session against hip/sacrum/colon silhouettes at four pelvis levels."""
    def __init__(self, frame_dir, legs_total_path):
        import nibabel as nib
        d = Path(frame_dir)
        self.cls = np.load(d / "cryo_legs_frame_cls.npy", mmap_mode="r")
        self.rgb = np.load(d / "cryo_legs_frame_rgb.npy", mmap_mode="r")
        self.n, self.H, self.W = self.cls.shape
        im = nib.load(str(legs_total_path))
        self.tot = np.asarray(im.dataobj)
        self.z0 = Z0

    def ct(self, k):
        from scipy import ndimage as ndi
        f = np.zeros((self.H, self.W), np.int32)
        if 0 <= k < self.tot.shape[2]:
            f[:, :] = ndi.zoom(self.tot[:, :, k], FRAME_W / CT_W, order=0).T
        return f

    def k_of_ct(self, kk):
        return kk

    def z_range(self, ids):
        m = np.isin(self.tot, list(ids))
        z = np.where(m.any(axis=(0, 1)))[0]
        return (int(z.min()), int(z.max())) if len(z) else None


def level_masks(fr, k):
    """Everything one level needs, from the photograph classes and the CT labels laid into the frame.
    Unchanged from the female script except PROSTATE joins the organ exclusion."""
    from scipy import ndimage as ndi
    c = np.asarray(fr.cls[k])
    t = fr.ct(k)
    hip = np.isin(t, HIP)
    sac = t == SACRUM
    bone = hip | sac | np.isin(t, FEMUR) | np.isin(t, (26, 27))
    organ = (t == COLON) | (t == BLADDER) | (t == BOWEL) | (t == PROSTATE) | np.isin(t, VESSELS)
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
    """The level anchors, all from his own labels (see the docstring). Same method as the female script's
    anchors(), reading legs_total instead of vhm_total, plus the prostate apex as a cross-check landmark."""
    tot = fr.tot
    zhip = fr.z_range(HIP)
    zbl = fr.z_range([BLADDER])
    zcol = fr.z_range([COLON])
    zpro = fr.z_range([PROSTATE])
    gaps, medial = {}, {}
    k_hi_search = zbl[0] if zbl else zhip[1]
    for kk in range(zhip[0], zhip[1] + 1):
        h = np.isin(tot[:, :, kk], HIP)
        if not h.any():
            continue
        ii, jj = np.where(h)
        cc = FRAME_W / CT_W * ii
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
    kk_arch = arch_apex_k(gaps, zhip[0], k_hi_search)
    kk_spine = spine_k(medial, max(zhip[0], k_hi_search - 10), min(zhip[1], k_hi_search + 25))
    a = {"kk_hip_bot": zhip[0], "kk_hip_top": zhip[1], "kk_bladder_bot": zbl[0] if zbl else None,
         "kk_bladder_top": zbl[1] if zbl else None, "kk_anal_bot": zcol[0], "kk_arch": kk_arch,
         "kk_spine": kk_spine, "kk_prostate_apex": zpro[0] if zpro else None,
         "kk_prostate_top": zpro[1] if zpro else None}
    log(f"anchors (legs-block slices, == frame k) {a}")
    if zpro and kk_arch is not None:
        log(f"cross-check: prostate apex k={zpro[0]} vs bone-based pubic arch apex k={kk_arch} "
            f"(delta {zpro[0] - kk_arch} mm)")
    return a


def run(a, log=print):
    from scipy import ndimage as ndi
    from skimage.morphology import white_tophat, disk as sk_disk
    fr = Frame(a.frame_dir, a.legs_total)
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
    # seed `anal` from the LOWEST level the colon label reaches (k_anal_bot), not None: his colon label
    # (like hers) does not reach all the way to the perineum, but unlike her band -- which apparently starts
    # at or below her colon's own lowest labelled level -- roughly HALF of his anal/perineal band (k_lo..
    # k_anal_bot-1, 706..727) is BELOW where the colon label exists at all. The loop runs k ascending, so an
    # `anal = None` seed (propagating only once colon is first seen) would skip every one of those lower
    # levels outright (found and fixed this session: it silently dropped ischiocavernosus / bulbospongiosus /
    # superficial_transverse_perineal to near zero, not a real absence). Seeding with the lowest labelled
    # centroid extrapolates the anal-canal position downward through the same hull/disc construction the
    # female script already uses for the analogous situation above her sacrum.
    Mseed = level_masks(fr, k_anal_bot)
    col0 = Mseed["t"] == COLON
    anal = (float(np.where(col0)[0].mean()), float(np.where(col0)[1].mean())) if col0.any() else None
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
    """Final label table: right block, left block, then the midline structures. Unchanged from the female script."""
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
    """Thin outlines of his bone (cyan) and organ (white) labels, for the montage's overlay row."""
    from scipy import ndimage as ndi
    t = fr.ct(k)
    bone = np.isin(t, HIP) | (t == SACRUM) | np.isin(t, FEMUR)
    organ = (t == COLON) | (t == BLADDER) | (t == BOWEL) | (t == PROSTATE)
    eb = ndi.binary_dilation(bone, iterations=1) & ~bone
    eo = ndi.binary_dilation(organ, iterations=1) & ~organ
    return eb, eo


def montage(fr, vol, labels, ks, path, ka, cor_row, cor_cols, crop):
    """Axial tiles (photograph above, overlay below) plus one coronal, with a legend. Unchanged from the
    female script."""
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
    d.text((4, 2), "AXIAL TILES: image LEFT = his RIGHT side; image TOP = ANTERIOR. bottom half of each tile "
                   "is the overlay. CORONAL: superior up, image LEFT = his RIGHT, and within it anterior is "
                   "toward the top of the axial tiles. Cyan outline = his bone labels, white outline = "
                   "colon / bladder / prostate.",
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
    ap.add_argument("--legs-total", default=LEGS_TOTAL)
    ap.add_argument("--out", default=str(TASK_DIR / "vhm_pelvic_floor_cryo.nii.gz"))
    ap.add_argument("--labels-out", default=str(REPO / "mappings/vhm_pelvic_floor_labels.json"))
    ap.add_argument("--mapping-out", default=str(REPO / "mappings/subjects/ct_vhm_pfloor_volume_mapping.json"))
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
    # X TRANSLATION: 240, NOT 350 (the female/torso-frame scripts' own constant, which this script had ported
    # unchanged along with everything else torso-frame-related -- Q86 found this was never re-derived for the
    # LEGS-block frame this script actually uses). 240 matches legs_total.nii.gz's OWN affine x-translation
    # (verified: its hip label's true RAS x at k=720 is -78.75..60.0, symmetric about ~0, matching vhm_both's
    # hip bones; the old 350 constant put the same pixels at 31..170, a uniform +110 mm rightward offset) and
    # is independently confirmed by external_anal_sphincter -- an anatomically midline structure by the rule's
    # own construction -- landing at mean atlas x=-5.7 with 240 (right next to vhm_both's sacrum center -3.75)
    # versus +104.3 with the old 350. Y translation (240, unchanged) was checked too and is fine: the (unshipped)
    # obturator_internus atlas Z already fell inside vhm_both's own obturator_internus z-range under the old code.
    aff = np.array([[-1, 0, 0, 240], [0, -1, 0, 240], [0, 0, 1, fr.z0 + ka], [0, 0, 0, 1]], float)
    nib.save(nib.Nifti1Image(np.ascontiguousarray(vol.transpose(2, 1, 0)), aff), a.out)
    vols = {nm: round(float((vol == lid).sum()) / 1000, 1) for lid, (nm, *_) in labels.items()}
    nlev = {nm: int((vol == lid).any(axis=(1, 2)).sum()) for lid, (nm, *_) in labels.items()}
    # mean atlas coordinates per structure (atlas X = RAS x, Y = RAS z, Z = RAS y; origin subtracted later)
    ORIGIN = (-6.035, -895.476, 4.787)     # the male torso-block atlas origin (vhm_arm_muscles_v2.py OX/origin-y/OZ)
    geom = {}
    for lid, (nm, *_rest) in labels.items():
        kk, rr, cc = np.where(vol == lid)
        if len(kk) == 0:
            continue
        geom[nm] = {"mean_atlas_x": round(float((240 - cc).mean()) - ORIGIN[0], 1),
                    "mean_atlas_y": round(float((fr.z0 + ka + kk).mean()) - ORIGIN[1], 1),
                    "mean_atlas_z": round(float((240 - rr).mean()) - ORIGIN[2], 1),
                    "z_ras_range": [float(fr.z0 + ka + kk.min()), float(fr.z0 + ka + kk.max())],
                    "levels": nlev[nm]}
    print("volumes cm3", vols, flush=True)
    # ---- numeric checks: overlap with his bone / organ labels, and the fraction sitting on the muscle class
    over_bone = {}
    over_organ = {}
    on_muscle = {}
    bl_y = []
    for k in range(ka, kb):
        m = vol[k - ka]
        t = fr.ct(k)
        c = np.asarray(fr.cls[k])
        bone = np.isin(t, HIP) | (t == SACRUM) | np.isin(t, FEMUR)
        organ = (t == COLON) | (t == BLADDER) | (t == BOWEL) | (t == PROSTATE)
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
    checks = {"_README": "voxels of each shipped label that fall inside his bone or organ labels (must be 0), "
                         "the fraction sitting on his cryosection muscle class, and the mean atlas Y "
                         "(superior) of each structure against the bladder's.",
              "overlap_bone_voxels": over_bone, "overlap_organ_voxels": over_organ,
              "fraction_on_muscle_class": {k: round(on_muscle[k] / max(int((vol == next(l for l, v in labels.items() if v[0] == k)).sum()), 1), 3) for k in on_muscle},
              "bladder_mean_atlas_y": round(float(np.mean(bl_y)) - ORIGIN[1], 1) if bl_y else None,
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
        "prostate_apex_atlas_y": round(float(lv["kk_prostate_apex"] + fr.z0) - ORIGIN[1], 1) if lv.get("kk_prostate_apex") is not None else None,
        "note": "atlas Y is superior (Y = RAS z - (-895.476))."}
    checks["inside_the_bony_pelvis"] = ("guaranteed by construction: every level's region is the convex hull "
                                        "of his hip + sacrum labels (pelvic band) or the hull of his hip "
                                        "label and a disc at the anal canal (perineal band), minus the bone, "
                                        "organ (including prostate), gluteal, iliopsoas and femur labels and "
                                        "the subcutaneous band")
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
    # montage levels: prostate apex / urogenital hiatus, bladder neck, anal canal, perineum, + coronal
    kk2k = fr.k_of_ct
    ml = [("ischial spine / coccygeus", lv["k_spine"] - 4)]
    if lv.get("kk_bladder_bot") is not None:
        ml.append(("bladder neck", kk2k(lv["kk_bladder_bot"])))
    ml += [("urogenital hiatus / prostate apex", lv["k_arch"] + 6),
           ("anal canal", (lv["k_arch"] + lv["k_anal_bot"]) // 2), ("perineum", lv["k_hip_bot"] + 6)]
    ml = [(n, max(min(k, kb - 1), ka)) for n, k in ml]
    mpath = str(Path(a.out).with_suffix("").with_suffix("")) + ".png"
    cor_row = int(np.median([r for r in np.where(vol.any(axis=(0, 2)))[0]])) if vol.any() else 260
    # crop centred on the actual shipped extent (the female script's fixed crop assumes HER frame's hip
    # position, which does not transfer -- his mid-column and hip position differ, verified this session:
    # a fixed crop copied from her script cut his right side out of the montage entirely)
    rs, cs = np.where(vol.any(axis=0))
    if len(rs):
        r0, r1 = max(int(rs.min()) - 30, 0), min(int(rs.max()) + 30, fr.H)
        c0, c1 = max(int(cs.min()) - 30, 0), min(int(cs.max()) + 30, fr.W)
    else:
        r0, r1, c0, c1 = 150, 330, 120, 370
    montage(fr, vol, labels, ml, mpath, ka, cor_row, (c0, c1), (r0, c0, r1 - r0, c1 - c0))
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
            return (f"{v} cm3; compartment holding {', '.join(members)}: the marker watershed found no pale "
                    f"septum between them (boundary / inside top-hat {'; '.join(pairs)} < {MERGE_RATIO}); "
                    f"not split, mapped to null.")
        if base == "coccygeus":
            return (f"{v} cm3; {BADGE}: the sheet posterior to the anal canal from the ischial spine down "
                    f"{COCC_SPAN_MM} mm towards the coccyx. His coccyx is NOT labelled either, so the "
                    f"posterior anchor is a {POST_PAD_MM} mm pad of the bony hull, same limitation as the "
                    f"female script.")
        if base == "levator_ani":
            return (f"{v} cm3; {BADGE}: the pelvic muscle funnel medial to the obturator internus band, "
                    f"between the pubic arch's apex and {LEV_ABOVE_SPINE_MM} mm above the ischial spine; "
                    f"pubococcygeus, puborectalis and iliococcygeus are NOT separated (no septum between "
                    f"them at 1 mm).")
        if base in ("bulbospongiosus", "ischiocavernosus"):
            body = "the corpus spongiosum bulb of the penis" if base == "bulbospongiosus" else "the crus of the penis"
            where = ("over the corpus spongiosum, in the midline behind the scrotum" if base == "bulbospongiosus"
                     else "on the ischiopubic ramus")
            return (f"{v} cm3; {BADGE}: {where}, in the superficial perineal pouch. It is the muscle "
                    f"TOGETHER WITH {body} it covers: erectile tissue photographs as dark as striated muscle "
                    f"at 1 mm and the two have no septum between them, so the shipped mass is larger than "
                    f"the muscle alone.")
        if base == "external_anal_sphincter":
            return (f"{v} cm3; {BADGE}: the midline ring within {EAS_MM} mm of the anal canal (the colon "
                    f"label's caudal end) below the levator; the internal sphincter and the anal wall are "
                    f"inside the colon label and are excluded with it, so the ring is the striated sphincter "
                    f"plus whatever intersphincteric tissue the label leaves outside itself.")
        return (f"{v} cm3; {BADGE}: position-rule marker relative to his bone and organ labels, boundary by "
                f"the marker watershed on the pale septa of his cryosection photographs.")

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
                   "external_urethral_sphincter": "a 3-5 mm collar on the membranous urethra in the deep "
                                                  "perineal pouch: below the resolution of a 1 mm frame, "
                                                  "same decision and reasoning as the female script "
                                                  "(scripts/cryo/vhf_pelvic_floor_from_cryo.py), plus his "
                                                  "frame's registration residual is not even independently "
                                                  "quantified here (see the module docstring LIMITS) -- if "
                                                  "anything a weaker case for attempting it than hers",
                   "internal_anal_sphincter": "smooth muscle inside the colon label; excluded with it",
                   "prostate": "not a muscle: TotalSegmentator organ label (id 22), carried only as an "
                              "exclusion + the urogenital-hiatus landmark (see the module docstring)"}
    readme_key = (f"Label id -> structure name for the Visible Human MALE pelvic floor and perineum volume "
                  f"(scripts/cryo/vhm_pelvic_floor_from_cryo.py), plus the mapping onto atlas entities. A "
                  f"KEY, not data. {BADGE}: markers by position rules relative to his bone and organ labels "
                  f"(including the prostate), boundaries by marker watershed on the pale septa of his "
                  f"cryosection photographs; compartments are muscles the photographs do not separate "
                  f"(mapped to null).")
    key = {"_README": [readme_key], "source": SOURCE, "task": "vhm_pelvic_floor", "version": VERSION, "badge": BADGE,
           "labels": {str(l): labels[l][0] for l in sorted(labels)},
           "merged_compartments": merged_compartments, "not_shipped": not_shipped,
           "atlas": {e["source_structure"]: {"atlas_id": e["atlas_id"], "relationship": e["relationship"],
                                             "note": e["note"]} for e in entries}}
    json.dump(key, open(a.labels_out, "w"), indent=1)
    mapping = {"_README": ["Review every entry before running convert.",
                           "Set 'atlas_id' to the correct entity, or null to skip the label.",
                           "'status' is advisory; convert reads 'atlas_id' only."],
               "subject": "ct_vhm_pfloor", "source_volume": str(Path(a.out).resolve()),
               "label_map": "vhm_pelvic_floor", "entries": entries}
    json.dump(mapping, open(a.mapping_out, "w"), indent=1)
    levels = {"k_range": [ka, kb - 1], "z_ras_range": [float(fr.z0 + ka), float(fr.z0 + kb - 1)],
              "legs_ct_slice_range": [ka, kb - 1],
              "pubic_arch_apex": {"k": lv["k_arch"], "legs_ct_slice": lv["kk_arch"],
                                  "z_ras": float(fr.z0 + lv["k_arch"])},
              "ischial_spine": {"k": lv["k_spine"], "legs_ct_slice": lv["kk_spine"],
                                "z_ras": float(fr.z0 + lv["k_spine"])},
              "bladder_neck": ({"legs_ct_slice": lv["kk_bladder_bot"],
                                "z_ras": float(lv["kk_bladder_bot"] + fr.z0)} if lv.get("kk_bladder_bot") is not None else None),
              "anal_canal_bottom": {"legs_ct_slice": lv["kk_anal_bot"], "z_ras": float(lv["kk_anal_bot"] + fr.z0)},
              "ischial_tuberosity_bottom": {"legs_ct_slice": lv["kk_hip_bot"], "z_ras": float(lv["kk_hip_bot"] + fr.z0)},
              "prostate_apex": ({"legs_ct_slice": lv["kk_prostate_apex"],
                                 "z_ras": float(lv["kk_prostate_apex"] + fr.z0),
                                 "delta_from_pubic_arch_apex_mm": lv["kk_prostate_apex"] - lv["k_arch"]}
                                if lv.get("kk_prostate_apex") is not None else None),
              "pelvic_band_k": [lv["k_arch"] + 1, lv["k_hi"]],
              "anal_perineal_band_k": [lv["k_lo"], lv["k_arch"]]}
    report = {
        "_README": ["Male pelvic diaphragm and perineal muscles by position rules on his registered 1 mm "
                    "legs-block cryosection frame (scripts/cryo/vhm_pelvic_floor_from_cryo.py). Rule-based, "
                    "derived data, ported from scripts/cryo/vhf_pelvic_floor_from_cryo.py.",
                    "He is male: a prostate sits at the urogenital hiatus and the midline structure below "
                    "the pubic arch is the bulb of the penis / corpus spongiosum, not the vaginal opening."],
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
                                                   "anterior_of_anal_centre_mm": UG_POST_MM,
                                                   "note": "BS_MIN_DX=0 (no vaginal-opening exclusion; runs to the midline raphe)"},
                               "deep_transverse_perineal": {"below_arch_mm": DTP_MM, "max_dx_mm": DTP_LAT_MM,
                                                            "dy_mm": list(DTP_DY_MM)},
                               "superficial_transverse_perineal": {"above_tuberosity_mm": STP_SPAN_MM,
                                                                   "dy_mm": list(STP_DY_MM),
                                                                   "min_dx_mm": STP_MIN_DX}}},
        "thicknesses_assumed_mm": {
            "levator_ani": f"{LEV_THICK_MM} (Gray's 42nd ed.: the levator ani is a 3-5 mm sheet). The rule "
                           f"band is not clipped to it -- the watershed takes the edge from the septa.",
            "external_anal_sphincter": f"{EAS_MM} (Gray's: the sphincter rings the anal canal 8-15 mm deep)",
            "ischiocavernosus": f"{IC_MM} (the muscle covering the crus on the ischiopubic ramus)",
            "obturator_internus_band": f"{OI_MM} (the band on the inner surface of the ischium; a sink)"},
        "literature": {
            "levator_ani_thickness_male": {
                "pmid": PUBLISHED_MM["levator_ani"][2].split("PMID ")[1].split(",")[0],
                "doi": "10.1007/s11255-015-1019-8",
                "value": PUBLISHED_MM["levator_ani"][2]},
            "levator_ani_volume_male": "not verified: no confirmed male levator-ani VOLUME figure was found "
                                       "(PubMed searched this session for 'levator ani muscle volume men "
                                       "MRI' and related queries) -- only the Tienza 2015 thickness figure "
                                       "above; no MAX_RATIO volume cap is applied for this reason (see "
                                       "plausibility()).",
            "external_anal_sphincter_volume": "not verified (same as the female script: no absolute-volume "
                                              "figure was confirmed)",
            "coccygeus_volume": "not verified",
            "bulbospongiosus_ischiocavernosus_volume_male": "not verified: PubMed searched this session for "
                                                            "'bulbospongiosus ischiocavernosus muscle volume "
                                                            "MRI men' -- no result",
            "comparison": "no male volume figure is confirmed for any structure here, so no MAX_RATIO cap "
                          "fires in plausibility(); MIN_LEVELS / MIN_CM3 fragment checks still apply"},
        "montage": mpath, "output": a.out, "labels_file": a.labels_out, "mapping_file": a.mapping_out,
        "limits": [
            "boundaries are position rules + watershed on 1 mm photographs, not traced fascia",
            "no rms z-registration residual figure exists for this frame the way the female frame.json "
            "states one (8.9 mm); this frame's chain (legs CT -> legs cryo frame -> legs-to-torso "
            "registration) was checked empirically at 4 pelvis levels this session, not independently "
            "quantified",
            "his coccyx is not labelled either, so the coccygeus is anchored on the ischial spine and a "
            f"{POST_PAD_MM} mm posterior pad of the bony hull, same limitation as the female script",
            "the perineal membrane is not visible at 1 mm: the deep and superficial pouches are separated "
            "only by the level of the pubic arch's apex",
            "the corpus spongiosum bulb of the penis is erectile tissue that photographs as dark as striated "
            "muscle; it is held in the perineal_other sink together with the crura of the corpus cavernosum "
            "where not claimed by ischiocavernosus, and is not shipped",
            "the levator ani's parts are not separated; the external urethral sphincter has no male "
            "equivalent attempted either (see not_shipped)",
            "the shipped bulbospongiosus and ischiocavernosus each include the erectile body they cover (the "
            "corpus spongiosum bulb, the crus of the penis): no septum separates muscle from erectile tissue "
            "at 1 mm",
            "the pelvic + perineal band together spans only k=708..752 in the legs block's own grid (45 mm): "
            "a real limitation of how much of the perineum this registration chain resolves, not present in "
            "the female script's much longer single-block frame",
            "the volume is on the 1 mm RAS-like frame grid used by this script (his legs-block cryo frame "
            "resampled onto legs_total.nii.gz's own grid), the grid the masks are computed on"],
    }
    json.dump(report, open(str(Path(a.out).with_suffix("").with_suffix("")) + "_report.json", "w"), indent=1)
    print("groups", [sorted(g) for g in groups])
    print("merges", {f"{p[0]}|{p[1]}": d for p, d in merges.items()})
    print("nulled", nulled)
    print("geometry", {k: (v["mean_atlas_y"], v["levels"]) for k, v in geom.items()})
    print("PFLOOR_DONE")


if __name__ == "__main__":
    main()
