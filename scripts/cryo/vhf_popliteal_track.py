"""Track the POPLITEAL artery and vein (and the tibial nerve beside them) through the female's
FULL-RESOLUTION cryosection crops (Q56).

    python3 scripts/cryo/vhf_popliteal_track.py track --crops SCRATCH/vh_cryo_f/thigh --side right \
        --bundle build/viewer_f --y-start -290 --y-end -500 --out SCRATCH/popliteal_right --common-fibular
    python3 scripts/cryo/vhf_popliteal_track.py clean --tracks SCRATCH/popliteal_right \
        --span artery=-305:-386 vein=-305:-386 tibial_n=-340:-386 common_fibular_n=-305:-386 \
        --crops SCRATCH/vh_cryo_f/thigh --side right --every 8 --exclude common_fibular_n \
        --montage data/ct_sources/task_outputs/vhf_popliteal_cryo_right.png
    python3 scripts/cryo/vhf_nerve_volume.py --crops SCRATCH/vh_cryo_f/thigh \
        --track popliteal_a_r=SCRATCH/popliteal_right_artery_clean.json:-305:-386 \
        --track popliteal_v_r=SCRATCH/popliteal_right_vein_clean.json:-305:-386 \
        --track tibial_n=SCRATCH/popliteal_right_tibial_n_clean.json:-340:-386 \
        --out data/ct_sources/task_outputs/vhf_popliteal_cryo.nii.gz \
        --labels-out mappings/vhf_popliteal_labels.json \
        --mapping-out mappings/subjects/ct_vhf_popliteal_volume_mapping.json --subject ct_vhf_popliteal
    python3 scripts/cryo/vhf_popliteal_track.py report --tracks SCRATCH/popliteal_right --suffix _clean \
        --span artery=-305:-386 vein=-305:-386 tibial_n=-340:-386 common_fibular_n=-305:-386 \
        --ids '{"artery_right": "popliteal_a_r", "vein_right": "popliteal_v_r", "tibial_n_right": "tibial_n"}' \
        --volume data/ct_sources/task_outputs/vhf_popliteal_cryo.nii.gz \
        --labels mappings/vhf_popliteal_labels.json \
        --montage-path data/ct_sources/task_outputs/vhf_popliteal_cryo_right.png --limits "..." \
        --volume-report data/ct_sources/task_outputs/vhf_popliteal_cryo_report.json --out <that same file>
    cp mappings/subjects/ct_vhf_popliteal_volume_mapping.json build/vh/ && \
    python3 scripts/ingest_volume_geometry.py convert data/ct_sources/task_outputs/vhf_popliteal_cryo.nii.gz \
        --labels vhf_popliteal --subject ct_vhf_popliteal --origin='7.769,-885.229,14.137' --smooth 1.0

Companion of vhf_femoral_track.py (Q55): the same crops (vhf_stream_crops.py), the same lumen rule, the same
paired local walk (walk_pair, here with one added rule: walk_pair_fossa), the same cleaning gate and the same
volume builder (vhf_nerve_volume.py). What changes is the seed landmark, the fossa-context rule and the DEPTH
order that the seed and the checks work in.

ANATOMY (Gray's 42nd ed. 'Knee and popliteal fossa'; Moore 8th ed.). In the popliteal fossa the neurovascular
contents lie in ONE plane of depth: from superficial (posterior) to deep (anterior) TIBIAL NERVE, POPLITEAL
VEIN, POPLITEAL ARTERY. The artery is the deepest structure of the fossa, lying directly on the popliteal
surface of the femur and then on the capsule of the knee joint and popliteus. It begins at the adductor hiatus
(the lower border of adductor magnus) and ends at the lower border of popliteus, dividing into the anterior
tibial artery and the tibioperoneal (fibular) trunk. The common fibular nerve leaves the sciatic trunk above
the fossa and runs laterally along the medial border of the biceps femoris tendon, away from the vessels.

RULES (+Z is anterior, +X is the subject's right/lateral on this side; 1 mm levels, 0.33 mm pixels):
  lumen     = vhf_femoral_track.vessel_lumina/vessel_candidates unchanged: a near-black core (3 mm mean red
              < 58; her muscle is dark red 75-95, fat cream > 150), opened by 0.7 mm, touching lumina split by
              a distance watershed, grown out to its wall (red < 105, at most 2 mm past the core), 6-160 mm2,
              solidity >= 0.75, aspect <= 2.5, 20th percentile of red < 40 and a pale wall (ring red >= 30
              above the lumen).
  seed      = LANDMARK RULE, not a hand click: the FEMUR's popliteal surface. Walking down from --y-start, the
              first level at which a PAIR of lumina lies POSTERIOR to the posterior cortex of her femur
              section (z below it, within 40 mm of it), the two 3-20 mm apart in depth, no more than 14 mm
              apart across, largest combined area. The ANTERIOR member (larger z, i.e. the one on the femur)
              is the ARTERY, the POSTERIOR member is the VEIN. That is the textbook order and it is also what
              is checked afterwards on the finished label volume (mean atlas z per structure per 10 mm band).
  vessels   = walk_pair_fossa, i.e. vhf_femoral_track.walk_pair with the fossa-context rule added: each
              level, inside its own previous atlas position dilated by reach_mm, the darkest round component
              (window 15th percentile of red + 18) of 0.35-3x its own previous area, solidity >= 0.7, aspect
              <= 2.6, with a pale wall, at least 30% of whose surrounding annulus is NOT muscle-red (the
              vessels of the fossa lie in fat; without this the walk follows the dark striations inside
              gastrocnemius below the knee), and the two must stay within PAIR_MM of each other because
              artery and vein share the popliteal sheath from the hiatus to the lower border of popliteus.
              The walk runs DOWN from the seed and UP from the seed to the hiatus. A mask wider than ~1.2x
              the textbook maximum (artery 60 mm2 ~ 8.7 mm, vein 120 mm2 ~ 12.4 mm) is refused: past that the
              component has eaten into muscle.
  tibial n. = fascicle texture (vhf_nerve_track.nerve_blobs) inside the fossa corridor, POSTERIOR to the
              tracked artery (z at least 2 mm below it) and 3-35 mm from it, within 6 mm of its own previous
              position. This is the nerve's RELATION to the vessels, measured per level, not a second copy of
              the shipped sciatic track: the shipped sciatic (vhf_nerves_cryo.nii.gz) stops at y = -235, well
              above the fossa, so the levels here are new.
  cleaning  = for a NERVE, a tracked level whose blob is surrounded by more than 70% muscle-red is dropped
              (it is an intramuscular fat pocket or a tendon, not a nerve in the intermuscular fat).
              For every structure, a tracked level whose mask is ragged (solidity < 0.85) or whose diameter falls outside the
              CLEAN_MM band widened by 25% drops back to a gap; the volume builder fills gaps of <= 12 levels
              from the neighbouring section. CLEAN_MM keeps the vein's floor LOW (3 mm) on purpose: this is a
              cadaver and a vein with no blood pressure in it is collapsed, so a vein under the textbook 7 mm
              is plausible and is reported as measured, not forced up.
  gate      = a structure whose median diameter is more than twice the textbook expectation or under half of
              it, or that survives over less than MIN_SPAN_MM mm, or on fewer than MIN_LEVELS levels, is NULLED
              in the volume mapping with the reason in its note rather than shipped under an anatomical name.

LIMITS: the tracked mask is the LUMEN (clotted blood), not the vessel wall, so the diameters are lumen
diameters and a lumen abutting muscle without a pale wall between is kept at its dark core and under-measured.
The roof/floor meshes of the corridor are TRANSFERRED muscle meshes, so the corridor is approximate and is
only used to reject far-away blobs. The division of the artery at the lower border of popliteus is not
resolved: the walk is stopped at the last level a human verified on the montage. The common fibular nerve is
tracked only if it is unambiguous over the whole shipped span; otherwise it is left unshipped with the reason
in the mapping note. Rule-based; badged; volumes and per-level diameters recorded.
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
from scripts.cryo.vhf_nerve_track import (Crops, PX, corridor_mask, disk, photo_classes,  # noqa: E402
                                          section_masks)
from scripts.cryo.vhf_femoral_track import (_dark_components, _row, blob_stats, clean_rows,  # noqa: E402
                                            nerve_candidates, outside_gel, roundness_score,
                                            vessel_candidates)
from scripts.transfer.bundle_io import meshes_by_id, read_bundle_dir  # noqa: E402

SOURCE = ("U.S. National Library of Medicine, The Visible Human Project (public domain), female cryosections at full "
          "resolution (0.33 mm) via the NCI Imaging Data Commons. Derived data (scripts/cryo/vhf_popliteal_track.py).")
POPLITEAL = {"roof": ["biceps_femoris", "semitendinosus", "semimembranosus", "gastrocnemius", "plantaris"],
             "floor": ["adductor_magnus", "popliteus", "soleus", "vastus_lateralis"],
             "bone": ["femur", "tibia", "fibula", "patella"], "corridor_mm": 20.0,
             "core_thr": 58.0, "wall_thr": 105.0, "vessel_mm2": (6.0, 160.0), "nerve_mm2": (6.0, 140.0),
             "max_mm2": {"artery": 60.0, "vein": 120.0}}
# textbook adult lumina (Gray's 42nd ed.; Moore 8th ed.)
EXPECTED_MM = {"artery": (5.0, 8.0), "vein": (7.0, 11.0), "tibial_n": (4.0, 14.0), "common_fibular_n": (2.0, 9.0)}
# band used by the cleaning gate: the vein's floor is dropped to 3 mm because a cadaveric vein is collapsed
CLEAN_MM = {"artery": (4.0, 9.0), "vein": (3.0, 12.0), "tibial_n": (3.0, 15.0), "common_fibular_n": (2.0, 10.0)}
ATLAS_ORIGIN = (7.769, -885.229, 14.137)      # her torso/legs RAS origin, as the femoral run used
PAIR_MM = 22.0
MIN_LEVELS = 20        # a named cord is shipped only when it was verified over
MIN_SPAN_MM = 30.0     # at least 30 mm of course, on at least 20 separate levels
NAMES = ("artery", "vein", "tibial_n", "common_fibular_n")
LAB_OF = {"artery": 1, "vein": 2, "tibial_n": 3, "common_fibular_n": 4}


# ---------------------------------------------------------------- landmark and seed
def femur_posterior(meshes, side, y, crops, shape):
    """(x, z) of the POPLITEAL SURFACE of her femur at level y: the mid-x of the femur section and the
    posterior (lowest z) edge of it. None where the femur section is empty (below the condyles)."""
    masks = section_masks(meshes, ["femur"], side, y, crops, shape)
    mm = masks.get("femur")
    if mm is None or not mm.any():
        return None
    rr, cc = np.nonzero(mm)
    ax, az = crops.px_to_atlas(y, rr, cc)
    return {"x": float(np.median(ax)), "z_post": float(np.min(az)), "z_mid": float(np.median(az))}


def seed_pair(cands, fem, max_behind=40.0):
    """artery = the ANTERIOR (deep) member, vein = the POSTERIOR member of the best lumen pair lying behind
    the femur's popliteal surface: both with z below the posterior cortex, within `max_behind` of it, the two
    3-20 mm apart in depth, at most 14 mm apart across, largest combined area."""
    near = [c for c in cands if fem["z_post"] - max_behind <= c["z"] <= fem["z_post"] + 3.0
            and abs(c["x"] - fem["x"]) <= 35.0]
    best = None
    for i in range(len(near)):
        for j in range(len(near)):
            if i == j:
                continue
            a, v = near[i], near[j]                       # a deep (anterior), v superficial (posterior)
            dz = a["z"] - v["z"]
            if not (3.0 <= dz <= 20.0) or abs(a["x"] - v["x"]) > 14.0:
                continue
            tot = a["area_mm2"] + v["area_mm2"]
            if best is None or tot > best[0]:
                best = (tot, a, v)
    return (best[1], best[2]) if best else (None, None)


def level_corridor(crops, meshes, side, spec, y, shape):
    names = list(dict.fromkeys(spec["roof"] + spec["floor"] + spec["bone"]))
    masks = section_masks(meshes, names, side, y, crops, shape)
    cor, _ = corridor_mask(crops.image(y), masks, spec)
    return cor


def seed_level(crops, meshes, side, spec, ys, log=print):
    """First level from --y-start at which the femur-popliteal-surface pair rule fires."""
    for y in ys:
        im = crops.image(y)
        fem = femur_posterior(meshes, side, y, crops, im.shape[:2])
        if fem is None:
            continue
        cor = level_corridor(crops, meshes, side, spec, y, im.shape[:2])
        cands, lab = vessel_candidates(im, cor, spec)
        for c in cands:
            ax, az = crops.px_to_atlas(y, c["rc"][0], c["rc"][1])
            c["x"], c["z"] = float(ax), float(az)
        a, v = seed_pair(cands, fem)
        if a is None:
            continue
        log(f"seed level y={y}: femur popliteal surface x{fem['x']:.0f} z{fem['z_post']:.0f} | "
            f"artery x{a['x']:.0f} z{a['z']:.0f} d{a['diam_mm']:.1f} | vein x{v['x']:.0f} z{v['z']:.0f} d{v['diam_mm']:.1f}")
        seed = {"y": y, "femur_popliteal_surface": {"x": round(fem["x"], 1), "z": round(fem["z_post"], 1)},
                "rule": ("deepest pair of lumina behind the posterior cortex of the femur; the ANTERIOR member "
                         "is the artery (it lies on the popliteal surface), the POSTERIOR member the vein")}
        return y, dict(a, mask=(lab == a["lab"])), dict(v, mask=(lab == v["lab"])), seed
    raise SystemExit("no popliteal lumen pair found in the given levels")


# ---------------------------------------------------------------- paired vessel walk
def walk_pair_fossa(crops, ys, y0, mask_a, mask_v, pair_mm=PAIR_MM, reach_mm=4.0, max_gap=8,
                    max_mm2=None, fat_frac=0.30, log=print):
    """vhf_femoral_track.walk_pair with ONE rule added, because the popliteal vessels lie in the FAT of the
    fossa while the femoral ones lie in a sheath against muscle: a candidate lumen is refused unless at least
    `fat_frac` of the 0.7-2 mm annulus around it is NOT muscle-red (3 mm mean red > 110, i.e. the fossa's
    fat and loose connective tissue). Without it the walk follows the dark intramuscular striations of
    gastrocnemius below the knee joint line - that was checked on the montage and is the walk's one failure
    mode. Everything else is unchanged: each member is the darkest round component (window 15th percentile of
    red + 18) inside its own previous atlas position dilated by reach_mm, area 0.35-3x its own previous area,
    solidity >= 0.7, aspect <= 2.6, a pale wall (ring red >= 20 above the lumen), and the pair must stay
    within `pair_mm` of each other (one popliteal sheath)."""
    max_mm2 = max_mm2 or POPLITEAL["max_mm2"]
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
        cl = photo_classes(im)
        R = cl["R"]
        R3 = ndi.uniform_filter(R, 3)
        gel = outside_gel(im[..., 2].astype(np.float32) > R)
        not_muscle = (cl["m5"] > 110) & ~gel
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
            fat = float(not_muscle[ring].mean())
            if fat < fat_frac:                      # a dark patch inside a muscle belly, not a lumen in fat
                continue
            cands.append({"mask": mm, "s": s, "xz": tuple(float(v) for v in crops.px_to_atlas(y, *s["rc"])),
                          "area": a, "fat": fat})
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
        if best is not None:
            take = {"artery": best[1], "vein": best[2]}
        else:
            singles = {nm: max(ok[nm], default=None) for nm in st}
            names = [nm for nm in st if singles[nm] is not None]
            if len(names) == 2 and singles["artery"][1] == singles["vein"][1]:
                nm = "artery" if singles["artery"][0] >= singles["vein"][0] else "vein"
                take = {nm: singles[nm][1]}
            else:
                take = {nm: singles[nm][1] for nm in names}
        for nm in st:
            if nm in take:
                c = cands[take[nm]]
                st[nm].update({"gaps": 0, "a": c["area"], "xz": c["xz"]})
                st[nm]["masks"][y] = c["mask"]
                st[nm]["rows"].append(dict(_row(y, c["s"], c["xz"], thr), fat=round(c["fat"], 2)))
            else:
                st[nm]["gaps"] += 1
                st[nm]["rows"].append({"y": y, "gap": True, "x": round(st[nm]["xz"][0], 1),
                                       "z": round(st[nm]["xz"][1], 1)})
        if all(st[nm]["gaps"] > max_gap for nm in st):
            break
    out = {}
    for nm in st:
        rows = st[nm]["rows"]
        while rows and rows[-1]["gap"]:
            rows.pop()
        out[nm] = (rows, {y: m for y, m in st[nm]["masks"].items() if any(r["y"] == y and not r["gap"] for r in rows)})
    return out


# ---------------------------------------------------------------- nerve walk
def walk_nerve(crops, meshes, side, spec, ys, art_xz, name="tibial_n", reach_mm=6.0, max_gap=4,
               lateral_min=-3.0, behind_mm=(8.0, 35.0), log=print):
    """Follow a nerve beside the tracked artery. Its SEED is a relation to the tracked artery, not a hand
    click: at the first level, the fascicle-texture blob (vhf_nerve_track.nerve_blobs, inside the fossa
    corridor) that lies POSTERIOR to the artery (z at least 2 mm below it), `behind_mm` away from it, and at
    least `lateral_min` mm LATERAL of it, NEAREST to the artery. In the popliteal fossa that is the tibial
    nerve: it is the superficial member of the trio and it lies posterolateral to the vein. Afterwards it is
    a walk: the same relation, plus within `reach_mm` of its own previous position."""
    sg = 1.0 if side == "right" else -1.0
    rows, masks = [], {}
    px = pz = None
    gaps = 0
    for i, y in enumerate(ys):
        im = crops.image(y)
        cor = level_corridor(crops, meshes, side, spec, y, im.shape[:2])
        cands, lab = nerve_candidates(im, cor, spec)
        ax = art_xz.get(y)
        best, bd = None, 1e9
        for c in cands:
            cx, cz = crops.px_to_atlas(y, c["rc"][0], c["rc"][1])
            cx, cz = float(cx), float(cz)
            if ax is not None:
                da = float(np.hypot(cx - ax[0], cz - ax[1]))
                if cz > ax[1] - 2.0 or not (behind_mm[0] <= da <= behind_mm[1]):
                    continue
                if sg * (cx - ax[0]) < lateral_min:
                    continue
            elif px is None:
                continue
            d = da if px is None else float(np.hypot(cx - px, cz - pz))
            if px is not None and d > reach_mm:
                continue
            if d < bd:
                best, bd = (c, cx, cz), d
        if best is None:
            if px is None:                     # the seed level itself gave nothing: try the next level down
                continue
            gaps += 1
            rows.append({"y": y, "gap": True, "x": round(px, 1), "z": round(pz, 1)})
            if gaps > max_gap:
                break
            continue
        gaps = 0
        c, cx, cz = best
        px, pz = cx, cz
        masks[y] = lab == c["lab"]
        s = blob_stats(masks[y])
        rows.append({"y": y, "gap": False, "x": round(cx, 1), "z": round(cz, 1),
                     "area_mm2": round(c["area_mm2"], 1), "diam_mm": round(s["diam_mm"], 1),
                     "inscribed_mm": round(s["inscribed_mm"], 1), "solidity": round(s["solidity"], 2),
                     "aspect": round(s["aspect"], 2), "inside": round(c["inside"], 2)})
    while rows and rows[-1]["gap"]:
        rows.pop()
    return rows, masks


def popliteus_end(meshes, side, y_floor=-600.0):
    """Lower border of popliteus from her mesh: where the popliteal artery divides (Gray's). Approximate -
    the muscle mesh is transferred."""
    m = meshes.get("popliteus_" + side[0])
    return float(m["v"][:, 1].min()) if m is not None else y_floor


# ---------------------------------------------------------------- montage
COL = {"artery": (255, 40, 40), "vein": (60, 120, 255), "tibial_n": (255, 230, 40), "common_fibular_n": (40, 255, 120)}


def montage(crops, tracks, labs, path, every=15, half_mm=36):
    """Tiles centred on the artery every `every` mm with the tracked outlines drawn on the photograph. The
    human check: the ARTERY (red) is the deepest and roundest, the VEIN (blue) sits between it and the NERVE
    (yellow), and no outline lies inside a muscle belly or inside bone."""
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
    bar = 34
    canvas = np.zeros((rws * 2 * h + bar, cols * 2 * h, 3), np.uint8)
    for i, t in enumerate(tiles):
        canvas[(i // cols) * 2 * h:(i // cols + 1) * 2 * h, (i % cols) * 2 * h:(i % cols + 1) * 2 * h] = t
    pil = Image.fromarray(canvas)
    d = ImageDraw.Draw(pil)
    y0 = rws * 2 * h + 4
    d.text((4, y0), "VH female, right popliteal fossa, full-resolution cryosections (0.33 mm).  "
                    "LEFT of each tile = LATERAL, RIGHT = MEDIAL;  DOWN = ANTERIOR (deep), UP = POSTERIOR (superficial).",
           fill=(255, 255, 255))
    d.text((4, y0 + 14), "popliteal artery RED (deepest, on the femur/capsule) - popliteal vein BLUE (between) - "
                         "tibial nerve YELLOW (most superficial).  Tile label: level y (atlas mm), artery lumen diameter.",
           fill=(255, 255, 255))
    pil.save(path)


# ---------------------------------------------------------------- entry points
def do_track(a):
    crops = Crops(a.crops, a.side)
    bf, blob = read_bundle_dir(a.bundle)
    meshes = meshes_by_id(bf, blob)
    ys_all = sorted([y for y in crops.ys if a.y_end <= y <= a.y_start], reverse=True)
    y0, art0, vein0, seed = seed_level(crops, meshes, a.side, POPLITEAL, ys_all)
    idx = {y: i for i, y in enumerate(ys_all)}
    store_path = f"{a.out}_labels.npy"
    labs = np.lib.format.open_memmap(store_path, mode="w+", dtype=np.uint8,
                                     shape=(len(ys_all), crops.a.shape[1], crops.a.shape[2]))
    down = [y for y in ys_all if y <= y0]
    up = [y for y in ys_all if y >= y0][::-1]
    rows, masks = {n: [] for n in ("artery", "vein")}, {n: {} for n in ("artery", "vein")}
    for leg in (down, up):
        pair = walk_pair_fossa(crops, leg, y0, art0["mask"], vein0["mask"], pair_mm=PAIR_MM,
                               max_mm2=POPLITEAL["max_mm2"])
        for nm in ("artery", "vein"):
            r, m = pair[nm]
            rows[nm] += [q for q in r if q["y"] != y0 or not masks[nm]]
            masks[nm].update(m)
    for nm in ("artery", "vein"):
        by_y = {}
        for r in rows[nm]:
            if r["y"] not in by_y or not r["gap"]:
                by_y[r["y"]] = r
        rows[nm] = [by_y[y] for y in sorted(by_y, reverse=True)]
        while rows[nm] and rows[nm][0]["gap"]:
            rows[nm].pop(0)
        while rows[nm] and rows[nm][-1]["gap"]:
            rows[nm].pop()
        print(f"{nm}: {sum(1 for r in rows[nm] if not r['gap'])} levels, "
              f"y {rows[nm][0]['y'] if rows[nm] else None} .. {rows[nm][-1]['y'] if rows[nm] else None}")

    art_xz = {r["y"]: (r["x"], r["z"]) for r in rows["artery"] if not r["gap"]}
    ys_a = sorted(art_xz, reverse=True)
    tracks = {"artery": rows["artery"], "vein": rows["vein"]}
    masks_all = {"artery": masks["artery"], "vein": masks["vein"]}
    jobs = [("tibial_n", {})]
    if a.common_fibular:
        jobs.append(("common_fibular_n", {"lateral_min": 18.0, "behind_mm": (15.0, 45.0)}))
    for name, kw in jobs:                      # the nerve is walked DOWN and UP from the vessels' seed level
        nrows, nmasks = [], {}
        for leg in ([y for y in ys_a if y <= y0], [y for y in ys_a if y >= y0][::-1]):
            r, m = walk_nerve(crops, meshes, a.side, POPLITEAL, leg, art_xz, name,
                              reach_mm=a.nerve_reach, max_gap=a.nerve_gap, **kw)
            nrows += r
            nmasks.update(m)
        by_y = {}
        for r in nrows:
            if r["y"] not in by_y or not r["gap"]:
                by_y[r["y"]] = r
        nrows = [by_y[y] for y in sorted(by_y, reverse=True)]
        while nrows and nrows[0]["gap"]:
            nrows.pop(0)
        while nrows and nrows[-1]["gap"]:
            nrows.pop()
        print(f"{name}: {sum(1 for r in nrows if not r['gap'])} of {len(nrows)} levels")
        tracks[name] = nrows
        masks_all[name] = nmasks
    for name, mk in masks_all.items():
        for y, m in mk.items():
            labs[idx[y], :m.shape[0], :m.shape[1]][m] = LAB_OF[name]
    labs.flush()
    pop_end = popliteus_end(meshes, a.side)
    for name, rws in tracks.items():
        for r in rws:
            if not r["gap"]:
                r["lab"] = LAB_OF[name]
                r["level_index"] = idx[r["y"]]
        found = [r for r in rws if not r["gap"]]
        d = {"source": SOURCE, "badge": "rule-based", "structure": name, "side": a.side,
             "seed": dict(seed, structure=name), "popliteus_lower_border_y": round(pop_end, 1),
             "levels": len(rws), "tracked_levels": len(found),
             "y_top": found[0]["y"] if found else None, "y_bottom": found[-1]["y"] if found else None,
             "rows": rws}
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
    """A nerve of the fossa lies in the intermuscular FAT, never inside a belly. Drop back to a gap any
    tracked level whose 0.7-2 mm annulus is more than `max_muscle` muscle-red (vhf_nerve_track.photo_classes),
    i.e. a pale blob surrounded by muscle - an intramuscular fat pocket or a tendon, not the nerve. Checked
    on the photograph, which is why it runs at cleaning time and not inside the walk."""
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
        if name.endswith("_n") and a.crops:                # nerves: also drop blobs that sit inside a belly
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
        shown = {k: v for k, v in tracks.items() if k not in a.exclude}   # only what is shipped is drawn
        montage(crops, shown, labs, a.montage, every=a.every)
        print("montage", a.montage)


def gate(name, med, levels, span_mm=1e9):
    """The plausibility gate. A structure is NOT shipped under its anatomical name if its median lumen /
    section diameter is more than twice the textbook maximum or under half the textbook minimum (the mask has
    run into muscle, or what is left is a fragment of something else), or if it was verified over less than
    MIN_SPAN_MM of course, or on fewer than MIN_LEVELS levels (too short and too broken to call a named
    structure). It is nulled in the volume mapping with this reason in its note."""
    lo, hi = EXPECTED_MM[name]
    if span_mm < MIN_SPAN_MM or levels < MIN_LEVELS:
        why = []
        if span_mm < MIN_SPAN_MM:
            why.append(f"only {span_mm:.0f} mm of course (< {MIN_SPAN_MM:.0f} mm)")
        if levels < MIN_LEVELS:
            why.append(f"only {levels} verified levels (< {MIN_LEVELS})")
        return "too short and too broken to ship under this name: " + " and ".join(why)
    if med > 2 * hi:
        return f"median lumen {med} mm is more than twice the expected maximum ({hi} mm)"
    if med < 0.5 * lo:
        return f"median {med} mm is far under the expected minimum ({lo} mm): a fragment, not the structure"
    return None


def depth_order(volume, labels_json, origin=ATLAS_ORIGIN):
    """Mean atlas z per label per 10 mm band of atlas y, straight off the shipped label volume (the grid's
    axes are atlas x, atlas z, atlas y + the atlas origin). +Z is anterior, so the ARTERY (deepest, on the
    femur and the knee capsule) must have the LARGEST z in every band, then the vein, then the tibial
    nerve."""
    import nibabel as nib
    img = nib.load(volume)
    vol = np.asarray(img.dataobj)
    aff = img.affine
    names = {int(k): v for k, v in json.load(open(labels_json))["labels"].items()}
    ijk = np.array(np.nonzero(vol))
    if not ijk.size:
        return {}
    xyz = aff[:3, :3] @ ijk + aff[:3, 3:4]
    xyz = xyz - np.array([[origin[0]], [origin[2]], [origin[1]]])      # grid axes: atlas x, atlas z, atlas y
    lab = vol[tuple(ijk)]
    y = xyz[2]
    out = {}
    lo, hi = np.floor(y.min() / 10) * 10, np.ceil(y.max() / 10) * 10
    for b0 in np.arange(hi, lo, -10):
        sel = (y <= b0) & (y > b0 - 10)
        if sel.sum() < 20:
            continue
        band = {}
        for l, nm in names.items():
            m = sel & (lab == l)
            if m.sum() >= 10:
                band[nm] = round(float(xyz[1][m].mean()), 1)
        if len(band) >= 2:
            out[f"{int(b0 - 10)}..{int(b0)}"] = band
    return out


def do_report(a):
    vol = json.load(open(a.volume_report)) if a.volume_report and os.path.exists(a.volume_report) else {}
    out = {"source": SOURCE, "badge": "rule-based",
           "task": "Q56 popliteal artery and vein with the tibial nerve (VH female cryosections, 0.33 mm)",
           "voxel_mm": vol.get("voxel_mm", [0.5, 0.5, 1.0]), "volume_cm3": vol.get("volume_cm3", {}),
           "volume_tracks": vol.get("tracks", {}), "expected_diameter_mm": EXPECTED_MM,
           "cleaning_band_mm": CLEAN_MM, "structures": {}, "nulled": {}, "limits": [],
           "montage": a.montage_path, "verification": {}}
    spans = {k: [float(t) if t else None for t in v.split(":")] for k, v in (sp.split("=") for sp in a.span)}
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
        dd = [r["diam_mm"] for r in found]
        ins = [r["inscribed_mm"] for r in found]
        med = round(float(np.median(dd)), 1)
        g = gate(name, med, len(found), abs(found[0]["y"] - found[-1]["y"]))
        key = f"{name}:{d['side']}"
        out["structures"][key] = {
            "atlas_id": a.ids.get(f"{name}_{d['side']}"), "shipped": g is None,
            "y_top": found[0]["y"], "y_bottom": found[-1]["y"],
            "levels": len(rows), "tracked_levels": len(found), "gaps_filled": len(rows) - len(found),
            "levels_dropped_by_cleaning": sum(1 for r in rows if r.get("dropped")),
            "diameter_mm": {"median": med, "p10": round(float(np.percentile(dd, 10)), 1),
                            "p90": round(float(np.percentile(dd, 90)), 1),
                            "inscribed_median": round(float(np.median(ins)), 1)},
            "diameter_by_level": {str(int(r["y"])): r["diam_mm"] for r in found},
            "seed": d["seed"], "popliteus_lower_border_y": d.get("popliteus_lower_border_y")}
        if g:
            out["nulled"][key] = g
    tr = {}
    for name in NAMES:
        p = f"{a.tracks}_{name}{a.suffix}.json"
        if os.path.exists(p):
            tr[name] = {r["y"]: r for r in json.load(open(p))["rows"] if not r["gap"]}
    if "tibial_n" in tr:
        rel = {}
        for other in ("artery", "vein"):
            ys = sorted(set(tr["tibial_n"]) & set(tr.get(other, {})), reverse=True)
            if not ys:
                continue
            post = [tr[other][y]["z"] - tr["tibial_n"][y]["z"] for y in ys]      # +ve: the nerve is behind it
            latl = [tr["tibial_n"][y]["x"] - tr[other][y]["x"] for y in ys]      # +ve: lateral to it (right side)
            rel[f"tibial_n_vs_{other}"] = {
                "levels": len(ys), "y_top": ys[0], "y_bottom": ys[-1],
                "posterior_offset_mm": {"median": round(float(np.median(post)), 1),
                                        "min": round(float(np.min(post)), 1), "max": round(float(np.max(post)), 1)},
                "lateral_offset_mm": {"median": round(float(np.median(latl)), 1),
                                      "min": round(float(np.min(latl)), 1), "max": round(float(np.max(latl)), 1)},
                "levels_with_the_nerve_superficial": sum(1 for v in post if v > 0)}
        out["verification"]["tibial_nerve_relation"] = rel
    if a.volume and a.labels and os.path.exists(a.volume):
        out["verification"]["depth_order_mean_atlas_z_per_10mm_band"] = depth_order(a.volume, a.labels)
        out["verification"]["depth_rule"] = ("+Z is anterior: the popliteal artery (deepest, on the femur and the "
                                             "knee capsule) must have the largest mean z, then the popliteal vein, "
                                             "then the tibial nerve (most superficial).")
    out["limits"] = a.limits or out["limits"]
    Path(a.out).write_text(json.dumps(out, indent=1))
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "diameter_by_level"}
                      for k, v in out["structures"].items()}, indent=1))
    print(json.dumps(out["verification"].get("depth_order_mean_atlas_z_per_10mm_band", {}), indent=1))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="mode", required=True)
    t = sub.add_parser("track")
    t.add_argument("--crops", required=True)
    t.add_argument("--side", required=True, choices=["right", "left"])
    t.add_argument("--bundle", default="build/viewer_f")
    t.add_argument("--y-start", type=float, default=-290)
    t.add_argument("--y-end", type=float, default=-500)
    t.add_argument("--out", required=True)
    t.add_argument("--montage", default=None)
    t.add_argument("--every", type=int, default=15)
    t.add_argument("--common-fibular", action="store_true", help="also attempt the common fibular nerve")
    t.add_argument("--nerve-reach", type=float, default=9.0, help="mm a nerve may move between levels")
    t.add_argument("--nerve-gap", type=int, default=20, help="levels without a fascicle blob before the nerve walk stops")
    c = sub.add_parser("clean")
    c.add_argument("--tracks", required=True)
    c.add_argument("--span", nargs="*", default=[], help="name=y_top:y_bottom, the range to ship")
    c.add_argument("--crops", default=None)
    c.add_argument("--side", default="right", choices=["right", "left"])
    c.add_argument("--montage", default=None)
    c.add_argument("--every", type=int, default=15)
    c.add_argument("--exclude", nargs="*", default=[], help="structures to leave off the montage (not shipped)")
    r = sub.add_parser("report")
    r.add_argument("--tracks", required=True)
    r.add_argument("--suffix", default="")
    r.add_argument("--span", nargs="*", default=[])
    r.add_argument("--ids", type=json.loads, default={})
    r.add_argument("--volume-report", default=None)
    r.add_argument("--volume", default=None, help="shipped NIfTI, for the numeric depth-order check")
    r.add_argument("--labels", default=None, help="label map json of that volume")
    r.add_argument("--montage-path", default=None)
    r.add_argument("--limits", nargs="*", default=[])
    r.add_argument("--out", required=True)
    a = ap.parse_args()
    {"track": do_track, "clean": do_clean, "report": do_report}[a.mode](a)


if __name__ == "__main__":
    main()
