"""Female RIGHT hand intrinsic muscles from her FULL-RESOLUTION (0.33 mm) cryosection crops (Q62 step 4). Rule-based; badged.

    python3 scripts/cryo/vhf_stream_hand_crops.py                      # once: the hand crops (palm included)
    python3 scripts/cryo/vhf_hand_muscles_from_cryo.py --crops SCRATCH/vh_cryo_f_hand --bones build/vh/ct_vhf_armb \
        --out data/ct_sources/task_outputs/vhf_hand_muscles_cryo.nii.gz --cache SCRATCH/hand/track.pkl

DATA. SCRATCH/vh_cryo_f_hand (vhf_stream_hand_crops.py): 0.33 mm RGB crops of the right hand, one per 1 mm level of
the v1 frame (z -680 .. -810), frame rows 40-250 (the arm crops of vhf_stream_arm_crops.py start at row 110 and
cut the palm and thumb off). Level <-> atlas y and px <-> RAS as in vhf_forearm_muscles_from_cryo.py (ArmCrops is
reused unchanged: same file names). Photo top = posterior (dorsum), photo left = the subject's right (ulnar side
of the pronated hand); the hand hangs by the thigh with the palm facing antero-medially.

MAPPING CHECK. Her CT hand bones (ct_vhf_armb: carpals, metacarpals, phalanges as groups) sectioned at each level
land on the hand but 3-10 mm off the photographed bones (the CT and the frozen block are not one rigid body,
as for the forearm); they are used only to NAME the five metacarpal discs at one anchor level (a global shift
fitted between the CT loop centroids and the pale-disc peaks, then nearest assignment). The rules are built on
the metacarpals AS PHOTOGRAPHED.

RULE, per level (0.33 mm px):
  island   = the hand's own tissue component (R > B + 30, not black; the thigh shares the crop: the component
             that touches no crop edge, 3 000-60 000 px after an 8 px erosion, grown back inside the tissue);
  muscle   = 5 px-mean red channel < 100 inside the island (this hand: muscle R 50-95; the flexor tendons and
             their sheaths photograph light brown, R 100-140; fat and bone > 150);
  bones    = per metacarpal the largest circle inscribed in the pale class (5 px-mean R > 150, marrow filled)
             within 5 mm (+2 mm per level lost) of the previous level's centre, >= 2.5 mm from the skin and of
             radius >= 2.5 mm (a tendon is thinner); tracked from the anchor level in both directions; the
             segment = the levels at which MC2..MC5 are all found and at least 8 mm apart (proximal end: the
             carpometacarpal joints, where the discs merge into the carpus; distal end: the metacarpal heads,
             where the discs merge with the proximal phalanges / the interossei have become tendons);
  frame    = the MC2-MC5 line (least squares through the four centres): e = unit vector MC5 -> MC2 (ulnar ->
             radial), n = its perpendicular pointing to the side of MC1 (palmar); u = mm along e from the MC5
             centre, t = mm along n from the line (+ palmar); MC1 at (u1, t1), disc radii r1..r5;
  comps    = compartments() by textbook position (Gray's Anatomy 42nd ed. ch. 50; Moore 8th ed. ch. 6):
             hypothenar = ulnar of the MC5 centre plane (u < r5 margin) or palmar of MC5 within the disc's width;
             thenar = radial of the MC2 centre, palmar of the MC1-MC2 line and nearer MC1 than MC2 (APB, FPB, OP);
             web1 = between MC1 and MC2 (projection on the MC1->MC2 segment in (0,1)): dorsal of the MC1-MC2
             line = 1st dorsal interosseous, palmar of it = adductor pollicis (its transverse head continues
             along the palmar face of MC2-MC3, palmar of the 2nd-space interossei, radial of the MC3 centre);
             spaces 2-4 = between adjacent MC centres (projection in (0,1)): dorsal of the MC2-5 line = dorsal
             interossei, palmar of it up to the palmar bone surface + 6 mm = palmar interossei (the palmar
             interossei arise from MC2 (ulnar face), MC4 and MC5 (radial faces): the palmar half of spaces 2, 3, 4);
             palm = palmar of that cap between MC5 and MC2: lumbricals / flexor-tendon compartment;
  split    = within the thenar and hypothenar compartments a marker watershed on the white top-hat (disk 4 px)
             of the brightness (the pale septa are the ridges) from rule seeds: APB superficial radial-palmar
             (n +9 mm, e +2 from the MC1 surface), FPB palmar-ulnar (n +7, e -5), OP on the MC1 palmar surface
             (n +2, e -1); ADM ulnar subcutaneous (e -8 from the MC5 surface, n +2), FDMB palmar-ulnar (e -4,
             n +7), ODM on the MC5 palmar-ulnar surface (e -2, n +2). boundary_support scores every adjacent pair
             (mean top-hat on the boundary band / inside; >= 1.8 = the split runs on a pale line).
  merge    = muscles the photographs do not separate (volumes the muscle cannot have, or a split without a
             pale line at most levels) are merged into named compartments (vhf_hand_merge.json, --merge) and
             mapped to null with the reason in the mapping note; the per-space interossei are merged into ONE
             dorsal and ONE palmar structure (the atlas entities are groups).
LIMITS. No level-to-level tracking of the muscles; the dorsal/palmar interosseous split is the rule plane through
the shaft centres, not a photographed border; the adductor/1st DI border is the MC1-MC2 line where no septum shows;
volumes are bounded by the tracked segment (no muscle assigned proximal to the CMC joints or distal to the MC
heads, where these muscles are tendinous anyway).
Output: label volume (RAS, 0.5 x 0.5 x 1 mm) for `ingest_volume_geometry.py convert`, label key, subject mapping,
report (per-muscle volumes, boundary support, merges, literature), montage (6 levels wrist -> fingers).
"""
from __future__ import annotations

import argparse
import json
import pickle
import sys
from pathlib import Path

import numpy as np
import nibabel as nib
from PIL import Image, ImageDraw
from scipy import ndimage as ndi
from skimage.feature import peak_local_max
from skimage.morphology import white_tophat, disk
from skimage.segmentation import watershed

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.cryo.vhf_forearm_muscles_from_cryo import (  # noqa: E402
    ArmCrops, PX, H, SC, ORIGIN, load_meshes, sections, classes, pale_filled, dt_bone, bone_mask, snap,
    boundary_support, to_volume, palette)

BADGE = "rule-based"
SOURCE = ("U.S. National Library of Medicine, The Visible Human Project (public domain), female cryosections at full "
          "resolution (0.33 mm) and CT via the NCI Imaging Data Commons. Derived data "
          "(scripts/cryo/vhf_hand_muscles_from_cryo.py), rule-based.")
MC = ("mc1", "mc2", "mc3", "mc4", "mc5")
SEED_PX = 5

# per-muscle rule seeds: (anchor bone, e_mm, n_mm) from the anchor disc SURFACE (radius added along each offset)
MARKER_RULES = {
    "abductor_pollicis_brevis":       ("mc1", +2, +9, "thenar"),
    "flexor_pollicis_brevis":         ("mc1", -5, +7, "thenar"),
    "opponens_pollicis":              ("mc1", -1, +2, "thenar"),
    "abductor_digiti_minimi_hand":    ("mc5", -8, +2, "hypothenar"),
    "flexor_digiti_minimi_brevis_hand": ("mc5", -4, +7, "hypothenar"),
    "opponens_digiti_minimi":         ("mc5", -2, +2, "hypothenar"),
}
COMP_ID = {"thenar": 1, "hypothenar": 2, "adductor_pollicis": 3, "dorsal_interossei_hand": 4, "palmar_interossei": 5,
           "palmar_flexor_tendon_compartment": 6}
STRUCTS = ["abductor_pollicis_brevis", "flexor_pollicis_brevis", "opponens_pollicis", "adductor_pollicis",
           "abductor_digiti_minimi_hand", "flexor_digiti_minimi_brevis_hand", "opponens_digiti_minimi",
           "dorsal_interossei_hand", "palmar_interossei", "palmar_flexor_tendon_compartment"]
IDS = {nm: i + 1 for i, nm in enumerate(STRUCTS)}


# ----------------------------------------------------------------------------------------------- photo classes
def hand_island(im, nr, nc, erode=8):
    """The hand's tissue component: (R > B + 30, not black) closed and filled, eroded `erode` px; the component that
    touches no crop edge and has 3 000-60 000 px (the thigh is bigger: 90 000 px eroded), grown back
    inside the tissue. Returns mask or None."""
    R = im[..., 0].astype(int); B = im[..., 2].astype(int); tissue = (R > B + 30) & (im.max(-1) > 60)
    tissue[nr:] = False; tissue[:, nc:] = False
    t0 = ndi.binary_fill_holes(ndi.binary_closing(tissue, iterations=3))
    t = ndi.binary_erosion(t0, iterations=erode); lab, n = ndi.label(t); best = None
    for i in range(1, n + 1):
        m = lab == i; a = int(m.sum())
        if a < 3000 or a > 60000:
            continue
        ys, xs = np.where(m)
        if xs.max() < nc - 4 and ys.max() < nr - 4 and ys.min() > 3 and xs.min() > 3 and (best is None or a > best[0]):
            best = (a, m)
    if best is None:
        return None
    g = best[1]
    for _ in range(erode + 2):
        g = ndi.binary_dilation(g, iterations=1) & t0
    return g


# ----------------------------------------------------------------------------------------------- bone naming/tracking
def name_metacarpals(cents):
    """Five (row, col) centroids -> {mc1..mc5}. MC1 = the one farthest from the least-squares line of the other
    four (leave-one-out); MC2..MC5 = the rest ordered along that line starting at the end nearest MC1."""
    C = np.asarray(cents, float)
    if len(C) != 5:
        raise ValueError("need five centroids")
    far = []
    for i in range(5):
        o = np.delete(C, i, 0); m = o.mean(0); d = np.linalg.svd(o - m)[2][0]; v = C[i] - m
        far.append(np.hypot(*(v - np.dot(v, d) * d)))
    i1 = int(np.argmax(far)); o = np.delete(C, i1, 0); m = o.mean(0); d = np.linalg.svd(o - m)[2][0]
    s = (o - m) @ d
    if np.dot(C[i1] - m, d) < 0:
        s = -s
    order = np.argsort(-s)                     # nearest MC1 first
    out = {"mc1": tuple(C[i1])}
    for k, idx in enumerate(order):
        out[f"mc{k + 2}"] = tuple(o[idx])
    return out


def match_shift(ct, peaks, max_mm=15.0):
    """Global translation (rows, cols, px) that best maps the CT loop centroids onto the pale-disc peaks: for every
    CT-peak pairing as the candidate shift, the sum of nearest-peak distances (capped at max_mm); the best shift and
    the nearest peak per CT centroid (None if farther than max_mm)."""
    ct = np.asarray(ct, float); pk = np.asarray(peaks, float); best = (np.inf, np.zeros(2))
    for a in ct:
        for b in pk:
            sh = b - a; d = np.linalg.norm((ct + sh)[:, None, :] - pk[None, :, :], axis=2).min(1) * PX
            cost = np.minimum(d, max_mm).sum()
            if cost < best[0]:
                best = (cost, sh)
    sh = best[1]; assign = []
    for a in ct:
        d = np.linalg.norm(pk - (a + sh), axis=1) * PX; k = int(np.argmin(d)); assign.append(k if d[k] <= max_mm else None)
    return sh, assign


def level_data(crops, j):
    L = crops.level(j); im = crops.image(j); nr, nc = L["w"][1] - L["w"][0], L["w"][3] - L["w"][2]
    isl = hand_island(im, nr, nc)
    if isl is None:
        return None
    cl = classes(im, isl); pale = pale_filled(cl, isl, marrow_mm2=120.0)
    return {"L": L, "im": im, "island": isl, "cl": cl, "pale": pale, "dt": ndi.distance_transform_edt(pale),
            "dist": ndi.distance_transform_edt(isl)}


def ct_bodies(meshes):
    """Her CT metacarpal group mesh split into bodies: the three with > 1 cm3 sorted by RAS x are MC1 (most radial =
    lowest x on the right hand), MC2, and the fused MC3-5 block (a 1.5 mm CT: their bases touch)."""
    parts = [p for p in meshes["metacarpals_r"].split(only_watertight=False) if p.is_volume and p.volume > 1000.0]
    parts.sort(key=lambda p: p.bounds[:, 0].mean())
    if len(parts) != 3:
        raise SystemExit(f"CT metacarpal mesh splits into {len(parts)} bodies > 1 cm3, expected MC1, MC2, MC3-5")
    return {"mc1": parts[0], "mc2": parts[1], "mc345": parts[2]}


def ct_centroids(bodies, crops, L, shape, prev=None):
    """CT metacarpal centroids (px) at a level: {mc1, mc2, mc3, mc4, mc5} (missing where the body has no section).
    The fused MC3-5 block is split into three by k-means on its section pixels, initialised from the previous
    level's three centroids (`prev`); without them (the anchor level) the block must give three loops, named by
    their order along the block's line starting at the end nearest MC2."""
    out = {}
    for nm in ("mc1", "mc2"):
        se = sections({nm: bodies[nm]}, crops, L, shape, (nm,))
        if nm in se:
            out[nm] = tuple(np.mean(np.where(se[nm]), axis=1))
    se = sections({"g": bodies["mc345"]}, crops, L, shape, ("g",))
    if "g" not in se:
        return out
    pts = np.argwhere(se["g"]).astype(float)
    if prev is not None and all(b in prev for b in ("mc3", "mc4", "mc5")) and len(pts) >= 30:
        C = np.array([prev[b] for b in ("mc3", "mc4", "mc5")], float)
        for _ in range(10):
            k = np.argmin(np.linalg.norm(pts[:, None, :] - C[None], axis=2), axis=1)
            for q in range(3):
                if (k == q).any():
                    C[q] = pts[k == q].mean(0)
        for q, b in enumerate(("mc3", "mc4", "mc5")):
            out[b] = tuple(C[q])
        return out
    gl, gn = ndi.label(se["g"]); cs = [np.mean(np.where(gl == i), axis=1) for i in range(1, gn + 1)]
    cs = [c for c, a in zip(cs, ndi.sum(se["g"], gl, range(1, gn + 1))) if a >= 40]
    if len(cs) == 3:
        C = np.array(cs); m = C.mean(0); d = np.linalg.svd(C - m)[2][0]; sc = (C - m) @ d
        ref = np.array(out.get("mc2", C[np.argmax(np.linalg.norm(C - m, axis=1))]))
        if np.dot(ref - m, d) < 0:
            sc = -sc
        for k, idx in enumerate(np.argsort(-sc)):
            out[f"mc{k + 3}"] = tuple(C[idx])
    return out


def detect_level(d, ct, skin_mm=2.5, min_r_mm=2.5):
    """Photographed discs at one level from the CT centroids alone: the peaks of the pale class's distance transform
    (>= skin_mm from the skin, radius >= min_r_mm); the CT centroids of MC2-5, moved by the global shift that best
    lays them on the peaks (match_shift), each take the nearest peak within 6 mm; MC1 the nearest peak of radius
    >= 3 mm within 8 mm of its shifted centroid. Returns (rec, shift_px) with rec[b] = (cy, cx, r_px, mask) or None."""
    rec = {"found": {b: False for b in MC}}
    for b in MC:
        rec[b] = None
    ok = d["dist"] * PX >= skin_mm
    pk = peak_local_max(np.where(ok, d["dt"], 0), min_distance=10, threshold_abs=min_r_mm / PX, labels=d["pale"].astype(int))
    names = [b for b in MC[1:] if b in ct]
    if len(pk) == 0 or len(names) < 3:
        return rec, None
    sh, assign = match_shift([ct[b] for b in names], pk, max_mm=6.0); used = set()
    for b, a in zip(names, assign):
        if a is None or a in used:
            continue
        used.add(a); y, x = pk[a]; r = float(d["dt"][y, x])
        rec[b] = (float(y), float(x), r, bone_mask(d["pale"], y, x, r)); rec["found"][b] = True
    if "mc1" in ct:
        c = np.array(ct["mc1"]) + sh; best = None
        for k, (y, x) in enumerate(pk):
            if k in used or d["dt"][y, x] * PX < 3.0:
                continue
            dd = np.hypot(y - c[0], x - c[1]) * PX
            if dd <= 8.0 and (best is None or dd < best[0]):
                best = (dd, k)
        if best is not None:
            y, x = pk[best[1]]; r = float(d["dt"][y, x]); rec["mc1"] = (float(y), float(x), r, bone_mask(d["pale"], y, x, r)); rec["found"]["mc1"] = True
    return rec, sh


def track_metacarpals(crops, meshes, j_anchor, j_lo, j_hi, log=print, skin_mm=2.5, min_r_mm=1.5, search_mm=4.0):
    """{j: {'mc1'..'mc5': (cy, cx, r_px, mask) or None, 'found', 'predicted', 'island', 'cl', 'im', 'L', 'pale', 'ct'}}
    and residual {bone: {j: [rows, cols] mm}}. At j_anchor the five discs are named from the CT bodies (detect_level:
    all five found, MC2-5 in the CT order along their line). At every other level each bone is PREDICTED from its
    CT centroid plus the CT->photo residual measured at the nearest processed level (the median over the bones
    found there; the residual is 10-15 mm and slowly varying, see the report), then the disc = the largest circle
    inscribed in the pale class within search_mm of the prediction, >= skin_mm from the skin, radius >= min_r_mm
    (MC1 3 mm), capped at 6 mm (MC1 8 mm: the pale class merges a bone with pale fat or tendon beside it). A bone
    with no disc keeps the predicted centre and its last radius ('predicted'); a bone whose CT body has no section
    at the level, or whose prediction falls outside the hand's island (the thumb leaves it distally), is absent."""
    bodies = ct_bodies(meshes); D = level_data(crops, j_anchor)
    if D is None:
        raise SystemExit(f"no hand island at anchor level {j_anchor}")
    ct0 = ct_centroids(bodies, crops, D["L"], D["im"].shape[:2]); rec0, sh = detect_level(D, ct0, skin_mm, 2.5)
    if not all(rec0["found"].values()):
        raise SystemExit(f"anchor level {j_anchor}: found only {[b for b in MC if rec0['found'][b]]}")
    named = name_metacarpals([rec0[b][:2] for b in MC])
    if any(np.hypot(named[b][0] - rec0[b][0], named[b][1] - rec0[b][1]) > 1 for b in MC):
        raise SystemExit(f"anchor level {j_anchor}: the CT order of the discs disagrees with their geometry")
    log(f"anchor j{j_anchor}: CT->photo shift {[round(float(v * PX), 1) for v in sh]} mm, radii " + ", ".join(f"{b} {rec0[b][2] * PX:.1f}" for b in MC))
    out = {}; residual = {}; cap = {b: (8.0 if b == "mc1" else 6.0) / PX for b in MC}

    def one(j, res_prev, r_prev, ct_prev):
        d = level_data(crops, j)
        if d is None:
            return None, res_prev, r_prev
        rec = dict(d); rec["found"] = {}; rec["predicted"] = {}; rec["ct"] = ct_centroids(bodies, crops, d["L"], d["im"].shape[:2], ct_prev); found_res = []
        for b in MC:
            rec[b] = None; rec["found"][b] = False; rec["predicted"][b] = False
            if b not in rec["ct"]:
                continue
            pred = np.array(rec["ct"][b]) + res_prev; pr, pc = int(round(pred[0])), int(round(pred[1]))
            if not (0 <= pr < d["island"].shape[0] and 0 <= pc < d["island"].shape[1] and d["island"][pr, pc]):
                continue
            h = dt_bone(d["dt"], d["dist"], pred, search_mm, skin_mm=skin_mm, min_r_mm=3.0 if b == "mc1" else min_r_mm)
            if h is not None:
                r = min(h[2], cap[b]); rec[b] = (h[0], h[1], r, bone_mask(d["pale"], h[0], h[1], r)); rec["found"][b] = True
                found_res.append(np.array(h[:2]) - np.array(rec["ct"][b]))
                residual.setdefault(b, {})[j] = [round(float(found_res[-1][0] * PX), 1), round(float(found_res[-1][1] * PX), 1)]
            else:
                rec[b] = (float(pred[0]), float(pred[1]), r_prev[b], None); rec["found"][b] = True; rec["predicted"][b] = True
        if found_res:
            res_prev = np.median(np.array(found_res), axis=0)
        r_prev = {b: (rec[b][2] if rec[b] is not None else r_prev[b]) for b in MC}
        return rec, res_prev, r_prev

    res0 = np.median(np.array([np.array(rec0[b][:2]) - np.array(ct0[b]) for b in MC[1:]]), axis=0); r0 = {b: rec0[b][2] for b in MC}
    out[j_anchor], _, _ = one(j_anchor, res0, r0, ct0)
    for rng in (range(j_anchor - 1, j_lo - 1, -1), range(j_anchor + 1, j_hi + 1)):
        res_prev, r_prev, ct_prev = res0, dict(r0), ct0
        for j in rng:
            r, res_prev, r_prev = one(j, res_prev, r_prev, ct_prev)
            if r is not None:
                ct_prev = {**ct_prev, **r["ct"]}
            if r is None:
                log(f"  track stops at level {j} (no island)"); break
            out[j] = r
            if not any(r["found"].values()):
                log(f"  track stops at level {j} (no CT metacarpal section)"); break
    return out, residual


def segment_bounds(track, min_sep_mm=6.0):
    """Levels at which MC2..MC5 are all present (photographed or CT-predicted) and every adjacent pair of discs is
    >= min_sep_mm apart (centre to centre): the longest run of such levels."""
    good = []
    for j in sorted(track):
        t = track[j]
        if not all(t["found"][b] for b in MC[1:]):
            good.append(False); continue
        seps = [np.hypot(t[a][0] - t[b][0], t[a][1] - t[b][1]) * PX for a, b in zip(MC[1:], MC[2:])]
        good.append(min(seps) >= min_sep_mm)
    js = sorted(track); best = (0, None, None); k = 0
    while k < len(js):
        if good[k]:
            m = k
            while m + 1 < len(js) and good[m + 1]:
                m += 1
            if m - k + 1 > best[0]:
                best = (m - k + 1, js[k], js[m])
            k = m + 1
        else:
            k += 1
    return best[1], best[2]


# ----------------------------------------------------------------------------------------------- pure rules
def hand_frame(P, n_prev=None):
    """P: {'mc1'..'mc5': (row, col) or None} with MC2..MC5 present. Returns (e, n, m): e = unit vector MC5 -> MC2
    (ulnar -> radial) along the least-squares line through the four centres, n = its perpendicular pointing to the
    palmar side (the side of MC1; else the side of n_prev; else raises), m = the line's centroid (rows, cols)."""
    C = np.array([P[b] for b in MC[1:]], float); m = C.mean(0); d = np.linalg.svd(C - m)[2][0]
    if np.dot(np.array(P["mc2"]) - np.array(P["mc5"]), d) < 0:
        d = -d
    e = d / np.hypot(*d); n = np.array([-e[1], e[0]])
    if P.get("mc1") is not None:
        if np.dot(np.array(P["mc1"]) - m, n) < 0:
            n = -n
    elif n_prev is not None:
        if np.dot(n, n_prev) < 0:
            n = -n
    else:
        raise ValueError("palmar side undefined: no MC1 and no previous orientation")
    return e, n, m


def _seg_coords(shape, A, B):
    """Per pixel: s = projection fraction on the segment A -> B (0 at A, 1 at B) and t = signed distance from its
    line in mm (positive to the left of A -> B in (row, col) space: the caller orients it)."""
    yy, xx = np.mgrid[0:shape[0], 0:shape[1]]; A = np.asarray(A, float); B = np.asarray(B, float); v = B - A; L = np.hypot(*v); v = v / L
    py = yy - A[0]; px = xx - A[1]; s = (py * v[0] + px * v[1]) / L; t = (py * -v[1] + px * v[0]) * PX
    return s, t


def compartments(shape, P, R, e, n, real=None, cap_mm=3.0, adductor_mm=8.0):
    """Pixel -> compartment id (COMP_ID; 0 = none) by the textbook layering rules (see the module docstring), from the
    metacarpal centres P (rows, cols; 'mc1' may be None), radii R (px), the hand frame (e ulnar -> radial, n palmar)
    and `real` (the bones photographed or CT-predicted at this level; the others are carried from a neighbouring
    level and get no interosseous space). Spaces 2-4 (between adjacent MC2-5 centres): dorsal of the line through
    the two centres = dorsal interossei; palmar of it up to (larger disc radius + cap_mm) = palmar interossei.
    Palmar of that cap: hypothenar ulnar of the MC4 centre; the palm (lumbricals / flexor-tendon compartment)
    between the MC4 and MC3 centres; radial of the MC3 centre the adductor pollicis band (transverse head on the
    MC3 shaft and the 2nd-space interossei, adductor_mm thick) and, beyond it, the thenar (APB, FPB, OP lie
    superficial to the adductor and the FPL tendon). Radial of MC2: the same layering from the MC2 surface;
    with MC1: dorsal of the MC1-MC2 line between them = 1st dorsal interosseous, radial of MC1 = thenar.
    Hypothenar also = ulnar of the MC5 centre plane (u < 0)."""
    real = set(MC) if real is None else set(real)
    comp = np.zeros(shape, np.uint8); yy, xx = np.mgrid[0:shape[0], 0:shape[1]]
    P5 = np.array(P["mc5"], float); u = ((yy - P5[0]) * e[0] + (xx - P5[1]) * e[1]) * PX
    u_of = {b: float(((np.array(P[b]) - P5) @ e) * PX) for b in MC[1:]}
    assigned = np.zeros(shape, bool)

    def coords(a, b):
        s_, t_ = _seg_coords(shape, P[a], P[b]); v = np.array(P[b], float) - np.array(P[a], float)
        return s_, (-t_ if np.dot(np.array([-v[1], v[0]]), n) < 0 else t_)         # t + palmar

    for a, b in (("mc2", "mc3"), ("mc3", "mc4"), ("mc4", "mc5")):
        s, t = coords(a, b); cap = max(R[a], R[b]) * PX + cap_mm; inside = (s >= 0) & (s <= 1) & ~assigned
        if a in real and b in real:
            comp[inside & (t < 0)] = COMP_ID["dorsal_interossei_hand"]
            comp[inside & (t >= 0) & (t <= cap)] = COMP_ID["palmar_interossei"]
        beyond = inside & (t > cap)
        comp[beyond & (u <= u_of["mc4"])] = COMP_ID["hypothenar"]
        comp[beyond & (u > u_of["mc4"]) & (u < u_of["mc3"])] = COMP_ID["palmar_flexor_tendon_compartment"]
        comp[beyond & (u >= u_of["mc3"]) & (t <= cap + adductor_mm)] = COMP_ID["adductor_pollicis"]
        comp[beyond & (u >= u_of["mc3"]) & (t > cap + adductor_mm)] = COMP_ID["thenar"]
        assigned |= inside
    # ulnar of MC5 and palmar of the 4-5 cap: hypothenar
    s45, t45 = coords("mc5", "mc4")
    hypo = ((u < 0) | ((u <= u_of["mc4"]) & (t45 > max(R["mc4"], R["mc5"]) * PX + cap_mm))) & ~assigned
    comp[hypo] = COMP_ID["hypothenar"]; assigned |= hypo
    # radial of MC2: the same layering measured from the MC2-3 line (s > 1 on it), palmar side
    s23, t23 = coords("mc2", "mc3"); cap2 = R["mc2"] * PX + cap_mm; rad = (s23 < 0) & ~assigned      # s < 0: beyond MC2 (radial)
    if P.get("mc1") is not None:
        s12, t12 = coords("mc1", "mc2"); web = (s12 >= 0) & (s12 <= 1) & rad
        if "mc2" in real:
            comp[web & (t12 < 0) & (t23 < cap2)] = COMP_ID["dorsal_interossei_hand"]          # 1st dorsal interosseous
        comp[web & ((t12 >= 0) | (t23 >= cap2)) & (t23 <= cap2 + adductor_mm)] = COMP_ID["adductor_pollicis"]
        comp[web & ((t12 >= 0) | (t23 >= cap2)) & (t23 > cap2 + adductor_mm)] = COMP_ID["thenar"]
        comp[rad & (s12 < 0)] = COMP_ID["thenar"]                                                # radial of MC1
        comp[rad & (s12 > 1) & (t23 >= 0) & (t23 <= cap2 + adductor_mm)] = COMP_ID["adductor_pollicis"]
        comp[rad & (s12 > 1) & (t23 > cap2 + adductor_mm)] = COMP_ID["thenar"]
    else:
        comp[rad & (t23 >= 0) & (t23 <= cap2 + adductor_mm)] = COMP_ID["adductor_pollicis"]
        comp[rad & (t23 > cap2 + adductor_mm)] = COMP_ID["thenar"]
    return comp


def marker_positions(P, R, e, n):
    """Rule seeds {name: (row, col)} in px from MARKER_RULES: offsets in mm from the anchor disc's SURFACE along
    e_loc / n (the thenar's e_loc is the MC2 -> MC1 direction, i.e. radial; the hypothenar's the frame's e)."""
    out = {}
    for name, (anc, em, nm, grp) in MARKER_RULES.items():
        if P.get(anc) is None:
            continue
        base = np.array(P[anc], float); rad = R[anc]
        if anc == "mc1" and P.get("mc2") is not None:
            el = base - np.array(P["mc2"], float); el = el / np.hypot(*el)
        else:
            el = e
        ev = em / PX + (np.sign(em) * rad if em else 0.0); nv = nm / PX + (np.sign(nm) * rad if nm else 0.0)
        out[name] = tuple(base + el * ev + n * nv)
    return out


# ----------------------------------------------------------------------------------------------- per-level split
def level_region(t):
    """The muscle mass to split: muscle class closed 1 mm, seams <= 8 mm2 filled, bone discs (+2 px) out."""
    isl = t["island"]; cl = t["cl"]; region = ndi.binary_closing(cl["muscle"], iterations=3) & isl
    holes = ndi.binary_fill_holes(region) & ~region; hl, hn = ndi.label(holes)
    if hn:
        hs = ndi.sum(holes, hl, range(1, hn + 1)); small = np.zeros(hn + 1, bool); small[1:] = hs * PX * PX <= 8.0; region |= small[hl]
    bones = np.zeros(isl.shape, bool)
    for b in MC:
        if t.get(b) is not None and t[b][3] is not None:
            bones |= ndi.binary_dilation(t[b][3], iterations=2)
    return region & ~bones


def split_level(th, region, comp, seeds):
    """Thenar and hypothenar: a marker watershed of the compartment's muscle on the top-hat `th` from the rule seeds
    (1.7 mm discs snapped into the compartment within 5 mm); the other compartments are single structures.
    Returns {name: mask}."""
    out = {}
    for grp in ("thenar", "hypothenar"):
        reg = region & (comp == COMP_ID[grp]); markers = np.zeros(region.shape, np.int32)
        for name, (anc, em, nm, g) in MARKER_RULES.items():
            if g != grp or name not in seeds:
                continue
            p = snap(seeds[name], reg & (markers == 0))
            if p is None:
                continue
            z = np.zeros(region.shape, bool); z[p] = True
            markers[ndi.binary_dilation(z, iterations=SEED_PX) & reg & (markers == 0)] = IDS[name]
        if not markers.any():
            continue
        ws = watershed(th, markers, mask=reg)
        for name in MARKER_RULES:
            m = ws == IDS[name]
            if m.any():
                out[name] = m
    for name in ("adductor_pollicis", "dorsal_interossei_hand", "palmar_interossei", "palmar_flexor_tendon_compartment"):
        m = region & (comp == COMP_ID[name]) & ~np.any([out.get(k, np.zeros(region.shape, bool)) for k in out], axis=0) if out else region & (comp == COMP_ID[name])
        if m.any():
            out[name] = m
    return out


# ----------------------------------------------------------------------------------------------- main
def carried_positions(track, j, max_gap=25):
    """{bone: (row, col, r_px)} at level j: the bone's own record where present, else the nearest level's within
    max_gap levels (the metacarpal bases continue into the carpal columns: a proxy frame for the thenar and
    hypothenar origins at the carpus). Returns (positions, real bones)."""
    P = {}; real = set(); t = track[j]
    for b in MC:
        if t.get(b) is not None and t["found"][b]:
            P[b] = t[b][:3]; real.add(b); continue
        if b == "mc1":
            continue                                                       # the thumb is never carried (it leaves the island)
        for k in range(1, max_gap + 1):
            hit = None
            for jj in (j - k, j + k):
                tt = track.get(jj)
                if tt is not None and tt.get(b) is not None and tt["found"][b]:
                    hit = tt[b][:3]; break
            if hit is not None:
                P[b] = hit; break
    return P, real


def run(a, log=print):
    crops = ArmCrops(a.crops); meshes = load_meshes(a.bones); cache = Path(a.cache) if a.cache else None
    if cache and cache.exists():
        track, residual = pickle.load(open(cache, "rb")); log(f"bone track from cache {cache}")
    else:
        track, residual = track_metacarpals(crops, meshes, a.anchor, a.j_lo, a.j_hi, log)
        if cache:
            pickle.dump((track, residual), open(cache, "wb"), protocol=4)
    j_top, j_bot = segment_bounds(track)
    if j_top is None:
        raise SystemExit("no level with four separate MC2-5 discs")
    j_first = min(j for j in track if any(track[j]["found"].values()))
    log(f"segment levels {j_first}..{j_bot} (four separate MC2-5 discs from {j_top}; atlas y {crops.level(j_first)['y']:.0f} .. {crops.level(j_bot)['y']:.0f})")
    labels_by_level = {}; area = {nm: 0.0 for nm in STRUCTS}; unassigned = 0.0; frames = {}; support = {}; n_prev = None
    for j in range(j_top, j_bot + 1):
        t = track.get(j)
        if t is None or not all(t["found"][b] for b in MC[1:]):
            continue
        P = {b: (t[b][:2] if t.get(b) is not None and t["found"][b] else None) for b in MC}
        e, n, m = hand_frame(P, n_prev); n_prev = n
        if n_prev is not None:
            break
    for j in list(range(j_top - 1, j_first - 1, -1)) + list(range(j_top, j_bot + 1)):
        t = track.get(j)
        if t is None:
            continue
        pos, real = carried_positions(track, j)
        if not all(b in pos for b in MC[1:]):
            continue
        P = {b: (pos[b][:2] if b in pos else None) for b in MC}; R = {b: (pos[b][2] if b in pos else 0.0) for b in MC}
        e, n, m = hand_frame(P, n_prev)
        if j >= j_top:
            n_prev = n
        region = level_region(t); comp = compartments(region.shape, P, R, e, n, real)
        th = white_tophat(t["im"].max(-1).astype(np.float32), disk(4)); seeds = marker_positions(P, R, e, n)
        cur = split_level(th, region, comp, seeds)
        frames[j] = {"P": {b: (list(map(float, v)) if v is not None else None) for b, v in P.items()}, "R": {b: float(v) for b, v in R.items()},
                     "real": sorted(real), "e": e.tolist(), "n": n.tolist(), "seeds": {nm: [float(p[0]), float(p[1])] for nm, p in seeds.items()}}
        lab = np.zeros(region.shape, np.uint8)
        for nm, mk in cur.items():
            area[nm] += mk.sum() * PX * PX; lab[mk] = IDS[nm]
        unassigned += (region & (lab == 0)).sum() * PX * PX
        for pair, v in boundary_support(th, {k: v for k, v in cur.items() if MARKER_RULES.get(k)}, IDS).items():
            support.setdefault(pair, []).append((j,) + v)
        labels_by_level[j] = lab
        if j % 10 == 0:
            log(f"  level {j} y={t['L']['y']:.0f} regions={len(cur)} real={sorted(real)} unassigned={(region & (lab == 0)).sum() * PX * PX:.0f} mm2")
    return crops, track, residual, (j_first, j_bot), labels_by_level, area, unassigned, frames, support


def montage(crops, track, labels_by_level, names, frames, levels, path, colors):
    tiles = []
    for j in levels:
        t = track.get(j); lab = labels_by_level.get(j)
        if t is None or lab is None:
            continue
        im = t["im"].copy(); isl = t["island"]; ys, xs = np.where(isl)
        r0, r1, c0, c1 = max(0, ys.min() - 6), ys.max() + 6, max(0, xs.min() - 6), xs.max() + 6
        for l, nm in names.items():
            mk = lab == l
            if mk.any():
                edge = mk & ~ndi.binary_erosion(mk, iterations=2); im[edge] = colors[l]
        for b in MC:
            if t.get(b) is not None and t[b][3] is not None:
                ed = t[b][3] & ~ndi.binary_erosion(t[b][3], iterations=2); im[ed] = (255, 255, 255)
        sub = Image.fromarray(im[r0:r1, c0:c1]); dr = ImageDraw.Draw(sub); fr = frames.get(j)
        if fr:
            pts = [fr["P"][b] for b in MC[1:] if fr["P"][b] is not None]
            for A, B in zip(pts, pts[1:]):
                dr.line([(A[1] - c0, A[0] - r0), (B[1] - c0, B[0] - r0)], fill=(255, 255, 255), width=1)
            for b in MC:
                if fr["P"][b] is not None:
                    dr.text((fr["P"][b][1] - c0 - 3, fr["P"][b][0] - r0 - 5), b[2], fill=(255, 255, 255))
            for nm, p in fr["seeds"].items():
                y, x = p[0] - r0, p[1] - c0; col = colors[IDS[nm]]
                dr.line([(x - 4, y), (x + 4, y)], fill=col, width=2); dr.line([(x, y - 4), (x, y + 4)], fill=col, width=2)
        dr.text((3, 3), f"j{j} y{t['L']['y']:.0f}", fill=(255, 255, 0))
        for l, nm in names.items():
            mk = lab[r0:r1, c0:c1] == l
            if mk.sum() > 60:
                cy, cx = np.mean(np.where(mk), axis=1)
                dr.text((cx - 8, cy - 4), "".join(w[0] for w in nm.split("_")).upper(), fill=colors[l])
        tiles.append(sub)
    if not tiles:
        return None
    cols = 3; rows = (len(tiles) + cols - 1) // cols; tw = max(t.width for t in tiles); th = max(t.height for t in tiles)
    out = Image.new("RGB", (cols * tw, rows * th))
    for i, t in enumerate(tiles):
        out.paste(t, ((i % cols) * tw, (i // cols) * th))
    out.save(path); return str(path)


LITERATURE = {
    "note": "Verified through PubMed on 2026-09-14 (abstracts only).",
    "thenar_total_cm3": {"value": 13.0, "range": [7.6, 15.8], "who": "13 healthy controls aged 9.5-25.4 years, right hand, quantitative MRI (total volume)",
                         "ref": "Naarding KJ et al. J Cachexia Sarcopenia Muscle 2021;12:694-703, doi:10.1002/jcsm.12711 (PMID 33963807)"},
    "architecture": {"ref": "Jacobson MD, Raab R, Fazeli BM, Abrams RA, Botte MJ, Lieber RL. Architectural design of the human intrinsic hand muscles. "
                            "J Hand Surg Am 1992;17:804-9, doi:10.1016/0363-5023(92)90446-v (PMID 1401784)",
                     "note": "muscle mass, length, PCSA of 18 intrinsics (cadaveric); the per-muscle masses are in the paper's tables, not verified here"},
    "hypothenar_cm3": "not verified", "adductor_pollicis_cm3": "not verified", "interossei_cm3": "not verified",
}

# plausibility windows for an adult female hand (cm3), from the task brief / Jacobson 1992 order of magnitude:
# the SHIPPED structure -> (low, high, what the window covers). A volume outside a window is flagged REVIEW in the
# report and in the mapping note; more than twice outside it is not shipped by name (atlas_id null).
PLAUSIBLE = {"thenar_compartment": (10.0, 20.0, "APB + FPB + OP together"),
             "abductor_pollicis_brevis": (2.0, 8.0, "part of the 10-20 cm3 thenar group"),
             "flexor_pollicis_brevis": (2.0, 8.0, "part of the 10-20 cm3 thenar group"),
             "opponens_pollicis": (2.0, 8.0, "part of the 10-20 cm3 thenar group"),
             "adductor_pollicis": (5.0, 8.0, "adductor pollicis, both heads"),
             "abductor_digiti_minimi_hand": (2.5, 7.0, "part of the 8-15 cm3 hypothenar group"),
             "flexor_digiti_minimi_brevis_hand": (1.0, 5.0, "part of the 8-15 cm3 hypothenar group"),
             "opponens_digiti_minimi": (1.5, 5.5, "part of the 8-15 cm3 hypothenar group"),
             "dorsal_interossei_hand": (8.0, 16.0, "four dorsal interossei, 2-4 cm3 per space"),
             "palmar_interossei": (4.5, 12.0, "three palmar interossei, 1.5-4 cm3 each")}
NOT_SHIPPED = {
    "palmaris_brevis": "a 1 mm subcutaneous sheet of transverse fibres in the hypothenar fat: below the muscle class's "
                       "reach at 0.33 mm (it photographs as streaks in the fat, not as a body); no rule seeds it.",
    "lumbricals_hand": "carried in palmar_flexor_tendon_compartment: in the mid-palm the four lumbricals photograph as "
                       "the dark walls of the flexor sheaths radial to the profundus tendons; no muscle blob separates "
                       "from the tendon mass at 0.33 mm, so lumbricals_hand_r is not shipped.",
    "dorsal_interossei_per_space": "the four dorsal interossei are shipped as ONE structure (the atlas entity "
                                   "dorsal_interossei_hand_r is a group); the per-space split is in the volume's geometry only.",
    "palmar_interossei_per_space": "the three palmar interossei are shipped as ONE structure (the atlas entity "
                                   "palmar_interossei_r is a group).",
    "thumb_distal_to_the_web": "at the levels where the thumb's section leaves the palm's tissue island (this hand lies "
                               "with the thumb off the palm) the thenar muscles are outside the segmented island; the "
                               "thenar volume is bounded by the levels where the thumb is still attached.",
}
LIMITS = [
    "boundaries are position rules in the metacarpal frame plus a marker watershed on the pale septa, not traced fascia",
    "the dorsal / palmar interosseous border is the rule plane through the adjacent metacarpal shaft centres, not a photographed border",
    "the adductor pollicis / 1st dorsal interosseous border is the MC1-MC2 centre line, where no septum shows",
    "no level-to-level tracking of the muscles themselves (only the metacarpal discs are tracked)",
    "volumes are bounded by the tracked segment: nothing proximal to the carpometacarpal joints or distal to the metacarpal heads",
    "the CT hand bones are 3-10 mm off the photographed bones (the CT and the frozen block are not one rigid body); they "
    "name the five discs at one anchor level only, the rules run on the metacarpals as photographed",
]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--crops", required=True, help="SCRATCH/vh_cryo_f_hand (vhf_stream_hand_crops.py)")
    ap.add_argument("--bones", default=str(REPO / "build/vh/ct_vhf_armb"))
    ap.add_argument("--anchor", type=int, default=45, help="crop level where the CT metacarpal bodies name the five photographed discs")
    ap.add_argument("--j-lo", type=int, default=15); ap.add_argument("--j-hi", type=int, default=115)
    ap.add_argument("--out", default=str(REPO / "data/ct_sources/task_outputs/vhf_hand_muscles_cryo.nii.gz"))
    ap.add_argument("--labels-out", default=str(REPO / "mappings/vhf_hand_muscles_labels.json"))
    ap.add_argument("--mapping-out", default=str(REPO / "mappings/subjects/ct_vhf_hand_volume_mapping.json"))
    ap.add_argument("--montage", default=str(REPO / "data/ct_sources/task_outputs/vhf_hand_muscles_cryo.png")); ap.add_argument("--montage-levels", default="")
    ap.add_argument("--cache", default=None, help="pickle of the bone track (scratch only; speeds up re-runs)")
    ap.add_argument("--merge", default=str(REPO / "scripts/cryo/vhf_hand_merge.json"),
                    help="JSON {merged_name: {members, note}} of muscles the photographs do not separate (compartments, mapped to null)")
    a = ap.parse_args(argv)
    crops, track, residual, (j_top, j_bot), labels_by_level, area, unassigned, frames, support = run(a)
    merge_raw = json.load(open(a.merge)) if a.merge and Path(a.merge).exists() else {}
    merge = {k: (v["members"] if isinstance(v, dict) else v) for k, v in merge_raw.items() if not k.startswith("_")}
    merge_note = {k: v.get("note", "") for k, v in merge_raw.items() if isinstance(v, dict)}
    final_ids = dict(IDS); final_names = {l: nm for nm, l in IDS.items()}; remap = np.arange(max(IDS.values()) + 1, dtype=np.uint8)
    for comp, members in merge.items():
        keep = IDS[members[0]]
        for mm in members:
            remap[IDS[mm]] = keep; final_ids.pop(mm, None)
        final_ids[comp] = keep; final_names[keep] = comp
        for mm in members[1:]:
            final_names.pop(IDS[mm], None)
    for j in labels_by_level:
        labels_by_level[j] = remap[labels_by_level[j]]
    vol, aff = to_volume(crops, labels_by_level); vox = float(abs(np.linalg.det(aff[:3, :3])))
    vols = {nm: round(float((vol == l).sum() * vox / 1000.0), 2) for nm, l in sorted(final_ids.items(), key=lambda kv: kv[1])}
    for l in list(final_names):
        if vols.get(final_names[l], 0) == 0:
            final_ids.pop(final_names[l], None); final_names.pop(l)
    Path(a.out).parent.mkdir(parents=True, exist_ok=True); nib.save(nib.Nifti1Image(vol, aff), a.out)
    colors = palette(len(IDS)); levels = [int(t) for t in a.montage_levels.split(",")] if a.montage_levels else \
        [int(round(j_top + (j_bot - j_top) * q)) for q in (0.02, 0.2, 0.4, 0.6, 0.8, 0.98)]
    mont = montage(crops, track, labels_by_level, final_names, frames, levels, Path(a.montage), colors)
    res_summary = {b: {"n_levels": len(v), "mean_mm": [round(float(np.mean([x[0] for x in v.values()])), 1), round(float(np.mean([x[1] for x in v.values()])), 1)],
                       "sd_mm": [round(float(np.std([x[0] for x in v.values()])), 1), round(float(np.std([x[1] for x in v.values()])), 1)]} for b, v in residual.items() if v}
    supp = {f"{p[0]}|{p[1]}": {"levels": len(v), "median_ridge_ratio": round(float(np.median([x[2] for x in v])), 2),
                               "frac_levels_ratio_ge_1.8": round(float(np.mean([x[2] >= 1.8 for x in v])), 2),
                               "contact_mm": round(float(np.mean([x[1] for x in v])) * PX, 1)} for p, v in sorted(support.items()) if len(v) >= 5}
    mc1_levels = [j for j in frames if frames[j]["P"]["mc1"] is not None]
    plaus = {}                                                     # shipped name -> (verdict, sentence); 'far' = not shipped by name
    for nm, v in vols.items():
        w = PLAUSIBLE.get(nm)
        if w is None:
            continue
        lo, hi, what = w
        if lo <= v <= hi:
            plaus[nm] = ("ok", f"{v} cm3, inside the expected {lo}-{hi} cm3 for {what}")
        else:
            far = v > 2 * hi or v < hi / 2 and v < lo / 2
            plaus[nm] = ("far" if far else "review",
                         f"{v} cm3 against the expected {lo}-{hi} cm3 for {what}" + (": more than twice off, not shipped by name" if far else ": REVIEW"))
    not_shipped = dict(NOT_SHIPPED)
    for nm, (verdict, why) in plaus.items():
        if verdict == "far":
            not_shipped[nm] = f"label kept in the volume but mapped to null: {why}"
    report = {"_README": [f"Female right hand intrinsic muscles from her full-resolution cryosections ({Path(__file__).name}); {BADGE}. "
                          "Metacarpals tracked in the photographs (named from the CT at one level); compartments by textbook position rules in the "
                          "metacarpal frame (Gray's Anatomy 42nd ed. ch. 50 'Wrist and hand'; Moore, Clinically Oriented Anatomy 8th ed. ch. 6); thenar and "
                          "hypothenar split by a marker watershed on the pale septa; muscles the photographs do not separate merged into compartments.",
                          "ct_to_photo_shift_mm: photographed disc centre minus the CT centroid, [photo rows, photo cols] in mm, per metacarpal: the residual of "
                          "the CT->cryo registration at the hand (used only to name the discs at the anchor level)."],
              "source": SOURCE, "badge": BADGE, "version": "2026-09-16",
              "levels": {"segment": [j_top, j_bot], "segment_atlas_y_mm": [round(crops.level(j_top)["y"], 1), round(crops.level(j_bot)["y"], 1)],
                         "thenar_levels_with_mc1": [min(mc1_levels), max(mc1_levels)] if mc1_levels else None,
                         "note": "crop level = 1 mm of atlas y; the segment runs from the carpometacarpal joints to the metacarpal heads"},
              "ct_to_photo_shift_mm": res_summary, "voxel_mm": [float(aff[0, 0]), float(aff[1, 1]), float(aff[2, 2])],
              "volumes_cm3": vols, "unassigned_muscle_cm3": round(unassigned / 1000.0, 2),
              "plausibility": {nm: why for nm, (verdict, why) in sorted(plaus.items())},
              "merged": {c: {"members": mem, "note": merge_note.get(c, "")} for c, mem in merge.items()},
              "not_shipped": not_shipped, "montage": mont, "labels": {str(l): nm for l, nm in sorted(final_names.items())},
              "septum_support": supp, "rules": [
                  "dorsal vs palmar interossei: the plane through the adjacent metacarpal shaft centres (not a photographed border)",
                  "palmar interossei vs adductor pollicis / hypothenar / palm: the palmar bone surface + 3 mm",
                  "1st dorsal interosseous vs adductor pollicis: the MC1-MC2 centre line", "thenar vs adductor: 4 mm ulnar of the MC1 surface",
                  "hypothenar vs interossei: the MC5 centre plane",
                  "thenar / hypothenar members: marker watershed on the white top-hat of the brightness (the pale septa) from the rule seeds"],
              "limits": LIMITS, "literature": LITERATURE,
              "output": str(Path(a.out).resolve()), "labels_file": str(Path(a.labels_out).resolve()), "mapping_file": str(Path(a.mapping_out).resolve())}
    Path(str(a.out).replace(".nii.gz", "_report.json")).write_text(json.dumps(report, indent=1))
    key = {"_README": [f"Label id -> structure for the Visible Human FEMALE right hand intrinsic muscle volume ({Path(__file__).name}). A KEY, not data. {BADGE}: "
                       "see the script docstring for the rule; compartments are muscles the photographs do not separate (mapped to null)."],
           "source": SOURCE, "task": "vhf_hand_muscles", "version": "2026-09-16", "badge": BADGE,
           "labels": {str(l): nm for l, nm in sorted(final_names.items())}, "merged_compartments": merge}
    Path(a.labels_out).write_text(json.dumps(key, indent=1))
    entries = []
    for l, nm in sorted(final_names.items()):
        if nm in merge:
            entries.append({"label": l, "source_structure": nm, "side": "right", "status": "no_atlas_entity", "atlas_id": None,
                            "relationship": "no_usable_label", "note": f"{BADGE}; compartment holding {', '.join(merge[nm])} ({vols.get(nm, 0)} cm3), not split: "
                            f"{merge_note.get(nm, 'the photographs show no septum the watershed could follow between them at most levels')}",
                            "candidates": [m + "_r" for m in merge[nm]]})
        elif nm == "palmar_flexor_tendon_compartment":
            entries.append({"label": l, "source_structure": nm, "side": "right", "status": "no_atlas_entity", "atlas_id": None, "relationship": "no_usable_label",
                            "note": f"{BADGE}; muscle-class pixels palmar of the interossei between MC3 and MC4 ({vols.get(nm, 0)} cm3): the lumbricals and the "
                                    "flexor sheaths' dark walls cannot be told apart at 0.33 mm; lumbricals_hand_r is not shipped.", "candidates": ["lumbricals_hand_r"]})
        else:
            verdict, why = plaus.get(nm, ("unchecked", f"{vols.get(nm, 0)} cm3, no plausibility window"))
            note = f"{BADGE}: position rule in the metacarpal frame" + (", boundary by the marker watershed on her septa" if nm in MARKER_RULES else
                                                                       " (rule planes through the metacarpal centres, see the report)") + f"; {why}."
            if nm in ("dorsal_interossei_hand", "palmar_interossei"):
                note += " One structure for the whole hand: the atlas entity is a group (the per-space split is in the volume's geometry only)."
            entries.append({"label": l, "source_structure": nm, "side": "right",
                            "status": "no_atlas_entity" if verdict == "far" else "curated",
                            "atlas_id": None if verdict == "far" else nm + "_r",
                            "relationship": "no_usable_label" if verdict == "far" else "exact",
                            "note": note, "candidates": [nm + "_r"] if verdict == "far" else []})
    Path(a.mapping_out).write_text(json.dumps({"_README": ["Review every entry before running convert.", "Set 'atlas_id' to the correct entity, or null to skip the label.",
                                                            "'status' is advisory; convert reads 'atlas_id' only."],
                                                "subject": "ct_vhf_hand", "source_volume": str(Path(a.out).resolve()), "label_map": "vhf_hand_muscles",
                                                "entries": entries}, indent=2))
    print(json.dumps({"segment": [j_top, j_bot], "thenar_levels": report["levels"]["thenar_levels_with_mc1"], "volumes_cm3": vols, "unassigned_cm3": round(unassigned / 1000, 2),
                      "residual": res_summary, "support": supp, "montage": mont}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
