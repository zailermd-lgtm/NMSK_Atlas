"""Female cryosections: FULL-RESOLUTION (0.33 mm) crops of a fixed atlas-space box over a range of levels.

    python3 scripts/cryo/vhf_stream_crops.py --frame SCRATCH/vh_cryo_f --y-top -40 --y-bot -420 \
        --box right=0,200,-140,80 --box left=-200,0,-140,80 --out SCRATCH/vh_cryo_f/thigh --step 1

Generalises vhf_stream_arm_crops.py. The box is given in ATLAS mm per side (x0,x1,z0,z1); levels are atlas y
(1 mm apart, --step). The corrected frame (frame.json "z_correction": frame slice k shows source slice
k + offset(y)) decides which photograph each level comes from, and the registration's per-level in-plane
shift (anchors.json, as vhf_resample_cryo.py) turns frame pixels into photograph pixels, x3 for full
resolution. Output: <out>_<side>.npy memmap (Z, h, w, 3) uint8 and <out>_bbox.json with, per level, the
photograph index and the window, plus the mapping needed to send a full-resolution pixel back to RAS mm:
    frame row r = (H-1 - pr/3) * sc + RS,  frame col c = (pc/3) * sc + 110 + CS,  RAS x = 350 - c, RAS y = 240 - r.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import io
import json
import time
import urllib.request
from pathlib import Path

import numpy as np
import pydicom
from scipy import ndimage as ndi

H, W1, SC, ORIGIN_Y = 405, 682, 0.99, -885.229


def level_mapping(frame_dir: Path, ys, origin):
    """Per atlas level y: (photo index zi, row shift RS, col shift CS) on the corrected frame."""
    fr = json.load(open(frame_dir / "frame.json")); idx = json.load(open(frame_dir / "cryo_index.json"))
    a0, b = fr["z_offset_line"]; z0 = fr["z0"]
    corr = fr.get("z_correction", {}).get("offset_mm_at_y", {})
    cy = np.array(sorted(float(k) for k in corr)); co = np.array([corr[str(int(k))] for k in cy]) if len(cy) else None
    A = [a for a in json.load(open(frame_dir / "anchors.json")) if a["flip"] == "fy" and a["iou"] >= 0.7]
    zs_a = np.array([a["ct_z"] for a in A]); o = np.argsort(zs_a)
    rs = ndi.median_filter(np.array([a["shift"][0] for a in A], float), size=5, mode="nearest")[o]
    cs = ndi.median_filter(np.array([a["shift"][1] for a in A], float), size=5, mode="nearest")[o]; zs_a = zs_a[o]
    out = {}
    for y in ys:
        z = y + origin[1]                                   # RAS z of the corrected frame slice
        off = float(np.interp(y, cy, co)) if co is not None else 0.0
        zsrc = z + off                                      # frame v1 slice that shows this anatomy
        zi = int(round(-(a0 + b * zsrc) - zsrc))
        if not (0 <= zi < len(idx)):
            continue
        out[int(y)] = {"zi": zi, "dcm": idx[zi][0], "RS": float(np.interp(zsrc, zs_a, rs)), "CS": float(np.interp(zsrc, zs_a, cs)),
                       "z_ras": z, "z_src": zsrc}
    return out


def window(box, RS, CS, origin):
    x0, x1, zz0, zz1 = box; ox, oy, oz = origin
    cols = [350.0 - (x + ox) for x in (x0, x1)]; rows = [240.0 - (z + oz) for z in (zz0, zz1)]
    src_r = [(H - 1) - (r - RS) / SC for r in rows]; src_c = [(c - 110 - CS) / SC for c in cols]
    rr0, rr1 = int(max(0, min(src_r))) * 3, int(min(H, max(src_r))) * 3
    cc0, cc1 = int(max(0, min(src_c))) * 3, int(min(W1, max(src_c))) * 3
    return [rr0, rr1, cc0, cc1]


def fetch(name):
    err = None
    for _ in range(4):
        try:
            d = urllib.request.urlopen(f"https://storage.googleapis.com/idc-open-data/{name}", timeout=60).read()
            return pydicom.dcmread(io.BytesIO(d)).pixel_array
        except Exception as e:  # noqa: BLE001
            err = e; time.sleep(2)
    raise err


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--frame", required=True); ap.add_argument("--y-top", type=float, required=True); ap.add_argument("--y-bot", type=float, required=True)
    ap.add_argument("--step", type=int, default=1); ap.add_argument("--box", action="append", required=True, help="side=x0,x1,z0,z1 (atlas mm)")
    ap.add_argument("--origin", default="7.769,-885.229,14.137"); ap.add_argument("--out", required=True); ap.add_argument("--threads", type=int, default=6)
    a = ap.parse_args()
    origin = [float(t) for t in a.origin.split(",")]
    boxes = {s: [float(t) for t in v.split(",")] for s, v in (b.split("=") for b in a.box)}
    ys = list(range(int(a.y_top), int(a.y_bot) - 1, -a.step))
    lm = level_mapping(Path(a.frame), ys, origin); ys = [y for y in ys if y in lm]
    win = {y: {s: window(b, lm[y]["RS"], lm[y]["CS"], origin) for s, b in boxes.items()} for y in ys}
    hmax = max(w[1] - w[0] for v in win.values() for w in v.values()); wmax = max(w[3] - w[2] for v in win.values() for w in v.values())
    print(f"{len(ys)} levels, photo idx {lm[ys[0]]['zi']}..{lm[ys[-1]]['zi']}, crop max h,w {hmax},{wmax}", flush=True)
    mm = {s: np.lib.format.open_memmap(f"{a.out}_{s}.npy", mode="w+", dtype=np.uint8, shape=(len(ys), hmax, wmax, 3)) for s in boxes}
    t0 = time.time()
    with cf.ThreadPoolExecutor(a.threads) as ex:
        for j, px in enumerate(ex.map(lambda y: fetch(lm[y]["dcm"]), ys)):
            for s, w in win[ys[j]].items():
                crop = px[w[0]:w[1], w[2]:w[3]]; mm[s][j, :crop.shape[0], :crop.shape[1]] = crop
            if j % 100 == 0:
                print(j, f"{time.time() - t0:.0f}s", flush=True)
    for s in mm:
        mm[s].flush()
    json.dump({"y_atlas": ys, "levels": {str(y): dict(lm[y], windows=win[y]) for y in ys}, "box_atlas": boxes, "origin": origin,
               "H": H, "sc": SC, "note": "full-res px = 3 x (1 mm photo px); frame row r = (H-1 - pr/3)*sc + RS, col c = (pc/3)*sc + 110 + CS; "
               "RAS x = 350 - c, RAS y = 240 - r; atlas = (RASx - ox, y, RASy - oz)"},
              open(f"{a.out}_bbox.json", "w"))
    print("done", f"{time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
