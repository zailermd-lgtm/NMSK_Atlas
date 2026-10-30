"""Male cryosections: FULL-RESOLUTION (0.33 mm) crops of a fixed atlas-space box over a range of levels (Q57).

    python3 scripts/cryo/vhm_stream_leg_crops.py --index SCRATCH/vh_cryo/cryo_index.json --y-top -40 --y-bot -480 \
        --box right=0,215,-135,60 --box left=-215,0,-135,60 --ap-row -1 --out SCRATCH/q57/thigh

The atlas-box male counterpart of vhf_stream_crops.py (vhm_stream_crops.py takes photograph-pixel boxes and
instance numbers, no frame); writes the same <out>_<side>.npy + <out>_bbox.json that
vhf_nerve_track.Crops reads, with the in-plane mapping stored EXPLICITLY per body (X0, Y0, ap_row, CB), so
the tracker needs no body-specific constants. His photographs sit in the LEGS block of his 1 mm frame
(resample_cryo_to_ct_frame.py 'legs': photo index zi = round(-16 - z), rows flipped, shift (4, -96), scale
0.99). Mapping, per level (atlas y -> torso-corrected RAS z = y + oy):
    frame col c = X0 - RASx,  frame row r = Y0 + ap_row * RASy,
    1 mm photo row = (H-1) - (r - RS)/sc,  col = (c - CB - CS)/sc,  full resolution = x3.
AP SENSE (--ap-row, required, no default): the photograph frame has row 0 ANTERIOR (+row = posterior,
ap_row = -1) -- the same sense as her frame, and the OPPOSITE of legs_total.nii.gz's own grid (+Y per row).
Checked 2026-09-29 (Q57), not assumed: legs_total's femur/hip/gluteus labels land on the photographed bone
and muscle only when row-flipped (scratch q57/ts_overlay.png), and his vhm_both thigh-muscle sections cover
87.7 % photographed muscle at the best offset (X0 241-242, Y0 237-238) against 1-2 % less at the value used
here, which is the flip of legs_total's grid plus the fixed legs->torso block offset (+2.72, -0.89) mm:
X0 = 240 + 2.72, Y0 = (-239.0625 + 479) - 0.89.

BODY-AWARE (Q179): --body vhf streams HER photographs (her 1 mm frame -- frame.json/anchors.json of vhf_stream_crops.py --
was lost with a container reset). Level: her cryosection z (cryo_index.json col 3) = torso-RAS z - 944.7 mm (Q154
calibration, data/derived/Q154_vhf_ct_frame_calibration.json) + --z-offset (measured on her femur, Q179). In-plane: her
old frame's form (X0 350, Y0 240, ap_row -1, CB 110, H 405, sc 0.99) with a constant starting shift --rs-cs; the crops
are cut WIDER by --margin mm so that a later per-level, per-side registration (written into the bbox json as
RS_by_side / CS_by_side, read by vhf_nerve_track.Crops) can move the mapping without re-streaming. --body vhm (default)
is unchanged byte for byte.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import json
import sys
import time
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))
from scripts.cryo.vhf_stream_crops import fetch  # noqa: E402

H, W1, SC = 405, 682, 0.99                       # his 1 mm photographs (1216 x 2048 / 3), resample scale
RS, CS, CB = 4.0, -96.0, 0.0                     # legs-block in-plane shift (rows, cols) of resample_cryo_to_ct_frame.py
Z0 = -1671.0                                     # corrected-RAS z of legs frame k = 0
X0 = 240.0 + 2.72
Y0 = (-239.0625 + 479.0) - 0.89
ORIGIN = "-6.035,-895.476,4.787"                 # his atlas origin (vhm_rebuild_bundle.sh)
# her (Q179): old-frame form of vhf_stream_crops.py; cryo z = torso-RAS z - 944.7 (Q154) + z offset
VHF = {"X0": 350.0, "Y0": 240.0, "CB": 110.0, "ORIGIN": "7.769,-885.229,14.137", "CRYO_Z_MINUS_RAS": -944.7}


def level(y, idx, origin):
    """Atlas level y -> the photograph that shows it (instance = round(1880.476 - y) with his origin, as vhm_arm_muscles_v2.py)."""
    z = y + origin[1]; zi = int(round(-16 - z))
    if not 0 <= zi < len(idx):
        return None
    return {"zi": zi, "dcm": idx[zi][0], "RS": RS, "CS": CS, "z_ras": z, "z_photo": idx[zi][2], "k_frame": z - Z0}


def window(box, origin, ap_row):
    x0, x1, zz0, zz1 = box; ox, _, oz = origin
    cols = [X0 - (x + ox) for x in (x0, x1)]; rows = [Y0 + ap_row * (z + oz) for z in (zz0, zz1)]
    src_r = [(H - 1) - (r - RS) / SC for r in rows]; src_c = [(c - CB - CS) / SC for c in cols]
    rr0, rr1 = int(max(0, min(src_r))) * 3, int(min(H, max(src_r))) * 3
    cc0, cc1 = int(max(0, min(src_c))) * 3, int(min(W1, max(src_c))) * 3
    return [rr0, rr1, cc0, cc1]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--index", required=True, help="cryo_index.json of the full 1878-slice male series (stream_cryosections.py)")
    ap.add_argument("--y-top", type=float, required=True); ap.add_argument("--y-bot", type=float, required=True)
    ap.add_argument("--step", type=int, default=1); ap.add_argument("--box", action="append", required=True, help="side=x0,x1,z0,z1 (atlas mm)")
    ap.add_argument("--ap-row", type=int, required=True, choices=[-1, 1], help="frame rows per +RAS y (-1: row 0 anterior)")
    ap.add_argument("--origin", default=None); ap.add_argument("--out", required=True); ap.add_argument("--threads", type=int, default=6)
    ap.add_argument("--body", choices=["vhm", "vhf"], default="vhm", help="vhf: her photographs (Q179), see the module doc")
    ap.add_argument("--z-offset", default="0", help="vhf: mm added to her Q154 cryo z of each level: a number, or 'y:dz,y:dz' "
                    "(linear in atlas y between the given levels, constant beyond)")
    ap.add_argument("--rs-cs", default="0,-108", help="vhf: starting in-plane shift RS,CS (frame mm)")
    ap.add_argument("--margin", type=float, default=15.0, help="vhf: mm added around each box")
    a = ap.parse_args()
    if a.body == "vhf":
        return main_vhf(a)
    a.origin = a.origin or ORIGIN
    origin = [float(t) for t in a.origin.split(",")]; idx = json.load(open(a.index))
    boxes = {s: [float(t) for t in v.split(",")] for s, v in (b.split("=") for b in a.box)}
    ys = list(range(int(a.y_top), int(a.y_bot) - 1, -a.step))
    lm = {y: L for y in ys if (L := level(y, idx, origin)) is not None}
    ys = [y for y in ys if y in lm]
    win = {s: window(b, origin, a.ap_row) for s, b in boxes.items()}
    hmax = max(w[1] - w[0] for w in win.values()); wmax = max(w[3] - w[2] for w in win.values())
    print(f"{len(ys)} levels, photo idx {lm[ys[0]]['zi']}..{lm[ys[-1]]['zi']}, crop h,w {hmax},{wmax}", flush=True)
    mm = {s: np.lib.format.open_memmap(f"{a.out}_{s}.npy", mode="w+", dtype=np.uint8, shape=(len(ys), hmax, wmax, 3)) for s in boxes}
    t0 = time.time()
    with cf.ThreadPoolExecutor(a.threads) as ex:
        for j, px in enumerate(ex.map(lambda y: fetch(lm[y]["dcm"]), ys)):
            for s, w in win.items():
                crop = px[w[0]:w[1], w[2]:w[3]]; mm[s][j, :crop.shape[0], :crop.shape[1]] = crop
            if j % 50 == 0:
                print(j, f"{time.time() - t0:.0f}s", flush=True)
    for s in mm:
        mm[s].flush()
    json.dump({"body": "vhm", "y_atlas": ys, "levels": {str(y): dict(lm[y], windows=win) for y in ys}, "box_atlas": boxes,
               "origin": origin, "H": H, "sc": SC, "X0": X0, "Y0": Y0, "ap_row": a.ap_row, "CB": CB,
               "note": "full-res px = 3 x (1 mm photo px); frame r = Y0 + ap_row*RASy, c = X0 - RASx; photo row = (H-1) - (r-RS)/sc, "
                       "col = (c - CB - CS)/sc; atlas = (RASx - ox, RASz - oy, RASy - oz); RAS is torso-corrected"},
              open(f"{a.out}_bbox.json", "w"))
    print("done", f"{time.time() - t0:.0f}s")


def z_offset_at(spec, y):
    """--z-offset: '-17' or '0:-20,-375:-14' (atlas y : mm, linear between, constant beyond)."""
    if ":" not in str(spec):
        return float(spec)
    pts = sorted((float(a), float(b)) for a, b in (t.split(":") for t in str(spec).split(",")))
    return float(np.interp(y, [p[0] for p in pts], [p[1] for p in pts]))


def level_vhf(y, idx, zc, origin, z_offset):
    """her atlas level y -> nearest photograph by her cryo z (Q154 offset + the Q179 z offset)."""
    zr = y + origin[1]; dz = z_offset_at(z_offset, y); want = zr + VHF["CRYO_Z_MINUS_RAS"] + dz; zi = int(np.argmin(np.abs(zc - want)))
    if abs(zc[zi] - want) > 0.5:
        return None
    return {"zi": zi, "dcm": idx[zi][0], "z_ras": zr, "z_photo": float(zc[zi]), "z_photo_wanted": round(want, 3), "z_offset_mm": round(dz, 3)}


def window_vhf(box, origin, RS, CS, margin):
    x0, x1, zz0, zz1 = box; ox, _, oz = origin
    xs = (x0 - margin, x1 + margin); zs = (zz0 - margin, zz1 + margin)
    cols = [VHF["X0"] - (x + ox) for x in xs]; rows = [VHF["Y0"] - (z + oz) for z in zs]
    src_r = [(H - 1) - (r - RS) / SC for r in rows]; src_c = [(c - VHF["CB"] - CS) / SC for c in cols]
    rr0, rr1 = int(max(0, min(src_r))) * 3, int(min(H, max(src_r))) * 3
    cc0, cc1 = int(max(0, min(src_c))) * 3, int(min(W1, max(src_c))) * 3
    return [rr0, rr1, cc0, cc1]


def main_vhf(a):
    origin = [float(t) for t in (a.origin or VHF["ORIGIN"]).split(",")]; idx = json.load(open(a.index)); zc = np.array([e[2] for e in idx])
    RS0, CS0 = (float(t) for t in a.rs_cs.split(","))
    boxes = {s: [float(t) for t in v.split(",")] for s, v in (b.split("=") for b in a.box)}
    ys = list(range(int(a.y_top), int(a.y_bot) - 1, -a.step))
    lm = {y: L for y in ys if (L := level_vhf(y, idx, zc, origin, a.z_offset)) is not None}
    ys = [y for y in ys if y in lm]
    win = {s: window_vhf(b, origin, RS0, CS0, a.margin) for s, b in boxes.items()}
    hmax = max(w[1] - w[0] for w in win.values()); wmax = max(w[3] - w[2] for w in win.values())
    print(f"{len(ys)} levels, photo idx {lm[ys[0]]['zi']}..{lm[ys[-1]]['zi']}, crop h,w {hmax},{wmax}", flush=True)
    mm = {s: np.lib.format.open_memmap(f"{a.out}_{s}.npy", mode="w+", dtype=np.uint8, shape=(len(ys), hmax, wmax, 3)) for s in boxes}
    t0 = time.time()
    with cf.ThreadPoolExecutor(a.threads) as ex:
        for j, px in enumerate(ex.map(lambda y: fetch(lm[y]["dcm"]), ys)):
            for s, w in win.items():
                crop = px[w[0]:w[1], w[2]:w[3]]; mm[s][j, :crop.shape[0], :crop.shape[1]] = crop
            if j % 50 == 0:
                print(j, f"{time.time() - t0:.0f}s", flush=True)
    for s in mm:
        mm[s].flush()
    json.dump({"body": "vhf", "y_atlas": ys, "levels": {str(y): dict(lm[y], RS=RS0, CS=CS0, windows=win) for y in ys}, "box_atlas": boxes,
               "origin": origin, "H": H, "sc": SC, "X0": VHF["X0"], "Y0": VHF["Y0"], "ap_row": -1, "CB": VHF["CB"],
               "z_offset_mm": a.z_offset, "margin_mm": a.margin,
               "note": "her photographs (Q179): cryo z = torso-RAS z - 944.7 (Q154) + z_offset_mm; frame r = Y0 - RASy, c = X0 - RASx; "
                       "photo row = (H-1) - (r-RS)/sc, col = (c - CB - CS)/sc, full resolution x3; RS/CS per level are the STARTING "
                       "shift until a registration writes RS_by_side / CS_by_side; atlas = (RASx - ox, RASz - oy, RASy - oz)"},
              open(f"{a.out}_bbox.json", "w"))
    print("done", f"{time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
