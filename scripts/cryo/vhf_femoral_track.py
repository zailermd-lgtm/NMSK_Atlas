"""Track the FEMORAL neurovascular bundle through the female's FULL-RESOLUTION cryosection crops (Q55).

    python3 scripts/cryo/vhf_femoral_track.py track --crops SCRATCH/vh_cryo_f/thigh --side right \
        --bundle build/viewer_f --y-start 20 --y-end -330 --out SCRATCH/vh_cryo_f/femoral_right
    python3 scripts/cryo/vhf_femoral_track.py clean --tracks SCRATCH/vh_cryo_f/femoral_right \
        --span artery=14:-46 vein=14:-46 nerve=14:-12 --crops SCRATCH/vh_cryo_f/thigh --side right \
        --montage data/ct_sources/task_outputs/vhf_femoral_bundle_cryo_right.png
    python3 scripts/cryo/vhf_nerve_volume.py --crops SCRATCH/vh_cryo_f/thigh \
        --track femoral_a_r=SCRATCH/vh_cryo_f/femoral_right_artery_clean.json:14:-46 ... \
        --out data/ct_sources/task_outputs/vhf_femoral_bundle_cryo.nii.gz \
        --labels-out mappings/vhf_femoral_bundle_labels.json \
        --mapping-out mappings/subjects/ct_vhf_femoral_volume_mapping.json --subject ct_vhf_femoral
    python3 scripts/cryo/vhf_femoral_track.py report --tracks SCRATCH/vh_cryo_f/femoral_right --suffix _clean \
        --span artery=14:-46 vein=14:-46 nerve=14:-12 --ids '{"artery_right": "femoral_a_r", ...}' \
        --volume-report data/ct_sources/task_outputs/vhf_femoral_bundle_cryo_report.json --out <same file>

Companion of vhf_nerve_track.py (sciatic): same crops (vhf_stream_crops.py), same Crops/corridor/section
machinery and the same volume builder (vhf_nerve_volume.py); a different detector for the two vessels, a
joint seed rule for the three structures, and a local walk (aorta_from_cryo.py) instead of a global Viterbi,
because a lumen's appearance changes down the thigh while its position does not.

ANATOMY (Gray's 42nd ed. 'Thigh'; Moore 8th ed.). Under the inguinal ligament the order lateral -> medial is
femoral NERVE, femoral ARTERY, femoral VEIN. The artery and vein cross the femoral triangle (roof: fascia lata
between sartorius laterally and adductor longus medially; floor: iliopsoas + pectineus + adductor longus) and
enter the adductor canal (between vastus medialis, adductor longus/magnus and sartorius), where the VEIN comes
to lie POSTERIOR(-lateral) to the artery; both leave the canal through the ADDUCTOR HIATUS in adductor magnus.
The nerve trunk breaks into its anterior and posterior divisions within ~4-5 cm of the ligament.

RULES:
  corridor  = as vhf_nerve_track.corridor_mask with roof = sartorius/iliopsoas/pectineus/adductor longus,
              floor = iliopsoas/pectineus/vastus medialis/adductor longus/adductor magnus, bone = femur,
              20 mm; the bundle lives in this intermuscular space, never inside a belly. Used for the seed
              level and for every nerve level (the vessel walk below is local and needs no corridor).
  seed      = LANDMARK RULE, not a hand click. The inguinal-ligament midpoint M = (ASIS + pubic tubercle)/2
              from her hip-bone mesh. Walking down from the first crop level, the first level at which a
              PAIR of dark round lumina sits within 35 mm of M (3-25 mm apart in x, < 18 mm in z, largest
              combined area) is the seed level; the LATERAL member is the artery, the MEDIAL the vein.
              A lumen there = near-black core (3 mm mean red < 58, her muscle is dark *red* 75-95 and fat
              cream > 150; blue-black clot counts, only blue reaching the crop edge is embedding gel),
              opened by 0.7 mm, touching lumina split by a distance watershed, each grown out to its wall
              (watershed on red < 105, at most 2 mm past the core), 8-200 mm2, solidity >= 0.75, aspect
              <= 2.5, >= 40% inside the corridor, 20th percentile of red < 40 (the darkest muscle patches
              bottom out at 43-49) and a pale wall (ring red >= 30 above the lumen).
  vessels   = WALK with the previous section as the prior (aorta_from_cryo.py rule at full resolution):
              inside the previous mask dilated by 5 mm, threshold at the window's 15th percentile of red
              + 18 (adaptive: distally the lumen is grey-brown, not black, but it is still the darkest
              round thing in the window), split touching lumina, and take the component of 0.35-3x the
              previous area with solidity >= 0.7, aspect <= 2.6, a wall (ring red >= 20 above the lumen)
              and the centroid nearest the previous one. A level without such a component is a gap that
              keeps the previous position; 8 gaps in a row end the walk. The two are walked TOGETHER and
              the chosen pair must stay within 20 mm of each other, because artery and vein share one
              femoral sheath the whole way: that is what keeps the artery off the profunda femoris (which
              leaves the vein behind and dives posterolaterally, 3-5 cm below the ligament) and the vein
              off the great saphenous (which leaves the artery at the saphenofemoral junction and climbs
              into the subcutaneous fat). A mask wider than ~1.2x the textbook maximum (artery 95 mm2,
              vein 160 mm2) is refused: past that the component has eaten into muscle.
  nerve     = walk of fascicle texture (vhf_nerve_track.nerve_blobs), 6-120 mm2, inside the corridor,
              LATERAL to the tracked artery and 3-30 mm from it, within 6 mm of the previous position. The
              walk stops when the blob has been under 8 mm2 for 3 levels or 4 levels give nothing: the trunk
              has divided, and that level is reported as the split.
  cleaning  = before the volume is built, a tracked level whose mask is ragged (solidity < 0.85) or whose
              diameter falls outside the textbook band widened by 25% is dropped back to a gap: that is the
              walk's one failure mode, a mask that has run into muscle.
  hiatus    = the first level below y = -150 at which the tracked artery centroid falls inside her adductor
              magnus section (the artery passing through the adductor hiatus).
  diameter  = per level, both the area-equivalent diameter 2*sqrt(area/pi) and the inscribed diameter
              2*max(distance transform); expected adult common femoral a. 6-9 mm, superficial femoral 5-7,
              femoral v. 9-13 (Gray's; Moore). Measured values are recorded per level in the report.

LIMITS: the crops start at y = +20 mm and the lumen pair is only separable from y = +12 mm down, i.e. ~20 mm
below the inguinal-ligament midpoint, so the top of the common femoral vessels is not covered. The roof/floor meshes are TRANSFERRED muscle
meshes, so the corridor is approximate (it is only used to reject far-away blobs, at 40% overlap). A lumen
that touches muscle without a pale wall between is kept at its dark core, which under-measures it. Nothing
here is a segmentation of the vessel wall: the tracked mask is the lumen.
Rule-based; badged; volumes and per-level diameters recorded.
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
from skimage.feature import peak_local_max
from skimage.morphology import convex_hull_image
from skimage.segmentation import watershed

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.cryo.vhf_nerve_track import (Crops, PX, corridor_mask, disk, nerve_blobs,  # noqa: E402
                                          section_masks)
from scripts.transfer.bundle_io import meshes_by_id, read_bundle_dir  # noqa: E402

SOURCE = ("U.S. National Library of Medicine, The Visible Human Project (public domain), female cryosections at full "
          "resolution (0.33 mm) via the NCI Imaging Data Commons. Derived data (scripts/cryo/vhf_femoral_track.py).")
FEMORAL = {"roof": ["sartorius", "iliopsoas", "pectineus", "adductor_longus"],
           "floor": ["iliopsoas", "pectineus", "vastus_medialis", "adductor_longus", "adductor_magnus"],
           "bone": ["femur"], "corridor_mm": 20.0,
           "core_thr": 58.0, "wall_thr": 105.0, "vessel_mm2": (8.0, 200.0), "nerve_mm2": (6.0, 120.0),
           # a femoral lumen is never wider than ~1.2x the textbook maximum: past that the mask has eaten
           # into her dark-red muscle, which is the walk's one failure mode
           "max_mm2": {"artery": 95.0, "vein": 160.0}}
EXPECTED_MM = {"artery": (5.0, 9.0), "vein": (7.0, 13.0), "nerve": (3.0, 12.0)}
NERVE_MIN_MM2 = 8.0


# ---------------------------------------------------------------- detectors
def outside_gel(blue):
    """The blue embedding gel = the blue components that reach the edge of the crop. A blue-black blob deep
    inside the limb is a vein whose clot photographed blue, so it must NOT be thrown away with the gel."""
    lab, n = ndi.label(blue)
    if n == 0:
        return blue
    edge = np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
    edge = edge[edge > 0]
    return np.isin(lab, edge)


def vessel_lumina(im, core_thr=58.0, wall_thr=105.0):
    """Label image of dark round lumina: near-black cores split by a distance watershed, each grown out to
    its wall (watershed on the red channel inside red < wall_thr, never further than 2 mm from the core, so
    the growth cannot run away into her dark-red muscle) unless the growth leaks (> 3x the core)."""
    R = im[..., 0].astype(np.float32); B = im[..., 2].astype(np.float32)
    gel = outside_gel(B > R)          # blue INSIDE the limb is clotted/blue-black blood, not embedding gel
    R3 = ndi.uniform_filter(R, 3)
    core = ndi.binary_fill_holes(ndi.binary_opening((R3 < core_thr) & ~gel, structure=disk(2)))
    if not core.any():
        return np.zeros(im.shape[:2], np.int32)
    dist = ndi.distance_transform_edt(core)
    pk = peak_local_max(dist, labels=core, min_distance=8, exclude_border=False)
    mk = np.zeros(core.shape, np.int32)
    for i, (r, c) in enumerate(pk):
        mk[r, c] = i + 1
    cores = watershed(-dist, mk, mask=core)
    reach = ndi.binary_dilation(core, structure=disk(6))               # at most 2 mm beyond the core
    grown = watershed(R3, cores, mask=(R3 < wall_thr) & ~gel & reach)
    out = np.zeros(core.shape, np.int32)
    for i in range(1, int(cores.max()) + 1):
        c = cores == i
        if not c.any():
            continue
        g = grown == i
        keep = g if (g.sum() <= 3 * c.sum() and g.sum() * PX * PX <= 250.0) else c
        out[keep & (out == 0)] = i
    return out


def blob_stats(mask):
    yy, xx = np.nonzero(mask)
    cy, cx = yy.mean(), xx.mean()
    a = mask.sum() * PX * PX
    sub = mask[yy.min():yy.max() + 1, xx.min():xx.max() + 1]      # hull/EDT on the bounding box only
    sol = mask.sum() / max(convex_hull_image(sub).sum(), 1)
    cov = np.cov(np.stack([yy - cy, xx - cx])) if len(yy) > 2 else np.eye(2)
    ev = np.sort(np.linalg.eigvalsh(cov))
    asp = float(np.sqrt(max(ev[1], 1e-6) / max(ev[0], 1e-6)))
    insc = 2.0 * float(ndi.distance_transform_edt(np.pad(sub, 1)).max()) * PX
    return {"rc": (float(cy), float(cx)), "area_mm2": float(a), "solidity": float(sol), "aspect": asp,
            "diam_mm": float(2 * np.sqrt(a / np.pi)), "inscribed_mm": insc}


def roundness_score(s):
    """1.0 = a round lumen, 0.0 = a ragged strip."""
    return float(np.clip((s["solidity"] - 0.65) / 0.30, 0, 1) * np.clip((2.5 - s["aspect"]) / 1.0, 0, 1))


def vessel_candidates(im, corridor, spec):
    """Round dark lumina inside the corridor. A clotted lumen has a genuinely BLACK centre (20th percentile
    of red < 40; the darkest patches of her muscle - the only other near-black blobs at this threshold -
    bottom out around 43-49) and a PALE WALL around it (mean red of a 0.7-2 mm annulus at least 30 above the
    lumen mean)."""
    R = im[..., 0].astype(np.float32)
    lab = vessel_lumina(im, spec["core_thr"], spec["wall_thr"])
    lo, hi = spec["vessel_mm2"]; out = []
    for i in range(1, int(lab.max()) + 1):
        mm = lab == i
        if not mm.any():
            continue
        s = blob_stats(mm)
        if not (lo <= s["area_mm2"] <= hi) or s["solidity"] < 0.75 or s["aspect"] > 2.5:
            continue
        inside = float(corridor[mm].mean())
        if inside < 0.4:
            continue
        ring = ndi.binary_dilation(mm, structure=disk(6)) & ~ndi.binary_dilation(mm, structure=disk(2))
        mr = float(R[mm].mean()); p20 = float(np.percentile(R[mm], 20))
        rr = float(R[ring].mean()) if ring.any() else 0.0
        if p20 > 40.0 or rr - mr < 30.0:
            continue
        out.append(dict(s, lab=i, inside=inside, mean_r=round(mr, 1), p20_r=round(p20, 1), ring_r=round(rr, 1),
                        score=roundness_score(s)))
    return out, lab


def nerve_candidates(im, corridor, spec):
    lab, n = nerve_blobs(im)
    lo, hi = spec["nerve_mm2"]; out = []
    for i in range(1, n + 1):
        mm = lab == i
        if not mm.any():
            continue
        s = blob_stats(mm)
        if not (lo <= s["area_mm2"] <= hi) or s["aspect"] > 3.0:
            continue
        inside = float(corridor[mm].mean())
        if inside < 0.4:
            continue
        out.append(dict(s, lab=i, inside=inside, score=roundness_score(s)))
    return out, lab


# ---------------------------------------------------------------- landmarks and seeds
def inguinal_midpoint(meshes, side):
    """(ASIS + pubic tubercle)/2 from her hip-bone mesh: ASIS = most anterior vertex of the upper ilium,
    pubic tubercle = most anterior vertex of the medial 25 mm of the pubis below the acetabulum."""
    p = meshes["hip_bone_" + side[0]]["v"]
    sg = 1.0 if side == "right" else -1.0
    up = p[p[:, 1] > p[:, 1].max() - 60]
    asis = up[np.argmax(up[:, 2])]
    medial_edge = (sg * p[:, 0]).min()
    pub = p[(sg * p[:, 0] < medial_edge + 25) & (p[:, 1] < 0)]
    pt = pub[np.argmax(pub[:, 2])] if len(pub) else p[np.argmax(p[:, 2])]
    m = (np.asarray(asis, float) + np.asarray(pt, float)) / 2.0
    return {"asis": [round(float(v), 1) for v in asis], "pubic_tubercle": [round(float(v), 1) for v in pt],
            "x": float(m[0]), "y": float(m[1]), "z": float(m[2]),
            "rule": "midpoint of the anterior superior iliac spine and the pubic tubercle of her hip-bone mesh"}


def seed_pair(cands, mid, side, max_dist=35.0):
    """artery = the lateral member, vein = the medial member of the best candidate pair near the inguinal
    midpoint (3-25 mm apart in x, < 18 mm apart in z, largest combined area)."""
    sg = 1.0 if side == "right" else -1.0
    near = [c for c in cands if np.hypot(c["x"] - mid["x"], c["z"] - mid["z"]) <= max_dist]
    best = None
    for i in range(len(near)):
        for j in range(len(near)):
            if i == j:
                continue
            a, v = near[i], near[j]                      # a lateral, v medial
            dx = sg * (a["x"] - v["x"])
            if not (3.0 <= dx <= 25.0) or abs(a["z"] - v["z"]) > 18.0:
                continue
            tot = a["area_mm2"] + v["area_mm2"]
            if best is None or tot > best[0]:
                best = (tot, a, v)
    if best is None:
        if not near:
            raise SystemExit("no lumen candidate near the inguinal midpoint")
        a = max(near, key=lambda c: c["area_mm2"])
        return a, None
    return best[1], best[2]


# ---------------------------------------------------------------- walking (previous section as the prior)
def level_corridor(crops, meshes, side, spec, y, shape):
    names = list(dict.fromkeys(spec["roof"] + spec["floor"] + spec["bone"]))
    masks = section_masks(meshes, names, side, y, crops, shape)
    cor, _ = corridor_mask(crops.image(y), masks, spec)
    return cor


def seed_level(crops, meshes, side, spec, ys, log=print):
    """First level from the top at which the lumen pair rule fires: returns (y, artery blob, vein blob)."""
    mid = inguinal_midpoint(meshes, side)
    for y in ys:
        im = crops.image(y)
        cor = level_corridor(crops, meshes, side, spec, y, im.shape[:2])
        cands, lab = vessel_candidates(im, cor, spec)
        for c in cands:
            ax, az = crops.px_to_atlas(y, c["rc"][0], c["rc"][1]); c["x"], c["z"] = float(ax), float(az)
        try:
            a, v = seed_pair(cands, mid, side)
        except SystemExit:
            continue
        if v is None:
            continue
        log(f"seed level y={y}: artery x{a['x']:.0f} z{a['z']:.0f} d{a['diam_mm']:.1f} | "
            f"vein x{v['x']:.0f} z{v['z']:.0f} d{v['diam_mm']:.1f}")
        return y, dict(a, mask=(lab == a["lab"])), dict(v, mask=(lab == v["lab"])), mid
    raise SystemExit("no seed pair found in the given levels")


def _dark_components(R3, gel, win, prev_a):
    """Adaptive local threshold (aorta_from_cryo.py rule at full resolution): inside the search window the
    lumen is the darkest thing, so threshold at the window's 15th percentile + 18, split touching lumina."""
    vals = R3[win]
    thr = float(np.clip(np.percentile(vals, 15) + 18.0, 38.0, 95.0))
    cand = ndi.binary_fill_holes(ndi.binary_opening((R3 < thr) & win & ~gel, structure=disk(2)))
    if not cand.any():
        return np.zeros(R3.shape, np.int32), thr
    dist = ndi.distance_transform_edt(cand)
    pk = peak_local_max(dist, labels=cand, min_distance=8, exclude_border=False)
    mk = np.zeros(cand.shape, np.int32)
    for i, (r, c) in enumerate(pk):
        mk[r, c] = i + 1
    return watershed(-dist, mk, mask=cand), thr


def walk_vessel(crops, ys, y0, mask0, forbid=None, reach_mm=5.0, max_gap=8, log=print):
    """Follow one lumen down the levels from its seed mask: inside a disk of the previous lumen's radius
    + reach_mm around the previous ATLAS position (each level's crop has its own window, so the prior travels
    in atlas mm, not in pixels), the darkest round component whose area is 0.35-3x the previous one,
    solidity >= 0.7, aspect <= 2.6, with a wall (ring red at least 20 above the lumen) and the centroid
    nearest the previous one. A level without such a component is a gap that keeps the previous position;
    `max_gap` gaps in a row end the walk."""
    rows, masks = [], {}
    prev_a = mask0.sum() * PX * PX; gaps = 0
    s0 = blob_stats(mask0)
    prev_xz = tuple(float(v) for v in crops.px_to_atlas(y0, *s0["rc"]))
    for y in ys:
        if y == y0:
            rows.append({"y": y, "gap": False, "x": round(prev_xz[0], 1), "z": round(prev_xz[1], 1),
                         "area_mm2": round(s0["area_mm2"], 1), "diam_mm": round(s0["diam_mm"], 1),
                         "inscribed_mm": round(s0["inscribed_mm"], 1), "solidity": round(s0["solidity"], 2),
                         "aspect": round(s0["aspect"], 2)})
            masks[y] = mask0
            continue
        im = crops.image(y)
        R = im[..., 0].astype(np.float32); B = im[..., 2].astype(np.float32)
        R3 = ndi.uniform_filter(R, 3); gel = outside_gel(B > R)
        pyx = np.array([float(v) for v in crops.atlas_to_px(y, prev_xz[0], prev_xz[1])])
        rad = np.sqrt(prev_a / np.pi) / PX + reach_mm / PX
        yy, xx = np.ogrid[:im.shape[0], :im.shape[1]]
        win = (yy - pyx[0]) ** 2 + (xx - pyx[1]) ** 2 <= rad * rad
        if not win.any():
            break
        f = forbid.get(y) if forbid else None
        if f is not None and f.shape == win.shape:
            win = win & ~f
        lab, thr = _dark_components(R3, gel, win, prev_a)
        best, bscore = None, -1e9
        for i in range(1, int(lab.max()) + 1):
            mm = lab == i
            a = mm.sum() * PX * PX
            if not (max(4.0, 0.35 * prev_a) <= a <= min(260.0, 3.0 * prev_a)):
                continue
            s = blob_stats(mm)
            if s["solidity"] < 0.70 or s["aspect"] > 2.6:
                continue
            ring = ndi.binary_dilation(mm, structure=disk(6)) & ~ndi.binary_dilation(mm, structure=disk(2))
            if not ring.any() or float(R[ring].mean()) - float(R[mm].mean()) < 20.0:
                continue
            d = float(np.hypot(s["rc"][0] - pyx[0], s["rc"][1] - pyx[1])) * PX
            if d > reach_mm + 3.0:
                continue
            sc = roundness_score(s) - abs(np.log(max(a, 1e-6) / max(prev_a, 1e-6))) - 0.15 * d
            if sc > bscore:
                best, bscore = (mm, s), sc
        if best is None:
            gaps += 1
            rows.append({"y": y, "gap": True, "x": round(prev_xz[0], 1), "z": round(prev_xz[1], 1)})
            if gaps > max_gap:
                break
            continue
        gaps = 0
        mm, s = best
        prev_a = s["area_mm2"]
        masks[y] = mm
        ax, az = crops.px_to_atlas(y, *s["rc"])
        prev_xz = (float(ax), float(az))
        rows.append({"y": y, "gap": False, "x": round(float(ax), 1), "z": round(float(az), 1),
                     "area_mm2": round(s["area_mm2"], 1), "diam_mm": round(s["diam_mm"], 1),
                     "inscribed_mm": round(s["inscribed_mm"], 1), "solidity": round(s["solidity"], 2),
                     "aspect": round(s["aspect"], 2), "thr": round(thr, 1)})
    while rows and rows[-1]["gap"]:
        rows.pop()
    return rows, masks


def _row(y, s, xz, thr=None):
    r = {"y": y, "gap": False, "x": round(xz[0], 1), "z": round(xz[1], 1),
         "area_mm2": round(s["area_mm2"], 1), "diam_mm": round(s["diam_mm"], 1),
         "inscribed_mm": round(s["inscribed_mm"], 1), "solidity": round(s["solidity"], 2),
         "aspect": round(s["aspect"], 2)}
    if thr is not None:
        r["thr"] = round(thr, 1)
    return r


def walk_pair(crops, ys, y0, mask_a, mask_v, pair_mm=20.0, reach_mm=4.0, max_gap=8,
              max_mm2=None, log=print):
    """Walk the ARTERY and the VEIN together. They lie in one femoral sheath from the inguinal ligament to
    the adductor hiatus, so at every level the chosen pair of lumina must stay within `pair_mm` of each
    other. That single constraint is what keeps the artery off the profunda femoris (which leaves the vein
    behind and dives posterolaterally) and the vein off the great saphenous (which leaves the artery behind
    at the saphenofemoral junction and climbs out to the subcutaneous fat). Each member is otherwise the
    same local dark round component as walk_vessel: inside its own previous position dilated by reach_mm,
    area 0.35-3x its own previous area, solidity >= 0.7, aspect <= 2.6, a pale wall (ring red >= 20 above
    the lumen). Where no admissible pair exists the better single is taken and the other level is a gap;
    `max_gap` gaps in a row for BOTH ends the walk."""
    max_mm2 = max_mm2 or FEMORAL["max_mm2"]
    st = {"artery": {"xz": None, "a": mask_a.sum() * PX * PX, "gaps": 0, "rows": [], "masks": {}},
          "vein": {"xz": None, "a": mask_v.sum() * PX * PX, "gaps": 0, "rows": [], "masks": {}}}
    for nm, m0 in (("artery", mask_a), ("vein", mask_v)):
        s0 = blob_stats(m0)
        st[nm]["xz"] = tuple(float(v) for v in crops.px_to_atlas(y0, *s0["rc"]))
        st[nm]["rows"].append(_row(y0, s0, st[nm]["xz"]))
        st[nm]["masks"][y0] = m0
    for y in ys:
        if y == y0:
            continue
        im = crops.image(y)
        R = im[..., 0].astype(np.float32); B = im[..., 2].astype(np.float32)
        R3 = ndi.uniform_filter(R, 3); gel = outside_gel(B > R)
        yy, xx = np.ogrid[:im.shape[0], :im.shape[1]]
        pyx, win = {}, np.zeros(im.shape[:2], bool)
        for nm in st:
            p = np.array([float(v) for v in crops.atlas_to_px(y, *st[nm]["xz"])])
            rad = np.sqrt(st[nm]["a"] / np.pi) / PX + reach_mm / PX
            pyx[nm] = p
            win |= (yy - p[0]) ** 2 + (xx - p[1]) ** 2 <= rad * rad
        if not win.any():
            break
        lab, thr = _dark_components(R3, gel, win, max(st[nm]["a"] for nm in st))
        cands = []
        for i in range(1, int(lab.max()) + 1):
            mm = lab == i
            a = mm.sum() * PX * PX
            if a < 4.0 or a > 260.0:
                continue
            s = blob_stats(mm)
            if s["solidity"] < 0.70 or s["aspect"] > 2.6:
                continue
            ring = ndi.binary_dilation(mm, structure=disk(6)) & ~ndi.binary_dilation(mm, structure=disk(2))
            if not ring.any() or float(R[ring].mean()) - float(R[mm].mean()) < 20.0:
                continue
            axz = tuple(float(v) for v in crops.px_to_atlas(y, *s["rc"]))
            cands.append({"mask": mm, "s": s, "xz": axz, "area": a})
        ok = {}
        for nm in st:
            ok[nm] = []
            for k, c in enumerate(cands):
                if not (max(4.0, 0.35 * st[nm]["a"]) <= c["area"] <= min(max_mm2[nm], 3.0 * st[nm]["a"])):
                    continue
                d = float(np.hypot(c["s"]["rc"][0] - pyx[nm][0], c["s"]["rc"][1] - pyx[nm][1])) * PX
                if d > reach_mm + 3.0:
                    continue
                sc = roundness_score(c["s"]) - abs(np.log(max(c["area"], 1e-6) / max(st[nm]["a"], 1e-6))) - 0.15 * d
                ok[nm].append((sc, k))
        best = None
        for sa, ka in ok["artery"]:
            for sv, kv in ok["vein"]:
                if ka == kv:
                    continue
                if np.hypot(cands[ka]["xz"][0] - cands[kv]["xz"][0], cands[ka]["xz"][1] - cands[kv]["xz"][1]) > pair_mm:
                    continue
                if best is None or sa + sv > best[0]:
                    best = (sa + sv, ka, kv)
        take = {}
        if best is not None:
            take = {"artery": best[1], "vein": best[2]}
        else:                                   # no admissible pair: keep the better single, gap the other
            singles = {nm: max(ok[nm], default=None) for nm in st}
            cand_nm = [nm for nm in st if singles[nm] is not None]
            if len(cand_nm) == 2 and singles["artery"][1] == singles["vein"][1]:
                nm = "artery" if singles["artery"][0] >= singles["vein"][0] else "vein"
                take = {nm: singles[nm][1]}
            else:
                take = {nm: singles[nm][1] for nm in cand_nm}
        for nm in st:
            if nm in take:
                c = cands[take[nm]]
                st[nm]["gaps"] = 0; st[nm]["a"] = c["area"]; st[nm]["xz"] = c["xz"]
                st[nm]["masks"][y] = c["mask"]
                st[nm]["rows"].append(_row(y, c["s"], c["xz"], thr))
            else:
                st[nm]["gaps"] += 1
                st[nm]["rows"].append({"y": y, "gap": True, "x": round(st[nm]["xz"][0], 1), "z": round(st[nm]["xz"][1], 1)})
        if all(st[nm]["gaps"] > max_gap for nm in st):
            break
    out = {}
    for nm in st:
        rows = st[nm]["rows"]
        while rows and rows[-1]["gap"]:
            rows.pop()
        out[nm] = (rows, {y: m for y, m in st[nm]["masks"].items() if any(r["y"] == y and not r["gap"] for r in rows)})
    return out


def walk_nerve(crops, meshes, side, spec, ys, y0, seed_xz, art_xz, reach_mm=6.0, max_gap=4, log=print):
    """Follow the femoral nerve trunk down from the ligament: fascicle-texture blobs (vhf_nerve_track.
    nerve_blobs) inside the corridor, lateral to the tracked artery and 4-30 mm from it, nearest the previous
    position. The walk stops at the first level with no such blob after `max_gap` tries, or when the blob has
    fallen under NERVE_MIN_MM2 for 3 levels: that is where the trunk has divided."""
    sg = 1.0 if side == "right" else -1.0
    rows, masks = [], {}
    px, pz = seed_xz; gaps = 0; small = 0
    for y in ys:
        im = crops.image(y)
        cor = level_corridor(crops, meshes, side, spec, y, im.shape[:2])
        cands, lab = nerve_candidates(im, cor, spec)
        ax = art_xz.get(y)
        best, bd = None, 1e9
        for c in cands:
            cx, cz = crops.px_to_atlas(y, c["rc"][0], c["rc"][1])
            d = float(np.hypot(cx - px, cz - pz))
            if d > reach_mm:
                continue
            if ax is not None:
                da = float(np.hypot(cx - ax[0], cz - ax[1]))
                if sg * (cx - ax[0]) < 2.0 or not (3.0 <= da <= 30.0):
                    continue
            if d < bd:
                best, bd = (c, float(cx), float(cz)), d
        if best is None:
            gaps += 1
            rows.append({"y": y, "gap": True, "x": round(px, 1), "z": round(pz, 1)})
            if gaps > max_gap:
                break
            continue
        gaps = 0
        c, cx, cz = best
        px, pz = cx, cz
        masks[y] = lab == c["lab"]
        rows.append({"y": y, "gap": False, "x": round(cx, 1), "z": round(cz, 1),
                     "area_mm2": round(c["area_mm2"], 1), "diam_mm": round(c["diam_mm"], 1),
                     "inscribed_mm": round(c["inscribed_mm"], 1), "solidity": round(c["solidity"], 2),
                     "aspect": round(c["aspect"], 2), "inside": round(c["inside"], 2)})
        small = small + 1 if c["area_mm2"] < NERVE_MIN_MM2 else 0
        if small >= 3:
            break
    while rows and rows[-1]["gap"]:
        rows.pop()
    return rows, masks


def clean_rows(rows, name, expected=None, min_solidity=0.85):
    """Drop a tracked level back to a GAP when its mask is not a plausible lumen: solidity < min_solidity
    (a ragged mask has run along a muscle edge) or a diameter outside the textbook band for that structure
    widened by 25% (artery 3.8-11.3 mm, vein 5.3-16.3, nerve 2.3-15). The chain keeps its place - the volume
    builder fills short gaps from the neighbouring section - but no unverifiable mask is shipped."""
    expected = expected or EXPECTED_MM
    lo, hi = expected[name]
    lo, hi = lo * 0.75, hi * 1.25
    out, dropped = [], 0
    for r in rows:
        if not r["gap"] and (r.get("solidity", 1.0) < min_solidity or not (lo <= r["diam_mm"] <= hi)):
            out.append({"y": r["y"], "gap": True, "x": r["x"], "z": r["z"], "dropped": True}); dropped += 1
        else:
            out.append(r)
    while out and out[-1]["gap"]:
        out.pop()
    return out, dropped


def do_clean(a):
    """Rewrite track files with clean_rows applied (and, with --span, cut to the range actually shipped),
    for the volume builder; with --crops/--montage, redraw the montage over exactly those levels."""
    spans = {k: [float(t) if t else None for t in v.split(":")] for k, v in (sp.split("=") for sp in a.span)}
    tracks = {}
    for name in ("artery", "vein", "nerve"):
        src = f"{a.tracks}_{name}.json"
        if not os.path.exists(src):
            continue
        d = json.load(open(src))
        rows, dropped = clean_rows(d["rows"], name)
        top, bot = spans.get(name, (None, None))
        rows = [r for r in rows if (top is None or r["y"] <= top) and (bot is None or r["y"] >= bot)]
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
        montage(crops, tracks, labs, a.montage, every=a.every)
        print("montage", a.montage)


def hiatus_level(crops, meshes, side, art):
    """First level (top down) at which the tracked artery centroid falls inside her adductor magnus section:
    the artery passing through the adductor hiatus. Mesh-based, so approximate."""
    sfx = "_r" if side == "right" else "_l"
    if meshes.get("adductor_magnus" + sfx) is None:
        return None
    for r in art:
        if r["gap"] or r["y"] > -150:
            continue
        masks = section_masks(meshes, ["adductor_magnus"], side, r["y"], crops, (crops.a.shape[1], crops.a.shape[2]))
        mm = masks.get("adductor_magnus")
        if mm is None:
            continue
        pr, pc = crops.atlas_to_px(r["y"], r["x"], r["z"])
        pr, pc = int(round(float(pr))), int(round(float(pc)))
        if 0 <= pr < mm.shape[0] and 0 <= pc < mm.shape[1] and mm[pr, pc]:
            return r["y"]
    return None


# ---------------------------------------------------------------- montage
COL = {"artery": (255, 40, 40), "vein": (60, 120, 255), "nerve": (255, 230, 40)}


def montage(crops, tracks, labs, path, every=20, half_mm=22):
    """Tiles centred on the artery every `every` mm, lumen/fascicle outlines drawn: artery red, vein blue,
    nerve yellow. The human check: the artery is round and dark, the vein medial in the triangle and
    posterior in the canal, the nerve lateral in the triangle only."""
    h = int(half_mm / PX)
    art = [r for r in tracks["artery"] if not r["gap"]]
    tiles = []
    for r in art[::every]:
        y = r["y"]; im = crops.image(y)
        pr, pc = crops.atlas_to_px(y, r["x"], r["z"]); pr, pc = int(pr), int(pc)
        vis = np.ascontiguousarray(im).copy()
        for name, rows in tracks.items():
            rr = next((q for q in rows if q["y"] == y and not q["gap"]), None)
            if rr is None:
                continue
            mm = np.asarray(labs[rr["level_index"], :im.shape[0], :im.shape[1]]) == rr["lab"]
            if mm.any():
                vis[mm & ~ndi.binary_erosion(mm)] = COL[name]
        t = np.zeros((2 * h, 2 * h, 3), np.uint8)
        r0, r1 = max(0, pr - h), min(vis.shape[0], pr + h)
        c0, c1 = max(0, pc - h), min(vis.shape[1], pc + h)
        t[r0 - (pr - h):r1 - (pr - h), c0 - (pc - h):c1 - (pc - h)] = vis[r0:r1, c0:c1]
        pil = Image.fromarray(t); d = ImageDraw.Draw(pil)
        d.text((3, 3), f"y{int(y)} a{r['diam_mm']:.1f}", fill=(255, 255, 255))
        tiles.append(np.asarray(pil))
    if not tiles:
        return
    n = len(tiles); cols = min(8, n); rws = (n + cols - 1) // cols
    canvas = np.zeros((rws * 2 * h, cols * 2 * h, 3), np.uint8)
    for i, t in enumerate(tiles):
        canvas[(i // cols) * 2 * h:(i // cols + 1) * 2 * h, (i % cols) * 2 * h:(i % cols + 1) * 2 * h] = t
    pil = Image.fromarray(canvas); d = ImageDraw.Draw(pil)
    d.text((4, canvas.shape[0] - 12), "artery red, vein blue, nerve yellow; lateral left, anterior down", fill=(255, 255, 255))
    pil.save(path)


# ---------------------------------------------------------------- entry points
LAB_OF = {"artery": 1, "vein": 2, "nerve": 3}


def do_track(a):
    crops = Crops(a.crops, a.side)
    bf, blob = read_bundle_dir(a.bundle); meshes = meshes_by_id(bf, blob)
    ys = sorted([y for y in crops.ys if a.y_end <= y <= a.y_start], reverse=True)
    y0, art0, vein0, mid = seed_level(crops, meshes, a.side, FEMORAL, ys)
    ys = [y for y in ys if y <= y0]
    idx = {y: i for i, y in enumerate(ys)}
    store_path = f"{a.out}_labels.npy"
    labs = np.lib.format.open_memmap(store_path, mode="w+", dtype=np.uint8,
                                     shape=(len(ys), crops.a.shape[1], crops.a.shape[2]))

    pair = walk_pair(crops, ys, y0, art0["mask"], vein0["mask"])
    art_rows, art_masks = pair["artery"]; vein_rows, vein_masks = pair["vein"]
    print(f"artery: {sum(1 for r in art_rows if not r['gap'])} levels to y={art_rows[-1]['y'] if art_rows else None}")
    print(f"vein:   {sum(1 for r in vein_rows if not r['gap'])} levels to y={vein_rows[-1]['y'] if vein_rows else None}")
    art_xz = {r["y"]: (r["x"], r["z"]) for r in art_rows if not r["gap"]}
    nys = [y for y in ys if y >= y0 - a.nerve_span]
    n_rows, n_masks = walk_nerve(crops, meshes, a.side, FEMORAL, nys, y0, (art0["x"] + (12.0 if a.side == "right" else -12.0), art0["z"]), art_xz)
    trunk_end = next((r["y"] for r in n_rows[::-1] if not r["gap"]), None)
    print(f"nerve:  {sum(1 for r in n_rows if not r['gap'])} levels, trunk last seen y={trunk_end}")

    tracks = {"artery": art_rows, "vein": vein_rows, "nerve": n_rows}
    masks = {"artery": art_masks, "vein": vein_masks, "nerve": n_masks}
    for name, mk in masks.items():
        for y, m in mk.items():
            labs[idx[y], :m.shape[0], :m.shape[1]][m] = LAB_OF[name]
    labs.flush()
    hi = hiatus_level(crops, meshes, a.side, art_rows)
    for name, rows in tracks.items():
        for r in rows:
            if not r["gap"]:
                r["lab"] = LAB_OF[name]; r["level_index"] = idx[r["y"]]
        found = [r for r in rows if not r["gap"]]
        d = {"source": SOURCE, "badge": "rule-based", "structure": name, "side": a.side,
             "seed": {"y": y0, "x": round(float((art0 if name != "vein" else vein0)["x"]), 1),
                      "z": round(float((art0 if name != "vein" else vein0)["z"]), 1),
                      "rule": ("lateral member of the lumen pair at the inguinal ligament" if name == "artery" else
                               "medial member of the lumen pair at the inguinal ligament" if name == "vein" else
                               "fascicle blob lateral to the artery at the inguinal ligament")},
             "inguinal_midpoint": mid, "nerve_trunk_last_y": trunk_end, "adductor_hiatus_y": hi,
             "levels": len(rows), "tracked_levels": len(found),
             "y_top": found[0]["y"] if found else None, "y_bottom": found[-1]["y"] if found else None,
             "rows": rows}
        p = f"{a.out}_{name}.json"
        Path(p).write_text(json.dumps(d, indent=1))
        lp = p.replace(".json", "_labels.npy")
        if os.path.exists(lp):
            os.remove(lp)
        os.link(store_path, lp)                     # one shared label image, hard-linked per track file
        if found:
            print(f"{name}: {len(found)}/{len(rows)} levels, y {d['y_top']} .. {d['y_bottom']}, "
                  f"median d {np.median([r['diam_mm'] for r in found]):.1f} mm")
    print("adductor hiatus level", hi)
    if a.montage:
        montage(crops, tracks, labs, a.montage, every=a.every)
        print("montage", a.montage)


def do_report(a):
    vol = json.load(open(a.volume_report)) if a.volume_report and os.path.exists(a.volume_report) else {}
    out = {"source": SOURCE, "badge": "rule-based", "task": "Q55 femoral neurovascular bundle (VH female cryosections, 0.33 mm)",
           "voxel_mm": vol.get("voxel_mm", [0.5, 0.5, 1.0]), "volume_cm3": vol.get("volume_cm3", {}),
           "volume_tracks": vol.get("tracks", {}),
           "expected_diameter_mm": EXPECTED_MM, "structures": {}, "limits": [], "montages": a.montage or []}
    spans = {k: [float(t) if t else None for t in v.split(":")] for k, v in (sp.split("=") for sp in a.span)}
    for pre in a.tracks:
        for name in ("artery", "vein", "nerve"):
            p = f"{pre}_{name}{a.suffix}.json"
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
            dd = [r["diam_mm"] for r in found]; ins = [r["inscribed_mm"] for r in found]
            key = f"{name}:{d['side']}"
            out["structures"][key] = {
                "atlas_id": a.ids.get(f"{name}_{d['side']}"), "y_top": found[0]["y"], "y_bottom": found[-1]["y"],
                "levels": len(rows), "tracked_levels": len(found),
                "gaps_filled": len(rows) - len(found),
                "levels_dropped_by_cleaning": sum(1 for r in rows if r.get("dropped")),
                "diameter_mm": {"median": round(float(np.median(dd)), 1), "p10": round(float(np.percentile(dd, 10)), 1),
                                "p90": round(float(np.percentile(dd, 90)), 1),
                                "inscribed_median": round(float(np.median(ins)), 1)},
                "diameter_by_level": {str(int(r["y"])): r["diam_mm"] for r in found},
                "seed": d["seed"], "nerve_trunk_last_y": d.get("nerve_trunk_last_y"),
                "adductor_hiatus_y": d.get("adductor_hiatus_y"),
            }
    out["limits"] = [
        "Crops start at y = +20 mm and the lumen pair is first separable at y = +14, ~19 mm below the "
        "inguinal-ligament midpoint (y = +32.5): the top of the common femoral vessels is not covered.",
        "Only the femoral triangle and the entrance of the adductor canal are shipped (down to y = -46). "
        "Below that the walk drifts into her dark-red muscle: the masks were checked on the montage and "
        "could not be confirmed, so the adductor canal proper and the adductor hiatus are NOT covered and "
        "no hiatus level is reported.",
        "The tracked mask is the LUMEN (clotted blood), not the vessel wall; a lumen abutting muscle without a pale wall is kept at its dark core and under-measured.",
        "Roof/floor muscle meshes are transferred, so the corridor and the adductor-hiatus level derived from adductor magnus are approximate.",
        "The femoral nerve is tracked as a trunk only; it divides within a few centimetres of the ligament and the branches are not followed.",
    ]
    Path(a.out).write_text(json.dumps(out, indent=1))
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "diameter_by_level"} for k, v in out["structures"].items()}, indent=1))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="mode", required=True)
    t = sub.add_parser("track")
    t.add_argument("--crops", required=True); t.add_argument("--side", required=True, choices=["right", "left"])
    t.add_argument("--bundle", default="build/viewer_f"); t.add_argument("--y-start", type=float, default=20)
    t.add_argument("--y-end", type=float, default=-320); t.add_argument("--out", required=True)
    t.add_argument("--montage", default=None); t.add_argument("--every", type=int, default=20)
    t.add_argument("--nerve-span", type=float, default=70.0, help="mm below the seed to look for the nerve trunk")
    c = sub.add_parser("clean")
    c.add_argument("--tracks", required=True, help="track prefix (<prefix>_artery.json ...)")
    c.add_argument("--span", nargs="*", default=[], help="name=y_top:y_bottom, the range to ship")
    c.add_argument("--crops", default=None); c.add_argument("--side", default="right", choices=["right", "left"])
    c.add_argument("--montage", default=None); c.add_argument("--every", type=int, default=8)
    r = sub.add_parser("report")
    r.add_argument("--tracks", nargs="+", required=True, help="track prefixes (<prefix>_artery.json ...)")
    r.add_argument("--volume-report", default=None); r.add_argument("--out", required=True)
    r.add_argument("--montage", nargs="*", default=[])
    r.add_argument("--suffix", default="", help="track file suffix, e.g. _clean")
    r.add_argument("--span", nargs="*", default=[], help="name=y_top:y_bottom, the range actually shipped")
    r.add_argument("--ids", type=json.loads, default={}, help='{"artery_right": "femoral_a_r", ...}')
    a = ap.parse_args()
    {"track": do_track, "clean": do_clean, "report": do_report}[a.mode](a)


if __name__ == "__main__":
    main()
