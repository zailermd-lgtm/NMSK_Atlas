"""Q179: her photo-tracked thigh / knee structures (Q53 sciatic nerve, Q55 femoral artery / vein / nerve trunk, Q56 popliteal
artery / vein + tibial nerve) brought to the standard reached on the male in Q173-Q178.

    # crops (per side, her photographs; her 1 mm frame is lost, so the level comes from the Q154 cryo-z calibration + the
    # z offset measured here on her femur, and the in-plane shift is registered per level below; delete after use):
    python3 scripts/cryo/vhm_stream_leg_crops.py --body vhf --index SCRATCH/vh_cryo_f_idx/cryo_index.json --y-top 40 --y-bot -420 \
        --box right=0,200,-140,80 --ap-row -1 --rs-cs=-2,-108 --margin 20 --z-offset="0:-20,-375:-14" --out SCRATCH/q179/crops/R
    python3 scripts/cryo/vhm_stream_leg_crops.py --body vhf ... --box left=-200,0,-140,80 --z-offset="0:-18.5,-375:-17" --out SCRATCH/q179/crops/L
    python3 scripts/cryo/vhf_tracked_q179.py register --crops SCRATCH/q179/crops      # femur registration -> RS/CS_by_side in the bbox json
    python3 scripts/cryo/vhf_tracked_q179.py offsets --crops SCRATCH/q179/crops       # the lost frame reconstructed -> vhf_tracked_reg_q179.json
    python3 scripts/cryo/vhf_tracked_q179.py regvol                                   # outlines translated -> *_reg_q179.nii.gz
    python3 scripts/cryo/vhf_tracked_q179.py photos --crops SCRATCH/q179/crops        # Q178 per-slice statistics -> unusable levels
    python3 scripts/cryo/vhf_tracked_q179.py clip --crops SCRATCH/q179/crops          # Q176 clip, her rule -> *_reg_clip_q179.nii.gz
    python3 scripts/cryo/vhf_tracked_q179.py interp --crops SCRATCH/q179/crops        # Q178 interpolation -> *_q179.nii.gz
    python3 scripts/cryo/vhf_tracked_q179.py audit --crops SCRATCH/q179/crops         # no changes: overlap, photo share, shift, slices

STATUS (2026-09-30): STOPPED after the audit, nothing wired or shipped. The *_q179 volumes are CANDIDATES: her Q48 thigh
muscles carry the same lost-frame error as the outlines, so registering only the outlines leaves 8-13 mm of muscle mesh over
them and a bounded Q177 face snap does not absorb it (data/derived/Q179_vhf_tracked_audit.json "decision").

REGISTRATION (her femur, Q173 method adapted): her CT femur (+ patella, + hip bone above y -30) sectioned per 1 mm level,
contour sampled every 0.5 mm; photograph edge map = colour Sobel magnitude on the 1 mm-binned crop, locally normalised
(/ 15 mm box mean); score = mean edge strength on the shifted contour; exhaustive search +-20 mm at 1 mm, then +-1 mm at
the full 0.33 mm; peak kept when it beats the best shift >= 4 mm away by >= 8 % and lies within 3 mm of the running median (31 levels)
of the kept levels (else the level is interpolated); the per-level shift is then smoothed (running median 21 levels, then running mean 9) because the femur is rigid and the leg's
pose changes slowly. Translation only (a rotation search at the knee and hip gave 0 to -2 deg, <= 1.7 mm at 50 mm, noisy).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import trimesh
from scipy import ndimage as ndi

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
import nibabel as nib  # noqa: E402
from scripts.cryo.vhf_nerve_track import Crops, nerve_blobs  # noqa: E402

T = REPO / "data/ct_sources/task_outputs"
REPORT = REPO / "data/derived/Q179_vhf_tracked_audit.json"
ORIGIN = np.array([7.769, -885.229, 14.137])
SIDES = {"right": ("R", "_r"), "left": ("L", "_l")}
SOURCE = ("U.S. National Library of Medicine, The Visible Human Project (public domain): her colour cryosections at full resolution "
          "(0.33 mm, NCI Imaging Data Commons) re-streamed by scripts/cryo/vhm_stream_leg_crops.py --body vhf; her CT femur / patella / "
          "hip bone (VH female CT, TotalSegmentator labels); her tracked outlines from Q53 (vhf_nerves_cryo.nii.gz), Q55 "
          "(vhf_femoral_bundle_cryo.nii.gz) and Q56 (vhf_popliteal_cryo.nii.gz); her thigh muscles = the male's (DU lower-extremity "
          "release, Andreassen TE et al., Sci Data 10:34 (2023), CC BY 4.0) transferred onto her and refined to her septa (Q48). Derived "
          "data (scripts/cryo/vhf_tracked_q179.py).")
REG_R_MM = 20
REG_JSON = T / "vhf_tracked_reg_q179.json"
# her tracked label volumes (0.5 x 0.5 x 1 mm, +x +y RAS grid of vhf_nerve_volume.py): label -> (atlas id, side, kind)
VOLS = {
    "sciatic": {"src": T / "vhf_nerves_cryo.nii.gz", "subject": "ct_vhf_nerve", "labels": {1: ("sciatic_n", None, "nerve")}},
    "femoral": {"src": T / "vhf_femoral_bundle_cryo.nii.gz", "subject": "ct_vhf_femoral",
                "labels": {1: ("femoral_a_r", "right", "artery"), 2: ("femoral_n", "right", "nerve"), 3: ("femoral_v_r", "right", "vein")}},
    "popliteal": {"src": T / "vhf_popliteal_cryo.nii.gz", "subject": "ct_vhf_popliteal",
                  "labels": {1: ("popliteal_a_r", "right", "artery"), 2: ("popliteal_v_r", "right", "vein"), 3: ("tibial_n", "right", "nerve")}},
}
OFF_R_PX = 60                                    # +-20 mm search of the traced outline against its photographed feature
OFF_WINDOW = 10                                  # levels pooled either side (the lost frame's shift changes slowly)
OFF_WEIGHT = {"nerve": 1.0, "artery": 1.0, "vein": 1.0}
OFF_MIN_SCORE = 0.35                             # pooled mean IoU below this: level interpolated
LUMEN_MAX_VALUE = 40.0                           # her clot: value median 42, 25th pct 34; her muscle 1st pct 45 (a 60 cut takes a quarter of her muscle)
REG_PEAK_RATIO = 1.08
REG_OUTLIER_MM = 3.0


def bundle_meshes(bdir):
    from scripts.transfer.bundle_io import read_bundle_dir, meshes_by_id
    bf, blob = read_bundle_dir(str(bdir)); return meshes_by_id(bf, blob)


def contour_points(tms, y, step=0.5):
    P = []
    for tm in tms:
        if tm.bounds[0, 1] > y or tm.bounds[1, 1] < y:
            continue
        s = tm.section(plane_origin=[0, y, 0], plane_normal=[0, 1, 0])
        if s is None:
            continue
        for e in s.entities:
            p = s.vertices[e.points]; L = np.r_[0, np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))]
            t = np.arange(0, L[-1], step); P.append(np.c_[np.interp(t, L, p[:, 0]), np.interp(t, L, p[:, 2])])
    return np.concatenate(P) if P else None


def edge_map(im, binning):
    im = im.astype(np.float32); h, w = (im.shape[0] // binning) * binning, (im.shape[1] // binning) * binning
    d = im[:h, :w].reshape(h // binning, binning, w // binning, binning, 3).mean((1, 3))
    d = ndi.gaussian_filter(d, (3.0 / binning, 3.0 / binning, 0))
    G = np.sqrt(sum(ndi.sobel(d[..., k], 0) ** 2 + ndi.sobel(d[..., k], 1) ** 2 for k in range(3)))
    return G / (ndi.uniform_filter(G, max(3, int(45 / binning))) + 1e-3)


def contour_score(G, pr, pc, shifts):
    out = np.full(len(shifts), -1.0)
    for i, (dr, dc) in enumerate(shifts):
        rr = np.rint(pr + dr).astype(int); cc = np.rint(pc + dc).astype(int)
        ok = (rr >= 0) & (cc >= 0) & (rr < G.shape[0]) & (cc < G.shape[1])
        if ok.mean() >= 0.9:
            out[i] = G[rr[ok], cc[ok]].mean()
    return out


def running(x, ok, med=21, mean=9):
    """robust smooth of a per-level series: interpolate rejected levels, running median, running mean."""
    i = np.arange(len(x)); xs = np.interp(i, i[ok], x[ok])
    xs = ndi.median_filter(xs, size=med, mode="nearest"); return ndi.uniform_filter1d(xs, size=mean, mode="nearest")


def side_mask(A, shape, side):
    ax = A[0, 3] + A[0, 0] * np.arange(shape[0]) - ORIGIN[0]
    return (ax > 0) if side == "right" else (ax < 0)


def level_k(A, y):
    return int(round(y + ORIGIN[1] - A[2, 3]))


def vox_atlas(A, i, j, k):
    return A[0, 3] + A[0, 0] * i - ORIGIN[0], A[1, 3] + A[1, 1] * j - ORIGIN[2], int(round(A[2, 3] + A[2, 2] * k - ORIGIN[1]))


def iter_sections(key, sides=("right", "left")):
    """(label, atlas id, side, kind, L, A) for every tracked label/side present in a volume."""
    cfg = VOLS[key]; img = nib.load(str(cfg["src"])); L = np.asarray(img.dataobj); A = img.affine
    for lab, (aid, side, kind) in cfg["labels"].items():
        for sd in ([side] if side else list(sides)):
            if ((L == lab) & side_mask(A, L.shape, sd)[:, None, None]).any():
                yield lab, aid, sd, kind, L, A


def lumen_mask(im):
    """her vessel lumina (Q55/Q56 detector, vhf_femoral_track.vessel_lumina: near-black cores grown to the wall), kept when
    lumen-like: 3-250 mm2, solidity >= 0.7, aspect <= 2.6, a black centre (20th pct red < 45) and a pale wall (0.7-2 mm ring
    red >= 25 above the lumen) -- her darkest muscle patches bottom out at red 43-49 and have no pale ring."""
    from scripts.cryo.vhf_femoral_track import vessel_lumina, blob_stats
    lab = vessel_lumina(im); R = im[..., 0].astype(np.float32); out = np.zeros(im.shape[:2], bool)
    for i, sl in enumerate(ndi.find_objects(lab), start=1):
        if sl is None:
            continue
        pad = 8; sl2 = tuple(slice(max(q.start - pad, 0), q.stop + pad) for q in sl); mm = lab[sl2] == i
        if not mm.any():
            continue
        st = blob_stats(mm)
        if not (3.0 <= st["area_mm2"] <= 250.0) or st["solidity"] < 0.7 or st["aspect"] > 2.6:
            continue
        ring = ndi.binary_dilation(mm, iterations=6) & ~ndi.binary_dilation(mm, iterations=2); Rw = R[sl2]
        if np.percentile(Rw[mm], 20) >= 45.0 or (ring.any() and Rw[ring].mean() - Rw[mm].mean() < 25.0):
            continue
        out[sl2] |= mm
    return out


def feature_map(win, kind):
    """what a traced outline was traced ON: her Q53 fascicle-texture blobs (nerves), her Q55/Q56 lumina (vessels)."""
    if kind == "nerve":
        lb, _ = nerve_blobs(win); return (lb > 0).astype(np.float32)
    return lumen_mask(win).astype(np.float32)


def offset_maps(crops, key, lab, side, kind, L, A, skip=()):
    """per level: IoU of the traced section (as placed) shifted by (dr, dc) crop px against its photographed feature."""
    from scipy.signal import fftconvolve
    c = Crops(str(Path(crops) / SIDES[side][0]), side); R = OFF_R_PX; xm = side_mask(A, L.shape, side); maps = {}
    sub = np.array([(u, v) for u in (-1 / 3, 0, 1 / 3) for v in (-1 / 3, 0, 1 / 3)])
    for k in range(L.shape[2]):
        m = (L[:, :, k] == lab) & xm[:, None]
        if not m.any():
            continue
        y = int(round(A[2, 3] + k - ORIGIN[1]))
        if y not in c.j_of or y in skip:
            continue
        ii, jj = np.nonzero(m)
        X = A[0, 3] + A[0, 0] * (ii[:, None] + sub[None, :, 0]) - ORIGIN[0]; Z = A[1, 3] + A[1, 1] * (jj[:, None] + sub[None, :, 1]) - ORIGIN[2]
        pr, pc = c.atlas_to_px(y, X.ravel(), Z.ravel()); pr = np.rint(pr).astype(int); pc = np.rint(pc).astype(int)
        im = c.image(y); r0, r1, c0, c1 = pr.min() - R - 5, pr.max() + R + 6, pc.min() - R - 5, pc.max() + R + 6
        if r0 < 0 or c0 < 0 or r1 > im.shape[0] or c1 > im.shape[1]:
            continue
        F = feature_map(im[r0:r1, c0:c1], kind)
        Tm = np.zeros((pr.max() - pr.min() + 1, pc.max() - pc.min() + 1), np.float32); Tm[pr - pr.min(), pc - pc.min()] = 1
        Tm = ndi.binary_closing(Tm, iterations=1).astype(np.float32)
        cor = fftconvolve(F, Tm[::-1, ::-1], mode="valid"); Fs = fftconvolve(F, np.ones_like(Tm), mode="valid")
        iou = cor / (Tm.sum() + Fs - cor + 1e-6)          # [i, j]: template top-left at (i, j); zero shift at (R + 5, R + 5)
        maps[y] = iou[5:5 + 2 * R + 1, 5:5 + 2 * R + 1].astype(np.float32)
    return maps


def do_offsets(a):
    """the LOST frame the outlines were traced in, reconstructed: per level one in-plane shift for the whole photograph (her
    old frame had one anchor shift per level), found where the traced outlines of BOTH legs sit best on their photographed
    features after each side's femur registration is taken out; -> per-side, per-level atlas translation."""
    reg = json.loads(Path(a.crops, "registration.json").read_text())
    fem = {s: {r["y"]: (r["dr_smooth_px"], r["dc_smooth_px"]) for r in reg[s]["per_level"]} for s in reg}
    R = OFF_R_PX; G = 2 * R; per = {}; raw = {}; gmaps = {}
    sp = Path(a.crops, "photo_stats.json"); skip = unusable(a.crops) if sp.exists() else {}
    for key in VOLS:
        for lab, aid, sd, kind, L, A in iter_sections(key):
            maps = offset_maps(a.crops, key, lab, sd, kind, L, A, skip.get(sd, ())); wts = OFF_WEIGHT[kind]; rows = []
            for y, m in maps.items():
                gmaps.setdefault(key, {}).setdefault(y, []).append(m * wts)
            for y, m in maps.items():
                fr, fc = fem[sd][y]; oi, oj = int(round(fr)), int(round(fc))
                big = np.zeros((2 * G + 1, 2 * G + 1), np.float32); big[G + oi - R:G + oi + R + 1, G + oj - R:G + oj + R + 1] = m * wts
                per.setdefault(y, []).append(big)
                i, j = np.unravel_index(m.argmax(), m.shape); rows.append([y, round((i - R) / 3, 2), round((j - R) / 3, 2), round(float(m.max()), 3), round(float(m[R, R]), 3)])
            raw[f"{aid}:{sd}"] = rows; print(aid, sd, len(rows), "levels", flush=True)
    ys = np.array(sorted(per)); Tr = []; Tc = []; sc_ = []
    # the short vessel groups (Q55 femoral, Q56 popliteal; right leg only, 60-80 mm long): ONE translation each, from their OWN
    # outlines against their photographed lumina / fascicles pooled over all their levels in the femur-registered frame (their
    # femur registration is the least certain -- hip and knee-metaphysis levels are mostly interpolated -- and a per-level
    # window at a group's ends holds too few outlines: attempt 1 gave 5-16 mm jumps at the last levels)
    groups = {}
    for key in ("femoral", "popliteal"):
        blk = [m for y in gmaps[key] for m in gmaps[key][y]]; tot = sum(blk) / len(blk)
        i, j = np.unravel_index(tot.argmax(), tot.shape)
        per_level = {}
        for y in gmaps[key]:
            t_ = sum(gmaps[key][y]) / len(gmaps[key][y]); u, v = np.unravel_index(t_.argmax(), t_.shape); per_level[y] = ((u - R) / 3, (v - R) / 3, float(t_.max()))
        groups[key] = {"r": (i - R) / 3, "c": (j - R) / 3, "score": float(tot.max()), "score_zero": float(tot[R, R]), "levels": sorted(gmaps[key]),
                       "per_level": per_level}
    for y in ys:
        blk = [b for yy in ys if abs(yy - y) <= OFF_WINDOW for b in per[yy]]; tot = sum(blk) / len(blk)
        i, j = np.unravel_index(tot.argmax(), tot.shape); Tr.append((i - G) / 3); Tc.append((j - G) / 3); sc_.append(float(tot.max()))
    Tr = np.array(Tr); Tc = np.array(Tc)
    ok = np.array(sc_) >= OFF_MIN_SCORE                  # weak pooled peaks (a lone, poorly matching outline) are interpolated
    Sr = running(Tr, ok, med=21, mean=9); Sc = running(Tc, ok, med=21, mean=9)
    b = json.loads(Path(a.crops, "R_bbox.json").read_text()); sc = b["sc"]
    out = {"source": SOURCE, "_README": "Q179: per level (atlas y) and side, the translation (atlas mm, dx, dz) that moves her tracked outlines "
           "(traced in her lost 1 mm frame) onto their photographed features in the femur-registered photographs; apply with "
           "vhf_tracked_q179.py regvol. old_frame_crop_mm = the lost frame's shift reconstructed (crop mm, rows/cols) from both legs; "
           "femur_crop_mm = each side's femur registration (crop mm); offset = old - femur.", "sc": sc,
           "levels_with_features": [int(ys[0]), int(ys[-1])], "sides": {}}
    for side in ("right", "left"):
        rows = {}
        fy = np.array(sorted(fem[side])); fr = np.array([fem[side][y][0] for y in fy]) / 3; fc = np.array([fem[side][y][1] for y in fy]) / 3
        for y in range(int(ys.max()) + 20, int(ys.min()) - 21, -1):
            tr = float(np.interp(y, ys, Sr)); tc = float(np.interp(y, ys, Sc)); f_r = float(np.interp(y, fy, fr)); f_c = float(np.interp(y, fy, fc))
            orr, occ = tr - f_r, tc - f_c
            rows[str(y)] = {"old_frame_crop_mm": [round(tr, 3), round(tc, 3)], "femur_crop_mm": [round(f_r, 3), round(f_c, 3)],
                            "offset_crop_mm": [round(orr, 3), round(occ, 3)], "atlas_dx_dz_mm": [round(-occ * sc, 3), round(orr * sc, 3)]}
        out["sides"][side] = rows
    out["groups"] = {}
    for key, g in groups.items():
        orr, occ = g["r"], g["c"]; dxdz = [round(-occ * sc, 3), round(orr * sc, 3)]
        out["groups"][key] = {"side": "right", "levels_with_outlines": [max(g["levels"]), min(g["levels"])], "offset_crop_mm": [round(orr, 3), round(occ, 3)],
                              "atlas_dx_dz_mm": dxdz, "pooled_iou": round(g["score"], 3), "pooled_iou_at_zero": round(g["score_zero"], 3),
                              "per_level_peak_crop_mm": {str(y): [round(v[0], 2), round(v[1], 2), round(v[2], 3)] for y, v in g["per_level"].items()},
                              "rows": {str(y): {"atlas_dx_dz_mm": dxdz} for y in range(max(g["levels"]) + 20, min(g["levels"]) - 21, -1)}}
        print(key, "offset crop mm", out["groups"][key]["offset_crop_mm"], "atlas dx,dz", dxdz, "IoU", round(g["score"], 3), "at zero", round(g["score_zero"], 3))
    out["pooled_peak"] = {str(int(y)): [round(float(r), 2), round(float(c_), 2), round(s_, 3), bool(o)] for y, r, c_, s_, o in zip(ys, Tr, Tc, sc_, ok)}
    out["per_structure_single_level_peaks"] = raw
    REG_JSON.write_text(json.dumps(out))
    for y in range(int(ys.max()), int(ys.min()) - 1, -25):
        print(y, "old", out["sides"]["right"][str(y)]["old_frame_crop_mm"], "R dx,dz", out["sides"]["right"][str(y)]["atlas_dx_dz_mm"],
              "L dx,dz", out["sides"]["left"][str(y)]["atlas_dx_dz_mm"])


# ------------------------------------------------------------------------------------------------ registered volumes
PAD_MM = 20.0


def reg_table(key="sciatic"):
    """sciatic: the lost frame reconstructed from both legs minus each side's femur registration (per level); femoral / popliteal
    (right leg only): the group's own outlines against their photographed lumina / fascicles (per level, pooled +-10)."""
    d = json.loads(REG_JSON.read_text()); tab = {s: {int(y): v["atlas_dx_dz_mm"] for y, v in rows.items()} for s, rows in d["sides"].items()}
    if key in d.get("groups", {}):
        tab["right"] = {int(y): v["atlas_dx_dz_mm"] for y, v in d["groups"][key]["rows"].items()}
    return tab


def shift_volume(L, A, table):
    """per level and side, translate the side's voxels by the tabled (dx, dz) atlas mm, rounded to whole 0.5 mm voxels; the grid
    is padded by PAD_MM in x and z (atlas) so nothing is cut. -> (L2, A2, applied {side: {y: [dx, dz]}})"""
    vx, vz = A[0, 0], A[1, 1]; px, pz = int(round(PAD_MM / vx)), int(round(PAD_MM / vz))
    L2 = np.zeros((L.shape[0] + 2 * px, L.shape[1] + 2 * pz, L.shape[2]), L.dtype); A2 = A.copy(); A2[0, 3] -= px * vx; A2[1, 3] -= pz * vz
    applied = {}
    for side in ("right", "left"):
        xm = side_mask(A, L.shape, side)
        for k in range(L.shape[2]):
            sl = L[:, :, k] * xm[:, None]
            if not sl.any():
                continue
            y = int(round(A[2, 3] + k - ORIGIN[1])); dx, dz = table[side][max(min(y, max(table[side])), min(table[side]))]
            di, dj = int(round(dx / vx)), int(round(dz / vz))
            ii, jj = np.nonzero(sl); L2[ii + px + di, jj + pz + dj, k] = sl[ii, jj]
            applied.setdefault(side, {})[y] = [round(di * vx, 2), round(dj * vz, 2)]
    return L2, A2, applied


def reg_path(key):
    return T / (VOLS[key]["src"].name.replace(".nii.gz", "_reg_q179.nii.gz"))


def do_regvol(a):
    out = {}
    for key, cfg in VOLS.items():
        img = nib.load(str(cfg["src"])); L = np.asarray(img.dataobj); L2, A2, applied = shift_volume(L, img.affine, reg_table(key))
        for lab in np.unique(L[L > 0]):
            assert (L == lab).sum() == (L2 == lab).sum(), (key, lab)
        nib.save(nib.Nifti1Image(L2, A2), str(reg_path(key))); out[key] = applied
        mags = [np.hypot(*v) for sd in applied.values() for v in sd.values()]
        print(key, "->", reg_path(key).name, "shift mm median", round(float(np.median(mags)), 2), "max", round(float(np.max(mags)), 2))
    return out


# ------------------------------------------------------------------------------------------------ her photographed muscle
MIN_RED = 50.0            # calibrated on her photographs (Q179 audit): her clot / lumen red median 41, muscle red 1st pct 45, 5th 50
MAX_VALUE = 100.0         # her muscle value 99th pct 94; her nerve (pale fascicles) value 25th pct 119, median 140


def muscle_f(im, lumen=True):
    """her photographed MUSCLE (Q179 calibration): tissue (red > blue + 8), value < 100, red >= 50, and not inside one of her
    photographed vessel lumina (lumen_mask: ~30 % of her clotted lumen is red >= 50, so colour alone calls it muscle). Her
    muscle is darker and more orange than his (green/red up to 0.77): his g < 0.62 r would drop ~half of it; value separates it
    from her nerve."""
    f = im.astype(np.float32); r, b = f[..., 0], f[..., 2]; v = f.max(-1)
    m = (r > b + 8) & (v < MAX_VALUE) & (r >= MIN_RED)
    return m & ~lumen_mask(im) if lumen else m


_PHOTO_CACHE = {}


class HerMusclePhoto:
    """as vhm_tracked_clip.MusclePhoto: 3 x 3 (1 mm) majority-smoothed muscle mask; 2 x 2 sub-samples per atlas point."""
    def __init__(self, crops, side, skip=()):
        self.c = Crops(str(Path(crops) / SIDES[side][0]), side); self.cache = {}; self.skip = set(skip)

    def mask(self, y):
        y = int(y)
        if y not in self.c.j_of or y in self.skip:
            return None
        key = (str(self.c.a.filename), y)
        if key not in _PHOTO_CACHE:
            if len(_PHOTO_CACHE) > 600:
                _PHOTO_CACHE.pop(next(iter(_PHOTO_CACHE)))
            im = self.c.image(y); lum = lumen_mask(im)
            _PHOTO_CACHE[key] = (ndi.uniform_filter((muscle_f(im, lumen=False) & ~lum).astype(np.float32), 3) >= 0.5, lum)
        self.cache[y] = _PHOTO_CACHE[key]
        return self.cache[y][0]

    def lumen(self, y):
        return None if self.mask(y) is None else self.cache[int(y)][1]

    def sample_lumen(self, y, ax, az):
        k = self.lumen(y)
        if k is None:
            return np.full(len(ax), -1.0)
        pr, pc = self.c.atlas_to_px(y, ax, az); pr = np.rint(pr).astype(int); pc = np.rint(pc).astype(int)
        ok = (pr >= 0) & (pc >= 0) & (pr < k.shape[0]) & (pc < k.shape[1]); out = np.full(len(ax), -1.0); out[ok] = k[pr[ok], pc[ok]]
        return out

    def sample(self, y, ax, az):
        k = self.mask(y)
        if k is None:
            return np.full(len(ax), -1.0)
        acc = np.zeros(len(ax)); bad = np.zeros(len(ax), bool)
        for dx in (-0.125, 0.125):
            for dz in (-0.125, 0.125):
                pr, pc = self.c.atlas_to_px(y, ax + dx, az + dz); pr = np.rint(pr).astype(int); pc = np.rint(pc).astype(int)
                ok = (pr >= 0) & (pc >= 0) & (pr < k.shape[0]) & (pc < k.shape[1]); bad |= ~ok
                acc[ok] += k[pr[ok], pc[ok]]
        out = acc / 4.0; out[bad] = -1.0
        return out


def photo_share(crops, L, A, lab, side, skip=()):
    """share of the section area on photographed muscle (her rule), and deeper than 1 mm inside the section, per level."""
    ph = HerMusclePhoto(crops, side, skip); xm = side_mask(A, L.shape, side); rows = []
    for k in range(L.shape[2]):
        M = (L[:, :, k] == lab) & xm[:, None]
        if not M.any():
            continue
        ii, jj = np.nonzero(M); ax, az, y = vox_atlas(A, ii, jj, k); fr = ph.sample(y, ax, az)
        if (fr < 0).all():
            continue
        d = ndi.distance_transform_edt(np.pad(M, 1))[1:-1, 1:-1][ii, jj] * abs(A[0, 0]); ok = fr >= 0
        lu = ph.sample_lumen(y, ax, az)
        rows.append({"y": y, "area_mm2": float(M.sum() * abs(A[0, 0] * A[1, 1])), "muscle": float((fr[ok] >= 0.5).mean()),
                     "muscle_deeper_1mm": float(((fr >= 0.5) & (d > 1.0))[ok].mean()), "lumen": float((lu[ok] > 0.5).mean())})
    return rows


def share_summary(rows):
    if not rows:
        return None
    w = np.array([r["area_mm2"] for r in rows])
    return {"levels": len(rows), "on_photographed_muscle": round(float(np.average([r["muscle"] for r in rows], weights=w)), 4),
            "deeper_than_1mm": round(float(np.average([r["muscle_deeper_1mm"] for r in rows], weights=w)), 4),
            "on_photographed_lumen": round(float(np.average([r["lumen"] for r in rows], weights=w)), 4)}


# ------------------------------------------------------------------------------------------------ unusable photographs
DV, DGR, MUS_RATIO = 0.10, 0.04, 0.85            # Q178's thresholds
REF_HALF = 15                                    # reference = median of the levels within 15 mm, the +-2 nearest excluded


def photo_stats(crops):
    """per side, per level (Q178 statistics): mean value, G/R, B/R and her photographed-muscle fraction over the crop's
    photographed pixels, against the running median of the usable levels within 15 mm (the +-2 nearest excluded); FLAGGED if
    |V/ref - 1| > 0.10 or |G/R - ref| > 0.04 or muscle fraction < 0.85 x ref (Q178's thresholds). Her series has isolated
    marginal flags (a single criterion just over, e.g. G/R +0.05 at the knee where the crop is ~2 % muscle) on photographs that
    look normal, so UNUSABLE = a blank photograph, or a level over TWICE a threshold (|V| > 0.20, |G/R| > 0.08, muscle < 0.70 x),
    plus flagged levels contiguous with one."""
    out = {}
    for side in ("right", "left"):
        c = Crops(str(Path(crops) / SIDES[side][0]), side); st = {}
        for y in c.ys:
            im = c.image(y); ok = im.astype(np.int32).sum(-1) > 0
            if ok.mean() < 0.05:
                st[y] = None; continue
            px = im[ok].astype(np.float64)
            st[y] = {"V": float(px.max(-1).mean()), "G_R": float(px[:, 1].sum() / px[:, 0].sum()), "B_R": float(px[:, 2].sum() / px[:, 0].sum()),
                     "muscle_frac": float(muscle_f(im, lumen=False)[ok].mean())}
        ys = sorted(st); lv = {}
        for y in ys:
            if st[y] is None:
                lv[y] = {"blank_photograph": True, "flagged": True, "strong": True}; continue
            ref = [yy for yy in ys if 2 < abs(yy - y) <= REF_HALF and st[yy] is not None]
            r = {k: float(np.median([st[yy][k] for yy in ref])) for k in ("V", "G_R", "muscle_frac")}
            s_ = st[y]; dv = s_["V"] / r["V"] - 1; dg = s_["G_R"] - r["G_R"]; mr = s_["muscle_frac"] / max(r["muscle_frac"], 1e-6)
            lv[y] = {**{k: round(v, 4) for k, v in s_.items()}, "V_rel": round(dv, 4), "G_R_diff": round(dg, 4), "muscle_ratio": round(mr, 4),
                     "flagged": bool(abs(dv) > DV or abs(dg) > DGR or mr < MUS_RATIO),
                     "strong": bool(abs(dv) > 2 * DV or abs(dg) > 2 * DGR or mr < 1 - 2 * (1 - MUS_RATIO))}
        bad = set(y for y in ys if lv[y]["strong"]); grow = True
        while grow:
            new = {y + d for y in bad for d in (-1, 1) if (y + d) in lv and lv[y + d]["flagged"]} - bad; grow = bool(new); bad |= new
        for y in ys:
            lv[y]["unusable"] = y in bad
        out[side] = {"levels": {str(y): v for y, v in lv.items()}, "unusable": sorted(bad, reverse=True),
                     "flagged_only": [y for y in ys if lv[y]["flagged"] and y not in bad]}
        print(side, "unusable levels:", out[side]["unusable"], "| flagged, kept (marginal):", out[side]["flagged_only"])
    return out


# ------------------------------------------------------------------------------------------------ Q176 clip + Q178 interpolation
CLIP_KINDS = ("nerve", "vein")                   # arteries not clipped (Q176: the wall is smooth muscle)
VOX = 0.5


def clip_path(key):
    return T / VOLS[key]["src"].name.replace(".nii.gz", "_reg_clip_q179.nii.gz")


def final_path(key):
    return T / VOLS[key]["src"].name.replace(".nii.gz", "_q179.nii.gz")


def unusable(crops):
    ph = json.loads(Path(crops, "photo_stats.json").read_text()); return {s: set(ph[s]["unusable"]) for s in ph}


def sec_stats(L0, L1, A, lab, side):
    xm = side_mask(A, L0.shape, side)[:, None, None]; m0 = (L0 == lab) & xm; m1 = (L1 == lab) & xm
    a0 = m0.sum((0, 1)) * VOX * VOX; a1 = m1.sum((0, 1)) * VOX * VOX; k = a0 > 0
    d0 = 2 * np.sqrt(a0[k] / np.pi); d1 = 2 * np.sqrt(a1[k] / np.pi)
    return {"volume_cm3": [round(float(m0.sum() * VOX * VOX / 1000), 3), round(float(m1.sum() * VOX * VOX / 1000), 3)],
            "volume_change_pct": round(100 * (m1.sum() - m0.sum()) / max(m0.sum(), 1), 1),
            "diameter_area_equivalent_median_mm": [round(float(np.median(d0)), 2), round(float(np.median(d1)), 2)],
            "components_3d_26conn": [int(ndi.label(m0, np.ones((3, 3, 3)))[1]), int(ndi.label(m1, np.ones((3, 3, 3)))[1])]}


def do_clip(a):
    from scripts.cryo.vhm_tracked_clip import clip_section
    skip = unusable(a.crops); rep = json.loads(REPORT.read_text()); out = {}
    for key, cfg in VOLS.items():
        img = nib.load(str(reg_path(key))); L0 = np.asarray(img.dataobj); A = img.affine; L1 = L0.copy()
        for lab, (aid, side, kind) in cfg["labels"].items():
            for sd in ([side] if side else ["right", "left"]):
                xm = side_mask(A, L0.shape, sd)
                if kind not in CLIP_KINDS or not ((L0 == lab) & xm[:, None, None]).any():
                    continue
                ph = HerMusclePhoto(a.crops, sd, skip[sd]); st = []; m0s = []; m1s = []
                for k in range(L0.shape[2]):
                    M = (L0[:, :, k] == lab) & xm[:, None]
                    if not M.any():
                        continue
                    ii, jj = np.nonzero(M); ax, az, y = vox_atlas(A, ii, jj, k)
                    fr = np.full(M.shape, -1.0); fr[ii, jj] = ph.sample(y, ax, az)
                    new, nrem, status = clip_section(M, fr); L1[:, :, k][M & ~new] = 0; st.append(status)
                    ok = fr[ii, jj] >= 0
                    if ok.any():
                        m0s.append((M.sum(), (fr[ii, jj][ok] >= 0.5).mean())); m1s.append((new.sum(), (fr[new] >= 0.5).mean() if new.any() else 0.0))
                w0 = np.array([u for u, _ in m0s]); w1 = np.array([u for u, _ in m1s])
                row = dict(sec_stats(L0, L1, A, lab, sd), atlas_id=aid, side=sd, levels=len(st), clipped=st.count("clipped"),
                           unchanged=st.count("unchanged"), kept_split=st.count("kept_split"),
                           on_photographed_muscle=[round(float(np.average([v for _, v in m0s], weights=w0)), 4),
                                                   round(float(np.average([v for _, v in m1s], weights=np.maximum(w1, 1e-9))), 4)])
                out[f"{aid}:{sd}"] = row; print(row, flush=True)
        nib.save(nib.Nifti1Image(L1, A), str(clip_path(key)))
    rep["clip"] = {"rule": "vhm_tracked_clip.clip_section (Q176: 2 mm bounded peel of photographed-muscle voxels connected to the edge, "
                   "core kept, rim specks <= 1 mm2 with it, a level that would split keeps its original) with HER muscle rule "
                   "(muscle_f: value < 100, red >= 50, not a photographed lumen; 3 x 3 majority; 2 x 2 sub-samples); unusable levels unknown",
                   "structures": out}
    REPORT.write_text(json.dumps(rep, indent=1))


def interp_spans(skip_side, lo, hi):
    """contiguous unusable runs within [hi, lo] (atlas y, descending)."""
    ys = sorted((y for y in skip_side if hi >= y >= lo), reverse=True); spans = []
    for y in ys:
        if spans and spans[-1][1] == y + 1:
            spans[-1][1] = y
        else:
            spans.append([y, y])
    return spans


def do_interp(a):
    from scripts.cryo.vhm_dark_slice_interp import interp_section
    skip = unusable(a.crops); rep = json.loads(REPORT.read_text()); out = {}
    for key, cfg in VOLS.items():
        img = nib.load(str(clip_path(key))); L0 = np.asarray(img.dataobj); A = img.affine; L1 = L0.copy()
        for lab, (aid, side, kind) in cfg["labels"].items():
            for sd in ([side] if side else ["right", "left"]):
                xm = side_mask(A, L0.shape, sd)[:, None]; sec = lambda L, y: (L[:, :, level_k(A, y)] == lab) & xm
                ks = [k for k in range(L0.shape[2]) if ((L0[:, :, k] == lab) & xm).any()]
                if not ks:
                    continue
                y_hi = int(round(A[2, 3] + ks[0] - ORIGIN[1])); y_lo = int(round(A[2, 3] + ks[-1] - ORIGIN[1]))
                y_hi, y_lo = max(y_hi, y_lo), min(y_hi, y_lo)
                for y_top, y_bot in interp_spans(skip[sd], y_lo, y_hi):
                    ya, yb = y_top + 1, y_bot - 1; row = {"atlas_id": aid, "side": sd, "span": [y_top, y_bot], "bounds": [ya, yb]}
                    if not (y_lo <= yb and ya <= y_hi) or not (sec(L0, ya).any() and sec(L0, yb).any()):
                        row.update(status="kept_as_traced", why="no section at a bound level (the outline starts/ends in the span)")
                    else:
                        Ma, Mb = sec(L0, ya), sec(L0, yb); before = {}; after = {}
                        for y in range(y_top, y_bot - 1, -1):
                            t = (ya - y) / (ya - yb); M, n = interp_section(Ma, Mb, t); sl = L1[:, :, level_k(A, y)]
                            before[str(y)] = float(sec(L0, y).sum() * VOX * VOX); sl[(sl == lab) & xm] = 0
                            free = (sl == 0); sl[M & free & xm] = lab; after[str(y)] = float((M & free & xm).sum() * VOX * VOX)
                        row.update(status="interpolated", bound_area_mm2=[float(Ma.sum() * VOX * VOX), float(Mb.sum() * VOX * VOX)],
                                   area_mm2_before=before, area_mm2_after=after)
                    out[f"{aid}:{sd}:{y_top}"] = row; print(row, flush=True)
        nib.save(nib.Nifti1Image(L1, A), str(final_path(key)))
    rep["interpolation"] = {"rule": "Q178: centroid-aligned signed-distance blend between the usable levels bounding each unusable run "
                            "(vhm_dark_slice_interp.interp_section), largest piece kept, only that label/side at the span levels changes",
                            "unusable_levels": {s: sorted(v, reverse=True) for s, v in skip.items()}, "structures": out}
    REPORT.write_text(json.dumps(rep, indent=1))


# ------------------------------------------------------------------------------------------------ audit
MUSCLE_WORDS = ("adductor", "biceps_femoris", "semitendinosus", "semimembranosus", "gracilis", "sartorius", "vastus", "rectus_femoris",
                "gluteus", "tensor_fasciae", "pectineus", "iliopsoas", "psoas", "iliacus", "gastrocnemius", "soleus", "plantaris",
                "popliteus", "quadratus_femoris", "obturator", "piriformis", "gemellus")
BONES = tuple(b + x for b in ("femur", "tibia", "fibula", "patella", "hip_bone") for x in ("_r", "_l"))
TRACKED = ("sciatic_n", "femoral_a_r", "femoral_v_r", "femoral_n", "popliteal_a_r", "popliteal_v_r", "tibial_n")


def subject_meshes(d):
    d = Path(d); m = json.loads((d / "manifest.json").read_text())
    V = np.frombuffer((d / "vertices.f32").read_bytes(), np.float32).reshape(-1, 3).astype(np.float64)
    F = np.frombuffer((d / "faces.u32").read_bytes(), np.uint32).reshape(-1, 3).astype(np.int64)
    out = {}
    for st in m["structures"]:
        v = V[st["vertex_offset"]:st["vertex_offset"] + st["vertex_count"]]; f = F[st["face_offset"]:st["face_offset"] + st["triangle_count"]] - st["vertex_offset"]
        if st["atlas_id"] in out:
            v0, f0 = out[st["atlas_id"]]; out[st["atlas_id"]] = (np.r_[v0, v], np.r_[f0, f + len(v0)])
        else:
            out[st["atlas_id"]] = (v, f)
    return out


def overlap(v, M, words, exact=False):
    """vertices of v inside each named mesh: (beyond 1 mm total, max depth, per mesh) -- vhm_tracked_clip.overlap."""
    from scripts.cryo.vhm_tracked_clip import overlap as ov
    return ov(v, M, words, exact)


def mesh_audit(bundle, subjects_dir):
    M = bundle_meshes(bundle); subj = {}
    for key in VOLS:
        subj.update(subject_meshes(Path(subjects_dir) / VOLS[key]["subject"]))
    out = {}
    for aid in TRACKED:
        vb = np.asarray(M[aid]["v"], np.float64); rb = overlap(vb, M, MUSCLE_WORDS); rs = overlap(subj[aid][0], M, MUSCLE_WORDS)
        bb = overlap(vb, M, BONES, exact=True)
        out[aid] = {"bundle": rb, "fullres_subject": rs, "bone_bundle": {"beyond_1mm_any": bb["beyond_1mm_any"], "max_depth_mm": bb["max_depth_mm"]}}
        print(f"{aid}: bundle {rb['beyond_1mm_any']}/{rb['vertices']} > 1 mm (max {rb['max_depth_mm']}), full-res {rs['beyond_1mm_any']}/{rs['vertices']}; "
              + ", ".join(f"{k} {v['beyond_1mm']} ({v['max_depth_mm']})" for k, v in rb["per_mesh"].items() if v["beyond_1mm"]))
    return out


def calibration(crops, skip):
    """her tissue colours: tracked nerve cores (eroded 1 mm) and vessel cores (eroded 0.5 mm) of the REGISTERED outlines, muscle
    interiors (5 px mean red < 90 eroded 2 mm) and fat interiors (> 178, eroded 2 mm) from the same photographs."""
    rng = np.random.default_rng(0); S_ = {"nerve": [], "lumen": [], "muscle": [], "fat": []}
    for key in VOLS:
        img = nib.load(str(reg_path(key))); L = np.asarray(img.dataobj); A = img.affine
        for lab, (aid, side, kind) in VOLS[key]["labels"].items():
            for sd in ([side] if side else ["right", "left"]):
                c = Crops(str(Path(crops) / SIDES[sd][0]), sd); xm = side_mask(A, L.shape, sd)
                for k in range(0, L.shape[2], 3):
                    m = (L[:, :, k] == lab) & xm[:, None]; y = int(round(A[2, 3] + k - ORIGIN[1]))
                    if m.sum() < 8 or y not in c.j_of or y in skip.get(sd, ()):
                        continue
                    core = ndi.binary_erosion(m, iterations=2 if kind == "nerve" else 1); ii, jj = np.nonzero(core)
                    if not len(ii):
                        continue
                    ax, az, _ = vox_atlas(A, ii, jj, k); pr, pc = c.atlas_to_px(y, ax, az); pr = np.rint(pr).astype(int); pc = np.rint(pc).astype(int)
                    im = c.image(y); ok = (pr >= 0) & (pc >= 0) & (pr < im.shape[0]) & (pc < im.shape[1])
                    S_["nerve" if kind == "nerve" else "lumen"].append(im[pr[ok], pc[ok]])
                    if key == "sciatic" and k % 9 == 0:
                        w = im.astype(np.float32); m5 = ndi.uniform_filter(w[..., 0], 5); gel = w[..., 2] > w[..., 0]
                        for nm, mm in (("muscle", ndi.binary_erosion((m5 < 90) & ~gel, iterations=6)), ("fat", ndi.binary_erosion((m5 > 178) & ~gel, iterations=6))):
                            rr, cc = np.nonzero(mm); sel = rng.choice(len(rr), min(4000, len(rr)), replace=False); S_[nm].append(im[rr[sel], cc[sel]])
    out = {"samples": {}, "her_rule": {"value_lt": MAX_VALUE, "red_ge": MIN_RED, "tissue": "red > blue + 8"}, "rule_rates": {}}
    q = lambda x: [round(float(t), 2) for t in np.percentile(x, [1, 5, 25, 50, 75, 95, 99])]
    arr = {}
    for k, v in S_.items():
        a_ = np.concatenate(v).astype(np.float32); a_ = a_[a_.max(1) > 0]; arr[k] = a_; r = a_[:, 0]
        out["samples"][k] = {"n": int(len(a_)), "pct": [1, 5, 25, 50, 75, 95, 99], "value": q(a_.max(1)), "red": q(r), "g_over_r": q(a_[:, 1] / np.maximum(r, 1))}
    from scripts.cryo.vhm_thigh_fat_plane_snap import classes as his_classes
    for k, a_ in arr.items():
        im = a_[None].astype(np.uint8)
        out["rule_rates"][k] = {"her_colour_rule_muscle": round(float(muscle_f(im, lumen=False)[0].mean()), 3),
                                "his_Q175_rule_muscle": round(float((his_classes(im, 55.0)[0] == 3).mean()), 3)}
    for vmax in (95, 100, 105, 110):
        for rmin in (45, 50, 55):
            key_ = f"value<{vmax},red>={rmin}"; out["rule_rates"].setdefault("grid", {})[key_] = {
                k: round(float(((a_[:, 0] > a_[:, 2] + 8) & (a_.max(1) < vmax) & (a_[:, 0] >= rmin)).mean()), 3) for k, a_ in arr.items()}
    return out


def do_audit(a):
    rep = json.loads(REPORT.read_text()) if REPORT.exists() else {}
    ph = json.loads(Path(a.crops, "photo_stats.json").read_text()); skip = {s: set(ph[s]["unusable"]) for s in ph}
    reg = json.loads(Path(a.crops, "registration.json").read_text()); rj = json.loads(REG_JSON.read_text())
    b = json.loads(Path(a.crops, "R_bbox.json").read_text()); bl = json.loads(Path(a.crops, "L_bbox.json").read_text())
    audit = {"mesh_overlap_as_shipped": mesh_audit(a.bundle, REPO / "build/vh")}
    share = {}
    for key in VOLS:
        for src_name, path in (("as_placed", VOLS[key]["src"]), ("registered", reg_path(key))):
            img = nib.load(str(path)); L = np.asarray(img.dataobj); A = img.affine
            for lab, (aid, side, kind) in VOLS[key]["labels"].items():
                for sd in ([side] if side else ["right", "left"]):
                    rows = photo_share(a.crops, L, A, lab, sd, skip[sd]); share.setdefault(f"{aid}:{sd}", {})[src_name] = share_summary(rows)
        for k_, v in share.items():
            if k_.split(":")[0] in [x[0] for x in VOLS[key]["labels"].values()]:
                print("share on photographed muscle", k_, v)
    audit["photo_share"] = share
    audit["calibration"] = calibration(a.crops, skip)
    print("calibration rule rates", audit["calibration"]["rule_rates"])
    zo = {s: [bb["levels"][str(y)]["z_offset_mm"] for y in (0, -375)] for s, bb in (("right", b), ("left", bl))}
    audit["registration"] = {
        "z": {"q154_cryo_z_minus_ras_mm": -944.7, "extra_offset_mm_at_y0_and_y-375": zo,
              "how": "femur (+ hip bone / patella) contour score over +-12 levels at the hip (y +25..-30) and knee (y -340..-410), 1 mm steps, per side; linear in y between"},
        "femur_in_plane": {s: {"levels": reg[s]["levels"], "levels_used": reg[s]["levels_used"], "residual_mm_median": reg[s]["residual_mm_median"],
                               "residual_mm_p90": reg[s]["residual_mm_p90"],
                               "smoothed_shift_mm_at": {str(r["y"]): [round(r["dr_smooth_px"] / 3, 2), round(r["dc_smooth_px"] / 3, 2)]
                                                         for r in reg[s]["per_level"] if r["y"] % 50 == 0}} for s in reg},
        "tracked_outline_translation_mm": {s: {y: v["atlas_dx_dz_mm"] for y, v in rows.items() if int(y) % 25 == 0} for s, rows in rj["sides"].items()}}
    audit["unusable_photographs"] = {s: {"unusable": ph[s]["unusable"], "flagged_marginal_kept": ph[s]["flagged_only"],
                                         "levels": {y: ph[s]["levels"][str(y)] for y in ph[s]["unusable"] + ph[s]["flagged_only"]}} for s in ph}
    rep.update({"source": SOURCE, "task": "Q179 her photo-tracked thigh/knee structures to the Q173-Q178 standard", "audit": audit})
    REPORT.write_text(json.dumps(rep, indent=1))


def do_register(a):
    M = bundle_meshes(a.bundle); rep = {}
    for side, (pfx, sfx) in SIDES.items():
        bb = Path(a.crops) / f"{pfx}_bbox.json"; b = json.loads(bb.read_text())
        for L in b["levels"].values():                      # register from the streamer's starting shift
            L.pop("RS_by_side", None); L.pop("CS_by_side", None)
        bb.write_text(json.dumps(b))
        c = Crops(str(Path(a.crops) / pfx), side)
        tms = [trimesh.Trimesh(M[k]["v"], M[k]["f"], process=False) for k in ("femur" + sfx, "patella" + sfx)]
        hip = trimesh.Trimesh(M["hip_bone" + sfx]["v"], M["hip_bone" + sfx]["f"], process=False) if "hip_bone" + sfx in M else None
        R = REG_R_MM; coarse = [(dr, dc) for dr in range(-R, R + 1) for dc in range(-R, R + 1)]
        rows = []
        for y in c.ys:
            P = contour_points(tms + ([hip] if (hip is not None and y > -30) else []), y)
            if P is None:
                continue
            pr, pc = c.atlas_to_px(y, P[:, 0], P[:, 1]); im = c.image(y)
            G1 = edge_map(im, 3); s1 = contour_score(G1, pr / 3, pc / 3, coarse); k = int(s1.argmax()); dr, dc = coarse[k]
            far = np.array([max(abs(r - dr), abs(q - dc)) >= 4 for r, q in coarse]); ratio = float(s1[k] / max(s1[far].max(), 1e-3))
            G3 = edge_map(im, 1); fine = [(3 * dr + i, 3 * dc + j) for i in range(-3, 4) for j in range(-3, 4)]
            s3 = contour_score(G3, pr, pc, fine); kf = int(s3.argmax())
            rows.append({"y": int(y), "dr_px": fine[kf][0], "dc_px": fine[kf][1], "score": round(float(s1[k]), 3), "peak_ratio": round(ratio, 3)})
        y = np.array([r["y"] for r in rows]); dr = np.array([r["dr_px"] for r in rows], float); dc = np.array([r["dc_px"] for r in rows], float)
        ok = np.array([r["peak_ratio"] >= REG_PEAK_RATIO for r in rows])
        for _ in range(3):                                  # outliers: > 3 mm from the running median of the kept levels
            mr = running(dr, ok, med=31, mean=1); mc = running(dc, ok, med=31, mean=1)
            ok = ok & (np.hypot(dr - mr, dc - mc) <= 3 * REG_OUTLIER_MM)
        sr = running(dr, ok); sc_ = running(dc, ok)
        for r, u, v, o in zip(rows, sr, sc_, ok):
            r["used"] = bool(o); r["dr_smooth_px"] = round(float(u), 2); r["dc_smooth_px"] = round(float(v), 2)
        # write the registered per-level mapping (RS/CS for this side) into the bbox json
        b = json.loads(bb.read_text()); sc = b["sc"]; byy = {r["y"]: r for r in rows}
        for ys, L in b["levels"].items():
            yy = int(ys); u = float(np.interp(yy, y[::-1], sr[::-1])); v = float(np.interp(yy, y[::-1], sc_[::-1]))
            L["RS_by_side"] = {side: L["RS"] + sc * u / 3.0}; L["CS_by_side"] = {side: L["CS"] - sc * v / 3.0}
            L["reg_px"] = {side: [round(u, 2), round(v, 2)]}
        b["registration"] = {"method": "her CT femur contour on the photograph edge map (vhf_tracked_q179.py register)"}
        bb.write_text(json.dumps(b))
        res = np.hypot(dr - sr, dc - sc_)[ok] / 3.0
        rep[side] = {"levels": len(rows), "levels_used": int(ok.sum()), "residual_mm_median": round(float(np.median(res)), 2),
                     "residual_mm_p90": round(float(np.percentile(res, 90)), 2), "per_level": rows}
        print(side, rep[side]["levels"], "used", rep[side]["levels_used"], "residual median/p90 mm", rep[side]["residual_mm_median"], rep[side]["residual_mm_p90"])
    Path(a.crops, "registration.json").write_text(json.dumps(rep))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="mode", required=True)
    p = sub.add_parser("register"); p.add_argument("--crops", required=True); p.add_argument("--bundle", default=str(REPO / "build/viewer_f_hr"))
    p = sub.add_parser("offsets"); p.add_argument("--crops", required=True)
    sub.add_parser("regvol")
    p = sub.add_parser("photos"); p.add_argument("--crops", required=True)
    p = sub.add_parser("clip"); p.add_argument("--crops", required=True)
    p = sub.add_parser("interp"); p.add_argument("--crops", required=True)
    p = sub.add_parser("audit"); p.add_argument("--crops", required=True); p.add_argument("--bundle", default=str(REPO / "build/viewer_f_hr"))
    a = ap.parse_args()
    {"register": do_register, "offsets": do_offsets, "regvol": do_regvol, "audit": do_audit, "clip": do_clip, "interp": do_interp,
     "photos": lambda a: Path(a.crops, "photo_stats.json").write_text(json.dumps(photo_stats(a.crops)))}[a.mode](a)


if __name__ == "__main__":
    main()
