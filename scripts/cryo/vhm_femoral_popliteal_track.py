"""Q174: the MALE femoral and popliteal neurovascular bundles, tracked in his FULL-RESOLUTION (0.33 mm) cryosection
crops -- the male counterpart of Q55/Q56 (vhf_femoral_track.py, vhf_popliteal_track.py).

    # crops (atlas boxes; delete after use):
    python3 scripts/cryo/vhm_stream_leg_crops.py --index SCRATCH/vh_cryo/cryo_index.json --y-top 70 --y-bot -420 \
        --box right=0,170,-70,120 --box left=-170,0,-70,120 --ap-row -1 --out SCRATCH/q174/fem
    python3 scripts/cryo/vhm_stream_leg_crops.py --index SCRATCH/vh_cryo/cryo_index.json --y-top -280 --y-bot -580 \
        --box right=50,225,-145,45 --box left=-225,-50,-145,45 --ap-row -1 --out SCRATCH/q174/pop
    # fold the Q173 photograph-to-atlas registration into the crop mapping (per side), then track:
    python3 scripts/cryo/vhm_femoral_popliteal_track.py register --crops SCRATCH/q174/fem --out SCRATCH/q174/femR
    python3 scripts/cryo/vhm_femoral_popliteal_track.py femoral --crops SCRATCH/q174/femR --side right --out SCRATCH/q174/fem_right
    python3 scripts/cryo/vhm_femoral_popliteal_track.py popliteal --crops SCRATCH/q174/popR --side right --out SCRATCH/q174/pop_right
    # her cleaning gates, the verified spans (SHIP below), volumes, subjects, report, badges:
    python3 scripts/cryo/vhf_popliteal_track.py clean --tracks SCRATCH/q174/fem_right --span artery=35:-17 vein=35:-225 --side right
    python3 scripts/cryo/vhf_popliteal_track.py clean --tracks SCRATCH/q174/fem_left --span artery=11:-33 vein=35:-280 --side left
    python3 scripts/cryo/vhf_popliteal_track.py clean --tracks SCRATCH/q174/pop_right --span vein=-380:-455 --crops SCRATCH/q174/popR --side right
    python3 scripts/cryo/vhf_popliteal_track.py clean --tracks SCRATCH/q174/pop_left --span vein=-395:-446 tibial_n=-393:-445 --crops SCRATCH/q174/popR --side left
    python3 scripts/cryo/vhf_nerve_volume.py --crops SCRATCH/q174/femR --track femoral_a_r=SCRATCH/q174/fem_right_artery_clean.json:35:-17 \
        --track femoral_a_l=SCRATCH/q174/fem_left_artery_clean.json:11:-33 --track femoral_v_r=SCRATCH/q174/fem_right_vein_clean.json:35:-35 \
        --track femoral_v_r=SCRATCH/q174/fem_right_vein_clean.json:-98:-225 --track femoral_v_l=SCRATCH/q174/fem_left_vein_clean.json:35:-280 \
        --out data/ct_sources/task_outputs/vhm_femoral_cryo.nii.gz --labels-out mappings/vhm_femoral_labels.json \
        --mapping-out mappings/subjects/ct_vhm_femoral_volume_mapping.json --subject ct_vhm_femoral
    python3 scripts/cryo/vhf_nerve_volume.py --crops SCRATCH/q174/popR --track popliteal_v_r=SCRATCH/q174/pop_right_vein_clean.json:-380:-455 \
        --track popliteal_v_l=SCRATCH/q174/pop_left_vein_clean.json:-395:-446 --track tibial_n=SCRATCH/q174/pop_left_tibial_n_clean.json:-393:-429 \
        --out data/ct_sources/task_outputs/vhm_popliteal_cryo.nii.gz --labels-out mappings/vhm_popliteal_labels.json \
        --mapping-out mappings/subjects/ct_vhm_popliteal_volume_mapping.json --subject ct_vhm_popliteal
    (mapping notes/sides edited by hand) ; convert + badge: scripts/vhm_rebuild_bundle.sh (Q174 block)
    python3 scripts/cryo/vhm_femoral_popliteal_track.py verify --scratch SCRATCH/q174 ; ... badge

WHAT IS DIFFERENT IN HIM (checked on his photographs, scratch q174/z*.png, not assumed):
  * His muscle is darker than hers (median red 66-75 against her 75-95) and his clotted veins are near-black (red
    20-35): a FIXED core threshold (3 px mean red < 55; his left femoral vein is dark brown, red 43-48; his darkest muscle 0.1st percentile
    44-55) separates them, where her adaptive "window 15th percentile + 18" walks into his muscle.
  * His EMPTY arteries: under the inguinal ligament his femoral artery is a thick-walled ring whose lumen holds BLUE
    embedding gelatine (his body was cut into blocks before embedding; the legs block's cut end is just above), not
    clot; blue inside the limb is a lumen, blue touching the crop edge is the embedding medium (as her rule). Lower
    down the contracted artery has no dark lumen at all: the lumen rule does not see it there, and it is NOT forced.
  * His veins are collapsed slits (aspect up to ~3.5): the aspect limit is 4.0 (hers 2.5).
RULES (all per 1 mm level, full-resolution pixels; +Z anterior, +X the subject's left-to-right):
  lumen   = core (3 px mean red < 55, not edge-touching blue, opened 0.33 mm, holes filled, >= 1.5 mm2), touching lumina
            split only where the distance transform has two maxima >= 1 mm above their saddle (h-maxima, so a slit vein
            is not cut in two), each grown <= 1 mm into red < 85 (the wall/clot edge).
  walk    = link by OVERLAP: the lumen at the next level must overlap the previous lumen dilated by 1 mm (+0.5 mm per
            gap level), area 0.33-3x the previous, solidity >= 0.7, aspect <= 4, a paler rim (0.7-2 mm annulus mean red
            >= 25 above the lumen: a dark patch inside his dark left iliopsoas has ~10-15); best = overlap fraction minus
            0.5 |log area ratio|. A level with none is a gap that keeps the previous mask; `max_gap` gaps end the walk.
            Walked DOWN and UP from each seed.
  femoral seed  = her landmark rule unchanged (vhf_femoral_track.seed_level): first level with a pair of lumina within
            35 mm of the inguinal-ligament midpoint (ASIS + pubic tubercle)/2 of his hip bone, the LATERAL member the
            artery, the MEDIAL the vein.
  canal seed    = at the mid-thigh level y_mid = (inguinal midpoint y + lowest y of his adductor magnus)/2, the largest
            lumen of >= 30 mm2 within 15 mm of his sartorius section (the roof of the adductor canal) = the femoral
            vein (his femoral artery there is empty and contracted; the only clotted lumen under sartorius is the vein).
  pair    = the artery must stay within 25 mm of the vein at every level it is tracked on and never be the same lumen.
  popliteal seed = her rule unchanged in substance (vhf_popliteal_track.seed_pair): the first level below the adductor
            hiatus with a pair of lumina behind the posterior cortex of his femur (<= 40 mm behind it, 3-20 mm apart in
            depth, <= 14 mm across); the ANTERIOR (deep) member is the artery, the POSTERIOR the vein.
  tibial n. = her fascicle-texture walk (vhf_popliteal_track.walk_nerve) behind his tracked popliteal VEIN (5-30 mm, <= 10 mm
            medial of it): her walk took the artery as the reference, and his artery lumen does not track.
  cleaning = her gates (vhf_femoral_track.clean_rows with the popliteal CLEAN_MM band; nerve: drop_intramuscular).
Registration: the crops are read through the Q173 per-side photograph-to-atlas shift (data/derived/
Q173_vhm_adductor_magnus.json, registration.used_px) folded into the crop mapping (`register`), so everything placed
here sits in the same frame as his Q57 sciatic nerve and Q173 thigh muscles. Rule-based; badged; numbers in the report.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi
from skimage.morphology import h_maxima
from skimage.segmentation import watershed

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.cryo.vhf_nerve_track import Crops, PX, disk, section_masks  # noqa: E402
from scripts.cryo import vhf_femoral_track as FT  # noqa: E402
from scripts.cryo.vhf_femoral_track import blob_stats, inguinal_midpoint, outside_gel  # noqa: E402
from scripts.cryo import vhf_popliteal_track as PT  # noqa: E402
from scripts.transfer.bundle_io import meshes_by_id, read_bundle_dir  # noqa: E402

SOURCE = ("U.S. National Library of Medicine, The Visible Human Project (public domain), male cryosections at full "
          "resolution (0.33 mm) via the NCI Imaging Data Commons, re-streamed by scripts/cryo/vhm_stream_leg_crops.py and "
          "read through the Q173 photograph-to-atlas registration. Derived data (scripts/cryo/vhm_femoral_popliteal_track.py).")
Q173 = REPO / "data/derived/Q173_vhm_adductor_magnus.json"
CORE_R, GROW_R = 55.0, 85.0
LAB_OF = {"artery": 1, "vein": 2, "tibial_n": 3}
AMAX = {"artery": 90.0, "vein": 200.0}


# ---------------------------------------------------------------- registration
def register(a):
    """Write <out>_bbox.json = the crops' bbox with his Q173 per-side shift folded into X0/Y0 (Crops reads X0_by_side /
    Y0_by_side), and link the per-side arrays, so every tool that takes a crop prefix reads the registered mapping."""
    rep = json.loads(Q173.read_text()); reg = rep["registration"]["used_px"]
    b = json.load(open(f"{a.crops}_bbox.json")); sc = b["sc"]; ap = b["ap_row"]
    assert ap == -1, "his photo legs frame has row 0 anterior (Q57)"
    # Crops.atlas_to_px: d(row)/d(Y0) = -3/sc and d(col)/d(X0) = +3/sc, so a shift of (dr, dc) crop px is Y0 - dr sc/3, X0 + dc sc/3
    b["X0_by_side"] = {s: b["X0"] + float(r[1]) * sc / 3.0 for s, r in reg.items()}
    b["Y0_by_side"] = {s: b["Y0"] - float(r[0]) * sc / 3.0 for s, r in reg.items()}
    b["registration"] = {"source": str(Q173.relative_to(REPO)) + " registration.used_px", "shift_px_rows_cols": reg}
    json.dump(b, open(f"{a.out}_bbox.json", "w"))
    for s in reg:
        src = os.path.abspath(f"{a.crops}_{s}.npy"); dst = f"{a.out}_{s}.npy"
        if os.path.lexists(dst):
            os.remove(dst)
        os.symlink(src, dst)
    print("registered", a.out, reg)


# ---------------------------------------------------------------- lumen detector
def lumina(im, core_r=CORE_R, grow_r=GROW_R, with_blue=False, split_h=6.0):
    """Label image of his dark lumina, see the module docstring. BLUE (gel-filled, his empty arteries near the legs-block
    cut) and BLACK (clot) cores are labelled separately so a blue artery touching a black vein stays two lumina."""
    R = im[..., 0].astype(np.float32); B = im[..., 2].astype(np.float32)
    R3 = ndi.uniform_filter(R, 3); B3 = ndi.uniform_filter(B, 3)
    gel = outside_gel(B > R + 15)
    bluish = (B3 > R3 + 15) & ~gel
    core = ndi.binary_fill_holes(ndi.binary_opening((R3 < core_r) & ~gel & ~bluish, structure=disk(1)))
    blue_core = ndi.binary_fill_holes(ndi.binary_opening(bluish & (R3 < grow_r), structure=disk(1)))   # gel in a lumen: any shade of blue
    cores = np.zeros(core.shape, np.int32); nxt = 0
    for part in (blue_core, core & ~blue_core):
        part = ndi.binary_opening(part, structure=disk(1))
        lab, n = ndi.label(part)
        if n == 0:
            continue
        big = np.zeros(n + 1, bool); big[1:] = ndi.sum(part, lab, range(1, n + 1)) * PX * PX >= 1.5
        part = big[lab]
        if not part.any():
            continue
        if split_h is None:                                  # no split: one clotted slit vein is one lumen
            ws, _ = ndi.label(part)
        else:
            dist = ndi.distance_transform_edt(part)
            mk, nm = ndi.label(h_maxima(dist, split_h) & part)  # maxima >= split_h px above their saddle
            comp, nc = ndi.label(part)                            # a lumen too small to have such a maximum stays one lumen
            has = np.zeros(nc + 1, bool); has[np.unique(comp[mk > 0])] = True
            for k in np.nonzero(~has[1:])[0] + 1:
                rr, cc = np.unravel_index(np.argmax(np.where(comp == k, dist, -1)), dist.shape); nm += 1; mk[rr, cc] = nm
            ws = watershed(-dist, mk, mask=part)
        cores[ws > 0] = ws[ws > 0] + nxt; nxt = int(cores.max())
    if nxt == 0:
        out = np.zeros(core.shape, np.int32)
        return (out, bluish) if with_blue else out
    grown = watershed(R3, cores, mask=(R3 < grow_r) & ~gel & ndi.binary_dilation(cores > 0, structure=disk(3)))
    grown = grown.astype(np.int32)
    return (grown, bluish) if with_blue else grown


def ring_contrast(R, m):
    """Mean red of the 0.7-2 mm annulus minus the lumen's mean red: a lumen has a paler wall/fat around it; a dark patch
    inside his dark muscle (left iliopsoas, 3 px red 45-55) does not (contrast ~10-15)."""
    ring = ndi.binary_dilation(m, structure=disk(6)) & ~ndi.binary_dilation(m, structure=disk(2))
    return float(R[ring].mean() - R[m].mean()) if ring.any() else 0.0


RING_MIN = 25.0


def stats_of(lab, i):
    m = lab == i
    return m, blob_stats(m)


def level_shift(crops, y_from, y_to):
    """Pixel offset of the same atlas point between two levels' crops (0 for his crops: one box, fixed constants)."""
    a = np.array(crops.atlas_to_px(y_from, 0.0, 0.0), float); b = np.array(crops.atlas_to_px(y_to, 0.0, 0.0), float)
    return b - a


def walk(crops, ys, y0, m0, name, max_gap=10, pair=None, pair_mm=25.0, forbid=None, amax=None, split_h=6.0, log=print):
    """Overlap-linked walk of one lumen from its seed mask over `ys` (ordered away from y0). `pair` = {y: (x, z)} of
    the partner vessel (artery must stay within pair_mm of the vein); `forbid` = {y: mask} lumina already taken."""
    amax = amax or AMAX.get(name, 200.0)
    prev = m0; s0 = blob_stats(m0); prev_a = s0["area_mm2"]; prev_y = y0; gaps = 0
    rows = [row(crops, y0, s0)]; masks = {y0: m0}
    for y in ys:
        if y == y0:
            continue
        im = crops.image(y)
        sh = level_shift(crops, prev_y, y)
        p = prev if not sh.any() else ndi.shift(prev.astype(np.uint8), sh, order=0) > 0
        r_px = int(round((1.0 + 0.5 * gaps) / PX))
        search = ndi.binary_dilation(p, structure=disk(r_px))
        lab, bluish = lumina(im, with_blue=True, split_h=split_h); R = im[..., 0].astype(np.float32)
        ids = np.unique(lab[search]); ids = ids[ids > 0]
        best, bsc = None, -1e9
        for i in ids:
            m = lab == i
            if forbid is not None and forbid.get(y) is not None and (m & forbid[y]).sum() > 0.3 * m.sum():
                continue
            if name == "vein" and float(bluish[m].mean()) > 0.3:     # gel-filled = an empty ARTERY, never his clotted vein
                continue
            a = m.sum() * PX * PX
            if not (max(1.5, prev_a / 3.0) <= a <= min(amax, 3.0 * prev_a)):
                continue
            s = blob_stats(m)
            if s["solidity"] < 0.70 or s["aspect"] > 4.0 or ring_contrast(R, m) < RING_MIN:
                continue
            if pair is not None:
                q = pair.get(y)
                if q is not None:
                    ax, az = crops.px_to_atlas(y, *s["rc"])
                    if np.hypot(float(ax) - q[0], float(az) - q[1]) > pair_mm:
                        continue
            ov = float((m & search).sum()) / m.sum()
            sc = ov - 0.5 * abs(np.log(a / prev_a))
            if sc > bsc:
                best, bsc = (m, s), sc
        if best is None:
            gaps += 1
            rows.append({"y": y, "gap": True, "x": rows[-1]["x"], "z": rows[-1]["z"]})
            if gaps > max_gap:
                break
            continue
        gaps = 0; prev, s = best; prev_a = s["area_mm2"]; prev_y = y
        masks[y] = prev; rows.append(row(crops, y, s))
    while rows and rows[-1]["gap"]:
        rows.pop()
    return rows, {y: m for y, m in masks.items() if any(r["y"] == y and not r["gap"] for r in rows)}


def row(crops, y, s):
    ax, az = crops.px_to_atlas(y, *s["rc"])
    return {"y": int(y), "gap": False, "x": round(float(ax), 1), "z": round(float(az), 1), "area_mm2": round(s["area_mm2"], 1),
            "diam_mm": round(s["diam_mm"], 1), "inscribed_mm": round(s["inscribed_mm"], 1),
            "solidity": round(s["solidity"], 2), "aspect": round(s["aspect"], 2)}


def both_ways(crops, ys_all, y0, m0, name, **kw):
    """Walk DOWN and UP from the seed and merge (seed row once)."""
    down = [y for y in ys_all if y <= y0]; up = [y for y in ys_all if y >= y0][::-1]
    rd, md = walk(crops, down, y0, m0, name, **kw)
    ru, mu = walk(crops, up, y0, m0, name, **kw)
    by = {r["y"]: r for r in ru + rd}
    rows = [by[y] for y in sorted(by, reverse=True)]
    return rows, {**mu, **md}


def femoral_seed(crops, meshes, side, ys, log=print):
    """Her Q55 seed rule (vhf_femoral_track.seed_pair: a pair of lumina within 35 mm of the inguinal-ligament midpoint,
    3-25 mm apart across, < 18 mm in depth; LATERAL = artery, MEDIAL = vein), fed by HIS lumen detector, top-down
    from the level of that midpoint (his crops start 35 mm above it; hers started below it)."""
    mid = inguinal_midpoint(meshes, side)
    for y in [v for v in ys if v <= mid["y"]]:          # the femoral vessels begin at the inguinal ligament
        im = crops.image(y); lab = lumina(im, split_h=None); cands = []; R = im[..., 0].astype(np.float32)
        for i in range(1, int(lab.max()) + 1):
            m = lab == i
            if not m.any():
                continue
            s = blob_stats(m)
            # >= 12 mm2 (3.9 mm): her cleaning floor for a femoral lumen (0.75 x 5 mm); her seed took 8 mm2, which on his
            # left side seeds on a 3.2 mm side lumen above the vessels' gel-filled segment
            if not (12.0 <= s["area_mm2"] <= 200.0) or s["solidity"] < 0.75 or s["aspect"] > 4.0 or ring_contrast(R, m) < RING_MIN:
                continue
            ax, az = crops.px_to_atlas(y, *s["rc"]); cands.append(dict(s, lab=i, x=float(ax), z=float(az)))
        try:
            art, vein = FT.seed_pair(cands, mid, side)
        except SystemExit:
            continue
        if vein is None:
            continue
        log(f"seed level y={y}: artery x{art['x']:.0f} z{art['z']:.0f} d{art['diam_mm']:.1f} | vein x{vein['x']:.0f} z{vein['z']:.0f} d{vein['diam_mm']:.1f}")
        return y, lab == art["lab"], lab == vein["lab"], art, vein, mid
    raise SystemExit("no femoral lumen pair near the inguinal midpoint")


def gel_artery_seed(crops, side, ys, vxz, v_masks, log=print):
    """His femoral ARTERY seed: from the vein's seed level down, the first level with a gel-filled (>= 50 % blue) lumen of
    >= 12 mm2, LATERAL of his tracked femoral vein (>= 2 mm) and within 25 mm of it. Under the ligament his artery is
    empty and holds the blue embedding gelatine (module docstring); the vein is the medial member of her Q55 pair."""
    sg = 1.0 if side == "right" else -1.0
    for y in ys:
        if y not in vxz:
            continue
        im = crops.image(y); lab, bl = lumina(im, with_blue=True, split_h=None); R = im[..., 0].astype(np.float32)
        best = None
        for i in range(1, int(lab.max()) + 1):
            m = lab == i
            if not m.any() or float(bl[m].mean()) < 0.5 or (m & v_masks[y]).any():
                continue
            s = blob_stats(m)
            if s["area_mm2"] < 12.0 or s["solidity"] < 0.75 or s["aspect"] > 4.0 or ring_contrast(R, m) < RING_MIN:
                continue
            ax, az = crops.px_to_atlas(y, *s["rc"]); ax, az = float(ax), float(az)
            vx, vz = vxz[y]
            if sg * (ax - vx) < 2.0 or np.hypot(ax - vx, az - vz) > 25.0:
                continue
            if best is None or s["area_mm2"] > best[1]["area_mm2"]:
                best = (m, s, ax, az)
        if best is not None:
            m, s, ax, az = best
            log(f"artery seed y={y}: gel-filled lumen x{ax:.0f} z{az:.0f} d{s['diam_mm']:.1f} lateral of the vein")
            return y, m, {"y": y, "x": round(ax, 1), "z": round(az, 1),
                          "rule": "first gel-filled (blue) lumen >= 12 mm2 lateral of his tracked femoral vein and within 25 mm of it, "
                                  "from the vein's seed level (the medial member of her Q55 pair near the inguinal midpoint) down"}
    return None, None, None


def seed_canal(crops, meshes, side, ys, log=print):
    """Canal seed (module docstring): at y_mid the largest lumen >= 30 mm2 within 15 mm of his sartorius section."""
    mid = inguinal_midpoint(meshes, side); am = meshes["adductor_magnus_" + side[0]]["v"]
    y_mid = int(round((mid["y"] + float(am[:, 1].min())) / 2.0))
    for y in sorted(ys, key=lambda v: abs(v - y_mid)):
        if abs(y - y_mid) > 15:
            break
        im = crops.image(y); lab, bl = lumina(im, with_blue=True, split_h=None)
        sart = section_masks(meshes, ["sartorius"], side, y, crops, im.shape[:2]).get("sartorius")
        if sart is None or not sart.any():
            continue
        near = ndi.distance_transform_edt(~sart) * PX <= 15.0
        best = None
        for i in range(1, int(lab.max()) + 1):
            m = lab == i; a = m.sum() * PX * PX
            if a < 30.0 or not (m & near).any() or float(bl[m].mean()) > 0.3:
                continue
            s = blob_stats(m)
            if s["solidity"] < 0.7 or s["aspect"] > 4.0 or ring_contrast(im[..., 0].astype(np.float32), m) < RING_MIN:
                continue
            if best is None or a > best[2]:
                best = (m, s, a)
        if best is not None:
            ax, az = crops.px_to_atlas(y, *best[1]["rc"])
            log(f"canal seed y={y} (y_mid {y_mid}): vein x{float(ax):.0f} z{float(az):.0f} d{best[1]['diam_mm']:.1f}")
            return y, best[0], {"y": y, "y_mid": y_mid, "x": round(float(ax), 1), "z": round(float(az), 1),
                                "rule": "largest lumen >= 30 mm2 within 15 mm of his sartorius section at the mid-thigh level "
                                        "(inguinal midpoint y + lowest adductor magnus y)/2"}
    return None, None, None


# ---------------------------------------------------------------- outputs
def save(out, side, tracks, masks, seeds, ys_all, crops, extra=None):
    idx = {y: i for i, y in enumerate(ys_all)}
    store = f"{out}_labels.npy"
    labs = np.lib.format.open_memmap(store, mode="w+", dtype=np.uint8, shape=(len(ys_all), crops.a.shape[1], crops.a.shape[2]))
    for name, mk in masks.items():
        for y, m in mk.items():
            labs[idx[y], :m.shape[0], :m.shape[1]][m] = LAB_OF[name]
    labs.flush()
    for name, rows in tracks.items():
        for r in rows:
            if not r["gap"]:
                r["lab"] = LAB_OF[name]; r["level_index"] = idx[r["y"]]
        found = [r for r in rows if not r["gap"]]
        d = {"source": SOURCE, "badge": "rule-based", "structure": name, "side": side, "seed": seeds.get(name),
             "levels": len(rows), "tracked_levels": len(found),
             "y_top": found[0]["y"] if found else None, "y_bottom": found[-1]["y"] if found else None, "rows": rows}
        if extra:
            d.update(extra)
        p = f"{out}_{name}.json"; Path(p).write_text(json.dumps(d, indent=1))
        lp = p.replace(".json", "_labels.npy")
        if os.path.exists(lp):
            os.remove(lp)
        os.link(store, lp)
        if found:
            print(f"{name}: {len(found)}/{len(rows)} levels, y {d['y_top']} .. {d['y_bottom']}, "
                  f"median d {np.median([r['diam_mm'] for r in found]):.1f} mm")
        else:
            print(f"{name}: nothing tracked")


def merge_rows(*chains):
    by = {}
    for rows in chains:
        for r in rows:
            if r["y"] not in by or (by[r["y"]]["gap"] and not r["gap"]):
                by[r["y"]] = r
    return [by[y] for y in sorted(by, reverse=True)]


def do_femoral(a):
    crops = Crops(a.crops, a.side)
    bf, blob = read_bundle_dir(a.bundle); meshes = meshes_by_id(bf, blob)
    ys_all = sorted([y for y in crops.ys if a.y_end <= y <= a.y_start], reverse=True)
    y0, ma, mv, art0, vein0, mid = femoral_seed(crops, meshes, a.side, ys_all)
    seeds = {"artery": {"y": y0, "x": round(art0["x"], 1), "z": round(art0["z"], 1), "inguinal_midpoint": mid,
                        "rule": "lateral member of the lumen pair near the inguinal-ligament midpoint (her Q55 rule)"},
             "vein": {"y": y0, "x": round(vein0["x"], 1), "z": round(vein0["z"], 1), "inguinal_midpoint": mid,
                      "rule": "medial member of the lumen pair near the inguinal-ligament midpoint (her Q55 rule)"}}
    v_rows, v_masks = both_ways(crops, ys_all, y0, mv, "vein", max_gap=a.max_gap, split_h=None)
    cy, cm, cseed = seed_canal(crops, meshes, a.side, ys_all)
    if cy is not None and cy not in v_masks:
        c_rows, c_masks = both_ways(crops, ys_all, cy, cm, "vein", max_gap=a.max_gap, split_h=None)
        seeds["vein_canal"] = cseed
        v_rows = merge_rows(v_rows, c_rows); v_masks = {**c_masks, **v_masks}
    vxz = {r["y"]: (r["x"], r["z"]) for r in v_rows if not r["gap"]}
    ya, ma2, aseed = gel_artery_seed(crops, a.side, [y for y in ys_all if y <= y0], vxz, v_masks)
    if ya is not None:                                  # HIS artery: the gel-filled lumen lateral to his vein
        ya0, ma = ya, ma2; seeds["artery"] = dict(aseed, inguinal_midpoint=mid, pair_rule_artery={"y": y0, "x": round(art0["x"], 1),
                                                                                                "z": round(art0["z"], 1)})
    else:
        ya0 = y0
    a_rows, a_masks = both_ways(crops, ys_all, ya0, ma, "artery", max_gap=a.max_gap, pair=vxz, pair_mm=25.0, forbid=v_masks,
                                split_h=None)
    for r in v_rows:
        if r["y"] in a_masks and r["y"] in v_masks and (a_masks[r["y"]] & v_masks[r["y"]]).any():
            raise SystemExit(f"artery and vein share a lumen at y={r['y']}")
    save(a.out, a.side, {"artery": a_rows, "vein": v_rows}, {"artery": a_masks, "vein": v_masks}, seeds, ys_all, crops)


def do_popliteal(a):
    crops = Crops(a.crops, a.side)
    bf, blob = read_bundle_dir(a.bundle); meshes = meshes_by_id(bf, blob)
    ys_all = sorted([y for y in crops.ys if a.y_end <= y <= a.y_start], reverse=True)
    y0 = None
    for y in ys_all:                                    # her seed rule, fed by HIS lumen detector
        im = crops.image(y)
        fem = PT.femur_posterior(meshes, a.side, y, crops, im.shape[:2])
        if fem is None:
            continue
        lab = lumina(im); cands = []
        for i in range(1, int(lab.max()) + 1):
            m = lab == i
            if not m.any():
                continue
            s = blob_stats(m)
            if not (6.0 <= s["area_mm2"] <= 160.0) or s["solidity"] < 0.75 or s["aspect"] > 4.0 or \
                    ring_contrast(im[..., 0].astype(np.float32), m) < RING_MIN:
                continue
            ax, az = crops.px_to_atlas(y, *s["rc"])
            cands.append(dict(s, lab=i, x=float(ax), z=float(az)))
        art, vein = PT.seed_pair(cands, fem)
        if art is None:
            continue
        y0 = y; ma, mv = lab == art["lab"], lab == vein["lab"]
        seed = {"y": y, "femur_popliteal_surface": {"x": round(fem["x"], 1), "z": round(fem["z_post"], 1)},
                "artery": {"x": round(art["x"], 1), "z": round(art["z"], 1)}, "vein": {"x": round(vein["x"], 1), "z": round(vein["z"], 1)},
                "rule": "first level with a pair of lumina behind the posterior cortex of his femur; the ANTERIOR (deep) member "
                        "is the artery, the POSTERIOR the vein (her Q56 rule)"}
        print(f"seed y={y}: femur z{fem['z_post']:.0f} | artery x{art['x']:.0f} z{art['z']:.0f} d{art['diam_mm']:.1f} | "
              f"vein x{vein['x']:.0f} z{vein['z']:.0f} d{vein['diam_mm']:.1f}")
        break
    if y0 is None:
        raise SystemExit("no popliteal lumen pair")
    v_rows, v_masks = both_ways(crops, ys_all, y0, mv, "vein", max_gap=a.max_gap)
    vxz = {r["y"]: (r["x"], r["z"]) for r in v_rows if not r["gap"]}
    a_rows, a_masks = both_ways(crops, ys_all, y0, ma, "artery", max_gap=a.max_gap, pair=vxz, pair_mm=22.0, forbid=v_masks)
    # the nerve's reference is his tracked popliteal VEIN (her walk_nerve used the artery; his artery lumen does not
    # track, see the report): posterior to the vein (z >= 2 mm less), 5-30 mm from it, not more than 10 mm medial of it
    ref = vxz
    ys_a = sorted(ref, reverse=True); n_rows, n_masks = [], {}
    for leg in ([y for y in ys_a if y <= y0], [y for y in ys_a if y >= y0][::-1]):
        r, m = PT.walk_nerve(crops, meshes, a.side, PT.POPLITEAL, leg, ref, "tibial_n", reach_mm=a.nerve_reach, max_gap=a.nerve_gap,
                             lateral_min=-10.0, behind_mm=(5.0, 30.0))
        n_rows += r; n_masks.update(m)
    n_rows = merge_rows(n_rows)
    while n_rows and n_rows[0]["gap"]:
        n_rows.pop(0)
    seeds = {"artery": seed, "vein": seed, "tibial_n": {"rule": "fascicle-texture blob posterior to his tracked popliteal vein, "
                                                                 "5-30 mm from it, <= 10 mm medial of it (her Q56 walk_nerve, vein as reference)"}}
    save(a.out, a.side, {"artery": a_rows, "vein": v_rows, "tibial_n": n_rows},
         {"artery": a_masks, "vein": v_masks, "tibial_n": n_masks}, seeds, ys_all, crops,
         extra={"popliteus_lower_border_y": round(PT.popliteus_end(meshes, a.side), 1)})


# ---------------------------------------------------------------- what is shipped (the ranges verified on the montages)
# atlas_id -> (subject, side, clean track file stem under the scratch dir, [(y_top, y_bottom), ...])
SHIP = {
    "femoral_a_r": ("ct_vhm_femoral", "right", "fem_right_artery", [(35, -17)]),
    "femoral_a_l": ("ct_vhm_femoral", "left", "fem_left_artery", [(11, -33)]),
    "femoral_v_r": ("ct_vhm_femoral", "right", "fem_right_vein", [(35, -35), (-98, -225)]),
    "femoral_v_l": ("ct_vhm_femoral", "left", "fem_left_vein", [(35, -280)]),
    "popliteal_v_r": ("ct_vhm_popliteal", "right", "pop_right_vein", [(-380, -455)]),
    "popliteal_v_l": ("ct_vhm_popliteal", "left", "pop_left_vein", [(-395, -446)]),
    "tibial_n": ("ct_vhm_popliteal", "left", "pop_left_tibial_n", [(-393, -429)]),
}
NULLED = {
    "popliteal_a_r": "No arterial lumen tracks in his popliteal fossa. His arteries are EMPTY (post-mortem) -- under the inguinal "
                     "ligament the femoral artery holds blue embedding gelatine, lower down it is a contracted ring with no dark lumen -- "
                     "while the veins hold black clot. Her Q56 pair rule (deep member of the lumen pair behind the femur = artery) "
                     "fired at y -406 on a 3.3 mm clotted lumen touching the vein, which held 3 levels (attempt 2) / a ragged fat patch "
                     "(attempt 1, her tracker unchanged); a second clotted lumen beside his popliteal vein may equally be a paired "
                     "popliteal vein, so nothing is shipped under the artery's name.",
    "popliteal_a_l": "Same as the right: the pair rule's deep clotted lumen held 7 levels (y -398..-406) and cannot be told from a "
                     "paired popliteal vein; his popliteal artery is empty and contracted.",
    "tibial_n (right)": "The fascicle-texture walk behind his right popliteal vein held 7 levels (y -399..-409), under the 20-level / "
                        "30 mm bar (attempt 1 behind the artery: 1-2 levels). Only the LEFT tibial nerve is shipped.",
    "femoral_a (adductor canal, both sides)": "Below the origin of the profunda his femoral artery is empty and contracted: no dark or "
                        "gel-filled lumen to follow (the lumen walk ends at y -17 right / -33 left); not forced.",
}
PUBLISHED = {
    "femoral_a": {"value_mm": "common femoral artery, men: 9.8 +/- 1.0 mm (ultrasound, outer diameter); superficial femoral 7-8 mm",
                  "ref": "Sandgren T, Sonesson B, Ahlgren AR, Lanne T. The diameter of the common femoral artery in healthy human: "
                         "influence of sex, age, and body size. J Vasc Surg 1999;29:503-10"},
    "femoral_v": {"value_mm": "common femoral vein ~10-13 mm, femoral vein ~8-11 mm (supine living adults; the vein is collapsed in a cadaver)",
                  "ref": "Gray's Anatomy 42nd ed. (Standring 2020) 'Thigh'; Moore Clinically Oriented Anatomy 8th ed."},
    "popliteal_v": {"value_mm": "popliteal vein ~7-11 mm (living adults)", "ref": "Gray's Anatomy 42nd ed.; Moore 8th ed. (as Q56)"},
    "tibial_n": {"value_mm": "tibial nerve in the popliteal fossa: cross-sectional area ~20-40 mm2 (~5-7 mm)",
                 "ref": "Cartwright MS et al. Cross-sectional area reference values for nerve ultrasonography. Muscle Nerve 2008;37:566-71"},
}
BONES = ["femur", "tibia", "fibula", "patella", "hip_bone"]


def load_ship_rows(scratch, stem, spans):
    d = json.load(open(f"{scratch}/{stem}_clean.json"))
    rows = [r for r in d["rows"] if any(lo <= r["y"] <= hi for hi, lo in spans)]
    return d, rows


def subject_meshes(subj):
    d = REPO / "build/vh" / subj; m = json.loads((d / "manifest.json").read_text())
    V = np.frombuffer((d / "vertices.f32").read_bytes(), np.float32).reshape(-1, 3).astype(np.float64)
    F = np.frombuffer((d / "faces.u32").read_bytes(), np.uint32).reshape(-1, 3).astype(np.int64)
    out = {}
    for st in m["structures"]:
        v = V[st["vertex_offset"]:st["vertex_offset"] + st["vertex_count"]]
        f = F[st["face_offset"]:st["face_offset"] + st["triangle_count"]] - st["vertex_offset"]
        out[st["atlas_id"]] = (v, f)
    return out


def inside(P, v, f):
    import trimesh
    tm = trimesh.Trimesh(v, f, process=False); c = tm.contains(P); d = np.zeros(len(P))
    if c.any():
        d[c] = trimesh.proximity.closest_point(tm, P[c])[1]
    return c, d


def section_centroid(mesh, y):
    import trimesh
    sec = trimesh.Trimesh(mesh["v"], mesh["f"], process=False).section(plane_origin=[0, y, 0], plane_normal=[0, 1, 0])
    if sec is None:
        return None
    P = sec.vertices
    return P


def verify(a):
    import trimesh
    bf, blob = read_bundle_dir(a.bundle); M = meshes_by_id(bf, blob)
    subj = {s: subject_meshes(s) for s in ("ct_vhm_femoral", "ct_vhm_popliteal")}
    rep = {"source": SOURCE, "badge": "rule-based", "task": "Q174 his femoral + popliteal neurovascular bundles (VH male cryosections, 0.33 mm)",
           "method": __doc__.split("RULES")[0].strip(), "registration": json.loads(Q173.read_text())["registration"]["used_px"],
           "published": PUBLISHED, "structures": {}, "nulled": NULLED, "attempts": {}}
    for aid, (sj, side, stem, spans) in SHIP.items():
        d, rows = load_ship_rows(a.scratch, stem, spans)
        found = [r for r in rows if not r["gap"]]
        dd = [r["diam_mm"] for r in found]; ins = [r["inscribed_mm"] for r in found]
        levels = sum(hi - lo + 1 for hi, lo in spans)
        v, f = subj[sj][aid]
        st = {"subject": sj, "side": side, "spans_y": spans, "levels_in_spans": levels, "tracked_levels": len(found),
              "gap_levels_filled": levels - len(found), "pieces": len(spans), "seed": d.get("seed"),
              "levels_dropped_by_cleaning": sum(1 for r in rows if r.get("dropped")),
              "diameter_mm": {"area_equivalent_median": round(float(np.median(dd)), 1), "p10": round(float(np.percentile(dd, 10)), 1),
                              "p90": round(float(np.percentile(dd, 90)), 1), "inscribed_median": round(float(np.median(ins)), 1)},
              "section_mm2_median": round(float(np.median([r["area_mm2"] for r in found])), 1),
              "mesh": {"vertices": int(len(v)), "triangles": int(len(f)), "y_range": [round(float(v[:, 1].min()), 1), round(float(v[:, 1].max()), 1)]},
              "longest_run_without_detection": max((sum(1 for _ in g) for k, g in __import__("itertools").groupby(rows, key=lambda r: r["gap"]) if k), default=0)}
        # bone: no vertex inside
        sfx = "_r" if side == "right" else "_l"; bone = {}
        for b in BONES:
            m = M.get(b + sfx)
            if m is None:
                continue
            c, dep = inside(v, m["v"], m["f"]); bone[b + sfx] = {"inside": int(c.sum()), "max_depth_mm": round(float(dep.max()), 2)}
        st["vertices_inside_bone"] = bone
        # muscle overlap (every muscle mesh whose bbox meets this structure's)
        lo, hi = v.min(0) - 1, v.max(0) + 1; mus = {}
        for mid_, m in M.items():
            if m["cat"] != "muscle" or np.any(m["v"].max(0) < lo) or np.any(m["v"].min(0) > hi):
                continue
            c, dep = inside(v, m["v"], m["f"])
            if c.any():
                mus[mid_] = {"inside": int(c.sum()), "beyond_1mm": int((dep > 1).sum()), "max_depth_mm": round(float(dep.max()), 2)}
        st["vertices_inside_muscle"] = mus
        st["vertices_inside_any_muscle_frac"] = round(float(sum(x["inside"] for x in mus.values())) / len(v), 4)
        # relations every 10 mm
        rel = []
        fem = M["femur" + sfx]; sart = M.get("sartorius" + sfx)
        sg = 1.0 if side == "right" else -1.0
        for r in found:
            if r["y"] % 10:
                continue
            q = {"y": r["y"], "x": r["x"], "z": r["z"]}
            P = section_centroid(fem, r["y"])
            if P is not None:
                q["femur_medial_mm"] = round(float(sg * (P[:, 0].mean() - r["x"])), 1)        # +: medial of the femur centre
                q["femur_anterior_mm"] = round(float(r["z"] - P[:, 2].mean()), 1)             # +: anterior of the femur centre
                q["behind_femur_posterior_cortex_mm"] = round(float(P[:, 2].min() - r["z"]), 1)
                q["to_femur_surface_mm"] = round(float(np.min(np.hypot(P[:, 0] - r["x"], P[:, 2] - r["z"]))), 1)
            if sart is not None and aid.startswith("femoral"):
                S_ = section_centroid(sart, r["y"])
                if S_ is not None:
                    q["to_sartorius_mm"] = round(float(np.min(np.hypot(S_[:, 0] - r["x"], S_[:, 2] - r["z"]))), 1)
                    q["sartorius_anterior_of_it_mm"] = round(float(S_[:, 2].mean() - r["z"]), 1)
            for nm in ("adductor_longus", "vastus_medialis", "adductor_magnus"):
                mm = M.get(nm + sfx)
                if mm is not None and aid.startswith("femoral"):
                    S_ = section_centroid(mm, r["y"])
                    if S_ is not None:
                        q[f"to_{nm}_mm"] = round(float(np.min(np.hypot(S_[:, 0] - r["x"], S_[:, 2] - r["z"]))), 1)
            rel.append(q)
        st["relations_every_10mm"] = rel
        rep["structures"][aid] = st
        print(aid, {k: st[k] for k in ("spans_y", "tracked_levels", "gap_levels_filled", "diameter_mm")},
              "bone", {k: v_["inside"] for k, v_ in bone.items()}, "muscle frac", st["vertices_inside_any_muscle_frac"])
    # femoral triangle: artery lateral of the vein, per level
    for sd, sg in (("right", 1.0), ("left", -1.0)):
        sfx = "_r" if sd == "right" else "_l"
        A = {r["y"]: r for r in load_ship_rows(a.scratch, SHIP["femoral_a" + sfx][2], SHIP["femoral_a" + sfx][3])[1] if not r["gap"]}
        V = {r["y"]: r for r in load_ship_rows(a.scratch, SHIP["femoral_v" + sfx][2], SHIP["femoral_v" + sfx][3])[1] if not r["gap"]}
        ys = sorted(set(A) & set(V), reverse=True)
        lat = [sg * (A[y]["x"] - V[y]["x"]) for y in ys]; dz = [A[y]["z"] - V[y]["z"] for y in ys]
        rep.setdefault("femoral_artery_vs_vein", {})[sd] = {
            "levels": len(ys), "artery_lateral_of_vein_levels": int(sum(1 for v_ in lat if v_ > 0)),
            "lateral_offset_mm": {"median": round(float(np.median(lat)), 1), "min": round(float(np.min(lat)), 1), "max": round(float(np.max(lat)), 1)},
            "artery_anterior_of_vein_mm_median": round(float(np.median(dz)), 1)}
    # popliteal fossa depth order (+Z anterior): vein deeper than the tibial nerve, per level
    V = {r["y"]: r for r in load_ship_rows(a.scratch, "pop_left_vein", SHIP["popliteal_v_l"][3])[1] if not r["gap"]}
    N = {r["y"]: r for r in load_ship_rows(a.scratch, "pop_left_tibial_n", SHIP["tibial_n"][3])[1] if not r["gap"]}
    ys = sorted(set(V) & set(N), reverse=True)
    post = [V[y]["z"] - N[y]["z"] for y in ys]; lat = [-(N[y]["x"] - V[y]["x"]) for y in ys]
    rep["popliteal_depth_order_left"] = {
        "rule": "+Z anterior. Textbook order from superficial (posterior) to deep: tibial nerve, popliteal vein, popliteal artery. "
                "The artery is not shipped (see nulled), so the checked pair is nerve vs vein.",
        "levels": len(ys), "nerve_posterior_of_vein_levels": int(sum(1 for v_ in post if v_ > 0)),
        "nerve_posterior_offset_mm": {"median": round(float(np.median(post)), 1), "min": round(float(np.min(post)), 1), "max": round(float(np.max(post)), 1)},
        "nerve_lateral_offset_mm_median": round(float(np.median(lat)), 1),
        "per_level": {str(y): {"vein_z": V[y]["z"], "nerve_z": N[y]["z"]} for y in ys[::5]}}
    # tibial nerve vs his Q57 sciatic nerve (left): extrapolate the sciatic's lowest 40 mm to the tibial nerve's top
    sc = M.get("sciatic_n")
    if sc is not None:
        P = sc["v"][sc["v"][:, 0] < 0]; ylo = P[:, 1].min()
        low = P[P[:, 1] < ylo + 40]
        ys_ = np.unique(np.round(low[:, 1])); cx = np.array([low[np.abs(low[:, 1] - y) < 0.6][:, [0, 2]].mean(0) for y in ys_])
        kx = np.polyfit(ys_, cx[:, 0], 1); kz = np.polyfit(ys_, cx[:, 1], 1)
        top = N[max(N)]; yt = top["y"]
        ex = (np.polyval(kx, yt), np.polyval(kz, yt))
        rep["tibial_vs_q57_sciatic_left"] = {
            "sciatic_lowest_y": round(float(ylo), 1), "sciatic_centre_at_its_end": [round(float(v_), 1) for v_ in cx[0]],
            "tibial_top": {"y": yt, "x": top["x"], "z": top["z"]},
            "sciatic_extrapolated_linearly_to_tibial_top": [round(float(ex[0]), 1), round(float(ex[1]), 1)],
            "offset_mm": round(float(np.hypot(top["x"] - ex[0], top["z"] - ex[1])), 1),
            "offset_from_sciatic_end_mm": {"x": round(float(top["x"] - cx[0][0]), 1), "z": round(float(top["z"] - cx[0][1]), 1),
                                          "y": round(float(yt - ylo), 1)},
            "gap_mm": round(float(ylo - yt), 1),
            "note": "Not connected: his Q57 sciatic ends at the level shown and the tibial nerve is first detected ~170 mm lower; "
                    "the division of the sciatic at the apex of the fossa is not tracked."}
    rep["limits"] = [
        "Tracked masks are LUMINA (clot or gel), not vessel walls; the artery is an empty vessel whose gel-filled lumen under-measures it.",
        "Registration: the Q173 per-side shift (measured on his posterior thigh muscles + femur) is applied. Re-measured here on these crops: "
        "femur gives the same shift (right 6.4/0.0, left 6.2/-8.5 crop px); his anterior-thigh muscles alone give a smaller AP shift (~3-4 px, "
        "IoU only 0.30, not trusted) -- the anterior vessels may sit up to ~1 mm too posterior.",
        "Femoral vein vertices inside his (DU, decimated) adductor longus mesh: right 3297 / left 4061 beyond 1 mm, max 2.8 / 3.2 mm -- the "
        "canal vein lies on adductor longus in the photographs; the mesh surface and/or the ~1 mm registration residual account for it.",
        "Right femoral vein has a gap y -36..-97 (lymph-node-crowded apex of the femoral triangle, not verified) -> two pieces.",
        "Femoral vein below y -225 (right) / -280 (left) and the adductor hiatus are not covered; nor the popliteal division.",
        "Tibial nerve is not joined to his Q57 sciatic nerve (ends y -222; the tibial nerve starts at y -393).",
    ]
    rep["montages"] = "session scratch q174/final_*.png (per-level tiles of the shipped spans), q174/render.png"
    rep["attempts"] = {
        "femoral (right)": "1: her vhf_femoral_track.py unchanged on his registered crops -- artery -1..-46 then ragged masks; "
                           "vein -1..-46 then drifted. 2: this script (fixed dark core, blue/black separation, overlap walk, "
                           "canal seed, gel-filled artery seed). Shipped from 2.",
        "femoral (left)": "Only this script (2): her tracker's seed logic was tried inside it first (pair rule on his lumina picked a "
                          "3.2 mm side lumen / dark iliopsoas patches until the 12 mm2 floor and rim rule), then the gel-lumen artery seed.",
        "popliteal": "1: her vhf_popliteal_track.py unchanged (right) -- artery 30 ragged levels in fat, vein 77, nerve blobs on fat. "
                     "2: this script -- veins track, arteries do not (nulled), tibial nerve left only.",
    }
    Path(a.out).write_text(json.dumps(rep, indent=1))
    print("wrote", a.out)


BADGE = {
    "femoral_a": ("Rule-based tracking on his own 0.33 mm cryosection photographs (Q174): the gel-filled lumen of his EMPTY femoral "
                  "artery, seeded lateral of the femoral vein under the inguinal ligament and followed level by level. Covers y {span} "
                  "({n} levels, {cov}): the common femoral artery down to about the origin of the profunda; the superficial femoral "
                  "artery in the adductor canal is NOT covered (no lumen to follow). Lumen median {d} mm (a living man's common femoral "
                  "artery is ~10 mm outer diameter). Placed with the Q173 photograph-to-atlas registration."),
    "femoral_v": ("Rule-based tracking on his own 0.33 mm cryosection photographs (Q174): the clotted lumen of the femoral vein, seeded as "
                  "the medial member of the vessel pair under the inguinal ligament{canal}. Covers y {span} ({n} levels, {cov}). "
                  "Lumen median {d} mm (collapsed cadaveric vein). Placed with the Q173 photograph-to-atlas registration."),
    "popliteal_v": ("Rule-based tracking on his own 0.33 mm cryosection photographs (Q174): the clotted lumen behind the popliteal surface "
                    "of his femur. Covers y {span} ({n} levels, {cov}). Lumen median {d} mm. The popliteal ARTERY is not shown: his "
                    "arteries are empty and it could not be told from a paired vein. Placed with the Q173 registration."),
    "tibial_n": ("Rule-based tracking on his own 0.33 mm cryosection photographs (Q174): fascicle texture posterior to his LEFT popliteal "
                 "vein in the fossa. Covers y {span} ({n} levels, {cov}); left side only, not joined to the sciatic nerve above "
                 "(~170 mm untracked). Median section {d} mm. Placed with the Q173 registration."),
}


def badge(a):
    rep = json.loads(Path(a.report).read_text())
    for sj in ("ct_vhm_femoral", "ct_vhm_popliteal"):
        d = REPO / "build/vh" / sj; m = json.loads((d / "manifest.json").read_text())
        for st in m["structures"]:
            s = rep["structures"][st["atlas_id"]]
            key = st["atlas_id"].rsplit("_", 1)[0] if st["atlas_id"] != "tibial_n" else "tibial_n"
            span = " and ".join(f"{hi}..{lo}" for hi, lo in s["spans_y"])
            cov = f"{s['tracked_levels']} detected, {s['gap_levels_filled']} short gaps bridged"
            st["procedural_badge"] = BADGE[key].format(span=span, n=s["levels_in_spans"], cov=cov, d=s["diameter_mm"]["area_equivalent_median"],
                                                       canal=(" plus a second seed in the adductor canal (largest clotted lumen beside "
                                                              "sartorius at mid-thigh)" if st["atlas_id"] == "femoral_v_r" or
                                                              st["atlas_id"] == "femoral_v_l" else ""))
        (d / "manifest.json").write_text(json.dumps(m, indent=1))
        print(sj, [st["atlas_id"] for st in m["structures"]])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="mode", required=True)
    r = sub.add_parser("register"); r.add_argument("--crops", required=True); r.add_argument("--out", required=True)
    for nm, y0, y1 in (("femoral", 60.0, -420.0), ("popliteal", -290.0, -580.0)):
        t = sub.add_parser(nm)
        t.add_argument("--crops", required=True); t.add_argument("--side", required=True, choices=["right", "left"])
        t.add_argument("--bundle", default="build/viewer_m_hr"); t.add_argument("--y-start", type=float, default=y0)
        t.add_argument("--y-end", type=float, default=y1); t.add_argument("--out", required=True)
        t.add_argument("--max-gap", type=int, default=10)
        if nm == "popliteal":
            t.add_argument("--nerve-reach", type=float, default=6.0); t.add_argument("--nerve-gap", type=int, default=8)
    v = sub.add_parser("verify"); v.add_argument("--scratch", required=True, help="dir holding the *_clean.json tracks")
    v.add_argument("--bundle", default="build/viewer_m_hr"); v.add_argument("--out", default=str(REPO / "data/derived/Q174_vhm_femoral_popliteal.json"))
    b = sub.add_parser("badge"); b.add_argument("--report", default=str(REPO / "data/derived/Q174_vhm_femoral_popliteal.json"))
    a = ap.parse_args()
    {"register": register, "femoral": do_femoral, "popliteal": do_popliteal, "verify": verify, "badge": badge}[a.mode](a)


if __name__ == "__main__":
    main()
