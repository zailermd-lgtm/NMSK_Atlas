"""Track the BRACHIAL artery and the MEDIAN, ULNAR and RADIAL nerves through the female's RIGHT UPPER ARM
in her FULL-RESOLUTION cryosection crops (Q56, second half).

    python3 scripts/cryo/vhf_stream_crops.py --frame SCRATCH/vh_cryo_f --y-top 592 --y-bot 300 \
        --box right=95,240,-140,30 --out SCRATCH/vh_cryo_f/uarm --step 1
    python3 scripts/cryo/vhf_brachial_track.py track --crops SCRATCH/vh_cryo_f/uarm --side right \
        --bundle build/viewer_f --y-start 560 --y-end 305 --out SCRATCH/brachial_right
    python3 scripts/cryo/vhf_brachial_track.py clean --tracks SCRATCH/brachial_right \
        --span artery=520:315 median_n=520:315 ulnar_n=520:315 radial_n=520:315 \
        --crops SCRATCH/vh_cryo_f/uarm --side right --every 14 \
        --montage data/ct_sources/task_outputs/vhf_brachial_cryo_right.png
    python3 scripts/cryo/vhf_nerve_volume.py --crops SCRATCH/vh_cryo_f/uarm \
        --track brachial_a_r=SCRATCH/brachial_right_artery_clean.json:520:315 \
        --track median_n=SCRATCH/brachial_right_median_n_clean.json:520:315 ... \
        --out data/ct_sources/task_outputs/vhf_brachial_cryo.nii.gz \
        --labels-out mappings/vhf_brachial_labels.json \
        --mapping-out mappings/subjects/ct_vhf_brachial_volume_mapping.json --subject ct_vhf_brachial
    python3 scripts/cryo/vhf_brachial_track.py report --tracks SCRATCH/brachial_right --suffix _clean \
        --span ... --ids '{"artery_right": "brachial_a_r", "median_n_right": "median_n", ...}' \
        --volume data/ct_sources/task_outputs/vhf_brachial_cryo.nii.gz \
        --labels mappings/vhf_brachial_labels.json \
        --volume-report data/ct_sources/task_outputs/vhf_brachial_cryo_report.json --out <that same file>
    cp mappings/subjects/ct_vhf_brachial_volume_mapping.json build/vh/ && \
    python3 scripts/ingest_volume_geometry.py convert data/ct_sources/task_outputs/vhf_brachial_cryo.nii.gz \
        --labels vhf_brachial --subject ct_vhf_brachial --origin='7.769,-885.229,14.137' --smooth 1.0

Companion of vhf_femoral_track.py (Q55) and vhf_popliteal_track.py (Q56 first half): the same crops
(vhf_stream_crops.py), the same lumen rule, the same "a lumen's surround must not be muscle-red" rule, the
same local walk, the same cleaning gate, the same plausibility gate and the same volume builder
(vhf_nerve_volume.py). What changes is the FRAME. In the thigh the corridor came from transferred muscle
meshes; here it comes from the HUMERUS AS PHOTOGRAPHED, because her arm in the CT and her arm in the frozen
block are not one rigid body (vhf_arm_muscles_from_cryo.py Q49, vhf_forearm_muscles_from_cryo.py Q62): the
CT humerus label lands 5-15 mm off the photographed bone and the residual grows distally. So the CT humerus
is used only to SEED a bone-disc tracker (vhf_forearm_muscles_from_cryo.island_mask / pale_filled / dt_bone:
the largest circle inscribed in the pale class, >= 10 mm from the skin, within 6 mm + 2 mm per lost level of
the previous centre) and every rule below is stated against the PHOTOGRAPHED bone.

ANATOMY (Gray's 42nd ed. 'Axilla and arm'; Moore 8th ed.). The BRACHIAL ARTERY runs down the MEDIAL BICIPITAL
GROOVE, anterior to the medial head of triceps and medial to the humerus, with the MEDIAN NERVE beside it: the
nerve starts LATERAL to the artery high in the arm, crosses in FRONT of it about mid-arm and lies MEDIAL to it
at the cubital fossa. The ULNAR NERVE leaves that bundle at mid-arm, pierces the medial intermuscular septum
and runs behind the medial epicondyle (the cubital tunnel), i.e. it ends up POSTERIOR-MEDIAL. The RADIAL NERVE
is POSTERIOR, in the spiral groove of the humerus with the profunda brachii artery, then pierces the lateral
intermuscular septum to lie between brachialis and brachioradialis.

RULES (+Z anterior, +X the subject's right; on this right arm MEDIAL = smaller x; 1 mm levels, 0.33 mm px):
  island    = vhf_forearm_muscles_from_cryo.island_mask seeded at the bone: the arm's own tissue component,
              eroded just enough to break the gelatin bridge to the chest wall and grown back. Everything
              below happens inside it, so the axilla and the thorax cannot be walked into.
  corridor  = (bundle) inside the island, >= 6 mm deep to the skin, within 60 mm of the photographed bone
              centre and MEDIAL of it (x <= bone x + 10 mm); (radial) inside the island, >= 6 mm deep to the
              skin, within 45 mm of the bone centre and POSTERIOR of it (z <= bone z + 6 mm).
  lumen     = vhf_femoral_track.vessel_candidates unchanged: a near-black core (3 mm mean red < 58), opened
              by 0.7 mm, touching lumina split by a distance watershed, grown out to its wall (red < 105, at
              most 2 mm past the core), 4-120 mm2, solidity >= 0.75, aspect <= 2.5, 20th percentile of red
              < 40 and a pale wall (ring red >= 30 above the lumen).
  seed      = LANDMARK RULE, not a hand click: the first level at or below --y-start whose BUNDLE CORRIDOR
              holds a lumen 2-7 mm across, >= 10 mm deep to the skin, 3-45 mm medial of the photographed
              humerus and within 30 mm of it in depth, whose 0.7-2 mm annulus is at least 25% NOT muscle-red
              (the artery lies in the fat of the medial bicipital groove, not inside a belly), best scoring
              on roundness + wall contrast. That is the BRACHIAL ARTERY.
  artery    = local walk (aorta_from_cryo.py rule at full resolution, as walk_vessel): inside its own previous
              ATLAS position dilated by reach_mm, the darkest round component (window 15th percentile of red
              + 18) of 0.35-3x its own previous area, solidity >= 0.7, aspect <= 2.6, a pale wall (ring red
              >= 20 above the lumen), at least 25% of its annulus NOT muscle-red, still inside the bundle
              corridor, area <= MAX_MM2 (a mask wider than ~1.2x the textbook maximum has eaten into muscle).
              Walked DOWN and UP from the seed; 8 gaps in a row end the walk.
  nerves    = fascicle texture (vhf_nerve_track.nerve_blobs via vhf_femoral_track.nerve_candidates), each
              nerve a walk whose seed is a RELATION, not a hand click, and the three never share a blob at a
              level (median is assigned first, then ulnar, then radial in its own corridor):
                median  2-20 mm from the tracked artery, nearest to it (its side changes down the arm - that
                        crossing is what is measured afterwards, so it is NOT constrained here);
                ulnar   4-35 mm from the artery and NOT anterolateral to it (medial or posterior: it leaves
                        the bundle at mid-arm through the medial septum), nearest its own previous position;
                radial  in the POSTERIOR corridor, 5-40 mm from the bone centre, nearest its own previous
                        position; seeded at the spiral-groove level (--radial-seed, default y 470).
              Each is within reach_mm of its own previous position once seeded.
  cleaning  = for a NERVE, a level whose blob is surrounded by more than 70% muscle-red is dropped (an
              intramuscular fat pocket or a tendon, not a nerve in the intermuscular fat). For every
              structure, a level whose mask is ragged (solidity < 0.85) or whose diameter falls outside
              CLEAN_MM widened by 25% drops back to a gap; the volume builder fills gaps of <= 12 levels.
  gate      = a structure whose median diameter is more than twice the textbook maximum or under half the
              textbook minimum, or that survives over less than MIN_SPAN_MM mm or on fewer than MIN_LEVELS
              levels, is NULLED in the volume mapping with the reason in its note rather than shipped under
              an anatomical name.

RESULT OF THE RUN (2026-09-16, Q56 second half). NOTHING IS SHIPPED UNDER AN ANATOMICAL NAME. All four
labels of data/ct_sources/task_outputs/vhf_brachial_cryo.nii.gz are NULLED in the subject mapping with the
reason in their notes, and `ingest_volume_geometry.py convert` therefore refuses the subject. Why: this
cadaver's brachial artery does not photograph as a dark clotted lumen. Inside the deep bundle corridor the
arm's own lumen rule yields a median of 0-1 candidates per level and no chain longer than 27 levels; the
one dark vessel that survives the length of the arm (144 of 211 levels) lies 45 mm ANTERIOR to the humerus
at the muscle/subcutaneous-fat interface, i.e. OUTSIDE the deep fascia - a superficial vein, not the
brachial artery, and not shipped, because naming it would be a guess. The artery track the seed ladder does
produce (60 levels, y 498-396, median 2.1 mm) was REJECTED on the montage: it outlines a 2 mm dark patch on
the medial border of the muscle belly, with no pale arterial wall. The three nerve walks held 1, 1 and 18
levels and are nulled by the plausibility gate. What the run does contribute and what is worth reusing is
the FRAME: the deep-arm muscle hull (which separates her arm from the chest wall it touches, where the
forearm's tissue island runs into the thorax) and the photographed humerus disc, tracked on 182 of 203
levels with a median CT-to-photo residual of 8.9 mm.

LIMITS: the tracked vessel mask is the LUMEN (clotted blood), not the wall, so the diameters are lumen
diameters and a lumen abutting muscle without a pale wall between is kept at its dark core and under-measured;
a cadaveric muscular artery is contracted, so a brachial artery under the living 3.5-5 mm would be reported AS
MEASURED and not forced up. The bone frame is the photographed humerus, so it is only as good as the bone
disc; the CT residual is recorded per level in the report. The brachial artery's origin (lower border of
teres major) and its division into radial and ulnar arteries in the cubital fossa are NOT resolved. The
profunda brachii and the brachial venae comitantes are not tracked. Only the RIGHT arm was run. Rule-based;
badged; volumes and per-level diameters recorded.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.cryo.vhf_nerve_track import Crops, PX, disk, photo_classes, section_masks  # noqa: E402
from scripts.cryo.vhf_femoral_track import (_dark_components, blob_stats, clean_rows,  # noqa: E402
                                            outside_gel, roundness_score)
from scripts.transfer.bundle_io import meshes_by_id, read_bundle_dir  # noqa: E402
from skimage.feature import peak_local_max  # noqa: E402
from skimage.morphology import convex_hull_image  # noqa: E402
from skimage.segmentation import watershed  # noqa: E402

SOURCE = ("U.S. National Library of Medicine, The Visible Human Project (public domain), female cryosections at full "
          "resolution (0.33 mm) and CT via the NCI Imaging Data Commons. Derived data "
          "(scripts/cryo/vhf_brachial_track.py).")
MUSCLE_R, PALE_R = 100.0, 150.0                # this cadaver: muscle red < 100, bone/fat/septa pale > 150
ARM = {"drop": 35.0, "vessel_mm2": (1.5, 40.0), "nerve_mm2": (4.0, 70.0), "ring_min": 30.0,
       "bundle_mm": 38.0, "radial_mm": 35.0, "skin_mm": 3.0, "max_mm2": {"artery": 30.0}}
# textbook adult cross-sections (Gray's 42nd ed.; Moore 8th ed.): a woman's brachial artery lumen 3.5-5 mm,
# the three nerves roughly 3-6 mm across in the arm
EXPECTED_MM = {"artery": (3.5, 5.0), "median_n": (3.0, 6.0), "ulnar_n": (3.0, 6.0), "radial_n": (3.0, 6.0)}
# band used by the cleaning gate: the artery's floor is dropped to 2 mm because a cadaveric muscular artery
# is contracted and its clotted lumen is smaller than the living vessel
CLEAN_MM = {"artery": (2.0, 6.5), "median_n": (2.5, 8.0), "ulnar_n": (2.5, 8.0), "radial_n": (2.5, 8.0)}
ATLAS_ORIGIN = (7.769, -885.229, 14.137)
MIN_LEVELS = 20        # a named cord is shipped only when it was verified over
MIN_SPAN_MM = 30.0     # at least 30 mm of course, on at least 20 separate levels
SEED_MED_MM = (12.0, 40.0)    # the medial bicipital groove: mm medial of the photographed humerus centre
SEED_DZ_MM = 25.0             # and within this of its depth
NAMES = ("artery", "median_n", "ulnar_n", "radial_n")
LAB_OF = {"artery": 1, "median_n": 2, "ulnar_n": 3, "radial_n": 4}


# ---------------------------------------------------------------- the frame: the photographed humerus
def ct_humerus_ref(meshes, side, y, crops, shape):
    """(row, col) of the CT humerus section's centroid at level y - the SEED of the bone tracker only."""
    m = section_masks(meshes, ["humerus"], side, y, crops, shape).get("humerus")
    if m is None or not m.any():
        return None
    rr, cc = np.nonzero(m)
    return float(rr.mean()), float(cc.mean())


def deep_arm(im, ref, cl=None):
    """The DEEP ARM at one level: the muscle class (3 mm mean red < 100) closed by ~12 mm and filled, the
    component holding `ref`, convex-hulled. That hull is the arm under its deep fascia - the bone, the muscle
    bellies and the intermuscular fat between them - and it excludes the subcutaneous fat (so the basilic
    vein, which is subcutaneous in the arm, cannot be mistaken for the artery). Her arm TOUCHES her chest
    wall in these sections, so a plain tissue island (vhf_forearm_muscles_from_cryo.island_mask, written for
    the free forearm) runs into the thorax; the muscle hull does not, because the chest wall's muscle is
    ~45 mm away, far beyond the closing."""
    cl = cl or photo_classes(im)
    mus = (cl["m5"] < MUSCLE_R) & ~cl["gel"]
    d = ndi.binary_fill_holes(ndi.binary_closing(mus, structure=disk(12), iterations=3))
    lab, n = ndi.label(d)
    if n == 0:
        return None, cl
    rr = int(min(max(round(ref[0]), 0), lab.shape[0] - 1))
    cc = int(min(max(round(ref[1]), 0), lab.shape[1] - 1))
    i = int(lab[rr, cc])
    if i == 0:
        idx = ndi.distance_transform_edt(lab == 0, return_indices=True)[1]
        i = int(lab[idx[0][rr, cc], idx[1][rr, cc]])
    if i == 0:
        return None, cl
    return convex_hull_image(lab == i), cl


def bone_disc(im, ref, search_mm, hull, cl, min_r_mm=3.5, edge_mm=3.0, marrow_mm2=250.0):
    """The HUMERUS AS PHOTOGRAPHED: the largest circle inscribed in the pale class (its marrow hole filled)
    inside the deep-arm hull, within `search_mm` of `ref` and at least `edge_mm` from the hull's edge. The
    rule is vhf_forearm_muscles_from_cryo.dt_bone's (there the bone is the largest inscribed circle in the
    pale class away from the skin); what changes is that the pale class is taken inside the muscle hull
    instead of inside the whole limb, which is what keeps it off the thick subcutaneous fat of this arm."""
    pale = ndi.binary_closing((cl["m5"] > PALE_R) & hull, iterations=2)
    holes = ndi.binary_fill_holes(pale) & ~pale
    hl, hn = ndi.label(holes)
    if hn:
        hs = ndi.sum(holes, hl, range(1, hn + 1))
        small = np.zeros(hn + 1, bool)
        small[1:] = hs * PX * PX <= marrow_mm2
        pale = pale | small[hl]
    dt = ndi.distance_transform_edt(pale)
    dist = ndi.distance_transform_edt(hull)
    yy, xx = np.mgrid[0:dt.shape[0], 0:dt.shape[1]]
    win = (np.hypot(yy - ref[0], xx - ref[1]) * PX <= search_mm) & (dist * PX >= edge_mm)
    if not win.any():
        return None, dist
    v = np.where(win, dt, -1.0)
    cy, cx = np.unravel_index(int(np.argmax(v)), v.shape)
    r = float(dt[cy, cx])
    return ((float(cy), float(cx), r) if r * PX >= min_r_mm else None), dist


def bone_level(crops, meshes, side, y, prev, search_mm):
    """One level of the frame: the deep-arm hull and the photographed humerus disc. None when no hull."""
    im = crops.image(y)
    hull, cl = deep_arm(im, prev)
    if hull is None:
        return None
    b, dist = bone_disc(im, prev, search_mm, hull, cl)
    rec = {"y": y, "hull": hull, "found": b is not None,
           "dist_mm": np.clip(dist * PX, 0, 255).astype(np.uint8)}      # only light arrays are kept per level
    rec["bone"] = (b[0], b[1], b[2]) if b is not None else (prev[0], prev[1], 0.0)
    bx, bz = crops.px_to_atlas(y, rec["bone"][0], rec["bone"][1])
    rec["bone_xz"] = (float(bx), float(bz))
    rec["bone_r_mm"] = float(rec["bone"][2]) * PX
    return rec


def track_humerus(crops, meshes, side, ys, y_anchor, log=print, lost_max=10):
    """Bone discs over `ys` (sorted top-down), seeded at `y_anchor` from the CT humerus section (search 15 mm)
    and tracked outward in both directions (search 6 mm + 2 mm per level lost). Also records, per level, the
    residual between the photographed disc centre and the CT section centroid (mm)."""
    shape = crops.image(y_anchor).shape[:2]
    ref = ct_humerus_ref(meshes, side, y_anchor, crops, shape)
    if ref is None:
        raise SystemExit(f"no CT humerus section at the anchor level y={y_anchor}")
    rec = bone_level(crops, meshes, side, y_anchor, ref, 15.0)
    if rec is None or not rec["found"]:
        raise SystemExit(f"the humerus disc was not found in the photograph at y={y_anchor}")
    out = {y_anchor: rec}
    for leg in ([y for y in ys if y < y_anchor], [y for y in ys if y > y_anchor][::-1]):
        prev = out[y_anchor]["bone"][:2]
        lost = 0
        for y in leg:
            r = bone_level(crops, meshes, side, y, prev, 6.0 + 2.0 * lost)
            if r is None:
                log(f"  bone frame stops at y={y} (no deep-arm hull)")
                break
            if r["found"]:
                prev = r["bone"][:2]
                lost = 0
            else:
                lost += 1
                if lost > lost_max:
                    log(f"  bone frame stops at y={y} (bone lost {lost} levels)")
                    break
            out[y] = r
    resid = {}
    for y, r in out.items():
        c = ct_humerus_ref(meshes, side, y, crops, r["hull"].shape)
        if c is not None and r["found"]:
            resid[int(y)] = [round((r["bone"][0] - c[0]) * PX, 1), round((r["bone"][1] - c[1]) * PX, 1)]
    return out, resid


def corridors(crops, rec, side):
    """(bundle, radial) corridors of one level, in the frame of the PHOTOGRAPHED humerus, memoised into the
    level record. bundle: inside the deep-arm hull, at least ARM['skin_mm'] from its edge, within
    ARM['bundle_mm'] of the bone centre and MEDIAL of it (x <= bone x + 10 mm). radial: the same but within
    ARM['radial_mm'] of the bone centre and POSTERIOR of it (z <= bone z + 6 mm). The bundle corridor's
    38 mm radius is what keeps the walk off the subcutaneous vein that runs the length of this arm 45 mm
    anterior to the humerus, just outside the deep fascia."""
    if "bundle" in rec:
        return rec["bundle"], rec["radial"]
    sg = 1.0 if side == "right" else -1.0                     # medial = sg * x smaller than the bone's
    shape = rec["hull"].shape
    yy, xx = np.mgrid[0:shape[0], 0:shape[1]]
    ax, az = crops.px_to_atlas(rec["y"], yy.ravel(), xx.ravel())
    ax = np.asarray(ax, float).reshape(shape)
    az = np.asarray(az, float).reshape(shape)
    bx, bz = rec["bone_xz"]
    deep = rec["hull"] & (rec["dist_mm"] >= ARM["skin_mm"])
    d = np.hypot(ax - bx, az - bz)
    rec["bundle"] = deep & (d <= ARM["bundle_mm"]) & (sg * (ax - bx) <= 10.0)
    rec["radial"] = deep & (d <= ARM["radial_mm"]) & (az - bz <= 6.0)
    return rec["bundle"], rec["radial"]


# ---------------------------------------------------------------- the arm's lumen rule
def arm_lumina(im, region, cl=None, drop=35.0, bg_px=25):
    """Label image of dark round lumina of the ARM. The femoral/popliteal rule (vhf_femoral_track.
    vessel_lumina) looks for a near-BLACK core (3 mm mean red < 58) because her thigh muscle photographs at
    red 75-95. Her UPPER-ARM muscle photographs far darker - the 20th percentile of red inside an arm muscle
    patch is 44-55, i.e. as dark as a thigh lumen - so an absolute threshold either swallows the whole belly
    or finds nothing (both were measured on these photographs before this rule was written). The rule is
    therefore LOCAL CONTRAST, which is the same idea the walk already used (aorta_from_cryo.py's adaptive
    window threshold), applied to the whole level: a lumen is a blob at least `drop` red levels darker than
    the mean of its own ~8 mm neighbourhood, opened by 0.7 mm and split by a distance watershed. Everything
    that follows (roundness, pale wall, not-muscle-red surround) is unchanged from the thigh."""
    cl = cl or photo_classes(im)
    R3 = ndi.uniform_filter(cl["R"], 3)
    bg = ndi.uniform_filter(cl["R"], bg_px)
    gel = outside_gel(im[..., 2].astype(np.float32) > cl["R"])
    core = ndi.binary_opening((R3 < bg - drop) & region & ~gel, structure=disk(2))
    if not core.any():
        return np.zeros(im.shape[:2], np.int32)
    dist = ndi.distance_transform_edt(core)
    pk = peak_local_max(dist, labels=core, min_distance=5, exclude_border=False)
    mk = np.zeros(core.shape, np.int32)
    for i, (r, c) in enumerate(pk):
        mk[r, c] = i + 1
    return watershed(-dist, mk, mask=core)


def arm_vessel_candidates(im, corridor, spec, cl=None, region=None):
    """Round dark lumina of `arm_lumina` inside the corridor: area in spec['vessel_mm2'], solidity >= 0.75,
    aspect <= 2.3, at least half inside the corridor, and a PALE WALL (mean red of a 0.7-2 mm annulus at
    least spec['ring_min'] above the lumen)."""
    cl = cl or photo_classes(im)
    R = cl["R"]
    lab = arm_lumina(im, corridor if region is None else region, cl)
    lo, hi = spec["vessel_mm2"]
    out = []
    for i in range(1, int(lab.max()) + 1):
        mm = lab == i
        if not mm.any():
            continue
        s = blob_stats(mm)
        if not (lo <= s["area_mm2"] <= hi) or s["solidity"] < 0.75 or s["aspect"] > 2.3:
            continue
        inside = float(corridor[mm].mean())
        if inside < 0.5:
            continue
        ring = ndi.binary_dilation(mm, structure=disk(6)) & ~ndi.binary_dilation(mm, structure=disk(2))
        mr = float(R[mm].mean())
        rr = float(R[ring].mean()) if ring.any() else 0.0
        if rr - mr < spec["ring_min"]:
            continue
        out.append(dict(s, lab=i, inside=inside, mean_r=round(mr, 1), ring_r=round(rr, 1),
                        score=roundness_score(s)))
    return out, lab


def arm_nerve_blobs(im, cl=None):
    """Fascicle texture in the ARM: vhf_nerve_track.nerve_blobs with two numbers changed, because the nerves
    of the arm are small (3-6 mm) and lie in FAT, not in the loose tissue of the thigh. nerve_blobs pushes
    the core 1 mm away from every muscle/fat/gel boundary and then asks for a core of at least 4 mm2; a 4 mm
    nerve in fat has only a 2 mm core left after that erosion (3.1 mm2) and is thrown away. Here the
    stand-off is 0.7 mm and the core threshold 2.5 mm2. Everything else is unchanged: mid brightness (3 mm
    mean red 95-190), dense fine edges (mean |sobel| > 55), not bimodal (sd < 35), opened by 0.7 mm, grown
    back 1 mm into mid-brightness non-muscle tissue."""
    cl = cl or photo_classes(im)
    R = cl["R"]
    m = ndi.uniform_filter(R, 9)
    g = ndi.uniform_filter(np.hypot(ndi.sobel(R, 0), ndi.sobel(R, 1)), 9)
    sd = np.sqrt(np.maximum(ndi.uniform_filter(R * R, 9) - m * m, 0))
    near = ndi.binary_dilation(cl["muscle"] | cl["fat"] | cl["gel"], structure=disk(2), iterations=1)
    core = ndi.binary_opening((m > 95) & (m < 190) & (g > 55) & (sd < 35) & ~near, structure=disk(2))
    lab, n = ndi.label(core)
    if n == 0:
        return lab, 0
    area = ndi.sum(core, lab, range(1, n + 1))
    keep = np.zeros(n + 1, bool)
    keep[1:] = area * PX * PX >= 2.5
    grown = (ndi.binary_dilation(keep[lab], structure=disk(3), iterations=1)
             & (m > 90) & (m < 186) & ~cl["muscle"] & ~cl["gel"])
    return ndi.label(grown)


def arm_nerve_candidates(im, corridor, spec, cl=None):
    """`arm_nerve_blobs` inside the corridor: area in spec['nerve_mm2'], aspect <= 3.0, at least half inside."""
    cl = cl or photo_classes(im)
    lab, n = arm_nerve_blobs(im, cl)
    lo, hi = spec["nerve_mm2"]
    out = []
    for i in range(1, n + 1):
        mm = lab == i
        if not mm.any():
            continue
        s = blob_stats(mm)
        if not (lo <= s["area_mm2"] <= hi) or s["aspect"] > 3.0:
            continue
        inside = float(corridor[mm].mean())
        if inside < 0.5:
            continue
        out.append(dict(s, lab=i, inside=inside, score=roundness_score(s)))
    return out, lab


# ---------------------------------------------------------------- seed and walks
def not_muscle_frac(im, mask, cl=None):
    """Fraction of the 0.7-2 mm annulus around `mask` that is NOT muscle-red. The brachial bundle lies in the
    fat of the medial bicipital groove; a dark patch wholly inside a belly is not a lumen."""
    cl = cl or photo_classes(im)
    ring = ndi.binary_dilation(mask, structure=disk(6)) & ~ndi.binary_dilation(mask, structure=disk(2))
    if not ring.any():
        return 0.0
    gel = outside_gel(im[..., 2].astype(np.float32) > cl["R"])
    return float(((cl["m5"] > 110) & ~gel)[ring].mean())


def groove_lumen(crops, frame, side, y, fat_frac=0.35):
    """The best brachial-artery candidate of ONE level, or None: a lumen of the medial bundle corridor
    1.8-6 mm across, SEED_MED_MM medial of the photographed humerus centre, within SEED_DZ_MM of it in
    depth, with a pale wall and an annulus at least `fat_frac` NOT muscle-red, scored on roundness + wall
    contrast."""
    sg = 1.0 if side == "right" else -1.0
    rec = frame.get(y)
    if rec is None or not rec["found"]:
        return None
    bundle, _ = corridors(crops, rec, side)
    im = crops.image(y)
    cl = photo_classes(im)
    cands, lab = arm_vessel_candidates(im, bundle, ARM, cl)
    bx, bz = rec["bone_xz"]
    best = None
    for c in cands:
        cx, cz = crops.px_to_atlas(y, c["rc"][0], c["rc"][1])
        cx, cz = float(cx), float(cz)
        med = sg * (bx - cx)
        if not (SEED_MED_MM[0] <= med <= SEED_MED_MM[1]) or abs(cz - bz) > SEED_DZ_MM:
            continue
        if not (1.8 <= c["diam_mm"] <= 6.0):
            continue
        mm = lab == c["lab"]
        f = not_muscle_frac(im, mm, cl)
        if f < fat_frac:
            continue
        sc = roundness_score(c) + (c["ring_r"] - c["mean_r"]) / 120.0
        if best is None or sc > best[0]:
            best = (sc, dict(c, x=cx, z=cz, medial_mm=med, fat=f, mask=mm,
                             bone={"x": round(bx, 1), "z": round(bz, 1), "r_mm": round(rec["bone_r_mm"], 1)}))
    return best[1] if best else None


def seed_artery(crops, frame, side, ys, reach_mm=4.0, fat_frac=0.35, log=print):
    """LANDMARK RULE, not a hand click. The MEDIAL BICIPITAL GROOVE is the interval at the medial border of
    the arm's muscle mass, medial to the humerus and between biceps/brachialis in front and the medial head
    of triceps behind. `groove_lumen` states that rule per level. Which level to seed at is decided by the
    data and not by hand: the groove lumen of every 8th level is walked up and down (walk_artery) and the
    seed whose walk survives the most levels wins, because the BRACHIAL ARTERY is the one lumen of the
    groove that runs the whole length of the arm - a vena comitans or a small muscular branch gives out
    after a few centimetres. Every seed tried and the length it reached are recorded in the report.
    The basilic vein cannot be picked up: it is subcutaneous in the arm and the deep-arm hull excludes it."""
    ladder = [y for y in ys if (ys[0] - y) % 8 == 0]
    tried = []
    for y in ladder:
        c = groove_lumen(crops, frame, side, y, fat_frac)
        if c is None:
            continue
        legs = [walk_artery(crops, frame, side, leg, y, c["mask"], reach_mm=reach_mm, fat_frac=fat_frac)
                for leg in ([q for q in ys if q <= y], [q for q in ys if q >= y][::-1])]
        rows = merge_legs([lg[0] for lg in legs])
        n = sum(1 for r in rows if not r["gap"])
        tried.append({"y": int(y), "levels": int(n),
                      "span_mm": int(abs(rows[0]["y"] - rows[-1]["y"])) if rows else 0,
                      "medial_mm": round(c["medial_mm"], 1), "diam_mm": round(c["diam_mm"], 1)})
        log(f"  seed try y={y}: groove lumen d{c['diam_mm']:.1f} at {c['medial_mm']:.0f} mm medial "
            f"-> {n} levels", flush=True)
    if not tried:
        raise SystemExit("no brachial-artery lumen found in the given levels")
    best = max(tried, key=lambda t: t["levels"])
    y0 = best["y"]
    c = groove_lumen(crops, frame, side, y0, fat_frac)
    log(f"seed level y={y0}: bone x{c['bone']['x']:.0f} z{c['bone']['z']:.0f} | artery x{c['x']:.0f} "
        f"z{c['z']:.0f} d{c['diam_mm']:.1f} ({c['medial_mm']:.0f} mm medial, fat {c['fat']:.2f}), "
        f"{best['levels']} levels")
    seed = {"y": int(y0), "x": round(c["x"], 1), "z": round(c["z"], 1),
            "humerus_photographed": c["bone"], "medial_of_humerus_mm": round(c["medial_mm"], 1),
            "rule": (f"the seed is a LANDMARK RULE, not a hand click: at each level of an 8 mm ladder the best "
                     f"round dark lumen of the MEDIAL BICIPITAL GROOVE corridor is taken "
                     f"({SEED_MED_MM[0]:.0f}-{SEED_MED_MM[1]:.0f} mm medial of the photographed humerus, within "
                     f"{SEED_DZ_MM:.0f} mm of it in depth, inside the deep-arm muscle hull, with a pale wall and "
                     f"a surround that is not muscle-red), the artery is walked up and down from each, and the "
                     f"seed whose walk survives the MOST levels is kept - the brachial artery is the one lumen "
                     f"of the groove that runs the length of the arm"),
            "seeds_tried": tried}
    return int(y0), c, seed


def walk_artery(crops, frame, side, ys, y0, mask0, reach_mm=4.0, max_gap=8, fat_frac=0.35, log=print):
    """Follow the artery lumen from its seed: inside its own previous ATLAS position dilated by reach_mm, the
    `arm_lumina` component of 0.35-3x its own previous area, solidity >= 0.7, aspect <= 2.6, a pale wall (ring
    red >= ARM['ring_min'] above the lumen), an annulus at least `fat_frac` NOT muscle-red, at least half
    inside the bundle corridor and no wider than MAX_MM2 (past that the mask has eaten into muscle). A level
    without such a component is a gap that keeps the previous position; `max_gap` gaps in a row end the walk."""
    rows, masks = [], {}
    s0 = blob_stats(mask0)
    prev_a = s0["area_mm2"]
    prev_xz = tuple(float(v) for v in crops.px_to_atlas(y0, *s0["rc"]))
    gaps = 0
    for y in ys:
        if y == y0:
            rows.append(_arow(y, s0, prev_xz))
            masks[y] = mask0
            continue
        rec = frame.get(y)
        if rec is None:
            break
        bundle, _ = corridors(crops, rec, side)
        im = crops.image(y)
        cl = photo_classes(im)
        pyx = np.array([float(v) for v in crops.atlas_to_px(y, *prev_xz)])
        rad = np.sqrt(prev_a / np.pi) / PX + reach_mm / PX
        yy, xx = np.ogrid[:im.shape[0], :im.shape[1]]
        win = (yy - pyx[0]) ** 2 + (xx - pyx[1]) ** 2 <= rad * rad
        if not win.any():
            break
        lab = arm_lumina(im, win & rec["hull"], cl)
        best, bscore = None, -1e9
        for i in range(1, int(lab.max()) + 1):
            mm = lab == i
            a = mm.sum() * PX * PX
            if not (max(1.2, 0.35 * prev_a) <= a <= min(ARM["max_mm2"]["artery"], 3.0 * prev_a)):
                continue
            s = blob_stats(mm)
            if s["solidity"] < 0.70 or s["aspect"] > 2.6:
                continue
            if float(bundle[mm].mean()) < 0.5:
                continue
            ring = ndi.binary_dilation(mm, structure=disk(6)) & ~ndi.binary_dilation(mm, structure=disk(2))
            if not ring.any() or float(cl["R"][ring].mean()) - float(cl["R"][mm].mean()) < ARM["ring_min"]:
                continue
            f = not_muscle_frac(im, mm, cl)
            if f < fat_frac:
                continue
            d = float(np.hypot(s["rc"][0] - pyx[0], s["rc"][1] - pyx[1])) * PX
            if d > reach_mm + 2.0:
                continue
            sc = roundness_score(s) - abs(np.log(max(a, 1e-6) / max(prev_a, 1e-6))) - 0.15 * d
            if sc > bscore:
                best, bscore = (mm, s, f), sc
        if best is None:
            gaps += 1
            rows.append({"y": y, "gap": True, "x": round(prev_xz[0], 1), "z": round(prev_xz[1], 1)})
            if gaps > max_gap:
                break
            continue
        gaps = 0
        mm, s, f = best
        prev_a = s["area_mm2"]
        masks[y] = mm
        prev_xz = tuple(float(v) for v in crops.px_to_atlas(y, *s["rc"]))
        rows.append(dict(_arow(y, s, prev_xz), fat=round(f, 2)))
    while rows and rows[-1]["gap"]:
        rows.pop()
    return rows, masks


def _arow(y, s, xz, thr=None):
    r = {"y": y, "gap": False, "x": round(xz[0], 1), "z": round(xz[1], 1),
         "area_mm2": round(s["area_mm2"], 1), "diam_mm": round(s["diam_mm"], 1),
         "inscribed_mm": round(s["inscribed_mm"], 1), "solidity": round(s["solidity"], 2),
         "aspect": round(s["aspect"], 2)}
    if thr is not None:
        r["thr"] = round(thr, 1)
    return r


def nerve_level(crops, frame, side, y, which):
    """Fascicle-texture candidates of one level in the corridor that `which` uses, with atlas centroids."""
    rec = frame.get(y)
    if rec is None or not rec["found"]:
        return [], None, None
    bundle, radial = corridors(crops, rec, side)
    cor = radial if which == "radial_n" else bundle
    cands, lab = arm_nerve_candidates(crops.image(y), cor, ARM)
    for c in cands:
        cx, cz = crops.px_to_atlas(y, c["rc"][0], c["rc"][1])
        c["x"], c["z"] = float(cx), float(cz)
    return cands, lab, rec


def walk_nerve(crops, frame, side, ys, which, art_xz, taken, reach_mm=7.0, max_gap=6,
               near_mm=(2.0, 20.0), log=print):
    """Follow one nerve. Its SEED is a RELATION, not a hand click (see the module docstring): median = the
    fascicle blob NEAREST the tracked artery, 2-20 mm from it; ulnar = the nearest blob 4-35 mm from the
    artery that is not anterolateral to it; radial = the blob of the POSTERIOR corridor nearest the bone,
    5-40 mm from its centre. Afterwards each is a walk: the same relation plus within `reach_mm` of its own
    previous position. `taken` holds, per level, the blob labels another nerve already owns."""
    sg = 1.0 if side == "right" else -1.0
    rows, masks = [], {}
    px = pz = None
    gaps = 0
    for y in ys:
        cands, lab, rec = nerve_level(crops, frame, side, y, which)
        if rec is None:
            break
        ax = art_xz.get(y)
        bx, bz = rec["bone_xz"]
        best, bd = None, 1e9
        for c in cands:
            if c["lab"] in taken.get(y, set()):
                continue
            cx, cz = c["x"], c["z"]
            if which == "radial_n":
                db = float(np.hypot(cx - bx, cz - bz))
                if not (5.0 <= db <= 40.0):
                    continue
                ref = db
            else:
                if ax is None:
                    continue
                da = float(np.hypot(cx - ax[0], cz - ax[1]))
                if not (near_mm[0] <= da <= near_mm[1]):
                    continue
                if which == "ulnar_n" and sg * (cx - ax[0]) > 2.0 and cz > ax[1] + 2.0:
                    continue                                  # anterolateral of the artery: that is the median
                ref = da
            d = ref if px is None else float(np.hypot(cx - px, cz - pz))
            if px is not None and d > reach_mm:
                continue
            if d < bd:
                best, bd = (c, cx, cz), d
        if best is None:
            if px is None:
                continue                                      # the seed level gave nothing: try the next level
            gaps += 1
            rows.append({"y": y, "gap": True, "x": round(px, 1), "z": round(pz, 1)})
            if gaps > max_gap:
                break
            continue
        gaps = 0
        c, cx, cz = best
        px, pz = cx, cz
        masks[y] = lab == c["lab"]
        taken.setdefault(y, set()).add(c["lab"])
        s = blob_stats(masks[y])
        rows.append({"y": y, "gap": False, "x": round(cx, 1), "z": round(cz, 1),
                     "area_mm2": round(c["area_mm2"], 1), "diam_mm": round(s["diam_mm"], 1),
                     "inscribed_mm": round(s["inscribed_mm"], 1), "solidity": round(s["solidity"], 2),
                     "aspect": round(s["aspect"], 2), "inside": round(c["inside"], 2)})
    while rows and rows[-1]["gap"]:
        rows.pop()
    return rows, masks


def merge_legs(parts):
    """Merge the DOWN and UP legs of a walk into one top-down chain."""
    by_y = {}
    for rows in parts:
        for r in rows:
            if r["y"] not in by_y or not r["gap"]:
                by_y[r["y"]] = r
    out = [by_y[y] for y in sorted(by_y, reverse=True)]
    while out and out[0]["gap"]:
        out.pop(0)
    while out and out[-1]["gap"]:
        out.pop()
    return out


# ---------------------------------------------------------------- montage
COL = {"artery": (255, 40, 40), "median_n": (255, 230, 40), "ulnar_n": (40, 255, 120), "radial_n": (80, 160, 255)}


def montage(crops, tracks, labs, path, every=14, half_mm=24):
    """Tiles centred on the artery every `every` mm with the tracked outlines drawn on the photograph. The
    human check: the ARTERY (red) is round and dark and lies in the medial bicipital groove; the MEDIAN nerve
    (yellow) is beside it and swaps sides down the arm; the ULNAR nerve (green) drifts posterior-medial away
    from it; the RADIAL nerve (blue) is behind the humerus and never in the medial groove."""
    h = int(half_mm / PX)
    art = [r for r in tracks.get("artery", []) if not r["gap"]]
    tiles = []
    for r in art[::every]:
        y = r["y"]
        im = crops.image(y)
        pr, pc = crops.atlas_to_px(y, r["x"], r["z"])
        pr, pc = int(pr), int(pc)
        vis = np.ascontiguousarray(im).copy()
        for name, rows in tracks.items():
            rr = next((q for q in rows if q["y"] == y and not q["gap"]), None)
            if rr is None or "level_index" not in rr:
                continue
            mm = np.asarray(labs[rr["level_index"], :im.shape[0], :im.shape[1]]) == rr["lab"]
            if mm.any():
                edge = ndi.binary_dilation(mm, iterations=1) & ~ndi.binary_erosion(mm)
                vis[edge] = COL[name]
        t = np.zeros((2 * h, 2 * h, 3), np.uint8)
        r0, r1 = max(0, pr - h), min(vis.shape[0], pr + h)
        c0, c1 = max(0, pc - h), min(vis.shape[1], pc + h)
        t[r0 - (pr - h):r1 - (pr - h), c0 - (pc - h):c1 - (pc - h)] = vis[r0:r1, c0:c1]
        pil = Image.fromarray(t)
        d = ImageDraw.Draw(pil)
        d.text((3, 3), f"y{int(y)} a{r['diam_mm']:.1f}mm", fill=(255, 255, 255))
        tiles.append(np.asarray(pil))
    if not tiles:
        return
    n = len(tiles)
    cols = min(6, n)
    rws = (n + cols - 1) // cols
    bar = 48
    canvas = np.zeros((rws * 2 * h + bar, cols * 2 * h, 3), np.uint8)
    for i, t in enumerate(tiles):
        canvas[(i // cols) * 2 * h:(i // cols + 1) * 2 * h, (i % cols) * 2 * h:(i % cols + 1) * 2 * h] = t
    pil = Image.fromarray(canvas)
    d = ImageDraw.Draw(pil)
    y0 = rws * 2 * h + 4
    d.text((4, y0), "VH female, RIGHT upper arm, full-resolution cryosections (0.33 mm).  "
                    "LEFT of each tile = LATERAL, RIGHT = MEDIAL;  DOWN = ANTERIOR, UP = POSTERIOR.",
           fill=(255, 255, 255))
    d.text((4, y0 + 14), "brachial artery RED (medial bicipital groove) - median n. YELLOW (beside it, lateral high "
                         "in the arm, medial at the elbow) -", fill=(255, 255, 255))
    d.text((4, y0 + 28), "ulnar n. GREEN (leaves the bundle, posterior-medial behind the medial epicondyle) - "
                         "radial n. BLUE (posterior, spiral groove).  Tile label: level y (atlas mm), artery lumen diameter.",
           fill=(255, 255, 255))
    pil.save(path)


# ---------------------------------------------------------------- entry points
def do_track(a):
    crops = Crops(a.crops, a.side)
    bf, blob = read_bundle_dir(a.bundle)
    meshes = meshes_by_id(bf, blob)
    ys_all = sorted([y for y in crops.ys if a.y_end <= y <= a.y_start], reverse=True)
    print(f"{len(ys_all)} levels, y {ys_all[0]} .. {ys_all[-1]}", flush=True)
    frame, resid = track_humerus(crops, meshes, a.side, ys_all, int(a.bone_anchor))
    fy = sorted(frame, reverse=True)
    print(f"bone frame: {sum(1 for y in frame if frame[y]['found'])}/{len(frame)} levels found, "
          f"y {fy[0]} .. {fy[-1]}", flush=True)
    ys = [y for y in ys_all if y in frame]
    idx = {y: i for i, y in enumerate(ys)}
    store_path = f"{a.out}_labels.npy"
    labs = np.lib.format.open_memmap(store_path, mode="w+", dtype=np.uint8,
                                     shape=(len(ys), crops.a.shape[1], crops.a.shape[2]))

    y0, art0, seed = seed_artery(crops, frame, a.side, ys, reach_mm=a.reach)
    down = [y for y in ys if y <= y0]
    up = [y for y in ys if y >= y0][::-1]
    legs = [walk_artery(crops, frame, a.side, leg, y0, art0["mask"], reach_mm=a.reach) for leg in (down, up)]
    art_rows = merge_legs([lg[0] for lg in legs])
    art_masks = {}
    for lg in legs:
        art_masks.update(lg[1])
    print(f"artery: {sum(1 for r in art_rows if not r['gap'])}/{len(art_rows)} levels, "
          f"y {art_rows[0]['y']} .. {art_rows[-1]['y']}", flush=True)

    art_xz = {r["y"]: (r["x"], r["z"]) for r in art_rows if not r["gap"]}
    tracks = {"artery": art_rows}
    masks_all = {"artery": art_masks}
    taken = {}
    jobs = [("median_n", y0, {"near_mm": (2.0, 20.0)}),
            ("ulnar_n", y0, {"near_mm": (4.0, 35.0)}),
            ("radial_n", int(a.radial_seed), {})]
    for name, ys0, kw in jobs:
        ys_n = sorted(art_xz, reverse=True) if name != "radial_n" else ys
        if ys0 not in ys_n:
            ys0 = min(ys_n, key=lambda v: abs(v - ys0))
        parts, nmasks = [], {}
        for leg in ([y for y in ys_n if y <= ys0], [y for y in ys_n if y >= ys0][::-1]):
            r, m = walk_nerve(crops, frame, a.side, leg, name, art_xz, taken,
                              reach_mm=a.nerve_reach, max_gap=a.nerve_gap, **kw)
            parts.append(r)
            nmasks.update(m)
        nrows = merge_legs(parts)
        print(f"{name}: {sum(1 for r in nrows if not r['gap'])}/{len(nrows)} levels"
              + (f", y {nrows[0]['y']} .. {nrows[-1]['y']}" if nrows else ""), flush=True)
        tracks[name] = nrows
        masks_all[name] = nmasks
    for name, mk in masks_all.items():
        for y, m in mk.items():
            labs[idx[y], :m.shape[0], :m.shape[1]][m] = LAB_OF[name]
    labs.flush()
    bone_track = {str(int(y)): {"x": round(frame[y]["bone_xz"][0], 1), "z": round(frame[y]["bone_xz"][1], 1),
                                "r_mm": round(frame[y]["bone_r_mm"], 1), "found": bool(frame[y]["found"])}
                  for y in sorted(frame, reverse=True)}
    for name, rws in tracks.items():
        for r in rws:
            if not r["gap"]:
                r["lab"] = LAB_OF[name]
                r["level_index"] = idx[r["y"]]
        found = [r for r in rws if not r["gap"]]
        d = {"source": SOURCE, "badge": "rule-based", "structure": name, "side": a.side,
             "seed": dict(seed, structure=name), "levels": len(rws), "tracked_levels": len(found),
             "y_top": found[0]["y"] if found else None, "y_bottom": found[-1]["y"] if found else None,
             "humerus_photographed": bone_track, "ct_to_photo_shift_mm": resid, "rows": rws}
        p = f"{a.out}_{name}.json"
        Path(p).write_text(json.dumps(d, indent=1))
        lp = p.replace(".json", "_labels.npy")
        if os.path.exists(lp):
            os.remove(lp)
        os.link(store_path, lp)
        if found:
            print(f"{name}: {len(found)}/{len(rws)} levels, y {d['y_top']} .. {d['y_bottom']}, "
                  f"median d {np.median([r['diam_mm'] for r in found]):.1f} mm")
    if a.montage:
        montage(crops, tracks, labs, a.montage, every=a.every)
        print("montage", a.montage)


def drop_intramuscular(rows, crops, labs, max_muscle=0.70):
    """A nerve of the arm lies in the intermuscular FAT, never inside a belly. Drop back to a gap any tracked
    level whose 0.7-2 mm annulus is more than `max_muscle` muscle-red - a pale blob surrounded by muscle is an
    intramuscular fat pocket or a tendon, not the nerve. Checked on the photograph, hence at cleaning time."""
    out, dropped = [], 0
    for r in rows:
        if r["gap"]:
            out.append(r)
            continue
        im = crops.image(r["y"])
        mm = np.asarray(labs[r["level_index"], :im.shape[0], :im.shape[1]]) == r["lab"]
        ring = ndi.binary_dilation(mm, structure=disk(6)) & ~ndi.binary_dilation(mm, structure=disk(2))
        mus = float(photo_classes(im)["muscle"][ring].mean()) if ring.any() else 1.0
        if mus > max_muscle:
            out.append({"y": r["y"], "gap": True, "x": r["x"], "z": r["z"], "dropped": True,
                        "muscle_ring": round(mus, 2)})
            dropped += 1
        else:
            out.append(dict(r, muscle_ring=round(mus, 2)))
    while out and out[0]["gap"]:
        out.pop(0)
    while out and out[-1]["gap"]:
        out.pop()
    return out, dropped


def do_clean(a):
    spans = {k: [float(t) if t else None for t in v.split(":")] for k, v in (sp.split("=") for sp in a.span)}
    tracks = {}
    for name in NAMES:
        src = f"{a.tracks}_{name}.json"
        if not os.path.exists(src):
            continue
        d = json.load(open(src))
        rows, dropped = clean_rows(d["rows"], name, expected=CLEAN_MM)
        if name.endswith("_n") and a.crops:
            crops_n = Crops(a.crops, a.side)
            labs_n = np.load(f"{a.tracks}_labels.npy", mmap_mode="r")
            rows, d_mus = drop_intramuscular(rows, crops_n, labs_n)
            dropped += d_mus
        top, bot = spans.get(name, (None, None))
        rows = [r for r in rows if (top is None or r["y"] <= top) and (bot is None or r["y"] >= bot)]
        while rows and rows[0]["gap"]:
            rows.pop(0)
        while rows and rows[-1]["gap"]:
            rows.pop()
        tracks[name] = rows
        found = [r for r in rows if not r["gap"]]
        d.update({"rows": rows, "cleaned_dropped": dropped, "levels": len(rows), "tracked_levels": len(found),
                  "y_top": found[0]["y"] if found else None, "y_bottom": found[-1]["y"] if found else None})
        out = f"{a.tracks}_{name}_clean.json"
        Path(out).write_text(json.dumps(d, indent=1))
        lp = out.replace(".json", "_labels.npy")
        if os.path.exists(lp):
            os.remove(lp)
        os.link(f"{a.tracks}_labels.npy", lp)
        print(f"{name}: dropped {dropped}, kept {len(found)} levels, y {d['y_top']} .. {d['y_bottom']}")
    if a.montage and a.crops:
        crops = Crops(a.crops, a.side)
        labs = np.load(f"{a.tracks}_labels.npy", mmap_mode="r")
        shown = {k: v for k, v in tracks.items() if k not in a.exclude}
        montage(crops, shown, labs, a.montage, every=a.every)
        print("montage", a.montage)


def gate(name, med, levels, span_mm=1e9):
    """The plausibility gate. A structure is NOT shipped under its anatomical name if its median lumen /
    section diameter is more than twice the textbook maximum or under half the textbook minimum (the mask has
    run into muscle, or what is left is a fragment of something else), or if it was verified over less than
    MIN_SPAN_MM of course, or on fewer than MIN_LEVELS levels. It is nulled in the volume mapping with this
    reason in its note."""
    lo, hi = EXPECTED_MM[name]
    if span_mm < MIN_SPAN_MM or levels < MIN_LEVELS:
        why = []
        if span_mm < MIN_SPAN_MM:
            why.append(f"only {span_mm:.0f} mm of course (< {MIN_SPAN_MM:.0f} mm)")
        if levels < MIN_LEVELS:
            why.append(f"only {levels} verified levels (< {MIN_LEVELS})")
        return "too short and too broken to ship under this name: " + " and ".join(why)
    if med > 2 * hi:
        return f"median section {med} mm is more than twice the expected maximum ({hi} mm)"
    if med < 0.5 * lo:
        return f"median {med} mm is far under the expected minimum ({lo} mm): a fragment, not the structure"
    return None


def band_positions(volume, labels_json, origin=ATLAS_ORIGIN, band=20):
    """Mean atlas x and z per label per `band` mm of atlas y, straight off the SHIPPED label volume (the grid's
    axes are atlas x, atlas z, atlas y + the atlas origin). On this right arm MEDIAL is smaller x and ANTERIOR
    is larger z, so the median nerve's (x - artery x) must change sign from + (lateral) high in the arm to -
    (medial) at the elbow, the ulnar nerve must end up with both offsets negative (posterior-medial), and the
    radial nerve must sit behind the artery and behind the humerus proximally."""
    import nibabel as nib
    img = nib.load(volume)
    vol = np.asarray(img.dataobj)
    aff = img.affine
    names = {int(k): v for k, v in json.load(open(labels_json))["labels"].items()}
    ijk = np.array(np.nonzero(vol))
    if not ijk.size:
        return {}
    xyz = aff[:3, :3] @ ijk + aff[:3, 3:4]
    xyz = xyz - np.array([[origin[0]], [origin[2]], [origin[1]]])     # grid axes: atlas x, atlas z, atlas y
    lab = vol[tuple(ijk)]
    y = xyz[2]
    out = {}
    lo, hi = np.floor(y.min() / band) * band, np.ceil(y.max() / band) * band
    for b0 in np.arange(hi, lo, -band):
        sel = (y <= b0) & (y > b0 - band)
        if sel.sum() < 20:
            continue
        rec = {}
        for l, nm in names.items():
            m = sel & (lab == l)
            if m.sum() >= 10:
                rec[nm] = {"x": round(float(xyz[0][m].mean()), 1), "z": round(float(xyz[1][m].mean()), 1)}
        if len(rec) >= 2:
            out[f"{int(b0 - band)}..{int(b0)}"] = rec
    return out


def relations_from_volume(bands, artery_id, side="right"):
    """Per band, each nerve's offset from the artery: lateral_mm (+ = lateral, i.e. sg*(x - artery x)) and
    anterior_mm (+ = anterior, i.e. z - artery z)."""
    sg = 1.0 if side == "right" else -1.0
    out = {}
    for b, rec in bands.items():
        if artery_id not in rec:
            continue
        a = rec[artery_id]
        row = {}
        for nm, p in rec.items():
            if nm == artery_id:
                continue
            row[nm] = {"lateral_mm": round(sg * (p["x"] - a["x"]), 1), "anterior_mm": round(p["z"] - a["z"], 1)}
        if row:
            out[b] = row
    return out


def do_report(a):
    vol = json.load(open(a.volume_report)) if a.volume_report and os.path.exists(a.volume_report) else {}
    out = {"source": SOURCE, "badge": "rule-based",
           "task": ("Q56 brachial artery with the median, ulnar and radial nerves, right upper arm "
                    "(VH female cryosections, 0.33 mm)"),
           "voxel_mm": vol.get("voxel_mm", [0.5, 0.5, 1.0]), "volume_cm3": vol.get("volume_cm3", {}),
           "volume_tracks": vol.get("tracks", {}), "expected_diameter_mm": EXPECTED_MM,
           "cleaning_band_mm": CLEAN_MM, "structures": {}, "nulled": {}, "limits": [],
           "montage": a.montage_path, "verification": {}}
    spans = {k: [float(t) if t else None for t in v.split(":")] for k, v in (sp.split("=") for sp in a.span)}
    tr = {}
    for name in NAMES:
        p = f"{a.tracks}_{name}{a.suffix}.json"
        if not os.path.exists(p):
            continue
        d = json.load(open(p))
        top, bot = spans.get(name, (None, None))
        rows = [r for r in d["rows"] if (top is None or r["y"] <= top) and (bot is None or r["y"] >= bot)]
        while rows and rows[-1]["gap"]:
            rows.pop()
        found = [r for r in rows if not r["gap"]]
        if not found:
            continue
        tr[name] = {r["y"]: r for r in found}
        dd = [r["diam_mm"] for r in found]
        ins = [r["inscribed_mm"] for r in found]
        med = round(float(np.median(dd)), 1)
        g = gate(name, med, len(found), abs(found[0]["y"] - found[-1]["y"]))
        key = f"{name}:{d['side']}"
        out["structures"][key] = {
            "atlas_id": a.ids.get(f"{name}_{d['side']}"), "shipped": g is None,
            "y_top": found[0]["y"], "y_bottom": found[-1]["y"],
            "y_span_mm": abs(found[0]["y"] - found[-1]["y"]),
            "levels": len(rows), "tracked_levels": len(found), "gaps_filled": len(rows) - len(found),
            "levels_dropped_by_cleaning": sum(1 for r in rows if r.get("dropped")),
            "diameter_mm": {"median": med, "p10": round(float(np.percentile(dd, 10)), 1),
                            "p90": round(float(np.percentile(dd, 90)), 1),
                            "inscribed_median": round(float(np.median(ins)), 1)},
            "diameter_by_level": {str(int(r["y"])): r["diam_mm"] for r in found},
            "seed": d["seed"]}
        if g:
            out["nulled"][key] = g
        if name == "artery":
            out["verification"]["humerus_ct_to_photo_shift_mm"] = {
                "note": ("the photographed humerus disc centre minus the CT humerus section centroid, per level "
                         "(row, col) in mm: why the CT is only a seed"),
                "median": [round(float(np.median([v[i] for v in d.get("ct_to_photo_shift_mm", {}).values()])), 1)
                           for i in (0, 1)] if d.get("ct_to_photo_shift_mm") else None,
                "per_level": d.get("ct_to_photo_shift_mm", {})}
    # relations measured on the TRACKS (per level), the artery as the reference
    sg = 1.0 if a.side == "right" else -1.0
    rel = {}
    for nm in ("median_n", "ulnar_n", "radial_n"):
        if nm not in tr or "artery" not in tr:
            continue
        ys = sorted(set(tr[nm]) & set(tr["artery"]), reverse=True)
        if not ys:
            continue
        latl = [sg * (tr[nm][y]["x"] - tr["artery"][y]["x"]) for y in ys]
        ante = [tr[nm][y]["z"] - tr["artery"][y]["z"] for y in ys]
        n3 = max(1, len(ys) // 3)
        rel[f"{nm}_vs_artery"] = {
            "levels": len(ys), "y_top": ys[0], "y_bottom": ys[-1],
            "lateral_mm": {"median": round(float(np.median(latl)), 1),
                           "top_third": round(float(np.median(latl[:n3])), 1),
                           "bottom_third": round(float(np.median(latl[-n3:])), 1)},
            "anterior_mm": {"median": round(float(np.median(ante)), 1),
                            "top_third": round(float(np.median(ante[:n3])), 1),
                            "bottom_third": round(float(np.median(ante[-n3:])), 1)},
            "levels_lateral": int(sum(1 for v in latl if v > 0)),
            "levels_medial": int(sum(1 for v in latl if v < 0))}
    out["verification"]["relation_to_artery_per_level"] = rel
    if a.volume and a.labels and os.path.exists(a.volume):
        bands = band_positions(a.volume, a.labels, band=a.band)
        out["verification"]["mean_atlas_x_z_per_20mm_band"] = bands
        out["verification"]["offsets_from_artery_per_20mm_band"] = relations_from_volume(
            bands, a.artery_id, a.side)
        out["verification"]["rule"] = (
            "Measured on the shipped label volume. On this RIGHT arm MEDIAL is smaller atlas x and ANTERIOR is "
            "larger atlas z, so lateral_mm = +(x - artery x) and anterior_mm = z - artery z. Expected: the "
            "MEDIAN nerve lateral (+) in the top bands and medial (-) in the bottom bands (it crosses in front "
            "of the artery about mid-arm); the ULNAR nerve medial AND posterior (both negative) in the bottom "
            "bands (it pierces the medial septum and runs behind the medial epicondyle); the RADIAL nerve "
            "posterior in the top bands, behind the artery and behind the humerus (spiral groove).")
    out["limits"] = a.limits or out["limits"]
    Path(a.out).write_text(json.dumps(out, indent=1))
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "diameter_by_level"}
                      for k, v in out["structures"].items()}, indent=1))
    print(json.dumps(out["verification"].get("offsets_from_artery_per_20mm_band", {}), indent=1))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="mode", required=True)
    t = sub.add_parser("track")
    t.add_argument("--crops", required=True)
    t.add_argument("--side", required=True, choices=["right", "left"])
    t.add_argument("--bundle", default="build/viewer_f")
    t.add_argument("--y-start", type=float, default=560)
    t.add_argument("--y-end", type=float, default=305)
    t.add_argument("--bone-anchor", type=float, default=470, help="level whose CT humerus seeds the bone frame")
    t.add_argument("--radial-seed", type=float, default=470, help="spiral-groove level the radial nerve starts at")
    t.add_argument("--out", required=True)
    t.add_argument("--montage", default=None)
    t.add_argument("--every", type=int, default=14)
    t.add_argument("--reach", type=float, default=4.0, help="mm the artery lumen may move between levels")
    t.add_argument("--nerve-reach", type=float, default=7.0, help="mm a nerve may move between levels")
    t.add_argument("--nerve-gap", type=int, default=6, help="levels without a fascicle blob before a nerve stops")
    c = sub.add_parser("clean")
    c.add_argument("--tracks", required=True)
    c.add_argument("--span", nargs="*", default=[], help="name=y_top:y_bottom, the range to ship")
    c.add_argument("--crops", default=None)
    c.add_argument("--side", default="right", choices=["right", "left"])
    c.add_argument("--montage", default=None)
    c.add_argument("--every", type=int, default=14)
    c.add_argument("--exclude", nargs="*", default=[], help="structures to leave off the montage (not shipped)")
    r = sub.add_parser("report")
    r.add_argument("--tracks", required=True)
    r.add_argument("--suffix", default="")
    r.add_argument("--side", default="right", choices=["right", "left"])
    r.add_argument("--span", nargs="*", default=[])
    r.add_argument("--ids", type=json.loads, default={})
    r.add_argument("--artery-id", default="brachial_a_r")
    r.add_argument("--band", type=int, default=20)
    r.add_argument("--volume-report", default=None)
    r.add_argument("--volume", default=None, help="shipped NIfTI, for the numeric relation check")
    r.add_argument("--labels", default=None, help="label map json of that volume")
    r.add_argument("--montage-path", default=None)
    r.add_argument("--limits", nargs="*", default=[])
    r.add_argument("--out", required=True)
    a = ap.parse_args()
    {"track": do_track, "clean": do_clean, "report": do_report}[a.mode](a)


if __name__ == "__main__":
    main()
